# ── Trace ──────────────────────────────────────────────
# Change:   CR-187-BRC10 lane FINDINGS — `work_route_findings` on REAL
#           PostgreSQL 16: its policy, and the rule's raise inside a savepoint
# Rules:    CLAUDE.md hard rule 1 (RLS ENABLE + FORCE, `work/0049`) · hard rule
#           6 (the capture key) · BR-WRK-067 · hard-won laws 7 and 14
# Migration: work/0048 + work/0049
# ───────────────────────────────────────────────────────
"""Route findings where the guarantees exist.

SQLite has no row-level security and no aborted-transaction state (hard-won
law 14), so the policy on `work_route_findings` and the rule's raise — which
must be able to FAIL without losing the finding — are proved here. Run::

    DJANGO_SETTINGS_MODULE=config.settings.pgtest JOBS_EAGER=false \\
      DATABASE_URL=postgres://postgres:postgres@localhost:5432/sbh \\
      pytest tests/test_cr187_route_findings_pg.py --ds=config.settings.pgtest

The isolation proofs run as `sbh_rls_probe` (NOSUPERUSER NOBYPASSRLS): a
superuser bypasses every policy, `FORCE` included.

RED FIRST (law 7), recorded in the lane report: with `work/0049`'s
`FORCE ROW LEVEL SECURITY` line removed the first case fails `(True, False)`;
with `_convert`'s `with transaction.atomic():` removed the savepoint case fails
on `InFailedSqlTransaction` — the finding and the whole batch are lost.
"""

from __future__ import annotations

import pytest
from django.db import connection

from apps.metering import field_reads
from apps.work import route_findings
from apps.work.route_finding_models import WorkRouteFinding
from apps.work.seams import metering_seam
from core import errors
from tests.isolation_helpers import (  # noqa: F401 — `rls` needs `rls_probe_role`
    assert_denied_without_context,
    assert_rls_scoped,
    assert_write_into_other_tenant_refused,
    requires_postgres,
    rls,
    rls_probe_role,
)
from tests.test_cr187_order_helpers import template
from tests.test_cr187_reads_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_cr187_reads_helpers import tenant_ctx
from tests.test_cr187_route_findings import (  # noqa: F401 — the `world` fixture
    SEAL_CHECK,
    _leak_rule,
    _orders,
    _sync,
    a_finding,
    world,
)

pytestmark = [pytest.mark.django_db, pytest.mark.isolation, requires_postgres]

TABLE = "work_route_findings"


def test_work_0049_the_table_is_enabled_and_forced(brazos):
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT c.relrowsecurity, c.relforcerowsecurity FROM pg_class c "
            "JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = 'public' AND c.relname = %s",
            [TABLE],
        )
        assert cursor.fetchone() == (True, True)


def test_work_0049_with_no_tenant_context_no_finding_is_visible(world, rls):
    with tenant_ctx(world["tenant"]):
        _sync(world, a_finding("pg-f-0", world, kind="broken_seal"))
    assert_denied_without_context(rls, TABLE)


def test_work_0049_one_utilitys_finding_is_invisible_to_the_other(world, lonestar, rls):
    with tenant_ctx(world["tenant"]):
        _sync(world, a_finding("pg-f-1", world, kind="broken_seal"))
    assert_rls_scoped(rls, TABLE, owner=world["tenant"], intruder=lonestar)
    assert_write_into_other_tenant_refused(rls, TABLE, owner=world["tenant"], intruder=lonestar)


def test_pg_a_rule_match_creates_exactly_one_job_and_a_resend_none(world):
    with tenant_ctx(world["tenant"]):
        _leak_rule(world)
        first = _sync(world, a_finding("pg-f-2", world))["items"][0]
        again = _sync(world, a_finding("pg-f-2", world))["items"][0]
        assert first["outcome"] == "work_order_created" and again["result"] == "duplicate"
        assert again["finding"]["work_order"] == first["finding"]["work_order"]
        assert _orders(world).count() == 1
        assert WorkRouteFinding.objects.filter(key="pg-f-2").count() == 1


def test_pg_no_rule_leaves_it_open_and_by_hand_converts_once(world):
    with tenant_ctx(world["tenant"]):
        receipt = _sync(world, a_finding("pg-f-3", world, kind="broken_seal"))["items"][0]
        assert receipt["outcome"] == "open" and _orders(world).count() == 0
        row = WorkRouteFinding.objects.get(key="pg-f-3")
        seal = template(world["admin"], world["tenant"], SEAL_CHECK)
        made = route_findings.office_create(world["admin"], row.id, {"template_id": str(seal)})
        again = route_findings.office_create(world["admin"], row.id, {"template_id": str(seal)})
        assert made["duplicate"] is False and again["duplicate"] is True
        assert again["work_order"] == made["work_order"]
        assert _orders(world).count() == 1


def test_pg_another_utility_gets_404_for_the_finding(world, lonestar, erin):
    with tenant_ctx(world["tenant"]):
        _sync(world, a_finding("pg-f-4", world, kind="broken_seal"))
        row = WorkRouteFinding.objects.get(key="pg-f-4")
    with tenant_ctx(lonestar):
        assert route_findings.office_page(status="all")["total"] == 0
        with pytest.raises(errors.NotFoundError):
            route_findings.office_create(erin, row.id, {"template_id": "x"})


def test_pg_a_raise_the_database_refuses_keeps_the_finding_and_the_batch(world, monkeypatch):
    """Hard-won law 14: a FAILED STATEMENT inside the rule's raise. Without
    `_convert`'s savepoint the transaction is aborted, the reading after it in
    the same batch raises `InFailedSqlTransaction`, and the finding is lost at
    COMMIT. With it, the raise alone rolls back and the finding waits open."""

    def refused_by_the_database(actor, payload):
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1 / 0")  # a real failed statement

    with tenant_ctx(world["tenant"]):
        _leak_rule(world)
        monkeypatch.setattr(metering_seam, "raise_work_order", refused_by_the_database)
        out = _sync(world, a_finding("pg-f-5", world), a_finding("pg-f-6", world, kind="broken_seal"))
        assert [i["result"] for i in out["items"]] == ["accepted", "accepted"], out
        assert [i["outcome"] for i in out["items"]] == ["open", "open"]
        assert WorkRouteFinding.objects.filter(key__in=["pg-f-5", "pg-f-6"], status="open").count() == 2
        assert _orders(world).count() == 0
