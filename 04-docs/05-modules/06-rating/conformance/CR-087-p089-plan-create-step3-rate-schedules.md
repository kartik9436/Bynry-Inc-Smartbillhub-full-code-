# Plans 31 · Create · Step 3 · Rate schedules — THE DRAWN SPEC

`PLN-03 step 3` · route `/:tenant/plans-rates/plans/new` · **blueprint pages 89–91**

**Source:** `05-prototype/SMARTBillHub Plans & Rates Blueprint.pdf`, screen `31`,
frame drawn on page 90, specified on 90–91.

**State chip:** `NEW BUILD`
**Commitments on the chip line:** `PRB-18`

**WHAT WAS WRONG (page 90, verbatim):** *"A read-only Base charge column showed one
base per service where a service can have several, and a service left with no rate
schedule was only refused five screens later."*

---

## 1 · Wizard chrome

As step 1, with `3 Rate schedules` active. Footer `Continue`.

## 2 · The one panel — `One schedule per service`

| slot | drawn |
|---|---|
| panel title | `One schedule per service` |
| table | THREE columns |

| # | header | alignment | drawn cell |
|---|---|---|---|
| 1 | `SERVICE` | left | `Electric` · `Water` — the service NAME as plain text |
| 2 | `RATE SCHEDULE` | left | a SELECT: `Residential Electric — TOU · 41 accounts`, and on the unbound row the placeholder `Choose a rate schedule` |
| 3 | `GL` | left-set in the frame, sitting at the right of the table | `4100-02` · `4100-01` |

**Under the table, in order:**

1. a refusal, accent rule, red:
   `Water has no rate schedule. Every service needs one before this plan can be published.`
2. a quiet note, grey rule:
   `A plan cannot carry a second schedule for the same service — different pricing means a different plan.`

⚠ **B14 rule 37 — `Residential Electric — TOU`, `41 accounts`, `4100-02` and `4100-01`
are ILLUSTRATIONS.** The SHAPE is: the schedule option carries its structure and its
account count so a clerk picks by recognising the tariff rather than by name alone.

**WHAT CHANGED · THE BASE CHARGE HAS LEFT THIS STEP (page 91, verbatim):**
*"It showed ONE base charge per service and a service can have several — a base is
picked by charge code, and the code can differ by customer class and by connection
size, so Electric · $12.0000 from BASE-E was one row's answer printed as if it were
the service's. Nothing is chosen here anyway: the column was read-only. The bases now
appear on the **review**, where every one that applies can be listed against the
service it belongs to."*

**WHAT CHANGED · AN EMPTY ROW WALKED TO STEP 8 (page 91, verbatim):** *"Nothing on this
step refused it; the refusal — every service needs a rate schedule — arrived five
screens later on the final press. It is checked here, named by service, where the
choice is made. A clerk may still leave and save a draft; what has gone is discovering
it at the end."*

## 3 · FOR · HOW YOU GET HERE · PRIMARY ACTION (pages 90–91)

* **FOR** — *"The clerk joining the plan to the prices."*
* **HOW YOU GET HERE** — *"Continue from Services."*
* **PRIMARY ACTION** — *"`Continue`."*

## 4 · COGNITIVE LOAD (page 91)

*"A row per service, three columns, one of them a choice. The schedule options carry
their structure and account count, so a clerk picks by recognising the tariff rather
than by name alone."*

## 5 · STATES (page 91)

| state | drawn behaviour |
|---|---|
| **A schedule for another class** | *"The row warns that bills priced by it may not match what this plan's customers were offered."* |
| **No schedule exists** | *"A link to create one, which returns here with the row still filled."* |
| **No services yet** | *"Pick the services first; each one then gets its own rate schedule here."* |

## 6 · COMPONENTS named in the frame (page 91)

`WizardFrame` `BindingTable` `SelectField` `InlineCheck`

## 7 · Absences — drawn as absent, do not fill them

* **No `BASE CHARGE` column**, in any form — read-only, attributed or otherwise.
* **No `+ Add alternate schedule for a service…`.**
* **No minimum, per service or per plan, anywhere on this step.**
* **No fourth column.**

---

## DIFF AGAINST THE RUNNING CODE — `2.234.19`

### Conforming

