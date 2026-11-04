# DEF-BIL-5255 · DEF-BIL-5258 — the scope a run never had, and the counts the browser was doing

**Date** 2026-09-14 · **Branch** `claude/eager-johnson-r0k88b` · **Base tip** `2352b7c2`
**Reads only.** `apps/billing/selectors.py` and the read endpoints in `apps/billing/api.py`.
Nothing in `models.py`, no migration, and nothing on the run-creation path — those were
another lane's files for the whole of this work.

**Spec** `04-docs/05-modules/07-billing/conformance/CR-105-BRC03-s03-element-inventory.md`
(883 lines, §03 read as images) · blueprint `05-prototype/04 Billing, As Built.pdf`
entries **16 Scope**, **17 Check** (17.L2, 17.L3), **17.0 Checking**
**Rules** `BR-BIL-005` · `BR-BIL-015` · `BR-BIL-040` · `BR-MET-121` · `BR-TEN-043` ·
`BR-CUS-068` · B14 rules 16, 31, 33, 37

---

## 1 · What was wrong, measured

| | `DEF-BIL-5255` (screen 16) | `DEF-BIL-5258` (screen 17) |
|---|---|---|
| The claim | a clerk chooses what to bill | the strip shows what the run found |
| What was there | one cycle, all or nothing. `runs.scope_account_count` could SIZE a cycle and nothing could narrow one | every chip is `.length` of an array the browser was sent, over `GET /billing/runs/{id}/findings`, unpaginated **by declared design** |
| The measured cost | a 40,000-account utility cannot bill a subset at all (`DEF-BIL-4224`); the run itself caps at 25,000 | **66,053 SQL statements and the whole population on the wire at 1,000 accounts, per refresh** |
| Why no check caught it | nothing reads a drawn control against a schema | the endpoint documents its own cost honestly and no test asserts a payload SIZE |

---

## 2 · Element list, and what each one answers

**Contract 1 — the scope resolver.** `GET /billing/run-scope`, `selectors.scope_resolution`.

| # | Element | What decides it |
|---|---|---|
| 1 | `SCOPE_KINDS` — `cycle` · `route` · `area` · `named_set` | the drawing's helper, *"Or a route, an area, or a named set."* |
| 2 | `_scope_units` | **the cycle's units first, the scope intersects them** — never the reverse |
| 3 | `counts.units_in_cycle` / `units_in_scope` / `accounts_to_bill` | `metering.units_in_cycle` → `customers.accounts_for_bill_run(...).count()` |
| 4 | `counts.master_accounts` | the same population filtered on `kind` — `DEF-BIL-5296` |
| 5 | `counts.service_points` and the read-only `services` chips | `metering.service_points_for_units`, ONE query for the population |
| 6 | `counts.meters_this_cycle` · `sub_meters` · `points_with_no_meter` | **null, with the reason served** — `DEF-BIL-5297` |
| 7 | `committable` + `SCOPE_KEY_LIMIT` | **false for every narrowed scope** — `DEF-BIL-5283` |

**Contract 2 — the streaming counts.** `GET /billing/runs/{id}/findings/counts`,
`selectors.finding_counts`; plus opt-in paging of one named list on the findings read.

| # | Element | What decides it |
|---|---|---|
| 1 | `BAND_ORDER` — seven bands, ordered by obligation | §03 p040; always served, including at zero, so the strip does not change shape mid-run |
| 2 | tags, **generated** | *"A case kind the engine did not raise gets no chip"* — from the rows, never a declared twenty-six |
| 3 | `BY_DEFAULT_CASES` | `estimated_read` and `base_only_billing` — every other decision case is *Needs you* |
| 4 | Held's two tags | `never_calculated` = unresolved exclusions · `calculated_and_broke` = `prepared.blocked` |
| 5 | `where the fix is` / `the reason` | the block's `stage` (BR-BIL-040) and its `reason` |
| 6 | `waiting_bands_for` | **multiples of the cycle's own period**, `metering.cycle_expected_span_days` |
| 7 | `age_bands_from` | a PARAMETER with no default — `OQ-BIL-12358`, OPEN |
| 8 | `kpi`, four cells, money null | phase 1 computes no money at all |
| 9 | `reconciliation` | ready + needs you + held + nothing-to-bill = accounts in scope, **by construction** |
| 10 | `?list=&page=&per=` on the findings read | B14 rule 16, opt-in — see §5 |

**Contract 5 — the cycle-scoped runs read.** `bill_runs_list`, already scoped by cycle.

| # | Element | What decides it |
|---|---|---|
| 1 | `ran_by` + `ran_by_name` | `bill_runs.run_by`, which EXISTS and was reaching a clerk on two refusals and nothing readable. Name beside id — B14 rule 31 |
| 2 | `is_open` | **not `status`**, which never advances off `draft`. A run is open when it has issued no bill |
| 3 | `label` | the run's own name. ⚠ **This read served `null` under that name until the column landed mid-lane** — `BR-BIL-1041`, pushed by the schema lane in `2.267.0`. Re-checking the packet before closing the record (r11 step 0) is what caught it; `DEF-BIL-5300` is closed |

