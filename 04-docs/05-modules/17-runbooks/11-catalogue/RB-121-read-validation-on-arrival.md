# RB-121 — Runbook 21 · Read validation on arrival

**On screen a clerk sees “Read exceptions.”** The definition title above is the name on its card; the screen name is the display name in the templates library and on every wireframe.

## What it declares

| | |
|---|---|
| **Kind** | Action |
| **Category** (one home, from the fixed list of sixteen) | Data Sync |
| **Tags** | Reads |
| **Phase** | 3 |
| **Trigger** | ⚡ `batch.landed` — an interval batch lands. The trigger is its arrival, not a clock. |
| **Subject and unit of work** | Meter-day, **never the interval** — 176,640 intervals become 1,840 records |
| **Step modes** | set (roll-up) · per record |
| **Result blocks it composes** | KPIs · Records · Downloads |
| **Ports it holds** | `write_read` (metering) |
| **Proves** | US-RBS-033 |
| **Waits on** | RB-022 (intervals landed) · RB-042 |
| **Status** | **BUILT — `06-backend/apps/runbooks/definitions/read_validation.py`** (`CR-075` wave R′, 2026-09-07). Five stamped divergences; see that file's docstring |

## What it does

Does: when an interval batch lands from the meter connection, rolls it up to the meter-day, validates it, estimates short gaps by the utility's own policy, and hands validated reads to billing. Most of its checks already exist in the read importer — what is new is running them on arrival, filling gaps, and the hand-off.

## Scope — how the set is decided

The setup panel is headed **Scope runs when a batch lands**.

| Row | Value | Control |
|---|---|---|
| Runs when | ⚡ An interval batch lands | read-only, Settings-owned (dashed) |
| Source | Meter connection · AMI head-end | read-only, Settings-owned (dashed) |
| Unit of work | Meter-day, never the interval | read-only, Settings-owned (dashed) |
| Never include | Sample | read-only, Settings-owned (dashed) |

The scope function also answers the count on the screen: **Last batch: 1,840 meters · 176,640 intervals → 1,840 meter-days.**

## Parameters

A parameter marked **Settings** is read-only here: policy lives in Settings and is never duplicated on a card (`RBR-03`, `RB-021`). Money is stored to 4 decimals and shown to 2; percentages are stored to 6 and shown to 2; rates carry 4 decimals.

| Parameter | Value on the card | Control | Read-only because it lives in Settings |
|---|---|---|---|
| High / low limits | From Settings · read validation | read-only, Settings-owned (dashed) | **Settings** |
| Rollover | From Settings · meter digits | read-only, Settings-owned (dashed) | **Settings** |
| Estimate gaps up to | From Settings · 3 days, own average | read-only, Settings-owned (dashed) | **Settings** |
| Longer gaps | Queue for a person | dropdown | — |
| Hand to billing | Validated meter-days only | read-only, Settings-owned (dashed) | **Settings** |
| Most estimates per run | 200 | input | — |
| Runs | When the batch lands | read-only, Settings-owned (dashed) | **Settings** |

## Steps

Source heading: **Steps 6 · four read, two write**. Steps run in the order shown.

| # | Step | What it does | Mode |
|---|---|---|---|
| 1 | Gather the batch and roll it up | 96 intervals become one meter-day; the run is 1,840 records, not 176,640 | `read` |
| 2 | Check high, low and rollover | The read importer's own validation stage, unchanged | `read` |
| 3 | Find the gaps | Missing intervals inside a day; meters silent all day | `read` |
| 4 | Estimate the short gaps by policy | Own 90-day average, up to the limit; longer gaps are queued | `read` |
| 5 | Write validated meter-days as reads | Through the metering service · source AMI · estimates flagged as estimates | `writes` |
| 6 | Raise exceptions as work items | Each with the meter's last good day | `writes` |

## Guards — what it may never touch

- **Read validation walks the meter-day; billing never asks about an interval** (`RBR-18`, restating `BR-RBS-019`). That is a rule, not a preference: a per-interval savepoint over 176,640 rows would be the bottleneck.
- **Never include: Sample.**
- **Only validated meter-days are handed to billing.**
- Gaps longer than the Settings limit are **queued for a person, never estimated**.
- Estimates are written flagged as estimates, source AMI, through the metering service's `write_read` port.
- **Most estimates per run: 200.**

## Produces

1,802 meter-days validated · 31 estimated · 7 queued — 5 meters silent, 1 rollover to confirm, 1 gap too long to estimate — and 1,833 meter-days handed to billing.

### The run, with the source's own figures

**Last night · 03:05 — "1,802 validated. 7 need you."**

