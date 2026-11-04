# P4 · Property → Overview — THE DRAWN SPEC

`PRM-02` · breadcrumb `Premises → a premise` · **blueprint page 19–22**

**Source:** `05-prototype/Premises & Units Blueprint 2.pdf` (the copy on
`origin/claude/confirm-understanding-3ktufc`), pages 19, 20, 21 and the top of 22.
Read as rendered pages, not as extracted text — the layout, the column order and
the tiers are drawn.

**State chip:** `EXISTS BEHIND`
**Commitments on the chip line:** `PUJ-04` · `PUJ-06` · `PUJ-10` · `PUJ-11` · `PUJ-20`

**CR-089 task rows this screen belongs to:** `A2` (Parcel on the property's page)
· `A3` (point, parcel, GIS flag) · `B2` (owner + master account, one row; the dead
tile goes) · `B6` (route and cycle, shown) · `D1` (a property can be taken out of
service) · `F3` (the four tiles on every property tab). `A6` reaches it through the
edit form.

**What this file is.** Only the **bordered grey frame** on pages 19–20 is the
specification. The amber block above it is what a clerk hits TODAY — the problem,
never the target — and the teal *WHAT CHANGED* block says what moved and why. The
grey frame is transcribed here character for character.

---

## 1 · Header

| slot | drawn |
|---|---|
| kicker | `PREMISE` |
| title (H1) | `412 Cypress Row` |
| sub-line 1 | `P-00080` · `Silver Creek, TX 78611` · `Apartment complex` · `ACTIVE` *(pill)* |
| sub-line 2 | `Route 12 · Cycle 3 — bills on the 12th` |

The header is **four lines** and the property number **leads the identity line**
rather than sitting in the kicker. It appears once, in the header, and **not again
in the facts below**. The town, the type and the status pill follow it on the same
line; the route/cycle line is its own line beneath.

## 2 · Actions — in the drawn order, left to right

| # | label | tier |
|---|---|---|
| 1 | `✎ Edit` | **primary** *(the spec's PRIMARY ACTION row names it: "✎ **Edit**. + New unit and Change status sit beside it")* |
| 2 | `+ New unit` | secondary |
| 3 | `Change status` | **danger** *("only Change status is in the danger tier")* |

Drawn top-right of the grey frame, all three on one row, `Change status` rightmost
with the danger border and danger text.

## 3 · Tabs — six, in this order, `Overview` default

`Overview` | `Units` | `Common areas` | `Assets` | `Work orders` | `Audit log`

⚠ **`Assets` IS THE DRAWN LABEL AND IT STAYS `Assets`.** The teal blocks on pages 21
and 22 carry a stale line — *"Assets is called Meters, because that is what is on
them"* / *"Assets reads Meters"* — which the blueprint **reverses two screens later,
on page 28**, at the head of P7: *"An earlier draft of this page proposed renaming
this tab from Assets to Meters. **That was wrong and is reversed here.**"* The grey
frames on pages 19, 23 and 26 all draw `Assets`. The frame wins; the P4 teal line is
a leftover of the reversed draft and must not be built.

⚠ **Six tabs is the whole set. No seventh is drawn.**

## 4 · Tiles — four, each with a detail line

| # | value | label | detail line |
|---|---|---|---|
| 1 | `4` | `UNITS` | `3 occupied · 1 vacant` |
| 2 | `9` | `ASSETS` | `4 metered, all read this cycle` |
| 3 | `$0.00` | `OWED HERE` | `across 3 accounts` |
| 4 | `1` | `OPEN WORK ORDER` | `meter change, Thursday` |

The tiles **answer questions rather than count rows**: *is anyone in it*, *have the
meters been read*, *what is owed across the whole building*, *is anyone due to
visit*. Tile 3 is the slot the unclickable `Master account — None yet` tile freed.

## 5 · Fact rows — THIRTEEN, ONE column, in this exact order

Label left, value right, a rule under each row.

| # | label (exact) | value as drawn |
|---|---|---|
| 1 | `Address` | `412 Cypress Row, Silver Creek, TX 78611` |
| 2 | `Parcel` | `R-114-0082-004` |
| 3 | `On the map` | `30.752104, −98.238391` · `placed by the address lookup, 8 Sep 2026` *(the provenance clause is quiet/grey)* |
| 4 | `Checked against GIS` | `CHECKED` *(pill)* · `D. Whitfield, 8 Sep 2026` |
| 5 | `City limits` | `Inside` |
| 6 | `Area` | `North Silver Creek` |
| 7 | `Sub-area` | `Cypress Row` |
| 8 | `Read route` | `Route 12 — North Silver Creek` · `read on the 8th` *(quiet)* |
| 9 | `Billing cycle` | `Cycle 3` · `bills on the 12th` *(quiet)* |
| 10 | `Utility services` | `Electric · Water · Sewer · Trash` — **words, not letter badges** |
| 11 | `Owner` | line 1 `Creekside Holdings LP · Landlord`<br>line 2 `Master account A-10442 · Open it →` |
| 12 | `Managed by` | `Cane Island Property Co` |
| 13 | `Common areas` | `None on this property` *(italic/grey absent style)* |

**Row 11 is ONE row with TWO lines and nothing else.** The owner and the master
account became one row precisely so there is *"one place to look, one link that goes
somewhere"*. No sub-table of account facts is drawn.

## 6 · Footer

None. The grey frame ends after fact row 13.

## 7 · States — the blueprint's own STATES block, verbatim

| state | drawn behaviour |
|---|---|
| **No point recorded** | The row reads `Not placed yet` and **offers to place it**. Sixteen properties are in this state today. |
| **Placed but not checked** | The point shows with `Not checked yet` beside it, so a reader knows how much to trust it. |
| **No owner** | The row reads `Needs an owner` in the absent style with a `Find` control, never an empty cell. |
| **Owner with no account** | `No account is linked to this owner yet`, and `Find` opens the search. This already works today and is untouched. |

Loading, error and permission-refusal states are **not drawn** on this screen.

## 8 · Cognitive load, as stated

*"Four tiles, nine facts, one map, six tabs. One sentence of description in the whole
screen, on the sub-meter block, where the arithmetic genuinely needs explaining."*

⚠ Two internal inconsistencies, recorded rather than resolved: the frame draws
**thirteen** fact rows, not nine; and no map graphic is drawn — *On the map* is a
fact row of figures. The **sub-meter block is not drawn in the frame** yet the
cognitive-load line licenses exactly one sentence of description on it, so that
block is expected below the facts.

## 9 · Components named

`PageHeader` `KPIStrip` `OwnerAccountBlock` `MasterAccountKpiValue` `PlainTable`
`StatusPill` `CommonAreasTab` `WorkOrdersTab` `PremisesEditModal` `InlineLinkTo`

## 10 · Rules it must obey

*"One page header. The danger tier for anything that takes a thing out of service. An
absence is italic and grey and never a zero or an empty cell. Colour is never the
only signal — every pill carries its word. A printed property number is shown; a
database id never is."*

## 11 · Absences — drawn as absent, do not fill them

* No export control, no delete, no map graphic, no draggable pin.
* No fact row for `Units` (the tile says it) and none for a database id.
* No footer, no pagination, no search on this tab.
