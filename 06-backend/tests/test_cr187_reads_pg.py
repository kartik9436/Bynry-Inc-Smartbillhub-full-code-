# ── Trace ──────────────────────────────────────────────
# Change:   CR-187-BRC10 — the route-reading sync's savepoint, on real
#           PostgreSQL (07-endpoints.md §0 rule 8: *"every NEW batch route
#           needs its own `_pg` test"*).
# Story:    US-FLD-042 TC-1 (one bad reading does not cost the other 49)
# Rules:    BR-WRK-042 · BR-WRK-063 · CLAUDE.md hard rule 1 (RLS FORCE) ·
#           **hard-won law 14** — the reason this file exists at all
# Tests:    this file — SKIPPED on SQLite by design
# ───────────────────────────────────────────────────────
"""Law 14, proved where it can be: PostgreSQL.

Run::

    DJANGO_SETTINGS_MODULE=config.settings.pgtest DATABASE_URL=postgres://… \\
        JOBS_EAGER=false pytest tests/test_cr187_reads_pg.py --ds=config.settings.pgtest

⚠ **THE RED PROOF IS IN THE SUITE** (law 7, in the harness that runs it):
`test_without_the_savepoint_the_transaction_is_poisoned` replaces the nested
`transaction.atomic()` in `apps/metering/field_reads.py` with a no-op and shows
the duplicate key ABORTS the transaction — the exact failure the savepoint
exists to prevent. On SQLite that same sabotage passes silently, which is why
this file skips there instead of passing.
"""

from __future__ import annotations

import contextlib

import pytest
from django.db import DatabaseError, connection, transaction
from django.db.transaction import TransactionManagementError

from apps.metering import field_reads
from apps.metering import models as metering_models
from apps.metering.field_read_models import FieldRead

from tests.isolation_helpers import requires_postgres
from tests.test_cr187_reads_helpers import *  # noqa: F401,F403
from tests.test_cr187_reads_helpers import a_reading, build_route, reader_actor, tenant_ctx

pytestmark = [pytest.mark.django_db, requires_postgres]


@pytest.fixture()
def world(brazos, dana):
    with tenant_ctx(brazos):
        reader = reader_actor(brazos)
        route = build_route(brazos, dana, reader)
    return {"tenant": brazos, "reader": reader, "route": route}


def _batch(w):
    good = [
        a_reading("pg-0001", "MTR-0471", "48400", route_id=w.route_id),
        a_reading("pg-0002", "MTR-0472", "48390", route_id=w.route_id),
    ]
    # Item 3 repeats item 1's KEY inside the same flush — the only path on which
    # the unique constraint (not a cheap read) answers, and so the only path on
    # which a failed statement can poison the transaction (`DEF-WRK-4079`).
    # Item 4 is below the last dial: refused until 2026-10-31, ACCEPTED with
    # its `negative_usage` flag since (FB-022, DEF-MET-10797).
    return {
        "items": [
            *good,
            dict(good[0]),
            a_reading("pg-0004", "MTR-0473", "41000", route_id=w.route_id),
            a_reading("pg-0005", "MTR-0474", "48420", route_id=w.route_id),
        ]
    }


def test_a_duplicate_and_a_refused_item_do_not_poison_the_rest(world):
    """⚠ AMENDED 2026-10-21 (PO: *"back to the technician"*): item 4, below the
    last dial, is REFUSED back to the reader and its row — inserted before the
    pipeline ran — is deleted in the same transaction. Until then it was
    stored and `held_for_review`. The savepoint is what this case is about,
    and the deletion is one more statement after a failed one, which is
    exactly where a poisoned transaction would show.

    ⚠ AMENDED AGAIN 2026-10-31 (FB-022, PO: *"do not refuse the reading
    accept"*): item 4 is now accepted, stored and posted with its flag. The
    duplicate key's failed statement is still what the savepoint is for."""
    w = world["route"]
    with tenant_ctx(world["tenant"]):
        out = field_reads.sync_reads(world["reader"], _batch(w))
        assert [i["result"] for i in out["items"]] == [
            "accepted",
            "accepted",
            "duplicate",
            "accepted",
            "accepted",
        ], out
        # TRUE AFTER the statements ran, not merely in the response: a poisoned
        # transaction would report these numbers and then lose the rows.
        assert FieldRead.objects.filter(key__startswith="pg-").count() == 4
        posted = metering_models.MeterRead.objects.filter(
            asset_id__in=[w.meters[m]["id"] for m in ("MTR-0471", "MTR-0472", "MTR-0473", "MTR-0474")],
            source="manual",
        )
        assert posted.count() == 4
        assert posted.get(asset_id=w.meters["MTR-0473"]["id"]).status == "negative_usage"
        with connection.cursor() as cursor:  # the connection is healthy
            cursor.execute("SELECT 1")
            assert cursor.fetchone() == (1,)


def test_without_the_savepoint_the_transaction_is_poisoned(world, monkeypatch):
    """The sabotage law 7 asks for: the nested atomic() becomes a no-op and the
    duplicate key's IntegrityError aborts the whole transaction."""
    w = world["route"]

    class _NoSavepoint:
        @staticmethod
        def atomic(*args, **kwargs):
            return contextlib.nullcontext()

    with tenant_ctx(world["tenant"]):
        monkeypatch.setattr(field_reads, "transaction", _NoSavepoint)
        with pytest.raises((DatabaseError, TransactionManagementError)):
            with transaction.atomic():
                field_reads.sync_reads(world["reader"], _batch(w))


def test_rls_is_enabled_and_forced_on_the_four_tables():
    """Read out of `pg_class`, not out of the migration (hard-won law 1)."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT relname, relrowsecurity, relforcerowsecurity FROM pg_class "
            "WHERE relname IN ('field_reads', 'cant_read_reasons', 'field_meter_proposals', "
            "'field_route_turn_ins') ORDER BY relname"
        )
        rows = cursor.fetchall()
    assert rows == [
        ("cant_read_reasons", True, True),
        ("field_meter_proposals", True, True),
        ("field_reads", True, True),
        ("field_route_turn_ins", True, True),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-FLD-042@fa5746815 (CR-187-BRC10 route-reading server lane)
# generated: 2026-10-21 by the CR-187 reads server lane
# checklist: A✔ B✔ C✔ D✔ E=deferred(no frontend in this lane) F✔ G✔ H=deferred(no 🔒 path in a test)
# gates: see the lane report
# exceptions: none
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
