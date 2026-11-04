# CR-094-BRC01 · seeder wave — the sample data can exercise two things it could not

**Branch** `claude/gifted-johnson-top7zn` · **rules** `BR-CUS-1070` · `BR-CUS-090` ·
the PO ruling of 2026-09-15 (*"RULED: THE COUNTER FEE POSTS"* and its `1010`
amendment) · **defects** `DEF-CUS-5423` (no seeded request had any service) ·
`DEF-RAT-5424` (`CC-REQFEE` existed in no tenant's catalogue and had no GL
mapping) · **found and fixed in passing** `DEF-CUS-5426`.

**The Product Owner asked for both, having been shown the measurements.** Their
words: ***"can you add this in seeder data"***.

---

## 1 · Before and after, counted

Every figure here was counted on PostgreSQL 16, never inferred.

| | Before | After |
|---|---|---|
| Sample service requests carrying ANY service row | **0 of 8** | **7 of 8** |
| Rows in `service_request_services` from the seeder | **0** | **12** |
| Requests asking for two services on two DIFFERENT days | **0** | **1** (`SR-26-0043`) |
| `CC-REQFEE` in the tenant's charge-code catalogue | **absent** — 28 codes and not this one | **present**, `$25.00`, `one_time` |
| Its GL account | — | **`4600` Connection & new-service fees** |
| Charge codes on a seeded tenant | 28 | **29** |
| `$25.00` taken at the counter and then approved | held in `2400` for ever, `release_error` naming the setting to fix | **earned**, `DR 2400 · CR 4600`, `release_error None` |

**The `0` is counted, not assumed.** On `brazosbend`, 2026-09-16:
`select count(*) from service_request_services s join service_requests r on
r.id = s.request_id where r.is_sample` → **0**, against 8 sample requests. The
seven requests that DID hold rows (`SR-26-0017`…`SR-26-0023`) were created by
lanes' own walks and carry `is_sample = false`.

⚠ **NOTHING WAS DONE TO THE DEMO TENANT.** Every after-figure comes from
tenants this lane provisioned for the purpose — `laneseed-reqfee`,
`laneseed-log` and `laneseed-fix`, all `Lane Seed Utilities`, electric and water,
through the real signup service and the real sample plant. `brazosbend` was not
written to, and it still holds 0 service rows and 28 charge codes because it was
planted before this change and is not re-seeded.

---

## 2 · What each of the eight sample requests now asks for

Read off `laneseed-fix` after the plant, `order by request_no, service.sort`:

| Request | Services | Their dates | What shape it is |
|---|---|---|---|
| `SR-26-0039` Osei, move-in | electric · water | both `2026-09-21` | **`p080`'s drawn pair** — every service agreeing on one date, over a request whose own `Connection date` is blank. No fallback can produce that state. |
| `SR-26-0043` Ridge Property, 25-unit build | electric · water | `2026-10-04` · `2026-10-18` | ⚠ **THE CASE THE RULE EXISTS FOR.** `p076`: *"A block that needs electric on the 12th and sewer a fortnight later is one request and not two."* A fortnight apart, on one request. |
| `SR-26-0047` Park, transfer | electric · water | neither | **all-unset is not an agreement** — `agreed` null and `unset` = the whole list |
| `SR-26-0042` Okonkwo, new connection | electric · water | `2026-10-26` · none | the mixed list |
| `SR-26-0048` Ridge Coffee, disconnect | electric | `2026-09-19` | one service, one date |
| `SR-26-0045` Kwan, move-in | electric · water | neither | **the mirror of `p080`** — the JOB has a connection date and the services do not. Under the old copy both would have read the job's. |
| `SR-26-0044` Alvarez, move-in | water | `2026-09-28` | a single dated service |
| `SR-26-0046` Thompson, move-out | — | — | ⚠ **NO SERVICES, DELIBERATELY.** A request that never reached step 2, so `count: 0` — a real answer a screen must render and nothing may divide by. |

`available` is **NULL on all twelve rows**: REQ-03.3's CHECK callout says
availability is settled at review, so *not yet asked* is never spelled the same
way as *no*.

**The dates are DAY OFFSETS in the fixture, not dates.** `start_days` counts
forward from the day the request came in, exactly as `age_days` and
`remind_on_days` already do beside it. A demo planted in March and a demo
planted in November both show a connection date in the future; an absolute date
would have rotted into the past and demonstrated the opposite of what these rows
are here to show.

