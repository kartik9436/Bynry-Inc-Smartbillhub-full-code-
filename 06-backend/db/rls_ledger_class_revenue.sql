-- rls_ledger_class_revenue.sql — RLS policy for `ledger_service_class_revenue_accounts`
-- (CR-197-BRC10, BR-LED-801: a service's revenue account per customer class).
-- HUMAN-OWNED (CLAUDE.md rule 1 🔒). HUMAN-REVIEW-PENDING — AI-authored
-- 2026-10-29 under the PO ruling of 2026-08-09, implementing the SIGNED B2 §3
-- template VERBATIM; the row in 12-governance/09-human-review-ledger.md is
-- written in the same commit. Applied by
-- apps/ledger/migrations/0022_cr197_class_revenue_and_refund_role.py (Postgres only).
--
-- WHY IT NEEDS IT: a row decides which of a utility's accounts a bill's revenue
-- lands in. Another tenant reading it learns that utility's chart; another
-- tenant WRITING one would misdirect its revenue on every bill it issues.
-- Nothing here deviates from the template.

ALTER TABLE ledger_service_class_revenue_accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE ledger_service_class_revenue_accounts FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS ledger_service_class_revenue_accounts_tenant_isolation ON ledger_service_class_revenue_accounts;
CREATE POLICY ledger_service_class_revenue_accounts_tenant_isolation ON ledger_service_class_revenue_accounts
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
