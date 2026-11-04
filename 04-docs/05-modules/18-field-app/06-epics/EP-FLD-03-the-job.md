# EP-FLD-03 — The job — getting there, opening it, the template, the clocks, handing it back

**Module:** field-app (`18-field-app`, module code FLD) · **Wave:** 4 · **Design tasks:** T-17, T-18 · **Screens:** FF-13, FF-14, RW-04, FF-10, FF-15, FF-16, FF-34, FF-28, FF-47, FF-58 · **Status:** draft (2026-10-21, `CR-187-BRC10`)

## Scope

**In:** the design's flow group *FF-13 to FF-16, FF-28, FF-58* and the requirements whose screens sit in it — US-FLD-007 (requirement 7), US-FLD-008 (requirement 8), US-FLD-021 (requirement 21), US-FLD-026 (requirement 26), US-FLD-029 (requirement 29), US-FLD-071 (requirement 71).

**Out:** everything the design's *Scope · Out* list excludes (`01-overview.md` §5) — taking payment on site, linear assets, inspection rounds, offline maps, a dispatcher app, live crew tracking, van stock-takes, customer-facing features, a watch app.

**Source:** the *SMART360 Next Field App* design canvas, version of 2026-10-21. The screens are the images in `../wireframes/` and they are the specification (B14 rule 42; PO 2026-10-21, *"please ensure all native app screens are build using images not using text or contents"*). Figures on a board are illustrations (B14 rule 37) and are used below as test data only.

## Capability matrix (list screens only — B9 conformance)

No list screen in this group.

## Stories

---
id: US-FLD-007
epic: EP-FLD-03
module: field-app
screens: [FF-13, FF-14, RW-04]
wave: 4
status: ready
blocked_by: []
depends_on: [US-FLD-002]
journeys: []           # the E2E-nn cases cited in §3 become journeys under 08-qa/01-e2e/journeys/ (sibling lane)
rules: [BR-FLD-00031, BR-FLD-00036]
golden_tests: []
finance_calc: none
---
### US-FLD-007 — Map — stops coloured by status, one tap out to Google or Apple Maps

**Requirement 7, in the design's words:** *Map — scheduled stops colour-coded by status, one-tap navigation to Google or Apple Maps* — section A · The original brief · standing *Partly*.

**1 · Details** — As **Dana**, I want **today's stops on a map coloured by status and one tap to my navigation app**, so that **I drive the route without retyping an address**. The map needs a signal (R31); the address travels with the job and is derived from the premises (R36). FF-14 *Stop* is the hand-off: distance, time, arrival estimate, *Google Maps* / *Apple Maps*.

**Screens (build from the images — B14 rules 42, 44, 45):** `FF-13` Map — [phone](../wireframes/phone/FF-13-map.png) · [tablet](../wireframes/tablet/FF-13-T-map.png)<br>`FF-14` Stop — [phone](../wireframes/phone/FF-14-stop.png) · [tablet](../wireframes/tablet/FF-14-T-the-stop.png)<br>`RW-04` Route map — [phone](../wireframes/reads/RW-04-route-map.png) · [tablet](../wireframes/tablet/RW-04-T-route-map.png)

**2 · Business Rules**

| BR | R | Statement (first sentence, verbatim — the whole rule is in `02-business-rules.md`) | Status |
|---|---|---|---|
| `BR-FLD-00031` | R31 | The map requires a signal. | CONFIRMED (PO) |
| `BR-FLD-00036` | R36 | An address is stored on premises and derived everywhere else. | CONFIRMED — repo `BR-MET-1161` |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | FF-13 with three stops | Elm St in progress, Cedar Ct dispatched, Hillcrest Ave queued, each in its status colour; tiles credited *© Esri* |
| TC-2 | FF-14 for 22 Cedar Court, tap *Apple Maps* | Apple Maps opens with 22 Cedar Court, Austin, TX 78704 |
| TC-3 · **negative** | No signal | FF-13 shows an offline state; FF-14 still shows the address and the job opens (R31) |
| TC-4 · **negative** | A job carries its own address copy that differs from the premises | Impossible — the address is read from `premise` only (R36) |
| TC-5 · **tenant isolation** | R. Patel works for Silver Creek Water and Lone Star Water and signs in to Lone Star Water on the same handset | Only `field-lone-star-water.sqlite` is opened; not one Silver Creek row is readable (R131), and the server takes the tenant from the credential, never from the payload (R127) |

