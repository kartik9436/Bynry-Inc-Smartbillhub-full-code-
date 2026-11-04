# EP-FLD-04 — Doing the work — tasks, checklists, readings, photographs, materials and parts

**Module:** field-app (`18-field-app`, module code FLD) · **Wave:** 5 · **Design tasks:** T-19 · **Screens:** FF-07, FF-15, FF-21, FF-22, FF-20, FF-23, FF-24, FF-49, FF-19, FF-17, FF-18, FF-59 · **Status:** draft (2026-10-21, `CR-187-BRC10`)

## Scope

**In:** the design's flow group *FF-17 to FF-24, FF-59* and the requirements whose screens sit in it — US-FLD-005 (requirement 5), US-FLD-009 (requirement 9), US-FLD-016 (requirement 16), US-FLD-018 (requirement 18), US-FLD-027 (requirement 27), US-FLD-028 (requirement 28), US-FLD-072 (requirement 72), US-FLD-074 (requirement 74).

**Out:** everything the design's *Scope · Out* list excludes (`01-overview.md` §5) — taking payment on site, linear assets, inspection rounds, offline maps, a dispatcher app, live crew tracking, van stock-takes, customer-facing features, a watch app.

**Source:** the *SMART360 Next Field App* design canvas, version of 2026-10-21. The screens are the images in `../wireframes/` and they are the specification (B14 rule 42; PO 2026-10-21, *"please ensure all native app screens are build using images not using text or contents"*). Figures on a board are illustrations (B14 rule 37) and are used below as test data only.

⚠ **1 of these stories is `blocked`** — US-FLD-074 — each on a collision between the design and a rule already signed in this repository, named in plain words in its §8. The open-questions lane (DOC-C) mints the `OQ-FLD-` id; until then `blocked_by` is empty and the gap is the comment beside it.

## Capability matrix (list screens only — B9 conformance)

No list screen in this group.

## Stories

---
id: US-FLD-005
epic: EP-FLD-04
module: field-app
screens: [FF-07, FF-15, FF-21, FF-22]
wave: 5
status: ready
blocked_by: []
depends_on: [US-FLD-027]
journeys: []           # the E2E-nn cases cited in §3 become journeys under 08-qa/01-e2e/journeys/ (sibling lane)
rules: [BR-FLD-00090, BR-FLD-00091, BR-FLD-00094]
golden_tests: []
finance_calc: none
---
### US-FLD-005 — Position when a job opens, and every photograph stamped with date, time, coordinates, technician and order

**Requirement 5, in the design's words:** *GPS and watermarks — position captured when a job opens (lat, lng, accuracy). Photos stamped with date, time, coordinates, technician and work-order number* — section A · The original brief · standing *GPS built*.

**1 · Details** — As **Dana**, I want **my position captured with its accuracy when I arrive and every photo stamped**, so that **the office can trust where and when the work happened**. FF-07 asks for location, camera and notifications, each for one stated reason. A poor fix warns and accepts (R91); the stamp is burned into the pixels (R94).

**Screens (build from the images — B14 rules 42, 44, 45):** `FF-07` Permissions — [phone](../wireframes/phone/FF-07-permissions.png) · [tablet](../wireframes/tablet/FF-07-T-permissions.png)<br>`FF-15` Job — [phone](../wireframes/phone/FF-15-job.png) · [tablet](../wireframes/tablet/FF-15-T-job.png)<br>`FF-21` Photos — [phone](../wireframes/phone/FF-21-photos.png) · [tablet](../wireframes/tablet/FF-21-T-photos.png)<br>`FF-22` Compare — [phone](../wireframes/phone/FF-22-compare.png) · [tablet](../wireframes/tablet/FF-22-T-before-and-after.png)

**2 · Business Rules**

