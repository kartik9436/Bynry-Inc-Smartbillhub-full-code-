-- rls_notifications_in_app.sql — RLS for the in-app message store (BR-NOT-019).
-- HUMAN-OWNED (CLAUDE.md rule 1 🔒). HUMAN-REVIEW-PENDING — AI-authored
-- 2026-08-17 under the PO ruling of 2026-08-09, implementing the SIGNED B2 §3
-- template VERBATIM; row in 12-governance/09-human-review-ledger.md; applied by
-- apps/notifications/migrations/0012_rls_cr009_in_app_messages.py
-- (Postgres only).
--
-- Template (B2 §3, repeated per tenant-scoped table — deny-by-default: with
-- app.tenant_id unset, the ::uuid cast of '' fails and NO row is visible):
--   ALTER TABLE <t> ENABLE ROW LEVEL SECURITY;
--   ALTER TABLE <t> FORCE ROW LEVEL SECURITY;
--   CREATE POLICY <t>_tenant_isolation ON <t> USING/WITH CHECK tenant_id = app.tenant_id
--
-- WHAT A CROSS-TENANT READ WOULD EXPOSE HERE, which is why this table gets the
-- policy on the day it is created rather than the day someone notices. Every
-- row holds a RENDERED MESSAGE BODY — the same artifact the queue row would have
-- handed a provider. A bulk-run summary names how many accounts a utility
-- billed and how many failed; a test message carries whatever the utility's own
-- template says. Read across a tenant boundary that is one utility reading
-- another utility's operational figures out of a bell menu, with no request
-- against their own data to explain where it came from.
--
-- WITH CHECK matters as much as USING, for the reason the settings policy one
-- level up states: a delivery WRITE that landed in the wrong tenant would put a
-- message in a stranger's inbox, and the recipient would have no way to tell
-- that it was not theirs.
--
-- ⚠ THIS IS TENANT ISOLATION AND NOT PER-USER ISOLATION, and the difference is
-- deliberate. RLS answers "which tenant's rows exist"; WHOSE INBOX is answered
-- by `apps/notifications/in_app.py`, which scopes every single read and write to
-- `user_id = the signed-in user` and has no callable that takes a user id from a
-- request. Putting `app.user_id` into a policy would mean a second session
-- variable that every job, migration and management command must also set
-- correctly — a guarantee with far more places to be forgotten than one service
-- module with four functions in it.

ALTER TABLE in_app_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE in_app_messages FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS in_app_messages_tenant_isolation ON in_app_messages;
CREATE POLICY in_app_messages_tenant_isolation ON in_app_messages
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
