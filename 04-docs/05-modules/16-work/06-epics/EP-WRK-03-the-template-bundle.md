# EP-WRK-03 — The template bundle: header columns, seven child tables, the write service the seeder says is OWED, the eight-step builder, step 6 of New Connect, and what v2 means

**Module:** work · **Wave:** phase **1** of `CR-070` · **Screens:** `Work-004` · `Work-005` (replaced) · `Work-013` · `Work-014` · `Work-015` · `Work-016` · `Work-017` · `Work-022` · **Status:** draft (`CR-070`, 2026-09-03; §15–§21 unread)

## Scope

**In:** `WM-08` header columns and one relaxed key · `WM-09` the seven child tables · `WM-10` the write service · `WM-11` the eight-step builder · `WM-12` New Connect step 6 proposes orders · `WM-40` versions · and the seeded starters becoming the thing they were seeded to be, with the gate that keeps them read (`CR-070` §12 gate 3).

**Out:** the order's own copies (`EP-WRK-06`, `WM-18`) · readings that post (`EP-WRK-09`, `WM-29`) · signature capture (`EP-WRK-06`, `WM-30`).

**Blueprint §5's finding:** *"A template today is one row with ten columns. No tasks, no materials, no readings, no safety, no help, no signature — and no screen to author one."* And: *"Twenty-four starter rows are seeded across eleven services. The only code that touches the table stamps a template id the caller supplies… The templates exist as data and are, today, completely inert."*

**Exit test of the phase (`CR-070` §11):** *a utility authors its own job templates, and the wizard proposes them.* `BR-MET-109` already says templates are developed *"in work order section"*; **this epic is that section.**

## Capability matrix (list screens only — B9 conformance)

| Screen | Search fields | Filters | Default sort | Sortable | Columns default/available | Row actions | Bulk actions | Export |
|---|---|---|---|---|---|---|---|---|
| `Work-013` Templates | template, job type | service (*Filter by service ▾*) | service seed order, then sequence | Template · Service · Status | Template · Service · Job type · Contents · Gate · Skill · Est. · Status | ✎ · 👁 | — | — |
| `Work-022` Template detail · Versions tab | — | — | version desc | — | Version · Published · By · What changed · Orders raised · Status | 👁 | — | — |

## Stories

---
id: US-WRK-013
epic: EP-WRK-03
module: work
screens: [Work-013]
wave: 1
status: ready
blocked_by: []
depends_on: [US-WRK-007, US-WRK-009, US-WRK-012]
journeys: [J60]
rules: [BR-WRK-010]
golden_tests: []
finance_calc: none
---
### US-WRK-013 — Template header columns, and one relaxed key: two Water templates at once (`WM-08`)

**1 · Details** — As **a utility admin**, I want **to save both *New connection* and *Leak investigation* for Water**, so that **one service can have as many job templates as it needs**.

