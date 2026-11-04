-- rls_identity_w0.sql — RLS policies for the W0 identity tables. HUMAN-OWNED
-- (CLAUDE.md rule 1 🔒). HUMAN-REVIEW-PENDING — AI-authored 2026-08-09 under PO
-- ruling 2026-08-09, implementing the SIGNED B2 §3 template VERBATIM per table;
-- row in 12-governance/09-human-review-ledger.md; applied by
-- apps/identity/migrations/0002_rls_w0_policies.py (Postgres only).
--
-- `users` IS in this list: B2 r16 #2 (r11 per-tenant identity) voids the stale
-- §3 no-RLS listing for users — users are tenant-scoped rows now (BR-IDN-029).
-- RLS-exempt (platform catalog per B2 §3): roles · permissions · role_permissions.

ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE users FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS users_tenant_isolation ON users;
CREATE POLICY users_tenant_isolation ON users
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE tenant_memberships ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenant_memberships FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_memberships_tenant_isolation ON tenant_memberships;
CREATE POLICY tenant_memberships_tenant_isolation ON tenant_memberships
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
