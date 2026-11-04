# RB-116 — Runbook 16 · Rate change preview

## What it declares

| | |
|---|---|
| **Kind** | Check |
| **Category** (one home, from the fixed list of sixteen) | Plans & Rates |
| **Tags** | Billing |
| **Phase** | 3 |
| **Trigger** | Manual |
| **Subject and unit of work** | Bill · one cycle + a draft schedule |
| **Step modes** | per record · set (sums) |
| **Result blocks it composes** | KPIs · Ranked · Records · Breakdown · Downloads |
| **Ports it holds** | — (a Check holds none) |
| **Proves** | US-RBS-028 |
| **Waits on** | — |

> A Check is constructed with **no ports**, so a write is not refused at runtime — it is unavailable (`BR-RBS-002`, `TC-RBS-1`).

## What it answers

Answers: what would this proposed tariff have done to last cycle's bills? Scope is a draft rate schedule against one real, already-issued cycle. Run it before the board meeting, not after.

## Scope — how the set is decided

| Row | Value | Control |
|---|---|---|
| Proposed schedule * | Water 2027 · draft | dropdown |
| Against cycle * | Monthly A · August | dropdown |
| Services | Water | dropdown |

The scope function also answers the count on the screen: **Re-prices 1,410 bills exactly as issued.**

## Parameters

A parameter marked **Settings** is read-only here: policy lives in Settings and is never duplicated on a card (`RBR-03`, `RB-021`). Money is stored to 4 decimals and shown to 2; percentages are stored to 6 and shown to 2; rates carry 4 decimals.

| Parameter | Value on the card | Control | Read-only because it lives in Settings |
|---|---|---|---|
| Compare to | The bills actually issued | read-only, Settings-owned (dashed) | **Settings** |
| Call it large above | ± 15% | input | — |
| Show biggest movers | 50 | input | — |
| Group by | Account type | dropdown | — |
| Revenue by service | on | toggle | — |

## Steps

Source heading: **Steps 6 · all read**. Steps run in the order shown.

| # | Step | What it does | Mode |
|---|---|---|---|
| 1 | Load the draft schedule | Blocks, base, minimums as drafted | `read` |
| 2 | Load the cycle as it was billed | Every account's usage, days and plan | `read` |
| 3 | Re-price every bill under the draft | The real pricing engine, not a spreadsheet | `read` |
| 4 | Compare to the issued bill | Line by line, then total | `read` |
| 5 | Distribute and group the changes | By size of change and by account type | `read` |
| 6 | Sum revenue by service | What the change is worth, and to whom | `read` |

## Guards — what it may never touch

- It is a Check, so it holds no ports and writes nothing — no bill is re-issued and no draft is adopted.
- The re-pricing uses **the same engine as the bill run**. The rule that preview and run are one code path is what makes this trustworthy rather than an estimate.

## Produces

A distribution of bill changes, the fifty biggest movers, and revenue +$5,310 (+4.7%) by service and account type.

### The run, with the source's own figures

**Water 2027 draft · vs August — "1,146 bills go up. 121 by more than 15%."**

- Tiles: **+$5,310** Revenue · +4.7% · **1,146** Bills up · **176** Bills down · **88** Unchanged · **121** Up more than 15%.
- How bills move, five rows: Down more than 15% **21** · Down 5–15% **155** · Within 5% **562** · Up 5–15% **551** · Up more than 15% **121**.
- Biggest movers · 50, showing 1–3 — Account · Type · August · Under draft · Change · Why: Marsh Farms · Irrigation · $412.80 · $538.10 · +30.4% · New top block above 20,000 gal; Riverside Apts · Multi-unit · $1,920.40 · $2,398.00 · +24.9% · Base charge per unit; Alvarez, M. · Residential · $214.60 · $258.90 · +20.6% · Tier 2 starts at 4,000 gal, not 5,000.
- By account type — Type · Bills · August · Under draft · Change: Residential 1,204 · $88,410.20 · $91,860.40 · +3.9%; Multi-unit 96 · $14,208.00 · $15,462.10 · +8.8%; Irrigation 62 · $6,940.60 · $7,410.20 · +6.8%; Municipal 48 · $3,112.00 · $3,248.30 · +4.4%.
- Actions: ↓ All bills · ↓ Biggest movers.

Every figure above is an **illustrative fixture**, not a finance-signed number — but the tables on the screens add up to them, so moving one is still an error.

