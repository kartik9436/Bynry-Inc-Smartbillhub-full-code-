# U3 · Add units · Review & create — THE DRAWN SPEC

> ⚠ **SUPERSEDED AS THE SCREEN'S DRAWING ON 2026-10-09 (`CR-176-BRC10`, `DEF-MET-10035`).** The PO approved a redesign of Add units and gave the go the same day; the screen is now built from `05-prototype/add-units-redesign-2026-10-09/images/01–11`. Rules `BR-MET-1196`–`1201` (next free start, one count, services from the building all ticked, building by search and *Use this building*, a common area chosen at the top, unit numbers from the series unless *My own pattern*). This file stays as the record of what the blueprint frame drew and of the rulings it carried that the redesign KEEPS (`Floor` free text, `Floor area` on the add form, every plan with a search, `← Units` / `Cancel`).

`S16 · PRM-07` — **state chip: `NEW BUILD`**
Blueprint *Premises & Units Blueprint 2*, **page 59** (the chip line and the
screen title) → **page 60** (the question, breadcrumb, amber block, the grey
frame's head, step rail and the first eight answer rows) → **page 61** (the last
two answer rows, the *THIS WILL CREATE* panel, its note, the footer and the
first four teal bullets) → **page 62** (the last teal bullet and the detail
table) → **page 63** (components and rules).

**Commitment chips on the chip line (page 59):** `PUJ-08` · `PUJ-25` · `PUJ-26`.
**CR-089 task rows this screen belongs to:** `E6` (*a review step before
anything is written*, `PUJ-26`) · `E5` (*a plan can be attached at creation*,
`PUJ-25`) · and `PUJ-08`'s half of `BR-MET-1165` — *a number a review shows is
taken on the PRESS, never reserved by the preview* — which this screen shares
with `B7`, the property review on page 15.

> **`NEW BUILD` means the blueprint says this screen does not exist in the
> product.** ⚠ **IT EXISTS NOW.** `CR-089` wave E built it on 2026-09-09 as step
> 2 of `07-frontend/src/features/metering/AddUnitsWizard.tsx`, routed at
> `/premises/units/new`. The chip is a statement about the day the blueprint was
> drawn, not about today, and the diff below is against a real screen.

> **This file records the GREY FRAME only.** The amber block on page 60 —
> *"There is no review at all. The unit generator writes on the press."* — is the
> PROBLEM STATEMENT. Where a commitment sentence disagrees with the frame, **the
> frame wins** (PO ruling 2026-09-10).

**Breadcrumb drawn above the frame:** `Premises → + New unit → step 2`
**The question the screen answers:** *is this right, before three flats become
real?*

---

## 1 · Header

| slot | drawn string |
|---|---|
| kicker | `UNITS` |
| title (H1) | `Review & create` |
| subtitle | `Everything you have entered. Nothing is written until you press Create.` |

**In the header, top right:** `Cancel` — secondary, and it is the **only**
header action drawn on this step.

## 2 · Step rail — two steps, `2` active, step 1 done

`✓ Details` | `2 Review & create`

Step 1's badge is a **tick**, not its number.

## 3 · The answer rows — TEN, label left, value right, in this order

| # | drawn label | drawn value | notes |
|---|---|---|---|
| 1 | `Building` | `412 Cypress Row` **strong** · `P-00080` quiet · `Silver Creek, TX 78611` · `Apartment complex` | the address leads; the number follows |
| 2 | `It has today` | `1 unit, numbered 1` | |
| 3 | `Route and cycle` | `Route 12 · Cycle 3` then `— every unit made here inherits both` in the quiet tone | |
| 4 | `Services` | `Electric · Water · Sewer · Trash` then `— from the building` quiet | |
| 5 | `How many` | `3, numbered from 2` | |
| 6 | `Unit numbers` | `U-01145 to U-01147` then `· three, from this utility's unit series` quiet | |
| 7 | `Unit type` | `Residential` | |
| 8 | `Floor` | `Not recorded` — **muted italic, the absence style** | |
| 9 | `Plan` | `Residential Standard` then `· from the day each unit is created` quiet | |
| 10 | `Common areas` | `None being added here` — **muted italic, the absence style** | |

