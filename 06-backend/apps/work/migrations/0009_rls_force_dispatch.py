"""work 0009 — RLS ENABLE + FORCE and the APPEND-ONLY trigger on
`work_order_assignments`.

HUMAN-OWNED (RLS policies are a CLAUDE.md hard-rule-1 🔒 path).

HUMAN-REVIEW-PENDING — AI-authored 2026-09-05 under the PO ruling of 2026-08-09
(*"AI will do it; we will review it later as human"*). Row in
`12-governance/09-human-review-ledger.md`; not RATIFIED without a sign-off.

WHY IT NEEDS ONE — TWO GUARANTEES ON ONE TABLE
──────────────────────────────────────────────
**One.** `work_order_assignments` says which named person was sent to which
address at which time. Read across a tenant boundary it is another utility's
crew roster and its customers' addresses in one join; written across one it puts
a stranger's name on a visit that happened.

**Two.** It is the answer to *who was supposed to be there* when a customer
rings to say nobody came, and to *who took this job off D. Ortiz*. An answer
that can be edited afterwards is not an answer. `BR-WRK-025` says **never an
UPDATE**, and hard rule 4's whole shape is that a correction is a NEW ROW —
`unassign` then `assign` — so the history reads as what happened rather than as
what somebody would prefer had happened.

THE TRIGGER IS THE RULE, NOT A DOCSTRING (hard-won law 1)
─────────────────────────────────────────────────────────
A service-layer refusal holds for the service layer. This one holds for the ORM,
for `.update()`, for `raw()`, for a data migration and for a person at a psql
prompt, because it is `BEFORE UPDATE OR DELETE` on the table and it raises. The
shape is `billing/0002`'s `trg_invoice_immutable`, one rule simpler: there is no
draft state here, so there is nothing that may ever be edited.

THE POLICY IS THE `NULLIF` FORM (DEF-639)
─────────────────────────────────────────
    NULLIF(current_setting('app.tenant_id', true), '')::uuid

Deny-by-default WITHOUT erroring on an unset GUC — what makes a fresh database
buildable (`OQ-354`/`DEF-622`).

WHY `FORCE` AND NOT ONLY `ENABLE`
─────────────────────────────────
`ENABLE` alone exempts the table's OWNER, and the application's migration role
owns every table in this schema. B2 §3 requires both, and
`tests/test_us_wrk_rls_pg.py` reads `relrowsecurity` AND `relforcerowsecurity`
out of `pg_class` rather than trusting that this file ran.

AND WHY NEITHER PROOF CAN BE THE SUITE'S OWN DATABASE
─────────────────────────────────────────────────────
`config/settings/test.py` hardcodes SQLite. It has no row-level security **and
runs no PL/pgSQL trigger**, so every assertion about either passes there by
vacuum — hard-won law 14's shape, one rule along. Both proofs run under
`config.settings.local` against real PostgreSQL 16
(`tests/test_us_wrk_025_dispatch_pg.py`), as the `sbh_rls_probe` role, because
PostgreSQL exempts superusers from RLS unconditionally, `FORCE` included, and
the development role IS a superuser (`DEF-2717`).
"""

from django.db import migrations

from core.migrationtools import PostgresOnlySQL

TENANT = "NULLIF(current_setting('app.tenant_id', true), '')::uuid"

POLICY = f"""
ALTER TABLE work_order_assignments ENABLE ROW LEVEL SECURITY;
ALTER TABLE work_order_assignments FORCE ROW LEVEL SECURITY;
CREATE POLICY work_order_assignments_tenant_isolation ON work_order_assignments
  USING      (tenant_id = {TENANT})
  WITH CHECK (tenant_id = {TENANT});

-- BR-WRK-025 — append-only. A correction is a new row (`unassign`, then
-- `assign`), never an edit to the row that recorded what happened.
CREATE OR REPLACE FUNCTION work_assignment_append_only() RETURNS trigger AS $$
BEGIN
  -- ⚠ ONE `%` PER PLACEHOLDER, NOT TWO, AND THE DOUBLING CONVENTION NEXT DOOR
  -- IS RIGHT FOR A DIFFERENT EXECUTION PATH (`DEF-WRK-4027`, 2026-09-05).
  -- `integrations/0001_initial.py` documents doubling every `%` because
  -- `schema_editor.execute(sql)` defaults to `params=()`, and psycopg then
  -- does %-substitution: `%%` arrives at the server as one `%`. THIS migration
  -- runs through `PostgresOnlySQL`, a `RunSQL`, which passes `params=None` —
  -- so psycopg substitutes nothing and `%%` arrived VERBATIM. PL/pgSQL reads
  -- `%%` as a literal percent sign with no placeholder behind it, so the
  -- function had two arguments and nowhere to put them and PostgreSQL refused
  -- to compile it: *too many parameters specified for RAISE*. That refusal is
  -- at CREATE FUNCTION time, so it failed the whole migration and every
  -- PostgreSQL database on this branch stopped at this file.
  RAISE EXCEPTION 'BR-WRK-025: the assignment history is append-only; row % cannot be %. To change who has a job, add an unassign row and an assign row.',
    OLD.id, lower(TG_OP);
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_work_assignment_append_only ON work_order_assignments;
CREATE TRIGGER trg_work_assignment_append_only
  BEFORE UPDATE OR DELETE ON work_order_assignments
  FOR EACH ROW EXECUTE FUNCTION work_assignment_append_only();
"""

REVERSE = """
DROP TRIGGER IF EXISTS trg_work_assignment_append_only ON work_order_assignments;
DROP FUNCTION IF EXISTS work_assignment_append_only();
DROP POLICY IF EXISTS work_order_assignments_tenant_isolation ON work_order_assignments;
ALTER TABLE work_order_assignments NO FORCE ROW LEVEL SECURITY;
ALTER TABLE work_order_assignments DISABLE ROW LEVEL SECURITY;
"""


class Migration(migrations.Migration):
    dependencies = [("work", "0008_cr070_g_assignments")]

    operations = [PostgresOnlySQL(POLICY, reverse_sql=REVERSE)]
