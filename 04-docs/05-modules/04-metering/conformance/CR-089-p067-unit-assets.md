# U5 · Unit → Assets — THE DRAWN SPEC

`S15 · PRM-03` · breadcrumb `Premises → Units → a unit → Assets → + Assign from
inventory` · **blueprint pages 67–71**

**Source:** `05-prototype/Premises & Units Blueprint 2.pdf`, the section opening at
the foot of page 67, **drawn on pages 68–69**, specified on 69–71. Read as RENDERED
pages — the column order, the two tables and the footer split are drawn.

**State chip:** `EXISTS BEHIND`
**Commitments on the chip line:** `PUJ-14` · `PUJ-15` · `PUJ-30` · `PUJ-31` · `PUJ-32`

**CR-089 task rows this screen belongs to:** `C3` + `C4` (what bills vs what does
not, and a last-read column that can say *not read* and why — `PUJ-14`) · `C5`
(`fire_line` seeded for every tenant that sells fire — `PUJ-15`) · `G1` (the
inventory search takes what a clerk is holding — `PUJ-30`) · `G2` (assigning
finishes on the unit — `PUJ-31`) · `G3` (an attached asset's status changes from
its row — `PUJ-32`) · `F3` (the four tiles on every unit tab).

**What this file is.** Only the **bordered grey frame** on pages 68–69 is the
specification. The amber block on 67–68 is what a clerk hits TODAY — *"The control
exists and it searches — **by asset number only**"* — and is the problem statement,
never the target.

---

## 1 · Header — identical to U4, `Assets` tab active

| slot | drawn |
|---|---|
| kicker | `UNIT` |
| title (H1) | `Unit 2` |
| sub-line 1 | `U-01145` **(bold)** · `412 Cypress Row, Silver Creek, TX 78611` · `Residential` · `ACTIVE` *(pill)* `OCCUPIED` *(pill)* |
| sub-line 2 | `Route 12 · Cycle 3 — from the building` |

Page 70, verbatim: *"It carried a header of its own — `Unit 2 · 412 Cypress Row /
Meters on this unit` — and no tab row, so it read as somewhere you had gone rather
than part of the unit you were on. **It now wears the same header, the same three
page actions and the same six tabs** as Overview, Plan, Account, Occupancy and the
audit log; `+ Assign from inventory` moves down to the tab it belongs to."*

## 2 · Header actions — in the drawn order

`✎ Edit` *(secondary)* | `Move` *(secondary)* | `Change status` *(**danger**)* —
below the sub-lines, left-aligned.

## 3 · Tabs — six, in this order, `Assets` active

`Overview` | `Assets` | `Plan` | `Account` | `Occupancy` | `Audit log`

## 4 · Tiles — the same four, with their detail lines

| # | value | label | detail line |
|---|---|---|---|
| 1 | `5` | `ASSETS` | `2 metered · 3 behind the meter` |
| 2 | `$61.40` | `OWED` | `due 24 Sep` |
| 3 | `Standard` | `PLAN` | `since 1 Jun 2026` |
| 4 | `—` | `OPEN WORK` | `nothing booked` |

## 5 · The consequence bar — drawn ABOVE the on-unit table, one row

| side | drawn |
|---|---|
| left | `A unit cannot bill a service until a meter is on it.` |
| right | `+ Assign from inventory` *(button, outline)* |

**This is the screen's PRIMARY ACTION**, page 69: *"`+ Assign from inventory`.
Inside the panel, `Assign ✓` on the row — one press, and it is done here."*

## 6 · The on-unit table — SIX columns and an unheaded action column

| # | header | alignment | cell, as drawn |
|---|---|---|---|
| 1 | `Meter` | left | `MTR-40218` **(bold)** |
| 2 | `Service` | left | `Electric` · `Water` |
| 3 | `Size` | left | `Class 200` · `5/8"` |
| 4 | `Status` | left | `IN SERVICE` *(pill)* |
| 5 | `On since` | left | `1 Jun 2026` |
| 6 | `Last read` | left | `28 Aug · 4,182 kWh` · `28 Aug · 14 kgal` — a date and a **quantity with its explicit unit** |
| 7 | *(no header)* | right | row actions as ICONS: `✎` `−` `…` |

**The two drawn rows, in order:**

