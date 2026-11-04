# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-639 (PO ruling 2026-08-24: "Change the security rule instead, in
#           a new step") · DEF-622 · OQ-354
# Rules:    CLAUDE.md hard rule 1 (never touch a tenant table without
#           app.tenant_id; RLS FORCE is on; DENY by default) · B2 §3 policy
#           template · NFR-10 (isolation, zero tolerance, release blocker)
# Guards:   06-backend/apps/audit/migrations/0005_rls_deny_on_unset_tenant.py
# Note:     Live-Postgres only, and asserted under the NON-SUPERUSER probe role
#           `sbh_rls_probe` — superusers bypass RLS FORCE or not, so the same
#           assertions on the app's own connection would be vacuous.
# ───────────────────────────────────────────────────────
"""DEF-639 — an unset or cleared tenant marker DENIES; it no longer ERRORS.

WHAT CHANGED, AND WHY A TEST HAD TO CHANGE WITH IT
--------------------------------------------------
Until 2026-08-24 every tenant-isolation policy read

    tenant_id = current_setting('app.tenant_id')::uuid

so a session with no tenant context did not read zero rows — it RAISED, because
`''` is not a uuid (and an entirely unset GUC raised `unrecognized configuration
parameter` before that). Both outcomes deny, but an exception is not a denial:
it aborts whatever else was in the statement, and PostgreSQL evaluates the same
policy during a FOREIGN KEY validation scan, which is how three committed
migrations came to poison their own FK validation and block the first deploy
outright (DEF-622 / DEF-639).

The Product Owner ruled on 2026-08-24, verbatim:

    "Change the security rule instead, in a new step"

so the predicate is now

    tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid

`tenant_id = NULL` is NULL, NULL is not TRUE, the row is denied. This file is
the proof of that sentence and of its two edges: that the denial is real (zero
rows, under a role RLS applies to) and that it is not a widening (tenant A still
sees exactly tenant A).

WHAT WOULD MAKE THIS FILE LIE
-----------------------------
A green run under a role that bypasses RLS. The `rls` fixture re-reads
`pg_roles` every test and FAILS — never skips — if `sbh_rls_probe` turns out to
be a superuser or to hold BYPASSRLS, so the proof cannot quietly become a
formality. If the probe role cannot be created at all (no CREATEROLE, no
SUPERUSER), the fixture SKIPS with a reason that says the guarantee is UNPROVEN
in that environment. A skip here is not a pass.
"""

import uuid

import pytest
from django.db import DatabaseError, connection, transaction

from apps.tenancy.models import Uom

from tests.isolation_helpers import (  # noqa: F401 — fixtures used by name
    assert_no_foreign_rows_anywhere,
    assert_rls_scoped,
    clear_live_guc,
    current_guc,
    iso_tenants,
    live_tenant_context,
    requires_postgres,
    rls,
    rls_probe_role,
)

pytestmark = pytest.mark.isolation

#: The predicate as PostgreSQL re-prints it once the migration has run, and the
#: erroring one it replaced. Compared as substrings of `pg_policies.qual`.
DENY_FORM = "NULLIF(current_setting('app.tenant_id'::text, true), ''::text)"
ERROR_FORM = "current_setting('app.tenant_id'::text)"


def _two_tenants_with_a_row_each(alpha, beta):
    """One `uoms` row per tenant, written through the shipping kernel's GUC."""
    with live_tenant_context(alpha.id):
        mine = Uom.objects.create(tenant=alpha, code="kWh", name="Kilowatt hour")
    with live_tenant_context(beta.id):
        Uom.objects.create(tenant=beta, code="kgal", name="Thousand gallons")
    return mine


# ── the change itself ───────────────────────────────────────────────────────
@requires_postgres
@pytest.mark.django_db
def test_def639_tc1__a_cleared_session_reads_zero_rows_and_does_not_raise(rls, iso_tenants):
    """`app.tenant_id = ''` — the value the kernel writes when it clears context.

    This is the exact state that used to raise `invalid input syntax for type
    uuid: ""` in the middle of a foreign-key validation scan.
    """
    alpha, beta = iso_tenants
    _two_tenants_with_a_row_each(alpha, beta)

    clear_live_guc()
    assert current_guc() == "", "the shipping kernel did not clear app.tenant_id"

    assert rls.count("uoms") == 0, (
        "a session with NO tenant context read rows from a tenant table — "
        "deny-by-default (CLAUDE.md hard rule 1) is not in force"
    )


@requires_postgres
@pytest.mark.django_db
def test_def639_tc2__a_session_at_the_guc_default_also_reads_zero_rows(rls, iso_tenants):
    """The other 'no context' shape: never set on this session at all.

    Depending on how the database was provisioned, `RESET` lands either on the
    NO-TENANT sentinel (DEF-622 provisions the nil uuid on database and role) or
    on nothing at all. Both are 'nobody said which tenant', and both must read
    zero rows without raising — which is why the assertion is on the ROWS and
    the resolved value is only reported.
    """
    alpha, beta = iso_tenants
    _two_tenants_with_a_row_each(alpha, beta)

    with connection.cursor() as cursor:
        cursor.execute("RESET app.tenant_id")
    resolved = current_guc()

    assert rls.count("uoms") == 0, (
        f"a session at the app.tenant_id default ({resolved!r}) read rows from a "
        "tenant table — deny-by-default is not in force"
    )


