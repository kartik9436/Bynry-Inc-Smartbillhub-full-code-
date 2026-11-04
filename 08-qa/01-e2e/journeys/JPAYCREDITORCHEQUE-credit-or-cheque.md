# J-PAY-credit-or-cheque — an account closes holding money, and the clerk is shown BOTH ways out: a cheque back, or leave it on the account

---
id: JPAYCREDITORCHEQUE
tier: 1
rules: [BR-PAY-007, BR-PAY-010, BR-PAY-014, BR-PAY-041, BR-PAY-1125, BR-SHL-025, BR-BIL-014, BR-TEN-043]
stories: [US-PAY-007, US-PAY-013]
---

<!-- `CR-138-BRC07` phase 4 `P4.23`, authored 2026-09-23 by LANE P4-TESTS.

     The filename carries the id for `G12` check 3 — see
     `JPAYCOUNTERSHIFT-a-shift-at-the-counter.md` for why.

     ⚠ **EVERY FIGURE BELOW WAS MEASURED.**
     `10-scripts/cr138_p4_journeys_readback.py` walks it on real PostgreSQL 16
     and prints what each step found, including the step where one of the two
     doors is correctly REFUSED. A journey written from a plan is `J19`
     (`DEF-112`). -->

**Intent.** The phase's own *done when*: **a clerk closing an account in credit
is offered both ways out.** Before `P4.12` only one of them was reachable from
payments — *"we can not have two path for 1 capabilities wew will confuse user"*
(PO, 2026-09-22) — and the answer was **one path, two doors**, never a second
implementation.

**Fixture.** Tenant brazos-bend, business day **2026-09-23**, on
`sbh_clone_p4walk` (2,072 accounts · 2,046 debtors). Measured:

| | |
|---|---|
| accounts holding **positive** credit | **1** |
| accounts holding **negative** credit | **0** on this clone; **181** on the aged one |
| the holder walked | `PY-260809-0061`'s account, **0.550000** unapplied |
| the payment behind it | **195.740000**, posted **2026-08-09** |
| holders that ALSO have an open bill | **0** |

⚠ **THE LAST ROW IS WHY THIS WALK ENDS WITH ONE DOOR OPEN AND ONE REFUSED, AND
THAT IS THE CORRECT ANSWER RATHER THAN A GAP.** A goodwill credit is raised
**against a bill** — `corrections.execute_credit_only` takes an invoice — so an
account with no open bill has nothing to credit today. `available: false` does
not mean *the feature is unbuilt*; it means *not on this account*, and
`BR-SHL-025` requires the reason to be on the control. *"Why can I not give them
a credit?"* is the question a greyed-out button leaves a clerk holding.

