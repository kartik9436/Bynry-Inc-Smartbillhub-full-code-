# EP-FLD-02 — The day — Home, Today, Nearby, refresh and the day staying true

**Module:** field-app (`18-field-app`, module code FLD) · **Wave:** 0, 3 · **Design tasks:** T-16 · **Screens:** FF-08, FF-10, FF-28, FF-42, FF-11, FF-12, FF-35, FF-41, FF-50, FF-63, FF-09 · **Status:** draft (2026-10-21, `CR-187-BRC10`)

## Scope

**In:** the design's flow group *FF-09 to FF-12, FF-63* and the requirements whose screens sit in it — US-FLD-002 (requirement 2), US-FLD-015 (requirement 15), US-FLD-023 (requirement 23), US-FLD-037 (requirement 37), US-FLD-043 (requirement 43), US-FLD-045 (requirement 45), US-FLD-078 (requirement 78).

**Out:** everything the design's *Scope · Out* list excludes (`01-overview.md` §5) — taking payment on site, linear assets, inspection rounds, offline maps, a dispatcher app, live crew tracking, van stock-takes, customer-facing features, a watch app.

**Source:** the *SMART360 Next Field App* design canvas, version of 2026-10-21. The screens are the images in `../wireframes/` and they are the specification (B14 rule 42; PO 2026-10-21, *"please ensure all native app screens are build using images not using text or contents"*). Figures on a board are illustrations (B14 rule 37) and are used below as test data only.

⚠ **1 of these stories is `blocked`** — US-FLD-023 — each on a collision between the design and a rule already signed in this repository, named in plain words in its §8. The open-questions lane (DOC-C) mints the `OQ-FLD-` id; until then `blocked_by` is empty and the gap is the comment beside it.

## Capability matrix (list screens only — B9 conformance)

| Screen | Search fields | Filters | Default sort | Sortable | Columns default/available | Row actions | Bulk actions | Export |
|---|---|---|---|---|---|---|---|---|
| FF-10 Today | customer · address · work-order number | status · service · window | appointment window (R1) | not declared | card: customer, address, number + type, window, distance | Start · Navigate · Hold | — | — |
| FF-11 Nearby | — | radius · job type · priority · due date | distance (R2) | not declared | card: distance, priority, address, number + type, due | Claim | — | — |
| FF-63 Home | — | — | — | — | two tiles | — | — | — |

*Not declared* means the design does not say; requirement 37 and R44 require it declared and wired before the screen ships — the build lane declares it, it is not guessed here.

## Stories

---
id: US-FLD-002
epic: EP-FLD-02
module: field-app
screens: [FF-08, FF-10, FF-28]
wave: 0
status: ready
blocked_by: []
depends_on: [US-FLD-004]
journeys: []           # the E2E-nn cases cited in §3 become journeys under 08-qa/01-e2e/journeys/ (sibling lane)
rules: [BR-FLD-00031, BR-FLD-00032, BR-FLD-00056]
golden_tests: []
finance_calc: none
---
### US-FLD-002 — Offline-first — the day opens instantly with no signal, and the phone says how far it is in step

**Requirement 2, in the design's words:** *Offline-first — jobs, checklists, premise notes and safety documents open with no signal. Instant open from local storage, with online / offline / pending-sync shown* — section A · The original brief · standing *Engine built*.

**1 · Details** — As **Dana in a basement with no bars**, I want **jobs, checklists, premise notes and safety documents to open from the handset**, so that **nothing I need waits for a signal**. FF-08 *First sync* loads the day at the depot and asks for 100% before driving out; afterwards Today opens from local storage and the header chip shows a number for how far phone and server are in step (R32).

**Screens (build from the images — B14 rules 42, 44, 45):** `FF-08` First sync — [phone](../wireframes/phone/FF-08-first-sync.png) · [tablet](../wireframes/tablet/FF-08-T-first-sync.png)<br>`FF-10` Today — [phone](../wireframes/phone/FF-10-today.png) · [tablet](../wireframes/tablet/FF-10-T-today.png)<br>`FF-28` Documents — [phone](../wireframes/phone/FF-28-documents.png) · [tablet](../wireframes/tablet/FF-28-T-documents.png)

