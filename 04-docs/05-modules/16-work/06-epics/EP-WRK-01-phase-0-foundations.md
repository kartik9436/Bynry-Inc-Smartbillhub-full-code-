# EP-WRK-01 — Phase 0: a work order without a build, the fifteen actions, the approval queue, and the module's skeleton

**Module:** work · **Wave:** phase **0** of `CR-070` · **Screens:** `Work-001` · `Work-002` · `Work-006` · `Work-007` (first visible) · `Work-009` · **Status:** draft (`CR-070`, written 2026-09-03 from the *Work Module Blueprint*, read at `2.128.2`; §15–§21 unread)

## Scope

**In:** the three free wins the blueprint names — `WM-01` (`connection_id` nullable), `WM-02` (mount the finished write actions), `WM-03` (the approval queue) — plus three things `CR-070` §11 phase 0 lists as tasks and this module writes as stories so they cannot be skipped: the honest state of the two screens no card covers (`Work-001`, `Work-006`), the module's own app with its read-only seams and the boundary gate (task 0.4, §12 gate 1), and the demo fixture (`CR-070` §3).

**Out:** every new table (phase 1 onward), the dispatcher's columns (`EP-WRK-05`), anything a technician touches.

**Exit test of the phase (`CR-070` §11):** *a clerk records a leak investigation on an existing meter — which is impossible today — holds it, releases it, and it appears in the approval queue.* **On a deployed build, not a green suite.** ⚠ *The CR's sentence mixes two records — hold and release act on a CONNECTION, and a leak investigation on an existing meter has none. Read it as two proofs on one build: the leak investigation is raised, its field result arrives and it appears in the queue; a build (`CON-26-0117`) is held and released from `Work-002`. Amended in the CR 2026-09-03 — `DEF-WRK-3600`.*

⚠ **NO DECISION IS NEEDED FOR ANY STORY HERE**, and every *"as built"* claim is `UNVERIFIED` until a lane re-reads the code (`01-overview.md` §4): the predecessor lane re-verified `connection_id NOT NULL` at `connections.py:699–701` and the sixteen service names in `connections.py` on 2026-09-03, at HEAD `654034ed`.

## Capability matrix (list screens only — B9 conformance)

| Screen | Search fields | Filters | Default sort | Sortable | Columns default/available | Row actions | Bulk actions | Export |
|---|---|---|---|---|---|---|---|---|
| `Work-001` New connects (exists) | connection, premise | none — segment strip removed (`OQ-371`) | target date, soonest first | none drawn | Connection · Premise · Units · Services · Orders · Target · Waiting on · State | 👁 | — | — |
| `Work-009` Awaiting approval (new read) | order, connection, premise | service · outcome | completed, oldest first | Completed · Waiting | Order · Connection · Premise · Service · Outcome · Completed · Waiting | 👁 · ✓ accept | — | — |

## Stories

---
id: US-WRK-001
epic: EP-WRK-01
module: work
screens: [Work-007, Work-002]
wave: 0
status: built
blocked_by: []
depends_on: []
journeys: [J62]
rules: [BR-WRK-006]
golden_tests: []
finance_calc: none
---
### US-WRK-001 — A work order may exist without a connection: `connection_id` goes nullable, `premises_id` and `account_id` sit beside it (`WM-01`)

**1 · Details** — As **a clerk**, I want **to record a leak investigation or a meter exchange on an existing meter**, so that **a job that is not part of a new build can exist at all**.

The blueprint's one structural blocker, in its words: *"work_orders.connection_id is NOT NULL. Every work order in the product must belong to a new-connection build. A leak investigation, a meter exchange, a reconnect or a backflow test — the eight job types the Product Owner's own dispatcher draws — cannot be recorded at all, not even by hand."* One migration makes the column nullable and adds `premises_id` and `account_id` beside the `asset_id` that already exists and is written by nothing. **Our addition (`BR-WRK-006`): a CHECK that at least one anchor is named**, so relaxing the column does not create an order attached to nothing.

