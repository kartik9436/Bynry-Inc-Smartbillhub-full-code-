# P2 · Add a property · Details — the DRAWN specification

> ⚠ **SUPERSEDED 2026-10-09 BY `CR-177-BRC10` (Add a premise, redesigned; PO GO of that date).** The screen this file specifies is redrawn: *Property · Units · Review* with no *How many?* step, one *Address* section with *Check address*, Owner by search and link, and a grouped *Check before saving*. The drawing is `05-prototype/add-premise-2026-10-09/`; the rules are `BR-MET-1190`–`1195` (`02-business-rules.md`). Read this file as history, not as the specification.

`S16 · PRM-07` — **state chip: `EXISTS BEHIND`**
Blueprint *Premises & Units Blueprint 2*, **page 8** (screen head and amber
block) → **page 15** (rules row). The grey frame is drawn across **pages 9, 10
and 11**.

**Commitment chips on the screen:** `PUJ-02` · `PUJ-03` · `PUJ-04` · `PUJ-05` ·
`PUJ-06` · `PUJ-18` · `PUJ-20`.
**CR-089 task rows this screen belongs to:** `A2` (parcel on the create form) ·
`A4` (coordinates, parcel and the GIS flag at creation) · `A5` (the lookup
reports its own failure) · `B1` (owner optional, required fields marked) ·
`B3` (the owner search says what that owner already owns) · `B4` (utility
services as a searchable multi-select) · `B5` (common areas at creation) ·
`B6` (route and cycle settable at creation) · `B8` (create and edit are the
same screen).

> **This file records the GREY FRAME only.** The amber block is the problem and
> the teal *WHAT CHANGED* block is the argument.

**Breadcrumb drawn above the frame:** `Premises → New premise → step 2`
**The question the screen answers:** *what do you need from me to put this
building on the books?*

---

## Header

| slot | drawn string |
|---|---|
| kicker | `PREMISES & UNITS` |
| title | `Add a premise` |
| subtitle | `One property, with its first unit if you want one.` |

## Actions — in the order drawn

**In the header, top right:**

| # | label | tier |
|---|---|---|
| 1 | `Cancel` | secondary |
| 2 | `Save draft & exit` | secondary |

*"`Save draft & exit` sits in the header rather than the footer, because parking
a half-finished property is leaving, not advancing."*

**In the footer:**

| # | label | tier |
|---|---|---|
| 1 | `← Back` | secondary |
| 2 | `Continue →` | **primary** — one filled button |

**Inside the frame, as part of a block rather than a page action:**
`Mark checked` · `✎ Change these` (both in the *Found on the city map* panel) ·
`Change` (in the chosen-owner card).

## The step rail — in order

`✓ One premise` | `2 Details` | `3 Review & save`

**Step 1's finished label reads `One premise`, NOT `How many?`.** *"A finished
step says what you chose, not what it asked. The rail read ✓ How many after you
had answered it; it now reads ✓ One premise."*

## Tabs

**None.** A wizard step draws no tab strip.

## Tiles

**None.**

## Sections and fact/field rows — every label, in the drawn order

**The section headings are QUESTIONS, not categories.** *"A person filling a
form is answering questions, and a heading that asks one is easier to answer
than a heading that names a database table."*

### 1 · `WHERE IS IT?`

| # | drawn label | control / row shape | help line drawn beneath |
|---|---|---|---|
| 1 | `Street address *` | one **wide** field, full width | `Start typing and we will look it up.` |
| 2 | `Town / city` | first of a three-up row, **wide** | *(none — "its label is the whole of it")* |
| 3 | `State` | second of that row, **small** | — |
| 4 | `ZIP` | third of that row, **small** | — |

Then, **inside the same section**, a green confirmation panel — not four more
inputs:

> **`✓ Found on the city map`**
>
> | drawn label | value as drawn | control on the row |
> |---|---|---|
> | `Parcel` | `R-114-0082-004` | — |
> | `Point` | `30.752104, −98.238391` | — |
> | `Checked against GIS` | `Not checked yet` *(absent style)* | `Mark checked` |
>
> and one control at the foot of the panel: `✎ Change these`

*"What the lookup found is a confirmation, not four more boxes. A clerk reads
them; they only edit them when the lookup is wrong."*

### 2 · `WHAT KIND OF PROPERTY IS IT?`

| # | drawn label | row shape | help line |
|---|---|---|---|
| 1 | `Property type *` | left half of a two-up row | *(shared, see below)* |
| 2 | `Inside city limits *` | right half of that row | *(shared)* |

