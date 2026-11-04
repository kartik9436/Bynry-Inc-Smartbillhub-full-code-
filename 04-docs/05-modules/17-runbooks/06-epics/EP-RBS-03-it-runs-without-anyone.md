# EP-RBS-03 — It runs without anyone: schedules, the work list, and evidence

**Module:** runbooks · **Phase:** 4 of 5 — **was 3, re-cut 2026-09-06; the epic is NOT renumbered** · **Screens:** `RBS-007` Work list · `RBS-008` Run history · `RBS-004` setup renderer (`RBS-004-R2`, `RBS-004-R3`, `RBS-004-R9`) · `RBS-006` result renderer (`RBS-006-R2`, `RBS-006-R3`, `RBS-006-R9`) · **Status:** draft (written 2026-09-06)

⚠ **PHASE ORDER RE-CUT 2026-09-06 — THIS EPIC MOVED FROM PHASE 3 TO PHASE 4 AND IS NOT RENUMBERED.** Two
Product Owner rulings that day put the integration runbooks first: *"once you have foundation I want to
prioritise runbook related to integration first and then rest"*, then *"For me integration related to
accounting, payment provider, emails, GIS are important - over other"*. Every integration-driven runbook is
an Action, so the acting half (`EP-RBS-04`) is now **phase 2** and this epic shares **phase 4** with
`EP-RBS-02`. Order: [`../10-execution-plan.md`](../10-execution-plan.md) §1.

⚠ **THREE CONSEQUENCES FOR THIS EPIC, AND ALL THREE MATTER TO A LANE BUILDING IT.**

**(1) Task `I1` — the two job kinds `runbooks.check` and `runbooks.act` on the existing platform runner —
WAS SAID TO LAND EARLY WITH WAVE `L` IN PHASE 2, AND IT DID NOT (`DEF-RBS-4353`, corrected 2026-09-07).**
The reasoning was sound — wave `M`'s soak and wave `O`'s event trigger both need something to run
unattended on, and both are before this epic — but the row moved and the work did not: wave `L` landed and
the two strings existed in three documents and in no Python file. **`I1` is built by wave `I`, 2026-09-07**,
with the `runbooks` queue and its consumer in the same commit. The rest of wave `I` — cron in the tenant's
timezone (`I2`, done), a missed firing raising (`I3`, done), `requires` wiring (`I4`, still owed) — stays
here. ⚠ **A STRUCK ROW IS NOT EVIDENCE.** Nothing in this repository compares a plan's status word against
the code it claims, and this is the second time in two days a *done* has turned out to be a *moved*.

**(2) `US-RBS-010` and `US-RBS-017` name `US-RBS-007` in their `depends_on` and are now built BEFORE it.**
What each of them actually needs is `I1` and nothing else in this story; the scheduling policy is this
epic's. The frontmatter is left as it is because the handoff contract is real — read this note with it.

**(3) The exception kind can now be proved on a REAL exception.** §4's test data below assumed *"Actions do
not exist until phase 4, so the exception kind is proved on a seeded row"*. **Under the new order the
collections ladder is already live**, so the seeded row is no longer the only option — and the work list
arriving AFTER the Actions that fill it is the cost: until wave `H` lands, an exception is readable on its
own run's result screen and nowhere else.


## Scope

**In:** the product's first **scheduled** work and the two surfaces that make it legible. **Scheduling on the platform job runner, evaluated in the tenant's timezone**, with a missed firing **raising** rather than silently catching up. **The work list (`RBS-007`)** — findings from Checks, exceptions from Actions and human tasks from a cutover plan, all in one table with provenance back to the run that raised them, **upserted by fingerprint so a repeated finding ages rather than duplicating**. **Run history (`RBS-008`)** across every runbook. Three more Checks: the **pre-bill sweep** (runbook 3), **cutover reconciliation** (runbook 2) and **books tie-out** (runbook 9). **Cutover plans and plan items with evidence** — a plan item optionally names a runbook, and the run's result becomes the item's evidence. **The `requires` declaration wired**: one Check runs first as its own run, linked from step 1 of the caller, and a failed requirement stops the caller with **"Never reached"** on every later step.

