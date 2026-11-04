# EP-FLD-11 — Reads — the stop

**Module:** field-app (`18-field-app`, module code FLD) · **Wave:** 11 · **Design tasks:** Reads tab §2 · **Screens:** RW-05, RW-06, RW-07, RW-12, RW-09, RW-10, RW-11 · **Status:** draft (2026-10-21, `CR-187-BRC10`)

## Scope

**In:** the design's flow group *RW-06 to RW-12* and the requirements whose screens sit in it — US-FLD-055 (requirement 55), US-FLD-057 (requirement 57), US-FLD-058 (requirement 58).

**Out:** everything the design's *Scope · Out* list excludes (`01-overview.md` §5) — taking payment on site, linear assets, inspection rounds, offline maps, a dispatcher app, live crew tracking, van stock-takes, customer-facing features, a watch app.

**Source:** the *SMART360 Next Field App* design canvas, version of 2026-10-21. The screens are the images in `../wireframes/` and they are the specification (B14 rule 42; PO 2026-10-21, *"please ensure all native app screens are build using images not using text or contents"*). Figures on a board are illustrations (B14 rule 37) and are used below as test data only.

## Capability matrix (list screens only — B9 conformance)

| Screen | Search fields | Filters | Default sort | Sortable | Columns default/available | Row actions | Bulk actions | Export |
|---|---|---|---|---|---|---|---|---|
| RW-08 Find a meter | serial · badge · device ID · address · account | — | not declared | — | row: meter, badge, address, unit, customer, state | Read | — | — |

*Not declared* means the design does not say; requirement 37 and R44 require it declared and wired before the screen ships — the build lane declares it, it is not guessed here.

## Stories

---
id: US-FLD-055
epic: EP-FLD-11
module: field-app
screens: [RW-05, RW-06, RW-07, RW-12]
wave: 11
status: ready
blocked_by: []
depends_on: [US-FLD-054]
journeys: []           # the E2E-nn cases cited in §3 become journeys under 08-qa/01-e2e/journeys/ (sibling lane)
rules: [BR-FLD-00074, BR-FLD-00014, BR-FLD-00036]
golden_tests: []
finance_calc: none
---
### US-FLD-055 — The unit of work is the address — a stop holds every meter at it

**Requirement 55, in the design's words:** *The unit of work is the address, not the meter. Walk order is held per premises, so the walk is a list of stops and a stop holds every meter at it — master and sub-meters included* — section I · Reading meters on a route · standing *Signed rule*.

**1 · Details** — As **Ray at 1318 Maple**, I want **one stop with every meter there — units, master and sub-meters**, so that **I read the address, not a meter at a time** (R74). Access notes are held on the property (RW-07).

**Screens (build from the images — B14 rules 42, 44, 45):** `RW-05` The walk — [phone](../wireframes/reads/RW-05-the-walk.png) · [tablet](../wireframes/tablet/RW-05-T-the-walk.png)<br>`RW-06` The stop — [phone](../wireframes/reads/RW-06-the-stop.png) · [tablet](../wireframes/tablet/RW-06-T-the-stop.png)<br>`RW-07` Getting in — [phone](../wireframes/reads/RW-07-getting-in.png) · [tablet](../wireframes/tablet/RW-07-T-getting-in.png)<br>`RW-12` Master and subs — [phone](../wireframes/reads/RW-12-master-and-subs.png) · [tablet](../wireframes/tablet/RW-12-T-master-and-subs.png)

**2 · Business Rules**

| BR | R | Statement (first sentence, verbatim — the whole rule is in `02-business-rules.md`) | Status |
|---|---|---|---|
| `BR-FLD-00074` | R74 | The stop is the address. | CONFIRMED — repo `BR-MET-033` |
| `BR-FLD-00014` | R14 | A master and its sub-meters are read in one visit, and the app is built for that shape rather than one meter per job | CONFIRMED — repo rule |
| `BR-FLD-00036` | R36 | An address is stored on premises and derived everywhere else. | CONFIRMED — repo `BR-MET-1161` |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | RW-06 1318 Maple | Unit A Carla Ruiz ACC-10294 MTR-0471 · Unit B Desmond Oyelaran ACC-10311 MTR-0472 · Common Maple Heights HOA ACC-10002 MTR-0470 master and 3 sub-meters |
| TC-2 | RW-07 | Two dogs · gate code 4417 · in the pit by the driveway · last visit 22 Sep |
| TC-3 | RW-12 master 92,480 gal, two subs 60,740 | *Still to find 31,740*; the office checks the balance against its loss tolerance |
| TC-4 · **negative** | A stop that lists one meter of an address | Not the shape — the walk is a list of addresses (R74) |
| TC-5 · **tenant isolation** | Ray's route WLK-07 belongs to Silver Creek Water; a Lone Star Water route is downloaded for the same reader on the same handset | The two routes live in two database files; Silver Creek's walk never lists a Lone Star stop (R131), and the server reads the tenant from the credential (R127) |

**4 · Test Data** — MTR-0470 92,480 · MTR-0470-A 31,100 · MTR-0470-B 29,640 · MTR-0470-C to read.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| stop | RW-06 | R74 | handset `route_stop` per premises | row | integration | walk order per premises (`BR-MET-033`) |

