# ── Trace ──────────────────────────────────────────────
# Change:   CR-187-BRC10 · lane INTEGRATE-2 — DEF-FLD-10357 (a route
#           photograph's door) and DEF-FLD-10358 (a route reading is its
#           CAPTOR's, not the courier's)
# Rules:    BR-WRK-059 (the capture token names who did it) · BR-WRK-062's
#           shape (the link is made with the record) · R61 / R125 · hard rule 6
# Tests:    this file (SQLite) · tests/test_cr187_route_photos_pg.py (PG 16)
# ───────────────────────────────────────────────────────
"""The reads door: who a route reading belongs to, and where its photographs go.

RED FIRST (hard-won law 7): at the commit before lane INTEGRATE-2, every case
here fails — `capture_token` was never read (the reading was the courier's),
`photo` was an unknown kind (refused `unknown_kind`), and there was no
`field_read_photos` to land bytes in.
"""

from __future__ import annotations

import hashlib
from types import SimpleNamespace

import pytest
from django.urls import resolve

from apps.metering import field_read_photos, field_reads
from apps.metering import models as metering_models
from apps.metering.field_read_models import FieldMeterProposal, FieldRead, FieldReadPhoto
from apps.work import mobile
from apps.work import models as work_models
from core import errors

from tests.test_cr187_reads_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_cr187_reads_helpers import a_reading, build_route, captured, reader_actor, tenant_ctx

pytestmark = pytest.mark.django_db

#: A one-pixel PNG — a real image, so the probe accepts it.
TINY_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010802000000907753de"
    "0000000c49444154789c63382127070002b6010534a675aa0000000049454e44ae426082"
)
PHOTO_ID = "0b6f7a52-6f8e-4c55-9d7e-3a3c2b1f0001"


def token_for(tenant, actor):
    """The CAPTOR's capture token, minted the way the handset is given one."""
    work_models.Technician.objects.get_or_create(tenant_id=tenant.id, user_id=actor.id)
    return mobile.issue_capture_token(SimpleNamespace(id=actor.id, role="field_technician"))["capture_token"]


@pytest.fixture()
def world(brazos, dana):
    with tenant_ctx(brazos):
        ray = reader_actor(brazos)
        marco = reader_actor(brazos, email="marco.chen@brazosbendutilities.test")
        route = build_route(brazos, dana, ray)
    return {"tenant": brazos, "ray": ray, "marco": marco, "route": route}


def a_photo(key, *, route_id, photo_id=PHOTO_ID, data=TINY_PNG, **extra):
    item = {
        "key": key,
        "kind": "photo",
        "route_id": str(route_id),
        "photo_id": photo_id,
        "sha256": hashlib.sha256(data).hexdigest(),
        "captured_at": captured(),
    }
    item.update(extra)
    return item


# ══════════════════════════════════════════════════════════════════════════
# DEF-FLD-10358 — the reading is its CAPTOR's
# ══════════════════════════════════════════════════════════════════════════
def test_a_reading_sent_by_marco_with_rays_token_is_rays(world):
    w = world["route"]
    with tenant_ctx(world["tenant"]):
        token = token_for(world["tenant"], world["ray"])
        item = a_reading("ray-tok-1", "MTR-0471", "48400", route_id=w.route_id, capture_token=token)
        out = field_reads.sync_reads(world["marco"], {"items": [item]})
        assert out["items"][0]["result"] == "accepted", out
        row = FieldRead.objects.get(key="ray-tok-1")
        assert row.reader_id == world["ray"].id
        assert row.reader_id != world["marco"].id


def test_without_a_token_the_reading_is_the_callers_as_before(world):
    w = world["route"]
    with tenant_ctx(world["tenant"]):
        out = field_reads.sync_reads(
            world["marco"], {"items": [a_reading("no-tok-1", "MTR-0471", "48400", route_id=w.route_id)]}
        )
        assert out["items"][0]["result"] == "accepted", out
        assert FieldRead.objects.get(key="no-tok-1").reader_id == world["marco"].id


def test_a_token_that_does_not_verify_is_refused_and_nothing_is_stored(world):
    w = world["route"]
    with tenant_ctx(world["tenant"]):
        item = a_reading("bad-tok-1", "MTR-0471", "48400", route_id=w.route_id, capture_token="forged")
        receipt = field_reads.sync_reads(world["marco"], {"items": [item]})["items"][0]
        assert receipt["result"] == "refused"
        assert receipt["reason"] == "capture_token_invalid"
        assert receipt["message_key"] == "work.mobile.reads.capture_token_invalid"
        assert not FieldRead.objects.filter(key="bad-tok-1").exists()


def test_an_expired_token_is_refused_back_and_a_stored_key_is_still_a_duplicate(world, monkeypatch):
    w = world["route"]
    with tenant_ctx(world["tenant"]):
        token = token_for(world["tenant"], world["ray"])
        first = a_reading("exp-tok-1", "MTR-0471", "48400", route_id=w.route_id, capture_token=token)
        assert field_reads.sync_reads(world["marco"], {"items": [first]})["items"][0]["result"] == "accepted"
        monkeypatch.setattr(mobile, "capture_token_max_age_s", lambda: -1)
        again = field_reads.sync_reads(world["marco"], {"items": [first]})["items"][0]
        assert again["result"] == "duplicate"
        fresh = a_reading("exp-tok-2", "MTR-0472", "48390", route_id=w.route_id, capture_token=token)
        receipt = field_reads.sync_reads(world["marco"], {"items": [fresh]})["items"][0]
        assert receipt["result"] == "refused"
        assert receipt["reason"] == "capture_token_expired"
        assert not FieldRead.objects.filter(key="exp-tok-2").exists()


