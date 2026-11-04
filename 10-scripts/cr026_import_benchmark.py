#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Component: the CR-023 import runner at CR-026 volume — THE MEASUREMENT, run
#            against real Postgres with the real stages and rolled back after.
# Change:   CR-026 (PO 2026-08-22 — *"the sizes of CSV file scan be 50,000 or
#           100,000 units or premises at a time; how you will hnadle such
#           volume in upload"*). The first half's figures — extract 6.8s ·
#           transform 77.9s · validate 50.8s · load 101.5s at 50,000 rows —
#           came from this measurement; the second half re-runs it, because a
#           background stage that is not measured is a claim, not a result.
# Rules:    BR-MET-085 · BR-MET-090 · BR-MET-096 (ONE runner) · CLAUDE.md
#           rule 1 (tenant scoping)
# ───────────────────────────────────────────────────────
"""How long does a 50,000-row premises import actually take, stage by stage?

WHY THIS IS A SCRIPT AND NOT A TEST. The figures it produces are the input to a
DESIGN DECISION (which stages must leave the request cycle, and where the bar
between synchronous and deferred goes), not an assertion about behaviour — and
a four-minute case in a suite that runs on every commit would be paid for by
every lane, forever, to re-learn a number that changes only when the engine
does. The suite asserts the RATIFIED bar (`tests/test_cr026_background_stages.
py::test_the_ratified_async_bar_is_5000_rows`); this says whether that bar is
still the right one.

IT WRITES NOTHING. Every pass runs inside one transaction that is rolled back at
the end, so a 50,000-row load can be measured against a live database — the dev
box's own — without leaving 50,000 premises behind. Nothing is committed, so
nothing needs cleaning up, and the script may be run as often as it is useful.

TWO PASSES, WHICH IS THE WHOLE POINT:

* **sync** — `ASYNC_ROW_BAR` raised above the row count, so every stage runs in
  the caller exactly as it did before CR-026's second half. This reproduces the
  baseline figures and is what "before" means.
* **deferred** — the bar left where it is, so transform, validate and load each
  go through `core.jobs` (a job record, the handler registry, the tenant
  re-entry, the gauge) and back. With `JOBS_EAGER=true` the body runs inside the
  enqueue, so the wall time is the stage PLUS the machinery, which is precisely
  the overhead CR-026's second half added and the number worth publishing.

⚠ **`IMPORT_PROGRESS_ISOLATED` IS FORCED OFF HERE** and that is a measurement
decision, stated so nobody reads the figure as something it is not. In
production the gauge is written on a second, autocommit connection so a poller
can read it while the stage holds its row lock; that connection cannot see this
script's uncommitted run row, so every write would fail its foreign key, be
swallowed (by design — a gauge never fails the work it measures) and be timed as
a failure instead of a write. Off, the same rows are written through the ORM on
this connection: one UPDATE per 1,000 rows, ~50 per stage at 50,000 rows, which
is the cost the throttle exists to make negligible.

USAGE
    python3 10-scripts/cr026_import_benchmark.py                # 50,000 rows, both passes
    python3 10-scripts/cr026_import_benchmark.py --rows 100000  # the PO's upper figure
    python3 10-scripts/cr026_import_benchmark.py --pass sync    # baseline only
"""

from __future__ import annotations

import argparse
import csv
import io
import os
import sys
import time
from pathlib import Path
from types import SimpleNamespace

BACKEND = Path(__file__).resolve().parent.parent / "06-backend"
sys.path.insert(0, str(BACKEND))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
os.environ.setdefault("DATABASE_URL", "postgres://sbh:sbh@127.0.0.1:5432/sbh")
# The deferred pass needs the body to actually RUN in-process; a broker and a
# worker would measure a queue rather than the engine.
os.environ.setdefault("JOBS_EAGER", "true")

import django  # noqa: E402

django.setup()

from django.conf import settings  # noqa: E402
from django.db import transaction  # noqa: E402

settings.IMPORT_PROGRESS_ISOLATED = False  # see the docstring — a measurement choice

from apps.identity import models as identity_models  # noqa: E402
from apps.metering import import_runs, models  # noqa: E402
from apps.tenancy import models as tenancy_models  # noqa: E402
from core import tenancy as core_tenancy  # noqa: E402

HEADERS = [
    "PREMISE_ID",
    "ADDR1",
    "CITY",
    "STATE",
    "ZIP",
    "PROP_TYPE",
    "SVC_AVAIL",
    "OWNER",
    "LEGACY_KEY",
    "INSIDE_CITY",
]

MAPPING = {
    "PREMISE_ID": "premise_no",
    "ADDR1": "address_line",
    "CITY": "city",
    "STATE": "state",
    "ZIP": "postal_code",
    "PROP_TYPE": "premises_type",
    "SVC_AVAIL": "services_available",
    "OWNER": "owner_manager",
    "LEGACY_KEY": "external_ref",
    "INSIDE_CITY": "inside_city_limits",
}

ROW_HANDLING = {
    "drop_exact_duplicates": True,
    "keep_latest_on_key": False,
    "skip_rows_missing_required": False,
}

STAGES = ("extract", "transform", "validate", "dry_run", "load")


class _Rollback(Exception):
    """Carries the figures out of the transaction that is being thrown away."""

    def __init__(self, figures: dict[str, float]) -> None:
        super().__init__("benchmark complete — rolling back")
        self.figures = figures


def _tenant():
    tenant = tenancy_models.Tenant.objects.order_by("created_at").first()
    if tenant is None:
        sys.exit("no tenant in this database — run 10-scripts/03-seed_demo.py first")
    return tenant