**6 · Acceptance** — **Given** an address with several meters, **when** the reader opens the stop, **then** every meter at the address is listed and can be read in one visit.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---

---
id: US-FLD-057
epic: EP-FLD-11
module: field-app
screens: [RW-09, RW-10]
wave: 11
status: ready
blocked_by: []
depends_on: [US-FLD-055]
journeys: []           # the E2E-nn cases cited in §3 become journeys under 08-qa/01-e2e/journeys/ (sibling lane)
rules: [BR-FLD-00078]
golden_tests: []
finance_calc: none
---
### US-FLD-057 — The previous reading and the expected range are both on screen

**Requirement 57, in the design's words:** *The previous reading and the expected range are both on screen. I recommended showing only the range, to stop the number anchoring the reader. Overruled — show both* — section I · Reading meters on a route · standing *Ruled*.

**1 · Details** — As **Ray**, I want **last month's reading and the expected range beside the keypad**, so that **I see a slip as I make it**. The design recommended the range only; overruled — show both (R78).

**Screens (build from the images — B14 rules 42, 44, 45):** `RW-09` Read entry — [phone](../wireframes/reads/RW-09-read-entry.png) · [tablet](../wireframes/tablet/RW-09-T-read-entry.png)<br>`RW-10` Dials — [phone](../wireframes/reads/RW-10-dials.png) · [tablet](../wireframes/tablet/RW-10-T-dials.png)

**2 · Business Rules**

| BR | R | Statement (first sentence, verbatim — the whole rule is in `02-business-rules.md`) | Status |
|---|---|---|---|
| `BR-FLD-00078` | R78 | The previous reading and the expected range are both on screen. | CONFIRMED (PO) |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | RW-09 MTR-0471 | *Last month 48,210 · Expected 40,000–56,000* |
| TC-2 | RW-10 dials | *That reads 18,210 cubic feet · Used 420 · inside the expected range* |
| TC-3 · **negative** | Hide the previous reading | Not allowed — the ruling stands (R78) |
| TC-4 · **tenant isolation** | Ray's route WLK-07 belongs to Silver Creek Water; a Lone Star Water route is downloaded for the same reader on the same handset | The two routes live in two database files; Silver Creek's walk never lists a Lone Star stop (R131), and the server reads the tenant from the credential (R127) |

**4 · Test Data** — MTR-0471 last 48,210 gal · MTR-0488 18,210 ft³.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| previous + range | RW-09 | R78 | handset `route_read` (last, min, max) | number + unit | integration | both shown |

**6 · Acceptance** — **Given** a meter with history, **when** the reader opens it, **then** both the previous reading and the expected range show.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---

---
id: US-FLD-058
epic: EP-FLD-11
module: field-app
screens: [RW-06, RW-09, RW-11]
wave: 11
status: ready
blocked_by: []
depends_on: [US-FLD-055]
journeys: []           # the E2E-nn cases cited in §3 become journeys under 08-qa/01-e2e/journeys/ (sibling lane)
rules: [BR-FLD-00079]
golden_tests: []
finance_calc: none
---
### US-FLD-058 — The customer's name, the unit label and the account number are shown at the stop

**Requirement 58, in the design's words:** *The customer's name, the unit label and the account number are all shown at the stop. I recommended label and account only, to keep names off a handset that can be lost. Overruled — show the name* — section I · Reading meters on a route · standing *Ruled*.

**1 · Details** — As **Ray**, I want **the name beside the unit and account**, so that **I know whose meter it is**. The design recommended label and account only; overruled — show the name (R79).

**Screens (build from the images — B14 rules 42, 44, 45):** `RW-06` The stop — [phone](../wireframes/reads/RW-06-the-stop.png) · [tablet](../wireframes/tablet/RW-06-T-the-stop.png)<br>`RW-09` Read entry — [phone](../wireframes/reads/RW-09-read-entry.png) · [tablet](../wireframes/tablet/RW-09-T-read-entry.png)<br>`RW-11` Scan to confirm — [phone](../wireframes/reads/RW-11-scan-to-confirm.png) · [tablet](../wireframes/tablet/RW-11-T-scan-to-confirm.png)

**2 · Business Rules**

| BR | R | Statement (first sentence, verbatim — the whole rule is in `02-business-rules.md`) | Status |
|---|---|---|---|
| `BR-FLD-00079` | R79 | The customer's name is shown at the stop, beside the unit label and the account number. | CONFIRMED (PO) |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | RW-06 Unit A | *Carla Ruiz · ACC-10294* |
| TC-2 | RW-11 scan | *Unit A, Carla Ruiz.* |
| TC-3 · **negative** | Remove the name | Not allowed (R79) |
| TC-4 · **tenant isolation** | Ray's route WLK-07 belongs to Silver Creek Water; a Lone Star Water route is downloaded for the same reader on the same handset | The two routes live in two database files; Silver Creek's walk never lists a Lone Star stop (R131), and the server reads the tenant from the credential (R127) |

**4 · Test Data** — Carla Ruiz ACC-10294 · Desmond Oyelaran ACC-10311.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| name | RW-06 | R79 | handset `customer` | text | reference-data | shown |

**6 · Acceptance** — **Given** a stop, **when** the reader opens it, **then** each unit shows its customer's name and account.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.
