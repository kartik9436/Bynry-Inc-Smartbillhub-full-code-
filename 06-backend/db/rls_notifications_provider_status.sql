-- HUMAN-OWNED (RLS policies are a CLAUDE.md 🔒 path). HUMAN-REVIEW-PENDING —
-- AI-authored 2026-10-29 (CR-198-BRC10) under the PO ruling of 2026-08-09.
-- The SIGNED B2 §3 template, verbatim, applied to one new table. Deny by
-- default: with app.tenant_id unset no row is visible. FORCE applies it to the
-- table owner too.
ALTER TABLE provider_status_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE provider_status_events FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS provider_status_events_tenant_isolation ON provider_status_events;
CREATE POLICY provider_status_events_tenant_isolation ON provider_status_events
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
