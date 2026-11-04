# ── Trace ──────────────────────────────────────────────
# Epics:    EP-RAT-15 (the resolution engine)
#           Screens: — (the chain is pure; its refusals surface on S31.3)
# Rules:    BR-RAT-001 (multiplier before tiers) · BR-RAT-007 (version in force
#           at the SERVICE date) · BR-MET-056 (the multiplier USED) ·
#           CR-013 part 1 (*"Blank base = size not served"*)
# Rulings:  PO 2026-08-19 — the meter multiplier and the inside/outside-city
#           factor are two different factors on opposite sides of pricing; a
#           plan cannot override a price; a stored 0.00 bills $0.00
# Tests:    this file IS EP-RAT-15's refusal suite (design §B4 tier 2)
# ───────────────────────────────────────────────────────
"""The narrowing, and every place it must REFUSE instead of coping.

Design §A0: *"Robustness here means refusing, not coping."* Every case below is
a place the chain could plausibly have picked a sensible default, and the whole
value of the module is that it does not. So the file is mostly `pytest.raises`,
which is unusual and is the point — a resolution chain is judged by what it
declines to answer.

⚠ THE TWO MULTIPLIERS ARE TESTED APART, AND THAT IS THE PO'S OWN CORRECTION.
`tc6` proves the METER multiplier scales the QUANTITY before tier boundaries are
walked (62 x 10 = 620 kWh, tier 2) and `tc8`/`tc9` prove the PREMISES factor
scales the MONEY after pricing and touches base charges as well as usage. A test
suite that only checked "the bill is bigger" would pass with the two swapped, and
swapping them is exactly the mistake the correction was issued for.
"""

from datetime import date
from decimal import Decimal

import pytest

from dataclasses import replace

from apps.rating import resolution as R

JUNE = date(2026, 6, 30)

RES = R.AccountFacts(account_no="A-1001", unit_id="U-1", customer_class="residential")
COMM = R.AccountFacts(account_no="A-2002", unit_id="U-2", customer_class="commercial")
INSIDE = R.PremisesFacts(inside_city_limits=True, county="Bexar")
OUTSIDE = R.PremisesFacts(inside_city_limits=False, county="Bexar")
UNRECORDED = R.PremisesFacts(inside_city_limits=None, county="Bexar")

ELECTRIC_METER = R.MeterFacts(service="electric", connection_size="1φ 100A")
WATER_METER = R.MeterFacts(service="water", connection_size='5/8"')


def plan(*services, plan_id="RES-STD", version=3, start=date(2026, 1, 1), end=None, binds=None):
    """A plan version. `binds` is service -> schedule id; by default each service
    binds the schedule named `SCH-<service>`, which is what `schedule()` mints."""
    return R.PlanVersion(
        plan_id=plan_id,
        version=version,
        services=tuple(services),
        effective_from=start,
        effective_to=end,
        schedules=binds if binds is not None else {code: f"SCH-{code}" for code in services},
    )


def schedule(
    service, *, version_id="TV-E1", tariff_id=None, sizes=None, start=date(2026, 1, 1), end=None
):
    return R.ScheduleVersion(
        version_id=version_id,
        service=service,
        tariff_id=tariff_id or f"SCH-{service}",
        effective_from=start,
        effective_to=end,
        size_rows=sizes if sizes is not None else {"1φ 100A": Decimal("18.50")},
    )


# ── R1 ──────────────────────────────────────────────────────────────────────


def test_cr013_r1_tc1__no_plan_in_force_refuses_rather_than_using_the_newest():
    """BR-RAT-007. A plan that ended in May does not price June, and the chain
    does not reach for it — a fallback to today's plan re-prices history."""
    catalogue = R.Catalogue(
        plan_versions=(plan("electric", start=date(2026, 1, 1), end=date(2026, 6, 1)),)
    )
    with pytest.raises(R.NoPlanInForce) as raised:
        R.resolve_plan(catalogue, RES, JUNE)
    assert raised.value.step == "R1"
    assert "BR-RAT-007" in str(raised.value)


def test_cr013_r1_tc2__two_plans_in_force_refuse_rather_than_picking():
    catalogue = R.Catalogue(
        plan_versions=(plan("electric"), plan("electric", plan_id="RES-ALT", version=1))
    )
    with pytest.raises(R.AmbiguousSchedule):
        R.resolve_plan(catalogue, RES, JUNE)


# ── R2 ──────────────────────────────────────────────────────────────────────


def test_cr013_r2_tc3__a_covered_service_with_no_schedule_refuses():
    """A service on the plan and no schedule bound to it is NOT a service that
    bills nothing — it is a configuration problem a human must see."""
    catalogue = R.Catalogue(
        plan_versions=(plan("electric", "water", binds={"electric": "SCH-electric"}),),
        schedule_versions=(schedule("electric"),),
    )
    with pytest.raises(R.NoScheduleForService):
        R.resolve_schedule(catalogue, catalogue.plan_versions[0], "water", JUNE)


