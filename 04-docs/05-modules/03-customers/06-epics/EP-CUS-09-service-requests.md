# EP-CUS-09 — The service request: the front door (`REQ-01`, `REQ-02`, `REQ-03`)

**Module:** customers (product name: Accounts) · **Wave:** CR-030 **W4** (`2.45.0`) — *not* B12's W4 · **Screens:** ⛔ **NONE ALLOCATED** — see the box below · **Status:** draft

> ⚠ **THIS EPIC WAS WRITTEN AFTER THE CODE, AND SAYS SO — hard-won law 8, the
> same finding EP-CUS-08 records for S89/S90 one day earlier.** The three request
> screens shipped on **2026-08-24** with both halves built —
> `ServiceRequestCapturePage.tsx` · `ServiceRequestsListPage.tsx` ·
> `ServiceRequestDetailPage.tsx`, twenty-four endpoints under
> `apps/customers/service_request_api.py`, a read model, a lifecycle module and a
> service layer — and **no user story owned any of them.** The journey that walks
> them, `08-qa/01-e2e/journeys/J26-request-to-service.md`, filed the finding
> itself and refused to name stories that did not exist:
>
> > *"`stories: []` IS A FINDING, NOT AN OMISSION — HARD-WON LAW 8. B18 §5.3
> > proposes S83 (the Requests list), S84 (the detail) and S85 (the applicant's
> > form); `05-user-stories.md` stops at US-CUS-023 and NO story owns any of the
> > three. … Naming a story that does not exist would make this journey index as
> > ready on an id nobody can look up."*
>
> B18 task 4.16 turns that into work: *"Three stories are owed."* These are the
> three. **Every acceptance criterion below is RECOVERED FROM WHAT EXISTS** and
> checked against B18 §5.3, B19 §11–§12 and the test that asserts it; where the
> design draws something the code does not do, the row says **NOT BUILT** and
> names what tracks it. Nothing here is an aspiration.
>
> ⚠ **THESE THREE STORY IDS ARE DELIBERATELY NOT YET CITED IN ANY SOURCE FILE'S
> TRACE HEADER, AND THAT IS THE NEXT STEP RATHER THAN AN OVERSIGHT.** G10 keys
> off Trace-header citations: the moment `service_request_reads.py`,
> `service_request_service.py` or `ServiceRequestDetailPage.tsx` names
> `US-CUS-024/025/026`, G10 demands pytest functions called
> `test_us_cus_024_tc*` (and a vitest file mentioning the id) and goes RED
> without them. **The cases exist and are green — they are named for the RULE
> they pin** (`test_br_cus_095_…`, `test_the_seed_…`, `test_the_detail_serves_
> the_category_it_was_given`), which is this module's own convention. So the
> citation and the `test_us_cus_0nn_tc*` aliases land together, in one change,
> **and adding the citation alone would make a failing gate fail wider.** G10 is
> already RED on five older customers stories (`US-CUS-007 · 008 · 021 · 022 ·
> 023`) for the same reason, and this lane did not add to that list.


> ⛔ **NO SCREEN ID IS CLAIMED BY ANY OF THESE THREE STORIES, AND THAT IS
> DELIBERATE.** B18 §5.3 proposes **S83 · S84 · S85** and **B18 §12.2 decision D1
> is UNRULED**: A1's reserved band `S61–S90` is exhausted, this CR needs sixteen
> ids where ten remain, the next free ground is **S115**, and *"allocation is the
> PO's"*. `04-docs/01-spec/01-screen-inventory.md` declares **no S83, S84 or
> S85** today, so every one of the three routes carries `ids: NONE` in
> `07-frontend/src/routing/screenIds.ts` with its reason on the row, and G29's
> first assertion — *every `a1:` id in the map is an id A1 declares* — would
> refuse them. `screen_id_baseline.txt`'s DIS-02 settles the principle: *"an id
> no authority defines is an id nobody can look up when it turns up in a bug
> report."*
>
> So each story below carries **`screens: []`** and names its surface by its
> **`REQ-` design id**, which is what the PO's own prototype draws.
> **`S83`/`S84`/`S85` remain the TICKET vocabulary** in B18 and in the CR-030
> record, and the frontmatter is filled in the day D1 is ruled — one edit, three
> rows, and G25's inventory-to-story direction starts asking about them.
>
> ⚠ **THIS DIVERGES FROM `EP-CUS-08`, which writes `screens: [S89]` / `[S90]` for
> two ids A1 also does not declare.** Recorded rather than silently copied: one of
> the two postures is wrong and a lane may not settle D1 by picking either. This
> epic takes the one `screenIds.ts` already took, so the story register and the
> route table agree with each other.

## Scope
**In:** the request object and everything that happens to it before a job exists — the six-step applicant capture form (`REQ-03.1…6` + the `REQ-03.sent` confirmation), the requests list with its five KPI tiles and five segments (`REQ-01`), the request detail with its six tabs, its two save controls and its decision panel (`REQ-02`), the ten-state lifecycle with its transition guards, numbering at creation (BR-CUS-093), address resolution as EVIDENCE, the clerk's identity search, the tenant's document checklist (BR-CUS-095), the application-fee quote and the counter collection (BR-CUS-090), approval against four conditions, refusal with a reason, park/resume, and the `outcome` + `outcome_ref` link that answers *"what happened to this application"* (BR-CUS-080).
**Out:** everything the decision HANDS OFF TO. The move-in it approves (US-CUS-004), the new connection it routes to (EP-MET-06, W6), the transfer (US-CUS-027) and the disconnect (US-CUS-028) — **W4 records a reference and creates no child**; the connection **quote builder** (no endpoint exists — the server answers `connection_quote: {raised: false, reason: "raised_after_review"}` and a builder drawn over it would be dead UI); document **upload** (no route in this product accepts a file); the applicant **identifier** (BR-CUS-092's app-layer encryptor is unbuilt); the acknowledgement **send** (`service_request` is not one of notifications' `SOURCE_TYPES` and cross-module writes are forbidden); the seven-glyph **icon rail** (BR-SHL-045 names it for the ACCOUNT detail and no glyph has a service-request endpoint behind it).
**Tables:** `service_requests` · `service_request_services` · `service_request_documents` · `service_request_fees` · `service_request_events` · `service_request_document_requirements` — all six customers-owned, all six RLS `FORCE` (migrations `0018`–`0020`). No cross-module write: premises/unit resolution goes through `apps.customers.seams`, and the AR position behind the arrears condition through `seams.ar_positions`.

