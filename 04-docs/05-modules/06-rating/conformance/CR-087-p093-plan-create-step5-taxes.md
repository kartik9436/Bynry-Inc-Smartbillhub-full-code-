# Plans 33 · Create · Step 5 · Taxes — THE DRAWN SPEC

`PLN-03 step 5` · route `/:tenant/plans-rates/plans/new` · **blueprint pages 93–95**

**Source:** `05-prototype/SMARTBillHub Plans & Rates Blueprint.pdf`, screen `33`,
frame drawn on page 94, specified on 94–95.

**State chip:** `NEW BUILD`
**Commitments on the chip line:** `PRB-17`

**WHAT WAS WRONG (page 94, verbatim):** *"Authorities could be removed and never
added, so a plan missing a county tax had to be started again."*

---

## 1 · Wizard chrome

As step 1, with `5 Taxes` active. Footer `Continue`.

## 2 · The one panel — `Taxes on this plan`

| slot | drawn |
|---|---|
| panel title | `Taxes on this plan` |
| panel sentence, under the title | `A plan chooses what applies — never at what rate.` |
| table | FOUR columns plus a row-action column |

| # | header | alignment | drawn cells |
|---|---|---|---|
| 1 | `AUTHORITY` | left | `Texas State` · `Bexar County` |
| 2 | `TAX OR FEE` | left | `TX State Utility Tax` · `Local · Bexar County` |
| 3 | `RATE` | left | `6.25%` · `1.0%` |
| 4 | `SERVICES` | left | `All services` · `All services` |
| — | row action | right | row 1: `Brought by jurisdiction` *(plain text, NOT a control)* · row 2: `Remove` *(accent text link)* |

⚠ **THE FIRST ROW'S ACTION CELL IS A FACT AND THE SECOND'S IS A CONTROL.** That
distinction is the point of the frame: a tax a bound authority mandates cannot be
detached, so its cell says why instead of offering a button.

**Beneath the table:** one button, `+ Add an authority` (secondary, outlined).

**Under that, a red-ruled callout:**

> **A PLAN CANNOT OPT OUT**
> `Attaching adds — it never removes. A tax a bound authority mandates stays on the`
> `bill whether or not anyone added it, and nothing on this step can detach it.`

⚠ **B14 rule 37 — `Texas State`, `Bexar County`, `6.25%`, `1.0%` are ILLUSTRATIONS.**

**WHAT CHANGED · THERE WAS NO WAY TO ADD ONE (page 95, verbatim):** *"A plan is
composed by adding, so there is an **Add** button and rows are removed one at a time.
… **+ Add an authority** lists the authorities this utility has set up, each with what
it levies and at what rate, and marks the ones already arriving by jurisdiction so
nobody adds a duplicate."*

**ATTACHING ADDS, NEVER REMOVES (page 95, verbatim):** *"Stated as its own note,
because a clerk who thinks this screen can take a tax off a bill is about to make a
compliance error. There is no exempt tick and the screen says marking a plan exempt is
not available — a plan may not skip a statutory tax."*

## 3 · FOR · HOW YOU GET HERE · PRIMARY ACTION (pages 94–95)

* **FOR** — *"The clerk making sure the statutory levies reach this plan's customers."*
* **HOW YOU GET HERE** — *"Continue from Charges."*
* **PRIMARY ACTION** — *"`Continue`."*

## 4 · COGNITIVE LOAD (page 95)

*"Grouped by authority, because that is how a tax arrives — a city and a county both
apply and each is decided on its own."*

## 5 · STATES (page 95)

| state | drawn behaviour |
|---|---|
| **No authorities set up** | *"Add is held, saying this is a setup gap and not a property of the plan, and points at Taxes & fees. The distinction matters: one is a missing step, the other is a decision."* |
| **Bound but levies nothing** | *"Bound, but this authority levies nothing on the services this plan carries."* |
| **A base code marked not taxable** | *"Warns that the bill would be short by that tax, and names the codes."* |

## 6 · COMPONENTS named in the frame (page 95)

`WizardFrame` `AttachedTable` `AddFromCatalogue` `Callout accent`

## 7 · Absences — drawn as absent, do not fill them

* **No rate box.** **No exempt tick.**
* **No search box on the panel** — the catalogue opens behind `+ Add an authority`.
* **No second pane.**

---

## DIFF AGAINST THE RUNNING CODE — `2.234.19`

