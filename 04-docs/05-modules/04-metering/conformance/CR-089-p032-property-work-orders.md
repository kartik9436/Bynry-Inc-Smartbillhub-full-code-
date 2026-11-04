# P8 · Property → Work orders — THE DRAWN SPECIFICATION

**Source:** *Premises & Units Blueprint 2*, **pages 32–34**. The screen section
opens on page 32; the grey frame runs pages 32–33; *WHAT CHANGED* is on page 33;
the specification table and the states are on page 34.

**Screen id:** `PRM-02` — Premises → a premise → Work orders
**State chip:** `EXISTS BEHIND` · `COMMITMENT PUJ-16`
**CR-089 task rows:** `C6`, the **work-orders half** (`PUJ-16`). The four tiles
are `F3`'s (`DEF-MET-4733`).

**The question the screen answers, as drawn:** *is anybody due to visit, and
what for?*

⚠ **THE AMBER BLOCK ON THIS SCREEN CLAIMS NO FAULT, AND SAYS SO.** Verbatim:
*"The tab exists and I did not find work on the sample property to judge it by,
so nothing here is claimed as a fault. What is drawn is what the journey needs: a
person on the phone to a resident wants **when is somebody coming**, and that is
a date and a name."* So the grey frame here is a design drawn to the journey
rather than a correction of an observed screen — which makes the frame the whole
specification.

---

## The header

* **kicker** — `PREMISE`
* **title** — `412 Cypress Row`
* **sub-line, first line** — `P-00080` · `Silver Creek, TX 78611` ·
  `Apartment complex` · then the status pill `ACTIVE`
* **sub-line, second line** — `Route 12 · Cycle 3 — bills on the 12th`

## Actions, in the order drawn

| # | label | tier as drawn | where |
|---|---|---|---|
| 1 | **✎ Edit** | secondary | page header |
| 2 | **+ New unit** | secondary | page header |
| 3 | **Change status** | emphasised / danger tier | page header |
| 4 | **⚡ Raise work here** | **PRIMARY** | the tab's own toolbar, at its right-hand end |

**PRIMARY ACTION, as stated in the specification table:** **`⚡ Raise work
here.`** — and *WHAT CHANGED* adds: *"with the property already the subject,
using the raise-work icon the conventions already assign."*

## Tabs, in order

`Overview` | `Units` | `Common areas` | `Assets` | **`Work orders`** *(active)* |
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

1. a search box, placeholder **`Search work…`**
2. chip **`OPEN`** — the drawn default filter
3. **`+ Filter ⌄`**
4. **`⚡ Raise work here`** — the primary button, at the right-hand end

**No `Columns` control is drawn on this tab.**

## Table columns, in order

| # | header | alignment | notes |
|---|---|---|---|
| 1 | `Work` | left | the order number alone — `WO-4822` |
| 2 | `What` | left | the job in words — `Meter change` |
| 3 | `Where` | left | **within the building** — `Unit 4`, `Laundry` |
| 4 | `Crew` | left | a person's name, or `—` |
| 5 | `Booked` | left | a date in words, or *Not booked yet* in the absent style |
| 6 | `Status` | left | drawn as a pill |
| 7 | *(no header)* | right | row actions — 👁 · `…` |

**Seven columns.** *COGNITIVE LOAD, as stated: "Seven columns, one filter chip,
no prose."* — **no prose**, so no explanatory sentence sits above the table.

## The rows, in the order drawn

| # | Work | What | Where | Crew | Booked | Status |
|---|---|---|---|---|---|---|
| 1 | `WO-4822` | `Meter change` | `Unit 4` | `K. Osei` | `Thu 11 Sep, am` | `SCHEDULED` |
| 2 | `WO-4610` | `Leak investigation` | `Laundry` | `—` | *Not booked yet* | `WAITING` |

⚠ **Every worked value above is an ILLUSTRATION.** The labels, the order, the
column count and the presence of each row are the specification. The values are
not — and CR-089 `C6` records that **no work order exists on any sample
property**, so these two rows have never been rendered by the product.

## Footer

