-- rls_tenancy_w0.sql — RLS policies for the W0 tenancy-hosted tables. HUMAN-OWNED
-- (CLAUDE.md rule 1 🔒). HUMAN-REVIEW-PENDING — AI-authored 2026-08-09 under PO
-- ruling 2026-08-09, implementing the SIGNED B2 §3 template VERBATIM per table;
-- row in 12-governance/09-human-review-ledger.md; applied by
-- apps/tenancy/migrations/0003_rls_w0_policies.py (Postgres only).
--
-- Template (B2 §3, repeated per tenant-scoped table — deny-by-default: with
-- app.tenant_id unset, the ::uuid cast of '' fails and NO row is visible):
--   ALTER TABLE <t> ENABLE ROW LEVEL SECURITY;
--   ALTER TABLE <t> FORCE ROW LEVEL SECURITY;
--   CREATE POLICY <t>_tenant_isolation ON <t> USING/WITH CHECK tenant_id = app.tenant_id
--
-- RLS-exempt here (platform tables per B2 §3): tenants (membership-filtered at
-- the app layer) · subscription_plans · services.

ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE subscriptions FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS subscriptions_tenant_isolation ON subscriptions;
CREATE POLICY subscriptions_tenant_isolation ON subscriptions
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE tenant_services ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenant_services FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_services_tenant_isolation ON tenant_services;
CREATE POLICY tenant_services_tenant_isolation ON tenant_services
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE tenant_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenant_settings FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_settings_tenant_isolation ON tenant_settings;
CREATE POLICY tenant_settings_tenant_isolation ON tenant_settings
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE uoms ENABLE ROW LEVEL SECURITY;
ALTER TABLE uoms FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS uoms_tenant_isolation ON uoms;
CREATE POLICY uoms_tenant_isolation ON uoms
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE reference_seed_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE reference_seed_runs FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS reference_seed_runs_tenant_isolation ON reference_seed_runs;
CREATE POLICY reference_seed_runs_tenant_isolation ON reference_seed_runs
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE number_series ENABLE ROW LEVEL SECURITY;
ALTER TABLE number_series FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS number_series_tenant_isolation ON number_series;
CREATE POLICY number_series_tenant_isolation ON number_series
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE holiday_calendars ENABLE ROW LEVEL SECURITY;
ALTER TABLE holiday_calendars FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS holiday_calendars_tenant_isolation ON holiday_calendars;
CREATE POLICY holiday_calendars_tenant_isolation ON holiday_calendars
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE user_preferences ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_preferences FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS user_preferences_tenant_isolation ON user_preferences;
CREATE POLICY user_preferences_tenant_isolation ON user_preferences
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE jobs FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS jobs_tenant_isolation ON jobs;
CREATE POLICY jobs_tenant_isolation ON jobs
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE bell_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE bell_events FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS bell_events_tenant_isolation ON bell_events;
CREATE POLICY bell_events_tenant_isolation ON bell_events
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
