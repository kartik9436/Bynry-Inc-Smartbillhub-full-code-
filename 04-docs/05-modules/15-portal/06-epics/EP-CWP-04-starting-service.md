# EP-CWP-04 — Starting service before identity exists

**Module:** portal (+ customers owns the request) · **Wave:** release 1 ·
**Screens:** CWP-008 · CWP-009 · CWP-010 · CWP-047 · **Status:** draft

## Scope

**In:** the one journey that begins before the person is a customer — *can I get service
here*, the price read, the applicant form, the submit where paperless consent is taken,
and the quick asks.

**Out:** collecting the fees (`US-CWP-050`, release 5) and uploading the documents
(deferred by signed decision). ⚠ **The documents half is SUPERSEDED FOR THE NEW-SERVICE
REQUEST, PO 2026-10-01** (`CR-158-BRC10`, `DF-4` superseded there only): the applicant MAY
attach PDF, JPG or PNG files, up to 10 MB each and 5 per application, on step 3 (*About
you*, the proof-of-identity drop the wireframe draws), and they travel with the application
to the clerk. Fees stay out.

⚠ **THIS IS THE ONE GUEST JOURNEY THE PRODUCT IS GENUINELY READY FOR.** A service request
already has a draft state, an applicant identity, a document checklist by request type
and a fee quote. **All of it built, all of it reachable only by a clerk.**

⚠ **AND THEY MAY NEVER BECOME A CUSTOMER IF WE REFUSE THEM.** An unknown address is not a
refusal — it means a person looks at it.

## Capability matrix

| Screen | Search | Filters | Default sort | Sortable | Columns | Row actions | Bulk | Export |
|---|---|---|---|---|---|---|---|---|
| CWP-008 | Address | — | — | — | Service · Available · To connect · Deposit | — | — | — |
| CWP-047 | — | — | — | — | — | — | — | Save and finish later |
| CWP-009 | — | — | — | — | — | — | — | — |
| CWP-010 | — | — | — | — | — | — | — | — |

---
id: US-CWP-012
epic: EP-CWP-04
module: portal
screens: [CWP-008]
wave: 1
status: ready
blocked_by: []
depends_on: []
journeys: [J32]
rules: [BR-CWP-026, BR-CWP-021]
golden_tests: []
finance_calc: confirmed
---
### US-CWP-012 — Can I get service here: availability, fees and deposits, read publicly

**1 · Details** — As **somebody moving in**, I want **to know what I can get at an
address and what it costs**, so that **I do not fill in the wrong form**.

An address box. Then a four-row table — service, available, to connect, deposit — and an
*if you apply* panel: what to pay before we start, what lands on the first bill, and how
long it takes.

⚠ **ANSWERING THIS BEFORE THE FORM IS WHAT STOPS HALF THE APPLICATIONS BEING WRONG.**
Everything on it already exists: premises and the services each carries, connection fees
on the tariff, deposits by account type. **What does not exist is any public read of it.**

⚠ **AND THE PANEL DRAWS A DISTINCTION A VISITOR CANNOT BE EXPECTED TO KNOW:** a new
connection and a move-in are different jobs with different costs. If someone lives there
now, this is a move-in — quicker and cheaper — and the form works that out.

