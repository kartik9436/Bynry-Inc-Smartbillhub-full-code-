# J19 — Month-end close (checklist WARN+CONFIRM → close → late event auto-forwards → gated idempotent export)

---
id: J19
tier: 2
rules: [BR-LED-006, BR-LED-018, BR-LED-017, BR-LED-004, BR-LED-005, BR-LED-001, BR-TEN-038, BR-PAY-004, BR-AUD-018, BR-REP-001]
stories: [US-LED-008, US-LED-014, US-LED-015, US-LED-016, US-PAY-023, US-TEN-006]
# journey→story wiring sweep pending: story frontmatter `journeys:` updated in a later sweep (00-e2e-design.md §6)
---

**Intent.** July's books, put to bed properly: the close checklist WARNS and lets Finance confirm-with-reason (never a silent close, never a hard lockout — BR-LED-018), the locked period defends itself by AUTO-FORWARDING a late-dated payment (LE-9), and the ERP export is double-gated — the covered period must be CLOSED (BR-LED-017) and the batch is idempotent (LE-5). The ERP never receives numbers that can still move.

**Fixture.** Tenant brazos-bend · closing **July 2026** on **Aug 5** · fixture-month trial balance = the LE-1 book (totals **598.69 / 598.69**) · checklist state: runs issued ✓, deposit batches reconciled ✓ (locked per BR-PAY-004), bank rec current ✓, accruals posted ✓, remittance recorded ✗ (the WARN item) · export target QuickBooks, batch **EXP-2607-QBO**, 8 GL summary rows.

**Fixture amendments (2026-08-22, CR-014 / DEF-557 / DEF-558).** *Reconciled ✓* is now real: OQ-219 CLOSED 2026-08-16 (PO: reconciled), so the seeder posts DEP-0731's reconciliation and the month renders realised cash **442.87** / undeposited **0.00**. *Accruals posted ✓* is satisfied per OQ-218's ruling (option a — no July accrual; LE-4 stays in September and the Aug-1 reversal epilogue is asserted from there). ⚠ **THE FIXTURE MONTH MOVES WHEN — AND ONLY WHEN — JULY IS ALREADY TAKEN (OQ-333 CLOSED 2026-08-22, PO verbatim: _"Chang the month if required"_).** On a DEMO-seeded stack the sample slice posts 47 invoice JEs dated Jul 2 into this same July (DEF-558), so the seeder now posts the LE-1 book **three months forward — October 2026, opening cutover Sep 30** — and closes THAT month instead. **No figure moves with it:** the book still foots **598.69 / 598.69**, the closed month still foots **553.69**, and the seeder REFUSES rather than report success if either changes. On a stack whose July is empty this journey keeps the July it states — the move is a repair for the collision, not a re-dating. Read the month off the seeder's own `fixture month ...` line; every date in the step table below shifts with it (close on the 5th of the following month, the late-dated payment on its 30th, the export batch id following the closed month).

