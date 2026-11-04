# EP-WRK-02 — Settings and series: the catalogue, the priorities, the three parked cards, the parts register, the Area filter and the four number series

**Module:** work · **Wave:** phase **1** of `CR-070` (`WM-28` is phase 2 by `CR-070` §11 and is grouped here by subject) · **Screens:** `Work-018` · `Work-019` · `Work-007` · `Work-008` · `Work-025` · **Status:** draft (`CR-070`, 2026-09-03; §15–§21 unread)

## Scope

**In:** `WM-04` a work order type catalogue · `WM-05` priorities with SLA · `WM-06` the three parked Settings cards (skills, safety kits, parts categories) · `WM-07` the parts register, without stock · `WM-28` `tenancy.Area` as the dispatcher's Area filter · `WM-42` the four Work cards and the four Work number series. Blueprint §4's finding: *"Eight checks. None passes outright, two are half-there, six are nothing at all."*

**Out:** crews and technicians (`EP-WRK-04`) · labour rates (`EP-WRK-10`, `WM-45`) · parts ISSUED against a job (`EP-WRK-10`, `WM-22`) · stock levels and reorder points (`OQ-WRK-1490`).

⚠ **THE FOUR CARDS ALREADY RENDER**, on `Work-018`, each as *"Field work is not part of this release yet, so there is nothing to configure here. When dispatching work orders to technicians arrives, this list arrives with it."* Their code says why (`referenceDataConfig.ts:578–605`): *"no module in the map owns a work order, a crew, a skill or a parts stock, so there is no table to host a row and no owner to author a handler."* The module now exists; **wiring them is what the ruling looks like on screen.** A Reference-data card is DATA, never a new layout (`BR-SHL-035`).

## Capability matrix (list screens only — B9 conformance)

| Screen | Search fields | Filters | Default sort | Sortable | Columns default/available | Row actions | Bulk actions | Export |
|---|---|---|---|---|---|---|---|---|
| `Work-018` Reference data — Work group | the card's rows | — | the card's own | — | per card: code · name · (SLA / colour / location) | ✎ · − | — | — |
| `Work-019` Numbering — Work group | series | — | seed order | — | Series · Format · Next · Sample · Other formats | ✎ | — | — |
| `Work-025` Parts — Stock register | part #, description | category · location | part # | Part # · Category · Location | Part # · Description · Category · Location · Unit cost · Status | 👁 · ✎ | — | ↓ (IS-9) |

## Stories

---
id: US-WRK-007
epic: EP-WRK-02
module: work
screens: [Work-018, Work-007]
wave: 1
status: ready
blocked_by: []
depends_on: [US-WRK-005]
journeys: [J60, J62]
rules: [BR-WRK-017]
golden_tests: []
finance_calc: none
---
### US-WRK-007 — A work order type catalogue, so two clerks cannot type *Meter set* and *Meter Set* (`WM-04`)

⚠ **AMENDED 2026-09-07 BY THE PRODUCT OWNER, AND THE AMENDMENT CHANGES THE
SHAPE OF THE LIST AND NOT ONLY ITS CONTENTS (`BR-WRK-058`).** Everything below
this notice was written for a FLAT list of eight seeded rows. The PO rejected
those eight — *"this is not correct - you will ahve to think from all Utilty
services point of view"* — and supplied the replacement themselves: **nine
types and eighteen sub-types**, then **twenty-four more sub-types, one group
per utility service, all hanging under the same nine**. So:

