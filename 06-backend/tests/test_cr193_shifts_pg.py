# ── Trace ──────────────────────────────────────────────
# Change:   CR-193-BRC10 — the four MQ-040 step-1 tables on REAL PostgreSQL 16
# Rules:    CLAUDE.md hard rule 1 (RLS ENABLE + FORCE, `work/0054`) · hard rule
#           6 (the handset's key) · hard-won laws 7 and 14
# Migration: work/0053 + work/0054
# ───────────────────────────────────────────────────────
"""Where the guarantees exist: the policies, and a refused INSERT that must
not poison the request (hard-won law 14 — SQLite has neither). Run::

    DJANGO_SETTINGS_MODULE=config.settings.pgtest JOBS_EAGER=false \\
      DATABASE_URL=postgres://postgres:postgres@localhost:5432/sbh \\
      pytest tests/test_cr193_shifts_pg.py --ds=config.settings.pgtest
"""

from __future__ import annotations

import pytest
from django.db import connection

from apps.work import shifts
from apps.work.shift_models import TechnicianDayException, TimesheetSubmission
from core import errors
from tests.isolation_helpers import (  # noqa: F401 — `rls` needs `rls_probe_role`
    assert_denied_without_context,
    assert_rls_scoped,
    assert_write_into_other_tenant_refused,
    requires_postgres,
    rls,
    rls_probe_role,
)
from tests.test_cr193_shifts import _ortiz, _slug
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin
from tests.test_us_met_helpers import tenant_ctx

pytestmark = [pytest.mark.django_db, pytest.mark.isolation, requires_postgres]

TABLES = (
    "work_technician_working_days",
    "work_technician_day_exceptions",
    "work_technician_shift_ends",
    "work_timesheet_submissions",
)


@pytest.mark.parametrize("table", TABLES)
def test_work_0053_each_table_is_enabled_and_forced(brazos, table):
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT c.relrowsecurity, c.relforcerowsecurity FROM pg_class c "
            "JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = 'public' AND c.relname = %s",
            [table],
        )
        assert cursor.fetchone() == (True, True)


def _seed(tenant, dana):
    with tenant_ctx(tenant):
        tech, actor = _ortiz(tenant)
        slug = _slug(tech)
        shifts.set_working_days(dana, slug, {"weekdays": ["mon", "tue"]})
        shifts.add_exception(dana, slug, {"date": "2026-11-02", "kind": "off"})
        shifts.end_shift(actor, {"key": "pg-end"})
        shifts.submit_day(actor, {"date": "2026-10-01", "key": "pg-sheet"})


@pytest.mark.parametrize("table", TABLES)
def test_work_0053_no_context_sees_nothing(brazos, dana, rls, table):
    _seed(brazos, dana)
    assert_denied_without_context(rls, table)


@pytest.mark.parametrize("table", TABLES)
def test_work_0053_one_utilitys_rows_are_invisible_to_the_other(brazos, lonestar, dana, rls, table):
    _seed(brazos, dana)
    assert_rls_scoped(rls, table, owner=brazos, intruder=lonestar)
    assert_write_into_other_tenant_refused(rls, table, owner=brazos, intruder=lonestar)


def test_pg_a_second_exception_for_the_day_is_refused_and_the_request_lives_on(brazos, dana):
    """Law 14: the losing INSERT is inside a SAVEPOINT, so the read after it in
    the same transaction still works. Forced past the pre-check to reach it."""
    with tenant_ctx(brazos):
        tech, _actor = _ortiz(brazos)
        slug = _slug(tech)
        shifts.add_exception(dana, slug, {"date": "2026-11-03", "kind": "off"})
        original_exists = TechnicianDayException.objects.filter
        try:
            # Skip the friendly pre-check so the database's unique index answers.
            TechnicianDayException.objects.filter = lambda *a, **k: original_exists(pk=None)  # type: ignore[method-assign]
            with pytest.raises(errors.BizError) as taken:
                shifts.add_exception(dana, slug, {"date": "2026-11-03", "kind": "off"})
        finally:
            TechnicianDayException.objects.filter = original_exists  # type: ignore[method-assign]
        assert taken.value.message_key == "work.shifts.exception_exists"
        assert TechnicianDayException.objects.filter(technician_id=tech.id).count() == 1


def test_pg_a_resubmitted_day_answers_the_first(brazos):
    with tenant_ctx(brazos):
        _tech, actor = _ortiz(brazos)
        first = shifts.submit_day(actor, {"date": "2026-10-02", "key": "pg-a"})
        again = shifts.submit_day(actor, {"date": "2026-10-02", "key": "pg-b"})
        assert first["duplicate"] is False and again["duplicate"] is True
        assert TimesheetSubmission.objects.filter(day="2026-10-02").count() == 1
