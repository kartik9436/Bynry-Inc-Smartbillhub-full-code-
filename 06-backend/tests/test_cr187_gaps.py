# ── Trace ──────────────────────────────────────────────
# Change:   CR-187-BRC10 lane S-GAPS — the server-shaped gaps the decision log
#           entry *"Field app: every expired hold released, eight proof
#           defects fixed"* listed as known limits.
# Rules:    `07-endpoints.md` §0 rule 7 (every mutating route is idempotent on a
#           key minted AT CAPTURE; a repeat answers duplicate) · rule 10 (a
#           technician sees only their own: 404) · BR-WRK-059 / BR-WRK-060 (the
#           capture token: the act is the captor's, whoever is the courier) ·
#           BR-FLD-00008 / 00009 / 00010 (R8, R9, R10) · FF-29 (*Correct their
#           time*, the ×) · US-FLD-020 TC-3 · hard rules 1, 4's shape, 7
# Code:     apps/work/mobile.py (`field_act`, `door_actor`) ·
#           apps/work/field_dispatch.py (`hand_back`) ·
#           apps/work/field_labour.py (`member_leaves`, `record_time`,
#           `crew_door`) · apps/work/api.py + field_orders_api.py (the doors)
#           · apps/work/migrations/0047_cr187_assignment_capture_key.py
# ───────────────────────────────────────────────────────
"""The acts and hand-back doors are idempotent; the own doors take a capture
token; the lead stops and corrects a helper's clock.

The PostgreSQL half (RLS still FORCEd, the append-only trigger still refusing,
the key race caught by a savepoint) is `test_cr187_gaps_pg.py`."""

from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.utils import timezone

from apps.work import dispatch, field_dispatch, field_labour, mobile
from apps.work import models as work_models
from apps.work.field_order_models import WorkFieldRaise, WorkOrderLabour
from core import errors

from tests.test_cr187_order_helpers import FIX, job, order, person, template
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_wrk_032_copies import _raise

pytestmark = pytest.mark.django_db


def _iso(dt):
    return dt.isoformat()


def _rows(oid, act):
    return work_models.WorkOrderAssignment.objects.filter(work_order_id=oid, act=act).count()


def _held_by(dana, brazos, email="dana.o@field.test", name="D. Ortiz"):
    """A raised job given to a fresh technician who has accepted it."""
    oid = _raise(dana, brazos, template(dana, brazos))["id"]
    tech_row, tech = person(brazos, email, name)
    dispatch.record_act(dana, oid, {"act": "assign", "technician_id": str(tech_row.id)}, push=False)
    mobile.accept_job(tech, oid)
    return oid, tech_row, tech


# ══════════════════════════════════════════════════════════════════════════
# 1 · depart / arrive — idempotent on the outbox key
# ══════════════════════════════════════════════════════════════════════════
def test_a_resent_depart_answers_duplicate_and_appends_nothing(brazos, dana, audit_rows):
    """The lost answer: the phone sends *depart* again with the same key. One
    row, one audit row, and the second answer says `duplicate: true`."""
    with tenant_ctx(brazos):
        oid, tech = job(dana, brazos)
        first = mobile.field_act(tech, oid, {"act": "depart", "key": "k-depart-1"})
        again = mobile.field_act(tech, oid, {"act": "depart", "key": "k-depart-1"})
        departs = _rows(oid, "depart")
        stored = work_models.WorkOrderAssignment.objects.get(key="k-depart-1")
    assert first["duplicate"] is False and again["duplicate"] is True
    assert again["assignment_id"] == first["assignment_id"] == str(stored.id)
    assert again["act"] == "depart" and departs == 1
    assert len([r for r in audit_rows if r["action"] == "work.order.depart"]) == 1


def test_a_replayed_depart_is_a_duplicate_even_after_the_job_moved_on(brazos, dana):
    """The resend arrives after *arrive* moved the job on site — it is still
    the act already recorded, never a second depart and never a refusal."""
    with tenant_ctx(brazos):
        oid, tech = job(dana, brazos)
        mobile.field_act(tech, oid, {"act": "depart", "key": "k-d"})
        mobile.field_act(tech, oid, {"act": "arrive", "key": "k-a"})
        late = mobile.field_act(tech, oid, {"act": "depart", "key": "k-d"})
        state = order(oid).dispatch_state
    assert late["duplicate"] is True and _rows(oid, "depart") == 1
    assert state == "on_site"


