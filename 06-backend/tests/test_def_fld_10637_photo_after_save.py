# ── Trace ──────────────────────────────────────────────
# Change:   DEF-FLD-10637 (FB-019, PO report 2026-10-28 — technician Jeremy,
#           Android 2.606.0, route reads; ruling "start FB-019 … go with
#           recommendation" the same day)
# Rules:    R123 (a photograph is declared with the data) · CLAUDE.md hard
#           rules 1 (tenant), 4's spirit (the reading is never touched), 6
#           (idempotent on the key) · hard-won law 14
# Tests:    this file (SQLite) · tests/test_def_fld_10637_photo_after_save_pg.py
# ───────────────────────────────────────────────────────
"""A photo added to a route reading AFTER it was saved names that reading.

RED FIRST (hard-won law 7): before this lane the reads door ignored
`reading_key` — the photo was accepted and linked to nothing, a key naming a
reading that did not exist or belonged to another reader was accepted all the
same, and the office reading listed only the photos saved with it.
"""

from __future__ import annotations

import hashlib

import pytest

from apps.metering import api as metering_api
from apps.metering import field_positions, field_reads
from apps.metering import models as metering_models
from apps.metering import services as metering_services
from apps.metering.field_read_models import FieldRead, FieldReadPhoto

from tests.test_cr187_reads_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_cr187_reads_helpers import a_reading, build_route, captured, reader_actor, tenant_ctx
from tests.test_us_ten_helpers import api_call

pytestmark = pytest.mark.django_db

SAVED_WITH = "1f0e3b1a-0000-4c55-9d7e-3a3c2b1f0001"
ADDED_1 = "1f0e3b1a-0000-4c55-9d7e-3a3c2b1f0002"
ADDED_2 = "1f0e3b1a-0000-4c55-9d7e-3a3c2b1f0003"


@pytest.fixture()
def world(brazos, dana):
    with tenant_ctx(brazos):
        reader = reader_actor(brazos)
        route = build_route(brazos, dana, reader)
    return {"tenant": brazos, "admin": dana, "reader": reader, "route": route}


def _photo(key, photo_id, *, route_id, reading_key=None, position=None):
    item = {
        "key": key,
        "kind": "photo",
        "route_id": str(route_id),
        "photo_id": photo_id,
        "sha256": hashlib.sha256(photo_id.encode()).hexdigest(),
        "captured_at": captured(),
    }
    if reading_key is not None:
        item["reading_key"] = reading_key
    if position is not None:
        item["position"] = position
    return item


def _sync(actor, *items):
    return field_reads.sync_reads(actor, {"items": list(items)})


def test_a_photo_added_after_saving_is_linked_to_its_reading(world):
    w = world["route"]
    with tenant_ctx(world["tenant"]):
        _sync(world["reader"], a_reading("jer-read-1", "MTR-0471", "48400", route_id=w.route_id))
        out = _sync(world["reader"], _photo("jer-photo-1", ADDED_1, route_id=w.route_id, reading_key="jer-read-1"))
        receipt = out["items"][0]
        assert receipt["result"] == "accepted", receipt
        assert receipt["photo_id"] == ADDED_1 and receipt["upload_url"].endswith(f"/reads/photos/{ADDED_1}")
        reading = FieldRead.objects.get(key="jer-read-1")
        photo = FieldRead.objects.get(key="jer-photo-1")
        assert photo.photo_for_id == reading.id
        assert photo.premises_id == reading.premises_id and photo.asset_id == reading.asset_id
        # The reading itself is never touched: its own photos are as sent.
        assert reading.photo_ids == []
        assert FieldReadPhoto.objects.filter(photo_id=ADDED_1).exists()


def test_the_reading_and_its_added_photo_in_one_batch(world):
    """The phone sends them in capture order, reading first."""
    w = world["route"]
    with tenant_ctx(world["tenant"]):
        out = _sync(
            world["reader"],
            a_reading("jer-read-2", "MTR-0471", "48400", route_id=w.route_id),
            _photo("jer-photo-2", ADDED_1, route_id=w.route_id, reading_key="jer-read-2"),
        )
        assert [i["result"] for i in out["items"]] == ["accepted", "accepted"], out
        assert FieldRead.objects.get(key="jer-photo-2").photo_for == FieldRead.objects.get(key="jer-read-2")


def test_a_photo_naming_a_reading_never_received_goes_back_and_stores_nothing(world):
    w = world["route"]
    with tenant_ctx(world["tenant"]):
        out = _sync(world["reader"], _photo("jer-photo-3", ADDED_1, route_id=w.route_id, reading_key="no-such-reading"))
        receipt = out["items"][0]
        assert receipt["result"] == "refused" and receipt["reason"] == "photo_reading_unknown", receipt
        assert receipt["message_key"] == "work.mobile.reads.photo_reading_unknown"
        assert not FieldRead.objects.filter(key="jer-photo-3").exists()
        assert not FieldReadPhoto.objects.filter(photo_id=ADDED_1).exists()


