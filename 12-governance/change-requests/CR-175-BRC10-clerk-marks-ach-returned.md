# CR-175-BRC10 — A billing clerk may mark an ACH payment returned, on any day, with a reason and the bank code; the returned-payments process then treats it exactly like a US Payments return

**Raised:** 2026-10-07 by the Product Owner, in chat (decision log row of 2026-10-07 that starts *"PO RULING — A BILLING CLERK MAY MARK AN ACH PAYMENT RETURNED"*).
**Status:** **BUILT — 2.561.0, 2026-10-07 (lane ACH-RETURN), commit `33a4665b2`.** 🔒 human review pending (`09-human-review-ledger.md`).
**Branch:** `claude/charming-pascal-k7i2lr` (`BRC10`). `10-scripts/allocate.py cr` answered **175** against the remote and `--verify 175` reported it free on every branch at allocation.
**Classification (`13-change-process.md` §1):** a **CHANGE** — today a billing clerk cannot record an ACH payment the bank sent back days later; only a System Admin can. It **reverses a signed rule for one case** (`BR-PAY-1070`'s Admin-only reversal gate) and **touches money** (a reversal, a ledger mirror, a bill owed again) and the 🔒 reversal service. One part is a **DEFECT** found while verifying the ruling: the returned-payments process picks up no return at all (`DEF-PAY-10010`).

## 0 · What arrived, in the requester's words (verbatim)

| | The PO, verbatim |
|---|---|
| The prompt | *"My recommendation is (A). - Even Clark can mark ACH returned and same effect wil ahppen"* |
| The ruling, option (a) | *"(a) Let billing clerks mark an ACH payment returned, any day, with a reason and the bank code. The same effect follows: balance restored, fee and notice."* |

The example the PO was shown: Dana, a billing clerk, sees on the 10 Oct bank statement that Rosa's $100 ACH from 7 Oct came back; before this change the product refused her and she had to ask the System Admin.

## 1 · What is reversed, and what is NOT (step 2)

- **`BR-PAY-1070` — *"reversing a payment is Admin-only, and the gate is on the service as well as the route"*** — is SUPERSEDED **for exactly one case**: a payment whose tender is ACH, returned by the bank, recorded with a bank return code and a return reason, by a billing clerk. Everything else in `BR-PAY-1070` stands.
- **NOT reversed:** `OQ-PAY-12603` (c) — a clerk's own same-day, same-till reversal — is unchanged (and is itself still unbuilt: `DEF-PAY-10011`). A clerk still may NOT reverse a card, cash or cheque payment from another day. `reverse_payment` itself keeps `@require_role(SYSTEM_ADMIN)`; the clerk's path is a second, narrower service that delegates to it. `REVERSAL_REASONS` stays the closed four-word set. No frozen B4/B5 figure is touched.

## 2 · Judgments made in this lane (each recorded in the decision log the same day)

1. **How ACH is identified:** by the tenant's payment method code `ach` (`tenancy.PaymentMethod.code`) — the same code US Payments' tender mapping lands `ACHCHECK` / `ACHSAVINGS` on, and the code `BR-PAY-011`'s 60-day window is keyed by.
2. **Which reasons a clerk may give:** the two a bank return can carry — *Returned by the bank* (`nsf`) and *Chargeback* (`bank_chargeback`). The two staff-correction reasons (*Recorded wrongly*, *Customer dispute*) stay a System Admin's Reverse.
3. **A second return of the same payment is refused by name**, never answered as success; the SAME submit retried is a replay (hard rule 6).
4. **The returned-payments process reads every reversing row that carries a bank return code** — whoever recorded it — as a returned item. That is both a US Payments return and a clerk's. The reversal is already done at arrival (reading (A)), so step 4 reports it as already reversed and step 5 drafts the fee (the tenant's charge code) and queues the notice; where the reversal already queued the customer's *payment failed* letter (an `nsf` return), the runbook does not queue a second one.

## 3 · Before and after (what was true, measured on PostgreSQL 16)

**Before:** Runbook 26 stopped at step 1 on every run — *"No returns have landed."* — because its read hardcoded *no column holds a bank return code*. A US Payments R01 return of $147.85 reached it only as *"1 were reversed by hand in this window"*; no fee was drafted and no notice handled for it. A clerk could not record an ACH return at all. **So the process picked up neither.**

**After (2.561.0, PostgreSQL 16):** a clerk's R01 return of Rosa's $100.00 and a US Payments R01 return of $147.85, run for 10 Oct with charge code NSF: the runbook finds **two items**, step 4 reads *Already reversed* for both, step 5 drafts **a fee for each** and records the notice the same way for both (the reversal already queued the *payment failed* letter, so none is queued twice). `tests/test_cr175_clerk_ach_return.py::test_the_runbook_picks_up_a_clerk_return_and_a_us_payments_return_alike`.

## 4 · Open, not this lane

- `DEF-PAY-10011` — `OQ-PAY-12603` (c) ruled and never built.
- `DEF-PAY-10012` — a return whose code maps to *Chargeback* (every code but R01/R09) on a payment that paid a bill needs an approval under `BR-PAY-011`: US Payments answers 400 and nothing is reversed, and a clerk choosing *Chargeback* is refused the same way. Pinned by a test; a reading of `BR-PAY-011` for the coordinator, not decided here.

## 5 · Built

**Backend.** `reversal.mark_ach_returned` (🔒, HUMAN-REVIEW-PENDING, ledger row 2026-10-07) — gated System Admin + Billing Clerk; ACH only (`method.code == "ach"`); money that arrived only; reason `nsf` or `bank_chargeback`; Nacha code required and checked by CR-174's own `_return_code`; a second return refused by name, the same submit replayed; delegates to `reverse_payment.__wrapped__`, whose Admin-only gate is unchanged. `POST /payments/{id}/mark-returned` (`AdminOrClerk`). `GET /payments/{id}` → `actions.mark_returned {offered, allowed, reason}`. `runbook_reads.returned_items_landed` reads every reversing row carrying a bank code; Runbook 26 reports them *Already reversed*, drafts the fee, skips a second letter for an `nsf` return, and counts the privilege without double-counting a return already on the books.

**Frontend.** Payment detail: **Mark returned**, danger tier, drawn only on an ACH payment, disabled with its reason for another role or once returned. `MarkReturnedModal` (new component, on the Route B ledger): *Why* (Returned by the bank · Chargeback), *Bank code*, *Bank return date*, *Memo*, and a consequence box *"$100.00 is owed again. Fee and notice follow."* On success the clerk lands on the reversing payment, which shows *Bank code R01*. 15 keys in eleven catalogues.

**Proof.** Backend `tests/test_cr175_clerk_ach_return.py` 28 cases, green on PostgreSQL 16 and SQLite; red first (26 failing before the build), and five guards mutated off one at a time went red (tender ×3, double return, runbook read). Neighbours on PG: 220 passed; the reds seen are dated in the lane report. Frontend `markReturned.dom.test.tsx` 6 cases (2 go red with the tender and role guards removed); `tsc` clean and proved able to fail. Browser at 1440 against the local API only (every request to 127.0.0.1): photos in the coordinator's `po-shots/ach-return-clerk/` — the action, the dialog, the reversing payment with *Bank code R01*, the original now *Already returned*, and an account's balance **$184.07 → $284.07**.

**Version 2.561.0** · rollback: redeploy 2.560.3; no migration; reversing rows written stay (hard rule 4).