**2 · Business Rules**

| BR | R | Statement (first sentence, verbatim — the whole rule is in `02-business-rules.md`) | Status |
|---|---|---|---|
| `BR-FLD-00031` | R31 | The map requires a signal. | CONFIRMED (PO) |
| `BR-FLD-00032` | R32 | The sync indicator is a number, not a word — how far the phone and the server are in step, in both directions. | CONFIRMED (PO) |
| `BR-FLD-00056` | R56 | A pull is a delta against a watermark, never a full download. | DERIVED (decision log T-05) |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | FF-08 at the depot on wi-fi | Shift, safety documents (14 of 14), jobs and checklists, asset history and customer details load with one combined progress; *Open my day* waits for 100% |
| TC-2 | E2E-02: airplane mode from 07:45; eleven jobs opened, worked and closed; one sync at 17:10 | Nothing lost, nothing doubled, nothing needed a signal mid-day |
| TC-3 | Open FF-28 with no signal | *Water shut-off SOP* and the install guide open from the phone |
| TC-4 · **negative** | Open the map with no signal | The map shows an offline state; the day and every job stay available and the address travels with the job (R31) |
| TC-5 | Header chip with 12 items unsent | Reads *12 to send* — a number, not a word (R32) |
| TC-6 · **tenant isolation** | R. Patel works for Silver Creek Water and Lone Star Water and signs in to Lone Star Water on the same handset | Only `field-lone-star-water.sqlite` is opened; not one Silver Creek row is readable (R131), and the server takes the tenant from the credential, never from the payload (R127) |

**4 · Test Data** — 11 jobs, 14 safety documents (22 MB), first sync about 40 seconds on depot wi-fi.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| the day | FF-10 | requirement 2 | handset `work_order`, `wo_item`, `wo_reading` | rows | integration | pulled whole on first sign-in only (R56) |
| sync number | FF-10 header | R32 | handset `outbox` pending count | integer | computed-display | items, not bytes |

**6 · Acceptance** — **Given** a technician whose day downloaded at the depot, **when** they lose signal for the whole shift, **then** every job, checklist, note and safety document still opens and the header says how much is waiting to send.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---

---
id: US-FLD-015
epic: EP-FLD-02
module: field-app
screens: [FF-10, FF-42]
wave: 3
status: ready
blocked_by: []
depends_on: [US-FLD-043, US-FLD-045]
journeys: []           # the E2E-nn cases cited in §3 become journeys under 08-qa/01-e2e/journeys/ (sibling lane)
rules: [BR-FLD-00001, BR-FLD-00002, BR-FLD-00019, BR-FLD-00058]
golden_tests: []
finance_calc: none
---
### US-FLD-015 — Mid-day re-sequencing — an emergency arrives and the day re-orders

**Requirement 15, in the design's words:** *Mid-day route re-sequencing — an emergency arrives and the day re-orders* — section C · From the reference apps, confirmed into scope · standing *New*.

**1 · Details** — As **Dana at 11:00**, I want **a job dispatch moves into my day, or out of it, to arrive and take its place by appointment window**, so that **the list is the day as it now is**. The server wins on mirrored data (R58) — a dispatcher's new window overwrites the local copy — and the list is ordered by window, never by priority (R1).

**Screens (build from the images — B14 rules 42, 44, 45):** `FF-10` Today — [phone](../wireframes/phone/FF-10-today.png) · [tablet](../wireframes/tablet/FF-10-T-today.png)<br>`FF-42` Alerts — [phone](../wireframes/phone/FF-42-alerts.png) · [tablet](../wireframes/tablet/FF-42-T-alerts.png)

**2 · Business Rules**

