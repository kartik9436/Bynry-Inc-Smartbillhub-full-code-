# EP-RBS-01 — Can we bill? The engine's envelope, the definition surface, and the first Check

**Module:** runbooks · **Phase:** 1 of 5 (unchanged by the 2026-09-06 re-cut) · **Screens:** `RBS-001` Runbooks home · `RBS-002` Templates (with the category filter) · `RBS-003` My runbooks · `RBS-004` Runbook detail (the setup renderer) · `RBS-005` Run wizard (the four-step Check path) · `RBS-006` Run result (the report renderer) · **Status:** draft (written 2026-09-06 from the Runbooks specification v0.1, restructured 5 September; product `2.201.1`)

⚠ **PHASE ORDER RE-CUT 2026-09-06 — THIS EPIC IS STILL PHASE 1 AND ITS CONTENTS DID NOT MOVE.** Two Product
Owner rulings that day put the integration runbooks first: *"once you have foundation I want to prioritise
runbook related to integration first and then rest"*, then *"For me integration related to accounting,
payment provider, emails, GIS are important - over other"*. **The epics are NOT renumbered, so the epic
numbers no longer track the phase numbers** — `EP-RBS-04` is now phase 2, `EP-RBS-02` and `EP-RBS-03` are
both phase 4, and `EP-RBS-05` spans phases 3 and 5. **The order is
[`../10-execution-plan.md`](../10-execution-plan.md) §1.**

⚠ **What changed FOR THIS EPIC: the thing built next after it is the ACTING half, not a Check.** Everything
this epic refuses to do — bind a writer, touch another module's table — is done in the wave immediately
after it, so *"phase 1 binds no writer, on purpose"* is now the last quiet phase rather than the first of
three.


## Scope

**In:** the whole envelope and exactly one runbook to prove it. **The seven-part contract** — key, kind, subject, unit of work, triggers, category, tags, typed parameters, `resolve()`, ordered `steps[]` with their two modes, absolute `guards[]`, the `ports[]` allow-list and `report()` — with **the plugin registry and the conformance suite** that refuses a module the contract does not accept. **The two renderers**: `RBS-004` over any definition and `RBS-006` over any run's frozen report, drawn from the **twelve block types** and nothing else. **Definition, versioning, run, per-record and set evaluation, and results** — the seven tables, RLS `FORCE`, the savepoint per record proved on PostgreSQL, the pinned scope, the report frozen at close. **The definition surface whole**: the shipped template library, adding a template, cloning and varying it, and every edit making a new version a run pins. **The "Can we bill?" Check (runbook 1)** with its ten steps. **`RBS-001`, `RBS-002` with its category filter, `RBS-003`, `RBS-004`, `RBS-005`, `RBS-006`.**

⚠ **AND EIGHT PIECES OF SHARED UI THE RENDERERS NEED DO NOT EXIST YET — THEY ARE THIS PHASE'S WORK, NOT PHASE 5's.** Verified absent from `07-frontend/src/components/` on 2026-09-06: **`VerdictBand` · `Chain` · `ContributionBars` · `OutcomeCard` · `SettingsOwnedField` · `PercentCell`**, plus the `Records` block's **sparkline cell** and its **grid display mode**. Phase 1 builds the renderer, so it builds these; and **phase 2's coverage grid IS that grid mode**, so deferring them makes `EP-RBS-02` unbuildable rather than merely late. They join the shared component kit (B14 rule 36). ⚠ **There is also no percent formatter in the front end at all**, and hard rule 2 says percentages display at **2** decimals over **6** stored — `PercentCell` needs one and it is shared, beside the money formatter.

⚠ **AND THE FIRST FRONTEND COMMIT ADDS THIS MODULE'S PATHS TO `07-frontend/src/styles/route-b-migrated.txt`, IN THE SAME COMMIT AS THE FIRST COMPONENT.** Measured 2026-09-06: that file is **3,241 lines and holds zero runbooks paths**. B14 rule 21's migration clause is **per file** — a Tailwind utility is emitted only for a file on that list — so without it **every screen in this module renders as nothing at all** while `tsc`, eslint and every `toContain("flex")` assertion pass, because the class **is** in the DOM (`DEF-974`). It is execution-plan task `A2` and it is not a tidy-up.

**Out:** every port and everything that uses one — **this phase binds no writer at all** (`EP-RBS-04`). Scheduling, the work list and run history (`EP-RBS-03`). Test bill and the coverage grid (`EP-RBS-02`). The `requires` declaration is part of the contract and is **declared here, used first in `EP-RBS-03`**, where runbook 2 needs it — the field exists in phase 1 and the sub-run linking and its test land in phase 3, said out loud rather than left to be discovered. `unit_of_work` is likewise declared here and first enforced against a volume runbook in `EP-RBS-05`.

**Exit test of the phase — a demonstration, not an opinion.** On the seeded two-service fixture, a clerk opens Runbooks, presses **Run** on *Can we bill?*, and the result shows **3 blockers, each with a button to the screen that fixes it**. Then a developer binds an action port to that Check and **the build fails** — not the run.

⚠ **PHASE 1 BINDS NO WRITER, ON PURPOSE.** Everything dangerous about this module lives in the acting half, and none of it is here. The riskiest thing this phase can do to a customer is nothing at all, which is the correct amount of risk for the phase in which the engine is being learned.

## Capability matrix (list screens only — B9 conformance)

