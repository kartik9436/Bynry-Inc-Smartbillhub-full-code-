# 16 · Rate schedule → Create · Step 4 · Effective & approval — THE DRAWN SPEC

`S11 · RAT-03` · route `/:tenant/plans-rates/rates/:id/edit` · **blueprint pages 48–51**

**Source:** `05-prototype/SMARTBillHub Plans & Rates Blueprint.pdf`, section opening
on page 48, **frame drawn across pages 48–49**, specified on 49–51. Read as
RENDERED pages — the four-tile impact strip, the absence band beneath it, the
calendar affordance on both date boxes and the `STARTING BLANK` callout at the
foot of the panel are only visible as a picture.

**State chip:** `BLOCKED`
**Commitment:** `PRB-10`. Screens `15` · `16`.

**Masthead warning, applied.** As-built at **2.232.0**; we are on **2.234.19**, and
**one of this section's as-built claims turned out to be false** — see D6.

---

## 1 · Header, step rail, footer

The wizard frame, unchanged, with **`4 Effective & approval` active**. Footer:
`Continue`, right-aligned.

## 2 · Panel 1 — `Impact of this change`, FIRST on the step

**Heading:** `Impact of this change`
**Hint, verbatim:** `Who this change reaches, and by how much. Worked out from the effective date you type below.`

**FOUR tiles, in this order:**

| # | label | value | detail line |
|---|---|---|---|
| 1 | `ACCOUNTS AFFECTED` | `74` | `across 3 plans` |
| 2 | `WORST-CASE BILL CHANGE` | `+11.4%` | `one account, Sample — Commercial` |
| 3 | `AVERAGE BILL CHANGE` | `+$3.18` | `a month` |
| 4 | `SECOND APPROVAL` | `Required` | `worst case is above the 10% bar` |

**Beneath the tiles, an absence band, ruled off:**

| legend | label | sentence |
|---|---|---|
| `NOT WORKED OUT YET` | `Annualised revenue change` | `Nothing projects a year of revenue from a rate change.` |

⚠ **B14 rule 37 — `74`, `+11.4%`, `+$3.18`, `3 plans` and `10%` are
ILLUSTRATIONS.** The shape is four tiles each carrying a figure and a
one-line qualifier, and the fourth tile being a **verdict word** rather than a
number.

## 3 · Panel 2 — `Effective & approval`

**Heading:** `Effective & approval`
**Hint, verbatim:** `When this pricing starts, and the regulator reference behind it.`

| # | label | required | help line, verbatim | value drawn |
|---|---|---|---|---|
| 1 | `EFFECTIVE FROM` | `*` | `Must be after 06/01/2026, when the version in force starts.` | `01/01/2027`, **with a calendar affordance** |
| 2 | `EFFECTIVE TO` | — | `Leave blank to run until the next version starts.` | placeholder `dd/mm/yyyy`, **with a calendar affordance** |
| 3 | `VERSION LABEL` | — | `Such as v4 or 2027-A. Blank numbers versions in date order.` | *(blank)* |
| 4 | `WHAT CHANGED` | — | `Optional. Shown against this version in the rate's history and on the schedule's own page — a version with nothing written against it simply shows a dash.` | *(blank)* |

**Closing callout, accent-ruled:**

| legend | sentence |
|---|---|
| `STARTING BLANK` | `The previous version's note and label are deliberately not carried forward. A new version is a new statement.` |

