# ── Trace ──────────────────────────────────────────────
# Change:  CR-187-BRC10 · Phase 13 — the money read and push, on PostgreSQL 16.
#          The 🔒 file under review is `apps/work/migrations/0040_rls_force_
#          money_pushes.py` (RLS ENABLE + FORCE on `work_money_pushes`).
# Rules:   CLAUDE.md hard rule 1 (tenant scoping; RLS FORCE) · hard-won law 14
#          (a failed statement poisons a PostgreSQL transaction — the sweep's
#          savepoint is proved HERE, never on SQLite) · R16 · R17 · R19
# ───────────────────────────────────────────────────────
"""PostgreSQL-only proofs. Run with
`DJANGO_SETTINGS_MODULE=config.settings.pgtest DATABASE_URL=postgres://… --ds=config.settings.pgtest`.
Every case skips on SQLite (`requires_postgres`) and FAILS, never skips, when the
probe role could bypass RLS."""

from __future__ import annotations

import pytest

from apps.work import money
from apps.work import models as work_models

from tests.isolation_helpers import (  # noqa: F401 — `rls` needs `rls_probe_role`
    assert_denied_without_context,
    assert_rls_scoped,
    requires_postgres,
    rls,
    rls_probe_role,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin
from tests.test_us_met_helpers import tenant_ctx
from tests.test_cr187_money_freshness import (
    a_bill,
    a_cancelled_payment,
    a_technician,
    an_order_on,
    pay,
)
from tests.test_w3_billing_models import an_account

pytestmark = [pytest.mark.django_db, pytest.mark.isolation]

TABLE = "work_money_pushes"


def _a_pushed_change(actor, tenant, *, account_no):
    account = an_account(actor, tenant, account_no=account_no)
    a_bill(tenant, account, "241.38", no=f"BL-2610-{account_no[-6:]}")
    tech, me = a_technician(tenant, f"{account_no.lower()}@pg.test")
    order, steps = an_order_on(actor, account, tech)
    pay(actor, account, "241.38")
    return account, order, steps, me


@requires_postgres
def test_work_0040_the_table_is_enabled_and_forced():
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname = %s", [TABLE]
        )
        assert cursor.fetchone() == (True, True)


@requires_postgres
def test_work_0040_one_utilitys_pushes_are_invisible_to_the_other(brazos, lonestar, dana, rls):
    with tenant_ctx(brazos):
        _a_pushed_change(dana, brazos, account_no="A-20588")
        assert money.sweep()["pushed"] == 1
    assert_rls_scoped(rls, TABLE, owner=brazos, intruder=lonestar)


@requires_postgres
def test_work_0040_with_no_tenant_context_the_table_answers_nothing(rls):
    assert_denied_without_context(rls, TABLE)


@requires_postgres
def test_law_14_a_lost_race_on_one_change_does_not_lose_the_next(brazos, dana, monkeypatch):
    """Two accounts change. The first one's mark is already there (another
    sweep won the race) and the `exists()` pre-check is made to miss it, so the
    INSERT really raises. Without the savepoint PostgreSQL aborts the
    transaction and the second account's push is lost with
    `InFailedSqlTransaction`; with it, the second is pushed."""
    from django.db.models import QuerySet

    with tenant_ctx(brazos):
        first, *_ = _a_pushed_change(dana, brazos, account_no="A-20589")
        _a_pushed_change(dana, brazos, account_no="A-20590")
        from apps.work.seams import payments_seam

        change_at = payments_seam.money_changed_since(
            [str(first.pk)], money.timezone.now() - money.FIRST_LOOK_BACK
        )[str(first.pk)]
        work_models.WorkMoneyPush.objects.create(
            tenant_id=brazos.id, account_id=first.pk, change_at=change_at
        )
        monkeypatch.setattr(QuerySet, "exists", lambda self: False)
        result = money.sweep()
        monkeypatch.undo()
        marks = work_models.WorkMoneyPush.objects.filter(tenant_id=brazos.id).count()
    assert result == {"accounts": 2, "changes": 1, "pushed": 1}
    assert marks == 2


@requires_postgres
def test_the_read_and_the_proceed_on_postgresql(brazos, dana):
    """FF-27's $241.38 and a cancelled $241.38 that moves nothing, and an
    unverified proceed written and read back through the real database."""
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-20591")
        a_bill(brazos, account, "241.38", no="BL-2610-020591")
        tech, me = a_technician(brazos, "pg-read@pg.test")
        order, [step] = an_order_on(dana, account, tech)
        a_cancelled_payment(account, "241.38")
        read = money.money_read(me, order["id"])
        answer = money.record_proceed(
            me, order["id"], step.id,
            {"money_as_at": "2026-10-17T09:12:00+00:00", "proceeded_at": "2026-10-20T09:12:00+00:00"},
        )
        step.refresh_from_db()
    assert read["owing"]["display"] == "241.38" and read["latest_payment"] is None
    assert answer["unverified"] is True and step.money_unverified is True


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-WRK-030@3e02d12e (CR-187-BRC10 Phase 13 T-33/T-34/T-35 on PostgreSQL 16; sha1[:8] of Rules.txt R16–R19 + WorkToDo.txt T-33..T-35, the design canvas of 2026-10-21)
# generated: 2026-10-21 by the CR-187 Phase 13 lane S-MONEY
# checklist: A✔ B✔ C✔ D=deferred(n/a) E=deferred(n/a) F✔ G✔ H✔ [work/0040 RLS]
# gates: pytest tests/test_cr187_money_pg.py on PostgreSQL 16 (--ds=config.settings.pgtest)
# exceptions: none
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