| Screen | Search fields | Filters | Default sort | Sortable | Columns default/available | Row actions | Bulk actions | Export |
|---|---|---|---|---|---|---|---|---|
| `RBS-002` Templates | template name | **category** (chips, drawn only for categories that hold a template) · kind | category order, then name | name · category | name · kind · category · what it touches / + last updated | Add · Open detail | — | — |
| `RBS-003` My runbooks | runbook name | kind · category · enabled | name | name · kind · category · next run · last result | name · kind · category · schedule · last result / + cap · gate · version | Open · Clone · Run | — | — |
| `RBS-004` Runs tab | — | outcome | started, newest first | started · outcome | started · mode · version · outcome · counts | Open result | — | — |

`RBS-001`, `RBS-005` and `RBS-006` are not B9 list screens: `RBS-001` is a landing screen with a KPI strip and sections, `RBS-005` is a stepper, `RBS-006` is a report renderer. **Every table on all six obeys `NFR-3`: it pages on the server**, with `per` clamped to 50/100/200/500/1000 and a default of 50. **No unpaginated list is added by this phase** — the four existing `NFR-3` breaches named in `DEF-PAY-4221` are not this module's and are not copied by it.

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
id: US-RBS-001
epic: EP-RBS-01
module: runbooks
screens: [RBS-001, RBS-005, RBS-006]
phase: 1
status: ready
blocked_by: []
depends_on: [US-RBS-002, US-RBS-015, US-RBS-016]
journeys: [J-RBS-1]
rules: [BR-RBS-001, BR-RBS-002, BR-RBS-010, BR-RBS-011, BR-RBS-023]
golden_tests: []
finance_calc: none
---
### US-RBS-001 — As a clerk I run a Check and see what is stopping billing

**1 · Details** — As **a billing clerk at a utility that is not live yet**, I want **to press one button and be told exactly what is stopping us from billing** — so that **I can fix the first thing in the chain instead of guessing which of forty settings is wrong**.

*Can we bill?* (runbook 1, displayed under that name; its definition title is **Configuration check**) walks the tenant's configuration graph in **ten steps, in the order a bill actually needs them**: services and units · reference data · tax · plans in force · rate coverage · account chain · meters · reads and windows · documents · books. **The first failure is always the earliest one in the chain**, which is the one to fix first. Its scope is decided for it — there is nothing to choose — and its four parameters are *Report*, *Usage to cover*, *Include held accounts* and *Raise work items*.

**Every finding names the screen that fixes it.** A failure with no fix route is a defect in the runbook, not a fact about the account (`BR-RBS-011`), and a static scan proves there is none (`TC-RBS-14`).

**The verdict is per SERVICE, rolled up to the tenant** — decided under law 13 with its reasoning in [`../01-overview.md`](../01-overview.md) §8.1, and **the ten steps ARE the minimum object set** (§8.2). Steps 1, 3, 4, 5, 7, 9 and 10 carry a per-service verdict; steps 2, 6 and 8 are tenant-wide. The tenant verdict is the worst of them.

Entry: **Run** on `RBS-001` or on the runbook's own `RBS-004`. Exit: `RBS-006` draws the ten-cell chain red at the earliest failure, with the findings beneath it.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-RBS-001` | A runbook is either a Check or an Action, declared at creation and never changed afterwards | PROPOSED |
| `BR-RBS-002` | A Check is constructed without action ports; a write attempt raises rather than being refused at runtime | PROPOSED |
| `BR-RBS-010` | Every record states the rule that decided it, in words a clerk can read | PROPOSED |
| `BR-RBS-011` | A failure names its fix route; a failure with no route is a defect in the runbook | PROPOSED |
| `BR-RBS-023` | A set-mode step runs once over the pinned set; a per-record step runs once per subject in its own savepoint; a step declares which | PROPOSED |

**3 · Test Cases**

| TC | Scenario | Expected | Must first fail on |
|---|---|---|---|
| `TC-RBS-1` | A Check with an action port bound | Raises **at construction**, not at run time | A Check with a port bound that only raises when the port is called — it must fail loudly at build |
| `TC-RBS-7` · **tenant isolation** | A run in tenant A while tenant B holds the same runbook | No row of tenant B is read or written, RLS `FORCE` on | A scope function missing the tenant context |
| `TC-RBS-14` · **gate** | Static scan of every failure reason in the module | Zero reasons without a fix route | One reason with no route, added on purpose |
| `TC-RBS-001.1` | The blockers fixture | Exactly **3 blockers**, three distinct fix routes, and `runbook_run_records` holds **no** row whose `planned_action` is anything but `report` | A Check that writes a work item directly instead of returning a finding |
| `TC-RBS-001.2` | Per-service rollup on the two-service fixture with the tax region missing on Sewer only | Water reads **Go**, Sewer reads **No-go**, the tenant reads **No-go** | A single tenant verdict — it cannot distinguish this case from both services failing |

**4 · Test Data** — Fixture tenant, **two services** (Water and Sewer, 60 accounts, 58 premises, 62 meters), plus the **billing-blockers** set: no tax region · one plan with no rate above 20,000 gallons · 4 accounts with no unit. **These three produce exactly the 3 blockers and the 3 fix routes**, which is what makes the figure on screen assertable. Second tenant for isolation. Nothing about Gas or Solar appears anywhere in this fixture, which is itself an assertion.

**5 · Data Fields / Mapping**

