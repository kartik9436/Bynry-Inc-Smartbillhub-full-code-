# ── Trace ──────────────────────────────────────────────
# Change:   FB-030 (DEF-FLD-10806) — a technician's 14-day history, on real
#           PostgreSQL 16 under a NOSUPERUSER NOBYPASSRLS role
# Rules:    HR-1 (another's work is a 404) · CLAUDE.md hard rule 1 (RLS FORCE)
#           · NFR-3 (paged in SQL) · the reader index `field_reads` already has
# Tests:    this file — SKIPPED on SQLite by design
# ───────────────────────────────────────────────────────
"""The history doors, run AS `sbh_rls_probe` — a role that is not a superuser
and does not bypass row-level security — so every read below is filtered by the
tenant policies exactly as production filters it. Run::

    DJANGO_SETTINGS_MODULE=config.settings.pgtest DATABASE_URL=postgres://… \\
      JOBS_EAGER=false pytest tests/test_fb030_history_pg.py --ds=config.settings.pgtest

What it proves, each as the probe role:
  * another technician's closed job, job photo and route photo are a 404, and
    their 14-day refill is empty;
  * another TENANT's technician sees nothing at all — no job in the feed, the
    bundle and the photo are 404, the reads history is empty;
  * the owner still gets every one of them (so the 404s are not an empty
    database answering everybody the same);
  * the reader-history read is served by the index `field_reads.reader_id`
    already carries (a foreign key), so no migration was needed.
"""

from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.db import connection
from django.utils import timezone as dj_tz

from apps.metering import field_history, field_read_photos, field_reads
from apps.work import mobile
from apps.work.field_order_models import WorkOrderLabour
from core import errors

from tests.isolation_helpers import requires_postgres, rls, rls_probe_role  # noqa: F401
from tests.test_cr187_reads_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana
from tests.test_cr187_reads_helpers import a_reading, build_route, reader_actor
from tests.test_cr187_route_photos import TINY_PNG, a_photo
from tests.test_cr187_sync_feed import _as, _assign, _drain, _raise, _seed, _technician, _upserted
from tests.test_fb030_history import _close, _photo_link
from tests.test_us_ten_helpers import tenant_ctx

pytestmark = [pytest.mark.django_db, pytest.mark.isolation, requires_postgres]

JOB_PHOTO = "0b6f7a52-6f8e-4c55-9d7e-3a3c2b1f5001"
ROUTE_PHOTO = "0b6f7a52-6f8e-4c55-9d7e-3a3c2b1f5002"


@pytest.fixture()
def world(brazos, lonestar, dana):
    """Ortiz's closed job (Chen helped) with a photo; Ray's turned-in route with
    a reading and a photo — all in Brazos. Built as the app's own role."""
    with tenant_ctx(brazos):
        _seed()
        ortiz = _technician(brazos, "d-ortiz@brazos.test", "D. Ortiz")
        chen = _technician(brazos, "m-chen@brazos.test", "M. Chen")
        patel = _technician(brazos, "r-patel@brazos.test", "R. Patel")
        oid = _raise(dana, "221 Oak Ave")
        _assign(dana, oid, ortiz)
        WorkOrderLabour.objects.create(tenant_id=brazos.id, work_order_id=oid, technician=chen)
        _photo_link(brazos, oid, JOB_PHOTO)
        _close(oid, days_ago=3, field_data={"problem_found": "Seized valve", "what_i_did": "Replaced it"})
        ray = reader_actor(brazos)
        marco = reader_actor(brazos, email="marco.chen@brazosbendutilities.test")
        w = build_route(brazos, dana, ray, history=False)
        field_reads.sync_reads(ray, {"items": [
            a_reading("pg-h-1", "MTR-0471", "48400", route_id=w.route_id),
            a_photo("pg-ph-1", route_id=w.route_id, photo_id=ROUTE_PHOTO),
        ]})
        field_read_photos.receive_bytes(ray, ROUTE_PHOTO, TINY_PNG, "image/png")
        field_reads.turn_in(ray, w.route_id, {"key": "pg-turn-1"})
    with tenant_ctx(lonestar):
        stranger = _technician(lonestar, "x@lonestar.test", "X")
    return SimpleNamespace(
        brazos=brazos, lonestar=lonestar, oid=oid, ortiz=ortiz, chen=chen, patel=patel,
        ray=ray, marco=marco, stranger=stranger,
    )


def _as_probe(probe):
    return probe._as_role()


