# EP-FLD-14 — Reads — progress and turning it in

**Module:** field-app (`18-field-app`, module code FLD) · **Wave:** 11, 12 · **Design tasks:** Reads tab §5 · **Screens:** RW-22, RW-23, RW-25, RW-26, RW-27, RW-28, RW-05, RW-09 · **Status:** draft (2026-10-21, `CR-187-BRC10`)

## Scope

**In:** the design's flow group *RW-22 to RW-29* and the requirements whose screens sit in it — US-FLD-040 (requirement 40), US-FLD-077 (requirement 77).

**Out:** everything the design's *Scope · Out* list excludes (`01-overview.md` §5) — taking payment on site, linear assets, inspection rounds, offline maps, a dispatcher app, live crew tracking, van stock-takes, customer-facing features, a watch app.

**Source:** the *SMART360 Next Field App* design canvas, version of 2026-10-21. The screens are the images in `../wireframes/` and they are the specification (B14 rule 42; PO 2026-10-21, *"please ensure all native app screens are build using images not using text or contents"*). Figures on a board are illustrations (B14 rule 37) and are used below as test data only.

## Capability matrix (list screens only — B9 conformance)

| Screen | Search fields | Filters | Default sort | Sortable | Columns default/available | Row actions | Bulk actions | Export |
|---|---|---|---|---|---|---|---|---|
| RW-23 Still to do | — | Not read · Came back to · Flagged | distance (as drawn) | — | row: address, reason/time, distance | open | — | — |
| RW-28 My reads | — | This week · This cycle · Earlier | newest first (as drawn) | — | row: route, counts, day | open | — | — |

*Not declared* means the design does not say; requirement 37 and R44 require it declared and wired before the screen ships — the build lane declares it, it is not guessed here.

## Stories

---
id: US-FLD-040
epic: EP-FLD-14
module: field-app
screens: [RW-22, RW-23, RW-25, RW-26, RW-27, RW-28]
wave: 11
status: ready
blocked_by: []
depends_on: [US-FLD-041, US-FLD-042]
journeys: []           # the E2E-nn cases cited in §3 become journeys under 08-qa/01-e2e/journeys/ (sibling lane)
rules: [BR-FLD-00041, BR-FLD-00045, BR-FLD-00049, BR-FLD-00120]
golden_tests: []
finance_calc: none
---
### US-FLD-040 — A route of 500 to 1,000 readings captured offline and sent at once

**Requirement 40, in the design's words:** *A reading route of 500 to 1,000 readings in one day is a supported case, captured with no signal and sent at once. Capture must stay instant at that volume and the send must be resumable* — section G · Search, large volumes, refresh and the handset's data · standing *New*.

**1 · Details** — As **Ray**, I want **capture instant at volume, a turn-in that is not a gate, and a receipt that names what did not land**, so that **a thousand readings are a normal day**.

**Screens (build from the images — B14 rules 42, 44, 45):** `RW-22` Where you are — [phone](../wireframes/reads/RW-22-where-you-are.png) · [tablet](../wireframes/tablet/RW-22-T-where-you-are.png)<br>`RW-23` Still to do — [phone](../wireframes/reads/RW-23-still-to-do.png) · [tablet](../wireframes/tablet/RW-23-T-still-to-do.png)<br>`RW-25` Turn it in — [phone](../wireframes/reads/RW-25-turn-it-in.png) · [tablet](../wireframes/tablet/RW-25-T-turn-it-in.png)<br>`RW-26` Sending — [phone](../wireframes/reads/RW-26-sending.png) · [tablet](../wireframes/tablet/RW-26-T-sending.png)<br>`RW-27` Turned in — [phone](../wireframes/reads/RW-27-turned-in.png) · [tablet](../wireframes/tablet/RW-27-T-turned-in.png)<br>`RW-28` My reads — [phone](../wireframes/reads/RW-28-my-reads.png) · [tablet](../wireframes/tablet/RW-28-T-my-reads.png)

**2 · Business Rules**

