-- rls_payments_refunds.sql — RLS policy for `refunds` (EP-PAY-03, US-PAY-011).
-- HUMAN-OWNED (CLAUDE.md rule 1 🔒). HUMAN-REVIEW-PENDING — AI-authored
-- 2026-08-11 under the PO ruling of 2026-08-09, implementing the SIGNED B2 §3
-- template VERBATIM; row in 12-governance/09-human-review-ledger.md; applied by
-- apps/payments/migrations/0004_w4_reversal_and_refunds.py (Postgres only).
--
-- Template (B2 §3, repeated per tenant-scoped table — deny-by-default: with
-- app.tenant_id unset, the ::uuid cast of '' fails and NO row is visible):
--   ALTER TABLE <t> ENABLE ROW LEVEL SECURITY;
--   ALTER TABLE <t> FORCE ROW LEVEL SECURITY;
--   CREATE POLICY <t>_tenant_isolation ON <t> USING/WITH CHECK tenant_id = app.tenant_id
--
-- B2 §3 names `refunds` in its apply-to list by name. This table records money
-- the utility PAID OUT and the cheque number it went out on; a cross-tenant
-- read here is somebody else's bank account being emptied on paper.
--
-- Nothing here deviates from the template. The policy name follows the same
-- `<table>_tenant_isolation` convention as rls_payments_w4.sql, which is what
-- `drop_rls` in the migration unwinds by name.

ALTER TABLE refunds ENABLE ROW LEVEL SECURITY;
ALTER TABLE refunds FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS refunds_tenant_isolation ON refunds;
CREATE POLICY refunds_tenant_isolation ON refunds
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
