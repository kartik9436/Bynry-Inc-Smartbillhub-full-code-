# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-WRK-10601 — the phone's three reading shapes, on PostgreSQL
# Rules:    hard-won law 14 (a refused item inside the batch must not poison the
#           items after it) · hard rule 1 (RLS FORCE on the table that gained
#           two columns)
# Tests:    this file — skipped on SQLite BY DESIGN
# ───────────────────────────────────────────────────────
"""The three phone shapes in ONE batch with a refused item between them, on a
real PostgreSQL — the case SQLite cannot judge (law 14).

    cd 06-backend && DATABASE_URL=postgres://postgres:postgres@localhost:5432/postgres \\
        DJANGO_SETTINGS_MODULE=config.settings.pgtest JOBS_EAGER=false \\
        pytest tests/test_def_wrk_10601_job_reading_shapes_pg.py --reuse-db
"""

from __future__ import annotations

import pytest
from django.db import connection

from apps.work import models as work_models

from tests.isolation_helpers import requires_postgres
from tests.test_cr187_order_helpers import job
from tests.test_def_wrk_10601_job_reading_shapes import _as_text, _readings, _send, _shape
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana
from tests.test_us_met_helpers import tenant_ctx

pytestmark = [pytest.mark.django_db(transaction=True), requires_postgres]


def test_three_shapes_land_around_a_refused_item(brazos, dana):
    with tenant_ctx(brazos):
        oid, tech = job(dana, brazos)
        first, second, serial = _readings(oid)
        serial = _as_text(serial)
        out = _send(brazos, tech, oid, [
            _shape("number", first.id, first.unit_of_measure),
            # A unit the job was not raised with: refused inside its savepoint.
            _shape("number", second.id, "gal"),
            _shape("unable", second.id, second.unit_of_measure),
            _shape("text", serial.id, ""),
        ], prefix="pg")
        rows = {r.id: r for r in work_models.WorkOrderReading.objects.filter(work_order_id=oid)}

    assert [i["result"] for i in out["items"]] == ["accepted", "refused", "accepted", "accepted"], out["refusals"]
    assert str(rows[first.id].value) == "1204.0000"
    assert rows[second.id].unable_to_read is True and rows[second.id].value is None
    assert rows[serial.id].value_text == "W-5000-N"


def test_the_table_is_still_forced_under_row_security():
    with connection.cursor() as cur:
        cur.execute(
            "SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname = 'work_order_readings'"
        )
        assert cur.fetchone() == (True, True)
