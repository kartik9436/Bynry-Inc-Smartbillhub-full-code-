# U2 · Add units · Details — THE DRAWN SPEC

> ⚠ **SUPERSEDED AS THE SCREEN'S DRAWING ON 2026-10-09 (`CR-176-BRC10`, `DEF-MET-10035`).** The PO approved a redesign of Add units and gave the go the same day; the screen is now built from `05-prototype/add-units-redesign-2026-10-09/images/01–11`. Rules `BR-MET-1196`–`1201` (next free start, one count, services from the building all ticked, building by search and *Use this building*, a common area chosen at the top, unit numbers from the series unless *My own pattern*). This file stays as the record of what the blueprint frame drew and of the rulings it carried that the redesign KEEPS (`Floor` free text, `Floor area` on the add form, every plan with a search, `← Units` / `Cancel`).

`S16 · PRM-07` — **state chip: `EXISTS BEHIND`**
Blueprint *Premises & Units Blueprint 2*, **page 53** (the chip line and the
screen title) → **page 54** (breadcrumb, amber block, the grey frame's head,
step rail and the *Which building?* section) → **page 55** (the rest of the
frame and the first teal bullet) → **pages 56–58** (the teal block and the
detail table) → **page 59** (the remaining STATES rows, components, rules).

**Commitment chips on the chip line (page 53):** `PUJ-23` · `PUJ-24` · `PUJ-25`.
**CR-089 task rows this screen belongs to:** `E3` (*adding units starts by
naming the building*, `PUJ-23`) · `E4` (*the plain case is plain; the pattern
generator folds away*, `PUJ-24`) · `E5` (*a plan can be attached at creation,
optionally*, `PUJ-25`, `BR-MET-007`).

> **This file records the GREY FRAME only.** The amber block on page 54 —
> *"Pressing '+ New unit' on a building forgets the building"* — is the PROBLEM
> STATEMENT. The teal block on pages 55–56 and the detail table on 56–58 are the
> argument. Where either disagrees with the frame, **the frame wins** (PO ruling
> 2026-09-10). Contradictions found are recorded at the foot, not resolved.

**Breadcrumb drawn above the frame:** `Premises → + New unit → step 1 · from a
property, or from the units list`
**The question the screen answers:** *three more flats went in. Which building,
and add them.*

---

## 1 · Header

| slot | drawn string |
|---|---|
| kicker | `UNITS` |
| title (H1) | `Add units` |
| subtitle | `A unit always belongs to a building. Start by saying which.` |

**In the header, top right:** `Cancel` — secondary, and it is the **only**
header action drawn on this step. No back link, no `Save draft & exit`.

## 2 · Step rail — two steps, `1` active

`1 Details` | `2 Review & create`

## 3 · Section 1 — `WHICH BUILDING? *`

A section kicker in caps with a required mark. Under it, in drawn order:

| # | control | label | drawn value | help beneath |
|---|---|---|---|---|
| 1 | search-select, full width | `Search premises` | `412 Cypress Row` | `By address, property number or parcel. Empty when you arrive from the units list; already filled when you arrive from a property.` |

### The chosen-building summary card — drawn as THREE dense lines

| line | drawn content |
|---|---|
| 1 | `412 Cypress Row` **strong** · `P-00080` quiet · `Silver Creek, TX 78611` |
| 2 | `Apartment complex` · `ACTIVE` *(pill)* · `1 unit today, numbered 1` · `Route 12` · `Cycle 3` |
| 3 | `Owner Creekside Holdings LP` · `master account A-10442` · `Electric` · `Water` · `Sewer` · `Trash` |

**A `Change` button sits at the card's right edge**, vertically centred.

**The address leads the first line and the property number follows it.**

**Beneath the card, one note:** `Everything below is added to this building. Its
route, cycle and services carry to every unit made here.`

## 4 · Section 2 — `HOW MANY, AND WHAT TO CALL THEM`

Six controls, drawn in a grid: three across the first row, two across the
second, one full width.

