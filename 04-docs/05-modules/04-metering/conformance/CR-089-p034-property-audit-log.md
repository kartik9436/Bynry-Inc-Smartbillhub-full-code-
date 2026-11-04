# P9 · Property → Audit log — THE DRAWN SPECIFICATION

**Source:** *Premises & Units Blueprint 2*. The screen section opens on **page
34**; the amber block and the grey frame are on **page 35**; *WHAT CHANGED*
runs pages 35–36 and the specification table and states are on **page 36**.

⚠ **THIS SCREEN'S SECTION BEGINS ON PAGE 34, INSIDE THIS LANE'S RANGE, AND ITS
TAIL FALLS ON PAGE 36.** The page-36 half (FOR · HOW YOU GET HERE · PRIMARY
ACTION · COGNITIVE LOAD · STATES · COMPONENTS · RULES) is recorded here because
it belongs to this screen; `P10 · Edit a property` opens on page 37 and is
another lane's.

**Screen id:** `PRM-02` — Premises → a premise → Audit log
**State chip:** `EXISTS BEHIND` · `COMMITMENT PUJ-17`
**CR-089 task rows:** `C6`, the **audit half** (`PUJ-17`). The four tiles are
`F3`'s (`DEF-MET-4733`).

**The question the screen answers, as drawn:** *who changed this, and what did it
say before?*

⚠ **WHAT A CLERK HITS TODAY, from the amber block — this is the PROBLEM, not the
target:** *"The columns are **When · Actor · Action**, and the action is one
phrase with an **Expand** control. The thing a person actually needs — **what the
value was before** — is behind a press, one row at a time."*

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
| 3 | **Change status** | emphasised / danger tier |

**PRIMARY ACTION, as stated in the specification table:** *"None. It is a record
and nothing on it can be changed, which is the point."*

## Tabs, in order

`Overview` | `Units` | `Common areas` | `Assets` | `Work orders` |
**`Audit log`** *(active)*

**Six tabs. No `Build` tab is drawn.** *HOW YOU GET HERE*: *"The property's page
→ Audit log. The unit has its own."*

## Tiles — four, each with a detail line

| # | value | label | detail line |
|---|---|---|---|
| 1 | `4` | `UNITS` | `3 occupied · 1 vacant` |
| 2 | `9` | `ASSETS` | `4 metered, all read this cycle` |
| 3 | `$0.00` | `OWED HERE` | `across 3 accounts` |
| 4 | `1` | `OPEN WORK ORDER` | `meter change, Thursday` |

## The toolbar, left to right

1. a search box, placeholder **`Search this history…`**
2. chip **`ALL`** — the drawn default filter
3. **`+ Filter ⌄`**

**No `Columns` control is drawn on this tab.** *WHAT CHANGED*: **"Searchable and
filterable, because the question is usually about one field."**

## Table columns, in order

| # | header | alignment | notes |
|---|---|---|---|
| 1 | `When` | left | date and time — `8 Sep 2026, 15:42` |
| 2 | `Who` | left | a person's NAME. *WHAT CHANGED*: ***Actor* becomes *Who*, and shows a person's name.** |
| 3 | `What changed` | left | the field, in words |
| 4 | `From` | left | **the previous value, as a COLUMN** |
| 5 | `To` | left | the new value |
| 6 | *(no header)* | right | row actions — `…` |

**Six columns.** *COGNITIVE LOAD, as stated: "Six columns, one search. **No prose
at all.**"*

⚠ **THERE IS NO `Expand` CONTROL AND NO DISCLOSURE ANYWHERE IN THE DRAWN TABLE.**
*WHAT CHANGED*: **"From and To as columns, so a history is read down the page
instead of expanded row by row. That is the whole use of an audit log: seeing
what a field used to say."*

## The rows, in the order drawn

| # | When | Who | What changed | From | To |
|---|---|---|---|---|---|
| 1 | `8 Sep 2026, 15:42` | `D. Whitfield` | `Property added` | `—` | `412 Cypress Row` |
| 2 | `8 Sep 2026, 15:44` | `D. Whitfield` | `Checked against GIS` | *Not checked* | `Checked` |
| 3 | `8 Sep 2026, 16:02` | `D. Whitfield` | **`Read route`** | *None* | `Route 12` |
| 4 | `8 Sep 2026, 16:02` | `D. Whitfield` | `Units created` | `—` | `1, 2, 3, 4` |

⚠ **`Read route` IS THE DRAWN LABEL, NOT `Reading route`.** It is one of the
three agreed labels `09-screen-conformance.md` records as existing nowhere in the
product.