**`requested_start` is ABSENT and never `None` when no date was given.**
`BR-CUS-1070` says an unset one means *the clerk gave none* and never *read the
job's* — in either direction — so a payload spelling *no date* as an explicit
null would encode the fallback the rule removed.

**The set is narrowed to what the tenant SELLS.** `set_services` validates
against the platform catalogue — all eleven — so nothing in the product would
have stopped the seeder asking a utility for a service it does not run. The
seeder reads `customers.seams.enabled_service_codes` (which is
`tenancy.selectors.enabled_service_codes`, the read tenancy already publishes to
the ledger and to metering) and drops the rest. **Nothing is switched on to make
the data look richer**, and no service is named in a list (`BR-RAT-024` has moved
from six to ten to eleven; that is `G47`).

### And a REPLAY reaches a request that predates the services step

**This is the half the demo tenant actually needs.** `_seed_cr030_service_requests`
is idempotent PER REQUEST, so without a reconcile, pressing *Load sample data*
again on `brazosbend` would walk straight past its eight existing requests and
the empty panel would stay empty for ever. That is `DEF-1250`'s shape one module
over — a plan idempotent per PLAN could never gain a service switched on
afterwards — and it is repaired the same way.

⚠ **ADDITIVE ONLY, AND ONLY WHEN THERE ARE NONE.** `set_services` REPLACES the
set, so a reconcile that ran unconditionally would overwrite a date somebody
typed while demonstrating the screen. The guard is *no rows at all*, which is
`apply_default_gl_accounts`' rule one module over: **fill an absence, never
replace an answer.** Both halves are asserted, and both were proved red (§6,
proofs 7 and 8) — the second one fails with
`ServiceRequestService.DoesNotExist`, because replacing deletes the row the
person's date was on.

The dates on a reconciled request are anchored to **that row's own
`received_at`**, not to today, so the Requests tab's ages stay true.

---

## 3 · The application fee, and the one judgment that was ours

`CC-REQFEE` is the code `core.sample_fixture.CR030_SERVICE_REQUESTS` quotes on
the request a clerk takes `$25.00` cash against. It existed **in that fixture
and in no tenant's catalogue.**

Since the ruling of 2026-09-15 that is a money hole rather than an untidiness:
the counter fee posts when it is taken and is released to *the charge code's own
revenue account* on approval or refusal, and
`payments.counter_receipts._revenue_account_id` resolves that account from
`rating.charges` — which had no row. So the money could be taken and held and
**could never be earned**. A clerk is never blocked by it, which is exactly why
nothing surfaced it.

**What was decided, and law 13 was applied first.** The decision log and the
open questions were grepped for *CC-REQFEE*, *application fee* and *request fee*;
neither holds a ruling on either half, so the judgment is the lane's and is
recorded with its figures.

* **The code is created by the SAMPLE-data loader**
  (`apps.rating.sample_data.seed_sample_request_fee_charge_code`), through
  rating's own audited `create_charge`, and **`lookup_defaults.json` is
  untouched.** That list is the 25 codes CR-066's table put to the PO, and
  widening it changes what every utility in the world is provisioned with. This
  code arrives with the sample service requests that quote it, on the same
  button — which is the same reasoning that puts the `BASE-*` family there
  rather than in the platform fixture.
* **The amount is `$25.00` and is not new.** It is `BR-CUS-090`'s own worked
  case, the one the PO ruled on: quoted `$130.00`, `$25.00` cash taken on
  receipt `RCP-26-4471`, `$105.00` outstanding. Copied, not chosen.
* **The account is `4600 Connection & new-service fees`**, recorded in
  `ledger.chart.CHARGE_CODE_ACCOUNTS` beside `CONN`, `TAP`, `TEMP-SVC` and
  `TRANSFER`. An application to take service is a new-service fee. **One home
  for the mapping** — a second table saying the same thing somewhere else is how
  two answers come to disagree — and **no account was created and no numbering
  scheme was invented.**
* **`auto_apply` is False.** `BR-RAT-117` puts a recurring auto-applied code on
  every ordinary bill; this one is quoted on a service REQUEST by a clerk and
  must never land on a customer's monthly bill.
* **No `is_sample` tag, stated rather than worked around.** `BR-TEN-057` puts
  the tag on the owning row and `rating.Charge` has no such column — the
  `BASE-*` family that loader already creates is in the identical position — so
  `remove_sample_records` will not sweep this code either. Adding the column is
  a migration on rating's own table.

### `CHARGE_CODE_ACCOUNTS` is one entry wider than its own heading said

