# ── Trace ──────────────────────────────────────────────
# Rules:    BR-RAT-088 (PO ruling 2026-08-20, closing B1/OQ-238 — the CHARGE
#           CODE owns the base) · §A3 · DEF-277 (blank ≠ 0.00) · DEF-359
# ───────────────────────────────────────────────────────
"""The flip, proved through `resolve()` — not through the helper it calls.

⚠ **THIS FILE EXISTS BECAUSE MY FIRST ATTEMPT AT IT WAS WORTHLESS.** I wrote five
tests named `..._flip__...` that asserted `resolve_base_charge` picks the right
row, then reverted the flip to prove they went RED (hard-won law 7). **All five
still passed.** They exercised the pure helper, which the revert did not touch —
a check whose output cannot distinguish pass from fail, which CLAUDE.md says is
worse than no check because it is trusted.

The claim §A3 actually rules on is not "the helper works". It is **"the chain
asks it"**. That can only be tested through `resolve()`, with a catalogue that
holds a base charge code whose figure DIFFERS from the schedule's — so a passing
test cannot be a coincidence of two equal numbers.
"""

from decimal import Decimal

import pytest

from apps.rating import resolution as R

from datetime import date

SERVICE_DATE = date(2026, 7, 31)

#: The schedule says $12.00 at 5/8". The charge code says $14.00. They differ ON
#: PURPOSE: with equal figures every assertion below passes whichever object
#: answered, which is exactly the bug §A3 warns about — "both rows are
#: individually correct and only the rule makes the total wrong".
SCHEDULE_BASE = Decimal("12.00")
CODE_BASE = Decimal("14.00")

SCHEDULE = R.ScheduleVersion(
    version_id="TV-W-1",
    service="water",
    tariff_id="SCH-W",            # the plan binds the TARIFF; R2 finds its version
    effective_from=date(2026, 1, 1),
    size_rows={'5/8"': SCHEDULE_BASE},
)
PLAN = R.PlanVersion(
    plan_id="P-1",
    version=1,
    services=("water",),
    effective_from=date(2026, 1, 1),
    schedules={"water": "SCH-W"},
)


def _catalogue(*, with_base_code: bool) -> R.Catalogue:
    codes = ()
    if with_base_code:
        codes = (
            R.ChargeCode(
                code="BASE-W", service="water", is_base=True, flat_amount=CODE_BASE
            ),
        )
    return R.Catalogue(
        plan_versions=(PLAN,),
        # `DEF-RAT-9832` (PO 2026-10-06): the schedule NAMES the code it means;
        # an unnamed schedule takes no code from the list.
        schedule_versions=(R.replace(SCHEDULE, base_charge_code="BASE-W") if with_base_code else SCHEDULE,),
        charge_codes=codes,
        taxes=(),
        outside_city_factor=Decimal("1"),
    )


def _resolve(*, with_base_code: bool) -> R.Resolution:
    return R.resolve(
        catalogue=_catalogue(with_base_code=with_base_code),
        account=R.AccountFacts(account_no="A-1", unit_id="U-1", customer_class="residential"),
        premises=R.PremisesFacts(inside_city_limits=True, county="Bexar"),
        meters=(R.MeterFacts(service="water", connection_size='5/8"'),),
        quantities={"water": Decimal("11")},
        service_date=SERVICE_DATE,
    )


def test_the_chain_prices_the_base_from_the_CHARGE_CODE():
    """B1's ruling, end to end. Reverting the flip turns this RED — verified."""
    water = _resolve(with_base_code=True).services[0]
    assert water.base_charge == CODE_BASE
    assert water.base_source == "named_charge_code"  # DEF-RAT-9832: named, never inferred


def test_the_chain_falls_back_to_the_SCHEDULE_for_a_tenant_that_has_not_moved():
    """`Charge.is_base` defaults False. Refusing here would stop every bill for
    every existing tenant the day this shipped; billing no base would be worse.
    The fallback is the migration path, and it RECORDS itself."""
    water = _resolve(with_base_code=False).services[0]
    assert water.base_charge == SCHEDULE_BASE
    assert water.base_source == "schedule"


def test_the_two_paths_produce_DIFFERENT_money__so_the_test_can_fail():
    """The guard on the guard. If these ever became equal, both tests above
    would pass no matter which object answered."""
    assert CODE_BASE != SCHEDULE_BASE


def test_R3_still_refuses_an_unserved_size_after_the_flip():
    """The flip moved the PRICE, not the GATE. Moving the base must not quietly
    delete a refusal — DEF-277's *"blank base = size not served"* still stops
    the bill, and so does a size the schedule never priced."""
    with pytest.raises(R.SizeNotServed):
        R.resolve(
            catalogue=_catalogue(with_base_code=True),
            account=R.AccountFacts(account_no="A-1", unit_id="U-1", customer_class="residential"),
            premises=R.PremisesFacts(inside_city_limits=True, county="Bexar"),
            meters=(R.MeterFacts(service="water", connection_size='2"'),),
            quantities={"water": Decimal("11")},
            service_date=SERVICE_DATE,
        )