def _actor(tenant):
    user = identity_models.User.objects.filter(tenant_id=tenant.id).order_by("created_at").first()
    if user is None:
        sys.exit(f"tenant {tenant.name!r} has no user to act as")
    return SimpleNamespace(id=user.id, pk=user.id, role="system_admin", user=user)


def _world(tenant) -> tuple[str, str]:
    """The premises type and the services THIS tenant actually has.

    A file naming a type it does not have would measure the reject path, and a
    service it does not sell is a BR-MET-003 error on every row — either would
    time a different piece of work than the one being measured.
    """
    kind = models.PremisesType.objects.filter(tenant_id=tenant.id, active=True).first()
    services = list(
        tenancy_models.TenantService.objects.filter(tenant_id=tenant.id, enabled=True)
        .select_related("service")
        .order_by("service__code")[:2]
    )
    if kind is None or not services:
        sys.exit(f"tenant {tenant.name!r} has no premises types or no enabled services")
    return kind.code, ",".join(row.service.code for row in services)


def build_csv(rows: int, kind: str, services: str) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(HEADERS)
    for index in range(1, rows + 1):
        writer.writerow(
            [
                f"BM-{100000 + index}",
                f"{index} Bluestem Ln",
                "Katy",
                "TX",
                "77494",
                kind,
                services,
                "Whitfield Rentals LLC",
                str(880000 + index),
                "inside",
            ]
        )
    return buffer.getvalue()


def _timed(label: str, call) -> tuple[object, float]:
    started = time.perf_counter()
    answer = call()
    elapsed = time.perf_counter() - started
    print(f"  {label:<10} {elapsed:8.1f}s")
    return answer, elapsed


def _check(run_id, expected: str, stage: str) -> None:
    """A deferred stage that failed answers 202 and changes nothing — so the
    RUN's own status is what says whether the work happened."""
    status = models.ImportRun.objects.get(pk=run_id).status
    if status != expected:
        job = tenancy_models.Job.objects.order_by("-created_at").first()
        sys.exit(
            f"{stage} did not complete: run is {status!r}, expected {expected!r}"
            + (f" — job says: {job.error}" if job is not None and job.error else "")
        )


def one_pass(tenant, actor, content: str, rows: int, *, defer: bool) -> dict[str, float]:
    label = "deferred (through core.jobs)" if defer else "sync (ASYNC_ROW_BAR raised)"
    print(f"\n── {rows:,} rows · {label} ──")
    original_bar = import_runs.ASYNC_ROW_BAR
    import_runs.ASYNC_ROW_BAR = original_bar if defer else rows + 1
    figures: dict[str, float] = {}
    try:
        with transaction.atomic():
            run, figures["extract"] = _timed(
                "extract",
                lambda: import_runs.extract(
                    actor,
                    {
                        "target": "premises",
                        "source_kind": "file",
                        "file_name": f"benchmark_{rows}.csv",
                        "content": content,
                        "session_ref": "sess_bench",
                        "ip": "127.0.0.1",
                    },
                ),
            )
            run_id = run["id"]
            _check(run_id, "extracted", "extract")

            _, figures["transform"] = _timed(
                "transform",
                lambda: import_runs.transform(
                    actor, run_id, {"mapping": MAPPING, "row_handling": ROW_HANDLING}
                ),
            )
            _check(run_id, "transformed", "transform")

            _, figures["validate"] = _timed("validate", lambda: import_runs.validate(actor, run_id))
            _check(run_id, "validated", "validate")

            _, figures["dry_run"] = _timed(
                "dry-run", lambda: import_runs.dry_run(actor, run_id, "insert")
            )

            _, figures["load"] = _timed(
                "load", lambda: import_runs.load(actor, run_id, {"write_mode": "insert"})
            )
            _check(run_id, "loaded", "load")

            written = models.Premises.objects.filter(tenant_id=tenant.id).count()
            print(f"  premises now  {written:,} (rolled back below)")
            raise _Rollback(figures)
    except _Rollback as done:
        figures = done.figures
    finally:
        import_runs.ASYNC_ROW_BAR = original_bar

    total = sum(figures.values())
    print(f"  {'TOTAL':<10} {total:8.1f}s   ({total * 1000 / rows:.2f} ms/row)")
    return figures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=50_000)
    parser.add_argument(
        "--pass", dest="which", choices=("sync", "deferred", "both"), default="both"
    )
    args = parser.parse_args()

    tenant = _tenant()
    actor = _actor(tenant)
    kind, services = _world(tenant)
    print(f"tenant: {tenant.name} · type {kind} · services {services}")

    with core_tenancy.tenant_context(tenant.id):
        started = time.perf_counter()
        content = build_csv(args.rows, kind, services)
        print(
            f"file:   {args.rows:,} rows, {len(content.encode()) / 1024 / 1024:.1f} MB, "
            f"built in {time.perf_counter() - started:.1f}s"
        )

        results: dict[str, dict[str, float]] = {}
        if args.which in ("sync", "both"):
            results["sync"] = one_pass(tenant, actor, content, args.rows, defer=False)
        if args.which in ("deferred", "both"):
            results["deferred"] = one_pass(tenant, actor, content, args.rows, defer=True)

    if len(results) == 2:
        print(f"\n── {args.rows:,} rows · sync vs deferred ──")
        print(f"  {'stage':<10} {'sync':>9} {'deferred':>10} {'delta':>9}")
        for stage in STAGES:
            before, after = results["sync"][stage], results["deferred"][stage]
            print(f"  {stage:<10} {before:8.1f}s {after:9.1f}s {after - before:+8.1f}s")
        before, after = sum(results["sync"].values()), sum(results["deferred"].values())
        print(f"  {'TOTAL':<10} {before:8.1f}s {after:9.1f}s {after - before:+8.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
