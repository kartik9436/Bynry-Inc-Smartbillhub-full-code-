-- rls_audit_w0.sql — RLS policy for audit_log (BR-AUD-007). HUMAN-OWNED
-- (CLAUDE.md rule 1 🔒). HUMAN-REVIEW-PENDING — AI-authored 2026-08-09 under PO
-- ruling 2026-08-09, implementing the SIGNED B2 §3 template VERBATIM;
-- row in 12-governance/09-human-review-ledger.md; applied by
-- apps/audit/migrations/0002_rls_w0_policies.py (Postgres only).
--
-- Applied to the PARTITIONED PARENT: every query through the parent is
-- tenant-filtered regardless of which monthly partition serves it (US-AUD-001
-- TC-5/TC-6 — the WITH CHECK clause also blocks forged cross-tenant INSERTs).

ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_log FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS audit_log_tenant_isolation ON audit_log;
CREATE POLICY audit_log_tenant_isolation ON audit_log
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
