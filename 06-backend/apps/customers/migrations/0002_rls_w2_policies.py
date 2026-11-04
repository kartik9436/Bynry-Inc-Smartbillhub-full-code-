"""customers 0002 — RLS ENABLE+FORCE on every W2 customers TENANT table.
HUMAN-OWNED (RLS policies are a CLAUDE.md rule-1 🔒 path).

HUMAN-REVIEW-PENDING — AI-authored 2026-08-10 under the PO ruling of 2026-08-09
("AI will do it; we will review it later as human"), applying the SIGNED B2 §3
policy template VERBATIM, once per table. Row per file in
12-governance/09-human-review-ledger.md; not RATIFIED without human sign-off.

The B2 §3 template, repeated per tenant-scoped table — deny-by-default: with
`app.tenant_id` unset the `::uuid` cast of '' fails and NO row is visible:

    ALTER TABLE <t> ENABLE ROW LEVEL SECURITY;
    ALTER TABLE <t> FORCE ROW LEVEL SECURITY;    -- applies even to the owner
    CREATE POLICY <t>_tenant_isolation ON <t>
      USING      (tenant_id = current_setting('app.tenant_id')::uuid)
      WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid);

FIVE tables, not six. `account_types` is the one table migration 0001 creates
with NO `tenant_id`: r5 #12 [D5] makes it PLATFORM ("platform-seeded"), and
r5's closing line is explicit — "RLS FORCE on every tenant-scoped table above;
platform tables (services, account_types, B10 set) excluded per B2 §3
pattern." Giving it a policy would be impossible (there is no column to test)
AND wrong (every tenant must read the same four categories). The suite-wide
G5 sweep `test_g5_the_rls_exempt_list_is_exactly_what_b2_declares` only flags
tables that HAVE a `tenant_id` and no policy, so this exemption is structural
rather than allowlisted — there is nothing to add to RLS_EXEMPT_TABLES.

⚠ FOR THE REVIEWER — one hosting call: the policy SQL is INLINE here rather
than in 06-backend/db/rls_customers_w2.sql. `06-backend/db/` is outside this
lane's stated territory, and identity 0004 and tenancy 0004 made the same call
for the same reason and flagged it for relocation at review. FLAGGED AGAIN
HERE: three files now want moving into db/ together, as one edit, by whoever
owns that directory. The policy TEXT is the B2 §3 template either way.

Postgres only — `PostgresOnlySQL` skips honestly on the sqlite test database,
where RLS does not exist. The live proofs are the G5 isolation suite
(NFR-10, zero tolerance, release blocker): see
tests/test_us_cus_schema_and_seed.py for the per-table probes.
"""

from django.db import migrations

from core.migrationtools import PostgresOnlySQL

# B2 §3 template, verbatim, one block per tenant-scoped customers table.
# Order matches the B2 §2 / r5 reading order, not the migration's create order.
POLICIES = "\n".join(
    f"""
ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {table} FORCE ROW LEVEL SECURITY;
CREATE POLICY {table}_tenant_isolation ON {table}
  USING      (tenant_id = current_setting('app.tenant_id')::uuid)
  WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid);
"""
    for table in (
        "account_subtypes",
        "account_statuses",
        "accounts",
        "contacts",
        "addresses",
        "service_agreements",
    )
)


class Migration(migrations.Migration):

    dependencies = [
        ("customers", "0001_initial"),
    ]

    operations = [
        PostgresOnlySQL(
            sql=POLICIES,
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