| BR | R | Statement (first sentence, verbatim — the whole rule is in `02-business-rules.md`) | Status |
|---|---|---|---|
| `BR-FLD-00090` | R90 | Position is taken at save, automatically, with its accuracy, and is never a field anybody fills in. | DERIVED (decision log T-05) |
| `BR-FLD-00091` | R91 | A poor fix or no fix warns and accepts. | DERIVED (decision log T-05) |
| `BR-FLD-00094` | R94 | The stamp is burned into the pixels, never laid over them — date, time, position with accuracy, reader, meter, route. | CONFIRMED (PO) |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Arrive at 1400 Elm Street | Position *30.2651, -97.7494 · ±4m* is on the Arrived event |
| TC-2 | Take *Meter in place* before photo | Stamp reads *20 Oct 2026 · 09:18 · 30.2651, -97.7494 · ±4m · D. Ortiz · WO-4822* |
| TC-3 · **negative** | No fix in a basement | The capture is accepted with no position and a warning (R91) |
| TC-4 · **negative** | Location permission off on FF-07 | The app still opens the day; captures carry no position |
| TC-5 · **tenant isolation** | R. Patel works for Silver Creek Water and Lone Star Water and signs in to Lone Star Water on the same handset | Only `field-lone-star-water.sqlite` is opened; not one Silver Creek row is readable (R131), and the server takes the tenant from the credential, never from the payload (R127) |

**4 · Test Data** — 30.2651, -97.7494 ±4m; before 09:18, after 09:52.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| lat, lng, accuracy | FF-15, FF-21 | R90 | outbox `lat`,`lng`,`accuracy_m`; photo pixels | degrees, metres | system-derived | never typed |

**6 · Acceptance** — **Given** a technician on site, **when** they arrive and photograph the work, **then** each event and photo carries position with accuracy, and the photo's stamp is in its pixels.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---

---
id: US-FLD-009
epic: EP-FLD-04
module: field-app
screens: [FF-20]
wave: 5
status: ready
blocked_by: []
depends_on: [US-FLD-026]
journeys: []           # the E2E-nn cases cited in §3 become journeys under 08-qa/01-e2e/journeys/ (sibling lane)
rules: [BR-FLD-00011, BR-FLD-00012, BR-FLD-00013, BR-FLD-00014]
golden_tests: []
finance_calc: none
---
### US-FLD-009 — Meter readings with explicit units — out of range is flagged, never blocks

**Requirement 9, in the design's words:** *Meter readings — numeric and text with explicit units (kWh, gallons, CCF). Out-of-range flagged for review without blocking completion* — section A · The original brief · standing *Built*.

**1 · Details** — As **Dana reading W-4471 and its two sub-meters**, I want **to enter each reading with its unit and be told when it is out of range**, so that **typos are caught and true values are kept**. Out of range: type it a second time; the same value twice is accepted and marked for the office; a different second value was a typo and no flag is raised (R11). Every quantity carries its unit (R12).

**Screens (build from the images — B14 rules 42, 44, 45):** `FF-20` Readings — [phone](../wireframes/phone/FF-20-readings.png) · [tablet](../wireframes/tablet/FF-20-T-readings.png)

**2 · Business Rules**

| BR | R | Statement (first sentence, verbatim — the whole rule is in `02-business-rules.md`) | Status |
|---|---|---|---|
| `BR-FLD-00011` | R11 | A reading outside its range is flagged, never refused. | CONFIRMED (PO) |
| `BR-FLD-00012` | R12 | Every quantity carries its unit. | CONFIRMED — repo `BR-SHL-023` |
| `BR-FLD-00013` | R13 | "Unable to read" is a reading-level answer, not a fifth outcome. | CONFIRMED (PO) |
| `BR-FLD-00014` | R14 | A master and its sub-meters are read in one visit, and the app is built for that shape rather than one meter per job | CONFIRMED — repo rule |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Master W-4471 closing read 48,200 gal, expected 40,000–50,000 | Accepted, not flagged |
| TC-2 | Closing read 58,000 gal | *Outside expected range. Enter it again.*; the same 58,000 again → *Accepted. Marked for the office.* |
| TC-3 · **negative** | 58,000 then 48,200 | The first was a typo; 48,200 is saved and no flag is raised (R11) |
| TC-4 | Sub-meter W-4471-B *Unable to read* | Recorded at reading level; the job can still pass (R13) |
| TC-5 · **negative** | A reading with no unit | Impossible — the unit is shown beside the number and stored with it (R12) |
| TC-6 · **tenant isolation** | R. Patel works for Silver Creek Water and Lone Star Water and signs in to Lone Star Water on the same handset | Only `field-lone-star-water.sqlite` is opened; not one Silver Creek row is readable (R131), and the server takes the tenant from the credential, never from the payload (R127) |

