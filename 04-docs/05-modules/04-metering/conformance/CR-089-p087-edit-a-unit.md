# U10 · Edit a unit — THE DRAWN SPECIFICATION

**Source:** *Premises & Units Blueprint 2*, **pages 87–90** (plate header p87,
screen frame p87–p89, teal *WHAT CHANGED* p89, frame metadata p89–p90).
Extracted 2026-09-10 from `05-prototype/Premises & Units Blueprint 2.pdf`
(md5 `f034d6e42c0caad658fadfdf6e4704eb`), read page by page with
`10-scripts/pdf/pdf_text.py` **and looked at** as rendered PNGs at scale 1.6 —
the four group headings, the two-up field pairs and the position of the point
offer are DRAWN, not written, and text extraction alone loses all three (it
also lifts the `Give this unit its own` button out of its block and prints it
at the top of page 88).

**State chip:** `NEW BUILD` · **Commitments:** `PUJ-27` · `PUJ-44` · `PUJ-45`
**Screen ids:** `U10` — `S15 · PRM-03`
**CR-089 task rows:** **`F6`** (wave F — a unit has an edit screen and its plan
is applied or changed from it, `PUJ-44`, `PUJ-45`) · **`A7`** (wave A — a unit
may carry its own point and parcel, `PUJ-27`)

⚠ **`NEW BUILD` MEANT *DOES NOT EXIST* WHEN THE BLUEPRINT WAS DRAWN, AND A FORM
EXISTS NOW — TWO OF THEM.** `07-frontend/src/features/metering/UnitEditModal.tsx`
landed with CR-089 wave F and opens from the unit's own page; a SECOND,
different form is declared privately at `UnitsListPage.tsx:980` and is what the
units-list pencil opens. The blueprint says the pencil *"opens the same form"*.
It does not. The chip is recorded as drawn; what exists today is a fact about
today, not a correction to the blueprint.

⚠ **EVERYTHING BELOW IS FROM THE BORDERED GREY FRAME ONLY.** The amber block on
page 87 (*"There is no edit screen for a unit…"*) is the problem, not the
target; the teal *WHAT CHANGED* block on page 89 is rationale. Neither is
specification.

⚠ **THE VALUES ARE ILLUSTRATIONS; THE LABELS, THE ORDER AND THE PRESENCE OF EACH
ROW ARE THE SPECIFICATION** (the standing caveat in `09-screen-conformance.md`).

---

## Header

**Kicker** `UNIT`
**Title** `Edit Unit 2`
**Sub-line, line 1** `U-01145 · 412 Cypress Row, Silver Creek, TX 78611 · Residential ·` then two pills, `ACTIVE` and `OCCUPIED`
**Sub-line, line 2** `Route 12 · Cycle 3 — from the building`

A horizontal rule closes the identity block before the first group.

## Actions, in the order drawn

| # | label | tier | where |
|---|---|---|---|
| 1 | `Cancel` | secondary | top right of the frame, on the title row |
| 2 | `Give this unit its own` | secondary | inside the `WHERE IT IS` panel, right-aligned |
| 3 | `Add a service…` | select control | the `Utility services` field's own picker |
| 4 | `Cancel` | secondary | footer, left |
| 5 | `Save changes ✓` | **primary** | footer, right |

**Primary action:** `Save changes ✓`.

## Tabs

**None.** This screen has no tabs. (A stated absence — the frame is a form.)

## Tiles

**None.** `COGNITIVE LOAD`: *"Seven fields in three groups, one offer, two lines
of help."*

⚠ **THE FRAME DRAWS FOUR GROUP HEADINGS AND THE METADATA ROW SAYS THREE.** The
drawing wins: `WHAT THIS UNIT IS CALLED`, `WHERE IT IS`, `WHAT IT CAN TAKE`,
`WHAT IT IS CHARGED ON`. Recorded, not resolved.

## Groups and fields — FOUR named headings, in this order

### 1 · `WHAT THIS UNIT IS CALLED`

| # | label | control | drawn value | width | help beneath |
|---|---|---|---|---|---|
| 1 | `Unit label` **\*** | text | `2` | left of a 2-up row | `What a resident and a reader call it.` |
| 2 | `Unit type` | select | `Residential` | right of that row | — |
| 3 | `Floor` | select | `Ground` | left of a 2-up row | — |
| 4 | `Floor area` | text | `820 sq ft` | right of that row | — |

