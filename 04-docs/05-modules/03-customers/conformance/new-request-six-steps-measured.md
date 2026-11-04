# The New request wizard and everything a request becomes — measured against the drawing

**Measured at:** `v2.277.0` · commit `4efac92a` · 2026-09-15
**Benchmark:** `05-prototype/02 Accounts Menu Blueprint.pdf`, entry **06 Service request
capture**, **pages 75–86**, read **AS PAGE IMAGES at scale 2** (B14 rule 42).
PO ruling of this date, verbatim: ***"document screens are benchmark"*** — where the
product and the drawing differ, the drawing is right and the product is the finding.
**Nothing was built. Nothing was fixed. Nothing was submitted, saved or approved.**

⚠ **STEPS 1 AND 3 WERE BUILT ON 2026-09-19 AND THIS MEASUREMENT IS NOW THE RECORD OF
WHAT THEY WERE, NOT OF WHAT THEY ARE.** The tables below are LEFT AS MEASURED — rewriting
a dated measurement destroys the only evidence of the gap it found. What those two steps
do now, and the nine places the product deliberately parts from the drawing with its
reason, is
`04-docs/05-modules/03-customers/conformance/CR-094-BRC01-capture-steps-1-and-3.md`.
Steps 2, 4, 5 and 6 below are current.

---

## 0 · Scope, and what is OUT

**IN.** Blueprint entry 06 in full — its index says **11 drawings** and eleven is what
was read:

| # | drawing | page | the product |
|---|---|---|---|
| 1–6 | the six capture steps `?step=1…6` | p75–p81 | `ServiceRequestCapturePage.tsx` |
| 7 | where a captured request lands — the register's Requests tab | p81–p82 | `AccountsListPage` tab `requests` → `ServiceRequestsListPage.tsx` (embedded), and the standalone `/:tenant/requests` |
| 8 | the request's own screen at a request number | p82–p83 | `ServiceRequestDetailPage.tsx` |
| 9 | **Approve** the request, and what it creates | p83–p84 | the Decision tab's `Approve` |
| 10 | **Refuse** the request — terminal, and reopenable | p84–p85 | the Refuse modal |
| 11 | **Ask for more** — the state that is not a refusal | p85–p86 | a lifecycle button |

plus p86's metadata table for the entry (doors, primary action, write surfaces, rules).

**OUT, deliberately.**

* **`ServiceRequestInterruption.tsx` belongs to a different entry.** Its own trace says
  `US-CWP-008 (EP-CWP-03)` — it is the customer-portal outage section that renders on a
  request whose `problem_kind` is set (`CR-072`), not on an application. It is not drawn
  anywhere in entry 06.
* **`ServiceRequestDocumentSettingsPage.tsx` belongs to Settings.** Its trace says
  `CR-030 W4 task 4.13, Form definitions (Settings → Configure)`, and it is the tenant
  checklist that capture step 4's own sentence points at. Also not drawn in entry 06.
* **The other five job queues** — New connects, Move-ins, Move-outs, Transfers,
  Disconnects — are entries 04, 07, 08, 11 and 12 of the same blueprint. Entry 06 says
  what a request BECOMES; measuring what those tabs then do is another measurement.
* **The customer portal's own request screens** (`portal/requests/`) are `CR-068`'s.
* **Phone width.** Every reading below is at **1280**, the width the blueprint itself is
  drawn at. These are staff screens; no portal page is in scope.

**Say so if that boundary is wrong.**

---

## 1 · Which surfaces were actually DRIVEN, and which were only read

| surface | how it was measured |
|---|---|
| the six capture steps | **DRIVEN** — Chromium at 1280 against a real Django + PostgreSQL stack, signed in as the `brazosbend` owner. Each step reached by its own URL. |
| the Requests tab, both copies | **DRIVEN**, with real seeded rows |
| the request's screen, all six tabs | **DRIVEN**, on four requests in four different states |
| the **Refuse** dialog | **DRIVEN** — opened and closed; nothing submitted |
| the **Park** and **Collect** dialogs | read in code; Park opened |
| **Approve**, **Ask for more**, **Reopen** | **READ, NOT PRESSED.** Pressing them writes to a shared demo tenant, and this lane was told to read and never write. The verdicts below come from the component, the endpoint and the server's own `actions.available`, which was read off each request. **Reopen-after-refuse is verified in the state machine and was NOT seen on a screen**, because no refused request exists on the tenant. |
| the write path | **READ.** No `POST`, `PATCH` or `PUT` was issued by this lane. |

**The drive is in the tree, not in this sentence:**
`10-scripts/cr094_new_request_six_steps_walkthrough.mjs`. It records a per-screen census
(every visible control with its label and its required flag, every button with its
disabled state and title, every table's headers and row count, the H1 and its computed
font size, and the full rendered text) plus one PNG per screen. Re-run it with
`BASE=<your spa>`.

⚠ **ONE CONSEQUENCE OF READ-ONLY, STATED SO NOBODY READS THE TABLE AS MORE THAN IT IS.**
The wizard PATCHes on every forward move, so walking it by pressing Continue would have
written a draft. Steps were therefore reached by URL, which means steps 5 and 6 were seen
**with no saved draft**: step 5 renders its no-draft sentence instead of a quote, and
step 6's review renders `Not supplied` in every row. What that CAN answer — and what the
table below uses it for — is **which controls and which labels exist**. Where a verdict
needed a saved request, it was taken from a seeded one on the detail screen instead.

