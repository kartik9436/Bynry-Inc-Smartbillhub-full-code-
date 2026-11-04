# ── Trace ──────────────────────────────────────────────
# Rulings: PO 2026-08-31, decision log "FIVE PO RULINGS IN ONE REPLY" §3 and §4.
#          §3 verbatim: "a) Take the unit from the service it's attached to"
#            -> BR-RAT-960, closing OQ-291.
#          §4 verbatim: "we will apply standard rate and also provdie discount -
#            thats how it should be handled; sicne there is subsidy we dont
#            change rate schedule"
#            -> BR-RAT-961, closing OQ-292.
# Rules:   BR-RAT-960 (the allowance's unit; a one-service discount) ·
#          BR-RAT-961 (a subsidy is standard schedule + discount line) ·
#          BR-RAT-962 (neither type became priceable, and the reason changed) ·
#          BR-RAT-068 (a discount is an overlay, never a rate) ·
#          BR-RAT-038 (no silent conversion) · CLAUDE.md hard rule 3
# Golden:  10-scripts/03-golden-verify.py — 33 PASS / 0 FAIL before AND after.
#          Nothing here moves a bill; see TC15/TC16 for why that is the correct
#          outcome rather than an unfinished one.
# ───────────────────────────────────────────────────────
"""The two discount rulings of 2026-08-31, and the arithmetic that proves them.

**WHAT THE PO WAS ASKED AND WHAT THEY ANSWERED, because the difference is the
reason both rulings are worth a test file of their own.**

On the ALLOWANCE we asked where a unit should be stored and recommended a
column. The PO said take it from the service. **We were overruled, and the
overruled argument still constrains the code**: CLAUDE.md hard rule 3 is
*"consumption: always with an explicit unit; never assume"*, so the ruling had
to give the unit a SOURCE without giving it a DEFAULT. TC1–TC4 are that
distinction.

On the SUBSIDY we offered three ways to record which schedule a rate override
swaps to. The PO answered the business question underneath instead: a subsidy is
not a different rate table. TC10–TC14 are that, and TC12 is the one that shows
WHY the PO's answer is better than any of ours — a discount line is visible on
the bill and a swapped schedule is not.

**AND TC15/TC16 ARE THE MOST IMPORTANT TESTS HERE.** Closing two questions that
blocked two discount types looks exactly like permission to make those types
priceable. It is not, and the reason is arithmetic rather than process: R6
subtracts MONEY and an allowance deducts UNITS, so admitting `usage_allowance`
to `DISCOUNT_TYPES_PRICEABLE` would take `$2.00` off a bill where the ruling
takes `$14.40`.
"""

from datetime import date
from decimal import Decimal

import pytest

from apps.rating import discount_services, resolution, selectors
from apps.rating import discounts as discount_models
from core import errors

from tests.test_cr166_usage_allowance_not_offered import saved_before_the_ruling
from tests.test_us_rat_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_rat_helpers import tenant_ctx

# ⚠ PO ruling 2026-10-03 (decision log, option b): a NEW usage allowance is
# refused by name (`rating.discounts.usage_allowance_not_offered`). The read
# cases below (TC8, TC9, TC9b, TC16) are about a row that EXISTS, so they build
# it the way one saved before the ruling is stored — `saved_before_the_ruling`.

pytestmark = pytest.mark.django_db


# The seeded catalogue, to the digit — `tests/test_us_rat_helpers` owns both.
WATER_TIERS = ((Decimal("5"), Decimal("3.20")), (Decimal("10"), Decimal("4.80")), (None, Decimal("7.20")))
ELECTRIC_TIERS = (
    (Decimal("500"), Decimal("0.11")),
    (Decimal("500"), Decimal("0.14")),
    (None, Decimal("0.19")),
)


def priced(quantity: Decimal, tiers) -> Decimal:
    """The tier walk, half-up to 2dp at the end (B4 §Rounding — round at
    finalization, never mid-calculation)."""
    remaining, total = quantity, Decimal("0")
    for span, rate in tiers:
        take = remaining if span is None or remaining < span else span
        total += take * rate
        remaining -= take
        if remaining <= 0:
            break
    return total.quantize(Decimal("0.01"))


