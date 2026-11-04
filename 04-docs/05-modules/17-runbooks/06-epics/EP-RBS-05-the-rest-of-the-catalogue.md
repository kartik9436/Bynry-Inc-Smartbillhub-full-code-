# EP-RBS-05 — The rest of the catalogue, on the proved engine

**Module:** runbooks · **Phase:** **3 and 5 of 5** — **was 5 only; re-cut 2026-09-06, and the epic is NOT renumbered or split** · **Screens:** **none new.** Every runbook here arrives on `RBS-002` as a template card, renders on `RBS-004` as a setup and on `RBS-006` as a result, the day its module lands · **Status:** draft (written 2026-09-06)

⚠ **PHASE ORDER RE-CUT 2026-09-06 — THIS EPIC NOW SPANS TWO PHASES AND IS NOT RENUMBERED OR SPLIT.** Two
Product Owner rulings that day: *"once you have foundation I want to prioritise runbook related to
integration first and then rest"*, then *"For me integration related to accounting, payment provider,
emails, GIS are important - over other"*. Order: [`../10-execution-plan.md`](../10-execution-plan.md) §1.

| | Waves | Runbooks | Stories |
|---|---|---|---|
| **PHASE 3 · the integration runbooks** | `O` `P` `Q′` | the event trigger · **cash application (10)** — payment provider · **bank reconciliation (14)** — accounting · **GIS reconciliation (20)** — GIS · **undeliverable contacts (22)** — emails | 017 · 022 · 026 · 032 · 034 |
| **PHASE 5 · the rest** | `R′` `S` `T` | returned payments (26) · autopay pre-notification (17) · **leak alert (11)** · **read validation (21)** · deposit review (15) · payment plans (25) · move-outs and final bills (27) · the eight remaining Checks · compose | 019–021 · 023–025 · 027–031 · 033 · 035 · 036 · 037 · 039 |

⚠ **ALL FOUR PHASE-3 RUNBOOKS ARE ACTIONS**, verified card by card in [`../11-catalogue/`](../11-catalogue/)
on 2026-09-06, and every one is triggered by a landed batch. **That is why the acting half (`EP-RBS-04`) had
to move to phase 2:** an Action cannot run before the ports, the cap, stop, the idempotency key and the
audit actor exist.

⚠ **TWO INTEGRATION-DRIVEN ACTIONS WERE IN PHASE 3 AND MOVED OUT — SAID OUT LOUD SO THE GAP READS AS A
DECISION.** **11 · leak and high-usage alert** and **21 · read validation on arrival** are both Actions and
both trigger off `batch.landed`, but they are fed by interval-meter data (`meters_mdm`,
`meters_neptune360`), which is **none of the four areas the Product Owner named**. They are in `R′`.

⚠ **AND RETURNED PAYMENTS (26) AND AUTOPAY PRE-NOTIFICATION (17) TOUCH THE PAYMENT PROVIDER AND ARE STILL
NOT IN PHASE 3**, because neither is triggered by a landed batch — 17 runs on a schedule and 26 is a
reserved definition. They are the **head of `R′`**, the first two things built after phase 3.

⚠ **WAVE `O` IS BLOCKED ON AN EVENT NOBODY OWNS.** `batch.landed(connection, batch_id, subject_type)` and
`feedback.landed(provider, batch_id)` **do not exist — zero occurrences under
`06-backend/apps/integrations/`, verified 2026-09-06.** Under `BR-INT-054` as amended that day, *"a batch
landed on this connection"* is a **lifecycle** fact about the connection, so it is **integrations' half to
build and it is CR-069's work — and no CR-069 wave commissions it today.** Without it phase 3 has no
trigger and the four runbooks can only be run by hand.

⚠ **`US-RBS-017`'s `depends_on` NAMES `US-RBS-007`, WHICH IS NOW LATER (phase 4).** What it needs is task
`I1` — the two job kinds on the platform runner — which moves forward to land with wave `L` in phase 2.


## Scope

**In:** the remaining **nineteen** runbooks of the twenty-one defined — eight Actions and eight Checks on the machinery phases 1 and 2 proved, plus the three reserved Collections/Payments/Accounts definitions — **the event trigger from a landed batch**, and **compose**: a runbook built from shipped steps with conformance on save and a trust ratchet.

**Out:** any new screen, any new block, any new category, and any new port that is not already on the thirteen. **If a runbook here needs one, that is a reviewed interface change and a rule change, not a phase-5 task.**

**Exit test of the phase — a demonstration, not an opinion.** A payments batch lands from the lockbox connection and **cash application starts within a minute**, with the batch **pinned as its scope** and named on the run header. Nobody pressed anything.

⚠ **THE POINT OF THIS PHASE IS THAT IT IS BORING, AND THAT IS THE PROOF THE CONTRACT HELD.** Each runbook is **one Python module — scope, steps, report — and no frontend code**. The conformance suite is its acceptance test. **If any runbook here needs a screen, the contract failed and the failure is in phases 1 and 2, not here.**

**Roughly 20 more hours a month**, on top of the collections ladder's ~33 — which is **phase 2's** after the 2026-09-06 re-cut.

## Capability matrix (list screens only — B9 conformance)

**No new list screen.** Every table in this phase is the `Records` block on `RBS-006`, whose search, filters, sort, columns, row actions and export are declared **per runbook in its report function** and drawn by the one renderer. `NFR-3` server-side paging is the renderer's, inherited by every one of them.

⚠ **THIS IS WHERE `NFR-3` STOPS BEING A PREFERENCE.** Read validation walks **80,000 meter-days** in one run (a 40,000-account tenant with two meters, one day) and GIS reconciliation walks a whole parcel file. **A single unpaginated result table here would be the fifth `NFR-3` breach in the repository** — and the four that exist (`GET /outstandings`, `GET /cheques`, the bank-rec batch list, and their two front-end mirrors) each name the abandoned 3,000-connection ceiling as their excuse (`DEF-PAY-4221`). This module inherits the paging and copies none of the excuse.

---

## Test-case ids — two families, and they are not the same one

⚠ **`TC-RBS-1` … `TC-RBS-25` are the SOURCE's**, carried unchanged from the specification's B7 and
cited by `02-business-rules.md`. **`TC-RBS-<story>.<n>` is NEW and belongs to this pack** — the
number names the STORY the case sits in, never a source case. So `TC-RBS-005.2` is the second new
case of `US-RBS-005` and has nothing to do with `TC-RBS-5`, the savepoint case. **The two patterns
cannot collide:** `TC-RBS-\d+(?!\d|\.)` finds the source's, `TC-RBS-\d{3}\.\d+` finds this
pack's. An earlier draft of these epics used a suffix form (`TC-RBS-5a`) that read as a sub-case of
`TC-RBS-5` and was not one — the same misreading `DEF-2804` cost two days on, one family down.

## Group A · The event trigger

---
id: US-RBS-017
epic: EP-RBS-05
module: runbooks
screens: [RBS-001, RBS-008]
phase: 3
status: ready
blocked_by: []
depends_on: [US-RBS-007, US-RBS-041]
journeys: []
rules: [BR-RBS-009, BR-RBS-016]
golden_tests: []
finance_calc: none
---
### US-RBS-017 — As a clerk a runbook runs when a batch lands

**1 · Details** — As **a cashier**, I want **the day's lockbox file to start applying itself the moment it lands** — so that **cash is on accounts before I open the product rather than after**. **Three trigger kinds, five events**: manual · schedule · `batch.landed(connection, batch_id, subject_type)` · `feedback.landed(provider, batch_id)` · `bill_run.completed(run_id)`. **Integrations emits the event; the engine subscribes runbooks to it by connection kind**, and **the batch is pinned as the run's scope** and named on the run header.

