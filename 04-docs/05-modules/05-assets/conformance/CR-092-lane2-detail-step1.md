# CR-092-BRC01 · step 1 · lane 2 — ONE ASSET: the detail screen and its five tabs, read against the blueprint

**Lane:** 2 of 6 · **Step:** 1 (IDENTIFY — this lane changed no component, catalogue,
route, stylesheet or test) · **Date:** 2026-09-11 · **Branch:** `claude/hi-0jmv62`
**Scope:** blueprint screens **08 Overview · 09 Reads · 10 Export · 11 Assignment
history · 12 Work & maintenance**, plus tab 5 (Audit) where it bears on the others.
**The file:** `07-frontend/src/features/assets/AssetDetailPage.tsx`, 1,403 lines.

**Specifications that land here:** `AST-B-16`, `AST-B-18`, `AST-B-19`, `AST-B-21`,
`AST-B-22`, `AST-B-23`, `AST-B-24`, and `BR-WRK-056`'s two missing doors.

**Defect rows filed by this lane:** `DEF-MET-4965` … `DEF-MET-4970` (six).

---

## ⚠ READ THIS FIRST — TWO FINDINGS THAT CHANGE WHAT STEP 2 BUILDS

Everything else in this document is description. These two change the work itself,
and each is a case where **a specification's own "waits on" line is wrong** — which
is worse than no line at all, because a "waits on" line is what a planner sizes from.

