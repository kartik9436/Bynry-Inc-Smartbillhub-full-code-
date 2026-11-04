-- rls_metering_cr006_route_meter_exclusions.sql — RLS for the ONE new CR-006 tenant table. HUMAN-OWNED
-- CR-006 (BR-MET-075) — RLS for the ONE new tenant table this CR adds.
--
-- The B2 §3 policy template, applied verbatim, exactly as
-- `rls_metering_w1.sql` applies it to `route_memberships` two tables above.
-- A new tenant table with no policy is a G5 isolation failure and a release
-- blocker (NFR-10, zero tolerance), so this ships in the same migration as
-- the CreateModel and not in a follow-up.
--
-- `route_meter_exclusions` holds (tenant, route, asset). A cross-tenant read
-- would disclose which meters another utility deliberately does not read —
-- an operational detail — and a cross-tenant write would silently drop a
-- meter off a competitor's crew sheet.

ALTER TABLE route_meter_exclusions ENABLE ROW LEVEL SECURITY;
ALTER TABLE route_meter_exclusions FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS route_meter_exclusions_tenant_isolation ON route_meter_exclusions;
CREATE POLICY route_meter_exclusions_tenant_isolation ON route_meter_exclusions
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
