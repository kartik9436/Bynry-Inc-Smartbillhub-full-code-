# ── Trace ──────────────────────────────────────────────
# Change:   CR-168-BRC10 §F — TECHNICIAN SYNC DESIGN (5): "Phone → office: the
#           office is told when a job closes, when its photos are complete
#           (Accept unlocks), and when anything is flagged Needs review."
#           Lane FIELD-2.
# Rules:    BR-NOT-021 · BR-NOT-019 · BR-NOT-020 · BR-WRK-062 · BR-WRK-063 ·
#           CLAUDE.md rule 6
# ───────────────────────────────────────────────────────
"""The office's bell, driven through the REAL sync, photo job, queue and
dispatcher — nothing stubbed. Each case reads the inbox a clerk reads."""

from __future__ import annotations

import uuid
from datetime import datetime
from datetime import timezone as dt_timezone

import pytest

from apps.work import connection_models as work_tables
from apps.notifications import dispatcher, in_app, models, seed_templates
from apps.work import photo_links, sync
from apps.work.evidence_models import WorkPhotoLink

from tests.test_cr168_technician_api import (
    FIX,
    TINY_PNG,
    _close,
    _photo_items,
    _ready,
    _token,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

SEEDED_ON = datetime(2026, 8, 17, 9, 0, tzinfo=dt_timezone.utc)


def _office_job(dana, brazos):
    """A ready job that DANA sent to the field (`assigned_by`)."""
    oid, tech = _ready(dana, brazos)
    work_tables.WorkOrder.objects.filter(pk=oid).update(assigned_by_id=dana.user.id)
    return oid, tech


def _field_rows():
    return list(models.OutboundMessage.objects.filter(source_type="field_work").order_by("created_at"))


def _deliver(dana):
    dispatcher.dispatch_cycle(now=datetime.now(dt_timezone.utc), channels=(models.CHANNEL_IN_APP,), actor=dana)


def _land_all(tech, items):
    for item in items:
        pid = item["payload"]["photo_id"]
        photo_links.receive_bytes(tech, pid, TINY_PNG, "image/png")
        photo_links.run_photo_job({"payload": {"link_id": str(WorkPhotoLink.objects.get(photo_id=pid).id)}})


def test_a_close_with_photos_uploading_tells_dana_then_photos_complete_tells_her_accept_is_open(brazos, dana):
    with tenant_ctx(brazos):
        seed_templates.seed_notice_templates(dana, on_date=SEEDED_ON.date())
        oid, tech = _office_job(dana, brazos)
        order_no = work_tables.WorkOrder.objects.get(pk=oid).order_no
        token = _token(tech)
        items = _photo_items(oid, token)
        assert items, "the fixture template asks for no photo — this case would prove nothing"
        sync.sync_batch(tech, oid, {"items": [*items, _close(token)]})

        closed = _field_rows()
        assert len(closed) == 1
        assert closed[0].render_context["event_code"] == "closed"
        assert closed[0].render_context["count"] == len(items)
        assert closed[0].recipient_address == str(dana.user.id)

        _land_all(tech, items)
        rows = _field_rows()
        assert [r.render_context["event_code"] for r in rows] == ["closed", "photos_complete"]

        _deliver(dana)
        bell = in_app.inbox(actor=dana)
        keys = sorted((i.message_key, i.params["order"], i.params["count"]) for i in bell)

    assert keys == sorted([
        ("notifications.fieldWork.closedUploading", order_no, len(items)),
        ("notifications.fieldWork.photosComplete", order_no, 0),
    ])
    # The utility's own copy rendered too, with the job number in it.
    assert all(order_no in i.body for i in bell)


def test_a_close_with_no_photo_outstanding_says_closed_and_nothing_else(brazos, dana):
    with tenant_ctx(brazos):
        seed_templates.seed_notice_templates(dana, on_date=SEEDED_ON.date())
        oid, tech = _office_job(dana, brazos)
        token = _token(tech)
        items = _photo_items(oid, token)
        sync.sync_batch(tech, oid, {"items": items})
        _land_all(tech, items)  # photos in BEFORE the close: not news yet
        assert _field_rows() == []
        sync.sync_batch(tech, oid, {"items": [_close(token)]})
        rows = _field_rows()

    assert [(r.render_context["event_code"], r.render_context["count"]) for r in rows] == [("closed", 0)]


def test_a_replayed_page_tells_nobody_twice(brazos, dana):
    with tenant_ctx(brazos):
        seed_templates.seed_notice_templates(dana, on_date=SEEDED_ON.date())
        oid, tech = _office_job(dana, brazos)
        token = _token(tech)
        page = {"items": [*_photo_items(oid, token), _close(token)]}
        sync.sync_batch(tech, oid, page)
        sync.sync_batch(tech, oid, page)
        rows = _field_rows()

    assert len(rows) == 1


def test_items_the_server_cannot_accept_go_back_to_the_technician_not_to_the_office(brazos, dana):
    """FLIPPED 2026-10-21 — PO, *"back to the technician"* (`BR-WRK-063`
    superseded for field items). Until then two unreadable items were STORED,
    `held_for_review`, and Dana and every System Admin were told *needs
    review*. Now the items are refused to the PHONE, which keeps them; nothing
    is stored for the office to review, so the office is told nothing."""
    with tenant_ctx(brazos):
        seed_templates.seed_notice_templates(dana, on_date=SEEDED_ON.date())
        oid, tech = _office_job(dana, brazos)
        token = _token(tech)
        bad = [
            {"key": f"odd-{n}", "kind": "teleport", "seq": n, "captured_at": "2026-03-15T15:30:00Z",
             "capture_token": token, "location": FIX, "payload": {}}
            for n in (1, 2)
        ]
        out = sync.sync_batch(tech, oid, {"items": bad})
        rows = _field_rows()

    assert out["held_for_review"] == 0 and out["refused"] == 2, out
    assert out["acknowledged"] == []
    assert all(i["detail"]["reason"] == "unknown_item_kind" for i in out["items"])
    assert rows == [], "nothing was stored, so nothing is for the office to review"


def test_a_job_nobody_sent_to_the_field_closes_without_inventing_an_addressee(brazos, dana):
    with tenant_ctx(brazos):
        seed_templates.seed_notice_templates(dana, on_date=SEEDED_ON.date())
        oid, tech = _ready(dana, brazos)
        work_tables.WorkOrder.objects.filter(pk=oid).update(assigned_by_id=None)
        token = _token(tech)
        out = sync.sync_batch(tech, oid, {"items": [*_photo_items(oid, token), _close(token)]})
        rows = _field_rows()
        order = work_tables.WorkOrder.objects.get(pk=oid)

    assert order.state == work_tables.WO_COMPLETED, "the close itself must never depend on the notice"
    assert out["accepted"] >= 1
    assert rows == [], "BR-NOT-021 (e): no initiator and no failure reaches nobody"


def test_an_optional_photo_landing_does_not_say_photos_complete(brazos, dana):
    from apps.work import office_notices

    with tenant_ctx(brazos):
        seed_templates.seed_notice_templates(dana, on_date=SEEDED_ON.date())
        oid, _tech = _office_job(dana, brazos)
        told = office_notices.after_photo_landed(oid, required=False)

    assert told is None
    assert uuid.UUID(str(oid))