The map's comment read *"for the codes the platform fixture ships"*. `CC-REQFEE`
is the first entry that fixture does not ship, so the heading is **amended where
it stands** rather than left to be inferred. `G70` is unaffected and was re-run:
it walks the platform fixture TOWARD the map — *is every shipped code
answered* — and never asks the reverse; its own docstring says the third
question (unreachable rows) is deliberately not checked.

---

## 4 · The money, walked end to end on real PostgreSQL

`laneseed-fix`, through the product's own service calls — `create_request` →
`set_customer_category` → `set_services` → `link_customer` → `resolve_address` →
`add_fee_line` → `collect_fee` → `submit` → `pick_up` → `decide_outcome` →
`approve`. The journal lines are read out of `journal_lines`, not asserted from
a fixture.

```
── AT COLLECTION ── receipt RCP-26-9002  25.0000 · state held
      1010 Undeposited funds              DR 25.000000
      2400 Customer credit balances       CR 25.000000
      debits 25.000000 · credits 25.000000 · BALANCED

── AFTER APPROVED ── state applied · earned 25.0000 · release_error None
      2400 Customer credit balances       DR 25.000000
      4600 Connection & new-service fees  CR 25.000000
      debits 25.000000 · credits 25.000000 · BALANCED
   revenue_postings: [{'amount': '25.0000', 'charge_code': 'CC-REQFEE', …}]
```

**Refusing posts the identical pair**, because the fee is non-refundable and in
double entry *applied to the fee* and *earned because it cannot be returned* are
one act — receipt `RCP-26-9003`, state `earned`, `release_error None`, the same
`DR 2400 · CR 4600` for `25.000000`.

**And the soft branch is unchanged and was re-proved**, on `CC-EXPEDITE`, which
still has no `charges` row anywhere — receipt `RCP-26-9004`:

```
── AFTER REFUSED ── state earned · earned 0.0000
   release_error "charge code 'CC-EXPEDITE' has no GL account on this tenant's
   charge-code catalogue, so there is no revenue account to earn 25.0000 USD
   into. Nothing is guessed and nothing is posted: the money stays in customer
   credit balances and is visible there. The fix is Settings → the charge code →
   GL account (BR-BIL-010)."
```

Nothing posted, the money stayed visible in `2400`, and **the refusal went
through** — *"a clerk stuck at a counter with a person in front of them is the
worse failure"*.

---

## 5 · `DEF-CUS-5426` — a regression this lane found and fixed

**On every tenant provisioned since 2026-09-15, `SR-26-0043` was landing in
`draft` instead of `In fulfilment`.**

Since `883206ca` (2026-09-15, wave 1 lane A) approval RAISES the job and
`request_jobs.raise_job` calls `link_child` itself with the real child's
reference. The seeder then called `link_child` again with the fixture's drawn
`CON-26-0117`, which `link_child` refuses by name — correctly — and because
`submit`, every transition, `decide_outcome`, `approve`, `route` and that call
all shared **one** `transaction.atomic()`, the refusal took the whole chain down
with it. Quoted from the run:

```
sample data (CR-030 W4): SR-26-0043 did not reach 'in_fulfilment' —
BizError: BIZ-IDEMPOTENT (customers.serviceRequest.childAlreadyLinked).
The row is left in the state the product allowed it to reach
```

Dated with `git log -S "childAlreadyLinked" --
06-backend/apps/customers/service_request_service.py`. **Not this lane's
commit.** `brazosbend` was planted before it and still reads `In fulfilment`,
which is why weeks of screen review never saw it, and nothing in the suite
provisions a fresh tenant and walks the eight requests.

The step has its own savepoint now — like every other step in that function —
and a child the product has already named is **left alone rather than
overwritten**, because the real reference beats the drawing's (B14 rule 37) and
the divergence is reported rather than hidden:

```
sample data (CR-030 W4): SR-26-0043 already names CON-26-0129 — the product
raised it at approval, so the fixture's CON-26-0117 is NOT linked over it
```

All six drawn states are back on a fresh tenant: `more_info`, `under_review` ×3,
`approved`, `in_fulfilment`, `submitted` ×2.

---

## 6 · Proof table

