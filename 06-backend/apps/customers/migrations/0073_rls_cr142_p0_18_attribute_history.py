# ── Trace ──────────────────────────────────────────────
# Change:  CR-142-BRC07 `P0.18` — the Reports Build Brief §7.2.4, RULED
#          option (b): one effective-dated table on customers for class, type
#          and status.
# Rules:   CLAUDE.md hard rule 1 / DB-1 (RLS ENABLE + FORCE on every tenant
#          table) · B2 §3 (the signed policy template)
# ───────────────────────────────────────────────────────
"""customers 0073 — RLS ENABLE+FORCE on `account_attribute_history`.
HUMAN-OWNED (RLS policies are a CLAUDE.md rule-1 🔒 path).

HUMAN-REVIEW-PENDING — AI-authored 2026-09-26 under the PO ruling of 2026-08-09
("AI will do it; we will review it later as human"), applying the SIGNED B2 §3
policy template VERBATIM. Row in 12-governance/09-human-review-ledger.md; not
RATIFIED without human sign-off.

WHY THIS TABLE IS NOT EXEMPT, SAID PLAINLY. It holds one row per period per
ACCOUNT — whose account, what class, what status, and when each began. That is
a shape from which a reader could reconstruct another utility's customer base
and its churn. There is no reading on which it is less sensitive than
`accounts` itself, which has carried this policy since migration 0002.

⚠ **`FORCE` IS THE HALF THAT BINDS THE OWNER.** The application's migration
role owns every table in this schema, and PostgreSQL exempts a table's owner
from its own policies unless `FORCE` is set. `ENABLE` alone would make this
file decoration.

Postgres only — `PostgresOnlySQL` skips honestly on the SQLite test database,
where RLS does not exist and a probe therefore proves nothing (hard-won law 7's
*incapable of failing*). The live proof is
`06-backend/tests/test_cr142_p0_10_reports_rls_pg.py`, which this lane ran
against a real PostgreSQL 16 — see the lane report.
"""

from django.db import migrations

from core.migrationtools import PostgresOnlySQL

# B2 §3 template, verbatim.
POLICIES = """
ALTER TABLE account_attribute_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE account_attribute_history FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS account_attribute_history_tenant_isolation ON account_attribute_history;
CREATE POLICY account_attribute_history_tenant_isolation ON account_attribute_history
  USING      (tenant_id = current_setting('app.tenant_id')::uuid)
  WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid);
"""

REVERSE = """
DROP POLICY IF EXISTS account_attribute_history_tenant_isolation ON account_attribute_history;
ALTER TABLE account_attribute_history NO FORCE ROW LEVEL SECURITY;
ALTER TABLE account_attribute_history DISABLE ROW LEVEL SECURITY;
"""


class Migration(migrations.Migration):

    dependencies = [
        ("customers", "0072_cr142_p0_18_attribute_history"),
    ]

    operations = [PostgresOnlySQL(POLICIES, reverse_sql=REVERSE)]