**4 · Test Data** — Stop 2 of 11 · 22 Cedar Court · Aaron Bruner · WO-4824 · 4.2 miles · 26 min · arrive 12:28.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| address | FF-13/14 | R36 | handset `premise` (one place) | text | reference-data | never copied onto a job |

**6 · Acceptance** — **Given** a day with stops, **when** the technician opens the map and taps a navigation app, **then** the stop opens in that app with the premises address.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---

---
id: US-FLD-008
epic: EP-FLD-03
module: field-app
screens: [FF-10, FF-14, FF-15, FF-16, FF-34]
wave: 4
status: ready
blocked_by: []
depends_on: [US-FLD-026, US-FLD-029]
journeys: []           # the E2E-nn cases cited in §3 become journeys under 08-qa/01-e2e/journeys/ (sibling lane)
rules: [BR-FLD-00001, BR-FLD-00003, BR-FLD-00004, BR-FLD-00009, BR-FLD-00010]
golden_tests: []
finance_calc: none
---
### US-FLD-008 — Service order execution — window order, safety first, depart and arrive, the labour clock, four outcomes

**Requirement 8, in the design's words:** *Service order execution — route ordered by appointment window, mandatory safety checks before work, departure and arrival tracking, automatic labour timer, four outcomes* — section A · The original brief · standing *Mostly built*.

**1 · Details** — As **Dana**, I want **to work an order from Today to Close in the order the template sets**, so that **every visit is done safely and recorded the same way**. Today is ordered by window (R1). FF-16 is all four safety checks or none, and the server re-derives the lock (R3). Depart starts the travel clock, Start work the labour clock (R9). Close offers four outcomes (R4).

**Screens (build from the images — B14 rules 42, 44, 45):** `FF-10` Today — [phone](../wireframes/phone/FF-10-today.png) · [tablet](../wireframes/tablet/FF-10-T-today.png)<br>`FF-14` Stop — [phone](../wireframes/phone/FF-14-stop.png) · [tablet](../wireframes/tablet/FF-14-T-the-stop.png)<br>`FF-15` Job — [phone](../wireframes/phone/FF-15-job.png) · [tablet](../wireframes/tablet/FF-15-T-job.png)<br>`FF-16` Safety — [phone](../wireframes/phone/FF-16-safety.png) · [tablet](../wireframes/tablet/FF-16-T-safety.png)<br>`FF-34` Close — [phone](../wireframes/phone/FF-34-close.png) · [tablet](../wireframes/tablet/FF-34-T-close.png)

**2 · Business Rules**

| BR | R | Statement (first sentence, verbatim — the whole rule is in `02-business-rules.md`) | Status |
|---|---|---|---|
| `BR-FLD-00001` | R1 | The day list is ordered by appointment window, never by priority. | CONFIRMED — repo `BR-WRK-035` |
| `BR-FLD-00003` | R3 | All safety checks or none. | CONFIRMED — repo `BR-WRK-037` |
| `BR-FLD-00004` | R4 | Four outcomes: Passed · Partly done · Failed · Waiting on someone. | CONFIRMED (PO) |
| `BR-FLD-00009` | R9 | Travel and labour are separate clocks — depart, arrive, start. | CONFIRMED (PO) |
| `BR-FLD-00010` | R10 | Every status change is stamped with who and when, and is readable on the job | CONFIRMED (PO) |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | E2E-01: meter exchange at 1400 Elm Street, 09:00–11:00; Dana departs, arrives, ticks four safety rows, works six steps, takes readings, uses two parts, gets a signature, closes Passed | Twenty-three outbox items accepted in one batch, four photos follow; the office sees 2 h 10 m of labour and accepts |
| TC-2 · **negative** | FF-16 with 2 of 4 ticked | Tasks stay locked — *Tasks stay locked. All four required.* |
| TC-3 · **negative** | E2E-23: a completion arrives with 3 of 4 safety rows ticked from a handset with a wrong clock | The server re-derives the gate and refuses, naming the unticked row (R3) |
| TC-4 | E2E-04 / 05 / 06: close as Partly done, Failed (meter seized, with a photograph), Waiting on someone (dog out) | Each outcome carries through to the office queue and reads as itself (R4) |
| TC-5 | Every status change | Stamped who and when and readable on FF-31 (R10) |
| TC-6 · **tenant isolation** | R. Patel works for Silver Creek Water and Lone Star Water and signs in to Lone Star Water on the same handset | Only `field-lone-star-water.sqlite` is opened; not one Silver Creek row is readable (R131), and the server takes the tenant from the credential, never from the payload (R127) |