| # | Date · action | Handoff contract (what this step leaves) | Downstream assertions (bill · ledger · reports · queue · audit) | Rule |
|---|---|---|---|---|
| 1 | **Aug 5** — Finance opens the close: checklist lists the incomplete item ("remittance recorded" ✗) → **WARN + CONFIRM**: Finance closes anyway WITH REASON (audited) | July period **CLOSED**; lock active; reason + incomplete-item snapshot recorded on the close | Trial balance at close: debits = credits (**598.69 = 598.69**, LE-1); close event audited with the confirm reason; no silent close occurred | **BR-LED-018** · BR-LED-006 |
| 2 | **Aug 7** — a payment arrives DATED **Jul 30** | **Auto-posts into August** with the audit note "period closed; auto-forwarded" — books stay locked, nothing silently lands in July (LE-9) | July TB byte-identical to step 1; August carries the payment; posting-basis reports label the basis (BR-REP-001); audit note present | **BR-TEN-038** · BR-LED-006 |
| 3 | **Aug 8** — export attempt for **AUGUST** (still open) | **REFUSED** — export requires the covered period CLOSED (the L-3b gate); refusal writes a security-event attempt row, nothing else | No batch created; attempt row in audit_log | **BR-LED-017** · BR-AUD-018 |
| 4 | **Aug 8** — export **JULY** to QBO: granularity chosen per export (summary default; weekly-over-the-closed-period also legal) → batch **EXP-2607-QBO**: one summary JE, 8 GL rows from July's period deltas, each carrying its qbo_ref from the mapping page | Export batch recorded (who/when/hash); files per IS-11 | Every exported figure DRILLS BACK to dimensioned journal lines — "what is the 506.31?" lists them (LE-5, BR-LED-001); audit | **BR-LED-004** · BR-LED-017 |
| 5 | **Aug 9** — July export re-run | **BLOCKED** with link to the existing EXP-2607-QBO batch — idempotent, no double-handover (LE-5) | Exactly one July batch exists, forever; attempt audited | BR-LED-004 |
| 6 | **Aug 12** — epilogue: July's accrual-type JE auto-reversed on Aug 1 (mirror linked both ways, LE-4 pattern) and the remittance gets recorded in August with its filing confirmation ref | Accrual pair linked; remittance JE drains the authority liability with confirmation ref + receipt attachment (BR-LED-019) | Remittance report dual-basis columns per authority (LE-3); August books normal; audit | BR-LED-005 · BR-LED-002 |
| 7 | **INVARIANCE** — July is byte-frozen from step 1 forward: no row entered or left the closed period (the Jul 30 payment lives in August); reopen exists only as an explicit SysAdmin act (not exercised here); the export file re-generated from the batch is identical (hash-stable) | — | Closed-period lock held through every probe; append-only books; every gate refusal attempt-audited (BR-AUD-018); tie-outs hold (BR-LED-007) | BR-LED-006 · hard rule 4 |

---

## What a browser can actually drive, as of 2026-08-15 (DEF-112 closed)

This journey went RED AT STEP 1 on 2026-08-15 — *not on a wrong figure, on the
absence of anything to click*. `close_checklist`, `close_period`,
`reopen_period` and the export batch with its four gates were all built,
unit-tested and correct, and no screen or endpoint reached one of them. That is
fixed. **The steps below now name the exact control a journey drives**, so the
next run asserts against the product rather than against a plan.

| # | Where | The control | What the server does |
|---|---|---|---|
| 1 | Finance → **Export to accounting** | *Before you close* lists BR-LED-006's five items with a state each; **Close this month** opens a form taking a closing DATE and a REASON | `GET /finance/close-checklist` then `POST /finance/periods/close`. Without a reason over an incomplete list: **422 `BIZ-APPROVAL`** naming every incomplete item — that is the WARN, and the same request with a reason succeeds |
| 2 | — | (no screen — a late-dated event arrives through billing or payments) | `apps.ledger.close.resolve_entry_date`. ⚠ **Only the manual JE calls it today**; a late-dated BILL or PAYMENT still lands where it was dated, which is US-LED-015 §8's own flagged residue and is NOT a screen gap |
| 3 | Finance → Export to accounting | **Hand this month over** is DISABLED while the period is open, and the reason is written above it | `GET /finance/export/preview` → `sendable: false`, `period_closed: false`. Forcing the POST: **409 `BIZ-LOCKED`**, BR-LED-017 |
| 4 | Finance → Export to accounting → **Export** | pick a destination, then **Hand this month over** → an IS-6 confirm dialog naming entries, both totals, the destination and the window; then **Download again** on the hand-over history | `POST /finance/export/batches` → **201**, batch recorded with its content hash. Then `GET /finance/export/batches/{id}/file` → the bytes, re-derived from the FROZEN payload (`P4.2`/`P4.8`) |
| 5 | Finance → Export to accounting | the same button again | **409 `BIZ-IDEMPOTENT`**, and the existing batch rides on `params` so the screen can point at it (T5-07: re-DOWNLOAD, never re-export) |
| 6 | Finance → **Taxes & Remittance** | **Record a payment** on the authority's row → amount, basis, confirmation reference, date | `POST /finance/taxes/remittances` → one balanced entry, DR 2200-nn / CR cash |
| 7 | Finance → **General ledger** | the trial balance and its footer, before and after | `GET /ledger/trial-balance`. The footer is the SERVER's `balanced`; the screen computes nothing. ⚠ **AND EVERY ENTRY IN THE JOURNAL BESIDE IT NOW CARRIES A `JE-` NUMBER** — the assertion below |

