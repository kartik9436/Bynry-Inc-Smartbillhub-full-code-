# ── Trace ──────────────────────────────────────────────
# Change:   FB-033 — `technician_availability_changes` on REAL PostgreSQL 16
# Rules:    CLAUDE.md hard rule 1 (RLS ENABLE + FORCE, `work/0063`) · hard rule
#           6 (the handset's key) · hard-won laws 7 and 14
# Migration: work/0062 + work/0063
# ───────────────────────────────────────────────────────
"""Where the guarantees exist: the policy, and a racing resend whose INSERT
must not poison the request (hard-won law 14 — SQLite has neither). Run::

    DJANGO_SETTINGS_MODULE=config.settings.pgtest JOBS_EAGER=false \\
      DATABASE_URL=postgres://… pytest tests/test_fb033_availability_pg.py --ds=config.settings.pgtest
"""

from __future__ import annotations

import pytest
from django.db import connection

from apps.work import availability
from apps.work.availability_models import TechnicianAvailabilityChange
from tests.isolation_helpers import (  # noqa: F401 — `rls` needs `rls_probe_role`
    assert_denied_without_context,
    assert_rls_scoped,
    assert_write_into_other_tenant_refused,
    requires_postgres,
    rls,
    rls_probe_role,
)
from tests.test_fb033_availability import _dana_tech
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin
from tests.test_us_met_helpers import tenant_ctx

pytestmark = [pytest.mark.django_db, pytest.mark.isolation, requires_postgres]

TABLE = "technician_availability_changes"


def test_work_0063_the_table_is_enabled_and_forced(brazos):
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT c.relrowsecurity, c.relforcerowsecurity FROM pg_class c "
            "JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = 'public' AND c.relname = %s",
            [TABLE],
        )
        assert cursor.fetchone() == (True, True)


def _seed(tenant):
    with tenant_ctx(tenant):
        _tech, actor = _dana_tech(tenant)
        availability.record(actor, {"key": "pg-av", "value": "off_duty"})


def test_work_0063_no_context_sees_nothing(brazos, rls):
    _seed(brazos)
    assert_denied_without_context(rls, TABLE)


def test_work_0063_one_utilitys_rows_are_invisible_to_the_other(brazos, lonestar, rls):
    _seed(brazos)
    assert_rls_scoped(rls, TABLE, owner=brazos, intruder=lonestar)
    assert_write_into_other_tenant_refused(rls, TABLE, owner=brazos, intruder=lonestar)


def test_pg_a_racing_resend_answers_the_first_and_the_request_lives_on(brazos):
    """Law 14: the losing INSERT is inside a SAVEPOINT, so the read after it in
    the same transaction still works. Forced past the pre-check to reach it."""
    with tenant_ctx(brazos):
        tech, actor = _dana_tech(brazos)
        availability.record(actor, {"key": "pg-race", "value": "on_break"})
        original = TechnicianAvailabilityChange.objects.filter
        calls = {"n": 0}

        def skip_first(*a, **k):
            calls["n"] += 1
            return original(pk=None) if calls["n"] == 1 else original(*a, **k)

        try:
            TechnicianAvailabilityChange.objects.filter = skip_first  # type: ignore[method-assign]
            again = availability.record(actor, {"key": "pg-race", "value": "on_break"})
        finally:
            TechnicianAvailabilityChange.objects.filter = original  # type: ignore[method-assign]
        assert again["duplicate"] is True
        assert TechnicianAvailabilityChange.objects.filter(technician_id=tech.id).count() == 1
