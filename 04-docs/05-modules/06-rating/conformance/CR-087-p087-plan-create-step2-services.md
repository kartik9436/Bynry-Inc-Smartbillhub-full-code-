# Plans 30 · Create · Step 2 · Services — THE DRAWN SPEC

`PLN-03 step 2` · route `/:tenant/plans-rates/plans/new` · **blueprint pages 87–89**

**Source:** `05-prototype/SMARTBillHub Plans & Rates Blueprint.pdf`, screen `30`,
frame drawn on pages 87–88, specified on 88–89.

**State chip:** `NEW BUILD`
**Commitments on the chip line:** `PRB-16` · `PRB-24`

**WHAT WAS WRONG (page 87, verbatim):** *"Five tick-boxes for a list of eleven, and a
surcharge field that asked a clerk to type 1.15 — where typing 15, the number in the
label, would have charged fifteen times the bill."*

---

## 1 · Wizard chrome

As step 1 (`CR-087-p085`): kicker `NEW PLAN`, title `New plan`, sub-line
`Eight steps · takes about 5 minutes.`, `Cancel` + `Save draft & exit`, the clipped
step rail with `2 Services` active, footer `Continue`.

## 2 · Panel 1 — `Services`

| # | drawn | control |
|---|---|---|
| panel title | `Services` | H-level heading inside the panel |
| field label | `SERVICES THIS PLAN COVERS` `*` | — |
| the control | **ONE SELECT**, reading `Electric, Water — choose more`, with a chevron | multi-select |
| chosen values | **CHIPS beneath the control**, each with a remove ×: `ELECTRIC ×` `WATER ×` | chip list |
| refusal / warning | `2 chosen. Sewer is offered but has no rate schedule for Residential yet, so it could not be billed until one exists.` *(accent rule, red text)* | inline warning |
| note | `The list holds the 5 services this utility has switched on; the other 6 are named in it, greyed, with where to switch them on.` *(quiet, grey rule)* | note |

⚠ **B14 rule 37 — `Electric`, `Water`, `Sewer`, `2`, `5` and `6` are ILLUSTRATIONS.**
The SHAPE is: a multi-select whose chosen values are removable chips, a count sentence,
and the switched-off services named INSIDE the list.

**WHAT CHANGED · A DROPDOWN THAT TAKES MORE THAN ONE (page 88, verbatim):**
*"Five tick-boxes in a row could only ever show five. This utility has eleven services
and a twelfth is possible, so the row either grows until it wraps or quietly stops
being the whole list. It is one multi-select now: what is chosen shows as chips
underneath, and the services this utility has switched OFF are named inside the list,
greyed, with where to switch them on — which is where a clerk is looking when they
wonder where a service went, rather than in a note under the form."*

## 3 · Panel 2 — `Outside the city limits`

| # | drawn label | drawn value | control |
|---|---|---|---|
| panel title | `Outside the city limits` | — | heading |
| 1 | `DO PREMISES OUTSIDE THE CITY LIMITS PAY MORE?` `*` | `Yes — a percentage more` | select |
| 2 | `HOW MUCH MORE` | `15` | text (numeric) |
| — | read-back | `15% more. A $100.00 bill outside the city becomes $115.00.` *(accent rule)* | note |

**WHAT CHANGED · THE SURCHARGE STOPPED ASKING FOR A RATIO (pages 88–89, verbatim):**
*"Multiply charges for premises outside the city limits by — type 1.15 to charge 15%
more. That is a multiplier a clerk has to compute, in a product where a nearby field
takes a percentage and another takes a fraction; 15 typed into it would have charged
fifteen times. It is now a plain question with two answers, and when the answer is yes
the field takes the percentage and reads back what it does: a $100.00 bill outside the
city becomes $115.00."*

**WHAT THE SERVER NEEDS (page 89, verbatim):** *"A percentage in, a multiplier stored —
and the conversion belongs on the server. … Either the API accepts a percent and
converts once, or the column changes. **It must not be converted in the browser** — a
scale conversion in a screen is the same trap one layer up, and two screens would
eventually disagree about which one they were sending."*

## 4 · THE WARNING ARRIVES BEFORE THE CHOICE (page 89, verbatim)

