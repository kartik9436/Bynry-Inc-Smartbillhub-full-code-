# Walk — the bill run applies the late fee, 2026-10-17

`DEF-BIL-10200` (the run never applied a late fee) · `DEF-BIL-10201` (a Flat late-fee code
charged $0.00) · `DEF-BIL-10202` (found on this walk, fixed and re-walked). Decision log
2026-10-17 *"THE LATE FEE IS APPLIED BY THE BILL RUN, AND MAY BE FLAT OR A PERCENTAGE"*, its
two same-day paragraphs (*"once per billing period"*; payment plans *"no"*) and the lane's
*"AS BUILT: FIVE LANE JUDGMENTS"*. The defects stay **open** for the coordinator to close at
release.

**Set-up.** Private copy `smartbillhub_latefee` (a dump of the dev database at this branch's
migrations — `createdb -T` was refused because the dev server holds the template; dropped
afterwards). Backend `runserver` on **8029** (local settings, this branch), SPA
`vite build --mode compose` served by `server.mjs` on **8109**. Staff Dana Whitfield,
Brazos Bend, Chromium 1440px. Script: `10-scripts/walk_late_fee_2026_10_17.mjs`.

The world, written by a set-up script on the copy only: a new cycle **LF-WALK** (June 2026,
bill date **1 Jul**, due 21 days) and four electric accounts, each holding one ISSUED May bill
due **10 Jun**. `LATE` is the tenant's seeded code (1.5%, minimum $5.00, grace from Billing
defaults: 5 calendar days, so grace runs out after **15 Jun**); `LATEFLAT` is a new penalty
code, amount rule **Flat $10.00**, grace 5 calendar days, booking to the same 4200 account.

| Account | Plan's late-fee code | May bill | Paid | Expected |
|---|---|---|---|---|
| LF-A | LATE | $100.00 | money arrived **20 Jun** (after grace) | **$5.00** |
| LF-B | LATE | $24.99 | unpaid | nothing — under the $25.00 floor |
| LF-C | LATEFLAT | $900.00 | unpaid | **$10.00** (flat) |
| LF-D | LATE | $542.10 | unpaid | ❄️ GT-8 **$8.13** — waived on the walk |

## What the screen said — 17 of 17 PASS

1. **Check → Payments & balances → Late fee due** (`1440-02-late-fee-pane.png`):
   **"3 accounts · late fees $23.13"**; rows *LF-A $5.00 on $100.00 overdue.*, *LF-C $10.00 on
   $900.00 overdue.*, *LF-D $8.13 on $542.10 overdue.*; LF-B absent. Each row reads **Apply**
   with nobody having answered; the bar says *"Waive one account at a time."* and offers no
   Waive for the whole tag. *Need a decision* reads **0** and *Ready* **4**: a late fee bills
   unless waived, it does not hold an account.
2. **Waive LF-D on its own row** (`1440-03-after-waive.png`): the line becomes **"2 accounts ·
   late fees $15.00"**.
3. **Price 4 accounts → Sign off → Send** (`04`, `05`): four bills issued.
4. **The bills** (`1440-06-bill-LF-*.png`, Charges tab):

   | Bill | Account | Total | Late-fee line | Taxable | Journal Dr = Cr | Late-fee GL (4200) Cr |
   |---|---|---|---|---|---|---|
   | BL-2607-000251 | LF-A | $72.94 | *Late payment fee* **$5.00** | No | 72.94 = 72.94 | 5.00 |
   | BL-2607-000252 | LF-B | $67.94 | — | — | 67.94 = 67.94 | 0.00 |
   | BL-2607-000253 | LF-C | $77.94 | *Late fee (flat)* **$10.00** | No | 77.94 = 77.94 | 10.00 |
   | BL-2607-000254 | LF-D | $67.94 | — (waived) | — | 67.94 = 67.94 | 0.00 |

   $67.94 is each account's June electricity (412 kWh × $0.12 = $49.44 + $18.50 base).
5. **No double.** The Check prepared the accounts and Calculate prepared them again; each bill
   carries ONE late-fee line. A second run over the same cycle and period is refused by
   BR-BIL-005 (*"a bill run over this cycle and period already exists"*), and an account that
   already holds a bill for the period carrying its late fee is never charged a second one
   (`test_a_bill_for_this_period_already_carrying_the_fee_stops_a_second`).

## Found on the walk, and fixed before the re-walk

**`DEF-BIL-10202`** — the first walk's pane read *Late fee due · Needs a decision* and *"3
accounts. A late fee applies. Fixed in Payments."* above *"3 accounts · late fees $23.13"*,
while the *Need a decision* tile read 0, and it drew row checkboxes that selected for
nothing. A fee the run applies unasked needs no decision and is answered on the Check, not
in Payments. Red first (`CheckLateFee.dom.test.tsx`, *"no Needs-a-decision pill, no
fix-screen sentence, one count line"* — failed on the base pane), fixed in `CheckPanes.tsx`,
re-walked on a fresh copy: 17 of 17.

## Not walked, and where it is proved instead

- **The next period still overdue gets its own fee; a bill paid late is fined once** — the
  decision log's own figures (October $5.00 on $100, November $5.00 on $180; paid 10/05 →
  November nothing) in `test_the_next_period_still_overdue_gets_its_own_fee_and_a_bill_paid_late_is_fined_once`.
- **A live payment plan → no late fee** (Ana, $62 → $0.00) in
  `test_a_live_payment_plan_is_charged_no_late_fee`.
- **Seen and not ours:** each fee line reads *"Charge code not readable yet"* under its
  description — `DEF-2428` (open since 2026-08-30: rating publishes no charge-id → code read),
  true of every fee line ever billed. The *No services on file* warnings come from the walk's
  fixture units, which state no service agreements.
