# Plans 29 · Create · Step 1 · Basics — THE DRAWN SPEC

`PLN-03 step 1` · route `/:tenant/plans-rates/plans/new` · **blueprint pages 85–87**

**Source:** `05-prototype/SMARTBillHub Plans & Rates Blueprint.pdf`, section `05 PLANS`,
screen `29`, opening on page 85 and specified on 86–87. Read as RENDERED pages — the
grey wireframe frame on 85–86 is the specification; the FOR / STATES / COMPONENTS /
RULES rows on 86–87 are its prose.

**State chip:** `NEW BUILD`
**Commitments on the chip line:** `PRB-15` (and `PRB-15` is itself **RULED NOT
REQUIRED** by the PO on 2026-09-08 — see the absence register, page 120)

**Section opener, page 85, verbatim:** *"Last, because a plan composes and prices
nothing itself. It can carry only what already exists."* · *"11 screens — 8 to create
or edit, 3 to view. 10 commitments touch them."*

**Figure 3, page 85 — the rule the whole section turns on:** *"a plan names, a charge
code prices. Five separate rulings on 2026-09-08 all resolved the same way. Reading
them as one rule is what makes the sixth predictable."*

**WHAT WAS WRONG (page 85, verbatim):** *"Five blocks of explanation on a four-field
screen, three of them describing where a value would later appear rather than what to
type."*

---

## 1 · The wizard chrome — drawn identically on every one of steps 1–8

| slot | drawn |
|---|---|
| kicker | `NEW PLAN` |
| title (H1) | `New plan` |
| sub-line | `Eight steps · takes about 5 minutes.` |
| action 1 (top-right) | `Cancel` *(link tier, accent text)* |
| action 2 (top-right) | `Save draft & exit` *(secondary, outlined)* |
| step rail | `1 Basics · 2 Services · 3 Rate schedules · 4 Charges · 5 Taxes · 6 Discounts & billing · 7 Eligibility · 8 …` — drawn CLIPPED, with a horizontal scrollbar under it |
| footer | one right-aligned button, `Continue` |

⚠ **EIGHT STEPS. `CR-087`'s headline — *"seven tab merges, a wizard step removed"* —
REMOVES A STEP FROM THE TAX WIZARD, NOT FROM THIS ONE.** `CR-087` §2's reversal table
reads *"Tax wizard | four steps | three"*; the plan wizard's row is *"Plan step 6 |
late fee and deposits set on the plan | set on the charge code"*. A lane reading the
headline as a plan-wizard step removal would delete a drawn step.

## 2 · The panel — one note, four fields, in this order

| # | drawn label | required | drawn value | control |
|---|---|---|---|---|
| — | *(note, above the first field)* | — | `The name is what customers see on their bills, so keep it plain.` | plain sentence |
| 1 | `PLAN NAME (CUSTOMER-FACING)` | `*` | `Residential Standard` | text |
| 2 | `PLAN CODE (INTERNAL)` | `*` | `SCW-RES` | text |
| 3 | `CUSTOMER CLASS` | `*` | `Residential` | select (chevron) |
| — | *(clause under the CUSTOMER CLASS label, above its control)* | — | `Chosen once — it narrows every later step.` | quiet line |
| 4 | `DESCRIPTION SHOWN TO CUSTOMER` | — | `Everyday water and power for a single home.` | text area |

⚠ **B14 rule 37 — every value in that column is an ILLUSTRATION.**
`Residential Standard`, `SCW-RES`, `Residential` and the description sentence are
examples of a shape. Nothing here may be asserted in a test or seeded from.

**TWO NAMES, SAID AS TWO (page 86, verbatim):** *"Customer-facing and internal are in
the labels, not in help text underneath. It is the commonest confusion on this screen
and a label fixes it for free."*

