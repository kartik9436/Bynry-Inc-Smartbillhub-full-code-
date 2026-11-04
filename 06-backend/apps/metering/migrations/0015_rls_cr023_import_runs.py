# ── Trace ──────────────────────────────────────────────
# Story:    US-MET-004 (CR-023 P3 — the recorded import path supersedes the
#           stateless one, design B15 §7A)   Screens: PRM-04, WFL-01.premises.1–5
# Rules:    CLAUDE.md hard rule 1 (never touch a tenant table without
#           app.tenant_id; RLS FORCE is on) · B2 §3 policy template · DB-1 ·
#           NFR-10 (zero tolerance, release blocker) · BR-MET-090 (a run's
#           stored rule results are the tenant's own history)
# Tests:    06-backend/tests/test_cr023_import_stages.py (TC-23 tenant scoping;
#           the live-Postgres probe rides the G5 isolation sweep)
# Impacts:  every query in apps/metering/import_runs.py + import_rules.py
# ───────────────────────────────────────────────────────
"""metering 0015 — RLS ENABLE+FORCE on the five CR-023 import tables.
HUMAN-OWNED (RLS policies are a CLAUDE.md rule-1 🔒 path).

HUMAN-REVIEW-PENDING — AI-authored 2026-08-21 under the PO ruling of 2026-08-09
("AI will do it; we will review it later as human"), applying the SIGNED B2 §3
policy template VERBATIM, once per table. Row per file in
12-governance/09-human-review-ledger.md; not RATIFIED without human sign-off.

The B2 §3 template, repeated per tenant-scoped table — deny-by-default: with
`app.tenant_id` unset the `::uuid` cast of '' fails and NO row is visible:

    ALTER TABLE <t> ENABLE ROW LEVEL SECURITY;
    ALTER TABLE <t> FORCE ROW LEVEL SECURITY;    -- applies even to the owner
    CREATE POLICY <t>_tenant_isolation ON <t>
      USING      (tenant_id = current_setting('app.tenant_id')::uuid)
      WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid);

FIVE TABLES, AND EVERY ONE OF THEM CARRIES `tenant_id` EVEN WHERE THE DESIGN'S
ER DIAGRAM DOES NOT DRAW ONE. B15 §5 shows `import_rule_results` and
`rollback_points` hanging off the run with no tenant column of their own, and
that shape would be a rule-1 violation the moment anything queried them by
`run_id` alone: RLS is enforced per TABLE, so a child table with no `tenant_id`
has no policy to enforce and is readable across tenants by anyone who knows a
uuid. `read_import_rows` carries `tenant_id` beside its `batch_id` for exactly
this reason, and these follow it. **The diagram is a picture of relationships;
the policy is the guarantee.**

NONE OF THESE TABLES IS PARTITIONED, so the `meter_reads` hazard that 0004
documents at length — a partition queried DIRECTLY consults only its own
policies, and a partition created by `CREATE TABLE … PARTITION OF` has RLS
DISABLED — does not arise here. It is named rather than omitted because the
next lane to add a table in this module will read this file, and the trap is
invisible until it is written down.

⚠ FOR THE REVIEWER — one hosting call, identical to the one metering 0004,
customers 0002, identity 0004 and tenancy 0004 each flagged: the policy SQL is
INLINE here rather than in 06-backend/db/rls_metering_cr023_imports.sql, because
06-backend/db/ is outside this lane's stated territory. That is now FIVE files
wanting the same relocation, as one edit, by whoever owns that directory.

Postgres only — `PostgresOnlySQL` skips honestly on the sqlite test database,
where RLS does not exist. The live proofs are the G5 isolation suite (NFR-10,
zero tolerance, release blocker).
"""

from django.db import migrations

from core.migrationtools import PostgresOnlySQL

#: B2 §3 template, verbatim, one block per CR-023 tenant-scoped table.
POLICIES = "\n".join(
    f"""
ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {table} FORCE ROW LEVEL SECURITY;
CREATE POLICY {table}_tenant_isolation ON {table}
  USING      (tenant_id = current_setting('app.tenant_id')::uuid)
  WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid);
"""
    for table in (
        "import_runs",
        "import_run_rows",
        "import_rules",
        "import_rule_results",
        "rollback_points",
    )
)


class Migration(migrations.Migration):

    dependencies = [
        ("metering", "0014_cr023_import_runs"),
    ]

    operations = [
        PostgresOnlySQL(
            sql=POLICIES,
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-MET-004@8bf4be8 (CR-023 P3 — design B15 §13 tables; §7A supersession)
# generated: 2026-08-21 by the CR-023 P3/P4 lane (RLS half of the schema slice)
# checklist: A✔ B=deferred(policy-half only — TC-23 asserts scoping through the service) C✔ D=deferred(no-API-half — RLS migration) E=deferred(no-frontend-half — PRM-04 is another lane) F✔ G✔ H=deferred(PO 2026-08-09 — RLS 🔒 HUMAN-REVIEW-PENDING, ledger row appended)
# gates: makemigrations --check clean · sqlite migrate applied (PostgresOnlySQL skips honestly) · ruff✔ black✔ · run_gates no new failure
# exceptions: policy SQL inline rather than in 06-backend/db/ (fifth file to flag the same relocation — REPORTED, not resolved here) · every table carries tenant_id even where B15 §5's ER diagram draws none, because RLS is enforced per table and a child with no tenant column has no policy — REPORTED as a design-doc correction
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
