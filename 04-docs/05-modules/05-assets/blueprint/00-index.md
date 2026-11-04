# Assets blueprint — screen → page map

**Source.** `05-prototype/01 Assets Menu Blueprint.pdf` — 9,913,838 bytes, **219 pages,
of which 213 carry content**; pages 214–219 are blank (each renders to the identical
2,762-byte all-white PNG).

**How this map was made.** Every page was rendered to PNG with
`10-scripts/pdf/pdf_render.py` at scale 1 (792×612, 3 channels, 6.8 s for all 219) and
the map was built by **looking at the pictures**, per B14 rule 42 (PO 2026-09-13:
*"When you use images to create screens your accuracy is higher; hence dont create
screens using only Text"*). The text layer was used only to find candidate pages and to
spell names; **all 35 screen headers below were then opened as images and confirmed
one by one — 35 of 35 matched, zero discrepancies.** Routes are transcribed off the
image, not the text layer, because the text extractor mangles the monospace route lines
(it returns `tenantassetseassetIdftabreads` for `/:tenant/assets/{assetId}?tab=reads`).

> ⚠ **Re-render before use.** `pypdfium2` was absent from every Python in this container
> on 2026-09-13 and had to be installed before `pdf_render.py` would run. If the script
> raises `ModuleNotFoundError`, that is why.

## What kind of document this is — read this before building anything from it

**It is not a wireframe deck. It is a module analysis, and it draws the product as it
was as well as the product as it should be.** Building to the wrong half rebuilds the
drift instead of removing it. Page 1 and page 3 state the convention, and it is
visual:

| Marker | What it is | Build to it? |
|---|---|---|
| **Description — grey rail** | *"A statement about what the code does today, including an honest statement that something is missing. **It commits nobody to anything.**"* | **No** |
| **Commitment — accent card** (red, interrupts the rail) | *"A change specification: a named piece of work, what it waits on, the screens it changes, and what a person could do and see once it is done."* | **Yes** |

*"If a thing is not in a commitment card, nobody has undertaken to build it."* (p2, p3, p157)

Four state chips and only four, on every screen header: **EXISTS BEHIND · NEW READ ·
NEW BUILD · BLOCKED**. A screen no specification covers carries **NO COMMITMENT**, and
p3 says that absence *"is the finding, not an oversight"*.

**The commitment ids are `AST-B-##` and they are NOT repo-live.** p157: *"a new series
opened for this document. The repository's live series are `US-AST-###`, `BR-AST-###`,
`OQ-###` and `DEF-###`, and allocating into any of them would make this analysis look
like scheduled work when it is not."* **`AST-B-01` … `AST-B-28` is the whole series and
FOUR of the 28 are withdrawn, not three.** The document's section 12 names
`AST-B-07`, `-08` and `-09` (the import runner, out of scope 2026-09-11); the module's
own `08-screen-layouts.md` names a fourth, **`AST-B-17`** — a registry-wide Work orders
tab, *"withdrawn the day it was drawn by PO instruction"*. 28 − 4 = **24 live
specifications**, which is exactly the cover's figure, and the cover's
`WITHDRAWN, NOT REUSED 4` says the same thing. Every live one still needs a real repo id
allocated before it is cited in code.

**Three figures on the cover that bound the job:** 35 screens · 56 wireframes drawn ·
24 specifications · 6 remedy drawings · 12 rule violations · 49 stated absences ·
3 dead controls · 9 journey issues.

### The document is stale in a known, bounded way

It was **read at product version `2.234.17`, commit `79c659d7`, on 2026-09-10 and
re-measured 2026-09-11**. The product is at **`2.261.3`** today (2026-09-13) — 27
change-level versions on. p2 states exactly what that costs: *"What goes stale here,
and what does not. This warning covers **descriptions** — every sentence about what the
code does today, every field table, every route, every measured figure, and every
drawing of a screen as it is. **It does not cover rulings.**"*

**So every as-built claim in this document is a hypothesis to re-verify against the
running app, and every commitment and ruling stands until somebody changes the code.**

### Scope, stated once by the document itself

p2: *"the registry draws **seven** tabs and this document covers **six**. The Imports tab
and the five-stage import runner behind it left this document by instruction on
2026-09-11. That is scope, not a defect, and nothing here describes them."*

**`/assets/import` is therefore outside this blueprint.** It is a live product screen
(`AssetImportWorkflow.tsx`, `AssetImportsTab.tsx`) and this document says nothing about
it, so nothing here licenses changing it.

### How the drawings are made (p3–p4)

* **Desktop only** — one drawing per screen at a fixed **1440** viewport, scaled to fit
  its box as a unit and **never reflowed**. No phone screens, ever.
* **Side rail, never top nav** — every signed-in drawing shows the left rail with
  thirteen items.
* Every figure is labelled `FIGURE n · DESKTOP · 1440, SCALED TO FIT · NEVER REFLOWED`.
  **56 figures, numbered 1–56**; a screen may carry an as-built AND a redrawn figure,
  and seven carry a class variant as well.

> ⚠ **The document says B14 has "38 binding UI rules" (p3). Do not take that number.**
> CLAUDE.md is explicit that this count has been wrong six times and that you must count
> B14's own status table. B14 numbers 1–21 and 31–42; 22–29 were never minted and 30 was
> declined.

## Sections

| § | Title | Pages |
|---|---|---|
| — | Cover, how to read it, what was measured | 1–2 |
| 01 | The standards every screen here is drawn to | 3–4 |
| 02 | The list — one page, six tabs (screens 01–07) | 4–33 |
| 03 | One asset — read it, and change it (screens 08–13) | 34–71 |
| 04 | Asset edits — what each pencil opens (screens 14–21) | 72–84 |
| 05 | Actions — moving it, fixing it, retiring it (screens 22–27) | 85–107 |
| 06 | Adding an asset — the four steps and the commit (screens 28–33) | 108–124 |
| 07 | What happened when the product was actually driven (6 journeys) | 125–127 |
| 08 | Everything the product says it cannot do, and one ruling each | 128–134 |
| 09 | Where these screens break their own rules (12 violations) | 135–138 |
| 10 | **Drawn answers to the findings worth drawing — remedies R1–R6** | 139–151 |
| 11 | What crosses a module boundary, and whether it holds | 152–155 |
| 12 | **Every commitment, in one place — the 24 specifications** | 156–160 |
| 13 | What this pass changed, line by line | 161–174 |
| 14 | Appendices A–L | 175–213 |
| — | *(blank)* | 214–219 |

Section 08's sub-lists: A things a person is told cannot be done (17) p129 · B server
refusals (13) p131 · C honest empties (11) p132 · D copy that reaches nobody (1) p133 ·
E absences found later (7) p134.

Section 14's appendices: **A** every rule this document states p175 · **B** every worked
figure verbatim p179 · **C** every screen with its exact contents p181 · **D** decisions
recorded here and nowhere else p188 · **E** every guarantee and what enforces it p191 ·
**F** what this document assumes and never says p192 · **G** every UI rule violation
p194 · **H** every cross-module finding p195 · **J** health and what each grade rests on
p196 · **K** everything an upgrade would drop, and who ruled it p209 · **L** every
drop-down and where its options come from p210. *(There is no appendix I.)*

## The 35 screens

Page ranges run from each screen's header to the page before the next header. `Fig` is
the as-built figure number; screens marked NEW BUILD are drawn to the rules rather than
read off the code.

### § 02 · The list — one page, six tabs

| # | Screen | Pages | Fig | Route (read off the image) | Chips | Commitments |
|---|---|---|---|---|---|---|
| 01 | Meters | 5–10 | 1 | `/:tenant/assets?tab=meters` · also the bare `/:tenant/assets` | EXISTS BEHIND · NEW READ | 01, 15, 20 |
| 02 | Sub-meters | 11–12 | 2 | `/:tenant/assets?tab=sub_meters` | EXISTS BEHIND | 01, 15, 20 |
| 03 | Behind the meter | 13–15 | 3 | `/:tenant/assets?tab=behind_the_meter` | EXISTS BEHIND · NEW READ | 01, 15, 20 |
| 04 | Inventory | 16–18 | 4 | `/:tenant/assets?tab=inventory` | EXISTS BEHIND | 01, 15, 20 |
| 05a | Lifecycle · Certifications & tests due | 19–21 | 5 | `/:tenant/assets?tab=lifecycle&section=certifications` | **NEW BUILD** | 11, 15 |
| 05b | Lifecycle · Warranty & supplier | 22–24 | 6 | `/:tenant/assets?tab=lifecycle&section=warranty` | **NEW BUILD** | 11, 15 |
| 05c | Lifecycle · Age & replacement forecast | 25–28 | 7 | `/:tenant/assets?tab=lifecycle&section=forecast` | **NEW BUILD** | 11, 15 |
| 06 | Map | 29–31 | 8 | `/:tenant/assets?tab=map` | EXISTS BEHIND | 06, 15 |
| 07 | Assign 3 assets to a unit | 32–33 | 9 | *no address of its own — a dialog on* `/:tenant/assets` | EXISTS BEHIND · **NO COMMITMENT** | — |

### § 03 · One asset — read it, and change it

| # | Screen | Pages | Fig | Route | Chips | Commitments |
|---|---|---|---|---|---|---|
| 08 | Overview | 34–46 | 10–19 | `/:tenant/assets/{id}` | EXISTS BEHIND · **NEW BUILD** | 12, 16, 22 |
| 09 | Reads | 47–52 | 20 | `/:tenant/assets/{assetId}?tab=reads` | EXISTS BEHIND | 19, 23, 24 |
| 10 | Export | 53–54 | — | `/:tenant/assets/{assetId}?tab=export` — *an inverter whose linked meter is a net meter, only* | EXISTS BEHIND · **NO COMMITMENT** | — |
| 11 | Assignment history | 55–57 | — | `/:tenant/assets/{assetId}?tab=assignments` | EXISTS BEHIND | 19, 23 |
| 12 | Work & maintenance | 58–62 | — | `/:tenant/assets/{id}?tab=work` | EXISTS BEHIND · **NEW BUILD** | 02, 18, 19, 21, 23 |
| 13 | Audit | 63–65 | 20 | `/:tenant/assets/{assetId}?tab=audit` | EXISTS BEHIND · **NO COMMITMENT** | — |

### § 04 · Asset edits — what each pencil opens

| # | Screen | Pages | Fig | Route | Chips | Commitments |
|---|---|---|---|---|---|---|
| 14 | Edit one asset | 66–69 | 21 | `/:tenant/assets/{assetId}/edit` — **a full page, replacing today's dialog** | **NEW BUILD** | 12, 13, 26 |
| 15 | Delete this asset? | 70–71 | 22 | *no address — a confirm on* `/:tenant/assets` *and* `/:tenant/assets/{id}` | EXISTS BEHIND · **NO COMMITMENT** | — |
| 16 | Edit · What's due | 73 | 23 | Modal over `/:tenant/assets/{id}` · `PATCH /assets/{id}` | **NEW BUILD** | 13, 25, 26 |
| 17 | Edit · Measurement | 74–75 | 24 | Modal over `/:tenant/assets/{id}` · `PATCH /assets/{id}` | **NEW BUILD** | 13, 25, 26 |
| 18 | Edit · Measurement · confirm | 76–77 | 25 | *the second step of the same modal — no second address* | **NEW BUILD** | 13, 25, 26 |
| 19 | Edit · Device | 78–79 | 26 | Modal over `/:tenant/assets/{id}` · `PATCH /assets/{id}` | **NEW BUILD** | 13, 25, 26 |
| 20 | Edit · Cost & value | 80 | 27 | Modal over `/:tenant/assets/{id}` · `PATCH /assets/{id}` | **NEW BUILD** | 13, 25, 26 |
| 21 | Edit · Lifecycle | 81–84 | 28 | Modal over `/:tenant/assets/{id}` · `PATCH /assets/{id}` | **NEW BUILD** | 13, 25, 26 |

*Screen 14's page 72 carries the section head "04 · Asset edits — what each pencil opens".*

### § 05 · Actions — moving it, fixing it, retiring it

| # | Screen | Pages | Fig | Route | Chips | Commitments |
|---|---|---|---|---|---|---|
| 22 | Reassign | 86–90 | 29–31 | `/:tenant/assets/{assetId}/reassign` · `?unit={id}` preselects a destination | EXISTS BEHIND | 26 |
| 23 | Log repair / maintenance | 91–94 | 33 | `/:tenant/assets/{assetId}/maintenance/new` — *titled* Log test *on a device with a cadence* | EXISTS BEHIND · **NEW BUILD** | 04, 13, 26 |
| 24 | Retire · 1 Reason & final read | 95–97 | 35 | `/:tenant/assets/{assetId}/retire` — step 1 | EXISTS BEHIND | 26, 28 |
| 25 | Retire · 2 Replacement | 98–100 | 37 | `/:tenant/assets/{assetId}/retire` — step 2 | EXISTS BEHIND | 26, 28 |
| 26 | Retire · 3 Book value | 101–103 | 39 | `/:tenant/assets/{assetId}/retire` — step 3 | EXISTS BEHIND | 26, 28 |
| 27 | Raise work order | 104–107 | 41 | `/:tenant/assets/{assetId}/work-orders/new` | EXISTS BEHIND · **NEW BUILD** | 02, 05, 10, 26 |

*Screen 22's page 85 carries the section head "05 · Actions — moving it, fixing it, retiring it".*
*Screens 22–27 each carry a REDRAWN figure beside the as-built one (figs 30, 32, 34, 36, 38, 40, 42).*

### § 06 · Adding an asset — the four steps and the commit

| # | Screen | Pages | Fig | Route | Chips | Commitments |
|---|---|---|---|---|---|---|
| 28 | Add an asset · 1 Identity | 109–112 | 43 | `/:tenant/assets/new?class=meters` | EXISTS BEHIND · **NEW BUILD** | 03, 26, 27, 28 |
| 29 | Add an asset · 2 Specification | 113–115 | 45 | `/:tenant/assets/new?class=meters` | EXISTS BEHIND · **NEW BUILD** | 14, 26, 27, 28 |
| 30 | Add an asset · 3 Assignment | 116–117 | 46 | `/:tenant/assets/new?class=meters` | EXISTS BEHIND · **NEW BUILD** | 26, 27, 28 |
| 31 | Add an asset · 4 Lifecycle | 118–119 | 48 | `/:tenant/assets/new?class=meters` | EXISTS BEHIND · **NEW BUILD** | 26, 27, 28 |
| 32 | Add an asset · 5 Review & add | 120–121 | 49 | `/:tenant/assets/new?class=meters` · `POST /assets` | **NEW BUILD** | 26, 28 |
| 33 | Drafts | 122–124 | 50 | `/:tenant/assets?drafts=1` — **proposed** · `GET /wizard-parks?flow=add_asset,retire_asset` | **NEW BUILD** | 28 |

*Screen 28's page 108 carries the section head "06 · Adding an asset — the four steps and the commit".*

## The remedies — § 10, pages 139–151

These are the drawn answers, and p139 states two rules that govern reading them:

* **"A remedy never loses anything."** Every field and every piece of information
  architecture on the as-built drawing survives into the remedy — grouping, order, tabs,
  hierarchy, words — *"unless somebody has ruled that it goes and the ruling is quoted.
  Each remedy carries a carry-over table and the arithmetic must reconcile."*
* ⚠ **THE DOCUMENT CONTRADICTS ITSELF ON THE ONE REMOVAL, AND THIS INDEX REPEATED ONE
  SIDE OF IT.** Page 139 says *"Across all six remedies in this document, exactly one
  thing is removed — the dialog frame on screen 18 … Appendix K carries that one row and
  nothing else."* **Appendix K itself, read as an image on p210, opens: *"Two rows, and
  both carry a quoted ruling. Rows with no quoted ruling: 0."*** The two rows are the
  dialog frame around **the edit form (screen 14, not 18)** and **screen 05c's Asset
  value panel**. Screen 18 removes nothing. p210 also names a near-third: R2's four row
  actions moving into an overflow menu, graded **MOVED** rather than removed *"so a
  reader who believes demoting a control into an overflow is a removal … can argue the
  point — and they would not be wrong to."*
  **Take appendix K, not the p139 summary**: the appendix is the enumeration and the
  summary is a sentence about it. Found by the lane auditing screens 14–21 and verified
  here against the page image before this correction was written.
* Screens **05a–05c** and **screen 18** are whole screens rather than changes to one, so
  they are drawn as numbered remedies **in section 02 rather than in section 10**, beside
  the as-built they replace.

| Remedy | Subject | Page |
|---|---|---|
| R1 | The asset gets the two doors its own rule already names (`AST-B-02`) | 140–141 |
| R2 | KPI figures — a new aggregate read over the whole filtered set, not the page | 142–143 |
| R3 | Asset # helper moves below its input | 144–145 |
| R4 | Label → input → helper | 146 |
| R5 | The opening read becomes a field a person can fill in (`AST-B-14`) — **overturns a ruling recorded earlier in the same document** | 147–149 |
| R6 | The description — the tab's own explainer, in the slot the toolkit already has (B14 rule 18) | 151 |

## The commitments — § 12, pages 156–160

One row per specification: **ID · what a person could do and what it waits on · which
screens · what done looks like on screen · status**. Every status reads **Unverified**,
and p157 says that is not a hedge: *"Engineering fills the column in from the code, one
row at a time, and on a module this well documented several will come back already
done."*

**That last sentence is this session's first job on the build side** — the document was
read 27 versions ago, so some of these 24 are already built.

## Four of these screens are ALREADY BUILT — read this before auditing them

`04-docs/05-modules/05-assets/08-screen-layouts.md` (created 2026-09-12 by `CR-092-BRC01`)
independently corroborates every headline figure in this index — 35 screens, 56
wireframes, 137 fields, 24 specifications, 49 absences, same version `2.234.17`, same
commit `79c659d7` — and it records something the PDF cannot, because it post-dates it:

| Screen | State | Version |
|---|---|---|
| 05a Lifecycle · Certifications & tests due | **BUILT** | `2.237.5` |
| 05b Lifecycle · Warranty & supplier | **BUILT** | `2.237.5` |
| 05c Lifecycle · Age & replacement forecast | **BUILT** | `2.237.5` — the Asset value panel REMOVED on a quoted PO instruction; Programme total and Turn-into-work KEPT |
| 14 Edit one asset | **BUILT** | `2.239.9` |

**So the drawing for those four is the REMEDY drawing and the code was built to it.**
They are not greenfield and they are not untouched; they are the one part of this module
where a drawing has already been followed.

**Two things in 05a–05c were deliberately NOT built**, each recorded on its own row: the
pager's first/last page control (out of scope by PO ruling 2026-09-12, its own CR) and
**server-side paging of `GET /assets/lifecycle` — `DEF-MET-4962`, still open**. The three
tables search, sort, filter and page **in the browser over the whole payload**. That is a
live `NFR-3` breach of the same shape CLAUDE.md already names four times (`DEF-PAY-4221`):
correct at T7, wrong at T5.

**Screen 14 carries a known open defect, `DEF-AST-5107`:** the drawing's field table names
`manufacturer_model` where the drawing itself writes `location_note`. The field set was
read from `AssetFormModal` and read wrongly, and **the reconciliation arithmetic beside it
cannot see a SWAP, because a swap leaves the count right.** `location_note` IS editable —
on the Lifecycle panel dialog (`AST-B-25`).

## Rule 37 bites hard here, and the document says so itself

The walk behind this document ran against **a tenant holding 126 assets, and no tenant
holds 126 today** — the figures are 14 / 74 / 135. **Every row count, every pager figure
and every KPI number drawn in this PDF needs re-measuring before it is trusted**, and none
of them may be asserted in a test or seeded into a fixture (B14 rule 37).

## Ten capabilities have no drawing yet, and they are gated on the PO

`08-screen-layouts.md` records that ten new capabilities were added to scope on 2026-09-12
and that several **have no screen at all today** — an edit address for an asset, the
attention strip on the Overview header, the six per-panel edit dialogs. The standing rule
for that case is the PO's own ruling of 2026-09-10: **draw it, show it, then build — and
the middle step is not optional.** Those items cannot be built from this PDF, because this
PDF does not draw them.

## Nothing here reads the Assets drawing automatically

`10-scripts/gates/g105_screen_matches_its_drawing.py` is the one gate in this repository
that compares a built screen with its layout drawing, and **line 173 hardcodes the PORTAL
drawing** (`04-docs/05-modules/15-portal/08-screen-layouts.md`). It does not look at
Assets. That is the mechanical reason these screens can drift from this document and
nothing goes red — and it is the same shape as the twenty-five portal screens G105 was
written for.

## What this map is not

It is a map. It is not a specification, not a diff, and not evidence that any screen
matches its drawing. **Nothing in this repository has ever diffed the Assets screens
against this PDF.** The nine `CR-092-*` records in
`04-docs/05-modules/05-assets/conformance/` were written against the r10 prototype, not
against this document.
