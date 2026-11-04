# runbooks — User Stories (INDEX)

> **Forty-one stories, each landing something a user can see.** Taken from the Runbooks
> specification §B5 (v0.1, restructured 5 September 2026). **Every acceptance sentence is the source's
> own, one sentence, unchanged in substance** — the only edits are the screen codes, which are
> `RBS-001`–`RBS-008` in this repository and `S147`–`S154` in the source (PO ruling 2026-09-06).
> Where a story's acceptance is also a commitment card's *"done looks like"* sentence, the two are
> the same words on purpose, so they cannot drift.

**Stories live inside their epic files in [`06-epics/`](06-epics/).** This index is generated from
story frontmatter at each pack merge — do not hand-edit story content here.

⚠ **THE PHASE COLUMN IS THIS PACK'S, NOT THE SOURCE'S — AND IT WAS RE-CUT ON 2026-09-06.** Two
Product Owner rulings that day put the integration runbooks first: *"once you have foundation I want
to prioritise runbook related to integration first and then rest"*, then *"For me integration related
to accounting, payment provider, emails, GIS are important - over other"*. **Sixteen of the
forty-one stories changed phase and NOT ONE changed epic**; the epics are not renumbered, so the epic
column and the phase column no longer track each other. The specification has eight increments
(`1a`–`1d`, `2a`–`2c`, `3`); the mapping is printed in
[`10-execution-plan.md`](10-execution-plan.md) §1, every story is placed **exactly once**, and the
source's own increment is kept in the last column so a citation of *"phase 2a"* still lands.

