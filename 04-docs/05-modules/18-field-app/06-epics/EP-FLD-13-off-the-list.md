# EP-FLD-13 — Reads — what does not fit the list

**Module:** field-app (`18-field-app`, module code FLD) · **Wave:** 11 · **Design tasks:** Reads tab §4 · **Screens:** RW-17, RW-18, RW-19, RW-20, RW-21 · **Status:** draft (2026-10-21, `CR-187-BRC10`)

## Scope

**In:** the design's flow group *RW-18 to RW-21* and the requirements whose screens sit in it — US-FLD-060 (requirement 60), US-FLD-061 (requirement 61).

**Out:** everything the design's *Scope · Out* list excludes (`01-overview.md` §5) — taking payment on site, linear assets, inspection rounds, offline maps, a dispatcher app, live crew tracking, van stock-takes, customer-facing features, a watch app.

**Source:** the *SMART360 Next Field App* design canvas, version of 2026-10-21. The screens are the images in `../wireframes/` and they are the specification (B14 rule 42; PO 2026-10-21, *"please ensure all native app screens are build using images not using text or contents"*). Figures on a board are illustrations (B14 rule 37) and are used below as test data only.

## Capability matrix (list screens only — B9 conformance)

No list screen in this group.

## Stories

---
id: US-FLD-060
epic: EP-FLD-13
module: field-app
screens: [RW-17]
wave: 11
status: ready
blocked_by: []
depends_on: [US-FLD-066]
journeys: []           # the E2E-nn cases cited in §3 become journeys under 08-qa/01-e2e/journeys/ (sibling lane)
rules: [BR-FLD-00082, BR-FLD-00096]
golden_tests: []
finance_calc: none
---
### US-FLD-060 — Eight seeded reasons a meter cannot be read — the utility's own list

**Requirement 60, in the design's words:** *Eight seeded reasons a meter cannot be read — locked, no access, dog, buried or covered, obstructed, meter not found, unsafe, illegible — tenant-extensible, never hardcoded and never counted in code* — section I · Reading meters on a route · standing *Ruled*.

**1 · Details** — As **Ray at a locked meter**, I want **a list of reasons that is the utility's own**, so that **the office can extend it**. Eight seeded, tenant-extensible, never hardcoded and never counted in code (R82).

**Screens (build from the images — B14 rules 42, 44, 45):** `RW-17` Can't read — [phone](../wireframes/reads/RW-17-can-t-read.png) · [tablet](../wireframes/tablet/RW-17-T-can-t-read.png)

**2 · Business Rules**

| BR | R | Statement (first sentence, verbatim — the whole rule is in `02-business-rules.md`) | Status |
|---|---|---|---|
| `BR-FLD-00082` | R82 | The reasons a meter cannot be read are DATA. | CONFIRMED (PO) |
| `BR-FLD-00096` | R96 | Two statuses, never merged. | DERIVED (decision log T-05) |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | RW-17 | Dog · Locked · No access · Buried or covered · Obstructed · Meter not found · Unsafe · Illegible |
| TC-2 | The utility adds *Flooded* | It appears on RW-17 after the next refresh |
| TC-3 · **negative** | A test asserting the count in code | The screen reads the list from the server, and the test counts the served list (R82) |
| TC-4 · **tenant isolation** | Ray's route WLK-07 belongs to Silver Creek Water; a Lone Star Water route is downloaded for the same reader on the same handset | The two routes live in two database files; Silver Creek's walk never lists a Lone Star stop (R131), and the server reads the tenant from the credential (R127) |

**4 · Test Data** — Eight seeded reasons + one tenant addition.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| reason | RW-17 | R82 | server reference list → handset | code + name | reference-data | tenant-extensible |

**6 · Acceptance** — **Given** a meter that cannot be read, **when** the reader opens Can't read, **then** the utility's own reasons are offered.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---