**Done looks like** (the commitment's own sentence, RB-116, status UNVERIFIED): Before the board meeting a clerk sees "1,146 bills go up · 121 by more than 15% · revenue +$5,310 (+4.7%)", the fifty biggest movers each with the clause that did it.

## Its screens

| | Wireframe | Build sheet | Route | Code in the source document |
|---|---|---|---|---|
| Setup | `RBS-004-R16.png` | `RBS-004-R16.md` | `…/runbooks/rate-change-preview` | `S150-R16`, figure 29 |
| Result | `RBS-006-R16.png` | `RBS-006-R16.md` | `…/runbooks/rate-change-preview/runs/latest` | `S152-R16`, figure 30 |

They live in `04-docs/05-modules/17-runbooks/wireframes/`. **The build sheet beside each frame is the acceptance check**: the built screen must show exactly those regions in that order with that copy, at those sizes, in those states. A region missing, a control added, a word changed or a size off is a defect of kind *Screen, copy or layout*, filed with the screen code and the region number. A sheet and its frame cannot disagree — one is derived from the other; if one is wrong, both are, and the frame is the thing to fix.

> The source document numbers these screens `S150-R16` and `S152-R16`. This repository numbers them `RBS-004-R16` and `RBS-006-R16` (PO ruling 2026-09-06: *"Screens S147–S154 - this should be RBS-nnn"*). Nothing in the source documents is renamed; the codes above are how the two meet.

## Why the card reads this way

The sleeper. It saves few hours in an average month and is the single most convincing thing to show a utility board, because it answers "what would this do to our customers" before doing it.

## Design notes on the result

The distribution is five rows, not a histogram — a board reads "121 bills go up by more than 15%" faster than a chart, and the one accent bar marks the row that will generate calls. Why on each mover names the clause of the draft that did it, so a tariff can be adjusted before it is adopted rather than defended after.

## Open questions and stated absences

- **An assumption the source relies on and never states:** accounts carry a customer class or account type with values such as Commercial, Municipal, Irrigation and Multi-unit. The grouping on this card needs the field to exist.

---

Source: the Runbooks definitions document (*Twenty-One Runbooks*, restructured 5 September 2026; build sheets added 6 September 2026) and the Runbooks specification, section B2b. Every figure here is the source's own; nothing has been added, and where the source is silent this file says so. Status of **RB-116: VERIFIED** — `CR-075` wave S, 2026-09-07.
`apps/runbooks/definitions/rate_change_preview.py` · 38 cases in
`tests/test_us_rbs_028_rate_change_preview.py`, four of which build a REAL
tariff, a real activated version and a real draft and require
`rating.runbook_reads.reprice_under_draft` to agree with
`apps.rating.engine.price_period` called directly, to four decimals · run on
the seeded utility against real PostgreSQL and walked in a browser.

**Three things worth reading before the figures.**
* **The comparison is this schedule's own portion, before taxes and fees.**
  `OQ-319` is OPEN and rating already answers it in shipped, finance-read code:
  `BR-RAT-091`'s ratified `$59.00 → $62.54` is `$59.00 × 1.06` exactly, so the
  signed figure is the service's portion. This runbook follows that answer
  rather than choosing a second one.
* **It re-prices only the bills the draft actually reaches.**
  `invoice_lines.tariff_version_id` is stamped at issue and frozen; a bill
  priced by another schedule is counted as one this draft does not touch. A
  first build re-priced the whole cycle and reported a confident `+$339.04` for
  a change none of those customers would have seen (`DEF-RBS-4407`).
* **It has NO sample guard, because this card declares none and `RB-112`'s
  does.** On a trial tenant, where 72 of 78 accounts are sample records,
  guarding them out would remove the whole cycle and tell a board *this draft
  changes nothing* over a run that looked at nothing. They are re-priced and
  COUNTED.

**On the seeded utility, 2026-09-07** — a `+8%` draft of the schedule July was
billed on, against that cycle: **49 bills · 46 reached by this draft · 46 up ·
0 down · 3 unchanged · 0 above the 15% threshold · revenue +`$527.77`
(+11.20%)**, biggest mover *Kaya Kowalski · Residential · `$148.98` →
`$169.57` · +13.82% · **Tier 3 price***. The run's own error bar: **44 of 46
reproduced the issued usage** to the cent, and `$376.00` of base charge is
reported as held constant rather than re-priced (`DEF-154`).