*"A service with no schedule for this class is named **here**, with what it would mean,
rather than at step 8. Choosing it is still allowed — a clerk building a plan ahead of
its rates is a real case — but nobody discovers it seven screens later."*

## 5 · FOR · HOW YOU GET HERE · PRIMARY ACTION (page 88)

* **FOR** — *"The same clerk, choosing scope."*
* **HOW YOU GET HERE** — *"Continue from Basics."*
* **PRIMARY ACTION** — *"`Continue`, blocked with no service chosen."*

## 6 · COGNITIVE LOAD (page 89)

*"Two questions. The surcharge panel collapses to the one question when the answer is
no, which is the overwhelming majority of plans."*

## 7 · STATES (page 89)

| state | drawn behaviour |
|---|---|
| **Nothing chosen** | *"Continue is refused here."* |
| **No surcharge** | *"The second field disappears and the plan never looks at whether a premises is inside the city."* |
| **A surcharge set** | *"Says a premises nobody has answered stops that one bill rather than guessing — which is the behaviour, and it is worth knowing before choosing."* |

## 8 · COMPONENTS named in the frame (page 89)

`WizardFrame` `MultiSelectField` `ChipList` `InlineCheck` `SelectField` `PercentField`

## 9 · Absences

* **No per-service exemption tick-list is drawn on this step.** The frame's second
  panel holds two controls and the read-back, and nothing else.
* **No third panel.**

---

## DIFF AGAINST THE RUNNING CODE — `2.234.19`

### Conforming

| drawn | code | evidence |
|---|---|---|
| the question, verbatim | `rating.plan.surcharge.questionLabel` = *"Do premises outside the city limits pay more?"* | `PlanWizard.tsx:2470` |
| the yes answer, verbatim | `rating.plan.surcharge.answerYes` = *"Yes — a percentage more"* | `en.json` |
| the panel collapses when the answer is no | `{surcharges && (…)}` | `PlanWizard.tsx:2480` |
| the read-back, verbatim | `rating.plan.surcharge.readback` = *"{{percent}}% more. A {{from}} bill outside the city becomes {{to}}."*, with `$100.00` as a constant | `PlanWizard.tsx:2496-2503`, `SURCHARGE_EXAMPLE_BILL` |
| the conversion is NOT done in the browser | `planPayload` sends `outside_city_percent` as typed; `apps/rating/services._validate_plan` computes `1 + percent/100` at six places | `PlanWizard.tsx:845-846`; `06-backend/apps/rating/services.py:715-731` |
| `""` ≠ `"0"` — *does not surcharge* vs *typed nothing extra* | kept apart on both sides | `PlanWizard.tsx:2282`; `selectors.py:465-469` |
| the switched-off services are NAMED, not hidden | the list iterates `SERVICE_CODES` (all eleven), a switched-off row is `opacity-60`, `cursor-not-allowed`, disabled, and carries the WORD `Not switched on` | `PlanWizard.tsx:2327-2364` |
| where to switch them on, said in the list | `rating.plan.services.switchOnWhere` under the list | `PlanWizard.tsx:2369-2371` |
| the count with its denominator | `rating.plan.services.enabledOnly` = *"Showing the {{enabled}} of {{total}} services…"* | `PlanWizard.tsx:2404-2409` |
| the unpriced warning is on THIS step | `unpriced` → `StepWarning` naming the services + a create link | `PlanWizard.tsx:2384-2400` |
| Continue refused with nothing chosen | the step's own validate | `PlanWizard.tsx` step gate |

### Findings

