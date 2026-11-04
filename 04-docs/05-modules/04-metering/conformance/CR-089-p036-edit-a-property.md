# P10 · Edit a property — THE DRAWN SPECIFICATION

**Source:** *Premises & Units Blueprint 2*, **pages 36–41** (plate header p36,
screen p37–p41). Extracted 2026-09-10 from
`origin/claude/confirm-understanding-3ktufc:05-prototype/Premises & Units Blueprint 2.pdf`
(md5 `f034d6e42c0caad658fadfdf6e4704eb`), read page by page with
`10-scripts/pdf/pdf_text.py` **and looked at** as rendered PNGs at scale 1.6 —
the layout, the column order and the group headings are DRAWN, not written, and
text extraction alone loses all three.

**State chip:** `EXISTS BEHIND` · **Commitments:** `PUJ-18` · `PUJ-19` · `PUJ-20`
**Screen ids:** `P10` — `PRM-02`
**CR-089 task rows:** **`B8`** (wave B — create and edit are the same screen,
`PUJ-18`) · **`A2`** (wave A — the reference field is renamed, `PUJ-20`) ·
**`A6`** (wave A — a point can be corrected, `PUJ-19`)

⚠ **EVERYTHING BELOW IS FROM THE BORDERED GREY FRAME ONLY.** The amber block on
page 37 is *what a clerk hits today* — the problem, not the target — and the teal
*WHAT CHANGED* block on page 39 is rationale. Neither is specification.

⚠ **THE VALUES ARE ILLUSTRATIONS; THE LABELS, THE ORDER AND THE PRESENCE OF EACH
ROW ARE THE SPECIFICATION** (the standing caveat in `09-screen-conformance.md`).

---

## Header

**Kicker** `PREMISE`
**Title** `Edit this premise`
**Sub-line** `Changes take effect at once. Everything is recorded.`

## Actions, in the order drawn

| # | label | tier | where |
|---|---|---|---|
| 1 | `Cancel` | secondary | top right of the frame, on the title row |
| 2 | `✎ Change these` | secondary | inside the map confirmation panel |
| 3 | `Change` | secondary | inside the owner confirmation card |
| 4 | `Cancel` | secondary | footer, left |
| 5 | `Save changes ✓` | **primary** | footer, right |

**Primary action:** `Save changes ✓` — *"The tick is the commit grammar."*

## Tabs

**None.** This screen has no tabs. (A stated absence — §2.5.)

## Tiles

**None.** This screen has no tiles.

## Groups and fields — FOUR named question-headings, in this order

⚠ **FOUR, drawn.** The blueprint contradicts itself here and the drawing wins
(§16): the teal *WHAT CHANGED* block says *"five question-headings"*, `PUJ-18` on
page 49 says *"the same six headings … Where is it? through What is inside it?"*,
and the frame's own `COGNITIVE LOAD` row says **"Fifteen fields in four named
groups"**. Four are drawn. There is no `What is inside it?` heading on the edit
form — that group belongs to the create form only.

### 1 · `WHERE IS IT?`

| # | label | drawn value | width |
|---|---|---|---|
| 1 | `Street address` **\*** | 412 Cypress Row | full row |
| 2 | `Town / city` | Silver Creek | 1 of 3 |
| 3 | `State` | TX *(select)* | 2 of 3 |
| 4 | `ZIP` | 78611 | 3 of 3 |

**Consequence box** (teal, immediately under the address row, inside the form):

* tag `CHANGING AN ADDRESS`
* body — one sentence pair, verbatim:
  `Four units, four meters, one route and two open work orders read this address. All of them follow it. The envelopes for the three open accounts change with the next bill run.`

**Map confirmation panel** (teal, headed with a tick), a FACT LIST of three rows —
not three input boxes:

| # | label | drawn value |
|---|---|---|
| 1 | `Parcel` | R-114-0082-004 |
| 2 | `Point` | 30.752104, −98.238391 · *placed by the address lookup* |
| 3 | `Checked against GIS` | `CHECKED` *(pill)* · D. Whitfield, 8 Sep 2026 |

* panel heading: `✓ On the city map`
* control beneath the rows: `✎ Change these` *(secondary)*
* helper beneath the control:
  `Changing the figures clears the checked flag, because the point it vouched for has changed.`

⚠ **THE PANEL IS THE SAME CONFIRMATION PANEL THE CREATE SCREEN DRAWS** — the
frame's own words. The three figures are read back as facts and edited behind
`✎ Change these`; they are not drawn as always-open numeric fields.