| BR | R | Statement (first sentence, verbatim — the whole rule is in `02-business-rules.md`) | Status |
|---|---|---|---|
| `BR-FLD-00001` | R1 | The day list is ordered by appointment window, never by priority. | CONFIRMED — repo `BR-WRK-035` |
| `BR-FLD-00002` | R2 | Nearby work is a different list with a different question, sorted by distance. | DERIVED (decision log T-05) |
| `BR-FLD-00019` | R19 | The server pushes the moment money changes. | CONFIRMED (PO) |
| `BR-FLD-00058` | R58 | The server wins on mirrored data; the handset wins on captured data. | DERIVED (decision log T-05) |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Dispatch moves WO-4831 to 14:00 (FF-42 *Schedule · WO-4831 moved to 14:00*) | On refresh Today puts WO-4831 in its 14:00 window; the alert is in Alerts |
| TC-2 | An emergency P1 job is dispatched to Dana with a 12:00–17:00 window | It sits in its window, with a P1 badge — it does not jump the job she is standing outside (R1) |
| TC-3 · **negative** | Dana had captured a reading on WO-4831 before the window moved | Her reading is not overwritten; only the mirrored window changes (R58) |
| TC-4 | A job is cancelled by the office | It leaves Today on the next delta (R57) and Alerts shows *Job cancelled* |
| TC-5 · **tenant isolation** | R. Patel works for Silver Creek Water and Lone Star Water and signs in to Lone Star Water on the same handset | Only `field-lone-star-water.sqlite` is opened; not one Silver Creek row is readable (R131), and the server takes the tenant from the credential, never from the payload (R127) |

**4 · Test Data** — WO-4822 08:00–12:00 · WO-4824 P1 12:00–17:00 · WO-4831 moved to 14:00 at 07:41.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| window | FF-10 | R1 | handset `work_order` (mirror) | time range | integration | server wins (R58) |

**6 · Acceptance** — **Given** a day already on the handset, **when** dispatch changes a window or adds an emergency, **then** the day re-orders by window on the next refresh and nothing the technician captured is overwritten.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---

---
id: US-FLD-023
epic: EP-FLD-02
module: field-app
screens: [FF-11, FF-12]
wave: 3
status: blocked
blocked_by: []          # the gap is named in §8; its OQ-FLD id is minted by the open-questions lane (DOC-C) and filled in here
depends_on: [US-FLD-037]
journeys: []           # the E2E-nn cases cited in §3 become journeys under 08-qa/01-e2e/journeys/ (sibling lane)
rules: [BR-FLD-00002, BR-FLD-00027, BR-FLD-00034, BR-FLD-00041]
golden_tests: []
finance_calc: none
---
### US-FLD-023 — Pending and nearby work — see unassigned orders and claim one where I am standing

**Requirement 23, in the design's words:** *Pending and nearby work — see unassigned orders, and claim one near where you are standing* — section D · Asked for by the technicians · standing *New*.

**1 · Details** — As **Dana with an hour spare**, I want **to see unassigned orders within my radius, sorted by distance, and claim one**, so that **the nearest work gets done without a phone call**. FF-11 is a different list with a different question, sorted by distance; it does not touch Today's order (R2). The radius is a setting, default 2 miles (R34). FF-12 says what claiming does to my day.

**Screens (build from the images — B14 rules 42, 44, 45):** `FF-11` Nearby — [phone](../wireframes/phone/FF-11-nearby.png) · [tablet](../wireframes/tablet/FF-11-T-nearby.png)<br>`FF-12` Claim — [phone](../wireframes/phone/FF-12-claim.png) · [tablet](../wireframes/tablet/FF-12-T-claim.png)

**2 · Business Rules**