| Field | Screen | DB target | Type | Origin | Validation |
|---|---|---|---|---|---|
| `report` · `usage_to_cover` · `include_held` · `raise_work_items` | `RBS-004` Scope/Parameters | `runbook_versions.definition` | enum · enum · toggle · toggle | user-input | typed against the eleven parameter types |
| `runbook_runs.scope_fingerprint` | — | `runbook_runs` | text | derived | pinned at run start, never re-resolved |
| `runbook_run_records.outcome` · `reason` · `fix_route` | `RBS-006` Records block | `runbook_run_records` | enum · text · route | derived | `fix_route` NOT NULL wherever `outcome` is a failure |
| `runbook_runs.report` | `RBS-006` | `runbook_runs` | jsonb | derived | validates against the twelve-block schema at close |

**6 · Acceptance**
- Given the blockers fixture, when a clerk presses Run on *Can we bill?*, then the result reads **3 things stop billing**, the chain shows ten cells red at the earliest failure, and each finding carries a button to the screen that fixes it.
- Given the same run, when the database is inspected, then **not one row outside this module's own seven tables changed**.
- Given the tax region is then fixed and the runbook re-run, then the count falls to **2** (journey `J-RBS-1`).

**7 · Finance Calculation** — N/A. This Check reads the pricing configuration; it prices nothing. Test bill (`EP-RBS-02`) is the story that touches money.

**8 · Open Questions** — **None.** The two the source left open on this phase — one verdict or one per service, and the minimum object set — are **decided in [`../01-overview.md`](../01-overview.md) §8 under law 13** and no `OQ` is minted for either.

---
id: US-RBS-002
epic: EP-RBS-01
module: runbooks
screens: [RBS-002, RBS-004]
phase: 1
status: ready
blocked_by: []
depends_on: []
journeys: []
rules: [BR-RBS-001, BR-RBS-002, BR-RBS-022]
golden_tests: []
finance_calc: none
---
### US-RBS-002 — As a developer I need a Check that cannot write

**1 · Details** — As **an engineer**, I want **the engine to construct a Check with no writer at all** — so that **a clerk pressing Run on a thousand accounts is safe by construction and not by review**.

The engine's constructor takes the runbook's declared `ports[]`. **A Check declares none, so the executor it is handed has no writer to call.** Binding a port to a `kind = check` runbook **raises at construction**: the process does not start. This is the difference between *report-only* as a capability and *report-only* as a sentence in a docstring, and hard-won law 1 is exactly about that difference.

**What the clerk sees, so the guarantee is legible and not merely true:** the template detail on `RBS-002` and the Overview tab on `RBS-004` carry a **"What it can touch"** block reading **Writes: Nothing · Sends: Nothing**, derived from the ports the runbook holds **and from nothing else** — never from a hand-written label that could disagree with the constructor.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-RBS-001` | Kind is declared at creation and never changed afterwards | PROPOSED |
| `BR-RBS-002` | A Check is constructed without action ports; a write attempt raises rather than being refused at runtime | PROPOSED |
| `BR-RBS-022` | A runbook reaches another module or a partner only through a named port; work items and audit rows are the ENGINE's to write | PROPOSED |

**3 · Test Cases**

| TC | Scenario | Expected | Must first fail on |
|---|---|---|---|
| `TC-RBS-1` | Binding an action port to a Check | Raises at construction, naming the runbook key and the port | A Check with a port bound, which must fail loudly |
| `TC-RBS-002.1` · **negative** | A Check's step calls a seam's write function | The seam a Check is given **exposes read functions only**, so the attribute does not exist | A seam module that exports writes unconditionally |
| `TC-RBS-002.2` · **screen** | The Overview tab for *Coverage grid* | Reads **Writes: Nothing · Sends: Nothing**, derived from `ports[]` | A hard-coded label — planted, it must go red when a port is added |

**4 · Test Data** — Two registered runbooks: one Check (*Can we bill?*, `ports = []`) and one Action (*Dunning and notices*, `ports = [queue_notice, apply_fee]`), the second registered but never run in this phase.

**5 · Data Fields / Mapping**

| Field | Screen | DB target | Type | Origin | Validation |
|---|---|---|---|---|---|
| `runbooks.kind` | `RBS-002` · `RBS-003` · `RBS-004` | `runbooks` | enum `check` \| `action` | reference-data | immutable after creation (`BR-RBS-001`) |
| `ports[]` | `RBS-004` Overview "What it can touch" | `runbook_versions.definition` | list of port names | reference-data | empty for a Check; every entry on the thirteen-port list |

**6 · Acceptance**
- Given a Check module declaring a port, when the app starts, then it refuses to start and names the runbook and the port.
- Given *Coverage grid*'s template detail, when it renders, then "What it can touch" reads **Writes: Nothing · Sends: Nothing** and the words come from `ports[]`.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — **None.** ⚠ `OQ-RBS-1734` (may a Check ever write a note to an account automatically) would, if answered yes, add a **fourteenth port** and **narrow this rule**. It is carried against **phase 5** and blocks nothing here: until it is answered, `BR-RBS-002` is absolute.

---
id: US-RBS-003
epic: EP-RBS-01
module: runbooks
screens: [RBS-001]
phase: 1
status: ready
blocked_by: []
depends_on: [US-RBS-015]
journeys: [J-RBS-1]
rules: [BR-RBS-024, BR-RBS-025, BR-RBS-026]
golden_tests: []
finance_calc: none
---
### US-RBS-003 — As a clerk I see the runbook catalogue

**1 · Details** — As **a clerk opening the product in the morning**, I want **one screen that answers *is anything waiting on me · what is running now · what can I run*, in that order** — so that **I do not have to remember what the automation was supposed to have done overnight**.

`RBS-001` is the landing screen at `/{tenant}/operations`. Its page head reads **Runbooks · Checks report. Actions send.** — three words that teach the whole safety model — with **Templates →**, **History →** and **Work list →** as its actions. A KPI strip of four tiles carries the counts a clerk actually acts on; the sections beneath answer the three questions in order. **A run left as a draft is kept, not lost.**

Every row names its **kind**, its **schedule**, its **last result** and its **open items**. **No database id is ever the visible value of a field** (B14 rule 31), and no rule id or internal code reaches this copy (B14 rule 32).

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-RBS-024` | A runbook has exactly one category, from a fixed list of sixteen held in code; anything else it touches is a tag | PROPOSED |
| `BR-RBS-025` | A category with no runbook is never drawn as a filter | PROPOSED |
| `BR-RBS-026` | Onboarding & Cutover sorts first in the library while a cutover plan is open and last once it closes; no other category carries an order rule | PROPOSED |

