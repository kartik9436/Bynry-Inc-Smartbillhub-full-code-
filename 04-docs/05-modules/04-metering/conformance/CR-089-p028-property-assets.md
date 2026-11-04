# P7 · Property → Assets — THE DRAWN SPECIFICATION

**Source:** *Premises & Units Blueprint 2*, **pages 28–32**. The screen section
opens on page 28; the grey frame runs pages 28–30; *WHAT CHANGED* runs pages
30–31; the specification table and the states run pages 31–32.

**Screen id:** `PRM-02` — Premises → a premise → Assets
**State chip:** `EXISTS BEHIND` · `COMMITMENT PUJ-14` · `COMMITMENT PUJ-15`
**CR-089 task rows:** `C3` (the two groups, `PUJ-14`) · `C4` (the last-read
column, `PUJ-14`) · `C5` (`fire_line` seeded, `PUJ-15`). The four tiles are
`F3`'s (`DEF-MET-4733`), drawn inside this frame because the strip renders
outside the tab bodies.

**The question the screen answers, as drawn:** *what of ours is on this
building, and has it all been read?*

⚠ **THE THREE BLOCKS MEAN DIFFERENT THINGS AND ONLY ONE IS THE TARGET.** The
amber block on page 28 is what a clerk hits TODAY — the problem. The **bordered
grey frame is the screen as it SHOULD BE** and is what everything below records.
The teal *WHAT CHANGED* block says what moved and why. Nothing from the amber
block is a specification.

⚠ **THE AMBER BLOCK REVERSES AN EARLIER PROPOSAL OF OURS, IN WRITING.** An
earlier draft renamed this tab from *Assets* to *Meters*. **That is withdrawn.**
PO, quoted in the frame: *"this should be assets - it will ahve all meter, sub
meters, cart, ERu, fire - all kind of assets will be tagged here"*. The tenant's
catalogue holds **thirteen asset types in three families** and only three are
meters, so the rename would have hidden ten.

---

## The header

* **kicker** — `PREMISE`
* **title** — `412 Cypress Row`
* **sub-line, first line** — `P-00080` · `Silver Creek, TX 78611` ·
  `Apartment complex` · then the status pill `ACTIVE`
* **sub-line, second line** — `Route 12 · Cycle 3 — bills on the 12th`

## Actions, in the order drawn

| # | label | tier as drawn |
|---|---|---|
| 1 | **✎ Edit** | secondary |
| 2 | **+ New unit** | secondary |
| 3 | **Change status** | emphasised / danger tier — drawn as the outlined, coloured button at the right of the row |

**PRIMARY ACTION, as stated in the specification table:** *"None. This is a read
tab; an asset is assigned from the unit that holds it, where the consequence is
understood."* — so the three buttons above are the PAGE's, not the tab's, and
the tab itself offers no primary action.

## Tabs, in order

`Overview` | `Units` | `Common areas` | **`Assets`** *(active)* | `Work orders` |
`Audit log`

**Six tabs. No `Build` tab is drawn.**

## Tiles — four, each with a detail line

| # | value | label | detail line |
|---|---|---|---|
| 1 | `4` | `UNITS` | `3 occupied · 1 vacant` |
| 2 | `9` | `ASSETS` | `4 metered, all read this cycle` |
| 3 | `$0.00` | `OWED HERE` | `across 3 accounts` |
| 4 | `1` | `OPEN WORK ORDER` | `meter change, Thursday` |

## The toolbar, left to right

1. a search box, placeholder **`Search by number, type or where it is…`**
2. chip **`METERS & SUB-METERS`**
3. chip **`BEHIND THE METER`**
4. **`+ Filter ⌄`**
5. **`▦ Columns`** — drawn at the right-hand end of the toolbar

## Table columns, in order

| # | header | alignment | notes |
|---|---|---|---|
| 1 | `Asset ⇅` | left | carries the sort affordance |
| 2 | `What it is` | left | |
| 3 | `Service` | left | |
| 4 | `Size` | left | |
| 5 | `Where` | left | in words — a unit, a common area, or *the property itself* (drawn in italic when it is the property) |
| 6 | `Installed` | left | |
| 7 | `Last read` | left | may carry a *not read* sentence instead of a date |
| 8 | `Status` | left | drawn as a pill |
| 9 | *(no header)* | right | row actions — 👁 · ✎ · `…` |