Add `type_id`, `skill_id` (replacing the dead free-text `skill`), `crew_size`, `safety_kit_id`, `active`, `version`, and `template_no` (`US-WRK-012`). Relax `unique(service, sequence)` — *"Two Water templates is the case today's unique key forbids."* `Work-013` lists each template with its **Contents** column — *7 tasks · 3 parts · 3 readings* — *"the whole point of the bundle in one line"*.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-WRK-010` | More than one template per service; unique on (tenant, name, version) | PROPOSED — `WM-08` |
| `BR-MET-109` | Templates are the utility's own | CONFIRMED |
| B14 rules 12, 16, 17 | Toolbar · footer · empty state | CONFIRMED |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Save *New connection* (Water) and *Leak investigation* (Water) | Both saved; `Work-013` lists both under Water |
| TC-2 · **negative** | Save a second *Leak investigation* v1 for the same tenant | Refused — unique (tenant, name, version); sentence ≤ 6 words |
| TC-3 · **negative** | The migration against 24 seeded rows with `skill = NULL` | `skill_id` NULL on all 24; the free-text column dropped only after a summary shows zero non-null values |
| TC-4 | Contents column for *Meter exchange — residential* | *7 tasks · 3 parts · 3 readings*; for a seeded starter with nothing behind it *0 tasks · 0 parts · 0 readings* — never blank |
| TC-5 · **tenant isolation** | Lone Star Ridge's list | Its own 24 starters (or fewer, service-shaped); none of Brazos Bend's authored rows |
| TC-6 | Footer | *6 templates · 4 published · 1 draft · 1 inactive*; *Seeded starters are marked and can be edited or deleted* (one sentence, B14 rule 32) |

**4 · Test Data** — The six rows of `WS-13`: *New connection* Electric · Move-in activation · 2 tasks · 0 parts · 1 reading · gate Meter set · Meter fitting · 40 min · Published · *Meter exchange — residential* Electric · 7 · 3 · 3 · — · Meter fitting · 45 min · Published · *New connection* Water · 3 · 1 · 1 · Meter set · Meter fitting · 1 h 10 m · Published · *New connection* Gas · 4 · 2 · 2 · **Light-up** · Gas fitting · 2 h · Published · *Leak investigation* Water · 4 · 0 · 2 · — · — · 50 min · Draft · *Backflow test* Water · 3 · 1 · 4 · — · Backflow · 35 min · Inactive.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| type | `Work-013` | `WM-08` | `work_order_templates.type_id` FK → `work_order_types` | uuid | reference-data | `US-WRK-007` |
| skill | `Work-013` | `WM-08` | `work_order_templates.skill_id` FK → `work_skills` (replaces text `skill`) | uuid NULL | reference-data | `US-WRK-009` |
| crew size | `Work-014` | `WM-08` | `work_order_templates.crew_size` | smallint | user-input | ≥ 1 |
| safety kit | `Work-014` | `WM-08` | `work_order_templates.safety_kit_id` | uuid NULL | reference-data | — |
| active · version | `Work-013`, `Work-022` | `WM-08` | `work_order_templates.active`, `.version` | bool · int | system-derived | version starts at 1 on first publish |
| the relaxed key | — | `WM-08` | drop `uq(service, sequence)`; add `uq(tenant, name, version)` | constraint | — | `BR-WRK-010` |
| existing columns | — | exist | `service_id` · `sequence` · `name` · `scope` · `est_duration` · `is_gate` · `is_sample` | — | — | untouched |

**6 · Acceptance** — **Given** Water has *New connection*, **when** an admin saves *Leak investigation* for Water, **then** both appear in the list with their contents counted.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---
id: US-WRK-014
epic: EP-WRK-03
module: work
screens: [Work-015, Work-016, Work-008]
wave: 1
status: ready
blocked_by: []
depends_on: [US-WRK-013, US-WRK-010]
journeys: [J60]
rules: [BR-WRK-009, BR-WRK-015]
golden_tests: []
finance_calc: none
---
### US-WRK-014 — The seven template child tables: details, safety, tasks, materials, readings, help, asset types — rows, not a blob (`WM-09`)

**1 · Details** — As **a utility admin**, I want **a template to carry its safety lines, its ordered tasks with minutes and photo flags, its planned parts, its reading specifications, its help pack and the asset types it applies to**, so that **a job is doable in the field from what the template says**.

`wot_details`, `wot_safety`, `wot_tasks`, `wot_materials`, `wot_readings`, `wot_help`, `wot_asset_types` — *"child rows, not a JSON blob, following BR-MET-108's precedent."* A task is three fields, not one: *"a title alone gives a technician a checklist; a title with minutes gives a dispatcher a schedule; a title with a photo flag gives a supervisor evidence"* — and **the sequence is data**, because it is what the phone shows.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-WRK-009` | Seven child collections as rows | PROPOSED — `WM-09`, `BR-MET-108` precedent |
| `BR-WRK-015` | A reading specification's six columns; the unit is a column | CONFIRMED — `WS-16`, hard rule 3 |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Open *Meter exchange — residential* | 3 safety lines, 7 tasks totalling **45 min**, 3 materials, 3 readings and 3 help entries, **in the order they were entered** |
| TC-2 | Reorder task 6 above task 5 with the drag handle | `wot_tasks.seq` rewritten for the two rows; the phone's order follows |
| TC-3 · **negative** | A reading with prompt *Final read (kWh)* and no unit | Refused — the unit is a column, not a word in the prompt |
| TC-4 · **negative** | A task with `est_minutes = 0` and `is_mandatory = true` | Accepted — a mandatory zero-minute check is lawful; the test guards that the validator does not confuse *no estimate* with *invalid* |
| TC-5 · **negative** | `work_order_templates` gains a `bundle` jsonb column in a draft migration | The schema test fails — no JSON blob for the bundle |
| TC-6 · **tenant isolation** | Lone Star Ridge reads `/work/templates/{brazos-id}/tasks` | `404` byte-identical to an absent row |
| TC-7 | Asset types | *Electric meter · AMI single-phase · Water meter 5/8"–1"* stored as rows pointing at `assets` asset types through the seam; `Work-028` filters on them |

