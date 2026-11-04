# EP-FLD-12 — Reads — the reading and its evidence

**Module:** field-app (`18-field-app`, module code FLD) · **Wave:** 11 · **Design tasks:** Reads tab §3 · **Screens:** RW-15, RW-16, RW-09, RW-13, RW-17, RW-14, RW-24 · **Status:** draft (2026-10-21, `CR-187-BRC10`)

## Scope

**In:** the design's flow group *RW-13 to RW-17* and the requirements whose screens sit in it — US-FLD-059 (requirement 59), US-FLD-063 (requirement 63), US-FLD-064 (requirement 64), US-FLD-065 (requirement 65), US-FLD-066 (requirement 66), US-FLD-067 (requirement 67), US-FLD-068 (requirement 68), US-FLD-069 (requirement 69).

**Out:** everything the design's *Scope · Out* list excludes (`01-overview.md` §5) — taking payment on site, linear assets, inspection rounds, offline maps, a dispatcher app, live crew tracking, van stock-takes, customer-facing features, a watch app.

**Source:** the *SMART360 Next Field App* design canvas, version of 2026-10-21. The screens are the images in `../wireframes/` and they are the specification (B14 rule 42; PO 2026-10-21, *"please ensure all native app screens are build using images not using text or contents"*). Figures on a board are illustrations (B14 rule 37) and are used below as test data only.

## Capability matrix (list screens only — B9 conformance)

No list screen in this group.

## Stories

---
id: US-FLD-059
epic: EP-FLD-12
module: field-app
screens: [RW-15, RW-16, RW-09]
wave: 11
status: ready
blocked_by: []
depends_on: [US-FLD-057]
journeys: []           # the E2E-nn cases cited in §3 become journeys under 08-qa/01-e2e/journeys/ (sibling lane)
rules: [BR-FLD-00080, BR-FLD-00081, BR-FLD-00096]
golden_tests: []
finance_calc: none
---
### US-FLD-059 — An out-of-range reading is warned and then accepted

**Requirement 59, in the design's words:** *An out-of-range reading is warned and then accepted. The warning names the consumption it implies and offers a re-read; the reader can always proceed, and the office gets it flagged* — section I · Reading meters on a route · standing *Ruled*.

**1 · Details** — As **Ray typing 71,400**, I want **the warning to name the consumption it implies and offer a re-read first**, so that **I catch a digit too many — and can always proceed** (R80). A reading below the previous is its own warning (R81).

**Screens (build from the images — B14 rules 42, 44, 45):** `RW-15` High or low — [phone](../wireframes/reads/RW-15-high-or-low.png) · [tablet](../wireframes/tablet/RW-15-T-high-or-low.png)<br>`RW-16` Second look — [phone](../wireframes/reads/RW-16-second-look.png) · [tablet](../wireframes/tablet/RW-16-T-second-look.png)<br>`RW-09` Read entry — [phone](../wireframes/reads/RW-09-read-entry.png) · [tablet](../wireframes/tablet/RW-09-T-read-entry.png)

**2 · Business Rules**

| BR | R | Statement (first sentence, verbatim — the whole rule is in `02-business-rules.md`) | Status |
|---|---|---|---|
| `BR-FLD-00080` | R80 | A reading is warned, never blocked. | CONFIRMED (PO) |
| `BR-FLD-00081` | R81 | A reading below the previous one is its own warning, not a “low” one. | DERIVED (decision log T-05) |
| `BR-FLD-00096` | R96 | Two statuses, never merged. | DERIVED (decision log T-05) |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | RW-15: 71,400 against 40,000–56,000 | *That is three times last month · usual month 7,800 gal · this would be 23,190 gal*; *Read it again* first, *Accept 71,400 anyway* second |
| TC-2 | RW-16 second try 52,410 | Both entries kept; *Nothing is overwritten. Both entries go to the office.* |
| TC-3 | Under 48,210 or over 56,000 on RW-09 | The figure turns amber and the button becomes *Accept anyway* |
| TC-4 · **negative** | A reading below last month's | Warned as below-previous, not as low; accepted; the office's engine decides (R81) |
| TC-5 · **tenant isolation** | Ray's route WLK-07 belongs to Silver Creek Water; a Lone Star Water route is downloaded for the same reader on the same handset | The two routes live in two database files; Silver Creek's walk never lists a Lone Star stop (R131), and the server reads the tenant from the credential (R127) |

**4 · Test Data** — MTR-0471 last 48,210 · typed 71,400 at 10:42 · re-read 52,410 at 10:49.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| reader status | RW-15 | R96 | handset `route_read.reader_status` | read · could not read · read with a problem | system-derived | never merged with the engine's status |

