# P1 · The property list — the DRAWN specification

`S14 · PRM-01` — **state chip: `EXISTS BEHIND`**
Blueprint *Premises & Units Blueprint 2*, **page 5** (screen head and amber
block) → **page 8** (detail table). The grey frame itself is drawn on **page 6**.

**Commitment chips on the screen:** `PUJ-01`.
**CR-089 task rows this screen belongs to:** `A8` (the *Needs a location*
filter), and — for the *On the map* column and its three states — `A4`/`A8`'s
own data (`lat`/`lng`/`gis_unchecked`).

> **This file records the GREY FRAME only.** The amber block is what a clerk
> hits today (the problem) and the teal *WHAT CHANGED* block is the argument.
> Neither is the specification. Where the teal block and the grey frame
> disagree, **the frame is the drawing** — see §*Two internal contradictions*
> at the foot of this file.

**Breadcrumb drawn above the frame:** `Premises → Premises`
**The question the screen answers:** *where is the property I am thinking of,
and which ones still need work?*

---

## Header

| slot | drawn string |
|---|---|
| kicker | `PREMISES & UNITS` |
| title | `Premises` |
| subtitle | `Every property that takes service, and the units inside them.` |

**No roll-up sentence is drawn.** The line under the title is the subtitle above
and nothing else.

## Actions — in the order drawn, left to right

| # | label | tier |
|---|---|---|
| 1 | `↑ Import` | secondary — outlined |
| 2 | `+ New premise` | **primary** — one filled button |

Detail table, verbatim: *"**+ New premise.** One filled button. *↑ Import* sits
beside it, outlined, because a portfolio arrives once and a single property
arrives every week."*

## Tabs — in order

`Premises` | `Units` | `Imports` — **`Premises` is the active tab.**

## Tiles

**None.** The screen draws no stat tiles and no KPI strip. This is a stated
absence: *"No prose on the screen at all — a list explains itself or it is the
wrong list."*

## Toolbar — in the order drawn

1. `Search premises…` (search box, left)
2. `ALL` (filter-state pill)
3. `+ Filter ˅`
4. `▦ Columns` (right-aligned, alone)

## Table columns — in order, with alignment

| # | drawn header | alignment | what the cell draws |
|---|---|---|---|
| 1 | `Premise ⇅` | left | `P-00080` — the printed reference, sortable |
| 2 | `Address ⇅` | left | **ONE cell, two lines** — street on the first line in the strong tone (`412 Cypress Row`), town and postcode beneath in the muted tone (`Silver Creek, TX 78611`). Sortable |
| 3 | `Type` | left | `Apartment complex` |
| 4 | `Units` | **right** | `4` |
| 5 | `Services` | left | letter squares — `E W S T` |
| 6 | `Owner` | left | `Creekside Holdings LP` |
| 7 | `On the map` | left | a status pill reading one of **three** states — `CHECKED` · `PLACED, UNCHECKED` · `NOT PLACED` |
| 8 | `Status` | left | `Active` |
| 9 | *(no header)* | right | row actions — icons: **eye · pencil · `…`** |

**Nine columns.** *"Nine columns, one search box, one filter row."*

**The `On the map` column is filterable, and it has THREE values, not two** —
*"because a point that arrived from an address lookup and a point a person has
seen against the city map are different degrees of confidence."*

## Footer

Left: `Showing 1–50 of 673 · Rows per page 50`
Right: `⇤` `←` `Page 1 of 14` `→` `⇥`

## States — the exact sentences

| state | what the frame says |
|---|---|
| **Nothing yet** | *The empty state names what is missing and offers the two ways to fill it — add one, **or import a list**.* |
| **Filtered to Not placed** | *The chip reads `Not placed ×` and the count in the footer is the size of the job.* |
| **Read-only role** | *Every figure, no buttons. The refusal names the role, never the screen.* |

## Components named by the drawing

`DataTable` · `FilterBar` · `RowActions` · `StatusPill` · `ListExportButton` ·
`OwnerMatchingPanel` · `InlineLinkTo`

## Rules the screen must obey

Table type is one size throughout. Row actions are icons with tooltips, never
text links, **two visible and the rest behind an overflow**. A pagination footer
on every list. A property number a clerk reads down the phone is a printed
reference and is shown; a database id never is.

