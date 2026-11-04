# EP-RBS-02 — Prove it on their data: the test bill and the coverage grid

**Module:** runbooks · **Phase:** 4 of 5 — **was 2, re-cut 2026-09-06; the epic is NOT renumbered** · **Screens:** `RBS-002` template cards · `RBS-004` setup renderer (`RBS-004-R23`, `RBS-004-R24`) · `RBS-005` run wizard · `RBS-006` result renderer (`RBS-006-R23`, `RBS-006-R24`) · **Status:** draft (written 2026-09-06)

⚠ **PHASE ORDER RE-CUT 2026-09-06 — THIS EPIC MOVED FROM PHASE 2 TO PHASE 4 AND IS NOT RENUMBERED.** Two
Product Owner rulings that day put the integration runbooks first: *"once you have foundation I want to
prioritise runbook related to integration first and then rest"*, then *"For me integration related to
accounting, payment provider, emails, GIS are important - over other"*. **Every integration-driven runbook
is an Action and cannot run before the acting half exists, so `EP-RBS-04` is now phase 2** and this epic's
two Checks are built after it, in phase 4, alongside `EP-RBS-03`. **Waves `F` and `G` are unchanged; only
their position moved.** Order: [`../10-execution-plan.md`](../10-execution-plan.md) §1.

⚠ **AND THIS EPIC CARRIES THE PRICE OF THE RE-CUT.** §1 below says why this work is second and not fifth —
*"it is the go-live artefact and the sales artefact at once"*. **Under the new order it is fourth**, so a
utility sees 25 green cells on its own data **three phases later than it would have**. That is stated
rather than sold, and it is the Product Owner's trade to have made: the integration runbooks come first.

⚠ **THE PHASE-1 DEPENDENCY IN §1 IS UNCHANGED AND GETS HARDER TO REMEMBER.** The `Records` block's grid
display mode and the other seven shared pieces are still **task `C1a`, phase 1** — now three phases before
they are needed rather than one, which makes deferring them look cheaper than it is.


## Scope

**In:** two Checks on the engine phase 1 proved, over the **existing** pricing path. **Test bill** (runbook 23) prices one account exactly as the bill run would, explains every line, and **consumes no bill number**. **Coverage grid** (runbook 24) prices **25 accounts — one per plan × service mix × cycle** — and shows the estate as a grid of *billed clean · billed with an estimate or default · refused*, each red cell opening that account's test bill with **the engine's own refusal sentence**.

⚠ **THIS PHASE DEPENDS ON A PIECE OF PHASE-1 UI AND CANNOT BE BUILT WITHOUT IT: the `Records` block's GRID DISPLAY MODE.** The coverage grid **is** that mode — not a new block and not a new screen (`BR-RBS-021` holds) — so it is built in phase 1 alongside the other five shared components the blocks need (`VerdictBand`, `Chain`, `ContributionBars`, `OutcomeCard`, `SettingsOwnedField`, `PercentCell`, and the sparkline cell), all of which were **verified absent from `07-frontend/src/components/` on 2026-09-06**. **A phase 1 that ships the renderer without the grid mode leaves this phase with nothing to draw on**, which is why it is named here rather than assumed.

**Out:** any change to the rating engine, to B4's money math or to B5's golden tests. **This phase writes no pricing code.** It calls the pricing path that exists and renders what comes back. Anything that would move a ❄️ FROZEN B4/B5 figure is a finance re-sign through HUMAN-GUIDE §6 and stops this phase dead rather than being worked around.

**Exit test of the phase — a demonstration, not an opinion.** On a utility's own seeded estate, an implementer runs the coverage grid and reads **21 clean · 2 estimated · 2 refused**; clicking a red cell opens that account's test bill and the refusal sentence on screen is **the engine's own** — not a second implementation's. Fixing the rate that caused it and re-running moves the grid to **23 clean** (journey `J-RBS-2`).

⚠ **WHY THIS WORK IS EARLY AND NOT FIFTH — AND IT IS NOW FOURTH, NOT SECOND (2026-09-06 re-cut).** It is the go-live artefact and the sales artefact at once: *"a utility that has seen 25 green cells on its own data before go-live behaves differently from one that has not"*, and no incumbent can show a prospect their own data producing correct bills before they sign anything. It also costs almost nothing to build, because the engine is phase 1's and the pricing path already exists — which is exactly why it must not be deferred behind the acting half.

