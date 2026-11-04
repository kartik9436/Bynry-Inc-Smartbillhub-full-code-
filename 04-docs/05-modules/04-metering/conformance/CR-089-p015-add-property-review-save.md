# P3 · Add a property · Review & save — the DRAWN specification

> ⚠ **SUPERSEDED 2026-10-09 BY `CR-177-BRC10` (Add a premise, redesigned; PO GO of that date).** The screen this file specifies is redrawn: *Property · Units · Review* with no *How many?* step, one *Address* section with *Check address*, Owner by search and link, and a grouped *Check before saving*. The drawing is `05-prototype/add-premise-2026-10-09/`; the rules are `BR-MET-1190`–`1195` (`02-business-rules.md`). Read this file as history, not as the specification.

`S16 · PRM-07` — **state chip: `EXISTS BEHIND`**
Blueprint *Premises & Units Blueprint 2*, **page 15** (screen head, amber block
and the start of the frame) → **page 18** (rules row). The grey frame runs
across **pages 15, 16 and 17**.

**Commitment chips on the screen:** `PUJ-02` · `PUJ-04` · `PUJ-05` · `PUJ-07` ·
`PUJ-08` · `PUJ-09`.
**CR-089 task rows this screen belongs to:** `B7` (the review shows every answer
and the numbers the series will take) · `B8` (a refusal is fixable where it
happens) · and the rows whose answers it must reflect back — `A4` (parcel, point
and the GIS flag), `B1` (owner optional), `B5` (common areas), `B6` (route and
cycle).

> **This file records the GREY FRAME only.**

**Breadcrumb drawn above the frame:** `Premises → New premise → step 3`
**The question the screen answers:** *is this right, before it becomes real?*

---

## Header

| slot | drawn string |
|---|---|
| kicker | `PREMISES & UNITS` |
| title | `Review & save` |
| subtitle | `Everything you have entered. Nothing is written until you press Create.` |

## Actions — in the order drawn

**In the header, top right:** `Cancel` — secondary, and it is the **only**
header action. `Save draft & exit` is NOT drawn on this step.

**In the footer:**

| # | label | tier |
|---|---|---|
| 1 | `← Back` | secondary |
| 2 | `Create premise ✓` | **primary** |

*"`Create premise ✓`. The tick is the grammar for a commit — this is the press
that writes."*

## The step rail — in order

`✓ One premise` | `✓ Details` | `3 Review & save`

*"The numbered rail above is clickable back to any finished step."*

## Tabs

**None.**

## Tiles

**None.**

## Fact rows — SEVENTEEN, one column, in this exact order

The label column is bold; the value column carries a muted suffix where one is
drawn. **The suffix is part of the row.**

| # | drawn label | value as drawn | muted suffix |
|---|---|---|---|
| 1 | `Premise number` | `P-00080` | `· the next in this utility's series` |
| 2 | `Unit numbers` | `U-01144 to U-01147` | `· four, from the unit series` |
| 3 | `Address` | `412 Cypress Row, Silver Creek, TX 78611` | — |
| 4 | `Parcel` | `R-114-0082-004` | — |
| 5 | `On the map` | `30.752104, −98.238391` | `· placed by the address lookup` |
| 6 | `Checked against GIS` | `Not checked yet` *(absent style — italic, grey)* | — |
| 7 | `Property type` | `Apartment complex` | — |
| 8 | `City limits` | `Inside` | `· city tax and the inside-city rate apply` |
| 9 | `Area` | `North Silver Creek` | — |
| 10 | `Sub-area` | `Cypress Row` | — |
| 11 | `Read route` | `Route 12 — North Silver Creek` | — |
| 12 | `Billing cycle` | `Cycle 3 — bills on the 12th` | — |
| 13 | `Utility services` | `Electric · Water · Sewer · Trash` | — |
| 14 | `Owner` | `Creekside Holdings LP` | — |
| 15 | `Managed by` | `Cane Island Property Co` | — |
| 16 | `Units` | `4 — labelled 1, 2, 3, 4 · Residential` | — |
| 17 | `Common areas` | `Laundry · Corridor lighting` | `· both bill to the owner` |

