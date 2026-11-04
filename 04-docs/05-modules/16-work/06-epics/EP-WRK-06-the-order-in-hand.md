# EP-WRK-06 — The order in hand: its own copies of the template, the six-tab detail, the consequence chain behind a failed outcome, the letter that is refused, and the signature

**Module:** work · **Wave:** phase **2** of `CR-070` · **Screens:** `Work-008` · `Work-003` · `Work-002` · `Work-009` · `Work-012` · **Status:** draft (`CR-070`, 2026-09-03; §15–§21 unread)

## Scope

**In:** `WM-18` the order's own copies · `WM-19` the six-tab detail · `WM-25` the consequence chain behind `failed` · `WM-27` a connection message kind (cites `OQ-376`) · `WM-30` attachments and the customer's signature.

**Out:** readings that post (`EP-WRK-09`) · the photograph's two columns (`EP-WRK-09`) · the report (`EP-WRK-10`).

**Blueprint §10, the PO's sentence the built half rests on (`BR-MET-110`):** *"Work order will send the data and confirm from field; utility staff will review these work order, accept them and use data from them to activate these services or confirm the installation is completed."* One press, four consequences — *"and the fourth has been refused at the door since it shipped."*

## Capability matrix (list screens only — B9 conformance)

No B9 list screen. `Work-008` is a six-tab detail; `Work-003` a drawer.

## Stories

---
id: US-WRK-032
epic: EP-WRK-06
module: work
screens: [Work-008]
wave: 2
status: ready
blocked_by: []
depends_on: [US-WRK-014, US-WRK-024]
journeys: [J62, J67]
rules: [BR-WRK-008]
golden_tests: []
finance_calc: none
---
### US-WRK-032 — The order's own copies of its template: tasks, readings, materials — and safety, help, details — copied at raise, never read through the link (`WM-18`)

**1 · Details** — As **a technician holding a job**, I want **the job I am standing in front of to be exactly what it was when it was raised**, so that **a template edited this afternoon changes nothing in my hand**.

