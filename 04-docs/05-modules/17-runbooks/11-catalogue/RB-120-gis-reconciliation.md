# RB-120 — Runbook 20 · GIS reconciliation

## What it declares

| | |
|---|---|
| **Kind** | Action |
| **Category** (one home, from the fixed list of sixteen) | Data Sync |
| **Tags** | Service points |
| **Phase** | 3 |
| **Trigger** | ⚡ `batch.landed` — a parcel batch lands. The trigger is its arrival, not a clock. |
| **Subject and unit of work** | Parcel ↔ premise |
| **Step modes** | per record |
| **Result blocks it composes** | KPIs · Breakdown · Records · Row decisions · Downloads |
| **Ports it holds** | `apply_premise_change` (metering) |
| **Proves** | US-RBS-032 |
| **Waits on** | RB-022 (parcels landed) · a GIS connection |

## What it does

Does: takes the parcels the GIS connection landed overnight, compares each to our premises, classifies every difference, and disposes of it the way the utility has chosen per field — apply automatically, queue for a person, or never touch. Scope is the landed batch; the trigger is its arrival, not a clock.

## Scope — how the set is decided

The setup panel is headed **Scope runs when a batch lands**.

| Row | Value | Control |
|---|---|---|
| Runs when | ⚡ A parcel batch lands | read-only, Settings-owned (dashed) |
| Source | GIS connection · County parcels | read-only, Settings-owned (dashed) |
| Compare to | Premises with a parcel id | read-only, Settings-owned (dashed) |
| Never include | Sample | read-only, Settings-owned (dashed) |

The scope function also answers the count on the screen: **Last batch: 69,140 parcels · 2,862 matched to a premise.**

## Parameters

A parameter marked **Settings** is read-only here: policy lives in Settings and is never duplicated on a card (`RBR-03`, `RB-021`). Money is stored to 4 decimals and shown to 2; percentages are stored to 6 and shown to 2; rates carry 4 decimals.

| Parameter | Value on the card | Control | Read-only because it lives in Settings |
|---|---|---|---|
| Match on | Parcel id, then standardised address | dropdown | — |
| Apply automatically | Postal code · Lot area · Zoning | dropdown | — |
| Queue for a person | Address line · Owner name · Premise type | dropdown | — |
| Never touch | Inside city limits · City · State | read-only, Settings-owned (dashed) | **Settings** |
| Create premises we do not have | off | toggle | — |
| Most changes per run | 500 | input | — |
| Runs | When the batch lands | read-only, Settings-owned (dashed) | **Settings** |

## Steps

Source heading: **Steps 7 · five read, two write**. Steps run in the order shown.

| # | Step | What it does | Mode |
|---|---|---|---|
| 1 | Gather the landed batch | From the GIS connection, once, pinned to this run | `read` |
| 2 | Match parcels to premises | By parcel id, then by standardised address | `read` |
| 3 | Classify each difference | New value · blank here · blank there · conflict · two premises one parcel · one premise two parcels · unmatched | `read` |
| 4 | Look up the disposition per field | Auto · queue · never — the utility's own table above | `read` |
| 5 | Check the cap and the guards | Never-touch fields are skipped whatever the class says | `read` |
| 6 | Apply the automatic changes | Through the metering service · one per premise · before-and-after kept | `writes` |
| 7 | Raise the rest as work items | Both values shown, so a person decides in one look | `writes` |

## Guards — what it may never touch