**1 · `AST-B-18` IS NOT A TYPE WIDENING. IT IS A SERVER CHANGE.**
The blueprint records *"Waits on: Nothing on the server."* **`priority` is not served
on `GET /assets/{id}/work-orders` at all.** It is built by `dispatch._priority_of` and
reaches `_dispatch_row` (`dispatch.py:256`, `:414`, `:1140`) and `mobile.py:170` —
**never `_scoped_row`**, which is the function this endpoint's rows are built by.
`due_at` and `technician` *are* served; `priority` is the one of the three that is not.
Sizing this as *widen a TypeScript interface from four fields to seven* is wrong: one
of the three columns needs `_priority_of(order)` added to `_scoped_row`, **which widens
the row for the premises tab and the account tab at the same time**, because all three
lists share that builder by design (*"one row shape for every list of work orders in
this product"*). That is a cross-screen server change with its own blast radius, and
nothing in the blueprint says so. Detail in §4.

**2 · THE `BR-WRK-056` FIX IS NOT ADDITIVE — A GREEN TEST HOLDS THE DOOR SHUT.**
`AssetDetail.test.tsx:811` runs `expect(html).not.toContain("Raise work order")`,
justified by the comment *"No wo storage exists yet (Work is R5)"*. **That premise is
dead:** `apps/work` ships with 27 migrations and `apps/work/asset_door.py` — a file
named for this exact door — names *the Maintenance history panel on `AssetDetailPage`*
as one of the ways in. So the backend built the door, the front end never hung it, and
**the test that should have fired when the hold expired is the test enforcing it.**
A step-2 lane will meet this as an unexplained red and must invert it, never weaken it.
Two neighbouring tests also constrain the shape: `TC-6` forbids any
`data-variant="primary"` in the detail header on every tab, and `TC-3` asserts the
header action block is byte-identical across tabs. Detail in §1.

---

## 0 · How this was produced, so the numbers can be re-run

Everything below is either a command over the source or a measurement taken in a real
browser. Where it is neither, it says so.

* **Baseline proved current first.** `git diff --numstat 79c659d7d HEAD --
  07-frontend/src/features/assets/AssetDetailPage.tsx` printed nothing: the file is
  byte-identical to the blueprint's commit, so its as-built statements about this
  file may be built on. Re-checked, not assumed.
* **A private stack**, backend `127.0.0.1:8483` and web `127.0.0.1:8484`, built from
  this worktree. The coordinator's correction is recorded: there was no shared stack
  on 8401. **This lane wrote nothing to the database** — every walkthrough is
  GET-only, no PATCH, no POST, no seeding.
* **Chromium rendered.** `playwright-core` resolved through `createRequire` pointed
  at `07-frontend/package.json`, executable from `/opt/pw-browsers`. **No claim in
  this document is unverified for want of a browser.**
* **Widths 1280 and 1440**, and nothing narrower — clerk and utility-admin
  (PO ruling 2026-09-10). Every rendered result below was identical at both.
* Scripts live in this lane's scratchpad rather than in `10-scripts/`, because step 1
  writes findings and nothing else: `detail_walk.mjs` (the five tabs),
  `kind_sweep.mjs` (four asset kinds), `census.mjs` and `reads_strip.mjs`.
  **Step 2 should land the first two in `10-scripts/`.**

### The baseline suite, before anything was judged (law 7, habit 1)

```
tsc --noEmit                      exit 0
vitest run src/features/assets    7 files · 162 passed · 12 todo · 0 failed
```

**There were no pre-existing reds in this lane's scope**, so every finding below is
one that a wholly green suite passes over. That is the point of the lane.

### The fixture, counted — because it decides what could be seen at all

Read directly from PostgreSQL with `app.tenant_id` set per tenant (RLS `FORCE` is on,
so an unscoped count returns 0 and reads as an empty database — it is not):

| tenant | assets | meter_reads | asset_assignments | asset_maintenance | work_orders | work_order_cost_lines |
|---|---|---|---|---|---|---|
| brazosbend | 12 | 24 | 9 | **0** | **0** | **0** |
| oak-ridge | 74 | 202 | 67 | **0** | 23 | **0** |
| pine-hill | 135 | 518 | 127 | **0** | 42 | 8 |
| **all three** | **221** | **744** | **203** | **0** | **65** | **8** |

* Largest read count on any one asset: **26**. Largest assignment count on any one
  asset: **1**, on every asset, on every tenant.
* **Work orders anchored to an asset: 0 of 65**, on all three tenants.
* **Behind-the-meter devices carrying a `parent_asset_id`: 0 of 24.**

---

## 1 · THE HEADLINE — `BR-WRK-056` has two doors missing, and a green test holds one of them shut

`BR-WRK-056` is **CONFIRMED** and reads, verbatim: *"The Assets door is ONE form with
four ways in … the action bar, the Maintenance history panel and the four
`RaiseWorkOrderCheckbox` ticks … all post it."*

**Verified, three ways.**

1. `grep -c raiseWorkOrderPath AssetDetailPage.tsx` = **0**, against **7 production
   call sites** in five sibling files — `AssetAddWizard.tsx:474`,
   `AssetFlowPages.tsx:294` and `:546`, `AssetRetireWizard.tsx:220`,
   `AssetLifecycleTab.tsx:187`. All four `RaiseWorkOrderCheckbox` ticks exist. The
   two controls on the asset's own screen do not.
2. The route is live: `App.tsx:1006` mounts `RAISE_WORK_ORDER_ROUTE`.
3. **In the browser, at 1280 and 1440, on all four asset kinds:** the Overview header
   offers exactly `Reassign · Log repair · Retire`; the Maintenance tab offers exactly
   `+ Log repair`. Zero occurrences of *Raise work order* anywhere on the page.

**What the blueprint missed, and it changes step 2's plan.**

* **A green test asserts the door shut.** `AssetDetail.test.tsx:811` runs
  `expect(html).not.toContain("Raise work order")` (the case is `:807-813`) on the maintenance tab, with the
  comment *"No wo storage exists yet (Work is R5)"* — a reason that expired the day
  `apps/work` shipped. The blueprint's own violation table records the enforcement
  column for this row as *"No. Nothing reads rendered output, and no test asserts a
  control's absence."* **Both halves are false**: vitest reads rendered output here,
  and a test asserts exactly this control's absence, by name, in the exact string the
  fix must add. **The fix is not additive — it turns that test red**, and a step-2
  lane reading it as an unrelated failure may weaken it instead of inverting it.
  → `DEF-MET-4966`
* **Two neighbouring tests constrain the shape of the fix.** `TC-6` forbids any
  `data-variant="primary"` in the detail header on every tab, so a header Raise
  control must be secondary; `TC-3` asserts the header action block is byte-identical
  across tabs, so it must be added to all of them or none.
* **There is no server gate to hang it on.** `row_actions()`
  (`apps/assets/selectors.py:214`) returns `view · edit · assign · delete · reassign ·
  log_repair · retire` — **no raise verb**. Every other header control here is gated by
  `hasAction(asset, "<verb>")`, which reads that set (`BR-AST-006`: *the header's
  action set is the SERVER's*). So step 2 must choose: add `raise_work_order` to
  `row_actions()` (a server change, which then has to answer whether a **retired**
  asset — behaviour class `TERMINAL`, actions `["view"]` — offers it, against
  `BR-AST-030`), or gate it client-side and break the page's own convention.
  **The blueprint records this as waiting on nothing.**
* **The blueprint's acceptance sentence picks an asset that sharpens the question.**
  *"On AST-04412's Work & maintenance tab a Raise work order button…"* — AST-04412 is
  drawn throughout as **Inventory**, whose server action set is
  `["assign","edit","delete"]` and which is offered no `log_repair` either.
* **A pointer slip:** the violation table files this under *"Screens 10, 14"*. The
  evidence it cites (`AssetDetailPage.tsx:375-410`, `:1286-1395`) is the header action
  bar and the maintenance panel, i.e. **screens 08 and 12**. `AST-B-02`'s own card
  says 12 and 27.

→ `DEF-MET-4965` (the doors) · `DEF-MET-4966` (the test holding one shut)

---

## 2 · Screen 08 · Overview

**What the blueprint claims.** *"Thirty-eight facts arrive at this page today and
thirty-one are drawn."* Six panels in the redesign; seven rows added from ids already
on the payload; no new endpoint, column or query; and `AST-R-09` — *a fact is said
once* — *"broken twice today: Parent and Last test date each render in two panels."*

**Verified.**

* **31 rows drawn** on a plain installed meter (M-7302, 1440 and 1280). Counted in the
  DOM. The blueprint's number is exactly right.
* Per kind: sub-meter **32** · backflow preventer **27** · battery **24**.
* Four panels as built — Specifications · Assignment · Warranty & supplier ·
  Lifecycle — plus Test & certification on a device with a cadence.
* The redesign really is nearly free: everything it draws is already on the wire.

**Corrections.**

1. **"Thirty-eight facts arrive" is `asset_dict()`'s key count, not this page's.**
   `asset_dict()` returns **38** keys (counted by AST) — that is the LIST row shape.
   `GET /assets/{id}` spreads it and adds seven blocks: `specs` (11), `classifications`
   (3), `billing_chain` (6), `sub_assets`, `valuation` (13), `lifecycle` (4),
   `linked_meter` (3). **The detail payload is 45 top-level keys / ≈78 leaf facts.**
   The blueprint reconciles its Overview carry-over against 38, which is the wrong
   denominator.
2. **`AST-R-09`'s evidence is wrong, and it is the one claim in the section a machine
   could settle.** The two pairs the blueprint names sit on **mutually exclusive
   branches**: Parent renders in Specifications when `tab === "sub_meters"` and in
   Assignment when `tab !== "sub_meters"`; Last test renders in Specifications when
   `measuring` (meters, sub-meters) and in Test & certification when
   `tab === "behind_the_meter"`. **Rendered, on all four kinds, at both widths: zero
   duplicate labels.** The proposed check — *assert every `<dt>` label appears at most
   once* — is a good check and **passes today**; it would have caught neither. The
   blueprint reached its conclusion from a source grep, which is the failure mode its
   own section 09 preamble warns about.
3. **14 of the 78 leaf facts are served and never referenced by the component**
   (checked by matching each served key against `AssetDetailPage.tsx` + `assetsShared.tsx`):
   `external_ref`, `read_method`, `service_point_id`, `assigned_unit_id`, `next_test`,
   `specs.allocation_rule`, `specs.loss_tolerance_pct`, `classifications.read_method`,
   `valuation.purchase_date`, `.depreciation_method`, `.accumulated_depreciation`,
   `.life_months`, `.book_value_amount`, `.book_value_treatment`. Four of those are
   duplicates of a fact served under another name or link targets; **nine are genuinely
   unrendered facts.** The blueprint's drawing names **seven** new rows and one of them
   — **the account — is already rendered** (its own interaction table says so: only the
   anchor is new). It misses **`accumulated_depreciation` and `life_months`**.
4. **`AST-B-22`'s five fields are four.** `asset_dict()["next_test"]` and
   `asset_detail()["lifecycle"]["certification_due"]` are **the same call**,
   `next_test_date(asset)`, served under two names on one payload. They can never
   disagree, so a strip condition written over both is writing one condition twice.
   `test_due`, `warranty_covered` and `status` are the other three, all served.
   **`AST-B-22`'s "waits on nothing" is otherwise correct** — and verified absent:
   no attention strip renders on any asset at either width.
5. **`AST-B-22` does not revert independently of `AST-B-02`.** Its drawn strip carries
   a `Raise work order →` control, which is precisely the door §1 says does not exist.
   The blueprint's rollback paragraph says all twenty-four revert independently.
6. **Small divergence from Figure 10:** the Assignment panel draws the premises
   **number** (`P-00004`) where the drawing shows an address, because the code is
   `chain.premise_no ?? chain.premise_address`.

**`AST-B-16` — where the two facts would have to be computed.** Answered:

* **Lifetime maintenance** is **already computed and served**, by
  `selectors.maintenance_lifetime_cost()` on `GET /assets/{id}/maintenance` — not on
  `asset_dict()`, exactly as the blueprint says. To reach the **Overview** it needs
  either a key on `asset_detail()` or a second query from the Overview tab. That is
  the decision, and it is small. (It sums at 4 dp and quantizes to 4; see §6.)
* **Open work orders** has **no read at all.** `open_work_order_count_for_unit` and
  `open_work_order_count_at_premises` exist; **there is no `..._for_asset`.** Three
  options, and the choice is real: publish a new count from `apps/work`; or add
  `state__in=OPEN_WORK_ORDER_STATES` filtering to the existing endpoint — which
  `_scoped_page` deliberately does not do (*"EVERY STATE, NOT JUST THE OPEN ONES"*);
  or count client-side from the `state` field on rows **the page already fetches and
  throws away** (§4). The third is free and is the one the blueprint explicitly
  rejects (*"served rather than computed in the browser from a list the page happens
  to hold"*).

---

## 3 · Screen 09 · Reads — and the finding the blueprint's own walk could not see

**What the blueprint claims.** A bare table: no search, filter, column chooser,
download or pagination at any of four layers; `channel` served and rendered nowhere;
one `AssetUsageStrip` mounted above the table.

**Verified.** All of it. Columns drawn: `DATE · READING · IMPORT · EXPORT (NET) ·
SOURCE · STATUS` — six, no Channel. `row.channel` is read **only** by
`isPeakChannel(row.channel)`. `GET /assets/{id}/reads` accepts no `page`/`per` and
returns a bare list; **49 in-asset list calls in one walkthrough and not one carries a
paging parameter.** `showExport={asset.net_metering}` is conditional as described.

**Two findings the blueprint does not have.**

1. **It is one chart panel PER REGISTER, not one strip.** `payload.series.map` renders
   a full `RegisterChart` — chart, date range, gap sentence, three stat tiles — for
   every register. **M-7302 draws five.** The read log begins at **y = 2,324px against
   a 900px viewport: 2.6 screens of scrolling** before a clerk sees a reading.
   M-7450 draws four, y = 1,945px, 2.2 screens. Identical at 1280 and 1440. The
   sentence *"N of 12 months have no reading."* repeats **five times on one screen**.
   Figure 13 draws one compact strip with three tiles. **The blueprint's walk opened an
   asset with no reads** — the single state in which the strip collapses to one empty
   panel — so its own walk could not see this. → `DEF-MET-4970`
2. **Five panel headings print raw channel codes to a clerk:** `total`, `tou_on`,
   `tou_mid`, `tou_off`, `export`. `AssetUsageStrip.tsx`'s exception **E3** justifies
   this — *"no signed vocabulary maps a register to a display word, and inventing one
   here would be a rule this screen does not get to write"*. **That is false today.**
   `metering.reads.channel.*` ships **7 keys in all 11 locale catalogues** —
   `total`→*Total register*, `tou_on`→*On-peak*, `tou_mid`→*Mid-peak*,
   `tou_off`→*Off-peak*, `demand`→*Demand*, `export`→*Export*,
   `generation`→*Generation* — and **six files already resolve it**
   (`ReadDetailPage` ×2, `readsShared`, `RoutesCyclesPage`, `readsImportRail`,
   `UploadReadsWizard` ×2). Hard-won law 1 in its quietest form: a comment asserting an
   **absence**, written into a lifecycle block so it reads as a decision rather than as
   stale. → `DEF-MET-4969`

   **This makes the Channel column CHEAPER than anyone thought:** the column and the
   words both already exist. It waits on nothing.

**`AST-B-24`, and the numbering problem.** The coordinator's ruling is recorded and
followed: the blueprint **double-books** `AST-B-24` — its section-13 card says *"A
meter with more than one register says which row is which"* while the register row
says *"the reads table pages on the server"*. **The register wins.** The consequence is
worth stating plainly: **the Channel column now carries no live specification number at
all**, and a lane working the register list would never build it. It is recorded here
and inside `DEF-MET-4969` so it is not lost.

---

## 4 · Screen 12 · Work & maintenance — `AST-B-18` is a different defect from the one described

**As built the merged tab does not exist**: the tab is labelled **Maintenance &
repairs** and holds one table of `asset_maintenance` rows —
`Date · Type · Technician · Detail · Work order · Cost · Outcome` — with no Open
work / History split and no sub-tabs. The blueprint says as much.

**`AST-B-18` — both numbers checked, and both differ.**

| | blueprint | measured |
|---|---|---|
| fields served per order | 29 | **24 top-level keys** (≈31 leaf with one nesting level expanded) |
| fields the client type declares | 4 | **4** ✓ (`id`, `order_no`, `type`, `state`) |

The 24 is `_row`'s 12 keys plus `_scoped_row`'s 12, counted by AST. **I could not
reproduce 29 under any counting rule** and report 24.

**Three corrections, and the third is a blocker for the stated fix.**

1. **The three columns are not "drawn and empty on every row".** `listAssetWorkOrders`
   has exactly one consumer, and that consumer reads **only** `maintenance_index`.
   `rows` and `total` are fetched and discarded. **No work order is rendered on the
   asset at all**, so there are no columns to be empty. The defect is larger than
   described and differently shaped: a full list round-trip paid on every Maintenance
   tab open with 100% of its row payload thrown away.
2. **`total` is already in the client's hand** and discarded — see `AST-B-16` above.
3. **`priority` IS NOT SERVED on this endpoint — so this specification's "waits on"
   line is false, and that is the finding that changes the size of the work.**
   It is built by `dispatch._priority_of` and reaches `_dispatch_row`
   (`dispatch.py:256`, `:414`, `:1140`) and `mobile.py:170` — **never `_scoped_row`**,
   which is what builds this endpoint's rows. `due_at` and `technician` *are* served.
   The blueprint records `AST-B-18` as *"Waits on: Nothing on the server"*; two of its
   three columns are free and **the third is not**. And `_scoped_row` is shared on
   purpose — *"one row shape for every list of work orders in this product means the
   account tab, the premises tab and the dispatcher's queue cannot describe the same
   order three ways"* — so adding `priority` there **widens the premises tab and the
   account tab in the same commit.** A planner reading the blueprint sizes this as a
   client-side type widening; it is a cross-screen server change. See the callout at
   the top of this document.

→ `DEF-MET-4967`

**`AST-B-21` — the decision, identified and NOT made.** It is **three** decisions, not
one:

* **(a) Which costs count.** `_scoped_page` deliberately serves **every** state, and
  `WorkOrderCostLine` rows are persisted **at acceptance**, so an open job has no cost
  lines. *"Jobs on this asset"* is therefore *"jobs that have been accepted"* — a
  different sentence from the one drawn.
* **(b) Which rounding rule the combined total obeys, and this is the sharp one.**
  `maintenance_lifetime_cost()` sums the stored 4-dp costs and quantizes to 4 dp
  (**sum then round**). `BR-WRK-051` says *"the total is the sum of the ROUNDED
  displayed lines"* — `42.20 + 96.00 + 0.22 = 138.42`, **not** `138.4150` (**round then
  sum**). A single *Lifetime* figure must obey one of them, and **`BR-WRK-051` is
  PROPOSED, not confirmed.** Nothing here is a ❄️ frozen B4/B5 figure and nothing posts,
  so this is ours to decide and write down — but it must be decided, not defaulted.
* **(c) Where the arithmetic lives, and it needs a seam that does not exist.**
  `apps/assets` reaches five modules through `seams.py` — audit, billing, customers,
  metering, tenancy — and **has no reference to `apps.work` anywhere**. Today the
  assets↔work join is client-side only, by design (`AssetDetailPage.tsx:1301`). A
  server-side sum must therefore be published by `apps/work` on the envelope it already
  serves — `maintenance_index` proves that pattern — rather than by `apps/assets`
  reaching across. `BR-WRK-051` says the cost arithmetic lives in exactly one named
  function, so whether an aggregate over stored `amount` values counts as *the
  arithmetic* is part of the same ruling.

**And the magnitude cannot be reproduced.** The brief and the blueprint both say
*"740 costed jobs are invisible from here"*. **740 is quoted from a docstring**
(`costing.post_field_cost_to_ledger`, *"740 jobs · $56,337 on the sample utility"*),
and the repo's own seeder note says the opposite — `sample_field_work.py:28`:
*"`work_order_cost_lines` **0**, against **39 raised work orders**"*. On this database
it is **8 cost lines and 65 work orders, 0 of them anchored to an asset**. The defect
is real and structural; **the number is not a measurement and should not be repeated as
one.**

---

## 5 · Screen 11 · Assignment history · and screen 10 · Export

**Screen 11.** Verified: a hand-built table with five columns —
`FROM · TO · PREMISE · UNIT · BY` — no toolbar, no pager. `final_read_id` **is**
served on every row (9 keys) and rendered nowhere, exactly as the blueprint says.
Newest-first is in SQL (`order_by("-from_date","-created_at")`), so that claim holds.

**One thing the blueprint's Figure 17 hides.** It draws Premise and Unit as links
(`118 Bayou Bend Dr →`), but its NEW annotation lists only *"the toolbar, the pager and
the Final read column"*. The links are not free and are **asymmetric**: the assignment
row serves `unit_id` but **not `premises_id`**, so linking the Unit is client-only and
linking the Premise needs a server change. Today both are plain text — while the
Overview's Assignment panel renders the same two facts as links.

**Screen 10 · Export — a blind spot with a number, and it is not the fixture's fault.**
The tab renders only when `linked_meter !== null && linked_meter.net_metering`, and
`linked_meter` is built only for a `behind_the_meter` asset **with a `parent_asset_id`**.
Across all three tenants: **0 of 24 behind-the-meter devices carry one.** So the Export
tab **cannot render on any asset in this product today** — not "was not reached on the
seeded tenant". Its structure is read from source only, and it stays UNVERIFIED here for
that reason. It is also hard-won law 2's mirror in a third shape: a pane whose render
condition no row in the database can satisfy.

---

## 6 · What I could NOT check, with the reason and the number

A declared blind spot with no number is indistinguishable from an empty one.

| what | how many claims | why not |
|---|---|---|
| The work-order list as **rendered** — its columns, its rows, `Priority`/`Due`/`Assigned to` | **3** | `work_orders.asset_id` is null on **all 65** orders across all three tenants, so `GET /assets/{id}/work-orders` returns an empty page for **every one of the 221 assets**. Verified from the code instead. |
| The Maintenance history **table** as rendered — its 7 columns, row shapes, the Work-order cell | **4** | `asset_maintenance` holds **0 rows on all three tenants**. The table never draws; the empty state does. Verified from source. |
| The server's `lifetime_cost` line as rendered | **1** | Same: it renders only when a maintenance row carries a cost, and there are none. |
| Screen 10, the Export tab | **all of it** | **0 of 24** behind-the-meter devices carry a `parent_asset_id` (§5). Unreachable, product-wide. |
| `AST-B-19`/`AST-B-24` at volume — a slow paint, a large payload | **2** | Largest read count on any asset is **26**; largest assignment count is **1**. The blueprint's *1,460 reads* and *14 rows narrowed to 3* are illustrations (B14 rule 37) and it says so. **The transport defect is structural and unfalsifiable on this data** — a step-2 lane following the maintenance process's REPRODUCE step will fail to reproduce it and must not conclude it is not real. |

**Everything else in this document was either rendered in a browser or counted over the
source.** Nothing is unverified for want of a browser.

---

## 7 · `AST-B-19` / `AST-B-24` — the transport, and what the envelope has to become

**Verified.** `asset_reads` and `asset_assignments` (`apps/assets/api.py:226-240`) call
`parse_list_params` not at all, accept no `page`/`per`, and return a bare list.
`selectors.assignments()` and `selectors.maintenance()` each do
`list(...objects.filter(...))` with no slice. `asset_reads()` pulls **every** committed
read head through the seam and regroups and folds the whole set in Python.
**Three endpoints are unbounded, not two** — the blueprint's fix names `/reads` and
`/assignments`, and **screen 12's own list comes from `/assets/{id}/maintenance`**,
which is unbounded too and appears in no row of the register. `/work-orders` is the only
one of the four that already pages (`_scoped_page`, with `clamp_page_size`).

**A cheaper partial fix nobody has named.** `metering.selectors.typed_reads_for_asset`
**already takes `period_start` and `period_end`**; `apps/assets/seams.py:237` drops both
from its signature, so the bound that exists on the metering side is unreachable from
the asset. A window is not a page, but it is one line and it bounds the worst case.

**A sequencing constraint step 2 must honour.** `DataTable` documents `rows` as *"the
CURRENT PAGE only — pagination is server-side (IS-2)"* with a server-provided
`totalRows`. **So `AST-B-23` cannot be done before `AST-B-19`** without passing the whole
list as one page — which would recreate inside the asset the exact *honest envelope over
an unbounded query* shape lane 6 filed as **`DEF-MET-4951`** on the registry. The
blueprint lists the two as independent and its rollback says all twenty-four revert
independently. **They do not.**

**Classification, recorded rather than acted on.** `CR-092` §1 classifies `AST-B-19`,
`AST-B-21`, `AST-B-22`, `AST-B-16` and `AST-B-24` as **changes**. `NFR-3` is a signed
engineering rule and the blueprint's own section 09 files its registry breach as a
**violation**; by §1's first table — *the product does not do what a signed rule
promises* — the in-asset half reads as a defect. **This lane did not file against a
ruled classification** and did not file a second `NFR-3` row (per the coordinator's
instruction). It is flagged here for step 2 and the PO.

---

## 8 · Where I disagree with the blueprint, in one list

1. **`AST-R-09` is not broken today.** Zero duplicate labels on all four kinds. Its
   proposed check passes. (§2.2)
2. **`GET /assets/{id}/work-orders` serves 24 top-level keys, not 29.** (§4)
3. **`priority` is not served on that endpoint at all**, so `AST-B-18`'s *"Waits on:
   Nothing on the server"* is false and the work is a **server** change that also widens
   the premises and account tabs — not the client-side type widening it is sized as. (§4)
4. **The three columns are not drawn-and-empty; nothing renders the list at all.** (§4)
5. **"Thirty-eight facts arrive at this page" is the list row shape.** The detail
   payload is 45 top-level keys / ≈78 leaf facts. (§2.1)
6. **The seven new Overview rows are six** — the account row already renders — **and it
   misses two** (`accumulated_depreciation`, `life_months`). (§2.3)
7. **`AST-B-22`'s five served fields are four**: `next_test` and `certification_due` are
   the same call. (§2.4)
8. **740 costed jobs is a docstring figure**, contradicted by the repo's own seeder note
   (0) and by this database (8). (§4)
9. **"No test asserts a control's absence" is false** — one does, and it will turn red
   on the fix. (§1)
10. **`AST-B-19` and `AST-B-23` are not independent**; nor are `AST-B-02` and
    `AST-B-22`. The rollback paragraph's *"every one of the twenty-four reverts
    independently"* does not hold. (§7, §2.5)
11. **The Reads tab is not one strip above a table** — it is N register panels, and the
    read log starts 2.6 screens down. (§3.1)
12. **`AssetUsageStrip`'s E3 exception asserts an absence that is not an absence.** (§3.2)
13. **The violation table files `BR-WRK-056` under "Screens 10, 14"**; its own evidence
    is screens 08 and 12. (§1)
14. **Counting the register: 28 rows, 4 withdrawn, 24 live.** The closing paragraph's
    *"Twelve live specifications"* is wrong, as `CR-092` §4 already says — **and so is
    the register's own preamble**, which says *"Three numbers are retired"* while the
    table strikes **four** (`AST-B-07`, `-08`, `-09` **and `AST-B-17`**).

**What the blueprint got right, and it is most of it:** the 31 drawn rows; the 38 keys
on `asset_dict()`; the 4-field client type; `channel` served and unrendered;
`final_read_id` served and unrendered; the three bare tables; the unbounded transport;
newest-first on assignments; `showExport` already conditional; rule 21's exemption (all
14 non-test asset feature files are on `route-b-migrated.txt` — checked); and the whole
of `BR-WRK-056`'s substance. Its as-built statements about this file held wherever I
could re-derive them.

---

## 9 · Defect rows this lane filed

| id | AST-B | what |
|---|---|---|
| `DEF-MET-4965` | `AST-B-02` | `BR-WRK-056`'s two doors do not exist on the asset detail page; and the server action set has no raise verb to gate them with |
| `DEF-MET-4966` | `AST-B-02` | `AssetDetail.test.tsx:807` asserts the door absent; the hold's reason expired when Work shipped |
| `DEF-MET-4967` | `AST-B-18` | the work-order list is fetched and 100% of its rows discarded; 4 of 24 keys typed; `priority` not served |
| `DEF-MET-4968` | `AST-B-23` | three hand-built in-asset tables: no search, filter, columns, download or pager, at both widths |
| `DEF-MET-4969` | — | raw channel codes on screen while the vocabulary ships in 11 catalogues; E3's stated absence is false |
| `DEF-MET-4970` | — | the Reads tab's per-register panels push the read log 2.6 screens below the fold |

`AST-B-16`, `AST-B-19`, `AST-B-21`, `AST-B-22` and `AST-B-24` are classified as
**changes** by `CR-092` §1 and carry no defect row from this lane; their findings and
the decisions each waits on are in §2, §4 and §7 above.

---

## Trace

* **Process:** `04-docs/02-decisions/12-engineering-plan.md` Addendum r11 ·
  `12-governance/13-change-process.md` · `12-governance/22-product-maintenance-process.md`
* **CR:** `12-governance/change-requests/CR-092-BRC01-assets-menu-blueprint.md` §3, §4, §6
* **Source blueprint:** artifact `2f979496-886a-47a2-a125-69035d1b3bff`,
  *The Assets menu, screen by screen*, read at `2.234.17` / `79c659d7d`; §03 (lines
  1085–1854), §09, §11, §12.
* **Rules touched:** `BR-WRK-056` (CONFIRMED) · `BR-WRK-051` (PROPOSED) · `BR-AST-006`
  · `BR-AST-029` · `BR-AST-030` · `NFR-3` · `NFR-5` · B14 rules 12, 13, 14, 16, 31 ·
  hard rules 1, 2, 3 · hard-won laws 1, 2, 6, 7
* **Sibling rows cited, not duplicated:** `DEF-MET-4951` (lane 6 — `NFR-3` on the registry)
