"""Tenant-isolation suite - RELEASE GATE, zero tolerance (CLAUDE.md rule #1).

For every API endpoint: authenticate as tenant A, attempt to read/write tenant B's
rows by id-guessing, filter tampering, and bulk endpoints. ANY leak = S1 defect.
Requires postgres (RLS untestable on sqlite); grows with each shipped endpoint.

This file holds the suite-wide proofs — the per-story cross-tenant cases live
next to their own TCs (tests/test_us_*.py, `@pytest.mark.isolation`). Read
tests/isolation_helpers.py first: it explains why these assertions run under a
dedicated NON-SUPERUSER role, and why a run that skipped that would be green
and worthless (superusers bypass RLS, FORCE or not).
"""

import pytest

from apps.rating import selectors as rating_selectors
from apps.tenancy.models import Uom
from core.pagination import ListParams

from tests.isolation_helpers import (  # noqa: F401 — fixtures used by name
    RLS_EXEMPT_TABLES,
    assert_denied_without_context,
    assert_rls_scoped,
    assert_write_into_other_tenant_refused,
    current_guc,
    iso_tenants,
    live_tenant_context,
    requires_postgres,
    rls,
    rls_enabled_tables,
    rls_probe_role,
)

pytestmark = pytest.mark.isolation


# ── the canary: without this, everything below could pass vacuously ─────────
@requires_postgres
@pytest.mark.django_db
def test_g5_canary__the_probe_role_does_not_bypass_rls(rls):
    """The proof-of-the-proof. FAILS (never skips) if the RLS half is a no-op.

    PostgreSQL exempts superusers and BYPASSRLS roles from row-level security
    even when the table carries FORCE. The app connects as a superuser in
    dev/CI, so this suite runs its RLS assertions under `sbh_rls_probe`
    instead — and re-checks, every run, that the swap really happened.
    """
    rls.assert_is_a_real_proof()  # rolsuper=false, rolbypassrls=false, SET ROLE took
    # And prove the distinction is not theoretical: the app's own role sees a
    # tenant table with no context set, the probe role cannot.
    from django.db import connection

    from tests.isolation_helpers import clear_live_guc

    clear_live_guc()
    with connection.cursor() as cursor:
        cursor.execute("SELECT rolsuper FROM pg_roles WHERE rolname = current_user")
        app_role_is_superuser = bool(cursor.fetchone()[0])
    if app_role_is_superuser:
        with connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM uoms")  # no GUC, no error: bypass
            assert cursor.fetchone()[0] is not None
    rls.denied_without_context("uoms")  # the probe role gets refused instead


# ── deny-by-default across the WHOLE schema (HR-1) ──────────────────────────
@requires_postgres
@pytest.mark.django_db
def test_g5_every_rls_table_denies_a_query_with_no_tenant_context(rls):
    """Manual probe (1), swept over every table the migrations protect.

    A table that answers a query with `app.tenant_id` unset is a table one
    forgotten `tenant_context` away from serving another tenant's rows.
    """
    tables = rls_enabled_tables()
    assert len(tables) >= 50, f"expected the W0+W1 RLS set, found {len(tables)}: {tables}"
    assert_denied_without_context(rls, *tables)


@requires_postgres
@pytest.mark.django_db
def test_g5_only_the_shipped_catalogue_tables_admit_a_tenantless_row(rls):
    """The other half of `DEF-REP-7823`'s fix, and the half that keeps it honest.

    The sweep above now holds a table whose policy READS `tenant_id IS NULL` to
    zero TENANT rows rather than zero rows, because the two reports catalogue
    tables ship platform rows every utility reads. That would let a policy that
    admits NULL BY ACCIDENT pass the sweep — so the set of tables whose policy
    admits NULL is pinned here to exactly the two `reports/0002` signed, and
    neither of them may WRITE one (`WITH CHECK` must not mention NULL, or any
    utility could plant a report every other utility reads).
    """
    from django.db import connection

    from tests.isolation_helpers import PLATFORM_ROW_TABLES

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT tablename, coalesce(qual, ''), coalesce(with_check, '') "
            "FROM pg_policies WHERE schemaname = 'public'"
        )
        policies = cursor.fetchall()
    admitting = {table for table, qual, _check in policies if "tenant_id IS NULL" in qual}
    assert admitting == set(PLATFORM_ROW_TABLES), (
        f"tables whose RLS policy READS tenantless rows: {sorted(admitting)}; the signed set is "
        f"{sorted(PLATFORM_ROW_TABLES)}. A new one is either a new platform catalogue (sign it "
        "and add it) or a policy one OR away from serving a row to every utility."
    )
    # A policy with no WITH CHECK applies its USING to writes too, so a USING
    # that admits NULL and no WITH CHECK is just as writable.
    writable = sorted(
        table for table, qual, check in policies
        if "tenant_id IS NULL" in check or (not check and "tenant_id IS NULL" in qual)
    )
    assert writable == [], f"a policy lets a tenant WRITE a tenantless row: {writable}"


