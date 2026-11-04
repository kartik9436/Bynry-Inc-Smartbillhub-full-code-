# Walk — an estimate behind a later reading is not counted twice, 2026-10-15

`DEF-MET-10163` · PO ruling 2026-10-15, *"go with 1 and 3"* (decision log *"AN ESTIMATE
BEHIND A LATER ACTUAL READING IS NOT COUNTED TWICE"* and *"DEF-MET-10163 AS BUILT"*). The
defect stays **open** for the coordinator to close at release.

**Set-up.** Private copy `smartbillhub_mv10163` (`createdb -T smartbillhub`, at the tip's
migrations, dropped afterwards). Backend `runserver` on **8021** (local settings, this
branch), SPA `vite build --mode compose` served by `server.mjs` on **8101**. Staff Dana
Whitfield, Brazos Bend, 1440px. Script: `10-scripts/walk_usage_months_2026_10_15.mjs`
(`WEB=http://127.0.0.1:8101 OUT=05-prototype/walk-def-met-10163-2026-10-15 PREFIX=…
ACCOUNTS=01a12b2c-6bbd-7c28-8159-9f59f551dac9`).

The stored months on the copy were stale (no month summed more than one reading), so
**before** = `manage.py backfill_monthly_usage --tenant brazosbend` run with the BASE code
(`ecd82f49f`): *1 stated, 36 restated, 266 unchanged*. **After** = the same command with
this branch: *34 restated, 268 unchanged, 1 withdrawn* — which is exactly what a deploy
does to history.

## AC-2026-00049, Usage tab, Month by month

| Month | Service | Before | After |
|---|---|---|---|
| Oct 2026 | Electric | 1,200 kWh · 5,176 → 6,376 · 10/06 | 1,200 kWh · 5,176 → 6,376 · 10/06 (unchanged) |
| Sep 2026 | Electric | **1,760 kWh** · 3,976 → *(blank)* · 09/30 *2 readings* · Estimated | **1,200 kWh** · 3,976 → 5,176 · 09/24 · Manual entry (Walk-by) · OK |
| Aug 2026 | Electric | 1,200 kWh | 1,200 kWh (unchanged) |

Shots: `before-1-months-table.png`, `before-1-usage-tab.png`, `after-1-months-table.png`,
`after-1-usage-tab.png`. Aug + Sep + Oct after = 3,600 kWh = the register's 2,776 → 6,376.
The 560 kWh estimate row is still in the register, untouched (it is on issued bill
BL-2610-000160, which is not re-priced).

## On the whole copy

- **42 of the 45** live estimates sit behind a later actual reading that did not true them
  up; each now leaves its month's sum.
- **1 month withdrawn:** AC-2026-00054's Sep 2026 electric (280 kWh) held only a bill-run
  estimate dated 09/30 (09/25 → 09/30), and AC-2026-00042's 10/07 reading on the **same
  meter** measures from 09/25 — so those days are already counted under 00042, and 00054's
  September now reads *No reading*. The rule is per meter; this is the cross-account case
  the decision log names.

## The bill run (part 2) — on the seam, against the copy

`metering.selectors.billing_reads_for_unit` for AC-2026-00049's unit over **09/25 → 09/30**
(the stretch after its last billed reading), read-only probe:

```
water    | consumption None   | absent no_read | covered_by 01a12b2e-c321-… 2026-10-06
electric | consumption 560    | absent None    | covered_by None
services a missing-read decision would NOT be raised for: ['water']
```

Water has no reading in the stretch and its 10/06 reading (2,800 → 2,812, measured from
09/24) already covers it, so a run over that stretch raises no *missing read* for water and
cannot estimate it — before this branch it would have asked the clerk to. (Electric shows
the 560 estimate already on file, which billing reads as that stretch's reading — issued
history, not changed.) The full flow — prepare, calculate, issue, next month — is asserted
in `tests/test_def_met_10163_covered_estimate.py::…a_bill_run_makes_no_estimate…`: Aug 31
read 1,000, 10/06 read 1,012 posted first → September raises no missing read and bills no
estimate, October bills **12 kWh** for 12 measured. Not clicked through the Billing screens.