# ══════════════════════════════════════════════════════════════════════════
# RULING 3 · THE ALLOWANCE TAKES ITS UNIT FROM ITS SERVICE  (BR-RAT-960)
# ══════════════════════════════════════════════════════════════════════════


def test_tc1__the_unit_is_the_services_own():
    """PO verbatim: *"a) Take the unit from the service it's attached to"*."""
    assert resolution.usage_allowance_units("water", "kgal") == "kgal"
    assert resolution.usage_allowance_units("electric", "kWh") == "kWh"


def test_tc2__the_same_stored_row_is_worth_14_40_on_water_and_0_28_on_electric():
    """⚖️ **THE RULING IN TWO NUMBERS, AND THE FAILURE IT REMOVES.**

    `discount_versions.value = 2` is ONE stored row. No column says what the 2
    is 2 OF. Resolved against the service it is attached to:

        water     18.72 kgal -> 16.72 kgal    90.78 -> 76.38   worth $14.40
        electric    620 kWh  ->   618 kWh     71.80 -> 71.52   worth  $0.28

    **Fifty-one times the money from the same row**, decided entirely by which
    service the discount is attached to. That is `OQ-291`'s worked failure, and
    it is why the unit had to come from somewhere rather than be assumed.

    The allowance comes off the TOP block in both cases, which is what
    *"deduct before the tier walk"* means: 2 kgal at 7.20 and 2 kWh at 0.14.
    """
    water_before = priced(Decimal("18.72"), WATER_TIERS)
    water_after = priced(
        resolution.allowance_deducted_quantity("water", Decimal("18.72"), "kgal", Decimal("2")),
        WATER_TIERS,
    )
    assert (water_before, water_after) == (Decimal("90.78"), Decimal("76.38"))
    assert water_before - water_after == Decimal("14.40")

    electric_before = priced(Decimal("620"), ELECTRIC_TIERS)
    electric_after = priced(
        resolution.allowance_deducted_quantity("electric", Decimal("620"), "kWh", Decimal("2")),
        ELECTRIC_TIERS,
    )
    assert (electric_before, electric_after) == (Decimal("71.80"), Decimal("71.52"))
    assert electric_before - electric_after == Decimal("0.28")

    # The whole point: one row, two answers, and the service is the only input
    # that differed.
    assert water_before - water_after != electric_before - electric_after


def test_tc3__a_service_that_states_no_unit_refuses_rather_than_being_given_one():
    """**THE RULING GIVES THE UNIT A SOURCE, NOT A DEFAULT** — CLAUDE.md hard
    rule 3 survives, and this is where.

    Four of the ten catalog services carry no stated unit (sewer, solar,
    thermal/heat, battery), so this is reachable on a real tenant rather than
    theoretical — TC4 proves it against the seeded database.
    """
    with pytest.raises(resolution.UsageAllowanceUnusable) as refusal:
        resolution.usage_allowance_units("sewer", None)
    assert "has not stated what unit that service is measured in" in str(refusal.value)
    # G28 / CR-016 — the clerk's sentence carries the FACT, not an id.
    assert "OQ-291" not in str(refusal.value)
    assert "BR-RAT" not in str(refusal.value)


def test_tc4__the_seeded_tenant_resolves_kgal_kwh_and_nothing_for_sewer(env):
    """The same three answers, off the REAL tenant rather than a literal.

    `tenant_services.billed_uom` is NULL on a fresh tenant and that means *the
    register's own unit is what is billed* (`apps.tenancy.selectors.
    service_billed_uoms` says so in as many words) — not "unconfigured, refuse".
    So water answers `kgal` from `primary_uom`, and sewer answers nothing at all
    because the tenant states neither.
    """
    from apps.rating import seams

    with tenant_ctx(env.tenant):
        assert (seams.billed_uom("water")["primary_uom"]) == "kgal"
        assert (seams.billed_uom("electric")["primary_uom"]) == "kWh"
        sewer = seams.billed_uom("sewer")
        assert sewer["billed_uom"] is None and sewer["primary_uom"] is None