---

## 3 · The arithmetic, worked

**The band/tag rule (`DEF-BIL-5273`), and it is counter-intuitive.** A tag counts **CASES**;
a band counts **ACCOUNTS**. A chip is an ACTION, so an account needing two actions appears in
two chips.

```
tc6, built:  one account that broke at stage 1 AND is held by a clerk
             never_calculated 1  +  calculated_and_broke 1  =  2 cases
             Held band                                      =  1 account
             sum(tags) 2  >  band 1                          ✅ strictly greater
```

**Every check asserts `sum(tags) >= band`, never equality.** `tc16` asserts it over all
seven bands at once.

**The waiting-time bands, derived rather than typed.** One cycle period escalates; two is a
long wait.

```
Monthly, 1–30 Jun 2026   period 30  →  escalate 30 · long wait 60
Monthly, 1–31 Aug 2026   period 31  →  escalate 31 · long wait 62
Fortnightly              period 14  →  escalate 14 · long wait 28
Quarterly, 1 Jun 2026    period 92  →  escalate 92 · long wait 184
no frequency             period  —  →  NO age tags, absence stated
```

⚠ **The drawn `Under 14 days` / `Over 60 days` are ILLUSTRATIONS (B14 rule 37) and are not
built.** A fixed 14 would escalate a quarterly cycle's entire queue before its first bill
was due; a fixed 60 would never escalate a fortnightly one.

**The reconciliation, as `tc7` pins it.** `ready 0 + needs_you 0 + held 1 + nothing_to_bill 1
= accounts_in_scope 2` — the four sets are built by subtraction from one population, in that
order, so no account can be in two and none can be in none.

---

## 4 · Proof

`06-backend/tests/test_def_bil_5255_5258_scope_and_counts.py` — **20 passed**, on real
PostgreSQL (`DATABASE_URL=postgres://…`, `DJANGO_SETTINGS_MODULE=config.settings.local`),
never the SQLite default suite (CLAUDE.md law 14).

**Four of the twenty are hard-won law 2 — *built is not wired*.** `tc17` resolves both new
addresses through the REAL root URLconf, because exporting `urlpatterns` is not an endpoint
until `config/urls.py` includes it and S31 shipped against exactly that gap. `tc18`–`tc20`
then call the views and read the answers: the scope card over the wire with its query string,
the counts read REFUSING without an `as_of` (**422**, and answering with seven bands when it
is given one), and one findings list paged with its own footer figures.

**Regression, measured against the clean tip rather than asserted.** The four neighbouring
billing suites were run three ways on real PostgreSQL:

```
the pinned tip, untouched                        10 failed · 38 passed
the pinned tip + this lane's two files           10 failed · 38 passed     ← no change
the SHARED working tree                          27 failed · 21 passed
```

**The ten are pre-existing at the tip and this work adds none of them.** The extra seventeen
in the shared tree are another lane's uncommitted schema work, not this one's — which is the
whole reason the comparison was run in a pinned `git worktree` instead of in the tree
everybody is standing in.

### ⚠ The new guard was shown RED — and its FIRST VERSION COULD NOT FAIL

`tc16` asserts `sum(tags) >= band` over every band. It was written after a probe found a
real bug: *where the fix is* counted **every** blocked account, while a block whose reason
carries **no stage** (`ruled_path_refused`, `cycle_has_no_service_points`,
`unit_has_no_billable_account`) produces no stage tag at all. A band was therefore claiming
an account its own chips did not show — the direction that HIDES work from a clerk.

The red proof was run by reverting the fix inside a `git worktree` pinned at the tip, so the
shared tree was never mutated:

```
first attempt   fix reverted   tc16 + tc7   →   2 passed        ⚠ INCAPABLE OF FAILING
```

The fixture held only a block that DID carry a stage, so `len(staged_ids)` and
`len(blocked_ids)` were the same number and the case was green with the bug put back. A
third account was added — `a_stageless_break`, a two-service unit with a plan and no meter,
which breaks with `ruled_path_refused` and no stage — and the proof re-run:

```
second attempt  fix reverted   tc16   →   AssertionError: ('where_the_fix_is', 1, 2)
                                          assert 1 >= 2                    ✅ RED
                fix restored   tc16   →   1 passed                         ✅ GREEN
```

**This is law 7's *incapable of failing* caught by law 7's own procedure**, and it is
recorded because the first version would have shipped as a guard nobody could ever have
distinguished from a working one.

### ⚠ And the gates caught something no test could — two refusals that would have said NOTHING

The first draft of the scope resolver raised its two seam refusals as catalog errors naming
**two brand-new `message_key`s**. Twenty tests passed, `ruff` passed, the endpoint answered a
well-formed 422 — and `G32` and `G18` both went red:

```
FAIL: billing.scope.accountsUnavailable  resolves to nothing
FAIL: billing.scope.unitsUnavailable     resolves to nothing
```