`work_order_tasks`, `work_order_readings`, `work_order_materials` — *"copied onto the order when it is raised, never read through the template link."* ⚠ **THE CARD NAMES THREE TABLES AND THE `WS-08` CAPTION SAYS *"the six order instance tables (WM-18)"*.** `WS-11` shows safety and help copied too, and `WS-10` shows the Details ticks (access notes, gate code) riding with the job. **This story copies all six** — tasks, readings, materials, safety, help, details — and records the three-versus-six discrepancy in `03-field-map.md` §5 for §16 to settle. Opening `WO-4822` shows 7 task checkboxes, 3 readings with their units and ranges (0–99,999 kWh and 0–999 kWh), 3 parts with planned quantities — *"and editing the template afterwards changes none of them."*

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-WRK-008` | Copy, never link; the version is stamped | CONFIRMED — `WM-18`, `WM-R-02` |
| `BR-WRK-015` | The copied reading carries its unit | CONFIRMED |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Raise `WO-4822` from *Meter exchange — residential* v2 | 7 task rows, 3 reading rows (kWh 0–99,999 · kWh 0–999 · serial), 3 material rows, 3 safety rows, 3 help rows, 1 details row; `template_version = 2` |
| TC-2 · **negative** | Rename task 3 on the template, then open `WO-4822` | The order still reads *Isolate supply & remove old meter* — unchanged |
| TC-3 · **negative** | Publish v3 with eight tasks | `WO-4822` still has seven |
| TC-4 · **negative** | Raise an order from a template in `draft` | Refused — only a published version may be copied |
| TC-5 · **tenant isolation** | Lone Star Ridge reads `WO-4822`'s checklist | `404` |
| TC-6 | A schema test | `work_order_tasks` has **no** FK to `wot_tasks` — a copy, not a link; the only template reference on the order is `template_id` + `template_version` |
| TC-7 | An order raised with no template (a one-off with no checklist) | Zero child rows; the detail's Checklist tab shows its empty state (B14 rule 17), not an error |

**4 · Test Data** — `WO-4822` raised 15 Mar 2026 from `ST-0002` v2; the bundle of `US-WRK-014`.

**5 · Data Fields / Mapping** `[from cards only — §16 unread; the card names three tables, the caption six]`

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| tasks | `Work-008` Checklist | `WM-18` | `work_order_tasks` (seq · title · est_minutes · photo_required · is_mandatory · ticked_at · ticked_by · photo_attachment_id NULL) | rows | copied at raise; ticked in the field | — |
| readings | `Work-008` Checklist | `WM-18` | `work_order_readings` (seq · prompt · unit_of_measure · min · max · required · photo_required · posts_as_meter_read · value NULL · captured_at · captured_by · photo_attachment_id NULL · in_range NULL) | rows | copied; captured in the field | unit required |
| materials | `Work-008` Parts | `WM-18` | `work_order_materials` (part_id · planned_qty · used_qty · unit_of_measure · issued_by · issued_at) | rows | copied; used in the field | — |
| safety | `Work-008` Checklist | `WS-08`, `WS-11` | `work_order_safety` (seq · text · is_mandatory · ticked_at · ticked_by) | rows | copied; ticked | — |
| help | `Work-008` Checklist | `WS-08` | `work_order_help` (seq · kind · label · ref) | rows | copied | — |
| details | `Work-010` | `WS-10` | `work_order_details` (access notes · hazards · gate code · show flags) | one row | copied + the premises' own access notes | — |

**6 · Acceptance** — **Given** `WO-4822` is raised from v2, **when** the template is edited or v3 is published, **then** the order's seven tasks, three readings and three parts are exactly what they were.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None. (Three tables or six is §16's to state; both readings are recorded in the field map.)

---
id: US-WRK-033
epic: EP-WRK-06
module: work
screens: [Work-008, Work-003]
wave: 2
status: ready
blocked_by: []
depends_on: [US-WRK-032, US-WRK-025]
journeys: [J62]
rules: [BR-WRK-008]
golden_tests: []
finance_calc: none
---
### US-WRK-033 — The six-tab work order detail: Overview · Checklist · Parts · Location · Customer · Audit (`WM-19`)

**1 · Details** — As **a technician or a supervisor**, I want **to tick *Record final read on old meter*, type 48,221 kWh, attach a photo, and see the task carry a tick with my name and the time**, so that **the Tasks header moves from *2 of 7* to *3 of 7***.

`Work-008` at `/{tenant}/work/orders/WO-4822?tab=checklist`. Header: *WO-4822 · Meter exchange · 221 Oak Ave · A-10688 · North · Route 1 · Normal · D. Ortiz · Today 15:30 · Scheduled*. The Checklist tab: **SAFETY — BEFORE YOU START** (three boxes) · **TASKS — 7 STEPS · 45 MIN ESTIMATED** · **READINGS TO TAKE** (Reading · Unit · Range · Photo required · Value · Photograph · Captured) · **HELP & SUPPORT**. Footer: *Marking complete sends it for approval. It does not activate anything until a person accepts it.* Actions: *Mark complete · Reassign… · Put on hold… · Cancel order*. ⚠ **Placement amended 2026-10-02 (PO: *"Move them to the top right like every other screen."*, decision log *"THREE UI RULINGS FROM THE RATE-SCHEDULE SWEEP"* (2); B14 rules 2 and 11):** the drawing puts the four under the footer sentence; they are built top-right in the page head, in this order, Cancel order in the danger tier. The footer sentence stays in the body. **`Work-003`, the drawer on the connection detail, becomes a link to this screen** and keeps its Accept.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-WRK-008` | Everything on the screen is the order's copy | CONFIRMED |
| `BR-MET-110` | Marking complete sends for approval; a person accepts | CONFIRMED |
| B14 rules 2, 6, 15, 31, 32 | One header; Cancel order danger-tier; icons; the human reference `WO-4822`, never a uuid; one sentence per section | CONFIRMED |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Tick task 2, type `48,221` kWh, attach `IMG-8841` | `ticked_at`, `ticked_by` = D. Ortiz; the header reads **3 of 7**; the reading row reads *48,221 · ▣ IMG-8841 · 15:12* |
| TC-2 | *Mark complete* | `submit_field_result`; `state = completed`; `accepted_by` NULL; the order appears on `Work-009`; **nothing activates** |
| TC-3 · **negative** | *Mark complete* with a mandatory safety row unticked | Refused by the server naming the row (`US-WRK-043`) |
| TC-4 · **negative** | *Cancel order* on a completed order | Refused — a finished job is accepted or failed, never cancelled after the fact |
| TC-5 | The Audit tab | Assignment rows, ticks, the completion and the acceptance, each with actor and time |
| TC-6 · **tenant isolation** | Lone Star Ridge opens `/work/orders/WO-4822` | `404` |
| TC-7 · **UI law** | The header | One `PageHeader`; the visible id is `WO-4822`; the six tabs; no `WS-08` or `BR-` anywhere |

