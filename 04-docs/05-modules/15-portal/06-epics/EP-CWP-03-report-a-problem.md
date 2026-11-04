# EP-CWP-03 — Report a problem, and the interruption record

**Module:** portal (+ metering owns the record) · **Wave:** release 1 ·
**Screens:** CWP-005 · CWP-006 · CWP-007 · CWP-012 · CWP-058 · **Status:** draft

## Scope

**In:** reporting an outage or a leak from a public form, the interruption record that
nothing in the product currently holds, the reference a stranger keeps, and the public
lookup that returns progress and never data.

**Out:** the public status page — `CR-068` `R9` ruled it **waits** until somebody owns
keeping it current out of hours. `CWP-005` is drawn and **not in scope**; it is here so
the other half of the interruption record is visible. **Do not put it in a build plan.**

⚠ **`CP-15` IS THE LARGEST GENUINELY NEW RECORD IN THE BLUEPRINT.** Nothing in this
product records an interruption or knows who it touches.

⚠ **THE RECORD BELONGS TO `metering`, NOT TO `portal`** (B2 §2 — the owning module owns
its data). An interruption is a network fact.

## Capability matrix

| Screen | Search | Filters | Default sort | Sortable | Columns | Row actions | Bulk | Export |
|---|---|---|---|---|---|---|---|---|
| CWP-006 | — | — | — | — | — | — | — | — |
| CWP-007 | — | — | — | — | — | — | — | Text me the reference |
| CWP-012 | Reference + a second fact | — | — | — | — | — | — | — |
| CWP-058 | — | Happening now · Planned | When | — | What · Where · When · Status | — | — | — |

---
id: US-CWP-007
epic: EP-CWP-03
module: portal
screens: [CWP-006]
wave: 1
status: ready
blocked_by: []
depends_on: [US-CWP-008, US-CWP-002]
journeys: [J31]
rules: [BR-CWP-026, BR-CWP-027, BR-CWP-076]
golden_tests: []
finance_calc: none
---
### US-CWP-007 — Report a problem, and the reporter need not be a customer

**1 · Details** — As **anyone who can see something wrong**, I want **to tell the utility
without an account**, so that **a burst main gets reported by whoever is standing over
it**.

Six kinds: no water at all (*treated as urgent*), a leak or a burst, low pressure, **a
smell of gas — ring us, do not use this form**, a missed collection, a damaged meter or
cover. Then a location, free text notes, an optional photo (held — TC-8), a name and a phone.

⚠ **THE EMERGENCY PANEL IS ROUTING, NOT A DISCLAIMER.** A form that quietly accepts
*"smell of gas"* and queues it behind a missed collection **is worse than no form**.

