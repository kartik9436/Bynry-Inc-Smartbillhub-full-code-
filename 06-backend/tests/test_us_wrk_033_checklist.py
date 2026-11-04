# ── Trace ──────────────────────────────────────────────
# Story:    US-WRK-033 (the six-tab work order detail) TC-1..TC-7 ·
#           US-WRK-043 (safety blocks the task list — on the phone AND the
#           SERVER).  Screens: Work-008, Work-011
# Rules:    BR-WRK-037 (the safety lock; *two of three ticked is locked, not
#           two-thirds unlocked*) · BR-WRK-008 (everything read is the order's
#           own copy) · B14 rule 31 (no database id is the visible value) ·
#           rule 33 (a refusal caps at five or six words) · hard rule 1 · 7
# Tests:    this file — every TC named in its own test name
# ───────────────────────────────────────────────────────
"""US-WRK-033 — the checklist read and the safety lock, by TC.

⚠ **THE LOCK IS THE SERVER'S AND THIS FILE IS WHERE THAT IS PROVED.** A greyed
button on `Work-008` and a locked list on `Work-011` are both courtesies that a
replayed request, an out-of-order sync batch or a hopeful offline phone walks
straight past. `test_tc3_*` POSTs a task tick under an incomplete safety list
and expects the refusal from the service, with no screen involved at all.

⚠ **AND *TWO OF THREE IS LOCKED* HAS ITS OWN TEST**, because the plausible bug
is a proportion — *most of the safety list is done, let them get on* — and a
partially-completed safety list is exactly the state in which somebody gets
hurt.
"""

from __future__ import annotations

import pytest

from apps.work import connection_models as work_tables
from apps.work import checklist
from apps.work import models as work_models
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_wrk_032_copies import _published_template, _raise

pytestmark = pytest.mark.django_db


def _order(actor, tenant):
    tid = _published_template(actor, tenant)
    return _raise(actor, tenant, tid)["id"]


def _safety(oid, seq):
    return work_models.WorkOrderSafety.objects.get(work_order_id=oid, seq=seq)


def _task(oid, seq):
    return work_models.WorkOrderTask.objects.get(work_order_id=oid, seq=seq)


# ══════════════════════════════════════════════════════════════════════════
# TC-1 — a tick names who and when, and the header count moves
# ══════════════════════════════════════════════════════════════════════════
def test_tc1_a_ticking_a_task_stamps_who_and_when(brazos, dana):
    """TC-1 — `ticked_at` and `ticked_by`, and the header moves to *1 of 7*."""
    with tenant_ctx(brazos):
        oid = _order(dana, brazos)
        for seq in (1, 2, 3):
            checklist.tick_safety(dana, oid, _safety(oid, seq).id)
        result = checklist.tick_task(dana, oid, _task(oid, 1).id)
        assert result["tasks_ticked"] == 1
        assert result["tasks_total"] == 7
        row = _task(oid, 1)
        assert row.ticked_at is not None
        assert str(row.ticked_by_id) == str(dana.id)


def test_tc1_b_the_count_is_the_servers_not_the_screens(brazos, dana):
    """TC-1 — *3 of 7* is counted server-side and served as two numbers.

    ⚠ A count assembled in the front end is a plural nobody can translate, and
    the eleven catalogues would each need a rule the data never reaches.
    """
    with tenant_ctx(brazos):
        oid = _order(dana, brazos)
        for seq in (1, 2, 3):
            checklist.tick_safety(dana, oid, _safety(oid, seq).id)
        for seq in (1, 2, 3):
            checklist.tick_task(dana, oid, _task(oid, seq).id)
        body = checklist.checklist(oid)
        assert (body["tasks_ticked"], body["tasks_total"]) == (3, 7)
        # *TASKS — 7 STEPS · 45 MIN ESTIMATED*, the drawing's own header.
        assert body["tasks_est_minutes"] == 45


# ══════════════════════════════════════════════════════════════════════════
# TC-3 / US-WRK-043 — the SERVER refuses a task tick under the safety lock
# ══════════════════════════════════════════════════════════════════════════
def test_tc3_a_a_task_tick_under_an_untouched_safety_list_is_refused(brazos, dana):
    """TC-3 · negative — no screen involved: the service refuses."""
    with tenant_ctx(brazos):
        oid = _order(dana, brazos)
        with pytest.raises(errors.BizError) as refused:
            checklist.tick_task(dana, oid, _task(oid, 1).id)
        assert refused.value.br_ref == "BR-WRK-037"
        assert refused.value.message_key == "work.order.finish_safety_first"


def test_tc3_b_two_of_three_ticked_is_still_locked(brazos, dana):
    """TC-3 · **the rule's own sentence** — *two of three ticked is locked, not
    two-thirds unlocked*. The plausible bug is a proportion; there is no
    threshold anywhere in `safety_lock`."""
    with tenant_ctx(brazos):
        oid = _order(dana, brazos)
        checklist.tick_safety(dana, oid, _safety(oid, 1).id)
        checklist.tick_safety(dana, oid, _safety(oid, 2).id)
        lock = checklist.safety_lock(oid)
        assert lock == {**lock, "locked": True, "remaining": 1, "ticked": 2, "total": 3}
        with pytest.raises(errors.BizError):
            checklist.tick_task(dana, oid, _task(oid, 1).id)


