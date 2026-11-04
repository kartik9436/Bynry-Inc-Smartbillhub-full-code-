"""`DEF-CUS-6427` — Edit on a service request: the SERVER half.

PO ruling 2026-09-23, verbatim: *"if user makes mistake while filling t new
request form then system should allow to correct it using edit , there is no
edit available on list view as wellas detail view"*. The decision log entry of
that date (*"THE PO ASKS FOR *EDIT* ON A SERVICE REQUEST, AND WHY IT CANNOT BE
THE NEXT THING WIRED"*) sets which requests are editable — Draft, Submitted,
Under review, More info needed — and says every edit writes `audit_log` with
the before and the after (hard rule 7).

What this file holds, each asserted the way it can fail:

  1. **A PATCH that carries one key changes one column.** The capture wizard
     now sends only what changed (`changedCapturePayload`); this proves the
     server's half of that promise — `update_request` is `partial=True`, so a
     key it is not sent is a column it does not touch. SSN and email survive a
     phone correction byte for byte.
  2. **The audit row records exactly that before → after**, and a masked
     identifier is recorded MASKED — `•••••5236`, never the number.
  3. **An approved request refuses the edit IN WORDS** (`approvedNoEdit`), and
     writes nothing — not the column, not an audit row. Before this fix the
     gate was `is_terminal` alone, which let `approved`, `in_fulfilment` and
     `on_hold` take a PATCH without a word.
  4. **The server's list and the screen's list are the same four states**,
     read out of `serviceRequestEditDoor.tsx`, so the door a clerk sees and the
     refusal the server gives cannot drift apart.
"""

import pathlib
import re

import pytest

from apps.customers import models as customers_models
from apps.customers import service_request as rules
from apps.customers import service_request_api as api
from apps.customers import service_request_service as sr
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import audit_rows, brazos, dana, tenant_ctx  # noqa: F401
from tests.test_us_ten_helpers import api_call

pytestmark = pytest.mark.django_db

SSN = "123-45-5236"
CAPTURE = {
    "channel": "walk_in",
    "applicant_kind": "person",
    "applicant_name": "Dana Whitfield",
    "applicant_email": "dana.whitfield@example.test",
    "applicant_phone": "512-555-0100",
    "ssn": SSN,
    "address_as_given": "212 Balcones Drive",
}


def _submitted(actor):
    request = sr.create_request(actor, dict(CAPTURE))
    sr.submit(actor, request.id)
    return sr.request_row(request.id)


def _patch(brazos, dana, request_id, data):  # noqa: F811
    return api_call(
        api.service_request_item,
        "patch",
        f"/api/brazos/service-requests/{request_id}",
        user=dana.user,
        role="billing_clerk",
        tenant=brazos,
        data=data,
        request_id=str(request_id),
    )


def _updated_rows(audit_rows, request_id):  # noqa: F811
    """The `service_request.updated` rows for ONE request, as the sink received
    them — i.e. exactly what `core.audit.write_row` hands the store."""
    return [
        row
        for row in audit_rows
        if row["action"] == "service_request.updated" and str(row["entity_id"]) == str(request_id)
    ]


# ══════════════════════════════════════════════════════════════════════════
# 1 · ONE KEY SENT, ONE COLUMN CHANGED
# ══════════════════════════════════════════════════════════════════════════
def test_a_phone_correction_on_a_submitted_request_leaves_ssn_and_email_intact(
    brazos, dana  # noqa: F811
):
    with tenant_ctx(brazos):
        request = _submitted(dana)
        request_id = request.id
    response = _patch(brazos, dana, request_id, {"applicant_phone": "512-555-0199"})
    assert response.status_code == 200, response.data
    with tenant_ctx(brazos):
        row = sr.request_row(request_id)
        assert row.applicant_phone == "512-555-0199"
        assert row.applicant_email == "dana.whitfield@example.test"
        assert row.ssn == SSN  # decrypted through the field — unchanged
        assert row.applicant_name == "Dana Whitfield"
    # What the screen reads back is the last four, and it is still 5236.
    assert response.data["applicant"]["identifier"]["ssn_last4"] == "5236"


# ══════════════════════════════════════════════════════════════════════════
# 2 · THE AUDIT ROW — before and after, masked where the value is sensitive
# ══════════════════════════════════════════════════════════════════════════
def test_every_edit_writes_its_before_and_after_and_nothing_else(
    brazos, dana, audit_rows  # noqa: F811
):
    with tenant_ctx(brazos):
        request_id = _submitted(dana).id
    _patch(brazos, dana, request_id, {"applicant_phone": "512-555-0199"})
    rows = _updated_rows(audit_rows, request_id)
    assert len(rows) == 1
    assert rows[0]["before"] == {"applicant_phone": "512-555-0100"}
    assert rows[0]["after"] == {"applicant_phone": "512-555-0199"}


