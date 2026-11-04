## CR-074 — Turning the test suite on: 54 walkthroughs, 347 journeys, and being able to say what our coverage is

**Status: RULED — the Product Owner asked for this change and asked for it in phases.**

⚠ **THIS TOOK `CR-074` AND NOT `CR-073`, DELIBERATELY.** The register's *next free number* line read
`CR-073` when this was written, and a lane building the universal-search change was mid-flight under
instruction to take exactly that. Two lanes correctly computing "the next free number" and getting the
same answer is a collision this repository has had three times in one day, across defect ids, gate
numbers and versions (`DEF-GOV-3756`, `DEF-CWP-3734`). Skipping one number costs nothing; a duplicated
CR id costs a citation that lands on the wrong change forever. Reserved in `14-id-reservations.md`.

### CR-074 · 0 · CAPTURE — the Product Owner's words, verbatim

Said 2026-09-05, after asking how many end-to-end tests we could run and being told the honest answer:

> *"Can we write a cr with phases to enable them? We are almost completed the product - we are left
> with integrations and run books ; once that is completed we are done with full decimation of product ;
> the next set of work is testing it ; while we are doing unit test bskend and front end test ; it us
> important all web walkthrough are completed and we are able to run e2e journey and we should have
> clear decimation of what is our test suite for product"*

**Read the sequencing in it, because it shapes every phase below.** The Product Owner is not asking for
tests to be written *now*. They are saying: the build finishes with integrations and runbooks; then the
next body of work is testing; and by the time that starts, three things must be true — **every web
walkthrough runs**, **the end-to-end journeys can actually be executed**, and **we can state plainly
what our test suite is**. The third is not a nicety. It is the one they said we do not have.

### CR-074 · 1 · CLASSIFIED

A **requirement**, not a defect. Nothing signed is being reversed and nothing is broken for a customer.

⚠ **BUT ONE PART OF IT IS A DEFECT WEARING A REQUIREMENT'S CLOTHES, AND SAYING SO IS THE POINT OF
STEP 1.** The change process says that when a classification is ambiguous it is a **defect**, because
filing our own misunderstanding as a "change" quietly converts our error into the customer's new
requirement. **The 347 journeys were authored as deliverables and were never runnable**; the walkthroughs
were written per wave and nothing was ever built to run them together. Neither gap was ruled — they
accumulated. So the *enabling* is a change; **the fact that they are off is ours**, and this document
says so rather than presenting a clean slate.

### CR-074 · 2 · WHAT WE ACTUALLY HAVE, MEASURED 2026-09-05

Counted from the tree at `2.196.0`, not estimated:

| Surface | Count | Runs on its own? |
|---|---|---|
| Backend tests | **9,810 functions across 835 files** | ✅ yes, every lane, every push |
| Front-end tests | **367 files** | ✅ yes |
| Merge gates | **116** | ✅ yes (`run_gates.py`) |
| Golden money checks | 33 document + 14 engine-verified of 61 signed | ✅ yes |
| **Journey specifications** | **347 files**, ~300 without a *not activated* banner | ❌ **prose. ONE executable spec exists for all 347** |
| **Browser walkthroughs** | **54 scripts, ~1,672 assertions** | ❌ **one at a time, by hand. No runner. Every CI workflow is `.disabled`** |
| Machine-computed expectations | 1 dataset — 245 money combinations | feeds golden |

**So roughly 10,300 automated checks run continuously, and the only two surfaces that exercise the
product END TO END do not run at all.**

⚠ **AND THE TWO ARE NOT THE SAME THING, WHICH IS WHY BOTH NUMBERS HAVE BEEN QUOTED AS "our e2e tests".**
A **journey** is a scenario specification — a path with the values it must produce, generated from
`00-e2e-design.md`'s seven axes (plan shape × category × read source × bill type × payment outcome ×
delivery × role = 44,100 combinations, designed down to ~307). It says **what should happen**. A
**walkthrough** is a script that boots the stack and clicks. It says **what does happen**. Neither is a
test alone: a journey with no script is a description nobody checks; a script with no journey is a
click-through with no claim behind it. **Sampling six journeys the Work waves cite as their contracts:
two have a walkthrough that names them, four have none.**

### CR-074 · 3 · WHY THIS IS WORTH REAL MONEY, EVIDENCED

On 2026-09-05 five walkthroughs were run by hand. Between them they found, in one day:

* a technician **could never open a job** — the function fetching one onto the phone was written, tested
  and called by nothing (`DEF-WRK-4061`);
* **two screens unreachable from the day they shipped** — route constants carrying a tenant prefix the
  router adds itself (`DEF-WRK-4051`);
* the dispatcher's map with **no background and an unassigned pin that was not red** — two colour names
  compiling to no rule at all (`DEF-WRK-4053`);
* **five further faults** in wave L, including an assertion that passed *because the page had never
  loaded*.

**Every one was invisible to all 9,810 backend tests, all 367 front-end files, `tsc`, eslint and all 116
gates.** That is hard-won law 6 — *nothing in this repository reads rendered output* — priced. **49 of
the 54 walkthroughs were not run that day**, and there is no reason to think they are quieter.

