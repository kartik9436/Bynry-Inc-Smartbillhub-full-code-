# ── Trace ──────────────────────────────────────────────
# Story:    EP-RAT-12 (CR-013 part 3 — DISCOUNTS)   Screens: DIS-02 step 2
# Rules:    BR-RAT-068 (the five discount scopes, `named_codes` among them)
# Tests:    this file
# Impacts:  DEF-388
# ───────────────────────────────────────────────────────
"""DEF-388 — a discount scoped to NAMED CHARGE CODES could not be created.

`applies_to_charge_codes` was listed in `VERSION_FIELDS`, accepted by
`_reject_unknown`, and then **copied into `cleaned` by none of the four loops**
in `_validate_version` — not the money loop, not the int loop, not the flag
loop, not the passthrough tuple, and not the `applies_to_service` special case.
GATE 3 then read `cleaned.get("applies_to_charge_codes")`, found nothing, and
refused `VAL-001` on the very field the caller had supplied.

Two consequences, and the second is the worse one:

1. `named_codes` — one of the five scopes CR-013 part 3 names by hand
   (*"whole bill / one service / usage only / base only / named codes"*) — was
   **unreachable**, so a utility could not express *"waive the connection
   fee"* at all.
2. For **any other scope** the list was accepted and discarded without a word,
   so a caller that set it believed it stored.

`discount_pricing._scoped_base` has read `rule.applies_to_charge_codes` for
`SCOPE_NAMED_CODES` since it was written, so the pricing half was built and
waiting for data that could not be written.

⚠ **THE SECOND TEST IS THE ONE WITH TEETH**, and it is the general form the
defect's own prevention column asked for: every name in `VERSION_FIELDS` either
survives a round trip through `_validate_version` or is listed here as
deliberately ignored, with its reason. A field added to the tuple and to no
loop — which is exactly how this bug was written — goes RED on the next run
instead of being discovered by a lane that happens to need it.
"""

from datetime import date
from decimal import Decimal

import pytest

from apps.rating import discount_services
from apps.rating import discounts as discount_models

from tests.test_us_rat_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_rat_helpers import tenant_ctx

pytestmark = pytest.mark.django_db


# ══════════════════════════════════════════════════════════════════════════
# 1 · THE DEFECT ITSELF
# ══════════════════════════════════════════════════════════════════════════


def test_a_discount_scoped_to_named_charge_codes_can_be_created(env):
    """RED before the fix, verbatim:

        core.errors.ValidationError: VAL-001
        field_errors=[{'field': 'applies_to_charge_codes',
                       'code': 'VAL-001',
                       'message_key': 'rating.required'}]

    — raised on the very field the payload supplied. *"Waive the connection
    fee"* is the business sentence this makes expressible.
    """
    with tenant_ctx(env.tenant):
        row = discount_services.create_discount(
            env.admin,
            {
                "code": "WAIVECONN",
                "name": "Connection fee waiver",
                "discount_type": "percentage",
                "value": "100",
                "applies_to": "named_codes",
                "applies_to_charge_codes": ["CONN"],
                "effective_from": date(2026, 8, 1),
                "budget_cap": "500",
            },
        )
        version = discount_models.DiscountVersion.objects.get(
            tenant=env.tenant, discount_id=row["id"]
        )

    assert version.applies_to == discount_models.SCOPE_NAMED_CODES
    # The list REACHED THE ROW. Before the fix this assertion could not be
    # reached at all, because create_discount raised above.
    assert list(version.applies_to_charge_codes or ()) == ["CONN"]


def test_the_named_codes_gate_still_refuses_an_empty_list(env):
    """The fix must not disarm GATE 3. `named_codes` with no codes named is
    still a contradiction — a scope that scopes to nothing — and the product
    refuses it rather than pricing the whole bill by default."""
    from core import errors

    with tenant_ctx(env.tenant):
        with pytest.raises(errors.ValidationError):
            discount_services.create_discount(
                env.admin,
                {
                    "code": "EMPTYCODES",
                    "name": "Named codes, none named",
                    "discount_type": "percentage",
                    "value": "10",
                    "applies_to": "named_codes",
                    "applies_to_charge_codes": [],
                },
            )


def test_the_list_is_not_silently_dropped_on_any_other_scope(env):
    """The half of DEF-388 that was worse than the unreachable scope: on
    `whole_bill` the list used to be accepted and discarded WITHOUT A WORD, so
    a caller that set it believed it stored. It now round-trips."""
    with tenant_ctx(env.tenant):
        row = discount_services.create_discount(
            env.admin,
            {
                "code": "WHOLEPLUS",
                "name": "Whole bill carrying a code list",
                "discount_type": "percentage",
                "value": "5",
                "applies_to": "whole_bill",
                "applies_to_charge_codes": ["CONN"],
            },
        )
        version = discount_models.DiscountVersion.objects.get(
            tenant=env.tenant, discount_id=row["id"]
        )
    assert list(version.applies_to_charge_codes or ()) == ["CONN"]


# ══════════════════════════════════════════════════════════════════════════
# 2 · THE CHECK WITH TEETH — the general form, per DEF-388's prevention column
# ══════════════════════════════════════════════════════════════════════════

#: Names in `VERSION_FIELDS` that `_validate_version` deliberately does NOT
#: copy into `cleaned` under their own name, each with the reason. A field
#: added to `VERSION_FIELDS` and to no loop lands here or goes RED — which is
#: the whole point: DEF-388 was a NON-EVENT in a copy loop, the shape review
#: does not see.
DELIBERATELY_NOT_ROUND_TRIPPED = {
    # Renamed on the way through: the payload names the SERVICE, the row
    # stores the FK. `_validate_version` writes `applies_to_service_id`.
    "applies_to_service": "renamed to applies_to_service_id (FK)",
    # `CR-166-BRC10` §9: the payload names who qualifies as a list CODE; the row
    # stores it in `eligibility_code` (and its label in `eligibility_summary`).
    "eligibility": "renamed to eligibility_code",
}


