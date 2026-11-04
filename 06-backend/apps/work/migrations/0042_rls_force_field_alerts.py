"""work 0042 — RLS ENABLE + FORCE on `work_field_alerts`.

HUMAN-OWNED (RLS policies are a CLAUDE.md hard-rule-1 🔒 path).

HUMAN-REVIEW-PENDING — AI-authored 2026-10-21 (CR-187-BRC10 T-41, lane S-FIND)
under the PO ruling of 2026-08-09 (*"AI will do it; we will review it later as
human"*). The review-ledger row is owed by the coordinator (this lane may not
edit shared registers); not RATIFIED without a sign-off.

`work/0036`'s policy character for character — the `NULLIF` form (`DEF-639`),
deny-by-default without erroring on an unset GUC — and FORCE as well as ENABLE
because the migration role owns the table and ENABLE alone exempts the owner.
"""

from django.db import migrations

from core.migrationtools import PostgresOnlySQL

TENANT = "NULLIF(current_setting('app.tenant_id', true), '')::uuid"
TABLE = "work_field_alerts"

POLICY = f"""
ALTER TABLE {TABLE} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {TABLE} FORCE ROW LEVEL SECURITY;
CREATE POLICY {TABLE}_tenant_isolation ON {TABLE}
  USING      (tenant_id = {TENANT})
  WITH CHECK (tenant_id = {TENANT});
"""

REVERSE = f"""
DROP POLICY IF EXISTS {TABLE}_tenant_isolation ON {TABLE};
ALTER TABLE {TABLE} NO FORCE ROW LEVEL SECURITY;
ALTER TABLE {TABLE} DISABLE ROW LEVEL SECURITY;
"""


class Migration(migrations.Migration):
    dependencies = [("work", "0041_cr187_field_alerts")]

    operations = [PostgresOnlySQL(POLICY, reverse_sql=REVERSE)]