⚠ **THE BOUNDARY IS `BR-INT-058` AND IT IS OPERATIONAL, NOT ARCHITECTURAL.** Integrations authenticates, dedupes, persists raw and **replies fast — that is where it stops**. Our work may happen a second later. **Fold the two together and a slow runbook becomes a duplicate delivery from every vendor at once**, because the vendor is waiting on our reply and will re-send if we are slow.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-RBS-009` | Scope is resolved once and pinned — here, the landed batch itself | PROPOSED |
| `BR-RBS-016` | A schedule is evaluated in the tenant's timezone; a missed firing raises | PROPOSED |
| `BR-INT-057` | There are three triggers, not two: scheduled · one-off · **their call**. *They push* and *they pull* have no cadence, no due time, no next run and no catch-up policy | **CONFIRMED — PO 2026-09-06** |

**3 · Test Cases**

| TC | Scenario | Expected | Must first fail on |
|---|---|---|---|
| `TC-RBS-017.1` | A payments batch lands from the lockbox connection | Cash application starts **within a minute**, the batch named on the run header | A poller — it must be the event, not a sweep |
| `TC-RBS-017.2` | The same `batch_id` delivered twice | **One** run | The event subscribed without the batch id in the run key |
| `TC-RBS-017.3` · **screen** | An event-triggered runbook's Overview tab | **No *Next run* field** — an event has no cadence | A *Next run* field that can never hold a value (`BR-INT-057`) |

**4 · Test Data** — One lockbox payments batch, one interval batch, one delivery-feedback batch, one completed bill run; the payments batch delivered twice.

**5 · Data Fields / Mapping**

| Field | Screen | DB target | Type | Origin | Validation |
|---|---|---|---|---|---|
| `runbooks.trigger_kind` · `event_kind` | `RBS-004` Overview | `runbooks` | enum · enum | reference-data | `event_kind` NOT NULL when `trigger_kind = event`; `cron` NULL |
| `runbook_runs.trigger` · `event_ref` | `RBS-008` · `RBS-006` header | `runbook_runs` | enum · text | derived | `event_ref` carries the batch id and is what the scope is pinned to |

**6 · Acceptance** — Given a payments batch landing from the lockbox connection, when the event is emitted, then cash application starts within a minute with the batch pinned as its scope; a second delivery of the same batch id starts nothing.

**7 · Finance Calculation** — N/A; the money is `US-RBS-022`'s.

**8 · Open Questions** — **None of its own.** ⚠ **The three event kinds wait on the integration substrate's door** (`CR-069`), and `BR-INT-054` *commissions nothing* until CR-069 and Runbooks are taken together. **Manual and schedule wait on nothing** and are phases 1 and 4. ⚠ **AND THE TWO EVENTS ARE NOT MERELY UNBUILT, THEY ARE UNOWNED**: zero occurrences under `06-backend/apps/integrations/` on 2026-09-06, and no CR-069 wave commissions them. **Without them phase 3 has no trigger.**

---

## Group B · The eight remaining Actions

Each is **one module** declaring the contract. The rows below give what each declares; the eight sections follow the same shape and are kept short **because the machinery is phase 2's and is not re-proved here.**

| Story | Runbook | Category | Trigger | Subject · unit | Step modes | Blocks | **Ports** |
|---|---|---|---|---|---|---|---|
| `US-RBS-022` | 10 · Cash application | Payments | ⚡ payments landed | Payment · a day's batch | per record | KPIs · Breakdown · Records · **Row decisions** · Downloads | `apply_payment` · `queue_receipt` |
| `US-RBS-023` | 11 · Leak and high-usage alert | Reads | ⚡ intervals landed | Meter-day | set (own normal) · per record | KPIs · Records · Sentence · Downloads | `queue_notice` · `flag_meter` |
| `US-RBS-026` | 14 · Bank reconciliation | Finance | ⚡ statement landed | Bank line | set (match) · per record | KPIs · Records · Downloads | `record_match` |
| `US-RBS-029` | 17 · Autopay pre-notification | Payments | schedule | Account · autopay | per record | KPIs · Records · Downloads | `queue_notice` · `flag_account` · `schedule_retry` |
| `US-RBS-032` | 20 · GIS reconciliation | Data Sync | ⚡ parcels landed | Parcel ↔ premise | per record | KPIs · Breakdown · Records · **Row decisions** · Downloads | `apply_premise_change` |
| `US-RBS-033` | 21 · Read validation on arrival | Data Sync | ⚡ intervals landed | **Meter-day**, never the interval | set (roll-up) · per record | KPIs · Records · Downloads | `write_read` |
| `US-RBS-034` | 22 · Undeliverable contacts | Data Sync | ⚡ feedback landed | Contact feedback | per record | KPIs · Breakdown · Records · Downloads | `suppress_channel` · `flag_account` |
| `US-RBS-027` | 15 · Deposit review | Collections | schedule | Deposit | per record | KPIs · Records · **Action** · Downloads | `post_credit` · `raise_refund` · `queue_notice` |
| `US-RBS-035` | 25 · Payment plans | Collections | schedule | Payment plan | per record | KPIs · Records · Downloads | `queue_notice` |
| `US-RBS-036` | 26 · Returned payments | Payments | ⚡ / schedule | Returned item | per record | KPIs · Breakdown · Records · Downloads | `apply_fee` · `queue_notice` · `flag_account` |
| `US-RBS-037` | 27 · Move-outs and final bills | Accounts | schedule | Closing account | per record | KPIs · Records · Downloads | `queue_notice` · `post_credit` · `raise_refund` |

---
id: US-RBS-022
epic: EP-RBS-05
module: runbooks
screens: [RBS-006]
phase: 3
status: ready
blocked_by: []
depends_on: [US-RBS-017, US-RBS-013]
journeys: []
rules: [BR-RBS-033, BR-RBS-013]
golden_tests: []
finance_calc: applies landed payments by the allocation order — payments' own service, not this module's
---
### US-RBS-022 — As a cashier the day's landed payments apply themselves and I decide only the unmatched

**1 · Details** — At **06:30** the clerk sees **"129 applied · 6 need you · 3 duplicates held"**, a by-source table, and each unmatched payment with **its likeliest account** and **Pick account →**. The row decision is performed **through payments' own port**, never by this module.

⚠ **A DUPLICATE PAYMENT IS HELD, NEVER REJECTED** (`BR-RBS-033`). A held duplicate is a decision waiting for a person; a rejected one is money the utility has and cannot see.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-RBS-033` | A duplicate payment is held, never rejected | PROPOSED |
| `BR-RBS-013` | No action may edit a payment; corrections go through the owning module | **CONFIRMED — hard rule 4** |

**3 · Test Cases**

| TC | Scenario | Expected | Must first fail on |
|---|---|---|---|
| `TC-RBS-022.1` | A day's lockbox batch | **129 applied · 6 need you · 3 duplicates held** | A duplicate rejected rather than held |
| `TC-RBS-022.2` | **Pick account →** on an unmatched payment | One row decision, through payments' port; the row reads **Applied** | This module writing the payment |
| `TC-RBS-022.3` · **negative** | A row decision on a record the run did not queue for a person | Refused — `runbooks.refusal.nothing_to_decide` (422) | Any record accepting a decision |

**4 · Test Data** — One day's batch of 138 payments: 129 matching cleanly, 6 unmatched, 3 duplicates of the same day's items.

**5 · Data Fields / Mapping** — `runbook_run_records.decision` · `decided_by` · `decided_at` (the row decision and who made it) · `amount NUMERIC(18,4)`. **Ports:** `apply_payment`, `queue_receipt`.

**6 · Acceptance** — Given a landed batch, when the run finishes, then the result reads 129 applied, 6 needing a person and 3 duplicates held; pressing **Pick account →** applies one payment through payments' service and the row reads Applied.

**7 · Finance Calculation** — **Allocation is payments' own**, by its existing allocation order. This module decides *which account*, never *how the money splits*.

**8 · Open Questions** — None.

---
id: US-RBS-023
epic: EP-RBS-05
module: runbooks
screens: [RBS-006]
phase: 5
status: ready
blocked_by: []
depends_on: [US-RBS-017, US-RBS-013]
journeys: []
rules: [BR-RBS-034, BR-RBS-028]
golden_tests: []
finance_calc: none — a leak alert never carries a dollar figure
---
### US-RBS-023 — As a clerk a customer is told about a running leak before the bill says so

**1 · Details** — The clerk sees **"9 alerts queued"** and **reads the exact text a customer receives**, naming the address and the hours; the row with no channel says so. A set step computes **each meter's own normal** before the per-record pass.

⚠ **A CUSTOMER-FACING ALERT NAMES THE UTILITY, THE ADDRESS AND THE HOURS — NEVER THE ACCOUNT OR A DOLLAR FIGURE** (`BR-RBS-034`). A dollar figure in an alert is a bill the utility has not issued, and an account number in an unsolicited message is a disclosure.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-RBS-034` | A customer-facing alert names the utility, the address and the hours, never the account or a dollar figure | PROPOSED |
| `BR-RBS-028` | Every threshold is relative to **the meter's own history**, never to a fleet average | PROPOSED |

**3 · Test Cases**

| TC | Scenario | Expected | Must first fail on |
|---|---|---|---|
| `TC-RBS-023.1` | Nine meters running continuously | **9 alerts queued**, the exact text shown to the clerk | Text composed at send time, so the clerk saw something else |
| `TC-RBS-023.2` · **copy gate** | Every alert body | **No account number and no dollar figure anywhere** | A template carrying a balance |
| `TC-RBS-023.3` | A meter whose customer has no channel | The row **says so**; nothing is silently dropped | A silent skip |

**4 · Test Data** — Interval data for a set of meters, nine of them running continuously against **their own** twelve-month normal; one customer with no channel.

**5 · Data Fields / Mapping** — Address comes from **`premises`**, by walking (hard rule 8): a meter has no address column of its own, and neither does this alert. **Ports:** `queue_notice`, `flag_meter`.

**6 · Acceptance** — Given nine continuously-running meters, when the run finishes, then 9 alerts are queued, the clerk can read the exact customer text, and no alert names an account or an amount.

**7 · Finance Calculation** — **None, deliberately.** `BR-RBS-034` forbids a figure.

**8 · Open Questions** — ⚠ **`OQ-RBS-1733`** (may a tenant ever set a runbook to run unattended once trusted) — **runbook 11 is the first candidate**. **Built meanwhile: every run is approved, and the *"Unattended after"* parameter is drawn read-only.** Blocks nothing.

---
id: US-RBS-026
epic: EP-RBS-05
module: runbooks
screens: [RBS-006]
phase: 3
status: ready
blocked_by: []
depends_on: [US-RBS-017, US-RBS-013]
journeys: []
rules: [BR-RBS-013, BR-RBS-023]
golden_tests: []
finance_calc: matching only — the ledger posts, this module does not
---
### US-RBS-026 — As a finance user yesterday's statement lines match our batches without a spreadsheet

**1 · Details** — Tom sees **"15 matched · 3 need you · $1,910.00 unmatched"**, each unmatched line beside **its nearest batch and the difference**, and the bank fee as a tile. A **set step** does the matching over the whole landed statement; the per-record step records each line's outcome.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-RBS-023` | A set-mode step runs once over the pinned set | PROPOSED |
| `BR-RBS-013` | No action may edit a journal entry; **only the ledger posting service writes journal lines** (hard rule 5) | **CONFIRMED** |

**3 · Test Cases**

