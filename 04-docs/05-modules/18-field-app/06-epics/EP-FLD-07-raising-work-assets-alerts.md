# EP-FLD-07 — Raising work, assets and alerts

**Module:** field-app (`18-field-app`, module code FLD) · **Wave:** 8 · **Design tasks:** T-22, T-23 · **Screens:** FF-38, FF-39, FF-37, RW-21, FF-42, FF-43, FF-52, FF-07, FF-40, FF-41, RW-08, RW-11, FF-62 · **Status:** draft (2026-10-21, `CR-187-BRC10`)

## Scope

**In:** the design's flow group *FF-37 to FF-43, FF-62* and the requirements whose screens sit in it — US-FLD-010 (requirement 10), US-FLD-011 (requirement 11), US-FLD-013 (requirement 13), US-FLD-019 (requirement 19), US-FLD-038 (requirement 38), US-FLD-039 (requirement 39), US-FLD-076 (requirement 76), US-FLD-084 (requirement 84).

**Out:** everything the design's *Scope · Out* list excludes (`01-overview.md` §5) — taking payment on site, linear assets, inspection rounds, offline maps, a dispatcher app, live crew tracking, van stock-takes, customer-facing features, a watch app.

**Source:** the *SMART360 Next Field App* design canvas, version of 2026-10-21. The screens are the images in `../wireframes/` and they are the specification (B14 rule 42; PO 2026-10-21, *"please ensure all native app screens are build using images not using text or contents"*). Figures on a board are illustrations (B14 rule 37) and are used below as test data only.

## Capability matrix (list screens only — B9 conformance)

| Screen | Search fields | Filters | Default sort | Sortable | Columns default/available | Row actions | Bulk actions | Export |
|---|---|---|---|---|---|---|---|---|
| FF-41 Asset search | serial · badge · device ID · address · account number | — | not declared | not declared | row: serial, address, model | open | — | — |
| FF-42 Alerts | — | — | newest first (as drawn) | — | row: kind, title, place, time | Mark read | — | — |
| FF-62 Pick a template | template name | — | recently used first (R112) | — | row: name, version, service, counts | Use it | — | — |

*Not declared* means the design does not say; requirement 37 and R44 require it declared and wired before the screen ships — the build lane declares it, it is not guessed here.

## Stories

---
id: US-FLD-010
epic: EP-FLD-07
module: field-app
screens: [FF-38, FF-39]
wave: 8
status: ready
blocked_by: []
depends_on: [US-FLD-038]
journeys: []           # the E2E-nn cases cited in §3 become journeys under 08-qa/01-e2e/journeys/ (sibling lane)
rules: [BR-FLD-00015, BR-FLD-00043]
golden_tests: []
finance_calc: none
---
### US-FLD-010 — Asset data and scanning — verify the meter against the record

**Requirement 10, in the design's words:** *Asset data and scanning — meter serial, device ID, badge, model. Camera scanning of 1D barcodes and 2D QR to verify equipment against records* — section A · The original brief · standing *Scan is new*.

**1 · Details** — As **Dana at the pit**, I want **to scan W-4471 and see it matches this job**, so that **I work on the right meter**. FF-39 shows serial, badge, device ID, size, where, sub-meters and last read. Assets are meters and sub-meters for now (R15).

**Screens (build from the images — B14 rules 42, 44, 45):** `FF-38` Scan — [phone](../wireframes/phone/FF-38-scan.png) · [tablet](../wireframes/tablet/FF-38-T-scan.png)<br>`FF-39` Asset — [phone](../wireframes/phone/FF-39-asset.png) · [tablet](../wireframes/tablet/FF-39-T-asset.png)

**2 · Business Rules**