### CR-074 · 4 · THE PHASES

Sequenced so each phase produces something usable on its own, and ordered by evidence-per-hour rather
than by tidiness. **Phases 1–3 are the ones that change what we know; 4–5 are the long tail.**

| Phase | What | Size | Produces |
|---|---|---|---|
| **1 · The runner** | One script that boots a stack **once**, seeds a tenant, runs all 54 walkthroughs against it and reports pass/fail per script. Registered in `run_gates` behind a flag so it is *available* without costing every merge 40 minutes | **~1 day** | a number where there is currently none |
| **2 · Triage what it says** | Run it. Sort every failure into *the product is wrong*, *the walkthrough is stale*, or *the fixture drifted* — the shape that took the isolation suite from 50 red to 3 in one lane. **Expect real defects**; today's rate was four in five runs | **2–4 days** | every walkthrough green or filed |
| **3 · The map, and the honest coverage number** | Which of the 347 journeys does each walkthrough actually exercise? Extend `01-journey-story-index.json`, and publish the figure — *"N of 347 journeys are executed by a script; the rest are described only"* | **~2 days** | the answer to *what is our test suite* |
| **4 · The spines and the money** | Make executable: the **6 module-handoff spines** (J1–J6), then the **money-critical set**, where `expected/money-triples.csv` already holds 245 machine-computed combinations so the arithmetic exists and only the driving is missing | **3–5 weeks** | end-to-end proof where the money is |
| **5 · The long tail, by tier** | T3 combination, T4 transition, T5 break-path, T6 RBAC, T7 non-functional — in the design's own priority order, **not evenly** | **months, ongoing** | breadth |

⚠ **PHASE 4 IS WHERE AN HONEST ESTIMATE MATTERS MOST.** 347 journeys at even two hours each is
**months, not days**, and the design forbids the shortcut: *"Every money-bearing journey's expected values
are MACHINE-COMPUTED — no hand math, ever."* A plan that promises all 347 by a date is a plan that will
be met by hand-typing expected values, which is the one thing the design rules out. **Phases 1–3 are
days and give most of the value; phase 4 is a programme.**

### CR-074 · 5 · WHEN

The Product Owner set the sequencing themselves: **integrations and runbooks finish the build**, then
testing is the next body of work. So:

* **Phases 1–3 can start now and should** — they need no new product code, they compete with nothing, and
  phase 2 will file defects the build lanes can fix while they are still in that code.
* **Phase 4 starts when the build does not** — it needs the product to stop moving under it, or the
  expectations drift as fast as they are written.

⚠ **AND `CR-069` (integrations) IS NOT DONE, WHICH THIS DOCUMENT SHOULD NOT PRETEND.** Its wave E needs a
real mail credential only the Product Owner can supply, and the Runbooks boundary ruling (`BR-INT-054`,
2026-09-05, **amended 2026-09-06**) says integrations *connects and manages the connection* while Runbooks
*handles the logic, ETL and record updates* — deliberately unscoped until CR-070 completed, which it now has.
⚠ **THE 2026-09-06 SHARPENING NAMES A FOURTH THING FOR RUNBOOKS — *SCHEDULING* — AND THAT REACHES THIS
DOCUMENT.** Integrations keeps three things (building a connection, holding keys and secrets, the lifecycle
of a connection); business logic, scheduling and processing go to Runbooks. `CR-069` §20 classifies all
nineteen waves, and **about half of what is left moves** — so a test-suite plan that sizes the integrations
backlog from the old wave list is sizing two projects as one. Nothing is built against it yet.

### CR-074 · 6 · WHAT "CLEAR DOCUMENTATION OF OUR TEST SUITE" MEANS

The Product Owner asked for this last and it is the deliverable they will actually read. It is **one
document**, produced by phase 3 and maintained after:

* **what runs, how often, and what each surface can and cannot see** — including that the gates read
  source and never rendered output, and that the backend suite runs on SQLite where row-level security
  does not exist (hard-won law 14);
* **the coverage figure with its denominator stated** — *N of 347 journeys executed*, not a percentage
  with no basis;
* **what is deliberately NOT tested, and by whose ruling** — reads and finance are out of universal
  search by PO ruling; stock and ledger-posting are unbuilt by closed rulings; each recorded so a lane
  in six months does not "discover" a gap that was a decision;
* **the standing figures that must be quoted in pairs** — `33/33` is DOCUMENT self-consistency and
  `14 of 61` is engine-verified, and quoting the first alone has misled this repository for weeks
  (`DEF-2846`).

### CR-074 · 7 · VERSION

The change process's step 7 exists because it is the step most often skipped. Each phase ships under its
own `<change>` bump with a CHANGELOG entry, and **phase 1 does not count as done until the runner has
been run and its output recorded** — a runner nobody has run is the pathology this whole CR is about.

### CR-074 · 8 · ROLLBACK

**Phases 1–3: delete the runner and the index rows.** Nothing in the product changes; only our ability
to see it does. **Phase 4 onward: the journey scripts are additive test code** — removing them removes
proof, never behaviour. There is no data migration and no customer-visible surface in any phase.
