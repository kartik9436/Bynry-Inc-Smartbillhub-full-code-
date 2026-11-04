# ── Trace ──────────────────────────────────────────────
# Story:    CR-168-BRC10 round 3, lane SRV-2 — P2.12 (bulk raise) on real
#           PostgreSQL 16
# Rules:    hard-won law 14 (one savepoint per job; SQLite cannot see this) ·
#           CLAUDE.md hard rule 6 (idempotency) · hard rule 1 (RLS FORCE)
# Tests:    this file
# ───────────────────────────────────────────────────────
"""The three guarantees of the bulk raise SQLite cannot check.

Run it with a real database:

    DATABASE_URL=postgres://… DJANGO_SETTINGS_MODULE=config.settings.pgtest \\
        JOBS_EAGER=false pytest tests/test_cr168_srv2_bulk_raise_pg.py

1. **ONE SAVEPOINT PER JOB.** The second of three jobs is refused BY THE
   DATABASE (a unique-index violation issued with a cursor, so nothing in
   Python decides it) and the other two are raised. Without the per-job
   savepoint, PostgreSQL aborts the transaction at that statement and the
   third job fails with `InFailedSqlTransaction` — law 14's own signature,
   quoted in CR-168 §15 from the red run.
2. **A REPEATED KEY RAISES NOTHING.** The second press returns the first
   answer and the job count does not move.
3. **`work_bulk_raises` CARRIES ENABLE AND FORCE**, and a second tenant reads
   none of the first's rows under the non-superuser probe role.
"""

from __future__ import annotations

import pytest
from django.db import connection

from apps.work import connection_models as work_tables
from apps.work import raise_svc
from apps.work import services as work_services
from apps.work.seams import metering_seam

from tests.isolation_helpers import (  # noqa: F401 — `rls` needs `rls_probe_role`
    assert_rls_scoped,
    requires_postgres,
    rls,
    rls_probe_role,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin
from tests.test_us_met_helpers import make_premises, make_unit, tenant_ctx

pytestmark = [pytest.mark.django_db, pytest.mark.isolation]


def _building(dana, units=3):
    for code in ("work_priorities", "work_order_types"):
        work_services.seed_reference_list(code, [], "test")
    premises = make_premises(dana, address_line="301 Mill Pond Ln", services_available=["water"])
    return premises, [make_unit(dana, premises["id"], label=f"Apt {101 + n}") for n in range(units)]


@requires_postgres
def test_one_job_refused_by_the_database_does_not_lose_the_others(dana, brazos, monkeypatch):
    with tenant_ctx(brazos):
        premises, units = _building(dana)
        poisoned = units[1]["id"]
        real = metering_seam.raise_work_order

        def raise_or_violate(actor, payload):
            created = real(actor, payload)
            if str(payload.get("unit_id")) == str(poisoned):
                # A refusal FROM POSTGRESQL, not from Python: a second row for
                # this press's own key. `uq_work_bulk_raises_tenant_key` refuses
                # it, and with no savepoint the whole transaction is aborted
                # from this statement on.
                with connection.cursor() as cursor:
                    cursor.execute(
                        "INSERT INTO work_bulk_raises (id, tenant_id, idempotency_key, answer, created_at) "
                        "SELECT gen_random_uuid(), tenant_id, idempotency_key, '{}'::jsonb, now() "
                        "FROM work_bulk_raises WHERE idempotency_key = %s",
                        ["pg-press-1"],
                    )
            return created

        monkeypatch.setattr(metering_seam, "raise_work_order", raise_or_violate)
        answer = raise_svc.bulk_raise(
            dana,
            {"type": "Leak investigation", "service": "water", "premises_id": premises["id"],
             "unit_ids": [u["id"] for u in units], "idempotency_key": "pg-press-1"},
        )
        assert [r["ok"] for r in answer["results"]] == [True, False, True], answer
        assert answer["results"][1]["reason"] == "work.dispatch.refused"
        made = work_tables.WorkOrder.objects.filter(tenant_id=brazos.id, premises_id=premises["id"])
        assert sorted(str(o.unit_id) for o in made) == sorted([units[0]["id"], units[2]["id"]])


@requires_postgres
def test_a_repeated_press_raises_nothing_on_postgresql(dana, brazos):
    with tenant_ctx(brazos):
        premises, units = _building(dana)
        body = {"type": "Leak investigation", "service": "water", "premises_id": premises["id"],
                "unit_ids": [u["id"] for u in units], "idempotency_key": "pg-press-2"}
        first = raise_svc.bulk_raise(dana, dict(body))
        again = raise_svc.bulk_raise(dana, dict(body))
        assert first["done"] == 3 and again["replayed"] is True
        assert again["results"] == first["results"]
        assert work_tables.WorkOrder.objects.filter(tenant_id=brazos.id, premises_id=premises["id"]).count() == 3


@requires_postgres
def test_work_0033_bulk_raises_is_enabled_and_forced():
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname = 'work_bulk_raises'"
        )
        assert cursor.fetchone() == (True, True)


@requires_postgres
def test_work_0033_bulk_raises_are_invisible_to_another_tenant(dana, brazos, lonestar, rls):
    with tenant_ctx(brazos):
        premises, units = _building(dana, units=1)
        raise_svc.bulk_raise(
            dana,
            {"type": "Leak investigation", "service": "water", "premises_id": premises["id"],
             "unit_ids": [units[0]["id"]], "idempotency_key": "pg-press-3"},
        )
    assert_rls_scoped(rls, "work_bulk_raises", owner=brazos, intruder=lonestar, min_owner_rows=1)

