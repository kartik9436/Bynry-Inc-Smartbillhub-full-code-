# EP-FLD-09 — Kit, sync, settings and themes — and the engine underneath every screen

**Module:** field-app (`18-field-app`, module code FLD) · **Wave:** 0, 1, 10 · **Design tasks:** T-25, T-26, T-10, T-11, T-73–T-76 · **Screens:** FF-09, FF-54, FF-55, FF-50, FF-51, FF-52, RW-29, FF-06, FF-18, FF-01, RW-26, RW-27, FF-08, FF-21, FF-53, FF-35 · **Status:** draft (2026-10-21, `CR-187-BRC10`)

## Scope

**In:** the design's flow group *FF-49 to FF-55* and the requirements whose screens sit in it — US-FLD-001 (requirement 1), US-FLD-004 (requirement 4), US-FLD-033 (requirement 33), US-FLD-034 (requirement 34), US-FLD-035 (requirement 35), US-FLD-036 (requirement 36), US-FLD-041 (requirement 41), US-FLD-042 (requirement 42), US-FLD-044 (requirement 44), US-FLD-046 (requirement 46), US-FLD-047 (requirement 47), US-FLD-048 (requirement 48), US-FLD-049 (requirement 49), US-FLD-050 (requirement 50), US-FLD-051 (requirement 51), US-FLD-052 (requirement 52), US-FLD-079 (requirement 79), US-FLD-081 (requirement 81), US-FLD-082 (requirement 82), US-FLD-083 (requirement 83).

**Out:** everything the design's *Scope · Out* list excludes (`01-overview.md` §5) — taking payment on site, linear assets, inspection rounds, offline maps, a dispatcher app, live crew tracking, van stock-takes, customer-facing features, a watch app.

**Source:** the *SMART360 Next Field App* design canvas, version of 2026-10-21. The screens are the images in `../wireframes/` and they are the specification (B14 rule 42; PO 2026-10-21, *"please ensure all native app screens are build using images not using text or contents"*). Figures on a board are illustrations (B14 rule 37) and are used below as test data only.

⚠ **2 of these stories are `blocked`** — US-FLD-042, US-FLD-047 — each on a collision between the design and a rule already signed in this repository, named in plain words in its §8. The open-questions lane (DOC-C) mints the `OQ-FLD-` id; until then `blocked_by` is empty and the gap is the comment beside it.

## Capability matrix (list screens only — B9 conformance)

No list screen in this group.

## Stories

---
id: US-FLD-001
epic: EP-FLD-09
module: field-app
screens: [FF-09, FF-54, FF-55]
wave: 0
status: ready
blocked_by: []
depends_on: []
journeys: []           # the E2E-nn cases cited in §3 become journeys under 08-qa/01-e2e/journeys/ (sibling lane)
rules: [BR-FLD-00121, BR-FLD-00122, BR-FLD-00102]
golden_tests: []
finance_calc: none
---
### US-FLD-001 — Phones and tablets — one native app, four tablet frames

**Requirement 1, in the design's words:** *Mobile and tablet — responsive for phones and tablets. Originally an installable PWA; superseded — see Decisions.* — section A · The original brief · standing *Changed*.

**1 · Details** — As **a utility issuing phones and tablets**, I want **one native app on both**, so that **a technician has the same app on either**. Originally a PWA; superseded by `CR-187-BRC10` (`BR-WRK-045` SUPERSEDED). On a tablet the drawer becomes a 220 px permanent sidebar; four frames do all screens; a pane is designed to its measured width (R121, R122).

**Screens (build from the images — B14 rules 42, 44, 45):** `FF-09` Menu — [phone](../wireframes/phone/FF-09-menu.png) · [tablet](../wireframes/tablet/FF-09-T-the-sidebar.png)<br>`FF-54` Dark theme — [phone](../wireframes/phone/FF-54-dark-theme.png) · [tablet](../wireframes/tablet/FF-54-T-dark.png)<br>`FF-55` Sunlight theme — [phone](../wireframes/phone/FF-55-sunlight-theme.png) · [tablet](../wireframes/tablet/FF-55-T-sunlight.png)

**2 · Business Rules**

| BR | R | Statement (first sentence, verbatim — the whole rule is in `02-business-rules.md`) | Status |
|---|---|---|---|
| `BR-FLD-00121` | R121 | A pane has a measured width, and content is designed to that number — not to the screen's. | DERIVED (decision log T-05) |
| `BR-FLD-00122` | R122 | Every frame states its usable width, and a check measures against it. | DERIVED (decision log T-05) |
| `BR-FLD-00102` | R102 | Reads is reached from the bottom bar, not from a menu. | CONFIRMED (PO) |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | FF-09 on a phone | The drawer: Work · Reads · Me · Sync · Version · Switch technician · Sign out |
| TC-2 | FF-09-T on a 1024 tablet | A permanent 220 px sidebar marks the current screen |
| TC-3 · **negative** | Sidebar + context + content with two columns of content | A check fails it: 464 px cannot hold two columns (R121, R122) |
| TC-4 · **negative** | A fixed child leaves its flexible sibling under 260 px | The width check fails it (R122) |
| TC-5 · **tenant isolation** | R. Patel works for Silver Creek Water and Lone Star Water and signs in to Lone Star Water on the same handset | Only `field-lone-star-water.sqlite` is opened; not one Silver Creek row is readable (R131), and the server takes the tenant from the credential, never from the payload (R127) |

**4 · Test Data** — Frames: sidebar + one pane 764 px · sidebar + context + content 464 px · sidebar + list + detail 424 px.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| frame width | all tablet boards | R122 | layout constants | px | computed-display | measured by a script |

**6 · Acceptance** — **Given** a phone and a 1024 tablet, **when** the same screen opens on each, **then** the phone shows it with a drawer and the tablet in its declared frame.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---

---
id: US-FLD-004
epic: EP-FLD-09
module: field-app
screens: [FF-50]
wave: 0
status: ready
blocked_by: []
depends_on: []
journeys: []           # the E2E-nn cases cited in §3 become journeys under 08-qa/01-e2e/journeys/ (sibling lane)
rules: [BR-FLD-00045, BR-FLD-00046, BR-FLD-00047, BR-FLD-00051, BR-FLD-00123]
golden_tests: []
finance_calc: none
---
### US-FLD-004 — Two-phase sync — data first, then photographs, compressed, with local receipts

**Requirement 4, in the design's words:** *Two-phase sync — data records first, photos after in the background. Image compression. Local receipts so nothing is lost* — section A · The original brief · standing *Engine built*.

**1 · Details** — As **Dana**, I want **my data to land first and photos to follow in the background**, so that **nothing is lost and the office sees the job quickly**. A photograph is declared with the data and its bytes follow (R123).

**Screens (build from the images — B14 rules 42, 44, 45):** `FF-50` Sync — [phone](../wireframes/phone/FF-50-sync.png) · [tablet](../wireframes/tablet/FF-50-T-sync.png)

**2 · Business Rules**

