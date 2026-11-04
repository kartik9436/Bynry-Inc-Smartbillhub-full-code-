# Rate Impact — walk of build 2.569.0 + CR-179-BRC10 (2026-10-12)

Walked on brazosbend at **1440** and **1280** with `10-scripts/cr179_rate_impact_walkthrough.mjs` (`STEP=walk`, then `STEP=history`). Shots are `<width>-NN-*.png`; the result tables as text are `<width>-result.txt`; the history step's checks are `walk-results-history.json`. No product code was changed.

**What was modelled:** services Electric + Water · classes Residential + Municipal · 12 months (Oct 2025 – Sep 2026) · five rows — *Sample — Electric usage* v2026-09-20 at 1φ 100A, 1φ 200A and 3φ 400A ($13.00 base, $0.125/kWh), and *Sample — Residential water (inclining tiers)* 5/8" on the version in force (2026-10-01) **and** on the older 2026-08-01 version ($9.00, $4.50/kgal, minimum $10.00) — then *Change all prices +5%* → Fill → Run.

## Before the walk: two things the environment needed

* **The monthly usage table was nearly empty.** 51 `metering.monthly_usage_refresh` jobs were queued with no worker running (`JOBS_EAGER=false`), so the first run said 46 accounts had *no usage*. They were run once through the product's own job runner (`core.jobs.resume`, what the worker calls); 302 monthly rows now exist for 52 accounts.
* **Export cannot finish on this host.** The CSV is built ("5 row(s)") and then refused: *"DOCUMENT_STORAGE_BUCKET is not set"*. The History row therefore says **Failed**. That is this host's setup, not the report.

## Checks

| Check | Result | Detail |
|---|---|---|
| Card under Billing · Readiness | PASS | READINESS · Rate Impact, next to Bill Run Readiness |
| Card basis line | FAIL | Card says **Period end**; drawing says **Usage months** |
| Report head | FAIL | Head shows **Schedule** + **Edit**; drawing shows **Export** + **Run report**, and the framework table says *Scheduled: not offered*. No subtitle *"Proposed rates against billed revenue."*; shows "2025-10-01 to 2026-09-30 · Event date" |
| Services / classes / 12 months | PASS | Multi-selects and the period dropdown work; services start on *Choose* (drawing shows them filled) |
| Version in a row | FAIL | Not defaulted to the one in force (starts *Choose*); labels are bare ISO dates (`2026-09-20`), drawing reads *v3 · in force*. Order is not by date (water: 2026-10-01 / 2027-03-01 / 2026-08-01) |
| Capacity per row | PASS | Sizes from the version (Electric 1φ 100A … CT; Water 5/8" … 6") |
| Charge code row | FAIL | The Item list is **empty** for Charge code. This tenant's only recurring non-base codes (HYDRANT, PAPER) have no service, and base codes are excluded by design — so on brazosbend a charge code can never be modelled |
| Trash or fire schedule | N/A | Not offered — this tenant has electric and water only |
| "now" figures under the boxes | PASS | now $12.00 / now $8.00; a tiered price shows **now Billed** |
| Change all prices + Fill | PASS | +5%: base $12.00 → **12.60**, $8.00 → **8.40**; price and minimum (no single "now") left as typed |
| Groups expand | PASS | 3 groups, ▸/▾ |
| Capacity column | PASS | — |
| Usage with its unit | PASS, with a flaw | `114500 kWh`, `1165.1 kgal` — **no thousands separator**, and the unit wraps onto a second line |
| Items with their noun | N/A | No counted service on this tenant |
| Group subtotal | **FAIL** | The group's **ACCOUNTS shows money: "$47.00", "$40.00"** |
| Grand total | PASS | Total 47 accounts · now **$35,350.50** · proposed **$29,639.30** · change **−$5,711.20** · **−16.16%** |
| Same schedule, two versions | **FAIL (money)** | The water schedule on v2026-10-01 and on v2026-08-01 are **two groups with the same 40 accounts and the same $7,991.50**, and the grand total counts it **twice** ($35,350.50 = $19,367.50 + $7,991.50 + $7,991.50). Rule 3 says an older version changes only the "now" figures — it should not add a second copy of the revenue |
| Not worked out | PASS | "39 accounts · No capacity on file" (per group counts are summed: 20 per group on the API) |
| Proposed figures used | PASS | One line per row, e.g. "Sample — Electric usage · 2026-09-20 · Electric 1φ 100A (09/20/2026) Base / month $12.00 → $12.60 · Price per unit Billed → $0.125 · Minimum Billed → Billed". The version date is printed twice in two formats |
| Export | PASS (request) / env-blocked (file) | Download CSV icon → 202, toast "Your CSV is being written. Find it on History."; the file fails on storage (above) |
| History shows the export | PASS | Row "Rate Impact · Dana Whitfield · … · Failed · 5" |
| Open in report | PASS | Re-opens the viewer with all five rows, versions, capacities and the +5% figures, and runs |
| B14 rule 31 — result | PASS | No id in the result |
| B14 rule 31 — History | **FAIL** | The History PARAMETERS cell prints the raw `rows` JSON: schedule and version **database ids** (`01a12b2b-d4fc-…`) and size codes (`E-1P-100`, `W-58`) |
| Layout at 1280 | FAIL | Type and Item selects collapse to a bare chevron — no text visible; Version shows "202". At 1440 they are cut to "Rate", "Sample — E", "2026-" |