**Out:** everything that writes to another module. **This epic still binds no port — but phase 4 is not a phase that binds none.** After the 2026-09-06 re-cut, phase 2 has already bound all thirteen; the property below is this epic's own, which is a sharper claim than the one this line used to make. Runbook 9's **Close period** button is drawn and is **a person's act performed by the ledger module**, never a step of the runbook (`BR-RBS-030`).

**Exit test of the phase — a demonstration, not an opinion.** Nobody opens the product. At **06:00 tenant local** the pre-bill sweep runs, and when a clerk arrives the work list holds the accounts that would have failed the run **with the step that would have stopped each one and the screen that fixes it**. Thirty days of that sweep over one missing read produce **one work item, thirty days old** — not thirty items.

⚠ **WHY THIS PHASE EXISTS AS ITS OWN OUTCOME.** Phases 1 and 2 are things a person presses. This is the first phase where **the product does something while the utility is asleep**, and the value is entirely in the timing: problems arrive **before** the bill run instead of during it. A sweep that produced the same findings at the same moment as the run would be worth nothing.

## Capability matrix (list screens only — B9 conformance)

| Screen | Search fields | Filters | Default sort | Sortable | Columns default/available | Row actions | Bulk actions | Export |
|---|---|---|---|---|---|---|---|---|
| `RBS-007` Work list | title · subject | source (check · exception · human task) · status · owner · due | weight, then age | age · due · weight · status | title · subject · raised by · age · owner · due · status / + fix route · run | Open fix route · Assign · Resolve · Reopen | Assign · Resolve | CSV |
| `RBS-008` Run history | runbook name | runbook · category · outcome · date range · mode | started, newest first | started · runbook · outcome | started · runbook · version · mode · trigger · outcome · counts / + duration · approver | Open result | — | CSV |

**Both page on the server** (`NFR-3`), `per` clamped to 50/100/200/500/1000, default 50. ⚠ **Neither copies the four `NFR-3` breaches named in `DEF-PAY-4221`** — `GET /outstandings`, `GET /cheques`, the bank-rec batch list and their two front-end mirrors are unpaginated *on purpose* on the argument that a utility under 3,000 connections has few rows. **That argument names a ceiling this repository abandoned**, and neither of these screens is built on it: run history over a 40,000-account tenant running twelve scheduled runbooks daily is six figures of rows within a year.

## Test-case ids — two families, and they are not the same one

⚠ **`TC-RBS-1` … `TC-RBS-25` are the SOURCE's**, carried unchanged from the specification's B7 and
cited by `02-business-rules.md`. **`TC-RBS-<story>.<n>` is NEW and belongs to this pack** — the
number names the STORY the case sits in, never a source case. So `TC-RBS-005.2` is the second new
case of `US-RBS-005` and has nothing to do with `TC-RBS-5`, the savepoint case. **The two patterns
cannot collide:** `TC-RBS-\d+(?!\d|\.)` finds the source's, `TC-RBS-\d{3}\.\d+` finds this
pack's. An earlier draft of these epics used a suffix form (`TC-RBS-5a`) that read as a sub-case of
`TC-RBS-5` and was not one — the same misreading `DEF-2804` cost two days on, one family down.

## Stories

---
id: US-RBS-006
epic: EP-RBS-03
module: runbooks
screens: [RBS-007]
phase: 4
status: ready
blocked_by: []
depends_on: [US-RBS-001]
journeys: [J-RBS-1]
rules: [BR-RBS-011, BR-RBS-017, BR-RBS-022]
golden_tests: []
finance_calc: none
---
### US-RBS-006 — As a clerk I find every open item in one place

**1 · Details** — As **a clerk**, I want **one list holding everything waiting on a person, whatever raised it** — so that **I open one screen each morning instead of remembering which of eleven runbooks found something**.

`RBS-007` holds three kinds of row in one table: **findings** from Checks, **exceptions** from Actions, and **human tasks** from a cutover plan. Each carries **where it came from** — the run that raised it — its **weight**, its **subject**, its **owner**, its **due date** and **the screen that fixes it**.