**4 · Test Data** — W-4471 last 48,180 gal expected 40,000–50,000 · W-4471-A Unit A last 12,210 expected 10,000–14,000 · W-4471-B Unit B.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| value + unit | FF-20 | R12 | handset `wo_reading` (value, unit, min, max, flagged, unable_to_read) | number + gal/kWh/CCF | user-input | range compared as columns (R130) |

**6 · Acceptance** — **Given** a job with readings, **when** the technician enters an out-of-range value twice, **then** it is accepted and flagged, and the job can still close.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---

---
id: US-FLD-016
epic: EP-FLD-04
module: field-app
screens: [FF-23, FF-24, FF-49]
wave: 5
status: ready
blocked_by: []
depends_on: [US-FLD-026]
journeys: []           # the E2E-nn cases cited in §3 become journeys under 08-qa/01-e2e/journeys/ (sibling lane)
rules: [BR-FLD-00007, BR-FLD-00020, BR-FLD-00016]
golden_tests: []
finance_calc: none
---
### US-FLD-016 — Van stock and parts consumption on the phone

**Requirement 16, in the design's words:** *Van stock and parts consumption on the phone* — section C · From the reference apps, confirmed into scope · standing *Backend only*.

**1 · Details** — As **Dana**, I want **to record the parts I used against the step and see what is on the van**, so that **the office sees used-of-planned and I know what to ask the depot for**. The van screen reads stock; it does not reconcile it (walkthrough scope, *Out*). Unit costs show up to 4 decimals (R20).

**Screens (build from the images — B14 rules 42, 44, 45):** `FF-23` Materials — [phone](../wireframes/phone/FF-23-materials.png) · [tablet](../wireframes/tablet/FF-23-T-materials.png)<br>`FF-24` Parts used — [phone](../wireframes/phone/FF-24-parts-used.png) · [tablet](../wireframes/tablet/FF-24-T-parts-used.png)<br>`FF-49` Van — [phone](../wireframes/phone/FF-49-van.png) · [tablet](../wireframes/tablet/FF-49-T-van.png)

**2 · Business Rules**

| BR | R | Statement (first sentence, verbatim — the whole rule is in `02-business-rules.md`) | Status |
|---|---|---|---|
| `BR-FLD-00007` | R7 | A field addition is never silent. | CONFIRMED (PO) |
| `BR-FLD-00020` | R20 | Money shows to 2 decimals; a unit price shows up to 4. | CONFIRMED — repo `BR-RAT-087` |
| `BR-FLD-00016` | R16 | The field app reads money and never writes it. | CONFIRMED (PO) |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | FF-24 on step 4 *Fit new meter and seal*: meter MTR-W58 serial W-9044 ×1, wire seal ×1 | Recorded as used; *Van drops to 0 of this meter* |
| TC-2 | FF-49 Van 14 | *Water meter 5/8" · $92.4000 each · 0 · need 1 · Ask the depot*; wire seal 26; door hanger 48 |
| TC-3 · **negative** | Try to edit a van count on FF-49 | Not possible — inventory counts are out of scope; *Count the van* is the only van action drawn |
| TC-4 · **negative** | Any money write from these screens | None — the field app reads money and never writes it (R16) |
| TC-5 · **tenant isolation** | R. Patel works for Silver Creek Water and Lone Star Water and signs in to Lone Star Water on the same handset | Only `field-lone-star-water.sqlite` is opened; not one Silver Creek row is readable (R131), and the server takes the tenant from the credential, never from the payload (R127) |

**4 · Test Data** — Van 14 · counted 07:44 · MTR-W58 $92.4000 · SEAL-W 26 · CPL-58 $18.5000 · DH-01 48.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| part used | FF-24 | requirement 16 | handset `wo_item` kind=material → outbox `material` | qty | user-input | against a step |
| unit cost | FF-49 | R20 | mirror of the parts register | money, 4 dp shown | reference-data | display only |

