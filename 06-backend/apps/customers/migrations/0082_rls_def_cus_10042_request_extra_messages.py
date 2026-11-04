"""customers 0082 — RLS ENABLE + FORCE on `service_request_extra_messages`.

HUMAN-OWNED (RLS policies are a CLAUDE.md rule-1 🔒 path).
HUMAN-REVIEW-PENDING — AI-authored 2026-10-11 under the PO ruling of 2026-08-09
(*"AI will do it; we will review it later as human"*). Row in
`12-governance/09-human-review-ledger.md`; not RATIFIED without a sign-off.

The same policy, word for word, as `0052` on `service_request_messages`, for the
same two reasons: hard rule 1 admits no tenant table without one, and each row
names a person applying to one utility and what they are being told.

⚠ **THE `NULLIF` FORM, per DEF-639** — deny-by-default without erroring on an
unset GUC. Postgres only — `PostgresOnlySQL` skips honestly on sqlite.
"""

from django.db import migrations

from core.migrationtools import PostgresOnlySQL

TABLE = "service_request_extra_messages"
TENANT = "NULLIF(current_setting('app.tenant_id', true), '')::uuid"

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
    dependencies = [("customers", "0081_def_cus_10042_request_extra_messages")]

    operations = [PostgresOnlySQL(POLICY, reverse_sql=REVERSE)]