**4 · Test Data** — The seven tasks of `WS-15`: 1 Verify meter ID matches work order · 3 min · — · Yes · 2 Record final read on old meter · 2 · Required · Yes · 3 Isolate supply & remove old meter · 10 · — · Yes · 4 Fit new meter & pressure test · 15 · — · Yes · 5 Record opening read on new meter · 2 · Required · Yes · 6 Apply tamper seal & log seal number · 5 · — · Yes · 7 Restore supply & confirm flow · 8 · — · Yes = **45 min**. Safety: *Isolate at the service head before removal* · *Check for backfeed / on-site generation* · *Confined space check where pit-set*. Materials: `MTR-E1P` ×1 · `SEAL-01` ×1 · `GSKT-STD` ×1. Readings: *Final read on old meter* kWh 0–99,999 photo Required · required Yes · posts Yes · *Opening read on new meter* kWh 0–999 · Required · Yes · Yes · *New meter serial* — · Optional · Yes · No. Help: *Meter exchange SOP v4 (PDF)* · *Supervisor · M. Torres · (512) 555-0138* · *AMI activation hotline · ext 44*. Details ticks: account & premise summary · asset card · access notes & hazards · appointment window & customer phone.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| details | `Work-014` | `WM-09` | `wot_details` (template_id · show_account_summary · show_asset_card · show_access_notes · show_appointment) | booleans | user-input | one row per template |
| safety | `Work-014` step 2 | `WM-09` | `wot_safety` (seq · text · is_mandatory) | rows | user-input | seq unique per template |
| tasks | `Work-015` | `WM-09` | `wot_tasks` (seq · title · est_minutes · photo_required · is_mandatory) | rows | user-input | minutes ≥ 0 |
| materials | `Work-014` step 4 | `WM-09` | `wot_materials` (part_id · planned_qty · unit_of_measure) | rows | user-input | part from `parts` |
| readings | `Work-016` | `WM-09` | `wot_readings` (seq · prompt · unit_of_measure · min · max · required · photo_required · posts_as_meter_read) | rows | user-input | unit required; min ≤ max |
| help | `Work-014` step 6 | `WM-09` | `wot_help` (seq · kind ∈ {document, phone, note} · label · ref) | rows | user-input | a document ref points at the document store |
| asset types | `Work-014` step 1 | `WM-09` | `wot_asset_types` (asset_type_id) | rows | reference-data via `assets_seam` | cross-module FK, reviewed set |

**6 · Acceptance** — **Given** the residential meter-exchange template, **when** it is opened, **then** its seven sections read back in entry order with their counts, **and** a reading without a unit cannot be saved.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---
id: US-WRK-015
epic: EP-WRK-03
module: work
screens: [Work-017, Work-013]
wave: 1
status: ready
blocked_by: []
depends_on: [US-WRK-014]
journeys: [J60, J67]
rules: [BR-WRK-011]
golden_tests: []
finance_calc: none
---
### US-WRK-015 — The template write service the seeder says is OWED: create, update, delete, publish, and nested CRUD for seven collections (`WM-10`)

**1 · Details** — As **the seeder and the builder**, I want **one service that writes a template**, so that **nothing writes rows straight through the model**.

