# DIS-02 step 4 · Create · Effective & approval — THE DRAWN SPEC, AND WHAT IS BUILT

Blueprint screen **24**, `/:tenant/plans-rates/discounts/new` · **blueprint
pages 72–74**, frame drawn on **pages 72–73**.

**Source:** `05-prototype/SMARTBillHub Plans & Rates Blueprint.pdf`
(md5 `2e46f5053ca65804da9c1a90a487e044`), text **and** rendered PNGs at 2.0.

**State chip:** `BLOCKED` · **Commitment:** `PRB-13`

⚠ **`BLOCKED` MEANS A SPECIFICATION HERE WAITS ON A DECISION NOBODY HAS MADE.**
That decision is `PRB-13`, and it is the same open question the product already
carries as `OQ-290`.

**Re-verified at 2.234.19** (blueprint read at 2.232.0 / d2d493e4).

**Code read:** `DiscountWizard.tsx` — `EffectiveStep`, lines **1550–1701**.

---

## 1 · Header, actions, rail

As step 1, with `4 Effective & approval` active.

## 2 · The one panel — heading `Dates and budget`

Section sentence, verbatim, **one sentence**:

> `A discount attached to a plan is available, not granted — nothing here enrols`
> `anybody.`

## 3 · Controls, in the drawn order

| # | label | control | drawn value / help |
|---|---|---|---|
| 1 | `EFFECTIVE FROM` * | **date picker** (calendar affordance at the right) | `01/01/2027` |
| 2 | `EFFECTIVE TO` | **date picker** | placeholder `No planned end` · **no help line** |
| 3 | `BUDGET CAP` | money, help above the box | help `Blank means unbounded, which always needs a second approval.` · `7332.00` |
| 4 | `BUDGET PERIOD` * | dropdown | `Annual` |
| 5 | `WHEN THE BUDGET RUNS OUT` * | dropdown | `Suspend the discount` · **no help line** |
| 6 | `WHAT CHANGED, AND WHY` * | text area | *(empty)* |

## 4 · The callout, below the controls, inside the panel

Label `SECOND APPROVAL — OPEN`, accent left rule. Body, verbatim, **two
sentences**:

> `Two approved policies disagree about when a second approval is needed, and this`
> `$7,332 a year — $611 a month — falls between them. This one is with you.`

⚠ **LEFT ON THE SCREEN DELIBERATELY.** Page 73: *"it is a question for you
rather than a defect. Two signed policies test different things against
different bars, and the worked figure falls between them. Choosing one quietly
would make one policy disappear."*

⚠ **THE DATES WERE PLAIN TEXT AND ARE NOW PICKERS.** Page 73: *"…they had no
picker, no format hint and no help at all on the `from` box, so a clerk had to
guess whether this utility writes 06/01/2026 or 01/06/2026. They are pickers
now, matching the rest of the module — **and the format hint went with the
helper line, because a picker shows the format by existing.**"*

**Cognitive load, as stated:** *"Dates, then money, then the reason. One helper
line survives, on the only field where blank means something other than empty."*

## 5 · Footer

`Continue`, right. **PRIMARY ACTION:** `Continue.`

## 6 · States — verbatim

| state | drawn behaviour |
|---|---|
| **Creating** | *"The reason box is absent — there is no previous version to have changed from."* |
| **No budget cap** | *"The panel says a discount with no cap always needs the second approval, whatever the figure."* |
| **Editing** | *"The reason box is required and checked here, on the step it lives on — this wizard was already the only one that got that right."* |

## 7 · Components named by the drawing

`WizardFrame` `DatePickerField` `MoneyTextField` `SelectField` `TextArea`
`Callout accent`

## 8 · Rules, verbatim — one clause more than the other steps

*"… Built in the shared utility classes, adding nothing to a stylesheet.
**A date is a picker in the utility's own format, everywhere.**"*

## 9 · `PRB-13`, verbatim — what done looks like on screen

> *"A clerk saves a discount with a $7,332 annual budget and the screen states
> one test with one figure — 'needs a second approval: $611 a month is over the
> $500 threshold' — instead of naming two policies and asking the reader to
> choose."*

⚠ **`PRB-13` IS A COMMITMENT WAITING ON A RULING, NOT AN INSTRUCTION TO A LANE.**
The blueprint states both policies on purpose until the PO chooses.

## 10 · Absences — drawn as absent

* **No `Enrolment window` stated absence.**
* **No `Impact analysis` block.**
* **No approval-authority sentence.**
* **No `STEP 4 OF 5` kicker** and no step heading sentence.

---

## AS BUILT AT 2.234.19 — the diff, with evidence

### Matches

* **Both dates ARE the module's picker** — `:1585-1602`, `DatePickerField` with
  the tenant's `dateFormat` from `useRegional`. **CR-087 C3's control half is
  built**, asserted at `DiscountWizard.test.tsx:758`.
* **No format hint on the `from` box** — `:1585-1592` passes no `help`. Matches.
* `BUDGET CAP` help sits **above** the box — the kit renders `field-help`
  between label and control (`components/FormModal.tsx:238-243`). Matches.
