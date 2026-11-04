# EP-FLD-05 — The customer, the money and the record on site

**Module:** field-app (`18-field-app`, module code FLD) · **Wave:** 6 · **Design tasks:** T-20 · **Screens:** FF-25, FF-26, FF-29, FF-30, FF-32, FF-18, FF-27, FF-31, FF-60, FF-61 · **Status:** draft (2026-10-21, `CR-187-BRC10`)

## Scope

**In:** the design's flow group *FF-25 to FF-31, FF-60, FF-61* and the requirements whose screens sit in it — US-FLD-012 (requirement 12), US-FLD-020 (requirement 20), US-FLD-022 (requirement 22), US-FLD-025 (requirement 25), US-FLD-030 (requirement 30), US-FLD-031 (requirement 31), US-FLD-073 (requirement 73), US-FLD-075 (requirement 75).

**Out:** everything the design's *Scope · Out* list excludes (`01-overview.md` §5) — taking payment on site, linear assets, inspection rounds, offline maps, a dispatcher app, live crew tracking, van stock-takes, customer-facing features, a watch app.

**Source:** the *SMART360 Next Field App* design canvas, version of 2026-10-21. The screens are the images in `../wireframes/` and they are the specification (B14 rule 42; PO 2026-10-21, *"please ensure all native app screens are build using images not using text or contents"*). Figures on a board are illustrations (B14 rule 37) and are used below as test data only.

## Capability matrix (list screens only — B9 conformance)

No list screen in this group.

## Stories

---
id: US-FLD-012
epic: EP-FLD-05
module: field-app
screens: [FF-25, FF-26]
wave: 6
status: ready
blocked_by: []
depends_on: [US-FLD-025]
journeys: []           # the E2E-nn cases cited in §3 become journeys under 08-qa/01-e2e/journeys/ (sibling lane)
rules: [BR-FLD-00016, BR-FLD-00017, BR-FLD-00019, BR-FLD-00020, BR-FLD-00026]
golden_tests: []
finance_calc: none
---
### US-FLD-012 — Customer, tariff, live balance and the cleared-payment check — read only

**Requirement 12, in the design's words:** *Customer, balance and payment — profile, active tariffs, live balance, cleared-payment check before restoring service, restoration countdown. On-site payment collection removed by ruling* — section A · The original brief · standing *Narrowed*.

**1 · Details** — As **Dana before restoring 22 Cedar Court**, I want **the balance, the tariff and whether a payment cleared**, so that **I restore only when the money says so**. The field app reads money and never writes it (R16); contractors see the name, not the money (R26). On-site payment collection is removed by ruling.

**Screens (build from the images — B14 rules 42, 44, 45):** `FF-25` Customer — [phone](../wireframes/phone/FF-25-customer.png) · [tablet](../wireframes/tablet/FF-25-T-customer.png)<br>`FF-26` Restoration — [phone](../wireframes/phone/FF-26-restoration.png) · [tablet](../wireframes/tablet/FF-26-T-restoration.png)

**2 · Business Rules**

| BR | R | Statement (first sentence, verbatim — the whole rule is in `02-business-rules.md`) | Status |
|---|---|---|---|
| `BR-FLD-00016` | R16 | The field app reads money and never writes it. | CONFIRMED (PO) |
| `BR-FLD-00017` | R17 | Money older than 5 minutes is warned, never blocked. | CONFIRMED (PO) |
| `BR-FLD-00019` | R19 | The server pushes the moment money changes. | CONFIRMED (PO) |
| `BR-FLD-00020` | R20 | Money shows to 2 decimals; a unit price shows up to 4. | CONFIRMED — repo `BR-RAT-087` |
| `BR-FLD-00026` | R26 | Contractors see the customer's name, not their money. | CONFIRMED (PO) |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | FF-25 for Sarah Miller as an employee | Account A-10432 · $241.38 owing · Res Standard · $0.0425 / gal · last payment $80.00 12 Aug |
| TC-2 | E2E-13: the customer pays at the counter while Dana is outside | A push reaches her (R19); FF-26 shows *Payment cleared $241.38 · Balance now $0.00 · Restore within 3:12* |
| TC-3 · **negative** | The same screen for R. Patel, contractor | Name and address only; balance, tariff and the cleared-payment check are not shown (R26) |
| TC-4 · **negative** | Look for a way to take payment | None — no tender capture, no staging, no money write (R16) |
| TC-5 | Amounts and unit prices | $241.38 at 2 decimals; $0.0425 per gallon up to 4 (R20) |
| TC-6 · **tenant isolation** | R. Patel works for Silver Creek Water and Lone Star Water and signs in to Lone Star Water on the same handset | Only `field-lone-star-water.sqlite` is opened; not one Silver Creek row is readable (R131), and the server takes the tenant from the credential, never from the payload (R127) |

