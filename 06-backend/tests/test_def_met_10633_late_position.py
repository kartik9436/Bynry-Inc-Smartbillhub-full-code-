# ── Trace ──────────────────────────────────────────────
# Change:   DEF-MET-10633 (FB-003, the position half — PO report 2026-10-26,
#           reader Sam Curran, RT-001; ruling 2026-10-27, decision log
#           "FB-003: the position is captured automatically, never by a button")
# Rules:    BR-MET-1202 (the phone's position at capture) · CLAUDE.md hard
#           rule 4's spirit (add, never change: a late position is its own row)
#           · hard rule 6 (idempotent on the key) · hard-won law 14
# Tests:    this file (SQLite) · tests/test_def_met_10633_late_position_pg.py
# ───────────────────────────────────────────────────────
"""A position that arrives after the reading was saved — kept as its own fact.

The ruling, verbatim: *"Saved without a position: the first fix within 5
minutes of saving is sent automatically as a SEPARATE fact, 'Position added at
18:35' — never written as if present at save … After 5 minutes nothing is
attached."* Worked case put to the PO: a reading saved 18:32:48 with no fix; a
±10 m fix arrives 18:35 → *"Position added at 18:35 ±10 m"*; a fix first
arriving 18:38 attaches nothing.

RED FIRST (hard-won law 7): at the commit before this lane, `position` is an
unknown kind — every item here is refused `unknown_kind` — a photo's position
is not stored, and `GET /reads/{id}` serves no `field_capture`.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from apps.metering import api as metering_api
from apps.metering import field_positions, field_reads
from apps.metering.field_read_models import FieldRead

from tests.test_cr187_reads_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_cr187_reads_helpers import a_reading, build_route, captured, reader_actor, tenant_ctx
from tests.test_us_ten_helpers import api_call

pytestmark = pytest.mark.django_db

PHOTO_ID = "0b6f7a52-6f8e-4c55-9d7e-3a3c2b1f0633"


@pytest.fixture()
def world(brazos, dana):
    with tenant_ctx(brazos):
        reader = reader_actor(brazos)
        route = build_route(brazos, dana, reader)
    return {"tenant": brazos, "admin": dana, "reader": reader, "route": route}


def _saved_at() -> datetime:
    return datetime.fromisoformat(captured())


def _no_fix_reading(key, w):
    item = a_reading(key, "MTR-0471", "48400", route_id=w.route_id)
    del item["position"]
    return item


def _position(key, for_key, *, after_s, for_kind="reading", route_id, accuracy="10", **extra):
    fix_at = (_saved_at() + timedelta(seconds=after_s)).isoformat()
    item = {
        "key": key,
        "kind": "position",
        "route_id": str(route_id),
        "captured_at": fix_at,
        "for_key": for_key,
        "for_kind": for_kind,
        "position": {"lat": "29.785300", "lng": "-95.824600", "accuracy_m": accuracy, "fix_at": fix_at},
    }
    item.update(extra)
    return item


def _sync(world, *items):
    return field_reads.sync_reads(world["reader"], {"items": list(items)})


def test_a_fix_2_minutes_after_a_save_without_one_is_kept_as_its_own_fact(world):
    w = world["route"]
    with tenant_ctx(world["tenant"]):
        out = _sync(world, _no_fix_reading("sam-read-1", w), _position("sam-pos-1", "sam-read-1", after_s=132, route_id=w.route_id))
        assert [i["result"] for i in out["items"]] == ["accepted", "accepted"], out
        assert out["items"][1]["outcome"] == "recorded"
        reading = FieldRead.objects.get(key="sam-read-1")
        late = FieldRead.objects.get(key="sam-pos-1")
        # Never written as if present at save: the reading's own row has none.
        assert reading.lat is None and reading.accuracy_m is None
        assert late.kind == "position"
        assert late.position_for_id == reading.id
        assert late.lat == Decimal("29.785300") and late.accuracy_m == Decimal("10.00")
        assert late.device_captured_at == _saved_at() + timedelta(seconds=132)
        assert late.meter_read_id is None


def test_the_same_position_resent_is_a_duplicate(world):
    w = world["route"]
    with tenant_ctx(world["tenant"]):
        _sync(world, _no_fix_reading("sam-read-2", w))
        item = _position("sam-pos-2", "sam-read-2", after_s=60, route_id=w.route_id)
        assert _sync(world, item)["items"][0]["result"] == "accepted"
        assert _sync(world, item)["items"][0]["result"] == "duplicate"
        assert FieldRead.objects.filter(kind="position").count() == 1


def test_only_the_first_position_attaches(world):
    """A second late position for the same reading is answered as already
    held — acknowledged, so the phone stops sending it, and not stored."""
    w = world["route"]
    with tenant_ctx(world["tenant"]):
        _sync(world, _no_fix_reading("sam-read-3", w))
        _sync(world, _position("sam-pos-3a", "sam-read-3", after_s=60, route_id=w.route_id))
        out = _sync(world, _position("sam-pos-3b", "sam-read-3", after_s=90, route_id=w.route_id, accuracy="4"))
        assert out["items"][0]["result"] == "duplicate", out
        assert list(FieldRead.objects.filter(kind="position").values_list("key", flat=True)) == ["sam-pos-3a"]


def test_a_fix_after_5_minutes_attaches_nothing(world):
    w = world["route"]
    with tenant_ctx(world["tenant"]):
        _sync(world, _no_fix_reading("sam-read-4", w))
        out = _sync(world, _position("sam-pos-4", "sam-read-4", after_s=5 * 60 + 12, route_id=w.route_id))
        receipt = out["items"][0]
        assert receipt["result"] == "refused" and receipt["reason"] == "position_too_late", receipt
        assert not FieldRead.objects.filter(key="sam-pos-4").exists()
        assert field_positions.LATE_WINDOW == timedelta(minutes=5)


def test_a_fix_from_before_the_save_is_not_a_late_one(world):
    w = world["route"]
    with tenant_ctx(world["tenant"]):
        _sync(world, _no_fix_reading("sam-read-5", w))
        out = _sync(world, _position("sam-pos-5", "sam-read-5", after_s=-30, route_id=w.route_id))
        assert out["items"][0]["reason"] == "position_too_late"


def test_a_position_for_a_key_never_received_goes_back(world):
    w = world["route"]
    with tenant_ctx(world["tenant"]):
        out = _sync(world, _position("sam-pos-6", "nothing-by-this-key", after_s=30, route_id=w.route_id))
        assert out["items"][0]["reason"] == "position_target_unknown"


def test_a_reading_saved_with_a_position_takes_no_late_one(world):
    w = world["route"]
    with tenant_ctx(world["tenant"]):
        _sync(world, a_reading("sam-read-7", "MTR-0471", "48400", route_id=w.route_id))
        out = _sync(world, _position("sam-pos-7", "sam-read-7", after_s=30, route_id=w.route_id))
        assert out["items"][0]["reason"] == "position_already_known"


def test_a_position_with_no_coordinates_goes_back(world):
    w = world["route"]
    with tenant_ctx(world["tenant"]):
        _sync(world, _no_fix_reading("sam-read-8", w))
        item = _position("sam-pos-8", "sam-read-8", after_s=30, route_id=w.route_id)
        del item["position"]["lat"]
        assert _sync(world, item)["items"][0]["reason"] == "position_missing"


def _photo(key, *, route_id, position=None):
    item = {
        "key": key,
        "kind": "photo",
        "route_id": str(route_id),
        "photo_id": PHOTO_ID,
        "sha256": hashlib.sha256(b"x").hexdigest(),
        "captured_at": captured(),
    }
    if position is not None:
        item["position"] = position
    return item


def test_a_photo_declaration_keeps_its_shutter_position(world):
    w = world["route"]
    with tenant_ctx(world["tenant"]):
        shutter = {"lat": "29.785111", "lng": "-95.824511", "accuracy_m": "7", "fix_at": captured()}
        assert _sync(world, _photo("sam-photo-1", route_id=w.route_id, position=shutter))["items"][0]["result"] == "accepted"
        row = FieldRead.objects.get(key="sam-photo-1")
        assert row.lat == Decimal("29.785111") and row.accuracy_m == Decimal("7.00")


def test_a_photo_without_a_fix_gets_the_late_position_too(world):
    w = world["route"]
    with tenant_ctx(world["tenant"]):
        _sync(world, _photo("sam-photo-2", route_id=w.route_id))
        out = _sync(
            world,
            _position("sam-pos-9", "sam-photo-2", after_s=45, for_kind="photo", route_id=w.route_id, photo_id=PHOTO_ID),
        )
        assert out["items"][0]["result"] == "accepted", out
        assert FieldRead.objects.get(key="sam-pos-9").position_for == FieldRead.objects.get(key="sam-photo-2")


def test_the_office_reading_shows_the_late_position_as_added_at(world):
    w = world["route"]
    with tenant_ctx(world["tenant"]):
        saved = _saved_at()
        out = _sync(world, _no_fix_reading("sam-read-10", w), _position("sam-pos-10", "sam-read-10", after_s=132, route_id=w.route_id))
        read_id = out["items"][0]["meter_read_id"]
        response = api_call(
            metering_api.read_detail, "get", user=world["admin"].user, role="billing_clerk", tenant=world["tenant"], read_id=read_id
        )
    assert response.status_code == 200, response.data
    capture = response.data["field_capture"]
    assert datetime.fromisoformat(capture["captured_at"]) == saved
    assert capture["position"] == {
        "lat": "29.785300",
        "lng": "-95.824600",
        "accuracy_m": "10.00",
        "at": capture["position"]["at"],
        "added": True,
    }
    # *added at* the FIX's own time, never the save's.
    assert datetime.fromisoformat(capture["position"]["at"]) == saved + timedelta(seconds=132)
    assert capture["photos"] == []


def test_the_office_reading_shows_a_position_taken_at_save(world):
    w = world["route"]
    with tenant_ctx(world["tenant"]):
        out = _sync(world, a_reading("sam-read-11", "MTR-0471", "48400", route_id=w.route_id))
        capture = field_positions.capture_for_meter_read(out["items"][0]["meter_read_id"])
    assert capture["position"]["added"] is False
    assert capture["position"]["lat"] == "29.785100" and capture["position"]["accuracy_m"] == "4.00"


def test_a_read_that_did_not_come_from_the_field_has_no_capture(world):
    with tenant_ctx(world["tenant"]):
        assert field_positions.capture_for_meter_read("00000000-0000-0000-0000-000000000000") is None