⚠ **A WORK ITEM IS UPSERTED BY FINGERPRINT, AND THIS IS THE PROPERTY THAT MAKES THE SCREEN USABLE AT ALL.** The daily pre-bill sweep raises the same missing read for thirty days. **That must be one item ageing, not thirty items.** The fingerprint is the runbook, the subject and the finding kind; the row's age is what tells a clerk this has been ignored for a month.

⚠ **A WORK ITEM IS DERIVED, NOT HAND-MANAGED.** Fix the tax region and re-run, and **the item closes itself** — that is `J-RBS-1`'s assertion and the reason the item is keyed by fingerprint rather than by a person's tick. A clerk may still assign, resolve or reopen one; what they may not do is have a resolved item silently re-raised as a new row.

⚠ **RAISING A WORK ITEM IS AN ENGINE ACT, NOT A PORT** (`BR-RBS-022`). A Check returns findings; the engine upserts them when the run closes. **That is exactly how a Check with no writer populates this screen.** A lane that makes `raise_work_item` a port has made every Check able to write.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-RBS-017` | A work item is upserted by fingerprint so a repeated finding ages rather than duplicating | PROPOSED |
| `BR-RBS-011` | A failure names its fix route; a failure with no route is a defect in the runbook | PROPOSED |
| `BR-RBS-022` | Work items and audit rows are the ENGINE's to write, never a port | PROPOSED |

**3 · Test Cases**

| TC | Scenario | Expected | Must first fail on |
|---|---|---|---|
| `TC-RBS-10` | Thirty daily sweeps over one missing read | **One** work item, **thirty days old** | Insert instead of upsert — thirty rows |
| `TC-RBS-006.1` · **journey `J-RBS-1`** | Fix the tax region, re-run *Can we bill?* | The blocker count falls 3 → 2 **and the item closes itself** | An item closed by a person's tick — it would stay open |
| `TC-RBS-006.2` | A resolved item whose finding recurs | The **same row** reopens with its history, not a second row | A fingerprint including the run id |
| `TC-RBS-006.3` · **B14** | Every visible cell | No database id, no rule id, no internal code (rules 31, 32) | A row headed by `work_item_id` |
| `TC-RBS-7` · **tenant isolation** | Two tenants with the same finding on accounts of the same number | Each sees only its own, RLS `FORCE` on | A fingerprint that omits the tenant |

**4 · Test Data** — Thirty consecutive daily sweeps over an estate with **one** missing read, one resolved-then-recurring finding, three human tasks from an open cutover plan, and one exception row seeded directly. ⚠ **THIS PARENTHESIS SAID *"Actions do not exist until phase 4"* AND THE 2026-09-06 RE-CUT REVERSED IT: the ladder is live from phase 2, so the exception kind can be proved on a REAL exception here** — the seeded row stays as the deterministic case, not as the only one.

**5 · Data Fields / Mapping**

| Field | Screen | DB target | Type | Origin | Validation |
|---|---|---|---|---|---|
| `source_kind` · `source_run_id` | `RBS-007` *raised by* | `work_items` | enum · uuid | derived | `source_run_id` NOT NULL for check and exception rows; NULL for a human task |
| `fingerprint` | — | `work_items` | text | derived | **UNIQUE per tenant**; never contains the run id; never rendered (B14 rule 31) |
| `title` · `weight` · `subject_ref` · `fix_route` | `RBS-007` columns | `work_items` | text · integer · ref · route | derived | `fix_route` NOT NULL for check and exception rows |
| `owner_user_id` · `due_on` · `status` · `resolved_at` | `RBS-007` columns | `work_items` | uuid · date · enum · timestamp | user-input / derived | resolving stamps `resolved_at`; reopening clears it and keeps the row |

**6 · Acceptance**
- Given thirty daily sweeps over one missing read, when a clerk opens the work list, then there is **one** item and it is **thirty days old**.
- Given the tax region is fixed and *Can we bill?* re-run, then the item **closes itself** and the blocker count falls from 3 to 2.

**7 · Finance Calculation** — N/A. A money figure appearing on a work item is quoted from the run record that raised it, displayed to two decimals over four stored.

**8 · Open Questions** — **None.**

---
id: US-RBS-007
epic: EP-RBS-03
module: runbooks
screens: [RBS-004, RBS-007, RBS-008]
phase: 4
status: ready
blocked_by: []
depends_on: [US-RBS-006, US-RBS-001]
journeys: [J-RBS-1]
rules: [BR-RBS-009, BR-RBS-016, BR-RBS-027]
golden_tests: []
finance_calc: none
---
### US-RBS-007 — As a clerk I have checks run on a schedule

**1 · Details** — As **a clerk**, I want **the pre-bill sweep to run itself in the days before a bill run** — so that **the accounts that would fail are on my desk days early rather than in the middle of the run**.

*Ready for billing?* (runbook 3, displayed as **Pre-bill sweep**) walks **every account due in the next cycle** in **eight read steps**: every meter has a read inside the window · reads pass validation · a plan in force for the whole period · rates cover the usage · prorations resolvable · no open corrections · prior period closed · **price a sample — one account per plan, through the real engine**. It produces **Ready**, or *N accounts will fail*, each with its step, its reason and the screen that fixes it; estimates are listed separately as warnings.

**Scheduling.** Triggers become jobs on the **existing** platform runner using its own naming, **one scheduler and not two** — both integration fetches and runbook runs are job kinds on the one runner. **Cron is evaluated in the TENANT's timezone**, which the notification schedule already does. A runbook set to *Daily 06:00* with `America/Chicago` runs at 06:00 Chicago and shows its next run on its Overview tab.

⚠ **A MISSED FIRING RAISES; IT DOES NOT SILENTLY CATCH UP.** It appears in run history as **Failed**, not as an absence. An absence is invisible to every check this repository has, and *"the sweep did not run for nine days"* is the kind of fact that is only ever discovered by the bill run failing.

⚠ **`BR-INT-054` PUTS THE SCHEDULER ON THIS SIDE OF THE LINE, AND THE QUEUE AND THE WORKER ON THE OTHER.** Deciding *when* — the utility's own midnight, spreading tenants so they do not fire together, skipping a run that is still going — is **scheduling** and is ours. **How the work runs** is the queue and the worker, which stay with integrations; Runbooks runs on them.

⚠ **THE `requires` DECLARATION IS WIRED HERE**, because runbook 3 and runbook 2 are the first to use it: a required Check runs **first, as its own run**, linked from step 1 of the caller; when it fails, the caller stops and every later step reads **"Never reached"** (`BR-RBS-027`).

⚠ **SCOPE IS RESOLVED ONCE AND PINNED** (`BR-RBS-009`). An account that becomes due after the run starts is not in the plan and is not touched. On a Check this changes nothing a customer can see; it was built here so that the acting half would inherit it already proved — ⚠ **and the 2026-09-06 re-cut reversed that direction: the acting half is now phase 2 and this epic is phase 4, so `BR-RBS-009` is proved BEFORE this epic and inherited BY it**.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-RBS-016` | A schedule is evaluated in the tenant's timezone, and a missed firing raises rather than silently catching up | PROPOSED |
| `BR-RBS-027` | A runbook may require one other Check; the engine runs it first as its own run, links it from step 1, and a failed requirement stops the caller with "Never reached" on every later step | PROPOSED |
| `BR-RBS-009` | Scope is resolved once and pinned; a record entering the set mid-run is not acted on | PROPOSED |

