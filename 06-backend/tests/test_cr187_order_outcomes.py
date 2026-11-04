# ── Trace ──────────────────────────────────────────────
# Change:   CR-187-BRC10 T-36, lane S-ORDER — partial and failed outcomes end
#           to end (E2E-04, E2E-05, E2E-06).
# Rules:    BR-FLD-00004 (R4) · BR-WRK-054 · BR-WRK-050/051 · OQ-WRK-1491 ·
#           hard rule 1
# Code:     apps/work/field_outcomes.py · apps/work/field_orders_api.py
# ───────────────────────────────────────────────────────
"""The four outcomes carried through the order, the cost and the office queue."""

from __future__ import annotations

import pytest
from django.urls import resolve

from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from apps.work import field_outcomes
from core import errors

from tests.test_cr187_order_helpers import close, job, order
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db


def test_r4_words_are_metering_tokens():
    """R4's four words map onto four of metering's five stored tokens — a
    renamed token goes red here, not on a screen."""
    assert set(field_outcomes.R4_WORDS.values()) <= set(work_tables.WORK_ORDER_OUTCOMES)
    assert field_outcomes.R4_WORDS == {
        "passed": work_tables.OUTCOME_PASSED,
        "partly_done": work_tables.OUTCOME_PARTIALLY_DONE,
        "failed": work_tables.OUTCOME_FAILED,
        "waiting_on_someone": work_tables.OUTCOME_WAITING,
        # FB-013 (PO ruling (b) 2026-10-28) — the fifth technician outcome.
        "not_done_paid": work_tables.OUTCOME_NOT_DONE_PAID,
    }
    assert field_outcomes.BLOCKERS == ("person", "part", "access")


def test_partly_done_shows_which_steps_remain(brazos, dana):
    """E2E-04 — four of the steps ticked, closed Partly done with a reason:
    the office sees the remaining steps, in order, and the reason."""
    with tenant_ctx(brazos):
        oid, tech = job(dana, brazos)
        close(tech, oid, "partially_done", field_data={"reason": "Ran out of daylight"}, tasks=4)
        out = field_outcomes.order_outcome(oid)

    assert out["word"] == "partly_done" and out["kind"] == "partial"
    assert out["reason"] == "Ran out of daylight" and out["reason_missing"] is False
    assert (out["steps_done"], out["steps_total"]) == (4, 7)
    assert [s["seq"] for s in out["remaining_steps"]] == sorted(
        s["seq"] for s in out["remaining_steps"]
    )
    assert len(out["remaining_steps"]) == 3
    assert out["is_failure"] is False
    # The cost is a PREVIEW until Accept freezes the report.
    assert out["cost"]["frozen"] is False


def test_failed_is_a_failure_and_waiting_is_not(brazos, dana):
    """E2E-05 / E2E-06 — Failed is the work failing; Waiting on someone is
    being blocked, names its blocker, and does not read as a failure."""
    with tenant_ctx(brazos):
        failed_id, tech = job(dana, brazos)
        close(tech, failed_id, "failed", field_data={"reason": "Meter seized"})
        waiting_id, tech2 = job(dana, brazos)
        close(
            tech2,
            waiting_id,
            "waiting_on_someone_else",
            field_data={"reason": "Dog is out", "blocker": "Access"},
        )
        failed = field_outcomes.order_outcome(failed_id)
        waiting = field_outcomes.order_outcome(waiting_id)

    assert failed["is_failure"] is True and failed["kind"] == "failure"
    assert failed["photographs"] >= 1, "a failed close carries its photograph"
    assert waiting["is_failure"] is False and waiting["kind"] == "blocked"
    assert waiting["blocker"] == "access" and waiting["blocker_known"] is True


def test_a_close_with_no_reason_is_not_refused_but_flagged(brazos, dana):
    """`07-endpoints.md` §0 rule 1 — an older handset closes with no reason and
    keeps working; the office SEES the blank."""
    with tenant_ctx(brazos):
        oid, tech = job(dana, brazos)
        close(tech, oid, "waiting_on_someone_else")
        out = field_outcomes.order_outcome(oid)

    assert order_state(oid, brazos) == work_tables.WO_COMPLETED
    assert out["reason"] is None and out["reason_missing"] is True


def order_state(oid, tenant):
    with tenant_ctx(tenant):
        return order(oid).state


def test_the_failed_reason_reaches_the_follow_up_chain_and_the_report_freezes(brazos, dana):
    """BR-WRK-054 — Accept on a FAILED job raises the follow-up (metering's
    chain, unchanged) and the cost becomes the frozen report's total."""
    with tenant_ctx(brazos):
        oid, tech = job(dana, brazos)
        close(tech, oid, "failed", field_data={"reason": "Meter seized"})
        accepted = w6.accept_field_result(dana, oid)
        out = field_outcomes.order_outcome(oid)

    assert accepted["failed_outcome"] is not None
    assert out["cost"]["frozen"] is True and out["cost"]["report_version"] == 1


def test_the_office_queue_filters_by_outcome_and_tallies_the_whole_queue(brazos, dana):
    with tenant_ctx(brazos):
        a, t1 = job(dana, brazos)
        close(t1, a, "partially_done", field_data={"reason": "Part missing"}, tasks=2)
        b, t2 = job(dana, brazos)
        close(t2, b, "failed", field_data={"reason": "Seized"})
        c, t3 = job(dana, brazos)
        close(t3, c, "passed")
        partial = field_outcomes.office_queue(outcome="partly_done")
        every = field_outcomes.office_queue(per=1)
        with pytest.raises(errors.ValidationError) as unknown:
            field_outcomes.office_queue(outcome="sort_of_done")

    assert [r["order_no"] for r in partial["rows"]] == [order_no(a, brazos)]
    assert partial["rows"][0]["remaining_steps"], "the partial row names what is left"
    # The page size clamps to the house set (smallest 50, `core.pagination`); the
    # total and the tally count the WHOLE queue, never the page.
    assert every["per"] == 50 and every["total"] == 3 and len(every["rows"]) == 3
    assert every["tally"]["partly_done"] == 1 and every["tally"]["failed"] == 1
    assert every["tally"]["passed"] == 1
    assert unknown.value.message_key == "work.outcome.filter_unknown"


def order_no(oid, tenant):
    with tenant_ctx(tenant):
        return order(oid).order_no


def test_the_office_queue_is_tenant_scoped(brazos, dana, lonestar, erin):
    """Hard rule 1 — Lone Star's queue holds none of Brazos Bend's jobs, and a
    Brazos id read under Lone Star is a 404."""
    with tenant_ctx(brazos):
        oid, tech = job(dana, brazos)
        close(tech, oid, "failed", field_data={"reason": "Seized"})
    with tenant_ctx(lonestar):
        queue = field_outcomes.office_queue(accepted="all")
        with pytest.raises(errors.NotFoundError):
            field_outcomes.order_outcome(oid)
    assert queue["total"] == 0


def test_routes_are_wired():
    assert resolve("/api/brazosbend/work/acceptance-queue").func.__module__ == "apps.work.field_orders_api"
    assert (
        resolve("/api/brazosbend/work-orders/01a10711-e839-7fba-a5e0-3762f041dd2e/outcome").url_name
        == "work_order_outcome"
    )
