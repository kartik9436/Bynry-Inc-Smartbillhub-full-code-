# ── Trace ──────────────────────────────────────────────
# Change:   CR-171-BRC10 (move-in redesign) · P1.06 · P1.07 · P1.08, lane MVI-REQ
# Rules:    the PO's eight-status actions table of 2026-10-05 (decision log
#           "MOVE-IN REDESIGN: DETAILS-VIEW ACTIONS BY STATUS RULED AS
#           PROPOSED") · CR-171 §6.2 J1 (approve raises the pending job, no
#           account — BR-CUS-1077) · J2 (decline and ask keep their servers) ·
#           J3 (edit uses the Add form; request fields written back, the rest
#           parked, never approves) · BR-SHL-048 (a park changes nothing) ·
#           NFR-3 (every list pages on the server) · CLAUDE.md hard rules 1 · 7
# Question: OQ-CUS-12789 (Reopen on a declined request) — CLOSED 2026-10-05 → (a)
# Tests:    this file
# ───────────────────────────────────────────────────────
"""**The move-in details view's request half, proved through the doors it uses.**

A request that suggests a move-in is shown on the Move-ins list as *To approve*,
*Waiting on customer* or *Declined* (images 03–08), and its buttons work through
the request's OWN doors — `/approve`, `/refuse`, `/transitions` — plus three new
routes on the same surface: `/resend-ask` (image 05), `/messages` and `/audit`
(images 22, 23) and `/move-in-form` (image 47, J3). Nothing here is a second
writer of a service request.

RED-FIRST PROOF (law 7), in pytest — the harness that runs these. Written before
the code; first run: `ImportError: cannot import name 'move_in_request' from
'apps.customers'`. With the module in place and `resend_the_ask` not yet written,
the three resend cases failed and 17 passed. ⚠ **Those 17 were therefore never
seen red at birth, so each guard was broken by hand afterwards and seen red:**
park keeps the request's keys → `assert 'full_name' not in {'full_name': 'Verma,
Asha K.', …}`; `request_no` out of the carried keys → `assert 'MVI-26-0001' ==
'SR-26-0001'`; the audit page ignored → `assert 61 == 50`; the message ids
narrowed to the request → `assert 1 == 2`. Green on SQLite and on PostgreSQL 16
(`config.settings.pgtest`, 20 passed).

⚠ **WHAT WOULD MAKE THESE PASS WRONGLY** (law 7, habit 2):

  * **Asserting the response instead of the tables.** Every write case reads
    the row back — `MoveInJob`, `OutboundMessage`, `WizardPark`, the request.
  * **A resend that passes because the first ask's row is counted twice.** The
    resend case counts the queue BEFORE and AFTER and asserts the SAME body on a
    DIFFERENT row.
  * **A paging case that passes because the list was short.** The audit case
    writes 55 rows so page 1 holds 50 and page 2 holds the rest; an unpaged read
    would return 57 on page 1 and fail.
  * **A park that passes because it stored everything.** The save case asserts
    the request-owned keys are ABSENT from the park, not merely that the rest is
    present.
"""

from datetime import date

import pytest
from django.urls import resolve

from core import errors

from apps.customers import models as customers_models
from apps.customers import move_in_jobs, move_in_request
from apps.customers import service_request as rules
from apps.customers import service_request_api as api
from apps.customers import service_request_service as sr
from apps.notifications import models as notification_models
from apps.notifications import service_request_events
from apps.tenancy.models import WizardPark

from tests.test_br_cus_1077_move_in_job import _served_unit
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import audit_rows, brazos, dana, tenant_ctx  # noqa: F401
from tests.test_us_ten_helpers import api_call

pytestmark = pytest.mark.django_db

EMAIL = "asha.v@example.test"
DOC_ID = customers_models.ServiceRequestDocument.DOC_PROOF_OF_IDENTITY


