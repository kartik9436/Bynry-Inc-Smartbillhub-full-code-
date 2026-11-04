# Plans 32 · Create · Step 4 · Charges — THE DRAWN SPEC

`PLN-03 step 4` · route `/:tenant/plans-rates/plans/new` · **blueprint pages 91–93**

**Source:** `05-prototype/SMARTBillHub Plans & Rates Blueprint.pdf`, screen `32`,
frame drawn on page 92, specified on 92–93.

**State chip:** `NEW BUILD`
**Commitments on the chip line:** `PRB-17`

**WHAT WAS WRONG (page 92, verbatim):** *"Rows could be removed and never added, so a
plan built with the wrong charge code had to be started again."*

---

## 1 · Wizard chrome

As step 1, with `4 Charges` active. Footer `Continue`.

## 2 · The one panel — `Charges on this plan`

| slot | drawn |
|---|---|
| panel title | `Charges on this plan` |
| panel sentence, immediately under the title | `A plan composes; it does not price. Amounts belong to the charge code.` |
| table | FOUR columns plus a row action |

| # | header | alignment | drawn cells |
|---|---|---|---|
| 1 | `CODE` | left | `CONN` · `LATE` |
| 2 | `CHARGE` | left | `Connection fee` · `Late payment fee` |
| 3 | `AMOUNT` | left | `$45.0000` over a second line `from CONN`; `1.5% of the amount` over `from LATE` |
| 4 | `APPLIED` | left | a SELECT per row: `Once` · `On an event` |
| — | row action | right | `Remove` — **a text link, accent colour** |

**Beneath the table, on one row:**

| # | control | tier |
|---|---|---|
| 1 | `+ Add a charge code` | secondary, outlined |
| 2 | `Not listed? Define one →` | link, accent |

**Under that, a quiet note (grey rule):**
`A plan cannot change a charge's amount. To charge something different, use a different charge code.`

⚠ **B14 rule 37 — `CONN`, `LATE`, `$45.0000`, `1.5%` are ILLUSTRATIONS.**
⚠ **AND `$45.0000` IS FOUR DECIMALS ON A CLERK-FACING SCREEN.** The blueprint's own
RULES row on this very page says *"Money shows two decimals and is stored to four"*,
and CLAUDE.md hard rule 2 says the same. **The frame contradicts its own rule.** See
CONTRADICTIONS below.

**WHAT CHANGED · THERE WAS NO WAY TO ADD ONE (page 93, verbatim):** *"A plan is
composed by adding, so there is an **Add** button and rows are removed one at a time.
Before this, a row could only be taken away — a plan built with the wrong thing had to
be started again. **+ Add a charge code** opens the catalogue filtered to this plan's
class and services, shows each code's amount, and adds the ones chosen. *Not listed?
Define one →* stays beside it for the case the catalogue genuinely lacks it."*

**A PLAN DOES NOT PRICE (page 93, verbatim):** *"Said once, at the top. There is no
amount box and no taxable tick — both were removed when the rule was signed, and the
screen explains rather than leaving a clerk hunting."*

## 3 · FOR · HOW YOU GET HERE · PRIMARY ACTION (page 92)

* **FOR** — *"The clerk attaching the fees this plan carries."*
* **HOW YOU GET HERE** — *"Continue from Rate schedules."*
* **PRIMARY ACTION** — *"`Continue`."*

## 4 · COGNITIVE LOAD (page 93)

*"The plan's own list, one Add button, and the only editable thing per row is how often
it lands."*

## 5 · STATES (page 93)

| state | drawn behaviour |
|---|---|
| **No charge codes exist** | *"Add is held, saying the catalogue is empty and where to fill it."* |
| **A code the catalogue no longer returns** | *"Kept on the plan, saved unchanged, and says it may have been deactivated — never silently dropped."* |
| **A base code with no amount** | *"Warns that those services would carry no base at all, and names them."* |

## 6 · WHAT THE SERVER NEEDS (page 93, verbatim)

*"A catalogue read, filtered. The Add button needs the charge codes this plan could
carry — narrowed to its customer class and its services. `applies_to_customer_classes`
is already stored and already served on a charge row, so the filter is expressible
today; what does not exist is an endpoint that takes a plan and answers with the codes
it may add."*

## 7 · COMPONENTS named in the frame (page 93)

`WizardFrame` `AttachedTable` `AddFromCatalogue` `SelectField`

## 8 · Absences — drawn as absent, do not fill them

* **No amount box.** **No taxable tick.**
* **No `Monthly base` block, no base total, no Σ of any kind on this step.**
* **No search box on this step's own panel** — the catalogue opens behind
  `+ Add a charge code`.
* **No second pane.**

---

## DIFF AGAINST THE RUNNING CODE — `2.234.19`

### Conforming

| drawn | code | evidence |
|---|---|---|
| the catalogue is NARROWED to this plan's class and services | `addableCharges(charges, draft, accountTypes)` — both halves | `PlanWizard.tsx:2892`, `PlanWizard.tsx:1233` |
| the count carries its denominator | `rating.plan.charges.narrowed` = *"Showing the {{shown}} of {{total}} charge codes this plan can carry."* | `PlanWizard.tsx:3011-3016` |
| no amount box | the override input is gone; the amount renders read-only from `charge.amount_display` | `PlanWizard.tsx:3113-3117` |
| no taxable tick on a new binding | `taxable: charge.taxable_default`, carried not offered | `PlanWizard.tsx:3033` |
| the "a plan cannot change an amount" sentence | `rating.plan.charges.noOverrideNote`, verbatim to the drawn note | `en.json` |
| **A code the catalogue no longer returns** state | `rating.plan.charges.unknownCode`, named never dropped | `PlanWizard.tsx:3070-3078` |
| **A base code with no amount** state | `servicesMissingBaseCharge` → `rating.plan.charges.missingBase`, naming the services | `PlanWizard.tsx:2880` |
| the `APPLIED` select's options | `Once` · `Every bill` · `On an event` | `en.json` `rating.plan.charges.recurrence.*` |
| `APPLIED` as the column word | `rating.plan.charges.recurrenceLabel` = *"Applied"* | `en.json` |

