# §07 Past billing runs — the server half (screen 27), lane H

`CR-101-BRC03` wave 3. **Lane H wrote no screen**; lane I drew screen 27 and
reads this payload, and this file is the handshake it was told to read from.

---

## 1 · What was read, as images, and at what scale

| Page | What it is | Scale | Where |
|---|---|---|---|
| **p145** | §07's section overview — *"what did we bill last month, who signed it off, and is this month's run continuous with it"* | 2 | `scratchpad/billing/p145.png` |
| **p146** | **Screen 27 itself**, its four tiles, its toolbar, its seven columns, its pager, and the five notes beneath it | 2 | `scratchpad/billing/p146.png` |
| **p146** | the table band again, to read the column heads and the tile sub-lines | **4** | `10-scripts/pdf/pdf_render.py "05-prototype/04 Billing, As Built.pdf" … 4 146` |

B14 rule 42 — a screen is built from the drawing AS AN IMAGE, and the extracted
text is an index. Rule 41 — the drawing is the agreement. Rule 37 — every figure
drawn (34 runs, 11,842 bills, `$3,184,206.40`, 58 min) is an ILLUSTRATION; what
was built is the SHAPE.

---

## 2 · Before and after, measured against the running product

Everything below was measured on the demo tenant `brazosbend`, through real HTTP
on a server this lane started on port 8477, signed in as `dana@…` — not from the
docstrings, which is the point of half the findings.

| The drawing asks for | Before | After |
|---|---|---|
| **RUN** | served, and the read's own note said it *"cannot be produced"* | served; real runs carry `RUN-0002` |
| **CYCLE** (`09-A`) | `cycle_id` only — a uuid, which B14 rule 31 forbids showing | `cycle_code` + `cycle_name`, along the reviewed FK, no query per row |
| **PERIOD** | served | served |
| **BILLS** | served | served |
| **VALUE** | **absent**, kept off by a rule about another module's screens | `value` + `value_currency`; measured `"15453.630000"` USD on `RUN-0002` |
| **RUN BY** | served | served |
| **STATUS** | `draft` on **every finished run in the product's history** | five words, advanced where the work happens |
| the pager | a `limit` clamped at 200, **no total** | `{count, next, previous, results}` — measured `"count": 4` |
| the search | none | `q` over run number, cycle code, cycle name, person |
| the chips | `f.cycle_id` only | `f.cycle_id` · `f.status` · `f.year` |
| the four tiles | none | three answered, one a stated absence — see §5 |

**The live reply, abbreviated, as proof it was CALLED and not merely tested:**

```
GET /api/brazosbend/billing/runs          HTTP 200
{"count": 4, "next": null, "previous": null,
 "results": [{"run_no": "RUN-0002", "cycle_code": "CY-001",
              "cycle_name": "Silver Creek — monthly",
              "period_start": "2026-07-01", "bills_issued": 39,
              "value": "15453.630000", "value_currency": "USD",
              "ran_by_name": "Dana Whitfield", "status": "draft",
              "exceptions": 1, "exceptions_outstanding": 1, …}, …],
 "tiles": {…}}
```

⚠ **`"status": "draft"` ON A RUN THAT ISSUED 39 BILLS IS WHY §4 HAS A
MIGRATION** — that row was released long before the writer existed.

---

## 3 · The status machine — `BR-BIL-1045`, and two vocabularies that were dead

**No signed status vocabulary existed anywhere.** `04-docs/03-contracts` carries
none; the model's own comment points at `RUN_STATUSES (r10 #7)`, which is not a
symbol in this repository. So the drawing is the agreement and the words are
ours to decide and write down (law 13) — `BR-BIL-1045`, with a decision-log row,
written **before** the code that depends on it.

**Five words:** `draft` → `issuing` → `issued`, with `abandoned` for a run that
ended having issued nothing and `corrected` for one the correction workflow has
restated. One writer, `runs.record_run_outcome`, called from
`release.release_run` inside the transaction that stamps `released_at`, and from
`corrections` for the rebill run and the run it restated.