**Nine columns.** *COGNITIVE LOAD, as stated: "Nine columns, two group headings,
one search, no prose."*

⚠ **ONE TABLE WITH ONE HEADER ROW, AND TWO GROUP HEADING ROWS INSIDE IT.** The
frame draws a single header row and then a full-width caption row before each
group. It is not two tables.

**The two group heading rows, character for character:**

* `METERS AND SUB-METERS · 4 · THESE ARE WHAT BILL`
* `BEHIND THE METER · 5 · WE OWN THEM, THEY ARE NOT READ`

⚠ **`Meter type` AND `Read method` ARE NOT DRAWN ON EITHER GROUP.** *WHAT
CHANGED*: **"Three type columns become two"** — what it is, and the service it
belongs to.

## The rows, in the order drawn

**Group 1 — `METERS AND SUB-METERS · 4 · THESE ARE WHAT BILL`**

| # | Asset | What it is | Service | Size | Where | Installed | Last read | Status |
|---|---|---|---|---|---|---|---|---|
| 1 | `MTR-40990` | `Meter` | `Water` | `2"` | *the property itself* | `1 Jun 2026` | `28 Aug · 96 kgal` | `MASTER` |
| 2 | `MTR-40218` | `Sub-meter` | `Electric` | `Class 200` | `Unit 1` | `1 Jun 2026` | `28 Aug · 4,182 kWh` | `IN SERVICE` |
| 3 | `MTR-40219` | `Sub-meter` | `Water` | `5/8"` | `Unit 1` | `1 Jun 2026` | `28 Aug · 14 kgal` | `IN SERVICE` |
| 4 | `MTR-40402` | `Sub-meter` | `Electric` | `Class 200` | `Laundry` | `1 Jun 2026` | `28 Aug · 611 kWh` | `IN SERVICE` |

**Group 2 — `BEHIND THE METER · 5 · WE OWN THEM, THEY ARE NOT READ`**

| # | Asset | What it is | Service | Size | Where | Installed | Last read | Status |
|---|---|---|---|---|---|---|---|---|
| 5 | `FIR-00311` | `Fire service line` | `Fire` | `6"` | *the property itself* | `1 Jun 2026` | *not read — billed on size* | `IN SERVICE` |
| 6 | `CRT-08820` | `Container / Cart` | `Trash` | `96 gal` | `Unit 1` | `1 Jun 2026` | *not read — billed per cart* | `IN SERVICE` |
| 7 | `ERT-51204` | `Comms endpoint` | *serves the water meter* | `—` | `Unit 1` | `1 Jun 2026` | *not read itself* | `IN SERVICE` |
| 8 | `BFP-00742` | `Backflow preventer` | `Water` | `2"` | *the property itself* | `1 Jun 2026` | *not read — tested yearly* | `TEST DUE 30 SEP` |
| 9 | `PV-00119` | `PV / solar` | `Solar` | `7.2 kW` | `Unit 4` | `14 Jul 2026` | *read through the net meter* | `IN SERVICE` |

