# J26 — Request to service (a phone call becomes `SR-26-0044`, is matched, priced, approved, routed, and produces a live account)

---
id: J26
tier: 2
rules: [BR-CUS-070, BR-CUS-079, BR-CUS-080, BR-CUS-089, BR-CUS-090, BR-CUS-091, BR-CUS-092, BR-CUS-093, BR-CUS-094, BR-CUS-095, BR-CUS-030, BR-MET-105, BR-SHL-025, BR-SHL-011]
stories: [US-CUS-024, US-CUS-025, US-CUS-026]
# ✅ **THE THREE OWED STORIES EXIST — 2026-08-25, CR-030 task 4.16.** This list
# was `[]` and that emptiness was A FINDING, not an omission: hard-won law 8,
# *"every screen needs a story"*, and B18 §5.3's S83/S84/S85 owned none while
# the screens were built and the endpoints live. They are now written, in the
# eight-section format, in
# `04-docs/05-modules/03-customers/06-epics/EP-CUS-09-service-requests.md`:
#   US-CUS-024 — `REQ-03`, the applicant's six-step form
#   US-CUS-025 — `REQ-01`, the requests list
#   US-CUS-026 — `REQ-02`, the detail, its six tabs and its decision
# and `05-user-stories.md` carries all three. Every id here resolves, which is
# what G12 check 6 asks and what the empty list was protecting.
#
# ⚠ **THE STORIES CARRY NO SCREEN ID, AND THAT IS NOT AN OVERSIGHT.** A1
# declares no S83/S84/S85 and B18 §12.2 decision **D1** is unruled — allocation
# is the PO's. So the three stories carry `screens: []` with the reason, exactly
# as `07-frontend/src/routing/screenIds.ts` carries `ids: NONE` on all three
# routes. **S83/S84/S85 stay the TICKET vocabulary** and the frontmatter is
# filled the day D1 is ruled.
#
# ✅ **ACTIVATED — 2026-08-25, CR-030 W4 task 4.16.** This note said *"AND THIS
# JOURNEY IS STILL NOT ACTIVATED. There is no `J26.spec.ts`, so G12 checks 2–5
# have nothing to bite on."* **`07-frontend/e2e/J26.spec.ts` now exists** and
# claims this id through the support kit's `journey("J26", …)`, which is what
# activation MEANS in this repo — `07-frontend/e2e/README.md` §Journey
# activation, and gate G12 reads `01-journey-story-index.json`, never prose.
# (⚠ `08-qa/01-e2e/tests/money-journey.spec.md` is NOT the convention: its own
# first line says *"becomes .spec.ts when app boots"* and G12 does not look in
# that directory at all.)
#
# ⚠ **WHAT ACTIVATION COST, BECAUSE THE NEXT JOURNEY WILL MEET IT TOO.** G12
# **check 5** refuses a spec claiming a journey whose declared stories the wiring
# index says are not built, and the index's build signal is a **Trace-header
# citation**. EP-CUS-09 deliberately cited none of US-CUS-024/025/026 anywhere,
# so `ready_by_stories` was **false** and `J26.spec.ts` was refused before it was
# written. The citation now lives in `apps/customers/service_request_reads.py`
# and the `test_us_cus_0nn_tc*` aliases G10 then demands land with it, in one
# change, exactly as the epic said they must. **The frontend half of the citation
# is still owed** and is stated in that file's own header.
#
# ⚠ **AND THE STACK NEEDED A SEEDER.** `08-qa/01-e2e/stack/boot_stack.sh` runs
# `seed_journey_fixture.py --activated`, which prints *"✗ NO FIXTURE SEEDER"* for
# an activated journey with no registered cohort — `seed_demo` does NOT plant
# sample records, so the eight `[shot]` requests were not on the booted stack at
# all. `seed_j26` (registered in `SEEDERS`) plants them through
# `apps/customers/sample_data._seed_cr030_service_requests`, and REFUSES with a
# named `CannotSeed` if fewer than eight land — a spec asserting over a partial
# cohort is DEF-108's shape.
#
# The file remains the HANDOFF CONTRACT the prime directive's dependency rule
# asks for — what each step leaves in the DB for the next — and it was written
# before the spec so the spec had something to be written against.
# ✅ **THE FIXTURE BLOCKER IS GONE.** This note said activation *"needs the seed
# (B18 task 4.14, the eight `[shot]` requests) which is a DATA task this lane
# did not do."* **Task 4.14 IS DONE** — `core/sample_fixture.CR030_SERVICE_
# REQUESTS` declares the eight and `apps/customers/sample_data._seed_cr030_
# service_requests` plants them through the service path a clerk drives, wired
# into `seed_sample_records`. What remains is the spec file itself, and one
# fixture caveat that belongs in the spec's own head: **the seeded numbers are
# `SR-26-0001…0008`, not the drawn `SR-26-0039…0048`** (BR-CUS-093 numbers at
# creation from the tenant's own series, so the drawn numbers cannot be seeded
# without writing behind the allocator's back). A spec asserting the literal
# string `SR-26-0044` will go red on a correct fixture — assert the ORDER, the
# AGE column and the cross-wire keys instead.
---

