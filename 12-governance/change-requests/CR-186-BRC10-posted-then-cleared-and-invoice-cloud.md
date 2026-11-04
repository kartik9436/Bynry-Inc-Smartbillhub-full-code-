# CR-186-BRC10 · Every payment POSTED at entry, CLEARED at bank reconciliation; one batch per till or provider per day; Invoice Cloud real-time balance

**Raised:** 2026-10-21 by the Product Owner, in chat, from Invoice Cloud's two Partner API asks: real-time balance on `consumer-info`, and immediate posting on `make-payment`.

**Requester's words (verbatim):** *"whether invoice cloud, or any other payment provider, or counter, or lockbox or any payment method - first they will pot the payment - so we crete the record and add posting date; then later money is recieved in the bank account ; uitlity will reconcile it bank statement that time it is cleared with clearing date … if payment is cancled then it will not be considered; reconciled ayment cannot be cancelled; cleared payment cannot be cancled ; in those cases refunds or credits will be issued; you will ahve to take refunds or credits into account while calcualting opening balance; we need to do what is correct"*.

**Rulings:** decision log 2026-10-21, seven entries:
- *"INVOICE CLOUD REAL-TIME BALANCE AND IMMEDIATE POSTING: FOUR RULINGS, AND 'CLEARED' REDEFINED PRODUCT-WIDE"*
- *"THE PAYMENT LIFECYCLE, STATED BY THE PO FOR EVERY METHOD"*
- *"NO 'RECONCILED' PAYMENT STATUS"*
- *"PAYMENT APPLICATION AND ITS ACCOUNTING ENTRY … CONFIRMED UNCHANGED"*
- *"DEPOSIT BATCHES: ONE BATCH ID PER TILL OR PER PROVIDER, PER DAY"*
- *"EXISTING `cleared` PAYMENTS ARE LEFT AS THEY ARE"*

## 1 · Classification

A **change**. It reverses signed rules: BR-PAY-021's clearing definition, BR-PAY-025 as amended 2026-09-22 (*"one till and one tender"*), and `OQ-PAY-12627`'s premise. It also adds a hard-rule-4 narrowing: `posted` → `cleared` only, only through bank reconciliation.

## 2 · Before → after

| Before | After |
|---|---|
| Card / cash / transfer payments saved `cleared` at entry; cheques and Invoice Cloud saved `processing` | Every method saved **`posted`** at entry |
| Applied to bills, and journal written, only when `cleared` | **Applied and journalled at posting.** Entry dated the posting date, forwarded to the first open period if closed |
| Batch = till × tender; non-counter money in one shared SYSTEM till; batch stamped at the nightly cut | **One batch per till, or per provider/channel, per day, all tenders**, stamped at posting, with a total per tender |
| Bank reconciliation changes the batch only | Reconciliation also moves every member payment **`posted` → `cleared`** with the clearing date (the one hard-rule-4 exception) |
| Cancel only from `processing` | Cancel only from **`posted`**; `cleared` is refused, and a refund or credit corrects it instead |
| Balance excludes only `processing` and deposits (so `cancelled` and `failed` wrongly count) | Balance counts **`posted` + `cleared`** (reversing rows negative), never `cancelled` / `failed` / `processing`, plus refunds and credits |
| Invoice Cloud reply `processing` plus a "not cleared" note | Reply **`posted`** with the payment number and batch ID; that note removed |

## 3 · Tasks

| # | Task | Lane |
|---|---|---|
| T1 | This CR, its reservation row, and the business-rule fan-out (BR-PAY-021, BR-PAY-025, cancel, balance, Invoice Cloud rules) | Coordinator + lanes |
| T2 | Defect for `cancelled` / `failed` counted in the balance, proved by a test before the fix | Lane PAY-CORE |
| T5–T8 | Posted at entry for every path; batch per till/provider/day at posting; nightly cut picks up stragglers; closed-period forward | Lane PAY-CORE |
| T9–T13 | Trigger exception `posted` → `cleared` only; reconciliation clears its members; un-reconcile handling; cancel only from `posted`; reversals from `posted` / `cleared` | Lane PAY-CORE |
| T14–T18 | One balance formula, every reader, adjustments verified; Invoice Cloud make-payment `posted` plus batch ID; partner replies | Lane BAL-IC |
| T19–T21 | Screens: labels, filters, "Shown on bill", 11 catalogues | Both, by screen |
| T22 | No data correction (PO: sandbox only) | — |
| T23–T26 | Tests, PostgreSQL, combined walk, release | Both, then coordinator |

## 4 · Status

**RELEASED in 2.589.0 (2026-10-21); follow-ups RELEASED in 2.590.0 (2026-10-21)** — Unreconcile back to Posted (payments/0052) and reports on the posting date, both PO-ruled; `DEF-PAY-10321`, `10323`, `10342`, `10346`, `DEF-CUS-10324`, `DEF-CWP-10341` fixed. (Earlier text follows.) Built by lanes PAY-CORE and BAL-IC and merged by the coordinator. The combined PostgreSQL run is green. Still open: `DEF-PAY-10321` (reports dated by clearing date), `DEF-PAY-10323`, `DEF-CUS-10324`, `DEF-CWP-10341`, `DEF-PAY-10342`. Two PO questions remain (unreconcile; the report date basis).