| TC | Scenario | Expected | Must first fail on |
|---|---|---|---|
| `TC-RBS-026.1` | A landed statement of 18 lines | **15 matched · 3 need you · $1,910.00 unmatched**, each unmatched beside its nearest batch and the difference | A match with no difference shown — a clerk cannot judge it |
| `TC-RBS-17` | The match step over the whole statement | Executes **once**, not per line | The set step registered as per-record |
| `TC-RBS-026.2` | The bank fee | Drawn as its own tile, **not netted into a match** | A fee absorbed into a difference |

**4 · Test Data** — One landed statement: 18 lines, 15 matching deposit batches, 3 unmatched totalling **$1,910.0000**, one bank fee.

**5 · Data Fields / Mapping** — `runbook_run_records.amount NUMERIC(18,4)`, displayed to 2. **Port:** `record_match` (payments).

**6 · Acceptance** — Given yesterday's statement, when the run finishes, then 15 lines are matched, 3 need a person with their nearest batch and difference, and the bank fee is its own tile.

**7 · Finance Calculation** — **Comparison only, at four decimals.** No journal line is written by this module.

**8 · Open Questions** — None.

---
id: US-RBS-029
epic: EP-RBS-05
module: runbooks
screens: [RBS-006]
phase: 5
status: ready
blocked_by: []
depends_on: [US-RBS-013]
journeys: []
rules: [BR-RBS-031, BR-RBS-016]
golden_tests: []
finance_calc: the amount told to the customer is the bill's own, unchanged
---
### US-RBS-029 — As a clerk autopay customers are told the amount before the debit and failed debits are handled

**1 · Details** — At **08:00** the clerk sees **"851 queued · 2 debits need you"**, and each failed debit **reads the bank's reason in words** with **Retry 7 Sep** or **To the ladder**.

⚠ **A DEBIT THAT FAILS TWICE IS NOT RETRIED A THIRD TIME; THE ACCOUNT GOES TO THE LADDER** (`BR-RBS-031`). Endless retries are how a bank relationship is damaged and how a customer is charged three return fees for one problem.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-RBS-031` | A debit that fails twice is not retried a third time; the account goes to the ladder | PROPOSED |
| `BR-RBS-016` | The schedule is the tenant's own clock | PROPOSED |

**3 · Test Cases**

| TC | Scenario | Expected | Must first fail on |
|---|---|---|---|
| `TC-RBS-029.1` | 853 autopay accounts, 2 failed debits | **851 queued · 2 need you**, each failure in the bank's words | A raw response code on screen (B14 rule 32) |
| `TC-RBS-029.2` | A debit failing a second time | **No third retry**; the account moves to the ladder | An unbounded retry loop |
| `TC-RBS-029.3` | The amount in the pre-notification | **The bill's own amount**, to the cent | An amount recomputed here |

**4 · Test Data** — 853 autopay accounts; two failed debits with different bank reasons; one already at its second failure.

**5 · Data Fields / Mapping** — **Ports:** `queue_notice`, `flag_account`, `schedule_retry`.

**6 · Acceptance** — Given 853 autopay accounts, when the run finishes, then 851 pre-notifications are queued and each of the 2 failures reads its bank reason in words with a next step; a second failure sends the account to the ladder rather than retrying.

**7 · Finance Calculation** — **None of its own.** The amount is the bill's, quoted.

**8 · Open Questions** — None.

---
id: US-RBS-032
epic: EP-RBS-05
module: runbooks
screens: [RBS-006]
phase: 3
status: ready
blocked_by: []
depends_on: [US-RBS-017, US-RBS-013]
journeys: []
rules: [BR-RBS-035, BR-RBS-013]
golden_tests: []
finance_calc: none
---
### US-RBS-032 — As a clerk a landed parcel batch is reconciled by the utility's own dispositions

**1 · Details** — After a parcel batch lands the clerk sees **"980 applied · 218 need you · 12 never touched"**, the by-class table, and **Ours · Theirs** on every queued row with **Accept theirs → · Keep ours**. This is the `Row decisions` block's only shipped use besides cash application.

⚠ **AN ADDRESS IS STORED ON `premises` AND NOWHERE ELSE** (hard rule 8). `apply_premise_change` writes **one field on one premise, before-and-after kept**, through metering's own service. **`premises.lat/lng` travels the same way**, so a map and an envelope cannot disagree.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-RBS-035` | A volume runbook keeps a record row for anything acted on or flagged and a count per outcome for the rest | PROPOSED |
| `BR-RBS-013` | Corrections go through the owning module | **CONFIRMED** |

**3 · Test Cases**

| TC | Scenario | Expected | Must first fail on |
|---|---|---|---|
| `TC-RBS-032.1` | A landed parcel batch | **980 applied · 218 need you · 12 never touched**, by class, with Ours · Theirs per queued row | A row with no *theirs* value — a clerk cannot decide |
| `TC-RBS-032.2` | **Accept theirs →** | One field on one premise changes through metering's service, **before and after kept** | This module writing `premises` |
| `TC-RBS-032.3` · **hard rule 8** | Any address written by this runbook | Written to **`premises` only**; nothing else grows an address column | A parcel address copied onto an account |

**4 · Test Data** — One parcel batch of 1,210 rows: 980 agreeing, 218 disagreeing on one field, 12 with no premise to match.

**5 · Data Fields / Mapping** — `runbook_run_records.data` carries *ours* and *theirs*. **Port:** `apply_premise_change`.

**6 · Acceptance** — Given a landed parcel batch, when the run finishes, then the three counts render with the by-class table and every queued row offers Accept theirs / Keep ours; accepting writes one premise field through metering with the before-and-after kept.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None of its own. ⚠ The **nightly GIS reconciliation on the integrations side** carries three open questions of its own (`OQ-INT-1470`–`1472`, closed 2026-09-04) and its wave **moves whole to Runbooks** under `BR-INT-054`; nothing here is rebuilt.

---
id: US-RBS-033
epic: EP-RBS-05
module: runbooks
screens: [RBS-006]
phase: 5
status: ready
blocked_by: []
depends_on: [US-RBS-017, US-RBS-013]
journeys: []
rules: [BR-RBS-019, BR-RBS-035, BR-RBS-023]
golden_tests: []
finance_calc: none
---
### US-RBS-033 — As a clerk a landed interval batch is validated and handed to billing overnight

**1 · Details** — After an interval batch lands the clerk sees **"1,802 validated · 31 estimated · 7 queued · 1,833 handed to billing"**, each queued meter with **its last good day**. A set step rolls the intervals up; the per-record step validates each meter-day.

⚠ **THE UNIT OF WORK IS THE METER-DAY, NEVER THE RAW INTERVAL, AND THAT IS A RULE RATHER THAN A PREFERENCE** (`BR-RBS-019`). **176,640 intervals become 1,840 records**, and a per-record savepoint stays cheap. Register the interval as the subject and the run is six figures of savepoints.

⚠ **A VOLUME RUNBOOK KEEPS A ROW FOR WHAT IT ACTED ON AND A COUNT FOR THE REST** (`BR-RBS-035`). Read validation over **80,000 meter-days** — a 40,000-account tenant with two meters, one day — writes **38 run records and a count of 80,000**.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-RBS-019` | A runbook declares its unit of work, and it is never the raw row; volume data is rolled up before any per-record step | PROPOSED |
| `BR-RBS-035` | A record row for anything acted on or flagged; a count per outcome for the rest | PROPOSED |
| `BR-RBS-023` | A step declares its mode | PROPOSED |

**3 · Test Cases**

| TC | Scenario | Expected | Must first fail on |
|---|---|---|---|
| `TC-RBS-18` | An interval batch of **176,640** rows | **1,840** run records | The interval registered as the subject |
| `TC-RBS-23` | Read validation over **80,000** meter-days | **38 run records and a count of 80,000** | A row per clean meter-day |
| `TC-RBS-033.1` | A queued meter | Names **its last good day** | A queue reason with no date — a clerk cannot act on it |

**4 · Test Data** — One interval batch of 176,640 rows over 1,840 meter-days; a validation set of 80,000 meter-days with 31 estimated and 7 queued.

**5 · Data Fields / Mapping** — `runbooks.unit_of_work = meter-day`; `runbook_runs.counts` jsonb carries the per-outcome counts. **Port:** `write_read` (a validated meter-day as a read, **source stamped**).

**6 · Acceptance** — Given an interval batch, when it lands, then 1,802 are validated, 31 estimated, 7 queued each with its last good day, 1,833 are handed to billing, and the run's record count reads 1,840 rather than 176,640.

**7 · Finance Calculation** — N/A. ⚠ **Consumption always carries an explicit unit** (hard rule 3): a validated read written through `write_read` carries the meter's unit and the source stamp, never a bare number.

**8 · Open Questions** — None. ⚠ **Partitioned interval storage in metering is one of the four `not scoped` 80,000-account commitments** (decision log 2026-09-06) and is **owned by metering, not by this module**.

---
id: US-RBS-034
epic: EP-RBS-05
module: runbooks
screens: [RBS-006]
phase: 3
status: ready
blocked_by: []
depends_on: [US-RBS-017, US-RBS-013]
journeys: []
rules: [BR-RBS-011, BR-RBS-013]
golden_tests: []
finance_calc: none
---
### US-RBS-034 — As a clerk a bounced address is suppressed and the next channel used the same day

**1 · Details** — At **07:00** the clerk sees **"31 suppressed · 27 fell back · 4 nothing left"**, with **where each suppressed channel fell back to** and **Owed** on every nothing-left row. A dead channel is suppressed and dated; the fallback is the tenant's own order, ending in paper.

⚠ **THE "NOTHING LEFT" ROWS ARE THE POINT OF THE SCREEN.** Four customers the utility can no longer reach is a fact somebody must act on, and showing **Owed** beside each is what makes it actionable rather than informational.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-RBS-011` | A failure names its fix route | PROPOSED |
| `BR-RBS-013` | Corrections go through the owning module | **CONFIRMED** |