**The judgment that cost the most thought: what `abandoned` means.** The
tempting reading — *the issue pass ended with zero bills* — lets a run that
broke on every account read Abandoned and then flip back to Issued when a clerk
clears the breaks. **A terminal word that un-terminates is worse than no word**,
so the test is zero issued AND zero drafts left.

⚠ **AND THE PART NOBODY WAS LOOKING FOR.** Two selector constants named a
vocabulary **no writer in this product has ever written**:

* `SETTLED_RUN_STATUSES = {"completed", "cancelled"}` — `unissued_run_count`
  EXCLUDES this set, so every run in every window counted as unfinished on every
  tenant, for ever, and the ledger's month-end *"every run finished"* item could
  never go green. Its own 2026-09-07 decision row measured the symptom — three
  runs reading `draft · issuing · draft` — and read it as the seam being
  unpublished.
* `RUN_STATUSES_THAT_CONSUME_A_PERIOD = {"completed"}` — matched no row, so
  `BR-MET-132`'s chase-days chip never dropped a period a bill run had billed.

Both now name the words that are written, and
`test_5352_4__every_settled_word_is_a_word_this_module_actually_writes` is the
check that goes red the day they drift again. **A constant is a claim about what
some writer writes, and nothing re-checks it.**

---

## 4 · The back-fill, and why the writer alone was not the fix

`billing/0029` writes **one word, `issued`, and only where a locked bill proves
it.** The writer fixes every run made from today and fixes no run already in the
database — and those are exactly the rows screen 27 exists to show.

⚠ **THE FIRST DRAFT OF THE MIGRATION WOULD HAVE STAMPED *Abandoned* ON EVERY RUN
IN FLIGHT.** `abandoned` means *the run ENDED having issued nothing*, and
"ended" is an EVENT; a stored row cannot tell a run that ended with nothing from
a run a clerk created this morning. Draft is at least TRUE of a new run. Two
cases hold that door shut, and a third holds the REVERSE, whose first draft
would have sent every `issuing` row — including a rebill run created that way —
back to `draft`.

⚠ **IT IS NOT APPLIED TO THE DEMO DATABASE.** This wave's brief forbids a lane
running `migrate`, so the live tenant's historical runs still read Draft and
lane I's screenshots will show it. **It needs one `migrate` before the Product
Owner looks at the screen.**

---

## 5 · What was NOT built, with the reason

**The LONGEST RUN tile cannot be answered, and it is served as `null`
(`DEF-BIL-5376`).** Nothing in this product records how long a bill run took:

* `bill_runs` carries `created_at` and an `auto_now` `updated_at`, whose
  difference is the time until the row was last TOUCHED — and for a run whose
  status now advances, that number gets LONGER after the run ended;
* the job record that drives a run is `apps.tenancy.Job` and billing may not read
  it (B1, gate G6 rule 4), and it carries only the same two stamps;
* `invoices.issued_at` is a PASSED-IN business time (BR-TEN-043), identical on
  every bill of one pass, so the span of a run's bills is not a duration either.

A tile filled from any of those would be a figure nobody could re-derive.
`test_s27_4__the_longest_run_tile_is_an_absence_because_nothing_times_a_run`
also asserts `BillRun` has no `finished_at`, so the day somebody adds one it
goes RED and names the tile that has been waiting for it.

**Three single-bill paths still leave their run reading `draft`
(`DEF-BIL-5373`)** — `one_time`, `cut_bill` and `fee_bill` issue through
`issue.issue_invoice` rather than through `release_run`. One call to
`runs.record_run_outcome` in each is the fix; the single writer that would cover
all four lives in 🔒 `issue.py`, which this lane may not edit.

**No sort control.** p146 draws seven plain column headings with no sort
affordance. `parse_list_params` is called with no `allowed_sorts`, so `?sort=`
falls back to the fixed newest-first order rather than erroring.

**`label` is not searched.** The drawn placeholder names three things — run
number, cycle, person — and a search that quietly matched a fourth would make
that sentence incomplete.

---

## 6 · One written note overturned, with its own wording quoted