## Cognitive-load budget

Nine columns, one search box, one filter row. **No prose on the screen at all.**

---

## Two internal contradictions in the source, recorded rather than resolved

1. **The `On the map` states.** The teal *WHAT CHANGED* block (page 7) and the
   drawn frame (page 6) both say **three** — `Checked` · `Placed, unchecked` ·
   `Not placed`. The grey detail table's *WHAT CHANGED · ONE NEW COLUMN* row on
   the same page says **two** — *"reading `Located` or `Not placed`"*. **The
   frame draws three and three is the specification**; `Located` appears nowhere
   in the drawing.
2. **The search placeholder.** The frame draws `Search premises…`, while the
   detail table's *WHAT DID NOT CHANGE* row says the toolbar is already right.
   B14 rule 19 requires the box to name what it matches. This is a drawing ↔
   design-system disagreement and is reported, not silently resolved either way.

   ⚠ **RULED 2026-09-10, AND THE RULE WINS HERE:** the box **KEEPS**
   `Search address, city, premise ID or owner…`. It is the one place on this
   plate where the drawn frame does NOT win, and the reason is the one §4 of
   the UI skill already gives — *where the wireframe and the design system
   disagree, the system wins*. `Search premises…` names the noun and not the
   legs, and `DEF-510`'s register row names this exact box as the reason rule
   19 exists: *"the premises search matches address, premise number, owner and
   city and a user has no way to learn that."* So the CONFORMANCE FILE is
   amended and the string is not: the built screen is right on this row and
   anybody diffing it against page 6 should read this paragraph rather than
   file it again.

---

## Amendments

**2026-09-10 · `DEF-4740` closed on this plate.** The `On the map` column is
built, drawn between `Owner` and `Status`, carrying the three states off
`lat`/`lng`/`gis_checked_at`; the location filter offers the same three
(`checked` · `placed_unchecked` · `needs_location`, the server's own value
strings) instead of the two it had; the address is one cell on two lines;
column 1 reads `Premise` and column 5 reads `Services`; the head carries the
`PREMISES & UNITS` kicker and `↑ Import`; and the empty state offers both drawn
ways out. **Still divergent, deliberately:** the pills are the kit's filled
`StatusPill` where the frame draws outlined ones (B14 rule 36 — comply through
the kit), and `Placed, unchecked` shares the quiet tone with `Not placed`
because the frame draws both in grey and only `CHECKED` in the accent.

**2026-09-19 · `DEF-MET-5851` — the head's one line is the DRAWN SUBTITLE at last.**
The screen drew a four-count roll-up where §Header says *"No roll-up sentence is
drawn"* and §Tiles says *"None. The screen draws no stat tiles and no KPI strip."*
It read `79 premises · 130 + 1 common units · 62 vacant · 4 pending activation`
and now reads `Every property that takes service, and the units inside them.` —
page 6's own string, B14 rule 41. The SLOT did not move: `page-header-rollup` is
the one line under the title, and the Units tab has filled it with a subtitle
since 2026-09-10; only what goes in it changed.

⚠ **THE FOUR COUNTS WERE WALKED TO THEIR DRAWN HOMES BEFORE THEY WERE REMOVED,
BECAUSE THIS PLATE'S STATED ABSENCE TAKES SOMETHING A CLERK HAS TODAY.** The home
this plate gives a count is §States' own sentence — *"the chip reads `Not placed ×`
and the count in the footer is the size of the job"* — and the same blueprint draws
a footer carrying a breakdown on page 24 (`Showing 4 of 4 · 3 occupied, 1 vacant`).
Measured in a browser on `brazosbend`, the figures are **identical**, not merely
close: the Premises footer reads **79**; `Status = Pending` narrows it to **4**; the
Units tab's footer reads **131**; `Occupancy = Vacant` narrows it to **62**.

**Still divergent, deliberately, and it is ONE figure:** `BR-MET-101`'s
`+ N common` split has no chip — the units list declares Occupancy, Plan, Premise
and Service, and `units_queryset` has no `is_common_area` branch — so that number
is reachable only on the **Imports** tab, where the roll-up still draws because no
plate in this folder covers that tab. Raised as `OQ-MET-12483` rather than
half-built, and **this paragraph is the answer to anybody who diffs the Imports tab
against page 6 and files it again.**