### 2 · `WHAT KIND OF PROPERTY IS IT?`

| # | label | drawn value | width |
|---|---|---|---|
| 1 | `Property type` **\*** | Apartment complex *(select)* | 1 of 2 |
| 2 | `Inside city limits` **\*** | Inside *(select)* | 2 of 2 |

helper under the pair: `These two decide which taxes and which rate the units here are billed on.`

| # | label | drawn value |
|---|---|---|
| 3 | `Utility services` | placeholder `Add a service this property can take…` *(select)* |

chips beneath, in this order: `ELECTRIC ×` · `WATER ×` · `SEWER ×` · `TRASH ×`
helper beneath the chips: `Removing one is refused while a unit here still meters it.`

### 3 · `WHO LOOKS AFTER IT?`

| # | label | drawn value | width |
|---|---|---|---|
| 1 | `Owner` | placeholder `Search by name, or clear it…` | full row |

**Owner confirmation card** beneath it: `Creekside Holdings LP` · Landlord —
second line `Owns 3 properties · master account A-10442` — with a `Change`
control on the right.
helper beneath the card: `Clearing it puts this property on the Needs an owner list.`

⚠ **BUILT 2026-09-22 (`CR-130-BRC07` lane C2), AND THREE THINGS DIVERGE FROM THE
DRAWING ABOVE. EACH IS STATED RATHER THAN ABSORBED (B14 rule 41).**

The drawn SHAPE is built exactly — a search box labelled `Owner`, a confirmation
card beneath it, a `Change` control on the right, `Managed by` below with
`Only if different.` **What the search searches has changed, and the drawing
could not have anticipated it:** the PO ruled on 2026-09-22 that *"owner IDs are
not required hence no screens or fucntionality for it"*, so the control searches
the tenant's **MASTER ACCOUNTS** and no screen creates, picks or searches an
owner record. Before that day it searched owner records and offered **0 options**
on this form, measured in a browser — the cupboard nobody could fill
(`DEF-MET-6155`).

| drawn | built | why |
|---|---|---|
| line 1 `Creekside Holdings LP` · `Landlord` | the account's NAME alone | `Landlord` is the OWNER RECORD's category and there is no owner record under the ruling |
| line 2 `Already owns 3 properties · master account A-10442` | `AC-2026-00051` | the PO's *"we ahve to use one volcabory"* retires the words *master account*; the NUMBER is what a clerk reads (B14 rule 31). A ruling dated 2026-09-22 outranks a drawing dated 2026-09-10 |
| `Already owns 3 properties` | **not drawn yet** | the wire carries no count. Rendering zero would say the opposite of what it means, so the line appears the moment a count arrives — `MasterAccountSearch.dom.test.tsx` proves that branch today rather than when it lands |

⚠ **AND THE DRAWING WAS RIGHT ABOUT TWO WORDS THE PRODUCT HAD WRONG.** It labels
this row `Owner` and the box below it `Managed by`; the product said
*Owner (record)* and *Owner / manager*, two of the five wordings the PO counted.
**The drawing and the ruling agreed with each other and not with the screen.**

| # | label | drawn value | width | helper |
|---|---|---|---|---|
| 2 | `Managed by` | Cane Island Property Co | 1 of 3 | `Only if different.` |
| 3 | `Area` | North Silver Creek *(select)* | 2 of 3 | `The district.` |
| 4 | `Sub-area` | Cypress Row *(select)* | 3 of 3 | `Narrowed to that district.` |

### 4 · `READING AND BILLING` — carries an `optional` chip on the heading

| # | label | drawn value | width | helper |
|---|---|---|---|---|
| 1 | `Read route` | Route 12 — North Silver Creek *(select)* | 1 of 2 | `Changing it moves the property to another reader's round.` |
| 2 | `Billing cycle` | Cycle 3 — bills on the 12th *(select)* | 2 of 2 | `Takes effect at the next run, never mid-cycle.` |

## Tables

**None.** The map and owner panels are fact lists, not tables.

## Footer

`Cancel` *(secondary, left)* · `Save changes ✓` *(primary, right)*.

## States — exact sentences

| state | drawn sentence |
|---|---|
| **Already billed** | `The address stays editable — a wrong address on an issued bill is exactly what wants correcting — and the consequence box says which bills carry the old one.` |
| **The point is changed** | `The GIS-checked flag clears, because the point it vouched for has changed.` |
| **Read-only role** | `Every value, no save. The refusal names the role.` |

No empty state and no loading state is drawn for this screen.

## Frame metadata

