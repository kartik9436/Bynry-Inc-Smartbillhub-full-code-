# RB-118 — Runbook 18 · Vacant premises with usage

## What it declares

| | |
|---|---|
| **Kind** | Check |
| **Category** (one home, from the fixed list of sixteen) | Service points |
| **Tags** | Reads · Business |
| **Phase** | 3 |
| **Trigger** | Schedule |
| **Subject and unit of work** | Premise · 90 days |
| **Step modes** | per record |
| **Result blocks it composes** | KPIs · Records · Action (raise items) · Downloads |
| **Ports it holds** | — (a Check holds none; *Raise work items ✓* is the engine's act at run close) |
| **Proves** | US-RBS-030 |
| **Waits on** | — |

> A Check is constructed with **no ports**, so a write is not refused at runtime — it is unavailable (`BR-RBS-002`, `TC-RBS-1`).

## What it answers

Answers: where is water being used with nobody billed for it — and where is an account being billed on a meter that never moves? Scope is every premise with a meter. This is revenue, not hours.

## Scope — how the set is decided

| Row | Value | Control |
|---|---|---|
| Premises | All with a meter | read-only, Settings-owned (dashed) |
| Service | Water | dropdown |
| Window | Last 90 days | dropdown |
| Never include | Sample | read-only, Settings-owned (dashed) |

The scope function also answers the count on the screen: **Checks 2,862 premises.**

## Parameters

A parameter marked **Settings** is read-only here: policy lives in Settings and is never duplicated on a card (`RBR-03`, `RB-021`). Money is stored to 4 decimals and shown to 2; percentages are stored to 6 and shown to 2; rates carry 4 decimals.

| Parameter | Value on the card | Control | Read-only because it lives in Settings |
|---|---|---|---|
| Vacant means | No active account | read-only, Settings-owned (dashed) | **Settings** |
| Usage means more than | 500 gal in 90 days | input | — |
| Stopped means | 0 for 3 reads in a row | input | — |
| Estimate revenue at | Residential base + tier 1 | dropdown | — |
| Raise work items | on | toggle | — |
| Runs | Monthly | dropdown | — |

## Steps

Source heading: **Steps 6 · all read**. Steps run in the order shown.

| # | Step | What it does | Mode |
|---|---|---|---|
| 1 | Find vacant premises with a meter | No active account against the unit | `read` |
| 2 | Find usage on them | Over the threshold inside the window | `read` |
| 3 | Find active accounts whose meter stopped | Zero for three consecutive reads | `read` |
| 4 | Check for a move-in already pending | Someone applied; this is not a finding | `read` |
| 5 | Estimate what is going unbilled | Usage priced at the plan named above | `read` |
| 6 | Group by likely cause | Occupant unbilled · construction · leak · stuck meter | `read` |

## Guards — what it may never touch

- It is a Check, so it holds no ports and writes nothing. Raising the work items is the engine's act at run close.
- **Never include: Sample.**
- A premise with a **move-in already pending** is not a finding — someone has applied.
- The revenue figure is an **estimate at a named plan** (Residential base + tier 1), and the screen says ~.

## Produces

18 vacant premises with usage, about $1,940 a month unbilled · 7 active accounts on a stopped meter · 4 already pending move-in.

### The run, with the source's own figures

**Last 90 days · Water — "18 premises. About $1,940 a month."**

- Tiles: **18** Vacant with usage · **~$1,940** Unbilled per month · **7** Meter stopped · **4** Move-in pending.
- Chips: All 25 · Vacant with usage 18 · Meter stopped 7.
- Table — Premise · Last account · Gal / 90 days · Est. / month · Likely cause · Fix, showing 1–4 of 25: 22 Harbor Rd · Closed 3 Jun · 41,200 · $286.00 · Occupant unbilled · Start account →; Lot 14, Ridge Ln · Never · 18,600 · $142.00 · Construction · Bill the builder →; 9 Willow Ct · Closed 30 Jul · 9,400 · $88.00 · Possible leak · Inspect →; 31 Bell Ave · Active · Nunes, R. · 0 · — · Stopped meter · billed base only · Order a test →.
- Actions: ↓ All · Raise work items ✓. Est. / month reads — on a stopped meter.

Every figure above is an **illustrative fixture**, not a finance-signed number — but the tables on the screens add up to them, so moving one is still an error.

**Done looks like** (the commitment's own sentence, RB-118, status UNVERIFIED): Monthly the clerk sees "18 premises · about $1,940 a month unbilled · 7 stopped meters", each with a likely cause in one of four words and a fix.

## Its screens

| | Wireframe | Build sheet | Route | Code in the source document |
|---|---|---|---|---|
| Setup | `RBS-004-R18.png` | `RBS-004-R18.md` | `…/runbooks/vacant-with-usage` | `S150-R18`, figure 33 |
| Result | `RBS-006-R18.png` | `RBS-006-R18.md` | `…/runbooks/vacant-with-usage/runs/latest` | `S152-R18`, figure 34 |

They live in `04-docs/05-modules/17-runbooks/wireframes/`. **The build sheet beside each frame is the acceptance check**: the built screen must show exactly those regions in that order with that copy, at those sizes, in those states. A region missing, a control added, a word changed or a size off is a defect of kind *Screen, copy or layout*, filed with the screen code and the region number. A sheet and its frame cannot disagree — one is derived from the other; if one is wrong, both are, and the frame is the thing to fix.

> The source document numbers these screens `S150-R18` and `S152-R18`. This repository numbers them `RBS-004-R18` and `RBS-006-R18` (PO ruling 2026-09-06: *"Screens S147–S154 - this should be RBS-nnn"*). Nothing in the source documents is renamed; the codes above are how the two meet.

## Why the card reads this way

The only runbook here whose output is a dollar figure rather than an hour figure. A vacant premise using 9,000 gallons is either an unbilled occupant, a builder, or a leak, and all three are worth a visit. The stopped-meter half is the mirror: revenue being lost on an account that looks fine.

## Design notes on the result

Default sort is estimated revenue, so the unbilled occupant is above the leak. Likely cause is one of four words a utility already uses, and the fix beside each is the module screen that handles that cause.

## Open questions and stated absences

- **Pending move-ins are counted but not listed.** Closed OUT OF SCOPE — *"they are already somebody's job."*
- **Raise work items is a button, not automatic.** Closed OUT OF SCOPE, the same ruling as runbooks 5 and 19.

---

Source: the Runbooks definitions document (*Twenty-One Runbooks*, restructured 5 September 2026; build sheets added 6 September 2026) and the Runbooks specification, section B2b. Every figure here is the source's own; nothing has been added, and where the source is silent this file says so. Status of **RB-118: UNVERIFIED** — engineering fills that in from the code, and a test that was first shown failing is what moves it.
