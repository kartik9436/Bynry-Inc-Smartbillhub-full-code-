"""customers 0006 — RLS ENABLE+FORCE on the four US-CUS-019 tables.
HUMAN-OWNED (RLS policies are a CLAUDE.md rule-1 🔒 path).

HUMAN-REVIEW-PENDING — AI-authored 2026-08-11 under the PO ruling of 2026-08-09
("AI will do it; we will review it later as human"), applying the SIGNED B2 §3
policy template VERBATIM, once per table. Row in
12-governance/09-human-review-ledger.md; not RATIFIED without human sign-off.

The B2 §3 template, repeated per tenant-scoped table — deny-by-default: with
`app.tenant_id` unset the `::uuid` cast of '' fails and NO row is visible:

    ALTER TABLE <t> ENABLE ROW LEVEL SECURITY;
    ALTER TABLE <t> FORCE ROW LEVEL SECURITY;    -- applies even to the owner
    CREATE POLICY <t>_tenant_isolation ON <t>
      USING      (tenant_id = current_setting('app.tenant_id')::uuid)
      WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid);

FOUR tables, and the STAGING pair matters as much as the entity pair
────────────────────────────────────────────────────────────────────
It is tempting to read `account_import_rows` as scratch space. It is not.
Between the upload and the commit it holds the customer's NAME, EMAIL, PHONE
and MAILING ADDRESS — PII per BR-CUS-045 — for two thousand people, with no
`accounts` row yet in existence to hang any of it on. A staging table without
a policy is a tenant's entire customer base readable by the next tenant to run
an import. So all four get the template, on the same terms as `accounts`.

⚠ FOR THE REVIEWER — the same hosting call migrations 0002 flagged: the policy
SQL is INLINE here rather than in `06-backend/db/rls_customers_w2.sql`, because
`06-backend/db/` is outside this lane's stated territory. customers 0002,
identity 0004 and tenancy 0004 all made this call and all flagged it for
relocation; this makes FOUR files wanting to move into `db/` together, as one
edit, by whoever owns that directory. The policy TEXT is the B2 §3 template
either way.

Postgres only — `PostgresOnlySQL` skips honestly on the sqlite test database,
where RLS does not exist. The live proof is the G5 isolation suite (NFR-10,
zero tolerance, release blocker).
"""

from django.db import migrations

from core.migrationtools import PostgresOnlySQL

# B2 §3 template, verbatim, one block per tenant-scoped table added by 0005.
POLICIES = "\n".join(
    f"""
ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {table} FORCE ROW LEVEL SECURITY;
CREATE POLICY {table}_tenant_isolation ON {table}
  USING      (tenant_id = current_setting('app.tenant_id')::uuid)
  WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid);
"""
    for table in (
        "customers",
        "customer_accounts",
        "account_import_batches",
        "account_import_rows",
    )
)


class Migration(migrations.Migration):

    dependencies = [
        ("customers", "0005_us_cus_019_customer_entity_and_import_staging"),
    ]

    operations = [
        PostgresOnlySQL(
            sql=POLICIES,
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
