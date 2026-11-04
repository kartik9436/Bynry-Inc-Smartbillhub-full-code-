# 17 · Runbooks — the step library

**The deduplication, done. 173 step instances across 26 runbooks reduce to 137 distinct steps
— not to the 80–100 that has been quoted since 5 September, and 89% of them are used by
exactly one runbook.** This file is the measurement, the method that produced it, and the
correction.

> ⚠ **FILENAME.** This was commissioned as `13-step-library.md`. `13-` was taken by
> `13-selector-inventory.md` earlier the same day, and **`DEF-RBS-4249` is already on the
> register for exactly that mistake in exactly this folder** — *"eleven docstrings and B2 r25
> point at `17-runbooks/05-selector-inventory.md`, a number already taken by
> `05-user-stories.md`"*. Filing a second collision the day the first was filed is not a
> transcription choice, so this is `14-`. Nothing else moved.

---

## 0 · What this implements, and what it does not touch

**PO ruling, 2026-09-06** (decision log, newest row), verbatim:

> *"See I dont mind your design - the problem is this is new concept for everyone - I dont think
> Utility admin will able to configure these using the 150 bricks that we give - you can keep all
> these bricks and buld ready to use runbooks - when we later change it will be small er changes
> for us"*

The PO did not reject the library. **They moved who touches it.** The steps below are an
**internal engineering asset**: they are how *we* build runbooks from wave `C` onward. **A utility
admin never sees a step list, never orders one, never composes anything.** A tenant sets inputs
and clones — the second ruling of the same day, verbatim: *"you cannot change the logic those are
finate steps ; you can change the input to logic"*.

> ⚠ **`BR-RBS-042` IS NAMED AS *(new)* IN THAT DECISION-LOG ROW AND IS NOT IN
> `02-business-rules.md`, WHICH STOPS AT `BR-RBS-041`** — checked against the tip at `1b33c8e0`.
> That is the fan-out CLAUDE.md warns about — *"closing a question is a fan-out, not a status
> edit"* — and a lane citing `BR-RBS-042` today is citing the decision log, not a written rule.
> It is named here as a pointer and quoted from nowhere.

⚠ **THE NUMBER IN THAT ROW WAS OURS, NOT THE PO'S — WHICH IS WHY CORRECTING IT IS NOT A RE-SIGN.**
The row's *"~150 step instances reduce to ~80–100 distinct steps"* is this repository's own
estimate, written inside a row whose ruling is about **adoption**. Nothing signed, frozen or
finance-touched moves when the estimate is replaced by a count. Per HUMAN-GUIDE §6 a signed
figure would need a re-sign; an unsigned estimate needs a measurement, and this is it.

**Not touched by this file:** no card in `11-catalogue/` is edited, no rule is amended, no
question is closed. Where a card and this file disagree, **the card is the source and this file
is the reading of it**, and every such disagreement is written out in §8.

---

## 1 · The arithmetic, and it is a count rather than an estimate

| | Figure | How it was got |
|---|---|---|
| Runbook cards in `11-catalogue/` | **34** | `RB-101`–`RB-135`, no `RB-107` |
| Cards that declare steps | **26** | `RB-101`–`RB-127`, no `RB-107`. The eight *named only* cards (`RB-128`–`RB-135`) carry no `## Steps` table at all |
| **Step instances before** | **173** | every row of every `## Steps` table, counted |
| **Distinct step names before** | **172** | the only name used twice is *"Raise the rest as work items"* (runbooks 14 and 20) |
| **Distinct steps after this pass** | **137** | §7 |
| Step-writings removed by sharing | **36** | 173 − 137 |
| **Reduction** | **20.8%** | 36 / 173 |
| Steps used by **two or more** runbooks | **15 of 137** — **11%** | §4 |
| Steps used by **exactly one** runbook | **122 of 137** — **89%** | §5 |
| Step instances landing on a shared step | **51 of 173** — **29%** | |
| Average steps per runbook | **6.7** | 173 / 26 |
| Average steps a *new* runbook has to write | **≈ 4.7** | 122 / 26 — see §5 |

### The claim this supersedes, quoted and corrected

> *"the 21 runbooks hold about 150 step instances; after removing repeats the library is roughly
> 80 to 100 steps, many shared."*

**Four things in that sentence are wrong, and the last one is the one that matters.**

| The claim | The count |
|---|---|
| **21** runbooks | **26** carry steps, of **34** cards |
| **about 150** step instances | **173** |
| **roughly 80 to 100** distinct steps | **137** |
| ***many shared*** | **89% are used once.** Fifteen steps carry all of the sharing |

⚠ **AND THE ROW'S OWN WORKED EXAMPLE DOES NOT SURVIVE A GREP.** The decision-log row offers
*"`Check nothing is past due today` is written once and used by three runbooks"*. That step
appears in **one** runbook's step table — `RB-115` step 3 — and in no other. The phrase *past
due* appears in the step tables of exactly two cards: `RB-108` (steps 1 and 3, which **find**
past-due accounts, the opposite question) and `RB-115`. **It is a singleton, and it was the
sentence chosen to demonstrate the sharing.**

### ⚠ 80–100 is not reachable by any cutting of these cards

**A projection, clearly labelled as one, because the obvious objection to 137 is "you cut the
steps too coarsely."** §3's granularity rule keeps one card step to one library step, so twelve
card steps that bundle two jobs each (§8.B) stay whole. Re-cut every one of them and roughly
**nine** further merges become available — `21.1` splits into a pin plus a roll-up, `3.8` into a
pick plus a pricing, `26.5` into a fee plus a notice, and so on. That lands near **128**, not
near 100. **The gap between 137 and 80 is not a granularity argument. It is that the sharing
was assumed and never counted.**

---

## 2 · The verdict on the shared-step model — supported as architecture, not as sizing

**Both halves are stated, because a file that reported only the disappointing half would be as
useless as the estimate it replaces.**

**SUPPORTED.** The fifteen shared steps are not a scattering of coincidences — they are **the
skeleton every Action walks**: resolve the scope → pin the landed batch → match it to ours →
exclude the guarded → act through a port → queue the notice → write the audit row → raise the
remainder as work items. Seven of them serve three or more runbooks and **every one sits on the
money path or the write path.** Writing those once, testing them once and fixing them once is
worth doing on its own terms, and it is exactly what the PO asked for in *"when we later change
it will be small er changes for us"*.

**NOT SUPPORTED.** The **sizing** built on top of it is not there:

* the execution plan's *"each new runbook is a week of work rather than a project"*
  (`10-execution-plan.md` phase 5, and repeated in `01-overview.md` and `CR-075`) rests on a
  library a new runbook can be assembled from. **A new runbook re-uses about 2 steps and writes
  about 4.7 of its own** — the assembly saves a fifth of the step-writing, not a third and not
  most of it;
* *"roughly a third of the step-writing gone"* is **20.8%**;
* **two runbooks share nothing at all with anything** — `RB-105` *Abnormal readings* (8 steps)
  and `RB-118` *Vacant premises with usage* (6 steps). Fourteen steps, no reuse, in either
  direction. A library cannot make either of them cheaper.