| BR | R | Statement (first sentence, verbatim — the whole rule is in `02-business-rules.md`) | Status |
|---|---|---|---|
| `BR-FLD-00002` | R2 | Nearby work is a different list with a different question, sorted by distance. | DERIVED (decision log T-05) |
| `BR-FLD-00027` | R27 | Contractors may claim unassigned nearby work | CONFIRMED (PO) |
| `BR-FLD-00034` | R34 | The nearby radius is a setting inside the app, default 2 miles | CONFIRMED (PO) |
| `BR-FLD-00041` | R41 | Search is local first, server on request. | DERIVED (decision log T-05) |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | FF-11 within 2 miles | *3 unassigned*: 1412 Elm Street 0.2 mi · 9 Maple Court 0.6 mi · 60 Birch Lane 1.4 mi (taken by R. Patel) |
| TC-2 | Claim WO-4840 on FF-12 | *Your day grows by 12 minutes · 6h 20m becomes 6h 32m*; dispatch is told and another technician cannot take it |
| TC-3 · **negative** | Claim a job R. Patel took a moment ago | Refused by the server; FF-11 shows *Taken by R. Patel* |
| TC-4 | E2E-19: a contractor claims a nearby unassigned order | The claim works within the tenant and the office sees who took it (R27) |
| TC-5 · **negative** | A contractor claims an order outside their skills | **Blocked** — see §8 |
| TC-6 · **tenant isolation** | R. Patel works for Silver Creek Water and Lone Star Water and signs in to Lone Star Water on the same handset | Only `field-lone-star-water.sqlite` is opened; not one Silver Creek row is readable (R131), and the server takes the tenant from the credential, never from the payload (R127) |

**4 · Test Data** — Radius 2 miles · WO-4840 Routine read 1412 Elm Street due 22 Oct · WO-4838 Meter seal check · WO-4835 taken by R. Patel.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| radius | FF-11 | R34 | MMKV preference | 1 · 2 · 5 · 10 mi | user-input | default 2 |
| distance | FF-11 | R2 | premise point vs device position | miles | computed-display | sorted ascending |

**6 · Acceptance** — **Given** unassigned work near a technician, **when** they open Nearby and claim one, **then** the job joins their day, dispatch is told, and no-one else can take it.

**7 · Finance Calculation** — N/A.

**8 · Open Questions**

| OQ-ID | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| *to be minted by DOC-C* | Whether a contractor's claim is refused outside their skills: walkthrough E2E-19 says *within their skills*, but the signed `BR-WRK-029` was superseded on 2026-09-23 so that the skill match advises and never blocks. Which applies to a claim from the handset is unruled. | the test case marked **Blocked** in §3 | Product Owner (a collision with a signed rule — law 13) | OPEN — not yet in the register |

---

---
id: US-FLD-037
epic: EP-FLD-02
module: field-app
screens: [FF-10, FF-11, FF-35, FF-41]
wave: 3
status: ready
blocked_by: []
depends_on: [US-FLD-002]
journeys: []           # the E2E-nn cases cited in §3 become journeys under 08-qa/01-e2e/journeys/ (sibling lane)
rules: [BR-FLD-00041, BR-FLD-00042, BR-FLD-00044]
golden_tests: []
finance_calc: none
---
### US-FLD-037 — Search and filter on every list, with criteria declared per screen

**Requirement 37, in the design's words:** *Search and filter on every list, with criteria per screen. Today searches customer, address, work-order number, status, service and window. Assets search serial, badge, device ID, address and account number. Completed searches a date range, an outcome and a customer. Nearby filters a radius, a job type, a priority and a due date* — section G · Search, large volumes, refresh and the handset's data · standing *New*.

**1 · Details** — As **Dana**, I want **every list to search and filter by what that list is for**, so that **I find the job, the meter or the visit without scrolling**. Today: customer, address, work-order number, status, service, window. Assets: serial, badge, device ID, address, account number. Completed: date range, outcome, customer. Nearby: radius, job type, priority, due date. Search is local first, server on request (R41); a declared control is wired before the screen ships (R44).

**Screens (build from the images — B14 rules 42, 44, 45):** `FF-10` Today — [phone](../wireframes/phone/FF-10-today.png) · [tablet](../wireframes/tablet/FF-10-T-today.png)<br>`FF-11` Nearby — [phone](../wireframes/phone/FF-11-nearby.png) · [tablet](../wireframes/tablet/FF-11-T-nearby.png)<br>`FF-35` Completed — [phone](../wireframes/phone/FF-35-completed.png) · [tablet](../wireframes/tablet/FF-35-T-completed.png)<br>`FF-41` Asset search — [phone](../wireframes/phone/FF-41-asset-search.png) · [tablet](../wireframes/tablet/FF-41-T-asset-search.png)