**3 · Test Cases**

| TC | Scenario | Expected | Must first fail on |
|---|---|---|---|
| `TC-RBS-003.1` | First visit, nothing configured | The empty state names what to do next and links to Templates; **no zero-filled KPI strip pretending to be data** | A populated-shape screen with zeros |
| `TC-RBS-003.2` | A run in flight | The row reads Running with its progress and a Stop control that is **live**, not a placeholder | A greyed control over a live run — hard-won law 2's mirror |
| `TC-RBS-003.3` · **B14** | Every visible field on `RBS-001` | No database id, no rule id, no internal code appears in any cell (rules 31 and 32) | A row keyed by `runbook_id` |

**4 · Test Data** — The two-service fixture with **three** shipped runbooks added: *Can we bill?* (ran clean today), *Ready for billing?* (scheduled, not yet run — its schedule renders, the run does not), *Dunning and notices* (an Action, disabled in this phase). Second tenant for isolation.

**5 · Data Fields / Mapping**

| Field | Screen | DB target | Type | Origin | Validation |
|---|---|---|---|---|---|
| `runbooks.name` · `kind` · `category` · `enabled` | `RBS-001` rows | `runbooks` | text · enum · enum · bool | user/reference | category ∈ the sixteen |
| last-run summary (`status`, `finished_at`, counts) | `RBS-001` rows | `runbook_runs` | derived | derived | newest run per runbook, server-side |
| open-item count | `RBS-001` KPI strip | `work_items` | integer | derived | counted per runbook by `source_run_id` |

**6 · Acceptance**
- Given three runbooks and one open finding, when a clerk opens `/{tenant}/operations`, then the KPI strip reads the four counts and the sections answer *waiting on me · running now · what can I run* in that order.
- Given a tenant with nothing configured, when the screen loads, then the first-visit state renders and no tile shows a fabricated zero.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — **None.** ⚠ The **section name in the navigation is not ruled**; the route stays `/{tenant}/operations` as drawn on every wireframe and the page head reads **Runbooks** (PO 2026-09-06). A lane may not change either.

---
id: US-RBS-015
epic: EP-RBS-01
module: runbooks
screens: [RBS-001, RBS-004, RBS-006]
phase: 1
status: ready
blocked_by: []
depends_on: [US-RBS-016]
journeys: []
rules: [BR-RBS-001, BR-RBS-019, BR-RBS-021, BR-RBS-023, BR-RBS-024]
golden_tests: []
finance_calc: none
---
### US-RBS-015 — As a developer I add a runbook without touching the frontend

**1 · Details** — As **an engineer**, I want **a runbook to be one Python module declaring the contract** — so that **runbook twenty-two costs a week and not a project, and adds no screen**.

**The contract, in full, and this is the phase that builds it.** A runbook declares `key` · `kind` · `subject_type` · `unit_of_work` · `triggers[]` · `category` · `tags[]` · typed `parameters[]` · `resolve(params) → [SubjectRef]` (one function, which also answers *"matches 1,004 today"*) · `steps[]`, each `run(ctx, subject) → outcome` declaring `writes: bool` and `mode: per_record | set` · `guards[]`, evaluated **before** any step · `requires` (optional; one Check run first — **declared here, wired in `EP-RBS-03`**) · `ports[]` · `report(run) → [Block]`.

**The registry and the conformance suite.** Modules register at `AppConfig.ready()`. The suite runs over **every** registered runbook: it constructs · resolves on the fixture · dry-runs · asserts a Check wrote nothing · validates its report against the block schema. **A module the suite refuses does not load.**