---

## 2 · THE TABLE — the capture wizard, six steps

One row per action or field. **Front end** and **Back end** each read Built · Partial ·
Missing. A row marked **PRODUCT ONLY** is something the product has and the drawing does
not.

### Step 1 · Customer — drawn p75–p76, title *"Who is this request for?"*

| Step | What the drawing asks for | Front end | Back end |
|---|---|---|---|
| 1 | Page head: `← Requests`, kicker `NEW REQUEST`, title *Who is this request for?*, sub-line `Step 1 of 6 · Customer` | **Built** — all four, title measured 32px | n/a |
| 1 | Top-right button `Save & exit` | **Partial** — the button is there and reads **`Save as draft`**; it saves and does not exit | **Built** — `POST /service-requests` |
| 1 | Six-step rail: Customer · Connection · Addresses & property · Documents · Fees · Check & submit | **Built** — same six, same words, same order | n/a |
| 1 | `Channel *` — a dropdown | **Partial** — the control is built and reads *How did this reach us?*; it carries **no asterisk**, because it is pre-filled and cannot be empty | **Built** — `channel` |
| 1 | `Full name *` | **Built** (optional only on a staff-raised request, which is the server's own rule) | **Built** — `applicant_name` |
| 1 | `Email` | **Built** | **Built** — `applicant_email` |
| 1 | `Phone` | **Built** | **Built** — `applicant_phone` |
| 1 | `Date of birth`, placeholder *if known* | **Missing** — the screen states the absence instead: ***"A date of birth is not recorded on a request yet."*** | **Missing** — the capture endpoint refuses `dob` and `date_of_birth` **by name** |
| 1 | `Driver's licence` | **Missing** — stated on screen: ***"We do not hold a driving licence number for this applicant — not even the last four digits. It is not captured anywhere yet."*** | **Missing** — `gov_id` and eleven other names refused by name |
| 1 | `SSN` | **Built** — an input, with *"Stored encrypted and shown to staff as the last four digits only."* | **Built** — encrypted column; the read path serves only the last four |
| 1 | Checkbox `Add a co-applicant` | **Built**, and reveals name / email / phone | **Built** — three `co_applicant_*` fields |
| 1 | — | **PRODUCT ONLY: `Customer category *`, eight chips** (Residential · Commercial · Industrial · Agricultural · Institutional · Municipal · Builder or developer, plus a disabled **Government**). Nowhere in the drawing on this step; **the drawing puts Category on step 2**. Moved here by PO ruling 2026-08-25. It is the only thing on step 1 that blocks Continue. | **Built** — its own endpoint |
| 1 | — | **PRODUCT ONLY: a `Co-applicant` heading, an `Optional · contact only` pill and a two-sentence explanation.** The drawing has a bare checkbox. | n/a |
| 1 | — | **PRODUCT ONLY: a `Capturing for a customer` banner** under the head. Not drawn. | n/a |

### Step 2 · Connection — drawn p76–p77, title *"What are they asking for?"*

| Step | What the drawing asks for | Front end | Back end |
|---|---|---|---|
| 2 | `Category *` | **Moved, by ruling** — it is on step 1 (PO 2026-08-25). Not a defect; the drawing is behind the ruling. | **Built** |
| 2 | `Sub-category` | **Built** | **Built** |
| 2 | `Which services does this property need? *` — **a multiselect** reading *3 of 11 selected* with removable chips beneath it | **Partial** — the services ARE pickable, as a grid of one card per enabled service, not as a multiselect with chips. On `brazosbend` two services are enabled, so two cards show. | **Built** — a replace-the-set endpoint |
| 2 | Table `When each one is wanted` — `SERVICE` / `REQUESTED START`, one row per picked service | **Missing** | **Missing** — the request carries ONE date for the whole job |
| 2 | `Connection date`, *if known* | **Built** | **Built** — `requested_start` |

### Step 3 · Addresses & property — drawn p77, title *"Addresses"*

| Step | What the drawing asks for | Front end | Back end |
|---|---|---|---|
| 3 | `Street address or premise *` | **Built** — one line, labelled *Address* | **Built** — kept verbatim, never overwritten |
| 3 | `Unit, flat or suite` | **Built** | **Built** |
| 3 | `City *` | **Missing** | **Missing** — no column |
| 3 | `State *` | **Missing** | **Missing** — no column |
| 3 | `ZIP code *` | **Missing** | **Missing** — no column |
| 3 | `How many units are on this property? *`, help *"What the applicant says is there"* | **Missing** | **Missing** — the drawing's own note says the number today *"lives only in whatever the clerk typed into the notes, which no screen and no rule can read"* |
| 3 | Checkbox `Billing address same as service`, and the box it reveals | **Built** | **Built** |
| 3 | Table `What the register matched` — `LOOKED FOR` / `MATCHED` / `CONFIDENCE` | **Missing** on this step. The match IS made and stored — step 6 shows one line of it, and the request's own screen shows more. | **Built** — the resolver writes the evidence |
| 3 | `Plot or parcel` — drawn as **gone**, *"— not asked on this wizard"* | **PRODUCT ONLY, conditionally** — it reappears, with *What is being built*, when the address resolves to nothing on record | **Built** — the column was kept |
| 3 | — | **PRODUCT ONLY: `Property details`, six radios** (Standalone · owner occupied / Rental · tenant applying / Rental · landlord applying / Multi-unit building / Under construction / Vacant land), each with its own explanation. Not drawn. | **Built** |

### Step 4 · Documents — drawn p78, title *"Documents"*

| Step | What the drawing asks for | Front end | Back end |
|---|---|---|---|
| 4 | Sentence: a missing document never blocks the request | **Built**, in the product's own words | n/a |
| 4 | Table `DOCUMENT` / `REQUIRED` / `FILE` / `UPLOADED BY` / `STATE` | **Missing** — the step is a flat checkbox list of nine document types, each with a line saying what it proves | **Partial** — the rows exist and carry a type, a state and who attached them; the request's own screen renders them as a table |
| 4 | Filter chips `All · Required · Missing · Rejected` | **Missing** | n/a |
| 4 | Button `Attach a file` | **Drawn and disabled, with its reason on screen:** ***"We cannot take a file yet — there is nowhere to store it. Tick what the applicant brought and hand the paperwork on the usual way; the request records what is expected."*** | ⚠ **THE BACKEND HALF LANDED 2026-09-19 AND THIS ROW SAID *"Missing — no route in this product accepts a file for a request"* UNTIL THEN.** That was true and is not. `POST /service-requests/{id}/documents` takes a `file` part, stores the bytes through tenancy's document store and writes `name`, `size`, `storage_ref`, `uploaded_by` and `uploaded_at`; `GET …/documents/{docId}/download` mints a four-hour link. PO ruling: *"you will have to reduce the size and save them on cloud container etc"*. **WHAT IS STILL MISSING IS THE CONTROL, AND ONLY THE CONTROL** — the button is still disabled and still renders `customers.serviceRequest.capture.noFileUpload`, whose words are now out of date. `ServiceRequestCapturePage.tsx` was owned by another lane on the day the door was built and was deliberately not touched. **This is hard-won law 2's mirror exactly (DEF-CWP-3925): a live path behind a dead control**, so the next lane on step 4 releases the button and retires that key rather than re-deriving whether a route exists. |
| 4 | Button `Add another document` | **Missing** | n/a |
| 4 | `Attaching one`: `Document type *`, `File *`, `What it proves`, checkbox `Required on this request` | **Missing** — the type is a tick, *what it proves* is read-only text, and nothing marks a document required on THIS request | **Partial** — required-ness is a tenant-wide checklist (Settings), not per request |
| 4 | — | **PRODUCT ONLY:** *"Which of these your utility insists on is set in Settings, and nothing is compulsory until somebody ticks it there."* | **Built** |

### Step 5 · Fees — drawn p79, title *"Fees"*

| Step | What the drawing asks for | Front end | Back end |
|---|---|---|---|
| 5 | Table `What this request is quoted` — `CHARGE` / `DESCRIPTION` / `BASIS` / `QTY` / `UNIT` / `AMOUNT`, and a bold `Quoted` total | **Missing** on this step — only the total shows. The line table exists on the request's own Fees tab. | **Built** — the lines are served |
| 5 | Buttons `Add a fee` and `Waive a line` | **Missing** on this step. Waive exists on the request's Fees tab. | **Built** (waive) · **Built** (raise) |
| 5 | `Fee timing *` — Collect now / Collect later | **Built** | **Built** |
| 5 | `Method *` — Cash / Card / Cheque | **Partial** — shown only when *Collect now* is chosen | **Built** |
| 5 | `Amount taken *`, *"A part payment is accepted."* | **Missing** on this step — it is on the request's Fees tab, behind *Record what was handed over* | **Built** |
| 5 | `Receipt number *` | **Missing** on this step — same dialog | **Built** |
| 5 | `Payment summary` card — Quoted / Settled by an invoice / Collected at the counter / **Outstanding** | **Partial** — Quoted and Outstanding render as two plain fields once a draft exists; there is no summary block and no collected line | **Built** — the arithmetic is served |
| 5 | Note: this takes money and posts nothing | **Built** — *"These fees are a quote. Nothing here is recorded, and nothing here is in the books."* | **Built** |
| 5 | — | **PRODUCT ONLY: a `Due by` date** on Collect later. Not drawn. | **Built** |

### Step 6 · Check & submit — drawn p79–p81, title *"Check and submit"*

| Step | What the drawing asks for | Front end | Back end |
|---|---|---|---|
| 6 | **Each review block links back to the step that captured it** | **Built for every block that exists** — `Edit step 1`, `Edit step 2`, `Edit step 3`, each returning to that step | n/a |
| 6 | Block `The applicant` ✎ Step 1 — Channel, Full name, Email, Phone, Date of birth, Driver's licence, SSN | **Partial** — four of seven: Full name, Email, Phone, SSN (masked). Channel, date of birth and licence are absent. | **Built** for the four |
| 6 | Block `What they are asking for` ✎ Step 2 — Category, Sub-category, Services, Requested start, Connection date | **Partial** — two of five: Category and Services | **Built** for the two |
| 6 | Block `Addresses and property` ✎ Step 3 — Street, Unit, City, State, ZIP, Units on the property, Billing address, Matched premises, Matched unit, Plot or parcel | **Partial** — five of ten, and two of the five are not drawn here: Address, Unit, Plot or parcel, What is being built, What the lookup found | **Partial** |
| 6 | Block `Documents` ✎ Step 4 — a table plus *"Two required documents are not yet cleared."* | **Missing** | **Built** — the data is served |
| 6 | Block `Fees` ✎ Step 5 — Quoted / Fee timing / Taken / Settled by an invoice / Outstanding | **Missing** | **Built** |
| 6 | Block `On submit` ✎ Step 6 — Request number · already allocated, State `Draft → Submitted`, Waiting on | **Missing** as a block. The footer states the equivalent while unsaved: ***"Not saved yet — we need the name and the address before this becomes a request with a number"*** | **Built** — a draft is numbered at creation |
| 6 | Table `What goes out to the applicant` — `SEND` / `WHAT IT SAYS` / `TO` / `CHANNEL` / `TEMPLATE` / `WHEN`, five rows with tick-boxes | **Missing** | **Missing** — see the acknowledgement absence in §5 |
| 6 | `Choosing a template` — a search box and a `TEMPLATE` / `GROUP` / `CHANNEL` / `VARIANT` / `VERSION` table with a radio per row | **Missing** | **Missing** |
| 6 | Footer `← Back` · `Save as draft` · `Submit request ✓` | **Partial** — Back and **`Submit the request ✓`** are in the footer; Save as draft is in the page head, not the footer | **Built** — submit is idempotent |
| 6 | — | **PRODUCT ONLY:** *"N field(s) left blank. None of them stop the request being created."* | n/a |

---

## 3 · THE TABLE — after submission: view and processing

Same columns; the step column becomes the **screen**.

### Screen 7 · Where a captured request lands — the register's Requests tab, drawn p81–p82

| Screen | What the drawing asks for | Front end | Back end |
|---|---|---|---|
| Requests tab | Ten tabs, Requests among them: Accounts · Requests · New connects · Move-ins · Move-outs · Transfers · Disconnects · Complaints · Services · Imports | **Built** — the same ten, in the same order | n/a |
| Requests tab | Page head: kicker `ACCOUNTS`, title **`The register`**, sub-line *"10 tabs · Requests is one of them"* | **Partial** — the page is headed `Accounts` and carries no sub-line. (The standalone `/requests` copy is headed `Requests.`) | n/a |
| Requests tab | Top-right `+ New request` | **Built** | n/a |
| Requests tab | Five tiles: `OPEN` · `WAITING ON SOMEONE` · `APPROVED, NOT STARTED` · `REFUSED THIS MONTH` · `OLDEST OPEN` | **Built, two renamed and one reordered** — `OPEN` · `WAITING ON CUSTOMER` · `OLDEST WAITING` · `APPROVED, NOT STARTED` · `REFUSED THIS MONTH`. Same five facts. | **Built** |
| Requests tab | Filter chips `Open · Waiting · Approved · Closed · All`, plus `Filter ▾` | **Partial** — `All`, a removable `Show: Open ×` chip and a `+ Filter` group. The four named state chips are not there; the same filtering is reachable through `+ Filter`. | **Built** |
| Requests tab | Search *"by request #, applicant, address or meter"* | **Partial** — *"Search request #, name, address, phone, or email…"*. Phone and email are searched and a **meter is not**. | **Partial** |
| Requests tab | Columns `REQUEST #` · `TYPE` · `APPLICANT` · `ADDRESS` · `RECEIVED` · `CHANNEL` · `AGE` · `WAITING ON` · `STATE` | **Built — all nine, in the drawn order**, plus an `ACTIONS` column | **Built** |
| Requests tab | A row action `↗ Open` | **Built**, as an icon rather than a labelled button | n/a |
| Requests tab | `Columns ▾` | **Missing** | n/a |
| Requests tab | `⇩ Export` | **Missing**, and the screen's own file states the absence and its reason: no `service_requests` export resource exists | **Missing** |
| Requests tab | Pagination `1–5 of 5 · Rows per page 50 / 100 / 200 · ‹ ›` | **Built**, with 500 and 1000 added | **Built** |
| Requests tab | *"Waiting on is not the state"* — the two are different columns | **Built** — measured on the real rows: `SR-26-0008` is *Submitted* waiting on a *scheduled date* while `SR-26-0005` is *Under review* waiting on a *third party* | **Built** |
| Requests tab | Every request carries its **TYPE**, the outcome that feeds the other five queues | **Partial** — the column is there and **all six seeded requests read `NOT YET CLASSIFIED`**, because the type is only set at the decision | **Built** |

### Screen 8 · The request's own screen, drawn p82–p83

| Screen | What the drawing asks for | Front end | Back end |
|---|---|---|---|
| Request | Back `← The register`; crumb Accounts / Requests / SR-… | **Built** | n/a |
| Request | Kicker `REQUEST SR-26-0001 · NEW CONNECTION` | **Built** — falls back to *NOT YET CLASSIFIED* before a decision | **Built** |
| Request | **Title is the applicant**, e.g. `Miller, Sarah` | **Built** — measured `Thompson, R.` at 32px | **Built** |
| Request | Meta line: state · waiting-on · channel · `Received <date>` | **Built** — measured *Submitted · Waiting on scheduled date · Phone · Received 09/15/2026* | **Built** |
| Request | The address on its own line under the meta | **Built** | **Built** |
| Request | Actions `Refuse` · `Ask for more` · `Approve` **in the head** | **Missing from the head.** The head carries `Save & exit`, `Park — waiting on ▾` and `Decide what this is →`. All three drawn actions exist further in — see screens 9–11. *(Already filed 2026-09-13.)* | **Built** |
| Request | Three tabs `Applicant · Documents · History` | **Partial** — six: Applicant · Location & services · Documents · Fees · Decision · History. *(Already an open question, 2026-09-13.)* | n/a |
| Request | `WHAT THEY ASKED FOR` — Type, Sub-category, Services, Requested start, Units on the property | **Partial** — the facts are on the *Location & services* tab, not beside the applicant, and there is no unit count | **Partial** |
| Request | `WHO IS ASKING` — Applying as, Full name, Email, Phone, Channel | **Built** — as `Who is asking`, with more rows than drawn | **Built** |
| Request | `THE ADDRESS THEY GAVE` — As given, **`Matched premises PR-0731 · exact`**, **`Matched unit U-001884 · exact`** | **Partial, and wrong where it is built** — the tab shows `ADDRESS AS GIVEN` and `WHAT THE LOOKUP FOUND` correctly, and shows the match as **`RESOLVED TO 01a0a444-5ad2-7e88-be8a-bdb8aa86c05e`** — a raw database id where the drawing names the premises | **Built** — the match is stored |
| Request | Right column `DOCUMENTS · 4` — `DOCUMENT` / `FILE` / `STATE` | **Built, on its own tab**, as `DOCUMENT` / `WHAT IT PROVES` / `UPLOADED` / `VERIFIED` / `ACTIONS`, with verify and reject actions | **Built** |
| Request | Right column `FEES` — Quoted and taken / Settled by an invoice / Collected / **Outstanding** | **Built, on its own tab**, with a line table and a *Record what was handed over* dialog | **Built** |
| Request | Right column `HISTORY` — `WHEN` / `WHAT` / `WHO` | **Built, on its own tab**, append-only, with a note box | **Built** |
| Request | *"the money does not gate approval and the documents do"* | **Built** — measured on a real request: Approve is disabled with the title *"This cannot be approved yet: Documents verified. Nothing is refused — it simply is not ready."* | **Built** |
| Request | — | **PRODUCT ONLY: `Park — waiting on ▾`**, a dialog recording what is being waited for, a note and a reminder. Not drawn. | **Built** |
| Request | — | **PRODUCT ONLY: a lifecycle row** — `Pick up for review`, `Withdraw`, `Close by hand`, `Mark the answer received`, offered by state. Not drawn. | **Built** |
| Request | — | **PRODUCT ONLY: a `Customer match` block** and a `Record that I searched` control, which states on screen that ***"Nothing matches an applicant to an existing customer automatically."*** | **Partial** |

### Screen 9 · Approve — drawn p83–p84

| Screen | What the drawing asks for | Front end | Back end |
|---|---|---|---|
| Approve | A dialog `Approve SR-26-0001` / *"This creates real service and real charges"* | **Missing** — there is no dialog; the button calls the endpoint | n/a |
| Approve | `WHAT IS THIS REQUEST?` — five radios, each with its consequence: A new connection · A move-in · A move-out · A transfer · A disconnect | **Partial** — the same five choices exist, as buttons on the *Decision* tab in a panel headed *What should this become?*, each with the server's own verdict and, where impossible, its reason (measured: *"A premise record already exists here."*) | **Built** |
| Approve | *"Nothing is preselected, deliberately"* | **Built** — the same sentence, on that panel | **Built** |
| Approve | Table `WHAT APPROVING WILL DO` — five `THEN` / `WHAT` rows | **Missing** | n/a |
| Approve | Row: *"This request becomes Approved and the outcome is recorded against your name"* | **Built** — the server stamps who decided and when | **Built** |
| Approve | Row: **"A build is raised on the New connects tab, naming this request"** | **Missing.** Approving moves the state, writes one event and one audit row, and creates nothing else. | **Missing** |
| Approve | Row: **"The $105.00 still outstanding here travels with it"** | **Missing** | **Missing** |
| Approve | Row: *"The build's own wizard asks for units, services, plans and charges"* | **Missing** — not reachable, because nothing is raised to open | **Missing** |
| Approve | Row: *"No account opens, no meter is fitted, nothing is energised"* | **Built** — true by construction | **Built** |
| Approve | Approval is blocked until every required document is checked | **Built** — the button is disabled and names the blocker | **Built** |
| Approve | Footer `Cancel` / `Approve and raise the build` | **Partial** — a single `Approve`, no cancel step, and no build | **Partial** |
| Approve | The request alone answers *what happened to this application* | **Partial** — the columns exist and an endpoint sets them; **no screen in the product calls it**, so a clerk cannot link an approved request to anything | **Built** (endpoint) |

### Screen 10 · Refuse — drawn p84–p85

| Screen | What the drawing asks for | Front end | Back end |
|---|---|---|---|
| Refuse | A dialog `Refuse SR-26-0001` / *"The applicant is told; the request stays on record"* | **Partial** — a dialog headed *Refuse this request*, with no sub-line | n/a |
| Refuse | `Reason *` — a **select** of five: Not our service area · Documents not provided · Applicant withdrew · Duplicate of another request · Other | **Missing** — one free-text box, *"Why is it being refused?"* | **Partial** — the server accepts a `reason_code` that no screen sets |
| Refuse | `What to tell them` — *"Goes into the refusal letter."* | **Missing** | **Missing** |
| Refuse | Table `WHAT REFUSING WILL DO` — four `THEN` / `WHAT` rows | **Missing** — one sentence stands in its place | n/a |
| Refuse | *"The request becomes Refused, which is terminal"* | **Built** | **Built** |
| Refuse | *"A refusal letter is queued to the applicant"* | **Missing** | **Missing** |
| Refuse | *"The $25.00 already collected stays collected"* | **Built** — nothing in the refusal touches the money | **Built** |
| Refuse | **"It can be reopened, with a reason, from refused or withdrawn and from nowhere else"** | **Built — NOT VERIFIED ON SCREEN.** The state machine allows `reopen` only from refused and withdrawn, the reason is required, and reopening clears the decision columns while the refusal stays on the append-only timeline. No refused request exists on the tenant, so the button was never seen. | **Built** |
| Refuse | A reason is required | **Built** | **Built** |
| Refuse | Footer `Cancel` / `Refuse the request` | **Partial** — `Cancel` / `Refuse` | n/a |

### Screen 11 · Ask for more — drawn p85–p86

| Screen | What the drawing asks for | Front end | Back end |
|---|---|---|---|
| Ask for more | A dialog `Ask SR-26-0001 for more` / *"It stays open and stops waiting on you"* | **Missing** — no dialog; it is a button in the lifecycle row | n/a |
| Ask for more | `WHAT IS NEEDED` — a tick-list (a readable site plan · proof of identity checked · a connection date · something else) | **Missing** | **Missing** |
| Ask for more | `Message to the applicant`, *"Sent to them and kept on the request's history."* | **Missing** — the product sends one fixed sentence for every request: *"More information is needed before this can be reviewed."* | **Partial** — a reason is stored on the timeline |
| Ask for more | Table `WHAT THIS WILL DO` — four rows | **Missing** | n/a |
| Ask for more | *"The request becomes More info — open, not refused"* | **Built** — measured: `SR-26-0001` reads **More info needed** on the list | **Built** |
| Ask for more | *"Waiting on changes from documents to the applicant"* | **Partial** — the state moves; the waiting-on column is set by the separate Park control, not by this action | **Partial** |
| Ask for more | *"A message is queued to them"* | **Missing** | **Missing** |
| Ask for more | It is offered only where it applies | **Built** — measured: offered on an under-review request, absent on a submitted one, replaced by *Mark the answer received* on a more-info one | **Built** |

---

## 4 · Counts

**Every count is of the DRAWING's rows**, not of the product's controls, and PRODUCT-ONLY
rows are counted separately.

⚠ **THESE NUMBERS ARE MACHINE-COUNTED OUT OF THE TABLES ABOVE, AND THE FIRST SET WAS
WRONG.** Counted by reading, this section first said `50 / 19 / 11 / 20` for the capture
and `108` for the entry. Parsing the rows gave `48 / 16 / 11 / 21` and `105`, with six of
the eleven sections off by one to three. That is skill §7 happening to the person writing
the skill's own document, so the command is printed here and any reader can re-run it:

```bash
python3 - <<'PY'
import re
txt = open('04-docs/05-modules/03-customers/conformance/new-request-six-steps-measured.md').read()
total = {'Built': 0, 'Partial': 0, 'Missing': 0, 'product': 0}
for sec in re.split(r'\n### ', txt)[1:]:
    head = sec.split('\n', 1)[0]
    # a section ENDS at the next '## ' heading, or §4's own table is counted twice
    sec = re.split(r'\n## ', sec)[0]
    if head.startswith(('Filed', 'Already')):
        continue
    n = {'Built': 0, 'Partial': 0, 'Missing': 0, 'product': 0}
    for line in sec.split('\n'):
        if not line.startswith('| ') or '---|' in line:
            continue
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        if len(cells) < 4 or re.match(r'^(Step|Screen)$', cells[0]):
            continue
        what, fe = cells[1], cells[2]
        if what == '—' or 'PRODUCT ONLY' in fe:
            n['product'] += 1
        elif fe.startswith('**Built'):
            n['Built'] += 1
        # a control that is drawn and REFUSES is present and does not work: Partial
        elif fe.startswith(('**Partial', '**Moved', '**Drawn and disabled')):
            n['Partial'] += 1
        elif fe.startswith('**Missing'):
            n['Missing'] += 1
        else:
            print('   UNCLASSIFIED:', head[:20], '|', what[:40], '|', fe[:40])
    for k in total:
        total[k] += n[k]
    drawn = n['Built'] + n['Partial'] + n['Missing']
    print(f"{head[:44]:46s} drawn={drawn:3d} built={n['Built']:3d} "
          f"partial={n['Partial']:3d} missing={n['Missing']:3d} productonly={n['product']}")
print('TOTAL drawn=', total['Built'] + total['Partial'] + total['Missing'], total)
PY
```

| step / screen | drawn rows | Built | Partial | Missing | product-only |
|---|---|---|---|---|---|
| 1 · Customer | 11 | 7 | 2 | 2 | 3 |
| 2 · Connection | 5 | 2 | 2 | 1 | 0 |
| 3 · Addresses | 8 | 3 | 0 | 5 | 2 |
| 4 · Documents | 6 | 1 | 1 | 4 | 1 |
| 5 · Fees | 8 | 2 | 2 | 4 | 1 |
| 6 · Check & submit | 10 | 1 | 4 | 5 | 1 |
| **capture, all six** | **48** | **16** | **11** | **21** | **8** |
| 7 · Requests tab | 13 | 7 | 4 | 2 | 0 |
| 8 · The request | 14 | 10 | 3 | 1 | 3 |
| 9 · Approve | 12 | 4 | 3 | 5 | 0 |
| 10 · Refuse | 10 | 4 | 2 | 4 | 0 |
| 11 · Ask for more | 8 | 2 | 1 | 5 | 0 |
| **after submission** | **57** | **27** | **13** | **17** | **3** |
| **ENTRY 06, ALL ELEVEN** | **105** | **43** | **24** | **38** | **11** |

⚠ **`105` IS A COUNT OF THE ROWS IN THIS DOCUMENT'S TABLES, WHICH IS A COUNT OF WHAT ONE
READER SAW IN ELEVEN DRAWINGS.** It is not a count of anything the blueprint itself
states. Where the drawing groups five boxes under one heading, this document may split
them into five rows or keep them as one; the counts move with that choice and the
findings do not. Read the tables, not the total.

The per-screen control counts come from the walkthrough, which prints its own command:
`document.querySelectorAll("input,select,textarea")` and `…("button,a[role='button']")`
over each rendered screen, with each control's `<label for>` resolved.

---

## 5 · Every absence the product STATES on screen, and whether it is still true

| where | the sentence, verbatim | still true? |
|---|---|---|
| capture step 1 | *"A date of birth is not recorded on a request yet."* | **TRUE** — `date_of_birth` and `dob` are refused by name by the capture endpoint |
| capture step 1 | *"We do not hold a driving licence number for this applicant — not even the last four digits. It is not captured anywhere yet."* | **TRUE** — `gov_id` and eleven sibling names still refused by name |
| capture step 4 | *"We cannot take a file yet — there is nowhere to store it. Tick what the applicant brought and hand the paperwork on the usual way; the request records what is expected."* | ⚠ **NO LONGER TRUE AS OF 2026-09-19 — this cell read `TRUE — no route in this product accepts a file for a request` and there is one now.** The half that is still true is *this screen* cannot take a file: the control is disabled and the door it would call is built, tested and tenant-scoped. **A stated absence that has stopped being absent is the thing this table exists to catch**, so it is corrected here on the day the door landed rather than left for whoever next measures the screen. The sentence itself is unchanged and the key is not retired, because retiring a key with a live call site is a defect of its own — the step 4 lane does both in one commit. |
| capture step 4 | *"Which of these your utility insists on is set in Settings, and nothing is compulsory until somebody ticks it there."* | **TRUE**, and the Settings screen exists and is routed |
| capture step 5 | *"These fees are a quote. Nothing here is recorded, and nothing here is in the books."* | **TRUE** |
| capture step 5 | *"Fees appear once the request is saved."* | **TRUE** — the quote needs a row |
| capture steps 1–6 footer | *"Not saved yet — we need the name and the address before this becomes a request with a number"* | **TRUE** — the server's own minimum |
| request · Applicant tab | *"Whether somebody is applying for themselves or for another person is not recorded on a request yet."* | **TRUE** — `acting_for` is refused by name |
| request · Applicant tab | *"Nothing matches an applicant to an existing customer automatically. Search for them and link them yourself…"* | **TRUE** |
| request · Documents tab | *"Your utility has not marked any document compulsory, so no document is blocking this request."* | **TRUE** on this tenant, and it is the ruled default — a tenant that configures nothing blocks nothing |
| request · Fees tab | *"A quote is raised after review, once you know what work the request actually needs. Nothing is priced yet."* | **TRUE** |
| request · Decision tab | *"This cannot be approved yet: … Nothing is refused — it simply is not ready."* | **TRUE**, and measured live on two requests |
| request · **History** | *"'service_request' is not a source kind this platform queues (invoice, payment, notice, plan, report, ledger, test, bulk_action, move, account, portal, appointment, message). … a row nothing recognises is a message nothing will ever send."* | **TRUE** — the vocabulary is a constant and `service_request` is not in it |
| the API's own refusal catalogue | *"No acknowledgement has been sent to the applicant and none is waiting to be sent. Tell them yourself if they need confirming."* | **TRUE** — and it matters, because p086 says the primary action *"sends the customer an acknowledgement"* and step 6 draws a whole table of five messages |
| the requests list's source file | there is no `Export` on this list because no `service_requests` export resource is registered | **TRUE**, and already carried as an open defect since 2026-08-27 |

**The mirror direction — a refusal still standing over something that now works — was
checked and found in one place, in code rather than on screen:** the capture page carries
a comment saying the category endpoint *"answers 200 the first time and 500 on every call
after it"* and that a clerk changing their mind *"still meets it"*. **That was fixed**;
the audit writer now coerces its own blobs. The comment is stale, the behaviour it
describes is gone, and the code it guards (send the category only when it changes) is the
right shape anyway. Recorded here rather than filed — see §7.

---

## 6 · What was routed, and where

### Filed as defects by this lane

| id | what |
|---|---|
| `DEF-CUS-5385` | Capture step 3 is drawn with five address boxes, a unit count and a match table, and the product has none of the three — on both ends |
| `DEF-CUS-5386` | The request's Location & services tab prints a raw premises UUID as the visible value of *RESOLVED TO*, where the blueprint names the premises |
| `DEF-CUS-5387` | Capture step 6 is drawn as six review blocks and ships three, and the three carry fewer than half the drawn rows |
| `DEF-CUS-5388` | Approving raises no job and opens no confirmation; the endpoint that would link a child is called by no screen |
| `DEF-CUS-5389` | Refuse and Ask for more cannot say why or tell the applicant what is needed |
| `DEF-CUS-5390` | Capture step 5 shows two numbers where the blueprint draws a priced quote, two controls and a payment summary |

### Already filed — cited, not re-filed

| id | status | what |
|---|---|---|
| `DEF-CUS-5194` | OPEN | the request's decision row is drawn `Refuse · Ask for more · Approve` in the head and the product draws none of the three there |
| `DEF-CUS-5195` | OPEN | step 2's eleven-service multiselect and its per-service `REQUESTED START` table |
| `DEF-CUS-5196` | OPEN | step 4's documents table and its four filter chips |
| `DEF-1005` | OPEN | no `Export` on the requests list |
| `OQ-CUS-12357` | OPEN | the record is drawn with three tabs and ships six — do the three fold back in, or does the drawing follow the product? |

**No question was minted.** Every gap above is ours to build or ours to decide, and the
one that looked like a PO question was already ruled: `BR-CUS-090` (PO 2026-08-24) puts
*quoted · collected · outstanding* **on the capture, the detail and the receipt**, with
the worked figures `$130.00 quoted / $25.00 taken / RCP-26-4471 / $105.00 outstanding` —
the same figures the drawing draws on step 5. The drawing and the ruling agree, so step 5
is a defect and not a question.

---

## 7 · What was deliberately NOT filed, and why

* **Sample figures.** `$130.00`, `05/12/2026`, `SR-26-0001`, *3 of 11 selected*, `PR-0731`
  and `6 units` are illustrations, not facts to build to (B14 rule 37). The *shape* they
  illustrate is filed; the numbers are not.
* **`Channel` drawn with an asterisk, built without one.** The control is seeded with a
  value and can never be empty, so an asterisk there would teach a clerk that the mark
  means nothing. The screen's own file records this. Left.
* **`Save & exit` named `Save as draft`.** The control saves a draft and does not exit.
  Renaming it to match the picture would make the screen say something untrue about what
  pressing it does.
* **Customer category on step 1 rather than step 2.** The drawing shows it on step 2; the
  PO moved it on 2026-08-25. The drawing is behind the ruling.
* **The removable `Show: Open ×` chip and `+ Filter` in place of four state chips.** How a
  filter bar is CONSTRUCTED is a product-wide UI decision, and changing it on one screen's
  authority would change every list at once. B14 rule 38's split: the drawing decides what
  the screen contains, the UI rules decide how it is built. Recorded, not filed.
* **A row action as an icon rather than a labelled `↗ Open` button.** Same reason — icons
  for row actions is a UI rule.
* **The register's page head reading `Accounts` rather than `The register`.** That head
  belongs to the Accounts entry of the blueprint, not to entry 06, and changing it on this
  entry's authority would be measuring one screen and editing another.
* **The stale comment about the category endpoint answering 500** (§5). It is a code
  comment, the behaviour is fixed, and the code it guards is correct regardless. Worth one
  line in whichever lane next opens that file; not worth a register row. **I am not
  certain about this one** — a stale comment is exactly the class that outlives its reason
  and misleads the next reader, and a case could be made for filing it.
* **Six tabs against three drawn.** Already an open question; adding a defect would be two
  records of one thing.

---

## 8 · Reds I did not cause

**None found, and the claim is dated rather than asserted.** This lane ran no test suite
and no gate — it read files, drove a browser and appended six register rows. The two
servers it started (Django on `127.0.0.1:8041`, the SPA join on `127.0.0.1:8141`) were
started by this lane on ports it first probed as closed, and both were clean: the backend
logged `System check identified no issues (0 silenced)`, and `vite build` exited 0.
`./10-scripts/check_head_current.sh` was run at the start of the session and again before
filing, and passed both times at `4efac92a`.

---

## 9 · What step 2 should do first, and why that order

1. **`DEF-CUS-5388` — approving creates nothing.** It is the only finding here that
   changes what a clerk can DO rather than what they can see, it is the blueprint's own
   *"spine of the whole document"*, and it has a dead endpoint sitting in the tree waiting
   for it. It also has a question inside it (does approval raise the child, or does a
   clerk raise it afterwards?) that should be settled before anybody builds the other five
   queues against it.
2. **`DEF-CUS-5386` — the UUID on screen.** Smallest fix here, a ratified rule, a fix
   already proved twice elsewhere, and a guard that is four lines away in a walkthrough
   that already exists.
3. **`DEF-CUS-5387` — step 6's missing review rows.** The ROWS are free: every one is
   already in the wizard's own state. Do the rows; leave the notification blocks until
   there is a sender.
4. **`DEF-CUS-5389` — the refusal vocabulary.** The column already exists on the server,
   the five words are on the drawing, and a register of refusals with free-text reasons
   answers no question about why this utility turns people down.
5. **`DEF-CUS-5390` — step 5's quote.** A move rather than a new capability: the lines and
   the waive action already exist on the request's Fees tab.
6. **`DEF-CUS-5385` — step 3.** Last, because the five-box half collides with a signed
   rule about keeping the applicant's address verbatim and must go to the PO with the
   drawing beside it; the unit count and the match table can go earlier if split out.

**Do not start with the notification table on step 6.** It is the largest-looking gap and
it cannot be built at all until `service_request` is a source kind the platform queues —
which is another module's change, and cross-module writes are forbidden.
