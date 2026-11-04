# EP-RBS-04 — It acts, and you approve: the acting half, dry first and live second

**Module:** runbooks · **Phase:** 2 of 5, **built in two halves** — **was 4, re-cut 2026-09-06; the epic is NOT renumbered** · **Screens:** `RBS-005` run wizard (all six steps, the cap refusal and the check-failed state) · `RBS-004` Limits tab · `RBS-006` result with failures and stopped part-way · `RBS-001` a run in flight · `RBS-008` run history · **Status:** draft (written 2026-09-06)

⚠ **PHASE ORDER RE-CUT 2026-09-06 — THIS EPIC MOVED FROM PHASE 4 TO PHASE 2 AND IS NOT RENUMBERED.** Two
Product Owner rulings that day put the integration runbooks first: *"once you have foundation I want to
prioritise runbook related to integration first and then rest"*, then *"For me integration related to
accounting, payment provider, emails, GIS are important - over other"*. **This epic IS the acting half, and
every integration-driven runbook is an Action — so it has to come first.** It is built immediately after
`EP-RBS-01`, and phases 3 and 5 both stand on it. Order:
[`../10-execution-plan.md`](../10-execution-plan.md) §1.

⚠ **WHAT THIS COSTS AND WHAT PRESERVES THE SAFETY ARGUMENT.** The old order reached this epic only after six
Checks had exercised the engine on real data. **It now arrives after one phase.** The thing that keeps it
safe is unchanged and must stay unchanged: **wave `M` — a full cycle, dry, in production, with sending
switched off and a written go/no-go — stays exactly where it is, between `L` and `N`, at its full length.**
⚠ **SHORTENING `M`, OR FOLDING IT INTO `L`, IS THE ONE CHANGE THAT WOULD MAKE THIS REORDER UNSAFE**, and it
is the one that will look most attractive because `M` produces no code.

⚠ **AND THE AUDIT ACTOR IS NOW A NAMED PREREQUISITE OF THIS EPIC'S FIRST TASK RATHER THAN A NOTE.**
`BR-AUD-003` says `actor_user_id` NULL means *"system job"*, so every automation in the product is
indistinguishable and a runbook would have to borrow a staff login — a person would appear to have
personally sent 812 letters at 07:00 on a Monday. **It blocked the old phase 4 and now blocks phase 2, and
through it phases 3 and 5 as well**: no writer is bound until it lands. Task `L1` closes it, in the audit
module.

