# ── Trace ──────────────────────────────────────────────
# Change:   CR-187-BRC10 lane S-GAPS — the PostgreSQL proofs for the keyed
#           acts and hand-back and the leave door.
# Rules:    CLAUDE.md hard rule 1 (RLS FORCE stays on) · BR-WRK-025 (the
#           assignment history is append-only — the trigger still refuses an
#           UPDATE, the new key column included) · hard-won law 14 (a lost race
#           on the key must not poison the transaction) · law 7 (prove it red)
# Migration under test: apps/work/migrations/0047_cr187_assignment_capture_key.py
# ───────────────────────────────────────────────────────
"""Skipped on SQLite BY DESIGN. Run:

    DJANGO_SETTINGS_MODULE=config.settings.pgtest DATABASE_URL=postgres://… \\
      JOBS_EAGER=false pytest tests/test_cr187_gaps_pg.py --ds=config.settings.pgtest

⚠ **THE RACE IS A REAL FAILED STATEMENT.** Each race case blinds the cheap
key lookup ONCE, so the second send reaches the INSERT and PostgreSQL refuses
it on `uq_work_order_assignments_key`. The `atomic()` around the act must take
the failed row — and its cache refresh and audit row — with it, and the caller
must still be able to query afterwards. Without the unique index (the red proof
below drops it for one run) the second send appends a second *depart*.
"""

from __future__ import annotations

import pytest
from django.db import connection, transaction

from apps.work import dispatch, field_dispatch, field_labour, mobile
from apps.work import models as work_models
from apps.work.field_order_models import WorkOrderLabour

from tests.isolation_helpers import (  # noqa: F401 — `rls` needs `rls_probe_role`
    assert_denied_without_context,
    assert_rls_scoped,
    requires_postgres,
    rls,
    rls_probe_role,
)
from tests.test_cr187_order_helpers import job, person, template
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_wrk_032_copies import _raise

pytestmark = [pytest.mark.django_db, pytest.mark.isolation]


def _blind_once(monkeypatch):
    """Hide the first answer of `mobile.assignment_by_key` — the race where two
    sends of one outbox item both pass the cheap lookup."""
    real = mobile.assignment_by_key
    calls = {"n": 0}

    def blind(key):
        calls["n"] += 1
        return None if calls["n"] == 1 else real(key)

    monkeypatch.setattr(mobile, "assignment_by_key", blind)


@requires_postgres
def test_the_assignment_table_is_still_enabled_and_forced(brazos):
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT c.relrowsecurity, c.relforcerowsecurity FROM pg_class c "
            "JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = 'public' AND c.relname = 'work_order_assignments'"
        )
        flags = cursor.fetchone()
        cursor.execute(
            "SELECT indexdef FROM pg_indexes WHERE indexname = 'uq_work_order_assignments_key'"
        )
        index = cursor.fetchone()
    assert flags == (True, True), f"hard rule 1: ENABLE and FORCE, has {flags}"
    assert index and "UNIQUE" in index[0] and "WHERE (key IS NOT NULL)" in index[0], index


@requires_postgres
def test_keyed_rows_stay_invisible_across_the_tenant_wall(brazos, lonestar, dana, rls):
    with tenant_ctx(brazos):
        oid, tech = job(dana, brazos)
        mobile.field_act(tech, oid, {"act": "depart", "key": "pg-rls-1"})
    assert_denied_without_context(rls, "work_order_assignments")
    assert_rls_scoped(rls, "work_order_assignments", owner=brazos, intruder=lonestar)


@requires_postgres
def test_the_append_only_trigger_still_refuses_rewriting_a_key(brazos, dana):
    from django.db.utils import InternalError, ProgrammingError

    with tenant_ctx(brazos):
        oid, tech = job(dana, brazos)
        mobile.field_act(tech, oid, {"act": "depart", "key": "pg-trig-1"})
        row = work_models.WorkOrderAssignment.objects.get(key="pg-trig-1")
        with pytest.raises((InternalError, ProgrammingError)) as refused:
            with transaction.atomic():
                work_models.WorkOrderAssignment.objects.filter(pk=row.pk).update(key="rewritten")
        assert "append-only" in str(refused.value)
        assert work_models.WorkOrderAssignment.objects.get(pk=row.pk).key == "pg-trig-1"


