# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-RAT-9791 — production's Edit plan (ottumwa-water-works, 2.526.0)
#          listed BASE-SOL x20 as "Several base codes" and AFTER-HRS x13 on the
#          Charges step: `rating/plan_reads.py` read tenant tables with no
#          tenant filter and relied on RLS alone, which was not holding.
# Rules:   CLAUDE.md hard rule 1 · hard-won laws 7 and 14 · G143
# ───────────────────────────────────────────────────────
"""The plan read and the plan form's options show ONE utility's codes even when
row-level security is NOT holding — on a real PostgreSQL 16.

RLS is simulated as ineffective the way production lost it: the queries run
under `SET ROLE` to a NOSUPERUSER **BYPASSRLS** role, which PostgreSQL exempts
from every policy (FORCE included). Two utilities each hold `BASE-SOL` (a solar
base code) and `AFTER-HRS` (a non-base code). Reading as utility A must show
A's one of each — which can only be true if the QUERY names the tenant.

    DATABASE_URL=postgres://postgres@127.0.0.1:<port>/postgres JOBS_EAGER=false \\
        pytest tests/test_def_rat_9791_plan_reads_name_the_tenant_pg.py \\
        --ds=config.settings.pgtest --reuse-db

RED before the fix (plan_reads at c5732968e): `_base_block` answered
`state="ambiguous"` with `["BASE-SOL", "BASE-SOL"]` and form-options listed
AFTER-HRS twice. GREEN after.

SKIPS by name on SQLite, which has no RLS to bypass (law 7: a green run there
proves nothing). And the role check inside the test FAILS rather than skips if
the role does not actually bypass — otherwise a healthy RLS would make this
pass for the wrong reason.
"""

from contextlib import contextmanager
from datetime import date

import pytest
from django.db import DatabaseError, connection

from apps.rating import plan_reads
from tests.isolation_helpers import is_postgres, requires_postgres
from tests.test_us_rat_helpers import *  # noqa: F401,F403 — shared fixtures (env, other_env)
from tests.test_us_rat_helpers import tenant_ctx

pytestmark = [pytest.mark.django_db, requires_postgres]

BYPASS_ROLE = "sbh_rls_bypass_probe"


@pytest.fixture(scope="session")
def bypass_role(django_db_setup, django_db_blocker):
    """A NOLOGIN NOSUPERUSER BYPASSRLS role — RLS made ineffective on purpose."""
    if not is_postgres():
        pytest.skip("PostgreSQL only — SQLite has no row-level security to bypass")
    with django_db_blocker.unblock():
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "DO $$ BEGIN "
                    "  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = %s) THEN "
                    "    EXECUTE format('CREATE ROLE %%I NOLOGIN NOSUPERUSER BYPASSRLS', %s); "
                    "  END IF; "
                    "END $$",
                    [BYPASS_ROLE, BYPASS_ROLE],
                )
                cursor.execute(
                    "SELECT pg_has_role(current_user, %s, 'MEMBER')", [BYPASS_ROLE]
                )
                if not cursor.fetchone()[0]:
                    cursor.execute(f'GRANT "{BYPASS_ROLE}" TO CURRENT_USER')
                cursor.execute(f'GRANT USAGE ON SCHEMA public TO "{BYPASS_ROLE}"')
                cursor.execute(f'GRANT SELECT ON ALL TABLES IN SCHEMA public TO "{BYPASS_ROLE}"')
        except DatabaseError as exc:  # pragma: no cover — environment-dependent
            pytest.skip(f"could not create the BYPASSRLS probe role ({exc}); needs a superuser")
    return BYPASS_ROLE


@contextmanager
def rls_ineffective(role):
    with connection.cursor() as cursor:
        cursor.execute(f'SET ROLE "{role}"')
        cursor.execute(
            "SELECT current_user, rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user"
        )
        who, superuser, bypass = cursor.fetchone()
    # Not a skip: if this role obeyed RLS the test would pass for the wrong reason.
    assert (who, superuser, bypass) == (role, False, True)
    try:
        yield
    finally:
        with connection.cursor() as cursor:
            cursor.execute("RESET ROLE")


def _seed(rating_env):
    from apps.rating import services

    rating_env.enable("solar")
    with tenant_ctx(rating_env.tenant):
        services.create_charge(
            rating_env.admin,
            {
                "code": "BASE-SOL",
                "name": "Solar base",
                "service": "solar",
                "charge_type": "recurring",
                "amount_rule": "flat",
                "amount": "10.00",
                "is_base": True,
                "effective_from": "2000-01-01",
            },
        )
    rating_env.charge("AFTER-HRS", "After-hours call-out", charge_type="one_time", amount="75.00")


def test_plan_form_reads_show_only_this_utilitys_codes_when_rls_is_bypassed(
    env, other_env, bypass_role
):
    _seed(env)
    _seed(other_env)
    with tenant_ctx(env.tenant):
        with rls_ineffective(bypass_role):
            base = plan_reads._base_block("solar", None, [None], date(2026, 10, 6), {})
            options = plan_reads.form_options(on=date(2026, 10, 6))
    # The Edit plan's Solar section: ONE code, not "Several base codes".
    assert base["state"] != "ambiguous", base
    assert base["codes"] == ["BASE-SOL"]
    # The Charges step dropdown: AFTER-HRS once.
    codes = [row["ref"]["code"] for row in options["charge_codes"]]
    assert codes.count("AFTER-HRS") == 1, codes


def test_the_probe_really_bypasses(env, other_env, bypass_role):
    """The control: under the same role an UNFILTERED read sees both utilities'
    rows — so the test above is green because of the query, not because RLS
    happened to hold."""
    from apps.rating import models

    _seed(env)
    _seed(other_env)
    with tenant_ctx(env.tenant):
        with rls_ineffective(bypass_role):
            unfiltered = models.Charge.objects.filter(code="BASE-SOL").count()
    assert unfiltered == 2