**What that changes, in one sentence:** keep composing from shared steps for the **blast-radius**
reason in §6, and **re-size phase 5 on 4.7 new steps per runbook rather than on a library a
runbook can be assembled out of.** The estimate is `10-execution-plan.md`'s to correct; this file
does not edit it (a sibling lane is in that file today) and `DEF-RBS-4275` carries the fan-out.

---

## 3 · How the pass was done — the four rules, so it can be re-run and argued with

**The merge test is the one already ruled:** *a step is shared only when a second runbook needs
EXACTLY it, unchanged. If it needs adapting, it is two steps that look alike — say so and keep
them apart.* Applied, that becomes four rules, and every one of them cost merges:

1. **MERGE ON THE JOB, NEVER ON THE NAME.** 172 of 173 names are unique, so a name-based pass
   returns 172 and learns nothing. Conversely the one repeated name (*"Raise the rest as work
   items"*, runbooks 14 and 20) is a genuine merge — and so is runbook 21's *"Raise exceptions as
   work items"*, which does not share a word of its name with either.
2. **EVERY DIFFERENCE MUST BE THE VALUE OF A DECLARED INPUT.** That is the PO's own model —
   *"you can change the input to logic … this way, we control the inputs however process remain
   same"*. A different connection, subject, template, tolerance, threshold or key ladder is an
   input. **A different rule, a different normalisation, or an extra job is not**, and that is
   what *needs adapting* means.
3. **ONE CARD STEP RESOLVES TO EXACTLY ONE LIBRARY STEP.** A library step is never half a card
   step. Two reasons, and the second is the load-bearing one: splitting a card step is a hair's
   breadth from inventing one, and **a step is drawn on screen** — `RBS-006`'s Chain block puts
   one cell per step (`RB-101` draws *"a ten-cell chain"* for its ten steps), so re-cutting a
   card's steps re-cuts a shipped screen. That is a change request, not a deduplication.
   ⚠ **The corollary: one runbook may use one library step TWICE**, and one does — runbook 10
   matches on two key tiers in steps 2 and 3, both `RS-SYN-02`.
4. **A SHARED STEP HAS ONE MODE.** `BR-RBS-023`: *"a set-mode step runs once over the pinned set;
   a per-record step runs once per subject in its own savepoint; **a step declares which**"*. A
   step that declares its mode cannot be *exactly* a step that declares the other one. This rule
   alone kept `1.5` and `3.4` apart (§8.A).

**What was refused, deliberately:** no step was invented that no card describes; no two steps
were merged to improve the number; no card was adjusted. **An honest 137 beats a manufactured 90**
— and the whole reason this pass exists is that the last number was asserted rather than counted.

---

## 4 · The steps used by three or more runbooks — ranked

**This is where a fix pays for itself most, and where a mistake spreads fastest. It is the same
list for both reasons** (§6).

| Rank | Step | Runbooks | Which |
|---|---|---|---|
| 1 | **`RS-PLT-01` Resolve the declared scope into the pinned set** | **7** | 8 · 12 · 13 · 15 · 17 · 25 · 27 |
| 2 | **`RS-SYN-01` Pin the landed batch from the declared connection** | **6** | 10 · 11 · 14 · 20 · 22 · 26 |
| 3 | **`RS-ACC-01` Queue the notice** | **6** | 8 · 11 · 15 · 17 · 25 · 27 |
| 4 | **`RS-SYN-02` Match the pinned items by the declared key ladder** | **4** *(5 instances)* | 10 ×2 · 14 · 20 · 26 |
| 5 | **`RS-BIL-02` Price the pinned set through the real engine** | **3** | 16 · 23 · 24 |
| 6 | **`RS-BIL-03` Compare two bills line by line** | **3** | 4 · 16 · 23 |
| 7 | **`RS-SYN-03` Raise the remainder as work items** | **3** | 14 · 20 · 21 |

**And the eight used by exactly two**, which complete the shared set — there are no others:

| Rank | Step | Runbooks |
|---|---|---|
| 8 | **`RS-FIN-01` Tie two money totals within a declared tolerance** *(4 instances)* | 2 · 9 |
| 9 | **`RS-COL-01` Exclude records under a protection or a dispute, as at now** | 8 · 12 |
| 10 | **`RS-BIL-01` A plan is in force for the whole period** | 3 · 6 |
| 11 | **`RS-RDS-02` Every subject has a read for the period, inside the window** | 3 · 6 |
| 12 | **`RS-RDS-01` Run the read-validation rules over the reads** | 3 · 21 |
| 13 | **`RS-ACC-02` Find the break in the account chain** | 1 · 19 |
| 14 | **`RS-BIL-20` Group the records by a declared key and count each group** | 16 · 24 |
| 15 | **`RS-PLT-02` Write the audit row naming the runbook and its version** | 8 · 25 |

**Which runbooks re-use most:** 8 (4 of its 6 steps are shared) · 3 (3 of 8) · 10, 14, 16, 20, 25
(3 each). **Which re-use nothing: 5 and 18.**

---

## 5 · The singletons — 122 of 137, and this is the finding

**A library of singletons is not a library.** 122 steps are used by exactly one runbook; that is
**89% of the library and 71% of the instances**. They are not evenly spread — these ten runbooks
account for **63** of them, and the first six for 42:

| Runbook | Steps | Of which used only here |
|---|---|---|
| 1 · Configuration check | 10 | **9** |
| 12 · Disconnect eligibility | 8 | **6** |
| 5 · Abnormal readings | 8 | **8** |
| 9 · Month-end completion | 9 | **7** |
| 4 · Why is this bill higher? | 7 | **6** |
| 19 · Data hygiene | 7 | **6** |
| 6 · Why did this account not bill? | 7 | **5** |
| 13 · Payment trace | 6 | **5** |
| 18 · Vacant premises with usage | 6 | **6** |
| 22 · Undeliverable contacts | 6 | **5** |

**And the pattern in them is worth more than the count: the singletons are the QUESTIONS and the
shared steps are the MACHINERY.** *Is there a tax region on every service point*, *is this meter
stuck*, *did the weather stop this today*, *does the sub-ledger tie to the control account* — each
is a different question about a different table, and no amount of parameterisation makes one of
them into another. What repeats is the run's skeleton: resolve, pin, match, guard, act, queue,
audit, raise.

⚠ **THAT IS AN ARGUMENT FOR BUILDING THE SKELETON ONCE AND AGAINST EXPECTING THE QUESTIONS TO
COLLAPSE.** A lane sizing phase 5 from *"the library"* will be wrong by roughly four steps per
runbook. A lane building the skeleton once will be right, and will get the §6 payoff.

---

## 6 · The risk and the payoff are the same fact, so they are written together

**A fix to a shared step lands in every runbook using it — and breaks them just as fast.**

`RS-ACC-01` is queued by six runbooks. A wrong quiet-hours read in it is one bug in one function
and it is **six runbooks sending at 03:00**. `RS-PLT-01` is the first step of seven runbooks: get
the pinning wrong and `BR-RBS-009` (*scope is resolved once and pinned*) fails everywhere at once
— an account that becomes past due mid-run gets acted on, in seven places, with every count still
agreeing. `RS-SYN-02` decides which of our records a landed **payment** belongs to; it is the same
function that decides which premises a parcel belongs to.

**So, three obligations, and they are cheap only if they are written in the same commit as the
step:**

1. **A SHARED STEP CARRIES ITS OWN TESTS**, at the step, not only through the runbooks that use
   it. A step tested only through runbook 8 is a step whose runbook-27 behaviour nobody asserts.
2. **A CHANGE TO A SHARED STEP MUST NAME WHICH RUNBOOKS IT MOVES**, in its commit message and in
   its decision-log row. The *Runbooks* column of §7 is the list to read; keeping that column
   true is part of changing a step, not a follow-up.
3. **THE TENANT-FACING HALF IS ALREADY RULED AND IS NOT THIS FILE'S TO RESTATE.** `BR-RBS-038`:
   *"a change to a shipped template is offered on a tenant's copy and never applied without a
   person accepting it"*. A shared-step fix reaches a tenant's runbook **as an offer**, never
   silently. ⚠ **What `BR-RBS-038` does NOT cover is the half above** — it governs what a tenant
   sees, and says nothing about a lane changing a step under six runbooks in our own tree. That
   half has no rule and no gate today; it has this section.

---

## 7 · The library — 137 steps, grouped by the sixteen categories

**How to read a row.** *Reads* names the module the step reaches through the runbooks module's own
seam (`BR-RBS-039` — never an HTTP client, never another module's models). *Inputs* are the
runbook's declared parameters and scope rows; **`S` marks one that lives in Settings and is
read-only to a tenant** (`RBR-03`, `RB-021` — policy is never duplicated on a card). *Port* is one
of the **thirteen** (`12-the-contract.md` §6); a Check holds none, **enforced at construction**
(`BR-RBS-002`).

**The category is the one the step's SUBJECT lives in**, per the brief's rule — a step used across
categories is homed with the thing it acts on and its row names the others. ⚠ **The category is
*Premises*, not *Service points*** — decision log 2026-09-06, *"category names use the product's
OWN existing word wherever the product already has one"*. **Work, Customer portal and Business
hold no step**, because no defined runbook acts on their subjects; that is an absence, drawn as
one.

### Platform — 9 steps · owning module `tenancy`

| Step | Reads | Inputs | Answers, per record | R/W | Port | Runbooks |
|---|---|---|---|---|---|---|
| **`RS-PLT-01`** Resolve the declared scope into the pinned set | the owning module's selector for the declared subject | the runbook's scope rows, each with a tenant-resolved domain; *all* stored as **the word** and resolved at run start | is this record in the run? | read · set | — | **8 · 12 · 13 · 15 · 17 · 25 · 27** (Collections · Payments · Accounts) |
| **`RS-PLT-02`** Write the audit row naming the runbook and its version | — | the runbook key and version; the action kind | what was done, and by which runbook | **engine act** | — (not a port) | **8 · 25** (Collections) |
| `RS-PLT-03` Every enabled service has a unit and a basis | `tenancy` · `rating` | enabled services `S` | does this service have a unit and a basis? | read · set | — | 1 |
| `RS-PLT-04` Reference data is present | `tenancy` | — | is each of number series, holidays and account types populated? | read · set | — | 1 |
| `RS-PLT-05` Every service point has a tax region | `metering` · `tenancy` | tax regions `S` | does this service point have a region? | read · set | — | 1 |
| `RS-PLT-06` Every metered unit has a meter, a multiplier and a unit | `metering` | — | does this unit have all three? | read · set | — | 1 |
| `RS-PLT-07` One read per meter, and the read window closes before bill day | `metering` · `billing` | read window `S`; bill day | does this meter have a read, and does the window close in time? | read · set | — | 1 |
| `RS-PLT-08` A bill and a notice template exist for every service | `notifications` | enabled services `S` | does this service have both? | read · set | — | 1 |
| `RS-PLT-09` Every charge code and tender maps to a ledger account | `ledger` · `billing` · `payments` | — | is this code mapped? | read · set | — | 1 |

⚠ **`RS-PLT-01` AND `RS-PLT-02` ARE THE ENGINE'S, NOT A RUNBOOK'S — SEE §8.C.** They are in the
library because nine card steps describe them and a builder needs somewhere to resolve those rows
to; they are homed in Platform because the engine is the platform's, not because `tenancy` runs
them.

### Onboarding & Cutover — 7 steps · owning module `tenancy` · the cutover plan in operations

| Step | Reads | Inputs | Answers, per record | R/W | Port | Runbooks |
|---|---|---|---|---|---|---|
| `RS-ONB-01` Run the required Check first, and stop if it fails | the required Check's own run | which Check (`requires`) | did the requirement pass? | read · set | — | 2 |
| `RS-ONB-02` Counts agree with the legacy file | `customers` · `metering` · `billing` · the uploaded file | the file; the entity list | does our count equal the file's? | read · set | — | 2 |
| `RS-ONB-03` Payment plans and budget levels carried across | `payments` · `billing` | — | is this plan or level present? | read · set | — | 2 |
| `RS-ONB-04` Number series continue from the legacy last-used | `tenancy` | the file's last-used numbers | does the series continue with no gap and no overlap? | read · set | — | 2 |
| `RS-ONB-05` No sample row remains | every module's sample flag | *Sample data must be gone* | is this row a sample? | read · set | — | 2 |
| `RS-ONB-06` The last coverage-grid run had no refusals | the runbooks module's own run history | *Coverage grid must pass* | did the last grid run refuse anything? | read · set | — | 2 |
| `RS-ONB-07` Every cutover plan item is done, with evidence attached | operations (cutover plan) | — | is this item done, and is its evidence there? | read · set | — | 2 |

⚠ `RS-ONB-01` is declaration **7** of the contract object (`requires`, `BR-RBS-027`), written as
runbook 2's step 1 because the Chain block draws it there. §8.C.

### Data Hygiene — 6 steps · owning module `customers` · `metering`, read only

| Step | Reads | Inputs | Answers, per record | R/W | Port | Runbooks |
|---|---|---|---|---|---|---|
| `RS-HYG-01` Find duplicate customers by the declared keys | `customers` | *Duplicate means* — phone · tax id · email | is this customer a duplicate of another? | read · set | — | 19 |
| `RS-HYG-02` Find premises with no meter | `metering` | *Orphan means* `S` | can this service point be read? | read · set | — | 19 |
| `RS-HYG-03` Find meters with no premises | `metering` | *Orphan means* `S` | can this meter be billed? | read · set | — | 19 |
| `RS-HYG-04` Find accounts with no contact channel | `customers` | *Reachable means* — email · mobile · postal | can anybody be told anything? | read · set | — | 19 |
| `RS-HYG-05` Find addresses that failed standardisation | `metering` (premises) | — | will post arrive? | read · set | — | 19 |
| `RS-HYG-06` Label each finding with what it will break | the run's own findings | the consequence list — storm text · dunning · billing · cutover | which downstream job does this break? | read · set | — | 19 |

### Premises — 7 steps · owning module `metering` — premises and units

| Step | Reads | Inputs | Answers, per record | R/W | Port | Runbooks |
|---|---|---|---|---|---|---|
| `RS-PRM-01` Find the vacant premises in the pinned set | `metering` · `customers` | *Vacant means* `S` | is this premises vacant? | read · per record | — | 18 |
| `RS-PRM-02` Find usage over the threshold | `metering` | *Usage means more than*; window | is there usage above the threshold? | read · per record | — | 18 |
| `RS-PRM-03` Find active accounts whose meter has stopped | `metering` · `customers` | *Stopped means* — 0 for N reads | has this meter stopped? | read · per record | — | 18 |
| `RS-PRM-04` Check for a move-in already pending | `customers` | — | has somebody applied? | read · per record | — | 18 |
| `RS-PRM-05` Estimate what is going unbilled, at a named plan | `rating` | *Estimate revenue at* — a named plan | what is this worth a period? | read · per record | — | 18 |
| `RS-PRM-06` Label each finding with its likely cause | the run's own findings | the cause list — occupant unbilled · construction · leak · stuck meter | which cause is this? | read · set | — | 18 |
| `RS-PRM-07` Apply the field-level never-touch list and the run cap | `tenancy` | *Never touch* `S`; *Most changes per run* | may this field be written, and is the run inside its cap? | read · per record | — | 20 (Data Sync) |

⚠ `RS-PRM-07`'s never-touch list is **fixed on the money-path fields and cannot be widened by a
tenant** (`RBR-17`, restating the integration substrate's C25), and a cap **refuses the run — it
never truncates the set** (`BR-RBS-006`).

### Plans & Rates — 5 steps · owning module `rating`

| Step | Reads | Inputs | Answers, per record | R/W | Port | Runbooks |
|---|---|---|---|---|---|---|
| `RS-RAT-01` Every plan has a version covering the date | `rating` | *As at* | does this plan have a version covering it? | read · set | — | 1 (Platform) |
| `RS-RAT-02` The block ladder spans the usage basis | `rating` · `metering` | *Usage to cover* — highest seen, 12 months | is there a block above the highest usage? | read · set | — | 1 (Platform) |
| `RS-RAT-03` Load the draft rate schedule | `rating` | *Proposed schedule* | — (set) | read · set | — | 16 |
| `RS-RAT-04` Load the cycle exactly as it was billed | `billing` · `metering` · `rating` | *Against cycle* | what was this account actually billed, on what usage and days? | read · set | — | 16 |
| `RS-RAT-05` Sum revenue by service | the run's own priced results | *Revenue by service* | — (set) | read · set | — | 16 |

### Assets — 1 step · owning module `metering` — assets

| Step | Reads | Inputs | Answers, per record | R/W | Port | Runbooks |
|---|---|---|---|---|---|---|
| `RS-AST-01` Check the meter for a multiplier change, an exchange or a rollover | `metering` (assets, meter history) | the two bills' periods | did the meter itself change between the two bills? | read · per record | — | 4 (Billing) |

**The Assets category holds one step and no runbook.** The catalogue names its first runbook as
*Meters past their change-out age, or never tested* (`RB-128`), which is *named only* and declares
no steps.

### Accounts — 5 steps · owning module `customers`

| Step | Reads | Inputs | Answers, per record | R/W | Port | Runbooks |
|---|---|---|---|---|---|---|
| **`RS-ACC-01`** Queue the notice | `notifications` | the template; *Channel*; the cap; quiet hours `S`; one per record per run | which notice does this record get, on which channel? | **writes** | **`queue_notice`** | **8 · 11 · 15 · 17 · 25 · 27** (Collections · Reads · Payments) |
| **`RS-ACC-02`** Find the break in the account chain | `customers` · `metering` | which link — account → unit → premises → address | is this link present? | read · set | — | **1 · 19** (Platform · Data Hygiene) |
| `RS-ACC-03` Was the subject in the bill run's scope? | `billing` · `customers` | the bill run | status, cycle and service dates inside the period? | read · per record | — | 6 (Billing) |
| `RS-ACC-04` Was it held on purpose? | `customers` | — | a hold, a dispute or a deliberate exclusion? | read · per record | — | 6 (Billing) |
| `RS-ACC-05` Check the forwarding address | `customers` (mailing) · `metering` (premises) | — | is a standardised forwarding address on file? | read · per record | — | 27 |

⚠ **`RS-ACC-01` IS THE ONE THAT SAYS *QUEUED*, NEVER *SENT*.** No delivery provider is connected
(PO ruling, 17 August 2026); nothing leaves the building, and no copy over this step may claim
otherwise. ⚠ **`RS-ACC-02` is the one merge the cards themselves ask for** — runbook 19's step 4
reads, verbatim, *"The chain break from runbook 1, re-checked"*.

### Reads — 18 steps · owning module `metering`

| Step | Reads | Inputs | Answers, per record | R/W | Port | Runbooks |
|---|---|---|---|---|---|---|
| **`RS-RDS-01`** Run the read-validation rules over the reads | `metering` — the read importer's own validation stage | high/low limits `S`; rollover digits `S`; the zero rule | does this read pass validation? | read · per record | — | **3 · 21** (Billing · Data Sync) |
| **`RS-RDS-02`** Every subject has a read for the period, inside the window | `metering` | period; read window `S`; whether an estimate counts | is there a read for this subject in the window? | read · per record | — | **3 · 6** (Billing) |
| `RS-RDS-03` Build each meter's own year of periods | `metering` | window — 12 months | what did this meter do each period, actual or estimated? | read · per record | — | 5 |
| `RS-RDS-04` Flag spikes against the meter's own median | the built year | *Spike above own median*; *Ignore usage under* | is this period a spike? | read · per record | — | 5 |
| `RS-RDS-05` Flag drops and zero runs | the built year | *Drop below own median*; *Zero reads in a row* | is this a drop or a zero run? | read · per record | — | 5 |
| `RS-RDS-06` Flag flat lines | the built year | *Identical reads in a row* | is this meter stuck? | read · per record | — | 5 |
| `RS-RDS-07` Flag rollovers and negatives | the built year | rollover digits `S` | is this read lower than the one before? | read · per record | — | 5 |
| `RS-RDS-08` Flag over-estimation | the built year | *Estimated more than* | is this meter estimated too often? | read · per record | — | 5 |
| `RS-RDS-09` Flag out-of-season usage | the built year | the meter's own same-month history | is this period out of season **for this meter**? | read · per record | — | 5 |
| `RS-RDS-10` Rank meters by revenue at risk | `rating` · the run's own flags | under-billed before over-billed | how much revenue is at risk here? | read · per record | — | 5 |
| `RS-RDS-11` Work out each meter's own normal | `metering` (intervals) | *Above own normal* — the 90-day average | — (set) | read · set | — | 11 |
| `RS-RDS-12` Flag continuous flow or a spike against own normal | the pinned meter-days · the own-normal set | *Continuous flow for*; *Above own normal*; *Ignore below*; the larger of the two wins | is this meter leaking or spiking? | read · per record | — | 11 |
| `RS-RDS-13` Apply the guards and the once-per-meter cadence | `customers` (opt-outs, disputes) · the runbook's own records | *Never include* `S`; *Once per meter every* | may this meter be told, and was it told recently? | read · per record | — | 11 |
| `RS-RDS-14` Flag the meter as told about a leak | `metering` | the date | — | **writes** | **`flag_meter`** | 11 |
| `RS-RDS-15` Find the gaps in the day | the rolled-up meter-days | — | which intervals are missing, and was the meter silent all day? | read · per record | — | 21 |
| `RS-RDS-16` Estimate the short gaps by policy | `metering` (own 90-day average) | *Estimate gaps up to* `S`; *Longer gaps*; *Most estimates per run* | can this gap be estimated, or must it be queued? | read · per record | — | 21 |
| `RS-RDS-17` Write validated meter-days as reads | `metering` | source stamp — AMI; the estimate flag | — | **writes** | **`write_read`** | 21 |
| `RS-RDS-18` Check the closing read | `metering` | *Closing read due* `S`; the estimation policy `S` | is there a closing read, or may one be estimated? | read · per record | — | 27 (Accounts) |

⚠ **Every threshold in `RS-RDS-04` to `RS-RDS-09` is relative to the meter's own history, never
to a fleet average** (`BR-RBS-028`, `RBR-09`). A lane that "simplifies" one of them into a fleet
comparison has broken a signed rule and nothing in the counts will show it.

### Billing — 21 steps · owning module `billing`

| Step | Reads | Inputs | Answers, per record | R/W | Port | Runbooks |
|---|---|---|---|---|---|---|
| **`RS-BIL-01`** A plan is in force for the whole period | `rating` · `customers` | period; services | is a plan version in force for the whole period? | read · per record | — | **3 · 6** |
| **`RS-BIL-02`** Price the pinned set through the real engine | `billing`'s own pricing path — never a second implementation | the rate basis — in force, or a named draft; the as-at date | what does this subject price to? | read · per record | — | **16 · 23 · 24** (Plans & Rates) |
| **`RS-BIL-03`** Compare two bills line by line | `billing` (bill lines) | the two bills; *Show causes above* | what is the difference on this line? | read · per record | — | **4 · 16 · 23** (Plans & Rates) |
| `RS-BIL-04` Every block the period's usage needs exists | `rating` | this period's usage | is there a block covering this account's usage? | read · per record | — | 3 |
| `RS-BIL-05` Prorations are resolvable | `customers` (move dates) · `metering` (reads) | — | are the dates and reads there to prorate? | read · per record | — | 3 |
| `RS-BIL-06` No open correction blocks issue | `billing` | — | is a correction pending on this account? | read · per record | — | 3 |
| `RS-BIL-07` The prior period is closed | `billing` | *Prior period must be closed* | was the last run issued or cancelled? | read · set | — | 3 |
| `RS-BIL-08` Price a covering sample through the real engine | `billing`'s pricing path · `rating` | one account per plan | did the sample price? | read · set | — | 3 |
| `RS-BIL-09` Fetch two issued bills | `billing` | *This bill*; *Compared with* | — | read · per record | — | 4 |
| `RS-BIL-10` Compare usage between two periods, normalised for days | `metering` | *Normalise for days* | how much of the difference is usage? | read · per record | — | 4 |
| `RS-BIL-11` Compare the rate versions behind two bills | `rating` | — | did a rate version change between the two? | read · per record | — | 4 |
| `RS-BIL-12` Find the one-off items on a bill | `billing` | *Include one-off items* | catch-up read, corrected estimate, back-bill or late fee? | read · per record | — | 4 |
| `RS-BIL-13` Rank the causes by dollars contributed | the run's own findings | *Show causes above* | how much did this cause contribute? | read · per record | — | 4 |
| `RS-BIL-14` Did pricing refuse, and with which sentence? | `billing`'s pricing path | *Re-price to confirm* | which step refused, and what did it say? | read · per record | — | 6 |
| `RS-BIL-15` Did the write refuse, and why? | `billing` | — | a duplicate, a constraint, or a number series exhausted? | read · per record | — | 6 |
| `RS-BIL-16` Did it bill last time, and what changed since? | `billing` (prior runs) | — | what changed since the run that worked? | read · per record | — | 6 |
| `RS-BIL-17` Assemble the pricing inputs as the bill run would see them | `customers` · `metering` · `rating` · `billing` | the account; a cycle or an as-at date | — | read · per record | — | 23 |
| `RS-BIL-18` Explain every line in words | the priced result | *Show — every line, explained* | what is this line, in words? | read · per record | — | 23 |
| `RS-BIL-19` Pick one account per plan, service mix and cycle, deterministically | `customers` · `rating` | *Cells*; *Re-pick accounts* | which account represents this cell? | read · set | — | 24 |
| **`RS-BIL-20`** Group the records by a declared key and count each group | the run's own records | *Group by*; the band threshold (*Call it large above*) | which group is this record in? | read · set | — | **16 · 24** (Plans & Rates) |
| `RS-BIL-21` Issue the bill on the ordinary bill-run path | `billing` | — | — | **writes** | ⚠ **none of the thirteen** — §8.D | 27 (Accounts) |

⚠ **`RS-BIL-02`, `RS-BIL-08`, `RS-BIL-14` and `RS-BIL-17` all reach the SAME pricing path the
bill run uses.** That is what makes a preview trustworthy rather than an estimate, and a second
implementation of any of them is the defect this rule exists to prevent.

### Collections — 18 steps · owning module `payments` — the ladder lives in its settings

| Step | Reads | Inputs | Answers, per record | R/W | Port | Runbooks |
|---|---|---|---|---|---|---|
| **`RS-COL-01`** Exclude records under a protection or a dispute, as at now | `customers` (protections, disputes) · `payments` (plan in good standing) | *Never include* `S` | may this record be acted on **today**? | read · per record | — | **8 · 12** |
| `RS-COL-02` Work out the tier due against the ladder | `payments` (the ladder) `S` · the runbook's own records | *Ladder tiers* `S`; *Grace days* `S` | which tier is due, and has it already been sent? | read · per record | — | 8 |
| `RS-COL-03` Check the chosen channel is deliverable | `customers` (channel suppressions) | *Channels* | is the chosen channel alive? | read · per record | — | 8 |
| `RS-COL-04` Confirm the notice was delivered | `notifications` (delivery feedback) | — | was the letter served, or returned? | read · per record | — | 12 |
| `RS-COL-05` Confirm the notice period has passed | `tenancy` (timezone, working hours) `S` | *Notice period* `S` | has the period passed, in the tenant's timezone? | read · per record | — | 12 |
| `RS-COL-06` Check for a payment since a named moment | `payments` | *Check payments to* | did anything land since — applied or not? | read · per record | — | 12 |
| `RS-COL-07` Check the weather moratorium | `tenancy` `S` · the service area's forecast | *Weather moratorium* `S` | does the weather stop this today? | read · per record | — | 12 |
| `RS-COL-08` Check it is a working day | `tenancy` (holidays) `S` | *Working days only* | is today a working day? | read · set | — | 12 |
| `RS-COL-09` Build the field list | `metering` (premises → address, meter) · `payments` (balance) · `work` (crew notes) | *Produce a field list* | what does the crew need to know? | read · per record | — | 12 |
| `RS-COL-10` Check twelve months of on-time payment | `payments` · `billing` | *Good-payment months* `S` | was every bill paid by its due date? | read · per record | — | 15 |
| `RS-COL-11` Check nothing is past due today | `payments` | as at **this morning**, not this month | is anything past due right now? | read · per record | — | 15 |
| `RS-COL-12` Work out the interest owed | `tenancy` — the state's rate and method `S` | *Interest* `S`; four decimals | how much interest is owed? | read · per record | — | 15 |
| `RS-COL-13` Decide credit or refund against the limit | `customers` · `payments` | *Settle by*; *Refund instead when* | credit, or refund? | read · per record | — | 15 |
| `RS-COL-14` Post the credit, or raise the refund | `payments` | the second approval, for refunds | — | **writes** | **`post_credit` · `raise_refund`** | 15 |
| `RS-COL-15` Find missed instalments against the grace days | `payments` (plan schedules) | *Missed instalment* — grace days `S` | was this instalment missed? | read · per record | — | 25 |
| `RS-COL-16` Count the misses against the limit | the plan's own history | *Void after* `S` | is this plan over the limit? | read · per record | — | 25 |
| `RS-COL-17` Void the plan and return the balance to the ladder | `payments` | — | — | **writes** | ⚠ **none of the thirteen** — §8.D | 25 |
| `RS-COL-18` Settle the deposit by the declared mode | `payments` · `customers` | *Deposit* — refund, or carry to the new account; the second approval for a refund | refund, or carry forward? | **writes** | **`raise_refund`**; ⚠ the carry arm has **no port** — §8.D | 27 (Accounts) |

⚠ **`RS-COL-14`, `RS-COL-18` and `RS-PAY-16` carry the SECOND approval**, separate from the batch
approval, and `OQ-RBS-1732` is **CLOSED with no threshold**: *"every money action, no threshold"*.
**A threshold is not to be added later without a new ruling.**

### Payments — 17 steps · owning module `payments`

| Step | Reads | Inputs | Answers, per record | R/W | Port | Runbooks |
|---|---|---|---|---|---|---|
| `RS-PAY-01` Hold a duplicate | `payments` | *Duplicate window*; the source | is this the same money twice? | read · per record | — | 10 |
| `RS-PAY-02` Check the amount against the balance | `payments` · `billing` | *Overpayment over* | over, short, or exact? | read · per record | — | 10 |
| `RS-PAY-03` Apply the payment by the allocation order | `payments` | *Allocation order* `S` | — | **writes** | **`apply_payment`** | 10 |
| `RS-PAY-04` Record the run and queue the receipts | `notifications` | the receipt rule `S` | — | **writes** | **`queue_receipt`** (+ the engine's audit row) | 10 |
| `RS-PAY-05` Work out the debit date and amount | `billing` · `payments` | *Notify* `S` — days before | what will be taken, and when? | read · per record | — | 17 |
| `RS-PAY-06` Check whether the debit amount changed | `payments` (the last debit) | *Only when amount changed* | does this one need a notice? | read · per record | — | 17 |
| `RS-PAY-07` Check yesterday's failed debits | `payments` | the bank's reason codes, in words | did this debit fail, and why? | read · per record | — | 17 |
| `RS-PAY-08` Flag the account and schedule the retry | `customers` · `payments` | *Failed debit* — retry once after 3 days; **never a third** | — | **writes** | **`flag_account` · `schedule_retry`** | 17 |
| `RS-PAY-09` Find the same amount and date on any account | `payments`, tenant-wide | *Or amount*; *Around*; *Amount tolerance*; *Search other accounts* | is this payment on the wrong account? | read · set | — | 13 |
| `RS-PAY-10` Find reversed or returned items | `payments` | *Include reversed and returned* | did it come and go again? | read · per record | — | 13 |
| `RS-PAY-11` Find unapplied cash matching | `payments` | *Look back* | are we holding it, unplaced? | read · per record | — | 13 |
| `RS-PAY-12` Look in today's landed batch | `integrations` | *Include today's unapplied batch* | has it arrived but not been applied? | read · per record | — | 13 |
| `RS-PAY-13` Build the trace and the move route | the run's own findings | — | where did this payment go, in one sentence? | read · per record | — | 13 |
| `RS-PAY-14` Count prior returns against the privilege limit | `payments` | *Remove privilege after* `S` | is this account over the limit? | read · per record | — | 26 |
| `RS-PAY-15` Reverse the payment as a new row | `payments` | — | — | **writes** | ⚠ **none of the thirteen** — §8.D | 26 |
| `RS-PAY-16` Apply the fee and queue the notice | `billing` · `notifications` | *Fee* `S`; the second approval for the fee | — | **writes** | **`apply_fee` · `queue_notice`** | 26 |
| `RS-PAY-17` Remove the privilege after N | `customers` | dated | — | **writes** | **`flag_account`** — the card says *"the customers service"* | 26 |

⚠ **`RS-PAY-01` HOLDS, IT NEVER REJECTS** (`BR-RBS-033`, `RBR-14`) — the second payment is real
money somebody sent. ⚠ **`RS-PAY-15` is a new row, never an edit** — hard rule 4, and the
narrowing of 2026-09-02 does not reach it: only `confirmation`, `memo` and `method_id` may ever
be UPDATEd on `payments`, and only through `POST /payments/{id}/correct-reference`.

### Finance — 11 steps · owning module `ledger`

| Step | Reads | Inputs | Answers, per record | R/W | Port | Runbooks |
|---|---|---|---|---|---|---|
| **`RS-FIN-01`** Tie two money totals within a declared tolerance | `ledger` · `billing` · `payments` · the uploaded file | the two sides; *Money tolerance* / *Total tolerance* / *Tie-out tolerance*; the grain — per account, per service, or in total | do the two sides agree within the tolerance? | read · set | — | **2 · 9** *(4 instances: 2.3 · 2.4 · 9.4 · 9.5)* (Onboarding) |
| `RS-FIN-02` Every bill run finished | `billing` | the period | is this run issued or cancelled — nothing half-done? | read · set | — | 9 |
| `RS-FIN-03` Every payment posted, or held as unapplied | `payments` | the period | is this payment posted and allocated? | read · set | — | 9 |
| `RS-FIN-04` Unapplied cash within the amount allowed | `payments` | *Unapplied cash allowed* | is the unapplied total inside the limit? | read · set | — | 9 |
| `RS-FIN-05` Bank reconciled — no unmatched statement lines | `payments` | *Bank rec must be complete* | is any statement line unmatched? | read · set | — | 9 |
| `RS-FIN-06` Every adjustment has its approver | `billing` · `ledger` · audit | the period | who approved this write-off or credit? | read · set | — | 9 |
| `RS-FIN-07` Held deposits reconcile and refunds are cleared | `payments` · `ledger` | the period | does this deposit reconcile, and is its refund cleared? | read · set | — | 9 |
| `RS-FIN-08` Exports prepared, not sent | `integrations` · `ledger` | *Prepare exports* | is the file prepared? | read · set | — | 9 |
| `RS-FIN-09` Load the counterpart set to match against | `payments` (open deposit batches) | *Never include — already matched* `S` | — | read · set | — | 14 |
| `RS-FIN-10` Separate fees and adjustments from the unmatched | `payments` · `ledger` | the bank's own charge codes | is this line a bank charge rather than a mismatch? | read · per record | — | 14 |
| `RS-FIN-11` Record the match | `payments` | *Record matches automatically* | — | **writes** | **`record_match`** | 14 |

⚠ **`RS-FIN-01`'s TAX ARM HAS NO TOLERANCE AND IT CANNOT BE RAISED** (`BR-RBS-029`, `RBR-10`). Tax
is remitted to an authority; there is no *"we'll fix it next month"*. A shared step with a
per-instance tolerance input is exactly where a lane will one day pass a non-zero tolerance to the
tax instance, and nothing in the counts will show it — **so the tax instance's zero belongs in the
step's own test, not only in the runbook's.**

⚠ **NO PORT REACHES `ledger`.** Closing the period is a **named person's act, never a step**
(`BR-RBS-030`, confirmed by `OQ-RBS-1736` — *"always a person"*). There is no step in this library
that closes a period, and that absence is the design.

### Data Sync — 12 steps · owning module `integrations`

| Step | Reads | Inputs | Answers, per record | R/W | Port | Runbooks |
|---|---|---|---|---|---|---|
| **`RS-SYN-01`** Pin the landed batch from the declared connection | `integrations` | the connection(s) — one, several or **`all`**, stored as the word and resolved at run start; the window | is this record in the run? | read · set | — | **10 · 11 · 14 · 20 · 22 · 26** (Payments · Reads · Finance) |
| **`RS-SYN-02`** Match the pinned items to our records by the declared key ladder | the counterpart set, through its owning module's seam | *Match on* — an ordered key ladder; the tolerance; *Date window* | which of ours is this, and on which key did it match? | read · per record | — | **10 ×2 · 14 · 20 · 26** (Payments · Finance) |
| **`RS-SYN-03`** Raise the remainder as work items | the run's own unmatched records | the context fields the item carries | what does a person need to see to decide in one look? | **engine act** — the cards mark it `writes` | — (not a port) | **14 · 20 · 21** (Finance) |
| `RS-SYN-04` Pin the landed batch and roll it up to the declared unit of work | `integrations` | the connection; the unit of work `S` — **meter-day, never the interval** | is this record in the run, and at what grain? | read · set | — | 21 |
| `RS-SYN-05` Classify each difference against the declared class list | the matched pair | the seven classes — new value · blank here · blank there · conflict · two premises one parcel · one premise two parcels · unmatched | which class is this difference? | read · per record | — | 20 |
| `RS-SYN-06` Look up the disposition per field | `tenancy` (the disposition table) | *Apply automatically* / *Queue for a person* | auto, queue, or never? | read · per record | — | 20 |
| `RS-SYN-07` Apply the automatic change | `metering` | one field, one premises, before-and-after kept | — | **writes** | **`apply_premise_change`** | 20 |
| `RS-SYN-08` Classify each feedback item | the landed feedback | hard bounce · soft bounce · failed text · returned post | which kind of failure is this? | read · per record | — | 22 |
| `RS-SYN-09` Apply the suppression rule | `customers` (the channel's history) | *Suppress after*; *Soft bounce* — **one soft bounce suppresses nothing** | does this item suppress the channel? | read · per record | — | 22 |
| `RS-SYN-10` Find the next channel on file | `customers` | *Fall back to* `S` — email → text → post → none | what is left? | read · per record | — | 22 |
| `RS-SYN-11` Suppress the channel and fall back | `customers` | dated; the account's own preferences | — | **writes** | **`suppress_channel`** | 22 |
| `RS-SYN-12` Flag the address and raise work items | `customers` | *Nothing left* `S` | — | **writes** | **`flag_account`** (+ the engine's work item) | 22 |

⚠ **`RS-SYN-01`'s *`all`* IS A RULE, NOT A VALUE** — decision log 2026-09-06: it is stored as the
word and **resolved at run start**, never expanded to a list at configure time, and it then pins
(`BR-RBS-009`). Expand it early and a utility that adds a connection silently drops out of every
runbook set to *all*, with nothing to see. **In a step used by six runbooks, that absence is six
absences.**

---

## 8 · What this pass found in the cards — recorded, not fixed

**Nothing below is a card edit.** Each is a reading a builder will hit, written down once so it is
not re-derived.

### A · Looks alike, kept apart — the near-misses, with the reason

**The four the finding names are TWO steps, not one.** The prompting observation was that one job
appears under four names — runbook 8's *"Remove protected accounts"*, 11's *"Apply guards and
once-a-week"*, 12's *"Check protections and disputes again"* and 20's *"Check the cap and the
guards"*. **It is two.**

* **8.2 and 12.5 ARE one step** (`RS-COL-01`). Both evaluate an account's protections and disputes
  **as at now** and exclude. Runbook 12's *"again … today, not when the letter went"* describes
  when the **run** happens, not a different computation — a guard is always evaluated now.
* **11.4 is its own step** (`RS-RDS-13`). It bundles the guards with a **once-per-meter-every-7-days
  cadence** read off the runbook's own records. That is a second job, on a different subject.
* **20.5 is its own step** (`RS-PRM-07`). Its guard is **field-level** — a never-touch list applied
  per column of a premises — and it also enforces the run cap. Neither is what 8.2 does.

| Kept apart | Why they are not exactly each other |
|---|---|
| `1.5` block ladder spans the usage basis **vs** `3.4` every block this period needs exists | different **modes** — one runs once over the tariff, one runs per account (`BR-RBS-023`) |
| `4.7` rank causes by dollars **vs** `5.8` rank by revenue at risk | 5.8 is sign-aware — under-billed before over-billed — and ranks the run's records; 4.7 ranks causes inside one record |
| `15.6` post the credit or raise the refund **vs** `27.5` settle the deposit | 27.5's second arm is **carry forward to the new account**, which is not `post_credit` and has no port at all |
| `10.4` hold a duplicate payment **vs** `19.1` duplicate customers | different subject, different keys, opposite outcome — one holds money, one raises a finding |
| `20.3` classify a field difference **vs** `22.2` classify a feedback item | the class list is an input; **the classifier is the job**, and the two share no rule |
| `18.6` label with the likely cause **vs** `19.7` label with what it will break | same shape, entirely different rule sets |
| `8.4` is the channel deliverable · `22.4` which channel is next · `12.2` was the letter delivered · `19.5` has this account any channel at all | four different questions about contact channels; only the noun is shared |
| `16.2` load the cycle **as it was billed** **vs** `23.1` load the inputs **as the run would see them** | one reads history, one reads current state |
| `2.2` counts agree **vs** `RS-FIN-01` money tie-out | integers with no tolerance are not money with one |
| `1.8` one read per meter **and** the window closes before bill day **vs** `RS-RDS-02` | 1.8 bundles a calendar check |

**And the four merges most likely to be split by a builder**, named so the split is a decision
rather than a surprise: `RS-SYN-02` (if the money tolerance and the standardised-address key
cannot both be key options, it becomes three steps) · `RS-RDS-01` (rests on both callers reaching
metering's **same** validation stage — runbook 21 says *"unchanged"*, runbook 3 says *"by your
rules"*) · `RS-BIL-03` (rests on a computed bill and an issued bill presenting the same lines) ·
`RS-ACC-01` (runbook 27's notice carries **two** documents, a bill and a deposit letter).

### B · Twelve card steps do two jobs in one row

`1.8` · `3.8` · `9.8` · `10.7` · `11.4` · `17.6` · `21.1` · `22.6` · `26.5` · `27.5` · `27.6` ·
`16.5`. Rule 3 keeps each whole. **They are listed because they are where a future re-cut would
buy its ~9 further merges (§1), and because each is a place a builder will reasonably ask "is this
one function or two?"** The answer today is *one, because the card and the screen say one*.

### C · 15 of the 173 step instances describe ENGINE machinery, not runbook logic

**8.7% of the library's raw material is the engine written out as steps.** That is not a fault of
the cards — the Chain block draws one cell per step, so a card that wants the clerk to see
*"scope resolved"* has to write it as a step — but a builder must not implement them **inside**
runbooks:

| Written as a step | What it actually is | Instances |
|---|---|---|
| `RS-PLT-01` resolve the scope | **declaration 4** of the contract object, `resolve(params) → [SubjectRef]` — the same function that answers *"matches 1,004 today"* on the setup screen | 7 |
| `RS-SYN-03` raise work items | an **engine act, not a port** (`BR-RBS-022`) — and this is exactly how a Check populates `RBS-007` while holding no writer | 3 |
| `RS-COL-01` exclude the guarded | **guards are absolute and evaluated before any step** (`BR-RBS-012`); each card declares them in its Scope as *Never include* | 2 |
| `RS-PLT-02` write the audit row | an **engine act** (`BR-RBS-022`, hard rule 7) | 2 |
| `RS-ONB-01` run the required Check | **declaration 7**, `requires` (`BR-RBS-027`) | 1 |

⚠ **AND THREE OF THEM ARE MARKED `writes` ON THEIR CARDS.** Runbook 14 step 6, runbook 20 step 7
and runbook 21 step 6 all carry `writes` in the Mode column while the contract says raising a work
item is an engine act and **not one of the thirteen ports**. A lane building from those three
rows gives itself a fourteenth port — which is `BR-RBS-002` gone, the same collision
`OQ-RBS-1734` was resolved to avoid, and **nothing in the suite would notice: the work item would
still be written and every count would still agree.** Recorded here; the cards are not edited.

### D · Four writes name no port that exists

The thirteen ports do not cover four writes the reserved Action runbooks describe. **This is
consistent with the cards, which say so** — 25, 26 and 27 all read *"Ports it holds: Not declared
on the contract coverage table"* — but the gap has not been listed in one place before:

| Step | The write | Nearest port | Verdict |
|---|---|---|---|
| `RS-COL-17` (25.5) | void a payment plan, *"through the payments service"* | — | **no port** |
| `RS-PAY-15` (26.4) | reverse a payment as a new row | — | **no port** |
| `RS-BIL-21` (27.4) | issue the final bill on the ordinary bill-run path | — | **no port** |
| `RS-COL-18` (27.5) | carry a deposit forward to the new account | `post_credit` is **not** it | **no port** for the carry arm |
| `RS-PAY-17` (26.6) | remove the privilege, *"through the customers service"* | `flag_account` — *a flag with a reason* | covered, but **unnamed on the card** |

**Each is a reviewed interface to add, not a custom write to invent** — *"a new runbook that needs
a new port is adding a reviewed interface, not a custom write"* (`12-the-contract.md` §6). Four
ports would take the list from **thirteen to seventeen**, and every document that says *thirteen*
moves in the same commit. That is a fan-out and a ruling, and it is neither made nor assumed here.

### E · Two documented source disagreements are inherited, not resolved

`11-catalogue/README.md` records both and this file follows it. **The thirteen-port table** is
followed, not the stale *"four named calls"* sentence. **The trigger disagreement** on runbooks
10, 11 and 14 — `⚡ batch.landed` in the specification, `Daily 06:30 / 07:30 / 07:00` on the cards
— touches no step in this library, because every one of those three opens with `RS-SYN-01`, whose
input is the connection and not the clock.

---

## 9 · Status

**Status of this file: UNVERIFIED, and it is a MEASUREMENT rather than a claim.** Every figure in
§1 is reproducible from the cards with one pass over the `## Steps` tables; the merges in §7 are
judgments, each with its reason written beside it, and every one is arguable in public. **A merge
that is wrong makes the library larger, never smaller** — which is the safe direction for a number
whose predecessor was too small.

**What is owed next, and by whom:**

* **`10-execution-plan.md` phase 5's sizing** — *"each new runbook is a week of work rather than a
  project"* — is built on a library a runbook can be assembled from. Re-size it on **4.7 new steps
  per runbook**. A sibling lane holds that file today; `DEF-RBS-4275` carries the fan-out and names
  `01-overview.md` and `CR-075` with it.
* **A test per shared step**, per §6, before the first shared step has a second user.
* **`BR-RBS-038`'s missing half** — a rule for changing a shared step **in our own tree**, naming
  the runbooks it moves. It does not exist; §6 is not a rule.

Built from the twenty-six cards in `11-catalogue/` that declare steps, `12-the-contract.md`
§§1–3 and 6–9, `02-business-rules.md` (`BR-RBS-002` · `006` · `009` · `012` · `019` · `022` ·
`023` · `028` · `029` · `030` · `033` · `038` · `042`), and the two newest rows of
`12-governance/02-decision-log.md`. **Every step name in §7 resolves to a numbered row of a
numbered card; nothing has been added, and where a card is silent this file says so.**
