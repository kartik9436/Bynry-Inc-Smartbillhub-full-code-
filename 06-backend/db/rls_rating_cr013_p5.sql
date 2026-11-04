-- rls_rating_cr013_p5.sql — RLS for `plan_versions`, the ONE table CR-013
-- part 5 adds (BR-RAT-111, the plan's filing record).
--
-- HUMAN-OWNED (CLAUDE.md rule 1 🔒). HUMAN-REVIEW-PENDING — AI-authored
-- 2026-08-21 under the PO ruling of 2026-08-09, applying the SIGNED B2 §3
-- template VERBATIM, identically to db/rls_rating_cr013_p1.sql. Row in
-- 12-governance/09-human-review-ledger.md; applied by
-- apps/rating/migrations/0021_cr013_p5_rls.py (Postgres only).
--
-- ⚠ WRITTEN IN THE SAME COMMIT AS THE TABLE, not after. rls_rating_w1.sql
-- exists because a schema lane once documented its policies in the models and
-- ended before authoring them, and every table it named shipped with no
-- isolation at all. Hard rule 1 admits no gap, and a new tenant table without a
-- policy IS that gap.
--
-- ⚠ AND THIS TABLE IS THE ONE WHERE A LEAK WOULD BE WORST. `plan_versions.snapshot`
-- holds the WHOLE of a plan — every base charge, every bound schedule, every
-- charge rule and tax rule, for every version — so one unscoped read is a
-- competitor's complete price book rather than one row of one column.
--
-- Template (B2 §3, deny-by-default: with app.tenant_id unset the ::uuid cast of
-- '' fails and NO row is visible):
--   ALTER TABLE <t> ENABLE ROW LEVEL SECURITY;
--   ALTER TABLE <t> FORCE ROW LEVEL SECURITY;
--   CREATE POLICY <t>_tenant_isolation ON <t> USING/WITH CHECK tenant_id = app.tenant_id

ALTER TABLE plan_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE plan_versions FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS plan_versions_tenant_isolation ON plan_versions;
CREATE POLICY plan_versions_tenant_isolation ON plan_versions
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
