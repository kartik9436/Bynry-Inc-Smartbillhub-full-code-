-- rls_rating_w1.sql — RLS policies for the W1 rating tables. HUMAN-OWNED
-- (CLAUDE.md rule 1 🔒). HUMAN-REVIEW-PENDING — AI-authored 2026-08-09 under the
-- PO ruling of 2026-08-09, implementing the SIGNED B2 §3 template VERBATIM per
-- table; row in 12-governance/09-human-review-ledger.md; applied by
-- apps/rating/migrations/0003_rls_w1_policies.py (Postgres only).
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

ALTER TABLE capacity_rates ENABLE ROW LEVEL SECURITY;
ALTER TABLE capacity_rates FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS capacity_rates_tenant_isolation ON capacity_rates;
CREATE POLICY capacity_rates_tenant_isolation ON capacity_rates
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE charges ENABLE ROW LEVEL SECURITY;
ALTER TABLE charges FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS charges_tenant_isolation ON charges;
CREATE POLICY charges_tenant_isolation ON charges
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE demand_rate_config ENABLE ROW LEVEL SECURITY;
ALTER TABLE demand_rate_config FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS demand_rate_config_tenant_isolation ON demand_rate_config;
CREATE POLICY demand_rate_config_tenant_isolation ON demand_rate_config
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE plan_charge_rules ENABLE ROW LEVEL SECURITY;
ALTER TABLE plan_charge_rules FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS plan_charge_rules_tenant_isolation ON plan_charge_rules;
CREATE POLICY plan_charge_rules_tenant_isolation ON plan_charge_rules
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE plan_deposit_rules ENABLE ROW LEVEL SECURITY;
ALTER TABLE plan_deposit_rules FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS plan_deposit_rules_tenant_isolation ON plan_deposit_rules;
CREATE POLICY plan_deposit_rules_tenant_isolation ON plan_deposit_rules
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE plan_penalty_rules ENABLE ROW LEVEL SECURITY;
ALTER TABLE plan_penalty_rules FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS plan_penalty_rules_tenant_isolation ON plan_penalty_rules;
CREATE POLICY plan_penalty_rules_tenant_isolation ON plan_penalty_rules
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE plan_rate_schedules ENABLE ROW LEVEL SECURITY;
ALTER TABLE plan_rate_schedules FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS plan_rate_schedules_tenant_isolation ON plan_rate_schedules;
CREATE POLICY plan_rate_schedules_tenant_isolation ON plan_rate_schedules
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE plan_services ENABLE ROW LEVEL SECURITY;
ALTER TABLE plan_services FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS plan_services_tenant_isolation ON plan_services;
CREATE POLICY plan_services_tenant_isolation ON plan_services
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE plan_tax_rules ENABLE ROW LEVEL SECURITY;
ALTER TABLE plan_tax_rules FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS plan_tax_rules_tenant_isolation ON plan_tax_rules;
CREATE POLICY plan_tax_rules_tenant_isolation ON plan_tax_rules
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE rate_change_batches ENABLE ROW LEVEL SECURITY;
ALTER TABLE rate_change_batches FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS rate_change_batches_tenant_isolation ON rate_change_batches;
CREATE POLICY rate_change_batches_tenant_isolation ON rate_change_batches
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE rate_change_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE rate_change_log FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS rate_change_log_tenant_isolation ON rate_change_log;
CREATE POLICY rate_change_log_tenant_isolation ON rate_change_log
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE rate_plans ENABLE ROW LEVEL SECURITY;
ALTER TABLE rate_plans FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS rate_plans_tenant_isolation ON rate_plans;
CREATE POLICY rate_plans_tenant_isolation ON rate_plans
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE rate_seasons ENABLE ROW LEVEL SECURITY;
ALTER TABLE rate_seasons FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS rate_seasons_tenant_isolation ON rate_seasons;
CREATE POLICY rate_seasons_tenant_isolation ON rate_seasons
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE rate_tiers ENABLE ROW LEVEL SECURITY;
ALTER TABLE rate_tiers FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS rate_tiers_tenant_isolation ON rate_tiers;
CREATE POLICY rate_tiers_tenant_isolation ON rate_tiers
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE tariff_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE tariff_versions FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tariff_versions_tenant_isolation ON tariff_versions;
CREATE POLICY tariff_versions_tenant_isolation ON tariff_versions
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE tariffs ENABLE ROW LEVEL SECURITY;
ALTER TABLE tariffs FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tariffs_tenant_isolation ON tariffs;
CREATE POLICY tariffs_tenant_isolation ON tariffs
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE tax_jurisdictions ENABLE ROW LEVEL SECURITY;
ALTER TABLE tax_jurisdictions FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tax_jurisdictions_tenant_isolation ON tax_jurisdictions;
CREATE POLICY tax_jurisdictions_tenant_isolation ON tax_jurisdictions
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE taxes ENABLE ROW LEVEL SECURITY;
ALTER TABLE taxes FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS taxes_tenant_isolation ON taxes;
CREATE POLICY taxes_tenant_isolation ON taxes
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE time_of_use_windows ENABLE ROW LEVEL SECURITY;
ALTER TABLE time_of_use_windows FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS time_of_use_windows_tenant_isolation ON time_of_use_windows;
CREATE POLICY time_of_use_windows_tenant_isolation ON time_of_use_windows
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE unit_plan_assignments ENABLE ROW LEVEL SECURITY;
ALTER TABLE unit_plan_assignments FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS unit_plan_assignments_tenant_isolation ON unit_plan_assignments;
CREATE POLICY unit_plan_assignments_tenant_isolation ON unit_plan_assignments
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

