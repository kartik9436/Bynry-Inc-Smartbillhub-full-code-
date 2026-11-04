# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-639 (PO ruling 2026-08-24: "Change the security rule instead, in a
#           new step") · split out of DEF-622 as its unfixable half
# Rules:    CLAUDE.md hard rule 1 (tenant scoping; RLS FORCE is on; deny by
#           default) · B2 §3 RLS policy template · NFR-10 (isolation, zero
#           tolerance, release blocker)
# Tests:    06-backend/tests/test_def639_unset_tenant_denies.py (live Postgres,
#           non-superuser probe role) · the whole G5 isolation suite
# Impacts:  EVERY tenant-scoped table in the schema — this rewrites the USING and
#           WITH CHECK clause of every tenant-isolation policy in `public`.
# ───────────────────────────────────────────────────────
"""audit 0005 — an UNSET tenant marker must DENY, not ERROR (DEF-639).

HUMAN-OWNED (RLS policies are a CLAUDE.md rule-1 🔒 path).
HUMAN-REVIEW-PENDING — AI-authored 2026-08-24 under the PO ruling of 2026-08-09
("AI will do it; we will review it later as human"), implementing the PO's
2026-08-24 ruling on DEF-639 verbatim:

    "Change the security rule instead, in a new step"

Row owed in 12-governance/09-human-review-ledger.md; never RATIFIED without a
recorded human sign-off.

WHAT CHANGES, MECHANICALLY
--------------------------
Every tenant-isolation policy in the `public` schema reads

    USING      (tenant_id = current_setting('app.tenant_id')::uuid)
    WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid)

and becomes

    USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)

Three parts, each doing one job:
  * the `true` second argument makes an UNSET GUC return NULL instead of raising
    `unrecognized configuration parameter "app.tenant_id"`;
  * `NULLIF(…, '')` turns the CLEARED value — the empty string
    `core/tenancy.py::clear_current_tenant()` writes — into NULL instead of
    feeding `''` to a uuid cast that cannot parse it;
  * `tenant_id = NULL` evaluates to NULL, which is not TRUE, so the row is
    DENIED.

That is exactly the deny-by-default semantics CLAUDE.md hard rule 1 already
claims and every docstring in this repo already promises. Before this migration
the implementation did not match the claim: it ERRORED, and an error is not a
denial — it is a denial that also takes down whatever else was in the statement.

WHY IT HAD TO BE A SECURITY-RULE CHANGE AND NOT A MIGRATION FIX (DEF-639)
-------------------------------------------------------------------------
`assets.0003_meter_types_and_read_methods` poisons its OWN foreign-key
validation. In one migration it runs CreateModel (Django DEFERS the FK
constraints) → RunSQL enabling ENABLE + FORCE RLS on the new tables →
RunPython(seed) which ends `set_config('app.tenant_id','')` → migration exit,
where the deferred FKs are created AND VALIDATED. That validation scan runs
under FORCE RLS, the policy casts `current_setting('app.tenant_id')::uuid`, and
`''` is not a uuid:

    django.db.utils.DataError: invalid input syntax for type uuid: ""
    CONTEXT: SQL statement "SELECT fk."tenant_id" FROM ONLY "public"."meter_types" fk
             LEFT OUTER JOIN ONLY "public"."tenants" pk ON (…) WHERE pk."id" IS NULL …"

`metering.0016_br_met_101_common_area` and
`tenancy.0004_settings_families_logo_and_hosted_lists` are the same shape. The
violated dependency lives INSIDE one file, so no external sequencer can reach
between the parts — DEF-622's step-by-step runner applies 11 of 165 steps and
stops at step 12 on exactly this.

The PO was offered a three-line edit to those three committed migrations and
ruled for this instead, because it fixes the CLASS rather than the three
instances: the next migration anybody writes in that shape is safe too, and
`.github/workflows/migration-guard.yml` stays intact and correct because no
committed migration is edited.

MEASURED, 2026-08-24, PostgreSQL 16.13, app role `rolsuper=f rolbypassrls=f`,
no BYPASSRLS and no `--fake` anywhere: with every policy in the whole schema
carrying this form, the ENTIRE migration set applies to an empty database in one
plain `manage.py migrate` — 165 of 165, exit 0 — where the old form dies at 12.

WHY IT IS DYNAMIC (pg_policies) RATHER THAN A LIST OF POLICY NAMES
-------------------------------------------------------------------
There are 34 `CREATE POLICY` literals inline in 18 committed migration files,
125 more in the 28 `06-backend/db/rls_*.sql` files those migrations load at run
time, and one TEMPLATE in `core/rls.py` that mints a policy per `audit_log`
partition at a name — `audit_log_2031_03` — that nobody can write down in
advance. A hardcoded list of 34 would silently miss the other two thirds, and
DEF-524 in this repo is precisely what happens when a guard names a fixed target
and the target moves. So this reads `pg_policies` and rewrites everything that
actually carries the old predicate, whatever created it, and then RAISES if a
single occurrence survives — a migration that half-worked must not report
success.

WHY IT LIVES IN `audit`
-----------------------
It must run AFTER every migration that creates a policy, so it depends on the
leaf migration of all eleven apps that have one. `audit` is the host because
(a) it already owns the repo's other cross-cutting RLS migration,
    `audit.0003_rls_audit_partitions`, so there is one place to review this kind
    of change rather than two, and
(b) on 2026-08-24 four lanes are adding migrations to `customers`, `metering`,
    `tenancy` and `assets`; putting a new leaf in any of those four would create
    a conflicting-leaves clash in a shared working tree for no benefit, since
    the dependency list below fixes the ordering regardless of which app the
    file sits in.

⚠ WHAT THIS DOES **NOT** COVER — READ BEFORE WRITING A NEW POLICY
------------------------------------------------------------------
This runs ONCE, at one point in the graph. A policy created AFTER it — by a
later migration, or by `core/rls.py` minting a partition policy next month —
is NOT rewritten and carries the old, erroring form again.

    EVERY NEW POLICY MUST BE WRITTEN AS
        tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid

`tests/test_def639_unset_tenant_denies.py` sweeps `pg_policies` and goes RED on
the first policy that does not, which is the only thing that will notice.

And the residue this migration cannot reach, stated rather than buried
(hard-won law 1): the three self-poisoning migrations create THEIR policies
before this one runs, from text committed inside them. `assets.0003` reads
`db/rls_assets_w1.sql`, which is a data file and can be corrected; but
`tenancy.0004` holds its two policy literals INLINE, so a fresh-database apply
still stops there until that file is corrected under a migration-guard
exception (OQ-354's open half). Measured both ways on 2026-08-24 — see the
DEF-639 row in 12-governance/10-defect-log.csv.
"""

