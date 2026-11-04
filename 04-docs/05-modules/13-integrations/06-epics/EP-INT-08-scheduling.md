# EP-INT-08 — Scheduling: the first beat schedule this product has ever had

**Module:** integrations · **Wave:** phase 3 (`US-INT-029`, `030`) · phase 4 (`US-INT-031`) · **Screens:** S142 (the budget figure, the collecting state) · S8 card · **Status:** draft (`CR-069`, 2026-09-03)

## Scope

**In:** the scheduling MODEL the design says does not exist — *"celery-beat is running and there is no `beat_schedule` anywhere in `06-backend/config/`; the container connects to the broker and sits there"* (verified 2026-09-03: `grep -rn beat_schedule 06-backend/config/` → nothing). Four decisions and two more (`BR-INT-024`, `BR-INT-034`): whose clock, spread not synchronise, overlap, catch-up, the budget that is not a rate, the window that is theirs. And completion as a declared value — `immediate`, or `submit–poll–collect` — with result delivery as a link or a handle (`BR-INT-046`).

**Out:** the runs themselves (`EP-INT-06`), the file guards (`EP-INT-09`), what a scheduled fetch from a bank's drop folder needs operationally — *"a genuinely different operational animal from an upload"* — which stays a scope call inside phase 4 (`US-INT-033`).

**All six decisions are configuration on the manifest, not code in an adapter** — a new connector declares its cadence policy and inherits the machinery.

## Capability matrix (list screens only — B9 conformance)

No list screen. The budget figure and the collecting sentence render on S142 and on the card.

## Stories

---
id: US-INT-029
epic: EP-INT-08
module: integrations
screens: [S142, S8]
wave: 3
status: ready
blocked_by: []
depends_on: [US-INT-016, US-INT-020]
journeys: [J50, J55, J56]
rules: [BR-INT-024, BR-INT-026]
golden_tests: []
finance_calc: none
---
### US-INT-029 — The scheduling model: their night, spread across the window, skipped rather than doubled, and never replayed six times (C29)

**1 · Details** — As **a utility**, I want **"nightly" to mean MY night, spread so we do not all fire at midnight, skipped rather than doubled when the last run is still going, and never replayed six times after an outage** — so that **a scheduled job nobody is watching fails the way a person would want it to**.

**Two entries in `config/settings/base.py`'s `beat_schedule`, the first the product has ever had:** `integration.sweep_due` every minute and `integration.sweep_expiry` nightly. The due sweep (Figure 13): *enabled AND `next_run_at ≤ now` AND not already running → spread (jitter the start) → enqueue, scope-keyed → run → compute the next due time from the cadence **in the tenant's own timezone, DST-safe***. The four decisions, each a production incident in a system that skipped it: **1 · whose clock** — a cadence stored in UTC arrives at 6 pm local in summer and 7 pm in winter and twice, or never, on the two days the clocks move; **2 · spread, not synchronise** — 300 tenants computed from midnight is a self-inflicted thundering herd, so a deterministic per-connection offset spreads them, and it costs one line; **3 · overlap** — the previous run still going when the next is due is how a bank file gets imported twice; the content-hash guard would catch it, *"but relying on the guard rather than not starting the run is the wrong order"*: skip, and **write down that you skipped**; **4 · catch-up** — six windows missed during a six-hour outage: for a file fetch run the **latest only**; for anything that moves money **never auto-catch-up at all** — surface it and let a human press the button. `manual` has no due time and is never swept — *"manual is a choice, not an absence."* Cadence is coarse — nightly, hourly, manual — never a free-text cron a user can type every minute into.

