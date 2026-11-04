# EP-WRK-05 — Dispatch: twelve columns, an append-only assignment, one list with six filters, the dispatcher with bulk actions, the New order wizard, the map, the push, and the edit screen

**Module:** work · **Wave:** phase **2** of `CR-070` · **Screens:** `Work-007` · `Work-002` · `Work-008` · `Work-010` · `Work-021` · **Status:** draft (`CR-070`, 2026-09-03; §15–§21 unread)

## Scope

**In:** `WM-14` the dispatch columns · `WM-15` assignment as history · `WM-16` one list, six filters · `WM-17` the dispatcher with bulk actions · `WM-20` the three-step New order wizard · `WM-23` the map · `WM-37` push to the phone on assignment · `WM-39` the edit screen — assign, reschedule, cancel.

**Out:** the order's own copies and the six tabs (`EP-WRK-06`) · rules that raise orders (`EP-WRK-07`) · what the phone does with a pushed job (`EP-WRK-08`).

**Blueprint §6:** *"One place to see every work order and drive it from assignment to completion to approval… The last two stages are built and work well. The first three do not exist, and neither does the list they would be shown in."* And the reason it could not start until today: the placement ruling. **Unblocked 2026-09-03.**

⚠ **`WM-01` GATES EVERYTHING HERE** — the dispatcher is worthless over orders that must belong to a build. `US-WRK-001` is phase 0 for that reason.

## Capability matrix (list screens only — B9 conformance)

| Screen | Search fields | Filters | Default sort | Sortable | Columns default/available | Row actions | Bulk actions | Export |
|---|---|---|---|---|---|---|---|---|
| `Work-007` Orders — the dispatcher | *Search WO #, premise…* | Type · Status · Priority · Technician · Area (six with search) | priority rank, then due time | Order · Type · Priority · Due · Status · Technician | ☐ · Order · Type · Premise · Svc · Priority · Technician · Due · Status · Raised by | 👁 · ✓ assign · ✎ | *Assign selected…* · *Reschedule selected…* · *Change priority…* | ↓ (IS-9) |

## Stories

---
id: US-WRK-024
epic: EP-WRK-05
module: work
screens: [Work-007, Work-002]
wave: 2
status: ready
blocked_by: []
depends_on: [US-WRK-001, US-WRK-007, US-WRK-008, US-WRK-020]
journeys: [J62]
rules: [BR-WRK-023, BR-WRK-024]
golden_tests: []
finance_calc: none
---
### US-WRK-024 — The twelve dispatch columns on a work order, kept apart from *state* (`WM-14`)

**1 · Details** — As **a dispatcher**, I want **Priority, Technician, Due and Status to hold real values on every open order**, so that **`Work-007` shows `WO-4824 · Urgent · M. Chen · Today 12:00 · On site` instead of dashes**.

