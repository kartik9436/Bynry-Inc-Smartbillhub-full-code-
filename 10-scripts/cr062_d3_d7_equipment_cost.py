#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Change:  CR-062 tasks D3–D7 — plant the billable capacity equipment. The
#          estate lane measured what a second METER costs the bill run and kept
#          `10-scripts/cr062_billrun_cost.py` so anyone can re-run it; this is
#          the same measurement for what the EQUIPMENT costs.
# Rules:   CLAUDE.md law 14 (a transaction-shaped path is proved on real
#          PostgreSQL, never on the in-memory SQLite suite) · law 1 (a comment
#          claiming a guarantee is not the guarantee — this prints figures)
# ───────────────────────────────────────────────────────
"""**WHAT DOES PLANTING NINE PIECES OF CAPACITY EQUIPMENT COST?** Measured.

WHY IT IS MEASURED AGAINST ITSELF AND NOT AGAINST A SMALLER TENANT
------------------------------------------------------------------
The obvious comparison — a `water + sewer` tenant against a
`water + sewer + solar + battery + broadband` one — would measure THREE EXTRA
SERVICES, not the equipment: more plans, more schedules, more service points and
three more lines on every bill. The number would be real and would answer a
different question.

So both runs here provision the SAME five-service utility on the SAME build, and
the only difference is whether `core.sample_fixture.capacity_equipment_plan()`
returns its nine rows or an empty tuple. The DIFFERENCE between the two figures
is the cost of D3–D7 and of nothing else.

WHAT IS TIMED, AND WHY IT IS `provision_tenant` AND NOT `seed_sample_data`
--------------------------------------------------------------------------
⚠ **THE OBVIOUS THING TO TIME MEASURES A REPLAY AND PRINTS A CONFIDENT `2.9s`.**
`provision_tenant` ENQUEUES the plant job (CR-010 mandate 1, PO 2026-08-17), and
under the local settings `JOBS_EAGER` defaults to true, so the whole estate is
planted INSIDE `provision_tenant`. A later call to `seed_sample_data` is then an
idempotent no-op (`BR-TEN-063`) and times at a couple of seconds — while the
process log shows two minutes of per-account bill runs going past. Measured
before this was noticed: `plant 2.9s / bill run 0.1s` for a tenant that had
issued **95 invoices and 1,062 lines**. A number that arrives fast and looks
plausible is the worst kind of wrong, so the wall clock now covers
`provision_tenant` — where the work actually happens — and the replay is timed
separately and LABELLED as a replay rather than dropped.

The bill-run block is timed with the same wrapper trick and for the same reason
as `cr062_billrun_cost.py`: it is patched on `apps.billing.services` because
`tenancy.seams.resolve` getattrs the name off that module at call time, so
wrapping `apps.billing.sample_data` would time nothing and print `n/a` silently
— hard-won law 2 inside a measurement script.

It also prints what each shape BILLS for the four capacity services, because a
timing that got faster by planting nothing would otherwise look like good news.

USAGE (real PostgreSQL 16 — law 14)

    DJANGO_SETTINGS_MODULE=config.settings.local \\
    DATABASE_URL="postgres://smartbillhub:smartbillhub@localhost:5432/smartbillhub" \\
    .venv/bin/python 10-scripts/cr062_d3_d7_equipment_cost.py

It writes two throwaway tenants into the configured database and leaves them
there — named `cr062equip-<random>` so they are easy to find and drop.
"""

from __future__ import annotations

import os
import sys
import time
import uuid
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "06-backend"
sys.path.insert(0, str(BACKEND))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

import django  # noqa: E402

django.setup()

from apps.billing import models as billing_models  # noqa: E402
from apps.billing import services as billing_services  # noqa: E402
from apps.tenancy import sample_data as tenancy_sample  # noqa: E402
from apps.tenancy import services as tenancy_services  # noqa: E402
from core import sample_fixture as fixture  # noqa: E402
from core import tenancy as core_tenancy  # noqa: E402

#: One shape, two builds of it. The pair IS the measurement.
SERVICES: tuple[str, ...] = ("water", "sewer", "solar", "battery", "broadband")
CAPACITY_CODES: tuple[str, ...] = ("solar", "battery", "broadband")

_REAL_PLAN = fixture.capacity_equipment_plan


def _payload(subdomain: str) -> dict:
    return {
        "subdomain": subdomain,
        "name": f"CR-062 D3-D7 cost {subdomain}",
        "services": list(SERVICES),
        "plan": "growth",
        "owner": {
            "full_name": "Dana Whitfield",
            "email": f"dana@{subdomain}.example.invalid",
            "password": "S3cure!passw0rd",
            "phone": None,
        },
    }