**4 · Test Data** — `WO-4822` as `US-WRK-032`; ticks: tasks 1 and 2 done at 15:12 by D. Ortiz.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Overview | `Work-008` | `WM-19` | `work_orders` header columns + details row | — | — | — |
| Checklist | `Work-008` | `WM-19` | `work_order_safety`, `_tasks`, `_readings`, `_help` | — | — | `US-WRK-032` |
| Parts | `Work-008` | `WM-19` | `work_order_materials` | — | — | `US-WRK-050` |
| Location | `Work-008` | `WM-19` | premises via `customers_seam`; the map pin | — | — | `US-WRK-029` |
| Customer | `Work-008` | `WM-19` | account and contact via `customers_seam`; the signature (`US-WRK-036`) | — | — | read-only |
| Audit | `Work-008` | `WM-19` | `audit_log` + `work_order_assignments` | — | — | — |

**6 · Acceptance** — **Given** `WO-4822` with two tasks done, **when** a technician ticks the third with its reading and photo, **then** the header reads 3 of 7 and the row names them and the time — **and** marking complete puts it in the approval queue without activating anything.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---
id: US-WRK-034
epic: EP-WRK-06
module: work
screens: [Work-002, Work-008]
wave: 2
status: ready
blocked_by: []
depends_on: [US-WRK-002, US-WRK-024]
journeys: [J66]
rules: [BR-WRK-054]
golden_tests: []
finance_calc: none
---
### US-WRK-034 — The consequence chain behind a failed outcome: a follow-up order and a hold on the build (`WM-25`)

**1 · Details** — As **a supervisor**, I want **a technician marking `WO-4907` Failed to raise `WO-4909` on `CON-26-0117` and move the build from Partly activated to On hold with the reason in Waiting on**, so that **a failure is not a token nobody acts on**.

*"`failed` is one of five outcome tokens that ship today. The design says it raises a follow-up order and puts the connection on hold; neither happens. Newly specified by this document."* The chain runs inside the acceptance transaction: a follow-up order copied from the same template (`BR-WRK-008`), `blocked_by` the failed one, source *Failed outcome*; `hold_connection` with `waiting_on` = the technician's stated reason.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-WRK-054` | Failed → follow-up order + hold, reason in Waiting on | CONFIRMED — `WM-25` |
| `BR-WRK-024` | The follow-up's source is *Failed outcome*, naming the order | CONFIRMED |
| blueprint §9.1 | Hold outranks progress in the derived state | CONFIRMED |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | `WO-4907` field result `outcome = failed`, reason *pressure test failed at 2.1 bar*; supervisor accepts | `WO-4909` raised, `blocked_by = WO-4907`, source *Failed outcome*; `CON-26-0117` reads **On hold**; Waiting on reads the reason |
| TC-2 · **negative** | Accept a `passed` outcome | No follow-up, no hold |
| TC-3 · **negative** | The follow-up raise fails (say, the template was deactivated) | The whole acceptance rolls back — *"A refusal anywhere in step 3 rolls the whole acceptance back — the order stays in the queue"* |
| TC-4 | A failed order with no connection (a one-off job) | A follow-up is raised; **no hold** — there is no build to hold; the response says so |
| TC-5 · **tenant isolation** | Lone Star Ridge accepts a Brazos Bend failed order | `404` before any chain runs |
| TC-6 | `Work-002` | `WO-4909` appears as an eighth row, *Waits for WO-4907*; the header moves *5 of 7* → *5 of 8* |