def test_cr013_r2_tc4__two_versions_in_force_on_one_date_answer_the_newest():
    """Two VERSIONS of one schedule in force on one date.

    ⚠ **AMENDED 2026-10-01 — THIS CASE ASSERTED A REFUSAL (`AmbiguousSchedule`)
    UNTIL THE PO RULED ON `DEF-RAT-8004`**, option A, verbatim: *"we have to
    return only 1 row; A · Use the newest everywhere, and flag it on Check"*
    (`BR-RAT-1055`). R2 now answers through `pick_in_force`, the same function
    as the nightly run: newest `effective_from`, then newest `created_at`,
    then id. These two tie on the first two (a hand-built fact carries no
    `created_at`), so the higher id answers — and both still name ONE row.
    """
    catalogue = R.Catalogue(
        plan_versions=(plan("electric"),),
        schedule_versions=(schedule("electric"), schedule("electric", version_id="TV-E2")),
    )
    chosen = R.resolve_schedule(catalogue, catalogue.plan_versions[0], "electric", JUNE)
    assert chosen.version_id == "TV-E2"


# ── R3 — the three outcomes, and only one is a price ────────────────────────


def test_cr013_r3_tc5a__a_size_with_no_row_refuses():
    sched = schedule("water", sizes={'5/8"': Decimal("12.00")})
    meter = R.MeterFacts(service="water", connection_size='2"')
    with pytest.raises(R.SizeNotServed):
        R.resolve_size_row(sched, meter)


def test_cr013_r3_tc5b__a_BLANK_base_refuses__CR_013_part_1():
    """*"Blank base = size not served"* — DEF-277 made into law."""
    sched = schedule("water", sizes={'2"': None})
    meter = R.MeterFacts(service="water", connection_size='2"')
    with pytest.raises(R.SizeNotServed) as raised:
        R.resolve_size_row(sched, meter)
    assert "DEF-277" in str(raised.value)


def test_cr013_r3_tc5c__a_stored_zero_is_a_PRICE_and_bills_zero__PO_2026_08_19():
    """The PO's ruling, verbatim *"print $0.00"*. Zero is a price; blank is the
    absence of one. This assertion sits beside tc5b on purpose: the two together
    are the whole distinction, and a later reading that collapses them breaks
    one of them."""
    sched = schedule("water", sizes={'2"': Decimal("0")})
    meter = R.MeterFacts(service="water", connection_size='2"')
    assert R.resolve_size_row(sched, meter) == Decimal("0")


# ── R3b — the METER multiplier, on the QUANTITY, before tiers ───────────────


def test_cr013_r3b_tc6__the_meter_multiplier_scales_the_quantity_not_the_money():
    """The PO's correction, worked: a x10 register reading 62 is 620 kWh.

    620 lands in tier 2 of a 0–500 / 500+ schedule; 62 never leaves tier 1. The
    money-side alternative would price 62 kWh at tier-1 rates and multiply by
    ten — a different, wrong number that looks entirely plausible.
    """
    meter = R.MeterFacts(service="electric", connection_size="1φ 100A", multiplier=Decimal("10"))
    assert R.billable_quantity(meter, Decimal("62")) == Decimal("620")


def test_cr013_r3b_tc7__an_unstated_multiplier_refuses_rather_than_defaulting_to_one():
    """BR-MET-056 stores the factor USED. An absent factor is not 1 — it bills a
    tenth of the consumption on a document that looks entirely normal."""
    meter = R.MeterFacts(service="electric", connection_size="1φ 100A", multiplier=None)
    with pytest.raises(R.MeterMultiplierUnstated):
        R.billable_quantity(meter, Decimal("62"))


def test_cr013_r3b_tc7b__no_read_yields_no_quantity_rather_than_zero():
    """A zero would claim the meter was read and showed nothing."""
    assert R.billable_quantity(ELECTRIC_METER, None) is None


# ── R5 — the PREMISES factor, on the MONEY, after pricing ──────────────────


def test_cr013_r5_tc8__outside_city_scales_and_inside_city_does_not():
    catalogue = R.Catalogue(outside_city_factor=Decimal("1.5"))
    assert R.money_factor(catalogue, OUTSIDE, "electric") == Decimal("1.5")
    assert R.money_factor(catalogue, INSIDE, "electric") == Decimal("1")


def test_cr013_r5_tc9__an_exempt_service_is_flat_everywhere():
    """§A4 S2: *"BASE-S $8.00 (flat everywhere — the multiplier does NOT touch
    sewer)"*. Two things move in that scenario and sewer is neither of them."""
    catalogue = R.Catalogue(
        outside_city_factor=Decimal("1.5"), outside_city_exempt_services=("sewer",)
    )
    assert R.money_factor(catalogue, OUTSIDE, "water") == Decimal("1.5")
    assert R.money_factor(catalogue, OUTSIDE, "sewer") == Decimal("1")


def test_cr013_r5_tc10__an_unrecorded_premises_refuses_when_the_tenant_prices_by_one():
    catalogue = R.Catalogue(outside_city_factor=Decimal("1.5"))
    with pytest.raises(R.JurisdictionUnstated):
        R.money_factor(catalogue, UNRECORDED, "electric")


def test_cr013_r5_tc11__a_tenant_with_no_factor_never_consults_the_premises():
    """A tenant who does not price by jurisdiction must not have bills refused
    because a premises flag nobody needed was never filled in."""
    assert R.money_factor(R.Catalogue(), UNRECORDED, "electric") == Decimal("1")


# ── R4 — charge codes ──────────────────────────────────────────────────────


