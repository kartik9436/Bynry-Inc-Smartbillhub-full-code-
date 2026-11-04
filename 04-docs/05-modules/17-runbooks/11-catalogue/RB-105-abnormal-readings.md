# RB-105 — Runbook 5 · Abnormal readings

The definitions document heads this card **“Abnormal readings — twelve months”**; the register row for RB-105 calls it **“Abnormal readings”**. Both are the source's own words.

## What it declares

| | |
|---|---|
| **Kind** | Check |
| **Category** (one home, from the fixed list of sixteen) | Reads |
| **Tags** | Assets |
| **Phase** | 3 |
| **Trigger** | Schedule · manual |
| **Subject and unit of work** | Meter · 12 months |
| **Step modes** | per record |
| **Result blocks it composes** | KPIs · Records (sparkline) · Action (raise items) · Downloads |
| **Ports it holds** | — (a Check holds none; *Raise work items ✓* is the engine's act at run close) |
| **Proves** | US-RBS-020 |
| **Waits on** | — |

> A Check is constructed with **no ports**, so a write is not refused at runtime — it is unavailable (`BR-RBS-002`, `TC-RBS-1`).

## What it answers

Answers: which meters are behaving oddly, by pattern, over the last year? Scope is a service and a window; the output groups meters by the kind of oddness and ranks them by revenue at risk.

## Scope — how the set is decided

| Row | Value | Control |
|---|---|---|
| Service | Water | value, not editable on this screen |
| Window | Last 12 months | value, not editable on this screen |
| Routes | All | dropdown |
| Meter types | All | dropdown |

The scope function also answers the count on the screen: **Matches 2,842 meters with 31,904 reads.**

## Parameters

A parameter marked **Settings** is read-only here: policy lives in Settings and is never duplicated on a card (`RBR-03`, `RB-021`). Money is stored to 4 decimals and shown to 2; percentages are stored to 6 and shown to 2; rates carry 4 decimals.

| Parameter | Value on the card | Control | Read-only because it lives in Settings |
|---|---|---|---|
| Spike above own median | 300% | input | — |
| Drop below own median | 20% | input | — |
| Zero reads in a row | 3 | input | — |
| Identical reads in a row | 4 | input | — |
| Estimated more than | 4 of 12 | input | — |
| Ignore usage under | 200 gal | input | — |

The panel is headed **Parameters thresholds**. Every threshold is relative to the meter's own history, never to a fleet average (`RBR-09`).

## Steps

Source heading: **Steps 8 · all read**. Steps run in the order shown.

| # | Step | What it does | Mode |
|---|---|---|---|
| 1 | Build each meter's year | Twelve periods, actual and estimated marked | `read` |
| 2 | Spikes | Above 300% of the meter's own median | `read` |
| 3 | Drops and zeros | Below 20%, or three zero reads running | `read` |
| 4 | Flat lines | Four identical reads — a stuck meter | `read` |
| 5 | Rollovers and negatives | A read lower than the one before | `read` |
| 6 | Over-estimated | More than four of twelve estimated | `read` |
| 7 | Out of season | Against the meter's own same-month history | `read` |
| 8 | Rank by revenue at risk | Under-billed first, then over-billed | `read` |

## Guards — what it may never touch

- It is a Check, so it holds no ports and writes nothing.
- `Ignore usage under 200 gal` exists so a vacant unit at 40 gallons a month does not produce spectacular percentages that mean nothing.

## Produces

Meters grouped by pattern, one line per meter showing the meter's own year, ranked by revenue at risk. The marked point is the anomaly; the pattern is named in words beside it, so the colour is never the only signal. Estimated reads draw dashed.

### The run, with the source's own figures

**Water · last 12 months — "75 meters worth a look."**

- Tiles: **14** Spikes · **6** Flat lines · **22** Zero streaks · **31** Over-estimated · **2** Rollovers · **$9,840** Revenue at risk.
- Chips: All 75 · Spike 14 · Flat 6 · Zero 22 · Estimated 31 · Rollover 2.
- Table — Meter · Account · Pattern · Twelve months (sparkline) · At risk ⇅ · Fix, showing 1–5 of 75 (page 1 of 2, 50 rows per page): WM-01128 · Riverside Apts · ▬ Flat · 5 months · $1,180.00 · Order a test →; WM-04471 · Alvarez, M. · ▲ Spike · Jul · $412.00 · Check for leak →; WM-02209 · Hale, T. · ○ Zero · 3 in a row · $290.00 · Confirm vacancy →; WM-00517 · Marsh Farms · ↺ Rollover · Aug · $0.00 · Confirm rollover →; WM-03390 · Nunes, R. · ≈ Estimated · 6 of 12 · $0.00 · Fix access →.
- Actions: ↓ All flagged · Raise work items ✓ (enabled, deliberate) · ▦ Columns.

Every figure above is an **illustrative fixture**, not a finance-signed number — but the tables on the screens add up to them, so moving one is still an error.

**Done looks like** (the commitment's own sentence, RB-105, status UNVERIFIED): A clerk sees 75 meters in six pattern tiles, each row with its own twelve-month line and "$1,180.00 at risk · Order a test →", sorted by revenue at risk.

## Its screens

| | Wireframe | Build sheet | Route | Code in the source document |
|---|---|---|---|---|
| Setup | `RBS-004-R5.png` | `RBS-004-R5.md` | `…/runbooks/abnormal-readings` | `S150-R5`, figure 9 |
| Result | `RBS-006-R5.png` | `RBS-006-R5.md` | `…/runbooks/abnormal-readings/runs/sep` | `S152-R5`, figure 10 |

They live in `04-docs/05-modules/17-runbooks/wireframes/`. **The build sheet beside each frame is the acceptance check**: the built screen must show exactly those regions in that order with that copy, at those sizes, in those states. A region missing, a control added, a word changed or a size off is a defect of kind *Screen, copy or layout*, filed with the screen code and the region number. A sheet and its frame cannot disagree — one is derived from the other; if one is wrong, both are, and the frame is the thing to fix.

> The source document numbers these screens `S150-R5` and `S152-R5`. This repository numbers them `RBS-004-R5` and `RBS-006-R5` (PO ruling 2026-09-06: *"Screens S147–S154 - this should be RBS-nnn"*). Nothing in the source documents is renamed; the codes above are how the two meet.

## Why the card reads this way

Every threshold is relative to the meter's own history, never to a fleet average. A restaurant and a retired couple are both normal at wildly different volumes; a fixed threshold would flag one and miss the other.

## Design notes on the result

Six tiles, one per pattern, and the chips below repeat them as filters — the tile is the count, the chip is the door. Default sort is revenue at risk, so the flat-lined apartment block is at the top rather than the vacant unit. Raise work items is a button rather than automatic because 75 items landing on a two-person work list unasked is how a work list gets ignored.

## Open questions and stated absences

- **Raise work items is a button, not automatic.** Closed OUT OF SCOPE — *"Ruled by this specification, 4 September 2026; Product Owner not asked; 75 items landing unasked is how a work list gets ignored."*

---

Source: the Runbooks definitions document (*Twenty-One Runbooks*, restructured 5 September 2026; build sheets added 6 September 2026) and the Runbooks specification, section B2b. Every figure here is the source's own; nothing has been added, and where the source is silent this file says so. Status of **RB-105: UNVERIFIED** — engineering fills that in from the code, and a test that was first shown failing is what moves it.