**3 · Test Cases**

| TC | Scenario | Expected | Must first fail on |
|---|---|---|---|
| `TC-RBS-034.1` | A landed feedback batch | **31 suppressed · 27 fell back · 4 nothing left**, each fallback naming its destination | A count with no destinations — the clerk cannot verify it |
| `TC-RBS-034.2` | A nothing-left row | Shows **Owed** and a fix route | A row with neither |
| `TC-RBS-034.3` | A suppressed channel | Marked undeliverable **and dated**, through customers' service | This module writing `customers` |

**4 · Test Data** — A feedback batch producing 31 bounces across email, text and post; 27 with a next channel; 4 with none, each carrying a balance.

**5 · Data Fields / Mapping** — **Ports:** `suppress_channel`, `flag_account`.

**6 · Acceptance** — Given a landed feedback batch, when the run finishes, then 31 channels are suppressed and dated, 27 fell back with their destination named, and each of the 4 with nothing left shows Owed.

**7 · Finance Calculation** — N/A; the Owed figure is quoted from the account, two decimals over four stored.

**8 · Open Questions** — None. ⚠ **The integrations half of this — the feedback DOOR — is built and finished there** (`BR-INT-054`(6), `OQ-INT-1729` ruled option (a) on 2026-09-06); **marking notification rows `delivered`/`bounced` and feeding the suppression list are ours and are THIS story.**

---
id: US-RBS-027
epic: EP-RBS-05
module: runbooks
screens: [RBS-006, RBS-004]
phase: 5
status: ready
blocked_by: []
depends_on: [US-RBS-011, US-RBS-013]
journeys: []
rules: [BR-RBS-018, BR-RBS-013]
golden_tests: []
finance_calc: deposit interest, and a refund threshold — every refund behind a second approval
---
### US-RBS-027 — As a finance user deposits owed back are found with interest, and refunds wait for a second approval

**1 · Details** — On the **1st** the clerk sees **"48 credited · 13 refunds await approval · $296.40 interest"**, and each refund row says **Account closed** or **Over the $250.00 limit**.

⚠ **EVERY REFUND HERE CARRIES THE SECOND APPROVAL** (`BR-RBS-018`). On the Limits tab, **Fees** reads *Second approval*, and a refund appears as **Waiting** under *"Refunds awaiting second approval"*, leaving only when a **second admin** approves it.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-RBS-018` | A money-bearing action carries a second approval, separate from the batch approval | PROPOSED — **the threshold is `OQ-RBS-1732`** |
| `BR-RBS-013` | Corrections go through the owning module | **CONFIRMED** |

**3 · Test Cases**

| TC | Scenario | Expected | Must first fail on |
|---|---|---|---|
| `TC-RBS-027.1` | A month's deposits | **48 credited · 13 awaiting approval · $296.4000 interest**, displayed as $296.40 | Interest at two decimals internally |
| `TC-RBS-027.2` | A refund with one approval | Stays **Waiting**; nothing leaves | One approval releasing a refund |
| `TC-RBS-027.3` | Each refund row | Names **why** — Account closed, or Over the limit | A refund with no stated reason |

**4 · Test Data** — A month of deposits: 48 due a credit, 13 due a refund (some closed accounts, some over a $250.00 limit), total interest **$296.4000**.

**5 · Data Fields / Mapping** — Interest at **four** decimals stored, two displayed; percentages at six. **Ports:** `post_credit`, `raise_refund`, `queue_notice`.

**6 · Acceptance** — Given the month's deposits, when the run finishes, then 48 are credited, 13 refunds wait with their reason, and no refund leaves on a single approval.

**7 · Finance Calculation** — **Deposit interest is the tenant's own rate from Settings**, applied by payments' service. Money **four** decimals, percentages **six**, both displayed **two** (hard rule 2).

**8 · Open Questions** — **`OQ-RBS-1732`** — until it is ruled, **every** money-bearing action here carries the second approval, which is the conservative reading and not a chosen value.

---
id: US-RBS-035
epic: EP-RBS-05
module: runbooks
screens: [RBS-006]
phase: 5
status: ready
blocked_by: []
depends_on: [US-RBS-013]
journeys: []
rules: [BR-RBS-010, BR-RBS-013]
golden_tests: []
finance_calc: instalment amounts are the plan's own
---
### US-RBS-035 — As a clerk missed instalments are warned and plans voided by rule

**1 · Details** — A clerk sees plans in flight, the instalments missed this cycle, and **which plans were voided after the configured number of misses, each with its rule**. Voiding is a payments act through the owning module.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-RBS-010` | Every record states the rule that decided it, in words | PROPOSED |
| `BR-RBS-013` | Corrections go through the owning module | **CONFIRMED** |

**3 · Test Cases**

| TC | Scenario | Expected | Must first fail on |
|---|---|---|---|
| `TC-RBS-035.1` | Plans with 1 and with N misses | Warned and voided respectively, **each naming its rule in words** | A void with no stated rule |
| `TC-RBS-035.2` | A plan in good standing | Untouched, and **not counted as skipped** | A plan swept in by a scope that ignores standing |
| `TC-RBS-035.3` | A voided plan | The void is payments' act; this module writes nothing of theirs | A plan status written here |

**4 · Test Data** — Plans in flight: some current, some with one miss, some at the configured limit. **43 accounts on a plan in good standing** are the same rows the ladder skips — the two runbooks must agree, and the fixture is shared so a disagreement is a test failure rather than a support call.

**5 · Data Fields / Mapping** — **Port:** `queue_notice`. Plan status is payments'.

**6 · Acceptance** — Given plans in flight, when the run finishes, then each missed instalment is warned and each plan past the configured misses is voided, every row naming its rule in words.

**7 · Finance Calculation** — **None of its own**; instalment amounts are the plan's.

**8 · Open Questions** — None.

---
id: US-RBS-036
epic: EP-RBS-05
module: runbooks
screens: [RBS-006]
phase: 5
status: ready
blocked_by: []
depends_on: [US-RBS-011, US-RBS-013]
journeys: []
rules: [BR-RBS-018, BR-RBS-013]
golden_tests: []
finance_calc: the return fee is the tenant's own rule, behind the second approval
---
### US-RBS-036 — As a cashier returned payments are reversed, the fee applied and the customer told

**1 · Details** — A clerk sees returned items **reversed**, the fee applied by rule **behind the second approval**, the customer notified, and **the privilege removed after N returns**, each act with its rule.

⚠ **A REVERSAL IS A NEW ROW, NEVER AN EDIT** (hard rule 4, `BR-RBS-013`). The original payment is untouched; payments' own service writes the reversal.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-RBS-013` | No UPDATE or DELETE on payments; corrections are new rows through the owning module | **CONFIRMED — hard rule 4** |
| `BR-RBS-018` | The fee carries a second approval | PROPOSED |

**3 · Test Cases**

| TC | Scenario | Expected | Must first fail on |
|---|---|---|---|
| `TC-RBS-036.1` | A returned item | Reversed as a **new row**; the original payment is byte-identical | An update of the payment |
| `TC-RBS-036.2` | The return fee | Applied only after the **second approval** | A fee applied on the batch approval alone |
| `TC-RBS-036.3` | The Nth return on one account | The privilege is removed, **naming the rule** | A silent removal |

**4 · Test Data** — Returned items across three reasons; one account reaching its Nth return.

**5 · Data Fields / Mapping** — **Ports:** `apply_fee`, `queue_notice`, `flag_account`.

**6 · Acceptance** — Given returned items, when the run finishes, then each is reversed as a new row, the fee waits on a second approval, the customer is notified, and the Nth return removes the privilege with its rule named.

**7 · Finance Calculation** — **The fee is the tenant's own rule, applied by billing's service**, four decimals. This module computes no fee.

**8 · Open Questions** — `OQ-RBS-1732` applies; every fee carries the second approval until it is ruled.

---
id: US-RBS-037
epic: EP-RBS-05
module: runbooks
screens: [RBS-006]
phase: 5
status: ready
blocked_by: []
depends_on: [US-RBS-013]
journeys: []
rules: [BR-RBS-011, BR-RBS-013, BR-RBS-018]
golden_tests: []
finance_calc: the final bill is billing's; the deposit settlement is payments'
---
### US-RBS-037 — As a clerk every closing account gets its final bill and its deposit settled

**1 · Details** — A clerk sees every closing account with **its closing read due, its final bill issued or waiting, its deposit refunded or carried, and the forwarding address captured** — four facts per row, each with the screen that settles it.

⚠ **THE FORWARDING ADDRESS IS `customers.addresses` `kind='mailing'`** — where the BILL goes — and is one of exactly **three** exceptions to hard rule 8's *an address lives on `premises` and nowhere else*. ⚠ **`kind='service'` IS RETIRED and a write asking for it is refused BY NAME**; a lane reaching for it here has found the fourth home `G85` exists to fail.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-RBS-011` | Every failure names its fix route | PROPOSED |
| `BR-RBS-013` | Corrections go through the owning module | **CONFIRMED** |
| `BR-RBS-018` | A deposit refund carries the second approval | PROPOSED |

**3 · Test Cases**

| TC | Scenario | Expected | Must first fail on |
|---|---|---|---|
| `TC-RBS-037.1` | A closing account with no closing read | Row says so, with **Add a read →** | A row that says only *waiting* |
| `TC-RBS-037.2` | A deposit larger than the final bill | Refunded, **behind the second approval** | A refund on one approval |
| `TC-RBS-037.3` · **hard rule 8** | The forwarding address | Written as `customers.addresses` `kind='mailing'`; **`kind='service'` is refused by name** | A write asking for the retired kind |

