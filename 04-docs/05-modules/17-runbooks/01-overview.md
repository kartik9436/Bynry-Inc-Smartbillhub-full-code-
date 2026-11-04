# Module — runbooks

**One engine that walks a set of things, applies a utility's own declared process, and either
reports what needs fixing or does the work — with a dry run before anything happens and an
audit row after everything does.**

**Backend module:** `06-backend/apps/runbooks` · **Route:** `/{tenant}/operations` ·
**Screens:** `RBS-001`–`RBS-008` (PO ruling 2026-09-06) · **Written** 2026-09-06 against product
`2.201.1` from the Runbooks specification (v0.1 draft, 4 September 2026, restructured 5 September,
build sheets 6 September), the *Twenty-One Runbooks* definitions page and the Runbooks market study.

> **Naming, stated once so nobody re-derives it wrongly.** The section, the module and the word a
> clerk reads are all **Runbooks** — PO 2026-09-06, *"we coin the word Runbooks - we should make
> this industry standard"*, which is a ruling **against** the market study's own counter-evidence
> and is not to be "corrected" to *Checklist* later (decision log 2026-09-06). The **route** stays
> `/{tenant}/operations` as drawn on every wireframe, and the section name in the nav is not ruled
> yet; the **backend module is `apps/runbooks`**, superseding the source documents' `apps/operations`.
> Where a source document says `apps/operations` or `S147`–`S154`, this repository says
> `apps/runbooks` and `RBS-001`–`RBS-008`. **Nothing in the source documents is renamed** — they
> stay the source and re-lettering them would break every cross-reference.

---

## 1 · What a runbook is

A utility's own process, written down once and run on demand.

A runbook takes a set of things — the tenant's configuration, 25 sample accounts, 250 accounts in
arrears — applies checks the utility has already configured, and produces either a list of what
needs fixing or a set of actions it has taken. **Nothing happens until a person sees what would
happen and approves it.**

The idea is not new to this product; it is already here three times in different clothes. The
import runner stages a file and shows every row before committing. The bill run produces
everything, holds, and releases separately. The collections ladder sits in settings as an ordered
escalation with parameters. **What is missing is the thing that walks a set and applies a declared
process** — and it is missing identically in onboarding, in cutover, and in the monthly work a
clerk does by hand. One engine, three uses. That is the whole proposal.

### 1.1 · One fixed process, declared inputs — what *configurable* means here (`BR-RBS-042`)

**A runbook's steps do not vary between utilities. Its INPUTS do.** PO ruling 2026-09-06,
verbatim: *“you cannot change the logic those are finate steps ; you can change the input to logic … this way, we control the inputs however process remain same , and then out put produced is filtered ; please note every utility will not have all utility services or all combinations of Plans and rates, so we ahve to work in variables”*.

The collections ladder already reads this way: ***past due over `$5.00` · services Water · Sewer ·
cycles All · account types All except Municipal*** are its **inputs**, and its six steps are the
same six at every utility. Each input carries a **domain**; a tenant picks **one value, several, or
*all***; the output is filtered by the choice.

⚠ ***ALL* IS A RULE, NOT A VALUE.** It is stored as the **word** and resolved when the **run
starts** — never expanded to a list at setup. A utility that picks *all services* while it has
Water and Sewer, then adds Trash, gets **three** on the next run. Expanding early would make adding
a service **silently drop it out of every runbook set to *all***, with nothing on any screen to see.

⚠ **AND EVERY DOMAIN IS TENANT-RESOLVED.** *“every utility will not have all utility services or
all combinations of Plans and rates”*. Two services means two; an empty domain says so.

⚠ **WHO ARRANGES THE STEPS: WE DO, AND ONLY WE.** **173 step instances across 26 runbooks reduce to 137 distinct steps** (`14-step-library.md`, the hand count of 2026-09-06) — a library used from wave `C` onward. It is an **internal engineering asset**: no screen
draws it, no endpoint serves it, and **a utility admin never sees a step list.** PO verbatim: *“I dont think Utility admin will able to configure these using the 150 bricks that we give - you can keep all these bricks and buld ready to use runbooks - when we later change it will be small er changes for us”*. **The reason is adoption, not architecture** — this is a new concept for everyone and a
two-person utility will not assemble a runbook out of a hundred bricks.

⚠ **THIS NARROWS A SIGNED RULING AND THE NARROWING IS STATED.** The PO ruled ***“compose yes,
author no”*** on **2026-09-05** and this module read *compose* as **the TENANT composing**. The
ruling of **2026-09-06 narrows it: WE compose; a tenant SETS and CLONES.** Both are the PO's; the
later governs. **The payoff is that *author no* becomes structural** — a tenant who can only choose
input values has no path by which to write logic, so the safety comes from the shape rather than
from a rule somebody has to police.

