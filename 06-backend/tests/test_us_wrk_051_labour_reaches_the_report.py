# ── Trace ──────────────────────────────────────────────
# Story:    US-WRK-051 TC-2 (the rate is stamped AT CLOSE) · US-WRK-053 TC-1
#           (the worked figure) · BR-WRK-020 · BR-WRK-050 · BR-WRK-051
# Defect:   DEF-WRK-4124 — the labour line could never appear on a real report
# ───────────────────────────────────────────────────────
"""**THE FIGURE, THROUGH A REAL ORDER — which is what nothing did.**

WHY THIS FILE EXISTS BESIDE `test_us_wrk_053_costing.py`
========================================================
That file pins the arithmetic beautifully and pins the INPUT nowhere. Every one
of its cases either calls `costing.compute()` with hand-built `LabourInput` and
`PartInput` values, or constructs a local `class _Order` that declares
`minutes_on_site = 52` and `labour_rate_snapshot` itself. So it proves that
**given** 52 minutes and a rate of `48.5000` the answer is `42.20`, and says
nothing whatever about whether a work order can ever carry those two things.

It could not. Two independent reasons, and either alone was fatal:

  1. `snapshot_labour_rate_at_close()` had **no caller** — one reference in the
     entire repository, its own `def` line — so `labour_rate_snapshot` was NULL
     on every order that had ever closed;
  2. `minutes_on_site` had **no column**, and `costing.minutes_on_site()` reads
     it through `getattr(order, ..., None)`, which cannot fail.

`WO-4822` therefore reported `96.00 + 0.22 = 96.22`. The signed figure is
`138.42`. **Roughly a third of the wave's own headline number was unreachable
and every test was green**, because no test went from a closed order to a
report.

So every case below starts from an ORDER and ends at what
`GET /work-orders/{id}/cost` would serve.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.utils import timezone

from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from apps.work import checklist
from apps.work import models as work_models
from apps.work import services as work_services

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin
from tests.test_us_met_helpers import field_close  # CR-168 P1.34 — close as the field
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_wrk_032_copies import _published_template, _raise

pytestmark = pytest.mark.django_db

FIELD_TECHNICIAN_HOURLY = Decimal("48.5000")


def _rate(tenant, role="field_technician", hourly=FIELD_TECHNICIAN_HOURLY):
    return work_models.LabourRate.objects.create(
        tenant_id=tenant.id,
        role=role,
        hourly=hourly,
        effective_from=timezone.now().date(),
    )


def _technician(actor, tenant, label="Field technician"):
    """A person row whose typed label slugifies to the rate's role code."""
    return work_models.Technician.objects.create(
        tenant_id=tenant.id, user_id=actor.id, role_label=label
    )


def _closed_order(actor, tenant, *, minutes=52, arrive=True):
    """An order taken all the way to CLOSE, through the product's own doors."""
    tid = _published_template(actor, tenant)
    order_id = _raise(actor, tenant, tid)["id"]
    order = work_tables.WorkOrder.objects.get(pk=order_id)
    technician = _technician(actor, tenant)
    order.assignee_technician = technician
    order.save(update_fields=["assignee_technician", "updated_at"])

    completed_at = timezone.now()
    if arrive:
        row = work_models.WorkOrderAssignment.objects.create(
            tenant_id=tenant.id,
            work_order_id=order_id,
            act=work_models.WorkOrderAssignment.ACT_ARRIVE,
            technician=technician,
            actor_id=actor.id,
        )
        # `at` is auto_now_add, so it is moved explicitly to make the span exact.
        work_models.WorkOrderAssignment.objects.filter(pk=row.pk).update(
            at=completed_at - timezone.timedelta(minutes=minutes)
        )

    for safety in work_models.WorkOrderSafety.objects.filter(work_order_id=order_id):
        checklist.tick_safety(actor, order_id, safety.id)
    field_close(actor, order_id, outcome="passed", completed_at=completed_at)
    return work_tables.WorkOrder.objects.get(pk=order_id)


# ══════════════════════════════════════════════════════════════════════════
# The close stamps all three — the fix for DEF-WRK-4124
# ══════════════════════════════════════════════════════════════════════════
def test_the_close_stamps_the_rate_the_role_and_the_minutes(brazos, dana):
    """`US-WRK-051` TC-2 and `BR-WRK-020`. Delete the call in
    `submit_field_result` and this goes red on the first assertion."""
    with tenant_ctx(brazos):
        _rate(brazos)
        order = _closed_order(dana, brazos, minutes=52)
        assert order.labour_rate_snapshot == FIELD_TECHNICIAN_HOURLY
        assert order.labour_role == "field_technician"
        assert order.minutes_on_site == 52


