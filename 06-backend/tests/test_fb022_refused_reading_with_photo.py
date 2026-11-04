# ── Trace ──────────────────────────────────────────────
# Change:   FB-022 (PO report 2026-10-31; DevOps traceback 29 Oct 10:34:58 UTC,
#           City of Houston, POST work/mobile/reads/sync → 500 ProtectedError on
#           `FieldRead.photo_for`) — DEF-MET-10796, DEF-MET-10797
# Rules:    BR-WRK-063 as superseded 2026-10-21 (a reading the pipeline will
#           not post is refused back to the reader, nothing stored) · PO
#           2026-10-31 decision log "FB-022: a lower reading is warned, never
#           refused; several readings in one cycle are all accepted" and
#           "Which reading bills … (PO, R1 A · R2 A)" · hard rules 1, 6 ·
#           hard-won law 14
# Tests:    this file (SQLite) · tests/test_fb022_refused_reading_with_photo_pg.py
# ───────────────────────────────────────────────────────
"""A reading the pipeline turns away, sent with a photo that names it — and
a reading LOWER than the last, which is no longer turned away at all.

RED FIRST (hard-won law 7), proved before the fix on SQLite and PostgreSQL:
`sync_reads` deleted the refused reading's row while the photo declared in the
SAME batch (FB-019, `reading_key`) pointed at it through the PROTECT foreign
key `photo_for` (metering/0082) — `ProtectedError` outside any savepoint, the
whole request 500, the phone re-sending the identical batch for ever (*"The
server had a problem. Trying again."*). Houston's reading was turned away for
`negative_usage` (a figure below the meter's last), the commonest refusal.

Now: (1) a reading refused for ANY reason takes its photos and late
positions with it, each refused by name, nothing stored, replay the same;
(2) a reading lower than the last is ACCEPTED, stored with its
`negative_usage` flag and no consumption, and does not bill until a clerk
corrects it; (3) several readings of one meter in one cycle are all stored and
the latest bills.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest

from apps.assets import models as assets_models
from apps.metering import field_reads
from apps.metering import models as metering_models
from apps.metering import selectors as metering_selectors
from apps.metering import services as metering_services
from apps.metering.field_read_models import FieldRead, FieldReadPhoto
from core import errors

from tests.test_cr187_reads_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_cr187_reads_helpers import (
    a_reading,
    build_route,
    captured,
    commit_read,
    reader_actor,
    tenant_ctx,
    today,
)
from tests.test_def_fld_10637_photo_after_save import ADDED_1, ADDED_2, _photo
from tests.test_def_met_10633_late_position import _no_fix_reading, _position

pytestmark = pytest.mark.django_db


@pytest.fixture()
def world(brazos, dana):
    with tenant_ctx(brazos):
        reader = reader_actor(brazos)
        route = build_route(brazos, dana, reader)
    return {"tenant": brazos, "admin": dana, "reader": reader, "route": route}


@pytest.fixture()
def new_world(brazos, dana):
    """The route with NO history: every meter is brand new, never read."""
    with tenant_ctx(brazos):
        reader = reader_actor(brazos)
        route = build_route(brazos, dana, reader, history=False)
    return {"tenant": brazos, "admin": dana, "reader": reader, "route": route}


def _sync(world, *items):
    return field_reads.sync_reads(world["reader"], {"items": list(items)})


@pytest.fixture()
def pipeline_refuses(monkeypatch):
    """The pipeline refuses the batch (`pipeline_refused`) — the refusal that
    still exists after FB-022, standing in for any reason the engine has."""

    def refuse(*_a, **_k):
        raise errors.BizError(errors.BIZ_IMMUTABLE, message_key="metering.read_batch.already_posted")

    monkeypatch.setattr(metering_services, "validate_read_batch", SimpleNamespace(__wrapped__=refuse))


# ══ (1) a refused reading takes what hangs off it — never a 500 ══════════════


def _batch(w):
    return [
        a_reading("hou-read-1", "MTR-0471", "48400", route_id=w.route_id),
        _photo("hou-photo-1", ADDED_1, route_id=w.route_id, reading_key="hou-read-1"),
    ]


def test_a_refused_reading_and_its_photo_answer_200_and_store_nothing(world, pipeline_refuses):
    w = world["route"]
    with tenant_ctx(world["tenant"]):
        out = _sync(world, *_batch(w))
        assert [(i["key"], i["result"], i.get("reason")) for i in out["items"]] == [
            ("hou-read-1", "refused", field_reads.HELD_PIPELINE_REFUSED),
            ("hou-photo-1", "refused", field_reads.HELD_PHOTO_READING_REFUSED),
        ], out
        photo = out["items"][1]
        assert photo["message_key"] == "work.mobile.reads.photo_reading_refused"
        assert photo["detail"]["params"] == {
            "reading_key": "hou-read-1",
            "reading_reason": field_reads.HELD_PIPELINE_REFUSED,
        }
        assert not FieldRead.objects.filter(key__in=["hou-read-1", "hou-photo-1"]).exists()
        assert not FieldReadPhoto.objects.filter(photo_id=ADDED_1).exists()


def test_the_replay_gets_the_same_answer(world, pipeline_refuses):
    w = world["route"]
    with tenant_ctx(world["tenant"]):
        first = _sync(world, *_batch(w))
        again = _sync(world, *_batch(w))
        assert [(i["result"], i.get("reason")) for i in again["items"]] == [
            (i["result"], i.get("reason")) for i in first["items"]
        ]
        assert not FieldRead.objects.filter(key__in=["hou-read-1", "hou-photo-1"]).exists()


def test_two_photos_and_a_late_position_on_one_refused_reading(world, pipeline_refuses):
    w = world["route"]
    with tenant_ctx(world["tenant"]):
        out = _sync(
            world,
            _no_fix_reading("hou-read-3", w),
            _photo("hou-photo-3a", ADDED_1, route_id=w.route_id, reading_key="hou-read-3"),
            _photo("hou-photo-3b", ADDED_2, route_id=w.route_id, reading_key="hou-read-3"),
            _position("hou-pos-3", "hou-read-3", after_s=60, route_id=w.route_id),
        )
        assert [(i["result"], i.get("reason")) for i in out["items"]] == [
            ("refused", field_reads.HELD_PIPELINE_REFUSED),
            ("refused", field_reads.HELD_PHOTO_READING_REFUSED),
            ("refused", field_reads.HELD_PHOTO_READING_REFUSED),
            ("refused", field_reads.HELD_POSITION_READING_REFUSED),
        ], out
        assert not FieldRead.objects.filter(key__startswith="hou-").exists()
        assert not FieldReadPhoto.objects.filter(photo_id__in=[ADDED_1, ADDED_2]).exists()


# ══ (2) a reading lower than the last is accepted, flagged, and not billed ═══


def _unit_of(meter_id):
    return assets_models.Asset.objects.get(pk=meter_id).service_point.unit_id


def _billing_row(meter_id):
    rows = metering_selectors.billing_reads_for_unit(
        _unit_of(meter_id),
        period_start=today() - timedelta(days=20),
        period_end=today(),
        service_codes=["electric"],
    )
    assert len(rows) == 1, rows
    return rows[0]


def test_a_lower_reading_and_its_photo_are_accepted_and_flagged(world):
    """MTR-0471's last committed dial is 47,700; 41,000 is below it."""
    w = world["route"]
    with tenant_ctx(world["tenant"]):
        out = _sync(
            world,
            a_reading("low-read-1", "MTR-0471", "41000", route_id=w.route_id),
            _photo("low-photo-1", ADDED_1, route_id=w.route_id, reading_key="low-read-1"),
        )
        assert [i["result"] for i in out["items"]] == ["accepted", "accepted"], out
        read = metering_models.MeterRead.objects.get(id=out["items"][0]["meter_read_id"])
        assert read.current_value == Decimal("41000")
        assert read.status == "negative_usage"
        assert read.consumption is None  # BR-MET-052: never invented
        assert FieldRead.objects.get(key="low-photo-1").photo_for.key == "low-read-1"


