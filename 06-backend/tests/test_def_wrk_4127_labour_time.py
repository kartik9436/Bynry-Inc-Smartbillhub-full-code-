# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-WRK-4127 — minutes on site were measured from a timestamp that
#           records the SYNC, not the arrival, so an offline day priced no labour
# Ruling:   PO 2026-10-05, verbatim: *"allow technicain to fill in time"*
#           (decision log, top row, item (3))
# Rules:    BR-WRK-020 (the rate is fixed at close) · BR-WRK-025 (the assignment
#           history is append-only — the entered times are NEW data on the
#           close, never an edit of an `arrive` row) · BR-WRK-051 (the labour
#           line) · BR-WRK-042 (they travel in the offline batch)
# ───────────────────────────────────────────────────────
"""**THE TECHNICIAN'S OWN TWO TIMES PRICE THE LABOUR — through a real batch.**

The PO's worked figure: arrived 09:00, finished 10:35 → 95 minutes → 1.58 h
booked × $48.50 = **$76.63**. Every case starts from a sync batch, which is the
only way a phone closes a job, and ends at what the cost report would serve.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.utils import timezone

from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from apps.work import costing, dispatch, sync
from apps.work import models as work_models
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana
from tests.test_us_met_helpers import field_actor, tenant_ctx
from tests.test_us_wrk_044_046_sync import _batch, _order_on_a_meter, _rows

pytestmark = pytest.mark.django_db

RATE = Decimal("48.5000")

ARRIVED = "2026-03-15T09:00:00Z"
FINISHED = "2026-03-15T10:35:00Z"


def _ready(actor, tenant):
    """An order on a meter, held by a FIELD TECHNICIAN whose typed role prices
    at $48.50 an hour."""
    work_models.LabourRate.objects.create(
        tenant_id=tenant.id, role="field_technician", hourly=RATE,
        effective_from=timezone.now().date(),
    )
    oid = _order_on_a_meter(actor, tenant)
    field = field_actor(oid, actor)
    work_models.Technician.objects.filter(tenant_id=tenant.id, user_id=field.id).update(
        role_label="Field technician"
    )
    return oid, field


def _with_times(batch, arrived=ARRIVED, finished=FINISHED):
    """The close carries the two times the technician confirmed on the phone."""
    close = batch["items"][-1]
    assert close["kind"] == "close"
    close["payload"] = {**close["payload"], "arrived_at": arrived, "finished_at": finished}
    return batch


def _offline_arrival_at_sync_time(tenant, oid, field):
    """The defect's own shape: the `arrive` act reached the server with the
    batch at 17:40, so its `at` is the SYNC — after the close."""
    technician = work_models.Technician.objects.get(tenant_id=tenant.id, user_id=field.id)
    work_models.WorkOrderAssignment.objects.create(
        tenant_id=tenant.id, work_order_id=oid,
        act=work_models.WorkOrderAssignment.ACT_ARRIVE,
        technician=technician, actor_id=field.id,
    )


def test_the_entered_times_price_the_labour_at_76_63(brazos, dana):
    """**THE MONEY ASSERTION.** 09:00 → 10:35 = 95 min = 1.58 h × $48.50 =
    $76.63. Before the fix this order carried NO labour line at all: the only
    arrival was stamped at the sync, after the close, so the span was None."""
    with tenant_ctx(brazos):
        oid, field = _ready(dana, brazos)
        _offline_arrival_at_sync_time(brazos, oid, field)
        out = sync.sync_batch(field, oid, _with_times(_batch(oid, _rows(oid))))
        assert out["accepted"] == len(out["items"]), out
        order = work_tables.WorkOrder.objects.get(pk=oid)
        assert order.minutes_on_site == 95
        lines, _total = costing.work_order_cost_lines(order)
        labour = [line for line in lines if line.kind == "labour"]
        assert len(labour) == 1, "the offline job now carries its labour line"
        assert labour[0].qty == Decimal("1.58")
        assert labour[0].rate == RATE
        assert labour[0].display_amount == Decimal("76.63")


def test_the_frozen_report_at_accept_carries_76_63(brazos, dana):
    """`BR-WRK-050` — what the office freezes at Accept is the same figure."""
    with tenant_ctx(brazos):
        oid, field = _ready(dana, brazos)
        sync.sync_batch(field, oid, _with_times(_batch(oid, _rows(oid))))
        w6.accept_field_result(dana, oid)
        stored = work_models.WorkOrderCostLine.objects.get(work_order_id=oid, kind="labour")
        assert stored.amount.quantize(Decimal("0.01")) == Decimal("76.63")


def test_the_office_sees_both_times_on_the_order_it_accepts(brazos, dana):
    """The order row's `closed` block carries the two times and the minutes,
    which is what the order page prints beside Accept and Send back."""
    with tenant_ctx(brazos):
        oid, field = _ready(dana, brazos)
        sync.sync_batch(field, oid, _with_times(_batch(oid, _rows(oid))))
        closed = dispatch.order_row(oid)["closed"]
    times = closed["labour_time"]
    assert times["minutes"] == 95
    assert times["arrived_at"].startswith("2026-03-15T09:00:00")
    assert times["finished_at"].startswith("2026-03-15T10:35:00")


def test_the_entered_times_are_new_data_and_no_assignment_row_moves(brazos, dana):
    """`BR-WRK-025` — the history is append-only. The entered times live on the
    close; the `arrive` row the sync wrote keeps its own `at`."""
    with tenant_ctx(brazos):
        oid, field = _ready(dana, brazos)
        _offline_arrival_at_sync_time(brazos, oid, field)
        before = list(
            work_models.WorkOrderAssignment.objects.filter(work_order_id=oid).values_list("id", "at")
        )
        sync.sync_batch(field, oid, _with_times(_batch(oid, _rows(oid))))
        after = list(
            work_models.WorkOrderAssignment.objects.filter(work_order_id=oid).values_list("id", "at")
        )
    assert after == before


def test_finished_before_arrived_goes_back_to_the_technician_and_is_never_priced(brazos, dana):
    """A clock disagreeing with itself must not produce a figure — the close
    goes BACK to the technician to correct (PO 2026-10-21, *"back to the
    technician"*; until then it was stored and flagged for the office), and no
    labour is priced from it."""
    with tenant_ctx(brazos):
        oid, field = _ready(dana, brazos)
        batch = _with_times(_batch(oid, _rows(oid)), arrived=FINISHED, finished=ARRIVED)
        out = sync.sync_batch(field, oid, batch)
        close = [item for item in out["items"] if item["kind"] == "close"][0]
        assert close["result"] == sync.RESULT_REFUSED, close
        assert close["ack"] is False
        order = work_tables.WorkOrder.objects.get(pk=oid)
        assert order.minutes_on_site is None


def test_a_job_sent_back_and_closed_again_is_priced_from_the_new_times(brazos, dana):
    """The office sends the job back over the times; the technician corrects
    them and closes again. The labour is the CORRECTED span, not the first."""
    with tenant_ctx(brazos):
        oid, field = _ready(dana, brazos)
        sync.sync_batch(field, oid, _with_times(_batch(oid, _rows(oid)), finished="2026-03-15T13:00:00Z"))
        assert work_tables.WorkOrder.objects.get(pk=oid).minutes_on_site == 240
        w6.send_back_field_result(dana, oid, "Finish time looks wrong")
        again = {"items": [{
            "key": "ortiz-01-2026-03-15-close-2", "kind": "close", "seq": 1,
            "captured_at": "2026-03-15T10:40:00Z",
            "payload": {"outcome": "passed", "arrived_at": ARRIVED, "finished_at": FINISHED},
        }]}
        out = sync.sync_batch(field, oid, again)
        assert out["accepted"] == 1, out
        order = work_tables.WorkOrder.objects.get(pk=oid)
        assert order.minutes_on_site == 95
        labour = [line for line in costing.work_order_cost_lines(order)[0] if line.kind == "labour"]
        assert labour[0].display_amount == Decimal("76.63")


def test_a_close_without_entered_times_still_reads_the_last_arrival(brazos, dana):
    """An older phone that sends no times keeps today's behaviour exactly."""
    with tenant_ctx(brazos):
        oid, field = _ready(dana, brazos)
        out = sync.sync_batch(field, oid, _batch(oid, _rows(oid)))
        assert out["accepted"] == len(out["items"]), out
        assert work_tables.WorkOrder.objects.get(pk=oid).minutes_on_site is None
