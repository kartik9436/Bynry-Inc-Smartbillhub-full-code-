# J-PAY-PUT-IT-RIGHT — four ways one payment goes wrong, and only the first writes in place

---
id: JPAYPUTITRIGHT
tier: 1
rules: [BR-PAY-002, BR-PAY-013, BR-PAY-021, BR-PAY-036, BR-PAY-865, BR-BIL-071, BR-LED-003]
stories: [US-PAY-001, US-PAY-004, US-PAY-009]
---

<!-- `CR-137-BRC07` `P3.20`, authored 2026-09-23 by lane P3-TESTS.

     ⚠ **THE FILE IS NAMED FOR ITS ID, AND THAT IS A RULE RATHER THAN A STYLE.**
     The task board calls this walk `J-PAY-put-it-right`. That string cannot be
     a journey id: `G12`'s `VALID_JOURNEY_ID_RE` is `^[JT][A-Za-z0-9]*(?:-\d+)?$`,
     so a hyphen after `J` fails it, the gate falls back to guessing an id from
     the filename, and a spec can then never be matched to this journey (check
     3, which matches BY FILENAME). `JPAYWRONGACCT` is the precedent — renamed
     on 2026-09-22 for exactly this, as one of the eight `DEF-QAE-6208` names —
     and this file follows it rather than repeating the defect eight days later.

     ⚠ **NOT ACTIVATED. There is no `JPAYPUTITRIGHT.spec.ts`, deliberately.**
     `G12` check 5 fails a spec claiming a journey whose declared stories are
     not all built, and the honest reason here is narrower: **step 1's own act
     is incomplete in the product.** See the ⚠ under step 2 — `payments
     .corrects_payment_id` exists and nothing writes it (`DEF-PAY-6259`). A
     journey first seen green is a journey nobody has proved (hard-won law 7),
     and a walk written against a link that is not made would be one.
-->

**Intent.** One payment, **PMT-2609-000418**, `$158.10` by cheque, taken at the
counter on **21 September**. It goes wrong four separate ways, and the product
answers each with a DIFFERENT act. The point of the walk is not that all four
work — each has its own tests — it is that **they are four and not one**, and
that a clerk meeting the wrong one is told which of the other three to use.

