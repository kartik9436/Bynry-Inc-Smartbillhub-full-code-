# ── Trace ──────────────────────────────────────────────
# Change:  CR-166-BRC10 round 2 task 3 — the PostgreSQL-only half.
# Rules:   PO 2026-10-03 ruling 1 (approved = live on its start date) ·
#          DEF-RAT-8050 (one version in force per discount per day) ·
#          CLAUDE.md hard rule 1 (RLS FORCE on every tenant table)
# Tests:   06-backend/tests/test_cr166_discounts_round2_pg.py
# ───────────────────────────────────────────────────────
"""rating 0061 — RLS on the list table, and the overlap lock covers APPROVED.

🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING (RLS policy, migration ordering, a money
path). Row in `12-governance/09-human-review-ledger.md`, 2026-10-03,
CR-166-BRC10 r2 t3.

**1 · `discount_list_values` — ENABLE + FORCE RLS**, the policy every tenant
table in this module carries (`rating/0058`'s exact shape).

**2 · `ex_discount_versions_no_overlap` IS RE-CREATED OVER `active` AND
`scheduled`.** Ruling 1 makes approval the act that puts a version in force
from its start date, and `approve_discount_version` now writes `active` — so
an approved version is already inside the lock. `scheduled` is no longer
written by anything (0060 put every left-over one in force or reported it);
it is named in the predicate anyway, because `rating/0049`'s docstring proves
why it was kept OUT — *"the incumbent's open window contains every future
date"* — and that reason is gone: approval now closes the incumbent's window
the day before, in the same transaction, before the lock is checked at
COMMIT. A legacy `scheduled` row that overlaps an active one is therefore a
real double-pricing hazard and the database now says so. `0060` left any such
row `scheduled` and printed it; **this statement then fails on it by design**,
naming the constraint — resolve the printed rows and re-run.

DOWN PATH: drop the policy and RLS on `discount_list_values`; re-create the
lock with `rating/0049`'s original predicate (`status = 'active'`).
"""

from django.db import migrations

from core.migrationtools import PostgresOnlySQL

TENANT = "NULLIF(current_setting('app.tenant_id', true), '')::uuid"

FORWARD = f"""
ALTER TABLE discount_list_values ENABLE ROW LEVEL SECURITY;
ALTER TABLE discount_list_values FORCE ROW LEVEL SECURITY;
CREATE POLICY discount_list_values_tenant_isolation ON discount_list_values
  USING      (tenant_id = {TENANT})
  WITH CHECK (tenant_id = {TENANT});

ALTER TABLE discount_versions DROP CONSTRAINT IF EXISTS ex_discount_versions_no_overlap;
ALTER TABLE discount_versions
  ADD CONSTRAINT ex_discount_versions_no_overlap
  EXCLUDE USING gist (
    tenant_id WITH =,
    discount_id WITH =,
    daterange(effective_from, COALESCE(effective_to + 1, 'infinity'::date)) WITH &&
  )
  WHERE (status IN ('active', 'scheduled') AND effective_from IS NOT NULL)
  DEFERRABLE INITIALLY DEFERRED;
"""

REVERSE = """
ALTER TABLE discount_versions DROP CONSTRAINT IF EXISTS ex_discount_versions_no_overlap;
ALTER TABLE discount_versions
  ADD CONSTRAINT ex_discount_versions_no_overlap
  EXCLUDE USING gist (
    tenant_id WITH =,
    discount_id WITH =,
    daterange(effective_from, COALESCE(effective_to + 1, 'infinity'::date)) WITH &&
  )
  WHERE (status = 'active' AND effective_from IS NOT NULL)
  DEFERRABLE INITIALLY DEFERRED;
DROP POLICY IF EXISTS discount_list_values_tenant_isolation ON discount_list_values;
ALTER TABLE discount_list_values NO FORCE ROW LEVEL SECURITY;
ALTER TABLE discount_list_values DISABLE ROW LEVEL SECURITY;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("rating", "0060_cr166_discount_list_backfill"),
        ("rating", "0049_def_rat_8050_discount_no_overlap"),
    ]

    operations = [PostgresOnlySQL(FORWARD, reverse_sql=REVERSE)]
