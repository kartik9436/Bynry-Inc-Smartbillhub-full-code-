"""work 0011 — RLS ENABLE + FORCE on wave N's four tables, and the FREEZE
trigger on `work_order_cost_lines` and `work_order_reports`.

HUMAN-OWNED (RLS policies are a CLAUDE.md hard-rule-1 🔒 path).

HUMAN-REVIEW-PENDING — AI-authored 2026-09-05 under the PO ruling of
2026-08-09 (*"AI will do it; we will review it later as human"*). Row in
`12-governance/09-human-review-ledger.md`; not RATIFIED without a sign-off.

WHY THESE FOUR NEED IT — THREE DIFFERENT ANSWERS
────────────────────────────────────────────────
**`labour_rates`.** Read across a tenant boundary it is another utility's
labour cost — what it pays its crews, which is commercially the most sensitive
number in the module and the reason `WM-45` refused to put a rate on a person
at all. Written across one, it reprices somebody else's work.

**`part_issues`.** Read across, it is another utility's stores and who on its
staff drew from them. Written across, it puts a stranger's name against a
movement that happened.

**`work_order_cost_lines` and `work_order_reports`.** Read across, they are
another utility's job costs and its customers' addresses on a signed document.
Written across — this is the one that matters — a stranger changes the total
on a report a supervisor has already approved.

THE FREEZE IS A TRIGGER, NOT A DOCSTRING (hard-won law 1)
─────────────────────────────────────────────────────────
`BR-WRK-050`: the report is **generated once, by Accept, frozen**, and *"a
correction produces `-v2` beside `-v1`; neither is overwritten."* A
service-layer refusal holds for the service layer. This one holds for the ORM,
for `.update()`, for `raw()`, for a data migration and for a person at a psql
prompt, because it is `BEFORE UPDATE OR DELETE` on the table and it raises.

The shape is `billing/0002`'s `trg_invoice_immutable` and `work/0009`'s
`trg_work_assignment_append_only`, one rule simpler than the invoice: there is
no draft state here, so there is nothing that may ever be edited. A report
that could be edited after approval is not evidence of anything, which is
hard rule 4's whole reasoning applied one table along from a bill.

⚠ **THE COST LINES ARE FROZEN TOO, AND THAT IS THE LOAD-BEARING HALF.**
Freezing the report row while leaving its lines editable would freeze the
`total` column and let the three numbers underneath it move — a document that
adds up to something other than the sum of its own lines, which is exactly
what `BR-WRK-051` exists to prevent.

⚠ **ONE `%` PER PLACEHOLDER, NOT TWO — `DEF-WRK-4027`, 2026-09-05.**
`integrations/0001_initial.py` doubles every `%` because
`schema_editor.execute(sql)` defaults to `params=()` and psycopg then does
%-substitution. THIS migration runs through `PostgresOnlySQL`, a `RunSQL`,
which passes `params=None` — psycopg substitutes nothing and `%%` would arrive
VERBATIM, PL/pgSQL would read it as a literal percent with no placeholder
behind it, and PostgreSQL would refuse to compile the function at CREATE
FUNCTION time. That refusal fails the whole migration, so every PostgreSQL
database on the branch stops at this file. It cost a day on 2026-09-05.

THE POLICY IS THE `NULLIF` FORM (DEF-639)
─────────────────────────────────────────
    NULLIF(current_setting('app.tenant_id', true), '')::uuid

Deny-by-default WITHOUT erroring on an unset GUC — what makes a fresh database
buildable (`OQ-354`/`DEF-622`).

WHY `FORCE` AND NOT ONLY `ENABLE`
─────────────────────────────────
`ENABLE` alone exempts the table's OWNER, and the application's migration role
owns every table in this schema. B2 §3 requires both, and the probe reads
`relrowsecurity` AND `relforcerowsecurity` out of `pg_class` rather than
trusting that this file ran.

AND WHY NEITHER PROOF CAN BE THE SUITE'S OWN DATABASE
─────────────────────────────────────────────────────
`config/settings/test.py` hardcodes SQLite. It has no row-level security **and
runs no PL/pgSQL trigger**, so every assertion about either passes there by
vacuum — hard-won law 14's shape, one rule along. Both proofs run under
`config.settings.local` against real PostgreSQL 16
(`tests/test_us_wrk_053_costing_pg.py`), as the `sbh_rls_probe` role, because
PostgreSQL exempts superusers from RLS unconditionally, `FORCE` included, and
the development role IS a superuser (`DEF-2717`).

⚠ AND THE TENANT-ISOLATION GATE IS NOT THAT PROOF (`DEF-GOV-4024`, filed
2026-09-05): it runs the isolation suite without pointing it at PostgreSQL, so
it inherits SQLite, 46 of 238 proofs run, 192 skip and it exits 0. A green
gate here is evidence of nothing. The `_pg.py` file is the evidence.
"""

from django.db import migrations

from core.migrationtools import PostgresOnlySQL

TENANT = "NULLIF(current_setting('app.tenant_id', true), '')::uuid"

_TABLES = (
    "labour_rates",
    "part_issues",
    "work_order_cost_lines",
    "work_order_reports",
)

_RLS = "\n".join(
    f"""
ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {table} FORCE ROW LEVEL SECURITY;
CREATE POLICY {table}_tenant_isolation ON {table}
  USING      (tenant_id = {TENANT})
  WITH CHECK (tenant_id = {TENANT});
"""
    for table in _TABLES
)

_FREEZE = """
-- BR-WRK-050 — a report is generated once and frozen. A correction is a new
-- version beside the old one (`-v2` beside `-v1`), never an edit to the
-- document a supervisor approved.
CREATE OR REPLACE FUNCTION work_report_frozen() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'BR-WRK-050: a work-order report is frozen; row % cannot be %. To correct a report, generate the next version beside it.',
    OLD.id, lower(TG_OP);
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_work_order_reports_frozen ON work_order_reports;
CREATE TRIGGER trg_work_order_reports_frozen
  BEFORE UPDATE OR DELETE ON work_order_reports
  FOR EACH ROW EXECUTE FUNCTION work_report_frozen();

-- BR-WRK-051 — and its LINES with it, or the total would be frozen over three
-- numbers that could still move.
CREATE OR REPLACE FUNCTION work_cost_line_frozen() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'BR-WRK-051: a work-order cost line is frozen; row % cannot be %. The report it belongs to is corrected by a new version.',
    OLD.id, lower(TG_OP);
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_work_order_cost_lines_frozen ON work_order_cost_lines;
CREATE TRIGGER trg_work_order_cost_lines_frozen
  BEFORE UPDATE OR DELETE ON work_order_cost_lines
  FOR EACH ROW EXECUTE FUNCTION work_cost_line_frozen();
"""

POLICY = _RLS + _FREEZE

REVERSE = (
    """
DROP TRIGGER IF EXISTS trg_work_order_cost_lines_frozen ON work_order_cost_lines;
DROP FUNCTION IF EXISTS work_cost_line_frozen();
DROP TRIGGER IF EXISTS trg_work_order_reports_frozen ON work_order_reports;
DROP FUNCTION IF EXISTS work_report_frozen();
"""
    + "\n".join(
        f"""
DROP POLICY IF EXISTS {table}_tenant_isolation ON {table};
ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY;
ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;
"""
        for table in _TABLES
    )
)


class Migration(migrations.Migration):
    dependencies = [("work", "0010_cr070_n_costing")]

    operations = [PostgresOnlySQL(POLICY, reverse_sql=REVERSE)]
