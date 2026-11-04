# J-RBS-2 — Prove it on their data (an implementer prices twenty-five of the utility's own accounts before go-live, opens the two red cells, fixes the rate that refused them, and watches the grid move 21 → 23 — because the refusal on screen was the engine's own)

---
id: J-RBS-2
tier: 2
rules: [BR-RBS-002, BR-RBS-010, BR-RBS-011, BR-RBS-013, BR-RBS-014, BR-RBS-021]
stories: [US-RBS-004, US-RBS-005]
# ⚠ **NOT ACTIVATED, and there is nothing yet to activate against.** At HEAD there is no
# `apps/runbooks` and no `J-RBS-2.spec.ts`. Written as the HANDOFF CONTRACT before the
# code, per `CR-075`'s five-phase plan.
# ⚠ **AND THE RESULT SCREEN THIS JOURNEY READS IS NOT DRAWN.** `RBS-006-R23` and
# `RBS-006-R24` do not exist in `wireframes/` — runbooks 23–27 have a SETUP frame and no
# RESULT frame, and `08-screen-layouts.md` says what that means in its own words: *"A
# setup screen with no result screen is a runbook that cannot finish, so the five
# reserved runbooks are not buildable from this pack alone."* Every result assertion
# below therefore comes from `US-RBS-004`/`US-RBS-005` and `12-the-contract.md`, never
# from a sheet, and each one says so.
# ⚠ **G12 REFUSES THIS `id:` — `DEF-RBS-4247`, and it is a fault in the gate, not here.**
# `VALID_JOURNEY_ID_RE` is `^[JT][A-Za-z0-9]*(?:-\d+)?$` and refuses `J-RBS-2`, while the
# wiring index's own `^id: ([JT]\S+)` reads it correctly. G12 is PO-ratified (G1–G16), so
# a lane may not widen it; the row carries the one-line fix. G12 is separately red on a
# stale index dating to 2026-09-05, which is what has been hiding this.
#
# `rules:` and `stories:` are `04-flows.md` §5's index for `J-RBS-2` plus the two stories
# whose own frontmatter names it.
---

⚠ **WALKED IN A BROWSER 2026-09-07, AND THE FIGURES BELOW ARE THE CARD'S RATHER THAN THE
RUN'S.** `10-scripts/render-checks/rbs-g-coverage-grid.mjs` signs in, opens the grid's stored
run, reads its four KPI tiles and its sentence off the page, counts the cells, **presses one**
and lands on that account's own test bill. Every check passes. What it reads is **1 clean ·
0 estimated · 2 refused over 3 cells** on the seeded utility, not 21 · 2 · 2 over 25 —
because **the six-service fixture §4 describes below does not exist in this repository** and
the demo utility holds three plan-and-cycle combinations. **The shape is proved and the
estate is not the estate this journey was written for**, and the two are stated apart rather
than blended: steps 1, 2, 5, 8 and 9 are walked; step 3's *21 clean* and step 7's *21 → 23*
wait on that fixture and on `POST /runbooks/{key}/runs` (wave `L`), because nothing in this
product can start a run from a screen yet.

⚠ **AND STEP 2's *press Run ▶* IS NOT WHAT THE WALKTHROUGH DOES.** The runs are made by
`rbs_g_seed_coverage.py`, through `services.run_to_completion` — the same engine call the
future endpoint will make — so everything from the stored run onwards is proved and the
click-to-start half is `L`'s.

**Intent.** This is the go-live artefact and the sales artefact at once, and it exists
because *"a utility that has seen 25 green cells on its own data before go-live behaves
differently from one that has not."* Runbook 24 (**Coverage grid**) picks one account per
plan × service mix × cycle, prices each one through runbook 23 (**Test bill**), and
groups the outcomes. **Both are Checks. No bill number is consumed and nothing is
written** — a construction property, not a promise (`BR-RBS-002`).

**The one assertion that would catch a wrong build is not the count.** It is this: **the
refusal sentence on the red cell is the RATING ENGINE'S OWN, not a second
implementation's.** A test bill that re-prices is worse than no test bill — it is green
while the real run refuses, and the utility goes live on a demonstration that proved
nothing. The journey catches it by **changing the rate and watching the refusal go
away**: a refusal composed inside this module would not move when a rate block did. That
is step 7, and it is why the journey is worth running in a browser rather than as a unit
test.