def test_a_meter_added_in_the_field_is_proposed_by_its_captor(world):
    w = world["route"]
    with tenant_ctx(world["tenant"]):
        token = token_for(world["tenant"], world["ray"])
        item = {
            "key": "add-tok-1",
            "kind": "add_meter",
            "route_id": str(w.route_id),
            "premises_id": str(w.premises[0]),
            "meter": {"service": "electric", "badge": "90241"},
            "photos": [PHOTO_ID],
            "captured_at": captured(),
            "capture_token": token,
        }
        out = field_reads.sync_reads(world["marco"], {"items": [item]})
        assert out["items"][0]["result"] == "accepted", out
        assert FieldMeterProposal.objects.get(key="add-tok-1").proposed_by_id == world["ray"].id


# ══════════════════════════════════════════════════════════════════════════
# DEF-FLD-10357 — a route photograph is declared, not read; its bytes have a door
# ══════════════════════════════════════════════════════════════════════════
def test_a_photo_declaration_is_a_link_not_a_reading(world):
    w = world["route"]
    with tenant_ctx(world["tenant"]):
        token = token_for(world["tenant"], world["ray"])
        before = metering_models.MeterRead.objects.count()
        out = field_reads.sync_reads(
            world["marco"], {"items": [a_photo("ph-decl-1", route_id=w.route_id, capture_token=token)]}
        )
        receipt = out["items"][0]
        assert receipt["result"] == "accepted", out
        assert receipt["outcome"] == "recorded"
        assert receipt["photo_id"] == PHOTO_ID
        assert receipt["upload_url"].endswith(f"/work/mobile/reads/photos/{PHOTO_ID}")
        assert metering_models.MeterRead.objects.count() == before
        link = FieldReadPhoto.objects.get(photo_id=PHOTO_ID)
        assert link.state == "pending"
        assert link.reader_id == world["ray"].id
        assert link.key == "ph-decl-1"
        # A resend is a duplicate and still says where the bytes go.
        again = field_reads.sync_reads(world["marco"], {"items": [a_photo("ph-decl-1", route_id=w.route_id)]})
        assert again["items"][0]["result"] == "duplicate"
        assert again["items"][0]["first"]["upload_url"] == receipt["upload_url"]
        assert FieldReadPhoto.objects.filter(photo_id=PHOTO_ID).count() == 1


def test_a_reused_photo_id_with_other_bytes_is_refused(world):
    w = world["route"]
    with tenant_ctx(world["tenant"]):
        field_reads.sync_reads(world["ray"], {"items": [a_photo("ph-1", route_id=w.route_id)]})
        other = a_photo("ph-2", route_id=w.route_id, data=b"another photograph")
        receipt = field_reads.sync_reads(world["ray"], {"items": [other]})["items"][0]
        assert receipt["result"] == "refused"
        assert receipt["reason"] == "photo_id_reused"
        assert not FieldRead.objects.filter(key="ph-2").exists()


def test_the_bytes_land_once_and_only_the_declared_bytes(world):
    w = world["route"]
    with tenant_ctx(world["tenant"]):
        field_reads.sync_reads(world["ray"], {"items": [a_photo("ph-b-1", route_id=w.route_id)]})
        with pytest.raises(errors.BizError) as wrong:
            field_read_photos.receive_bytes(world["marco"], PHOTO_ID, b"not these bytes", "image/png")
        assert wrong.value.message_key == "work.photo.hash_mismatch"
        assert FieldReadPhoto.objects.get(photo_id=PHOTO_ID).state == "pending"
        landed = field_read_photos.receive_bytes(world["marco"], PHOTO_ID, TINY_PNG, "image/png")
        assert landed["state"] == "landed"
        assert landed["duplicate"] is False
        row = FieldReadPhoto.objects.get(photo_id=PHOTO_ID)
        assert bytes(row.data) == TINY_PNG
        assert row.bytes_received == len(TINY_PNG)
        again = field_read_photos.receive_bytes(world["marco"], PHOTO_ID, TINY_PNG, "image/png")
        assert again["duplicate"] is True
        assert field_read_photos.link_answer_for(PHOTO_ID)["state"] == "landed"


def test_bytes_for_an_undeclared_photo_are_a_404(world):
    with tenant_ctx(world["tenant"]):
        with pytest.raises(errors.NotFoundError):
            field_read_photos.receive_bytes(world["ray"], "0b6f7a52-6f8e-4c55-9d7e-3a3c2b1fffff", TINY_PNG)


def test_the_bytes_route_is_mounted():
    from apps.metering import field_reads_api

    match = resolve(f"/api/brazos/work/mobile/reads/photos/{PHOTO_ID}")
    assert match.func is field_reads_api.reads_photo