def test_without_a_key_each_send_is_its_own_act_as_before(brazos, dana):
    """An older handset sends no key: unchanged — rule 1, additive only."""
    with tenant_ctx(brazos):
        oid, tech = job(dana, brazos)
        mobile.field_act(tech, oid, {"act": "depart"})
        mobile.field_act(tech, oid, {"act": "depart"})
        assert _rows(oid, "depart") == 2


def test_a_key_is_the_callers_own_on_this_job(brazos, dana):
    """Somebody else's key, or this caller's key replayed on another job, is
    the not-found an absent job gets (HR-1) — never *duplicate*."""
    with tenant_ctx(brazos):
        oid, tech = job(dana, brazos)
        mobile.field_act(tech, oid, {"act": "depart", "key": "k-mine"})
        other_oid, other_row, other = _held_by(dana, brazos, "sam@field.test", "Sam Ng")
        with pytest.raises(errors.NotFoundError):
            mobile.field_act(other, other_oid, {"act": "depart", "key": "k-mine"})
        second_oid = _raise(dana, brazos, template(dana, brazos))["id"]
        tech_row = work_models.Technician.objects.get(user_id=tech.id)
        dispatch.record_act(
            dana, second_oid, {"act": "assign", "technician_id": str(tech_row.id)}, push=False
        )
        with pytest.raises(errors.NotFoundError):
            mobile.field_act(tech, second_oid, {"act": "depart", "key": "k-mine"})
        assert _rows(other_oid, "depart") == 0 and _rows(second_oid, "depart") == 0


def test_the_office_door_never_reads_a_key_from_its_body(brazos, dana):
    """The key is an ARGUMENT of `record_act`, not a body field: the office's
    assignment door is unchanged by this lane."""
    with tenant_ctx(brazos):
        oid, tech = job(dana, brazos)
        dispatch.record_act(dana, oid, {"act": "schedule", "key": "office-key"}, push=False)
        assert not work_models.WorkOrderAssignment.objects.filter(key="office-key").exists()


# ══════════════════════════════════════════════════════════════════════════
# 2 · hand-back — idempotent on the outbox key
# ══════════════════════════════════════════════════════════════════════════
def test_a_resent_hand_back_answers_duplicate_not_a_404(brazos, dana, audit_rows):
    """The first send took the job off the technician, so before the key a
    resend met a job that was no longer theirs and FF-50 showed a 404 over a
    hand-back that had worked."""
    with tenant_ctx(brazos):
        oid, tech_row, tech = _held_by(dana, brazos)
        first = field_dispatch.hand_back(tech, oid, {"reason": "Van broke down", "key": "hb-1"})
        again = field_dispatch.hand_back(tech, oid, {"reason": "Van broke down", "key": "hb-1"})
        unassigns = work_models.WorkOrderAssignment.objects.filter(
            work_order_id=oid, act="unassign"
        ).count()
    assert first["duplicate"] is False and again["duplicate"] is True
    assert again["reason"] == first["reason"] == "Van broke down"
    assert again["handed_back_by"] == first["handed_back_by"]
    assert again["assigned"] is False and unassigns == 1
    assert len([r for r in audit_rows if r["action"] == "work.order.handed_back"]) == 1


def test_a_hand_back_key_is_the_technicians_own_on_this_job(brazos, dana):
    with tenant_ctx(brazos):
        oid, tech_row, tech = _held_by(dana, brazos)
        field_dispatch.hand_back(tech, oid, {"reason": "Too far", "key": "hb-own"})
        _s, stranger = person(brazos, "sam@field.test", "Sam Ng")
        with pytest.raises(errors.NotFoundError):
            field_dispatch.hand_back(stranger, oid, {"reason": "x", "key": "hb-own"})
        # A depart's key replayed as a hand-back is not a hand-back.
        oid2, _r2, tech2 = _held_by(dana, brazos, "lee@field.test", "J. Lee")
        mobile.field_act(tech2, oid2, {"act": "depart", "key": "dep-as-hb"})
        with pytest.raises(errors.NotFoundError):
            field_dispatch.hand_back(tech2, oid2, {"reason": "x", "key": "dep-as-hb"})
        assert order(oid2).assignee_technician_id is not None


