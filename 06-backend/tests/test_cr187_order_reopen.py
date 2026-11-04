# ── Trace ──────────────────────────────────────────────
# Change:   CR-187-BRC10 T-37, lane S-ORDER — reopen versus follow-on (FF-36,
#           E2E-17, E2E-18).
# Rules:    BR-FLD-00021 (R21) · BR-FLD-00022 (R22) · BR-MET-110 · hard rules
#           1, 4's shape, 7
# Code:     apps/work/field_reopen.py
# ───────────────────────────────────────────────────────
"""Reopen and follow-on are distinguishable, and each side owns its door."""

from __future__ import annotations

import pytest

from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from apps.work import field_reopen
from apps.work.field_order_models import WorkOrderReopen
from core import errors

from tests.test_cr187_order_helpers import close, job, order, person, template
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db


def test_tc1_the_technician_reopens_their_closed_unaccepted_job(brazos, dana, audit_rows):
    """FF-36 / US-FLD-024 TC-1 — *Missed a step*: the close is undone, the
    history keeps what it said, the readings stay, and a replay is a duplicate."""
    with tenant_ctx(brazos):
        oid, tech = job(dana, brazos)
        close(tech, oid, "passed", field_data={"reason": "done"})
        first = field_reopen.technician_reopen(tech, oid, {"reason": "missed_step", "key": "r-1"})
        again = field_reopen.technician_reopen(tech, oid, {"reason": "missed_step", "key": "r-1"})
        row = order(oid)
        rows = WorkOrderReopen.objects.filter(work_order_id=oid).count()

    assert first["kind"] == "technician_reopen" and first["duplicate"] is False
    assert first["prior"]["outcome"] == "passed" and first["prior"]["state"] == "completed"
    assert again["duplicate"] is True and again["id"] == first["id"] and rows == 1
    assert row.state == work_tables.WO_IN_PROGRESS and row.outcome is None and row.completed_at is None
    assert row.field_data and row.field_data.get("reason") == "done", "field data is kept"
    assert any(r["action"] == "work.order.reopened_by_technician" for r in audit_rows)


def test_tc2_after_acceptance_the_technician_cannot_reopen(brazos, dana):
    """R22 — *after acceptance it is a correction and the office owns it*."""
    with tenant_ctx(brazos):
        oid, tech = job(dana, brazos)
        close(tech, oid, "passed")
        w6.accept_field_result(dana, oid)
        with pytest.raises(errors.BizError) as owned:
            field_reopen.technician_reopen(tech, oid, {"reason": "wrong_outcome"})
    assert owned.value.message_key == "work.reopen.office_owns_it"


@pytest.mark.parametrize(
    "reason,key",
    [
        ("reconnect", "work.reopen.reconnect_is_a_new_order"),
        ("bored", "work.reopen.reason_unknown"),
    ],
)
def test_a_reconnect_is_never_a_reopen_and_reasons_are_ff36s_three(brazos, dana, reason, key):
    with tenant_ctx(brazos):
        oid, tech = job(dana, brazos)
        close(tech, oid, "passed")
        with pytest.raises(errors.ApiError) as refused:
            field_reopen.technician_reopen(tech, oid, {"reason": reason})
    assert refused.value.message_key == key


def test_an_open_job_cannot_be_reopened_and_another_technicians_is_a_404(brazos, dana):
    with tenant_ctx(brazos):
        oid, tech = job(dana, brazos)
        with pytest.raises(errors.BizError) as not_closed:
            field_reopen.technician_reopen(tech, oid, {"reason": "missed_step"})
        _s, stranger = person(brazos, "sam@field.test", "Sam Ng")
        with pytest.raises(errors.NotFoundError):
            field_reopen.technician_reopen(stranger, oid, {"reason": "missed_step"})
    assert not_closed.value.message_key == "work.reopen.not_closed"


def test_e2e17_the_office_reopens_the_same_order(brazos, dana):
    """The office's reopen = metering's send-back + a history row."""
    with tenant_ctx(brazos):
        oid, tech = job(dana, brazos)
        close(tech, oid, "partially_done", field_data={"reason": "Part missing"}, tasks=3)
        out = field_reopen.office_decide(
            dana, oid, {"decision": "reopen", "reason": "Finish the job"}
        )
        history = field_reopen.history(oid)
        row = order(oid)

    assert out["kind"] == "office_reopen" and row.state == work_tables.WO_IN_PROGRESS
    assert [e["kind"] for e in history["events"]] == ["office_reopen"]
    assert history["events"][0]["prior"]["outcome"] == "partially_done"


def test_e2e18_the_office_raises_a_linked_follow_on_and_the_two_are_distinguishable(brazos, dana):
    """R21 — a reconnect is a NEW order: different number, linked, the
    original untouched; allowed after acceptance too."""
    with tenant_ctx(brazos):
        oid, tech = job(dana, brazos)
        close(tech, oid, "passed")
        w6.accept_field_result(dana, oid)
        tid = template(dana, brazos, "Reconnect — residential")
        out = field_reopen.office_decide(
            dana,
            oid,
            {
                "decision": "follow_on",
                "reason": "Payment cleared",
                "template_id": tid,
                "key": "f-1",
            },
        )
        again = field_reopen.office_decide(
            dana,
            oid,
            {
                "decision": "follow_on",
                "reason": "Payment cleared",
                "template_id": tid,
                "key": "f-1",
            },
        )
        original = order(oid)
        follow = order(out["follow_on"]["id"])
        child_history = field_reopen.history(follow.id)

    assert out["kind"] == "follow_on" and again["duplicate"] is True
    assert follow.order_no != original.order_no and follow.state == work_tables.WO_PLANNED
    assert follow.premises_id == original.premises_id
    assert follow.follows_order_id is None, "a follow-on is not failure provenance"
    assert original.accepted_at is not None and original.state == work_tables.WO_COMPLETED
    assert child_history["followed_on_from"]["order_no"] == original.order_no