def test_cr013_r4_tc12__a_class_restricted_code_fires_only_for_that_class():
    """§A4 S3: *"`CAP-W` appears because the class is Commercial"*."""
    cap = R.ChargeCode(
        code="CAP-W",
        service="water",
        customer_classes=("commercial", "industrial"),
        # BR-RAT-730 (2026-08-28) — the TC is about the CLASS axis and is
        # unchanged. R4 gained a fourth axis, so a fixture that wants a code to
        # resolve at all must now say the code rides a periodic bill.
        charge_type="recurring",
        auto_apply=True,
        amounts={'2"': Decimal("120.00")},
    )
    catalogue = R.Catalogue(charge_codes=(cap,))
    sizes = {"water": '2"'}
    assert R.resolve_charge_codes(catalogue, COMM, ("water",), sizes) == ((cap, Decimal("120.00")),)
    assert R.resolve_charge_codes(catalogue, RES, ("water",), sizes) == ()


def test_cr013_r4_tc13__a_code_with_no_amount_for_the_size_refuses():
    code = R.ChargeCode(
        code="FIRE",
        service="water",
        charge_type="recurring",  # BR-RAT-730 — it rides, so the SIZE is what refuses
        auto_apply=True,
        amounts={'4"': Decimal("14.00")},
    )
    with pytest.raises(R.ChargeCodeAmountMissing):
        R.resolve_charge_codes(R.Catalogue(charge_codes=(code,)), RES, ("water",), {"water": '8"'})


def test_cr013_r4_tc14__a_code_stating_both_a_flat_and_a_per_size_table_refuses():
    code = R.ChargeCode(
        code="BASE-W",
        service="water",
        # BR-RAT-088 — a base code rides without the two flags (BR-RAT-730), so
        # the BOTH-BASES refusal below is still what this TC reaches.
        is_base=True,
        flat_amount=Decimal("12.00"),
        amounts={'5/8"': Decimal("12.00")},
    )
    with pytest.raises(R.ChargeCodeAmountMissing):
        R.resolve_charge_codes(
            R.Catalogue(charge_codes=(code,)), RES, ("water",), {"water": '5/8"'}
        )


# ── R6 — the named gap ─────────────────────────────────────────────────────


def test_cr013_r6_tc15__an_account_enrolled_in_nothing_is_a_TRUE_empty_not_a_refusal():
    """⚠ **THIS TEST ASSERTED THE OPPOSITE UNTIL 2026-08-20 (DEF-361).**

    It read `modelled is False` and looked for *"EP-RAT-12"* in a refusal, because
    when it was written the discounts table genuinely did not exist. Migration
    `0009_cr013_discounts` landed six tables and the stub went on refusing with a
    reason that had become false — and this test kept it green, which is how a
    stub outlives the thing it apologises for.

    The distinction the old test protected is still the one that matters and it
    has simply changed sides: an empty `applied` is now a TRUE statement about
    the ACCOUNT (*enrolled in nothing*) instead of a stand-in for one about the
    PRODUCT (*cannot express discounts*).
    """
    resolved = R.resolve_discounts(R.Catalogue(), RES)
    assert resolved.modelled is True
    assert resolved.applied == ()
    # The empty answer is usable now — it does not raise, and it totals to zero.
    assert resolved.total() == Decimal("0")
    assert R.require_discounts(resolved) == ()


def test_cr013_r6_tc15b__enrolments_resolve_in_PRECEDENCE_order_not_arrival_order():
    """CR-013 part 3: *"stacking precedence, explicit because percentage-of-usage
    after a usage allowance gives a different number than the reverse."* Order is
    DATA. Silver Creek runs all four of these on the same accounts, so precedence
    is live from day one rather than a future concern.

    The enrolment tuple is deliberately in the WRONG order here — if R6 returned
    arrival order this test fails, which is the whole point.
    """
    catalogue = R.Catalogue(
        discounts=(
            R.DiscountRule(code="AUTOPAY", value=Decimal("0.005"), precedence=30),
            R.DiscountRule(code="SENIOR", value=Decimal("0.15"), precedence=10),
            R.DiscountRule(code="PAPERLESS", value=Decimal("1.00"), precedence=20),
        )
    )
    account = replace(RES, enrolments=("AUTOPAY", "PAPERLESS", "SENIOR"))
    resolved = R.resolve_discounts(catalogue, account)
    assert resolved.modelled is True
    assert resolved.applied == (
        ("SENIOR", Decimal("0.15")),
        ("PAPERLESS", Decimal("1.00")),
        ("AUTOPAY", Decimal("0.005")),
    )


def test_cr013_r6_tc15c__an_enrolment_the_catalogue_does_not_offer_is_DROPPED_not_guessed():
    """*"Plan attachment makes a discount available, not granted"* (part 3), read
    from the other end: an account enrolled in something no configured object
    offers has a mismatch, and inventing a value for it would reduce a bill by a
    figure nothing states.
    """
    catalogue = R.Catalogue(discounts=(R.DiscountRule(code="SENIOR", value=Decimal("0.15")),))
    account = replace(RES, enrolments=("SENIOR", "VETERAN"))
    resolved = R.resolve_discounts(catalogue, account)
    assert resolved.applied == (("SENIOR", Decimal("0.15")),)


# ── BR-RAT-081 — the metered/unmetered declaration (DEF-161's fix) ──────────


def _trash_catalogue(*, unmetered):
    """A plan covering ONE service with a schedule bound and no meter anywhere.

    This is DEF-161's exact shape: *"a plan carrying any non-metered service
    cannot be billed at all, because the run demands a meter."*
    """
    return R.Catalogue(
        plan_versions=(plan("trash"),),
        schedule_versions=(schedule("trash", version_id="TV-T1"),),
        unmetered_services=("trash",) if unmetered else (),
    )