**6 · Acceptance** — **Given** a job with planned parts, **when** the technician records parts used, **then** used-of-planned is recorded and the van shows what is left.

**7 · Finance Calculation** — N/A. The field app reads money and never writes it (R16).

**8 · Open Questions** — None.

---

---
id: US-FLD-018
epic: EP-FLD-04
module: field-app
screens: [FF-19]
wave: 5
status: ready
blocked_by: []
depends_on: [US-FLD-026]
journeys: []           # the E2E-nn cases cited in §3 become journeys under 08-qa/01-e2e/journeys/ (sibling lane)
rules: [BR-FLD-00038]
golden_tests: []
finance_calc: none
---
### US-FLD-018 — Conditional checklists — questions that branch on the answer

**Requirement 18, in the design's words:** *Conditional checklists — questions that branch on the answer* — section C · From the reference apps, confirmed into scope · standing *New*.

**1 · Details** — As **Dana**, I want **a checklist that asks the next question because of my last answer**, so that **I only answer what applies**. Answers are taps (R38).

**Screens (build from the images — B14 rules 42, 44, 45):** `FF-19` Checklist — [phone](../wireframes/phone/FF-19-checklist.png) · [tablet](../wireframes/tablet/FF-19-T-checklist.png)

**2 · Business Rules**

| BR | R | Statement (first sentence, verbatim — the whole rule is in `02-business-rules.md`) | Status |
|---|---|---|---|
| `BR-FLD-00038` | R38 | A technician taps, never types. | CONFIRMED (PO) |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Q1 *Did you speak to the customer?* → Yes | Q2 *Were they happy with the work?* appears, marked *Because you said yes* |
| TC-2 | Q4 *Was the old seal intact?* → No | *No opens a tamper report* |
| TC-3 · **negative** | Q1 → No | Q2 does not appear |
| TC-4 | *Save and exit* at 3 of 5 | Progress saved; FF-15 shows *Checklist 3 of 7* |
| TC-5 · **tenant isolation** | R. Patel works for Silver Creek Water and Lone Star Water and signs in to Lone Star Water on the same handset | Only `field-lone-star-water.sqlite` is opened; not one Silver Creek row is readable (R131), and the server takes the tenant from the credential, never from the payload (R127) |

**4 · Test Data** — Meter exchange checklist, 5 questions; Q3 *New meter start read* in gal.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| answer | FF-19 | requirement 18 | handset `wo_item` kind=checklist (detail JSON holds the branch) | choice | user-input | branch from the template |

**6 · Acceptance** — **Given** a checklist with a branch, **when** the technician answers, **then** only the questions that apply are asked.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---

---
id: US-FLD-027
epic: EP-FLD-04
module: field-app
screens: [FF-17, FF-20, FF-21, FF-22]
wave: 5
status: ready
blocked_by: []
depends_on: [US-FLD-004]
journeys: []           # the E2E-nn cases cited in §3 become journeys under 08-qa/01-e2e/journeys/ (sibling lane)
rules: [BR-FLD-00006, BR-FLD-00051, BR-FLD-00052, BR-FLD-00093, BR-FLD-00123]
golden_tests: []
finance_calc: none
---
### US-FLD-027 — Photos belong to the task and the reading, as the template defines — the gallery is a review

**Requirement 27, in the design's words:** *Photos belong to the task and to the reading, as the template defines — not to a loose gallery* — section E · From the walkthrough of the drawings · standing *New*.

**1 · Details** — As **Dana**, I want **to take each photo on the step or reading that asks for it**, so that **the office sees what each photo proves**. FF-21 is a review, never the place of capture (R6); FF-22 compares before and after (side by side on a tablet). A photo is a file on disk and a row, declared with the data, bytes after (R52, R123).

