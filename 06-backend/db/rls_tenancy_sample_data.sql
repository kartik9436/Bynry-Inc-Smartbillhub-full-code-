-- rls_tenancy_sample_data.sql — RLS policy for `sample_data_runs`
-- (US-TEN-019 §5). HUMAN-OWNED (CLAUDE.md rule 1 🔒). HUMAN-REVIEW-PENDING —
-- AI-authored 2026-08-15 under PO ruling 2026-08-09, implementing the SIGNED
-- B2 §3 template VERBATIM; row in 12-governance/09-human-review-ledger.md;
-- applied by apps/tenancy/migrations/0009_sample_data_runs.py (Postgres only).
--
-- Template (B2 §3, deny-by-default: with app.tenant_id unset, the ::uuid cast
-- of '' fails and NO row is visible):
--   ALTER TABLE <t> ENABLE ROW LEVEL SECURITY;
--   ALTER TABLE <t> FORCE ROW LEVEL SECURITY;
--   CREATE POLICY <t>_tenant_isolation ON <t> USING/WITH CHECK tenant_id = app.tenant_id
--
-- WHY A RUN LEDGER NEEDS ISOLATION AT ALL, stated because it reads like
-- telemetry. Two reasons, and the second is the one that would bite:
--
--   1. It is tenant CONTENT. The row says what this utility's tenant holds and
--      what it does not — "customers: skipped, seam not wired" is a statement
--      about their data, rendered on their own S62 checklist (BR-TEN-060).
--
--   2. US-TEN-019's removal path (BR-TEN-061/066) deletes rows on a predicate —
--      `is_sample = true` — and NOTHING ELSE. A predicate-driven DELETE is the
--      shape where a missing policy stops being a disclosure and becomes data
--      loss in another tenant's account. The delete itself lives in the owning
--      modules, but the run record is what an operator reads before pressing
--      the button and what the confirmation counts against, so it is scoped on
--      the same terms as everything it describes. TC-11's probe — "removal
--      under `app.tenant_id` = pecangrove can never select another tenant's
--      rows" — starts here.
--
-- FORCE, not merely ENABLE, for the reason B2 §3 gives everywhere: the
-- application's own DB role owns these tables, and without FORCE the owner is
-- exempt from its own policy — the isolation would be decorative.

ALTER TABLE sample_data_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE sample_data_runs FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS sample_data_runs_tenant_isolation ON sample_data_runs;
CREATE POLICY sample_data_runs_tenant_isolation ON sample_data_runs
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
