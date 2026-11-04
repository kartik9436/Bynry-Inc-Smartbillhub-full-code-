"""work 0019 — RLS ENABLE + FORCE on `work_sync_receipts`.

HUMAN-OWNED (RLS policies are a CLAUDE.md hard-rule-1 🔒 path).

HUMAN-REVIEW-PENDING — AI-authored 2026-09-05 under the PO ruling of 2026-08-09
(*"AI will do it; we will review it later as human"*). Its row is in
`12-governance/09-human-review-ledger.md` (task `L6`); not RATIFIED without a
recorded sign-off.

WHY THIS TABLE NEEDS IT, AND IT IS NOT THE USUAL ANSWER
────────────────────────────────────────────────────────────────────────────
The usual answer is *a tenant table needs a tenant policy*, and it applies. What
is specific here is that this table decides whether an act HAPPENS.

A receipt row is the server's answer to *have I seen this key before*. If a row
written under one tenant were visible to another, then a Lone Star Ridge phone
queueing an item whose short key happens to equal a Brazos Bend key would be
told **duplicate** — and its safety tick, its reading or its CLOSE would be
silently dropped with the sync reporting success. That is not a leak of data; it
is a leak that DESTROYS data, in the one place a technician has no way to
notice: `J65` step 13 asserts it in as many words (*"a Lone Star key equal to a
Brazos Bend key is not a duplicate"*).

THE POLICY IS THE `NULLIF` FORM (DEF-639)
────────────────────────────────────────────────────────────────────────────
    NULLIF(current_setting('app.tenant_id', true), '')::uuid

Deny-by-default WITHOUT erroring on an unset GUC — what makes a fresh database
buildable (`OQ-354`/`DEF-622`).

WHY `FORCE` AND NOT ONLY `ENABLE`
────────────────────────────────────────────────────────────────────────────
`ENABLE` alone exempts the table's OWNER, and the application's migration role
owns every table in this schema. B2 §3 requires both, and the proof reads
`relrowsecurity` AND `relforcerowsecurity` out of `pg_class` rather than
trusting that this file ran (hard-won law 1).

AND WHY THE PROOF CANNOT BE THE SUITE'S OWN DATABASE
────────────────────────────────────────────────────────────────────────────
`config/settings/test.py` hardcodes SQLite, which has no row-level security at
all, so every assertion about it passes there by vacuum — hard-won law 14's
shape. ⚠ **AND A RUN AS THE ORDINARY `smartbillhub` ROLE PROVES NOTHING EITHER:
it holds SUPERUSER, and PostgreSQL exempts a superuser from row security
unconditionally, `FORCE` included (`DEF-2717`).**
`tests/test_us_wrk_044_sync_pg.py` runs under `config.settings.local` against
real PostgreSQL 16 as `sbh_gate_iso`, which is NOSUPERUSER NOBYPASSRLS
(`DEF-GOV-4036`) — the only configuration in which any of this is evidence.

NO `%` IN THIS FILE, AND THAT IS DELIBERATE (`DEF-WRK-4027`)
────────────────────────────────────────────────────────────────────────────
This SQL runs through `RunSQL`, which passes `params=None` — so psycopg
substitutes nothing and a `%%` written here would reach PostgreSQL verbatim as a
literal percent. That is what stopped every PostgreSQL migration on this branch
at `work/0009` on 2026-09-05. This file contains none, so the question does not
arise.
"""

from django.db import migrations

from core.migrationtools import PostgresOnlySQL

TENANT = "NULLIF(current_setting('app.tenant_id', true), '')::uuid"

TABLES = ("work_sync_receipts",)

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
    dependencies = [("work", "0018_cr070_l_sync_receipts")]

    operations = [PostgresOnlySQL(POLICY, reverse_sql=REVERSE)]
