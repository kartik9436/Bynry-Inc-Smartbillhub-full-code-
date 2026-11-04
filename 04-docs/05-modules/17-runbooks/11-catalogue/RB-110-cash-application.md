# RB-110 — Runbook 10 · Cash application

## What it declares

| | |
|---|---|
| **Kind** | Action |
| **Category** (one home, from the fixed list of sixteen) | Payments |
| **Tags** | Finance |
| **Phase** | 2c |
| **Trigger** | ⚡ `batch.landed` — payments landed (specification B2b). The card's own `Runs` parameter reads *Daily 06:30*; see the note below. |
| **Subject and unit of work** | Payment · a day's batch |
| **Step modes** | per record |
| **Result blocks it composes** | KPIs · Breakdown · Records · Downloads |
| **Ports it holds** | `apply_payment` (payments) · `queue_receipt` (notifications) |
| **Proves** | US-RBS-022 · US-RBS-017 |
| **Waits on** | RB-022 (the landed-batch event) |

## What it does

Does: takes every payment that landed today — lockbox, bank file, portal, kiosk — finds the account it belongs to, applies it by the allocation order, and lists the ones it could not place. Scope is a day's landed payments; the integration lands them, this decides what they mean.

## Scope — how the set is decided

| Row | Value | Control |
|---|---|---|
| Payments landed | Today | dropdown |
| Sources | Lockbox · Bank file · Portal · Kiosk | dropdown |
| Never include | Already applied · Reversed | read-only, Settings-owned (dashed) |

The scope function also answers the count on the screen: **Matches 138 payments today.**

## Parameters

A parameter marked **Settings** is read-only here: policy lives in Settings and is never duplicated on a card (`RBR-03`, `RB-021`). Money is stored to 4 decimals and shown to 2; percentages are stored to 6 and shown to 2; rates carry 4 decimals.

| Parameter | Value on the card | Control | Read-only because it lives in Settings |
|---|---|---|---|
| Allocation order | From Settings · oldest first | read-only, Settings-owned (dashed) | **Settings** |
| Match on | Account no., then remittance id, then name + amount | dropdown | — |
| Auto-apply exact matches | on | toggle | — |
| Overpayment over | $50.00 | input | — |
| Duplicate window | 3 days | input | — |
| Most per run | 2,000 | input | — |
| Runs | Daily 06:30 | dropdown | — |

## Steps

Source heading: **Steps 7 · five read, two write**. Steps run in the order shown.

| # | Step | What it does | Mode |
|---|---|---|---|
| 1 | Gather today's landed payments | From every connected source, once, pinned | `read` |
| 2 | Match by account number | The clean case — most of the file | `read` |
| 3 | Match by remittance id, then name and amount | For the ones the number does not resolve | `read` |
| 4 | Check for a duplicate | Same account, amount and source inside the window | `read` |
| 5 | Check the amount against the balance | Over- and short-payments flagged, never guessed | `read` |
| 6 | Apply by allocation order | Through the payments service · one per payment | `writes` |
| 7 | Record and queue receipts | Audit row names this runbook; receipt per tenant rule | `writes` |

## Guards — what it may never touch

- **The runbook never writes a payment row.** Posting goes through the payments service, through the `apply_payment` port.
- **Never include: Already applied · Reversed.**
- **A duplicate payment is held, never rejected** (`RBR-14`) — the second payment is real money someone sent.
- Over- and short-payments are flagged, **never guessed**. Likeliest account carries a confidence and a name, never an id: a clerk confirms a guess, the runbook does not make it.

## Produces

Applied, unmatched and held — 129 applied · 6 need a person · 3 duplicates held, each unmatched payment carrying its likeliest account and a Pick account →.

### The run, with the source's own figures

**Today · 06:30 — "129 applied. 6 need you."**

- Tiles: **129** Applied · **$14,210.60** Applied value · **6** Need a person · **3** Duplicates held.
- By source — Source · Landed · Applied · Unmatched: Lockbox 71 · 68 · 3; Bank file 32 · 31 · 1; Portal 28 · 28 · 0; Kiosk 7 · 2 · 2.
- Unmatched · 6, showing 1–3 — Payment · Source · Amount · Likeliest account · Why · Fix: 12 Sep · ref 88213 · Lockbox · $182.40 · Alvarez, M. · 92% · Account no. mistyped · Pick account →; 12 Sep · ref 88240 · Kiosk · $60.00 · Two candidates · Same name, two accounts · Pick account →; 11 Sep · ref 88199 · Lockbox · $1,204.05 · Okonkwo, D. · $1,204.05 over balance · Confirm overpayment →.
- Actions: ↓ Applied · ↓ Unmatched; Pick account → and Confirm overpayment → enabled.