**4 · Test Data** — `WO-4907` Pressure test and light-up 🚩 · Gas · Per premise · External · waits for `WO-4906` · outcome Failed. `CON-26-0117` Partly activated → On hold.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| follow-up | `Work-002` | `WM-25` | `work_orders` row via `create_work_order`, `blocked_by`, `source = failed_outcome`, `follows_order_id` | row | system | inside the accept transaction |
| hold | `Work-002` | `WM-25` | `hold_connection(reason)` — metering's own writer, through the seam | — | system | the one place Work asks metering to write a connection, and it is metering's function that writes |
| the reason | `Work-001` Waiting on | `WM-25` | `connections.waiting_on` | text | from the field result | — |

**6 · Acceptance** — **Given** `WO-4907` fails, **when** a supervisor accepts the result, **then** `WO-4909` exists blocked by it and the build is on hold with the reason shown.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---
id: US-WRK-035
epic: EP-WRK-06
module: work
screens: [Work-003, Work-009]
wave: 2
status: blocked
blocked_by: [OQ-376]
depends_on: [US-WRK-003]
journeys: [J61]
rules: [BR-WRK-057]
golden_tests: []
finance_calc: none
---
### US-WRK-035 — Give the connection letter its own source kind, so *Your electric service is live* stops coming back *queued: false · unavailable* (`WM-27`)

**1 · Details** — As **a customer whose gate order was just accepted**, I want **the letter the PO ruled to arrive**, so that **my Messages tab reads *Your electric service is live***.

