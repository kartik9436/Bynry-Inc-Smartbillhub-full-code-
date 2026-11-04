"""customers 0020 — RLS ENABLE + FORCE on BR-CUS-095's checklist table.
HUMAN-OWNED (RLS policies are a CLAUDE.md rule-1 🔒 path).

HUMAN-REVIEW-PENDING — AI-authored 2026-08-24 under the PO ruling of 2026-08-09
(*"AI will do it; we will review it later as human"*). Row in
`12-governance/09-human-review-ledger.md`; not RATIFIED without a sign-off.

WHY IT NEEDS ONE
────────────────
`service_request_document_requirements` is a SETTINGS table, and settings are
where the temptation to skip RLS is strongest — nobody's name is in it. What is
in it is one utility's compliance posture: exactly which documents this utility
demands before it will connect anybody. A competitor reading it learns what the
neighbouring utility asks for and what it does not, and a WRITE across the
boundary is worse than a read — ticking `proof_of_identity` on another tenant's
`move_in` blocks every one of their approvals until somebody finds the row.

⚠ **THE POLICY IS THE `NULLIF` FORM, NOT THE BARE CAST — AND THAT IS DEF-639.**
The 34 policies written before today read
`current_setting('app.tenant_id')::uuid`, which **ERRORS** on an unset or empty
GUC rather than denying. That is what makes a fresh database un-buildable
(OQ-354/DEF-622: a deferred FK validation at a migration's exit is evaluated
against `''` and dies with `invalid input syntax for type uuid: ""`). The form
here —

    NULLIF(current_setting('app.tenant_id', true), '')::uuid

— is deny-by-default WITHOUT the error: the second argument to
`current_setting` makes a missing parameter return NULL instead of raising,
`NULLIF` turns `''` into NULL, and `tenant_id = NULL` is NULL, which is not
TRUE, so **no row is visible and no row may be written**. Same guarantee, one
fewer way to brick a deploy. A lane landing the same rewrite across the existing
34 is in flight; this table is born in the new form and never needs it.

Postgres only — `PostgresOnlySQL` skips honestly on the sqlite test database,
where RLS does not exist. The G5 isolation suite proves the policy under a
NON-SUPERUSER probe role, because the app connects as a superuser and superusers
bypass RLS unconditionally, which makes any assertion made on the app's own
connection vacuous (`tests/isolation_helpers.py`).
"""

from django.db import migrations

from core.migrationtools import PostgresOnlySQL

TABLE = "service_request_document_requirements"

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
    dependencies = [("customers", "0019_cr031_br_cus_090_093_094_095")]

    operations = [PostgresOnlySQL(POLICY, reverse_sql=REVERSE)]