| Story | Title | Acceptance, in one sentence | Epic | Phase | Source |
|---|---|---|---|---|---|
| US-RBS-001 | As a clerk I run a Check and see what is stopping billing | Pressing Run on "Can we bill?" returns 3 blockers, each naming the screen that fixes it, and writes nothing | [EP-RBS-01](06-epics/EP-RBS-01-can-we-bill.md) | **1** | 1a |
| US-RBS-002 | As a developer I need a Check that cannot write | A Check constructed without action ports raises on any write attempt, proved by a test that binds a port and fails | [EP-RBS-01](06-epics/EP-RBS-01-can-we-bill.md) | **1** | 1a |
| US-RBS-003 | As a clerk I see the runbook catalogue | RBS-001 lists every runbook with kind, schedule, last result and open items | [EP-RBS-01](06-epics/EP-RBS-01-can-we-bill.md) | **1** | 1a |
| US-RBS-004 | As a clerk I price one account without billing it | Test bill returns every line explained, or one refusal naming the service and the date; no bill number is consumed | [EP-RBS-02](06-epics/EP-RBS-02-prove-it-on-their-data.md) | **4** | 1b |
| US-RBS-005 | As an implementer I see coverage across 25 accounts | The grid shows 21 clean, 2 estimated, 2 refused, and each cell opens that account's test bill | [EP-RBS-02](06-epics/EP-RBS-02-prove-it-on-their-data.md) | **4** | 1b |
| US-RBS-006 | As a clerk I find every open item in one place | RBS-007 shows findings, exceptions and human tasks together, upserted so a repeated finding ages rather than duplicates | [EP-RBS-03](06-epics/EP-RBS-03-it-runs-without-anyone.md) | **4** | 1c |
| US-RBS-007 | As a clerk I have checks run on a schedule | The pre-bill sweep runs daily at 06:00 tenant local and raises work items without anyone opening the product | [EP-RBS-03](06-epics/EP-RBS-03-it-runs-without-anyone.md) | **4** | 1c |
| US-RBS-008 | As an implementer I reconcile a cutover | Loaded balances are compared to the legacy trial balance, and the plan item records the variance as evidence | [EP-RBS-03](06-epics/EP-RBS-03-it-runs-without-anyone.md) | **4** | 1d |
| US-RBS-009 | As a finance user I see what does not balance at month end | Books tie-out lists unposted items and unallocated cash, and is clear when the period balances | [EP-RBS-03](06-epics/EP-RBS-03-it-runs-without-anyone.md) | **4** | 1d |
| US-RBS-010 | As a clerk I see what an Action would do before it does it | A dry run of the collections ladder shows 812 to send, 97 skipped and 95 needing a person, each with its rule | [EP-RBS-04](06-epics/EP-RBS-04-it-acts-and-you-approve.md) | **2 · dry** | 2a |
| US-RBS-011 | As an admin I approve a batch, not a row | One approval carrying the count releases the run; a plan that has changed since returns a conflict | [EP-RBS-04](06-epics/EP-RBS-04-it-acts-and-you-approve.md) | **2 · dry** | 2a |
| US-RBS-012 | As an admin I can stop a run in flight | Stopping halts before the next record; records already acted stay acted and are listed | [EP-RBS-04](06-epics/EP-RBS-04-it-acts-and-you-approve.md) | **2 · dry** | 2a |
| US-RBS-013 | As a clerk the ladder sends the right notice to the right account | 248 notices are queued against the tenant's own ladder, none to a protected or disputed account, and a re-run sends nothing twice | [EP-RBS-04](06-epics/EP-RBS-04-it-acts-and-you-approve.md) | **2 · live** | 2b |
| US-RBS-014 | As an auditor I can see what the automation did and why | Every acted record carries the runbook, its version, the rule that decided it and an audit row naming the runbook as actor | [EP-RBS-04](06-epics/EP-RBS-04-it-acts-and-you-approve.md) | **2 · live** | 2b |
| US-RBS-015 | As a developer I add a runbook without touching the frontend | A new module declaring scope, steps and report appears on RBS-001 and renders on RBS-004 and RBS-006 with no frontend change; the conformance suite passes it | [EP-RBS-01](06-epics/EP-RBS-01-can-we-bill.md) | **1** | 1a |
| US-RBS-016 | As a clerk every result reads the same way | One renderer draws any run's report from its twelve block types; a report with an unknown block type is refused at run close, not at render | [EP-RBS-01](06-epics/EP-RBS-01-can-we-bill.md) | **1** | 1a |
| US-RBS-017 | As a clerk a runbook runs when a batch lands | A payments batch landing from the lockbox connection starts cash application within a minute, with the batch pinned as its scope | [EP-RBS-05](06-epics/EP-RBS-05-the-rest-of-the-catalogue.md) | **3** | 2c |
| US-RBS-018 | As a clerk I find a runbook by the part of the business it serves | RBS-002 filters by category; twelve templates show eight chips because eight categories hold one, and a category holding none draws no chip | [EP-RBS-01](06-epics/EP-RBS-01-can-we-bill.md) | **1** | 1a |
| US-RBS-019 | As a clerk I explain a higher bill in one screen | A clerk picks an account and two bills and reads aloud "Up $82.20 · usage +38% over 4 more days · tier 2 reached · late fee $12.00 · rate unchanged", with the two bills side by side. (runbook 4, RB-104) | [EP-RBS-05](06-epics/EP-RBS-05-the-rest-of-the-catalogue.md) | **5** | 3 |
| US-RBS-020 | As a clerk I see which meters behave oddly, ranked by revenue at risk | A clerk sees 75 meters in six pattern tiles, each row with its own twelve-month line and "$1,180.00 at risk · Order a test →", sorted by revenue at risk. (runbook 5, RB-105) | [EP-RBS-05](06-epics/EP-RBS-05-the-rest-of-the-catalogue.md) | **5** | 3 |
| US-RBS-021 | As a clerk I learn why one account did not bill and fix it from the same screen | A clerk opens the account and reads "Stopped at step 4 · No Sewer read between 18 Aug and 17 Sep" with Add a read → in the page head; the variant lists all 14 accounts the run left unbilled by the step that stopped them. (runbook 6, RB-106) | [EP-RBS-05](06-epics/EP-RBS-05-the-rest-of-the-catalogue.md) | **5** | 3 |
| US-RBS-022 | As a cashier the day's landed payments apply themselves and I decide only the unmatched | At 06:30 the clerk sees "129 applied · 6 need you · 3 duplicates held", a by-source table, and each unmatched payment with its likeliest account and Pick account →. (runbook 10, RB-110) | [EP-RBS-05](06-epics/EP-RBS-05-the-rest-of-the-catalogue.md) | **3** | 2c |
| US-RBS-023 | As a clerk a customer is told about a running leak before the bill says so | The clerk sees "9 alerts queued" and reads the exact text a customer receives, naming the address and hours and never a dollar figure; the row with no channel says so. (runbook 11, RB-111) | [EP-RBS-05](06-epics/EP-RBS-05-the-rest-of-the-catalogue.md) | **5** | 2c |
| US-RBS-024 | As a supervisor I sign a disconnect list that was re-checked this morning | The morning of, a person sees "14 eligible · 9 removed since the letter" with why each was removed, and signs a field list; nothing is disconnected by the product. (runbook 12, RB-112) | [EP-RBS-05](06-epics/EP-RBS-05-the-rest-of-the-catalogue.md) | **5** | 3 |
| US-RBS-025 | As a clerk I find where a payment went from an amount and a date | A clerk enters $182.40 around 12 Sep and reads "Found · applied to Alvarez, M. · account ending 4471 · same last four", with Move payment → beside it. (runbook 13, RB-113) | [EP-RBS-05](06-epics/EP-RBS-05-the-rest-of-the-catalogue.md) | **5** | 3 |
| US-RBS-026 | As a finance user yesterday's statement lines match our batches without a spreadsheet | Tom sees "15 matched · 3 need you · $1,910.00 unmatched", each unmatched line beside its nearest batch and the difference, and the bank fee as a tile. (runbook 14, RB-114) | [EP-RBS-05](06-epics/EP-RBS-05-the-rest-of-the-catalogue.md) | **3** | 2c |
| US-RBS-027 | As a finance user deposits owed back are found with interest, and refunds wait for a second approval | On the 1st the clerk sees "48 credited · 13 refunds await approval · $296.40 interest", and each refund row says Account closed or Over the $250.00 limit. (runbook 15, RB-115) | [EP-RBS-05](06-epics/EP-RBS-05-the-rest-of-the-catalogue.md) | **5** | 3 |
| US-RBS-028 | As a manager I see what a draft tariff would have done to last cycle's bills | Before the board meeting a clerk sees "1,146 bills go up · 121 by more than 15% · revenue +$5,310 (+4.7%)", the fifty biggest movers each with the clause that did it. (runbook 16, RB-116) | [EP-RBS-05](06-epics/EP-RBS-05-the-rest-of-the-catalogue.md) | **5** | 3 |
| US-RBS-029 | As a clerk autopay customers are told the amount before the debit and failed debits are handled | At 08:00 the clerk sees "851 queued · 2 debits need you", and each failed debit reads the bank's reason in words with Retry 7 Sep or To the ladder. (runbook 17, RB-117) | [EP-RBS-05](06-epics/EP-RBS-05-the-rest-of-the-catalogue.md) | **5** | 2c |
| US-RBS-030 | As a manager I see where water is used with nobody billed | Monthly the clerk sees "18 premises · about $1,940 a month unbilled · 7 stopped meters", each with a likely cause in one of four words and a fix. (runbook 18, RB-118) | [EP-RBS-05](06-epics/EP-RBS-05-the-rest-of-the-catalogue.md) | **5** | 3 |
| US-RBS-031 | As a clerk I see what in our records will trip the other runbooks | Monthly the clerk sees "212 items · 900 accounts unreachable by text" grouped by what each will break, with Reachable by text as a tile. (runbook 19, RB-119) | [EP-RBS-05](06-epics/EP-RBS-05-the-rest-of-the-catalogue.md) | **5** | 3 |
| US-RBS-032 | As a clerk a landed parcel batch is reconciled by the utility's own dispositions | After a parcel batch lands the clerk sees "980 applied · 218 need you · 12 never touched", the by-class table, and Ours · Theirs on every queued row with Accept theirs → · Keep ours. (runbook 20, RB-120) | [EP-RBS-05](06-epics/EP-RBS-05-the-rest-of-the-catalogue.md) | **3** | 3 |
| US-RBS-033 | As a clerk a landed interval batch is validated and handed to billing overnight | After an interval batch lands the clerk sees "1,802 validated · 31 estimated · 7 queued · 1,833 handed to billing", each queued meter with its last good day. (runbook 21, RB-121) | [EP-RBS-05](06-epics/EP-RBS-05-the-rest-of-the-catalogue.md) | **5** | 3 |
| US-RBS-034 | As a clerk a bounced address is suppressed and the next channel used the same day | At 07:00 the clerk sees "31 suppressed · 27 fell back · 4 nothing left", with where each suppressed channel fell back to and Owed on every nothing-left row. (runbook 22, RB-122) | [EP-RBS-05](06-epics/EP-RBS-05-the-rest-of-the-catalogue.md) | **3** | 2c |
| US-RBS-035 | As a clerk missed instalments are warned and plans voided by rule | A clerk sees plans in flight, the instalments missed this cycle, and which plans were voided after the configured misses, each with its rule. (runbook 25, RB-125) | [EP-RBS-05](06-epics/EP-RBS-05-the-rest-of-the-catalogue.md) | **5** | 2c |
| US-RBS-036 | As a cashier returned payments are reversed, the fee applied and the customer told | A clerk sees returned items reversed, the fee applied by rule behind the second approval, the customer notified, and the privilege removed after N returns, each with its rule. (runbook 26, RB-126) | [EP-RBS-05](06-epics/EP-RBS-05-the-rest-of-the-catalogue.md) | **5** | 2c |
| US-RBS-037 | As a clerk every closing account gets its final bill and its deposit settled | A clerk sees every closing account with its closing read due, its final bill issued or waiting, its deposit refunded or carried, and the forwarding address captured. (runbook 27, RB-127) | [EP-RBS-05](06-epics/EP-RBS-05-the-rest-of-the-catalogue.md) | **5** | 2c |
| US-RBS-038 | As an admin I clone a runbook and vary its settings | Clone on Dunning makes "Commercial accounts" with its own schedule, cap and dry run; both rows appear on My runbooks (RB-040) | [EP-RBS-01](06-epics/EP-RBS-01-can-we-bill.md) | **1** | 1c |
| US-RBS-039 | As an admin I compose a runbook from shipped steps | A composition saves only when the conformance suite passes it, and an edited Action is dry-run only until one clean dry run is reviewed (RB-041) | [EP-RBS-05](06-epics/EP-RBS-05-the-rest-of-the-catalogue.md) | **5** | 3 |
| US-RBS-040 | As an admin I change a runbook and every run still says which version ran it | Changing the first reminder to 15 days makes v4; the Activity tab shows it with my name and the time; the v3 run's report is unchanged; Run offers only a dry run until one clean dry run of v4 is reviewed; a template update appears on my copy as "Template updated · Review →" and changes nothing until I press it | [EP-RBS-01](06-epics/EP-RBS-01-can-we-bill.md) | **1** | 1c |
| US-RBS-041 | As a developer I reach another module only through a seam I own, and the register knows it | The runbook module has one seam file per module it reads and thirteen port seams for writes, each with a row in the interface register; importing another module's models or adding an HTTP client fails the module's import census | [EP-RBS-01](06-epics/EP-RBS-01-can-we-bill.md) | **1** | 1a |
| US-RBS-042 | As a bookkeeper I download the month as a journal file instead of typing it in | A clerk picks the months, presses Run, and gets a six-column general-journal CSV — date, account code, description, debit, credit, reference — with two decimals on both money columns and debits equal to credits; anything that could not be exported is listed beside it with the screen that fixes it, and an unbalanced file is refused whole rather than exported short. (runbook 36, RB-136) | [EP-RBS-01](06-epics/EP-RBS-01-can-we-bill.md) | **1** | 1d |