| BR | R | Statement (first sentence, verbatim — the whole rule is in `02-business-rules.md`) | Status |
|---|---|---|---|
| `BR-FLD-00015` | R15 | Assets are meters and sub-meters only, for now. | CONFIRMED (PO) |
| `BR-FLD-00043` | R43 | A scanned code is matched serial, then badge, then device ID — one order, everywhere, so the same sticker always finds the same asset | DERIVED (decision log T-05) |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Scan W-4471 on WO-4822 | *Matches this job*; *Open asset* |
| TC-2 | FF-39 W-4471 | Serial W-4471 · Badge 88-2041 · Device ID E1P-77412 · 5/8" · Neptune T-10 · since 14 Mar 2019 · 2 sub-meters · last read 48,180 gal 12 Jun 2026 R. Patel |
| TC-3 · **negative** | Scan a meter not on this job | Says it does not match; nothing is changed |
| TC-4 | Damaged label | *Enter manually* |
| TC-5 · **tenant isolation** | R. Patel works for Silver Creek Water and Lone Star Water and signs in to Lone Star Water on the same handset | Only `field-lone-star-water.sqlite` is opened; not one Silver Creek row is readable (R131), and the server takes the tenant from the credential, never from the payload (R127) |

**4 · Test Data** — W-4471 · 88-2041 · E1P-77412 · W-4471-A 12,210 gal · W-4471-B 9,044 gal.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| serial / badge / device ID | FF-39 | requirement 10 | handset `asset` (mirror) | text | reference-data | matched in that order (R43) |

**6 · Acceptance** — **Given** a job with an asset, **when** the technician scans it, **then** the app says whether it matches and opens the asset.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---

---
id: US-FLD-011
epic: EP-FLD-07
module: field-app
screens: [FF-37, RW-21]
wave: 8
status: ready
blocked_by: []
depends_on: [US-FLD-076]
journeys: []           # the E2E-nn cases cited in §3 become journeys under 08-qa/01-e2e/journeys/ (sibling lane)
rules: [BR-FLD-00023, BR-FLD-00024, BR-FLD-00112, BR-FLD-00036]
golden_tests: []
finance_calc: none
---
### US-FLD-011 — Field-raised orders — auto-filled with premise, account, customer and position

**Requirement 11, in the design's words:** *Field-raised orders — new work orders from site for emergencies, leaks, damaged meters, broken seals and hazards, auto-filled with premise, account, customer and GPS* — section A · The original brief · standing *New on phone*.

**1 · Details** — As **Dana finding a leaking service at the kerb**, I want **to raise an order on the spot with everything filled in**, so that **the office is never surprised by it**. No number until it syncs (R24); a reader raises work from the route on RW-21. ⚠ **AMENDED 2026-10-31 (FB-028, PO W1/W2/W3 and the field-raised-disconnects ruling): this read *"a reconnect lands pending (R23)"*.** R23 is SUPERSEDED: the raised order is assigned to the raiser at once, every template; Send goes to the server immediately when there is signal (otherwise it queues — W2 = B, no provisional job) and the job appears on Today, numbered, once the server has it; the screen offers *Send now* and *Open job*. A raised reconnect's step is gated by the template's *Reconnect limit*; a raised disconnect's step stops on cleared / notice / protected.

**Screens (build from the images — B14 rules 42, 44, 45):** `FF-37` Raise — [phone](../wireframes/phone/FF-37-raise.png) · [tablet](../wireframes/tablet/FF-37-T-raise-an-order.png)<br>`RW-21` Raise it — [phone](../wireframes/reads/RW-21-raise-it.png) · [tablet](../wireframes/tablet/RW-21-T-raise-it.png)

**2 · Business Rules**

