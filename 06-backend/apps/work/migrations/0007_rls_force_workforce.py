"""work 0007 — RLS ENABLE + FORCE on the six workforce tables.
HUMAN-OWNED (RLS policies are a CLAUDE.md hard-rule-1 🔒 path).

HUMAN-REVIEW-PENDING — AI-authored 2026-09-05 under the PO ruling of 2026-08-09
(*"AI will do it; we will review it later as human"*). Row in
`12-governance/09-human-review-ledger.md`; not RATIFIED without a sign-off.

WHY IT NEEDS ONE
────────────────
These six tables say **who works for a utility and what they are allowed to
do**. Three of them are about a named person: their shift, the van they drive,
the skills they hold and the certifications that are about to run out.
`technician_certifications.expires_on` is, in plain words, a date on which a
named individual stops being allowed to enter a confined space — read across a
tenant boundary it is a competitor's staffing plan, and written across one it
is a safety record that says the wrong thing about a real person.

And `work_settings.certification_lapse_policy` is the row that decides whether
a lapsed certification REFUSES an assignment. A write across the boundary
flips another utility's safety posture from *block* to *warn* and nothing about
the resulting dispatch looks wrong. That is what `FORCE` is for.

THE POLICY IS THE `NULLIF` FORM (DEF-639)
─────────────────────────────────────────
    NULLIF(current_setting('app.tenant_id', true), '')::uuid

Deny-by-default WITHOUT erroring on an unset GUC — which is what makes a fresh
database buildable (`OQ-354`/`DEF-622`). These six tables are born in that form.

WHY `FORCE` AND NOT ONLY `ENABLE`
─────────────────────────────────
`ENABLE` alone exempts the table's OWNER and the application's migration role
owns every table in this schema. B2 §3 requires both, and
`test_us_wrk_rls_pg.py` reads `relrowsecurity` AND `relforcerowsecurity` out of
`pg_class` for every Work table rather than trusting that this file ran.

AND WHY THE PROOF CANNOT BE THE SUITE'S OWN DATABASE
────────────────────────────────────────────────────
`config/settings/test.py` hardcodes SQLite, which has no row-level security of
any kind — every assertion about a policy passes there by vacuum (hard-won law
14's shape one rule along). The proof runs under `config.settings.local`
against real PostgreSQL 16, as the `sbh_rls_probe` role, because PostgreSQL
exempts superusers from RLS unconditionally, `FORCE` included, and the
development role IS a superuser (`DEF-2717`).
"""

from django.db import migrations

from core.migrationtools import PostgresOnlySQL

#: The six tables `work/0006` created, and only those.
TABLES = (
    "work_settings",
    "crews",
    "technicians",
    "technician_skills",
    "crew_skills",
    "technician_certifications",
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
    dependencies = [("work", "0006_cr070_f_workforce")]

    operations = [PostgresOnlySQL(POLICY, reverse_sql=REVERSE)]