* `WHEN THE BUDGET RUNS OUT` offers the three exhaustion behaviours with
  `Suspend the discount` among them — `:1633-1645`.
* **The reason box is absent when creating and required when editing** —
  `:1683-1697`, gated on `props.editing`. Matches both STATES rows exactly.
* **Both signed policies are stated and neither is resolved** — `:1670`
  (`secondApprovalConflict`), asserted at `DiscountWizard.test.tsx:770`.
* **The no-cap sentence** — `:1671-1673` (`budgetUnbounded`). Matches the STATES
  row.

### 1 · The callout quotes the WRONG figures, and this is the screen's live gap

| | drawn | built |
|---|---|---|
| the figures | `$7,332 a year — $611 a month` — **the clerk's own cap, and what it works out to** | `$500` and `$10,000` — the two policy thresholds |
| the closing sentence | `This one is with you.` | `The $10,000 test is the one that runs today, and choosing between them is with the Product Owner.` |
| sentence count | 2 | 2 |

`:1670` renders `secondApprovalConflict`:
*"Two approved policies disagree about when this needs a second approval: one
measures the projected monthly subsidy against $500, the other measures the
budget cap above against a setting that starts at $10,000. The $10,000 test is
the one that runs today, and choosing between them is with the Product Owner."*

⚠ **THE DRAWN VERSION ASKS THE SCREEN TO DIVIDE MONEY, AND THE CODE REFUSES ON
PURPOSE.** `:1655-1660` states the reason in the file: *"Quoting the clerk's own
cap back as a monthly figure would mean dividing money on this screen, which is
`DEF-364`'s shape exactly: the server owns every money conversion and this
wizard prints no figure it did not receive."* `$7,332 ÷ 12 = $611` is the
conversion. **A discount changes what a customer is charged, so a monthly-
subsidy figure is `B4`/`B5` territory: it is served or it is not shown.**
**Recorded for the PO. No lane should build the drawn sentence by dividing on
the client.**

⚠ **AND `Product Owner` IS AN INTERNAL WORD ON A CLERK'S SCREEN.** B14 rule 32
bans a rule id or internal code in clerk-facing copy; a role only this project
uses is the same shape of leak. The drawing's `This one is with you.` is written
for the reader the blueprint has, not for the clerk either. **Neither sentence
is right for a clerk — recorded, not resolved.**

### 2 · The frame draws the reason box on a CREATE door with a required asterisk

The kicker says `NEW DISCOUNT`; control 6 is `WHAT CHANGED, AND WHY` with a
required `*`; and the page's own STATES row says *"Creating — the reason box is
absent"*. **The built product follows the STATES row** (`:1685` is gated on
`editing`), which is the coherent reading. See CONTRADICTIONS §1.

### 3 · Two stated absences and one help line the frame does not draw

| built | evidence |
|---|---|
| `Enrolment window` — `The window during which accounts may join cannot be set on a discount yet. The effective dates above say when the programme prices, which is a different thing.` | `:1605-1608`, `ArrivesWithField` |
| `Impact analysis` — `Eligible accounts, projected monthly and annual subsidy, average bill effect and revenue impact belong here and cannot be worked out yet. Nothing in the product projects what a discount will cost before it exists.` | `:1678-1681`, `ArrivesWith` |
| `Leave the end date blank for a programme with no planned end.` under `EFFECTIVE TO` | `:1599` (`datesHelp`) — the drawing puts this in the picker's **placeholder** as `No planned end` |

⚠ **THE IMPACT ABSENCE IS NOT LOOSE FURNITURE.** It is the read `PRB-13`'s
`$500` test would have to consume — the file says so at `:1675-1677`. Removing
it would delete the statement of what `PRB-13` waits on.

### 4 · `WHEN THE BUDGET RUNS OUT` carries a help line the frame does not draw

`:1642` renders `exhaustionHelp`:
*"Suspend is the one setting that lets a BILL RUN change this discount's status
by itself, to Suspended — funding exhausted. The other two leave the status
alone."* — the one sentence on this step that explains a status a bill run can
set without anybody asking. The drawing removes it and its own screen-26 STATES
row then says *"the edit screen names which setting allows that"*. See
CONTRADICTIONS §2.

### 5 · `BUDGET CAP` help is two sentences where the drawing writes one

Built: *"What this programme may spend in the period below. Blank means
unbounded — and unbounded always needs a second approval."*
Drawn: *"Blank means unbounded, which always needs a second approval."*

### 6 · The callout is hand-rolled, not the kit's consequence box

`:1668-1674` is `<Panel as="section">` + `<Kicker as="div">` + `<Note>`. The
drawn callout is a label in an outlined tag with an accent left rule and one
body sentence — which is `components/ConsequenceBox.tsx`'s staff shape
(`tone` + `tag` + `title` + `body`, `:81-93`), already in the kit. See the
root-cause note in `CR-087-p074`.

### 7 · Three panels where the drawing draws one

`:1572` · `:1611` · `:1668`, plus the `ArrivesWith` blocks between them and the
reason panel at `:1685`.

---

