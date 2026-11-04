# ── Trace ──────────────────────────────────────────────
# Change:  CR-052 W1 tasks 4·5·6·7 — the two minimum-bill thresholds cross the
#          seam, the stage that owns the rule applies them, and the adjustment
#          is its own TAXABLE line.
# Rules:   BR-RAT-028 (CONFIRMED, PO Q&A R5+R6 — **both modes**: (A) the
#          per-service minimum, ⚠ **`tariff_versions.minimum_bill` SINCE THE PO
#          RULING OF 2026-09-10** and `plan_services.minimum_amount` before it,
#          (B) the plan floor `plans.minimum_bill_amount`; when both are set,
#          per-service
#          minimums apply FIRST and the plan floor then tops up the total) ·
#          BR-RAT-005 / B4.2 (the tax base is decided by KIND — the minimum
#          adjustment is one of the three kinds admitted) · BR-RAT-003 / B4.4
#          (round per line, half-up, 2dp, at finalization only) ·
#          CLAUDE.md hard rule 2 (money) · hard rule 3 (an explicit unit)
# Golden:  GT-13 (usage 6.10 + base 12.00 = 18.10 < min 25.00 → adjustment
#          6.90; tax on 25.00) · WE-3 / GT-19 (water-only, 0.4 kgal: usage 1.60
#          + base 8.00 = 9.60 < min 15.00 → +5.40, tax on 15.00 = 1.42, total
#          **16.42**). GT-13 is a PROPOSED golden test; WE-3's figures are the
#          billing workbook's own and are reproduced here, never retyped.
# Tests:   this file
# Impacts: apps/billing/rating_seam.TariffConfig (the seam that carries the two
#          thresholds) · apps/billing/gather.py (the projection) ·
#          apps/rating/pricing/stages/apply_charges.py (the rule) ·
#          apps/rating/engine.price_bill (the bill-level floor)
# ───────────────────────────────────────────────────────
"""BR-RAT-028 — the minimum bill, both modes, end to end through the seam.

⚠ **THE RULE WAS SIGNED AND HAD NO INPUT.** `apply_charges.py` said so by name
for three weeks: *"neither the per-service minimum (`plan_services
.minimum_amount`) nor the plan floor (`plans.minimum_bill_amount`) can travel on
the seam's `TariffConfig` today, so there is no input to apply."* This file is
the proof that both now travel and that the arithmetic over them reproduces the
workbook's own figures.

**WHY THE ADJUSTMENT IS TAXED.** B4's addendum (OQ-007) says the minimum-bill
adjustment line is *"taxable like base"*, and both signed examples state the tax
base as the MINIMUM and not the subtotal — GT-13's *"tax on $25.00"* and WE-3's
*"tax on 15.00 = 1.42"*. The engine gets that structurally rather than from a
flag: `KIND_MINIMUM_ADJUSTMENT` is one of the three kinds in `TAX_BASE_KINDS`,
so a minimum adjustment enters a percent base for the same reason a base charge
does, and a fee still cannot.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from apps.billing import gather, rating_seam
from apps.rating import models as rating_models
from apps.rating import selectors as rating_selectors
from apps.rating.pricing import errors as pricing_errors
from apps.tenancy import models as tenancy_models

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import make_plan, tenant_ctx

USD = "USD"
TAXED = rating_seam.AccountContext(currency=USD, tax_exempt=False)
FULL_MONTH = rating_seam.BillingPeriod(cycle_days=30, service_days=30)

#: WE-1's four authorities, recovered from the workbook's own addends rather
#: than retyped: 13.87 / 2.22 / 4.44 / 0.44 on a taxable 221.90 are 6.25%, 1%,
#: 2% and 0.2%, and the same four rates reproduce WE-3's 0.94 / 0.15 / 0.30 /
#: 0.03 on 15.00. Four rules, because WE-3 states four addends and one combined
#: rate would hide which authority is owed what (BR-BIL-069).
WE_TAXES = (
    rating_seam.TaxRule(code="STATE", rate=Decimal("0.0625")),
    rating_seam.TaxRule(code="COUNTY", rate=Decimal("0.01")),
    rating_seam.TaxRule(code="CITY", rate=Decimal("0.02")),
    rating_seam.TaxRule(code="DISTRICT", rate=Decimal("0.002")),
)

#: Silver Creek's own residential water: `$8.00` base, tier-1 `$4.00 / kgal`
#: (core/sample_fixture.py). 0.4 kgal therefore prices at `1.60`, which is
#: WE-3's usage figure exactly — the fixture is not retyped from the workbook.
WATER_TIER_1 = Decimal("4.00")
WATER_BASE = Decimal("8.00")


def water(minimum_amount=None, plan_floor=None):
    return rating_seam.TariffConfig(
        service="water",
        model="flat",
        billed_unit="kgal",
        base_charge=WATER_BASE,
        unit_price=WATER_TIER_1,
        minimum_amount=minimum_amount,
        plan_minimum_bill_amount=plan_floor,
    )


def electric(minimum_amount=None, plan_floor=None):
    return rating_seam.TariffConfig(
        service="electric",
        model="flat",
        billed_unit="kWh",
        base_charge=Decimal("12.00"),
        unit_price=Decimal("0.10"),
        minimum_amount=minimum_amount,
        plan_minimum_bill_amount=plan_floor,
    )


def kgal(amount):
    return rating_seam.Quantity(amount=Decimal(amount), unit="kgal")


def kwh(amount):
    return rating_seam.Quantity(amount=Decimal(amount), unit="kWh")


def price(services, taxes=(), fees=()):
    return rating_seam.price_bill(
        services=services, period=FULL_MONTH, account=TAXED, taxes=taxes, fees=fees
    )


def adjustments(bill):
    return tuple(line for line in bill.lines if line.kind == "minimum_adjustment")


# ── Task 4 — the two thresholds CROSS THE SEAM ──────────────────────────────


def test_task4_the_seam_carries_both_thresholds_and_defaults_to_neither():
    """`TariffConfig` publishes both, and both default to None — absence, not 0.

    `None` is BR-RAT-028's "no minimum", which is what every tariff in the
    database says today. A default of `Decimal("0")` would be a floor of zero
    that bites on no bill and reads identically — the shape `base_charge=None`
    already avoids, for the same reason.
    """
    plain = water()
    assert plain.minimum_amount is None
    assert plain.plan_minimum_bill_amount is None

    stated = water(minimum_amount=Decimal("15.000000"), plan_floor=Decimal("20.000000"))
    assert stated.minimum_amount == Decimal("15.000000")
    assert stated.plan_minimum_bill_amount == Decimal("20.000000")


@pytest.mark.django_db
def test_task4_rating_publishes_both_thresholds_and_gather_projects_them(brazos):
    """The DB half — the stored figures reach `TariffConfig` UNCHANGED.

    ⚠ **THE HOP IS THE THING THIS TEST EXISTS FOR.** DEF-466's own words: *"the
    engine's own tests pass a tariff carrying the factor directly, so the
    arithmetic is proven and the SOURCING is untested."* Every other test in
    this file constructs a `TariffConfig` by hand; this one starts in the
    database and ends at the fields the engine reads.

    ⚠ **AMENDED 2026-09-10 — MODE (A) IS NO LONGER PUBLISHED HERE.** PO ruling,
    *"set it in rates and use it in plans - thats it - this is rule"*: the
    per-service floor moved onto `tariff_versions.minimum_bill`
    (`rating/0030`+`0031`) and this seam publishes only mode (B), the PLAN's
    whole-bill floor, which no schedule could carry. **Mode (A)'s hop is not
    lost — it moved to its own file**,
    `test_cr090_minimum_reads_from_the_schedule.py`, which asserts it in DOLLARS
    at the end of the hop (`$16.42` with the schedule's floor, `$10.51`
    without) because a column assertion cannot tell a successful move from a
    lost one.

    Both halves are still asserted, exactly as DEF-484's own re-proof does: a
    plan stating no floor answers `None` — which is every plan in every existing
    database and is why no issued bill moves — and a plan stating one answers
    that figure and no others.
    """
    with tenant_ctx(brazos):
        plan = make_plan(brazos, name="Silver Creek Residential", services=("water",))

        # ── Half 1: an untouched plan states no floor. Nothing appears unbidden.
        quiet = rating_selectors.plan_rate_schedules(plan.id)[0]
        assert quiet["plan_minimum_bill_amount"] is None
        # ⚠ AN ABSENT KEY, NOT A `None` — a caller that still reads the plan's
        # per-service figure gets a `KeyError` rather than a floor of *no
        # minimum* it would silently believe.
        assert "minimum_amount" not in quiet

        # ── Half 2: the plan floor, stored and then read back out.
        service = tenancy_models.Service.objects.get(code="water")
        rating_models.PlanService.objects.update_or_create(
            tenant=brazos,
            rate_plan_id=plan.id,
            service=service,
            defaults={"base_charge": WATER_BASE},
        )
        rating_models.RatePlan.objects.filter(pk=plan.id).update(
            minimum_bill_amount=Decimal("20.00")
        )
        row = rating_selectors.plan_rate_schedules(plan.id)[0]
        assert row["plan_minimum_bill_amount"] == Decimal("20.000000")

        # ── And the projection: gather carries it across UNCHANGED. No
        # precedence, no fallback, no third figure — see the note beside
        # `minimum_amount=` in `gather._tariff_config_for` and DEF-2589.
        assert gather._decimal_or_none(row["plan_minimum_bill_amount"]) == Decimal("20.000000")


# ── Tasks 5·6·7 — MODE A, the per-service minimum, on the SIGNED example ─────


def test_task7_we3_the_signed_example_water_only_0_4_kgal():
    """WE-3 / GT-19, every stated figure: 1.60 + 8.00 = 9.60 → +5.40 → 16.42."""
    bill = price(((water(minimum_amount=Decimal("15.00")), kgal("0.4")),), taxes=WE_TAXES)

    usage = tuple(line for line in bill.lines if line.kind == "usage")
    base = tuple(line for line in bill.lines if line.kind == "base")
    assert [line.amount for line in usage] == [Decimal("1.60")]
    assert [line.amount for line in base] == [Decimal("8.00")]

    # "Minimum bill adjustment" +5.40 (taxable)
    adjustment = adjustments(bill)
    assert len(adjustment) == 1
    assert adjustment[0].amount == Decimal("5.40")
    assert adjustment[0].description == "Minimum bill adjustment"
    assert adjustment[0].taxable is True
    assert adjustment[0].service == "water"

    # tax on 15.00 = 1.42 (0.94 + 0.15 + 0.30 + 0.03)
    assert bill.taxable_subtotal == Decimal("15.00")
    assert [line.amount for line in bill.lines if line.kind == "tax"] == [
        Decimal("0.94"),
        Decimal("0.15"),
        Decimal("0.30"),
        Decimal("0.03"),
    ]
    assert bill.tax_total == Decimal("1.42")

    # total 16.42
    assert bill.total == Decimal("16.42")


def test_task7_gt13_the_other_signed_example():
    """GT-13: usage 6.10 + base 12.00 = 18.10 < 25.00 → 6.90; tax base 25.00."""
    tariff = rating_seam.TariffConfig(
        service="electric",
        model="flat",
        billed_unit="kWh",
        base_charge=Decimal("12.00"),
        unit_price=Decimal("0.10"),
        minimum_amount=Decimal("25.00"),
    )
    bill = price(((tariff, kwh("61")),))

    assert [line.amount for line in bill.lines if line.kind == "usage"] == [Decimal("6.10")]
    assert adjustments(bill)[0].amount == Decimal("6.90")
    assert bill.taxable_subtotal == Decimal("25.00")


def test_task5_a_subtotal_at_or_above_the_minimum_emits_no_line():
    """No adjustment, not a `$0.00` one — the bill must not carry an empty row."""
    at = price(((water(minimum_amount=Decimal("9.60")), kgal("0.4")),))
    above = price(((water(minimum_amount=Decimal("5.00")), kgal("0.4")),))
    assert adjustments(at) == ()
    assert adjustments(above) == ()
    assert at.total == above.total == Decimal("9.60")


def test_task5_no_threshold_stated_prices_byte_for_byte_as_before():
    """Every tariff in the database states neither, so no issued bill moves."""
    bill = price(((water(), kgal("0.4")),), taxes=WE_TAXES)
    assert adjustments(bill) == ()
    assert bill.taxable_subtotal == Decimal("9.60")
    # 9.60 x (6.25 + 1 + 2 + 0.2)% = 0.60 + 0.10 + 0.19 + 0.02
    assert bill.tax_total == Decimal("0.91")
    assert bill.total == Decimal("10.51")


def test_task5_the_minimum_is_PER_SERVICE_and_never_pools():
    """Mode A tops each service to its own floor; a rich service does not cover
    a poor one. Electric 12.00 + 6.10 = 18.10 is above its 15.00 and stays put;
    water 9.60 is below its 15.00 and is topped by 5.40."""
    bill = price(
        (
            (electric(minimum_amount=Decimal("15.00")), kwh("61")),
            (water(minimum_amount=Decimal("15.00")), kgal("0.4")),
        )
    )
    lines = adjustments(bill)
    assert [(line.service, line.amount) for line in lines] == [("water", Decimal("5.40"))]
    assert bill.taxable_subtotal == Decimal("33.10")  # 18.10 + 15.00


# ── MODE B — the PLAN FLOOR tops up the TOTAL ───────────────────────────────


def test_task5_mode_b_the_plan_floor_tops_up_the_whole_bill():
    """Two services, no per-service minimum, one plan floor over their sum.

    electric 12.00 + 6.10 = 18.10 and water 8.00 + 1.60 = 9.60 make 27.70; a
    plan floor of 40.00 adds 12.30 ONCE, at bill level, and the line names no
    service because the floor is a fact about the PLAN.
    """
    bill = price(
        (
            (electric(plan_floor=Decimal("40.00")), kwh("61")),
            (water(plan_floor=Decimal("40.00")), kgal("0.4")),
        )
    )
    lines = adjustments(bill)
    assert len(lines) == 1
    assert lines[0].amount == Decimal("12.30")
    assert lines[0].service is None
    assert lines[0].description == "Minimum bill adjustment"
    assert lines[0].taxable is True
    assert bill.taxable_subtotal == Decimal("40.00")
    assert bill.total == Decimal("40.00")


def test_task5_both_modes_per_service_FIRST_then_the_plan_floor():
    """BR-RAT-028's combination rule, worked.

    Water 9.60 is topped to its own 15.00 (+5.40). Electric 18.10 needs
    nothing. The bill is then 33.10, and a plan floor of 40.00 tops THAT by
    6.90 — the floor sees the topped-up subtotal, which is what "per-service
    minimums apply first, then the plan floor tops up the total" means.
    """
    bill = price(
        (
            (electric(minimum_amount=Decimal("15.00"), plan_floor=Decimal("40.00")), kwh("61")),
            (water(minimum_amount=Decimal("15.00"), plan_floor=Decimal("40.00")), kgal("0.4")),
        )
    )
    lines = adjustments(bill)
    assert [(line.service, line.amount) for line in lines] == [
        ("water", Decimal("5.40")),
        (None, Decimal("6.90")),
    ]
    assert bill.taxable_subtotal == Decimal("40.00")


def test_task5_a_plan_floor_already_met_adds_nothing():
    bill = price(
        (
            (electric(plan_floor=Decimal("20.00")), kwh("61")),
            (water(plan_floor=Decimal("20.00")), kgal("0.4")),
        )
    )
    assert adjustments(bill) == ()
    assert bill.total == Decimal("27.70")


def test_task5_a_fee_never_helps_a_bill_reach_its_floor():
    """B4.2 is structural: a fee is outside the tax base, so it is outside the
    minimum-bill basis too. A 20.00 late fee on a 9.60 water bill with a 15.00
    floor still owes the full 5.40 adjustment — the customer is not treated as
    having reached a minimum because a penalty was added to their bill."""
    fee = rating_seam.RatedLine(
        kind="fee", description="Late fee", amount=Decimal("20.00"), taxable=False
    )
    bill = price(((water(plan_floor=Decimal("15.00")), kgal("0.4")),), fees=(fee,))
    assert [line.amount for line in adjustments(bill)] == [Decimal("5.40")]
    assert bill.taxable_subtotal == Decimal("15.00")
    assert bill.total == Decimal("35.00")  # 15.00 + the 20.00 fee; no tax rules passed


def test_task5_two_plans_stating_DIFFERENT_floors_refuse_by_name():
    """A master's bill can carry tariffs from more than one plan (BR-CUS-014),
    and nothing signed says which plan's floor governs the combined total. The
    engine refuses rather than picking the first one it reached.

    It surfaces as the SEAM's `PricingRefused` and not as a raw engine error:
    `rating_seam._priced` adapts every `RatingError` so a bill run records the
    account as an exception a clerk can read (BR-BIL-055) instead of the run
    dying on its first account. Both facts are asserted — the seam's wrapper
    and the rule id inside it — because a refusal a clerk cannot act on is the
    failure the wrapper exists to remove.
    """
    with pytest.raises(rating_seam.PricingRefused) as refusal:
        price(
            (
                (electric(plan_floor=Decimal("40.00")), kwh("61")),
                (water(plan_floor=Decimal("60.00")), kgal("0.4")),
            )
        )
    assert "BR-RAT-028" in str(refusal.value)
    assert "40.00" in str(refusal.value) and "60.00" in str(refusal.value)


def test_task5_the_refusal_is_a_rating_input_error_underneath():
    """The engine's own door raises B4's own error type, which is what makes
    the seam's adapter catch it rather than letting it escape as a bug."""
    from apps.rating.pricing.stages import apply_charges as stage

    class _Config:
        def __init__(self, floor):
            self.plan_minimum_bill_amount = floor

    with pytest.raises(pricing_errors.RatingInputError):
        stage.plan_floor((_Config(Decimal("40.00")), _Config(Decimal("60.00"))))
    assert stage.plan_floor((_Config(None), _Config(None))) is None
    assert stage.plan_floor((_Config(Decimal("40.00")), _Config(Decimal("40.00")))) == Decimal(
        "40.00"
    )
