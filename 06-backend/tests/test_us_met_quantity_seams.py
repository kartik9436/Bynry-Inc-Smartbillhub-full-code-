# ── Trace ──────────────────────────────────────────────
# Story:    US-MET-011 (the validation engine owns the wrap arithmetic) ·
#           US-MET-014 (auto-estimate) · US-MET-015 (true-up at the next actual)
#           Screens: — (pure functions; the quantities render on S28 step 3,
#           S29, S31.2 and are priced by rating for S31.3)
# Rules:    BR-MET-019 (consumption = (current − prior) × multiplier, explicit
#           unit, unrounded) · BR-RAT-011 (rollover consumption) · BR-AST-015
#           (register_digits is the rollover-detection input) · BR-MET-052
#           (a negative that is not a wrap is NEVER auto-fixed) · BR-MET-029
#           (true-up by register arithmetic) · BR-MET-058 (one lineage) ·
#           OQ-009 closure (the >50%-of-span check) · OQ-004 closure (no silent
#           unit conversion)
# Golden:   GT-4 / GT-14 (rollover → 440) · GT-9 (true-up → +82) — B5 ❄️ FROZEN,
#           finance-signed 2026-08-08. Asserted here through metering's OWN
#           module; tests/golden/ asserts the same figures through the billing
#           seam, which is what proves the two are wired together.
# Journeys: J2 step 6 · J3 (exception handling)
# ───────────────────────────────────────────────────────
"""The published metering quantity seams — GT-4/GT-14 and GT-9.

Three properties are asserted here that the golden fixtures cannot assert on
their own, because a golden fixture states B5 and nothing else:

* **The unit comes from CONFIGURATION, not from this code** (CLAUDE.md rule 3;
  PO ruling 2026-08-11). B5 GT-4 states a bare 440 with no unit. Rather than
  annotate the frozen document or hardcode "kWh", the database half of this
  file creates REAL meters — one configured in kWh, one in kgal — and reads
  `unit`, `multiplier` and `register_digits` off the persisted asset row. The
  kgal meter produces kgal. Nothing in the seam can produce a unit by itself:
  a missing one is a refusal, not a default.

* **Nothing is invented for a value the engine cannot compute** (BR-MET-052).
  A wrap computes and flags; every other negative refuses, and refuses the same
  way through both the seam and the read pipeline.

* **No money, anywhere.** These functions return quantities. No rate is read,
  no amount is produced, nothing is rounded to 2dp — asserted structurally, not
  merely promised in a docstring (hard-won law 1).
"""

import inspect
from decimal import Decimal

import pytest

from apps.assets import models as asset_models
from apps.billing import rating_seam
from apps.metering import estimation, quantities, services, validation

from tests.test_us_met_reads_helpers import *  # noqa: F401,F403
from tests.test_us_met_reads_helpers import (  # noqa: F401
    a_meter,
    tenant_ctx,
)

# ── B5 GT-4 / GT-14, quoted (05-golden-tests.md lines 21-22 and 52-53) ──────
# "5-digit register, prior 99,800, current 240, ×1 → (100,000−99,800)+240 = 440
#  (span check: 99,560 > 50% of 100,000 → rollover, not negative-read)."
GT4_PRIOR = Decimal("99800")
GT4_CURRENT = Decimal("240")
GT4_MULTIPLIER = Decimal("1")
GT4_DIGITS = 5
GT4_CONSUMPTION = Decimal("440")

# ── B5 GT-9, quoted (05-golden-tests.md line 37) ────────────────────────────
# "trailing-3 avg = 618 kWh billed; next cycle real read implies actual 700 →
#  true-up +82 kWh on that bill."
GT9_PREVIOUSLY_BILLED = Decimal("618")
GT9_ACTUAL = Decimal("700")
GT9_TRUE_UP = Decimal("82")

# B5 states NO unit for GT-4/GT-14. A symbolic one is passed so the assertion is
# "whatever the configuration supplied comes back untouched" rather than a
# quietly chosen kWh — the same posture tests/golden/test_gt04 takes.
UNIT_NOT_STATED_IN_B5 = "UNIT-NOT-STATED-IN-B5-GT-4"


