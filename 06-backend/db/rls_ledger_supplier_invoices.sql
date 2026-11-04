-- rls_ledger_supplier_invoices.sql — RLS policy for `supplier_invoices`
-- (EP-LED-06, US-LED-018 / US-LED-019 / US-LED-020).
-- HUMAN-OWNED (CLAUDE.md rule 1 🔒). HUMAN-REVIEW-PENDING — AI-authored
-- 2026-08-15 under the PO ruling of 2026-08-09, implementing the SIGNED B2 §3
-- template VERBATIM; a row in 12-governance/09-human-review-ledger.md is OWED
-- (12-governance/ is the Product Owner's to write — the lane report names this
-- file and the exact row it needs). Applied by
-- apps/ledger/migrations/0008_supplier_invoices.py (Postgres only).
--
-- Template (B2 §3, repeated per tenant-scoped table — deny-by-default: with
-- app.tenant_id unset, the ::uuid cast of '' fails and NO row is visible):
--   ALTER TABLE <t> ENABLE ROW LEVEL SECURITY;
--   ALTER TABLE <t> FORCE ROW LEVEL SECURITY;
--   CREATE POLICY <t>_tenant_isolation ON <t> USING/WITH CHECK tenant_id = app.tenant_id
--
-- WHY THIS TABLE NEEDS IT AS MUCH AS THE JOURNAL DOES.
-- `supplier_invoices` is what a utility PAID OUT and what it BOUGHT. A leaked
-- row is another utility's supplier list, its purchase prices and — through the
-- reconciliation built on it — its water loss percentage. J25 step 12 states
-- the requirement in full: Brazos Bend's CI-1..CI-9 must be unreachable from
-- Lone Star Ridge *"by id, by search, by filter, by drill-back, by CSV and by
-- export payload"*, and every one of those six paths reads this table.
--
-- The `supplier_name` column makes it sharper than most. It is FREE TEXT by
-- rule (BR-LED-028 forbids a vendor master), and the register searches it
-- server-side — so a search endpoint is a string oracle over the column, and
-- the app-layer filter is the only thing between it and every tenant's supplier
-- list. FORCE ROW LEVEL SECURITY is what makes that filter a belt beside a
-- brace instead of the whole defence.
--
-- Nothing here deviates from the template. The `<table>_tenant_isolation`
-- naming matches rls_ledger_w5.sql and rls_ledger_close_export.sql, which is
-- what the migration's `drop_rls` unwinds by name.

ALTER TABLE supplier_invoices ENABLE ROW LEVEL SECURITY;
ALTER TABLE supplier_invoices FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS supplier_invoices_tenant_isolation ON supplier_invoices;
CREATE POLICY supplier_invoices_tenant_isolation ON supplier_invoices
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
