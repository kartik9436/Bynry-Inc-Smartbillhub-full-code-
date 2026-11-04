## CR-075 — Runbooks: one engine that walks a set, applies a utility's own declared process, and either reports what needs fixing or does the work

**Arrived 2026-09-06.** Raised by the Product Owner across three artifacts and six
messages in one session. Written up under `12-governance/13-change-process.md`.

---

## 0 · Capture — the requester's words, verbatim

> *"I want you to read 3 documents from artifacts. and confirm whether you ahve all the
> etails to write details in 04 folder as new module; Runbook; also here please note each
> runbook details should be save in seperate folder or file so that later himan developer
> can edit them easily; rest fot eh details remain same ; please confirm your high level
> understanding in table format and folder strcture,prefix for all items that we write
> including screens; we ahve marker in documents os that you can udnerstand"*

Then, clearing the three items put back to them:

> *"it is an example so we can understand the impact - you can keep the note ; nothing to
> act right now"* — on the 60,000–80,000 account figure.

> *"what do you want from me I did not udnerstand"* — on being told nine rulings were not
> in the repository. **Nothing was wanted. That was a reporting failure on our side**
> (`DEF-1931`'s shape: a sentence that reads as a request and is a statement of intent).

> *"we coin the word Runbooks - we should make this industry standard"*

> *"Screens S147–S154 - this should be RBS-nnn"*

> *"phase them in to 4 or 5 phases and ask questions in phase 4 and 5 … we have to design
> each phase in agile way that means each phase deliver outcome"*

⚠ **THE PLACEMENT HALF OF THAT SENTENCE — *"ask questions in phase 4 and 5"* — WAS OVERTAKEN BY THE
SAME REQUESTER ON 2026-09-06** (§6). **Nobody moved the questions: the WORK moved earlier and the
questions came with it.** Three of the six now arrive in phase 2 and one in phase 4. **The part that
mattered still holds — not one of them blocks anything**, because each has a deliberate build that
an answer can only widen, so a question arriving three phases sooner costs a conversation and never
a stub.

> *"You can start writing 04 folder and CR"*

**The three source artifacts**, read in full and stripped to plain text for the lanes:
the **Runbooks specification** (screens, contract, data, endpoints, rules, tests, phases),
**Twenty-One Runbooks** (each runbook's scope, parameters, steps and result), and the
**Runbooks market position** (who else has this, and what the design is worth).

---

## 1 · Classify

**A CHANGE, not a defect.** Nothing in the product is wrong; a capability that does not
exist is being specified. The change process says an ambiguous case is a defect, because
filing our own misunderstanding as a "change" converts our error into the customer's new
requirement. This one is not ambiguous: no line of Runbooks code exists.

**Size: a new module.** Eleventh documentation module, twelfth code module.

---

## 2 · What signed statement is being reversed

**One, and it is ours rather than the PO's.** This lane recommended on 2026-09-06 that
runbook screens take `S147`–`S154`, on the argument that Runbooks is a section of the
staff app rather than a new surface, and that the `CWP-nnn` / `Work-nnn` precedent was
about band exhaustion at 75 and 33 screens — which eight screens do not cause.

**The PO reversed it the same hour**: *"Screens S147–S154 - this should be RBS-nnn"*.
The pattern of 2026-09-03 is a rule about **modules**, not about size, and that reading is
the one that keeps `S` meaning one thing forever. Recorded in the decision log with the
reasoning, because a reversal nobody can see gets re-derived. **`S147` remains the next
free `S` and this CR consumes none of them.**

**Nothing FROZEN is touched.** B4 and B5 are untouched: a runbook prices nothing itself —
runbook 23 (Test bill) and runbook 24 (Coverage grid) call the existing rating engine and
show what it returns. If a coverage cell disagrees with a golden test, the defect is in the
engine or in the fixture, never in the runbook.

**One earlier PO quote is superseded and the supersession is stated**: the market page
records *"we will have to increase the scale up to 60,000 accounts or 80,000 accounts"*
(5 September). The ICP ruling of 6 September stands at 40,000 (T7/T6/T5), and the PO ruled
today that the larger figure was an illustration. Four commitments that wait on it
(`RB-043`, `RB-045`, `RB-046`, `RB-047`) are **kept as written and marked not scoped**.

---

## 3 · Impact across the ten surfaces

| Surface | What changes |
|---|---|
| **Spec A1–A17** | A1's screen inventory gains a pointer to the `RBS-nnn` series. No `S` number is consumed. |
| **Decisions B1–B14** | B14 gains nothing new; the eight screens obey the 36 rules as drawn. B2 needs seven table rows and thirteen port rows in the cross-module interface register — **not done in this pass and named as a gap.** |
| **Contracts** | `04-docs/03-contracts` gains 18 routes and six refusal keys. The enums gain `runbook_kind`, `run_status`, `trigger_kind`, `origin` and the sixteen categories. |
| **Modules** | New folder `04-docs/05-modules/17-runbooks/`. New code module `apps/runbooks`. Nothing is renumbered; the never-used `14` slot is left alone. |
| **Open questions** | Eleven of the specification's twelve open decisions carry over. Nine are minted as `OQ-RBS-nnnn`; two that the source left open on phase 1 are OURS under law 13 and are decided rather than asked. |
| **Defect register** | No existing defect is closed by this. `DEF-BIL-4224` (the 25,000-account bill-run ceiling) becomes more visible, because runbook 3 sweeps every account due in a cycle. |
| **Journeys** | Three new: `J-RBS-1` get to billable · `J-RBS-2` prove it on their data · `J-RBS-3` a guarded send. |
| **Demo fixture** | A fixture tenant with exact figures: 1,004 past-due accounts splitting 812 / 43 / 31 / 23 / 95, three billing blockers, two medical protections, two disputes, three sample rows, and a legacy trial balance of `$412,880.4400` differing on twelve accounts by `$1,204.0500`. |
| **Non-functional** | `NFR-3` (universal server pagination) and `NFR-5` (no hard caps) bind every list this module adds. The run-record cap is a **per-run** limit a clerk sets, which is not a tenant cap and does not breach `NFR-5`. |
| **Integrations** | `BR-INT-054` already draws the line and three CR-069 waves (`G`, `L`, `Q`) move here whole. Two events integrations does not emit yet — `batch.landed` and `feedback.landed` — are needed by six runbooks and are phase 5's dependency, not phase 1's. |

---

## 4 · What is already built, and is now wrong

**Nothing is wrong. Some of it is already ours.** Three CR-069 waves moved to Runbooks by
`BR-INT-054` as amended, and two of them shipped their work on the integrations side before
the boundary was drawn:

| Already shipped | Where it sits now | What must happen |
|---|---|---|
| Wave `C`'s per-item run results — the `items` column, `runs.py`, `RunCard` | Runbooks' side of the line | `OQ-INT-1727` — does it move, stay as a named exception, or does Runbooks read it where it is? **Open, and it is the PO's.** |
| Wave `D`'s value mappings — `mappings.py`, `mappings_api.py`, `ValueMappingPage.tsx`, screen `S143` | Runbooks' side | same question, same OQ |
| Wave `G` (scheduling), `L` (late readings), `Q` (the parcel night report) | **Not built** | They wait for this module. Nothing to unpick. |

**One live lane was checked and is unaffected:** the CR-069 integrations UI lane finished at
`2.201.1` and touched no path this CR will.

---

## 5 · Size, in plain English with a figure

**Phase 1 is the engine plus one Check plus six screens.** Everything after it is one
Python module per runbook and no frontend work at all, because the two renderers already
draw whatever a runbook's report composes out of the twelve blocks.

**What the five phases return**, on the market study's own estimates — which are estimates
to check against a real customer's week, not measurements:

* Phases 1–3 return **no hours**. They return the go-live confidence problem: a utility
  that has seen 25 green cells on its own data before go-live behaves differently from one
  that has not, and problems arrive before the bill run instead of during it.
* Phase 4 returns about **33 hours a month** at a 3,000-connection utility — one runbook,
  the collections ladder, is two thirds of the whole return.
* Phase 5 returns roughly **20 more hours a month** across eight more Actions.

---

## 6 · Execution — through r11, unchanged

Five phases, each ending with something a user can open. The Product Owner asked for four
or five, agile, each delivering an outcome, with the questions pushed into phases 4 and 5.

⚠ **THE PHASE ORDER WAS RE-CUT ON 2026-09-06 BY TWO PRODUCT OWNER RULINGS, AND THE TABLE BELOW IS
THAT ORDER.** Verbatim: *"For Cr 75 - once you have foundation I want to prioritise runbook related
to integration first and then rest"*, then, narrowing which integrations: *"For me integration
related to accounting, payment provider, emails, GIS are important - over other"*.

**Why honouring it moves the ACTING half into the foundation, and why that is not a
reinterpretation.** Every runbook fed by an integration is an **Action** — cash application (10),
bank reconciliation (14), GIS reconciliation (20), undeliverable contacts (22) — verified card by
card, and each is triggered by a landed batch. **An Action writes, and an Action cannot run before
the acting half exists**: the thirteen ports, the batch approval carrying its count, the cap that
refuses rather than truncates, stop, the idempotency key and the runbook as a named audit actor.
**So the acting half is now phase 2. It is the only order in which the four can run at all.**

**Nothing is renumbered.** Every wave letter and task id is unchanged; only which phase a wave
belongs to moved, and two letters changed their contents and are written `Q′` and `R′`. **The epics
are not renumbered either**, so `EP-RBS-04` is now phase 2's epic, `EP-RBS-02` and `EP-RBS-03` are
both phase 4, and `EP-RBS-05` spans phases 3 and 5.

| Phase | Builds | The outcome |
|---|---|---|
| **1 · The foundation, part one: it can look** (waves `A`–`E`) | The engine's envelope — the seven-part contract, the two renderers, the conformance suite, definition · versioning · run · per-record and set evaluation · results — plus runbook 1, and screens `RBS-001` to `RBS-006` | A clerk presses one button and sees exactly what is stopping billing, each finding with a button to the screen that fixes it. **Nothing can be written: no writer is bound.** |
| **2 · The foundation, part two: it can act** (waves `L` `M` `N`) — *was phase 4* | The thirteen ports, the gate, the cap, stop, idempotency, the audit actor — runbook 8, **dry-run only first, live second** | A clerk sees exactly what would be sent to 812 accounts and cannot send it. Then: ~33 hours a month, every notice naming the rule that sent it |
| **3 · The integration runbooks** (waves `O` `P` `Q′`) — *new grouping* | The event trigger from a landed batch, then the four runbooks serving the four areas named: **cash application (10)** — payment provider · **bank reconciliation (14)** — accounting · **GIS reconciliation (20)** — GIS · **undeliverable contacts (22)** — emails | A file lands and the work starts itself. Cash is on accounts before a cashier opens the product rather than after |
| **4 · Prove it on their data, and the scheduled Checks** (waves `F`–`K`) — *was phases 2 and 3* | Runbooks 23 and 24 over the existing pricing path; scheduling in tenant time, the work list (`RBS-007`), run history (`RBS-008`), runbooks 3, 2 and 9, plan items with evidence | A utility sees its own accounts produce correct bills before go-live — 25 cells; and problems arrive before the bill run, in one list a clerk opens each morning |
| **5 · The rest** (waves `R′` `S` `T`) | The non-integration Actions — returned payments (26) and autopay pre-notification (17) first, then leak alert (11), read validation (21), deposit review (15), payment plans (25), move-outs (27) — the eight remaining Checks, and **inputs with tenant-resolved domains** (`BR-RBS-042`) | ~20 more hours a month; **each runbook re-uses about 2 shared steps and writes about 4.7 of its own**, and **no new screen**. ⚠ **This cell read *“and compose”* and *“a week rather than a project”* until 2026-09-06, and BOTH were wrong.** A tenant sets input values and never arranges steps (`BR-RBS-042`); and the hand count of the 26 catalogue cards (`04-docs/05-modules/17-runbooks/14-step-library.md`, `DEF-RBS-4275`) makes the sizing **173 instances → 137 distinct steps, 89% of them singletons, a 20.8% reduction** — a fifth of the step-writing, not a third. ⚠ **The figure that moved was OURS, not the PO's, so this is a measurement replacing an estimate and not a re-sign** |

⚠ **TWO INTEGRATION-DRIVEN ACTIONS ARE NOT IN PHASE 3, AND THE GAP IS A DECISION RATHER THAN AN
OVERSIGHT.** **Leak and high-usage alert (11)** and **read validation on arrival (21)** are both
Actions and both trigger off `batch.landed`, but they are fed by interval-meter data (`meters_mdm`,
`meters_neptune360`), which is none of the four areas named. They are in wave `R′`, phase 5.
**Returned payments (26) and autopay pre-notification (17) touch the payment provider and are also
not in phase 3**, because neither is triggered by a landed batch — 17 runs on a schedule and 26 is a
reserved definition. They are the head of `R′`, the first two things built after phase 3. **If the
payment-provider AREA matters more than the landed-batch TRIGGER, those two move up and phase 3
becomes six runbooks — that is the Product Owner's call, not a lane's.**

⚠ **WHAT THE RE-CUT COSTS, STATED RATHER THAN SOLD.** The old order put every Check first and
reached an Action only after the engine had been proved on work that could not reach a customer.
**The new order reaches the dangerous half immediately after the foundation.** Two prices:

1. **The safety argument now rests entirely on wave `M`** — a full cycle, dry, in production, with
   sending switched off and a written go/no-go, which **stays exactly where it is, between `L` and
   `N`, at its full length. Shortening it, or folding it into `L`, is the one change that would make
   this reorder unsafe.**
2. **The coverage grid — the go-live artefact and the sales artefact at once — lands in phase 4
   instead of phase 2.** A utility that has seen 25 green cells on its own data before go-live
   behaves differently from one that has not, and under this order the first customer sees it three
   phases later.

⚠ **AND ONE GAP SITS INSIDE THE FIRST AREA ON THE LIST: NOTHING BUILDS THE ACCOUNTING FILE'S
CONTENTS.** `CR-069` wave `J` makes the **envelope** — the `accounting_file` connection, its
destination, its codec and `test()`. Under `BR-INT-054` **what goes IN the file is Runbooks' half,
and no runbook card exists for it.** Runbook 9 (*month-end completion*) is a **Check** that reads a
period's postings and produces a tie-out; it carries the guard *"the GL export can only be called
once Close has been pressed"* and a step reading *"Exports ready · files prepared, not yet sent"*,
and it composes nothing and sends nothing. **None of the thirteen ports writes or emits a file.**
So **accounting is first on the Product Owner's list and is the one of the four areas with no
runbook.** ⚠ **This CR does NOT invent the card** — a runbook that composes a general-ledger export
needs a fourteenth port, which is a reviewed interface change and a rule change, not a lane's
decision — **and it does not quietly drop it either.** It is recorded here, in
[`../../04-docs/05-modules/17-runbooks/10-execution-plan.md`](../../04-docs/05-modules/17-runbooks/10-execution-plan.md)
§5 and in the decision log, so the Product Owner sees it rather than discovering it.

**Why the acting half is split into a dry half and a live half, and it is not caution for its own sake.** (It is **phase 2** from 2026-09-06; it was phase 4 when this paragraph was written, and everything in it matters MORE at second than it did at fourth.) Everything dangerous
about this feature lives in the acting half: the ports, the cap, the stop, the idempotency
key, the audit actor. Shipping all of it with sending switched **off** means the risky code
runs against real accounts, in production, for a full cycle, while being unable to do
anything. Turning it on is then a one-line change to a runbook's kind — made after the code
has already proved itself where it matters.

**The risk that decides the design, stated plainly.** The failure that hurts is not a
runbook doing nothing — somebody notices that. It is a misconfigured runbook queueing three
thousand wrong disconnection notices in four minutes, and **a notice cannot be unsent**.
The cap, the dry run, the batch approval and the stop button are first-release
requirements, not hardening for later. Everything else here is negotiable; those four are
not.

**Two dependencies outside this CR, and the 2026-09-06 re-cut made both of them urgent.**

**1 · The audit actor.** An automated action has no name today: `BR-AUD-003` says a NULL
`actor_user_id` means *"a system job"*, so every automation in the product is indistinguishable from
every other and a runbook would have to borrow a staff login — **a person would appear to have
personally sent 812 letters at 07:00 on a Monday.** It blocked the old phase 4; **it now blocks
phase 2, and through it phases 3 and 5**, because no writer is bound until it lands. **It is the
single largest schedule risk in the plan.** A delivery provider must also be connected before phase
2's live half means anything to a customer.

**2 · Integrations emits neither event.** `batch.landed(connection, batch_id, subject_type)` and
`feedback.landed(provider, batch_id)` **do not exist — zero occurrences under
`06-backend/apps/integrations/` and zero in the backend at all, verified 2026-09-06.** All four
phase-3 runbooks trigger off them, and two more (11 and 21) do as well. **Under `BR-INT-054` as
amended 2026-09-06, integrations keeps exactly three things — building a connection, holding keys
and secrets, and the lifecycle of a connection — and *"a batch landed on this connection"* is a
LIFECYCLE fact, so it is integrations' half to build and it is CR-069's work. It is currently scoped
to nobody.** ⚠ **What it costs if it slips: phase 3 has no trigger.** The four runbooks still work
by hand and still produce the right figures, but *"a file lands and the work starts itself"* — the
phase's whole launch sentence — does not happen, and a cashier presses Run every morning instead of
finding the cash already applied. **It must be raised on CR-069 as scoped work before phase 2
closes.**

**Phase 1 depends on neither and can start immediately.**

---

## 7 · Version

Scheme `<release>.<change>.<fix>`. This CR is a `<change>` bump per phase that lands.
No version is claimed here: this row is the specification, and a version is written into it
when a phase closes. **A CR marked done with no version is refused by a gate**, which is why
this section exists at all — the PO named step 7 as the one usually skipped.

---

## 8 · Close, and the rollback stated before shipping

**Rollback for PHASE 1 is complete and costs nothing:** it is Checks. No port is
bound, no other module's table is written, and the seven tables are this module's own.
Dropping the module drops its rows and nothing else in the product changes. ⚠ **THIS
PARAGRAPH SAID *phases 1–3* UNTIL 2026-09-06 AND THE RE-CUT NARROWED IT TO ONE PHASE** —
phase 4 is still all Checks and rolls back the same way, but it is no longer reached before
anything writes.

**Rollback for the acting half — phase 2 from 2026-09-06 — is not symmetric and the CR says so rather than pretending.** Once
an Action has queued a notice, the queue row exists and the audit row exists; unbuilding the
runbook does not unqueue them. The reversible act is **turning the runbook off** — which is
one field on one row — not removing the code. That is why the kind is immutable after
creation and why the trust ratchet drops an edited Action back to dry-run.

---

## What is deliberately NOT decided here

| # | Question | Whose | Phase |
|---|---|---|---|
| 1 | The default cap for a first run — a number you are comfortable seeing acted on unattended | PO | **2** (was 4) |
| 2 | Which actions need a second approval, and above what amount | PO | **2** (was 4) |
| 3 | Does an admin approve every run, or may a tenant set a runbook unattended once it is trusted | PO | **2** (was 4) |
| 4 | May a Check ever write a note to an account automatically | PO | 5 |
| 5 | ~~Compose scope — which fields may be filtered and which steps a tenant may use~~ **CLOSED, PO 2026-09-06 — the question had the wrong shape.** A tenant filters no fields and uses no steps: a runbook is one fixed process with declared **inputs**, each with a **tenant-resolved domain**, and a value may be one, several or ***all*** (`BR-RBS-042`) | **answered** | — |
| 6 | May closing the accounting period ever be automated once every tie-out is clear | PO | **4** (was 5) |
| 7 | Is the cutover plan a product screen now, or a spreadsheet for the first two customers | PO | **4** (was 3) |
| 8 | The sixteen category names as a clerk would read them | **decided as ours**: use the product's own existing word wherever it has one, so *Service points* is **Premises** | 1 |
| 9 | Is *Can we bill?* one verdict for the tenant or one per service | **decided as ours**: one per service, rolled up | 1 |
| 10 | The minimum object set before a bill is permitted | **decided as ours**: runbook 1's ten steps already enumerate it | 1 |
| 11 | Packaging — included or a tier | PO, commercial, blocks nothing technical | — |

**Answered already:** *do tenants author their own runbooks?* — **compose yes, author no**
(PO, 5 September), ⚠ **NARROWED BY THE PO ON 6 SEPTEMBER AND THE NARROWING IS STATED RATHER THAN
INFERRED: *WE* compose; a tenant SETS INPUT VALUES and CLONES.** This CR read *compose* as the
tenant composing, and it does not mean that. PO verbatim: *“I dont think Utility admin will able to configure these using the 150 bricks that we give - you can keep all these bricks and buld ready to use runbooks - when we later change it will be small er changes for us”* — **the reason is adoption, not architecture.** Both statements are the PO's and the later
governs; *author no* is unchanged and is now **structural**, because a tenant who can only choose
input values has no path by which to write logic. See `BR-RBS-042`. *Is it called Runbooks?* —
**yes, coined deliberately** (PO, 6 September).

---

## Three errors found inside the source documents, corrected as this was written

1. **Four ports or thirteen.** The architecture section says a runbook writes through
   *"four named calls"* and lists *raise a work item* among them. The contract section lists
   **thirteen** and states explicitly that raising work items and writing audit rows are
   **engine acts, never ports** — which is the only thing that lets a Check populate the
   work list while holding no writer. Thirteen is right. Building the four-call version
   gives every Check a writer and `BR-RBS-002` is gone.
2. **`BR-RBS-029` is used twice** — once for "the month-end tie-out tolerance for tax is
   $0.00", once in the appendix for "a new category or a thirteenth block needs three
   runbooks". The tax rule keeps the id; the second is dropped because `BR-RBS-021` and
   `BR-RBS-025` already state both halves. A lane citing 029 for the three-runbook rule
   would land on a money figure.
3. **Numeric error codes.** `RBS-001`…`RBS-006` are not this repo's shape — every refusal
   is a message key — and `RBS-nnn` now means a screen. They become
   `runbooks.refusal.<name>` in all eleven catalogues.

---

## Prefixes — every id this module writes

| Kind | Prefix | Note |
|---|---|---|
| Change specification | `RB-001`–`RB-052` (engine, screens, roadmap) · `RB-101`–`RB-135` (one per runbook) | PO: *"yes you can use prefix RB"*. Free in this repo. The last two digits of an `RB-1nn` are the runbook's number. |
| Business rule | `BR-RBS-#####` | PO: *"if you need 3 letter then RBS"* |
| User story | `US-RBS-#####` | |
| Epic | `EP-RBS-01`–`05` | one per phase |
| Test case | `TC-RBS-#####` | |
| Journey | `J-RBS-1`–`3` | in `08-qa/01-e2e/journeys/` |
| Open question | `OQ-RBS-nnnn` | one running number across the whole register |
| Defect | `DEF-RBS-nnnn` | |
| **Screen** | **`RBS-001`–`RBS-008`** | PO ruling. States dotted (`RBS-005.3`); per-runbook renderer instances `-Rn` (`RBS-004-R8`) |
| Refusal | `runbooks.refusal.<name>` | not a number |

⚠ **The grammar needs a lookbehind as well as a lookahead, and this is `DEF-2804` waiting to
happen.** The module code is also `RBS`, so a screen is `RBS-001` while a rule is
`BR-RBS-001`. A search for `RBS-001` matches **inside all four families**, and `RBS-\d{3}`
returns `RBS-001` for `RBS-0012`. The pattern is **`(?<![A-Z]-)RBS-\d{3,5}(?!\d)`** and both
assertions are load-bearing: without the lookbehind a screen search returns rules; without
the lookahead it truncates, which is exactly how `OQ-\d{3}` returned `OQ-119` for `OQ-1190`
and put a stub against the wrong question for two days.

---

## Where it lives

```
04-docs/05-modules/17-runbooks/
├── 01-overview.md            what it is, the two kinds, what it refuses
├── 02-business-rules.md      BR-RBS-001..039
├── 03-field-map.md           the seven tables, column by column
├── 04-flows.md               three sequences, the six-step lifecycle
├── 05-user-stories.md        US-RBS-001..041
├── 06-epics/                 EP-RBS-01..05, one per phase
├── 07-endpoints.md           18 routes, six refusal keys
├── 08-screen-layouts.md      RBS-001..RBS-008 and their 29 states
├── 09-component-inventory.md the 12 result blocks, the 11 parameter types
├── 10-execution-plan.md      the five phases as waves
├── 11-catalogue/             ONE FILE PER RUNBOOK — the PO's own requirement
│   ├── README.md
│   └── RB-101-configuration-check.md … RB-135-service-request-chase.md  (34 files)
├── 12-the-contract.md        the seven-part object, 13 ports, 16 categories
└── wireframes/               75 pictures + 75 build sheets, paired
```

**Backend module `apps/runbooks`.** The nav route stays `/{tenant}/operations` as drawn in
every wireframe until the section's on-screen name is settled — the name of the *product
concept* is ruled, the name of the *nav word* rides on the same open decision the PO closed
for the concept, and changing the route moves 75 build sheets.

**One file per runbook is the PO's explicit requirement**, in their words: *"each runbook
details should be save in seperate folder or file so that later human developer can edit
them easily"*. A developer opens one file, edits one runbook, and touches nothing else.

---

## Before the first line of code — four traps found while writing this up

Added 2026-09-06, from the pass that wrote the screens, the components and the contract.
Each is a thing that passes every check this repository has and still ships a broken product.

**1 · No runbooks path is in `07-frontend/src/styles/route-b-migrated.txt`, and B14 rule 21's
migration clause is PER FILE.** A Tailwind utility is emitted only for a file on that list.
Write one in a file that is not on it and the class is declared by no stylesheet: **the screen
renders as nothing at all**, while `tsc`, eslint and every `toContain("flex")` assertion pass,
because the class *is* in the DOM. **Adding the module's frontend paths to that file belongs in
the same commit as its first component**, not in a later tidy-up. Two lanes hit this in one week
already.

**2 · Six components the twelve result blocks need do not exist**: `VerdictBand`, `Chain`,
`ContributionBars`, `OutcomeCard`, `SettingsOwnedField`, `PercentCell` — plus the Records block's
**sparkline cell** and its **grid mode**. The coverage grid *is* that grid mode, so
`EP-RBS-02` depends on a phase-1 component. They are phase 1 work. ⚠ **After the 2026-09-06
re-cut the coverage grid is in PHASE 4, three phases after the components it needs**, which
makes deferring them look cheaper and puts the day it bites further away.

**3 · There is no percent formatter in the front end at all**, and **no percentage in any of the
75 build sheets is drawn at two decimals**. Hard rule 2 says percentages store to six and display
to two. Two money figures are also drawn without cents (`+$5,310`, `$9,840`).

**4 · Thirty-nine of the seventy-five build sheets are FRAGMENTS with no page head.** A lane
building one literally ships a headerless page. A sheet is the region list for its frame, not the
whole screen — the page head comes from `RBS-004` or `RBS-006`, whichever renderer is drawing it.

### And one open question the wireframes raise against B14 rule 33

Twenty-eight Outcome boxes run **14 to 88 words** (median 25.5). Rule 33 caps on-screen text by
what it is for — a label 3 words, a fact 6, an instruction 6 per sentence, a consequence 6 per
sentence at most two, and **rationale zero words on screen**. All twenty-eight exceed every one of
those caps. Either the outcome box is a FACT list and must be cut to facts, or it is a template
description that does not belong on the runbook's own screen at all. **Not decided here.** ⚠ Note
for anyone checking this: `CLAUDE.md`'s own one-line summary of rule 33 says *"a refusal sentence
caps at five or six words"*, which is the half `G33` enforces and NOT the rule — that gap is
`DEF-GOV-4242`, and reading the summary instead of the rule is what nearly got this finding
dismissed.