**6 · Acceptance** — **Given** an out-of-range reading, **when** the reader is warned, **then** they can re-read or accept, and the office gets it flagged.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---

---
id: US-FLD-063
epic: EP-FLD-12
module: field-app
screens: [RW-13, RW-09]
wave: 11
status: ready
blocked_by: []
depends_on: [US-FLD-059]
journeys: []           # the E2E-nn cases cited in §3 become journeys under 08-qa/01-e2e/journeys/ (sibling lane)
rules: [BR-FLD-00089, BR-FLD-00090]
golden_tests: []
finance_calc: none
---
### US-FLD-063 — Position at the moment the reading is saved, with its distance to the meter's recorded place

**Requirement 63, in the design's words:** *Position is captured at the moment the reading is saved — latitude, longitude and accuracy, automatically, never typed. Shown as one line, never as a field. It also measures the distance to where the meter is recorded, which catches a wrong meter before the office has to* — section J · What a reading actually carries · standing *New*.

**1 · Details** — As **the office**, I want **latitude, longitude and accuracy taken at save, never typed, and the distance to where the meter is recorded**, so that **a wrong meter shows before a bill does** (R90).

**Screens (build from the images — B14 rules 42, 44, 45):** `RW-13` The reading — [phone](../wireframes/reads/RW-13-the-reading.png) · [tablet](../wireframes/tablet/RW-13-T-the-reading.png)<br>`RW-09` Read entry — [phone](../wireframes/reads/RW-09-read-entry.png) · [tablet](../wireframes/tablet/RW-09-T-read-entry.png)

**2 · Business Rules**

| BR | R | Statement (first sentence, verbatim — the whole rule is in `02-business-rules.md`) | Status |
|---|---|---|---|
| `BR-FLD-00089` | R89 | Evidence never costs more than one tap. | DERIVED (decision log T-05) |
| `BR-FLD-00090` | R90 | Position is taken at save, automatically, with its accuracy, and is never a field anybody fills in. | DERIVED (decision log T-05) |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | RW-13 | *30.267153, −97.743061 · ±4 m · 3 m from where the meter is recorded* |
| TC-2 · **negative** | Look for a position field | None — one line, never a field (R89) |
| TC-3 · **tenant isolation** | Ray's route WLK-07 belongs to Silver Creek Water; a Lone Star Water route is downloaded for the same reader on the same handset | The two routes live in two database files; Silver Creek's walk never lists a Lone Star stop (R131), and the server reads the tenant from the credential (R127) |

**4 · Test Data** — ±4 m, 3 m from record.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| position | RW-13 | R90 | handset `route_read` lat, lng, accuracy, distance | degrees, m | system-derived | at save |

**6 · Acceptance** — **Given** a reading being saved, **when** the reader saves, **then** the position, its accuracy and the distance are stored.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---

---
id: US-FLD-064
epic: EP-FLD-12
module: field-app
screens: [RW-13, RW-09]
wave: 11
status: ready
blocked_by: []
depends_on: [US-FLD-063]
journeys: []           # the E2E-nn cases cited in §3 become journeys under 08-qa/01-e2e/journeys/ (sibling lane)
rules: [BR-FLD-00091]
golden_tests: []
finance_calc: none
---
### US-FLD-064 — A poor fix or no fix warns and still accepts

**Requirement 64, in the design's words:** *A poor fix or no fix warns and still accepts. A meter in a basement or a pit has no sky; refusing the reading there would refuse it exactly where it is hardest to get* — section J · What a reading actually carries · standing *New*.

**1 · Details** — As **Ray in a basement**, I want **the reading accepted without a fix**, so that **the hardest reads are not refused** (R91, `BR-WRK-061`).

**Screens (build from the images — B14 rules 42, 44, 45):** `RW-13` The reading — [phone](../wireframes/reads/RW-13-the-reading.png) · [tablet](../wireframes/tablet/RW-13-T-the-reading.png)<br>`RW-09` Read entry — [phone](../wireframes/reads/RW-09-read-entry.png) · [tablet](../wireframes/tablet/RW-09-T-read-entry.png)

**2 · Business Rules**

| BR | R | Statement (first sentence, verbatim — the whole rule is in `02-business-rules.md`) | Status |
|---|---|---|---|
| `BR-FLD-00091` | R91 | A poor fix or no fix warns and accepts. | DERIVED (decision log T-05) |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | No fix in a pit | Saved with a warning and no position |
| TC-2 | ±300 m | Saved; the accuracy is stored beside the point |
| TC-3 · **negative** | Refuse a reading for location | Never (R91) |
| TC-4 · **tenant isolation** | Ray's route WLK-07 belongs to Silver Creek Water; a Lone Star Water route is downloaded for the same reader on the same handset | The two routes live in two database files; Silver Creek's walk never lists a Lone Star stop (R131), and the server reads the tenant from the credential (R127) |

