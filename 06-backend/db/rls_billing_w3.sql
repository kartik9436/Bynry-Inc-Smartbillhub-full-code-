-- rls_billing_w3.sql — RLS policies for the W3 billing invoice-core tables.
-- HUMAN-OWNED (CLAUDE.md rule 1 🔒). HUMAN-REVIEW-PENDING — AI-authored
-- 2026-08-11 under the PO ruling of 2026-08-09, implementing the SIGNED B2 §3
-- template VERBATIM per table; row in 12-governance/09-human-review-ledger.md;
-- applied by apps/billing/migrations/0002_rls_w3_and_immutability.py
-- (Postgres only).
--
-- Template (B2 §3, repeated per tenant-scoped table — deny-by-default: with
-- app.tenant_id unset, the ::uuid cast of '' fails and NO row is visible):
--   ALTER TABLE <t> ENABLE ROW LEVEL SECURITY;
--   ALTER TABLE <t> FORCE ROW LEVEL SECURITY;
--   CREATE POLICY <t>_tenant_isolation ON <t> USING/WITH CHECK tenant_id = app.tenant_id
--
-- Six tables, and every one of them holds money or names who owes it. These
-- are the rows a cross-tenant read would be worst on.

ALTER TABLE bill_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE bill_runs FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS bill_runs_tenant_isolation ON bill_runs;
CREATE POLICY bill_runs_tenant_isolation ON bill_runs
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE bill_run_exclusions ENABLE ROW LEVEL SECURITY;
ALTER TABLE bill_run_exclusions FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS bill_run_exclusions_tenant_isolation ON bill_run_exclusions;
CREATE POLICY bill_run_exclusions_tenant_isolation ON bill_run_exclusions
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE invoices ENABLE ROW LEVEL SECURITY;
ALTER TABLE invoices FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS invoices_tenant_isolation ON invoices;
CREATE POLICY invoices_tenant_isolation ON invoices
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE invoice_lines ENABLE ROW LEVEL SECURITY;
ALTER TABLE invoice_lines FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS invoice_lines_tenant_isolation ON invoice_lines;
CREATE POLICY invoice_lines_tenant_isolation ON invoice_lines
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE adjustments ENABLE ROW LEVEL SECURITY;
ALTER TABLE adjustments FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS adjustments_tenant_isolation ON adjustments;
CREATE POLICY adjustments_tenant_isolation ON adjustments
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE credit_notes ENABLE ROW LEVEL SECURITY;
ALTER TABLE credit_notes FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS credit_notes_tenant_isolation ON credit_notes;
CREATE POLICY credit_notes_tenant_isolation ON credit_notes
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