*"The seeder currently writes rows straight through the model because none of this exists"* — `sample_data.py` records in its own words that *"a create_work_order_template service is OWED."* `apps/work/templates_svc.py`: `create_work_order_template`, `update_work_order_template`, `delete_work_order_template` (refused while referenced), `publish_work_order_template`, `duplicate_work_order_template`, `deactivate_work_order_template`, and nested writes for the seven collections. The seeder is re-pointed at it.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-WRK-011` | Publish is the one write that reaches orders; a draft persists as a draft | CONFIRMED |
| `BR-WRK-012` | Delete refused while referenced; Deactivate instead | CONFIRMED |
| B1 | Writes in `services`, reads in `selectors` | CONFIRMED |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Rename *Meter set* to *Meter fit* on the Electric template, reload | The new name persists — **and `WO-4902`, already raised, still reads *Meter set*** (copy, never link) |
| TC-2 | `publish_work_order_template` on a draft | `version` = 1, `template_no` allocated, `active` = true, one audit row |
| TC-3 · **negative** | `delete_work_order_template` on a template with 4 orders | Refused naming the count; the screen's Delete is disabled with that reason (`BR-SHL-025`) |
| TC-4 · **negative** | `sample_data.py` still contains `WorkOrderTemplate.objects.create` | A test greps the seeder and fails — the OWED note is retired only when the call site is |
| TC-5 · **negative** | Publish a template with zero tasks and zero readings | Accepted with a warning — some jobs are a visit and a signature; the test guards that emptiness is not a refusal |
| TC-6 · **tenant isolation** | Lone Star Ridge calls `update` on a Brazos Bend template id | `404` |
| TC-7 | Duplicate | A new draft carrying every child row, `version` unset, name suffixed *(copy)* |

**4 · Test Data** — `Meter exchange — residential` (`ST-0002`) with the bundle of `US-WRK-014`; `WO-4902 · Meter set` raised from the Electric *New connection* template before the rename.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| the service | — | `WM-10` | `apps/work/templates_svc.py` | functions | — | the only writer of `work_order_templates` and `wot_*` |
| publish | `Work-017` | `WM-10` | `POST /work/templates/{id}/publish` | — | user-input | allocates `template_no`, sets version |
| seeder | — | `WM-10` | `apps/work/sample_data.py` → the service | — | — | no direct model write |

**6 · Acceptance** — **Given** the seeder and the builder, **when** either writes a template, **then** it goes through one service, **and** deleting a referenced template is refused.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---
id: US-WRK-016
epic: EP-WRK-03
module: work
screens: [Work-014, Work-015, Work-016, Work-017, Work-005]
wave: 1
status: ready
blocked_by: []
depends_on: [US-WRK-015]
journeys: [J60, J67]
rules: [BR-WRK-011]
golden_tests: []
finance_calc: none
---
### US-WRK-016 — The eight-step template builder the PO designed and nobody built, with starter packs on step 1 that prefill the rest (`WM-11`)

**1 · Details** — As **a one-or-two-person utility**, I want **to start from a ready-made pack and edit**, so that **I never author seven tasks from a blank page**.

Details · Safety · Tasks · Materials · Readings · Help & support · Signature & completion · Review — r10's own eight steps, *"with exactly the nine sections asked for"*. Step 1 offers **START FROM A PACK**: *Meter exchange 7 tasks · 3 parts · 3 readings* · *New connection 3 · 1 · 1* · *Inspection 4 · 0 · 2* · *Start empty*. *"It prefills safety, tasks, materials, readings and help. Everything stays editable."* Every footer reads *"Step n of 8 · nothing is saved to a work order until you Publish. Editing a published template never changes work already in the field."* Step 8's consequence box: *"Publishing affects new work orders only. The 4 orders already raised from the previous version keep exactly what they were given — nothing in the field changes."* **This replaces `Work-005`**, the blank page whose four sentences were the whole deliverable.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-WRK-011` | Publish is the one write | CONFIRMED |
| `BR-WRK-008` | Copy, never link — the consequence box says it before the button | CONFIRMED |
| B14 rules 1, 3, 11 | `← Back` means previous step; the numbered rail; a consequence box before Publish | CONFIRMED |
| B14 rule 21 | Tailwind only, file on `route-b-migrated.txt` | CONFIRMED |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Press *New template*, pick the *Meter exchange* pack | Steps 2–6 prefilled — 3 safety · 7 tasks · 3 materials · 3 readings · 3 help — every one editable |
| TC-2 · **negative** | Work through steps 1–7 and close the tab | **No** `work_order_templates` row with `active = true`; a draft row only if *Save draft* was pressed |
| TC-3 | Step 8 Review | *METER EXCHANGE — RESIDENTIAL · ELECTRIC · 7 SECTIONS · 26 ITEMS*; each section row with its count and *what it produces on the job* |
| TC-4 · **negative** | Press *Publish* twice quickly | One version, one `ST-` number — idempotent on the draft id |
| TC-5 | The replaced page | `/{tenant}/work/templates` renders `Work-013`, never the four-sentence blank; the old test asserting those sentences is **rewritten, not deleted** |
| TC-6 · **tenant isolation** | Lone Star Ridge's packs | The three platform packs, and none of Brazos Bend's templates as a pack |
| TC-7 · **UI law** | Every file under `features/work/templates/` | On `route-b-migrated.txt` (`G31`); footer copy one sentence per section; no `BR-` string rendered |