def kwh(amount: str) -> quantities.Quantity:
    return quantities.Quantity(amount=Decimal(amount), unit="kWh")


# ── GT-4 / GT-14: the wrap ─────────────────────────────────────────────────


def test_gt_4_and_gt_14__a_five_digit_wrap_computes_440():
    """The frozen figure, through the published seam: (100,000−99,800)+240."""
    consumption = quantities.consumption_from_registers(
        prior_read=GT4_PRIOR,
        current_read=GT4_CURRENT,
        multiplier=GT4_MULTIPLIER,
        register_digits=GT4_DIGITS,
        unit=UNIT_NOT_STATED_IN_B5,
    )
    assert consumption.amount == GT4_CONSUMPTION
    assert consumption.unit == UNIT_NOT_STATED_IN_B5  # rule 3: in, then out, untouched


def test_gt_14__the_span_check_is_what_separates_a_wrap_from_a_bad_read():
    """GT-14's own working: the drop is 99,560 against a 100,000 span.

    The rule is ">50% of the span", strictly. A drop of EXACTLY half the span
    is therefore NOT a wrap — it is the BR-MET-052 hard error. Asserting the
    boundary is what makes the threshold a rule rather than a coincidence: move
    `ROLLOVER_SPAN_FRACTION` and this test and GT-4 both go red.
    """
    span = validation.register_span(GT4_DIGITS)
    assert span == Decimal("100000")
    assert GT4_PRIOR - GT4_CURRENT == Decimal("99560")
    assert Decimal("99560") > span * validation.ROLLOVER_SPAN_FRACTION

    # Exactly 50,000 of drop on a 100,000 span: not MORE than half, so not a wrap.
    at_the_boundary = validation.classify_register_delta(
        prior=Decimal("60000"),
        current=Decimal("10000"),
        multiplier=Decimal("1"),
        register_digits=GT4_DIGITS,
    )
    assert at_the_boundary.drop == span * validation.ROLLOVER_SPAN_FRACTION
    assert at_the_boundary.kind == "negative_usage"
    assert at_the_boundary.consumption is None


def test_br_met_019__a_normal_advance_is_the_delta_times_the_multiplier():
    """No wrap involved: 42,180 → 42,864 ×1 = 684 (EP-MET-03's Brazos batch)."""
    consumption = quantities.consumption_from_registers(
        prior_read=Decimal("42180"),
        current_read=Decimal("42864"),
        multiplier=Decimal("1"),
        register_digits=5,
        unit="kWh",
    )
    assert consumption.amount == Decimal("684") and consumption.unit == "kWh"


def test_br_met_019__the_multiplier_applies_to_the_wrapped_delta_too():
    """BR-MET-019's general form. GT-14's fixture is ×1 and cannot discriminate,
    so the ×10 case is pinned here rather than left to chance — this is the Eng
    reading the read lane REPORTED, made visible instead of implicit."""
    consumption = quantities.consumption_from_registers(
        prior_read=GT4_PRIOR,
        current_read=GT4_CURRENT,
        multiplier=Decimal("10"),
        register_digits=GT4_DIGITS,
        unit="kWh",
    )
    assert consumption.amount == Decimal("4400")


def test_br_met_052__a_negative_that_is_not_a_wrap_refuses_instead_of_inventing():
    """88,204 → 88,102 is nowhere near a wrap. The seam cannot return "no
    answer" (its contract is `-> Quantity`), so it RAISES. What it must never
    do is produce a number."""
    with pytest.raises(ValueError, match="NEGATIVE read"):
        quantities.consumption_from_registers(
            prior_read=Decimal("88204"),
            current_read=Decimal("88102"),
            multiplier=Decimal("1"),
            register_digits=5,
            unit="kWh",
        )


def test_br_ast_015__with_no_register_digits_no_wrap_can_be_claimed():
    """The span is an ASSET fact. With none, guessing a 5-, 6- or 9-digit
    register would be inventing exactly the input the rule turns on."""
    with pytest.raises(ValueError, match="NEGATIVE read"):
        quantities.consumption_from_registers(
            prior_read=GT4_PRIOR,
            current_read=GT4_CURRENT,
            multiplier=Decimal("1"),
            register_digits=0,
            unit="kWh",
        )