⚠ **THE OUTCOME, AND IT IS THE WHOLE JOURNEY: *four acts, and only the first
writes in place.*** Hard rule 4 freezes issued payments. **`OQ-1322` narrowed it
for three columns and for nothing else** (PO 2026-09-02, verbatim: *"(a) Allow
those fields to change"*) — `confirmation`, `memo`, `method_id`, through the one
named endpoint `POST /payments/{id}/correct-reference`. Steps 2, 3 and 4 each
put something right **by writing a new row**, and the original keeps every
column it had. A walk that cannot tell those apart is how a clerk learns to
reach for Reverse when they meant Cancel.

**Fixture.** Tenant `brazosbend` · account `AC-2026-00001`, Ana Alvarez ·
bill `BL-2609-000085` · payment **PMT-2609-000418**, `$158.10`, cheque, posted
**21 Sep**, taken by Dana Whitfield at the Main counter.

| # | Date · action | Handoff contract (what this step leaves) | Downstream assertions (row · books · screen · audit) | Rule |
|---|---|---|---|---|
| 1 | **21 Sep 11:50 — the cheque number was mistyped.** Dana typed `4417` and the cheque reads `4471`. `POST /payments/{id}/correct-reference` with a **required note** | **The SAME row.** `confirmation` now reads `4471`; `payment_no`, `amount`, `account_id`, both dates, `status` and the allocations are untouched. `updated_at` moves | **THE ONLY IN-PLACE WRITE IN THIS WALK.** Every money field refused BY NAME if sent · the tender refused once the payment is banked (deposit batches group by day AND tender) · an audit row, which is **the only place `4417` now lives** and **is pruned on audit's ordinary retention schedule** — `OQ-1340` CLOSED 2026-09-23, PO: *"keep the same rule s; when audit log is delete - it is deleted thats okay"*. ⚠ **No screen says one word about that** (B14 rule 33: rationale is ZERO words on screen); the response carries `amendment_history_is_not_a_permanent_record` as a MACHINE fact | **hard rule 4, narrowed** · `payments/0014` |
| 2 | **22 Sep — the amount was wrong.** The cheque was `$150.00`, not `$158.10`. A **correction**: the record path with `type=adjustment`, signed `−8.10` | **A NEW ROW.** PMT-2609-000418 is **byte-identical** to what step 1 left — every concrete column compared, not the four a reader would think of. `BL-2609-000085` re-opens at `$8.10` and Ana owes `$8.10` more | The Correction modal says it before anything else: *"This does not change PMT-2609-000418. It writes a new row instead."* · the adjustment carries its own `PMT-` number and appears on S33 as a signed row · ledger balanced pairs (BR-LED-003) · audit on the new row. ⚠ **AND THE LINK BACK IS NOT MADE YET** — `payments.corrects_payment_id` exists (`payments/0037`, `P3.7`) and **nothing in the product writes or reads it** (`DEF-PAY-6259`, hard-won law 2). So today this step leaves two rows a human can pair up and a machine cannot | hard rule 4 (*corrections are new rows*) |
| 3 | **22 Sep — it should never have been taken at all.** Wrong customer. **Cancel**, and only because the cheque has **not cleared** | `processing → cancelled` on the original **plus a negative reversing row of `−158.10` under its own `PMT-` number**. The original keeps its amount for ever | ⚠ **THE STATUS MOVE ALONE WOULD OVERSTATE THE DRAWER** — `selectors.payments_totals` nets by ROWS and reads no status, so the reversing row is what takes `$158.10` out of the day's takings · **no ledger posting is reversed and no allocation is released**, because a processing payment posted nothing — and the result SAYS so in two codes rather than leaving a screen to imply a bill moved (hard rule 5) · the clerk's optional note lands on the reversing row's `memo` · a double-click answers `200 · created:false` (hard rule 6; the STATUS is the key) · the cancelled payment **does not vanish** — the history panel is what makes it honest (`P3.4`) | **BR-PAY-002** · hard rule 5 · hard rule 6 |
| 4 | **28 Sep — the money arrived and went back.** A week later the bank returns the cheque. **Reverse**, dated by the BANK | BR-PAY-013's machine in full: reversing row `−158.10`, allocations reversed, AR reinstated **at the ORIGINAL due date**, NSF charge code auto-added, `nsf_count` incremented | ⚠ **THIS IS THE STEP THAT LOOKS LIKE STEP 3 AND IS NOT.** *"Cancel is for money that never cleared … Reverse is for money that arrived and went back"* (p044). The late-fee clock never reset — lateness reads the day the money actually arrived (**BR-BIL-071**), so a bounce does not forgive a bill that was paid on time and then unpaid · money is ALWAYS accepted afterwards (BR-PAY-036) · `J12-nsf-life` owns the two-bounce chain and the cash-only flag; this step is its first rung | **BR-PAY-013** · BR-PAY-021 · BR-PAY-036 |
| 5 | **THE FORK, ASSERTED IN BOTH DIRECTIONS** — a clerk who reaches for the wrong act is told which one to use | — | Cancel on a **cleared** payment is refused and the refusal **names Reverse** · and **no other refusal does** — Reverse itself requires a cleared row (`US-PAY-009` TC-5), so sending the holder of a `failed`, `reversed` or already-`cancelled` row to Reverse is a second refusal wearing a signpost. **Both halves are `P3.13`** | BR-PAY-021 · BR-SHL-025 |
| 6 | **INVARIANCE** — the original payment row was EDITED exactly once, in three columns, through one named endpoint | — | No `UPDATE` reached `amount`, `account_id`, `posted_at`, `cleared_at` or the allocations at any step · no `DELETE` in any status · `trg_payment_immutable` proved in both directions on **PostgreSQL 16** (`10-scripts/p3_cancel_state_and_trigger_readback.py` §3 · §4 · §6 · §8) — **SQLite has neither the CHECK nor the trigger and the default suite runs there** (hard-won law 14) | **hard rule 4** · BR-PAY-002 |

---

## What a lane building against this walk must not assume

⚠ **STEP 3 AND STEP 4 ARE ONE CONTROL AND THE PRODUCT CHOOSES BY STATUS**, which
is the drawing's own ruling (p044). **A counter CASH payment is `cleared` the
same minute it is taken**, so at a window step 3 is unreachable and the clerk
lands on step 4 for a payment taken ninety seconds ago. That is
**`OQ-PAY-12603`** — put to the PO, **not settled in code**, and a lane that
"fixes" it by widening cancel to cleared payments would be answering an open
question by choosing a value.

⚠ **STEP 1'S NOTE IS REQUIRED AND STEP 3'S IS NOT.** The correction takes a
**required** note (`amend_reference(note=…)`); the cancel takes a **required
reason CODE** (p044 ②, one of four) and an **optional** note. They read alike on
screen and are different obligations — and no ruling makes the cancel's note
required, so a test asserting one would put a rule into the suite that nobody
made.
