"""customers 0016 — RLS ENABLE+FORCE on `account_opening_buckets`.
HUMAN-OWNED (RLS policies are a CLAUDE.md rule-1 🔒 path).

HUMAN-REVIEW-PENDING — AI-authored 2026-08-24 under the PO ruling of 2026-08-09
("AI will do it; we will review it later as human"), applying the SIGNED B2 §3
policy template VERBATIM. Row in `12-governance/09-human-review-ledger.md`; not
RATIFIED without human sign-off.

WHY THIS TABLE NEEDS THE TEMPLATE AS MUCH AS `accounts` DOES
─────────────────────────────────────────────────────────────
`account_opening_buckets` is not scratch space and it is not a derived cache. It
holds **what every migrated customer owed on cutover day**, per account, aged —
1,213 rows summing to **$184,320.55** in the GT-16 fixture. A tenant's entire
receivables position, in one table, in four numbers a row.

That is commercially sensitive in a way a name and address are not: it is the
whole book. So it gets the same policy as the accounts it points at, on the same
terms, and the G5 isolation suite proves it under a NON-SUPERUSER role — because
the app connects as a superuser and superusers bypass RLS unconditionally, which
makes any assertion made on the app's own connection vacuous
(`tests/isolation_helpers.py`).

The B2 §3 template, deny-by-default: with `app.tenant_id` unset the `::uuid`
cast of '' fails and NO row is visible.

Postgres only — `PostgresOnlySQL` skips honestly on the sqlite test database,
where RLS does not exist.
"""

from django.db import migrations

from core.migrationtools import PostgresOnlySQL

TABLE = "account_opening_buckets"

POLICY = f"""
ALTER TABLE {TABLE} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {TABLE} FORCE ROW LEVEL SECURITY;
CREATE POLICY {TABLE}_tenant_isolation ON {TABLE}
  USING      (tenant_id = current_setting('app.tenant_id')::uuid)
  WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid);
"""

REVERSE = f"""
DROP POLICY IF EXISTS {TABLE}_tenant_isolation ON {TABLE};
ALTER TABLE {TABLE} NO FORCE ROW LEVEL SECURITY;
ALTER TABLE {TABLE} DISABLE ROW LEVEL SECURITY;
"""


class Migration(migrations.Migration):
    dependencies = [("customers", "0015_cr030_w1_opening_buckets")]

    operations = [PostgresOnlySQL(POLICY, reverse_sql=REVERSE)]
