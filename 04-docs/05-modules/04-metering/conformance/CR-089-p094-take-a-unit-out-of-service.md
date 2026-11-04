# U12 · Take a unit out of service — THE DRAWN SPECIFICATION

**Source:** *Premises & Units Blueprint 2*, **pages 94–96** (plate header p94,
amber block p95, screen frame p95, teal *WHAT CHANGED* p95–p96, frame metadata
p96). Extracted 2026-09-10 from
`05-prototype/Premises & Units Blueprint 2.pdf` (md5
`f034d6e42c0caad658fadfdf6e4704eb`), read page by page with
`10-scripts/pdf/pdf_text.py` **and looked at** as a rendered PNG at scale 1.6 —
the two-up first field row, the amber refusal TABLE with its per-row links and
the held line BELOW the footer are DRAWN, not written.

**State chip:** `NEW BUILD` · **Commitment:** `PUJ-48`
**Screen ids:** `U12` — `S15 · PRM-03`
**CR-089 task row:** **`D2`** (wave D — a unit can be taken out of service,
`PUJ-48`, `BR-MET-1164`)

⚠ **`NEW BUILD` MEANT *DOES NOT EXIST* WHEN THE BLUEPRINT WAS DRAWN.** It exists
now: `07-frontend/src/features/metering/StatusChangeDialog.tsx`, landed by
CR-089 wave D and shared with the property's `P11`. A **second door** also
exists — a `Deactivate` row action on the units list
(`UnitsListPage.tsx:677`) posting `POST /units/{id}/deactivate`, which records
neither a date nor a reason. The chip is recorded as drawn.

⚠ **EVERYTHING BELOW IS FROM THE BORDERED GREY FRAME ONLY.** The amber block on
page 95 (*"There is no way to do this…"*) is the problem, not the target; the
teal *WHAT CHANGED* block on pages 95–96 is rationale. Neither is
specification.

⚠ **THE VALUES ARE ILLUSTRATIONS; THE LABELS, THE ORDER AND THE PRESENCE OF EACH
ROW ARE THE SPECIFICATION** (the standing caveat in `09-screen-conformance.md`).

---

## Header

**Kicker** `UNIT`
**Title** `Change status`
**Sub-line** `Unit 2 · 412 Cypress Row · currently Active`

A horizontal rule closes the identity block before the first field.

⚠ **THE TITLE IS THE NEUTRAL `Change status`, NOT THE COMMIT.** The commit word
is on the footer button only, and the frame metadata says the control is *"in
the same place and the same words as the property's"* — `P11`'s title is also
`Change status`.

## Actions, in the order drawn

| # | label | tier | where |
|---|---|---|---|
| 1 | `Cancel` | secondary | top right of the frame, on the title row |
| 2 | `Open it →` | inline link | first blocked row, right-aligned |
| 3 | `Show them →` | inline link | second blocked row, right-aligned |
| 4 | `Cancel` | secondary | footer, left |
| 5 | `Deactivate unit` | **danger** (outlined amber, not filled) | footer, right |

**Primary action:** `Deactivate unit`, in the danger tier. **No `✓`** is drawn
on this commit — unlike `U10`'s `Save changes ✓` and `U11`'s `Move unit ✓`.

## Tabs

**None.**

## Tiles

**None.** `COGNITIVE LOAD`: *"Three inputs, one refusal panel, two buttons."*

## Fields — three inputs, in this order

**`New status` and `From` share one row, two-up; `Why` sits alone on row 2 at
full width.**

| # | label | control | drawn value | width |
|---|---|---|---|---|
| 1 | `New status` **\*** | select | `Inactive — no longer takes service` | left of a 2-up row |
| 2 | `From` **\*** | date | `09/30/2026` | right of that row |
| 3 | `Why` **\*** | text, single line | `Merged into Unit 1` | full row |

All three carry a required asterisk. **No help line is drawn under any of the
three.**

## The refusal panel

Amber, drawn **BELOW the three inputs**, inside the frame.