Shared help beneath the pair:
`These two decide which taxes and which rate the units here will be billed on.`

| # | drawn label | control | help line |
|---|---|---|---|
| 3 | `Utility services` | a **searchable multi-select**: one box with the placeholder `Add a service this property can take…`, chosen ones beneath as removable chips — `ELECTRIC ×` `WATER ×` `SEWER ×` `TRASH ×` | `Type to filter all eleven. Only what this utility sells is offered.` |

### 3 · `WHO LOOKS AFTER IT?`

| # | drawn label | control | help line |
|---|---|---|---|
| 1 | `Owner` | a **search** box, placeholder `Search by name, or leave it for later…` | *(none)* |

Beneath it, when one is chosen, a result card — **and it is one line of fact,
not a second field**:

> **`Creekside Holdings LP`** · `Landlord`
> `Already owns 3 properties · master account A-10442`      `Change`

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

| # | drawn label | row shape | help line |
|---|---|---|---|
| 2 | `Managed by` | first of a three-up row, **wide** | `Only if different.` |
| 3 | `Area` | second of that row | `The district.` |
| 4 | `Sub-area` | third of that row | `Narrowed to that district.` |

**Area and sub-area are TWO controls, not one** (PO, this session: *"these
should be 2 input fileds - Area · sub-area - not 1"*), the second narrowed by
the first, one column stored.

### 4 · `READING AND BILLING` `optional`

The heading itself carries an `optional` chip — *"the optional section says it
is optional, on the heading, so a clerk in a hurry knows what they may skip."*

| # | drawn label | row shape | help line |
|---|---|---|---|
| 1 | `Read route` | left half of a two-up row | `Who reads the meters here.` |
| 2 | `Billing cycle` | right half of that row | `When it bills.` |

**TWO separate fields.** Values as drawn: `Route 12 — North Silver Creek` and
`Cycle 3 — bills on the 12th`.

### 5 · `WHAT IS INSIDE IT?`

| # | drawn label | row shape | help line |
|---|---|---|---|
| 1 | `How many units?` | left half of a two-up row, a **number** (`4`) | *(none)* |
| 2 | `Unit type` | right half of that row (`Residential`) | *(none)* |
| 3 | `Common areas` | a multi-select, placeholder `Add a shared space this property meters…`, chosen ones beneath as removable chips — `LAUNDRY ×` `CORRIDOR LIGHTING ×` | `A shared space with its own meter. It bills to the owner, not to a resident.` |

**`How many units?` is a NUMBER, not a tick-box.** *"'Also create a unit
automatically' becomes 'How many units?' — a four-flat building is recorded in
one pass instead of one flat plus three trips through a pattern generator."*

## Required marks

**Exactly three asterisks are drawn**, and only on what the server will actually
insist on: `Street address *`, `Property type *`, `Inside city limits *`.
The owner carries **no** asterisk — ruled 8 September, *not required at all*.

## Table columns

**None.** This screen holds no table.

## Footer

`← Back` (left) · `Continue →` (right, primary). No audit line is drawn on this
step.

## States — the exact sentences

| state | what the frame says |
|---|---|
| **The lookup answers** | *The two figures fill in and `Placed by` reads `The address lookup`.* |
| **The lookup is unavailable** | *One line in the block: **address lookup unavailable**. The figures stay open and can be typed by hand.* |
| **The point is changed** | *`Placed by` changes to `A person`, so the next reader knows the point was checked rather than guessed.* |
| **No owner chosen** | *Saves. The property appears on the `Needs an owner` list, and its vacant-unit charges have nowhere to go until one is linked.* |

## Components named by the drawing

`WizardFrame` · `FindTheAddress` · `JurisdictionField` · `OwnerField` ·
`OwnerNameCheck` · `ServicesAvailableField` · `RefusalStrip` · `Panel` · `Note`

## Rules the screen must obey

Required fields carry the asterisk on the label, **and only the ones the server
will actually insist on**. A multiple choice is chips plus an add control, never
a wall of tick-boxes, and five or more options are searchable. Colour is never
the only signal — every state carries its word. Built in the shared utility
classes, adding nothing to a stylesheet.

## Cognitive-load budget

**Fifteen inputs in five named groups, four lines of help.** *"Help appears only
where it prevents a refusal or explains a consequence; `Town / city` gets none,
because its label is the whole of it."*

---

## One thing the drawing shows and CR-089 has already ruled out of scope

The teal block describes *"a map you can drag"* inside the *Where it is* block.
**The draggable map pin is OUT OF SCOPE by PO ruling** — CR-089 §Trace, *"we
dont need this right now"*. The two coordinate FIGURES are in scope; the pin is
not. Nothing else on this screen carries such a ruling.

---

## BUILT — 2026-09-10, and where the product deliberately diverges

`07-frontend/src/features/metering/AddPremisesWizard.tsx` ·
`premisesFormSections.tsx` · `FindTheAddress.tsx` (the panel) · commit
`5f90fc493`. Every row of the grey frame above is now on the screen, in the
drawn order. What follows is the honest remainder: seven things the drawing
asks for that the product does NOT do, each with its reason.

### Ruled out of scope, not built

| what | ruling |
|---|---|
| A draggable map pin in the *Where it is* block | PO 2026-09-08, *"we dont need this right now - Drag the pin to correct it"*. The two coordinate FIGURES are built. |
| The asterisks on `Property type` and `Inside city limits` | PO 2026-09-10, *"(a) No asterisks, follow the rule"*. The frame draws three; its own rules row says *"only the ones the server will actually insist on"*, and the server insists on the street address alone. **One asterisk is built and a test asserts exactly one.** |

### Built differently, and why

1. **The section headings are sentence case, not the drawn SMALL UPPERCASE.**
   `premisesFormSections.tsx` is Route A — neither it nor `AddPremisesWizard
   .tsx` is on `07-frontend/src/styles/route-b-migrated.txt` — so B14 rule 21
   allows it no Tailwind utility and no new stylesheet class. A `uppercase
   tracking-kicker` written there is a class no stylesheet declares: it renders
   as **nothing at all** while `tsc`, eslint and every assertion pass
   (DEF-974). The heading is an unclassed `<h4>` carrying the drawn WORDS. The
   case treatment arrives when the file is migrated, which is its own work with
   its own proof.
2. **`Billing cycle` is a read-only field, not a second picker.** PO ruling
   2026-09-10 (10) is TWO fields; `BR-MET-073` says a route belongs to one
   cycle per service, so two freely-settable boxes let a clerk state a pair the
   schema cannot hold. Both are honoured: the cycle is drawn, labelled and
   helped exactly as the frame draws it, and it FOLLOWS the route. There is
   still one answer and it is the route.
3. **The header still reads `Add premises & units`, not `Add a premise`**, and
   its sub-line still names all four modes. This wizard serves four entry modes
   (one premise · premises CSV · unit pattern · units CSV) behind one
   `PageHead`; the frame draws only the single-premise flow. Per-step,
   per-mode header copy is a change to the wizard's frame rather than to this
   screen, and is **not** built here. Same reason the review step does not draw
   its own `Review & save` title and sub-line.
4. **`Save draft & exit` is drawn DISABLED, carrying its reason.** A premises
   has no draft state: `premises.status` is `active` / `out_of_service`,
   `POST /premises` writes a LIVE row, and nothing in the API parks a
   half-filled one. `ChargeCodeWizard`'s precedent (DEF-375) and `BR-SHL-025`'s
   shape. Drawing it live and quietly creating a real property would be the
   worst of the three answers; hiding it would leave a clerk hunting for a
   control the design promised.
5. **`Town / city` and `ZIP` read `City` and `ZIP / postal code`.** Those two
   catalogue values are shared with the premises list, the edit form, the
   detail page and the importer; re-wording them is a copy change across those
   screens rather than a fact about this one.
6. **`← Back` and `Continue →` render without their arrows.** `WizardFrame`
   owns that row for about ten wizards and draws the bare words. Filed as
   `DEF-SHL-4748` rather than fixed here — it moves ten screens at once.
7. **A refusal naming `external_ref`, `lat` or `lng` focuses nothing**, because
   those three now live behind `✎ Change these`. `B8`'s promise — the sentence
   NAMES the field — still holds; the panel not opening itself is recorded
   here rather than fixed by having a refusal reach into another component's
   state.

### The four groups, and the form the edit screen has not caught up to

`PREMISES_FORM_SECTIONS` is now the four this frame draws, shared with
`CR-089-p036`'s edit form. **The edit form still renders six** — `DEF-MET-4747`
— so `premisesFormSections.tsx` keeps `RETIRED_SECTION_LABELS` for `map`,
`belongs` and `services` until that lane re-cuts it. Without it the edit form
would draw three EMPTY headings, which no check in this repo can see.