**4 · Test Data** — WO-4822 Meter exchange · Sarah Miller · 1400 Elm Street · Unit A · travel 14m (08:00→08:14) · on site from 08:46.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| outcome | FF-34 | R4 | outbox `close` → server `work_orders.outcome` | Passed · Partly done · Failed · Waiting on someone | user-input | one of four |
| safety ticks | FF-16 | R3 | handset `wo_item` kind=safety → outbox `safety_tick` | bool ×4 | user-input | all or none; server re-derives |

**6 · Acceptance** — **Given** a dispatched order, **when** the technician departs, arrives, passes safety, works it and closes it, **then** the office receives the order with its outcome, its clocks and its stamped history.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---

---
id: US-FLD-021
epic: EP-FLD-03
module: field-app
screens: [FF-28, FF-15]
wave: 4
status: ready
blocked_by: []
depends_on: [US-FLD-002]
journeys: []           # the E2E-nn cases cited in §3 become journeys under 08-qa/01-e2e/journeys/ (sibling lane)
rules: [BR-FLD-00031, BR-FLD-00062]
golden_tests: []
finance_calc: none
---
### US-FLD-021 — SOPs and safety documents ride with the job and open offline

**Requirement 21, in the design's words:** *SOPs riding with the job, opening offline* — section C · From the reference apps, confirmed into scope · standing *Ruled*.

**1 · Details** — As **Dana at the pit**, I want **the job's SOPs, the install guide and the premise notes on the phone**, so that **I can read them with no signal**. FF-28 lists documents for this job and those always on the phone; documents are kept to a 200 MB cap, evicted oldest first (R62).

**Screens (build from the images — B14 rules 42, 44, 45):** `FF-28` Documents — [phone](../wireframes/phone/FF-28-documents.png) · [tablet](../wireframes/tablet/FF-28-T-documents.png)<br>`FF-15` Job — [phone](../wireframes/phone/FF-15-job.png) · [tablet](../wireframes/tablet/FF-15-T-job.png)

**2 · Business Rules**

| BR | R | Statement (first sentence, verbatim — the whole rule is in `02-business-rules.md`) | Status |
|---|---|---|---|
| `BR-FLD-00031` | R31 | The map requires a signal. | CONFIRMED (PO) |
| `BR-FLD-00062` | R62 | Sent work is kept seven days; closed jobs fourteen; documents to a 200 MB cap, evicted oldest first. | DERIVED (decision log T-05) |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | FF-28 for WO-4822 offline | *Water shut-off SOP* (PDF, 4 pages) and *Neptune T-10 install guide* (12 pages) open from the phone |
| TC-2 | Premise notes | *Dog in the yard. Pit lid is heavy.* shows with the job |
| TC-3 · **negative** | Documents exceed 200 MB | The oldest are evicted first; a document for today's job is not |
| TC-4 | Footer | *14 documents · 22 MB · updated 07:42* |
| TC-5 · **tenant isolation** | R. Patel works for Silver Creek Water and Lone Star Water and signs in to Lone Star Water on the same handset | Only `field-lone-star-water.sqlite` is opened; not one Silver Creek row is readable (R131), and the server takes the tenant from the credential, never from the payload (R127) |

**4 · Test Data** — 14 documents, 22 MB, updated 07:42; confined space procedure, traffic control setup, emergency contacts always on the phone.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| document | FF-28 | Data.txt §2 | handset `document` (owner_kind, owner_id, local path) | file + row | integration | 200 MB cap (R62) |

**6 · Acceptance** — **Given** a job with SOPs attached, **when** the technician opens Documents with no signal, **then** every document for the job opens from the handset.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---

---
id: US-FLD-026
epic: EP-FLD-03
module: field-app
screens: [FF-15]
wave: 4
status: ready
blocked_by: []
depends_on: [US-FLD-002]
journeys: []           # the E2E-nn cases cited in §3 become journeys under 08-qa/01-e2e/journeys/ (sibling lane)
rules: [BR-FLD-00005, BR-FLD-00007, BR-FLD-00112]
golden_tests: []
finance_calc: none
---
### US-FLD-026 — The job shows the whole template — safety, tasks, materials, readings and help, each with a count and a state