**Panel heading:** `NOT WHILE THIS IS LIVE`

**Table** — a plain two-column table, one row per blocker, in this order:

| # | left column (text, left-aligned) | right column (link, right-aligned) |
|---|---|---|
| 1 | `Account A-10517 is still open` | `Open it →` |
| 2 | `2 meters are still on this unit` | `Show them →` |

**Helper beneath the table, verbatim:**
`Close the account and remove the meters first. Then this can be done.`

⚠ **ROW 1 NAMES THE ACCOUNT NUMBER**, it is not a count. Row 2 IS a count.
⚠ **TWO ROWS ARE DRAWN.** `P11`'s teal block (p42) says *"A unit's version is
the same screen with one row: whether an account is open on it."* — see
*Contradictions*.

## Footer

A horizontal rule, then `Cancel` *(secondary, left)* · `Deactivate unit`
*(danger, outlined, right)*.

**Beneath the footer, left-aligned, in the grey helper style:** the held line —
`Held: an account is still open.`

## Table columns

**None** beyond the refusal table above.

## States — exact sentences

| state | drawn sentence |
|---|---|
| **Blocked** | `The blockers, each linked, and the commit held with a five-word reason.` |
| **Clear** | `The refusal panel is replaced by the consequence: what stops billing and what the record will read afterwards.` |
| **Already inactive** | `Offers reactivation instead, with the same date and reason.` |

⚠ **THE CONSEQUENCE AND THE REFUSAL ARE ALTERNATIVES, NOT NEIGHBOURS** — the
*Clear* state says the refusal panel is **replaced by** the consequence. The
drawn frame is the blocked state and carries **no consequence box at all**.
Same reading as `P11`.

## Frame metadata

* **FOR** — `A clerk closing a flat — merged, demolished, or converted to a common area.`
* **HOW YOU GET HERE** — `The unit's page → Change status. Deliberately the only route.`
* **PRIMARY ACTION** — `Deactivate unit, in the danger tier.`
* **WHAT CHANGED · IT EXISTS** — `Neither the property nor the unit had a status control, and the unit's page gave advice that assumed one.`
* **WHAT CHANGED · THE REFUSAL IS THE SCREEN** — `Not a toast. Each blocked thing is a row with a link, so why not is also the route to do this first.`
* **COGNITIVE LOAD** — `Three inputs, one refusal panel, two buttons.`
* **COMPONENTS** — `ConfirmDialog` `FormModal` `PlainTable` `RefusalStrip` `StatusPill`
* **RULES** — `The danger tier for destructive commits. A refusal caps at five or six words. Every service action is recorded with who, when and what.`

## Commitment this screen carries

| id | statement | done looks like (verbatim) |
|---|---|---|
| `PUJ-48` | A unit can be taken out of service | `A clerk presses Change status on a unit, sees 1 open account · 2 attached meters, and the commit is held reading Close the account first; once clear, a date and a reason are required.` |

## Contradictions inside the blueprint, recorded and NOT resolved

Per the PO ruling of 2026-09-10 the **frame wins and the sentence gets
corrected**. Four found in this section:

1. **One blocker row or two.** `P11`'s teal block (p42) says the unit's version
   is *"the same screen with one row: whether an account is open on it"*; the
   `U12` frame draws **two** rows — the open account and `2 meters are still on
   this unit`. Frame wins: two rows.
2. **How the blockers read.** The frame draws `Account A-10517 is still open`
   and `2 meters are still on this unit` with a link labelled `Open it →` /
   `Show them →` beside each. `PUJ-48`'s *done looks like* (p105) quotes the
   same panel as `1 open account · 2 attached meters` — counts on one line,
   which is a different drawing. Frame wins: two table rows, each with its own
   link.
3. **`meters` or `assets`.** The frame draws `2 meters are still on this unit`;
   the PO ruled the same day that on a unit *"Meter = assets"* (`CR-089` D2,
   recorded in the decision log), and the list a clerk is sent to is the unit's
   **Assets** tab. Flagged rather than settled by §16, because the ruling is the
   newer statement and it is the PO's.