| US-RBS-043 | As a clerk I see which meters are past their change-out age or have never been tested | A clerk sees meters older than the utility's change-out age or with no test on file, ranked by revenue at risk, each with **Order a test →** or **Schedule change-out →**; a meter that cannot be judged on age is COUNTED beside them rather than reported as fine, and the count is a ratio. (runbook 28, RB-128 — the first runbook in the Assets category) | [EP-RBS-05](06-epics/EP-RBS-05-the-rest-of-the-catalogue.md) | **5** | later |
| US-RBS-044 | As a clerk I see which budget-billing levels the last twelve months no longer support | A clerk sees each budget-billing account's current level, the level the last twelve months support, and the change queued behind approval with the customer told first — and where this product cannot move a level, the row says so in words and nobody is told about a change that cannot be made. (runbook 33, RB-133) | [EP-RBS-05](06-epics/EP-RBS-05-the-rest-of-the-catalogue.md) | **5** | 3 |

**43 stories · 5 epics · none blocked.** ⚠ **THIS READ *41* UNTIL 2026-09-07**, when `US-RBS-043`
and `US-RBS-044` were added with runbooks 28 and 33 — the first two of the eight *named only* cards
to be built. Neither is blocked: `OQ-RBS-1759` and `OQ-RBS-1760` are open beside runbook 33 and
each is a stated absence in the shipped code rather than a stub awaiting an answer.
Rules: [`02-business-rules.md`](02-business-rules.md) · Overview: [`01-overview.md`](01-overview.md) ·
Execution plan: [`10-execution-plan.md`](10-execution-plan.md) · Wireframes and build sheets:
[`wireframes/`](wireframes/).