## Money check by hand — Electric 3φ 400A · Municipal (1 account, AC-2026-00049)

* Usage in the window (monthly table): Aug 1,200 kWh + Sep 1,200 kWh = **2,400 kWh** ✓
* Billed now (issued lines, electric, period ending in the window): BL-2609-000049 $154.50 + BL-2610-000099 $154.50 = **$309.00** ✓
* Proposed: 2 months × ($12.60 + 1,200 × $0.125) = 2 × $162.60 = **$325.20** ✓
* Change $325.20 − $309.00 = **$16.20**, 16.20 / 309.00 = **5.24%** ✓

## Differences from the drawing (05-result.png, 04-inputs.png, 02, 03)

1. Card basis "Period end" vs "Usage months".
2. Head buttons Schedule + Edit vs Export + Run report; Export is an icon above the table, Run report sits in the filter bar.
3. No head subtitle; a date range and "Event date" instead.
4. Services start empty ("Choose") vs pre-filled.
5. Version labels are ISO dates vs "v3 · in force"; no default to the one in force.
6. Effective from shown as 09/20/2026 vs 01-Jan-2026 style (date format follows the tenant).
7. Drawn result is **one card per schedule** with its own NOW / PROPOSED / CHANGE / % header and a subtitle ("Rate schedule · Water · v3, from 01-Jan-2026 · 3 capacities · 1,242 accounts") and its own column header row. Built: one flat table, the schedule as a collapsible group row with "3 rows" and no subtitle.
8. Group row ACCOUNTS printed as money ($47.00).
9. Column "CONSUMER CLASS" vs "CLASS".
10. KPI tiles above the table (NOW / PROPOSED / CHANGE / CHANGE % with "EVENT DATE" captions) — not in the drawing; the drawing has a "Revenue impact · 12 months · Oct-2025 to Sep-2026" heading instead.
11. Usage without thousands separators; drawing "66,000 kgal".
12. A "What is missing" panel ("Today's size used for every month.") — not drawn.
13. Pager "1–8 of 8 · Rows per page" under the table — not drawn.
14. Proposed figures used: drawn "base $8.50 → $9.00, per kgal $4.25 → $4.60"; built repeats the version date twice and says "Billed" where there is no single now price.
15. The drawn input note "One row per capacity. A capacity-billed schedule takes a price per item. A charge code takes one amount a month." is absent (retired on purpose in 51dde0e48).
