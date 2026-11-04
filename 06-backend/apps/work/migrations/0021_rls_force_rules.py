"""work 0021 — RLS ENABLE + FORCE on `work_order_rules` and `work_order_rule_raises`.

HUMAN-OWNED (RLS policies are a CLAUDE.md hard-rule-1 🔒 path).

HUMAN-REVIEW-PENDING — AI-authored 2026-09-05 under the PO ruling of 2026-08-09
(*"AI will do it; we will review it later as human"*). Its row is in
`12-governance/09-human-review-ledger.md` (task `M6`); not RATIFIED without a
recorded sign-off.

WHY THESE TWO TABLES NEED IT, AND THE ANSWER IS NOT THE USUAL ONE
────────────────────────────────────────────────────────────────────────────
The usual answer is *a tenant table needs a tenant policy*, and it applies. What
is different about a RULE is that it is not a record of something that happened
— it is a standing instruction that a machine executes at 02:00 with nobody
watching.

`work_order_rules` is read by an unattended job. Every other table in this
module is read by a person who is looking at a screen and would notice a row
belonging to another utility. **Nobody is looking at 02:00.** If a policy failure
let Brazos Bend's asset-age rule be read while `app.tenant_id` was Lone Star
Ridge's, the sweep would not display a stranger's row — it would **raise real
jobs against Lone Star Ridge's meters from a rule Lone Star Ridge never wrote**,
dispatch them to technicians, and the first person to see it would be a crew
member driving to an address at 08:00. A leak here is not a disclosure, it is an
instruction.

`work_order_rule_raises` is the sweep's memory, and a leak there is the same
failure with the sign flipped: a raise row read across the boundary makes a rule
believe it has already fired for a subject it has never seen, and the job is
**silently never raised**. A meter past its certification life is then simply
missed, for ever, with nothing on any screen to show it.

⚠ **AND THE MEMORY MATTERS MORE THAN THE RULE, WHICH IS WHY BOTH TABLES ARE HERE
AND NOT JUST THE FIRST.** It is tempting to read `work_order_rule_raises` as
bookkeeping — a log — and log tables are where a lane economises. It is not a
log: it is the only thing standing between one job and a job every single night.

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
`tests/test_us_wrk_037_rules_pg.py` runs under `config.settings.local` against
real PostgreSQL 16 as `sbh_gate_iso`, which is NOSUPERUSER NOBYPASSRLS
(`DEF-GOV-4036`) — the only configuration in which any of this is evidence.

NO `%` IN THIS FILE, AND THAT IS DELIBERATE (`DEF-WRK-4027`)
────────────────────────────────────────────────────────────────────────────
This SQL runs through `RunSQL`, which passes `params=None` — so psycopg
substitutes nothing and a `%%` written here would reach PostgreSQL verbatim as a
literal percent. That is what stopped every PostgreSQL migration on this branch
at `work/0009` on 2026-09-05. This file contains none.
"""

from django.db import migrations

from core.migrationtools import PostgresOnlySQL

TENANT = "NULLIF(current_setting('app.tenant_id', true), '')::uuid"

TABLES = ("work_order_rules", "work_order_rule_raises")

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
    dependencies = [("work", "0020_cr070_m_rules")]

    operations = [PostgresOnlySQL(POLICY, reverse_sql=REVERSE)]
