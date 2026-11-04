# ── Trace ──────────────────────────────────────────────
# Story:    CR-168-BRC10 round 2, lane SRV-1 — RLS on the three tables round 2
#           creates (work/0028, work/0029)
# Rules:    CLAUDE.md hard rule 1 (never touch a tenant table without
#           `app.tenant_id`; RLS FORCE is on) · B2 §3 · DEF-639 (the NULLIF
#           form) · CR-168-BRC10 §7.3 (row work/0030)
# Tests:    06-backend/tests/test_cr168_srv1_migrations_pg.py (reads
#           relrowsecurity AND relforcerowsecurity from pg_class, and proves a
#           cross-tenant read answers nothing as the non-superuser probe role)
# ───────────────────────────────────────────────────────
"""work 0030 — RLS ENABLE + FORCE on `work_hold_reasons`,
`work_order_rule_triggers` and `work_order_rule_escalation_fires`.

HUMAN-OWNED (RLS policies are a CLAUDE.md hard-rule-1 🔒 path).

HUMAN-REVIEW-PENDING — AI-authored 2026-10-04 under the PO ruling of 2026-08-09
(*"AI will do it; we will review it later as human"*). Row in
`12-governance/09-human-review-ledger.md`; not RATIFIED without a sign-off.

The policy is `work/0009`'s, character for character — the `NULLIF` form
(`DEF-639`), deny-by-default without erroring on an unset GUC — and FORCE as well
as ENABLE because the migration role owns the tables and ENABLE alone exempts
the owner. Nothing new is invented here; three tables join the set.
"""

from django.db import migrations

from core.migrationtools import PostgresOnlySQL

TENANT = "NULLIF(current_setting('app.tenant_id', true), '')::uuid"
TABLES = ("work_hold_reasons", "work_order_rule_triggers", "work_order_rule_escalation_fires")

POLICY = "\n".join(
    f"""
ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {table} FORCE ROW LEVEL SECURITY;
CREATE POLICY {table}_tenant_isolation ON {table}
  USING      (tenant_id = {TENANT})
  WITH CHECK (tenant_id = {TENANT});
"""
    for table in TABLES
)

REVERSE = "\n".join(
    f"""
DROP POLICY IF EXISTS {table}_tenant_isolation ON {table};
ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY;
ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;
"""
    for table in TABLES
)


class Migration(migrations.Migration):
    dependencies = [("work", "0029_cr168_rule_triggers_and_escalation_fires")]

    operations = [PostgresOnlySQL(POLICY, reverse_sql=REVERSE)]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-168-BRC10 §7.3 (row work/0030)
# generated: 2026-10-04 by CR-168 round 2 lane SRV-1
# checklist: A✔ B=n/a C=n/a D=n/a E=n/a F✔ G✔ H✔ (🔒 RLS → review-ledger row)
# gates: migrate up → down → up on PostgreSQL 16 · pg_class flags read back
# exceptions: none
# status: HUMAN-REVIEW-PENDING
# ──────────────────────────────────────────────────────────
