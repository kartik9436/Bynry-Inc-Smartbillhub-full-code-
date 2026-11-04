# ── Trace ──────────────────────────────────────────────
# Change:   CR-187-BRC10 T-39 + FF-58, lane S-ORDER — a contractor claims
#           unassigned work (E2E-19); a technician hands a job back.
# Rules:    BR-FLD-00027 (R27) · BR-WRK-029 SUPERSEDED (advice, never a block)
#           · BR-FLD-00106/00107 (R106, R107) · BR-FLD-00023 (R23) ·
#           BR-WRK-025 · hard rules 1, 7
# Code:     apps/work/field_dispatch.py
# ───────────────────────────────────────────────────────
"""Take a job nobody holds; give one back to Queued."""

from __future__ import annotations

import pytest

from apps.work import connection_models as work_tables
from apps.work import dispatch, field_dispatch, mobile
from apps.work import models as work_models
from core import errors

from tests.test_cr187_order_helpers import order, person, template
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_wrk_032_copies import _raise

pytestmark = pytest.mark.django_db


def _unassigned(dana, brazos, *, skill=None):
    tid = template(dana, brazos)
    if skill is not None:
        work_tables.WorkOrderTemplate.objects.filter(pk=tid).update(skill=skill)
    return _raise(dana, brazos, tid)["id"]


def _contractor(brazos, email="ace@contractor.test", name="Ace Plumbing — J. Lee"):
    crew = work_models.Crew.objects.create(
        tenant_id=brazos.id, name="Ace Plumbing", kind=work_models.Crew.KIND_CONTRACTOR
    )
    return person(brazos, email, name, crew=crew)


def test_e2e19_a_contractor_claims_and_the_office_can_see_who_took_it(brazos, dana, audit_rows):
    with tenant_ctx(brazos):
        oid = _unassigned(dana, brazos)
        tech_row, contractor = _contractor(brazos)
        out = field_dispatch.claim(contractor, oid)
        again = field_dispatch.claim(contractor, oid)
        row = order(oid)
        last = (
            work_models.WorkOrderAssignment.objects.filter(work_order_id=oid)
            .order_by("-at")
            .first()
        )

    assert (
        out["dispatch_state"] == "scheduled"
        and out["technician"]["name"] == "Ace Plumbing — J. Lee"
    )
    assert again["already_yours"] is True
    assert row.assignee_technician_id == tech_row.id and row.accepted_at_technician is not None
    assert last.act == "assign" and last.actor_id == contractor.id and last.reason == "claimed"
    assert any(r["action"] == "work.order.claimed" for r in audit_rows)


def test_skill_match_advises_and_never_blocks_the_claim(brazos, dana, audit_rows):
    """⚠ The NAMED collision: E2E-19 says *within their skills*; signed
    BR-WRK-029 is SUPERSEDED to *advises, never blocks*. The signed rule stands
    — the claim succeeds and the override is recorded. A ruling that flips
    this goes red HERE."""
    with tenant_ctx(brazos):
        skill = work_models.WorkSkill.objects.create(
            tenant_id=brazos.id, code="CR187_METER_X", name="Meter X (cr187)"
        )
        oid = _unassigned(dana, brazos, skill=skill)
        _row, contractor = _contractor(brazos)
        out = field_dispatch.claim(contractor, oid)

    assert out["advice"]["has_skill"] is False and out["advice"]["skill"] == {"name": "Meter X (cr187)"}
    assert out["against_advice"]["missing_skill"] == "Meter X (cr187)"
    assert any(r["action"] == dispatch.AGAINST_ADVICE for r in audit_rows)


def test_a_held_job_cannot_be_claimed_and_a_field_raise_is_no_longer_refused(brazos, dana):
    """⚠ FB-028 (PO 2026-10-31, R23 superseded): the `pending_office` refusal is
    gone — a raise is assigned to its raiser, and a raise row on an open
    unassigned order no longer stops a claim."""
    from apps.work.field_order_models import WorkFieldRaise

    with tenant_ctx(brazos):
        oid = _unassigned(dana, brazos)
        _a, first = _contractor(brazos)
        _b, second = person(brazos, "bo@field.test", "Bo Diaz")
        field_dispatch.claim(first, oid)
        with pytest.raises(errors.BizError) as taken:
            field_dispatch.claim(second, oid)
        pending = _unassigned(dana, brazos)
        WorkFieldRaise.objects.create(tenant_id=brazos.id, work_order_id=pending, key="k-p")
        claimed = field_dispatch.claim(second, pending)
    assert taken.value.message_key == "work.claim.already_taken"
    assert claimed["dispatch_state"] == "scheduled"