def test_a_new_ssn_is_audited_masked_on_both_sides(brazos, dana, audit_rows):  # noqa: F811
    with tenant_ctx(brazos):
        request_id = _submitted(dana).id
    _patch(brazos, dana, request_id, {"ssn": "987-65-4321"})
    with tenant_ctx(brazos):
        assert sr.request_row(request_id).ssn == "987-65-4321"
    rows = _updated_rows(audit_rows, request_id)
    assert len(rows) == 1
    blob = f"{rows[0]['before']} {rows[0]['after']}"
    assert str(rows[0]["before"]["ssn"]).endswith("5236")
    assert str(rows[0]["after"]["ssn"]).endswith("4321")
    for secret in ("123-45-5236", "123455236", "987-65-4321", "987654321"):
        assert secret not in blob


# ══════════════════════════════════════════════════════════════════════════
# 3 · AFTER APPROVAL — refused in words, nothing written
# ══════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("state", ["approved", "in_fulfilment", "on_hold"])
def test_an_approved_request_refuses_an_edit_by_name_and_writes_nothing(
    brazos, dana, audit_rows, state  # noqa: F811
):
    with tenant_ctx(brazos):
        request_id = _submitted(dana).id
        customers_models.ServiceRequest.objects.filter(id=request_id).update(state=state)
    response = _patch(brazos, dana, request_id, {"applicant_phone": "512-555-0199"})
    assert response.status_code == 409, response.data
    assert response.data["message_key"] == "customers.serviceRequest.approvedNoEdit"
    with tenant_ctx(brazos):
        assert sr.request_row(request_id).applicant_phone == "512-555-0100"
    assert _updated_rows(audit_rows, request_id) == []


def test_a_refused_request_keeps_its_closed_refusal(brazos, dana):  # noqa: F811
    with tenant_ctx(brazos):
        request_id = _submitted(dana).id
        customers_models.ServiceRequest.objects.filter(id=request_id).update(state="refused")
        with pytest.raises(errors.BizError) as caught:
            sr.update_request(dana, request_id, {"applicant_phone": "512-555-0199"})
    assert caught.value.message_key == "customers.serviceRequest.terminalNoEdit"


@pytest.mark.parametrize(
    "write",
    [
        lambda actor, rid: sr.set_services(actor, rid, ["water"]),
        lambda actor, rid: sr.set_customer_category(actor, rid, account_type_code="residential"),
    ],
    ids=["services", "category"],
)
def test_the_wizards_other_writes_are_refused_after_approval_too(brazos, dana, write):  # noqa: F811
    """The capture wizard saves through three doors — the PATCH, the category
    and the services. Gating only the PATCH would leave the other two open on
    an approved request, so all three ask the same question."""
    with tenant_ctx(brazos):
        request_id = _submitted(dana).id
        customers_models.ServiceRequest.objects.filter(id=request_id).update(state="approved")
        with pytest.raises(errors.BizError) as caught:
            write(dana, request_id)
    assert caught.value.message_key == "customers.serviceRequest.approvedNoEdit"


@pytest.mark.parametrize("state", ["submitted", "under_review", "more_info"])
def test_still_being_worked_means_still_editable(brazos, dana, state):  # noqa: F811
    with tenant_ctx(brazos):
        request_id = _submitted(dana).id
        customers_models.ServiceRequest.objects.filter(id=request_id).update(state=state)
    response = _patch(brazos, dana, request_id, {"applicant_email": "dana@example.test"})
    assert response.status_code == 200, response.data
    with tenant_ctx(brazos):
        assert sr.request_row(request_id).applicant_email == "dana@example.test"


# ══════════════════════════════════════════════════════════════════════════
# 4 · THE SCREEN'S LIST IS THE SERVER'S LIST
# ══════════════════════════════════════════════════════════════════════════
def test_the_editable_states_match_the_screens_door():
    source = (
        pathlib.Path(__file__).resolve().parents[2]
        / "07-frontend/src/features/customers/serviceRequestEditDoor.tsx"
    ).read_text(encoding="utf-8")
    match = re.search(r"EDITABLE_REQUEST_STATES = \[([^\]]*)\]", source)
    assert match is not None, "the screen's list moved — re-point this test, do not delete it"
    screen = tuple(re.findall(r'"([a-z_]+)"', match.group(1)))
    assert screen == rules.EDITABLE_STATES
