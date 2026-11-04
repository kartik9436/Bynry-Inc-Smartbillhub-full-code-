# ── Trace ──────────────────────────────────────────────
# Task:     Bulk bill run build plan DB1 — "tenant-scoped, RLS FORCE"
# Tests:    tests/test_bbr_check_store.py (policy reached the cluster, on
#           PostgreSQL) · 10-scripts/bbr_check_engine_pg_proof.py
# ───────────────────────────────────────────────────────
"""billing 0033 — tenant isolation for the three Check-store tables.

HUMAN-OWNED (RLS policies are a CLAUDE.md 🔒 path). HUMAN-REVIEW-PENDING —
AI-authored 2026-09-30 under the PO ruling of 2026-08-09. Row in
12-governance/09-human-review-ledger.md.

A findings row names a customer's account and why it cannot be billed yet; it
is one tenant's operating position. The policy is the `NULLIF` form `0027`
argues for (deny-by-default WITHOUT erroring on an unset setting) — copied
from `0027`, never from a pre-`DEF-639` neighbour.

Postgres only — `PostgresOnlySQL` skips honestly on the sqlite test database,
where RLS does not exist.
"""

from django.db import migrations

from core.migrationtools import PostgresOnlySQL

TABLES = ("bill_run_account_checks", "bill_run_findings", "bill_run_standing_answers")
TENANT = "NULLIF(current_setting('app.tenant_id', true), '')::uuid"

POLICY = "".join(f"""
ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {table} FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS {table}_tenant_isolation ON {table};
CREATE POLICY {table}_tenant_isolation ON {table}
  USING      (tenant_id = {TENANT})
  WITH CHECK (tenant_id = {TENANT});
""" for table in TABLES)

REVERSE = "".join(f"""
DROP POLICY IF EXISTS {table}_tenant_isolation ON {table};
ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY;
ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;
""" for table in TABLES)


class Migration(migrations.Migration):
    dependencies = [
        ("billing", "0032_bbr_check_store"),
    ]

    operations = [PostgresOnlySQL(POLICY, reverse_sql=REVERSE)]