⚠ **FOUR FIELDS AND NO FIFTH.** There is **one** free-text note on this step and it
is `WHAT CHANGED`. Page 49: *"There were two — `what changed` and `reason for this
change` — written to two different places, and the server quietly used one for the
other when the second was empty. One box now, written to both the version history
and the compliance record. **Optional, on your instruction**."*

⚠ **THE REGULATOR FILING FOLDS AWAY.** Page 50, COGNITIVE LOAD: *"Impact first,
because it is what decides whether the date is acceptable. Dates second. The
regulator filing folds away — it is a record and nothing on the screen depends on
it."* The frame shows no filing panel open, and the panel hint still says *"and the
regulator reference behind it"* — so the filing is present and **closed**, which is
B14 rule 32's `<details>` closed by default.

## 4 · States — verbatim

| state | drawn behaviour |
|---|---|
| **Creating** | *"No impact panel at all — there is nothing yet to compare against, and an empty panel of em-dashes is worse than none."* |
| **Nothing could be priced** | *"None of the 74 accounts could be priced, so we cannot say whether the second-approval bar applies. **That is not the same as being under it.** Activation records that impact was unknown."* |
| **Second approval needed** | *"A danger strip naming the percentage and the bar, before the button, not after."* |
| **Date on or before the current version** | *"Checked here: the field says the earliest date that would be accepted."* |

## 5 · Components named in the frame

`WizardFrame` `KPIStrip` `AbsenceBar` `DatePickerField` `TextArea` `InlineCheck` `Callout accent`

## 6 · FOR · HOW YOU GET HERE · PRIMARY ACTION

* **FOR** — *"The clerk who has the numbers approved and now has to say from when."*
* **HOW YOU GET HERE** — *"Continue from Rates."*
* **PRIMARY ACTION** — `Continue.`

## 7 · The RULES line, with its own extra clause

*"… A field that can be refused states its own condition where it is typed."*

---

# THE DIFF — drawing against the code at 2.234.19

Code: `RateScheduleWizard.tsx` — `EffectiveStep` **2378**, `FilingCapturePanel`
**2521**, `ImpactAnalysisPanel` **2643**, `IMPACT_FIGURES` **358**.

## D1 · THE FOUR PRE-FILLS ARE STILL CARRIED FORWARD — the named defect, verified live

`RateScheduleWizard.tsx:521-525`, inside `draftFromSchedule`:

```tsx
    effective_from: version.effective_from ?? "",
    effective_to: version.effective_to ?? "",
    regulator_ref: version.regulator_ref ?? "",
    version_label: version.version_label ?? "",
    change_reason: version.change_reason ?? "",
