# Walk — Usage tab, Month by month, 2026-10-15

`DEF-CUS-10162` (no previous/current reading, no check) · `DEF-CUS-5146` (Read on /
Source stated absent). Decision log 2026-10-15, *USAGE TAB "MONTH BY MONTH"* (PO: *"go
ahead"*). Both defects stay **open** for the coordinator to close at release.

**Set-up.** Private copy `smartbillhub_usagewalk` (`createdb -T smartbillhub`, already at
the tip's migrations, dropped afterwards). `manage.py backfill_monthly_usage --tenant
brazosbend` was run on the copy first: the stored months were stale (**36 restated, 1
stated, 266 unchanged**), and without it no month on file summed more than one reading.
Backend `runserver` on **8019** (local settings). Two SPA builds (`vite build --mode
walk`) served by `server.mjs`: **before** = HEAD `fa67c4a55` on 8098, **after** = this
branch on 8099, both against the same backend. Staff Dana Whitfield, Brazos Bend, 1440px.
Script: `10-scripts/walk_usage_months_2026_10_15.mjs` (`WEB=`, `PREFIX=`, `ACCOUNTS=`);
it prints every row of the table by column.

## Before (HEAD)

| Shot | What it shows |
|---|---|
| `before-1-months-table.png` · `before-1-usage-tab.png` | A-10432: columns Month · Electric · Water · Read on · Source; every Read on and Source cell **Not recorded** |
| `before-2-months-table.png` · `before-2-usage-tab.png` | AC-2026-00049: the same, Sep 2026 Source **Estimated**, no readings anywhere |

## After (this branch) — PASS

**A-10432** (two services, a High month):

| Month | Service | Usage | Previous | Current | Read on | Source | Check |
|---|---|---|---|---|---|---|---|
| Aug 2026 | Electric | 628 kWh | 15,454 | 16,082 | 08/14/2026 | Manual entry (AMI) | Flagged (*Read interval*) |
| Aug 2026 | Water | 4 kgal | 837 | 841 | 08/14/2026 | Manual entry (Drive-by) | Flagged |
| Jul 2026 | Electric | 842 kWh | 14,612 | 15,454 | 07/31/2026 | Manual entry (AMI) | **High** (red) |
| Jul 2026 | Water | 9 kgal | 828 | 837 | 07/31/2026 | Manual entry (Drive-by) | OK |
| Jun 2026 | Electric | 412 kWh | 14,200 | 14,612 | 06/30/2026 | Manual entry (AMI) | OK |
| Jun 2026 | Water | 8 kgal | 820 | 828 | 06/30/2026 | Manual entry (Drive-by) | OK |

Every other month of the 24: *No reading*, the rest of the row empty.

**AC-2026-00049** (a month with two readings, one an estimate):

| Month | Service | Usage | Previous | Current | Read on | Source | Check |
|---|---|---|---|---|---|---|---|
| Oct 2026 | Electric | 1,200 kWh | 5,176 | 6,376 | 10/06/2026 | Manual entry (Walk-by) | Flagged |
| Sep 2026 | Electric | 1,760 kWh | 3,976 | *(blank — latest is an estimate)* | 09/30/2026 · *2 readings* | Estimated | Estimated |
| Sep 2026 | Water | 12 kgal | 2,788 | 2,800 | 09/24/2026 | Manual entry (Walk-by) | OK |
| Aug 2026 | Electric | 1,200 kWh | 2,776 | 3,976 | 08/25/2026 | Manual entry (Walk-by) | OK |

Shots: `after-1-months-table.png`, `after-1-usage-tab.png`, `after-2-months-table.png`,
`after-2-usage-tab.png`.

## Found on the walk

AC-2026-00049's Sep 2026 electric **1,760 kWh** is the 09/24 actual (1,200) **plus** a
bill-run estimate dated 09/30 (560) whose days the 10/06 actual (5,176 → 6,376) counts
again in October. 42 of the copy's 45 live estimates sit behind a later actual this way.
Filed `DEF-MET-10163`; not fixed here (it needs a metering/billing rule).

Not walked in a browser: a single-service account (every account on the copy has two
services) — covered by `AccountUsageMonths.dom.test.tsx`. Staff screen, so 390px is out
of scope (staff app is laptop and desktop only).