**3 · Test Cases**

| TC | Scenario | Expected | Must first fail on |
|---|---|---|---|
| `TC-RBS-007.1` | A runbook set to Daily 06:00, `America/Chicago`, nobody logged in | It runs at **06:00 Chicago** and raises its work items | Cron evaluated in UTC — ⚠ this is `DEF-MET-4101`'s shape: a clock question answered in the wrong frame, where every check compared UTC and the product showed local, so the two never met |
| `TC-RBS-007.2` | The runner is down across a firing | Run history shows **Failed**, naming the missed time; no silent catch-up | A scheduler that skips quietly, or one that fires six times on recovery |
| `TC-RBS-21` | *Ready for cutover?* with a failing configuration check | Stops after step 1, **links the sub-run**, and shows **"Never reached"** on steps 2 to 9 | Steps 2 to 9 running anyway |
| `TC-RBS-22` | An account becoming due after the run starts | **Absent from the plan and untouched** | Scope re-resolved at act time |
| `TC-RBS-007.3` · **tenant isolation** | Two tenants, two timezones, one runbook key | Each fires on its own clock and reads only its own rows | A single global beat entry |

**4 · Test Data** — The two-service fixture with **1,410 accounts due on 20 September** on cycle *Monthly A*; the sweep set to run each day **from 5 days before**, at 06:00 `America/Chicago`. One tenant on `America/New_York` for the timezone case. One deliberately missed firing. One failing configuration check, to prove the `requires` chain and the *Never reached* rendering.

