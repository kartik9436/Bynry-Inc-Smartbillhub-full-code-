# EP-WRK-07 — Rules and doors: what raises an order without a person, the Assets door with four ways in, and the Customers door that is two calls from one wizard step

**Module:** work · **Wave:** phase **2** of `CR-070` · **Screens:** `Work-026` · `Work-028` · `Work-029` · `Work-020` · `Work-007` · **Status:** draft (`CR-070`, 2026-09-03; §15–§21 unread)

## Scope

**In:** `WM-24` the rules engine and the five-step rule builder · `WM-43` the Assets door · `WM-44` the Customers door.

**Out:** the orders these doors raise once raised (`EP-WRK-05`, `EP-WRK-06`).

**Why these three are one epic:** every one of them is a way an order comes to exist without a dispatcher typing it — a rule watching Payments, Billing, Assets, Reads or Accounts; a clerk on an asset; a clerk closing an account. **And every one writes through Work's own raise** (`create_work_order`, `US-WRK-002`), never through another module's table. `WS-26`'s caption: *"Proves the four disabled Assets checkboxes at WS-20 and this screen are the same feature."*

⚠ **`Work-026` IS THE RISKIEST SCREEN ON THE PAGE:** *"a rule that is on and wrong raises orders all night."* The *This month* column and the source stamp on every raised order are what make that visible and traceable — *"both are r10's own, not additions."*

## Capability matrix (list screens only — B9 conformance)

| Screen | Search fields | Filters | Default sort | Sortable | Columns default/available | Row actions | Bulk actions | Export |
|---|---|---|---|---|---|---|---|---|
| `Work-026` Rules | rule | source module · enabled | source module | Rule · Raised this month | Rule · Source module · Trigger · Template raised · Priority · This month · Enabled | ✎ · switch | — | — |

## Stories

---
id: US-WRK-037
epic: EP-WRK-07
module: work
screens: [Work-026, Work-007, Work-020]
wave: 2
status: ready
blocked_by: []
depends_on: [US-WRK-024, US-WRK-026, US-WRK-015]
journeys: [J63]
rules: [BR-WRK-033, BR-WRK-024]
golden_tests: []
finance_calc: none
---
### US-WRK-037 — Rules that raise work orders on their own: *Meter over 15 years → raise Meter exchange, Normal, unassigned*, and three orders appear overnight reading *Raised by: Asset age rule* (`WM-24`)

**1 · Details** — As **a utility**, I want **rules to watch the rest of SMARTBillHub and raise work orders**, so that **a final notice expiring unpaid, a payment clearing on a disconnected account, an unresolved billing exception, a meter past its certification life, a continuous-flow alarm or a completed occupancy wizard each becomes a job without a person typing it**.