Entry: the migration. Exit: `create_work_order()` accepts a payload with no connection and a premises; the row appears on `Work-007` once that screen exists (phase 2) and, until then, is reachable through `GET /work-orders` (`US-WRK-026`) — **in phase 0 the exit is the exit test itself, on a deployed build.**

⚠ **THE TABLES LIVE IN `apps/metering/connections.py` TODAY.** This migration is `metering`'s, not `work`'s — the move of the six tables into `apps/work/` is `US-WRK-005`'s question and is answered there. **Do not write `work/0001` for a column on a metering table.**

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-WRK-006` | A work order may exist without a connection; premises, account and asset anchors beside it; at least one anchor required | PROPOSED — `WM-01` + our CHECK |
| CLAUDE.md hard rule 1 | RLS `FORCE` unchanged on `work_orders` | CONFIRMED |
| `CR-070` §14 | Phase 0 rolls back cleanly — a nullable column and mounted buttons | CONFIRMED |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Raise *Leak investigation* at `77 Cedar Ct` (premises only, no connection) | Row saved; `order_no` `WO-4832` allocated from the tenant's series; `connection_id` NULL; `premises_id` set |
| TC-2 | Raise an order with `account_id = A-10688` and nothing else | Saved — an account is an anchor |
| TC-3 · **negative** | Raise an order with **no** connection, premises, account or asset | Refused by the CHECK constraint, on PostgreSQL, before any row exists |
| TC-4 · **negative** | The migration run against a database holding existing orders | Every existing row keeps its `connection_id`; zero rows change |
| TC-5 · **tenant isolation** | Lone Star Ridge WSC lists orders while Brazos Bend holds `WO-4832` | Zero Brazos Bend rows under Lone Star's `app.tenant_id`; RLS `FORCE` unchanged (isolation probe) |
| TC-6 · **PostgreSQL** | The CHECK is asserted on real PostgreSQL 16 | SQLite does not run the constraint the same way (law 14); the test is marked PG-only and fails if skipped in CI |

**4 · Test Data** — Tenant Brazos Bend Utilities (`brazosbend`). Premises `77 Cedar Ct` · account `A-10891`. Order `WO-4832` · *Leak investigation* · Water · High · due today 17:00 · Queued (the dispatch columns are phase 2; in phase 0 only the anchors and the state are asserted). Isolation tenant Lone Star Ridge WSC.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| `connection_id` | `Work-002` | `WM-01` | `work_orders.connection_id` | uuid FK, **NULL allowed** | system | was NOT NULL (`connections.py:699–701`) |
| `premises_id` | `Work-007` | `WM-01` | `work_orders.premises_id` | uuid FK → `premises` | user-input | new column |
| `account_id` | `Work-007` | `WM-01` | `work_orders.account_id` | uuid FK → `accounts` | user-input | new column; ⚠ a cross-module FK is part of the reviewed interface set (B2 §2) |
| anchor CHECK | — | ours | `ck_work_orders_has_anchor` | constraint | system | at least one of connection · premises · account · asset |

**6 · Acceptance** — **Given** a meter at `77 Cedar Ct` with no new-connection build, **when** a clerk raises a leak investigation, **then** the order is saved with a `WO-` number and no connection, **and** an order naming no anchor at all is refused by the database.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---
id: US-WRK-002
epic: EP-WRK-01
module: work
screens: [Work-002]
wave: 0
status: ready
blocked_by: []
depends_on: [US-WRK-001]
journeys: [J61, J62]
rules: [BR-WRK-006]
golden_tests: []
finance_calc: none
---
### US-WRK-002 — Mount the finished write actions: fourteen writers and two readers that only a Python shell can reach (`WM-02`)

**1 · Details** — As **a clerk on a connection**, I want **the greyed *Add work order*, *Continue setup* and *Cancel connection* controls to work**, so that **the engine that already exists can be driven from a screen**.

The blueprint's §7 lists the capabilities and their state: *"of the eighteen things this module can do, only three can be reached from outside a Python shell: committing the wizard, receiving a field result, and accepting one."* **This story mounts the rest.** ⚠ **THE COUNT IS PINNED HERE BECAUSE THREE DOCUMENTS DISAGREE:** the blueprint's headline says *"fifteen finished write actions"*; its §7 table lists **sixteen names — fourteen writers and two readers** (`characteristic()` and `outstanding_work`); the predecessor lane counted **thirteen route-less writers plus `set_characteristic`**. **The list this story mounts is the fourteen writers**, named in §5 below, and the two readers ride on `GET /connections/{id}`. *"Read them before rewriting them; they are written and tested"* (`CR-070` §11 task 0.2).

Entry: `Work-002`'s three page actions and the row action ⚡ *raise work* (B14 rule 15). Exit: each writer has one route in `07-endpoints.md` §1, and `Work-002`'s counter moves from *5 of 7* to *5 of 8* when an eighth order is added.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-SHL-025` | Forbidden actions render disabled-with-reason; the server enforces every mutating call | CONFIRMED |
| `BR-MET-109` | Batching is the utility's choice — *Add work order* adds ONE, and the clerk may add as many as they want | CONFIRMED |
| `BR-WRK-006` | The raise accepts an order without a connection | PROPOSED |
| CLAUDE.md hard rule 7 | Every action already writes its audit row — the five audit actions the blueprint counts stay | CONFIRMED |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | On `CON-26-0117`, press *Add work order*, fill *Meter set / per asset / our crew* | An eighth row appears; the header reads **5 of 8**; one audit row |
| TC-2 | Hold, then release `CON-26-0119` from the screen | State reads *On hold* then re-derives (blueprint §9.1 Figure 6 — seven tests, first match wins) |
| TC-3 · **negative** | Call `POST /connections/{id}/cancel` as a Billing Clerk | `403`, no write — the server enforces regardless of the button |
| TC-4 · **negative** | `transition_service` from `activated` to `pending` | Refused — terminal is terminal (Figure 7); the refusal sentence is ≤ 6 words (B14 rule 33) and in all eleven catalogues (`g15`) |
| TC-5 · **negative** | Mount all fourteen and run `G52` (role-gated doors) | The gate's *unreached* count for `connections.py` falls to **0**; a route added without its service-level guard is RED |
| TC-6 · **tenant isolation** | Lone Star Ridge calls `POST /connections/{brazos-id}/hold` | `404`, byte-identical to an absent row |
| TC-7 | Every one of the fourteen | Exactly one route each in `07-endpoints.md` §1; a test enumerates the module's service functions and fails on a writer with no route (the `built is not wired` guard, `G13`'s shape) |

