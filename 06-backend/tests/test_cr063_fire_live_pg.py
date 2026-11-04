# ── Trace ──────────────────────────────────────────────
# Story:    US-TEN-019 (EP-TEN-03 — tenant sample data)   Screens: S110, S8, S62
# Change:   CR-063 task D1/D6 — a FIRE-ONLY utility is provisioned through the
#           real signup entry point and its bills are COUNTED.
# Rules:    BR-RAT-024 (the catalogue is ELEVEN; `fire` appended 2026-09-02) ·
#           BR-RAT-090 (a capacity service's quantity is a COUNT of its assets)
#           · BR-TEN-060 (a gap is NAMED, never a silent zero) ·
#           CLAUDE.md law 14 (this must be proved on PostgreSQL, not SQLite)
# Tests:    this file
# Impacts:  core/sample_fixture.CAPACITY_ESTATE_SERVICES · apps/rating/
#           sample_data (the capacity-companion payload) · apps/ledger/chart
# ───────────────────────────────────────────────────────
"""**DOES A UTILITY THAT SELLS ONLY FIRE PROTECTION GET AN ESTATE AND BILLS?**

`CR-063` exists because a real customer is being onboarded and they sell fire
lines, so this is the one measurement that answers their question directly.

WHY THIS IS A SEPARATE FILE FROM `test_service_billing_coverage.py`
--------------------------------------------------------------------
That file is the SCOREBOARD — fifteen tenants, one per catalogue service plus
the realistic combinations — and it is the right home for the permanent record.
It is also **one un-parametrised test that provisions all fifteen**, so asking it
*"does fire bill?"* costs the whole board: roughly a minute per tenant plus a
three-minute collection, and every other lane's PostgreSQL contention on top.

This file asks the ONE question, so the answer arrives in about a minute and a
lane changing anything about fire can afford to run it. **It does not replace the
scoreboard row** — `svc-fire` is recorded there with `bills_for=("fire",)` and
that is the guarantee that survives; this is the fast door to the same fact.

⚠ **IT IS MARKED `requires_postgres` AND THAT IS NOT DECORATION (CLAUDE.md law
14).** `config/settings/test.py` hardcodes in-memory SQLite, and the estate this
exercises writes rows through RLS-forced tables and a provisioning path that
catches database errors per block. A green SQLite run here would be measuring a
database that cannot express the failure. Run it with:

    DJANGO_SETTINGS_MODULE=config.settings.local \\
    DATABASE_URL="postgres://smartbillhub:smartbillhub@localhost:5432/smartbillhub" \\
    JOBS_EAGER=false pytest tests/test_cr063_fire_live_pg.py --reuse-db
"""

import pytest

from tests.isolation_helpers import requires_postgres
from tests.test_us_ten_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import brazosbend_payload, provisioned_tenant, tenant_ctx

#: ⚠ **`requires_postgres` IS APPLIED TO THE WHOLE MODULE, AND THE DOCSTRING
#: ABOVE WOULD OTHERWISE BE A COMMENT CLAIMING A GUARANTEE (hard-won law 1).**
#: `config/settings/test.py` hardcodes in-memory SQLite, so without this the file
#: would run there, pass, and report itself as the PostgreSQL proof — which is
#: law 14's trap wearing the costume of the check for it. It SKIPS on SQLite
#: rather than passing vacuously.
pytestmark = [pytest.mark.django_db, requires_postgres]


def _fire_only_tenant(settings):
    """One tenant that sells FIRE and nothing else, through the real signup.

    ⚠ **`JOBS_EAGER = True` IS LOAD-BEARING AND ITS ABSENCE COST THIS LANE A
    FALSE RED.** The sample plant is a QUEUED JOB; the suites run with
    `JOBS_EAGER=false` for speed (`DEF-567`), so without this line the tenant is
    provisioned and **no sample data is planted at all** — 0 premises, 0 units, 0
    bills, and **not one failing block**, because nothing ran to fail. That reads
    exactly like the defect this file was written to catch and is not it.
    `test_service_billing_coverage.py` sets the same flag with the same comment:
    *the plant runs inline, as it does on a real signup*.

    The lesson is the one hard-won law 1 states — a red is not evidence until you
    know what produced it — and the cheap tell is the one that caught it here: a
    tenant with zero rows AND zero failing blocks has not been seeded, whereas a
    tenant that was seeded and broke has a SENTENCE saying so (`BR-TEN-060`).
    """
    settings.JOBS_EAGER = True
    return provisioned_tenant(
        brazosbend_payload(
            subdomain="svc-fire-live",
            name="Brazos Fire Protection",
            services=["fire"],
            owner={
                "full_name": "Ruth Alvarez",
                "email": "ruth@svc-fire-live.example.invalid",
                "password": "S3cure!passw0rd",
                "phone": None,
            },
        )
    )


