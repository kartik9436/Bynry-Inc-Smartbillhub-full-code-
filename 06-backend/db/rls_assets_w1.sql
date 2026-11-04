-- rls_assets_w1.sql — RLS policies for the W1 assets tables. HUMAN-OWNED
-- (CLAUDE.md rule 1 🔒). HUMAN-REVIEW-PENDING — AI-authored 2026-08-09 under the
-- PO ruling of 2026-08-09, implementing the SIGNED B2 §3 template VERBATIM per
-- table; row in 12-governance/09-human-review-ledger.md; applied by
-- apps/assets/migrations/0002_rls_w1_policies.py (Postgres only).
--
-- Authored during the W1 verification pass: the schema lane hit its session limit
-- after documenting these policies in the models but before writing them, leaving
-- every table below unprotected. Hard rule 1 admits no gap, so they are written here.
--
-- AMENDED 2026-08-09 (BR-AST-043 gap lane): the meter_types + read_methods blocks
-- were appended below the SECTION MARKER near the end of this file. Migration 0002
-- applies only the text ABOVE the marker; migration 0003 applies only the text
-- BELOW it. Two migrations, one policy file — see the marker comment for why.
--
-- Template (B2 §3, repeated per tenant-scoped table — deny-by-default: with
-- app.tenant_id unset, the ::uuid cast of '' fails and NO row is visible):
--   ALTER TABLE <t> ENABLE ROW LEVEL SECURITY;
--   ALTER TABLE <t> FORCE ROW LEVEL SECURITY;
--   CREATE POLICY <t>_tenant_isolation ON <t> USING/WITH CHECK tenant_id = app.tenant_id

ALTER TABLE asset_assignments ENABLE ROW LEVEL SECURITY;
ALTER TABLE asset_assignments FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS asset_assignments_tenant_isolation ON asset_assignments;
CREATE POLICY asset_assignments_tenant_isolation ON asset_assignments
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE asset_import_batches ENABLE ROW LEVEL SECURITY;
ALTER TABLE asset_import_batches FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS asset_import_batches_tenant_isolation ON asset_import_batches;
CREATE POLICY asset_import_batches_tenant_isolation ON asset_import_batches
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE asset_import_rows ENABLE ROW LEVEL SECURITY;
ALTER TABLE asset_import_rows FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS asset_import_rows_tenant_isolation ON asset_import_rows;
CREATE POLICY asset_import_rows_tenant_isolation ON asset_import_rows
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE asset_lifecycle_stages ENABLE ROW LEVEL SECURITY;
ALTER TABLE asset_lifecycle_stages FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS asset_lifecycle_stages_tenant_isolation ON asset_lifecycle_stages;
CREATE POLICY asset_lifecycle_stages_tenant_isolation ON asset_lifecycle_stages
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE asset_maintenance ENABLE ROW LEVEL SECURITY;
ALTER TABLE asset_maintenance FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS asset_maintenance_tenant_isolation ON asset_maintenance;
CREATE POLICY asset_maintenance_tenant_isolation ON asset_maintenance
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE asset_types ENABLE ROW LEVEL SECURITY;
ALTER TABLE asset_types FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS asset_types_tenant_isolation ON asset_types;
CREATE POLICY asset_types_tenant_isolation ON asset_types
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE assets ENABLE ROW LEVEL SECURITY;
ALTER TABLE assets FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS assets_tenant_isolation ON assets;
CREATE POLICY assets_tenant_isolation ON assets
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

-- ─────────────────────────────────────────────────────────────────────────────
-- SECTION MARKER — everything BELOW this line is applied by assets migration
-- 0003_meter_types_and_read_methods, NOT by 0002_rls_w1_policies: these two
-- tables do not exist at 0002's point in history, so 0002 would fail on a fresh
-- database. Both migrations read THIS one file and slice it at the marker, so
-- the policy text still lives in exactly one reviewable place (B2 §3 / 🔒).
-- Do not move, reword, or delete the marker line — both migrations index on it.
-- >>> ASSETS-0003 <<<
--
-- BR-AST-043 (PO 2026-08-09): the two Reference-data catalogs the S8 card grid
-- ratified but no table backed — meter_types (what the meter IS) and
-- read_methods (how the read is COLLECTED). Same B2 §3 template, VERBATIM.

ALTER TABLE meter_types ENABLE ROW LEVEL SECURITY;
ALTER TABLE meter_types FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS meter_types_tenant_isolation ON meter_types;
CREATE POLICY meter_types_tenant_isolation ON meter_types
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE read_methods ENABLE ROW LEVEL SECURITY;
ALTER TABLE read_methods FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS read_methods_tenant_isolation ON read_methods;
CREATE POLICY read_methods_tenant_isolation ON read_methods
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