- **Never touch: Inside city limits · City · State.** *Never touch* is a Guard by another name, and it is **fixed on the money-path fields and cannot be widened by a tenant** (`RBR-17`, restating the integration substrate's C25).
- Never-touch fields are skipped **whatever the difference class says** (step 5).
- **Never include: Sample.**
- **Most changes per run: 500** — a cap never truncates; it refuses (`RB-004`, `TC-RBS-3`).
- Changes go through the metering service, through `apply_premise_change`, one per premise, with before-and-after kept.
- **Creating premises from unmatched parcels is off by default.**

## Produces

1,268 differences · 980 applied automatically · 218 queued for a person · 70 never touched, listed.

### The run, with the source's own figures

**Last night · 02:14 — "980 applied. 218 need you."**

- Tiles: **980** Applied · **218** Queued for you · **70** Never touched · **41** Parcels unmatched · **3** Two premises, one parcel.
- By difference class — Class · Count · Disposition · What happened: New value where we had one · 742 · Auto · Queue by field · 611 applied · 131 queued; Blank here, value there · 369 · Auto · Queue by field · 369 applied; Blank there, value here · 58 · Never · Ours kept · listed; Conflict on a field queued by disposition · 83 · Queue · Ours and theirs shown; a person decides; Conflict on a never-touch field · 12 · Never · Listed, nothing changed; Two premises share one parcel · 3 · Queue · A person decides; One premise on two parcels · 1 · Queue · A person decides; Parcel with no premise · 41 · Off — create is disabled · Listed only.
- Queued for a person · 218, showing 1–3 — Premise · Field · Ours · Theirs · Class · Decide: 14 Cedar St · Owner name · M. Alvarez · Alvarez Family Trust · New value · Accept theirs → · Keep ours; 2 Mill Rd · Premise type · Residential · Mixed use · New value · Accept theirs → · Keep ours; Lot 14, Ridge Ln · Parcel · — · Shared with Lot 15 · Two premises, one parcel · Open both →.
- Actions: ↓ Applied · ↓ Queued.

Every figure above is an **illustrative fixture**, not a finance-signed number — but the tables on the screens add up to them, so moving one is still an error.

**Done looks like** (the commitment's own sentence, RB-120, status **BUILT — VERIFIED-UNRATIFIED**): After a parcel batch lands the clerk sees "980 applied · 218 need you · 12 never touched", the by-class table, and Ours · Theirs on every queued row with Accept theirs → · Keep ours.

### What engineering built, and where it differs — `CR-075` wave Q′, 2026-09-06

`06-backend/apps/runbooks/definitions/gis_reconciliation.py`, seven steps, walked in Chromium. On the seeded
utility, over nine county parcels against six premises, the screen reads **"2 to apply. 5 need you."** with
tiles **2 · 5 · 1 never touched · 2 parcels unmatched · 0 two-premises-one-parcel**, the by-class table, and
**Ours · Theirs** on every queued row with **Accept theirs →** and **Keep ours** as real buttons.

⚠ **NOTHING IS CHANGED.** `apply_premise_change` IS bound (`CR-075` task `L2`) and
`engine.acts.LIVE_ENABLED_RUNBOOKS` is empty for the whole catalogue, so every port is handed writer-less and
the port's own refusal is the outcome. The tile therefore says **To apply**, not *Applied*.

**Five stamped divergences**, each with its reason in the module's own docstring:

1. **The trigger is manual and schedule, not ⚡ `batch.landed`.** That event is emitted by nothing — zero
   occurrences in the backend — and it is `CR-069`'s work, scoped to nobody.
2. **`gis_city`'s `reconcile_parcels` is STUBBED, so even a connected tenant has no batch.** Under
   `BR-INT-054` as amended 2026-09-06 that is integrations' half. The **second door** is therefore a parcel
   file a person uploaded — an `import_runs` row for `premises` at `validated`, staged and never loaded — and
   the run stops only when both doors are shut.
3. ***Lot area* and *Zoning* are columns this product does not hold**, here or in B2. They are counted and
   named in the run's own `fields_the_product_does_not_hold` rather than dropped. **And a column the FILE does
   not carry is not a blank either** — comparing an unmapped field would report *blank there* on every
   property in the estate.
4. **`Most changes per run` is not a parameter** — the cap is `runbooks.cap`, one policy with one home
   (`RBR-03`). Step 5 READS it and STOPS when the automatic changes exceed it (`BR-RBS-006`).
5. **Only FIELD differences reach the queued-decision table.** *Accept theirs → · Keep ours* is a choice
   between two named values, and there are none on *two premises share one parcel* — whose card row carries
   *Open both →*. Those are drawn in Records with their own fix route.

**Three stops, each its own sentence:** *"Nothing to compare."* (both doors shut) · *"Nothing has landed
yet."* (a connection, no batch) · *"That parcel file is not here."* (a batch named and gone). Every one draws
one red chain cell, six reading **Never reached**, a WHAT TO DO box, and **no KPI strip** — a strip of noughts
over a run that examined nothing reads exactly like a morning the county agreed with us about everything.

## Its screens

| | Wireframe | Build sheet | Route | Code in the source document |
|---|---|---|---|---|
| Setup | `RBS-004-R20.png` | `RBS-004-R20.md` | `…/runbooks/gis-reconciliation` | `S150-R20`, figure 37 |
| Result | `RBS-006-R20.png` | `RBS-006-R20.md` | `…/runbooks/gis-reconciliation/runs/latest` | `S152-R20`, figure 38 |

They live in `04-docs/05-modules/17-runbooks/wireframes/`. **The build sheet beside each frame is the acceptance check**: the built screen must show exactly those regions in that order with that copy, at those sizes, in those states. A region missing, a control added, a word changed or a size off is a defect of kind *Screen, copy or layout*, filed with the screen code and the region number. A sheet and its frame cannot disagree — one is derived from the other; if one is wrong, both are, and the frame is the thing to fix.

> The source document numbers these screens `S150-R20` and `S152-R20`. This repository numbers them `RBS-004-R20` and `RBS-006-R20` (PO ruling 2026-09-06: *"Screens S147–S154 - this should be RBS-nnn"*). Nothing in the source documents is renamed; the codes above are how the two meet.

## Design notes on the result

The by-class table is the audit: every one of the 1,268 differences is in exactly one row, and the disposition column says what the utility's own settings did with it. Ours · Theirs side by side on every queued row is the whole decision — a person accepts or keeps in one look. The 12 never-touch conflicts are listed, not hidden: a county disagreeing with us about a city boundary is worth knowing even when we refuse to change it.

## Open questions and stated absences

- **Creating premises from unmatched parcels is off by default.** Closed *OUT OF SCOPE as a default* — the toggle exists and a tenant may switch it on.
- **Corrected in this pass.** The difference classes summed to 1,226 against tiles of 1,210; both now agree at **1,268** with a class row that was missing (the 83 conflicts on a field queued by disposition). *Never touched* was corrected from 12 to **70**; the commitment sentence still reads *"12 never touched"*, which is the twelve never-touch **conflicts**.
- **The overlap this runbook resolves.** The integration specification designs difference classes, per-field dispositions and an approval queue for GIS *inside integrations*. That is a runbook — check, guard, gate, work list — and it is built once, here, with the integration spec as its rules.

---

Source: the Runbooks definitions document (*Twenty-One Runbooks*, restructured 5 September 2026; build sheets added 6 September 2026) and the Runbooks specification, section B2b. Every figure here is the source's own; nothing has been added, and where the source is silent this file says so. Status of **RB-120: BUILT, VERIFIED-UNRATIFIED** (`CR-075` wave Q′, 2026-09-06) — 33 cases in `06-backend/tests/test_us_rbs_032_gis_reconciliation.py` plus its share of the 12 PostgreSQL cases in `test_rbs_sync_runbooks_pg.py`, four of them first shown failing on the specific wrong build they were written for. The figures above are the SOURCE's illustrative fixture and are not what the seeded utility produces; what it produces is in the section above and in `12-governance/02-decision-log.md`.