`work_order_rules` plus the five-step builder: *Trigger · Assignment logic · Notifications · Reminders & escalation · Review & activate* (r10's `WRK-13`, a **sub-screen of `Work-026`**). `Work-026` lists seven rules, six on, with *This month* counts (96 · 88 · 203 · 184 · 42 · 127 · 18). Six of the seven fire from modules that already ship — *"which makes this the screen that decides how much of the product suddenly starts creating work."* The engine reads the source modules through the seams; it never subscribes by writing into them. ⚠ **`CR-070` §11 sends a lane to *"read WM-24 in full before writing the offline queue"* — that is a misaim (the offline queue is `WM-36`) and is filed as a defect draft; the trap it means is probably §16's and is unread.**

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-WRK-033` | A rule raises orders without a person; off raises nothing; source stamped; This month counted | CONFIRMED — `WM-24`, `WS-26` |
| `BR-WRK-024` | Every rule-raised order carries the rule | CONFIRMED |
| `BR-WRK-002` | The engine reads the six source modules through seams | CONFIRMED |
| `BR-WRK-008` | The raised order copies the named template | CONFIRMED |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Create *Meter over 15 years → raise Meter exchange — residential, Normal, unassigned*; run the nightly sweep against three qualifying meters | Three new orders on `Work-007` reading *Raised by: Asset age rule*, joining `WO-4822` and `WO-4830`; `rule_id` set; *This month* = 3 |
| TC-2 · **negative** | The same sweep the next night | **Zero** new orders — a rule is idempotent on (rule, subject, open order): a meter with an open exchange is not raised twice |
| TC-3 · **negative** | The rule switched *Off*, three more meters qualify | Nothing raised; *This month* unchanged |
| TC-4 · **negative** | A rule naming a template in `draft` | Refused at *Review & activate* — only a published template may be raised |
| TC-5 · **negative** | The engine's source for *Payment clears on a disconnected account* | Read through `payments_seam` (a new seam file, read-only); the boundary gate passes; a direct `Payment.objects` import fails it |
| TC-6 · **tenant isolation** | Lone Star Ridge's rules | Its own seven seeded rows, its own counts; a Brazos Bend rule never fires on Lone Star's meters |
| TC-7 | The four Assets checkboxes on `Work-020` | Stop being disabled and pre-tick the Assets door (`US-WRK-038`) — *"the same feature"* |

**4 · Test Data** — The seven rules of `WS-26`: Disconnect for non-pay · Payments · dunning · Final notice expires unpaid · Disconnect — non-payment · High · 96 · On · Reconnect after payment · Payments · Payment clears on a disconnected account · Reconnect after payment · Urgent · 88 · On · Read verification · Billing · Billing exception unresolved · Read verification · Normal · 203 · On · Meter exchange programme · Assets · Meter past certification life · Meter exchange — residential · Normal · 184 · On · Leak investigation · Reads · AMI · Continuous-flow alarm · Leak investigation · High · 42 · On · Move-in / move-out · Accounts · Occupancy wizard completes · Move-in activation · Normal · 127 · On · Backflow test due · Assets · lifecycle · Certification due within 30 days · Backflow inspection · Low · 18 · **Off**.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| rule | `Work-026` | `WM-24` | `work_order_rules` (name · source_module ∈ {payments, billing, assets, reads, accounts} · trigger_kind · trigger_params jsonb · template_id · priority_id · assignment ∈ {unassigned, technician, crew} · assignee · notifications jsonb · escalation jsonb · enabled · raised_this_month (computed)) | row | user-input | template published; source module one of the five |
| the sweep | — | `WM-24` | `jobs.kind = work.rules_sweep`, nightly, queue `work` | job | system | idempotent per (rule, subject) |
| source stamp | `Work-007` | `WM-24` | `work_orders.source = rule`, `.rule_id` | — | system | `BR-WRK-024` |

**6 · Acceptance** — **Given** the asset-age rule is on, **when** the nightly sweep finds three meters past their certification life, **then** three exchange orders appear naming the rule — **and** the same sweep the next night raises nothing new.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None. (Whether a rule may ASSIGN as well as raise is drawn — *Assignment logic* — and built as drawn; a rule that assigns writes an `assign` row like a dispatcher does.)

---
id: US-WRK-038
epic: EP-WRK-07
module: work
screens: [Work-028, Work-020]
wave: 2
status: ready
blocked_by: []
depends_on: [US-WRK-001, US-WRK-014]
journeys: [J63]
rules: [BR-WRK-056]
golden_tests: []
finance_calc: none
---
### US-WRK-038 — The Assets door: one form, four ways in — and the Maintenance history's Work order column stops being a dash (`WM-43`)

**1 · Details** — As **a clerk on `AST-04412`**, I want **to press *Raise work order*, pick *Meter exchange — residential*, and see `WO-4908` in the dispatcher unassigned**, so that **the Maintenance history's Work order column, a dash on every row today, reads `WO-4908`**.

`Work-028` at `/{tenant}/assets/AST-04412/work-orders/new` — *"a sibling of the shipped `…/maintenance/new` (S53 · AST-07), so it needs no new navigation pattern and no new shell."* THIS ASSET · THE JOB (Template filtered to *applies to asset types* · Priority · Due · Assign to *Leave unassigned — the dispatcher will place it* · Reason) · **What this writes**: *One `work_orders` row, not connected to a build — `connection_id` is null · `work_orders.asset_id = AST-04412` — the column already exists and nothing writes it today · The Maintenance history Work order column stops being a dash.* **Four doors, one form:** the action bar · the Maintenance history panel · the four `RaiseWorkOrderCheckbox` ticks on Asset add, reassign/move, log maintenance and retire/replacement (`Work-020`), which stop being disabled and post this form on save. ⚠ **`DEF-WRK-4125`, 2026-09-06:** this said *three `WorkOrderR5Checkbox` controls* and named add, retire/exchange and move — while `10-execution-plan.md` §271 said three and named add, move and **maintenance**. Two documents, two different threes, and the code has four.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-WRK-056` | One form, four ways in; writes `asset_id`; templates filtered by asset type | CONFIRMED — `WM-43` |
| `BR-WRK-006` | An asset is an anchor | PROPOSED |
| `BR-WRK-002` | Assets calls Work's raise from the SCREEN; Assets writes nothing to `work_orders` and Work writes nothing to `assets` | CONFIRMED |
| B14 rule 11 | *What this writes* is the consequence box | CONFIRMED |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | On `AST-04412`, *Raise work order*, *Meter exchange — residential*, Normal, due Mar 31, unassigned, reason *Certification life ends. Programmed exchange.* | `WO-4908` on `Work-007` unassigned, source *Assets*; `asset_id = AST-04412`; `connection_id` NULL; Maintenance history's Work order column reads `WO-4908` for that asset |
| TC-2 | The template picker | Lists only templates whose `wot_asset_types` includes *Electric meter · 1φ AMI* |
| TC-3 · **negative** | Asset add with the *Raise an installation work order* box ticked, then the add fails validation | No order — the two writes are one screen transaction: the asset first, then the raise, and a failed asset save raises nothing |
| TC-4 · **negative** | grep `apps/assets/**` for `work_orders` writes | Zero — the door is the screen calling `POST /work-orders` |
| TC-5 · **negative** | The maintenance-history column when an asset has maintenance rows and no order | Still a dash, honestly (`WS-20`) |
| TC-6 · **tenant isolation** | Lone Star Ridge opens `/assets/AST-04412/work-orders/new` | `404` |
| TC-7 · **UI law** | The three checkboxes | Enabled; their *Work R5* note gone; the route pattern matches `AST-07`'s |

**4 · Test Data** — `AST-04412` · Electric meter · 1φ AMI · installed Mar 2021 · `221 Oak Ave · Unit 3` · account `A-10688` · Electric · *Certification life ends Mar 2026*. Maintenance history: 12 Feb 2026 Inspection R. Patel Annual inspection — 42.00 Passed · 04 Nov 2025 Repair D. Ortiz Register replaced — 118.00 Passed.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| asset | `Work-028` | `WM-43` | `work_orders.asset_id` (exists, migrated, RLS-scoped, written by nothing) | uuid | system from the route | — |
| template filter | `Work-028` | `WM-43` | `wot_asset_types` ∩ the asset's type via `assets_seam` | list | computed | — |
| reason | `Work-028` | `WS-28` | `work_orders.detail` (the existing *"because"* column) | text | user-input | one sentence |
| the column | Asset detail › Maintenance history | `WS-20` | read: the latest `work_orders` row with this `asset_id` — `[the Assets design's §10-D7 asks for a column on maintenance history to hold the reference; §16 unread; this story reads rather than adds]` | — | computed-display | — |

**6 · Acceptance** — **Given** a meter at the end of its certification life, **when** a clerk raises an exchange from the asset, **then** the order is in the dispatcher with the asset on it and the asset's history names the order.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---
id: US-WRK-039
epic: EP-WRK-07
module: work
screens: [Work-029]
wave: 2
status: ready
blocked_by: []
depends_on: [US-WRK-001, US-WRK-024]
journeys: [J64]
rules: [BR-WRK-055]
golden_tests: []
finance_calc: none
---
### US-WRK-039 — The Customers door: a move-out's field visit is two calls from one wizard step, never a cross-module write (`WM-44`)

**1 · Details** — As **a clerk completing a move-out on `A-10688`**, I want **to tick *Raise a work order for the final read* and have the account close and settle as it does today while `WO-4910` arrives in the dispatcher stamped *Move-out · A-10688***, so that **the close never waits for the visit and the visit never closes the account**.

`Work-029`, step 4 of 6 of the move-out wizard — **Does somebody have to attend?** ☑ *Raise a work order for the final read — Electric · Final read & deactivate · due 28 Mar 2026* (drawn *de-energise*; `CR-032`, TC-7) · ☐ *Raise a work order to lock the water curb stop* · ☐ ***No visit needed — the customer will send a photo of the meter***. **WHAT HAPPENS ON SAVE:** *1 Close the account, settle the deposit, cut the final bill — Customers — as today · 2 The screen calls metering to raise the work order — Work — WO-4910 · Queued · unassigned · 3 The order carries its source — Work — Move-out · A-10688.* `apps/customers/disconnects.py` refuses the cross-module version under `VISIT_NOT_SCHEDULED` *"in its own words"* — the predecessor lane counted **one constant, one payload site and two docstring mentions, not four refusals**; the design it names is the same. The same step serves disconnect and reconnect. ⚠ **ONE WORD, NOT TWO:** the requirement said *service order*; the product calls it a work order, on the same table, in the same dispatcher — nothing here mints a second entity, and `SR-{YY}-{0000}` stays a customer's request. ⚠ **AND *de-energise* IN THE DRAWN COPY BECOMES *deactivate*** (`CR-032`).

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-WRK-055` | Two calls from one step; Customers writes nothing to `work_orders`; the close does not wait; *No visit needed* is recorded | CONFIRMED — `WM-44`, `disconnects.py` |
| `BR-WRK-024` | Source *Move-out · A-10688* | CONFIRMED |
| `BR-WRK-003` | The final read, when it arrives, posts through the same approval path (`Work-009` → the meter's history) | CONFIRMED |
| `CR-032` | *activated / deactivated*, never *energise* | CONFIRMED |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Move-out on `A-10688`, final-read box ticked, complete step 6 | The account closes and settles exactly as today; `WO-4910` Queued · unassigned · source *Move-out · A-10688* · `account_id = A-10688` · `connection_id` NULL |
| TC-2 · **negative** | The raise fails (Work is down) | **The move-out still completes**; the step reports the visit was not raised and offers to raise it from the dispatcher — the close does not wait for the visit |
| TC-3 · **negative** | The visit's final read arrives and is accepted | The account is **not** re-opened, re-closed or re-settled; the read posts to the meter's history; a final-bill true-up is billing's existing behaviour, untouched here |
| TC-4 | *No visit needed* ticked | A recorded choice on the move-out — `field_visit = not_needed` — so nobody can mistake a move-out nobody attended for one nobody decided |
| TC-5 · **negative** | grep `apps/customers/**` for `WorkOrder.objects` | Zero; `VISIT_NOT_SCHEDULED` stays as the refusal for any path that is not the screen |
| TC-6 · **tenant isolation** | Lone Star Ridge's move-out | Raises on Lone Star's tenant only |
| TC-7 · **copy** | The step's copy | *Final read & deactivate*, not *de-energise*; one sentence per section; no id |

**4 · Test Data** — `A-10688` · Miller, Sarah · `221 Oak Ave · Unit 3` · Electric · move-out 28 Mar 2026. **`WO-4910`** (⚠ the blueprint's `WO-4907` is the gas light-up on `CON-26-0117` in §9 and §12; the fixture gives the move-out visit `WO-4910`, recorded in `03-field-map.md` D-8 — and until 2026-09-03 this story's own §1 and TC-1 still said `WO-4907`, `DEF-WRK-3575`). **The template the visit is raised from (2026-09-03, `DEF-WRK-3578`):** no card and no wireframe names one — `Work-029`'s label *Final read & deactivate* describes the VISIT and is neither a type in the catalogue nor a template on `Work-013`. The raise goes through the job type's `default_template_id` (`BR-WRK-017`'s shape — the same door `Work-018`'s *Backflow test · default template Backflow inspection* uses): the final-read tick raises with job type **Read verification**, whose default template on the fixture is **`Final read — electric`** (Electric · 1 task *Record the final read · 5 min · photo Required* · 1 reading *Final read · kWh · 0–99,999 · photo Required · required · posts as meter read: Yes* · est. 15 min · skill Reads) — `J64`'s fixture, now this story's. The curb-stop tick's type is named by no card, is ticked in no journey, and is stated as unstated rather than guessed.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| field visit choice | `Work-029` | `WM-44` | `disconnect_cases.field_visit ∈ {final_read, curb_stop, not_needed}` — **Customers owns the write** (its own wizard's record) `[our column; §16 unread]` | enum | user-input | required at step 4 |
| the order | `Work-007` | `WM-44` | `POST /work-orders` from the screen with `account_id`, `source = move_out` | — | system | Work's own raise |

**6 · Acceptance** — **Given** a move-out with the final-read box ticked, **when** the clerk completes it, **then** the account closes as today and a queued order stamped *Move-out · A-10688* is in the dispatcher — **and** if the raise fails, the close still completes and says so.

**7 · Finance Calculation** — N/A — the settlement and the final bill are Customers' and Billing's existing arithmetic, untouched.

**8 · Open Questions** — None.
