# Step 3 · Units — THE ABSORBED-FIELD AUDIT, BOTH DIRECTIONS

**Why this file exists, in the Product Owner's own words:** *"we dont want any
information to be reduced or lost - 8 steps → 5"* (2026-09-28, `CR-150-BRC09`,
decision log answer 1).

Two whole steps fold into step 3 — **Map services** (old step 4,
`NewConnectServicesStep.tsx`) and **Work orders** (old step 5,
`NewConnectPlansStep.tsx`) — **and their step ids are gone**. There is no longer a
screen anywhere else that could hold one of their fields, so a field missed here is
a field the product loses. This audit was written **before** the build and the
right-hand column was filled in **after** it, which is the only order in which it
proves anything.

⚠ **A FIELD WITH NOWHERE TO GO IS SAID SO EXPLICITLY** rather than left off the
list. Two are, and both are named below.

---

## A · OLD STEP 4 · MAP SERVICES — every field it held

| # | What the old step held | Where it is now |
|---|---|---|
| A1 | **Services available at this premise** — the tick list over the tenant's enabled services (`ServiceTicks`, writes `draft.premiseServices`) | **Step 2 · Premise**, as one multi-select (`ServicesAvailableField`), by PO ruling — decision log answer 12, *"this should be… dropdown"*. It was ALREADY asked twice; step 3 now asks it zero times |
| A2 | The `{{count}} of {{total}} available at this address` count | **Step 3, KPI tile `Services here`** — `4 of 4` on the drawing |
| A3 | `servicesLoading` / `servicesFailed` states of that read | **Step 2**, with A1. Step 3's tile states its own absence when the tenant read has not answered |
| A4 | **Count · Service points** | **Step 3, KPI tile `Service points`** |
| A5 | **Count · Meters to fit** | **Step 3, KPI tile `Meters to fit`** |
| A6 | **Count · Work orders** | **Step 3, KPI tile `Work orders`** — *"N will be written"* |
| A7 | Shortcut · the `Service` picker beside the three buttons | **GONE, AND DELIBERATELY** — superseded by the drawn **Common selection**, which sets every service at once instead of one column at a time. Recorded as removed, not lost: the capability it gave is a strict subset of *Apply to all* |
| A8 | Shortcut · `Tick a column` | **GONE**, superseded as A7 |
| A9 | Shortcut · `Clear a column` | **GONE**, superseded as A7 |
| A10 | Shortcut · `Copy unit 1 to all` | **GONE**, superseded as A7 — *Apply to all* is the drawn replacement and does strictly more |
| A11 | Grid column **Unit** | **Units table, column `Unit`** — now the group heading plus an editable first-row cell |
| A12 | Grid column **Utility service** (tick + name) | **Units table, column `Service`** (the PO's short name). The TICK is gone and the row itself is the answer: a service not taken is a row a clerk removes with `✕`, which is what `+ Add row` is the other half of |
| A13 | `UnitServiceCell.taken` | **Still written.** Removing a row writes `taken: false`; adding one writes `taken: true`. The field is unchanged; only the control moved |
| A14 | Grid column **Asset type** | **Units table, column `Asset`** |
| A15 | Grid column **Size** | **Units table, column `Size`** |
| A16 | Grid column **Work order** | **Units table, column `Work order`** — now a searchable cell, per the drawing |
| A17 | Grid column **Occupancy** | **Units table, column `Occupancy`**, and in the Common selection. PO: *"why dont you keep this with units itself"* |
| A18 | Refusal · *"{unit} takes {service}. This address does not."* | **Units table, as the GROUP's error**, under that unit's heading — the drawing shows it exactly there |
| A19 | Refusal · *"{unit} takes sewer, not water. Sewer follows water."* | **Units table, as the group's error**, same slot |
| A20 | Note · *"No service is ticked above."* | **GONE.** It described A1, which is no longer on this step. The table's own empty state replaces it |

## B · OLD STEP 5 · WORK ORDERS — every field it held

| # | What the old step held | Where it is now |
|---|---|---|
| B1 | Refusal · *"Work orders could not be loaded…"* | **Step 3**, over the units table, unchanged |
| B2 | Empty state · *"No template covers these services."* | **Step 3**, under the units table — the drawing names this sentence in as many words |
| B3 | Empty state · the `Write a template` link | **Step 3**, beside B2 — the drawing names it too |
| B4 | Proposed order · **name** | **Units table, `Work order` cell** — the template's name is the option's label. `BR-WRK-008`, and B14 rule 31 keeps the id out of sight |
| B5 | Proposed order · **service** beside the name | **The row's own `Service` cell.** The order sits ON the service row, so the service is no longer a suffix on a name |
| B6 | Proposed order · the **`Completes service`** pill (`is_gate`) | **Units table, column `Completes`** — the drawn tick box. **Read-only, with its reason**: `BR-WRK-013` makes it the template's own flag, never a clerk's |
| B7 | Proposed order · **Remove** | **The row's `✕`** (B14 rule 15 — a row action is an icon) |
| B8 | Count · *"{{count}} orders will be written."* | **KPI tile `Work orders`** — A6 |
| B9 | **Add a work order** — the published-template picker | **`+ Add work order`**, which adds a row in place with a template search (`step3b-add-work-order.png`). Published only, version > 0, as before |
| B10 | Refusal · *"Templates could not be loaded…"* | **Step 3**, on the added row's search |
| B11 | **Target activation date** | **Step 3 · Common selection**, top right — the drawing puts it there |
| B12 | `draft.removedWorkOrderTemplateIds` | **Unchanged.** Written by the row `✕` on a whole-build order |
| B13 | `draft.addedWorkOrders` | **Unchanged.** Written by `+ Add work order` |

## C · WHAT STEP 3 ITSELF ALREADY HELD, AND KEEPS

`Units from` · `To` · `Include a common-area unit` · the disabled `Upload a unit
schedule` with its reason · the duplicate-label refusal and its per-row mark ·
`Kind` · `Occupancy`. All present.

---

## D · THE TWO THINGS THAT ARE **NOT** BUILT, SAID PLAINLY

**D1 · `Qty` IS DRAWN AND IS NOT BUILT.** `OQ-CUS-12770` is **OPEN** and it is the
only one of nineteen questions the Product Owner did not answer. It asks whether a
charge's quantity is typed per line or counted, **and it multiplies a price on a
real invoice**. `CR-150-BRC09` §5 says in terms: *"the Qty column is drawn and not
built until the PO rules"*. The column is therefore **absent** rather than present
and inert — a cell showing a figure nothing reads is the shape this repo files most
often. **Nothing from Map services or Work orders is lost by its absence: neither
step had a quantity at all.**

**D2 · THE DRAWN *COMPLETES* TICK DOES NOT TAKE A CLERK'S ANSWER.** It shows
`is_gate`, which `BR-WRK-013` makes the template's own. It is rendered as the drawn
tick box, disabled, carrying its reason (`BR-SHL-025`). The old step showed the same
fact as a pill, so nothing is lost; what is refused is a NEW power the drawing could
be read as offering.

---

## E · DIVERGENCES FROM THE DRAWING, STAMPED HERE RATHER THAN LEFT SILENT

| # | The drawing | What was built, and why |
|---|---|---|
| E1 | `step3a-add-row.png` and `step3b-add-work-order.png` are titled *"…after Add row"* / *"…after Add work order"* and were commissioned as *"screens"* | **NEITHER IS A DIALOG**, and both drawings say so themselves — *"Nothing opens on top of the screen"* and *"Also in place, at the bottom of the table."* Decision log answer 13(e) rules it: *"neither opens a dialog: the row is added in place"*. Built in place |
| E2 | Both drawings ring the new row in red | **NOT BUILT.** Both frames are explainers titled *"The new row"* and the outline points at the row the prose is about. `TableArray`'s own exception E1 already states this for the kit |
| E3 | `Qty` column with a `NEW` badge | **NOT BUILT** — D1 |
| E4 | The prose under *Apply to all*, under the table, and the *Occupancy options: …* line | **NOT BUILT.** Every one is RATIONALE — *why* the product works this way — which B14 rule 33 gives **zero words on screen**. *"Required before Continue. Rows stay editable."* is an INSTRUCTION and IS built |
| E5 | Units 2 and 15 are drawn folded, unit 1 open | Built: the **first group is open and the rest are folded**, each toggleable. The drawn resting state, with every row reachable |
| E6 | The figures — 4 of 4, 12, 3, 4, `Water 1"`, `10/15/2026`, units 1, 2, 15 | **ILLUSTRATIONS** (B14 rule 37). Every count on the built screen is computed from the rows |

---

*Written 2026-09-29 by the step-3 lane of `CR-150-BRC09`. Section A and B's
left-hand columns were read out of `NewConnectServicesStep.tsx` and
`NewConnectPlansStep.tsx` at commit `dd1cda9c0`, before any code was written.*