**Intent.** The front door, end to end. A walk-in becomes a numbered request in
the first keystroke that the server will accept, gets its address resolved, its
category and services set, its documents recorded, its fee taken **short of the
quote**, its outcome decided by a clerk against evidence the system offered but
did not choose, and finally a job — and every rule the PO ruled on 2026-08-24 is
exercised at the step it governs.

**Fixture.** Tenant **brazos-bend** · clerk **A. Reed** (Billing Clerk) ·
applicant **Okonkwo, David** · service address **14 Willow Bend, Springfield**
(NOT on the premises register) · category **Residential** · services
**Electricity + Water** · fees quoted **$130.00** (`CC-REQFEE` $25.00 +
`CC-EXPED` $60.00 + `CC-METERT` $45.00) · cash handed over **$25.00** · receipt
**`RCP-26-4471`**.

| # | Step · screen | Handoff contract (what this step leaves) | Downstream assertions | Rule |
|---|---|---|---|---|
| 1 | **REQ-03.1** — the clerk opens the capture form and types the applicant's name. `Save as draft` is **DISABLED, with its reason on the control**. | Nothing in the database yet. | ⚠ **THE SCREEN AND THE RULING DISAGREE HERE AND THE SCREEN SAYS SO.** BR-CUS-093's worked example is *"a clerk opens the form on Tuesday, the request is `SR-26-0048` from that moment"*; `service_request_service._clean_capture(partial=False)` requires `address_as_given` — which is **step 3** — and `applicant_name`. So the footer reads *"not saved yet"* and names what is missing, rather than printing a number that does not exist. **Reported as needing a defect row and a backend change; nothing here invents a number.** | BR-CUS-093 · BR-SHL-025 |
| 1a | **REQ-03.1** — the `ID` row. | Nothing is captured. | ⛔ **NO IDENTIFIER INPUT EXISTS AND THE WORDS *"stored encrypted"* APPEAR NOWHERE.** BR-CUS-092(b) makes the app-layer encryptor the precondition and it does not exist; the capture path refuses thirteen field names BY NAME. Clause (d): a false security promise over a government identifier is worse than an absent one. The row renders the SERVER's own sentence with `data-tracks="BR-CUS-092"`. | BR-CUS-092 |
| 2 | **REQ-03.3** — the address is typed. `POST /service-requests` fires. | `service_requests` row in `draft`, **numbered `SR-26-0044` in the same transaction**; `address_as_given = "14 Willow Bend"`, byte for byte. The URL gains `?request=<id>` so a refresh finds the same draft rather than burning a second number. | The footer becomes ***"Step 3 of 6 · saved as draft SR-26-0044"***. ⛔ *"nothing is created until you submit"* must appear NOWHERE. `POST .../resolve-address` then writes `resolution_kind = no_premise` and stores `lookup_found` — EVIDENCE, never a decision. | BR-CUS-093(b) · BR-CUS-070 |
| 3 | **REQ-03.2** — category and services. | `account_type_id` set from the SEVEN; `service_request_services` holds `electric` + `water` with `available = NULL`. | ✅ Seven chips in the **ruling's order** (Residential · Commercial · Industrial · Agricultural · Institutional · Municipal · Builder or developer), never alphabetical. ⛔ `government` renders **disabled with its reason** — unselectable on a new record, lawful everywhere else, and **never re-labelled**. `available = NULL` is *not yet asked* and is never spelled the same way as *no*. | BR-CUS-094 |
| 4 | **REQ-03.4** — documents. | `service_request_documents` rows with `doc_type` and NO `storage_ref`. | ✅ **GATE ONE: attaching never blocks CREATION** — the step has no validation at all, and that absence is the rule. ⛔ **The file control is DISABLED with its reason**: no route in this product accepts a file for a service request, so a working picker would silently discard what a customer handed across the counter. ⛔ The `2 needed · 1 optional` badge is NOT drawn — BR-CUS-095 ships the checklist unticked, so the honest fresh-tenant number is zero. | BR-CUS-095 · B19 §5 |
| 5 | ⛔ **AMENDED 2026-09-24 (`OQ-CUS-12624`, `DEF-CUS-6455`): `"25.00"` against the `$130.00` quote is now REFUSED (422, `feeTakeInFull`) and the step takes `"130.00"`; the cells to the right are the superseded 2026-08-24 case.** **REQ-03.5 → REQ-02 Fees** — `POST .../fee-collection` with `{"amount": "25.00", "method": "cash", "receipt_no": "RCP-26-4471"}`. | `fee_quoted = 130.0000`, `fee_collected = 25.0000`, `fee_currency = USD`, ONE `fee_receipt_no`. **No ledger row, no invoice, no payment row.** | ✅ **BR-CUS-090's worked case, on screen:** *$25.00 collected of $130.00 quoted · $105.00 outstanding*, receipt `RCP-26-4471`. ⛔ The shortfall is **NEVER** refused at the desk, **NEVER** drawn as a waiver, and the quote is **NEVER** adjusted to match the cash. `amount` travels as a STRING — a JSON float is refused by name, not coerced. Idempotent on the receipt number: a double-click is a no-op. | BR-CUS-090 · rule 2 · rule 6 |
| 6 | **REQ-03.6 → REQ-03.sent** — submit. | State `submitted`. A second submit answers `idempotent_replay: true` and allocates nothing. | ✅ TC-REQ-2. ⛔ **The acknowledgement is NOT badged *"Sent automatically"***: notifications' `SOURCE_TYPES` has no `service_request` and cross-module writes are forbidden, so the panel prints the server's own *"No acknowledgement has been sent…"*. ⛔ **BR-CUS-090(3): *"Nothing is charged"* is NOT printed** on a confirmation showing $25.00 collected — the sentence states the amount, the method and the receipt number instead. | BR-CUS-079 · BR-CUS-090(3) |
| 7 | **REQ-01** — the request appears in the list. | Segment `Open`, sorted `received_at` ascending. | The KPI strip's five tiles read from the server; `OLDEST WAITING` with nothing parked says *"nothing waiting"*, **never `0 days`**. ✅ **`AGE` ACCENTS AT SEVEN DAYS, INCLUSIVE — BR-CUS-106 (PO 2026-08-25, closing D4).** This row said *"`AGE` carries NO ACCENT on any row"* while D4 was open. The spec asserts it as an INVARIANT over every rendered row (`days >= 7 ⇔ accented`), not against the fixture's ages — the seeded eight are 15 · 11 · 5 · 4 · 3 · 2 · 1 · 0, so the nearest row to the line is `5d` and **the fixture alone cannot tell `>= 7` from `> 7`**; the boundary is pinned in `test_br_cus_106_the_age_accent_starts_at_seven_days_inclusive` and in the cell's own vitest case. ✅ A `DISCONNECT` row is lawful in this list (BR-CUS-091). | BR-CUS-106 · BR-CUS-091 |
| 8 | **REQ-02 Decision** — the clerk records the customer search, then picks. | `match_confirmed_at` stamped even where NO prior customer exists — *"searched, and there is no prior customer"* is a real answer and is what clears the arrears condition for a first-time applicant. `outcome` set by the CLERK. | ⛔ **Nothing is preselected.** One option may be badged `Fits the evidence`; every `not_possible` carries the server's own sentence; every undrawn combination is `possible` **with no invented reason** (OQ-356). ✅ **Disconnect is ENABLED** and the withdrawn *"only ever started by collections"* reason appears nowhere. ⚠ And the distinction it drew survives, beside the two controls: a **move-out** closes the account and settles the deposit; a **disconnect** leaves it **open and accruing**. | BR-CUS-091 · BR-CUS-089 · OQ-356 |
| 9 | **REQ-02 Documents → approve.** | Approval is REFUSED while a required document is attached-but-unverified. | ✅ **GATE TWO: verifying is what unblocks APPROVAL** — *"attaching a file is not the same as verifying it"*. The refusal is a **reason on the button**, not a hidden button and **not a move to `Refused`**: *"Nothing is refused — it simply cannot be approved yet."* TC-REQ-7. The `Conditions` panel prints **4**, not the design's 5, and says why (OQ-355). | BR-CUS-095 · OQ-355 |
| 10 | **REQ-02 → refuse, then reopen.** | `service_request_events` keeps the refusal FOREVER. | TC-REQ-9: a refusal with no reason is refused at the control and at the server. TC-REQ-10: `reopen` is allowed from `refused` **with a reason**, and the refusal stays on the timeline — which is the whole reason the register keeps refused requests (*someone turned down for arrears at a previous address simply reapplies*). The History tab is append-only; nothing edits a line. | BR-CUS-080 |
| 11 | **INVARIANCE** — `address_as_given` is byte-identical to submission; `lookup_found` is the sentence STORED at resolution and does not move when the premises record does; the request number is never renumbered, backfilled or reused; nothing in this module posted to the ledger. | — | TC-REQ-6. BR-CUS-093(a): **gaps in the series are NORMAL and no report may present one as a missing record.** B18 §4.6: the fees are a quote. | BR-CUS-070 · BR-CUS-093(a) |

