"""identity 0004 — RLS ENABLE+FORCE on security_policies.
HUMAN-OWNED (RLS policies are a CLAUDE.md rule-1 🔒 sensitive path).

HUMAN-REVIEW-PENDING — AI-authored 2026-08-09 under PO ruling 2026-08-09
("AI will do it; we will review it later as human"), applying the SIGNED B2
§3 policy template VERBATIM to the one new tenant-scoped table of the
EP-IDN lanes (`security_policies` — US-IDN-010 §5: "tenant-scoped, RLS +
FORCE, one row per tenant"). `sessions` is deliberately NOT here: US-IDN-003
§5 anchors it as a PLATFORM table (the row must be readable to ESTABLISH
tenant context) — RLS-exempt, tenant binding enforced by the auth layer and
probed by the G5 isolation suite.

Eng disposition (territory): the repo convention keeps policy SQL in
06-backend/db/*.sql; that path sits outside this story lane's territory, so
the template is carried inline below — flagged for relocation to
06-backend/db/ by the migrations lane at human review. Row per file in
12-governance/09-human-review-ledger.md; not RATIFIED without human sign-off.

Postgres only — sqlite cannot exercise RLS (G5 isolation suite owns the live
assertions, NFR-10 zero tolerance).
"""

from django.db import migrations

from core.migrationtools import PostgresOnlySQL

# B2 §3 template, verbatim per tenant-scoped table.
RLS_SECURITY_POLICIES_SQL = """
ALTER TABLE security_policies ENABLE ROW LEVEL SECURITY;
ALTER TABLE security_policies FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS security_policies_tenant_isolation ON security_policies;
CREATE POLICY security_policies_tenant_isolation ON security_policies
  USING      (tenant_id = current_setting('app.tenant_id')::uuid)
  WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid);
"""


class Migration(migrations.Migration):

    dependencies = [
        ("identity", "0003_sessions_security_policy_lockout"),
    ]

    operations = [
        PostgresOnlySQL(
            sql=RLS_SECURITY_POLICIES_SQL,
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