⚠ **Every worked value above is an ILLUSTRATION** (`09-screen-conformance.md`'s
own warning, and CR-089 §6's correction block). **The labels, the order, the
column count and the presence of each row are the specification. The values are
not.**

## Footer

`Showing 9 of 9 · 4 read this cycle, 5 not read by design`  ⇤ ← `Page 1 of 1` → ⇥

## States, with the exact sentence drawn for each

| state | what is drawn |
|---|---|
| **Nothing installed** | Says the property cannot bill any service until a meter is on a unit, and **links to the units**. |
| **Overdue reads** | The count **leads the footer** and the rows **sort to the top**; only the metered group can be overdue. |
| **No behind-the-meter assets** | The second group is **absent entirely rather than drawn empty**. |
| **The type is not in this tenant's catalogue** | Fire service line is missing from three tenants. The row cannot exist, so the empty state **links to Settings → Asset types** rather than leaving a clerk to wonder. |

*(loading is not separately drawn on this screen)*

## Components named in the frame

`DataTable` · `FilterBar` · `StatusPill` · `RowActions` · `DateCell` ·
`InlineLinkTo`

## Rules it must obey, as stated

> Consumption always carries its unit. An absence is drawn as an absence and
> says why. Colour is never the only signal. Row actions are icons with
> tooltips.

## WHAT CHANGED — the teal block, for context only

* **It stays *Assets*, and it holds all thirteen types.** The earlier proposal to
  call it *Meters* is withdrawn.
* **Two groups, headed in the table.**
* **A last-read column that can say *not read* and why.** An empty cell would
  read as an overdue reading on every one of them.
* **Three type columns become two** — what it is, and the service it belongs to.
* ***Where* says which unit, common area or the property itself**, in words.
* **A status that is not only in-service or not** — a backflow preventer's
  yearly test is the one date on this tab with a deadline attached.


---

## AMENDMENTS — what was BUILT on 2026-09-10 (`DEF-4739` · `DEF-4740`)

The tab drew two `PlainTable`s under two headings, with `Asset # · Asset type ·
Meter type · Read method · Last read · Assigned to · Installed · Status`. It now
draws ONE shared `DataTable` + `FilterBar`, with the drawn nine in the drawn
order, so the search box, `+ Filter ⌄`, the column chooser and the pagination
footer are all on it.

**What was fixed:** `Service` and `Size` arrive — both SERVED all along, both
with a catalogue key (`assets.col.service`, `assets.col.sizeClass`) that nothing
ever read, which is `DEF-4740` in one line · `Asset type` becomes `What it is` ·
`Assigned to` becomes `Where`, saying *the property itself* in words and in the
absent style when the asset hangs on the property · `Meter type` and `Read
method` leave BOTH families, per *"three type columns become two"* · the status
is a PILL and carries `BR-AST-007`'s derived test-due chip · the drawn footer
counts arrive. **The tab stays `Assets`** — the blueprint reverses its own
rename on page 28 and the product was already right.

### Departures, recorded rather than left to be found

1. **THE TWO GROUP HEADING ROWS ARE NOT BUILT.** The frame draws ONE table with
   a full-width caption row before each family (`METERS AND SUB-METERS · 4 ·
   THESE ARE WHAT BILL`). `DataTable` has no group-row capability, and growing
   the shared kit for one tab is a bigger act than this fix — so it is recorded
   here instead. **Everything the headings bought a clerk survives in three
   things the frame also draws, and all three are asserted:** the rows that BILL
   still LEAD whatever the page is sorted by; the two family names are the
   `+ Filter ⌄` panel's options; and the two counts are the footer sentence.
   **Open.**
2. **THE TWO STANDING CHIPS BECOME A DECLARED FILTER, AND THAT IS A RATIFIED
   RULE BEATING THE FRAME.** The frame draws `METERS & SUB-METERS` and `BEHIND
   THE METER` as chips permanently in the toolbar. `DEF-1700` removed exactly
   that shape from this product by PO ruling — *"as per our stadard first raw of
   tookkit is more than suficient"* — because each such row duplicated a
   dimension the screen already declared in `TableConfig.filters`. So the split
   is declared, the panel offers it, and an applied one puts its chip where B14
   rule 12 puts every other chip.
3. **THE ROW-ACTION COLUMN (`👁 ✎ …`) IS NOT BUILT.** The specification table
   states this tab's PRIMARY ACTION is *"None. This is a read tab; an asset is
   assigned from the unit that holds it"*, so what `✎` and `…` would commit is
   not stated. The `Asset` cell opens the asset. **Open.**
4. **THE FOOTER SENTENCE SITS UNDER THE KIT'S PAGER, NOT INSIDE IT** — the same
   divergence, and the same reason, as `P5`'s footer.
   The overdue clause LEADS it when there is one, which is this file's own
   *"the count leads the footer"* state.
