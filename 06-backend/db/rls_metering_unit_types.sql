-- rls_metering_unit_types.sql — RLS for the ONE new CR-010 metering tenant table. HUMAN-OWNED
-- CR-010 A-section item 4 (BR-MET-084) — unit types become editable rows.
--
-- The B2 §3 policy template, applied verbatim, exactly as
-- `rls_metering_w1.sql` applies it to `premises_types` — the table this one
-- is the sibling of (same card, same laws, same seeded-rows posture).
-- A new tenant table with no policy is a G5 isolation failure and a release
-- blocker (NFR-10, zero tolerance), so this ships in the same migration as
-- the CreateModel and not in a follow-up.
--
-- `unit_types` holds (tenant, code, name): a tenant's own vocabulary for what
-- its units are. Low sensitivity, same zero tolerance — the rule has no
-- "harmless table" clause, and the last table that shipped policy-less was
-- the one nobody thought worth isolating.

ALTER TABLE unit_types ENABLE ROW LEVEL SECURITY;
ALTER TABLE unit_types FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS unit_types_tenant_isolation ON unit_types;
CREATE POLICY unit_types_tenant_isolation ON unit_types
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
