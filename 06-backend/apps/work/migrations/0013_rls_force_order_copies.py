"""work 0013 — RLS ENABLE + FORCE on the order's six copy tables.

HUMAN-OWNED (RLS policies are a CLAUDE.md hard-rule-1 🔒 path).

HUMAN-REVIEW-PENDING — AI-authored 2026-09-05 under the PO ruling of 2026-08-09
(*"AI will do it; we will review it later as human"*). Its row is in
`12-governance/09-human-review-ledger.md` (task `H4`); not RATIFIED without a
recorded sign-off.

WHY THESE SIX TABLES NEED IT — AND IT IS NOT THE USUAL ANSWER
-------------------------------------------------------------
The usual answer is *a tenant table needs a tenant policy*, and it applies here.
But these six carry something the reference tables do not: **a technician's
whereabouts and a way into a customer's property.** `work_order_details` holds a
GATE CODE and access notes for a specific address; `work_order_safety` and
`work_order_tasks` say who was at that address and at what minute they ticked
each step; `work_order_readings` holds the meter serials and the numbers taken
off them. Read across a tenant boundary that is another utility's customers'
entry codes and a schedule of when their houses were visited. There is no
version of that leak that is minor.

Written across one, it is worse in a quieter way: a copy row inserted under
another utility's order would change what a technician is shown to do on a job —
a safety step removed, a reading added — and the copy is precisely the thing
nothing downstream re-checks against a template, because not re-checking it is
`BR-WRK-008`.

THE POLICY IS THE `NULLIF` FORM (DEF-639)
-----------------------------------------
    NULLIF(current_setting('app.tenant_id', true), '')::uuid

Deny-by-default WITHOUT erroring on an unset GUC — what makes a fresh database
buildable (`OQ-354`/`DEF-622`).

WHY `FORCE` AND NOT ONLY `ENABLE`
---------------------------------
`ENABLE` alone exempts the table's OWNER, and the application's migration role
owns every table in this schema. B2 §3 requires both, and the proof reads
`relrowsecurity` AND `relforcerowsecurity` out of `pg_class` rather than trusting
that this file ran (hard-won law 1).

AND WHY THE PROOF CANNOT BE THE SUITE'S OWN DATABASE
-----------------------------------------------------
`config/settings/test.py` hardcodes SQLite, which has no row-level security at
all, so every assertion about it passes there by vacuum — hard-won law 14's
shape. ⚠ **AND THE TENANT-ISOLATION GATE CANNOT BE TAKEN AS THE PROOF EITHER**:
`DEF-GOV-4024` (2026-09-05) records that it runs the isolation suite without
pointing it at PostgreSQL and therefore inherits SQLite — 46 of 238 proofs run,
192 skip, and it exits 0. `tests/test_us_wrk_032_copies_pg.py` runs under
`config.settings.local` against real PostgreSQL 16 as the `sbh_rls_probe` role,
because PostgreSQL exempts superusers from RLS unconditionally — `FORCE`
included — and the development role IS a superuser (`DEF-2717`).
"""

from django.db import migrations

from core.migrationtools import PostgresOnlySQL

TENANT = "NULLIF(current_setting('app.tenant_id', true), '')::uuid"

TABLES = (
    "work_order_details",
    "work_order_safety",
    "work_order_tasks",
    "work_order_materials",
    "work_order_readings",
    "work_order_help",
)

POLICY = "\n".join(
    f"""
ALTER TABLE {t} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {t} FORCE ROW LEVEL SECURITY;
CREATE POLICY {t}_tenant_isolation ON {t}
  USING      (tenant_id = {TENANT})
  WITH CHECK (tenant_id = {TENANT});
"""
    for t in TABLES
)

REVERSE = "\n".join(
    f"""
DROP POLICY IF EXISTS {t}_tenant_isolation ON {t};
ALTER TABLE {t} NO FORCE ROW LEVEL SECURITY;
ALTER TABLE {t} DISABLE ROW LEVEL SECURITY;
"""
    for t in TABLES
)


class Migration(migrations.Migration):
    dependencies = [("work", "0012_cr070_h_order_copies")]

    operations = [PostgresOnlySQL(POLICY, reverse_sql=REVERSE)]
