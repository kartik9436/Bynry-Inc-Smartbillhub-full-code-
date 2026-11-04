# ── Trace ──────────────────────────────────────────────
# Change:   CR-168-BRC10 §F — the technician API (PO 2026-10-04: "you should
#           create apis for techncian app and use those apis wth payload to
#           complete the jobs"), lane FIELD-FIX
# Rules:    BR-WRK-025 (dispatch acts, append-only) · BR-MET-110 · HR-1 ·
#           hard rule 7 (audit)
# ───────────────────────────────────────────────────────
"""The three acts that had no route: accept, decline, and on the way / on site."""

from __future__ import annotations

import pytest
from django.urls import resolve

from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from apps.work import mobile
from apps.work import models as work_models
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana
from tests.test_us_met_helpers import field_actor, tenant_ctx
from tests.test_us_wrk_032_copies import _published_template, _raise

pytestmark = pytest.mark.django_db


def _job(actor, tenant):
    oid = _raise(actor, tenant, _published_template(actor, tenant))["id"]
    return oid, field_actor(oid, actor)


def test_the_three_routes_exist():
    for tail, name in (("accept", "mobile_accept"), ("decline", "mobile_decline"), ("acts", "mobile_act")):
        match = resolve(f"/api/brazosbend/work/mobile/jobs/01a10711-e839-7fba-a5e0-3762f041dd2e/{tail}")
        assert getattr(match.func, "cls", match.func).__name__ in (name, "WrappedAPIView"), match.func
        assert match.url_name in (None, name) and match.func.__module__ == "apps.work.api"


def test_accept_stamps_once_and_audits(brazos, dana):
    with tenant_ctx(brazos):
        oid, tech = _job(dana, brazos)
        first = mobile.accept_job(tech, oid)
        again = mobile.accept_job(tech, oid)
        order = work_tables.WorkOrder.objects.get(pk=oid)

    assert first["technician_acceptance"]["state"] == "accepted"
    assert again["technician_acceptance"]["at"] == first["technician_acceptance"]["at"]
    assert order.accepted_by_technician_id is not None


def test_decline_needs_a_reason_and_then_blocks_accept(brazos, dana):
    with tenant_ctx(brazos):
        oid, tech = _job(dana, brazos)
        with pytest.raises(errors.ValidationError) as no_reason:
            mobile.decline_job(tech, oid, {})
        out = mobile.decline_job(tech, oid, {"reason": "Van in the shop"})
        with pytest.raises(errors.BizError) as later:
            mobile.accept_job(tech, oid)

    assert no_reason.value.message_key == "work.mobile.decline_reason_required"
    assert out["technician_acceptance"] == {
        "state": "declined", "at": out["technician_acceptance"]["at"], "reason": "Van in the shop",
    }
    assert later.value.message_key == "work.mobile.job_already_declined"


def test_depart_and_arrive_append_rows_and_assign_is_refused(brazos, dana):
    with tenant_ctx(brazos):
        oid, tech = _job(dana, brazos)
        mobile.accept_job(tech, oid)
        mobile.field_act(tech, oid, {"act": "depart"})
        mobile.field_act(tech, oid, {"act": "arrive"})
        with pytest.raises(errors.ValidationError) as refused:
            mobile.field_act(tech, oid, {"act": "assign"})
        acts = list(
            work_models.WorkOrderAssignment.objects.filter(work_order_id=oid)
            .order_by("at", "id")
            .values_list("act", flat=True)
        )

    assert acts[-2:] == ["depart", "arrive"]
    assert refused.value.message_key == "work.mobile.act_not_a_field_act"


def test_another_technicians_job_is_a_404(brazos, dana):
    with tenant_ctx(brazos):
        oid, _tech = _job(dana, brazos)
        with pytest.raises(errors.NotFoundError):
            mobile.accept_job(dana, oid)  # Dana holds no technician profile


# ══════════════════════════════════════════════════════════════════════════
# The sync design: capture token, held-for-review, photo links, accept hold.
# ══════════════════════════════════════════════════════════════════════════
import hashlib  # noqa: E402
import uuid  # noqa: E402

from apps.work import photo_links, sync  # noqa: E402
from apps.work.evidence_models import WorkPhotoLink  # noqa: E402
from apps.work.sync_models import WorkSyncReceipt  # noqa: E402
from tests.test_us_wrk_047_049_evidence import TINY_PNG  # noqa: E402

FIX = {"lat": "29.560100", "lng": "-95.807200", "accuracy_m": "8.0", "fix_at": "2026-03-15T16:05:00Z"}