**Screens (build from the images — B14 rules 42, 44, 45):** `FF-17` Tasks — [phone](../wireframes/phone/FF-17-tasks.png) · [tablet](../wireframes/tablet/FF-17-T-tasks.png)<br>`FF-20` Readings — [phone](../wireframes/phone/FF-20-readings.png) · [tablet](../wireframes/tablet/FF-20-T-readings.png)<br>`FF-21` Photos — [phone](../wireframes/phone/FF-21-photos.png) · [tablet](../wireframes/tablet/FF-21-T-photos.png)<br>`FF-22` Compare — [phone](../wireframes/phone/FF-22-compare.png) · [tablet](../wireframes/tablet/FF-22-T-before-and-after.png)

**2 · Business Rules**

| BR | R | Statement (first sentence, verbatim — the whole rule is in `02-business-rules.md`) | Status |
|---|---|---|---|
| `BR-FLD-00006` | R6 | A photo belongs to the thing it proves — a task or a reading, as the template defines. | CONFIRMED (PO) |
| `BR-FLD-00051` | R51 | Data before photographs, always. | CONFIRMED — repo `BR-WRK-062` |
| `BR-FLD-00052` | R52 | A photograph is a file on disk and a row in the database, never bytes in the database. | DERIVED (decision log T-05) |
| `BR-FLD-00093` | R93 | A photograph comes from the camera. | CONFIRMED (PO) |
| `BR-FLD-00123` | R123 | A photograph is DECLARED with the data and its bytes follow separately. | CONFIRMED — repo `BR-WRK-062` |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Step 2 and step 5 demand a photograph (E2E-01) | Each is taken on its step; FF-21 lists them under the step |
| TC-2 | FF-22 Compare | Before 09:18 and after 09:52 · *34 min later*, stacked or side by side |
| TC-3 · **negative** | Look for *add from gallery* on FF-21 | Not offered — camera only (R93) |
| TC-4 | Security seal photo waiting | *Waiting to upload · 1.2 MB*; the declaration already went with the data (R123) |
| TC-5 · **tenant isolation** | R. Patel works for Silver Creek Water and Lone Star Water and signs in to Lone Star Water on the same handset | Only `field-lone-star-water.sqlite` is opened; not one Silver Creek row is readable (R131), and the server takes the tenant from the credential, never from the payload (R127) |

**4 · Test Data** — WO-4822: Meter in place (before/after), New meter fitted (required), Security seal.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| photo | FF-17/20/21 | R52 | handset `photo` (local_path, outbox_id) + file on disk | file + row | user-input | camera only |
| what it proves | FF-21 | R123 | photo declaration (id, sha256, proves, required) | ref | system-derived | declared with the data |

**6 · Acceptance** — **Given** a template that asks for photos on steps and readings, **when** the technician captures them, **then** each photo belongs to its step or reading and the gallery only reviews them.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---

---
id: US-FLD-028
epic: EP-FLD-04
module: field-app
screens: [FF-18, FF-23, FF-17]
wave: 5
status: ready
blocked_by: []
depends_on: [US-FLD-026]
journeys: []           # the E2E-nn cases cited in §3 become journeys under 08-qa/01-e2e/journeys/ (sibling lane)
rules: [BR-FLD-00007, BR-FLD-00130]
golden_tests: []
finance_calc: none
---
### US-FLD-028 — Add a task or a material in the field, with a reason, shown as a variance

**Requirement 28, in the design's words:** *Add a task or a material in the field, with a reason, shown as a variance against the template* — section E · From the walkthrough of the drawings · standing *New*.

**1 · Details** — As **Dana with a corroded coupling**, I want **to add the step and the part I needed, with why**, so that **the office sees the variance against the template**. A field addition is never silent (R7).

**Screens (build from the images — B14 rules 42, 44, 45):** `FF-18` Add step — [phone](../wireframes/phone/FF-18-add-step.png) · [tablet](../wireframes/tablet/FF-18-T-add-a-step.png)<br>`FF-23` Materials — [phone](../wireframes/phone/FF-23-materials.png) · [tablet](../wireframes/tablet/FF-23-T-materials.png)<br>`FF-17` Tasks — [phone](../wireframes/phone/FF-17-tasks.png) · [tablet](../wireframes/tablet/FF-17-T-tasks.png)

**2 · Business Rules**