def _actor(owner_user_id) -> SimpleNamespace:
    """The provisioning OWNER, never an invented uuid — `DEF-2722`: an actor
    `tenancy.sample_data._attributed` cannot resolve is stripped, `BR-BIL-058`'s
    release gate then issues nothing, and the bill-run block is timed doing
    nothing at all."""
    return SimpleNamespace(
        id=uuid.UUID(str(owner_user_id)),
        pk=uuid.UUID(str(owner_user_id)),
        role="system_admin",
        roles=("system_admin",),
        is_authenticated=True,
    )


BILL_RUN_SECONDS: dict[str, float] = {}
_ORIGINAL_BILLING_SEAM = billing_services.seed_sample_records
_CURRENT_SUBDOMAIN: list[str] = []


def _timed_billing(actor):
    started = time.perf_counter()
    try:
        return _ORIGINAL_BILLING_SEAM(actor)
    finally:
        if _CURRENT_SUBDOMAIN:
            BILL_RUN_SECONDS[_CURRENT_SUBDOMAIN[-1]] = time.perf_counter() - started


def _run(label: str, with_equipment: bool) -> dict:
    fixture.capacity_equipment_plan = _REAL_PLAN if with_equipment else (lambda: ())
    subdomain = f"cr062equip-{uuid.uuid4().hex[:8]}"
    _CURRENT_SUBDOMAIN.append(subdomain)
    # THE REAL WORK IS IN HERE — see the module docstring. The plant job is
    # enqueued by provisioning and runs inline under JOBS_EAGER.
    started = time.perf_counter()
    result = tenancy_services.provision_tenant(_payload(subdomain))
    plant_seconds = time.perf_counter() - started
    tenant_id = result["id"]
    actor = _actor(result["owner_user_id"])
    core_tenancy.set_current_tenant(tenant_id)
    try:
        started = time.perf_counter()
        tenancy_sample.seed_sample_data(actor)
        replay_seconds = time.perf_counter() - started
        billed: dict[str, Decimal] = {}
        for line in billing_models.InvoiceLine.objects.filter(
            tenant_id=tenant_id, invoice__status="issued"
        ).select_related("service"):
            if line.service_id is None:
                continue
            code = line.service.code
            if code in CAPACITY_CODES:
                billed[code] = billed.get(code, Decimal("0")) + line.amount
        issued = billing_models.Invoice.objects.filter(
            tenant_id=tenant_id, status="issued"
        ).count()
        lines = billing_models.InvoiceLine.objects.filter(
            tenant_id=tenant_id, invoice__status="issued"
        ).count()
    finally:
        core_tenancy.clear_current_tenant()
    return {
        "label": label,
        "plant": plant_seconds,
        "replay": replay_seconds,
        "bill_run": BILL_RUN_SECONDS.get(subdomain),
        "issued": issued,
        "lines": lines,
        "billed": billed,
    }


def main() -> int:
    billing_services.seed_sample_records = _timed_billing
    rows = [
        _run("no capacity equipment (the tip)", with_equipment=False),
        _run("nine pieces planted   (D3-D7)", with_equipment=True),
    ]
    fixture.capacity_equipment_plan = _REAL_PLAN

    print("\n── CR-062 D3-D7 · what planting the capacity equipment costs ──")
    header = (
        f"{'build':36}{'plant s':>10}{'replay s':>10}{'bill run s':>12}"
        f"{'issued':>8}{'lines':>8}  capacity billed"
    )
    print(header)
    for row in rows:
        bill_run = "n/a" if row["bill_run"] is None else f"{row['bill_run']:.1f}"
        billed = ", ".join(f"{k} ${v}" for k, v in sorted(row["billed"].items())) or "nothing"
        print(
            f"{row['label']:36}{row['plant']:>10.1f}{row['replay']:>10.1f}{bill_run:>12}"
            f"{row['issued']:>8}{row['lines']:>8}  {billed}"
        )
    before, after = rows
    delta = after["plant"] - before["plant"]
    factor = after["plant"] / before["plant"] if before["plant"] else float("nan")
    print(
        f"\nthe equipment costs {delta:+.1f}s on the plant ({factor:.2f}x) for "
        f"{after['lines'] - before['lines']:+d} invoice line(s) — the nine pieces "
        "change the AMOUNT on lines the bill already carried rather than adding "
        "any. One run of one shape on one build — a measurement, not a guarantee "
        "(hard-won law 1)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