def test_a_claim_is_within_the_tenant(brazos, dana, lonestar):
    with tenant_ctx(brazos):
        oid = _unassigned(dana, brazos)
    with tenant_ctx(lonestar):
        _t, outsider = person(lonestar, "ls@field.test", "Lone Star Tech")
        with pytest.raises(errors.NotFoundError):
            field_dispatch.claim(outsider, oid)
    with tenant_ctx(brazos):
        assert order(oid).assignee_technician_id is None


# ── hand-back (FF-58) ─────────────────────────────────────────────────────
def test_hand_back_returns_the_job_to_queued_with_name_and_reason(brazos, dana, audit_rows):
    """R106 — Queued, unassigned, the technician's name and reason on it; no
    eighth state. The change feed then tombstones it for the technician."""
    with tenant_ctx(brazos):
        oid = _unassigned(dana, brazos)
        tech_row, tech = person(brazos, "dana.o@field.test", "D. Ortiz")
        dispatch.record_act(
            dana, oid, {"act": "assign", "technician_id": str(tech_row.id)}, push=False
        )
        mobile.accept_job(tech, oid)
        # The handset holds a cursor from its last refresh; a cursor-less call
        # is a FULL pass of open jobs (lane S-SYNC), which has nothing to remove.
        held = mobile.changes(tech)["next_cursor"]
        out = field_dispatch.hand_back(tech, oid, {"reason": "Van broke down"})
        row = order(oid)
        last = (
            work_models.WorkOrderAssignment.objects.filter(work_order_id=oid)
            .order_by("-at")
            .first()
        )
        feed = mobile.changes(tech, cursor=held)

    assert out["dispatch_state"] == "queued" and out["assigned"] is False
    assert row.assignee_technician_id is None and row.accepted_at_technician is None
    assert row.dispatch_state in work_tables.DISPATCH_STATES
    assert (
        last.act == "unassign"
        and last.technician_id == tech_row.id
        and last.reason == "Van broke down"
    )
    assert any(r["action"] == "work.order.handed_back" for r in audit_rows)
    # The tombstone (BR-WRK-063): the job leaves the hand-backer's handset.
    mine = [c for c in feed["changes"] if c["order_id"] == str(oid)]
    assert mine and mine[-1]["change"] == "removed", feed


def test_an_emergency_cannot_be_handed_back(brazos, dana):
    """R107 — the tenant's most urgent priority is an emergency; it takes a call."""
    with tenant_ctx(brazos):
        oid = _unassigned(dana, brazos)
        top = (
            work_models.WorkPriority.objects.filter(tenant_id=brazos.id, active=True)
            .order_by("rank")
            .first()
        )
        assert top is not None, "the seeded priorities exist"
        work_tables.WorkOrder.objects.filter(pk=oid).update(priority=top)
        tech_row, tech = person(brazos, "dana.o@field.test", "D. Ortiz")
        dispatch.record_act(
            dana, oid, {"act": "assign", "technician_id": str(tech_row.id)}, push=False
        )
        with pytest.raises(errors.BizError) as refused:
            field_dispatch.hand_back(tech, oid, {"reason": "Too far"})
        still = order(oid)
    assert refused.value.message_key == "work.handback.emergency_needs_a_call"
    assert still.assignee_technician_id == tech_row.id


def test_hand_back_needs_a_reason_and_is_own_job_only(brazos, dana):
    with tenant_ctx(brazos):
        oid = _unassigned(dana, brazos)
        tech_row, tech = person(brazos, "dana.o@field.test", "D. Ortiz")
        _s, stranger = person(brazos, "sam@field.test", "Sam Ng")
        dispatch.record_act(
            dana, oid, {"act": "assign", "technician_id": str(tech_row.id)}, push=False
        )
        with pytest.raises(errors.ValidationError) as no_reason:
            field_dispatch.hand_back(tech, oid, {})
        with pytest.raises(errors.NotFoundError):
            field_dispatch.hand_back(stranger, oid, {"reason": "x"})
    assert no_reason.value.message_key == "work.handback.reason_required"


# Fixed by lane S-SYNC (DEF-WRK-10347): the feed walks the assignment history.
def test_an_office_reassign_tombstones_the_job_for_the_old_holder(brazos, dana):
    with tenant_ctx(brazos):
        oid = _unassigned(dana, brazos)
        first_row, first = person(brazos, "first@field.test", "First Tech")
        second_row, _second = person(brazos, "second@field.test", "Second Tech")
        dispatch.record_act(
            dana, oid, {"act": "assign", "technician_id": str(first_row.id)}, push=False
        )
        held = mobile.changes(first)["next_cursor"]
        dispatch.record_act(
            dana,
            oid,
            {"act": "reassign", "technician_id": str(second_row.id), "reason": "Closer"},
            push=False,
        )
        feed = mobile.changes(first, cursor=held)
    mine = [c for c in feed["changes"] if c["order_id"] == str(oid)]
    assert mine and mine[-1]["change"] == "removed", feed