**Requirement 26, in the design's words:** *The job shows the whole template — safety, tasks, materials, readings and help, each with a count and a state* — section E · From the walkthrough of the drawings · standing *New*.

**1 · Details** — As **Dana opening WO-4822**, I want **everything the template asks of this job on one screen, each with a count and a state**, so that **nothing is a bare link and I see what is left**. The order holds its own copy of the template, version stamped (R112).

**Screens (build from the images — B14 rules 42, 44, 45):** `FF-15` Job — [phone](../wireframes/phone/FF-15-job.png) · [tablet](../wireframes/tablet/FF-15-T-job.png)

**2 · Business Rules**

| BR | R | Statement (first sentence, verbatim — the whole rule is in `02-business-rules.md`) | Status |
|---|---|---|---|
| `BR-FLD-00005` | R5 | The job screen shows the whole template — safety, tasks, materials, readings, help — each with a count and a completion state | CONFIRMED (PO) |
| `BR-FLD-00007` | R7 | A field addition is never silent. | CONFIRMED (PO) |
| `BR-FLD-00112` | R112 | Raising an order starts with a template, and every published template is offered — recently used first, search behind it. | CONFIRMED (PO) |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | FF-15 for WO-4822 | Safety checks *4 of 4* · Tasks *3 of 8* (2 need a photo) · Materials *1 of 2* (1 not on the van) · Checklist *3 of 7* · Readings *1 of 3* (1 needs a photo, 1 flagged) · Asset papers · Help and SOPs · Crew · Notes · Activity |
| TC-2 | The primary button | *Continue — step 4 of 8* |
| TC-3 · **negative** | The office edits the template after WO-4822 was raised | WO-4822 is unchanged — it holds its own copy (R112) |
| TC-4 | A step added in the field | Counted in Tasks and shown as a variance (R7) |
| TC-5 · **tenant isolation** | R. Patel works for Silver Creek Water and Lone Star Water and signs in to Lone Star Water on the same handset | Only `field-lone-star-water.sqlite` is opened; not one Silver Creek row is readable (R131), and the server takes the tenant from the credential, never from the payload (R127) |

**4 · Test Data** — WO-4822 Meter exchange · residential · On site · P3 · 08:00–12:00 · asset W-4471 Neptune T-10 5/8".

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| section counts | FF-15 | R5 | handset `wo_item` by kind + `wo_reading` | n of m | computed-display | counted from rows |
| template version | FF-15 | R112 | handset `work_order.template_version` | int | integration | stamped at raise |

**6 · Acceptance** — **Given** an order raised from a template, **when** the technician opens it, **then** every section of the template is listed with its count and state.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---

---
id: US-FLD-029
epic: EP-FLD-03
module: field-app
screens: [FF-15, FF-47]
wave: 4
status: ready
blocked_by: []
depends_on: [US-FLD-008]
journeys: []           # the E2E-nn cases cited in §3 become journeys under 08-qa/01-e2e/journeys/ (sibling lane)
rules: [BR-FLD-00008, BR-FLD-00009, BR-FLD-00010]
golden_tests: []
finance_calc: none
---
### US-FLD-029 — Travel and time on the job — depart, arrive, start, pause, correct

**Requirement 29, in the design's words:** *Travel time and time on the job — depart, arrive, start, pause, correct* — section E · From the walkthrough of the drawings · standing *New*.

**1 · Details** — As **Dana**, I want **separate travel and labour clocks I can pause and correct**, so that **my hours are right without paperwork**. Both clocks are correctable by the technician and every change is stamped (R9, R10).

**Screens (build from the images — B14 rules 42, 44, 45):** `FF-15` Job — [phone](../wireframes/phone/FF-15-job.png) · [tablet](../wireframes/tablet/FF-15-T-job.png)<br>`FF-47` Timesheet — [phone](../wireframes/phone/FF-47-timesheet.png) · [tablet](../wireframes/tablet/FF-47-T-timesheet.png)

**2 · Business Rules**

