# ── Trace ──────────────────────────────────────────────
# Story:    CR-168-BRC10 round 5, lane SRV-4 — P5.2, P5.3 (the read), P5.6,
#           P5.8, P5.9, P5.10. Image 65.
# Rules:    BR-WRK-018 · BR-WRK-053 · PO answer (1) of 2026-10-04 (judgment J7)
# ───────────────────────────────────────────────────────
"""The promise, measured: SLA met with the default target, held time paused,
Performance paged, a job type's own hours, and the at-risk list.

Runs on SQLite (the default suite) AND on PostgreSQL 16
(`DJANGO_SETTINGS_MODULE=config.settings.pgtest`): the promise is interval
arithmetic done in the database, and both engines must agree.
"""

from __future__ import annotations

import datetime as dt
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from apps.work import models as work_models
from apps.work import selectors as work_selectors
from apps.work import services as work_services
from apps.work import workforce

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana
from tests.test_us_met_helpers import make_premises, tenant_ctx

pytestmark = pytest.mark.django_db

T0 = dt.datetime(2026, 9, 1, 9, 0, tzinfo=dt.timezone.utc)


def _priorities(tenant):
    work_services.seed_reference_list("work_priorities", [], "test")
    return {p.code: p for p in work_models.WorkPriority.objects.filter(tenant_id=tenant.id)}


def _done(tenant, premises, order_no, *, raised, completed, due=None, held_seconds=0, kind="Meter set"):
    row = work_tables.WorkOrder.objects.create(
        tenant=tenant, type=kind, order_no=order_no, premises_id=premises["id"],
        state=work_tables.WO_COMPLETED, completed_at=completed, due_at=due, held_seconds=held_seconds,
    )
    work_tables.WorkOrder.objects.filter(pk=row.pk).update(created_at=raised)
    return row


# ── P5.9 · the SLA figure counts an undated job against the default ────────
def test_p59_an_undated_job_is_measured_against_the_default_72_hours(brazos, dana):
    """RED on the tip: ``assert '50.0' == '66.7'`` — an undated job was left
    out of SLA met, so the demo read *100.0%* over rows of 0.0% (image 65)."""
    with tenant_ctx(brazos):
        _priorities(brazos)
        premises = make_premises(dana, address_line="65 Promise Ln")
        _done(brazos, premises, "kept", raised=T0, completed=T0 + timedelta(hours=2),
              due=T0 + timedelta(hours=4))
        _done(brazos, premises, "missed", raised=T0, completed=T0 + timedelta(hours=9),
              due=T0 + timedelta(hours=4))
        # No due date: measured against Normal's 72 h — done in 48 h, kept.
        _done(brazos, premises, "undated", raised=T0, completed=T0 + timedelta(hours=48))
        result = work_selectors.performance()
    assert result["tiles"]["sla_met_pct"] == "66.7"
    assert result["tiles"]["sla_measured"] == 3


# ── P5.2 / P5.8 · a held job's clock pauses ────────────────────────────────
def test_p52_two_days_on_hold_move_the_promise_two_days(brazos, dana):
    with tenant_ctx(brazos):
        _priorities(brazos)
        premises = make_premises(dana, address_line="66 Rain St")
        # Due in 24 h, finished in 60 h, but 48 h of it was on hold (rain).
        _done(brazos, premises, "rained", raised=T0, completed=T0 + timedelta(hours=60),
              due=T0 + timedelta(hours=24), held_seconds=48 * 3600)
        result = work_selectors.performance()
    assert result["tiles"]["sla_met_pct"] == "100.0"


# ── P5.6 · the table is paged in SQL, and the headline is its rows' sum ────
def test_p56_by_job_type_pages_and_the_headline_agrees_with_its_rows(brazos, dana):
    with tenant_ctx(brazos):
        _priorities(brazos)
        premises = make_premises(dana, address_line="67 Paging Pl")
        # 51 job types, so the smallest page (50) cuts the table in two.
        for n in range(3):
            _done(brazos, premises, f"set-{n}", raised=T0, completed=T0 + timedelta(hours=1),
                  kind="Meter set")
        for n in range(50):
            _done(brazos, premises, f"t-{n:02d}", raised=T0, completed=T0 + timedelta(hours=200),
                  kind=f"Type {n:02d}")
        first = work_selectors.performance(per=50)
        second = work_selectors.performance(per=50, page=2)
    assert first["total"] == 51
    assert len(first["rows"]) == 50 and len(second["rows"]) == 1
    # Volume, most first: the three meter sets lead.
    assert first["rows"][0]["job_type"] == "Meter set"
    rows = first["rows"] + second["rows"]
    assert sum(r["sla_met"] for r in rows) == first["tiles"]["sla_met"] == 3
    assert sum(r["sla_measured"] for r in rows) == first["tiles"]["sla_measured"] == 53
    assert first["tiles"]["sla_met_pct"] == "5.7"


