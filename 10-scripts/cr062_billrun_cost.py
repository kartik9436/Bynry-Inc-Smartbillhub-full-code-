#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Change:  CR-062 group C task H11 — *"Bill-run cost is re-measured after the
#          estate multiplies. Three metered services means three times the
#          readings; the run was just changed to stream accounts 500 at a time
#          rather than load them all, so this is a MEASUREMENT, not an expected
#          failure."*
# Rules:   CLAUDE.md law 14 (a transaction-shaped path is proved on real
#          PostgreSQL, never on the in-memory SQLite suite) · law 1 (a comment
#          claiming a guarantee is not the guarantee — this prints figures)
# ───────────────────────────────────────────────────────
"""**WHAT DOES A SECOND METERED SERVICE COST THE BILL RUN?** Measured, printed.

WHY IT IS MEASURED THIS WAY AND NOT AS "BEFORE THE COMMIT / AFTER THE COMMIT"
-----------------------------------------------------------------------------
The change is to the SEED, not to the engine: `gather` has always built one
tariff per plan service row and `metering.billing_reads_for_unit` has always
returned one row per service point. So "before" and "after" on the same tenant
shape would differ only in how much data the seeder planted — and the honest
question is exactly that: **what does one more register per unit cost when the
run bills it?**

So this provisions two real tenants through the real signup service, on ONE
build, and times the June bill-run block on each:

  * `water + sewer`             — one metered service. This is precisely what
    the PO's `electric + water + sewer` tenant used to receive, because electric
    was refused as a second register.
  * `electric + water + sewer`  — two metered services, which is what the same
    signup receives now.

The DIFFERENCE between those two numbers is the cost of the change, on the same
code, with nothing else varying.

WHAT IS TIMED
-------------
`apps.billing.sample_data.seed_sample_records` — the block that creates the run,
prepares it, applies the fixture's decisions, calculates, passes the release
gate and issues. That is the whole of what a person means by "the bill run", and
it is the block the PO presses on the Sample data panel.

The seeding that precedes it is timed too and printed beside it, because a
lane reading only the bill-run figure would miss that the estate itself takes
longer to plant — which is the cost that actually doubles.

USAGE (real PostgreSQL 16 — law 14)

    DJANGO_SETTINGS_MODULE=config.settings.local \\
    DATABASE_URL="postgres://smartbillhub:smartbillhub@localhost:5432/smartbillhub" \\
    .venv/bin/python 10-scripts/cr062_billrun_cost.py

It writes two throwaway tenants into the configured database and leaves them
there — they are named `cr062cost-<random>` so they are easy to find and drop.
"""

from __future__ import annotations

import os
import sys
import time
import uuid
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
from apps.metering import models as metering_models  # noqa: E402
from apps.tenancy import sample_data as tenancy_sample  # noqa: E402
from apps.tenancy import services as tenancy_services  # noqa: E402
from core import tenancy as core_tenancy  # noqa: E402

#: The two shapes, and the pair IS the measurement — see the module docstring.
SHAPES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("one metered service   (water + sewer)", ("water", "sewer")),
    ("two metered services  (electric + water + sewer)", ("electric", "water", "sewer")),
)


def _payload(subdomain: str, services: tuple[str, ...]) -> dict:
    return {
        "subdomain": subdomain,
        "name": f"CR-062 cost {subdomain}",
        "services": list(services),
        "plan": "growth",
        "owner": {
            "full_name": "Dana Whitfield",
            "email": f"dana@{subdomain}.example.invalid",
            "password": "S3cure!passw0rd",
            "phone": None,
        },
    }


def _actor(owner_user_id) -> SimpleNamespace:
    """The provisioning OWNER, never an invented uuid — `DEF-2722`.

    `tenancy.sample_data._attributed` strips an actor it cannot resolve, and
    `BR-BIL-058`'s release gate then refuses to issue anything at all, so the
    bill-run block would be timed doing nothing.
    """
    return SimpleNamespace(
        id=uuid.UUID(str(owner_user_id)),
        pk=uuid.UUID(str(owner_user_id)),
        role="system_admin",
        roles=("system_admin",),
        is_authenticated=True,
    )


