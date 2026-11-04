# ── Trace ──────────────────────────────────────────────
# Change:   FB-030 (DEF-FLD-10806) — a technician's history is the last 14
#           days, kept on the phone (PO 2026-10-31, decision log, and its
#           "photos 3 days" follow-up)
# Rules:    BR-FLD-00061 (R61, SUPERSEDED in part 2026-10-31) · BR-FLD-00062 ·
#           R120 (never how fast) · HR-1 (another's work is a 404) · hard rule 1
#           · hard rule 3 · NFR-3 / NFR-5
# Tests:    this file (SQLite) · tests/test_fb030_history_pg.py (PostgreSQL 16,
#           a NOSUPERUSER NOBYPASSRLS role)
# ───────────────────────────────────────────────────────
"""What a technician can look back at, and what they cannot.

RED FIRST (hard-won law 7): at 7af7fbd1f every case below failed — the card
carried no `completed_at`/`outcome`/`accepted_at`, the first sync sent open
jobs only, the bundle and the photo doors admitted the CURRENT assignee only
(a helper's closed job was a 404), and there was no history or photo-content
door for a route.
"""

from __future__ import annotations

import hashlib
from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.urls import resolve
from django.utils import timezone as dj_tz

from apps.metering import field_history, field_read_photos, field_reads
from apps.metering.field_read_models import FieldRead, FieldRouteTurnIn
from apps.work import connection_models as work_tables
from apps.work import mobile
from apps.work.evidence_models import WorkPhotoLink
from apps.work.field_order_models import WorkOrderLabour
from core import errors

from tests.test_cr187_reads_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana
from tests.test_cr187_reads_helpers import a_reading, build_route, reader_actor
from tests.test_cr187_route_photos import TINY_PNG, a_photo
from tests.test_cr187_sync_feed import _as, _assign, _drain, _raise, _seed, _technician, _upserted
from tests.test_us_ten_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

#: Keys that would carry money or speed into history (decision log (5)). A
#: figure of either kind under any of these names, anywhere in a payload, fails.
FORBIDDEN_KEYS = {
    "balance", "amount", "cost", "price", "total", "currency", "rate", "rate_snapshot",
    "labour_rate_snapshot", "minutes_on_site", "labour_minutes", "travel_minutes", "per_hour",
}


def _keys(value, out=None):
    out = set() if out is None else out
    if isinstance(value, dict):
        for k, v in value.items():
            out.add(k)
            _keys(v, out)
    elif isinstance(value, list):
        for v in value:
            _keys(v, out)
    return out


def _close(oid, *, days_ago, outcome="passed", field_data=None):
    """A close done somewhere other than this phone, `days_ago` days back."""
    at = dj_tz.now() - timedelta(days=days_ago)
    work_tables.WorkOrder.objects.filter(pk=oid).update(
        state=work_tables.WO_COMPLETED,
        dispatch_state="complete",
        outcome=outcome,
        completed_at=at,
        field_data=field_data or {},
        updated_at=at,
    )


@pytest.fixture()
def crew(brazos, dana):
    with tenant_ctx(brazos):
        _seed()
        ortiz = _technician(brazos, "d-ortiz@brazos.test", "D. Ortiz")
        chen = _technician(brazos, "m-chen@brazos.test", "M. Chen")
        patel = _technician(brazos, "r-patel@brazos.test", "R. Patel")
    return SimpleNamespace(tenant=brazos, dana=dana, ortiz=ortiz, chen=chen, patel=patel)


# ── 1 · the card ─────────────────────────────────────────────────────────────
def test_a_job_closed_on_the_web_arrives_in_the_delta_with_its_outcome_and_time(crew):
    from apps.metering import connections as w6

    with tenant_ctx(crew.tenant):
        oid = _raise(crew.dana, "221 Oak Ave")
        _assign(crew.dana, oid, crew.ortiz)
        _, cursor, _ = _drain(_as(crew.ortiz))
        # Closed through the server's own door, not by this phone.
        w6.submit_field_result(_as(crew.ortiz), oid, outcome="partially_done", field_data={})
        delta, _, _ = _drain(_as(crew.ortiz), cursor)
    card = next(c["job"] for c in delta if c["change"] == "upsert" and c["order_id"] == str(oid))
    assert card["outcome"] == "partially_done"
    assert card["completed_at"]
    assert "accepted_at" in card and card["accepted_at"] is None


