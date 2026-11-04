-- rls_rating_cr013_p1.sql — RLS for the two tables CR-013 P1 adds.
-- HUMAN-OWNED (CLAUDE.md rule 1 🔒). HUMAN-REVIEW-PENDING — AI-authored
-- 2026-08-20 under the PO ruling of 2026-08-09, applying the SIGNED B2 §3
-- template VERBATIM, identically to db/rls_rating_w1.sql. Row in
-- 12-governance/09-human-review-ledger.md; applied by
-- apps/rating/migrations/0011_cr013_p1_rls.py (Postgres only).
--
-- Written IN THE SAME COMMIT as the tables, not after. rls_rating_w1.sql exists
-- because a schema lane once documented its policies and ended before writing
-- them, and every table it named shipped unprotected. Hard rule 1 admits no gap
-- and a new tenant table without a policy is that gap, so these are here.
--
-- Template (B2 §3, deny-by-default: with app.tenant_id unset the ::uuid cast of
-- '' fails and NO row is visible):
--   ALTER TABLE <t> ENABLE ROW LEVEL SECURITY;
--   ALTER TABLE <t> FORCE ROW LEVEL SECURITY;
--   CREATE POLICY <t>_tenant_isolation ON <t> USING/WITH CHECK tenant_id = app.tenant_id

ALTER TABLE charge_code_amounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE charge_code_amounts FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS charge_code_amounts_tenant_isolation ON charge_code_amounts;
CREATE POLICY charge_code_amounts_tenant_isolation ON charge_code_amounts
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE rate_size_rows ENABLE ROW LEVEL SECURITY;
ALTER TABLE rate_size_rows FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS rate_size_rows_tenant_isolation ON rate_size_rows;
CREATE POLICY rate_size_rows_tenant_isolation ON rate_size_rows
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