⚠ **`US-RBS-010`'s `depends_on` NAMES `US-RBS-007`, WHICH IS NOW LATER.** What it needs from it is task
`I1` — the two job kinds on the platform runner — and `I1` moves forward to land with wave `L`. The rest of
`US-RBS-007` (cron in the tenant's timezone, a missed firing raising) is phase 4 and is not needed here;
until it lands, **wave `M`'s weekly dry run is started by hand**.


## Scope

**In:** everything that writes, and every control on it. **The thirteen ports** — one service function in its owning module each, idempotent per record, each writing its own audit row with the runbook as actor. **The gate** — batch approval carrying the count, conflicting when the plan has moved; a **second approval** on any money-bearing action. **The cap** — refusing the run, never truncating the set. **Stop** — reachable at every moment of a run. **The idempotency key** per runbook, run, record and action kind. **The audit actor** — the runbook, named and versioned, never a staff login. And **the collections ladder (runbook 8)**, in two halves: **DRY-RUN ONLY first, then live.**

**Out:** every other Action. Runbooks 10, 11, 14, 17, 22, 25, 26 and 27 land in `EP-RBS-05`, **on the machinery this phase has already been watched running.**

**Exit test of the dry half.** A clerk runs the ladder on 1,004 past-due accounts and reaches **Review** with **812 to send · 97 skipped · 95 needing a person**, each with the rule that decided it — **and there is no Approve button that can send anything.** The riskiest code in the product is running against real accounts, in production, unable to do anything.

**Exit test of the live half.** The same code queues exactly those notices, **none to a protected or disputed account**, a re-run on the same day queues **nothing twice**, and every acted record carries the runbook, its version and the rule that decided it, with an audit row naming **"Collections ladder · version 3"** and never a person.

---

## Why this phase is split into a dry half and a live half — it is **phase 2** from 2026-09-06, and the split matters more at second than it did at fourth

**Everything dangerous about this feature lives in the acting half: the ports, the cap, the stop, the idempotency key, the audit actor.** Shipping all of it with sending switched **off** means the risky code runs against real accounts, in production, **for a full cycle, while being unable to do anything.** Then the live half is a one-line change to a runbook's kind on machinery that has already been watched.

**Merging the two saves a week and removes the only cheap opportunity to be wrong safely.**

⚠ **THE FAILURE THAT HURTS IS NOT A RUNBOOK DOING NOTHING — SOMEONE NOTICES THAT.** It is **a misconfigured runbook queueing three thousand wrong disconnection notices in four minutes, and a notice cannot be unsent.** The cap, the dry run, the batch approval and the stop button are **first-release requirements, not hardening for later**. Everything else in this module is negotiable; those four are not.

⚠ **AND THE DRY HALF IS NOT A DEMO MODE.** `BR-RBS-003`: **dry run and live run are the SAME code path**, differing only in whether the writer is bound. A dry run that walks a different path proves nothing about the live one — which is why `TC-RBS-2` is first shown red on **a deliberately divergent second implementation**.

## Two dependencies outside this module, both of which must close before the halves they gate

| Dependency | Gates | State |
|---|---|---|
| **The audit actor.** An automated action has no identity today: the audit table records who acted, and a **blank actor means "a system job"**, so every automation in the product is indistinguishable. A runbook needs a **first-class actor carrying its name and version**, and it must never borrow a staff login — or a person will appear to have personally sent 812 letters at 07:00 on a Monday. | **the dry half** — it must exist **before any Action writes anything**, and the dry half is where the port seams first bind a writer | `TC-RBS-12` is first shown red on **the current platform behaviour**: actor left null |
| **A delivery provider connected.** The notification queue fills and **nothing leaves the building** until one is. | **the live half** — the live half means nothing to a customer without it | Until then the word on every screen is **Queued**, never *Sent*, and the copy must not claim otherwise |

## Capability matrix (list screens only — B9 conformance)

| Screen | Search fields | Filters | Default sort | Sortable | Columns default/available | Row actions | Bulk actions | Export |
|---|---|---|---|---|---|---|---|---|
| `RBS-005.3` Review (the plan) | account | outcome (to send · skipped · needs a person) · tier · **why** | tier, then account | account · tier · outcome | account · tier · what would happen · **why** / + amount · channel | Open account | — | — |
| `RBS-006` Records, after acting | account | outcome (queued · skipped · failed · not reached) | outcome, then account | account · outcome | account · tier · outcome · **rule that decided it** · fix route | Open account · Open fix route | — | the two result files |

**Both page on the server** (`NFR-3`). ⚠ **The Review table over 1,004 rows is the first place in this module where an unpaginated list would be tempting and would be wrong**: at T5 the same screen is drawn over an arrears set an order of magnitude larger, and a cap of 400 on the ACT does not cap the PLAN.

---

## Test-case ids — two families, and they are not the same one

⚠ **`TC-RBS-1` … `TC-RBS-25` are the SOURCE's**, carried unchanged from the specification's B7 and
cited by `02-business-rules.md`. **`TC-RBS-<story>.<n>` is NEW and belongs to this pack** — the
number names the STORY the case sits in, never a source case. So `TC-RBS-005.2` is the second new
case of `US-RBS-005` and has nothing to do with `TC-RBS-5`, the savepoint case. **The two patterns
cannot collide:** `TC-RBS-\d+(?!\d|\.)` finds the source's, `TC-RBS-\d{3}\.\d+` finds this
pack's. An earlier draft of these epics used a suffix form (`TC-RBS-5a`) that read as a sub-case of
`TC-RBS-5` and was not one — the same misreading `DEF-2804` cost two days on, one family down.

## Stories · the dry half

---
id: US-RBS-010
epic: EP-RBS-04
module: runbooks
screens: [RBS-005, RBS-004]
phase: 2-dry
status: ready
blocked_by: []
depends_on: [US-RBS-001, US-RBS-007, US-RBS-041]
journeys: [J-RBS-3]
rules: [BR-RBS-003, BR-RBS-004, BR-RBS-009, BR-RBS-010, BR-RBS-012, BR-RBS-014]
golden_tests: []
finance_calc: fee amounts read from the tenant's own ladder; nothing charged in the dry half
---
### US-RBS-010 — As a clerk I see what an Action would do before it does it

**1 · Details** — As **a clerk**, I want **to see exactly what would happen to every account before anything happens to any of them** — so that **I can find the misconfiguration while it is still a list on a screen**.

*Dunning and notices* (runbook 8, displayed as **Collections ladder**) walks accounts past due, applies the tier each account is due, and — in the live half — queues its notice. **In the dry half it plans and stops.** The Review step reads **812 to send · 97 skipped · 95 needing a person**, and **every row states the rule that decided it, in words a clerk can read**.

⚠ **AN ACTION ALWAYS PRODUCES A PLAN FIRST. THERE IS NO ROUTE IN THE PRODUCT THAT ACTS WITHOUT ONE** (`BR-RBS-004`). Not a fast path, not an admin override, not a scheduled exception.

⚠ **GUARDS ARE ABSOLUTE AND ARE EVALUATED BEFORE ANY STEP** (`BR-RBS-012`). An account with **medical protection** appears as **Skipped · Medical protection** *even when every check says send*. A guard evaluated after the checks is a guard that can lose an argument, which is why `TC-RBS-6` is first shown red on exactly that ordering.

⚠ **A SAMPLE RECORD IS NEVER ACTED ON, IN ANY TENANT, AT ANY TIME** (`BR-RBS-014`). A tenant holding sample accounts runs the ladder and **no sample row is touched.**

⚠ **SCOPE IS PINNED** (`BR-RBS-009`): an account becoming past due after the run starts is **absent from the plan and untouched**. The alternative — re-resolving at act time — means the count a person approved is not the count that gets acted on, which is the same defect as a stale approval wearing different clothes.

**Support load rises before it falls.** Expect *"why was this account skipped"* for the first two cycles — which is why the **Why** column exists on Review and why **every skip states its rule in plain words** rather than a code.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-RBS-003` | Dry run and live run are the **same code path**, differing only in whether the writer is bound | PROPOSED |
| `BR-RBS-004` | An Action always produces a plan first; there is no route in the product that acts without one | PROPOSED |
| `BR-RBS-012` | Guards are absolute — a guarded record is skipped whatever the checks conclude | PROPOSED |
| `BR-RBS-014` | A sample record is never acted on by an Action, in any tenant, at any time | PROPOSED |
| `BR-RBS-009` | Scope is resolved once and pinned | PROPOSED |
| `BR-RBS-010` | Every record states the rule that decided it, in words a clerk can read | PROPOSED |

**3 · Test Cases**

| TC | Scenario | Expected | Must first fail on |
|---|---|---|---|
| `TC-RBS-2` | A dry run and a live run over the same pinned scope | **Identical plans** | A deliberately divergent second implementation |
| `TC-RBS-6` | An account with medical protection where every check says send | **Skipped · Medical protection** | The guard evaluated **after** the checks instead of before |
| `TC-RBS-11` | A tenant holding sample accounts | **No sample account is touched** | The guard omitted |
| `TC-RBS-22` | An account becoming past due after the run starts | **Absent from the plan and untouched** | Scope re-resolved at act time |
| `TC-RBS-010.1` · **the dry half's own** | The whole dry half, run against production data for a cycle | **Zero rows written outside this module's seven tables**, asserted by a database diff | A writer bound in dry mode |

**4 · Test Data** — **The ladder set: 1,004 accounts past due** — **812** due a notice · **43** on a plan in good standing · **31** protected · **23** undeliverable · **95** over the fee limit. That is every branch of the dry run and the four figures on the Review screen (**97 skipped** = 43 + 31 + 23). Plus **the guarded accounts**: 2 medical protection · 2 open dispute · **3 sample records**.

**5 · Data Fields / Mapping**

| Field | Screen | DB target | Type | Origin | Validation |
|---|---|---|---|---|---|
| `runbook_runs.mode` | `RBS-005` header | `runbook_runs` | enum `dry` \| `live` | derived | **the dry half never writes `live`** |
| `runbook_run_records.planned_action` · `decided_by_rule` | `RBS-005.3` Review | `runbook_run_records` | enum · text | derived | `decided_by_rule` NOT NULL on every row, in words |
| `runbook_run_records.outcome` | `RBS-006` | `runbook_run_records` | enum | derived | written **only** in the live half; NULL through the dry half, which is itself an assertion |
| guards | `RBS-004` Guards tab | `runbook_versions.definition` | list | user-input | evaluated **before** step 1 |

**6 · Acceptance**
- Given the ladder set, when a clerk dry-runs the ladder, then Review reads **812 to send · 97 skipped · 95 needing a person** and every row names its rule in words.
- Given an account with medical protection, when it is planned, then it reads **Skipped · Medical protection** whatever the checks concluded.
- Given the dry half running in production for a cycle, when the database is diffed, then **nothing outside this module's seven tables changed**.

**7 · Finance Calculation** — Fee amounts on the plan are **read from the tenant's own ladder settings** and displayed to two decimals over four stored. **Nothing is charged in the dry half**; `apply_fee` is declared and bound to no writer.

**8 · Open Questions** — **`OQ-RBS-1733`** (does an admin approve every run, or may a tenant set a runbook unattended once trusted). ⚠ **It blocks nothing.** Until it is ruled, **every run is approved by a person** and the *"Unattended after"* parameter is **drawn read-only with "awaiting a decision"** — a deliberate absence rather than a stub or a guess, so no option is pre-empted.

---
id: US-RBS-011
epic: EP-RBS-04
module: runbooks
screens: [RBS-005, RBS-004]
phase: 2-dry
status: ready
blocked_by: []
depends_on: [US-RBS-010]
journeys: [J-RBS-3]
rules: [BR-RBS-005, BR-RBS-006, BR-RBS-018]
golden_tests: []
finance_calc: the second approval gates every money-bearing action until OQ-RBS-1732 is ruled
---
### US-RBS-011 — As an admin I approve a batch, not a row

**1 · Details** — As **an administrator**, I want **one approval that carries the count** — so that **I am agreeing to a specific thing rather than to a screen I looked at ten minutes ago**.

**Approve shows "Sending to 400 accounts".** If the plan has moved to 806 since Review, pressing Approve returns **"The plan changed. Review it again."** and **nothing is queued** (`BR-RBS-005`; refusal key `runbooks.refusal.plan_changed`, HTTP 409).

⚠ **A CAP REFUSES THE RUN. IT NEVER TRUNCATES THE SET** (`BR-RBS-006`). 812 planned against a limit of 400 shows **"Too many for one run"** with **Narrow scope · Raise limit · Send first 400** as *the clerk's own choices*. **No notice is queued until one is pressed.** A cap that silently sends the first 400 is worse than no cap: it looks like it worked.

⚠ **A MONEY-BEARING ACTION CARRIES A SECOND APPROVAL, SEPARATE FROM THE BATCH APPROVAL** (`BR-RBS-018`). On the Limits tab, **Fees** reads **Second approval**; a deposit refund appears as **Waiting** under *"Refunds awaiting second approval"* and leaves only when a second admin approves it.

⚠ **AND THE APPROVAL IS THE PLACE `NFR-3` MATTERS MOST.** The count is computed **server-side over the pinned scope**, never from what the page happened to load. An approval carrying a count a paginated screen calculated is a stale approval that thinks it is fresh.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-RBS-005` | Approval is per batch and carries the count; a plan that has changed since returns a conflict | PROPOSED |
| `BR-RBS-006` | A cap refuses the run. It never truncates the set | PROPOSED |
| `BR-RBS-018` | A money-bearing action carries a second approval, separate from the batch approval | PROPOSED — **the threshold is the Product Owner's, `OQ-RBS-1732`** |

**3 · Test Cases**

| TC | Scenario | Expected | Must first fail on |
|---|---|---|---|
| `TC-RBS-8` | Approving with a count of 812 after the plan moved to 806 | **409**, and **nothing queued** | An approval that ignores the count |
| `TC-RBS-3` | 812 planned against a cap of 400 | Status stays **awaiting_approval** and **zero** notices are queued | A build that truncates to 400 — it must go red |
| `TC-RBS-011.1` | Pressing **Raise limit** deliberately | The new limit is a **new version** of the runbook, recorded on Activity with who and when | A limit raised in place, leaving no record of who widened it |
| `TC-RBS-011.2` | A money-bearing action with no second approval given | Stays **Waiting**; nothing is charged or refunded | A single approval covering both |
| `TC-RBS-011.3` · **role** | A clerk (not an admin) pressing Approve | Refused | Approval on the Staff role |

**4 · Test Data** — The ladder set at **812 planned** against a cap of **400**; the same plan moved to **806** between Review and Approve. One deposit refund of **$296.40** requiring a second approval, and a second admin to give it. Actors: Tom (Admin), a second Admin, Priya (Billing Clerk).

**5 · Data Fields / Mapping**

| Field | Screen | DB target | Type | Origin | Validation |
|---|---|---|---|---|---|
| `runbooks.cap` | `RBS-004` Limits | `runbooks` | integer | user-input | **required before an Action can be enabled** — see `OQ-RBS-1731` |
| `runbooks.gate_mode` | `RBS-004` Limits | `runbooks` | enum | user-input | second approval on every money-bearing action until `OQ-RBS-1732` |
| `runbook_runs.approved_by` · `approved_count` | `RBS-005.4` · `RBS-008` | `runbook_runs` | uuid · integer | derived | `approved_count` must equal the **server-side** plan count or 409 |
| `runbook_runs.status` | `RBS-005` · `RBS-001` | `runbook_runs` | enum | derived | `queued · running · awaiting_approval · approved · acting · done · failed · stopped` |

**6 · Acceptance**
- Given 812 planned against a cap of 400, when the run reaches the gate, then it reads **"Too many for one run"** with three choices and **nothing is queued** until one is pressed.
- Given the plan moved from 812 to 806, when Approve is pressed with 812, then it returns **"The plan changed. Review it again."** and nothing is queued.
- Given a refund awaiting a second approval, when only one admin has approved, then it stays **Waiting**.

**7 · Finance Calculation** — No arithmetic of this module's own. **Every money-bearing action is gated by the second approval** until `OQ-RBS-1732` narrows it — which is the conservative reading of `BR-RBS-018`, not a chosen value.

**8 · Open Questions** — **Two, both carried against this phase and both non-blocking.**
* **`OQ-RBS-1731` — the default cap for a first run.** ⚠ **Built meanwhile: `cap` is a REQUIRED field with NO default. An Action cannot be enabled until an admin sets one.** That is a deliberate absence, it pre-empts no answer, and it is safer than any number this lane could pick.
* **`OQ-RBS-1732` — which actions need the second approval, and above what amount.** ⚠ **Built meanwhile: EVERY money-bearing action carries it, with no threshold.** A threshold can only widen what is permitted, so shipping without one cannot be wrong in the dangerous direction.

---
id: US-RBS-012
epic: EP-RBS-04
module: runbooks
screens: [RBS-001, RBS-005, RBS-006]
phase: 2-dry
status: ready
blocked_by: []
depends_on: [US-RBS-011]
journeys: [J-RBS-3]
rules: [BR-RBS-007, BR-RBS-008]
golden_tests: []
finance_calc: none
---
### US-RBS-012 — As an admin I can stop a run in flight

**1 · Details** — As **an administrator watching a run go wrong**, I want **to stop it now** — so that **a mistake costs 120 notices rather than 400**.

**Stop is reachable at every moment of a run** — from `RBS-001`, from the wizard's Applying step and from the result. Pressing Stop at **120 of 400** leaves the run marked **Stopped** with **120 queued, 280 untouched**, and the result reads **"Re-run would send 280"**.

⚠ **STOPPING HALTS BEFORE THE NEXT RECORD.** Records already acted **stay acted** and are listed. There is no rollback and there must not be a claim of one: a notice already queued is a notice, and a screen saying otherwise would be a lie about the customer's world.

⚠ **EVERY RECORD EXECUTES IN ITS OWN SAVEPOINT; ONE FAILURE NEVER ABORTS THE RUN** (`BR-RBS-007`). ⚠ **AND THIS IS THE ONE A LANE WILL GET WRONG.** `try: … except IntegrityError: continue` is the obvious way to skip a bad row and carry on. **On PostgreSQL it does not work**: once any statement errors inside a transaction, the transaction is aborted, every later query raises `InFailedSqlTransaction`, and the work is lost at COMMIT anyway. **A SAVEPOINT — a nested `transaction.atomic()` — is not the tidy option, it is the ONLY option**, and the comment must say so or the next lane will simplify it away. ⚠ `config/settings/test.py` **hardcodes in-memory SQLite, which has no aborted-transaction state**, so the broken version passes the entire suite, green, on every machine, and fails the first time a real row is refused in production (hard-won law 14).

⚠ **EVERY ACTION CARRIES AN IDEMPOTENCY KEY OF RUNBOOK, RUN, RECORD AND ACTION KIND** (`BR-RBS-008`). It is what makes a stop safe to recover from, a retry safe to run, and `J-RBS-3`'s last assertion — **a re-run queues 280, not 400** — true in a browser rather than only in a unit test.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-RBS-007` | Every record executes in its own savepoint; one failure never aborts the run | PROPOSED |
| `BR-RBS-008` | Every action carries an idempotency key of runbook, run, record and action kind | PROPOSED |

**3 · Test Cases**

| TC | Scenario | Expected | Must first fail on |
|---|---|---|---|
| `TC-RBS-9` | Stopping after 120 of 400 | **120 acted, 280 untouched**, run marked **stopped** | A stop that only sets a flag nothing reads |
| `TC-RBS-5` · **PostgreSQL only** | One record failing a database constraint | The other **1,003** commit | The naive `try/except`, which **passes on SQLite and loses the run on PostgreSQL** |
| `TC-RBS-4` | Running the ladder twice on the same day | **248 notices in total, not 496** | The idempotency key removed |
| `TC-RBS-012.1` · **journey `J-RBS-3`** | Dry → confirm 97 skipped → approve 400 → stop at 120 → re-run | The re-run queues **280**, not 400 | The key scoped to the run rather than to the record |
| `TC-RBS-012.2` · **screen** | Stop during Applying | The control is **live**, not a placeholder, and the result reads **"Re-run would send 280"** | A greyed Stop over a live run — hard-won law 2's mirror, which `G13` cannot see |

**4 · Test Data** — 400 approved records with a stop injected at record 120. **The failure row:** one account whose notice write fails a database constraint, to prove the savepoint **on PostgreSQL**. A same-day re-run of the ladder for the idempotency case.

**5 · Data Fields / Mapping**

| Field | Screen | DB target | Type | Origin | Validation |
|---|---|---|---|---|---|
| `runbook_run_records.idempotency_key` | — | `runbook_run_records` | text | derived | **UNIQUE on (tenant, idempotency_key)** — the index is what makes a retry safe |
| `runbook_runs.stopped_by` · `status` | `RBS-006` · `RBS-008` | `runbook_runs` | uuid · enum | derived | `stopped` is terminal; a stopped run is re-run, never resumed in place |
| per-record failure reason and fix route | `RBS-006` Records | `runbook_run_records` | text · route | derived | a failed row carries its fix, like every other |

**6 · Acceptance**
- Given a run of 400, when Stop is pressed at 120, then 120 stay queued, 280 are untouched, and the result reads **"Re-run would send 280"**.
- Given one record failing a constraint **on PostgreSQL**, when the run finishes, then the other 1,003 are committed.
- Given the ladder run twice on the same day, when both finish, then **248** notices exist in total.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — **None.**

---

## Stories · the live half

---
id: US-RBS-013
epic: EP-RBS-04
module: runbooks
screens: [RBS-005, RBS-006]
phase: 2-live
status: ready
blocked_by: []
depends_on: [US-RBS-010, US-RBS-011, US-RBS-012, US-RBS-014]
journeys: [J-RBS-3]
rules: [BR-RBS-003, BR-RBS-008, BR-RBS-012, BR-RBS-013, BR-RBS-022]
golden_tests: []
finance_calc: fees applied by the tenant's own ladder rule, behind the second approval
---
### US-RBS-013 — As a clerk the ladder sends the right notice to the right account

**1 · Details** — As **a clerk at a two-person utility**, I want **the ladder to do on Monday morning what I would have done by hand all week** — so that **about 33 hours a month come back**.

**The live half is a change to a runbook's kind on machinery that has already been watched for a cycle.** The same code that produced the plan now queues the notices — **`BR-RBS-003`, and it is the reason this is a one-line change rather than a second implementation.**

**248 notices are queued against the tenant's OWN ladder**, none to a protected or disputed account, and **a re-run sends nothing twice**.

⚠ **THE WORD IS *QUEUED*, NOT *SENT*.** Until a delivery provider is connected **nothing leaves the building**, and the copy must not claim otherwise. A screen reading *Sent* over an unconnected provider is a claim that was not true — the second-largest defect class this repository has.

⚠ **NO ACTION MAY EDIT AN ISSUED INVOICE, A PAYMENT OR A JOURNAL ENTRY** (`BR-RBS-013`, restating hard rule 4). A ladder fee is a **new** row through billing's own service, never an edit of a bill. ⚠ **The three-column narrowing on `payments` — `confirmation`, `memo`, `method_id` through `POST /payments/{id}/correct-reference` — is NOT a port and is not reachable from a runbook.** It is a person correcting a mistyped cheque number on one payment, and widening it anywhere else is a new ruling, not this one.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-RBS-003` | Dry and live are the same code path, differing only in whether the writer is bound | PROPOSED |
| `BR-RBS-008` | Every action carries an idempotency key of runbook, run, record and action kind | PROPOSED |
| `BR-RBS-012` | Guards are absolute | PROPOSED |
| `BR-RBS-013` | No action may edit an issued invoice, a payment or a journal entry | **CONFIRMED — restates hard rule 4** |
| `BR-RBS-022` | A runbook reaches another module only through a named port | PROPOSED |

**3 · Test Cases**

| TC | Scenario | Expected | Must first fail on |
|---|---|---|---|
| `TC-RBS-4` | The ladder run twice on the same day | **248 in total, not 496**; the second Done screen reads **0 queued** and names the 248 already sent | The idempotency key removed |
| `TC-RBS-6` · **live** | 31 protected and 2 disputed accounts in the set | **None receives a notice** | The guard checked in the plan but not at the act |
| `TC-RBS-013.1` · **copy** | Every result and every screen in this module | The word is **Queued**; **no screen says Sent** while no provider is connected | A screen reading *Sent* |
| `TC-RBS-013.2` · **negative** | An Action attempting to update an issued invoice | Refused — the port does not exist | A port that writes to `invoices` |
| `TC-RBS-2` | The same pinned scope, dry then live | **Identical plans**, and the live run queues **exactly** the planned set | Two implementations |

**4 · Test Data** — The tenant's own ladder tiers with **248 accounts due a notice on the run day**; the guarded accounts (2 medical protection · 2 open dispute · 3 sample); one notice write failing a constraint.

⚠ **THE SOURCE USES TWO DIFFERENT FIGURES AND THIS PACK DOES NOT RECONCILE THEM.** The dry half's fixture is the **1,004-account arrears set** yielding **812 planned**; the idempotency and live cases use **248**. The source states both and never says whether they are the same fixture in two states or two fixtures. **The lane seeds both explicitly and names which is which** rather than silently picking one — a figure quoted from the wrong fixture is a test that passes for the wrong reason.

**5 · Data Fields / Mapping**

| Field | Screen | DB target | Type | Origin | Validation |
|---|---|---|---|---|---|
| `queue_notice` port | — | **notifications**' own queue row | — | port | idempotent per record; writes its own audit row |
| `apply_fee` port | — | **billing**'s own service | money `(18,4)` | port | behind the **second approval**; never an edit of an issued bill |
| `runbook_run_records.outcome` · `amount` | `RBS-006` Records | `runbook_run_records` | enum · `NUMERIC(18,4)` | derived | 4 stored, 2 displayed |

**6 · Acceptance**
- Given the tenant's own ladder, when the ladder runs live, then **248** notices are queued and **none** goes to a protected or disputed account.
- Given the same day, when it is re-run, then **0** are queued and the screen names the 248 already sent.
- Given no delivery provider, when a clerk reads any result, then the word is **Queued** and no screen says *Sent*.

**7 · Finance Calculation** — Fees are applied **by the tenant's own ladder rule, through billing's `apply_fee` service, behind the second approval**, at four decimals. **This module computes no fee**; it decides which rule applies and calls the owner.

**8 · Open Questions** — **None of its own.** `OQ-RBS-1732` (the second-approval threshold) applies here; until it is ruled every fee carries the second approval.

---
id: US-RBS-014
epic: EP-RBS-04
module: runbooks
screens: [RBS-006, RBS-008]
phase: 2-live
status: ready
blocked_by: []
depends_on: [US-RBS-010]
journeys: []
rules: [BR-RBS-010, BR-RBS-015, BR-RBS-022]
golden_tests: []
finance_calc: none
---
### US-RBS-014 — As an auditor I can see what the automation did and why

**1 · Details** — As **an auditor, a regulator, or a customer's counsel**, I want **every acted record to name the runbook, its version and the rule that decided it** — so that **the question "why did this customer receive this letter" has an answer that does not need reconstructing**.

**Every acted record carries the runbook, its version, the rule that decided it and an audit row naming the runbook as actor** (hard rule 7: every money action writes `audit_log`).

⚠ **THIS IS THE STORY THE PLATFORM GAP BLOCKS, AND IT MUST CLOSE BEFORE THE DRY HALF BINDS ITS FIRST WRITER.** An automated action currently **has no identity**: the audit table records a blank actor for a system job, so every automation in the product is indistinguishable from every other. **A runbook needs a first-class actor carrying its name and version, and it must NEVER borrow a staff member's login** — or a person will appear to have personally sent 812 letters at 07:00 on a Monday, which is worse than no record at all because it is a record that is wrong.

**Run history shows `By: Schedule`** rather than a person for a scheduled run, and every audit row for an acted record names **"Collections ladder · version 3"**.

⚠ **Regulatory posture, stated because it is the cheapest thing here and the most expensive to retrofit:** every action names the rule that produced it and the version of the runbook that ran. That is what a regulator or a customer's counsel asks for, **and it is cheaper to record from the first run than to reconstruct later.**

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-RBS-015` | The runbook is the audit actor, named and versioned; it never borrows a user identity | ✅ **CONFIRMED — the platform gap CLOSED 2026-09-06** (`US-AUD-010` / `BR-AUD-019`, migration `audit/0007`). `audit_log` carries `actor_kind` · `actor_label` · `actor_version`; a runbook passes `core.audit.AutomationActor` and a clerk reads *"Returned payments, version 4"*. `TC-RBS-12` red first at the tip `a10eae00`, then green. **`L2` — binding a writer that passes it — is still this module's own undone work** |
| `BR-RBS-010` | Every record states the rule that decided it, in words a clerk can read | PROPOSED |
| `BR-RBS-022` | Audit rows are the engine's to write, never a port's | PROPOSED |

**3 · Test Cases**

| TC | Scenario | Expected | Must first fail on |
|---|---|---|---|
| `TC-RBS-12` | Every acted record | An audit row naming **the runbook and its version**, never a user | **Actor left null — the current platform behaviour** |
| `TC-RBS-014.1` · **negative** | A scheduled run | Run history reads **By: Schedule**; **no staff login appears anywhere on it** | A scheduled run borrowing the login of whoever last edited the runbook |
| `TC-RBS-014.2` | An acted record reopened months later | Names the version that ran it, and that version's stored definition is unchanged | The version read live |
| `TC-RBS-014.3` | Every audit row this module writes | Written by the **engine**, never by a port | A port writing its own audit row independently — the row would survive a rolled-back savepoint |

**4 · Test Data** — 400 acted records under *Collections ladder · version 3*, one scheduled run and one manual run by Tom, and one record acted before and after a version bump.

**5 · Data Fields / Mapping**

| Field | Screen | DB target | Type | Origin | Validation |
|---|---|---|---|---|---|
| audit actor | audit rows · `RBS-008` | **audit**'s own table | actor identity | **the platform gap** | carries the runbook's name and version; **never a user id** |
| `runbook_runs.version` | `RBS-006` header · `RBS-008` | `runbook_runs` | integer | pinned at start | never re-read from `runbooks.current_version` |
| `runbook_run_records.decided_by_rule` | `RBS-006` Records | `runbook_run_records` | text | derived | in words a clerk can read, never a rule id (B14 rule 32) |

**6 · Acceptance**
- Given 400 acted records, when the audit trail is read, then every row names **"Collections ladder · version 3"** and none names a person.
- Given a scheduled run, when run history loads, then it reads **By: Schedule**.

**7 · Finance Calculation** — N/A. Hard rule 7 applies to every money action this module causes, and the audit row is the engine's.

**8 · Open Questions** — **None.** ⚠ **A monthly report of what automation did, by runbook** — runs, records acted, notices queued, fees charged, refunds raised, each line naming the version — is a **commitment the source carries and this pack does not schedule** (`RB-048`, which waits on this actor identity). It is named here so it is not silently lost.

---

## What this epic does NOT prove, said out loud

* **Eight of the twelve catalogue Actions are not here.** Cash application, leak alerts, bank reconciliation, autopay pre-notification, undeliverable contacts, payment plans, returned payments and move-outs are `EP-RBS-05`'s, **deliberately** — they land on machinery that has already run against real accounts for a cycle.
* **The event trigger is not here.** `batch.landed`, `feedback.landed` and `bill_run.completed` are **phase 3's** after the 2026-09-06 re-cut (they read *phase 5's* before it), and the first two wait on the integration substrate's door — **which nobody has been commissioned to build; see [`../10-execution-plan.md`](../10-execution-plan.md) §5.**
* **Notice throughput is not measured.** A run of 10,000 text notices showing *"Still sending · 3,140 of 10,000 · about 40 minutes left"* and respecting quiet hours is `RB-044`, which waits on a connected delivery provider and is **not scoped by this phase**.
* ⚠ **AND THE HOLD ON THE LIVE HALF CARRIES ITS OWN EXPIRY TEST, IN THE COMMIT THAT WRITES IT.** Every control the dry half disables asserts, by **address and by screen id**, what it will point at when the live half lands — so the day it lands the suite goes **red** and names the control. A hold with no such test is a promise nobody is keeping, and the customer portal has already paid for that lesson: two working doors out of eight, every one of 42 test files and 391 cases green (`DEF-CWP-3925`).
