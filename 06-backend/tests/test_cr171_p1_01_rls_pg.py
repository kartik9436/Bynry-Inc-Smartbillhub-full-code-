# ── Trace ──────────────────────────────────────────────
# Change:   CR-171-BRC10 `P1.01` (lane MVI-SCHEMA) — the three new tenant tables
#           of the move-in redesign, under real row-level security.
# Rules:    CLAUDE.md hard rule 1 (RLS FORCE) · B2 §3 · hard-won law 14 (SQLite
#           has no RLS) · law 7 (a probe under a role RLS applies to)
# Migration under test: apps/customers/migrations/0080_cr171_p1_01_move_in_redesign.py
# ───────────────────────────────────────────────────────
"""`account_co_owners`, `move_fee_lines` and `move_extra_messages` on PostgreSQL.

A co-owner row holds another person's encrypted SSN and licence, their date of
birth and phone; a fee line says what a household was charged; an extra message
says who is told what. A read across the tenant wall is another utility's
customers; a write across it is a fee on someone else's move.

Skipped on SQLite BY DESIGN (`requires_postgres`); every read runs under the
`sbh_rls_probe` role so a superuser connection cannot make the proof vacuous.
Run:

    DATABASE_URL=postgres://postgres@127.0.0.1:55433/<db> JOBS_EAGER=false \\
      pytest tests/test_cr171_p1_01_rls_pg.py --ds=config.settings.pgtest -p no:xdist
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from django.db import connection

from tests.isolation_helpers import (  # noqa: F401 — `rls` needs `rls_probe_role`
    assert_denied_without_context,
    assert_rls_scoped,
    assert_write_into_other_tenant_refused,
    requires_postgres,
    rls,
    rls_probe_role,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin
from tests.test_us_met_helpers import make_premises, make_unit, tenant_ctx

pytestmark = [pytest.mark.django_db, pytest.mark.isolation]

TABLES = ("account_co_owners", "move_fee_lines", "move_extra_messages")


def _seed(tenant, actor, service):
    """One account, one move record, and one row in each new table."""
    from apps.customers import models as cm
    from apps.customers import moves
    from apps.customers.co_owner_models import AccountCoOwner
    from apps.customers.move_in_extras import MoveExtraMessage, MoveFeeLine

    premises = make_premises(actor, address_line="1 Probe Way", services_available=[service])
    unit = make_unit(actor, premises["id"], label="Unit A", services=[service])
    account = cm.Account.objects.create(
        tenant=tenant,
        unit_id=unit["id"],
        status=cm.AccountStatus.objects.filter(tenant=tenant).first(),
        account_type=cm.AccountType.objects.filter(tenant=tenant).first(),
        account_no=f"A-{tenant.pk.hex[:8]}",
    )
    move = moves.MoveRecord.objects.create(
        tenant=tenant, kind=moves.KIND_MOVE_IN, account=account, effective_on=date(2026, 10, 10)
    )
    co = AccountCoOwner.objects.create(
        tenant=tenant, account=account, kind="co_owner", full_name="Riya G"
    )
    fee = MoveFeeLine.objects.create(
        tenant=tenant,
        move_record=move,
        seq=1,
        kind="deposit",
        source="plan",
        code="DEPOSIT",
        amount=Decimal("150.0000"),
        currency="USD",
    )
    msg = MoveExtraMessage.objects.create(
        tenant=tenant,
        move_record=move,
        seq=1,
        template_key="move_in_reminder",
        recipient="co_owner",
        co_owner=co,
        channel="text",
        send_when="day_before_move_in",
    )
    return {"account_co_owners": co.pk, "move_fee_lines": fee.pk, "move_extra_messages": msg.pk}


@requires_postgres
@pytest.mark.parametrize("table", TABLES)
def test_each_new_table_is_enabled_AND_forced(table):
    """Read from `pg_class`: the state of the DATABASE, not of the migration."""
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
def test_with_no_tenant_context_the_new_tables_return_nothing(brazos, dana, rls):
    with tenant_ctx(brazos):
        _seed(brazos, dana, "electric")
    assert_denied_without_context(rls, *TABLES)


@requires_postgres
def test_one_tenants_move_in_rows_are_invisible_to_another(brazos, lonestar, dana, erin, rls):
    rls.assert_is_a_real_proof()
    with tenant_ctx(brazos):
        mine = _seed(brazos, dana, "electric")
    with tenant_ctx(lonestar):
        # Lone Star Ridge is WATER-ONLY.
        _seed(lonestar, erin, "water")
    for table in TABLES:
        assert_rls_scoped(rls, table, owner=brazos, intruder=lonestar, owner_ids={str(mine[table])})
        with rls.under(lonestar):
            assert rls.count(table, "id = %s", [str(mine[table])]) == 0


@requires_postgres
def test_a_row_stamped_for_another_tenant_is_refused_by_the_policy(brazos, lonestar, dana, rls):
    """The WITH CHECK half."""
    with tenant_ctx(brazos):
        _seed(brazos, dana, "electric")
    for table in TABLES:
        message = assert_write_into_other_tenant_refused(
            rls, table, owner=brazos, intruder=lonestar
        )
        assert "row-level security" in message


@requires_postgres
def test_the_down_guard_counts_under_rls_rather_than_seeing_nothing(brazos, dana, rls):
    """DEF-RAT-5799's trap, proved closed: the guard is run AS THE PROBE ROLE —
    a role that does not bypass RLS, as a production migration role need not —
    with NO tenant set, and it must still find the rows and refuse."""
    import importlib

    from django.apps import apps as django_apps

    with tenant_ctx(brazos):
        _seed(brazos, dana, "electric")
    module = importlib.import_module("apps.customers.migrations.0080_cr171_p1_01_move_in_redesign")
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.tenant_id', '', false)")
        cursor.execute(f'SET ROLE "{rls.role}"')
    try:
        with pytest.raises(RuntimeError) as refused:
            module.refuse_while_rows_exist(django_apps, SimpleNamespace(connection=connection))
    finally:
        with connection.cursor() as cursor:
            cursor.execute("RESET ROLE")
    assert "1 co-owners" in str(refused.value)
    assert "1 fee lines" in str(refused.value)
    assert "1 extra messages" in str(refused.value)
