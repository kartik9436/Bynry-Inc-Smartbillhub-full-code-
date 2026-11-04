# Meter Reads blueprint — the rulings, and a verdict on all 53 specifications

**What this file is.** The output of MEASURE LANE D, step 1 of `CR-096-BRC02`. It reads
the blueprint's back sections — 05 to 10 and the appendices, PDF pages 61–114 — and does
two things and nothing else:

1. **Transcribes every PO ruling of 2026-09-12 and 2026-09-13 that exists in no file of
   this repository**, verbatim, with its date and what it reverses, ready for the
   coordinator to write into the shared registers.
2. **Gives every one of the 53 `MR-##` specifications a verdict against THIS branch's
   code** — the register ships them all at `Unverified`, and the document was read at
   `2.237.10` while the branch is `2.261.3`.

⚠ **NOTHING HERE IS WRITTEN INTO A SHARED REGISTER, AND NOTHING IS BUILT.** No id is
allocated. `12-governance/02-decision-log.md`, `01-open-questions.md`, the defect log and
the module's `02-business-rules.md` are the coordinator's to write; this file is the
transcript they write from.

**Method.** Sections 01 and 09 were read **as images** at scale 4 per B14 rule 42
(`10-scripts/pdf/pdf_render.py /tmp/reads.pdf /tmp/readsD 4 4,5,6,7` and `… 75,76,77,78,79,80,81`);
the text layer was used only as an index. Every verdict below names the file and line
that decided it.

| | |
|---|---|
| Document read at | `2.237.10` · commit `3706b459` · 2026-09-12 |
| Measured against | `claude/hi-0jmv62` @ `965fd6e6` · `07-frontend/package.json` **`2.261.3`** |
| `check_head_current.sh` | **PASS** — HEAD is the tip of `origin/claude/hi-0jmv62` (`7b1dc74f` at session start) |

---

## Part 1 · The rulings that exist nowhere else

### 1.1 · The table, transcribed — and it holds NINE rows, not thirteen

Pages 4–7, read as images at scale 4. The table has fourteen rows: five carry a green
"Also in the repo?" chip and **nine carry `NOWHERE`**. Those nine are transcribed verbatim
below.

⚠ **THE DOCUMENT'S OWN HEADING SAYS THIRTEEN AND ITS TABLE SHOWS NINE.** The heading reads
*"Thirteen PO rulings of 12–13 September exist in this document and in no file of the
repository"*, and `MR-53` repeats the figure. Counting quoted strings rather than rows
gives ten (row 3 carries two quotes). **The remaining rulings of those two days are quoted
in the document's BODY and never reach the table** — §1.2 lists them. This is reported
rather than reconciled: a count that does not match its own table is a finding, and
inventing four rows to make thirteen would be worse than saying so.

**Verified absent from this repository.** Every quoted phrase below was grepped across
`12-governance/` and `04-docs/` (excluding this blueprint folder): **zero hits for all
nine.** The decision log carries 120 rows dated 2026-09-12/13 and not one of them is a
Meter Reads ruling.

| # | Date | Ruling, verbatim | Kind | Where it belongs |
|---|---|---|---|---|
| **R1** | **2026-09-12** | *"Need Attention — does not add any value"* | **REVERSES A SIGNED RULE** | **CHANGE REQUEST** — `CR-096-BRC02` §2. Supersedes **`BR-MET-060`** (*"Reads screen opens on Needs attention (Missing/Flagged/Disputed KPI chips + drill-in); full list one tab away"*, source PO RD-12, status **CONFIRMED** in `02-business-rules.md` today) and retires **`US-MET-019`**. Also touches `BR-MET-132`, whose own text cites *"US-MET-019 §5"* |
| **R2** | **2026-09-12** | *"we should say Read Cycles and within that we should show Routes and their completion"* | **REVERSES A SIGNED RULE** | **CHANGE REQUEST** — retires Routes as a screen. Collides with **`BR-MET-011`** (*"S26/S27 are read-only operational views; all CRUD in Settings"*, **CONFIRMED** PO closure batch 2026-08-08) and with A1's screen ids **S26** and **S27**, which `screenIds.ts:913-914` still registers as two addresses |
| **R3** | **2026-09-12** | *"we will need a list view of read cycles"* · *"and a detail view"* | **NEW RULE** | `04-docs/05-modules/04-metering/02-business-rules.md`. Two quoted strings, one table row. No signed rule says Reads may not have these; it is an addition, not a reversal |
| **R4** | **2026-09-12** | *"in detail section use Panel to information groups"* | **NEW RULE — and it is PRODUCT-WIDE, not Meter Reads'** | `04-docs/02-decisions/14-ui-conventions.md` (**B14**), because it governs every detail screen in the product. The document's fuller quote (p91) is *"use Panel — a box, 1px border on all four sides, surface fill, 16px padding, heading inside … in detail section use Panel to information groups"*. ⚠ **It changes the product, not a drawing**: `ReadDetailPage.tsx:139` renders the OTHER container (`border-t border-divider pt-3.5`) and `<Panel>` is already used 548 times in 127 files, so ratifying this in B14 rather than in a module file is what stops two lanes disagreeing about which container is which |
| **R5** | **2026-09-12** | *"on this screen can you show utility services chip in header"* | **NEW RULE** | `02-business-rules.md` (metering). Scoped to the reading detail's header |
| **R6** | **2026-09-12** | *"just keep the what is final screen"* | **JUDGEMENT — a process ruling** | `12-governance/02-decision-log.md`. It governs how a blueprint is assembled (no as-built/revised twins), not what the product does |
| **R7** | **2026-09-12** | *"write it down in document and not in repo"* | **JUDGEMENT — a process ruling, and it is the CAUSE of all the others being lost** | `12-governance/02-decision-log.md`. ⚠ **The instruction was made about a CODE PATCH and silently took the rulings with it.** `MR-53` waits on the PO lifting it for rulings specifically. Recording it verbatim, with that scope note, is the one thing that stops the next lane repeating this |
| **R8** | **2026-09-13** | *"a details view of Route … similar to details view of Cycle"*, **option A** | **NEW RULE** | `02-business-rules.md` (metering). The document's fuller quote (p89): *"in this Route Tab — what if User click on Route link — we will have to give a details view of Route. this view should be similar to details view of Cycle. in Cycle you will need to add a tab — all reads and same in route details also."* **Option A** = the route page gets **its own address** with the window in the header, rather than nesting under the cycle — because a route can be walked on more than one cycle, so *"0 of 11 collected"* has no denominator until a window is named |
| **R9** | **2026-09-13** | *The walk-reorder question, raised and unanswered* | **NOT A RULING — AN OPEN QUESTION** | `12-governance/01-open-questions.md`, as a new `OQ-MET-nnnn`. The question: **may a clerk reorder a route's walk from Reads, or only from Settings?** `PUT /routes/{id}/premises-order` is served (`api.py:3037`) and `BR-MET-011` puts route configuration in Settings. ⚠ **THE DOCUMENT'S FRAMING IS ALREADY STALE ON THIS BRANCH** — see `MR-44` below: Settings' own `RouteDetailPage.tsx:214` already WRITES the order through `saveRoutePremisesOrder`, so the question is now only about the Reads surface |