**5 · Data Fields / Mapping**

| Field | Screen | DB target | Type | Origin | Validation |
|---|---|---|---|---|---|
| `trigger_kind` · `cron` · `timezone` | `RBS-004` Overview | `runbooks` | enum · text · IANA tz | user-input | tz from the tenant's own setting; `cron` valid or refused at save |
| `runbook_runs.trigger` · `parent_run_id` | `RBS-008` · `RBS-006` step 1 | `runbook_runs` | enum · uuid | derived | `parent_run_id` NOT NULL on a required Check's run |
| `runbook_runs.scope_fingerprint` | — | `runbook_runs` | text | derived at start | never recomputed during the run |
| next-run time | `RBS-004` Overview | derived | timestamp | derived | rendered in the tenant's timezone with its zone named |

**6 · Acceptance**
- Given the sweep scheduled at 06:00 `America/Chicago`, when nobody opens the product, then it runs at 06:00 Chicago and the work list holds the accounts that would fail, each with its step and its fix route.
- Given a firing is missed, when a clerk opens run history, then it reads **Failed** and names the missed time.
- Given the configuration check fails, when *Ready for cutover?* runs, then it stops at step 1 and steps 2 to 9 read **Never reached**.

**7 · Finance Calculation** — **Reads only.** Step 8 prices a sample through the real engine — `EP-RBS-02`'s path, not a second implementation.

**8 · Open Questions** — **None.** ⚠ **The spring-forward mirror is recorded rather than asked** (`BR-INT-062`): when the clock goes back and a wall-clock time occurs twice, the batch runs **once** — *late is a delay, twice is a duplicate* — and the case where the time never occurs at all is unruled. It cannot be reached by a Check and is settled before the first scheduled Action — **which after the 2026-09-06 re-cut is in phase 2, not phase 4, so it is settled EARLIER than this line assumed** — under `BR-INT-024`'s existing frame.

---
id: US-RBS-008
epic: EP-RBS-03
module: runbooks
screens: [RBS-004, RBS-006, RBS-007]
phase: 4
status: ready
blocked_by: []
depends_on: [US-RBS-005, US-RBS-007]
journeys: []
rules: [BR-RBS-026, BR-RBS-027, BR-RBS-014]
golden_tests: []
finance_calc: reconciliation arithmetic at 4 decimals, displayed at 2
---
### US-RBS-008 — As an implementer I reconcile a cutover

**1 · Details** — As **an implementer at freeze**, I want **the loaded balances compared against the legacy trial balance, and the answer kept as evidence on the plan** — so that **go-live is a decision with a document behind it rather than a feeling**.

*Ready for cutover?* (runbook 2, displayed as **Cutover reconciliation**) takes three inputs — the cutover plan, the legacy trial balance **as a file through the import runner**, and an as-at date — and runs **nine read steps**: the configuration check passes (`requires`, runbook 1) · counts agree · **balances tie — every account within $0.01, the total within 0.05%** · deposits and credits match · plans and levels carried · numbering continues · **sample data gone** · coverage grid green · plan items complete.

**The verdict is a `Verdict` block** — *No-go · 2 of 9 steps not clear · Balances off by $1,204.05 · 2 plan items open* — over a `Reconciled` block of ours · theirs · difference.

⚠ **THE RESULT BECOMES THE PLAN ITEM'S EVIDENCE, AND THAT IS THE WHOLE INTEGRATION BETWEEN A PLAN AND THE ENGINE.** A plan item optionally names a runbook; the run id and its figures are stored on the item; a **zero-variance re-run turns the item green on its own**. A **human-only item names no runbook** and is completed by a person attaching a file or ticking it — `cutover_plan_items.runbook_key` being NULL is what says so.