**Upstream leaves.** `J-RBS-1`'s tenant, in the state that journey leaves it in — **2
blockers, one of them the rate coverage above 20,000 gallons.** This journey closes that
one from the other end, on a bigger estate.

The estate is the **six-service fixture** of `US-RBS-005` §4 — **Electric · Water · Gas ·
Trash · Storm water · Broadband, 40 accounts** — spanning enough plans, service mixes and
cycles to fill **25 cells**, and seeded with exactly three deliberate facts:

| # | Seeded | What it produces | Asserted as |
|---|---|---|---|
| 1 | **One plan whose rate blocks stop at 20,000 gallons** | **2 refused** cells | the engine's own refusal sentence, twice |
| 2 | **Two accounts whose latest read is an estimate** | **2 estimated** cells | billed, but not on a real read |
| 3 | **3 sample records** | **nothing** | they are never picked, not merely never acted on |

⚠ **The pack names no tenant for this fixture.** The routes below read `silvercreek`
because every wireframe does; **the tenant slug is not an assertion of this journey**,
only the estate is. Actor: **the implementer**, at a utility that has not gone live.
Rounding is Settings-owned and drawn dashed with *Open settings →*: **money stored to 4
decimals, percentages to 6, both displayed to 2** (hard rule 2).

**The journey's clock.** Grid run 1, then both red cells opened, then the rate block
added, then grid run 2 — one sitting. Run 3 (step 4) is an immediate repeat of run 1 over
an unchanged estate, and exists only to prove the pick is deterministic.

**What this journey may never do, and it is worth saying before the table.** ❄️ **B4 and
B5 are FROZEN.** Nothing here adds, moves or reinterprets a signed money figure. If a
cell disagrees with a golden test, **the defect is in the engine or in the fixture, never
in the runbook**, and a figure that would move is a finance re-sign through HUMAN-GUIDE §6
that stops this journey dead rather than being worked around. Of the 61 signed golden
tests **14 are engine-verified** (`GT-1`–`11`, `16`, `24`, `47`); the harness's **33
checks are document self-consistency and import no application code**. Quote both, never
one.