| BR | R | Statement (first sentence, verbatim — the whole rule is in `02-business-rules.md`) | Status |
|---|---|---|---|
| `BR-FLD-00045` | R45 | Fifty items to a request, in capture order within an order. | DERIVED (decision log T-05) |
| `BR-FLD-00046` | R46 | The idempotency key is minted at capture, on the handset — not at send, and never by the server. | CONFIRMED — repo `BR-WRK-042` |
| `BR-FLD-00047` | R47 | The server answers per item, never per batch — accepted, duplicate or refused, with a savepoint around each. | CONFIRMED — repo `BR-WRK-042` |
| `BR-FLD-00051` | R51 | Data before photographs, always. | CONFIRMED — repo `BR-WRK-062` |
| `BR-FLD-00123` | R123 | A photograph is DECLARED with the data and its bytes follow separately. | CONFIRMED — repo `BR-WRK-062` |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | E2E-01 sync | Twenty-three outbox items in one batch, all accepted; four photographs follow on their own line |
| TC-2 | E2E-08: the app is killed between sending a batch and recording its receipt; it sends again on launch | 50 duplicate replies and not one doubled reading (R46) |
| TC-3 · **negative** | A safety tick and the close it unlocks are in different batches | The tick lands first (R45) |
| TC-4 | FF-50 | *Waiting to send · Completed work All sent · Photos 38 uploading · 24 of 62 · 41 MB left* |
| TC-5 · **tenant isolation** | R. Patel works for Silver Creek Water and Lone Star Water and signs in to Lone Star Water on the same handset | Only `field-lone-star-water.sqlite` is opened; not one Silver Creek row is readable (R131), and the server takes the tenant from the credential, never from the payload (R127) |

**4 · Test Data** — 23 items, 4 photos (E2E-01); 62 photos, 41 MB left (FF-50).

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| idempotency key | — | R46 | handset `outbox.id` minted at capture → server `work_sync_receipts` unique (tenant, work_order, key) | uuid | system-derived | never minted at send (R128) |

**6 · Acceptance** — **Given** captured work and photos, **when** the handset syncs, **then** data lands first with per-item receipts and photos follow without blocking it.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---

---
id: US-FLD-033
epic: EP-FLD-09
module: field-app
screens: [FF-51, FF-52, RW-29]
wave: 10
status: ready
blocked_by: []
depends_on: []
journeys: []           # the E2E-nn cases cited in §3 become journeys under 08-qa/01-e2e/journeys/ (sibling lane)
rules: [BR-FLD-00034, BR-FLD-00040, BR-FLD-00054, BR-FLD-00072]
golden_tests: []
finance_calc: none
---
### US-FLD-033 — Settings in full

**Requirement 33, in the design's words:** *Settings in full — language, date format, clock, units, four screen modes, bigger text, keep-awake, nearby radius, notifications per alert kind, sync over mobile data, version* — section F · Getting in, and the field conditions · standing *New*.

**1 · Details** — As **Dana**, I want **language, date format, clock, units, four screen modes, bigger text, keep-awake, nearby radius, notifications per kind, sync over mobile data and the version in one place**, so that **the app fits my day**. RW-29 holds the reading settings (keypad size, order, confirm each number, scan before reading, photos on mobile data, sound, dictation language).

**Screens (build from the images — B14 rules 42, 44, 45):** `FF-51` Settings — [phone](../wireframes/phone/FF-51-settings.png) · [tablet](../wireframes/tablet/FF-51-T-settings.png)<br>`FF-52` Notifications — [phone](../wireframes/phone/FF-52-notifications.png) · [tablet](../wireframes/tablet/FF-52-T-notifications.png)<br>`RW-29` Reading settings — [phone](../wireframes/reads/RW-29-reading-settings.png) · [tablet](../wireframes/tablet/RW-29-T-reading-settings.png)

**2 · Business Rules**