# ── 2 · the refill ──────────────────────────────────────────────────────────
def test_a_first_sync_refills_14_days_of_closed_jobs_and_not_day_15(crew):
    with tenant_ctx(crew.tenant):
        open_job = _raise(crew.dana, "1 Open St")
        day13 = _raise(crew.dana, "13 Kept St")
        day15 = _raise(crew.dana, "15 Gone St")
        for oid in (open_job, day13, day15):
            _assign(crew.dana, oid, crew.ortiz)
        _close(day13, days_ago=13)
        _close(day15, days_ago=15)
        first, _, _ = _drain(_as(crew.ortiz))
    got = _upserted(first)
    assert {str(open_job), str(day13)} <= got
    assert str(day15) not in got
    kept = next(c["job"] for c in first if c["change"] == "upsert" and c["order_id"] == str(day13))
    assert kept["outcome"] == "passed" and kept["completed_at"]


def test_a_helper_with_crew_time_is_refilled_and_reads_the_record_and_nobody_else_does(crew):
    with tenant_ctx(crew.tenant):
        oid = _raise(crew.dana, "221 Oak Ave")
        _assign(crew.dana, oid, crew.ortiz)
        WorkOrderLabour.objects.create(tenant_id=crew.tenant.id, work_order_id=oid, technician=crew.chen)
        _close(oid, days_ago=2, field_data={"problem_found": "Seized valve", "what_i_did": "Replaced it"})
        chen_feed, _, _ = _drain(_as(crew.chen))
        patel_feed, _, _ = _drain(_as(crew.patel))
        record = mobile.bundle(_as(crew.chen), oid)["record"]
        with pytest.raises(errors.NotFoundError):
            mobile.bundle(_as(crew.patel), oid)
        # A helper's history READ never becomes a write door.
        with pytest.raises(errors.NotFoundError):
            mobile._own_job_or_404(_as(crew.chen), oid)
    assert str(oid) in _upserted(chen_feed)
    assert str(oid) not in _upserted(patel_feed)
    assert record["problem"] == "Seized valve" and record["done"] == "Replaced it"
    assert record["outcome"] == "passed"


def test_the_helpers_record_closes_at_day_14_too(crew):
    with tenant_ctx(crew.tenant):
        oid = _raise(crew.dana, "221 Oak Ave")
        _assign(crew.dana, oid, crew.ortiz)
        WorkOrderLabour.objects.create(tenant_id=crew.tenant.id, work_order_id=oid, technician=crew.chen)
        _close(oid, days_ago=15)
        with pytest.raises(errors.NotFoundError):
            mobile.bundle(_as(crew.chen), oid)


# ── 3 · photos ──────────────────────────────────────────────────────────────
def _photo_link(tenant, oid, photo_id, data=TINY_PNG):
    return WorkPhotoLink.objects.create(
        tenant_id=tenant.id,
        work_order_id=oid,
        photo_id=photo_id,
        sha256=hashlib.sha256(data).hexdigest(),
        state=WorkPhotoLink.STATE_STAGED,
        staged=data,
        content_type="image/png",
    )


def test_a_job_photo_loads_for_its_own_technician_and_is_a_404_for_another(crew):
    photo_id = "0b6f7a52-6f8e-4c55-9d7e-3a3c2b1f3001"
    with tenant_ctx(crew.tenant):
        oid = _raise(crew.dana, "221 Oak Ave")
        _assign(crew.dana, oid, crew.ortiz)
        _photo_link(crew.tenant, oid, photo_id)
        _close(oid, days_ago=5)
        data, content_type = mobile.photo_content(_as(crew.ortiz), photo_id)
        with pytest.raises(errors.NotFoundError):
            mobile.photo_content(_as(crew.patel), photo_id)
        listed = mobile.bundle(_as(crew.ortiz), oid)["record"]["photos"]
    assert data == TINY_PNG and content_type == "image/png"
    assert [p["photo_id"] for p in listed] == [photo_id]
    from apps.work import api as work_api

    assert resolve(f"/api/brazos/work/mobile/photos/{photo_id}/content").func is work_api.mobile_photo_content


def test_another_tenant_sees_none_of_it(crew, lonestar):
    photo_id = "0b6f7a52-6f8e-4c55-9d7e-3a3c2b1f3002"
    with tenant_ctx(crew.tenant):
        oid = _raise(crew.dana, "221 Oak Ave")
        _assign(crew.dana, oid, crew.ortiz)
        _photo_link(crew.tenant, oid, photo_id)
        _close(oid, days_ago=1)
    with tenant_ctx(lonestar):
        stranger = _technician(lonestar, "x@lonestar.test", "X")
        feed, _, _ = _drain(_as(stranger))
        with pytest.raises(errors.NotFoundError):
            mobile.photo_content(_as(stranger), photo_id)
        with pytest.raises(errors.NotFoundError):
            mobile.bundle(_as(stranger), oid)
    assert feed == []