def _capture(address):
    return {
        "channel": "counter",
        "applicant_kind": "person",
        "applicant_name": "Verma, Asha",
        "applicant_email": EMAIL,
        "applicant_phone": "(641) 555-0182",
        "address_as_given": address,
        "property_type": "standalone_owner_occupied",
        "requested_start": "2026-10-12",
        "what_they_said": "Moving into 4A",
    }


def _to_approve(actor, tenant, label="Unit 4A"):
    """A SUBMITTED request whose resolver found a served, vacant unit — the
    *To approve* row of image 03. No outcome is stored: the move-in view's
    Approve carries `outcome: move_in` itself (CR-171 S8)."""
    _premises, unit = _served_unit(actor, tenant, label=label)
    request = sr.create_request(actor, _capture(str(unit["unit_no"])))
    doc = sr.attach_document(
        actor, request.id, doc_type=DOC_ID, name="photo-id.jpg", storage_ref="s3://id"
    )
    sr.submit(actor, request.id)
    sr.resolve_address(actor, request.id)
    sr.link_customer(actor, request.id, customer_id=None)
    sr.verify_document(actor, doc.id)
    return sr.request_row(request.id), unit


def _post(view, path, request_id, data, tenant, actor):
    return api_call(
        view,
        "post",
        path,
        user=actor.user,
        role="system_admin",
        tenant=tenant,
        data=data,
        request_id=str(request_id),
    )


def _get(view, path, request_id, tenant, actor, query=None):
    return api_call(
        view,
        "get",
        path,
        user=actor.user,
        role="system_admin",
        tenant=tenant,
        query=query or {},
        request_id=str(request_id),
    )


def _queued(template_code):
    return list(
        notification_models.OutboundMessage.objects.filter(
            source_type=service_request_events.SOURCE_SERVICE_REQUEST,
            template_code=template_code,
        ).order_by("created_at", "id")
    )


# ═══════════════════════════════════════════════════════════════════════════
# 0 · LAW 2 — every new route is reachable through the root urlconf
# ═══════════════════════════════════════════════════════════════════════════
def test_every_new_request_route_resolves_through_the_root_urlconf():
    for path, view in (
        ("/api/brazos/service-requests/abc/resend-ask", api.service_request_resend_ask),
        ("/api/brazos/service-requests/abc/messages", api.service_request_messages),
        ("/api/brazos/service-requests/abc/audit", api.service_request_audit),
        ("/api/brazos/service-requests/abc/move-in-form", api.service_request_move_in_form),
    ):
        assert resolve(path).func is view, path


# ═══════════════════════════════════════════════════════════════════════════
# 1 · P1.06 — THE BUTTONS, THROUGH THE EXISTING DOORS
# ═══════════════════════════════════════════════════════════════════════════
def test_approve_from_the_view_raises_the_not_started_job_and_opens_no_account(brazos, dana):
    """J1 / `BR-CUS-1077`, today's rule kept: approving raises the PENDING
    move-in job (*Not started*, image 09) and opens no account. The modal sends
    `outcome: move_in` because on this view the kind is already decided."""
    with tenant_ctx(brazos):
        request, _unit = _to_approve(dana, brazos)
        assert request.outcome is None
        accounts_before = customers_models.Account.objects.count()

    response = _post(
        api.service_request_approve,
        f"/api/brazos/service-requests/{request.id}/approve",
        request.id,
        {"outcome": "move_in"},
        brazos,
        dana,
    )

    assert response.status_code == 200, response.data
    assert "raised" in response.data["job"], response.data["job"]
    with tenant_ctx(brazos):
        row = sr.request_row(request.id)
        assert row.state == rules.APPROVED
        assert row.outcome == "move_in"
        job = move_in_jobs.MoveInJob.objects.get(request_id=request.id)
        assert job.state == move_in_jobs.STATE_PENDING
        assert customers_models.Account.objects.count() == accounts_before


