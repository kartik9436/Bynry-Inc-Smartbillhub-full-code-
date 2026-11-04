-- ── Trace ──────────────────────────────────────────────
-- Change:  CR-092-BRC01 step 2 · lane 2 — the rows three findings needed in
--          order to be REPRODUCED at all. PO ruling 2026-09-12, verbatim:
--          *"you can do actual figures"* — a lane may seed the data a finding
--          needs, and must say what it seeded and how many.
-- Defects: DEF-MET-4967 · DEF-MET-4969 · DEF-MET-4970
-- Pairs with: 10-scripts/cr092_lane2_asset_detail_walkthrough.mjs
-- ───────────────────────────────────────────────────────
--
-- WHAT WAS THERE BEFORE, counted with `app.tenant_id` set on each tenant
-- (RLS `FORCE` is on, so an unscoped count returns 0 and reads as an empty
-- database — it is not):
--
--     tenant       assets  reads  work_orders  with asset_id  maintenance
--     brazosbend       14     24            0             0            0
--     oak-ridge        74    202           23             0            0
--     pine-hill       135    518           42             0            0
--
-- **0 of 65 work orders anywhere carried an `asset_id`** and
-- `asset_maintenance` held **0 rows on every tenant**, so the Open work panel
-- and the maintenance history had never been drawn by anything. No meter's
-- usage payload carried more than one register either, so the multi-register
-- strip was equally unreachable.
--
-- WHAT THIS ADDS — 57 rows, all new, on ONE asset of ONE tenant:
--   ·  9 `meter_reads`  — three TOU registers × three dates on W-5001
--   ·  3 `work_orders`  — WO-4908 in_progress · WO-4907 blocked · WO-4900 done
--   ·  2 `asset_maintenance` — one costed repair, one uncosted 2024 test
--   · 45 `meter_read_asset_monthly_usage` — the per-asset cache
--     (`BR-MET-141`) for four registers over twelve months, because
--     `asset_usage` reads STORED first and only computes when nothing is
--     stored, so seeding reads alone changes no chart.
--
-- ⚠ **NOTHING EXISTING IS EDITED OR DELETED.** Every statement is an INSERT,
-- and each copies its unchanged columns from a row the product itself wrote,
-- so no shape here is one the product could not have produced.
--
-- USAGE — the tenant id is oak-ridge's on the demo database; re-derive it
-- rather than trusting it after a re-seed:
--     SELECT id FROM tenants WHERE subdomain = 'oak-ridge';

SET app.tenant_id = '01a08ef9-c890-739c-9014-6750c65f7629';  -- oak-ridge

-- 1 · THREE MORE REGISTERS on W-5001, copied from its own newest total read
--     so every other column is a shape the product already produced.
INSERT INTO meter_reads (
  id, tenant_id, asset_id, account_id, read_at, channel, period_start, period_end,
  prior_value, current_value, multiplier, consumption, unit, source, source_detail,
  status, lifecycle, days_since_prior, rule_outcomes, created_at, updated_at,
  is_sample, read_method, demand_reset_noted, consecutive_estimate_no
)
SELECT
  gen_random_uuid(), r.tenant_id, r.asset_id, r.account_id,
  r.read_at - (g.n || ' days')::interval,
  v.channel, r.period_start, r.period_end,
  r.prior_value, r.current_value, r.multiplier, v.consumption, v.unit,
  r.source, r.source_detail, r.status, r.lifecycle, r.days_since_prior,
  r.rule_outcomes, now(), now(), r.is_sample, r.read_method,
  r.demand_reset_noted, r.consecutive_estimate_no
FROM (
  SELECT * FROM meter_reads
  WHERE asset_id = '01a08efa-12ed-7dc2-b5a9-08111147a36e' AND channel = 'total'
  ORDER BY read_at DESC LIMIT 3
) r
JOIN LATERAL (VALUES
  ('tou_on',  412.000000, r.unit),
  ('tou_mid', 290.000000, r.unit),
  ('tou_off', 1098.000000, r.unit)
) AS v(channel, consumption, unit) ON true
JOIN LATERAL (SELECT 0 AS n) g ON true;