| BR | R | Statement (first sentence, verbatim — the whole rule is in `02-business-rules.md`) | Status |
|---|---|---|---|
| `BR-FLD-00023` | R23 | ~~A field-raised reconnect needs office approval.~~ | **SUPERSEDED 2026-10-31 (PO, FB-028)** — assigned to the raiser; the step is gated |
| `BR-FLD-00024` | R24 | A field-raised order gets no number until it syncs. | CONFIRMED (PO) |
| `BR-FLD-00112` | R112 | Raising an order starts with a template, and every published template is offered — recently used first, search behind it. | CONFIRMED (PO) |
| `BR-FLD-00036` | R36 | An address is stored on premises and derived everywhere else. | CONFIRMED — repo `BR-MET-1161` |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | E2E-16: raise *Leak* at 22 Cedar Court with a photo | Premise, account A-10588, customer, meter W-6120 and *30.2612, -97.7431 · ±4m* are filled in; with signal it is sent at once, ASSIGNED to Dana and on her Today, numbered (FB-028); the office's *Raised on site* lists it for review |
| TC-2 | Before sync | *Number arrives when this sends* — never a number the server might not honour (R24) |
| TC-3 | RW-21 on route WLK-07: *Leak*, photo, urgency *This week* | Filled in with 1318 Maple · Unit A · ACC-10294 · MTR-0471; *Carry on reading* |
| TC-4 | A raised reconnect (FB-028, R23 superseded) | Assigned to the raiser with no office wait; Reconnect enabled at $18.40 against a $25.00 limit; *Still owes $804.50. Leave it off.* and the office told above it; *Check the balance with signal.* on a stale figure |
| TC-4b · **negative** | Raised with no signal (W2 = B) | Queued only — no provisional job; *Send now* shown, *Open job* waits |
| TC-5 · **tenant isolation** | R. Patel works for Silver Creek Water and Lone Star Water and signs in to Lone Star Water on the same handset | Only `field-lone-star-water.sqlite` is opened; not one Silver Creek row is readable (R131), and the server takes the tenant from the credential, never from the payload (R127) |

**4 · Test Data** — Template *Leak investigation* v3 · urgency Normal · Same day · Emergency.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| raised order | FF-37 | requirement 11 | outbox `raise` → server field-raised queue | order draft | user-input | number at sync |

**6 · Acceptance** — **Given** a technician on site, **when** they raise an order, **then** it is sent at once with signal, assigned to them, and on their Today numbered; the office sees it filled in on *Raised on site* for review (FB-028, 2026-10-31).

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---

---
id: US-FLD-013
epic: EP-FLD-07
module: field-app
screens: [FF-42, FF-43, FF-52, FF-07]
wave: 8
status: ready
blocked_by: []
depends_on: [US-FLD-033]
journeys: []           # the E2E-nn cases cited in §3 become journeys under 08-qa/01-e2e/journeys/ (sibling lane)
rules: [BR-FLD-00028, BR-FLD-00029, BR-FLD-00019]
golden_tests: []
finance_calc: none
---
### US-FLD-013 — Push and emergency alerts — distinct sound and vibration, on a locked device

**Requirement 13, in the design's words:** *Push and emergency alerts — distinct audio and vibration for urgent assignments, emergencies and schedule changes, on a locked device. In-app badges for dispatch messages* — section A · The original brief · standing *Unblocked*.

**1 · Details** — As **Dana with the phone locked and on silent**, I want **an emergency to sound and vibrate distinctly**, so that **I never miss one**. An emergency must be acknowledged; no acknowledgement in 5 minutes and dispatch is told (R28). Dispatch messages only, no crew chat (R29). Breaking silent mode on iPhone needs Apple's Critical Alerts entitlement — applied for (T-01) and not yet granted, so E2E-22 cannot pass until it is.

**Screens (build from the images — B14 rules 42, 44, 45):** `FF-42` Alerts — [phone](../wireframes/phone/FF-42-alerts.png) · [tablet](../wireframes/tablet/FF-42-T-alerts.png)<br>`FF-43` Emergency — [phone](../wireframes/phone/FF-43-emergency.png) · [tablet](../wireframes/tablet/FF-43-T-emergency.png)<br>`FF-52` Notifications — [phone](../wireframes/phone/FF-52-notifications.png) · [tablet](../wireframes/tablet/FF-52-T-notifications.png)<br>`FF-07` Permissions — [phone](../wireframes/phone/FF-07-permissions.png) · [tablet](../wireframes/tablet/FF-07-T-permissions.png)

**2 · Business Rules**