## Capability matrix (list screens only — B9 conformance)
| Screen | Search fields | Filters | Default sort | Sortable | Columns default/available | Row actions | Bulk actions | Export |
|---|---|---|---|---|---|---|---|---|
| **`REQ-01`** (no id — D1) | request # · applicant name · `address_as_given` · phone · email — *"Request #, name, address, phone, or email…"*, one `icontains` per leg in `list_queryset` | **Five segments, all served:** `All` · **`Open`** (default) · `Waiting on customer` · `Approved` · `Closed`, as a URL filter | `received_at` **ASC**, `id` tiebreak — *"Sorted by age, oldest first — the oldest thing waiting is the thing to look at"*, and it is the QUERY's order, not something a caller must remember | **NONE** — `list_queryset` takes no `sort`; no column is declared sortable | **Default (8, B19 §12.1, all visible):** REQUEST · TYPE · APPLICANT · ADDRESS · RECEIVED · AGE · WAITING ON · STATE. **Available: none extra** | **One:** the row opens `REQ-02`. ⛔ **No icon rail** — B14 rule on row actions is satisfied by the single navigation | **NONE** | ⛔ **DRAWN, NOT BUILT** — B19 §12.1 puts `Export` in the header and no endpoint serves it |

## Stories

---
id: US-CUS-024
epic: EP-CUS-09
module: customers
screens: []              # ⛔ B18 proposes S85; A1 allocates nothing — decision D1. See the box above.
wave: 4                  # CR-030 W4 (`2.45.0`) — NOT B12's wave 4
status: ready
blocked_by: []
depends_on: [US-CUS-003, US-CUS-004, US-TEN-012]
journeys: [J26]
rules: [BR-CUS-070, BR-CUS-079, BR-CUS-090, BR-CUS-092, BR-CUS-093, BR-CUS-094, BR-CUS-095, BR-SHL-025, BR-TEN-035]
golden_tests: []
finance_calc: none       # the fee is a QUOTE — B18 §4.6, nothing posts to the ledger
---
### US-CUS-024 — `REQ-03`: the applicant's form — six steps, a number from the first save, and a fee that is a quote

**1 · Details** — As a **billing clerk taking a walk-in, a phone call or a paper form**, I want a six-step form in the applicant's own language — *"who is applying"*, *"what do they want"*, *"where"*, *"what did they bring"*, *"what do we take now"*, *"read it back"* — that **allocates the request number the first time it saves**, so that I can quote `SR-26-0048` down the phone while the form is still half-filled and the customer can ring back on Thursday and be found.

**Entry:** `REQ-01` header **`+ New request`** → route `/:tenant/requests/new` (`ServiceRequestCapturePage.tsx`, built on the shared `WizardFrame`). **Exit:** `REQ-03.sent`, the confirmation, which names the number and what was collected.

**What it calls:** `POST /service-requests` (create + number, one transaction) · `PATCH /service-requests/{id}` · `POST …/category` · `POST …/services` · `POST …/resolve-address` · `POST …/documents` · `POST …/fees` · `POST …/fee-collection` · `POST …/submit`. The URL gains `?request=<id>` after the first save so a refresh finds the same draft rather than burning a second number.