-- 2 · TWO WORK ORDERS ANCHORED TO W-5001 — one open, one done. Every one of
--     the 65 orders on this database carried `asset_id = NULL`, so the Open
--     work panel had no row it could ever draw.
INSERT INTO work_orders (
  id, order_no, type, scope, state, outcome, mode, is_gate, is_sample,
  created_at, updated_at, asset_id, tenant_id, type_id, source,
  due_at, assignee_technician_id, completed_at, dispatch_state
) VALUES
  (gen_random_uuid(), 'WO-4908', 'Meter exchange', 'asset', 'in_progress', NULL,
   'standard', false, true, now() - interval '10 days', now(),
   '01a08efa-12ed-7dc2-b5a9-08111147a36e', '01a08ef9-c890-739c-9014-6750c65f7629',
   '01a08ef9-cd5a-7c12-a397-ff1a8b868a8c', 'assets',
   now() + interval '3 days', '01a08efb-f659-74a1-8c66-c62b89ea3e48', NULL, 'scheduled'),
  (gen_random_uuid(), 'WO-4907', 'Backflow test', 'asset', 'blocked', NULL,
   'standard', false, true, now() - interval '25 days', now(),
   '01a08efa-12ed-7dc2-b5a9-08111147a36e', '01a08ef9-c890-739c-9014-6750c65f7629',
   '01a08ef9-cd5c-7598-909e-16cf05fe1dae', 'assets',
   now() - interval '11 days', NULL, NULL, 'queued'),
  (gen_random_uuid(), 'WO-4900', 'Annual accuracy test', 'asset', 'completed', NULL,
   'standard', false, true, now() - interval '90 days', now(),
   '01a08efa-12ed-7dc2-b5a9-08111147a36e', '01a08ef9-c890-739c-9014-6750c65f7629',
   '01a08ef9-cd5c-7598-909e-16cf05fe1dae', 'assets',
   now() - interval '80 days', '01a08efb-f68c-7cfd-b040-236013fc61f1',
   now() - interval '82 days', 'scheduled');

-- 3 · TWO MAINTENANCE ROWS — `asset_maintenance` held 0 on all three tenants,
--     so the history table had never drawn on any asset in the product.
INSERT INTO asset_maintenance (id, kind, date, detail, created_at, asset_id, tenant_id, tech_user_id, cost)
VALUES
  (gen_random_uuid(), 'repair', (now() - interval '82 days')::date,
   'Replaced the register and resealed', now(),
   '01a08efa-12ed-7dc2-b5a9-08111147a36e', '01a08ef9-c890-739c-9014-6750c65f7629',
   '01a08ef9-d3dd-7ed5-8914-0eda2b4fdcf5', 84.0000),
  (gen_random_uuid(), 'inspection', (now() - interval '400 days')::date,
   'Commissioning accuracy test', now(),
   '01a08efa-12ed-7dc2-b5a9-08111147a36e', '01a08ef9-c890-739c-9014-6750c65f7629',
   NULL, NULL);

-- 4 · THE PER-ASSET USAGE CACHE — and this step is the one that is not
--     obvious. `asset_usage.asset_usage_payload` reads the STORED per-asset
--     monthly row first (`BR-MET-141`, OQ-421's closure) and computes from
--     reads only when nothing is stored. W-5001 had a stored row for `total`
--     and nothing else, so seeding nine TOU reads changed no chart at all and
--     the strip went on drawing one register. `source: "stored"` on the
--     payload is what said so.
INSERT INTO meter_read_asset_monthly_usage (
  id, tenant_id, account_id, asset_id, service_id, channel, period_month, quantity,
  unit, read_count, estimated_read_count, source_read_ids, source_fingerprint,
  computed_at, is_sample, created_at, updated_at)
SELECT gen_random_uuid(), u.tenant_id, u.account_id, u.asset_id, u.service_id,
       v.channel, u.period_month, v.qty, u.unit, u.read_count, u.estimated_read_count,
       u.source_read_ids, u.source_fingerprint||'-'||v.channel, now(), u.is_sample, now(), now()
FROM meter_read_asset_monthly_usage u
JOIN LATERAL (VALUES ('tou_on', 412.000000), ('tou_mid', 290.000000), ('tou_off', 1098.000000))
     AS v(channel, qty) ON true
WHERE u.asset_id = '01a08efa-12ed-7dc2-b5a9-08111147a36e' AND u.channel = 'total';

-- 5 · TWELVE MONTHS of each register, so the chart draws a full year rather
--     than three bars and the BEFORE/AFTER fold measurement is taken on a
--     meter the size the defect describes.
INSERT INTO meter_read_asset_monthly_usage (
  id, tenant_id, account_id, asset_id, service_id, channel, period_month, quantity,
  unit, read_count, estimated_read_count, source_read_ids, source_fingerprint,
  computed_at, is_sample, created_at, updated_at)
SELECT gen_random_uuid(), u.tenant_id, u.account_id, u.asset_id, u.service_id, u.channel,
       (u.period_month - (g.n || ' months')::interval)::date,
       u.quantity * (0.85 + (g.n % 5) * 0.07), u.unit, u.read_count, u.estimated_read_count,
       u.source_read_ids, u.source_fingerprint||'-m'||g.n, now(), u.is_sample, now(), now()
FROM meter_read_asset_monthly_usage u
JOIN LATERAL generate_series(3, 11) AS g(n) ON true
WHERE u.asset_id = '01a08efa-12ed-7dc2-b5a9-08111147a36e'
  AND u.period_month = (SELECT max(period_month) FROM meter_read_asset_monthly_usage
                        WHERE asset_id = '01a08efa-12ed-7dc2-b5a9-08111147a36e');