⚠ **CUTOVER OPEN ITEMS ARE CARRIED AS ONE LINE PER OPEN INVOICE** — PO ruling 2026-09-05. Not one line per account and not a single total: an account with four open invoices is four lines, because that is what the legacy system hands over and what a clerk reconciles against.

⚠ **ONBOARDING & CUTOVER IS THE ONE CATEGORY WITH AN ORDER RULE** (`BR-RBS-026`): first in the library while a plan is open, last once it closes. No other category carries one, and adding a second is a rule change rather than a preference.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-RBS-027` | A required Check runs first as its own run and a failure stops the caller with "Never reached" | PROPOSED |
| `BR-RBS-026` | Onboarding & Cutover sorts first while a cutover plan is open and last once it closes | PROPOSED |
| `BR-RBS-014` | A sample record is never acted on — step 7 refuses a cutover while one remains | PROPOSED |

**3 · Test Cases**

| TC | Scenario | Expected | Must first fail on |
|---|---|---|---|
| `TC-RBS-008.1` | The cutover pair fixture | **12 accounts disagree, total variance $1,204.0500** stored to four decimals and shown as **$1,204.05**; the verdict reads **No-go** | Money held as a float, or rounded before the comparison |
| `TC-RBS-008.2` | The variances resolved and a re-run | Zero variance and **the plan item goes green on its own** | An item ticked by a person — it would go green without the evidence |
| `TC-RBS-008.3` | An account with four open invoices | **Four lines**, not one | One line per account, or a single total |
| `TC-RBS-21` | The configuration check fails | Stops after step 1; steps 2 to 9 read **Never reached** | Steps 2 to 9 running anyway |
| `TC-RBS-008.4` | A tenant still holding sample rows | Step 7 fails and the verdict is **No-go** | The sample flag read at act time rather than as a guard |

**4 · Test Data** — **The cutover pair:** a legacy trial balance of **$412,880.4400** against loaded balances **differing on 12 accounts by $1,204.0500**. 2,907 loaded accounts against 2,911 in the file. One account with four open invoices. Three sample rows, removed between the two runs. A cutover plan named *Silver Creek go-live* with two open human tasks.

**5 · Data Fields / Mapping**

| Field | Screen | DB target | Type | Origin | Validation |
|---|---|---|---|---|---|
| `cutover_plans.name` · `go_live_on` · `status` · `closed_at` | `RBS-007` · `RBS-004-R2` Scope | `cutover_plans` | text · date · enum · timestamp | user-input | `status` drives `BR-RBS-026`'s ordering |
| `cutover_plan_items.seq` · `title` · `owner` · `due_on` · `runbook_key` · `last_run_id` · `evidence_ref` · `status` | `RBS-007` | `cutover_plan_items` | — | user-input / derived | **a NULL `runbook_key` is a human task the engine never performs** |
| legacy trial balance | `RBS-004-R2` Scope | `runbook_versions.definition` (parameter type **`file`**) | file | user-upload | read **once** by the run, through the import runner |
| variance per account | `RBS-006-R2` Reconciled | `runbook_run_records.amount` | `NUMERIC(18,4)` | derived | **4 decimals stored, 2 displayed** (hard rule 2) |

**6 · Acceptance**
- Given the cutover pair, when the reconciliation runs, then 12 accounts disagree with a total variance of **$1,204.05** on screen and the verdict reads **No-go**.
- Given the variances are resolved, when it re-runs, then the plan item reads **Evidence attached** and goes green on its own.

**7 · Finance Calculation** — **Comparison arithmetic only, at four decimals.** Money tolerance **$0.01** per account, total tolerance **0.05%**; percentages are stored to six decimals. **No amount is written anywhere** — this is a Check, and the comparison is a read against the ledger's own figures. Nothing here touches B4.

**8 · Open Questions** — **None on the arithmetic.** ⚠ **The source carried an open decision on whether the cutover plan is a product screen now or a spreadsheet for the first two customers.** It is built as a product screen here, because a spreadsheet cannot hold a run id as evidence and the evidence is the point of the story. Recorded as this pack's judgment under law 13, visible to overrule.

---
id: US-RBS-009
epic: EP-RBS-03
module: runbooks
screens: [RBS-004, RBS-006, RBS-007]
phase: 4
status: ready
blocked_by: []
depends_on: [US-RBS-007]
journeys: []
rules: [BR-RBS-013, BR-RBS-023, BR-RBS-029, BR-RBS-030]
golden_tests: []
finance_calc: tie-out comparisons at 4 decimals; tax tolerance $0.00
---
### US-RBS-009 — As a finance user I see what does not balance at month end

**1 · Details** — As **a finance user on the last day of the month**, I want **the exceptions assembled for me** — so that **I spend the evening settling three things rather than finding them**.

*Month-end completion* (runbook 9, displayed as **Books tie-out**) walks one accounting period in **nine steps**: every run finished · every payment posted · unapplied cash listed and within the amount allowed · receivables tie to the control account **to the cent** · revenue and tax tie per service · bank reconciled · adjustments approved · deposits and refunds reconcile · exports ready.

It produces **Balanced — with the figures** — or the list of what is not, **each item linking to the screen that settles it**: *Not balanced · 6 of 9 steps clear · Tax off by $14.25 · $312.00 unapplied · 3 bank lines unmatched*.

⚠ **THE TAX TIE-OUT TOLERANCE IS `$0.00` AND CANNOT BE RAISED** (`BR-RBS-029`). It is not a parameter with a conservative default; it is a floor. A tenant may not widen it and neither may a lane.

⚠ **CLOSING THE PERIOD IS A NAMED PERSON'S ACT, NEVER A STEP** (`BR-RBS-030`). The **Close period ✓** button is **DRAWN DISABLED WITH ITS REASON while blockers remain — never hidden** (`RBR-06`, B14), carries the **danger tier** because it is an irreversible commit (B14 rule 6), and **the ledger module performs it**. ⚠ **THIS SENTENCE READ *"appears on the verdict band only when the list is empty"* UNTIL 2026-09-07 AND IT WAS WRONG (`DEF-RBS-4360`)** — against five sources including the `RBS-006-R9` build sheet, which is the acceptance check and says *"DISABLED — reason on the button title"*, `RB-109`'s own *stated absences* section which closed this question that way, `contract.PAYLOAD_FIELDS` where `enabled: false` structurally requires a `reason`, and the shipped `ActionBlock.tsx`. **The distinction: a control is ABSENT when the CAPABILITY does not exist** — wave `L7`'s Approve, because nothing can send — **and DISABLED when a PRECONDITION is not met.** Hiding it would leave a finance user hunting for a button nobody told them about. ⚠ **And the reason counts BLOCKERS rather than list rows:** on the seeded utility's August the list has six rows and four of them block, and a button saying *"4 items open"* over a table of six is a mismatch a finance user would stop and try to resolve. The runbook has no port for it and never will while this rule stands. ⚠ Whether it may EVER be automated once every tie-out is clear is **`OQ-RBS-1736`, now carried against phase 4** (it was phase 5; wave `K` moved and the question moved with it) — it blocks nothing here, because the answer *no* is what is built.

⚠ **THIS IS THE PHASE'S SET-MODE STORY.** Month-end is mostly set steps: a tie-out over 1,410 bills executes its set step **once**, and its per-record step 1,410 times. Without set mode it would be awkward and slow over 1.2M journal lines — which is why `BR-RBS-023` is a declaration on the step rather than a scheduling detail.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-RBS-029` | The month-end tie-out tolerance for tax is **$0.00** and cannot be raised | PROPOSED |
| `BR-RBS-030` | Closing the accounting period is a named person's act, never a step of a runbook | PROPOSED |
| `BR-RBS-023` | A set-mode step runs once over the pinned set; a per-record step once per subject in its own savepoint | PROPOSED |
| `BR-RBS-013` | No action may edit an issued invoice, a payment or a journal entry; corrections go through the owning module | **CONFIRMED — restates hard rule 4** |

