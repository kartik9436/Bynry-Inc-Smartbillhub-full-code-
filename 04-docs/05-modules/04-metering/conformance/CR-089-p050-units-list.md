# U1 · The units list — THE DRAWN SPEC

`S15 · PRM-01U` — **state chip: `EXISTS BEHIND`**
Blueprint *Premises & Units Blueprint 2*, **page 50** (part-two opener and the
chip line) → **page 51** (screen head, amber block, the grey frame's head and
first row) → **page 52** (the frame's remaining rows, footer, teal *WHAT
CHANGED*) → **page 53** (the detail table: primary action, cognitive load,
states, components, rules).

**Commitment chips on the chip line (page 50):** `PUJ-22` · `PUJ-50`.
**CR-089 task rows this screen belongs to:** `E1` (*the units list is scanned by
address and carries money*, `PUJ-22`) and `E2` (*a building's address finds its
units*, `PUJ-50`).

> **This file records the GREY FRAME only.** The amber block on page 51 is what
> a clerk hits TODAY — *"the columns are `Select · Unit ID · Premise · Unit ·
> Type · Services · Meters · Occupant / Account · Status · Actions`"* — and that
> is the PROBLEM STATEMENT, never the target. The teal *WHAT CHANGED* block on
> page 52 is the argument. Neither is the specification. Where the teal block or
> a commitment sentence disagrees with the frame, **the frame wins** (PO ruling
> 2026-09-10); the disagreements found here are recorded at the foot of this
> file and not resolved by picking.

**Section opener (page 50), verbatim:** *"04 · Part two · a unit — A unit is
what actually takes service — it holds the meters and everything else of ours,
the plan and the account. A property with no units bills nothing at all. These
screens are the same five acts as part one, for the smaller thing: find, create,
read, change, retire."*

**Breadcrumb drawn above the frame:** `Premises → Units`
**The question the screen answers:** *which flat is this, and is anything owed
on it?*

---

## 1 · Header

| slot | drawn string |
|---|---|
| kicker | `PREMISES & UNITS` |
| title (H1) | `Units` |
| subtitle | `Every unit that can take service, across every property.` |

**No roll-up sentence is drawn.** The line under the title is the subtitle above
and nothing else. The subtitle sits **between the title and the tab strip**, not
below it.

## 2 · Header actions — in the order drawn, left to right

| # | label | tier |
|---|---|---|
| 1 | `↑ Import` | secondary — outlined |
| 2 | `+ New unit` | **primary** — one filled button |

**Primary action, verbatim (page 53):** *"`+ New unit`, which asks for the
building first."*

## 3 · Tabs — three, in this order, `Units` active

`Premises` | `Units` | `Imports`

**Page 53, *WHAT CHANGED · ONE TAB ROW*, verbatim:** *"An earlier draft of this
page drew the unit's six tabs — Overview, Meters, Plan, Account, Occupancy,
audit log — above the list's own three. They belong to one unit and there is no
unit here yet. Only `Premises · Units · Imports` remains."*

## 4 · Tiles

**None.** No stat tiles, no KPI strip. A stated absence — see §10.

## 5 · Toolbar — one row, in the order drawn

| # | element | drawn text |
|---|---|---|
| 1 | search input (left) | placeholder `Search units by address, unit or occupant…` |
| 2 | chip | `ALL` |
| 3 | filter control | `+ Filter ⌄` |
| 4 | column chooser (right-aligned, alone) | `▦ Columns` |

## 6 · Table columns — NINE, in this order

| # | drawn header | alignment | what the cell draws |
|---|---|---|---|
| 1 | `Unit ⇅` | left | **ONE cell, two lines** — the label leads in the strong tone (`1`, `4`, `Laundry`), the unit number beneath it, quiet (`U-01144`, `U-01147`, `U-01148`). Sortable, and **the default sort is the LABEL** |
| 2 | `Address ⇅` | left | **ONE cell, two lines** — street on the first line, strong (`412 Cypress Row`); town, state and postcode beneath, muted (`Silver Creek, TX 78611`). Sortable |
| 3 | `Type` | left | `Residential` · `Common area` |
| 4 | `Services` | left | letter squares — `E W` |
| 5 | `Meters` | left | **a COUNT** — `2`; `none` in the muted italic absence style where there are none |
| 6 | `Occupant` | left | a **name and its account** — `M. Alvarez` then `A-10517` quiet; `Creekside Holdings` then `A-10442`. On a vacant unit it reads `Vacant — base charges bill to the owner`, muted italic, **as the cell's visible text** |
| 7 | `Owed` | **right, tabular** | `61.40` · `0.00` · `34.90` — two decimals, no currency glyph on the rows |
| 8 | `Status` | left | pill: `OCCUPIED` · `VACANT` · `ACTIVE` |
| 9 | *(no header)* | right | row actions as icons — **eye · pencil · `…`**, three and no more |

**Nine columns** — page 53's own count, and the actions column is the ninth.

**There is NO `Select` checkbox column in the frame.** `Select` appears only in
the amber block, as the first of the columns a clerk hits today.

**Column 1's number is not a database id and the blueprint says so** (page 53
RULES): *"A printed reference from the tenant's own series is shown; a database
id never is."* `U-01144` is `unit_no`, off the tenant's own series.

**Column 6 replaces the old `Occupant / Account` header** with the single word
`Occupant`. The account is still in the cell, quiet, beneath the name.

**A vacant row never draws a dash in the occupant cell** — *"A vacant unit says
what that costs instead of showing a dash."* The vacant row still draws `0.00`
in `Owed`.

**Common areas are rows in this list, marked as such** — *"Common areas appear
in the list, marked as such, because they are units and they are billed."* The
`Laundry` row's `Type` reads `Common area`.

## 7 · Footer

Left: `Showing 1–50 of 1,109 · Rows per page 50`
Right: `⇤` `←` `Page 1 of 23` `→` `⇥`

## 8 · States — the frame's own STATES block, verbatim

| state | drawn behaviour |
|---|---|
| **Nothing yet** | *"Says a property must exist first, and links to the property list."* |
| **Filtered to vacant** | *"The footer count is the size of the job, and every row carries the owner-billing sentence."* |

Loading, error and permission-refusal states are **not drawn**.

## 9 · Components named by the drawing

`DataTable` · `FilterBar` · `RowActions` · `StatusPill` · `MoneyCell` ·
`MoveUnitModal` · `InlineLinkTo`

## 10 · Cognitive-load budget, as stated

*"Nine columns, one search, no prose."* — no explainer paragraph, no callout,
no hint line, no audit sentence anywhere on this list.

## 11 · Rules it must obey, verbatim

*"A printed reference from the tenant's own series is shown; a database id never
is. Money right-aligned, two decimals, tabular. A pagination footer on every
list. Search placeholders name what is searched."*

## 12 · Absences — drawn as absent, do not fill them

* No `Select` column and no bulk-action bar.
* No `Plan` column and no `Floor` column.
* No stat tiles and no roll-up sentence.
* No prose of any kind — see §10.
* No `Premise` column of its own; the property number is not drawn at all on
  this list (see contradiction 2 below).

---

## Contradictions inside the source, recorded rather than resolved

1. **What sits beneath the address.** The frame (page 51) draws the address cell
   as street over **town, state and postcode**. The teal block (page 52) says
   only *"the address is a column, not a code — `Premise` showed a property
   reference a clerk would have to look up first"*, which argues the code away
   without saying where it goes. **The frame draws no `P-00080` anywhere on this
   list.** Recorded, not resolved.
2. **`Meters` is a count here and a service list on the property's own Units
   tab.** This frame draws `2` / `none`; `CR-089-p022`'s frame draws `E · W` in
   the same-named column. Both are in the same document. Recorded.
3. **The search placeholder names a leg the frame's own columns do not.** The
   box reads `Search units by address, unit or occupant…`; the frame's RULES row
   says *"search placeholders name what is searched"*. Whether the server
   matches an occupant is a question this file cannot answer from the drawing —
   see the diff note below.

---

## AMENDMENTS — what was BUILT on 2026-09-10 (`DEF-MET-4771` · `DEF-MET-4773`)

**What moved to match the frame:** column 1 is `Unit` and column 2 is `Address`,
which is the frame's own order · `Occupant / Account` becomes **`Occupant`** ·
the vacancy sentence is the cell's **visible text** and no longer a `title=`
attribute · `Meters` is a **count** · `Type` reads `Common area` off
`is_common_area` rather than the legacy typing · the five row-action glyphs
become the drawn **eye · pencil · `…`**, with the four that moved reachable
inside the overflow · the empty state says a property must exist first and opens
the property list · the default sort is the **label**.

### ⚠ `Owed` ON A VACANT ROW — `Not measured`, BY THE SAME PO RULING

The frame draws `0.00` on the vacant row. `CR-089-p022`'s amendment records the
PO's ruling of 2026-09-10 on the property's Units tab: the vacancy sentence
moves to `Occupant` and `Owed` shows `0.00` — *"but keep the existing
protection: show `0.00` only when the balance really is zero, never manufactured
over a real debt."* A unit with **no occupying account** produced no ledger read
at all, so this list draws **`Not measured`** there, exactly as the property tab
does. This is the ruling applied, not a second decision.

### ⚠ THE COLUMN ORDER REVERSES A SHIPPED CHANGE, ON PURPOSE

`CR-089` wave E read `E1`'s task sentence — *"the units list is scanned by
address"* — and shipped `Address` first on 2026-09-09. The frame (page 51) draws
`Unit ⇅` first, and this file's own preamble rules the tie: *"Where the teal
block or a commitment sentence disagrees with the frame, the frame wins"* (PO
2026-09-10). What wave E actually fixed is untouched — the SERIES NUMBER no
longer leads either column.

### Departures, recorded rather than left to be found

1. **THE `Select` COLUMN AND THE BULK BAR STAY.** §12 lists both among the drawn
   absences. `BR-MET-041` is a SIGNED rule requiring bulk plan assignment and
   this checkbox is the only control that reaches it, so removing the column
   would cut a ratified capability to match a drawing. **That is the Product
   Owner's call, not this lane's. Open.**
2. **THE ADDRESS CELL STILL PRINTS THE PREMISE NUMBER BENEATH THE STREET.** The
   frame draws town, state and postcode there; contradiction 1 above records
   that the source does not resolve where the property code goes, and
   `unit_list_dict` serves no locality for a unit. Unchanged, and unresolved.
3. **THE EXPORT BUTTON IS NOT IN THE FRAME AND IS KEPT.** §5 draws four toolbar
   elements and no export. `US-MET-002`'s capability row declares CSV export and
   it works; removing a working door is a loss the drawing did not ask for.
4. **THE `…` OVERFLOW IS A NEW KIT COMPONENT** (`RowActionsMore` /
   `RowMenuAction` in `components/RowActions.tsx`). B14 rule 15 has ended *"Max
   2 visible, then `…`"* since it was written and the product had no `…` at all,
   so the second half of a ratified rule was unenforceable. Inside the opened
   menu each action carries its WORD beside its glyph — an icon-only menu is a
   puzzle, and every menu in r10 is words.

---

## AMENDMENT — 2026-09-25 · THE SERVICE GAP REPORT JOINS THE TAB (`DEF-MET-6796`)

**A panel that is NOT on the frame is now on the screen, and this records it.**

`BR-MET-119` as amended 2026-09-25 makes a unit's service set *within* its
address's offer rather than equal to it, so a shortfall is a LAWFUL state. It is
therefore counted rather than refused. `BR-BIL-300` is why counting it matters:
service points decide what a bill charges, so every row is a service the address
advertises and nobody is billed for.

**What it draws.** `UnitServiceGaps` — a `Panel` above the units table, headed
with the count, listing the short units with what the address offers and what is
missing, server-paged (`GET /units/service-gaps`, `NFR-3`; no cap, `NFR-5`).

**Two judgments the drawing does not speak to, recorded rather than assumed:**

1. **IT DRAWS NOTHING WHEN NOTHING IS SHORT.** A panel reading *Nothing missing*
   every day is furniture on a screen a utility opens all day, and B14 rule 32
   gives a screen a description budget. The cost is stated rather than hidden: a
   clerk cannot confirm a zero from this panel. The units list's own `Services`
   column is what answers *what does this unit have* when nothing is short.
2. **IT IS A SECOND TABLE, NOT A CHIP ON THE FIRST.** The rows carry two facts
   the units list has no column for — what the address OFFERS, and what is
   MISSING — and folding them into `DataTable`'s `UnitRow` would give one table
   two row shapes. `PlainTable` + `ListPager` is the kit's own answer for a list
   that is not the shared table.

**It is scoped to the same premise the table below is scoped to**, so the two
always answer about one set.


### AMENDED 2026-09-26 — it arrives CLOSED (`DEF-MET-6815`)

Judgment 2 above said the report is a second table. It still is, and it is now
**collapsed by default**, because the first build drew it inline and that was
wrong in a way only a browser could show.

**MEASURED, Chromium at 1440, seeded utility, 44 of 131 units short:** the panel
was **2,650px tall and the units table began at y=3054**. A clerk opening Units
to find a flat met a whole exception report first. Every jsdom case passed,
because a count is a count whether it is drawn in 40px or in 2,650 — hard-won
law 6, exactly.

It is a `Disclosure` now — `Missing services · 44 units · Expand ▾` on one line,
between the bulk bar and the table's toolbar. `Disclosure` unmounts its body, so
the rows are not built while it is closed; the read still runs, because the
heading needs the count.

⚠ **THE HEADING ALSO BROKE B14 RULE 33.** *"Short of the address (44)"* is four
words plus a bracketed number against a cap of three for a heading. It is
`Missing services`, with the count in `Disclosure`'s own `value` slot.

⚠ **`Offered here` AND `Missing` SHOW THE SAME BADGES ON THE DEMO DATA, AND THAT
IS THE TRUTH RATHER THAN A FAULT.** All 44 short units on that utility hold
**zero** service points, so everything offered is missing. The two columns
diverge as soon as a unit holds one of the two, which is the case `T4` asserts
by name.

---

## SUPERSEDED 2026-09-28 — THE PANEL IS DELETED AND BECOMES A FILTER ON THE LIST

⚠ **EVERYTHING ABOVE UNDER *"THE SERVICE GAP REPORT JOINS THE TAB"* DESCRIBES A
PANEL THAT NO LONGER EXISTS.** It is kept rather than rewritten because the two
judgments it records are what the PO ruled against, and a lane that meets only
the outcome cannot tell whether the panel was a mistake or a step.

**PO ruling 2026-09-28, verbatim:** *"the Units "Missing services" block —
filter or leave it. - filter"*, raised by them as *"why this is build - missing
services - it would ahve been a filer criteria and I can filter th units based
on this"*. Decision log, same date.

**WHY, AND IT IS NOT AESTHETIC.** A section cannot compose. The 60 short units
appeared TWICE — once in the panel, once in the list below — and in the panel a
clerk could combine them with neither the search nor the four filters, could
not page them with the list, and **could not select them for a bulk action**.
That last one is the strongest: the gap is a thing to FIX, and the panel was
the one place in the product where those exact units could not be acted on
together.

**WHAT IS ON THE SCREEN NOW**

| | |
|---|---|
| The panel | **DELETED**, not hidden — `UnitServiceGaps.tsx` and its dom test are gone |
| Its pager | Gone. The units list's own footer pages the filtered set |
| `GET /units/service-gaps` | **RETIRED.** `?f.missing_services=yes` on `GET /units` |
| The filter | Declared with the four already there, in the `+ Filter ▾` panel, a removable chip, `f.missing_services` in the URL |
| The count | `service_gap_count` on the units envelope, drawn on the toolbar as a `ChipToggle` **whether or not the filter is engaged** |
| `Offered here` | A column, declared **hidden by default** — see below |
| `Missing` | A column, **visible by default** |

⚠ **THE COUNT IS THE DELIVERABLE, NOT THE FILTER CONTROL.** `DEF-MET-6796`
exists because the shortfall was INVISIBLE, and a filter nobody switches on is
invisible in exactly the same way. That is why the figure sits on the toolbar
where the eye lands rather than inside a panel that is closed by default, and
why it rides the list's own envelope instead of a second request the screen
would have to remember to make.

### THE ONE DIVERGENCE, RECORDED RATHER THAN TAKEN SILENTLY

**`Offered here` DRAWS THE SAME VALUES AS THE DRAWN `Services` COLUMN.**
`row.services` is what the ADDRESS offers (`DEF-755`), which is exactly what
*Offered here* meant inside the panel. So the ratified column and the drawn
column are one fact:

* the PO ratified `Offered here` **by name**, so it is DECLARED — a lane is not
  where that gets reversed;
* a second column drawn BY DEFAULT would put one fact twice on a row that
  already carries ten (B14 rule 32) and would add a column the `U1` frame
  (pages 50–52) does not draw (rule 41);
* so it is declared **`defaultVisible: false`** and offered in the column
  chooser, which is what *"show/hide like any other"* asks for.

**This is the one thing on this change that is put back to the PO**, in plain
English: *the Services column already shows what the address offers, so Offered
here is the same list under a second name — is one column enough?*

### WHAT STILL HOLDS FROM THE AMENDMENTS ABOVE

* **`Missing` is empty on a whole unit and draws a quiet dash.** It must NOT
  read *"No services"* — that is `ServiceTags`' sentence for an address that
  offers nothing, which is the right sentence on the `Services` column and the
  opposite of the truth here.
* **A deleted unit is not a shortfall.** The exclusion rides inside the filter
  branch rather than on the list, so the number a clerk reads is the same
  number the retired panel printed while the list itself still shows inactive
  units.
* **`Offered here` and `Missing` show the same badges on the demo data**, and
  that is the truth rather than a fault: every short unit on that utility holds
  zero service points, so everything offered is missing.
