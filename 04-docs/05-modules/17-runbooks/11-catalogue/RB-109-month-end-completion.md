# RB-109 — Runbook 9 · Month-end completion

**On screen a clerk sees “Books tie-out.”** The definition title above is the name on its card; the screen name is the display name in the templates library and on every wireframe.

## What it declares

| | |
|---|---|
| **Kind** | Check |
| **Category** (one home, from the fixed list of sixteen) | Finance |
| **Tags** | Billing · Payments |
| **Phase** | 1d |
| **Trigger** | Schedule |
| **Subject and unit of work** | Period |
| **Step modes** | set |
| **Result blocks it composes** | Verdict · KPIs · Reconciled · Records · Action (close, by a person) · Downloads |
| **Ports it holds** | — (a Check holds none; **Close** is a ledger act a person performs) |
| **Proves** | US-RBS-009 |
| **Waits on** | — |

> A Check is constructed with **no ports**, so a write is not refused at runtime — it is unavailable (`BR-RBS-002`, `TC-RBS-1`).

## What it answers

Answers: can this period be closed? Scope is one accounting period; the output is either balanced or the exact list of what is not. Closing the period itself stays a human act on the last line.

## Scope — how the set is decided

| Row | Value | Control |
|---|---|---|
| Period | August 2026 | value, not editable on this screen |
| Books | All | value, not editable on this screen |
| Currency | USD | value, not editable on this screen |

The scope function also answers the count on the screen: **3 bill runs · 4,118 payments · 61 adjustments in the period.**

## Parameters

A parameter marked **Settings** is read-only here: policy lives in Settings and is never duplicated on a card (`RBR-03`, `RB-021`). Money is stored to 4 decimals and shown to 2; percentages are stored to 6 and shown to 2; rates carry 4 decimals.

| Parameter | Value on the card | Control | Read-only because it lives in Settings |
|---|---|---|---|
| Tie-out tolerance | $0.00 | input | — |
| Bank rec must be complete | on | toggle | — |
| Unapplied cash allowed | $0.00 | input | — |
| Prepare exports | Ledger · Remittance | dropdown | — |
| Runs | Last day, 23:00 | dropdown | — |

Tolerance defaults to zero, **and the tax line has none at all** (`RBR-10`). Tax is remitted to an authority; there is no "we'll fix it next month".

## Steps

Source heading: **Steps 9 · all read**. Steps run in the order shown.

| # | Step | What it does | Mode |
|---|---|---|---|
| 1 | Every run finished | Issued or cancelled — nothing half-done | `read` |
| 2 | Every payment posted | And allocated to a bill or held as unapplied | `read` |
| 3 | Unapplied cash | Listed, and within the amount allowed | `read` |
| 4 | Receivables tie | Sub-ledger to control account, to the cent | `read` |
| 5 | Revenue and tax tie | Billed totals to posted totals, per service | `read` |
| 6 | Bank reconciled | No unmatched statement lines | `read` |
| 7 | Adjustments approved | Every write-off and credit has its approver | `read` |
| 8 | Deposits and refunds | Held deposits reconcile; refunds cleared | `read` |
| 9 | Exports ready | Files prepared, not yet sent | `read` |

## Guards — what it may never touch

- It is a Check, so it holds no ports and writes nothing.
- **The tax line has no tolerance and it cannot be raised** (`RBR-10`).
- **Closing the period is a named person's act, never a step** (`RBR-11`). The period lock is an irreversible act with a person's name on it; this runbook's job is to make that person confident, not to make the decision for them.
- The GL export can only be called once Close has been pressed — an unbalanced period cannot leave the building, and that guard lives here, not in the connector.

## Produces

Balanced — with the figures — or the list of what is not, each item linking to the screen that settles it. The Close period button appears only when the list is empty, and a person presses it.

### The run, with the source's own figures

**August 2026 — "3 things to settle before closing."**

- Verdict band: **Not balanced** · 6 of 9 steps clear · Tax off by $14.25 · $312.00 unapplied · 3 bank lines unmatched.
- Tiles: **$0.00** Receivables difference · **$0.00** Revenue difference · **−$14.25** Tax difference · **$312.00** Unapplied cash.
- Tie-out (Billed · In the books · Difference): Receivables $1,204,318.22 · $1,204,318.22 · Ties; Revenue $388,412.60 · $388,412.60 · Ties; Tax $23,304.76 · $23,290.51 · **−$14.25**; Deposits held $38,150.00 · $38,150.00 · Ties. The first header of that table is blank by design.
- To settle · 3: Tax does not tie · One correction posted without tax · Open correction →; Unapplied cash · $312.00 across 2 payments · Allocate →; Bank lines unmatched · 3 lines · $1,910.00 · Reconcile →.
- Actions: ↓ Tie-out; **Close period ✓ disabled** carrying its reason. ⚠ **The reason counts BLOCKERS and uses the table's own word for them** — in this illustration all three settle rows are blockers so *"3 items open"* and *"3 blockers open"* coincide; on real books they do not. The seeded utility's August has **six rows on the list and four that block**, and a button saying *"4 items open"* over a table of six is a mismatch a finance user would stop and try to resolve. It reads **"4 blockers open."** ⚠ **A warning never disables it** (`BR-LED-018` forbids a hard lockout): two of the six are permanent stated absences — nothing records an adjustment's approver (`OQ-RBS-1739`) and a month with no bank statement cannot be counted — and counting them would leave the button disabled on every tenant for ever, a check incapable of passing.
- Variant · balanced: **Balanced** · 9 of 9 steps clear · Receivables · revenue · tax · deposits all tie · exports ready — and only now does Close period ✓ enable, for a named person to press.

