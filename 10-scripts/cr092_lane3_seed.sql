-- ── Trace ──────────────────────────────────────────────
-- Change:  CR-092-BRC01 step 2 · wave C lane 3 — SERVER-SIDE PAGING INSIDE AN
--          ASSET (AST-B-24) and the three still-unpaged registry reads.
-- Defects: DEF-MET-4995 (the three in-asset lists answer the whole history) ·
--          DEF-MET-4962 remainder (/assets/stock, /assets/lifecycle,
--          /assets/geo take no page parameter)
-- Rules:   NFR-3 (universal server pagination) · NFR-5 (no hard caps)
-- Pairs with: 06-backend/tests/test_cr092_asset_paging.py
-- PO:      2026-09-12, verbatim — *"Okay - you can do actual figures"*: a lane
--          may SEED the data a finding needs, and must say what it seeded.
-- ───────────────────────────────────────────────────────
--
-- WHY THIS EXISTS: PAGING IS MEANINGLESS ON A LIST OF THREE.
--
-- Counted 2026-09-12 with `app.tenant_id` set on each tenant (RLS `FORCE` is
-- on, so an unscoped count returns 0 and reads as an empty database — it is
-- not):
--
--     tenant       assets  reads  assignments  maintenance  largest history
--     brazosbend       14     24           11            0   1 assignment
--     oak-ridge        74    202           67            2  13 reads
--     pine-hill       135    518          127            0  26 reads
--
-- **The largest list inside any asset on any tenant is 26 rows**, and the page
-- size floor is 50 (`core/pagination.PAGE_SIZES`, PO ruling 2026-08-09). So
-- page 1 IS the whole list on every asset anybody has ever opened, and a
-- missing pager has no visible symptom anywhere. That is exactly why
-- `DEF-MET-4995` survived three weeks: the fixture cannot show the defect.
--
-- WHAT THIS ADDS — 240 rows, all new, on ONE asset of ONE tenant
-- (pine-hill water meter **M-88402**, `01a08efc-3417-7420-b4d2-e197f2621b57`):
--
--   · 120 `meter_reads`      — days 5, 10, 15, 20, 25 of the 24 months from
--                              2024-09 to 2026-08. Added to the 26 the product
--                              already wrote, the Reads tab folds to **146
--                              rows**, which is page 1 (50) · page 2 (50) ·
--                              page 3 (46) — three pages, so "page 2 differs
--                              from page 1" is a claim with teeth.
--   ·  60 `asset_assignments` — CLOSED historical seats (`to_date` always set;
--                              `uq_asset_assignments_current` permits exactly
--                              one open row per asset and the product's own
--                              open row is left alone).
--   ·  60 `asset_maintenance` — one costed repair in every fifth row, the rest
--                              uncosted inspections and tests, so
--                              `lifetime_cost` stays a real sum and never
--                              becomes a fabricated $0.00.
--
-- ⚠ **NOTHING EXISTING IS EDITED OR DELETED.** Every statement is an INSERT
-- and each copies its unchanged columns from a row the product itself wrote,
-- so no shape here is one the product could not have produced. Re-running is
-- safe: every insert is guarded by `WHERE NOT EXISTS` on the same key the
-- database already enforces.
--
-- ⚠ **THE REGISTRY'S THREE COMPOSITE READS ARE DELIBERATELY NOT SEEDED.**
-- `/assets/geo` already answers 123 markers on pine-hill, which crosses two
-- page boundaries as it stands. `/assets/stock` groups by asset TYPE (4 rows)
-- and `/assets/lifecycle`'s certifications list is cadenced assets only (2
-- rows); making either cross a boundary means either inventing ~50 asset types
-- or EDITING the cadence columns of ~50 existing assets, and an edit is the one
-- thing this file will not do. Both are proved past the boundary in
-- `06-backend/tests/test_cr092_asset_paging.py`, where the population is the
-- lane's own to build — which is the durable proof anyway.
--
-- USAGE — the ids are pine-hill's on this demo database; re-derive rather than
-- trusting them after a re-seed:
--     SELECT id FROM tenants WHERE subdomain = 'pine-hill';
--     SELECT id FROM assets WHERE asset_no = 'M-88402';
--
--     PGPASSWORD=smartbillhub psql -h 127.0.0.1 -U smartbillhub \
--       -d smartbillhub -v ON_ERROR_STOP=1 -f 10-scripts/cr092_lane3_seed.sql
-- ─────────────────────────────────────────────────────────────────────────────

\set ON_ERROR_STOP on

BEGIN;

-- RLS `FORCE` is on: nothing below sees a row without this (hard rule 1).
SET LOCAL app.tenant_id = '01a08ef6-2b3e-79a8-aceb-3d209789105b';