⚠ **AND THE ADDRESS IS FREE TEXT, RESOLVED LATER.** Demanding an exact premises match
would refuse the person standing over a burst main in the street.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-CWP-027` | The reporter need not be a customer; the address is free text resolved later | CONFIRMED — `CR-068` `R9`, answering `PQ-10` |
| `BR-CWP-026` | A public form may create work and may never change an account | CONFIRMED — blueprint `G10` |
| `BR-CWP-076` | Every request raised here carries channel `customer_portal` | CONFIRMED — `CP-13` |
| `BR-CWP-022` | Behind the throttle; the 61st in a minute is refused | CONFIRMED — blueprint §7 |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Report *a leak or a burst* at `1408 Elm St` with no account | Reference `RP-26-0412` on screen; the report appears on a clerk's worklist with channel **Customer portal** |
| TC-2 | An address that matches **no** premises | Accepted. `premises_id` stays null and a clerk resolves it — **never a refusal** |
| TC-3 · **negative** | Select *a smell of gas* | The form returns `(512) 555-0100` and **creates nothing**. No request row, no interruption row |
| TC-4 · **negative** | Submit with no phone | Refused — *"we ring you only if we need to"* requires a way to ring |
| TC-5 · **negative** | The 61st report in one minute | Refused, five-or-six-word sentence |
| TC-6 · **tenant isolation** | Report on `/oak-ridge` | The row lands under Oak Ridge only. It does not appear on any Pine Hill worklist |
| TC-7 | A second report from the same street | Accepted, and the screen says the street is already reported. ⚠ **Two reports of one burst is the desired behaviour** — *"we would rather hear twice than not at all"* |
| TC-8 | Attach a photo | ⚠ **Held — consumer upload is a signed deferral** (PO 2026-08-08, DF-4: *consumer upload portal = v2*; `CR-068` §2b; `US-CWP-064`). The `PhotoPicker` renders its sentence and **no file input**; a file posted to any portal endpoint is refused. After a re-sign: stored through the **existing** document store — its allow-list and its size cap, and NO malware scan — SUPERSEDED (PO 2026-09-22 / 2026-09-23 → no malware scan on upload), `DEF-SHL-6347` (this row read as built until 2026-09-03 — `DEF-CWP-3611`) |

**4 · Test Data** — Reporter *D. Okafor*, `(512) 555-7730`, not a customer. Location
`1408 Elm St, Austin TX 78702`. Notes *"Water coming up through the pavement outside
number 1412, been going since about seven…"*. Reference issued `RP-26-0412`, 2 Sep 2026
9:52am.

**5 · Data Fields / Mapping**

| Field | Screen | Source | DB target | Type | Origin | Validation |
|---|---|---|---|---|---|---|
| What is happening | CWP-006 | prototype-extracted | `interruption.kind` | enum | user-input | ⚠ `gas_smell` routes and does not persist |
| Where | CWP-006 | prototype-extracted | `interruption.location_text` | text | user-input | ⚠ Free text. **No premises match required** |
| Anything else | CWP-006 | prototype-extracted | `service_request.notes` | text | user-input | — |
| A photo | CWP-006 | prototype-extracted | **none until the upload deferral is re-signed** (then `document`) | — | user-input | ⚠ No route, no control — a held picker with its sentence (`DEF-CWP-3611`) |
| Your name, Phone | CWP-006 | prototype-extracted | `service_request.reporter_name`, `reporter_phone` | text | user-input | Phone required |
| Channel | — | A5 | `service_request.channel` | enum | system-derived | ⚠ `customer_portal` — **the first rows in the product ever to carry it** |

**6 · Acceptance** — **Given** a passer-by who is not a customer, **when** they report a
burst near `1412 Elm St`, **then** they get `RP-26-0412` on screen and a clerk sees it
with channel *Customer portal*; **and when** they select *a smell of gas*, **then** they
get a phone number and nothing is created.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None. `PQ-10` was ruled 2026-09-02.

---
id: US-CWP-008
epic: EP-CWP-03
module: metering
screens: []
wave: 1
status: ready
blocked_by: []
depends_on: []
journeys: [J31]
rules: [BR-CWP-027]
golden_tests: []
finance_calc: none
---
### US-CWP-008 — The interruption record and its affected-area rule

**1 · Details** — As **a clerk**, I want **one record of what is interrupted and which
premises it touches**, so that **reporting, tracking and planned-work notices all read
from one place**.

⚠ **THIS IS THE NEW THINKING IN THE WHOLE BLUEPRINT.** Not the record — the
**affected-area rule**. An interruption is *"Elm St, 1400–1500"*, and something has to
turn that into a set of premises.

The record: kind, reported and resolved times, a status of `looking_into_it` →
`crew_on_site` → `resolved`, free-text location, a nullable resolved premises, the
affected area, the reporter, and an expected back-on time.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-CWP-027` | Free-text location; premises resolved by a clerk, not by the form | CONFIRMED — blueprint `G6` |
| `BR-CWP-012` | The record lives in `metering` and the portal reads it through a seam | CONFIRMED — B2 §2 |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | A clerk moves the Elm St burst to `crew_on_site` | `CWP-007`'s timeline moves **without anyone editing the customer's page** |
| TC-2 | Affected area *Elm St, 1400–1500* | Resolves to the premises on that stretch **and to nobody else** |
| TC-3 · **negative** | Affected area naming a street with no premises | Resolves to an empty set and the record is still valid. **An interruption can exist before we know who it touches** |
| TC-4 · **negative** | Resolve an interruption already `resolved` | Refused; the second resolution is not recorded as a new event |
| TC-5 · **tenant isolation** | Pine Hill's affected area overlapping an Oak Ridge street name | Resolves within Pine Hill's premises only. RLS `FORCE` is on the table |
| TC-6 | An interruption with `expected_back_on` in the past, still `crew_on_site` | Shows as still open. ⚠ **The clock does not close a record** — a crew does |