# ── PO answer 11 (2026-10-21): the office MAY reopen an accepted job ─────────


def _reports(oid):
    from apps.work import models as work_models

    return list(
        work_models.WorkOrderReport.objects.filter(work_order_id=oid)
        .order_by("version")
        .values_list("version", "total", "generated_at")
    )


def test_po11_the_office_reopens_an_accepted_job_and_the_next_acceptance_writes_v2(
    brazos, dana, audit_rows
):
    """PO answer 11 — *"yes"*. Judgment J9 is superseded FOR THE OFFICE: the
    reopen goes through metering's send-back, the history keeps what the close
    and the acceptance said, both sides audit it, `-v1` is never touched and
    the next acceptance writes `-v2` beside it."""
    from apps.metering.connections import submit_field_result
    from django.utils import timezone

    with tenant_ctx(brazos):
        oid, tech = job(dana, brazos)
        close(tech, oid, "passed")
        w6.accept_field_result(dana, oid)
        v1_before = _reports(oid)
        out = field_reopen.office_decide(
            dana, oid, {"decision": "reopen", "reason": "Wrong reading", "key": "o-1"}
        )
        again = field_reopen.office_decide(
            dana, oid, {"decision": "reopen", "reason": "Wrong reading", "key": "o-1"}
        )
        reopened = order(oid)
        history = field_reopen.history(oid)
        v1_after_reopen = _reports(oid)
        # The field finishes it again; the office accepts it again.
        submit_field_result(tech, oid, outcome="passed", completed_at=timezone.now())
        answer = w6.accept_field_result(dana, oid)
        accepted = order(oid)
        versions = _reports(oid)
        with pytest.raises(errors.BizError) as owned:
            field_reopen.technician_reopen(tech, oid, {"reason": "wrong_outcome"})

    assert [v for v, _t, _g in v1_before] == [1]
    assert out["kind"] == "office_reopen" and out["duplicate"] is False
    assert again["duplicate"] is True and again["id"] == out["id"]
    assert reopened.state == work_tables.WO_IN_PROGRESS and reopened.accepted_at is None
    assert reopened.accepted_by_id is None and reopened.outcome is None
    assert [e["kind"] for e in history["events"]] == ["office_reopen"]
    assert history["events"][0]["prior"]["accepted_at"] is not None
    # The frozen report is untouched by the reopen.
    assert v1_after_reopen == v1_before
    sent_back = [r for r in audit_rows if r["action"] == "work.order.sent_back"]
    assert sent_back and sent_back[-1]["after"]["after_acceptance"] is True
    assert sent_back[-1]["before"]["accepted_at"] is not None
    ours = [r for r in audit_rows if r["action"] == "work.order.reopened_after_acceptance"]
    assert len(ours) == 1 and ours[0]["after"]["supersedes_report_version"] == 1
    # The next acceptance: accepted again, `-v2` BESIDE `-v1`, `-v1` unchanged.
    assert accepted.accepted_at is not None and answer["report"]["version"] == 2
    assert [v for v, _t, _g in versions] == [1, 2] and versions[0] == v1_before[0]
    reaccepted = [r for r in audit_rows if r["action"] == "work_order.accepted"]
    assert reaccepted[-1]["after"].get("reaccepted") is True
    # R22 still binds the technician after the second acceptance.
    assert owned.value.message_key == "work.reopen.office_owns_it"


def test_po11_the_cost_section_reads_the_latest_report_versions_lines(brazos, dana):
    """`-v1`'s frozen lines stay; the cost section adds up `-v2`'s alone."""
    from decimal import Decimal

    from apps.work import models as work_models
    from apps.work import selectors

    with tenant_ctx(brazos):
        oid, _tech = job(dana, brazos)
        for version, amount in ((1, "42.1950"), (2, "96.0000")):
            work_models.WorkOrderCostLine.objects.create(
                tenant_id=brazos.id,
                work_order_id=oid,
                kind="labour",
                description="Field technician",
                qty=Decimal("1"),
                unit="h",
                rate=Decimal(amount),
                amount=Decimal(amount),
                sequence=0,
                report_version=version,
            )
        cost = selectors.work_order_cost_lines(oid)

    assert cost["total"] == "96.00" and len(cost["lines"]) == 1


def test_po11_another_utilitys_accepted_job_cannot_be_reopened(brazos, dana, lonestar, erin):
    """Tenant isolation — another utility's accepted job is a 404, and nothing
    about it moves."""
    with tenant_ctx(brazos):
        oid, tech = job(dana, brazos)
        close(tech, oid, "passed")
        w6.accept_field_result(dana, oid)
    with tenant_ctx(lonestar):
        with pytest.raises(errors.NotFoundError):
            field_reopen.office_decide(erin, oid, {"decision": "reopen", "reason": "x"})
    with tenant_ctx(brazos):
        assert order(oid).accepted_at is not None
        assert WorkOrderReopen.objects.filter(work_order_id=oid).count() == 0


def test_a_technician_cannot_make_the_office_decision(brazos, dana):
    with tenant_ctx(brazos):
        oid, tech = job(dana, brazos)
        close(tech, oid, "passed")
        with pytest.raises(errors.AuthError):
            field_reopen.office_decide(tech, oid, {"decision": "reopen", "reason": "x"})


def test_the_history_is_tenant_scoped(brazos, dana, lonestar):
    with tenant_ctx(brazos):
        oid, tech = job(dana, brazos)
    with tenant_ctx(lonestar):
        with pytest.raises(errors.NotFoundError):
            field_reopen.history(oid)