def test_decline_sends_the_one_text_as_the_letter_and_files_it_under_other(brazos, dana):
    """J2, image 19: *Reason \\** is the one required text and the EFFECT line
    says *The customer is told*. So the text is both the register's reason and
    the letter's body, and the utility files it under `other`."""
    told = "We cannot confirm the lease for Unit 4A."
    with tenant_ctx(brazos):
        request, _unit = _to_approve(dana, brazos)

    response = _post(
        api.service_request_refuse,
        f"/api/brazos/service-requests/{request.id}/refuse",
        request.id,
        {"reason": told, "reason_code": rules.REFUSAL_OTHER, "message_to_applicant": told},
        brazos,
        dana,
    )

    assert response.status_code == 200, response.data
    assert response.data["applicant_message"]["state"] == sr.ACK_QUEUED
    with tenant_ctx(brazos):
        row = sr.request_row(request.id)
        assert row.state == rules.REFUSED
        assert row.reason_code == rules.REFUSAL_OTHER
        assert row.refusal_message == told
        letters = _queued(service_request_events.TEMPLATE_REFUSED)
        assert [m.render_context["message_body"] for m in letters] == [told]
        assert letters[0].recipient_address == EMAIL


def test_the_refuse_door_needs_a_reason_and_does_not_need_a_code(brazos, dana):
    """**J2's contract check, recorded in CR-171 §9.** `reason` is REQUIRED
    (`REASON_REQUIRED`, TC-REQ-9); `reason_code` is OPTIONAL — absent, it is
    stored NULL and nothing is refused. A code outside the five is refused by
    name. Asserted here so the contract the CR quotes cannot drift silently."""
    with tenant_ctx(brazos):
        blank, _ = _to_approve(dana, brazos, label="Unit 1")
        no_code, _ = _to_approve(dana, brazos, label="Unit 2")
        bad_code, _ = _to_approve(dana, brazos, label="Unit 3")

    refused_blank = _post(
        api.service_request_refuse,
        f"/api/brazos/service-requests/{blank.id}/refuse",
        blank.id,
        {"reason": "  ", "reason_code": rules.REFUSAL_OTHER},
        brazos,
        dana,
    )
    assert refused_blank.status_code == 422
    no_code_answer = _post(
        api.service_request_refuse,
        f"/api/brazos/service-requests/{no_code.id}/refuse",
        no_code.id,
        {"reason": "No lease"},
        brazos,
        dana,
    )
    assert no_code_answer.status_code == 200
    unknown = _post(
        api.service_request_refuse,
        f"/api/brazos/service-requests/{bad_code.id}/refuse",
        bad_code.id,
        {"reason": "No lease", "reason_code": "not_a_reason"},
        brazos,
        dana,
    )
    assert unknown.status_code == 422
    with tenant_ctx(brazos):
        assert sr.request_row(blank.id).state == rules.SUBMITTED
        assert sr.request_row(no_code.id).reason_code is None
        assert sr.request_row(bad_code.id).state == rules.SUBMITTED


def test_ask_for_more_from_the_view_waits_on_the_customer_and_sends_the_text(brazos, dana):
    """Image 20: *What you need \\** — the one text — and *The request waits for
    the reply.* Through `/transitions` (`request_info`), the door every screen
    already calls."""
    need = "Please send the signed lease for Unit 4A."
    with tenant_ctx(brazos):
        request, _unit = _to_approve(dana, brazos)

    response = _post(
        api.service_request_transition,
        f"/api/brazos/service-requests/{request.id}/transitions",
        request.id,
        {"action": rules.REQUEST_INFO, "reason": need, "message_to_applicant": need},
        brazos,
        dana,
    )

    assert response.status_code == 200, response.data
    with tenant_ctx(brazos):
        row = sr.request_row(request.id)
        assert row.state == rules.MORE_INFO
        assert row.info_message == need
        assert [
            m.render_context["message_body"]
            for m in _queued(service_request_events.TEMPLATE_MORE_INFO)
        ] == [need]