⚠ **AN EIGHTEENTH ROW IS DRAWN AND THE DRAWING DOES NOT HAVE IT — `DEF-MET-5844`,
2026-09-19, recorded here rather than made silently.** `Account type` renders
between `Managed by` and `Units`, and it is a DIVERGENCE from this frame, stated
under B14 rule 41 rather than absorbed.

| 17a | `Account type` | `Residential`, or `No owner account will be created.` *(absent style)* | — |

**Why it is here at all.** PO 2026-08-31 (`CR-056`) — *every address gets its
owner a Master Account* — and `customers.create_master_account` refuses a missing
account type by name, because it is the consumer category the bill is priced and
reported by. The form had no box for it, so `create_premises` opened no account
for anybody. The blueprint could not draw this row because the form it drew never
asked the question.

**Why it is a CONSEQUENCE and not an ordinary absent row.** Every other unanswered
row says *not answered*, which is true and useless. This is the last screen before
an address is written without its owner's account, so the blank state names what
will not happen. B14 rule 33 caps a consequence at six words per sentence, at most
two, and says never cut below clarity: **`No owner account will be created.` is
six words**, counted on the rendered screen.

**Where the drawing should go next.** The frame is the authority (rule 41) and a
row we added is a thing to put back to the PO with the drawing, not a thing to
leave as an exception forever.

⚠ **`OQ-MET-12472` CLOSED ON 2026-09-19 AND THIS PARAGRAPH IS AMENDED RATHER
THAN LEFT POINTING AT A LIVE QUESTION.** It used to read *"It rides with
`OQ-MET-12472`"*, and that question is settled: the PO ruled that the form
COLLECTS the owner's kind and one identifier, so the divergence is now LARGER
than the one row this file recorded — the step draws a `Person or company`
control and, once a kind is picked, that kind's identifier boxes, none of which
the frame draws. **All of it is still an exception to be put back to the PO with
the drawing**, and it is now `BR-MET-1176` that it rides with rather than an open
question. ⚠ **AND THE REVIEW ROW'S OWN TEST CHANGED WITH IT:** the row used to
read the account type alone, so a property with a type chosen and nobody
identified promised an account the server then declined. It now asks whether the
account will actually open (`ownerAccountWillOpen`), and the same six-word
sentence covers every declining case.

**The two numbering rows are FIRST, not last.** *"A clerk needs the property
number the moment the record exists — it is what they read down the phone — and
until now the first place it appeared was after the save."*

**Rows 1 and 2 carry their own refusal**: *"If the series has not been set up,
this row says so by name and offers the way to set it; it never invents a number
and never quietly leaves one out."*

## The map

**A map is drawn with the rows**, between the fact list and the consequence box.
*"The map comes with it, so the last check before committing includes* is this
the right building*, not just* is this the right text*."*

## The consequence box

Headed **`WHAT THIS WILL DO`**, drawn beneath the fact rows, teal-bordered:

> One property, four units and two common areas are created. Each unit can then
> take service, and nothing is billed until an account is opened on it. The four
> units start vacant, and base charges on a vacant unit reach the owner — as do
> both common areas, always.

## Footer

`← Back` (left) · `Create premise ✓` (right, primary), and beneath the row, one
line only:

`Recorded in the audit log by the server: who, when, and what.`

**One audit sentence, not two.**

## Table columns

**None.** *"Nothing is editable, which is the point — reading and changing are
different acts and this screen only does one of them."*

## States — the exact sentences

| state | what the frame says |
|---|---|
| **Everything answered** | *Ten rows, no gaps.* |
| **Something optional left blank** | *The row is drawn in the absent style — **italic and grey** — never as an empty cell, so `not set` and `zero` cannot be confused.* |
| **The write fails** | *The failure names the field and the step it lives on, and the rail takes you straight there. **It does not offer an error report.*** |

**A refusal never lands on this screen.** *"Every required field is checked on
the step that asks it, so this screen either commits or does nothing. The
bulk-upload's `Download error report` button is gone from a one-property form,
where it never belonged."*

## Components named by the drawing

`WizardFrame` · `PlainTable` · `Panel` · `Note`

## Rules the screen must obey