*"The trigger is built and audited; the message queue's source list has no `connection` in it, so the letter comes back refused with its reason. Filing it as `notice` would misclassify it in every monthly report."* **This is `OQ-376`, already OPEN — *"blocking the send only"* — and it is CITED, not re-minted** (law 13; `CR-070` §6 said raise it anew and the predecessor lane corrected that). Until ruled: `accept_field_result` still queues and is still refused, the refusal reason is carried on the response as it is today, and `Work-003`'s footer sentence stays honest. *"The PO was shown that figure before ruling and chose it anyway"* — the person pressing Accept IS the send, and accepting order three of seven sends the letter for that order's service.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-WRK-057` | The letter needs a `connection` source kind; `notice` is wrong | OPEN — `OQ-376` |
| `BR-MET-115` | The send fires when a human marks the job complete | CONFIRMED |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 · **stub** | Accept the gate order on `CON-26-0110` today | The letter is queued and refused; the response carries the refusal and `raise NotImplementedError("OQ-376")` sits where the `connection` source would be chosen |
| TC-2 · **negative** | A lane sends it as `notice` | The test FAILS — the source kind is asserted by name, so the tempting fix cannot land quietly |
| TC-3 · **negative** | Accept a non-gate order | No letter attempted — only the gate order's service is live |
| TC-4 · **tenant isolation** | The refusal reason on Lone Star Ridge | Its own; no Brazos Bend message row |
| TC-5 | The day the ruling lands | One constant value and one template; TC-1 turns from stub to *Your electric service is live* on the customer's Messages tab |

**4 · Test Data** — `CON-26-0110` · `3450 Oak Ridge Dr` · E · 2 of 2 · Activated; gate order `WO-4902 · Meter set 🚩`.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| source kind | Customer · Messages | `WM-27` | `outbound_messages.source_type` — the platform constant gains `connection` **when ruled**; notifications owns the write | enum | system | **stub `NotImplementedError("OQ-376")`** |

**6 · Acceptance** — **Given** the gate order is accepted, **when** the queue is asked, **then** today it refuses with its reason and nothing pretends otherwise — **and** the fix is one constant and one template, not a workaround through `notice`.

**7 · Finance Calculation** — N/A.

**8 · Open Questions**

| OQ | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| `OQ-376` | What source kind and template does a *your service is live* letter use? | The send only | PO | OPEN — already registered; cited, not re-minted |

---
id: US-WRK-036
epic: EP-WRK-06
module: work
screens: [Work-008, Work-012]
wave: 2
status: ready
blocked_by: []
depends_on: [US-WRK-033, US-WRK-048]
journeys: [J62]
rules: [BR-WRK-046]
golden_tests: []
finance_calc: none
---
### US-WRK-036 — Attachments and the customer's signature, replacing the dead `attachment_ref` column nothing writes or reads (`WM-30`)

**1 · Details** — As **a technician**, I want **to attach two photos and capture the customer's printed name and signature**, so that **the Audit tab lists both with who added them and when — and a refusal records the decline reason instead**.

`work_order_attachments` and `work_order_signatures`, *"replacing the dead `attachment_ref` column that nothing in the entire codebase writes or reads."* The bytes live in the document store under the three kinds `US-WRK-048` adds; this story is the rows and the capture. r10: *"Customer signature required · capture printed name · if refused, record decline reason and photo of door hanger."*

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-WRK-046` | Signature = printed name + image + who/when; refusal = reason + door-hanger photo | CONFIRMED — `WM-30` |
| `BR-WRK-047` | The bytes are `stored_documents` rows of the three Work kinds | CONFIRMED |
| B14 rule 31 | The screen shows `SIG-4822`, never a document uuid | CONFIRMED |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Attach `IMG-8841` and `IMG-8842`; capture *S. Miller*, signed 16:07 | Two attachment rows, one signature row (`SIG-4822`); Audit lists all three with D. Ortiz and the times |
| TC-2 · **negative** | The customer refuses to sign | `refused = true`, `decline_reason` required, a door-hanger photo required; **no** signature image |
| TC-3 · **negative** | A template whose Signature step says required, and the job closes with neither a signature nor a refusal | Refused at close naming the requirement |
| TC-4 · **negative** | `work_orders.attachment_ref` | Dropped by the migration after a summary shows it is NULL on every row (it is written by nothing) |
| TC-5 · **tenant isolation** | Lone Star Ridge fetches `SIG-4822` | `404` |
| TC-6 | The Customer tab | *Signed S. Miller · 15 Mar 2026 16:07 · signature image SIG-4822*; the image behind a link that expires in four hours (`US-WRK-048`) |

**4 · Test Data** — `WO-4822`: `IMG-8841` 15:12 · `IMG-8842` 16:02 · `SIG-4822` *S. Miller* 16:07 · technician's note *Customer present throughout. Old meter left for collection.*

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| attachment | `Work-008` | `WM-30` | `work_order_attachments` (work_order_id · document_id FK → `stored_documents` · kind · taken_at · device · added_by · reading_id NULL · task_id NULL) | rows | phone | idempotency key per image (`US-WRK-048`) |
| signature | `Work-008` Customer | `WM-30` | `work_order_signatures` (work_order_id · printed_name · document_id · signed_at · captured_by · refused · decline_reason · door_hanger_document_id) | one row | phone | exactly one per order |
| `attachment_ref` | — | `WM-30` | **dropped** | — | — | after a NULL-only summary |

**6 · Acceptance** — **Given** a job requiring a signature, **when** the customer signs, **then** the name, the image and the time are on the Customer tab and in the audit — **and when** they refuse, **then** the reason and the door-hanger photo are, instead.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None new; retention is `OQ-WRK-1496` (`US-WRK-048`).