```

`version` is `detail.current_version ?? detail.draft_version`
(`RateScheduleWizard.tsx:451`), so **opening a live schedule to make a new version
loads the in-force version's own start date into `EFFECTIVE FROM`.**

Page 49, verbatim: *"The start date came in holding the live version's own start
date, and a new version may not begin on or before the current one — so the first
refusal was certain. Fixing it put the carried end date behind the new start,
causing the second."* And the drawn fix: *"Both are now blank."*

The filing block is carried too (`:530-533` — authority, filed on, approved on,
approver), which the drawing does not comment on either way.

## D2 · THERE ARE TWO REASON BOXES, WRITING TO TWO PLACES — the named defect, verified live

| box | line | label | writes to |
|---|---|---|---|
| `WHAT CHANGED` | `RateScheduleWizard.tsx:2450-2456` | `rating.rate.changeReasonLabel` = `What changed` | `change_reason` on the version |
| `Reason for this change` | `RateScheduleWizard.tsx:2482-2492` | `rating.rate.reasonLabel` = `Reason for this change` | `reason` — the compliance record |

The second is **`required` and `multiline`**, rendered only when
`props.needsReason` (a live schedule), with
`rating.rate.reasonHelp` = *"Required: a change to a live schedule creates a new
version, and the reason goes into the compliance record."*

The drawing has ONE box and it is **optional**. That is a PO instruction (*"Optional,
on your instruction"*) that collides with **BR-RAT-037**, which the code cites at
`:2480-2481` as making the compliance reason `NOT NULL`. **See the contradictions
section — this needs the PO, not a lane.**

## D3 · THE `EFFECTIVE FROM` HELP DOES NOT STATE THE EARLIEST DATE

`rating.rate.effectiveFromHelp` = *"A draft can be saved without one; activating
cannot."*

Drawn: *"Must be after 06/01/2026, when the version in force starts."* — the date
of the version in force, named, so the refusal is read before it fires. The
comment at `RateScheduleWizard.tsx:2410-2413` states the current position
explicitly: *"It is not marked required here because a draft may legitimately have
none — the server decides at activation and its refusal is what the user reads."*

The drawing does not ask for the field to become required; it asks for the
**condition to be stated where it is typed**, which is this screen's own extra
RULES clause (§7).

## D4 · `WHAT CHANGED`'S HELP IS HALF THE DRAWN SENTENCE

`rating.rate.changeReasonHelp` = *"Shown against this version in the rate's
history."*
Drawn: *"Optional. Shown against this version in the rate's history **and on the
schedule's own page — a version with nothing written against it simply shows a
dash**."*

The dropped clause is what makes the Audit tab's em-dash readable
(`CR-087-p061-view-audit.md` §4), and the word `Optional.` is what tells a clerk
they may leave it.

## D5 · THE FIELD ORDER AND PANEL ORDER BOTH DIFFER

**Drawn:** `Impact of this change` → `Effective & approval` (4 fields) → the
`STARTING BLANK` callout, with the regulator filing folded away.

**Built** (`EffectiveStep`, `:2390-2494`):

1. `ImpactAnalysisPanel`
2. **`FilingCapturePanel`** — a fully open `Panel`, five fields
   (`rating.rate.filing.title` = `Regulator filing`)
3. `Effective & approval` panel, in this order: `Effective from` · `Effective to` ·
   **`Regulator reference`** (`:2424-2431`) · `Version label` · `What changed` ·
   **`Note that customers should be told 30 days ahead`** (checkbox, `:2457-2462`) ·
   **`Note that this should appear on a public rate page`** (checkbox, `:2463-2468`) ·
   a `MoreAbout` disclosure of three sentences · **`Reason for this change`**

So the built step has **five extra controls** the drawing does not place here: the
open filing panel, the `Regulator reference` text field, two checkboxes, and the
second reason box.

⚠ **THE TWO CHECKBOXES ARE THE DRAWING'S `Telling customers` PANEL, ONE STEP
EARLY AND IN DIFFERENT WORDS.** Page 52 moves telling-customers to **step 5** as
two ticks — `Show a notice in the customer portal` and `Email every affected
customer` — with their reach stated beside them. The built pair are *"Note that
customers should be told 30 days ahead"* and *"Note that this should appear on a
public rate page"*, which are different intentions. See
`CR-087-p051-create-step5-review-activate.md` D4.

## D6 · ⚠ THE BLUEPRINT'S `Annualised revenue change` ABSENCE IS **FALSE** AT 2.234.19 — BUILDING THE FRAME LITERALLY WOULD DELETE A WORKING FIGURE

**Drawn:** an absence band — `NOT WORKED OUT YET · Annualised revenue change ·
Nothing projects a year of revenue from a rate change.`

**Built and served:**

* the server computes it — `06-backend/apps/rating/impact.py:274-275`,
  `annualised_revenue_change=monthly * ANNUALISATION_MONTHS`, with the worked
  figure in its own comment (*"`+$3.54 × 914 × 12 = $38,826.72`"*);
* it is projected — `06-backend/apps/rating/selectors.py:1917-1918`
  (`annualised_revenue_change` + `_display`);
* it is typed — `07-frontend/src/api/endpoints.ts:3838-3839`;
* and **it is rendered as a tile today** — `IMPACT_FIGURES` includes
  `{ key: "revenue", labelKey: "rating.rate.impact.revenueLabel" }`
  (`RateScheduleWizard.tsx:361`), `rating.rate.impact.revenueLabel` =
  `Annualised revenue change`, value from
  `rating.rate.impact.revenueValue` = *"{{annual}} a year · {{monthly}} a month"*
  (`impactValues`, `:2765-2771`).

**This is a masthead re-verification hit.** The blueprint says its as-built claims
were true at 2.232.0 and must be re-checked; this one is not true now. `DEF-434`
is the change that closed it. **Do not build the absence band for this figure.**

## D7 · THE FOUR TILES ARE THE WRONG FOUR

`RateScheduleWizard.tsx:358-364`

```tsx
export const IMPACT_FIGURES: readonly ImpactFigure[] = [
  { key: "accounts", labelKey: "rating.rate.impact.accountsLabel" },
  { key: "billChange", labelKey: "rating.rate.impact.billChangeLabel" },
  { key: "revenue", labelKey: "rating.rate.impact.revenueLabel" },
  { key: "overThreshold", labelKey: "rating.rate.impact.overThresholdLabel" },
];
```

| # | drawn tile | built tile |
|---|---|---|
| 1 | `ACCOUNTS AFFECTED` — `74` / `across 3 plans` | `Accounts affected` — `rating.rate.impact.accountsValue` = *"{{accounts}} accounts across {{plans}} plans"*, **one string, no detail line** |
| 2 | `WORST-CASE BILL CHANGE` — `+11.4%` / `one account, Sample — Commercial` | — |
| 3 | `AVERAGE BILL CHANGE` — `+$3.18` / `a month` | — |
| 2+3 merged | — | `Average and worst-case bill change` — *"{{worst}} worst case · {{average}} average · {{change}} a month"*, **three figures in one cell** |
| 4 | `SECOND APPROVAL` — `Required` / `worst case is above the 10% bar` | `Accounts over the threshold` — *"{{priced}} of {{affected}} priced"*, which is a **different fact**: how many could be priced at all |
| absence band | `Annualised revenue change` | rendered as **tile 3** (see D6 — correctly) |

**Tile 4 is the one that matters.** The drawn tile is the VERDICT — `Required` /
`Not required` — and the built one reports coverage. The verdict does exist on the
screen, but as a sentence below the tiles (`SecondApprovalNote`, `:2623-2641`), and
the built label admits its own gap in the code comment at `:2769-2775`: *"The
endpoint serves the WORST case rather than a per-account tally, so this row
reports how many of the affected accounts were priced at all — which is the honest
half."*

⚠ **THE FRAME'S FOURTH TILE IS BUILDABLE TODAY.** `second_approval_required`
(`boolean | null`) and `second_approval_threshold_pct_display` are both served
(`endpoints.ts:3841-3843`) and `SecondApprovalNote` already reads them — a column
the server sends that the tile does not draw.

## D8 · THE `AbsenceBar` IS NOT IN THE KIT

`KPIStrip`'s tile type (`components/KPIStrip.tsx:31-32`) is `{label, value|money,
detail?}` with no absence variant, and there is no `AbsenceBar` component. The
wizard renders its own `<dl>` grid rather than `KPIStrip`
(`RateScheduleWizard.tsx:2653-2675`) and prints an em-dash + reason inside each
tile.

**B14 rule 36 in practice:** *"Where the kit lacks a piece, ADD IT TO THE KIT"* —
this band is drawn on **five** screens in this section (16, 18, 19, 20 and, as the
`NOT WORKED OUT YET` legend, on 14's sibling) and is a kit addition, not a
per-screen div.

## D9 · DATE PICKERS — ⚠ THE BLUEPRINT'S DEFECT IS ALREADY FIXED

Page 50: *"Both dates were plain text boxes. No picker, no format hint."*

**Not true at 2.234.19.** `RateScheduleWizard.tsx:2404` and `:2416` both use
`DatePickerField` from `components/FormModal`, both passed the tenant's
`dateFormat` (`useRegional`, `:860`). B14 rule 7 is met. **Second masthead
re-verification hit; nothing to do.**

## D10 · ⚠ THE PER-ACCOUNT REASONS ARE SERVED AND THE SCREEN PRINTS A LIST OF POSSIBILITIES INSTEAD

Page 50, verbatim: *"The analysis declared a per-account reason for being
unpriceable and never assigned one, so it printed a generic list of possibilities.
**Where a reason is known it is named**; where it is not, the count says so and the
screen states that impact was unknown, which is recorded on the version."*

**The reasons ARE assigned today.** `06-backend/apps/rating/selectors.py:1986-1989`
builds a `{reason: count}` tally and five call sites populate it —
`consumption_read_unwired` · `no_metered_consumption` · `base_charge_refused` ·
`engine:<ExceptionClass>` · `no_percentage_from_zero_before` — and it is projected
at `:1908` (`"unpriced_reasons": unpriced_reasons`) and typed at
`07-frontend/src/api/endpoints.ts:3829`:

```ts
  /** `{reason: count}` — why each unpriced account could not be priced. */
  unpriced_reasons: Record<string, number>;
