# Plans 35 · Create · Step 7 · Eligibility — THE DRAWN SPEC

`PLN-03 step 7` · route `/:tenant/plans-rates/plans/new` · **blueprint pages 99–101**

**Source:** `05-prototype/SMARTBillHub Plans & Rates Blueprint.pdf`, screen `35`,
frame drawn on pages 99–100, specified on 100–101.

**State chip:** `NEW BUILD`
**Commitments on the chip line:** `PRB-25`

**WHAT WAS WRONG (page 99, verbatim):** *"A heading that read as a permission sat four
inches above a sentence saying it refuses nobody, with the same fact stated a third
time below — and the dates, which are not eligibility, were buried in the same block."*

---

## 1 · Wizard chrome

As step 1, with `7 Eligibility` active. Footer `Continue`.

## 2 · Panel 1 — `Who this plan is meant for`

| # | drawn | control |
|---|---|---|
| panel title | `Who this plan is meant for` | heading |
| callout, red rule, FIRST thing in the panel | **NOTHING HERE REFUSES ANYBODY** — `This is a note for staff. It does not stop anyone being put on this plan — any account can be assigned to it, and the record shows who did.` | callout |
| 1 | `ATTRIBUTE` | select, placeholder `Choose an attribute` |
| 2 | `OPERATOR` | select, placeholder `Choose an operator` |
| 3 | `VALUE` | select, placeholder `Choose a value` |
| — | one button, under the three | `+ Add a note` *(secondary, outlined)* |

⚠ **THE THREE CELLS SIT SIDE BY SIDE IN ONE ROW** — attribute, operator, value, equal
thirds, with the button beneath at the left.

⚠ **THE BUTTON SAYS `+ Add a note`, NOT `+ Add rule`.** That is the whole point of the
screen: *"A row like `Meter size · is · 5/8 inch` is a written note about the kind of
customer this plan was designed for. It is stored, it shows on the plan's page and in
the audit trail, and **nothing reads it at billing time** — a clerk can put any account
on any plan and the product will price it. It is documentation, not a rule."* (page 100)

## 3 · Panel 2 — `When it runs`

| # | drawn label | required | drawn value |
|---|---|---|---|
| 1 | `EFFECTIVE FROM` | `*` | `01/01/2027`, in a date input with a calendar affordance |
| — | refusal, red, directly under the input | `Set a start date. A plan cannot be published without one.` | — |
| 2 | `EFFECTIVE TO` | — | placeholder `No planned end`, date input |

**WHAT CHANGED · A REQUIRED DATE WAS UNCHECKED HERE (page 100, verbatim):** *"A blank
start date passed Continue and surfaced on step 8 as *set a start date before publishing
this plan* — one screen from the end, for a field on this one. **It is checked here**,
and the dates are their own block because they are not eligibility at all."*

## 4 · FOR · HOW YOU GET HERE · PRIMARY ACTION (page 100)

* **FOR** — *"The clerk recording who a plan is aimed at, and when it starts."*
* **HOW YOU GET HERE** — *"Continue from Discounts & billing."*
* **PRIMARY ACTION** — *"`Continue`."*

## 5 · WHAT CHANGED · THE SCREEN CONTRADICTED ITSELF IN TWO LINES (page 100, verbatim)

*"*Who may be put on this plan* is a permission. *They never block an assignment in this
version* is the opposite, and both were on the screen, four inches apart, with a third
sentence saying the same thing again lower down. A reader could not tell whether this was
a gate. It is not, so the heading now says **who this plan is meant for**, the one note
says **nothing here refuses anybody**, and the third sentence is gone. Same fact, said
once, in a heading that agrees with it."*

## 6 · ONLY REAL ATTRIBUTES ARE OFFERED (page 100, verbatim)

*"The list holds only what the product can actually read off an account. Meter size,
jurisdiction, premise type, income programme and demand are named as absent rather than
offered and ignored."*

## 7 · COGNITIVE LOAD (page 101)

*"Two blocks: the note, and the dates. They were one, which is why the dates were hard
to find."*

## 8 · STATES (page 101)

| state | drawn behaviour |
|---|---|
| **No notes** | *"`No notes yet. Every account qualifies for this plan.` Which is the truth, and is not a warning."* |
| **Older boolean flags stored** | *"Kept, saved unchanged, and named — new limits are written as rows above."* |
| **A count against accounts** | *"Not shown: nothing evaluates one of these or counts accounts against it. Said, rather than left as an empty figure."* |

## 9 · COMPONENTS named in the frame (page 101)

`WizardFrame` `RuleBuilder` `DatePickerField` `Callout accent`

## 10 · Absences — drawn as absent, do not fill them

* **No third panel** — the seven limits a plan cannot record are on the plan's PAGE
  (screen 37), not on this step.
* **No count of matching accounts.**
* **No self-serve-signup toggle, no zone/route toggle.**

---

## DIFF AGAINST THE RUNNING CODE — `2.234.19`

### Conforming

