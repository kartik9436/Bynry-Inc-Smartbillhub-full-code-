# ── Trace ──────────────────────────────────────────────
# Change:   CR-187-BRC10 · lane INTEGRATE-2 — DEF-FLD-10357 / DEF-FLD-10358 on
#           real PostgreSQL (07-endpoints.md §0 rule 8: a new write needs its
#           own `_pg` proof)
# Rules:    CLAUDE.md hard rule 1 (RLS FORCE) · hard rule 6 · hard-won law 14
# Tests:    this file — SKIPPED on SQLite by design
# ───────────────────────────────────────────────────────
"""The route photograph's link and the captor's reading, where it matters.

Run::

    DJANGO_SETTINGS_MODULE=config.settings.pgtest DATABASE_URL=postgres://… \\
        JOBS_EAGER=false pytest tests/test_cr187_route_photos_pg.py --ds=config.settings.pgtest

A photo declaration writes TWO rows inside its item's savepoint — the link
(`field_read_photos`) and the receipt (`field_reads`). When the receipt's
INSERT fails on its unique key (the same item twice in one flush), PostgreSQL
aborts the transaction unless the savepoint is there; the link written a
moment earlier must go with it, and every later item must still land.
"""

from __future__ import annotations

import contextlib
import hashlib

import pytest
from django.db import DatabaseError, transaction
from django.db.transaction import TransactionManagementError

from apps.metering import field_read_photos, field_reads
from apps.metering.field_read_models import FieldRead, FieldReadPhoto

from tests.isolation_helpers import requires_postgres, rls_enabled_tables
from tests.test_cr187_reads_helpers import *  # noqa: F401,F403
from tests.test_cr187_reads_helpers import a_reading, build_route, reader_actor, tenant_ctx
from tests.test_cr187_route_photos import TINY_PNG, a_photo, token_for

pytestmark = [pytest.mark.django_db, requires_postgres]

PHOTO_A = "0b6f7a52-6f8e-4c55-9d7e-3a3c2b1f00a1"
PHOTO_B = "0b6f7a52-6f8e-4c55-9d7e-3a3c2b1f00b2"


@pytest.fixture()
def world(brazos, dana):
    with tenant_ctx(brazos):
        ray = reader_actor(brazos)
        marco = reader_actor(brazos, email="marco.chen@brazosbendutilities.test")
        route = build_route(brazos, dana, ray)
    return {"tenant": brazos, "ray": ray, "marco": marco, "route": route}


def _batch(w, token):
    first = a_photo("pg-ph-1", route_id=w.route_id, photo_id=PHOTO_A, capture_token=token)
    return {
        "items": [
            first,
            # The same item again in one flush: the receipt's unique key — not
            # a cheap read — answers, so a failed statement happens INSIDE the
            # item, after its link row was written (law 14's case).
            dict(first),
            a_reading("pg-rd-1", "MTR-0471", "48400", route_id=w.route_id, capture_token=token),
            a_photo("pg-ph-2", route_id=w.route_id, photo_id=PHOTO_B, capture_token=token),
        ]
    }


def test_the_new_table_has_a_forced_tenant_policy():
    assert "field_read_photos" in rls_enabled_tables()


def test_a_duplicate_inside_one_flush_costs_nothing_else_and_every_row_is_the_captors(world):
    w = world["route"]
    with tenant_ctx(world["tenant"]):
        token = token_for(world["tenant"], world["ray"])
        out = field_reads.sync_reads(world["marco"], _batch(w, token))
        assert [i["result"] for i in out["items"]] == ["accepted", "duplicate", "accepted", "accepted"], out
        assert FieldReadPhoto.objects.filter(photo_id__in=[PHOTO_A, PHOTO_B]).count() == 2
        assert set(FieldRead.objects.filter(key__in=["pg-ph-1", "pg-rd-1", "pg-ph-2"]).values_list("reader_id", flat=True)) == {
            world["ray"].id
        }
        assert set(FieldReadPhoto.objects.values_list("reader_id", flat=True)) == {world["ray"].id}


def test_the_bytes_land_in_postgres_and_come_back_byte_for_byte(world):
    w = world["route"]
    with tenant_ctx(world["tenant"]):
        field_reads.sync_reads(world["ray"], {"items": [a_photo("pg-ph-b", route_id=w.route_id, photo_id=PHOTO_A)]})
        assert field_read_photos.receive_bytes(world["marco"], PHOTO_A, TINY_PNG, "image/png")["state"] == "landed"
        row = FieldReadPhoto.objects.get(photo_id=PHOTO_A)
        assert hashlib.sha256(bytes(row.data)).hexdigest() == row.sha256


def test_without_the_savepoint_the_same_flush_is_poisoned(world, monkeypatch):
    """Law 7, in the harness that runs it: replace the item's nested atomic()
    with a no-op and the duplicate's failed INSERT aborts the transaction —
    the exact failure the savepoint exists to prevent."""
    w = world["route"]
    real_atomic = transaction.atomic
    depth = {"n": 0}

    def outer_only(*args, **kwargs):
        depth["n"] += 1
        # The request's own transaction is the first; every item's savepoint after it is removed.
        return real_atomic(*args, **kwargs) if depth["n"] == 1 else contextlib.nullcontext()

    with tenant_ctx(world["tenant"]):
        token = token_for(world["tenant"], world["ray"])
        monkeypatch.setattr(field_reads.transaction, "atomic", outer_only)
        with pytest.raises((DatabaseError, TransactionManagementError)):
            field_reads.sync_reads(world["marco"], _batch(w, token))
