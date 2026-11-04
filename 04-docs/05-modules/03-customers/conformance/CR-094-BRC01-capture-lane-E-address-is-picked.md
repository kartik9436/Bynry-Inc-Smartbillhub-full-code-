# CR-094 capture wave · lane E — the address on a service request is PICKED, not typed

**Date** 2026-09-15 · **Branch** `claude/gifted-johnson-top7zn` · **Base** `8c5edc0f`
**Ruling built** `12-governance/02-decision-log.md`, 2026-09-15, *"RULED: THE CAPTURE
WIZARD'S ADDRESS STEP IS A SEARCH OF THE PREMISES REGISTER…"*, clause (1) and clause (2).

PO verbatim, both clauses:

> *"if we have unit or street address then we should take it from premises/Unit - it
> means its a search and if not foudn them alow user to add them"*

> *"if unit is found then it is gi=oing to be mobve in mostly and all asset - which we
> will take acre in move in request"*

---

## 1 · The page read as an IMAGE

| Page | Scale | Read with |
|---|---|---|
| `p077.png` | 2 | the Read tool, as an image |

`p077` draws step 3 entire: the two address boxes, the five-box form as it stands, the
unit count, the billing-address pair, the `What the register matched` table
(`LOOKED FOR` / `MATCHED` / `CONFIDENCE`), three dashed absence panels and one red one.
Scale 2 was legible throughout; no higher render was needed.

Three sentences off that page are what this lane built to, and each is quoted where the
code implements it:

* *"The address is the APPLICANT'S, not a record. It is matched against the premises
  register below it and the match is shown beside it — never written over it."*
* *"The match is evidence, never a decision."*
* **in red** — *"An address that matches nothing is not refused. It is flagged as having
  no premises on record, and the request carries on — because a new connection at a
  field with no address yet is exactly the job this wizard exists for."*

## 2 · Before and after

| | Before | After |
|---|---|---|
| Finding an address | No search anywhere on this step. Five free-text boxes, three of which had no column (`DEF-CUS-5385`) | `GET /premises/picker?q=` — the register searched by street, premise number or town, **server-paginated in SQL**, each premises with its units |
| Naming the record | A fuzzy resolver matching on UNIT references only. `500 Main St` — a real property with 31 units — resolved to *no premise record* | The clerk PICKS. `picked_premises_id` / `picked_unit_id` on the capture door |
| City / state / ZIP | No column, and none may be added (hard rule 8; a sibling lane was stopped an hour into adding three) | `premises.city` / `.state` / `.postal_code` on the read payload, read by WALKING, named as the premises' |
| What the screen could show | `RESOLVED TO 01a0a444-5ad2-7e88-be8a-bdb8aa86c05e` (`DEF-CUS-5386`, B14 rule 31) | `premise_no` and `unit_no` beside the ids |
| A building with no unit named | `no_premise` — the add-a-premises path opened over a property that exists | `premise_no_unit`, the fifth resolution kind |
| Assets on a found unit | — | Still nothing, deliberately. Clause (2) puts them on the move-in request |

## 3 · What was published — the contract lane D builds against

### `GET /api/{tenant}/premises/picker`

Query: `q` (≥ 2 characters; shorter is ignored, never refused — `BR-SHL-011`), plus the
standard `page` / `per` (50 · 100 · 200 · 500 · 1000, default 50).
Role: any tenant role, like the S14 list. It is a read of the register.

Worked, against the demo utility `brazosbend`:

```
GET /api/brazosbend/premises/picker?q=Main&per=50

{
  "count": 1,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": "01a0a444-5b1c-736b-917f-0d84a6882e02",
      "premise_no": "P-00053",
      "address_line": "500 Main St",
      "city": "Silver Creek",
      "state": "TX",
      "postal_code": "78611",
      "units": [
        {"id": "01a0a444-642e-7236-8a10-eafb536399f2", "unit_no": "SCW-U-324",
         "label": "Common area", "is_common_area": true},
        {"id": "01a0a444-5b24-7416-b982-b80cffbea279", "unit_no": "SCW-U-208",
         "label": "Unit 100", "is_common_area": false},
        {"id": "01a0a444-5b4f-72f1-945b-26fa654cb75f", "unit_no": "SCW-U-209",
         "label": "Unit 200", "is_common_area": false}
      ]
    }
  ]
}
```

