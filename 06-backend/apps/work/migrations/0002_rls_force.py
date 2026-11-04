"""work 0002 — RLS ENABLE + FORCE on all six Work reference tables.
HUMAN-OWNED (RLS policies are a CLAUDE.md hard-rule-1 🔒 path).

HUMAN-REVIEW-PENDING — AI-authored 2026-09-04 under the PO ruling of 2026-08-09
(*"AI will do it; we will review it later as human"*). Row in
`12-governance/09-human-review-ledger.md`; not RATIFIED without a sign-off.

WHY IT NEEDS ONE
────────────────
These are SETTINGS tables, and settings are where the temptation to skip RLS is
strongest — nobody's name is in any of them. What IS in them is one utility's
operating posture: the jobs it does, how fast it promises to do them, what its
crews are qualified for, what safety kit it demands before a confined-space
entry, and **what every part it fits costs it**. A competitor reading
`work_priorities` learns the SLA another utility promises its customers; a
competitor reading `parts` learns its meter prices. And a WRITE across the
boundary is worse than a read: flipping another tenant's *Urgent* from 4 hours
to 400 breaks every due date they raise from that moment, silently, and the
only trace is an audit row on the wrong side of the wall.

`CR-070` §3 asks for the policy in the same migration as the table. It is in
the same COMMIT and the migration immediately after — split so a reviewer of
a 🔒 path reads the policy and nothing else, never so that a deployment can get
one without the other.

THE POLICY IS THE `NULLIF` FORM (DEF-639)
─────────────────────────────────────────
    NULLIF(current_setting('app.tenant_id', true), '')::uuid

The 34 policies written before 2026-08-24 read `current_setting('app.tenant_id')
::uuid`, which **ERRORS** on an unset or empty GUC rather than denying — which
is what makes a fresh database un-buildable (`OQ-354`/`DEF-622`: a deferred FK
validation at a migration's exit evaluated against `''` dies with *invalid input
syntax for type uuid: ""*). This form is deny-by-default WITHOUT the error: the
second argument to `current_setting` makes a missing parameter return NULL
instead of raising, `NULLIF` turns `''` into NULL, and `tenant_id = NULL` is
NULL — which is not TRUE, so **no row is visible and no row may be written.**
These six tables are born in the new form and never need the rewrite.

WHY `FORCE` AND NOT ONLY `ENABLE`
─────────────────────────────────
`ENABLE ROW LEVEL SECURITY` alone exempts the table's OWNER, and the
application's migration role owns every table in this schema. `FORCE` is what
makes the policy apply to the owner too. B2 §3 requires both; `test_us_wrk_rls_
pg.py` reads `relrowsecurity` AND `relforcerowsecurity` out of `pg_class` for
all six rather than trusting that this file ran.

AND WHY THE PROOF CANNOT BE THE SUITE'S OWN DATABASE
────────────────────────────────────────────────────
`config/settings/test.py` hardcodes in-memory SQLite, **which has no row-level
security of any kind** — every assertion about a policy passes there by
vacuum. That is hard-won law 14's shape one rule along, so the proof for this
migration lives in `06-backend/tests/test_us_wrk_rls_pg.py`, runs under
`config.settings.local` against real PostgreSQL 16, and asserts under the
`sbh_rls_probe` role (NOLOGIN NOSUPERUSER NOBYPASSRLS) — because PostgreSQL
exempts superusers from RLS unconditionally, `FORCE` included, and the
development role IS a superuser (`DEF-2717`).

`PostgresOnlySQL` skips honestly on sqlite rather than pretending to apply.
"""

from django.db import migrations

from core.migrationtools import PostgresOnlySQL

#: The six tables this module created in `0001_initial`, and only those. A
#: table Work does not own does not get a policy from Work's migration.
TABLES = (
    "work_order_types",
    "work_priorities",
    "work_skills",
    "work_safety_kits",
    "part_categories",
    "parts",
)

TENANT = "NULLIF(current_setting('app.tenant_id', true), '')::uuid"

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
    dependencies = [("work", "0001_initial")]

    operations = [PostgresOnlySQL(POLICY, reverse_sql=REVERSE)]
