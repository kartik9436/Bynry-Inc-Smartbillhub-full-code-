-- rls_tenancy_custom_field.sql — RLS policy for `custom_field` (B2 addendum
-- r17.1). HUMAN-OWNED (CLAUDE.md rule 1 🔒). HUMAN-REVIEW-PENDING —
-- AI-authored 2026-08-11 under PO ruling 2026-08-09, implementing the SIGNED
-- B2 §3 template VERBATIM; row in 12-governance/09-human-review-ledger.md;
-- applied by apps/tenancy/migrations/0008_rls_custom_field.py (Postgres only).
--
-- Template (B2 §3, deny-by-default: with app.tenant_id unset, the ::uuid cast
-- of '' fails and NO row is visible):
--   ALTER TABLE <t> ENABLE ROW LEVEL SECURITY;
--   ALTER TABLE <t> FORCE ROW LEVEL SECURITY;
--   CREATE POLICY <t>_tenant_isolation ON <t> USING/WITH CHECK tenant_id = app.tenant_id
--
-- WHY THIS TABLE IS NOT AN EXCEPTION, stated because it looks like one. A
-- custom-field DEFINITION is configuration, not customer data, and the two
-- neighbouring platform catalogs (services, subscription_plans) are RLS-exempt
-- for exactly that reason. This one is not: BR-TEN-046 is explicit — "no tenant
-- can alter another tenant's field set, and no tenant's fields are visible to
-- another". The definitions carry a tenant's own vocabulary (`label`,
-- `help_text` are tenant PROSE per r17.5) and they decide what is stamped onto
-- that tenant's invoices, so a leak here is both a disclosure and a document
-- defect. US-TEN-014 TC-6, US-TEN-015 TC-9, US-TEN-016 TC-8 and US-BIL-028
-- TC-10 are the same statement from four directions.
--
-- The values themselves need nothing new: `custom_data` is a COLUMN on
-- accounts / contacts / addresses / service_agreements / premises / units /
-- service_points / assets, every one of which already carries ENABLE + FORCE
-- from its own module's RLS migration. That is a second, unadvertised benefit
-- of r17.2's "a column on the owning row, not a shared value table" — the
-- shared table would have needed its own policy, and would have been the one
-- table in the product where eight modules' isolation depended on one row.

ALTER TABLE custom_field ENABLE ROW LEVEL SECURITY;
ALTER TABLE custom_field FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS custom_field_tenant_isolation ON custom_field;
CREATE POLICY custom_field_tenant_isolation ON custom_field
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

