-- rls_notifications_cr009_rules.sql — RLS for the SET-12 notification rules.
-- HUMAN-OWNED (CLAUDE.md rule 1 🔒). HUMAN-REVIEW-PENDING — AI-authored
-- 2026-08-17 under the PO ruling of 2026-08-09, implementing the SIGNED B2 §3
-- template VERBATIM; row in 12-governance/09-human-review-ledger.md; applied by
-- apps/notifications/migrations/0010_rls_cr009_notification_rules.py
-- (Postgres only).
--
-- Template (B2 §3, repeated per tenant-scoped table — deny-by-default: with
-- app.tenant_id unset, the ::uuid cast of '' fails and NO row is visible):
--   ALTER TABLE <t> ENABLE ROW LEVEL SECURITY;
--   ALTER TABLE <t> FORCE ROW LEVEL SECURITY;
--   CREATE POLICY <t>_tenant_isolation ON <t> USING/WITH CHECK tenant_id = app.tenant_id
--
-- WHAT A CROSS-TENANT WRITE WOULD DO HERE, which is why WITH CHECK matters more
-- than USING on both of these tables — the same argument
-- rls_notifications_settings_w3.sql makes, one level up. These rows do not hold
-- a customer's name; they hold WHICH customers get contacted and how. Flipping
-- another utility's `past_due_reminder` off stops every chasing letter they
-- send, silently, with nothing in their own audit trail to explain it: their
-- receivables age, their disconnect ladder never starts, and the first sign is
-- a month-end number nobody can account for. Flipping `disconnect_notice` ON
-- for a tenant who had it off starts posting regulated letters at real postage
-- to customers who were never meant to receive one.
--
-- `notification_rule_channels` carries its OWN tenant_id rather than relying on
-- its parent's, deliberately: a policy that reached through the FK would make
-- every channel read a join, and a child row whose tenant disagrees with its
-- parent's is a bug this schema can then refuse rather than one it has to
-- reason about.

ALTER TABLE notification_rules ENABLE ROW LEVEL SECURITY;
ALTER TABLE notification_rules FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS notification_rules_tenant_isolation ON notification_rules;
CREATE POLICY notification_rules_tenant_isolation ON notification_rules
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE notification_rule_channels ENABLE ROW LEVEL SECURITY;
ALTER TABLE notification_rule_channels FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS notification_rule_channels_tenant_isolation ON notification_rule_channels;
CREATE POLICY notification_rule_channels_tenant_isolation ON notification_rule_channels
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