@requires_postgres
@pytest.mark.django_db
def test_g5_the_rls_exempt_list_is_exactly_what_b2_declares(rls, iso_tenants):
    """The complement of the sweep: nothing tenant-scoped slipped out of RLS.

    B2 §3 names the platform tables that carry NO policy. Any OTHER table with
    a `tenant_id` column and no RLS is an isolation hole, so it is named here.
    """
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT c.relname FROM pg_class c "
            "JOIN pg_namespace n ON n.oid = c.relnamespace "
            "JOIN pg_attribute a ON a.attrelid = c.oid AND a.attname = 'tenant_id' "
            "WHERE n.nspname = 'public' AND c.relkind = 'r' AND NOT a.attisdropped "
            "AND NOT c.relrowsecurity "
            "AND c.relispartition IS FALSE "
            "ORDER BY c.relname"
        )
        unprotected = {row[0] for row in cursor.fetchall()}
    assert unprotected <= RLS_EXEMPT_TABLES, (
        "tenant-scoped table(s) with NO row-level security policy: "
        f"{sorted(unprotected - RLS_EXEMPT_TABLES)} — every one is a cross-tenant read away"
    )


# ── id-guessing: the docstring's own promise ────────────────────────────────
@requires_postgres
@pytest.mark.django_db
def test_cross_tenant_read_is_impossible(rls, iso_tenants):
    """Tenant A holds a row; tenant B knows its id and still cannot reach it.

    Both halves in one test: the app-layer selector filters it out, AND the
    database refuses it under a role RLS applies to (id-guessing is exactly the
    attack that survives a missing app filter).
    """
    alpha, beta = iso_tenants
    with live_tenant_context(alpha.id):
        secret = Uom.objects.create(tenant=alpha, code="kWh", name="Kilowatt hour")
    with live_tenant_context(beta.id):
        Uom.objects.create(tenant=beta, code="kgal", name="Thousand gallons")

    # (2) A's row exists under A, is gone under B — proven by the database.
    assert_rls_scoped(rls, "uoms", owner=alpha, intruder=beta, owner_ids={str(secret.id)})

    # id-guessing through the ORM under B's context finds nothing either.
    with live_tenant_context(beta.id):
        assert not Uom.objects.filter(tenant=beta, pk=secret.id).exists()
        assert rls.count("uoms", "id = %s", [str(secret.id)]) == 0

    # (4) B cannot write into A: the policy's WITH CHECK refuses the stamp.
    assert_write_into_other_tenant_refused(rls, "uoms", owner=beta, intruder=alpha)

    # (1) and with no context at all, neither tenant's rows are reachable.
    assert_denied_without_context(rls, "uoms")


@requires_postgres
@pytest.mark.django_db
def test_g5_filter_tampering_cannot_widen_a_tenant_scoped_list(rls, iso_tenants):
    """A forged filter naming another tenant's row still returns zero rows.

    The list kernel (BE-05/BR-SHL-011) is where a tampered query string lands;
    under RLS the row is not even a candidate.
    """
    alpha, beta = iso_tenants
    from apps.rating import models as rating_models

    with live_tenant_context(alpha.id):
        plan = rating_models.RatePlan.objects.create(
            tenant=alpha, name="Alpha Residential", code="A-RES", status="published"
        )
    with live_tenant_context(beta.id):
        rows = rating_selectors.plan_list(ListParams(sort="name", dir="asc", q="Alpha"))
        assert rows == []
        # …and the id-shaped filter the attacker would reach for next.
        assert rls.count("rate_plans", "id = %s", [str(plan.id)]) == 0
    assert_rls_scoped(rls, "rate_plans", owner=alpha, intruder=beta, owner_ids={str(plan.id)})


@requires_postgres
@pytest.mark.django_db
def test_g5_the_guc_never_outlives_the_context_that_set_it(rls, iso_tenants):
    """BE-01's finally-clause, on a real session: context in, context out.

    A pooled connection that kept the last request's `app.tenant_id` would hand
    the next caller another tenant's rows — so the cleared state must deny.
    """
    alpha, beta = iso_tenants
    with live_tenant_context(alpha.id):
        assert current_guc() == str(alpha.id)
        with live_tenant_context(beta.id):
            assert current_guc() == str(beta.id)
        # inner context restored nothing but the cleared state (BE-01 contract)
        assert current_guc() == ""
        rls.denied_without_context("uoms")
    assert current_guc() == ""
    rls.denied_without_context("uoms")
