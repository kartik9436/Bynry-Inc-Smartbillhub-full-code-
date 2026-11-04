# CR-092-BRC01 · step 2 · lane 2 — ONE ASSET: what was built, what was left, and what it was proved against

**Lane:** 2 of 6 · **Step:** 2 (FIX) · **Date:** 2026-09-12 · **Branch:** `claude/hi-0jmv62`
**Base:** `ce623f444` · **Version shipped:** `2.237.6`
**Screens:** 08 Overview · 09 Reads · 12 Work & maintenance (`S50` / `AST-02`)
**Rows:** `DEF-MET-4965` `4966` `4967` `4968` `4969` `4970`
**Step 1's findings:** `CR-092-lane2-detail-step1.md` — read it first; this file only records what changed.

---

## The scoreboard, so the rest can be skipped

| row | what it was | status |
|---|---|---|
| `DEF-MET-4965` | `BR-WRK-056`'s two doors do not exist on the asset's own screen | **fixed** |
| `DEF-MET-4966` | a green test asserted the door absent, over a dead premise | **fixed** |
| `DEF-MET-4967` | the work-order list fetched and 100% of its rows discarded | **fixed** |
| `DEF-MET-4968` | three bare in-asset tables: no search, filter, columns, download or pager | **OPEN — not started, and why is below** |
| `DEF-MET-4969` | raw register codes (`tou_on`) printed to a clerk | **fixed** |
| `DEF-MET-4970` | the read log pushed below the fold by one chart panel per register | **fixed** |

**Proof:** `tsc` 0 · `eslint --max-warnings 0` 0 · `vitest run src/features/assets` **208 passed / 12 todo / 0 failed** across 10 files (162 across 7 before this lane and before the siblings' files landed) ·
**38 of 38 browser checks at 1280 AND 1440** (`10-scripts/cr092_lane2_asset_detail_walkthrough.mjs`).

---

## 1 · The headline — the door, and the test that was holding it shut

`BR-WRK-056` is CONFIRMED and names four ways into the raise-work-order form. The four
`RaiseWorkOrderCheckbox` ticks shipped at `CR-070` wave M; **the two on the asset's own
screen never did**, and `grep -c raiseWorkOrderPath AssetDetailPage.tsx` returned **0**
against 7 production call sites in five sibling files.

**Built.** The header offers `Raise work order` **first** — screen 08's own order,
`Raise work order · Reassign · Log repair · Retire` — on **every tab**, because `TC-3`
asserts the header action block is byte-identical across them. The Maintenance tab's
**Open work** panel carries the second, under the list it adds a row to, which is where
Figure 18 draws it. Both are `<Link>`s and not buttons-that-navigate, so the destination
is in the markup and a test can assert the ADDRESS rather than assert that a label exists
— the assertion `DEF-WRK-4051` was missing when two shipped screens pointed at nothing.

### The engineering decision `BR-AST-534` deliberately left open, and the reasoning

The PO ruled ***"a) Show it disabled, with the reason"*** and left to engineering whether
`row_actions()` (`BR-AST-006`) grows a `raise_work_order` verb or the control renders
outside it.

**It renders OUTSIDE it, gated on `behavior_class`, and NO SERVER CHANGE IS MADE.**

1. **`row_actions()` is the ASSETS module's vocabulary and this door is `apps/work`'s.**
   `apps/work/asset_door.py` states its own design as *"`apps/assets/**` gains no line of
   code at all — which is a stronger statement than 'assets writes nothing to
   `work_orders`', and it is the one a grep test can prove"*. Minting a Work verb inside
   `apps/assets/selectors.py` weakens that test's premise for a string.
2. **It would ride `asset_dict()` onto every registry row.** `row_actions()` feeds the
   LIST shape as well as the detail one, so the verb would be served on all 221 assets
   where nothing renders it — a served fact with no reader, hard-won law 2's shape.
3. **`hasAction()` can only HIDE, and the rule's whole content is that the control
   stays.** Every other header control here is hide-on-state. `BR-AST-534` asks for
   show-disabled-on-state. A mechanism whose only move is removal cannot express it.

`behavior_class` is already on every asset payload and is the same string `row_actions()`
itself branches on, so the client is reading the server's own fact rather than inventing
one. On a retired meter the control is **shown, disabled, titled *This asset is
retired.*** — four words (B14 rule 33 caps a refusal at six) — **and it is not a link**,
so a middle-click cannot open it either.

**The role reason and the state reason are one control with one sentence, and the STATE
one wins.** Both can be true at once (a View-only clerk on a retired meter). The state
reason is true for every role and does not change when permissions do.

### `DEF-MET-4966` — the test is INVERTED, at its own address, with the old assertion written out

`AssetDetail.test.tsx:811` ran `expect(html).not.toContain("Raise work order")` under the
comment *"No wo storage exists yet (Work is R5)"* — a premise that died the day
`apps/work` shipped with 27 migrations behind it.

It is **not deleted**. The case keeps its place, gains `DEF-MET-4966` in its name, asserts
the door is offered AND the address it opens, and carries the old assertion verbatim in a
comment above it. Deleting it would remove the only record that the door was ever pinned
shut, and that record is the finding.

> **A hold with no test that fires when it expires is a promise nobody is keeping.** This
> one had the opposite: a test that fired only if somebody tried to KEEP the promise.

---

## 2 · `DEF-MET-4967` — the rows were already on the screen and were thrown away

`listAssetWorkOrders` has exactly one consumer and that consumer read **only**
`maintenance_index`; `rows` and `total` were paid for on every Maintenance tab open and
discarded. **Nothing here adds a call** — the Open work panel draws the list that was
already arriving.

Columns, from Figure 18: `Work order # · Type · State · Raised · Expected completion ·
Technician`. The state is the same `StatusPill` and the same `workOrderStateTone` the
Orders queue draws, imported rather than re-derived. `isOpenOrder` is imported from
`buildViews` rather than re-typed — `planned · in_progress · blocked` is
`metering_seam.OPEN_WORK_ORDER_STATES` on the server, and a third hand-written copy is how
a list stops agreeing with itself.

**`AssetWorkOrderRow` is now an ALIAS of `ScopedWorkOrderRow`**, not a four-key interface.
`_scoped_page`'s own docstring is the argument: *"one row shape for every list of work
orders in this product, so the account tab, the premises tab, the dispatcher's queue and
this one cannot describe the same order four ways."* A second interface here was the
fourth description.

### ⚠ `priority` IS NOT ADDED, AND THE BLAST RADIUS IS WHY

Step 1 proved `priority` is **not served on this endpoint at all** — it is built by
`dispatch._priority_of` and reaches `_dispatch_row` (`dispatch.py:256`, `:414`, `:1140`)
and `mobile.py:170`, never `_scoped_row`. **`_scoped_row` is shared on purpose**, so
adding it there widens the **premises tab and the account tab in the same commit**.

`workEndpoints.ts` already carried this argument from the other side, written by the lane
that split `WorkOrderDispatchRow` off: *"Putting the dispatch fields on the base type
would have declared, in the type system, that those two routes send a priority and an
assignee — they do not."* **So the two columns that were free are built (`due_at`,
`technician`) and the one that is not is left, stated rather than smuggled in.** A
cross-screen server change belongs to whoever owns `AST-B-18`, sized as one.