**ONE ASSERTION ADDED 2026-09-24 (`P0.11`), AND DELIBERATELY NO NEW JOURNEY.**
`P0.3` makes `apps.ledger.posting.post()` allocate `BR-LED-021`'s `JE-` number,
so every entry this journey posts — the LE-1 month behind step 1, the
remittance at step 6 — now carries one. **Step 7 asserts it:**

> every row `GET /ledger/journal-entries` returns for the closed period has a
> non-null `je_number`, and every one begins `JE-`.

**Why this is one line and not a journey of its own**, written down so the
absence is a decision rather than an oversight: a journey exists to prove a
PERSON can get from one end of a task to the other. Numbering changes nothing a
person does — no screen, no click, no new decision — it changes what is written
on rows they were already looking at. **A new journey here would be a test with
no user in it**, and `P0.11`'s own row says so: *"stated honestly: no new
journey is needed for a stamping change"*.

**What this catches that the unit tests do not.** They post through
`posting.post()` directly. This step reaches the entries the way a clerk does —
through `GET /ledger/journal-entries`, after a real close — so it goes red if
the number is allocated but never SERVED. That is the wiring half, and
hard-won law 2 is that built is not wired.

⚠ **ONE ROW MAY LAWFULLY COME BACK WITH A NULL NUMBER, AND THE ASSERTION MUST
NOT BE RELAXED TO HIDE IT.** A tenant with no `journal_entry` row in
`number_series` posts unnumbered FOR EVER (hard rule 4 freezes `number` at
post), and the list reports that by name in `unavailable` as
`posted_entries_without_a_je_number`. **On this fixture it cannot happen** —
`seed_demo` seeds every catalogued series — so a null here is a real failure.
If the fixture ever changes, assert the `unavailable` code; do not weaken the
assertion.

**THE FIXTURE THIS JOURNEY NEEDS, written down rather than assumed (DEF-110).**
`seed_e2e_fixture.py` seeds ONE bill dated **30 June**, so a July window answers
**0 rows, 0.000000 = 0.000000** at every step above. The screens are built to
make that visible rather than green — the trial balance says *"No posted entries
fall in this period. This is an empty book, not a balanced one."* and the export
summary says *"This period has nothing to hand over. An empty month is not a
finished one."* — but a journey run over that fixture still proves only that the
buttons exist. What it needs, in the order the steps use it:

1. **A July book that foots** — the LE-1 month posted through the real posting
   service (`tests/ledger_le_fixtures.post_le1_month` is the shape), so step 1
   and step 7 read **553.69 = 553.69** on the windowed trial balance rather
   than zero. (LE-1's whole-book **598.69** includes an opening entry dated
   before July; both figures are LE-1 and the difference is the window.)
2. **A tax liability on a 2200-nn account** — LE-3's four authorities
   (`ensure_authority_accounts` + `post_le3_authorities`), or step 6 has no row
   to record against and the *remittance recorded* checklist item reports
   `complete` because nothing is owed.
3. **Export codes on the GL accounts for the chosen target** — without a
   `qbo_ref`/`xero_ref` the step-4 send is refused **422 `BIZ-COMPLETENESS`**
   naming the account. **CSV and IIF address accounts by code+name and need no
   codes**, which is the cheapest target for a first green run.
4. **Fiscal settings on the tenant** — `apps.tenancy.selectors.current_period`
   must answer, or every screen here says the period is not configured and
   refuses to guess a calendar month (BR-TEN-022).

Extending the fixture is DEF-110's lane, not this one. Nothing above is assumed
present; each screen states the absence it meets.

---

## ⚠ REGRESSION, 2026-09-23 — THE BATCHING RULE CHANGED UNDERNEATH THIS JOURNEY