| BR | R | Statement (first sentence, verbatim — the whole rule is in `02-business-rules.md`) | Status |
|---|---|---|---|
| `BR-FLD-00041` | R41 | Search is local first, server on request. | DERIVED (decision log T-05) |
| `BR-FLD-00045` | R45 | Fifty items to a request, in capture order within an order. | DERIVED (decision log T-05) |
| `BR-FLD-00049` | R49 | State lives per row, so a send always resumes. | CONFIRMED — repo `BR-WRK-063` |
| `BR-FLD-00120` | R120 | A technician's landing screen shows what is left and what is next, never how fast they are going. | DERIVED (decision log T-05) |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | E2E-03: 1,000 meters offline; 20 batches; connection killed during batches 7 and 14 | The office counts exactly 1,000 — not 1,048, not 963; 11 flagged, 3 unread; total send about 30 seconds |
| TC-2 | RW-25 with 15 unread | *Go and read the 15* is primary; *Turn in 136 of 151* second, danger tier |
| TC-3 | RW-27 | 129 readings · 7 with a reason · 11 flagged · 18 photos · 2 raised · 15 never read · *1 refused — Yours* |
| TC-4 | RW-22 | *136 of 151 done*; counted from the readings themselves, never a stored tally |
| TC-5 · **negative** | RW-28 pace | *What you read, not how fast.* (R120) |
| TC-6 · **tenant isolation** | Ray's route WLK-07 belongs to Silver Creek Water; a Lone Star Water route is downloaded for the same reader on the same handset | The two routes live in two database files; Silver Creek's walk never lists a Lone Star stop (R131), and the server reads the tenant from the credential (R127) |

**4 · Test Data** — WLK-07: 151 meters, 129 read, 7 could not be, 15 left, 11 flagged, 18 photos.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| turn-in | RW-25 | requirement 40 | outbox `turn_in` | event | user-input | never a gate |

**6 · Acceptance** — **Given** a route with readings left, **when** the reader turns it in, **then** the office has what landed, and the receipt names what did not.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---

---
id: US-FLD-077
epic: EP-FLD-14
module: field-app
screens: [RW-05, RW-09, RW-22, RW-28]
wave: 12
status: ready
blocked_by: []
depends_on: [US-FLD-001]
journeys: []           # the E2E-nn cases cited in §3 become journeys under 08-qa/01-e2e/journeys/ (sibling lane)
rules: [BR-FLD-00121, BR-FLD-00122]
golden_tests: []
finance_calc: none
---
### US-FLD-077 — Every reading screen works on a tablet

**Requirement 77, in the design's words:** *Every reading screen works on a tablet — all 29, in the same four frames as the field app. Capture is still a phone job and the design says so; the tablet earns its width on the walk, the read entry and the route progress* — section L · The nine of 2026-10-21 · standing *Built*.

**1 · Details** — As **a utility issuing tablets**, I want **all 29 reading screens on a tablet in the same four frames**, so that **a tablet earns its width on the walk, the read entry and the progress** — capture remains a phone job and the design says so.

**Screens (build from the images — B14 rules 42, 44, 45):** `RW-05` The walk — [phone](../wireframes/reads/RW-05-the-walk.png) · [tablet](../wireframes/tablet/RW-05-T-the-walk.png)<br>`RW-09` Read entry — [phone](../wireframes/reads/RW-09-read-entry.png) · [tablet](../wireframes/tablet/RW-09-T-read-entry.png)<br>`RW-22` Where you are — [phone](../wireframes/reads/RW-22-where-you-are.png) · [tablet](../wireframes/tablet/RW-22-T-where-you-are.png)<br>`RW-28` My reads — [phone](../wireframes/reads/RW-28-my-reads.png) · [tablet](../wireframes/tablet/RW-28-T-my-reads.png)

**2 · Business Rules**

| BR | R | Statement (first sentence, verbatim — the whole rule is in `02-business-rules.md`) | Status |
|---|---|---|---|
| `BR-FLD-00121` | R121 | A pane has a measured width, and content is designed to that number — not to the screen's. | DERIVED (decision log T-05) |
| `BR-FLD-00122` | R122 | Every frame states its usable width, and a check measures against it. | DERIVED (decision log T-05) |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | RW-05-T | The stop list beside the stop |
| TC-2 | RW-09-T | The keypad beside the meter and its history |
| TC-3 | RW-22-T | The whole route's progress at once |
| TC-4 · **negative** | Two columns in a 464 px pane | Fails the width check (R121, R122) |
| TC-5 · **tenant isolation** | Ray's route WLK-07 belongs to Silver Creek Water; a Lone Star Water route is downloaded for the same reader on the same handset | The two routes live in two database files; Silver Creek's walk never lists a Lone Star stop (R131), and the server reads the tenant from the credential (R127) |

**4 · Test Data** — 29 RW-…-T boards at 1024×768.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| frame | RW-*-T | R122 | layout | px | computed-display | measured |

**6 · Acceptance** — **Given** any reading screen, **when** it opens on a tablet, **then** it renders in one of the four frames within its measured width.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.