def test_br_rat_081_tc1__an_UNDECLARED_service_with_no_meter_still_refuses_as_before():
    """The default is unchanged, and deliberately so. Every service this product
    has billed to date is metered, so a tenant that declares nothing keeps
    today's behaviour exactly — the unsafe option is the one you type."""
    with pytest.raises(R.SizeNotServed) as raised:
        R.resolve(
            catalogue=_trash_catalogue(unmetered=False),
            account=RES,
            premises=INSIDE,
            meters=(),
            service_date=JUNE,
        )
    # And the refusal now TELLS the tenant the way out, which it did not before.
    assert "BR-RAT-081" in str(raised.value)


def test_br_rat_081_tc2__a_DECLARED_unmetered_service_stops_demanding_a_meter():
    """DEF-161's fix, and it is GENERAL — nothing here mentions trash carts.

    ⚠ **AMENDED 2026-08-21 — OQ-283 IS CLOSED (BR-RAT-090, option A).** This TC
    used to assert a `NotImplementedError` naming OQ-283, which was right while
    the quantity source was unruled: BR-RAT-081 ruled only the DECLARATION and a
    lane must never choose what a customer is charged. The PO then ruled the
    count, so the stub is gone.

    What this TC has always been for survives unchanged and is what it still
    asserts: **the wrong refusal — the demand for a meter — must not come
    back.** A caller that supplies no asset count is now told what IS missing,
    and the message names the declaration so a tenant can act on it.
    """
    with pytest.raises(R.AssetCountUnavailable) as raised:
        R.resolve(
            catalogue=_trash_catalogue(unmetered=True),
            account=RES,
            premises=INSIDE,
            meters=(),
            service_date=JUNE,
        )
    assert "BR-RAT-081" in str(raised.value)
    # The point of the assertion below, unchanged since this TC was written: if
    # a later change reinstates the meter demand for a declared-unmetered
    # service, this goes red on the substitution rather than on the message.
    assert not isinstance(raised.value, R.SizeNotServed)


def test_br_rat_081_tc3__declaring_ONE_service_unmetered_does_not_touch_the_others():
    """The declaration is per service, so a tenant selling metered water and
    unmetered trash must still get its water bill priced normally."""
    catalogue = R.Catalogue(
        plan_versions=(plan("water"),),
        schedule_versions=(
            schedule("water", version_id="TV-W1", sizes={'5/8"': Decimal("12.00")}),
        ),
        unmetered_services=("trash",),
    )
    resolved = R.resolve(
        catalogue=catalogue,
        account=RES,
        premises=INSIDE,
        meters=(WATER_METER,),
        service_date=JUNE,
    )
    assert resolved.service("water").base_charge == Decimal("12.00")


# ── R7 — attachment, never selection ───────────────────────────────────────


def test_cr013_r7_tc16__class_and_jurisdiction_each_change_the_tax_set_alone():
    """§A4's whole point: three selectors each moved the answer on their own.

    State Utility is Commercial+Industrial only; City Franchise is electric and
    inside-city. Residential inside city fires one of the two; Commercial
    outside city fires the other.
    """
    state = R.TaxRule(
        code="TX State Utility",
        rate=Decimal("0.0625"),
        customer_classes=("commercial", "industrial"),
    )
    franchise = R.TaxRule(
        code="City Franchise",
        rate=Decimal("0.015"),
        services=("electric",),
        inside_city_only=True,
    )
    catalogue = R.Catalogue(taxes=(state, franchise))

    inside_res = R.resolve_taxes(catalogue, RES, INSIDE, ("electric", "water"))
    outside_comm = R.resolve_taxes(catalogue, COMM, OUTSIDE, ("electric", "water"))

    assert [rule.code for rule in inside_res] == ["City Franchise"]
    assert [rule.code for rule in outside_comm] == ["TX State Utility"]


def test_cr013_r7_tc17__a_service_restricted_tax_does_not_attach_to_a_bill_without_it():
    """§A4 S4 is electric-only and still fires the franchise fee; a water-only
    bill does not. The outcome of a failed condition is NO LINE, never a zero
    one (DEF-273) — a $0.00 tax line claims the authority charges nothing."""
    franchise = R.TaxRule(code="City Franchise", rate=Decimal("0.015"), services=("electric",))
    catalogue = R.Catalogue(taxes=(franchise,))
    assert R.resolve_taxes(catalogue, RES, INSIDE, ("electric",)) == (franchise,)
    assert R.resolve_taxes(catalogue, RES, INSIDE, ("water",)) == ()


def test_cr013_r7_tc18__an_account_with_no_recorded_class_does_not_match_a_restricted_rule():
    """DEF-273's fail-safe direction: under-charging is recoverable, and
    over-charging a customer who is exempt is not."""
    state = R.TaxRule(
        code="TX State Utility", rate=Decimal("0.0625"), customer_classes=("commercial",)
    )
    unknown = R.AccountFacts(account_no="A-9", unit_id="U-9", customer_class=None)
    assert R.resolve_taxes(R.Catalogue(taxes=(state,)), unknown, INSIDE, ("electric",)) == ()


# ── The whole chain ────────────────────────────────────────────────────────