| BR | R | Statement (first sentence, verbatim — the whole rule is in `02-business-rules.md`) | Status |
|---|---|---|---|
| `BR-FLD-00028` | R28 | An emergency must be acknowledged. | CONFIRMED (PO) |
| `BR-FLD-00029` | R29 | Dispatch messages only. | CONFIRMED (PO) |
| `BR-FLD-00019` | R19 | The server pushes the moment money changes. | CONFIRMED (PO) |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | FF-43 Gas leak reported 14 Oak Street, WO-4850 | *Dispatch is told in 4:12*; *Acknowledge* · *Call dispatch* · *Cannot attend* |
| TC-2 · **negative** | No acknowledgement in 5 minutes | Dispatch is told (R28) |
| TC-3 | E2E-22: handset locked and on silent | The alert breaks silent mode — passes only once Apple grants the entitlement |
| TC-4 | FF-42 Alerts | Emergency not acknowledged · *Job cancelled* · *Aaron Bruner has paid* · *WO-4831 moved to 14:00* · a dispatch message |
| TC-5 · **negative** | Look for a crew-to-crew chat | None (R29) |
| TC-6 · **tenant isolation** | R. Patel works for Silver Creek Water and Lone Star Water and signs in to Lone Star Water on the same handset | Only `field-lone-star-water.sqlite` is opened; not one Silver Creek row is readable (R131), and the server takes the tenant from the credential, never from the payload (R127) |

**4 · Test Data** — Emergency WO-4850 14 Oak Street 10:06 · 1.8 miles · 7 min.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| alert kind | FF-42/52 | requirement 13 | push kinds: urgent assignment · emergency · schedule change · dispatch message | enum | integration | own sound and channel each |
| acknowledged at | FF-43 | R28 | outbox `ack` | timestamp | user-input | 5-minute clock |

**6 · Acceptance** — **Given** an emergency dispatched to a locked phone, **when** it arrives, **then** it sounds distinctly, and if not acknowledged in 5 minutes dispatch is told.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---

---
id: US-FLD-019
epic: EP-FLD-07
module: field-app
screens: [FF-40]
wave: 8
status: ready
blocked_by: []
depends_on: [US-FLD-010]
journeys: []           # the E2E-nn cases cited in §3 become journeys under 08-qa/01-e2e/journeys/ (sibling lane)
rules: [BR-FLD-00015]
golden_tests: []
finance_calc: none
---
### US-FLD-019 — Asset service history on site

**Requirement 19, in the design's words:** *Asset service history on site — work type, problem, solution, parts replaced, technician* — section C · From the reference apps, confirmed into scope · standing *New*.

**1 · Details** — As **Dana at W-4471**, I want **who touched this meter, what they found and what they replaced**, so that **I start from what is known**. Cached on the phone.

**Screens (build from the images — B14 rules 42, 44, 45):** `FF-40` Asset history — [phone](../wireframes/phone/FF-40-asset-history.png) · [tablet](../wireframes/tablet/FF-40-T-asset-history.png)

**2 · Business Rules**

| BR | R | Statement (first sentence, verbatim — the whole rule is in `02-business-rules.md`) | Status |
|---|---|---|---|
| `BR-FLD-00015` | R15 | Assets are meters and sub-meters only, for now. | CONFIRMED (PO) |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | FF-40 W-4471 | 4 visits: 12 Jun 2026 Routine read (R. Patel) · 03 Feb 2026 Seal check, Partly done, wire seal (D. Ortiz) · 21 Sep 2025 Leak investigation (M. Chen) |
| TC-2 | Offline | History opens from the cache |
| TC-3 · **negative** | History rows queried across assets | Never — history is a JSON blob rendered whole (R116) |
| TC-4 · **tenant isolation** | R. Patel works for Silver Creek Water and Lone Star Water and signs in to Lone Star Water on the same handset | Only `field-lone-star-water.sqlite` is opened; not one Silver Creek row is readable (R131), and the server takes the tenant from the credential, never from the payload (R127) |

**4 · Test Data** — W-4471 · 4 visits cached.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| history | FF-40 | requirement 19 | handset `asset.history` JSON | list | integration | displayed only |