**Two columns Figure 18 draws are deliberately absent:**
* **Raised by** — the blueprint's own field table says it: *"nothing serves this —
  `assigned_by` and `accepted_by` exist, `raised_by` does not"*. A column of dashes is not
  the drawing being followed.
* **Actions** (the eye and the swap) — those open Work's own screens and belong to the
  screen-12 merge, not to this defect row.

---

## 3 · `DEF-MET-4969` — the words existed and a comment said they did not

`metering.reads.channel.*` ships **seven keys in all eleven catalogues** and **six files**
in Meter Reads already resolve them. `AssetUsageStrip`'s exception **E3** asserted *"no
signed vocabulary maps a register to a display word, and inventing one here would be a
rule this screen does not get to write"*, and the read log one panel down drew no Channel
column at all.

**`channelLabel` lives in `assetsShared.tsx`**, not on either screen, because there are two
— the read log in `AssetDetailPage` and the register panels in `AssetUsageStrip` — and the
second cannot import from the first without a cycle (the first mounts it).

The **Channel column** is built, and **only when the rows carry more than one register**,
which is the same reasoning the Export column already follows: a flat meter's log would
otherwise carry a column repeating one word on every row. Figure 15 draws exactly this.

> ⚠ **WHERE WE DIVERGED FROM THE DRAWING, ON PURPOSE.** Figure 15 writes the registers as
> *Total* and *Peak demand*; the shipped catalogue says *Total register* and *Demand*. The
> catalogue wins — a second set of words for the same seven codes is the drift this
> repository keeps paying for — and the difference is filed here rather than followed.

---

## 4 · `DEF-MET-4970` — one chart panel, whatever the register count