def test_tc5__a_stated_unit_that_disagrees_with_the_meter_still_refuses():
    """`BR-RAT-038`, *"no silent conversion"*, and the branch that keeps the
    inference honest. Under the ruling a production caller passes no unit at
    all, so this fires only for a caller that resolved one ITSELF and resolved
    it from the wrong service — which is exactly the failure `OQ-291` described,
    arriving from the other direction."""
    with pytest.raises(resolution.UsageAllowanceUnusable) as refusal:
        resolution.allowance_deducted_quantity(
            "electric", Decimal("620"), "kWh", Decimal("2"), allowance_unit="kgal"
        )
    assert "'kgal'" in str(refusal.value) and "'kWh'" in str(refusal.value)


def test_tc6__a_whole_bill_usage_allowance_refuses_at_setup(env):
    """⚖️ **`BR-RAT-960`'s SECOND HALF — decided by implication, written down
    rather than re-asked (law 13).**

    Taking the unit from the service means a discount attached to the WHOLE
    BILL has no service to take one from. The decision log's own sentence: *"a
    refusal a clerk meets while configuring is a correction; the same refusal
    met during a bill run is an outage."* So it refuses HERE, at
    `create_discount`, on the `applies_to` field.
    """
    with tenant_ctx(env.tenant):
        with pytest.raises(errors.ValidationError) as refusal:
            discount_services.create_discount(
                env.admin,
                {
                    "code": "FREEKGAL",
                    "name": "Two free units",
                    "discount_type": "usage_allowance",
                    "value": "2",
                    "applies_to": "whole_bill",
                },
            )
    fields = {error["field"]: error for error in refusal.value.field_errors}
    assert "applies_to" in fields
    assert fields["applies_to"]["message_key"] == "rating.discounts.allowance_needs_one_service"
    assert fields["applies_to"]["params"]["br_ref"] == "BR-RAT-960"


def test_tc7__omitting_the_scope_refuses_too_because_the_column_defaults_to_whole_bill(env):
    """⚠ **THE CASE A GATE-SHAPED COMMENT WOULD HAVE MISSED, AND IT IS THE MOST
    LIKELY ONE.**

    `DiscountVersion.applies_to` defaults to `whole_bill`, so a payload that
    simply never mentions the scope — a clerk who left the control alone —
    STORES the state the ruling forbids. A gate reading only the submitted
    `applies_to` would refuse the explicit whole-bill save and wave this one
    through, i.e. it would be green on the commonest way to break the rule.
    """
    with tenant_ctx(env.tenant):
        with pytest.raises(errors.ValidationError) as refusal:
            discount_services.create_discount(
                env.admin,
                {
                    "code": "FREEKGAL2",
                    "name": "Two free units, scope untouched",
                    "discount_type": "usage_allowance",
                    "value": "2",
                },
            )
    assert any(e["field"] == "applies_to" for e in refusal.value.field_errors)


def test_tc8__a_one_service_allowance_saves_and_resolves_its_unit(env):
    """The positive case, which is what proves the gate is not simply always on
    — and the display half of the ruling in the same assertion.

    The stored value is `2` and the screen shows **`2.00 kgal`**, because the
    unit was RESOLVED from the service the scope names. A bare `2.00` is the row
    `OQ-291`'s worked failure describes.
    """
    from apps.tenancy import models as tenancy_models

    with tenant_ctx(env.tenant):
        # `DEF-RAT-5815` — the field takes a CODE, like every other surface
        # that names a service. It took a UUID until 2026-09-19, which is why
        # DIS-02's own picker (which sends `row.service`, the code) had never
        # been able to save this scope at all.
        tenancy_models.Service.objects.get(code="water")  # it exists on this tenant
        row = saved_before_the_ruling(
            env.admin,
            {
                "code": "FREEKGAL3",
                "name": "Two free kilogallons",
                "discount_type": "usage_allowance",
                "value": "2",
                "applies_to": "one_service",
                "applies_to_service": "water",
                "effective_from": date(2026, 8, 1),
            },
        )
        assert row["type"] == "usage_allowance"
        assert row["allowance_unit"] == "kgal"
        assert row["value_display"] == "2.00 kgal"