4. **A numeric date on a document that argues against one.** The frame draws
   `From · 09/30/2026`, while its neighbour `U11` (p91) draws `8 Sep 2026` and
   the same document's `PUJ-47` makes *"a date picker, not a format
   instruction"* a commitment. `PUJ-47` names screen `U11` only, so `U12`'s
   numeric date is drawn without a commitment either way. Recorded.

---

# WHAT WAS BUILT, 2026-09-10 — and every difference that REMAINS

**Fixed under `DEF-MET-4761` (the second door) and `DEF-MET-4763` (the frame).**
Proof: `StatusChangeDialog.dom.test.tsx` (nine cases, four shown red first) and
`UnitsListOneDoor.dom.test.tsx` (five cases, all five shown red first).

⚠ **THE SECOND DOOR IS THE HEADLINE AND IT WAS A MONEY-ADJACENT RECORD LOSS.**
`UnitsListPage.tsx:677` drew a `Deactivate` row action opening a plain
`ConfirmDialog` that posted `POST /units/{id}/deactivate` with **no date, no
reason and no dependency list**. Both doors always enforced `BR-MET-1164`
through one computation, so nothing unsafe ever got through either — what
differed is what was WRITTEN DOWN. A clerk who took a flat out of service from
the LIST left no record of when it took effect or why, and the effective date
and the reason live in `audit_log` and in NO column, so neither could be
recovered afterwards.

This is `DEF-4743` one level down. The PO ruled that one the same day, option
(b) — *keep the shortcut, point it at the real dialog* — so the ruling was
applied rather than put back to them (hard-won law 13). The bad door is deleted
from the screen and `services.deactivate_unit` now validates the same three
fields and delegates to `change_unit_status` with the status forced to
`inactive`. **Two behaviour changes at the API, stated rather than discovered:**
the payload is now required, and the call is no longer idempotent — deactivating
something already inactive is refused by name instead of answering 200.

## Closed

| # | what the frame draws | what it now does |
|---|---|---|
| 1 | *"The unit's page → Change status. Deliberately the only route."* | The list row opens the same dialog. One door, one audit shape |
| 2 | `New status` **\***, the first of three inputs | A `SelectField` carrying the one legal destination in words — *Inactive — no longer takes service*. It did not exist; the product inferred the target and never said it |
| 3 | three inputs, THEN the refusal panel | Was inverted — counts, hold, consequence, then the two questions — so a clerk read the verdict before saying what they were doing |
| 4 | the panel heading `NOT WHILE THIS IS LIVE` | Present. The panel had no heading at all |
| 5 | a plain two-column **table**, one row per blocker, each with its own link | A `PlainTable` from the kit. It was a flex-wrap `<ul>` of inline links, with the count itself as the link text |
| 6 | `Account A-10517 is still open` — a NAME | `unit_status_dependencies` now sends the account number as `reference`, and the row names it. A unit is blocked by at most one account, so the number is knowable; a clerk with two flats open could not tell which account the refusal meant |
| 7 | `Open it →` / `Show them →` | One destination is a single record, the other is a list, so the two links are not the same word |
| 8 | the consequence **replaces** the refusal | Was drawn always (`:349`), so a blocked screen showed a panel saying it cannot be done above a box describing what would happen when it was |
| 9 | `Deactivate unit` on the footer | The drawn label lived on the door being deleted; the good dialog said `Take out of service`. Moved |
| 10 | `From` **\*** and `Why` **\*** | Were `Date of the change` and `Why it is changing` |

## Divergences that REMAIN, each with its reason

### Ruled by the PO, 2026-09-10 — not ours to build

| what the frame draws | why not |
|---|---|
| `New status` and `From` two-up on one row | **B14 rule 38.** *"if youa re doing a form - go as per our UI rules."* |
| the held line BELOW the footer | B14 rule 38 — a slot under `ModalShell`'s footer is a change to every dialog in the product. The hold sentence sits inside the refusal panel instead, which is where a reader is already looking |
| `Cancel` on the title row | B14 rule 38 — the shell's `✕` |