⚠ **AND THE SHARED STEP'S SAVING IS SMALLER THAN THIS MODULE CLAIMED, WHICH IS A MEASUREMENT AND
NOT A RE-SIGN.** **122 of the 137 (89%) are used by exactly one runbook** and fifteen steps carry all of the sharing — the most-used is *“resolve the declared scope into the pinned set”* at seven runbooks, and the reduction is **20.8%** (36 of 173), so the assembly saves **a fifth** of the step-writing rather than a third. The model is kept for **blast radius** — a fix to one shared step lands in every runbook
using it, **and breaks every one just as fast** — so a shared step **carries its own tests** and a
change to one **names which runbooks it moves**. `BR-RBS-038` holds the tenant-facing half: a
change to a shipped template is **offered** on a tenant's copy and never applied without a person
accepting it. This section's *“each new runbook is a week of work”* sizing is owed a correction and
`DEF-RBS-4275` carries it.

---

## 2 · The two kinds, and why the distinction is ENFORCED rather than promised

| | |
|---|---|
| **A Check reports. It cannot write.** | Runs against configuration or records and produces findings, each with a reason and the screen that fixes it. |
| **An Action writes, behind a gate.** | Queues a notice, applies a fee by rule, flags an account, raises a task. Dry-run first, approved as a batch, capped, stoppable mid-flight, idempotent per account per run. Money-bearing actions carry a second approval. |

⚠ **THE ONE DECISION THAT CARRIES THE MOST WEIGHT — AND IT IS THE REASON THIS MODULE IS SAFE TO
GIVE A TWO-PERSON UTILITY.** Report-only is a **capability the engine withholds**, never a promise
in a description. **A Check is CONSTRUCTED WITHOUT A WRITER**: the action ports are not bound, so
binding one to a Check is a **construction error, not a runtime refusal** (`BR-RBS-002`,
`TC-RBS-1`, first shown red on a Check with a port bound). A clerk pressing **Run** on a Check
knows with certainty that no customer can be affected.

**This is hard-won law 1 applied before the fact.** *"A comment claiming a guarantee is not the
guarantee."* A docstring saying *this runbook does not write* is a note; a constructor that has no
writer to call is the guarantee. Every other safety property in this module — the cap, the plan,
the gate, the stop — is a control on an Action; this one removes the capability entirely from two
thirds of the catalogue.

---

## 3 · What a runbook is made of — seven parts

| Part | What it declares | Example — the collections ladder |
|---|---|---|
| **Trigger** | Manual, a schedule in the tenant's timezone, or a platform event | Every Monday 07:00, tenant local |
| **Scope** | The set to walk, **resolved once per run and pinned** | Accounts with a balance past due and no plan in good standing |
| **Checks** | Ordinary code registered against the engine — **never a rules language** | Protected? Disputed? Notice already sent? Address deliverable? |
| **Actions** | A narrow allow-list, each needing its own permission | Queue the tier's notice; record what was sent |
| **Guards** | What it may never touch, whatever the checks say | Medical protection, active dispute, sample rows |
| **Gate** | Who approves, and at which point | Batch approval; a second one for the fee tier |
| **Caps** | The most it may do in one run, **refusing rather than truncating** | 400 notices |

**The full contract a registered runbook implements** adds four more declarations to those seven —
`category` (one home from a fixed list of sixteen), `parameters[]` (typed, eleven types),
`requires` (optionally one other Check, run first as its own run) and `report(run) → [Block]`
(composed from the twelve blocks and **frozen when the run closes**). The seven above are what a
clerk configures; the eleven are what a developer declares. **The full declaration lives in
[`12-the-contract.md`](12-the-contract.md), the twelve blocks and the components that draw them in
[`09-component-inventory.md`](09-component-inventory.md), the rules in
[`02-business-rules.md`](02-business-rules.md) and the columns in
[`03-field-map.md`](03-field-map.md)** — none of it is repeated here, and where this file and one of
those disagree, **the contract and the rules win and the divergence is a defect in this file.**

**Two acts only the ENGINE performs, and they are not ports.** Raising work items and writing audit
rows. A Check produces findings; the engine upserts them as work items when the run closes. **That
is how a Check can populate the work list and still be constructed with no writer** — and it is the
single most misread line in the source documents, which list *"raise a work item"* among the ports.
It is not one.

---

## 4 · The module map — seven tables, and it writes no other module's data

| Table | Holds |
|---|---|
| `runbooks` | One row per runbook available to the tenant — key, kind, category, origin, trigger, cap, gate, current version |
| `runbook_versions` | An immutable snapshot each time the definition changes |
| `runbook_runs` | One row per run — mode, trigger, parent run, status, pinned scope fingerprint, counts, the frozen report |
| `runbook_run_records` | One row per record examined: **the plan and then the outcome, in the same row** |
| `work_items` | Everything waiting on a person, whatever raised it — upserted by fingerprint |
| `cutover_plans` | A go-live plan, one per cutover |
| `cutover_plan_items` | Its tasks, some backed by a runbook, some purely human |