def test_tc9__the_same_row_on_electric_displays_kwh(env):
    """The display half of TC2 — one stored `2`, two screens, two units. This is
    how a clerk NOTICES a discount attached to the wrong service, which is the
    only protection left once the unit is inferred rather than stated."""
    from apps.tenancy import models as tenancy_models

    with tenant_ctx(env.tenant):
        tenancy_models.Service.objects.get(code="electric")
        row = saved_before_the_ruling(
            env.admin,
            {
                "code": "FREEKWH",
                "name": "Two free kilowatt-hours",
                "discount_type": "usage_allowance",
                "value": "2",
                "applies_to": "one_service",
                "applies_to_service": "electric",
                "effective_from": date(2026, 8, 1),
            },
        )
    assert row["allowance_unit"] == "kWh"
    assert row["value_display"] == "2.00 kWh"


def test_tc9b__an_allowance_on_a_unitless_service_displays_the_bare_figure(env):
    """`None` unit prints the figure and no unit, which is the honest fallback:
    the service states none, and `usage_allowance_units` REFUSES to price it.
    A screen that guessed `kgal` here would put a made-up fact on a
    bill-affecting page — the exact thing `discount_value_display` refused to do
    before the ruling gave it a real source."""
    from apps.tenancy import models as tenancy_models

    with tenant_ctx(env.tenant):
        # ⚠ **SEWER HAS TO BE SWITCHED ON FOR THIS TENANT NOW, AND THE REASON IS
        # A REAL BEHAVIOUR CHANGE RATHER THAN A FIXTURE DETAIL (`DEF-RAT-5815`,
        # 2026-09-19).** `applies_to_service` used to take a UUID and pass it
        # straight into the column, so NOTHING checked the service at all — a
        # discount could name a service the utility does not sell. It now takes
        # a CODE and is validated the way its plural sibling and the tax already
        # are (`BR-RAT-024`: in the platform catalogue AND enabled here). The
        # `env` fixture sells electric and water, and both of those HAVE a unit,
        # so this case — *what does a UNITLESS service display?* — needs a third
        # one that this utility actually sells.
        #
        # ⚠ **THIS DOES NOT MAKE THE CASE PASS, AND IT IS NOT MEANT TO.** The
        # case is RED at the tip as well, for an older and unrelated reason:
        # sewer gained `kgal` as its primary unit in `c7485bebc` (2026-09-08),
        # so the seeded estate has no unitless service left and the assertion
        # reads `assert 'kgal' is None`. That is `DEF-RAT-6450`, filed rather
        # than papered over — deciding what `BR-RAT-960` now means is a ruling,
        # not a test edit. **All this line does is stop `DEF-RAT-5815` adding a
        # SECOND reason for the same failure**, which would hide the first from
        # whoever picks that defect up.
        # `update_or_create` and NOT `get_or_create`: provisioning writes a
        # `tenant_services` row for every catalogue service and sets `enabled`
        # from the payload, so the row already EXISTS here with `enabled=False`
        # and `get_or_create` would find it and change nothing — a fixture that
        # looks like it switched a service on and did not.
        tenancy_models.TenantService.objects.update_or_create(
            tenant=env.tenant,
            service=tenancy_models.Service.objects.get(code="sewer"),
            defaults={"enabled": True},
        )
        row = saved_before_the_ruling(
            env.admin,
            {
                "code": "FREESEWER",
                "name": "Two free units of sewer",
                "discount_type": "usage_allowance",
                "value": "2",
                "applies_to": "one_service",
                "applies_to_service": "sewer",
            },
        )
    assert row["allowance_unit"] is None
    assert row["value_display"] == "2.00"


# ══════════════════════════════════════════════════════════════════════════
# RULING 4 · A SUBSIDY DOES NOT CHANGE THE RATE SCHEDULE  (BR-RAT-961)
# ══════════════════════════════════════════════════════════════════════════


