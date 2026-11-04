# ── Trace ──────────────────────────────────────────────
# Change:   DEF-FLD-10579 (beta report MQ-026) — the phone never accepted a job,
#           so every item came back *accept the job first*. PO 2026-10-24
#           (decision log "MQ-026: STARTING A JOB ACCEPTS IT; A NOT-YET-STARTED
#           JOB CAN BE DECLINED WITH A REASON"): the first Start accepts; a job
#           not yet started may be declined with a reason.
# Rules:    BR-WRK-059 (the captor holds AND accepted the job; the session is
#           only the courier) · BR-WRK-025 (decline keeps the job; moving it is
#           the dispatcher's) · hard rule 7 (audited) · HR-1 (404)
# Code:     apps/work/api.py (`mobile_accept`, `mobile_decline` read
#           `capture_token` through `mobile.door_actor`) · apps/work/mobile.py
#           (`_job_card` carries `technician_acceptance`; `decline_job` keeps a
#           note as hand-back does)
# ───────────────────────────────────────────────────────
"""The accept and decline doors take the captor's token, so the phone can queue
them offline like every other own-door act; the card says where the job stands."""

from __future__ import annotations

import pytest

from apps.work import api, mobile
from apps.work import connection_models as work_tables

from tests.test_cr187_gaps import _call, _token
from tests.test_cr187_order_helpers import person, template
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana · audit_rows
from tests.test_us_met_helpers import field_actor, tenant_ctx
from tests.test_us_wrk_032_copies import _raise

pytestmark = pytest.mark.django_db


def _assigned_not_accepted(dana, brazos):
    """A raised job held by the field technician, NOT yet accepted — the beta's WO-0028."""
    oid = _raise(dana, brazos, template(dana, brazos))["id"]
    return oid, field_actor(oid, dana)


def _order(oid):
    return work_tables.WorkOrder.objects.get(pk=oid)


def test_an_accept_carried_by_another_login_is_the_captors_and_audited_once(brazos, dana, audit_rows):
    """Dana pressed Start in a basement; Sam's login carries it upstairs. The
    stamp says Dana, and a resend (the outbox's lost answer) stamps nothing new."""
    with tenant_ctx(brazos):
        oid, tech = _assigned_not_accepted(dana, brazos)
        token = _token(tech)
        _s, sam = person(brazos, "sam@field.test", "Sam Ng")
        first = _call(api.mobile_accept, brazos, sam, {"capture_token": token}, order_id=oid)
        again = _call(api.mobile_accept, brazos, sam, {"capture_token": token}, order_id=oid)
        row = _order(oid)
        holder = work_tables.WorkOrder.objects.get(pk=oid).assignee_technician_id
    assert first.status_code == 200, first.data
    assert first.data["technician_acceptance"]["state"] == "accepted"
    assert again.data["technician_acceptance"]["at"] == first.data["technician_acceptance"]["at"]
    assert row.accepted_by_technician_id == holder
    accepted = [r for r in audit_rows if r["action"] == "work.order.technician_accepted"]
    assert len(accepted) == 1 and str(accepted[0]["actor_user_id"]) == str(tech.id)


def test_the_accept_ends_accept_the_job_first(brazos, dana):
    """BR-WRK-059 — before the accept the sync refuses the captor's item by
    name; after it, nothing stands in the way."""
    with tenant_ctx(brazos):
        oid, tech = _assigned_not_accepted(dana, brazos)
        technician = mobile.technician_of(tech)
        before = mobile.state_reason_for(technician, oid)
        _call(api.mobile_accept, brazos, tech, {"capture_token": _token(tech)}, order_id=oid)
        after = mobile.state_reason_for(technician, oid)
    assert before == "work.mobile.accept_the_job_first"
    assert after is None


@pytest.mark.parametrize("door", ["accept", "decline"])
def test_a_bad_token_is_refused_never_downgraded_to_the_session(brazos, dana, door):
    with tenant_ctx(brazos):
        oid, tech = _assigned_not_accepted(dana, brazos)
        token = _token(tech)[:-4] + "AAAA"
        view = api.mobile_accept if door == "accept" else api.mobile_decline
        answer = _call(view, brazos, tech, {"reason": "time", "capture_token": token}, order_id=oid)
        row = _order(oid)
    assert answer.status_code == 403, answer.data
    assert answer.data["message_key"] == "work.mobile.capture_token_invalid"
    assert row.accepted_at_technician is None and row.declined_at is None


def test_a_decline_carried_by_another_login_is_the_captors_and_keeps_the_note(brazos, dana, audit_rows):
    """*Other* + a note, queued offline and carried by Sam: the board reads
    *other — Van in the shop*, the job stays Dana's, and the token never
    reaches the stored reason."""
    with tenant_ctx(brazos):
        oid, tech = _assigned_not_accepted(dana, brazos)
        token = _token(tech)
        _s, sam = person(brazos, "sam@field.test", "Sam Ng")
        holder = _order(oid).assignee_technician_id
        answer = _call(
            api.mobile_decline, brazos, sam,
            {"reason": "other", "note": "Van in the shop", "capture_token": token}, order_id=oid,
        )
        row = _order(oid)
    assert answer.status_code == 200, answer.data
    assert answer.data["technician_acceptance"]["state"] == "declined"
    assert row.declined_reason == "other — Van in the shop"
    assert row.assignee_technician_id == holder
    declined = [r for r in audit_rows if r["action"] == "work.order.technician_declined"]
    assert len(declined) == 1 and str(declined[0]["actor_user_id"]) == str(tech.id)


def test_a_decline_without_a_note_stores_the_reason_alone(brazos, dana):
    with tenant_ctx(brazos):
        oid, tech = _assigned_not_accepted(dana, brazos)
        mobile.decline_job(tech, oid, {"reason": "time"})
        assert _order(oid).declined_reason == "time"


def test_a_decline_after_the_start_is_refused(brazos, dana):
    """Once started (accepted) the way out is Hand back, not Decline."""
    from core import errors

    with tenant_ctx(brazos):
        oid, tech = _assigned_not_accepted(dana, brazos)
        mobile.accept_job(tech, oid)
        with pytest.raises(errors.BizError) as refused:
            mobile.decline_job(tech, oid, {"reason": "time"})
    assert refused.value.message_key == "work.mobile.job_already_accepted"


def test_the_card_says_where_the_job_stands(brazos, dana):
    """The change feed's card carries `technician_acceptance`, so a phone that
    was not the one to accept or decline still shows it right."""
    with tenant_ctx(brazos):
        oid, tech = _assigned_not_accepted(dana, brazos)
        pending = mobile._job_card(_order(oid), None)["technician_acceptance"]
        mobile.accept_job(tech, oid)
        accepted = mobile._job_card(_order(oid), None)["technician_acceptance"]
        other, other_tech = _assigned_not_accepted(dana, brazos)
        mobile.decline_job(other_tech, other, {"reason": "unsafe"})
        declined = mobile._job_card(_order(other), None)["technician_acceptance"]
    assert pending == {"state": "pending", "at": None, "reason": None}
    assert accepted["state"] == "accepted" and accepted["at"]
    assert declined["state"] == "declined" and declined["reason"] == "unsafe"


def test_without_a_token_the_session_is_the_actor_as_before(brazos, dana):
    """Rule 1, additive: an accept with no body is the signed-in technician's."""
    with tenant_ctx(brazos):
        oid, tech = _assigned_not_accepted(dana, brazos)
        answer = _call(api.mobile_accept, brazos, tech, {}, order_id=oid)
    assert answer.status_code == 200, answer.data
    assert answer.data["technician_acceptance"]["state"] == "accepted"
