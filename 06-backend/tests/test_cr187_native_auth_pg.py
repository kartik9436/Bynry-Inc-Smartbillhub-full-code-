# ── Trace ──────────────────────────────────────────────
# Change:   CR-187-BRC10 — the native field app's sign-in, on PostgreSQL 16
# Rules:    hard rule 1 (RLS ENABLE + FORCE on `native_tokens`,
#           `activation_codes`) · hard-won law 14 (a refused call must not roll
#           back the revocation or the lockout it wrote) · BR-IDN-006
# ───────────────────────────────────────────────────────
"""The same contract on real PostgreSQL, plus what SQLite cannot show.

Run it (PostgreSQL 16 locally):

    DJANGO_SETTINGS_MODULE=config.settings.pgtest \\
    DATABASE_URL=postgres://postgres:postgres@localhost:5432/sbh JOBS_EAGER=false \\
    pytest tests/test_cr187_native_auth_pg.py --ds=config.settings.pgtest

1. **RLS on the two new tables, read out of `pg_class`, and probed under a
   role row security actually applies to** (`rls_probe_role` — NOSUPERUSER,
   NOBYPASSRLS): one utility's tokens and codes are invisible to the other,
   none is visible with no context, none may be written stamped for another.
2. **Every HTTP case of `test_cr187_native_auth.py` again**, imported below, so
   the tenant GUC is the shipping kernel's and the token rows are read under it.
   The cross-tenant 404, the refresh-reuse revocation that must SURVIVE its own
   401, the lockout that must survive its refusal, and the weak password that
   must roll back without burning a code are all transaction-shaped, which is
   exactly where SQLite cannot be believed (hard-won law 14).
"""

from __future__ import annotations

import pytest

from tests.isolation_helpers import (  # noqa: F401 — `rls` needs `rls_probe_role`
    assert_denied_without_context,
    assert_rls_scoped,
    assert_write_into_other_tenant_refused,
    requires_postgres,
    rls,
    rls_probe_role,
)
from tests.test_cr187_native_auth import *  # noqa: F401,F403 — every HTTP case, re-run here
from tests.test_cr187_native_auth import _office_adds_technician, _token, field  # noqa: F401
from tests.test_us_idn_helpers import idn  # noqa: F401

pytestmark = [pytest.mark.django_db, requires_postgres]

TABLES = ("native_tokens", "activation_codes")


def _seed_rows(field):
    _token()
    _office_adds_technician(field)


def test_identity_0011_tables_are_enabled_AND_forced(field):
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity "
            "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = 'public' AND c.relname = ANY(%s)",
            [list(TABLES)],
        )
        found = {name: (enabled, forced) for name, enabled, forced in cursor.fetchall()}
    assert found == {table: (True, True) for table in TABLES}


@pytest.mark.isolation
def test_identity_0011_nothing_is_visible_without_a_tenant(field, rls):
    _seed_rows(field)
    assert_denied_without_context(rls, *TABLES)


@pytest.mark.isolation
def test_identity_0011_one_utilitys_tokens_and_codes_are_invisible_to_another(field, rls):
    _seed_rows(field)
    for table in TABLES:
        assert_rls_scoped(rls, table, owner=field.silvercreek, intruder=field.bluemesa)


@pytest.mark.isolation
def test_identity_0011_a_row_stamped_for_another_tenant_is_refused(field, rls):
    _seed_rows(field)
    for table in TABLES:
        assert_write_into_other_tenant_refused(
            rls, table, owner=field.silvercreek, intruder=field.bluemesa
        )