Only `Unit label` carries a required asterisk.

### 2 · `WHERE IT IS` — heading carries a grey `optional` pill

**No coordinate fields are drawn.** One bordered panel, full width:

* **panel text, verbatim:** `Using ` **`412 Cypress Row`** `'s point — 30.752104, −98.238391 · parcel R-114-0082-004`
* **panel action, right-aligned:** `Give this unit its own`
* **help beneath the panel, verbatim:** `A unit only needs its own point where it sits somewhere its building does not — a cabin, a pad, a wing of a campus.`

⚠ **THE PARCEL IS PART OF THE DRAWN SENTENCE** (`parcel R-114-0082-004`).

### 3 · `WHAT IT CAN TAKE`

| # | label | control | drawn state | help beneath |
|---|---|---|---|---|
| 5 | `Utility services` | select + chips | picker reads `Add a service…`; chips below it read `ELECTRIC ×` `WATER ×` | `Only what the building offers. Removing one is refused while a meter for it is attached.` |
| 6 | `This is a common area` | **select**, answer in words | `No — it is a unit somebody lives in` | `A common area bills to the owner and can never hold a resident's account.` |

⚠ **ROW 6 IS A SELECT AND NOT A TICK-BOX, AND THE FRAME SAYS SO ON PURPOSE** —
the teal block: *"Common area is a question with an answer in words, not a
tick-box, because it changes who gets billed."*

### 4 · `WHAT IT IS CHARGED ON` — heading carries a grey `optional` pill

| # | label | control | drawn value | width | help beneath |
|---|---|---|---|---|---|
| 7 | `Plan` | select | `Residential Standard` | left of a 2-up row | `Electric and water. Type to filter; only plans this unit's services can be billed on are offered.` |
| 8 | `The change takes effect` | select | `1 Oct 2026 — the next cycle` | right of that row | `Never mid-cycle. Bills already issued keep the plan they were made on.` |

**A full-width sentence beneath both, verbatim:**
`A unit with no plan cannot be billed. If this one has none the field says so and applying one here is the whole job.`

⚠ **NO `Reason` FIELD IS DRAWN IN THIS GROUP.**

## Table columns

**None.** This screen has no table.

## Footer

`Cancel` *(secondary, left)* · `Save changes ✓` *(primary, filled, right)*, above
a horizontal rule that separates them from the last help line.

## States — exact sentences

| state | drawn sentence |
|---|---|
| **Has its own point** | `The block shows the unit's figures and offers to go back to the building's.` |
| **Service in use** | `The chip cannot be removed and says why in five words.` |
| **Occupied** | `Becoming a common area is refused while an account is open on it.` |

**No empty, loading or error state is drawn.** (A stated absence.)

## Frame metadata

* **FOR** — `A clerk correcting a flat — a label typed wrong, a floor recorded wrong, a service added when the building was extended.`
* **HOW YOU GET HERE** — `The unit's page → ✎ Edit. Also the pencil on the units list, which opens the same form.`
* **PRIMARY ACTION** — `Save changes ✓.`
* **WHAT CHANGED · IT EXISTS** — `The unit's page had no edit control at all; the only route was a row action on a list.`
* **WHAT CHANGED · THE POINT IS AN OFFER** — `Two empty coordinate boxes on every unit would imply every unit ought to have them. Almost none should.`
* **COGNITIVE LOAD** — `Seven fields in three groups, one offer, two lines of help.`
* **COMPONENTS** — `FormModal` `TextField` `SelectField` `ServicesAvailableField` `RefusalStrip`
* **RULES** — `Required asterisks only where the server insists. A refusal caps at five or six words and says what to do. A multiple choice is chips plus an add control.`

## Commitments this screen carries

| id | statement | done looks like (verbatim) |
|---|---|---|
| `PUJ-27` | A unit may carry its own point and its own parcel | `A cabin's unit page reads On the map 30.751880, −98.238004 · this unit's own point; a flat in a block reads 30.752104, −98.238391 · from the building with Give this unit its own point beside it.` |
| `PUJ-44` | A unit has an edit screen | `From the unit's page a clerk presses ✎ Edit, changes the label from 2 to 2B and the floor area to 820 sq ft, and saves — without going back to the list to find the pencil.` |
| `PUJ-45` | A unit's plan is applied or changed from its edit form | `The edit form carries Plan · Residential Standard and The change takes effect · 1 Oct 2026 — the next cycle, and a unit with no plan says so with applying one available in the same form.` |