@requires_postgres
@pytest.mark.django_db
def test_def639_tc3__an_unset_guc_yields_null_rather_than_raising(rls):
    """The half of the fix that `NULLIF` alone does not buy: the `true` argument.

    A GUC that was NEVER set is not empty — it is UNRECOGNISED, and the one-arg
    `current_setting` raises on it. Proved on a name nothing in this product
    ever sets, so the assertion cannot be satisfied by a provisioned default.
    """
    never_set = f"app.def639_probe_{uuid.uuid4().hex[:8]}"

    assert rls.scalar(
        f"SELECT NULLIF(current_setting('{never_set}', true), '')::uuid IS NULL"
    ), "the two-argument current_setting did not resolve an unset GUC to NULL"

    message = rls.refused(f"SELECT current_setting('{never_set}')::uuid")
    assert "unrecognized configuration parameter" in message, (
        "the one-argument form no longer raises on an unset GUC — the premise of "
        f"this whole change has moved: {message}"
    )


# ── and it is not a widening ────────────────────────────────────────────────
@requires_postgres
@pytest.mark.django_db
def test_def639_tc4__a_tenant_still_reads_only_its_own_rows(rls, iso_tenants):
    """Deny-on-unset must not have cost scoping-when-set. Both halves asserted."""
    alpha, beta = iso_tenants
    mine = _two_tenants_with_a_row_each(alpha, beta)

    assert_rls_scoped(rls, "uoms", owner=alpha, intruder=beta, owner_ids={str(mine.id)})
    assert_no_foreign_rows_anywhere(rls, alpha, ["uoms"])

    with live_tenant_context(beta.id):
        assert rls.count("uoms", "id = %s", [str(mine.id)]) == 0, (
            "id-guessing across the tenant boundary succeeded — the policy is "
            "matching more than it should"
        )


@requires_postgres
@pytest.mark.django_db
def test_def639_tc5__a_cleared_session_still_cannot_WRITE(rls, iso_tenants):
    """Reads go quiet; writes must stay LOUD.

    `WITH CHECK` evaluating to NULL is not TRUE, so an INSERT with no tenant
    context is REFUSED by the policy rather than accepted. Nothing about this
    change may turn a rejected write into a silent one.
    """
    alpha, _beta = iso_tenants
    clear_live_guc()

    message = rls.refused(
        "INSERT INTO uoms (id, tenant_id, code, name) VALUES (%s, %s, %s, %s)",
        [str(uuid.uuid4()), str(alpha.id), "therm", "Therm"],
    )
    assert (
        "row-level security" in message
    ), f"a write with no tenant context was not refused by the RLS policy — {message}"


# ── the drift guard: this is a CLASS fix, so it is asserted as a class ──────
@requires_postgres
@pytest.mark.django_db
def test_def639_tc6__every_policy_in_the_schema_carries_the_deny_on_unset_form(rls):
    """No policy anywhere may still cast the raw GUC.

    audit.0005 rewrites what exists WHEN IT RUNS. A policy created after it — a
    later migration, or `core/rls.py` minting an `audit_log` partition policy
    next month — is not rewritten, and this is the only thing in the repo that
    will notice. If this goes RED, the named policy was written as

        tenant_id = current_setting('app.tenant_id')::uuid

    and must be written as

        tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
    """
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT tablename, policyname, coalesce(qual, '') || ' ' || "
            "coalesce(with_check, '') FROM pg_policies WHERE schemaname = 'public' "
            "ORDER BY tablename, policyname"
        )
        policies = cursor.fetchall()

    tenant_policies = [row for row in policies if "app.tenant_id" in row[2]]
    assert len(tenant_policies) >= 50, (
        "expected the whole tenant-isolation policy set, found "
        f"{len(tenant_policies)} — this assertion would prove nothing"
    )

    stale = sorted(
        f"{table}.{policy}" for table, policy, expr in tenant_policies if ERROR_FORM in expr
    )
    assert not stale, (
        f"{len(stale)} policy/policies still cast the raw tenant GUC and will "
        f"ERROR instead of denying when it is unset or cleared: {stale}"
    )

    without_deny_form = sorted(
        f"{table}.{policy}" for table, policy, expr in tenant_policies if DENY_FORM not in expr
    )
    assert not without_deny_form, (
        "policy/policies reference app.tenant_id in some OTHER shape this guard "
        f"cannot vouch for: {without_deny_form}"
    )