**4 · Test Data** — Sarah Miller A-10432 $241.38 · Aaron Bruner A-10588 meter W-6120 · paid $241.38 by card 18 Oct 16:04.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| balance | FF-25 | R16 | server payments seam read (online only; never stored in `customer`) | money 2 dp | integration | with its as-at time |
| cleared payment | FF-26 | requirement 12 | payments seam read | bool + time | integration | employee only (R26) |

**6 · Acceptance** — **Given** an employee at a restoration, **when** the payment has cleared, **then** the screen shows it with its age and the restoration countdown, and nothing on it writes money.

**7 · Finance Calculation** — N/A. The field app reads money and never writes it (R16).

**8 · Open Questions** — None.

---

---
id: US-FLD-020
epic: EP-FLD-05
module: field-app
screens: [FF-29]
wave: 6
status: ready
blocked_by: []
depends_on: [US-FLD-029]
journeys: []           # the E2E-nn cases cited in §3 become journeys under 08-qa/01-e2e/journeys/ (sibling lane)
rules: [BR-FLD-00008, BR-FLD-00010]
golden_tests: []
finance_calc: none
---
### US-FLD-020 — Crew jobs — more than one technician on an order

**Requirement 20, in the design's words:** *Crew jobs — more than one technician on an order* — section C · From the reference apps, confirmed into scope · standing *Backend only*.

**1 · Details** — As **Dana leading WO-4822 with M. Chen**, I want **each of us on the order with our own time**, so that **labour is per person and the cost is the sum**. The lead closes it (R8).

**Screens (build from the images — B14 rules 42, 44, 45):** `FF-29` Crew — [phone](../wireframes/phone/FF-29-crew.png) · [tablet](../wireframes/tablet/FF-29-T-crew.png)

**2 · Business Rules**

| BR | R | Statement (first sentence, verbatim — the whole rule is in `02-business-rules.md`) | Status |
|---|---|---|---|
| `BR-FLD-00008` | R8 | Labour is per person, not per job. | CONFIRMED (PO) |
| `BR-FLD-00010` | R10 | Every status change is stamped with who and when, and is readable on the job | CONFIRMED (PO) |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | FF-29 with D. Ortiz (lead) and M. Chen | *2h 24m labour on this job · 2 technicians · 1h 12m each* |
| TC-2 · **negative** | M. Chen tries to close | Only the lead closes (R8) |
| TC-3 | *Correct their time* on M. Chen | Corrected and stamped who and when (R10) |
| TC-4 · **tenant isolation** | R. Patel works for Silver Creek Water and Lone Star Water and signs in to Lone Star Water on the same handset | Only `field-lone-star-water.sqlite` is opened; not one Silver Creek row is readable (R131), and the server takes the tenant from the credential, never from the payload (R127) |

**4 · Test Data** — D. Ortiz Water II lead, arrived 08:14 · M. Chen Water I, arrived 08:46, came with lead.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| crew time | FF-29 | R8 | handset `crew_time` per person per order | minutes | system-derived | one record per person |

**6 · Acceptance** — **Given** two technicians on one order, **when** both record time, **then** two time records exist and the cost is their sum.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---

---
id: US-FLD-022
epic: EP-FLD-05
module: field-app
screens: [FF-30, FF-32, FF-18]
wave: 6
status: ready
blocked_by: []
depends_on: [US-FLD-030]
journeys: []           # the E2E-nn cases cited in §3 become journeys under 08-qa/01-e2e/journeys/ (sibling lane)
rules: [BR-FLD-00038, BR-FLD-00095]
golden_tests: []
finance_calc: none
---
### US-FLD-022 — Voice capture for notes — works with gloves on and wet hands

