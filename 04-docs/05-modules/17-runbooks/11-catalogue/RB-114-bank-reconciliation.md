# RB-114 — Runbook 14 · Bank reconciliation

## What it declares

| | |
|---|---|
| **Kind** | Action |
| **Category** (one home, from the fixed list of sixteen) | Finance |
| **Tags** | Payments |
| **Phase** | 2c |
| **Trigger** | ⚡ `batch.landed` — statement landed (specification B2b). The card's own `Runs` parameter reads *Daily 07:00*; see the note below. |
| **Subject and unit of work** | Bank line |
| **Step modes** | set (match) · per record |
| **Result blocks it composes** | KPIs · Records · Downloads |
| **Ports it holds** | `record_match` (payments) |
| **Proves** | US-RBS-026 |
| **Waits on** | RB-022 (statement lines landed) |

## What it does

Does: matches yesterday's bank statement lines to our deposit batches, records the matches inside tolerance, and lists the lines it cannot place with their likeliest cause. Scope is the statement lines the bank connection landed overnight.

## Scope — how the set is decided

| Row | Value | Control |
|---|---|---|
| Statement lines | Landed overnight | read-only, Settings-owned (dashed) |
| Bank account | Operating | dropdown |
| Statement date | Yesterday | dropdown |
| Never include | Already matched | read-only, Settings-owned (dashed) |

The scope function also answers the count on the screen: **Matches 18 lines today.**

## Parameters

A parameter marked **Settings** is read-only here: policy lives in Settings and is never duplicated on a card (`RBR-03`, `RB-021`). Money is stored to 4 decimals and shown to 2; percentages are stored to 6 and shown to 2; rates carry 4 decimals.

| Parameter | Value on the card | Control | Read-only because it lives in Settings |
|---|---|---|---|
| Auto-match tolerance | From Settings · $0.00 | read-only, Settings-owned (dashed) | **Settings** |
| Date window | ± 2 days | input | — |
| Match on | Amount, then batch reference | dropdown | — |
| Record matches automatically | on | toggle | — |
| Runs | Daily 07:00 | dropdown | — |

## Steps

Source heading: **Steps 6 · four read, two write**. Steps run in the order shown.

| # | Step | What it does | Mode |
|---|---|---|---|
| 1 | Gather statement lines | From the bank connection; this only reads them | `read` |
| 2 | Gather open deposit batches | Ours, not yet matched | `read` |
| 3 | Match by amount and reference | Inside tolerance and the date window | `read` |
| 4 | Separate fees and adjustments | A bank charge is not an unmatched deposit | `read` |
| 5 | Record the matches | Through the payments service · one per line | `writes` |
| 6 | Raise the rest as work items | With the nearest batch and the difference | `writes` |

## Guards — what it may never touch

- The matches are recorded **through the payments service**, through the `record_match` port; the runbook writes no payments row of its own.
- **Never include: Already matched.**
- **Auto-match tolerance is $0.00, and it comes from Settings.**
- A bank charge is separated from the unmatched deposits — it is not a mismatch, it is the bank being paid.

## Produces

15 matched · 3 unmatched, $1,910.00 — each unmatched line beside its nearest batch and the difference between them.

### The run, with the source's own figures

**4 Sep · Operating — "15 matched. 3 need you."**

- Tiles: **15** Matched · **$6,410.55** Matched value · **3** Unmatched · **$1,910.00** Unmatched value · **1** Bank fee · $12.00.
- Table — Bank line · Bank amount · Nearest batch · Batch amount · Difference · Likely cause · Fix: 4 Sep · DEP 0917 · $1,240.00 · Lockbox 3 Sep · $1,204.05 · $35.95 · Bank added a late item · Split and match →; 4 Sep · DEP 0918 · $610.00 · — · — · $610.00 · No batch — a direct deposit? · Record deposit →; 3 Sep · DEP 0902 · $60.00 · Kiosk 3 Sep · $120.00 · −$60.00 · Half of a kiosk batch · Investigate →.
- Nearest batch and Batch amount read — where no batch exists.
- Actions: ↓ Matched · ↓ Unmatched.