**4 · Test Data** — Closing accounts spanning: no closing read · read taken, bill waiting · bill issued, deposit carried · bill issued, deposit refunded · no forwarding address.

**5 · Data Fields / Mapping** — **Ports:** `queue_notice`, `post_credit`, `raise_refund`.

**6 · Acceptance** — Given closing accounts, when the run finishes, then each row shows its closing read, its final bill, its deposit and its forwarding address, and every gap names the screen that fills it.

**7 · Finance Calculation** — **The final bill is billing's** and the deposit settlement is payments'. This module decides *which accounts* and *what is missing*.

**8 · Open Questions** — `OQ-RBS-1732` applies to the refund.

---

## Group C · The eight remaining Checks

Every one is a Check: **constructed with no writer, no port, nothing to approve.** They ship faster than the Actions for that reason, and the phase may take them in any order.

| Story | Runbook | Category | Trigger | Blocks | What a clerk reads |
|---|---|---|---|---|---|
| `US-RBS-019` | 4 · Why is this bill higher? | Billing | manual | KPIs · Ranked · Reconciled · Sentence · Facts | *"Up $82.20 · usage +38% over 4 more days · tier 2 reached · late fee $12.00 · rate unchanged"* |
| `US-RBS-020` | 5 · Abnormal readings | Reads | schedule · manual | KPIs · Records (sparkline) · Action · Downloads | 75 meters in six pattern tiles, *"$1,180.00 at risk · Order a test →"* |
| `US-RBS-021` | 6 · Why did this not bill? | Billing | manual | Sentence · Chain · Facts · Records | *"Stopped at step 4 · No Sewer read between 18 Aug and 17 Sep"* |
| `US-RBS-024` | 12 · Disconnect eligibility | Collections | manual | Verdict · KPIs · Records · Action · Downloads | *"14 eligible · 9 removed since the letter"* |
| `US-RBS-025` | 13 · Payment trace | Payments | manual | Verdict · Chain · Facts · Action | *"Found · applied to Alvarez, M. · account ending 4471 · same last four"* |
| `US-RBS-028` | 16 · Rate change preview | Plans & Rates | manual | KPIs · Ranked · Records · Breakdown · Downloads | *"1,146 bills go up · 121 by more than 15% · revenue +$5,310 (+4.7%)"* |
| `US-RBS-030` | 18 · Vacant premises with usage | Premises | schedule | KPIs · Records · Action · Downloads | *"18 premises · about $1,940 a month unbilled · 7 stopped meters"* |
| `US-RBS-031` | 19 · Data hygiene | Data Hygiene | schedule | KPIs · Breakdown · Action · Downloads | *"212 items · 900 accounts unreachable by text"* |

---
id: US-RBS-019
epic: EP-RBS-05
module: runbooks
screens: [RBS-006]
phase: 5
status: ready
blocked_by: []
depends_on: [US-RBS-004]
journeys: []
rules: [BR-RBS-002, BR-RBS-010]
golden_tests: []
finance_calc: differences between two issued bills; nothing recomputed
---
### US-RBS-019 — As a clerk I explain a higher bill in one screen

**1 · Details** — A clerk picks an account and two bills and **reads aloud**: *"Up $82.20 · usage +38% over 4 more days · tier 2 reached · late fee $12.00 · rate unchanged"*, with the two bills side by side. **The `Sentence` block is written for the phone**: a clerk can say it to the customer as it stands.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-RBS-002` | A Check has no writer | PROPOSED |
| `BR-RBS-010` | Every record states its reason in words a clerk can read | PROPOSED |

**3 · Test Cases**

| TC | Scenario | Expected | Must first fail on |
|---|---|---|---|
| `TC-RBS-019.1` | Two issued bills, one higher | The sentence, with **every cause and its size**, and *rate unchanged* stated when it is | A sentence listing only what changed — a clerk cannot say *the rate did not move* |
| `TC-RBS-019.2` | The two bills side by side | Line by line, **difference per line** | An inner join hiding lines present in one only |
| `TC-RBS-019.3` | Any run | **Nothing is written to the account** | A note written automatically — see `OQ-RBS-1734` |

**4 · Test Data** — One account with two issued bills differing by **$82.20**: usage +38%, four more days, tier 2 reached, a **$12.00** late fee, the rate unchanged.

**5 · Data Fields / Mapping** — Amounts from **issued** bills, read only; four decimals stored, two displayed.

**6 · Acceptance** — Given two issued bills, when the runbook runs, then the sentence names every cause with its size, the bills sit side by side line by line, and nothing is written.

**7 · Finance Calculation** — **Differences between two issued bills. Nothing is recomputed** — a re-pricing here could disagree with the bill the customer holds.

**8 · Open Questions** — **`OQ-RBS-1734`** (may a Check ever write a note to an account automatically). ⚠ **Built meanwhile: it does not.** The clerk adds the explanation with **one button**, performed by the customers module. **If the answer is yes it is a fourteenth port and a narrowing of `BR-RBS-002`** — which is why it is a question and not a lane's choice.

---
id: US-RBS-020
epic: EP-RBS-05
module: runbooks
screens: [RBS-006]
phase: 5
status: ready
blocked_by: []
depends_on: [US-RBS-007]
journeys: []
rules: [BR-RBS-028, BR-RBS-002]
golden_tests: []
finance_calc: revenue at risk, from the meter's own history
---
### US-RBS-020 — As a clerk I see which meters behave oddly, ranked by revenue at risk

**1 · Details** — 75 meters in **six pattern tiles**, each row with **its own twelve-month line** and *"$1,180.00 at risk · Order a test →"*, **sorted by revenue at risk**. The sparkline is the `Records` block's sparkline cell — the only runbook that uses it.

⚠ **EVERY THRESHOLD IS RELATIVE TO THE METER'S OWN HISTORY, NEVER TO A FLEET AVERAGE** (`BR-RBS-028`). An irrigation meter and a duplex are not comparable, and a fleet average makes both wrong.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-RBS-028` | Every threshold is relative to the meter's own history, never to a fleet average | PROPOSED |
| `BR-RBS-002` | A Check has no writer | PROPOSED |

**3 · Test Cases**

| TC | Scenario | Expected | Must first fail on |
|---|---|---|---|
| `TC-RBS-020.1` | An irrigation meter with a seasonal profile | **Not flagged** on its own history | A fleet-average threshold |
| `TC-RBS-020.2` | The result | 75 meters in six tiles, **sorted by revenue at risk** | Sorted by deviation — the clerk's time then goes to the cheapest problems |
| `TC-RBS-020.3` | **Raise work items ✓** | Raised through the **engine**, on demand, not by a port | `raise_work_item` as a port |

**4 · Test Data** — Twelve months for a mixed meter estate, 75 abnormal against their own history across six patterns, one seasonal irrigation meter that must not be flagged.

**5 · Data Fields / Mapping** — `runbook_run_records.data` carries the twelve sparkline values. **Ports: none.**

**6 · Acceptance** — Given twelve months of reads, when the runbook runs, then 75 meters render in six pattern tiles sorted by revenue at risk, each with its own line, and the seasonal irrigation meter is absent.

**7 · Finance Calculation** — **Revenue at risk** is computed from the meter's own history and the account's own plan, four decimals, displayed two. It is an estimate and the screen says so.

**8 · Open Questions** — None.

---
id: US-RBS-021
epic: EP-RBS-05
module: runbooks
screens: [RBS-006]
phase: 5
status: ready
blocked_by: []
depends_on: [US-RBS-004]
journeys: []
rules: [BR-RBS-011, BR-RBS-002]
golden_tests: []
finance_calc: none
---
### US-RBS-021 — As a clerk I learn why one account did not bill and fix it from the same screen

**1 · Details** — A clerk opens the account and reads **"Stopped at step 4 · No Sewer read between 18 Aug and 17 Sep"** with **Add a read →** in the page head; the variant lists **all 14 accounts** the run left unbilled, **by the step that stopped them**. Triggered manually, and by `bill_run.completed(run_id)` for the whole break list.

