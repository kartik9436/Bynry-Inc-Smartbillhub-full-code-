# ── Trace ──────────────────────────────────────────────
# Change:   CR-187-BRC10 · Phase 13 · T-40/T-41 — lane S-FIND
# Rules:    CLAUDE.md hard rule 1 (RLS FORCE) · hard-won laws 7 and 14 ·
#           BR-FLD-00028 (R28)
# Migration: work/0039 + work/0040
# ───────────────────────────────────────────────────────
"""The two finds and the alert table on REAL PostgreSQL 16.

SQLite has no row-level security and no aborted-transaction state (hard-won law
14), and its `Case`/`Cast` arithmetic is not PostgreSQL's — so the distance SQL,
the policy on `work_field_alerts` and the escalation's savepoints are proved
here. Run:

    DJANGO_SETTINGS_MODULE=config.settings.pgtest JOBS_EAGER=false \\
      DATABASE_URL=postgres://postgres:postgres@localhost:5432/sbh \\
      pytest tests/test_cr187_find_pg.py --ds=config.settings.pgtest

The isolation proofs run as `sbh_rls_probe` (NOSUPERUSER NOBYPASSRLS, through
`tests.isolation_helpers`): a superuser bypasses every policy, `FORCE` included.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone

from tests.isolation_helpers import (  # noqa: F401 — `rls` needs `rls_probe_role`
    assert_denied_without_context,
    assert_rls_scoped,
    assert_write_into_other_tenant_refused,
    requires_postgres,
    rls,
    rls_probe_role,
)
from tests.test_cr187_find_alerts import _emergency, _technician
from tests.test_cr187_find_search_nearby import LAT0, LNG0, _job
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin
from tests.test_us_met_helpers import make_asset, tenant_ctx

pytestmark = [pytest.mark.django_db, pytest.mark.isolation]

TABLES = ("work_field_alerts",)


@requires_postgres
def test_work_0040_work_field_alerts_is_enabled_and_forced(brazos):
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT c.relrowsecurity, c.relforcerowsecurity FROM pg_class c "
            "JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = 'public' AND c.relname = 'work_field_alerts'"
        )
        assert cursor.fetchone() == (True, True)


@requires_postgres
def test_work_0040_with_no_tenant_context_no_alert_is_visible(brazos, rls):
    assert_denied_without_context(rls, *TABLES)


@requires_postgres
def test_work_0040_one_utilitys_alert_is_invisible_to_the_other(brazos, lonestar, dana, rls):
    with tenant_ctx(brazos):
        _emergency(dana, brazos)
    for table in TABLES:
        assert_rls_scoped(rls, table, owner=brazos, intruder=lonestar)


@requires_postgres
def test_work_0040_an_alert_restamped_for_another_tenant_is_refused(brazos, lonestar, dana, rls):
    with tenant_ctx(brazos):
        _emergency(dana, brazos)
    for table in TABLES:
        assert_write_into_other_tenant_refused(rls, table, owner=brazos, intruder=lonestar)


@requires_postgres
def test_pg_nearby_sorts_by_distance_in_sql_and_keeps_the_other_utility_out(brazos, lonestar, dana, erin):
    from apps.work import field_find

    with tenant_ctx(lonestar):
        _job(erin, "1 Same Spot", north_mi=0.1, service="water")
    with tenant_ctx(brazos):
        _me, me = _technician(brazos, "d.ortiz@b.test", "D. Ortiz")
        far = _job(dana, "Far", north_mi=1.5)
        near = _job(dana, "Near", north_mi=0.2, east_mi=0.1)
        _job(dana, "No Point")
        out = field_find.nearby(me, lat=str(LAT0), lng=str(LNG0))
    assert [r["order_no"] for r in out["results"]] == [near["order_no"], far["order_no"]]
    assert out["results"][1]["distance_mi"] == "1.50"
    assert out["without_location"] == 1 and out["complete"] is False


@requires_postgres
def test_pg_search_ranks_and_counts_in_sql(brazos, dana):
    from apps.work import field_find

    with tenant_ctx(brazos):
        contains = make_asset(dana, asset_no="A-ZX9-B", serial_no="Q-1")
        by_serial = make_asset(dana, asset_no="M-777", serial_no="zx9")
        out = field_find.search_assets(dana, q="ZX9", per=50)
    assert [r["id"] for r in out["results"]] == [by_serial["id"], contains["id"]]
    assert out["count"] == 2


@requires_postgres
def test_pg_emergency_ack_within_and_after_five_minutes(brazos, dana):
    """R28 on PostgreSQL: one escalation, once; a late answer kept and marked."""
    from apps.work import field_alerts
    from apps.work import models as work_models

    with tenant_ctx(brazos):
        answered, _t, tech_actor, _o = _emergency(dana, brazos)
        field_alerts.acknowledge(tech_actor, answered["id"])
        late_one = field_alerts.send_alert(dana, {"kind": "emergency", "work_order_id": _o["id"]})
        swept = field_alerts.escalate_unacknowledged(now=timezone.now() + timedelta(minutes=6))
        again = field_alerts.escalate_unacknowledged(now=timezone.now() + timedelta(minutes=7))
        work_models.WorkFieldAlert.objects.filter(pk=late_one["id"]).update(
            ack_due_at=timezone.now() - timedelta(seconds=1)
        )
        late = field_alerts.acknowledge(tech_actor, late_one["id"])
    assert [f["id"] for f in swept["fired"]] == [late_one["id"]]
    assert again["count"] == 0
    assert late["late"] is True and late["dispatch_told"] is True