def test_the_minutes_are_the_last_arrival_to_the_close_not_the_first(brazos, dana):
    """A job visited, left and revisited has two arrivals. Charging from the
    FIRST would bill the customer for the gap between visits."""
    with tenant_ctx(brazos):
        _rate(brazos)
        tid = _published_template(dana, brazos)
        order_id = _raise(dana, brazos, tid)["id"]
        technician = _technician(dana, brazos)
        order = work_tables.WorkOrder.objects.get(pk=order_id)
        order.assignee_technician = technician
        order.save(update_fields=["assignee_technician", "updated_at"])
        completed_at = timezone.now()
        for minutes_before in (300, 52):  # a morning visit, then the real one
            row = work_models.WorkOrderAssignment.objects.create(
                tenant_id=brazos.id,
                work_order_id=order_id,
                act=work_models.WorkOrderAssignment.ACT_ARRIVE,
                technician=technician,
                actor_id=dana.id,
            )
            work_models.WorkOrderAssignment.objects.filter(pk=row.pk).update(
                at=completed_at - timezone.timedelta(minutes=minutes_before)
            )
        for safety in work_models.WorkOrderSafety.objects.filter(work_order_id=order_id):
            checklist.tick_safety(dana, order_id, safety.id)
        field_close(dana, order_id, outcome="passed", completed_at=completed_at)
        assert work_tables.WorkOrder.objects.get(pk=order_id).minutes_on_site == 52


def test_no_recorded_arrival_stamps_nothing_rather_than_guessing(brazos, dana):
    """`costing.py`: a guess from `created_at` would price a job at however long
    it sat in a queue. NULL reads as *we cannot say*; a wrong duration on a
    frozen money report reads as a fact."""
    with tenant_ctx(brazos):
        _rate(brazos)
        order = _closed_order(dana, brazos, arrive=False)
        assert order.minutes_on_site is None
        assert order.labour_rate_snapshot == FIELD_TECHNICIAN_HOURLY, "the rate still stamps"


def test_a_job_with_no_rate_for_its_role_carries_no_labour_line_not_a_free_one(brazos, dana):
    """No `labour_rates` row at all. `costing.py`'s posture: absent, not zero."""
    from apps.work import costing

    with tenant_ctx(brazos):
        order = _closed_order(dana, brazos, minutes=52)  # no _rate() call
        assert order.labour_rate_snapshot is None
        lines, total = costing.work_order_cost_lines(order)
        assert [line for line in lines if line.kind == "labour"] == []


# ══════════════════════════════════════════════════════════════════════════
# THE WORKED FIGURE, end to end — 42.20 + 96.00 + 0.22 = 138.42
# ══════════════════════════════════════════════════════════════════════════
def test_the_signed_figure_is_reachable_from_a_real_order(brazos, dana):
    """**`US-WRK-053` TC-1, but through the product rather than through
    `compute()`.** 52 minutes of a field technician at $48.50 an hour is $42.20;
    one meter at $96.00 and one seal at $0.22 make the job $138.42, and that is
    the sum a reader gets adding the three printed lines.

    Before `DEF-WRK-4124` this order reported `96.22`."""
    from apps.work import costing

    with tenant_ctx(brazos):
        _rate(brazos)
        order = _closed_order(dana, brazos, minutes=52)

        # Two parts USED, through #75's own door.
        materials = list(
            work_models.WorkOrderMaterial.objects.filter(work_order_id=order.id).order_by(
                "part__part_no"
            )
        )
        assert len(materials) >= 2, "the fixture template plans three parts"
        priced = []
        for row in materials[:2]:
            checklist.set_material_used(dana, order.id, row.id, {"used_qty": "1"})
            priced.append(row.part.unit_cost)
        for row in materials[2:]:
            # left unreported — NULL is not zero, and contributes no line
            pass

        order.refresh_from_db()
        lines, total = costing.work_order_cost_lines(order)

        labour = [line for line in lines if line.kind == "labour"]
        assert len(labour) == 1, "the labour line EXISTS — this is the whole defect"
        assert labour[0].qty == Decimal("0.87"), "52 minutes booked to two decimals"
        assert labour[0].rate == FIELD_TECHNICIAN_HOURLY
        assert labour[0].display_amount == Decimal("42.20")

        parts = [line for line in lines if line.kind != "labour"]
        assert len(parts) == 2, "only the parts REPORTED as used are priced"

        # The total is the sum of the ROUNDED displayed lines (`BR-WRK-051`).
        expected = sum(line.display_amount for line in lines)
        assert total == expected
        assert total == Decimal("42.20") + sum(
            costing.display(cost) for cost in priced
        )


def test_the_report_generated_at_accept_carries_the_labour_line(brazos, dana):
    """`BR-WRK-050` — generated ONCE, by Accept, frozen. The persisted lines are
    what `GET /work-orders/{id}/cost` serves, so this is what a reader sees."""
    with tenant_ctx(brazos):
        _rate(brazos)
        order = _closed_order(dana, brazos, minutes=52)
        materials = list(
            work_models.WorkOrderMaterial.objects.filter(work_order_id=order.id).order_by(
                "part__part_no"
            )
        )
        for row in materials[:2]:
            checklist.set_material_used(dana, order.id, row.id, {"used_qty": "1"})

        w6.accept_field_result(dana, order.id)

        report = work_models.WorkOrderReport.objects.get(work_order_id=order.id, version=1)
        stored = list(
            work_models.WorkOrderCostLine.objects.filter(work_order_id=order.id).order_by(
                "sequence"
            )
        )
        assert [line.kind for line in stored].count("labour") == 1, (
            "the frozen report carries a labour line"
        )
        assert report.total == sum(
            line.amount.quantize(Decimal("0.01")) for line in stored
        )
        assert report.total > Decimal("96.22"), (
            "the total is no longer parts-only — DEF-WRK-4124"
        )