#: Filled by the wrapper below, keyed by the tenant's subdomain, so the bill-run
#: block is timed WHERE THE PLANT RUNS IT rather than by a second call that a
#: replay would make free (BR-TEN-063).
BILL_RUN_SECONDS: dict[str, float] = {}
#: ⚠ **PATCHED ON `apps.billing.services`, NOT ON `apps.billing.sample_data`.**
#: `tenancy.seams.resolve` imports `apps.<module>.services` and getattrs the
#: name at call time, so wrapping the sample_data function would time nothing —
#: the seam would go on calling the unwrapped one and every figure would be
#: `n/a`, silently. That is hard-won law 2 in a measurement script.
_ORIGINAL_BILLING_SEAM = billing_services.seed_sample_records
_CURRENT_SUBDOMAIN: list[str] = []


def _timed_billing(actor):
    started = time.perf_counter()
    try:
        return _ORIGINAL_BILLING_SEAM(actor)
    finally:
        if _CURRENT_SUBDOMAIN:
            BILL_RUN_SECONDS[_CURRENT_SUBDOMAIN[-1]] = time.perf_counter() - started


def main() -> int:
    billing_services.seed_sample_records = _timed_billing
    rows = []
    for label, services in SHAPES:
        subdomain = f"cr062cost-{uuid.uuid4().hex[:8]}"
        _CURRENT_SUBDOMAIN.append(subdomain)
        result = tenancy_services.provision_tenant(_payload(subdomain, services))
        tenant_id = result["id"]
        actor = _actor(result["owner_user_id"])
        core_tenancy.set_current_tenant(tenant_id)
        try:
            started = time.perf_counter()
            tenancy_sample.seed_sample_data(actor)
            plant_seconds = time.perf_counter() - started
            reads = metering_models.MeterRead.objects.filter(tenant_id=tenant_id).count()
            issued = billing_models.Invoice.objects.filter(
                tenant_id=tenant_id, status="issued"
            ).count()
            lines = billing_models.InvoiceLine.objects.filter(
                tenant_id=tenant_id, invoice__status="issued"
            ).count()
            on_bills = sorted(
                str(code)
                for code in billing_models.InvoiceLine.objects.filter(
                    tenant_id=tenant_id, invoice__status="issued"
                )
                .values_list("service__code", flat=True)
                .distinct()
                if code
            )
        finally:
            core_tenancy.clear_current_tenant()
        rows.append(
            {
                "label": label,
                "plant": plant_seconds,
                "bill_run": BILL_RUN_SECONDS.get(subdomain),
                "reads": reads,
                "issued": issued,
                "lines": lines,
                "on_bills": on_bills,
            }
        )

    print("\n── CR-062 H11 · what a second metered service costs the bill run ──")
    print(f"{'shape':52}{'plant s':>10}{'bill run s':>12}{'reads':>8}{'issued':>8}{'lines':>8}  services on the bills")
    for row in rows:
        bill_run = "n/a" if row["bill_run"] is None else f"{row['bill_run']:.1f}"
        print(
            f"{row['label']:52}{row['plant']:>10.1f}{bill_run:>12}"
            f"{row['reads']:>8}{row['issued']:>8}{row['lines']:>8}  {','.join(row['on_bills'])}"
        )
    if len(rows) == 2 and rows[0]["bill_run"] and rows[1]["bill_run"]:
        delta = rows[1]["bill_run"] - rows[0]["bill_run"]
        factor = rows[1]["bill_run"] / rows[0]["bill_run"]
        print(
            f"\nthe second register costs {delta:+.1f}s on the bill run "
            f"({factor:.2f}x), and {rows[1]['plant'] - rows[0]['plant']:+.1f}s on the "
            "whole plant. One run of one shape on one build — a measurement, not a "
            "guarantee (hard-won law 1)."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