⚠ **AMENDED 2026-10-30 (PO ruling A, verbatim *"A, move-in"*; `DEF-CWP-10690`).** Whether
somebody lives there NO LONGER decides it: an address — and, at a building, the apartment
picked — that is already **in Premises** is a **move-in, occupied or empty**; a new
connection is only an address NOT in Premises (2026-09-23 / 2026-10-11, the rule the staff
Approve window keeps). Worked: `1408 Elm St` · Apt B (empty, beside occupied Apt A) and
`31 Palm Ct` (an empty house) both read move-in. The figures quoted are the move-in's — the
plan's move-in fees for a home (`rating.move_in_fees`, the staff move-in Fees table's read)
— and occupancy is not read for a guest at all.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-CWP-026` | A public read may never change an account | CONFIRMED — blueprint `G10` |
| `BR-CWP-021` | ⚠ Availability names the **services**, never the current occupier | CONFIRMED — blueprint §20 |
| `BR-CWP-093` | An unknown address returns *"a person will look at it"*, **never a refusal** | CONFIRMED — blueprint `G8` |
| Inherited | Money displays to two decimals | CLAUDE.md hard rule 2 |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | `31 Palm Ct, Austin TX 78702` | Four rows — Water **Yes `$185.00`** · Sewer **Yes Included** · Trash **Yes `$0.00`** · Electric **Not here** — and *"$185.00 before we start · $150.00 deposit on your first bill · about three working days"* |
| TC-2 · **negative** | An address matching no premises | *"a person will look at it"* and an *Apply* route. ⚠ **Not a refusal and not an empty table** |
| TC-3 · **negative** | An address where somebody **already** has service | The panel says this is a **move-in**, not a new connection. ⚠ It does **not** name the current occupier. ⊕ **AMENDED 2026-10-30 (PO ruling A, `DEF-CWP-10690`): an address in Premises reads move-in EMPTY too** — `1408 Elm St · B` (empty) and `31 Palm Ct` read move-in; only an address not in Premises is not one (`job` null, *a person will look at it*) |
| TC-4 · **negative** | A service the utility does not carry at that premises | Reads **Not here** with no fee and no deposit — ⚠ not `$0.00`, which means free |
| TC-5 · **tenant isolation** | `31 Palm Ct` submitted on `/oak-ridge` | Oak Ridge's own premises and prices, or *"a person will look at it"*. **Never Pine Hill's fees** |
| TC-6 | A tariff with a fee version dated in the future | The **currently effective** version. A price read must not quote next quarter's fee |

**4 · Test Data** — Premises `31 Palm Ct, Austin TX 78702`: Water available, connection
`$185.00`, deposit `$150.00`; Sewer available, included, no deposit; Trash available,
`$0.00`; Electric **not present**. Occupied premises `1408 Elm St · A` for TC-3. Unknown
`77 Nowhere Ln`.

**5 · Data Fields / Mapping**

| Field | Screen | Source | DB target | Type | Origin | Validation |
|---|---|---|---|---|---|---|
| Address | CWP-008 | prototype-extracted | `premises.address` | text | user-input | Fuzzy; a miss is not a refusal |
| Service available | CWP-008 | prototype-extracted | `service_point` per premises | boolean | reference-data | Per service |
| To connect | CWP-008 | prototype-extracted | connection fee on the effective tariff | numeric(18,4) → 2 | reference-data | ⚠ Effective **today** |
| Deposit | CWP-008 | prototype-extracted | deposit by account type | numeric(18,4) → 2 | reference-data | — |

**6 · Acceptance** — **Given** a visitor with no account, **when** they check `31 Palm
Ct`, **then** they read that Water costs `$185.00` before we start and a `$150.00`
deposit lands on the first bill, that Electric is not there, and — for an address we do
not hold — that a person will look at it.

**7 · Finance Calculation** — To pay before we start = sum of the *before we start* fees
on the effective tariff for the selected services. Worked: `$185.00` (water connection)
`+ $0.00` (trash) `= $185.00`. On the first bill = deposit `$150.00`. **Neither is
charged today.** No new GT — this reads existing tariff arithmetic.

**8 · Open Questions** — None.

---
id: US-CWP-013
epic: EP-CWP-04
module: portal
screens: [CWP-047]
wave: 1
status: ready
blocked_by: []
depends_on: [US-CWP-012]
journeys: [J32]
rules: [BR-CWP-031, BR-CWP-076]
golden_tests: []
finance_calc: none
---
### US-CWP-013 — About you: the applicant, and recognising a returning customer

**1 · Details** — As **an applicant with no account**, I want **a form that survives a
closed tab**, so that **I do not lose twenty minutes of typing**.

Name, person or business, email, mobile, **date of birth**, and the date service should
start — at least three working days out. A draft is saved from the first keystroke and
carries **no reference**, because no promise has been made.

⚠ **THE DATE OF BIRTH IS ASKED HERE AND NOT ON THE ENROLMENT FORM, AND THE DIFFERENCE IS
DELIBERATE.** Here it is used to recognise a returning customer — *a decision a person
makes*. On enrolment it would be a fact anyone can hammer against a public form
(`BR-CWP-031`).

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-CWP-031` | Enrolment must not match on date of birth; **application matching may**, because a person decides | CONFIRMED — blueprint `P2`, `P33` |
| `BR-CWP-076` | The row carries channel `customer_portal` | CONFIRMED — `CP-13` |
| — | A draft holds **no allocated number** until submit | CONFIRMED — blueprint `P33` |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Type two fields and close the tab | Returning to the URL restores them. **No reference has been issued** |
| TC-2 | A date of birth matching an existing customer | Flags a possible returning customer **for a clerk**. ⚠ It does **not** link the records and does **not** tell the applicant |
| TC-3 · **negative** | A start date two working days out | Refused — *"at least three working days from today"* |
| TC-4 · **negative** | A business applicant with no tax ID | Refused; a business is identified by company name and tax ID rather than date of birth |
| TC-5 · **negative** | Submit a draft with the address step incomplete | Refused, naming the step, and the draft is kept |
| TC-6 · **tenant isolation** | A draft started on `/pine-hill` opened under `/oak-ridge` | Not found |
| TC-7 | A returning-customer match | ⚠ The **encrypted, blind-indexed** identity fields are used through the existing matching service — the portal does not read them directly |

