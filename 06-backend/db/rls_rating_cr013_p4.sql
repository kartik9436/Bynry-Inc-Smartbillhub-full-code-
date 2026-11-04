-- rls_rating_cr013_p4.sql — RLS for the two tables CR-013 P4 adds (DEF-383).
-- HUMAN-OWNED (CLAUDE.md rule 1 🔒). HUMAN-REVIEW-PENDING — AI-authored
-- 2026-08-21 under the PO ruling of 2026-08-09, applying the SIGNED B2 §3
-- template VERBATIM, identically to db/rls_rating_cr013_p1.sql and
-- db/rls_rating_discounts.sql. Row in 12-governance/09-human-review-ledger.md;
-- applied by apps/rating/migrations/0017_cr013_p4_tax_fields.py (Postgres only).
--
-- Written IN THE SAME MIGRATION as the tables, not after. rls_rating_w1.sql
-- exists because a schema lane once documented its policies and ended before
-- writing them, and every table it named shipped unprotected.
--
-- ⚠ `tax_exemption_certificates` IS THE MOST SENSITIVE TABLE THIS MODULE HAS
-- ADDED SINCE `discount_enrolments`. Each row names ONE CUSTOMER OF ONE UTILITY
-- WHO DOES NOT PAY A TAX, with the certificate number that proves it. A leak
-- across tenants is a customer list and a regulator's exhibit at once, so
-- FORCE is on both tables and the policy is the deny-by-default template: with
-- app.tenant_id unset the ::uuid cast of '' fails and NO row is visible.
--
-- Template (B2 §3):
--   ALTER TABLE <t> ENABLE ROW LEVEL SECURITY;
--   ALTER TABLE <t> FORCE ROW LEVEL SECURITY;
--   CREATE POLICY <t>_tenant_isolation ON <t> USING/WITH CHECK tenant_id = app.tenant_id

ALTER TABLE tax_exemption_categories ENABLE ROW LEVEL SECURITY;
ALTER TABLE tax_exemption_categories FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tax_exemption_categories_tenant_isolation ON tax_exemption_categories;
CREATE POLICY tax_exemption_categories_tenant_isolation ON tax_exemption_categories
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE tax_exemption_certificates ENABLE ROW LEVEL SECURITY;
ALTER TABLE tax_exemption_certificates FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tax_exemption_certificates_tenant_isolation ON tax_exemption_certificates;
CREATE POLICY tax_exemption_certificates_tenant_isolation ON tax_exemption_certificates
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