⚠ **BR-CUS-093's WORKED EXAMPLE CANNOT BE HONOURED TODAY AND THE SCREEN SAYS SO INSTEAD OF FAKING IT.** The ruling is *"a clerk opens the form on Tuesday, the request is `SR-26-0048` from that moment"*; `service_request_service._clean_capture(partial=False)` requires **`address_as_given`** (step **3**) and `applicant_name` before a row may exist. So `Save as draft` is **disabled with that reason** and the footer reads *"not saved yet"* rather than naming a number that does not exist. **A defect row and a backend change are OWED** (a nullable-at-draft create, or a ruling that the number arrives with the address); no lane may pick either.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-CUS-093 | Numbered **at creation**, from the tenant's `service_request` series; an abandoned draft **burns its number** and the gap is normal. Footer copy is *"Step N of 6 · saved as draft SR-26-####"*; *"nothing is created until you submit"* appears **nowhere** | CONFIRMED — PO 2026-08-24 (DEF-634) · ⚠ the *first-keystroke* half is NOT honoured, see §1 |
| BR-CUS-094 | Seven customer categories in the **ruling's order** (Residential · Commercial · Industrial · Agricultural · Institutional · Municipal · Builder or developer), never alphabetical; `government` renders **disabled with its reason** and is never re-labelled | CONFIRMED — PO 2026-08-24 (*"Expand the signed list to seven"*) |
| BR-CUS-070 | `address_as_given` is kept **verbatim**; the resolver writes the premise/unit ids **beside** it and the service refuses an edit after capture | CONFIRMED (transcribed 2026-08-25) |
| BR-CUS-095 | Step 4 has **no validation at all**, and that absence IS the rule: attaching never blocks CREATION. The `2 needed · 1 optional` badge is NOT drawn — a fresh tenant ticks nothing, so the honest number is zero | CONFIRMED — PO 2026-08-24 (OQ-351 → reading A) |
| BR-CUS-090 | The counter accepts what is handed over: `fee_collected < fee_quoted` is lawful, stays an **open balance**, never a waiver and never a refusal at the desk. One receipt number, idempotent | CONFIRMED — PO 2026-08-24 (DEF-637) |
| BR-CUS-092 | ⛔ **NO IDENTIFIER INPUT IS DRAWN and the words *"stored encrypted"* appear nowhere.** Clause (b) makes the app-layer encryptor the precondition and it is not built; the capture path refuses thirteen field names BY NAME. Clause (d): a false security promise over a government identifier is worse than an absent one | CONFIRMED (rule) — **NOT BUILT** (clause (b) precondition) |
| BR-CUS-079 | Submission records the acknowledgement's **ABSENCE**, never a fabricated `sent` state | CONFIRMED — PO 2026-08-24 |
| B18 §4.6 | The fees are a **quote**. `posts_to_ledger: false` is stated in the payload so a caller cannot assume otherwise. ⚠ **AMENDED 2026-09-24 (`DEF-CUS-6381`):** since 2026-09-15 money taken at the counter posts `DR 1010 · CR 2400` through payments, so the flag is DERIVED — true once that journal entry exists, false for a quote nobody has paid | CONFIRMED (design), amended |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 *(= TC-REQ-1)* | A clerk types a name and an address and saves | ONE `service_requests` row in `draft`, **numbered in the same transaction** from `SR-{YY}-{0000}`; the footer names the number |
| TC-2 *(= TC-REQ-2)* | The same draft is submitted twice | **Idempotent** — one number, not two; the second call allocates nothing and answers a replay (hard rule 6) |
| TC-3 | A clerk types only a name and stops | **No row, and `Save as draft` is disabled naming what is missing.** ⚠ This is the case that contradicts BR-CUS-093's worked example — it asserts what the product DOES, and the defect row is owed |
| TC-4 | Seven category chips render | In the **ruling's order**; `government` is present, **disabled, with its reason**, and its label is still `Government` |
| TC-5 *(negative)* | `POST …/category` with `government` | Refused `BIZ-STATE` / `customers.serviceRequest.categoryIsLegacy`, `br_ref = BR-CUS-094` |
| TC-6 *(= TC-REQ-6)* | The address is resolved, then the premise record is corrected | `address_as_given` is **byte-identical to capture**; an edit to it after capture is REFUSED |
| TC-7 | Step 4 with nothing attached | The step submits. **No validation fires**, and no `2 needed` badge is drawn |
| TC-8 | ⛔ **AMENDED 2026-09-24 (`OQ-CUS-12624`, `DEF-CUS-6455`, PO: *"all or waived"*): `$25.00` against `$130.00` is now REFUSED at the desk — `customers.serviceRequest.feeTakeInFull`, *"Take the full $130.00. Or waive it."*, nothing written — and `$130.00` is taken on the same receipt. The row below is the superseded 2026-08-24 case, kept visible.** `$25.00` cash against a `$130.00` quote, receipt `RCP-26-4471` | `fee_quoted 130.0000` · `fee_collected 25.0000` · `USD` · one receipt; **$105.00 outstanding**; no ledger row, no invoice, no payment row; `amount` travels as a **string** and a JSON float is refused, not coerced |
| TC-9 *(negative)* | Any of the thirteen identifier field names in the capture payload | Refused BY NAME with `BR-CUS-092`; nothing is silently dropped |
| TC-10 *(isolation)* | Lone Star Ridge submits while Brazos Bend has drafts | Numbers come from the **submitting tenant's** series; no Brazos row is visible or reachable (404, never 403) |

**4 · Test Data** — Tenant **Brazos Bend Utilities** · clerk **Marcus Vega** (Billing Clerk) · applicant **Okonkwo, David** · service address **`14 Willow Bend, Springfield`** (deliberately NOT on the premises register, so it resolves `no_premise`) · plot **`PL-2026-0884`** · category **Residential** · services **electric + water**, `available = NULL` (*not yet asked*) · fees quoted **$130.00** = `CC-REQFEE` $25.00 + `CC-EXPED` $60.00 + `CC-METERT` $45.00 · cash **$25.00** · receipt **`RCP-26-4471`** → outstanding **$105.00**. Series opened at 48 so the number comes out `SR-26-0048`. Seeded by `core/sample_fixture.CR030_SERVICE_REQUESTS` → `okonkwo-new-connection`.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Request # | every step footer · `REQ-03.sent` | BR-CUS-093 | `service_requests.request_no` (tenancy `number_series` `service_request`, BR-TEN-035) | text | system-derived | allocated at CREATE, never at submit; gaps are normal |
| Applicant name / kind / email / phone / language | `REQ-03.1` | B19 §2 | `service_requests.applicant_name` / `.applicant_kind` / `.applicant_email` / `.applicant_phone` / `.preferred_language` | text | user-input | name required to create |
| Co-applicant name / email / phone | `REQ-03.1` | B19 §2 (*"they carry no liability for the bill"*) | `.co_applicant_name` / `_email` / `_phone` — three columns and nothing else | text | user-input | optional |
| ⛔ SSN / driving licence | — | BR-CUS-092 | **NO COLUMN** — the encryptor is the precondition | — | — | thirteen field names refused BY NAME |
| Customer category / Sub-category | `REQ-03.2` | BR-CUS-094 · BR-CUS-067 | `.account_type_id` → ~~platform~~ **the tenant's own** `account_types` ⚠ **AMENDED 2026-09-17 — `account_types` IS NO LONGER A PLATFORM TABLE.** PO ruling, verbatim: *"utility can get their own account types"* (`BR-CUS-1079`), superseding `BR-CUS-094`'s platform half and B2 r5 #12 [D5]. It is tenant-scoped with RLS `FORCE` (`customers.0054`/`0055`); the seven are the SEED and a utility adds its own. **The sentence beside this stamp is history.** · `.account_subtype_id` → tenant `account_subtypes` | uuid | user-input | one of the seven; a `legacy` code is refused by name |
| Services requested | `REQ-03.2` | B19 §3 | `service_request_services` (service, `requested_start`, `available`) | rows | user-input | **`available = NULL` is *not yet asked*** and is never spelled the same way as *no* |
| `Address as given` / unit / billing address | `REQ-03.3` | BR-CUS-070 | `.address_as_given` · `.address_unit_as_given` · `.billing_address_same` · `.billing_address_as_given` | text | user-input | ⚠ **AMENDED 2026-09-20 — REQUIRED TO *SUBMIT*, NOT TO CREATE** (PO ratification, decision log §3; `DEF-CUS-6006`). It read *"required to create"*, and that made `Save as draft` a permanently disabled control on steps 1 and 2: the address is captured on `REQ-03.3` while the action sits on every step. A draft now opens on the applicant NAME ALONE — on NOTHING for a staff-raised channel (`BR-CUS-091`) — and `_require_submit_minimum` refuses the submit without one. **`BR-CUS-070` is untouched: still verbatim, still immutable after capture**, which is implemented as *after the row leaves DRAFT*, so a draft opened with no address can still be given one on step 3. |
| Plot or parcel / what is being built / property type | `REQ-03.3` | B19 §4 | `.plot_or_parcel` · `.what_is_being_built` · `.property_type` | text | user-input | blanks are RENDERED as blanks, never omitted |
| Documents brought | `REQ-03.4` | BR-CUS-095 | `service_request_documents` (`doc_type`, `what_it_proves`, `name`, `storage_ref` NULL) | rows | user-input | ⛔ **no file control** — no route accepts a file; the step records WHICH documents were brought |
| Fee lines / collection | `REQ-03.5` | BR-CUS-090 · B18 §4.6 | `service_request_fees` + `.fee_quoted` / `.fee_collected` / `.fee_currency` `CHAR(3)` / `.fee_receipt_no` | numeric 4 dp, display 2 | user-input | **never posts to the ledger**; a shortfall is an open balance |
| Acknowledgement | `REQ-03.sent` | BR-CUS-079 | `.acknowledgement_state` · `.acknowledgement_absence_reason` · `.acknowledgement_ref` | text | system-derived | **`sent` is never fabricated**; BR-CUS-090(3) forbids *"Nothing is charged"* over a collected fee |
| Audit | — | CLAUDE.md rule 7 | `audit_log` `service_request.*` | jsonb | system-derived | append-only; every money action writes one |