Every table carries `tenant_id` with row-level security **forced**, a uuid7 primary key and
created/updated stamps. Money is stored to **four** decimals and displayed to **two** (hard rule 2).

**There are exactly three routes to the database and no fourth.**

| Route | Who writes | What |
|---|---|---|
| **1 · The module's own seven tables** | the engine | definitions, versions, runs, pinned scope, run records, decisions, work items, cutover plans. A runbook's step code never writes these directly; it returns findings and the engine records them |
| **2 · The thirteen action ports** | an Action, through the engine, **after the gate** | one named service function in the owning module per port, each idempotent per record, each writing its own audit row with the runbook as actor. **A Check is constructed with none, so a write from a Check is a construction error** |
| **3 · Reads** | any runbook | through each module's selectors, under the tenant context with RLS forced. No raw SQL, no cross-tenant queryset |

### 4.1 · The thirteen ports — the whole list of what automation can do to a customer

⚠ **THIRTEEN, NOT FOUR.** The source's architecture section says *"a small allow-list … queue a
notice, flag an account, raise a work item, apply a fee"* and repeats *four* in five places. **It is
stale and it is wrong twice over:** the contract section of the same document lists thirteen, and
*raise a work item* is not among them because raising work items is an **engine act** (§3 above).
Anyone reading the architecture section alone will build four ports and put the work-item writer in
the wrong place.

| Port | Owning module | What it does |
|---|---|---|
| `queue_notice` | notifications | Writes a queue row; the dispatcher sends |
| `queue_receipt` | notifications | A receipt document to the queue |
| `apply_payment` | payments | Applies a landed payment by the allocation order |
| `post_credit` | payments | A credit to an open account |
| `raise_refund` | payments | A refund awaiting its own approval |
| `apply_fee` | billing | A fee by rule, behind the second approval |
| `record_match` | payments | A bank line matched to a deposit batch |
| `write_read` | metering | A validated meter-day as a read, source stamped |
| `apply_premise_change` | metering | One field on one premise, before-and-after kept |
| `suppress_channel` | customers | A contact channel marked undeliverable, dated |
| `flag_account` | customers | A flag with a reason |
| `flag_meter` | metering | *"Told about a leak on"* a date |
| `schedule_retry` | payments | A retry of a failed debit |

**A new runbook that needs a new port is adding a reviewed interface, not a custom write.**

### 4.2 · Seams, not clients — the part a builder is most likely to get wrong

Every read of another module is a **seam file this module owns** — `runbooks → customers`,
`→ metering`, `→ rating`, `→ billing`, `→ payments`, `→ ledger`, `→ notifications`,
`→ tenancy` (settings), `→ integrations` (a landed batch) — calling the owner's selector by name,
in process, under the tenant context. Every write is one of the thirteen port seams. **Every seam is
a row in the cross-module interface register, added in the same commit as the file.** No HTTP client
anywhere in the module; no import of another module's models. The pattern exists — billing carries
nine seams today — so a lane reaches for it rather than inventing a client
(`BR-RBS-039`, `TC-RBS-25`, an import census first shown red on a planted violation).

**Where a selector a runbook needs does not exist yet, the OWNING module adds it and the seam calls
it.** That inventory is a phase-1 task, done before the first Check is written, not discovered
during it.

---

## 5 · What this module deliberately REFUSES

| | |
|---|---|
| **REFUSED · a rules language** | Checks stay ordinary code registered against the engine. The moment a condition syntax appears, a workflow product starts growing inside a billing product and every future check becomes a support question about the syntax. |
| **REFUSED · a filter builder, and a step picker, for ANYBODY** | `BR-RBS-042` (PO 2026-09-06). **Nobody composes filter expressions — not a tenant, not us.** Inputs carry domains and that is the whole mechanism. And a tenant never arranges steps: **we** build runbooks from a library only we see. ⚠ **This module's own execution plan promised *“the step library, the filter builder”* as a tenant-facing wave `T` until 2026-09-06** — the library is real and stays, as an internal asset; the builder was never right. |
| **REFUSED · one scope abstraction** | Walking a configuration graph and querying 250 accounts are different jobs. A single selector interface across both would fit neither and would leak query concerns into the engine. Each runbook declares its own scope function; the resolved id list is pinned at run start. |

Two more closed vocabularies exist for the same reason and are stated as rules rather than as
preferences: **twelve result blocks** — a thirteenth needs three runbooks that cannot be drawn
without it (`BR-RBS-021`) — and **sixteen categories** — a seventeenth needs three runbooks that
fit nowhere else, and a category holding no runbook is **never drawn as a filter**
(`BR-RBS-024`, `BR-RBS-025`; a chip that filters to nothing is dead UI, hard-won law 2).

---

## 6 · The boundary with integrations — already ruled, and it is `BR-INT-054`

**PO ruling 2026-09-05, verbatim:**

> *"I want integration to just make the conenction nad manage the conenction, Runbooks will handle
> the logic , ETL and record udaptes, and we will abel to keep record, audit of it as part of
> runbooks."*