Every figure above is an **illustrative fixture**, not a finance-signed number — but the tables on the screens add up to them, so moving one is still an error.

**Done looks like** (the commitment's own sentence, RB-114, status UNVERIFIED): Tom sees "15 matched · 3 need you · $1,910.00 unmatched", each unmatched line beside its nearest batch and the difference, and the bank fee as a tile.

## Its screens

| | Wireframe | Build sheet | Route | Code in the source document |
|---|---|---|---|---|
| Setup | `RBS-004-R14.png` | `RBS-004-R14.md` | `…/runbooks/bank-reconciliation` | `S150-R14`, figure 25 |
| Result | `RBS-006-R14.png` | `RBS-006-R14.md` | `…/runbooks/bank-reconciliation/runs/latest` | `S152-R14`, figure 26 |

They live in `04-docs/05-modules/17-runbooks/wireframes/`. **The build sheet beside each frame is the acceptance check**: the built screen must show exactly those regions in that order with that copy, at those sizes, in those states. A region missing, a control added, a word changed or a size off is a defect of kind *Screen, copy or layout*, filed with the screen code and the region number. A sheet and its frame cannot disagree — one is derived from the other; if one is wrong, both are, and the frame is the thing to fix.

> The source document numbers these screens `S150-R14` and `S152-R14`. This repository numbers them `RBS-004-R14` and `RBS-006-R14` (PO ruling 2026-09-06: *"Screens S147–S154 - this should be RBS-nnn"*). Nothing in the source documents is renamed; the codes above are how the two meet.

## Why the card reads this way

Runbook 10's twin, one step further from the customer. Cash application matches payments to accounts; this matches the bank to our batches. Done weekly by hand today, and it is why month-end reports three unmatched lines — this run is what makes that list empty before the month ends.

## Design notes on the result

Nearest batch and difference are the two columns that turn an hour of squinting into a decision: a $35.95 gap against a lockbox batch is almost always a late item, and the row says so. The fee is a tile, not a row, because it is not a mismatch — it is the bank being paid.

## Open questions and stated absences

- **A trigger disagreement between the two source documents.** The specification's coverage table gives this runbook *⚡ Statement landed*; the card's `Runs` parameter reads *Daily 07:00*. Both are recorded here; neither has been reconciled by a ruling. **Settled in the build by the Product Owner's ruling of 6 September 2026:** a person imports the statement, so the built runbook declares **manual and schedule**.
- **An assumption the source relies on and never states:** a lockbox, bank statement, GIS parcel and AMI head-end connection each exist and land batches. All four are the integration substrate's to build (`CR-069`). **This is no longer a precondition** — the same ruling makes *no connection* a designed outcome rather than a blocker.

---

## BUILT — `CR-075` wave P, 6 September 2026 (`US-RBS-026`)

`06-backend/apps/runbooks/definitions/bank_reconciliation.py`. Six steps, and the sixth writes nothing.

**What it does today, in one sentence:** it reads the statement a person imported, keeps the lines `payments` already tied, offers every line it cannot place **beside the batch it is nearest to and the difference between them**, separates the bank's own charges onto a tile, and **records nothing**.

### ⚠ THE KIND IS A JUDGMENT, AND IT IS THE FIRST THING TO CHECK IF SOMETHING HERE LOOKS WRONG

The lane's briefing described runbook 14 as a **Check** — *"it produces a tie-out; do not give it a writer"*. **Four places in this repository say Action:** this card's own *Kind* and *Ports it holds* rows, `12-the-contract.md` §8's coverage table, `boundary.py` (*"`record_match` is drawn on runbook 14"*), and `10-execution-plan.md` §1.1, which verified card by card on 6 September 2026 that all four phase-3 runbooks read *Kind: Action* — and moved the entire acting half into the foundation because of it.

**The card is the acceptance check, so the card won.** It is **one line to reverse** (`kind=` and `ports=`), a test pins the decision so a silent flip goes red, and nothing is written either way while `record_match` has no writer bound. If the briefing was right, this is a cheap correction; it is written down so that it can be one.

**What the port is actually for**, which is not obvious: `import_bank_statement` already auto-matches on import and is deliberately strict — *one-to-one and unambiguous or nothing*, inside the tenant's own tolerance. This runbook's date window is a PARAMETER and can be wider, so it finds pairings the strict rule left alone; where exactly one candidate ties exactly, it plans a match and a second person approves it.

| The card says | What is built | Why |
|---|---|---|
| Trigger ⚡ `batch.landed` | **manual · schedule** | A person imports the statement (PO ruling 6 Sep 2026) |
| Step 6 *Raise the rest as work items* — `writes` | A **read** step | Raising a work item is an ENGINE act (`BR-RBS-022`); `raise_work_item` is refused BY NAME as a port. ⚠ **And the engine's upsert is wave `C`'s and is NOT BUILT**, so today those findings reach a person on this screen and nowhere else |
| Tile *1 — Bank fee · $12.00* | Value **1**, label **Bank fee**, detail the money | A money amount typed into a LABEL is a string: it loses its `CHAR(3)` currency and its two-decimal rule (hard rule 2). `KpiTile` has a `detail` slot for exactly this |
| Tiles read **Matched** | **To record** while nothing is recorded | Same reason as runbook 10's *To apply* |
| Three regions, no chain | A **chain** is drawn **only when the run stopped** | The frame draws a run that finished |

### Step 1 can STOP the run, and that is a result

Two doors — an accounting connection, and a statement somebody imported. Both shut and the run closes **stopped**: *Nothing to reconcile.* on one red cell, *Never reached* on the other five, and a sentence saying what to do. No KPI strip, for runbook 10's reason.

### Nothing is recorded

`record_match` is money-bearing, so every run needs a second person with **no threshold** (`BR-RBS-018`, CONFIRMED 6 Sep 2026), and no writer is bound until task `L2`.

### ⚖ The judgments this lane made where the documents did not settle it

1. **Kind: Action**, per the card and against the briefing — the first item above, and the one most worth reversing if it is wrong.
2. **What a fee IS.** The card asserts *"a bank charge is not an unmatched deposit"* and defines nothing under it. **This lane's rule: a line whose amount is NEGATIVE is money leaving and is a fee or adjustment; and a line already explained under `bank_fee` or `processor_fee` is one too, whatever its sign.** Both go to the tile, neither to the unmatched table.
3. **Nearest means money first, then days.** A bank posts a batch on the day it feels like and never changes the amount, so the amount is the stronger signal. Ties break on the smaller date gap, then on the batch code, so two runs over the same data agree.
4. **A batch outside the date window is not offered at all.** A batch a fortnight away with the right amount is a coincidence, not a candidate.
5. **A batch two lines could claim is left for a person** — `auto_match`'s own rule, applied to this runbook's wider window rather than reinvented with a different answer.
6. **The likely-cause sentences.** The frame gives three examples, not a vocabulary. The rules under them: **more at the bank than in the batch → the bank added a late item; less → the deposit was split or is short; no candidate at all → not ours.** Each ends in a hedge or a question where it is a guess, because it is.
7. **The statement is a declared INPUT, and falls back to the most recent import** when a person starts the run with nothing chosen.

### Proved by

`06-backend/tests/test_us_rbs_026_bank_reconciliation.py` and `06-backend/tests/test_rbs_money_runbooks_pg.py`. The browser walkthrough is `10-scripts/render-checks/rbs-p-money-runbooks.mjs`, which opens this runbook's stopped run in a real browser and reads six chain cells — one red, five *Never reached*.

**`DEF-RBS-4329` applies here too**: every *Fix* link on `RBS-006` resolves against the run's own address and opens *"This screen is not built yet."* It predates both of these runbooks and breaks the same column on runbook 1.

---

Source: the Runbooks definitions document (*Twenty-One Runbooks*, restructured 5 September 2026; build sheets added 6 September 2026) and the Runbooks specification, section B2b. Every figure in the sections above the build note is the source's own; nothing has been added, and where the source is silent this file says so. Status of **RB-114: BUILT, VERIFIED-UNRATIFIED** — the runbook exists, its rules are asserted by tests that were first shown failing, and no human has signed it off.