**6 · Acceptance** — **Given** an asset with past visits, **when** the technician opens its history, **then** each visit's work type, problem, solution, parts and technician show offline.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---

---
id: US-FLD-038
epic: EP-FLD-07
module: field-app
screens: [FF-38, FF-41, RW-08, RW-11]
wave: 8
status: ready
blocked_by: []
depends_on: [US-FLD-084]
journeys: []           # the E2E-nn cases cited in §3 become journeys under 08-qa/01-e2e/journeys/ (sibling lane)
rules: [BR-FLD-00043, BR-FLD-00083]
golden_tests: []
finance_calc: none
---
### US-FLD-038 — Scanning is the first-class way to find an asset; typing is the fallback

**Requirement 38, in the design's words:** *Scanning is the first-class way to find an asset, typing the fallback. A scanned code matches serial, then badge, then device ID* — section G · Search, large volumes, refresh and the handset's data · standing *New*.

**1 · Details** — As **Dana or Ray**, I want **to scan rather than type**, so that **the same sticker always finds the same asset**. A scanned code matches serial, then badge, then device ID — one order everywhere (R43, R83).

**Screens (build from the images — B14 rules 42, 44, 45):** `FF-38` Scan — [phone](../wireframes/phone/FF-38-scan.png) · [tablet](../wireframes/tablet/FF-38-T-scan.png)<br>`FF-41` Asset search — [phone](../wireframes/phone/FF-41-asset-search.png) · [tablet](../wireframes/tablet/FF-41-T-asset-search.png)<br>`RW-08` Find a meter — [phone](../wireframes/reads/RW-08-find-a-meter.png) · [tablet](../wireframes/tablet/RW-08-T-find-a-meter.png)<br>`RW-11` Scan to confirm — [phone](../wireframes/reads/RW-11-scan-to-confirm.png) · [tablet](../wireframes/tablet/RW-11-T-scan-to-confirm.png)

**2 · Business Rules**

| BR | R | Statement (first sentence, verbatim — the whole rule is in `02-business-rules.md`) | Status |
|---|---|---|---|
| `BR-FLD-00043` | R43 | A scanned code is matched serial, then badge, then device ID — one order, everywhere, so the same sticker always finds the same asset | DERIVED (decision log T-05) |
| `BR-FLD-00083` | R83 | A scanned code decides the meter — matched serial, then badge, then device ID. | DERIVED (decision log T-05) |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Scan badge 88241 on RW-11 | *88241 matches. Unit A, Carla Ruiz.* |
| TC-2 | A code equal to one asset's serial and another's badge | The serial match wins (R43) |
| TC-3 | RW-08 type *882* | MTR-0471, MTR-0472, MTR-0519 on this phone |
| TC-4 · **negative** | Scan finds nothing | Offers typing, and on a route the add-a-meter path (requirement 61) |
| TC-5 · **tenant isolation** | R. Patel works for Silver Creek Water and Lone Star Water and signs in to Lone Star Water on the same handset | Only `field-lone-star-water.sqlite` is opened; not one Silver Creek row is readable (R131), and the server takes the tenant from the credential, never from the payload (R127) |

**4 · Test Data** — MTR-0471 badge 88241 · MTR-0472 badge 88242 · MTR-0519 badge 88293.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| scanned code | FF-38, RW-11 | R43 | handset `asset` (serial, badge, device_id) | text | user-input | serial → badge → device ID |

**6 · Acceptance** — **Given** a meter with a readable label, **when** the technician scans it, **then** the asset is found by the one matching order.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---

---
id: US-FLD-039
epic: EP-FLD-07
module: field-app
screens: [FF-41, RW-08]
wave: 8
status: ready
blocked_by: []
depends_on: [US-FLD-037]
journeys: []           # the E2E-nn cases cited in §3 become journeys under 08-qa/01-e2e/journeys/ (sibling lane)
rules: [BR-FLD-00041, BR-FLD-00042]
golden_tests: []
finance_calc: none
---
### US-FLD-039 — A search that cannot see everything says so