def test_one_wrap_implementation__the_seam_and_the_read_engine_agree():
    """The seam adds a unit; it does not re-derive the rule. Both paths read
    the same `classify_register_delta`, so a change to the rule moves both — a
    second implementation is how a frozen figure drifts."""
    through_the_seam = quantities.consumption_from_registers(
        prior_read=GT4_PRIOR,
        current_read=GT4_CURRENT,
        multiplier=GT4_MULTIPLIER,
        register_digits=GT4_DIGITS,
        unit="kWh",
    )
    through_the_engine, outcome = validation.compute_consumption(
        validation.ReadContext(
            value=GT4_CURRENT,
            prior_value=GT4_PRIOR,
            multiplier=GT4_MULTIPLIER,
            register_digits=GT4_DIGITS,
            unit="kWh",
        )
    )
    assert through_the_seam.amount == through_the_engine == GT4_CONSUMPTION
    # And the read pipeline still FLAGS it — auto-computing is not auto-accepting.
    assert outcome.rule == "rollover" and outcome.severity == "warning"


# ── GT-9: the true-up ──────────────────────────────────────────────────────


def test_us_met_015_tc1__gt_9_true_up_is_the_actual_less_what_was_billed():
    """618 kWh was estimated and billed; the span actually measured 700 kWh;
    the correction carried onto the next bill is +82 kWh. No money is asserted
    because B5 GT-9 states none."""
    true_up = quantities.true_up_quantity(
        actual=kwh(str(GT9_ACTUAL)),
        previously_billed=kwh(str(GT9_PREVIOUSLY_BILLED)),
    )
    assert true_up.amount == GT9_TRUE_UP
    assert true_up.unit == "kWh"  # B5 states kWh on both sides of this one


def test_us_met_015_tc3__an_over_estimate_trues_negative_and_is_not_clamped():
    """Clamping would silently keep an over-billed customer over-billed."""
    true_up = quantities.true_up_quantity(actual=kwh("1100"), previously_billed=kwh("1236"))
    assert true_up.amount == Decimal("-136")


def test_one_true_up_implementation__the_seam_and_the_lineage_path_agree():
    """`estimation.true_up` derives its actual from register arithmetic over a
    whole estimate→actual lineage; the seam is handed the two quantities. Both
    reduce to `estimation.correction_quantity`, so the rule has one version."""
    lineage = estimation.true_up(
        estimation.TrueUpInput(
            channel="total",
            unit="kWh",
            actual_register=Decimal("44182"),
            last_actual_register=Decimal("42864"),
            multiplier=Decimal("1"),
            estimated_consumptions=[Decimal("618")],
        )
    )
    assert lineage.quantity == GT9_ACTUAL  # 1,318 − 618 = 700
    seam = quantities.true_up_quantity(
        actual=quantities.Quantity(amount=lineage.quantity, unit=lineage.unit),
        previously_billed=kwh(str(GT9_PREVIOUSLY_BILLED)),
    )
    assert seam.amount == GT9_TRUE_UP


def test_oq_004__a_true_up_never_converts_between_units():
    """A factor is tenant configuration and this module holds none, so a unit
    mismatch is a refusal — never a silent conversion."""
    with pytest.raises(ValueError, match="kgal"):
        quantities.true_up_quantity(
            actual=quantities.Quantity(amount=Decimal("700"), unit="kgal"),
            previously_billed=kwh("618"),
        )


# ── CLAUDE.md rule 3: the unit is never assumed ────────────────────────────


@pytest.mark.parametrize("bare", [None, "", "   "])
def test_claude_rule_3__consumption_from_registers_refuses_a_bare_quantity(bare):
    """There is no "assume kWh" branch, and no default argument to fall back to."""
    with pytest.raises(ValueError, match="never travels without its unit"):
        quantities.consumption_from_registers(
            prior_read=Decimal("100"),
            current_read=Decimal("200"),
            multiplier=Decimal("1"),
            register_digits=5,
            unit=bare,
        )