def _ready(dana, brazos):
    """A job assigned to a technician who has ACCEPTED it, every safety row
    and task ticked — what a close needs except its photographs."""
    from apps.work import checklist

    oid, tech = _job(dana, brazos)
    mobile.accept_job(tech, oid)
    for row in work_models.WorkOrderSafety.objects.filter(work_order_id=oid):
        checklist.tick_safety(tech, oid, row.id)
    return oid, tech


def _token(tech):
    return mobile.issue_capture_token(tech)["capture_token"]


def _photo_items(oid, token, *, prefix="p"):
    """One `photo` item per photo-required task and reading, each with its own
    client photo id and the sha256 of TINY_PNG."""
    items, digest = [], hashlib.sha256(TINY_PNG).hexdigest()
    rows = [("task_id", r.id) for r in work_models.WorkOrderTask.objects.filter(work_order_id=oid, photo_required=True)]
    rows += [("reading_id", r.id) for r in work_models.WorkOrderReading.objects.filter(work_order_id=oid, photo_required=True)]
    for n, (field, rid) in enumerate(rows):
        items.append({
            "key": f"{prefix}-{n}", "kind": "photo", "seq": n, "captured_at": "2026-03-15T15:40:00Z",
            "capture_token": token, "location": FIX,
            "payload": {"photo_id": str(uuid.uuid4()), "sha256": digest, field: str(rid)},
        })
    return items


def _close(token, *, key="close-1", accuracy="8.0"):
    return {"key": key, "kind": "close", "seq": 99, "captured_at": "2026-03-15T16:07:00Z",
            "capture_token": token, "location": {**FIX, "accuracy_m": accuracy},
            "payload": {"outcome": "passed"}}


def test_photo_links_are_created_with_the_record_and_a_replay_answers_the_same_link(brazos, dana):
    with tenant_ctx(brazos):
        oid, tech = _ready(dana, brazos)
        items = _photo_items(oid, _token(tech))
        first = sync.sync_batch(tech, oid, {"items": items})
        again = sync.sync_batch(tech, oid, {"items": items})
        links = WorkPhotoLink.objects.filter(work_order_id=oid).count()

    assert [r["result"] for r in first["items"]] == ["accepted"] * len(items)
    assert all(r["detail"]["state"] == "pending" for r in first["items"])
    assert [r["detail"]["upload_url"] for r in again["items"]] == [r["detail"]["upload_url"] for r in first["items"]]
    assert links == len(items), "a replay made a second link"
    assert set(first["acknowledged"]) == {i["key"] for i in items}


def test_close_with_photos_pending_lands_and_accept_waits_for_the_last_required_one(brazos, dana):
    with tenant_ctx(brazos):
        oid, tech = _ready(dana, brazos)
        token = _token(tech)
        items = _photo_items(oid, token)
        sync.sync_batch(tech, oid, {"items": [*items, _close(token)]})
        order = work_tables.WorkOrder.objects.get(pk=oid)
        assert order.state == work_tables.WO_COMPLETED, "a close with its photos pending was not accepted"
        with pytest.raises(errors.BizError) as held:
            w6.accept_field_result(dana, oid)
        assert held.value.message_key == "work.order.photos_uploading"
        assert held.value.params["count"] == len(items)
        for item in items:
            pid = item["payload"]["photo_id"]
            photo_links.receive_bytes(tech, pid, TINY_PNG, "image/png")
            link = WorkPhotoLink.objects.get(photo_id=pid)
            photo_links.run_photo_job({"payload": {"link_id": str(link.id)}})
        w6.accept_field_result(dana, oid)
        order.refresh_from_db()

    assert order.accepted_at is not None


def test_an_optional_photo_still_uploading_does_not_hold_accept(brazos, dana):
    with tenant_ctx(brazos):
        oid, tech = _ready(dana, brazos)
        token = _token(tech)
        items = _photo_items(oid, token)
        optional = work_models.WorkOrderTask.objects.filter(work_order_id=oid, photo_required=False).first()
        extra = {"key": "opt-1", "kind": "photo", "seq": 50, "captured_at": "2026-03-15T15:41:00Z",
                 "capture_token": token, "location": FIX,
                 "payload": {"photo_id": str(uuid.uuid4()), "sha256": hashlib.sha256(TINY_PNG).hexdigest(),
                             "task_id": str(optional.id)}}
        sync.sync_batch(tech, oid, {"items": [*items, extra, _close(token)]})
        for item in items:
            pid = item["payload"]["photo_id"]
            photo_links.receive_bytes(tech, pid, TINY_PNG, "image/png")
            photo_links.run_photo_job({"payload": {"link_id": str(WorkPhotoLink.objects.get(photo_id=pid).id)}})
        w6.accept_field_result(dana, oid)  # the optional one is still pending