**2 · Business Rules**

| BR | R | Statement (first sentence, verbatim — the whole rule is in `02-business-rules.md`) | Status |
|---|---|---|---|
| `BR-FLD-00041` | R41 | Search is local first, server on request. | DERIVED (decision log T-05) |
| `BR-FLD-00042` | R42 | A search that cannot see everything says so, in the result area. | DERIVED (decision log T-05) |
| `BR-FLD-00044` | R44 | Every list declares its own search and filter criteria, and a declared control is wired before the screen ships. | CONFIRMED — repo rule |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Today, search *Elm* | WO-4822 Sarah Miller, 1400 Elm Street, answered from the handset instantly (R41) |
| TC-2 | Completed, filter outcome *Waiting on someone* | WO-4815 Marcus Webb, 88 Hillcrest Avenue |
| TC-3 | Nearby, filter priority P2 | WO-4838 9 Maple Court only |
| TC-4 · **negative** | A screen declares a filter that changes nothing | The screen does not ship — a declared control is wired first (R44) |
| TC-5 · **negative** | Assets search offline for a serial not on the handset | The result area says only today's assets are here and a signal searches the whole utility (R42) |
| TC-6 · **tenant isolation** | R. Patel works for Silver Creek Water and Lone Star Water and signs in to Lone Star Water on the same handset | Only `field-lone-star-water.sqlite` is opened; not one Silver Creek row is readable (R131), and the server takes the tenant from the credential, never from the payload (R127) |

**4 · Test Data** — WO-4822 Sarah Miller 1400 Elm Street · WO-4815 Marcus Webb 88 Hillcrest Avenue (Waiting on someone) · WO-4838 P2.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| search | FF-10/11/35/41 | requirement 37 | handset `search_index` (FTS5, carries technician_id) | text | user-input | local first (R41) |

**6 · Acceptance** — **Given** any list in the app, **when** the technician searches or filters it, **then** only matching rows remain, and a partial result says so.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---

---
id: US-FLD-043
epic: EP-FLD-02
module: field-app
screens: [FF-10, FF-50]
wave: 0
status: ready
blocked_by: []
depends_on: [US-FLD-044]
journeys: []           # the E2E-nn cases cited in §3 become journeys under 08-qa/01-e2e/journeys/ (sibling lane)
rules: [BR-FLD-00056, BR-FLD-00059]
golden_tests: []
finance_calc: none
---
### US-FLD-043 — Four refresh triggers — pull, coming forward, a push for one record, every fifteen minutes on shift

**Requirement 43, in the design's words:** *Four refresh triggers: pull-to-refresh on any list · the app coming forward after five minutes · a push from the server for one changed record · every fifteen minutes while on shift and connected* — section G · Search, large volumes, refresh and the handset's data · standing *New*.

**1 · Details** — As **Dana**, I want **the day to refresh when I pull down, when the app comes forward after five minutes, when the server pushes a change, and every fifteen minutes while I am on shift and connected**, so that **I never act on a list that is hours old**. A pull never runs while a push is mid-batch for the same order (R59).

**Screens (build from the images — B14 rules 42, 44, 45):** `FF-10` Today — [phone](../wireframes/phone/FF-10-today.png) · [tablet](../wireframes/tablet/FF-10-T-today.png)<br>`FF-50` Sync — [phone](../wireframes/phone/FF-50-sync.png) · [tablet](../wireframes/tablet/FF-50-T-sync.png)

**2 · Business Rules**