## Contradictions inside the blueprint, recorded and NOT resolved

Per the PO ruling of 2026-09-10 the **frame wins and the sentence gets
corrected**. Three found in this section:

1. **Three groups or four.** `COGNITIVE LOAD` (p90) says *"Seven fields in three
   groups"*; the frame draws **four** named headings. Frame wins: four.
2. **The point button's label.** The frame draws `Give this unit its own`;
   `PUJ-27`'s *done looks like* (p98) quotes `Give this unit its own point`.
   Frame wins: `Give this unit its own`.
3. **Seven fields or eight.** `COGNITIVE LOAD` says seven; the frame draws eight
   controls (label, type, floor, floor area, services, common area, plan,
   effective) not counting the point offer. Frame wins: eight.

## Collision with a signed rule — for the PO, not for us

⚠ **THE `Utility services` FIELD AS DRAWN CANNOT BE BUILT WITHOUT REVERSING A
STANDING PO RULING.** A unit's services are its **premises'** services — PO
ruling 2026-08-26 after `CR-037` was withdrawn, recorded on `DEF-755` and in
`endpoints.ts:6115`: *"no unit-level column, no override."* The frame draws
removable chips on the unit with `Removing one is refused while a meter for it
is attached`, which presumes a unit-level list a clerk can subtract from. This
is the one item in this section that legitimately reaches the PO (hard-won law
13: *a ruling that collides with a signed rule*). It is recorded here and
nothing is chosen.

---

# WHAT WAS BUILT, 2026-09-10 — and every difference that REMAINS

**Fixed under `DEF-MET-4731` (two forms), `DEF-MET-4762` (a retired rule still
on screen) and `DEF-MET-4763` (the frame was never diffed).** Proof:
`07-frontend/src/features/metering/UnitEditForm.dom.test.tsx` (nine cases, eight
of them shown red against the pre-fix form first) and
`UnitsListOneDoor.dom.test.tsx` (the two forms are now one).

## Closed

| # | what the frame draws | what it now does |
|---|---|---|
| 1 | *"the pencil … opens the same form"* | It does. `UnitsListPage`'s private `UnitEditModal` is deleted and both doors import this one. `is_common_area` came with it |
| 2 | four named group headings | `WHAT THIS UNIT IS CALLED` · `WHERE IT IS` · `WHAT IT CAN TAKE` · `WHAT IT IS CHARGED ON`, declared as `UNIT_FORM_SECTIONS` and asserted in order |
| 3 | no `Premise` field | Gone, and its sentence with it — see below |
| 4 | `Floor area` | Was `Square feet`; the unit's own Overview already said `Floor area` |
| 5 | `This is a common area`, a **select** with the answer in words | A `SelectField`: *No — it is a unit somebody lives in* / *Yes — shared space that bills the owner* |
| 6 | `Edit Unit 2` — the LABEL | Was `Edit unit U-01145`. `unitFormTitle` puts the label first and falls back to the series number only where there is no label |
| 7 | the point as an **offer** inside `WHERE IT IS` | The sentence names which point is in force and whose; `Give this unit its own point` reveals two coordinate boxes that ride the SAME `PATCH` |
| 8 | `Save changes ✓` | Was `Save unit`. B14's grammar — `Verb ✓` commits |
| 9 | the `optional` pill on two headings | On `WHERE IT IS` and `WHAT IT IS CHARGED ON`, as drawn |

**`DEF-MET-4762`, in full, because it is the one that reached a clerk.** The
read-only `Premise` field carried *"A unit never moves between premises. To
relocate it, deactivate it and create it under the other premise."* `BR-MET-095`
superseded `BR-MET-046` on **2026-08-21** and `MoveUnitModal` shipped the same
day. The sentence was false for twenty days, on **two** forms, and it advised a
clerk to destroy and re-create a unit rather than press the button beside it.
The key is retired from all eleven catalogues.

