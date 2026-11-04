# Plans 36 · Create · Step 8 · Review & activate — THE DRAWN SPEC

`PLN-03 step 8` · route `/:tenant/plans-rates/plans/new` · **blueprint pages 101–105**

**Source:** `05-prototype/SMARTBillHub Plans & Rates Blueprint.pdf`, screen `36`,
frame drawn on pages 102–103, specified on 104–105.

**State chip:** `NEW BUILD`
**Commitments on the chip line:** `PRB-01` · `PRB-18` · `PRB-19`

**WHAT WAS WRONG (page 101, verbatim):** *"The last screen before a plan became
assignable was seven one-line summaries — a receipt rather than a review — arranged by
the step that collected each answer rather than by the order a bill is made in."*

---

## 1 · Wizard chrome

As step 1, with `8` active. Footer: **one button, `Publish plan ✓`.**

## 2 · Block 1 — the plan's IDENTITY, a plain block ABOVE the card

| slot | drawn |
|---|---|
| heading | `Residential Standard` — the plan's name, plain |
| fact 1 | `CODE` · `SCW-RES` |
| fact 2 | `CUSTOMER CLASS` · `Residential` |
| fact 3 | `RUNS` · `01/01/2027 — no planned end` |
| fact 4 | `SHOWN TO CUSTOMERS` · `Everyday water and power for a single home.` |
| fact 5 | `MEANT FOR` · `No notes recorded`, with a quiet second line `Assignable to any account either way.` |
| links, one row, at the foot of the block | `Edit basics` · `Edit dates` · `Edit who it is for` — **three, accent text** |

⚠ **THREE EDIT LINKS, NOT SEVEN.** Page 104, verbatim: *"**WHY THE PLAN'S IDENTITY
SITS OUTSIDE THE CARD** — The card is titled *the price* and holds only what reaches a
bill. Name, code, class, dates and who the plan is meant for are **facts about the
plan**, not prices, so they stay in a plain block above it. Mixing them in was what
made the old review read as a list of eight unrelated things."*

## 3 · Block 2 — the card `Plan, rates, charges, discounts and taxes`

| slot | drawn |
|---|---|
| card heading | `Plan, rates, charges, discounts and taxes` |
| chip beside it | `THE PRICE` *(accent, outlined)* |
| caption, right-aligned on the same row, monospaced | `effective before the first bill` |

**FIVE BANDS, IN THE ORDER A BILL IS MADE IN.** Each band label is a heading with its
own ground and an accent marker at the left.

### Band 1 · `RATE SCHEDULE`

| # | header | alignment | drawn cells |
|---|---|---|---|
| 1 | `SERVICE` | left | `Water` · `Electric` · `Sewer` |
| 2 | `BASE` | left | `8.00 / month` · `12.00 / month` · *`none`* (italic) |
| 3 | `USAGE` | left | `tiered by kgal` · `time of use` · `share of water usage` |
| 4 | `RATE` | **right, monospaced** | `4.0000 · 6.5000 · 8.0000` · `0.1100 peak · 0.0700 off-peak` · `40%` |

### Band 2 · `CHARGE CODES` — sub-label `the five that reach this bill`

| # | header | alignment | drawn cells |
|---|---|---|---|
| 1 | `CODE` | left | `BASE-W` · `BASE-E` · `LATE` · `CONN` · `DEP` |
| 2 | `NAME` | left | `Water monthly base` · `Electric monthly base` · `Late payment fee` · `Connection fee` · `Deposit` |
| 3 | `AMOUNT` | **right** | `8.00` · `12.00` · `1.5% · min 5.00` · `45.00` · `150.00 residential · 400.00 commercial` |
| 4 | `WHEN IT APPLIES` | **right, monospaced** | `every bill, while the service is on` (×2) · `after the due date` · `once, at move-in` · `once, before service starts` |

### Band 3 · `DISCOUNTS` — sub-label `offered, not granted`

| # | header | alignment | drawn cells |
|---|---|---|---|
| 1 | `CODE` | left | `SENIOR` · `AUTOPAY` · `PAPERLESS` |
| 2 | `NAME` | left | `Senior citizen discount` · `Autopay discount` · `Paperless billing` |
| 3 | `VALUE` | right | `15%` · *`set by the utility`* (italic) · *`set by the utility`* (italic) |
| 4 | `ON THIS PLAN` | **right** | `offered from 09/08/2026` · *`not offered`* · *`not offered`* |

### Band 4 · `TAXES`

