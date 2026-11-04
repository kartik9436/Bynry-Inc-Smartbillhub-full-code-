# ── Trace ──────────────────────────────────────────────
# Change:  CR-165-BRC10 round 2 task 3 — the database locks on the tax chain.
# Defects: DEF-RAT-9281 (nothing stops two rows of one tax overlapping) ·
#          DEF-RAT-9276 (one code names one chain, not one row)
# Rules:   CLAUDE.md hard rule 1 (RLS FORCE on every tenant table) ·
#          B2 §2's no-overlap shape (`rating/0047`, `rating/0052`)
# Tests:   06-backend/tests/test_cr165_tax_versions_pg.py
# ───────────────────────────────────────────────────────
"""rating 0058 — PostgreSQL-only: the trigger, the two exclusions, and RLS.

🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING (migration ordering · RLS). Ledger row 2026-10-03.

1. **`trg_taxes_chain_default`** — a row inserted with no `chain_id` starts
   its own chain (`chain_id := id`) — or joins the chain of the row it
   corrects or follows — for any path that bypasses
   `Tax.save()` (a raw insert, a `bulk_create`). Then `chain_id` is NOT NULL.

2. **`ex_taxes_chain_no_overlap`** (`DEF-RAT-9281`) — two LIVE rows of one
   chain may not be in force on the same day. *Live* = not superseded by a
   correction, not deactivated, not a draft: a superseded row is the audit
   artefact of a mistake and keeps its window for ever, which is exactly a
   window its correction restates. The range is `[effective_from,
   effective_to + 1)` with NULL meaning unbounded on either side —
   `rating/0052`'s form. **DEFERRABLE INITIALLY DEFERRED**, because a
   correction inserts the new row BEFORE it can point the old row's
   `superseded_by` at it (the FK needs the new row to exist): for those few
   statements two live rows share a window, and the check runs at COMMIT.
   `new_tax_rate` ends the old row before inserting the new one, so it never
   needs the deferral.
   **Worked:** v1 6.25% open-ended plus v2 6.5% from 11/01/2026, both live,
   are refused at commit — v1 must end 10/31/2026 first, which is what
   `POST /taxes/{id}/new-rate` does in one transaction.

3. **`ex_taxes_code_one_chain`** (`DEF-RAT-9276`) — replaces 0056's dropped
   `uq_taxes_tenant_code_ci`: the same code (case-insensitive) in one tenant
   may only appear on rows of ONE chain. v1 and v2 of *TX-STATE* both read
   *TX-STATE*; a different tax may not take it.

4. **RLS on `tax_authority_accounts`** — `ENABLE` + `FORCE` + the B2 §3
   policy, exactly `work/0021`'s template. No `%` in this file (`RunSQL`
   passes `params=None`, `DEF-WRK-4027`).

SQLite gets none of it (no range type, no triggers worth the name, no RLS);
`Tax.save()` fills `chain_id` there and the services refuse an overlap and a
foreign code at the field.

DOWN PATH: drops both exclusions, the trigger and its function, makes
`chain_id` nullable again, and removes RLS from `tax_authority_accounts`.
Nothing is lost; the rows stay.
"""

from django.db import migrations

from core.migrationtools import PostgresOnlySQL

TENANT = "NULLIF(current_setting('app.tenant_id', true), '')::uuid"

FORWARD = f"""
CREATE OR REPLACE FUNCTION taxes_chain_default() RETURNS trigger AS $$
BEGIN
  IF NEW.chain_id IS NULL THEN
    NEW.chain_id := COALESCE(
      (SELECT t.chain_id FROM taxes t
        WHERE t.id = COALESCE(NEW.corrects_tax_id, NEW.follows_tax_id)),
      NEW.id
    );
  END IF;
  RETURN NEW;
END
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_taxes_chain_default
  BEFORE INSERT ON taxes
  FOR EACH ROW EXECUTE FUNCTION taxes_chain_default();

ALTER TABLE taxes ALTER COLUMN chain_id SET NOT NULL;

ALTER TABLE taxes
  ADD CONSTRAINT ex_taxes_chain_no_overlap
  EXCLUDE USING gist (
    chain_id WITH =,
    daterange(effective_from, effective_to + 1, '[)') WITH &&
  )
  WHERE (superseded_by_tax_id IS NULL AND deleted_at IS NULL AND NOT is_draft)
  DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE taxes
  ADD CONSTRAINT ex_taxes_code_one_chain
  EXCLUDE USING gist (
    tenant_id WITH =,
    (lower(code)) WITH =,
    chain_id WITH <>
  )
  WHERE (code IS NOT NULL);

ALTER TABLE tax_authority_accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE tax_authority_accounts FORCE ROW LEVEL SECURITY;
CREATE POLICY tax_authority_accounts_tenant_isolation ON tax_authority_accounts
  USING      (tenant_id = {TENANT})
  WITH CHECK (tenant_id = {TENANT});
"""

REVERSE = """
DROP POLICY IF EXISTS tax_authority_accounts_tenant_isolation ON tax_authority_accounts;
ALTER TABLE tax_authority_accounts NO FORCE ROW LEVEL SECURITY;
ALTER TABLE tax_authority_accounts DISABLE ROW LEVEL SECURITY;
ALTER TABLE taxes DROP CONSTRAINT IF EXISTS ex_taxes_code_one_chain;
ALTER TABLE taxes DROP CONSTRAINT IF EXISTS ex_taxes_chain_no_overlap;
ALTER TABLE taxes ALTER COLUMN chain_id DROP NOT NULL;
DROP TRIGGER IF EXISTS trg_taxes_chain_default ON taxes;
DROP FUNCTION IF EXISTS taxes_chain_default();
"""


class Migration(migrations.Migration):
    dependencies = [
        ("rating", "0057_cr165_tax_chain_backfill"),
        # btree_gist (uuid / text WITH = in a gist index) is installed there.
        ("rating", "0045_def_rat_8000_btree_gist"),
    ]

    operations = [PostgresOnlySQL(FORWARD, reverse_sql=REVERSE)]
