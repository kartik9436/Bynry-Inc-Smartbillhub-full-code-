# Plans 34 · Create · Step 6 · Discounts & billing — THE DRAWN SPEC

`PLN-03 step 6` · route `/:tenant/plans-rates/plans/new` · **blueprint pages 95–99**

**Source:** `05-prototype/SMARTBillHub Plans & Rates Blueprint.pdf`, screen `34`,
frame drawn on pages 96–97, specified on 97–99.

**State chip:** ⚠ **`BLOCKED`** — *"a specification here waits on a decision nobody
has made"* (page 2's own definition of the chip).
**Commitments on the chip line:** `PRB-17` · `PRB-26`

**WHAT WAS WRONG (page 96, verbatim):** *"The same money could be set in two places —
a late fee and a deposit on the plan, and the same figures on the charge code the plan
already names — and discounts could be removed but never added."*

---

## 1 · Wizard chrome

As step 1, with `6 Discounts & billing` active. Footer `Continue`.

## 2 · Panel 1 — `Discounts offered`

| # | header | drawn cells |
|---|---|---|
| 1 | `CODE` | `SENIOR` |
| 2 | `DISCOUNT` | `Senior citizen discount` |
| 3 | `VALUE` | `10%` |
| 4 | `OFFERED FROM` | a DATE input holding `09/08/2026` |
| 5 | `OFFERED UNTIL` | a DATE input, empty, placeholder `dd/mm/yyyy` |
| — | row action | `Remove` *(accent text link)* |

**Beneath the table:** one button, `+ Add a discount` (secondary, outlined).

**Under that, a red-ruled callout:**

> **OFFERED, NOT GIVEN**
> `Adding a discount here offers it. Nobody's bill changes until an account is enrolled on it.`

## 3 · Panel 2 — `Other terms`

| # | drawn | control |
|---|---|---|
| 1 | `☐ Offer budget billing on this plan` | checkbox, label to the right |
| 2 | `MINIMUM BILL FOR THE WHOLE PLAN` | label |
| — | `Applied after the per-service minimums, to top the total up.` | help line, under the label, above the input |
| 3 | *(the money input)* | text, empty |
| 4 | `BILLING CYCLE, FREQUENCY AND DUE-DATE OFFSET` | label |
| — | `—` | absence mark |
| — | `These come from the utility's billing defaults and cannot be set per plan yet.` | quiet sentence |
| — | red-ruled callout | **SET ON THE CHARGE CODE** — `Late fees and deposits are not set here. They are charge codes — added on step 4, priced by customer class on the code itself — and step 8 shows what this plan ends up with.` |

## 4 · Panel 3 — `Joining or leaving part-way through a cycle` ⚠ **DRAWN AND NOT BUILT**

| # | drawn | control |
|---|---|---|
| 1 | `WHEN SOMEONE JOINS OR LEAVES MID-CYCLE` | label |
| 2 | `Charge the days they had it — 16th of a 30-day month bills 15/30` | select |
| — | read-back, accent rule | `A $30.50 base charge from the 16th of a 30-day month bills $15.25.` |
| — | red-ruled callout | **PROPOSED — AWAITING A FINANCE RE-SIGN** — `Drawn for your decision and NOT built. Today every plan does exactly what this box says, because it is a finance-signed rule rather than a setting: proration is by calendar days and the base charge is always prorated. Offering a plan any other answer changes a signed figure, which needs a finance re-sign before a line of code is written.` |

⚠ **THIS IS WHY THE SCREEN CARRIES `BLOCKED`, AND IT IS `B4`/`B5` TERRITORY.** Page 98,
verbatim: *"You asked for this to be selectable and it is drawn so you can see what you
would be choosing — **but it is not a setting today and cannot become one on a chat
instruction.** … what actually decides it is a **finance-signed rule** — by calendar
days, one factor for the whole account, the base charge always prorated, usage prorated
only when there was no move-in read. A move-in on the 16th of a 30-day month with a
$30.50 base bills **$15.25**, and that figure is signed. A plan offering *charge the
whole period* would contradict *always prorated* on a signed number, so it needs a
finance re-sign first. **The cheaper version, if you want it:** the plan states which
of the existing answers applies to it, read-only — documentation rather than a choice,
and no re-sign."*

