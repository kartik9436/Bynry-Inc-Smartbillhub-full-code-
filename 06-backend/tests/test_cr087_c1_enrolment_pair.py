# ── Trace ──────────────────────────────────────────────
# Change:   CR-087 task C1 (PRB-14) — the impossible enrolment pair is refused
#           by the SERVER, and the refusal names BOTH fields that make it.
#           Screens: DIS-02 step 3 (`09-screen-inventory.md` §18 row 12)
# Rules:    BR-RAT-076 (automatic enrolment with mandatory proof is REFUSED,
#           never resolved) · CR-087 §6 C1 · CLAUDE.md hard-won law 14 (the
#           refusal path is proved on real PostgreSQL, not on the sqlite suite)
# Tests:    this file
# Impacts:  apps/rating/discount_services.py (GATE 1)
# ───────────────────────────────────────────────────────
"""The pair, refused at the server, on both doors, naming both halves.

⚠ **THE SCREEN STOPPED BEING ABLE TO EXPRESS THIS AND THAT IS NOT A REFUSAL.**
CR-087 C1 turns Enrolment into one dropdown of three real answers, so
*automatic* + *proof required* cannot be typed. A client that cannot express a
state is not a server that refuses it (`DEF-384`'s lesson on a different
endpoint), so the server keeps the gate — and this file is what proves the gate
is still there after the control that used to carry it is gone.

⚠ **WHAT MOVED IS *WHICH FIELDS THE REFUSAL NAMES*, AND IT MATTERS BECAUSE OF
THE DROPDOWN.** GATE 1 named `proof_required` alone. That was right when the
screen had a tick-box to point the message at; with one dropdown there is no
tick-box, and a refusal naming a field the form no longer draws is a refusal a
clerk cannot act on. Both halves make the contradiction, so the refusal names
both and a screen can highlight whichever control it actually has.
"""

import pytest

from apps.rating import api
from apps.rating import discounts as discount_models

from tests.test_us_rat_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_rat_helpers import FakeUser, api_call, tenant_ctx

pytestmark = pytest.mark.django_db


def _body(**overrides):
    body = {
        "code": "PAIRTEST",
        "name": "Senior discount",
        "discount_type": discount_models.DISCOUNT_PERCENTAGE,
        "value": "15",
        "applies_to": discount_models.SCOPE_WHOLE_BILL,
    }
    body.update(overrides)
    return body


def _field_errors(response):
    return {error["field"] for error in response.data["field_errors"]}


def test_the_pair_is_refused_on_create_and_the_refusal_names_both_fields(env):
    """A POST setting automatic + proof-required comes back 422 naming BOTH."""
    response = api_call(
        api.discounts,
        "post",
        data=_body(
            enrolment_mode=discount_models.ENROLMENT_AUTOMATIC,
            proof_required=True,
            accepted_proof_kinds=["government_id"],
        ),
        user=FakeUser(env.owner.id),
        role="system_admin",
        tenant=env.tenant,
    )
    assert response.status_code == 422
    fields = _field_errors(response)
    # BOTH halves make the contradiction. Naming one of them tells a clerk to
    # change that one, which is only half an instruction.
    assert "proof_required" in fields
    assert "enrolment_mode" in fields
    keys = {
        error["message_key"]
        for error in response.data["field_errors"]
        if error["field"] in ("proof_required", "enrolment_mode")
    }
    assert keys == {"rating.discounts.automatic_with_mandatory_proof"}


def test_the_pair_is_refused_on_the_edit_door_too(env):
    """`POST /discounts/{id}/versions` is the other way in — BR-RAT-078 makes an
    edit a new dated version, so it is a second door onto the same gate."""
    created = api_call(
        api.discounts,
        "post",
        data=_body(code="PAIRTEST2"),
        user=FakeUser(env.owner.id),
        role="system_admin",
        tenant=env.tenant,
    )
    assert created.status_code == 201
    discount_id = created.data["id"]

    response = api_call(
        api.discount_versions,
        "post",
        discount_id=discount_id,
        data={
            "discount_type": discount_models.DISCOUNT_PERCENTAGE,
            "value": "10",
            "applies_to": discount_models.SCOPE_WHOLE_BILL,
            "enrolment_mode": discount_models.ENROLMENT_AUTOMATIC,
            "proof_required": True,
            "accepted_proof_kinds": ["government_id"],
            "change_reason": "testing the pair",
        },
        user=FakeUser(env.owner.id),
        role="system_admin",
        tenant=env.tenant,
    )
    assert response.status_code == 422
    fields = _field_errors(response)
    assert {"proof_required", "enrolment_mode"} <= fields


def test_nothing_is_stored_when_the_pair_is_refused(env):
    """⚠ HARD-WON LAW 14. A refused row inside a PostgreSQL transaction poisons
    the whole transaction; on sqlite it does not. So this asserts the OUTCOME —
    no discount, no version — rather than trusting the status code alone."""
    response = api_call(
        api.discounts,
        "post",
        data=_body(
            code="PAIRTEST3",
            enrolment_mode=discount_models.ENROLMENT_AUTOMATIC,
            proof_required=True,
            accepted_proof_kinds=["government_id"],
        ),
        user=FakeUser(env.owner.id),
        role="system_admin",
        tenant=env.tenant,
    )
    assert response.status_code == 422
    with tenant_ctx(env.tenant):
        assert not discount_models.Discount.objects.filter(
            tenant=env.tenant, code="PAIRTEST3"
        ).exists()


def test_the_three_real_answers_still_save(env):
    """The dropdown's three options are the three combinations that mean
    something. Each must still save, or the gate has been widened into a wall."""
    cases = (
        ("AUTOOK", discount_models.ENROLMENT_AUTOMATIC, False, []),
        ("APPLYOK", discount_models.ENROLMENT_APPLY_AND_APPROVE, False, []),
        ("PROOFOK", discount_models.ENROLMENT_APPLY_AND_APPROVE, True, ["government_id"]),
    )
    for code, mode, proof, kinds in cases:
        response = api_call(
            api.discounts,
            "post",
            data=_body(
                code=code,
                enrolment_mode=mode,
                proof_required=proof,
                accepted_proof_kinds=kinds,
            ),
            user=FakeUser(env.owner.id),
            role="system_admin",
            tenant=env.tenant,
        )
        assert response.status_code == 201, (code, response.data)
