# U11 · Move a unit to another property — THE DRAWN SPECIFICATION

**Source:** *Premises & Units Blueprint 2*, **pages 90–94** (plate header p90,
amber block p90–p91, screen frame p91–p92, teal *WHAT CHANGED* p92–p93, frame
metadata p93–p94). Extracted 2026-09-10 from
`05-prototype/Premises & Units Blueprint 2.pdf` (md5
`f034d6e42c0caad658fadfdf6e4704eb`), read page by page with
`10-scripts/pdf/pdf_text.py` **and looked at** as rendered PNGs at scale 1.6 —
the three-up field row, the two-column consequence TABLE and the dashed hint
box under the tick are DRAWN, not written.

**State chip:** `EXISTS BEHIND` · **Commitments:** `PUJ-46` · `PUJ-47` · `PUJ-55`
**Screen ids:** `U11` — `S15 · PRM-03`
**CR-089 task rows:** **`J1`** (wave J — the move screen itemises what moving
does, `PUJ-46`) · **`J2`** (wave J — a date picker and a human plural,
`PUJ-47`) · **`J3`** (wave J — bills can be counted for a single unit,
`PUJ-55`)

⚠ **EVERYTHING BELOW IS FROM THE BORDERED GREY FRAME ONLY.** The amber block on
pages 90–91 (*"The screen exists and it is the only action…"*, *"Two things are
wrong"*) is the problem, not the target; the teal *WHAT CHANGED* block on pages
92–93 is rationale. Neither is specification.

⚠ **THE VALUES ARE ILLUSTRATIONS; THE LABELS, THE ORDER AND THE PRESENCE OF EACH
ROW ARE THE SPECIFICATION** (the standing caveat in `09-screen-conformance.md`).

---

## Header

**Kicker** `UNIT`
**Title** `Move Unit 1 to another property`
**Sub-line** `SCW-U-001 ·` `Residential ·` then two pills, `ACTIVE` and `OCCUPIED`

A horizontal rule closes the identity block before the first field.

## Actions, in the order drawn

| # | label | tier | where |
|---|---|---|---|
| 1 | `Cancel` | secondary | top right of the frame, on the title row |
| 2 | `Cancel` | secondary | footer, left |
| 3 | `Move unit ✓` | **danger** (outlined amber, not filled) | footer, right |

**Primary action:** `Move unit ✓`, danger tier. *"A tick commits."*

## Tabs

**None.**

## Tiles

**None.** `COGNITIVE LOAD`: *"Four fields, one consequence table, one tick, two
buttons. The tick appears only where the unit has carried an account."*

## Fields — four, in this order

**Row 1 is THREE fields across; `Reason` sits alone on row 2 at one-third
width.**

| # | label | control | drawn value | help beneath, verbatim |
|---|---|---|---|---|
| 1 | `Currently on` | text, **read-only** | `101 Silver Creek Rd, Ottumwa, IA · P-00041` | `Read-only. This is where its bills have been attributed.` |
| 2 | `Move to` **\*** | search-select | placeholder `Search by address, property number or parcel…` | `Any active property. The unit takes the new building's route, cycle and services.` |
| 3 | `Effective from` **\*** | **date picker** (chevron drawn) | `8 Sep 2026` | `Today or earlier. A future move is refused — this product cannot hold one that has not happened yet.` |
| 4 | `Reason` **\*** | text | `Recorded on the wrong building at import` | `This is the only record of why the unit moved.` |

⚠ **THE DRAWN VALUE OF ROW 1 IS ADDRESS FIRST, NUMBER SECOND.**
⚠ **ROW 3 IS A NAMED-MONTH PICKER, NOT A FORMAT INSTRUCTION** — that is the
whole of `PUJ-47`'s first half.

## The consequence panel

Teal-bordered, drawn BELOW the four fields, inside the frame.

**Panel heading:** `WHAT THIS WILL DO`

**A two-column TABLE — a bold label on the left, one sentence on the right —
SEVEN rows in this order:**

| # | left column (label) | right column (verbatim) |
|---|---|---|
| 1 | `Bills already issued` | `Stay on 101 Silver Creek Rd. Nothing already billed moves.` |
| 2 | `The next bill` | `Is attributed to the new property, from 8 Sep 2026.` |
| 3 | `Accounts this unit has carried` | `2 — a report that reads a unit's current property will show both under the new one.` |
| 4 | `Bills it has produced` | `Cannot be counted — nothing counts bills for a single unit yet` *(drawn in the absence style — italic, greyed)* |
| 5 | `Route and cycle` | `Route 12 · Cycle 3 → Route 4 · Cycle 1, from the new building.` |
| 6 | `Meters and assets` | `The 5 tagged to this unit travel with it. Their addresses are the building's, so all five change address too.` |
| 7 | `Recorded` | `Both properties, the date and your reason, in the audit log.` |

**Row 7's label is `Recorded`** — B14 rule 34's word for *held here*, drawn.

## The account acknowledgement

Drawn beneath the consequence table, outside it, in this order:

1. warning line, with a `⚠` glyph: `This unit has carried ` **`two accounts`** `. Tick to move it anyway.`
2. checkbox: `☐ I understand, and I want to move this unit anyway`
3. a **dashed-border hint box** immediately beneath the checkbox: `Required before the move can be made`

⚠ **THE COUNT IS SPELLED IN WORDS IN THE DRAWING** (`two accounts`), and the
whole of `PUJ-47`'s second half is that `2 account(s)` was a machine's plural.

## Footer

A horizontal rule, then `Cancel` *(secondary, left)* · `Move unit ✓` *(danger,
outlined, right)*.

## States — exact sentences

| state | drawn sentence |
|---|---|
| **Same property** | `Refused in five words — already on that property — before anything else is checked.` |
| **Future date** | `Refused, and the reason is a true statement about the product rather than a validation message: a move that has not happened yet cannot be held.` |
| **Never carried an account** | `No tick and no warning. The consequence table still lists what changes.` |
| **Has carried accounts** | `The count leads the warning and the tick is required. Reports that read a unit's current property will show its whole history under the new one.` |
| **Reason left empty** | `Held. It is the only record of why the unit moved, and the refusal says that rather than this field is required.` |

## Frame metadata

* **FOR** — `A clerk correcting an import that put a flat on the wrong building, and — rarely — a genuine re-parcelling. It is almost always an error correction, which is why the reason box is the point of the screen.`
* **HOW YOU GET HERE** — `The unit's page → Move. Today it is the only button in that header; with Edit and Change status beside it, it becomes the third of three and stops being the default thing to press.`
* **PRIMARY ACTION** — `Move unit ✓, danger tier. A tick commits.`
* **WHAT CHANGED · THE CONSEQUENCE, ITEMISED** — `Seven rows in place of two sentences: bills already issued stay, the next bill moves, how many accounts are affected, that the bill count cannot be produced, the new route and cycle, that the five tagged assets change address with the unit, and what is written to the audit log.`
* **WHAT CHANGED · THE ASSETS CHANGE ADDRESS** — `An address is stored in one place — on the property — and everything else walks to it. So moving a unit silently re-addresses every meter, sub-meter, cart and endpoint on it. True before this change and said nowhere.`
* **WHAT CHANGED · A PICKER AND A PLURAL** — `"Enter the date as YYYY-MM-DD" and "2 account(s)" — a format instruction and a machine's plural, on the two sentences a person has to read before agreeing.`
* **COGNITIVE LOAD** — `Four fields, one consequence table, one tick, two buttons. The tick appears only where the unit has carried an account.`
* **COMPONENTS** — `MoveUnitModal` `SearchSelectField` `DateField` `TextField` `CheckboxField` `ConsequencePanel` `RefusalStrip`
* **RULES** — `The danger tier for a commit that cannot be simply undone. A consequence preview before the commit. A refusal caps at five or six words. Every service action is recorded with who, when and what. An absence is drawn as an absence.`

## Commitments this screen carries

| id | statement | done looks like (verbatim) |
|---|---|---|
| `PUJ-46` | The move screen itemises what moving does | `Move Unit 1 lists seven consequences, including Meters and assets · the 5 tagged to this unit travel with it. Their addresses are the building's, so all five change address too and Route 12 · Cycle 3 → Route 4 · Cycle 1.` |
| `PUJ-47` | The move screen uses a picker and a human plural | `The effective-date field is a picker showing 8 Sep 2026, not the instruction Enter the date as YYYY-MM-DD; the warning reads This unit has carried two accounts.` |
| `PUJ-55` | Bills can be counted for a single unit | `The move screen reads Bills it has produced · 14 instead of Cannot be counted — nothing counts bills for a single unit yet.` |

## Contradictions inside the blueprint, recorded and NOT resolved

Per the PO ruling of 2026-09-10 the **frame wins and the sentence gets
corrected**. Two found in this section:

1. **The word for what travels.** The frame's row 6 label is `Meters and
   assets`; `PUJ-46`'s *done looks like* (p104) quotes the same row as `the 5
   assets tagged to this unit`, and the PO ruled the same day that on a unit
   *"Meter = assets"* (`CR-089` D2). Frame wins as drawn: `Meters and assets`.
   ⚠ The ruling is the newer statement of the two and it is the PO's, so this
   one is flagged rather than treated as settled by §16.
2. **`ConsequencePanel` is not a kit component.** `COMPONENTS` names
   `ConsequencePanel`; the kit's component is `ConsequenceBox`
   (`07-frontend/src/components/ConsequenceBox.tsx`), and neither of its two
   looks is the two-column labelled table the frame draws. The DRAWING is the
   specification; the name in the metadata row is not.

---

# WHAT WAS BUILT, 2026-09-10 — and every difference that REMAINS

**Fixed under `DEF-MET-4763`.** Proof: `MoveUnitModal.test.tsx` — the seven rows
as a pure function, plus the rendered field order and the two commit labels.

## Closed

| # | what the frame draws | what it now does |
|---|---|---|
| 1 | `WHAT THIS WILL DO` as a **two-column labelled table** | A `PlainTable` from the kit, one row per consequence, a bold label on the left and one sentence on the right. It rendered as an unlabelled bullet list, because `MoveUnitModal.tsx:437` passed `heading`/`bullets` — which is `ConsequenceBox`'s **customer-portal** look, not a staff one |
| 2 | seven rows, in the drawn order | `Bills already issued` · `The next bill` · `Accounts this unit has carried` · `Bills it has produced` · `Route and cycle` · `Meters and assets` · `Recorded` |
| 3 | row 7's label is `Recorded` | B14 rule 34's ratified word, and the row is new — nothing on this screen used to say what gets written down |
| 4 | `Currently on` = address, then number | Was number-then-address, so the field a clerk reads to check the building opened with a code nobody navigates by |
| 5 | `Move to` **\*** with its help line | `SearchSelectField` has taken `required` and `help` all along and was passed neither. It was required in the schema and required nowhere a person could see |
| 6 | `Tick to move it anyway` | The warning had lost its instruction to a sentence about reports — which is TRUE, is now row 3 of the table, and left the one sentence asking a person to agree with no sentence telling them how |
| 7 | `Required before the move can be made` under the tick | Present, as the kit's `Note` |
| 8 | `Move Unit 1 to another property` — the LABEL | Was `Move {{unit}}` off `unitLabel`, which puts the series number first. Now `unitFormTitle`, shared with the edit form |
| 9 | `Move unit ✓` | Was `Move unit`. *"A tick commits."* |

## Divergences that REMAIN, each with its reason

### Ruled by the PO, 2026-09-10 — not ours to build

| what the frame draws | why not |
|---|---|
| `Currently on` · `Move to` · `Effective from` three-across, `Reason` alone at one-third width | **B14 rule 38.** Multi-column field rows are a `FormModal` change that moves every dialog in the product |
| a header sub-line (`SCW-U-001 · Residential · ACTIVE OCCUPIED`) | B14 rule 38 — `ModalShell` has no sub-line slot |
| `Cancel` on the title row | B14 rule 38 — the shell's `✕` |
| the dashed-border hint box under the tick | The BOX is form construction and ours; the SENTENCE is the drawing's and it is built |

### Ours, and stated rather than quietly followed

| what changed | why |
|---|---|
| **three rows the old screen drew are GONE, and they are a real loss** — *its address becomes X* · *its pin moves to the new property's point* · *moving it back is a second move, not an undo* | The frame draws seven rows and none of them is these. Row 6 carries the address fact (*"their addresses are the building's, so all five change address too"*), so nothing is lost there; **the map pin and the not-an-undo sentence are lost outright.** The second is the reasoning behind the danger tier and it is now readable only in this file and in the component's own header. Recorded rather than kept, because an absence in a drawing is a decision (skill §2.5) — but it is the one item on this screen worth putting back if a clerk misses it |
| `postedMoneyNote` is gone from ABOVE the fields | Its two halves are rows 1 and 2. **The cost: a clerk who has not yet picked a destination no longer reads the posted-money guarantee at all**, because the table is drawn only once there is a move to describe. That is the frame's own shape; it is stated here because it is a behaviour change, not a re-wording |
| the panel's teal border | None. This file is not on `route-b-migrated.txt`, so a utility written here renders as nothing (B14 rule 21's per-file clause). The heading is an unclassed `<h4>` and the table is the kit's |
| `Bills it has produced · Cannot be counted` | Unchanged, and still `DEF-511`. The seam resolves at call time, so the number appears the day `apps/billing/selectors.issued_bill_count_for_unit` lands, with no change to this file. `MoveUnitModal.test.tsx` asserts BOTH states so the hold cannot expire unnoticed |
| the drawn values `101 Silver Creek Rd, Ottumwa, IA · P-00041`, `8 Sep 2026`, `two accounts`, `the 5 tagged` | **B14 rule 37** (PO 2026-09-10): *"Treat every number drawn in a wireframe as an illustration, never a fact to build to."* Every figure comes from the server's `move-preview` and the date is the tenant's format through the one shared picker. No test asserts a drawn number |

## Found in a BROWSER, and by nothing else (hard-won law 6)

**`Currently on` is address-first and the `Move to` PICKER is still
number-first**, so the two premises on this screen are written in opposite
orders — `1408 Bluestem Ln · P-00001` above `P-00002 · 2201 Cane Island Pkwy`.
The frame draws `Currently on`'s order explicitly and does not draw a chosen
value for `Move to`, so only the first is a conformance failure and it is fixed.
The picker's option format comes from `premisesPickerOptions`, which the units
LIST filter also renders, so changing it moves a screen belonging to
`CR-089-p050`'s lane. **Recorded, not changed** — and worth changing there,
because two orderings of one fact on one screen is what a reader notices.

**And the title loses the drawn noun** — `Move Unit 1 to another property`
became `Move Unit Unit B to another property` on real data. See
`CR-089-p087`'s browser section for the reasoning; the same correction.