1. **THE MULTI-SELECT IS A WALL OF CHECKBOXES, AND THE DRAWING AND B14 AGREE AGAINST
   THE CODE.** `PlanWizard.tsx:2326` renders
   `<div className="grid grid-cols-3 max-sm:grid-cols-1 gap-2">` over
   `SERVICE_CODES.map(…)`, each cell a `<label>` wrapping an `sr-only`
   `<input type="checkbox">` (`PlanWizard.tsx:2332-2363`). The frame draws **one
   select plus removable chips**; the frame's own COMPONENTS row names
   `MultiSelectField` and `ChipList`; and **B14 rule 9** reads *"Multi-select renders
   as removable chips + an add control — never a wall of checkboxes"*, with B14 rule
   36 breach (e) naming *a wall of checkboxes* as a live breach found by the PO on a
   different screen. **`ChipMultiSelect` is already in the kit**
   (`07-frontend/src/components/ChipMultiSelect.tsx`) and is composed by six other
   screens — `SettingsServiceCentres.tsx`, `SettingsCustomerPortalTab.tsx`,
   `ScopeModal.tsx`, `TemplateBuilder.tsx`, `portal/components/primitives.tsx`.
   This is **not** a rule-38 divergence: the drawing and the UI rules say the same
   thing and the code says something else.
   ⚠ The file's own docstring at `PlanWizard.tsx:2196-2228` still describes the
   *"3-column grid of rectangular toggle tiles"* as r10's shape, so the next lane
   reading the docstring will keep it.
2. **THE FIELD LABEL IS NOT THE DRAWN ONE.** Drawn `SERVICES THIS PLAN COVERS *`;
   code `rating.plan.servicesLegend` = *"Services in this plan"*, rendered as a
   `<legend>` (`PlanWizard.tsx:2300-2302`). The drawn label also carries the required
   asterisk; a `<legend>` on a fieldset carries none.
3. **THE SECOND PANEL'S TITLE IS NOT THE DRAWN ONE.** Drawn `Outside the city limits`;
   code `rating.plan.surcharge.legend` = *"Outside-city surcharge"*
   (`PlanWizard.tsx:2456`).
4. **THE PERCENT FIELD'S LABEL CARRIES A UNIT THE DRAWING DOES NOT.** Drawn
   `HOW MUCH MORE`; code `rating.plan.surcharge.percentLabel` = *"How much more (%)"*.
   The drawn answer sentence (`Yes — a percentage more`) already says the unit, which
   is why the frame's label does not repeat it.
5. **A WHOLE BLOCK IS ON SCREEN THAT THE FRAME DOES NOT DRAW: the per-service
   exemption tick-list.** `PlanWizard.tsx:2513-2529` renders
   `rating.plan.surcharge.exemptLegend` = *"Services this surcharge does not touch"*
   over a 3-column grid of `CheckboxField`s, one per service on the draft, plus
   `exemptHelp`. It is `BR-RAT-102`'s ratified per-service exemption, so **this is a
   drawing-vs-rule item and not a defect** — see FOR THE PRODUCT OWNER below. It is
   also a second wall of checkboxes (rule 9 again).
6. **THREE MORE NOTES ARE STACKED UNDER THE PANEL THAT THE FRAME DOES NOT DRAW.**
   `PlanWizard.tsx:2411-2416` (`noClassYet` / `classFilterNote`) and
   `PlanWizard.tsx:2536-2540` (`premisesNote` / `noFactorNote`), on top of the
   `enabledOnly` note and the `unpricedSummary` note at `PlanWizard.tsx:2425-2431`.
   The frame draws **one** note under the services panel and **one** read-back under
   the surcharge panel. B14 rule 32: one sentence per section.

### Divergences recorded under B14 rule 38 — the UI rules win, nothing is built

* **The drawn refusal is fourteen words** — *"2 chosen. Sewer is offered but has no
  rate schedule for Residential yet, so it could not be billed until one exists."*
  **B14 rule 33 caps a refusal at five or six words.** The code's
  `rating.plan.services.noScheduleForClass` plus the service names is the shorter
  form. Rule wins; the drawing loses; nothing is built.

---

## FOR THE PRODUCT OWNER

1. **The drawn step 2 has no per-service surcharge exemption and the product has one.**
   `BR-RAT-102` ratifies it — *"on the plan's own service line, because the plan is
   what lists its services"* — so the drawing appears to have dropped a ratified
   capability rather than to have removed one deliberately. **Recorded, not resolved.**
   Deleting it to match the frame would remove a stored fact the engine reads.
2. **The services control should become the shared chip multi-select.** The drawing,
   B14 rule 9 and the kit all agree; only the code differs. One sentence of
   confirmation and it is a straight swap — but it is a control on a money-adjacent
   wizard, so it is named here rather than done.