def test_houston_new_meter_install_read_4812_then_4790_with_photo(new_world):
    """The worked figure shown to the PO: installed at 4,812, read 4,790.
    Stored with the warning, the photo kept — and NOT billed until a clerk
    corrects it: billing meets the meter as having no usable reading (R1)."""
    w = new_world["route"]
    meter = w.meters["MTR-0472"]["id"]
    with tenant_ctx(new_world["tenant"]):
        commit_read(None, meter, day=(today() - timedelta(days=40)).isoformat(), value="4812")
        out = _sync(
            new_world,
            a_reading("hou-new-1", "MTR-0472", "4790", route_id=w.route_id),
            _photo("hou-new-photo-1", ADDED_1, route_id=w.route_id, reading_key="hou-new-1"),
        )
        assert [i["result"] for i in out["items"]] == ["accepted", "accepted"], out
        read = metering_models.MeterRead.objects.get(id=out["items"][0]["meter_read_id"])
        assert (read.current_value, read.status, read.consumption) == (Decimal("4790"), "negative_usage", None)
        row = _billing_row(meter)
        # R1: the period holds no approved reading — the missing-reading case.
        assert (row["consumption"], row["absent_reason"], row["read_id"]) == (None, "no_read", None), row


def test_the_next_reading_is_measured_from_4812_not_from_the_flagged_4790(new_world):
    """4,812 → 4,790 (awaiting a clerk) → 4,900: 88 kWh, never 110."""
    w = new_world["route"]
    meter = w.meters["MTR-0472"]["id"]
    with tenant_ctx(new_world["tenant"]):
        commit_read(None, meter, day=(today() - timedelta(days=40)).isoformat(), value="4812")
        _sync(new_world, a_reading("nx-1", "MTR-0472", "4790", route_id=w.route_id, captured_at=captured(-10)))
        out = _sync(new_world, a_reading("nx-2", "MTR-0472", "4900", route_id=w.route_id, captured_at=captured(-2)))
        read = metering_models.MeterRead.objects.get(id=out["items"][0]["meter_read_id"])
        # Its status may carry an unrelated warning (the fixture's 40-day gap);
        # what matters is the baseline and the usage.
        assert (read.prior_value, read.consumption) == (Decimal("4812"), Decimal("88")), read.__dict__
        assert read.status != "negative_usage"
        row = _billing_row(meter)
        assert (row["current_value"], row["consumption"]) == (Decimal("4900"), Decimal("88")), row


