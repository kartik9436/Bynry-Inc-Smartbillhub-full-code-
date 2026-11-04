# Move-out drafts the final bill — walk of 2026-10-13

**What was built:** the PO's ruling of 2026-10-13, option B (`DEF-CUS-10093`). Pressing **Complete** on a move-out now creates the final bill as a **draft**, from step 3's readings and date, in the same act and before the account closes. The clerk sends it from Billing. If the bill cannot be created, the account stays open and the reason is shown.

Build `2.572.0` + this lane, tenant `brazosbend`, signed in as Dana, on private copies of the demo database (`smartbillhub_mvo2`; scenario 9 and the multi-family re-walk on `smartbillhub_mvo3`). Move-out date **10/12/2026** for every case. Every move-out went through the screens, and every draft was opened from the completion screen's link and approved on the bill page (`10-scripts/def_cus_10093_move_out_final_draft_walkthrough.mjs`). Record checks are in `records/` (made with `records/check.sh`).

**Data set up first, through the product's own payment door** (`payments.services.record_payment`), because no demo account with a deposit has a billing cycle: a $150.00 deposit on AC-2026-00002, a $500.00 deposit on AC-2026-00012, and a $500.00 payment on account on AC-2026-00009.

## Scenarios

"Step 3" is the *Final bill, net* the screen showed before Complete. "Draft" is the bill Complete created.

| # | Case | Account | Readings | Step 3 | Draft | Account | Issued from Billing | Journal | Deposit / refund / owner | Deliveries | Audit | Id on screen |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Residential, owes | AC-2026-00001 (Ana Alvarez) | prefilled (no use since 11 Oct) | **$186.36** | **BL-2610-000251 $186.36**, final, 10/01–10/12, base prorated $4.65 + $3.10, marked as made by a move-out | closed 10/12 | issued | 186.36 / 186.36 | none held | 3 queued (email, print, portal) | drafted → closed → issued → sent | none |
| 2 | Multi-family unit, sub-meter on Estimate | AC-2026-00043 | +5, SM-7042 estimated | **$282.46** (was $239.21 before `DEF-MET-10111`) | **BL-2610-000258 $282.46** | closed | issued | 282.46 / 282.46 | none held | 3 queued | yes | none |
| 3 | Commercial, demand meter | AC-2026-00047 | +30 | $1,551.59 | BL-2610-000252 $1,551.59 | closed | issued | balanced | none held | 3 queued | yes | none |
| 4 | Industrial | AC-2026-00050 | +50 | $5,392.07 | BL-2610-000253 $5,392.07 | closed | issued | balanced | none held | 3 queued | yes | none |
| 5 | Municipal | AC-2026-00049 | +40 | $510.76 | BL-2610-000254 $510.76 | closed | issued | balanced | none held | 3 queued | yes | none |
| 6 | Residential in credit | AC-2026-00009 | +10 | $413.27 | BL-2610-000255 $413.27 | closed | issued | balanced | $413.27 of the $500.00 credit applied to the bill at issue. ⚠ Step 3 offered **Refund $156.09**; the books say about $121.41 (`DEF-CUS-10112`, open) | 3 queued | yes + credit.applied | none |
| 7 | Deposit + owes | AC-2026-00002 | +50 | $662.11 | BL-2610-000256 $662.11 | closed | issued | bill 662.11 / 662.11; deposit 150.00 / 150.00 | **Deposit applied:** DR deposit liability $150.00 / CR receivable $150.00; $720.61 still owed on the closed account | 3 queued | yes | none |
| 8 | Deposit + credit | AC-2026-00012 | +10 | $423.29 | BL-2610-000257 $423.29 (09/01–10/12: no September bill) | closed | issued | bill 423.29 / 423.29; deposit 500.00 / 500.00 | **Refund:** DR deposit liability $500.00 / CR receivable $423.29 / CR customer credit **$76.71** | 3 queued | yes | none |
| 9 | Balance to owner (step 3 *Tie it back*) | AC-2026-00041 | +15, master + sub-meter estimated | $509.29 | BL-2610-000251 $509.29 (copy 2) | closed | issued | 509.29 / 509.29 | Decision recorded: transfer **$1,053.78** to owner account AC-2026-00053. **No money moves** (existing rule); the owner's balance stays $0.00 and the debt stays on the closed account | 3 queued | shortfall_decided + closed + issued | none |
| 10 | Autopay | A-10432 | +20 | not priced (no billing cycle) | **none: refused** | **stays open** | — | — | — | — | nothing written, no readings kept | none |

Scenario 10 is the refusal path working: *"Final bill not created. Account still open. No billing cycle. Assign one on the account."* No demo account with autopay has a billing cycle, so no autopay move-out could complete.

## What else was checked

* **Nothing else bills a closed account.** Covered by tests: a One-time Final for any later day is refused, and an interim draft made before the close is refused at Send. Only the move-out's own final draft may be sent after the close.
* **The move-out screen issues nothing.** Every bill above was still a draft until it was approved on the Billing bill page.
* **Quantities** show at most 2 decimals: `193.55 kWh @ $0.12`, never 28 places (`DEF-BIL-10095`).

## Defects

| Id | What | State |
|---|---|---|
| `DEF-CUS-10093` | A move-out never produced a final bill | **Fixed**: Complete drafts it |
| `DEF-BIL-10095` | Prorated quantities at 28 places | **Fixed** (display only) |
| `DEF-MET-10110` | Step 3 dropped a reading typed over an earlier committed one (Ana: $186.36 vs $246.93) | **Fixed** |
| `DEF-MET-10111` | Step 3 dropped the main meter's typed reading when a sub-meter on the same point was estimated | **Fixed** |
| `DEF-CUS-10112` | Step 3 counts an older overpayment twice for a customer in credit ($156.09 vs $121.41) | **Open**: money path, not this ruling |

## Left open

* **Moving a balance to the owner or master** is recorded and moves no money. That is the rule as written (`move_out_settlement.shortfall_decision`). Whether the money should move needs a ruling.
* **Paying the refund out** belongs to Payments. The move-out leaves the money in customer credit.
* While step 3 is still loading, it shows *"The closing period is not priced."* A clerk can read that as a refusal.