### 1.2 · Ten more PO utterances of the same two days, quoted in the body and in no register

Found by reading sections 06, 07 and 10. Each is quoted verbatim in the blueprint and
**none is in this repository either** — so the exposure is larger than the table shows.

| # | Date | Quoted, verbatim | Where in the doc | Kind |
|---|---|---|---|---|
| B1 | 2026-09-12 | *"All reads — all good"* | p82, the four-ruling index | **JUDGEMENT** — decision log. Confirms entry 02 carries over unchanged |
| B2 | 2026-09-12 | *"Write all change in 02, 03 and 04 section only lets not create two places for revised screens."* | p83 | **JUDGEMENT — process.** Decision log. It deleted the document's whole "Drawn answers" section |
| B3 | 2026-09-12 | *"check section 06 absences for missed commitments"* | p63 | **JUDGEMENT — process.** Decision log. It is what found three absences misfiled as out-of-scope on a code comment |
| B4 | 2026-09-12 | *"run all 18"* | p71, the copy budget | **JUDGEMENT.** Decision log — applies B14 rule 33 to seventeen lines across eleven screens |
| B5 | 2026-09-12 | *"commitment chip — not just on screens but all changes that we need to ask Claude Code to do"* | p6, p90 | **NEW RULE — how a blueprint is assembled.** Decision log |
| B6 | 2026-09-12 | *"check all screens once more for missed commitments"* | p90 | **JUDGEMENT — process.** Decision log |
| B7 | 2026-09-12 | *"fix J-01 — that crash is the priority"* | p86 | **JUDGEMENT with a priority.** Decision log. ⚠ **ALREADY SATISFIED** — see `MR-01` |
| B8 | 2026-09-12 | *"highlight these as important items"* | p86 | **JUDGEMENT — process.** Decision log |
| B9 | 2026-09-12 | *"do all these changes"* | p88, the rate-type work | **JUDGEMENT.** Decision log — it is what `MR-45` to `MR-51` were minted from |
| B10 | 2026-09-13 | *"please create screens for Routes 2, Still to read 5, History — I need to see what the details in it"* | p91 | **NEW RULE.** `02-business-rules.md` (metering) — it fixes the cycle page's tab set |