⚠ **THE CHAIN SAYS *NOT NEEDED* AND *NEVER REACHED* HONESTLY.** A step that did not run carries the reason it did not — the same honesty the seeding flow already uses, and the reason a clerk can read a stopped chain without guessing.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-RBS-011` | A failure names its fix route; a failure with no route is a defect in the runbook | PROPOSED |
| `BR-RBS-002` | A Check has no writer | PROPOSED |

**3 · Test Cases**

| TC | Scenario | Expected | Must first fail on |
|---|---|---|---|
| `TC-RBS-021.1` | One unbilled account | **"Stopped at step 4 · No Sewer read between 18 Aug and 17 Sep"** with **Add a read →** in the page head | A message with no date range — the clerk cannot know which read to add |
| `TC-RBS-021.2` | The break-list variant | **All 14** accounts, grouped by the step that stopped them | A flat list |
| `TC-RBS-021.3` | Later steps after a stop | **Never reached**, not *passed* and not blank | A blank cell, which reads as *fine* |

**4 · Test Data** — A completed bill run leaving **14** accounts unbilled across four different stopping steps; one of them missing a Sewer read between 18 Aug and 17 Sep.

**5 · Data Fields / Mapping** — `fix_route` per record; `runbook_runs.event_ref` carries the bill run id for the variant.

**6 · Acceptance** — Given a bill run that left 14 accounts unbilled, when the runbook runs, then each is grouped by the step that stopped it and each names its fix route; the single-account view carries the fix in the page head.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---
id: US-RBS-024
epic: EP-RBS-05
module: runbooks
screens: [RBS-006]
phase: 5
status: ready
blocked_by: []
depends_on: [US-RBS-013]
journeys: []
rules: [BR-RBS-032, BR-RBS-002, BR-RBS-012]
golden_tests: []
finance_calc: none
---
### US-RBS-024 — As a supervisor I sign a disconnect list that was re-checked this morning

**1 · Details** — **The morning of**, a person sees **"14 eligible · 9 removed since the letter"** with **why each was removed**, and signs a field list. ⚠ **NOTHING IS DISCONNECTED BY THE PRODUCT.** This is a Check with an `Action` block whose button **approves a list a crew acts on** — the approval is engine-owned and the disconnection is a person's.

⚠ **A RETURNED LETTER IS NOT A SERVED NOTICE; THE LIST RE-CHECKS DELIVERY ON THE MORNING** (`BR-RBS-032`). A list assembled when the letters went out is a list of who was eligible **then**, and the nine removed are exactly the people a stale list would have disconnected wrongly.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-RBS-032` | A returned letter is not a served notice; a disconnect list re-checks delivery on the morning | PROPOSED |
| `BR-RBS-012` | Guards are absolute — medical protection and an open dispute win over every check | PROPOSED |
| `BR-RBS-002` | A Check has no writer — **nothing is disconnected here** | PROPOSED |

**3 · Test Cases**

| TC | Scenario | Expected | Must first fail on |
|---|---|---|---|
| `TC-RBS-024.1` | 23 accounts on the letter, re-checked on the morning | **14 eligible · 9 removed**, each removal with its reason | A list built when the letters went out |
| `TC-RBS-024.2` | An account whose letter was returned undelivered | **Removed**, naming the return | A returned letter counted as served |
| `TC-RBS-024.3` | Any run | **No disconnection is performed by the product** | A disconnect port — there is none, and there must be none |

**4 · Test Data** — 23 accounts at the last tier; 9 removed on the morning across: paid · on a plan · returned letter · medical protection · open dispute.

**5 · Data Fields / Mapping** — **Ports: none.** The approval writes `runbook_runs.approved_by`; the crew's act is outside the product.

**6 · Acceptance** — Given 23 accounts on the letter, when the list is re-checked on the morning, then 14 are eligible and 9 are removed each with its reason, and a supervisor signs a list the product does not act on.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---
id: US-RBS-025
epic: EP-RBS-05
module: runbooks
screens: [RBS-006]
phase: 5
status: ready
blocked_by: []
depends_on: []
journeys: []
rules: [BR-RBS-002, BR-RBS-013]
golden_tests: []
finance_calc: none — the move is payments' own screen
---
### US-RBS-025 — As a clerk I find where a payment went from an amount and a date

**1 · Details** — A clerk enters **$182.40 around 12 Sep** and reads **"Found · applied to Alvarez, M. · account ending 4471 · same last four"**, with **Move payment →** beside it. ⚠ **The chain stops where it stops and says so** — steps that were not needed read **Not needed**, the same honesty as *Never reached*. **The move itself is a payments screen with its own approval, one click away.**

⚠ **NO DATABASE ID ON SCREEN** (B14 rule 31): *account ending 4471* is the visible value, never the account's id.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-RBS-002` | A Check has no writer — the trace finds, it does not move | PROPOSED |
| `BR-RBS-013` | A payment is not edited here; **the three-column reference correction is a person's act on payments' own endpoint** and is not reachable from a runbook | **CONFIRMED — hard rule 4 as narrowed 2026-09-02** |

**3 · Test Cases**

| TC | Scenario | Expected | Must first fail on |
|---|---|---|---|
| `TC-RBS-025.1` | $182.40 around 12 Sep | **Found**, with the likely cause in words and **Move payment →** | A raw match list with no verdict |
| `TC-RBS-025.2` | A trace that stops at step 2 | Steps 3 to 5 read **Not needed** | Blank cells |
| `TC-RBS-025.3` · **B14 31** | The account on screen | *account ending 4471* | The account id |

**4 · Test Data** — A payment of **$182.4000** applied to the wrong account of the same last four, on 12 September.

**5 · Data Fields / Mapping** — **Ports: none.**

**6 · Acceptance** — Given an amount and a date, when the trace runs, then it reads Found with the account by its last four and the likely cause in words, and Move payment → opens payments' own screen.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — **`OQ-RBS-1734`** applies here too: runbook 13 no longer writes a note automatically. **Built meanwhile: the clerk adds it with one button.**

---
id: US-RBS-028
epic: EP-RBS-05
module: runbooks
screens: [RBS-006]
phase: 5
status: ready
blocked_by: []
depends_on: [US-RBS-004]
journeys: []
rules: [BR-RBS-002, BR-RBS-023]
golden_tests: []
finance_calc: re-prices a past cycle against a DRAFT schedule; issues nothing
---
### US-RBS-028 — As a manager I see what a draft tariff would have done to last cycle's bills

**1 · Details** — Before the board meeting a clerk sees **"1,146 bills go up · 121 by more than 15% · revenue +$5,310 (+4.7%)"**, and **the fifty biggest movers each with the clause that did it**. Per-record pricing plus a **set** step for the sums.

⚠ **IT RE-PRICES A PAST CYCLE THROUGH THE REAL ENGINE AGAINST A DRAFT SCHEDULE AND ISSUES NOTHING.** No bill number is consumed, no invoice moves, and the draft schedule is not made current. **A second pricing implementation here would tell a board something the product would not then do.**

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-RBS-002` | A Check has no writer | PROPOSED |
| `BR-RBS-023` | The sums are a set step; the pricing is per record | PROPOSED |

**3 · Test Cases**

| TC | Scenario | Expected | Must first fail on |
|---|---|---|---|
| `TC-RBS-028.1` | Last cycle against a draft schedule | **1,146 up · 121 by >15% · revenue +$5,310 (+4.7%)**; the fifty biggest movers each naming the clause | A total with no per-clause attribution — a board cannot act on it |
| `TC-RBS-028.2` | Any run | **No issued bill changes and no bill number is consumed** | A run that writes |
| `TC-RBS-028.3` | The pricing path | **The rating engine's**, identical to a real run | A second implementation |

**4 · Test Data** — A completed cycle of bills and one draft rate schedule producing exactly those figures.

**5 · Data Fields / Mapping** — The draft schedule is a **`ref:object`** parameter. Percentages **six** decimals stored, **two** displayed.

**6 · Acceptance** — Given last cycle and a draft schedule, when the preview runs, then the three figures render with the fifty biggest movers each naming the clause, and no issued bill has changed.

**7 · Finance Calculation** — **The rating engine's own path**, against a draft schedule. Money four decimals, percentages six, both displayed two. ⚠ **This story adds no figure to `GT-1..61` and moves nothing in ❄️ FROZEN B4/B5.**

**8 · Open Questions** — None.

---
id: US-RBS-030
epic: EP-RBS-05
module: runbooks
screens: [RBS-006]
phase: 5
status: ready
blocked_by: []
depends_on: [US-RBS-007]
journeys: []
rules: [BR-RBS-002, BR-RBS-011]
golden_tests: []
finance_calc: an estimate of unbilled revenue, labelled as one
---
### US-RBS-030 — As a manager I see where water is used with nobody billed

**1 · Details** — Monthly the clerk sees **"18 premises · about $1,940 a month unbilled · 7 stopped meters"**, each with **a likely cause in one of four words** and a fix. **The four words are a closed list** — a free-text cause is how a category becomes unusable, which is the largest defect class this repository has (380 unclassified rows, 21.5%).

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-RBS-002` | A Check has no writer | PROPOSED |
| `BR-RBS-011` | Every finding names its fix route | PROPOSED |

**3 · Test Cases**

| TC | Scenario | Expected | Must first fail on |
|---|---|---|---|
| `TC-RBS-030.1` | 90 days of usage on premises with no live service | **18 premises · about $1,940 · 7 stopped meters** | A count without the estimate — a manager cannot prioritise |
| `TC-RBS-030.2` | Every row | A cause from **the closed list of four**, and a fix route | A free-text cause |
| `TC-RBS-030.3` | The word *about* | Present — **the figure is an estimate and says so** | A precise-looking figure |

**4 · Test Data** — 90 days over an estate with 18 premises using water with no live service, 7 of them on stopped meters.

**5 · Data Fields / Mapping** — Subject **premise**, unit **90 days**. Category **Premises** (the product's own word; the specification's *Service points* is not used).

**6 · Acceptance** — Given 90 days of usage, when the runbook runs, then 18 premises render with an estimated monthly unbilled figure, 7 stopped meters, and every row carries one of four causes and a fix.

**7 · Finance Calculation** — **An estimate, labelled as one** — *about $1,940 a month*. It is not a receivable and must never be presented as one.

**8 · Open Questions** — None.

---
id: US-RBS-031
epic: EP-RBS-05
module: runbooks
screens: [RBS-006, RBS-007]
phase: 5
status: ready
blocked_by: []
depends_on: [US-RBS-006, US-RBS-007]
journeys: []
rules: [BR-RBS-002, BR-RBS-017]
golden_tests: []
finance_calc: none
---
### US-RBS-031 — As a clerk I see what in our records will trip the other runbooks