**4 · Test Data** — Water off, burst main, `Elm St, 1400–1500`, since 7:05am today, back
on about 2pm, `crew_on_site`. Low pressure, `Cedar Row`, since 8:20am, no ETA,
`looking_into_it`. Premises `1408 Elm St` (units A, B, Common) and `1412 Elm St` in the
area; `22 Palm Ct` outside it.

**5 · Data Fields / Mapping** — See `03-field-map.md` § `interruption`. The one field
worth repeating: `affected_area` `jsonb`, a street plus a number range, **and it is the
piece with no precedent anywhere in the schema**.

**6 · Acceptance** — **Given** a burst reported on Elm St, **when** a clerk sets it to
*crew on site*, **then** every guest tracking that reference sees the change, the four
premises on that stretch are the affected set, and `22 Palm Ct` is not in it.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None for the record itself. ⚠ `CWP-058` (planned work) sits on
the **same** record and **is** blocked — `US-CWP-011`.

---
id: US-CWP-009
epic: EP-CWP-03
module: portal
screens: [CWP-007]
wave: 1
status: ready
blocked_by: []
depends_on: [US-CWP-007, US-CWP-008]
journeys: [J31]
rules: [BR-CWP-024, BR-CWP-028]
golden_tests: []
finance_calc: none
---
### US-CWP-009 — Report sent: a reference a stranger can keep

**1 · Details** — As **someone who has just reported a problem**, I want **a reference and
a timeline**, so that **I do not ring the office to ask whether anything happened**.

Shows `SENT`, the reference, when, where, what, and a four-step *what happens now* —
*you told us · we look at it · a crew is sent if needed · we close it off*. Plus *text me
the reference*.

⚠ **A REFERENCE IS WHAT MAKES A GUEST WORKFLOW FINISH PROPERLY.** Without one the visitor
has no way to know anything happened, and rings the office to check — **which is the call
the form was supposed to prevent.**