⚠ **THIS EPIC STILL BINDS NO WRITER — BUT PHASE 4 IS NOT A PHASE THAT BINDS NONE.** Both runbooks here are Checks, and after the 2026-09-06 re-cut they are built in phase 4, by which point phase 2 has bound all thirteen ports. **The property is this epic's, not its phase's**, which is a sharper claim than the one this line used to make. **No bill number is consumed and nothing is written**, and that is a construction property, not a promise (`BR-RBS-002`).

## Capability matrix (list screens only — B9 conformance)

| Screen | Search fields | Filters | Default sort | Sortable | Columns default/available | Row actions | Bulk actions | Export |
|---|---|---|---|---|---|---|---|---|
| `RBS-006-R24` Records block, **grid display mode** | account | outcome (clean · estimated · refused) · plan · cycle | plan, then cycle | plan · cycle · outcome | account · plan · service mix · cycle · outcome / + refusal sentence · amount | Open test bill | — | the two result files |

The grid is **the `Records` block in its grid display mode**, not a thirteenth block (`BR-RBS-021` holds). The test bill's result is `KPIs` · `Records` · `Reconciled` · `Sentence` · `Downloads`. **Server-side paging applies to the grid's underlying record list exactly as to every other** (`NFR-3`), even though 25 cells fit on one page today — a cap-free path at 25 is what makes it cap-free at 25,000.

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
id: US-RBS-004
epic: EP-RBS-02
module: runbooks
screens: [RBS-002, RBS-004, RBS-005, RBS-006]
phase: 4
status: ready
blocked_by: []
depends_on: [US-RBS-001, US-RBS-015, US-RBS-016]
journeys: [J-RBS-2]
rules: [BR-RBS-002, BR-RBS-010, BR-RBS-011, BR-RBS-013]
golden_tests: [GT-1, GT-2, GT-3, GT-4, GT-5, GT-6, GT-7, GT-8, GT-9, GT-10, GT-11, GT-16, GT-24, GT-47]
finance_calc: reads only — no new money math
---
### US-RBS-004 — As a clerk I price one account without billing it

**1 · Details** — As **a billing clerk, and as an implementer before go-live**, I want **to price one account exactly as the bill run would and see every line explained** — so that **I can answer "what would this customer's bill be" without issuing anything**.

**Four steps, all read.** (1) Load the account, unit, plan and reads **as the bill run would see them on bill day**. (2) **Price through the real engine — the same code path as the run, never a second implementation.** (3) Explain every line: base, each block, taxes, fees, prorations, **in words**. (4) Compare with the last issued bill, line by line, difference per line.

**It produces either a complete priced bill with every line explained, or ONE refusal sentence naming the service and the date.** No bill number is consumed and nothing is written.

⚠ **STEP 2 IS THE WHOLE STORY AND IS THE ONE A LANE WILL GET WRONG.** A test bill that re-implements pricing is worse than no test bill: it would be green while the real run refused, and the utility would go live on a demonstration that proved nothing. **The rating engine is called; it is not copied.** `J-RBS-2`'s assertion is written to catch exactly this — *the refusal sentence on screen is the engine's own, not a second implementation's*.

⚠ **THE BILLING-CODE GATE IS OPEN AND `GT-1..61` ARE THE BILLING-MATH CONTRACT.** This story adds no figure to it. Of the 61 signed golden tests, **14 are engine-verified** (`GT-1`–`11`, `16`, `24`, `47`); the harness's **33 checks are DOCUMENT self-consistency and import no application code**. Quote both, never one — `G64` fails any live document quoting `33/33` without saying *engine-verified*.

