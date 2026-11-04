# ── Trace ──────────────────────────────────────────────
# Change:   CR-187-BRC10 Phase 13, lane S-ORDER — the PostgreSQL proofs:
#           RLS on the three new tables, the append-only reopen history, and
#           every path that CATCHES a database error and carries on.
# Rules:    CLAUDE.md hard rule 1 (RLS FORCE) · hard-won law 14 (a failed
#           statement poisons the PostgreSQL transaction; SQLite has no such
#           state, so these pass there by vacuum) · law 7 (prove it red)
# Migration under test: apps/work/migrations/0039_cr187_field_orders.py
# ───────────────────────────────────────────────────────
"""Skipped on SQLite BY DESIGN. Run:

    DJANGO_SETTINGS_MODULE=config.settings.pgtest DATABASE_URL=postgres://… \\
      JOBS_EAGER=false pytest tests/test_cr187_order_pg.py --ds=config.settings.pgtest
"""

from __future__ import annotations

import pytest
from django.db import connection, transaction

from apps.work import field_labour, field_raise, field_reopen
from apps.work.field_order_models import WorkFieldRaise, WorkOrderLabour, WorkOrderReopen

from tests.isolation_helpers import (  # noqa: F401 — `rls` needs `rls_probe_role`
    assert_denied_without_context,
    assert_rls_scoped,
    assert_write_into_other_tenant_refused,
    requires_postgres,
    rls,
    rls_probe_role,
)
from tests.test_cr187_order_helpers import FIX, close, job, person, template
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana
from tests.test_us_met_helpers import tenant_ctx

pytestmark = [pytest.mark.django_db, pytest.mark.isolation]

TABLES = ("work_order_labour", "work_order_reopens", "work_field_raises")


def _one_row_each(dana, brazos):
    """One row in each new table, made through the product's own doors."""
    oid, tech = job(dana, brazos)
    marco_row, _marco = person(brazos, "marco.pg@field.test", "Marco Rossi")
    field_labour.add_technician(tech, oid, {"technician_id": str(marco_row.id)})
    close(tech, oid, "passed")
    field_reopen.technician_reopen(tech, oid, {"reason": "missed_step"})
    tid = template(dana, brazos, "Leak investigation")
    field_raise.raise_from_field(
        tech,
        {"key": "pg-raise", "template_id": str(tid), "carried_from": str(oid), "location": FIX},
    )
    return oid, tech


@requires_postgres
@pytest.mark.parametrize("table", TABLES)
def test_each_new_table_is_enabled_and_forced(brazos, table):
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT c.relrowsecurity, c.relforcerowsecurity FROM pg_class c "
            "JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = 'public' AND c.relname = %s",
            [table],
        )
        flags = cursor.fetchone()
    assert flags == (True, True), f"hard rule 1: {table} needs ENABLE and FORCE, has {flags}"


@requires_postgres
def test_rows_are_invisible_across_the_tenant_wall_and_without_context(brazos, lonestar, dana, rls):
    with tenant_ctx(brazos):
        _one_row_each(dana, brazos)
    assert_denied_without_context(rls, *TABLES)
    for table in TABLES:
        assert_rls_scoped(rls, table, owner=brazos, intruder=lonestar)


@requires_postgres
@pytest.mark.parametrize("table", ("work_order_labour", "work_field_raises"))
def test_a_row_stamped_for_another_tenant_is_refused_by_the_policy(
    brazos, lonestar, dana, rls, table
):
    with tenant_ctx(brazos):
        _one_row_each(dana, brazos)
    message = assert_write_into_other_tenant_refused(rls, table, owner=brazos, intruder=lonestar)
    assert "row-level security" in message