## Divergences that REMAIN, each with its reason

### Ruled by the PO, 2026-09-10 — not ours to build

| what the frame draws | why not |
|---|---|
| `Utility services` as removable per-unit chips | **`BR-MET-118`.** *"no they will do it on Premises - if it is change on premises all units will inherit it."* There is no unit-level column and no override. The building's list is drawn READ-ONLY with one sentence saying where it comes from — a stated absence (B14 rule 32), not a gap. **The inheritance claim was verified before the sentence was written:** `selectors.unit_detail_dict` reads `unit.premises.services_available` at read time, `units` has no services column in the model or in any migration, and `_validate_unit` never writes one |
| two-up field rows | **B14 rule 38.** *"if youa re doing a form - go as per our UI rules."* Side-by-side rows are a `FormModal` change that moves every dialog in the product on one screen's authority |
| help text BENEATH its input | B14 rule 38 — same reason. `FormModal` puts help above |
| a header sub-line (`U-01145 · 412 Cypress Row … ACTIVE OCCUPIED`, `Route 12 · Cycle 3`) | B14 rule 38 — `ModalShell` has no sub-line slot and adding one is a shared-kit change |
| `Cancel` on the title row | B14 rule 38 — the shell's `✕` |

### Ours, and stated rather than quietly followed

| what the frame draws | what was built, and why |
|---|---|
| `Floor` as a **select** showing `Ground` | A text field. `units.floor_label` is free text in the model and already holds `Ground`, `G`, `Mezzanine`, `PH`. A closed list needs a vocabulary nobody has ratified, and shipping one would make every existing value unselectable on the form that edits it |
| `· parcel R-114-0082-004` in the point sentence | Absent. The parcel is the premises' and `unit_detail_dict` does not carry it; that dict is what `update_unit` writes into `audit_log` as `before`/`after` and what `customers.seams` hands the move-in flows, so a field added to it changes three payloads to draw one word |
| `Plan` help: *"Electric and water. Type to filter; only plans this unit's services can be billed on are offered."* | Not built. `getUnitPlanOptions` is called with `{per: 500}` and no unit, so it does **not** filter by the unit's services. Printing the sentence would be a comment claiming a guarantee (hard-won law 1). The filtering is worth having; it is a change, not a copy fix |
| `The change takes effect` help: *"Never mid-cycle. Bills already issued keep the plan they were made on."* | The label is the drawn one; the help stays *"Leave blank to use today."* Nothing in this build forces the next cycle, so *"never mid-cycle"* would be the same claim-without-a-guarantee |
| the plan section's sentence, two sentences long | One: *"A unit with no plan cannot be billed."* B14 rule 32 gives a section ONE sentence, and where the drawing and the design system disagree the system wins |
| the four headings in SMALL UPPERCASE | Sentence case. This file is Route A — B14 rule 21's per-file clause means a Tailwind utility written here renders as **nothing at all** — so the heading is an unclassed `<h4>` |

## Still open for the PO

`OQ` — **should the plan picker be filtered to the unit's services?** The frame
says it is and the product does not. It is a real improvement and a real change:
the endpoint would need the unit id and the server would need to intersect.
Recorded here rather than built.

## Found in a BROWSER, and by nothing else (hard-won law 6)

`10-scripts/cr089_unit_dialogs_walkthrough.mjs` — 27 checks against a booted
stack, screenshots in its own output directory.

**`Edit Unit 2` becomes `Edit {{unit}}`, and the frame loses this one on
evidence.** The drawn title puts the noun in front of the label, which reads
correctly for the frame's own example — a bare `2`. **It does not read correctly
for the labels this product actually holds.** `UnitsListPage`'s own column
comment says what a unit label IS here: *"`Unit A`, `Suite 200`, `Master`, `Apt
101`"*. The first screenshot of the fixed form read **`Edit Unit Unit B`**, and
`Edit Unit Suite 200` is the same sentence one tenant over. No test could have
seen it — every assertion about the title was about which FIELD it came from.
The same correction is applied to `U11`'s `Move Unit 1 to another property`.

**And the three dialogs now name a unit the same way.** `U12` opened as `Take
U-00101-A out of service?` — the series number — beside an edit form titled
`Edit Unit B`, from the same table row. One unit, two names, one click apart.