| BR | R | Statement (first sentence, verbatim — the whole rule is in `02-business-rules.md`) | Status |
|---|---|---|---|
| `BR-FLD-00008` | R8 | Labour is per person, not per job. | CONFIRMED (PO) |
| `BR-FLD-00009` | R9 | Travel and labour are separate clocks — depart, arrive, start. | CONFIRMED (PO) |
| `BR-FLD-00010` | R10 | Every status change is stamped with who and when, and is readable on the job | CONFIRMED (PO) |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Depart 08:00, arrive 08:14 | Travel reads *14m · 08:00 → 08:14* |
| TC-2 | Start work 08:46 | On site reads *Running since 08:46* |
| TC-3 | *Correct time* on travel to 08:02 | The correction is saved and stamped who and when on Activity (R10) |
| TC-4 · **negative** | Pause, then close without resuming | The labour clock stops at the pause; the close records the paused total |
| TC-5 · **tenant isolation** | R. Patel works for Silver Creek Water and Lone Star Water and signs in to Lone Star Water on the same handset | Only `field-lone-star-water.sqlite` is opened; not one Silver Creek row is readable (R131), and the server takes the tenant from the credential, never from the payload (R127) |

**4 · Test Data** — Travel 14m · on site 1h 12m (08:46–09:58).

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| travel / labour | FF-15 | R9 | handset `crew_time` (per person per order) → outbox `time` | minutes | system-derived | correctable, stamped |

**6 · Acceptance** — **Given** a technician on a job, **when** they depart, arrive, start, pause and correct, **then** travel and labour are recorded separately and every correction is stamped.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---

---
id: US-FLD-071
epic: EP-FLD-03
module: field-app
screens: [FF-58, FF-15]
wave: 4
status: ready
blocked_by: []
depends_on: [US-FLD-008]
journeys: []           # the E2E-nn cases cited in §3 become journeys under 08-qa/01-e2e/journeys/ (sibling lane)
rules: [BR-FLD-00106, BR-FLD-00107, BR-FLD-00038]
golden_tests: []
finance_calc: none
---
### US-FLD-071 — Hand an assigned job back, with a reason

**Requirement 71, in the design's words:** *A technician can hand an assigned job back, with a reason from a short list and optional dictation. It returns to Queued, unassigned, carrying their name and reason — no eighth dispatch state is invented. An emergency cannot be handed back from the app; that takes a call to dispatch* — section K · The seven asks of 2026-10-20 · standing *Ruled*.

**1 · Details** — As **Dana with no part on the van**, I want **to hand WO-4824 back with a reason from a short list and optional dictation**, so that **dispatch reassigns it**. It returns to Queued, unassigned, carrying my name and reason — no eighth dispatch state (R106). An emergency cannot be handed back from the app (R107).

**Screens (build from the images — B14 rules 42, 44, 45):** `FF-58` Hand it back — [phone](../wireframes/phone/FF-58-hand-it-back.png) · [tablet](../wireframes/tablet/FF-58-T-hand-it-back.png)<br>`FF-15` Job — [phone](../wireframes/phone/FF-15-job.png) · [tablet](../wireframes/tablet/FF-15-T-job.png)

**2 · Business Rules**

| BR | R | Statement (first sentence, verbatim — the whole rule is in `02-business-rules.md`) | Status |
|---|---|---|---|
| `BR-FLD-00106` | R106 | Handing a job back returns it to Queued, unassigned, with the technician’s name and reason on it. | CONFIRMED (PO) |
| `BR-FLD-00107` | R107 | An emergency cannot be handed back from the app. | CONFIRMED (PO) |
| `BR-FLD-00038` | R38 | A technician taps, never types. | CONFIRMED (PO) |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Hand back WO-4824, reason *No parts on the van* | The order is Queued and unassigned with *D. Ortiz · No parts on the van*; dispatch reassigns |
| TC-2 · **negative** | Hand back an emergency | Not offered; the sheet says to ring dispatch (R107) |
| TC-3 · **negative** | The server receives a hand-back as a new status | None exists — Queued is one of the seven signed states (R106, `BR-WRK-023`) |
| TC-4 | *Keep it* | Nothing changes |
| TC-5 · **tenant isolation** | R. Patel works for Silver Creek Water and Lone Star Water and signs in to Lone Star Water on the same handset | Only `field-lone-star-water.sqlite` is opened; not one Silver Creek row is readable (R131), and the server takes the tenant from the credential, never from the payload (R127) |

**4 · Test Data** — WO-4824 Disconnect · 218 Pecan Grove · 11:00–13:00 · reasons: Not my skills · No parts on the van · Cannot reach it today · Needs two people · Already done by someone · Something else.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| reason | FF-58 | R106 | outbox `hand_back` → server assignment history | choice + optional text | user-input | required |

**6 · Acceptance** — **Given** an assigned, non-emergency job, **when** the technician hands it back with a reason, **then** it is Queued, unassigned, carrying their name and reason.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.
