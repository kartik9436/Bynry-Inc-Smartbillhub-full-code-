# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-PAY-4054 — four payments tables kept the pre-DEF-639 policy form
# Rules:   CLAUDE.md hard rule 1 (tenant scoping; RLS FORCE is on; deny by
#          default) · B2 §3 RLS policy template · DEF-639 (PO ruling 2026-08-24,
#          "Change the security rule instead, in a new step")
# Tests:   tests/test_def639_unset_tenant_denies.py::test_def639_tc6 ·
#          tests/test_tenant_isolation.py::test_g5_every_rls_table_denies_a_query_with_no_tenant_context
# Impacts: payment_import_batches · payment_import_rows · payment_webhook_events
#          · stored_payment_instruments — USING and WITH CHECK on each.
# ───────────────────────────────────────────────────────
"""payments 0025 — the four policies audit/0005 could not reach (DEF-PAY-4054).

HUMAN-OWNED (RLS policies are a CLAUDE.md rule-1 🔒 path).
HUMAN-REVIEW-PENDING — AI-authored 2026-09-05 under the PO ruling of 2026-08-09
("AI will do it; we will review it later as human"). Row owed in
12-governance/09-human-review-ledger.md; never RATIFIED without a recorded
human sign-off.

WHAT WAS WRONG
--------------
`audit.0005_rls_deny_on_unset_tenant` swept every policy in the schema on
2026-08-24 into the deny-by-default form. Its docstring then said, in capitals,
that a policy created AFTER it is not rewritten and that every new policy must
be written as

    tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid

Three migrations written after that date did not:

    payments/0020_cr060_c21_webhook_events        (CR-060, payment_webhook_events)
    payments/0023_cr059_cs2_payment_import        (CR-059, payment_import_batches,
                                                   payment_import_rows)
    payments/0024_cr068_p2_stored_payment_instrument (CR-068, stored_payment_instruments)

all four carrying `tenant_id = current_setting('app.tenant_id', true)::uuid`.

WHAT THAT COSTS — AND WHAT IT DOES *NOT*
-----------------------------------------
It is **not** a leak and never was. The predicate is still `tenant_id = <the
GUC>`, so with a context set the rows are scoped correctly, and with no context
ever set `current_setting(…, true)` is NULL, `tenant_id = NULL` is NULL, and the
row is denied. Nothing of one tenant's has ever been reachable from another's.

What is wrong is the SHAPE OF THE REFUSAL. `core/tenancy.py::clear_current_tenant`
writes the EMPTY STRING, not an unset GUC, and `''::uuid` cannot be parsed — so
on these four tables a read taken with context cleared RAISES

    invalid input syntax for type uuid: ""

instead of quietly returning zero rows. An error is not a denial; it is a denial
that also takes down whatever else was in the statement. Concretely, the same
policy is evaluated during FOREIGN KEY VALIDATION, which is how the old form
stopped a fresh database at step 12 of 168 and is the whole reason DEF-639 was
ruled the way it was.

WHY IT SURVIVED NINE DAYS AND THREE LANES
------------------------------------------
The guard existed and could not fire. `tests/test_def639_unset_tenant_denies.py`
sweeps `pg_policies` and goes red on the first policy in the old form — and it
is `@requires_postgres`, while G5 ran `pytest -m isolation` with no settings
override and so ran on the in-memory SQLite pinned in `pyproject.toml`, where it
skipped. G5 reported PASS over all three (DEF-GOV-4024). A warning in a docstring
plus a guard that cannot execute is hard-won law 1: a comment claiming a
guarantee is not the guarantee.

WHY THIS IS A DYNAMIC SWEEP AND NOT FOUR `CREATE POLICY` LITERALS
------------------------------------------------------------------
Same reasoning as `audit.0005`, and DEF-524 in this repo is what happens when a
guard names a fixed target and the target moves: this reads `pg_policies`,
rewrites whatever actually carries the old predicate, and RAISES if a single
occurrence survives, so a migration that half-worked cannot report success.

⚠ **THE ONE TRAP IN WRITING IT, STATED SO THE NEXT READER DOES NOT RE-LEARN IT.**
The CORRECT form *contains* the broken form as a substring —
`NULLIF(current_setting('app.tenant_id'::text, true), ''::text)` — so a plain
`replace()` over every policy would DOUBLE-WRAP the 262 already-correct policies
into `NULLIF(NULLIF(…))`. The `strpos(…, 'NULLIF') = 0` guard in the WHERE clause
below is what makes this safe, and it is load-bearing rather than defensive.

⚠ **AND WHAT THIS STILL DOES NOT COVER**, for the same reason `audit.0005` did
not: it runs ONCE, at one point in the graph. A policy created after it carries
whatever its author wrote. The thing that will notice is the isolation suite —
now that it is actually run against a role RLS applies to, and recorded in
`12-governance/isolation-receipt.json`.
"""