Every figure above is an **illustrative fixture**, not a finance-signed number — but the tables on the screens add up to them, so moving one is still an error.

**Done looks like** (the commitment's own sentence, RB-109, status UNVERIFIED): Tom sees "3 things to settle before closing" with Tax off by $14.25, $312.00 unapplied and 3 bank lines unmatched, and Close period disabled with "3 items open"; when the list is empty the button enables and a named person presses it.

## Its screens

| | Wireframe | Build sheet | Route | Code in the source document |
|---|---|---|---|---|
| Setup | `RBS-004-R9.png` | `RBS-004-R9.md` | `…/runbooks/month-end` | `S150-R9`, figure 15 |
| Result | `RBS-006-R9.png` | `RBS-006-R9.md` | `…/runbooks/month-end/runs/aug` | `S152-R9`, figure 16 |

They live in `04-docs/05-modules/17-runbooks/wireframes/`. **The build sheet beside each frame is the acceptance check**: the built screen must show exactly those regions in that order with that copy, at those sizes, in those states. A region missing, a control added, a word changed or a size off is a defect of kind *Screen, copy or layout*, filed with the screen code and the region number. A sheet and its frame cannot disagree — one is derived from the other; if one is wrong, both are, and the frame is the thing to fix.

> The source document numbers these screens `S150-R9` and `S152-R9`. This repository numbers them `RBS-004-R9` and `RBS-006-R9` (PO ruling 2026-09-06: *"Screens S147–S154 - this should be RBS-nnn"*). Nothing in the source documents is renamed; the codes above are how the two meet.

## Design notes on the result

Billed · In the books · Difference uses the product's ratified pair of words for "held here" and "posted" (B14 rule 34). Receivables and revenue tying while tax does not is the common real case, and a $14.25 tax difference stops the close because tax is remitted to an authority. The disabled Close button carries its reason in words rather than being hidden.

## Open questions and stated absences

- **The period lock is deliberately not a step.** Closed OUT OF SCOPE, and flagged to the Product Owner as **open decision 12** — whether Close may ever be automated. That decision is open.
- **Close period stays disabled until the settle list is empty.** Closed OUT OF SCOPE — the button carries its reason in words rather than being hidden, which is the platform's own rule for a control a user may not yet use (`RBR-06`, B14).
- ~~*"The tax line at month end has no tolerance"* is a rule with **no home in the repository yet** — convention on the definition card, not yet code.~~ **CLOSED 2026-09-07: it is code.** `BR-RBS-029` is `month_end.TAX_TOLERANCE = Decimal("0.0000")` and `_refuse_a_tax_tolerance`, which runs during the import `AppConfig.ready()` performs — so a tax-tolerance parameter added to the definition **stops the process from starting and names itself**. Refused at CONSTRUCTION and not at run time, for the reason `BR-RBS-002` is: a run-time check would mean a runbook with a raised tax tolerance existing in memory on a live schedule.

---

Source: the Runbooks definitions document (*Twenty-One Runbooks*, restructured 5 September 2026; build sheets added 6 September 2026) and the Runbooks specification, section B2b. Every figure here is the source's own; nothing has been added, and where the source is silent this file says so. Status of **RB-109: VERIFIED 2026-09-07** — `06-backend/tests/test_us_rbs_009_month_end.py`, and the run below was reproduced through the engine on the seeded utility for **August 2026**: *Not balanced · 6 of 9 steps clear · USD 1,195.05 unapplied · Tax off by USD 816.45 · Tax remittance not done.* Receivables **$7,984.68 = $7,984.68** and deposits held **$750.00 = $750.00**, both Ties. ⚠ **The tax figure is NOT trustworthy and the runbook says so on the row** — `DEF-LED-4356`: the ledger's tax comparison windows the register side and not the GL side, so the honest August drift is **−$2.30** and not **+$816.45**. Was **UNVERIFIED** — engineering fills that in from the code, and a test that was first shown failing is what moves it.
