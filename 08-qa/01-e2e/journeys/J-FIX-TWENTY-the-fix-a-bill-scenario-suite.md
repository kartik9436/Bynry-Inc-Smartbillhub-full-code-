# J-FIX-TWENTY: the Fix a bill scenario suite (revamp, 2026-10-12)

The end-to-end walk the PO asked for on 2026-10-12, verbatim: *"in end to end web walk please create scenarios based on all account type, for one cutomer one moth, for one cutomer several month , for one change or multiple change in bill, for bulk cycle, for bulk specific run upto 50 or 100 accounts … once the bills corect you shoud check data record in bill table, in general ledger table, emailsent , payments chnages updated or not ; prorated cases are habdle or not please check in walk"*.

**Tenant:** `brazosbend` has 77 accounts:
- 63 residential (single-family and multi-family)
- 12 commercial (small commercial, 3 of them master accounts)
- 1 light industrial
- 1 municipal

Six of them use autopay, and their states are Active, Pending activation, Vacation hold, Marked disconnect and Closed. A 100-account run does not exist on this tenant, so **S17 seeds the accounts it needs** through the product's own import, and says so.

**Bulk "cycle"** means the billing run of one cycle (for example *Cycle 7 · October 2026*), because Bulk's sub-options are *a billing run* and *a price mistake* (decision log 2026-10-12, items 1–2). **The drawing** is `05-prototype/fix-a-bill-2026-10-12/` (23 images).

## Scenarios

| # | Account type | Option · bills | What was wrong | Prorated? | Payment state before | Must see |
|---|---|---|---|---|---|---|
| S1 | Residential · single-family | One customer · one bill | Wrong reading (one change) | No | Unpaid | New bill on the corrected usage; old bill *Corrected* |
| S2 | Residential · single-family · autopay | One customer · one bill | Wrong plan (bill rises) | No | Paid in full by autopay | Payment moves to the new bill; only the difference is owed; autopay not charged twice |
| S3 | Residential · single-family | One customer · one bill | Several changes: reading + tax + missed charge (bill falls) | No | Paid in full | Leftover becomes account credit, not a refund |
| S4 | Residential · multi-family unit | One customer · several months (3) | Wrong rate (one change, all months) | No | Mixed: 2 paid, 1 unpaid | One case, 3 credit notes + 3 new bills, payments moved per bill |
| S5 | Commercial · small commercial | One customer · several months (3) | Several changes: plan + goodwill on one month + name fix | No | Unpaid | Strongest wins (re-price); goodwill as a credit line; name on the reissued pages |
| S6 | Commercial · master account | One customer · one bill | Goodwill only | No | Unpaid | Credit only: a credit note, no new bill, concession posted |
| S7 | Industrial · light industrial | One customer · several months (2) | Wrong rate on electric (time-of-use + demand lines) | No | Unpaid | Demand and on/off-peak lines re-priced, kW and kWh unchanged |
| S8 | Municipal | One customer · one bill | Reprint only: mailing address + template | No | Paid | No ledger entry; the reissued document is queued; the amounts are identical |
| S9 | Residential · single-family | One customer · one bill | Wrong reading on a bill crossing a mid-month price change (15 and 20 Sep) | **Yes** | Unpaid | Per-part lines add back to the full usage; each part priced on its own version; base charge once |
| S10 | Residential · single-family | One customer · one bill (move-out final bill) | Wrong period dates (move-out date) | **Yes** | Unpaid | Base charges prorated days/days; usage on the corrected dates |
| S11 | Commercial · small commercial | One customer · one bill in a closed month (Aug) | Wrong tax | No | Unpaid | Entries post in the earliest open month; the posting month is shown before approval |
| S12 | Residential · single-family | One customer · one bill | Wrong deposit ($0 → $150) | No | Unpaid | Deposit untaxed, posted to customer deposits held (a liability), not revenue |
| S13 | Residential · closed account (final bill) | One customer · one bill | Missed charge | No | Unpaid | The balance stays outstanding on the closed account (no write-off, PO 2026-10-12) |
| S14 | Any | One customer · a draft bill, and a bill already in an open case | — | — | — | Refused at Bills with the reason; nothing saved |
| S15 | Mixed, whole run | Bulk · the cycle's run (Cycle 7 · October, about 48 bills) | Wrong tax | No | Mixed | Up and down shown apart; every bill done; per-bill credit note + new bill |
| S16 | Mixed, part of a run | Bulk · specific run, only Water (about 50 accounts) | A charge was missed | No | Mixed | Only water bills touched; others listed as left as they are |
| S17 | Mixed, 100 accounts (seeded) | Bulk · specific run of 100 | Wrong plan, with one bill made to fail | No | Mixed | 99 done, 1 failed, no rollback of the 99; resume touches only the failure |
| S18 | Mixed, across runs | Bulk · price mistake: water tier 2, Aug 1 – Sep 30 (two runs) | Wrong rate (price fixed in Plans & Rates first) | **Yes**, where a period crosses the change | Mixed | Bills from both runs found; split periods re-priced per part |
| S19 | Any | Any | Figures change between preview and approval | — | — | Approval refused: *Figures changed. Check again.* |
| S20 | Any | Any | The clerk leaves before Send | — | — | Nothing saved; the bill is not locked by a half-finished case |

## The record checks, after every scenario that issues

| Area | Table | Check |
|---|---|---|
| Bills | `invoices` (old) | status `corrected`; printed snapshot byte-identical to before |
| | `invoices` (new) | a new number; `corrects_invoice_id` = old bill; total = preview |
| | `invoice_lines` | old lines untouched; new lines = the preview's lines (incl. prorated parts) |
| | `credit_notes` | one per bill (none for reprint only); amount = old total (re-price) or the credit (credit only) |
| | `correction_cases` · `correction_case_bills` · `correction_case_items` | case done; one row per bill with its result; one row per correction |
| General ledger | `journal_entries` · `journal_lines` | two balanced entries per bill (credit note + new bill), never netted; net per account = the Check step; dated in the bill's month or the earliest open one; deposit to the liability; tax per authority |
| Delivery (email) | `outbound_messages` | one row per document per channel: paper always, email where the account chose it. Queued, not sent: no provider runs locally, and *queueing is not sending* (`billing/delivery_seam.py`). |
| Payments | `allocations` · account credit | old allocations not edited; new allocation rows to the new bill; leftover = account credit; autopay not re-captured; balance after = the Check step |
| Meter Reads | read batches · `read_corrections` | the corrected reading saved and locked on issue |
| Audit | `audit_log` | rows for case sent, approved, each bill done or failed, closed without correcting |
| Screen | every step | no database id visible (B14 rule 31); figures match the preview |