def test_resend_the_ask_queues_the_same_words_again_and_moves_nothing(brazos, dana, audit_rows):
    """Image 05's *Resend the ask*. A SECOND queue row with the SAME body, the
    state untouched, no second state row on the timeline, and an audit row
    saying a resend happened (hard rule 7)."""
    need = "Please send the signed lease for Unit 4A."
    with tenant_ctx(brazos):
        request, _unit = _to_approve(dana, brazos)
        sr.ask_for_more(dana, request.id, reason=need, message_to_applicant=need)
        state_rows_before = customers_models.ServiceRequestEvent.objects.filter(
            request_id=request.id, kind=customers_models.ServiceRequestEvent.KIND_STATE
        ).count()

    response = _post(
        api.service_request_resend_ask,
        f"/api/brazos/service-requests/{request.id}/resend-ask",
        request.id,
        {"message_to_applicant": "a screen must not be able to change the words"},
        brazos,
        dana,
    )

    assert response.status_code == 200, response.data
    assert response.data["applicant_message"]["state"] == sr.ACK_QUEUED
    with tenant_ctx(brazos):
        rows = _queued(service_request_events.TEMPLATE_MORE_INFO)
        assert len(rows) == 2
        assert rows[0].id != rows[1].id
        assert [m.render_context["message_body"] for m in rows] == [need, need]
        assert sr.request_row(request.id).state == rules.MORE_INFO
        assert (
            customers_models.ServiceRequestEvent.objects.filter(
                request_id=request.id, kind=customers_models.ServiceRequestEvent.KIND_STATE
            ).count()
            == state_rows_before
        )
    resent = [r for r in audit_rows if r["action"] == "service_request.info_resent"]
    assert [str(r["entity_id"]) for r in resent] == [str(request.id)]


def test_resend_is_refused_unless_the_request_is_waiting_on_the_customer(brazos, dana):
    with tenant_ctx(brazos):
        request, _unit = _to_approve(dana, brazos)
        with pytest.raises(errors.BizError) as refused:
            sr.resend_the_ask(dana, request.id)
        assert refused.value.message_key == "customers.serviceRequest.transitionNotAllowed"
        assert refused.value.params["action"] == sr.RESEND_THE_ASK
        assert _queued(service_request_events.TEMPLATE_MORE_INFO) == []


def test_resending_an_ask_that_carried_no_message_queues_nothing_and_says_so(brazos, dana):
    with tenant_ctx(brazos):
        request, _unit = _to_approve(dana, brazos)
        sr.ask_for_more(dana, request.id, reason="Needs the lease")
        resent = sr.resend_the_ask(dana, request.id)
        assert resent.applicant_message["state"] == sr.ACK_NOT_SENT
        assert resent.applicant_message["reason"] == sr.APPLICANT_NO_INFO_MESSAGE
        assert _queued(service_request_events.TEMPLATE_MORE_INFO) == []


def test_the_view_offers_the_rulings_actions_for_each_request_status():
    """The PO's table of 2026-10-05, the three request rows of it — served so
    the list's pill, the details chip and the buttons read one answer."""
    assert move_in_request.request_status(rules.SUBMITTED) == "to_approve"
    assert move_in_request.request_status(rules.UNDER_REVIEW) == "to_approve"
    assert move_in_request.request_status(rules.MORE_INFO) == "waiting_on_customer"
    assert move_in_request.request_status(rules.REFUSED) == "declined"
    assert move_in_request.request_status(rules.APPROVED) is None
    assert move_in_request.request_actions(rules.SUBMITTED) == (
        "approve",
        "ask_for_more",
        "edit",
        "decline",
    )
    assert move_in_request.request_actions(rules.MORE_INFO) == (
        "approve",
        "resend_ask",
        "edit",
        "decline",
    )