⚠ **AND THE CLOSING LINE MATTERS:** people suppress a second report assuming it is a
nuisance, and for a burst main it is the opposite.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-CWP-028` | Every guest flow ends on a reference, offers to send it, and is lookup-able with it | CONFIRMED — blueprint §7 |
| `BR-CWP-024` | The tracked view returns progress and never data | CONFIRMED — `CP-14` |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Submit a report | `RP-26-0412` with the timestamp, the location and the kind |
| TC-2 | Open the reference URL later, signed out | The timeline, updated to the current status |
| TC-3 · **negative** | Open the reference URL with **no** second fact | ⚠ The direct URL from the confirmation is trusted for **this session only**; a fresh visit requires the postcode or the phone (`BR-CWP-025`) |
| TC-4 · **negative** | The page after a clerk added an **internal routing note** | The note is **not** shown. Only notes flagged customer-visible appear |
| TC-5 · **tenant isolation** | `RP-26-0412` under `/oak-ridge` | Not found |
| TC-6 | *Text me the reference* | Sends through the existing outbound queue, to the phone given on the form |

**4 · Test Data** — `RP-26-0412`, reported 2 Sep 2026 9:52am, near `1412 Elm St`, *a leak
or a burst*, now *crew on site*. One internal note *"route to Tuesday crew, low
priority"* which must not appear.

**5 · Data Fields / Mapping**

| Field | Screen | Source | DB target | Type | Origin | Validation |
|---|---|---|---|---|---|---|
| Reference | CWP-007 | prototype-extracted | `service_request.reference` | text | system-derived | The human reference |
| Timeline | CWP-007 | prototype-extracted | `service_request_transition` | — | system-derived | ⚠ Filtered to the customer-safe half |

**6 · Acceptance** — **Given** a report just sent, **when** the confirmation opens,
**then** it shows `RP-26-0412` and a timeline; **and when** a clerk moves it to *crew on
site*, **then** the same reference shows the new status without exposing the internal
note beside it.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---
id: US-CWP-010
epic: EP-CWP-03
module: portal
screens: [CWP-012]
wave: 1
status: ready
blocked_by: []
depends_on: [US-CWP-002]
journeys: [J31]
rules: [BR-CWP-024, BR-CWP-025, BR-CWP-023]
golden_tests: []
finance_calc: none
---
### US-CWP-010 — Track anything: progress, and never data

**1 · Details** — As **anyone holding a reference**, I want **one box for every reference
the utility hands out**, so that **I can check a report, an application, a request or a
payment without an account**.

Two fields: the reference, and the postcode or the phone number given. Returns the
status and the dates.

⚠ **THE SECOND FIELD IS WHAT MAKES THIS SAFE.** A reference alone is guessable; a
reference plus a fact only the sender knows is not.

⚠ **AND THE LIMIT IS ABSOLUTE: PROGRESS, NEVER DATA.** No name, no balance, no other
reference on the account. Otherwise this is an account-disclosure route.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-CWP-024` | Returns the status and the dates. No name, no balance, no other reference | CONFIRMED — `CP-14` |
| `BR-CWP-025` | A second fact only the sender knows is required | CONFIRMED — blueprint `G12` |
| `BR-CWP-023` | Five wrong pairs locks fifteen minutes | CONFIRMED — `CP-37` |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | `RP-26-0412` + `78702` | *"A leak or a burst, near 1412 Elm St · Crew on site"* |
| TC-2 | `SR-26-0056` + the phone given | The move-out's progress and its dates |
| TC-3 · **negative** | `RP-26-0412` + a wrong postcode | Refused, and **identically** to an unknown reference |
| TC-4 · **negative** | A valid pair | ⚠ The response contains **no** customer name, **no** balance and **no** other reference. Asserted on the response body, not on the rendered page |
| TC-5 · **negative** | Six wrong pairs | Locked fifteen minutes, independently of the quick-pay lock |
| TC-6 · **tenant isolation** | A Pine Hill reference under `/oak-ridge` | Not found |
| TC-7 | A **payment** reference, `PAY-26-08841` + `78702` | Its status and date. ⚠ **Not the amount** — the amount is account data. ⊕ **BUILT 2026-09-05** (`7ac5d92c`, `DEF-CWP-3939`); the served key set is frozen in a test at five — `series`, `reference`, `status`, `reported_at`, `cleared_at`. ⚠ **THIS ROW ASSERTED THE ABSENCE UNTIL TODAY AND THAT IS WHY NOTHING WENT RED.** `TRACKABLE_SERIES == ("request",)` was the assertion, so it passed for as long as the gap lasted and would have passed forever; the wave-P dependency it waited on landed on 2026-09-04 and no check anywhere noticed. **A hold needs a test that fires when the hold EXPIRES** — the same bill `DEF-CWP-3925` paid three days earlier |

**4 · Test Data** — `RP-26-0412` + `78702`. `SR-26-0056` + `(512) 555-4218`.
`PAY-26-08841` + `78702`. Wrong pairs `RP-26-0413`…`0417` + `78702`.

**5 · Data Fields / Mapping**

