# ── Trace ──────────────────────────────────────────────
# Rule:     BR-RAT-036 as AMENDED 2026-08-21 (PO ruling, option C, DEF-386).
#           PO verbatim: "Per-meter now (it's a small change), stacking later —
#           because that one needs care to avoid a tax that taxes itself in a
#           circle."
# Defect:   DEF-386 — CR-013 part 4 names FOUR computation forms and BR-RAT-036
#           ratified THREE. "Per meter" is the shape a state regulatory fee
#           usually takes, and it had nowhere to live: a $1.25 per-meter fee on
#           a duplex with two meters billed $0.00.
# Shape:    The load-bearing test here is the NEGATIVE one — per_meter takes no
#           unit of measure, where per_unit requires one. That asymmetry is the
#           distinction between pricing a COUNT and pricing a MEASURE, and it is
#           the thing a future reader is most likely to "fix" by adding a UoM.
# Prove-it: run against the previous commit and the create fails outright, the
#           kind not being in TAX_KINDS.
# ───────────────────────────────────────────────────────
"""BR-RAT-036 amended — the fourth tax computation form."""

from decimal import Decimal

import pytest

from apps.rating import models, services
from core import errors

from tests.test_us_rat_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_rat_helpers import api_call, tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db


def _per_meter_payload(**overrides):
    payload = {
        "name": "State Regulatory Fee",
        # Every tax attaches to an authority — a fee remitted to nobody is not a
        # tax, so the validator requires one and these TCs supply the real one.
        "jurisdiction": {
            "name": "Texas",
            "authority": "Public Utility Commission of Texas",
            "level": "state",
        },
        "kind": "per_meter",
        "per_meter_amount": "1.25",
    }
    payload.update(overrides)
    return payload


def test_br_rat_036__a_per_meter_tax_can_be_created_and_keeps_its_figure(env):
    with tenant_ctx(env.tenant):
        row = services.create_tax(env.admin, _per_meter_payload())
    assert row["kind"] == "per_meter"
    assert Decimal(row["per_meter_amount"]) == Decimal("1.25")
    # BR-RAT-087: the screen renders the DISPLAY string, never the stored figure.
    assert row["per_meter_amount_display"] == "1.25"


def test_br_rat_036__the_amount_is_required_because_a_form_without_its_figure_bills_nothing(env):
    with tenant_ctx(env.tenant), pytest.raises(errors.ValidationError) as raised:
        services.create_tax(
            env.admin, _per_meter_payload(**{"per_meter_amount": None})
        )
    assert any(
        error["field"] == "per_meter_amount" for error in raised.value.field_errors
    ), raised.value.field_errors


def test_br_rat_036__a_negative_per_meter_amount_is_refused(env):
    with tenant_ctx(env.tenant), pytest.raises(errors.ValidationError) as raised:
        services.create_tax(env.admin, _per_meter_payload(per_meter_amount="-1.25"))
    assert raised.value.code == errors.VAL_RANGE


def test_br_rat_036__per_meter_takes_no_unit_of_measure(env):
    """THE distinction, asserted rather than described.

    `per_unit` prices billed USAGE and hard rule 3 makes its unit mandatory.
    `per_meter` prices a COUNT OF METERS — a meter is not a measure of anything
    — so there is no unit to state and no column to state it in. A payload that
    tries is refused as an unknown field, not silently dropped.
    """
    with tenant_ctx(env.tenant), pytest.raises(errors.ValidationError) as raised:
        services.create_tax(env.admin, _per_meter_payload(per_meter_uom="meters"))
    assert any(
        error["field"] == "per_meter_uom" for error in raised.value.field_errors
    ), raised.value.field_errors


def test_br_rat_036__the_three_ratified_forms_are_untouched(env):
    """The amendment ADDS; it does not reshape what was already signed off."""
    with tenant_ctx(env.tenant):
        percent = env.tax("TX State", rate="0.0625")
        flat = env.tax("Filing fee", kind="flat_per_bill", flat_amount="2.00", rate=None)
        per_unit = env.tax(
            "Conservation levy",
            kind="per_unit",
            per_unit_amount="0.25",
            per_unit_uom="kgal",
            rate=None,
        )
    assert percent["kind"] == "percent" and Decimal(percent["rate"]) == Decimal("0.0625")
    assert flat["kind"] == "flat_per_bill"
    assert per_unit["per_unit_uom"] == "kgal"
    # And none of them acquired a per-meter figure by widening the model.
    for row in (percent, flat, per_unit):
        assert row["per_meter_amount"] is None


def test_br_rat_036__nothing_here_compounds(env):
    """DEF-381 is DEFERRED, not quietly delivered alongside this.

    The PO split the two explicitly. A per-meter tax has no compounding order
    and no base-of-another-tax selector, and this asserts the absence so a later
    reader cannot mistake the fourth FORM for the fourth BASE.
    """
    with tenant_ctx(env.tenant):
        row = services.create_tax(env.admin, _per_meter_payload())
    assert "compounds_on" not in row
    assert "compounding_order" not in row
    # B4.2's two bases are still the only two.
    assert row["base_includes_usage"] is True
    assert row["base_includes_base"] is True