```

**Nothing in the front end reads it.** `grep unpriced_reasons 07-frontend/src`
returns only the type declaration. What the panel prints is
`RateScheduleWizard.tsx:2708-2714` →
`rating.rate.impact.unpriced` = *"{{unpriced}} of {{affected}} accounts could not
be priced: **no read, a read in another unit, or a base charge a bill would
refuse.** They are counted, never priced at zero."*

That trailing clause is the generic list of possibilities the drawing removes, and
it is **the largest of the four served-but-undrawn columns in this section** by the
number of clerk questions it would answer.

⚠ **TWO THINGS TO GET RIGHT WHEN IT IS BUILT.** The reason keys are internal codes
and one of them is a Python exception CLASS NAME (`engine:<ExceptionClass>`) —
**B14 rule 32's fourth clause and rule 31 both forbid that reaching a screen**, so
each code needs a catalogue key and the `engine:*` family needs one catchall
sentence rather than a rendered class name. And the counts must still add up to
`accounts_unpriced`, which the drawing keeps.


---

## ABSENCES — drawn as absent, do not fill them

* **No approval control.** BR-RAT-031 as-modified: approval is out of system.
* **No `Back` label other than the rail** — the frame's own stepper.
* **No per-class impact breakdown.** The code names the same gap in a closed
  disclosure (`rating.rate.impact.byClassGap`, `OQ-319`).

## WHAT THE CODE HAS THAT THE DRAWING DOES NOT

Listed in D5: the open `Regulator filing` panel, `Regulator reference`, two
checkboxes, the second reason box, and a `MoreAbout` of three sentences
(`rating.rate.captureOnlyNote` · `rating.rate.approvalOutsideSystem` ·
`rating.rate.prorationNote`).

---

## CONTRADICTIONS AND THINGS FOR THE PRODUCT OWNER

1. **THE ONE OPTIONAL REASON BOX COLLIDES WITH `BR-RAT-037`.** The drawing:
   *"One box now, written to both the version history and the compliance record.
   **Optional, on your instruction**"*. The code, at
   `RateScheduleWizard.tsx:2478-2480`: *"BR-RAT-037 / US-RAT-010 TC-6: a change to
   a live schedule is a NEW version and the compliance reason is **NOT NULL**."*
   The Audit tab's own spec (page 62) takes the drawing's side — *"On your
   instruction the change note is not required, so a version can legitimately
   carry none"* — and the server refuses it. **A signed rule is being reversed;
   the change process step 2 says quote it and stop. FOR THE PO.**

2. **THE BLUEPRINT IS WRONG TWICE ABOUT THIS SCREEN (D6, D9)** and each error
   points a lane the wrong way — one would delete a working figure, one would
   rebuild a control that already exists. Both are exactly what the masthead
   warns about, and both were found only by reading the code.

3. **`SECOND APPROVAL` AS A TILE IS A LABEL DECISION WITH A `BR-RAT-091` EDGE.**
   The third state — *"Nobody could work out the worst-case bill change"* — must
   read as neither `Required` nor `Not required`. The sentence for it already
   exists and is well-judged (`rating.rate.impact.secondApprovalUnknown`: *"That
   is not the same as being under it."*). Whatever the tile shows in that state
   must not be an em-dash that reads as *clear*.

---

## ⚑ BUILT 2026-09-10 — `CR-087` RATE-SCHEDULE MAINTENANCE LANE

**D10 · THE FIVE PER-ACCOUNT REASONS ARE DRAWN.** `unpriced_reasons` was served,
counted at five call sites and read by nothing. The panel now tallies it under
the unpriced sentence, and **the generic list of possibilities is deleted from
`rating.rate.impact.unpriced`** so the sentence and the panel cannot disagree.
⚠ Every reason code is translated through the catalogue and the whole
`engine:<ExceptionClass>` family collapses into ONE sentence — B14 rules 31 and
32 both forbid a Python class name reaching a clerk. An unknown code falls back
to *reason not recorded*, never to the code.

**D2 · ONE REASON BOX, AND IT SAYS WHICH MODE IT IS IN.** The second box —
*Reason for this change* — is gone; `What changed` is posted to BOTH the version
note and `BR-RAT-037`'s compliance record, so the server is unchanged and its
NOT NULL still holds. The field carries the asterisk and the sentence *"Required:
this version changes pricing already billing."* only when the schedule is live.
⚠ **THIS DOES NOT MAKE THE NOTE OPTIONAL ON A LIVE CHANGE**, which is what the
drawing asks for and what contradiction 1 of this file routes to the PO. The two
were never in conflict — optional when creating, required when changing something
already billing — and the screen now SAYS which, rather than the clerk meeting an
unexplained asterisk or a refusal at the last step.

**D1, D3, D4, D5, D7, D8 · NOT DONE** and each stays recorded above: the four
carried pre-fills, the earliest-date sentence, the dropped `Optional.` clause,
the panel order, the four tiles, and `AbsenceBar` as a kit piece — `AccentBand`
IS now in the kit (`components/TextBits.tsx`) and this panel does not use it yet.
