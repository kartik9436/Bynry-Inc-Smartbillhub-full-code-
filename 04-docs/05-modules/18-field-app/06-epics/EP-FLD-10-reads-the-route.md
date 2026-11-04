# EP-FLD-10 — Reads — getting a route

**Module:** field-app (`18-field-app`, module code FLD) · **Wave:** 11 · **Design tasks:** Reads tab §1 · **Screens:** RW-01, FF-63, FF-09, RW-02, RW-03, RW-05, RW-04 · **Status:** draft (2026-10-21, `CR-187-BRC10`)

## Scope

**In:** the design's flow group *RW-01 to RW-05* and the requirements whose screens sit in it — US-FLD-053 (requirement 53), US-FLD-054 (requirement 54), US-FLD-056 (requirement 56), US-FLD-062 (requirement 62).

**Out:** everything the design's *Scope · Out* list excludes (`01-overview.md` §5) — taking payment on site, linear assets, inspection rounds, offline maps, a dispatcher app, live crew tracking, van stock-takes, customer-facing features, a watch app.

**Source:** the *SMART360 Next Field App* design canvas, version of 2026-10-21. The screens are the images in `../wireframes/` and they are the specification (B14 rule 42; PO 2026-10-21, *"please ensure all native app screens are build using images not using text or contents"*). Figures on a board are illustrations (B14 rule 37) and are used below as test data only.

## Capability matrix (list screens only — B9 conformance)

| Screen | Search fields | Filters | Default sort | Sortable | Columns default/available | Row actions | Bulk actions | Export |
|---|---|---|---|---|---|---|---|---|
| RW-01 My routes | — | — | not declared | — | card: route, code, service, stops, meters, window | Open | — | — |
| RW-05 The walk | — | Nearest · Walk order | nearest (R75) | walk order one tap away | row: address, meters, distance | open stop | — | — |

*Not declared* means the design does not say; requirement 37 and R44 require it declared and wired before the screen ships — the build lane declares it, it is not guessed here.

## Stories

---
id: US-FLD-053
epic: EP-FLD-10
module: field-app
screens: [RW-01, FF-63, FF-09]
wave: 11
status: ready
blocked_by: []
depends_on: [US-FLD-078]
journeys: []           # the E2E-nn cases cited in §3 become journeys under 08-qa/01-e2e/journeys/ (sibling lane)
rules: [BR-FLD-00073, BR-FLD-00102]
golden_tests: []
finance_calc: none
---
### US-FLD-053 — Meter reading is a mode of the same app

**Requirement 53, in the design's words:** *Meter reading is a mode of the same app, not a second app. One sign-in, one sync engine, one outbox, one photo queue. The same role does service orders and reads — at these sizes it is the same person* — section I · Reading meters on a route · standing *Ruled*.

**1 · Details** — As **Dana, who does jobs and reads**, I want **Reads beside Jobs in one app with one sign-in, one sync engine, one outbox and one photo queue**, so that **I never switch apps** (R73). Reads is reached from the bottom bar (R102).

**Screens (build from the images — B14 rules 42, 44, 45):** `RW-01` My routes — [phone](../wireframes/reads/RW-01-my-routes.png) · [tablet](../wireframes/tablet/RW-01-T-my-routes.png)<br>`FF-63` Home — [phone](../wireframes/phone/FF-63-home.png) · [tablet](../wireframes/tablet/FF-63-T-home.png)<br>`FF-09` Menu — [phone](../wireframes/phone/FF-09-menu.png) · [tablet](../wireframes/tablet/FF-09-T-the-sidebar.png)

**2 · Business Rules**

| BR | R | Statement (first sentence, verbatim — the whole rule is in `02-business-rules.md`) | Status |
|---|---|---|---|
| `BR-FLD-00073` | R73 | Reading is a mode of the app, never a second app. | CONFIRMED (PO) |
| `BR-FLD-00102` | R102 | Reads is reached from the bottom bar, not from a menu. | CONFIRMED (PO) |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Bottom bar | *Home · Jobs · Reads*; Reads opens RW-01 My routes |
| TC-2 | RW-01 | *62 waiting to send · 38 photos · last sent 10:02* — the same outbox as jobs |
| TC-3 · **negative** | A second sign-in for Reads | None (R73) |
| TC-4 · **tenant isolation** | Ray's route WLK-07 belongs to Silver Creek Water; a Lone Star Water route is downloaded for the same reader on the same handset | The two routes live in two database files; Silver Creek's walk never lists a Lone Star stop (R131), and the server reads the tenant from the credential (R127) |