**3 · Test Cases**

| TC | Scenario | Expected | Must first fail on |
|---|---|---|---|
| `TC-RBS-17` | A tie-out over **1,410 bills** | The set step executes **once**; the per-record step **1,410** times | The set step registered as per-record |
| `TC-RBS-009.1` | A period where tax is off by **$0.01** | **Not balanced**; the tolerance cannot be raised to pass it | A configurable tax tolerance |
| `TC-RBS-009.2` | A balanced period | **Close period ✓** appears, in the **danger** tier, and pressing it calls the **ledger's** own close | The runbook closing the period itself |
| `TC-RBS-009.3` | An unbalanced period | **Close period ✓ is absent**, not merely disabled | A greyed button, which reads as *later* rather than as *not yet* |
| `TC-RBS-009.4` | Every unbalanced item | Links the screen that settles it | An item with no route (`TC-RBS-14` covers the scan) |

**4 · Test Data** — August 2026 with **3 bill runs · 4,118 payments · 61 adjustments**; the unbalanced case seeded to produce exactly **tax off by $14.25 · $312.00 unapplied · 3 bank lines unmatched**, and the balanced case with all nine steps clear. One period with tax off by **$0.01**, to prove the floor.

**5 · Data Fields / Mapping**

| Field | Screen | DB target | Type | Origin | Validation |
|---|---|---|---|---|---|
| `period` · `books` · `currency` | `RBS-004-R9` Scope | `runbook_versions.definition` | ref:object · enum · `CHAR(3)` | user-input | currency `CHAR(3)`; never a float, never cents |
| `tie_out_tolerance` · `unapplied_allowed` | `RBS-004-R9` Parameters | `runbook_versions.definition` | money · money | **fixed for tax** | tax tolerance is `$0.0000` and refuses any other value |
| every tie-out difference | `RBS-006-R9` Reconciled | `runbook_run_records.amount` | `NUMERIC(18,4)` | derived | 4 stored, 2 displayed |
| close-period act | `RBS-006-R9` Action block | **ledger's own tables** | — | a person's act | performed by ledger; this module writes nothing |