@requires_postgres
@pytest.mark.django_db
def test_def639_tc7__the_probe_is_a_real_proof(rls, iso_tenants):
    """The canary. Everything above is vacuous if the probe role bypasses RLS.

    ⚠ **IT NO LONGER SKIPS ON A CORRECTLY-PROVISIONED CLUSTER (`OQ-GOV-12655`,
    decided 2026-10-02).** The contrast half used to need a BYPASSING app
    connection and `pytest.skip`ped without one — so the better the cluster,
    the redder `G5`, which fails on any skip and was therefore unable to report
    green at all on a NOSUPERUSER NOBYPASSRLS role. The contrast is now taken
    AGAINST THE POLICY ITSELF, which needs no bypassing role: one real row is
    written under a utility, the probe SEES it with that utility's context and
    sees NOTHING with the context cleared. That proves the zero is the policy
    speaking and not an empty table — the same thing the bypassing contrast
    proved — and it runs on either kind of role. Where the app role does
    bypass, the original contrast is still made as well.
    """
    rls.assert_is_a_real_proof()

    alpha, _beta = iso_tenants
    with live_tenant_context(alpha.id):
        row = Uom.objects.create(tenant=alpha, code="tc7", name="Canary unit")
        # With the owner's context the probe sees the row: the table is NOT empty.
        assert str(row.id) in rls.ids("uoms")

    # With the context cleared the SAME probe sees nothing: the policy did that.
    clear_live_guc()
    assert rls.count("uoms") == 0

    with connection.cursor() as cursor:
        cursor.execute("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user")
        app_super, app_bypass = cursor.fetchone()
    if app_super or app_bypass:
        # And where a bypassing connection exists, the original contrast too.
        with connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM uoms WHERE id = %s", [str(row.id)])
            assert cursor.fetchone()[0] == 1  # bypasses RLS: the row is there
        assert rls.count("uoms") == 0  # the probe is scoped by the policy


@requires_postgres
@pytest.mark.django_db
def test_def639_tc8__the_old_predicate_is_what_used_to_break_fk_validation(iso_tenants):
    """Why this mattered at all, asserted rather than narrated.

    Reproduces DEF-639's mechanism in miniature on a scratch table: FORCE RLS +
    the OLD predicate + a cleared session, and the foreign-key validation scan
    PostgreSQL runs when the constraint is added cannot cast `''`. The identical
    table under the NEW predicate validates cleanly. That pair is the whole
    ruling, on one table, in one test.

    It runs as the CONNECTED role rather than the probe — it has to issue DDL,
    which the probe role deliberately cannot — so it takes no `rls` fixture and
    is skipped, loudly, where that role bypasses RLS and the reproduction would
    be a no-op. On PostgreSQL 16 those are two DIFFERENT environments: the probe
    fixture needs a SUPERUSER connection to create its role at all, while this
    case needs a NON-superuser one, so the two halves of this file are proved by
    two runs against the same database.
    """
    alpha, _beta = iso_tenants
    with connection.cursor() as cursor:
        cursor.execute("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user")
        app_super, app_bypass = cursor.fetchone()
    if app_super or app_bypass:
        pytest.skip(
            "DEF-639's mechanism CANNOT BE REPRODUCED on this connection: the app "
            "role bypasses row-level security, so no policy is consulted during FK "
            "validation. Re-run against a NOSUPERUSER NOBYPASSRLS role (see "
            "10-scripts/13-provision-database.sh) before trusting a green result here."
        )

    def _scratch_table(predicate: str) -> str:
        name = f"def639_probe_{uuid.uuid4().hex[:8]}"
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE TABLE {name} (id uuid PRIMARY KEY, tenant_id uuid NOT NULL)")
            cursor.execute(
                f"INSERT INTO {name} VALUES (%s, %s)", [str(uuid.uuid4()), str(alpha.id)]
            )
            cursor.execute(f"ALTER TABLE {name} ENABLE ROW LEVEL SECURITY")
            cursor.execute(f"ALTER TABLE {name} FORCE ROW LEVEL SECURITY")
            cursor.execute(
                f"CREATE POLICY {name}_iso ON {name} "
                f"USING (tenant_id = {predicate}) WITH CHECK (tenant_id = {predicate})"
            )
        return name

    # (a) the OLD predicate — the defect, reproduced.
    with pytest.raises(DatabaseError) as excinfo:
        with transaction.atomic():
            old_table = _scratch_table("current_setting('app.tenant_id')::uuid")
            clear_live_guc()
            with connection.cursor() as cursor:
                cursor.execute(
                    f"ALTER TABLE {old_table} ADD CONSTRAINT {old_table}_fk "
                    "FOREIGN KEY (tenant_id) REFERENCES tenants(id)"
                )
    assert 'invalid input syntax for type uuid: ""' in str(excinfo.value), (
        "the OLD predicate no longer breaks FK validation — the defect this "
        f"change exists for has changed shape: {excinfo.value}"
    )

    # (b) the NEW predicate — the ruling, on the identical table.
    with transaction.atomic():
        new_table = _scratch_table("NULLIF(current_setting('app.tenant_id', true), '')::uuid")
        clear_live_guc()
        with connection.cursor() as cursor:
            cursor.execute(
                f"ALTER TABLE {new_table} ADD CONSTRAINT {new_table}_fk "
                "FOREIGN KEY (tenant_id) REFERENCES tenants(id)"
            )