def test_a_damaged_upload_is_asked_for_again_and_a_second_upload_adds_nothing(brazos, dana):
    with tenant_ctx(brazos):
        oid, tech = _ready(dana, brazos)
        items = _photo_items(oid, _token(tech))[:1]
        sync.sync_batch(tech, oid, {"items": items})
        pid = items[0]["payload"]["photo_id"]
        with pytest.raises(errors.BizError) as damaged:
            photo_links.receive_bytes(tech, pid, TINY_PNG[:-5], "image/png")
        first = photo_links.receive_bytes(tech, pid, TINY_PNG, "image/png")
        second = photo_links.receive_bytes(tech, pid, TINY_PNG, "image/png")

    assert damaged.value.message_key == "work.photo.hash_mismatch"
    assert first["duplicate"] is False and second["duplicate"] is True


def test_a_shared_tablet_item_is_the_captors_even_when_another_login_sends_it(brazos, dana):
    from types import SimpleNamespace

    with tenant_ctx(brazos):
        oid, x = _ready(dana, brazos)
        token = _token(x)
        y = SimpleNamespace(id=dana.id, role="system_admin")  # the courier
        task = work_models.WorkOrderTask.objects.filter(work_order_id=oid).first()
        out = sync.sync_batch(y, oid, {"items": [{
            "key": "x-tick-1", "kind": "task_tick", "seq": 1, "captured_at": "2026-03-15T15:30:00Z",
            "capture_token": token, "location": FIX, "payload": {"task_id": str(task.id)},
        }]})
        receipt = WorkSyncReceipt.objects.get(work_order_id=oid, key="x-tick-1")
        technician = mobile.technician_of(x)

    assert out["items"][0]["result"] == "accepted"
    assert receipt.captured_by_technician_id == technician.id
    assert receipt.accepted_by_id == x.id
    assert str(receipt.accuracy_m) == "8.0"


def test_an_item_from_a_technician_who_never_accepted_goes_back_to_the_technician(brazos, dana):
    """FLIPPED 2026-10-21 — PO, *"back to the technician"* (`BR-WRK-063`
    superseded for field items). Until then this item was STORED and answered
    `held_for_review`; now it is refused with its reason, NOT acknowledged,
    and nothing is stored, so the same key posts once the job is accepted."""
    with tenant_ctx(brazos):
        oid, tech = _job(dana, brazos)  # assigned, NOT accepted
        task = work_models.WorkOrderTask.objects.filter(work_order_id=oid).first()
        item = {
            "key": "na-1", "kind": "task_tick", "seq": 1, "captured_at": "2026-03-15T15:30:00Z",
            "capture_token": _token(tech), "payload": {"task_id": str(task.id)},
        }
        out = sync.sync_batch(tech, oid, {"items": [item]})
        stored = WorkSyncReceipt.objects.filter(work_order_id=oid, key="na-1").exists()
        # The technician fixes it: accepts the job (and clears the safety
        # lock a task tick waits on), then the SAME key goes again.
        from apps.work import checklist

        mobile.accept_job(tech, oid)
        for row in work_models.WorkOrderSafety.objects.filter(work_order_id=oid):
            checklist.tick_safety(tech, oid, row.id)
        again = sync.sync_batch(tech, oid, {"items": [item]})

    answer = out["items"][0]
    assert answer["result"] == "refused" and answer["ack"] is False
    assert answer["detail"]["reason"] == "accept_the_job_first"
    assert answer["detail"]["message_key"] == "work.mobile.accept_the_job_first"
    assert out["acknowledged"] == [] and out["held_for_review"] == 0
    assert stored is False
    assert again["items"][0]["result"] == "accepted", again["items"][0]


def test_a_close_with_a_300m_fix_is_accepted_and_flagged_not_precise(brazos, dana):
    with tenant_ctx(brazos):
        oid, tech = _ready(dana, brazos)
        token = _token(tech)
        sync.sync_batch(tech, oid, {"items": [*_photo_items(oid, token), _close(token, accuracy="300")]})
        order = work_tables.WorkOrder.objects.get(pk=oid)

    assert order.state == work_tables.WO_COMPLETED
    assert order.field_data["close_location"]["precise"] is False
    assert order.field_data["close_location"]["accuracy_m"] == "300.0"