# ══════════════════════════════════════════════════════════════════════════
# 3 · the capture token on the own doors (through the VIEWS)
# ══════════════════════════════════════════════════════════════════════════
def _call(view, tenant, courier, data, method="post", **kwargs):
    """A request to a field door, signed in as `courier` (the session)."""
    from rest_framework.test import APIRequestFactory, force_authenticate

    from apps.identity import models as identity_models

    factory = APIRequestFactory()
    request = getattr(factory, method)("/api/brazosbend/work/mobile/x", data, format="json")
    force_authenticate(request, user=identity_models.User.objects.get(pk=courier.id))
    request.tenant_role = "field_technician"
    request.tenant_id = tenant.id
    return view(request, **kwargs)


def _token(actor):
    return mobile.issue_capture_token(actor)["capture_token"]


def test_a_depart_carried_by_another_login_is_written_as_its_captor(brazos, dana):
    """BR-WRK-059 — Dana captured *depart* in the basement; Sam is signed in
    upstairs when it sends. The row says Dana; the session was the courier."""
    from apps.work import api

    with tenant_ctx(brazos):
        oid, tech = job(dana, brazos)
        token = _token(tech)
        _s, sam = person(brazos, "sam@field.test", "Sam Ng")
        answer = _call(
            api.mobile_act, brazos, sam,
            {"act": "depart", "key": "tok-dep", "capture_token": token}, order_id=oid,
        )
        row = work_models.WorkOrderAssignment.objects.get(key="tok-dep")
        refused = _call(api.mobile_act, brazos, sam, {"act": "depart", "key": "no-tok"}, order_id=oid)
    assert answer.status_code == 200, answer.data
    assert str(row.actor_id) == str(tech.id)
    # Without the token Sam is himself, and it is not Sam's job (HR-1).
    assert refused.status_code == 404


@pytest.mark.parametrize("which", ["expired", "forged"])
def test_a_bad_capture_token_is_refused_never_downgraded_to_the_session(
    brazos, dana, monkeypatch, which
):
    """Falling back to the courier would write Dana's act as Sam — the one
    thing the token exists to stop. Refused, by name; nothing written."""
    from apps.work import api

    with tenant_ctx(brazos):
        oid, tech = job(dana, brazos)
        token = _token(tech)
        if which == "expired":
            monkeypatch.setattr(mobile, "capture_token_max_age_s", lambda: -1)
        else:
            token = token[:-4] + "AAAA"
        answer = _call(
            api.mobile_act, brazos, tech,
            {"act": "depart", "key": "bad-tok", "capture_token": token}, order_id=oid,
        )
        written = work_models.WorkOrderAssignment.objects.filter(key="bad-tok").exists()
    assert answer.status_code == 403, answer.data
    assert answer.data["message_key"] == (
        "work.mobile.capture_token_expired" if which == "expired" else "work.mobile.capture_token_invalid"
    )
    assert written is False


def test_hand_back_crew_labour_and_raise_each_take_the_captors_token(brazos, dana):
    """The four other own doors, each sent by a courier who is NOT the captor."""
    from apps.work import api, field_orders_api

    with tenant_ctx(brazos):
        oid, tech = job(dana, brazos)
        lead_token = _token(tech)
        _s, sam = person(brazos, "sam@field.test", "Sam Ng")
        marco_row, _marco = person(brazos, "marco@field.test", "Marco Rossi")
        now = timezone.now()

        crew = _call(
            field_orders_api.mobile_crew, brazos, sam,
            {"technician_id": str(marco_row.id), "key": "crew-tok", "capture_token": lead_token},
            order_id=oid,
        )
        labour = _call(
            field_orders_api.mobile_labour, brazos, sam,
            {"arrive_at": _iso(now - timedelta(minutes=30)), "capture_token": lead_token},
            method="put", order_id=oid,
        )
        raised = _call(
            field_orders_api.mobile_orders, brazos, sam,
            {
                "key": "raise-tok",
                "template_id": str(template(dana, brazos)),
                "carried_from": str(oid),
                "location": FIX,
                "capture_token": lead_token,
            },
        )
        handed = _call(
            field_orders_api.mobile_hand_back, brazos, sam,
            {"reason": "Van broke down", "key": "hb-tok", "capture_token": lead_token},
            order_id=oid,
        )
        lead_row = work_models.Technician.objects.get(user_id=tech.id)
        lead_labour = WorkOrderLabour.objects.get(work_order_id=oid, technician=lead_row)
        raise_row = WorkFieldRaise.objects.get(key="raise-tok")
        unassign = work_models.WorkOrderAssignment.objects.get(key="hb-tok")
        _ = api  # the acts door is proved above

    assert crew.status_code == 201, crew.data
    assert labour.status_code == 200 and lead_labour.arrive_at is not None, labour.data
    assert raised.status_code == 201, raised.data
    assert raise_row.raised_by_technician_id == lead_row.id
    assert handed.status_code == 200, handed.data
    assert unassign.technician_id == lead_row.id and str(unassign.actor_id) == str(tech.id)


