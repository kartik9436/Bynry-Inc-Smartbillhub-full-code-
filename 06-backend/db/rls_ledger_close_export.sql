-- rls_ledger_close_export.sql — RLS policies for `fiscal_period_closes` and
-- `export_batches` (EP-LED-05, US-LED-015 / US-LED-016).
-- HUMAN-OWNED (CLAUDE.md rule 1 🔒). HUMAN-REVIEW-PENDING — AI-authored
-- 2026-08-15 under the PO ruling of 2026-08-09, implementing the SIGNED B2 §3
-- template VERBATIM; row in 12-governance/09-human-review-ledger.md; applied by
-- apps/ledger/migrations/0007_je_number_close_export.py (Postgres only).
--
-- Template (B2 §3, repeated per tenant-scoped table — deny-by-default: with
-- app.tenant_id unset, the ::uuid cast of '' fails and NO row is visible):
--   ALTER TABLE <t> ENABLE ROW LEVEL SECURITY;
--   ALTER TABLE <t> FORCE ROW LEVEL SECURITY;
--   CREATE POLICY <t>_tenant_isolation ON <t> USING/WITH CHECK tenant_id = app.tenant_id
--
-- WHY THESE TWO TABLES NEED IT AS MUCH AS THE JOURNAL DOES.
-- `fiscal_period_closes` decides whether a money event may land in the month it
-- is dated (BR-TEN-038): a cross-tenant read here would let one utility's close
-- state auto-forward another utility's payment. `export_batches` is the record
-- that a month was handed to an accounting system — US-LED-016 TC-7 requires a
-- tenant's batches, codes and EXP- series to be its own, and a leaked row is
-- another utility's general-ledger totals, hash and QuickBooks refs.
--
-- Nothing here deviates from the template. The `<table>_tenant_isolation`
-- naming matches rls_ledger_w5.sql, which is what the migration's `drop_rls`
-- unwinds by name.

ALTER TABLE fiscal_period_closes ENABLE ROW LEVEL SECURITY;
ALTER TABLE fiscal_period_closes FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS fiscal_period_closes_tenant_isolation ON fiscal_period_closes;
CREATE POLICY fiscal_period_closes_tenant_isolation ON fiscal_period_closes
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE export_batches ENABLE ROW LEVEL SECURITY;
ALTER TABLE export_batches FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS export_batches_tenant_isolation ON export_batches;
CREATE POLICY export_batches_tenant_isolation ON export_batches
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
