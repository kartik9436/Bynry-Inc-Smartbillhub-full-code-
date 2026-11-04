# ── Trace ──────────────────────────────────────────────
# Change:   CR-038 W6 (2026-08-26) — sub-meters   Screens: S14 (PRM-02)
# Rules:    CLAUDE.md hard rule 1 (never touch a tenant table without
#           app.tenant_id; RLS FORCE is on) · B2 §3 policy template · DB-1 ·
#           NFR-10 (zero tolerance, release blocker) · BR-MET-125
# Tests:    06-backend/tests/test_cr038_w6_submeters_devices.py (the app-layer
#           scoping case; the live-Postgres probe rides the G5 isolation sweep)
# Impacts:  every query in apps/metering/submeter_reconciliation.py and the
#           premises report selector
# ───────────────────────────────────────────────────────
"""metering 0033 — RLS ENABLE+FORCE on `premises_submeter_reconciliations`.
HUMAN-OWNED (RLS policies are a CLAUDE.md rule-1 🔒 path).

HUMAN-REVIEW-PENDING — AI-authored 2026-08-26 under the PO ruling of 2026-08-09
("AI will do it; we will review it later as human"), applying the SIGNED B2 §3
policy template. A row in 12-governance/09-human-review-ledger.md is OWED for
this file; not RATIFIED without human sign-off.

⚠ **THE PREDICATE IS `NULLIF(current_setting('app.tenant_id', true), '')::uuid`
AND NOT B2 §3's LITERAL CAST — THIS IS `DEF-639`, NOT A DEVIATION.** The literal
form casts whatever the GUC holds straight to `uuid`, which denies by default
for the right reason but ALSO dies wherever Postgres evaluates the policy on its
own account — including inside `migrate`, where an FK validation scan under
FORCE RLS meets `''::uuid` and the whole database refuses to build
(`DataError: invalid input syntax for type uuid: ""`). `NULLIF(…, '')` makes the
empty string NULL, `NULL = tenant_id` is NULL, and a policy evaluating to NULL
admits NOTHING — the guarantee is identical and the cast can no longer raise.
Metering 0025 carries the full account.

    ALTER TABLE premises_submeter_reconciliations ENABLE ROW LEVEL SECURITY;
    ALTER TABLE premises_submeter_reconciliations FORCE ROW LEVEL SECURITY;
    CREATE POLICY premises_submeter_reconciliations_tenant_isolation
      ON premises_submeter_reconciliations
      USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
      WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

⚠ THE TABLE IS NOT PARTITIONED, so the `meter_reads` hazard metering 0004
documents at length — a partition queried DIRECTLY consults only its own
policies — does not arise here. Named rather than omitted, because it is
invisible until it is written down.

⚠ FOR THE REVIEWER — one hosting call, identical to the one metering 0004, 0015
and 0025, customers 0002, identity 0004 and tenancy 0004 each flagged: the
policy SQL is INLINE here rather than in `06-backend/db/`, because that
directory is outside this lane's stated territory. That is now SEVEN files
wanting the same relocation, as one edit, by whoever owns it.

Postgres only — `PostgresOnlySQL` skips honestly on the sqlite test database,
where RLS does not exist. The live proof is the G5 isolation suite (NFR-10,
zero tolerance, release blocker).
"""

from django.db import migrations

from core.migrationtools import PostgresOnlySQL

TABLE = "premises_submeter_reconciliations"

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
        ("metering", "0033_cr038_w6_submeter_reconciliation"),
    ]

    operations = [
        PostgresOnlySQL(
            sql=POLICY,
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-038 W6 (BR-MET-125 as ruled 2026-08-26)
# generated: 2026-08-26 by the CR-038 W6 lane (RLS half of the schema slice)
# checklist: A✔ B=deferred(policy-half only — the scoping TC asserts through the service) C✔ D=deferred(no-API-half — RLS migration) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09 — RLS 🔒 HUMAN-REVIEW-PENDING; the ledger row is REPORTED to the orchestrator)
# gates: makemigrations --check clean · ruff✔ black✔ · sqlite migrate applied (PostgresOnlySQL skips honestly)
# exceptions: DEF-639 predicate rather than B2 §3's literal cast (identical guarantee, see docstring) · policy SQL inline rather than in 06-backend/db/ (SEVENTH file to flag the same relocation — REPORTED, not resolved here) · LIVE POSTGRES PROOF NOT RUN IN THIS CONTAINER — the G5 isolation sweep is the gate and is REPORTED as owed for this table
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
