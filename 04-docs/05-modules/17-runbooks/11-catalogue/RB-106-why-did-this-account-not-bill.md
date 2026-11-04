# RB-106 — Runbook 6 · Why did this account not bill?

## What it declares

| | |
|---|---|
| **Kind** | Check |
| **Category** (one home, from the fixed list of sixteen) | Billing |
| **Tags** | Accounts |
| **Phase** | 3 |
| **Trigger** | Manual · and `bill_run.completed(run_id)` for the whole-break-list variant |
| **Subject and unit of work** | Account · one, or a break list |
| **Step modes** | per record (1) |
| **Result blocks it composes** | Sentence · Chain · Facts · Records |
| **Ports it holds** | — (a Check holds none) |
| **Proves** | US-RBS-021 |
| **Waits on** | — |

> A Check is constructed with **no ports**, so a write is not refused at runtime — it is unavailable (`BR-RBS-002`, `TC-RBS-1`).

## What it answers

Answers: a bill run finished and this account produced nothing — what stopped it? Scope is one account and one run; the answer is the single earliest stop in the chain and the screen that fixes it.

## Scope — how the set is decided

The setup panel is headed **Scope one account, or the whole break list**.

| Row | Value | Control |
|---|---|---|
| Account | 🔍 Okonkwo, D. · 2 Mill Rd | value, not editable on this screen |
| Bill run * | Monthly A · Sep · 20 Sep | dropdown |

Or run it for all 14 accounts that run left unbilled.

## Parameters

A parameter marked **Settings** is read-only here: policy lives in Settings and is never duplicated on a card (`RBR-03`, `RB-021`). Money is stored to 4 decimals and shown to 2; percentages are stored to 6 and shown to 2; rates carry 4 decimals.

| Parameter | Value on the card | Control | Read-only because it lives in Settings |
|---|---|---|---|
| Stop at first cause | on | toggle | — |
| Re-price to confirm | on | toggle | — |
| Raise a work item | on | toggle | — |

## Steps

Source heading: **Steps 7 · all read · stops at the first that fails**. Steps run in the order shown.

| # | Step | What it does | Mode |
|---|---|---|---|
| 1 | Was it in scope? | Status, cycle, service dates inside the period | `read` |
| 2 | Was it held on purpose? | A hold, a dispute, a deliberate exclusion | `read` |
| 3 | A plan in force? | For every service, for the whole period | `read` |
| 4 | A read for every service? | Actual or estimated, inside the window | `read` |
| 5 | Did pricing refuse? | Which step, which sentence | `read` |
| 6 | Did the write refuse? | A duplicate, a constraint, a number series exhausted | `read` |
| 7 | Did it bill last time? | What changed since the run that worked | `read` |

## Guards — what it may never touch

- It is a Check, so it holds no ports and writes nothing. `Raise a work item` is the engine's act at run close.
- It **stops at the first failure** because a clerk needs one answer, not seven.

## Produces

One sentence: "Stopped at step 4 — no Sewer read between 18 Aug and 17 Sep. Last billed 20 Aug." With Add a read → beside it.

### The run, with the source's own figures

**Okonkwo, D. · 2 Mill Rd — "Stopped at step 4 · Monthly A · September · run of 20 Sep."**

- Stop card: **No Sewer read between 18 Aug and 17 Sep** — *Water has a read. Sewer does not. The account cannot bill until it does.*
- A seven-cell chain: 1 In scope · 2 Not held · 3 Plan in force · 4 **Read missing** · 5 Pricing *Never reached* · 6 Write *Never reached* · 7 Last time *Billed 20 Aug*.
- Facts: Last billed 20 Aug · $96.40; Water read 12 Sep · 4,410 gal; Sewer read None in window; What changed since August — Sewer meter exchanged 2 Sep.
- Variant — the whole break list, 14 accounts. Chips: All 14 · Read 9 · Plan 3 · Rate 2. Table — Account · Stopped at · Why · Fix, showing 1–3 of 14: Okonkwo, D. · 4 · Read · No Sewer read in window · Add a read →; Vance, L. · 3 · Plan · Plan ended 31 Aug · Assign a plan →; Marsh Farms · 5 · Pricing · 28,400 gal · no block above 20,000 · Add a block →.
- Action: Add a read → (primary, in the page head).

Every figure above is an **illustrative fixture**, not a finance-signed number — but the tables on the screens add up to them, so moving one is still an error.

**Done looks like** (the commitment's own sentence, RB-106, status UNVERIFIED): A clerk opens the account and reads "Stopped at step 4 · No Sewer read between 18 Aug and 17 Sep" with Add a read → in the page head; the variant lists all 14 accounts the run left unbilled by the step that stopped them.

## Its screens

| | Wireframe | Build sheet | Route | Code in the source document |
|---|---|---|---|---|
| Setup | `RBS-004-R6.png` | `RBS-004-R6.md` | `…/runbooks/why-not-billed` | `S150-R6`, figure 11 |
| Result | `RBS-006-R6.png` | `RBS-006-R6.md` | `…/runbooks/why-not-billed/runs/okonkwo-sep` | `S152-R6`, figure 12 |

They live in `04-docs/05-modules/17-runbooks/wireframes/`. **The build sheet beside each frame is the acceptance check**: the built screen must show exactly those regions in that order with that copy, at those sizes, in those states. A region missing, a control added, a word changed or a size off is a defect of kind *Screen, copy or layout*, filed with the screen code and the region number. A sheet and its frame cannot disagree — one is derived from the other; if one is wrong, both are, and the frame is the thing to fix.

> The source document numbers these screens `S150-R6` and `S152-R6`. This repository numbers them `RBS-004-R6` and `RBS-006-R6` (PO ruling 2026-09-06: *"Screens S147–S154 - this should be RBS-nnn"*). Nothing in the source documents is renamed; the codes above are how the two meet.

## Why the card reads this way

This is runbook 3 run backwards, for one account, after the fact. Same checks, opposite direction. Re-price to confirm pushes the account through the real engine so the sentence shown is the engine's refusal, not an inference about it — the same principle as the test bill.

## Design notes on the result

One answer, stated twice — as a sentence and as the chain with the red cell — and the fix is the primary button in the page head, because the clerk opened this to fix it. "What changed since August" is the row that usually explains everything: here a meter exchange on 2 Sep is why the read is missing. The variant groups the whole break list by the step that stopped each account, so nine missing reads are handled as one job rather than nine.

## Open questions and stated absences

*The source names none for this runbook.*

---

Source: the Runbooks definitions document (*Twenty-One Runbooks*, restructured 5 September 2026; build sheets added 6 September 2026) and the Runbooks specification, section B2b. Every figure here is the source's own; nothing has been added, and where the source is silent this file says so. Status of **RB-106: UNVERIFIED** — engineering fills that in from the code, and a test that was first shown failing is what moves it.