| # | Actor · action · screen | Expected outcome (contract — what this step leaves) | Downstream assertions (record · screen · audit · books) | Rule |
|---|---|---|---|---|
| 1 | **The implementer** opens **Templates** (`RBS-002.1`) and reads the *Coverage grid* card, then **+ Add to my runbooks** | The card's *What it can touch* reads **Writes · Nothing · Sends · Nothing · Reads · Accounts, plans, reads**. A `runbooks` row is created: `kind = check` **immutable after creation**, `origin = shipped`, `template_key` set, `current_version = 1` | ⛔ ***What it can touch* is the ports allow-list RENDERED, not a description somebody typed.** It reads *Nothing* because `ports[]` is empty, and that is why a Check can be trusted: **the screen states capability, not intention**. ✅ `RBS-002.1` draws **eight** category chips for twelve templates — a category with no template draws none, because a chip that filters to nothing is dead UI (`RB-019`) | **BR-RBS-001** · **BR-RBS-002** · `RB-019` |
| 2 | The implementer opens `RBS-004-R24` and presses **Run ▶** | Scope is decided: *25 accounts, one per plan · service mix · cycle, chosen automatically* · *Period: the next cycle* · **Never include: Sample**. `POST /runbooks/coverage-grid/runs`. `runbook_runs.scope_fingerprint` **pins the 25 subject ids at start** | ⛔ `TC-RBS-005.3`: **no sample account is picked, whatever the plan spread** — and the guard sits in the PICK, not in the act. **Must first fail on** a build that omits the sample guard from the pick and relies on there being no act: a Check has no act, so that version never refuses anything. ⛔ Guards are evaluated **before any step** and cannot be switched off; `RBS-004.4` draws them with **no control beside them** | **BR-RBS-014** · `TC-RBS-005.3` · `RBS-004.4` |
| 3 | The run walks its **three steps, all read** — pick · price each through the real engine · group by outcome | **25 `runbook_run_records`**, one per cell, each `planned_action = report`, each carrying `outcome` ∈ `clean` \| `estimated` \| `refused`, and **every `refused` row carrying `reason` and `fix_route`**. The result reads **21 clean · 2 estimated · 2 refused** | ⛔ `TC-RBS-005.1` **must first fail on** a grid that counts cells it did not price. ⛔ **Step 2 is the whole story:** each cell is runbook 23's own path, which is the rating engine's — *the engine is called; it is not copied*. ⛔ `TC-RBS-004.3`: the same account through this grid and through a real bill run produces an **identical line set and identical amounts to four decimals**; **plant a second pricing implementation and it must go red** | **BR-RBS-010** · **BR-RBS-011** · `TC-RBS-005.1` · `TC-RBS-004.3` |
| 4 | **The determinism leg.** Run it again immediately over an unchanged estate | **The same 25 accounts, in the same order**, and the same `scope_fingerprint` | ⛔ `TC-RBS-005.2` **must first fail on** a random or `ORDER BY`-less pick. **Without this the journey's headline is not a measurement**: if the 25 are re-picked at random, *"the grid moved from 21 to 23"* says nothing at all. The pick is a stated function of plan, service mix and cycle, and when the estate changes the pick changes **for a reason a person can read** | **`US-RBS-005`** §1 · `TC-RBS-005.2` |
| 5 | The implementer **clicks a red cell** | It opens **that account's test bill** (`RBS-006-R23`, runbook 23), which shows **ONE refusal sentence naming the service and the date** — not a stack trace, not a multi-sentence explanation | ⛔ `TC-RBS-004.2`: **one** sentence, and where it is a refusal it is **six words or fewer** (B14 rule 33 as ratified — ⚠ not `CLAUDE.md`'s one-line summary of it, which covers only the half `G33` enforces; that gap is `DEF-GOV-4242`). ⛔ **No bill number is consumed** — `billing`'s number series is byte-identical across the whole journey (`TC-RBS-004.1`, **must first fail on** a test bill that reserves one). ⛔ No `invoices` row, no `invoice_lines` row, no `journal_lines` row: hard rule 4 is not approached, because there is no writer to approach it with | **BR-RBS-002** · **BR-RBS-013** · B14 33 · `TC-RBS-004.1` · `TC-RBS-004.2` |
| 6 | The implementer reads the sentence, and it names the missing block | The refusal's `reason` is the string the **rating engine** returned; `runbook_run_records.reason` stores it verbatim and the module **composes nothing of its own** | ⛔ **THE ASSERTION THIS JOURNEY EXISTS FOR, stated as a data check before it is stated as a screen check:** the refusal text on `RBS-006-R23` and the refusal text the rating engine returns for that account are **the same string**. A module that formats its own sentence around an engine error code passes this and fails step 7 | **BR-RBS-011** · `US-RBS-004` §5 |
| 7 | **The implementer adds the rate block above 20,000 gallons and re-runs the grid** | **THE GRID MOVES 21 → 23 CLEAN**, `2 → 0` refused, the 2 estimated **unchanged**. A third `runbook_runs` row with its own frozen report; the first two are untouched and reopen exactly as they drew | ⛔ **THE ONE THAT CATCHES A WRONG BUILD:** *the refusal that vanished was the engine's own sentence.* `TC-RBS-005.4` **must first fail on** a refusal composed by this module — **it would not change when the rate did**, so the two cells stay red and the grid stays at 21 while every count, every fingerprint and every other assertion in this journey remains correct. ⛔ The 2 **estimated** cells must NOT move: a build that treats *estimated* as a kind of refusal quietly reads 25 clean and looks like a better result | **BR-RBS-011** · `TC-RBS-005.4` |
| 8 | **More plans than cells (negative).** An estate whose plan × mix × cycle spread exceeds 25 | The pick **states what it left out** and the count on screen says so | ⛔ `TC-RBS-005.5` **must first fail on** a silent `LIMIT 25` — which is the same failure mode as a cap that truncates instead of refusing, one screen along. ✅ Server-side paging applies to the grid's underlying record list exactly as to every other list, *even though 25 cells fit on one page today* — **a cap-free path at 25 is what makes it cap-free at 25,000** (`NFR-3`, `NFR-5`) | `TC-RBS-005.5` · `NFR-3` · `NFR-5` |
| 9 | **The block vocabulary (static).** The grid is drawn | It is the **`Records` block in its GRID DISPLAY MODE** — not a thirteenth block and not a new screen | ⛔ `TC-RBS-16`: a report naming a thirteenth block is refused **at close**, never at render. ✅ `BR-RBS-021` holds, and this is the contract paying for itself: **the highest-value screen in phase 2 costs a display mode on a component phase 1 already built.** ⚠ **Which is also this phase's hard dependency:** phase 1 must ship the grid mode or there is nothing here to draw on | **BR-RBS-021** · `TC-RBS-16` |
| 10 | **ISOLATION** — a second tenant holding an account with the same number | Picking by number without the tenant context is **refused**; RLS `FORCE` on | ⛔ `TC-RBS-7` **must first fail on** an account lookup by number with no tenant context. ✅ Every read of `rating`, `billing`, `metering` and `customers` goes through a seam file **this module owns**, calling the owner's selector by name, in process, under the tenant context — **no HTTP client and no import of another module's models** (`TC-RBS-25`) | hard rule 1 · **BR-RBS-039** · `TC-RBS-7` |
| 11 | **INVARIANCE** | — | **Zero rows written outside this module's seven tables**, across all three runs. **No bill number, no invoice, no journal line, no notification, no audit money row.** ❄️ **B4 and B5 unchanged**: this journey adds no figure to the golden set and asserts none of its own arithmetic — it counts outcomes. `US-RBS-005` §7 is the sentence to keep: *"The grid adds no arithmetic of its own — not a sum, not an average, not a total."* | **BR-RBS-002** · **BR-RBS-013** · hard rules 2, 4, 7 |