| drawn | code | evidence |
|---|---|---|
| panel is a table, THREE columns | `<thead>` renders `rating.filter.service` · `rating.plan.scheduleLabel` · `rating.plan.schedules.colGl` | `PlanWizard.tsx:2657-2672` |
| the base column is GONE | no `colBase` in the `<thead>`; the key `rating.plan.schedules.colBase` survives in the catalogue, referenced by nothing | `PlanWizard.tsx:2657-2672`; `en.json` |
| the schedule option carries structure + account count | `rating.plan.scheduleOption` built from `card.structure` and `card.applied_to_accounts` — the SERVER's count, nothing derived | `PlanWizard.tsx:2683-2692` |
| Continue is refused on this step | `validate: () => servicesWithoutSchedule(draft).length === 0` | `PlanWizard.tsx:1580` |
| the refusal names the services | `everyServiceNeedsOne` + the service names joined | `PlanWizard.tsx:2775-2780` |
| the second-schedule note | `rating.plan.schedules.noAlternates` = *"One rate schedule per service. A plan cannot carry a second schedule for the same service — different pricing means a different plan."* | `PlanWizard.tsx:2785` |
| **No services yet** state, verbatim | `rating.plan.schedules.pickServicesFirst` = *"Pick the services first; each one then gets its own rate schedule here."* | `PlanWizard.tsx:2643` |
| **A schedule for another class** state | `schedulesWithForeignClass` → `rating.plan.schedules.foreignClass` | `PlanWizard.tsx:2625`, `en.json` |
| **No schedule exists** state | `newScheduleHint` + the step-2 create link | `PlanWizard.tsx:2786` |

### Findings

1. **A WHOLE SECOND PANEL IS ON SCREEN THAT THE FRAME DOES NOT DRAW: `Minimum per
   service`.** `PlanWizard.tsx:2795-2814` renders a panel headed
   `rating.plan.schedules.minimumsTitle` = *"Minimum per service"* with one numeric
   `TextField` per service. The drawn step 3 has **one** panel and **no** money field
   of any kind. The code's own comment (`PlanWizard.tsx:2789-2794`) states the reason:
   `BR-RAT-028` mode (A) ratifies per-service minimums and *"dropping it to match the
   drawing would delete a ratified capability"*. **Drawing-vs-rule; recorded, not
   resolved** — see FOR THE PRODUCT OWNER.
2. **THE GL COLUMN IS RIGHT-ALIGNED IN CODE AND SET LEFT IN THE FRAME.**
   `PlanWizard.tsx:2669` gives the `<th>` `text-right`. The frame draws `4100-02` and
   `4100-01` left-set within a column at the table's right edge. A GL code is a CODE,
   not a figure, and the blueprint's own RULES row says a code is *"a printed
   reference"*; B14 has no rule that settles alignment for a code column. Minor;
   recorded because column alignment is part of §4's comparison.
3. **TWO EXTRA LINES SIT BETWEEN THE TABLE AND THE REFUSAL.**
   `PlanWizard.tsx:2764-2770` renders `rating.gl.editedInSettings` plus an
   `Open settings` link. The frame draws nothing between the table and the refusal.
   B14 rule 32's budget again — the panel now carries four sentences.
4. **THE `SERVICE` CELL DRAWS THE COLOURED BADGE; THE FRAME DRAWS THE NAME.**
   `PlanWizard.tsx:2678-2680` puts r10's service badge in the first cell. The frame
   for THIS step prints `Electric` and `Water` as plain text (contrast screen 38,
   page 111, which draws the badge and says so in as many words). Recorded as a
   frame-to-frame difference rather than a defect: the Units frame's own note —
   *"the same 20-pixel square r10 drew and the plan list already uses, so a service
   looks the same wherever a clerk meets it"* — argues the badge is right, and the
   blueprint contradicts itself between two of its own frames.

### Divergences recorded under B14 rule 38 — the UI rules win, nothing is built

* **The drawn refusal is fourteen words.** B14 rule 33 caps it at five or six. The code
  splits it — a six-word sentence plus a NAME LIST, which the code's own comment
  argues is not a sentence and does not count against the cap
  (`PlanWizard.tsx:2771-2774`). Rule wins; the drawn sentence is not built.

---

## FOR THE PRODUCT OWNER

**The drawn step 3 has no minimum field and the product has one per service.**
`BR-RAT-028` mode (A) ratifies per-service minimums — they apply first, then the plan
floor tops the total up — and it is a FLOOR rather than a price, which is why
`BR-RAT-088` did not move it onto the charge code with the base. The blueprint removed
the BASE column on 2026-09-08 and is silent about the minimum. **Two readings and only
one sentence is needed:** the minimum stays where it is and the drawing is incomplete,
or the minimum moves with the base. Nothing is built either way from this lane.