⚠ **THE `From` CELL HAS THREE DRAWN FORMS AND THEY ARE DIFFERENT FACTS.** `—`
where the row is a creation and there was no previous value at all; *Not checked*
and *None* in the ABSENT style where a field previously held nothing. *WHAT
CHANGED*: **"An absent previous value is drawn as an absence — a property that
had no route now says *None → Route 12*, which is a different fact from a route
being changed."**

⚠ **Every worked value above is an ILLUSTRATION.** The labels, the order, the
column count and the presence of each row are the specification.

## Footer

`Showing 4 of 4`  ⇤ ← `Page 1 of 1` → ⇥

**No per-row count of a wider window and no *open the full log* control is drawn
inside this frame.**

⚠ **AMENDED 2026-09-10 — THE LINK AND THE WINDOW SENTENCE ARE KEPT, BY PO
RULING, AND THE FRAME IS NOT FOLLOWED HERE.** PO, verbatim: *"keep it as it
is"*. The built tab draws, under the table, the `Open the audit log for this
record →` control and the sentence `Showing the last 2 years`.

**Why this is a ratified rule beating the frame rather than a lapse.** The
window is bounded SERVER-side (`BR-AUD-006` retention, `BR-AUD-013` the archive
opt-in) and `BR-AUD-010` requires a per-entity tab to be a WINDOW that *"links
to S61 pre-filtered"*. The frame drew a four-row history where the whole history
happened to fit, so the question *is this all of it?* never arose in the
drawing. On a record older than the hot window it arises on every visit, and an
unstated absence reads as **it never happened** — which is the one thing an
audit log must never say. `DEF-579` is the record of the opposite mistake (a tab
that linked and drew no rows); this keeps both halves.

## States, with the exact sentence drawn for each

| state | what is drawn |
|---|---|
| **Only the creation** | One row. A new property's history is one line and should look like one, **not like an error**. |
| **Retention reached** | Says plainly that **older entries have been removed on the retention schedule**, rather than implying nothing happened. |

*(loading and error are not separately drawn on this screen)*

## Components named in the frame

`AuditEventCell` · `DataTable` · `DateCell` · `FilterBar`

## Rules it must obey, as stated

> Every money or service action is recorded with who, when and what. No database
> id on screen. An absence is drawn as an absence.

## WHAT CHANGED — the teal block, for context only

* **From and To as columns**, so a history is read down the page instead of
  expanded row by row.
* ***Actor* becomes *Who***, and shows a person's name.
* **An absent previous value is drawn as an absence** — *None → Route 12*.
* **Searchable and filterable**, because the question is usually about one field.


---

## AMENDMENTS — what was BUILT on 2026-09-10, and where it departs (`DEF-4739` · `DEF-4740`)

The tab drew `PlainTable` with `When · Actor · Action`, the values behind an
`Expand`. It now draws the shared `DataTable` + `FilterBar` with the drawn
columns. Three departures are recorded rather than left to be found:

1. **`▦ Columns` RENDERS, AND THE FRAME DRAWS NO SUCH CONTROL ON THIS TAB.**
   The kit puts the column chooser on every list (B14 rule 12's toolbar
   grammar); suppressing it on one screen is a per-screen exception to a
   ratified rule, which is a bigger act than the divergence it would fix. Kept,
   recorded, not built around.
2. **THE ROW-ACTION COLUMN (`…`) IS NOT BUILT.** The frame draws a sixth,
   header-less column of row actions and the specification table says the tab's
   PRIMARY ACTION is *"None. It is a record and nothing on it can be changed"* —
   so what the `…` opens is not stated anywhere. A control is not invented to
   fill a drawn cell (hard-won law 2: a menu that opens onto nothing is dead
   UI). **Open.**
3. **ONE ROW PER EVENT, WITH A THREE-LINE CAP AND `+N more`.** The frame draws
   four events that each moved one field, so *one row per event* and *one row
   per change* are indistinguishable in it. They are not the same on real data:
   `premises.created` records `premises_detail_dict(row)` — thirty-odd keys — so
   a cell stacking every one of them would set the height of its whole row.
   A CREATION therefore reads as the EVENT (`Premises added`) with `—` in
   `From`, which is what the frame's own `Property added` row draws; an UPDATE
   stacks its changed fields, three at a time, and says how many more there are.

**What was FIXED, in the frame's own words:** `Actor` → `Who` · `What changed`,
`From` and `To` as COLUMNS · no `Expand` and no disclosure in the table · **an
absent previous value drawn as an ABSENCE**, so `None → Route 12` can no longer
read like a route being changed. That last one was the sharpest miss on this
screen and it is asserted as markup, not as a word, in
`07-frontend/src/features/metering/PremisesTabFurniture.test.tsx`.