def test_tc10__the_subsidy_priced_end_to_end_on_the_standard_schedule():
    """⚖️ **THE RULING'S THREE FIGURES.** PO verbatim: *"we will apply standard
    rate and also provdie discount - thats how it should be handled; sicne there
    is subsidy we dont change rate schedule"*.

    A `620 kWh` residential customer on the seeded `Res Electric · Tiered`
    (`0–500 @ 0.11 / 500–1,000 @ 0.14 / 1,000+ @ 0.19`), with the seeded `CAP /
    low-income credit` programme (a `$25.00` fixed amount on the whole bill):

        the standard schedule charges     500 × 0.11 + 120 × 0.14 =  $71.80
        the subsidy takes off                                        $25.00
        the customer pays                                            $46.80

    **Both numbers are printed** — `BR-RAT-068`: *"the bill shows the full tariff
    amount and the reduction as its own line, so subsidy granted is
    reportable."*
    """
    standard = priced(Decimal("620"), ELECTRIC_TIERS)
    subsidy = Decimal("25.00")  # the seeded CAP programme, to the digit
    assert standard == Decimal("71.80")
    assert standard - subsidy == Decimal("46.80")


def test_tc11__the_seeded_cap_programme_is_the_subsidy_and_it_is_already_priceable(env):
    """The mechanism the ruling names is not new and needs building nowhere: a
    subsidy is an ORDINARY discount, and the seeded estate already carries one.
    `CAP / low-income credit` is a `fixed_amount` — in
    `DISCOUNT_TYPES_PRICEABLE` — funded by a city programme and reported in the
    annual assistance filing."""
    from apps.rating import discount_sample_data

    with tenant_ctx(env.tenant):
        discount_sample_data.seed_sample_discounts(env.admin)
        cap = discount_models.Discount.objects.get(tenant=env.tenant, code="CAP")
        row = selectors.discount_row(cap)
    assert row["type"] == "fixed_amount"
    assert Decimal(row["value"]) == Decimal("25")
    assert row["type"] in discount_models.DISCOUNT_TYPES_PRICEABLE
    assert cap.report_in_assistance_filing is True


def test_tc12__the_swap_would_have_hidden_the_subsidy_and_that_is_why_the_ruling_is_better():
    """⚖️ **WHY THE PO'S ANSWER BEATS ALL THREE OF OURS, as a number.**

    Every option we offered kept a mechanism that prices a customer from a
    schedule their plan does not name. Through a half-price subsidy schedule the
    same `620 kWh` customer's bill would read **ONE line of `$35.90`** and
    nothing on it would say a subsidy had been granted. Through the ruling it
    reads `$71.80` and `−$25.00`.

    **A discount line is visible on the bill; a swapped schedule is invisible.**
    The customer can see what they were given, and `BR-RAT-068` required exactly
    that from 2026-08-19 — which the `rate_override` type had contradicted in
    silence ever since.
    """
    halved = tuple((span, rate / 2) for span, rate in ELECTRIC_TIERS)
    swapped = priced(Decimal("620"), halved)
    assert swapped == Decimal("35.90")

    standard = priced(Decimal("620"), ELECTRIC_TIERS)
    # One printed figure through the swap; two through the ruling.
    assert (standard, Decimal("25.00"), standard - Decimal("25.00")) == (
        Decimal("71.80"),
        Decimal("25.00"),
        Decimal("46.80"),
    )


def test_tc13__the_override_read_names_the_ruling_and_not_an_open_question():
    """`OQ-292` is CLOSED **by dissolution**. An `OQ-###` here would tell the
    next lane a person still has to decide; a person decided. A lane that adds
    `override_tariff_id` to satisfy this is reversing a ruling, not finishing a
    stub — so the refusal says so."""
    with pytest.raises(NotImplementedError) as refusal:
        resolution.rate_override_target("SUBSIDY-RES")
    text = str(refusal.value)
    assert "BR-RAT-961" in text
    assert "OQ-292" not in text
    assert "standard" in text.lower()


