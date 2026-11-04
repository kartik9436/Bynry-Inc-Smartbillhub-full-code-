# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-BIL-9252 — a master account over a build with a common area could
#          not take its first bill: the unplanned common area (PO 2026-09-21,
#          "common area dont need rate plan as of now; make this optional") was
#          the master's anchor, so the gather read its plan — none — and refused
#          the WHOLE owner's bill with unit_has_no_plan.
# Rules:   PO 2026-09-21 ruling 1 (decision log) · DEF-CUS-5496 (2026-09-16) ·
#          BR-CUS-170 (the empty homes' base charges are the owner's) ·
#          DEF-CUS-9050 (PO 2026-10-02, option A — a master with no common area
#          borrows its first planned empty home as anchor)
# Tests:   this file — run on PostgreSQL (`--ds=config.settings.pgtest`)
# Impacts: apps/billing/gather.py · apps/customers/selectors.py
# ───────────────────────────────────────────────────────
"""The unplanned common area contributes nothing, and blocks nothing.

The walk's S1 shape (`AC-2026-00064`): homes on a plan that nobody occupies yet,
plus a METERED common area the PO ruled needs no plan. Before: the owner's
first bill refused `unit_has_no_plan`. After, worked on a $8.00 water base: two
empty homes → the owner is billed `2 × $8.00 = $16.00`, and NOTHING of the
common area — no base, no usage — which is the ruling's own precondition,
*an unplanned unit can never be billed*, held on the unit rather than on the
whole account.

⚠ **WHAT WOULD MAKE THIS PASS WRONGLY:** a common area the master does not
cover at all (then nothing was ever in its way), or one that carries a plan. So
both are asserted BEFORE the bill: it is covered by the master's agreements,
and it is unplanned.
"""

from decimal import Decimal

import pytest

from apps.billing import gather as billing_gather
from apps.billing import models as billing_models
from apps.customers import selectors as customer_selectors
from apps.customers import services as customer_services
from apps.metering import models as metering_models

from tests.test_def_cus_9050_empty_unit_base_to_master import (
    WATER_BASE,
    _bill,
    _cycle,
    _home,
    _master,
    _water_plan,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import make_premises, make_unit, tenant_ctx  # noqa: F401
from tests.test_us_met_reads_helpers import a_meter

pytestmark = pytest.mark.django_db

CENT = Decimal("0.01")


def _s1_build(actor, tenant, code):
    cycle = _cycle(tenant, code)
    plan = _water_plan(tenant)
    premises = make_premises(
        actor,
        address_line=f"{code} Commons Way",
        premises_type="apartment_complex",
        owner_manager="Ridge Property LLC",
        services_available=["water"],
    )
    for n in (1, 2):
        _home(actor, tenant, cycle, plan, premises, label=f"Unit {n}", asset_no=f"W-{code}-{n}")
    common = make_unit(
        actor,
        premises["id"],
        label="Common area",
        unit_type="common_area",
        is_common_area=True,
        services=["water"],
    )
    a_meter(actor, asset_no=f"W-{code}-CA", unit_id=common["id"], service="water", uom="kgal")
    metering_models.ServicePoint.objects.filter(tenant=tenant, unit_id=common["id"]).update(
        cycle=cycle
    )
    master = _master(actor, premises)
    row = metering_models.Unit.objects.get(pk=common["id"])
    assert row.rate_plan_id is None, "the common area is genuinely unplanned"
    assert str(row.id) in [str(u) for u in customer_selectors.covered_unit_ids(master)], (
        "the master covers the common area — else nothing was ever in its way"
    )
    return cycle, master, row


def test_def_bil_9252_tc1__the_owners_first_bill_is_not_blocked_by_the_common_area(brazos, dana):
    with tenant_ctx(brazos):
        cycle, master, common = _s1_build(dana, brazos, "CA1")

        assert str(common.id) not in billing_gather.covered_units(master)
        invoice = _bill(brazos, cycle, master, "def-bil-9252-tc1")

        lines = list(billing_models.InvoiceLine.objects.filter(invoice=invoice))
        bases = sorted(
            (line.description, line.amount.quantize(CENT)) for line in lines if line.kind == "base"
        )
        print("\nPROOF DEF-BIL-9252 owner's lines:", [(l.kind, l.description, l.amount) for l in lines])
        assert [amount for _text, amount in bases] == [WATER_BASE, WATER_BASE]
        assert all("Common area" not in (line.description or "") for line in lines)
        assert not [line for line in lines if line.kind == "usage"], "no common-area usage"


def test_def_bil_9252_tc2__the_constant_still_decides(brazos, dana, monkeypatch):
    """`COMMON_AREA_REQUIRES_A_PLAN` is the PO's *"as of now"*; set it back and the
    owner's bill refuses again, by name, exactly as before the ruling."""
    with tenant_ctx(brazos):
        cycle, master, common = _s1_build(dana, brazos, "CA2")
        monkeypatch.setattr(customer_services, "COMMON_AREA_REQUIRES_A_PLAN", True)

        assert str(common.id) in billing_gather.covered_units(master)
        with pytest.raises(billing_gather.GatherProblem) as caught:
            billing_gather.gather_account(
                account=master,
                service_date=cycle_end(),
                period_start=cycle_start(),
                period_end=cycle_end(),
                cycle_days=30,
            )
        assert caught.value.reason == billing_gather.GATHER_NO_PLAN


def cycle_start():
    from tests.test_def_cus_9050_empty_unit_base_to_master import START

    return START


def cycle_end():
    from tests.test_def_cus_9050_empty_unit_base_to_master import END

    return END