def test_cr013_chain_tc19__resolve_narrows_a_whole_bill_in_one_pass():
    catalogue = R.Catalogue(
        plan_versions=(plan("electric", "water"),),
        schedule_versions=(
            schedule("electric", version_id="TV-E1", sizes={"1φ 100A": Decimal("18.50")}),
            schedule("water", version_id="TV-W1", sizes={'5/8"': Decimal("12.00")}),
        ),
        taxes=(R.TaxRule(code="Bexar County", rate=Decimal("0.02")),),
        outside_city_factor=Decimal("1.5"),
        outside_city_exempt_services=("sewer",),
    )
    resolved = R.resolve(
        catalogue=catalogue,
        account=RES,
        premises=OUTSIDE,
        meters=(ELECTRIC_METER, WATER_METER),
        quantities={"electric": Decimal("840"), "water": Decimal("11")},
        service_date=JUNE,
    )

    assert resolved.plan.plan_id == "RES-STD"
    assert resolved.service("electric").schedule_version_id == "TV-E1"
    assert resolved.service("water").base_charge == Decimal("12.00")
    assert resolved.service("electric").money_factor == Decimal("1.5")
    assert resolved.service("electric").billable_quantity == Decimal("840")
    assert [rule.code for rule in resolved.taxes] == ["Bexar County"]
    # DEF-361: this read `modelled is False` until 2026-08-20. The catalogue in
    # this case configures no discounts, so the account is enrolled in nothing
    # and the TRUE answer is a modelled empty — not a refusal.
    assert resolved.discounts.modelled is True
    assert resolved.discounts.applied == ()


def test_cr013_chain_tc20__a_plan_service_with_no_meter_refuses():
    catalogue = R.Catalogue(
        plan_versions=(plan("electric", "water"),),
        schedule_versions=(schedule("electric"), schedule("water", version_id="TV-W1")),
    )
    with pytest.raises(R.SizeNotServed):
        R.resolve(
            catalogue=catalogue,
            account=RES,
            premises=INSIDE,
            meters=(ELECTRIC_METER,),
            service_date=JUNE,
        )


# ── DEF-360 · the schedule's own per-size money (CR-013 P1) ─────────────────
#
# r10's rate matrix is `size · base · min · t1 · t2 · t3` and THREE of those
# columns vary by size. §B3's table list named only ONE of the three, so building
# it exactly as written still could not price r10's 2" water row.


def test_def_360_tc1__the_two_inch_row_prices_its_own_tiers():
    """THE case that settles why the SCHEDULE needs a size axis at all.

    Residential Water prices four sizes at 3.20 / 4.80 / 7.20 and prices 2" at
    3.45 / 5.10 / 7.70. That cannot be derived from a base, a multiplier or the
    size — only a row on the schedule can say it.
    """
    default = (Decimal("3.20"), Decimal("4.80"), Decimal("7.20"))
    sched = schedule("water", sizes={'5/8"': Decimal("12.00"), '2"': Decimal("64.00")})
    sched = R.replace(
        sched, tiers_by_size={'2"': (Decimal("3.45"), Decimal("5.10"), Decimal("7.70"))}
    )

    small = R.MeterFacts(service="water", connection_size='5/8"')
    large = R.MeterFacts(service="water", connection_size='2"')

    assert R.resolve_tiers(sched, small, default) == default
    assert R.resolve_tiers(sched, large, default) == (
        Decimal("3.45"),
        Decimal("5.10"),
        Decimal("7.70"),
    )


def test_def_360_tc2__a_schedule_states_the_exception_not_the_rule():
    """Four of r10's five water sizes say nothing about tiers. A schedule with
    no per-size entries at all must price every size the way it always has —
    which is what makes this column additive rather than a migration."""
    default = (Decimal("3.20"), Decimal("4.80"), Decimal("7.20"))
    sched = schedule("water", sizes={'5/8"': Decimal("12.00")})
    meter = R.MeterFacts(service="water", connection_size='5/8"')
    assert R.resolve_tiers(sched, meter, default) == default


def test_def_360_tc3__minimum_bill_falls_back_to_the_versions_scalar():
    """Every schedule written before P1 carries only the scalar, so it must keep
    pricing identically. The fallback IS the backward-compatibility guarantee."""
    sched = R.replace(
        schedule("water", sizes={'5/8"': Decimal("12.00")}),
        minimum_bill=Decimal("18.00"),
    )
    meter = R.MeterFacts(service="water", connection_size='5/8"')
    assert R.resolve_minimum_bill(sched, meter) == Decimal("18.00")


def test_def_360_tc4__a_named_size_with_NO_minimum_is_not_the_scalar_and_not_zero():
    """r10 draws an em-dash for the minimum on EVERY electric size while water
    carries one. A size named with None says 'no minimum here' and must not
    inherit the version's scalar — absent is not zero, and it is not 18.00
    either."""
    sched = R.replace(
        schedule("electric", sizes={"1φ 100A": Decimal("18.50")}),
        minimum_bill=Decimal("18.00"),
        minimum_bill_by_size={"1φ 100A": None},
    )
    meter = R.MeterFacts(service="electric", connection_size="1φ 100A")
    assert R.resolve_minimum_bill(sched, meter) is None


# ── BR-RAT-088 · the CHARGE CODE owns the base (CR-013 P1b) ────────────────