from django.db import migrations

from core.migrationtools import PostgresOnlySQL

#: The predicate as PostgreSQL stores and re-prints it (`pg_get_expr` normalises
#: `'app.tenant_id'` to `'app.tenant_id'::text`), and the deny-by-default form it
#: becomes. Text substitution on the STORED expression rather than a rewritten
#: policy body, so a policy that differs from the B2 §3 template in any other way
#: keeps that difference instead of being silently flattened into the template.
_OLD = "current_setting('app.tenant_id'::text)"
_NEW = "NULLIF(current_setting('app.tenant_id'::text, true), ''::text)"


def _rewrite_sql(old: str, new: str, *, expect_none_of: str) -> str:
    """One DO block that re-creates every policy carrying `old` with `new`.

    Recreates rather than edits because PostgreSQL has no `ALTER POLICY … USING`
    that can be driven from the stored text without re-stating it, and re-stating
    it is what this does. Name, permissive/restrictive class, command and role
    list are all carried across from `pg_policies` unchanged; only the two
    expressions move.
    """
    old_lit = old.replace("'", "''")
    new_lit = new.replace("'", "''")
    expect_lit = expect_none_of.replace("'", "''")
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
           AND (strpos(coalesce(qual, ''), '{old_lit}') > 0
             OR strpos(coalesce(with_check, ''), '{old_lit}') > 0)
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

    -- A migration that half-worked must not report success (hard-won law 7 in
    -- reverse: prove the guard can go RED, and let it).
    SELECT count(*) INTO leftover
      FROM pg_policies
     WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
       AND (strpos(coalesce(qual, ''), '{expect_lit}') > 0
         OR strpos(coalesce(with_check, ''), '{expect_lit}') > 0);
    IF leftover > 0 THEN
        RAISE EXCEPTION
            'DEF-639: % policy/policies still carry the old tenant predicate after the rewrite',
            leftover;
    END IF;

    RAISE NOTICE 'DEF-639: rewrote % tenant-isolation policies', rewritten;
END
$rls$;
"""


FORWARD = _rewrite_sql(_OLD, _NEW, expect_none_of=_OLD)
# The exact inverse, so `migrate audit 0004` restores the erroring predicate and
# the new test goes RED on demand — which is how this change was proved.
BACKWARD = _rewrite_sql(_NEW, _OLD, expect_none_of=_NEW)


class Migration(migrations.Migration):
    """Rewrites policy PREDICATES only. No model state changes, by design."""

    dependencies = [
        # The leaf of every app that owns a tenant-isolation policy, so this runs
        # after all of them. Adding an app here is how a future module joins the
        # rewrite; leaving one out is how a policy quietly keeps the old form.
        ("assets", "0008_cr028_allocation_share"),
        ("audit", "0004_archive_job_runs"),
        ("billing", "0023_cr029_bill_run_number"),
        ("customers", "0018_rls_cr031_service_requests"),
        ("identity", "0004_rls_security_policies"),
        ("ledger", "0008_supplier_invoices"),
        ("metering", "0023_cr029_drop_cycle_bill_date"),
        ("notifications", "0015_cr009_sender_config"),
        ("payments", "0010_rls_writeoffs_and_intents"),
        ("rating", "0022_br_rat_113_plan_tax_attachments"),
        ("tenancy", "0017_br_ast_048_mapping_templates"),
    ]

    operations = [
        # The list-of-tuples form is deliberate: a bare string is handed to
        # `prepare_sql_script`, which splits on `;` and would cut this DO block
        # into pieces. The tuple form passes it through as ONE statement with
        # params=None, so the `%I`/`%s` inside `format()` are never read as
        # placeholders either.
        PostgresOnlySQL(sql=[(FORWARD, None)], reverse_sql=[(BACKWARD, None)]),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-639 (PO ruling 2026-08-24) · DEF-622 · OQ-354
# generated: 2026-08-24 by the DEF-639 lane
# checklist: A✔ B=n/a(no API half) C✔ D=n/a E=n/a(no frontend half) F✔ G✔ H=PENDING(🔒 human review owed)
# gates: ruff✔ black✔ makemigrations --check✔ · G7 needs the review-ledger row
# exceptions: sqlite has no RLS — PostgresOnlySQL makes this a no-op there, and
#             the proof is the live-Postgres G5 suite, not the sqlite tier
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