def test_reopen_was_held_and_the_hold_has_expired():
    """**THE HOLD EXPIRED 2026-10-05 — `OQ-CUS-12789` CLOSED → (a).** This read
    `test_reopen_is_held_on_its_question_and_this_fires_when_the_hold_expires`
    and asserted a declined request offered nothing; it went red on the day the
    PO ruled, as law 2 intends. Reopen is built (lane MVI-FLOW) and proved in
    `test_cr171_reopen_declined_move_in.py`; here only the actions table and
    the scope (the generic table still has no reopen) are pinned."""
    assert move_in_request.request_actions(rules.REFUSED) == ("reopen",)
    assert rules.REOPEN not in rules.TRANSITIONS
    assert rules.MOVE_IN_TRANSITIONS[rules.REOPEN] == ((rules.REFUSED,), rules.SUBMITTED)


# ═══════════════════════════════════════════════════════════════════════════
# 2 · P1.07 — THE MESSAGES TAB AND THE AUDIT TAB
# ═══════════════════════════════════════════════════════════════════════════
def test_the_messages_tab_lists_every_letter_this_request_queued_newest_first(brazos, dana):
    """Image 22: Message · To · Channel · When · State. The acknowledgement
    (keyed on the request) and the ask (keyed on its timeline row) are both
    THIS request's, and another request's letters are not."""
    with tenant_ctx(brazos):
        request, _unit = _to_approve(dana, brazos)
        other, _ = _to_approve(dana, brazos, label="Unit 9")
        sr.ask_for_more(dana, request.id, reason="Lease", message_to_applicant="Send the lease.")

    response = _get(
        api.service_request_messages,
        f"/api/brazos/service-requests/{request.id}/messages",
        request.id,
        brazos,
        dana,
    )

    assert response.status_code == 200, response.data
    assert set(response.data) >= {"count", "next", "previous", "results"}
    rows = response.data["results"]
    assert response.data["count"] == 2
    assert [r["template_code"] for r in rows] == [
        service_request_events.TEMPLATE_MORE_INFO,
        service_request_events.TEMPLATE_ACKNOWLEDGEMENT,
    ]
    first = rows[0]
    assert first["channel"] == notification_models.CHANNEL_EMAIL
    assert first["to_name"] == "Verma, Asha"
    assert first["to_address"] == EMAIL
    assert first["status"]
    assert first["queued_at"]
    with tenant_ctx(brazos):
        ids = {r["id"] for r in rows}
        foreign = notification_models.OutboundMessage.objects.filter(source_id=str(other.id))
        assert foreign.exists()
        assert not ids & {str(m.id) for m in foreign}


def test_the_audit_tab_reads_the_requests_timeline_with_who_and_what(brazos, dana):
    """Image 23: When · Who · What, newest first, WHO as a name (B14 rule 31)."""
    with tenant_ctx(brazos):
        request, _unit = _to_approve(dana, brazos)
        sr.ask_for_more(dana, request.id, reason="Lease", message_to_applicant="Send the lease.")

    response = _get(
        api.service_request_audit,
        f"/api/brazos/service-requests/{request.id}/audit",
        request.id,
        brazos,
        dana,
    )

    assert response.status_code == 200, response.data
    rows = response.data["results"]
    assert rows[0]["at"] >= rows[-1]["at"]
    moved = [r for r in rows if r["kind"] == "state" and r["to_state"] == rules.MORE_INFO]
    assert len(moved) == 1
    assert moved[0]["actor_kind"] == "staff"
    assert moved[0]["actor_name"]
    assert all("actor" in r and "note_type" in r for r in rows)


def test_the_audit_filter_splits_messages_from_changes(brazos, dana):
    with tenant_ctx(brazos):
        request, _unit = _to_approve(dana, brazos)
        sr.ask_for_more(dana, request.id, reason="Lease", message_to_applicant="Send the lease.")

    def kinds(value):
        return _get(
            api.service_request_audit,
            f"/api/brazos/service-requests/{request.id}/audit",
            request.id,
            brazos,
            dana,
            query={"f.kind": value},
        ).data

    everything = kinds("all")
    messages = kinds("messages")
    changes = kinds("changes")
    assert messages["count"] >= 2  # the acknowledgement and the ask's letter
    assert all(move_in_request.is_message_event(r["note_type"]) for r in messages["results"])
    assert not any(move_in_request.is_message_event(r["note_type"]) for r in changes["results"])
    assert messages["count"] + changes["count"] == everything["count"]