**4 · Test Data** — Basement meter, no sky.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| accuracy | RW-13 | R91 | `route_read.accuracy_m` | m | system-derived | warns, never refuses |

**6 · Acceptance** — **Given** no usable fix, **when** the reader saves, **then** the reading is accepted with a warning.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---

---
id: US-FLD-065
epic: EP-FLD-12
module: field-app
screens: [RW-13]
wave: 11
status: ready
blocked_by: []
depends_on: [US-FLD-063]
journeys: []           # the E2E-nn cases cited in §3 become journeys under 08-qa/01-e2e/journeys/ (sibling lane)
rules: [BR-FLD-00092, BR-FLD-00129]
golden_tests: []
finance_calc: none
---
### US-FLD-065 — Date and time stamped automatically, both clocks kept

**Requirement 65, in the design's words:** *Date and time are stamped automatically, and both clocks are kept — the phone's at capture and the server's on arrival — so a wrong device clock is visible instead of silently believed* — section J · What a reading actually carries · standing *New*.

**1 · Details** — As **a supervisor reviewing a disputed reading**, I want **the phone's time at capture and the server's on arrival**, so that **a wrong device clock is visible** (R92, R129).

**Screens (build from the images — B14 rules 42, 44, 45):** `RW-13` The reading — [phone](../wireframes/reads/RW-13-the-reading.png) · [tablet](../wireframes/tablet/RW-13-T-the-reading.png)

**2 · Business Rules**

| BR | R | Statement (first sentence, verbatim — the whole rule is in `02-business-rules.md`) | Status |
|---|---|---|---|
| `BR-FLD-00092` | R92 | Both clocks are recorded — the phone's at capture, the server's on arrival. | DERIVED (decision log T-05) |
| `BR-FLD-00129` | R129 | taken_at is not created_at, and conflating them lies about a disputed reading. | CONFIRMED — repo `BR-WRK-060` |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Shutter at 16:02 offline; arrives 17:40 | `taken_at` 16:02 and `received_at` 17:40 both stored (R129) |
| TC-2 · **negative** | A device clock an hour fast | Visible as a gap between the two clocks |
| TC-3 · **tenant isolation** | Ray's route WLK-07 belongs to Silver Creek Water; a Lone Star Water route is downloaded for the same reader on the same handset | The two routes live in two database files; Silver Creek's walk never lists a Lone Star stop (R131), and the server reads the tenant from the credential (R127) |

**4 · Test Data** — 20 Oct 2026, 10:42:18 phone clock.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| taken_at / received_at | RW-13 | R129 | `route_read.captured_at` + server arrival | timestamps | system-derived | never conflated |

**6 · Acceptance** — **Given** a reading sent later, **when** it arrives, **then** both times are kept.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---

---
id: US-FLD-066
epic: EP-FLD-12
module: field-app
screens: [RW-13, RW-09, RW-17]
wave: 11
status: ready
blocked_by: []
depends_on: [US-FLD-059]
journeys: []           # the E2E-nn cases cited in §3 become journeys under 08-qa/01-e2e/journeys/ (sibling lane)
rules: [BR-FLD-00096, BR-FLD-00089]
golden_tests: []
finance_calc: none
---
### US-FLD-066 — The reader's status comes from what they already did

**Requirement 66, in the design's words:** *The reader's status comes from what they already did. Typing a number is read; choosing a reason is could not read; accepting a warning is read with a problem. No separate status control exists* — section J · What a reading actually carries · standing *New*.

**1 · Details** — As **Ray**, I want **no separate status control**: typing a number is *read*, choosing a reason is *could not read*, accepting a warning is *read with a problem* (R96).

**Screens (build from the images — B14 rules 42, 44, 45):** `RW-13` The reading — [phone](../wireframes/reads/RW-13-the-reading.png) · [tablet](../wireframes/tablet/RW-13-T-the-reading.png)<br>`RW-09` Read entry — [phone](../wireframes/reads/RW-09-read-entry.png) · [tablet](../wireframes/tablet/RW-09-T-read-entry.png)<br>`RW-17` Can't read — [phone](../wireframes/reads/RW-17-can-t-read.png) · [tablet](../wireframes/tablet/RW-17-T-can-t-read.png)

**2 · Business Rules**

