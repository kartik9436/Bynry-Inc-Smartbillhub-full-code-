# CR-094-BRC01 · capture wave · lane F — each service carries its own start

**Branch** `claude/gifted-johnson-top7zn` · **rule** `BR-CUS-1070` · **defect**
`DEF-CUS-5195` (the data half; the screen half is lane D's) · **found and fixed
in passing** `DEF-CUS-5412`.

**Lane D builds from this file, not from a conversation.** §3 is the request
shape the wizard sends and §4 is the read shape it gets back, both with values
taken off the running product.

---

## 1 · The pages, read as images

B14 rule 42 — a screen is built from the drawing AS AN IMAGE; extracted text is
an index, never the specification. All three were rendered at **scale 2** by
`10-scripts/pdf/pdf_render.py` from `05-prototype/02 Accounts Menu Blueprint.pdf`
and read with the Read tool as PNGs. No higher scale was needed; every figure
below was legible at 2.

| Page | Read at | What was taken from it |
|---|---|---|
| `p076.png` | scale 2 | step 2's lower half — the services multiselect, the heading *When each one is wanted*, the `SERVICE · REQUESTED START` table (Electric · Water · Sewer, all `05/12/2026`), the argument beneath it, and `Connection date` with *"The whole job, where the applicant has a date in mind."* |
| `p077.png` | scale 2 | step 2's foot and its caption — *"services picked from a multiselect, **each with its own start**"* |
| `p080.png` | scale 2 | step 6's review block — `Requested start → 05/12/2026, all three` and `Connection date → — not given`, adjacent rows of ONE request |

Every figure on those pages is an **illustration** under B14 rule 37. What is
built is the SHAPE: a date per service, and a job-level date beside it. Nothing
in the product hard-codes `05/12/2026` or the number three.

---

## 2 · Before and after, measured

**The wave brief said `ServiceRequestService.requested_start` *"is never written
by anything"*. That is not what the code did, and the truth is narrower and
worse.**

| | Before (at `62a81b3f`) | After |
|---|---|---|
| `set_services` writes | `requested_start=request.requested_start` — a COPY of the job-level `Connection date`, on every row | the date the clerk gave for THAT service, or NULL |
| A clerk can give electric the 12th and sewer a fortnight later | **No.** Every row was the same date by construction | Yes |
| `p080`'s drawn pair (`all three 05/12/2026` over `— not given`) | **Unreachable.** A blank job date forced three blank service dates | Reached — §5 step 3 |
| Rows in `service_request_services`, demo tenant | **0**, against 8 service requests | unchanged; nothing was backfilled |
| The read can say *all three agree* | No — the list only | `requested_start_agreement` |

The `0` is counted, not assumed: `select count(*) from service_request_services`
on `smartbillhub`, 2026-09-15. **Nothing in `sample_data.py` calls
`set_services`**, so the join table has never held a row on the demo tenant —
which is also why `DEF-CUS-5412` below could hide.

---

## 3 · The request shape — what the wizard POSTs

`POST /api/{tenant}/service-requests/{id}/services`, `@require_role(SYSTEM_ADMIN,
BILLING_CLERK)`, body:

```jsonc
{
  "services": [
    { "code": "electric", "requested_start": "2026-12-05" },
    { "code": "water",    "requested_start": "2026-12-05" },
    { "code": "sewer",    "requested_start": "2026-12-19" }
  ]
}
```

* **`code`** is the platform catalogue's code (`tenancy.Service.code`) — the same
  value the old flat list carried. The multiselect's options come from
  `GET /settings/services` filtered on `enabled`, as the 2026-09-15 ruling
  requires; nothing here hard-codes eleven.
* **`requested_start`** is `YYYY-MM-DD`, or `null`, or absent. All three of those
  mean **the clerk gave no date for this service** — never *use the job's*.
* **The old shape is still accepted and is not deprecated.** A bare string
  entry, `"electric"`, means the same as `{"code":"electric"}`: no date given. A
  **mixed list is fine** — `["electric", {"code":"sewer","requested_start":"…"}]`
  works and is proved in §5 step 7. Nothing was migrated, because there was
  nothing to migrate (§2).
* The call **replaces** the set, dates included. A clerk who steps back to
  step 2 and changes one date does not leave the old row behind.
* `available` is NOT settable here and stays NULL — *not yet asked*, REQ-03.3's
  CHECK callout, drawn on `p076` as its own panel.

**The TypeScript is published too**, so lane D imports rather than retypes:

```ts
// 07-frontend/src/features/customers/serviceRequestEndpoints.ts
export type RequestedServiceInput = string | { code: string; requested_start?: string | null };

export async function setServiceRequestServices(
  id: string,
  services: RequestedServiceInput[],
  client?: ApiClient,
): Promise<ServiceRequestDetail>;
```

The existing call site (`ServiceRequestCapturePage.tsx` line ~592,
`setServiceRequestServices(id, next.services, client)` with `next.services:
string[]`) **still compiles unchanged** — deliberately, so this lane could land
without breaking lane D mid-edit.

### The three refusals, each BY NAME

There is no 500 on this path. Every refusal is a catalogue message key, and
each was exercised against the running product (§5 step 6).

| What was sent | HTTP | code | `message_key` | params |
|---|---|---|---|---|
| `requested_start: "next tue"` | 422 | `VAL-002` | `customers.serviceRequest.requestedStartNotADate` | `{service, value}` |
| the same code twice | 422 | `VAL-005` | `customers.serviceRequest.serviceRepeated` | `{service}` |
| a code the platform does not have | 422 | `VAL-005` | `customers.serviceRequest.serviceUnknown` | `{service}` |

Both new keys are in **all eleven catalogues** (`i18n_fanin.py`, +2 / −0 in each,
each translated in its own language per B14 rule 35). Neither sentence
interpolates the service code: rule 32 keeps internal codes off clerk-facing
copy, and the clerk can already see which row they are looking at.

⚠ **The duplicate refusal is new and it replaces a 500.**
`ux_sr_services_request_service` is UNIQUE on (request, service), so a repeated
code used to reach the database and come back as an `IntegrityError`. A list of
objects makes a repeat much easier to send than a list of bare codes did, so the
guard moved in front of the constraint.

---

## 4 · The read shape — what step 6 and the detail get back

Both live on `detail.location_and_services`:

```jsonc
{
  "services": [
    { "code": "electric", "requested_start": "2026-12-05", "available": null },
    { "code": "water",    "requested_start": "2026-12-05", "available": null },
    { "code": "sewer",    "requested_start": "2026-12-05", "available": null }
  ],
  "requested_start_agreement": { "count": 3, "agreed": "2026-12-05", "unset": 0 }
}
```

and the **job-level** date stays where it always was, on the header:

```jsonc
{ "header": { "requested_start": null } }     // `Connection date → — not given`
```

`services` is ordered by the catalogue's own `sort`, then code — so the screen
never sorts it and two screens cannot order it differently.

### `requested_start_agreement`, and why it is served rather than computed

`p080` draws **`Requested start → 05/12/2026, all three`**. A screen cannot say
*all three* from the list alone without deciding what *agree* means, and two
screens deciding that separately is how they come to disagree. So it is decided
once, on the server, in `service_request_reads._requested_start_agreement`.
**Three facts and no wording** — the sentence is lane D's, under rule 33's
six-word cap for a fact.

| field | what it is |
|---|---|
| `count` | how many services are on the request. **0 is a real answer** — a request that has not reached step 2, which is every one of the demo tenant's original eight. Nothing may divide by it. |
| `agreed` | the one ISO date when **every** service carries the **same non-null** date; `null` otherwise |
| `unset` | how many services carry no date |

**The four cases a screen has to tell apart, with the values it reads:**

| The request | `count` | `agreed` | `unset` | What `p080` draws |
|---|---|---|---|---|
| three services, all 5 Dec | 3 | `"2026-12-05"` | 0 | `05/12/2026, all three` |
| electric + water 5 Dec, sewer 19 Dec | 3 | `null` | 0 | list them |
| three services, nobody gave a date | 3 | `null` | **3** | `— not given` |
| electric no date, sewer 19 Dec | 2 | `null` | **1** | list them |
| step 2 not reached | 0 | `null` | 0 | nothing |

⚠ **ALL-UNSET IS NOT AN AGREEMENT.** Three services all saying *not given* must
never read as three services agreeing on a date. `agreed` is a date or it is
nothing, and `unset` is the only thing that separates row 3 from row 2 — a single
null could not.

---

## 5 · Proved against the running product, on the real demo tenant

`10-scripts/../laneF-bits/walk.sh`, against a lane-owned server on port 8097
reading `brazosbend`. **The worked example is `SR-26-0017`**, created by this
walk and **left in `p080`'s drawn state** so lane D can open it: three services,
all `2026-12-05`, and no `Connection date`.

```
── 1 · open a draft ──  SR-26-0017  (01a0a65f-1a89-741b-8adc-97f7712991bd)
                        Connection date on the job: None

── 2 · three services, each with its own start ──
   electric   2026-12-05   available=None
   water      2026-12-05   available=None
   sewer      2026-12-19   available=None
   requested_start_agreement: {'count': 3, 'agreed': None, 'unset': 0}

── 3 · the step-6 review pair, on ONE request ──
   Requested start  -> {'count': 3, 'agreed': None, 'unset': 0}
   Connection date  -> None (not given)

── 4 · all three on the same day — THE DRAWN CASE ──
   {'count': 3, 'agreed': '2026-12-05', 'unset': 0}
   …beside header.requested_start = None — which is p080's pair exactly,
   and which the old copy could not produce.

── 5 · the OLD flat shape still works, and means NO DATE GIVEN ──
   starts: [None, None, None]
   {'count': 3, 'agreed': None, 'unset': 3}

── 6 · the three refusals, each BY NAME and never a 500 ── (table in §3)

── 7 · a mixed list — one dated, one not ──
   [('electric', None), ('sewer', '2026-12-19')]
   {'count': 2, 'agreed': None, 'unset': 1}
```

⚠ **`SR-26-0017` is a real row on the shared demo tenant and its number is burnt
permanently.** `BR-CUS-093(a)` says gaps are normal and nothing renumbers; it was
created as a DRAFT and **nothing was approved, refused or submitted**, per the
wave brief.

---

## 6 · `DEF-CUS-5412` — a 500 this lane uncovered and fixed

**`GET /service-requests/{id}` was a 500 for any request that HAS services**, on
the branch, before this lane touched it.

`request_jobs._service_codes` read `row.service_code`. There is no such field:
`ServiceRequestService.service` is a FK to the platform catalogue, so the code is
`row.service.code`. It raised
`AttributeError: 'ServiceRequestService' object has no attribute 'service_code'`
inside `reads.detail()`.

**Introduced** `883206ca`, 2026-09-15, *"Approving a service request now raises
the job (CR-094-BRC01 wave 1 lane A)"* — dated with
`git log -S "row.service_code" -- 06-backend/apps/customers/request_jobs.py`.
**Not this lane's commit, and this lane is why it became visible.**

**Why nothing could see it, which is the part worth keeping:** a list
comprehension evaluates the attribute only when the queryset yields a row, and
`service_request_services` held **zero rows** in the demo tenant and in every
suite — `sample_data.py` never calls `set_services`. An empty queryset makes
every attribute name inside the loop unfalsifiable. That is hard-won law 7's
*incapable of failing*, and no gate in this repo can look at it. **The first lane
to write a service row is the first to see it.**

Fixed here (one expression, plus `select_related("service")` so it does not walk
the catalogue once per row) and guarded by
`test_the_whole_detail_can_be_read_with_services_on_the_request`, **proved RED
against the unfixed line in a clean worktree at the tip**, through `pytest` —
the harness that runs it.

---

## 7 · What this lane did NOT build, and why

* **The screen.** `ServiceRequestCapturePage.tsx` is lane D's for this wave and
  was not edited. Two lines were added to `ServiceRequestCapturePage.test.tsx`
  and two to `ServiceRequestDetailPage.test.tsx` — the new payload field in each
  fixture, because `requested_start_agreement` is required on
  `ServiceRequestLocation` and `tsc` was red without them. Lane D should expect
  those two lines and keep them.
* **The services multiselect control** — lane D's.
* **The premises search** — lane E's.
* **Step 5's fees and step 6's message-and-template block** — both held on a PO
  decision. Untouched.
* **A data migration.** None was written and none was owed: 0 rows (§2). Had
  there been rows they would already hold the job's date, which under
  `BR-CUS-1070` reads correctly as *this service was wanted then*.
* **A schema change.** The column has existed since `customers/0017`. **No
  migration number was allocated by this lane** and none should be read into it.
* **`DEF-CUS-5195` is NOT closed.** Its `surface` is
  `ServiceRequestCapturePage.tsx` and it names both the multiselect and the
  per-service table; the screen half is lane D's. This lane fixed the data half
  and left the row OPEN deliberately.

---

## 8 · Proof table

| What | Command | Result |
|---|---|---|
| New tests | `JOBS_EAGER=false pytest tests/test_cr094_per_service_starts.py --reuse-db` | **16 passed** |
| The same file, before the code moved | as above, on the pre-change tree | **14 failed, 1 passed** — `AssertionError: assert ['2026-11-02', '2026-11-02'] == [None, None]` and `KeyError: 'requested_start_agreement'` |
| `DEF-CUS-5412`'s guard, against the unfixed line | the same, in a clean worktree at `62a81b3f` | **RED**: `AttributeError: … has no attribute 'service_code'` |
| Neighbouring backend suites (22 files) | `JOBS_EAGER=false pytest … --reuse-db` | **23 failed, 341 passed, 3 skipped** — and the SAME 23 fail in a clean worktree at the same base, name for name (§9) |
| Typecheck | `07-frontend/node_modules/.bin/tsc --noEmit` | **clean** — and it was shown able to fail first (two fixtures missing the new field) |
| Frontend tests | `vitest run` on the two request pages, the detail DOM test and `routeBUtilities.test.ts` | **106 passed** |
| Locale parity | `i18n_fanin.py` | **+2 / −0 in each of the eleven** |
| OpenAPI | `export_openapi` + a one-path splice | **+1 / −0** — only this endpoint's `description` |
| End to end | `walk.sh` against the running product on `brazosbend` | §5 |
| Gates | `run_gates.py --changed <base>` | §9 |

---

## 9 · Reds, dated

**Every red below was measured in a clean worktree at the same commit, with none
of this lane's files present** — which is stronger than an opinion about whether
it looks related.

* **23 backend failures across the 22 neighbouring suites.** Both sets counted
  and compared name for name: **identical**. `test_w5_eligibility_and_deposit_carry`
  (11), `test_w5_move_worklists` (4), `test_w5_move_in_out_cases` (3),
  `test_cr031_service_request` (2, both *oldest first* list-order assertions),
  `test_cr005_numbering_reaches_records` (1),
  `test_us_wrk_039_from_flows` (1).
* **`test_cr031_service_request_api.py::test_the_detail_states_what_it_cannot_answer`**
  — fails at the clean tip `62a81b3f` with none of this lane's files present. A
  sibling retired a stated absence on 2026-09-15 (the driving licence) and this
  assertion still counts the old list.
* **Gates.** Every gate that ran in BOTH trees returned the same verdict; **no
  gate got worse**. Three gates fail for this lane that the baseline run did not
  select — `G78` (work), `G79` (integrations), `G115` (runbooks) — all in modules
  this lane does not touch; `--changed` simply chose a different subset. `G98`
  (eslint), `G103`, `G105`, `G106`, `G107`, `G114`, `G116` name no file of this
  lane's.
* **`06-backend/openapi/schema.json` is stale at the tip and was not fixed
  here.** Regenerating it whole would have published another lane's unexported
  path (`/billing/print-sets/bills`) — law 11 mechanism five — so **only this
  endpoint's entry was spliced in**, byte-stability of the exporter's own
  formatting asserted first.

---

## 10 · Where the ruling is written

* `12-governance/02-decision-log.md`, 2026-09-15 — the decision with its worked
  figures, written and pushed **before** the code (step W).
* `04-docs/05-modules/03-customers/02-business-rules.md` — `BR-CUS-1070`.
* `12-governance/14-id-reservations.md` — why the id is 1070 and not 1055.
  (`BR-CUS-1055` was taken by a sibling in migration
  `0049_br_cus_1055_units_on_property` while this lane worked, which is the
  reservation earning its keep.)
* `12-governance/10-defect-log.csv` — `DEF-CUS-5412`.

**Nothing here needs the PO.** Law 13 was applied before deciding: the decision
log and the open questions were grepped for *requested start*, *per-service* and
*requested_start*, and neither holds a ruling on it; the drawing answers the
question, so the judgment is the lane's and is recorded with its figures. **No
`OQ` was minted.**
