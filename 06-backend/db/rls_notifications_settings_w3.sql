-- rls_notifications_settings_w3.sql — RLS policy for the tenant dispatch config.
-- HUMAN-OWNED (CLAUDE.md rule 1 🔒). HUMAN-REVIEW-PENDING — AI-authored
-- 2026-08-15 under the PO ruling of 2026-08-09, implementing the SIGNED B2 §3
-- template VERBATIM; row in 12-governance/09-human-review-ledger.md; applied by
-- apps/notifications/migrations/0004_rls_w3_notification_settings.py (Postgres
-- only).
--
-- Template (B2 §3, repeated per tenant-scoped table — deny-by-default: with
-- app.tenant_id unset, the ::uuid cast of '' fails and NO row is visible):
--   ALTER TABLE <t> ENABLE ROW LEVEL SECURITY;
--   ALTER TABLE <t> FORCE ROW LEVEL SECURITY;
--   CREATE POLICY <t>_tenant_isolation ON <t> USING/WITH CHECK tenant_id = app.tenant_id
--
-- This table holds no customer data at all, which is exactly why it still needs
-- the policy and why saying so matters. It holds the numbers that govern how a
-- utility's messages leave the building: the batch size, and the hours of the
-- day it is allowed to text people. A cross-tenant WRITE here does not leak one
-- row — it moves another utility's quiet-hours window, and the consequence
-- lands as a 23:00 text message to their customers (T5-23), on their letterhead,
-- with nothing in their own audit trail explaining it. Read isolation matters
-- least on this table and write isolation matters most, which is what FORCE +
-- WITH CHECK is for.

ALTER TABLE notification_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE notification_settings FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS notification_settings_tenant_isolation ON notification_settings;
CREATE POLICY notification_settings_tenant_isolation ON notification_settings
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