## What this journey CANNOT yet assert, and why

| # | Not asserted | Blocked on |
|---|---|---|
| a | **The number exists from the instant the form opens.** | The create path requires `address_as_given` and `applicant_name`. Backend change or a ruling; reported by the W4 frontend lane. |
| b | **A file is attached and then verified.** | No upload route exists for a service request. A document can be RECORDED and, without a file, cannot be verified — which is correct, and which means gate two cannot be exercised end to end from the UI alone. |
| c | **The acknowledgement reaches the applicant.** | `service_request` is not one of notifications' eight `SOURCE_TYPES`, and cross-module writes are forbidden — it is that module's own change. |
| d | **The request produces a live account and a first bill** (B18's own one-line summary of J26). | `POST .../child-link` records a reference; nothing in W4 CREATES the account or the connection. That is W5/W6. |
| e | ~~**The `AGE` accent.**~~ ✅ **CLOSED 2026-08-25 — D4 IS RULED.** **BR-CUS-106**: a request accents once it is **7 days old or more**, and the boundary is **INCLUSIVE**. `list_row` serves `age_is_accented`, `AgeCell` renders it and re-derives nothing, and `TC-REQ-14` was **REPLACED, not deleted** — it proved a 15-day row and a 2-day row were styled identically while D4 was open, and it now asserts the rule with the 7-day boundary case the fixture cannot supply. | — |
| f | ~~**The eight `[shot]` seeded requests.**~~ ✅ **CLOSED 2026-08-25 — TASK 4.14 IS DONE.** `core/sample_fixture.CR030_SERVICE_REQUESTS` declares the eight and `apps/customers/sample_data._seed_cr030_service_requests` plants them through `create_request` → `resolve_address` → `attach_document`/`verify_document` → `add_fee_line`/`collect_fee` → `submit` → `transition` → `decide_outcome`/`approve` → `park`/`link_child` — the service path a clerk drives, never a raw INSERT — and it is wired into `seed_sample_records`. `received_at` is back-dated **relative** to today so the AGE column stays true whenever the demo is planted (DEF-629's reason). | ⚠ **ONE CAVEAT FOR THE SPEC:** the seeded numbers are `SR-26-0001…0008`, **not** the drawn `SR-26-0039…0048` — BR-CUS-093 numbers at creation from the tenant's own series, and seeding the drawn numbers would mean writing behind the allocator's back or burning 38 numbers on phantom drafts. **This journey's own title names `SR-26-0044`; a spec asserting that literal string will go RED on a correct fixture.** Assert the ORDER, the AGE column and the `CR030_SR_KEY` cross-wires. |