def test_the_token_never_reaches_the_service(brazos, dana):
    assert mobile.without_capture_token({"a": 1, "capture_token": "x"}) == {"a": 1}
    session = SimpleNamespace(id="s", role="field_technician")
    assert mobile.door_actor(session, {"a": 1}) is session
    assert mobile.door_actor(session, {"capture_token": ""}) is session


# ══════════════════════════════════════════════════════════════════════════
# 4 · FF-29's × — a crew member leaving (the crew door extended)
# ══════════════════════════════════════════════════════════════════════════
def _crew(dana, brazos):
    oid, lead = job(dana, brazos)
    marco_row, marco = person(brazos, "marco@field.test", "Marco Rossi")
    field_labour.add_technician(lead, oid, {"technician_id": str(marco_row.id)})
    return oid, lead, marco_row, marco


def test_the_lead_stops_a_helpers_clock_and_their_time_stays_theirs(brazos, dana, audit_rows):
    """E2E-20's shape: Marco arrived 90 minutes ago; Dana taps × now. His
    finish is set, his minutes stand, his row is not deleted. A resend changes
    nothing and answers duplicate."""
    with tenant_ctx(brazos):
        oid, lead, marco_row, marco = _crew(dana, brazos)
        now = timezone.now()
        field_labour.record_time(marco, oid, {"arrive_at": _iso(now - timedelta(minutes=90))})
        left_at = _iso(now - timedelta(minutes=1))
        body = {"act": "leave", "technician_id": str(marco_row.id), "ended_at": left_at}
        first = field_labour.crew_door(lead, oid, body)
        again = field_labour.crew_door(lead, oid, body)
        row = WorkOrderLabour.objects.get(work_order_id=oid, technician=marco_row)
    assert first["duplicate"] is False and first["changed"] == ["end_at"]
    assert first["labour_minutes"] == 89 and first["labour_from"] == "arrive_at"
    assert again["duplicate"] is True and again["changed"] == []
    assert row.end_at is not None
    left = [r for r in audit_rows if r["action"] == "work.labour.member_left"]
    assert len(left) == 1 and left[0]["after"]["technician"] == "Marco Rossi"


def test_leaving_never_overwrites_a_finish_the_helper_recorded(brazos, dana):
    with tenant_ctx(brazos):
        oid, lead, marco_row, marco = _crew(dana, brazos)
        now = timezone.now()
        own_end = now - timedelta(minutes=20)
        field_labour.record_time(
            marco, oid, {"arrive_at": _iso(now - timedelta(minutes=60)), "end_at": _iso(own_end)}
        )
        out = field_labour.crew_door(
            lead, oid, {"act": "leave", "technician_id": str(marco_row.id)}
        )
        row = WorkOrderLabour.objects.get(work_order_id=oid, technician=marco_row)
    assert out["changed"] == [] and row.end_at == own_end