def test_a_new_meters_first_reading_and_its_photo_post(new_world):
    w = new_world["route"]
    with tenant_ctx(new_world["tenant"]):
        out = _sync(
            new_world,
            a_reading("new-read-1", "MTR-0471", "0", route_id=w.route_id),
            _photo("new-photo-1", ADDED_1, route_id=w.route_id, reading_key="new-read-1"),
        )
        assert [i["result"] for i in out["items"]] == ["accepted", "accepted"], out


# ══ (3) several readings in one cycle: all stored, the latest bills ══════════


def test_three_readings_in_one_cycle_are_all_stored_and_5155_bills(new_world):
    """The PO's R2 figure: 5,010, 5,140 and 5,155 in one cycle → 5,155 bills."""
    w = new_world["route"]
    meter = w.meters["MTR-0473"]["id"]
    with tenant_ctx(new_world["tenant"]):
        commit_read(None, meter, day=(today() - timedelta(days=40)).isoformat(), value="4812")
        for key, value, offset in (("cyc-1", "5010", -15), ("cyc-2", "5140", -8), ("cyc-3", "5155", -2)):
            out = _sync(new_world, a_reading(key, "MTR-0473", value, route_id=w.route_id, captured_at=captured(offset)))
            assert out["items"][0]["result"] == "accepted", out
        stored = sorted(
            metering_models.MeterRead.objects.filter(asset_id=meter, superseded_by_id__isnull=True).values_list(
                "current_value", flat=True
            )
        )
        assert stored == [Decimal("4812"), Decimal("5010"), Decimal("5140"), Decimal("5155")]
        row = _billing_row(meter)
        assert row["current_value"] == Decimal("5155"), row


def test_a_lower_latest_reading_in_the_cycle_is_skipped_and_5140_bills(new_world):
    """R2 with R1: 5,010 and 5,140 approved, then 4,790 awaiting a clerk →
    the latest APPROVED reading, 5,140, bills."""
    w = new_world["route"]
    meter = w.meters["MTR-0474"]["id"]
    with tenant_ctx(new_world["tenant"]):
        commit_read(None, meter, day=(today() - timedelta(days=40)).isoformat(), value="4812")
        for key, value, offset in (("sk-1", "5010", -15), ("sk-2", "5140", -8), ("sk-3", "4790", -2)):
            out = _sync(new_world, a_reading(key, "MTR-0474", value, route_id=w.route_id, captured_at=captured(offset)))
            assert out["items"][0]["result"] == "accepted", out
        row = _billing_row(meter)
        assert row["current_value"] == Decimal("5140"), row