**4 · Test Data** — Maple Heights WLK-07 (Water, walk, 47 stops, 151 of 153 meters) · Riverside East DRV-02 (Electric, drive, not downloaded).

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| route list | RW-01 | requirement 53 | handset `route` (technician_id) | rows | integration | scoped |

**6 · Acceptance** — **Given** a technician with routes and jobs, **when** they tap Reads, **then** their routes open in the same app with the same sync.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---

---
id: US-FLD-054
epic: EP-FLD-10
module: field-app
screens: [RW-02, RW-03, RW-01]
wave: 11
status: ready
blocked_by: []
depends_on: [US-FLD-053]
journeys: []           # the E2E-nn cases cited in §3 become journeys under 08-qa/01-e2e/journeys/ (sibling lane)
rules: [BR-FLD-00076, BR-FLD-00104]
golden_tests: []
finance_calc: none
---
### US-FLD-054 — A route is downloaded whole, at the depot, and reaches 100% before leaving

**Requirement 54, in the design's words:** *A route is downloaded whole, at the depot. Stops in order, meters with last month's reads, access notes, map tiles, customer names — and the number has to reach 100% before leaving* — section I · Reading meters on a route · standing *New*.

**1 · Details** — As **Ray at the depot**, I want **stops in order, meters with last month's reads, access notes, map tiles and customer names on the phone**, so that **I need no signal on the walk**. One action downloads everything (R104).

**Screens (build from the images — B14 rules 42, 44, 45):** `RW-02` Route summary — [phone](../wireframes/reads/RW-02-route-summary.png) · [tablet](../wireframes/tablet/RW-02-T-route-summary.png)<br>`RW-03` Download — [phone](../wireframes/reads/RW-03-download.png) · [tablet](../wireframes/tablet/RW-03-T-download.png)<br>`RW-01` My routes — [phone](../wireframes/reads/RW-01-my-routes.png) · [tablet](../wireframes/tablet/RW-01-T-my-routes.png)

**2 · Business Rules**

| BR | R | Statement (first sentence, verbatim — the whole rule is in `02-business-rules.md`) | Status |
|---|---|---|---|
| `BR-FLD-00076` | R76 | Nearest-first works with no signal. | DERIVED (decision log T-05) |
| `BR-FLD-00104` | R104 | One action downloads everything — every assigned route and the whole day of service orders, one tap, one combined progress. | CONFIRMED (PO) |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | RW-02 Maple Heights | 47 stops · 151 meters · 3 sub-meters · WLK-07 · Water · Walk · North · WTR-M Oct · 20–24 Oct · route notes |
| TC-2 | RW-03 at 72% | *Start the walk · Opens at 100%* |
| TC-3 | RW-01 *Download both routes* | *419 meters · 15 MB · one tap, then go* (R104) |
| TC-4 · **negative** | Start the walk at 72% | Not offered until 100% |
| TC-5 · **tenant isolation** | Ray's route WLK-07 belongs to Silver Creek Water; a Lone Star Water route is downloaded for the same reader on the same handset | The two routes live in two database files; Silver Creek's walk never lists a Lone Star stop (R131), and the server reads the tenant from the credential (R127) |

**4 · Test Data** — WLK-07 151 meters + DRV-02 268 meters = 419; 6 MB of 9 MB on depot wi-fi.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| route bundle | RW-03 | requirement 54 | handset `route`, `route_stop`, `route_read`, `premise`, `customer` | rows | integration | 100% before start |

**6 · Acceptance** — **Given** an assigned route, **when** the reader downloads it, **then** everything for the walk is on the phone before it can start.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---

---
id: US-FLD-056
epic: EP-FLD-10
module: field-app
screens: [RW-05, RW-04]
wave: 11
status: ready
blocked_by: []
depends_on: [US-FLD-054]
journeys: []           # the E2E-nn cases cited in §3 become journeys under 08-qa/01-e2e/journeys/ (sibling lane)
rules: [BR-FLD-00075, BR-FLD-00076, BR-FLD-00077]
golden_tests: []
finance_calc: none
---
### US-FLD-056 — Nearest first by default, the office's walk order one tap away

**Requirement 56, in the design's words:** *Nearest first by default, with the office's walk order one tap away. Reading out of sequence is normal and never refused; the order actually walked is recorded* — section I · Reading meters on a route · standing *Ruled*.

