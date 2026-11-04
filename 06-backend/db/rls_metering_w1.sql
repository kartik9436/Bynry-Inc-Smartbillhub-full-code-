-- rls_metering_w1.sql — RLS policies for the W1 metering tables. HUMAN-OWNED
-- (CLAUDE.md rule 1 🔒). HUMAN-REVIEW-PENDING — AI-authored 2026-08-09 under the
-- PO ruling of 2026-08-09, implementing the SIGNED B2 §3 template VERBATIM per
-- table; row in 12-governance/09-human-review-ledger.md; applied by
-- apps/metering/migrations/0002_rls_w1_policies.py (Postgres only).
--
-- Authored during the W1 verification pass: the schema lane hit its session limit
-- after documenting these policies in the models but before writing them, leaving
-- every table below unprotected. Hard rule 1 admits no gap, so they are written here.
--
-- Template (B2 §3, repeated per tenant-scoped table — deny-by-default: with
-- app.tenant_id unset, the ::uuid cast of '' fails and NO row is visible):
--   ALTER TABLE <t> ENABLE ROW LEVEL SECURITY;
--   ALTER TABLE <t> FORCE ROW LEVEL SECURITY;
--   CREATE POLICY <t>_tenant_isolation ON <t> USING/WITH CHECK tenant_id = app.tenant_id

ALTER TABLE cycles ENABLE ROW LEVEL SECURITY;
ALTER TABLE cycles FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS cycles_tenant_isolation ON cycles;
CREATE POLICY cycles_tenant_isolation ON cycles
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE premises ENABLE ROW LEVEL SECURITY;
ALTER TABLE premises FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS premises_tenant_isolation ON premises;
CREATE POLICY premises_tenant_isolation ON premises
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE premises_types ENABLE ROW LEVEL SECURITY;
ALTER TABLE premises_types FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS premises_types_tenant_isolation ON premises_types;
CREATE POLICY premises_types_tenant_isolation ON premises_types
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE read_schedules ENABLE ROW LEVEL SECURITY;
ALTER TABLE read_schedules FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS read_schedules_tenant_isolation ON read_schedules;
CREATE POLICY read_schedules_tenant_isolation ON read_schedules
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE route_memberships ENABLE ROW LEVEL SECURITY;
ALTER TABLE route_memberships FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS route_memberships_tenant_isolation ON route_memberships;
CREATE POLICY route_memberships_tenant_isolation ON route_memberships
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE routes ENABLE ROW LEVEL SECURITY;
ALTER TABLE routes FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS routes_tenant_isolation ON routes;
CREATE POLICY routes_tenant_isolation ON routes
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE service_points ENABLE ROW LEVEL SECURITY;
ALTER TABLE service_points FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS service_points_tenant_isolation ON service_points;
CREATE POLICY service_points_tenant_isolation ON service_points
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE units ENABLE ROW LEVEL SECURITY;
ALTER TABLE units FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS units_tenant_isolation ON units;
CREATE POLICY units_tenant_isolation ON units
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

