-- rls_cr039_c12_premises_owners_metering.sql — the METERING half of CR-039
-- wave C task 12's RLS. See rls_cr039_c12_premises_owners.sql for the full
-- account of why both tables are tenant-scoped; this file exists only because
-- the two tables land in two different apps' migrations and a policy cannot be
-- applied before its table exists.
--
-- HUMAN-OWNED (CLAUDE.md hard rule 1 🔒). HUMAN-REVIEW-PENDING — AI-authored
-- 2026-08-27 under the PO ruling of 2026-08-09. Row APPENDED in
-- 12-governance/09-human-review-ledger.md. Applied by
-- apps/metering/migrations/0040_* (Postgres only).
--
-- ⚠ `premises_owners` HOLDS NAMED PARTIES WITH CONTACT DETAILS, and three of
-- the five seeded occupancy states make one of them the party who PAYS. A
-- cross-tenant read discloses one utility's landlords to another; a
-- cross-tenant write would change who gets billed.

ALTER TABLE premises_owners ENABLE ROW LEVEL SECURITY;
ALTER TABLE premises_owners FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS premises_owners_tenant_isolation ON premises_owners;
CREATE POLICY premises_owners_tenant_isolation ON premises_owners
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
