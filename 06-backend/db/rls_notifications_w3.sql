-- rls_notifications_w3.sql — RLS policy for the platform-wide outbound queue.
-- HUMAN-OWNED (CLAUDE.md rule 1 🔒). HUMAN-REVIEW-PENDING — AI-authored
-- 2026-08-11 under the PO ruling of 2026-08-09, implementing the SIGNED B2 §3
-- template VERBATIM; row in 12-governance/09-human-review-ledger.md; applied by
-- apps/notifications/migrations/0002_rls_w3_outbound_queue.py (Postgres only).
--
-- Template (B2 §3, repeated per tenant-scoped table — deny-by-default: with
-- app.tenant_id unset, the ::uuid cast of '' fails and NO row is visible):
--   ALTER TABLE <t> ENABLE ROW LEVEL SECURITY;
--   ALTER TABLE <t> FORCE ROW LEVEL SECURITY;
--   CREATE POLICY <t>_tenant_isolation ON <t> USING/WITH CHECK tenant_id = app.tenant_id
--
-- ONE table, and it is the one that holds the personal data. B2 §3's original
-- list named `notifications`; r12 #16 replaced that table with this one, so the
-- policy lands here. Every row carries a customer's name, their service
-- address, their phone number or their email address, snapshotted at queue time
-- and kept for as long as the message is auditable. A cross-tenant read here is
-- a mailing list of another utility's customers.

ALTER TABLE outbound_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE outbound_messages FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS outbound_messages_tenant_isolation ON outbound_messages;
CREATE POLICY outbound_messages_tenant_isolation ON outbound_messages
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
