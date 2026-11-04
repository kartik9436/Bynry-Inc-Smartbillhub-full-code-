# ── Trace ──────────────────────────────────────────────
# Change:   DEF-MET-10633 (FB-003) on real PostgreSQL — metering/0081's partial
#           unique index `uq_field_reads_one_late_position`
# Rules:    hard rule 6 · hard-won law 14
# Tests:    this file — SKIPPED on SQLite by design
# ───────────────────────────────────────────────────────
"""The first late position stands; a second one costs nothing else.

Run::

    DJANGO_SETTINGS_MODULE=config.settings.pgtest DATABASE_URL=postgres://… \\
        JOBS_EAGER=false pytest tests/test_def_met_10633_late_position_pg.py --ds=config.settings.pgtest

A second late position for the same reading trips the partial unique index
INSIDE its item's savepoint. Without the savepoint PostgreSQL aborts the whole
request's transaction and every later item is lost at COMMIT — SQLite cannot
show that, so this file does.
"""

from __future__ import annotations

import contextlib

import pytest
from django.db import DatabaseError, transaction
from django.db.transaction import TransactionManagementError

from apps.metering import field_reads
from apps.metering.field_read_models import FieldRead

from tests.isolation_helpers import requires_postgres
from tests.test_cr187_reads_helpers import *  # noqa: F401,F403
from tests.test_cr187_reads_helpers import a_reading, build_route, reader_actor, tenant_ctx
from tests.test_def_met_10633_late_position import _no_fix_reading, _position

pytestmark = [pytest.mark.django_db, requires_postgres]


@pytest.fixture()
def world(brazos, dana):
    with tenant_ctx(brazos):
        reader = reader_actor(brazos)
        route = build_route(brazos, dana, reader)
    return {"tenant": brazos, "reader": reader, "route": route}


def _batch(w):
    return {
        "items": [
            _no_fix_reading("pg-read-1", w),
            _position("pg-pos-1", "pg-read-1", after_s=60, route_id=w.route_id),
            # A second late position for the same reading: the index answers,
            # inside this item's savepoint.
            _position("pg-pos-2", "pg-read-1", after_s=90, route_id=w.route_id),
            a_reading("pg-read-2", "MTR-0472", "48400", route_id=w.route_id),
        ]
    }


def test_the_second_late_position_is_a_duplicate_and_the_next_item_still_lands(world):
    w = world["route"]
    with tenant_ctx(world["tenant"]):
        out = field_reads.sync_reads(world["reader"], _batch(w))
        assert [i["result"] for i in out["items"]] == ["accepted", "accepted", "duplicate", "accepted"], out
        assert list(FieldRead.objects.filter(kind="position").values_list("key", flat=True)) == ["pg-pos-1"]
        assert FieldRead.objects.filter(key="pg-read-2").exists()


def test_without_the_savepoint_the_same_flush_is_poisoned(world, monkeypatch):
    """Law 7, in the harness that runs it: remove every item's nested atomic()
    and the second late position's failed INSERT aborts the transaction."""
    w = world["route"]
    real_atomic = transaction.atomic
    depth = {"n": 0}

    def outer_only(*args, **kwargs):
        depth["n"] += 1
        return real_atomic(*args, **kwargs) if depth["n"] == 1 else contextlib.nullcontext()

    with tenant_ctx(world["tenant"]):
        monkeypatch.setattr(field_reads.transaction, "atomic", outer_only)
        with pytest.raises((DatabaseError, TransactionManagementError)):
            field_reads.sync_reads(world["reader"], _batch(w))