**WHAT CHANGED · THREE EXPLANATIONS BECAME ONE (page 86, verbatim):** *"The intro was
two sentences of advice, the class carried two more, and the description carried two
about where it appears. One sentence survives — the one a clerk can act on while
typing the name. The class keeps a single clause because chosen once is a consequence,
not a definition."*

## 3 · FOR · HOW YOU GET HERE · PRIMARY ACTION (page 86)

* **FOR** — *"A clerk building the thing a customer actually subscribes to."*
* **HOW YOU GET HERE** — *"`Plans` tab → `+ New plan`."*
* **PRIMARY ACTION** — *"`Continue`."*

## 4 · COGNITIVE LOAD (page 86)

*"Four fields, three required. From five blocks of prose to one."*

## 5 · STATES (pages 86–87)

| state | drawn behaviour |
|---|---|
| **No classes set up** | *"The field degrades to a read-only note saying where they are managed, rather than an empty select."* |
| **Editing** | *"All four pre-fill. The code stays editable until the plan is published."* |
| **Read-only role** | *"A role that may read but not change Plans & Rates sees every figure and no button. The refusal names the role, not the screen."* |

## 6 · COMPONENTS named in the frame (page 87)

`WizardFrame` `StepHead` `TextField` `SelectField` `TextArea`

## 7 · RULES, as stated (page 87)

*"Money shows two decimals and is stored to four; a percentage six. Colour is never
the only signal — every state carries its word. A code a clerk reads down the phone is
a printed reference, not a database id, so it is shown; a database id never is. Built
in the shared utility classes, adding nothing to a stylesheet."*

**Route corrected in the blueprint itself (page 87):** *"the document read
`/plans-rates/plans/new`; the router registers `/:tenant/plans-rates/plans/new`."*

## 8 · Absences — drawn as absent, do not fill them

* **No customer SUB-type field.** `PRB-15` is on this screen's chip line and the
  absence register (page 120) records it **RULED NOT REQUIRED by the PO on
  2026-09-08**, kept listed *"only because the COLUMN exists and is written by
  nothing, which is the shape of a field with no writer."*
* **No fifth field, and no help paragraph under any of the four.**

---

## DIFF AGAINST THE RUNNING CODE — `2.234.19`

Read from `07-frontend/src/features/rating/PlanWizard.tsx` and
`07-frontend/src/i18n/locales/en.json`.

### Conforming

| drawn | code | evidence |
|---|---|---|
| eight steps, in the drawn order | `PLAN_WIZARD_STEPS` — `basics · services · schedules · charges · taxes · discounts · eligibility · review` | `PlanWizard.tsx:198-207` |
| step labels | `rating.plan.step.*` = `Basics · Services · Rate schedules · Charges · Taxes · Discounts & billing · Eligibility · Review & activate` | `en.json` |
| sub-line `Eight steps · takes about 5 minutes.` | `rating.plan.sub`, verbatim | `PlanWizard.tsx:1935` |
| kicker `New plan`, title `New plan` | `rating.plan.kicker` / `rating.plan.newTitle` | `PlanWizard.tsx:1928,1931` |
| `Cancel` then `Save draft & exit`, in that order | two `secondaryActions` in that order | `PlanWizard.tsx:1937-1959` |
| the ONE note | `rating.plan.basics.oneNote` = *"The name is what customers see on their bills, so keep it plain."* — verbatim | `PlanWizard.tsx:2108` |
| four fields, three required | `plan-name` · `plan-code` · `plan-customer-class` · `plan-description` | `PlanWizard.tsx:2110,2121,2150,2173` |
| labels 1, 2, 3, 4 | `Plan name (customer-facing)` · `Plan code (internal)` · `Customer class` · `Description shown to customer` | `en.json` |
| the class clause | *"Chosen once — it narrows every later step."* is present as `rating.plan.customerClassChoose`-adjacent copy | see finding 2 |
| **No classes set up** state | `ArrivesWithField` with `rating.plan.customerClassEmpty` when `accountTypes.length === 0` | `PlanWizard.tsx:2144-2149` |
| `Continue` footer, right-aligned | `WizardFrame` owns it | `PlanWizard.tsx:1974` |