def _code(code, *, service, is_base=False, flat=None, amounts=None):
    return R.ChargeCode(
        code=code,
        service=service,
        is_base=is_base,
        flat_amount=flat,
        amounts=amounts or {},
    )


def test_br_rat_088_tc1__the_base_comes_from_the_code_that_DECLARES_it():
    """Not from the code's NAME. A tenant may call theirs anything, and matching
    `BASE-<service>` fails silently — it produces a bill with no base rather
    than an error, which is the worst of both."""
    resolved = (
        (_code("SERVICE-CHG", service="water", is_base=True), Decimal("12.00")),
        (_code("TAP-W", service="water"), Decimal("850.00")),
    )
    # ⚠ AMENDED 2026-10-06 (`DEF-RAT-9832`, PO ruling): a code that merely
    # DECLARES itself the base prices nothing unless the schedule NAMES it —
    # *"if it is not provided then you will take it zeo"*. Named, it is the base.
    with pytest.raises(R.BaseChargeNotBound):
        R.resolve_base_charge(resolved, "water")
    assert R.resolve_base_charge(resolved, "water", "SERVICE-CHG") == Decimal("12.00")


def test_br_rat_088_tc2__a_base_belongs_to_ONE_service():
    """A plan covering water and electric carries two base codes, and each
    service must get its own. Picking the first `is_base` code on the plan would
    bill every service the water base."""
    resolved = (
        (_code("BASE-W", service="water", is_base=True), Decimal("12.00")),
        (_code("BASE-E", service="electric", is_base=True), Decimal("18.50")),
    )
    # `DEF-RAT-9832` (2026-10-06): each schedule NAMES its service's code.
    assert R.resolve_base_charge(resolved, "water", "BASE-W") == Decimal("12.00")
    assert R.resolve_base_charge(resolved, "electric", "BASE-E") == Decimal("18.50")


def test_br_rat_088_tc3__no_base_code_is_None_and_that_is_NOT_zero():
    """§A3 makes a missing base an ACTIVATION gate — *"refused, naming the
    service"* — not a billing-time guess. Returning 0.00 here would bill a
    customer nothing for a base the utility does charge, and every row would
    look correct."""
    resolved = ((_code("TAP-W", service="water"), Decimal("850.00")),)
    assert R.resolve_base_charge(resolved, "water") is None


def test_br_rat_088_tc4__an_account_level_code_is_never_a_base():
    """`service is None` is CR-013 part 2's *"Any"* — late fees and NSF belong to
    the ACCOUNT. One flagged `is_base` with no service must not answer for a
    service that has no base of its own."""
    resolved = ((_code("LATE", service=None, is_base=True), Decimal("5.00")),)
    assert R.resolve_base_charge(resolved, "water") is None


# ── BR-RAT-088 · the HELPER's own cases (the chain is proved elsewhere) ────
#
# ⚠ THESE DO NOT PROVE THE FLIP AND ARE NO LONGER NAMED AS THOUGH THEY DO.
# I first wrote five cases here called `..._flip__...`, then reverted the flip in
# `resolve()` to prove them RED (law 7). **All five still passed** — they call
# `resolve_base_charge` directly, which the revert never touched. A check whose
# output cannot distinguish pass from fail is worse than no check, because it is
# trusted. The chain-level proof lives in `test_br_rat_088_flip.py`, where
# reverting the flip does turn a case red.


def test_r3_still_refuses_an_unserved_size():
    """The flip moved the PRICE, not the GATE. A size the schedule never priced
    still stops the bill."""
    schedule = R.ScheduleVersion(
        version_id="v1", service="water", size_rows={'5/8"': Decimal("12.00")}
    )
    meter = R.MeterFacts(service="water", connection_size='2"', multiplier=None)
    with pytest.raises(R.SizeNotServed):
        R.resolve_size_row(schedule, meter)


def test_r3_still_refuses_a_blank_base():
    """DEF-277 unchanged: a size PRESENT with a blank is data — *this size is not
    served* — and is never $0.00."""
    schedule = R.ScheduleVersion(version_id="v1", service="water", size_rows={'2"': None})
    meter = R.MeterFacts(service="water", connection_size='2"', multiplier=None)
    with pytest.raises(R.SizeNotServed):
        R.resolve_size_row(schedule, meter)


# ── BR-RAT-090 — CR-019, the unmetered QUANTITY (OQ-283 closed) ─────────────
#
# PO ruling 2026-08-20, option A, verbatim: *"an unmetered service's quantity is
# a COUNT OF ITS ASSETS ON THE UNIT"*, observed and never typed. The worked
# figure the PO ratified: **3 carts x $15.00 = $45.00; remove one and the next
# bill is $30.00.**
#
# These TCs price the QUANTITY, not the money — R3b's output is a quantity and
# the tier walk that turns it into money is B4's, tested by the golden harness.
# What is asserted here is the number that ENTERS pricing, because that is the
# number BR-RAT-090 rules on.


def _cart_catalogue(sizes=None):
    """Silver Creek's trash service: declared unmetered, priced per cart."""
    return R.Catalogue(
        plan_versions=(plan("trash"),),
        schedule_versions=(
            schedule("trash", version_id="TV-T1", sizes=sizes if sizes is not None else {}),
        ),
        unmetered_services=("trash",),
        # BR-RAT-088: the base lives on the charge code. `$0.00` is a PRICE
        # here — Silver Creek charges nothing to have trash service and bills
        # only for the carts — where a BLANK would be the absence of one.
        charge_codes=(
            R.ChargeCode(code="BASE-T", service="trash", is_base=True, flat_amount=Decimal("0.00")),
        ),
    )


