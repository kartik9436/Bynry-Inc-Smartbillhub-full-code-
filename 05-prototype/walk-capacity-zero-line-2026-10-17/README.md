# Walk — a $0.00 capacity line is left off the bill (2026-10-17)

Ruling: decision log *"2026-10-17 — A $0.00 CAPACITY LINE IS LEFT OFF THE BILL; MUNICIPAL SOLAR IS SETUP, NOT CODE"*. Defect: `DEF-RAT-10210`.
Build: engine stage 3 (`06-backend/apps/rating/pricing/stages/price_usage.py`) no longer emits a capacity line whose rate is exactly $0, so no `$0.00` row is stored and every screen reads the same lines.

## How it was walked

- A private copy of the dev database (`createdb -T smartbillhub smartbillhub_cap0`), the worktree's backend on 8030 and its built SPA on 8110. Both servers stopped and the copy dropped afterwards.
- `10-scripts/capzero_walk_prep.py` seeded a cycle of its own, `CAP0-SOLAR`, with two accounts, a 4% tax and portal logins:
  - **CAP0-FLAT** (AC-2026-00057, Rosa Delgado): solar 6 kW (one SOL-P6) and battery 10 kW (one BAT-10), plan *Solar + battery flat fee*. Both schedules are $0.00 per kW. BASE-SOL $25.00, BASE-BAT $25.00.
  - **CAP0-MUNI** (AC-2026-00058, Hal Brenner): solar 6 kW, plan *Municipal Solar*. $4.00 per kW, BASE-MSOL $10.00 for all sizes.
- `10-scripts/capzero_walkthrough.mjs` ran a September bulk run in Chromium at 1440 wide (Scope, Check, Sign off, Send; bill date 1 Oct). It then read each bill's Charges tab, the bill as sent and the PDF, and signed into the customer portal for each bill. **14 of 14 checks passed.**

## What the walk showed

| Bill | Lines | Tax | Total |
|---|---|---|---|
| BL-2610-000251, flat fee | solar base charge $25.00 · battery base charge $25.00 (**no `$0.00` capacity line**, and none is stored) | 4% = $2.00 | **$52.00** |
| BL-2610-000252, Municipal Solar | solar 6 kW × $4.00 = $24.00 · solar base charge $10.00 | 4% = $1.36 | **$35.36** |

The same lines appear on every surface. The Sign off review totals $87.36 ($52.00 + $35.36) across 2 draft bills.

## Screenshots

- `01`–`05`: the bulk run (scope, check, sign off, send, sent).
- `10`, `12`: the flat-fee bill's Charges tab. Two $25.00 lines and the tax; no $0.00 row.
- `11`, `13`: the same bill as it was sent. `flat-bill.pdf` and `flat-bill.txt` hold the PDF and its text.
- `15`, `17`: Municipal Solar's Charges tab, showing 6 kW · $4.00 · $24.00, $10.00 and tax $1.36.
- `16`, `18`: Municipal Solar as it was sent. `muni-bill.pdf` and `muni-bill.txt` hold the PDF and its text.
- `20`, `21`: the flat-fee bill in the customer portal, and its printed bill.
- `25`, `26`: the Municipal Solar bill in the customer portal, and its printed bill.
- `walk-facts.json`: the stored lines of both bills and the text read off each screen.

## Seen on the way (not part of this change)

- The tax rate shows as `$0.04` on the staff Charges tab and as `0.04` on the printed bill and PDF. The portal shows `4.00%`. The staff half is already filed and open as `DEF-BIL-9317`.
- First attempt: the bill date was 1 September, which is in a CLOSED fiscal period. Every bill failed to post, and the Sent card read *"0 bills sent"* while the side panel read *"2 bills sent"*. Neither said why. The walk was re-run with the bill date in October. This is reported to the coordinator rather than filed, because it sits in the bill-run screens a sibling lane is changing.
- A capacity service's line on the bill is worded *"solar usage tier 1 (0+ kW)"*, and *Services this period* says *"read"* for solar and battery. These wordings were here before this change.