**1 · Details** — Monthly the clerk sees **"212 items · 900 accounts unreachable by text"**, **grouped by what each will break**, with *Reachable by text* as a tile. ⚠ **THE GROUPING IS THE STORY.** A hygiene list grouped by field is a chore; **grouped by the runbook it will break, it is a work queue with a reason** — and it is the one runbook whose findings are about the other runbooks.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-RBS-002` | A Check has no writer | PROPOSED |
| `BR-RBS-017` | Findings become work items upserted by fingerprint, so a monthly sweep ages rather than duplicating | PROPOSED |

**3 · Test Cases**

| TC | Scenario | Expected | Must first fail on |
|---|---|---|---|
| `TC-RBS-031.1` | An estate with known gaps | **212 items**, grouped by **what each will break** | Grouped by field |
| `TC-RBS-031.2` | Twelve monthly runs over one unfixed gap | **One** work item, twelve months old | Insert instead of upsert (`TC-RBS-10`'s shape) |
| `TC-RBS-031.3` | **900 accounts unreachable by text** | Rendered as a tile with its own count | Buried in the 212 |

**4 · Test Data** — An estate seeded to produce exactly 212 hygiene items across the runbooks they would break, and 900 accounts with no usable text channel.

**5 · Data Fields / Mapping** — Findings → `work_items` by fingerprint, through the **engine**, never a port.

**6 · Acceptance** — Given a monthly run, when it finishes, then 212 items render grouped by what each will break, *Reachable by text* is a tile, and a repeat run ages the items rather than duplicating them.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---

## Group D · Compose

---
id: US-RBS-039
epic: EP-RBS-05
module: runbooks
screens: [RBS-004]
phase: 5
status: ready
blocked_by: []
depends_on: [US-RBS-038, US-RBS-040]
journeys: []
rules: [BR-RBS-036, BR-RBS-037, BR-RBS-038]
golden_tests: []
finance_calc: none
---
### US-RBS-039 — As an admin I set a runbook's inputs, and *all* means all

⚠ **THIS STORY WAS TITLED *“As an admin I compose a runbook from shipped steps”* AND DESCRIBED A TENANT PICKING STEPS FROM A LIBRARY AND BUILDING A FILTER. THE PO CORRECTED IT ON 2026-09-06 (`BR-RBS-042`).** The old text is stamped rather than deleted, so a lane that read it learns what changed and who ruled it.

**What was wrong, and what was NOT.** *“An admin builds Vacant premises, Sewer from the step library”* — **a tenant never sees a step list.** *“Saving runs the conformance suite and refuses a composition”* — **there is no composition to save**; conformance is ours, at build time. ⚠ **But the step LIBRARY itself is REAL and it STAYS** — **173 step instances across 26 runbooks reduce to 137 distinct steps** (`14-step-library.md`, the hand count of 2026-09-06) — and it is **ours**, used from wave `C` onward. PO verbatim: *“I dont think Utility admin will able to configure these using the 150 bricks that we give - you can keep all these bricks and buld ready to use runbooks - when we later change it will be small er changes for us”*. **The reason is adoption, not architecture.**

**1 · Details** — **A runbook is one fixed process with declared inputs.** An admin opens the collections ladder's setup screen and sets its inputs: *past due over* `$5.00`, *services* **Water · Sewer**, *cycles* **All**, *account types* **All except Municipal**. The **process is identical at every utility**; the **output is filtered** by what was chosen. PO verbatim: *“you cannot change the logic those are finate steps ; you can change the input to logic … this way, we control the inputs however process remain same , and then out put produced is filtered”*.

⚠ ***ALL* IS A RULE, NOT A VALUE — THIS IS THE CLAUSE A BUILD WILL GET WRONG.** *All* is stored as **the word** and resolved when the **run starts** (`BR-RBS-009` pins it there). A utility that sets *all services* while it has Water and Sewer, then adds Trash, must get **three** on the next run. **Expand it at setup and adding a service silently drops it out of every runbook set to *all*** — no error, no screen change, nothing to see.

⚠ **EVERY DOMAIN IS TENANT-RESOLVED.** *“every utility will not have all utility services or all combinations of Plans and rates, so we ahve to work in variables”*. A two-service utility's *services* list offers two. **An empty domain says so** rather than drawing an empty dropdown.

⚠ **COMPOSE YES, AUTHOR NO — NARROWED, AND THE NARROWING IS STATED.** The PO ruled those four words on **2026-09-05** and this epic read *compose* as **the TENANT composing**. **2026-09-06 narrows it: WE compose; a tenant SETS and CLONES.** Both are the PO's and the later governs. *Author no* is unchanged and is now **structural**: a tenant who can only choose input values has no path by which to write logic, so nobody has to police it.

⚠ **THE TRUST RATCHET STAYS AND NOW BITES ON AN INPUT CHANGE.** `BR-RBS-036` used to guard a new composition; it guards a **changed input**. Widen a scope and the Action is **dry-run only** until a person has read one clean dry run of the changed set — so the first thing a widened runbook can do is show you what it would do.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-RBS-042` | A runbook is one fixed process with declared inputs; a domain per input, resolved per tenant; one value, several, or *all*, and *all* is stored as the word and resolved at run start | **CONFIRMED** (PO 2026-09-06) |
| `BR-RBS-009` | Scope is resolved once and pinned — which is where *all* resolves | PROPOSED |
| `BR-RBS-036` | An edited Action drops back to dry-run only until one clean dry run has been reviewed — **an edit now means a changed INPUT** | PROPOSED |
| `BR-RBS-038` | Every edit makes a new version; a run pins the version that produced it; **a change to a shipped template is OFFERED on a tenant's copy and never applied silently** | PROPOSED |
| `BR-RBS-037` | A runbook that fails the conformance suite does not save — ⚠ **ours at build time, not a tenant's save button** | PROPOSED |

**3 · Test Cases**

| TC | Scenario | Expected | Must first fail on |
|---|---|---|---|
| `TC-RBS-039.1` | *Services* set to **All** at a Water + Sewer utility; **Trash added the following month**; run again | The run covers **three** services | *All* expanded to a two-item list at setup, so Trash is silently outside every run |
| `TC-RBS-039.2` | The *services* domain at a two-service utility | Offers exactly **two** — the tenant's own | A hardcoded list of eleven, offering services the utility does not sell |
| `TC-RBS-039.3` | A domain with **no rows** (no plans configured yet) | **Says so in words** | An empty dropdown, which reads as broken |
| `TC-RBS-039.4` | An admin **widens** an Action's scope | **Dry-run only** until one clean dry run is reviewed | A widened Action sending on its first run |
| `TC-RBS-039.5` · **negative** | Anywhere in the product | **No step list, no filter builder, and no condition syntax is reachable by a tenant** | A rules language, however small — or a step picker |

**4 · Test Data** — One tenant with **Water and Sewer**, its collections ladder set to *services = All*; the same tenant after **Trash** is added. One tenant with **no plans configured**, for the empty-domain case.

**5 · Data Fields / Mapping** — The parameter's stored value is either a list of ids **or the literal `all`**; `resolve(params)` expands `all` **at run start** against the tenant's own domain and `BR-RBS-009` pins the result. `runbooks.origin = cloned` for a tenant's copy of a shipped runbook. ⚠ **This read `origin = composed` and *“the composition is a `runbook_versions.definition`”* until 2026-09-06** — a tenant produces no definition.

**6 · Acceptance** — Given a Water-and-Sewer utility whose collections ladder has *services* set to **All**, when Trash is added and the runbook runs, then it covers **three** services; and when an admin widens any input, the Action is dry-run only until one clean dry run is reviewed.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — **NONE. `OQ-RBS-1735` IS CLOSED** (PO 2026-09-06). ⚠ **This cell said the question was open and that *“the step library is the steps phase 5 has shipped”* until that date.** The question itself had the wrong shape: a tenant uses **no** steps and filters **no** fields, so *“which fields and which steps may a tenant use”* had no true answer. What replaced it is `BR-RBS-042`.


---

## Group U · The first two *named only* cards, built from one sentence each

⚠ **THIS GROUP IS NOT IN THE ORIGINAL PLAN AND THAT IS THE POINT.** The execution plan covers
runbooks 1–27 and 36. Runbooks 28–35 arrived with **a number, a home and one sentence** — no scope,
no steps, no guards, no ports, no screens — so no wave owned them and no story existed to place.
`US-RBS-043` and `US-RBS-044` were built on 2026-09-07 from those sentences, and **every decision
the source did not make is marked *(build)* on the card and recorded in the decision log**, so
nobody reads a judgment as a quotation. Six named-only cards remain: 29, 30, 31, 32, 34 and 35.

---
id: US-RBS-043
epic: EP-RBS-05
module: runbooks
screens: [RBS-004, RBS-006]
phase: 5
status: ready
blocked_by: []
depends_on: [US-RBS-015, US-RBS-016, US-RBS-041]
journeys: []
rules: [BR-RBS-002, BR-RBS-011, BR-RBS-012, BR-RBS-019, BR-RBS-020, BR-RBS-025, BR-AST-007, BR-REP-001]
golden_tests: []
finance_calc: none
---
### US-RBS-043 — As a clerk I see which meters are past their change-out age or have never been tested

**1 · Details** — As **a billing clerk**, I want **the meters that are older than their expected life
or that nobody has ever tested, biggest revenue first** — so that **the ones quietly under-registering
get changed out before another year of it**. Runbook 28 (`RB-128`), and **the first runbook in the
Assets category**, which held one step and no runbook: the category stops being empty and draws its
filter chip (`BR-RBS-025`).