**4 · Test Data** — Packs as §1. Template name *Meter exchange — residential* · Electric · Meter exchange · applies to *Electric meter · AMI single-phase · Water meter 5/8"–1"* · Meter fitting · crew 1 · *Standard electrical*.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| pack | `Work-014` | `WS-14` | platform data in `apps/work/packs/` (three packs) | code data | reference-data | prefill only; never stored as a link |
| draft | `Work-014`–`017` | `WS-17` | `work_order_templates` with `active = false`, `version` NULL | row | user-input | *Save draft* |
| Publish | `Work-017` | `WM-10` | `publish_work_order_template` | — | user-input | the one write |

**6 · Acceptance** — **Given** a clerk presses *New template*, **when** they work through eight steps and press *Publish*, **then** *Meter exchange — residential* appears in the list reading *7 tasks · 3 parts · 3 readings* — where the page today shows four sentences.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---
id: US-WRK-017
epic: EP-WRK-03
module: work
screens: [Work-004]
wave: 1
status: ready
blocked_by: []
depends_on: [US-WRK-015]
journeys: [J60, J61]
rules: [BR-WRK-016]
golden_tests: []
finance_calc: none
---
### US-WRK-017 — New Connect step 6 finally proposes work orders from the utility's own templates (`WM-12`)

**1 · Details** — As **a clerk creating a build**, I want **step 6 — *Plans & work orders* — to offer the jobs the enabled services need**, so that **the step named after work orders offers some**.

Today step 6 *"proposes nothing"* and *"the only caller stamps a template id the caller supplies."* Read the enabled services' PUBLISHED templates and offer the resulting list; the clerk removes one and confirms; **the build is created at step 9 with the remaining orders** (`BR-MET-112`). Choosing Electric and Water shows 5 proposed orders; remove one; the build is created with 4.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-WRK-016` | Step 6 proposes from published templates; the clerk may remove; nothing written until step 9 | CONFIRMED — `WM-12` |
| `BR-MET-112` | The wizard writes nothing until step 9 | CONFIRMED |
| `BR-MET-109` | The utility's templates decide the grouping, never the engine | CONFIRMED |
| `OQ-249` | *We schedule it* mode stays disabled with its reason until `EP-WRK-05` lands | OPEN (placement half closed) |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Electric + Water at step 6 | **5** proposed orders (Electric: Service drop → Meter set; Water: Site inspection & mark-out → Tap and service line → Meter set), each carrying its template's `is_gate` |
| TC-2 | Remove *Site inspection & mark-out*, continue to step 9, confirm | The build has **4** orders; each stamps its template and version |
| TC-3 · **negative** | Refresh at step 7 | No connection, no order, no reserved number exists — steps 1–8 issue no request (`BR-MET-112`) |
| TC-4 · **negative** | A Water template in `draft` | **Not** proposed; only published versions are |
| TC-5 | Gas enabled | The four gas jobs proposed with the gate on **Pressure test and light-up**, not Meter set |
| TC-6 · **tenant isolation** | Lone Star Ridge at step 6 | Its own templates, none of Brazos Bend's |
| TC-7 | *We schedule it* | Still disabled: *"crew, skill, date, priority and dispatch come with the Work module"* — one sentence, until `EP-WRK-05` |