## Where each phase's stories sit, and the count

| Phase (from 2026-09-06) | Waves | Stories | Count |
|---|---|---|---|
| **1 · The foundation, part one: it can look** | `A`–`E` | 001 · 002 · 003 · 015 · 016 · 018 · 038 · 040 · 041 | 9 |
| **2 · The foundation, part two: it can act** | `L` `M` `N` | dry: 010 · 011 · 012 — live: 013 · 014 | 5 |
| **3 · The integration runbooks** | `O` `P` `Q′` | 017 · 022 · 026 · 032 · 034 | 5 |
| **4 · Prove it on their data, and the scheduled Checks** | `F`–`K` | 004 · 005 · 006 · 007 · 008 · 009 | 6 |
| **5 · The rest** | `R′` `S` `T` | 019 · 020 · 021 · 023 · 024 · 025 · 027 · 028 · 029 · 030 · 031 · 033 · 035 · 036 · 037 · 039 | 16 |
| | | | **41** |

⚠ **`US-RBS-014` IS BUILT ACROSS BOTH HALVES, WHICH IS WHY TWO TRUE DOCUMENTS APPEAR TO DISAGREE
ABOUT IT — noticed while applying the re-cut and written down rather than "fixed".** The execution
plan lists it under wave `L` because task **`L1`** — the audit actor identity, the thing that stops
a runbook borrowing a staff login — is the story's foundation and is the first task of the dry half.
This index and the epic list it under **live** because task **`N4`** is where it is *demonstrated*:
the audit trail read end to end, 400 rows naming the runbook and its version and none naming a
person. **Both are correct and neither is a placement error**; the story's `phase:` field says
`2-live` because that is where it is finished.

