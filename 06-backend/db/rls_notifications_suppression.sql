-- rls_notifications_suppression.sql — RLS for the do-not-send list
-- (DEF-NOT-5632). HUMAN-OWNED (CLAUDE.md rule 1 🔒). HUMAN-REVIEW-PENDING —
-- AI-authored 2026-09-17 under the PO ruling of 2026-08-09, implementing the
-- SIGNED B2 §3 template VERBATIM; row in
-- 12-governance/09-human-review-ledger.md; applied by
-- apps/notifications/migrations/0020_rls_def_not_5632_suppressed_addresses.py
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
-- row is a CUSTOMER'S EMAIL ADDRESS OR PHONE NUMBER (BR-CUS-045 — every contact
-- column is PII) paired with a fact about that person: that their mailbox is
-- dead, or — worse to leak — that they reported this utility's mail as spam, or
-- that they unsubscribed. Read across a tenant boundary, that is one utility
-- obtaining another utility's customer contact list, already filtered down to
-- the people most likely to be annoyed with them, with a reason code attached.
-- It is a better marketing list than anything either utility owns legitimately.
--
-- WITH CHECK matters as much as USING, and here it matters MORE than on most
-- tables in this schema. A suppression WRITE that landed in the wrong tenant
-- would silently stop a DIFFERENT utility sending to that address — their bills
-- would be written, marked held, and never dispatched, and the clerk looking at
-- the blocked-addresses screen would see an address blocked by an event that
-- never happened on their system. The failure is silent on both sides: nothing
-- errors, nothing is lost, and a customer simply stops receiving email.
--
-- ⚠ THE `address` COLUMN IS NOT ENCRYPTED, AND THAT IS A DELIBERATE MATCH TO
-- THE ROW IT GUARDS RATHER THAN AN OVERSIGHT. `outbound_messages.
-- recipient_address` holds the same value in clear on the same deployment,
-- because a queue row has to be handed to a provider as itself; an encrypted
-- column here could not be compared against it in the dispatcher's selection
-- predicate without decrypting the whole table on every cycle. Encrypting this
-- one column would move no secret out of reach while making the guarantee
-- unenforceable, so tenant isolation is the whole of the protection and is
-- stated here rather than assumed. DB-15's app-layer encryption applies to the
-- high-sensitivity columns it names; a delivery address on a queue rail is not
-- one of them TODAY, and if that changes it changes for both tables at once.

ALTER TABLE suppressed_addresses ENABLE ROW LEVEL SECURITY;
ALTER TABLE suppressed_addresses FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS suppressed_addresses_tenant_isolation ON suppressed_addresses;
CREATE POLICY suppressed_addresses_tenant_isolation ON suppressed_addresses
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