| # | header | alignment | drawn cells |
|---|---|---|---|
| 1 | `LEVEL` | left | `State` · `County` · `City` · `Special district` |
| 2 | `AUTHORITY` | left | `Texas State — TX State Utility Tax` · `Bexar County — Local` · *`not set`* · *`not set`* |
| 3 | `RATE` | right | `6.25%` · `1.0%` · *`no rate`* · *`no rate`* |
| 4 | `APPLIES TO` | **right, monospaced** | `all services · by jurisdiction` · `all services` · `–` · `–` |

⚠ **A LEVEL WITH NO AUTHORITY IS A ROW, NOT AN ABSENCE FROM THE LIST.** Page 105:
*"not set and no rate, so a missing county tax is visible rather than absent from the
list entirely."*

### Band 5 · `OTHER TERMS` — no column headers

| row label | detail | figure | scope |
|---|---|---|---|
| `Outside the city limits` | `premises beyond the boundary` | `15% more` | `every service` |
| `Budget billing` | *`not offered`* (italic) | `–` | `–` |
| `Minimum bill` | *`no plan minimum`* (italic) | `–` | `–` |
| `Cycle and due date` | `from the utility's billing defaults` | *`not settable per plan`* (italic) | `–` |

## 4 · Block 3 — `What publishing does`

| slot | drawn |
|---|---|
| heading | `What publishing does` |
| callout, red rule | **NOBODY MOVES BY ITSELF** — `Publishing makes this plan available for staff to assign from 01/01/2027. No live customer is affected right now — accounts move onto a plan one at a time.` |
| named absence | `A SPECIMEN BILL` · `—` · `A sample bill is produced by the billing service and cannot be rendered for a plan that has never billed.` |

## 5 · Footer

One right-aligned button: **`Publish plan ✓`**.

## 6 · FOR · HOW YOU GET HERE · PRIMARY ACTION (page 104)

* **FOR** — *"The clerk one press from making a plan assignable."*
* **HOW YOU GET HERE** — *"Continue from Eligibility, or any Edit link and back."*
* **PRIMARY ACTION** — *"`Publish plan ✓`."*

## 7 · The four presentation rules the frame states about itself (page 104)

* **EVERY FIGURE RIGHT, EVERY CONDITION BESIDE IT** — *"Amounts and rates are
  right-aligned and set in the monospaced face so a column of them can be scanned; each
  row's last cell says **when it applies** in plain words. A number without its
  condition is the thing a clerk has to go and look up."*
* **AN ABSENCE IS ITALIC, NEVER BOLD** — *"none, not set, no rate, not offered. A grey
  italic reads as nothing-here at a glance; the same words in the body face read as a
  value, which is how a plan with no city tax looked identical to one with a city tax
  of zero."*
* **THE BASE CHARGES AND THE DEPOSITS ARE BACK HERE** — *"This is where step 3's Base
  column and step 6's late-fee and deposit blocks went. Every base a service can carry
  is listed, every deposit by customer class."*
* **COGNITIVE LOAD** — *"One header, one card, one consequence. Five bands rather than
  five panels, so the whole price is a single scroll and the borders between parts are
  a label rather than a box."*

## 8 · STATES (pages 104–105)

| state | drawn behaviour |
|---|---|
| **A service without a schedule** | *"The Rate schedule band shows the service with no schedule in italic, and publishing is refused — but it has already been named on step 3."* |
| **More than one base for a service** | *"Every one listed with the class and size that selects it — the case a single read-only cell on step 3 could never show."* |
| **A level with no authority** | *"not set and no rate, so a missing county tax is visible rather than absent from the list entirely."* |
| **Editing a published plan** | *"A required reason box appears above the button: every change becomes a new version with this reason in the compliance record."* |
| **Base total** | *"Worked out by the server on save; the screen says so rather than adding it up in the browser."* |

## 9 · WHAT THE SERVER NEEDS (page 105, verbatim)

*"Two reads that do not exist, and one sum that must not happen in the browser. Every
base charge that applies to a service — by customer class and connection size — is the
read behind *What it prices*, and it depends on the class column named on the
charge-code screen. The combined tax rate (7.25%) is a sum: the server states it, for
the same reason the base total is worked out on save. Nothing else on this card is new;
the rest is already served."*

## 10 · COMPONENTS named in the frame (page 105)

`WizardFrame` `FieldGrid` `PriceCard` `BandLabel` `RightAlignedTable` `NamedAbsence`
`ConsequenceNote`

## 11 · Absences — drawn as absent, do not fill them