**Requirement 39, in the design's words:** *A search that cannot see everything says so. Offline, asset search states that only the day's assets are on the handset and that a signal searches the whole utility. A silent subset is worse than a refusal — the technician concludes the meter does not exist* — section G · Search, large volumes, refresh and the handset's data · standing *New*.

**1 · Details** — As **Dana offline**, I want **to be told only today's assets are on the handset**, so that **I do not conclude a meter does not exist**. A silent subset is worse than a refusal (R42).

**Screens (build from the images — B14 rules 42, 44, 45):** `FF-41` Asset search — [phone](../wireframes/phone/FF-41-asset-search.png) · [tablet](../wireframes/tablet/FF-41-T-asset-search.png)<br>`RW-08` Find a meter — [phone](../wireframes/reads/RW-08-find-a-meter.png) · [tablet](../wireframes/tablet/RW-08-T-find-a-meter.png)

**2 · Business Rules**

| BR | R | Statement (first sentence, verbatim — the whole rule is in `02-business-rules.md`) | Status |
|---|---|---|---|
| `BR-FLD-00041` | R41 | Search is local first, server on request. | DERIVED (decision log T-05) |
| `BR-FLD-00042` | R42 | A search that cannot see everything says so, in the result area. | DERIVED (decision log T-05) |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | FF-41 offline | *3 on this phone · Only today's assets are here. A signal searches the whole utility.* |
| TC-2 | RW-08 offline | *Only this route is on the phone. A signal searches the whole utility.* with *Search everything* |
| TC-3 | *Search everything* with a signal | The server answers, paged, with no cap (R41) |
| TC-4 · **negative** | An offline search with no match and no sentence | Not acceptable — the result area must say what it cannot see (R42) |
| TC-5 · **tenant isolation** | R. Patel works for Silver Creek Water and Lone Star Water and signs in to Lone Star Water on the same handset | Only `field-lone-star-water.sqlite` is opened; not one Silver Creek row is readable (R131), and the server takes the tenant from the credential, never from the payload (R127) |

**4 · Test Data** — W-4471, W-4471-A, W-4471-B on the phone.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| scope sentence | FF-41, RW-08 | R42 | computed from where the answer came from | text | computed-display | always shown offline |

**6 · Acceptance** — **Given** a search over a partial local store, **when** it returns, **then** it states that it is partial and how to search everything.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---

---
id: US-FLD-076
epic: EP-FLD-07
module: field-app
screens: [FF-62, FF-37]
wave: 8
status: ready
blocked_by: []
depends_on: [US-FLD-011]
journeys: []           # the E2E-nn cases cited in §3 become journeys under 08-qa/01-e2e/journeys/ (sibling lane)
rules: [BR-FLD-00112]
golden_tests: []
finance_calc: none
---
### US-FLD-076 — Raising a work order starts by picking a template

**Requirement 76, in the design's words:** *Raising a work order starts by picking a template, because the template is what carries the steps, safety checks, materials and readings. Every published template the back office made, recently-used first, with search. The order takes its own copy and stamps the version* — section K · The seven asks of 2026-10-20 · standing *Ruled*.

**1 · Details** — As **Dana**, I want **every published template, recently used first, with search**, so that **picking the template is picking the work**. The order takes its own copy and stamps the version (R112).

**Screens (build from the images — B14 rules 42, 44, 45):** `FF-62` Pick a template — [phone](../wireframes/phone/FF-62-pick-a-template.png) · [tablet](../wireframes/tablet/FF-62-T-pick-a-template.png)<br>`FF-37` Raise — [phone](../wireframes/phone/FF-37-raise.png) · [tablet](../wireframes/tablet/FF-37-T-raise-an-order.png)

**2 · Business Rules**

