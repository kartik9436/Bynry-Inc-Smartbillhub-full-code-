"""customers 0046 — RLS ENABLE + FORCE on `account_unit_corrections`.
HUMAN-OWNED (RLS policies are a CLAUDE.md rule-1 🔒 path).

HUMAN-REVIEW-PENDING — AI-authored 2026-09-13 under the PO ruling of 2026-08-09
(*"AI will do it; we will review it later as human"*). Row in
`12-governance/09-human-review-ledger.md`; not RATIFIED without a sign-off.

WHY THIS TABLE NEEDS ONE LIKE EVERY OTHER, AND ONE REASON OF ITS OWN
─────────────────────────────────────────────────────────────────────────────
Every tenant table in this product is RLS FORCE-scoped and hard rule 1 admits
no exception, so the ordinary reason applies first: `account_unit_corrections`
carries `tenant_id`, and a query without `app.tenant_id` set must see nothing.

The reason of its own is what the rows SAY. Each one names two units and an
account, which is a statement about where a named utility's customers live —
and it names a member of staff, `approved_by`, which is a statement about who
works there and what they are trusted to sign. A tenant able to read another
tenant's corrections would learn both. `NFR`-level existence leakage (HR-1) is
enough on its own; this table leaks addresses-by-proxy and staff authority on
top of it.

⚠ **THE `NULLIF` FORM, per DEF-639** — deny-by-default without erroring on an
unset GUC. `NULLIF(current_setting('app.tenant_id', true), '')::uuid` returns
NULL rather than raising on a missing parameter, and `tenant_id = NULL` is NULL,
which is not TRUE, so no row is visible and no row may be written.

Postgres only — `PostgresOnlySQL` skips honestly on the sqlite test database,
where RLS does not exist. The G5 isolation suite proves the policy under a
NON-SUPERUSER probe role, because the app connects as a superuser and
superusers bypass RLS unconditionally (`tests/isolation_helpers.py`).
"""

from django.db import migrations

from core.migrationtools import PostgresOnlySQL

TABLE = "account_unit_corrections"

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
    dependencies = [("customers", "0045_br_cus_1047_unit_correction")]

    operations = [PostgresOnlySQL(POLICY, reverse_sql=REVERSE)]