`P-00053` really has **31 units**; three are shown here. `premise_no` and `unit_no` are
the visible values (B14 rule 31); the `id`s are for the pick and never render.

**There is no meter, service, asset or account anywhere in this payload, and adding one
is undoing a ruling.** `test_nothing_about_the_meters_or_services_on_a_unit_is_served`
fails the day somebody does.

### The pick, on the capture door

`POST /service-requests` and `PATCH /service-requests/{id}` accept two new names:

| name | meaning |
|---|---|
| `picked_premises_id` | the building the clerk chose off the picker |
| `picked_unit_id` | the unit, where there is one. Optional |

Four shapes:

| sent | stored |
|---|---|
| neither | nothing changes — a PATCH about the fee does not clear a pick |
| both null | the pick is undone: `unresolved`, all four columns null |
| a premises, no unit | `premise_no_unit`, `no_premise_flag: false` |
| a unit (its building comes with it) | `served_vacant` or `served_occupied` |

Refusals: a unit at another address answers
`customers.serviceRequest.pickedUnitNotAtPremises`; an id belonging to another tenant
gets metering's own 404-never-403. `resolution_kind` is **still** refused as an unknown
field — the clerk names a row, the server decides what the row means. Neither name is in
`PORTAL_CAPTURE_FIELDS`, so a guest on the public form is refused by name.

### The read payload — NOT THIS LANE's, and that is a correction

**Lane E built a nested `premises: {premise_no, address_line, city, state, postal_code}`
and `unit: {unit_no, label}` on `location_and_services`, and then REMOVED it.**

While both lanes were still unpushed, `CR-094-BRC01` wave 1 **lane B** was found
building the same fact under different names: `resolved_place()` serving
`resolved_premises_no`, `resolved_unit_no`, `resolved_premise_address` and
`premise_locality`, on both the head and the location tab, with its own tests and a
full docstring. `premise_locality` is **already this repo's word** for a walked
locality — it is what `DEF-CUS-3653`'s repair put on the account header.

Two names for one fact is the thing this repo punishes hardest, and a payload carrying
both would have handed lane D two ways to read one value. So lane E's version came out
and `service_request_reads.py` is **byte-identical to the tip** in this lane's commit.
Lane B's shape is the contract; lane D builds against that.

**What lane E contributes to that half instead, and it is not nothing:** until the pick,
`resolved_premises_id` was only ever filled FROM a matched unit. Lane B's own code says
so, calling its premises-only branch *"unreachable through today's resolver"*. A clerk
picking a building makes it reachable, and two cases here assert the walk ARRIVES from a
picked premises with a real value (`Katy · TX · 77494`), plus one that asserts
`service_requests` grew no `city`, `state`, `postal_code`, `address_line` or `zip`.

⚠ **ONE HANDOVER TO LANE B, NOT ACTED ON HERE:** `resolved_place` stamps
`resolved_match = "exact_reference"` on the premises-only branch. Under a PICK that is
no longer what happened — a clerk chose the row — so a second value (`picked`) belongs
there. It is lane B's file and its own docstring says a new matcher adds a value rather
than changing what this one means.

### The not-found route

The request carries on flagged (`no_premise_flag: true`, `resolution_kind: no_premise`),
and *"allow user to add them"* is the premises register's **own** create at
`/:tenant/premises/new` (S16 · PRM-07, `CR-089` wave B). **No write seam was added and
none may be** — the reasoning is in the decision-log row and in `address_picker.py`'s own
docstring. `test_customers_has_no_way_to_write_a_premises` asserts the absence.