Rounding is **from Settings, read-only on the card, dashed with "Open settings →"**: money stored to **4** decimals, percentages to **6**, both **displayed to 2**, rounded only at finalization or display (hard rule 2, B4).

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-RBS-002` | A Check is constructed without action ports — no bill number is consumed because there is no writer to consume one | PROPOSED |
| `BR-RBS-010` | Every record states the rule that decided it, in words a clerk can read — here, every line of the bill | PROPOSED |
| `BR-RBS-011` | A refusal names its fix route | PROPOSED |
| `BR-RBS-013` | No action may edit an issued invoice, a payment or a journal entry | **CONFIRMED — restates hard rule 4** |

**3 · Test Cases**

| TC | Scenario | Expected | Must first fail on |
|---|---|---|---|
| `TC-RBS-004.1` | A billable account on the two-service fixture | Every line explained — base, each block, tax, fee, proration — and **`billing`'s number series is untouched** | A test bill that reserves or consumes a bill number |
| `TC-RBS-004.2` | An account whose Sewer read is missing | **One** refusal sentence naming the service and the date, six words or fewer where it is a refusal (B14 rule 33) | A stack trace, or a multi-sentence explanation |
| `TC-RBS-004.3` · **the one that matters** | The same account through the test bill and through a real bill run | **Identical** line set and identical amounts to four decimals | A second pricing implementation — plant one and it must go red |
| `TC-RBS-004.4` | Comparison with the last issued bill | Line by line with the difference per line; a line present in one and not the other is shown, not dropped | An inner join, which silently hides new and removed lines |
| `TC-RBS-7` · **tenant isolation** | Picking an account while another tenant holds one with the same number | Refused; RLS `FORCE` on | An account lookup by number without the tenant context |

**4 · Test Data** — The **two-service** fixture (Water and Sewer, 60 accounts, 58 premises, 62 meters) and the **six-service** fixture (Electric, Water, Gas, Trash, Storm water, Broadband, 40 accounts) — the second exists to prove scope and coverage across a mixed estate. One account with a missing Sewer read for the refusal case. One account with an issued prior bill for the comparison. **Money figures are asserted to four decimals and read off the screen at two.**

**5 · Data Fields / Mapping**

| Field | Screen | DB target | Type | Origin | Validation |
|---|---|---|---|---|---|
| `account` · `period` · `services` | `RBS-004-R23` Scope | `runbook_versions.definition` | ref:object · window · derived | user-input | one account; period is a cycle or an as-at date |
| `period.as_at` — **THE DATE THAT DECIDES THE PRICE** | `RBS-004-R23` Scope · `RBS-006-R23` KPI tile *Priced as at* | `runbook_versions.definition` | date | user-input, defaults to the period end | ⚠ **BUILT 2026-09-06 (`CR-075` wave F, judgment `J9`) AFTER A REAL RUN, NOT AFTER A READING.** `BR-RAT-007` prices on the SERVICE date, and a cycle run prices on its **BILL DAY**: the seeded July bills carry `service_date = 2026-08-02` and the water rate moved from `$4.00` to `$4.24` a kgal on 1 August, so re-pricing July at the period END answers **$158.10** on `AC-2026-00001` where the customer was billed **$160.52**. Neither figure is wrong — the row above already said *"a cycle, or an as-at date"* and only the first half had been built. **The result screen states which date priced the run**, because a clerk who cannot see it would report a fault in a bill that is correct. |
| `compare_with` · `show` · `rounding` | `RBS-004-R23` Parameters | `runbook_versions.definition` | enum · enum · **ref:setting** | user-input / settings | rounding is read-only and rendered from Settings with a link |
| every priced line | `RBS-006-R23` Records | `runbook_run_records.data` | jsonb | **derived from the rating engine** | amounts `NUMERIC` to 4 decimals; displayed to 2 |
| refusal sentence | `RBS-006-R23` Sentence block | `runbook_run_records.reason` | text | **the engine's own** | never composed in this module |

**6 · Acceptance**
- Given a billable account, when a clerk runs Test bill, then every line is explained and **no bill number is consumed**.
- Given an account with no Sewer read in the window, when Test bill runs, then it returns **one** refusal naming the service and the date.
- Given the same account, when a real bill run prices it, then the amounts match the test bill to four decimals.

**7 · Finance Calculation** — **Reads only; this story writes no money math.** It calls the rating engine's own path and renders the result. Every figure it shows is B4's, and any disagreement between this screen and a bill is a defect in this story, never a reason to change B4 — which is ❄️ FROZEN and moves only by a finance re-sign through HUMAN-GUIDE §6.

**8 · Open Questions** — **None.**

---
id: US-RBS-005
epic: EP-RBS-02
module: runbooks
screens: [RBS-002, RBS-004, RBS-005, RBS-006]
phase: 4
status: ready
blocked_by: []
depends_on: [US-RBS-004]
journeys: [J-RBS-2]
rules: [BR-RBS-002, BR-RBS-011, BR-RBS-014, BR-RBS-021]
golden_tests: []
finance_calc: reads only — every cell is US-RBS-004's own path
---
### US-RBS-005 — As an implementer I see coverage across 25 accounts

**1 · Details** — As **an implementer at go-live, and as a salesperson before one**, I want **the whole estate priced as a grid** — so that **a utility sees its own accounts produce correct bills before it commits, and I know which plan is broken rather than that something is**.

**Three steps, all read.** (1) Pick one account per plan, service mix and cycle — **a deterministic pick, so two runs compare**. (2) Price each one through the real engine — **runbook 23 on each cell**. (3) Group by outcome: clean · estimated or defaulted · refused, **with the refusal sentence**.

**25 cells, one per plan × service mix × cycle.** The result reads **21 clean · 2 estimated · 2 refused**, and **each cell opens that account's test bill**. **Sample records are never included.**

⚠ **THE DETERMINISTIC PICK IS WHAT MAKES THE GRID AN ARTEFACT RATHER THAN A SNAPSHOT.** If the 25 are re-picked at random, two runs cannot be compared and *"the grid moved from 21 to 23"* is not a measurement. The pick is a stated function of plan, service mix and cycle; when the estate changes, the pick changes for a reason a person can read.

⚠ **THE GRID IS THE `Records` BLOCK'S GRID DISPLAY MODE.** No thirteenth block; `BR-RBS-021` holds. That is the contract paying for itself: the highest-value screen in phase 2 costs a display mode on a component phase 1 already built.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-RBS-002` | A Check is constructed without action ports | PROPOSED |
| `BR-RBS-011` | A refusal names its fix route; a refusal with no route is a defect in the runbook | PROPOSED |
| `BR-RBS-014` | A sample record is never acted on — and here, never picked | PROPOSED |
| `BR-RBS-021` | The block vocabulary is fixed at twelve; the grid is a display mode of `Records` | PROPOSED |

