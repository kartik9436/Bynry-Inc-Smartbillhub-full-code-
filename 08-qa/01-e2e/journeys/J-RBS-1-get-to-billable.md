# J-RBS-1 — Get to billable (a clerk presses one button, reads the three things stopping the bill, fixes the tax region, re-runs — and the work item that named it closes itself)

---
id: J-RBS-1
tier: 2
rules: [BR-RBS-001, BR-RBS-002, BR-RBS-010, BR-RBS-011, BR-RBS-017, BR-RBS-022, BR-RBS-023]
stories: [US-RBS-001, US-RBS-006]
# ⚠ **NOT ACTIVATED, and there is nothing yet to activate against.** At HEAD there is no
# `apps/runbooks`, no `07-frontend/src/features/runbooks/`, and no `J-RBS-1.spec.ts`.
# Written as the HANDOFF CONTRACT before the code, which is what `CR-075`'s five-phase
# plan asks for.
# ⚠ **G12 REFUSES THIS `id:`, AND THAT REFUSAL IS `DEF-RBS-4247`, NOT A FAULT IN THIS
# FILE.** `10-scripts/gates/g12_journeys.py`'s `VALID_JOURNEY_ID_RE` is
# `^[JT][A-Za-z0-9]*(?:-\d+)?$` — it accepts `J63` and `T3P-02` and refuses `J-RBS-1` —
# while the wiring index generator's own `^id: ([JT]\S+)` reads `J-RBS-1` correctly and
# indexes it. Gate and generator disagree, and the gate's refusal sentence ("the wiring
# index cannot read it") is false for this id. The id is the one the module cites 38
# times across ten files; renaming it here would manufacture the phantom citation this
# file exists to close. G12 is PO-ratified (G1–G16) so a lane may not widen it —
# `DEF-RBS-4247` carries the one-line fix.
# ⚠ **G12 IS ALSO RED FOR A REASON THAT PREDATES THIS FILE**, and that red hides the one
# above: the journey index has been STALE since 2026-09-05 (`f28d4a2f`) because `CR-069`
# has since built `US-INT-027`, `033`, `040` and `041`. G12 returns on staleness before
# check 6 ever runs.
#
# `rules:` and `stories:` are `04-flows.md` §5's index for `J-RBS-1` plus the two
# stories whose own frontmatter names it (`US-RBS-001` phase 1, `US-RBS-006` phase 3).
---

⚠ **THE WORK-LIST HALF WAS WALKED IN A BROWSER 2026-09-07 AND THE CLOSING HALF WAS NOT —
SAID APART RATHER THAN BLENDED.** `10-scripts/render-checks/rbs-g-coverage-grid.mjs` opens
`RBS-007` on the seeded utility and reads: six items raised by two runbooks, the six columns
the build sheet draws in that order, every row linking to the run that raised it at the
tenant's own address, ages read from the FIRST sighting, chip counts that are the server's
and not the page's — and it **presses Resolve and watches the row leave the open list**.

**What it does NOT click is this journey's last leg** — *fix the tax region, re-run, 3 → 2,
and the item closes itself*. Fixing a tax region and re-running are two acts no screen in
this product can perform: `POST /runbooks/{key}/runs` is wave `L`'s and is not built. The
self-closing itself IS proved, twice: `test_us_rbs_006_work_items.py` runs a sweep that
raises the finding and a sweep that raises nothing and asserts the item resolves itself with
`work_items_closed = 1`, and `rbs_g_seed_coverage.py --again` does the same against real
PostgreSQL. **A journey that claimed a click nobody made would be worth less than one that
says which half is which.**

**Intent.** The first thing a utility does with this product, and the first thing this
module has to be right about: **a clerk who is not live yet presses one button and is
told exactly what is stopping billing, in the order a bill actually needs it.** Runbook
1 (*Can we bill?*, definition title **Configuration check**) walks the tenant's
configuration graph in ten steps and returns findings — it never writes. **The
load-bearing assertions are two, and neither is the blocker count on its own:**

