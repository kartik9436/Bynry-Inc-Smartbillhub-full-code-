# ── Trace ──────────────────────────────────────────────
# Change:   CR-168-BRC10 §F.8.3 — "a cross-tenant PostgreSQL probe on
#           `work_photo_links` (the RLS policy is applied and reversible; the
#           probe is owed)". Lane FIELD-2.
# Rules:    CLAUDE.md hard rule 1 (RLS FORCE) · B2 §3 · BR-WRK-062 ·
#           hard-won law 14 (SQLite has no row-level security) · law 7
# Migration under test: apps/work/migrations/0036_rls_force_photo_links.py
# ───────────────────────────────────────────────────────
"""`work_photo_links` under real row-level security, on real PostgreSQL.

A photo link holds a utility's photograph BYTES while they wait to be filed
(`staged`), the hash the phone declared, and which job and task they belong
to. A read across the tenant wall is another utility's meter photographs; a
WRITE across it is a photograph filed against someone else's job, which then
releases their Accept hold (`pending_required` counts links by job).

Skipped on SQLite BY DESIGN — see `tests/test_us_wrk_rls_pg.py`'s docstring for
why every read here runs under the `sbh_rls_probe` role. Run:

    DATABASE_URL=postgres://postgres@127.0.0.1:55433/<db> JOBS_EAGER=false \\
      pytest tests/test_cr168_photo_links_rls_pg.py --ds=config.settings.pgtest -p no:xdist
"""

from __future__ import annotations

import hashlib
import uuid

import pytest

from tests.isolation_helpers import (  # noqa: F401 — `rls` needs `rls_probe_role`
    assert_denied_without_context,
    assert_rls_scoped,
    assert_write_into_other_tenant_refused,
    requires_postgres,
    rls,
    rls_probe_role,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana
from tests.test_us_met_helpers import tenant_ctx

pytestmark = [pytest.mark.django_db, pytest.mark.isolation]

TABLE = "work_photo_links"


def _a_declared_link(dana, brazos) -> str:
    """One link for Brazos Bend, made the way the phone makes it: a `photo`
    item's declaration through `photo_links.declare`, on a real job."""
    from apps.work import photo_links
    from apps.work import models as work_models

    from tests.test_cr168_technician_api import _job

    oid, tech = _job(dana, brazos)
    task = work_models.WorkOrderTask.objects.filter(work_order_id=oid).order_by("seq").first()
    answer = photo_links.declare(
        tech,
        oid,
        {
            "photo_id": str(uuid.uuid4()),
            "sha256": hashlib.sha256(b"a meter face").hexdigest(),
            "task_id": str(task.id),
        },
    )
    return answer["photo_id"]


@requires_postgres
def test_work_photo_links_is_enabled_AND_forced(brazos):
    """Read from `pg_class`: the state of the DATABASE, not of the migration."""
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT c.relrowsecurity, c.relforcerowsecurity FROM pg_class c "
            "JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = 'public' AND c.relname = %s",
            [TABLE],
        )
        flags = cursor.fetchone()
    assert flags == (True, True), f"hard rule 1: {TABLE} needs ENABLE and FORCE, has {flags}"


@requires_postgres
def test_with_no_tenant_context_work_photo_links_returns_nothing(brazos, dana, rls):
    with tenant_ctx(brazos):
        _a_declared_link(dana, brazos)
    assert_denied_without_context(rls, TABLE)


@requires_postgres
def test_brazos_bends_photo_links_are_invisible_to_lone_star(brazos, lonestar, dana, rls):
    """Asserted through the database under a role RLS applies to — no
    application `filter(tenant_id=…)` is in the path."""
    with tenant_ctx(brazos):
        photo_id = _a_declared_link(dana, brazos)
    assert_rls_scoped(rls, TABLE, owner=brazos, intruder=lonestar)
    # And by the phone's own id, the thing an upload names in its URL.
    with rls.under(lonestar):
        assert rls.count(TABLE, "photo_id = %s", [photo_id]) == 0
    with rls.under(brazos):
        assert rls.count(TABLE, "photo_id = %s", [photo_id]) == 1


@requires_postgres
def test_a_photo_link_stamped_for_another_tenant_is_refused_by_the_policy(
    brazos, lonestar, dana, rls
):
    """The WITH CHECK half."""
    with tenant_ctx(brazos):
        _a_declared_link(dana, brazos)
    message = assert_write_into_other_tenant_refused(rls, TABLE, owner=brazos, intruder=lonestar)
    assert "row-level security" in message
