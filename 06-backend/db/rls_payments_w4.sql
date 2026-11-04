-- rls_payments_w4.sql — RLS policies for the W4 payments closed-loop tables.
-- HUMAN-OWNED (CLAUDE.md rule 1 🔒). HUMAN-REVIEW-PENDING — AI-authored
-- 2026-08-11 under the PO ruling of 2026-08-09, implementing the SIGNED B2 §3
-- template VERBATIM per table; row in 12-governance/09-human-review-ledger.md;
-- applied by apps/payments/migrations/0002_rls_w4_and_immutability.py
-- (Postgres only).
--
-- Template (B2 §3, repeated per tenant-scoped table — deny-by-default: with
-- app.tenant_id unset, the ::uuid cast of '' fails and NO row is visible):
--   ALTER TABLE <t> ENABLE ROW LEVEL SECURITY;
--   ALTER TABLE <t> FORCE ROW LEVEL SECURITY;
--   CREATE POLICY <t>_tenant_isolation ON <t> USING/WITH CHECK tenant_id = app.tenant_id
--
-- B2 §3 names both of these tables in its apply-to list. `payments` holds the
-- money a customer handed over and `allocations` says which of their bills it
-- met — a cross-tenant read here is somebody else's bank position.

ALTER TABLE payments ENABLE ROW LEVEL SECURITY;
ALTER TABLE payments FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS payments_tenant_isolation ON payments;
CREATE POLICY payments_tenant_isolation ON payments
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE allocations ENABLE ROW LEVEL SECURITY;
ALTER TABLE allocations FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS allocations_tenant_isolation ON allocations;
CREATE POLICY allocations_tenant_isolation ON allocations
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
