-- rls_ledger_tax_remittances.sql — RLS policy for `tax_remittances`
-- (B2 Addendum r13 #3; Finance blueprint `P4.4`, p017 and p058).
-- HUMAN-OWNED (CLAUDE.md rule 1 🔒). HUMAN-REVIEW-PENDING — AI-authored
-- 2026-09-24 under the PO ruling of 2026-08-09, implementing the SIGNED B2 §3
-- template VERBATIM; the row in 12-governance/09-human-review-ledger.md is
-- written in the same commit. Applied by
-- apps/ledger/migrations/0020_p4_4_tax_remittances.py (Postgres only).
--
-- Template (B2 §3, repeated per tenant-scoped table — deny-by-default: with
-- app.tenant_id unset, the ::uuid cast of '' fails and NO row is visible):
--   ALTER TABLE <t> ENABLE ROW LEVEL SECURITY;
--   ALTER TABLE <t> FORCE ROW LEVEL SECURITY;
--   CREATE POLICY <t>_tenant_isolation ON <t> USING/WITH CHECK tenant_id = app.tenant_id
--
-- WHY THIS TABLE NEEDS IT AS MUCH AS THE JOURNAL DOES.
-- A row here is a utility's TAX FILING: which authorities it files with, on
-- which basis, what it paid each of them, when, and the confirmation reference
-- the authority issued. A leaked row is another utility's tax position and its
-- filing history — and `confirmation_ref` is the authority's own identifier for
-- that return, which is the one string that could be used against them at the
-- authority's end.
--
-- It also carries the SOURCE of a screen a clerk searches. The Payments-made
-- panel searches authority and confirmation server-side, so that endpoint is a
-- string oracle over this table, and the app-layer tenant filter is the only
-- thing between it and every tenant's filings. FORCE ROW LEVEL SECURITY is what
-- makes that filter a belt beside a brace rather than the whole defence — the
-- same argument `rls_ledger_supplier_invoices.sql` makes about `supplier_name`.
--
-- ⚠ THE RECEIPT IS NOT IN THIS TABLE AND IS NOT COVERED BY THIS POLICY.
-- A filing's receipt is a `stored_documents` row found by `source_type` +
-- `source_id` (tenancy/0052), and that table carries its own policy from
-- tenancy/0025. Said here because a reader looking for the attachment's
-- isolation would otherwise look for it in the wrong file.
--
-- Nothing here deviates from the template. The `<table>_tenant_isolation`
-- naming matches rls_ledger_w5.sql, rls_ledger_close_export.sql and
-- rls_ledger_supplier_invoices.sql, which is what the migration's `drop_rls`
-- unwinds by name.

ALTER TABLE tax_remittances ENABLE ROW LEVEL SECURITY;
ALTER TABLE tax_remittances FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tax_remittances_tenant_isolation ON tax_remittances;
CREATE POLICY tax_remittances_tenant_isolation ON tax_remittances
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