| BR | R | Statement (first sentence, verbatim — the whole rule is in `02-business-rules.md`) | Status |
|---|---|---|---|
| `BR-FLD-00096` | R96 | Two statuses, never merged. | DERIVED (decision log T-05) |
| `BR-FLD-00089` | R89 | Evidence never costs more than one tap. | DERIVED (decision log T-05) |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Type 52,410 and save | Status *Read* |
| TC-2 | Choose *Dog* | Status *Could not read* |
| TC-3 | Accept 71,400 anyway | Status *Read with a problem* |
| TC-4 · **negative** | A status picker | Does not exist; the engine's OK/high/low/zero/mismatch is separate (R96) |
| TC-5 · **tenant isolation** | Ray's route WLK-07 belongs to Silver Creek Water; a Lone Star Water route is downloaded for the same reader on the same handset | The two routes live in two database files; Silver Creek's walk never lists a Lone Star stop (R131), and the server reads the tenant from the credential (R127) |

**4 · Test Data** — RW-13 *Decided by the office · Not yet*.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| reader status | RW-13 | R96 | `route_read.reader_status` | enum | system-derived | derived from the act |

**6 · Acceptance** — **Given** a reader acting on a meter, **when** they read, refuse or accept, **then** the status is recorded from that act.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---

---
id: US-FLD-067
epic: EP-FLD-12
module: field-app
screens: [RW-14, RW-24]
wave: 11
status: ready
blocked_by: []
depends_on: [US-FLD-066]
journeys: []           # the E2E-nn cases cited in §3 become journeys under 08-qa/01-e2e/journeys/ (sibling lane)
rules: [BR-FLD-00093, BR-FLD-00094]
golden_tests: []
finance_calc: none
---
### US-FLD-067 — A photograph comes from the camera only, with the stamp burned in

**Requirement 67, in the design's words:** *A photograph comes from the camera and nowhere else. The gallery is never offered — a picture from the camera roll could be any meter on any day. Date, time, position with accuracy, reader, meter and route are burned into the pixels, not laid over them, so the stamp survives export, cropping and email* — section J · What a reading actually carries · standing *Engine built*.

**1 · Details** — As **the office**, I want **every reading photo from the camera with date, time, position, reader, meter and route in the pixels**, so that **it survives export, cropping and email** (R93, R94).

**Screens (build from the images — B14 rules 42, 44, 45):** `RW-14` The camera — [phone](../wireframes/reads/RW-14-the-camera.png) · [tablet](../wireframes/tablet/RW-14-T-the-camera.png)<br>`RW-24` Photos — [phone](../wireframes/reads/RW-24-photos.png) · [tablet](../wireframes/tablet/RW-24-T-photos.png)

**2 · Business Rules**

| BR | R | Statement (first sentence, verbatim — the whole rule is in `02-business-rules.md`) | Status |
|---|---|---|---|
| `BR-FLD-00093` | R93 | A photograph comes from the camera. | CONFIRMED (PO) |
| `BR-FLD-00094` | R94 | The stamp is burned into the pixels, never laid over them — date, time, position with accuracy, reader, meter, route. | CONFIRMED (PO) |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | RW-14 | *52410 · 20 Oct 2026 · 10:42:18 · 30.267153, −97.743061 · ±4 m · R. Delacroix · MTR-0471 · WLK-07* |
| TC-2 | RW-24 | 18 photos, 4 sent, 14 waiting for wi-fi, each stamped |
| TC-3 · **negative** | Gallery | Never offered (R93) |
| TC-4 · **tenant isolation** | Ray's route WLK-07 belongs to Silver Creek Water; a Lone Star Water route is downloaded for the same reader on the same handset | The two routes live in two database files; Silver Creek's walk never lists a Lone Star stop (R131), and the server reads the tenant from the credential (R127) |

**4 · Test Data** — 18 photos, 5 MB.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| stamp | RW-14 | R94 | photo pixels | text burned in | system-derived | not an overlay |

**6 · Acceptance** — **Given** a reading photo, **when** it is taken, **then** it comes from the camera with the stamp in its pixels.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---

---
id: US-FLD-068
epic: EP-FLD-12
module: field-app
screens: [RW-09, RW-13]
wave: 11
status: ready
blocked_by: []
depends_on: [US-FLD-066]
journeys: []           # the E2E-nn cases cited in §3 become journeys under 08-qa/01-e2e/journeys/ (sibling lane)
rules: [BR-FLD-00095]
golden_tests: []
finance_calc: none
---
### US-FLD-068 — A remark is spoken by default, typed as the fallback, never mandatory

