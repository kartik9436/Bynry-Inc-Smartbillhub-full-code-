# 16 · Work — execution plan for `CR-070` (phases → waves → tasks)

⚠ **RE-HOSTED 2026-09-04 — READ §0c BEFORE ANY OTHER SECTION OF THIS FILE.** This plan was written on
2026-09-03 with the **connection detail** (`NCT-02`, `/connections/<uuid>`) as the host for the build and its
jobs. On 2026-09-04 the Product Owner ruled that host away — *"there is nothing called connections;
Connection = Account only - you cannot have two differnt screen - this is an integration problem"* — and named
where the work orders belong instead: *"check out new services, new connect move in move out, transfer - you
will see all these requirements are handled their , we had a missing element work order - now it go and fit in
it"*. The ruling is `CR-070 §W`; **§0c below is the whole of what it does to this plan** — two new waves (`O`
and `P`), one story moved (`US-WRK-039`, wave `M` → wave `P`, phase 2 → phase 1), **no table changed, no
migration, no data moved, and nothing renumbered.** Waves `A`, `B` and `C` are landed and none is rebuilt.
**Where a wave section below still reads as though `NCT-02` were a destination, §0c is right and the wave text
is stale — every such place is stamped in line, and there were two.**

**Written 2026-09-03 against HEAD `f02400b3` (product `2.128.2`) from the documentation that already exists:
`12-governance/change-requests/CR-070-work-module.md` (§8 the 49 cards, §11 the three phases, §12 the three
gates, §14–§15 version and rollback), this module's `01`–`09` files and `wireframes/`, `04-docs/02-decisions/12-engineering-plan.md`
Addendum r11, `12-governance/13-change-process.md` step 7, `12-governance/20-wave-tasks.tsv` and
`12-governance/01-open-questions.md` rows `OQ-WRK-1490`–`1497`, `OQ-376`, `OQ-249`, `OQ-371`.** Paths are relative
to the repository root. Task ids (`A1`, `B3` …) are this plan's own; the blueprint's `WM-` cards and `WS-` screens
appear in the cross-reference column only where the module's own documents name them, and none is invented here.
The shape follows `13-integrations/10-execution-plan.md`, written the same morning for `CR-069`. **Checkpointed by
the parent lane at `bb7d2e3f` and `358c603c` while it was being written; between those, `d0cf0b00` landed the eight
journey files and the `CR-070` register rows — §1 says where that changes a row.**

## 0 · What this is, and the three rules it obeys

**A PHASE is a launchable increment with a launch sentence.** `CR-070` §11 has three and they are kept verbatim.
**A WAVE is a sprint-sized lane** (one or two people, one to two weeks) that **ends in a demonstration** — a
five-to-eight-step script clicked in the running product on the seeded fixture — **and a version bump**. No wave
ends in "the tables exist". A wave blocked to a boundary by an open question still demonstrates the boundary: the
stub, the sentence on the screen, the test that asserts the raise. **A TASK is one r11 part** — `2a` backend · `2b`
frontend · `2c` tests + data · `2d` prove it — or a `ground`, `gate`, `doc`, `review` or `version` act, each with
what it touches verified against the code at HEAD.

**The Product Owner's rules, verbatim (decision log 2026-09-03):**

> *"we ahve to execute in agile way - each phase/wave should produce tangila eoutcome"*
> *"at the end of each pahse we should abl to luanch some funtionlaity"*
> *"everything should be executed based on actual code, and rules that we place, also ensure you do web
> walkthorugh before you sign off the user story or build"*
> *"for Cr68, 69 and 70 - you will have to ensure you refer to screenshot we build and not just r10"*
> *"Dont add Tax on work order - for now"*

**Definition of done for every task and every wave in this plan — three parts, all required:**

1. **Actual code.** Every task's *touches* column was verified against the code at HEAD `f02400b3` before it was
   written — the file, the model, the route, the component, with its path and line where useful. Where a document
   and the code disagreed, the code won and the task says so (§1 lists every such finding). A lane re-verifies at
   step 0 before it starts, because the tree moves.
2. **The rules.** Every task names the `BR-WRK-`, B14 or CLAUDE.md rule it satisfies, and every wave's exit test
   asserts a rule — the CHECK that refuses an order with no anchor, the server refusing a completion with an unticked
   safety row, a total that is the sum of the rounded lines — never an impression.
3. **The web walkthrough.** Every wave's `2d` task is a browser walkthrough of the running product in the repo's
   existing convention — `10-scripts/render-checks/cr070-<wave-letter>-<slug>.mjs` (Playwright on the preinstalled
   Chromium; the shape is `cr058-owner-import-and-sale.mjs`: `SMOKE_BASE`, a database nobody else seeds, computed
   style read in a real engine, screenshots saved). It clicks the wave's demo script against the seeded fixture and
   asserts the on-screen sentences **against this module's own wireframes** — `wireframes/Work-0NN.png` read through
   `08-screen-layouts.md` (the regions and the copy) and `09-component-inventory.md` (the pieces) — with the
   corrections that file's closing table already makes (rule 32 strips the ids from four drawings; every list gets
   the CR-045 toolbar; the report shows `48.50` not `48.5000`; `Work-025`'s stock columns and `Work-023`'s block are
   held). **A story is signed off only when its tests are green — on PostgreSQL where law 14 applies — that
   walkthrough has run green on the actual build, and the screens match the pack.** The three phone screens
   (`Work-010`–`012`) are not in the pack; for them the walkthrough asserts r10's mobile frame
   (`05-prototype/r10-2026-08-16/SMARTBillHub.dc.html`, `workTab === 'mobile'`) and the rule sentences the stories
   quote — the pack wins the day the blueprint's §14 drawings arrive.

**How a lane uses this plan.** Take one wave. Run `./10-scripts/check_head_current.sh` first (law 12). Do r11
**step 0** — re-read `01-open-questions.md`, `02-decision-log.md`, `10-defect-log.csv` and
`11-change-requests.md` for anything ruled since 2026-09-03, and grep before putting anything to the PO (law 13).
Assemble the **packet** (the wave's stories in `06-epics/`, the rules they cite verbatim from
`02-business-rules.md`, the field-map rows in `03-field-map.md`, the journeys in `04-flows.md`, the layouts entry
and its image). **A phase-1 lane reads the blueprint's §16 before writing `work/0001`** — every table row marked
`[ours — §16 unread]` and the three-way placement choice in `03-field-map.md` §4 wait on it. Build the tasks in
the order their `depends_on` allows, **writing back as you go** — a stale rule amended before building on it, a
question minted before code would guess, a defect filed before it is fixed. Work in a `git worktree`, commit by
pathspec, push after every task (law 11). Close the record — decision-log row, review-ledger row for every 🔒
file stating what was shown to the PO in plain English with a figure, `20-wave-tasks.tsv` rows moved to `verify`
then `done`, CHANGELOG and version — **before** review. Then the walkthrough is run green on the built product,
and only then is the story signed off.

**Version.** Scheme `<release>.<change>.<fix>` (`13-change-process.md` step 7); the product is `2.128.2` at HEAD
in both `07-frontend/package.json:4` and `06-backend/pyproject.toml:193`, held in lockstep by G35. **Each wave
lands as its own `<change>` bump with a CHANGELOG entry, and each phase's closing wave carries the phase's entry**
(`CR-070` §14: *"Each phase gets its own version and changelog entry"*). Absolute numbers are NOT pre-assigned
here: the `CR-068` and `CR-069` lanes bump the same literal concurrently — `CHANGELOG.md` carries an
*[Unreleased] — 2026-09-03* entry (`DEF-3422`) waiting for exactly that reason — so each wave takes **the next
free `<change>` at push time**, re-derived from the tip (law 11: an allocated number is a blob). The first wave of
any of the three CRs to move the version attaches the waiting entry.

**Coverage.** Every one of the 54 stories `US-WRK-001`–`054` is placed in exactly one wave — the three blocked
ones and the one closed by ruling included, because a boundary is demonstrated in a wave like anything else.
`US-WRK-006` (the fixture) is placed in wave A and **grows under every later wave's `2c` task**, the way the
epic's own `0 → 2` phase marking says; a story placed in one wave may have acceptance tests landing in a
neighbour and the closing table says where. §7 prints the check that was run over this file.

**Rollback (`CR-070` §14).** Phase 0 rolls back cleanly — a nullable column and mounted buttons. **From phase 1
rollback is *hide the section and keep the data*, never *drop the tables*** — a utility that has authored templates
has content that matters. Each phase's closing wave states its rollback in its version task.

### The visual reference — the pack, then r10 (PO 2026-09-03)

**PO, verbatim: *"for Cr68, 69 and 70 - you will have to ensure you refer to screenshot we build and not just r10"*.**
Every wave's walkthrough below is judged against **`wireframes/Work-0NN.png` in this module** — 21 screens from the
§13 PDF the PO exported — read through `08-screen-layouts.md`, which has one entry per drawn screen, and
`09-component-inventory.md`, which names the pieces and the three the staff kit lacks (`EditableTable`,
`SegmentedControl`, `Thumbnail`). **r10 stays the default for everything the pack does not draw** (the shell, the
nine screens that exist today, the three phone screens, the seven undrawn sub-screens). **Where the two disagree
on one of these screens, the pack wins and the divergence is stamped in `08-screen-layouts.md`.** ⚠ **And where
the pack disagrees with its own card, the CARD wins** — two of the 21 images draw things the cards forbid, both
already filed: `Work-025` draws stock levels and a reorder banner (`DEF-WRK-3550`, `OQ-WRK-1490`) and `Work-023`
draws a lapsed certification blocking four template types (`DEF-WRK-3551`, `OQ-WRK-1493`). A walkthrough that
asserted those images verbatim would build what a ruling removed; waves C and F assert their ABSENCE.

### 0c · THE RE-HOSTING — what `CR-070 §W` changed under this plan (2026-09-04)

⚠ **THIS PLAN WAS WRITTEN ON 2026-09-03 WITH THE CONNECTION AS THE HOST. ON 2026-09-04 THE PRODUCT OWNER RULED
THAT HOST AWAY, AND THREE OF THE FOURTEEN WAVES WERE BUILT ON IT.** The ruling is `CR-070 §W`, folded into this
CR by PO instruction the same day (*"why are you wirting Cr 72 - it should be part of CR 70 itself - all changes
related to work orders"*). Read §W before this section; what follows is only what it does to the plan.

**The ruling in three sentences.** *"There is nothing called connections; Connection = Account only — you cannot
have two different screens; this is an integration problem."* It is **one screen too many, not one table too
many** (§W.10): `connections`, `connection_services` and `connection_todos` all survive as plumbing, `work_orders
.connection_id` survives, wave A's four anchors survive, and **no migration and no data change comes out of this
at all.** What stops is the DESTINATION — `NCT-02` at `/connections/<uuid>` as a place a person navigates to.
And the work orders go where the work already is: *"check out new services, new connect move in move out,
transfer - you will see all these requirements are handled their , we had a missing element work order - now it
go and fit in it"*.

**What that costs this plan, measured rather than estimated.**

| | Before the ruling | After |
|---|---|---|
| Waves | 14 (`A`–`N`) | **16** (`A`–`N` unchanged in letter, plus **`O`** and **`P`**) |
| Waves landed | A · B · C | A · B · C — **and none of them is rebuilt** |
| Waves remaining | 11 (D–N) | **13** (O · D · E · P · F · G · H · I · J · K · L · M · N) |
| Waves hosting Work on `NCT-02` | **2** — `B3` (shipped) and `I`'s demo step 6 | **0** |
| Waves already hosted on an existing flow | **2** — `E` (New Connect step 6) and `M3` (move-out) | **6** — the five flows plus Assets |
| Flows of the PO's five with a wave | **2** of 5 — new connect, move-out | **5** of 5 |
| Tables changed by the ruling | — | **0** |
| Migrations | — | **0** |

**Nothing is renumbered.** Wave letters `O` and `P` are appended and PLACED BY PHASE, not by letter — the same
discipline the id rule takes (`CLAUDE.md`, *"THAT IS A CEILING, NOT A SPELLING"*). Read §2's phase table for the
running order; `O` runs FIRST of what remains, and `P` runs after `E`.

**The two new waves, in one line each.**

* **Wave `O` — one destination.** The build's six views move from `/connections/<uuid>` to the **premises** and the
  **account**; `B3`'s **eight** acts move with them; the URL redirects rather than 404s. Phase 0's correction, and it
  runs first because every wave after it points somewhere.
* **Wave `P` — the five flows raise their jobs.** New service, move-in, move-out, transfer and the reconnect visit
  each gain the raise at the moment the clerk is standing there. `M3`'s move-out door moves here from wave M, and
  onto the step the clerk actually uses.

**What is DROPPED, and it is short:** `Work-002` as a screen id and `/connections/<uuid>` as a navigable
destination; `B3`'s action row as a standalone place; the `CONNECTION` column's LINK on `Work-009` and the
dispatcher (the column's text stays, the link moves to the build's home); wave `M`'s move-out door (moved, not
deleted); wave `I`'s demo step 6 as written. **Nothing else. No table, no route, no service, no test.**

**What becomes NEW work because a flow needs what the connection screen used to provide — three things, and they
are the honest cost of the ruling:**

1. **A host on the premises.** `PremisesDetailPage.tsx` has **five** tabs (overview · units · common-areas ·
   assets · audit — ⚠ AMENDED 2026-09-04, `DEF-WRK-3749`: this line said *"four tabs (units · occupied · meters ·
   master-account)"*, which are the `KPIStrip` TILE ids and not tabs at all) and no build, no work orders and no
   charges. It has to grow them, because a multi-unit build has nowhere else to be — see the judgment below.
2. **A host on the account.** `AccountDetailPage.tsx` has **eleven** tabs (`ACCOUNT_TAB_IDS`, line 223) and not one
   of them mentions a job. It gains a twelfth.
3. **A way to reach a job from the flow record that raised it.** The four anchors say WHERE a job stands; nothing
   says WHICH flow raised it, so a move-out cannot show its own visit. Wave `G`'s `source` enum is a display stamp,
   not a pointer. See judgment 4.

**Where re-hosting costs MORE than patching would have, stated with the figure, because it does.** `B3` was one
file — `features/customers/ConnectionDetailPage.tsx`, 1,464 lines — gaining a row of seven buttons, sized **L**
for one person. Wave `O` is **two host screens and six panels**, sized **two people, one and a half weeks**. So
the re-host costs roughly **a week more than the patch**. ⚠ **And it is still the cheaper road, for a reason worth
writing down: the patch would have been paid THREE TIMES.** Wave `I` would have shown the failed-outcome hold on
that screen; wave `M` would have hung the move-out visit off it; wave `G`'s `CONNECTION` column would have linked
to it — three lanes, three sprints apart, each discovering the same retired destination on its own. That is what
*"I'd rather do it once than discover it at wave G"* is buying.

#### 0c.1 · The five flows — where a work order attaches, verified in the code

Read before re-hosting anything. Every line below is a file and a line at the pinned tip, not a description.

| # | Flow | Where the job attaches, in the code | What the clerk is doing at that moment | Wave |
|---|---|---|---|---|
| 1 | **New service** (the service request) | `apps/customers/service_request.py:164` — `TRANSITIONS[ROUTE]` is `APPROVED → IN_FULFILMENT`, and it is a bare state move through `_apply` (`service_request_service.py:2032`) that creates nothing. The vocabulary's own comment at `:183` already promises the job: *"A request closes on its own when the job it created finishes."* | They have just approved the application and are deciding **who does the work**. `ServiceRequestDetailPage.tsx:116` gives them six tabs — applicant · location · documents · fees · decision · history — and **no fulfilment tab and nowhere for the job** | **P** |
| 2 | **New connect** | `NewConnectWizard.tsx:1273` — step 6, whose own name in `newConnectShared.tsx` is **`Plans & work orders`**, says *"Those templates are not built yet, so no orders are proposed here."* | They are mapping services to plans and are being told the jobs cannot be proposed | **E** — already hosted here, nothing to move |
| 3 | **Move-in** | `apps/customers/services.py:3855` `move_in`; steps in `moveShared.tsx:228` — unit · customer · **start date & reads** · plan · review. Step 3 takes the opening reads; a unit left off needs somebody to turn it on. `MOVE_IN_UNAVAILABLE` (`services.py:3377`) does not name the visit at all, so today the absence is not even stated | Step 3: they are entering the opening reads and the start date | **P** |
| 4 | **Move-out** | `apps/customers/services.py:3644` `move_out`; steps in `moveShared.tsx:213` — account · **date & final reads** · settlement · shortfall · impact · review | Step 2: they are entering the move-out date and the final reads, and the reads are the reason a person has to attend | **P** (moved from `M3`, and onto step 2 — see `DEF-WRK-3725`) |
| 5 | **Transfer** | `apps/customers/transfers.py:266` `Transfer`, committed by `reassign_account` at `:1244`; steps in `transferDisconnectShared.tsx` — leaving · **final reads** · arriving · money · review | Step 2: the same moment as a move-out — the reads at the changeover | **P** |
| 6 | **The reconnect visit** — not one of the PO's five, and the only place the code already carries a named hole | `apps/customers/disconnects.py:1214` `VISIT_NOT_SCHEDULED`, set into the answer by `mark_reconnecting` at `:3993`. Its own words: *"§5.8.4's reconnect flow is 'payment confirmed → visit scheduled → restored' and nothing here schedules the visit: `work_orders` belongs to metering and cross-module writes are forbidden"* | The customer has paid and is waiting to be reconnected; the state literally means *"paid, awaiting a visit"* | **P** |

⚠ **THE SENTENCE IN `VISIT_NOT_SCHEDULED` STOPPED BEING TRUE ON 2026-09-03.** *"`work_orders` belongs to metering
and cross-module writes are forbidden"* was correct when it was written; wave A made Work the eleventh module with
a read-only seam per module and a door of its own, so customers now calls Work's API exactly as `E2` has customers
calling it for step 6. Wave `P` amends that docstring with the date the door opened and **keeps the constant and
its name** — the same posture `M3` already took.

#### 0c.2 · The nine judgments made here, and why none of them went back to the PO

Every one is recorded in `12-governance/02-decision-log.md` dated 2026-09-04 with its worked figure. Law 13: a
judgment recorded with its reasoning is the deliverable; a question is the failure to make one.

1. **THE BUILD'S HOME IS THE PREMISES, AND THE ACCOUNT AS WELL WHERE ONE EXISTS.** §W.11 says *"the account, and
   from the premises where a build spans units"*, and the code says the account half is not always PRESENT:
   `connections.owner_account_id` is NULLABLE, so a build carries no owner account until one is asked for, and
   `BR-MET-116` refuses one outright on a build with no common area. **Measured with `app.tenant_id` set on
   2026-09-12: 8 `brazosbend` connections, 0 with an owner account**, so an account-only host would show an
   empty screen on every build in this fixture. **So the premises is the host that always exists; the account is
   the host a person usually starts from.**
   ⚠ **THIS ITEM SAID *"nothing fills it"* AND BLAMED `create_owner_account()` RAISING
   `NotImplementedError("OQ-373")` "because `accounts.unit_id` is NOT NULL" UNTIL 2026-09-12 (`DEF-MET-5081`).
   Every clause of that was false by 2026-09-01.** `OQ-373` closed 2026-08-25 → `BR-MET-116`;
   `create_owner_account()` is implemented and `commit_connection` calls it at step 4; and `accounts.unit_id` is
   NULLABLE — `brazosbend` holds `AC-2026-00052`, `kind='master'`, `unit_id` NULL, anchored on `CON-26-0117`'s
   own premises. **The judgment is unchanged and this row is the correction to its proof**, per the
   decision-log row of 2026-09-12: *a decision log records what was believed when a decision was made.*
2. **THE SIX VIEWS SPLIT BY WHAT OWNS THE FACT.** Overview · Units · Assets → the **premises** (a unit list and a
   meter list are facts about a place). Charges · History → the **account** (money and its trail are facts about
   a payer). **Work orders appears on BOTH**, because both are anchors and a person asks the question from either
   side. Nothing is duplicated: each panel reads one selector.
3. **THE LIST IS SCOPED BY PATH, NOT BY A SEVENTH FILTER.** `GET /accounts/{id}/work-orders` and
   `GET /premises/{id}/work-orders`, so **`BR-WRK-026` does not move** — the dispatcher keeps exactly six filters
   and still answers `400` on a seventh. Adding *account* and *premises* as filters would have made it eight and
   put a signed rule in the way of a screen.
