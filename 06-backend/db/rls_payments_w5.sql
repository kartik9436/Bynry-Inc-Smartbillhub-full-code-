-- rls_payments_w5.sql — RLS policies for the W5 deposit-batch + bank-rec tables.
-- HUMAN-OWNED (CLAUDE.md rule 1 🔒). HUMAN-REVIEW-PENDING — AI-authored
-- 2026-08-11 under the PO ruling of 2026-08-09, implementing the SIGNED B2 §3
-- template VERBATIM per table; row in 12-governance/09-human-review-ledger.md;
-- applied by apps/payments/migrations/0005_rls_w5_bankrec_and_lock.py
-- (Postgres only).
--
-- Template (B2 §3, repeated per tenant-scoped table — deny-by-default: with
-- app.tenant_id unset, the ::uuid cast of '' fails and NO row is visible):
--   ALTER TABLE <t> ENABLE ROW LEVEL SECURITY;
--   ALTER TABLE <t> FORCE ROW LEVEL SECURITY;
--   CREATE POLICY <t>_tenant_isolation ON <t> USING/WITH CHECK tenant_id = app.tenant_id
--
-- B2 §3's apply-to list names `deposit_batches` and `bank_lines` by name. The
-- other four tables are r14 #1 / r12 #10 / US-PAY-023 §5 additions and take the
-- SAME template, because each of them says how much money a tenant banked on a
-- given day: a cross-tenant read here is somebody else's bank position, their
-- statement file and their explanation of why it did not tie.

ALTER TABLE bank_accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE bank_accounts FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS bank_accounts_tenant_isolation ON bank_accounts;
CREATE POLICY bank_accounts_tenant_isolation ON bank_accounts
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE deposit_batches ENABLE ROW LEVEL SECURITY;
ALTER TABLE deposit_batches FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS deposit_batches_tenant_isolation ON deposit_batches;
CREATE POLICY deposit_batches_tenant_isolation ON deposit_batches
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE deposit_batch_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE deposit_batch_events FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS deposit_batch_events_tenant_isolation ON deposit_batch_events;
CREATE POLICY deposit_batch_events_tenant_isolation ON deposit_batch_events
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE bank_statement_imports ENABLE ROW LEVEL SECURITY;
ALTER TABLE bank_statement_imports FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS bank_statement_imports_tenant_isolation ON bank_statement_imports;
CREATE POLICY bank_statement_imports_tenant_isolation ON bank_statement_imports
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE bank_lines ENABLE ROW LEVEL SECURITY;
ALTER TABLE bank_lines FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS bank_lines_tenant_isolation ON bank_lines;
CREATE POLICY bank_lines_tenant_isolation ON bank_lines
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE bank_rec_resolutions ENABLE ROW LEVEL SECURITY;
ALTER TABLE bank_rec_resolutions FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS bank_rec_resolutions_tenant_isolation ON bank_rec_resolutions;
CREATE POLICY bank_rec_resolutions_tenant_isolation ON bank_rec_resolutions
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