## CONTRADICTIONS INSIDE THE BLUEPRINT — recorded, not resolved

1. **THE REASON BOX ON A CREATE DOOR.** The frame draws `WHAT CHANGED, AND WHY`
   with a required asterisk under a `NEW DISCOUNT` kicker; the same page's
   STATES row says it is absent when creating. **Reading: the STATES row is the
   coherent half and the frame is drawn with an edit door's content** — the same
   mixing `CR-087-p065` CONTRADICTIONS §3 records, and step 5's `SAVING AS V3`
   confirms it. Built behaviour already follows the STATES row.

2. **THE EXHAUSTION HELP LINE.** This page removes it; page 79's screen-26
   STATES row then promises *"the edit screen names which setting allows that"*.
   The two cannot both hold. **Reading: the sentence stays somewhere on this
   step**, or screen 26's promise goes with it. One sentence to the PO.

3. **`Save draft & exit`** — see `CR-087-p065` CONTRADICTIONS §2.

---

## WHAT NEEDS THE PRODUCT OWNER

* **`PRB-13` / `OQ-290` itself** — which of `BR-RAT-091` ($500 against projected
  monthly subsidy) and `BR-RAT-077` ($10,000 against the budget cap) governs.
  **Both are signed. A lane must not pick.** ⚠ Whichever is chosen, the drawn
  wording asks for a **monthly subsidy figure**, which nothing in the product
  computes (`DEF-402`) and which the client may not derive.
* **§1's closing sentence** — neither `This one is with you.` nor
  `…is with the Product Owner.` is clerk-facing copy.
* **CONTRADICTIONS §2** — where the bill-run-sets-a-status sentence lives.

## WHAT COULD NOT BE VERIFIED WITHOUT THE APP RUNNING

* Whether `EFFECTIVE TO` shows `No planned end` as a placeholder or an empty
  box in the browser — `DatePickerField`'s empty rendering was not exercised.
* The date picker's rendered format echo against a non-US tenant format.

---

## FIXED 2026-09-10 — the second-approval panel is gone, and PRB-13 is closed

**§1 · THE CALLOUT IS DELETED, PANEL AND ALL — PO ruling 2026-09-10.** Verbatim:
*"Keep the plumbing, default it off. The threshold setting stays but starts
unset, so nothing ever requires a second approval unless a utility deliberately
turns it on."* **This closes `PRB-13` / `OQ-290` without choosing between
`BR-RAT-077` and `BR-RAT-091`** — neither runs by default, so the conflict stops
being live and stops being visible. The drawn figures (`$7,332 a year — $611 a
month`) are moot: nothing on this step now states a second-approval requirement,
so the client is not asked to divide money and `DEF-364` is not reached.

⚠ **AND THE `budgetUnbounded` SENTENCE WENT WITH IT, WHICH IS THE HALF THAT
MATTERS.** A blank budget cap used to force the approval whatever the threshold
said — the one discount a small utility is most likely to write. Disabled with
the rest, and its reasoning preserved in `BR-RAT-964` for the day a utility
types a figure into Settings and gets the whole mechanism back.

**§§3, 4, 5, 6, 7 AND CONTRADICTIONS §2 · UNCHANGED.** The two stated absences,
the exhaustion help line, the two-sentence budget help and the hand-rolled
callout all stand. **The callout question is now moot** — that panel is the one
this wave deleted. CONTRADICTIONS §2 (where the bill-run-sets-a-status sentence
lives) is still one sentence for the PO.

### AMENDED THE SAME DAY — a fourth sentence was still claiming the approval, and only the browser found it

**§3's `BUDGET CAP` help line said, after the panel was deleted:** *"What this
programme may spend in the period below. Blank means unbounded — and unbounded
always needs a second approval."* **The panel went and this did not**, so a clerk
who cleared the budget cap was still told a second approval was required — by a
help line, on the same step, under the control the ruling was about.

⚠ **NO TEST IN THIS REPO COULD SEE IT, AND THE ONES THIS WAVE ADDED LOOKED
RIGHT.** Every assertion was about the PANEL — its label, its two figures, its
absence — and every one passed. The sentence that survived belonged to a
different control and said the same false thing. **It was found by clearing the
box in a browser and reading the step**, which is hard-won law 6 with no tool
behind it. It now reads `Blank means no ceiling.`

⚠ **AND THE BLAST RADIUS REACHED A SCREEN THIS WAVE DOES NOT OWN.** The plan
wizard's Discounts step states the same rule in two more notes —
`rating.plan.discounts.secondApprovalNoBudget` (*"A discount with no budget cap
at all ALWAYS needs the second approval, whatever that figure is"*, rendered
unconditionally) and `.secondApprovalUnknown`, whose text blamed the reader's
ROLE for a figure that is now simply unset. Both were made false by the ruling
rather than by that screen, so both are corrected in the catalogue and neither
`PlanWizard.tsx` nor any other lane's file is touched.

**The lesson, and it is the one worth carrying: turning a rule off does not turn
off the sentences that describe it.** Grep the catalogues for the rule's own
words, not for the component you deleted.