| BR | R | Statement (first sentence, verbatim — the whole rule is in `02-business-rules.md`) | Status |
|---|---|---|---|
| `BR-FLD-00112` | R112 | Raising an order starts with a template, and every published template is offered — recently used first, search behind it. | CONFIRMED (PO) |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | FF-62 | *Search 34 templates*; recently used *Leak investigation v3* (used 2 days ago) and *Meter replacement v7*; then all 34 |
| TC-2 | Pick *Leak investigation v3* | FF-37 shows *4 steps · 3 safety checks · 1 reading* |
| TC-3 · **negative** | The template is edited to v4 after raising | The raised order keeps v3 (R112) |
| TC-4 · **negative** | A draft template | Not offered — published only |
| TC-5 · **tenant isolation** | R. Patel works for Silver Creek Water and Lone Star Water and signs in to Lone Star Water on the same handset | Only `field-lone-star-water.sqlite` is opened; not one Silver Creek row is readable (R131), and the server takes the tenant from the credential, never from the payload (R127) |

**4 · Test Data** — 34 published templates; Broken seal v2; Suspected tamper v4; Service connection v5; Routine inspection v2; Re-read v1.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| template + version | FF-62 | requirement 76 | handset `template` (catalogue) → outbox `raise` | ref + int | reference-data | published only |

**6 · Acceptance** — **Given** a technician raising work, **when** they pick a template, **then** the order takes its own copy of that version.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---

---
id: US-FLD-084
epic: EP-FLD-07
module: field-app
screens: [FF-38, RW-11]
wave: 8
status: ready
blocked_by: []
depends_on: [US-FLD-038]
journeys: []           # the E2E-nn cases cited in §3 become journeys under 08-qa/01-e2e/journeys/ (sibling lane)
rules: [BR-FLD-00043, BR-FLD-00083]
golden_tests: []
finance_calc: none
---
### US-FLD-084 — Barcode, QR and Data Matrix — local first, torch, continuous mode, manual entry

**Requirement 84, in the design's words:** *Barcode and QR, including Data Matrix — which is what fits on a meter plate. Resolved locally first, torch because meters live in pits, continuous mode because 151 meters is 151 camera launches otherwise, and manual entry when the label is damaged* — section L · The nine of 2026-10-21 · standing *New*.

**1 · Details** — As **Ray on a 151-meter route**, I want **the camera to stay open and read 1D, QR and Data Matrix, with a torch**, so that **151 meters are not 151 camera launches**. Resolved locally first; manual entry when the label is damaged.

**Screens (build from the images — B14 rules 42, 44, 45):** `FF-38` Scan — [phone](../wireframes/phone/FF-38-scan.png) · [tablet](../wireframes/tablet/FF-38-T-scan.png)<br>`RW-11` Scan to confirm — [phone](../wireframes/reads/RW-11-scan-to-confirm.png) · [tablet](../wireframes/tablet/RW-11-T-scan-to-confirm.png)

**2 · Business Rules**

| BR | R | Statement (first sentence, verbatim — the whole rule is in `02-business-rules.md`) | Status |
|---|---|---|---|
| `BR-FLD-00043` | R43 | A scanned code is matched serial, then badge, then device ID — one order, everywhere, so the same sticker always finds the same asset | DERIVED (decision log T-05) |
| `BR-FLD-00083` | R83 | A scanned code decides the meter — matched serial, then badge, then device ID. | DERIVED (decision log T-05) |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Continuous mode on route WLK-07 | Scan, read, scan, read — the camera stays open |
| TC-2 | A Data Matrix on a meter plate | Read and matched serial → badge → device ID (R43) |
| TC-3 | A pit with no light | The torch is one tap |
| TC-4 · **negative** | Damaged label | *Type it* / *Enter manually* |
| TC-5 · **tenant isolation** | R. Patel works for Silver Creek Water and Lone Star Water and signs in to Lone Star Water on the same handset | Only `field-lone-star-water.sqlite` is opened; not one Silver Creek row is readable (R131), and the server takes the tenant from the credential, never from the payload (R127) |

**4 · Test Data** — Route WLK-07, 151 meters.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| symbology | FF-38, RW-11 | requirement 84 | scanner result | 1D · QR · Data Matrix | integration | resolved locally first |

**6 · Acceptance** — **Given** a route of meters with labels, **when** the reader scans in continuous mode, **then** each label resolves locally without relaunching the camera.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.