## 4 · What was NOT built, and why

| | why |
|---|---|
| The screen. `ServiceRequestCapturePage.tsx` untouched | lane D's for this wave |
| The TypeScript wrapper and the `ServiceRequestLocation` type | lane D's hunk in `endpoints.ts` / `serviceRequestEndpoints.ts`; a sibling lane is live on the read payload and two lanes in one shared file is how a revert starts |
| The request's read payload | **lane B's**, found mid-build under different names. Backed out rather than shipped twice — see §3 |
| A regenerated `06-backend/openapi/schema.json` | the snapshot has drifted from the code already (a sibling's `/billing/print-sets/bills` is missing from it) and the CI step that would diff it is `.disabled`. Regenerating from a tree three lanes are adding endpoints to would publish their in-flight docstrings with it. Filed as `DEF-GOV-5402`; it belongs in the wave close-out, once |
| Anything about meters, services or assets on a picked unit | **PO ruling 2026-09-15 clause (2)** — they are the MOVE-IN request's. Named here so the next lane does not add them back |
| The unit count (`How many units are on this property?`) and the match table on step 3 | the other two thirds of `DEF-CUS-5385`. The count has no column anywhere and the drawing's own dashed panel says so; the match table is a screen |
| `resolve_address` made to search the register too | the ruling replaces the fuzzy run with a pick. Its clobber guard was added; widening its matching is a different change |
| A version bump / CHANGELOG line | the orchestrator's, per the wave brief. The sentence is in the report |

## 5 · Proof

### The endpoint was CALLED, against the real demo utility

Not a fixture — a Django server on `127.0.0.1:8231` against `brazosbend`, signed in as
Dana Whitfield, `GET /api/brazosbend/premises/picker`:

| asked | answered |
|---|---|
| `?q=Main` | `count=1` · `P-00053 · 500 Main St · Silver Creek · TX · 78611` · **31 units** |
| `?q=Mill Pond` | `count=9`, first `P-00004 · 107 Mill Pond Ln` |
| `?q=P-00039` | `count=1` — the premise number finds it |
| `?q=Silver Creek` | `count=73` — the town finds them |
| `?q=M` (one character) | `count=79` — ignored, never refused (`BR-SHL-011`) |
| `?q=nowhere at all` | `count=0`, and that is an answer |
| `?per=2&page=1` then `page=2` | `count=79`, 50 then 29, `next` true then false, **no row on both pages** |
| `?page=99999` | **HTTP 200**, clamped — a list URL never 4xxs over its params |

And the refusals reach a client as sentences, each writing nothing:

| asked | answered |
|---|---|
| a `picked_premises_id` this tenant does not hold | **404**, `errors.not-found` (HR-1 — never a 403) |
| `resolution_kind: "served_vacant"` | **422**, `customers.serviceRequest.fieldNotAccepted`, `{"field": "resolution_kind"}` |

`service_requests` held 8 rows before those two calls and 8 after.

### The pick, end to end on real data

Picking `P-00053` with no unit named stored, on a live request:

```
resolution_kind   premise_no_unit
lookup_found      customers.serviceRequest.lookup.premiseNoUnit
resolved_premises_id  01a0a444-5b1c-736b-917f-0d84a6882e02   (P-00053)
resolved_unit_id      null
no_premise_flag       false
evidence              premise_exists: true
decision.options      new_connection → not_possible → …verdict.newConnection.premiseExists
```

**That last line is the whole case for the fifth resolution kind, shown rather than
argued:** with `no_premise` the verdict table would have said a NEW CONNECTION *fits the
evidence* at an address the clerk had just found in the register.

⚠ **AND THAT CALL CREATED A REAL ROW ON THE SHARED DEMO TENANT BY ACCIDENT.** A shell
variable holding a unit id came back empty, so what was meant to be a refused probe was a
valid premises-only pick and `SR-26-0009` was created. It was **closed through the
product's own door** (`POST .../transitions`, `manual_close`) with a reason saying what
happened, rather than deleted: the number is burned either way (`BR-CUS-093` — *gaps are
normal*), and a record that says what happened beats a tidy one that does not. The demo
tenant now holds 9 service requests, one of them closed and labelled.

### Suites

| what | how | result |
|---|---|---|
| Lane E, this file | `pytest tests/test_cr094_lane_e_address_is_picked.py --reuse-db` | **21 passed, 1 skipped** (the PostgreSQL RLS case) |
| Neighbours | `pytest test_cr031_service_request{,_api}.py test_us_met_001_002_lists.py test_cr072_report_is_a_request.py test_cr094_service_request_messages.py --reuse-db` | **163 passed, 2 failed, 2 skipped** — the two are dated in §9 |
| Lint | `ruff check` on every file touched | clean |
| Locale parity | eleven catalogues, `17784 → 17787`, `git diff --numstat` = `3 0` on every one | ✅ |

## 6 · What existed already, measured before anything was written

The brief said a premises selector already exists and is not wired to this step.
**Two do, and both were read before a line was written. Neither fits, for a reason
that is checkable rather than a matter of taste.**

| candidate | has units? | paged? | why it was not reused |
|---|---|---|---|
| `GET /premises` — the S14 list (`selectors.premises_list`) | **no** — it serves a `units` COUNT | yes | It cannot answer the half of this step that picks a unit. It also runs the S14 roll-up and two per-row counts a counter type-ahead has no use for, and it matches the OWNER's name, so *Balcones* would return a shop owned by somebody called Balcones |
| `GET /routes/premises-picker` (`selectors.route_premises_picker`) | **yes** | **no** — `list[dict]` | Unpaginated: correct over 79 properties, `NFR-3` at a T5 tenant's 40,000. And every row carries the **meter count** and the route badge, which the same ruling's clause (2) puts on the move-in request |

What WAS reused rather than rewritten: `seams.premises_locality`'s pattern (the
`DEF-CUS-3653` repair), `seams.unit_row`'s 404-never-403 boundary, `_unit_resolution`
as the ONE definition of what a found unit means, `core.pagination.StandardPagination`,
`10-scripts/i18n_fanin.py` for the catalogues, `10-scripts/file_defect.py`,
`10-scripts/sync_stale_tree.py` and `10-scripts/push_paths.sh`.