**Two acts the engine performs and no runbook may:** raising work items and writing audit rows. A Check returns findings; **the engine** upserts them when the run closes.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-RBS-021` | The block vocabulary is fixed at twelve; a thirteenth needs three runbooks that cannot be drawn without it | PROPOSED |
| `BR-RBS-023` | A step declares its mode; set runs once over the pinned set, per-record once per subject in its own savepoint | PROPOSED |
| `BR-RBS-024` | Exactly one category from the fixed sixteen; the category names the owning module whose ports it may call | PROPOSED |
| `BR-RBS-019` | A runbook declares its unit of work, and it is never the raw row | PROPOSED — **declared here, first enforced in `EP-RBS-05`** |

**3 · Test Cases**

| TC | Scenario | Expected | Must first fail on |
|---|---|---|---|
| `TC-RBS-15` | Conformance — every registered runbook, one suite | Each constructs · resolves on the fixture · dry-runs · a Check wrote nothing · its report validates against the block schema | A runbook module whose report contains an unknown block, added on purpose |
| `TC-RBS-19` · **negative** | A module declaring `category = "Misc"` | Refused at construction, naming the module and the category | A module declaring Misc, added on purpose |
| `TC-RBS-17` | A set-mode step over the fixture | Executes **once**, and the per-record step once per subject | The set step registered as per-record — the tie-out figure (1,410 bills) lands in `EP-RBS-03` |
| `TC-RBS-015.1` · **gate** | Adding a new runbook module and diffing the branch | **No file under `07-frontend/` changed** | A runbook that needs a component — the gate must go red on one added on purpose |

**4 · Test Data** — One deliberately broken module per negative case, each added and removed by the test: unknown block · category `Misc` · set step registered per-record · a Check with a port. **Each is first shown red**; a green with no red behind it is not proof of anything.

**5 · Data Fields / Mapping**

| Field | Screen | DB target | Type | Origin | Validation |
|---|---|---|---|---|---|
| the contract's eleven declarations | `RBS-004` (all seven tabs render from them) | `runbook_versions.definition` jsonb | struct | code | validated by the conformance suite at load |
| `runbooks.subject_type` · `unit_of_work` | `RBS-004` Overview | `runbooks` | enum · enum | reference-data | subject ∈ tenant · account · premise · meter · meter-day · bill · payment · bank line · deposit · parcel · contact feedback · period |
| `runbooks.category` | `RBS-002` chips · `RBS-003` column | `runbooks` | enum of sixteen | reference-data | never free text |

**6 · Acceptance**
- Given one new Python module declaring the contract, when the app starts, then it appears on `RBS-002`, renders on `RBS-004`, and its result renders on `RBS-006` — **with no frontend change**.
- Given a module whose report names a thirteenth block, when the suite runs, then it fails and names the block.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — **None.**

---
id: US-RBS-016
epic: EP-RBS-01
module: runbooks
screens: [RBS-006, RBS-004]
phase: 1
status: ready
blocked_by: []
depends_on: []
journeys: []
rules: [BR-RBS-020, BR-RBS-021]
golden_tests: []
finance_calc: none
---
### US-RBS-016 — As a clerk every result reads the same way

**1 · Details** — As **a clerk**, I want **every runbook's result drawn the same way** — so that **learning one result screen teaches me all twenty-one**.

**Twelve blocks, and that is the whole result vocabulary:** `Verdict` · `KPIs` · `Chain` · `Records` · `Breakdown` · `Reconciled` · `Ranked` · `Sentence` · `Facts` · `Action` · `Row decisions` · `Downloads`. One renderer draws any report from them. **A report naming a thirteenth block is refused at RUN CLOSE, not at render** — so a bad report never reaches a screen and never leaves a half-drawn page behind.

**The report is FROZEN when the run closes.** `runbook_runs.report` holds the composed block list as it was at close. **A later change to a runbook's report function never alters what a past run showed** — the same principle as storing the version, and the reason a result from last month reads exactly as it did.

**The rule that keeps this a vocabulary and not a language:** a thirteenth block needs **three** runbooks that cannot be drawn without it. One runbook wanting a new shape is a runbook that should compose the existing twelve differently.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-RBS-020` | A run's report is composed once, at close, from the twelve block types, and frozen; a later code change never alters a past result | PROPOSED |
| `BR-RBS-021` | The block vocabulary is fixed at twelve; a thirteenth needs three runbooks that cannot be drawn without it | PROPOSED |

**3 · Test Cases**

| TC | Scenario | Expected | Must first fail on |
|---|---|---|---|
| `TC-RBS-16` | Changing a runbook's report function after a run | That run's stored report is **byte-identical** | The report read live at render |
| `TC-RBS-15` | A report containing an unknown block | Refused **at run close**; the run is marked failed and the block named | Refused at render, which leaves a half-drawn screen |
| `TC-RBS-016.1` · **screen** | `RBS-006` over each of the twelve blocks | Every block renders at its build-sheet size, state and tone | A block with no component — it must not fall through to raw JSON |

**4 · Test Data** — One synthetic report exercising all twelve blocks in one run, plus one report with a planted thirteenth. **Runbook 1's own report uses four of the twelve** (`KPIs` · `Chain` · `Records` · `Downloads`), so the other eight are proved on the synthetic report in this phase and re-proved by their runbooks in phases 3 and 5.

**5 · Data Fields / Mapping**

| Field | Screen | DB target | Type | Origin | Validation |
|---|---|---|---|---|---|
| `runbook_runs.report` | `RBS-006` | `runbook_runs` | jsonb | derived at close | validates against the twelve-block schema **before** the run is marked done |
| `runbook_run_records.data` | `RBS-006` Records block | `runbook_run_records` | jsonb | derived | carries per-record extras a block needs — twelve sparkline values, ours and theirs, a bank's reason text |

**6 · Acceptance**
- Given a run closed last month, when it is reopened on `RBS-006` after the report function has changed, then it draws exactly what it drew the day it closed.
- Given a runbook whose report names a thirteenth block, when the run closes, then it is refused and never reaches the screen.

**7 · Finance Calculation** — N/A. Money **inside** a block displays to two decimals over four stored (hard rule 2), and the `Records` block's money cell renderer is the one place that formatting lives.

**8 · Open Questions** — **None.**

---
id: US-RBS-018
epic: EP-RBS-01
module: runbooks
screens: [RBS-002, RBS-003, RBS-004]
phase: 1
status: ready
blocked_by: []
depends_on: [US-RBS-015]
journeys: []
rules: [BR-RBS-024, BR-RBS-025, BR-RBS-026]
golden_tests: []
finance_calc: none
---
### US-RBS-018 — As a clerk I find a runbook by the part of the business it serves

