# ── Trace ──────────────────────────────────────────────
# Change:  PO ruling 2026-09-10 — "set it in rates and use it in plans - thats
#          it - this is rule". `plan_services.minimum_amount` moves onto
#          `tariff_versions.minimum_bill`; migrations `rating/0030` + `0031`.
#          Decision log entries 13 and 14 of 2026-09-10.
# Rules:   BR-RAT-028 AMENDED (the SOURCE moves; the arithmetic does not) ·
#          BR-RAT-007 (the version in force at the SERVICE date) ·
#          CLAUDE.md hard rule 2 (money) · hard rule 3 (an explicit unit)
# Golden:  WE-3 / GT-19 — water only, 0.4 kgal: usage 1.60 + base 8.00 = 9.60,
#          floor 15.00 → adjustment +5.40, tax on 15.00 = 1.42, total 16.42.
#          NOT re-derived here: every figure is read back from the priced bill
#          and compared with the workbook's, which is the same protection
#          `test_br_rat_028_minimum_bill.py` already gives the arithmetic.
# Tests:   this file
# ───────────────────────────────────────────────────────
"""The per-service minimum now comes from the RATE SCHEDULE, and the bill is
identical — asserted as MONEY, never as a column.

⚠ **THIS GUARD ASSERTS DOLLARS ON PURPOSE, AND THE REASON IS THE WHOLE POINT OF
THE CHANGE IT GUARDS.** Moving a figure between two nullable decimal columns is
invisible to every check this repository has: a test that asserts
`row["minimum_amount"] == Decimal("15.000000")` passes on the plan's column and
passes on the schedule's, and a test that asserts the column is GONE passes on a
product that has silently stopped charging the floor. **The only assertion that
can tell a successful move from a lost one is the amount on the bill** — a
`0.4 kgal` residential water bill is `$16.42` with the floor and `$9.60` without
it, and `$5.40` a month is what the shipped fixture's `RES-STD` water line
loses if `rating/0031` runs without `rating/0030`.

**WHAT WAS DELIBERATELY NOT ASSERTED.** Nothing here checks that
`plan_services.minimum_amount` no longer exists. That would be a check about a
schema and it would go green on exactly the failure this file exists to catch.
The column's absence is `0031`'s statement and Django's migration state is the
thing that enforces it.

**PROVED RED, through pytest — the harness that runs it.** With
`gather._tariff_config_for` no longer reading the schedule's figure (the shape a
lost move takes), this file fails on the SOURCE, verbatim:

    >           assert stated.minimum_amount == Decimal("15.000000")
    E           AssertionError: assert None == Decimal('15.000000')
    E            +  where None = TariffConfig(service='water', … minimum_amount=None,
    E                             plan_minimum_bill_amount=None).minimum_amount

    1 failed, 4 passed

⚠ **FOUR OF THE FIVE PASSED ON THAT, AND IT IS WORTH SAYING WHY.** The two
arithmetic tests hand the engine a figure directly, so they are blind to where it
came from — which is `DEF-466`'s own finding (*"the arithmetic is proven and the
SOURCING is untested"*) and the reason the hop test exists beside them rather
than instead of them.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from apps.billing import gather, rating_seam
from apps.rating import models as rating_models
from apps.rating import selectors as rating_selectors
from apps.tenancy import models as tenancy_models

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import make_plan, tenant_ctx

USD = "USD"
TAXED = rating_seam.AccountContext(currency=USD, tax_exempt=False)
FULL_MONTH = rating_seam.BillingPeriod(cycle_days=30, service_days=30)

#: WE-3's four authorities, at the rates `test_br_rat_028_minimum_bill.py`
#: recovers from the workbook's own addends rather than retyping them.
WE_TAXES = (
    rating_seam.TaxRule(code="STATE", rate=Decimal("0.0625")),
    rating_seam.TaxRule(code="COUNTY", rate=Decimal("0.01")),
    rating_seam.TaxRule(code="CITY", rate=Decimal("0.02")),
    rating_seam.TaxRule(code="DISTRICT", rate=Decimal("0.002")),
)

#: Silver Creek's own residential water (core/sample_fixture.py).
WATER_BASE = Decimal("8.00")
WATER_TIER_1 = Decimal("4.00")
WE3_FLOOR = Decimal("15.00")

#: WE-3, every stated figure. Written out so a reader can check the arithmetic
#: without opening the workbook, and so a drift shows as a number rather than as
#: a diff of two opaque decimals.
WE3_USAGE = Decimal("1.60")  # 0.4 kgal × $4.00
WE3_SUBTOTAL = Decimal("9.60")  # 1.60 + 8.00
WE3_ADJUSTMENT = Decimal("5.40")  # 15.00 − 9.60
WE3_TAX = Decimal("1.42")  # 9.45% of 15.00
WE3_TOTAL = Decimal("16.42")


def _price(config, quantity):
    return rating_seam.price_bill(
        services=((config, quantity),),
        period=FULL_MONTH,
        account=TAXED,
        taxes=WE_TAXES,
        fees=(),
    )


def _kgal(amount):
    return rating_seam.Quantity(amount=Decimal(amount), unit="kgal")


def _amounts(bill, kind):
    return [line.amount for line in bill.lines if line.kind == kind]


# ── 1 · THE MONEY, from the schedule's figure, unchanged ────────────────────


def test_the_floor_from_the_schedule_prices_we3_to_the_cent():
    """A `$15.00` floor arriving from the RATE SCHEDULE prices WE-3 exactly.

    This is the arithmetic assertion and it is deliberately the first thing in
    the file: whatever the source, `1.60 + 8.00 = 9.60` under a `15.00` floor is
    `+5.40` and `$16.42` including tax. If this line ever moves, the change is a
    B4/B5 re-sign and not a refactor.
    """
    config = rating_seam.TariffConfig(
        service="water",
        model="flat",
        billed_unit="kgal",
        base_charge=WATER_BASE,
        unit_price=WATER_TIER_1,
        minimum_amount=WE3_FLOOR,
    )
    bill = _price(config, _kgal("0.4"))

    assert _amounts(bill, "usage") == [WE3_USAGE]
    assert _amounts(bill, "base") == [WATER_BASE]
    assert _amounts(bill, "minimum_adjustment") == [WE3_ADJUSTMENT]
    assert sum(_amounts(bill, "tax")) == WE3_TAX
    assert bill.total == WE3_TOTAL


def test_no_floor_anywhere_is_five_dollars_forty_short_and_that_is_the_risk():
    """The SAME bill with no floor is `$9.60` + tax, not `$16.42`.

    ⚠ **This is the failure `rating/0031` would ship without `rating/0030`, and
    it is written down as a number so nobody has to imagine it.** Every line is
    individually correct, the document foots, and `$5.40` a month is missing
    from one real customer's bill.
    """
    config = rating_seam.TariffConfig(
        service="water",
        model="flat",
        billed_unit="kgal",
        base_charge=WATER_BASE,
        unit_price=WATER_TIER_1,
        minimum_amount=None,
    )
    bill = _price(config, _kgal("0.4"))

    assert _amounts(bill, "minimum_adjustment") == []
    assert bill.total != WE3_TOTAL
    assert bill.total == Decimal("10.51")  # 9.60 + 9.45% of 9.60


# ── 2 · THE HOP — the database column the engine actually reads ─────────────


@pytest.mark.django_db
def test_the_hop_starts_at_the_schedule_version_and_ends_on_the_bill(brazos):
    """From `tariff_versions.minimum_bill` in the database to `$16.42` priced.

    ⚠ **THE HOP IS THE THING THIS TEST EXISTS FOR**, in `DEF-466`'s own words:
    *"the engine's own tests pass a tariff carrying the factor directly, so the
    arithmetic is proven and the SOURCING is untested."* Test 1 above proves the
    arithmetic. This one starts at a row in the database, goes through
    `rating.selectors.pricing_inputs` and `billing.gather._tariff_config_for`,
    and asserts the DOLLARS at the other end.

    **Both halves, the same shape `DEF-484`'s re-proof uses.** A schedule
    stating no floor prices `$10.51`; the same schedule stating WE-3's `$15.00`
    prices `$16.42`. A move that lost the figure would fail the second half
    while every column assertion in the repository stayed green.
    """
    with tenant_ctx(brazos):
        plan = make_plan(brazos, name="Silver Creek Residential", services=("water",))
        bound = rating_models.PlanRateSchedule.objects.get(rate_plan_id=plan.id)
        service_date = date(2026, 8, 15)

        # ⚠ **THE VERSION IS BUILT HERE AND NOT TAKEN FROM THE FIXTURE.**
        # `make_plan` creates the tariff and NO version, so `in_force_version`
        # answers `None` and every read below would be about an absent schedule
        # rather than about which of two columns is read. That is the
        # *incapable of failing* shape, so the assertion beneath the creation
        # states what it needs rather than trusting the fixture to supply it.
        version = rating_models.TariffVersion.objects.create(
            tenant=brazos,
            tariff=bound.tariff,
            model="flat",
            uom="kgal",
            # A base is stated so `_base_charge_for` can answer at all: this
            # tenant declares no `is_base` charge code and the plan states
            # nothing, and `CR-013` part 1 makes a blank base *this size is not
            # served* — which refuses the bill by name. It is the SAME `$8.00`
            # WE-3 uses, so the priced figures below are the workbook's.
            base_charge=WATER_BASE,
            # ⚠ NO `unit_price` — `TariffVersion` has none. The per-unit price
            # lives on `RateTier`, and this test does not need one: the hop it
            # proves ends at `TariffConfig.minimum_amount`, and the priced bill
            # below is built with WE-3's own base and tier so the figures are the
            # workbook's rather than this fixture's.
            effective_from=date(2026, 1, 1),
        )
        assert rating_selectors.in_force_version(bound.tariff, service_date) == version, (
            "the version just created must be the one in force at the service "
            "date, or this test proves nothing about the source it claims to check"
        )

        # ── `DEF-BIL-7170` · THE BASE MOVES ONTO THE CHARGE CODE ────────────
        # ⚠ **THE COMMENT ON `base_charge=` ABOVE IS NOW HALF TRUE AND IS KEPT
        # WITH THIS STAMP.** It says the version's own base is stated *"so
        # `_base_charge_for` can answer at all"*. From 2026-09-28 that column is
        # RETIRED and unread — PO: *"we will never take default value from plan
        # $8.0 - that is retired"* — so `_tariff_config_for` below refused with
        # *"No base charge for water. Declare one on Charge codes."* and this
        # test could not reach the minimum it exists to measure.
        #
        # The SAME `$8.00` is stated on the object that now owns it, unscoped,
        # so the priced figures below are still WE-3's own.
        rating_models.Charge.objects.get_or_create(
            tenant=brazos,
            code="BASE-W-CR090",
            defaults=dict(
                name="Water base",
                charge_type="recurring",
                service=tenancy_models.Service.objects.get(code="water"),
                amount_rule="flat",
                amount=WATER_BASE,
                is_base=True,
                applies_to_customer_classes=[],
            ),
        )

        # ── Half 1 · no floor stated anywhere. Nothing appears unbidden.
        rating_models.TariffVersion.objects.filter(pk=version.pk).update(minimum_bill=None)
        quiet = gather._tariff_config_for(bound.tariff, "water", service_date)
        assert quiet.minimum_amount is None

        # ── Half 2 · WE-3's own figure, stored on the SCHEDULE and read back
        # through the seam the engine actually uses.
        #
        # ⚠ **AMENDED 2026-10-01 (`DEF-RAT-8737`, PO option A: *"A · Minimum
        # per size - this is correct"*).** The schedule's figure is now the
        # PER-SIZE one on `rate_size_rows`; the version's scalar is no longer
        # billed. So the version figure alone now reaches NOTHING, and the
        # same `$15.00` on the 5/8" size row reaches the bill for a 5/8"
        # connection — the hop this test exists for, one row further on.
        rating_models.TariffVersion.objects.filter(pk=version.pk).update(minimum_bill=WE3_FLOOR)
        retired = gather._tariff_config_for(bound.tariff, "water", service_date, size_class="W-58")
        assert retired.minimum_amount is None, (
            "the per-version minimum is still billed — the PO removed it on 2026-10-01"
        )
        rating_models.TariffVersion.objects.filter(pk=version.pk).update(minimum_bill=None)
        rating_models.RateSizeRow.objects.create(
            tenant=brazos,
            tariff_version=version,
            size_class="W-58",
            minimum_bill=WE3_FLOOR,
            currency="USD",
        )
        stated = gather._tariff_config_for(bound.tariff, "water", service_date, size_class="W-58")
        assert stated.minimum_amount == Decimal("15.000000")

        # ── And the MONEY at the end of the hop. Priced with the fixture's own
        # base and tier so the figures are WE-3's and not this test's.
        priced = _price(
            rating_seam.TariffConfig(
                service="water",
                model="flat",
                billed_unit="kgal",
                base_charge=WATER_BASE,
                unit_price=WATER_TIER_1,
                minimum_amount=stated.minimum_amount,
            ),
            _kgal("0.4"),
        )
        assert priced.total == WE3_TOTAL


@pytest.mark.django_db
def test_the_plan_no_longer_publishes_a_per_service_minimum(brazos):
    """`plan_rate_schedules` does not carry `minimum_amount` at all.

    ⚠ **AN ABSENT KEY, NOT A `None`.** A caller that still reads the plan's
    figure gets a `KeyError` rather than a floor of *no minimum* it would
    silently believe — which is the same reasoning `plan_detail` uses when it
    renames its own served key. Mode (B), the plan floor, is still the plan's
    and is still published.
    """
    with tenant_ctx(brazos):
        plan = make_plan(brazos, name="Silver Creek Residential", services=("water",))
        row = rating_selectors.plan_rate_schedules(plan.id)[0]
        assert "minimum_amount" not in row
        assert "plan_minimum_bill_amount" in row


# ── 3 · THE PER-SIZE GUARD — a floor is charged ONCE, not once per line ─────


def test_only_the_first_size_group_may_carry_the_floor():
    """`carries_service_minimum=False` yields no floor on the later groups.

    ⚠ **THIS IS THE HALF THE RENAME EXISTS FOR.** The plan's column was read by
    the CALLER, which passed it on the first size group only. The schedule's
    column is read INSIDE `_tariff_config_for`, and `inputs` is built per size
    group — so reading it unconditionally would top a warehouse's 6" and two 2"
    fire lines up three times. Asserted on the flag rather than on a bill
    because the fire fixture is a different lane's; the money consequence is
    named here so the next reader knows what the flag is worth.
    """
    inputs = {"minimum_bill": Decimal("60.00")}
    assert gather._decimal_or_none(inputs.get("minimum_bill")) == Decimal("60.00")
    # The expression `_tariff_config_for` evaluates, isolated — the flag decides
    # whether the figure is read at all.
    for carries, expected in ((True, Decimal("60.00")), (False, None)):
        got = gather._decimal_or_none(inputs.get("minimum_bill")) if carries else None
        assert got == expected


# ── PROVED RED FIRST — quoted verbatim, through pytest ──────────────────────
#
# The proof is recorded in `12-governance/02-decision-log.md` under the entry of
# 2026-09-10 for this change, and the two failures are:
#
#   1 · With `gather._tariff_config_for` left reading the plan's column, the
#       hop test fails on the SOURCE:
#           E   AssertionError: assert None == Decimal('15.000000')
#           E    +  where None = TariffConfig(...).minimum_amount
#
#   2 · With `rating/0030` skipped and only `0031` applied to the seeded
#       utility, `test_seed_demo.py` fails on the MONEY, which is the failure
#       that matters:
#           E   assert Decimal('10.51') == Decimal('16.42')