| BR | R | Statement (first sentence, verbatim — the whole rule is in `02-business-rules.md`) | Status |
|---|---|---|---|
| `BR-FLD-00056` | R56 | A pull is a delta against a watermark, never a full download. | DERIVED (decision log T-05) |
| `BR-FLD-00059` | R59 | A pull never runs while a push is mid-batch for the same order, so a stale mirror cannot overwrite what the server has just accepted | DERIVED (decision log T-05) |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Pull to refresh on Today | A delta pull runs (R56) |
| TC-2 | App backgrounded six minutes, then brought forward | A delta pull runs; after four minutes it does not |
| TC-3 | The server pushes one changed record (WO-4824 paid) | That record refreshes without a full pull |
| TC-4 · **negative** | A timer fires while order WO-4822's batch is mid-send | The pull for WO-4822 waits until the push settles (R59) |
| TC-5 · **negative** | Off duty, connected | The fifteen-minute timer does not run |
| TC-6 · **tenant isolation** | R. Patel works for Silver Creek Water and Lone Star Water and signs in to Lone Star Water on the same handset | Only `field-lone-star-water.sqlite` is opened; not one Silver Creek row is readable (R131), and the server takes the tenant from the credential, never from the payload (R127) |

**4 · Test Data** — Shift 08:00–16:30 · timer 15 minutes · foreground threshold 5 minutes.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| last pull | FF-50 | requirement 43 | handset `sync_state.last_pull` | timestamp | system-derived | per technician per table |

**6 · Acceptance** — **Given** a technician on shift with a signal, **when** any of the four triggers happens, **then** a delta refresh runs, and never over a send in progress for the same order.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---

---
id: US-FLD-045
epic: EP-FLD-02
module: field-app
screens: [FF-10]
wave: 0
status: ready
blocked_by: []
depends_on: [US-FLD-044]
journeys: []           # the E2E-nn cases cited in §3 become journeys under 08-qa/01-e2e/journeys/ (sibling lane)
rules: [BR-FLD-00057, BR-FLD-00058]
golden_tests: []
finance_calc: none
---
### US-FLD-045 — A delta carries removals — a job reassigned away leaves the handset

**Requirement 45, in the design's words:** *A delta must carry removals as well as changes — a job reassigned, an order cancelled, an asset off the route. Without that, a job the technician no longer owns stays on their phone and they drive to it* — section G · Search, large volumes, refresh and the handset's data · standing *New*.

**1 · Details** — As **Dana**, I want **a job the office moved to someone else to disappear from my day**, so that **I do not drive to it**. A delta must carry removals — reassigned, cancelled, an asset off the route — or the job lives on the handset forever and nothing on screen looks wrong (R57).

**Screens (build from the images — B14 rules 42, 44, 45):** `FF-10` Today — [phone](../wireframes/phone/FF-10-today.png) · [tablet](../wireframes/tablet/FF-10-T-today.png)

**2 · Business Rules**

| BR | R | Statement (first sentence, verbatim — the whole rule is in `02-business-rules.md`) | Status |
|---|---|---|---|
| `BR-FLD-00057` | R57 | A delta carries removals. | DERIVED (decision log T-05) |
| `BR-FLD-00058` | R58 | The server wins on mirrored data; the handset wins on captured data. | DERIVED (decision log T-05) |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | E2E-10: office moves job 7 to another technician while Dana is offline; she refreshes at noon | Job 7 leaves her list — asserted by address and by what Today then shows |
| TC-2 | An order is cancelled in the office | It arrives as a removal and leaves Today |
| TC-3 · **negative** | A removed job had unsent captures | The captures stay in the outbox and send under Dana's name (R60); only the mirror row goes |
| TC-4 · **negative** | The delta reports changes only | Not acceptable — the test fails because job 7 is still on Today |
| TC-5 · **tenant isolation** | R. Patel works for Silver Creek Water and Lone Star Water and signs in to Lone Star Water on the same handset | Only `field-lone-star-water.sqlite` is opened; not one Silver Creek row is readable (R131), and the server takes the tenant from the credential, never from the payload (R127) |

