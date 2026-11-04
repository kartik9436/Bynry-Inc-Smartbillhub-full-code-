# CR-094-BRC01 wave 1 lane A — approving a request RAISES THE JOB

**What this lane committed to:** the PO's ruling of 2026-09-15, verbatim —
*"pass all information to create the new connect requets or move -in request
based on selction"*. The drawing's button reads **`Approve and raise the
build`**, and its callout on p082 reads *"Approving this is what creates the
job."*

**Before:** approving moved the state to `Approved`, stamped who decided and
when, wrote one history line and one audit row, **and created nothing**. The
five downstream queues were fed by a clerk retyping the job.

**After:** approving creates the job the outcome names, the job carries the
request's id, and the Approve modal has a published shape to render.

**No screen was touched by this lane.** Wave 2 builds the modal from what is
published here.

---

## 1 · Which blueprint pages were read AS IMAGES, and at what scale

`05-prototype/02 Accounts Menu Blueprint.pdf`, rendered at **scale 2** into
`/tmp/…/scratchpad/acct/`, read with the Read tool as images (B14 rule 42 — a
screen is built from the drawing as an image; extracted text is an index, never
the specification):

| Page | Read as an image | Scale | What it settled |
|---|---|---|---|
| `p082.png` | ✅ | 2 | The register's row for each outcome, the `APPROVED, NOT STARTED · no job raised yet` tile, and the request's own screen carrying the callout *"Approving this is what creates the job. A request resolves to one of five outcomes and this one is a new connection, so approval raises a build on the New connects tab and links it back here."* |
| `p083.png` | ✅ | 2 | The Approve modal's head (`Approve SR-26-0001` / *"This creates real service and real charges"*), `WHAT IS THIS REQUEST?` and the first two radios with their consequence lines. Also the FEES block — quoted $130.00, collected $25.00, **outstanding $105.00** — and the callout *"The money does not gate approval and the documents do."* |
| `p084.png` | ✅ | 2 | The remaining three radios and their consequence lines, *"Nothing is preselected, deliberately"*, the whole `WHAT APPROVING WILL DO` table (five `THEN`/`WHAT` rows) and the footer `Cancel` / `Approve and raise the build`. |

**No higher-scale render was needed** — every line of the consequence table and
every radio's sub-line was legible at scale 2.

### The five drawn consequence lines, transcribed from the images

| Radio | The drawing's own words |
|---|---|
| A new connection | *"Raises a build on the New connects tab, linked back to this request."* |
| A move-in | *"Opens an account on a unit that already has service."* |
| A move-out | *"Closes an account and frees its unit."* |
| A transfer | *"One customer, a different address of ours."* |
| A disconnect | *"Raises a case and starts the notice ladder."* |

### The drawn `WHAT APPROVING WILL DO` table, transcribed

| THEN | WHAT |
|---|---|
| Now | This request becomes **Approved** and the outcome is recorded against your name |
| Now | A build is raised on the New connects tab, naming this request |
| Now | The $105.00 still outstanding here travels with it |
| Next | The build's own wizard asks for units, services, plans and charges |
| Not now | No account opens, no meter is fitted, nothing is energised |

---

## 2 · THE PUBLISHED SHAPE — what wave 2 renders and must not compute

**Two doors serve the same function, so the sentence a clerk reads before
pressing the button and the row the tab shows afterwards cannot disagree.**

* `GET /service-requests/{id}/approval-preview?outcome=<one of five>`
* the detail's **decision tab**, key `what_approving_will_do`, **one preview per
  outcome keyed by outcome**, so the modal redraws as a radio moves with no
  round trip.

Both are `apps/customers/request_jobs.approval_preview(request, outcome)`.

### A worked example — `SR-26-0001`, outcome `new_connection`

```json
{
  "outcome": "new_connection",
  "known": true,
  "creates": {
    "kind": "connection",
    "table": "connections",
    "module": "metering",
    "queue": "new_connects",
    "state_it_lands_in": "draft",
    "named_by_series": "connection",
    "names_this_request": true,
    "drawn_consequence": "raises_a_build_on_the_new_connects_tab",
    "raises_a_row": true,
    "absence": null,
    "blockers": []
  },
  "carries": {
    "request_no": "SR-26-0001",
    "applicant": "Miller, Sarah",
    "premises_id": "…", "unit_id": "…",
    "requested_start": "2026-05-12",
    "services": ["electric", "water", "sewer"],
    "money": {
      "outstanding": {"amount": "105.0000", "display": "105.00", "currency": "USD"},
      "quoted":      {"amount": "130.0000", "currency": "USD"},
      "collected":   {"amount": "25.0000",  "currency": "USD"},
      "travels": "by_the_link",
      "copied_onto_the_job": false,
      "gates_approval": false
    }
  },
  "rows": [
    {"then": "now",     "what": "request_becomes_approved_and_recorded_against_you"},
    {"then": "now",     "what": "job_is_raised_naming_this_request",
                        "queue": "new_connects", "kind": "connection"},
    {"then": "now",     "what": "the_outstanding_travels_with_it"},
    {"then": "next",    "what": "the_jobs_own_wizard_asks_for_the_rest"},
    {"then": "not_now", "what": "no_account_no_meter_nothing_energised"}
  ],
  "not_now": ["no_account_opens", "no_meter_is_fitted", "nothing_is_energised"]
}
```

**For `move_in` and `move_out` the second row is different**, and that is the
whole of §4 below:

```json
{"then": "now", "what": "no_job_row_is_raised", "queue": "move_ins",
 "kind": "move_in",
 "absence": {"code": "move_wizard_is_the_record",
             "br_ref": "BR-CUS-150 · BR-CUS-152 · B18 §5.5.2",
             "detail": "…"}}