**6 · Acceptance**
- Given an unbalanced August, when books tie-out runs, then the verdict reads **Not balanced · 6 of 9 steps clear** with the three figures, each item linking to the screen that settles it.
- Given a balanced August, when it runs, then **Close period ✓** appears in the danger tier and pressing it calls the ledger's close.
- Given tax is off by one cent, when it runs, then it is **Not balanced** and no tolerance can make it pass.

**7 · Finance Calculation** — **Comparisons only, at four decimals, displayed at two.** Receivables sub-ledger to control account **to the cent**; revenue and tax billed totals to posted totals **per service**; tax tolerance **$0.0000**. **Only the ledger posting service writes journal lines** (hard rule 5) and this module is not it. No figure here is new; every one is read from the ledger.

**8 · Open Questions** — **`OQ-RBS-1736` is carried against phase 4** (may closing the period ever be automated once every tie-out is clear). ⚠ **It read *phase 5* until the 2026-09-06 re-cut**: its deliberate absence is built in wave `K`, and wave `K` is now phase 4. ⚠ **It blocks nothing here**: `BR-RBS-030`'s answer — a named person's act — is what phase 3 builds, so a *yes* later is an addition and a *no* is the status quo.

---

## What this epic does NOT prove, said out loud

* **No port is bound and nothing is sent.** All three runbooks are Checks. The `Action` block on runbook 9's result draws **a button a person presses**, performed by the ledger — not a runbook act, and not a port.
* **`TC-RBS-5` runs on PostgreSQL or it proves nothing.** The savepoint per record is phase 1's, and this epic is the first to exercise it under a **scheduled** run nobody is watching (phase 2's Actions exercise it first under a run a person starts). ⚠ A skip-and-continue written the obvious way **passes the entire SQLite suite on every machine and loses the run the first time a real row is refused** (hard-won law 14).
* **The `requires` chain has one link, deliberately.** A runbook may require **one** other Check, and the required Check is run as its own run. Chains of three are not built and are not a deferral: no defined runbook needs one, and the rule says one.
* **Run history is a list with no retention rule of its own.** ⚠ The specification's thirteen-month partitioning of run records is one of the four commitments waiting on an **80,000-account change request** and is **not scoped** (decision log 2026-09-06). `NFR-3` paging is what makes the screen correct at 40,000; partitioning is what would make it fast at 80,000, and we are not building for 80,000.