* **No seven one-line step summaries.**
* **No second service→schedule table.**
* **No `Exceptions on this plan` block.**
* **No `Save it` panel repeating the effective date.**

---

## DIFF AGAINST THE RUNNING CODE — `2.234.19`

The card itself is `07-frontend/src/features/rating/PlanSummaryCard.tsx`, fed by
`ReviewStep`'s adapter at `PlanWizard.tsx:4536-4609`.

### Conforming

| drawn | code | evidence |
|---|---|---|
| five bands, in bill order | `PLAN_SUMMARY_BAND_ORDER = ["schedules","charges","discounts","taxes","terms"]`, exported so a reorder is a failing test | `PlanSummaryCard.tsx:79-85` |
| band labels | `Rate schedule` · `Charge codes` · `Discounts` · `Taxes` · `Other terms` | `en.json` `rating.planSummary.band.*` |
| the card title chip and the caption | `rating.planSummary.title` = *"The price"*; `captionReview` = *"effective before the first bill"* — verbatim | `PlanWizard.tsx:4631-4633` |
| an absence is a DIFFERENT KIND of cell, not a differently-worded one | `absentValue` / `textValue` / `figureValue`, exported so an adapter cannot invent a fourth | `PlanSummaryCard.tsx:89-` |
| the absence words, verbatim | `none` · `not set` · `no rate` · `not offered` · `no schedule` · `not settable per plan` | `en.json` `rating.planSummary.absent.*` |
| figures right-aligned and tabular | `figureValue` | `PlanSummaryCard.tsx` |
| `WHEN IT APPLIES` in plain words | `applies.everyBill` · `applies.afterDue` · `applies.onceAtMoveIn` · `applies.beforeService` — all four drawn sentences, verbatim | `en.json` |
| the deposit row states both class amounts | `rating.planSummary.deposit.byClass` = *"by customer class"* beside the amounts | `PlanSummaryCard.tsx:` deposit rows |
| nothing on the card computes a number | every figure arrives as a server-formatted string; the file says so in its own header | `PlanSummaryCard.tsx:47-52` |
| a plan naming no late-fee code says so | `rating.planSummary.lateFee.zero` = *"No charge code names one, so no late fee is charged."* | `PlanSummaryCard.tsx:532` |
| **Editing a published plan** state | the required reason `TextField` above the commit | `PlanWizard.tsx:4740-4749` |
| **Base total** state | server's figure when saved, `derivedPending` when not | `PlanWizard.tsx:4674-4681` |
| footer commit label, verbatim | `rating.plan.publish` = *"Publish plan ✓"* | `PlanWizard.tsx:1978` |

### Findings

1. **⚠ THE `Outside the city limits` ROW PRINTS A MULTIPLIER WHERE THE DRAWING SAYS A
   PERCENTAGE — ON BOTH SURFACES, FROM ONE CAUSE.**
   `bandTerms` renders that cell as
   `t("rating.planSummary.term.surcharge", { percent: input.outsideCityFactorPercentDisplay })`,
   and the template is `'{{percent}} more'`
   (`PlanSummaryCard.tsx:688-696`; `en.json`). Both adapters feed it the **factor**:

   * the wizard — `outsideCityFactorPercentDisplay: draft.outside_city_factor === "" ? null : draft.outside_city_factor` (`PlanWizard.tsx:4603-4604`);
   * the plan's page — `outsideCityFactorPercentDisplay: detail.outside_city_factor` (`PlanSummaryCard.tsx:776`).

   `draft.outside_city_factor` is documented at `PlanWizard.tsx:333-338` as *"A
   MULTIPLIER, NOT A PERCENTAGE"* — `1.15` for fifteen percent — and **no control
   writes it**; step 2 writes `outside_city_percent` (`PlanWizard.tsx:2473,2487`). So:

   | case | what the row reads | what the drawing says |
   |---|---|---|
   | new plan, clerk typed `15` on step 2 | *not set* — the factor is `""` | `15% more` |
   | editing a plan stored at `1.15` | `1.15 more` | `15% more` |

   **The server already serves the right field.** `plan_detail` returns
   `outside_city_percent` and `outside_city_percent_display` (two places, per hard
   rule 2) beside the unchanged factor —
   `06-backend/apps/rating/selectors.py:469-474` — and `endpoints.ts:3140,3149` types
   both. The card is reading the wrong one of the three.
   **No test covers it:** `PlanDetail.test.tsx:118` sets `outside_city_factor: null`,
   so only the `absentValue` branch is ever exercised, and
   `cr087ClassSizeGrid.dom.test.tsx:218` passes `null` too. Hard-won law 7's
   *looking at the wrong thing* — the assertion exists and cannot fail on the bug.
