# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-021 (🔒, EP-CWP-03) TC-7 — the isolation only PostgreSQL can
#           prove. Screens: every signed-in portal screen stands on this
# Rules:    CLAUDE.md hard rule 1 (RLS FORCE; no tenant → nothing) ·
#           BR-CWP-005 (the tenant is resolved from the path and RLS forced
#           BEFORE the credential is read) · hard-won law 14 (proved on
#           PostgreSQL, never faked on SQLite)
# Tests:    this file
# Impacts:  apps/portal/migrations/0008_rls_portal_credentials.py
# ───────────────────────────────────────────────────────
"""US-CWP-021 on PostgreSQL — what SQLite cannot hold.

    DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \\
    DATABASE_URL=postgres://smartbillhub:smartbillhub@localhost:5432/<db> \\
        pytest tests/test_us_cwp_021_pg.py --reuse-db

Every case carries `requires_postgres` and SKIPS on the default SQLite suite
rather than passing vacuously (law 14: `config/settings/test.py` hardcodes
in-memory SQLite and ignores `DATABASE_URL`, and SQLite has no RLS at all).

⚠ **AND IT RUNS UNDER `rls_probe_role`, A NON-SUPERUSER.** A superuser bypasses
row security completely — `FORCE` included — and `DEF-2717` measured exactly
that: the same table, the same policy, the same `app.tenant_id`, and a
`SUPERUSER` role read the OTHER tenant's row. A green under the developer role
would be a green over nothing. `tests/isolation_helpers.rls` self-verifies that
the probe is a real proof and FAILS rather than skips if it is not.
"""

import pytest

from apps.portal import models
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

WAVE_E_TABLES = ("portal_credential", "portal_session", "portal_one_time_code")


@requires_postgres
@pytest.mark.django_db
def test_us_cwp_021_tc7_pg_the_three_tables_carry_enable_and_force():
    """⚠ **BOTH FLAGS, AND THAT IS THE POINT OF THIS CASE.**

    `relrowsecurity` alone is ENABLE, which leaves the table's OWNER exempt —
    and the owner is the role the application connects as. A migration that
    enabled without forcing would pass every row-count check in this file while
    the application itself saw every tenant's rows.
    """
    forced = set(rls_enabled_tables())
    missing = [table for table in WAVE_E_TABLES if table not in forced]
    assert not missing, (
        f"{missing} do not carry BOTH relrowsecurity AND relforcerowsecurity. ENABLE without "
        "FORCE leaves the table owner exempt, and the owner is the role this application "
        "connects as (CLAUDE.md hard rule 1; portal/0008)"
    )


@requires_postgres
@pytest.mark.django_db
def test_us_cwp_021_tc7_pg_no_context_sees_no_credential(pine_hill, sarah, rls):
    """With no `app.tenant_id`, all three tables answer zero rows.

    ⚠ **A COUNT OF ZERO ON AN EMPTY TABLE PROVES NOTHING**, which is why the
    case above asserts the two `pg_class` flags as well: an empty table looks
    exactly like a table nobody may read.
    """
    assert_denied_without_context(rls, *WAVE_E_TABLES)


@requires_postgres
@pytest.mark.django_db
def test_us_cwp_021_tc7_pg_pine_hills_credential_is_invisible_under_oak_ridge(
    pine_hill, sarah, oak_ridge, elena, rls
):
    """Maria's login row is not among the rows Oak Ridge's context returns."""
    maria = enrol_maria(pine_hill, sarah)
    assert_rls_scoped(
        rls,
        "portal_credential",
        owner=pine_hill,
        intruder=oak_ridge,
        owner_ids={str(maria.pk)},
    )


@requires_postgres
@pytest.mark.django_db
def test_us_cwp_021_tc7_pg_a_cross_tenant_write_is_refused_by_the_policy(
    pine_hill, sarah, oak_ridge, rls
):
    """The policy's WITH CHECK refuses a row re-stamped for another utility —
    and the assertion reads the DATABASE's own words, so a refusal that came
    from anywhere else (a constraint, a trigger, the app) fails this case."""
    enrol_maria(pine_hill, sarah)
    assert_write_into_other_tenant_refused(
        rls, "portal_credential", owner=pine_hill, intruder=oak_ridge
    )