**1 · Details** — As **a clerk**, I want **the template library filtered by the part of the business a runbook serves** — so that **a cashier is not reading past nine things that are not theirs**.

**Sixteen categories, held in code and never free text:** Platform · Onboarding & Cutover · Data Hygiene · Premises · Plans & Rates · Assets · Accounts · Reads · Billing · Collections · Payments · Finance · Work · Customer portal · Business · Data Sync.

⚠ **The category is an ENGINEERING fact, not a label, and three things read it.** The library filters by it. Role visibility **defaults** from it — Owner and Admin see everything; an Admin may widen or narrow per runbook. And **it names the owning module whose ports the runbook may call**: a Collections runbook reaches payments' ports and no other module's, and a Check reaches none.

⚠ **A CATEGORY HOLDING NO RUNBOOK IS NEVER DRAWN.** Twelve templates show **eight** chips, because eight categories hold at least one; **Assets, Accounts, Work, Customer portal and Business draw nothing.** A chip that filters to an empty list is dead UI (hard-won law 2), and the chip row is built **from the templates present**, never from the fixed list.

⚠ **The specification's category name *Service points* is rendered as *Premises***, which is what the product already calls them and where a clerk already navigates (decision log 2026-09-06 — this lane's decision under law 13, not the PO's). A second name for a thing the product has already named is how a clerk learns two vocabularies for one screen.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-RBS-024` | Exactly one category from the fixed sixteen; anything else it touches is a tag; the category names the owning module whose ports it may call | PROPOSED |
| `BR-RBS-025` | A category with no runbook is never drawn as a filter; a new category needs three runbooks that fit nowhere else | PROPOSED |
| `BR-RBS-026` | Onboarding & Cutover sorts first while a cutover plan is open and last once it closes; no other category carries an order rule | PROPOSED |

**3 · Test Cases**

| TC | Scenario | Expected | Must first fail on |
|---|---|---|---|
| `TC-RBS-20` | The library with the twelve shipped templates | Exactly **eight** chips; **none reads Assets or Work** | A chip row built from the fixed list of sixteen instead of from the templates present |
| `TC-RBS-19` · **negative** | A module declaring a category outside the sixteen | Fails the conformance suite at construction | A module declaring `Misc`, added on purpose |
| `TC-RBS-018.1` | An open cutover plan, then a closed one | Onboarding & Cutover sorts **first**, then **last**; no other category moves | Order hard-coded either way |
| `TC-RBS-018.2` · **role** | A Finance user's Templates page | Finance, Payments and Collections templates; **not Platform** | Visibility read from a per-runbook flag with no category default |

**4 · Test Data** — The twelve shipped templates in their catalogue order, spread across eight categories (Platform 1 · Onboarding & Cutover 1 · Billing 3 · Finance 1 · Collections 2 · Payments 1 · Reads 1 · Data Sync 2). One tenant with an open cutover plan and one with a closed one. Actors: an Owner, an Admin, a Finance user, a Billing clerk.

**5 · Data Fields / Mapping**

| Field | Screen | DB target | Type | Origin | Validation |
|---|---|---|---|---|---|
| `runbooks.category` | `RBS-002` chips · `RBS-003` column · `RBS-004` Overview | `runbooks` | enum of sixteen | reference-data | held in code; a value outside the list is refused at load |
| `runbooks.tags[]` | `RBS-002` search | `runbooks` | text[] | reference-data | free within the module; never filters the chip row |
| role visibility | `RBS-002` · `RBS-003` | `runbook_versions.definition` | role list | derived from category, editable per runbook | Owner and Admin always included |

**6 · Acceptance**
- Given the twelve shipped templates, when a clerk opens `RBS-002`, then eight category chips render and none reads Assets, Accounts, Work, Customer portal or Business.
- Given a Finance user, when the library loads, then Platform templates are absent from it.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — **None.** The category **names** were the source's open decision 10 and are settled: the product's own word wins wherever it has one (decision log 2026-09-06).

---
id: US-RBS-038
epic: EP-RBS-01
module: runbooks
screens: [RBS-002, RBS-003, RBS-004]
phase: 1
status: ready
blocked_by: []
depends_on: [US-RBS-018, US-RBS-040]
journeys: []
rules: [BR-RBS-001, BR-RBS-038]
golden_tests: []
finance_calc: none
---
### US-RBS-038 — As an admin I clone a runbook and vary its settings

**1 · Details** — As **an administrator**, I want **to copy a shipped runbook and give the copy its own settings** — so that **commercial accounts can be dunned on a different clock from residential without anyone authoring anything**.

Clone on *Dunning and notices* makes **Commercial accounts**, carrying `origin = cloned`, its own `template_key`, `cloned_from`, and **its own version 1**. Both rows appear on **My runbooks**, each with its own schedule, cap and dry-run state. **The copy's kind is the original's and is immutable** (`BR-RBS-001`), so a cloned Check can never become an Action.