2. **⚠ A MESSAGE KEY IN THIS CARD EXISTS IN NONE OF THE ELEVEN CATALOGUES.**
   `PlanSummaryCard.tsx:440` calls `t("rating.planSummary.absent.noUsage")` for the
   `USAGE` cell when the schedule card is missing. `grep -rl` over
   `07-frontend/src/i18n/locales/` returns **0 files**; the seven sibling keys
   (`noFloor`, `noRate`, `noSchedule`, `none`, `notOffered`, `notSet`,
   `notSettable`) are all present at `en.json:10798-10804`. A missing key reaches a
   clerk as the raw key or as silence, and `G15`'s parity check compares the
   catalogues to each other, never to the call sites — the same blind spot
   `DEF-MET-4769` was filed for.
3. **THE SEVEN ONE-LINE SUMMARIES ARE STILL THE FIRST THING ON THE STEP.**
   `PlanWizard.tsx:4615-4629` renders a Panel of seven rows built from `sections`
   (`PlanWizard.tsx:4464-4522`), each `**label** · summary` with an
   `Edit {{section}}` link — `Basics · Services · Rate schedules · Charges · Taxes ·
   Discounts & billing · Eligibility`. The drawing replaces them with the identity
   block of §2 and **three** links. The code's own comment
   (`PlanWizard.tsx:4525-4535`) records the decision to keep them *"as the JUMP-BACK
   list"*, so this is deliberate — but it is a departure from the drawn frame and it
   is what the blueprint's `WHAT WAS WRONG` names.
4. **THE IDENTITY BLOCK OF §2 DOES NOT EXIST.** There is no block carrying
   `CODE · CUSTOMER CLASS · RUNS · SHOWN TO CUSTOMERS · MEANT FOR`. `customerClass`
   is computed at `PlanWizard.tsx:4448-4457` and used only inside section row 1's
   summary string.
5. **A SECOND SERVICE→SCHEDULE TABLE IS DRAWN BELOW THE CARD.**
   `PlanWizard.tsx:4645-4672` renders a two-column `Service | Rate schedule` table
   over the same rows the card's Band 1 already draws, followed by the derived-base
   line. Two tables of one fact on one screen is B14 rule 32 in the direction page
   104 calls out — *"a receipt, not a review"*.
6. **AN `Exceptions on this plan` NAMED ABSENCE SITS BETWEEN THE CARD AND THAT
   TABLE.** `PlanWizard.tsx:4637-4640`. Not drawn.
7. **A `Save it` PANEL REPEATS THE EFFECTIVE DATE BELOW `What publishing does`.**
   `PlanWizard.tsx:4772-4810` — a Kicker `Save it`, the effective date read-only with
   an eighth `Edit` link, and two more notes (`activationNote`, `buttonsElsewhere`).
   Not drawn.
8. **`What publishing does` HAS NO HEADING AND ITS SENTENCE IS SHORTER.** The drawn
   panel is headed `What publishing does` with the callout label `NOBODY MOVES BY
   ITSELF`; the code renders `rating.plan.review.publishNote` = *"Publishing makes the
   plan available for staff to assign. No live customer is affected right now."* as a
   bare `Note` (`PlanWizard.tsx:4761`) — no heading, no label, and without the drawn
   clauses *"from 01/01/2027"* and *"accounts move onto a plan one at a time."*
9. **THE `A SPECIMEN BILL` ABSENCE IS LABELLED DIFFERENTLY.** Code
   `rating.plan.review.sampleBillLabel` = *"Sample bill, as the customer receives
   it"* (`PlanWizard.tsx:4757-4760`); the frame's label is `A SPECIMEN BILL` and its
   sentence is the code's `sampleBillPending`, verbatim.
10. **BAND 1's THIRD AND FOURTH COLUMNS ARE SWAPPED AGAINST BOTH FRAMES.**
    `PlanSummaryCard.tsx:399-404` declares `Service · Base · Rate schedule · Usage`
    and the cells follow that order (`:415-445`). **Both frames draw
    `SERVICE · BASE · USAGE · RATE`** — the usage shape third, the tariff fourth. The
    result is that the heading `Usage` sits over the tariff structure and the heading
    `Rate schedule` over the schedule name in the third position, so a clerk reading
    the two frames and the screen side by side sees the same four facts in a
    different sequence.