**Requirement 68, in the design's words:** *A remark is spoken by default, typed as the fallback, and never mandatory. Readers push buttons; they do not type* — section J · What a reading actually carries · standing *New*.

**1 · Details** — As **Ray**, I want **to say the remark**, so that **I do not type** (R95).

**Screens (build from the images — B14 rules 42, 44, 45):** `RW-09` Read entry — [phone](../wireframes/reads/RW-09-read-entry.png) · [tablet](../wireframes/tablet/RW-09-T-read-entry.png)<br>`RW-13` The reading — [phone](../wireframes/reads/RW-13-the-reading.png) · [tablet](../wireframes/tablet/RW-13-T-the-reading.png)

**2 · Business Rules**

| BR | R | Statement (first sentence, verbatim — the whole rule is in `02-business-rules.md`) | Status |
|---|---|---|---|
| `BR-FLD-00095` | R95 | A remark is spoken by default, typed as the fallback, and never required. | DERIVED (decision log T-05) |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | *Remark* on RW-09 | *“Pit lid cracked, water pooling around it.”* · *Spoken, not typed* |
| TC-2 · **negative** | Save with no remark | Saved (R95) |
| TC-3 · **tenant isolation** | Ray's route WLK-07 belongs to Silver Creek Water; a Lone Star Water route is downloaded for the same reader on the same handset | The two routes live in two database files; Silver Creek's walk never lists a Lone Star stop (R131), and the server reads the tenant from the credential (R127) |

**4 · Test Data** — Remark on MTR-0471.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| remark | RW-09 | R95 | `route_read.remark` | text | user-input | optional |

**6 · Acceptance** — **Given** a reading, **when** the reader speaks a remark, **then** it is saved as text, and omitting it blocks nothing.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---

---
id: US-FLD-069
epic: EP-FLD-12
module: field-app
screens: [RW-09, RW-15, RW-17]
wave: 11
status: ready
blocked_by: []
depends_on: [US-FLD-067]
journeys: []           # the E2E-nn cases cited in §3 become journeys under 08-qa/01-e2e/journeys/ (sibling lane)
rules: [BR-FLD-00097, BR-FLD-00018]
golden_tests: []
finance_calc: none
---
### US-FLD-069 — The reading prompt decides when a photograph is required

**Requirement 69, in the design's words:** *The reading prompt decides when a photograph is required, the way a job step already does — so a utility that wants one on every read can have it and one that wants them only on exceptions can have that, with no code knowing the difference. An out-of-range reading or a could-not-read makes the photo button prominent on its own* — section J · What a reading actually carries · standing *New*.

**1 · Details** — As **a utility**, I want **the prompt to say whether a photo is required**, so that **no code knows which readings need one** (R97). Out of range or could-not-read makes the photo button prominent on its own.

**Screens (build from the images — B14 rules 42, 44, 45):** `RW-09` Read entry — [phone](../wireframes/reads/RW-09-read-entry.png) · [tablet](../wireframes/tablet/RW-09-T-read-entry.png)<br>`RW-15` High or low — [phone](../wireframes/reads/RW-15-high-or-low.png) · [tablet](../wireframes/tablet/RW-15-T-high-or-low.png)<br>`RW-17` Can't read — [phone](../wireframes/reads/RW-17-can-t-read.png) · [tablet](../wireframes/tablet/RW-17-T-can-t-read.png)

**2 · Business Rules**

| BR | R | Statement (first sentence, verbatim — the whole rule is in `02-business-rules.md`) | Status |
|---|---|---|---|
| `BR-FLD-00097` | R97 | The reading prompt decides when a photograph is required, exactly as a job step does. | DERIVED (decision log T-05) |
| `BR-FLD-00018` | R18 | Freshness sits on the template step, the same way photo required and must do already do. | DERIVED (decision log T-05) |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | A prompt with photo required | Save waits for a photo |
| TC-2 | Out-of-range reading on a prompt without | The *Photo* button turns red of its own accord |
| TC-3 · **negative** | A code branch on meter type for photos | Not allowed (R97) |
| TC-4 · **tenant isolation** | Ray's route WLK-07 belongs to Silver Creek Water; a Lone Star Water route is downloaded for the same reader on the same handset | The two routes live in two database files; Silver Creek's walk never lists a Lone Star stop (R131), and the server reads the tenant from the credential (R127) |

**4 · Test Data** — 300 MB a day if every one of 1,000 readings had a photo (design figure).

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| photo_required | RW-09 | R97 | reading prompt (template) → `route_read` | bool | reference-data | the prompt decides |

**6 · Acceptance** — **Given** a prompt, **when** the reader saves, **then** a photo is required only if the prompt says so.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.