def test_the_probe_role_cannot_bypass_rls(rls):  # noqa: F811
    with connection.cursor() as cursor:
        cursor.execute("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = %s", [rls.role.strip('"')])
        assert cursor.fetchone() == (False, False)


def test_the_owner_and_the_helper_get_their_history_under_rls(world, rls):  # noqa: F811
    with _as_probe(rls), tenant_ctx(world.brazos):
        ortiz_feed, _, _ = _drain(_as(world.ortiz))
        chen_record = mobile.bundle(_as(world.chen), world.oid)["record"]
        data, _ = mobile.photo_content(_as(world.ortiz), JOB_PHOTO)
        reads = field_history.reads_history(world.ray)
        route_data, _ = field_history.route_photo_content(world.ray, ROUTE_PHOTO)
    assert str(world.oid) in _upserted(ortiz_feed)
    assert chen_record["problem"] == "Seized valve"
    assert data == TINY_PNG and route_data == TINY_PNG
    assert [r["key"] for r in reads["results"]] == ["pg-h-1"] and reads["results"][0]["unit"] == "kWh"


def test_another_technician_gets_404s_and_an_empty_refill_under_rls(world, rls):  # noqa: F811
    with _as_probe(rls), tenant_ctx(world.brazos):
        patel_feed, _, _ = _drain(_as(world.patel))
        with pytest.raises(errors.NotFoundError):
            mobile.bundle(_as(world.patel), world.oid)
        with pytest.raises(errors.NotFoundError):
            mobile.photo_content(_as(world.patel), JOB_PHOTO)
        with pytest.raises(errors.NotFoundError):
            field_history.route_photo_content(world.marco, ROUTE_PHOTO)
        marco_reads = field_history.reads_history(world.marco)
    assert str(world.oid) not in _upserted(patel_feed)
    assert marco_reads["count"] == 0


def test_another_tenant_sees_nothing_under_rls(world, rls):  # noqa: F811
    stranger_reader = SimpleNamespace(id=world.stranger.user_id, role="field_technician")
    with _as_probe(rls), tenant_ctx(world.lonestar):
        feed, _, _ = _drain(_as(world.stranger))
        with pytest.raises(errors.NotFoundError):
            mobile.bundle(_as(world.stranger), world.oid)
        with pytest.raises(errors.NotFoundError):
            mobile.photo_content(_as(world.stranger), JOB_PHOTO)
        with pytest.raises(errors.NotFoundError):
            field_history.route_photo_content(stranger_reader, ROUTE_PHOTO)
        # Even naming Ray's own id from the other tenant reads nothing.
        theirs = field_history.reads_history(world.ray)
    assert feed == []
    assert theirs["count"] == 0


def test_day_15_is_not_history_under_rls(world, rls):  # noqa: F811
    from apps.work import connection_models as work_tables

    with tenant_ctx(world.brazos):
        work_tables.WorkOrder.objects.filter(pk=world.oid).update(completed_at=dj_tz.now() - timedelta(days=15))
    with _as_probe(rls), tenant_ctx(world.brazos):
        feed, _, _ = _drain(_as(world.chen))
        with pytest.raises(errors.NotFoundError):
            mobile.bundle(_as(world.chen), world.oid)
    assert str(world.oid) not in _upserted(feed)


def test_the_reader_history_read_is_served_by_the_reader_index(world):
    """No new index was needed: `field_reads.reader_id` is a foreign key and
    carries Django's own index on it. Measured on PostgreSQL 16: with the
    tenant-only index taken away (inside this test's transaction, rolled back
    with it) and the sequential scan forbidden, the read goes BY READER."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT indexname FROM pg_indexes WHERE tablename = 'field_reads' AND indexdef LIKE '%%(reader_id)'"
        )
        reader_indexes = [r[0] for r in cursor.fetchall()]
        assert reader_indexes, "field_reads has no index on reader_id"
        cursor.execute(
            "SELECT indexname FROM pg_indexes WHERE tablename = 'field_reads' "
            "AND indexdef LIKE '%%(tenant_id)'"
        )
        for (name,) in cursor.fetchall():
            cursor.execute(f'DROP INDEX "{name}"')
        cursor.execute("SET LOCAL enable_seqscan = off")
        cursor.execute(
            "EXPLAIN SELECT id FROM field_reads WHERE tenant_id = %s AND reader_id = %s "
            "AND received_at >= now() - interval '14 days' ORDER BY received_at, id",
            [str(world.brazos.id), str(world.ray.id)],
        )
        plan = "\n".join(r[0] for r in cursor.fetchall())
    assert any(name in plan for name in reader_indexes), plan
    assert "Seq Scan" not in plan, plan