11. **BAND 1's FOURTH COLUMN CARRIES THE SCHEDULE'S NAME, NOT THE TIER PRICES — AND THAT
    IS A RECORDED DECISION, NOT A DEFECT.** `12-governance/02-decision-log.md`,
    2026-09-08, `CR-087 D4/D5/E1/E2`, judgment 1: *"The blueprint draws 4.0000 ·
    6.5000 · 8.0000 under a Rate heading. Those figures are on the tariff VERSION and
    are not served to this screen; assembling them would be a second price renderer
    whose every figure this screen invented."* Recorded here so the next reader does
    not re-open it.
12. **BAND 3's FOURTH COLUMN IS `Take-up`, NOT THE DRAWN `ON THIS PLAN`, AND IT SHOWS
    A BARE COUNT — ALSO RECORDED.** Same decision-log entry, judgment 6:
    `PRB-20` is unbuilt, nothing works out eligibility, and *"a ratio one half of
    which is another question's answer is worse than a bare count with its gap
    named"*. `PlanSummaryCard.tsx:594,617-620` plus the `takeUpAbsent` footnote.
13. **BAND 5's CELL ORDER DIFFERS FROM THE FRAME.** Drawn:
    `label | detail | figure | scope`. Built: `label | figure | detail` for the
    surcharge row (`PlanSummaryCard.tsx:686-698`) and `label | detail | figure` for
    the cycle row (`PlanSummaryCard.tsx:719-729`). The drawn fourth cell
    (`every service`, `–`) has no counterpart — `rating.planSummary.term.everyService`
    exists but is used in Band 4's `APPLIES TO`, not here.
14. **BAND 5 CARRIES A SUB-LABEL THE FRAME DOES NOT DRAW.**
    `rating.planSummary.note.terms` = *"Everything else that changes a bill."*
    (`PlanSummaryCard.tsx:684`). The frame's `OTHER TERMS` band label stands alone.
15. **BAND 2's SUB-LABEL IS THE PAGE'S, NOT THE REVIEW'S.** The frame draws
    `the five that reach this bill` on step 8 and `what each one lands on` on the
    plan's page; the code serves `rating.planSummary.note.charges` = *"What each one
    lands on."* on both, because one component draws both. Likewise Band 3's
    sub-label. **Consistent with the blueprint's own prose** (page 108: *"This card
    and the review on step 8 are the same component with the same bands in the same
    order"*) and inconsistent with its two frames. See CONTRADICTIONS.

### Divergences recorded under B14 rule 38 — the UI rules win, nothing is built

* **The drawn `Edit basics` / `Edit dates` / `Edit who it is for` are accent text
  links.** The code uses the kit's `Button variant="link"`. Kit wins.
* **The drawn four-decimal money** (`$45.0000` on step 4; the `AMOUNT` column here is
  correctly two) — hard rule 2 and B14 rule 37 both say the screen is right.

---

## CONTRADICTIONS FOUND IN THE BLUEPRINT — recorded, not resolved

**THE PROSE SAYS ONE COMPONENT; THE TWO FRAMES DRAW DIFFERENT COLUMNS.** Page 108
states, in bold: *"This card and the review on step 8 are the same component with the
same bands in the same order. A clerk who checks a plan before publishing it recognises
the page afterwards, and a figure cannot be laid out one way on the wizard and another
way on the record."* But the two frames differ in four places:

| | step 8 (page 102–103) | the plan's page (page 106–107) |
|---|---|---|
| Band 1 columns | `SERVICE · BASE · USAGE · RATE` | `SERVICE · BASE · USAGE · RATE · CHANGE ALREADY DATED` |
| Band 1 `BASE` cell | `8.00 / month` | `8.00 / month` over a second line `BASE-W` |
| Band 2 columns | `CODE · NAME · AMOUNT · WHEN IT APPLIES` | `CODE · NAME · AMOUNT · APPLIED · TAXED` |
| Band 3 columns | `CODE · NAME · VALUE · ON THIS PLAN` | `CODE · DISCOUNT · VALUE · OFFERED · TAKE-UP` |
| Band 5 rows | four, incl. `Budget billing` | three; budget billing is a fact in `What this plan is` |

**Reading: the PROSE wins, because it is explicit and the frames are not in dialogue
with each other.** Recorded rather than acted on. B14 rule 37's third clause covers the
FIGURES in those cells but not the COLUMN SETS, so this needs one sentence from the PO
if the two surfaces are ever to differ.