# ── 4 · no money, no speed ──────────────────────────────────────────────────
def test_no_money_or_speed_key_in_the_card_the_record_or_the_reads_history(crew, brazos, dana):
    with tenant_ctx(crew.tenant):
        oid = _raise(crew.dana, "221 Oak Ave")
        _assign(crew.dana, oid, crew.ortiz)
        _close(oid, days_ago=1, field_data={"problem_found": "p", "what_i_did": "d"})
        first, _, _ = _drain(_as(crew.ortiz))
        record = mobile.bundle(_as(crew.ortiz), oid)["record"]
        ray = reader_actor(brazos)
        w = build_route(brazos, dana, ray, history=False)
        field_reads.sync_reads(ray, {"items": [a_reading("h-1", "MTR-0471", "48400", route_id=w.route_id)]})
        field_reads.turn_in(ray, w.route_id, {"key": "ti-1"})
        history = field_history.reads_history(ray)
    keys = _keys([c["job"] for c in first if c["change"] == "upsert"]) | _keys(record) | _keys(history)
    assert not keys & FORBIDDEN_KEYS, keys & FORBIDDEN_KEYS


# ── 5 · route reads: the refill, the 404s, the window ───────────────────────
@pytest.fixture()
def route_world(brazos, dana):
    with tenant_ctx(brazos):
        ray = reader_actor(brazos)
        marco = reader_actor(brazos, email="marco.chen@brazosbendutilities.test")
        w = build_route(brazos, dana, ray, history=False)
    return SimpleNamespace(tenant=brazos, ray=ray, marco=marco, w=w)


def test_the_readers_turned_in_reads_of_14_days_refill_with_their_units_and_not_day_15(route_world):
    rw = route_world
    with tenant_ctx(rw.tenant):
        field_reads.sync_reads(rw.ray, {"items": [
            a_reading("k-13", "MTR-0471", "48400", route_id=rw.w.route_id),
            a_reading("k-15", "MTR-0472", "48390", route_id=rw.w.route_id),
        ]})
        field_reads.turn_in(rw.ray, rw.w.route_id, {"key": "turn-1"})
        FieldRead.objects.filter(key="k-15").update(received_at=dj_tz.now() - timedelta(days=15))
        mine = field_history.reads_history(rw.ray)
        theirs = field_history.reads_history(rw.marco)
    assert [r["key"] for r in mine["results"]] == ["k-13"]
    row = mine["results"][0]
    assert row["value"] == "48400.000000" and row["unit"] == "kWh"
    assert row["meter_no"] == "MTR-0471" and row["address"] == "1318 Maple St"
    assert row["route"]["code"] == "WLK-07" and row["route"]["turned_in_at"]
    assert theirs["count"] == 0


def test_reads_not_turned_in_are_not_history(route_world):
    rw = route_world
    with tenant_ctx(rw.tenant):
        field_reads.sync_reads(rw.ray, {"items": [a_reading("k-open", "MTR-0471", "48400", route_id=rw.w.route_id)]})
        assert field_history.reads_history(rw.ray)["count"] == 0
        # A turn-in older than the window does not make it history either.
        field_reads.turn_in(rw.ray, rw.w.route_id, {"key": "turn-old"})
        FieldRouteTurnIn.objects.filter(key="turn-old").update(received_at=dj_tz.now() - timedelta(days=15))
        assert field_history.reads_history(rw.ray)["count"] == 0


def test_the_history_pages_with_no_cap(route_world):
    rw = route_world
    with tenant_ctx(rw.tenant):
        field_reads.sync_reads(rw.ray, {"items": [
            a_reading(f"pg-{n}", meter, str(48400 + n), route_id=rw.w.route_id)
            for n, meter in enumerate(("MTR-0471", "MTR-0472", "MTR-0473", "MTR-0474"))
        ]})
        field_reads.turn_in(rw.ray, rw.w.route_id, {"key": "turn-pg"})
        first = field_history.reads_history(rw.ray, page=1, per=50)
    assert first["count"] == 4 and first["next_page"] is None
    from apps.metering import field_reads_api

    assert resolve("/api/brazos/work/mobile/reads/history").func is field_reads_api.reads_history


def test_a_route_photo_loads_for_its_reader_and_is_a_404_for_another(route_world):
    rw = route_world
    photo_id = "0b6f7a52-6f8e-4c55-9d7e-3a3c2b1f4001"
    with tenant_ctx(rw.tenant):
        field_reads.sync_reads(rw.ray, {"items": [a_photo("ph-1", route_id=rw.w.route_id, photo_id=photo_id)]})
        field_read_photos.receive_bytes(rw.ray, photo_id, TINY_PNG, "image/png")
        data, _ = field_history.route_photo_content(rw.ray, photo_id)
        with pytest.raises(errors.NotFoundError):
            field_history.route_photo_content(rw.marco, photo_id)
    assert data == TINY_PNG
    from apps.metering import field_reads_api

    assert resolve(f"/api/brazos/work/mobile/reads/photos/{photo_id}/content").func is field_reads_api.reads_photo_content