**What it was:** one full panel per register — chart, date range, gap sentence, three
tiles — so a clerk who opened the Reads tab for the readings met N of them first, and
*"N of 12 months have no reading."* repeated once per register on one screen.

**What it is:** a meter with ONE register draws the plain panel screen 09's Figure 13
shows. A meter with more draws a `Disclosure` list — **the first open, the rest collapsed
rows** — and the whole of `DEF-798` survives it, which is the constraint that shaped the
fix rather than a picker or a tab strip:

* `Disclosure`'s own law is that **collapsing never hides a number**. The closed row
  carries the register's NAME, its own UNIT and its own average, and still says *not
  consumption* where that is true. Every register is named and figured on arrival.
* Nothing is blended and there is still **no code path that could produce a meter total**.
* A register PICKER would have hidden the other registers' existence behind a click. This
  hides only their derivation.

**Measured in Chromium on a four-register meter, both shapes on the same page:**

| width | all four panels open (the shape this was filed against) | collapsed |
|---|---|---|
| 1280 | **1,214px** (1.35 screens) | **907px** (1.01 screens) |
| 1440 | **1,214px** | **884px** (0.98 screens) |

⚠ **Step 1's `2,324px` is NOT re-measured and is not claimed here.** That was `M-7302` on
a tenant this database no longer holds in that shape; the numbers above are this lane's
own meter, seeded by this lane, and the walkthrough prints both so a reader can see the
size of the change rather than a bare pass.

### The structural check, because a pixel threshold is one I would have chosen myself

The browser check does not assert a fold position. It asserts that **however many
registers a meter has, exactly ONE full chart panel stands between the top of the page and
the read log**, and that every other register is a collapsed row. That is the fix stated
as a shape; a pixel bar drifts with the header's wrapping and would have been my own
invention.

---

## 5 · `DEF-MET-4968` — OPEN, and it is a sequencing fact rather than an effort one

`AST-B-23` asks the three in-asset lists to use `DataTable` and `FilterBar`. **It cannot
be built before `AST-B-19` (server-side paging)** without passing the whole list as one
page — which recreates inside the asset the exact *honest envelope over an unbounded
query* shape lane 6 filed on the registry as **`DEF-MET-4951`**. `DataTable` documents its
own `rows` prop as *"the CURRENT PAGE only — pagination is server-side (IS-2)"*.

Three endpoints are unbounded, not the two the register names: `/assets/{id}/reads`,
`/assets/{id}/assignments` **and `/assets/{id}/maintenance`**, which appears in no row of
the register at all. `/work-orders` is the only one of the four that already pages.

**Nothing was half-built toward it.** The row stays `open` with this paragraph as its
reason.

---

## 6 · The data — what was seeded, and why three findings could not be reproduced without it

Counted with `app.tenant_id` set (RLS `FORCE` is on, so an unscoped count returns 0 and
reads as an empty database):

| tenant | assets | reads | work orders | with `asset_id` | maintenance |
|---|---|---|---|---|---|
| brazosbend | 14 | 24 | 0 | **0** | **0** |
| oak-ridge | 74 | 202 | 23 | **0** | **0** |
| pine-hill | 135 | 518 | 42 | **0** | **0** |

**0 of 65 work orders anywhere carried an `asset_id`**, `asset_maintenance` held **0 rows
on every tenant**, and no meter's usage payload carried more than ONE register. So the
Open work panel, the maintenance history and the multi-register strip had never been drawn
by anything in this product, and a lane following REPRODUCE would have concluded the
defects were gone.

**Under the PO's ruling of 2026-09-12 — *"you can do actual figures"* — 57 rows were
seeded on ONE oak-ridge meter (`W-5001`), and every measurement in this document is over
rows this lane created:**

| what | rows |
|---|---|
| `meter_reads` — three TOU registers × three dates | 9 |
| `work_orders` — `WO-4908` in progress · `WO-4907` blocked · `WO-4900` done | 3 |
| `asset_maintenance` — one costed repair, one uncosted 2024 test | 2 |
| `meter_read_asset_monthly_usage` — four registers × twelve months | 45 |

`10-scripts/cr092_lane2_seed.sql` is the file, every statement an INSERT, every unchanged
column copied from a row the product itself wrote.