⚠ **This is CONFIGURE and CLONE, never COMPOSE and never AUTHOR** — PO 2026-09-05, *"compose yes, author no"*, **narrowed by PO 2026-09-06 (`BR-RBS-042`): WE compose; a tenant SETS and CLONES.** Cloning varies **input VALUES** — parameters, guards, limits, scope, schedule and which optional steps are on. It writes no new step and it arranges no steps. ⚠ **THIS SENTENCE ENDED *“Composing from a step library is `US-RBS-039` and is phase 5”* UNTIL 2026-09-06, AND THAT IS NO LONGER TRUE:** the step library is **ours**, an internal asset from wave `C`, and `US-RBS-039` is now *set the inputs, and* all *means all*. Each input carries a **tenant-resolved domain** and accepts one value, several or ***all***, with *all* stored as the word and resolved at run start.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-RBS-001` | Kind is declared at creation and never changed — a clone inherits it | PROPOSED |
| `BR-RBS-038` | Every edit makes a new version; a run pins the version that produced it; a template update is offered on a copy and never applied without a person accepting it | PROPOSED |

**3 · Test Cases**

| TC | Scenario | Expected | Must first fail on |
|---|---|---|---|
| `TC-RBS-038.1` | Clone *Dunning*, name it *Commercial accounts*, set the first reminder to 15 days | Both rows on My runbooks, each with its own schedule, cap and dry-run state; the copy is `origin = cloned`, `version = 1` | A clone that shares the original's version row — editing one would move the other |
| `TC-RBS-038.2` · **negative** | Editing a clone's `kind` | Refused | Kind writable after creation |
| `TC-RBS-038.3` · **tenant isolation** | Tenant B holds a clone of the same template | Tenant A's list shows only its own, under RLS `FORCE` | A `template_key` lookup that forgets the tenant |

**4 · Test Data** — *Dunning and notices* as a shipped template; one clone named *Commercial accounts* with a 15-day first reminder and a cap of 200 against the original's 400. Two tenants.

**5 · Data Fields / Mapping**

| Field | Screen | DB target | Type | Origin | Validation |
|---|---|---|---|---|---|
| `runbooks.origin` | `RBS-003` | `runbooks` | enum `shipped` \| `cloned` \| `composed` | derived | set at creation, never edited |
| `runbooks.template_key` · `cloned_from` | `RBS-003` · `RBS-004` Activity | `runbooks` | text · uuid | derived | `cloned_from` NOT NULL when `origin = cloned` |
| `runbooks.key` | — | `runbooks` | text | derived | **unique per tenant**; never rendered (B14 rule 31) |

**6 · Acceptance**
- Given *Dunning*, when an admin presses Clone and names it *Commercial accounts* with a 15-day first reminder, then both rows appear on My runbooks, each with its own schedule, cap and dry run.
- Given the clone, when its kind is edited, then it is refused.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — **None.**

---
id: US-RBS-040
epic: EP-RBS-01
module: runbooks
screens: [RBS-003, RBS-004, RBS-006]
phase: 1
status: ready
blocked_by: []
depends_on: [US-RBS-016]
journeys: []
rules: [BR-RBS-036, BR-RBS-038]
golden_tests: []
finance_calc: none
---
### US-RBS-040 — As an admin I change a runbook and every run still says which version ran it

**1 · Details** — As **an administrator**, I want **every edit to make a new version, and every past run to keep the version that produced it** — so that **a result from last month reads exactly as it did and nobody has to reconstruct what the rules were**.

**Three kinds of change, three routes, one rule for all of them.** A **shipped step's logic** changes as a product release: the template's version increments and a tenant's copy shows **"Template updated · Review →"** and **changes nothing until a person presses it**. A **tenant's settings** — parameters, guards, limits, scope, schedule, optional steps — make a new version row of that tenant's runbook, with who, what and when on the **Activity** tab. A **composed runbook's steps** (phase 5) are a version like any other.

⚠ **THE TRUST RATCHET: an edited ACTION drops back to dry-run only until one clean dry run of the new version has been reviewed** (`BR-RBS-036`). In phase 1 nothing acts, so this is built and asserted here and first *matters* in **phase 2** (it was phase 4 until the 2026-09-06 re-cut, so it now matters one phase later rather than three) — said out loud rather than left to be discovered when the ladder goes live.

**What this deliberately does not do:** change a run that already happened, apply a template update behind an admin's back, or let an edited Action send anything before someone has read a dry run of the edited version.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-RBS-038` | Every edit makes a new version; a run pins the version that produced it and its stored plan and report never change; a template update is offered and never applied silently | PROPOSED |
| `BR-RBS-036` | An edited Action drops back to dry-run only until one clean dry run has been reviewed | PROPOSED |

**3 · Test Cases**

| TC | Scenario | Expected | Must first fail on |
|---|---|---|---|
| `TC-RBS-13` | Editing a runbook after a run | That run's stored version and plan are unchanged | The definition read live at display time |
| `TC-RBS-24` | Edit after a run, then bump the shipped template | The old run's stored report is **byte-identical** and still names v3; the next run names v4; an edited Action refuses a live run until a clean dry run of v4 is reviewed; the copy shows "Template updated" and **its steps are unchanged** | The old run re-rendering with the new version, or the copy silently gaining the step |
| `TC-RBS-040.1` · **screen** | The Activity tab after an edit | The change, the person's name and the time; **no version id rendered as a database id** (B14 rule 31) | An Activity row keyed by `runbook_version_id` |

**4 · Test Data** — *Dunning and notices* at v3 with one closed run against it; the first reminder changed from 10 to 15 days making v4; the shipped template then gaining one step. Actor: Tom, an administrator.

**5 · Data Fields / Mapping**

| Field | Screen | DB target | Type | Origin | Validation |
|---|---|---|---|---|---|
| `runbook_versions.version` · `definition` · `changed_by` · `changed_at` | `RBS-004` Activity | `runbook_versions` | integer · jsonb · uuid · timestamp | derived | append-only; a version row is never updated |
| `runbook_runs.version` | `RBS-006` header · `RBS-004` Runs | `runbook_runs` | integer | derived at run start | pinned; never re-read from `runbooks.current_version` |
| template-update offer | `RBS-003` row | derived from `template_key` + template version | flag | derived | **offered**, never applied |