* **A Check holds no writer at all.** `ports[]` is empty and it is enforced at
  CONSTRUCTION, so a write is *unavailable* rather than refused at run time
  (`BR-RBS-002`). The database proof is the negative in step 4: **not one row outside
  this module's own seven tables changed**, and the work items on `RBS-007` were raised
  anyway — by the ENGINE at run close, which is why *raise a work item* is not a port
  (`BR-RBS-022`, and the reason `03-field-map.md`'s `D-1` resolves to thirteen ports
  rather than the source's four).
* **A work item is DERIVED, not hand-managed.** Fix the tax region, re-run, and the item
  **closes itself** — that is step 8, it is why the item is keyed by `fingerprint` and
  never by the run id, and it is the one assertion in this journey that would catch a
  wrong build. An implementation that closes items on a person's tick passes every other
  step here and fails only this one.

**Upstream leaves.** Nothing. This journey is the module's own front door and depends on
no other journey; what it depends on is a fixture.

Tenant **Silver Creek Water** (`silvercreek`), the **two-service** fixture of
`US-RBS-001` §4: **Water and Sewer · 60 accounts · 58 premises · 62 meters**, plus the
**billing-blockers set**, which is exactly three faults and no more:

| # | The fault seeded | The step that finds it | Its weight | Its fix button |
|---|---|---|---|---|
| 1 | **No tax region set** | 3 · Tax | Blocks billing | **Set a tax region →** |
| 2 | **One plan with no rate block above 20,000 gallons** | 5 · Rate coverage | Blocks billing | **Add a block →** |
| 3 | **4 accounts with no unit** | 6 · Account chain | Blocks billing | **Match units →** |

**These three produce exactly the 3 blockers and the 3 distinct fix routes**, which is
what makes the number on screen assertable (`TC-RBS-001.1`). *Nothing about Gas or Solar
appears anywhere in this fixture, and that absence is itself an assertion.* Runbook 1's
four parameters at their card values: *Report* = **Blockers and warnings** · *Usage to
cover* = **Highest seen, 12 months** · *Include held accounts* = **off** · *Raise work
items* = **on**. Isolation tenant **Lone Star Ridge WSC** with its own two services and
its own three faults (*ours*). Actor: **Dana Whitfield**, a billing clerk.

**The journey's clock.** Run 1 at **08:12** on day 1. The work list is opened at
**08:20**. The tax region is set at **08:31**. Run 2 at **08:34**. The ageing leg (step
9) is the same Check on a schedule for **thirty consecutive days**, day 1 to day 30, over
an estate holding **one** missing read.

**Where two documents disagree, and which one this journey follows.**
* `US-RBS-001` §6 says the result *"shows ten cells red at the earliest failure"*, and
  the drawn frame `RBS-006-R1` region 3 draws **three** red cells — Tax, Rate coverage
  and Account chain — under the subtitle *3 things stop billing.* **This journey follows
  the frame**: a red cell per blocking step, and the chain is read left to right so the
  earliest red is the one to fix first. Filed for the parent as a wording ambiguity in
  the story, not as a defect in either.
* `RBS-006-R1`'s drawn figures are the SOURCE's illustrative estate — *2,907 service
  points*, *240 accounts have no unit*, *6 warnings* — while this journey's fixture is
  the epic's 60-account one. **The sheet's own acceptance line settles it:** *"Sample
  values are illustrative; the words around them are not."* So this journey asserts the
  words and the epic's counts, never the frame's sample numbers.

| # | Actor · action · screen | Expected outcome (contract — what this step leaves) | Downstream assertions (record · screen · audit · books) | Rule |
|---|---|---|---|---|
| 1 | **Dana** opens **Runbooks** at `/silvercreek/operations` (`RBS-001`) | First visit draws `RBS-001.2`: the `EmptyList` — *Nothing has run yet* / *Start with a check. Nothing is sent.* / **Run "Can we bill?" ▶** / **Browse templates →** | ⛔ The empty state **names the missing thing and the action that fills it** (B14 rule 17), and it offers a CHECK — nothing this screen can start sends anything. ✅ No `S`-series id and no database id is visible anywhere (rules 31, 32) | **BR-RBS-001** · B14 17, 31, 32 · `US-RBS-001` |
| 2 | Dana presses **Run "Can we bill?" ▶** | `POST /runbooks/configuration-check/runs {mode: "check"}`. **One `runbook_runs` row**: `trigger = manual`, `version` **pinned at start**, `status = running`, `scope_fingerprint` = the pinned config graph, `parent_run_id` NULL. `RBS-005` opens on the **four-step** rail — *Scope · Checking · Review · Done* — with **no Approve and no Applying** | ⛔ **A Check's wizard is four steps and skips Gate and Act entirely.** A six-step rail on a Check is the build to catch here. ✅ Every step is listed before the first one starts, and a step that does not run carries its reason, including *Never reached*. ✅ Scope is *decided for you* — three read-only rows (Covers · Services · As at) and no picker | **BR-RBS-023** · `RB-001` · `RBS-005` |
| 3 | The run walks its **ten steps, all read** — services and units · reference data · tax · plans in force · rate coverage · account chain · meters · reads and windows · documents · books | **`runbook_run_records`**: every row's `planned_action` is **`report`** and nothing else, each carrying `decided_by_rule` in words a clerk can read, `reason` in plain language with **no rule id in it**, and `fix_route` NOT NULL on every failure | ⛔ `TC-RBS-001.1`: the register holds **no** row whose `planned_action` is anything but `report`. ⛔ `TC-RBS-14`: a static scan of every failure reason in the module returns **zero** reasons without a fix route — *a failure with no route is a defect in the runbook, not a fact about the account*. ⛔ A per-record step runs **in its own savepoint**; on PostgreSQL a naive `try/except IntegrityError: continue` loses the run and **passes green on the SQLite test settings** (hard-won law 14, `TC-RBS-5`) | **BR-RBS-010** · **BR-RBS-011** · **BR-RBS-023** · `US-RBS-001` TC-1 |
| 4 | The run closes · `RBS-006` draws the result | Page head *Run · Today 08:12* / **3 things stop billing.** → KPI strip → **Chain, ten cells, red at Tax, Rate coverage and Account chain** → chips *All · Blockers 3 · Warnings n* → the findings table, columns **Step · Finding · Affects · Weight · Fix**, each blocker carrying its button. `runbook_runs.report` holds **the block list as composed at close, and frozen** | ⛔ **THE NEGATIVE THAT IS THE WHOLE SAFETY STORY: not one row outside this module's seven tables changed.** Diff the database across the run — `accounts`, `premises`, `meters`, `tariffs`, `invoices`, `notifications`, `audit_log`: zero writes. ⛔ `TC-RBS-16`: a report naming a thirteenth block is refused **at close**, never at render. ⛔ `TC-RBS-13`: reopening this run next month draws exactly what it draws today — the report is read from the frozen document, never recomposed from the live definition | **BR-RBS-002** · **BR-RBS-020** · `RB-016` |
| 5 | **The construction check (negative).** A developer binds `queue_notice` to runbook 1 and builds | **The BUILD fails**, naming the runbook and the port. Not at the call, and not at run time | ⛔ `TC-RBS-1` **must first fail on** a Check with a port bound that only raises when the port is *called* — that version is green until the day something calls it. *"A write from a Check is a construction error, not a bad Monday."* ✅ `RBS-004.1`'s *This can* panel reads *Send notices · No · Charge fees · No · Change bills · No*, derived from the empty `ports[]` and typed by nobody | **BR-RBS-002** · `TC-RBS-1` |
| 6 | **The engine raises the work items** at run close (*Raise work items* is on) | **THREE `work_items` rows**, written by the ENGINE and not by the runbook: `source_kind = check` · `source_run_id` = this run · `fingerprint` = (tenant, runbook, subject, finding kind) and **never the run id** · `title` · `weight` *Blocks billing* · `subject_ref` · `fix_route` · `owner_user_id` NULL · `status` open · `created_at` today | ⛔ **This is the step that proves *raise a work item* is not a port.** The runbook that produced these findings holds an EMPTY `ports[]`; a build in which `raise_work_item` is a port has given every Check in the product a writer, and `BR-RBS-002` is gone. ⛔ `TC-RBS-006.3`: no cell on `RBS-007` shows a database id, a rule id or an internal code | **BR-RBS-022** · **BR-RBS-017** · B14 31, 32 · `US-RBS-006` |
| 7 | **08:20 · Dana opens the work list** `RBS-007` at `/silvercreek/operations/work` | Columns **What needs doing · From · Weight · Owner · Age · row actions**. Three rows, **heaviest first** — all three read *Blocks billing*, which is a fact about CONSEQUENCE and sorts itself to the top. *From* names the run that raised each one | ⛔ The heading `S153.2 · all clear` drawn inside the `RBS-007` frame **must not ship** — it is the drawing labelling its own second state on one sheet, and it is an internal code in clerk-facing copy (B14 rules 31, 32). **The built screen shows the table or the empty state, never both.** ✅ The list pages on the server, `per` clamped 50/100/200/500/1000 (`NFR-3`) | **BR-RBS-011** · B14 31, 32 · `US-RBS-006` |
| 8 | **08:31 · Dana follows *Set a tax region →***, sets the region, returns and presses **Run again ▶** at **08:34** | A **second** `runbook_runs` row — a re-run is a new run, never a resumption. **THE TWO ASSERTIONS: the blocker count falls from 3 to 2 and the Tax cell is no longer red — AND THE TAX WORK ITEM CLOSES ITSELF.** The **same** `work_items` row is resolved by the engine: `status` resolved, `resolved_at` stamped, `created_at` unchanged; **no second row and no new id** | ⛔ **THE ONE THAT CATCHES A WRONG BUILD:** an implementation in which an item is closed by a person's tick leaves this row **open** after the re-run, with the count correctly at 2 — every other assertion in this journey still passes. ⛔ The other two items are **untouched**: same rows, same `created_at`, still open. ⛔ `TC-RBS-006.2`: if the tax region is removed again, the **same row reopens with its history** — a fingerprint containing the run id would create a second | **BR-RBS-017** · **BR-RBS-022** · `TC-RBS-006.1` · `US-RBS-006` |
| 9 | **The ageing leg.** The same Check runs daily for **thirty days** over an estate with **one** missing read | **ONE** work item, **thirty days old** — upserted by fingerprint on every sweep, never re-created. The age a clerk reads is `created_at`, not the last sighting | ⛔ `TC-RBS-10` **must first fail on** an insert instead of an upsert: thirty rows for one problem, and a work list nobody can read after a fortnight. ✅ `UNIQUE (tenant_id, fingerprint)` is what the upsert needs, and it is a database constraint rather than application code | **BR-RBS-017** · `TC-RBS-10` |
| 10 | **Per-service rollup** (`TC-RBS-001.2`, on the fixture variant where the tax region is missing on **Sewer only**) | **Water reads Go · Sewer reads No-go · the tenant reads No-go.** Steps 1, 3, 4, 5, 7, 9 and 10 carry a per-service verdict; steps 2, 6 and 8 are tenant-wide; the tenant verdict is the worst of them | ⛔ **Must first fail on** a single tenant verdict — it cannot distinguish one service failing from both failing, which is the whole reason the answer is one per service rolled up. ⚠ This leg runs on a **variant** of the fixture; see boundary **b** | **`US-RBS-001`** §1 · `TC-RBS-001.2` |
| 11 | **ISOLATION — Lone Star Ridge WSC** (`app.tenant_id` = Lone Star's) | Its own run over its own three faults; **Silver Creek's run reads not one row of it**, and its work items appear only on its own `RBS-007`. `/lone-star-ridge/operations/runbooks/configuration-check/runs/<Silver Creek's run>` → **404** | ⛔ `TC-RBS-7` **must first fail on** a scope function missing the tenant context — *"a scope function that forgets the tenant is refused by the database, not by a reviewer"*. ✅ RLS `FORCE` on all seven tables; every seam read with `app.tenant_id` unset returns zero rows. ⛔ A fingerprint that omits the tenant collides two utilities' identical findings into one item | hard rule 1 · **BR-RBS-039** · `TC-RBS-7` |
| 12 | **INVARIANCE** | — | **Zero rows written outside `runbooks`, `runbook_versions`, `runbook_runs`, `runbook_run_records`, `work_items`, `cutover_plans`, `cutover_plan_items`.** No money: this Check prices nothing, charges nothing and posts nothing — no `journal_lines`, no `invoices`, no money `audit_log` row, because there is no money action to write one for. No notice queued, no bill number consumed. Every cross-module read went through a seam file this module owns; **a census of the module's imports finds no other module's models, no raw SQL and no HTTP client** | **BR-RBS-002** · **BR-RBS-039** · `TC-RBS-25` · hard rules 1, 4, 7 |

**This journey leaves (for downstream).** A tenant whose *Can we bill?* reads **2
blockers**, with the Tax step green · **two open work items** on `RBS-007`, ageing from
day 1, and **one resolved** one carrying its own history · **two `runbook_runs` rows**
with frozen reports, both openable from `RBS-008` and both reading *By: Dana Whitfield*
rather than *Schedule* · a `runbooks` row at version 1, `origin = shipped`,
`template_key` set. **Downstream:** `EP-RBS-03`'s runbook 3 (*Ready for billing?*) calls
this one through `requires` as its own sub-run, linked by `runbook_runs.parent_run_id`;
`J-RBS-2` starts from the same tenant with its rate coverage still broken and closes that
blocker from the other end.

## Boundaries — what this journey stops at, and why

| # | Not asserted | Because |
|---|---|---|
| a | **The screen the *Set a tax region →* button opens.** | **The pack names the BUTTON and never its destination.** `RBS-006-R1` region 5 draws five fix labels and no route for any of them, and `07-endpoints.md` carries no route for a fix either. `BR-RBS-011` requires that a route EXISTS and `TC-RBS-14` proves none is missing — neither says which screen. **Reported to the parent as the first thing phase 1 must decide**, because a fix button that opens the wrong screen passes `TC-RBS-14` perfectly |
| b | **A single fixture producing both the three-blocker count and the per-service rollup.** | `TC-RBS-001.1` seeds three faults and asserts the count; `TC-RBS-001.2` seeds the tax fault **on Sewer only** and asserts Water = Go. The three-blocker set does not say which service carries the rate-coverage and account-chain faults, and *rate coverage above 20,000 gallons* reads as Water. **Seeded as two fixture states and named as such** rather than reconciled by guessing which service owns which fault |
| c | **The warning count.** | The epic asserts **3 blockers** and three fix routes and says nothing about warnings; `RBS-006-R1` draws **6** on the source's own 2,907-service-point estate. A 60-account fixture does not owe that number, so it is not asserted here |
| d | **Anything scheduled.** | Runbook 1's trigger is **Manual**. The daily sweep in step 9 is `EP-RBS-03`'s scheduling and is asserted here only for the ageing property it produces; the scheduler itself, `RBS-008` and the work list's own screen story land in phase 3 |
| e | **The audit actor.** | `BR-RBS-015` / `RB-011` — *"the runbook, version n"* as an actor — is **BLOCKED on the audit module**, and nothing in this journey writes money, so no audit row is due. It is `J-RBS-3` that cannot proceed without it |
| f | **That this file can be activated.** | `DEF-RBS-4247`: G12 refuses this `id:`. And there is no product to click — phase 1 has not been built |