def test_a_photo_naming_another_readers_reading_goes_back(world):
    w = world["route"]
    with tenant_ctx(world["tenant"]):
        other = reader_actor(world["tenant"], email="sam.curran@brazosbendutilities.test")
        _sync(world["reader"], a_reading("jer-read-4", "MTR-0471", "48400", route_id=w.route_id))
        out = _sync(other, _photo("sam-photo-4", ADDED_1, route_id=w.route_id, reading_key="jer-read-4"))
        receipt = out["items"][0]
        assert receipt["result"] == "refused" and receipt["reason"] == "photo_reading_foreign", receipt
        assert not FieldRead.objects.filter(key="sam-photo-4").exists()


def test_a_photo_naming_a_reading_on_another_route_goes_back(world):
    w = world["route"]
    with tenant_ctx(world["tenant"]):
        cycle = metering_services.create_cycle(world["admin"], {"code": "CY-WLK-09", "name": "Cycle 9", "frequency": "monthly"})
        second = metering_services.create_route(
            world["admin"],
            {"code": "WLK-09", "name": "Off Maple", "service_code": "electric", "premises_ids": [w.off_premises], "cycle_id": cycle["id"]},
        )
        metering_models.Route.objects.filter(pk=second["id"]).update(assigned_to_id=world["reader"].id)
        _sync(world["reader"], a_reading("jer-read-5", "MTR-0471", "48400", route_id=w.route_id))
        out = _sync(world["reader"], _photo("jer-photo-5", ADDED_1, route_id=second["id"], reading_key="jer-read-5"))
        assert out["items"][0]["reason"] == "photo_reading_foreign", out


def test_a_key_that_names_a_photo_rather_than_a_reading_goes_back(world):
    w = world["route"]
    with tenant_ctx(world["tenant"]):
        _sync(world["reader"], _photo("jer-photo-6a", ADDED_1, route_id=w.route_id))
        out = _sync(world["reader"], _photo("jer-photo-6b", ADDED_2, route_id=w.route_id, reading_key="jer-photo-6a"))
        assert out["items"][0]["reason"] == "photo_reading_unknown", out


def test_the_same_added_photo_resent_is_a_duplicate(world):
    w = world["route"]
    with tenant_ctx(world["tenant"]):
        _sync(world["reader"], a_reading("jer-read-7", "MTR-0471", "48400", route_id=w.route_id))
        item = _photo("jer-photo-7", ADDED_1, route_id=w.route_id, reading_key="jer-read-7")
        assert _sync(world["reader"], item)["items"][0]["result"] == "accepted"
        again = _sync(world["reader"], item)["items"][0]
        assert again["result"] == "duplicate"
        assert FieldRead.objects.filter(photo_for__key="jer-read-7").count() == 1


def test_a_photo_with_no_reading_key_is_as_before(world):
    """An older build's declaration (and one saved WITH its reading) names no
    reading: accepted, linked to nothing — exactly as before this lane."""
    w = world["route"]
    with tenant_ctx(world["tenant"]):
        assert _sync(world["reader"], _photo("jer-photo-8", ADDED_1, route_id=w.route_id))["items"][0]["result"] == "accepted"
        assert FieldRead.objects.get(key="jer-photo-8").photo_for_id is None


def test_the_office_reading_lists_photos_added_after_saving(world):
    """Worked case: saved with 1 photo, 2 added after → 3 listed, the last 2
    marked added after saving, each with its own position."""
    w = world["route"]
    with tenant_ctx(world["tenant"]):
        shutter = {"lat": "29.785222", "lng": "-95.824522", "accuracy_m": "6", "fix_at": captured()}
        out = _sync(
            world["reader"],
            a_reading("jer-read-9", "MTR-0471", "48400", route_id=w.route_id, photos=[SAVED_WITH]),
            _photo("jer-photo-9a", SAVED_WITH, route_id=w.route_id),
        )
        read_id = out["items"][0]["meter_read_id"]
        _sync(
            world["reader"],
            _photo("jer-photo-9b", ADDED_1, route_id=w.route_id, reading_key="jer-read-9", position=shutter),
            _photo("jer-photo-9c", ADDED_2, route_id=w.route_id, reading_key="jer-read-9"),
        )
        capture = field_positions.capture_for_meter_read(read_id)
        response = api_call(
            metering_api.read_detail, "get", user=world["admin"].user, role="billing_clerk", tenant=world["tenant"], read_id=read_id
        )
    assert [(p["photo_id"], p["added_after_save"]) for p in capture["photos"]] == [
        (SAVED_WITH, False),
        (ADDED_1, True),
        (ADDED_2, True),
    ]
    assert capture["photos"][1]["position"]["lat"] == "29.785222"
    assert capture["photos"][2]["position"] is None
    assert response.status_code == 200, response.data
    assert [p["added_after_save"] for p in response.data["field_capture"]["photos"]] == [False, True, True]