def _resolve_carts(count, *, size_class=None, sizes=None):
    return R.resolve(
        catalogue=_cart_catalogue(sizes),
        account=RES,
        premises=INSIDE,
        meters=(),
        asset_counts=(R.AssetCountFacts("trash", count=count, size_class=size_class),),
        service_date=JUNE,
    )


def test_br_rat_090_tc1__three_carts_is_a_billable_quantity_of_three():
    """THE ratified figure. Three carts at $15.00 must bill $45.00, and the way
    that happens is that R3b hands pricing a quantity of exactly 3."""
    line = _resolve_carts(3).service("trash")
    assert line.billable_quantity == Decimal("3")
    # x $15.00 per cart = $45.00, the figure the PO ratified.
    assert line.billable_quantity * Decimal("15.00") == Decimal("45.00")


def test_br_rat_090_tc2__removing_a_cart_changes_the_next_bill_by_itself():
    """The second half of the same ratified figure — and the point of option A.

    Nobody edited a plan, an account or a typed quantity between these two
    calls. The asset count changed in the field and the bill followed, which is
    exactly why option B (a `quantity` column on the plan's service line) was
    rejected: a typed number can disagree silently with the carts in the street.
    """
    assert _resolve_carts(3).service("trash").billable_quantity == Decimal("3")
    assert _resolve_carts(2).service("trash").billable_quantity == Decimal("2")
    assert Decimal("2") * Decimal("15.00") == Decimal("30.00")


def test_br_rat_090_tc3__a_count_of_zero_is_an_ANSWER_and_bills():
    """`0` says the utility looked and this unit has no carts. That is a real
    fact and it prices to nothing for carts, while the base still applies."""
    line = _resolve_carts(0).service("trash")
    assert line.billable_quantity == Decimal("0")


def test_br_rat_090_tc4__a_count_that_could_not_be_determined_REFUSES():
    """The rule's own words: *"it REFUSES rather than defaults exactly as the
    metered branch does."* `None` and `0` are different facts, and reading the
    first as the second bills a three-cart household for none — on a document
    that looks entirely normal."""
    with pytest.raises(R.AssetCountUnavailable) as raised:
        _resolve_carts(None)
    assert "BR-RAT-090" in str(raised.value)


def test_br_rat_090_tc5__an_unmetered_service_with_NO_asset_row_at_all_refuses():
    """An absent row is 'nobody looked', which is not 'this unit has none'."""
    with pytest.raises(R.AssetCountUnavailable) as raised:
        R.resolve(
            catalogue=_cart_catalogue(),
            account=RES,
            premises=INSIDE,
            meters=(),
            asset_counts=(),
            service_date=JUNE,
        )
    assert "BR-RAT-081" in str(raised.value)


def test_br_rat_090_tc6__the_line_records_that_its_quantity_came_from_a_COUNT():
    """A metered and an unmetered quantity look identical on the document — both
    are just a number — so the line says which it is, for the same reason
    `base_source` exists (BR-RAT-088)."""
    assert _resolve_carts(3).service("trash").quantity_source == "asset_count"


def test_br_rat_090_tc7__no_multiplier_is_applied_to_a_COUNT():
    """R3b's metered half scales a register difference because a reading is a
    scaled number — 62 on a x10 register is 620 kWh. A cart count is scaled by
    nothing: three carts are three carts. The absence is asserted so a later
    reader does not 'restore' a factor no ruling mentions."""
    line = _resolve_carts(3).service("trash")
    assert line.meter_multiplier == Decimal("1")
    assert line.billable_quantity == Decimal("3")


def test_br_rat_090_tc8__a_negative_count_is_refused():
    """A count is a number of physical things. A negative one would price as a
    credit against a customer nobody authorised."""
    with pytest.raises(R.AssetCountUnavailable):
        _resolve_carts(-1)


def test_br_rat_090_tc9__carts_may_be_priced_by_their_SIZE_CLASS():
    """A1 §S76 lists **carts** among `service_size_classes`, so a 96-gallon cart
    can be priced differently from a 35-gallon one. Where the assets state a
    class, R3 resolves the schedule row for it exactly as a meter's connection
    size does — same lookup, same two refusals."""
    line = _resolve_carts(
        3, size_class="96 gal", sizes={"96 gal": Decimal("4.00"), "35 gal": Decimal("2.50")}
    ).service("trash")
    assert line.connection_size == "96 gal"
    assert line.billable_quantity == Decimal("3")


def test_br_rat_090_tc10__an_unpriced_cart_size_refuses_exactly_as_a_meter_size_does():
    """DEF-277, reached from the unmetered side: a size the utility has never
    priced stops the bill rather than billing $0.00 for it."""
    with pytest.raises(R.SizeNotServed):
        _resolve_carts(3, size_class="64 gal", sizes={"96 gal": Decimal("4.00")})


def test_br_rat_090_tc11__the_metered_path_is_untouched_by_any_of_this():
    """The whole change is additive. A metered service still goes through R3's
    size row and R3b's multiplier, and still records `read` as its source."""
    catalogue = R.Catalogue(
        plan_versions=(plan("water"),),
        schedule_versions=(
            schedule("water", version_id="TV-W1", sizes={'5/8"': Decimal("12.00")}),
        ),
    )
    line = R.resolve(
        catalogue=catalogue,
        account=RES,
        premises=INSIDE,
        meters=(WATER_METER,),
        quantities={"water": Decimal("11")},
        service_date=JUNE,
    ).service("water")
    assert line.quantity_source == "read"
    assert line.billable_quantity == Decimal("11")
    assert line.base_charge == Decimal("12.00")