Entry: the beat tick. Exit: enqueued runs; skip rows; the next due time on the connection.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-INT-024` | Tenant timezone · deterministic spread · skip-and-record · no auto-catch-up for money · manual never swept · coarse cadences | PROPOSED — design §1.9, Figure 13, `C29` |
| `BR-INT-026` | A sandbox connection is never handed a real batch — the sweep enqueues no real work for it | PROPOSED |
| `BR-INT-022` | A connection whose breaker is open is skipped, and the skip recorded | PROPOSED |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Brazos Bend (America/Chicago), cadence nightly; sweep evaluated on 2026-11-01 (DST ends) and 2027-03-14 (DST starts) | The due time is **their midnight** on both days — one run each night, not two and not zero (doc TC-INT-19) |
| TC-2 | 300 connections all `nightly`, mixed timezones | Computed start times are spread across the window; **identical across two sweeps** — deterministic, not random (doc TC-INT-20) |
| TC-3 | A run still `running` when the next window is due | No second run; a row `outcome = skipped`, summary *skipped — the previous run is still going* (doc TC-INT-21) |
| TC-4 | Workers down six hours; six windows missed on a bank-file fetch and six on a card-charge operation | **One** run for the file fetch (the latest window); **zero** for the money-moving one, which appears on S142 and the S8 panel as *needs a person to start it* (doc TC-INT-22) |
| TC-5 · **negative** | Cadence `manual` | `next_run_at` is NULL; the sweep never selects it; nothing is recorded as skipped |
| TC-6 · **negative** | `PATCH /integrations/{key}` with `cadence = "*/5 * * * *"` | Refused; the vocabulary is `nightly · hourly · manual` |
| TC-7 · **tenant isolation** | Two tenants in different timezones both `nightly` | Each runs at its own midnight; the scope key carries the tenant |

**4 · Test Data** — Brazos Bend `America/Chicago`, Silver Creek `America/Denver`, 298 synthetic connections across six US zones; DST dates 2026-11-01 and 2027-03-14; a bank-file fetch connection and a `payments_card` charge operation for TC-4; a `manual` accounting target.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| `cadence` | S141 · S8 card | `BR-INT-024` | `integration_connection.cadence` | enum | user-input | `nightly \| hourly \| manual` |
| `next_run_at` | S142 | Figure 13 | `integration_connection.next_run_at` | timestamptz | system-derived | computed in the tenant's zone; NULL when manual |
| per-connection offset | — | decision 2 | derived from `connection.id` (hash mod window) | seconds | system-derived | stable across sweeps |
| `catch_up_policy` | — | decision 4 | manifest per operation | enum | reference-data | `latest_only \| never` (money ⇒ `never`) |
| skip row | S142 | decision 3 | `integration_run` `outcome = skipped` | row | system-derived | reason in words |
| `beat_schedule` | — | `C29` | `config/settings/base.py` | dict | code | two entries; the sweep itself is the only scheduler |

**6 · Acceptance**
- Given a nightly cadence in Chicago, then the run happens at Chicago midnight on both sides of the clock change.
- Given a run still going, then the next window is skipped and the skip is visible.
- Given six missed windows on a money-moving operation, then nothing runs by itself and a person is asked.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---
id: US-INT-030
epic: EP-INT-08
module: integrations
screens: [S142, S8]
wave: 3
status: ready
blocked_by: []
depends_on: [US-INT-029]
journeys: [J56]
rules: [BR-INT-034]
golden_tests: []
finance_calc: none
---
### US-INT-030 — The request budget: knowing the allowance has run out before readings stop on a Thursday

**1 · Details** — As **a utility manager**, I want **to see how much of this week's request allowance we have used** — so that **readings stopping on a Thursday is something the screen tells me rather than something a bill tells me**.

Failure 10, the first of the four silent ones: a weekly request quota is spent on Thursday and readings simply stop arriving — **nothing errors, the connection just goes quiet**. A quota is not a rate limit: backoff does not help and a token bucket cannot see it, because a bucket paces requests and this is a total. So a connection declares `budget = {allowance: 10,000, period: week, resets: Monday 00:00 provider time}`, the runtime counts what each run spent, and the due sweep **declines to start a run it cannot finish** — at 9,980 of 10,000 with a collection needing 40 calls, it does not start — records why, **and shows the figure on the screen**: *9,980 of 10,000 requests used this week · resets Monday*. The card carries the same figure when it passes 90 %.

Entry: the due sweep, before enqueue. Exit: a declined row with the figure; S142 and the card show the spend.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-INT-034` | A request budget is not a rate limit: declared allowance and reset; decline what cannot finish; show the spend | PROPOSED — design §1.7 failure 10, §1.9.2 decision 5 |
| `BR-INT-024` | A declined window is recorded, never silent | PROPOSED |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Budget 10,000/week, spent 9,980; a collection needing 40 calls falls due | It **does not start**; a row *declined — 40 requests needed, 20 left this week*; S142 reads **9,980 of 10,000 requests used this week · resets Monday** (doc TC-INT-34) |
| TC-2 | Monday 00:00 provider time passes | The counter resets; the deferred collection starts at its next due time |
| TC-3 | A run of 105 windows spends 105 calls | The spend increments by 105, once, atomically with the run row |
| TC-4 · **negative** | A provider with no declared budget | No figure shown; nothing declined; a gate asserts the manifest either declares a budget or declares `budget = none` explicitly — not omitted |
| TC-5 | The card at 91 % | Reads *9,100 of 10,000 used this week* under the state word; below 90 % the card is silent and S142 still shows it |
| TC-6 · **tenant isolation** | Two tenants with the same vendor | Two budgets; one tenant's spend never counts against the other |