def test_tc3_c_the_refusal_names_the_row_that_is_still_outstanding(brazos, dana):
    """TC-3 — `BR-WRK-037` says the server NAMES the row. It travels in
    `params` rather than inside the sentence, because B14 rule 33 caps a
    refusal at five or six words and *Finish safety first.* is three."""
    with tenant_ctx(brazos):
        oid = _order(dana, brazos)
        checklist.tick_safety(dana, oid, _safety(oid, 1).id)
        checklist.tick_safety(dana, oid, _safety(oid, 3).id)
        with pytest.raises(errors.BizError) as refused:
            checklist.tick_task(dana, oid, _task(oid, 1).id)
        assert refused.value.params["safety"] == "Gloves and eye protection on"


def test_tc3_d_the_third_tick_lifts_the_lock(brazos, dana):
    """TC-3 — and then the task tick lands, which is the half that proves the
    refusal above was the lock and not something else refusing."""
    with tenant_ctx(brazos):
        oid = _order(dana, brazos)
        for seq in (1, 2, 3):
            checklist.tick_safety(dana, oid, _safety(oid, seq).id)
        assert checklist.safety_lock(oid)["locked"] is False
        assert checklist.tick_task(dana, oid, _task(oid, 1).id)["tasks_ticked"] == 1


def test_tc3_e_only_mandatory_rows_lock(brazos, dana):
    """TC-3 — an advisory safety line does not hold a job up. `is_mandatory`
    is what the copy carried across and what the lock reads."""
    with tenant_ctx(brazos):
        oid = _order(dana, brazos)
        work_models.WorkOrderSafety.objects.filter(work_order_id=oid, seq=3).update(
            is_mandatory=False
        )
        checklist.tick_safety(dana, oid, _safety(oid, 1).id)
        checklist.tick_safety(dana, oid, _safety(oid, 2).id)
        assert checklist.safety_lock(oid)["locked"] is False


def test_tc3_f_a_safety_tick_is_never_refused_by_the_lock(brazos, dana):
    """TC-3 — the act that CLEARS the lock cannot be gated by it, and a replayed
    tick is a no-op rather than a failure a technician must interpret in a
    basement."""
    with tenant_ctx(brazos):
        oid = _order(dana, brazos)
        first = checklist.tick_safety(dana, oid, _safety(oid, 1).id)
        again = checklist.tick_safety(dana, oid, _safety(oid, 1).id)
        assert first["ticked_at"] == again["ticked_at"]


# ══════════════════════════════════════════════════════════════════════════
# TC-6 — tenant isolation, application layer
# ══════════════════════════════════════════════════════════════════════════
def test_tc6_another_utility_cannot_tick_a_row_on_this_order(brazos, lonestar, dana, erin):
    """TC-6 — a 404 on the ORDER before any row is looked at, so a stranger
    learns nothing from the shape of the refusal either."""
    with tenant_ctx(brazos):
        oid = _order(dana, brazos)
        sid = _safety(oid, 1).id
    with tenant_ctx(lonestar):
        with pytest.raises(errors.NotFoundError):
            checklist.tick_safety(erin, oid, sid)


# ══════════════════════════════════════════════════════════════════════════
# TC-7 — the UI law the API can be held to: the visible id is the human one
# ══════════════════════════════════════════════════════════════════════════
def test_tc7_the_checklist_serves_the_human_reference(brazos, dana):
    """TC-7 · B14 rule 31 — *no database id is ever the visible value of a
    field*. The payload carries `order_no` so the screen never has to render
    the uuid it also needs for its calls."""
    with tenant_ctx(brazos):
        oid = _order(dana, brazos)
        body = checklist.checklist(oid)
        assert body["order_no"] == work_tables.WorkOrder.objects.get(pk=oid).order_no
        assert body["order_no"].startswith("WO-")


def test_tc7_b_everything_served_is_the_orders_own_copy(brazos, dana):
    """TC-7 · `BR-WRK-008` — publish v3 with an eighth task and the checklist
    READ still returns seven. The read is the surface a link would leak
    through, so it is asserted here as well as in the copy's own file."""
    from apps.work import templates_svc
    from tests.test_us_wrk_032_copies import SEVEN_TASKS

    with tenant_ctx(brazos):
        tid = _published_template(dana, brazos)
        oid = _raise(dana, brazos, tid)["id"]
        templates_svc.replace_collection(
            dana, tid, "tasks", [*SEVEN_TASKS, {"title": "Apply tamper seal", "est_minutes": 2}]
        )
        templates_svc.publish(dana, tid)
        assert len(checklist.checklist(oid)["tasks"]) == 7