```

⚠ **`what` AND `then` ARE KEYS, NEVER SENTENCES.** Server text does not reach a
customer screen (the 2026-08-19 ruling, G32/G33), so the words are the
catalogue's and wave 2 mints them. `detail` on an absence is the platform's own
long-form reason and belongs in the register, not on the modal — B14 rule 33:
rationale is **zero words on screen**.

### The approve response

`POST /service-requests/{id}/approve` now returns the detail **plus `job`**,
which holds EITHER `raised` OR `not_raised`, never both and never neither:

```json
{"job": {"raised": {"kind": "connection", "table": "connections",
                    "module": "metering", "queue": "new_connects",
                    "id": "…", "ref": "CON-26-0131", "state": "draft",
                    "names_this_request": true, "warnings": []}}}
```

```json
{"job": {"not_raised": {"code": "no_premises_resolved",
                        "br_ref": "BR-MET-1024", "detail": "…"}}}
```

The five refusal codes: `no_premises_resolved` · `no_live_account` ·
`job_door_refused` · `job_door_unpublished` · `job_already_linked`, plus the
move absence `move_wizard_is_the_record`.

---

## 3 · WHAT EACH OUTCOME NOW CREATES, and through whose door

| Outcome | Row created | Table | Owner | Door called | Lands in |
|---|---|---|---|---|---|
| new connection | a build | `connections` | **metering** | `seams.raise_connection_build` → `metering.connections.create_connection` | `draft` |
| move-in | — see §4 | `move_records` | customers | — | — |
| move-out | — see §4 | `move_records` | customers | — | — |
| transfer | a transfer job | `transfers` | customers | `transfers.start_transfer` | `scheduled`, step 1 of 5 |
| disconnect | a case | `disconnect_cases` | customers | `disconnects.open_case` | `notice_sent` |

**Nothing writes another module's table.** `connections` is metering's, so it
goes through a published seam and metering's own door — which allocates the
`CON-` number, resolves the premises with the 404-never-403 refusal, writes the
`connection.created` audit row and reports its own warnings. A second creator in
`customers` would have been a second place `BR-MET-1024`'s mandatory-owner rule
could be relaxed.

**⚠ `create_connection` has taken a `service_request_id` since `CR-070` wave B
and NOTHING HAS EVER PASSED ONE.** Its own docstring says *"Prefilled from an
approved request where there is one"* — the door was built for a call that did
not exist, and `connections.request_id` has been NULL on every row of every
tenant. `DEF-MET-5397`.

### What TRAVELS into the job, and what could not

| Fact | Where it lands | Where it does not, and why |
|---|---|---|
| the request itself | `connections.request_id` · `transfers.request_id` · `disconnect_cases.request_id` | — |
| the resolved premises | `connections.premises_id` | a transfer does not move address (`BR-CUS-1030`); a case is anchored on the account |
| the requested start | `connections.target_activation` | `transfers.out_date`/`in_date` are the wizard's step 3, not the application's ask |
| the resolved unit | — | `connections` has no unit column; units are the build wizard's step 5 |
| the services asked for | — | `connection_services` is written at `commit_connection` (`BR-MET-112`: *"nothing is written until step 9"*) |
| the applicant | — | the job reads it by walking `request_id` |
| **the outstanding money** | **read through the link** | see below |

⚠ **THE MONEY TRAVELS BY THE LINK AND IS NEVER COPIED.** `$105.00` is
`fee_total_to_collect`'s `outstanding` — quoted $130.00 less $25.00 taken at the
counter (`BR-CUS-090`). **None of the four tables has a column that means
that**, and adding one would be the exact fault two of this repo's own files
already refuse in their own words: *"a second copy of a fact that already has an
owner is how two numbers come to disagree"* (`moves.py` §1) and *"a stored
`deposit_carried` would read as money that moved on a path where nothing
moved"* (`Transfer`). `connections.quote_total` is the BUILD's quote;
`disconnect_cases.amount_owed_at_open` is the ACCOUNT's AR balance. Neither
means the application's fee. So the figure stays on the request, the job names
the request, and `request_jobs.carried_money()` is the ONE reader — which is
what lets the modal and the job screen print the same $105.00.

---

## 4 · WHAT I DID NOT BUILD, AND WHY — move-in and move-out raise no row

**This is the biggest finding of the lane and it is a judgment, recorded rather
than guessed.** `DEF-CUS-5398`.

The brief and the ruling both name `move_records` as where a move-in and a
move-out go. **Checked against the code before building on it** (build skill §0
— a written rule is a claim about the product, not evidence), and three signed
things say that table cannot be the raised job:

1. **It is the record of a move that HAS HAPPENED.** `moves.MoveRecord`'s own
   docstring: *"a move record is written by a flow that has already committed,
   in the same transaction, so there is no in-flight moment for it to
   describe"*, and *"⛔ NOTHING UPDATES A ROW OF THIS TABLE"* (`BR-CUS-152`). A
   row written at approval would state that somebody performed a move-in that
   nobody has performed — and would be **duplicated** when the wizard runs, on a
   table whose correction path is a third row.
2. **It requires the account the job exists to create.** `account_id` is NOT
   NULL with `on_delete=PROTECT`. Raising a move-in would have to open an
   account, and the drawing forbids exactly that in as many words: *"No account
   opens, no meter is fitted, nothing is energised."*
3. **A case table for a move is ruled out by the design it would come from.**
   `move_reads.STEP_HAS_NO_STORE` records B18 §5.5.2's own footnote — *"a
   move-in is short enough that the wizard is the record"*.

**So approval does, for these two, exactly what the drawn table's OTHER rows
say** — the request becomes Approved, the outcome is recorded against the
clerk's name, the money stays readable — and the missing row is **stated by
name** in the same payload the modal renders, so a clerk reads an honest absence
instead of a promise nothing keeps.

**The link is still built and is not a slot nothing fills.**
`move_records.request_id` lands in the same migration, `moves.record_move` takes
`service_request_id`, and `services.move_in` / `move_out` pass it — so the
wizard fills it at the moment the move commits. That completes `BR-CUS-080`'s
child half for moves properly: today the Move-ins tab finds the request by
matching `outcome_ref` against an **account number**
(`move_reads._requests_by_account_no`), whose own docstring records that two
vocabularies already disagree there.

**What would close this properly** is a product judgment — whether a move gets
an in-flight case row of its own, against B18 §5.5.2's footnote that says it
should not. Routed as `DEF-CUS-5398`, not decided by this lane.

---

## 5 · TWO CONTRADICTIONS BETWEEN SIGNED SURFACES, FOUND AND FILED

Neither was fixed here. Both change what a clerk can DO, so both are routed.

**`DEF-CUS-5399` — the money DOES gate approval today, and the blueprint says it
must not.** Two signed screens disagree:

* `REQ-03.5` (B19, CR-031's screenshots): *"the review step lists the unpaid fee
  as a blocking condition. **Nothing is refused — it simply cannot be approved
  yet.**"* — built as `fee_condition`, which BLOCKS on `$105.00`.
* The Accounts blueprint p083, read as an image: *"**The money does not gate
  approval and the documents do.** $105.00 outstanding is finance's to
  reconcile; an unchecked identity document is this clerk's."* — and p084 draws
  the approval going ahead with that $105.00 still outstanding.

Measured: a request with `$105.00` outstanding is refused
`BIZ-COMPLETENESS (customers.serviceRequest.condition.feeOutstandingAmount)`.
The conformance measurement recorded that drawn line as **Built** because the
request it measured had no outstanding fee, so the disagreement was invisible
from both sides. `test_the_outstanding_money_travels_by_the_link_and_is_never_copied`
pins the product AS BUILT and names the drawing's sentence beside it, so the day
the rule moves the case goes red and says which of the two changed.

✅ **RESOLVED 2026-09-21 — THE BLUEPRINT WON, AND THE CASE ABOVE IS WHAT FOUND
IT.** PO, verbatim: *"make application fees optional - so that we can approve
it"*. `fee_condition` now reports rather than blocks, so p083's *"The money does
not gate approval and the documents do"* is what the product does and
`REQ-03.5`'s second sentence is SUPERSEDED. `BR-CUS-090` clause (1) carries the
amendment with its date.

⛔⛔ **SUPERSEDED 2026-09-23 — THE FEE GATES APPROVAL AGAIN (`OQ-CUS-12617` CLOSED, `DEF-CUS-6420`).** PO, verbatim: *"we already told you - either fee is paid or waived - no other condition"*. Approve waits until the application fee is **paid in full or waived**; a part payment holds it on the REMAINDER (quoted $130.00, taken $25.00 → *✗ Fee · $105.00 unpaid*, Approve off). A utility with no fee lines is untouched, and the counter still accepts a short payment and never refuses — the desk half of `BR-CUS-090` stands. The paragraph above is kept as the record of 2026-09-21. `test_the_outstanding_money_travels_by_the_link_and_is_never_copied` FLIPS with it: the approval is refused naming $105.00, and goes through once the rest is waived.

⚠ **THE HOLD-EXPIRY CASE DID EXACTLY WHAT IT WAS WRITTEN FOR AND IT IS WORTH
SAYING SO** (hard-won law 2's second half). It went RED the moment the rule
moved, named which of the two screens had changed, and was REWRITTEN rather than
deleted — it now asserts the approval goes through **with the $105.00 still
outstanding** and reads the figure back through the same reader afterwards. A
hold with no such test is a promise nobody is keeping.

⚠ **AND THE PO CORRECTED THE CASE ITSELF THE SAME DAY:** *"in practical this
does not ahppen … $20 or $0 - some utilities will not take applciation fees
also"*. The `$105.00` part payment this section is built on is **not what an
application fee does**; it is paid once, waived, or never charged. The
measurement stands, the ranking does not.

**`DEF-CUS-5404` — a disconnect request cannot be approved because the
applicant's own arrears block it.** The arrears condition blocks approval
whenever the matched customer owes money, and a disconnect is the one outcome
where they are expected to. Nothing tested the two together: every arrears test
uses a new-connection request and every disconnect test starts from the
collections ladder rather than from an application.

---

## 6 · THE APPROVAL STANDS EVEN WHEN THE JOB CANNOT BE RAISED

`route()` already settled this posture for field work (`BR-WRK-055`): *"the
state moves in its own committed transaction FIRST and the raise happens after
it, so a field module that is down, unpublished or refusing cannot hold an
approved application in `approved` for ever."* This follows it exactly rather
than inventing a second posture.

The four real refusals, each measured rather than imagined:

* a new connection whose address resolved to **no premise record** —
  `connections.premises_id` is NOT NULL, and creating the premises needs the
  mandatory owner `BR-MET-1010` requires and an application does not carry;
* a transfer or a disconnect on a request with **no live account**;
* a disconnect where **the ladder is not running** — a protection in force, a
  payment plan, or nothing owed;
* **any door unpublished** in this deployment.

⚠ **The exception's CLASS is reported in the refusal detail, and that is not
decoration.** A broad catch turns OUR bug into something that reads exactly like
the product refusing — hard-won law 7's *check that cannot fail* wearing a
business face — and **it happened to this lane on its first run**: `could not be
raised: 'id'` was a `KeyError` on `case_payload`'s key (`case_id`, not `id`),
not a refusal. It now reads `could not be raised: KeyError: 'id'` and is logged
with a traceback.

---

## 7 · THE GUARD THE RAISE MUST NOT BYPASS

**Approval is blocked until every required document is checked, and that is
unchanged — but it MOVED.** `approve_and_raise` is a second door onto the
approval, and a second door that skipped the two drawn guards is exactly how a
documents-blocked request would get a build raised for it with nothing ever
saying so. The guards now live in `_refuse_unless_approvable`, which **both**
doors call first. `test_an_unverified_document_still_blocks_and_raises_nothing`
is the case that holds it.

---

## 8 · PROOF

### Red first, in the harness that runs it

Every case was written and run against the branch **before**
`apps/customers/request_jobs.py` existed, through `pytest` — the harness that
will run them, not a script calling the functions directly (`DEF-GOV-3733`'s
shape). The run:

```
FAILED tests/test_cr094_approval_raises_the_job.py::test_approving_a_new_connection_raises_a_build
FAILED …::test_the_requested_start_travels_onto_the_build
FAILED …::test_approving_a_transfer_raises_a_transfer_job
FAILED …::test_approving_a_disconnect_raises_a_case_on_the_notice_ladder
FAILED …::test_approving_a_move_says_by_name_that_no_row_is_raised[move_in]
FAILED …::test_approving_a_move_says_by_name_that_no_row_is_raised[move_out]
FAILED …::test_the_move_record_names_the_request_when_the_wizard_commits
FAILED …::test_the_outstanding_money_travels_by_the_link_and_is_never_copied
FAILED …::test_an_unverified_document_still_blocks_and_raises_nothing
FAILED …::test_one_approval_raises_one_job_even_when_called_twice
FAILED …::test_every_raise_writes_an_audit_row
11 failed, 4 passed
```

Green after: **15 passed** in 22 s.

### What would make these pass wrongly — asked before trusting the green

* **A count taken before the approval.** Every case counts rows NAMING THIS
  REQUEST, on a request the case created itself.
* **An assertion on the RESPONSE rather than the database.** Each case reads the
  row back out of its table and asserts the request id is on it.
* **A move case passing because nothing happened.** It asserts the NAMED code as
  well as the empty table, so a silent no-op fails.
* **An audit assertion that cannot see the row.** The first draft queried
  `AuditLog` and got `[]` — the shared fixture replaces the platform sink with a
  list for the length of a test, so a table query passes or fails for a reason
  that has nothing to do with the code under test. It asserts against the
  capture sink now.

### The proof table

| What | Command | Result |
|---|---|---|
| The new suite | `pytest tests/test_cr094_approval_raises_the_job.py --reuse-db` | **15 passed** |
| The neighbours | `pytest tests/test_cr031_service_request.py tests/test_cr031_service_request_api.py tests/test_cr039_wd_move_records.py tests/test_w7_transfers.py tests/test_w7_disconnects.py tests/test_w6_connection_detail.py --reuse-db` | see the lane report |
| Migration state | `makemigrations --check --dry-run` | see the lane report |
| Gates | `run_gates.py --changed <base>` | see the lane report |

---

## 9 · WHAT THIS LANE LEFT

| Left | Where it is routed |
|---|---|
| The Approve modal itself — no screen was touched | wave 2, from §2's published shape |
| A move-in / move-out queue row | `DEF-CUS-5398` |
| Whether the unpaid fee may block approval | `DEF-CUS-5399` — **CLOSED 2026-09-21, PO ruling: it may not** |
| Whether a disconnect request's own arrears may block it | `DEF-CUS-5404` |
| No back-fill of `request_id` on existing jobs | deliberate — migration 0048's docstring says why, and why a back-fill that did not walk tenants would report success and change nothing (`DEF-BIL-5382`'s shape) |

---

## 10 · WALKED THROUGH THE REAL API, AND IT FOUND A DEFECT NOTHING ELSE COULD

**A test with its own fixture proves the fixture** (build skill §1's API bar), so
one approval was walked end to end against a running server on port 8077, on the
`brazosbend` demo tenant, **on requests this lane created itself**. The six real
service requests were read before and after and are untouched:
`SR-26-0001 more_info` · `SR-26-0003/0004/0005 under_review` ·
`SR-26-0007/0008 submitted`, all with no outcome, before and after.

### The positive path, read back FROM THE DATABASE

```
POST /api/brazosbend/service-requests                       → SR-26-0016
POST …/documents  ·  submit  ·  pick_up  ·  resolve-address ·
     customer-link  ·  decision{outcome:new_connection}  ·  documents/{id}/verify