4. **THE FLOW STAMP IS `source` PLUS `source_ref`, AND NO NEW ANCHOR.** A job raised by a flow already stands on
   an anchor it has — the move-out's visit on the **account** it closed, the request's install jobs on the
   **premises** the request resolved to. What is missing is only a reference BACK, and each flow record already
   carries a number a clerk quotes (`MVO-…`, `SR-…`, `TRF-…`, `DSC-…`, unique per tenant). **So: `source` (wave
   G's enum, four values added) + `source_ref` (text, nullable).** ⚠ **Worked against the alternative:** one
   nullable FK per flow would take `work_orders` from **4 anchor columns to 9** and `ck_work_orders_has_anchor`
   from a four-way CHECK to a nine-way one, and would add **four** cross-module FKs to B2 §2's reviewed interface
   set for a link that is only ever read to print a reference. **The CHECK does not move.**
5. **`/connections/<uuid>` REDIRECTS; IT DOES NOT 404.** The New Connect wizard's completion, the *New connects*
   tab on the Accounts page, `AccountsListPage.tsx` and every bookmark point there today. A 404 would break a
   working link to punish a screen.
6. **MOVE-OUT'S VISIT HANGS OFF STEP 2, NOT STEP 4.** `MOVE_OUT_STEPS[3]` carries `conditional: true`
   (`moveShared.tsx:216–221`): the shortfall step renders **greyed and *skipped*** whenever the account settles,
   so a control placed there is invisible on the ordinary move-out. Filed as **`DEF-WRK-3725`** before it was
   moved.
7. **A FLOW OFFERS THE JOB AND NEVER RAISES ONE SILENTLY, AND THE FLOW COMPLETES WHETHER THE RAISE SUCCEEDS OR
   NOT.** This is `BR-WRK-055`'s posture — written for move-out — applied to all five. A flow that fails because
   a work order could not be created would make the field module able to block a customer's move.
8. **A REQUEST WITH NO RESOLVED PREMISES CANNOT RAISE A JOB.** `resolve_address` (`service_request_service.py:968`)
   can leave a request with no unit and no premises — a request taken by phone for an address not yet in the
   system. Such a request has **none of the four anchors**, so `ck_work_orders_has_anchor` would refuse the row.
   The raise is refused on the screen first, with a five-or-six-word sentence (B14 rule 33), rather than by adding
   a fifth anchor for a state that is meant to be temporary.
9. **PHASE 0'S LAUNCH SENTENCE STANDS AND IS NOT RE-DECLARED.** *A clerk can raise, hold, cancel and close a job*
   is TRUE at `2.136.0` and stays true. What was wrong is the DOOR the walkthrough went through, so wave `O`
   re-runs `cr070-b`'s script against the new host and the CHANGELOG says which door moved. Re-declaring a launch
   that never stopped working would say something false in the other direction.

⚠ **AND ONE THING THAT IS NOT OURS AND IS IN THE REGISTER: `OQ-WRK-1561`** — which of the five flows a clerk may
complete when the visit has NOT happened. Move-out is ruled (`BR-WRK-055`: it completes regardless). The other
four are a **utility's operating policy and its regulator's**, and getting one wrong bills a real person for a
service they do not have. Nothing waits on it: every flow completes exactly as it does today and the visit is a
separate record, which is what wave `P` builds.

## 1 · The code at HEAD — what every task rests on, verified 2026-09-03

| Claim in the documentation | Measured at HEAD `f02400b3` | Consequence for the plan |
|---|---|---|
| `apps/work/` does not exist; `features/work/` holds one blank page | **TRUE.** `06-backend/apps/` has 13 apps and no `work`; `config/settings/base.py:99` lists `apps.integrations` and no `apps.work`. `07-frontend/src/features/work/` holds `WorkOrderTemplatesPage.tsx` (the blank page, PO 2026-08-25 *"Just keep it black"*) and its test | Wave A creates the app and `apps.py`; the first Work migration is the first |
| `route-b-migrated.txt` lists `features/work/` | **Per FILE, not per folder.** `07-frontend/src/styles/route-b-migrated.txt:2521` lists `features/work/WorkOrderTemplatesPage.tsx` alone (2,976 lines, no glob for the folder) | **Every new file under `features/work/` is its own line, added in the commit that creates it** (B14 rule 21, `DEF-974`); A2 adds the shell's files, each later `2b` task adds its own |
| Six tables exist in `apps/metering/connections.py`, `connection_id` NOT NULL at 699–701 | **TRUE.** `WorkOrder` at line 684; `connection = models.ForeignKey(Connection, on_delete=PROTECT, db_column="connection_id")` at 699–701 with no `null=True`; `attachment_ref` at 769 (written and read by nothing); `WorkOrderTemplate` at 828 with `uq_work_order_templates_seq` on (tenant, service, sequence) and `skill` free text. metering's last migration is `0043_cr054_w1_row_key.py` | The phase-0 column change is **`metering/0044`** — the table is metering's today; where the six models LIVE afterwards is `03-field-map.md` §4, pending §16, and the lane that writes `work/0001` decides it |
| Fourteen finished writers and two readers with no route | **TRUE.** In `connections.py`: `transition_service` 1186 · `submit_connection` 1237 · `hold_connection` 1248 · `release_connection` 1264 · `set_waiting_on` 1285 · `cancel_connection` 1315 · `create_connection` 1382 · `add_connection_service` 1499 · `create_work_order` 1538 · `tag_charges_to_account` 1610 · `create_owner_account` 1908 · `mark_outstanding_work` ~2357 · `close_outstanding_work` · `set_characteristic` 2463; readers `outstanding_work` 2421 · `characteristic` 2544. **Mounted routes are exactly five** (`metering/api.py:2418–2431`): `connections`, `connections/{id}/commit`, `connections/{id}`, `work-orders/{id}/field-result`, `work-orders/{id}/accept` | Wave B mounts fourteen and the queue selector; nothing is rewritten |
| `create_work_order` is *"the one raise every door uses"* | **Its signature is `create_work_order(actor, connection_id, payload)`** — the connection is a required positional argument | `US-WRK-001` changes the contract to an anchor set (connection · premises · account · asset); every later door (A, H, M) calls the new shape |
| Twenty-four seeded starters, gas gated on the light-up, and a write service OWED | **TRUE.** `W6_TEMPLATE_STARTERS` at `metering/sample_data.py:1889` — **24 rows across 8 services** (electric, water, gas, solar, broadband, thermal_heat, battery, fire), gates: *Meter set* ×3, *Pressure test and light-up* (gas), *Container delivery*, *Activate*, *Commissioning*, *Service connection*; written by `_seed_work_order_template_starters` at 2533 with `is_sample=True`; its docstring at 2547: *"a `create_work_order_template` service is OWED"* | Wave D writes the service; wave E makes the 24 editable bundles and adds the gate that keeps every seeded row read |
| `submit_field_result` → `accept_field_result` is the built half | **TRUE.** `connections.py:2053` and `:2116`; accept posts `field_data.set_reads` through the event-read door (2170–2203, `set_reads_posted`) and queues the letter, refused for want of a source kind (`OQ-376`) | Waves B, L and N add consequences to accept inside its one transaction and remove none |
| The connection detail's drawer accepts an order (⚠ **AND THE SCREEN IS RETIRED AS A DESTINATION 2026-09-04 — see §0c and wave `O`; every claim below is still TRUE of the code at the tip and stops being true when `O4` lands**) | **TRUE, and the stale comment is now CORRECTED (2026-09-04, `DEF-WRK-3603`).** `features/customers/ConnectionDetailPage.tsx:254` mutates `acceptWorkOrder`; its header said `GET /connections/{id}` and `POST /work-orders/{id}/accept` were *"NOT mounted"* — `api.py:2429` and `:2431` mount both, the route is wired in `App.tsx`, and `screenIds.ts` badges `NCT-02`, all three of which the header denied. **Four claims across three files** (the screen, `ConnectionDetailPage.test.tsx` E1/E3, `ConnectionDetailPage.dom.test.tsx`'s 404 branch and E1) | **DONE AHEAD OF WAVE B by the coordinating session** — B3 keeps every other clause and does NOT redo this one; re-derive those three files from the pushed tip so the correction is built on rather than over (law 11) |
| Four Settings cards render *arrives with Work*; four Work number series | **TRUE.** `features/tenancy/referenceDataConfig.ts:578–605`: `work_skills · work_safety_kits · work_priorities · work_parts_categories`, each `arrivesWithKey: "settings.reference.arrivesWith.work"`. Numbering: `SettingsNumberingTab.tsx:352` group `work`; the test fixture shows `work_order · WO-{0000} · next 4834`; `connections.py:312` — `work_order` allocates from `GROUP_WORK`; `dispatch_batch` appears in **no backend module** by that name outside notifications' unrelated dispatcher | Wave C wires the four cards and adds `template_no`; `dispatch_batch` stays unwired (`BR-WRK-021`, `OQ-WRK-1497`) and C's test asserts no caller |
| Three Assets checkboxes ship disabled (overview) · four Work controls (CR §1) | **Both right: four controls, three of them checkboxes.** `WorkOrderR5Checkbox` (`features/assets/AssetFlowPages.tsx:104`) rendered at `AssetAddWizard.tsx:999`, `AssetFlowPages.tsx:396` (move) and `:627` (maintenance); plus `AssetInventoryTab.tsx:207` *Parts in Work →* disabled with `assets.flow.workR5`. `AssetMaintenance.cost` (`assets/models.py:521`) is *"CAPTURED and totalled, never posted"*; `log_maintenance` at `assets/services.py:1301`, the D3 comment at 1324; **no column stores a work order** on maintenance. ⚠ **STAMP 2026-09-06 (`DEF-WRK-4125`): TRUE AS WRITTEN, AND SUPERSEDED BY THE WAVE IT PLANS.** Wave M renamed `WorkOrderR5Checkbox` to `RaiseWorkOrderCheckbox`, added a FOURTH tick on the retire wizard's *Replacement* step and made *Parts in Work →* live — so from wave M it is four ticks, not three of four controls. Kept as the record of what was true when the wave was planned; the old symbol exists in this row and nowhere in the code. | Wave M enables all four and posts one form (`Work-028`); the Maintenance history's Work-order column is a READ of `work_orders.asset_id` through the Assets side — Work adds no column to assets |
| Customers' reconnect refuses to book the visit | **TRUE.** `customers/disconnects.py:1214` `VISIT_NOT_SCHEDULED` — *"`work_orders` belongs to metering and cross-module writes are forbidden"*; `features/customers/MoveOutWizard.tsx` exists (the step-4 host) | Wave M's Customers door is two calls from the screen; the constant's docstring is amended, not deleted |
| The message queue's source constant has eight kinds and no `connection` | ⚠ **TWELVE, and still no `connection` — CORRECTED 2026-09-05 at wave L's r11 step 0 (`DEF-WRK-4074`).** This cell read *TEN* and named ten by name; `portal` arrived 2026-09-04 (`CR-068` wave E) and `appointment` on 2026-09-05 (`CR-070` wave I). **That is the THIRD time this one count has gone stale in three days** — `DEF-WRK-3602` corrected eight-to-ten on 2026-09-03 — and the reason it recurs is that **the count is not what the argument turns on**: every document making this point is saying `connection` is ABSENT, which is still true, so the wrong number changes no conclusion and nobody re-reading the paragraph has any reason to check it. **So stop quoting the list.** Read `notifications.models.SOURCE_TYPES`; `metering.connections.dispatch_communication` and `work.seams.notifications_seam.give_connection_kind()` both say so at the place the change is made. `services.py:428` `QueueWriteRefused` is unchanged | `OQ-376` stands exactly as open. **Wave L built the boundary and nothing past it**: the letter is queued, refused, and reported as `queued: false` with the platform's own sentence and `tracks: "OQ-376"` — never filed as `notice`, never a stamp on a send that did not happen |
| No Work permission, no technician role | **TRUE.** `identity/models.py:65–70` `Role.code` is `system_admin | billing_clerk | executive`; `Permission` holds the nine A4 rows (`A4_MATRIX`); `core/permissions.py` checks **roles** (`RoleRequired`, `require_role`), not permissions | Wave F declares `work_accept` in the catalogue and assigns it to no role; the check in accept resolves as today and logs once (`OQ-WRK-1492` boundary); a permission-based check is identity's companion work |
| Tenancy owns areas, certification types, number series and the document store | **TRUE.** `tenancy/models.py:611` `Area` · `:855` `CertificationType` (+ `CertificationTypeLookupHandler`, `services.py:4909`) · `:1242` `NumberSeries`; `document_models.py:295` `DOCUMENT_KINDS` = **33 kinds** (16 + 17), CHECK `ck_stored_documents_kind` at 503; `document_store.store()` at 272, signed URLs with `url_ttl_seconds()` at 531. Premises carry `lat`/`lng` (`metering/models.py:404–405`); `geocode_premises` command exists | Work reads all of these through seams; the three document kinds are **tenancy's migration** (33 → 36), written by wave K's lane in tenancy's own app; the map (I) reads coordinates it never writes |
| Named-queue pattern | **TRUE.** `core/jobs.py`: `set_job_handler` 445 · `set_job_queue` 468 · `job_queue` 503; `config/celery_routes.py` routes by kind; `billing/run_jobs.py:680–699` registers handlers + queue; `docker-compose.yml`: `celery` (`-Q celery`, 256) · `celery-billing` (`-Q billing`, 383) · `celery-beat`; G59 guards the billing pair. **No `beat_schedule` anywhere in `06-backend/config`** | Wave J adds `work.push` on queue `work` with `celery-work` in the same commit (G59's clauses cloned); wave M's nightly `work.rules_sweep` is a beat entry — the product's first unless `CR-069` wave G lands before it |
| CI proves things on PostgreSQL; `tests/pg/` exists | **Only migrations.** `.github/workflows/ci-backend.yml:24–50` boots `postgres:16` and migrates against it; line 97 runs `pytest -q` (SQLite). **There is no `06-backend/tests/pg/` folder at this HEAD** — the one law-14 proof is `06-backend/tests/test_def_2444_law14_savepoint_pg.py`; `qa.yml` runs `npx playwright test` (the `08-qa` suite), the render checks are run by hand as their headers say | Wave A adds a CI step running the `*_pg.py` files against the service (law 14) so L's per-item savepoints are proved in CI; if `CR-069` wave A lands its step first, A2 reuses it |
| Gates and the guard list | `run_gates.py` GATES; highest file `g74_tables_nobody_reads.py` → **next free G75**, taken at push. `10-scripts/gates/human_owned.txt` has **no work glob**; `06-backend/**/migrations/*rls*` already matches every RLS migration. G74 (a model nothing names) is the precedent for `BR-WRK-014`'s row-level gate | A2 adds globs for `apps/work/seams/metering_seam.py` and `apps/work/costing.py`; every wave that creates tables has a 🔒 `*rls*` migration and a ledger row |
| Screen badges | `screenIds.ts:1169–1181` routes `/:tenant/work/templates` with badge `WRK-19`; `g29_allocated_badges.txt:108` has WRK-19 only; r10 draws `WRK-01..18`; `sidebarDestinations.ts:43` keeps `/work` in the unbuilt list; `AppShell.tsx:228–240` is the rail entry. PO 2026-09-03: every screen shows an id; **whether `Work-nnn` renders is unruled** (`BR-WRK-005`) | Each `2b` that mounts a route adds a `screenIds.ts` row and a `g29` row with r10's `WRK-nn` from `01-overview.md` §6; nothing renders a `Work-` number |
| The staff kit has the pieces | `07-frontend/src/components/`: `WizardFrame` (steps · `commitVariant`), `DataTable`, `FilterBar`, `KPIStrip`, `StatusPill`, `MoneyCell`, `PageHeader`, `Panel`, `ConfirmDialog`, `RowActions`, `ListPager`, `icons.tsx`. **No `EditableTable`, `SegmentedControl` or `Thumbnail`** (the inventory's three). **No service worker, manifest or offline store anywhere in `07-frontend/src`** | D builds `EditableTable`; C builds `SegmentedControl`; K builds `Thumbnail`; J builds the phone shell from nothing |
| New Connect step 6 proposes nothing; S86 segments are off | **TRUE.** `NewConnectWizard.tsx:1273`: *"Those templates are not built yet, so no orders are proposed here."*; `NewConnectsTab.tsx` disables four of five segments on `OQ-371` | Wave E replaces the sentence with the proposal; A leaves `OQ-371` exactly as it is |
| Journeys `J60`–`J67` exist | **Not at `f02400b3` — written since, at `d0cf0b00`, while this plan was being drafted:** `08-qa/01-e2e/journeys/J60`–`J67` exist, each headed *NOT ACTIVATED — no `J6n.spec.ts`* because its first step is impossible at HEAD; `J61` extends `J27`, itself not activated | Each demonstrating wave **activates** its journey — writes the `.spec.ts` beside the other journey specs, runs it green on the build, removes the banner — rather than writes the file |
| Fixture tenants and actors | `seed_demo` provisions **Brazos Bend Utilities**; `seed_sample_records` (`sample_data.py:1064`) writes the starters at 1253; **Lone Star Ridge WSC is not seeded** (no hit in `tenancy/brand.py`) — tests provision it; M. Torres, D. Ortiz, Alex Reed are story actors | Each wave's `2c` seeds what its demo needs; every isolation test provisions the second tenant |
| Eleven locale catalogues | **TRUE.** `07-frontend/src/i18n/locales/`: de · en · es-MX · es · fr-FR · hi · id-ID · it-IT · ja-JP · ko-KR · pt-BR | Every new key lands in all eleven (G15); every refusal is five or six words (G33) with a key (G32, baseline 0) |
| Phase 0's exit test: *"records a leak investigation on an existing meter, holds it, releases it, and it appears in the approval queue"* | **Mixes two records.** `hold_connection` / `release_connection` act on a CONNECTION; a leak investigation on an existing meter has none (that is the point of `WM-01`). `04-flows.md` already reads the exit as *"the first half of J62 and the last screen of J61"* | Demo B shows both honestly: the leak investigation goes raise → field result → queue; hold and release are shown on a build (`CON-26-0117`) |

## 2 · The phases — three increments, each with a launch sentence

| Phase | LAUNCH (`CR-070` §11, kept) | Exit test — a demonstration, and the rule it asserts | Stories | Waves | Rollback (§14) |
|---|---|---|---|---|---|
| **0** | **A clerk can raise, hold, cancel and close a job this week** — *no decision needed* | Wave B's walkthrough **on a deployed build, not a green suite**: a leak investigation raised on `77 Cedar Ct` with no connection — impossible today — closes from the field and appears in *Awaiting approval*; a build is held and released from its detail; an order with no anchor at all is refused by the database (`BR-WRK-006`, `BR-WRK-007`, `BR-WRK-002`) | 001 · 002 · 003 · 004 · 005 · 006 | A · B · **O** | Clean — a nullable column, mounted buttons and a redirect |
| **1** | **A utility authors its own job templates, and the wizard proposes them** — *no decision needed* (`BR-MET-109`: templates are developed *"in work order section"*) | Wave E's walkthrough (`J60`): Alex adds a skill and a type in Settings, walks eight steps from the *Meter exchange* pack, publishes `ST-0001`, and New Connect step 6 proposes **5** orders for Electric + Water — with nothing written until step 9 (`BR-WRK-011`, `BR-WRK-016`, `BR-WRK-013`) | 007 · 008 · 009 · 010 · 012 · 013 · 014 · 015 · 016 · 017 · 018 · 019 · **039** | C · D · E · **P** | **Hide the section and keep the data** — a utility has authored templates |
| **2** | **A dispatcher assigns work to a crew, and the technician works it on a phone** — *unblocked by the placement ruling* | Wave L's walkthrough (`J61` + `J65`): M. Torres assigns; the phone shows the job; safety locks the tasks and **the server refuses a close carrying an unticked safety row**; D. Ortiz works three jobs offline and syncs once — a second sync adds nothing, **proved on PostgreSQL**; M. Torres accepts and the reading is a `meter_reads` row written by metering's own door, dated to the completion (`BR-WRK-037`, `BR-WRK-042`, `BR-WRK-003`, `BR-MET-110`) | 011 · 020 – 054 **less 039** (35) | F · G · H · I · J · K · L · M · N | Hide and keep — photographs, signatures and reports are evidence |

⚠ marks a story built to the boundary and stubbed `NotImplementedError("OQ-…")`. 🔒 marks a sensitive path — a
`HUMAN-REVIEW-PENDING` file and a review-ledger row in plain English with a figure: every `*rls*` migration
(waves C, D, F, G, H, K, M, N), `apps/work/seams/metering_seam.py` (wave L — the one door through which a
technician's number becomes billing data) and `apps/work/costing.py` (wave N — money rounding on a
customer-facing document). **Nothing in this CR touches a ❄️ B4/B5 figure**; the one card that would have,
`WM-46`, is closed by ruling and `US-WRK-052` builds nothing.

⚠ **THE RUNNING ORDER IS NOT THE ALPHABET (2026-09-04, §0c).** Waves `O` and `P` were appended after the ruling
and nothing was renumbered, so read the order from this table and not from the letters: **`A` `B` `C` are
landed; then `O` — the destination — then `D` `E`, then `P`, then `F`–`N`.** `O` runs first of what remains
because every wave after it points somewhere; `P` runs after `E` because it reuses `E2`'s proposal reader
rather than writing a second one.

## 3 · The waves

Wave letters are unique across this CR. **Size:** S ≤ 1 day · M 2–3 days · L 4–5 days, per person. **Demo
scripts** are clicked by the walkthrough named in the wave's `2d` task; fixture tenant **Brazos Bend Utilities**
(`seed_demo`) unless said, with **Lone Star Ridge WSC** provisioned by the tests as the isolation tenant; actors
**M. Torres** (supervisor and dispatcher), **Alex Reed** (System Admin), **D. Ortiz**, **M. Chen**, **R. Patel**,
**J. Kaur** (technicians), **Sarah Miller** (`A-10688`, `221 Oak Ave · Unit 3`), as `04-flows.md` uses them.
`WorkTabs` renders only the tabs whose screen exists at that wave — a tab pointing at nothing is dead UI (law 2) —
and grows to its eight (Orders · Awaiting approval · Map · Crews · Parts · Templates · Rules · Performance) as the
waves land. Every `2b` task that mounts a route adds its `screenIds.ts` row and its `g29_allocated_badges.txt`
row with r10's `WRK-nn` from `01-overview.md` §6, and renders no `Work-` number (`BR-WRK-005`, unruled).

---

### Wave A — the module exists, and an order can stand alone · phase 0

**Goal a clerk can see:** the Work entry on the rail stops being a *not built yet* screen and opens a Work shell
whose Orders tab lists every open order across every connection; from the terminal a leak investigation is raised on
a premises with no build — refused today by a NOT NULL — and appears in that list.
**Stories:** US-WRK-005 · US-WRK-001 · US-WRK-004 · US-WRK-006 (the fixture, phase-0 slice; grows under every later `2c`)
**Depends on:** nothing — this is day one. **Blocked by:** nothing (`OQ-371` bounds `Work-001`'s segment strip, which stays exactly as it is).
**Version:** the next free `<change>`; attaches CHANGELOG's waiting *[Unreleased]* entry if no sibling has.
**Size:** two people, two weeks.

| Task | r11 | What it touches — verified at HEAD | Stories · rules | Depends on | Design xref | Size |
|---|---|---|---|---|---|---|
| **A1** | ground / doc | **B2 and the module map FIRST, in the commit that carries the first migration** (`CR-070` §2a: *"Amend the module map, dated, in the same commit as the first migration — not before, and not after"*). `04-docs/02-decisions/02-database-design-brief.md` gains `### Module: work` under §2 (the phase-0 column change from `03-field-map.md` §3 rows 1–4; the new tables arrive with their waves) and an addendum row; `CLAUDE.md`'s module map gains `work` as the eleventh code module, dated 2026-09-03 with the ruling quoted; `12-governance/14-id-reservations.md:45` already holds the id block — nothing to add | 005 · `BR-WRK-001` · hard rule 1 | — | `CR-070` §2, §10 | S |
| **A2** | ground | `07-frontend/src/styles/route-b-migrated.txt` gains one line per new file under `features/work/` **in the commit that creates each** (the list is per file — `:2521` lists the blank page alone). `10-scripts/gates/human_owned.txt` gains globs + reasons for `06-backend/apps/work/seams/metering_seam.py` (the door a field reading takes into billing data) and `06-backend/apps/work/costing.py` (money rounding on a customer-facing document); `**/migrations/*rls*` already matches. `.github/workflows/ci-backend.yml` gains a step running `pytest -q 06-backend/tests/*_pg.py` against the `postgres:16` service it already boots (`DJANGO_SETTINGS_MODULE=config.settings.local`, `DATABASE_URL=…sbh_ci`, `JOBS_EAGER=false`) — no step runs them at HEAD; if `CR-069` wave A's step has landed, reuse it. Prove it RED by breaking the savepoint in `test_def_2444_law14_savepoint_pg.py` (law 7) | 005 · B14 rule 21 · G7 · law 14 | — | — | S |
| **A3** | 2a | **`06-backend/apps/work/`** — `__init__.py`, `apps.py` (`AppConfig.ready()` — registers nothing yet; J and M register jobs here), `seams/` with **one read-only file per module** — `assets_seam.py` · `metering_seam.py` · `customers_seam.py` · `tenancy_seam.py` · `identity_seam.py` — each following `apps/metering/seams.py`'s `resolve(module, attribute)` shape and exposing only the reads Work needs (a connection, a premises with its `lat`/`lng`, an account, an asset, an area, a certification type, a user); `selectors.py` — `open_orders()` every open order across every anchor (the Orders tab's read; the six filters are G); `api.py` + one `include` in `config/urls.py` — `GET /work-orders` (minimal list). `"apps.work"` into `INSTALLED_APPS` beside `apps.integrations` (`base.py:99`). **No model of its own yet** — where the six existing models live is `03-field-map.md` §4, decided by the phase-1 lane after reading §16 | 005 · `BR-WRK-001` · `002` · B2 §2 | A1 | `CR-070` §10 | M |
| **A4** | 2a | **`metering/0044`** (metering's last is `0043_cr054_w1_row_key.py`): `work_orders.connection_id` → nullable; `premises_id` FK NULL → premises; `account_id` FK NULL → accounts (reviewed-set FKs, B2 §2); **`ck_work_orders_has_anchor`** CHECK — at least one of connection · premises · account · `asset_id` (the FK that exists at `connections.py:711–727` and nothing writes). `create_work_order(actor, connection_id, payload)` at `connections.py:1538` becomes `create_work_order(actor, payload)` with an anchor set — every existing caller (`commit_connection` at 1666, the seeder) passes the connection explicitly; `refresh_connection_state()` (1082) is untouched by an order with no connection; the audit row names the anchor. On PostgreSQL the CHECK refuses an order with nothing (`US-WRK-001` TC on PG) | 001 · `BR-WRK-006` · hard rules 1 · 7 | A1 | `WM-01` | M |
| **A5** | 2b | **`features/work/WorkShell.tsx`** + `WorkTabs` (per `09-component-inventory.md`: the Settings tab strip's component, different tabs) mounted at `/:tenant/work`; **`/work` removed from `UNBUILT_SIDEBAR_DESTINATIONS`** (`sidebarDestinations.ts:43`) — `sidebarReachability.test.tsx` then requires a real destination; the rail entry (`AppShell.tsx:228–240`) unchanged. **Orders tab** — `features/work/OrdersPage.tsx`, template W1 for now (W2's KPI strip, filters and bulk arrive in G): kicker *WORK* · title *Work orders* · the one sentence *Everything open, across every connection and every account.* · `DataTable` ORDER · TYPE · PREMISE · SVC · STATE · OUTCOME · CONNECTION (a dash where there is none) · CR-045 toolbar · footer. **Templates tab** keeps the blank `WorkOrderTemplatesPage.tsx` until D replaces it. `Work-001` (`NewConnectsTab.tsx`) unchanged — `OQ-371`'s four disabled segments stay disabled with the server's reason; `Work-006` is now the shell. `screenIds.ts` row for `/work/orders` with r10's `WRK-01`; `g29` row. New keys in all eleven catalogues | 004 · 001 · `BR-WRK-005` · B14 rules 2 · 20 · 21 · 31 · 32 · g13 · g15 · g29 | A3 · A2 | `Work-007` (the pack: `wireframes/Work-007.png`, the head and the table only) · `Work-006` · `Work-001` | L |
| **A6** | 2c | Tests named for their TCs: `US-WRK-001` TC-1..6 (the CHECK on PG in a `*_pg.py`; an order on `77 Cedar Ct` with no connection; `refresh_connection_state` untouched) · `US-WRK-005` TC-1..7 (TC-1 the app exists and is the eleventh; TC-2..4 the gate shown RED first) · `US-WRK-004` TC-1..6 (the rail entry resolves; the segments still refuse on `OQ-371`) · `US-WRK-006` phase-0 slice — **`apps/work/sample_data.py`** seeds `77 Cedar Ct` (`A-10891`, no build) and one order per existing state; the second tenant provisioned by the fixture for every isolation TC | 001 · 005 · 004 · 006 | A3–A5 | — | M |
| **A7** | gate | **The boundary gate** (`CR-070` §12 gate 1; next free number is **G75** at HEAD — take it at push): no file under `apps/work/**` names another module's model in a write position — `.objects.create/update/delete/bulk_*`, `.save()`, `.delete()` on anything not in `apps.work` (metering's `work_orders` is exempt only through the seam's named door until §16 settles the move); RED by adding `AssetModel.objects.create(...)` to `services.py` (`US-WRK-005` TC-3); RED again by a `JournalLine` write (hard rule 5). Registered in `run_gates.py`'s `GATES` in the same commit (G42 contract: `run()` + `__main__` + `selftest()`) | 005 · `BR-WRK-002` · hard rule 5 · law 7 | A3 | §12 gate 1 | M |
| **A8** | 2d | **`10-scripts/render-checks/cr070-a-work-shell-and-anchor.mjs`** — the demo script below, asserting: the rail's *Work* opens a shell with two tabs · the Orders table lists the seeded orders across two connections and the one with no connection shows a dash under CONNECTION · the page carries no `NotBuiltYet` frame · no string matches `BR-[A-Z]+-\d+` or a uuid (rule 31/32) · the utilities compiled (computed style) · no sideways scroll at 1440 · screenshots beside `wireframes/Work-007.png`. Plus the terminal proof quoted in the PR: `POST /work-orders` with no anchor at all → the database's own refusal, on PostgreSQL | 001 · 004 · 005 · `BR-WRK-006` · B14 31 · 32 · law 6 | A5 · A6 · A7 | — | S |
| **A9** | doc / version | CHANGELOG entry (attach the waiting *[Unreleased]* entry if still unversioned) · `package.json` + `pyproject.toml` bumped together (G35) · decision-log row for the wave's judgments (the seam set; the Orders tab as W1 first; `create_work_order`'s new contract) · `20-wave-tasks.tsv` rows A1–A9 → `verify` → `done` | — | A8 | — | S |

**Demo script A (Alex Reed):** 1 sign in to Brazos Bend → 2 the rail's *Work* — the *not built yet* screen is gone;
a shell with *Orders* and *Templates* → 3 *Orders* lists the seeded open orders across `CON-26-0117` and
`CON-26-0122` → 4 in the terminal: raise a *Leak investigation* on `77 Cedar Ct` with `premises_id` and no
connection — **accepted**, where yesterday the database refused → 5 it is in the list, CONNECTION reads a dash →
6 raise one with no connection, no premises, no account, no asset → the database refuses → 7 sign in as J. Okafor
of Lone Star Ridge — the shell, and an empty list.
**Exit test (asserts a rule):** `BR-WRK-006` — the CHECK refuses on PostgreSQL, not only in Python; `BR-WRK-002` —
the boundary gate goes RED on a direct write to `assets` and on a journal line; hard rule 1 — with no
`app.tenant_id` set, `work_orders` returns zero rows.

---

**Wave A — AS BUILT (2026-09-03, the CR-070 wave A build lane; product `2.130.0`).** Every task above was
re-verified against the code before it was built, and six of its claims were found to have moved or to be wrong.
Each is recorded here rather than left for the next lane to rediscover:

* **A2 — `human_owned.txt` gains NO glob from this lane, by G53's rule and not by omission.** The row says to add
  globs for `apps/work/seams/metering_seam.py` and `apps/work/costing.py`; `G53`'s own docstring says *"adding a file
  is a PROCESS EVENT and is the Product Owner's call, not a lane's"*, and two lanes on 2026-08-28 declined for the same
  reason. Neither file holds money logic in wave A (`costing.py` does not exist; the seam's one write is a named call
  to metering's service). The globs go on the PO's agenda in the decision-log row of the same day. **The CI step for
  `tests/test_*_pg.py` was already in `.github/workflows/ci-backend.yml`** (`CR-069` wave A landed it), and it is
  reused; CI itself has no runner, so the PostgreSQL proofs were run locally on `sbh_cr070a` and quoted.
* **A5 — `UNBUILT_SIDEBAR_DESTINATIONS` lives in `07-frontend/src/components/NotBuiltYet.tsx`, not in
  `sidebarDestinations.ts:43`** (that file holds the path list the smoke check walks). The entry left there. **No
  `g29_allocated_badges.txt` row was needed**: `WRK-01` is r10's own badge, and that file holds only ids r10 does not
  draw. The shell is three flat routes with a `tab` prop (`PremisesTabsPage`'s shape), not a nested `<Outlet/>`,
  because `screenIds.test.tsx` flattens an index child onto its parent's path and would demand `/work` twice.
* **A6 — no `apps/work/sample_data.py`, and the fixture's `77 Cedar Ct` is metering's seat.** A Work seeder cannot
  plant a premises without writing (or tagging) a metering row — the very thing `BR-WRK-002` and G78 forbid — so the
  address is one row in metering's own `W6_SEATS` (`apps/metering/sample_data.py`, unit `SCW-U-319`), planted through
  `create_premises` and removed with the rest. **No connection-less order is seeded**: a completed one cannot exist
  through the doors until wave B (`submit_field_result` and `accept_field_result` read `order.connection`), and the
  demo raises the planned one live from the terminal. **`A-10891` is not seeded** — the account-anchored door is wave
  M's, and the seat carries no account. `US-WRK-006`'s phase-0 slice is, as its own text says, *"nothing new"* plus
  this one address.
* **A8 — the terminal proof goes through `apps.work.services.raise_work_order`, not `POST /work-orders`.** A3's
  table mounts `GET /work-orders` alone and `07-endpoints.md` §1 row 14 puts the POST in wave B with the screen that
  presses it (law 2: a route with no screen is half a feature). The refusal is shown twice — the service's sentence,
  then the database's CHECK around it — and quoted in the lane report.
* **A4 — `create_work_order`'s contract is WIDENED, not replaced.** Thirty callers pass the connection positionally;
  the parameter is now optional and the payload may carry the anchor set. Recorded in the decision log.
* **Demo step 3 names `CON-26-0117` and `CON-26-0122` — measured on the seeded fixture, `CON-26-0117` has NO open
  order.** Brazos Bend sells electric and water, so its gas and sewer orders are never planted and its four seeded
  orders are all accepted (closed); the Orders tab correctly omits it. The walkthrough asserts `CON-26-0122` (four
  planned), asserts `CON-26-0117`'s ABSENCE, and measures the list spanning five builds. The story's *"5 of 7"* is
  B18's drawn figure, not the seed's — `_seed_w6_connections` says so in its own header.
* **§1's "Orders tab lists every open order":** *open* is `planned · in_progress · blocked`. A `completed` order that
  nobody has accepted is the approval queue's (`BR-WRK-007`, wave B), not this list's — `metering_seam.
  OPEN_WORK_ORDER_STATES` says so and `test_us_wrk_004_orders_list.py` asserts it.

Three defects found in the tree while building, none of them this wave's, are filed in the register the same day: the
connections suite's manifest test has been red since `DEF-2961`'s own fix; the Integrations grid's twelve undeclared
utilities paint no colour (`routeBUtilities.test.ts` red at the tip); a nineteenth sample block landed without its
provisioning-step mirror. **Native review owed** on the eleven catalogues' forty-two new lines each (B14 rule 35).

---

### Wave B — fourteen doors, and the queue · phase 0 (the phase-0 LAUNCH)

**Goal:** the eleven connection acts and the raise that only a Python shell could reach are buttons on the
connection's detail; every finished order nobody has accepted, on any connection or none, is one list.
**Stories:** US-WRK-002 · US-WRK-003
**Depends on:** A (the anchor; the shell). **Blocked by:** nothing. **Runs beside C.**
**Version:** next free `<change>`. **Size:** one person, one and a half weeks.

| Task | r11 | What it touches | Stories · rules | Depends on | Design xref | Size |
|---|---|---|---|---|---|---|
| **B1** | 2a | **Fourteen routes, no rewrite.** The eleven connection acts (`07-endpoints.md` §1 #1–#13 less the raise) registered **beside the five that exist at `metering/api.py:2418–2431`** — metering owns `connections` today, so the routes sit where `connections` sits and move with the models if §16 moves them; each a thin view over the service at its line (`hold_connection` 1248 · `release_connection` 1264 · `set_waiting_on` 1285 · `cancel_connection` 1315 · `submit_connection` 1237 · `transition_service` 1186 · `add_connection_service` 1499 · `create_owner_account` 1908 · `tag_charges_to_account` 1610 · `set_characteristic` 2463 · `mark_outstanding_work` · `close_outstanding_work`); **`POST /work-orders`** in `apps/work/api.py` over A4's `create_work_order`; the two readers (`characteristic` 2544 · `outstanding_work` 2421) ride inside `GET /connections/{id}`. Every refusal a catalogue sentence of five or six words (G33) with a key in all eleven (G32, baseline 0); every mutating route enforced server-side regardless of the button (`BR-SHL-025`); every act writes its audit row | 002 · `BR-WRK-006` · `BR-SHL-025` · B14 rule 33 · hard rule 7 | A4 | `WM-02` | M |
| **B2** | 2a | `apps/work/selectors.py` — `awaiting_approval()`: `accepted_by IS NULL AND state = completed`, across every connection and every anchor; **no new table — the null is the queue**; `GET /work-orders/awaiting-approval` with the drawing's columns (order · connection · premise · service · outcome · completed · waiting-days); cross-tenant ids → 404 identical to absent | 003 · `BR-WRK-007` · hard rule 1 | A3 | `WM-03` | S |
| **B3** | 2b | **`Work-002`** — `features/customers/ConnectionDetailPage.tsx` gains the action row: *Hold…* · *Release…* · *Cancel…* (danger) · *Waiting on…* · *Add service* · *Mark outstanding work* · *Close* on a to-do · *Raise order* — each **disabled with its reason** when the state forbids it (`BR-SHL-025`), each calling B1; the header comment at lines 25–27 corrected (accept IS mounted — law 1). **`Work-009`** — `features/work/AwaitingApprovalPage.tsx`, template W1 per `08-screen-layouts.md`: kicker *WORK* · *Awaiting approval* · *The field has finished these. Nobody has accepted them yet.* · ORDER · CONNECTION · PREMISE · SERVICE · OUTCOME (`StatusPill` Passed green / Partially done amber) · COMPLETED · WAITING · eye icon → the `Work-003` drawer (its Accept unchanged) · footer *3 orders · oldest waiting 6 days* · **the note bar rewritten by rule 32** — *nobody has accepted them* in place of `accepted_by`. `WorkTabs` gains *Awaiting approval*. `screenIds.ts` row; a `g29` row minted by the lane in that file's shape (r10 draws no badge for this screen — `01-overview.md` §6 reads *—*; not decided here) | 002 · 003 · `BR-WRK-007` · `BR-SHL-025` · B14 rules 6 · 15 · 20 · 32 · g13 · g15 | B1 · B2 · A5 | `Work-009` (`wireframes/Work-009.png`) · `Work-002` · `Work-003` | L |
| **B4** | 2c | `US-WRK-002` TC-1..7 (each of the fourteen reachable; a forbidden state refused server-side with the button disabled; audit per act) · `US-WRK-003` TC-1..7 (an accepted order leaves the list; an order with no connection is in it; Lone Star's queue empty). Fixture: `WO-4906 · Meter set · Gas · CON-26-0117` (Passed, 6 days), `WO-4903` (Partially done), `WO-4917 · Container delivery · Trash` — the drawing's three rows | 002 · 003 | B1–B3 | — | M |
| **B5** | 2d | **`cr070-b-fourteen-doors-and-the-queue.mjs`**: the demo script below, asserting the three rows and the footer sentence against `wireframes/Work-009.png` · the note bar contains no `accepted_by` · every Work-002 button either enabled or disabled **with a sentence** · a leak investigation raised on `77 Cedar Ct`, given a field result through `POST /work-orders/{id}/field-result`, appears in the queue with CONNECTION a dash · Accept from the drawer removes it · screenshots | 002 · 003 · `BR-WRK-007` · `BR-MET-110` · B14 32 | B3 · B4 | — | S |
| **B6** | doc / version | CHANGELOG (the **phase-0 entry**) · lockstep · TSV · decision-log row · **phase 0 LAUNCH declared** — *a clerk can raise, hold, cancel and close a job this week* — proved **on a deployed build, not a green suite** (`CR-070` §11 0.6); rollback stated: a nullable column and mounted buttons | — | B5 | — | S |

**Demo script B (a clerk, then M. Torres):** 1 open `CON-26-0117` → *Hold…* with a reason → the state reads
*On hold* and *Waiting on* carries the reason → 2 *Release…* → back to *In progress* → 3 *Cancel…* is danger tier
and asks first → 4 raise a *Leak investigation* on `77 Cedar Ct` — no connection — from the terminal → 5 send its
field result *Passed* → 6 Work → *Awaiting approval*: the leak investigation is there beside `WO-4906`, its
CONNECTION a dash, *4 orders · oldest waiting 6 days* → 7 open `WO-4906` → *Accept* → it leaves the list and the
gas service on unit 14 reads *Activated* → 8 Lone Star Ridge's queue is empty.
**Exit test (asserts a rule):** `BR-WRK-007` — the queue is a null, not a table (no new migration in this wave);
`BR-SHL-025` — a hold on a cancelled connection is refused by the server with a five-or-six-word sentence while
the button is disabled with the same reason; `BR-MET-110` — nothing activates at the field result, only at Accept.
**Phase 0 closes when A and B are done: six stories.**

**Wave B — AS BUILT (2026-09-04, the CR-070 wave B build lane; product `2.136.0`). ⚠ AND THE ACTS WERE
RE-HOSTED BY WAVE `O` AT `2.141.0` THE SAME WEEK, SO THE SCREEN HALF OF `B3` BELOW NAMES A FILE THAT NO
LONGER EXISTS.** Verified task by task against the code on 2026-09-05 by a later lane; where this table and
the code disagreed, the code won and the difference is written out here rather than left to be rediscovered.

⚠ **THIS STAMP IS THE POINT OF THE EXERCISE, NOT A FORMALITY.** On 2026-09-05 **two lanes were dispatched to
build wave B** — the backend half and the screen half — because wave `O`'s section directly above describes
wave B in the past tense (*"landed as `2.136.0`"*) while this table still read as work to do. Neither lane
wrote a line; both spent their step 0 discovering the wave was finished. **Ratifying the work and updating
the pointer to it are two acts, and only the first one feels like the work** — the same shape as B14's
rule-count line going stale five times (`CLAUDE.md`, hard-won law 12's lesson about pointers).

* **B1 — fourteen routes, and the plan's own cell miscounts them.** This row says *"the eleven connection
  acts"* and then **lists twelve**. `07-endpoints.md` §1's header is the count that survives measurement —
  *"The fourteen writers mounted, and the queue — 15"* — and fourteen is what was built, matching
  `US-WRK-002` §5's table and TC-7's guard. **Twelve connection sub-paths** are registered in
  `apps/metering/api.py`'s single `urlpatterns` (line 2696), every literal before the bare
  `<uuid:connection_id>` so no literal is reachable only by having beaten a converter; **`create_connection`
  is the POST half of the existing `connections` view** (one path, one view — Django reaches only the first
  view registered on a path), and **`create_work_order` is `POST /work-orders` in `apps/work/api.py`**
  because Work owns the raise every door uses. The two READERS — `outstanding_work()` and `characteristic()`
  — ride inside `GET /connections/{id}` and got no route of their own, as the row asks. Every view is thin:
  no refusal, default, derivation or audit row is authored in the view layer, because each service already
  writes its own. **No new refusal sentence was added by this wave**, so G32's unresolved count stayed 0 and
  G33's six-word cap was owed no new line — the row's *"a key in all eleven (G32, baseline 0)"* is met by
  there being nothing to add, not by adding eleven translations. **`AdminOrClerk`, not `AnyTenantRole`, on
  every write**, and TC-3 proves `BR-SHL-025` with an Executive rather than the Billing Clerk the story names
  (A4 gives the Clerk this write; this product has three roles).
* **B2 — met exactly as written, and the null really is the queue.** `awaiting_approval()` at
  `apps/work/selectors.py:195`, over `metering_seam.awaiting_approval_queryset()`, which filters
  `state = completed AND accepted_by IS NULL` and nothing else. **BOTH HALVES ARE LOAD-BEARING**: a `planned`
  order also has no `accepted_by` and is not awaiting anyone (TC-3), and `completed` is exactly the state
  `OPEN_WORK_ORDER_STATES` leaves out, so the Orders tab and this queue can never show the same row. Routed
  at `apps/work/api.py:346` as `work-orders/awaiting-approval`, **above** the bare `work-orders` path so the
  literal wins. Sorted `completed_at` ascending, nulls last, id as tiebreak; `oldest_waiting_days` computed
  over the WHOLE queue rather than the page in hand, and `None` on an empty queue. **The exit test holds and
  was re-measured: this wave added NO migration.** Metering's only CR-070 migrations are `0044`
  (wave A's anchors) and `0045` (wave C's template columns); `accepted_by` has been nullable since
  `metering/0027`, which is what `WM-03` means by *"one query, no new table"*.
* **B3 — BUILT, THEN RE-HOSTED, AND THE FILE THIS ROW NAMES IS DELETED.** `B3` put the action row on
  `07-frontend/src/features/customers/ConnectionDetailPage.tsx`. **Wave `O` deleted that file** (`§W.11`,
  task `O4`) and the acts now live in **`07-frontend/src/features/work/buildViews.tsx`**, drawn on the
  premises and on the account, `data-act` per button. **There are EIGHT acts, not the seven wave O's prose
  said in four places** (`DEF-WRK-3749`) — *Raise order* is the eighth. `Work-009` landed as
  `features/work/AwaitingApprovalPage.tsx` and is untouched by the re-hosting except for `O5`: its
  `CONNECTION` cell keeps its text and its LINK now goes to the build's home. ⚠ **Grep by PATH, never by
  basename:** `features/integrations/ConnectionDetailPage.tsx` is a different screen with the same file name
  and is not related to this row.
* **B4 — present and green.** `06-backend/tests/test_us_wrk_002_doors.py` (947 lines) and
  `test_us_wrk_003_queue.py` (501 lines): **45 cases, all passing** on 2026-09-05. Both files record their
  RED-first proof in their own footer, which is what hard-won law 7 asks for. The PostgreSQL half —
  `test_us_wrk_003_queue_pg.py`, `test_us_wrk_rls_pg.py`, `test_us_wrk_001_anchor_check_pg.py` — is **12
  cases, all passing** against a real PostgreSQL (law 14).
* **B5 / B6 — present.** `10-scripts/render-checks/cr070-b-fourteen-doors-and-the-queue.mjs` exists and
  asserts `acts.length === 8`; the CHANGELOG carries `[2.136.0] — 2026-09-04 · A clerk can raise, hold,
  cancel and close a job`. **G78 passes** — 13 files under `apps/work` write no other module's table and
  import foreign models only under `seams/`.
* **One red test found while verifying, and it is wave C's rather than this wave's.**
  `tests/test_us_wrk_007_010_reference.py::test_us_wrk_010_tc6_...` asserts
  `str(raised.value) == "OQ-WRK-1490"` while `work/services.py:133` now raises the RULING's own sentence
  (*"ruled 2026-09-04: Work keeps a parts register and an issue log and no stock at all…"*). Commit
  `523d3625` changed the three stub messages so nobody has to look an id up; the one test that asserted a
  stub message by value was not changed with it. Filed by the verifying lane; it blocks nothing in wave B.


---

### Wave C — Settings tells the truth · phase 1

**Goal:** the four Work cards that have read *arrives with Work* for three weeks hold real rows; a type, a
priority with its SLA hours, a skill, a safety kit, a parts category and a part can be added and appear in the
pickers; the Parts tab is a register with a unit cost and **no stock column**.
**Stories:** US-WRK-007 · US-WRK-008 · US-WRK-009 · US-WRK-010 ⚠ (stock) · US-WRK-012
**Depends on:** A3 (the app). **Runs beside B.** **Blocked by:** `OQ-WRK-1490` bounds the stock half of 010 only;
`OQ-WRK-1497` (what a dispatch batch is) blocks nothing — the series stays unwired.
**Version:** next free `<change>`. **Size:** two people, one and a half weeks.

| Task | r11 | What it touches | Stories · rules | Depends on | Design xref | Size |
|---|---|---|---|---|---|---|
| **C1** | 2a | **`apps/work/models.py` — six tables** (`03-field-map.md` §2.1 less `labour_rates`, which is N): `work_order_types` · `work_priorities` (Urgent 4 h · High · Normal · Low seeded, unique rank) · `work_skills` · `work_safety_kits` · `part_categories` · `parts` (`unit_cost numeric(18,4)`; **no `on_hand`, no `reorder_at`, no `location`**). `work/0001_initial` + **`work/0002_rls_force`** 🔒 (RLS `FORCE` in the migration that creates them — `CR-070` §3). `type_id` FK NULL and **`template_no`** (`ST-{0000}`, allocated on publish in D) on `work_order_templates` — the templates table's own migration. **Before writing fifteen handlers, check whether `BR-SHL-035`'s generic `kind: "list"` reference-data routes can serve the four cards** (`07-endpoints.md` §2 says so; the count then falls from 21); otherwise `GET · POST · PATCH` per lookup, `GET /work/parts/{id}`. `due_at` default = raise + SLA hours is G's (`BR-WRK-018` second half). `stock_position()` raises `NotImplementedError("OQ-WRK-1490")` and nothing calls it; `dispatch_batch` has **no caller** and a test says so | 007 · 008 · 009 · 010 · 012 · `BR-WRK-017` · `018` · `019` · `021` · hard rules 1 · 2 | A3 | `WM-04` · `05` · `06` · `07` · `42` | L |
| **C2** | 2b | `features/tenancy/referenceDataConfig.ts:578–605` — the four cards **lose `arrivesWithKey`** and gain handlers; `settings.reference.arrivesWith.work` **deleted from all eleven catalogues in this commit**; the group gains *Work order types* and *Parts* cards (`Work-018`); `Work-019` unchanged — four series already render, `ST-` now has a column to write into. **`features/work/PartsPage.tsx`** (`Work-025`, template W1 with the **`SegmentedControl`** — the second of the inventory's three new components — *Stock register* | *Issue log*, the issue log arriving in N): PART # · DESCRIPTION · CATEGORY · UNIT · UNIT COST (`MoneyCell` 2 dp) · STATUS (active) — **no ON HAND, no REORDER AT, no LOCATION, no Reorder box, no In-cover pill** (the card over the drawing: `DEF-WRK-3550`); *Add part* as a sub-screen; CR-045 toolbar. `WorkTabs` gains *Parts*. `screenIds.ts` + `g29` rows (`WRK-10`) | 007 · 008 · 009 · 010 · 012 · `BR-WRK-019` · `BR-SHL-035` · B14 rules 21 · 31 · 32 · g15 | C1 · A5 | `Work-018` · `Work-019` · `Work-025` (`wireframes/Work-025.png`, **asserted for what it must NOT show**) | L |
| **C3** | 2c | `US-WRK-007` TC-1..6 · `008` TC-1..6 · `009` TC-1..5 · `010` TC-1..7 (**TC-5 asserts by name that `GET /work/parts` carries no `on_hand`, `reorder_at` or `location` key**; TC-6 the stub raises naming the question) · `012` TC-1..6 (TC-4 no caller allocates from `dispatch_batch`); RLS zero-rows on all six tables on PG. Fixture: `MTR-E1P` `96.0000` · `SEAL-01` `0.2200` · `MTR-W58` `92.4000` (the card's figure, `03-field-map.md` D-1) · `GSKT-STD`; skills *Water I · Water II · Meter I · Reads · Backflow · Electric I · Excavation*; kits *Standard electrical · Confined space*; the type catalogue of the drawings (*Meter exchange · Leak investigation · Move-in activation · Read verification · Disconnect — non-payment · Reconnect after payment · Backflow inspection · Main repair*) | 007 · 008 · 009 · 010 · 012 | C1 · C2 | — | M |
| **C4** | review | **Review-ledger row for `work/0002_rls_force`** 🔒 in plain English with a figure: *six new lists — job types, priorities, skills, safety kits, parts categories, parts — each row belongs to one utility; with no utility set, all six return zero rows, proved on PostgreSQL; Brazos Bend's eight job types are invisible to Lone Star Ridge*. File flagged `HUMAN-REVIEW-PENDING` | 009 · CLAUDE.md 🔒 · HUMAN-GUIDE §6 | C1 | — | S |
| **C5** | 2d | **`cr070-c-settings-tell-the-truth.mjs`**: Settings → Configure → Reference data → the Work group shows six cards and **no card reads *arrives with Work*** (the sentence absent from the DOM) · add the skill *Backflow* → it appears · *Urgent* shows *4 h* · Numbering shows four Work series, `DSP-260903-01` among them · Work → Parts: `MTR-E1P` at `$96.00`, the table has **no column headed ON HAND, REORDER AT or LOCATION and no Reorder box** · the segmented control has two segments · Lone Star Ridge sees none of Brazos Bend's rows · screenshots beside `wireframes/Work-025.png` with the divergence noted | 007 · 009 · 010 · 012 · `BR-WRK-019` · `021` · B14 31 · 32 · law 6 | C2 · C3 | — | S |
| **C6** | doc / version | CHANGELOG · lockstep · TSV · decision-log row (the generic-routes decision from C1; the sample copy chosen) | — | C5 | — | S |
| **C7** | blocked | **After `OQ-WRK-1490` is ruled:** the stock columns, the reorder box and deduct-on-issue on `Work-025` — or the ruling that there are none, and the drawing stamped. Nothing before | 010 · `BR-WRK-019` | a ruling | `DEF-WRK-3550` | — |

**Demo script C (Alex Reed):** 1 Settings → Configure → Reference data → 2 the Work group: six cards, the
grey sentence gone → 3 open *Skills*, add *Backflow* → 4 open *Priorities* — *Urgent · 4 h · red* → 5 Numbering →
the Work group: Connection · Work order · Service template · Dispatch batch → 6 Work → *Parts*: four parts with
unit costs at two decimals and **no count of anything** → 7 Lone Star Ridge: six cards, empty.
**Exit test (asserts a rule):** `BR-WRK-019` — the parts payload has no stock key, asserted by name; `BR-WRK-021` —
nothing allocates from `dispatch_batch`; hard rule 2 — `92.4000` stored, `$92.40` shown.

**Wave C — AS BUILT (2026-09-04, the CR-070 wave C build lane; product `2.139.0`). Stamped
2026-09-05 by the wave D lane, one wave late — the same miss `DEF-WRK-3933` records, and the
reason r11 step 4 now says a wave stamps its own rows in the commit that lands it.** Verified
from the code at `ce221fc9`, not from the task table:

* **`C1` — six tables and two migrations.** `apps/work/models.py` holds `WorkOrderType` ·
  `WorkPriority` · `WorkSkill` · `WorkSafetyKit` · `PartCategory` · `Part`, created by
  `work/0001_initial` with `work/0002_rls_force` 🔒 immediately after (ENABLE + FORCE, the
  `NULLIF` form, all six). `metering/0045` added `work_order_templates.template_no` and
  `type_id` and `work_orders.type_id`.
* **`C1`'s own check was run and the answer was YES.** The task said *"before writing fifteen
  handlers, check whether `BR-SHL-035`'s generic `kind: "list"` routes can serve the four
  cards"*. They can: `apps/work/lookups.py` registers five handlers into
  `WORK_LOOKUP_HANDLERS` and the reference-data framework serves them, so the endpoint count
  fell as `07-endpoints.md` §2 predicted. `parts` is the one that could not be — a register
  with five columns against a card that renders three — and it has its own four routes.
* **`C2`/`C3` — the Settings cards and the parts register.** `SettingsReferenceData` serves
  the four; `features/work/PartsPage.tsx` and `AddPartModal.tsx` are `Work-025`.
* **`stock_position()` raises `NotImplementedError` naming its question and nothing calls it**;
  `dispatch_batch` has no caller. Both as the task asked.
* **`C7` is `blocked` and stays so** — the stock half of `US-WRK-010`.

⚠ **ONE THING THE PLAN SAID THAT THE CODE DOES DIFFERENTLY, AND THE CODE WINS.** `C1` reads
*"`type_id` FK NULL … on `work_order_templates`"* as though the templates table's own
migration carried it. It did not: `metering/0045` did, because `work_order_templates` is
metering's table and has not moved (§4 below). Wave D takes the same road for the same reason.

---

### Wave O — one destination: the build on the premises and the account · phase 0 (the correction)

⚠ **AMENDED 2026-09-04 BY THE WAVE-O BUILD LANE, THREE FIGURES (`DEF-WRK-3748`,
`DEF-WRK-3749`, `DEF-WRK-3750`).** This wave was written saying *seven acts* in
four places; `CR-070 §W.6` says **eight**, `ConnectionAct` has had eight members
since wave B, and `cr070-b-fourteen-doors-and-the-queue.mjs` asserts
`acts.length === 8`. Consistency is what made it dangerous — a lane cross-reading
this file four times gets the same wrong number four times — and the eighth act
is *Raise order*, so losing it would have left a build with no way to add a job
from the screen a person is standing on. The tab list in `O2` and the test-file
count in `O4` are corrected in place for the same reason. **The counts are now
pinned by tests rather than by prose**: `buildViews.test.tsx` TC-1 asserts eight
`data-act` buttons and `PremisesPage.test.tsx`'s `DEF-578` case asserts both
forms of `premisesTabs`.

⚠ **NEW, 2026-09-04, and it runs FIRST of everything that remains.** `CR-070 §W.11`: *"`NCT-02` at
`/connections/<uuid>` stops being a place a person navigates to. Its six tabs — Overview · Units · Work orders ·
Assets · Charges · History — are reached from the account, and from the premises where a build spans units."*
Every wave after this one points somewhere, so this is the wave that decides where.

**Goal a clerk can see:** a person looking for how the build at *1408 Elm St* is going opens the **premises** —
or the **account**, if the build has one — and finds its progress, its units, its jobs, its meters, its charges
and its trail there. The **eight** acts wave B mounted are on those screens. `/connections/<uuid>` still works if
somebody has it bookmarked, and lands them in the same place.
**Stories:** `US-WRK-002` (re-hosted — the acts, not the screen) · `US-WRK-003` (the queue's link) · `US-WRK-004`
· `US-WRK-006` (the fixture grows)
**Depends on:** B (the fourteen doors and the queue, landed as `2.136.0`). **Blocked by:** nothing. The premises
is the host that always exists because `owner_account_id` is OPTIONAL (judgment 1). ⚠ **This line read *"must NOT
wait on `OQ-373`"* until 2026-09-12 (`DEF-MET-5081`); `OQ-373` closed on 2026-08-25 and there was nothing left to
wait on.**
**Version:** the next free `<change>`. **Size:** two people, one and a half weeks.

| Task | r11 | What it touches — verified at the pinned tip | Stories · rules | Depends on | Design xref | Size |
|---|---|---|---|---|---|---|
| **O1** | 2a | **Two scoped readers and no new filter** (judgment 3): `GET /premises/{id}/work-orders` and `GET /accounts/{id}/work-orders` in `apps/work/api.py` over one selector in `apps/work/selectors.py` — the orders standing on that premises, on any unit of it, on any asset at it, or on any account of it, newest first, with the same row shape `awaiting_approval()` already serves. **`BR-WRK-026`'s six filters and its `400` on a seventh are untouched** — these are paths, not filters. Plus `GET /premises/{id}/build` and `GET /accounts/{id}/build` — the connection row's own facts (state, mode, target activation, quote total, `connection_no`) read through the metering seam, `null` where there is no build, and **the sentence says so rather than rendering an empty panel** | 002 · 004 · `BR-WRK-006` · `BR-WRK-026` · hard rule 1 | — | `CR-070 §W.11` | M |
| **O2** | 2b | **`features/metering/PremisesDetailPage.tsx` gains its build**: a fifth and sixth tab — **Build** (Overview: state · mode · target activation · quote total · the units manifest; the **eight** acts from `B1`'s routes — *Hold… · Release… · Cancel… · Waiting on… · Add service · Mark outstanding work · Close · Raise order* — each **disabled with its reason** when the state forbids it, `Cancel…` on the danger tier) and **Work orders** (the `Work-002` orders table verbatim — ⚠ **`wireframes/Work-002.png` DOES NOT EXIST AND NEVER DID (`DEF-WRK-3934`, amended 2026-09-05).** The wireframes folder starts at `Work-007`: its README records that `Work-001`–`006` and `Work-018`–`020` are screens the product ALREADY HAS, drawn in the parent blueprint's §12/§12.1, and that half of the document is over the 10 MB download cap and cannot be rendered. **So there is no drawing to open, and a row that sends a builder to one costs them the search before they can start.** The specification is the COLUMN LIST written out in this row, plus the live screen itself (hard-won law 6 — diff the running app), and `05-prototype/r10-2026-08-16/` as the standing reference default. The drawing is owed if those blueprint sections ever arrive under the cap. The columns are — ORDER · TYPE · SERVICE · UNIT · MODE · STATE · TECHNICIAN — reading `O1`). ⚠ **AMENDED 2026-09-04 (`DEF-WRK-3749`): the FIVE tabs it has — overview · units · common-areas · assets · audit — do not move, and Build and Work orders make SEVEN with Audit kept last.** The four names this row used to list (units · occupied · meters · master-account) are the `KPIStrip` TILE ids twenty lines further down the same file, not tabs; `DEF-578` removed a sixth tab on 2026-08-22 with the PO's own screenshots and there has never been one called *occupied*. **A premises with no build renders no Build tab at all** — a tab pointing at nothing is dead UI (law 2, `G13`) | 002 · 004 · `BR-SHL-025` · `BR-WRK-006` · B14 rules 6 · 20 · 21 · 31 · 32 · 33 · g13 · g15 | O1 | `Work-002` (**no drawing — see the row**) · `CR-070 §W.11` | L |
| **O3** | 2b | **`features/customers/AccountDetailPage.tsx` gains a twelfth tab** — `ACCOUNT_TAB_IDS` (line 223) goes from eleven to twelve with **`work`**, placed after `meters` because a job is about the thing at the address rather than about the money. It lists the orders standing on this account **and** on its unit's premises, each row saying which. **Charges and History are already there** — the Charges tab of `NCT-02` is this account's `bills`/`adjustments`, and its History is the `audit` tab; nothing new is built for either, and `08-screen-layouts.md` is stamped to say so. `TAB_LABEL_FALLBACK` gains no entry: the key lands in all eleven catalogues in this commit (`G15`) | 002 · 004 · B14 rules 20 · 21 · 31 · 32 · g13 · g15 | O1 | `Work-002` · `CR-070 §W.11` | M |
| **O4** | 2b | **The destination closes, and nothing breaks.** `App.tsx:646` — `/connections/:connectionId` becomes a **redirect** to the build's home (judgment 5): the owner account where `owner_account_id` is set, the premises otherwise, resolved by `O1`'s reader. `screenIds.ts` retires the `NCT-02`/`S88` badge for that path and the `g29` row goes with it in the same commit. **Every link is repointed, not deleted** — `NewConnectsTab.tsx`, `AccountsListPage.tsx`, `NewConnectWizard.tsx`'s completion and `newConnectShared.tsx`. **`features/customers/ConnectionDetailPage.tsx` is DELETED** and its **two** test files with it — `ConnectionDetailPage.test.tsx` and `ConnectionDetailPage.dom.test.tsx`, both under `features/customers/` (⚠ **AMENDED 2026-09-04, `DEF-WRK-3750`: this row said THREE.** The third file with that basename is `features/integrations/ConnectionDetailPage.test.tsx`, which covers `INT-02` and is a different screen — the very collision this row warns about two sentences later); its action row and its tab bodies are what `O2` and `O3` are made of. ⚠ **`features/integrations/ConnectionDetailPage.tsx` IS A DIFFERENT SCREEN WITH THE SAME FILE NAME** (`App.tsx:155` aliases it `IntegrationDetailPage`) and is NOT touched — grep by path, never by basename | 002 · 004 · law 2 · B14 rule 31 | O2 · O3 | `CR-070 §W.10` · `§W.11` | M |
| **O5** | 2b | **The queue and the dispatcher stop pointing at a retired screen.** `Work-009`'s `CONNECTION` column keeps its TEXT (`CON-26-0117` is a number a clerk quotes, not a database id) and its **link moves to the build's home**; the `PREMISE` column beside it is unchanged. The same one-line change is written into wave `G`'s `G3` so the dispatcher inherits it rather than repeating it | 003 · B14 rule 31 · `BR-WRK-007` | O4 | `Work-009` | S |
| **O6** | 2c | `US-WRK-002` TC-1..7 **re-pointed, not rewritten** — each of the **eight** acts reachable from the premises and from the account; a forbidden state refused server-side with the button disabled; an audit row per act · `US-WRK-004` TC-1..5 (the twelfth account tab; the premises Build tab absent where there is no build) · **TC: `/connections/<uuid>` answers a redirect and never a 404** · **TC: no route, link or `href` in `07-frontend/src` resolves to `/connections/` followed by an id** — a grep case, so a later lane cannot quietly put the destination back · Lone Star Ridge sees none of Brazos Bend's builds. Fixture: `CON-26-0117` (26 units, **0 owner accounts** — judgment 1's own case) and a single-unit build that HAS one, so both hosts are demonstrated | 002 · 003 · 004 · 006 | O1–O5 | — | M |
| **O7** | 2d | **`10-scripts/render-checks/cr070-o-one-destination.mjs`** — demo script O below. It **re-runs `cr070-b`'s eight acts through the new door** rather than replacing that script's assertions: hold with a reason, release, the refusal sentence at five or six words, the audit row. Plus: the premises Build tab matches the column list in `O2` region by region (there is no `Work-002.png` — `DEF-WRK-3934`); the account has twelve tabs; a bookmarked `/connections/<uuid>` lands on the premises; the DOM contains no anchor whose `href` starts `/connections/` and ends in an id; screenshots beside `Work-002.png` | 002 · 003 · 004 · law 6 · `B14` rule 36 | O6 | `Work-002` | S |
| **O8** | doc / version | CHANGELOG · lockstep · TSV · **`08-screen-layouts.md` stamped**: `Work-002`'s layout now lands on two hosts and its Charges/History regions are the account's existing tabs · `01-overview.md` §6's screen list stamped · decision-log row (the nine judgments) · **`12-governance/09-human-review-ledger.md` row**: what the PO is shown, in plain English with a figure — *the build at 1408 Elm St, 26 units, is now reached from the premises and from the account; the old `/connections/…` link still works and lands in the same place; nothing was migrated and no data moved*. ⚠ **Phase 0 is NOT re-declared** (judgment 9) — the entry says which door moved | — | O7 | `CR-070 §W` | S |

**Demo script O (a clerk, then M. Torres):** 1 Premises → *1408 Elm St* → **Build**: *In progress · Our crew ·
target 14 Apr · $14,435.00*, 26 units → 2 *Hold…* with a reason → the state reads *On hold* and *Waiting on* shows
it → 3 *Release…* → back to *In progress* → 4 the **Work orders** tab: `5 of 8` done, the MODE column per order →
5 Accounts → a single-unit build's account → the **twelfth tab, Work**: its two jobs, each saying whether it
stands on the account or on the premises → 6 paste an old `/connections/<uuid>` link → it lands on the premises,
same screen as step 1 → 7 Work → *Awaiting approval* → the `CON-26-0117` cell goes to the premises, not to a
connection screen.
**Exit test (asserts a rule):** `BR-SHL-025` — a hold on a cancelled build is refused by the SERVER with a
five-or-six-word sentence while the button is disabled with its reason, on whichever of the two hosts it is
pressed; **B14 rule 31** — no database id is the visible value of anything on either host; and the grep case:
**no link in the front end navigates to `/connections/<id>`.**

**Wave O — AS BUILT (2026-09-04, the CR-070 wave O build lane; product `2.141.0`). Stamped
2026-09-05 by the wave D lane, one wave late — see wave C's stamp for why that is now a rule.**
Verified from the code at `ce221fc9`:

* **`O1` — five reads, no new filter.** `apps/work/api.py` serves `GET /premises/{id}/work-orders`
  · `/accounts/{id}/work-orders` · `/premises/{id}/build` · `/accounts/{id}/build` ·
  `/work/builds/{id}/home`, over `apps/work/selectors.py` and the metering seam.
  `BR-WRK-026`'s six filters are untouched — these are paths.
* **`O2` — the premises has SEVEN tabs**, `premisesTabs(t, hasBuild)` in
  `features/metering/PremisesDetailPage.tsx:189`, and a premises with no build renders no Build
  tab at all. `PremisesPage.test.tsx` asserts both forms.
* **`O3` — the account has TWELVE**, `ACCOUNT_TAB_IDS` at `features/customers/AccountDetailPage.tsx:230`,
  with `work` after `meters` and deliberately absent from `TAB_LABEL_FALLBACK`.
* **`O4` — `features/customers/ConnectionDetailPage.tsx` IS DELETED** with its two test files;
  `features/work/BuildRedirect.tsx` is the redirect and `features/integrations/ConnectionDetailPage.tsx`
  — the different screen with the same basename — is untouched.
* **`O5`–`O8`** — the queue's `CONNECTION` cell links through `buildHomePath`,
  `10-scripts/render-checks/cr070-o-one-destination.mjs` exists, and the wave shipped as
  `2.141.0`.
* A later commit (`6e7baf9d`) added the account half of the build reader, which had no caller.

---

### Wave D — the bundle, and the one write · phase 1

**Goal:** a template is a bundle of seven collections stored as rows; the list shows what each contains; a
template can be duplicated, deactivated, and refused deletion while any order references it; two Water templates
coexist; v2 leaves v1's orders untouched.
**Stories:** US-WRK-013 · US-WRK-014 · US-WRK-015 · US-WRK-018
**Depends on:** C (types, skills, kits, parts, `template_no`). **Blocked by:** nothing — **but the lane reads the
blueprint's §16 before `work/000N`** and decides `03-field-map.md` §4 (where the six existing models live),
recording the choice in the decision log.
**Version:** next free `<change>`. **Size:** two people, two weeks.

| Task | r11 | What it touches | Stories · rules | Depends on | Design xref | Size |
|---|---|---|---|---|---|---|
| **D1** | 2a | **Header columns and the relaxed key** (`03-field-map.md` §3 rows 21–27): `skill_id` FK NULL **replacing** text `skill` (NULL on all 24 rows, so the data migration is trivial) · `crew_size` · `safety_kit_id` · `active` · `version` · `no_gate_reason`; **drop `uq_work_order_templates_seq`** (`connections.py:856–863`), **add `uq(tenant, name, version)`**. **Seven child tables as rows** — `wot_details` · `wot_safety` · `wot_tasks` · `wot_materials` · `wot_readings` (six columns incl. `unit_of_measure` and `posts_as_meter_read`, `BR-WRK-015`) · `wot_help` · `wot_asset_types` (→ `assets`, reviewed set) — plus `work_order_template_versions`; **`work/000N_rls_force`** 🔒 | 013 · 014 · 018 · `BR-WRK-009` · `010` · `012` · `015` · hard rules 1 · 3 | C1 | `WM-08` · `WM-09` · `WM-40` | L |
| **D2** | 2a | **`apps/work/templates_svc.py` — the service the seeder says is OWED** (`sample_data.py:2547`): `create_draft` · `update_header` · `replace_collection(template, name, rows)` (one route, seven collections — `PUT /work/templates/{id}/{collection}`) · **`publish`** — the ONE write: allocates `ST-{0000}` from the tenant's series (`BR-TEN-035`), sets `version`, writes a versions row, refused twice-in-quick-succession into one version · `duplicate` · `deactivate` · `delete` **refused while any version is referenced** (PROTECT + a sentence). Reads: `GET /work/templates` (the list with the Contents count), `/{id}`, `/{id}/versions`, `/{id}/usage`, `GET /work/template-packs` (the three platform packs as constants — *Meter exchange · New connection · Inspection*). Audit per write | 015 · 018 · `BR-WRK-011` · `012` · `BR-MET-109` · hard rule 7 | D1 | `WM-10` · `WS-14` | L |
| **D3** | 2b | **`features/work/TemplatesPage.tsx`** (`Work-013`, template W1 per the layouts entry: TEMPLATE · SERVICE · JOB TYPE · CONTENTS *2 tasks · 0 parts · 1 reading* · GATE with the red flag · SKILL · EST. · STATUS · pencil; footer *6 templates · 4 published · 1 draft · 1 inactive  Seeded starters are marked and can be edited or deleted.*; CR-045 toolbar with **Filter by service**) **replaces `WorkOrderTemplatesPage.tsx` at `/work/templates`** — the blank page and its four sentences are deleted with their test; the `g29` row is re-pointed by the lane to r10's `WRK-04` and `WRK-19` retired in that file. **`features/work/TemplateDetailPage.tsx`** (`Work-022`, W5): kicker · title · meta · `StatusPill` · **Duplicate · Deactivate · Delete (disabled with the sentence)** — *Edit template* arrives with E's builder and is not rendered before it exists (law 2) · Tabs Overview · Usage · Versions · Audit · the Versions table with `CountFooter` *35 orders raised across 2 versions  The 4 v1 orders still read v1 — nothing was rewritten*. `screenIds.ts` rows (`WRK-04`, `WRK-15`) | 013 · 015 · 018 · `BR-WRK-010` · `012` · B14 rules 6 · 15 · 20 · 21 · 32 · g13 · g15 | D2 · A5 | `Work-013` (`wireframes/Work-013.png`) · `Work-022` (`wireframes/Work-022.png`) · `Work-005` replaced | L |
| **D4** | 2c | `US-WRK-013` TC-1..6 (two Water templates at once; the old key gone — on PG) · `014` TC-1..7 (rows not a blob; the unit is a column) · `015` TC-1..7 (publish twice quickly → one version; delete refused while referenced) · `018` TC-1..7 (v2 publish leaves a v1 order's copies untouched — the copy tables arrive in H, so TC-3 lands in H's suite and is named here). Fixture: `ST-0002 · Meter exchange — residential` v1 (6 tasks, 4 orders) then v2 (*Added Apply tamper seal*, 31 orders) — `J67`'s fixture; the drawing's six-row list | 013 · 014 · 015 · 018 | D1–D3 | — | M |
| **D5** | review | Review-ledger row for the RLS migration 🔒: *eight new tables hold a template's contents — every safety row, task, material, reading and help line belongs to one utility; Brazos Bend's 24 starters and their rows are zero rows to Lone Star Ridge, proved on PostgreSQL* | 014 · CLAUDE.md 🔒 | D1 | — | S |
| **D6** | 2d | **`cr070-d-the-bundle-and-the-write.mjs`**: Work → Templates reads *6 templates · 4 published · 1 draft · 1 inactive* and two rows say *Water* · open `ST-0002` → Versions: *v2 · 31 · Current* over *v1 · 4 · Superseded* and the footer sentence · *Delete* is disabled and the note says why · *Duplicate* → a seventh row, *Draft* · *Deactivate* → *Inactive* · from the API: `PUT …/tasks` on the draft then `publish` → `ST-0003` v1; `publish` again at once → still one version · no string matches `BR-`/`WM-` · screenshots beside `wireframes/Work-013.png` and `Work-022.png` | 013 · 015 · 018 · `BR-WRK-010` · `011` · `012` · B14 31 · 32 | D3 · D4 | — | S |
| **D7** | doc / version | CHANGELOG · lockstep · TSV · decision-log rows: **the §16 reading and the `03-field-map.md` §4 placement choice** (a, b or c — stated with its reason and stamped into the field map), and the 23-vs-25 table count settled | — | D6 | — | S |

**Demo script D (M. Torres):** 1 Work → *Templates* → six rows, the footer counts them → 2 two *Water* rows sit
together — yesterday's key forbade it → 3 open *Meter exchange — residential* → *Versions*: v2 current, v1
superseded, *the 4 v1 orders still read v1* → 4 *Delete* is greyed and the note says it has produced orders →
5 *Duplicate* → a draft appears in the list → 6 *Deactivate* the draft → *Inactive* → 7 in the terminal, publish
the same draft twice within a second → one version.
**Exit test (asserts a rule):** `BR-WRK-010` — `(tenant, name, version)` is the key on PostgreSQL and
`(service, sequence)` is gone; `BR-WRK-011` — seven edits persist as a draft and nothing reaches an order until
Publish; `BR-WRK-012` — Delete refused while referenced, Deactivate stops new orders and keeps the old readable.

**Wave D — AS BUILT (2026-09-05, the CR-070 wave D build lane; product `2.166.0`). `D6` was
owed and is now RUN — see the amended stamp below; the seeder's re-point landed as wave `E`'s
`E4`.**

* **`D1`** — `work/0003_cr070_d_template_bundle` creates the seven `wot_*` tables and
  `work_order_template_versions`; `work/0004_rls_force_bundle` 🔒 puts ENABLE + FORCE on all
  eight. `metering/0048` adds `skill_id` (replacing the free-text `skill`), `safety_kit_id`,
  `crew_size`, `active`, `version`, `no_gate_reason` and `work_orders.template_version`, drops
  `uq_work_order_templates_seq` and adds the new key.
* **`D2`** — `apps/work/templates_svc.py` (create · update · replace_collection · publish ·
  duplicate · deactivate · reactivate · delete) over metering's own
  `create_work_order_template` family, reached by name through the seam. Nine routes in
  `apps/work/api.py`, including the ONE collection route.
* **`D3`** — `features/work/TemplatesPage.tsx` (`Work-013`) replaces
  `WorkOrderTemplatesPage.tsx`, which is DELETED with its test; `TemplateDetailPage.tsx`
  (`Work-022`) is new. `WRK-19` retired, `WRK-04` and `WRK-15` in its place.
* **`D4`** — `tests/test_us_wrk_013_018_templates.py`, 29 cases; `test_us_wrk_rls_pg.py` now
  reads `pg_class` for all fourteen Work tables.
* **`D5`** — the review-ledger row is written.
* **`D7`** — this stamp, the field-map §4 decision, the TSV, the CHANGELOG and the version.

⚠ **THE REPLACEMENT KEY IS `(tenant, service, name, version)` AND NOT `(tenant, name,
version)`.** `BR-WRK-010` is PROPOSED and names the three-column form; `US-WRK-013` TC-2
repeats it. **It cannot be created on any database that has run the seeder**: the 24 CONFIRMED
starters (`BR-WRK-013`) seed **`Meter set` four times** (electric · water · gas · thermal
heat), **`Inspection` three times** (gas · solar · thermal heat) and **`Service connection`
twice** (thermal heat · fire). The four-column key is what they admit; the rule's stated
purpose — *"a utility holds New connection and Leak investigation for Water at once"* — is met
exactly, and TC-2's refusal still refuses. Decision log, 2026-09-05.

⚠ **`D6` IS DONE — AMENDED 2026-09-05 BY THE WORK WALKTHROUGH LANE.** This paragraph read
*"`D6` IS NOT DONE — `cr070-d-the-bundle-and-the-write.mjs` DOES NOT EXIST"* from the day the
wave shipped, and it was true for that day. The file exists now, with
`cr070-d-fixture.py` beside it, and it has been **run in Chromium against the built bundle:
86 checks pass and ONE fails.**

**The one that fails is a real defect and not a flaky check, which is why the walkthrough is
left RED rather than softened.** `BR-WRK-011`'s *publish twice within a second → one version*
holds when the two presses are SEQUENTIAL and does not hold when they are SIMULTANEOUS:
`publish()` decides whether there is anything to version by READING the newest version row,
and with none committed yet two first-publishes both pass the test and the template lands on
**v2 with two identical *First publish* rows**. The builder's own commit button is
single-flighted by `WizardFrame`, so a person cannot do it through the screen — the DOOR is
what is open, which is the half `BR-SHL-025` says a disabled control can never cover.
`US-WRK-015` TC-4 asserts the sequential case in one process on SQLite and cannot see it. The
row is written up in `scratchpad/lane-WALK-defects.md` with both measurements.

⚠ **AND THE FIXTURE IS NOT OPTIONAL, FOR A REASON WORTH READING BEFORE THE NEXT WAVE.** On a
freshly seeded utility every template has ONE version, ZERO orders and an ENABLED Delete —
so the three things `Work-022` exists to show (a superseded version under a current one, the
count that proves `BR-WRK-008`, and Delete refused WITH ITS NUMBER) cannot be seen at all.
`cr070-d-fixture.py` writes *Meter exchange — residential* through the product's own service,
raises 4 orders while it is v1 and 31 more after v2, and is idempotent.

⚠ **THE 24 SEEDED STARTERS NOW READ *Draft*, AND THAT IS HONEST RATHER THAN A REGRESSION.**
`version` defaults to 0 and 0 is a draft (`BR-WRK-011`: publish is the one write). They carry
no bundle, no `template_no`, and nothing in this product has ever raised an order from one.
**Wave `E`'s `E4` (`US-WRK-019`) is what republishes them through the service** — and until it
runs, the seeder still writes `WorkOrderTemplate.objects.get_or_create` directly, so
`US-WRK-015` TC-4's grep is red BY PLAN and is named in wave D's test file as landing in E.

---

### Wave E — eight steps, and step six · phase 1 (the phase-1 LAUNCH)

**Goal:** the builder the PO designed and nobody built; the 24 seeded starters become editable bundles; New
Connect step 6 proposes orders from the utility's own published templates.
**Stories:** US-WRK-016 · US-WRK-017 · US-WRK-019
**Depends on:** D (the write service, the child tables). **Blocked by:** nothing.
**Version:** next free `<change>`. **Size:** two people, two weeks.

| Task | r11 | What it touches | Stories · rules | Depends on | Design xref | Size |
|---|---|---|---|---|---|---|
| **E1** | 2b | **`features/work/TemplateBuilder.tsx`** on the existing `WizardFrame` (`components/WizardFrame.tsx:673`, `steps` · `commitVariant`) — eight steps per `08-screen-layouts.md` 13.1: **1 Details** (`Work-014`: four `PackCard`s incl. *Start empty*; the form; *WHAT THE TECHNICIAN SEES ON THE JOB*; **rule 32 strips `WM-04` from the help line**) · 2 Safety · **3 Tasks** (`Work-015`: **`EditableTable`** — the first of the inventory's three, drag handle ≡ · # · TASK · MINUTES · PHOTO · MUST DO · ✕ · inline add row; the order is `seq`) · 4 Materials · **5 Readings** (`Work-016`: PROMPT · UNIT · MIN · MAX · PHOTO · REQUIRED · BECOMES A METER READ) · 6 Help & support · 7 Signature · **8 Review** (`Work-017`: the seven-section table; the `ConsequenceBox` *Publishing affects **new** work orders only…*; **Publish template** primary · **Save as draft** · **Delete** danger disabled with the note). *Edit template* on `Work-022` opens it at step 1. Every file on the migrated list | 016 · `BR-WRK-011` · `015` · B14 rules 5 · 6 · 11 · 21 · 31 · 32 · g13 · g15 | D2 · D3 | `Work-014`–`017` (`wireframes/Work-014.png` … `Work-017.png`) · `WM-11` | L |
| **E2** | 2a | `GET /connections/proposed-work-orders?services=` — the enabled services' **published** templates, with the gate template flagged; the New Connect wizard's step 6 reads it (`customers` reads Work through the API — no ORM cross); nothing is written until step 9 (`BR-MET-112`) | 017 · `BR-WRK-016` · `BR-MET-109` · `112` | D2 | `WM-12` | S |
| **E3** | 2b | `features/customers/NewConnectWizard.tsx:1273` — *"Those templates are not built yet, so no orders are proposed here."* **replaced** by the proposal list (one row per template, the gate flagged, *remove* per row, the count in the step's footer); the key retired from all eleven catalogues in the same commit | 017 · `BR-WRK-016` · B14 rule 32 · g15 | E2 | `Work-004` | M |
| **E4** | 2a | **The 24 starters become bundles** (`US-WRK-019`): `_seed_work_order_template_starters` (`sample_data.py:2533`) writes through `templates_svc.publish` — a `wot_details` row each, version 1, a `template_no`, `is_sample=True`; **gas stays gated on the light-up** (row *Pressure test and light-up · True* at 1913); services whose starters carry no gate store `no_gate_reason`; the seeder's OWED sentence at 2547 and the footnote at 4129 retired — the service exists | 019 · `BR-WRK-013` · `BR-MET-109` | D2 | blueprint §11 | M |
| **E5** | gate | **Every seeded starter row has a reader** (`CR-070` §12 gate 3, `BR-WRK-014`; G74 is the model-level precedent, this is row-level): for every row the seeder writes into `work_order_templates`, a list endpoint serves it and a screen renders it — RED first by seeding a 25th row and hiding it from `GET /work/templates` (`US-WRK-019` TC-6). Registered in `GATES` the same commit; next free number at push | 019 · `BR-WRK-014` · law 7 | E4 · D2 | §12 gate 3 | S |
| **E6** | 2c | `US-WRK-016` TC-1..7 (Save draft persists a draft; Publish is the one write; the pack prefills; Start empty) · `017` TC-1..7 (Electric + Water propose **5**; remove one → 4; nothing written before step 9; Lone Star's templates never proposed) · `019` TC-1..6. **Journey `J60` activated** — the file exists at `d0cf0b00`; its `J60.spec.ts` is written, run green on the build, and the *NOT ACTIVATED* banner removed | 016 · 017 · 019 | E1–E5 | — | M |
| **E7** | 2d | **`cr070-e-eight-steps-and-step-six.mjs`** (`J60`): Settings → add the skill *Backflow* and the type *Backflow test* → Work → Templates → *+ New template* → the *Meter exchange* pack → eight steps, asserting each step's title against `wireframes/Work-014.png` … `Work-017.png` (*What job is this template for?* · *What are the steps?* · *What has to be measured?* · *Review*), the help line carries no `WM-04`, step 3 reorders a row by drag and the seq changes · **Publish** → `Work-022` reads *v1 · Current* · New Connect for Electric + Water → step 6 proposes **5** orders → remove one → 4 → Back out before step 9 → no `work_orders` row · screenshots | 016 · 017 · 019 · `BR-WRK-011` · `013` · `016` · B14 31 · 32 · law 6 | E1–E6 | — | S |
| **E8** | doc / version | CHANGELOG (the **phase-1 entry**) · lockstep · TSV · decision-log row · **phase 1 LAUNCH declared** — *a utility authors its own job templates, and the wizard proposes them*; rollback stated: **hide the section and keep the data** | — | E7 | — | S |

**Demo script E (Alex Reed, then M. Torres):** 1 Settings → Reference data → add *Backflow* and *Backflow test*
→ 2 Work → Templates → *+ New template* → *Meter exchange* pack: seven tasks, three parts, three readings prefilled
→ 3 step 3: drag *Apply tamper seal* above *Restore supply* → the order sticks → 4 step 5: the reading *Opening read on
new meter* · kWh · 0–999 · *Yes — posts on approval* → 5 step 8: the consequence box says publishing affects new
orders only → **Publish** → 6 the detail reads *v1 · Current*, the list counts one more published → 7 Customers →
New Connect for Electric + Water → step 6 proposes five orders, one flagged as the gate → 8 remove one; leave the
wizard — nothing was written.
**Exit test (asserts a rule):** `BR-WRK-011` — Publish is the one write (a draft at step 7 has produced no version);
`BR-WRK-016` — step 6 proposes only PUBLISHED templates of ENABLED services and writes nothing before step 9;
`BR-WRK-013` — the gas starter's gate is the light-up, asserted after the seeder is rewritten. **This is `CR-070`
§11's phase-1 exit test. Phase 1 closes when C, D and E are done: twelve stories.**

**Wave E — AS BUILT (2026-09-05, the CR-070 wave E build lane; product `2.168.0`), with `E7`
NOT RUN and named below.**

* **`E1`** — `features/work/TemplateBuilder.tsx` on the shared `WizardFrame`, eight steps at
  `/{tenant}/work/templates/new` and `…/{id}/edit`, `?step=1..8`, badges `WRK-05.1`…`WRK-05.8`
  (r10's own, from its `sid()`; nothing minted). `templateBuilderModel.ts` holds the state and
  the arithmetic so both can be asserted without mounting anything.
  **Two pieces went into the KIT rather than into `features/work` (B14 rule 36):**
  `components/EditableTable.tsx` (new — the inventory's own first of three) and
  `components/ConsequenceBox.tsx` (a MOVE: it was declared inside
  `features/tenancy/RoutesCyclesWizards.tsx` and read by four call sites while the inventory
  lists it against thirteen Work screens). `WizardFrame` gained an optional
  `secondaryActions` slot, because *Save draft* is not a commit, not an exit and not a park.
* **`E2`** — `GET /connections/proposed-work-orders?services=` in `apps/work/api.py`
  (metering's noun, Work's content, the wave O shape), over
  `selectors.proposed_work_orders` — published, active, `sequence >= 1`, in sequence order,
  every condition IN THE QUERY.
* **`E3`** — `NewConnectWizard.tsx` step 6 lists the proposal, flags the gate, removes per row
  and counts underneath; the *"those templates are not built yet"* sentence and its link are
  DELETED, and the surviving list travels into `CommitPlan.work_orders` as template ids with
  their versions (`BR-WRK-008`).
* **`E4`** — `_seed_work_order_template_starters` writes through `templates_svc`
  (`create_draft` → the `wot_details` row → `publish`), so the starters are PUBLISHED v1
  bundles with `ST-` numbers rather than the inert drafts wave D's stamp recorded. The OWED
  sentence at `sample_data.py` and the module footnote that carried it are retired in the same
  commit. `W6_NO_GATE_REASON` carries the three clerk-facing reasons (B14 rule 32 keeps
  `W6_UNGATED_STARTERS`' rule ids off the screen).
* **`E5`** — `G101 seeded-starters-have-a-reader`, registered in `GATES`, three clauses, RED
  first on all four sabotages **through `run_gates`' own path** and not through `__main__`
  (`DEF-GOV-3733`'s other half).
* **`E6`** — `tests/test_us_wrk_016_019_builder.py` (20 cases),
  `TemplateBuilder.test.tsx` (16), `templateBuilderModel.test.ts` (10). 149 catalogue keys in
  eleven languages in `scratchpad/lane-WE-keys.json`.
* **`E8`** — this stamp, the CHANGELOG, the version, and the rows in
  `scratchpad/lane-WE-decisions.md` and `-defects.md`.

⚠ **`E7` IS NOT DONE — `cr070-e-eight-steps-and-step-six.mjs` IS WRITTEN AND HAS NOT BEEN
RUN.** It needs a seeded database, a running backend and a built front end, and this lane did
not stand one up. The wave is not signed off until it has run green on the built product
(§0's definition of done, part 3), and this stamp says so rather than implying otherwise —
the same posture wave D took for its own `D6`, which is also still owed.

⚠ **THE THREE THINGS `US-WRK-016` ASKS FOR THAT ARE NOT BUILT, EACH FOR A STATED REASON.**
`TC-4`'s *press Publish twice quickly* is asserted on the SERVER (wave D's own case and this
wave's) and single-flighted by the frame; there is no browser case for it until `E7` runs.
**`Delete` is not rendered on step 8**: the drawing draws it disabled with a note, a DRAFT
that has never been published has nothing to delete, and deleting a PUBLISHED template is
`Work-022`'s control, which already exists there (`BR-WRK-012`). And **`J60` is still NOT
ACTIVATED** — its `J60.spec.ts` is not written, so the banner stands; what `E6` covers is
every step of it that a unit test can reach.

⚠ **STEP 7 NEEDED A TABLE AND `03-field-map.md` §3 DOES NOT HAVE ONE.** `work/0005` adds
three columns to `wot_details` — `signature_required`, `refusal_reason_required`,
`door_hanger_on_no_answer` — named after `work_order_signatures`' own columns so the
template's ASK and the phone's ANSWER (`US-WRK-036`, phase 2) read in one vocabulary. Not a
🔒 path: three booleans with defaults, no RLS policy and no money. Decision log, 2026-09-05.

---

### Wave P — the five flows raise their jobs · phase 1

⚠ **NEW, 2026-09-04.** `CR-070 §W.10`, the PO's own words: *"check out new services, new connect move in move
out, transfer - you will see all these requirements are handled their , we had a missing element work order -
now it go and fit in it"*, and §W.12: **before a new module builds a screen, find the flow that already owns that
moment.** Wave `E` already does this for New Connect. This wave does the other four, plus the reconnect visit —
the one place the code carries a named hole for it.

**Goal a clerk can see:** at the moment they are already standing in the flow — routing an approved application,
entering the final reads on a move-out, taking the opening reads on a move-in, doing the reads at a transfer,
recording that a cut customer has paid — the screen offers the job that has to happen, and says what raising it
does. The flow finishes whether or not the job could be raised, and says which.
**Stories:** `US-WRK-039` (moved here from wave M and widened from move-out to the five) · `US-WRK-017` (its
proposal engine, shared) · `US-WRK-006` (the fixture grows)
**Depends on:** `D` (the write service and the child tables) · `E` (`E2`'s proposal reader — this wave reuses it
rather than writing a second one) · `O` (the destination, so a raised job has somewhere to be seen).
**Blocked by:** nothing. **`OQ-WRK-1561`** bounds nothing — it decides a REFUSAL this wave does not build.
**Version:** next free `<change>`. **Size:** two people, two weeks.

| Task | r11 | What it touches | Stories · rules | Depends on | Design xref | Size |
|---|---|---|---|---|---|---|
| **P1** | 2a | **The flow stamp** (judgment 4): wave `G`'s `source` enum gains **four values** — `service_request` · `move_in` · `transfer` · `reconnect` — beside the `move_out`, `assets` and `new_connect` it already declares, and **`source_ref`** (text, nullable) holds the flow record's own number. ⚠ **NO NEW ANCHOR COLUMN AND NO NEW CROSS-MODULE FK**: `ck_work_orders_has_anchor` stays a four-way CHECK, and a flow-raised job stands on the anchor it already has — the account it closes, the premises the request resolved to. **`metering/0049` carries the two columns and the CHECK** — ⚠ the row read `work/000N` until 2026-09-05 and that is not buildable: Django resolves `model_name` inside the migration's own app and `workorder` is declared in `apps/metering/connections.py`, so an `AddField` on it from `apps/work/migrations` raises before it runs. ⚠ **AND THE FOUR VALUES ARE THREE**: r10's eighth source is drawn *Move-in wizard* and this wave's move-in door is the same fact, so `move_in` is ONE token with a catalogue label, not two — fourteen in all. **`G1` is amended in the same commit** so a lane building `G` cannot ship the three-value enum (`DEF-WRK-3726`) | 039 · `BR-WRK-024` · `BR-WRK-055` · hard rule 1 | G1 · A4 | `WM-44` | M |
| **P2** | 2a | **One raise service, five callers** — `apps/work/from_flows.py`: `propose(flow_kind, flow_id)` returns the published templates that fit (reusing `E2`'s reader, never a second copy) and `raise_for(flow_kind, flow_id, template_ids, actor)` creates the orders on the flow's existing anchor and stamps `source` + `source_ref`. **Customers calls it over the API, not the ORM** — exactly as `E2` has customers reading Work — so `A7`'s boundary gate stays green and `apps/customers/**` writes nothing to `work_orders`. **The raise is offered, never automatic, and a failure never fails the flow** (judgment 7): every caller catches, completes, and returns `work_orders_not_raised` with the platform's own sentence. **A request with no resolved premises is refused before the call** (judgment 8) | 039 · `BR-WRK-055` · `BR-WRK-006` · `BR-SHL-025` | P1 · D2 · E2 | `WM-44` | L |
| **P3** | 2a | **The four flow doors, each written in the flow's OWN app** (the pattern `M3` set and `F2` sets for identity): `service_request_service.route()` gains the offer at `APPROVED → IN_FULFILMENT` (`service_request.py:164`) and **B19 §12.3's promise becomes executable** — a request closes on its own when **every** job it raised is accepted, not the first · `services.py:3855` `move_in` and `:3644` `move_out` each take an optional visit election · `transfers.py:1244` `reassign_account` the same · **`disconnects.py:3993` `mark_reconnecting`** books the visit and `VISIT_NOT_SCHEDULED` (`:1214`) **keeps its name and its constant** with its docstring amended to the date the door opened — its sentence *"cross-module writes are forbidden"* was true when written and stopped being true when Work became a module with a seam. `MOVE_IN_UNAVAILABLE` (`services.py:3377`) gains and then loses its visit entry in the same wave | 039 · `BR-WRK-055` · `BR-MET-110` · law 1 | P2 | `WM-44` · `WS-29` | L |
| **P4** | 2b | **Five screens, each at the step the clerk is already on** — one shared `<RaiseFieldWork>` panel from the staff kit, never five copies, and every file on `route-b-migrated.txt` in the commit that creates it (B14 rule 21, `DEF-974`): **`ServiceRequestDetailPage.tsx`** — the *Route* action opens it; the six tabs (line 116) gain no seventh, because the offer belongs to the act and not to a tab · **`MoveOutWizard.tsx` STEP 2** — *Date & final reads*, **not step 4** (judgment 6, `DEF-WRK-3725`), with the consequence restated on step 5's *What happens next* · **`MoveInWizard.tsx` step 3** — *Start date & reads* · **`TransferWizard.tsx` step 2** — *Final reads* · **the reconnect** on the account's disconnect surface. Each carries the *WHAT HAPPENS ON SAVE* table and a `ConsequenceBox` whose sentences are catalogue keys in all eleven (`G15`), each refusal five or six words (`G33`) | 039 · B14 rules 11 · 21 · 31 · 32 · 33 · g13 · g15 | P2 · P3 | `Work-029` (`wireframes/Work-029.png`) · `Work-020` | L |
| **P5** | 2c | `US-WRK-039` TC-1..12, three per flow for four flows: the job is raised with the right anchor and the right `source`; the flow completes when the raise FAILS and says so; nothing in `apps/customers/**` writes `work_orders` (a grep case, and `A7`); Lone Star's flows raise nothing on Brazos Bend. Plus **TC: a service request with no resolved premises is refused with its sentence and no row is written** · **TC: a request with three jobs closes on the third acceptance, not the first** · **TC: `MoveOutWizard` step 4 is not the host** — the control is on step 2 and is present on a move-out that settles cleanly, which is `DEF-WRK-3725`'s regression case, RED first. **Journey `J64` activated** (it is the move-out visit end to end) and **two new journeys written** — the request to fulfilment, and the reconnect. Fixture: `A-10688`'s move-out; an approved request at an address that resolves and one at an address that does not; a cut account that has paid | 039 · 017 · 006 | P1–P4 | — | L |
| **P6** | gate | **`G8n` — no flow raises a job silently and no flow can be blocked by one.** Two clauses, RED first: (a) every caller of `from_flows.raise_for` is inside a `try` whose failure path completes the flow — RED by removing one catch; (b) `apps/customers/**` contains no write to `work_orders` — RED by adding one. Registered in `GATES` in the same commit; number taken at push from the tip | 039 · `BR-WRK-055` · law 7 | P2 · P3 | `CR-070 §12` | S |
| **P7** | 2d | **`cr070-p-the-five-flows.mjs`** — demo script P below, run against the built product. Asserts each panel's copy against `wireframes/Work-029.png` through `08-screen-layouts.md`; that the move-out control renders on a settling move-out (the `DEF-WRK-3725` case); that each raised job appears on the premises or the account host wave `O` built, stamped with its flow's number; and that a raise forced to fail still closes the account, with the sentence on screen | 039 · `BR-WRK-055` · law 6 · B14 rule 36 | P5 · P6 | `Work-029` | S |
| **P8** | doc / version | CHANGELOG · lockstep · TSV · **`04-flows.md` gains the four flow entries** and `02-business-rules.md` records `BR-WRK-055` widened from move-out to five flows, dated, with `M3`'s original text kept and marked superseded · `VISIT_NOT_SCHEDULED`'s docstring dated · decision-log row · **review-ledger row** in plain English with a figure: *when a clerk closes Sarah Miller's move-out at 221 Oak Ave, the screen now offers to send somebody for the final read; the account closes at the same moment whether or not that job could be created, and the job carries the move-out's own number so either one finds the other* | — | P7 | `CR-070 §W` | S |

**Demo script P (a clerk, five moments):** 1 Requests → an approved application → *Route* → the panel offers
*Meter set · Service connection* from the utility's own published templates → raise both → the request reads *In
fulfilment* and names the two jobs → 2 Accounts → Sarah Miller → Move-out → **step 2**: *Date & final reads* →
*Does somebody have to attend?* → *Final read* → step 6 → the account closes and settles; the visit sits *Queued*
in the dispatcher stamped with the move-out's number → 3 a Move-in on a unit that was left off → step 3 offers
the turn-on → 4 a Transfer → step 2 offers the changeover read → 5 a cut account pays → *Reconnect* → the visit
is booked, and the answer no longer says *the visit is not scheduled* → 6 open the premises from step 2's job →
it is on the Build tab wave O made → 7 with the Work API forced to fail, redo step 2: the account still closes,
and the screen says the visit could not be raised.
**Exit test (asserts a rule):** `BR-WRK-055` — every one of the five flows completes when the raise fails, and
says so, and `apps/customers/**` writes no `work_orders` row (the gate and `A7`); **judgment 8** — a request with
no resolved premises is refused before any row is written; **`DEF-WRK-3725`** — the move-out control is on step 2
and is visible on a move-out with no shortfall. **This is where the PO's *"we had a missing element work order -
now it go and fit in it"* becomes something a person can click.**

### Wave F — who can do what · phase 2

**Goal:** the crews screen lists four people, a crew and a contractor as rows in one table; a technician is a
profile beside a login, never a second one; a lapsed certification is shown with its date and **blocks nothing**;
a Field technician can be invited; and the two questions the identity module cannot answer are visible at their
boundary — a clerk's Accept still succeeds and the log says the mapping is unruled.
**Stories:** US-WRK-020 · US-WRK-021 ⚠ (the block) · US-WRK-022 ⚠ · US-WRK-023 ⚠
**Depends on:** C (skills, safety kits). **Runs beside D and E.** **Blocked by:** `OQ-WRK-1492` (who may accept),
`OQ-WRK-1494` (one login, one surface), `OQ-WRK-1493` (block or warn) — each to its boundary.
**Version:** next free `<change>`. **Size:** two people, one and a half weeks.

| Task | r11 | What it touches | Stories · rules | Depends on | Design xref | Size |
|---|---|---|---|---|---|---|
| **F1** | 2a | **Four tables** (`03-field-map.md` §2.3 less `technician_devices`, which is J): `crews` (kind ∈ crew · contractor) · `technicians` (`user_id` → `identity.users`, reviewed set, unique per tenant; `POST` **refuses a user with no `identity.User`** — *"a profile beside an identity, never a second identity"*) · `technician_skills` (proficiency trained · certified) · `technician_certifications` (→ `tenancy.certification_types`, `tenancy/models.py:855`, reviewed set); **`work/000N_rls_force`** 🔒. Routes `07-endpoints.md` §4 #50–#60: crews, technicians, `PUT …/skills` (the wizard's confirm), `PUT …/certifications`, `POST …/unavailable`, **`GET /work/certification-watch`** — expiries within 30 and 60 days and the count of template types that NAME the certification; **nothing refuses**; the one branch that would raises `NotImplementedError("OQ-WRK-1493")`. The skill-match predicate (`BR-WRK-029`) published for G | 020 · 021 · `BR-WRK-028` · `029` · `030` · hard rule 1 | C1 | `WM-13` · `WM-21` · `WS-23` · `WS-24` | L |
| **F2** | 2a | **Identity's companion, written in identity's app because identity owns the write** (`07-endpoints.md` §4's note): `identity/000N` declares **`work_accept`** in the permission catalogue (`identity/models.py:80`, the nine A4 rows) **assigned to no role**; adds the **`field_technician`** role beside `system_admin · billing_clerk · executive` (`models.py:65–70`), holding no staff permission; `users.surface_scope` enum defaulting to *both*. `apps/work/seams/identity_seam.py` — `may(actor, "work_accept")` resolves **exactly as today** (any authenticated staff) and logs once `work_accept_mapping_unruled`; `enforce_surface(actor, "web")` raises naming `OQ-WRK-1494`, is caught into *allow*, logged once. `accept_field_result` (`connections.py:2116`) asks `may(...)` inside its transaction. `core/permissions.py` checks roles (`RoleRequired`, `require_role`) — the permission-based check is the boundary and is NOT built past the stub | 022 · 023 · `BR-WRK-043` · `044` · B2 §2 | A3 | `WM-26` · `WM-31` | M |
| **F3** | 2b | **`features/work/CrewsPage.tsx`** (`Work-023`, W1 per the layouts entry): TECHNICIAN (`StatusPill.amber` *cert expiring* inline on J. Kaur) · ROLE · SKILLS · CERTIFICATIONS · SHIFT · TODAY · UTILISATION · STATUS; footer *6 rows · 4 people, 1 crew, 1 contractor*; the **Certification watch** `ConsequenceBox` with the two dated lines and **without** *She is blocked from 4 template types until renewed* (the card over the drawing — `DEF-WRK-3551`); CR-045 toolbar. **`features/work/TechnicianDetailPage.tsx`** (`Work-024`, W5): Overview · Jobs · Certifications · Audit; *Assign skills* opens the **three-step skills wizard** sub-screen; *Set unavailable*. Settings › Team's role picker (identity's screen) gains *Field technician · Work (mobile only)* — one row, r10's own words (`SMARTBillHub.dc.html:7119`). `WorkTabs` gains *Crews*. `screenIds.ts` + `g29` rows (`WRK-07`, `WRK-08`, `WRK-14`) | 020 · 021 · 023 · `BR-WRK-028` · `030` · B14 rules 15 · 20 · 21 · 31 · 32 · g13 · g15 | F1 · F2 · A5 | `Work-023` (`wireframes/Work-023.png`, **the block sentence asserted ABSENT**) · `Work-024` (`wireframes/Work-024.png`) | L |
| **F4** | 2c | `US-WRK-020` TC-1..7 (a technician with no login refused; crew and contractor as rows) · `021` TC-1..7 (**TC-3 the stub raises naming `OQ-WRK-1493`; TC-4 the watch shows the date and refuses nothing**) · `022` TC-1..5 (the permission is declared and held by no role; **the TC asserting a clerk is refused is marked expected-to-fail naming `OQ-WRK-1492`**) · `023` TC-1..6 (**TC-2/TC-3 the web refusal — expected-to-fail naming `OQ-WRK-1494`**; the role holds no staff permission today). Fixture: D. Ortiz · M. Chen · R. Patel · J. Kaur (confined space expires Aug 20) · Crew B (3) · Apex Utility Svc (contractor); T. Osei invited as Field technician. RLS zero rows on PG | 020 · 021 · 022 · 023 | F1–F3 | — | M |
| **F5** | review | Review-ledger row for the RLS migration 🔒: *four new tables say who works for a utility and what they may do; a technician is one utility's; Lone Star Ridge's dispatcher sees none of Brazos Bend's six rows, proved on PostgreSQL* | 020 · CLAUDE.md 🔒 | F1 | — | S |
| **F6** | 2d | **`cr070-f-who-can-do-what.mjs`**: Crews reads *6 rows · 4 people, 1 crew, 1 contractor* · J. Kaur carries *cert expiring* and the watch reads *30 days — J. Kaur, confined space expires Aug 20.* **and the DOM contains no *blocked from*** · open R. Patel → three skills with proficiency, two certification chips with expiry, *Jobs closed 88* · *Assign skills* → three steps → confirm → the row changes · Settings › Team → invite T. Osei as *Field technician* → in the terminal: T. Osei's web sign-in is **allowed** and the log carries one line naming the question · a Billing Clerk's Accept on `WO-4906` **succeeds** and the log carries one line naming the other · screenshots | 020 · 021 · 022 · 023 · `BR-WRK-028` · `030` · `043` · `044` · law 6 | F3 · F4 | — | S |
| **F7** | doc / version | CHANGELOG · lockstep · TSV · decision-log row (the watch's "template types that NAME the certification" count; the role added holding nothing) | — | F6 | — | S |
| **F8** | blocked | **After `OQ-WRK-1492`:** assign `work_accept` to the ruled roles and turn the log line into a refusal (five or six words) — the expected-to-fail test goes green and is un-marked. **After `OQ-WRK-1494`:** the web refusal *This login is for the field app* (option a's own sentence) or the empty shell (b). **After `OQ-WRK-1493`:** the block, or the drawing stamped *warn*. Nothing before | 021 · 022 · 023 | three rulings | `DEF-WRK-3551` | — |

**Wave F — AS BUILT (2026-09-05, the CR-070 wave F build lane).**

⚠ **THE HEADER ABOVE IS STALE AND IS LEFT STANDING AS THE RECORD.** It reads
*"Blocked by: `OQ-WRK-1492` … `OQ-WRK-1494` … `OQ-WRK-1493` — each to its
boundary"*, and `F1`, `F2`, `F4` and `F8` each name a `NotImplementedError`.
**All three questions were RULED on 2026-09-04, the day after this plan was
written**, and r11 step 0 is what caught it. **No stub was written; the ruled
behaviour is built.** What each ruling changed:

* `OQ-WRK-1492` — *"clark can do it sicne it s a day to day work"*. The three
  OFFICE roles hold `work_accept`; `accept_field_result` refuses a role that
  does not. `F4`'s *"marked expected-to-fail"* case is INVERTED: what is worth
  asserting is that `field_technician` holds zero permissions.
* `OQ-WRK-1493` — option (c), per-tenant, default **warn**. `work_settings.
  certification_lapse_policy` is the switch; **both sides are built** and
  `F3`'s *"the block sentence asserted ABSENT"* is asserted absent on a default
  tenant and PRESENT on a blocking one.
* `OQ-WRK-1494` — option (a), a `surface_scope` column on `users`. The web
  sign-in is REFUSED with *"Sign in on the field app."* — six words, because
  B14 rule 33 caps a refusal at five or six and r10's seven-word sentence
  breaches it. `F4`'s two expected-to-fail cases are green assertions.

**`F8` is therefore EMPTY and this wave closes it.**

Built, verified from the code:

* **`F1` — six tables, not four.** `work/0006_cr070_f_workforce` creates
  `crews`, `technicians`, `technician_skills`, `technician_certifications`,
  plus **`crew_skills`** (a crew holds skills too, and a nullable either/or FK
  is a shape that lets a bad row exist) and **`work_settings`** (one row per
  tenant, the certification-lapse policy the ruling needs — Work's own table,
  because Work writes nobody else's). `work/0007_rls_force_workforce` 🔒 is the
  policy file. `technician_devices` is deliberately absent — `US-WRK-030`'s.
* **`F1` — eight routes** in `apps/work/api.py` over `apps/work/workforce.py`:
  `GET·POST /work/crews` · `PATCH /work/crews/{id}` · `GET·POST
  /work/technicians` · `GET·PATCH /work/technicians/{slug}` · `PUT
  …/skills` · `PUT …/certifications` · `POST …/unavailable` ·
  `GET /work/certification-watch`. **The technician path segment is a SLUG**
  (`r-patel`) — B14 rule 31, and the address `WS-24` itself draws.
  `skill_match()` (`BR-WRK-029`) is published for wave G and applies the
  certification ruling, so the two waves cannot write the predicate twice.
* **`F2` — identity's companion, in identity's own app.**
  `identity/0005_cr070_f_field_technician` adds `users.surface_scope`
  (default `both`, so no existing login changed), seeds the
  `field_technician` role holding NOTHING, and seeds `work_accept` granted to
  the three office roles. ⚠ **`work_accept` is NOT an A4 row**: `A4_MATRIX`
  transcribes a SIGNED grid verbatim (`BR-IDN-014`) and a tenth row would make
  the transcription untrue — so Settings › Users & roles still draws nine, and
  **that gap is written down rather than hidden**. `identity_seam.may()`,
  `surface_scope()`, `enforce_surface()` and `staff_user_choices()` READ
  identity and grant nothing.
* **`F3` — `features/work/CrewsPage.tsx`** (`WRK-07`),
  **`TechnicianDetailPage.tsx`** (`WRK-08`), **`SkillsWizard.tsx`** (a
  sub-screen, no id per `01-overview.md` §6) and `workforceLabels.ts` (a leaf
  module — the two fallback maps closed an import CYCLE when they lived in the
  screens, the trap `WorkShell.tsx` records for `DEF-WRK-3955`). All three
  screens are on `route-b-migrated.txt` from their FIRST commit. `WorkTabs`
  gains *Crews*, before Parts, in the inventory's order. **`WRK-14` was NOT
  allocated** — `01-overview.md` §6 lists the skills wizard among the seven
  undrawn r10 surfaces that take no id, and the plan's F3 row is wrong on this.
* **What is NOT built, and it is not a deferral to chase:** TODAY,
  UTILISATION and the *THIS MONTH* figures need `work_orders`'s assignee
  column, which is wave `G`'s. Every one is stamped in `08-screen-layouts.md`.
* **`F4`** — `tests/test_us_wrk_020_021_workforce.py`, 24 cases, and
  `CrewsPage.test.tsx` (13) + `TechnicianDetailPage.test.tsx` (12).
* **Locale keys are OWED**: every string carries a `defaultValue`, so the
  screens read correctly in English; the eleven catalogues are handed over.

**Demo script F (M. Torres, then Alex Reed):** 1 Work → *Crews* → six rows, one of them a crew of three and one a
contractor → 2 J. Kaur: *cert expiring*; the watch names the date — and does not say she is blocked → 3 open
R. Patel → skills with proficiency, two certifications with expiry → 4 *Assign skills* → add *Water II · trained*
→ the row reads it → 5 Settings › Team → invite T. Osei as *Field technician · Work (mobile only)* → 6 T. Osei
opens the web app — it lets her in, and the log says the rule is not yet decided → 7 a Billing Clerk accepts a
gas light-up — it succeeds, and the log says the same.
**Exit test (asserts a rule):** `BR-WRK-028` — a technician with no `identity.User` is refused; `BR-WRK-030` —
nothing refuses on a lapsed certification and the sentence is not rendered; `BR-WRK-044` / `043` — the boundary
is a logged line, not a silent allow, and the tests that would prove the refusal are marked, not deleted.

---

### Wave G — the dispatcher · phase 2

**Goal:** one place to see every open order and drive it: five KPI tiles, six filters and no seventh, ten
columns, bulk *Assign · Reschedule · Change priority* writing one row per order, the Area filter from the areas
the utility already has.
**Stories:** US-WRK-024 · US-WRK-025 · US-WRK-026 · US-WRK-027 · US-WRK-011
**Depends on:** A (the anchor) · C (types, priorities) · F (technicians, the skill match). **Runs beside E.**
**Blocked by:** nothing.
**Version:** next free `<change>`. **Size:** two people, two weeks.

| Task | r11 | What it touches | Stories · rules | Depends on | Design xref | Size |
|---|---|---|---|---|---|---|
| **G1** | 2a | **The twelve dispatch columns** on the orders table (`03-field-map.md` §3 rows 6–15: `priority_id` · `due_at` · `window_start/end` · **`dispatch_state`** enum Queued · Scheduled · En route · On site · Complete · On hold · Cancelled — a THIRD axis beside `state` and `outcome` · ⚠ **`source` IS ALREADY BUILT AND ITS VOCABULARY IS CLOSED — `metering/0049` (wave `P`, 2026-09-05) declares all FOURTEEN tokens and `ck_work_orders_source` refuses anything else, so this row adds NO column and MAY NOT narrow it (`DEF-WRK-3726`); `G` reads it and draws it as RAISED BY** · `rule_id` · `assignee_technician_id` / `assignee_crew_id` (a cache) · `assigned_at` / `assigned_by` · `est_duration` · `area_id` → `tenancy.areas` (`tenancy/models.py:611`)); `due_at` defaults to raise + the priority's SLA hours (`BR-WRK-018`). **`work_order_assignments`** — act ∈ assign · unassign · schedule · depart · arrive, **append-only trigger**, never an UPDATE; **`work/0008_cr070_g_assignments` + `work/0009_rls_force_dispatch`** 🔒 ⚠ **AS BUILT 2026-09-05, AND THREE THINGS IN THIS ROW MOVED** (restored 2026-09-05, `DEF-WRK-4041` — this amendment was reverted off the branch for about an hour and the row read `work/000N_rls_force` again, which is the exact instruction it exists to correct). (a) The twelve columns are **`metering/0050`**, not `work/000N`: Django resolves a migration's `model_name` inside its own app and `workorder` is declared in `apps/metering/connections.py`, so an `AddField` written into `apps/work/migrations` raises before it can run — the same correction `metering/0049` already had to make for wave `P`. (b) The estimate column is **`est_duration`, a `DurationField`**, because that is what `work_order_types.est_duration` — the column it is COPIED from — already is; a first draft called it `est_minutes` reasoning from hard rule 3, and the suite caught it: hard rule 3 is met by the TYPE here, since a `timedelta` cannot be read in the wrong unit. (c) `rule_id` is a **plain uuid**, the B11 F-3 deferred-FK convention `gate_order_id` already uses, because `work_order_rules` is wave `M`'s table and does not exist yet. | 024 · 025 · 011 · `BR-WRK-018` · `022` · `023` · `024` · `025` · hard rule 1 | A4 · C1 · F1 | `WM-14` · `WM-15` · `WM-28` | L |
| **G2** | 2a | `apps/work/dispatch.py` — `assign` offers only a technician, crew or contractor whose skills match the template's skill (`BR-WRK-029`, F1's predicate); each act appends a row and refreshes the cache. Routes `07-endpoints.md` §5: **`GET /work-orders?q=&type=&status=&priority=&technician=&area=` — exactly six filters, `400` on a seventh**, sorted by priority rank then due time, footer count; `GET /work-orders/{id}`; `POST /work-orders/{id}/assignments`; `POST …/hold` (`dispatch_state = on_hold`); `POST …/cancel` (nothing deleted); **`POST /work-orders/bulk`** act ∈ assign · reschedule · priority + ids — **per-order results, one assignment or audit row PER ORDER, never one for the batch** (`BR-WRK-027`; `dispatch_batch` still allocates nothing — `OQ-WRK-1497`); `GET /work/kpis` — the five tiles; `GET /work-orders/{id}/audit` | 024 · 025 · 026 · 027 · 011 · `BR-WRK-025` · `026` · `027` · `029` · hard rule 7 | G1 | `WM-16` · `WM-17` | L |
| **G3** | 2b | **`Work-007` becomes template W2** (`features/work/OrdersPage.tsx`): `KPIStrip` of **five** (`components/KPIStrip.tsx` has carried four — a count, not a new component) UNASSIGNED · DUE TODAY · IN THE FIELD · AWAITING APPROVAL · OVERDUE with the sub-lines; `Card` *OPEN ORDERS* with **Columns ▾**; `FilterBar` — search *Search WO #, premise…* + chips *Type · Status · Priority · Technician · Area* (the Area chip from `tenancy.Area` through the seam) + the CR-045 download glyph; the ten columns with bulk checkbox — `PriorityPill`, `StatusPill.red` *Unassigned*, RAISED BY; footer *Showing 8 of 10 open orders · sorted by priority then due time  1–8 of 10*; `ActionRow` **+ New work order** (the wizard is H — the button is not rendered before it exists, law 2) · **Assign selected…** · **Reschedule selected…** · **Change priority…** as `FormModal`s | 026 · 027 · 011 · 024 · `BR-WRK-026` · `027` · B14 rules 15 · 20 · 21 · 31 · 32 · g13 · g15 | G2 · A5 | `Work-007` (`wireframes/Work-007.png`, the whole frame) · `WM-17` | L |
| **G4** | 2c | `US-WRK-024` TC-1..7 (`dispatch_state` moves while `state` does not; `due_at` = raise + SLA; source stamped) · `025` TC-1..7 (**the append-only trigger on PG**; an UPDATE refused; a skill mismatch refused) · `026` TC-1..7 (six filters; the seventh → 400; footer count) · `027` TC-1..7 (bulk assign of three → three rows; per-order results) · `011` TC-1..5 (the Area filter is `tenancy.Area`, never a copy). Fixture: the drawing's ten open orders `WO-4821`–`WO-4830` with priorities, technicians, areas *North · Route 1…*, sources; `JOBS_EAGER=false --reuse-db` | 024 · 025 · 026 · 027 · 011 | G1–G3 | — | M |
| **G5** | review | Review-ledger row for the RLS migration 🔒: *the assignment history is written, never rewritten — on PostgreSQL an attempt to change a row is refused by the database; and every row belongs to one utility, zero to the other* | 025 · CLAUDE.md 🔒 · hard rule 4's shape | G1 | — | S |
| **G6** | 2d | **`cr070-g-the-dispatcher.mjs`**: five tiles with the drawing's figures (*4 · 5 · 2 · 3 · 1*) · six chips and a search, and a seventh query parameter answered `400` · `WO-4823` reads *Unassigned* in red and *High* in amber · tick three Queued rows → *Assign selected…* → D. Ortiz → three rows read *Scheduled* and three assignment rows exist · the Area chip lists Brazos Bend's areas · the footer sentence · no `BR-` string, no uuid · screenshots beside `wireframes/Work-007.png` | 024 · 025 · 026 · 027 · 011 · `BR-WRK-023` · `026` · `027` · law 6 | G3 · G4 | — | S |
| **G7** | doc / version | CHANGELOG · lockstep · TSV · decision-log row (the fifth KPI tile; the bulk modal shape) | — | G6 | — | S |

**Demo script G (M. Torres):** 1 Work → *Orders* → five tiles: *4 unassigned · 5 due today · 2 in the field · 3
awaiting approval · 1 overdue* → 2 filter *Status · Queued* → three rows → 3 tick all three → *Assign selected…* →
D. Ortiz (offered because his skills match) → 4 the three rows read *Scheduled · D. Ortiz*; the UNASSIGNED tile
reads *1* → 5 open `WO-4823`'s audit → three *assign* rows, not one → 6 *Change priority…* on one → *Urgent* → the
list re-sorts → 7 the footer counts what is shown.
**Exit test (asserts a rule):** `BR-WRK-025` — the assignment table refuses an UPDATE on PostgreSQL; `BR-WRK-026`
— exactly six filters, the seventh refused; `BR-WRK-027` — a bulk act writes one row per order; `BR-WRK-023` —
assigning moves `dispatch_state` and leaves `state` where it was.

**Wave G — AS BUILT (2026-09-05, the CR-070 wave G build lane; product `2.189.0`).** Every task above is done and
pushed, and the SCHEMA went out ahead of the screens so H, I and M could start on it.

⚠ **RESTORED 2026-09-05 BY THE WAVE K LANE — THIS BLOCK WAS DELETED FROM THE BRANCH FOR ABOUT AN HOUR
(`DEF-WRK-4041`).** Wave I's `I2` commit (`0e090e91`) wrote this file from a copy read before wave G pushed, so
its own 41 correct lines arrived and these 37 left by subtraction. Law 11 mechanism two, and every post-push check
in that law passes on it: the file count is right, wave I's hunks are all its own, and the deleted text is not in
the diff at all. It was found only because a third lane's push helper refused to overwrite a path that had moved.
**The four corrections below are why it matters rather than a record for its own sake** — a lane reading G1's table
row without them writes a migration into `apps/work/migrations` that cannot run.

**What exists now.** `work_orders` carries the twelve dispatch columns (`metering/0050`) and
`work_order_assignments` is a new, append-only table (`work/0008` + `work/0009`). `apps/work/dispatch.py` serves
nine routes beside the grown `GET /work-orders`; `Work-007` is template W2.

**Four things this row's own table got wrong, each corrected above or in the decision log.**
1. The columns are a **metering** migration, not `work/000N` — Django resolves `model_name` inside the migration's
   own app (`metering/0049` had already made this correction for wave `P`).
2. The estimate is **`est_duration`, a `DurationField`**, not an integer of minutes.
3. The seventh filter is refused with **`422`**, not `400` — every `VAL_*` refusal in this product answers 422 by
   law IS-7, and `07-endpoints.md` row 61 is amended rather than the code.
4. **`BR-WRK-026` and `BR-SHL-011` collided** and neither moved: the six are BARE parameters and a seventh bare
   name is refused, while `f.<name>` stays ignored — which is what wave `O`'s shipped test already asserted.

**What wave `H` can build on, stated plainly.** The order row it opens is served by
`GET /work-orders/{id}` in the SAME shape as a list row plus `state`, `outcome` and
`est_duration_minutes`; the list's column set is `workOrdersTableConfig`; the assignment history is
`GET /work-orders/{id}/audit`, oldest first. `metering_seam.work_order_with_joins` and `save_order_fields` are the
read and the write door — ⚠ **wave `H` landed its own `work_order()` in that seam while this lane worked, returning
a DICT where this one returns the model row, so the dispatcher's is `work_order_row()`.** `Work-008`'s row action
and the `+ New work order` button are declared as HOLDS in `ORDERS_HELD_CONTROLS` with the address that releases
each, and `OrdersPage.test.tsx` goes RED the day either path is registered — **release them in the commit that
lands the screen** (hard-won law 2's mirror clause).

**Proved.** 33 backend cases (`tests/test_us_wrk_024_027_dispatch.py`), **8 on real PostgreSQL 16**
(`tests/test_us_wrk_025_dispatch_pg.py` — the append-only trigger, RLS `FORCE` under `sbh_rls_probe`, and the
per-order savepoint), 16 frontend cases, `tsc`, `G31`, `G33`, `G78`. ⚠ Two of the three red proofs found real
defects: `work/0009` **did not compile** (`DEF-WRK-4027`, found by another lane first), and the savepoint case
**could not fail** as first written. Both are recorded where they happened rather than quietly fixed.

**Owed, and deliberately not built.** `GET /work-orders/map` (row 68) — it needs coordinates through
`customers_seam` and is `WM-23`'s own screen, not the dispatcher's frame. `dispatch_batch` still allocates nothing
(`BR-WRK-021`, `OQ-WRK-1497` OPEN), which is the shape that does not prejudge the answer.

---

### Wave H — the order in hand · phase 2

**Goal:** a dispatcher raises a one-off job in three steps; the order takes its own copies of the template and
opens as a six-tab detail whose checklist, readings and help are its own — so publishing v2 changes nothing on
the four v1 orders.
**Stories:** US-WRK-028 · US-WRK-032 · US-WRK-033
**Depends on:** D (the child tables) · G (the columns, the list). **Blocked by:** nothing.
**Version:** next free `<change>`. **Size:** two people, two weeks.

| Task | r11 | What it touches | Stories · rules | Depends on | Design xref | Size |
|---|---|---|---|---|---|---|
| **H1** | 2a | **Six copy tables** (`03-field-map.md` §2.4: `work_order_tasks` · `work_order_readings` — `photo_required` the RULE and `photo_attachment_id` the FILE as two columns, `in_range` server-derived · `work_order_materials` · `work_order_safety` · `work_order_help` · `work_order_details`; **no FK to any `wot_*` row — a copy**; the decision-log row of 2026-09-03 *six copies, not three*); **`work/000N_rls_force`** 🔒. `create_work_order` **copies the published version's collections at raise and stamps `template_version`** (`BR-WRK-008`). Routes `07-endpoints.md` §6 #71–#73: `GET /work-orders/{id}/checklist`, `POST …/safety/{sid}/tick`, `POST …/tasks/{tid}/tick` — **refused while the safety lock holds** (`checklist.py`, the one lock both the staff screen and J's phone call; two of three ticked is locked, not two-thirds unlocked) | 032 · 033 · `BR-WRK-008` · `037` (the lock) · hard rules 1 · 3 | D1 · G1 | `WM-18` · `WM-19` · `WS-08` | L |
| **H2** | 2b | **`features/work/OrderDetailPage.tsx`** (`Work-008`, W4 per the layouts entry): kicker *WORK › ORDERS* · title `WO-4822 · Meter exchange` · `MetaLine` · Tabs **Overview · Checklist · Parts · Location · Customer · Audit** · Checklist: *SAFETY — BEFORE YOU START* `CheckRow`s · *TASKS — 7 STEPS · 45 MIN ESTIMATED* with *· photo required* in red · *READINGS TO TAKE* table (the `Thumbnail` cell arrives in K — a dash until then) · *HELP & SUPPORT* `ContactRow`s · the `ConsequenceBox` *Marking complete sends it for approval. It does not activate anything until a person accepts it.* · **Mark complete** (disabled until the ticks) · **Reassign…** · **Put on hold…** · **Cancel order** (danger). The `Work-003` drawer links through. **The three-step New order wizard** as a sub-screen of `Work-007` on `WizardFrame` — *Job & location* (anchor: connection · premises · account · asset; template from the type's default) · *Schedule & crew* · *Confirm* → `POST /work-orders`; **+ New work order** now rendered on `Work-007`. `screenIds.ts` + `g29` rows (`WRK-02`, `WRK-12`) | 028 · 032 · 033 · `BR-WRK-008` · `024` · B14 rules 6 · 11 · 15 · 21 · 31 · 32 · g13 · g15 | H1 · G3 | `Work-008` (`wireframes/Work-008.png`) · `WM-20` (undrawn — r10 `WRK-12`) | L |
| **H3** | 2c | `US-WRK-028` TC-1..6 (the anchor CHECK from step 1; a template's copies land) · `032` TC-1..7 (**publish v2 → a v1 order still has six tasks**; a task row has no FK to `wot_tasks`; `US-WRK-018` TC-3 lands here as named in D4) · `033` TC-1..7 (six tabs; Mark complete disabled until the lock lifts; a tick on a task under the lock refused by the server). **Journey `J67` activated** (its spec written and green, the banner removed); `J62`'s first half. Fixture: `WO-4822 · Meter exchange · 221 Oak Ave · A-10688 · D. Ortiz · Today 15:30 · Scheduled` with the drawing's seven tasks and three readings | 028 · 032 · 033 | H1 · H2 | — | M |
| **H4** | review | Review-ledger row for the RLS migration 🔒: *six new tables are the order's own copy of its template — safety, tasks, readings, materials, help, details; editing the template afterwards changes none of them; each belongs to one utility, proved on PostgreSQL* | 032 · CLAUDE.md 🔒 | H1 | — | S |
| **H5** | 2d | **`cr070-h-the-order-in-hand.mjs`** (`J67` + `J62`'s first half): `Work-007` → *+ New work order* → *Leak investigation* on `77 Cedar Ct` · *High* · due today 17:00 → *Confirm* → `WO-4832` reads *Queued · Unassigned* · open `WO-4822` → six tabs; Checklist shows the seven tasks, two reading *photo required* in red, the three help rows, the consequence sentence, *Mark complete* disabled · tick two of three safety rows → a task tick is refused (the sentence, five or six words) · publish v2 of *Meter exchange — residential* adding *Apply tamper seal* → `WO-4822` still shows **seven** tasks · screenshots beside `wireframes/Work-008.png` | 028 · 032 · 033 · `BR-WRK-008` · `037` · B14 31 · 32 · law 6 | H2 · H3 | — | S |
| **H6** | doc / version | CHANGELOG · lockstep · TSV · decision-log row | — | H5 | — | S |

**Demo script H (M. Torres):** 1 *Orders* → *+ New work order* → *Job & location*: `77 Cedar Ct`, *Leak
investigation* → 2 *Schedule & crew*: leave unassigned, due 17:00 → 3 *Confirm* → `WO-4832 · Queued` in the list
→ 4 open `WO-4822` → *Checklist*: three safety rows, seven tasks, three readings, the SOP and two phone numbers →
5 tick two safety rows → try a task → refused: *Finish safety first* → 6 Templates → publish v2 with an eighth task
→ 7 back to `WO-4822` → still seven; the Versions tab says the four v1 orders still read v1.
**Exit test (asserts a rule):** `BR-WRK-008` — copy, never link: a v2 publish leaves a v1 order's tables untouched
and no FK joins them; `BR-WRK-037`'s lock — the server refuses a task tick under an incomplete safety list, whatever
the screen does.

**Wave H — AS BUILT (2026-09-05, the CR-070 wave H build lane; product `2.190.0`).
⚠ `H1`'s MIGRATION NUMBERS MOVED AND THE PLAN'S OWN TABLE IS AMENDED HERE:** the row
says `work/000N_rls_force`, which is right — these six are Work's own tables, unlike
wave `G`'s columns, which sit on metering's `work_orders` and had to move. What did
move is the NUMBER: wave `N` took `work/0010` and `work/0011` in the same minute this
lane did, both lanes computing the next free number correctly from the world each could
see. They are **`work/0012`** and **`work/0013`**. It is `DEF-CWP-3734`'s shape one
family along — `allocate.py` asks the remote for defect ids, gate numbers and versions,
and knows nothing about migration numbers, where a collision breaks the branch harder:
Django refuses **every test in the process** with *"Conflicting migrations detected;
multiple leaf nodes"*, which names neither lane.

* **`H1`** — `work/0012_cr070_h_order_copies` creates the six copy tables
  (`work_order_details` · `_safety` · `_tasks` · `_materials` · `_readings` · `_help`);
  `work/0013_rls_force_order_copies` 🔒 puts ENABLE + FORCE on all six.
  `apps/work/order_copies.copy_template_onto_order` writes them, called BY NAME from
  metering's `create_work_order` inside its own transaction — the shape
  `templates_svc.publish` already takes in reverse, so neither module writes the other's
  table (B2 §2). ⚠ **IT HANGS OFF THE RAISE AND NOT OFF THE WIZARD**, so
  `commit_connection`, the five customer flows of wave `P`, a failed outcome's follow-up
  and the seeder all get copies: `BR-WRK-008` says *when an order is raised*, not *when a
  dispatcher raises one*. `apps/work/checklist.py` is the ONE lock both surfaces read
  (`safety_lock`), and routes #71–#73 are in `apps/work/api.py`. A DRAFT template is
  refused before the order row is written (`US-WRK-032` TC-4), so no order can be stamped
  `template_version = 0` against a bundle that may still move.
  ⚠ **`access_notes`, `hazards` AND `gate_code` ARE WRITTEN NULL, DELIBERATELY** —
  `03-field-map.md` §2.4 sources them from the premises and `metering.Premises` carries
  none of the three at this tip.
* **`H2`** — `features/work/OrderDetailPage.tsx` (`Work-008`, W4) with `WM-19`'s six tabs,
  and `features/work/NewOrderWizard.tsx` (`WM-20`, r10's `WRK-12`) as a sub-screen of
  `Work-007` on `WizardFrame`. Both on `route-b-migrated.txt` in the commit that created
  them. `screenIds.ts` gains `WRK-02` and `WRK-12`, both BORROWED from r10 rather than
  minted. ⚠ **WAVE G's TWO HELD CONTROLS ARE RELEASED IN THE SAME COMMIT** — its
  `ORDERS_HELD_CONTROLS` declared each refusal with the address that would release it, and
  registering those two addresses turned `OrdersPage.test.tsx` RED and NAMED both. The
  list is kept, now empty, with its assertions INVERTED so a later unmount fails too.
* **`H3`** — `tests/test_us_wrk_032_copies.py` (12 cases, `US-WRK-032` TC-1..TC-7 including
  `US-WRK-018` TC-3 as `D4` named) · `tests/test_us_wrk_033_checklist.py` (11) ·
  `OrderDetailPage.test.tsx` + `NewOrderWizard.test.tsx` (24). **TC-6 is the case that
  survives a refactor:** it asserts against the SCHEMA that no copy table has a foreign key
  to any `wot_*` table, because TC-2 and TC-3 pass for exactly as long as nobody writes the
  join. ⚠ `J67` and `J62` are NOT activated — see the amendment below.
* **`H4`** — the review-ledger row for `work/0013` 🔒, in plain English with the worked
  figure (`WO-4822`'s seven tasks against the template's eight after a publish).
  `tests/test_us_wrk_032_copies_pg.py` proves the policy on real PostgreSQL under the
  `sbh_rls_probe` role. ⚠ **THE TENANT-ISOLATION GATE WAS NOT ACCEPTED AS THE EVIDENCE**:
  `DEF-GOV-4024` records that it runs the isolation suite without pointing it at
  PostgreSQL and inherits SQLite — 46 of 238 proofs run, 192 skip, exit 0.
* **`H5`** — `10-scripts/render-checks/cr070-h-the-order-in-hand.mjs`. ⚠ **ONE OF ITS
  ASSERTIONS CANNOT BE MADE ANYWHERE ELSE:** `WizardFrame` renders only the ACTIVE step and
  `BR-SHL-018` refuses a URL jump to step 3, so **no server render can contain the Confirm
  step's consequence box**. Only clicking Continue twice reaches it, which is exactly the
  gap hard-won law 6 names.
* **`H6`** — CHANGELOG `2.190.0`, version lockstep across all three literals, this stamp,
  and the decision-log row.

**⚠ WHAT WAVE H DID NOT DO, STATED RATHER THAN LEFT TO BE DISCOVERED.**
**(a) `J67` AND `J62` ARE NOT ACTIVATED.** `H3` says *"Journey `J67` activated (its spec
written and green, the banner removed); `J62`'s first half"*, and neither happened. The
journey files are cross-module handoff contracts and activating one is a claim about what
upstream leaves in the database for downstream; wave H proved its own tables and screens
and did not write those specs. They remain banner-ed.
**(b) THE ORDER DETAIL'S FOUR ACTIONS ARE DRAWN AND DO NOTHING YET.** *Mark complete*,
*Reassign…*, *Put on hold…* and *Cancel order* render — the first correctly disabled by
the safety lock — and none is wired to its endpoint. `Mark complete` is
`submit_field_result` (`US-WRK-033` TC-2), and the other three are wave `I`'s
`PATCH /work-orders/{id}` and the hold/cancel routes wave `G` already built. ⚠ **THIS IS
EXACTLY THE SHAPE OF `DEF-CWP-3925`** — a live screen behind dead controls — and it is
recorded here rather than declared as data, because `ORDERS_HELD_CONTROLS` is
`Work-007`'s and `Work-008` has no equivalent. **A lane wiring them should add one.**
**(c) `Work-003`, the drawer, does not link through yet.** `H2`'s row says it should.

---

### Wave I — changing course · phase 2

**Goal:** everything a dispatcher changes after an order exists, behind a box that says what pressing Save does;
a failed field outcome raises the follow-up and holds the build on its own; the map shows the day's pins.
**Stories:** US-WRK-031 ⚠ (the notice) · US-WRK-034 · US-WRK-029
**Depends on:** G (the columns, the list) · F (technicians) · B (accept) · **O (the build's home — `I`'s failed
outcome puts a build on hold and the hold has to be VISIBLE somewhere; that somewhere is no longer `NCT-02`)**.
**Runs beside H.** ⚠ **Blocked by: NOTHING — `OQ-WRK-1495` WAS CLOSED 2026-09-04 AND THIS ROW SAID IT WAS OPEN UNTIL 2026-09-05** (found by the wave I build lane at r11 step 0). The PO ruled option **(a)**: a reschedule sends on a NEW message source kind, `appointment`. So the stub `I1` describes below is superseded, `I6` is not a later task, and the Change effects box's first line is no longer *being decided*. **All nine `OQ-WRK-*` questions are now CLOSED.**
**Version:** next free `<change>`. **Size:** one person, two weeks.

| Task | r11 | What it touches | Stories · rules | Depends on | Design xref | Size |
|---|---|---|---|---|---|---|
| **I1** | 2a | `PATCH /work-orders/{id}` — priority · due · window · area · `technician_notes` (`03-field-map.md` §3 row 17); **refuses priority on Complete**; **every field change audited with who and when** (`BR-WRK-031`'s confirmed half); ⚠ **THE RESCHEDULE NOTICE IS A REAL SEND, NOT A STUB — AMENDED 2026-09-05.** This row said `notify_reschedule()` raises `NotImplementedError("OQ-WRK-1495")` and the response carries `reschedule_notice_kind_unruled`. `OQ-WRK-1495` closed 2026-09-04 on option (a), so `notify_reschedule()` QUEUES on the new source kind **`appointment`** through `seams.queue_document`, and the response carries `reschedule_notice` with the queued row. ⚠ **AND THE CLOSURE'S OWN ARITHMETIC IS STALE TOO:** it says the platform constant goes from *ten kinds to eleven*, and `portal` landed the same day (`CR-068` wave E), so `notifications.SOURCE_TYPES` is at ELEVEN and `appointment` makes **TWELVE**. **The consequence chain** inside `accept_field_result` (`connections.py:2116`): outcome `failed` → a follow-up order with `blocked_by` = the failed one and `follows_order_id`, source *Failed outcome*; the connection **On hold** with the reason in `waiting_on`; *"a refusal anywhere rolls the whole acceptance back"*; a failed one-off job with no connection gets the follow-up and no hold. **`GET /work-orders/map`** — pins from premises `lat`/`lng` (`metering/models.py:404–405`) through `metering_seam`, coloured by status and priority, hollow when unassigned, plus the *not on the map* strip for orders with no coordinates | 031 · 034 · 029 · `BR-WRK-031` · `054` · `023` · hard rule 7 | G2 · B1 | `WM-39` · `WM-25` · `WM-23` | L |
| **I2** | 2b | **`features/work/OrderEditPage.tsx`** (`Work-021`, W6 per the layouts entry): *STATUS, PRIORITY AND PROMISE* — STATUS with the help line *Queued · Scheduled · En route · On site · Complete · On hold · Cancelled* (a select whose options are those words) · PRIORITY · SLA TARGET; *WHO AND WHEN* — ASSIGNED TO · DATE · WINDOW (*Any time · 08:00–12:00 · 12:00–17:00 · Exact appointment*) · AREA · SUB-AREA · TEMPLATE · NOTES FOR THE TECHNICIAN; the **Change effects** `ConsequenceBox` — *Customer notification — **not yet sent; being decided*** (the register row's own wording) · *Technician phone — job updates immediately* · *Audit — every field change is logged with who and when*; **Cancel · Cancel work order (danger) · Save changes ✓**. **`features/work/MapView.tsx`** as a sub-screen of `Work-007` — the tile pattern `features/assets/AssetMapTab.tsx:51` already uses; click a pin → the job card. `WorkTabs` gains *Map*. `screenIds.ts` + `g29` rows (`WRK-03`, `WRK-09`) | 031 · 029 · `BR-WRK-032` · B14 rules 6 · 11 · 21 · 31 · 32 · g13 · g15 | I1 · G3 | `Work-021` (`wireframes/Work-021.png`) · `WM-23` (undrawn — r10 `WRK-09`) | L |
| **I3** | 2c | `US-WRK-031` TC-1..7 (**TC-5 AMENDED 2026-09-05 — the send is REAL: one `outbound_messages` row on source kind `appointment`, and the negative is that it is NOT filed as `notice`**; TC-6 the audit row per field) · `034` TC-1..6 (**`J66`**: *failed* raises `WO-4909` blocked by `WO-4907` and holds `CON-26-0117`; *passed* raises nothing; the follow-up failing rolls the acceptance back; hold outranks progress in the derived state) · `029` TC-1..6 (a premises with no coordinates is in the strip, not lost). **Journey `J66` activated** (spec written and green, banner removed) | 031 · 034 · 029 | I1 · I2 | — | M |
| **I4** | 2d | **`cr070-i-changing-course.mjs`**: open `WO-4821` → *Edit* → move the window to *12:00–17:00* → the Change effects box precedes Save and its first line reads *not yet sent; being decided* → Save → the audit tab shows the field, who and when; the response carried the unruled marker · *Cancel work order* is danger tier and asks first · the crew's result on `WO-4907` arrives *Failed · pressure test failed at 2.1 bar* → Accept → `WO-4909` exists *blocked by WO-4907*, `CON-26-0117` reads *On hold* with the reason · Map → pins; one order in *not on the map* · screenshots beside `wireframes/Work-021.png` | 031 · 034 · 029 · `BR-WRK-031` · `032` · `054` · law 6 | I2 · I3 | — | S |
| **I5** | doc / version | CHANGELOG · lockstep · TSV · decision-log row (the map tile source reused; the hollow-pin vocabulary) | — | I4 | — | S |
| **I6** | ~~blocked~~ **2a + 2b, FOLDED INTO `I1`/`I2` 2026-09-05** | **`OQ-WRK-1495` closed 2026-09-04 on option (a)** — a NEW source kind `appointment`, its own template, and the Change effects line rewritten to the ruling. Not a later task: a wave that ships the edit screen with the *being decided* line and leaves the send to a follow-up wave is hard-won law 2's mirror — a refusal that outlived its reason. **`notifications.SOURCE_TYPES` grows to TWELVE** (`portal` made eleven on 2026-09-04) | 031 · `BR-WRK-031` | ruled | `WS-21` | M |

**Demo script I (M. Torres):** 1 open `WO-4821 · Disconnect for non-payment` → *Edit* → 2 the window from
*08:00–12:00* to *12:00–17:00* → 3 the box says what Save does — and that the customer's message is not yet sent,
being decided → 4 Save → Audit: the window, M. Torres, the time → 5 `Work-009`: the external crew's `WO-4907` came
back *Failed* → Accept → 6 **the premises for `CON-26-0117`, on the Build tab wave `O` made** (⚠ **AMENDED
2026-09-04 — this step read *`Work-002` for `CON-26-0117`* and that screen is retired by `CR-070 §W.11`;
the HOLD itself is unchanged, it is a backend act and `hold_connection` still performs it**): *On hold ·
pressure test failed*, and `WO-4909` waits on `WO-4907`; the Work orders tab reads *5 of 8* → 7 *Map*: the
day's pins, `77 Cedar Ct` hollow because nobody is going.
**Exit test (asserts a rule):** `BR-WRK-054` — *failed* raises a follow-up and holds; *passed* raises nothing; a
refusal inside the chain rolls the whole acceptance back (on PostgreSQL); `BR-WRK-032` — Cancel is danger tier and
Save follows the box; `BR-WRK-031` — the notice is a named stub, never a *notice*-kind send.

---

**Wave I — AS BUILT (2026-09-05, the CR-070 wave I build lane; product `2.185.0`). Stamped
in the commit that lands the work, per the r11 step 4 amendment of the same day.**

* **`I1` — BUILT, AND THE STUB IT SPECIFIED WAS NEVER WRITTEN.** `PATCH /work-orders/{id}`
  (`apps/work/edit.py`), `GET /work-orders/{id}/edit`, `GET /work-orders/map`, and
  `_failed_outcome_chain` inside `accept_field_result`. `metering/0052` adds
  `technician_notes` and `follows_order_id` and **widens `ck_work_orders_source` to fifteen
  tokens** — `failed_outcome` did not exist, and the chain would have been refused by the
  database inside a supervisor's Accept. ⚠ Renumbered from `0051`, which wave N took while
  this was being written.
* **`I2` — BUILT.** `features/work/OrderEditPage.tsx` (`Work-021`, r10 `WRK-03`),
  `features/work/MapView.tsx` + `WorkMapPage.tsx` (r10 `WRK-09`), the Map tab on
  `WorkTabs`, two `screenIds.ts` rows, three files on `route-b-migrated.txt` in the commit
  that creates them, 42 keys × 11 catalogues. **The order number on `Work-007` is now a
  LINK to the edit screen** — landing a screen and landing the door that reaches it are one
  act, not two (hard-won law 2's mirror, `DEF-CWP-3925`).
* **`I6` — NOT A LATER TASK, AND THAT IS THIS WAVE'S HEADLINE.** `OQ-WRK-1495` closed
  2026-09-04 on option (a) and **six documents still described the stub on 2026-09-05**
  (`DEF-WRK-4028`). The reschedule notice is a REAL SEND on a new message source kind,
  `appointment` — the **twelfth**, not the eleventh the ruling names, because `CR-068`
  wave E added `portal` the same day.
* **Three collisions with live siblings, every one caught by the push helper refusing the
  file rather than by any test:** wave N's `metering/0051`; wave G publishing its own seam
  vocabulary in the same hour (mine was a duplicate and was deleted — this builds on
  `dispatch_tokens()`, `parse_moment()` and `save_order_fields()`); wave H's checklist
  routes in `api.py`.
* **Four guards found RED that nobody had run**, three fixed here: `DEF-NOT-4032` (a
  message kind unclassified since 2026-09-04), `DEF-WRK-4033` (a NOT NULL column against a
  raw-cursor PostgreSQL proof), `DEF-WRK-4034` (`G78`, the module boundary, naming
  `dispatch.py:69` by line), and `DEF-WRK-4035` left OPEN because renaming four seam
  functions would satisfy the assertion and leave the breach.
* **`I3` — PARTIAL, and stated rather than implied.** `US-WRK-031`'s patch arithmetic and
  `US-WRK-029`'s placement are covered by `OrderEditPage.test.tsx` (7 cases) and
  `MapView.test.tsx` (4 cases). The BACKEND cases for `US-WRK-034`'s chain, and journey
  `J66`'s activation, are **NOT written** — `J66` still carries its *NOT ACTIVATED* banner.
* **`I4` — NOT BUILT.** `cr070-i-changing-course.mjs` is not written and the demo script
  has not been run against the product (law 6). Reported, not papered over.
* ⚠ **AND NEITHER IS THE POSTGRESQL ISOLATION PROOF FOR THE TWO NEW COLUMNS.** The brief
  asked for it explicitly. `metering/0052`'s docstring named a test file that was never
  written, and the review-ledger row said the RLS claim was *"asserted against a real
  PostgreSQL"* — **both were corrected the same day rather than left standing**, because a
  docstring naming a test nobody wrote is hard-won law 1 exactly. What IS true: the policy
  is on the TABLE and covers new columns by construction. What is UNPROVEN: the
  cross-tenant case for `follows_order_id`.
* ⚠ **THE WAVE ALSO REVERTED WAVE H's FRONT END AND 1,001 LOCALE KEYS, AND PUT THEM BACK**
  (`DEF-WRK-4045`). The push helper re-derived a file only when the TIP had moved it, which
  is the wrong condition when a worktree is stale: base and tip agreed, re-derivation was
  skipped, and a stale blob went straight in. **Only `git diff --numstat`, read as
  arithmetic, caught it** — a commit that only ADDED reported 206 deletions on one file.
  It then happened a SECOND time, because the per-file guard written for the first was
  given a GLOBAL override, and one file that legitimately shrank switched the check off for
  twenty-two others.

---

### Wave J — the phone, day one · phase 2

**Goal:** assigning an order pushes it to the technician's phone without them opening anything; the day list is
ordered by appointment time with an honest offline marker; the job carries everything copied from the template and
its help works with no signal; safety locks the task list on the phone **and the server refuses a close that
carries an unticked safety row**.
**Stories:** US-WRK-040 · US-WRK-041 · US-WRK-042 · US-WRK-043 · US-WRK-030
**Depends on:** F (technicians, the role) · G (assignments) · H (the copies). **Blocked by:** nothing — `OQ-WRK-1494`
bounds the login's WEB refusal (F), nothing on the phone waits.
**Version:** next free `<change>`. **Size:** two people, two weeks.

| Task | r11 | What it touches | Stories · rules | Depends on | Design xref | Size |
|---|---|---|---|---|---|---|
| **J1** | 2a | `technician_devices` (token · platform · active) + **`work/000N_rls_force`** 🔒; `POST /work/mobile/devices`. **`work.push` job kind** registered in `apps/work/apps.py` via `core.jobs.set_job_handler` + `set_job_queue(kind, "work")` (the `run_jobs.py:680–699` pattern; `celery_routes.py` routes by kind) — **the job row is written before the broker message**; **`docker-compose.yml` gains `celery-work`** (`-Q work`, `entrypoint: []`, the `CMD-SHELL` healthcheck, a CPU limit — G59's clauses) **in the same commit**; the audit row *Dispatched · pushed to phone · 14:02*. `GET /work/mobile/today` (ordered by appointment time, never priority) · `GET /work/mobile/jobs/{id}` (the six copies, the customer contact, help documents as pre-signed GETs from the document store). **The server half of the safety gate:** `submit_field_result` (`connections.py:2053`) refuses a completion carrying an unticked mandatory safety row, **naming the row**, in five or six words | 030 · 041 · 042 · 043 · `BR-WRK-034` · `035` · `037` · `038` · TD-17 · `DEF-320` | G2 · H1 · F1 | `WM-37` · `WM-32` · `WM-33` · `WM-34` | L |
| **J2** | 2b | **The phone shell** (`BR-WRK-045`, the decision-log row of 2026-09-03): `features/work/mobile/` — a web manifest, a service worker and an offline store (IndexedDB) served by the staff app's own build under `/{tenant}/work/mobile/`, installable; the staff tokens, a phone viewport; `screenIds.ts` rows; **every file on the migrated list**. Nothing of this exists at HEAD (no `serviceWorker`, no manifest anywhere in `07-frontend/src`) | 040 · `BR-WRK-045` · B14 rule 21 · g13 | A5 | r10 `workTab === 'mobile'` (the pack does not draw the phone) | L |
| **J3** | 2b | **`Work-010` Today** — the day ordered by appointment time, `PriorityPill` shown and never reordering, the offline marker *◍ offline · synced 08:12* always visible, the details ticks (dog, gate code) carried; **`Work-011` the job** — the safety panel first, the task list **locked until every mandatory safety row is ticked** (two of three ticked is locked), tasks with *· photo required*, the help rows opening offline; the readings, parts, signature and close panes arrive in K and L | 041 · 042 · 043 · `BR-WRK-035` · `036` · `037` · `038` · B14 rules 31 · 32 · g15 | J1 · J2 | `WS-10` · `WS-11` (blueprint §14, undrawn — r10 mobile) | L |
| **J4** | 2c | `US-WRK-040` TC-1..7 (installable; the store survives a reload) · `041` TC-1..7 (order by time; the marker) · `042` TC-1..6 (nothing on the screen was fetched — it was carried) · `043` TC-1..7 (**the phone lock AND the server refusal, named row**) · `030` TC-1..5 (`JOBS_EAGER=false --reuse-db`: the job row exists before the message; the audit line). Fixture: four jobs for D. Ortiz on Wed 15 Mar; a device token | 040 · 041 · 042 · 043 · 030 | J1–J3 | — | M |
| **J5** | gate | Two gates RED first, registered the same commit: **the queue pair** — G59's clauses cloned for `work` (routing ⇄ `celery-work` consumer; the default worker not draining it; entrypoint cleared; healthcheck form) — RED by deleting the compose service; **the safety gate is enforced server-side** (`CR-070` §12 gate 2) — a permanent test that POSTs a completion with an unticked mandatory row and expects the refusal — RED by commenting the check out | 030 · 043 · `BR-WRK-037` · law 7 | J1 | §12 gate 2 | S |
| **J6** | review | Review-ledger row for the RLS migration 🔒: *a phone's push token belongs to one technician of one utility; Lone Star Ridge cannot see or push to a Brazos Bend phone, proved on PostgreSQL* | 030 · CLAUDE.md 🔒 | J1 | — | S |
| **J7** | 2d | **`cr070-j-the-phone-day-one.mjs`** — two contexts: the desktop (M. Torres assigns `WO-4822` to D. Ortiz for 15:30) and a **390×844 phone context** (D. Ortiz's Today list shows it in time order with *Normal* as a pill; the marker reads *synced* with a time; open the job — the task list is locked; tick two of three safety rows — still locked; tick the third — unlocked; the SOP opens with the network **off** (`context.setOffline(true)`); in the terminal: a completion with a safety row unticked is refused naming the row) · `docker compose config` lists `celery-work` on `-Q work` · screenshots | 030 · 041 · 042 · 043 · `BR-WRK-034` · `035` · `037` · `038` · law 6 | J3–J6 | — | S |
| **J8** | doc / version | CHANGELOG · lockstep · TSV · decision-log row (the offline store chosen; the queue name) | — | J7 | — | S |

**Demo script J (M. Torres, then D. Ortiz):** 1 assign `WO-4822` to D. Ortiz for 15:30 → the audit reads
*Dispatched · pushed to phone* → 2 on the phone: Today lists four jobs in time order, `WO-4822` at 15:30, *Normal*
as a pill → 3 the marker reads *synced 08:12* → 4 open it — safety first; the tasks are greyed → 5 tick two of three
— still greyed → 6 tick the third — seven tasks appear → 7 airplane mode → the SOP still opens → 8 in the terminal,
a close with one safety row unticked is refused, and the refusal names the row.
**Exit test (asserts a rule):** `BR-WRK-037` — the server refuses, not only the phone, and the gate stays RED if the
check is removed; `BR-WRK-035` — the day is ordered by time whatever the priority; `BR-WRK-034` — the push is a job
on its own queue with its consumer in the same commit (G59's shape, `DEF-320`).

**Wave J — AS BUILT (2026-09-05, the CR-070 wave J build lane; product `2.192.0`).** J1–J8 done.
`technician_devices` with `work/0014` + `work/0015` 🔒, the `work.push` job kind with `celery-work`
(`-Q work`) in the same commit, `GET /work/mobile/today`, `GET /work/mobile/jobs/{id}`,
`POST /work/mobile/devices`, the phone shell (manifest · service worker · IndexedDB — the first of
each in this product), `Work-010`, `Work-011`, 41 tests, `G109` and `G110`, and the server half of
the safety gate. **`BR-WRK-045` moves PROPOSED → CONFIRMED**: the decision-log row of 2026-09-03 was
already a ruling, not a draft, and the rules file said *draft* until this wave read the log.

⚠ **THE MIGRATIONS WERE RUN ON REAL POSTGRESQL, NOT ONLY WRITTEN**, and on this day that was not
ceremony: `DEF-WRK-4027` had stopped **every** PostgreSQL migration on this branch at `work/0009`
until hours earlier, and `PostgresOnlySQL` is a no-op off PostgreSQL, so the SQLite suite cannot see
that class of bug at all. `relrowsecurity` and `relforcerowsecurity` are read back out of `pg_class`
under the NOSUPERUSER `sbh_rls_probe` role — the isolation GATE was not accepted as evidence, for the
two reasons the review-ledger row states.

⚠ **AND THE WAVE FOUND ONE DEFECT OF ITS OWN, IN THE REBASE RATHER THAN IN A TEST — `DEF-WRK-4041`.**
`Work-021`'s Change effects box (wave I, the same day) tells a dispatcher *"Technician phone — job
updates immediately"*. The push was built against `dispatch.record_act`, which was the only
assignment door when this wave's packet was assembled; `append_act` was extracted hours later and
`edit.save_order_edit` reassigns through IT, enqueueing nothing. **Nothing looked wrong** — the
technician still gets the job on the next ordinary sync — which is why it would have survived. The
fix is one call; the durable part is `test_tc4_c`, which asserts the job row after a reassignment
through **each** door by name, so a fourth door that forgets goes red naming itself.

⚠ **WHAT WAVE K AND WAVE L INHERIT, AND IT IS A MECHANISM RATHER THAN A NOTE.**
`features/work/mobile/heldPanes.ts` declares the four panes those waves land — readings, photographs,
signature, close — each by ADDRESS, screen and story, and `heldPanes.test.ts` asserts the route is
**not yet mounted**. The day wave K mounts `jobs/:orderId/readings`, that test goes RED and its
message names the pane, the file and the story. That is `DEF-CWP-3925`'s remedy followed literally,
one day after it was written: *when you write a hold, write the test that fires when the hold
expires, in the same commit.* **Do not delete the row to make it pass — release the control.**

---

### Wave K — what the phone sends back · phase 2

**Goal:** a photograph, a signature or a refusal, a reading with its unit — each a row the supervisor can open;
an out-of-range value is flagged and accepted; a missing required photograph is a different thing, and says so
before Close; a link to a photograph dies in four hours.
**Stories:** US-WRK-048 · US-WRK-036 · US-WRK-049 · US-WRK-047
**Depends on:** H (the readings copy) · J (the job on the phone). **Blocked by:** nothing.
**Version:** next free `<change>`. **Size:** two people, one and a half weeks.

⚠ **AMENDED 2026-09-05, AND THE AMENDMENT IS THE FIRST THING TO READ — `OQ-WRK-1496` CLOSED ON 2026-09-04,
THE DAY AFTER THIS TABLE WAS WRITTEN, AND IT MOVED TWO NUMBERS AND UNBLOCKED `K7`.** Found at r11 step 0. The
rows below still carry the pre-ruling wording; where they disagree with this block, **this block is right**.

1. **`K1` — `retention_policy()` DOES NOT RAISE.** The question is answered, so a stub naming it would be a
   lie about the state of the repo. It returns the ruled regime: **twelve months**, an **export offered before
   deletion**, and an **open-matter hold**. What still does not exist is `prune_due()`'s ability to act — it
   **raises** while no export path is built, because *an export that does not exist is not a retention policy*.
   The pruning job remains unscheduled, for the ruled reason rather than for want of a ruling.
2. **`K2`/`K3` — the phone's ceiling is `100 KB`, not `1,600 px → 250 KB`.** PO: *"when image is captured we
   redce the size first 50 Kb 60 Kb or 100 kb max"*. 1,600 px on the long side is the MECHANISM that gets
   there and is no longer the target; the quality steps down until the bytes fit. `K3`'s *"a 3 MB image
   arrives at about 250 KB"* becomes **at most 100 KB**, and the server refuses anything larger.
3. **`K1` — the PRE-SIGNED PUT IS NOT BUILT** (`BR-WRK-047a`, decision log 2026-09-05). At 250 KB–3 MB a
   direct-to-S3 PUT earned its keep; at 100 KB it buys nothing and costs the content hash, the
   `byte_length > 0` CHECK, the tenant check and the audit row, because the server never sees the bytes.
   `POST …/attachments/upload-url` still exists and still answers — with a ticket addressed at our own `PUT`
   route, a `max_bytes` and an expiry. **Revisit this rule, and only this rule, if the cap ever rises.**
4. **`K7` is no longer blocked on a ruling — it is blocked on the EXPORT**, which is a story nobody has
   written. Nothing may be deleted before it exists and the utility has been told.
5. **The storage arithmetic this replaces is the blueprint's own:** 59 GB over seven years for one utility at
   250 KB an image becomes about **3.4 GB standing** at 100 KB over twelve months — roughly one seventeenth,
   and it stops growing.

| Task | r11 | What it touches | Stories · rules | Depends on | Design xref | Size |
|---|---|---|---|---|---|---|
| **K1** | 2a | **Tenancy's migration, written in tenancy's app** (`apps/tenancy/migrations/`) — `DOCUMENT_KINDS` (`document_models.py:295`) gains `work_order_photo` · `work_order_signature` · `work_order_report`, **33 → 36**, the CHECK `ck_stored_documents_kind` (503) rebuilt. `work_order_attachments` (document · kind · taken_at · device · added_by · `reading_id` / `task_id` NULL · **`idempotency_key` unique**) · `work_order_signatures` (printed name · image · captured_by · signed_at · **or** `refused` + `decline_reason` + `door_hanger_document_id`) + **`work/000N_rls_force`** 🔒; **`attachment_ref` dropped** (`connections.py:769`, dead). Routes `07-endpoints.md` §6 #74–#79: `PUT …/readings/{rid}` (value **+ unit**; `in_range` server-derived; **never refused for range**) · `POST …/attachments/upload-url` (a pre-signed PUT through `document_store`, `:272`) · `POST …/attachments` (the row, idempotent) · `GET …/attachments/{aid}` (**a link that expires in four hours**, `url_ttl_seconds()` at 531) · `POST …/signature`. **`retention_policy()` raises `NotImplementedError("OQ-WRK-1496")`**; no pruning job is scheduled; nothing describes the files as permanent | 048 · 036 · 049 · 047 · `BR-WRK-039` · `040` · `046` · `047` · `048` · hard rules 1 · 3 | H1 · J1 | `WM-48` · `WM-30` · `WM-49` · `WM-35` | L |
| **K2** | 2b | **`Work-033`** — the Readings panel of `Work-008`'s Checklist per the layouts entry, with the **`Thumbnail`** component (the last of the inventory's three; a lightbox with *taken at* and device), VALUE *1,204* **out of range** in red (`FlagText`), PHOTOGRAPH CAPTURED `▣ IMG-8841 · D. Ortiz · 15:12` / *none — not required* / `StatusPill.amber` **missing — job cannot close**; the footer *3 of 4 readings captured · 2 of 3 required photographs*; the `ConsequenceBox` *Required means the job will not close without it; out of range never blocks.* **`Work-012` on the phone** — readings with a unit column, the camera (resized to **1,600 px** before send), the signature pad with printed name, the refusal path (decline reason + door-hanger photo); the Customer tab on `Work-008` shows the signature. Every file on the migrated list | 049 · 047 · 036 · 048 · `BR-WRK-039` · `040` · `046` · `047` · B14 rules 21 · 31 · 32 · g15 | K1 · H2 · J3 | `Work-033` (`wireframes/Work-033.png`) · `WS-12` (undrawn) | L |
| **K3** | 2c | `US-WRK-048` TC-1..7 (**TC-7 the stub raises naming `OQ-WRK-1496`**; the same key twice writes one row; the link expires; a 3 MB image arrives at about 250 KB) · `036` TC-1..6 (signature or refusal, never both; the door-hanger photo) · `049` TC-1..6 (**the rule column and the file column are different; a required photograph missing stops the close; an optional one missing does not**) · `047` TC-1..6 (1,204 against 0–999 is stored, flagged, and the job can close). Fixture: `IMG-8841`, `IMG-8842`, `SIG-4822`; the fourth reading *Voltage at socket · V · 110–125 · required* on the v2 template (`03-field-map.md` D-9) so the *missing* case exists. Isolation: Lone Star Ridge cannot fetch a Brazos Bend photograph | 048 · 036 · 049 · 047 | K1 · K2 | — | M |
| **K4** | review | Review-ledger row for the RLS migration 🔒: *a photograph, a signature and a report each belong to one order of one utility; a link to one dies after four hours; Lone Star Ridge asking for a Brazos Bend photograph gets the same answer as for one that does not exist — proved on PostgreSQL* | 048 · CLAUDE.md 🔒 | K1 | — | S |
| **K5** | 2d | **`cr070-k-what-came-back.mjs`**: on the phone, take the opening read *1,204 kWh* with a photograph → on `Work-008` the row reads *1,204 **out of range*** with a thumbnail that opens to *IMG-8842 · D. Ortiz · 16:02* · the *Voltage at socket* row reads *not taken* and **missing — job cannot close** · the footer sentence · the customer signs *S. Miller* → the Customer tab shows it · fetch the photograph's link, wait past its life (a clock the test controls) → gone · Lone Star's fetch → the absent-resource answer · screenshots beside `wireframes/Work-033.png` | 049 · 047 · 036 · 048 · `BR-WRK-039` · `040` · `046` · `047` · law 6 | K2 · K3 | — | S |
| **K6** | doc / version | CHANGELOG · lockstep · TSV · decision-log row (the 1,600 px resize; the four-hour life; the idempotency key shape) | — | K5 | — | S |
| **K7** | blocked | **After `OQ-WRK-1496`:** the retention regime — the legal-document regime (a), their own (b) or kept for the order's life (c) — and, if (b), the pruning job for Work kinds on the beat schedule. Nothing before, and **no document, screen or docstring names a period** until then | 048 · `BR-WRK-048` | a ruling | `OQ-1340`'s shape | — |

**Wave K — `K5` AS BUILT (2026-09-06, the `K5`/`N7` walkthrough lane).**
`10-scripts/render-checks/cr070-k-what-came-back.mjs`, green twice in a row against a database the first run had
already written to. ⚠ **IT FOUND FIVE FAULTS THAT 245 FRONT-END TESTS, 30 BACKEND CASES, `tsc`, eslint and every
gate were green over**, and two of them were the wave's own subject:

* **`DEF-WRK-4111` (critical) — A TECHNICIAN COULD NOT RECORD A SINGLE READING.** `Work-012`'s `ReadingRow`
  declared `unit`; the job bundle is `checklist.checklist()` verbatim and serves `unit_of_measure`. So `row.unit`
  was `undefined` on every real handset: the unit column rendered EMPTY (hard rule 3, on screen) and every save
  posted a body with no unit, which the server refuses — correctly — as `work.reading.unit_required`. The server
  log shows three 422s where three readings should have been. `ReadingsPane.dom.test.tsx` mocked `loadJob` with a
  fixture written from the TYPE, and **a mock built from a type can only confirm the type to itself**.
* **`DEF-WRK-4112` — `K2` BUILT THE PHONE AND NOT THE OFFICE.** Its commit subject says so: *"the three panes on
  the phone"*. `Work-033` had no out-of-range flag, no cannot-close pill, no thumbnail, no footer, no consequence
  line, and the Customer tab showed no signature — while `GET …/checklist` had been serving `in_range` and
  `photo_attachment_id` on every row and `close-readiness` had been publishing both lists and both counts. The
  cell rendered a dash behind a comment reading *"a dash until it lands"*. **Wave K had landed.** That is
  hard-won law 2's mirror: a refusal with a clock in it. Built here.
* **`DEF-WRK-4113`** — the phone rendered its rows from the offline bundle, which only `syncJob` writes, so
  *Photo needed to close.* survived the photograph that answered it while the live footer read *2 of 3*.
* **`DEF-WRK-4114`** — a thumbnail opened to a timestamp and a blank: `device` is sent by no client, `added_by`
  was withheld. · **`DEF-WRK-4115`** — the detail route's `:orderNo` is fed a uuid.

⚠ **TWO THINGS THE FILE REFUSES TO CLAIM, STATED THERE AT LENGTH RATHER THAN SKIPPED.** The four-hour link is
NOT watched dying: on the filesystem backend `temporary_read_url` returns a `file://` path and says in its own
docstring that it does not expire, so there is no clock to move and the assertion would be faked. What is
asserted is `expires_in_seconds = 14400` and that `url_ttl_seconds()` REFUSES a longer setting. And the
cross-TENANT fetch is not made from a second utility — the database holds one, and standing another up would
make a walkthrough a seeder — so what is proved is the observable half: a photograph of another ORDER and one
that does not exist come back BYTE-IDENTICAL, which is `HR-1`'s actual claim.

**Demo script K (D. Ortiz, then M. Torres):** 1 on the phone, *Final read on old meter · 48,221 kWh* with a
photograph → 2 *Opening read on new meter · 1,204* — the phone flags it, and lets it stand → 3 *Voltage at socket*
left blank — the phone says a required photograph is missing and the job cannot close yet → 4 S. Miller signs →
5 M. Torres opens `WO-4822` → *1,204 out of range* in red with its thumbnail; *missing — job cannot close* in amber
→ 6 the thumbnail opens: who, when, which phone → 7 the link, four hours later — gone.
**Exit test (asserts a rule):** `BR-WRK-039` — out of range flags and never refuses; `BR-WRK-040` — a missing REQUIRED
photograph stops the close and the two sentences differ; `BR-WRK-047` — the same idempotency key writes one row;
`BR-WRK-048` — ⚠ **AMENDED 2026-09-05:** twelve months IS named, and `prune_due()` refuses while the export
does not exist. The old form of this assertion (*nothing anywhere names a period*) would now go RED against a
correctly-built repo, which is what a stale exit test does.

---

### Wave L — the offline day, one sync, and the read that posts · phase 2 (the phase-2 LAUNCH)

⚠ **STATUS AS OF 2026-09-05, `2.195.0` — READ THIS BEFORE THE TABLE BELOW, WHICH IS THE PLAN AND
NOT THE RECORD.** `L1`–`L8` are BUILT and **the phase-2 launch is DECLARED**; `L9` is not, and
stays blocked on `OQ-376`. What that means in each case, because *"built"* on its own
is the sentence this repository keeps having to correct:

* **`L1` — BUILT.** `POST /work/mobile/jobs/{id}/sync`, `work_sync_receipts` (`work/0018`), RLS
  FORCE (`work/0019`), a SAVEPOINT per item with law 14's reasoning in the code, per-item
  results. The close inside it is `submit_field_result` and activates nothing.
  ⚠ **`submit_field_result` GAINED A `completed_at` PARAMETER** — the handset's time, not the
  sync's, because `accept_field_result` dates every set read from that column.
* **`L2` — BUILT, 🔒 HUMAN-REVIEW-PENDING.** `metering_seam.post_set_reads()`, called from
  `accept_field_result` inside its one transaction. ⚠ **ONE-METER JOBS ONLY.** A job carrying
  more than one posting reading is REFUSED BY NAME on **`OQ-WRK-1723`** — `work_order_readings`
  has six columns and none of them names a meter, so a meter EXCHANGE cannot say which of its
  two readings belongs to which meter, and guessing would write a second read on the OLD meter.
* **`L3` — BUILT to its boundary.** `dispatch_communication` already queued the letter, caught
  the refusal and answered `queued: false` with `tracks: "OQ-376"` at HEAD; wave L added
  `give_connection_kind()`, which raises naming the question and says why `notice` is wrong.
* **`L4` — BUILT, AND THE DESKTOP HALF LANDED 2026-09-05.** The phone's offline queue (a
  fifth IndexedDB store, DB_VERSION 1 → 2, an additive upgrade), the close pane at
  `jobs/:orderId/close`, the marker's *N jobs to send* counted in JOBS, and the sync
  client. **`HELD_PANES` is now EMPTY** and the phone holds nothing back.
  ⚠ **THE DESKTOP HALF IS NOW BUILT AND WALKED** (the wave-L leftovers lane): the
  walkthrough CLICKS `Work-009`'s eye, arrives at the `Work-003` drawer, reads *Nobody has
  accepted this yet*, presses **Mark complete**, and the job leaves the queue while the
  day's other two stay on it. **`Work-003` gained a section it did not have** — *What this
  acceptance did*, with the service state and **the letter as refused with its reason** —
  because `WorkOrderAcceptResult`'s own docstring had demanded exactly that in capitals
  since 2026-09-04 and no screen obeyed it (hard-won law 1, with the comment in a type).
  ⚠ **THERE IS NO “Customer › Messages” SCREEN IN THIS PRODUCT AND THIS ROW ASSUMED ONE.**
  The staff app has no per-customer message tab; `GET /outbound` is Settings › Notifications'
  platform queue, and the portal's own Messages page is `CWP-053` and is not built. The
  letter is REFUSED, so no message row exists to show on any of them — which is why the
  refusal is reported where the press happens, and the walkthrough pairs that positive with
  the negative that `outbound_messages` holds nothing of kind `connection`.
* **`L5` — BUILT, and the PostgreSQL half is `tests/test_us_wrk_044_sync_pg.py`.**
  ✅ **`J61` AND `J65` ARE ACTIVATED (2026-09-05, the wave-L leftovers lane)** —
  `06-backend/tests/test_j65_offline_day_one_sync.py` (6 cases) and
  `test_j61_connect_field_accept_live.py` (8 cases), green, **each proved RED first
  through pytest**, and both banners removed.
  ⚠ **THEY ARE `.py`, NOT THE `.spec.ts` THIS PLAN NAMES AT LINE 282, AND THAT IS A
  RECORDED DECISION.** No `.spec.ts` exists anywhere in this repository and nothing would
  run one, so writing one would have been a check that cannot fail — and the fourth wave
  running to claim an activation that did not happen. A journey is a claim about what
  upstream leaves in the DATABASE, so the spec lives where that can be asserted. The
  decision log of 2026-09-05 §1 carries the reasoning **and what an activation asserts**,
  so `J60`, `J62`, `J63`, `J66` and `J67` can be done the same way.
  ⚠ **AND THREE OF THE TWO JOURNEYS' BOUNDARIES HAD CLOSED WHILE THEY SAT UNACTIVATED** —
  `OQ-WRK-1492`, `-1494` and `-1496` were all ruled 2026-09-04 and all three journey bodies
  still described their stubs. Amended, dated, BEFORE the specs were written.
* **`L6` — the review-ledger row is written**, five statements in plain English with the
  figures, naming three things the signature does NOT cover.
* **`L7` — BUILT AND RUN, GREEN; EXTENDED 2026-09-05 TO 100 CHECKS.**
  ⚠ **ITS `BR-WRK-057` CHECK WAS PASSING FOR THE WRONG REASON UNTIL THEN.** The fixture
  raised its jobs with no connection, so `dispatch_communication` returned at its FIRST
  guard (`no_connection`) and **never reached the message queue at all**; the assertion is
  an OR and the first half was true for the wrong reason. The jobs now stand on a build as
  well as a meter, `tracks` is asserted to be `OQ-376` by name, and the desktop leg is
  clicked rather than fetched. It also found **`DEF-MET-4101`** — every meter read displays
  ONE DAY EARLY for any tenant west of UTC.
  **The original two runs, for the record:**
  `10-scripts/render-checks/cr070-l-the-offline-day-and-the-read.mjs` walks demo script L on a
  booted stack: a phone at 390×844 with the engine offline, a desktop at 1440. **It found five
  things no unit test could**, all of them recorded in the file itself — a cold `goto()` while
  offline loads nothing (a technician taps; a tap is client-side routing), a zero-requests count
  that passed because the page never loaded, a batch whose close arrived before its safety ticks
  and was refused BY NAME (the server was right), a fixture meter with no unit recorded whose read
  the pipeline refused (`US-WRK-046` TC-5, happening for real), and assertions written against
  column names rather than the keys the endpoint serves.
* **`L8` — DONE, AND THE PHASE-2 LAUNCH IS DECLARED.** Version `2.195.0`, CHANGELOG, decision-log
  row, and the launch — *a dispatcher assigns work to a crew, and the technician works it on a
  phone* — declared on a walkthrough that was actually run rather than on an intention.
* **`L9` — BLOCKED on `OQ-376`, untouched.**

### The exit test, run — the figures it printed

`CR-070` §11's phase-2 exit test, on a phone and a desktop, twice in a row against the same
database:

* **A second sync adds nothing**, asserted as a COUNT COMPARISON and not as an absence of error:
  the approval queue **19 → 19** and the meter's history **4 → 4**, with every one of the nine
  replayed items answering *duplicate* and none accepted. A check that only said *the second sync
  did not throw* would pass over a server that applied everything twice, which is the exact failure
  being ruled out.
* **The close carries the handset's time.** Three jobs closed at `2026-03-15T16:07` reached the
  server on 5 September; all three read `completed_at = 2026-03-15T16:07:00+00:00` on `Work-009` —
  the screen a supervisor actually reads, which is where the column is published.
* **The read lands on the meter, dated to the completion, with its unit:** *1204.000000 · kWh ·
  2026-03-15*, one row added by the acceptance (**4 → 5**), accepted on **2026-09-05** — and the
  walkthrough asserts the two dates DIFFER, so it cannot pass by coincidence.
* **Nothing activated at close:** all three orders `completed`, `accepted_by` NULL, zero meter
  reads until a person accepted.
* **The letter is refused with its reason** and never filed as `notice`.
* **No write left the handset while offline** (0), paired with the positive that the three closes
  were IN the handset's own store (3) — because zero requests is also what a blank page looks like.

**Rollback, stated before shipping (`13-change-process` step 8):** **hide and keep.**
Photographs, signatures and receipts are EVIDENCE — a technician's account of a job somebody
may dispute months later — so nothing this wave wrote is ever deleted to undo it. Taking it
back means unmounting `jobs/:orderId/close` and putting its row back in `HELD_PANES`
(the machinery is kept, empty, for exactly this), and refusing `POST …/sync` at the route.
The receipts, the attachments and the signatures stay where they are.


**Goal:** a technician works three jobs with no signal and closes them; the phone syncs once at 17:40 and a second
sync adds nothing — proved on PostgreSQL; the supervisor accepts, and the reading D. Ortiz typed is a meter read
written by metering's own door, dated to the completion, with its unit; the service reads *Activated*; the letter
is queued and refused with its reason.
**Stories:** US-WRK-044 · US-WRK-045 · US-WRK-046 · US-WRK-035 ⚠
**Depends on:** J (the phone, the server safety gate) · K (attachments, readings) · B (accept). **Blocked by:**
`OQ-376` bounds the letter's send only.
**Version:** next free `<change>`. **Size:** two people, two weeks.

| Task | r11 | What it touches | Stories · rules | Depends on | Design xref | Size |
|---|---|---|---|---|---|---|
| **L1** | 2a | **`POST /work/mobile/jobs/{id}/sync`** (`07-endpoints.md` #90): a batch of captured items **in capture order**, each with its key; `work_sync_receipts` (key unique · order · kind · accepted_at) + **`work/000N_rls_force`** 🔒; **a SAVEPOINT per item — a nested `transaction.atomic()` — with law 14's comment in the code** so a refused item does not poison the rest; per-item results, never a boolean; safety ticks applied before the close they gate; **the close inside it is `submit_field_result` and nothing more** (`BR-WRK-041`) — it activates nothing. `WM-36` and `WM-38`'s cards are unread (`US-WRK-044`/`045` say so); nothing past `WS-10`, `WS-12`, §3 steps 10–14 and #90 is built | 044 · 045 · `BR-WRK-041` · `042` · `BR-MET-110` · law 14 | J1 · K1 | `WM-36` · `WM-38` (unread) | L |
| **L2** | 2a 🔒 | **`apps/work/seams/metering_seam.py` — the one door** (`BR-WRK-003`): on `accept_field_result`, every `work_order_readings` row with `posts_as_meter_read` posts through **metering's existing event-read door** (`connections.py:2158–2203`, `field_data.set_reads` → `set_reads_posted`) **with its `unit`, dated to the order's completion, never to the acceptance**; a reading with no unit is refused before it reaches metering; **if metering's door takes no unit, that is metering's story — filed, not worked around** (`03-field-map.md` D-13). Flagged `HUMAN-OWNED` + `HUMAN-REVIEW-PENDING`; on the guard list since A2 | 046 · `BR-WRK-003` · `015` · hard rule 3 · CLAUDE.md 🔒 | K1 · B1 | `WM-29` · `WS-16` | M |
| **L3** | 2a | **The letter, to its boundary** (`US-WRK-035`): accept queues *your service is live* through `notifications.queue_document`, catches `QueueWriteRefused` (`notifications/services.py:428`) and returns `queued: False` with the platform's own sentence and `tracks: "OQ-376"` — **never `notice`, never a stamp on a send that did not happen**; the `SOURCE_TYPES` constant (`models.py:338`) is **ten kinds at HEAD, not the register row's eight** — the staleness filed as a defect with the story; `give_connection_kind()` raises naming `OQ-376` | 035 · `BR-WRK-057` · `BR-MET-115` · law 13 | B1 | `WM-27` | S |
| **L4** | 2b | **`Work-012`'s close** — *Close job* online, *Close job · send when back online* offline; the offline queue's marker *3 jobs to send*; sync once and the marker clears; **`Work-003` / `Work-009`** read *Nobody has accepted this yet* → Accept → *Passed · 1 day* gone from the queue; Customer › Messages shows the letter **refused with its reason**, not sent; the meter's history shows the read dated to the completion. Every file on the migrated list | 045 · 044 · 046 · 035 · `BR-WRK-041` · `036` · B14 rules 31 · 32 · g15 | L1–L3 · K2 | `WS-12` (undrawn) · `Work-003` · `Work-009` | M |
| **L5** | 2c | `US-WRK-044` TC-1..7 — **on PostgreSQL in a `*_pg.py`**: a duplicate key inside a batch does not poison the rest (the `DEF-2444` pattern); a second sync adds nothing; the safety tick lands before the close · `045` TC-1..7 (the close is one call and activates nothing) · `046` TC-1..7 (**metering-side:** the `meter_reads` row carries the unit and the completion date; a reading with no unit is refused; `posts_as_meter_read = false` posts nothing; accepting twice does nothing) · `035` TC-1..5 (the refusal, the marker, no `notice`). **Journeys `J61` (extends `J27`) and `J65` activated** — specs written and green, banners removed | 044 · 045 · 046 · 035 | L1–L4 | — | L |
| **L6** | review | **Review-ledger row for `metering_seam.py`** 🔒, plain English with the figure: *D. Ortiz types 1,204 kWh at 16:07 on 15 March; M. Torres accepts at 09:12 on 16 March; the meter's history shows 1,204 kWh dated 15 March, not 16 — and it got there through the same door every meter read uses; a number typed without kWh beside it never reaches the meter at all*. Plus the RLS row for the receipts table | 046 · 044 · CLAUDE.md 🔒 · HUMAN-GUIDE §6 | L2 · L1 | — | S |
| **L7** | 2d | **`cr070-l-the-offline-day-and-the-read.mjs`** (`J65` then `J61`) — phone context with `setOffline(true)` from 08:12: three jobs worked and closed, nine photographs, one out-of-range reading; the marker reads *3 jobs to send*; `setOffline(false)` at 17:40 → sync → three completed orders, nine `work_order_photo` rows, receipts for every item; sync again → nothing added (row counts equal) · desktop: `Work-009` shows the three → open one → *Nobody has accepted this yet* → Accept → the meter's history has the read dated 15 Mar with *kWh*; the connection reads *Activated*; Customer › Messages: the letter refused, the reason shown · Lone Star's queue empty · screenshots | 044 · 045 · 046 · 035 · `BR-WRK-003` · `041` · `042` · `BR-MET-110` · law 6 · law 14 | L4–L6 | — | S |
| **L8** | doc / version | CHANGELOG · lockstep · TSV · decision-log row · **phase 2 LAUNCH declared** — *a dispatcher assigns work to a crew, and the technician works it on a phone*; rollback stated: **hide and keep — photographs, signatures and receipts are evidence** | — | L7 | — | S |
| **L9** | blocked | **After `OQ-376`:** the `connection` source kind and its template in notifications (a), or the category (b), or the in-app path (c) — and the *your service is live* letter finally leaves. Nothing before, and never as `notice` | 035 · `BR-WRK-057` | a ruling | `BR-MET-115` | — |

**Demo script L (D. Ortiz, then M. Torres):** 1 08:12 — the phone syncs, then the signal goes → 2 three jobs
worked and closed offline; *3 jobs to send* → 3 17:40 — back online, one sync; the marker clears → 4 sync again —
nothing changes → 5 M. Torres: *Awaiting approval* has the three → 6 open `WO-4902` → *Nobody has accepted this
yet* → Accept → 7 the meter's history: *1,204 kWh · 15 Mar* — the day it was read, not the day it was accepted;
the electric service on `CON-26-0129` reads *Activated* → 8 Customer › Messages: the letter was queued and refused,
and the screen says why.
**Exit test (asserts a rule):** `BR-WRK-042` — a second sync adds nothing and a bad item does not poison the batch,
**on PostgreSQL**; `BR-WRK-003` — the read is written by metering's door, dated to completion, with its unit;
`BR-MET-110` — nothing activates at Close, only at Accept; `BR-WRK-057` — the letter is refused, not misfiled.
**This is `CR-070` §11's phase-2 exit test, shown on a phone and a desktop.**

---

### Wave M — rules and doors · phase 2

🏗 **BUILT 2026-09-05 at `2.196.0`.** `M1`, `M2`, `M4`, `M6` and `M8` are done; `M3`
moved to wave `P` before this lane started.
⚠ **`M5`'s FIXTURE AND `M7` ARE DONE — 2026-09-05, `DEF-WRK-4085` CLOSED. THE
DEMO HAS BEEN RUN, AND IT DID NOT ALL PASS.** `work` is a sample-data module
now (`apps/work/sample_data.py`, the seven rules of `WS-26` with six On) and
`assets:seed_sample_aged_meters` seeds `AST-04412`, `AST-04413`, `AST-04414`
past their certification life. On a freshly seeded tenant on real PostgreSQL 16
the script scored **24 of 29 checks**: Rules lists **seven, six On**; the sweep
raises **three** `Meter exchange — residential` orders and the second sweep
raises **none** (`raised: 3` then `raised: 0`, orders 39 → 42 → 42); a rule
switched **Off** raises nothing and drops out of the sweep entirely; the Assets
door offers **7** templates and excludes a restricted one; *Work R5* is gone
from all five surfaces and *Parts in Work →* lands on `/work/parts`.

**The five that failed are three real findings and they are worth more than the
pass would have been:**
  · **`DEF-WRK-4098` (fixed)** — `Work-026` drew **zero** rules for every
    tenant. The endpoint serves `{count, next, previous, results}`; the page
    read `rows`/`total`. `tsc` cannot see a wrong interface, and the page's own
    test never mounted it.
  · **`DEF-WRK-4096` (open, high)** — **four of the five triggers cannot raise
    an order at all**, and the fifth stamps the wrong source, which is why the
    dispatcher reads *Assets* where the demo expects *Asset age rule*.
    `_raise_one` stamps `source = rule.source_module`; `create_work_order`
    validates against `WORK_ORDER_SOURCES`. Every raise-path test in this wave
    used the assets trigger — the one token that is valid in both vocabularies
    by coincidence. `work.orders.source.asset_age_rule` already exists in all
    eleven catalogues.
  · **`DEF-WRK-4097` (open)** — the leak rule matches **98 of ~98** meters, so
    fixing `4096` alone floods every trial tenant.
  · **`DEF-WRK-4099` (open, low)** — the Maintenance-history step and the
    retire pre-tick cannot be demonstrated on this fixture, and neither is a
    product bug: there are **zero** `asset_maintenance` rows on a seeded
    tenant and the column is keyed by DATE, and the retire tick renders on
    **step 2** and only for an *assigned* asset (the seeded `AST-04412` is in
    inventory on purpose — see the fixture constant).

⚠ **THE SCRIPT ITSELF CARRIED THREE VACUOUS ASSERTIONS AND ONE WRONG SELECTOR,
ALL FIXED.** `[].every(...)` is `true`, so it reported *"retire: and it is
ENABLED"* and *"every one of them is a Meter exchange"* as PASSES over empty
sets, and it asked `?tab=meters` for a control that lives on `?tab=inventory`.
**Pair every claim about a set with a positive that the set is not empty.**

⚠ **THE ORIGINAL BLOCKER, FOR THE RECORD (`DEF-WRK-4085`).** The test CODE is written and green — `US-WRK-037` 11 cases,
`US-WRK-038` 7, plus **7 on real PostgreSQL 16 under a NOSUPERUSER role**, which is
where the RLS proof and the SAVEPOINT proof live. What is missing is the DATA: M5's
last clause asks for *AST-04412 and two more meters past certification life; the
drawing's seven rules, six On*, and **`work` is not a sample-data module at all** —
`apps/tenancy/sample_data.py`'s `SAMPLE_MODULES` has no entry for it. Registering one
is a shared-file edit to the framework every tenant's `load_sample_data` runs through,
and this lane reported it rather than making that edit unstudied at the end of a long
session. `cr070-m-rules-and-doors.mjs` is written, asserts the demo script step for
step, and **has not been run** — a demo script nobody has clicked is a plan and not a
proof (hard-won law 6), and its own header says so.
⚠ **`M4` NAMED FOUR DEAD CONTROLS AND THE TREE HAD SEVEN** (`DEF-WRK-4083`): a fourth
checkbox on the retire wizard — which this wave's own demo script names in step 6 —
and two more on the lifecycle tab. All seven are released, because deleting
`assets.flow.workR5` from eleven catalogues forces all seven.
⚠ **THE BEAT ENTRY IS THE PRODUCT'S THIRD SCHEDULED JOB, NOT ITS FIRST.**
`apps/notifications/schedule.py` and `apps/payments/collections_schedule.py` each
install one from `ready()` already, and `config/settings/base.py` declares no
`CELERY_BEAT_SCHEDULE` constant at HEAD or now; `M1` follows that installer rather
than minting a second mechanism for one entry.
⚠ **`work/0020` and `work/0021`, NOT `work/000N`** — wave `L` took `0018`/`0019`
while this lane was building and both lanes computed the next free number correctly.


**Goal:** a rule raises orders overnight with nobody typing them and every one says why it exists; and a clerk
on an asset raises a job through one form that four doors open.
⚠ **THE MOVE-OUT DOOR LEFT THIS WAVE ON 2026-09-04** (`CR-070 §W.10`). It was `M3` here, at the very end of
phase 2, hosted on a wizard step that renders as *skipped* on the ordinary move-out (`DEF-WRK-3725`). It is now
**wave `P`**, in phase 1, beside the other four flows and on the step a clerk actually uses. `US-WRK-039` goes
with it and is widened from one flow to five. **This wave keeps the rules engine and the Assets door and
nothing else moved.**
**Stories:** US-WRK-037 · US-WRK-038
**Depends on:** G (the columns, the source stamp — **whose enum wave `P` already widened to six flow values,
`DEF-WRK-3726`**) · D (published templates, `wot_asset_types`) · A (the anchor). **Runs beside H–L.**
**Blocked by:** nothing.
**Version:** next free `<change>`. **Size:** two people, two weeks.

| Task | r11 | What it touches | Stories · rules | Depends on | Design xref | Size |
|---|---|---|---|---|---|---|
| **M1** | 2a | `work_order_rules` (name · source_module ∈ payments · billing · assets · reads · accounts · trigger_kind · params · template · priority · assignment · notifications · escalation · enabled) + **`work/000N_rls_force`** 🔒; `apps/work/rules.py` — one trigger reader per source module **through the seams** (a final notice expired unpaid; a billing exception unresolved; a meter past its certification life — `assets_seam`; a continuous-flow alarm; an occupancy wizard completed); **`work.rules_sweep` nightly job**, idempotent per (rule, subject), registered in `apps.py` on queue `work` and **a `CELERY_BEAT_SCHEDULE` entry** — the product's first unless `CR-069` wave G landed before it (`config/settings/base.py` has none at HEAD); **a rule that is Off raises nothing**; every rule-raised order stamps `source` and `rule_id`; the *This month* count. Routes `07-endpoints.md` §7 #82–#87 | 037 · `BR-WRK-033` · `024` · `002` | G1 · D2 · A3 | `WM-24` · `WS-26` | L |
| **M2** | 2a | **The Assets door** (`BR-WRK-056`): `POST /work-orders` with `asset_id` (the FK at `connections.py:711–727` that nothing writes), templates filtered by `wot_asset_types`; `apps/assets/**` writes nothing to `work_orders` (A7 stays green); the Maintenance history's Work-order column becomes a **READ** of `work_orders.asset_id` through a selector Work publishes — no column is added to `AssetMaintenance` (`assets/models.py:521` carries `cost` and no work order) | 038 · `BR-WRK-056` · `002` | A4 · D1 | `WM-43` · `WS-28` | M |
| **M3** | — | ⚠ **MOVED TO WAVE `P` ON 2026-09-04 — the task id is kept and NOT reused, so a citation of `M3` still lands on the thing it named.** It read *the Customers door: `disconnect_cases.field_visit` enum, the move-out wizard's step 4 calls Work from the screen, and the move-out completes even if the raise fails*. `CR-070 §W.10` puts the work order into the flow that already owns the moment, so this became **`P3`** (the door, written in customers' own app) and **`P4`** (the panel, on **step 2** rather than step 4 — `DEF-WRK-3725`), and it is widened from move-out alone to all five flows. `VISIT_NOT_SCHEDULED` still keeps its name and its docstring is still amended rather than deleted — that clause survived the move intact | — | — | — | — |
| **M4** | 2b | **`features/work/RulesPage.tsx`** (`Work-026`, W1 per the layouts entry — RULE · SOURCE MODULE · TRIGGER · TEMPLATE RAISED · PRIORITY · THIS MONTH · ENABLED; the *Audit* `ConsequenceBox`) + the **five-step rule builder** sub-screen (Trigger · Assignment logic · Notifications · Reminders & escalation · Review & activate). **`features/assets/RaiseWorkOrderPage.tsx`** (`Work-028`, W6) at `/{tenant}/assets/{assetId}/work-orders/new` — a sibling of `…/maintenance/new`; the `ConsequenceBox` **rewritten by rule 32** (*One work order, not tied to a new connection · for this asset · the Maintenance history gains a work-order reference*); **the four disabled controls come alive** — `RaiseWorkOrderCheckbox` (renamed from `WorkOrderR5Checkbox` by this wave — `DEF-WRK-4125`; `AssetFlowPages.tsx:115`, rendered at `AssetAddWizard.tsx:1017`, `AssetFlowPages.tsx:418`, `:659` and, added here, `AssetRetireWizard.tsx:327`) becomes a live pre-tick that opens the form on save, `AssetInventoryTab.tsx:207`'s *Parts in Work →* links to `Work-025`; **`assets.flow.workR5` deleted from all eleven catalogues**; `AssetDetailPage.tsx`'s Maintenance history reads `WO-4908` where it read a dash. ⚠ **THE `MoveOutWizard` PANEL IS NOT HERE ANY MORE — it is `P4`, on step 2** (`CR-070 §W.10`, `DEF-WRK-3725`); `Work-029`'s drawing is unchanged and is asserted by `P7`. `WorkTabs` gains *Rules*. `screenIds.ts` + `g29` rows (`WRK-06`, `WRK-13`) | 037 · 038 · 039 · `BR-WRK-033` · `055` · `056` · B14 rules 11 · 21 · 31 · 32 · g13 · g15 | M1–M3 | `Work-026` (`wireframes/Work-026.png`) · `Work-028` (`wireframes/Work-028.png`) · `Work-029` (`wireframes/Work-029.png`) · `Work-020` | L |
| **M5** | 2c | `US-WRK-037` TC-1..7 (the sweep is idempotent per (rule, meter); Off raises nothing; the source stamp; Lone Star's assets raise nothing on Brazos Bend) · `038` TC-1..7 (`apps/assets/**` writes nothing to `work_orders` — a grep TC; the four doors post one form; the history column) (⚠ **`039`'s cases moved to `P5` with the story**; `apps/customers/**` writing nothing to `work_orders` is asserted in BOTH waves, because `M2`'s Assets door and `P3`'s four flow doors are two different ways to break it). **Journey `J63` activated** (⚠ `J64` is the move-out visit and is activated by `P5`) — specs written and green, banners removed. Fixture: `AST-04412` and two more meters past certification life; the drawing's seven rules, six On | 037 · 038 · 039 | M1–M4 | — | M |
| **M6** | review | Review-ledger row for the RLS migration 🔒: *a rule belongs to one utility and reads only that utility's payments, bills, meters, reads and accounts through the seams; Brazos Bend's meter-exchange rule raised three orders overnight and none for Lone Star Ridge, proved on PostgreSQL* | 037 · CLAUDE.md 🔒 | M1 | — | S |
| **M7** | 2d | **`cr070-m-rules-and-doors.mjs`** (`J63` + `J64`): Rules lists seven, six *On* · run the sweep (the terminal) → three orders on `Work-007` read *Raised by: Asset age rule* · run it again → none · switch the rule *Off*, run → none · Assets → `AST-04412` → *Raise work order* → the template list holds only templates whose asset types include this one → *Raise work order ✓* → `WO-4908` in the dispatcher with CONNECTION a dash; the Maintenance history reads `WO-4908` · the three checkboxes are enabled and the DOM has no *Work R5* (⚠ **the move-out leg moved to `P7`** — and note it was written here as *step 4 → tick the final read*, which named two different steps at once: the final read is step 2. `DEF-WRK-3725`) · screenshots beside `Work-026.png`, `Work-028.png`, `Work-029.png` | 037 · 038 · 039 · `BR-WRK-033` · `055` · `056` · law 6 | M4 · M5 | — | S |
| **M8** | doc / version | CHANGELOG · lockstep · TSV · decision-log row (the trigger readers per module; the beat entry; `VISIT_NOT_SCHEDULED` kept) | — | M7 | — | S |

**Demo script M (the system, then a clerk):** 1 Work → *Rules* → seven rules, six on → 2 the night's sweep runs
→ three *Meter exchange* orders appear, each *Raised by: Asset age rule* → 3 the next night raises none → 4 Assets →
`AST-04412` → *Raise work order* → only templates for this kind of meter are offered → raise it, unassigned → 5 the
Maintenance history's Work order column reads `WO-4908` where it read a dash → 6 the *Raise a work order* checkbox on
Asset retire is live, and *Work R5* is nowhere. **(Step 7 was Sarah Miller's move-out; it is demo script `P` step 2
now, and on step 2 of the wizard rather than step 4.)**
**Exit test (asserts a rule):** `BR-WRK-033` — Off raises nothing and the sweep is idempotent; `BR-WRK-056` —
`apps/assets/**` writes no `work_orders` row (a grep test and A7's gate). **`BR-WRK-055`'s exit — a flow completes
whether or not the raise succeeds — is wave `P`'s**, across all five flows rather than move-out alone.

---

### Wave N — what it cost, and the report · phase 2

**Goal:** a rate per role, dated; a part issued against a job as used-of-planned with **no count moving**; on
approval a frozen report whose cost lines add up to the total a reader reaches by hand — `42.20 + 96.00 + 0.22 =
138.42`, **and no tax line**; a performance tab that totals the field's cost and carries no arrow into Finance.
**Stories:** US-WRK-050 ⚠ (stock) · US-WRK-051 · US-WRK-053 🔒 · US-WRK-054 ⚠ (posting) · US-WRK-052 (closed by ruling — nothing built)
**Depends on:** C (parts) · F (roles) · H (the materials copy) · K (attachments, signature, document kinds).
**Runs beside L.** ⚠ **BLOCKED BY NOTHING — AMENDED 2026-09-05 (`DEF-WRK-4030`). This line said `OQ-WRK-1490` bounds stock
and `OQ-WRK-1491` bounds the posting; BOTH CLOSED ON 2026-09-04, each to option (a)** — no stock, and cost captured and
posted nowhere. `WM-46` is closed by the PO's ruling and re-opens only through HUMAN-GUIDE §6. **So all three boundaries
are now RULINGS rather than questions, and each absence raises the ruling's own sentence instead of a question id**: a stub
invites a later lane to unblock it, a deliberate absence does not. ⚠ **`N9` IS THEREFORE DEAD FOR TWO OF ITS THREE ITEMS**
— read it before starting it.
⚠ **AND TWO OF THIS WAVE'S FOUR DEPENDENCIES HAD NOT LANDED WHEN IT WAS DISPATCHED (2026-09-05):** `H`'s
`work_order_materials` does not exist, so `PUT …/materials/{mid}/used` has no table to write; and `K`'s three
`stored_documents` kinds do not exist (`03-field-map.md` row 28, 33 → 36), so the report has no document store to be
frozen into. What ships regardless is the row, its lines and its total — `work_order_reports.document_id` is NULLABLE for
exactly this reason and is filled the moment the kind exists.
**Version:** **`2.193.0`, SHIPPED 2026-09-05.** **Size:** two people, two weeks.

✅ **N1 · N2 🔒 · N3 · N5 · N6 DONE.** Four tables and their RLS + freeze migration; `costing.py` with the worked figure `138.42` and the `42.03` counter-case pinned; five routes; `Work-027` and `Work-030` with all eleven catalogues; two review-ledger rows; `G111`. **Isolation and the freeze proved on real PostgreSQL 16** under a non-superuser probe role (`tests/test_us_wrk_053_costing_pg.py`, 9 tests) — the tenant-isolation gate is NOT that evidence, it inherits SQLite and skips 192 of 238 proofs (`DEF-GOV-4024`).
⚠ **AMENDED 2026-09-06 BY THE `K5`/`N7` WALKTHROUGH LANE — THREE OF THESE ARE NOW DONE, AND ONE OF THEM
WAS HIDING A CRITICAL DEFECT.** `PUT …/materials/{mid}/used` **IS BUILT** (`checklist.set_material_used`,
route #75): the stamp below named an OMISSION rather than a question, and every piece of evidence for that was
already written down — the contract has specified row 75 all along, `work_order_materials` exists, `costing.py`
reads `used_qty`, and `sync._apply_material` had been writing that column from the handset since wave `L` with a
docstring asking for the route so it could stop being a second writer. It had already forgotten one rule:
`issued_by` and `issued_at` — this route's own *who* and *when* — were set by neither door, so every part
reported from the field landed with no attribution. Both doors are one writer now.
**`N7`'s walkthrough IS DONE** (`10-scripts/render-checks/cr070-n-what-it-cost.mjs`, green twice), and running it
found `DEF-WRK-4124`: **no report could ever carry a labour line**, so a real order totalled `96.22` against this
wave's signed `138.42`. Two independent causes — `snapshot_labour_rate_at_close()` had NO CALLER anywhere in the
repository, and `minutes_on_site`, which `costing.py` reads, had no column and no writer. `metering/0053` and
the call at the close fix both; `tests/test_us_wrk_051_labour_reaches_the_report.py` goes from an ORDER to a
report so it cannot recur silently. **`N4`'s TC-1/TC-2 are covered by that file end to end.**
⚠ **STILL NOT DONE, AND STILL NOT A DEFERRAL A LATER LANE SHOULD GUESS AT:** the report DOCUMENT — the row, its lines and its frozen total ship, but `document_id` is NULL until wave `K` adds the `work_order_report` kind (`03-field-map.md` row 28, 33 → 36); `Work-032`'s rendered PDF and `Work-025`'s Issue-log SEGMENT (the endpoint and the types ship; the segment is still disabled with its reason); `N4`'s remaining TCs and `N8`'s TSV row.

| Task | r11 | What it touches | Stories · rules | Depends on | Design xref | Size |
|---|---|---|---|---|---|---|
| **N1** | 2a | `labour_rates` (**per ROLE**: hourly · overtime_hourly NULL · overtime_after_hours NULL · effective_from · superseded_on — **append-only, one current per role**; a contractor one rate and a dash) · `part_issues` (signed qty · issued_to · purpose · **`order_ref` plain text by design**) · `work_order_reports` (order · version unique) · `work_order_cost_lines`; `labour_rate_snapshot` and `labour_role` on the order **at close** (`03-field-map.md` §3 row 19); + **`work/000N_rls_force`** 🔒. Routes: `PUT …/materials/{mid}/used` (used-of-planned, who, when — **no on-hand count moves**) · `GET · POST /work/parts/issues` · `GET · POST /work/labour-rates` (a change is a new dated row) · `GET /work/performance?period=` (the four tiles and the by-job-type table, **no posting**) · `GET …/reports`, `GET …/reports/{v}.pdf`. **`post_field_cost_to_ledger()` raises THE RULING SENTENCE — not `OQ-WRK-1491`, which CLOSED on 2026-09-04 (`DEF-WRK-4030`) — and nothing calls it**; A7's gate would refuse a ledger write regardless. ⚠ `PUT …/materials/{mid}/used` IS BUILT (2026-09-06) — `checklist.set_material_used`, the ONE writer of `used_qty`, which `sync._apply_material` now calls | 050 · 051 · 054 · `BR-WRK-020` · `049` · `053` · `004` · hard rules 1 · 2 · 5 · 7 | C1 · F1 · H1 | `WM-45` · `WM-22` · `WM-41` | L |
| **N2** | 2a 🔒 | **`apps/work/costing.py` — `work_order_cost_lines(order)`, the ONE named function** (`BR-WRK-051`): hours booked to **2 decimals** (52 min → `0.87 h`); labour = hours × the role's rate snapshotted at close (`0.87 × 48.5000 = 42.1950` stored, `42.20` shown); a part line = quantity × unit cost (`1 × 96.0000`, `1 × 0.2200`); **the total is the sum of the ROUNDED displayed lines** — `42.20 + 96.00 + 0.22 = 138.42`; **no tax line** (`BR-WRK-052`); one test pins the figure and pins that 4-decimal hours would give `42.03`. **The report** (`BR-WRK-050`): generated **once, by `accept_field_result`, never by completion**, through the document store as `work_order_report` (K1's kind), version 1, frozen; a correction produces `-v2` beside `-v1`; a second Accept produces no second `v1`. Flagged `HUMAN-OWNED` + `HUMAN-REVIEW-PENDING`; on the guard list since A2 | 053 · 051 · `BR-WRK-050` · `051` · `052` · hard rule 2 · CLAUDE.md 🔒 | N1 · K1 · B1 | `WM-47` · `WS-32` | M |
| **N3** | 2b | **`features/work/LabourRatesPage.tsx`** (`Work-030`, W7 per the layouts entry — the ONE screen that shows money at 4 dp, because the stored value is being edited; the footnote; the `ConsequenceBox` *A rate is dated, and a job keeps the rate it was closed at.*) at `…/settings/configure/reference-data/work-labour-rates`. **`Work-025`'s Issue log segment** + the sub-screens *Issue parts* (two steps), *Return entry*, *Part detail* (Overview · Movements · Audit) — **no stock column anywhere**. `Work-008`'s **Parts tab** — used-of-planned with who and when. **`features/work/PerformancePage.tsx`** (`Work-027`, W9): four tiles, the by-job-type table ending in `TotalRow` *Total field cost · 740 · $56,337*, the `ConsequenceBox` **with `CR-028 D3` stripped by rule 32** and **no link, button or note into Finance**. **The report document** (`Work-032`, W8) rendered with **`48.50`** (rule 2 — a customer-facing document), the COST section ending at **`138.42`** with **no tax rows**, the `NoteBar` on `-v2`; `Work-008` lists the versions. **`Work-031` — nothing.** `WorkTabs` gains *Performance*. `screenIds.ts` + `g29` rows (`WRK-11`, `WRK-16`, `WRK-17`, `WRK-18`) | 051 · 050 · 054 · 053 · 052 · `BR-WRK-019` · `020` · `049` · `052` · `053` · B14 rules 21 · 31 · 32 · 34 · g13 · g15 | N1 · N2 · C2 · H2 | `Work-030` (`wireframes/Work-030.png`) · `Work-027` (`Work-027.png`) · `Work-032` (`Work-032.png`, **the two tax lines and `149.84` asserted ABSENT**) · `Work-025` · `Work-031` (drawn, not built) | L |
| **N4** | 2c | `US-WRK-050` TC-1..7 (**TC-5 no on-hand count moves and the absence raises the RULING, not `OQ-WRK-1490` — closed 2026-09-04, `DEF-WRK-4030`**) · `051` TC-1..8 (one current per role; a closed job keeps its rate after a new row; the contractor's dash) · `053` TC-1..9 (**TC-1/TC-2 the worked figure `138.42` and the `42.03` counter-case; TC-3 no tax line; generated once, by Accept; v2 beside v1**) · `054` TC-1..7 (**TC-4 the posting absence raises the RULING, not `OQ-WRK-1491` — closed 2026-09-04, `DEF-WRK-4030`**; the tab carries no Finance link) · **`052` TC-1 — nothing is built:** a grep asserts no `base_includes_field_work`, no `per_work_order`, no `Work-031` route, no tax line in the report renderer. **Journey `J62` activated** (the whole one-off job — its spec written and green, the banner removed). Fixture: Field technician `48.5000` / `72.7500` / 8 h; `WO-4822`'s 52 minutes, `MTR-E1P` and `SEAL-01` used | 050 · 051 · 053 · 054 · 052 | N1–N3 | — | L |
| **N5** | review | **Review-ledger row for `costing.py`** 🔒, plain English with the figure: *52 minutes of a field technician at $48.50 an hour is $42.20 on the report; one meter at $96.00 and one seal at $0.22 make the job $138.42, and that is the sum a reader gets adding the three lines; if the hours were kept to four decimals the labour line would read $42.03 and the column would not add up; there is no tax line because the Product Owner said not to add tax for now*. Plus the RLS row for the four tables | 053 · 051 · CLAUDE.md 🔒 · HUMAN-GUIDE §6 | N2 · N1 | — | S |
| **N6** | gate | Two permanent checks, RED first: **the performance tab and the report carry no route, link or word into Finance** (`BR-WRK-053`, `004`) — RED by adding a `/finance` link to `PerformancePage.tsx`; **no tax on a work order** (`BR-WRK-052`) — `US-WRK-052` TC-1's grep promoted to a gate so a later lane cannot add the flag quietly — RED by adding `per_work_order` to the tax frequencies. Registered the same commit | 054 · 052 · `BR-WRK-052` · `053` · law 7 | N2 · N3 | — | S |
| **N7** | 2d | **`cr070-n-what-it-cost.mjs`** (`J62`'s tail): Settings → Labour rates reads `48.5000` and the footnote · Parts → *Issue parts* → `MTR-E1P` against `WO-4822` → the issue log has the row and **no count anywhere changed** · `WO-4822` closed *Passed* after 52 minutes → Accept → `WO-4822-v1.pdf` opens: *0.87 h · 48.50 · 42.20*, *96.00*, *0.22*, **Total 138.42**, and **no line contains the word tax** · Accept again → still one version · Performance: the Leak investigation row moved by one; the page has **no link to Finance**; the box carries no `CR-028` · in the terminal: `journal_lines` row count unchanged · screenshots beside `Work-030.png`, `Work-027.png`, `Work-032.png` | 050 · 051 · 053 · 054 · 052 · `BR-WRK-004` · `049` · `050` · `051` · `052` · `053` · law 6 | N3–N6 | — | S |
| **N8** | doc / version | CHANGELOG · lockstep · TSV · decision-log row (the hours-at-2-dp judgment already logged 2026-09-03 is cited, not repeated) | — | N7 | — | S |
| **N9** | ⚠ **MOSTLY DEAD** | ⚠ **AMENDED 2026-09-05 (`DEF-WRK-4030`) — TWO OF THESE THREE WILL NEVER HAPPEN.** It read *after `OQ-WRK-1491`, the posting … after `OQ-WRK-1490`, stock against issues*. **Both questions CLOSED on 2026-09-04, each to option (a):** there is no posting to build and no stock to build, ever, and each is now a deliberate absence rather than a task waiting on a ruling. What survives is the third clause unchanged: **tax only through HUMAN-GUIDE §6** — not a task any lane can start. Re-opening either of the other two is a change request through `13-change-process.md`, not the arrival of an answer | 054 · 050 · 052 · `BR-WRK-004` · `052` | a re-sign, and nothing else | `WM-41` · `WM-46` | — |

**Demo script N (Alex Reed, then M. Torres):** 1 Settings → Labour rates: *Field technician · 48.5000 · 72.7500 ·
8 h / day* → 2 Work → Parts → *Issue parts*: one `MTR-E1P` to D. Ortiz for `WO-4822` → the log shows it; nothing
counts down → 3 `WO-4822` comes back *Passed*, 52 minutes on site → 4 Accept → 5 the report: three cost lines and
a total of **$138.42**, no tax → 6 Accept again — still `-v1`, nothing new → 7 Performance: `$56,337` at the foot,
and no way from here into Finance.
**Exit test (asserts a rule):** `BR-WRK-051` — the total is the sum of the rounded lines and the test pins `138.42`
against `42.03`; `BR-WRK-050` — generated once, by Accept, frozen; `BR-WRK-052` — no tax line, and the gate goes RED
if one is added; `BR-WRK-004` — `journal_lines` is untouched. **Phase 2 closes when F–N are done: thirty-six stories.**

## 4 · Critical path, and what runs in parallel on day one

⚠ **AMENDED 2026-09-04 FOR THE RE-HOSTING (§0c). Waves `A`, `B` and `C` ARE LANDED** — `2.130.0`, `2.136.0` and
`2.134.0` — so the spines below are history for their first third and are kept because a later wave still cites
them. **What remains, in order: `O` → `D` → `E` → `P` → then `F`–`N` on the phase-2 spine.**

**`O` IS THE ONE THING THAT MUST GO FIRST, and it is worth saying why in one sentence:** four later waves put
something on a screen — `I` shows a build on hold, `G` links a `CONNECTION` cell, `M` shows a maintenance
history, `P` shows a raised job — and until `O` lands, the only screen any of them can point at is the one the
Product Owner retired. **Adds about one and a half weeks to the front of the remaining work** and takes the same
amount out of `I`, `G` and `M` three times over.

**`P` NEEDS `E`, NOT THE OTHER WAY ROUND.** `P2` reuses `E2`'s proposal reader; writing `P` first would mean
writing that reader twice and then deleting one.

**To the phase-0 launch (a clerk raises, holds, cancels and closes a job):** `A1 → A3 → A4 → A5 → A8` then
`B1 → B3 → B5`. **A then B, in series: about three and a half weeks with two people.** The launch sentence is true
at **B5**, on a deployed build.

**To the phase-1 launch (a utility authors its templates and the wizard proposes them):** `A → C → D → E`. C needs
only A3 (the app exists), so it starts the day A3 lands and runs beside B; D needs C's lookups and the §16 reading;
E needs D's service. **About seven and a half weeks along that spine.**

**To the phase-2 launch (a dispatcher assigns, a technician works it on a phone):** `A → C → F → G → H → J → K → L`.
F needs C's skills; G needs F's technicians and C's priorities; H needs G's columns and D's child tables; J needs
H's copies and F's role; K needs J's phone and H's readings copy; L needs J and K. **About fourteen and a half weeks
along the spine with two people per wave**, with B, D, E, I, M and N off it.

**Everything else is off the spine and can be parallel:** **D and E** run beside F and G (they share only C);
**I** starts the day G lands and runs beside H; **M** starts once G and D have landed and runs beside H–L; **N**
starts once K has landed (it needs the document kinds and the signature) and runs beside L. B runs beside C.

**Day one, three lanes can start at once:**

1. **Lane 1 — A1 → A3 → A4** (the brief and the module map in the migration's commit; the app, its five seams and
   the minimal list; `metering/0044` and the anchor CHECK on PostgreSQL).
2. **Lane 2 — A2 and A7** (the migrated-list lines, the two guard-list globs, the CI step for `*_pg.py`; the boundary
   gate proven RED), then **A5** (the shell and the Orders tab) once A3 lands.
3. **Lane 3 — C1** (the six lookups and the RLS migration — none needs the column) the moment A3's `apps/work/`
   exists, which is day one or two.

**The four things that gate a later wave and can be done early:** the **reading of the blueprint's §16** (the
phase-1 lane, before `work/000N` — it settles 23-vs-25 tables and where the six existing models live); **F2**
(identity's companion — the permission, the role, the surface scope — is identity's own migration and can be
written the day F opens); the **`celery-work` worker** (J1's compose service is a copy of `celery-billing` with
G59's clauses and can be prepared beside G); and the **journey specs** (`J60`–`J67`'s files landed at `d0cf0b00`, each *NOT ACTIVATED*;
a lane can write a spec ahead of its wave and leave the banner until the build makes it pass). ⚠ **Nothing here goes back to the PO.** The eight questions are in
the register with their worked cases and their *what is built meanwhile*; law 13 says the repo is where an answer
lives, and every blocked task in §5 waits for a ruling to ARRIVE, not for a lane to ask.

**Where this sits against `12-governance/19-execution-sequence.md` — proposed, not decided here** (that file says
*"if the order changes, say who changed it and why, in the log"*): the go-live path's step for putting a customer's
service live is what phase 0 makes honest (the queue, the acceptance across every connection) and phase 2
completes (the phone, the read that posts); phase 1 is what `BR-MET-109` has been waiting for since 2026-08-25 and
needs no other step to move; the real utility going live on the fire service (`CR-063`) raises no field work in
its first month and does not wait on any of this. **So the proposal is: phase 0 immediately — two weeks of work
that unblocks a real record nobody can write today; phase 1 beside whatever the sequence file runs next; phase 2
when a utility with a crew is named.** An argument for the log, not a change to the sequence file.

## 5 · Blocked — and what each still demonstrates

The story index says **four blocked and six with one branch stubbed**. Read against the frontmatter, **four
stories carry `status: blocked`** (`022`, `023`, `035`, `052`) and **six are `ready` with one branch stubbed and
named** (`010`, `021`, `031`, `048`, `050`, `054`); the ten are these, and every one ends its wave with a
demonstration of the boundary — the stub, the sentence on the screen, the test that asserts the raise.

| Story | Wave | Waits on | What is demonstrated anyway |
|---|---|---|---|
| `US-WRK-022` who may accept | F | `OQ-WRK-1492` | `work_accept` declared and held by no role; a clerk's Accept succeeds today and the log says the mapping is unruled; the refusal test marked expected-to-fail, naming the question |
| `US-WRK-023` the field technician's login | F | `OQ-WRK-1494` | the role exists and holds no staff permission; T. Osei is invited *Field technician · Work (mobile only)*; the web lets her in and logs it once; the phone never waits |
| `US-WRK-035` the connection letter | L | `OQ-376` — the send only | the letter is queued from Accept, refused with the platform's own sentence and `tracks: OQ-376`; never sent as `notice`; the stale *eight kinds* count filed |
| `US-WRK-052` tax on a work order | N | **a PO ruling, not a question** — re-opens only through HUMAN-GUIDE §6 | nothing is built, and a test plus a gate prove it: no flag, no frequency, no `Work-031`, no tax line, `138.42` not `149.84` |
| `US-WRK-010` the parts register (ready) | C | `OQ-WRK-1490` bounds stock | the register with unit cost at 4 dp shown 2; the payload asserted by name to carry no stock key; `stock_position()` raises |
| `US-WRK-021` crews and the watch (ready) | F | `OQ-WRK-1493` bounds the block | the watch with its dates and the count of template types naming the certification; *blocked from* not rendered; the one refusing branch raises |
| `US-WRK-031` the edit screen (ready) | I | ⚠ **NOTHING — `OQ-WRK-1495` CLOSED 2026-09-04** (this cell said it bounded the message until 2026-09-05) | every field change audited; the Change effects box names the real send — *Customer notification — the customer is told the visit moved*; the response carries the queued `appointment` row |
| `US-WRK-048` three document kinds (ready) | K | `OQ-WRK-1496` bounds retention | upload, rows, the four-hour link, the resize; no period named anywhere; `retention_policy()` raises |
| `US-WRK-050` parts against a job (ready) | N | `OQ-WRK-1490` bounds stock | used-of-planned with who and when; no count moves; the issue log |
| `US-WRK-054` the performance tab (ready) | N | `OQ-WRK-1491` bounds the posting | the four tiles and the table with its total; no link into Finance; `post_field_cost_to_ledger()` raises and nothing calls it |

**Six tasks wait for a ruling before they can start** — `C7`, `F8`, `I6`, `K7`, `L9`, `N9` — and every other task
in those waves builds and demonstrates the boundary. **`OQ-WRK-1497`** (what a dispatch batch is) blocks nothing:
the series stays on the Numbering screen and C3's test asserts that nothing allocates from it.

**Not ours to decide, and not decided here:** where the six existing models live (`03-field-map.md` §4 — the
phase-1 lane's call after reading §16, recorded in the log); whether a `Work-` number ever renders on screen
(`BR-WRK-005`, unruled — nothing renders one); the `g29` badges for the screens r10 does not draw (minted by the
lane in that file's own shape, as B3 says).

## 6 · Closing table — every story, its wave, its phase

| Story | Wave | Phase | Story | Wave | Phase |
|---|---|---|---|---|---|
| US-WRK-001 the anchor · `connection_id` nullable | A | 0 | US-WRK-028 the New order wizard | H | 2 |
| US-WRK-002 fourteen writers mounted | B | 0 | US-WRK-029 the map | I | 2 |
| US-WRK-003 the approval queue | B | 0 | US-WRK-030 push to the phone | J | 2 |
| US-WRK-004 the two screens no card covers | A | 0 | US-WRK-031 the edit screen ⚠ | I | 2 |
| US-WRK-005 `apps/work/`, seams, the boundary gate | A | 0 | US-WRK-032 the order's own copies | H | 2 |
| US-WRK-006 the fixture (grows under every `2c`) | A | 0 → 2 | US-WRK-033 the six-tab detail | H | 2 |
| US-WRK-007 work order types | C | 1 | US-WRK-034 the failed-outcome chain | I | 2 |
| US-WRK-008 priorities with SLA | C | 1 | US-WRK-035 the connection letter ⚠ | L | 2 |
| US-WRK-009 the three parked cards | C | 1 | US-WRK-036 attachments and the signature | K | 2 |
| US-WRK-010 the parts register ⚠ | C | 1 | US-WRK-037 rules that raise orders | M | 2 |
| US-WRK-011 the Area filter | G | 2 | US-WRK-038 the Assets door | M | 2 |
| US-WRK-012 the four cards and four series | C | 1 | US-WRK-039 the five flow doors (was *the Customers door*, wave M) | **P** | **1** |
| US-WRK-013 header columns, the relaxed key | D | 1 | US-WRK-040 the phone shell | J | 2 |
| US-WRK-014 the seven child tables | D | 1 | US-WRK-041 today's jobs | J | 2 |
| US-WRK-015 the template write service | D | 1 | US-WRK-042 the job on the phone | J | 2 |
| US-WRK-016 the eight-step builder | E | 1 | US-WRK-043 the safety gate, both sides | J | 2 |
| US-WRK-017 step 6 proposes | E | 1 | US-WRK-044 offline capture and sync | L | 2 |
| US-WRK-018 template versions (TC-3 lands in H) | D | 1 | US-WRK-045 the close from the phone | L | 2 |
| US-WRK-019 the starters become bundles + the gate | E | 1 | US-WRK-046 readings that post 🔒 | L | 2 |
| US-WRK-020 crews, technicians, skills | F | 2 | US-WRK-047 out-of-range flags | K | 2 |
| US-WRK-021 the crews screen, the watch ⚠ | F | 2 | US-WRK-048 three document kinds ⚠ | K | 2 |
| US-WRK-022 who may accept ⚠ | F | 2 | US-WRK-049 the photograph's two columns | K | 2 |
| US-WRK-023 the field technician's login ⚠ | F | 2 | US-WRK-050 parts against a job ⚠ | N | 2 |
| US-WRK-024 the twelve dispatch columns | G | 2 | US-WRK-051 labour rates | N | 2 |
| US-WRK-025 append-only assignment | G | 2 | US-WRK-052 tax — NOT BUILT | N | 2 |
| US-WRK-026 one list, six filters | G | 2 | US-WRK-053 the report 🔒 | N | 2 |
| US-WRK-027 the dispatcher screen | G | 2 | US-WRK-054 the performance tab ⚠ | N | 2 |

**Counts:** 3 phases · 14 waves · 105 tasks (6 of them blocked until a ruling — `C7`, `F8`, `I6`, `K7`, `L9`, `N9`;
every other task in a blocked wave builds and demonstrates the boundary) · 54 stories placed once each · 14
walkthrough scripts · 8 journeys activated (`J60`–`J67`, whose files landed at `d0cf0b00` while this plan was being written; `J61` extends `J27`) · 9 waves creating tables, each with a 🔒
RLS migration and a ledger row · 2 more 🔒 files (`metering_seam.py`, `costing.py`) · 3 new components
(`SegmentedControl` in C, `EditableTable` in E, `Thumbnail` in K) · 4 new gates (the boundary, every-seeded-row-read,
the `work` queue pair, the safety gate server-side) and 2 permanent checks in N.

## 7 · The coverage check, as run over this file

Run 2026-09-03 with `scratchpad/cr070/check_plan.py`, a sixty-line script that reads this file's `### Wave` headings, their
`**Stories:**` lines and their task rows, and writes the TSV rows for `20-wave-tasks.tsv` (anyone can re-derive it from the
two regexes it uses: `^### Wave ([A-Z]) —` and `^\| \*\*([A-Z])(\d+)\*\* \|`; a task whose r11 column reads `blocked` is
a `blocked` row, every other task `open`):

⚠ **THE BLOCK BELOW IS THE 2026-09-03 RUN AND IT IS KEPT AS THE RECORD OF WHAT WAS CHECKED THEN.** The
re-hosting of 2026-09-04 (§0c) adds two waves and moves one story, so the numbers a lane should hold in its
head are the ones in the second block. **The script is unchanged and its two regexes still read this file**;
re-run it and it prints the second block.

```
waves: 14 (ABCDEFGHIJKLMN)
tasks: 105  per wave: A=9 B=6 C=7 D=7 E=8 F=8 G=7 H=6 I=6 J=8 K=7 L=9 M=8 N=9
tasks blocked until a ruling: 6 (C7, F8, I6, K7, L9, N9)
stories US-WRK-001..054 placed exactly once: YES (54/54)
placement: A=[001,004,005,006] B=[002,003] C=[007,008,009,010,012] D=[013,014,015,018] E=[016,017,019] F=[020,021,022,023] G=[011,024,025,026,027] H=[028,032,033] I=[029,031,034] J=[030,040,041,042,043] K=[036,047,048,049] L=[035,044,045,046] M=[037,038,039] N=[050,051,052,053,054]
every wave names its 2d walkthrough: YES
TSV rows written: 105 -> cr070/wave-tasks.tsv
RESULT: PASS
```

**After the re-hosting of 2026-09-04, and this is the live count:**

```
waves: 16 (ABCDEFGHIJKLMNOP)   running order: A B C | O D E P | F G H I J K L M N
waves landed: 3 (A=2.130.0, B=2.136.0, C=2.134.0)   waves remaining: 13
tasks: 121  per wave: A=9 B=6 C=7 D=7 E=8 F=8 G=7 H=6 I=6 J=8 K=7 L=8 M=7 N=9 O=8 P=8
  (M loses M3 to P and M5's 039 cases with it; L is unchanged at 9 minus none - see note)
tasks blocked until a ruling: 6 (C7, F8, I6, K7, L9, N9)   - unchanged, and O and P add none
stories US-WRK-001..054 placed exactly once: YES (54/54)
moved: US-WRK-039 M -> P (phase 2 -> phase 1), widened from move-out to five flows
re-hosted: US-WRK-002 and 004 gain wave O beside their landed wave B / wave A work
waves naming NCT-02 or /connections/<uuid> as a host: 0 (was 2 - B3 shipped, I demo step 6)
waves hosted on an existing product flow: 6 (E new connect, P x4 + reconnect, M assets)
tables changed by the re-hosting: 0    migrations: 0    data migrated: 0
every wave names its 2d walkthrough: YES (16 scripts; cr070-o and cr070-p are the new two)
RESULT: PASS
```

⚠ **THE TASK TOTAL IS 121 AND NOT 105 + 16.** `M3` is MOVED rather than deleted — its row is kept in place as a
pointer so a citation of `M3` still lands on the thing it named — and it is counted once, in `P`. Anyone
re-deriving this from the two regexes will read `M3`'s row and should read its text: the r11 column is `—`,
which is the marker for a task that has gone somewhere.