| Meter | Service | Size | Status | On since | Last read |
|---|---|---|---|---|---|
| `MTR-40218` | `Electric` | `Class 200` | `IN SERVICE` | `1 Jun 2026` | `28 Aug · 4,182 kWh` |
| `MTR-40219` | `Water` | `5/8"` | `IN SERVICE` | `1 Jun 2026` | `28 Aug · 14 kgal` |

Page 69: *"The meters already on the unit **carry their status**, and it can be
changed from this row — **the edit icon on the row**, exactly as the rules ask for
row actions."*

## 7 · The `ASSIGN FROM INVENTORY` panel — a bordered panel inside the tab

**Panel kicker:** `ASSIGN FROM INVENTORY`

**Toolbar, left to right:**

| # | element | drawn text |
|---|---|---|
| 1 | search input | placeholder `Search by number, type or size…` |
| 2 | chip, removable | `WATER ×` |
| 3 | chip, removable | `IN THE DEPOT ×` |
| 4 | filter control | `+ Filter ⌄` |

**Result table — FIVE columns and an unheaded action column:**

| # | header | cell, as drawn |
|---|---|---|
| 1 | `Meter` | `MTR-41007` **(bold)** |
| 2 | `Service` | `Water` |
| 3 | `Size` | `5/8"` · `1"` |
| 4 | `Where it is` | `Main depot · shelf B` · `Van 3 · K. Osei` |
| 5 | `Status` | `IN STOCK` *(pill)* · `HELD BY A TECHNICIAN` *(pill)* |
| 6 | *(no header)* | `Assign ✓` *(button)* |

**The three drawn rows, in order:**

| Meter | Service | Size | Where it is | Status |
|---|---|---|---|---|
| `MTR-41007` | `Water` | `5/8"` | `Main depot · shelf B` | `IN STOCK` |
| `MTR-41008` | `Water` | `5/8"` | `Van 3 · K. Osei` | `HELD BY A TECHNICIAN` |
| `MTR-40990` | `Water` | `1"` | `Main depot · shelf B` | `IN STOCK` |

⚠ Row 1's `Assign ✓` is drawn **filled** and rows 2–3's are drawn **outlined**. One
tier, drawn twice; treat the filled one as the hover/focus state rather than as a
per-row tier, and confirm with the PO if it matters.

## 8 · The panel footer — one row, two halves

| side | drawn |
|---|---|
| left | `Showing 3 of 3 in stock · 41 water meters in inventory` |
| right | `Assigning records the start read and takes it out of stock.` |

Page 69: *"What assigning does is said before you do it, in one line: the start read
is recorded, and the meter leaves stock."*

## 9 · States — the blueprint's own STATES block, verbatim

| state | drawn behaviour |
|---|---|
| **Nothing in stock** | *"The empty state names the service and the size searched for and offers the inventory screen, rather than an empty table."* |
| **Held by a technician** | *"The row shows who has it. It can still be assigned, because a van is a location and not a refusal."* |
| **Wrong service for the unit** | *"Refused before the press, in the row, naming the service the unit takes. A water meter cannot be assigned to an electric-only unit."* |
| **Removing a meter** | *"The consequence is the one the current screen already states: a final read is recorded, it returns to inventory, and the unit cannot bill that service until a replacement is on it."* |

## 10 · Cognitive load, as stated

*"One table of what is on the unit, one search, one table of what is available.
**No prose beyond the single consequence line.**"*

## 11 · Components named in the frame

`DataTable` `FilterBar` `SearchSelectField` `RowActions` `StatusPill` `RefusalStrip`
`ConfirmDialog`

⚠ **`DataTable` and `FilterBar`, NOT `PlainTable`.** This is the same naming the
premises half found five screens away from (`DEF-4739`): the shared table is what
carries search, filters, the column chooser, pagination and the footer counts.

## 12 · Rules it must obey, as stated

*"Row actions are icons with tooltips. A refusal caps at five or six words and says
what to do. A consequence preview before a commit that changes service state.
Colour is never the only signal."*

## 13 · FOR · HOW YOU GET HERE (page 69)

* **FOR** — *"A clerk or a technician with a meter in their hand, or a supervisor
  preparing a change-out. It is the last step of connecting a unit and the first
  step of every meter exchange."*