*"Twelve columns: priority, due, appointment window, dispatch state, source, rule, assignee, assignment stamps, estimated duration. Kept separate from `state`, which means has the work happened."* Today *"only `completed_at` exists — a record of the past, never a plan"*, and the built states *planned · in_progress · blocked · completed · cancelled* express nothing of Scheduled, En route or On site.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-WRK-023` | Dispatch state is a third axis: Queued · Scheduled · En route · On site · Complete · On hold · Cancelled | CONFIRMED — `WM-14` |
| `BR-WRK-024` | Every order carries its source; a rule-raised order stamps the rule | CONFIRMED |
| `BR-WRK-018` | `due_at` defaults to raise + SLA | CONFIRMED |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Raise `WO-4824` Reconnect, Urgent, source *Payment received* | `dispatch_state = queued`, `priority` Urgent, `due_at` raise + 4 h, `source = payment_received`, assignee NULL |
| TC-2 | Assign to M. Chen for today 12:00 (via `US-WRK-025`) | `dispatch_state = scheduled`; `state` still `planned` — two axes |
| TC-3 · **negative** | Set `dispatch_state = on_site` on an order whose `state = completed` | Refused — a finished job has nowhere to be |
| TC-4 · **negative** | Raise with `source` blank | Refused — every order says why it exists; the New order wizard stamps *Dispatcher* |
| TC-5 · **tenant isolation** | Lone Star Ridge reads `WO-4824` | `404` |
| TC-6 | The existing seven `CON-26-0117` orders after the migration | `dispatch_state` back-filled: `completed` state → `complete`; `planned` → `queued`; `source = new_connect`; nothing else invented |
| TC-7 | `Work-002` | Gains Priority · Technician · Due · Status columns beside the existing ones; the `is_gate` flag and `blocked_by` unchanged |

**4 · Test Data** — The ten open orders of `WS-07`: `WO-4824` Reconnect · `903 Birch Ln · A-10222` · E · Urgent · M. Chen · Today 12:00 · On site · Payment received · `WO-4828` Main repair · Elm St & 3rd — network · W · Urgent · Crew B · Today · On site · Dispatcher · `WO-4821` Disconnect · non-pay · `1408 Elm St · A-10432` · W · High · D. Ortiz · Today 14:00 · En route · Dunning · auto · `WO-4823` Leak investigation · `77 Cedar Ct · A-10891` · W · High · Unassigned · Today 17:00 · Queued · High-usage alert · `WO-4822` Meter exchange · `221 Oak Ave · A-10688` · E · Normal · D. Ortiz · Today 15:30 · Scheduled · Asset age rule · `WO-4827` Backflow inspection · `500 Commerce Pk · A-20114` · W · Normal · R. Patel · Aug 19 · Scheduled · Compliance calendar · `WO-4830` Meter exchange · `88 Willow · A-10901` · E · Normal · Unassigned · Aug 19 · Queued · Asset age rule · `WO-4825` Read verification · `14 Pine Row · A-10514` · W · Low · Unassigned · Aug 18 · Queued · Billing exception (eight shown of ten).

**5 · Data Fields / Mapping** `[from cards only — §16 unread; the card counts twelve and names nine groups; the columns below are how we spell them]`

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| priority | `Work-007` | `WM-14` | `work_orders.priority_id` FK → `work_priorities` | uuid | user-input / type default | required |
| due | `Work-007` | `WM-14` | `work_orders.due_at` | timestamptz | derived / user-input | `BR-WRK-018` |
| appointment window | `Work-021` | `WM-14` | `work_orders.window_start`, `.window_end` | timestamptz NULL ×2 | user-input | *Any time* leaves both NULL; the four r10 choices |
| dispatch state | `Work-007` | `WM-14` | `work_orders.dispatch_state` | enum, seven | system-derived | `BR-WRK-023` |
| source · rule | `Work-007` | `WM-14` | `work_orders.source` enum · `.rule_id` FK NULL → `work_order_rules` | enum · uuid | system | `BR-WRK-024` |
| assignee | `Work-007` | `WM-14` | `work_orders.assignee_technician_id` FK NULL · `.assignee_crew_id` FK NULL | uuid | derived from the latest assignment row | exactly one or neither |
| assignment stamps | `Work-008` Audit | `WM-14` | `work_orders.assigned_at`, `.assigned_by` | timestamptz · uuid | derived from the latest assignment row | a cache; the history is `work_order_assignments` |
| estimated duration | `Work-007` | `WM-14` | `work_orders.est_duration` | interval | copied from the template at raise | its own unit |
| area | `Work-007` | `WM-28` | `work_orders.area_id` | uuid | `US-WRK-011` | — |

**6 · Acceptance** — **Given** ten open orders, **when** `Work-007` loads, **then** Priority, Technician, Due and Status carry real values on every row and `WO-4824` reads *Urgent · M. Chen · Today 12:00 · On site*.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---
id: US-WRK-025
epic: EP-WRK-05
module: work
screens: [Work-007, Work-008]
wave: 2
status: ready
blocked_by: []
depends_on: [US-WRK-024]
journeys: [J62]
rules: [BR-WRK-025, BR-WRK-029]
golden_tests: []
finance_calc: none
---
### US-WRK-025 — Assignment as an append-only history: assign, unassign, schedule, depart, arrive — never an UPDATE (`WM-15`)

**1 · Details** — As **a dispatcher**, I want **assigning `WO-4823` to D. Ortiz for tomorrow 09:00 to move it Queued → Scheduled, drop the Unassigned tile from 4 to 3, and write *Assigned to D. Ortiz by M. Torres* on the Audit tab**, so that **who was sent where, and when, is never overwritten**.

`work_order_assignments` plus five acts. *"Never an UPDATE."* The order's `assignee_*` and `assigned_*` columns are a cache of the latest row (`US-WRK-024`).

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-WRK-025` | Append-only history; five acts; never an UPDATE | CONFIRMED — `WM-15` |
| `BR-WRK-029` | Only a skill match may be assigned | CONFIRMED |
| CLAUDE.md hard rule 7's shape | Every act writes its audit row | CONFIRMED |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Assign `WO-4823` to D. Ortiz, tomorrow 09:00 | One `assign` row; `dispatch_state` Queued → Scheduled; the Unassigned tile 4 → 3; Audit reads *Assigned to D. Ortiz by M. Torres* |
| TC-2 | Reassign to R. Patel | An `unassign` row **and** an `assign` row — two rows, the first never touched |
| TC-3 · **negative** | Assign a meter-exchange order to R. Patel (no Meter fitting) | Refused naming the skill; ≤ 6 words |
| TC-4 · **negative · PostgreSQL** | `UPDATE work_order_assignments SET technician_id = … WHERE id = …` | Refused by trigger — append-only (hard rule 4's shape, on a Work table by our choice) |
| TC-5 | `depart`, then `arrive` from the phone | Two rows; `dispatch_state` En route → On site; `arrived_at` is what the report's *On site 15:15* reads |
| TC-6 · **tenant isolation** | Lone Star Ridge posts an assignment on a Brazos Bend order | `404` |
| TC-7 | Unassign only | An `unassign` row; `dispatch_state` back to Queued; the tile 3 → 4 |

**4 · Test Data** — `WO-4823` Leak investigation · Queued · Unassigned. D. Ortiz (Water II · Meter I), R. Patel (Water I · Reads). Tiles: UNASSIGNED **4** · DUE TODAY **5** (2 urgent) · IN THE FIELD **2** · AWAITING APPROVAL **3** · OVERDUE **1** (`WO-4823 · 2 days`).

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| assignment row | `Work-008` Audit | `WM-15` | `work_order_assignments` (work_order_id · act ∈ {assign, unassign, schedule, depart, arrive} · technician_id NULL · crew_id NULL · scheduled_for NULL · window_start/end NULL · actor_id · at) | rows | system | append-only trigger; one of technician/crew on `assign` |
| the acts | — | `WM-15` | `POST /work-orders/{id}/assignments` with `act` | — | user-input / phone | `depart` and `arrive` only from the assignee |

**6 · Acceptance** — **Given** `WO-4823` is queued, **when** it is assigned, **then** a history row is written, the state moves, the tile drops and the audit names both people — **and** no row in that table is ever updated.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---
id: US-WRK-026
epic: EP-WRK-05
module: work
screens: [Work-007]
wave: 2
status: ready
blocked_by: []
depends_on: [US-WRK-024]
journeys: [J62]
rules: [BR-WRK-026]
golden_tests: []
finance_calc: none
---
### US-WRK-026 — One list of every work order, with six filters (`WM-16`)

**1 · Details** — As **a dispatcher**, I want **`GET /work-orders` filtered by search, type, status, priority, technician and area**, so that **Status = Queued and Priority = High leaves exactly `WO-4823` and the footer reads *Showing 1 of 10 open orders***.

Today *"orders are listed only inside one connection's Work orders tab. No cross-connection list and no endpoint that would serve one."*

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-WRK-026` | Exactly six filters; the footer states the count | CONFIRMED — `WM-16` |
| `BR-WRK-022` | Area from `tenancy.Area` | CONFIRMED |
| B14 rules 12, 13, 16, 19 | Toolbar · sort cycles · footer · *Search WO #, premise…* placeholder (`G43`) | CONFIRMED |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Status = Queued, Priority = High | `WO-4823` alone; *Showing 1 of 10 open orders* |
| TC-2 | Search `A-10688` | `WO-4822` — the search covers order number, premise and account |
| TC-3 · **negative** | A seventh filter parameter `?service=` | Ignored with a `400` naming the six — the count is a rule, not a habit |
| TC-4 · **negative** | `?status=` with an unknown value | `400`; the sentence names the seven states |
| TC-5 · **tenant isolation** | Lone Star Ridge with no filters | Its own orders only |
| TC-6 | Default | Open orders (not Complete · Cancelled) sorted by priority rank then due; *Showing 8 of 10 open orders · 1–8 of 10*; page size remembered per table (B14 rule 16) |
| TC-7 | An order with no connection | Listed — the whole point of `US-WRK-001` |

**4 · Test Data** — The ten open orders of `US-WRK-024`.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| the six filters | `Work-007` | `WM-16` | `GET /work-orders?q=&type=&status=&priority=&technician=&area=` | query | user-input | each resolved under RLS |
| footer | `Work-007` | `WS-07` | `total`, `page`, `page_size` | ints | computed-display | `ListPager` |

**6 · Acceptance** — **Given** ten open orders, **when** two filters are set, **then** one row remains and the footer says *1 of 10*.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---
id: US-WRK-027
epic: EP-WRK-05
module: work
screens: [Work-007]
wave: 2
status: ready
blocked_by: []
depends_on: [US-WRK-026, US-WRK-025, US-WRK-004]
journeys: [J62]
rules: [BR-WRK-027]
golden_tests: []
finance_calc: none
---
### US-WRK-027 — The dispatcher screen: the KPI strip, the filter bar, the ten-column table and bulk select (`WM-17`)

**1 · Details** — As **a dispatcher**, I want **to tick the three Queued rows, read *3 selected*, press *Assign* and pick R. Patel**, so that **`WO-4823`, `WO-4830` and `WO-4825` all move to Scheduled with R. Patel named on each**.

`Work-007` at `/{tenant}/work/orders` — **the shell `Work-006` becomes.** Sub-navigation `Orders Map Crews Parts Templates Rules` (plus *Awaiting approval* and *Performance* where drawn). Five KPI tiles: UNASSIGNED 4 · DUE TODAY 5 (*2 of them urgent*) · IN THE FIELD 2 · AWAITING APPROVAL 3 · OVERDUE 1 (*WO-4823 · 2 days*). Footer buttons: *+ New work order* · *Assign selected…* · *Reschedule selected…* · *Change priority…*. *"Raised by is the one nobody asks for until it is missing."*

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-WRK-027` | Bulk Assign · Reschedule · Change priority; one row per order | CONFIRMED — `WM-17` |
| `BR-WRK-029` | The bulk assign refuses the rows that do not match | CONFIRMED |
| B14 rules 2, 4, 12, 15, 16, 21 | One page header · `+ New work order` opens a creator · toolbar · icon row actions (⚡ ✓ 👁) · footer · Tailwind on the migrated list | CONFIRMED |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Tick the three Queued rows, *Assign selected…*, R. Patel | A bar reads *3 selected*; three `assign` rows; all three Scheduled with R. Patel |
| TC-2 · **negative** | Tick `WO-4830` (Meter exchange) among them and R. Patel lacks Meter fitting | The two matching rows assign; `WO-4830` is refused **by name** in the result and stays Queued — never all-or-nothing silently, never a partial nobody is told about |
| TC-3 | *Reschedule selected…* to Aug 20 | One `schedule` row per order; each Audit tab names the dispatcher |
| TC-4 · **negative** | *Change priority…* on a Complete order | Refused — priority is a promise about work not yet done |
| TC-5 · **tenant isolation** | Lone Star Ridge's tiles | Its own counts; zero when it has no orders, drawn as zeros not blanks |
| TC-6 | The KPI strip | Five tiles, each a `KpiTile`, each qualifier ≤ 6 words (B14 rule 33) |
| TC-7 · **UI law** | `features/work/orders/**` | On `route-b-migrated.txt`; row actions are icons with tooltips; no `WS-`/`WM-`/`BR-` in rendered copy |

**4 · Test Data** — As `US-WRK-024`; tiles as `US-WRK-025`.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| tiles | `Work-007` | `WS-07` | `GET /work/kpis` | five counts + one reference | computed-display | recomputed per load |
| bulk | `Work-007` | `WM-17` | `POST /work-orders/bulk` with `act ∈ {assign, reschedule, priority}` and ids | — | user-input | per-order results, never a boolean |

**6 · Acceptance** — **Given** three queued rows ticked, **when** *Assign* is pressed with R. Patel, **then** each matching order is scheduled to them and each mismatch is named.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---
id: US-WRK-028
epic: EP-WRK-05
module: work
screens: [Work-007]
wave: 2
status: ready
blocked_by: []
depends_on: [US-WRK-024, US-WRK-026]
journeys: [J62]
rules: [BR-WRK-024]
golden_tests: []
finance_calc: none
---
### US-WRK-028 — The three-step New order wizard: Job & location · Schedule & crew · Confirm (`WM-20`, undrawn — sub-screen of `Work-007`)

**1 · Details** — As **a clerk at an empty dispatcher**, I want **to raise `WO-4832 · Leak investigation · 77 Cedar Ct · A-10891 · High · due today 17:00`**, so that **it appears Queued and unassigned with *Raised by: Dispatcher***.

r10's `WRK-12`, named in `WS-07`'s footer as *+ New work order* and drawn nowhere in the blueprint — recorded here as a **sub-screen of `Work-007`**, not a `Work-` id of its own. Three steps; the template picker is filtered by the job type; the customer's presence requirement (`US-WRK-007`) is shown before Confirm.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-WRK-024` | Source stamped *Dispatcher* | CONFIRMED |
| `BR-WRK-006` | An anchor is required — premises, account or asset | PROPOSED |
| B14 rules 3, 11 | A three-stage flow uses the stepper; a consequence box before Confirm | CONFIRMED |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Job & location: Leak investigation at `77 Cedar Ct` (account `A-10891`); Schedule & crew: leave unassigned, High, due 17:00; Confirm | `WO-4832` Queued · Unassigned · *Raised by: Dispatcher* |
| TC-2 | Pick a template on step 1 | The order takes its copies (`US-WRK-032`) and `est_duration` |
| TC-3 · **negative** | Confirm with no premises, account or asset | Refused by the CHECK (`US-WRK-001`) and, first, by the wizard's own validation |
| TC-4 · **negative** | Close the tab on step 2 | No row — nothing is written until Confirm (the `BR-MET-112` shape) |
| TC-5 · **tenant isolation** | Lone Star Ridge's template picker | Its own templates |
| TC-6 | The consequence box | Names the three things Confirm does — raises the order, stamps the source, leaves it for the dispatcher — in one sentence each |

**4 · Test Data** — `WO-4832` as §1; template *Leak investigation* (Water, 4 tasks, 2 readings).

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| the wizard | sub-screen of `Work-007` | `WM-20` | `POST /work-orders` (`US-WRK-002`'s raise) with `source = dispatcher` | — | user-input | three steps, one write |

**6 · Acceptance** — **Given** an empty dispatcher, **when** a clerk completes the three steps, **then** the order is queued, unassigned, and says a dispatcher raised it.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---
id: US-WRK-029
epic: EP-WRK-05
module: work
screens: [Work-007]
wave: 2
status: ready
blocked_by: []
depends_on: [US-WRK-026]
journeys: [J62]
rules: [BR-WRK-023]
golden_tests: []
finance_calc: none
---
### US-WRK-029 — The map: pins coloured by status and priority, hollow when unassigned, click through to the job card (`WM-23`, undrawn — sub-screen of `Work-007`)

**1 · Details** — As **a dispatcher**, I want **to click the hollow red pin at `77 Cedar Ct` and read `WO-4823 · Leak investigation · High · Unassigned · due today 17:00` with an *Open details* button**, so that **a day's work can be placed on the ground**.

r10's `WRK-09` (*Map* in the sub-navigation), drawn nowhere in the blueprint — a **sub-screen of `Work-007`**. *"Nothing uses a premise's coordinates for this."* The pins come from the premises' coordinates through `customers_seam`; the basemap is the browser's own tile call the substrate already declares (`map_tiles_public`, `CR-069`).

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-WRK-023` | Pin colour reads dispatch state; hollow = unassigned | CONFIRMED — `WM-23` |
| `BR-WRK-002` | Coordinates are read through the seam | CONFIRMED |
| `CR-069` | Tiles come through the substrate's declared operation, never a hardcoded host | CONFIRMED |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Open Map with the ten orders | Ten pins; `WO-4823`'s is hollow and red (High, Unassigned) |
| TC-2 | Click it | A card: *WO-4823 · Leak investigation · High · Unassigned · due today 17:00* · *Open details* → `Work-008` |
| TC-3 · **negative** | An order whose premises has no coordinates | Listed in a *not on the map* strip with its address — never silently dropped |
| TC-4 · **negative** | `apps/work/**` for a tile host string | Zero — tiles come via the substrate (the `CR-069` gate) |
| TC-5 · **tenant isolation** | Lone Star Ridge's map | Its own pins |
| TC-6 | The same six filters apply | Filtering Area = North leaves four pins |

**4 · Test Data** — `77 Cedar Ct` at a fixture coordinate; one order at a premises with no coordinate (`Elm St & 3rd — network`, `WO-4828`, which has no premises — a network job).

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| pin | Map | `WM-23` | `GET /work-orders/map` → order id, lat/lng from `premises`, dispatch state, priority, assignee | list | computed-display | coordinates via `customers_seam` |

**6 · Acceptance** — **Given** ten open orders, **when** the map opens, **then** every order with a coordinate is a pin coloured by its state and the unassigned ones are hollow.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---
id: US-WRK-030
epic: EP-WRK-05
module: work
screens: [Work-007, Work-010]
wave: 2
status: ready
blocked_by: []
depends_on: [US-WRK-025, US-WRK-041]
journeys: [J62]
rules: [BR-WRK-034]
golden_tests: []
finance_calc: none
---
### US-WRK-030 — Push the order to the technician's phone on assignment: *Dispatched · pushed to phone · 14:02* (`WM-37`)

**1 · Details** — As **a dispatcher**, I want **assigning `WO-4823` to D. Ortiz to put the job on D. Ortiz's phone within seconds without them opening anything**, so that **the audit tab can honestly read *Dispatched · pushed to phone***.

r10's own words: *"Push to the technician's phone immediately"* and the audit line *"Dispatched · pushed to phone"*. *"Nothing pushes anything today."* Built as a job on its own queue (the `CR-069` shape: a job row before the broker message), delivering the job bundle (`US-WRK-042`) and a push notification where the device has registered a token.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-WRK-034` | Push on assignment; audit line | CONFIRMED — `WM-37` |
| `BR-WRK-025` | The push is a consequence of the `assign` row, never a separate act | CONFIRMED |
| B12 r1 §3 | Async = Celery on Redis; a job row before the broker message | CONFIRMED |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Assign `WO-4823` to D. Ortiz at 14:02 | A `work.push` job row exists before the broker message; the phone's next sync carries the job; Audit reads *Dispatched · pushed to phone · 14:02* |
| TC-2 · **negative** | The phone has no registered push token | The job is delivered on the next sync; the audit line reads *Dispatched · waiting for the phone* — never *pushed* when it was not |
| TC-3 · **negative** | The push provider is down | The job row stays queued and retries with jitter; the assignment stands; nothing is lost |
| TC-4 | Reassign to R. Patel | D. Ortiz's phone drops the job on its next sync; R. Patel's gains it; two audit lines |
| TC-5 · **tenant isolation** | Two tenants' pushes on the same queue | Two scope keys; neither dedupes the other |
| TC-6 | `JOBS_EAGER=false --reuse-db` | The suite runs against the real queue shape (`DEF-567`) |

**4 · Test Data** — D. Ortiz's device token `fxtr-ortiz-01`; R. Patel's `fxtr-patel-01`; J. Kaur with none.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| device token | phone | `WM-37` | `technician_devices` (technician_id · token · platform · registered_at) `[our table — §16 unread]` | rows | phone | one active per device |
| the push job | — | `WM-37` | `jobs.kind = work.push`, queue `work` | job row | system | scope key tenant · order · assignment row |
| audit line | `Work-008` Audit | r10 | `audit_log` action `work.dispatched` | jsonb | system | the sentence is in eleven catalogues |

**6 · Acceptance** — **Given** an assignment at 14:02, **when** D. Ortiz's phone is reachable, **then** the job is on it within seconds and the audit line says so — **and** when it is not, the audit line does not lie.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---
id: US-WRK-031
epic: EP-WRK-05
module: work
screens: [Work-021]
wave: 2
status: ready
blocked_by: []
depends_on: [US-WRK-024, US-WRK-025, US-WRK-020]
journeys: [J62]
rules: [BR-WRK-031, BR-WRK-032]
golden_tests: []
finance_calc: none
---
### US-WRK-031 — The work-order edit screen: assign, reschedule, re-prioritise, re-area, cancel — with a Change effects box before Save (`WM-39`)

**1 · Details** — As **a dispatcher**, I want **to move `WO-4821` from D. Ortiz to R. Patel and from 08:00–12:00 to 12:00–17:00 on one form**, so that **the customer is told because the window changed, R. Patel's phone shows the job within seconds, and the Audit tab lists both changes with my name and the time**.

`Work-021` at `/{tenant}/work/orders/WO-4821/edit` — *"Everything a dispatcher changes after the order exists."* Status · Priority · SLA target · Assigned to · Date · Window (*Any time · 08:00–12:00 · 12:00–17:00 · Exact appointment*) · Area · sub-area · Template (read-only) · Notes for the technician. The **Change effects** box before Save: *Customer notification — the customer is told the visit moved · Technician phone — job updates immediately · Audit — every field change is logged with who and when.* (⚠ The first line read *sent on save if the date or window changes* until 2026-09-05; B14 rule 32 wants one plain sentence per line and a clerk does not need the trigger condition recited back.) *Cancel work order* is danger tier. *"Nothing in §16 specified any of them — the dispatcher list shows orders and the detail reads one, but the screen that changes one was missing."*

⚠ **THE CUSTOMER NOTIFICATION IS SENT. THIS PARAGRAPH DESCRIBED A STUB UNTIL 2026-09-05, AND THE QUESTION HAD BEEN CLOSED FOR A DAY.** `OQ-WRK-1495` was ruled 2026-09-04, option **(a)** — PO verbatim: *"filing an appointment change beside disconnection notices distorts every monthly report"*. A reschedule queues on a NEW message source kind, **`appointment`**, with its own wording, through the one cross-module door (`seams.queue_document` → `outbound_messages`, B2 r16 #7). So Save writes the audit rows, the assignment rows **and the message**, and the Change effects box reads *Customer notification — the customer is told the visit moved* (one sentence, B14 rule 32).

⚠ **WHAT THE STUB'S REMOVAL COSTS A READER TO KNOW:** the marker `reschedule_notice_kind_unruled` is GONE from the response, and nothing should be written that greps for it. The negative that replaces TC-5 is stronger rather than weaker — the send must NOT be filed as `notice`, and the test asserts the kind by name.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-WRK-031` | Reschedule notifies on the `appointment` kind; every change audited | ⚠ **CONFIRMED IN FULL 2026-09-04** — `OQ-WRK-1495` closed on option (a); this cell read *OPEN for the kind* until 2026-09-05 |
| `BR-WRK-032` | Cancel is danger tier; Change effects before Save | CONFIRMED — B14 rules 6, 11 |
| `BR-WRK-025` | Assignment changes are new history rows | CONFIRMED |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Open `WO-4821`, change technician and window, Save | `unassign` + `assign` rows; `window_start/end` moved; **two** audit rows naming M. Torres and the time |
| TC-2 | R. Patel's phone | The job appears on the next sync (`US-WRK-030`) |
| TC-3 · **negative** | Cancel work order | Danger-tier button (`data-variant="danger"`); a confirmation naming the order; `dispatch_state = cancelled`, `state = cancelled`, one audit row; **no row deleted** |
| TC-4 | The Change effects box | Three lines, one sentence each, before Save (B14 rule 11) |
| TC-5 · **negative** ⚠ **AMENDED 2026-09-05, `OQ-WRK-1495` HAVING CLOSED 2026-09-04** | Save with a changed window | **ONE `outbound_messages` row, `source_type = "appointment"`** — and the negative is the KIND: a row filed as `notice` fails the test by name, because a monthly count of notices that silently includes appointment changes is wrong every month. `source_id` is the WORK ORDER's own id, so the unique key `(tenant, source_type, source_id, channel, copy_no)` makes a SECOND reschedule of the same order dedupe into the first — the `copy_no` the caller passes is what separates them |
| TC-6 · **negative** | Change only the notes | **No** notification branch reached; one audit row |
| TC-7 · **tenant isolation** | Lone Star Ridge opens `/work/orders/WO-4821/edit` | `404` |

**4 · Test Data** — `WO-4821` Disconnect for non-payment · En route · High · SLA Aug 16, 2026 16:00 · D. Ortiz · Water II · Aug 16 · 08:00–12:00 · North · Route 3 · template *Disconnect — non-payment · 5 steps* · notes *Dog on property — use side gate. Customer notified 08:00.*

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| status · priority · SLA target | `Work-021` | `WS-21` | `work_orders.dispatch_state`, `.priority_id`, `.due_at` | — | user-input | a Complete order refuses priority changes |
| assigned to · date · window | `Work-021` | `WS-21` | `work_order_assignments` rows; `work_orders.window_start/end` | — | user-input | skill match |
| area · sub-area | `Work-021` | `WS-21` | `work_orders.area_id` | uuid | user-input | `tenancy.Area` |
| notes for the technician | `Work-021` | `WS-21` | `work_orders.technician_notes` | text | user-input | carried to the phone |
| customer notification | `Work-021` | `WS-21` | `outbound_messages` via `seams.queue_document`, `source_type = "appointment"` (⚠ **a stub in this row until 2026-09-05**) | row | system | queued only when the date or the window actually moved |

**6 · Acceptance** — **Given** `WO-4821` is scheduled to D. Ortiz for the morning, **when** a dispatcher moves it to R. Patel in the afternoon and saves, **then** two audit rows and two assignment rows exist, R. Patel's phone has the job, **and** Sarah Miller is told the visit moved — filed as an **appointment**, never as a notice. (This sentence ended *"the customer notice is stated as not yet sent"* until 2026-09-05.)

**7 · Finance Calculation** — N/A.

**8 · Open Questions**

| OQ | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| `OQ-WRK-1495` | Which message kind fires on a reschedule? | The send only | PO | ✅ **CLOSED 2026-09-04 — option (a), a new source kind `appointment`.** This cell read OPEN until 2026-09-05 |