| BR | R | Statement (first sentence, verbatim — the whole rule is in `02-business-rules.md`) | Status |
|---|---|---|---|
| `BR-FLD-00034` | R34 | The nearby radius is a setting inside the app, default 2 miles | CONFIRMED (PO) |
| `BR-FLD-00040` | R40 | The app version is on screen, so a defect report can name a build | CONFIRMED (PO) |
| `BR-FLD-00054` | R54 | ~~Photographs wait for wi-fi unless the technician says otherwise — a setting inside the app, defaulting to off on mobile data~~ | **SUPERSEDED 2026-10-28 (PO, FB-015 option A: *"it should work on mobile and wifi both"*, *"go with A"*) → photos upload on mobile data AND wi-fi by default; the one switch left is *Photos on wi-fi only*, OFF by default; every phone moves to that default (decision log 2026-10-28, `DEF-FLD-10640`)** |
| `BR-FLD-00072` | R72 | Diagnostics are visible in Settings — one line saying they are on and what they leave out. | CONFIRMED — repo rule |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Language English → Español | Changes without restarting |
| TC-2 | Screen *Sunlight* | The theme switches at once (requirement 35) |
| TC-3 | Nearby work 5 mi | FF-11 uses 5 miles (R34) |
| TC-4 | About | *Version 2.587.0 · 412* (R40); diagnostics line says they are on and what they leave out (R72) |
| TC-5 · **negative** | *Photos on wi-fi only* ON, on cellular | Photos wait for wi-fi, and FF-50 says *Photos wait for wi-fi.* (2026-10-28; was R54's *Photos on mobile data off*, SUPERSEDED) |
| TC-5a | *Photos on wi-fi only* OFF (the default), on cellular | Photos upload; FF-50 shows no wi-fi line (2026-10-28, `DEF-FLD-10640`) |
| TC-6 · **tenant isolation** | R. Patel works for Silver Creek Water and Lone Star Water and signs in to Lone Star Water on the same handset | Only `field-lone-star-water.sqlite` is opened; not one Silver Creek row is readable (R131), and the server takes the tenant from the credential, never from the payload (R127) |

**4 · Test Data** — Date 20 Oct 2026 / 10/20/2026 / 2026-10-20 · clock 14:30 / 2:30 PM · miles / kilometres · radius 1 · 2 · 5 · 10 mi.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| preferences | FF-51, RW-29 | requirement 33 | MMKV (theme, language) + handset `settings` | various | user-input | survive restart |

**6 · Acceptance** — **Given** a technician, **when** they change a setting, **then** it applies without restarting and survives a restart.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---

---
id: US-FLD-034
epic: EP-FLD-09
module: field-app
screens: [FF-06, FF-18, FF-51]
wave: 10
status: ready
blocked_by: []
depends_on: []
journeys: []           # the E2E-nn cases cited in §3 become journeys under 08-qa/01-e2e/journeys/ (sibling lane)
rules: [BR-FLD-00038]
golden_tests: []
finance_calc: none
---
### US-FLD-034 — A technician taps, never types

**Requirement 34, in the design's words:** *A technician taps, never types — choices on screen instead of keyboards, steppers instead of number fields, dictation beside every note* — section F · Getting in, and the field conditions · standing *Design rule*.

**1 · Details** — As **Dana with gloves**, I want **choices on screen, steppers and dictation instead of keyboards**, so that **I can work in the field**. FF-06 has no input box at all (R38).

**Screens (build from the images — B14 rules 42, 44, 45):** `FF-06` Forgot password — [phone](../wireframes/phone/FF-06-forgot-password.png) · [tablet](../wireframes/tablet/FF-06-T-forgot-password.png)<br>`FF-18` Add step — [phone](../wireframes/phone/FF-18-add-step.png) · [tablet](../wireframes/tablet/FF-18-T-add-a-step.png)<br>`FF-51` Settings — [phone](../wireframes/phone/FF-51-settings.png) · [tablet](../wireframes/tablet/FF-51-T-settings.png)

**2 · Business Rules**

| BR | R | Statement (first sentence, verbatim — the whole rule is in `02-business-rules.md`) | Status |
|---|---|---|---|
| `BR-FLD-00038` | R38 | A technician taps, never types. | CONFIRMED (PO) |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | FF-18 *How long?* | Chips 5 · 15 · 30 min, not a number field |
| TC-2 | FF-06 | Three choices, no input box |
| TC-3 · **negative** | A free-text field with no dictation beside it | Fails review (R38) |
| TC-4 · **tenant isolation** | R. Patel works for Silver Creek Water and Lone Star Water and signs in to Lone Star Water on the same handset | Only `field-lone-star-water.sqlite` is opened; not one Silver Creek row is readable (R131), and the server takes the tenant from the credential, never from the payload (R127) |

**4 · Test Data** — FF-18 durations 5, 15, 30 min.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| — | all | R38 | — | — | — | design rule |

**6 · Acceptance** — **Given** any capture screen, **when** the technician enters data, **then** they can do it by tapping or speaking.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---

---
id: US-FLD-035
epic: EP-FLD-09
module: field-app
screens: [FF-54, FF-55, FF-51]
wave: 10
status: ready
blocked_by: []
depends_on: [US-FLD-001]
journeys: []           # the E2E-nn cases cited in §3 become journeys under 08-qa/01-e2e/journeys/ (sibling lane)
rules: [BR-FLD-00039, BR-FLD-00100, BR-FLD-00101]
golden_tests: []
finance_calc: none
---
### US-FLD-035 — Built for gloves and weather — 56 pt primary, 48 pt any control, 8 pt clear; three themes

**Requirement 35, in the design's words:** *Built for gloves and weather — primary action 56pt, any control 48pt, 8pt clear between targets* — section F · Getting in, and the field conditions · standing *Design rule*.

**1 · Details** — As **Dana at noon on a driveway**, I want **big targets and a sunlight theme**, so that **I hit the right button with gloves on**. Primary 56 pt, any control 48 pt, 8 pt clear (R39); the primary fill is #e12e13 (R100); spacing on the 4 px scale (R101). Sunlight is black on white, 3 px borders, one size up.

**Screens (build from the images — B14 rules 42, 44, 45):** `FF-54` Dark theme — [phone](../wireframes/phone/FF-54-dark-theme.png) · [tablet](../wireframes/tablet/FF-54-T-dark.png)<br>`FF-55` Sunlight theme — [phone](../wireframes/phone/FF-55-sunlight-theme.png) · [tablet](../wireframes/tablet/FF-55-T-sunlight.png)<br>`FF-51` Settings — [phone](../wireframes/phone/FF-51-settings.png) · [tablet](../wireframes/tablet/FF-51-T-settings.png)

**2 · Business Rules**

| BR | R | Statement (first sentence, verbatim — the whole rule is in `02-business-rules.md`) | Status |
|---|---|---|---|
| `BR-FLD-00039` | R39 | Built for gloves and weather: primary action 56pt, any interactive control 48pt, icon-only button 48pt, 8pt clear between adjacent targets | CONFIRMED (PO) |
| `BR-FLD-00100` | R100 | A primary button is the brand orange, so the app matches the website. | CONFIRMED (PO) |
| `BR-FLD-00101` | R101 | Spacing is a 4px scale and only seven values exist — 4, 8, 12, 16, 20, 24, 32. | CONFIRMED — repo rule |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Measure every control on FF-15 | Primary ≥ 56 pt, others ≥ 48 pt, 8 pt between targets (T-51 audit) |
| TC-2 | FF-54 dark and FF-55 sunlight | The same screen, nothing re-laid out — only the tokens change |
| TC-3 · **negative** | A 14 px gap | Not on the scale (R101) — refused |
| TC-4 | White on the primary button | Contrast 4.56:1 (R100) |
| TC-5 · **tenant isolation** | R. Patel works for Silver Creek Water and Lone Star Water and signs in to Lone Star Water on the same handset | Only `field-lone-star-water.sqlite` is opened; not one Silver Creek row is readable (R131), and the server takes the tenant from the credential, never from the payload (R127) |

**4 · Test Data** — Spacing 4, 8, 12, 16, 20, 24, 32.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| tokens | all | R100, R101 | `shared/tokens.ts` | colours, spacing, type | reference-data | one source |

**6 · Acceptance** — **Given** any screen, **when** it is measured, **then** every target meets the sizes and every gap is on the scale.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---

---
id: US-FLD-036
epic: EP-FLD-09
module: field-app
screens: [FF-01, FF-09, FF-51]
wave: 10
status: ready
blocked_by: []
depends_on: []
journeys: []           # the E2E-nn cases cited in §3 become journeys under 08-qa/01-e2e/journeys/ (sibling lane)
rules: [BR-FLD-00040]
golden_tests: []
finance_calc: none
---
### US-FLD-036 — The app version is visible, so a defect report names a build

**Requirement 36, in the design's words:** *The app version is visible to the technician, so a defect report names a build* — section F · Getting in, and the field conditions · standing *New*.

**1 · Details** — As **the office taking a defect report**, I want **the technician to read the version off the screen**, so that **we know which build** (R40).

**Screens (build from the images — B14 rules 42, 44, 45):** `FF-01` Splash — [phone](../wireframes/phone/FF-01-splash.png) · [tablet](../wireframes/tablet/FF-01-T-splash.png)<br>`FF-09` Menu — [phone](../wireframes/phone/FF-09-menu.png) · [tablet](../wireframes/tablet/FF-09-T-the-sidebar.png)<br>`FF-51` Settings — [phone](../wireframes/phone/FF-51-settings.png) · [tablet](../wireframes/tablet/FF-51-T-settings.png)

**2 · Business Rules**

| BR | R | Statement (first sentence, verbatim — the whole rule is in `02-business-rules.md`) | Status |
|---|---|---|---|
| `BR-FLD-00040` | R40 | The app version is on screen, so a defect report can name a build | CONFIRMED (PO) |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | FF-01, FF-09, FF-51 | *2.587.0 · build 412* |
| TC-2 · **negative** | A build with no version on screen | Fails (R40) |
| TC-3 · **tenant isolation** | R. Patel works for Silver Creek Water and Lone Star Water and signs in to Lone Star Water on the same handset | Only `field-lone-star-water.sqlite` is opened; not one Silver Creek row is readable (R131), and the server takes the tenant from the credential, never from the payload (R127) |

**4 · Test Data** — 2.587.0 · 412.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| version | FF-01/09/51 | R40 | app bundle | text | system-derived | one product version + store build |

**6 · Acceptance** — **Given** any build, **when** the technician opens the drawer or settings, **then** the version and build are on screen.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---

---
id: US-FLD-041
epic: EP-FLD-09
module: field-app
screens: [FF-50, RW-26]
wave: 0
status: ready
blocked_by: []
depends_on: [US-FLD-004]
journeys: []           # the E2E-nn cases cited in §3 become journeys under 08-qa/01-e2e/journeys/ (sibling lane)
rules: [BR-FLD-00045, BR-FLD-00049, BR-FLD-00050]
golden_tests: []
finance_calc: none
---
### US-FLD-041 — Captured work sent in batches of fifty, in capture order, resumably

**Requirement 41, in the design's words:** *Captured work is sent in batches, in capture order, item by item. Fifty to a request — not one request of a thousand, which a sixty-second worker timeout kills, and not a thousand requests. A batch that dies halfway leaves the rest pending, and only the rest is re-sent* — section G · Search, large volumes, refresh and the handset's data · standing *Engine built*.

**1 · Details** — As **Ray with 1,000 readings**, I want **them sent fifty to a request, two batches in flight, so that a batch that dies halfway re-sends only the rest** (R45, R49, R50).

**Screens (build from the images — B14 rules 42, 44, 45):** `FF-50` Sync — [phone](../wireframes/phone/FF-50-sync.png) · [tablet](../wireframes/tablet/FF-50-T-sync.png)<br>`RW-26` Sending — [phone](../wireframes/reads/RW-26-sending.png) · [tablet](../wireframes/tablet/RW-26-T-sending.png)

**2 · Business Rules**

| BR | R | Statement (first sentence, verbatim — the whole rule is in `02-business-rules.md`) | Status |
|---|---|---|---|
| `BR-FLD-00045` | R45 | Fifty items to a request, in capture order within an order. | DERIVED (decision log T-05) |
| `BR-FLD-00049` | R49 | State lives per row, so a send always resumes. | CONFIRMED — repo `BR-WRK-063` |
| `BR-FLD-00050` | R50 | At most two batches in flight. | DERIVED (decision log T-05) |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | 1,000 items | 20 batches of 50; at most two in flight |
| TC-2 | 23 of 50 accepted, then the connection dies | 27 are re-sent and nothing else (R49) |
| TC-3 · **negative** | One request of 1,000 | Not built — the sixty-second worker timeout would kill it (R45) |
| TC-4 | RW-26 | *Batch 4 of 5 · two in flight* |
| TC-5 · **tenant isolation** | R. Patel works for Silver Creek Water and Lone Star Water and signs in to Lone Star Water on the same handset | Only `field-lone-star-water.sqlite` is opened; not one Silver Creek row is readable (R131), and the server takes the tenant from the credential, never from the payload (R127) |

**4 · Test Data** — 1,000 readings; 20 batches; 60-second worker timeout.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| outbox state | FF-50 | R49 | handset `outbox.state` | pending · sending · accepted · duplicate · refused | system-derived | per row |

**6 · Acceptance** — **Given** a large outbox, **when** the handset sends, **then** it sends in batches of fifty and resumes only what did not land.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---

---
id: US-FLD-042
epic: EP-FLD-09
module: field-app
screens: [FF-50, RW-26, RW-27]
wave: 0
status: blocked
blocked_by: []          # the gap is named in §8; its OQ-FLD id is minted by the open-questions lane (DOC-C) and filled in here
depends_on: [US-FLD-041]
journeys: []           # the E2E-nn cases cited in §3 become journeys under 08-qa/01-e2e/journeys/ (sibling lane)
rules: [BR-FLD-00047, BR-FLD-00048]
golden_tests: []
finance_calc: none
---
### US-FLD-042 — The server answers for every item — accepted, duplicate or refused

**Requirement 42, in the design's words:** *The server answers for every item, never for the batch — accepted, duplicate or refused. One bad reading cannot cost the other forty-nine. A refusal is surfaced with its reason and stays until the technician acts on it* — section G · Search, large volumes, refresh and the handset's data · standing *Built*.

**1 · Details** — As **Dana**, I want **one bad reading not to cost the other forty-nine, and a refusal shown with its reason until I act**, so that **nothing is retried silently** (R47, R48).

**Screens (build from the images — B14 rules 42, 44, 45):** `FF-50` Sync — [phone](../wireframes/phone/FF-50-sync.png) · [tablet](../wireframes/tablet/FF-50-T-sync.png)<br>`RW-26` Sending — [phone](../wireframes/reads/RW-26-sending.png) · [tablet](../wireframes/tablet/RW-26-T-sending.png)<br>`RW-27` Turned in — [phone](../wireframes/reads/RW-27-turned-in.png) · [tablet](../wireframes/tablet/RW-27-T-turned-in.png)

**2 · Business Rules**

| BR | R | Statement (first sentence, verbatim — the whole rule is in `02-business-rules.md`) | Status |
|---|---|---|---|
| `BR-FLD-00047` | R47 | The server answers per item, never per batch — accepted, duplicate or refused, with a savepoint around each. | CONFIRMED — repo `BR-WRK-042` |
| `BR-FLD-00048` | R48 | A refusal is shown to the technician, never retried silently. | DERIVED (decision log T-05) |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | E2E-07: one reading of 180 in a batch of 50 is refused as impossible for that meter | The other 49 are accepted (savepoint per item, R47) |
| TC-2 | RW-26 / RW-27 | *2 already there — sent twice, counted once*; *1 refused — needs you* with the reason |
| TC-3 · **negative** | A refused item retried automatically | Never (R48) |
| TC-4 · **negative** | Whether an impossible reading is REFUSED or HELD FOR REVIEW | **Blocked** — see §8 |
| TC-5 · **tenant isolation** | R. Patel works for Silver Creek Water and Lone Star Water and signs in to Lone Star Water on the same handset | Only `field-lone-star-water.sqlite` is opened; not one Silver Creek row is readable (R131), and the server takes the tenant from the credential, never from the payload (R127) |

**4 · Test Data** — Batch of 50, one impossible reading; MTR-0618 removed 14 Oct.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| receipt | FF-50, RW-27 | R47 | server per-item answer → handset `outbox.state`, `last_error` | enum + reason | integration | stays until acted on |

**6 · Acceptance** — **Given** a batch with one bad item, **when** the server answers, **then** every item gets its own answer and a refusal waits for the technician.

**7 · Finance Calculation** — N/A.

**8 · Open Questions**

| OQ-ID | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| *to be minted by DOC-C* | What the technician sees for an item the server cannot apply: the design (R42, R48, E2E-07, RW-27 *1 refused — needs you*) says REFUSED and shown until acted on; the signed `BR-WRK-063` (PO 2026-10-04) says the server STORES anything it cannot apply, flagged needs-review, and acknowledges it — only the safety lock and an unverifiable caller go unacknowledged. Whether a refusal the technician must act on still exists is unruled. | the test case marked **Blocked** in §3 | Product Owner (a collision with a signed rule — law 13) | OPEN — not yet in the register |

---

---
id: US-FLD-044
epic: EP-FLD-09
module: field-app
screens: [FF-50, FF-08]
wave: 0
status: ready
blocked_by: []
depends_on: []
journeys: []           # the E2E-nn cases cited in §3 become journeys under 08-qa/01-e2e/journeys/ (sibling lane)
rules: [BR-FLD-00056, BR-FLD-00117, BR-FLD-00134]
golden_tests: []
finance_calc: none
---
### US-FLD-044 — A refresh is a delta, never a re-download

**Requirement 44, in the design's words:** *A refresh is a delta, never a re-download. A watermark per table asks only for what changed. A full pull happens on first sign-in and after a schema change, and nowhere else* — section G · Search, large volumes, refresh and the handset's data · standing *New*.

**1 · Details** — As **Dana on a mobile allowance**, I want **a refresh to ask only for what changed**, so that **it is fast and cheap**. A full pull happens on first sign-in and after a schema change only (R56); a payload carries a schema version the handset checks (R117).

**Screens (build from the images — B14 rules 42, 44, 45):** `FF-50` Sync — [phone](../wireframes/phone/FF-50-sync.png) · [tablet](../wireframes/tablet/FF-50-T-sync.png)<br>`FF-08` First sync — [phone](../wireframes/phone/FF-08-first-sync.png) · [tablet](../wireframes/tablet/FF-08-T-first-sync.png)

**2 · Business Rules**

| BR | R | Statement (first sentence, verbatim — the whole rule is in `02-business-rules.md`) | Status |
|---|---|---|---|
| `BR-FLD-00056` | R56 | A pull is a delta against a watermark, never a full download. | DERIVED (decision log T-05) |
| `BR-FLD-00117` | R117 | The wire shape and the local shape are two declared things with a versioned mapping. | DERIVED (decision log T-05) |
| `BR-FLD-00134` | R134 | The sync watermark is per technician per table, and the pair is the key. | CONFIRMED (PO) |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Second refresh of the day | Only rows changed since the per-technician watermark (R134) |
| TC-2 | First sign-in | A full pull (FF-08) |
| TC-3 · **negative** | A payload with an unknown schema version | Refused by the handset, never stored as nulls (R117) |
| TC-4 · **tenant isolation** | R. Patel works for Silver Creek Water and Lone Star Water and signs in to Lone Star Water on the same handset | Only `field-lone-star-water.sqlite` is opened; not one Silver Creek row is readable (R131), and the server takes the tenant from the credential, never from the payload (R127) |

**4 · Test Data** — Watermark per technician per table.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| watermark | FF-50 | R56 | handset `sync_state.cursor` | text | system-derived | per technician per table |

**6 · Acceptance** — **Given** a handset already holding the day, **when** it refreshes, **then** only changes since its watermark are pulled.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---

---
id: US-FLD-046
epic: EP-FLD-09
module: field-app
screens: [FF-50, FF-21]
wave: 0
status: ready
blocked_by: []
depends_on: [US-FLD-004]
journeys: []           # the E2E-nn cases cited in §3 become journeys under 08-qa/01-e2e/journeys/ (sibling lane)
rules: [BR-FLD-00051, BR-FLD-00053, BR-FLD-00061, BR-FLD-00124, BR-FLD-00125, BR-FLD-00126]
golden_tests: []
finance_calc: none
---
### US-FLD-046 — Photographs upload after the data, one at a time, resumably, even with the app closed

**Requirement 46, in the design's words:** *Photographs upload after the data, asynchronously, one at a time, resumably, continuing when the app is closed. The record must exist on the server before the photograph that attaches to it. One failed photo never blocks the next* — section G · Search, large volumes, refresh and the handset's data · standing *Engine built*.

**1 · Details** — As **Dana**, I want **photos to keep going up after I close the app, and one failure not to block the next**, so that **evidence lands** (R53). Binary multipart, one per request, hash declared first (R124); success means durably stored (R125).

**Screens (build from the images — B14 rules 42, 44, 45):** `FF-50` Sync — [phone](../wireframes/phone/FF-50-sync.png) · [tablet](../wireframes/tablet/FF-50-T-sync.png)<br>`FF-21` Photos — [phone](../wireframes/phone/FF-21-photos.png) · [tablet](../wireframes/tablet/FF-21-T-photos.png)

**2 · Business Rules**

| BR | R | Statement (first sentence, verbatim — the whole rule is in `02-business-rules.md`) | Status |
|---|---|---|---|
| `BR-FLD-00051` | R51 | Data before photographs, always. | CONFIRMED — repo `BR-WRK-062` |
| `BR-FLD-00053` | R53 | One photograph at a time, oldest first, resumable. | DERIVED (decision log T-05) |
| `BR-FLD-00061` | R61 | A photograph's file is deleted on confirmed receipt, not on sending. | DERIVED (decision log T-05) |
| `BR-FLD-00124` | R124 | Photographs travel as binary, never base64. | DERIVED (decision log T-05) |
| `BR-FLD-00125` | R125 | A success response means the bytes are durably stored, never that a job was enqueued. | DERIVED (decision log T-05) |
| `BR-FLD-00126` | R126 | Data items are answered synchronously; photo bytes are filed in the background. | DERIVED (decision log T-05) |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | E2E-09: 38 photos queued Monday with no wi-fi; charged overnight; up Tuesday morning | They outlive a shift, a sign-out and a restart, and attach to the right items |
| TC-2 · **negative** | Photo 7 fails | Photo 8 goes next (R53) |
| TC-3 · **negative** | The server answers 200 on enqueue only | The file is not deleted — only on confirmed durable storage (R125, R61) |
| TC-4 · **tenant isolation** | R. Patel works for Silver Creek Water and Lone Star Water and signs in to Lone Star Water on the same handset | Only `field-lone-star-water.sqlite` is opened; not one Silver Creek row is readable (R131), and the server takes the tenant from the credential, never from the payload (R127) |

**4 · Test Data** — 38 photos ~300 KB each by the design's figure (see `US-FLD-047` §8 for the signed size).

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| photo upload | FF-50 | R124 | multipart PUT per photo | binary | integration | hash first |

**6 · Acceptance** — **Given** queued photographs, **when** the handset has a connection, **then** they upload one at a time, oldest first, and each file is deleted only on confirmed receipt.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---

---
id: US-FLD-047
epic: EP-FLD-09
module: field-app
screens: [FF-51, FF-50]
wave: 0
status: blocked
blocked_by: []          # the gap is named in §8; its OQ-FLD id is minted by the open-questions lane (DOC-C) and filled in here
depends_on: [US-FLD-046]
journeys: []           # the E2E-nn cases cited in §3 become journeys under 08-qa/01-e2e/journeys/ (sibling lane)
rules: [BR-FLD-00054, BR-FLD-00055]
golden_tests: []
finance_calc: none
---
### US-FLD-047 — Photographs wait for wi-fi by default, compressed before queueing

**Requirement 47, in the design's words:** *Photographs wait for wi-fi by default, with a setting to send them on mobile data. Compressed to a 1,600 px long edge before queueing, around 300 KB each* — section G · Search, large volumes, refresh and the handset's data · standing *Built*.

**1 · Details** — ⚠ **R54 SUPERSEDED 2026-10-28 (PO, FB-015 option A).** As **Dana**, I want **my photos to go on mobile data or wi-fi, whichever I have**, so that **the office sees them the day I take them**; and a switch, *Photos on wi-fi only* (off by default), for when my allowance matters. Data always goes before photos. Compression never silently gives up (R55). *(Read until 2026-10-28: "photos to wait for wi-fi unless I say otherwise … (R54)".)*

**Screens (build from the images — B14 rules 42, 44, 45):** `FF-51` Settings — [phone](../wireframes/phone/FF-51-settings.png) · [tablet](../wireframes/tablet/FF-51-T-settings.png)<br>`FF-50` Sync — [phone](../wireframes/phone/FF-50-sync.png) · [tablet](../wireframes/tablet/FF-50-T-sync.png)

**2 · Business Rules**

| BR | R | Statement (first sentence, verbatim — the whole rule is in `02-business-rules.md`) | Status |
|---|---|---|---|
| `BR-FLD-00054` | R54 | ~~Photographs wait for wi-fi unless the technician says otherwise — a setting inside the app, defaulting to off on mobile data~~ | **SUPERSEDED 2026-10-28 (PO, FB-015 option A: *"it should work on mobile and wifi both"*, *"go with A"*) → photos upload on mobile data AND wi-fi by default; the one switch left is *Photos on wi-fi only*, OFF by default; every phone moves to that default (decision log 2026-10-28, `DEF-FLD-10640`)** |
| `BR-FLD-00055` | R55 | Compression never silently gives up. | CONFIRMED — repo `BR-WRK-047` |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Cellular, *Photos on mobile data* off | Photos wait; data still sends |
| TC-2 | Turn the setting on | Photos send on cellular |
| TC-3 · **negative** | A photo that will not compress small enough | Queued anyway; the server decides (R55, `BR-WRK-047` as superseded) |
| TC-4 · **negative** | The compression target | **Blocked** — see §8 |
| TC-5 · **tenant isolation** | R. Patel works for Silver Creek Water and Lone Star Water and signs in to Lone Star Water on the same handset | Only `field-lone-star-water.sqlite` is opened; not one Silver Creek row is readable (R131), and the server takes the tenant from the credential, never from the payload (R127) |

**4 · Test Data** — Default: wi-fi only.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| compressed size | — | requirement 47 | photo file | KB | system-derived | see §8 |

**6 · Acceptance** — **Given** a photo captured on cellular with the default setting, **when** the handset syncs, **then** data sends and the photo waits for wi-fi.

**7 · Finance Calculation** — N/A.

**8 · Open Questions**

| OQ-ID | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| *to be minted by DOC-C* | The compression target: requirement 47 says a 1,600 px long edge and about 300 KB each; the signed `BR-WRK-047` (PO 2026-10-04) says compress to 70–100 KB, with 1,600 px only the mechanism. The design's size, and the mobile-data budgets built on it (requirement 50, R110), collide with a signed rule. | the test case marked **Blocked** in §3 | Product Owner (a collision with a signed rule — law 13) | OPEN — not yet in the register |

---

---
id: US-FLD-048
epic: EP-FLD-09
module: field-app
screens: [FF-53, FF-50]
wave: 0
status: ready
blocked_by: []
depends_on: [US-FLD-003]
journeys: []           # the E2E-nn cases cited in §3 become journeys under 08-qa/01-e2e/journeys/ (sibling lane)
rules: [BR-FLD-00060, BR-FLD-00064, BR-FLD-00115]
golden_tests: []
finance_calc: none
---
### US-FLD-048 — Nothing unsent is ever deleted

**Requirement 48, in the design's words:** *Nothing unsent is ever deleted — at any age, under any sign-in, including another technician's work on a shared handset. A sign-out deletes nothing* — section G · Search, large volumes, refresh and the handset's data · standing *Ruled*.

**1 · Details** — As **Dana**, I want **unsent work kept at any age, under any sign-in, including someone else's**, so that **nothing is lost** (R60, R64).

**Screens (build from the images — B14 rules 42, 44, 45):** `FF-53` Sign out — [phone](../wireframes/phone/FF-53-sign-out.png) · [tablet](../wireframes/tablet/FF-53-T-sign-out.png)<br>`FF-50` Sync — [phone](../wireframes/phone/FF-50-sync.png) · [tablet](../wireframes/tablet/FF-50-T-sync.png)

**2 · Business Rules**

| BR | R | Statement (first sentence, verbatim — the whole rule is in `02-business-rules.md`) | Status |
|---|---|---|---|
| `BR-FLD-00060` | R60 | Nothing unsent is ever purged — at any age, under any sign-in, including another technician's work. | CONFIRMED (PO) |
| `BR-FLD-00064` | R64 | A sign-out deletes nothing. | CONFIRMED (PO) |
| `BR-FLD-00115` | R115 | A remote sign-out drops the mirror and keeps the outbox. | DERIVED (decision log T-05) |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | T-49: an unsent item 90 days old | Still there |
| TC-2 | Sign out with unsent work | Nothing deleted (R64) |
| TC-3 · **negative** | A purge that removes an unsent row | The retention test fails (R60) |
| TC-4 · **tenant isolation** | R. Patel works for Silver Creek Water and Lone Star Water and signs in to Lone Star Water on the same handset | Only `field-lone-star-water.sqlite` is opened; not one Silver Creek row is readable (R131), and the server takes the tenant from the credential, never from the payload (R127) |

**4 · Test Data** — An unsent item captured 90 days ago.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| unsent | FF-50 | R60 | handset `outbox` state pending/sending | rows | system-derived | never purged |

**6 · Acceptance** — **Given** unsent work of any age, **when** the purge runs, **then** it remains.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---

---
id: US-FLD-049
epic: EP-FLD-09
module: field-app
screens: [FF-50, FF-35, RW-27]
wave: 0
status: ready
blocked_by: []
depends_on: [US-FLD-048]
journeys: []           # the E2E-nn cases cited in §3 become journeys under 08-qa/01-e2e/journeys/ (sibling lane)
rules: [BR-FLD-00061, BR-FLD-00062, BR-FLD-00063, BR-FLD-00118]
golden_tests: []
finance_calc: none
---
### US-FLD-049 — Data leaves the handset once it is safely on the server

**Requirement 49, in the design's words:** *Data leaves the handset once it is safely on the server. A photograph's file is deleted the moment receipt is confirmed — not when it is sent. Sent work is kept seven days so the technician can see it; closed jobs fourteen so Completed works offline. Target footprint under 500 MB* — section G · Search, large volumes, refresh and the handset's data · standing *New*.

**1 · Details** — As **the utility**, I want **files deleted on confirmed receipt, sent work kept seven days and closed jobs fourteen**, so that **the handset stays under 500 MB and Completed works offline** (R61, R62, R63).

**Screens (build from the images — B14 rules 42, 44, 45):** `FF-50` Sync — [phone](../wireframes/phone/FF-50-sync.png) · [tablet](../wireframes/tablet/FF-50-T-sync.png)<br>`FF-35` Completed — [phone](../wireframes/phone/FF-35-completed.png) · [tablet](../wireframes/tablet/FF-35-T-completed.png)<br>`RW-27` Turned in — [phone](../wireframes/reads/RW-27-turned-in.png) · [tablet](../wireframes/tablet/RW-27-T-turned-in.png)

**2 · Business Rules**

| BR | R | Statement (first sentence, verbatim — the whole rule is in `02-business-rules.md`) | Status |
|---|---|---|---|
| `BR-FLD-00061` | R61 | A photograph's file is deleted on confirmed receipt, not on sending. | DERIVED (decision log T-05) |
| `BR-FLD-00062` | R62 | Sent work is kept seven days; closed jobs fourteen; documents to a 200 MB cap, evicted oldest first. | DERIVED (decision log T-05) |
| `BR-FLD-00063` | R63 | A purge runs on app start, never on a timer, so it cannot run mid-upload | DERIVED (decision log T-05) |
| `BR-FLD-00118` | R118 | A delete is the file before the row, and one transaction with its cascade. | DERIVED (decision log T-05) |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | A photo confirmed received | Its file is deleted; while merely sent, it stays (R61) |
| TC-2 | App start | The purge runs; never on a timer (R63) |
| TC-3 | RW-27 | *Kept on this phone for 14 days, then it clears itself.* |
| TC-4 · **negative** | A half-deleted job | Impossible — file before row, one transaction (R118) |
| TC-5 · **tenant isolation** | R. Patel works for Silver Creek Water and Lone Star Water and signs in to Lone Star Water on the same handset | Only `field-lone-star-water.sqlite` is opened; not one Silver Creek row is readable (R131), and the server takes the tenant from the credential, never from the payload (R127) |

**4 · Test Data** — Sent 7 days · closed jobs 14 days · documents 200 MB cap · target under 500 MB.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| settled_at | — | R62 | handset `outbox.settled_at` | timestamp | system-derived | drives the purge |

**6 · Acceptance** — **Given** settled work older than its window, **when** the app starts, **then** it is purged file first, and nothing unsent is touched.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---

---
id: US-FLD-050
epic: EP-FLD-09
module: field-app
screens: [FF-50]
wave: 0
status: ready
blocked_by: []
depends_on: [US-FLD-004]
journeys: []           # the E2E-nn cases cited in §3 become journeys under 08-qa/01-e2e/journeys/ (sibling lane)
rules: [BR-FLD-00033, BR-FLD-00065]
golden_tests: []
finance_calc: none
---
### US-FLD-050 — The mobile allowance is budgeted and visible; the sync screen counts items, not bytes

**Requirement 50, in the design's words:** *The mobile allowance is budgeted and the technician can see it. A realistic day is 15–18 MB, or 4–6 MB with photographs on wi-fi only. The sync screen counts items, not bytes, so one large photograph cannot make a finished day look unfinished* — section G · Search, large volumes, refresh and the handset's data · standing *New*.

**1 · Details** — As **Dana**, I want **the sync screen to read as finished when my work is sent**, so that **one large photo does not look like an unfinished day** (R33, R65).

**Screens (build from the images — B14 rules 42, 44, 45):** `FF-50` Sync — [phone](../wireframes/phone/FF-50-sync.png) · [tablet](../wireframes/tablet/FF-50-T-sync.png)

**2 · Business Rules**

| BR | R | Statement (first sentence, verbatim — the whole rule is in `02-business-rules.md`) | Status |
|---|---|---|---|
| `BR-FLD-00033` | R33 | Count items, not bytes, and show photos on their own line — "all work sent · 38 photos uploading" reads as finished, not broken | DERIVED (decision log T-05) |
| `BR-FLD-00065` | R65 | The sync number counts items, not bytes, and photographs get their own line. | CONFIRMED (PO) |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | All work sent, 38 photos uploading | *all work sent · 38 photos uploading* — finished, not broken |
| TC-2 · **negative** | One 4 MB photo left | The work line still reads all sent |
| TC-3 | Download everything | *11 jobs and 2 routes · 19 MB · do it on depot wi-fi* |
| TC-4 · **tenant isolation** | R. Patel works for Silver Creek Water and Lone Star Water and signs in to Lone Star Water on the same handset | Only `field-lone-star-water.sqlite` is opened; not one Silver Creek row is readable (R131), and the server takes the tenant from the credential, never from the payload (R127) |

**4 · Test Data** — A realistic day 15–18 MB, or 4–6 MB with photos on wi-fi only (design figures).

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| counts | FF-50 | R65 | handset `outbox`, `photo` | items | computed-display | photos on their own line |

**6 · Acceptance** — **Given** work sent and photos pending, **when** the technician opens Sync, **then** the work line says sent and the photos have their own line.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---

---
id: US-FLD-051
epic: EP-FLD-09
module: field-app
screens: [FF-51]
wave: 1
status: ready
blocked_by: []
depends_on: []
journeys: []           # the E2E-nn cases cited in §3 become journeys under 08-qa/01-e2e/journeys/ (sibling lane)
rules: [BR-FLD-00066, BR-FLD-00067, BR-FLD-00068]
golden_tests: []
finance_calc: none
---
### US-FLD-051 — Crash reporting that survives a shift offline

**Requirement 51, in the design's words:** *Crash reporting that survives a shift offline. JavaScript errors and native crashes with source maps and the breadcrumbs leading up to the fault, queued locally and sent later. Performance tracing on the four paths that hurt — app start, the day pull, a batch send, a photo upload* — section H · Knowing how it behaves in the field · standing *New*.

**1 · Details** — As **the team supporting a handset we cannot see**, I want **crashes queued locally and sent later with breadcrumbs, and traces on app start, day pull, batch send and photo upload**, so that **we can fix what we cannot reproduce**. Never customer data (R66); queued behind the work (R67).

**Screens (build from the images — B14 rules 42, 44, 45):** `FF-51` Settings — [phone](../wireframes/phone/FF-51-settings.png) · [tablet](../wireframes/tablet/FF-51-T-settings.png)

**2 · Business Rules**

| BR | R | Statement (first sentence, verbatim — the whole rule is in `02-business-rules.md`) | Status |
|---|---|---|---|
| `BR-FLD-00066` | R66 | Telemetry never carries customer data — no name, address, account number, balance, reading, photograph or signature, and never an outbox payload. | DERIVED (decision log T-05) |
| `BR-FLD-00067` | R67 | Telemetry queues behind the work, always. | DERIVED (decision log T-05) |
| `BR-FLD-00068` | R68 | Session replay is off — not configured carefully, off. | DERIVED (decision log T-05) |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | T-76: force a crash on FF-25 with a real account on screen | The report carries no name, address, account number or balance (R66) |
| TC-2 | Force a crash on FF-20 | No reading leaves |
| TC-3 · **negative** | Telemetry endpoint dead | Invisible to the technician; the outbox and photos go first (R67) |
| TC-4 · **negative** | Session replay | Off (R68) |
| TC-5 · **tenant isolation** | R. Patel works for Silver Creek Water and Lone Star Water and signs in to Lone Star Water on the same handset | Only `field-lone-star-water.sqlite` is opened; not one Silver Creek row is readable (R131), and the server takes the tenant from the credential, never from the payload (R127) |

**4 · Test Data** — FF-25 Sarah Miller A-10432 $241.38 on screen at the crash.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| event | — | R66 | telemetry queue (third queue) | allow-listed fields | system-derived | scrubbed |

**6 · Acceptance** — **Given** a crash offline, **when** the handset later reaches a signal, **then** the report is sent after the work, with no customer data in it.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---

---
id: US-FLD-052
epic: EP-FLD-09
module: field-app
screens: [FF-51]
wave: 1
status: ready
blocked_by: []
depends_on: [US-FLD-051]
journeys: []           # the E2E-nn cases cited in §3 become journeys under 08-qa/01-e2e/journeys/ (sibling lane)
rules: [BR-FLD-00069, BR-FLD-00070, BR-FLD-00071, BR-FLD-00072]
golden_tests: []
finance_calc: none
---
### US-FLD-052 — Product analytics and feature flags, with no customer data and never ahead of the work

**Requirement 52, in the design's words:** *Product analytics and feature flags. Which screens are used, where a technician abandons a flow, how long a job really takes — and flags, because an app-store review takes days and a held feature otherwise cannot be released without a build. No customer data, no named technician, no session replay, and never ahead of the work queue* — section H · Knowing how it behaves in the field · standing *New*.

**1 · Details** — As **the product team**, I want **which screens are used and where a flow is abandoned, and flags with cached defaults**, so that **a held feature can be released without a build**. Tenant, role and an anonymous device id only (R69); analytics is never the audit trail (R70).

**Screens (build from the images — B14 rules 42, 44, 45):** `FF-51` Settings — [phone](../wireframes/phone/FF-51-settings.png) · [tablet](../wireframes/tablet/FF-51-T-settings.png)

**2 · Business Rules**

| BR | R | Statement (first sentence, verbatim — the whole rule is in `02-business-rules.md`) | Status |
|---|---|---|---|
| `BR-FLD-00069` | R69 | A technician is not identified by name in analytics. | DERIVED (decision log T-05) |
| `BR-FLD-00070` | R70 | Analytics is never the audit trail. | CONFIRMED — repo rule |
| `BR-FLD-00071` | R71 | Every feature flag has a cached default, so a handset with no signal behaves the same way twice | DERIVED (decision log T-05) |
| `BR-FLD-00072` | R72 | Diagnostics are visible in Settings — one line saying they are on and what they leave out. | CONFIRMED — repo rule |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | An event leaves the handset | It carries tenant, role and an anonymous device id — never a name (R69) |
| TC-2 | No signal at launch | Every flag uses its cached default (R71) |
| TC-3 | FF-51 | One line: diagnostics are on and what they leave out (R72) |
| TC-4 · **negative** | Reading analytics to reconstruct who did what | Not a record — `audit_log` is (R70) |
| TC-5 · **tenant isolation** | R. Patel works for Silver Creek Water and Lone Star Water and signs in to Lone Star Water on the same handset | Only `field-lone-star-water.sqlite` is opened; not one Silver Creek row is readable (R131), and the server takes the tenant from the credential, never from the payload (R127) |

**4 · Test Data** — —

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| flag | — | R71 | cached flag set | bool | integration | cached default |

**6 · Acceptance** — **Given** a handset with no signal, **when** it launches, **then** it behaves as last time and sends no customer data.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---

---
id: US-FLD-079
epic: EP-FLD-09
module: field-app
screens: [FF-09]
wave: 0
status: ready
blocked_by: []
depends_on: []
journeys: []           # the E2E-nn cases cited in §3 become journeys under 08-qa/01-e2e/journeys/ (sibling lane)
rules: [BR-FLD-00098, BR-FLD-00099, BR-FLD-00119]
golden_tests: []
finance_calc: none
---
### US-FLD-079 — The code mirrors the server's module boundaries, and every screen has a door

**Requirement 79, in the design's words:** *The code mirrors the server's module boundaries — screens by flow stage, no SQL in a screen, one read-only seam file per server module, and a doors.test.ts that asserts every screen has something that opens it* — section L · The nine of 2026-10-21 · standing *New*.

**1 · Details** — As **the next lane**, I want **screens by flow stage, no SQL in a screen, one read-only seam file per server module, and a doors test**, so that **a screen with nothing opening it is caught** (R98, R99, R119).

**Screens (build from the images — B14 rules 42, 44, 45):** `FF-09` Menu — [phone](../wireframes/phone/FF-09-menu.png) · [tablet](../wireframes/tablet/FF-09-T-the-sidebar.png)

**2 · Business Rules**

| BR | R | Statement (first sentence, verbatim — the whole rule is in `02-business-rules.md`) | Status |
|---|---|---|---|
| `BR-FLD-00098` | R98 | A screen is not finished until something opens it, and the thing that opens it goes to the right address. | CONFIRMED — repo rule |
| `BR-FLD-00099` | R99 | Sweep the doors, do not reason about them. | DERIVED (decision log T-05) |
| `BR-FLD-00119` | R119 | No SQL in a screen — every query lives in db/queries/, one file per table. | DERIVED (decision log T-05) |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | doors.test.ts | Every screen has an inbound route; the splash is the one named orphan (R99) |
| TC-2 · **negative** | A screen file with an SQL statement | Fails (R119) |
| TC-3 · **negative** | A drawer entry pointing at the wrong screen | Fails by address and by screen id (R98) |
| TC-4 · **tenant isolation** | R. Patel works for Silver Creek Water and Lone Star Water and signs in to Lone Star Water on the same handset | Only `field-lone-star-water.sqlite` is opened; not one Silver Creek row is readable (R131), and the server takes the tenant from the credential, never from the payload (R127) |

**4 · Test Data** — 63 FF and 29 RW screens.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| — | — | R119 | `field-app/src/db/queries/` one file per table | — | — | — |

**6 · Acceptance** — **Given** the field-app source, **when** the doors test runs, **then** every screen has something that opens it at the right address.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---

---
id: US-FLD-081
epic: EP-FLD-09
module: field-app
screens: []
wave: 0
status: ready
blocked_by: []
depends_on: [US-FLD-079]
journeys: []           # the E2E-nn cases cited in §3 become journeys under 08-qa/01-e2e/journeys/ (sibling lane)
rules: [BR-FLD-00119]
golden_tests: []
finance_calc: none
---
### US-FLD-081 — Every screen's tables are written down, as a matrix

**Requirement 81, in the design's words:** *Every screen's tables are written down — what it reads and what it writes, as a matrix. It caught asset_document and template, neither of which had a table or a download* — section L · The nine of 2026-10-21 · standing *New*.

**1 · Details** — As **the next lane**, I want **a matrix of what each screen reads and writes**, so that **a table nobody designed is found before it is needed** — it found `asset_document` and `template`. The matrix itself lives in `03-field-map.md` (DOC lane), not here.

**Screens (build from the images — B14 rules 42, 44, 45):** No screen of its own — an engineering requirement every screen depends on.

**2 · Business Rules**

| BR | R | Statement (first sentence, verbatim — the whole rule is in `02-business-rules.md`) | Status |
|---|---|---|---|
| `BR-FLD-00119` | R119 | No SQL in a screen — every query lives in db/queries/, one file per table. | DERIVED (decision log T-05) |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | The matrix | Names a table for every read and write of every screen |
| TC-2 · **negative** | A screen writes a table the matrix does not list | The matrix check fails |
| TC-3 · **tenant isolation** | R. Patel works for Silver Creek Water and Lone Star Water and signs in to Lone Star Water on the same handset | Only `field-lone-star-water.sqlite` is opened; not one Silver Creek row is readable (R131), and the server takes the tenant from the credential, never from the payload (R127) |

**4 · Test Data** — —

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| — | — | requirement 81 | `03-field-map.md` | — | — | — |

**6 · Acceptance** — **Given** every screen, **when** its reads and writes are listed, **then** no table is missing from the handset design.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---

---
id: US-FLD-082
epic: EP-FLD-09
module: field-app
screens: []
wave: 0
status: ready
blocked_by: []
depends_on: [US-FLD-044]
journeys: []           # the E2E-nn cases cited in §3 become journeys under 08-qa/01-e2e/journeys/ (sibling lane)
rules: [BR-FLD-00116, BR-FLD-00117]
golden_tests: []
finance_calc: none
---
### US-FLD-082 — Queried means a column; the wire shape and the local shape are two declared things

**Requirement 82, in the design's words:** *Queried, sorted or filtered becomes a column; only ever displayed stays a JSON blob. And the half that bites: the wire shape and the local shape are two declared things with a versioned mapping, because a handset cannot ship a fix the same hour a web app can* — section L · The nine of 2026-10-21 · standing *New*.

**1 · Details** — As **the next lane**, I want **queried, sorted or filtered fields as columns and the rest as a JSON blob, with a versioned wire-to-local mapping**, so that **a server rename cannot silently store nulls** (R116, R117).

**Screens (build from the images — B14 rules 42, 44, 45):** No screen of its own — an engineering requirement every screen depends on.

**2 · Business Rules**

| BR | R | Statement (first sentence, verbatim — the whole rule is in `02-business-rules.md`) | Status |
|---|---|---|---|
| `BR-FLD-00116` | R116 | Queried, sorted or filtered → a column. | DERIVED (decision log T-05) |
| `BR-FLD-00117` | R117 | The wire shape and the local shape are two declared things with a versioned mapping. | DERIVED (decision log T-05) |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | An unknown field arrives | Kept and sent back untouched (R116) |
| TC-2 · **negative** | A payload with an unknown schema version | Refused (R117) |
| TC-3 · **tenant isolation** | R. Patel works for Silver Creek Water and Lone Star Water and signs in to Lone Star Water on the same handset | Only `field-lone-star-water.sqlite` is opened; not one Silver Creek row is readable (R131), and the server takes the tenant from the credential, never from the payload (R127) |

**4 · Test Data** — —

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| schema version | — | R117 | payload header | int | integration | known versions only |

**6 · Acceptance** — **Given** a server change to a field, **when** the handset receives it, **then** it is mapped by version or refused, never stored as nulls.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---

---
id: US-FLD-083
epic: EP-FLD-09
module: field-app
screens: [FF-50]
wave: 0
status: ready
blocked_by: []
depends_on: [US-FLD-049]
journeys: []           # the E2E-nn cases cited in §3 become journeys under 08-qa/01-e2e/journeys/ (sibling lane)
rules: [BR-FLD-00060, BR-FLD-00063, BR-FLD-00118]
golden_tests: []
finance_calc: none
---
### US-FLD-083 — Deleting after sync is specified, not implied

**Requirement 83, in the design's words:** *Deleting after sync is specified, not implied — the file before the row, cascades in one transaction, on app start never a timer, and nothing unsent at any age* — section L · The nine of 2026-10-21 · standing *New*.

**1 · Details** — As **the utility**, I want **the file deleted before the row, cascades in one transaction, on app start only, and nothing unsent at any age** (R118, R63, R60).

**Screens (build from the images — B14 rules 42, 44, 45):** `FF-50` Sync — [phone](../wireframes/phone/FF-50-sync.png) · [tablet](../wireframes/tablet/FF-50-T-sync.png)

**2 · Business Rules**

| BR | R | Statement (first sentence, verbatim — the whole rule is in `02-business-rules.md`) | Status |
|---|---|---|---|
| `BR-FLD-00060` | R60 | Nothing unsent is ever purged — at any age, under any sign-in, including another technician's work. | CONFIRMED (PO) |
| `BR-FLD-00063` | R63 | A purge runs on app start, never on a timer, so it cannot run mid-upload | DERIVED (decision log T-05) |
| `BR-FLD-00118` | R118 | A delete is the file before the row, and one transaction with its cascade. | DERIVED (decision log T-05) |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Purge a settled job | Its photo files go first, then its rows in one transaction |
| TC-2 · **negative** | The app is killed mid-purge | Rows remain consistent — either the whole job or none (R118) |
| TC-3 · **tenant isolation** | R. Patel works for Silver Creek Water and Lone Star Water and signs in to Lone Star Water on the same handset | Only `field-lone-star-water.sqlite` is opened; not one Silver Creek row is readable (R131), and the server takes the tenant from the credential, never from the payload (R127) |

**4 · Test Data** — —

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| — | — | R118 | handset purge | — | system-derived | one transaction |

**6 · Acceptance** — **Given** settled work, **when** the purge runs, **then** files go before rows and nothing is half-deleted.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.
