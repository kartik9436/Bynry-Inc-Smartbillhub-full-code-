"""work 0054 — RLS ENABLE + FORCE on the four MQ-040 step-1 tables.

HUMAN-OWNED (RLS policies are a CLAUDE.md hard-rule-1 🔒 path).

HUMAN-REVIEW-PENDING — AI-authored 2026-10-26 (CR-193-BRC10) under the PO
ruling of 2026-08-09 (*"AI will do it; we will review it later as human"*);
the review-ledger row is written in the same commit. Not RATIFIED without a
sign-off.

`work/0049`'s policy character for character — the `NULLIF` form (`DEF-639`),
deny-by-default without erroring on an unset GUC — and FORCE as well as ENABLE
because the migration role owns the tables and ENABLE alone exempts the owner.
Proved on PostgreSQL 16 in `tests/test_cr193_shifts_pg.py`.
"""

from django.db import migrations

from core.migrationtools import PostgresOnlySQL

TENANT = "NULLIF(current_setting('app.tenant_id', true), '')::uuid"
TABLES = (
    "work_technician_working_days",
    "work_technician_day_exceptions",
    "work_technician_shift_ends",
    "work_timesheet_submissions",
)

POLICY = "".join(
    f"""
ALTER TABLE {t} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {t} FORCE ROW LEVEL SECURITY;
CREATE POLICY {t}_tenant_isolation ON {t}
  USING      (tenant_id = {TENANT})
  WITH CHECK (tenant_id = {TENANT});
"""
    for t in TABLES
)

REVERSE = "".join(
    f"""
DROP POLICY IF EXISTS {t}_tenant_isolation ON {t};
ALTER TABLE {t} NO FORCE ROW LEVEL SECURITY;
ALTER TABLE {t} DISABLE ROW LEVEL SECURITY;
"""
    for t in TABLES
)


class Migration(migrations.Migration):
    dependencies = [("work", "0053_cr193_shifts_timesheets")]

    operations = [PostgresOnlySQL(POLICY, reverse_sql=REVERSE)]