`api.py`'s runs-read exception (3) kept money off the row citing `BR-MET-078`,
*"Money never touches these surfaces"*. **That rule's PO wording is** *"you dont
need late fees in this. so dont have anything related to money when you create
route and cycles"* **and its subject is r10 SET-07.3 — the route and cycle
CREATION screens**, where a clerk is setting up a schedule and has no bills to
look at. A billing run's HISTORY row is neither. The rule itself is untouched
and still governs the screens it was written for; the note is stamped in place
with its date rather than deleted, so a reader who followed it finds out that it
moved (`DEF-BIL-5353`).

Exception (1) — *`run_no` … nothing in this product can produce it* — was TRUE
on 2026-08-23 when it was written and stopped being true **the same day**, when
`OQ-342` was ruled. Nothing re-checks prose.

---

## 7 · The payload, for lane I

`GET /billing/runs` · `q`, `f.cycle_id`, `f.status`, `f.year`, `page`, `per`.

```jsonc
{
  "count": 34, "next": "…?page=2", "previous": null,
  "results": [{
    "id": "01a0a445-…",           // the row opens this run
    "run_no": "RUN-0002",          // RUN      · null before the series existed
    "cycle_id": "01a0a444-…",      // the link
    "cycle_code": "09-A",          // CYCLE    · rule 31 — never the id
    "cycle_name": "Silver Creek — monthly",
    "period_start": "2026-07-01",  // PERIOD
    "period_end": "2026-07-31",
    "bills_issued": 39,            // BILLS
    "value": "15453.630000",       // VALUE    · stored decimal, DISPLAY 2
    "value_currency": "USD",       //          · null when a run has two
    "ran_by_name": "Dana Whitfield", // RUN BY · null is "nobody is recorded"
    "status": "issued",            // STATUS   · BR-BIL-1045's five words
    "accounts": 39, "held": 0, "issued_at": "2026-08-02T09:00:00+00:00",
    "exceptions": 1, "exceptions_outstanding": 1,
    "bill_type": "cycle", "label": null, "ran_by": "01a0a444-…",
    "created_at": "…", "is_open": false
  }],
  "tiles": {
    "year": 2026,
    "runs": {"count": 34, "cycles": 9},
    "bills_issued": {"count": 11842, "value": "3184206.400000", "currency": "USD"},
    "exceptions": {"runs": 6, "all_resolved": true},
    "longest_run": null            // DEF-BIL-5376 — draw a stated absence
  }
}
```

`07-frontend/src/api/endpoints.ts` carries `BillRunHistoryRow`, `BillRunTiles`,
`BillRunHistoryQuery` and `getBillRunHistory`. **The ten new fields are declared
OPTIONAL and the server always sends them** — required fails `tsc` in seven
files whose fixtures predate them, six belonging to live sibling lanes, and two
lanes never edit one file. Read them with `?? null`; when the fixtures move,
drop every `?`.

⚠ **LANE I's TC-I7 TRIPWIRE HAS FIRED, WHICH IS IT WORKING.**
`pastBillingRuns.dom.test.tsx:241` declares `HasKey<PastRunRow, "value"> = false`
against the day the row carries money. It does now, so `tsc` is RED there,
naming the VALUE column. **That file is lane I's and this lane did not touch
it.** Flipping it to `true` (and collapsing `PastRunRow` into
`BillRunHistoryRow`, which its own docstring says to do) is theirs.

**The row opens the run, and the drawing's *"its exceptions, its totals and its
sign-off"* is reachable at three addresses that were already mounted** —
`GET /billing/runs/{id}` (phase, scope, decisions, counts),
`GET /billing/runs/{id}/exceptions` and `/breaks`, and
`GET /billing/runs/{id}/summary` (the totals and the confirmations). Nothing new
was built there.

---

## 8 · Proof