| drawn | code | evidence |
|---|---|---|
| the panel title, verbatim | `rating.plan.eligibility.meantForTitle` = *"Who this plan is meant for"* | `PlanWizard.tsx:4114` |
| the callout sentence's first half, verbatim | `rating.plan.eligibility.refusesNobody` = *"Nothing here refuses anybody."* | `PlanWizard.tsx:4115` |
| three cells: attribute, operator, value | three `SelectField`s / a `TextField` for the value | `PlanWizard.tsx:4134-4172` |
| the three placeholders, verbatim | `chooseAttribute` · `chooseOperator` · `chooseValue` | `en.json` |
| only real attributes offered, and the rest NAMED | `attributes` is assembled by the consumer, never invented; `rating.plan.eligibility.attributesLimited` names the five | `PlanWizard.tsx:4180`, `en.json` |
| **No notes** state, verbatim | `rating.plan.eligibility.noRules` = *"No rules yet. Every account qualifies for this plan."* | `PlanWizard.tsx:4187` |
| **Older boolean flags** state | `legacyEligibilityFlags` → `rating.plan.eligibility.legacyFlags`, kept and saved unchanged | `PlanWizard.tsx:4068`, `en.json` |
| **A count against accounts** state | `rating.plan.eligibility.matchPending` — said, not blank | `PlanWizard.tsx:4232` |
| the second panel's title, verbatim | `rating.plan.eligibility.whenItRuns` = *"When it runs"* | `PlanWizard.tsx:4241` |
| `EFFECTIVE FROM` required, with the asterisk on the field | `DatePickerField … required` | `PlanWizard.tsx:4266-4273` |
| a real date control, not a text box (B14 rule 7) | `DatePickerField` on both | `PlanWizard.tsx:4266,4274` |

### Findings

1. **THE HEADING THE DRAWING SAYS WAS REMOVED IS STILL ON THE SCREEN, AND SO IS THE
   THIRD SENTENCE.** `PlanWizard.tsx:4098-4101` renders
   `StepHead step={7} headingKey="rating.plan.eligibility.heading"
   hintKey="rating.plan.eligibility.hint"` — and those two keys are, verbatim:

   * `rating.plan.eligibility.heading` = **`Who may be put on this plan.`**
   * `rating.plan.eligibility.hint` = **`These record who the plan is meant for. They never block an assignment in this version.`**

   Those are the exact two sentences page 100 names as the contradiction: *"Who may be
   put on this plan is a permission. They never block an assignment in this version is
   the opposite, and both were on the screen, four inches apart."* The panel below now
   carries the corrected pair, so **the screen says it three times and still opens with
   the permission wording.** The fix landed on the panel and not on the step head.
   ⚠ A third copy sits at `PlanWizard.tsx:4121` —
   `rating.plan.eligibility.whatItRecords` = *"These are notes for staff. Any account
   can still be put on this plan, and the record shows who did it."* The frame draws
   this fact ONCE, inside the callout.
2. **THE BUTTON SAYS `+ Add rule`, WHICH IS THE WORD THE DRAWING REPLACED.**
   `rating.plan.eligibility.addRule` = *"+ Add rule"*, rendered at
   `PlanWizard.tsx:4174-4176`. The frame draws `+ Add a note`, and the surrounding
   prose is explicit that *"It is documentation, not a rule."* A button that says
   `rule` over a screen that says `it is not a rule` is the same self-contradiction
   one word further along.
   ⚠ The rules list header is the same word: `rating.plan.eligibility.rulesTitle` =
   *"Rules · all must pass · {{count}}"* (`PlanWizard.tsx:4184`), and *"all must
   pass"* asserts an evaluation nothing performs.
3. **`EFFECTIVE FROM` IS NOT CHECKED ON THIS STEP.** `PlanWizard.tsx:1644-1657` — step 7's
   entry in `planWizardSteps` carries **no `validate` at all** (only steps 1, 2 and 3
   declare one — `:1548`, `:1556`, `:1580`), so `draft.effective_from` is never tested
   before `Continue`; the only refusal is on step 8
   (`PlanWizard.tsx:4695-4697`, `rating.plans.no_effective_from`). **This is the exact
   defect page 100 describes as fixed:** *"A blank start date passed Continue and
   surfaced on step 8 … It is checked here."* It is not.
4. **THE `+ Add rule` BUTTON IS `variant="primary"`.** `PlanWizard.tsx:4174`. B14 rule
   4's grammar makes `+ Noun` a CREATOR, and `BR-SHL-044` reserves one primary per
   screen — which the wizard frame's own commit already holds. Recorded as a tier
   question rather than a defect.
5. **A NAMED-ABSENCE FIELD SITS BELOW THE SECOND PANEL THAT THE FRAME DOES NOT DRAW.**
   `PlanWizard.tsx:4293-4296` renders `rating.plan.eligibility.limitsLabel` =
   *"Area, connection size, occupancy, proof and recertification"* with
   `limitsPending`. The blueprint puts those seven limits on the plan's PAGE (screen
   37, page 108's `Not recorded on a plan yet` panel) and draws nothing for them here.
6. **A STAFF-ASSIGNMENT-ONLY NOTE IS DRAWN NOWHERE IN THE FRAME.**
   `PlanWizard.tsx:4283` renders `rating.plan.staffAssignmentOnly`. Recorded under
   B14 rule 32.
7. **`EFFECTIVE TO`'s PLACEHOLDER IS NOT `No planned end`.** The frame draws that
   sentence in the empty input; `DatePickerField` at `PlanWizard.tsx:4274-4280`
   passes none, so the control shows the browser's own empty date affordance.

---

## FOR THE PRODUCT OWNER

Nothing here conflicts with a signed rule. Two of the findings are the SAME fix
half-landed — the step head still opens with the permission wording the ruling
removed, and the add control still says `rule` where the screen says `note`. Both are
copy on a step that writes nothing to a bill.