GET  …/approval-preview?outcome=new_connection              → the drawn table
POST …/approve                                              → 200
```

The approve response's `job`:

```json
{"raised": {"kind": "connection", "table": "connections", "module": "metering",
            "queue": "new_connects", "ref": "CON-26-0129", "state": "draft",
            "names_this_request": true, "warnings": []}}
```

And the two rows, read out of PostgreSQL rather than out of the response:

```
connections       CON-26-0129 | draft    | request_id 01a0a64f-b8cb-…-3325ffa7ff6f
service_requests  SR-26-0016  | approved | new_connection | connection | CON-26-0129
```

The move-in preview on the same request, live:

```
raises_a_row: False | queue: move_ins
absence code: move_wizard_is_the_record
row 2 of the drawn table: no_job_row_is_raised
```

### What the walk found — `DEF-CUS-5406`, this lane's own defect

**On the first walk, a request whose address had not resolved came back
`job_door_unpublished` — *"This deployment publishes no door for a
connection"*.** It should have said `no_premises_resolved`. Every raiser
returned a bare `None` for every cause it had, and `raise_job` turned `None`
into one code.

**Both unit tests passed**, because the case covering that path asserted the
code with an `or` across three alternatives — so it accepted the wrong answer
and could not fail. That is hard-won law 7's *a check you cannot describe a
false pass for*, described in this very test file's own docstring and then
shipped anyway.

**The two answers go to different people**, which is why it matters: *resolve
the address, then approve* is something a clerk can act on; *this deployment
publishes no door* is something only an engineer can, and printing the second
over the first sends the wrong person to fix it.

Fixed: every raiser now returns either a job or a NAMED refusal carrying its own
`code` and `br_ref`. The test asserts one code exactly, and was proved RED on the
old behaviour first:

```
E   AssertionError: assert 'job_door_unpublished' == 'no_premises_resolved'
```

Confirmed live afterwards:

```json
{"not_raised": {"code": "no_premises_resolved", "br_ref": "BR-MET-1024",
  "detail": "A build is written against a premise record and this request's
             address has not resolved to one. Resolve the address, or create
             the premise, then the build can be raised."}}
```

**Nothing but a walk of the real API would have found this**, because the
sentence a clerk reads is not something any check in this repo looks at — which
is hard-won law 6 in one sentence.

### One thing fixed on the way that was not this lane's

The shared demo database was returning **HTTP 500 on `GET /service-requests`** —
`column service_requests.date_of_birth does not exist`, because
`customers/0050_br_cus_092_dob_and_drivers_licence` was on the branch and had
not been applied. Every lane reading a service request on that tenant was
blocked. Applied (three nullable columns and an index, no data touched), and the
list works again. Reported rather than left, per the build skill's §10: a red
that stops the next lane working is yours the moment you find it.

### Requests left on the demo tenant by this walk

`SR-26-0010` … `SR-26-0016`, all named **Lane A Walkthrough** with
*"lane A end-to-end proof, safe to delete"* in their own words. `SR-26-0016`
carries the build `CON-26-0129`. The six real requests were never written to.
