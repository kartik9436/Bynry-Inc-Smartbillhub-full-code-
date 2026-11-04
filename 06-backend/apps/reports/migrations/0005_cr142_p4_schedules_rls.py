"""reports 0005 — RLS ENABLE + FORCE on `report_schedules` (`CR-142-BRC07` `P4.1`).
HUMAN-OWNED (RLS policies are a CLAUDE.md hard-rule-1 🔒 path).

HUMAN-REVIEW-PENDING — AI-authored 2026-09-27 under the PO ruling of 2026-08-09
(*"AI will do it; we will review it later as human"*). Row in
`12-governance/09-human-review-ledger.md`; not RATIFIED without a sign-off.

⚠ THIS TABLE TAKES THE ORDINARY POLICY, AND THAT IS THE WHOLE REVIEW
────────────────────────────────────────────────────────────────────
`0002` is the unusual file in this module: `report_definitions` and
`report_categories` admit `tenant_id IS NULL` on USING so every tenant can read
the 46 reports we ship. **`report_schedules` admits NOTHING of the kind.** A
schedule is always somebody's — there is no platform schedule and there must
never be one, because a platform row here would mean we had scheduled a report
on a customer's behalf and addressed it to people we chose. So both clauses are
`tenant_id = <tenant>`, the same shape `report_tenant_settings` takes.

**WHAT A REVIEWER SHOULD CHECK, IN ONE SENTENCE:** that neither clause mentions
`IS NULL`.

⚠ **AND THIS IS THE ONE REPORTS TABLE A PROCESS OUTSIDE A REQUEST WRITES.**
Everything else here is read or written by a view, with `app.tenant_id` set by
`core.tenancy` from the session. The sweep in `apps/reports/schedules.py` runs
on a celery beat tick with no request behind it, so it enters
`core.tenancy.tenant_context(tenant_id)` per tenant and the policy below is the
only thing standing between a bug in that loop and one utility's schedules
firing under another's name. `tests/test_cr142_p4_schedules_pg.py` is the proof
and it must run on real PostgreSQL: `config/settings/test.py` hardcodes
in-memory SQLite, **which has no row-level security of any kind**, so every
assertion about this policy passes there by vacuum (hard-won law 14's shape one
rule along).

The predicate is the `NULLIF(current_setting(…, true), '')::uuid` form for the
reason `0002` gives at length (DEF-639): deny-by-default without erroring on an
unset GUC. The pre-DEF-639 spelling is described there and deliberately not
quoted anywhere, because `G41` is a shrink-only ratchet over that literal
string.

`FORCE` and not merely `ENABLE` because `ENABLE` alone exempts the table's
owner, and the migration role owns every table in this schema (B2 §3).
"""

from django.db import migrations

from core.migrationtools import PostgresOnlySQL

TENANT = "NULLIF(current_setting('app.tenant_id', true), '')::uuid"

TABLE = "report_schedules"

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
    dependencies = [("reports", "0004_cr142_p4_report_schedules")]

    operations = [PostgresOnlySQL(POLICY, reverse_sql=REVERSE)]