## Two changes to the source's own placement, and the reason for each

⚠ **`US-RBS-038` (clone) and `US-RBS-040` (versions) move from the source's `1c` into phase 1.** The
brief for phase 1 names *"definition + versioning"* among the engine's envelope, and both stories
render entirely on `RBS-002`, `RBS-003` and `RBS-004`, which are phase-1 screens. **Phase 1
therefore delivers the definition surface whole** — the shipped library, adding a template to My
runbooks, cloning it, and every edit making a new version that a run pins. Splitting versioning
from the run record it pins would leave phase 1 shipping a run whose `version` column means
nothing.

⚠ **No story is BLOCKED, and that is a change from the source's shape rather than an oversight.**
The source carries `US-RBS-039` as waiting on an open question about which fields and steps a
tenant may compose with, and `US-RBS-023` as waiting on whether a tenant may ever set a runbook
unattended. **Both questions are now carried against the phase they belong to** (`OQ-RBS-1735` on
phase 5, `OQ-RBS-1733` on phase 4) **rather than against a phase-1 story**, which is what the
Product Owner asked for: the open questions land in phases 4 and 5 and block nothing before them.
See [`10-execution-plan.md`](10-execution-plan.md) §6.


## What the 2026-09-06 re-cut changed in this index

**Sixteen phase cells moved and nothing else did.** No story changed its epic, its acceptance
sentence, its source increment or its id.