def test_the_audit_tab_is_paged_on_the_server(brazos, dana):
    """NFR-3. Fifty-five notes: an unpaged read returns them all on page 1."""
    with tenant_ctx(brazos):
        request, _unit = _to_approve(dana, brazos)
        for n in range(55):
            sr.add_note(dana, request.id, note=f"note {n}")
        total = customers_models.ServiceRequestEvent.objects.filter(request_id=request.id).count()

    first = _get(
        api.service_request_audit,
        f"/api/brazos/service-requests/{request.id}/audit",
        request.id,
        brazos,
        dana,
    ).data
    second = _get(
        api.service_request_audit,
        f"/api/brazos/service-requests/{request.id}/audit",
        request.id,
        brazos,
        dana,
        query={"page": 2},
    ).data
    assert first["count"] == total
    assert len(first["results"]) == 50
    assert len(second["results"]) == total - 50
    assert not {r["id"] for r in first["results"]} & {r["id"] for r in second["results"]}


# ═══════════════════════════════════════════════════════════════════════════
# 3 · P1.08 — EDIT USES THE ADD FORM (J3)
# ═══════════════════════════════════════════════════════════════════════════
def _form(method, request_id, tenant, actor, data=None):
    return api_call(
        api.service_request_move_in_form,
        method,
        f"/api/brazos/service-requests/{request_id}/move-in-form",
        user=actor.user,
        role="system_admin",
        tenant=tenant,
        data=data,
        request_id=str(request_id),
    )


def test_the_edit_form_opens_filled_from_the_request(brazos, dana):
    with tenant_ctx(brazos):
        request, unit = _to_approve(dana, brazos)

    response = _form("get", request.id, brazos, dana)

    assert response.status_code == 200, response.data
    body = response.data
    assert body["request"]["request_no"] == request.request_no
    assert body["request"]["editable"] is True
    assert body["park_id"] is None
    values = body["values"]
    assert values["service_request_id"] == str(request.id)
    assert values["unit_id"] == str(unit["id"])
    assert values["opened_at"] == "2026-10-12"
    assert values["customer"]["full_name"] == "Verma, Asha"
    assert values["customer"]["email"] == EMAIL
    assert values["customer"]["phone"] == "(641) 555-0182"
    assert values["customer"]["customer_kind"] == "person"


def test_save_writes_the_requests_own_fields_back_and_parks_the_rest(brazos, dana):
    """J3. The applicant's name, phone and date go back ON THE REQUEST; the
    reads, the deposit and the field visit are parked; nothing is approved and
    no move-in number is spent (the park carries the request's own number)."""
    with tenant_ctx(brazos):
        request, unit = _to_approve(dana, brazos)
        parks_before = WizardPark.objects.count()
        jobs_before = move_in_jobs.MoveInJob.objects.count()
    form = _form("get", request.id, brazos, dana).data
    values = form["values"]
    values["customer"]["full_name"] = "Verma, Asha K."
    values["customer"]["phone"] = "(641) 555-0199"
    values["opened_at"] = "2026-10-19"
    values["reads"] = [{"asset_id": "m-1", "reading": "1043"}]
    values["deposit"] = {"choice": "first_bill"}
    values["field_visit"] = {"needed": True, "rows": []}

    saved = _form("put", request.id, brazos, dana, data={"step": 3, "values": values})

    assert saved.status_code == 200, saved.data
    with tenant_ctx(brazos):
        row = sr.request_row(request.id)
        assert row.applicant_name == "Verma, Asha K."
        assert row.applicant_phone == "(641) 555-0199"
        assert row.requested_start == date(2026, 10, 19)
        assert row.state == rules.SUBMITTED
        assert move_in_jobs.MoveInJob.objects.count() == jobs_before
        assert WizardPark.objects.count() == parks_before + 1
        park = WizardPark.objects.get(id=saved.data["park_id"])
        assert park.flow == "move_in"
        assert park.step == 3
        assert park.reference == request.request_no
        assert park.subject_ref["service_request_id"] == str(request.id)
        assert park.values["reads"] == [{"asset_id": "m-1", "reading": "1043"}]
        assert park.values["deposit"] == {"choice": "first_bill"}
        # The request's own facts are NOT copied into the park — one home each.
        assert "full_name" not in park.values.get("customer", {})
        assert "phone" not in park.values.get("customer", {})
        assert "opened_at" not in park.values
        assert "unit_id" not in park.values