| # | control | label | drawn value | help beneath |
|---|---|---|---|---|
| 1 | text, numeric | `How many units` **\*** | `3` | *(none)* |
| 2 | text, numeric | `Start numbering at` | `2` | `1 is taken.` |
| 3 | select | `Unit type` | `Residential` | *(none)* |
| 4 | select | `Floor` | `Not recorded` | *(none)* |
| 5 | select | `Unit numbers` | `From the series — U-01145 onward` | `Or type a pattern of your own.` |
| 6 | select, full width | `Or add a common area instead` | `Laundry · Corridor · Car park · Pool · Lift · Landscape irrigation…` | `A shared space with its own meter, billed to the owner rather than to a resident.` |

**`How many units` is the only required field in this section**, and the only
one besides the building carrying a `*`.

## 5 · Section 3 — `WHAT THEY WILL BE CHARGED ON` `optional`

The section kicker carries an `optional` pill beside it.

| # | control | label | drawn value | help beneath |
|---|---|---|---|---|
| 1 | select, half width | `Plan` | `Residential Standard` | `Type to filter. Only plans this building's services can be billed on are offered.` |
| 2 | select, half width | `Starts` | `The day the unit is created` | `Or a date you choose. Never mid-cycle.` |
| 3 | select, full width | `Or leave it for later` | `Set the plan when somebody moves in` | `A unit with no plan is created and cannot be billed until one is set. Its Plan tab says so.` |

## 6 · The fold

One disclosure line, closed by default, drawn beneath section 3 and above the
footer rule:

`▶ Uneven layout? Name them by a pattern instead`

The `{floor}` / `{seq}` / `{seq:00}` token grammar lives behind it and is
**not on screen unless a clerk opens it**.

## 7 · Footer

Left: `Cancel` — secondary
Right: `Continue →` — **primary**

**Primary action, verbatim (page 57):** *"`Continue →`. An arrow navigates;
nothing is written on this step. The commit is on step 2 and it says `Create 3
units ✓`, with the count in the button so the press and its consequence are one
sentence."*

## 8 · States — the frame's own STATES block, verbatim

| state | drawn behaviour |
|---|---|
| **No building chosen yet** | *"Everything below the search is held, greyed and unreachable, and the commit says `Choose a building first`. Nothing about units can be answered before it."* |
| **The building is out of service** | *"The summary carries its status pill and the commit is held: a property that takes no service cannot gain a unit that bills."* |
| **A label is already taken** | *"The refusal is short and names the clash — `Unit 2 already exists` — and the start number moves on."* |
| **Uneven layout** | *"The fold opens and the preview under the pattern shows the first labels it produces, so the syntax is checked by eye and not by trying."* |
| **Adding a common area instead** | *"The unit count disappears and the shared-space list takes its place; the two are the same act with different consequences and the screen only ever shows one."* |
| **No plan chosen** | *"The preview's Plan column says `none yet` in the absence style, and the commit is not held — it is a legitimate choice, and the unit's Plan tab will say the same thing."* |
| **No plan fits the services** | *"The picker is empty and says which service has no plan, with a link to Plans & Rates. Never a silent empty list."* |
| **No numbering series** | *"The block says the unit series has not been set up and links to Settings. No number is invented and the create is held."* |

## 9 · Components named by the drawing

`WizardFrame` · `SearchSelectField` · `SummaryCard` · `TextField` ·
`SelectField` · `RefusalStrip` · `Panel` · `Note`

## 10 · Cognitive-load budget, as stated

*"One search, five inputs and one folded section. The generator's token syntax
is not on screen unless a clerk asks for it."*

## 11 · Rules it must obey, verbatim

*"A consequence preview before the commit. A refusal is short and says what to
do, not what went wrong. Button grammar: a tick commits."*

## 12 · How you get here — BOTH doors are the specification

Page 56, verbatim: *"**Two doors.** The property's page → `+ New unit`, where
the building is already chosen. And the units list → `+ New unit`, where there
is none — that door exists, it is the one a clerk uses when they have been given
a flat and not a building, and **neither should pass through a chooser**."*

Page 57, *WHAT CHANGED · THE FORM STARTS WITH THE BUILDING*, quoting the PO
verbatim: *"firs form should start with Search premises - there is no premsies
and on search you should show premises details - summary"*.

## 13 · Absences — drawn as absent, do not fill them