@pytest.mark.parametrize("bare", [None, "", "   "])
def test_claude_rule_3__true_up_quantity_refuses_a_bare_quantity(bare):
    with pytest.raises(ValueError, match="never travels without its unit"):
        quantities.true_up_quantity(
            actual=quantities.Quantity(amount=Decimal("700"), unit=bare),
            previously_billed=kwh("618"),
        )


def test_claude_rule_3__the_unit_is_a_required_argument_with_no_default():
    """Structural, not a promise: if a default ever appears on `unit`, the seam
    acquires an assumption and this test says so."""
    signature = inspect.signature(quantities.consumption_from_registers)
    assert signature.parameters["unit"].default is inspect.Parameter.empty
    assert signature.parameters["register_digits"].default is inspect.Parameter.empty


# ── quantities only: no money crosses this seam ────────────────────────────


def test_no_money__a_quantity_carries_an_amount_and_a_unit_and_nothing_else():
    """B5 GT-4 and GT-9 freeze quantities and state no rate, charge or total.
    A currency field appearing here would mean metering had started pricing."""
    fields = quantities.Quantity.__dataclass_fields__
    assert set(fields) == {"amount", "unit"}


def test_no_money__the_quantity_seam_reads_no_rate_and_rounds_no_currency():
    """Hard-won law 1: the docstring's promise is checked, not trusted. B4.4
    puts money rounding at invoice-line finalization inside rating; this module
    must not reach for `core.money` or any tariff/price/rate."""
    source = inspect.getsource(quantities)
    body = source.split('"""', 2)[-1]  # skip the module docstring, which discusses money
    for forbidden in ("core.money", "money.finalize", "tariff", "unit_price", "currency"):
        assert forbidden not in body, f"{forbidden!r} appeared in the quantity seam"


# ── the seam is WIRED, not merely built (hard-won law 2) ───────────────────


def test_the_billing_seam_resolves_the_metering_owner():
    """`rating_seam` resolves `apps.metering.services.<name>` at call time. If
    the publication in services.py were removed, these would raise
    NotImplementedError instead of returning a figure."""
    assert services.consumption_from_registers is quantities.consumption_from_registers
    assert services.true_up_quantity is quantities.true_up_quantity

    consumption = rating_seam.consumption_from_registers(
        prior_read=GT4_PRIOR,
        current_read=GT4_CURRENT,
        multiplier=GT4_MULTIPLIER,
        register_digits=GT4_DIGITS,
        unit=UNIT_NOT_STATED_IN_B5,
    )
    assert consumption.amount == GT4_CONSUMPTION

    true_up = rating_seam.true_up_quantity(
        actual=rating_seam.Quantity(amount=GT9_ACTUAL, unit="kWh"),
        previously_billed=rating_seam.Quantity(amount=GT9_PREVIOUSLY_BILLED, unit="kWh"),
    )
    assert true_up.amount == GT9_TRUE_UP and true_up.unit == "kWh"


# ── the unit comes from CONFIGURATION (PO ruling 2026-08-11) ───────────────


@pytest.mark.django_db
def test_the_unit_and_the_span_come_off_the_METER_ROW_not_out_of_this_code(brazos, marcus):
    """The PO ruling, proved rather than asserted.

    Two real meters are created through the real assets service — an electric
    one in kWh with a 5-digit register, and a water one in kgal. Every input
    the seam needs (`unit`, `multiplier`, `register_digits`) is read back off
    the PERSISTED row; no literal is typed into the call. GT-4's 440 therefore
    reproduces on a meter that was CONFIGURED as 5-digit, and the same reading
    pair on the kgal meter comes back in kgal — which it could not do if any
    unit were baked in here.
    """
    with tenant_ctx(brazos):
        a_meter(marcus, "M-7301", service="electric", uom="kWh", register_digits=5)
        a_meter(
            marcus,
            "M-7302",
            service="water",
            uom="kgal",
            register_digits=5,
            unit_label="Unit B",
            address="221 Cypress Row",
        )
        electric = asset_models.Asset.objects.get(asset_no="M-7301")
        water = asset_models.Asset.objects.get(asset_no="M-7302")

        # Nothing below names a unit: every argument comes off the row.
        from_electric = quantities.consumption_from_registers(
            prior_read=GT4_PRIOR,
            current_read=GT4_CURRENT,
            multiplier=electric.multiplier,
            register_digits=electric.register_digits,
            unit=electric.unit,
        )
        from_water = quantities.consumption_from_registers(
            prior_read=GT4_PRIOR,
            current_read=GT4_CURRENT,
            multiplier=water.multiplier,
            register_digits=water.register_digits,
            unit=water.unit,
        )

    assert electric.unit == "kWh" and water.unit == "kgal"  # what was CONFIGURED
    assert from_electric.amount == GT4_CONSUMPTION  # GT-4, on a configured 5-digit meter
    assert from_electric.unit == "kWh"
    assert from_water.unit == "kgal"  # same reading pair, different meter, different unit