`CR-136-BRC07` `P2.19`, LANE P2-TESTS. **This section adds no step and moves no
figure.** It records what `CR-135-BRC07` `P0.6` did to step 1's checklist on
2026-09-22, because this journey's *deposit batches reconciled ✓* item is
counted from a register whose shape moved and **nothing here said so**.

**WHAT MOVED, IN ONE SENTENCE.** A deposit batch stopped being *one day × one
tender for the whole utility* and became **one counter session × one tender**
(`payments/0033`, PO ruling 2026-09-22 — at a two-counter office Dana's
**$1,240** of cheques and Sam's **$880** were one row neither clerk could be
held to; the day still ties to **$2,120** and is now two deposits).

**WHY THAT REACHES THIS JOURNEY.** Step 1's checklist item is
`apps.payments.selectors.unreconciled_batch_count(start, end)`, and it counts
**BATCHES** — every one of the window's batches that is not `reconciled`. So the
number of things standing between Finance and a closed month is no longer
*tenders × drawer days*; it is **tills × tenders × drawer days**. Three clerks at
three windows taking cash and cheques leave **six** batches for a day that used
to leave two, and each one has to be matched to the bank on its own.

**AND A COUNTED CLOSE DOES NOT RECONCILE ANYTHING.** Closing a till seals its
batches at their totals and leaves them **`in_transit`** — measured, by
`10-scripts/cr136_p2_17_counter_shift_readback.py`: a clean shift with a
**$0.00** difference produced `DEP-260923-0021` cash **$510.00** and
`DEP-260923-0022` cheque **$1,284.60**, both `in_transit`, both counting against
this checklist. **A balanced drawer is not a reconciled deposit**, and a lane
reading only `J-PAY-counter-shift` could easily assume otherwise.

**MEASURED ON A MIGRATED PostgreSQL 16.13 CLONE, 2026-09-23.** The old key is no
longer unique in the data: **two `(day, tender)` combinations carried more than
one batch, the largest carrying 19**. Any check, report or fixture that still
assumes *one batch per day per tender* is reading a rule that was superseded.

**WHAT THIS JOURNEY'S OWN FIXTURE MUST DO ABOUT IT.** The fixture amendment of
2026-08-22 says *"the seeder posts DEP-0731's reconciliation"* — **singular**, a
sentence written when a drawer day was one batch. On a stack where any counter
shift has happened in the window, reconciling one batch no longer clears the
item, and step 1 then reports a SECOND incomplete item where this journey
expects exactly one (*remittance recorded* ✗). **That would read as a broken
WARN+CONFIRM and is not**: it is this journey meeting the new rule. Whoever next
runs J19 on a counter-bearing fixture should reconcile **every** batch in the
window or expect the extra item, and say which they did.

⚠ **NOTHING ABOVE IS ASSERTED AS A NEW STEP, DELIBERATELY.** `P2.19` is a
regression note, not a rewrite: the seven steps, the **598.69 / 598.69** book and
the **553.69** closed month are untouched, and changing a signed figure is a
finance re-sign (HUMAN-GUIDE §6), never an inline edit.

---


## `P4.8`, 2026-09-24 — STEP 4 GAINS THE FILE, AND THE VIEW IT LIVES ON MOVED

**The step-4 row above has said *"files per IS-11"* since this journey was
written, and until today the second half was a plan.** `apps/ledger/exports.py`
said *"No file is written and nothing is sent"* and the hand-over history drew
**Not written** in its File column. `P4.2` writes the bytes; `P4.8` is the
assertion that they reach a person.

**What step 4 asserts now, in addition to everything it already did:**

> the hand-over history offers **Download again**, and following it produces a
> file with a NAME and a length greater than zero.

⚠ **IT ASSERTS THE BYTES, NOT THE BUTTON — and that is the point rather than
thoroughness.** A control that starts a download and produces nothing passes
every check that stops at the click, and this journey's own sweep already
counts OPERABLE controls apart from merely matching ones for exactly that
reason (*"a button onto nothing must not be read as a path"*). So the download
is awaited, saved and READ.