**A raised key with no catalogue entry reaches a clerk as SILENCE**, because server `detail`
text has not reached a screen since the 2026-08-19 ruling. The fix is not to write the
sentence in eleven catalogues: it is to stop inventing a key. Both now raise a plain
`BillingRuleError`, which `_as_catalog_refusal` renders through the existing
`billing.run.refused` — the same sentence `runs.scope_account_count` already gives the same
two conditions, four lines from where it resolves the same two seams.

**Four other unresolved keys remain and are NOT this lane's** —
`billing.templates.layout_preview_refused`, `customers.closing_accounts.as_of_required`,
`metering.meter_normals.as_of_required`, `runbooks.refusal.over_cap`. All four arrived in
`cf45a3d2` on **2026-09-13**, dated with `git log -S` rather than assumed (law 7, habit 1:
calling a red pre-existing WITHOUT dating it does the opposite of what the habit is for).
`G6`'s `api.py` ORM finding is likewise older — `938d89c9`, **2026-09-02**; this lane's 138
added lines moved its line number from 1208 to 1338 and nothing else.

---

## 5 · Judgment calls, each with the figure it rested on

**1 · A narrowed scope is SHOWN and is not COMMITTABLE.** `DEF-BIL-5283`: `runs.create_run`
composes its key from cycle + period and nothing else, so a Water-only September run
consumes the key for September and the Sewer run is refused as a duplicate — **with zero
exclusion rows written**, so those accounts never reach the held queue and no catch-up ever
bills them. The key lives in the run-creation path, which was another lane's file. The brief
allowed either fixing the key or refusing with a sentence naming the limit; the resolver
therefore answers `committable: false` for every narrowed scope, with the limit in the
clerk's own words. **A scope chooser over an unfixed key is a revenue hole with a dropdown
on it, and the front end must read this flag before it renders one.**

**2 · Three meter counts are NULL rather than bought.** `assets.asset_ids_for_service_point`
is per service point, so the drawn *meters this cycle · sub-meters · points with no meter*
would cost roughly **1,600 round trips on a 1,502-unit cycle** to draw three numbers on a
header — on a card whose own note says every figure is a count precisely because resolving
scope for real is the expensive thing. A zero would be a claim that the cycle has no meters.
`DEF-BIL-5297`.

**3 · `In arrears` is not folded into the findings pass.** It is a fact about an ACCOUNT, at
a date the clerk chooses, from a different source and against a different clock. Folding it
in would give the run a number that moves when somebody pays. Served as a named absence;
`DEF-BIL-5299`.

**4 · Counts are a separate address, and paging stays OPT-IN.** The findings read is
unpaginated because its lists are the denominator the chips count — one argument holding up
both halves. Serving the counts separately dissolves it. Making the page the DEFAULT today
would turn `ready.length` into a page size and the live screen would report fifty accounts
in a run of ten thousand, so `?list=&page=&per=` is opt-in until the screen reads its
numbers from the counts address.

**5 · Nothing is cached.** `OQ-843` is closed on the PO's ruling that the pass is dynamic.
This recomputes; what it saves is the wire and the browser's arithmetic.

**6 · The progress figures needed nothing.** §03 p050 says the in-flight *checked so far /
of* pair is the job's own `done` and `total`, already served and already polled — verified:
`run_jobs._progress_reporter` → `core.jobs.record_progress`, read back through
`/api/jobs/{id}`. **No new plumbing was built for it.**

---

## 6 · What this work did NOT do, and who owns each

| | Owner |
|---|---|
| The run key carrying the scope (`DEF-BIL-5283`) | `runs.py` / `core/idempotency.py` — the run-creation lane |
| ~~`bill_runs.label`~~ | **landed during this lane** — `2.267.0`, and this read now serves it |
| The cycle-level waiting-band setting (`DEF-BIL-5298`) | metering's `Cycle` — this read asks for `cycle_waiting_bands` BY NAME and falls back, so wiring it changes no billing code |
| A bulk meters-by-service-point read (`DEF-BIL-5297`) | assets |
| A population count read (`DEF-BIL-5296`) | customers |
| Named sets (`DEF-BIL-5295`) | nowhere — no table, no seam, no screen |
| The takeover write on an open run | not a read |
| Every screen | the front end |

---

## 7 · Where this brief disagreed with the inventory

* The brief says **"26 chips in 7 categories"**. The inventory's own §3 says the strip is
  *generated* — *"A case kind the engine did not raise gets no chip"* — and 26 is the count
  when every case is raised. **The bands are the taxonomy and are always served; the tags are
  generated.** A read that always served twenty-six would be the as-built screen's existing
  defect (fifteen declared tabs over nine emitted cases) wearing a new number.
* The brief asks for **"units in the cycle, accounts to bill, master accounts, meters this
  cycle, points with no meter"**. Three of those five cannot be served at the card's own cost
  ceiling today; see §5.2.
* The brief's waiting-band example — *"a 15-day cycle bands around 12–18 days"* — reads as a
  band AROUND one cycle length, which is what one-period escalation gives (14 on a
  fortnightly cycle). The drawn 14 and 60 are not reproducible from any single rule across
  cycle lengths and are recorded as illustrations.