-- ── 1 · 120 reads on M-88402 ────────────────────────────────────────────────
-- Every column but id/read_at/period/values/created_at is copied from the
-- meter's own newest read, so the rule_outcomes blob, the source, the unit and
-- the account are the product's, not this file's.
INSERT INTO meter_reads (
    id, tenant_id, asset_id, account_id, read_at, channel,
    period_start, period_end, prior_value, current_value, multiplier,
    consumption, unit, source, source_detail, status, lifecycle,
    days_since_prior, rule_outcomes, import_batch_id, imported_by,
    demand_reset_noted, created_at, updated_at, is_sample, read_method
)
SELECT
    gen_random_uuid(),
    src.tenant_id,
    src.asset_id,
    src.account_id,
    (make_date(2024, 9, 1) + (m || ' months')::interval + ((d - 1) || ' days')::interval)
        AT TIME ZONE 'UTC',
    'total',
    (make_date(2024, 9, 1) + (m || ' months')::interval + ((d - 1) || ' days')::interval)::date - 30,
    (make_date(2024, 9, 1) + (m || ' months')::interval + ((d - 1) || ' days')::interval)::date,
    NULL, NULL, src.multiplier,
    -- A plausible, varying quantity with its explicit unit (hard rule 3).
    (3200 + ((m * 5 + d) % 37) * 45)::numeric(18,6),
    src.unit, src.source, src.source_detail, src.status, src.lifecycle,
    30, src.rule_outcomes, src.import_batch_id, src.imported_by,
    false, now(), now(), true, src.read_method
FROM (
    SELECT * FROM meter_reads
    WHERE asset_id = '01a08efc-3417-7420-b4d2-e197f2621b57'
      AND superseded_by_id IS NULL
    ORDER BY read_at DESC LIMIT 1
) AS src
CROSS JOIN generate_series(0, 23) AS m
CROSS JOIN (VALUES (5), (10), (15), (20), (25)) AS days(d)
WHERE NOT EXISTS (
    SELECT 1 FROM meter_reads x
    WHERE x.asset_id = src.asset_id
      AND x.channel = 'total'
      AND x.superseded_by_id IS NULL
      AND x.read_at = (make_date(2024, 9, 1) + (m || ' months')::interval
                       + ((days.d - 1) || ' days')::interval) AT TIME ZONE 'UTC'
);

-- ── 2 · 60 closed assignment seats ──────────────────────────────────────────
-- `to_date` is ALWAYS set: the partial unique index permits one open seat per
-- asset and the product already holds it. Each seat is 30 days, walking
-- backwards from 2021-03-04, the from_date of the open row.
INSERT INTO asset_assignments (
    id, tenant_id, asset_id, unit_id, from_date, to_date,
    actor_user_id, final_read_id, created_at, updated_at, is_sample
)
SELECT
    gen_random_uuid(),
    src.tenant_id, src.asset_id, src.unit_id,
    src.from_date - ((n + 1) * 30),
    src.from_date - (n * 30) - 1,
    src.actor_user_id, NULL, now(), now(), true
FROM (
    SELECT * FROM asset_assignments
    WHERE asset_id = '01a08efc-3417-7420-b4d2-e197f2621b57'
      AND to_date IS NULL
    LIMIT 1
) AS src
CROSS JOIN generate_series(1, 60) AS n
WHERE NOT EXISTS (
    SELECT 1 FROM asset_assignments x
    WHERE x.asset_id = src.asset_id
      AND x.from_date = src.from_date - ((n + 1) * 30)
);

-- ── 3 · 60 maintenance entries ──────────────────────────────────────────────
-- BR-AST-018 append-only. One in five carries a cost, so `lifetime_cost`
-- remains a genuine sum over SOME rows rather than over all or none — the
-- distinction the selector's own docstring turns on.
INSERT INTO asset_maintenance (
    id, tenant_id, asset_id, kind, date, detail,
    resulting_status_id, tech_user_id, closed_at, cost, created_at
)
SELECT
    gen_random_uuid(),
    '01a08ef6-2b3e-79a8-aceb-3d209789105b',
    '01a08efc-3417-7420-b4d2-e197f2621b57',
    (ARRAY['repair', 'inspection', 'test'])[1 + (n % 3)],
    date '2026-08-20' - (n * 11),
    'Seeded history row ' || n || ' — CR-092 lane 3, so a page boundary exists.',
    (SELECT id FROM asset_lifecycle_stages WHERE code = 'active' LIMIT 1),
    (SELECT id FROM users WHERE email = 'sam.reyes@sample.test' LIMIT 1),
    (date '2026-08-20' - (n * 11))::timestamptz,
    CASE WHEN n % 5 = 0 THEN (85 + (n % 7) * 30)::numeric(18,4) ELSE NULL END,
    now()
FROM generate_series(1, 60) AS n
WHERE NOT EXISTS (
    SELECT 1 FROM asset_maintenance x
    WHERE x.asset_id = '01a08efc-3417-7420-b4d2-e197f2621b57'
      AND x.detail LIKE 'Seeded history row %CR-092 lane 3%'
      AND x.date = date '2026-08-20' - (n * 11)
);

-- ── What landed, printed rather than assumed ────────────────────────────────
SELECT 'reads on M-88402'       AS list, count(*) AS rows FROM meter_reads
    WHERE asset_id = '01a08efc-3417-7420-b4d2-e197f2621b57' AND superseded_by_id IS NULL
UNION ALL
SELECT 'distinct read dates', count(DISTINCT read_at) FROM meter_reads
    WHERE asset_id = '01a08efc-3417-7420-b4d2-e197f2621b57' AND superseded_by_id IS NULL
UNION ALL
SELECT 'assignment seats', count(*) FROM asset_assignments
    WHERE asset_id = '01a08efc-3417-7420-b4d2-e197f2621b57'
UNION ALL
SELECT 'maintenance entries', count(*) FROM asset_maintenance
    WHERE asset_id = '01a08efc-3417-7420-b4d2-e197f2621b57';

COMMIT;