**Sharpened by the PO on 2026-09-06**, which added a fourth word to this side of the line:

> *"We want integration scope about building a conn crore , managing keys/secret, managing lifecycle
> of connect - while business logic , scheduling , processing we will take it in run book."*

⚠ *"conn crore"* is read as ***connection***; the words are recorded as they were said.

**So: integrations keeps exactly three things — (a) building a connection · (b) holding keys and
secrets · (c) the lifecycle of a connection. Business logic, scheduling and processing are
Runbooks'.** The test that decides every disputed case is one sentence and it is
`BR-INT-056`'s: **PURPOSE, NOT SHAPE.** Integration settings answer *"how do I talk to this vendor,
and am I allowed to right now?"* **Anything about what the data MEANS is the runbook's** — including
a value mapping that looks like configuration (`ACHCHECK` → *Bank transfer*) and what a vendor's
`429` or `401` means **for our processing**. The PO corrected that lane twice on exactly those two,
both times because it had sorted by shape.

**Four consequences this module inherits, stated rather than left to be inferred:**

1. **The scheduler is ours.** Deciding that *nightly* means the utility's own midnight, spreading
   tenants so they do not fire together, skipping a run that is still going, and declining a run a
   request budget cannot pay for are **scheduling**. ⚠ **The QUEUE and the WORKER are NOT the
   scheduler** and stay with integrations; Runbooks runs on them. **One scheduler, not two** — both
   integration fetches and runbook runs are job kinds on the one existing platform runner.
2. **A landed batch is where integrations stops and we start.** They authenticate, dedupe, persist
   raw and reply fast; the `apply` half is ours and may happen a second later (`BR-INT-058`). The
   reason is operational and is worth repeating so nobody folds the halves back together: **the
   vendor is waiting on our reply and will re-send if we are slow.**
3. **The run record splits in two.** `IntegrationRun` records *a connection authenticated, pulled a
   file and took three seconds* — lifecycle, theirs. `runbook_runs` records *what was decided about
   the 899 rows inside that file* — ours (`BR-INT-054`(3)).
4. ⏸ **`BR-INT-054` COMMISSIONS NOTHING AND NEITHER DOES THIS FILE.** PO 2026-09-05:
   *"right now notng to be done … we will handle CR 69 and Runbook together once CR70 is
   completed."* `OQ-INT-1727` — about three people-weeks of value mappings and per-item run results
   already shipped on the integrations side — **remains OPEN and is the PO's**, because it is a
   ruling colliding with signed, shipped work.

---

## 7 · The platform gap that blocks ACTING, and it must close before phase 2

⚠ **THIS SECTION SAID *"before phase 4"* UNTIL 2026-09-06.** Two Product Owner rulings that day re-cut the
phase order — *"once you have foundation I want to prioritise runbook related to integration first and then
rest"*, then *"For me integration related to accounting, payment provider, emails, GIS are important - over
other"*. **Every integration-driven runbook is an Action, and an Action cannot run before the acting half
exists, so the acting half is now PHASE 2.** The gap below did not change; **the date it has to close by
moved three phases earlier.** [`10-execution-plan.md`](10-execution-plan.md) §1 is the current order.

**An automated action has no identity today.** The audit table records who acted, and **a blank
actor means "a system job"** — so every automation in the product is indistinguishable from every
other. Before the first Action runbook writes anything, **a runbook needs a first-class actor
identity carrying its NAME and its VERSION**, and it must never borrow a staff member's login, or a
person will appear to have personally sent 812 letters at 07:00 on a Monday.

This is not a nicety and it is not hardening for later. Hard rule 7 says every money action writes
`audit_log`; `BR-RBS-015` says the runbook is the audit actor, named and versioned; `TC-RBS-12` is
first shown red on **the current platform behaviour** — actor left null. **Phase 1 does not need it**,
because nothing in it writes. **Phase 2 cannot start without it — and neither can phases 3 or 5**, because
every runbook in both of them is an Action. **It is the single largest schedule risk in the plan.**

A second dependency sits beside it and is different in kind: **a delivery provider must be connected
before phase 2's live half means anything to a customer.** The notification queue fills and nothing
leaves the building until one is — which is why the word on every result screen is **Queued**, never
*Sent*, and why the copy must not claim otherwise.

---

## 8 · Two questions the source left open on phase 1, DECIDED HERE

⚠ **These are OURS under CLAUDE.md law 13 and no `OQ` is minted for either.** Neither collides with
a signed rule, neither moves a ❄️ FROZEN B4/B5 figure, and neither is a fact only the Product Owner
holds. Both are recorded with their reasoning **so they are visible to overrule** — which is what a
judgment call in the decision log is for, and the alternative is a question that manufactures
inconsistency by being asked twice.

### 8.1 · *Can we bill?* produces **ONE VERDICT PER SERVICE, ROLLED UP TO A TENANT VERDICT**