| # | Step · what she does | Handoff contract (what this step leaves) | Downstream assertions | Rule |
|---|---|---|---|---|
| 1 | Finds the account: it owes nothing and the utility is holding money | `billing_seam._credit_positions` — the SAME tenant-wide read `outstanding_positions` uses, so the debtor list and this screen cannot disagree about a figure they both print. Measured: **1** positive holder at **0.550000** | ⚠ **A NEGATIVE CREDIT IS A REAL DEBT AND IS NOT NETTED INTO THIS.** PO 2026-08-11, verbatim *"Yes, it's a real debt"*. `BR-PAY-1125` takes POSITIVE credit off a chase and leaves a negative one reported by name — **181 such accounts on the aged clone**, none of them made to look like credit | **BR-PAY-1125** · BR-PAY-041 |
| 2 | **Way out one — a cheque back.** She opens the refund path | `credit.refundable_position` → **0.550000 refundable**, with `contributing_payments` beside it: **1 payment**, `195.740000` on **2026-08-09** | ⚠ **THE EVIDENCE TRAVELS WITH THE FIGURE** (`CR-059` CS-7, PO ruling 2026-09-01 `OQ-195` option (a)): *"a credit built from two overpayments can be refunded, **listing the payments behind it**"*. A refund screen that showed only a total would leave a customer's *"where did that come from?"* unanswerable | **BR-PAY-014** |
| 2a | …and she cannot simply pay it | The read OFFERS the figure and raises nothing. `refunds.py` owns `BR-PAY-014`'s chain: **offset first**, then an **Admin approves** | ⚠ The readback writes nothing here on purpose. A second implementation of the offset-first test would eventually disagree with the one that actually pays the money | **BR-PAY-014** |
| 3 | **Way out two — leave it on the account.** She opens the credit door | `GET /accounts/{id}/credit-path` — **a DOOR, not a copy**. It computes no money, writes nothing and mints no write verb; the write is `POST /corrections…`, billing's, and always was. Measured on this account: `available` **false**, **0** bills | ⚠ **TWO REASONS COME BACK, NOT A SHRUG:** `credit_path_needs_an_open_bill` (*this account has no open bill to raise one against*) and `invoice_composition_unavailable` (billing publishes no per-bill composition read). A clerk is told which | **BR-SHL-025** · BR-BIL-014 |
| 4 | She sees **both**, reads the refusal, and takes the cheque | Measured, the two doors side by side: **refund OFFERED, 0.550000 refundable · credit REFUSED WITH ITS REASON** | ⚠ **THIS IS `P4.12` WORKING.** Before it, the credit was invisible from payments altogether — not refused, ABSENT — and a clerk closing an account in credit had one option and no idea there was another | **P4.12** |
| 5 | **INVARIANCE** — one path, two places | `corrections.execute_credit_only` has exactly **ONE** definition and its only callers are inside billing. The payments door forwards billing's own figures and re-implements no part of it | A grep that found a second `execute_credit_only`, or a payments-side credit write verb, is the defect this journey exists to make visible | **CR-059 §10** · `P4.12` |

---

## What a browser can actually drive, as of 2026-09-23 — and where this walk STOPS

**Steps 1 to 4 are drivable.** The refunds-and-credits list (6·1) moved into
payments with `P4.10` and `P4.26` put a **Kind** column and filter on it, so a
clerk standing on `/{tenant}/payments/refunds` sees refunds and credit notes in
one list. `IssueCreditDoor` is the control `P4.12` added and
`issueCreditDoor.dom.test.tsx` covers it.

⚠ **STEP 3 IS REFUSED ON EVERY ACCOUNT IN THE SEEDED SAMPLE, AND A READER
SHOULD NOT TAKE THAT AS A BROKEN SCREEN.** Measured: **0 of the 1** credit
holders on this clone has an open bill. To see the door OPEN, seed a credit onto
an account that still has an issued, unpaid invoice; the readback prints
`holders that ALSO have an open bill` on every run precisely so nobody has to
guess which case they are looking at.

⚠ **ONE ABSENCE IS CARRIED ON THE READ ITSELF AND IS NOT THIS JOURNEY'S.**
`credit_auto_application_has_no_caller`: `BR-PAY-010` auto-applies a carried
credit to the account's next issued bill, payments publishes
`apply_credit_at_issue`, and **nothing calls it** — the issue path is
`apps/billing/issue.py` and belongs to another module. So on this walk a credit
is **visible and refundable and does not settle the next bill by itself**. It is
reported on every refundable position rather than left silent.

### Two things this walk proved that nothing had asserted

1. **The two doors answer independently, and the refusal is a sentence.** The
   refund path offered `0.550000` on the same account where the credit path
   answered `available: false` with two named reasons. A screen that gated both
   on one flag would have hidden a lawful refund behind a missing bill.
2. **The credit-holder count and the negative-credit count are different
   questions and the product keeps them apart.** Measured: **1** positive
   holder and **0** negatives here, **181** negatives on the aged clone. A build
   that summed them would report 182 accounts *"in credit"*, of which 181 owe
   money.