### Conforming

| drawn | code | evidence |
|---|---|---|
| rows GROUPED by authority | `taxesByAuthority(matches)` | `PlanWizard.tsx:3250`, `PlanWizard.tsx:1481` |
| the bind control sits on the AUTHORITY, never on a single tax | the button is rendered beside the authority Kicker, not per row | `PlanWizard.tsx:3317-3341` |
| `Brought by jurisdiction` as a FACT on a mandated row | `rating.plan.taxes.broughtByBoundAuthority` = *"Carried — brought by a bound authority"*, rendered as text | `PlanWizard.tsx:3366-3369` |
| the opt-out callout, near-verbatim | `rating.plan.taxes.addOnlyNote` = *"Attaching adds — it never removes. A tax a bound authority mandates stays on the bill whether or not anyone ticked it, and nothing on this step can detach it."* | `en.json` |
| no exempt tick, and the screen says so | `rating.plan.taxes.noExemptControl` | `en.json` |
| no rate box | `rating.plan.taxes.noRateOverrideNote`; the override field is not rendered | `en.json` |
| **No authorities set up** state, both halves | `rating.plan.taxes.noneToBind` = *"…That is a setup gap, not a property of this plan — add them on the Taxes & fees tab."* | `en.json` |
| **Bound but levies nothing** state, verbatim | `rating.plan.taxes.boundButUnknown` | `en.json` |
| **A base code marked not taxable** state | `taxabilityMismatches` → `rating.plan.taxes.taxabilityMismatch`, naming the codes | `PlanWizard.tsx:1159`, `en.json` |

### Findings

1. **THE TWO-PANE LAYOUT AGAIN.** `PlanWizard.tsx:3296-3298` — the same
   `grid-cols-[1fr_340px]` geometry as steps 4 and 6, with a
   `Search taxes and authorities` box (`PlanWizard.tsx:3301-3306`) on the left and
   `On this plan · {{count}}` on the right. The frame draws one attached table plus
   `+ Add an authority`. **Same drawing-versus-PO-ruling conflict as step 4** — see
   `CR-087-p091`'s CONTRADICTIONS section; `CR-021` in
   `12-governance/11-change-requests.md:9604` captures the PO's own words for THIS
   step: *"Step 5 - Cannnot add Taxes at all - again it is search and add option"*.
2. **THERE IS NO `+ Add an authority` BUTTON.** The add controls are
   `rating.plan.taxes.attach` = **`+ Attach`** per tax row
   (`PlanWizard.tsx:3376-3382`) and a bind/unbind Button per authority group
   (`PlanWizard.tsx:3330-3341`). The drawn button names its object once.
3. **THE PANEL HAS NO TITLE MATCHING THE DRAWING.** Drawn `Taxes on this plan`; the
   left pane opens with `rating.plan.taxes.bindNote` and no heading, and the right
   pane's Kicker is `rating.plan.taxes.appliedTitle` = *"On this plan · {{count}}"*.
   `rating.plan.taxes.title` = *"Taxes"* exists and is used elsewhere.
4. **THE TABLE IS NOT A TABLE.** The frame draws four column headers —
   `AUTHORITY · TAX OR FEE · RATE · SERVICES`. The code draws grouped rows of flex
   items with the rate and the base rule as inline sentences
   (`PlanWizard.tsx:3352-3394`), so there are no column headers at all and the
   `SERVICES` fact rides inside `rating.plan.taxes.baseRule` =
   *"Applies to {{base}} on {{services}}."* B14 rule 20's table tiers cannot apply to
   something that is not a table.
5. **TWO MORE NOTES THAN THE FRAME DRAWS.** `rating.plan.taxes.bothGatesNote` and
   `rating.plan.taxes.noRateOverrideNote` sit beside `addOnlyNote`. The frame carries
   ONE callout. B14 rule 32.

### Divergences recorded under B14 rule 38 — the UI rules win, nothing is built

* **The drawn `Remove` is a text link.** B14 rule 15 makes a row action an ICON with a
  tooltip. The code's unbind is a Button with an accessible name
  (`rating.plan.taxes.unbindNamed`). Rule wins; the drawing loses.

---

## FOR THE PRODUCT OWNER

Same single question as step 4: **the drawn one-table-plus-Add shape and the built
two-pane search-and-add shape are both the PO's**, ruled fifteen days apart. One
sentence settles steps 4, 5 and 6 together.