**6 · Acceptance**
- Given a name ALONE — no address — When the form saves on step 1, Then exactly one numbered `draft` exists and the footer shows its number — and *"nothing is created until you submit"* appears nowhere on any step.
- Given the same draft submitted twice, Then one number exists and the second call allocates nothing.
- Given a draft with a name and no address, When it is submitted, Then the submit is refused naming `address_as_given` and the request stays a `draft` (PO 2026-09-20 §3 — the requirement MOVED to submit; it did not disappear).
- Given seven category chips, Then they render in the ruling's order and `government` is disabled with its reason and its own label.
- Given a resolved address, Then `address_as_given` is byte-identical to what was typed and an edit to it is refused.
- ⛔ **SUPERSEDED 2026-09-24 (`OQ-CUS-12624`): Given `$25.00` offered against a `$130.00` quote, Then it is REFUSED naming the whole `$130.00` and nothing is written; only a request part-paid before that day still reads as follows.** Given `$25.00` handed over against a `$130.00` quote, Then the request shows **$25.00 collected of $130.00 quoted · $105.00 outstanding** on receipt `RCP-26-4471`, nothing posts to the ledger, and the confirmation does not print *"Nothing is charged"*.
- Given step 4 with nothing attached, Then the step submits and nothing is blocked.
- Given an identifier field in the payload, Then it is refused by name and never silently dropped.
- Given two tenants, Then numbers, drafts and documents never cross.