def test_saving_twice_updates_the_one_park_and_reopening_merges_it(brazos, dana):
    with tenant_ctx(brazos):
        request, _unit = _to_approve(dana, brazos)
    values = _form("get", request.id, brazos, dana).data["values"]
    values["deposit"] = {"choice": "take"}
    first = _form("put", request.id, brazos, dana, data={"step": 2, "values": values}).data
    values["deposit"] = {"choice": "waive"}
    second = _form("put", request.id, brazos, dana, data={"step": 4, "values": values}).data

    assert first["park_id"] == second["park_id"]
    reopened = _form("get", request.id, brazos, dana).data
    assert reopened["park_id"] == first["park_id"]
    assert reopened["step"] == 4
    assert reopened["values"]["deposit"] == {"choice": "waive"}
    assert reopened["values"]["customer"]["full_name"] == "Verma, Asha"


def test_an_ssn_left_blank_on_the_form_is_not_cleared_on_the_request(brazos, dana):
    """The request serves only the last four of an SSN (BR-CUS-092), so the
    form opens with the box EMPTY; empty on save means *unchanged*."""
    with tenant_ctx(brazos):
        request, _unit = _to_approve(dana, brazos)
        sr.update_request(dana, request.id, {"ssn": "123-45-6789"})
        before = sr.request_row(request.id).ssn
        assert before
    values = _form("get", request.id, brazos, dana).data["values"]
    assert values["customer"]["ssn"] == ""
    _form("put", request.id, brazos, dana, data={"step": 2, "values": values})
    with tenant_ctx(brazos):
        assert sr.request_row(request.id).ssn == before


def test_edit_is_refused_once_the_request_is_decided_and_nothing_is_parked(brazos, dana):
    with tenant_ctx(brazos):
        request, _unit = _to_approve(dana, brazos)
        sr.refuse_request(dana, request.id, reason="No lease", reason_code=rules.REFUSAL_OTHER)
        parks_before = WizardPark.objects.count()
    form = _form("get", request.id, brazos, dana).data
    assert form["request"]["editable"] is False

    refused = _form("put", request.id, brazos, dana, data={"step": 1, "values": form["values"]})

    assert refused.status_code in (409, 422), refused.data
    with tenant_ctx(brazos):
        assert WizardPark.objects.count() == parks_before


def test_a_refused_write_back_parks_nothing(brazos, dana):
    """One transaction: a request field the writer refuses leaves no park."""
    with tenant_ctx(brazos):
        request, _unit = _to_approve(dana, brazos)
        parks_before = WizardPark.objects.count()
    values = _form("get", request.id, brazos, dana).data["values"]
    values["customer"]["dob"] = "not a date"
    values["deposit"] = {"choice": "take"}

    refused = _form("put", request.id, brazos, dana, data={"step": 2, "values": values})

    assert refused.status_code == 422, refused.data
    with tenant_ctx(brazos):
        assert WizardPark.objects.count() == parks_before
        assert sr.request_row(request.id).applicant_name == "Verma, Asha"
