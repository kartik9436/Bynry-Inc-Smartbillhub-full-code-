-- rls_metering_cr029_routes.sql — RLS for the THREE new CR-029 tenant tables. HUMAN-OWNED
-- CR-029 RC-W1 T4 (B17 §6) — D10's service set, D11's per-premises walk order
-- and D1's first-class read windows.
--
-- The B2 §3 policy template, applied verbatim, exactly as
-- `rls_metering_cr006_route_meter_exclusions.sql` applies it one CR earlier.
-- A new tenant table with no policy is a G5 isolation failure and a release
-- blocker (NFR-10, zero tolerance), so this ships in the SAME migration as the
-- CreateModel and never in a follow-up.
--
-- What each disclosure would actually be, because "add the policy" is easier to
-- remember when the leak is concrete:
--
--   route_services         which utilities another operator reads together —
--                          their crew structure, service by service.
--   route_premises_orders  the WALKING ORDER of another utility's route, which
--                          is a list of addresses in the sequence a lone reader
--                          visits them at a predictable time of day.
--   read_windows           another utility's operational performance: how many
--                          meters a crew collected, how many were skipped, and
--                          which windows closed Incomplete.
--
-- A cross-tenant WRITE is worse than a read in all three: a row inserted into
-- another tenant's route_premises_orders re-orders a crew sheet, and a
-- read_windows row closed against their route falsifies a history their audit
-- reads back.

ALTER TABLE route_services ENABLE ROW LEVEL SECURITY;
ALTER TABLE route_services FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS route_services_tenant_isolation ON route_services;
CREATE POLICY route_services_tenant_isolation ON route_services
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE route_premises_orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE route_premises_orders FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS route_premises_orders_tenant_isolation ON route_premises_orders;
CREATE POLICY route_premises_orders_tenant_isolation ON route_premises_orders
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE read_windows ENABLE ROW LEVEL SECURITY;
ALTER TABLE read_windows FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS read_windows_tenant_isolation ON read_windows;
CREATE POLICY read_windows_tenant_isolation ON read_windows
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
