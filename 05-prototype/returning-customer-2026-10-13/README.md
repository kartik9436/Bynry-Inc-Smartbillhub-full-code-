# Returning customer at move-in — E1 walk (CR-181-BRC10, BR-CUS-1119)

Walked 2026-10-13 by lane REOPEN on a **private copy** of the dev database
(`smartbillhub_reopen`, dropped afterwards), Brazos Bend Utilities, as Sam Reyes
(Billing Clerk) at 1440 px, through `10-scripts/cr181_returning_customer_walk.mjs`.
Every check below printed PASS.

**Set-up:** Viktor Valdez (C-00022 — his record holds a name and a phone, no SSN,
no date of birth) had AC-2026-00022 on SCW-U-022. It was closed by a move-out on
09/30/2026. The books said it still owed **$168.18** (AR net of credit held).

## Pass A — *Carry it* (MVI-26-0027)

| Shot | What it shows |
|---|---|
| `A-1-unit.png` | Step 1, History: *Viktor Valdez · AC-2026-00022 · Closed 09/30/2026 · Owes $168.18* |
| `A-2a-search.png` | Search with name + phone: **Same name and phone** + **Lived here last**, AC-2026-00022 *$168.18 due* |
| `A-2b-reopen-pay-first.png` | Linked: *Returning customer* — **Reopen AC-2026-00022** / New account, *Owes $168.18*, *Must pay first* chosen |
| `A-4-review.png` | Review: *Reopened AC-2026-00022 · Must pay first*; account number *Reopened AC-2026-00022* |
| `A-4b-refused-pay-first.png` | Complete refused — *Pay the old balance first.* — and the wizard lands on the Customer step with the sentence beside the choice |
| `A-2f-carry.png`, `A-4c-review-carry.png` | *Carry it* → Review *Reopened AC-2026-00022 · $168.18 carried* |
| `A-5-completed.png` | Completed on **AC-2026-00022** (no new number) |
| `A-6-details.png`, `C-details-MVI-26-0027.png` | Details: *Returning customer — Reopened AC-2026-00022 · $168.18 carried* |
| `A-7-move-ins-list.png` | Move-ins list: *Reopened AC-2026-00022* under the customer |

## Pass B — *Must pay first* (MVI-26-0030)

AC-2026-00022 closed again by a move-out on 10/14/2026, still owing $168.18.

| Shot | What it shows |
|---|---|
| `B-2c-record-payment.png`, `B-2d-…` | *Record payment* opens Payments' own *Record a payment* on AC-2026-00022 — balance $168.18, amount 168.18, ACH |
| `B-2e-after-payment.png` | After the payment the step reads *Nothing owed* (figure re-read from the ledger) |
| `B-4-review.png` | Review: *Reopened AC-2026-00022 · Must pay first* |
| `B-5-completed.png`, `C-details-MVI-26-0030.png` | Completed on AC-2026-00022; details *Reopened AC-2026-00022 · Paid first* |

`C-settings-billing-defaults.png` — Settings › Configure › Reference data › Billing
defaults: **Reopen closed accounts within 5 Years** (B4, System Admin).

## Records checked (read from the database after each pass)

| Check | After pass A | After pass B |
|---|---|---|
| `accounts` AC-2026-00022 | active · opened 10/13/2026 · closed — · the only account on the unit | active · opened 10/15/2026 · closed — |
| `service_agreements` | 2 old rows kept (08/01 → 09/30) + 2 new from 10/13 | + 2 rows 10/13 → 10/14 (closed by the second move-out) + 2 new from 10/15 |
| Owed (ledger) | **$168.18** — carried onto the reopened account | **$0.00** after payment PY-261013-0086 $168.18 |
| Issued money rows | 5 invoices · 53 journal lines — digest `966c01cf46a34257`, **identical to the source database** (nothing issued was changed) | 6 invoices · 55 journal lines — the 6th invoice is the second move-out's final-bill draft and the 2 lines are the payment's; no earlier row changed |
| `move_in_reopenings` | MVI-26-0027 · **carry · $168.18** · was 08/01 → 09/30 | MVI-26-0030 · **pay_first · $0.00** · was 10/13 → 10/14 |
| `audit_log` | `account.reopened` (before closed 09/30, after none) · `account.moved_in` · `move_in.reopen_balance` (carry, 168.1800) | the same three, pay_first 0.0000 |

**Noticed on the walk, not changed here:** the move-in's *Messages* tile counts the
whole account's messages (15 on the reopened account, earlier tenancy included),
and *Earliest legal start* reads *No earlier tenancy* because the tenancy before is
the same account. Both are listed as open items in `CR-181-BRC10` §4.