**Requirement 22, in the design's words:** *Voice capture for notes — works with gloves on and wet hands* — section C · From the reference apps, confirmed into scope · standing *New*.

**1 · Details** — As **Dana with wet gloves**, I want **to dictate a note beside every note field**, so that **I never type on site**. Dictation sits beside every note (R38); a remark is never required (R95).

**Screens (build from the images — B14 rules 42, 44, 45):** `FF-30` Notes — [phone](../wireframes/phone/FF-30-notes.png) · [tablet](../wireframes/tablet/FF-30-T-notes.png)<br>`FF-32` Debrief — [phone](../wireframes/phone/FF-32-debrief.png) · [tablet](../wireframes/tablet/FF-32-T-debrief.png)<br>`FF-18` Add step — [phone](../wireframes/phone/FF-18-add-step.png) · [tablet](../wireframes/tablet/FF-18-T-add-a-step.png)

**2 · Business Rules**

| BR | R | Statement (first sentence, verbatim — the whole rule is in `02-business-rules.md`) | Status |
|---|---|---|---|
| `BR-FLD-00038` | R38 | A technician taps, never types. | CONFIRMED (PO) |
| `BR-FLD-00095` | R95 | A remark is spoken by default, typed as the fallback, and never required. | DERIVED (decision log T-05) |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Dictate on FF-32 *What I did* | *Replaced meter, re-sealed, opened main, no leaks.* is saved as text |
| TC-2 | Add note on FF-30 by voice | Stamped *D. Ortiz · On site · 20 Oct 09:31* |
| TC-3 · **negative** | Leave a note empty | Nothing blocks — a note is never mandatory (R95) |
| TC-4 · **tenant isolation** | R. Patel works for Silver Creek Water and Lone Star Water and signs in to Lone Star Water on the same handset | Only `field-lone-star-water.sqlite` is opened; not one Silver Creek row is readable (R131), and the server takes the tenant from the credential, never from the payload (R127) |

**4 · Test Data** — Notes on WO-4822 at 07:12, 08:52, 09:31, 09:44.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| note text | FF-30/32 | R38 | handset `activity` kind=remark | text | user-input | dictated or typed |

**6 · Acceptance** — **Given** any note field, **when** the technician dictates, **then** the note is saved as text with who and when.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---

---
id: US-FLD-025
epic: EP-FLD-05
module: field-app
screens: [FF-27]
wave: 6
status: ready
blocked_by: []
depends_on: [US-FLD-012]
journeys: []           # the E2E-nn cases cited in §3 become journeys under 08-qa/01-e2e/journeys/ (sibling lane)
rules: [BR-FLD-00017, BR-FLD-00018, BR-FLD-00019]
golden_tests: []
finance_calc: none
---
### US-FLD-025 — A real-time check before an irreversible act — stale money is warned, never blocked

**Requirement 25, in the design's words:** *Real-time check before an irreversible act — the balance must not be three days old when the valve closes* — section D · Asked for by the technicians · standing *New*.

**1 · Details** — As **Dana about to close the valve at 22 Cedar Court**, I want **to see how old the balance is and check it now**, so that **I never disconnect a customer who paid**. Older than 5 minutes is warned, never blocked; proceeding is recorded as unverified and the button moves to the danger tier (R17). Freshness sits on the template step (R18).

**Screens (build from the images — B14 rules 42, 44, 45):** `FF-27` Stale money — [phone](../wireframes/phone/FF-27-stale-money.png) · [tablet](../wireframes/tablet/FF-27-T-disconnect.png)

**2 · Business Rules**