**Page 62, verbatim:** *"Every answer is on it, including the ones left blank.
`Floor — not recorded` and `common areas — none being added here` are drawn as
absences, not left out. The property review had the opposite fault: eight
answers given, four shown."*

**Rows 1–4 are what the BUILDING lends** and rows 5–10 are what the clerk
entered. There is **no owner row** on this screen.

## 4 · The `THIS WILL CREATE` panel

A bordered consequence panel with its own caps kicker, `THIS WILL CREATE`,
drawn beneath the answer rows.

### Its table — FIVE columns, in this order, one row per unit

| # | drawn header | alignment | cell |
|---|---|---|---|
| 1 | `Label` | left | `2` · `3` · `4` — **strong** |
| 2 | `Unit number` | left | `U-01145` · `U-01146` · `U-01147` |
| 3 | `Type` | left | `Residential` |
| 4 | `Plan` | left | `Residential Standard` |
| 5 | `Starts` | left | `Vacant, no meter` — **muted italic** |

**All three rows are drawn.** Nothing is elided and there is no *and N more*
line.

### The note inside the panel, verbatim

`Unit numbers come from this utility's series in Settings — they are taken when
you press Create, not now. Each unit starts vacant with no meter, and base
charges on a vacant unit reach the owner.`

## 5 · Footer

Left: `← Back` — secondary
Right: `Create 3 units ✓` — **primary**

Beneath the footer row, one line, left-aligned, quiet:
`Recorded in the audit log by the server: who, when, and what.`

**Primary action, verbatim (page 62):** *"`Create 3 units ✓` — a tick commits,
and the count is in the button."*

## 6 · States — the frame's own STATES block, verbatim

| state | drawn behaviour |
|---|---|
| **A label clashed while you reviewed** | *"The refusal names the clash in five words and `← Back` lands on the field that caused it, not at the top."* |
| **The series moved** | *"Another clerk took U-01145 meanwhile. The numbers are re-read on the press, the preview updates and the commit says what it is about to take."* |
| **Refused by the server** | *"The failure appears above the button with the field named — never a `Retry` and a `Download error report` on a screen with nothing to fix."* |

## 7 · Components named by the drawing

`WizardFrame` · `StepRail` · `PlainTable` · `ConsequencePanel` ·
`RefusalStrip` · `Note`

## 8 · Cognitive-load budget, as stated

*"Ten rows of answers, one preview table of three rows, two buttons. **No prose
beyond one consequence note.**"*

## 9 · Rules it must obey, verbatim

*"A consequence preview before the commit. Button grammar: an arrow navigates,
a tick commits. An absence is drawn as an absence. A refusal is short and says
what to do. Every money-or-service action is recorded with who, when and what."*

## 10 · How you get here

*"`Continue →` from step 1. `← Back` returns with everything still filled in."*

## 11 · Absences — drawn as absent, do not fill them

* No `Owner` row and no `master account` on this step, although the step-1 card
  draws both.
* No `Retry` and no `Download error report` — named as forbidden by the
  *Refused by the server* state.
* No second audit sentence: **one** line, beneath the footer.
* No elision of the preview rows.

---

## Contradictions inside the source, recorded rather than resolved

1. **`U-01145 to U-01147` is an illustration, not a figure to assert.**
   `CR-089` §E6 already records this for the built screen — *"the numbers are
   not `U-01145`–`U-01147` and were never going to be"* — because the series is
   the tenant's own. What must hold is `BR-MET-1165`: the numbers shown are what
   the series will issue NEXT, and the screen must never say they are held. The
   drawn strings are recorded here as drawn; the RULE is what a test asserts.