@pytest.mark.django_db
def test_a_true_up_carries_the_meters_own_unit(brazos, marcus):
    """GT-9's arithmetic on a meter configured in kgal comes back in kgal. The
    quantities are B5's; the unit is the asset's."""
    with tenant_ctx(brazos):
        a_meter(marcus, "M-7303", service="water", uom="kgal", address="9 Sabine Ct")
        meter = asset_models.Asset.objects.get(asset_no="M-7303")
        true_up = quantities.true_up_quantity(
            actual=quantities.Quantity(amount=GT9_ACTUAL, unit=meter.unit),
            previously_billed=quantities.Quantity(amount=GT9_PREVIOUSLY_BILLED, unit=meter.unit),
        )
    assert true_up.amount == GT9_TRUE_UP
    assert true_up.unit == "kgal" == meter.unit


@pytest.mark.django_db
def test_claude_rule_3__a_meter_with_no_configured_uom_cannot_produce_a_quantity(brazos, marcus):
    """The refusal is not theoretical: an asset row whose `unit` is NULL feeds
    the seam nothing to work with, and the seam refuses rather than defaulting.
    (`validation` already errors the same read with `unit_missing`.)"""
    with tenant_ctx(brazos):
        a_meter(marcus, "M-7304", service="electric", uom="kWh", address="14 Neches Way")
        meter = asset_models.Asset.objects.get(asset_no="M-7304")
        meter.unit = None  # a row that never captured its UoM
        with pytest.raises(ValueError, match="never travels without its unit"):
            quantities.consumption_from_registers(
                prior_read=Decimal("100"),
                current_read=Decimal("200"),
                multiplier=meter.multiplier,
                register_digits=meter.register_digits,
                unit=meter.unit,
            )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-MET-015@ec4ba67 (sha1[:7] of the four frozen sources, concatenated in
#         order: 04-docs/02-decisions/05-golden-tests.md ·
#         04-docs/05-modules/04-metering/06-epics/EP-MET-04-read-validation.md ·
#         04-docs/05-modules/04-metering/06-epics/EP-MET-05-estimation.md ·
#         04-docs/05-modules/04-metering/02-business-rules.md; co-stories
#         US-MET-011 + US-MET-014, same sources)
# generated: 2026-08-11 by the metering quantity-seam lane
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — pure functions behind an existing seam) E=deferred(no-frontend-half) F✔ G✔ H=deferred(N/A — not a 🔒 path: quantities only, no money figure/threshold/key authored)
# gates: ruff✔ black✔ · pytest tests -m golden → 10 passed / 1 xfailed✔ · pytest tests -m "not golden and not isolation"✔ · 10-scripts/03-golden-verify.py 33 PASS + GT-1..16 12 PASS✔ · run_gates 14 PASS / 0 FAIL / 1 SKIP✔
# exceptions: (1) The rollover boundary case (a drop of EXACTLY half the span) is asserted from the RULE's wording (">50% of the span", OQ-009 closure) — B5 states no worked figure at the boundary, so the fixture is Eng-constructed and only the STRICTNESS of the comparison is claimed, never a new frozen number. (2) GT-4/GT-14 state no unit; the symbolic unit is passed through and the CONFIGURED unit is proved separately against real meter rows — the frozen document was not annotated. (3) No money is asserted anywhere, because B5 GT-4 and GT-9 freeze quantities only.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