* No `Floors` field. `Floor` is drawn, and it is the floor **label** for the
  units being made, offered as a select reading `Not recorded` — not a
  floors-times-units multiplier.
* No total-to-create hint line under the form; the count appears in the step-2
  commit button.
* No audit sentence on this step.
* No `Save draft & exit`.

---

## Contradictions inside the source, recorded rather than resolved

1. **`five inputs` versus the nine drawn.** Page 58's COGNITIVE LOAD reads *"One
   search, five inputs and one folded section"*. The frame draws **nine**
   controls after the search — `How many units`, `Start numbering at`,
   `Unit type`, `Floor`, `Unit numbers`, `Or add a common area instead`, `Plan`,
   `Starts`, `Or leave it for later`. The frame wins; the count is a count of
   the plain case, at most. Recorded.
2. **`Floor` as a select reading `Not recorded`.** A floor label is free text
   everywhere else in this module. The frame draws a select with a chevron.
   Recorded as drawn.
3. **The plan `Starts` control has no counterpart in any rule this file could
   find.** `BR-MET-007` gives a unit a default plan; the frame adds a start date
   with *"Never mid-cycle"* beneath it, which is a constraint stated nowhere
   else. Recorded, not invented into a rule.

---

## AMENDMENTS — what was BUILT on 2026-09-10 (`DEF-MET-4772` · `DEF-MET-4773`)

