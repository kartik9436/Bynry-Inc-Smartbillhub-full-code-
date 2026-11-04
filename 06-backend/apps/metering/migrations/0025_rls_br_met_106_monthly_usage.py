# ── Trace ──────────────────────────────────────────────
# Change:   CR-030 W3 task 3.8 (the ACC-01 Usage tab)   Screens: S21 (Usage)
# Rules:    CLAUDE.md hard rule 1 (never touch a tenant table without
#           app.tenant_id; RLS FORCE is on) · B2 §3 policy template · DB-1 ·
#           NFR-10 (zero tolerance, release blocker) · BR-MET-106 (a tenant's
#           own stored months)
# Tests:    06-backend/tests/test_br_met_106_monthly_usage.py (the app-layer
#           scoping cases; the live-Postgres probe rides the G5 isolation sweep)
# Impacts:  every query in apps/metering/monthly_usage_service.py +
#           apps/metering/monthly_usage_reads.py
# ───────────────────────────────────────────────────────
"""metering 0025 — RLS ENABLE+FORCE on `meter_read_monthly_usage`.
HUMAN-OWNED (RLS policies are a CLAUDE.md rule-1 🔒 path).

HUMAN-REVIEW-PENDING — AI-authored 2026-08-24 under the PO ruling of 2026-08-09
("AI will do it; we will review it later as human"), applying the SIGNED B2 §3
policy template. Row per file in 12-governance/09-human-review-ledger.md; not
RATIFIED without human sign-off.

⚠ **THE PREDICATE IS `NULLIF(current_setting('app.tenant_id', true), '')::uuid`
AND NOT THE `current_setting('app.tenant_id')::uuid` OF THE OTHER 34 POLICIES —
THIS IS `DEF-639`, NOT A DEVIATION FROM THE TEMPLATE.**

The literal B2 §3 form casts whatever the GUC holds straight to `uuid`, and it
denies by default for the right reason: with `app.tenant_id` unset the cast of
`''` FAILS, so no row is visible. What it also does is fail everywhere ELSE the
database evaluates the policy on its own account — and one of those places is
inside `migrate`. `assets.0003_meter_types_and_read_methods` creates tables,
enables FORCE RLS on them, seeds them with a `RunPython` that ends by setting
`app.tenant_id` to `''`, and then exits — at which point Postgres validates the
FK constraints Django deferred, that scan runs under FORCE RLS, the policy casts
`''::uuid`, and the migration dies with

    DataError: invalid input syntax for type uuid: ""
    CONTEXT: SQL statement "SELECT fk."tenant_id" FROM ONLY "public"."meter_types" …

A fresh database cannot be built. This lane MET that failure in this container
while trying to run the isolation suite, which is why it is quoted rather than
described.

`NULLIF(…, '')` makes the empty string a NULL, `NULL = tenant_id` is NULL, and a
policy that evaluates to NULL admits NOTHING — so the deny-by-default guarantee
is IDENTICAL and the cast can no longer raise. The `true` second argument to
`current_setting` makes a MISSING parameter answer NULL instead of erroring,
which is the same defect one step earlier (the `unrecognized configuration
parameter "app.tenant_id"` half of OQ-354).

    ALTER TABLE meter_read_monthly_usage ENABLE ROW LEVEL SECURITY;
    ALTER TABLE meter_read_monthly_usage FORCE ROW LEVEL SECURITY;  -- owner too
    CREATE POLICY meter_read_monthly_usage_tenant_isolation
      ON meter_read_monthly_usage
      USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
      WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

⚠ THE TABLE IS NOT PARTITIONED, so the `meter_reads` hazard metering 0004
documents at length — a partition queried DIRECTLY consults only its own
policies, and `CREATE TABLE … PARTITION OF` creates it with RLS DISABLED — does
not arise here. Named rather than omitted, because it is invisible until it is
written down.

⚠ FOR THE REVIEWER — one hosting call, identical to the one metering 0004,
metering 0015, customers 0002, identity 0004 and tenancy 0004 each flagged: the
policy SQL is INLINE here rather than in `06-backend/db/`, because that
directory is outside this lane's stated territory. That is now SIX files wanting
the same relocation, as one edit, by whoever owns it.

Postgres only — `PostgresOnlySQL` skips honestly on the sqlite test database,
where RLS does not exist. The live proof is the G5 isolation suite (NFR-10, zero
tolerance, release blocker).
"""

from django.db import migrations

from core.migrationtools import PostgresOnlySQL

TABLE = "meter_read_monthly_usage"

#: B2 §3 template with DEF-639's cast repair — see the docstring.
PREDICATE = "tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid"

POLICY = f"""
ALTER TABLE {TABLE} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {TABLE} FORCE ROW LEVEL SECURITY;
CREATE POLICY {TABLE}_tenant_isolation ON {TABLE}
  USING      ({PREDICATE})
  WITH CHECK ({PREDICATE});
"""


class Migration(migrations.Migration):

    dependencies = [
        ("metering", "0024_br_met_106_monthly_usage"),
    ]

    operations = [
        PostgresOnlySQL(
            sql=POLICY,
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CUS-011@a1fbf3f (the S21 operational tabs — Usage is the first of
#         the five; BR-MET-106 snapshot 2026-08-24)
# generated: 2026-08-24 by the CR-030 W3 task 3.8 lane (RLS half of the schema slice)
# checklist: A✔ B=deferred(policy-half only — the scoping TCs assert through the service) C✔ D=deferred(no-API-half — RLS migration) E=deferred(no-frontend-half — the Usage tab is the same lane's separate file) F✔ G✔ H=deferred(PO 2026-08-09 — RLS 🔒 HUMAN-REVIEW-PENDING; the ledger row is written to this lane's scratchpad because 12-governance/09-human-review-ledger.md is another lane's file today, and is REPORTED for the orchestrator to land)
# gates: makemigrations --check clean · ruff✔ black✔ · sqlite migrate applied (PostgresOnlySQL skips honestly) · LIVE POSTGRES RLS PROOF RUN AND GREEN — tests/test_br_met_106_monthly_usage.py::test_br_met_106_tc9b under `sbh_rls_probe` (NOLOGIN NOSUPERUSER NOBYPASSRLS): scoped ✔, deny-with-no-context ✔, WITH CHECK refusal ✔. Proven RED first by DISABLE ROW LEVEL SECURITY (`LEAK — tenant <lonestar> can read tenant <brazos>'s rows`), green again on ENABLE+FORCE. ⚠ The database had to be CLONED from an already-migrated one: a fresh `migrate` in this container dies inside assets.0003 with DEF-639's `invalid input syntax for type uuid: ""`
# exceptions: the policy predicate is DEF-639's `NULLIF(current_setting('app.tenant_id', true), '')::uuid` rather than B2 §3's literal cast — the deny-by-default guarantee is identical and the cast can no longer poison an FK validation scan (lane L1 is rewriting the other 34 policies to the same form) · policy SQL inline rather than in 06-backend/db/ (sixth file to flag the same relocation — REPORTED, not resolved here)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