**1 · Details** — As **Ray**, I want **the nearest stop first, with the office's order one tap away, and out-of-sequence reading never refused**, so that **I walk the way the street is** (R75, R77). Nearest-first works offline (R76).

**Screens (build from the images — B14 rules 42, 44, 45):** `RW-05` The walk — [phone](../wireframes/reads/RW-05-the-walk.png) · [tablet](../wireframes/tablet/RW-05-T-the-walk.png)<br>`RW-04` Route map — [phone](../wireframes/reads/RW-04-route-map.png) · [tablet](../wireframes/tablet/RW-04-T-route-map.png)

**2 · Business Rules**

| BR | R | Statement (first sentence, verbatim — the whole rule is in `02-business-rules.md`) | Status |
|---|---|---|---|
| `BR-FLD-00075` | R75 | Nearest first is the default; the office's walk order is always one tap away. | CONFIRMED (PO) |
| `BR-FLD-00076` | R76 | Nearest-first works with no signal. | DERIVED (decision log T-05) |
| `BR-FLD-00077` | R77 | Reading out of sequence is normal and never refused, and the order actually walked is recorded — which is also how next cycle's walk order gets better | CONFIRMED (PO) |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | RW-05 *Nearest* | 1318 Maple 40 m · 1322 Maple 70 m · 1240 Maple 150 m · 1206 Maple 240 m · 42 Birch Lane 310 m |
| TC-2 | *Walk order* | 9 1240 Maple · 10 1306 · 11 1312 · 12 1318 · 13 1322 |
| TC-3 | No signal | Nearest still sorts — premises points came with the route; only the reader's position is live (R76) |
| TC-4 · **negative** | Read stop 13 before stop 12 | Never refused; the order walked is recorded (R77) |
| TC-5 · **tenant isolation** | Ray's route WLK-07 belongs to Silver Creek Water; a Lone Star Water route is downloaded for the same reader on the same handset | The two routes live in two database files; Silver Creek's walk never lists a Lone Star stop (R131), and the server reads the tenant from the credential (R127) |

**4 · Test Data** — 29 of 151 read · 2 could not be.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| walked order | RW-05 | R77 | handset `route_read` sequence | int | system-derived | recorded as walked |

**6 · Acceptance** — **Given** a downloaded route, **when** the reader opens the walk, **then** the nearest stop is first, walk order is one tap away, and any order is accepted.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---

---
id: US-FLD-062
epic: EP-FLD-10
module: field-app
screens: [RW-01]
wave: 11
status: ready
blocked_by: []
depends_on: [US-FLD-054]
journeys: []           # the E2E-nn cases cited in §3 become journeys under 08-qa/01-e2e/journeys/ (sibling lane)
rules: [BR-FLD-00087]
golden_tests: []
finance_calc: none
---
### US-FLD-062 — One reader per route for now — nothing that forbids splitting later

**Requirement 62, in the design's words:** *One reader per route for now — and nothing is built that would have to be removed to split a route between two readers later. No constraint, no single-reader assumption in a code path* — section I · Reading meters on a route · standing *Ruled*.

**1 · Details** — As **the utility at T4 later**, I want **no constraint or code path assuming one reader**, so that **splitting a route is a change, not a rewrite** (R87).

**Screens (build from the images — B14 rules 42, 44, 45):** `RW-01` My routes — [phone](../wireframes/reads/RW-01-my-routes.png) · [tablet](../wireframes/tablet/RW-01-T-my-routes.png)

**2 · Business Rules**

| BR | R | Statement (first sentence, verbatim — the whole rule is in `02-business-rules.md`) | Status |
|---|---|---|---|
| `BR-FLD-00087` | R87 | One reader per route for now, and nothing is built that would have to be removed to split one later. | CONFIRMED (PO) |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Route WLK-07 assigned to Ray | One assignment row |
| TC-2 · **negative** | A unique constraint on route → reader | Not present (R87) |
| TC-3 · **negative** | A code path that reads `the` reader of a route as a single value | Fails review (R87) |
| TC-4 · **tenant isolation** | Ray's route WLK-07 belongs to Silver Creek Water; a Lone Star Water route is downloaded for the same reader on the same handset | The two routes live in two database files; Silver Creek's walk never lists a Lone Star stop (R131), and the server reads the tenant from the credential (R127) |

**4 · Test Data** — WLK-07 → Ray Delacroix.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| assignment | RW-01 | R87 | server route assignment (a row that could become many) | row | integration | no single-reader constraint |

**6 · Acceptance** — **Given** a route, **when** it is assigned, **then** the assignment is a row that could become many.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.
