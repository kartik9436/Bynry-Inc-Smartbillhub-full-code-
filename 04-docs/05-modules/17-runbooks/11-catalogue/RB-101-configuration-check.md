# RB-101 — Runbook 1 · Configuration check

**On screen a clerk sees “Can we bill?.”** The definition title above is the name on its card; the screen name is the display name in the templates library and on every wireframe.

## What it declares

| | |
|---|---|
| **Kind** | Check |
| **Category** (one home, from the fixed list of sixteen) | Platform |
| **Tags** | Plans & Rates · Service points |
| **Phase** | 1a |
| **Trigger** | Manual |
| **Subject and unit of work** | Tenant · config graph |
| **Step modes** | set · per record |
| **Result blocks it composes** | KPIs · Chain · Records · Downloads |
| **Ports it holds** | — (a Check is constructed with no ports; the engine raises the work items at run close) |
| **Proves** | US-RBS-001 · J-RBS-1 |
| **Waits on** | — |

> A Check is constructed with **no ports**, so a write is not refused at runtime — it is unavailable (`BR-RBS-002`, `TC-RBS-1`).

## What it answers

Answers: is the product configured correctly, and do the data and the process hold together end to end? Runs on demand, and again before every bill run as part of runbook 3 via the requires step, `RB-036`.

## Scope — how the set is decided

The setup panel is headed **Scope decided for you**.

| Row | Value | Control |
|---|---|---|
| Covers | Whole utility | value, not editable on this screen |
| Services | Water · Sewer | value, not editable on this screen |
| As at | Today | value, not editable on this screen |

Nothing to choose. It reads your enabled services and checks everything behind them.

## Parameters

A parameter marked **Settings** is read-only here: policy lives in Settings and is never duplicated on a card (`RBR-03`, `RB-021`). Money is stored to 4 decimals and shown to 2; percentages are stored to 6 and shown to 2; rates carry 4 decimals.

| Parameter | Value on the card | Control | Read-only because it lives in Settings |
|---|---|---|---|
| Report | Blockers and warnings | dropdown | — |
| Usage to cover | Highest seen, 12 months | dropdown | — |
| Include held accounts | off | toggle | — |
| Raise work items | on | toggle | — |

## Steps

Source heading: **Steps 10 · all read**. Steps run in the order shown.

| # | Step | What it does | Mode |
|---|---|---|---|
| 1 | Services and units | Every enabled service has a unit and a basis | `read` |
| 2 | Reference data | Number series, holidays, account types present | `read` |
| 3 | Tax | A region on every service point | `read` |
| 4 | Plans in force | Every plan has a version covering today | `read` |
| 5 | Rate coverage | Blocks cover zero to the highest usage seen | `read` |
| 6 | Account chain | Account → unit → premise → address, unbroken | `read` |
| 7 | Meters | Every metered unit has a meter, multiplier and unit | `read` |
| 8 | Reads and windows | One read per meter; read window closes before bill day | `read` |
| 9 | Documents | Bill and notice templates exist for every service | `read` |
| 10 | Books | Every charge code and tender maps to an account | `read` |

## Guards — what it may never touch

- It is a Check, so it is constructed with no ports and cannot write to any table or send anything. Raising the work items is the **engine's** act when the run closes, not the runbook's — that is how a Check populates the work list and still has no writer.
- `Include held accounts` is off by default.

## Produces

A list of blockers and warnings, each naming the screen that fixes it, and a work item per blocker. Clear when nothing is found.

### The run, with the source's own figures

**Run · Today 08:12 — "3 things stop billing."**

- Tiles: **3** Blockers · **6** Warnings · **7 of 10** Steps clear · **12s** Took.
- A ten-cell chain — 1 Services · 2 Reference data · 3 Tax · 4 Plans · 5 Rate coverage · 6 Account chain · 7 Meters · 8 Reads · 9 Documents · 10 Books — red at the earliest failure, and a red cell names the blocker.
- Chips: All 9 · Blockers 3 · Warnings 6.
- Table — Step · Finding · Affects · Weight · Fix, showing 1–6 of 9: Tax · No tax region set · 2,907 service points · Blocks billing · Set a tax region →; Rate coverage · No block above 20,000 gal · Residential Water · Blocks billing · Add a block →; Account chain · 240 accounts have no unit · 240 accounts · Blocks billing · Match units →; Reads · 41 meters have one read only · 41 meters · Warning · Import history →; Documents · No Spanish bill template · Water · Sewer · Warning · Add template →; Meters · 3 meters have no multiplier · 3 meters · Warning · Set multiplier →.
- Actions: ↓ Findings · Run again ▶ (both enabled); each Fix → enabled.

Every figure above is an **illustrative fixture**, not a finance-signed number — but the tables on the screens add up to them, so moving one is still an error.

**Done looks like** (the commitment's own sentence, RB-101, status UNVERIFIED): A clerk presses Run and sees "3 things stop billing" with a ten-cell chain, red at Tax, Rate coverage and Account chain, and each finding has a button such as "Set a tax region →".

## Its screens

| | Wireframe | Build sheet | Route | Code in the source document |
|---|---|---|---|---|
| Setup | `RBS-004-R1.png` | `RBS-004-R1.md` | `…/runbooks/configuration-check` | `S150-R1`, figure 1 |
| Result | `RBS-006-R1.png` | `RBS-006-R1.md` | `…/runbooks/configuration-check/runs/today` | `S152-R1`, figure 2 |

They live in `04-docs/05-modules/17-runbooks/wireframes/`. **The build sheet beside each frame is the acceptance check**: the built screen must show exactly those regions in that order with that copy, at those sizes, in those states. A region missing, a control added, a word changed or a size off is a defect of kind *Screen, copy or layout*, filed with the screen code and the region number. A sheet and its frame cannot disagree — one is derived from the other; if one is wrong, both are, and the frame is the thing to fix.

> The source document numbers these screens `S150-R1` and `S152-R1`. This repository numbers them `RBS-004-R1` and `RBS-006-R1` (PO ruling 2026-09-06: *"Screens S147–S154 - this should be RBS-nnn"*). Nothing in the source documents is renamed; the codes above are how the two meet.

## Open questions and stated absences

- **No scope picker — "Nothing to choose."** Recorded as a stated absence and closed OUT OF SCOPE: *"Ruled by this specification, 4 September 2026; Product Owner not asked; the scope is the tenant's enabled services."*
- A runbook calling another runbook was drawn on this card and was **not in the contract**. That gap is now `RB-036` — a `requires` step, `BR-RBS-027`, `TC-RBS-21`. Runbooks 2 and 3 call this one through it.

---

Source: the Runbooks definitions document (*Twenty-One Runbooks*, restructured 5 September 2026; build sheets added 6 September 2026) and the Runbooks specification, section B2b. Every figure here is the source's own; nothing has been added, and where the source is silent this file says so. Status of **RB-101: UNVERIFIED** — engineering fills that in from the code, and a test that was first shown failing is what moves it.
