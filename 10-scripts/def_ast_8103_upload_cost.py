#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-AST-8103 — updating 400–500 assets by upload took ~14 s for 500
#           (≈19 statements per row) and, with JOBS_EAGER=true on the
#           deployment, ran inside the request against gunicorn's 60 s.
# Ruling:   PO GO 2026-09-30, step 2: MEASURE on PostgreSQL at 100/500/1,000
#           rows (wall-clock + statements/row) before and after, and set the
#           assets load bar from the numbers.
# Rules:    BR-MET-085 · BR-MET-096 (ONE runner) · CLAUDE.md law 14 (measure
#           on PostgreSQL, never SQLite)
# ───────────────────────────────────────────────────────
"""Asset upload LOAD cost on PostgreSQL — insert and update, per row.

Modelled on `def2487_accounts_bar_benchmark.py` (accounts) and
`pay_p1_1_load_bar_benchmark.py` (payments), which answer the same question for
their targets and are the other two columns of the lane's table.

IT WRITES NOTHING. Each pass runs inside one transaction that is rolled back.
The load bar is raised for the pass so the LOAD BODY is timed in-process
rather than a deferral; statements are counted with an execute wrapper.

USAGE (the lane's throwaway cluster, a migrated + `seed_demo`'d database):
    DJANGO_SETTINGS_MODULE=config.settings.local \\
    DATABASE_URL=postgres://postgres@127.0.0.1:55491/sbh_dev \\
    python3 10-scripts/def_ast_8103_upload_cost.py --rows 100 500 1000
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path
from types import SimpleNamespace

BACKEND = Path(__file__).resolve().parent.parent / "06-backend"
sys.path.insert(0, str(BACKEND))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
os.environ.setdefault("JOBS_EAGER", "false")

import django  # noqa: E402

django.setup()

from django.conf import settings  # noqa: E402
from django.db import connection, transaction  # noqa: E402

settings.IMPORT_PROGRESS_ISOLATED = False

from apps.assets import models as asset_models  # noqa: E402
from apps.identity import models as identity_models  # noqa: E402
from apps.metering import import_runs  # noqa: E402
from apps.tenancy import models as tenancy_models  # noqa: E402
from core import tenancy as core_tenancy  # noqa: E402

GUNICORN_TIMEOUT_S = 60.0
TARGET = import_runs.TARGET_ASSETS_METERS
HEADER = ["Meter number (existing only)", "External reference", "Service", "Multiplier",
          "Manufacturer"]  # fmt: skip


class _Rollback(Exception):
    def __init__(self, figures: dict[str, float]) -> None:
        super().__init__("measured — rolling back")
        self.figures = figures


def _csv(rows: list[list[str]]) -> str:
    return "\n".join(",".join(r) for r in [HEADER, *rows]) + "\n"


def _stages(actor, content: str, write_mode: str) -> str:
    run = import_runs.extract(
        actor,
        {"target": TARGET, "source_kind": "file", "file_name": "bench.csv",
         "content": content, "session_ref": "sess_bench", "write_mode": write_mode},
    )  # fmt: skip
    import_runs.transform(
        actor,
        run["id"],
        {"mapping": run["detected_mapping"],
         "row_handling": {k: False for k in import_runs.ROW_HANDLING_KEYS}},
    )  # fmt: skip
    import_runs.validate(actor, run["id"], write_mode)
    return run["id"]


def _load(actor, run_id: str, write_mode: str) -> tuple[float, int]:
    """(seconds, statements). Counted with an execute wrapper, NOT
    `CaptureQueriesContext`: that keeps only the last 9,000 queries, so at 500
    rows it silently reported 0 statements per row (law 7 — a check reporting
    zero over a scope it excludes; found on this script's own first run)."""
    count = [0]

    def _count(execute, sql, params, many, context):
        count[0] += 1
        return execute(sql, params, many, context)

    with connection.execute_wrapper(_count):
        started = time.perf_counter()
        import_runs.load(actor, run_id, {"write_mode": write_mode, "approved": True})
        elapsed = time.perf_counter() - started
    return elapsed, count[0]


def one_pass(actor, service: str, rows: int) -> dict[str, float]:
    key = (TARGET, "load")
    original = import_runs.ASYNC_ROW_BAR_BY_TARGET.get(key)
    stamp = int(time.time() * 1000)
    figures: dict[str, float] = {}
    try:
        with transaction.atomic():
            import_runs.ASYNC_ROW_BAR_BY_TARGET[key] = rows + 1
            inserts = [["", f"B{stamp}-{n}", service, "1", ""] for n in range(rows)]
            run_id = _stages(actor, _csv(inserts), "insert")
            figures["insert_s"], figures["insert_q"] = _load(actor, run_id, "insert")
            numbers = dict(
                asset_models.Asset.objects.filter(
                    external_ref__startswith=f"B{stamp}-"
                ).values_list("external_ref", "asset_no")
            )
            if len(numbers) != rows:
                sys.exit(f"expected {rows} created, got {len(numbers)} — wrong path")
            updates = [[numbers[f"B{stamp}-{n}"], f"B{stamp}-{n}", service, "2", "Acme"]
                       for n in range(rows)]  # fmt: skip
            run_id = _stages(actor, _csv(updates), "upsert")
            figures["update_s"], figures["update_q"] = _load(actor, run_id, "upsert")
            raise _Rollback(figures)
    except _Rollback as done:
        figures = done.figures
    finally:
        if original is None:
            import_runs.ASYNC_ROW_BAR_BY_TARGET.pop(key, None)
        else:
            import_runs.ASYNC_ROW_BAR_BY_TARGET[key] = original
    return figures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, nargs="+", default=[100, 500, 1000])
    args = parser.parse_args()
    tenant = tenancy_models.Tenant.objects.order_by("created_at").first()
    if tenant is None:
        sys.exit("no tenant — run `manage.py seed_demo` first")
    user = identity_models.User.objects.filter(tenant_id=tenant.id).order_by("created_at").first()
    actor = SimpleNamespace(id=user.id, pk=user.id, role="system_admin", user=user)
    with core_tenancy.tenant_context(tenant.id):
        from apps.metering import seams

        units = seams.service_default_uoms()
        service = next((c for c in sorted(units) if units[c]), None)
        print(f"tenant: {tenant.name} · service {service}")
        results = {rows: one_pass(actor, service, rows) for rows in args.rows}
    print("\n  rows | insert s | stmt/row | update s | stmt/row | vs 60 s")
    for rows, f in results.items():
        print(
            f"  {rows:>4} | {f['insert_s']:8.2f} | {f['insert_q'] / rows:8.1f} | "
            f"{f['update_s']:8.2f} | {f['update_q'] / rows:8.1f} | "
            f"{'inside' if max(f['insert_s'], f['update_s']) < GUNICORN_TIMEOUT_S else 'OVER'}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