| BR | R | Statement (first sentence, verbatim — the whole rule is in `02-business-rules.md`) | Status |
|---|---|---|---|
| `BR-FLD-00017` | R17 | Money older than 5 minutes is warned, never blocked. | CONFIRMED (PO) |
| `BR-FLD-00018` | R18 | Freshness sits on the template step, the same way photo required and must do already do. | DERIVED (decision log T-05) |
| `BR-FLD-00019` | R19 | The server pushes the moment money changes. | CONFIRMED (PO) |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | E2E-11: balance read eleven minutes ago; Dana taps *Check now* | The amount drops to $0.00, turns green, and *Disconnect anyway* becomes *Close — customer paid* |
| TC-2 | E2E-12: no signal, the figure is three days old | Warned; she proceeds; the office sees *unverified* on the order |
| TC-3 · **negative** | A disconnect step with no freshness on the template | No warning — no code knows what a disconnect is (R18) |
| TC-4 · **negative** | Stale balance | Never blocks; *Disconnect anyway* is danger tier |
| TC-5 · **tenant isolation** | R. Patel works for Silver Creek Water and Lone Star Water and signs in to Lone Star Water on the same handset | Only `field-lone-star-water.sqlite` is opened; not one Silver Creek row is readable (R131), and the server takes the tenant from the credential, never from the payload (R127) |

**4 · Test Data** — WO-4824 · Aaron Bruner · 22 Cedar Court · A-10588 · W-6120 · $241.38.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| as-at | FF-27 | R17 | money freshness read (server) | timestamp | integration | 5 minutes |
| unverified | FF-27 | R17 | outbox `close` flag | bool | system-derived | set when proceeding on stale data |

**6 · Acceptance** — **Given** a step that declares a freshness of 5 minutes, **when** the figure is older, **then** the technician is warned, can check now or proceed, and proceeding is recorded as unverified.

**7 · Finance Calculation** — N/A. The field app reads money and never writes it (R16).

**8 · Open Questions** — None.

---

---
id: US-FLD-030
epic: EP-FLD-05
module: field-app
screens: [FF-30, FF-31]
wave: 6
status: ready
blocked_by: []
depends_on: [US-FLD-008]
journeys: []           # the E2E-nn cases cited in §3 become journeys under 08-qa/01-e2e/journeys/ (sibling lane)
rules: [BR-FLD-00010, BR-FLD-00035]
golden_tests: []
finance_calc: none
---
### US-FLD-030 — Notes, remarks and a stamped status history

**Requirement 30, in the design's words:** *Notes, remarks, and a stamped status history — who, what, when, for every change* — section E · From the walkthrough of the drawings · standing *New*.

**1 · Details** — As **the office reading WO-4822 later**, I want **every remark and every status change with who and when**, so that **the job's story is on the job**. Every status change is stamped (R10).

**Screens (build from the images — B14 rules 42, 44, 45):** `FF-30` Notes — [phone](../wireframes/phone/FF-30-notes.png) · [tablet](../wireframes/tablet/FF-30-T-notes.png)<br>`FF-31` Activity — [phone](../wireframes/phone/FF-31-activity.png) · [tablet](../wireframes/tablet/FF-31-T-activity.png)

**2 · Business Rules**

| BR | R | Statement (first sentence, verbatim — the whole rule is in `02-business-rules.md`) | Status |
|---|---|---|---|
| `BR-FLD-00010` | R10 | Every status change is stamped with who and when, and is readable on the job | CONFIRMED (PO) |
| `BR-FLD-00035` | R35 | No database id is ever a visible value. | CONFIRMED — repo rule |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | FF-31 Activity | *Raised 17 Oct 14:22 J. Okafor* … *Pushed to the phone 07:12* … *Accepted 07:48* … *Departed 08:00* … *Arrived 08:14 · 30.2651, -97.7494 · ±4m* … *Safety checks passed 08:44* … *Work started 08:46* … *M. Chen joined 08:46* … *Step 3 done 09:38* |
| TC-2 | FF-30 Notes | Dispatch's note of 07:12 and three on-site notes, each with its author |
| TC-3 · **negative** | A database id on either screen | Never — WO-4822 is the identifier (R35) |
| TC-4 · **tenant isolation** | R. Patel works for Silver Creek Water and Lone Star Water and signs in to Lone Star Water on the same handset | Only `field-lone-star-water.sqlite` is opened; not one Silver Creek row is readable (R131), and the server takes the tenant from the credential, never from the payload (R127) |