| BR | R | Statement (first sentence, verbatim — the whole rule is in `02-business-rules.md`) | Status |
|---|---|---|---|
| `BR-FLD-00007` | R7 | A field addition is never silent. | CONFIRMED (PO) |
| `BR-FLD-00130` | R130 | One row per thing to do on a job, in one table with a kind — not a table per kind. | CONFIRMED (PO) |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Add step *Replace corroded coupling*, 15 min, reason *Old coupling corroded through, would not reseal.* | Listed under *Added in the field · D. Ortiz 09:31* |
| TC-2 | Add material *Meter coupling kit CPL-58* | *1 extra, 1 short. The office sees both.* |
| TC-3 · **negative** | Add a step with no reason | Not saved — a reason is required (R7) |
| TC-4 | Needs a photo toggled on the added step | The step demands a photo like a template step |
| TC-5 · **tenant isolation** | R. Patel works for Silver Creek Water and Lone Star Water and signs in to Lone Star Water on the same handset | Only `field-lone-star-water.sqlite` is opened; not one Silver Creek row is readable (R131), and the server takes the tenant from the credential, never from the payload (R127) |

**4 · Test Data** — Step 5 *Replace corroded coupling* 15 min · CPL-58 $18.5000.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| added_in_field + reason | FF-18/23 | R130 | handset `wo_item` (added_in_field, reason) | bool + text | user-input | reason required |

**6 · Acceptance** — **Given** a job whose template missed something, **when** the technician adds a step or a part with a reason, **then** it appears as a variance the office can see.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---

---
id: US-FLD-072
epic: EP-FLD-04
module: field-app
screens: [FF-59]
wave: 5
status: ready
blocked_by: []
depends_on: [US-FLD-009]
journeys: []           # the E2E-nn cases cited in §3 become journeys under 08-qa/01-e2e/journeys/ (sibling lane)
rules: [BR-FLD-00007, BR-FLD-00012, BR-FLD-00011]
golden_tests: []
finance_calc: none
---
### US-FLD-072 — Add a reading the template did not ask for

**Requirement 72, in the design's words:** *A reading the template did not ask for can be added on a service order — the mirror of adding a step or a part. A reason is required and it shows as a variance. A first reading on a new meter has no expected range, so nothing is flagged* — section K · The seven asks of 2026-10-20 · standing *New*.

**1 · Details** — As **Dana fitting MTR-0903**, I want **to add a start read the template lacked**, so that **the new meter has its first reading**. A reason is required and it shows as a variance; a first reading on a new meter has no expected range, so nothing is flagged.

**Screens (build from the images — B14 rules 42, 44, 45):** `FF-59` Add a reading — [phone](../wireframes/phone/FF-59-add-a-reading.png) · [tablet](../wireframes/tablet/FF-59-T-add-a-reading.png)

**2 · Business Rules**

| BR | R | Statement (first sentence, verbatim — the whole rule is in `02-business-rules.md`) | Status |
|---|---|---|---|
| `BR-FLD-00007` | R7 | A field addition is never silent. | CONFIRMED (PO) |
| `BR-FLD-00012` | R12 | Every quantity carries its unit. | CONFIRMED — repo `BR-SHL-023` |
| `BR-FLD-00011` | R11 | A reading outside its range is flagged, never refused. | CONFIRMED (PO) |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Add a reading on MTR-0903 · Unit 3, reason *Meter not on the list*, 00,124 gal | Saved as a variance; no flag |
| TC-2 · **negative** | No reason chosen | *Add it* stays unavailable — the reason is required |
| TC-3 · **negative** | A meter at another premises | Not offered — only meters at this premises |
| TC-4 | Unit | Chosen explicitly (gal · CCF · kWh), never assumed from the service (R12) |
| TC-5 · **tenant isolation** | R. Patel works for Silver Creek Water and Lone Star Water and signs in to Lone Star Water on the same handset | Only `field-lone-star-water.sqlite` is opened; not one Silver Creek row is readable (R131), and the server takes the tenant from the credential, never from the payload (R127) |