# ── DEF-468 · one base charge must survive the narrowing, or the bill refuses ──


def _base(code, service, amount, classes=()):
    return R.ChargeCode(
        code=code,
        service=service,
        is_base=True,
        flat_amount=Decimal(amount),
        customer_classes=classes,
    )


def _priced(*codes, named=None):
    version = schedule("water", version_id="TV-W1", sizes={'5/8"': Decimal("99.00")})
    if named is not None:
        version = R.replace(version, base_charge_code=named)
    catalogue = R.Catalogue(
        plan_versions=(plan("water"),),
        schedule_versions=(version,),
        charge_codes=codes,
    )
    return R.resolve(
        catalogue=catalogue,
        account=RES,
        premises=INSIDE,
        meters=(WATER_METER,),
        service_date=JUNE,
    )


def test_def_468__two_base_codes_for_one_service_REFUSE_rather_than_taking_the_first():
    """The PO's own case: *"based on Asset and Account type you will have select
    1 base charge out of so many charges … then you need to derive which base
    rate to select."*

    This used to `return` on the first match, so the customer was billed by
    CATALOGUE ORDER. Nothing in the schema prevents two — `charges.is_base` is a
    bare boolean with no uniqueness constraint — so the chain is the only place
    it can be caught.

    ⚠ AMENDED 2026-10-06 (`DEF-RAT-9832`, PO ruling): neither is taken and
    nothing refuses — a schedule naming no code bills `$0` (`not_set`), and a
    schedule naming one bills exactly that one. Catalogue order still decides
    nothing, which was the point.
    """
    line = _priced(_base("BASE-W", "water", "8.00"), _base("BASE-W-ALT", "water", "15.00")).service("water")
    assert (line.base_charge, line.base_source) == (Decimal("0"), "not_set")
    named = _priced(
        _base("BASE-W", "water", "8.00"), _base("BASE-W-ALT", "water", "15.00"), named="BASE-W-ALT"
    ).service("water")
    assert named.base_charge == Decimal("15.00")


def test_def_468__ORDER_DOES_NOT_DECIDE_and_that_is_the_whole_point():
    """The same two codes, listed the other way round, answer identically.

    If this ever passes with a price instead, the first-match has come back and
    a customer is being billed $8.00 or $15.00 depending on tuple order.
    (`DEF-RAT-9832`, 2026-10-06: the identical answer is now `$0` not-set.)
    """
    for pair in (
        (_base("A-BASE", "water", "8.00"), _base("Z-BASE", "water", "15.00")),
        (_base("Z-BASE", "water", "15.00"), _base("A-BASE", "water", "8.00")),
    ):
        line = _priced(*pair).service("water")
        assert (line.base_charge, line.base_source) == (Decimal("0"), "not_set")


def test_def_468__CUSTOMER_CLASS_IS_WHAT_MAKES_THE_CHOICE_UNAMBIGUOUS():
    """Two base codes for one service are FINE when the narrowing separates
    them — which is the shape BR-RAT-088's migration needs.

    Silver Creek's water base is `$8.00` residential and `$15.00` commercial.
    Scoped by class, exactly one survives R4 and the bill is decided by the
    ACCOUNT rather than by the catalogue.
    """
    codes = (
        _base("BASE-W-RES", "water", "8.00", classes=("residential",)),
        _base("BASE-W-COM", "water", "15.00", classes=("commercial",)),
    )
    # ⚠ AMENDED 2026-10-06 (`DEF-RAT-9832`, PO ruling): the class no longer
    # PICKS a code — that is the pool the ruling retires (*"you cannot take
    # W-COM because it is availabel in charge coede"*). Unnamed: `$0`.
    line = _priced(*codes).service("water")
    assert (line.base_charge, line.base_source) == (Decimal("0"), "not_set")
    # Named: the schedule's code, for the account it reaches.
    line = _priced(*codes, named="BASE-W-RES").service("water")
    assert line.base_charge == Decimal("8.00")  # RES is a residential account
    assert line.base_source == "named_charge_code"


def test_def_468__exactly_one_base_code_still_prices_as_before():
    """The unambiguous case — `DEF-RAT-9832` (2026-10-06): only when the
    schedule NAMES it; unnamed, even a single code prices nothing."""
    line = _priced(_base("BASE-W", "water", "8.00"), named="BASE-W").service("water")
    assert line.base_charge == Decimal("8.00")
    assert line.base_source == "named_charge_code"
    line = _priced(_base("BASE-W", "water", "8.00")).service("water")
    assert (line.base_charge, line.base_source) == (Decimal("0"), "not_set")


def test_def_468__no_base_code_at_all_still_falls_back_to_the_schedule():
    """BR-RAT-088's deliberate fallback: a tenant that has not declared a base
    code keeps billing from the schedule's size row, and the LINE RECORDS which
    answered. Refusing here would stop every bill for every existing tenant the
    day the flip shipped."""
    line = _priced().service("water")
    assert line.base_charge == Decimal("99.00")
    assert line.base_source == "schedule"