**4 · Test Data** — Activity of WO-4822, nine events; notes by J. Okafor, D. Ortiz, M. Chen.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| event | FF-31 | R10 | handset `activity` kind=status | kind + time + who | system-derived | append only |

**6 · Acceptance** — **Given** a job with changes, **when** anyone opens Activity, **then** every change is listed with who and when.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---

---
id: US-FLD-031
epic: EP-FLD-05
module: field-app
screens: [FF-29]
wave: 6
status: ready
blocked_by: []
depends_on: [US-FLD-020]
journeys: []           # the E2E-nn cases cited in §3 become journeys under 08-qa/01-e2e/journeys/ (sibling lane)
rules: [BR-FLD-00008]
golden_tests: []
finance_calc: none
---
### US-FLD-031 — A second technician on the job, with their own time

**Requirement 31, in the design's words:** *A second technician on the job, with their own time* — section E · From the walkthrough of the drawings · standing *New*.

**1 · Details** — As **Dana**, I want **to add Marco to the job at 11:20**, so that **his 90 minutes are his own**.

**Screens (build from the images — B14 rules 42, 44, 45):** `FF-29` Crew — [phone](../wireframes/phone/FF-29-crew.png) · [tablet](../wireframes/tablet/FF-29-T-crew.png)

**2 · Business Rules**

| BR | R | Statement (first sentence, verbatim — the whole rule is in `02-business-rules.md`) | Status |
|---|---|---|---|
| `BR-FLD-00008` | R8 | Labour is per person, not per job. | CONFIRMED (PO) |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | E2E-20: Dana adds Marco at 11:20; he records 90 minutes; she closes | Two labour records; cost is the sum; Dana closes |
| TC-2 · **negative** | Marco's time recorded under Dana | Not possible — crew_time is per person |
| TC-3 | *Add a technician* | Picks from the technicians on the roster |
| TC-4 · **tenant isolation** | R. Patel works for Silver Creek Water and Lone Star Water and signs in to Lone Star Water on the same handset | Only `field-lone-star-water.sqlite` is opened; not one Silver Creek row is readable (R131), and the server takes the tenant from the credential, never from the payload (R127) |

**4 · Test Data** — Marco added 11:20, 90 minutes.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| crew member | FF-29 | requirement 31 | outbox `crew_add` → server | technician | user-input | lead adds |

**6 · Acceptance** — **Given** a lead technician, **when** they add a second technician, **then** the second technician records their own time.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---

---
id: US-FLD-073
epic: EP-FLD-05
module: field-app
screens: [FF-60]
wave: 6
status: ready
blocked_by: []
depends_on: [US-FLD-027]
journeys: []           # the E2E-nn cases cited in §3 become journeys under 08-qa/01-e2e/journeys/ (sibling lane)
rules: [BR-FLD-00108, BR-FLD-00109]
golden_tests: []
finance_calc: none
---
### US-FLD-073 — Asset papers for a new asset — camera, file or typed, travelling with the job

**Requirement 73, in the design's words:** *Documents about a newly installed asset are attached in the field — a certificate, a permit, an inspection sheet, a seal number. They may come from the camera, from a file, or be typed, and the source is recorded on each one. They travel with the job; the office files them against the asset on acceptance* — section K · The seven asks of 2026-10-20 · standing *Ruled*.

**1 · Details** — As **Dana fitting MTR-0903 at 1318 Maple, Unit 3**, I want **to attach the serial plate photo, the permit PDF and the seal number**, so that **the office files them against the meter**. Where each came from is recorded (R108); they attach to the work order, never the asset (R109).

**Screens (build from the images — B14 rules 42, 44, 45):** `FF-60` Asset papers — [phone](../wireframes/phone/FF-60-asset-papers.png) · [tablet](../wireframes/tablet/FF-60-T-asset-papers.png)

**2 · Business Rules**