* **HOW YOU GET HERE** — *"The unit's page → Assets. Also from a work order, which
  is where a technician arrives from."*

## 14 · Absences — drawn as absent, do not fill them

* **No `Type` column** on either table — the drawn classification columns are
  `Service` and `Size`.
* **No `Installed` column** — the drawn date column is `On since`.
* **No `Meter type` or `Connection size` columns** in the inventory panel; `Size`
  is one column.
* **No count line above either table** — the counts are in the panel FOOTER.
* **No `Last read` arrives-with note.** `Last read` is a drawn COLUMN.
* **No prose beyond the two consequence lines** (the bar above the table and the
  footer's right half).

---

## AMENDMENTS — what was BUILT on 2026-09-10 (`DEF-MET-4768`)

Maintenance. The read lane called this the worst of the three unit tabs and the
count is why: five columns of a six-column frame, on the wrong table component.

**What was fixed.** `PlainTable` → the shared **`DataTable`**, which is what
§11 names and why — *"the shared table is what carries search, filters, the
column chooser, pagination and the footer counts"* · **`Service`, `Size` and
`Last read` arrive**, all three SERVED all along on the registry row this tab
already held, each with a catalogue key nothing read — `DEF-4740`'s shape a
second time, one module folder over · `Asset type · Meter type · Read method`
joined into one cell becomes `Service` and `Size`, per *"three type columns
become two"* · `Installed` → **`On since`**, which §14 names · the status is a
**pill** (`AssetStatusCell`, carrying `BR-AST-007`'s derived Test-due chip)
rather than plain text · the row action is an **icon in `RowActions`** rather
than a text button under a column headed `Change` (B14 rule 15; `DEF-337` is
what the text form costs) and is now **disabled with its reason** where the
registry row is missing (`BR-SHL-025`) instead of rendering a dash · the
`Last read` **arrives-with note is deleted**, and §14 already said it should
never have existed: *"No `Last read` arrives-with note. `Last read` is a drawn
COLUMN."*

⚠ **THE DELETED NOTE WAS FALSE, NOT MERELY SUPERFLUOUS.** It read *"a registry
row carries no reading and nothing joins the reads onto it, so the column is
left out"*. `selectors.asset_page_rows` joins the latest read onto every meter
and sub-meter in ONE query and has since wave `C`. That is hard-won law 1 in a
user-visible string, and it is `DEF-MET-4767`.

### Departures, recorded rather than left to be found

1. **THE IDENTITY COLUMN IS HEADED `Asset`, WHERE THE FRAME HEADS IT `Meter`.**
   This table carries everything ON the unit — a trash cart and a fire line
   included — and `Meter` over a cart is wrong in a way a frame drawn with two
   meter rows never had to consider. The premises Assets tab, the same data and
   the same module, says `Asset`; B14 rule 36 asks for one word per thing across
   the product. **Open — one sentence to the PO if it matters.**
2. **THE `−` AND `…` ROW ACTIONS ARE NOT BUILT.** The frame draws `✎ − …`.
   Nothing in this product removes a meter from a unit; the consequence is
   stated in the rule line under the table and the act belongs to the asset
   registry. Inventing the call is not maintenance. **Open.**
3. **`Last read`'s DATE-AND-QUANTITY SHAPE IS BUILT HERE AND NOT ON THE
   PREMISES ASSETS TAB**, which draws the same column from the same selector and
   shows the DATE ALONE — `CR-089-p028`'s own frame draws `28 Aug · 96 kgal`
   there too. The two cells are now duplicates and should collapse into one in
   `assetsShared`; that file's neighbour had another lane in it on the day, so
   the merge is recorded rather than done. **Open.**
4. **THE INVENTORY PANEL'S RESULT TABLE IS STILL A `PlainTable`** with its own
   hand-rolled search and server-resolved chips (§7). Its search is a SERVER
   query on `?terms=` and its chips are the server's answer, so moving it onto
   `DataTable` + `FilterBar` is a different and larger job from this one.
   **Open.**
5. **THE FOOTER SENTENCES ARE NOT A FOOTER ROW.** §8 draws one row, two halves:
   `Showing 3 of 3 in stock · 41 water meters in inventory` and *"Assigning
   records the start read and takes it out of stock."* The kit's pager carries
   the counts and the sentence sits beside the panel — the same divergence, and
   the same reason, as `P5`'s footer on the premises half. **Open.**
6. **NO `searchFields` AND NO `filters` ARE DECLARED ON THE ON-UNIT TABLE,
   DELIBERATELY.** `BR-SHL-010`: a list that declares none gets no filter UI at
   all, and the frame draws the toolbar on the INVENTORY panel rather than on
   this table. Declaring one filter in order to "use `FilterBar`" would put
   furniture on screen the drawing does not have.

---

## AMENDMENTS — what was BUILT on 2026-09-19 (`DEF-MET-5860`, `DEF-MET-5861`, `DEF-MET-5862`)

Maintenance, from the PO's own beta walk. Three faults on this one tab, and two
of them were columns this file had already specified correctly.

**1 · THE ASSIGN NOW ASKS WHICH SERVICE.** PO ruling, verbatim: *"this is
correct fix it"* — the Assign step asks which service, **required for meters and
sub-meters, optional for everything else** (`BR-AST-009` binds `MEASURING_TYPES`
only), and **no default, because nothing may guess which service a meter
serves**. The picker offers `unit.services` — the premises' own
`services_available`, inherited by the unit (`BR-MET-1161`) — in `SERVICE_CODES`
seed order, which is the same list the header's sub-line reads and the same
bound the server enforces (`BR-MET-119`).

⚠ **IT IS A CONTROL THE FRAME DOES NOT DRAW, AND THAT IS STATED RATHER THAN
SLIPPED IN.** §7 gives the inventory table a `Service` column carrying each
row's own service (`MTR-41007 · Water · 5/8"`), and §9 names the state *"Wrong
service for the unit — refused before the press, in the row"*. **Both presume a
service STORED on the shelf spare, and there is no column for one** —
`_check_measuring_requirements`'s docstring has said so since the module
shipped, and `B2 r4` stores the service via `service_point_id`, which only
exists once the asset sits on a unit. **That gap is `OQ-AST-12485` and it is
open.** Until it is answered the panel carries ONE picker instead of a fact per
row; when it is answered the picker becomes a PRE-FILLED CONFIRMATION and §7's
column becomes buildable.

⚠ **THE REFUSAL IS IN THE ROW, WHICH IS §9's OWN SHAPE.** *"Refused before the
press"* — a measuring row's `Assign ✓` is disabled with its reason until a
service is chosen. Unreachable beats refused-after-the-fact: a server refusal
would bounce the clerk back to an empty shelf with their search gone.

**2 · `On since` READS THE ASSIGNMENT'S `from_date`, NOT `install_date`.**
§14 already had this right — *"No `Installed` column — the drawn date column is
`On since`"* — and the built column read `install_date` anyway. They are
different facts: `install_date` is when the DEVICE was installed (the
depreciation age base, and the registry's own `Installed` column), while
`from_date` is when it arrived at THIS unit. **A meter moved between units has
one installation and several arrivals**, and a shelf spare has no `install_date`
at all, so the column drew a dash on every meter a clerk had just assigned.
`asset_dict` now serves `assigned_from`, at no query cost — the current
assignment is already read for `assigned_unit_id`.

**3 · `Last read` SHOWS THE READING, WITH THE USAGE BESIDE IT.** PO ruling,
verbatim: *"fix it"*, against *"Show the reading, and keep the usage beside it
when there is one … and a sub-meter's first read shows its date and its reading
instead of a bare date."* The cell drew `consumption` alone, which is the USAGE
since the previous read — null on a register's FIRST read, so the cell showed a
bare date over a reading the clerk could already see on two other screens. The
payload did not carry the reading at all; `latest_read_for_asset` and its batched
twin now serve `current_value` beside it. **A first read shows no usage clause
and never a zero** (`BR-MET-106`, `DEF-079`), and an ESTIMATE is the mirror — a
usage with no reading (`BR-MET-028`) — so the two clauses are independent.

⚠ **AND THE PRODUCT DISAGREES WITH ITSELF ABOUT THIS CELL IN FOUR PLACES**
(`DEF-MET-5866`), reported rather than settled here: the asset registry draws
usage-then-month-day, the premises Assets tab draws the date alone, this tab now
draws date · reading · usage, and the Reads screens draw a server-composed
string that rounds identically but is **not grouped**. This tab follows the PO's
own written example, which carries the thousands comma.

---

## AMENDMENTS — what was BUILT on 2026-09-27 (`DEF-MET-6911`, `DEF-MET-6926`)

Maintenance, from the PO's own beta walk at `2.352.0`. **Reproduced at
`2.376.0`** on `brazosbend` unit `SCW-U-001`, in a browser at 1440 — so this is
not fixed since; it is the same screen, twenty-four builds on.

**1 · THE INVENTORY PANEL NAMES WHAT EACH SPARE MEASURES IN.** A new column,
headed `Unit of measure` (`assets.col.uom`, the registry's own word for it),
carrying `assets.unit`.

⚠ **IT IS NOT §7's `Service` COLUMN AND DOES NOT STAND IN FOR IT.**
`OQ-AST-12485` is still **OPEN** — a shelf spare stores no service, because
`service_point_id` is the only place one lives and it exists only once the
asset sits on a unit. Measured on `brazosbend` 2026-09-27: **sixteen unassigned
assets and not one carries a service.** A `Service` column here would be an
em-dash on every row for ever, which is the failure the PO named in their own
third finding.

⚠ **THE UNIT OF MEASURE IS THE FACT THE PRODUCT ACTUALLY HOLDS, AND CLAUDE.md
HARD RULE 3 IS WHY IT IS A COLUMN.** On this tenant four shelf meters carry **no
size class at all** — `AST-04412`, `AST-04413`, `AST-04414` (`kgal`) and
`M-5099` (`kWh`) — so all four read `Meter · —` and a clerk fitting a water
service could not tell the three water meters from the electric one. `unit` is
non-null on all nine measuring spares and was already on the wire, so this cost
no endpoint change.

**2 · THE HEADER IS `Size`, WHICH §14 ABOVE HAS ALWAYS SAID.** `Connection
size` → `Size`. ⚠ **`Meter type` IS KEPT, DELIBERATELY, AGAINST §14.** Dropping
a real fact a clerk uses is not needed to close this defect and would be a
second change carrying the first one's authority; it is recorded here as a live
divergence rather than done quietly. `Type` likewise stays.

**3 · EVERY DASH ON `Size`, `Unit of measure` AND `Meter type` IS NOW WORDS.**
`DEF-514`'s ruling decides this: an em-dash cannot tell *nobody recorded it*
from *the product cannot record it*, and the PO asked the question directly.
`BR-AST-009` binds `MEASURING_TYPES` only, so `CART-0099`, `BAT-0904`,
`BF-0002`, `PV-0001`, `EV-0001` and `COM-0001` have no service, no size and no
unit **correctly and for ever** — they read **not measured**. A METER missing
one reads **no size recorded** / **no unit recorded**, which is a gap worth
closing. One sentence for both would have been the dash again, in words.

⚠ **`CART-0099` IS A SHELF SPARE ON THIS TENANT, NOT AN INSTALLED ROW.** The PO
photographed it in the installed table on theirs. Either way the question they
asked is answered: **yes, an asset can exist with no service at all.**

**4 · `DEF-MET-6926` — THE ON-UNIT `Size` CELL PRINTED THE LOOKUP CODE.** Found
while reproducing the above, not reported. This table rendered
`line.row.size_class` raw, so it read **`W-58`** and **`E-1P-100`** while the
shelf panel on the SAME SCREEN read `Water 5/8"` and `Electric 1φ 100A` for
those same codes — and §6 of this file draws `Class 200` and `5/8"`, names in
both. Both tables now resolve the code through one `useSizeClassNames`, one
request, so they cannot drift again.

⚠ **THE COMMENT ON THAT CELL IS WHY IT SURVIVED — HARD-WON LAW 1.** It asserted
`size_class` was *"the tenant's own code TEXT … a printed reference"*. It is a
`service_size_classes` lookup code. **And the fixture agreed with the comment**:
`UnitAssetsColumns.dom.test.tsx` seeds `size_class: '5/8"'`, a display string
production never holds — so the suite asserted the belief instead of testing
it. `UnitAssetsUom.dom.test.tsx` seeds the CODE, asserts the NAME, and asserts
the code is absent.