### Ours, and stated rather than quietly followed

| what the frame draws | what was built, and why |
|---|---|
| the title `Change status`, with the unit named on a sub-line | The title still reads `Take {{name}} out of service?`. The frame moves the unit's identity to a sub-line, and the sub-line is a `ModalShell` change we may not make — so taking the name OUT of the title would leave the dialog naming nothing at all. **This is the one place where obeying rule 38 and obeying the frame cannot both be done, and identity won** |
| the helper *"Close the account and remove the meters first. Then this can be done."* | Not built. It is two sentences of 13 and 16 words — over B14 rule 32's one-sentence budget and over `G33`'s twelve-word cap — and its first clause says the METERS block, which `BR-MET-1164` says they do not. The hold sentence (*"Close the account first"*, four words) stands in its place, and it is the frame's own held line |
| `2 meters are still on this unit` | `2 assets are still on this unit`. The PO ruled on 2026-09-08 that on a unit *"Meter = assets"*, which is the newer statement of the two, and the row links to the unit's **Assets** tab. Contradiction 3 above, decided |
| a zero row for every count the rule names | Only rows with something in them. The panel is drawn ONLY when blocked and its heading says something is holding this; a nought inside it is a line saying nothing is wrong. **This reverses `DEF-127`'s posture on this screen** — *"no open accounts"* and *"nobody looked"* were deliberately different — and the reassurance moves into the consequence, which the clear state draws instead |
| `From · 09/30/2026` | The tenant's own format through the one shared picker. **B14 rule 37**: a drawn figure is an illustration |

### Left to `CR-089-p041`'s lane, deliberately

`StatusChangeDialog` is shared with the property's `P11`, so every structural
change above applies to both — which is right, because `p041` draws the same
three inputs, the same table and the same *replaced by* rule. **Two things were
NOT touched:** the premises row ORDER (`DEPENDENCY_ORDER` renders units · meters
· accounts where `p041` draws units · accounts · meters) and the premises row
WORDING (still noun phrases — *3 open accounts* — where the frame draws
sentences). Both are that lane's, and moving its copy under it while it is
running is how two lanes make one screen worse.

## Found in a BROWSER, and by nothing else (hard-won law 6)

Two things `StatusChangeDialog.dom.test.tsx` was green over, both found on the
first screenshot of `10-scripts/cr089_unit_dialogs_walkthrough.mjs`:

1. **THE BLOCKED ROWS WERE IN THE PROPERTY'S ORDER.** `DEPENDENCY_ORDER` was one
   shared list — `active_units · attached_assets · open_accounts · unpaid_
   balances` — so a unit drew the meters ABOVE the account. The `U12` frame
   draws the account first, which is also the order the work is done in: the
   account is the only thing that HOLDS the commit. The order is now per
   subject, and both the dom test and the walkthrough assert the sequence rather
   than the presence.
2. **THE TITLE NAMED THE UNIT BY ITS SERIES NUMBER** — `Take U-00101-A out of
   service?` — while the edit form one click away said `Edit Unit B`. Both
   dialogs now compose the name through `unitFormTitle`.

⚠ **AND THE WALKTHROUGH ITSELF HAD TO BE FIXED THREE TIMES BEFORE IT COULD BE
TRUSTED**, which is hard-won law 7 in miniature. Its first run read the FIRST
button in the modal footer and reported the commit as `Cancel`, in the ghost
tier and not held — three green-looking failures about the wrong element. Its
second clicked that Cancel and then reported *"pressing the held commit posted
NOTHING"*, which was true and answered a question nobody asked. Its third
screenshotted the dialog before the counts arrived, producing a picture of the
loading skeleton. **Every one of those is a check looking at the wrong thing,
and the only reason they were caught is that a person read the output and the
image rather than the exit code.**