---
id: US-FLD-061
epic: EP-FLD-13
module: field-app
screens: [RW-18, RW-19, RW-20, RW-21]
wave: 11
status: ready
blocked_by: []
depends_on: [US-FLD-038]
journeys: []           # the E2E-nn cases cited in §3 become journeys under 08-qa/01-e2e/journeys/ (sibling lane)
rules: [BR-FLD-00083, BR-FLD-00084, BR-FLD-00085, BR-FLD-00086]
golden_tests: []
finance_calc: none
---
### US-FLD-061 — A meter not on the route is scanned — read it if known, add it if not

**Requirement 61, in the design's words:** *A meter not on the route is scanned. Known to the system → read it, marked off-route. Unknown → add it, with a photograph, pending the office's acceptance. The reading is taken either way* — section I · Reading meters on a route · standing *New scope*.

**1 · Details** — As **Ray finding MTR-0903 nobody routed**, I want **to read it as off-route, or add an unknown meter with a photo pending the office**, so that **a true number is not lost** (R84, R85). A wrong badge is never guessed (RW-18).

**Screens (build from the images — B14 rules 42, 44, 45):** `RW-18` Different meter — [phone](../wireframes/reads/RW-18-different-meter.png) · [tablet](../wireframes/tablet/RW-18-T-different-meter.png)<br>`RW-19` Not on the route — [phone](../wireframes/reads/RW-19-not-on-the-route.png) · [tablet](../wireframes/tablet/RW-19-T-not-on-the-route.png)<br>`RW-20` Add a meter — [phone](../wireframes/reads/RW-20-add-a-meter.png) · [tablet](../wireframes/tablet/RW-20-T-add-a-meter.png)<br>`RW-21` Raise it — [phone](../wireframes/reads/RW-21-raise-it.png) · [tablet](../wireframes/tablet/RW-21-T-raise-it.png)

**2 · Business Rules**

| BR | R | Statement (first sentence, verbatim — the whole rule is in `02-business-rules.md`) | Status |
|---|---|---|---|
| `BR-FLD-00083` | R83 | A scanned code decides the meter — matched serial, then badge, then device ID. | DERIVED (decision log T-05) |
| `BR-FLD-00084` | R84 | An off-route reading is accepted and marked as off-route. | CONFIRMED (PO) |
| `BR-FLD-00085` | R85 | A meter added in the field is pending until the office accepts it, and a photograph is required. | DERIVED (decision log T-05) |
| `BR-FLD-00086` | R86 | A field-added meter takes its address by walking to the premises — resolved from the reader's position and confirmable, never typed as a new address. | CONFIRMED — repo `BR-MET-1161` |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | RW-19: scan 90118, known as MTR-0903 at 1318 Maple Unit C | *Read it anyway* — sent off-route; the office decides where it belongs |
| TC-2 | RW-20: scan 90241, unknown | Add with service, size and a required photo; address from where you are standing, confirmable; *You can read it now. It bills once accepted.* |
| TC-3 | RW-18: listed MTR-0471, scanned MTR-0533 recorded at 1206 Maple | *Do not guess* — swapped / wrong address / cannot tell; the plate photo is required |
| TC-4 · **negative** | A field-added meter bills before acceptance | Never (R85) |
| TC-5 · **negative** | A typed new address for a field-added meter | Not offered — resolved to the premises (R86) |
| TC-6 · **tenant isolation** | Ray's route WLK-07 belongs to Silver Creek Water; a Lone Star Water route is downloaded for the same reader on the same handset | The two routes live in two database files; Silver Creek's walk never lists a Lone Star stop (R131), and the server reads the tenant from the credential (R127) |

**4 · Test Data** — MTR-0903 badge 90118 ACC-10402 route none · badge 90241 unknown · MTR-0533 badge 90876.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| off-route flag | RW-19 | R84 | `route_read.off_route` | bool | system-derived | accepted |
| field-added meter | RW-20 | R85 | outbox `add_meter` → office acceptance | pending asset | user-input | photo required |

**6 · Acceptance** — **Given** a meter the list does not have, **when** the reader scans it, **then** it is read as off-route or added pending acceptance, with the reading kept either way.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.