def test_tc14__discount_versions_still_has_no_pointer_to_a_tariff():
    """**The absence is now SETTLED, not pending**, and this asserts it stays
    that way. `BR-RAT-961` removed the need for the column rather than deciding
    where to put it, so a migration adding one would be reversing the ruling —
    the same shape `test_a_plan_discount_rule_cannot_carry_a_value` gives the
    2026-08-19 ruling one table over."""
    columns = {f.name for f in discount_models.DiscountVersion._meta.get_fields()}
    forbidden = {"override_tariff", "override_tariff_id", "target_tariff", "rate_schedule"}
    assert not (columns & forbidden), f"a discount may not swap a schedule: {columns & forbidden}"


# ══════════════════════════════════════════════════════════════════════════
# BOTH · THE MONEY DID NOT MOVE, AND THAT IS THE RULING  (BR-RAT-962)
# ══════════════════════════════════════════════════════════════════════════


def test_tc15__neither_type_became_priceable_and_the_reason_is_arithmetic():
    """⚠ **THE TEST THAT STOPS THE OBVIOUS WRONG NEXT STEP.**

    Closing two questions that blocked two discount types reads as permission to
    make them priceable. It is not.

    `DISCOUNT_TYPES_PRICEABLE` gates `discount_pricing._raw_reduction`, which is
    **R6 — a subtraction of MONEY from a subtotal**. A usage allowance deducts
    **UNITS** before R3b's tier walk. Admitting it would price the `2 kgal`
    allowance of TC2 as **`$2.00` off** where the ruled arithmetic makes it
    **`$14.40`** — a `$12.40` error on one bill, in the customer's disfavour, on
    a discount the utility believes it granted.

    `rate_override` stays out because `BR-RAT-961` left it nothing to do.
    """
    assert set(discount_models.DISCOUNT_TYPES_PRICEABLE) == {
        discount_models.DISCOUNT_PERCENTAGE,
        discount_models.DISCOUNT_FIXED_AMOUNT,
        discount_models.DISCOUNT_CHARGE_WAIVER,
    }

    # The $12.40 the exclusion is worth, computed rather than asserted from
    # memory: money-at-R6 against units-before-the-tier-walk.
    as_money_at_r6 = Decimal("2.00")
    as_units_before_tiers = priced(Decimal("18.72"), WATER_TIERS) - priced(
        Decimal("16.72"), WATER_TIERS
    )
    assert as_units_before_tiers == Decimal("14.40")
    assert as_units_before_tiers - as_money_at_r6 == Decimal("12.40")


def test_tc16__activation_still_refuses_both_types(env):
    """The gate an operator actually meets, asserted through the real service
    rather than through the tuple — a constant nothing enforces is a comment.

    ⚠ AND THIS IS THE OTHER REASON THE SET-UP REFUSAL OF TC6 MATTERS: it fires
    at `create_discount`, so a whole-bill allowance never even reaches here.
    """
    with tenant_ctx(env.tenant):
        for code, discount_type in (("OVR31", "rate_override"), ("ALW31", "usage_allowance")):
            payload = {
                "code": code,
                "name": f"Test {discount_type}",
                "discount_type": discount_type,
                "value": "2",
                "effective_from": date(2026, 8, 1),
            }
            if discount_type == "usage_allowance":
                # BR-RAT-960 — the only scope this type may be saved on at all.
                from apps.tenancy import models as tenancy_models

                payload["applies_to"] = "one_service"
                # `DEF-RAT-5815` — a CODE, resolved and validated at save.
                payload["applies_to_service"] = tenancy_models.Service.objects.get(
                    code="water"
                ).code
            if discount_type == "usage_allowance":
                row = saved_before_the_ruling(env.admin, payload)
            else:
                row = discount_services.create_discount(env.admin, payload)
            version = discount_models.DiscountVersion.objects.get(
                tenant=env.tenant, discount_id=row["id"]
            )
            with pytest.raises(errors.BizError):
                discount_services.activate_discount_version(env.admin, version.id)