### Findings

1. **THE STEP HEAD ADDS A HEADING AND A HELPER PARAGRAPH THE FRAME DOES NOT DRAW,
   AND THE HELPER IS THE PROSE THE BLUEPRINT REMOVED.**
   `PlanWizard.tsx:2100` renders `StepHead step={1}` with
   `rating.plan.basics.hint` = *"The name is what customers see on their bills and
   during signup. Keep it plain — “Residential Standard” beats “RES-STD-2026-A”."*
   That is the second sentence of advice about the NAME, over a panel whose one note
   already says *"The name is what customers see on their bills, so keep it plain."*
   The drawn frame carries the note ONCE. **Two copies of one sentence is exactly
   `WHAT CHANGED · THREE EXPLANATIONS BECAME ONE` and B14 rule 32's description
   budget.** The heading (`rating.plan.basics.heading` = *"Name and describe this
   plan."*) is a third line the frame does not draw.
   ⚠ The `StepHead` is drawn on **every** step of **all five** wizards
   (`PlanWizard.tsx:2010-2023`), so removing it here is not a local edit.

2. **THE CLASS CLAUSE IS NOT WHERE THE DRAWING PUTS IT.** The frame draws
   `Chosen once — it narrows every later step.` as a quiet line **between the
   `CUSTOMER CLASS` label and its select**. In code the comment at
   `PlanWizard.tsx:2155-2159` says the clause was *"moved into the
   placeholder-adjacent copy above"* — and the only string the select receives is
   `placeholder={t("rating.plan.customerClassChoose")}` = `Choose a class`. **The
   clause is not rendered at all on this step.** Not verified in a browser; verified
   as absent from the JSX.

3. **NOTHING ON THIS STEP MARKS THE CODE AS EDITABLE-UNTIL-PUBLISHED.** The drawn
   `Editing` state says *"The code stays editable until the plan is published."*
   `PlanWizard.tsx:2121` renders `plan-code` with no `disabled`/`readOnly` branch on
   `plan.status`, so the code is editable **after** publish too. Whether the server
   refuses it was not checked from this lane; the SCREEN makes no distinction, which
   is what the drawn state describes.

4. **THE HELP TEXT THE RULING REMOVED IS STILL IN ALL ELEVEN CATALOGUES, AND FIVE OF
   THEM CARRY IT IN ENGLISH.** `rating.plan.customerClassHelp` = *"Chosen once. It
   narrows the services, rate schedules and discounts every later step offers."* is
   referenced by **no screen** — its only mention in the tree is a NEGATIVE assertion,
   `cr087PlanWizard.dom.test.tsx:509`: `expect(html).not.toContain(...)`. It is left
   untranslated in **`hi`, `id-ID`, `ja-JP`, `ko-KR` and `es-MX`** (raw English,
   `en.json:10430` and the same line in each), which is B14 rule 35's subject. Latent
   today because nothing renders it; it becomes a live rule-35 breach the moment
   anybody reaches for the key by name.

### Divergences recorded under B14 rule 38 — the UI rules win, nothing is built

* **The drawing shows no asterisk convention of its own** and the code marks required
  fields with the kit's asterisk (B14 rule 10). Agreement, recorded for completeness.
* **`Cancel` is a `ghost` Button in the header** rather than the drawn accent-text
  link. `WizardFrame` owns the footer row for ten wizards
  (`PlanWizard.tsx:1937-1943`, its own comment). Kit wins.

---

## FOR THE PRODUCT OWNER

Nothing on this screen conflicts with a signed rule. One question is worth one
sentence: **the drawn frame carries no step heading and no helper paragraph, and the
product draws both on every step of every wizard.** Removing them matches the drawing
and changes five wizards at once.