**4 · Test Data** — *Daniel Okafor*, a person, `d.okafor@example.com`, `(512) 555-7730`,
born 4 Dec 1987. Start 21 Sep 2026 (today 2 Sep, so 13 working days out). Address `22
Palm Ct`, services Water, Sewer, Trash. Returning-customer seed: a closed account for the
same name and date of birth at `91 Cedar Row`.

**5 · Data Fields / Mapping**

| Field | Screen | Source | DB target | Type | Origin | Validation |
|---|---|---|---|---|---|---|
| First / last name | CWP-047 | prototype-extracted | `service_request.applicant_name` | text | user-input | Required |
| Person or business | CWP-047 | prototype-extracted | `customer.kind` | enum | user-input | Drives which identity fields are asked |
| Email, Mobile | CWP-047 | prototype-extracted | `service_request.applicant_email`, `_phone` | text | user-input | Both required |
| Date of birth | CWP-047 | prototype-extracted | `customer.date_of_birth` | date | user-input | ⚠ **AMENDED 2026-10-02:** a **plain `date`**, neither encrypted nor blind-indexed (`BR-CUS-1020`: *"The date of birth is a plain `date` and deliberately so — it must be COMPARABLE"*). It reaches the clerk as the plain `service_requests.date_of_birth` (`BR-CUS-089`'s middle clause, `DEF-CWP-9046`). This cell read *"Encrypted, blind-indexed"* until today; that is the SSN and licence, not this. **Matching only** |
| Start date | CWP-047 | prototype-extracted | `service_request.requested_start_on` | date | user-input | ≥ 3 working days |
| Draft state | — | A5 | `service_request.status = draft` | enum | system-derived | **No number allocated** |

**6 · Acceptance** — **Given** an applicant halfway through the form, **when** they close
the tab and come back, **then** everything typed is there and no reference has been
issued; **and given** a date of birth matching a closed account, **then** a clerk sees a
possible returning customer and the applicant is told nothing.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---
id: US-CWP-014
epic: EP-CWP-04
module: portal
screens: [CWP-009]
wave: 1
status: ready
blocked_by: []
depends_on: [US-CWP-013]
journeys: [J32, J45]
rules: [BR-CWP-087, BR-CWP-076, BR-CWP-026]
golden_tests: []
finance_calc: confirmed
---
### US-CWP-014 — Check and send, and where paperless consent is taken

**1 · Details** — As **an applicant**, I want **to see what I am agreeing to before I
send it**, so that **I know what will be charged and when**.

A summary — address, applicant, services, start date, to pay before we start, on your
first bill — then the document checklist marked `AFTER YOU APPLY`, then **the paperless
tick**, then a consequence box and the commit.

⚠ **THIS IS THE ONE PLACE PAPERLESS CONSENT IS CAPTURED** (`CR-068` `R5`, `R6`). Existing
customers are **not asked again**, so the connection form is where the agreement is
taken, **with its date and the wording they saw**. A migration that back-fills consent
for existing customers invents a consent nobody gave.

⚠ **TWO THINGS IT DELIBERATELY DOES NOT DO:** it does not take money — fees are collected
after approval, which the record already models — and it does **not ask for documents up
front**. A checklist you cannot yet upload to would stop the application dead. ⚠ **Still
true, and now half of a pair (superseded for new-service request, PO 2026-10-01,
`CR-158-BRC10`):** the applicant MAY attach documents before sending — nothing REQUIRES
one, and Send never waits for a file.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-CWP-087` | Paperless is a recorded consent — timestamp, wording version, and a way to withdraw | CONFIRMED — `CR-068` `R5` |
| `BR-CWP-087` | Existing paperless customers are **not** asked again | CONFIRMED — `CR-068` `R6` |
| Inherited | **Print stays the floor** on bills, receipts, notices and plan letters whatever they pick | CONFIRMED — `CR-068` `R4` |
| `BR-CWP-026` | The form grants nothing by itself — a person judges it | CONFIRMED — blueprint `G9` |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Send the application with the paperless box ticked | A reference is issued, the request appears with channel **Customer portal**, and a `portal_consent` row carries the **wording version** and the timestamp |
| TC-2 | Send it **unticked** | The application succeeds and **no consent row is written**. ⚠ An absent consent is not a withdrawn one |
| TC-3 · **negative** | The copy claims paperless stops paper bills | Fails review — bills, receipts, notices and plan letters are **always printed**; the screen must say *"we print them as well"* |
| TC-4 · **negative** | A consent row dated in the future | Refused by a constraint. ⚠ The blueprint shipped one dated nineteen days after its own *today* and its §26 lists the repair |
| TC-5 · **negative** | Submit twice from a double-click | One request, one reference, one consent row |
| TC-6 · **tenant isolation** | The consent row | Scoped to the tenant and the account; RLS `FORCE` on `portal_consent` |
| TC-7 | The consequence box | Reads *"nothing is charged today"* and *"we answer within two working days"*, and the fee figures match `CWP-008` |

**4 · Test Data** — Address `31 Palm Ct`; applicant *Daniel Okafor*; services Water,
Sewer, Trash; start 21 Sep 2026; to pay before we start `$185.00`; on your first bill
`$150.00` deposit. Checklist: Photo ID and Proof of address, both `AFTER YOU APPLY`.
Wording version `paperless-v1-2026-09`.

**5 · Data Fields / Mapping**

| Field | Screen | Source | DB target | Type | Origin | Validation |
|---|---|---|---|---|---|---|
| Paperless tick | CWP-009 | prototype-extracted | `portal_consent` (kind `paperless`) | row | user-input | ⚠ Writes a **row**, never a boolean on the account |
| Wording version | — | GAP | `portal_consent.wording_version` | text | system-derived | ⚠ **The version they saw.** A consent without it is not a consent |
| Agreed on | — | GAP | `portal_consent.agreed_on` | timestamptz | system | **Never in the future** |
| To pay before we start | CWP-009 | prototype-extracted | quoted fees on the request | numeric(18,4) → 2 | computed-display | Must equal `CWP-008`'s figure |
| Reference | CWP-009 | prototype-extracted | `service_request.reference` | text | system-derived | Allocated **at submit**, not at draft |

**6 · Acceptance** — **Given** an applicant on the final step with paperless ticked,
**when** they send it, **then** a reference is issued, a clerk sees channel *Customer
portal*, a consent row records the wording version and the moment, nothing is charged,
and no document was demanded up front.

**7 · Finance Calculation** — Restates `US-CWP-012`'s arithmetic and must not
recompute it independently: before we start `$185.00`; on the first bill `$150.00`. **A
figure that disagrees with the availability screen is the defect this test exists to
catch.**

**8 · Open Questions** — None. ⚠ `PQ-05`, `PQ-09` and `PQ-10` were all ruled 2026-09-02
and none of them touches this screen.

---
id: US-CWP-015
epic: EP-CWP-04
module: portal
screens: [CWP-010]
wave: 1
status: ready
blocked_by: []
depends_on: [US-CWP-002]
journeys: [J32]
rules: [BR-CWP-026, BR-CWP-076]
golden_tests: []
finance_calc: none
---
### US-CWP-015 — Ask for a quick service

**1 · Details** — As **anyone**, I want **to ask for a small thing without an account**,
so that **I do not queue on the telephone for a re-read**.

Six cards: a reading looks wrong · my collection was missed · I need a copy of a bill ·
my water pressure has dropped · a question about my bill · something else.

⚠ **THE CHEAPEST GUEST WORKFLOW TO BUILD AND THE BEST RATIO OF CALLS SAVED TO WORK
DONE.** Each is the same request record with a different category, and the categories are
**already tenant-configurable**.

⚠ **THE CLOSING NOTE IS THE BOUNDARY:** anything that changes who an account belongs to,
or moves money, needs a sign-in or a phone call. **We cannot take that from a form.**

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-CWP-026` | A form a stranger can fill may create work, never change an account | CONFIRMED — blueprint `G10` |
| `BR-CWP-076` | Channel `customer_portal` on every row | CONFIRMED — `CP-13` |
| `BR-CWP-028` | Ends on a reference | CONFIRMED — blueprint §7 |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | *A meter reading looks wrong*, with an address | A reference, and a clerk sees the tenant's own re-read category |
| TC-2 | *A question about my bill* | Requires the bill number, and the resulting row **names that bill** |
| TC-3 · **negative** | Ask to change the account holder through *Something else* | Accepted as a **request a clerk judges** — and nothing on the account changes. ⚠ Assert the account row is byte-identical afterwards |
| TC-4 · **negative** | A tenant that has switched requests off | The cards are absent **and** `POST /public/requests` refuses |
| TC-5 · **negative** | The 61st ask in a minute | Refused |
| TC-6 · **tenant isolation** | A category configured only by Oak Ridge | Not offered on Pine Hill's form |
| TC-7 | A tenant that has renamed a category | The renamed label appears — the six cards read from the tenant's configuration, not from a hardcoded list |

**4 · Test Data** — Categories as configured for Pine Hill: `re_read`,
`missed_collection`, `copy_of_bill`, `low_pressure`, `bill_question`, `other`. Address
`1408 Elm St, Austin TX 78702`. Bill `BL-2608-0141` for TC-2.

**5 · Data Fields / Mapping**

| Field | Screen | Source | DB target | Type | Origin | Validation |
|---|---|---|---|---|---|---|
| Category | CWP-010 | prototype-extracted | `service_request.category` | FK | reference-data | ⚠ **Tenant-configurable.** Never a hardcoded list |
| Which bill | CWP-010 | prototype-extracted | `service_request.invoice_id` | uuid FK | user-input | Only for `bill_question` |
| Contact | CWP-010 | prototype-extracted | `service_request.reporter_*` | text | user-input | Required |

**6 · Acceptance** — **Given** a visitor with no account, **when** they ask for a
re-read at their address, **then** a reference is issued and a clerk sees it under the
tenant's own category; **and when** they use *something else* to ask for the account to
be put in another name, **then** it becomes a request a person judges and nothing on the
account moves.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.