Every figure above is an **illustrative fixture**, not a finance-signed number — but the tables on the screens add up to them, so moving one is still an error.

**Done looks like** (the commitment's own sentence, RB-110, status UNVERIFIED): At 06:30 the clerk sees "129 applied · 6 need you · 3 duplicates held", a by-source table, and each unmatched payment with its likeliest account and Pick account →.

## Its screens

| | Wireframe | Build sheet | Route | Code in the source document |
|---|---|---|---|---|
| Setup | `RBS-004-R10.png` | `RBS-004-R10.md` | `…/runbooks/cash-application` | `S150-R10`, figure 17 |
| Result | `RBS-006-R10.png` | `RBS-006-R10.md` | `…/runbooks/cash-application/runs/latest` | `S152-R10`, figure 18 |

They live in `04-docs/05-modules/17-runbooks/wireframes/`. **The build sheet beside each frame is the acceptance check**: the built screen must show exactly those regions in that order with that copy, at those sizes, in those states. A region missing, a control added, a word changed or a size off is a defect of kind *Screen, copy or layout*, filed with the screen code and the region number. A sheet and its frame cannot disagree — one is derived from the other; if one is wrong, both are, and the frame is the thing to fix.

> The source document numbers these screens `S150-R10` and `S152-R10`. This repository numbers them `RBS-004-R10` and `RBS-006-R10` (PO ruling 2026-09-06: *"Screens S147–S154 - this should be RBS-nnn"*). Nothing in the source documents is renamed; the codes above are how the two meet.

## Why the card reads this way

The two most common things a clerk does are match a payment and explain one. This is the first. Everything here is deterministic; the only judgment is "which account is this", and the runbook narrows it to a likeliest guess a person confirms rather than guessing itself.

## Design notes on the result

Likeliest account carries a confidence and a name, never an id — a clerk confirms a guess, the runbook does not make it. The by-source table is what tells a utility which channel is dirty: here the kiosk mis-keys two of seven. Duplicates are held, not rejected, because the second payment is real money someone sent.

## Open questions and stated absences

- **Cash application never writes a payment row itself.** Already specified as `RB-017` — `apply_payment` is a port into the payments service.
- **A trigger disagreement between the two source documents.** The specification's coverage table (B2b) gives this runbook the event trigger *⚡ Payments landed* and lists it under `batch.landed`; the definitions card's own `Runs` parameter reads *Daily 06:30*. Both are recorded here; neither has been reconciled by a ruling. **Settled in the build by the Product Owner's ruling of 6 September 2026 rather than by reconciling the documents:** a person collects the payments and uploads them, so the built runbook declares **manual and schedule**, and the event joins them the day something emits it.

---

## BUILT — `CR-075` wave P, 6 September 2026 (`US-RBS-022` · `US-RBS-017`)

`06-backend/apps/runbooks/definitions/cash_application.py`. Seven steps, five read and two write, exactly as the card's heading says.

**What it does today, in one sentence:** a clerk uploads a day's payments, the runbook finds the account each one belongs to, plans the application in the allocation order, and lists the ones it could not place with the reason beside each — **and it applies nothing**, for two independent reasons that are both printed on the screen.

| The card says | What is built | Why |
|---|---|---|
| Trigger ⚡ `batch.landed` | **manual · schedule** | A person uploads the file (PO ruling 6 Sep 2026). `batch.landed` is emitted by nothing, and a runbook whose only trigger is an unbuilt event is not runnable |
| Tiles read **Applied** · **Applied value** | **To apply** · **To apply value**, with *Planned — waiting for a second approval* underneath | A tile reading *129 Applied* over a run that applied nothing is the most dangerous sentence this screen could print. The card's words return the day a writer is bound and a second person approves |
| By source: Lockbox · Bank file · Portal · Kiosk | The sources that actually landed | An uploaded remittance batch is `lockbox` or `csv` in this product; Portal and Kiosk are tenders on a recorded payment, not files anybody uploads. Two permanently empty rows would be decoration |
| Parameter **Most per run · 2,000** | Not a parameter — `runbooks.cap`, default **100** | The cap REFUSES the run rather than truncating it (`BR-RBS-006`) and lives on the runbook row. `OQ-RBS-1731` closed on 6 Sep 2026 at 100. A parameter of the same name would be a second copy of one policy |
| Six result regions, no chain | A **chain** is drawn **only when the run stopped** | The frame draws a run that finished. A stopped run is a state the frame does not cover, and the chain is the only block that can say *this step never ran* |

### Step 1 is *where today's work comes from*, and it can STOP the run

PO ruling 6 September 2026: *"in absence of API conenctions you will not find anything and you can stop the job saying APi or conenct not available; that is a valid case and state for us"*.

Two doors — a live payment-provider connection, and a file somebody uploaded. When **both** are shut the run closes **stopped**: one red chain cell reading *Nothing to work on.*, six cells reading *Never reached*, and a sentence saying what to do. **No KPI strip** — *0 applied · $0.00 · 0 need a person* over a run that examined nothing reads exactly like a clean day.

A connection with no file is a **different** sentence — *Nothing has landed yet.* — and a connection that exists with its switch off is named as such, because that one has a two-second fix.

### Nothing is applied, and both reasons are on the screen

1. **Every money-bearing action carries a second approval, with no threshold** (`BR-RBS-018`, CONFIRMED 6 Sep 2026). The runbook reads `approved_by` **and** `approved_count`: approving *129 to apply* and acting on 140 is the failure the second column exists to refuse.
2. **No writer is bound to `apply_payment` or `queue_receipt`** until `CR-075` task `L2`. The port is CALLED anyway and its own refusal is the outcome — there is no `if is_bound` branch, because `BR-RBS-003` makes dry and live one code path.

### ⚖ The judgments this lane made where the documents did not settle it

Recorded here rather than only in code comments, because a wrong one should be cheap to reverse.

1. **What counts as a match is `payments`' answer, not a second one.** `payment_import._match_row` already walks the card's ladder — account number, then remittance id, then name and amount — so the runbook READS its verdict rather than matching again. Two implementations of one ladder is how a screen and a runbook end up disagreeing about whose money it is.
2. **A name-and-amount hit is never planned for application.** It carries the suggested account and a *Likely* confidence and goes to the *needs a person* list, which is the card's own *"a clerk confirms a guess, the runbook does not make it"* made mechanical.
3. **A duplicate is the SECOND of a pair, never the first.** Inside one file, the first cheque of an identical pair is planned and only the second is held. Holding both would stop a legitimate payment as well as the copy.
4. **A short payment is applied; an overpayment above the threshold is not.** A part payment is what the allocation order is for. A surplus is a decision about what happens to the extra money, which is a person's call.
5. **An account whose books will not open becomes a row, not a silence.** The balance read can refuse for reasons this module has no vocabulary for; that ONE payment is reported as *this account's open bills could not be read* and the other 137 carry on.
6. **The batch is a declared INPUT, not something the runbook goes looking for.** `payments` publishes no list of uploaded batches (inventoried as `S-15`, owned by `payments`), and taking it as an input is also the shape the Product Owner described: a person collects the file and uploads it.
7. **The file's columns are `payments`' own aliases**, not a set this runbook invents — `account_ref`, `payer_name`, `amount`, `paid_on`, `reference`, matched by NAME and never positionally.

### Proved by

`06-backend/tests/test_us_rbs_022_cash_application.py` (the rules, with the seams replaced) and `06-backend/tests/test_rbs_money_runbooks_pg.py` (the stop, the money path, the dry promise and the tenant boundary on real PostgreSQL, through the REAL seams). The browser walkthrough is `10-scripts/render-checks/rbs-p-money-runbooks.mjs` with `rbs_p_seed_money.py` as its fixture — **44 of its 45 checks pass.**

### ⚠ One thing on this screen does not work, and it is not this runbook's

**`DEF-RBS-4329` — every *Fix* link on `RBS-006` opens *"This screen is not built yet."*** The renderer resolves a fix route against the run's own address, so *Pick account →* lands on `…/runbooks/cash-application/runs/<id>/payments/record` instead of `…/payments/record`. It predates this runbook (the renderer's link has behaved this way since wave `C` task `C1b`) and it breaks the same column on **runbook 1** as well. `BR-RBS-011` is the rule it breaks: a failure names its fix route, and one that opens onto *not built yet* has not.

---

Source: the Runbooks definitions document (*Twenty-One Runbooks*, restructured 5 September 2026; build sheets added 6 September 2026) and the Runbooks specification, section B2b. Every figure in the sections above the build note is the source's own; nothing has been added, and where the source is silent this file says so. Status of **RB-110: BUILT, VERIFIED-UNRATIFIED** — the runbook exists, its rules are asserted by tests that were first shown failing, and no human has signed it off.