**6 · Acceptance**
- Given a closed run at v3, when the first reminder is changed to 15 days, then the next run header reads v4 while the closed run still reads v3 with its report unchanged.
- Given the shipped template gains a step, when My runbooks loads, then the copy reads "Template updated · 1 new step · Review →" and **nothing in it has changed**.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — **None.** ⚠ **The template-update rule was decided by the source document on 6 September 2026 and the Product Owner has NOT been asked.** It is recorded here as ours, visible to overrule, exactly as the source records it — not quoted as a ruling.

---
id: US-RBS-041
epic: EP-RBS-01
module: runbooks
screens: []
phase: 1
status: ready
blocked_by: []
depends_on: []
journeys: []
rules: [BR-RBS-022, BR-RBS-039]
golden_tests: []
finance_calc: none
---
### US-RBS-041 — As a developer I reach another module only through a seam I own, and the register knows it

**1 · Details** — As **an engineer**, I want **every reach outside this module to go through a seam file this module owns, with a row in the cross-module interface register** — so that **the platform's ban on cross-module writes is a property of the code and not of a review**.

**One seam file per module read**, named for the pair: `runbooks → customers` · `→ metering` · `→ rating` · `→ billing` · `→ payments` · `→ ledger` · `→ notifications` · `→ tenancy` (settings) · `→ integrations` (a landed batch). Each calls the owner's **selector by name, in process, under the tenant context**. **Every write is one of the thirteen port seams**, and **a Check's seams expose read functions only**.

⚠ **THIRTEEN PORT SEAMS, NOT FOUR.** The source's architecture section says four in five places and lists *raise a work item* among them. **It is stale.** The contract lists thirteen and raising work items is an **engine act**. A lane building four ports and putting the work-item writer among them has built the wrong thing twice.

⚠ **THE SELECTORS THAT DO NOT EXIST YET ARE A PHASE-1 TASK, DONE BEFORE THE FIRST CHECK IS WRITTEN.** Several runbooks read things no module exposes today — a meter's last good day, an account's ladder tier, a premise's usage over 90 days. **The owning module adds the selector; the runbook module never reaches past a seam.** Discovering this during phase 5 rather than inventorying it now is how an HTTP client gets written.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-RBS-039` | A runbook reaches another module only through a seam this module owns, calling the owner's selector or service by name in the same process; every seam is a row in the cross-module interface register; the module never calls the product's own HTTP endpoints and never imports another module's models | PROPOSED |
| `BR-RBS-022` | A runbook reaches another module or a partner only through a named port; work items and audit rows are the engine's to write | PROPOSED |

**3 · Test Cases**

| TC | Scenario | Expected | Must first fail on |
|---|---|---|---|
| `TC-RBS-25` · **gate** | Import census of `06-backend/apps/runbooks` | Every import of another module resolves to a file named `*_seam.py`; each seam names a register row; **no file imports `requests`, `httpx` or another module's models**; a Check's seams expose read functions only | A cross-module model import, or an HTTP client, planted — **the census must first be shown red on it** |
| `TC-RBS-041.1` · **gate** | Every seam file against the interface register | Zero seams without a row | A seam added with no register row, planted |
| `TC-RBS-041.2` | A Check's seam object | Has no write attribute at all | A seam module exporting writes unconditionally |

**4 · Test Data** — The nine read seams and thirteen port seams as they stand at the end of phase 1 — **the port seams exist as declarations and bind no writer until `EP-RBS-04`.** Two planted violations, each added and removed by the test.

**5 · Data Fields / Mapping** — N/A: this story adds no field and no screen. Its artefact is the module's import graph and the cross-module interface register in the database design brief.

**6 · Acceptance**
- Given the module at the end of phase 1, when the census runs, then every cross-module import is a seam, every seam has a register row, and there is no HTTP client anywhere in the module.
- Given a planted `from apps.customers.models import Account`, when the census runs, then it goes **red** and names the file and the line.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — **None.**

---

## What this epic does NOT prove, said out loud

* **No port is bound and nothing is sent.** The thirteen ports exist as declarations and as seams with no writer behind them. `TC-RBS-4` (idempotency), `TC-RBS-3` (the cap), `TC-RBS-8` (a stale approval), `TC-RBS-9` (stop) and `TC-RBS-12` (the audit actor) are **`EP-RBS-04`'s** and are not asserted here — a phase that claimed them would be claiming a check that cannot fail.
* **`TC-RBS-5` (savepoint per record) is proved HERE and only on PostgreSQL.** The engine's per-record savepoint is built in this phase because runbook 1 already runs a per-record step. ⚠ **`config/settings/test.py` hardcodes in-memory SQLite, which has no aborted-transaction state**, so the naive `try/except IntegrityError: continue` passes the entire suite green on every machine and loses the run the first time a real row is refused in production (hard-won law 14). The case runs under `config.settings.local` with `DATABASE_URL`, beside the existing `06-backend/tests/test_*_pg.py` files, and is **marked skipped in red wherever only SQLite is available** (`RB-038`).
* **The work list does not exist yet.** Runbook 1's findings are run records. `work_items` is created in this phase's migration and **written in `EP-RBS-03`**, where `TC-RBS-10` proves that thirty daily sweeps over one missing read produce **one** item thirty days old rather than thirty items.