`Showing 2 open · 7 done in the last year`  ⇤ ← `Page 1 of 1` → ⇥

*WHAT CHANGED*: *"The footer counts what is done as well as what is open, because
**is this building always breaking** is a real question."*

## States, with the exact sentence drawn for each

| state | what is drawn |
|---|---|
| **Nothing open** | Says so, **and offers to raise work** — an empty list here is good news and should read like it. |
| **Unbooked** | ***Not booked yet*** in the absent style, **never a blank date**. |

*(loading and error are not separately drawn on this screen)*

## Components named in the frame

`WorkOrdersTab` · `DataTable` · `StatusPill` · `DateCell` · `RowActions`

## Rules it must obey, as stated

> An absence is drawn as an absence. Row actions are icons with tooltips. Button
> grammar: ⚡ raises work.

## WHAT CHANGED — the teal block, for context only

* **Booked, in words a person can repeat down the phone** — *Thursday 11
  September, morning* — and *Not booked yet* in the absent style when there is no
  date, never an empty cell.
* **Where, within the building**, so a resident can be told whether it is their
  flat.
* **Raise work here**, with the property already the subject.
* **The footer counts what is done as well as what is open.**

**And the specification table's own WHAT CHANGED row:** *"Drawn to the journey
rather than to the table. I did not have work on the sample property to walk, and
that is said above rather than dressed up as a finding."*

---

## WHAT WAS BUILT AGAINST THIS FILE — 2026-09-10 (`2.234.16`)

`DEF-4739` (the component) and `DEF-4740` (the columns), the Work-orders half.
Decision log, same date.

**Built to the frame:** the shared `DataTable` with its `FilterBar` · the search
box `Search work…` · the chip **OPEN** applied on arrival, with `+ Filter ⌄`
offering `Open` and `Done` · `⚡ Raise work here` as the primary, at the
toolbar's right-hand end · the **seven** drawn columns in the drawn order, with
`Work` and `What` split apart and `Where` drawn from `unit_label` (served since
wave O and previously visible only inside the drawer) · `Status` as a pill ·
`Nothing open` saying so and offering to raise work · *no prose*: the `<h3>` and
the sentence above the table are gone, the sentence moved into a disclosure
closed by default.

**`Service`, `Mode`, `Outcome` and `Stands on` are declared and OFF by
default** rather than deleted — the column chooser the shared table brings is
where a capability like that belongs. `Stands on` is default-**ON** for the
ACCOUNT host, because `US-WRK-004`'s reason for it is specific to a list that
mixes anchors.

**The drawn `OPEN` default had a consequence this file does not mention.**
`DataTable` draws a screen's own empty state only when nothing is searched and
nothing is filtered; with a filter applied it draws *no results, clear filters*.
So the chip would have replaced *"an empty list here is good news and should
read like it"* with a dead end on every quiet property. The tab passes an
unfiltered state to the table when there is genuinely nothing to filter. Found
by a test going red, not by reading.

### WHERE THIS FILE IS WRONG, OR ASKS FOR SOMETHING THAT DOES NOT EXIST

* **The primary does not carry the property.** *"with the property already the
  subject"* is not buildable today: `NewOrderWizard` holds the premises in local
  state, reads no query parameter, and asks for it as a raw text box — which is
  a database id on screen (B14 rule 31) as well as unanswerable by a clerk. The
  door is opened plain rather than faked. `DEF-WRK-4752`.
* **The footer's second half has no source.** *"7 done in the last year"* — no
  endpoint serves a done-in-the-last-year count, and the shared footer has no
  slot for a sentence. `DEF-MET-4753`.
* **The amber block still holds.** `CR-089` `C6` records that no work order
  exists on any sample property, and that is still true: **nothing on this tab
  has ever rendered a row in a browser.** Everything asserted about it is
  asserted against fixtures.
* **Column 7 is drawn with no header** and the kit gives every action column
  one (`Actions`). B14 rule 36 says the kit is how you comply and §4 of the UI
  skill says the system wins where the two disagree; the difference is recorded
  here rather than followed silently.