from django.db import migrations

from core.migrationtools import PostgresOnlySQL

#: The predicate as PostgreSQL stores and re-prints it (`pg_get_expr` normalises
#: `'app.tenant_id'` to `'app.tenant_id'::text`), and the deny-by-default form it
#: must become. Text substitution on the STORED expression, so a policy that
#: differs from the B2 §3 template in any other way keeps that difference.
_OLD = "current_setting('app.tenant_id'::text, true)"
_NEW = "NULLIF(current_setting('app.tenant_id'::text, true), ''::text)"


def _rewrite_sql(old: str, new: str) -> str:
    """One DO block that re-creates every OLD-FORM policy in the NEW form.

    Recreates rather than edits because PostgreSQL has no
    `ALTER POLICY … USING` drivable from the stored text without re-stating it.
    Name, permissive/restrictive class, command and role list are all carried
    across from `pg_policies` unchanged; only the two expressions move.
    """
    old_lit = old.replace("'", "''")
    new_lit = new.replace("'", "''")
    return f"""
DO $rls$
DECLARE
    r          record;
    new_qual   text;
    new_check  text;
    role_list  text;
    stmt       text;
    rewritten  int := 0;
    leftover   int := 0;
BEGIN
    FOR r IN
        SELECT schemaname, tablename, policyname, permissive, roles, cmd, qual, with_check
          FROM pg_policies
         WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
           -- carries the old predicate ...
           AND (strpos(coalesce(qual, ''), '{old_lit}') > 0
             OR strpos(coalesce(with_check, ''), '{old_lit}') > 0)
           -- ... and is not ALREADY the new one. The new form CONTAINS the old
           -- as a substring, so without this the 262 correct policies would be
           -- double-wrapped into NULLIF(NULLIF(...)).
           AND strpos(coalesce(qual, ''), 'NULLIF') = 0
           AND strpos(coalesce(with_check, ''), 'NULLIF') = 0
    LOOP
        new_qual  := replace(r.qual, '{old_lit}', '{new_lit}');
        new_check := replace(r.with_check, '{old_lit}', '{new_lit}');

        SELECT string_agg(CASE WHEN role_name = 'public'
                               THEN 'PUBLIC'
                               ELSE quote_ident(role_name) END, ', ')
          INTO role_list
          FROM unnest(r.roles::text[]) AS role_name;

        stmt := format('CREATE POLICY %I ON %I.%I AS %s FOR %s TO %s',
                       r.policyname, r.schemaname, r.tablename,
                       CASE WHEN r.permissive = 'RESTRICTIVE'
                            THEN 'RESTRICTIVE' ELSE 'PERMISSIVE' END,
                       r.cmd, role_list);
        IF new_qual IS NOT NULL THEN
            stmt := stmt || format(' USING (%s)', new_qual);
        END IF;
        IF new_check IS NOT NULL THEN
            stmt := stmt || format(' WITH CHECK (%s)', new_check);
        END IF;

        EXECUTE format('DROP POLICY %I ON %I.%I', r.policyname, r.schemaname, r.tablename);
        EXECUTE stmt;
        rewritten := rewritten + 1;
    END LOOP;

    -- A migration that half-worked must not report success.
    SELECT count(*) INTO leftover
      FROM pg_policies
     WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
       AND (strpos(coalesce(qual, ''), '{old_lit}') > 0
         OR strpos(coalesce(with_check, ''), '{old_lit}') > 0)
       AND strpos(coalesce(qual, ''), 'NULLIF') = 0
       AND strpos(coalesce(with_check, ''), 'NULLIF') = 0;

    IF leftover > 0 THEN
        RAISE EXCEPTION
            'DEF-PAY-4054: % policy/policies still carry the erroring form after rewriting %',
            leftover, rewritten;
    END IF;

    RAISE NOTICE 'DEF-PAY-4054: rewrote % policy/policies into the deny-on-unset form', rewritten;
END
$rls$;
"""


class Migration(migrations.Migration):

    dependencies = [
        # After the three migrations that created the four policies …
        ("payments", "0024_cr068_p2_stored_payment_instrument"),
        # … and after the original schema-wide sweep, so this is unambiguously
        # the second pass rather than a race with the first.
        ("audit", "0005_rls_deny_on_unset_tenant"),
    ]

    operations = [
        PostgresOnlySQL(
            _rewrite_sql(_OLD, _NEW),
            # Deliberately irreversible in the unsafe direction: putting the
            # erroring cast back would re-introduce a defect, and hard-won law 3
            # says the unsafe option must be the one you type.
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
