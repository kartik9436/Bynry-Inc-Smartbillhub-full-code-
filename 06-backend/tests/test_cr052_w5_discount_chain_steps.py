# ── Trace ──────────────────────────────────────────────
# Change:  CR-052 W5 task 17 — "Price the two discount types that refuse at
#          set-up: `rate_override` needs a schedule swap in R2, `usage_allowance`
#          a quantity deduction before the tier walk".
# Rules:   CR-013 part 3 (the five discount types; the two refusals a rate
#          override must make — "retired or mismatched-service schedules") ·
#          BR-RAT-007 (a period prices on the terms in force AT THE SERVICE
#          DATE) · BR-RAT-001 / B4.4 (quantity is settled BEFORE the tier walk)
#          · BR-RAT-038 (no silent conversion) · CLAUDE.md hard rule 3 (an
#          explicit unit, always) · CLAUDE.md prime directive (an OPEN question
#          is stubbed with its id, never answered by choosing)
# Blocked: OQ-291 (a usage allowance is a QUANTITY and no column holds its unit)
#          · OQ-292 (a rate override swaps a SCHEDULE and no column holds which)
#          — both OPEN, both the PO's call.
# ───────────────────────────────────────────────────────
"""The two discount types that refuse at set-up, built as far as the data allows.

**WHAT THIS FILE PROVES AND WHAT IT DELIBERATELY DOES NOT.**

CR-052 task 17 says these two are fixed *in the chain's own terms* — a schedule
swap in R2, a quantity deduction before the tier walk — *"not a special case in
billing"*. Both are built here, in `apps/rating/resolution.py`, as pure
narrowings with worked figures.

**Neither prices a bill, and that is correct rather than a shortfall.** Three
separate things stand in the way and only one of them is code:

  1. `OQ-291` and `OQ-292` are OPEN. Nothing stores WHICH schedule a rate
     override swaps to, and nothing stores WHAT UNIT a usage allowance is
     measured in. The prime directive says implement to the boundary and stub
     the gap with the question's id — so `rate_override_target` and
     `usage_allowance_units` raise `NotImplementedError` naming them, and this
     file asserts that they do.
  2. `DEF-438` — the R1–R7 chain has NO production caller. Switching a step is
     the ruled six-step cutover's step 5 and is gated on the PO's step 4
     (CR-052 task 20), which has not happened.
  3. `DISCOUNT_TYPES_PRICEABLE` is therefore UNCHANGED and activation still
     refuses both types. That is not an oversight: a `usage_allowance` that
     activated today would reach the LIVE path, where `discount_pricing`
     refuses it by name, and break every bill for that account.

The last test in this file asserts all three, so a later lane cannot switch one
without meeting the other two.
"""

from datetime import date
from decimal import Decimal

import pytest

from apps.rating import discounts as discount_models
from apps.rating import resolution

SERVICE_DATE = date(2026, 7, 31)
STANDARD = "tariff-water-standard"
SUBSIDY = "tariff-water-subsidy"
ELECTRIC = "tariff-electric-standard"


def a_version(version_id, tariff_id, service="water", frm=date(2026, 1, 1), to=None):
    return resolution.ScheduleVersion(
        version_id=version_id,
        service=service,
        tariff_id=tariff_id,
        effective_from=frm,
        effective_to=to,
        size_rows={"5/8": Decimal("8.00")},
    )


PLAN = resolution.PlanVersion(
    plan_id="plan-residential",
    version=1,
    services=("water",),
    effective_from=date(2026, 1, 1),
    schedules={"water": STANDARD},
)


def a_catalogue(*versions):
    return resolution.Catalogue(plan_versions=(PLAN,), schedule_versions=versions)


# ══════════════════════════════════════════════════════════════════════════
# R2 · THE SCHEDULE SWAP
# ══════════════════════════════════════════════════════════════════════════


def test_tc1__no_override_resolves_exactly_what_r2_always_resolved():
    """Every account in the product. The swap is additive to the digit."""
    catalogue = a_catalogue(a_version("v-std-1", STANDARD))
    assert (
        resolution.resolve_schedule_with_override(catalogue, PLAN, "water", SERVICE_DATE).version_id
        == "v-std-1"
    )