**3 · Test Cases**

| TC | Scenario | Expected | Must first fail on |
|---|---|---|---|
| `TC-RBS-005.1` | The go-live fixture | **25 cells: 21 clean · 2 estimated · 2 refused**, and each cell opens that account's test bill | A grid that counts cells it did not price |
| `TC-RBS-005.2` | Two runs over an unchanged estate | **The same 25 accounts**, in the same order | A random or `ORDER BY` -less pick |
| `TC-RBS-005.3` | A tenant holding sample accounts | **No sample account is picked**, whatever the plan spread | The sample guard omitted from the pick rather than from the act |
| `TC-RBS-005.4` · **journey `J-RBS-2`** | Fix the rate above 20,000 gallons and re-run | The grid moves **21 → 23** clean, and the refusal that vanished was the engine's own sentence | A refusal composed by this module — it would not change when the rate did |
| `TC-RBS-005.5` | An estate with more plans than cells | The pick states what it left out rather than silently truncating; the count on screen says so | A silent `LIMIT 25` |

**4 · Test Data** — An estate spanning **enough plans, service mixes and cycles to fill 25 cells**, built on the six-service fixture, with: one plan whose rate blocks stop at 20,000 gallons (→ 2 refused), two accounts whose latest read is an estimate (→ 2 estimated), and **3 sample records that must never appear**. The same rate fix as `J-RBS-2` moves it to 23.

**5 · Data Fields / Mapping**

| Field | Screen | DB target | Type | Origin | Validation |
|---|---|---|---|---|---|
| `cells` · `refusals` · `repick` | `RBS-004-R24` Parameters | `runbook_versions.definition` | enum · enum · enum | user-input | typed |
| the 25 subject refs | — | `runbook_runs.scope_fingerprint` + `runbook_run_records.subject_id` | uuid list | **derived, pinned at run start** | deterministic; two runs over an unchanged estate produce the same fingerprint |
| cell outcome | `RBS-006-R24` Records (grid) | `runbook_run_records.outcome` | enum `clean` \| `estimated` \| `refused` | derived | every `refused` carries `reason` and `fix_route` |

**6 · Acceptance**
- Given the go-live fixture, when an implementer runs the coverage grid, then 25 cells render as **21 clean, 2 estimated, 2 refused** and a red cell opens that account's test bill.
- Given the estate is unchanged, when it is run twice, then the same 25 accounts are picked in the same order.
- Given the missing rate is added, when it is re-run, then the grid reads **23 clean**.

**7 · Finance Calculation** — **Reads only.** Every cell is `US-RBS-004`'s own path, which is the rating engine's. The grid adds no arithmetic of its own — not a sum, not an average, not a total. It counts outcomes.

**8 · Open Questions** — **None.**

---

## What this epic does NOT prove, said out loud

* **Nothing here schedules.** Both runbooks are manual. The pre-bill sweep that runs *without anyone opening the product* is `EP-RBS-03`.
* **Nothing here writes, and no port is bound.** The result files are downloads composed from run records; the two result screens have **no `Action` block**.
* **The two result screens were NOT DRAWN in the source.** Runbooks 23 and 24 are *reserved definitions*: their scope, parameters and steps are drafted from the catalogue and **their result screens are not yet drawn**. ⚠ **Until they are drawn, `RBS-006-R23` and `RBS-006-R24` have no build sheet to be compared against**, and hard-won law 6 — diff the running app against the design — cannot be performed on them. **The frames are the first task of this phase**, before any component is written, and a lane that builds the result from this text alone has built a screen nobody has approved.
