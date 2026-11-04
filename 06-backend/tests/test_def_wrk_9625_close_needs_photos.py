# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-WRK-9625 — the server closed a job with its required
#           photographs missing when the close arrived through the field sync
#           (WO-0044: three photo-required tasks, no photograph, stored
#           *completed* and then accepted by the office).
# Change:   CR-168-BRC10 lane FIELD-FIX; FLIPPED by CR-187-BRC10 2026-10-21
# Rules:    BR-WRK-040 — **SUPERSEDED 2026-10-21** (PO: *"warn"*; decision log
#           *"Field app: the PO corrects four of the ten answers"* item 3) ·
#           BR-WRK-041 (the close is `submit_field_result`) · BR-MET-110 ·
#           ruling 18 (only the field closes)
# ───────────────────────────────────────────────────────
"""A missing required photograph WARNS; the close lands WITH the gap recorded.

⚠ **THIS FILE ASSERTED THE OPPOSITE UNTIL 2026-10-21.** `DEF-WRK-9625` moved
`BR-WRK-040`'s stop from the phone's Close button to the server, below every
door, and these cases proved the server REFUSED the close. The PO then
corrected the rule — *"warn"* — so the close is accepted and the server writes
the gap onto it (`field_data["photos_missing"]`), where the office's
acceptance queue reads it. What `DEF-WRK-9625` was really about survives the
flip: **WO-0044 reached the office with nothing saying three photographs were
missing.** It now reaches the office saying exactly that, by every door.
"""

from __future__ import annotations

import pytest

from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from apps.work import models as work_models
from apps.work import checklist, field_outcomes, sync

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana
from tests.test_us_met_helpers import field_actor, tenant_ctx
from tests.test_us_wrk_032_copies import _published_template, _raise
from tests.test_us_wrk_047_049_evidence import _satisfy_required_photos

pytestmark = pytest.mark.django_db


def _ready_but_for_photos(actor, tenant):
    """A job with every safety row and task ticked and NO photograph taken —
    the state WO-0044 was closed in."""
    oid = _raise(actor, tenant, _published_template(actor, tenant))["id"]
    tech = field_actor(oid, actor)
    for row in work_models.WorkOrderSafety.objects.filter(work_order_id=oid):
        checklist.tick_safety(tech, oid, row.id)
    for row in work_models.WorkOrderTask.objects.filter(work_order_id=oid):
        checklist.tick_task(tech, oid, row.id)
    return oid, tech


def _close_item(key="wo-close-1"):
    return {
        "key": key,
        "kind": "close",
        "seq": 1,
        "captured_at": "2026-03-15T16:07:00Z",
        "payload": {"outcome": "passed"},
    }


def test_9625_a_sync_close_with_photographs_missing_lands_with_the_gap_recorded(brazos, dana):
    with tenant_ctx(brazos):
        oid, tech = _ready_but_for_photos(dana, brazos)
        out = sync.sync_batch(tech, oid, {"items": [_close_item()]})
        order = work_tables.WorkOrder.objects.get(pk=oid)

    item = out["items"][0]
    assert item["result"] == "accepted", item
    assert order.state == work_tables.WO_COMPLETED
    gap = order.field_data["photos_missing"]
    # The count and every missing row, written by the SERVER on the close.
    assert gap["count"] == 4, gap
    assert len(gap["items"]) == 4 and all(i["prompt"] for i in gap["items"]), gap
    assert gap["br_ref"] == "BR-WRK-040"


def test_9625_the_metering_door_records_the_gap_too(brazos, dana):
    """Every door reaches `submit_field_result`, so the record is made there."""
    with tenant_ctx(brazos):
        oid, tech = _ready_but_for_photos(dana, brazos)
        w6.submit_field_result(tech, oid, outcome="passed")
        order = work_tables.WorkOrder.objects.get(pk=oid)

    assert order.state == work_tables.WO_COMPLETED
    assert order.field_data["photos_missing"]["count"] == 4


def test_9625_the_office_sees_the_gap_on_the_acceptance_queue(brazos, dana):
    """The close is recorded with the gap AND THE OFFICE SEES IT (the PO's
    words) — on the queue row and on the job's outcome."""
    with tenant_ctx(brazos):
        oid, tech = _ready_but_for_photos(dana, brazos)
        sync.sync_batch(tech, oid, {"items": [_close_item()]})
        queue = field_outcomes.office_queue()
        outcome = field_outcomes.order_outcome(oid)

    row = next(r for r in queue["rows"] if r["id"] == str(oid))
    assert row["photos_missing"] == 4
    assert len(row["photos_missing_items"]) == 4
    assert outcome["photos_missing"] == 4


def test_9625_a_phone_cannot_write_the_gap_itself(brazos, dana):
    """The count is the server's: a `photos_missing` the phone sent is dropped,
    and a close with nothing missing carries no gap at all."""
    with tenant_ctx(brazos):
        oid, tech = _ready_but_for_photos(dana, brazos)
        _satisfy_required_photos(tech, oid)
        item = _close_item("wo-close-3")
        item["payload"]["field_data"] = {"photos_missing": {"count": 0, "items": []}, "note": "ok"}
        out = sync.sync_batch(tech, oid, {"items": [item]})
        order = work_tables.WorkOrder.objects.get(pk=oid)
        outcome = field_outcomes.order_outcome(oid)

    assert out["items"][0]["result"] == "accepted", out["items"][0]
    assert "photos_missing" not in order.field_data
    assert order.field_data["note"] == "ok"
    assert outcome["photos_missing"] == 0 and outcome["photos_missing_items"] == []


def test_9625_once_the_photographs_are_in_the_close_lands_clean(brazos, dana):
    with tenant_ctx(brazos):
        oid, tech = _ready_but_for_photos(dana, brazos)
        _satisfy_required_photos(tech, oid)
        out = sync.sync_batch(tech, oid, {"items": [_close_item("wo-close-2")]})
        order = work_tables.WorkOrder.objects.get(pk=oid)

    assert out["items"][0]["result"] == "accepted", out["items"][0]
    assert order.state == work_tables.WO_COMPLETED
    assert "photos_missing" not in (order.field_data or {})


def test_9625_a_job_whose_template_asks_for_no_photograph_closes(brazos, dana):
    """`not photo_required` is *never asked*, and it records nothing."""
    no_photo_tasks = [{"title": "Confirm address and customer", "est_minutes": 3}]
    with tenant_ctx(brazos):
        tid = _published_template(dana, brazos, tasks=no_photo_tasks)
        oid = _raise(dana, brazos, tid)["id"]
        work_models.WorkOrderReading.objects.filter(work_order_id=oid).update(
            photo_required=False
        )
        tech = field_actor(oid, dana)
        for row in work_models.WorkOrderSafety.objects.filter(work_order_id=oid):
            checklist.tick_safety(tech, oid, row.id)
        w6.submit_field_result(tech, oid, outcome="passed")
        order = work_tables.WorkOrder.objects.get(pk=oid)

    assert order.state == work_tables.WO_COMPLETED
    assert "photos_missing" not in (order.field_data or {})
