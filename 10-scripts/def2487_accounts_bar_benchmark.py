#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Component: the CR-023 import runner's ACCOUNTS target, timed against the wall
#            the request actually has to clear — gunicorn's `--timeout 60`
#            (06-backend/docker-entrypoint.sh:168).
# Defect:   DEF-2487 (critical) — the accounts commit of 1,048 rows is killed by
#           that timeout after a clean dry run, and the screen can only say
#           "Something went wrong. Nothing was saved — try again."
# Rules:    BR-MET-085 · BR-MET-090 · BR-MET-096 (ONE runner) · BR-CUS-047 (an
#           account is opened on a unit) · CLAUDE.md rule 1 (tenant scoping)
# ───────────────────────────────────────────────────────
"""How long does an ACCOUNTS import take per row, and where does the bar go?

`10-scripts/cr026_import_benchmark.py` measured the PREMISES target and the bar
of 5,000 rows was set from it. **An accounts row is not a premises row.** It
opens an account, inherits the unit's services, plan and meters (CR-047 /
BR-CUS-672/673), writes an opening balance, posts to the ledger and snapshots
the whole account-detail payload for its audit row — so its per-row cost is an
order of magnitude larger, and one bar for every target is the arithmetic that
produced DEF-2487.

This script answers the only question that matters for the bar: **at N accounts,
does the load stage finish inside the sixty seconds the web worker gives it?**

IT WRITES NOTHING. Units, accounts, journal entries and the run itself are all
created inside one transaction that is rolled back, so it may be run against the
dev database as often as it is useful — the same posture, and for the same
reason, as the CR-026 script it is modelled on.

USAGE
    DJANGO_SETTINGS_MODULE=config.settings.local \\
    DATABASE_URL=postgres://smartbillhub:smartbillhub@localhost:5432/smartbillhub \\
    python3 10-scripts/def2487_accounts_bar_benchmark.py --rows 100 500 1048
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
os.environ.setdefault(
    "DATABASE_URL", "postgres://smartbillhub:smartbillhub@localhost:5432/smartbillhub"
)
# A worker would measure a queue rather than the engine; this times the BODY.
os.environ.setdefault("JOBS_EAGER", "false")

import django  # noqa: E402

django.setup()

from django.conf import settings  # noqa: E402
from django.db import transaction  # noqa: E402

settings.IMPORT_PROGRESS_ISOLATED = False  # see the CR-026 script's docstring

from apps.identity import models as identity_models  # noqa: E402
from apps.metering import import_runs, models, services as metering_services  # noqa: E402
from apps.rating import models as rating_models  # noqa: E402
from apps.tenancy import models as tenancy_models  # noqa: E402
from core import tenancy as core_tenancy  # noqa: E402

#: The wall the request has to clear. `06-backend/docker-entrypoint.sh` runs
#: `gunicorn --timeout "${GUNICORN_TIMEOUT:-60}"`, and a sync worker that is
#: still inside the WSGI call at that point is SIGKILLed — no exception, no
#: response body, nothing written. That is DEF-2487.
GUNICORN_TIMEOUT_S = 60.0

HEADERS = "UNIT_REF,ACCT,NAME,CUST_ID,TYPE,STATUS,OPENED,CURRENT"
MAPPING = {
    "UNIT_REF": "unit_ref",
    "ACCT": "account_no",
    "NAME": "customer_name",
    "CUST_ID": "customer_ref",
    "TYPE": "account_type",
    "STATUS": "status",
    "OPENED": "opened_at",
    "CURRENT": "ob_current",
}


class _Rollback(Exception):
    """Carries the figures out of the transaction that is being thrown away."""

    def __init__(self, figures: dict[str, float]) -> None:
        super().__init__("benchmark complete — rolling back")
        self.figures = figures


def _tenant():
    tenant = tenancy_models.Tenant.objects.order_by("created_at").first()
    if tenant is None:
        sys.exit("no tenant in this database — run `manage.py seed_demo` first")
    return tenant


def _actor(tenant):
    user = identity_models.User.objects.filter(tenant_id=tenant.id).order_by("created_at").first()
    if user is None:
        sys.exit(f"tenant {tenant.name!r} has no user to act as")
    return SimpleNamespace(id=user.id, pk=user.id, role="system_admin", user=user)


def _world(tenant):
    """The published plan and the first enabled service THIS tenant has.

    A unit with no plan and no service point would measure the cheap path — the
    one an account inherits nothing from — which is not the path a migration
    takes and not the one that timed out.
    """
    plan = rating_models.RatePlan.objects.filter(tenant_id=tenant.id, status="published").first()
    service = (
        tenancy_models.TenantService.objects.filter(tenant_id=tenant.id, enabled=True)
        .select_related("service")
        .order_by("service__code")
        .first()
    )
    if plan is None or service is None:
        sys.exit(f"tenant {tenant.name!r} has no published plan or no enabled service")
    return plan, service.service.code


def _units(actor, plan, service_code: str, rows: int) -> list[dict]:
    from apps.metering import premises_owners

    found = premises_owners.resolve_owner_name("Whitfield Rentals LLC")
    owner_id = (
        found["owner"]["id"]
        if found["match"] == "exact"
        else premises_owners.create_premises_owner(
            actor, {"name": "Whitfield Rentals LLC", "category": "landlord"}
        )["id"]
    )
    premises = metering_services.create_premises(
        actor,
        {
            "address_line": f"1 Benchmark Way {time.time():.0f}",
            "city": "Katy",
            "state": "TX",
            "postal_code": "77494",
            "premises_type": models.PremisesType.objects.filter(active=True).first().code,
            "services_available": [service_code],
            "owner_manager": "Whitfield Rentals LLC",
            "owner_id": owner_id,
        },
    )
    out = []
    for index in range(rows):
        unit = metering_services.create_unit(
            actor,
            {"premises_id": premises["id"], "label": f"BM {index}", "unit_type": "residential"},
        )
        metering_services.assign_unit_plan(actor, unit["id"], {"tariff_id": str(plan.id)})
        metering_services.ensure_service_point(unit["id"], service_code)
        out.append(unit)
    return out


def _csv(units: list[dict]) -> str:
    stamp = int(time.time() * 1000)
    lines = [HEADERS]
    for index, unit in enumerate(units, start=1):
        lines.append(
            f"{unit['unit_no']},BM{stamp}-{index},Customer {index},C{stamp}-{index},"
            f"residential,active,2024-02-12,{(index % 90) + 1}.00"
        )
    return "\n".join(lines) + "\n"


def _timed(label: str, call):
    started = time.perf_counter()
    answer = call()
    elapsed = time.perf_counter() - started
    print(f"  {label:<10} {elapsed:8.1f}s")
    return answer, elapsed


def one_pass(actor, plan, service_code: str, rows: int) -> dict[str, float]:
    print(f"\n── {rows:,} accounts ──")
    figures: dict[str, float] = {}
    key = (import_runs.TARGET_ACCOUNTS, "load")
    original = import_runs.ASYNC_ROW_BAR_BY_TARGET.get(key)
    try:
        with transaction.atomic():
            # The fixture is timed too, because it is the same per-unit work the
            # premises/units import does and it makes the two targets comparable.
            units, figures["fixture"] = _timed(
                "units", lambda: _units(actor, plan, service_code, rows)
            )
            content = _csv(units)
            run, figures["extract"] = _timed(
                "extract",
                lambda: import_runs.extract(
                    actor,
                    {
                        "target": import_runs.TARGET_ACCOUNTS,
                        "source_kind": "file",
                        "file_name": f"benchmark_{rows}.csv",
                        "content": content,
                        "session_ref": "sess_bench",
                        "write_mode": "insert",
                    },
                ),
            )
            run_id = run["id"]
            _, figures["transform"] = _timed(
                "transform",
                lambda: import_runs.transform(
                    actor,
                    run_id,
                    {
                        "mapping": MAPPING,
                        "row_handling": {key: False for key in import_runs.ROW_HANDLING_KEYS},
                        "options": {"cutover_on": "2026-08-31"},
                    },
                ),
            )
            _, figures["validate"] = _timed("validate", lambda: import_runs.validate(actor, run_id))
            _, figures["dry_run"] = _timed(
                "dry-run", lambda: import_runs.dry_run(actor, run_id, "insert")
            )
            # The bar is raised for the duration so the LOAD BODY is timed rather
            # than the deferral this measurement exists to justify.
            import_runs.ASYNC_ROW_BAR_BY_TARGET[key] = rows + 1
            receipt, figures["load"] = _timed(
                "load",
                lambda: import_runs.load(actor, run_id, {"write_mode": "insert", "approved": True}),
            )
            created = receipt["counts"]["created"]
            if created != rows:
                sys.exit(f"expected {rows} created, got {created} — measuring the wrong path")
            raise _Rollback(figures)
    except _Rollback as done:
        figures = done.figures
    finally:
        if original is None:
            import_runs.ASYNC_ROW_BAR_BY_TARGET.pop(key, None)
        else:
            import_runs.ASYNC_ROW_BAR_BY_TARGET[key] = original
    load = figures["load"]
    print(f"  {'LOAD':<10} {load:8.1f}s   ({load * 1000 / rows:.0f} ms/row)")
    headroom = GUNICORN_TIMEOUT_S / load if load else float("inf")
    verdict = "INSIDE" if load < GUNICORN_TIMEOUT_S else "OVER THE WALL — the worker is killed"
    print(f"  vs the {GUNICORN_TIMEOUT_S:.0f}s web-worker timeout: {verdict} ({headroom:.1f}x)")
    return figures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, nargs="+", default=[100, 500, 1048])
    args = parser.parse_args()

    tenant = _tenant()
    actor = _actor(tenant)
    with core_tenancy.tenant_context(tenant.id):
        plan, service_code = _world(tenant)
        print(f"tenant: {tenant.name} · plan {plan.name} · service {service_code}")
        results = {rows: one_pass(actor, plan, service_code, rows) for rows in args.rows}

    print("\n── accounts load, against the 60s web-worker timeout ──")
    print(f"  {'rows':>8} {'load':>9} {'ms/row':>9} {'headroom':>10}")
    for rows, figures in results.items():
        load = figures["load"]
        print(
            f"  {rows:>8,} {load:8.1f}s {load * 1000 / rows:8.0f}  "
            f"{GUNICORN_TIMEOUT_S / load:9.1f}x"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