* **FOR** — `A clerk correcting a record that is already live — a mistyped street, a property that was placed on the wrong side of the road, an owner who has sold up.`
* **HOW YOU GET HERE** — `The property's page → ✎ Edit. Also from the list's row action, which opens the same form.`
* **COGNITIVE LOAD** — `Fifteen fields in four named groups, one confirmation panel, one consequence box. The same fields as today, grouped by the question they answer.`
* **COMPONENTS** — `PremisesEditModal` `FindTheAddress` `JurisdictionField` `OwnerField` `ServicesAvailableField` `FormModal` `RefusalStrip`
* **RULES** — `A consequence preview before any commit that changes service state, and an address is exactly that. Required asterisks only where the server insists. A multiple choice is chips plus an add control.`

## Commitments this screen carries

| id | statement | done looks like (verbatim) |
|---|---|---|
| `PUJ-18` | Edit a property matches create, section for section | `The edit form carries the same six headings in the same order as the create form — Where is it? through What is inside it? — with the same labels and the same required marks.` |
| `PUJ-19` | A property's point can be corrected | `A clerk opens the edit form for a property placed on the wrong side of the street, changes 30.752104, −98.238391, saves, and the map pin moves with it.` |
| `PUJ-20` | *External / GIS ref* becomes *Parcel ID* | `The field is labelled Parcel ID on create, edit and the property's page, and holds R-114-0082-004.` |

⚠ **`PUJ-20`'s wording and the drawing disagree, and the drawing wins:** the grey
frame labels the row **`Parcel`**, the teal block says *Parcel number*, `PUJ-20`
says *Parcel ID*. Three names for one field, in one document. Recorded here
rather than resolved — a divergence agreed with the PO belongs in
`09-screen-conformance.md`, dated, with the ruling.

⚠ **`PUJ-18`'s *six headings* is the same class of conflict** — the frame draws
four and its own `COGNITIVE LOAD` row says four.

---

## Amendments

**2026-09-10 · `DEF-4741` closed on this plate.** `PremisesEditModal` imported
`ConsequenceBox` zero times and now renders it under the address row, tagged
`CHANGING AN ADDRESS`, in the kit's `move` tone — B14 rule 11 requires one
before any commit that changes service state, and moving an address moves which
taxes and which rate apply.

⚠ **THE BOX CARRIES NO COUNTS AND THE DRAWN SENTENCE DOES.** The frame reads
*"Four units, four meters, one route and two open work orders read this
address… the three open accounts…"* — and the standing caveat on every plate is
that the VALUES are illustrations. `PremisesRow` carries a unit count and none
of the other four, so a sentence built from it would be three invented numbers
beside one real one. What is true of every property is said instead:
*"Everything here follows the address. The meters, the route and any open work
orders move with it, and the envelopes change at the next bill run."* Serving
the real five would need a new endpoint; that is not this pass's to invent and
is worth raising.

**STILL OPEN on this plate**, and it is the group structure rather than a
field: the edit form still draws the six statement-form sections
(`where` · `map` · `kind` · `belongs` · `services` · `owner`) where the frame
draws **four question-headings**. `premisesFormSections.tsx` was re-cut to the
four on the same day by the create-form lane, which left
`RETIRED_SECTION_LABELS` behind so the edit form keeps resolvable headings in
the meantime and named this file as what re-cuts it. The follow-up is one
commit: re-group the edit modal onto `where` (address **and** the parcel/point
confirmation) · `kind` (type, city limits **and** utility services) · `owner`
(owner, managed by, area, sub-area) · `readingBilling`, then delete
`RETIRED_SECTION_LABELS` and restore `expect(edit).toEqual(declared)` in
`PremisesFormSections.test.tsx`.

## ⚖ PO RULING 2026-09-10 — THE ADDRESS WARNING CARRIES NO COUNTS

The frame draws the consequence box with **five counts** — four units, four
meters, one route, two work orders, three accounts. **Only the unit count is
served.** Three of the five would have been invented.

Put to the PO as three options — build an endpoint for all five, keep the
general sentence, or show the single count we hold — and the ruling was **(b),
keep the general sentence**, with the endpoint worth building whenever somebody
is next in it.

So the box says what is true of EVERY property:

> **CHANGING AN ADDRESS** · *Everything here follows the address.*
> *The meters, the route and any open work orders move with it, and the
> envelopes change at the next bill run.*

**Do not file this as a divergence.** It is a decision, and the reasoning is
that a clerk about to move an address needs to know *what follows* — which that
sentence says — and the counts make it concrete without being what stops a
mistake.