**4 · Test Data** — `CON-26-0117` · `500 Main St` · 25 units · E · W · G · S · **5 of 7** complete (`WO-4901`…`WO-4907`). `CON-26-0119` · `18 Larkspur Ln` · *On hold · permit*. Actors: M. Torres (supervisor), Priya Menon (Billing Clerk — the negative actor the substrate epic already uses).

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| The fourteen writers | `Work-002` | blueprint §7 | `create_work_order` · `create_connection` · `add_connection_service` · `transition_service` · `submit_connection` · `hold_connection` · `release_connection` · `cancel_connection` · `set_waiting_on` · `mark_outstanding_work` · `close_outstanding_work` · `create_owner_account` · `tag_charges_to_account` · `set_characteristic` | service functions | — | each gets one route; **none is rewritten** |
| The two readers | `Work-002` | blueprint §7 | `characteristic()` · `outstanding_work()` | reads | — | served inside `GET /connections/{id}` |
| *Add work order* | `Work-002` | `WS-02` | `POST /work-orders` | — | user-input | mode · scope · service · unit; `BR-MET-109` |

**6 · Acceptance** — **Given** `CON-26-0117` at 5 of 7, **when** a clerk adds a meter-set order from the screen, **then** the list reads 5 of 8 and the audit tab names the clerk — **and** a clerk without the permission is refused by the server, not merely by a grey button.