**Six of the nine drawn controls were simply absent**, and three of the six were
already accepted by the server. All six are built: `Start numbering at`
(→ the generator's own `seq_start`), `Floor` (→ `floor_label`), `Unit numbers`,
`Or add a common area instead` (→ `is_common_area` + the chosen name as the
label), `Starts` (→ the plan block's `effective_from`) and `Or leave it for
later`. The header's `← Units` becomes the `Cancel` §1 draws; the building card
becomes the three dense lines §3 draws, with `Change` at its right edge and the
address leading its first line; `How many units` replaces *Units on each floor*;
and `Floors` leaves the form for the naming fold, which is §13's own absence.

**The backend change is two lines:** `_stage_pattern` carries `floor_label` and
`is_common_area` into the staged row. `create_unit` has accepted both since
`_validate_unit` was written — the generator simply never put them there, so
every unit this wizard made had an empty floor and no wizard could make a common
area at all.

### Departures, recorded rather than left to be found

1. **THE FIELDS STACK; THE FRAME LAYS §4 OUT THREE ACROSS THEN TWO.** `B14`
   rule 38 (PO 2026-09-10, *"if youa re doing a form - go as per our UI
   rules"*) puts form CONSTRUCTION with the UI rules and the kit: *"a drawing
   telling you that two fields sit side by side … is not layout, it is FORM
   CONSTRUCTION."* Multi-column field rows change every form in the product and
   no lane owns that blast radius. **Which fields, in which order, under which
   headings is still the drawing's and is built.**
2. **`Floor` IS A TEXT FIELD AND THE FRAME DRAWS A SELECT.** This is the ruling
   already made for the form that EDITS the same column (decision log,
   2026-09-10): `units.floor_label` is free text and already holds `Ground`,
   `G`, `Mezzanine`, `PH`, so a closed list needs a vocabulary nobody has
   ratified and would make existing values unselectable. A create form offering
   a list the edit form cannot show back is one fact wearing two shapes.
   Contradiction 2 above anticipated exactly this.
3. **`Never mid-cycle` IS NOT PRINTED.** §5's drawn help under `Starts` reads
   *"Or a date you choose. Never mid-cycle."* Contradiction 3 above records that
   no rule in this repository states that constraint, and nothing enforces it. A
   sentence promising a guarantee nothing keeps is hard-won law 1 in a string a
   clerk reads, so the first half is printed and the second is not. **The
   constraint itself is still an open question for the Product Owner.**
4. **THE SEARCH HELP IS ONE SENTENCE.** §3 draws two — the second describes when
   the box arrives filled, which the clerk can see. `B14` rule 32's budget wins.
5. **`Or leave it for later` OWNS THE FACT RATHER THAN REPORTING IT.** Choosing
   *later* clears the plan; *use the plan above* is offered only once there is
   one. Two controls that could disagree about whether the run carries a plan is
   the shape `DEF-442` cost.
6. **THE SHARED-SPACE NAMES ARE A SUGGESTION LIST, NOT AN ENUM.** The six are
   declared once as `COMMON_AREA_KINDS`; the server stores the chosen name as
   the unit's LABEL, so nothing here is a vocabulary the database knows about,
   and a clerk with a shared space nobody drew can still name it in the fold.

### FOUND IN A BROWSER, NOT BY A TEST (`10-scripts/cr089_u1u2u3_units_screens_walkthrough.mjs`)

Four of these were STRINGS, and a test asserting a key's own value can never see
that the key holds the wrong string:

* the **`Search premises` box** labelled its options `P-00001 · 1408 Bluestem Ln`
  — a property CODE first, where the frame draws `412 Cypress Row`.
  `premisesPickerOptions` now leads with the address, as the units list's
  address cell and the building card already do. The number has not left.
* the **step rail** read `Building and how many` / `Review`; the frame draws
  `Details` / `Review & create`.
* the **subtitle** was *"Name the building, say how many, and read the numbers
  before anything is created"*; the frame draws *"A unit always belongs to a
  building. Start by saying which."*
* the **kicker** read `PREMISES & UNITS` — the list's — where both Add-units
  frames draw `UNITS`.

**Still divergent, and each is B14 rule 38's *construction* half:**

1. **HELP SITS ABOVE ITS INPUT.** The frame draws it beneath. That is
   `FormModal`'s layout for every field in the product.
2. **THE BUILDING CARD DRAWS SERVICES AS LETTER SQUARES**, where §3 line 3
   draws the words. `ServiceSquares` is the ONE badge (`CR-023` §9.7,
   `DEF-439`); a second rendering here would be a second vocabulary. The
   REVIEW's own `Services` row does draw the words, which is where the frame
   asks for a list a clerk reads.
3. **STEP 1's BADGE STAYS ITS NUMBER ON STEP 2**, where the frame draws a tick.
   `WizardFrame` draws every wizard's rail in this product.

### ⚠ A CONTROL THIS SCREEN MAY NEVER GROW — `BR-MET-1170`, RULED 2026-09-10

PO, verbatim: *"City limits - on Unit will be inherited from Premises only -
please note"*. **No frame on this screen's range draws a `City limits` picker on
a unit and nothing here builds one**, which was checked rather than assumed:
`inside_city_limits` is a column on `premises` alone, `Unit` has no such field,
and `_validate_unit` refuses one by name.

It is recorded HERE because the building card is where somebody would put it.
`BR-MET-1162` lets a unit carry its OWN `lat`/`lng`, and a lane that has just
built that can reasonably read it as a licence to refine any address-shaped fact
per unit. **It is not one.** A point is a MAP fact; city limits is an ADDRESS
fact, and a flat cannot be outside the city its building is inside. It also
decides money — `BR-RAT-101`/`BR-RAT-102` multiply an address's bills by the
outside-city surcharge — so a unit-level answer would price two flats in one
building differently on a fact that cannot differ between them.

**What may be built is the BUILDING's answer shown on a unit, read-only, with
one sentence saying where it comes from** — the shape `BR-MET-118` gives
services. Never a control.

---

## AMENDMENTS — what was BUILT on 2026-09-19 (`DEF-MET-5868` · `DEF-MET-5869` · `DEF-MET-5870`)

**Three Product Owner reports off this screen, in one fix.** Two of them
overturn §1 of the frame above, so the drawn text is left exactly as it is and
the departures are recorded here — which is what this file is for.

### 1 · `Floor area` IS ON THE FORM, AND THE FRAME DOES NOT DRAW IT

PO, verbatim: ***"Unit add form -> square feet field present on edit form but
not present on add form why?"***

§4 draws six controls and this is not one of them; §13's *"Absences — drawn as
absent, do not fill them"* does not name it either, so it is simply not on the
frame rather than deliberately withheld. **B14 rule 41 makes the drawing the
scope and names its one exception** — *"only exception to the rule can be in
case any rule or BR is not matching or contrdicting - in such case you can ask
us"*. The Product Owner asked for this directly, which is the exception
arriving from their end, so it is built.

**It was never a backend limitation.** `_validate_unit` has parsed and
range-checked `square_feet` since it was written, the units CSV importer maps it
as `Floor area (sq ft)`, and the edit form, the unit page and the units list all
draw it. **The generator was the gap:** `_stage_pattern` never put the field in
the staged row — the identical shape as `floor_label` and `is_common_area` in
the 2026-09-10 amendment above, and the third field to be found this way.

**It is `Floor`'s construction, deliberately:** the same `TextField`, the same
optionality, the same help sentence (*"Written onto every unit this run
creates."*). That sentence is why it is ONE box and not a per-unit grid. The
label is the EDIT form's own key, `metering.units.field.floorArea` — `Floor
area`, which `DEF-MET-4763` ruled over `Square feet` — so one fact keeps one
pair of words (B14 rule 34). **The review names it**, because §11 asks for a
consequence preview and a value entered on step 1 and never mentioned again is
indistinguishable from one the run will discard.

### 2 · `Cancel` IS IN THE WIZARD FOOTER — §1 IS SUPERSEDED

PO, verbatim: ***"cancel button should be bottom not on top"***. Put back to
them as *"Footer: the wizard actions, with `Cancel`, and `← Back` meaning
previous step only"* — ***"this is correct"***.

§1 reads *"`Cancel` — secondary, and it is the **only** header action drawn on
this step."* **⚠ §7 of this same frame already drew `Left: Cancel — secondary`
in the footer**, so the drawing states it in both places and the build took §1.
The ruling settles which one is the specification: **§7**.

B14 rule 3 puts a 2+ stage flow's actions in a wizard-actions footer, and rule
38 settles the position inside it — *"a drawing telling you … that the footer
puts Cancel on the left … is not layout, it is FORM CONSTRUCTION, and B14 plus
the component kit already settle it."*

⚠ **IT IS A KIT CHANGE, NOT A CHANGE TO THIS SCREEN.** `WizardFrame` now takes a
`cancel` prop and draws the button in its own action row, per rule 36 — *"one
component, one visual decision, every screen"*. Five screens had each
hand-rolled one in their page head and had already drifted: three drew `ghost`
where the kit draws `secondary`.

⚠ **AND THE REASON ALL FIVE GAVE FOR THE HEAD WAS FALSE.** Each said, in its own
words, that *"`WizardFrame` owns the footer row and right-aligns it for ten
wizards, so Cancel sits in the header"*. The row is `justify-end`, but
`WizardExitControls` has sat at its LEFT since `CR-030` by carrying `mr-auto` —
the slot was always there and the claim was never checked against the code
(hard-won law 1). **23 of the 26 wizards pass no `cancel` and render byte-identical
markup**, which `WizardFrame.dom.test.tsx` asserts by name.

### 3 · `← Units` IS BACK IN THE HEAD — §1's *"No back link"* IS SUPERSEDED

PO, verbatim: ***"back arrow button is missing user not able to navigate on unit
list view"***.

§1's *"No back link, no `Save draft & exit`"* was built literally on 2026-09-10,
and the amendment above records it in its own words: *"The header's `← Units`
becomes the `Cancel` §1 draws."* **That left the screen with no way back to the
units list at all**, because the only other candidate does not work:

> ⚠ **THE SHELL BREADCRUMB IS NOT AN EXIT, AND IT LOOKS LIKE ONE.** Measured in
> Chromium at `/brazosbend/premises/units/new`, `nav.crumbs` renders
> `Premises › Units` with exactly one anchor — `/brazosbend/premises`, the
> **properties** list. `Units` is the leaf, and `BR-SHL-004` makes a leaf plain
> text, never a link. So the crumb that names where the clerk wants to go cannot
> be pressed, and the one that can goes somewhere else. **This is why the fix is
> a header link and not "make the breadcrumb discoverable"** — there is no
> working control here to duplicate.

**B14 rule 1 provides for exactly this:** *"A page header's `←` names where it
EXITS to."* A drawn element contradicting a ratified rule is the case rule 41
sends to the PO, and they have now ruled.

⚠ **RULE 1's LAST CLAUSE IS LOAD-BEARING HERE, BECAUSE BOTH CONTROLS NOW SIT ON
ONE SCREEN:** *"The two never share a label."* The head says `← Units`
(`metering.addUnits.back`) and names the list it leaves to; the footer says
`Back` (`wizard.back`) and means only *previous step*. **Checked in all eleven
catalogues, and they differ in every one** — `← Einheiten`/`Zurück`,
`← Unidades`/`Regresar`, `← Lots`/`Retour`, `← 住戸`/`戻る`, and so on.

⚠ **NO NEW COPY WAS MINTED FOR ANY OF THE THREE.** `metering.addUnits.back` was
already translated in all eleven catalogues and had been left ORPHANED when the
link was removed — restoring the control re-used it. `Floor area`, its help
sentence, `Not recorded` and `{{value}} sq ft` are all existing keys. B14 rule
35 was therefore never engaged, which is the cheapest possible outcome and was
luck rather than design: the orphaned key survived only because nobody swept it.

### Still divergent after this fix

The three construction departures recorded above are unchanged — help above its
input, the building card's service squares, and step 1's badge staying a number
on step 2. **`Floors` is still off the form** (§13), and **`Never mid-cycle` is
still not printed**, for the reasons already given.

---

## AMENDMENT — 2026-09-25 · A SERVICES TICK-LIST JOINS SECTION 1 (`DEF-MET-6796`)

**A control that is NOT on the frame is now on the screen, and this records it
rather than leaving it to be found.**

**The ruling.** PO, 2026-09-25, verbatim: *"the premises' list is what a unit
takes, the tick-list stays, and a clerk may untick"*. `BR-MET-119` is amended the
same day: a unit inherits the address's list **by default**, so a unit's set is
*within* the premises' set rather than equal to it.

**Why it is an addition and not a divergence.** The `U2` frame is 2026-09-10 and
draws no services control on this step; the ruling is fifteen days younger. B14
rule 41 sends a drawing that contradicts a signed rule to the PO — here the PO
ruled FIRST, so there is nothing to escalate. The frame is not wrong; it is
older than the rule.

**Where it sits, and why there.** In §3, `WHICH BUILDING?`, directly beneath the
frame's own note — *"Everything below is added to this building. Its route,
cycle and services carry to every unit made here."* That sentence is the promise
and the control is what honours it; separating them would put the promise in one
section and the way to change it in another.

**What it draws.** `UnitServicesField` — the address's offer as removable chips,
every one ticked, with a select that adds an unticked service back. **B14 rule 9
is why they are chips and not checkboxes**, and the wording of the ruling is
satisfied either way: a chip's ✕ is how this product unticks.

**Two absences, deliberately.** An address offering nothing, and an address
nobody has been asked about, draw one short sentence each and no control —
`BR-MET-119`'s own distinction, and neither can leave a unit short. No rationale
is printed beside either (B14 rule 33: rationale is ZERO words on screen).

**What the run posts.** Nothing at all when the clerk never touched the control
and the building has not loaded — the SERVER then inherits, which is the rule,
so this door and `POST /units` agree. An array, a deliberate empty one included,
is the clerk's answer and is sent.

**The exceptions block at the foot of `AddUnitsWizard.tsx` is REVERSED in the
same commit.** It read *"the wizard sets no `services` on the generated units …
creating service points for each of them is a different act"*. The ruling says
it is not a different act.


### AMENDED 2026-09-26 — the control now sits on the form's rhythm (`DEF-MET-6815`)

Walked in Chromium at 1440 and 1280. The control was at **`margin-top: 0`** and
read as part of the note above it rather than as a field of its own: the note
ended at **y=566** and the `Services` label began at **y=583**, against **20px**
between every other pair of fields on this form.

`[data-panel] > .field + .field` supplies that 20px (B14 rule 39), and its own
comment says it deliberately does not reach a field that follows a `<Note>` —
which is what this one does. It carries `mt-[var(--space-5)]` now: **the
product's own token, not the number 20**, because two figures for one distance
is the drift that rule's comment warns about. Re-measured: `margin-top: 20px`,
level with every sibling.

**The chip row wraps sanely at both widths** — `Electric ×`, `Water ×` and the
add-back select sit on ONE line at 1440 and at 1280, and horizontal page
overflow measured **0px** at both.