def test_tc2__an_override_binds_the_subsidised_schedule_instead():
    """CR-013 part 3: *"Rate override is the mechanism behind 'Res Electric ·
    Tiered (subsidy)'"*. The customer is billed from a DIFFERENT SCHEDULE, so
    every tier boundary, every block price and the minimum move together — which
    is exactly why this cannot be expressed as money taken off at R6."""
    catalogue = a_catalogue(a_version("v-std-1", STANDARD), a_version("v-sub-1", SUBSIDY))
    resolved = resolution.resolve_schedule_with_override(
        catalogue, PLAN, "water", SERVICE_DATE, override_tariff_id=SUBSIDY
    )
    assert resolved.version_id == "v-sub-1"
    assert resolved.tariff_id == SUBSIDY


def test_tc3__the_override_still_picks_the_version_in_force_at_the_service_date():
    """BR-RAT-007 governs the overriding schedule exactly as it governs the
    plan's own: two versions, and the one whose window contains the service date
    wins. There is no fallback to the newest."""
    catalogue = a_catalogue(
        a_version("v-std-1", STANDARD),
        a_version("v-sub-old", SUBSIDY, frm=date(2025, 1, 1), to=date(2026, 6, 1)),
        a_version("v-sub-new", SUBSIDY, frm=date(2026, 6, 1)),
    )
    resolved = resolution.resolve_schedule_with_override(
        catalogue, PLAN, "water", SERVICE_DATE, override_tariff_id=SUBSIDY
    )
    assert resolved.version_id == "v-sub-new"


def test_tc4__a_retired_override_refuses_and_never_falls_back():
    """CR-013 part 3's own words — the product must refuse *"rate overrides
    pointing at retired … schedules"*.

    ⚠ **THE REFUSAL IS THE FEATURE.** Falling back to the plan's ordinary
    schedule would bill the customer the FULL rate on a subsidy the utility
    believes it granted, on a document where nothing looks wrong. That is the
    failure part 3's *"subsidy granted is reportable"* exists to prevent, and
    the customer is the one who finds out."""
    catalogue = a_catalogue(
        a_version("v-std-1", STANDARD),
        a_version("v-sub-old", SUBSIDY, frm=date(2025, 1, 1), to=date(2026, 6, 1)),
    )
    with pytest.raises(resolution.RateOverrideUnusable) as refusal:
        resolution.resolve_schedule_with_override(
            catalogue, PLAN, "water", SERVICE_DATE, override_tariff_id=SUBSIDY
        )
    # The sentence a clerk reads names no register id (G28 / CR-016); the id
    # for CR-013 part 3's "retired" refusal is in the comment beside the raise.
    assert "was not in force on" in str(refusal.value)
    assert refusal.value.step == "R2"


def test_tc5__a_mismatched_service_override_refuses_and_names_both_services():
    """Part 3's second named refusal. A subsidised ELECTRIC schedule cannot price
    a water meter, and the message says which is which so a utility can fix the
    configuration rather than the symptom."""
    catalogue = a_catalogue(
        a_version("v-std-1", STANDARD),
        a_version("v-elec-1", ELECTRIC, service="electric"),
    )
    with pytest.raises(resolution.RateOverrideUnusable) as refusal:
        resolution.resolve_schedule_with_override(
            catalogue, PLAN, "water", SERVICE_DATE, override_tariff_id=ELECTRIC
        )
    assert "'water'" in str(refusal.value) and "'electric'" in str(refusal.value)


def test_tc6__an_override_naming_a_schedule_this_tenant_has_never_had_refuses():
    catalogue = a_catalogue(a_version("v-std-1", STANDARD))
    with pytest.raises(resolution.RateOverrideUnusable):
        resolution.resolve_schedule_with_override(
            catalogue, PLAN, "water", SERVICE_DATE, override_tariff_id="tariff-nobody-has"
        )


def test_tc7__an_override_naming_the_plans_own_schedule_is_not_an_override():
    """A configuration that says nothing, not one that says something impossible.
    Returned rather than refused."""
    catalogue = a_catalogue(a_version("v-std-1", STANDARD))
    assert (
        resolution.resolve_schedule_with_override(
            catalogue, PLAN, "water", SERVICE_DATE, override_tariff_id=STANDARD
        ).version_id
        == "v-std-1"
    )


# ══════════════════════════════════════════════════════════════════════════
# R3b · THE QUANTITY DEDUCTION
# ══════════════════════════════════════════════════════════════════════════


def deduct(billable, allowance, allowance_unit="kgal", billed_unit="kgal"):
    return resolution.allowance_deducted_quantity(
        "water",
        Decimal(billable) if billable is not None else None,
        billed_unit,
        allowance=None if allowance is None else Decimal(allowance),
        allowance_unit=allowance_unit,
    )


def test_tc8__no_allowance_leaves_the_quantity_exactly_as_it_was():
    """Every account in the product; the deduction is additive to the digit."""
    assert deduct("18.72", None) == Decimal("18.72")


