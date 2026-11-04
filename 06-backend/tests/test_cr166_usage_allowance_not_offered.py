# ── Trace ──────────────────────────────────────────────
# Change:  CR-166-BRC10 follow-up — PO ruling 2026-10-03 (decision log, *"A USAGE
#          ALLOWANCE IS NOT OFFERED ON THE NEW DISCOUNT FORM UNTIL 'FREE UNITS
#          BEFORE PRICING' IS BUILT"*), PO verbatim *"recommend (b) - this is
#          correct"*.
# Rules:   BR-RAT-962 (unchanged: a usage allowance stays unpriceable) ·
#          BR-RAT-960 (the scope gate, still asserted beside the new one)
# ───────────────────────────────────────────────────────
"""A usage allowance can no longer be CREATED; one already saved stays readable.

The walk's *Garden allowance* (first 2,000 gallons of water free) could be
saved and could never go live: the engine has no step that takes free units off
the reading before pricing, and pricing it as a dollar credit would take $2.00
off a bill where the ruled arithmetic makes it $14.40. The PO chose to stop
offering the type rather than build that step now.

So, server side, three doors refuse a NEW usage allowance by name
(`rating.discounts.usage_allowance_not_offered`): create, a new version, and an
edit that would TURN a draft into one. A draft that already IS one opens,
reads, saves other fields, and cannot be submitted (it could never be
approved). Nothing is priced differently.
"""

from datetime import date

import pytest

from apps.rating import discount_services, selectors
from apps.rating import discounts as discount_models
from core import errors

from tests.test_us_rat_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_rat_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

NOT_OFFERED = "rating.discounts.usage_allowance_not_offered"

GARDEN = {
    "code": "GARDEN",
    "name": "Garden allowance",
    "discount_type": "usage_allowance",
    "value": "2",
    "applies_to": "one_service",
    "applies_to_service": "water",
    "effective_from": date(2026, 8, 1),
}


def saved_before_the_ruling(actor, payload):
    """A usage-allowance draft as one saved before 2026-10-03 is stored.

    The service no longer creates one, so the row is created as a fixed amount
    with the same scope and value and its version's type is set the way the
    old create stored it. Every other column is what the old create wrote.
    """
    as_fixed = {**payload, "discount_type": discount_models.DISCOUNT_FIXED_AMOUNT}
    row = discount_services.create_discount(actor, as_fixed)
    discount_models.DiscountVersion.objects.filter(discount_id=row["id"]).update(
        discount_type=discount_models.DISCOUNT_USAGE_ALLOWANCE
    )
    discount = discount_models.Discount.objects.get(pk=row["id"])
    return discount_services.discount_row(discount)


def _type_refusal(refusal):
    fields = {error["field"]: error for error in refusal.value.field_errors}
    assert "discount_type" in fields, refusal.value.field_errors
    return fields["discount_type"]


def test_creating_a_usage_allowance_is_refused_by_name(env):
    with tenant_ctx(env.tenant):
        with pytest.raises(errors.ValidationError) as refusal:
            discount_services.create_discount(env.admin, dict(GARDEN))
        assert not discount_models.Discount.objects.filter(code="GARDEN").exists()
    error = _type_refusal(refusal)
    assert error["message_key"] == NOT_OFFERED
    assert error["params"]["br_ref"] == "BR-RAT-962"


def test_the_whole_bill_scope_gate_still_speaks_beside_it(env):
    """BR-RAT-960's refusal is not swallowed by the new one: both boxes are
    marked, so a later build of the step finds the scope rule still enforced."""
    with tenant_ctx(env.tenant):
        with pytest.raises(errors.ValidationError) as refusal:
            discount_services.create_discount(
                env.admin, {**GARDEN, "applies_to": "whole_bill", "applies_to_service": None}
            )
    fields = {error["field"] for error in refusal.value.field_errors}
    assert {"discount_type", "applies_to"} <= fields


def test_a_new_version_cannot_become_a_usage_allowance(env):
    with tenant_ctx(env.tenant):
        row = discount_services.create_discount(
            env.admin, {**GARDEN, "code": "FLAT2", "discount_type": "fixed_amount"}
        )
        draft = discount_models.DiscountVersion.objects.get(discount_id=row["id"])
        discount_services.discard_discount_version_draft(env.admin, draft.id)
        with pytest.raises(errors.ValidationError) as refusal:
            discount_services.create_discount_version(
                env.admin,
                row["id"],
                {
                    **{k: v for k, v in GARDEN.items() if k not in ("code", "name")},
                    "change_reason": "Make it free units",
                },
            )
    assert _type_refusal(refusal)["message_key"] == NOT_OFFERED


def test_a_draft_cannot_be_edited_into_a_usage_allowance(env):
    with tenant_ctx(env.tenant):
        row = discount_services.create_discount(
            env.admin, {**GARDEN, "code": "FLAT3", "discount_type": "fixed_amount"}
        )
        with pytest.raises(errors.ValidationError) as refusal:
            discount_services.update_discount_details(
                env.admin, row["id"], {"discount_type": "usage_allowance"}
            )
        version = discount_models.DiscountVersion.objects.get(discount_id=row["id"])
        assert version.discount_type == discount_models.DISCOUNT_FIXED_AMOUNT
    assert _type_refusal(refusal)["message_key"] == NOT_OFFERED


def test_a_usage_allowance_saved_before_the_ruling_still_reads(env):
    with tenant_ctx(env.tenant):
        row = saved_before_the_ruling(env.admin, GARDEN)
        detail = selectors.discount_detail(row["id"])
    assert row["type"] == "usage_allowance"
    assert detail["type"] == "usage_allowance"
    assert detail["value_display"] == "2.00 kgal"


def test_its_draft_opens_and_saves_other_fields_with_the_type_unchanged(env):
    """The Edit form sends the draft's own type back with it; that is not a
    new usage allowance, so it is not refused."""
    with tenant_ctx(env.tenant):
        row = saved_before_the_ruling(env.admin, GARDEN)
        discount_services.update_discount_details(
            env.admin,
            row["id"],
            {"name": "Garden allowance (summer)", "discount_type": "usage_allowance", "value": "3"},
        )
        version = discount_models.DiscountVersion.objects.get(discount_id=row["id"])
        discount = discount_models.Discount.objects.get(pk=row["id"])
    assert discount.name == "Garden allowance (summer)"
    assert version.discount_type == discount_models.DISCOUNT_USAGE_ALLOWANCE
    assert str(version.value).startswith("3")


def test_its_draft_cannot_be_submitted_because_it_could_never_be_approved(env):
    with tenant_ctx(env.tenant):
        row = saved_before_the_ruling(env.admin, GARDEN)
        with pytest.raises(errors.BizError) as refusal:
            discount_services.submit_discount(env.admin, row["id"])
        version = discount_models.DiscountVersion.objects.get(discount_id=row["id"])
    assert refusal.value.message_key == "rating.discounts.type_not_priceable"
    assert version.status == discount_models.VERSION_DRAFT