| What | Result |
|---|---|
| `tests/test_def_bil_5352_run_status_machine.py` | **19 passed** |
| `tests/test_cr101_screen27_past_runs.py` | **21 passed** |
| `tests/test_cr029_rcw4b_run_history.py` | **21 passed** (6 rewritten for the new envelope and the VALUE column) |
| `tests/test_br_met_132_chase_days.py` | **11 passed** (5 were RED on the vocabulary change — mine, fixed) |
| regression: release · issue · staff alerts · run API · scope-and-counts · run numbers | 166 passed, 6 pre-existing failures (§9) |
| `npx tsc --noEmit` (local install, **proved able to fail** — it named 12 errors on the first cut of the widened type) | 1 error, lane I's own tripwire (§7) |
| `npx vite build` | ✓ built in 18.02s — **the product builds** |
| `npx vitest run` paginated · routeBUtilities · RoutesCyclesDetail | 62 passed |
| `ruff check` on the migration | All checks passed |
| `manage.py showmigrations billing` | one leaf, `0029` |
| the API, called over HTTP on the demo tenant | HTTP 200, envelope and every drawn column present |

**Red-first, in the harness that runs them.** The two writers were stubbed to
their pre-2026-09-15 behaviour and the two selector sets put back to
`{"completed", …}`; `pytest` then reported **9 of 15 red**, including:

```
AssertionError: assert 'draft' == 'issued'
AssertionError: assert 'draft' == 'corrected'
AssertionError: assert frozenset({'c... 'completed'}) <= {'abandoned',…}
AssertionError: and an issued one is finished, which was never reachable
  assert 1 == 0
assert False is True          (period_consumed_by_run)
```

The six that stayed green are the pure-function and no-regression cases. Their
red is one order further back: **none of `RUN_STATUSES`,
`run_status_from_evidence`, `record_run_outcome` or `mark_run_corrected` existed
at the branch tip** (0 occurrences in `939a8fe6:apps/billing/runs.py`), so every
case in the file would have failed with `AttributeError` there. The same is true
of `bill_runs_page`, `bill_run_tiles`, `cycle_code` and `value` in
`939a8fe6:apps/billing/selectors.py` — 0 occurrences each.

---

## 9 · Every red this lane did not cause, dated

**The definitive check, rather than a claim:** the five backend files were
temporarily replaced with their `939a8fe6` bytes and the three suites re-run.
**The same six failed**, so they are the branch's and not this lane's.

| Red | Dated by | When |
|---|---|---|
| `test_us_bil_001_003_run_api.py` × 5 (`assert [] == ['missing_read']`, then four `IndexError`) | `git log -S "a_missing_read_is_a_decision_and_names_its_stage"` | `fbf07102`, **2026-09-14** |
| `test_us_bil_005_release.py::tc58` | `git log -S "the_downstream_batches_are_named_and_none_of_them_ran"` | `d6d31c46`, **2026-09-04** |
| `G6 forbidden` — two ORM hits in `billing/api.py` | present at the tip as lines 1433 and 1743 (this lane's edit shifted them to 1491/1801); `git log -S` | `fbf07102`, **2026-09-14** |
| `G53 guard-list-coverage` names `billing/runs.py` | the 🔒 marker is at the tip (5 occurrences) | pre-existing |
| `G114 list-envelope` names `ImportRunListResult` in `endpoints.ts` | 3 occurrences at `939a8fe6` | pre-existing |

`run_gates --changed` reports **72 PASS, 49 FAIL, 5 SKIP**. No FAIL line names
`BR-BIL-1045`, `DEF-BIL-5373`, `DEF-BIL-5376`, `bill_runs_page`,
`bill_run_tiles`, or either new test file.

---

## 10 · Ids, and the thing that went wrong twice

`DEF-BIL-5373` and `DEF-BIL-5376` were first allocated as **5357 and 5358**.
`allocate.py defect --verify` caught both at push time — a sibling had pushed
5357 and 5358, and then, five minutes after `--verify` said 5374 was free, a
sibling pushed that too. **That second window is the one the allocator says out
loud it cannot close**, and the only thing that caught it was re-deriving
unconditionally at push time rather than inside any branch. Both rows and all
eleven citations of them moved together; the register on the branch holds no
duplicate id.