def test_tc9__the_allowance_comes_off_the_quantity_before_anything_is_priced():
    """**THE WORKED FIGURE, and it is why the placement is the rule.**

    Water priced `0–5 @ 3.20 / 5–15 @ 4.80 / 15+ @ 7.20`, meter `18.72 kgal`,
    programme allows `2 kgal` free.

        priced as read   16.00 + 48.00 + 26.78 = 90.78
        deducted here    16.72 kgal -> 16.00 + 48.00 + 12.38 = 76.38

    The allowance is worth **$14.40** — the two kilogallons come off the TOP
    block at 7.20, which is what "before the tier walk" means. The same
    allowance handed to R6 as a money credit at the bill's average price
    (90.78 / 18.72 = 4.85/kgal) is **$9.70**, and the customer is $4.70 worse
    off on one bill for a discount the utility believes it granted.
    """
    assert deduct("18.72", "2") == Decimal("16.72")
    # The arithmetic the deduction enables, worked here so the figure above is
    # a number this file computed and not a sentence it asserts.
    tiers = (
        (Decimal("5"), Decimal("3.20")),
        (Decimal("10"), Decimal("4.80")),
        (None, Decimal("7.20")),
    )

    def priced(quantity):
        remaining, total = quantity, Decimal("0")
        for span, rate in tiers:
            take = remaining if span is None or remaining < span else span
            total += take * rate
            remaining -= take
            if remaining <= 0:
                break
        return total.quantize(Decimal("0.01"))

    assert priced(Decimal("18.72")) == Decimal("90.78")
    assert priced(Decimal("16.72")) == Decimal("76.38")
    assert priced(Decimal("18.72")) - priced(Decimal("16.72")) == Decimal("14.40")


def test_tc10__an_allowance_larger_than_the_consumption_bills_zero_units_never_a_credit():
    """A negative quantity would walk the tiers backwards and price as a credit
    the programme never granted. The BASE charge is untouched — a customer who
    used less than their allowance still pays to be connected."""
    assert deduct("1.20", "2") == Decimal("0")


def test_tc11__an_allowance_exactly_equal_to_the_consumption_bills_zero():
    assert deduct("2", "2") == Decimal("0")


def test_tc12__a_service_with_no_read_still_has_no_billable_quantity():
    """`None` in, `None` out. An allowance cannot invent a reading."""
    assert deduct(None, "2") is None


def test_tc13__an_allowance_with_no_stated_unit_now_takes_the_services():
    """⚖️ **AMENDED 2026-08-31 — `BR-RAT-960`, and the superseded reading is kept
    in the test rather than deleted with it** (the shape `BR-RAT-094` used for
    the two tests its ruling overtook).

    **THIS TEST USED TO ASSERT A REFUSAL.** Until the PO ruled, an allowance that
    stated no unit was unusable — *"a usage-allowance discount on 'water' allows
    2 of SOMETHING"* — because `OQ-291` was open and no column held a unit. PO
    ruling 2026-08-31, verbatim: *"a) Take the unit from the service it's
    attached to"*. So the absent unit is no longer a refusal: it is the ORDINARY
    case, and it RESOLVES.

    `18.72 kgal` less a `2` allowance is `16.72 kgal`, and nothing had to say
    `kgal` on the discount for that to be true — the service did.
    """
    assert deduct("18.72", "2", allowance_unit=None) == Decimal("16.72")


def test_tc13b__a_service_that_states_no_unit_still_refuses():
    """**`BR-RAT-960`'s other half, and the reason hard rule 3 survives the
    ruling.** The PO gave the unit a SOURCE, not a DEFAULT. Four of the ten
    catalog services carry no stated unit, so an allowance attached to one has
    nothing to take — and it REFUSES rather than being handed a unit nobody
    chose, which is the assumption CLAUDE.md hard rule 3 forbids.

    The clerk's sentence carries the FACT and not any id (G28 / CR-016)."""
    with pytest.raises(resolution.UsageAllowanceUnusable) as refusal:
        resolution.allowance_deducted_quantity(
            "sewer", Decimal("18.72"), "", allowance=Decimal("2")
        )
    assert "has not stated what unit that service is measured in" in str(refusal.value)
    assert "sewer" in str(refusal.value)
    assert refusal.value.step == "R3b"