@requires_postgres
def test_a_depart_that_loses_the_key_race_answers_duplicate_and_the_transaction_lives(
    brazos, dana, monkeypatch
):
    with tenant_ctx(brazos):
        oid, tech = job(dana, brazos)
        first = mobile.field_act(tech, oid, {"act": "depart", "key": "pg-race-dep"})
        _blind_once(monkeypatch)
        with transaction.atomic():  # the caller's own transaction, as a request's
            second = mobile.field_act(tech, oid, {"act": "depart", "key": "pg-race-dep"})
            # NOT poisoned: an ordinary query still answers inside it.
            departs = work_models.WorkOrderAssignment.objects.filter(
                work_order_id=oid, act="depart"
            ).count()
    assert second["duplicate"] is True and second["assignment_id"] == first["assignment_id"]
    assert departs == 1


@requires_postgres
def test_a_hand_back_that_loses_the_key_race_answers_duplicate(brazos, dana, monkeypatch):
    with tenant_ctx(brazos):
        oid = _raise(dana, brazos, template(dana, brazos))["id"]
        tech_row, tech = person(brazos, "pg.hb@field.test", "D. Ortiz")
        dispatch.record_act(
            dana, oid, {"act": "assign", "technician_id": str(tech_row.id)}, push=False
        )
        mobile.accept_job(tech, oid)
        first = field_dispatch.hand_back(tech, oid, {"reason": "Van", "key": "pg-race-hb"})
        # The race the key lookup cannot see: the order still looks like hers to
        # the second send (both passed `_own_job_or_404` before either wrote).
        dispatch.record_act(
            dana, oid, {"act": "assign", "technician_id": str(tech_row.id)}, push=False
        )
        _blind_once(monkeypatch)
        with transaction.atomic():
            second = field_dispatch.hand_back(tech, oid, {"reason": "Van", "key": "pg-race-hb"})
            unassigns = work_models.WorkOrderAssignment.objects.filter(
                work_order_id=oid, act="unassign", key="pg-race-hb"
            ).count()
            holder = work_models.WorkOrderAssignment.objects.filter(work_order_id=oid).count()
    assert first["duplicate"] is False and second["duplicate"] is True
    assert unassigns == 1 and holder >= 3


@requires_postgres
def test_leaving_and_correcting_another_persons_time_hold_on_postgres(brazos, dana):
    """The CHECKs that back `_refuse_backwards` are real here; a correction a
    lead sends for a helper lands on the helper's row and only there."""
    from datetime import timedelta

    from django.utils import timezone

    with tenant_ctx(brazos):
        oid, lead = job(dana, brazos)
        marco_row, marco = person(brazos, "pg.marco@field.test", "Marco Rossi")
        field_labour.add_technician(lead, oid, {"technician_id": str(marco_row.id)})
        now = timezone.now()
        field_labour.record_time(marco, oid, {"arrive_at": (now - timedelta(minutes=90)).isoformat()})
        left = field_labour.crew_door(
            lead, oid, {"act": "leave", "technician_id": str(marco_row.id)}
        )
        fixed = field_labour.record_time(
            lead,
            oid,
            {"technician_id": str(marco_row.id), "end_at": (now - timedelta(minutes=18)).isoformat()},
        )
        rows = {
            r.technician_id: r for r in WorkOrderLabour.objects.filter(work_order_id=oid)
        }
    assert left["changed"] == ["end_at"]
    assert fixed["labour_minutes"] == 72 and fixed["corrected"] == ["end_at"]
    assert rows[marco_row.id].corrections == 1


@requires_postgres
def test_without_the_unique_index_a_lost_race_appends_a_second_depart(
    brazos, dana, monkeypatch
):
    """THE RED PROOF, kept in the file (law 7): drop `uq_work_order_assignments_key`
    for one run and the same race appends a second *depart* — so the index,
    not the lookup, is what ends the race. Restored by the test transaction's
    rollback."""
    with tenant_ctx(brazos):
        oid, tech = job(dana, brazos)
        mobile.field_act(tech, oid, {"act": "depart", "key": "pg-red-dep"})
        with connection.cursor() as cursor:
            cursor.execute("DROP INDEX uq_work_order_assignments_key")
        _blind_once(monkeypatch)
        second = mobile.field_act(tech, oid, {"act": "depart", "key": "pg-red-dep"})
        departs = work_models.WorkOrderAssignment.objects.filter(
            work_order_id=oid, act="depart"
        ).count()
    assert second["duplicate"] is False
    assert departs == 2, "without the index the race is NOT caught — the guard is the index"