**4 · Test Data** — Brazos Bend's published starters for Electric (2), Water (3), Gas (4). New build `CON-26-0129` · `12 Heron Way` · 1 unit · E · W.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| proposed orders | `Work-004` | `WM-12` | none until step 9; then `work_orders` rows via `create_work_order` with `template_id`, `template_version` | list | system-derived | read from `GET /connections/proposed-work-orders?services=` |
| remove | `Work-004` | `WS-04` | wizard state only | — | user-input | — |

**6 · Acceptance** — **Given** Electric and Water are chosen, **when** step 6 opens, **then** five orders are proposed from the utility's own templates, **and** removing one leaves a build of four at commit.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None new. `OQ-249`'s scope half stands; *We schedule it* is `EP-WRK-05`'s.

---
id: US-WRK-018
epic: EP-WRK-03
module: work
screens: [Work-022]
wave: 1
status: ready
blocked_by: []
depends_on: [US-WRK-015, US-WRK-013]
journeys: [J67]
rules: [BR-WRK-012, BR-WRK-008]
golden_tests: []
finance_calc: none
---
### US-WRK-018 — Template versions, and what v2 means: the four v1 orders still read v1 (`WM-40`)

**1 · Details** — As **a supervisor**, I want **to see which version an order was raised from and read v1 after v2 exists**, so that **"copy, never link" is a number on a screen and not a rule in a document**.

