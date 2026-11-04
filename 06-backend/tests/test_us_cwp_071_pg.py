# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-071 TC-10 · US-CWP-072 TC-9 · US-CWP-073 TC-8 ·
#           US-CWP-074 TC-7 — the isolation only PostgreSQL can prove, on all
#           six published-content tables.
# Rules:    CLAUDE.md hard rule 1 (RLS FORCE; no tenant → nothing) ·
#           BR-CWP-005 · hard-won law 14 (proved on PostgreSQL, never faked on
#           SQLite — the default suite hardcodes in-memory SQLite, which has no
#           RLS at all, so a case that "passed" there would prove nothing)
# Tests:    this file
# Impacts:  apps/tenancy/migrations/0038_rls_cr068_d_published_content.py
# ───────────────────────────────────────────────────────
"""CR-068 wave D on PostgreSQL — what SQLite cannot hold.

    DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \\
    DATABASE_URL=postgres://smartbillhub:smartbillhub@127.0.0.1:5432/<db> \\
        pytest tests/test_us_cwp_071_pg.py

Every case carries `requires_postgres` and SKIPS on the default suite rather
than passing vacuously.

⚠ **AND IT CHECKS THE CATALOGUE, NOT ONLY THE ANSWER.** A query coming back
empty proves nothing on its own — an empty table looks exactly like a table
nobody may read. So the first case reads `pg_class` and asserts both
`relrowsecurity` AND `relforcerowsecurity` on each of the six: ENABLE without
FORCE leaves the table owner exempt, which is the shape a migration written
from memory produces and the shape no SELECT can distinguish.
"""

import pytest

from apps.tenancy import published_content_models as content
from apps.tenancy import published_content_sample
from core.tenancy import tenant_context
from tests.isolation_helpers import (  # noqa: F401 — fixtures used by name
    assert_denied_without_context,
    assert_rls_scoped,
    assert_write_into_other_tenant_refused,
    requires_postgres,
    rls,
    rls_enabled_tables,
    rls_probe_role,
)
from tests.test_us_cwp_helpers import *  # noqa: F401,F403


@requires_postgres
@pytest.mark.django_db
def test_all_six_tables_are_enabled_AND_forced_in_pg_class(pine_hill):
    """⚠ The catalogue, not the answer. `relrowsecurity` alone would let the
    owning role read every tenant's rows."""
    forced = set(rls_enabled_tables())
    missing = [table for table in content.TENANT_TABLES if table not in forced]
    assert not missing, (
        f"{missing} are not both ENABLE and FORCE row level security — "
        "a table with ENABLE and no FORCE is exempt for its owner (B2 §3)"
    )


@requires_postgres
@pytest.mark.django_db
def test_no_context_sees_no_published_content_at_all(pine_hill, sarah, rls):
    with tenant_context(pine_hill.id):
        published_content_sample.seed_published_content(pine_hill.id)
    assert_denied_without_context(rls, *content.TENANT_TABLES)


@requires_postgres
@pytest.mark.django_db
@pytest.mark.parametrize("table", list(content.TENANT_TABLES))
def test_pine_hills_rows_are_invisible_under_oak_ridge(
    pine_hill, sarah, oak_ridge, elena, rls, table
):
    with tenant_context(pine_hill.id):
        published_content_sample.seed_published_content(pine_hill.id)
    with tenant_context(oak_ridge.id):
        published_content_sample.seed_oak_ridge_content(oak_ridge.id)
    assert_rls_scoped(rls, table, owner=pine_hill, intruder=oak_ridge)


@requires_postgres
@pytest.mark.django_db
def test_a_cross_tenant_write_into_help_answers_is_refused_by_the_policy(
    pine_hill, sarah, oak_ridge, rls
):
    with tenant_context(pine_hill.id):
        published_content_sample.seed_published_content(pine_hill.id)
    assert_write_into_other_tenant_refused(rls, "help_answers", owner=pine_hill, intruder=oak_ridge)


@requires_postgres
@pytest.mark.django_db
def test_a_cross_tenant_write_into_service_centres_is_refused_by_the_policy(
    pine_hill, sarah, oak_ridge, rls
):
    with tenant_context(pine_hill.id):
        published_content_sample.seed_published_content(pine_hill.id)
    assert_write_into_other_tenant_refused(
        rls, "service_centres", owner=pine_hill, intruder=oak_ridge
    )