| BR | R | Statement (first sentence, verbatim — the whole rule is in `02-business-rules.md`) | Status |
|---|---|---|---|
| `BR-FLD-00108` | R108 | A document may come from anywhere; where it came from is recorded. | CONFIRMED (PO) |
| `BR-FLD-00109` | R109 | A document about an asset attaches to the WORK ORDER, never to the asset. | CONFIRMED — repo `BR-WRK-002` |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Attach *Serial plate* (camera), *Plumbing permit* (file, PDF 2 pages), *Factory seal number NT-88-412977* (typed) | *Done — 3 attached*, each with its source |
| TC-2 · **negative** | Attach a task photograph from a file | Not allowed — task evidence stays camera-only (R93); only papers may come from a file |
| TC-3 | The office accepts the job | The office files the three against MTR-0903 (R109) |
| TC-4 · **tenant isolation** | R. Patel works for Silver Creek Water and Lone Star Water and signs in to Lone Star Water on the same handset | Only `field-lone-star-water.sqlite` is opened; not one Silver Creek row is readable (R131), and the server takes the tenant from the credential, never from the payload (R127) |

**4 · Test Data** — MTR-0903 5/8" Neptune fitted 20 Oct 11:04; plate 280 KB; permit 410 KB.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| asset document | FF-60 | requirement 81 | handset `document` owner_kind=work_order (asset_document) | file + source | user-input | camera · file · typed |

**6 · Acceptance** — **Given** a newly installed asset, **when** the technician attaches papers, **then** they travel with the order, each with its source.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---

---
id: US-FLD-075
epic: EP-FLD-05
module: field-app
screens: [FF-61]
wave: 6
status: ready
blocked_by: []
depends_on: [US-FLD-025]
journeys: []           # the E2E-nn cases cited in §3 become journeys under 08-qa/01-e2e/journeys/ (sibling lane)
rules: [BR-FLD-00111, BR-FLD-00017]
golden_tests: []
finance_calc: none
---
### US-FLD-075 — A reconnect checks the reconnect fee as its own question, beside the arrears

**Requirement 75, in the design's words:** *A reconnect checks the reconnect FEE as its own question, beside the arrears. A customer can clear their balance and still not have paid the fee — a single balance would read $0.00 and say nothing. Same five-minute freshness and same warn-never-block as a disconnect* — section K · The seven asks of 2026-10-20 · standing *New*.

**1 · Details** — As **Dana at 95 Cedar Court**, I want **arrears and the reconnect fee shown as two things**, so that **a cleared balance with an unpaid fee is not read as $0.00**. Same five-minute freshness and warn-never-block as a disconnect (R111, R17).

**Screens (build from the images — B14 rules 42, 44, 45):** `FF-61` Reconnect — [phone](../wireframes/phone/FF-61-reconnect.png) · [tablet](../wireframes/tablet/FF-61-T-reconnect.png)

**2 · Business Rules**

| BR | R | Statement (first sentence, verbatim — the whole rule is in `02-business-rules.md`) | Status |
|---|---|---|---|
| `BR-FLD-00111` | R111 | A reconnect fee is its own question, asked beside the arrears. | DERIVED (decision log T-05) |
| `BR-FLD-00017` | R17 | Money older than 5 minutes is warned, never blocked. | CONFIRMED (PO) |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Priya Raghunathan ACC-10377: arrears was $312.40, paid 09:40; fee $45.00 charged 18 Oct, not paid | *Two things, not one*: arrears $0.00, fee $45.00 unpaid |
| TC-2 | *Reconnect anyway* | Recorded as reconnected with the fee outstanding |
| TC-3 · **negative** | Both figures read over 5 minutes ago | Warned with *Check now*; never blocked |
| TC-4 · **tenant isolation** | R. Patel works for Silver Creek Water and Lone Star Water and signs in to Lone Star Water on the same handset | Only `field-lone-star-water.sqlite` is opened; not one Silver Creek row is readable (R131), and the server takes the tenant from the credential, never from the payload (R127) |

**4 · Test Data** — ACC-10377 · 95 Cedar Court · $312.40 paid · fee $45.00.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| arrears / fee | FF-61 | R111 | payments seam read | money 2 dp | integration | each with its as-at |

**6 · Acceptance** — **Given** a reconnect where the arrears are cleared and the fee is not, **when** the technician opens the check, **then** both are shown separately, and they can still proceed.

**7 · Finance Calculation** — N/A. The field app reads money and never writes it (R16).

**8 · Open Questions** — None.