⚠ **IT IS A CHECK, WHICH IS THE CARD'S OWN CONDITIONAL RESOLVED.** The source says it *"waits on
`RB-049` for a field order, and is a Check without it"*. `RB-049` does not exist and there is no
work-order port, so it is **constructed with no ports at all** and its two controls are FIX ROUTES
into `assets` rather than writes. What it becomes the day a field order arrives is written out in
`definitions/meter_change_out.py`'s docstring — a NEW VERSION, because `BR-RBS-001` says a kind never
changes.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-RBS-002` | A Check is CONSTRUCTED with no writer — the capability is absent, not unused | CONFIRMED |
| `BR-RBS-011` | Every finding names a TENANT-RELATIVE fix route; the shell prefixes the tenant | CONFIRMED |
| `BR-RBS-012` | Three guards, absolute, before step 1: sample · retired · in the store room | CONFIRMED |
| `BR-AST-007` | A test is due at `last_test_date + test_interval_months`; the stored status never moves | CONFIRMED |
| `BR-REP-001` | The money tile declares its basis — `posting`, because it is summed off issued bills | CONFIRMED |

**3 · Test Cases**

| TC | Scenario | Expected | Must first fail on |
|---|---|---|---|
| `TC-RBS-043.1` | A meter exactly at its expected life | **Not** past it — strictly greater, the Assets forecast's own rule | `>=`, which retires a 20-year meter a month early |
| `TC-RBS-043.2` | A fleet where no meter records an expected life | **0 past change-out age BESIDE `116 of 128 cannot be judged`** | The count alone, which reads as *your fleet is young* |
| `TC-RBS-043.3` | A meter tested but past its interval | **Counted on a tile, never raised as a row** — the card names two groups | Raising it, which widens a commitment |
| `TC-RBS-043.4` | A meter on an account that has billed | **The dollar it carries**, from the last issued bill's usage lines for its service | Reading the account under the wrong key — a silent `None` on every row |
| `TC-RBS-043.5` | A known **$0.00** against an unknown | The known one first — an unknown sorts BELOW every known figure and is never `0.0000` | Treating the unknown as zero, so the alphabet decides |

**4 · Test Data** — The seeded Brazos Bend fleet: **128 meters**, 119 of them sample records, 3 past
their expected life (by 5 months, 10 months and 1 year 2 months), **128 with no test on file**, 116
recording no expected life at all, and **$19,674.08 a month at risk across 111** — largest single
meter `E-5049` at **$4,590.00**.

**5 · Data Fields / Mapping**

| Field | Screen | DB target | Type | Origin | Validation |
|---|---|---|---|---|---|
| `assets.install_date` · `purchase_date` | `RBS-006` Records | read only | date | assets | the age base; `install` wins, `purchase` for stock |
| `assets.expected_life_years` | — | read only | int | assets | NULL is COUNTED, never defaulted |
| `assets.last_test_date` · `test_interval_months` | `RBS-006` Records | read only | date · int | assets | NULL `last_test_date` is the *never tested* group |

**6 · Acceptance** — Given a fleet with meters past their expected life and meters with no test on
file, when a clerk presses Run, then each appears once, ranked by the revenue it carries, with
**Order a test →** or **Schedule change-out →**; and the number of meters that cannot be judged on
age is on the screen as a ratio beside them.

**7 · Finance Calculation** — N/A. *Revenue at risk* is READ from the last issued bill's usage lines
and is not priced here; re-interpreting a tariff is rating's job.

**8 · Open Questions** — **NONE.** `RB-049` does not exist, and its absence is a stated design fact
on the card rather than a question.

---
id: US-RBS-044
epic: EP-RBS-05
module: runbooks
screens: [RBS-004, RBS-006]
phase: 5
status: ready
blocked_by: []
depends_on: [US-RBS-015, US-RBS-016, US-RBS-041, US-RBS-012]
journeys: []
rules: [BR-RBS-004, BR-RBS-006, BR-RBS-018, BR-RBS-020, BR-RBS-022, BR-BIL-017, BR-BIL-021, BR-REP-001]
golden_tests: [GT-24]
finance_calc: none
---
### US-RBS-044 — As a clerk I see which budget-billing levels the last twelve months no longer support

**1 · Details** — As **a billing clerk**, I want **each budget-billing account's current level beside
the level its last twelve months support** — so that **a customer paying far too little or far too
much is found before the settle-up rather than at it**. Runbook 33 (`RB-133`), an **Action**.

⚠ **ITS CENTRAL ACT HAS NO PORT AND THE REFUSAL IS THE DELIVERABLE.** Nothing in the fourteen ports
moves `account_budget_status.level`; `billing`'s single port raises a draft fee. A fifteenth is a
REVIEWED INTERFACE (`BR-RBS-022`), so step 4 records the refusal with both figures on the row —
`OQ-RBS-1760`, open. ⚠ **AND NOBODY IS TOLD EITHER.** The commitment's order is *told first*, which
is right when a change can FAIL and wrong when it is known impossible before the run starts: the
notice would tell a customer their payment is changing when nothing can change it. Step 3 holds it.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-RBS-018` | Every money-bearing action carries a second approval, no threshold | **CONFIRMED — PO 2026-09-06** |
| `BR-RBS-006` | The cap REFUSES the run and never truncates it; 100 is the PO's own default | **CONFIRMED — PO 2026-09-06** |
| `BR-RBS-022` | A write is a NAMED port; a fifteenth is a reviewed interface, not a line | CONFIRMED |
| `BR-BIL-017` | Level = trailing-window average, whole $; re-level at drift AND at cadence | CONFIRMED |
| `BR-BIL-021` | Every budget parameter is tenant config, READ and never defaulted | CONFIRMED |
| `BR-REP-001` | The money tiles declare `priced` — a level is computed and never posted | CONFIRMED |

**3 · Test Cases**

| TC | Scenario | Expected | Must first fail on |
|---|---|---|---|
| `TC-RBS-044.1` | Any run, on any tenant | **No port applies a budget level** — asserted BY NAME, so the day one lands this goes red and names the file | Planting a budget-level port |
| `TC-RBS-044.2` | An account whose level should move | The notice is **HELD**, with *"this product cannot move a budget level yet"* | Queueing it, then discovering the change is impossible |
| `TC-RBS-044.3` | ❄️ `GT-24`'s own chain | $2,904 over twelve months → a level of **$242**, through billing's own function | Re-implementing a frozen figure here |
| `TC-RBS-044.4` | Past the band but levelled last month | **Not at cadence** — a separate outcome, never one *no change* | Dropping the cadence gate |
| `TC-RBS-044.5` | Nine months of bills under a twelve-month window | **Not enough history**, reported as *9/12 months* | Averaging what it has |
| `TC-RBS-044.6` | An account carrying a level override | Walked, and the row says the computed level moves while the payment does not | Guarding it out, which leaves the ±30% bound stale |

**4 · Test Data** — Twelve accounts enrolled through `budget_service.enroll` on the seeded utility,
the drift band at 5%: **4 of 12 levels should move, $51.00 a month**, and `AC-2026-00013` reads
*"268.00 would become 282.00. This one has to be changed by hand."*

**5 · Data Fields / Mapping**

| Field | Screen | DB target | Type | Origin | Validation |
|---|---|---|---|---|---|
| `account_budget_status.level` · `level_override` | `RBS-006` Records | read only | numeric | billing | both travel; neither replaces the other |
| `account_budget_status.last_leveled_at` · `enrolled_on` | — | read only | date | billing | a NULL `last_leveled_at` is NOT age zero — it falls back to `enrolled_on` |
| the S69 window · drift · cadence | `RBS-004` Setup, **dashed and read-only** | `tenants.settings` | int · decimal · int | tenancy | READ, never defaulted (`RBR-03`) |

**6 · Acceptance** — Given budget-billing accounts whose usage has moved, when a clerk presses Run,
then each account shows its current level, the level the last twelve months support and the change;
and because nothing in this product can apply that change, **Apply the new levels** is drawn disabled
with its reason and no customer is written to.

**7 · Finance Calculation** — The level is `apps.billing.budget.compute_level`, ❄️ **`GT-24`**, asked
through `billing_seam.budget_level_decision` and re-implemented nowhere.

**8 · Open Questions** — **TWO, NEITHER BLOCKING.** `OQ-RBS-1759` (the template library cannot draw
this card *Unavailable*) and `OQ-RBS-1760` (should a fifteenth port move a budget level). Each is a
stated absence in the shipped code rather than a stub awaiting an answer.


## What this epic does NOT prove, said out loud

* ~~**Runbook 33 (budget billing) is not here.** It waits on the budget-billing capability existing and is **not scheduled by this pack**.~~ ⚠ **SUPERSEDED 2026-09-07 — IT IS HERE NOW, AS `US-RBS-044` IN GROUP `U` BELOW**, together with runbook 28 (`US-RBS-043`), the first two of the eight *named only* cards to be built. **The capability sentence was right and is now stated differently:** the product has no budget-billing capability FLAG to wait on, and a run on a tenant with nobody enrolled pins zero accounts and says so — which is `OQ-RBS-1759`, open.
* **Runbooks 34 and 35 are not here.** The storm broadcast waits on a delivery provider and `RB-044`; the service-request chase waits on the **Work module** (`CR-070`) and on `OQ-249`. Both are *later*, not phase 5.
* **Work orders and inspection records are not subject types yet.** `RB-049` waits on `CR-070` and `OQ-249`; **a reference default is not permission to build them.**
* **Notice throughput and the *still sending* state are not built** (`RB-044`, waiting on a connected delivery provider).
* ⚠ **AND THE HOLDS ON THESE NINETEEN CARRY THEIR EXPIRY TESTS.** Each runbook's template card sits on `RBS-002` behind a hold until its module lands, and **the hold's test asserts the destination by address and by screen id in the same commit that writes the hold** — so the day the module lands the suite goes **red** and names the card. Nineteen holds with no such tests is `DEF-CWP-3925` at nineteen times the scale.