`Work-022` — Overview · Usage · Versions · Audit. The Versions tab: *v2 · 28 Feb 2026 · M. Torres · Added Apply tamper seal; opening-read max 999 → 999 · 31 · Current* over *v1 · 04 Jan 2026 · A. Reed · First publish · 6 tasks · 4 · Superseded*; *35 orders raised across 2 versions — the 4 v1 orders still read v1, nothing was rewritten*. Delete disabled while any order references any version; Deactivate stops new orders and leaves the 35 readable. ⚠ Two things in the wireframe are recorded in `03-field-map.md` §5 rather than copied: *"999 → 999"* changes nothing and reads as a slip; the kicker says *40 min · 1 technician* where `Work-013` says *45 min* for the same template.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-WRK-012` | Versioned; orders stamp the version; Delete refused while referenced; Deactivate | CONFIRMED — `WM-40` |
| `BR-WRK-008` | Copy, never link | CONFIRMED |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Publish v2 adding *Apply tamper seal* | Versions tab reads *v2 · 31 orders · Current* above *v1 · 4 orders · Superseded* |
| TC-2 | Open one of the four v1 orders | **Six** tasks, not seven |
| TC-3 · **negative** | Edit v1's task list after v2 is published | Refused — a superseded version is read-only |
| TC-4 · **negative** | Press Delete with 35 orders referencing two versions | Disabled with its reason; the API refuses too (`BR-SHL-025`) |
| TC-5 | Deactivate | `active = false`; `Work-004` step 6 no longer proposes it; the 35 orders open unchanged |
| TC-6 · **tenant isolation** | Lone Star Ridge opens `/work/templates/ST-0002` | Its own `ST-0002` or `404`; never Brazos Bend's |
| TC-7 | Usage tab | *35 orders raised* with a per-version breakdown that sums to 35 |

**4 · Test Data** — `ST-0002` *Meter exchange — residential*: v1 04 Jan 2026 by A. Reed, 6 tasks, 4 orders; v2 28 Feb 2026 by M. Torres, 7 tasks, 31 orders.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| version stamp | `Work-022`, `Work-008` | `WM-40` | `work_orders.template_version` | int | system-derived at raise | never changes |
| what changed | `Work-022` | `WS-22` | `work_order_template_versions.change_note` `[our table — §16 unread; the card says "lists versions with what changed"]` | text | user-input at publish | one sentence |
| orders raised | `Work-022` | `WS-22` | count over `work_orders` by (template_id, template_version) | int | computed-display | sums to the Usage total |

**6 · Acceptance** — **Given** v1 raised four orders, **when** v2 is published, **then** the Versions tab shows both with their counts and a v1 order still shows six tasks.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---
id: US-WRK-019
epic: EP-WRK-03
module: work
screens: [Work-013, Work-014]
wave: 1
status: ready
blocked_by: []
depends_on: [US-WRK-015, US-WRK-006]
journeys: [J60]
rules: [BR-WRK-013, BR-WRK-014]
golden_tests: []
finance_calc: none
---
### US-WRK-019 — The twenty-four seeded starters become editable bundles, gas stays gated on the light-up, and a gate keeps every seeded row read

**1 · Details** — As **a utility on its first day**, I want **the starter templates to be real templates I can open, edit and delete**, so that **the rows seeded since wave 6 stop being inert**.

Blueprint §11: *"Twenty-four rows, each carrying a name, a scope and a gate flag — no tasks, no parts, no readings."* Across eleven services: Electric 2 · Water 3 · Gas 4 · Sewer 1 · Trash 1 · Storm water 0 · Solar 4 · Broadband 2 · Thermal/heat 3 · Battery 2 · Fire 2 — **8 carry a gate, 3 deliberately do not**, each absence stored with its reason. *"THE ONE ROW A COPYING LANE GETS WRONG: Gas is gated on the light-up, not the meter set… A lane that copies electric's shape onto gas will bill a customer who has no gas."* The seeded rows are marked (`is_sample`) on `Work-013` and re-seeded through the service (`US-WRK-015`). **And the gate (`CR-070` §12 gate 3):** every row `sample_data.py` writes is served by `GET /work/templates` and rendered by `Work-013`.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-WRK-013` | Starters marked and editable; gas gated on light-up; three no-gate reasons stored | CONFIRMED |
| `BR-WRK-014` | Every seeded starter row has a reader — gate | PROPOSED |
| `BR-MET-109` | Ready-to-use templates the utility then develops | CONFIRMED |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Seed a tenant selling all eleven services | 24 rows; 8 with `is_gate`; the gas gate is *Pressure test and light-up* |
| TC-2 · **negative** | Assert the gas *Meter set* row's `is_gate` | **false** — the test that a copying lane would break |
| TC-3 | Sewer · Storm water · Solar | Zero gates each, and a stored reason: *gated on the water service it derives from* · *assessed from records, no visit* · *the gate is permission to operate, which names no step* |
| TC-4 | Open a starter on `Work-013` | Marked *seeded*; editable; deletable while no order references it |
| TC-5 · **tenant isolation** | Two tenants seeded | 24 rows each, no shared row |
| TC-6 · **gate** | Remove the Fire starters from the list endpoint's queryset | The gate FAILS naming the two unread rows — **proved RED first** (law 7), then restored |

**4 · Test Data** — The 24 rows of blueprint §11 Figure 10, gate per service: Electric → Meter set · Water → Meter set · Gas → **Light-up** · Sewer → none · Trash → Container delivery · Storm water → none (0 rows) · Solar → none · Broadband → Activate · Thermal/heat → Meter set · Battery → Commissioning · Fire → Service connection.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| is_sample | `Work-013` | exists | `work_order_templates.is_sample` | bool | system | shown as *seeded* |
| no-gate reason | — | §11 | `work_order_templates.no_gate_reason` `[our column — the blueprint says the absence "is stored as data with its reason"; §16 unread]` | text NULL | system | present iff the service has no gate |
| the gate | — | `CR-070` §12 | `10-scripts/gates/g7x_seeded_starters_have_a_reader.py` | check | — | compares `sample_data.py`'s rows to the list endpoint |

**6 · Acceptance** — **Given** a fresh tenant, **when** it is seeded, **then** 24 starters appear on `Work-013` as editable bundles with gas gated on the light-up, **and** a seeded row nothing serves fails the build.

**7 · Finance Calculation** — N/A — but the gas gate is what stands between a fitted meter and a bill for gas nobody has, which is why TC-2 exists.

**8 · Open Questions** — None.