def test_p56_the_cost_is_the_sum_of_rounded_lines(brazos, dana):
    """`BR-WRK-051`: the sum of the ROUNDED displayed lines — 10.005 + 10.005
    prints 20.02, not 20.01."""
    from decimal import Decimal

    with tenant_ctx(brazos):
        _priorities(brazos)
        premises = make_premises(dana, address_line="68 Cost Ct")
        order = _done(brazos, premises, "costed", raised=T0, completed=T0 + timedelta(hours=1))
        for n in (1, 2):
            work_models.WorkOrderCostLine.objects.create(
                tenant_id=brazos.id, work_order_id=order.id, sequence=n, kind="labour",
                description="Labour", qty=Decimal("1"), unit="h", rate=Decimal("10.005"),
                amount=Decimal("10.005"),
            )
        result = work_selectors.performance()
    assert result["rows"][0]["total_cost"] == "20.02"
    assert result["totals"]["total_cost"] == "20.02"


# ── P5.10 · a job type's own hours override its priority's ─────────────────
def test_p510_a_type_with_its_own_hours_stamps_that_promise(brazos, dana):
    from apps.work import promise

    with tenant_ctx(brazos):
        priorities = _priorities(brazos)
        work_services.seed_reference_list("work_order_types", [], "test")
        kind = work_models.WorkOrderType.objects.filter(tenant_id=brazos.id).first()
        promise.set_job_type_sla(dana, kind.id, {"sla_hours": 24})
        premises = make_premises(dana, address_line="69 Type Way")
        raised = w6.create_work_order(
            dana, None,
            {"type_id": str(kind.id), "type": kind.name, "premises_id": premises["id"],
             "priority_id": str(priorities["NORMAL"].id)},
        )
        order = work_tables.WorkOrder.objects.get(pk=raised["id"])
        # Stamped from the raise moment, a few ms before the row's created_at.
        assert abs(order.due_at - order.created_at - timedelta(hours=24)) < timedelta(seconds=5)
        # Blank is *the priority's* again — for the NEXT job; this one keeps
        # its stamped promise (`BR-WRK-018`).
        promise.set_job_type_sla(dana, kind.id, {"sla_hours": ""})
        again = w6.create_work_order(
            dana, None,
            {"type_id": str(kind.id), "type": kind.name, "premises_id": premises["id"],
             "priority_id": str(priorities["NORMAL"].id)},
        )
        later = work_tables.WorkOrder.objects.get(pk=again["id"])
        assert abs(later.due_at - later.created_at - timedelta(hours=72)) < timedelta(seconds=5)
        order.refresh_from_db()
        assert abs(order.due_at - order.created_at - timedelta(hours=24)) < timedelta(seconds=5)


# ── P5.3's read · the at-risk list ─────────────────────────────────────────
def test_p53_at_risk_lists_what_falls_inside_the_window_soonest_first(brazos, dana):
    from apps.work import promise

    with tenant_ctx(brazos):
        _priorities(brazos)
        premises = make_premises(dana, address_line="70 Risk Rd")
        now = timezone.now()

        def open_job(order_no, due, **extra):
            raised = w6.create_work_order(
                dana, None, {"type": "Meter set", "premises_id": premises["id"]}
            )
            work_tables.WorkOrder.objects.filter(pk=raised["id"]).update(
                order_no=order_no, due_at=due, **extra
            )

        open_job("late", now - timedelta(hours=1))
        open_job("soon", now + timedelta(hours=2))
        open_job("later", now + timedelta(hours=10))
        # Due an hour ago, but on hold since two hours ago — paused, so not
        # breaching: its promise is about an hour from now.
        open_job("held", now - timedelta(hours=1), held_at=now - timedelta(hours=2))

        no_window = promise.at_risk_page()
        assert [r["order_no"] for r in no_window["rows"]] == ["late"]
        assert no_window["window_hours"] is None

        workforce.set_default_target(dana, {"at_risk_window_hours": 4})
        page = promise.at_risk_page()
        assert [r["order_no"] for r in page["rows"]] == ["late", "held", "soon"]
        assert page["rows"][0]["promise"]["overdue"] is True
        assert page["rows"][2]["promise"]["overdue"] is False
        assert workforce.default_target()["at_risk_window_hours"] == 4