2. **`Starts` names two different things across the two frames.** On page 55
   (`U2`) `Starts` is the plan's start date — *"The day the unit is created"*.
   On page 61 (`U3`) the preview table's `Starts` column reads `Vacant, no
   meter`, which is the unit's starting STATE. One word, two facts, in one
   wizard. Recorded.
3. **The teal block calls the note *"one consequence note"* and the frame draws
   two quiet lines** — the panel note and the audit line beneath the footer.
   The frame draws both. Recorded.

---

## AMENDMENTS — what was BUILT on 2026-09-10 (`DEF-MET-4772`)

The step existed and drew a building card, three sentences and a three-column
table capped at five rows. It now draws **the ten answer rows §3 names, in the
drawn order**, with `Floor` and `Common areas` as ABSENCES rather than omitted
rows; the preview table's **five** drawn columns, `Type` and `Starts` included;
and **every** row.

**The cap was the defect worth naming.** The table showed five and printed *and
N more, ending at …* underneath — so on any run above five the rows a clerk
cannot see are the rows they cannot check, which is the only thing a review is
for. The table scrolls inside its own container now; the page never does.

**The panel is the kit's.** `PlainTable` and `ConsequenceBox` are both in
`components/` and were imported ZERO times here; the panel was a plain `Panel`
with a hand-rolled `<table>` and a hand-rolled note. `B14` rule 36: compose the
kit.

### Departures, recorded rather than left to be found

1. **THE CONSEQUENCE NOTE IS SPLIT ACROSS THE BOX'S `title` AND `body`.**
   `ConsequenceBox`'s staff shape renders `body` inside a `<p>`, so the drawn
   panel — a caps kicker, a TABLE and a note — cannot be one box. The kicker is
   the panel's, the table sits under it, and the drawn note's two sentences are
   the box's bold line and its body, verbatim and in order.
2. **NO DRAWN FIGURE IS ASSERTED ANYWHERE.** `B14` rule 37 (PO 2026-09-10):
   *"Treat every number drawn in a wireframe as an illustration, never a fact to
   build to."* Contradiction 1 above already said it for `U-01145`–`U-01147`;
   the suite pins the SHAPE — a range where the frame draws a range, every row
   where the frame draws every row.
3. **`Starts` MEANS THE UNIT'S STARTING STATE HERE AND THE PLAN'S START DATE ON
   STEP 1.** Contradiction 2 above records the collision and it is built as
   drawn: the review's column reads `Vacant, no meter`, and the plan's own start
   is the quiet trailer on the `Plan` row.

### FOUND IN A BROWSER, NOT BY A TEST (`10-scripts/cr089_u1u2u3_units_screens_walkthrough.mjs`)

* the `Services` answer row was labelled **`Utility services`** — the premises
  column's spelling of the same fact — where the frame draws `Services`. That
  two keys in this product name one fact differently is `B14` rule 34's
  business and is recorded rather than swept.
* the preview table headed its first two columns **`Unit`** and **`Unit ID`**,
  borrowed from the units list's column chooser. The frame draws `Label` and
  `Unit number`, and they have their own keys now.

**Still divergent, each recorded rather than built:**

1. **BEYOND THE FIRST FIVE, A ROW SAYS `Next in the series` RATHER THAN A
   NUMBER.** `GET /units/number-preview` answers with five numbers and the last
   one, so on a run of seven the answer row can name the RANGE and the table
   cannot name rows six and seven. Nothing is elided — every row is drawn — and
   the screen says what it does not know instead of counting on from the last
   number it was given, which would be a second implementation of the
   allocator. Serving a number per row is a server change with a real cost.
2. **THE FOOTER DRAWS `Back`, NOT `← Back`**, and the audit line is the
   product's shared sentence rather than the frame's wording. Both are
   `WizardFrame`'s and `metering.auditLine`'s, shared by every wizard and every
   list; `B14` rule 34 wants ONE pair of words per fact and rule 38 leaves
   construction with the kit.