### Findings

1. **THE WHOLE LAYOUT IS THE OTHER ONE. The frame draws ONE attached table with ONE
   Add button; the code draws r10's TWO PANES.** `PlanWizard.tsx:2992-2993` opens
   `<div className="grid grid-cols-[1fr_340px] max-md:grid-cols-1 gap-6 items-start">`
   — catalogue on the left with a `Search charge codes` box
   (`PlanWizard.tsx:3018-3023`), a `+ Add` button on **every catalogue row**
   (`PlanWizard.tsx:3048-3058`), an `Added` marker on the taken ones
   (`PlanWizard.tsx:3044-3047`); and *"what is on the plan"* on the right
   (`PlanWizard.tsx:3062-3120`). **This is a drawing-versus-earlier-PO-ruling
   conflict, not a defect** — see CONTRADICTIONS.
2. **THERE IS NO `+ Add a charge code` BUTTON.** The code's add control is
   `rating.plan.charges.add` = **`+ Add`**, repeated once per catalogue row
   (`PlanWizard.tsx:3057`). The drawn button is one button, named for its object,
   which is B14 rule 4's `+ Noun` grammar.
3. **`Not listed? Define one →` READS DIFFERENTLY.** Code
   `rating.plan.charges.defineInCatalog` = *"Not listed? Define it in Charge codes →"*
   (`PlanWizard.tsx:3002-3004`), and it is a **secondary Button**, not the drawn link.
4. **THE `Monthly base` PANEL IS ON SCREEN AND THE FRAME DOES NOT DRAW IT.**
   `PlanWizard.tsx:2926-2990` renders a panel headed
   `rating.plan.charges.baseTitle` = *"Monthly base"* with `baseNote`, one `<dl>` row
   per service showing `{{amount}} · from {{code}}`, and a `Monthly base total` line
   or `monthlyTotalPending`. The drawn step 4 is one panel. The base's own home per
   the blueprint is the **review** (screen 36) — *"The bases now appear on the review"*
   (page 91) and *"THE BASE CHARGES AND THE DEPOSITS ARE BACK HERE"* (page 104).
5. **ROW REMOVAL IS A `×` GLYPH IN A GHOST-DANGER BUTTON, NOT THE DRAWN `Remove`
   LINK.** `PlanWizard.tsx:3110-3120`. The code's own comment records the reason and
   the gap honestly: **`components/icons.tsx` exports no close/× glyph**, so a
   character is used. **B14 rule 15 says row actions are ICONS with tooltips, never
   text links** — so the rule agrees with the code and the drawing loses here; but the
   glyph is not a kit icon, which is rule 36's *"compose the kit; where the kit lacks
   a piece, ADD IT TO THE KIT"*.
6. **THE STEP HEADING STILL NAMES THE BASE.** `rating.plan.charges.heading` =
   *"Confirm the base and add the charges this plan carries."* and
   `rating.plan.charges.title` = *"Charges & discounts"*. The drawn panel title is
   `Charges on this plan`, and the base is no longer confirmed here.
7. **THE `No charge codes exist` STATE DOES NOT HOLD THE ADD BUTTON.** The drawing
   says *"Add is held, saying the catalogue is empty and where to fill it."* In code
   there is no single Add button to hold; the empty case renders
   `rating.plan.charges.none` = *"No charge codes exist yet. Create them on the Charge
   codes tab."* as a note (`PlanWizard.tsx:3025`). The SENTENCE is right; the HOLD has
   nowhere to land because of finding 1.

---

## CONTRADICTIONS — recorded, not resolved

**THE TWO-PANE SHAPE IS ITSELF A PO RULING, AND IT IS NEWER THAN r10 AND OLDER THAN
THE BLUEPRINT.** `DEF-447` (2026-08-21) records the PO walking this wizard step by
step, verbatim: ***"Step 4 - you search and add - its search and add ; not select kind
of UI"***, and `CR-021` in `12-governance/11-change-requests.md:9644` records the
reading taken from it: *"The PO has asked for the two-pane search-and-add shape on
steps 4, 5 and 6 in one breath, and on step 4 it is uncontroversial."*

`CR-087` §0's own capture is compatible with either shape — *"user will need add more
button - they can select ad nad from the chagre code"* — and `CR-087` D2's done-when
sentence measures the FILTER, not the layout: *"`+ Add a charge code` on a residential
electric plan offers 6 codes, not the utility's 41."*

**So the drawing and a PO ruling disagree about the shape of steps 4, 5 and 6, and
both are the PO's.** One sentence settles it. Nothing is built from this lane.

**THE FOUR-DECIMAL MONEY IN THE FRAME.** `$45.0000` on this frame, and `$20.0000` on
screens 37, 38 and 39, contradict the blueprint's own RULES row on every one of those
pages and CLAUDE.md hard rule 2 (*display 2*). Read as a rule the frame loses; read as
B14 rule 37 the figure is an illustration and its DECIMAL COUNT is not a fact to build
to either. **Recorded so no lane "fixes" a two-decimal screen to match it.**