def test_leaving_is_the_leads_act_for_a_helper_on_this_job(brazos, dana):
    with tenant_ctx(brazos):
        oid, lead, marco_row, marco = _crew(dana, brazos)
        lead_row = work_models.Technician.objects.get(user_id=lead.id)
        sam_row, _sam = person(brazos, "sam@field.test", "Sam Ng")
        with pytest.raises(errors.AuthError) as helper_asks:
            field_labour.crew_door(marco, oid, {"act": "leave", "technician_id": str(lead_row.id)})
        with pytest.raises(errors.ValidationError) as lead_leaves:
            field_labour.crew_door(lead, oid, {"act": "leave", "technician_id": str(lead_row.id)})
        with pytest.raises(errors.NotFoundError):
            field_labour.crew_door(lead, oid, {"act": "leave", "technician_id": str(sam_row.id)})
        with pytest.raises(errors.ValidationError) as no_one:
            field_labour.crew_door(lead, oid, {"act": "leave"})
        with pytest.raises(errors.ValidationError) as unknown:
            field_labour.crew_door(lead, oid, {"act": "swap", "technician_id": str(sam_row.id)})
    assert helper_asks.value.message_key == "work.labour.lead_changes_others_only"
    assert lead_leaves.value.message_key == "work.labour.already_lead"
    assert no_one.value.message_key == "work.labour.technician_required"
    assert unknown.value.message_key == "work.labour.crew_act_unknown"


def test_the_crew_door_still_adds_as_before(brazos, dana):
    """`act` absent is a join — the handset that sends none is unchanged."""
    with tenant_ctx(brazos):
        oid, lead = job(dana, brazos)
        marco_row, _m = person(brazos, "marco@field.test", "Marco Rossi")
        out = field_labour.crew_door(lead, oid, {"technician_id": str(marco_row.id), "key": "j"})
    assert out["created"] is True


# ══════════════════════════════════════════════════════════════════════════
# 5 · *Correct their time* — the lead corrects a helper's clocks (US-FLD-020 TC-3)
# ══════════════════════════════════════════════════════════════════════════
def test_the_lead_corrects_a_helpers_time_stamped_who_and_when(brazos, dana, audit_rows):
    """FF-29: Dana corrects M. Chen to 0 minutes' travel and 72 minutes' labour.
    The handset sends the moments those minutes mean; the server records them
    on Marco's row, counts a correction, and the audit names both people."""
    with tenant_ctx(brazos):
        oid, lead, marco_row, marco = _crew(dana, brazos)
        now = timezone.now()
        arrived = now - timedelta(minutes=100)
        field_labour.record_time(
            marco,
            oid,
            {"arrive_at": _iso(arrived), "start_at": _iso(arrived), "end_at": _iso(now - timedelta(minutes=10))},
        )
        out = field_labour.record_time(
            lead,
            oid,
            {
                "technician_id": str(marco_row.id),
                "depart_at": _iso(arrived),
                "arrive_at": _iso(arrived),
                "start_at": _iso(arrived),
                "end_at": _iso(arrived + timedelta(minutes=72)),
            },
        )
        lead_row = WorkOrderLabour.objects.filter(
            work_order_id=oid, technician__user_id=lead.id
        ).first()
    assert out["technician"]["name"] == "Marco Rossi"
    assert out["travel_minutes"] is None or out["travel_minutes"] == 0
    assert out["labour_minutes"] == 72 and out["corrected"] == ["end_at"]
    assert out["corrections"] == 1
    assert lead_row is None or lead_row.end_at is None  # the lead's own clock untouched
    fixed = [r for r in audit_rows if r["action"] == "work.labour.corrected"]
    assert fixed and fixed[-1]["after"]["technician"] == "Marco Rossi"
    assert "changed_by" in fixed[-1]["after"]


def test_a_helper_cannot_change_anybody_elses_time(brazos, dana):
    with tenant_ctx(brazos):
        oid, lead, marco_row, marco = _crew(dana, brazos)
        lead_row = work_models.Technician.objects.get(user_id=lead.id)
        sam_row, _sam = person(brazos, "sam@field.test", "Sam Ng")
        before = timezone.now() - timedelta(minutes=5)
        with pytest.raises(errors.AuthError) as helper:
            field_labour.record_time(
                marco, oid, {"technician_id": str(lead_row.id), "end_at": _iso(before)}
            )
        with pytest.raises(errors.NotFoundError):
            field_labour.record_time(
                lead, oid, {"technician_id": str(sam_row.id), "end_at": _iso(before)}
            )
        own = field_labour.record_time(
            marco, oid, {"technician_id": str(marco_row.id), "end_at": _iso(before)}
        )
    assert helper.value.message_key == "work.labour.lead_changes_others_only"
    assert own["technician"]["name"] == "Marco Rossi"
