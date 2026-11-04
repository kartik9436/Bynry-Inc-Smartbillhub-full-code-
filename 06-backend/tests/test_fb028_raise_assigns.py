# ── Trace ──────────────────────────────────────────────
# Change:   FB-028 (DEF-WRK-10800) — an order raised on site is the raiser's job
#           at once: assigned in the same act, for every template, reconnects
#           and disconnects included; a skill gap is advice and the phone warns.
# Rules:    PO 2026-10-31 W1, W3 = C, W2 = B and "Field-raised disconnects go
#           to the technician" (decision log) · BR-FLD-00023 (R23) SUPERSEDED ·
#           BR-WRK-029 superseded (advice, never a block) · hard rule 7
# Code:     apps/work/field_raise.py · apps/work/field_dispatch.py
# ───────────────────────────────────────────────────────
"""Raise on the kerb → it is on the raiser's phone, numbered, with no office wait."""

from __future__ import annotations

import pytest

from apps.work import dispatch, field_dispatch, field_raise, mobile
from apps.work import connection_models as work_tables
from apps.work import models as work_models
from apps.work.field_order_models import WorkFieldRaise

from tests.test_cr187_order_helpers import FIX, job, order, person, template
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db


def _body(tid, key="fb028-1", **extra):
    return {
        "key": key,
        "template_id": str(tid),
        "need": "Leak",
        "urgency": "normal",
        "captured_at": "2026-03-15T16:05:00Z",
        "location": FIX,
        **extra,
    }


def _today_ids(tech):
    return {c["id"] for c in mobile.today(tech)["jobs"]}


def test_a_leak_raised_on_site_is_assigned_to_the_raiser_and_on_her_today(brazos, dana, audit_rows):
    """Worked: Dana raises *Leak investigation* at the premise she is standing
    on. Before FB-028 the order was Queued, unassigned and on nobody's phone;
    now it is hers, accepted, on Today — one history row, one audit row."""
    with tenant_ctx(brazos):
        oid, tech = job(dana, brazos)
        tid = template(dana, brazos, "Leak investigation")
        out = field_raise.raise_from_field(tech, _body(tid, carried_from=str(oid)))
        new = order(out["order_id"])
        raiser = mobile.technician_of(tech)
        history = list(
            work_models.WorkOrderAssignment.objects.filter(work_order_id=new.id).order_by("at")
        )
        on_today = out["order_id"] in _today_ids(tech)
        raise_row = WorkFieldRaise.objects.get(work_order_id=new.id)

    assert out["assigned"] is True and out["order_no"].startswith("WO-")
    assert out["assigned_to"]["id"] == str(raiser.id)
    assert new.assignee_technician_id == raiser.id and new.accepted_at_technician is not None
    assert new.dispatch_state == "scheduled"
    assert [(h.act, h.reason) for h in history] == [("assign", field_raise.RAISED_ON_SITE)]
    assert on_today, "the raised job is on the raiser's day"
    # The office's queue is a REVIEW list now: the row still lands pending.
    assert raise_row.status == "pending"
    raised = [r for r in audit_rows if r["action"] == "work.order.raised_in_field"]
    assert len(raised) == 1 and raised[0]["after"]["assignment_id"] == str(history[0].id)


def test_a_reconnect_raised_on_site_is_assigned_with_no_office_wait(brazos, dana):
    """W1 supersedes R23: no pending-office wait, no claim refusal."""
    with tenant_ctx(brazos):
        oid, tech = job(dana, brazos)
        tid = template(dana, brazos, "Reconnect visit")
        out = field_raise.raise_from_field(
            tech, _body(tid, key="fb028-rc", need="Reconnect", carried_from=str(oid))
        )
        on_today = out["order_id"] in _today_ids(tech)
        # A replayed claim tap on her own raised job is answered, not refused.
        again = field_dispatch.claim(tech, out["order_id"])
    assert out["is_reconnect"] is True and out["assigned"] is True and on_today
    assert again["already_yours"] is True


def test_a_disconnect_raised_on_site_is_assigned_too(brazos, dana):
    with tenant_ctx(brazos):
        oid, tech = job(dana, brazos)
        tid = template(dana, brazos, "Disconnect visit")
        out = field_raise.raise_from_field(tech, _body(tid, key="fb028-dc", carried_from=str(oid)))
    assert out["assigned"] is True


def test_a_skill_gap_still_assigns_records_advice_and_tells_the_phone(brazos, dana, audit_rows):
    """W3 = C — *"Assign it to Dana, but her phone warns before she starts"*."""
    with tenant_ctx(brazos):
        oid, tech = job(dana, brazos)
        tid = template(dana, brazos, "Backflow test")
        skill = work_models.WorkSkill.objects.create(
            tenant_id=brazos.id, code="FB028_BACKFLOW", name="Backflow tester (certified)"
        )
        work_tables.WorkOrderTemplate.objects.filter(pk=tid).update(skill=skill)
        out = field_raise.raise_from_field(tech, _body(tid, key="fb028-sk", carried_from=str(oid)))
        new = order(out["order_id"])
        details = mobile.bundle(tech, out["order_id"])["details"]
    assert out["assigned"] is True and new.assignee_technician_id is not None
    assert out["advice"]["has_skill"] is False
    assert out["advice"]["skill"] == {"name": "Backflow tester (certified)"}
    # The phone's copy: it warns before Start from these two facts.
    assert details["raised_on_site"] is True
    assert details["skill_advice"] == {
        "skill": {"name": "Backflow tester (certified)"},
        "has_skill": False,
    }
    against = [r for r in audit_rows if r["action"] == dispatch.AGAINST_ADVICE]
    assert against and against[-1]["after"]["missing_skill"] == "Backflow tester (certified)"


def test_the_office_reassigns_and_the_job_leaves_the_raisers_feed(brazos, dana):
    """The queue is a review list; the dispatcher may move the job any time."""
    with tenant_ctx(brazos):
        oid, tech = job(dana, brazos)
        tid = template(dana, brazos, "Leak investigation")
        out = field_raise.raise_from_field(tech, _body(tid, key="fb028-re", carried_from=str(oid)))
        held = mobile.changes(tech)["next_cursor"]
        other_row, _other = person(brazos, "fb028-other@field.test", "Ray Ortiz")
        dispatch.record_act(
            dana,
            out["order_id"],
            {"act": "reassign", "technician_id": str(other_row.id), "reason": "Closer"},
            push=False,
        )
        feed = mobile.changes(tech, cursor=held)
        on_today = out["order_id"] in _today_ids(tech)
        accepted = field_raise.decide(dana, out["order_id"], {"decision": "accept"})
        queue = field_raise.field_raised_queue(status="accepted")
    mine = [c for c in feed["changes"] if c["order_id"] == out["order_id"]]
    assert mine and mine[-1]["change"] == "removed"
    assert not on_today
    # Accept = seen: it leaves the assignment where the office put it.
    assert accepted["status"] == "accepted" and accepted["assigned_to"]["name"] == "Ray Ortiz"
    assert queue["rows"][0]["assigned_to"]["name"] == "Ray Ortiz"
