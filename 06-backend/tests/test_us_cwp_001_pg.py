# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-001 (EP-CWP-01) TC-5 · US-CWP-069 TC-8 · US-CWP-070 TC-7 —
#           the isolation only PostgreSQL can prove.
# Rules:    CLAUDE.md hard rule 1 (RLS FORCE; no tenant → nothing) · BR-CWP-005
#           · hard-won law 14 (proved on PostgreSQL, never faked on SQLite)
# Tests:    this file — zero rows without context under the non-superuser
#           probe role; Pine Hill's row invisible under Oak Ridge; a
#           cross-tenant re-stamp refused by the policy itself
# Impacts:  apps/portal/migrations/0002_rls_portal_settings.py
# ───────────────────────────────────────────────────────
"""US-CWP-001 on PostgreSQL — what SQLite cannot hold.

    DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \\
    DATABASE_URL=postgres://smartbillhub:smartbillhub@localhost:5432/<db> \\
        pytest tests/test_us_cwp_001_pg.py

Every case carries `requires_postgres` and SKIPS on the default SQLite suite
rather than passing vacuously (hard-won law 14).
"""

import pytest

from apps.portal import models
from tests.isolation_helpers import (  # noqa: F401 — fixtures used by name
    assert_denied_without_context,
    assert_rls_scoped,
    assert_write_into_other_tenant_refused,
    requires_postgres,
    rls,
    rls_probe_role,
)
from tests.test_us_cwp_helpers import *  # noqa: F401,F403
from tests.test_us_cwp_helpers import switch_on


@requires_postgres
@pytest.mark.django_db
def test_us_cwp_001_tc5_pg_no_context_sees_no_portal_settings_row(pine_hill, sarah, rls):
    switch_on(pine_hill, sarah)
    assert_denied_without_context(rls, *models.TENANT_TABLES)


@requires_postgres
@pytest.mark.django_db
def test_us_cwp_001_tc5_pg_pine_hills_row_is_invisible_under_oak_ridge(pine_hill, sarah, oak_ridge, elena, rls):
    switch_on(pine_hill, sarah)
    switch_on(oak_ridge, elena)
    assert_rls_scoped(
        rls,
        "portal_settings",
        owner=pine_hill,
        intruder=oak_ridge,
        owner_ids={str(pine_hill.id)},
        id_column="tenant_id",
    )


@requires_postgres
@pytest.mark.django_db
def test_us_cwp_001_tc5_pg_a_cross_tenant_write_is_refused_by_the_policy(pine_hill, sarah, oak_ridge, rls):
    switch_on(pine_hill, sarah)
    assert_write_into_other_tenant_refused(rls, "portal_settings", owner=pine_hill, intruder=oak_ridge)