## 7 · Red first — what was PROVED, and what was written and not finished

⚠ **READ THIS SECTION AS TWO LISTS, BECAUSE ONLY THE FIRST ONE IS EVIDENCE.**
Hard-won law 7 says a guard you have only seen pass is not evidence, and the same
sentence applies to a mutation table nobody ran: claiming nine red proofs this lane did
not observe would be exactly the shape it warns about.

### Proved red, in the harness that runs the guard, with the failure quoted

**Both of these went red FOR REAL rather than as an exercise, and each caught a bug that
would otherwise have shipped.**

**1 · The mismatched-unit refusal was raised through the wrong exception class.**
`_refuse` builds a `BizError`, and it was handed a `VAL-` code:

```
FAILED tests/test_cr094_lane_e_address_is_picked.py::test_a_unit_at_another_address_is_refused_by_name
E   ValueError: 'VAL-005' is not a BizError catalog code (B12 §3)
core/errors.py:147: ValueError
```

Every clerk who picked a unit at the wrong building would have got a 500 instead of a
sentence. It raises a `ValidationError` now — nothing about the RECORDS is wrong, the
PAYLOAD contradicts itself — and the reasoning is in the code beside it. Live against a
running server afterwards: `422`, `customers.serviceRequest.fieldNotAccepted` shape.

**2 · The no-fourth-address case was asserting a column that legitimately exists.**

```
FAILED tests/test_cr094_lane_e_address_is_picked.py::test_hard_rule_8_the_request_grows_no_address_column
E   AssertionError: service_requests grew a 'state' column
```