**7 · Finance Calculation** — **N/A as a posting; ONE figure is computed and it is a quote.** `outstanding = quoted − settled − collected`, at 4 dp, displayed at 2, with the `CHAR(3)` currency beside it (`service_request_reads._money`). Worked (BR-CUS-090's own case): quoted **130.0000**, collected **25.0000** → outstanding **105.0000**, displayed **$105.00**. **Nothing here writes a journal line** (B18 §4.6, `posts_to_ledger: false`), so no golden test is claimed and none is owed.

**8 · Open Questions** — **OQ-355** (the design prints *"4 of 5 conditions clear"* and four are identifiable) · **OQ-356** (an undrawn evidence combination has no sentence and none is invented) · **OQ-357** (a fee line cannot be removed, only waived) · **BR-CUS-092** clause (b), the unbuilt encryptor · **DEF-638** items b/c (`Date of birth` and `Acting for` are never collected and the customer match is made ON the date of birth; the detail labels the identifier `ID` where the form says `Social Security Number`) · ⛔ **a defect row is OWED for BR-CUS-093's first-keystroke half** (§1).

---
id: US-CUS-025
epic: EP-CUS-09
module: customers
screens: []              # ⛔ B18 proposes S83; A1 allocates nothing — decision D1. See the box above.
wave: 4
status: ready
blocked_by: []           # ✅ D4 is RULED (BR-CUS-106, PO 2026-08-25) — nothing blocks this screen
depends_on: [US-CUS-024]
journeys: [J26]
rules: [BR-CUS-091, BR-CUS-093, BR-SHL-010, BR-SHL-011, BR-SHL-013, BR-SHL-025, BR-TEN-043]
golden_tests: []
finance_calc: none
---
### US-CUS-025 — `REQ-01`: the requests list — five tiles, five segments, oldest first, and one cell that may not be styled

**1 · Details** — As a **billing clerk**, I want every live request in one list — **oldest first**, with five tiles across the top saying how many are open, how many are waiting on the customer, how long the oldest one has been waiting, how many are approved with nobody started and how many were refused this month — so that *"what came in this week?"* has an answer and the backlog stops being invisible until a customer complains (B18 §1.2 cost #2).

**Entry:** route `/:tenant/requests` (`ServiceRequestsListPage.tsx`). **Exit:** a row opens `REQ-02`; the header's `+ New request` opens `REQ-03`.

⚠ **B19 §12.1 DRAWS THIS AS A TAB OF THE ACCOUNTS PAGE AND IT IS A ROUTE OF ITS OWN.** `AccountsListPage.tsx` owns the eight-tab strip and was another lane's file in the shared tree; **the tab body is ONE line and it is OWED**. Until it lands, the Accounts page's `Requests` tab still renders an *arrives-with* note that is now FALSE.

✅ **THE AGE ACCENT IS DRAWN — `D4` IS RULED AT SEVEN DAYS, INCLUSIVE (BR-CUS-106, PO 2026-08-25).** This paragraph said *"THE AGE ACCENT IS NOT DRAWN AND `D4` IS UNRULED"*, and the refusal was right while it stood: B19 §12.1 measured the drawing and could only bound the threshold **between 6 and 11 days** (`15d` and `11d` are accent; `5d` and below are not), B18 *proposed* 7 without authority, and `list_row` **refused to serve `age_is_accented`** so that no lane could quietly pick a number. The PO chose **7 — one week — and the boundary is INCLUSIVE**. `list_row` now serves the flag, `AgeCell` renders it and **re-derives nothing**, and `TC-REQ-14` was **REPLACED, not deleted**: it now asserts the rule with a **7-day boundary case**, which the fixture cannot supply (the eight seeded ages are 15 · 11 · 5 · 4 · 3 · 2 · 1 · 0, so the nearest row to the line is `5d` and a `>` reading passes on all of them).

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-CUS-091 | **A `DISCONNECT` request is lawful in this list**, and the decision panel's *"only ever started by collections"* reason is WITHDRAWN. Raised by collections, so the applicant-identity fields are not required | CONFIRMED — PO 2026-08-24 (*"Yes customer can request it"*), closing DEF-638 12.a |
| BR-CUS-093 | A row created from 2026-08-24 always carries its number; a row that PREDATES the ruling carries NULL forever and **the absence names the RULE, not an open defect** | CONFIRMED — PO 2026-08-24 |
| BR-SHL-013 | Order is the QUERY's: `received_at` ASC, `id` tiebreak — *"the oldest thing waiting is the thing to look at"* | CONFIRMED (shared list law) |
| BR-SHL-025 | Role gate on every leg; a request belonging to another tenant is a **404, never a 403** | CONFIRMED |
| ✅ **BR-CUS-106** | The `AGE` accent threshold: a row accents once the request is **7 days old or more**, and **the boundary is inclusive**. Closes decision **D4**, which was bounded 6–11 days and derivable no further | CONFIRMED — PO 2026-08-25 (D4). `age_is_accented` IS SERVED by `list_row`; the screen never re-derives it |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 *(= TC-REQ-13)* | Segment `Open` over a larger register | The pager states both figures — *"Showing 1–8 of 42 (filtered from 118)"* — and the footnote names the sort |
| TC-2 | Eight seeded requests | Rendered **oldest first**; the `AGE` column is derived from `received_at`, never stored |
| TC-3 | Five segments | `All` · `Open` · `Waiting on customer` · `Approved` · `Closed` are a **URL filter**, so a segment survives a link being shared |
| TC-4 | The KPI strip | Five tiles read from the server. `OLDEST WAITING` with nothing parked says *"nothing waiting"* — **never `0 days`** |
| TC-5 | A `DISCONNECT` row | Lawful and rendered like any other type (BR-CUS-091); it carries no special badge |
| TC-6 *(= TC-REQ-14)* | A 15-day row, a 5-day row, **a row at exactly 7 days**, and a 15-day row the SERVER did not accent | 15d and 7d accent; 5d does not; the contradicted 15-day row renders **PLAIN** (which is what proves the threshold is not in the component). ✅ **REPLACED, not deleted** — the case used to prove a 15-day and a 2-day row were styled identically because D4 was open; BR-CUS-106 closed it and the inversion is obsolete. The 7-day case is the one the fixture cannot supply |
| TC-7 | `age_days = null` (no `received_at`) | The cell prints **nothing** — never `0`, never a guessed word (fabrication rule) |
| TC-8 | A row predating BR-CUS-093 | `request_no` is NULL and `number_absence` names **BR-CUS-093**, not a defect |
| TC-9 *(= TC-REQ-12, isolation)* | Lone Star Ridge lists requests | **None of Brazos Bend's rows**, under RLS `FORCE`, asserted through the non-superuser probe role |

**4 · Test Data** — The eight `[shot]` requests seeded by `core/sample_fixture.CR030_SERVICE_REQUESTS` (task 4.14), **cross-wired to five tabs** and back-dated so the AGE column stays true whenever the demo is planted: `osei-move-in` **15d** `More info needed · documents` · `ridge-property-new-connection` **11d** `In fulfilment` → `CON-26-0117` · `park-transfer` **5d** `Under review` · `okonkwo-new-connection` **4d** `Under review · payment` · `ridge-coffee-disconnect` **3d** `Under review · third party` · `kwan-move-in` **2d** `Approved` → `A-12048` · `alvarez-move-in` **1d** `Submitted` · `thompson-move-out` **0d** `Submitted · scheduled date`. ⚠ **The printed numbers are `SR-26-0001…0008`, not the drawn `SR-26-0039…0048`** — BR-CUS-093 numbers at creation from the tenant's own series and seeding the drawn numbers would mean writing behind the allocator's back; the cross-wiring travels by `CR030_SR_KEY`, never by the printed number.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| REQUEST | `REQ-01` col 1 | BR-CUS-093 | `service_requests.request_no` | text | system-derived | NULL only on a pre-ruling row, and the absence says so |
| TYPE | col 2 | B19 §12.1 | `.outcome` restricted to `JOB_OUTCOMES` | enum | system-derived | undecided → `type_absence: not_yet_classified`, never a blank chip |
| APPLICANT · ADDRESS | cols 3–4 | BR-CUS-070 | `.applicant_name` · `.address_as_given` (+ `.address_unit_as_given`) | text | user-input | the address is the one the applicant gave |
| RECEIVED · AGE | cols 5–6 | B19 §12.1 · BR-CUS-106 | `.received_at` → `age_days` **derived**, never stored; `age_is_accented` derived beside it | date / days / bool | computed-display | ✅ **`age_is_accented` IS SERVED — BR-CUS-106**, 7 days inclusive, computed once in `service_request.age_is_accented` |
| WAITING ON | col 7 | B19 §12.2 (Park) | `.waiting_on` | text | user-input | **orthogonal to `state`** — `Submitted` and *waiting on a scheduled date* are both true at once |
| STATE | col 8 | B18 §5.3.3 | `.state` (ten-state lifecycle) | enum | system-derived | segment membership comes from `SEGMENT_STATES`, never from a screen's list |
| KPI tiles ×5 | strip | B18 §5.3.1 | counts over `service_requests` + `.closed_at` | integer | computed-display | `period_basis: server_month_to_date` is **named in the payload**, because no rule states which clock a KPI window uses |

**6 · Acceptance**
- Given the eight seeded requests, Then they render oldest first and the footnote says so.
- Given a segment, Then it is a URL filter and the counts agree with `SEGMENT_STATES`.
- Given nothing parked, Then `OLDEST WAITING` says *nothing waiting* and never `0 days`.
- Given a 15-day row, a 7-day row and a 5-day row, Then the first two carry the accent and the third does not (**BR-CUS-106**, inclusive at 7) — and given a 15-day row the server did NOT accent, Then it renders plain, because the threshold is the server's and not the screen's.
- Given a `DISCONNECT` row, Then it renders like any other type.
- Given a second tenant, Then none of the first tenant's requests appear, under a role that cannot bypass RLS.

**7 · Finance Calculation** — N/A. **No money is displayed on this list at all**, which is itself the design: B19 §12.1's eight columns carry no amount, and the fee lives on `REQ-02`'s Fees tab (US-CUS-026).

**8 · Open Questions** — ~~**D4**, the AGE accent threshold~~ ✅ **CLOSED 2026-08-25 → BR-CUS-106** (seven days, inclusive; TC-REQ-14 replaced) · ⛔ **D1**, the screen id · **the Accounts-page `Requests` tab body is OWED** and its current *arrives-with* note is FALSE · **`Export` is drawn and has no endpoint.**

---
id: US-CUS-026
epic: EP-CUS-09
module: customers
screens: []              # ⛔ B18 proposes S84; A1 allocates nothing — decision D1. See the box above.
wave: 4
status: ready
blocked_by: []
depends_on: [US-CUS-024, US-CUS-025]
journeys: [J26]
rules: [BR-CUS-070, BR-CUS-071, BR-CUS-072, BR-CUS-073, BR-CUS-074, BR-CUS-079, BR-CUS-080, BR-CUS-089, BR-CUS-090, BR-CUS-091, BR-CUS-094, BR-CUS-095, BR-SHL-025]
golden_tests: []
finance_calc: none       # four figures are DISPLAYED; none is posted (B18 §4.6)
---
### US-CUS-026 — `REQ-02`: the request detail — six tabs, two save controls, and a decision nothing preselects

**1 · Details** — As a **billing clerk holding a request**, I want one screen that shows me who applied, where, what they brought, what they paid and what it should become — with **`Save & exit`** to leave quietly and **`Park — waiting on ▾`** to record WHAT I am waiting for, a note and a reminder date — so that *"a request rarely settles in one sitting"* stops being a reason to lose it, and so the decision about what a request BECOMES is made deliberately by a person.

**Entry:** a `REQ-01` row → `/:tenant/requests/:requestId` (`ServiceRequestDetailPage.tsx`). Per-tab deep links ride in `?tab=`. **Exit:** `Approve` (→ a job reference), `Refuse` (danger tier, reason required), `Ask for more`, or `Manual close`.

**Six tabs, not seven:** `Applicant · Location & services · Documents · Fees · Decision · History` (B19 §12.2 — the *"7"* in B18's task row is that document's own earlier count and is stale).

⛔ **THE SEVEN-GLYPH ICON RAIL IS NOT BUILT.** BR-SHL-045 names its seven for the ACCOUNT detail and **not one has a service-request endpoint behind it**; a rail of seven disabled glyphs would be seven reasons nobody asked for (hard-won law 2). **It needs its own ruling.**

⛔ **THE QUOTE BUILDER IS NOT BUILT.** The server answers `connection_quote: {raised: false, reason: "raised_after_review"}` with **no endpoint behind it**. What is built is the application-fee half; the quote half **states its own absence on the panel it belongs to**.

✅ **THE CATEGORY IS SERVED — closed 2026-08-25 (B18 task 4.12's reported read-model gap).** `set_customer_category` had written `account_type_id` / `account_subtype_id` since W4 landed and **no tab served either**, so this screen could not show what a request had been categorised as and a half-finished draft reopened from the list could not restore the chip. It is now on the **Applicant** tab beside `person_or_company` — B19 §14.3's two axes, side by side — carrying `legacy` and `selectable` so a `government` row reads as **picked and not pickable** rather than being re-labelled to nothing by omission.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-CUS-071 | ~~The system classifies~~ — **THE CLERK DECIDES.** The resolver serves EVIDENCE (`resolution_kind`, `lookup_found`, both STORED); the panel preselects **nothing**, badges at most one option `Fits the evidence`, and every `not_possible` carries the PO's own sentence. A clerk deciding against the evidence is **recorded, never refused** | **SUPERSEDED** — CR-031 statement 3 (PO 2026-08-24) |
| BR-CUS-089 | The match tier and its confirmer are stored; **money moves only on `strong`**. `match_confirmed_at` carries *somebody looked*, so a genuine first-time applicant clears the arrears condition through the same control | CONFIRMED |
| BR-CUS-095 | **Two gates, and they are two fields so a screen cannot conflate them:** attaching never blocks CREATION; an unverified required document blocks APPROVAL. An unconfigured tenant contributes an empty checklist and **blocks nothing** — the shipped default, never softened | CONFIRMED — PO 2026-08-24 |
| BR-CUS-090 | The Fees tab shows four figures — quoted · settled · collected · outstanding — each at 4 dp with a 2 dp display and its `CHAR(3)` currency. `SEPARATE`: settling the application fee does not settle the quote | CONFIRMED |
| BR-CUS-091 | `Disconnect` is decidable and carries **no badge**. ⚠ What survives the withdrawal and the screen must keep saying: a **move-out** closes the account and settles the deposit; a **disconnect** leaves it **open and accruing** | CONFIRMED |
| BR-CUS-072 | Refuse **keeps** the request and its reason; `reopen` needs a reason and the refusal stays on the append-only timeline forever | CONFIRMED (transcribed 2026-08-25) |
| BR-CUS-073 | Documents **move by reference, never by copy** — one uploaded file stays one row and the audit trail of who supplied it survives the hand-off | CONFIRMED (adopted by BR-CUS-080) — ⚠ the destination table is NOT BUILT (task 3.7) |
| BR-CUS-080 | The SR alone answers *"what happened to this application"* from `outcome` + `outcome_ref`; the child points at the parent | CONFIRMED |
| BR-CUS-074 | ⛔ **Approval is NOT threshold-checked and refusal is NOT supervisor-only.** The measure, the figure and the supervising role are all unstated — *and there is no supervisor role in the identity model.* What IS built: approval gated on an outcome + four conditions, and refusal gated on a free-text reason | **PROPOSED — NOT RULED, NOT BUILT.** `TC-REQ-8` cannot be written as designed and is pinned as an ABSENCE |
| BR-CUS-094 | The category is **served back** with `legacy` / `selectable`, so a legacy code reads as picked and not pickable and is never re-labelled by omission | CONFIRMED — read-back added 2026-08-25 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | The detail is fetched | All **six** tabs are served in one payload, plus the header, the three metric columns and the actions |
| TC-2 | A request that was categorised `builder_developer` | The Applicant tab serves the code, its name, `legacy: false` and `selectable: true` — **through the same payload REQ-02 renders**, not through the model |
| TC-3 | A draft that never reached step 2 | `not_yet_categorised: true`, both fields `null`, **no `_absence` block and no invented default** — a guessed chip is a guessed tariff class |
| TC-4 | A row carrying the LEGACY `government` code | Served with `legacy: true` · `selectable: false` · name still `Government`. **Never re-labelled** |
| TC-5 | A sub-category | Served **with its parent id**, so a screen cannot draw `Residential › Healthcare` |
| TC-6 *(= TC-REQ-7)* | A ticked, attached, **unverified** document → `approve` | **Refused**, naming the blocking condition — *"Nothing is refused — it simply cannot be approved yet"*. NOT a move to `Refused`, NOT a hidden button |
| TC-7 | The Decision panel | **Nothing preselected**; every `not_possible` carries the server's own sentence; an undrawn combination is `possible` with **no invented reason** (OQ-356) |
| TC-8 | A clerk picks an option badged `Not possible` | **Recorded, not refused** — `decided_against_evidence = true` and the evidence is snapshotted |
| TC-9 *(= TC-REQ-9)* | `refuse` with no reason | Refused at the control and at the server |
| TC-10 *(= TC-REQ-10)* | A refused request is reopened | Allowed **with a reason**; the refusal stays in `service_request_events` forever |
| TC-11 *(= TC-REQ-11)* | `route` on an approved request | A child reference is recorded and one SR can produce only ONE live child; linking before an outcome is decided is refused |
| TC-12 | `Park` | Records `waiting_on` + note + reminder and **moves no state**; `Resume` clears the park and keeps the note on the timeline |
| TC-13 | The Fees tab | Four figures at 4 dp with 2 dp displays and `CHAR(3)`; `posts_to_ledger` false for an unpaid quote and true once the counter's collection posted (amended 2026-09-24, `DEF-CUS-6381`); a shortfall is `shortfall_is_open_balance`, never a waiver and never a refusal |
| TC-14 *(= TC-REQ-8, INVERTED)* | A **billing clerk** approves once conditions clear | **It succeeds** — there is no threshold and no supervisor tier. ⛔ Pinned as an ABSENCE so that the day a threshold appears the case goes RED and whoever added it must name the ruling |
| TC-15 | The category is changed twice | Three `service_request.category_set` audit rows, all JSON-serialisable (DEF-657) |
| TC-16 *(isolation)* | Another tenant's request id | **404, never 403** — the boundary must not confirm the row exists |

**4 · Test Data** — `SR-26-0039` **Osei, Grace** · `3450 Oak Ridge Dr` — served, and the unit is **vacant**, which is what badges `Move-in` as *Fits the evidence*; `AGE 15 days`, waiting on **documents** since Aug 21; the tenant has ticked **two** documents for `move_in` (`proof_of_identity`, `signed_service_agreement`) and one of the two is attached-and-unverified, so approval is blocked BY NAME. Beside it `SR-26-0042` **Okonkwo, David** carries BR-CUS-090's worked money (`$25.00` of `$130.00`, `RCP-26-4471`, `$105.00` outstanding) and `SR-26-0043` **Ridge Property LLC** carries the cross-wire to `CON-26-0117`. All from `core/sample_fixture.CR030_SERVICE_REQUESTS`.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Header: number · state · classification chip · applicant · address · received/by/channel | `REQ-02` header | B19 §12.2 | `.request_no` · `.state` · `.outcome` · `.applicant_name` · `.address_as_given` · `.received_at` · `.received_by_id` · `.channel` | text | mixed | ⚠ `classification` is the **OUTCOME** chip; the customer CATEGORY is a different column on the Applicant tab |
| **Customer category / sub-category** | **Applicant** tab | BR-CUS-094 · BR-CUS-067 · **task 4.12** | `.account_type_id` → `account_types` · `.account_subtype_id` → `account_subtypes` | uuid → `{code,name,legacy,selectable}` | user-input | **served back with `legacy`/`selectable`**; unset → `not_yet_categorised: true`, never a default |
| Customer match | Applicant tab | BR-CUS-089 | `.matched_customer_id` · `.match_tier` · `.match_basis` · `.match_confirmed_at` | text | user-input | `may_move_money` only on `strong` |
| ⛔ `ID` · `Date of birth` · `Acting for` | Applicant tab | BR-CUS-092 · DEF-638 | **NO COLUMNS** | — | — | served as three named absences, each citing what closes it |
| Address as given / resolved to / consequence | Location tab | BR-CUS-070 | `.address_as_given` · `.resolved_premises_id` · `.resolved_unit_id` · `.resolution_kind` · `.lookup_found` | text/uuid | mixed | the resolved record sits **beside**, never over |
| Services + availability | Location tab | B19 §3 | `service_request_services.available` | bool NULL | user-input | **NULL is *not yet asked*** |
| Documents + the tenant's checklist | Documents tab | BR-CUS-095 | `service_request_documents` + `service_request_document_requirements` | rows | mixed | three fields, deliberately: `checklist_required` (tenant) · `checklist_unmet` · per-row `required_flag` (clerk). An empty checklist is the SHIPPED STATE and is **not an absence** |
| Fee lines + four totals | Fees tab | BR-CUS-090 | `service_request_fees` + `.fee_quoted` / `.fee_settled` / `.fee_collected` / `.fee_currency` | numeric 4 dp → display 2 | mixed | `posts_to_ledger: false`; `connection_quote.raised: false` with its reason |
| Decision: options · verdicts · conditions · commit | Decision tab | BR-CUS-071 (superseded) · BR-CUS-091 | `.outcome` · `.decided_by_id` · `.decided_at` · `.decided_against_evidence` · `.evidence_snapshot` · `.outcome_kind` · `.outcome_ref` | enum/jsonb | user-input | **`preselected: null`**; `undrawn_verdict_absence` tracks **OQ-356**; conditions count **4** and say why not 5 (**OQ-355**) |
| History | History tab | B19 §12.3 | `service_request_events` | rows | mixed | **append-only**; internal notes are never shown to the customer |

**6 · Acceptance**
- Given a categorised request, When `REQ-02` loads, Then it shows the category it was given, with its sub-category and its parent — and a legacy code reads as picked and not pickable.
- Given an uncategorised draft, Then the screen says *not yet categorised* and shows no default.
- Given an attached-but-unverified required document, When `Approve` is pressed, Then it is refused by name and the request does **not** move to `Refused`.
- Given the Decision panel, Then nothing is preselected, every impossibility carries its own sentence, and an undrawn combination invents none.
- Given a clerk choosing against the evidence, Then it is recorded with the evidence snapshot, not refused.
- Given `Refuse` with no reason, Then it is refused; given a reopen, Then the refusal survives on the timeline.
- Given `Park`, Then the reason, note and reminder are stored and the state does not move.
- Given the Fees tab, Then four figures render at two decimals with their currency and nothing posts to the ledger.
- Given a billing clerk with conditions clear, Then approval succeeds — **there is no threshold, and the day there is one this acceptance changes with a ruling behind it.**
- Given another tenant's request id, Then 404, never 403.

**7 · Finance Calculation** — **N/A as a posting.** Four figures are DISPLAYED and one is derived: `outstanding = quoted − settled − collected`, 4 dp stored, 2 dp displayed, `CHAR(3)` beside. Worked: **130.0000 − 0 − 25.0000 = 105.0000 → $105.00**, and that outstanding figure is what the review step **REPORTS**. ⛔ **It read *"reads as a blocking condition"* until 2026-09-21** — PO, *"make application fees optional - so that we can approve it"* — so the request approves with the $105.00 outstanding and still shows it afterwards (`BR-CUS-090` clause (1), amended, dated). No journal line, no invoice, no payment row (B18 §4.6) — so no golden test is claimed and none is owed. ⛔⛔ **SUPERSEDED 2026-09-23 — THE FEE GATES APPROVAL AGAIN (`OQ-CUS-12617` CLOSED, `DEF-CUS-6420`).** PO, verbatim: *"we already told you - either fee is paid or waived - no other condition"*. Approve waits until the application fee is **paid in full or waived**; a part payment holds it on the REMAINDER (quoted $130.00, taken $25.00 → *✗ Fee · $105.00 unpaid*, Approve off). A utility with no fee lines is untouched, and the counter still accepts a short payment and never refuses — the desk half of `BR-CUS-090` stands. The paragraph above is kept as the record of 2026-09-21.

**8 · Open Questions** — **OQ-355** (*"4 of 5 conditions"* — four are identifiable and nothing prints a `5` it cannot itemise) · **OQ-356** (the undrawn verdict) · **OQ-357** (a fee line is waived, never removed) · **BR-CUS-074** ⛔ the approval threshold, the supervising role and the reason-code vocabulary — **all three unstated, and TC-REQ-8 is pinned as an absence until they are ruled** · ⛔ **the seven-glyph icon rail needs its own ruling** (no glyph has an endpoint) · ⛔ **the quote builder has no endpoint** · **BR-CUS-073's destination table does not exist** (task 3.7) · **DEF-638** items b/c/e · ⛔ **D1**, the screen id.