**4 · Test Data** — Job 7 reassigned from D. Ortiz to M. Chen at 10:40; refresh 12:00.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| tombstone | FF-10 | R57 | server change feed (`GET /work/mobile/changes`) → handset delete | event | integration | file before row, one transaction (R118) |

**6 · Acceptance** — **Given** a job reassigned away while the handset is offline, **when** the handset refreshes, **then** the job leaves the day and no unsent capture is lost.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---

---
id: US-FLD-078
epic: EP-FLD-02
module: field-app
screens: [FF-63, FF-09]
wave: 3
status: ready
blocked_by: []
depends_on: [US-FLD-053]
journeys: []           # the E2E-nn cases cited in §3 become journeys under 08-qa/01-e2e/journeys/ (sibling lane)
rules: [BR-FLD-00102, BR-FLD-00103, BR-FLD-00120]
golden_tests: []
finance_calc: none
---
### US-FLD-078 — Home — both modules at a glance: what is left and what is next

**Requirement 78, in the design's words:** *A landing screen showing both modules — jobs left and next, meters left and nearest, waiting to send, hours today. What to do next, never how fast anybody is going. The bottom bar becomes Home, Jobs, Reads* — section L · The nine of 2026-10-21 · standing *Built*.

**1 · Details** — As **Dana starting her shift**, I want **one landing screen with a tile for Jobs and a tile for Reads**, so that **I know what to do next**. Jobs left, done, on hold and the next address; meters left, read, could not be, and the nearest stop; the sync strip above both; hours today. The bottom bar becomes *Home · Jobs · Reads* (requirement 78, which extends R102's two tabs). No reads per hour, no average job time, no ranking (R120).

**Screens (build from the images — B14 rules 42, 44, 45):** `FF-63` Home — [phone](../wireframes/phone/FF-63-home.png) · [tablet](../wireframes/tablet/FF-63-T-home.png)<br>`FF-09` Menu — [phone](../wireframes/phone/FF-09-menu.png) · [tablet](../wireframes/tablet/FF-09-T-the-sidebar.png)

**2 · Business Rules**

| BR | R | Statement (first sentence, verbatim — the whole rule is in `02-business-rules.md`) | Status |
|---|---|---|---|
| `BR-FLD-00102` | R102 | Reads is reached from the bottom bar, not from a menu. | CONFIRMED (PO) |
| `BR-FLD-00103` | R103 | Sync is one tap from the day, never three. | CONFIRMED (PO) |
| `BR-FLD-00120` | R120 | A technician's landing screen shows what is left and what is next, never how fast they are going. | DERIVED (decision log T-05) |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Home on Tuesday 21 October | Jobs *8 left today · 3 done · 1 on hold* · Next *1400 Elm Street · Unit A*; Reads *15 meters left · 129 read · 7 could not be* · Nearest *1318 Maple Street · 3 meters* |
| TC-2 | Tap the sync strip *12 waiting to send* | Opens Sync in one tap (R103) |
| TC-3 · **negative** | Look for a pace, an average or a rank | None exists on the screen (R120) |
| TC-4 | Bottom bar | *Home · Jobs · Reads*; on a tablet both modules sit in the permanent sidebar (R102) |
| TC-5 · **tenant isolation** | R. Patel works for Silver Creek Water and Lone Star Water and signs in to Lone Star Water on the same handset | Only `field-lone-star-water.sqlite` is opened; not one Silver Creek row is readable (R131), and the server takes the tenant from the credential, never from the payload (R127) |

**4 · Test Data** — Dana · on shift until 16:00 · 4h 52m today (travel 48m, on site 3h 04m, depot 1h) · route WLK-07.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| jobs left / done / on hold | FF-63 | requirement 78 | handset `work_order` (scoped) | counts | computed-display | counted from rows, never a stored tally |
| meters left / read / could not be | FF-63 | requirement 78 | handset `route_read` | counts | computed-display | counted from readings |

**6 · Acceptance** — **Given** a technician with jobs and a route, **when** they open the app, **then** Home shows what is left and what is next in both modules and nothing about how fast they are going.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.
