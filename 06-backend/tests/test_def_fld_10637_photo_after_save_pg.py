# ── Trace ──────────────────────────────────────────────
# Change:   DEF-FLD-10637 (FB-019) on real PostgreSQL — metering/0082's
#           `field_reads.photo_for_id` foreign key
# Rules:    hard rule 6 · hard-won law 14
# Tests:    this file — SKIPPED on SQLite by design
# ───────────────────────────────────────────────────────
"""A photo sent back mid-batch costs nothing else; a linked one is a real FK.

Run::

    DJANGO_SETTINGS_MODULE=config.settings.pgtest DATABASE_URL=postgres://… \\
        JOBS_EAGER=false pytest tests/test_def_fld_10637_photo_after_save_pg.py --ds=config.settings.pgtest

The refusal path issues no failing statement (the reading is looked up, not
inserted against), and the item's savepoint is rolled back by `_SendBack` —
so the items after it in the same request still land, and the linked photo's
`photo_for_id` is enforced by PostgreSQL's own foreign key.
"""

from __future__ import annotations

import pytest

from apps.metering import field_reads
from apps.metering.field_read_models import FieldRead

from tests.isolation_helpers import requires_postgres
from tests.test_cr187_reads_helpers import *  # noqa: F401,F403
from tests.test_cr187_reads_helpers import a_reading, build_route, reader_actor, tenant_ctx
from tests.test_def_fld_10637_photo_after_save import ADDED_1, ADDED_2, _photo

pytestmark = [pytest.mark.django_db, requires_postgres]


@pytest.fixture()
def world(brazos, dana):
    with tenant_ctx(brazos):
        reader = reader_actor(brazos)
        route = build_route(brazos, dana, reader)
    return {"tenant": brazos, "reader": reader, "route": route}


def test_a_refused_photo_mid_batch_and_the_next_items_still_land(world):
    w = world["route"]
    with tenant_ctx(world["tenant"]):
        out = field_reads.sync_reads(
            world["reader"],
            {
                "items": [
                    a_reading("pg-read-1", "MTR-0471", "48400", route_id=w.route_id),
                    _photo("pg-photo-1", ADDED_1, route_id=w.route_id, reading_key="no-such-reading"),
                    _photo("pg-photo-2", ADDED_2, route_id=w.route_id, reading_key="pg-read-1"),
                    a_reading("pg-read-2", "MTR-0472", "48400", route_id=w.route_id),
                ]
            },
        )
        assert [i["result"] for i in out["items"]] == ["accepted", "refused", "accepted", "accepted"], out
        assert out["items"][1]["reason"] == "photo_reading_unknown"
        assert FieldRead.objects.get(key="pg-photo-2").photo_for == FieldRead.objects.get(key="pg-read-1")
        assert FieldRead.objects.filter(key="pg-read-2").exists()
        assert not FieldRead.objects.filter(key="pg-photo-1").exists()
