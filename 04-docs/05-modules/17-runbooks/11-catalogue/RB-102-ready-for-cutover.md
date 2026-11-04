# RB-102 — Runbook 2 · Ready for cutover?

**On screen a clerk sees “Cutover reconciliation.”** The definition title above is the name on its card; the screen name is the display name in the templates library and on every wireframe.

## What it declares

| | |
|---|---|
| **Kind** | Check |
| **Category** (one home, from the fixed list of sixteen) | Onboarding & Cutover |
| **Tags** | Platform · Billing |
| **Phase** | 1d |
| **Trigger** | Manual |
| **Subject and unit of work** | Tenant + uploaded file · plan items |
| **Step modes** | set |
| **Result blocks it composes** | Verdict · KPIs · Chain · Reconciled · Records · Downloads |
| **Ports it holds** | — (a Check holds none; attaching evidence to the plan is an act the engine or the owning module performs) |
| **Proves** | US-RBS-008 |
| **Waits on** | RB-035 · RB-036 |

> A Check is constructed with **no ports**, so a write is not refused at runtime — it is unavailable (`BR-RBS-002`, `TC-RBS-1`).

## What it answers

Answers: can we switch this utility off the old system on the agreed date? Runs at freeze, and as often as the implementer wants before it.

## Scope — how the set is decided

| Row | Value | Control |
|---|---|---|
| Cutover plan | Silver Creek go-live | value, not editable on this screen |
| Legacy balances * | ↑ trial-balance.csv | input · required |
| As at * | 🗓 6 Sep 2026 | input · required |

The scope function also answers the count on the screen: **Compares 2,907 loaded accounts against 2,911 in the file.**

## Parameters

A parameter marked **Settings** is read-only here: policy lives in Settings and is never duplicated on a card (`RBR-03`, `RB-021`). Money is stored to 4 decimals and shown to 2; percentages are stored to 6 and shown to 2; rates carry 4 decimals.

| Parameter | Value on the card | Control | Read-only because it lives in Settings |
|---|---|---|---|
| Money tolerance | $0.01 | input | — |
| Total tolerance | 0.05% | input | — |
| Open items at | Invoice level | dropdown | — |
| Sample data must be gone | on | toggle | — |
| Coverage grid must pass | on | toggle | — |

## Steps

Source heading: **Steps 9 · all read**. Steps run in the order shown.

| # | Step | What it does | Mode |
|---|---|---|---|
| 1 | Configuration check passes | Requires runbook 1 (`RB-036`): its own run, linked here; stops if it fails | `read` |
| 2 | Counts agree | Accounts, premises, meters, live services against the file | `read` |
| 3 | Balances tie | Every account within $0.01; the total within 0.05% | `read` |
| 4 | Deposits and credits | Held deposits, credits and unapplied cash match | `read` |
| 5 | Plans and levels carried | Payment plans and budget levels present | `read` |
| 6 | Numbering continues | Bill, receipt and customer numbers follow on | `read` |
| 7 | Sample data gone | No sample row remains | `read` |
| 8 | Coverage grid green | Last grid run had no refusals | `read` |
| 9 | Plan items complete | Every human task done, evidence attached | `read` |

## Guards — what it may never touch

- It is a Check, so it holds no ports and writes nothing.
- Step 1 requires runbook 1. If that sub-run fails, steps 2 to 9 read "Never reached" and the verdict is No-go (`RB-036`, `BR-RBS-027`).
- `Sample data must be gone` and `Coverage grid must pass` are both on.

## Produces

Go or No-go, with every disagreeing account listed with both figures and the difference, and the plan items still open.

### The run, with the source's own figures

**Run · 6 Sep 14:02 — "Balances do not tie."**

- Verdict band, danger tone: **No-go** · 2 of 9 steps not clear · Balances off by $1,204.05 · 2 plan items open.
- Tiles: **−$1,204.05** Balance difference · **0.29%** Of total · limit 0.05% · **12** Accounts disagree · **7 of 9** Steps clear.
- A nine-cell chain, red at 3 Balances and 9 Plan items.
- Counts and totals (Legacy file · Loaded · Difference): Accounts 2,911 · 2,907 · −4; Premises 2,862 · 2,862 · 0; Meters 2,842 · 2,842 · 0; Receivables $412,880.44 · $411,676.39 · −$1,204.05; Deposits held $38,150.00 · $38,150.00 · $0.00. The first header of that table is blank by design.
- Accounts that disagree · 12, showing 1–3: Okonkwo, D. $1,204.05 · $0.00 · −$1,204.05; Reyes, P. $88.20 · $88.20 · absent in file; Hale, T. $0.00 · $0.00 · absent in file.
- Plan items still open · 2: Customer signs bill layout · Bynry · Human task; Legacy set read-only · Utility IT · Human task.
- Actions: ↓ Differences · Attach to plan ✓ · Run again ▶ (all enabled).

