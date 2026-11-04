-- rls_tenancy_cr004_reference_lists.sql — RLS policies for the six reference
-- tables CR-004 adds. HUMAN-OWNED (CLAUDE.md rule 1 🔒). HUMAN-REVIEW-PENDING —
-- AI-authored 2026-08-16 under PO ruling 2026-08-09 ("AI will do it; we will
-- review it later as human"), implementing the SIGNED B2 §3 template VERBATIM;
-- row in 12-governance/09-human-review-ledger.md; applied by
-- apps/tenancy/migrations/0010_* (Postgres only).
--
-- Template (B2 §3, deny-by-default: with app.tenant_id unset, the ::uuid cast
-- of '' fails and NO row is visible):
--   ALTER TABLE <t> ENABLE ROW LEVEL SECURITY;
--   ALTER TABLE <t> FORCE ROW LEVEL SECURITY;
--   CREATE POLICY <t>_tenant_isolation ON <t> USING/WITH CHECK tenant_id = app.tenant_id
--
-- WHY ALL SIX, INCLUDING THE ONES THAT LOOK LIKE PLATFORM CATALOGS. Two
-- neighbouring tables — `services` and `subscription_plans` — ARE RLS-exempt,
-- because they are platform vocabulary identical for every tenant. None of
-- these six is that, and the distinguishing test is ownership of the CONTENT:
-- every one of them carries a `tenant_id`, is seeded per tenant, and is
-- editable by that tenant's System Admin through /lookups (BR-TEN-036 —
-- platform-seeded defaults, tenant may EXTEND and rename). The moment a tenant
-- can add a row, the table holds that tenant's own vocabulary, and one
-- utility's district names, meter fleet or crew certifications are not another
-- utility's business.
--
-- `occupancy_statuses` is the one worth naming individually. Its values are
-- BILLING BEHAVIOUR, not description — occupied tenant-billed, occupied
-- owner-billed, landlord-billed, vacant base-charges-only, vacant no-billing.
-- A cross-tenant read there discloses how a competitor bills; a cross-tenant
-- WRITE would change who gets charged. It is the same class of table as
-- `charge_codes`, not the same class as `services`.
--
-- Applied as one file because these six land in one migration: B2 §7 wants RLS
-- immediately after each table, one boring pattern repeated (LAW 0), and six
-- copies of four lines in six files would be six chances to omit one. The
-- isolation sweep in tests/test_tenant_isolation.py is what proves none was
-- omitted — it walks every tenant-scoped table rather than a hand-kept list,
-- so a seventh table added later without a policy fails there.

ALTER TABLE areas ENABLE ROW LEVEL SECURITY;
ALTER TABLE areas FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS areas_tenant_isolation ON areas;
CREATE POLICY areas_tenant_isolation ON areas
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE meter_size_classes ENABLE ROW LEVEL SECURITY;
ALTER TABLE meter_size_classes FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS meter_size_classes_tenant_isolation ON meter_size_classes;
CREATE POLICY meter_size_classes_tenant_isolation ON meter_size_classes
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE occupancy_statuses ENABLE ROW LEVEL SECURITY;
ALTER TABLE occupancy_statuses FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS occupancy_statuses_tenant_isolation ON occupancy_statuses;
CREATE POLICY occupancy_statuses_tenant_isolation ON occupancy_statuses
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE device_types ENABLE ROW LEVEL SECURITY;
ALTER TABLE device_types FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS device_types_tenant_isolation ON device_types;
CREATE POLICY device_types_tenant_isolation ON device_types
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE certification_types ENABLE ROW LEVEL SECURITY;
ALTER TABLE certification_types FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS certification_types_tenant_isolation ON certification_types;
CREATE POLICY certification_types_tenant_isolation ON certification_types
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE import_mappings ENABLE ROW LEVEL SECURITY;
ALTER TABLE import_mappings FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS import_mappings_tenant_isolation ON import_mappings;
CREATE POLICY import_mappings_tenant_isolation ON import_mappings
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