*(the source's open decision 6, "one verdict for the tenant, or one per service?")*

**Decided: one verdict per enabled service, plus a tenant verdict that is the worst of them.**

**Why.**

1. **The thing being checked is per-service, six times out of ten.** Read runbook 1's own steps: *"every
   enabled **service** has a unit and a basis"* · *"a region on every **service point**"* · *"every plan
   has a version covering today"* · *"blocks cover zero to the highest usage seen"* · *"bill and notice
   templates exist for **every service**"* · *"every charge code and tender maps to an account"*. A
   verdict that collapses eleven possible services into one word throws away the axis the data is
   already organised on.
2. **A single verdict cannot show progress, and showing progress is the whole point of the screen.**
   A two-service utility that fixes water would watch the verdict go from *No-go* to *No-go* and
   learn nothing. **Sewer must stay visibly red while water goes green.** Journey `J-RBS-1` asserts
   the blocker count falling from 3 to 2; per-service verdicts are that same assertion one level up,
   and without them the run header is the only place movement is legible.
3. **It costs nothing in the contract and adds no block.** The `Verdict` block draws the tenant
   verdict; the per-service verdicts are a `Breakdown` block grouped by service over the same run
   records — both already in the twelve, so `BR-RBS-021` is untouched. The `Records` block already
   carries a Service column.
4. **It matches how the product already decides what exists.** The tenant service-enablement table
   says which of the eleven services are on. A verdict that ignores it would report on services the
   tenant does not sell, and a verdict that averages across it would let a disabled service hide a
   live one.

**The rollup rule, written out so two implementations cannot disagree:** every step is either
*per-service* or *tenant-wide*. Steps 1, 3, 4, 5, 7, 9 and 10 are per-service; steps 2, 6 and 8 are
tenant-wide (reference data; the account → unit → premise → address chain; the read window). **A
service's verdict is the worst outcome among its own steps. The tenant verdict is the worst among
the enabled services' verdicts and the tenant-wide steps.** Blocker anywhere → **No-go**. Warnings
only → **Warn**. Nothing found → **Go**.

### 8.2 · The minimum object set before a bill is permitted is **EXACTLY RUNBOOK 1'S TEN STEPS**

*(the source's open decision 7, "the minimum object set before the product permits a bill at all")*

**Decided: the ten steps ARE the minimum object set. No second list is written anywhere.**

| # | Step | What must exist |
|---|---|---|
| 1 | Services and units | Every enabled service has a unit and a basis |
| 2 | Reference data | Number series, holidays, account types present |
| 3 | Tax | A region on every service point |
| 4 | Plans in force | Every plan has a version covering today |
| 5 | Rate coverage | Blocks cover zero to the highest usage seen in twelve months |
| 6 | Account chain | Account → unit → premise → address, unbroken |
| 7 | Meters | Every metered unit has a meter, a multiplier and a unit |
| 8 | Reads and windows | One read per meter; the read window closes before bill day |
| 9 | Documents | Bill and notice templates exist for every service |
| 10 | Books | Every charge code and tender maps to a ledger account |

**Why this rather than a separate list.**

1. **A second enumeration of the same fact is how this repository breaks.** Two lists of the minimum
   set would disagree within a week — the catalogue numbering did, the screen ids did, and B14's
   rule count has now been wrong five times. Hard-won law 5 is the same instinct: one source, derive
   views on demand, never commit a second copy.
2. **The steps are already ordered by the chain a bill actually needs** — a service, a rule, a
   customer, a meter, a read, a document, a ledger account — so **the first failure is always the
   earliest one in the chain, which is the one to fix first.** A separate list would have to
   re-derive that order and would get it wrong.
3. **The runbook that reports the answer and the rule that defines it are then the same code.**
   Journey `J-RBS-2` asserts that the refusal sentence on screen is *the engine's own, not a second
   implementation's*; this decision is that property applied one layer up.
4. **Blocker versus warning is decided by scope, not by step.** A step failing at the **service**
   level is a **blocker** for that service — it cannot bill at all. A step failing on **some records
   only** is a **warning** naming those records — those accounts cannot bill and the rest can. Step
   8 is normally a warning for exactly this reason: a missing read is per account and is the
   pre-bill sweep's daily job (runbook 3), not a configuration fault.
5. **What the minimum deliberately EXCLUDES, and why each exclusion is safe.** A delivery provider
   (a bill can be produced and held; nothing about producing it needs a channel — and the notice
   templates of step 9 are documents, not a connection) · a payment method or a tender beyond step
   10's mapping · a collections ladder · a cutover plan · the customer portal. **None is needed to
   price and issue one bill**, and putting any of them in the minimum set would block go-live on
   work that has nothing to do with billing.

---

## 9 · Pack status (2026-09-06)

**41 stories · 5 epics · 8 screens · 2 renderers · 7 tables · 13 ports · 12 result blocks · 16
categories (11 in use) · 18 endpoints · 6 refusal message keys · 39 business rules · 25 test cases ·
3 journeys.**

⚠ **THE PHASE ORDER WAS RE-CUT ON 2026-09-06 AND THE EPIC NUMBERS NO LONGER TRACK IT.** The epics are
**not renumbered** — renumbering five epics would move every citation of them at once. Read the phase
column, not the epic number.

| Epic | Phase (from 2026-09-06) | Stories | The outcome a utility can see |
|---|---|---|---|
| [`EP-RBS-01`](06-epics/EP-RBS-01-can-we-bill.md) | **1 · The foundation, part one: it can look** (waves `A`–`E`) — unchanged | 001 · 002 · 003 · 015 · 016 · 018 · 038 · 040 · 041 | A clerk presses one button and sees exactly what is stopping billing, each finding with a button to the screen that fixes it. **Nothing can be written; the engine has no writer bound.** |
| [`EP-RBS-04`](06-epics/EP-RBS-04-it-acts-and-you-approve.md) | **2 · The foundation, part two: it can act** (waves `L` `M` `N`) — **was phase 4** | 010 · 011 · 012 · 013 · 014 | A clerk sees exactly what would be sent to 812 accounts and cannot yet send it; then, when it goes live, about **33 hours a month** return and every notice can name the rule that sent it. |
| [`EP-RBS-05`](06-epics/EP-RBS-05-the-rest-of-the-catalogue.md) | **3 · The integration runbooks** (waves `O` `P` `Q′`) — **this epic now spans TWO phases** | 017 · 022 · 026 · 032 · 034 | A file lands and the work starts itself. The four runbooks serving the areas the Product Owner named — **accounting · payment provider · emails · GIS**. |
| [`EP-RBS-02`](06-epics/EP-RBS-02-prove-it-on-their-data.md) | **4 · Prove it on their data, and the scheduled Checks** (waves `F` `G`) — **was phase 2** | 004 · 005 | A utility sees its OWN accounts produce correct bills before go-live — 25 cells, one per plan × service mix × cycle. The go-live and sales artefact. |
| [`EP-RBS-03`](06-epics/EP-RBS-03-it-runs-without-anyone.md) | **4 · Prove it on their data, and the scheduled Checks** (waves `H`–`K`) — **was phase 3** | 006 · 007 · 008 · 009 | Problems arrive BEFORE the bill run instead of during it, in one list a clerk opens each morning. Go-live has evidence attached to it. Month-end exceptions arrive assembled. |
| [`EP-RBS-05`](06-epics/EP-RBS-05-the-rest-of-the-catalogue.md) | **5 · The rest** (waves `R′` `S` `T`) | 019–021 · 023–025 · 027–031 · 033 · 035 · 036 · 037 · 039 | Roughly **20 more hours a month**. Each new runbook **re-uses about 2 shared steps and writes about 4.7 of its own**, and arrives with **no new screen** — it renders on the two existing renderers. ⚠ **This cell read *“a week of work rather than a project”* until 2026-09-06**; the hand count in [`14-step-library.md`](14-step-library.md) puts the sharing at **20.8%** (36 of 173 instances, 137 distinct steps, 89% of them singletons), which is a fifth of the step-writing rather than a third. `DEF-RBS-4275` carries the fan-out. |

⚠ **THE PRICE OF THE RE-CUT, NAMED HERE TOO SO IT IS NOT ONLY IN THE PLAN: `EP-RBS-02`'s coverage grid —
the go-live artefact and the sales artefact at once — lands three phases later than it would have.** And the
safety property the old order had (every Check first, an Action last) is replaced by one thing: **wave `M`,
a full cycle dry in production with a written go/no-go, which stays exactly where it is between `L` and `N`.**

**Execution plan:** [`10-execution-plan.md`](10-execution-plan.md) — the five phases as waves, every
wave ending in a clicked walkthrough of the running product and a version bump.
**Stories index:** [`05-user-stories.md`](05-user-stories.md).
**The rest of the pack, landed alongside this one:** [`02-business-rules.md`](02-business-rules.md)
(the 39 rules) · [`03-field-map.md`](03-field-map.md) · [`04-flows.md`](04-flows.md) ·
[`07-endpoints.md`](07-endpoints.md) (18 routes, 6 refusal keys) ·
[`08-screen-layouts.md`](08-screen-layouts.md) · [`09-component-inventory.md`](09-component-inventory.md)
· [`11-catalogue/`](11-catalogue/) (one card per runbook, `RB-101`–`RB-135`) ·
[`12-the-contract.md`](12-the-contract.md). ⚠ **The catalogue runs to 34 runbooks while this pack's
five phases cover the 21 the specification DEFINES** — `RB-133`, `RB-134` and `RB-135` (budget-billing
re-level, storm mass-send, service-request chase) are *later*, not phase 5, and each says what it waits
on. ⚠ **THE ACCOUNTING RUNBOOK IS NO LONGER MISSING — IT IS `RB-136`, AND THIS PARAGRAPH SAID THE
OPPOSITE UNTIL 2026-09-06.** It read: *"nothing in this catalogue composes the ACCOUNTING FILE's
contents … the card is not invented here — a runbook that composes a general-ledger export needs a
fourteenth port, which is a reviewed interface change and a rule change."* **The Product Owner split
that blocker and the split dissolves it** (decision log, 2026-09-06, *"THE ACCOUNTING EXPORT IS TWO
THINGS"*): a runbook that **pushes** a file to an accounting system needs the fourteenth port and is
still a change request nobody has raised; a runbook that produces a file **a clerk downloads and
uploads** needs nothing new, because **producing a download is not a write to a business record** and
`downloads` is one of the twelve blocks already built. The PO asked it in one sentence — *"utility
clark can down the file and upload it in Quickbook if integration is not yet enabled, isnt it?"* —
and the answer is yes. **The file's six columns were ruled the same day** (*date · account code ·
description · debit · credit · reference*), and the runbook is [`RB-136`](11-catalogue/RB-136-accounting-export.md),
a **Check** in the Finance category whose input is the accounting month. What it still owes is one
download ADDRESS: the two result files carry the nine RECORD columns, which hold no date and no
account code, so a general journal cannot be expressed in them (`DEF-RBS-4312`). ⚠ **The general
lesson, which is why this amendment is this long: a capability was reported absent because the lane
looked for it in the shape it expected — an outbound PORT — and never looked for the shape it already
had, a DOWNLOAD.**
**Wireframes:** [`wireframes/`](wireframes/) — every frame carries its `RBS` code on its own title
bar and its build sheet beside it, derived from the frame's own markup. **A screen is finished when
a screenshot of it matches the sheet region by region, not when its tests pass** (hard-won law 6).

### The screens — eight, and the count does not grow with the catalogue

| Screen | What it is | States drawn | Phase |
|---|---|---|---|
| `RBS-001` | Runbooks home — the landing screen | Populated · first visit · a run in flight | 1 |
| `RBS-002` | Runbook templates — the library we ship | Gallery · template detail before adding | 1 |
| `RBS-003` | My runbooks — the configured list | All · filtered to Actions · empty | 1 |
| `RBS-004` | Runbook detail — seven tabs | Overview · Steps · Scope · Guards · Limits · Runs · Activity | 1 |
| `RBS-005` | Run wizard — six steps | Scope · Checking · Review · Approve · Applying · Done · cap refused · check failed | 1 (Check path) · **2** (gate) |
| `RBS-006` | Run result — a past run reopened | Clean · with failures · stopped part-way | 1 |
| `RBS-007` | Work list | Populated · all clear | **4** |
| `RBS-008` | Run history — across every runbook | Populated | **4** |

⚠ **`RBS-004` AND `RBS-006` ARE RENDERERS, NOT PAGES.** `RBS-004` draws any runbook's definition;
`RBS-006` draws any run's frozen report from the twelve blocks. **Twenty-one runbooks are still
eight screens** — the per-runbook instances are `RBS-004-R1`…`RBS-004-R27` and
`RBS-006-R1`…`RBS-006-R22`, and what a lane builds is *twelve components, one renderer, twenty-one
report functions*. **This is why phases 3 and 5 add no screen.**

⚠ **GRAMMAR, AND IT NEEDS A LOOKBEHIND AS WELL AS A LOOKAHEAD.** The module code is also `RBS`, so a
screen is `RBS-001` while a rule is `BR-RBS-001`, a story `US-RBS-001` and a test `TC-RBS-1`. The
search pattern for a **screen** is **`(?<![A-Z]-)RBS-\d{3,5}(?!\d)`** and both assertions are
load-bearing: without the lookbehind a screen search returns rules; without the lookahead it
truncates, which is exactly how `OQ-\d{3}` returned `OQ-119` for `OQ-1190` and put a stub against
the wrong question for two days (`DEF-2804`). ⚠ **The bare `RBS-001`…`RBS-006` ERROR CODES in the
specification are a collision and are DROPPED** — this repo has no numeric error codes; every
refusal is a message key, `runbooks.refusal.<name>`, which `G15` and `G32` already police.

### The scale this is built for

**The ICP is 40,000 accounts — T7 (≤3,000) · T6 (3–10K) · T5 (10–40K), all three in scope.**
⚠ **The market study's 60,000–80,000 figure is an ILLUSTRATION and was ruled so on 2026-09-06** —
PO verbatim: *"it is an example so we can understand the impact - you can keep the note ; nothing to
act right now"*. **Nothing in this module is scoped to it.** The four commitments that wait on an
80,000-account change request (queue-depth worker scaling, monthly partitions with a read replica,
partitioned interval storage in metering, a synthetic 80,000-account fixture) are **kept as written
and marked *not scoped***; they are the worked impact of a tier we are not building for. What DOES
bind is `NFR-3` and `NFR-5`: **every list this module serves pages on the server, and no table,
index or code path enforces a maximum account count per tenant.**

---

## 10 · What step 0 found, recorded rather than fixed silently

* ✔ **RESOLVED THE SAME DAY — THIS MODULE'S CHANGE REQUEST IS `CR-075`, NOT `CR-076`.** What
  step 0 found was real: the decision log cited `CR-076` while `11-change-requests.md` said the
  next free number was `CR-075`, and the CR file did not exist. **The cause was a mis-read, not a
  missing allocation** — a grep for the next free number matched the register's own *"Next free
  number: `CR-075`"* line and took it for a number already spoken for. `CR-075` is allocated,
  written and in the register; the four decision-log citations were corrected in place; the
  register's pointer now reads `CR-076` as the next free. **The finding is kept rather than
  deleted, because a step-0 catch that worked is worth more in the record than a tidy page.**
* **The source's architecture section says the module owns FOUR tables and has FOUR ports.** The
  data model has **seven** tables and the contract has **thirteen** ports, and *raise a work item*
  is an engine act rather than a port. Corrected throughout this pack; §3 and §4.1 say so out loud
  because the wrong version is the one a reader reinvents.
* **The source numbers screens `S147`–`S154` and the module `apps/operations`.** Superseded by the
  PO ruling of 2026-09-06 and by this pack respectively. The wireframe build sheets already carry
  the `RBS` codes and say which `S` number each replaced.
* **The specification's phase list has eight increments (1a–1d, 2a–2c, 3).** This pack has **five**,
  at the Product Owner's request, each delivering an outcome, with the open questions pushed into
  phases 4 and 5 — **that placement half was overtaken by the 2026-09-06 re-cut: three of the six now
  arrive in phase 2, because the wave they hang on moved and they came with it, and not one of them blocks
  anything.** The mapping is printed in [`10-execution-plan.md`](10-execution-plan.md) §1 and
  no story is lost or duplicated by it.
* **Three of the nine "rulings" on the market page are NOT the Product Owner's** — the sixteen
  categories, *deterministic first*, and the six-step product journey are that page's own decisions
  (decision log 2026-09-06). They are carried here as ours, visible to overrule, and are not quoted
  as PO rulings anywhere in this pack.

**Hazards written into the documentation, so a lane meets them before they cost a cycle:**

* `06-backend/apps/runbooks/` is a **new** module: its `AppConfig`, its first migration and its RLS
  `FORCE` migration land together, and the seven tables are anchored in the schema brief **before**
  `0001` is written.
* `07-frontend/src/features/runbooks/` joins `07-frontend/src/styles/route-b-migrated.txt` **in its
  first frontend commit** — measured 2026-09-06, that file is **3,241 lines and holds zero runbooks
  paths** — or every Tailwind utility in this module renders as **nothing at all** while `tsc`,
  eslint and every `toContain("flex")` assertion pass, because the class **is** in the DOM (B14 rule
  21, `DEF-974`). **The migration clause is PER FILE**, so this is a numbered task, not a tidy-up.
* **Eight pieces of shared UI the twelve blocks need do not exist**, verified absent from
  `07-frontend/src/components/` on 2026-09-06: `VerdictBand` · `Chain` · `ContributionBars` ·
  `OutcomeCard` · `SettingsOwnedField` · `PercentCell`, plus the `Records` block's **sparkline cell**
  and its **grid display mode**. **All eight are phase-1 work** — the coverage grid *is* the grid
  mode, so `EP-RBS-02` cannot be built without them. ⚠ **After the 2026-09-06 re-cut the coverage grid is
  in PHASE 4, three phases after the components it needs**, which makes deferring them look cheaper and
  makes the day it bites further away. They stay phase-1 work for exactly that reason.
* **There is no percent formatter in the front end at all**, and **no percentage in any of the 75
  build sheets is drawn at two decimals** — while hard rule 2 stores percentages to **6** and
  displays them at **2**. The rule wins; the divergence is stamped in `08-screen-layouts.md`.
* **A build sheet is the region list, not the whole screen: 39 of the 75 are fragments with no page
  head** (36 carry one, 39 do not). A lane building one of those literally would ship a headerless
  page; the head, the shell, the toolbar and the pagination footer come from B14 and the shared kit.
* **The savepoint-per-record behaviour is proved on real PostgreSQL or it is not proved** — the
  default suite hardcodes in-memory SQLite, which has no aborted-transaction state, so the naive
  `try/except IntegrityError: continue` passes the whole suite green on every machine and loses the
  run the first time a real row is refused in production (hard-won law 14, `TC-RBS-5`, `RB-038`).
* **A hold written into this module carries the test that fires when the hold expires, in the same
  commit** — assert the destination by address and by the screen id it opens. Phase 5's runbooks
  arrive behind holds on `RBS-002`, and the portal's front page has already shown what a hold with
  no such test costs (`DEF-CWP-3925`: two working doors out of eight, every check green).