`service_requests.state` is the WORKFLOW state, and it is `G85`'s own measured false
positive — that gate's docstring names it among eight, with the reason: *"a gate whose
output is 73% false positives is a gate that gets an allow-list entry per commit until it
means nothing."* The case was **narrowed** rather than given an exception.

**3 · And two more, during the build rather than after it:** the fixture's
`premises_type="multi_family"` went red as `VAL-005 (metering.premises.type_unknown)` —
that code is not seeded, the six that are came out of the database — and the isolation
cases went red as `VAL-005 (metering.service_not_enabled)` because Lone Star Ridge is a
water-only tenant and the helper offers electric by default. Both are the fixture being
made to describe the real product rather than a convenient one.

### Written, started, and NOT finished — say so rather than imply it

`10-scripts/`-style harness at `scratchpad/laneE-work/red-first.sh` applies **nine**
mutations, one per guard, each run through `pytest` with a `-k` naming the single case it
should break, restoring from a pristine copy on EXIT:

| # | what it breaks | the case that should go red |
|---|---|---|
| 1 | the picker stops carrying units | `test_a_picked_row_carries_its_units_and_its_visible_values` |
| 2 | a `meters: 3` creeps onto the picker row | `test_nothing_about_the_meters_or_services_on_a_unit_is_served` |
| 3 | `search()` returns `list(qs)` | `test_nfr_3_the_search_pages_in_sql_and_caps_nothing` |
| 4 | the unit/premises agreement check dropped | `test_a_unit_at_another_address_is_refused_by_name` |
| 5 | a building with no unit called `no_premise` | `test_br_cus_1010_a_building_may_be_picked_with_no_unit_named` |
| 6 | the match overwrites `address_as_given` | `test_br_cus_070_the_pick_never_overwrites_what_the_applicant_said` |
| 7 | the resolver allowed to wipe a pick | `test_the_fuzzy_resolver_may_not_wipe_a_clerks_pick` |
| 8 | the pick stops storing the building | `test_a_picked_premises_is_walkable_to_a_real_locality` |
| 9 | `picked_premises_id` added to `PORTAL_CAPTURE_FIELDS` | `test_a_guest_on_the_public_form_may_not_pick` |

**It reached mutation 3 and was stopped by this lane, deliberately.** Five lanes were on
this machine and one `pytest` invocation of 23 cases went from **70 seconds to over seven
minutes**; nine of them would have been an hour of shared CPU for a table, while
mutations 4 and 8's targets had already gone red for real above. The harness is committed
to the scratchpad and named here so the next lane runs it in a quiet hour rather than
re-inventing it — and the tree was verified byte-identical to the pushed commit
afterwards (`git diff --numstat b87b9655` empty on both files), which is the trap working.

## 8 · Reds this lane did not cause, DATED

| red | dated how | verdict |
|---|---|---|
| `test_the_list_is_oldest_first_and_segments_by_state` and `test_us_cus_025_tc2_the_list_is_oldest_first` in `test_cr031_service_request.py` | run on a **pristine worktree at tip `701243a0` with no lane-E code in it**: identical failure, `2 failed in 617s` | **PRE-EXISTING since 2026-09-12.** `BR-CUS-1046` moved all eight lists to `created` DESCENDING in version `2.238.0`; both tests still assert oldest-first and say so in their own names. Filed as `DEF-CUS-5403` rather than reported and left |
| `kombu.exceptions.OperationalError: Error 111 connecting to localhost:6379` on every fixture that provisions a tenant | environmental — no Redis on this box; `config/settings/test.py` sets `JOBS_EAGER = False` unconditionally | **NOT A FAILURE.** It logs *"the record stays queued"* and the test carries on. It is noise that hid a real error for one run of this lane's own file, which is worth knowing: the first draft's real failure (`VAL-005 (metering.premises.type_unknown)`) was four lines above forty lines of Redis traceback |