**NOTHING IN THIS PANEL MAY BE BUILT FROM THIS LANE OR ANY OTHER WITHOUT A FINANCE
RE-SIGN THROUGH HUMAN-GUIDE §6.**

## 5 · FOR · HOW YOU GET HERE · PRIMARY ACTION (page 97)

* **FOR** — *"The clerk setting what happens when a bill is late, and what help is on offer."*
* **HOW YOU GET HERE** — *"Continue from Taxes."*
* **PRIMARY ACTION** — *"`Continue`."*

## 6 · WHAT CHANGED · LATE FEES AND DEPOSITS LEFT THIS STEP ALTOGETHER (page 97, verbatim)

*"A plan names charge codes; the charge code carries the money. Both were drawn here and
both are gone, on your ruling. A deposit varies by customer class — $150.00 Residential,
$400.00 Commercial — and the charge code now has a class column, so that is **one**
charge code with two prices rather than two rows repeated on every plan that exists. The
late fee is the same shape and was already half-done: the engine has read its percentage
and its minimum off the charge code since **2026-09-07**, so the picker here was a second
place to name a code the plan already names on step 4."*

**NOTHING IS LOST BY REMOVING THEM (page 97, verbatim):** *"`LATE · Late payment fee ·
1.5% of the amount · On an event` sits on step 4 with every other charge code this plan
carries. Removing the second picker removes the duplicate, not the capability — and
**step 8 lists the late fee and every deposit**, read-only, sourced from the attached
codes, the same treatment you ruled for base charges."*

## 7 · COGNITIVE LOAD (page 98)

*"Two blocks, and the second is three controls. The old screen was one list of nine in
which a deposit, a grace day and a budget-billing tick sat at the same weight."*

## 8 · STATES (page 98)

| state | drawn behaviour |
|---|---|
| **No discounts set up** | *"Add is held: this utility has not set up any discounts yet."* |
| **Removing one with people on it** | *"Refused, naming the count: removing a discount from a plan while people are receiving it has not been decided."* |
| **No late-fee charge code on step 4** | *"Step 8 says so plainly: this plan charges nothing for a late bill. That is the ruled behaviour and not an oversight."* |
| **No deposit charge code** | *"Step 8 says no deposit is taken on this plan, rather than showing an empty table."* |

## 9 · COMPONENTS named in the frame (page 98)

`WizardFrame` `AttachedTable` `AddFromCatalogue` `DatePickerField` `InlineCheck`
`MoneyTextField` `NamedAbsence`

## 10 · Absences — drawn as absent, do not fill them

* **No late-fee picker, no late-fee percentage, no late-fee minimum.**
* **No deposit block, no deposit amount, no per-class deposit row.**
* **No grace-days control.**
* **No value box on a discount row.**

---

## DIFF AGAINST THE RUNNING CODE — `2.234.19`

### Conforming

| drawn | code | evidence |
|---|---|---|
| the late-fee block is GONE | no picker, no percentage, no minimum on this step; the map and setter were DELETED rather than commented out | `PlanWizard.tsx:3653-3667`, and the file's own note |
| the deposit block is GONE | same commit; `planPayload` still re-posts `deposit_rules` untouched so a stored `$400.00` survives a rename | `PlanWizard.tsx:3953-3960`, `PlanWizard.tsx:819-` |
| the sentence where the block was | `rating.plan.discounts.setOnChargeCode` = *"Late fees and deposits are charge codes, added on step 4."* | `PlanWizard.tsx:3937` |
| offered-not-granted | `rating.plan.discounts.availableNotGrantedNote` = *"Adding a discount here offers it. Nobody's bill changes until an account is enrolled on it."* — verbatim to the drawn callout | `PlanWizard.tsx:3865` |
| `OFFERED FROM` / `OFFERED UNTIL` as the two date labels | `availableFromLabel` / `availableToLabel`, verbatim | `PlanWizard.tsx:3831,3846` |
| both are real date controls | `DatePickerField` with the tenant's `dateFormat` (B14 rule 7) | `PlanWizard.tsx:3830,3845` |
| **Removing one with people on it** refused, naming the count | `discountUnbindAllowed(enrolled)` → `rating.plan.discounts.unbindBlocked` | `PlanWizard.tsx:1474`, `en.json` |
| the budget-billing checkbox label, verbatim | `rating.plan.budgetBillingLabel` = *"Offer budget billing on this plan"* | `PlanWizard.tsx:3886-3892` |
| the minimum-bill label, verbatim | `rating.plan.minimumBillLabel` = *"Minimum bill for the whole plan"* | `PlanWizard.tsx:3897` |
| the minimum-bill help, near-verbatim | `rating.plan.minimumBillHelp` = *"Optional. Applied after the per-service minimums, to top the total up."* | `en.json` |
| the cycle label + its absence sentence, verbatim | `cycleLabel` / `cyclePending`, drawn as an `ArrivesWithField` (a named absence) | `PlanWizard.tsx:3948-3951` |
| **the mid-cycle panel is NOT BUILT** | no proration control anywhere in the file; the only mentions are two comments naming it as a gap | `PlanWizard.tsx:3941,3945` |
| `Remove` as the discount row's word | `rating.plan.discounts.unbind` = *"Remove"* | `en.json` |

### Findings

1. **THE TWO-PANE LAYOUT, A THIRD TIME.** `PlanWizard.tsx:3697-3698`. Same conflict as
   steps 4 and 5; see `CR-087-p091`'s CONTRADICTIONS.
2. **THERE IS NO `+ Add a discount` BUTTON**, for the same reason: the add control is
   per catalogue row in the left pane.
3. **PANEL TITLES DIVERGE.** Drawn `Discounts offered` / `Other terms`; code
   `rating.plan.discounts.availableTitle` = *"Available discounts"*
   (`PlanWizard.tsx:3700`) and `rating.plan.discounts.billingTitle` =
   *"Billing terms"* (`PlanWizard.tsx:3884`).
4. **THE DISCOUNT ROWS ARE A `<ul>`, NOT THE DRAWN FIVE-COLUMN TABLE.**
   `PlanWizard.tsx:3800-3859` renders each bound discount as a list item with the
   value and the enrolled count as one inline sentence and the two dates side by side
   underneath. The frame draws `CODE · DISCOUNT · VALUE · OFFERED FROM · OFFERED UNTIL`
   as column headers.
5. **THE `SET ON THE CHARGE CODE` CALLOUT IS SHORTER THAN DRAWN.** The frame's sentence
   also says *"priced by customer class on the code itself — and step 8 shows what this
   plan ends up with"*, which is the half that tells a clerk where to look next. The
   code's one sentence stops at *"added on step 4."*
6. **FOUR NOTES STACK UNDER THE DISCOUNT PANEL WHERE THE FRAME DRAWS ONE CALLOUT.**
   `availableNotGrantedNote` · `noValueOverrideNote` · `secondApproval` (or
   `secondApprovalUnknown`) · `secondApprovalNoBudget`
   (`PlanWizard.tsx:3865-3879`). B14 rule 32's description budget.
7. **THE CYCLE ABSENCE IS DRAWN OUTSIDE THE `Other terms` PANEL.**
   `PlanWizard.tsx:3948` renders the `ArrivesWithField` AFTER the panel closes at
   `:3938`. The frame puts it inside `Other terms`, as its third row.

### Divergences recorded under B14 rule 38 — the UI rules win, nothing is built

* **The drawn `dd/mm/yyyy` placeholder.** The tenant's regional date format is
  `BR-SHL-033`'s and `DatePickerField` owns it; a hard-coded day-first placeholder
  would be wrong for a North American tenant. Kit wins.
* **The drawn `Remove` text link.** B14 rule 15 — icons, not text links. Rule wins.

---

## FOR THE PRODUCT OWNER — ⚠ **B4/B5, DO NOT ACT WITHOUT A RE-SIGN**

**The frame's third panel asks a plan to choose its mid-cycle proration, and the
blueprint itself says it cannot be built.** The signed figure is `$15.25` — a $30.50
base from the 16th of a 30-day month — and *"a plan offering charge the whole period
would contradict always prorated on a signed number"*. **The screen is correct today
precisely by NOT having the control.** The blueprint offers the cheap alternative in
its own words: *"the plan states which of the existing answers applies to it,
read-only — documentation rather than a choice, and no re-sign."* Recorded; nothing
built.