@requires_postgres
def test_a_reopen_row_inserted_for_another_tenant_is_refused_by_the_policy(
    brazos, lonestar, dana, rls
):
    """The WITH CHECK half for `work_order_reopens`, by INSERT. The shared
    helper re-stamps by UPDATE, and this table's append-only trigger refuses
    every UPDATE before RLS is asked — measured on PostgreSQL 16, the helper
    reported *refused, but not by the RLS policy — the reopen history is
    append-only*. So the cross-tenant write is proved the other way."""
    from tests.isolation_helpers import live_tenant_context

    with tenant_ctx(brazos):
        _one_row_each(dana, brazos)
    with live_tenant_context(brazos.id):
        message = rls.refused(
            "INSERT INTO work_order_reopens "
            "(id, tenant_id, work_order_id, kind, reason, prior, at) "
            "SELECT gen_random_uuid(), %s, work_order_id, kind, reason, prior, now() "
            "FROM work_order_reopens WHERE tenant_id = %s LIMIT 1",
            [str(lonestar.id), str(brazos.id)],
        )
    assert "row-level security" in message, message


@requires_postgres
def test_the_reopen_history_refuses_update_and_delete(brazos, dana):
    """`trg_work_reopen_append_only` — *nothing overwritten* (E2E-17) is the
    database's rule, not this module's intention."""
    from django.db.utils import InternalError, ProgrammingError

    with tenant_ctx(brazos):
        _one_row_each(dana, brazos)
        row = WorkOrderReopen.objects.first()
        for attempt in (
            lambda: WorkOrderReopen.objects.filter(pk=row.pk).update(reason="rewritten"),
            lambda: WorkOrderReopen.objects.filter(pk=row.pk).delete(),
        ):
            with pytest.raises((InternalError, ProgrammingError)) as refused:
                with transaction.atomic():
                    attempt()
            assert "append-only" in str(refused.value)
        assert WorkOrderReopen.objects.get(pk=row.pk).reason == "missed_step"


# ── law 14: the catches survive a real aborted statement ──────────────────
@requires_postgres
def test_a_raise_that_loses_the_key_race_answers_the_first_and_the_transaction_lives(
    brazos, dana, monkeypatch
):
    """Two sends of one outbox item: the second passes the cheap pre-check
    (simulated by hiding the first) and hits the unique key. The savepoint
    must take the failed INSERT — and the second WO number — with it, and the
    caller's transaction must still answer queries afterwards."""
    with tenant_ctx(brazos):
        oid, tech = job(dana, brazos)
        tid = template(dana, brazos, "Leak investigation")
        body = {"key": "race-1", "template_id": str(tid), "carried_from": str(oid), "location": FIX}
        first = field_raise.raise_from_field(tech, body)

        real_filter = WorkFieldRaise.objects.filter
        calls = {"n": 0}

        def blind_once(*args, **kwargs):
            calls["n"] += 1
            qs = real_filter(*args, **kwargs)
            return qs.none() if calls["n"] == 1 else qs

        monkeypatch.setattr(WorkFieldRaise.objects, "filter", blind_once)
        second = field_raise.raise_from_field(tech, body)
        monkeypatch.undo()
        # The transaction is NOT poisoned: an ordinary query still answers.
        assert WorkFieldRaise.objects.filter(tenant_id=brazos.id).count() == 1
    assert second["duplicate"] is True and second["order_no"] == first["order_no"]


@requires_postgres
def test_adding_the_same_helper_twice_in_a_race_answers_one_row(brazos, dana, monkeypatch):
    with tenant_ctx(brazos):
        oid, tech = job(dana, brazos)
        marco_row, _marco = person(brazos, "marco.race@field.test", "Marco Rossi")
        first = field_labour.add_technician(tech, oid, {"technician_id": str(marco_row.id)})

        real_filter = WorkOrderLabour.objects.filter
        hidden = {"done": False}

        def blind_on_the_existence_check(*args, **kwargs):
            qs = real_filter(*args, **kwargs)
            if not hidden["done"] and kwargs.get("technician_id") == marco_row.id:
                hidden["done"] = True
                return qs.none()
            return qs

        monkeypatch.setattr(WorkOrderLabour.objects, "filter", blind_on_the_existence_check)
        second = field_labour.add_technician(tech, oid, {"technician_id": str(marco_row.id)})
        monkeypatch.undo()
        assert (
            WorkOrderLabour.objects.filter(work_order_id=oid, technician_id=marco_row.id).count()
            == 1
        )
    assert second["created"] is False and second["id"] == first["id"]