| Stories | Was | Now | Why |
|---|---|---|---|
| 010 · 011 · 012 · 013 · 014 | 4 | **2** | Every integration-driven runbook is an **Action**, and an Action cannot run before the acting half exists — the thirteen ports, the gate, the cap, stop, the idempotency key and the audit actor. Prioritising the integration runbooks therefore moves the acting half into the foundation |
| 017 · 022 · 026 · 032 · 034 | 5 | **3** | The event trigger plus the four runbooks serving the areas the Product Owner named — **accounting** (bank reconciliation, 14) · **payment provider** (cash application, 10) · **emails** (undeliverable contacts, 22) · **GIS** (GIS reconciliation, 20) |
| 004 · 005 | 2 | **4** | Test bill and the coverage grid are Checks; they move behind the acting half and the integration runbooks |
| 006 · 007 · 008 · 009 | 3 | **4** | The work list, schedules, cutover reconciliation and the books tie-out join them in one phase of Checks |
| 023 · 033 | 5 | **5** (unchanged, but they were briefly phase 3) | Leak alert (11) and read validation (21) are integration-driven Actions, **but they are fed by interval-meter data — `meters_mdm`, `meters_neptune360` — which is none of the four areas the Product Owner named.** They stay in phase 5, at the head of wave `R′` after returned payments and autopay |

⚠ **THAT PARAGRAPH READ *"`US-RBS-023` IS STILL WAITING ON `OQ-RBS-1733`"* UNTIL 2026-09-07 AND IT
IS NO LONGER TRUE — `OQ-RBS-1733` CLOSED ON 2026-09-06.** Stamped rather than deleted, because a lane
that read the old sentence would otherwise be corrected without learning why (CLAUDE.md's
status-column law: *a closed question's body goes on describing the open world, and the body is what a
lane actually reads*).

**The answer was a FOURTH option nobody offered**, and it is now `BR-RBS-041`: permission is granted
**up front, per runbook**; with it on a run goes plan → act in ONE pass, with it off it stops at
Review. PO verbatim, *"ask for permission from user upfront - if they are okay we complete the run and
action, otherwise not"*, confirmed with *"you are correct"*. **The three-clean-run ratchet this project
recommended is NOT built.** The plan is computed and stored either way, so `BR-RBS-004` survives.

**Nothing was blocked in either phase and nothing is now.** What is BUILT for `US-RBS-023`
(`06-backend/apps/runbooks/definitions/leak_alert.py`, `CR-075` wave R′, 2026-09-07) still draws the
*"Unattended after"* parameter read-only — **for a different reason**: the switch `BR-RBS-041`
describes is wave `L3`'s, and `runbooks.gate_mode` holds one value today.
