-- rls_cr039_c12_premises_owners.sql — RLS policies for the two tables CR-039
-- wave C task 12 adds: `premises_owner_categories` (tenancy-hosted vocabulary)
-- and `premises_owners` (metering-owned party records).
--
-- HUMAN-OWNED (CLAUDE.md hard rule 1 🔒). HUMAN-REVIEW-PENDING — AI-authored
-- 2026-08-27 under the PO ruling of 2026-08-09 (*"AI will do it; we will review
-- it later as human"*), implementing the SIGNED B2 §3 template VERBATIM. A row
-- IS APPENDED in 12-governance/09-human-review-ledger.md. Applied by
-- apps/tenancy/migrations/0022_* and apps/metering/migrations/0040_*
-- (Postgres only — PostgresOnlySQL skips honestly on sqlite).
--
-- Template (B2 §3, deny-by-default), with DEF-639's cast repair: `NULLIF(…,'')`
-- makes an unset GUC NULL rather than an empty string, `NULL = tenant_id` is
-- NULL, and a policy evaluating to NULL admits NOTHING — an identical
-- guarantee to the literal cast that can no longer raise inside `migrate`.
--
-- ⚠ WHY BOTH TABLES ARE TENANT-SCOPED AND NEITHER IS PLATFORM DATA. The
-- distinguishing test this repo already uses is ownership of the CONTENT
-- (rls_tenancy_cr004_reference_lists.sql): `services` and `subscription_plans`
-- are RLS-exempt because they are platform vocabulary identical for every
-- tenant. Neither of these is that.
--   * `premises_owner_categories` carries a tenant_id, is seeded per tenant and
--     is editable by that tenant's System Admin through /lookups (BR-TEN-036,
--     BR-TEN-150 clause 4). The moment a tenant can add a row, the table holds
--     that tenant's own vocabulary.
--   * `premises_owners` is the stronger case of the two and is worth naming
--     individually: it holds NAMED PARTIES with email addresses and phone
--     numbers, and three of the five occupancy states make one of them the
--     party who PAYS. A cross-tenant read discloses one utility's landlords to
--     another; a cross-tenant WRITE would change who gets billed. It is the
--     same class of table as `contacts`, not the same class as `services`.
--
-- ⚠ THIS FILE IS APPLIED BY TWO MIGRATIONS IN TWO APPS, EACH TAKING ITS OWN
-- HALF, and the halves are separated below so neither runs before its table
-- exists. `tests/test_tenant_isolation.py` walks every tenant-scoped table
-- rather than a hand-kept list, so a table that reached the schema without a
-- policy fails there and not here.

-- ── tenancy 0022 applies THIS half ──────────────────────────────────────────
ALTER TABLE premises_owner_categories ENABLE ROW LEVEL SECURITY;
ALTER TABLE premises_owner_categories FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS premises_owner_categories_tenant_isolation ON premises_owner_categories;
CREATE POLICY premises_owner_categories_tenant_isolation ON premises_owner_categories
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