**This journey leaves (for downstream).** A six-service estate whose coverage grid reads
**23 clean · 2 estimated · 0 refused**, with a deterministic 25-account pick that a later
run can be compared against · **three `runbook_runs` rows** with frozen reports, so the
before-and-after is evidence rather than a memory · a rate schedule with a block above
20,000 gallons, which is also the second of `J-RBS-1`'s three blockers closed · **no bill
number consumed and no row written outside this module.** **Downstream:** `EP-RBS-03`'s
runbook 2 (*Ready for cutover?*) attaches a run like these to a cutover plan item as its
evidence (`cutover_plan_items.last_run_id`, `evidence_ref`); `J-RBS-3` is the first
journey in which a runbook is allowed to write anything at all.

## Boundaries — what this journey stops at, and why

| # | Not asserted | Because |
|---|---|---|
| a | **Any region, copy string or size on the result screen.** | **`RBS-006-R23` and `RBS-006-R24` ARE NOT DRAWN.** Runbooks 23–27 carry a setup frame and no result frame, and the pack says plainly that a setup screen with no result screen is a runbook that cannot finish. Every result assertion above is read from `US-RBS-004`, `US-RBS-005` and `12-the-contract.md`. **A build lane must not infer the missing frames from `RBS-006-R1`** — that is a different runbook's composition |
| b | **The refusal sentence's exact words.** | The pack requires that it is **one sentence**, that it **names the service and the date**, that it is **six words or fewer**, and above all that it is **the engine's own**. It nowhere quotes the string, and quoting one here would create the second implementation this journey exists to refuse |
| c | **The tenant slug.** | The pack names no tenant for the six-service fixture. `silvercreek` is used for the routes because every wireframe does; the estate is the assertion |
| d | **Which two accounts are the estimated ones.** | The epic seeds *two accounts whose latest read is an estimate* and names neither. Naming them here would be this journey's fixture invention rather than the pack's, and the count is what the grid asserts |
| e | **A comparison with the last issued bill.** | `TC-RBS-004.4` (line by line, difference per line, **a line present in one and not the other is shown rather than dropped** — must first fail on an inner join) belongs to runbook 23 on an account with an issued prior bill. This journey's estate is pre-go-live and has none |
| f | **That the grid re-picks when the estate changes.** | Stated by `US-RBS-005` — *"when the estate changes, the pick changes for a reason a person can read"* — and not exercised: step 7 changes a RATE, not the estate, which is exactly why the same 25 accounts are still comparable across it |
| g | **That this file can be activated.** | `DEF-RBS-4247`: G12 refuses this `id:`. And phase 2 depends on a phase-1 component (`Records` grid mode) that does not exist |
