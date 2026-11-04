-- rls_rating_discounts.sql — RLS policies for the six CR-013 part-3 discount
-- tables. HUMAN-OWNED (CLAUDE.md rule 1 🔒). HUMAN-REVIEW-PENDING — AI-authored
-- 2026-08-19 under the PO ruling of 2026-08-09 ("AI will do it; we will review
-- it later as human"), implementing the SIGNED B2 §3 template VERBATIM per
-- table; row in 12-governance/09-human-review-ledger.md; applied by
-- apps/rating/migrations/0009_cr013_discounts.py (Postgres only).
--
-- ⚠ WRITTEN IN THE SAME MIGRATION THAT CREATES THE TABLES, and that is the
-- point. `rating 0003_rls_w1_policies` exists because the W1 schema lane
-- DOCUMENTED these policies in the models and ended before writing them, so
-- nine tables shipped with no isolation at all and a later pass had to notice.
-- CLAUDE.md rule 1 admits no gap, so there is no window here in which a
-- `discount_enrolments` row — which names a customer, a subsidy and a proof of
-- income — is readable across tenants.
--
-- Template (B2 §3, repeated per tenant-scoped table — deny-by-default: with
-- app.tenant_id unset, the ::uuid cast of '' fails and NO row is visible):
--   ALTER TABLE <t> ENABLE ROW LEVEL SECURITY;
--   ALTER TABLE <t> FORCE ROW LEVEL SECURITY;
--   CREATE POLICY <t>_tenant_isolation ON <t> USING/WITH CHECK tenant_id = app.tenant_id
--
-- Every one of the six carries `tenant_id` as a real column rather than
-- reaching its tenant through a parent FK. A policy that joined to the parent
-- would be a policy that can be defeated by a parent row a subquery cannot see,
-- and it would cost a join on every read of every bill run.

ALTER TABLE discounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE discounts FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS discounts_tenant_isolation ON discounts;
CREATE POLICY discounts_tenant_isolation ON discounts
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE discount_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE discount_versions FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS discount_versions_tenant_isolation ON discount_versions;
CREATE POLICY discount_versions_tenant_isolation ON discount_versions
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE plan_discount_rules ENABLE ROW LEVEL SECURITY;
ALTER TABLE plan_discount_rules FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS plan_discount_rules_tenant_isolation ON plan_discount_rules;
CREATE POLICY plan_discount_rules_tenant_isolation ON plan_discount_rules
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE discount_enrolments ENABLE ROW LEVEL SECURITY;
ALTER TABLE discount_enrolments FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS discount_enrolments_tenant_isolation ON discount_enrolments;
CREATE POLICY discount_enrolments_tenant_isolation ON discount_enrolments
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE discount_enrolment_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE discount_enrolment_documents FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS discount_enrolment_documents_tenant_isolation ON discount_enrolment_documents;
CREATE POLICY discount_enrolment_documents_tenant_isolation ON discount_enrolment_documents
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE discount_grants ENABLE ROW LEVEL SECURITY;
ALTER TABLE discount_grants FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS discount_grants_tenant_isolation ON discount_grants;
CREATE POLICY discount_grants_tenant_isolation ON discount_grants
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