Every figure above is an **illustrative fixture**, not a finance-signed number — but the tables on the screens add up to them, so moving one is still an error.

**Done looks like** (the commitment's own sentence, RB-102, status UNVERIFIED): An implementer uploads the legacy trial balance and sees No-go with "Balances off by $1,204.05 · 2 plan items open", the twelve disagreeing accounts with both figures, and Attach to plan ✓.

## Its screens

| | Wireframe | Build sheet | Route | Code in the source document |
|---|---|---|---|---|
| Setup | `RBS-004-R2.png` | `RBS-004-R2.md` | `…/runbooks/cutover-readiness` | `S150-R2`, figure 3 |
| Result | `RBS-006-R2.png` | `RBS-006-R2.md` | `…/runbooks/cutover-readiness/runs/6-sep` | `S152-R2`, figure 4 |

They live in `04-docs/05-modules/17-runbooks/wireframes/`. **The build sheet beside each frame is the acceptance check**: the built screen must show exactly those regions in that order with that copy, at those sizes, in those states. A region missing, a control added, a word changed or a size off is a defect of kind *Screen, copy or layout*, filed with the screen code and the region number. A sheet and its frame cannot disagree — one is derived from the other; if one is wrong, both are, and the frame is the thing to fix.

> The source document numbers these screens `S150-R2` and `S152-R2`. This repository numbers them `RBS-004-R2` and `RBS-006-R2` (PO ruling 2026-09-06: *"Screens S147–S154 - this should be RBS-nnn"*). Nothing in the source documents is renamed; the codes above are how the two meet.

## Why the card reads this way

Scope here has three inputs, and one is a file. ⚠ **THIS PARAGRAPH SAID THE TRIAL BALANCE IS *"uploaded through the existing import runner"* UNTIL 2026-09-07, AND IT IS NOT — the reason is decisive rather than a preference.** `trial_balance` is **not one of the six `IMPORT_TARGETS`**, so `metering.import_runs.extract` refuses it by name and a runbook reading a staged batch for it could **never** get one back: a check *incapable of passing*, which is CLAUDE.md hard-won law 7's third shape. The runner is also a **stage → map → validate → LOAD** machine for entity rows, and a trial balance is compared once and never written. So the file is the `file` parameter's own content, parsed by the runbook, and **the per-row refusals this paragraph wanted are the runbook's own product**: every unreadable line is KEPT as a finding carrying its LINE NUMBER and a fix route, because a silently skipped row is a bill the old system says is open and this product would never mention — precisely what a cutover reconciliation exists to catch. Decision log, 2026-09-07.

## Design notes on the result

The verdict banner carries the two reasons, not just the word. The totals table puts file · loaded · difference side by side because an implementer at freeze wants to see both figures, not be told they differ. Attach to plan ✓ is what turns a run into evidence on the cutover plan item — the run id and these figures are stored on it, so the plan shows why it went green, not merely that it did.

## Open questions and stated absences

- Attaching the run to a cutover plan item is `RB-035`, and that commitment **waits on open decision 8** — a product screen now, or a spreadsheet for the first two customers.
- The `requires` step this card depends on is `RB-036`, new to the contract in this pass.
- Cutover open items are carried as **one line per open invoice** — PO ruling, 5 September 2026, chosen from one line per open invoice / one balance per account / one bucket per age band. The `Open items at` parameter exists because a legacy system that cannot produce invoice detail needs the bucket option available rather than a workaround.

---

Source: the Runbooks definitions document (*Twenty-One Runbooks*, restructured 5 September 2026; build sheets added 6 September 2026) and the Runbooks specification, section B2b. Every figure here is the source's own; nothing has been added, and where the source is silent this file says so. Status of **RB-102: VERIFIED 2026-09-07** — `06-backend/tests/test_us_rbs_008_cutover_readiness.py`, and the figure below was reproduced through the engine on the seeded utility: **No-go · Balances off by $1,204.05 · 11 accounts disagreeing across 12 LINES.** ⚠ **The card says *12 accounts* and the engine says 12 LINES on 11 accounts, and the engine is right about the product** — the PO ruled the grain is the OPEN INVOICE on 5 September, so one account may carry several. Was **UNVERIFIED** — engineering fills that in from the code, and a test that was first shown failing is what moves it.
