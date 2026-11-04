"""customers 0055 — RLS ENABLE + FORCE on `account_types`, the table that had
none.

HUMAN-OWNED (RLS policies are a CLAUDE.md rule-1 🔒 path).

HUMAN-REVIEW-PENDING — AI-authored 2026-09-17 under the PO ruling of 2026-08-09
(*"AI will do it; we will review it later as human"*). Row in
`12-governance/09-human-review-ledger.md`; not RATIFIED without a sign-off.

WHY THIS TABLE HAD NO POLICY UNTIL TODAY, AND WHY IT NEEDS ONE NOW
───────────────────────────────────────────────────────────────────
It is not an oversight being corrected — it is a **posture being reversed**. B2
r5 #12 [D5] made `account_types` PLATFORM (*"platform-seeded"*) and r5's closing
line named it among the tables deliberately excluded from RLS. `customers.0002`
says so in as many words: *"FIVE tables, not six"*. There was no `tenant_id` to
test, so there was nothing a policy could have said.

**The PO ruling of 2026-09-17 — *"utility can get their own account types"* —
gives the table a `tenant_id` (`customers.0054`), and hard rule 1 admits no
exception once it has one.** `customers.0002`'s own comment anticipated exactly
this and said what to do: *"account_types grew a tenant_id — it now NEEDS an RLS
policy"*. This is that policy.

WHAT IT PROTECTS, WHICH IS MORE THAN IT LOOKS
──────────────────────────────────────────────
The rows are a vocabulary, so the instinct is that they are harmless. They are
not: a utility's own categories are a statement about **what kind of business it
is in and who its customers are** — a tenant that adds `Marina berth`, `Cannabis
grow` or `Tribal housing` has told you something about itself that no other
tenant is entitled to read. And the write half matters more than the read half:
without `WITH CHECK`, one tenant could create a row belonging to another and
then have its accounts silently priced against a vocabulary it never chose.

⚠ **THE `NULLIF` FORM, per DEF-639** — deny-by-default without erroring on an
unset GUC. `NULLIF(current_setting('app.tenant_id', true), '')::uuid` returns
NULL rather than raising on a missing parameter, and `tenant_id = NULL` is NULL,
which is not TRUE, so no row is visible and no row may be written.

⚠ **ORDER MATTERS AND IS THE REASON THIS IS A SEPARATE FILE FROM 0054.** `FORCE
ROW LEVEL SECURITY` applies to the table OWNER too. Enabled one operation
earlier, it would have hidden from `0054`'s own fan-out the very rows it was
cloning — the migration would have run green over an empty result set and every
account would have been left pointing at a platform row about to be deleted.

Postgres only — `PostgresOnlySQL` skips honestly on the sqlite test database,
where RLS does not exist. The live proof is the G5 isolation suite under a
NON-SUPERUSER probe role, because the app connects as a superuser and superusers
bypass RLS unconditionally (`tests/isolation_helpers.py`); the policy is read
back from `pg_class`/`pg_policy` rather than trusted because the SQL ran —
`tests/test_us_cus_schema_and_seed.py`.
"""

from django.db import migrations

from core.migrationtools import PostgresOnlySQL

TABLE = "account_types"

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
    dependencies = [("customers", "0054_br_cus_1079_account_types_are_the_tenants")]

    operations = [PostgresOnlySQL(POLICY, reverse_sql=REVERSE)]