**4 · Test Data** — `meters_neptune360` budget `10,000 / week / resets Monday 00:00 America/New_York`; spent `9,980`; a due collection of 40 calls (TC-1); the 105-window backfill (TC-3).

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| `budget.allowance` · `.period` · `.resets` | — | decision 5 | manifest; overridable in `config` | int/enum/ts | reference-data / user-input | allowance > 0 |
| spend this period | S142 · S8 card | `BR-INT-034` | `integration_connection.config.budget_spent` + `period_started_at` (non-secret) | int/ts | system-derived | incremented with each run row |
| declined row | S142 | `BR-INT-024` | `integration_run` `outcome = skipped`, summary with the figure | row | system-derived | names calls needed and calls left |

**6 · Acceptance**
- Given the allowance is nearly spent, when a run that would exceed it falls due, then it does not start, the reason and the figure are on screen, and it starts after the reset.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---
id: US-INT-031
epic: EP-INT-08
module: integrations
screens: [S142]
wave: 4
status: ready
blocked_by: []
depends_on: [US-INT-016, US-INT-020, US-INT-029]
journeys: [J19]
rules: [BR-INT-046, BR-INT-018]
golden_tests: []
finance_calc: none
---
### US-INT-031 — Completion: immediate, or submit–poll–collect — and a result that is a link, or a handle to collect (C10, C20)

**1 · Details** — As **a billing clerk**, I want **a billing export to say *They are building the file. We will collect it when it is ready · asked them 4 times · checking again in 30 seconds* — and to be able to leave the page** — so that **a file the vendor builds while we wait is collected when it is ready and the run is not called finished until it is**.

Two declared values, forced by one vendor whose export builds a file while we wait and whose two API versions return two different kinds of thing — one a link, the other an identifier. **`completion = submit_poll_collect`**: the runner submits, then polls on the declared schedule (`every 30 s · up to 40 times`) through the job framework — **which already does the waiting** — and the run stays `running` with the attempt count on S142; the clerk can close the page. **`result_delivery = link | handle`**: one runner reads the value and either stores the vendor's link as `artifact_link` or collects by the handle into the artifact store. When the poll budget is exhausted the run is **`unconfirmed`** — *they never finished the file* — never `succeeded` and never silently `failed`.

Entry: a submit-style operation. Exit: `artifact_link` on the run; the collected file in the artifact store.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-INT-046` | Completion and result delivery are declared; a run is not finished until the file is collected | PROPOSED — design §2.18.2, §2.25.9, `C10`, `C20` |
| `BR-INT-018` | An exhausted poll is `unconfirmed`, not succeeded | PROPOSED |
| `BR-INT-020` | File-out key = period + target; regenerating produces the same file or refuses | PROPOSED |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Neptune billing export; vendor fixture answers *building* four times then *ready* with a link | S142 shows the sentence with **asked them 4 times · checking again in 30 seconds** while running; on the fifth poll `artifact_link` is set and the run reads `succeeded` |
| TC-2 | Same operation on the vendor's other version, which returns an identifier | The runner collects by handle into the artifact store; the run reads `succeeded`; **the same runner** served both — a declared value, no branch |
| TC-3 | Alex closes the browser at poll 2 | Nothing changes; the job continues; S142 on return shows the outcome |
| TC-4 · **negative** | 40 polls, never ready | `unconfirmed` · *they never finished the file*; the S8 panel shows attention |
| TC-5 · **negative** | An operation declares `completion = submit_poll_collect` and no poll schedule | Refused at load |
| TC-6 · **tenant isolation** | Two tenants export at once | Two jobs, two handles; neither can collect the other's file |

**4 · Test Data** — `meters_neptune360` operation `billing_export`, `completion = submit_poll_collect`, `poll = {every: 30 s, max: 40}`; fixtures *v1 link* (ready after 4) and *v2 handle*; a *never ready* fixture.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| `completion` · `poll.every` · `poll.max` | — | `C10` | manifest per operation | enum/duration/int | reference-data | required together |
| `result_delivery` | — | `C20` | manifest per operation | enum | reference-data | `link \| handle` |
| collecting sentence · attempt count | S142 | Figure (C10 card) | `jobs.progress` via `record_progress` | text/int | computed-display | one sentence, the two figures |
| `artifact_link` | S142 | `core.jobs.succeed(result_link)` | `integration_run.artifact_link` | url | system-derived | set on collection |

**6 · Acceptance**
- Given a vendor that builds the file while we wait, then the clerk reads how many times we asked and when we ask next, may leave, and the run is finished only when the file is in hand.
- Given two vendor versions returning different things, then one runner collects both from a declared value.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.