- Tiles: **1,802** Validated · **31** Estimated · **7** Queued for you · **5** Silent meters · **1,833** Handed to billing.
- Queued · 7, showing 1–4 — Meter · Account · Issue · Last good day · Fix: WM-01128 · Riverside Apts · Silent 2 days · no intervals at all · 2 Sep · Check meter →; WM-02209 · Hale, T. · Silent 2 days · 2 Sep · Check meter →; WM-00517 · Marsh Farms · Rollover · 99,940 → 00,120 · 3 Sep · Confirm rollover →; WM-04471 · Alvarez, M. · Gap 5 days · over the 3-day limit · 30 Aug · Estimate by hand →.
- Estimated · 31, showing 1–2 — Meter · Account · Gap · Estimated from · Gal: WM-02871 · Brant, H. · 6 h · 28 intervals · 90-day average · 210; WM-03390 · Nunes, R. · 1 day · 90-day average · 640.
- Actions: ↓ Exceptions · ↓ Estimates.

Every figure above is an **illustrative fixture**, not a finance-signed number — but the tables on the screens add up to them, so moving one is still an error.

**Done looks like** (the commitment's own sentence, RB-121, status UNVERIFIED): After an interval batch lands the clerk sees "1,802 validated · 31 estimated · 7 queued · 1,833 handed to billing", each queued meter with its last good day.

## Its screens

| | Wireframe | Build sheet | Route | Code in the source document |
|---|---|---|---|---|
| Setup | `RBS-004-R21.png` | `RBS-004-R21.md` | `…/runbooks/read-validation` | `S150-R21`, figure 39 |
| Result | `RBS-006-R21.png` | `RBS-006-R21.md` | `…/runbooks/read-validation/runs/latest` | `S152-R21`, figure 40 |

They live in `04-docs/05-modules/17-runbooks/wireframes/`. **The build sheet beside each frame is the acceptance check**: the built screen must show exactly those regions in that order with that copy, at those sizes, in those states. A region missing, a control added, a word changed or a size off is a defect of kind *Screen, copy or layout*, filed with the screen code and the region number. A sheet and its frame cannot disagree — one is derived from the other; if one is wrong, both are, and the frame is the thing to fix.

> The source document numbers these screens `S150-R21` and `S152-R21`. This repository numbers them `RBS-004-R21` and `RBS-006-R21` (PO ruling 2026-09-06: *"Screens S147–S154 - this should be RBS-nnn"*). Nothing in the source documents is renamed; the codes above are how the two meet.

## Why the card reads this way

Thin on purpose. Steps 2 and 3 are the import runner's validation stage; this runbook exists to run them the moment a batch lands, fill the short gaps, and hand the result on — and to give an AMI utility one screen that says reads validated overnight.

## Design notes on the result

Handed to billing is a tile because it is the number that matters to the bill run: 1,833 meter-days it can rely on. Last good day on every exception is what a field crew needs and what a clerk deciding whether to estimate needs — the same fact serves both. Estimates are their own download and their own table because they will bill, flagged, and the utility may prefer to chase an actual read first.

## Open questions and stated absences

- **Corrected in this pass.** The queued rows did not fit *"6 silent, 1 rollover"*; it is now **5 silent, 1 rollover, 1 long gap**.
- ⚠ **THIS CARD'S OWN TWO FIGURES DISAGREE ABOUT THE INTERVAL SIZE, AND THE BUILD ASSUMES NEITHER (`CR-075` wave R′, 2026-09-07).** Step 1 says *"96 intervals become one meter-day"*, which is **fifteen-minute** data; the bullet below says reads arrive **hourly** and that fifteen-minute reads would *"quadruple every figure on this card"*. Both cannot be true of one batch, and assuming either is expensive in opposite directions: assume 96 and an hourly day reads as 75% missing; assume 24 and a quarter-day of fifteen-minute data reads as complete. **`read_validation.py` therefore MEASURES the cadence from the timestamps each meter actually sent** — the span from first to last, divided by the gaps between them — and reports `cadence_unmeasurable` for a day with one reading. **Which of the two figures is right is the card author's to settle**, and it does not block: the build is correct under both.
- **An assumption the source relies on and never states:** interval reads arrive **hourly**. Fifteen-minute reads quadruple every figure on this card, and the sizing table assumes hourly (`RB-046`). ⚠ See the clause immediately above — this is one half of a contradiction, not a settled fact.
- `RB-042` — which this runbook waits on — is the *exception rows, counts for the clean* rule (`BR-RBS-035`): a volume runbook keeps a record row for anything acted on or flagged, and a count per outcome for the rest.

---

Source: the Runbooks definitions document (*Twenty-One Runbooks*, restructured 5 September 2026; build sheets added 6 September 2026) and the Runbooks specification, section B2b. Every figure here is the source's own; nothing has been added, and where the source is silent this file says so. Status of **RB-121: UNVERIFIED** — engineering fills that in from the code, and a test that was first shown failing is what moves it.
