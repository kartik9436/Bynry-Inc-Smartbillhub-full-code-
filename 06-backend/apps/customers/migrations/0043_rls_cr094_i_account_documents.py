"""customers 0043 — RLS ENABLE + FORCE on `account_documents`.
HUMAN-OWNED (RLS policies are a CLAUDE.md rule-1 🔒 path).

HUMAN-REVIEW-PENDING — AI-authored 2026-09-12 under the PO ruling of 2026-08-09
(*"AI will do it; we will review it later as human"*). Row in
`12-governance/09-human-review-ledger.md`; not RATIFIED without a sign-off.

WHY IT NEEDS ONE, AND THIS TABLE IS THE SHARP CASE
───────────────────────────────────────────────────
`account_documents` is the INDEX to a filing cabinet of scanned identity
documents, signed leases and bank letters. **It is also the only thing standing
between a tenant and another tenant's files**, and that is not rhetoric — it is
the design `tenancy/document_models.py` states in its own words:

    *"TENANT SEPARATION IS THIS ROW. IT IS NOT THE KEY PREFIX. … What actually
    prevents a cross-tenant read is that the only way to learn a key is to read
    a row of this table, and this table is RLS FORCE-scoped."*

That sentence is about `stored_documents`, and `account_documents` is now a
SECOND table that can lead to the same bytes: read a row here and you have a
`document_id`, and `document_store.reference()`/`download_url()` take one. Both
re-resolve under the caller's own tenant context, so a stolen id still returns
*"no stored document"* — **but a table that lists another tenant's document ids
would leak the EXISTENCE of their files even if the bytes stayed shut**, and
HR-1 says existence must not leak. So the policy here is not belt-and-braces; it
is the first of the two locks on the same door.

A cross-tenant WRITE is worse again: filing a document against another utility's
account puts a stranger's scanned licence in their clerk's Documents tab, and
nothing in this product can remove it (`NFR-35`, write-once, seven years).

⚠ **THE `NULLIF` FORM, per DEF-639** — deny-by-default without erroring on an
unset GUC. `NULLIF(current_setting('app.tenant_id', true), '')::uuid` returns
NULL rather than raising on a missing parameter, and `tenant_id = NULL` is NULL,
which is not TRUE, so no row is visible and no row may be written.

Postgres only — `PostgresOnlySQL` skips honestly on the sqlite test database,
where RLS does not exist. The G5 isolation suite proves the policy under a
NON-SUPERUSER probe role, because the app connects as a superuser and superusers
bypass RLS unconditionally (`tests/isolation_helpers.py`).
"""

from django.db import migrations

from core.migrationtools import PostgresOnlySQL

TABLE = "account_documents"

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
    dependencies = [("customers", "0042_cr094_i_account_documents")]

    operations = [PostgresOnlySQL(POLICY, reverse_sql=REVERSE)]
