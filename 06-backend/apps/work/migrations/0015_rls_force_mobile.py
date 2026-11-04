"""work 0015 — RLS ENABLE + FORCE on `technician_devices`.

HUMAN-OWNED (RLS policies are a CLAUDE.md hard-rule-1 🔒 path).

HUMAN-REVIEW-PENDING — AI-authored 2026-09-05 under the PO ruling of 2026-08-09
(*"AI will do it; we will review it later as human"*). Its row is in
`12-governance/09-human-review-ledger.md` (task `J6`); not RATIFIED without a
recorded sign-off.

WHY THIS ONE TABLE NEEDS IT, AND IT IS NOT THE USUAL ANSWER
------------------------------------------------------------
The usual answer is *a tenant table needs a tenant policy*, and it applies. But
this table carries something none of the reference tables do: **a live bearer
credential that addresses a physical handset in a named person's pocket.** A
row read across a tenant boundary is another utility's technician's push token;
a row WRITTEN across one is worse, because it makes another utility's phone a
delivery address for jobs — a stranger's handset ringing with somebody else's
customer's name, street and gate code, and nothing anywhere to notice.

There is no version of that leak that is minor, and it is the reason `token` is
never rendered, never logged and never returned by a read: the policy is the
boundary and the silence is the second layer.

THE POLICY IS THE `NULLIF` FORM (DEF-639)
-----------------------------------------
    NULLIF(current_setting('app.tenant_id', true), '')::uuid

Deny-by-default WITHOUT erroring on an unset GUC — what makes a fresh database
buildable (`OQ-354`/`DEF-622`).

WHY `FORCE` AND NOT ONLY `ENABLE`
---------------------------------
`ENABLE` alone exempts the table's OWNER, and the application's migration role
owns every table in this schema. B2 §3 requires both, and the proof reads
`relrowsecurity` AND `relforcerowsecurity` out of `pg_class` rather than
trusting that this file ran (hard-won law 1).

AND WHY THE PROOF CANNOT BE THE SUITE'S OWN DATABASE
-----------------------------------------------------
`config/settings/test.py` hardcodes SQLite, which has no row-level security at
all, so every assertion about it passes there by vacuum — hard-won law 14's
shape. ⚠ **AND THE TENANT-ISOLATION GATE CANNOT BE TAKEN AS THE PROOF EITHER**:
`DEF-GOV-4024` (2026-09-05) records that it runs the isolation suite without
pointing it at PostgreSQL and therefore inherits SQLite. **On this machine the
gate SKIPs for a second reason and names it: the local `smartbillhub` role holds
SUPERUSER, and PostgreSQL exempts a superuser from row security unconditionally
— `FORCE` included (`DEF-2717`).** `tests/test_us_wrk_030_push_pg.py` runs under
`config.settings.local` against real PostgreSQL 16 as the NOSUPERUSER
NOBYPASSRLS role `sbh_gate_iso`, which is the only configuration in which any of
this is evidence.

NO `%` IN THIS FILE, AND THAT IS DELIBERATE (`DEF-WRK-4027`)
-------------------------------------------------------------
This SQL runs through `RunSQL`, which passes `params=None` — so psycopg
substitutes nothing and a `%%` written here would reach PostgreSQL verbatim as a
literal percent. That is exactly what stopped every PostgreSQL migration on this
branch at `work/0009` on 2026-09-05. The convention documented in
`integrations/0001_initial.py` (*double every `%`*) is true only of
`schema_editor.execute(sql)`, whose default `params=()` makes psycopg
substitute. Restated so it travels: **double a `%` only where psycopg will
substitute.** This file contains none, so the question does not arise — and the
sentence is here because the two neighbouring files look identical and disagree.
"""

from django.db import migrations

from core.migrationtools import PostgresOnlySQL

TENANT = "NULLIF(current_setting('app.tenant_id', true), '')::uuid"

TABLES = ("technician_devices",)

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
    dependencies = [("work", "0014_cr070_j_mobile_devices")]

    operations = [PostgresOnlySQL(POLICY, reverse_sql=REVERSE)]