* the list is **TWO LEVELS**. A row with no parent IS a type; a row with a
  parent IS a sub-type; there is no third level, and depth is enforced in the
  service, not by a constraint (`tenancy.Area`'s posture, `BR-MET-066b`);
* the seeding **follows what the utility sells** — *"a utility that picks water
  and gas gets the eighteen plus the four gas ones; a water-only utility gets
  exactly the eighteen and nothing else"*. ⚠ **AMENDED THE SAME DAY: EVERY
  sub-type names a service, the eighteen included, and they are WATER's.** They
  were unscoped at first, so a gas-only utility received *No Water Supply* and
  *Water Truck Services*; the PO ruled *"gas onlyutility carry only gas
  meters"*. **Water-only = 9 + 18. Water and gas = 9 + 22. Electric and water =
  9 + 21. GAS-ONLY = 9 + 4. All eleven services = 9 + 42.** The nine TYPES are
  never scoped. Eleven of the eighteen name no service at all — *Billing
  Issues*, *Meter Change*, *Re-read*, the four *Connection* rows and four more
  — so a gas utility lost job types it does daily. ⚠ **ELEVEN OF THEM CAME
  BACK THE SAME EVENING (`DEF-WRK-4512`, `work/0026`):** the PO ruled the
  service-neutral group common to every utility — *"yes that is correct; but we
  will ahve to see which Utility service they do"* — so *Billing Issues*,
  *Meter Change*, *Meter Dispose*, *Meter Replacement*, *Routine Inspection*,
  *Disconnection/Reconnection*, *Re-read* and the four *Connection* rows carry
  no `service` tag, and **a gas-only utility goes from `9 / 4` to `9 / 15`**.
  Water keeps the seven rows that are actually about water. **The second half
  of that sentence is still OPEN as `OQ-WRK-1764`** — whether the four METER
  rows should be narrowed to the services that have a meter, since a trash cart
  and a fire line are not re-read;
* **the eight rows below are RETIRED — deactivated on every existing tenant by
  `work/0023`, never deleted and never remapped.** A row a utility renamed
  stays active, because a renamed row is one they have made their own;
* **no seeded row carries an estimated duration or a customer-present flag any
  more**, and §4's r10 figures below are HISTORY. ⚠ **A DEFAULT PRIORITY IS
  RULED IN AND IS NOW SEEDED — `OQ-WRK-1765` is CLOSED (2026-09-07) as a
  recorded JUDGMENT, not as an answer from the PO.** They answered *"Yes"* to
  whether a type carries one, were shown the four bands with the response time
  each implies, did not dispute the values, redirected to *"you keep them
  configurable in settings - user can change the timings"*, and then said
  *"please complete all the changes /bug we discussed - dont wait for me"*.
  **That is a delegation and not a signature, and no document may restate these
  hours as ratified.** What makes seeding them safe is the PO's own ruling:
  `work_priorities.sla_hours` is a per-tenant SETTING, editable on Settings →
  Reference data → Work priorities since `work/0001` and read live by both
  `due_at` derivations — so a seeded default is a starting point a utility
  changes in one word, not a promise the platform makes for them.
  **SEEDED (`work/0027`, `models.SEED_TYPES`):** High 8 h — *Consumer
  Complaint* · *Corrective Maintenance* · *Water Quality Monitoring*; Normal
  72 h — *Meter Maintenance* · *Connection* · *Consumer Services*; Low 168 h —
  *Preventive Maintenance* · *Infrastructure Development* · *Reading*.
  ⚠ **AND FOUR SUB-TYPES CARRY `Urgent` 4 h IN THEIR OWN RIGHT, BEATING THEIR
  PARENT HEADING** — *Gas leak call-out* · *Odour complaint* · *No Water
  Supply* · *Outage report*. `_resolve_priority` falls back to the TYPE's
  default and no further, so without a row of its own a gas leak would inherit
  **eight hours** from *Consumer Complaint* — the wrong number, arriving by
  accident, at a customer's house. `models.URGENT_BEATS_ITS_PARENT` names them
  and `tests/test_cr070_default_priorities.py` fails if one is removed.

The list itself, the counts and the refusals live in `BR-WRK-058` and in
`tests/test_cr070_work_order_type_levels.py`. **TC-2 and §4 below describe the
superseded world and are kept only so the supersession is legible.**

**1 · Details** — As **a utility admin**, I want **the job types my utility does written down once**, so that **a picker offers them and a filter groups them**.

Today `work_orders.type` is free text, *"deliberately not an enum"*, and nothing groups two spellings. `work_order_types` — code, name, default priority, default template, estimated duration, whether the customer must be present. A clerk adds *Backflow test* in Settings and it appears immediately in the Type picker on New work order and in the Type filter on `Work-007`, beside the eight r10 types. **The existing free-text column is not dropped in this story** — `work_orders.type_id` is added beside it and the eight r10 names are seeded and matched; the free-text column's retirement is §16's to state (unread).

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-WRK-017` | Types are a catalogue; a new type appears immediately in picker and filter | CONFIRMED — `WM-04` |
| `BR-SHL-035` | A new Reference-data card is data, never a new layout | CONFIRMED |
| B14 rule 31 | The picker shows the name; the code is never the visible value | CONFIRMED |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Add *Backflow test* · default Normal · default template *Backflow inspection* · 35 min · customer present: no | It appears in the Type picker and in `Work-007`'s Type filter on the next load, ninth of nine |
| TC-2 | ~~The eight seeded types~~ **SUPERSEDED 2026-09-07 (`BR-WRK-058`)** — the eight (Reconnect · Main repair · Disconnect — non-pay · Leak investigation · Meter exchange · Backflow inspection · Read verification · Move-in activation) are RETIRED, and what is seeded is the PO's own nine types with eighteen sub-types plus the per-service ones for the services this utility sells. Asserted in `tests/test_cr070_work_order_type_levels.py`, not here |
| TC-3 · **negative** | Add a second type with code `METER_EXCHANGE` | Refused — unique per tenant on code; sentence ≤ 6 words |
| TC-4 · **negative** | Delete a type that an order references | Refused; the card offers *Deactivate* instead (the same shape templates use, `BR-WRK-012`) |
| TC-5 · **tenant isolation** | Lone Star Ridge's Type picker | Its own eight seeded rows and none of Brazos Bend's additions |
| TC-6 | An existing order whose free-text `type` is *Meter set* | Matched to the seeded *Meter exchange*? **No** — matched only on an exact seeded name; unmatched text stays and is reported in the migration's summary, never guessed |

**4 · Test Data** — ⚠ **HISTORY SINCE 2026-09-07 (`BR-WRK-058`): none of these rows is seeded any more and no seeded type carries a default priority at all.** The eight r10 types above with r10's own default priorities (Reconnect → Urgent · Main repair → Urgent · Disconnect → High · Leak investigation → High · Meter exchange → Normal · Backflow inspection → Normal · Read verification → Low · Move-in activation → Normal). New: *Backflow test*, 35 min.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| code · name | `Work-018` | `WM-04` | `work_order_types.code`, `.name` | text | user-input | unique (tenant, code) |
| default priority | `Work-018` | `WM-04` | `work_order_types.default_priority_id` | FK → `work_priorities` | reference-data | `US-WRK-008` |
| default template | `Work-018` | `WM-04` | `work_order_types.default_template_id` | FK → `work_order_templates` | reference-data | nullable until templates exist |
| estimated duration | `Work-018` | `WM-04` | `work_order_types.est_duration` | interval (its own unit) | user-input | ≥ 0 |
| customer must be present | `Work-018` | `WM-04` | `work_order_types.customer_present` | boolean | user-input | default false |
| type on an order | `Work-007` | `WM-04` | `work_orders.type_id` | FK NULL | reference-data | beside the existing free-text `type` `[§16 unread on its retirement]` |

**6 · Acceptance** — ⚠ **AMENDED 2026-09-07 (`BR-WRK-058`).** **Given** the seeded list — nine types, the eighteen base sub-types and the per-service sub-types for the services this utility sells — **when** an admin adds *Backflow test*, **then** the dispatcher's Type filter and the New work order picker both offer it, **and** a duplicate code is refused, **and** a sub-type may not itself be given children.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---
id: US-WRK-008
epic: EP-WRK-02
module: work
screens: [Work-018, Work-007, Work-008]
wave: 1
status: ready
blocked_by: []
depends_on: [US-WRK-005]
journeys: [J60, J62]
rules: [BR-WRK-018]
golden_tests: []
finance_calc: none
---
### US-WRK-008 — Priorities, each with its SLA: Urgent = 4 hours means a 09:00 order reads *Due 13:00* with nobody typing a date (`WM-05`)

**1 · Details** — As **a dispatcher**, I want **a priority to carry a promise**, so that **the due time is derived and the list sorts by it**.

`work_priorities` — code, name, rank, SLA hours, colour. `due_at` defaults to the raise time plus the SLA. The card on `Work-018` today says *arrives with Work*; it stops. Four seeded rows: Urgent · High · Normal · Low.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-WRK-018` | A priority carries SLA hours; `due_at` defaults to raise + SLA; sort by rank then due | CONFIRMED — `WM-05` |
| B14 rule 32 | A colour is a chip, not a sentence | CONFIRMED |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Set Urgent = 4 h; raise `WO-4824` at 09:00 Urgent | `due_at` = 13:00 with no date typed; it sorts above the two High rows |
| TC-2 | Raise with an explicit due of 17:00 on a High (SLA 8 h) order at 09:00 | The typed 17:00 wins; the default fills only a blank |
| TC-3 · **negative** | SLA hours = −1 | Refused at validate |
| TC-4 · **negative** | Change Urgent from 4 h to 2 h | `WO-4824`'s existing `due_at` does **not** move — a due is stamped at raise, like `is_gate` |
| TC-5 · **tenant isolation** | Lone Star Ridge changes its Normal to 48 h | Brazos Bend's Normal unchanged |
| TC-6 | Ordering on `Work-007` | Urgent → High → Normal → Low by rank, then due time within a rank — `WS-07`'s footer *"sorted by priority then due time"* |

**4 · Test Data** — Urgent 4 h · High 8 h · Normal 72 h · Low 168 h, colours per r10. `WO-4824` Reconnect · Urgent · raised 09:00 · due 13:00. `WO-4821` High · `WO-4823` High.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| code · name · rank | `Work-018` | `WM-05` | `work_priorities.code`, `.name`, `.rank` | text · int | user-input | unique (tenant, code); unique (tenant, rank) |
| SLA hours | `Work-018` | `WM-05` | `work_priorities.sla_hours` | numeric hours (its unit is in the column name) | user-input | ≥ 0 |
| colour | `Work-018` | `WM-05` | `work_priorities.colour` | text token | user-input | from the design tokens, never a hex typed by a clerk |
| due | `Work-007` | `WM-05` | `work_orders.due_at` | timestamptz | system-derived / user-input | raise + SLA when blank (`US-WRK-024` carries the column) |

**6 · Acceptance** — **Given** Urgent = 4 hours, **when** an Urgent order is raised at 09:00, **then** it reads *Due 13:00* and sorts first.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---
id: US-WRK-009
epic: EP-WRK-02
module: work
screens: [Work-018]
wave: 1
status: ready
blocked_by: []
depends_on: [US-WRK-005]
journeys: [J60]
rules: [BR-WRK-017]
golden_tests: []
finance_calc: none
---
### US-WRK-009 — Wire the three parked Settings cards: skills, safety kits, parts categories (`WM-06`)

**1 · Details** — As **a utility admin**, I want **Settings · Work · Skills to list the six skills I just added**, so that **a template can name a skill and a technician can hold one**.

Three plain lookups — `work_skills`, `work_safety_kits`, `part_categories` — behind three cards that today render one sentence and no control. `work_order_templates.skill` is free text, null on all 24 seeded rows, written by nothing; `US-WRK-013` replaces it with `skill_id` pointing here.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-WRK-017`'s shape | A lookup, not free text; appears immediately in the pickers that read it | CONFIRMED — `WM-06` |
| `BR-SHL-035` | A card is data | CONFIRMED |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Add *Backflow* to Skills | It appears in the Skill needed picker on `Work-014` and in the skills wizard reached from `Work-024` |
| TC-2 | The seeded sample copy | Skills: Water I–III · Electric I/II · Meter I · Reads · Excavation; Safety kits: Basic PPE · LOTO · Confined space · Traffic control; Parts categories: Meters · Consumables (locations Yard · Van 3/8/12 belong to `US-WRK-010`) — the card's own sample copy becomes its seeded rows |
| TC-3 · **negative** | Delete *Meter fitting* while a template names it | Refused; *Deactivate* offered |
| TC-4 · **negative** | The card with zero rows | The empty state names what is missing and the action that fills it (B14 rule 17); **never** *"arrives with Work"* again |
| TC-5 · **tenant isolation** | Lone Star Ridge adds *Chlorination* | Absent from Brazos Bend's picker |

**4 · Test Data** — As TC-2. New: *Backflow* (skill).

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| skill | `Work-018` | `WM-06` | `work_skills.code`, `.name`, `.active` | text · bool | user-input | unique (tenant, code) |
| safety kit | `Work-018` | `WM-06` | `work_safety_kits.code`, `.name`, `.items` | text · text[] | user-input | items are the kit's contents, shown on `Work-014` |
| parts category | `Work-018` | `WM-06` | `part_categories.code`, `.name` | text | user-input | unique (tenant, code) |

**6 · Acceptance** — **Given** the three cards, **when** an admin adds a skill, **then** the card lists it and the template builder offers it — and the sentence *arrives with Work* appears nowhere.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---
id: US-WRK-010
epic: EP-WRK-02
module: work
screens: [Work-018, Work-025, Work-008]
wave: 1
status: ready
blocked_by: []
depends_on: [US-WRK-009]
journeys: [J60, J62]
rules: [BR-WRK-019]
golden_tests: []
finance_calc: proposed
---
### US-WRK-010 — The parts register: part number, name, category, unit, unit cost at four decimals — and no stock level, because none lawfully exists (`WM-07`)

**1 · Details** — As **a utility admin**, I want **the parts my crews fit written down with a cost**, so that **a template can plan them and a job can price them**.

`parts` — part number, name, category, unit of measure, unit cost at 4 decimals. A clerk adds `MTR-W58 · Water meter 5/8" · each · $92.4000` stored and `$92.40` displayed, and it then appears on a template's Materials step and on `WO-4822`'s Parts tab. ⚠ **`Work-025` DRAWS WHAT THE CARD REFUSES.** The wireframe shows *On hand 184 · Reorder at 60*, a *Reorder — 2 parts at or below reorder level* banner and *"Issues deduct stock the moment they are recorded"*; `WM-07` and `WM-22` say *"No stock levels, no reorder points"* and `CR-028` §11-D5 parks the stock table. **The card wins and the columns are not drawn** until `OQ-WRK-1490` is ruled; the register ships without them. A second contradiction, recorded in `03-field-map.md` §5: the card prices `MTR-W58` at `$92.4000`, the wireframe at `78.40`. **The card's figure is used.**

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-WRK-019` | Part number, name, category, uom, unit cost 4 dp / display 2; no stock, no reorder | CONFIRMED — `WM-07`; stock OPEN `OQ-WRK-1490` |
| CLAUDE.md hard rule 2 | 4 decimals stored, 2 displayed | CONFIRMED |
| CLAUDE.md hard rule 3 | A quantity carries its unit | CONFIRMED |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Add `MTR-W58` · Water meter 5/8" · Meters · each · `92.4000` | Stored `92.4000`; shown `$92.40` on `Work-025` and on `Work-014` step 4 |
| TC-2 | The same part in two locations | ⚠ **Not modelled** — location is a stock concept (`OQ-WRK-1490`); the register holds one row per part number |
| TC-3 · **negative** | Unit cost `92.40004` | Refused — more than 4 decimals |
| TC-4 · **negative** | A part with no unit of measure | Refused (hard rule 3) |
| TC-5 · **negative** | `GET /work/parts` response body | Contains **no** `on_hand`, `reorder_at` or `location` key — asserted by name, so a lane cannot add them quietly |
| TC-6 · **tenant isolation** | Lone Star Ridge's register | Its own parts; Brazos Bend's `MTR-W58` absent |
| TC-7 | Export ↓ (IS-9) | The CSV carries unit cost to **2** decimals as displayed, with a column header naming the unit |

**4 · Test Data** — `MTR-W58` Water meter 5/8" · AMI · Meters · each · `92.4000` · `MTR-E1P` Electric meter · 1φ AMI · Meters · each · `96.0000` · `SEAL-01` Wire seal · Consumables · each · `0.2200` · `GSKT-STD` Gasket set · Consumables · each · `1.8000` (ours — the blueprint gives no price) · `GAUGE-BF` Backflow test gauge · Test equipment · each · `640.0000`.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| part number | `Work-025` | `WM-07` | `parts.part_no` | text | user-input | unique (tenant, part_no) |
| name | `Work-025` | `WM-07` | `parts.name` | text | user-input | required |
| category | `Work-025` | `WM-07` | `parts.category_id` | FK → `part_categories` | reference-data | `US-WRK-009` |
| unit of measure | `Work-025` | `WM-07` | `parts.unit_of_measure` | text | user-input | required (hard rule 3) |
| unit cost | `Work-025` | `WM-07` | `parts.unit_cost` | `numeric(18,4)` → display 2 | user-input | ≥ 0 |
| on hand · reorder at · location | `Work-025` (drawn) | `WS-25` | **none** | — | — | **NOT BUILT — `OQ-WRK-1490`** |

**6 · Acceptance** — **Given** an empty register, **when** an admin adds `MTR-W58` at `92.4000`, **then** it shows as `$92.40`, appears on a template's Materials step, **and** the register has no stock column anywhere.

**7 · Finance Calculation** — Unit cost stored `92.4000`, displayed `92.40`. A part line on a report is quantity × unit cost (`BR-WRK-051`, `US-WRK-053`): `1 × 96.0000 = 96.00`. No GT — a lookup value, not billing arithmetic.

**8 · Open Questions**

| OQ | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| `OQ-WRK-1490` | Can a parts stock table exist? | The On hand / Reorder / Location columns and the *issues deduct stock* behaviour drawn on `Work-025`. **The register ships without them** | PO | OPEN |

---
id: US-WRK-011
epic: EP-WRK-02
module: work
screens: [Work-007]
wave: 2
status: ready
blocked_by: []
depends_on: [US-WRK-026]
journeys: [J62]
rules: [BR-WRK-022]
golden_tests: []
finance_calc: none
---
### US-WRK-011 — Wire `tenancy.Area` as the dispatcher's Area filter, and as the order's area · sub-area (`WM-28`)

**1 · Details** — As **a dispatcher**, I want **Area = North to leave the four orders on Route 1 and Route 3**, so that **a day's work can be read by district**.

`tenancy.Area` is a real seeded lookup that metering routes already use; nothing in Work references it. This story adds `work_orders.area_id` and the sixth filter, and reads the lookup through `seams/tenancy_seam.py` — Work never copies it.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-WRK-022` | Areas are `tenancy.Area`; Work references, never duplicates | CONFIRMED — `WM-28` |
| `BR-WRK-026` | Six filters exactly, Area the sixth | CONFIRMED |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Area = North | Exactly `WO-4821`, `WO-4822`, `WO-4826`, `WO-4828` remain; footer *Showing 4 of 10 open orders* |
| TC-2 | Area = North + Priority = High | `WO-4821` alone |
| TC-3 · **negative · tenant isolation** | An area code Lone Star Ridge owns, passed on Brazos Bend's list | Zero rows — the filter is resolved under RLS, never trusted from the query string |
| TC-4 · **negative** | `apps/work/**` for a copy of the Area model | Zero — the gate of `US-WRK-005` TC-4 fails on `from apps.tenancy.models import Area` outside `seams/` |
| TC-5 | `Work-021` Area · sub-area | Reads *North · Route 3* from the same lookup |

**4 · Test Data** — Areas North (Route 1, Route 3), South (Route 2). Orders as `WS-07`; `WO-4822` `221 Oak Ave · North · Route 1`.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| area | `Work-007`, `Work-021` | `WM-28` | `work_orders.area_id` FK → `tenancy.areas` | uuid | system-derived from the premises' route, overridable | cross-module FK in the reviewed set |

**6 · Acceptance** — **Given** ten open orders, **when** Area = North is set, **then** four remain and the footer says so.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---
id: US-WRK-012
epic: EP-WRK-02
module: work
screens: [Work-018, Work-019]
wave: 1
status: ready
blocked_by: []
depends_on: [US-WRK-007, US-WRK-008, US-WRK-009, US-WRK-010]
journeys: [J60]
rules: [BR-WRK-021]
golden_tests: []
finance_calc: none
---
### US-WRK-012 — Wire the four Work settings cards and the four Work number series — and leave `dispatch_batch` deliberately unwired (`WM-42`)

**1 · Details** — As **a utility admin**, I want **Settings → Reference data → Work and Settings → Numbering → Work to edit real rows**, so that **the four promises the shipped product makes on those screens are kept**.

The four Reference-data cards — skills, safety kits, priorities & SLA, parts categories & locations — stop rendering *arrives with Work* and edit the rows `US-WRK-007`–`010` created. On `Work-019` the `service_template` series (`ST-{0000}`, next `ST-0001`) gets `work_order_templates.template_no` to write into (`US-WRK-013`). ⚠ **`dispatch_batch` (`DSP-{YY}{MM}{DD}-{00}`, next `DSP-260903-01`) IS DELIBERATELY EXCLUDED.** *"It numbers an entity with no table, no service and no screen, and inventing one would answer a question nobody has asked."* The series stays on `Work-019` as seeded — the PO ruled these standalone on 2026-08-16 (*"Yes; it should work standalone in settings; we will link it later ith work"*) — and what a dispatch batch IS is `OQ-WRK-1497`.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-WRK-021` | `work_order` allocates; `service_template` gets a column; `dispatch_batch` excluded | CONFIRMED — `WM-42`; `OQ-WRK-1497` |
| `BR-TEN-035` | Never renumber what has been issued; format changes apply forward | CONFIRMED |
| `BR-SHL-035` | A card is data | CONFIRMED |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Open Settings → Reference data → Work, add skill *Backflow* | It appears in the Skill needed picker on `Work-014` and the skills wizard on `Work-024`; the card shows a control, not a sentence |
| TC-2 | Publish a template | `template_no` = `ST-0001`; `Work-019` reads next `2`, sample `ST-0002` |
| TC-3 · **negative** | Change the template format to `TMPL-{000}` after `ST-0001` issued | `ST-0001` stays; the next is `TMPL-002`? **No** — the counter is per series and continues: `TMPL-002` is the sample only if the counter reads 2; the test asserts the issued number never changes |
| TC-4 · **negative** | Anything in `apps/work/` allocating from `dispatch_batch` | Zero call sites — asserted by grep in a test; the series exists in numbering (`numbering.py:356–357`) and is allocated by nothing |
| TC-5 · **tenant isolation** | Lone Star Ridge publishes its first template | `ST-0001` on Lone Star; Brazos Bend's counter untouched |
| TC-6 | `Work-019` header | *WORK · 4 of 27 series* with the four formats and their alternatives exactly as seeded |

**4 · Test Data** — Series as `WS-19`: Connection `CON-{YY}-{0000}` next 117 · Work order `WO-{0000}` next 4834 · Service template `ST-{0000}` next 1 · Dispatch batch `DSP-{YY}{MM}{DD}-{00}` next 1.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| template number | `Work-019`, `Work-013` | `WM-42`, `WM-08` | `work_order_templates.template_no` | text | system-derived (`core/numbering.py`) | allocated inside the publish transaction; unique (tenant, template_no) |
| the four cards | `Work-018` | `WM-42` | `work_skills` · `work_safety_kits` · `work_priorities` · `part_categories` | rows | user-input | the card's `kind: "list"` config points at the module's endpoints |
| dispatch batch | `Work-019` | `WM-42` | **none** | — | — | **excluded; `OQ-WRK-1497`** |

**6 · Acceptance** — **Given** the four cards, **when** an admin opens them, **then** each edits real rows, **and** the first published template is `ST-0001` — **and** nothing allocates a dispatch batch number.

**7 · Finance Calculation** — N/A.

**8 · Open Questions**

| OQ | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| `OQ-WRK-1497` | What is a dispatch batch? | Nothing — the series stays seeded and unallocated | PO | OPEN — non-blocking |
