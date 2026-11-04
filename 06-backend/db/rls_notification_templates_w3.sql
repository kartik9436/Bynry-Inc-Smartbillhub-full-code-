-- rls_notification_templates_w3.sql — RLS for the template registry and its
-- append-only version rows (US-NOT-006).
--
-- HUMAN-OWNED (CLAUDE.md rule 1 🔒). HUMAN-REVIEW-PENDING — AI-authored
-- 2026-08-15 under the PO ruling of 2026-08-09, implementing the SIGNED B2 §3
-- template VERBATIM; row required in 12-governance/09-human-review-ledger.md;
-- applied by apps/notifications/migrations/0006_rls_w3_notification_templates.py
-- (Postgres only).
--
-- Template (B2 §3, repeated per tenant-scoped table — deny-by-default: with
-- app.tenant_id unset, the ::uuid cast of '' fails and NO row is visible):
--   ALTER TABLE <t> ENABLE ROW LEVEL SECURITY;
--   ALTER TABLE <t> FORCE ROW LEVEL SECURITY;
--   CREATE POLICY <t>_tenant_isolation ON <t> USING/WITH CHECK tenant_id = app.tenant_id
--
-- WHAT A LEAK WOULD BE HERE. These rows hold no customer's name — they hold the
-- utility's own words: the letters it sends, the tone it takes, the terms of its
-- contracts, its regulatory footer. A cross-tenant READ hands one utility the
-- drafting of another's legal notices and contracts. A cross-tenant WRITE is
-- worse and quieter: publish a version into a neighbour's registry and their
-- next disconnect notice renders a body they never wrote, on their letterhead,
-- to their customers, with their own audit trail showing nothing but a normal
-- dispatch. WITH CHECK is what refuses that, and FORCE is what applies the
-- policy to the table owner too — without it the application role (a superuser
-- in dev/CI) would be exempt and the guarantee would live only in this comment.
--
-- The version rows are ALSO protected by the append-only trigger installed in
-- the same migration. The two answer different questions: RLS decides WHOSE rows
-- you can touch, the trigger decides WHAT may change on one you legitimately own
-- (CLAUDE.md rule 4 — a published body is evidence of what a customer was sent).

ALTER TABLE notification_templates ENABLE ROW LEVEL SECURITY;
ALTER TABLE notification_templates FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS notification_templates_tenant_isolation ON notification_templates;
CREATE POLICY notification_templates_tenant_isolation ON notification_templates
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE notification_template_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE notification_template_versions FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS notification_template_versions_tenant_isolation ON notification_template_versions;
CREATE POLICY notification_template_versions_tenant_isolation ON notification_template_versions
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