def test_tc14__two_free_kgal_cannot_be_taken_off_a_meter_read_in_kwh():
    """BR-RAT-038, *"no silent conversion"*, applied to a subtraction. This is
    `OQ-291`'s own worked failure: a water programme allowing 2 free kgal and an
    electric one allowing 2 free kWh are the same stored row today."""
    with pytest.raises(resolution.UsageAllowanceUnusable) as refusal:
        deduct("620", "2", allowance_unit="kgal", billed_unit="kWh")
    assert "'kgal'" in str(refusal.value) and "'kWh'" in str(refusal.value)


def test_tc15__a_negative_allowance_refuses_because_it_is_a_surcharge():
    with pytest.raises(resolution.UsageAllowanceUnusable):
        deduct("18.72", "-2")


# ══════════════════════════════════════════════════════════════════════════
# THE BOUNDARY — three things that must move together, and none of them here
# ══════════════════════════════════════════════════════════════════════════


def test_tc16__both_reads_are_ruled_now_and_neither_still_names_an_open_question():
    """⚖️ **AMENDED 2026-08-31 — BOTH QUESTIONS ARE CLOSED, AND THE TWO DOORS
    CLOSED IN OPPOSITE DIRECTIONS.** This test used to assert the prime
    directive's stub — *"implement up to the boundary and stub the gap as
    `raise NotImplementedError("OQ-###")`"* — on both. A person has now ruled,
    so an `OQ-###` here would be a lie about who is still deciding.

    **`usage_allowance_units` was ANSWERED** (`BR-RAT-960`, *"a) Take the unit
    from the service it's attached to"*): it returns the service's unit and no
    longer raises at all.

    **`rate_override_target` was DISSOLVED** (`BR-RAT-961`, *"sicne there is
    subsidy we dont change rate schedule"*): nothing needs the read, so it still
    refuses — but it names the RULING, not a question, and a lane that adds
    `override_tariff_id` to satisfy it is reversing a decision rather than
    finishing a stub.

    Asserted rather than left to a reader, so neither reason can quietly revert
    to the other."""
    with pytest.raises(NotImplementedError) as refusal:
        resolution.rate_override_target("SUBSIDY-RES")
    assert "BR-RAT-961" in str(refusal.value)
    assert "OQ-292" not in str(refusal.value)

    assert resolution.usage_allowance_units("water", "kgal") == "kgal"
    assert resolution.usage_allowance_units("electric", "kWh") == "kWh"


def test_tc17__neither_type_became_activatable_and_that_is_deliberate():
    """⚠ **THE ONE THING THIS TASK MUST NOT DO.**

    `DISCOUNT_TYPES_PRICEABLE` is the set an activation may use, and both types
    are deliberately still outside it. A `usage_allowance` that activated today
    would reach the LIVE pricing path — which is `engine.price_bill`, not this
    chain (`DEF-438`: R1–R7 has no production caller) — and
    `discount_pricing.price_discounts` would refuse it by name and break every
    bill for that account.

    Switching a step is the ruled cutover's step 5 and is gated on the PO's step
    4, which is CR-052 task 20 and has not happened. So: the arithmetic exists,
    the data cannot reach it, and the switch is somebody else's commit."""
    assert discount_models.DISCOUNT_RATE_OVERRIDE not in discount_models.DISCOUNT_TYPES_PRICEABLE
    assert discount_models.DISCOUNT_USAGE_ALLOWANCE not in discount_models.DISCOUNT_TYPES_PRICEABLE
    assert set(discount_models.DISCOUNT_TYPES_PRICEABLE) == {
        discount_models.DISCOUNT_PERCENTAGE,
        discount_models.DISCOUNT_FIXED_AMOUNT,
        discount_models.DISCOUNT_CHARGE_WAIVER,
    }


def test_tc18__no_r_step_was_switched_and_no_shadow_outcome_prices_anything():
    """CR-051's second hard rule, asserted rather than promised: the ordinary
    `resolve_schedule` and `billable_quantity` are untouched, so a caller that
    passes no override and no allowance gets byte-identical answers — which is
    what keeps the shadow comparison measuring what it measured yesterday."""
    catalogue = a_catalogue(a_version("v-std-1", STANDARD))
    plain = resolution.resolve_schedule(catalogue, PLAN, "water", SERVICE_DATE)
    through_override = resolution.resolve_schedule_with_override(
        catalogue, PLAN, "water", SERVICE_DATE
    )
    assert plain == through_override

    meter = resolution.MeterFacts(service="water", connection_size="5/8", multiplier=Decimal("1"))
    quantity = resolution.billable_quantity(meter, Decimal("18.72"))
    assert quantity == Decimal("18.72")
    assert resolution.allowance_deducted_quantity("water", quantity, "kgal") == quantity