A consequence preview before any commit that changes service state. Money at two
decimals on screen and four in store. **An absence is drawn as an absence and
never as a zero.**

## Cognitive-load budget

**Ten rows, one map, one consequence box, two buttons.**

---

## One internal contradiction in the source, recorded rather than resolved

The cognitive-load row and the *Everything answered* state both say **ten
rows**; the frame draws **seventeen**, and the teal block says *"all ten
answers"*. **The frame draws seventeen and seventeen is the specification** —
the "ten" is a count of the ANSWERS A CLERK GAVE, and the drawing adds the two
allocated numbers, the parcel, the point, the GIS flag, the sub-area and the
common areas on top of them.

---

## BUILT — 2026-09-10, and where the product deliberately diverges

`07-frontend/src/features/metering/AddPremisesWizard.tsx`, `SingleReview` ·
commit `5f90fc493`. **All seventeen rows are on the screen, in the drawn
order**, and `AddPremisesWizard.test.tsx` asserts that list spelled out rather
than derived from the component (a test that reads the component's own order
and asserts it is a check that cannot fail).

### What changed, against what shipped

| # | drawn | what shipped before today |
|---|---|---|
| 1-2 | `Premise number` · `Unit numbers` FIRST | drawn LAST, after the units |
| 12 | `Billing cycle` | not rendered at all |
| 15 | `Managed by` | rendered as `Owner / manager`, the control's label |
| 16 | `Units` → `4 — labelled 1, 2, 3, 4 · Residential` | `Also create a unit automatically: Yes` — a tick-box read aloud |
| — | `WHAT THIS WILL DO` | absent; `ConsequenceBox` was imported zero times (`DEF-4741`, now `fixed`) |
| — | the absent style, italic and grey | the plain string `not answered`, in the ink of an answer |

Two more, found while building and not in the task list:

* **`Owner` printed `values.owner_id` — a UUID on a clerk-facing screen**,
  which B14 rule 31 forbids by name. It resolves to the party's NAME now.
* **`Area`, `Sub-area` and `Read route` printed lookup CODES.** All three
  resolve to names, read from the same caches the details step fills, so the
  review and the form cannot disagree about what was chosen.

### Ruled out of scope, not built

**The map between the fact list and the consequence box.** PO ruling
2026-09-10, verbatim: ***"(b) Out of scope — amend the drawing"*** — the
drawing is amended, not the product. The frame's argument for it (*"the last
check before committing includes* is this the right building*"*) is recorded
and declined. **A test asserts the absence**, so a later lane adding one is
building something the PO declined rather than filling a gap.

### Built differently, and why

1. **The rows are a `<dl class="met-facts">`, not `PlainTable`.** The
   components row names `PlainTable`; a label/value list is what `<dl>` is for,
   `met-facts` is the class every other metering fact block already uses, and
   the frame's own *"Nothing is editable"* is satisfied either way. Recorded
   rather than re-cut.
2. **The consequence box is the kit's `check` tone, which is not teal.** The
   blueprint's teal is the BLUEPRINT's palette; `--color-accent` in this theme
   is `#ec3013`. Where the wireframe and the design system disagree, the system
   wins and the difference is filed — B14 rule 36 says the shared kit is how
   you comply.
3. **The `Units` and `Common areas` rows say so when empty**, in the absent
   style, rather than being omitted. The drawing shows a filled example only.
4. **One audit sentence.** The panel used to add `Saving writes an audit
   record…` on top of the page's `Every change here is recorded…`, which sits
   directly beneath the footer where the frame draws its one line. The page's
   is the one that stayed, and a test asserts the other is gone.
5. **The header still reads `Add premises & units`** rather than the drawn
   per-step `Review & save` with its own sub-line — one `PageHead` serves four
   entry modes. See `CR-089-p008`'s note 3. `Save draft & exit` IS correctly
   absent from this step; `Cancel` alone is drawn, and a test asserts both.
6. **`Create premise ✓` is correct and was already correct.**

### The seventeen-versus-ten contradiction

Recorded above and unchanged: the frame draws seventeen and seventeen is what
is built. The two `ten`s in the source are a count of the ANSWERS A CLERK GAVE.