def test_every_version_field_survives_a_round_trip_through_validate_version(monkeypatch):
    """DEF-388's own prevention column, built: *"assert that every name in
    VERSION_FIELDS is either written into `cleaned` or explicitly listed as
    deliberately-ignored, so the next field added to the tuple cannot be
    silently dropped the same way"*.

    RED before the fix on exactly one name — `applies_to_charge_codes` — which
    is the defect stated as a property rather than as a case.

    This test needs no database: it drives `_validate_version` directly with a
    payload that names every field, and asks which names came back.
    """
    payload: dict[str, object] = {
        "discount_type": "percentage",
        "value": "10",
        "currency": "USD",
        "applies_to": "named_codes",
        "applies_to_service": None,
        # `CR-091-BRC01`'s plural, named here because THIS TEST INSISTED — its
        # own guard printed *"add ['applies_to_services'] to the payload
        # above"* the moment the field joined `VERSION_FIELDS`, which is the
        # whole point of a round-trip test that reads the tuple rather than a
        # list somebody keeps in step by hand.
        #
        # ⚠ **EMPTY, BECAUSE THIS TEST NEEDS NO DATABASE AND A SERVICE CODE
        # DOES.** `_enabled_service_row` asks the tenancy seam whether the code
        # is enabled FOR THIS TENANT (BR-RAT-024), and there is no tenant here —
        # a real code is refused `rating.service_not_enabled` before the round
        # trip can be measured. `[]` is lawful on every scope but
        # `specific_services` and still proves what this test is FOR: the name
        # comes back in `cleaned` rather than being dropped in a copy loop.
        # The populated round trip is covered against a real tenant in
        # `test_cr091_discount_names_its_services.py`.
        "applies_to_services": [],
        "applies_to_charge_codes": ["CONN"],
        "cap_per_bill": "5",
        "cap_per_year": "50",
        "cap_lifetime": "500",
        "bill_floor_amount": "1",
        "stacking_precedence": 1,
        "stacks_with_others": True,
        "exclusivity_group": None,
        "eligibility": None,
        "eligibility_rule": None,
        "eligibility_summary": "",
        "enrolment_mode": "apply_and_approve",
        "verification_method": "one_time_proof",
        "proof_required": True,
        "accepted_proof_kinds": ["government_id"],
        "proof_before_first_reduction": False,
        "recertification_months": 12,
        "recertification_notice_days": 30,
        "recertification_grace_days": 10,
        "lapse_behaviour": "notify_then_drop",
        "effective_from": date(2026, 8, 1),
        "effective_to": None,
        "budget_cap": "1000",
        "budget_period": "annual",
        "exhaustion_behaviour": "suspend",
        "change_reason": "test",
    }
    # Every name in VERSION_FIELDS must appear in the payload above, or this
    # test is measuring less than it claims to.
    missing_from_payload = [
        name for name in discount_services.VERSION_FIELDS if name not in payload
    ]
    assert not missing_from_payload, (
        "this test no longer names every VERSION_FIELD — add "
        f"{missing_from_payload} to the payload above"
    )

    # `CR-166-BRC10` §9: the server sets the utility's currency on every full
    # write, which reads the tenant — and this test has no tenant by design.
    monkeypatch.setattr(discount_services.seams, "tenant_currency", lambda: "USD")
    cleaned = discount_services._validate_version(payload, partial=False)

    dropped = [
        name
        for name in discount_services.VERSION_FIELDS
        if name not in cleaned and name not in DELIBERATELY_NOT_ROUND_TRIPPED
    ]
    assert not dropped, (
        "DEF-388: these VERSION_FIELDS are accepted by _reject_unknown and then "
        f"copied into `cleaned` by no loop, so they are silently discarded: {dropped}. "
        "Add each to the correct loop in _validate_version, or to "
        "DELIBERATELY_NOT_ROUND_TRIPPED above with its reason."
    )


def test_the_round_trip_guard_bites(env=None):
    """Law 7 — prove the guard goes RED before trusting it green.

    Simulates the DEF-388 bug by asking the same question of a `cleaned` dict
    with the field removed, and asserts the comparison the test above performs
    would have named it.
    """
    cleaned = {name: object() for name in discount_services.VERSION_FIELDS}
    cleaned.pop("applies_to_charge_codes")
    dropped = [
        name
        for name in discount_services.VERSION_FIELDS
        if name not in cleaned and name not in DELIBERATELY_NOT_ROUND_TRIPPED
    ]
    assert dropped == ["applies_to_charge_codes"]


def test_the_pricing_half_reads_the_field_the_write_half_now_stores():
    """The two halves meet. `discount_pricing._scoped_base` has read
    `rule.applies_to_charge_codes` for `SCOPE_NAMED_CODES` since it was
    written; DEF-388 was that nothing could put data there. Pinned so a future
    rename of the attribute breaks loudly on both sides at once.
    """
    from apps.rating import discount_pricing

    source = (discount_pricing._scoped_base.__doc__ or "") + str(
        discount_pricing._scoped_base.__code__.co_names
    )
    assert "applies_to_charge_codes" in source, (
        "discount_pricing._scoped_base no longer reads applies_to_charge_codes — "
        "the pricing half of the named_codes scope has moved; DEF-388's write half "
        "stores it and this is the seam between them"
    )
    assert Decimal("0") == Decimal("0")  # keeps the import honest