**4 · Test Data** — MTR-0903 · Unit 3 · 00,124 gal · reasons: Meter not on the list · Second register · Office asked · Template wrong.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| added reading | FF-59 | requirement 72 | handset `wo_reading` (added_in_field, reason) | number + unit | user-input | reason required; no range |

**6 · Acceptance** — **Given** a meter the template did not list, **when** the technician adds a reading with a reason, **then** it is saved as a variance and is not flagged.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---

---
id: US-FLD-074
epic: EP-FLD-04
module: field-app
screens: [FF-17, FF-20, FF-21]
wave: 5
status: blocked
blocked_by: []          # the gap is named in §8; its OQ-FLD id is minted by the open-questions lane (DOC-C) and filled in here
depends_on: [US-FLD-027]
journeys: []           # the E2E-nn cases cited in §3 become journeys under 08-qa/01-e2e/journeys/ (sibling lane)
rules: [BR-FLD-00110, BR-FLD-00006]
golden_tests: []
finance_calc: none
---
### US-FLD-074 — Several photographs on one task, as many as the template says

**Requirement 74, in the design's words:** *Several photographs on one task, with the template saying how many — typically three for before, during and after. A thumbnail strip, not one thumbnail. Short of the count is a warning, never a block* — section K · The seven asks of 2026-10-20 · standing *Ruled*.

**1 · Details** — As **Dana on step 4**, I want **a thumbnail strip and the count the template asks for**, so that **I take before, during and after**. Short of the count is a warning, never a block (R110).

**Screens (build from the images — B14 rules 42, 44, 45):** `FF-17` Tasks — [phone](../wireframes/phone/FF-17-tasks.png) · [tablet](../wireframes/tablet/FF-17-T-tasks.png)<br>`FF-20` Readings — [phone](../wireframes/phone/FF-20-readings.png) · [tablet](../wireframes/tablet/FF-20-T-readings.png)<br>`FF-21` Photos — [phone](../wireframes/phone/FF-21-photos.png) · [tablet](../wireframes/tablet/FF-21-T-photos.png)

**2 · Business Rules**

| BR | R | Statement (first sentence, verbatim — the whole rule is in `02-business-rules.md`) | Status |
|---|---|---|---|
| `BR-FLD-00110` | R110 | The template says how many photographs a task needs, not just whether it needs one. | CONFIRMED (PO) |
| `BR-FLD-00006` | R6 | A photo belongs to the thing it proves — a task or a reading, as the template defines. | CONFIRMED (PO) |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Step 4 *Fit new meter and seal* needs 3, 1 taken | *This step needs 3 photos · 1 so far*; *Two more*; *Short is a warning, never a block.* |
| TC-2 | Mark done at 1 of 3 | Done, with the shortfall shown to the office |
| TC-3 | Sub-meter W-4471-B reading with 3 photos | A strip of three thumbnails |
| TC-4 · **negative** | Close the job with a required photo never taken | **Blocked** — see §8 |
| TC-5 · **tenant isolation** | R. Patel works for Silver Creek Water and Lone Star Water and signs in to Lone Star Water on the same handset | Only `field-lone-star-water.sqlite` is opened; not one Silver Creek row is readable (R131), and the server takes the tenant from the credential, never from the payload (R127) |

**4 · Test Data** — Step 4 needs 3 photos (1 at 20 Oct 10:41); step 8 *Photograph new meter fitted* 2 photos.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| photo count | FF-17 | R110 | template step `photo_count` → handset `wo_item` | int | reference-data | warns when short |

**6 · Acceptance** — **Given** a step that asks for three photos, **when** the technician takes one and marks it done, **then** it is done with a warning, and the office sees the shortfall.

**7 · Finance Calculation** — N/A.

**8 · Open Questions**

| OQ-ID | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| *to be minted by DOC-C* | Whether a REQUIRED photograph that was never taken stops the close: R110 and requirement 74 say short of the count warns and never blocks; the signed `BR-WRK-040` says a missing required photograph stops the job closing (and `BR-WRK-062` lets a close through while required photos are still uploading). Which rule governs a required photo with zero taken is unruled. | the test case marked **Blocked** in §3 | Product Owner (a collision with a signed rule — law 13) | OPEN — not yet in the register |