| What | Command | Result |
|---|---|---|
| New tests | `JOBS_EAGER=false pytest tests/test_cr094_seeded_services_and_request_fee.py --reuse-db` | **13 passed** |
| Each guard RED first, in the harness that runs it | the same, with one named thing broken at a time | **8 red proofs**, each failure quoted in the file's own docstring |
| The seeded tenant | `provision_tenant` + the real sample plant, PostgreSQL 16 | 8 requests · **12 service rows across 7** · 29 charge codes · `CC-REQFEE` → `4600` |
| The money, both ends | the walk in §4, reading `journal_lines` | debits = credits at collection and at release |
| The unmapped branch | the same walk on `CC-EXPEDITE` | earned `0.0000`, nothing posted, refusal went through |
| `G70` | `run_gates.py --changed` | PASS — 25 platform charge codes, **24** mapped (23 at the tip), 2 exempt by a written ruling |
| Every other gate | `run_gates.py --changed` in this tree AND in a clean worktree at `f52da422` with none of this lane's files present | **46 FAIL in both, name for name. No gate got worse.** |
| Neighbouring backend suites (9 files) | `JOBS_EAGER=false pytest … --reuse-db` | 5 failed / 178 passed / 16 skipped — **the same 5 fail in the clean worktree**, listed in §9 |

---

## 7 · What this wave did NOT do, and why

* **It did not touch `brazosbend`.** Every measurement is from a lane-owned
  tenant. The demo tenant still holds 0 service rows and 28 charge codes and
  will until somebody re-runs its sample load.
* **It did not backfill.** Nothing was written over a row that already existed,
  which is the same posture `BR-CUS-1070` took on the day it landed.
* **It did not add `CC-EXPEDITE` or `CC-METERTEST`.** They are the other two
  codes the demo fixture quotes and they still have no row anywhere. Only
  `CC-REQFEE` is collected against (the receipt is `$25.00` and the walk stops
  at the first line), so only it reaches the money path — and widening the
  scope is how a wave grows while it is being built. **Reported, not fixed:**
  the request's quote still names two codes that resolve to nothing, which is
  visible on the fee panel as a code with no catalogue row behind it.
* **It did not add a `charges.is_sample` column.** §3 says why.
* **It did not mint an `OQ`.** Nothing here is a fact only the PO holds: they
  asked for both things, the figures were already ruled, and the account was a
  judgment recorded with its reasoning.
* **It did not touch the screen.** Capture step 2's services multiselect and the
  request's own services panel are the screen lanes'; this wave gave them data
  to render.

## 8 · Where the record is

* `12-governance/02-decision-log.md`, 2026-09-16 — the decision with its worked
  figures.
* `04-docs/05-modules/03-customers/02-business-rules.md` — `BR-CUS-1070`, the
  seeder half stamped BUILT with its counts.
* `12-governance/09-human-review-ledger.md` — 🔒 the one GL-map entry, with the
  `$25.00` and the two account codes in plain English.
* `12-governance/10-defect-log.csv` — `DEF-CUS-5423`, `DEF-RAT-5424`,
  `DEF-CUS-5426`.

---

## 9 · Reds, dated

**Every red below was measured in a clean `git worktree` at `f52da422` — the
commit this lane started from — with none of this lane's files present.** That
is stronger than an opinion about whether a failure looks related, and it is why
this section exists rather than a sentence saying *"pre-existing"*.

* **46 gate failures**, `run_gates.py --changed` against the same base, run in
  both trees. **Identical, name for name**, and no gate moved from PASS to FAIL.
  `G70` PASSES in both and its own count moves the right way: 23 mapped at the
  tip, **24** here, because `CC-REQFEE` now resolves.
* **5 backend failures across the 9 neighbouring suites**, and the same 5 in the
  clean worktree: `test_cr031_service_request.py::test_the_seeded_numbers_are_allocated_not_the_drawn_ones`,
  `::test_br_cus_106_exactly_two_of_the_eight_seeded_requests_accent`,
  `::test_us_cus_025_tc14_the_age_accent_is_seven_days`,
  `test_cr010_silent_seed_gaps.py::test_def257_every_sample_account_carries_a_sub_type`,
  `test_cr039_sample_block_reporting.py::test_cr039__every_declared_edge_is_quoted_from_the_file_it_cites`.
  ⚠ **Three of those five are about the SEEDED REQUESTS**, which is this lane's
  own subject, so they were run in the clean worktree first rather than
  dismissed. They fail there too, with none of this lane's code present.
  `git log -S` on each symbol resolves only to the branch's own merge commit and
  therefore dates nothing useful; the clean-worktree run is the evidence.
* **Nothing here was fixed.** They are not this wave's commitment and none of
  them stops the next lane: the product builds, the migration graph has one
  leaf, and the suites collect.
