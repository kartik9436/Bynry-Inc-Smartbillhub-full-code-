"""work 0004 — RLS ENABLE + FORCE on the eight template-bundle tables.
HUMAN-OWNED (RLS policies are a CLAUDE.md hard-rule-1 🔒 path).

HUMAN-REVIEW-PENDING — AI-authored 2026-09-05 under the PO ruling of 2026-08-09
(*"AI will do it; we will review it later as human"*). Row in
`12-governance/09-human-review-ledger.md`; not RATIFIED without a sign-off.

WHY IT NEEDS ONE
────────────────
`work/0002`'s argument was that Settings tables carry a utility's operating
posture. These are worse. **A template bundle is the utility's method** — the
exact steps its crews follow, the minutes each takes, the safety lines it
demands before a confined-space entry, the parts it fits and what it measures.
A competitor reading `wot_tasks` reads how another utility does the job; a
competitor reading `wot_materials` reads what it fits and, through `parts`,
what it pays.

And a WRITE across the boundary is worse than a read, in a way that reaches a
customer rather than a spreadsheet: deleting another tenant's `wot_safety` row
removes a safety line from a template, and the next order raised from it is
copied WITHOUT that line (`BR-WRK-008` — copy, never link). Nothing about the
resulting job looks wrong. That is what `FORCE` is for.

THE POLICY IS THE `NULLIF` FORM (DEF-639)
─────────────────────────────────────────
    NULLIF(current_setting('app.tenant_id', true), '')::uuid

Deny-by-default WITHOUT erroring on an unset GUC — which is what makes a fresh
database buildable (`OQ-354`/`DEF-622`). These eight tables are born in that
form.

WHY `FORCE` AND NOT ONLY `ENABLE`
─────────────────────────────────
`ENABLE` alone exempts the table's OWNER and the application's migration role
owns every table in this schema. B2 §3 requires both, and
`test_us_wrk_rls_pg.py` reads `relrowsecurity` AND `relforcerowsecurity` out of
`pg_class` for all fourteen Work tables rather than trusting that this file ran.

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

#: The eight tables `work/0003` created, and only those. A table Work does not
#: own does not get a policy from Work's migration — `work_order_templates`
#: has carried its own since `metering/0026`.
TABLES = (
    "wot_details",
    "wot_safety",
    "wot_tasks",
    "wot_materials",
    "wot_readings",
    "wot_help",
    "wot_asset_types",
    "work_order_template_versions",
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
    dependencies = [("work", "0003_cr070_d_template_bundle")]

    operations = [PostgresOnlySQL(POLICY, reverse_sql=REVERSE)]