def test_cr063_d1__a_fire_only_utility_gets_an_estate_and_issues_bills(
    growth_plan, audit_rows, settings
):
    """**THE GOING-LIVE CUSTOMER'S OWN SHAPE, COUNTED.**

    A fire-only tenant has NO metered service at all — no register, no reading —
    so every count here is the capacity path working end to end: premises and
    units exist, a service point carries fire, a plan prices it, and invoices
    reach `issued`.

    ⚠ **WHAT THIS DOES NOT CLAIM, AND IT MATTERS FOR THE CUSTOMER.** The LINE is
    on the document; this test is about the line and not about its amount. **A
    `$0.00` line on a real bill and NO line at all are different facts**, and
    this test is about the second one.

    ⚠ **AND THE REASON THE SEEDED AMOUNT IS `$0.00` CHANGED ON 2026-09-02, SO
    THE OLD SENTENCE IS REPLACED RATHER THAN LEFT TO ROT.** It read *"the seeded
    capacity schedule prices at `0` like every other capacity companion
    (`CAPACITY_UNPRICED`) … `CR-063` task C3 is the work that would make it
    `$12.00`"*. **Both halves are now false.** `CAPACITY_UNPRICED` was retired
    with `CR-062` D8, and **C3 has landed**: fire's seeded schedule prices per
    size — a 2" line at `$12.00`, a 6" line at `$60.00` — and
    `tests/test_cr063_c3_fire_priced.py` proves `$12.00`, `$60.00` and `$84.00`
    on real bills through this same live run.

    ⚠ **A PRIVATE HYDRANT AT `$25.00` WAS THE THIRD SEEDED PRICE AND THE PO
    REMOVED IT ON 2026-09-03** (*"remove private hydrants from list"*), which
    also moved the warehouse figure that file proves from `$110.00` to `$60.00`
    — `−$50.00` a month on that customer. The six line diameters and their
    prices did not move.

    **What is still `$0.00` here, and why:** the seeded ESTATE plants no fire
    EQUIPMENT, so every unit has a fire connection with nothing standing on it.
    That is `BR-MET-108`'s ruled zero — the utility looked and there is nothing
    — and the count of zero multiplies whatever the price is. The estate half is
    `CR-063` task C5, blocked on `OQ-1361`: `BR-AST-042` ratifies twelve asset
    types and none of them is a fire service line. ⚠ **`OQ-1361` IS HALF ANSWERED
    SINCE 2026-09-03 AND THE HALF THAT BLOCKS THIS IS THE HALF STILL OPEN** — the
    PO ruled a hydrant is an asset and removed it from fire's size list, which
    settles what a HYDRANT is and says nothing about what a fire LINE is called.
    """
    from apps.billing import models as billing_models
    from apps.metering import models as metering_models
    from apps.tenancy import models as tenancy_models

    tenant, _result = _fire_only_tenant(settings)
    with tenant_ctx(tenant):
        units = metering_models.Unit.objects.filter(tenant_id=tenant.id).count()
        points = metering_models.ServicePoint.objects.filter(
            tenant_id=tenant.id, service__code="fire"
        ).count()
        issued = billing_models.Invoice.objects.filter(
            tenant_id=tenant.id, status="issued"
        ).count()
        # The seeding blocks are read from `SampleDataRun`, which is where the
        # scoreboard reads them — NOT off the provisioning result, whose shape
        # this file must not guess at.
        blocks = [
            dict(block, module=block.get("module") or row.module)
            for row in tenancy_models.SampleDataRun.objects.filter(tenant_id=tenant.id)
            for block in (row.blocks or [])
        ]

    # BR-TEN-060 — a seeding block that could not run must have SAID why. A
    # silent zero is the thing that rule exists to prevent, so this asserts the
    # SENTENCE and deliberately does not require the block to have succeeded:
    # a fire tenant has no money to refund and no reads to take, and those
    # blocks failing is correct.
    for block in blocks:
        if block.get("outcome") != "seeded":
            assert block.get("detail"), (
                f"{block.get('block')} did not seed and gave NO reason — BR-TEN-060. "
                "A gap is named, never a silent zero."
            )

    assert units > 0, (
        "a fire-only tenant got NO units. `fire` is in CAPACITY_ESTATE_SERVICES, so "
        "`estate_plan` must shape an estate with no backbone at all — the shape a "
        "trash-only tenant has had since DEF-2414.\n"
        f"There are {len(blocks)} seeding block(s) recorded. ZERO blocks means the "
        "plant never RAN (check JOBS_EAGER) and this is not a fire defect at all; "
        "blocks WITH failures means it ran and refused, and each carries the "
        "sentence saying why (BR-TEN-060). The two zeros look identical in a count "
        "and mean opposite things."
    )
    assert points > 0, (
        "the estate exists and NO unit carries a fire service point, so BR-RAT-090 has "
        "nothing to count and every bill would refuse asset_count_unavailable"
    )
    assert issued > 0, (
        f"a fire utility issued NO bills ({units} units, {points} fire service points). "
        "That is DEF-2414's exact shape one service along, and it is what CR-063 was "
        "raised to prevent for the customer going live"
    )


def test_cr063_d1__the_fire_line_is_ON_the_bill_and_not_merely_beside_it(
    growth_plan, audit_rows, settings
):
    """**`DEF-3224`'S LESSON, APPLIED ON THE DAY THE SERVICE ARRIVED.**

    A count of invoices cannot see a MISSING SERVICE on those invoices: a tenant
    that issues 96 bills carrying nothing for fire scores as a pass on every
    figure in the case above. That is not hypothetical — it put `$576.00 a month`
    of electric off the bills of a tenant where every count was green.

    So this asserts the LINE, by service code, on a bill that actually issued.
    """
    from apps.billing import models as billing_models

    tenant, _ = _fire_only_tenant(settings)
    with tenant_ctx(tenant):
        services_on_bills = set(
            billing_models.InvoiceLine.objects.filter(
                tenant=tenant, invoice__status="issued"
            )
            .exclude(service__isnull=True)
            .values_list("service__code", flat=True)
            .distinct()
        )

    assert "fire" in services_on_bills, (
        "no issued bill carries a FIRE line. The tenant sells exactly one service, so "
        "a bill without it is a bill about nothing — and a count of invoices cannot "
        f"see this (DEF-3224). Services actually billed: {sorted(services_on_bills)}"
    )