⚠ **THE FOURTH LINE IS THE ONE THAT IS NOT OBVIOUS, AND IT COST A WHOLE MEASUREMENT.**
`asset_usage` reads the **STORED** per-asset monthly row first (`BR-MET-141`, `OQ-421`'s
closure) and computes from reads **only when nothing is stored**. `W-5001` had a stored
row for `total` and nothing else, so seeding nine TOU reads changed no chart at all and
the strip went on drawing one register — while the browser check reported *"the read log
is above the fold"*, truthfully, **over a one-register meter**. That is law 7's *reporting
zero over a scope it silently excludes*, produced by this lane, in this lane's own check.
`source: "stored"` on the payload is what said so.

---

## 7 · Two of this lane's own checks were wrong before they were right

Both are recorded rather than quietly fixed, because each is one of law 7's named shapes
and each was found by looking at a number that could not move.

1. **The fold measurement used `boundingBox()`, which is VIEWPORT-relative** — and
   Playwright scrolls an element into view before clicking one. It printed **765px before
   and 765px after expanding every register**. That is not *"the layout did not move"*, it
   is *"the ruler moved with it"*: a check incapable of failing. It reads the document
   coordinate now.
2. **The register count matched every `[aria-expanded="false"]` on the page**, app shell
   included, and reported **five registers on a four-register meter**. It reads
   `data-register-list` now — a witness added for exactly this.

A third, caught the same way: the Open work panel's first test asserted `>Technician<`
**page-wide**, and that string is also the Maintenance history's own column header — so it
would have passed over a panel that drew no such column at all. It is scoped to the panel.

---

## 8 · Reds this lane did not cause, dated with the command law 7 asks for

Two suites outside this lane's scope are red on `ce623f444` and were red before this lane
started. `git log -S` on the failing files dates both to **2026-09-07**, five days before
this lane's base:

| suite | what it reports | dated |
|---|---|---|
| `components/ConfirmDialogTier.dom.test.tsx` | 32 call sites against 29 classified — `MachineKeysPage.tsx`, `OrderDetailPage.tsx`, `OrderEditPage.tsx` | `eff8fe404` / `a43849b99`, 2026-09-07 · **already filed as `DEF-GOV-4695`** |
| `components/regionalReachesTheScreen.dom.test.tsx` | one offender: `features/runbooks/history/RunHistory.tsx` | `9fcf59f32`, 2026-09-07 · **no defect row found — unfiled** |

Neither is touched by this lane. The second carries no row in the register and is reported
rather than closed.

---

## 9 · Where this diverges from the drawing, in one list

1. **Register words** — Figure 15 writes *Total* and *Peak demand*; the shipped catalogue
   says *Total register* and *Demand*, and the catalogue wins (§3).
2. **An unassigned technician** — Figure 18 draws a dash; the product says *Nobody yet*,
   and `dispatch._holder`'s own docstring argues for it (*"a blank cell reads as a bug"*).
   The premises and account tabs already print that exact key.
3. **Raised by** and **Actions** are not built — the first serves no data, the second
   belongs to the screen-12 merge (§2).
4. **The tab is still `Maintenance & repairs`, not `Work & maintenance`, and there are no
   `Open work` / `History` sub-tabs.** The merge is `AST-B-02`'s, not this defect row's;
   the Open work panel sits above the history inside the existing tab, in the drawn order.
5. **No toolbar on Open work.** The drawing gives it search, chips, download and columns;
   `DEF-MET-4968` is why (§5), and the drawing's own *Table controls* row says *Open work —
   no toolbar*, so only the chips are being deferred.

---

## Trace

* **Process:** `12-governance/22-product-maintenance-process.md` (this is MAINTENANCE — a
  user could not raise a job from an asset today) · `04-docs/02-decisions/12-engineering-plan.md` r11
* **CR:** `12-governance/change-requests/CR-092-BRC01-assets-menu-blueprint.md` §3a, §4a, §6a, §6b, §6c
* **Drawings:** `04-docs/05-modules/05-assets/wireframes/CR-092-assets-screens.html` screens
  08, 09, 12; and the PDF at full fidelity, pages 34, 47–50, 58–59 (Figures 13, 15, 18)
* **Skill:** `react-tailwind-css-ui-generator`, invoked before the first line of TSX and
  again before calling these screens done
* **Rules:** `BR-WRK-056` · `BR-AST-534` (built here) · `BR-AST-006` · `BR-AST-030` ·
  `BR-SHL-025` · `BR-MET-141` · `NFR-3` · B14 rules 21, 31, 33, 37 · hard rules 2, 3 ·
  hard-won laws 1, 2, 6, 7
* **Sibling rows cited, not duplicated:** `DEF-MET-4951` (lane 6 — `NFR-3` on the registry)
  · `DEF-GOV-4695` (the ConfirmDialog census)