⚠ **AND THE HAND-OVER MOVED TO A VIEW OF ITS OWN (`P4.12`).** Tab 6 is two
screens now — **Close** and **Export** — and the history, the preview and the
send are on the second. The spec walks to `?view=export` rather than assuming
the tab's landing view still carries them: a step that opened the right TAB and
the wrong VIEW would report *"no download control"* over one that is three
pixels away, which is `DEF-REP-6649`'s neighbouring shape and is how a true
failure acquires the colouring of a missing feature.

⚠ **STEP 5 IS UNCHANGED AND IS WHY THIS ONE MATTERS.** T5-07's recovery path is
*re-DOWNLOAD, never re-export*, and until today the first half of that sentence
pointed at nothing. A journey that proved the second export is refused, without
proving the first one can be fetched again, was describing a dead end.


## `P3.7`, 2026-09-24 — STEP 8: REOPEN THE MONTH, AND THE TRIAL BALANCE DOES NOT MOVE

Finance blueprint `P3.7`, LANE FIN-P3. Finance blueprint p016, verbatim: *"Extend
with reopen: close July, reopen it, confirm the trial balance is byte-identical
before and after."* OUTCOME: *"Reopen is proved not to move a figure."*

**THIS ADDS ONE STEP AND MOVES NO FIGURE.** The seven steps, the **598.69 /
598.69** book and the **553.69** closed month are untouched — changing a signed
figure is a finance re-sign (HUMAN-GUIDE §6), never an inline edit.

### WHY THE STEP IS WORTH HAVING, AND WHAT IT ACTUALLY CATCHES

Until `P3.2` a period closed in error was reopened **from a shell**:
`POST /finance/periods/reopen` and its typed client wrapper had both existed
since 2026-08-16 and **no component called either** (the blueprint's own p073
GAP box). So the act had no user, and a journey step for it could not be
written.

What this step catches is the thing the endpoint's unit tests cannot: **a reopen
that quietly changes a number.** `close.reopen_period` writes four columns on
one `fiscal_period_closes` row and touches no journal entry — but *nothing said
so from the outside*, and the trial balance is derived from the entries rather
than from the close, so the assertion is cheap and the guarantee is not.

### THE STEP

| | |
|---|---|
| **8a** | Take the windowed trial balance for the CLOSED month and keep the response body — `GET /reports/trial-balance?from=&to=`, which is what screen 1·2 renders |
| **8b** | As a **System Admin**, open **Close & export**, find the month under *Months already closed*, press `↺` and reopen it with a reason. BR-LED-006 as amended by the PO on 2026-09-24: closing is `system_admin` + `billing_clerk`, **reopening is `system_admin` only**, reason required, audited |
| **8c** | Take the same trial balance again. **It must be byte-identical** — not *equal to two decimals*, and not *both balanced*. `P3.7`'s word is "byte-identical" and it is the right one: a derived report that re-rounds, re-orders or drops a null between two reads is a real difference and an "equal" assertion hides it |
| **8d** | The period reads **open** again, and `fiscal_period_closes` keeps its `closed_at` AND gains `reopened_at`, `reopened_by_user_id` and `reopen_reason`. The close is not deleted — the history of a month that was shut and reopened is two facts, not one |
| **8e** | **A handover already sent is NOT recalled** (BR-LED-017). If the month was exported, 6·1b says so before the act — *"Handed over {date}. That handover stands. Post the difference."* — and after the reopen the export batch is still there, unchanged |

### ⚠ WHAT A BILLING CLERK MUST MEET, AND WHY IT IS PART OF THE STEP

Signed in as a **Billing Clerk**, the `↺` is drawn **DISABLED with its reason**
(`BR-SHL-025`), and `POST /finance/periods/reopen` refuses the same request with
**403**. Both halves are the step: a screen that merely hid the control would
pass a happy-path walk while leaving the endpoint open, and an endpoint that
refused while the screen offered a live button would teach the clerk the product
is broken.

### WHAT IS NOT PROVED HERE, STATED RATHER THAN IMPLIED

**That a reopened month can then be closed AGAIN.** `close_period` refuses a
period that is not open and this step leaves the month open, so re-closing it is
a second act with its own checklist — and on this fixture the checklist is the
one step 1 already walks. Worth adding when somebody has a reason to; not
smuggled in here as though it had been proved.
