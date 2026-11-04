# ── Trace ──────────────────────────────────────────────
# Story:    US-WRK-043 (EP-WRK-08) TC-3, TC-4, TC-6, TC-7 — the SERVER half of
#           the safety gate.  Screens: Work-011 (the phone), Work-008
# Rules:    BR-WRK-037 (safety blocks the task list on the phone AND the server
#           refuses a completion carrying an unticked mandatory safety row,
#           NAMING the row; two of three ticked is locked) · BR-SHL-025 (the
#           server independently enforces every mutating call) · B14 rule 33
#           (a refusal caps at five or six words) · hard rule 1
# Tests:    this file · 10-scripts/gates/g110_safety_gate_server_side.py is the
#           permanent guard that this check still EXISTS (CR-070 §12 gate 2)
# ───────────────────────────────────────────────────────
"""US-WRK-043 — **the server refuses the completion**, and that is the wave.

r10, verbatim: *"The lock is on the phone, and it must also be on the server. A
screen that greys a list is a convenience; a server that refuses a completion
with an unticked mandatory safety row is the guarantee. **Build both or you have
built neither.**"*

⚠ **EVERY TEST HERE GOES STRAIGHT AT THE SERVICE, WITH NO SCREEN INVOLVED.**
That is the point: a greyed control is walked past by a replayed request, a sync
batch that arrived out of order, and a phone that was offline and hopeful.
`test_tc3_*` posts a completion the way a tampered client would.

⚠ **AND `test_tc4_*` IS THE OTHER HALF OF THE RULE, WHICH IS EASY TO LOSE.**
Only MANDATORY rows gate. A template may carry an advisory safety line, and a
gate that refused on one would silently make every advisory line mandatory — a
job that cannot be closed for a reason nobody wrote down.
"""

from __future__ import annotations

import pytest

from apps.work import connection_models as work_tables
from apps.work import checklist
from apps.work import models as work_models
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin
from tests.test_us_met_helpers import field_close  # CR-168 P1.34 — close as the field
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_wrk_032_copies import _published_template, _raise

pytestmark = pytest.mark.django_db


def _order(actor, tenant):
    tid = _published_template(actor, tenant)
    return _raise(actor, tenant, tid)["id"]


def _safety(oid, seq):
    return work_models.WorkOrderSafety.objects.get(work_order_id=oid, seq=seq)


# ══════════════════════════════════════════════════════════════════════════
# TC-3 — the completion is REFUSED, naming the row, with nothing written
# ══════════════════════════════════════════════════════════════════════════
def test_tc3_a_a_completion_with_an_unticked_mandatory_row_is_refused(brazos, dana):
    """TC-3 · **negative · server** — `submit_field_result` refuses.

    This is the assertion `CR-070` §12 gate 2 exists to keep true, and the one
    the whole wave is measured by.
    """
    with tenant_ctx(brazos):
        oid = _order(dana, brazos)
        with pytest.raises(errors.BizError) as refused:
            field_close(dana, oid, field_data={}, outcome="passed")
        assert refused.value.br_ref == "BR-WRK-037"
        assert refused.value.message_key == "work.order.finish_safety_first"


def test_tc3_b_the_refusal_names_the_row(brazos, dana):
    """TC-3 — `BR-WRK-037` says the server NAMES the row.

    It travels in `params`, not inside the sentence: B14 rule 33 caps a refusal
    at five or six words and *Finish safety first.* is three. Naming it inside
    would break rule 33; naming it nowhere would break the rule the sentence
    serves. So both halves are asserted — the short key AND the named row.
    """
    with tenant_ctx(brazos):
        oid = _order(dana, brazos)
        first = _safety(oid, 1)
        with pytest.raises(errors.BizError) as refused:
            field_close(dana, oid, field_data={}, outcome="passed")
        assert refused.value.params["safety"] == first.text
        assert refused.value.params["remaining"] == 3


def test_tc3_c_nothing_is_written_by_a_refused_completion(brazos, dana, audit_rows):
    """TC-3 — *"`state` unchanged; no audit of a completion."*

    The check runs before any write and before the audit row, so a refusal
    leaves the order exactly as it was. An order marked `completed` with a
    refusal returned would be the worst of both.
    """
    with tenant_ctx(brazos):
        oid = _order(dana, brazos)
        before = work_tables.WorkOrder.objects.get(pk=oid)
        assert before.state == "planned"
        with pytest.raises(errors.BizError):
            field_close(dana, oid, field_data={"set_reads": []}, outcome="passed")
        after = work_tables.WorkOrder.objects.get(pk=oid)
        assert after.state == "planned"
        assert after.completed_at is None
        assert not [row for row in audit_rows if row["action"] == "work_order.field_result"]


def test_tc3_d_two_of_three_ticked_is_still_refused(brazos, dana):
    """TC-3 — **the rule's own sentence.** *"Two of three ticked is not
    two-thirds unlocked; it is locked."*

    The plausible bug is a proportion — *most of the safety list is done, let
    them get on* — and a partially-completed safety list is exactly the state in
    which somebody gets hurt. There is no threshold anywhere on this path.
    """
    with tenant_ctx(brazos):
        oid = _order(dana, brazos)
        checklist.tick_safety(dana, oid, _safety(oid, 1).id)
        checklist.tick_safety(dana, oid, _safety(oid, 2).id)
        with pytest.raises(errors.BizError) as refused:
            field_close(dana, oid, field_data={}, outcome="passed")
        assert refused.value.params["remaining"] == 1
        assert refused.value.params["safety"] == _safety(oid, 3).text


