# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-BIL-8724 (high) — the owner's bill that carries an empty unit's
#           base charge was refused outright on the ruled path.
# Rule:     BR-CUS-170 (PO 2026-08-27, closing OQ-531) — a master's bill is its
#           common areas PLUS the base charge of every unit with no occupying
#           account. ❄️ worked figure: 1408 Elm, hallway $41.20 + irrigation
#           $28.40 = $69.60, plus empty Unit D's electric base $12.00 = $81.60.
# Rules:    BR-BIL-870/871 (the R1–R7 cutover; R3 + R4 switched on by default,
#           CR-057) · DEF-990 (the empty unit's base comes from ITS OWN plan,
#           as its own base-only tariff) · DEF-BIL-8470 (each service of a
#           master is resolved against the covered unit that serves it)
# Impacts:  apps/billing/resolution_switch.py · apps/billing/resolution_shadow.py
#           · apps/billing/gather.py · apps/billing/rating_seam.py
# ───────────────────────────────────────────────────────
"""DEF-BIL-8724 — the owner of 1408 Elm owes $81.60 and got no bill at all.

**WHAT WAS WRONG, MEASURED.** Through the run's own path (`prepare_run`, which
hands the gather the readings `runs.readings_for_account` collects), the owner
was refused with *"the ruled path resolves one answer per service and this bill
carries more than one tariff for electric"*. The bill carries two electric
tariffs ON PURPOSE: the hallway's (usage and base, from the owner's plan) and
Unit D's (base only, from Unit D's OWN plan — DEF-990's ruling). The chain
answers one plan, one answer per service, so it cannot price a base that
belongs to a different unit on a different plan, and it refused the whole bill.

The *"the unit has no meter for it"* sentence the triage lane saw was a second,
test-only effect: `gather_account(...)` called with no `readings` hands the
adapter no reading rows at all, the adapter builds its meters from those rows,
and so EVERY metered service — the hallway's electric first — looked meterless.
The product never gathers that way; tc3/tc4 of `test_br_cus_170_…` now hand the
gather the run's own readings.

**THE FIX.** The empty unit's base-only tariff now names its unit
(`TariffConfig.covers_unit_id`), and the ruled path leaves THAT tariff exactly
as the live path priced it — a named exclusion, logged, like a per-size line —
while the hallway's and the irrigation's tariffs are still substituted by the
chain. Nothing about an ordinary account's bill moves: no ordinary tariff ever
carries the field.
"""

from decimal import Decimal

import pytest

from apps.billing import gather, models as billing_models, resolution_shadow, runs
from apps.customers import models as customer_models

from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import tenant_ctx  # noqa: F401
from tests.test_br_cus_068_master_bill import (
    COMMON_BILL,
    PERIOD_END,
    PERIOD_START,
    SERVICE_DATE,
    _cycle,
    _priced_plan,
    _run,
    a_master,
    elm_1408,
)
from tests.test_br_cus_170_master_covers_the_unbilled import (
    ELECTRIC_BASE,
    _planned_metered_unit,
)

pytestmark = pytest.mark.django_db

OWNER_WITH_ONE_EMPTY_UNIT = Decimal("81.60")


def _world(brazos, dana, label):
    cycle = _cycle(brazos, f"MA-8724-{label}")
    plan = _priced_plan(brazos)
    premises, hallway, irrigation = elm_1408(dana, brazos, cycle, plan)
    unit_d = _planned_metered_unit(
        dana, brazos, cycle, plan, premises, label="Unit D", asset_no=f"M-8724{label}"
    )
    master = customer_models.Account.objects.get(pk=a_master(dana, premises)["id"])
    return cycle, master, unit_d


def test_def_bil_8724_tc1__the_owner_is_billed_81_60_through_the_ruled_path(brazos, dana):
    """❄️ $41.20 + $28.40 + $12.00 = **$81.60**, with R3 + R4 switched on.

    RED BEFORE THE FIX: the owner was not in `prepared.ready` at all — refused
    *"more than one tariff for electric"*.
    """
    with tenant_ctx(brazos):
        cycle, master, _unit_d = _world(brazos, dana, "1")
        prepared = runs.prepare_run(
            cycle_id=cycle.id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            service_date=SERVICE_DATE,
        )
        refused = [p for p in prepared.blocked if p.account_no == master.account_no]
        assert refused == [], refused
        owner = next(row for row in prepared.ready if row.account_no == master.account_no)

        # The ruled path DID run on this bill — it was not switched off to pass.
        assert {"R3", "R4"} <= set(owner.resolution_steps)

        invoice = runs.calculate_account(
            owner, bill_run=_run(brazos, cycle, "ma-8724-1"), service_date=SERVICE_DATE
        )
        assert invoice.total == OWNER_WITH_ONE_EMPTY_UNIT == COMMON_BILL + ELECTRIC_BASE
        # Three bases (hallway electric, irrigation water, Unit D electric) and
        # ONE electric usage line — Unit D's meter is never read.
        assert billing_models.InvoiceLine.objects.filter(invoice=invoice, kind="base").count() == 3
        assert (
            billing_models.InvoiceLine.objects.filter(
                invoice=invoice, kind="usage", service__code="electric"
            ).count()
            == 1
        )


def test_def_bil_8724_tc2__the_empty_units_tariff_names_its_unit_and_nothing_else_does(
    brazos, dana
):
    """The exclusion is keyed on the flag `gather` set, never on counting tariffs.

    Only the empty unit's base-only tariff carries `covers_unit_id`; the two
    common areas' tariffs carry None, so the chain still substitutes them, and
    two COMMON-AREA tariffs for one service (OQ-334) would still refuse.
    """
    with tenant_ctx(brazos):
        cycle, master, unit_d = _world(brazos, dana, "2")
        readings, _unmeasured = runs.readings_for_account(
            master, period_start=PERIOD_START, period_end=PERIOD_END, scope_services=None
        )
        gathered = gather.gather_account(
            account=master,
            service_date=SERVICE_DATE,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            cycle_days=(PERIOD_END - PERIOD_START).days + 1,
            readings=readings,
        )
        flagged = [(c.service, c.base_only, c.covers_unit_id) for c in gathered.tariffs]
        assert sorted(flagged, key=str) == sorted(
            [
                ("electric", False, None),
                ("water", False, None),
                ("electric", True, str(unit_d["id"])),
            ],
            key=str,
        )
        # The hallway's electric usage is still USAGE to the adapter: the empty
        # unit's base-only tariff must not mark the whole service base-only, or
        # the multiplier guard would be relaxed for the hallway's meter.
        inputs = resolution_shadow.adapt(gathered, account=master)
        assert inputs.blocked_reason is None
        assert inputs.quantities.get("electric") is not None
