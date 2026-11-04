-- rls_ledger_w5.sql — RLS policies for the W5 ledger journal-core tables.
-- HUMAN-OWNED (CLAUDE.md rule 1 🔒). HUMAN-REVIEW-PENDING — AI-authored
-- 2026-08-11 under the PO ruling of 2026-08-09, implementing the SIGNED B2 §3
-- template VERBATIM per table; row in 12-governance/09-human-review-ledger.md;
-- applied by apps/ledger/migrations/0002_rls_w5_and_immutability.py
-- (Postgres only).
--
-- Template (B2 §3, repeated per tenant-scoped table — deny-by-default: with
-- app.tenant_id unset, the ::uuid cast of '' fails and NO row is visible):
--   ALTER TABLE <t> ENABLE ROW LEVEL SECURITY;
--   ALTER TABLE <t> FORCE ROW LEVEL SECURITY;
--   CREATE POLICY <t>_tenant_isolation ON <t> USING/WITH CHECK tenant_id = app.tenant_id
--
-- All three tables are named in B2 §3's own apply-to list. `journal_lines` is
-- the row every money figure in the product is summed from, and `ledger_accounts`
-- is the chart those figures are grouped by — a cross-tenant read here is one
-- tenant reading another's entire books, not one record.

ALTER TABLE ledger_accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE ledger_accounts FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS ledger_accounts_tenant_isolation ON ledger_accounts;
CREATE POLICY ledger_accounts_tenant_isolation ON ledger_accounts
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE journal_entries ENABLE ROW LEVEL SECURITY;
ALTER TABLE journal_entries FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS journal_entries_tenant_isolation ON journal_entries;
CREATE POLICY journal_entries_tenant_isolation ON journal_entries
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE journal_lines ENABLE ROW LEVEL SECURITY;
ALTER TABLE journal_lines FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS journal_lines_tenant_isolation ON journal_lines;
CREATE POLICY journal_lines_tenant_isolation ON journal_lines
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