| Field | Screen | Source | DB target | Type | Origin | Validation |
|---|---|---|---|---|---|---|
| Reference | CWP-012 | prototype-extracted | `service_request.reference` \| `payment.reference` | text | user-input | Matched across both series |
| Second fact | CWP-012 | prototype-extracted | `premises.postcode` \| the phone on the record | text | user-input | Either satisfies it |

**6 · Acceptance** — **Given** a stranger holding `RP-26-0412`, **when** they enter it
with `78702`, **then** they see the kind, the approximate location and the status — and
nothing about the customer, the balance or their other references.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---
id: US-CWP-011
epic: EP-CWP-03
module: metering
screens: [CWP-058, CWP-005]
wave: 1
status: blocked
blocked_by: [OQ-249]
depends_on: [US-CWP-008]
journeys: [J31]
rules: [BR-CWP-084, BR-CWP-093]
golden_tests: []
finance_calc: none
---
### US-CWP-011 — Outages and planned work

**1 · Details** — As **a customer**, I want **to know about work near me before it
happens**, so that **I am not surprised by a supply going off**.

⚠ **BLOCKED, AND ON A QUESTION OLDER THAN THIS MODULE.** A planned-outage notice needs
three things the product does not have: a record of the work, a way to say which premises
it touches, and a decision on whether it is published to everyone or only to affected
accounts. **The first two depend on the field-work module, whose scope is `OQ-249` and
open.** The notification event **exists and is refused by name** for exactly that reason.

Implement to the boundary: the read, the screen and the affected-premises join against
`interruption` (which `US-CWP-008` builds). Stub the planned-work source as
`raise NotImplementedError("OQ-249")`.

⚠ **`CWP-005`, the public status page, IS NOT IN SCOPE AT ALL** — `CR-068` `R9`. It is
drawn because it is the other half of the same record. **Reporting ships without it.**

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-CWP-093` | Nothing empty ever appears — no work, no page, no link | CONFIRMED — blueprint §16 |
| `BR-CWP-084` | A portal row is a record that a message exists, never proof it arrived | CONFIRMED — blueprint §19 |
| — | Whether planned work is published to everyone or only to affected accounts | **OPEN** — part of `OQ-249` |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Two planned works exist, seeded directly | `CWP-058` lists *"Water main replacement · Elm St, 1400–1500 · 4–5 Sep · Planned"* |
| TC-2 | The same work | It appears in `CWP-053` (messages) **for the accounts on that stretch and for nobody else** |
| TC-3 · **negative** | No planned work | ⚠ The page and its link are **absent**, not an empty table |
| TC-4 · **negative** | Call the planned-work write path | `NotImplementedError("OQ-249")` — ⚠ **the id is in the code**, per the prime directive |
| TC-5 · **tenant isolation** | Pine Hill's work under `/oak-ridge` | Absent |
| TC-6 | An account at `22 Palm Ct` | Does **not** see the Elm St work |

**4 · Test Data** — Water main replacement, `Elm St, 1400–1500`, 4–5 Sep, supply off
9am–3pm, `planned`. Meter exchange programme, `Palm Ct`, week of 15 Sep, `scheduled`.
Accounts: `1408 Elm St · A` (affected), `22 Palm Ct` (not).

**5 · Data Fields / Mapping** — See `03-field-map.md` § `planned_outage`. ⚠ **Do not
write the migration for that table until `OQ-249` is answered** — its affected-premises
rule is the field-work module's shape, and guessing it costs a migration rather than a
field.

**6 · Acceptance** — **Given** planned work seeded on `Elm St, 1400–1500`, **when** an
account on that stretch opens its messages, **then** the work appears there and on
`CWP-058`; **and given** no work is recorded, **then** neither the page nor its link
exists; **and** the write path raises `NotImplementedError("OQ-249")`.

**7 · Finance Calculation** — N/A.

**8 · Open Questions**

| OQ | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| `OQ-249` | The field-work module's scope, and with it the planned-outage record and its affected-premises rule | `CP-16`, this story, `US-CWP-068` | Product Owner | OPEN — **older than this module** |