**7 · Finance Calculation** — N/A. (`tag_charges_to_account` moves a charge's TAG, not money.)

**8 · Open Questions** — None. `OQ-371` (list segments) and `OQ-376` (the letter) touch `Work-001` and `Work-003`, not these routes.

---
id: US-WRK-003
epic: EP-WRK-01
module: work
screens: [Work-009]
wave: 0
status: ready
blocked_by: []
depends_on: [US-WRK-002]
journeys: [J61, J64]
rules: [BR-WRK-007]
golden_tests: []
finance_calc: none
---
### US-WRK-003 — The approval queue, across every connection: one list of every order where `accepted_by` is null (`WM-03`)

**1 · Details** — As **a supervisor**, I want **one worklist of every order the field has finished and nobody has accepted**, so that **the acceptance rule stops being something I stumble into one connection at a time**.

*"One dispatcher-shaped thing already exists in the schema with no screen: every order where `accepted_by` is null is an order the field has finished and nobody has approved."* This is a single query over data that exists, has an approval endpoint and writes an audit row. **No new table.** `Work-009` lists Order · Connection · Premise · Service · Outcome · Completed · Waiting, oldest waiting first, with a footer *"3 orders · oldest waiting 6 days"*, and the row action ✓ opens `Work-003` where the null is rendered as the sentence *"Nobody has accepted this yet."*

⚠ **THE QUEUE INCLUDES ORDERS WITH NO CONNECTION** once `US-WRK-001` lands — the Connection column reads a dash and the Premise column carries the anchor. Phase 0's exit test ends here.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-WRK-007` | The queue is `accepted_by IS NULL AND state = completed`, across every connection and anchor; no new table | CONFIRMED — `WM-03` |
| `BR-MET-110` | A person accepts; only then does service go live | CONFIRMED |
| B14 rules 16, 17 | Pagination footer; empty state says what is missing and the action that fills it | CONFIRMED |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Three completed, unaccepted orders across three connections | Three rows; footer *"3 orders · oldest waiting 6 days"*; sorted oldest first |
| TC-2 | Accept `WO-4906` from `Work-003` | The row leaves the list; the count reads **2**; `accepted_by` = M. Torres; the set read `[{G-4417-882, 0}]` posts; the connection re-derives |
| TC-3 · **negative** | An order in `state = planned` (not yet completed) | **Not** in the queue — the null alone is not enough; the field must have sent something |
| TC-4 · **negative** | Accept `WO-4906` a second time | Refused, idempotently — *"refuses a second approval"* |
| TC-5 · **tenant isolation** | Lone Star Ridge opens `Work-009` | Its own unaccepted orders only; Brazos Bend's three absent |
| TC-6 | The empty state | *"Nothing is waiting for you."* plus what fills it — a job the field closes lands here (B14 rule 17; ≤ 6 words on the label) |
| TC-7 | A completed order with `connection_id` NULL (phase 0's leak investigation) | Appears; Connection reads a dash; Premise reads `77 Cedar Ct` |

**4 · Test Data** — `WO-4906` · Meter set · `CON-26-0117` · `500 Main St · Unit 14` · Gas · Passed · 28 Mar 2026 · 6 days · `set_reads: [{meter_no: G-4417-882, value: 0}]` · `photo_ref img/2026-03-28/4417.jpg` · tech M. Chen · their reference `NGX-88410`. `WO-4903` · Tap and service line · `CON-26-0122` · Ridgeway Mews · Water · Partially done · 31 Mar · 3 days. `WO-4917` · Container delivery · `CON-26-0128` · `91 Fen Close` · Trash · Passed · 02 Apr · 1 day.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Waiting | `Work-009` | `WS-09` | derived: today − `work_orders.completed_at` | days | computed-display | in words, never a raw timestamp |
| Outcome | `Work-009` | `WS-09` | `work_orders.outcome` | enum (five tokens) | system | passed · failed · partially_done · cancelled · waiting_on_someone_else |
| Accept | `Work-003` | exists | `POST /work-orders/{id}/accept` | — | user-input | refuses if not completed; refuses a second accept |

**6 · Acceptance** — **Given** three finished, unaccepted orders, **when** a supervisor opens *Awaiting approval*, **then** all three show with the oldest waiting first, **and when** one is accepted, **then** it leaves the list and its set read is on the meter's history.

**7 · Finance Calculation** — N/A.

**8 · Open Questions**

| OQ | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| `OQ-376` | The letter's source kind | Only the fourth consequence of Accept — the letter is queued and refused with its reason, exactly as today (`US-WRK-035`) | PO | OPEN |
| `OQ-WRK-1492` | Who may accept | Nothing in phase 0 — the endpoint's reach is what it is today; `US-WRK-022` carries the stub | PO | OPEN |

---
id: US-WRK-004
epic: EP-WRK-01
module: work
screens: [Work-001, Work-006]
wave: 0
status: built
blocked_by: []
depends_on: []
journeys: []
rules: [BR-WRK-005]
golden_tests: []
finance_calc: none
---
### US-WRK-004 — The two screens no card covers: New connects lists builds, not jobs; the Work rail entry becomes the shell for the dispatcher

**1 · Details** — As **the next lane**, I want **the two Work surfaces with NO COMMITMENT stated honestly**, so that **nobody builds a dispatcher onto a list of builds or removes a rail entry the prototype draws**.

`Work-001` (`WS-01`, `/{tenant}/connections`, exists · `S86` reserved to B18) *"lists builds, not jobs"* — every row is a connection and a work order is never visible from it. Its segment strip *All · In progress · Waiting · Partly activated · Done* was **removed rather than faked** because a build can satisfy two exclusive tabs at once; that is `OQ-371`, still *"OPEN — blocking the S86 segment strip"*, and this story changes nothing about it. `Work-006` (`WS-06`, `/{tenant}/work`) resolves to the registered not-built-yet destination between Payments and Finance, where r10 puts it; **with the placement ruled it becomes the shell for `Work-007`** in phase 2 (`US-WRK-027`), and until then it is correct as it is.

The one change this story makes: `Work-006`'s not-built-yet copy stops saying the placement is undecided — *"Whether SMARTBillHub takes on field work … is still being decided"* is now false (PO 2026-09-03) — and says instead that the Work module is being built and this page becomes its dispatcher. **One sentence** (B14 rule 32).

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-WRK-005` | `Work-001` ↔ `S86` (reserved), `Work-006` ↔ the rail entry; both ids recorded, neither moves | CONFIRMED |
| `OQ-371` | Exclusive segments on the connection list | OPEN — unchanged here |
| PO 2026-08-25 | *"Just keep it black - and show note that Work orders not yet build"* — the blank-page pattern `Work-005` follows and `Work-006` inherits | CONFIRMED |
| B14 rule 32 | One sentence per section; no rule id in clerk-facing copy | CONFIRMED |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Open `/{tenant}/connections` | Eight builds sorted by target date; **no work order visible**; no segment strip |
| TC-2 · **negative** | `GET /connections?segment=waiting` | The server raises for any segment but `all` — unchanged, `OQ-371` |
| TC-3 | Open `/{tenant}/work` | The not-built-yet page; its sentence names the Work module as being built and this page as its future dispatcher; **no** *"still being decided"* |
| TC-4 · **negative** | grep the rendered copy of both screens for `OQ-`, `BR-`, `WS-`, `Work-0` | Zero hits (B14 rule 31) |
| TC-5 · **tenant isolation** | Lone Star Ridge opens `Work-001` | Its own builds; Brazos Bend's `CON-26-0117` absent |
| TC-6 | The rail | *Work* sits between *Payments* and *Finance*, as r10 draws it |

**4 · Test Data** — The eight builds of `WS-01`: `CON-26-0119` `18 Larkspur Ln` 1 unit W·S 2 of 5 12 Mar permit On hold · `CON-26-0117` `500 Main St` 25 E·W·G·S 5 of 7 02 Apr inspection Partly activated · `CON-26-0121` `7 Kestrel Ct` · `CON-26-0122` Ridgeway Mews 12 · `CON-26-0126` `44 Alder Row` · `CON-26-0128` `91 Fen Close` · `CON-26-0124` `2 Willow Bank` Requested · `CON-26-0110` `3450 Oak Ridge Dr` Activated. KPI tiles: OPEN 7 · WAITING ON INSPECTION 2 · PARTLY ACTIVATED 3 · UNITS AWAITING ACTIVATION 42 · OLDEST 19d.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| State | `Work-001` | exists | `connections.state` (a cache written only by `refresh_connection_state()`) | enum, seven | system-derived | never a WHERE clause on a derived value |
| Not-built-yet sentence | `Work-006` | this story | locale key, eleven catalogues (`g15`) | text | — | one sentence; no id |

**6 · Acceptance** — **Given** the rail, **when** a clerk opens *Work*, **then** they read one honest sentence about what is coming and see no dead control — **and** the connection list still shows builds and never jobs.

**7 · Finance Calculation** — N/A.

**8 · Open Questions**

| OQ | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| `OQ-371` | Which segment holds a build that is both Partly activated and waiting | The segment strip on `Work-001` only | PO | OPEN |

---
id: US-WRK-005
epic: EP-WRK-01
module: work
screens: []
wave: 0
status: built
blocked_by: []
depends_on: []
journeys: []
rules: [BR-WRK-001, BR-WRK-002]
golden_tests: []
finance_calc: none
---
### US-WRK-005 — `apps/work/`: the eleventh module, its read-only seams, the migrated-list entry, and the gate that proves it writes nothing of anyone else's

**1 · Details** — As **the lane that opens phase 1**, I want **the module to exist with its boundary already enforced**, so that **the first table lands inside a wall rather than before one**.

`CR-070` §10 draws the folder: `models.py` · `migrations/` (RLS `FORCE` in the SAME migration as each table) · `api.py` · `services.py` · `selectors.py` · `templates_svc.py` · `dispatch.py` · `rules.py` · `seams/` (`assets_seam` · `metering_seam` · `customers_seam` · `tenancy_seam` — **read only, one file each**) · `sample_data.py`. Frontend: `07-frontend/src/features/work/` plus the phone surface, **both added to `07-frontend/src/styles/route-b-migrated.txt` in the first commit** or every Tailwind class renders as nothing while `tsc` passes (B14 rule 21, `DEF-974`).

**2b — this story has no screen by design.** Its frontend part is the migrated-list entry and the empty feature folder; step 6 accepts that because the absence is stated, not skipped.

⚠ **THE SIX EXISTING TABLES STAY WHERE THEY ARE IN PHASE 0.** `connections`, `connection_services`, `work_orders`, `work_order_templates`, `connection_todos`, `service_characteristics` live in `apps/metering/connections.py` — *"deliberately, so two lanes editing one models module could not fork the migration graph."* **Whether and when they MOVE into `apps/work/` is not decided by this story**; `03-field-map.md` §4 records the choice as PENDING §16 and phase 1's first migration. The seams are how Work reads them meanwhile, and the gate below is what makes the eventual move safe.

**The gate (`CR-070` §12 gate 1):** `10-scripts/gates/g7x_work_writes_nothing_foreign.py` reads `apps/work/**` and fails on any `.objects.create`, `.save(`, `.update(`, `.delete(` or raw SQL against a model whose `app_label` is not `work`, and on any import from another app's `models` outside `seams/`. **Shown RED first** by adding one direct write to `assets.Asset` (law 7).

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-WRK-001` | Work is its own module and owns the list | CONFIRMED — PO 2026-09-03 |
| `BR-WRK-002` | Work writes no other module's tables; one read-only seam per module; a gate | CONFIRMED |
| B14 rule 21 + per-file clause | Tailwind only in a file on `route-b-migrated.txt` | CONFIRMED — `G31` |
| `CR-070` §2(a) | The module map is amended, dated, **in the same commit as the first migration** | CONFIRMED |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | `INSTALLED_APPS` and the module map | `apps.work` present; CLAUDE.md's module map names it as the eleventh code module **in the commit that carries `work/0001`**, not before, not after |
| TC-2 · **gate** | The gate over `apps/work/` as written | PASS with zero findings |
| TC-3 · **negative · gate** | Add `Asset.objects.filter(pk=…).update(status="retired")` to `apps/work/services.py` | The gate FAILS naming the file, the line and the foreign model — **first proved RED, then the line removed** (law 7) |
| TC-4 · **negative · gate** | `from apps.assets.models import Asset` in `apps/work/dispatch.py` (outside `seams/`) | FAILS — imports of another app's models are allowed only inside `seams/` |
| TC-5 · **negative** | A Tailwind utility in `features/work/OrdersPage.tsx` with the folder NOT on `route-b-migrated.txt` | `G31` reports the file; the utility renders as nothing — the test asserts the LIST entry exists, not that the class is in the DOM (`DEF-974`'s lesson) |
| TC-6 | Each seam file | Exposes reads only; a test imports each and asserts no function name starts with `create_`, `set_`, `update_`, `delete_`, `post_` |
| TC-7 · **tenant isolation** | Every seam read with `app.tenant_id` unset | Zero rows — the seams go through the owning module's RLS-forced tables |

**4 · Test Data** — No data. The negative cases are one-line mutations of the module's own source, applied and reverted inside the test.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| `seams/assets_seam.py` | — | `CR-070` §10 | reads `assets` (asset by id, type, install date, certification life) | functions | — | read-only |
| `seams/metering_seam.py` | — | `CR-070` §10 | reads connections, meters; **calls** metering's set-read door (`US-WRK-046`) | functions | — | the ONE call that writes, and it writes through metering's own service |
| `seams/customers_seam.py` | — | `CR-070` §10 | reads accounts, premises, customer contact | functions | — | read-only |
| `seams/tenancy_seam.py` | — | `CR-070` §10 | reads `Area`, `CertificationType`, number series, services | functions | — | read-only |
| `route-b-migrated.txt` | — | B14 rule 21 | `features/work/**`, `features/work/mobile/**` | list | — | present in the first commit |

**6 · Acceptance** — **Given** the module exists, **when** the gate runs, **then** it passes — **and when** one foreign write is added anywhere under `apps/work/`, **then** it fails naming the line.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None. (Where the six existing tables eventually live is a phase-1 decision recorded in `03-field-map.md` §4, not a question for the PO — it moves no rule.)

---
id: US-WRK-006
epic: EP-WRK-01
module: work
screens: []
wave: 0
status: ready
blocked_by: []
depends_on: [US-WRK-005]
journeys: [J60, J61, J62, J63, J64, J65, J66, J67]
rules: [BR-WRK-013]
golden_tests: []
finance_calc: none
---
### US-WRK-006 — The demo fixture: crews, technicians with certifications, a published template with tasks and readings, and a job in every lifecycle state

**1 · Details** — As **the Product Owner walking the deployed build**, I want **the sample utility to arrive with field work already in every state**, so that **each screen has something on it the day it lands and every journey has its upstream**.

`CR-070` §3's demo-fixture row, made a story so it grows with the phases: **phase 0** — nothing new (the 24 starter rows and the seven `CON-26-0117` orders already seed); **phase 1** — the six lookups, the parts register (`MTR-W58`, `MTR-E1P`, `SEAL-01`, `GSKT-STD`, `GAUGE-BF`), and `Meter exchange — residential` published as v1 then v2 with its 7 tasks · 3 parts · 3 readings · 3 safety · 3 help; **phase 2** — D. Ortiz, M. Chen, R. Patel, J. Kaur (cert expiring), T. Osei (invited), Crew B (3), Apex Utility Svc (contractor); the ten open orders of `WS-07` with their sources; `WO-4907` failed with its follow-up `WO-4909`; the seven rules of `WS-26`, six on. **Idempotent** (`BR-TEN-063`'s replay is a no-op) and **service-shaped** (`DEF-2397`: seed only for services the tenant sells).

**2b — no screen; this story is data.** Its screens are everybody else's.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-WRK-013` | Seeded starters marked as samples; gas gated on light-up | CONFIRMED |
| `BR-TEN-063` | The seed is idempotent | CONFIRMED |
| `DEF-2397` | Sample data is service-shaped | CONFIRMED |
| hard-won law 6 | Diff the running app against `05-prototype/` — the fixture carries r10's own figures so the diff is possible | CONFIRMED |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Seed Brazos Bend twice | Identical row counts both times; no duplicate `WO-` number |
| TC-2 | Seed a tenant selling Water only | No electric template, no `MTR-E1P`, no electric orders; the water starters and `MTR-W58` present |
| TC-3 · **negative** | Seed with the phase-2 tables absent (a phase-0 database) | The phase-2 half is skipped by capability, not by exception — the seeder checks for the table and says so in its `blocks[]` |
| TC-4 · **negative** | A seeded order with `outcome = failed` and no follow-up | The test FAILS — `WO-4907` must carry `WO-4909` (`BR-WRK-054`) once phase 2 lands |
| TC-5 · **tenant isolation** | Seed Brazos Bend, then count Lone Star Ridge's work tables | Zero rows in every one |
| TC-6 | The performance figures | Six job types summing **740 jobs and `$56,337`**, r10's own, so `Work-027` can be diffed against the prototype |

**4 · Test Data** — Exactly the figures named in §1 and in the stories that consume them; **this story is where they are written once.** Technicians and their skills as `WS-23`: D. Ortiz Water II · Meter I · Confined space 07:00–16:00 · M. Chen Electric I · Reads · HV awareness (expires Sep 2026) · R. Patel Senior · Water I · Reads · Backflow (exp Jan 2028) · First aid/CPR (exp Sep 2027) · J. Kaur Water I · Confined space **expires Aug 20** · Crew B (3) Water III · Excavation · Traffic control · Apex Utility Svc Water II, by arrangement. ⚠ **Three states of *Meter exchange — residential*, stated once here (2026-09-03, `DEF-WRK-3572`):** the Product Owner's walk-through seed holds it at **v2 current (7 tasks · 45 min · 31 orders) over v1 superseded (6 tasks · 40 min · 4 orders)** — `Work-022`'s drawing and §1's *"v1 then v2"*; **`J67`** starts from the **v1-only** state (v1 published 04 Jan 2026 by A. Reed, four orders `WO-4835`–`4838`, one on D. Ortiz's phone) and publishes v2 itself; **`J60`** starts from the state **before it exists** (`Work-019` reads `ST` next 1) and authors it as a first publish with the pack's 7 tasks. The drawn `ST-0002` is the seed's own allocation and `J60`'s `ST-0001` is a fresh counter's — **a spec asserts the template by name, version and task count and never by its `ST-` string**, exactly as it asserts an order by its key and never by a drawn `WO-` number (`03-field-map.md` D-16).

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| `is_sample` | every Work table | `BR-TEN-063` pattern | `*.is_sample` | boolean | system | every seeded row carries it, as `work_order_templates.is_sample` already does |
| `sample_data_runs.blocks[]` | — | `CR-064` | existing | jsonb | system | the Work block reports what it seeded and what it skipped |

**6 · Acceptance** — **Given** a fresh Brazos Bend, **when** it is seeded, **then** every Work screen in the current phase shows r10's own figures, **and** seeding again changes nothing.

**7 · Finance Calculation** — The fixture carries `$56,337` across 740 jobs as a **display figure on the performance tab only**; nothing posts (`BR-WRK-004`).

**8 · Open Questions** — None.