def test_tc3_e_all_three_ticked_completes(brazos, dana):
    """TC-3 — and the gate OPENS. A guard that never lets anything through is
    not a guard, and this is the assertion that would catch a check inverted or
    left permanently on."""
    with tenant_ctx(brazos):
        oid = _order(dana, brazos)
        for seq in (1, 2, 3):
            checklist.tick_safety(dana, oid, _safety(oid, seq).id)
        result = field_close(dana, oid, field_data={}, outcome="passed")
        assert result["state"] == "completed"
        assert result["awaiting_review"] is True


# ══════════════════════════════════════════════════════════════════════════
# TC-4 — only MANDATORY rows gate
# ══════════════════════════════════════════════════════════════════════════
def test_tc4_a_a_non_mandatory_row_left_unticked_is_accepted(brazos, dana):
    """TC-4 · **negative** — *"the same with a NON-mandatory safety row unticked
    → accepted; only mandatory rows gate."*

    ⚠ **THIS IS THE HALF THAT IS EASY TO LOSE.** A gate that refused on an
    advisory line would make every advisory line mandatory by accident, and a
    technician would be unable to close a job for a reason nobody ever wrote
    down. The template's own `is_mandatory` is what the copy brought across and
    what the lock reads.
    """
    with tenant_ctx(brazos):
        oid = _order(dana, brazos)
        # Make the third row advisory, then tick only the two that gate.
        third = _safety(oid, 3)
        third.is_mandatory = False
        third.save(update_fields=["is_mandatory"])
        checklist.tick_safety(dana, oid, _safety(oid, 1).id)
        checklist.tick_safety(dana, oid, _safety(oid, 2).id)
        result = field_close(dana, oid, field_data={}, outcome="passed")
        assert result["state"] == "completed"
        assert _safety(oid, 3).ticked_at is None, "the advisory row stayed unticked"


def test_tc4_b_an_order_with_no_safety_rows_is_not_refused(brazos, dana):
    """TC-4 — an order carrying NO safety list closes.

    ⚠ **THIS IS NOT A HOLE, IT IS THE RULE READ CORRECTLY.** The lock is *"a
    mandatory row is outstanding"*, not *"a safety list was found"*. Orders
    raised before wave H copied nothing at all, and a template may legitimately
    declare no safety step; refusing here would make every historical order
    uncloseable — a data migration disguised as a safety rule.
    """
    with tenant_ctx(brazos):
        order = _raise(dana, brazos, None)  # no template → no copies
        result = field_close(dana, order["id"], field_data={}, outcome="passed")
        assert result["state"] == "completed"


# ══════════════════════════════════════════════════════════════════════════
# TC-6 — the server re-derives the lock, never trusting the client
# ══════════════════════════════════════════════════════════════════════════
def test_tc6_a_the_lock_comes_from_the_rows_not_from_the_payload(brazos, dana):
    """TC-6 · **negative** — *"a tick smuggled into the client store is refused
    at sync — the server re-derives the lock from the safety rows' timestamps,
    never from the client's word."*

    So a `field_data` blob claiming the safety list is complete changes nothing:
    the payload is free-shaped (`BR-MET-109`) and is never consulted by the
    gate.
    """
    with tenant_ctx(brazos):
        oid = _order(dana, brazos)
        smuggled = {"safety": [{"seq": 1, "ticked": True}, {"seq": 2, "ticked": True},
                               {"seq": 3, "ticked": True}]}
        with pytest.raises(errors.BizError) as refused:
            field_close(dana, oid, field_data=smuggled, outcome="passed")
        assert refused.value.params["remaining"] == 3, "the client's word counted for nothing"


# ══════════════════════════════════════════════════════════════════════════
# TC-7 — tenant isolation
# ══════════════════════════════════════════════════════════════════════════
def test_tc7_a_another_tenants_order_is_a_404_not_a_refusal(brazos, lonestar, dana, erin):
    """TC-7 · **tenant isolation** — *"the field-result route for another
    tenant's order → 404."*

    ⚠ **AND IT MUST BE A 404 *BEFORE* THE SAFETY GATE, NOT AFTER.** A safety
    refusal for a foreign order would confirm the order exists and would even
    NAME one of its safety rows — leaking another utility's job content through
    a refusal message (HR-1). The order resolves first and the gate runs second,
    which is why this asserts the error TYPE rather than only that something was
    raised.
    """
    with tenant_ctx(brazos):
        oid = _order(dana, brazos)
    with tenant_ctx(lonestar):
        with pytest.raises(Exception) as refused:
            field_close(erin, oid, field_data={}, outcome="passed")
        assert not isinstance(refused.value, errors.BizError), (
            "a safety refusal would confirm the order exists and name its safety row"
        )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-WRK-043 (EP-WRK-08) · BR-WRK-037 · CR-070 §12 gate 2 · 10-execution-plan.md wave J task J4
# generated: 2026-09-05 by the CR-070 wave J build lane
# gates: pytest tests/test_us_wrk_043_safety_server.py · G110 (the check still exists, shown RED first)
# exceptions: none — every case here is the story's own TC
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