**So nineteen distinct PO utterances of 2026-09-12/13 are quoted in the blueprint and
none of the nineteen is anywhere in this repository.** Three reverse or collide with a
signed rule (R1, R2, and R4 against the read detail's built container); nine are new
rules; six are judgements or process rulings; one (R9) is an open question wearing a
ruling's clothes.

### 1.3 · Two of the three signed rules the rulings reverse are still obeyed in code

Not an inference — read on this branch:

* **`BR-MET-060`** is **CONFIRMED** in `02-business-rules.md` and `ReadsListPage.tsx:24`
  states it verbatim: *"It lands on Needs attention (BR-MET-060), on EVERY open."* The tab
  ids `READS_TAB_ATTENTION` / `READS_TAB_ALL` are both live (`:790`, `:795`).
* **`BR-MET-011`** is **CONFIRMED** and `RoutesCyclesPage.tsx:842` still routes a clerk to
  Settings for CRUD.
* **R4's container**: `ReadDetailPage.tsx:139` renders the top-ruled `SECTION`, not a
  `<Panel>`.

---

## Part 2 · The 53 specifications, with a verdict each

### 2.1 · The count

| Verdict | Count | Which |
|---|---|---|
| **ALREADY DONE** | **1** | MR-01 |
| **PARTLY DONE** | **9** | MR-05 · MR-13 · MR-18 · MR-23 · MR-30 · MR-44 · MR-46 · MR-47 · MR-49 |
| **BLOCKED** | **3** | MR-24 · MR-38 · MR-42 |
| **NOT DONE** | **40** | everything else |

⚠ **THIS IS NOT THE ASSETS SHAPE.** The Assets blueprint found 17 of 24 already built.
Meter Reads finds **one**. The reason is in the document's own structure: Assets' register
was mostly *"show data the server already answers"*, while 17 of these 53 are `NEW BUILD`
and the four largest — MR-28, MR-29, MR-30, MR-44 — are a screen redesign the PO ruled on
2026-09-12/13, **after** the code this branch carries.

**What DID move in the 24 versions is the single worst defect.** `MR-01` — the crash the
PO called *"the priority"* — is fixed, and its fix carries the trap the blueprint spent a
page on (`total` is READ DATES, not rows).

### 2.2 · The table

`Screens` are the document's own entry numbers. `Read` names the file and line that decided
the verdict.

| ID | What it undertakes | Verdict | What I read to decide |
|---|---|---|---|
| **MR-01** | A clerk can open a reading again | **ALREADY DONE** | `api/endpoints.ts:8772` — `getAssetReads` returns `Promise<PagedRows<AssetReadRow>>` through `readListPage`, which **asserts the envelope at runtime**. Its docstring (`:8744-8771`) records the fix, names `DEF-WRK-4119`/`DEF-AST-4120`, and carries MR-01's own trap verbatim: *"`total` is the number of read DATES and not of rows"*. `ReadDetailPage.tsx:469` reads `historyQuery.data?.rows`. The 00-index confirms it by clicking: zero page errors at 1440 |
| **MR-02** | Reach Routes and Cycles without knowing a URL | **NOT DONE** | `AppShell.tsx:225-230` declares `children` for `/reads` — and `:758-769` says in its own words that the rail renders **no submenus** by PO rulings of 2026-08-10, `children` surviving only as BREADCRUMB data. Both screens are routed (`App.tsx:719-720`) and registered (`screenIds.ts:913-914`); `ReadsListPage` has two tabs, neither of them Routes or Cycles. **No gate covers this**: `G100` (every screen has a door) **PASSES over 52 registered PORTAL screens** and reads no staff screen |
| **MR-03** | See which readings are missing, not just how many | **NOT DONE** | `selectors.py:3225` — `READ_FILTERS = ("route","status","cycle","service","source","channel","disputed","asset")`. No `missing`. `api.py:1411` passes exactly that tuple, and an undeclared `f.` param is ignored, so a drill-in would return every read while looking like a slice |
| **MR-04** | Read a batch number in the Batch column | **NOT DONE** | `selectors.read_dict` (`:3595-3735`) serves `"import_batch_id"` and no `batch_no`; `batch_no` exists only at `:5700` and `:7708`, on the batch itself. `ReadsListPage.tsx:637-642` renders `row.import_batch_id` raw. **Violation 7-01 still true** |
| **MR-05** | The reading page survives a failed history read | **PARTLY DONE** | `ReadDetailPage.tsx:321-326` — `historyQuery` has `retry:false`; `:901-902` degrades the history section alone to `metering.read.history.failed` = *"The read history could not be loaded."* and the four figures, math line, flags and stamp all still render. **The Retry control the spec names does not exist** |
| **MR-06** | A clerk with hundreds of routes finds one by typing | **NOT DONE** | `SearchSelectField` appears in **none** of `UploadReadsWizard.tsx`, `ReadsListPage.tsx`, `EstimateReadModal.tsx`, `RoutesCyclesPage.tsx`. **Violation 7-07 still true** |
| **MR-07** | A supervisor sees a window that has closed, as closed | **NOT DONE** | `completeness.py:841` — `"days_left": max((window[1] - today).days, 0)`, so a window shut nine days ago reads **0**. The catalogue has only `metering.cycles.completeness.daysLeft` = *"{{count}} days left"*. The input exists: `current_window` (`:516`) serves a `state` of `open` / `closed_unbilled` / `before_open` |
| **MR-08** | The wizard's grids use the product's own controls | **NOT DONE** | `UploadReadsWizard.tsx:1478-1489` — a raw `<input className="input" type="date">` per row; `:1495-1511` a raw `<select className="input">` per row. `DatePickerField` and `SelectField` are not imported for the grid. **Violations 7-05 and 7-06 still true** |
| **MR-09** | A clerk cannot spend a press on an uncertified commit | **NOT DONE** | `UploadReadsWizard.tsx:3092-3094` — `advanceBlocked` on stage 4 is `committing \|\| writeBlockedReason !== null`, and `writeBlockedReason` (`:2578`) is an **RBAC** gate (`metering.rbac.readOnly`). The certification is checked at `:3012-3014`, **inside `commit()`, after the press**. **Violation 7-02 still true** |
| **MR-10** | Estimate a group of missing readings from the list that names them | **NOT DONE** | `ReadsBulkBar.tsx:293` still records the gap in its own trailer; the chase panel (`RoutesCyclesPage.tsx:320-360`) has no row action, no pager and neither *Estimate these* nor *Send someone out*. `POST /reads/bulk-estimate` is served and called by no screen. **Violation 7-12 still true** |
| **MR-11** | Routes and Cycles page on the server | **NOT DONE** | `RoutesCyclesPage.tsx:403` / `:582` call `getRoutes` / `getCycles`, which are `listAll("/routes")` / `listAll("/cycles")` (`endpoints.ts:2203`, `:2309`); `:480` and `:648` then `pageSlice` in the browser. `getRoutesPage` / `getCyclesPage` exist (`endpoints.ts:2264`, `:2271`) and **neither screen calls either**. **Violation 7-04 still true** |
| **MR-12** | Routes and Cycles get the toolbar every other list has | **NOT DONE** | No search box, filter chips, `+ Filter`, Columns control or sortable header anywhere in `RoutesCyclesPage.tsx`. `ListPager` is the only toolbar element. **Violation 7-03 still true** |
| **MR-13** | One cycle row states one set of numbers | **PARTLY DONE** | `DEF-2730` landed: `:713-718` renames the column to **Meters** and replaces the quotient with BR-MET-057's own, and `:290-296` no longer double-clamps the server's percentage. `:253-264` makes a closed window with nothing expected **say so** rather than print `0 of 0`. **What remains is the adjacency** — `Meters` (meters) beside `Completeness` (registers) — and the code names its own residue: `OQ-1201`, whose status column reads **OPEN — non-blocking** |
| **MR-14** | The estimate dialog stops arguing | **NOT DONE** | `metering.estimate.lede` is the same 25 words: *"When a meter could not be read, this works out the consumption from that meter's own recent actual readings. It never guesses a rate and it never rounds."* **Violation 7-08 still true** |
| **MR-15** | A clerk can correct a billed reading from the reading | **NOT DONE** | `ReadDetailPage.tsx:188-190` — `overrideBlockedReason` returns `metering.read.action.billedLocked` for **every** BILLED read, unconditionally, while `:442-444` renames the primary to *Correct billed read*. `POST /reads/{id}/billed-correction` is served (`api.py:1479`, routed `:3067`). **Not one `.ts`/`.tsx` file calls it.** **Violations 7-13 and section 06's first expired hold still true** |
| **MR-16** | Two screens stop claiming the reads module is unwired | **NOT DONE** | `metering.ops.notCollectedWhy` = *"…The reads module is not wired yet, so this is unknown rather than zero."* is in the catalogue and rendered at `RoutesCyclesPage.tsx:528`. `seams.collected_read_count` (`seams.py:1618-1624`) returns `None` only when `resolve` fails — and `collected_read_count_impl` lives in **`apps/metering/services.py:10243`, the same app**, so it always resolves. **The branch is unreachable and its stated reason is false. Violations 7-14 and the second expired hold still true** |
| **MR-17** | A utility that requires a second pair of eyes can enforce it | **NOT DONE — AND IT IS NOT BLOCKED** | ⚠ **THE BLUEPRINT SAYS *"waits on: a tenant toggle nobody has ruled on"*. SOMEBODY DID.** `OQ-042`'s status column reads **CLOSED** — *"optional toggle default ON; supervisor = SysAdmin/Executive; blocks when enabled (PO R6)"*. The writer is built (`services.py:7994`, `@require_role(SYSTEM_ADMIN, EXECUTIVE)`) and its own comment (`:7987-7992`) says the blocking half was deferred to another lane's screen. ⚠ **AND ITS DEFECT ROW IS CLOSED THE WRONG WAY**: `DEF-815`'s status column reads **`wontfix`**. Building MR-17 means reopening that row — coordinator's call, not mine |
| **MR-18** | Three dead strings leave eleven catalogues | **PARTLY DONE** | `metering.read.device.unitRequired`, `metering.read.generation.requiresDevice` and `metering.read.batch.errorsNeedResolution` are **gone** from `en.json`. `metering.reads.deviceReadNote` = *"A device reading — generation, not consumption. It is never added to usage."* is present in **all eleven** catalogues and rendered by no source file |
| **MR-19** | Last completion shows a date | **NOT DONE** | `RoutesCyclesPage.tsx:536-545` still passes **`withTime`** to `DateCell` for `route.last_completion`. **Violation 7-10 still true.** The identical defect was fixed on the reads list's Read date column — `selectors.read_dict:3623` takes `.date()` with a nine-line comment about `DEF-MET-4101` — and never swept here |
| **MR-20** | The commit button counts in English | **NOT DONE** | `metering.upload.post.commitRows` = *"Commit {{count}} rows ✓"*; `metering.upload.split.line` = *"{{post}} rows will post. {{hold}} will not, and you can download them."*; `metering.upload.split.all` = *"All {{post}} rows will post."*. No singular form, on the button that writes to a financial record. **Violation 7-09 still true** |
| **MR-21** | An empty Routes or Cycles screen says what fills it | **NOT DONE** | `metering.routes.empty` = *"No routes are configured yet."* rendered bare at `RoutesCyclesPage.tsx:460` (and `metering.cycles.empty` at `:696`). No action, no Settings link — which the header offers two lines above at `:842`. **Violation 7-11 still true** |
| **MR-22** | A gate that cannot see a file says so | **NOT DONE — AND THE BLIND SPOT IS NOW TWO ALIASES, NOT ONE** | Verified by running it: **`python3 10-scripts/gates/g96_portal_reads_name_the_tenant.py` prints `PASS: 30 portal file(s) read; every queryset over another module's model names the tenant … except 0 row(s)`** — and prints **no skipped count**. `FOREIGN_MODELS` (`:97-116`) is eleven aliases; `apps/portal/seams/metering_seam.py:310` binds `from apps.metering import models as reads_models` and `:317` runs `reads_models.MeterRead.objects.filter(id__in=wanted)` — **no tenant predicate**, invisible to the gate. `:35` binds `interruption_models`, also absent from the list (that query at `:83` *does* name the tenant, so it is safe and still unseen). ⚠ **This guards CLAUDE.md hard rule 1 and hard-won law 14 is why it matters**: the suite runs on in-memory SQLite, where a tenant-less read is indistinguishable from a scoped one, forever |
| **MR-23** | A client helper cannot claim an array over a paginated endpoint | **PARTLY DONE** | The durable half landed: `api/paginated.ts`'s `readListPage` is the ONE envelope declaration and asserts it at runtime, and **`G114`** refuses a second description of it. **But G114 reads `client.get<{…}>` OBJECT literals only** — it says so in its own output: *"NOT COVERED: 11 file(s) inline a `client.get<{…}>` literal"* — and nothing refuses a `client.get<T[]>` over a paginated path, which is MR-01's exact shape. ⚠ **G114 IS RED RIGHT NOW AND IT IS NOT THIS PASS'S DOING** — see §3.1 |
| **MR-24** | A reading filed on the wrong register can be put right | **BLOCKED — and the question it names is the wrong one** | ⚠ **`OQ-209` IS NOT OPEN.** Its status column reads **CLOSED (CR-038) — RULED 2026-08-26: option (a) CONFIRMED as implemented — PO: *"Never update the value backword"***, and that closure **confirms** migration 0007's trigger freezing the measurement (`channel` included). So the blocker is not an unanswered narrowing; it is that **the four shapes (a)–(d) have never been put to anybody**, and no question exists for them in `01-open-questions.md`. It stays BLOCKED and **a question is owed** |
| **MR-25** | Key a multi-register meter without opening the import wizard | **NOT DONE** | `metering.quickRead.notSimple` = *"This meter has {{count}} registers."* + `notSimpleAction` = *"Use Upload reads to enter all of them."* both live. `QuickReadModal.tsx` still hands off |
| **MR-26** | A clerk lands on the readings instead of on three tiles | **NOT DONE** | `ReadsListPage.tsx:24-27` states the superseded rule in its own words; `READS_TAB_ATTENTION` is the default at `:478` and `:851`; `attentionTiles` (`:395`) and `metering.reads.attention.allClear` are live. **This is R1's build, and R1 is not in the repo** |
| **MR-27** | See which plan a reading belongs to, and find one by address | **NOT DONE** | `ReadsListPage.tsx:289` column label is `metering.reads.col.channel` = **"Channel"**, not Register; `:312` `searchFields: ["meter"]` and `metering.reads.searchPlaceholder` = *"Search meter #…"*, not widened to address; `:303` Batch renders the uuid; there is **no Plan column** and **no Read cycles tab** |
| **MR-28** | Routes stops being a doorless screen and becomes part of the cycle | **NOT DONE** | `/reads/routes` is a live standalone address (`App.tsx:719` → `RoutesOpsPage`); nothing redirects. **This is R2's build** |
| **MR-29** | A person can reach the cycles at all | **NOT DONE** | Same as MR-02. No Read cycles tab; `getCyclesPage` unused |
| **MR-30** | A person can answer for one cycle in one place | **PARTLY DONE — AND IT ALREADY EXISTS IN SETTINGS** | ⚠ **The blueprint calls entry 20 *"a NEW screen"*. A cycle detail page is built and linked.** `features/tenancy/CycleDetailPage.tsx` is routed at `/settings/reference-data/routes-cycles/cycles/{id}` (`routesCyclesShared.tsx:461`) with **five** separately-linkable tabs — schedule · routes · coverage · runs · audit (`:169`, `:337-341`, `:354-380`) — and `RoutesCyclesPage.tsx:727` already links every cycle row to it. **What is missing** is the Reads address, a *Still to read* chase list with the bulk-estimate control, and a History-of-windows tab of the drawn shape. Whoever builds MR-30 should start from this file, not from an empty one |
| **MR-31** | Every helper line on every reads screen fits its purpose | **NOT DONE** | **15 of the 17 lines are verbatim as the document quotes them** — `metering.reads.headsOnlyNote` (14 words, pure rationale), `metering.read.dispute.reasonHelp` (10), `metering.upload.field.cycleHelp` (9, pure rationale), `metering.upload.writeMode.insertConsequence` (16+13, the worst), `metering.ops.derivedNote` (22, pure rationale), `metering.reads.routeSheet.help` (15), and the rest. **Two no longer exist on this branch** — the quick-read pair — and `git log -S` finds neither string ever in `en.json` here, so the document measured a different branch's copy; today's `metering.quickRead.meterHelp` (*"Type the number on the meter, then check it."*) and `valueHelp` (*"The number shown on the meter today."*) are shorter but are **not** the specified replacements. **Violation 7-08 and the copy budget still open** |
| **MR-32** | The reading's information groups become Panels | **NOT DONE** | `ReadDetailPage.tsx:139` — `const SECTION = "flex flex-col gap-1.5 border-t border-divider pt-3.5"`, used for Calculation (`:617`), Flags (`:639`), History (`:899`) and the rest. **No `<Panel>` is imported into the file.** This is R4's build |
| **MR-33** | The reads list's trailer stops lying to the next maintainer | **NOT DONE** | `ReadsListPage.tsx:1202`, and it is false in at least five clauses on this branch: (1) *"FOUR of the prototype's ten S25 columns are NOT rendered … `selectors.read_dict` builds none of them"* — `_read_linkage` (`selectors.py:3508-3541`) builds all four and the file's own header at `:28-32` says so; (2) *"there is NO Download/export control"* — `exports.py:363-371` registers READS with `READ_FILTERS` and `default_dir="desc"`; (3) *"the server IGNORES `dir`"* — `_order` (`selectors.py:111-113`) takes a direction; (4) the Service filter; (5) S29 as a drawer — it is `ReadDetailPage`, a page. **Violation 7-15 still true** |
| **MR-34** | One answer about whether Routes and Cycles paginate | **NOT DONE — AND THE FALSE CLAIMS HAVE DOUBLED** | The blueprint found two. On this branch there are **four**: `RoutesCyclesPage.tsx:853` (*"their endpoints are still unpaginated plain arrays"*), `RoutesCyclesPage.test.tsx:303`, `ListExportButton.tsx:77` and `ListExportButton.tsx:283`. `endpoints.ts:2209-2215` is the one that is right, dated 2026-08-23, and calls the old claim *"hard-won law 1 pointed backwards"*. **Violation 7-16 still true** |
| **MR-35** | No live bound is argued from a ceiling this repository retired | **NOT DONE** | Both cited bounds live: `RoutesCyclesPage.tsx:664` (*"this product is <3,000 connections with a handful of cycles"*) and `completeness.py:894` (*"Bounded by the cycle's own membership (<3,000 connections …)"*). **Violation 7-17 still true.** The ICP ceiling moved to 40,000 on 2026-09-06 |
| **MR-36** | A file appears once in the migration list | **NOT DONE — AND IT IS SEVEN PATHS, NOT ONE** | `styles/route-b-migrated.txt` — `features/metering/readsShared.tsx` at lines **2687** and **2751**, and six more: `JobIntakeWizard.tsx`, `JobQueueTab.tsx`, `ConnectModal.tsx`, `ValueMappingPage.tsx`, `WorkShell.tsx` (twice each) and **`features/work/OrdersPage.tsx` three times**. Neither reader refuses a duplicate. **Violation 7-18 still true, and wider** |
| **MR-37** | Four direct reads of metering's tables go through the seam | **NOT DONE** | All four families live: **(1)** `apps/rating/seams.py:841` `django_apps.get_model("metering","MeterRead")` (plus `:668` Premises, `:743` ServicePoint); **(2)** `apps/integrations/mappings.py:164` `from apps.metering.models import Route`, inline in a function body; **(3)** `apps.metering.interruptions` imported directly by **five** files — `customers/service_request_api.py:96`, `customers/service_request_service.py:458`, `portal/services.py:73`, `portal/guest_api.py:58`, `portal/selectors.py:478`; **(4)** `portal/selectors.py:859,891` and `portal/credentials.py:256,323` reach `apps.metering.models` from **outside** portal's own seam file. Reads only — nothing writes |
| **MR-38** | Two derivations of *"the current window"* give one answer | **BLOCKED — AND THE QUESTION HAS NEVER BEEN MINTED** | Both derivations live and differ: `completeness.current_window` (`:516`) takes `period_engine.latest_opened_window` — the most recent occurrence to have **opened**, with a lane judgment recorded in its own docstring — while `selectors.cycle_dict` derives from `as_of`'s **month**. ⚠ **Nothing in `01-open-questions.md`, `02-decision-log.md` or metering's `02-business-rules.md` raises it.** The prime directive forbids picking a value; a question is owed before anything computes from either |
| **MR-39** | A clerk can open the account a reading belongs to | **NOT DONE** | `_read_linkage` (`selectors.py:3530-3541`) serves cycle · route · service · premise · premise_no · premises_id · unit_label · unit_id — **and no account**. `meter_reads.account_id` is a real FK in the reviewed cross-module set |
| **MR-40** | A staged batch is read a page at a time, and no row count is capped | **NOT DONE** | `read_batch_rows` (`selectors.py:5767-5777`) materialises **every** staged row with no page argument, and `api.py:1235` assigns it whole. `read_import.py:59` — **`CSV_ROW_CAP = 50_000`**, with the comment *"the row cap mirrors the assets lane's BR-AST-034 ceiling"*. ⚠ **Both halves are the T4/T3 flexibility CLAUDE.md calls load-bearing** — `NFR-3` (universal server pagination) and `NFR-5` (no hard caps anywhere). A 40,000-account utility importing a monthly cycle can reach that ceiling on one file |
| **MR-41** | The receipt is walked rather than composed from its source | **NOT DONE** | No test in `features/metering/*.test.tsx` ticks the certification and reaches `ResultPanel`. `UploadReadsPage.test.tsx:169` and `CR054ReadsUpload.dom.test.tsx:105` both seed `certified: false`; neither clicks the checkbox. Stage 5 is the one screen in the module nobody has seen, and it is the one that reports what a write did |
| **MR-42** | A tenant can choose how a missing read is estimated | **BLOCKED** | `metering.readValidation.estMethodWhen.plan_average` = *"Not available yet: a rate plan holds no average for us to read."* and `…route_peer_average` = *"Not available yet: nothing here says which accounts count as similar."* — both options render disabled with their reason, which is `BR-SHL-025` working. ⚠ **MONEY — an estimate is a bill input. Not classified here beyond "blocked"; the two questions are the coordinator's to route** |
| **MR-43** | A person can see what a cycle DID collect | **NOT DONE** | `f.cycle` is one of `READ_FILTERS` (`selectors.py:3225`), so the server half exists. There is no cycle page at a Reads address to hang the fifth tab on — see MR-30 |
| **MR-44** | A route has a page, measured against a window a person chose | **PARTLY DONE — AND TWO OF THE SPEC'S OWN CLAIMS ARE ALREADY FALSE HERE** | `features/tenancy/RouteDetailPage.tsx` is routed at `/settings/reference-data/routes-cycles/routes/{id}` with five tabs — **premises · units · assets · accounts · audit**, not the drawn Overview · Stops · Still to read · All reads · History. ⚠ **`GET /routes/{id}/read-windows` is NOT *"wrapped and uncalled since 2026-08-23"*** — `RouteDetailPage.tsx:201-205` calls it on the audit tab. ⚠ **The walk order is NOT *"drawn read-only"*** — `:213-215` writes it through `saveRoutePremisesOrder` → `PUT /routes/{id}/premises-order`. What is genuinely missing: the Reads address, the `?window=` parameter, and the two reads tabs. **This also narrows R9** |
| **MR-45** | A clerk sees the whole register set the plan expects | **NOT DONE** | `plan_registers` reaches only the upload wizard (`UploadReadsWizard.tsx:779,791,881`). `ReadDetailPage` says nothing about sibling registers |
| **MR-46** | A demand reading is read as a maximum, never as a difference | **PARTLY DONE** | The sharp half is built: `ReadDetailPage.tsx:568-581` renders `metering.read.peak` = *"Peak demand"* through `PeakQuantity` in the **register's own unit** (`kW`), with the reset chip — `BR-MET-143` closed `OQ-391`/`DEF-797` on 2026-08-27 and `read_dict:3720-3735` explains it at length. ⚠ **What is NOT done is the math line.** `mathLine` (`readsShared.tsx:267-277`) has **no `is_peak` guard**, and `ReadDetailPage.tsx:617-621` renders it whenever a register pair exists — so a demand row still prints `Register: (current − prior) × multiplier = usage`. **MONEY-ADJACENT: reported, not classified further.** It needs a test and a ruling-check, not a lane's judgment |
| **MR-47** | Service and register sit with the reading's identity | **PARTLY DONE** | `ReadDetailPage.tsx:397-402` — the kicker already carries **meter + channel** (the register). **The service badge is not in the header**; `service` is served by `_read_linkage` and appears only lower down. This is R5's build |
| **MR-48** | A meter with years of history is read a page at a time | **NOT DONE** | `ReadDetailPage.tsx:321-326` — `getAssetReads(read.asset_id, client)` with **no page argument**; `:896-930` renders the whole table with no pager. MR-01's fix makes `total` reachable, so this is the second half of one fix |
| **MR-49** | Wherever a shortfall is counted, the missing registers are named | **PARTLY DONE** | The resolver answers by name (`completeness.chase_list:907` `"missing_channels"`) and **two of the four surfaces render them**: the chase panel (`RoutesCyclesPage.tsx:353-356`, translated through `metering.reads.channel.*`) and the wizard's Load stage (`readsImportRail.tsx:392`). The other two surfaces are entries 20 and 21, which do not exist at a Reads address |
| **MR-50** | A completeness figure states what its denominator is made of | **NOT DONE** | `metering.cycles.completeness.line` = *"{{collected}} of {{expected}}"*, with no composition line under it. `RoutesCyclesPage.tsx:253-264` already documents the residue in a comment and names `OQ-1201`, **OPEN — non-blocking** |
| **MR-51** | A meter that cannot be estimated says so before it is ticked | **NOT DONE** | `completeness.chase_list:898-909` builds each row from unit · premises · meter · asset_id · route · service · missing_channels · days_left. **No estimability marker.** `BR-MET-026`/`BR-MET-027` refuse at the endpoint, so a clerk still learns after the press |
| **MR-52** | A reading shows who cleared its dispute, and who filed it | **NOT DONE** | The server half is complete — `read_dict` serves `dispute_cleared_at`, `dispute_cleared_by`, `imported_by`, `disposition`, `disposition_reason`, `event_context`, `trues_up_read_ids`, `read_type`, `period_end` (`:3695-3716`) — and `api/endpoints.ts:12358-12429` declares them. **No `.tsx` in the module renders any of the nine**; the only hit is `UploadReadsWizard.tsx:1893` using `disposition_reason` as a form value. Entry 06 restricts clearing to a System Admin and records who and when, and the reading shows no trace |
| **MR-53** | The thirteen PO rulings of 12–13 September exist as text in the repository | **NOT DONE** | Grepped all nine table quotes across `12-governance/` and `04-docs/` (blueprint folder excluded): **zero hits, all nine.** The decision log holds 120 rows dated 2026-09-12/13 and none is a Meter Reads ruling. **Part 1 of this file is the transcript that closes it** — the write itself is the coordinator's |

### 2.3 · The five to do first, re-checked against this branch

The document orders its own top five by what a person cannot do today. Re-measured:

| Doc rank | Spec | Still the right priority? |
|---|---|---|
| 1 | MR-01 — open a reading at all | **NO — ALREADY DONE.** The PO's *"fix J-01 — that crash is the priority"* is satisfied |
| 2 | MR-46 — tell a peak from a total | **PARTLY.** The figure is right; the math line is not. ⚠ money-adjacent |
| 3 | MR-22 — trust a clean gate | **YES, AND IT IS NOW FIRST.** It guards hard rule 1, it reports `PASS … 0 unresolved` today, and the blind alias count has gone from one to two |
| 4 | MR-45 — see that a sibling register never arrived | **YES, unchanged** |
| 5 | MR-52 — see that a dispute was cleared | **YES, unchanged** — and it is nine served fields and no renderer, which is the cheapest row on the register |

---

## Part 3 · The other checks the brief asked for

### 3.1 · The 18 rule violations — how many are still true, and how many any gate can see

**Still true on this branch: 17 of 18.** Only `7-17` has moved, and only halfway.

| # | Rule | Still true? | Does any gate ask? |
|---|---|---|---|
| 7-01 | B14 31 — no database id on screen | **YES** | `G28` reads strings, not rendered values. **No** |
| 7-02 | BR-SHL-025 · B14 11 — a control that cannot act is disabled with its reason | **YES** | **No** |
| 7-03 | B14 12/13/14 — the table toolbar | **YES** | **No** |
| 7-04 | NFR-3 — universal server pagination | **YES** | **No** |
| 7-05 | B14 8 · 36 — the kit's `SelectField` | **YES** | The chevron register does not cover this screen. **No** |
| 7-06 | B14 7 · 36 — the kit's date field | **YES** | Rule 7 is half-enforced on four asset screens. **No** |
| 7-07 | B14 8 · BR-SHL-033 — type-to-filter past ten | **YES** | The searchable half is explicitly unchecked. **No** |
| 7-08 | B14 33 — rationale is zero words on screen | **YES** | `G33` caps refusal sentences; it does not read a lede. **Partly** |
| 7-09 | B14 33 — a fact is a fact | **YES** | **No** |
| 7-10 | BR-SHL-034 — one date formatter | **YES** | **No** |
| 7-11 | B14 17 — an empty state names the action that fills it | **YES** | **No** |
| 7-12 | B14 15 · 16 — row actions and a pager | **YES** | `G37` covers icons where actions exist; it cannot ask for a missing one. **No** |
| 7-13 | law 2's mirror — a hold with no expiry test | **YES** | `G103` exists for rotting holds and does not cover this string. **No** |
| 7-14 | law 1 — a comment claiming a guarantee | **YES** | **No** |
| 7-15 | law 1 — the trailer | **YES** | **No** |
| 7-16 | law 1 — two files disagreeing about one fact | **YES, and now FOUR files** | **No** |
| 7-17 | the ICP ruling · NFR-5 | **YES** — both comments still name `<3,000`; neither is a cap in code | **No** |
| 7-18 | B14 21 — the migration ledger is an exact list | **YES, and now seven paths** | Both readers key on the path; neither refuses a duplicate. **Partly** |

**Why the last column is the finding, and it is worse than the document says.** The
blueprint counted 3 of 18 as machine-catchable. Two gates that look as though they would
help were run and **both are scoped to the customer portal**:

* `G100` (*every screen has a door*) — `PASS: all 52 registered portal screens are reachable`. It reads no staff screen, so `7-03`, `7-04`, `7-11`, `7-12` and the whole doorless finding are outside it.
* `G105` (*a screen matches its drawing*) — its own docstring names `04-docs/05-modules/15-portal/08-screen-layouts.md` as *"this gate's ONLY source of truth about shape"*.

**So B14 rules 41 and 42 — the product matches the blueprint exactly, built from the
image — have no enforcement on any staff screen.** `04-docs/02-decisions/14-ui-conventions.md`
holds **33 rules today** (numbered 1–21 and 31–42, counted from its own status table),
which matches CLAUDE.md's pointer exactly — no pointer rot to report.

### 3.2 · G96 reports a clean zero over a file it cannot see — **CONFIRMED**

Run, not inferred:

```
$ python3 10-scripts/gates/g96_portal_reads_name_the_tenant.py
PASS: 30 portal file(s) read; every queryset over another module's model names the
tenant, except 0 row(s) held in the ratchet (which may only shrink); self-test: …
```

* `FOREIGN_MODELS` (`g96…py:97-116`) is a **hardcoded list of eleven import aliases**.
* `apps/portal/seams/metering_seam.py:310` — `from apps.metering import models as reads_models`. Not on the list.
* `:316-320` — `reads_models.MeterRead.objects.filter(id__in=wanted).select_related("asset")`. **No tenant keyword.**
* `:35` — `from apps.metering import interruptions as interruption_models`. **Also not on the list.** Its one query (`:83`) does name the tenant, so it is safe today and equally invisible.
* The gate prints **no skipped count**, which is exactly hard-won law 7's fifth shape: *"a declared blind spot with no NUMBER attached is indistinguishable from an empty one."*

The read is still tenant-safe in production (RLS `ENABLE`+`FORCE`), so **the defect is in
the check, not today's data** — and the check is the only thing standing between this file
and law 14's trap.

### 3.3 · Four places read metering's tables directly instead of through the seam — **CONFIRMED, and it is more than four files**

| Consumer | Line | What it does |
|---|---|---|
| `apps/rating/seams.py` | `:841` (`:668`, `:743`) | `django_apps.get_model("metering","MeterRead")` then `.objects.filter` — and it **declares itself** in its own docstring (`:825`) |
| `apps/integrations/mappings.py` | `:164` | `from apps.metering.models import Route`, inline in a function body |
| `apps/customers` + `apps/portal` | 5 files | `from apps.metering import interruptions as interruption_models` — `service_request_api.py:96`, `service_request_service.py:458`, `portal/services.py:73`, `portal/guest_api.py:58`, `portal/selectors.py:478`. **A consistent shape across five callers usually means a seam function is owed, not that five lanes were careless** |
| `apps/portal` outside its own seam | 4 sites | `portal/selectors.py:859,891` · `portal/credentials.py:256,323` |

**Reads only; nothing writes.** That is the grade that matters most, and it is unchanged.
It is also how `G96`'s blind spot became reachable: the boundary and the blind spot are
the same defect from two ends.

### 3.4 · The 181 stated absences — counted by category, not transcribed

The document's own census (p63): **741 reads keys · 181 refusal-or-absence strings · 28
holding a control a user can see and cannot use · 3 dead · 2 expired holds**, resolved as
**7 specifications · 13 rows out of scope · 50 prose absences · 103 server refusals**.

**Re-measured on this branch, and the census cannot be reproduced.** The reads-family key
space has grown from 741 to **844** (+103), so any figure I derive with my own predicate
would not be comparable with the document's. What CAN be checked one by one is the small
set the document singles out, and here it is:

| The document's finding | State on this branch |
|---|---|
| **2 expired holds** | **BOTH STILL LIVE.** `metering.read.action.billedLocked` over a served endpoint (MR-15) · `metering.ops.notCollectedWhy` over an unreachable branch (MR-16) |
| **3 dead strings** | **2 of 3 GONE** (`device.unitRequired`, `generation.requiresDevice`), plus the fourth (`batch.errorsNeedResolution`). `metering.reads.deviceReadNote` survives in **all eleven** catalogues (MR-18) |
| **3 rows re-decided from out-of-scope to specification** | All three still stand as specifications: MR-25, MR-39, MR-42 — none is built |
| **7 specifications from §06** | MR-03 · MR-04 · MR-10 · MR-15 · MR-16 · MR-17 · MR-18 — **none done; MR-18 partly** |
| **13 rows out of scope** | Not re-opened. The judgement rule that produced them (*"a recorded ruling that a thing waits makes it out of scope; no ruling makes it a specification"*) is itself worth writing into the repo — it is the local form of the change process's *"when it is ambiguous it is a DEFECT, not a change"* |

### 3.5 · A red I did not cause, dated

Per law 7 habit (1), and dated with `git log -S` rather than asserted:

```
$ python3 10-scripts/gates/g114_list_envelope.py
G114 FAIL 07-frontend/src/api/endpoints.ts: `ImportRunListResult` declares `rows`
beside `per`/`pages`/`last_page` — that is the SELECTOR's page dict, not the reply …
```

`git log -S "ImportRunListResult" -- 07-frontend/src/api/endpoints.ts` and
`git log --diff-filter=A -- 10-scripts/gates/g114_list_envelope.py` both return the
**same** commit, `cf45a3d2`, dated **2026-09-13** — *"Communication dialog: start from the
utility's own wording…"*. **The gate arrived today, red, on a declaration that predates
it.** Not this pass's, not fixed here, and named so the next reader does not dismiss it as
a known one.

---

## Part 4 · What the coordinator has to do with this file

**Nothing in Part 1 has been written to a register. That is deliberate and it is the
whole point of the file.**

| Destination | Rows |
|---|---|
| `12-governance/change-requests/CR-096-BRC02-meter-reads-blueprint.md` — supersedes chains | **R1** (`BR-MET-060` → superseded, `US-MET-019` → retired), **R2** (collides with `BR-MET-011` and with A1's S26/S27) |
| `04-docs/02-decisions/14-ui-conventions.md` (B14) | **R4** — the Panel ruling is product-wide, not metering's |
| `04-docs/05-modules/04-metering/02-business-rules.md` | **R3 · R5 · R8 · B10** |
| `12-governance/02-decision-log.md`, verbatim with its date | **R6 · R7 · B1–B9** — and R7 with its scope note, because it is why the other eighteen were lost |
| `12-governance/01-open-questions.md` | **R9** (the walk-reorder question, narrowed by MR-44) · **MR-24**'s four shapes, which no question covers · **MR-38**'s window fork, which no question covers |
| `12-governance/10-defect-log.csv` | `DEF-815` reads **`wontfix`** and MR-17 would reverse that — a decision, not a filing |

**Three things worth the coordinator's attention before anything is built:**

1. **MR-30 and MR-44 are redesigns of screens that already exist**, in `features/tenancy/`,
   linked and working. Building them from scratch would be the third time this repo
   discovers that late.
2. **MR-17 is not blocked** — `OQ-042` is CLOSED and rules it. The blueprint's "waits on a
   ruling" is wrong, and law 13 says a re-ask is a bug in us.
3. **MR-24's cited question is CLOSED and its closure confirms the constraint**, so the
   blocker is real but its name in the document is wrong. Same shape as (2): a register
   row's **status column** and a document's **prose** disagreed, and the status column
   decides.
