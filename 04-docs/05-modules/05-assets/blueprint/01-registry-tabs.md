# Assets blueprint § 02 — the registry's six tabs and its one dialog, drawing against code

**Scope.** Screens 01–07 of `05-prototype/01 Assets Menu Blueprint.pdf`, PDF pages 4–33,
plus the six remedy drawings on pages 139–151. Nine screens: Meters · Sub-meters ·
Behind the meter · Inventory · Lifecycle ×3 · Map · the Assign dialog.

**Product version measured:** `2.261.3` (`07-frontend/package.json:4`), branch tip
`11307c79`. **The document was read at `2.234.17` / `79c659d7` on 2026-09-10 and
re-measured 2026-09-11** — 27 change-level versions ago — so every as-built claim in
it was treated here as a hypothesis and re-checked against the code on this branch.

---

## How this was read, and one thing that had to be corrected

**Every layout detail below came from the PDF page images**, rendered with
`python3 10-scripts/pdf/pdf_render.py "05-prototype/01 Assets Menu Blueprint.pdf"
/tmp/laneA 2 <pages>` and opened one page at a time with the Read tool — B14 rule 42,
PO 2026-09-13: *"When you use images to create screens your accuracy is higher; hence
dont create screens using only Text"*. Pages 4–33 and 139–151, 43 images.

⚠ **Two files in the tree are DERIVED copies of these wireframes and were NOT used as
the specification** (PO clarification, 2026-09-13 — hard-won law 5, one generated file
committed once):

* `04-docs/05-modules/05-assets/wireframes/CR-092-assets-screens.html` — an HTML
  re-drawing of the 56 wireframes;
* `04-docs/05-modules/05-assets/08-screen-layouts.md` — a prose index of them.

**Nothing in this file's layout, field, label, column or ordering claims came from
either.** The one use made of them was factual history, which the clarification
permits: `08-screen-layouts.md` records that screens **05a, 05b and 05c landed in
`2.237.5`** and screen 14 in `2.239.9`. `CR-092-assets-screens.html` was touched once,
by a one-line `grep -l`, purely to confirm that the sentence *"N of 126 assets have
coordinates"* exists **only** there and nowhere in the product — the sentence itself was
read off PDF page 30.

⚠ **And reading it as history rather than as specification immediately caught it drifting.**
`08-screen-layouts.md` line 112 says `DEF-MET-4962` is *"still open"*. **It is not** —
the defect register has it `fixed` at `2.237.8`, and the code proves it. A second copy
went stale in the two days since it was written, which is exactly why the PO ruled it
out as a source.

---

## The two halves of the document, and which half each screen is judged against

Page 2 and page 3 state the convention and it is visual: a **grey-rail passage is a
DESCRIPTION** of what the code did on 2026-09-11 and *"commits nobody to anything"*; a
**red accent card is a COMMITMENT**. Where a screen carries both an as-built figure and
a redrawn one, the redrawn one is the target.

In this section that means:

| Screen | Judged against |
|---|---|
| 01 Meters | **Figure 52** (remedy R2), not Figure 1 |
| 02 Sub-meters · 03 Behind the meter · 04 Inventory | Figures 2 / 3 / 4, plus **R6**'s description row |
| 05a · 05b · 05c | Figures 5 / 6 / 7 — these ARE the remedy, drawn in § 02 rather than § 10 |
| 06 Map | Figure 8, plus commitment `AST-B-06` |
| 07 Assign dialog | Figure 9 — **NO COMMITMENT**, so the drawing is the whole of it |

---

## 01 · Meters — `/:tenant/assets?tab=meters`, and the bare `/:tenant/assets`

### What the drawing shows

**Figure 1 (as-built, p7)** and **Figure 52 (R2, redrawn, pp141–142)** share everything
but five details, so they are described once.

Top to bottom, off the image:

* **Topbar** — `SMARTBillHub` over the rail; the word `Assets` at the left of the bar; a
  search box with a magnifier and the placeholder `Search` on the right, then `?` and a
  bell.
* **Left rail, thirteen items**, in this order: Dashboard · Plans & Rates · Premises ·
  Assets *(current, carrying a ▽ marker)* · Accounts · Reads · Billing · Payments ·
  Work · Finance · Runbooks · Reports · Settings. Above them the tenant chip
  `BB  Brazos Bend Utilities`; below them `v2.234.17` and `DW  Dana Whitfield / System
  Admin`.
* **Page head** — the title `Assets`, large, left. **One right-aligned action**,
  `+ Add asset`, drawn as an outlined accent button.
* **Tab strip, six tabs**, left-aligned under the head, `Meters` active with an accent
  underline: `Meters · Sub-meters · Behind the meter · Inventory · Lifecycle · Map`.
* **A description slot directly under the tab strip** — on Figure 1 it holds only the
  annotation *"no description — the tab renders none"*; on **Figure 56 (R6, p150)** the
  same slot holds the sentence **`Meters, where they sit, and their state`**.
* **A KPI strip of FOUR cells**, full width, separated by vertical hairlines. Each cell
  is a small uppercase label, then a large figure, then — on three of the four — a small
  detail line beneath:

  | label | figure | detail line |
  |---|---|---|
  | `METERS IN SERVICE` | `103` | `7 masters · 9 subs · 1% AMI` |
  | `NEEDS REPAIR` | `0` | *(none — the cell is deliberately bare)* |
  | `IN INVENTORY` | `6` | `Ready to assign` |
  | `PAST CERTIFICATION AGE` | `0` | `Exchange due this year` |

  Figure 1 annotates the strip ② *"ONE STRIP, ALWAYS WITH FIGURES. TODAY IT RENDERS
  FOUR EM DASHES UNLESS THE WHOLE SET IS ON ONE PAGE — THAT IS THE DEFECT, NOT A SECOND
  STATE TO BUILD"*.
* **A toolbar in one row**: `[Search asset #, serial, manufacturer, model or address…]`
  then `[All]` then `[+ Filter ▾]`, a gap, and two square icon buttons hard right —
  `[↓]` (download) and `[▦]` (columns).
* **A table of TEN visible columns**, in this order and this alignment:
  `SELECT` (a checkbox) · `METER #` · `TYPE` · `ROLE` · `SERVICE` · `MULT.` ·
  `ASSIGNED TO` · `INSTALLED` · `STATUS` · `ACTIONS`. Headers are small uppercase. The
  meter number is an accent link. `STATUS` is a pill — outlined neutral for `Inventory`,
  outlined green for `Installed`.
* **Row actions vary by row state** in Figure 1: an inventory row draws **3** glyphs, an
  installed row draws **5**, and there is no overflow control on either.
* **A pagination footer**: `1–50 of 109` and `Rows per page 50 100 200 500 1000` on the
  left; `← Page 1 of 3 →` on the right.
* **One sentence under the table**: `Every change here is recorded in the audit log by
  the server.`

**The five things Figure 52 changes** (its own numbered legend, p142):

1. The KPI figures are real, from *"a new aggregate read over the whole filtered set,
   not the page"* — `NEW READ`. Same four cards, same labels, same order, same detail
   lines; *"only the value changes, from a dash to a figure"*.
2. `METER # ⇅` replaces `METER # ▲` — rule 13, CHANGED.
3. Row actions become `👁 ✎ ⋯` — two visible, the rest behind an overflow. The
   carry-over is explicit that **nothing is dropped**: *"All six survive."*
4. The pager gains first and last: `⇤ ← Page 1 of 3 → ⇥`.
5. Everything else — title, Add, six tabs, four cards, the toolbar, ten columns, the
   range, the page-size list, the audit line — is stamped **UNCHANGED**.

### What the code does today

* `07-frontend/src/features/assets/AssetRegistryPage.tsx:797-847` declares the six tabs
  plus Imports, each with its label, explainer and primary action.
* `:812` — `explainer: id === "sub_meters" ? t(\`assets.explainer.${id}\`) : undefined`.
  **Meters passes `undefined`, so the description slot renders nothing.**
* `:962-1000` — the four KPI cards, labels `assets.kpi.metersInService` /
  `needsRepair` / `inInventory` / `pastCertification`, details
  `{{masters}} masters · {{subs}} subs · {{ami}}% AMI` / *(none)* / `Ready to assign` /
  `Exchange due this year`. **Every label and every detail line matches the drawing
  character for character.**
* `:868-881` — `metersKpis(rows, kpisComplete, servedKpis)`.
  `assetsShared.tsx:311-348`: **when a served block arrives it wins outright**; the
  browser count survives only as a fallback.
* `06-backend/apps/assets/selectors.py:731-796` — `asset_kpis(tab)` counts the tab's
  whole population in SQL: three queries for Meters, one for Behind the meter.
  `apps/assets/api.py:144-146` attaches it to the list answer.
* `:310-374` — the column set. Ten visible on Meters, in the drawn order; `meter_type`,
  `read_method`, `unit`, `serial_no` and `manufacturer` are declared `defaultVisible:
  false` and live in the `▦` chooser.
* `:663-729` — the actions cell. Up to **six** `RowAction`s: view, edit, reassign/assign,
  log repair, retire, delete. `components/RowActions.tsx:52-57` is a bare
  `inline-flex … flex-nowrap` that **does not cap**.
* `components/RowActions.tsx:237-266` — `RowActionsMore`, the `…` overflow, **exists in
  the kit**. `grep -rln RowActionsMore 07-frontend/src` returns exactly two files:
  the component itself and `features/metering/UnitsListPage.tsx`. Assets does not use it.
* `components/DataTable.tsx:934-978` — the pager. Range, page-size select, `‹`, `›`.
  **No `Page x of y` and no first/last.** `table.pager.pageOf` exists in all eleven
  catalogues and is rendered only by `components/ListPager.tsx:69`, which 9 files mount;
  `DataTable`, which 54 files mount, ignores it.
* `components/DataTable.tsx:54-59` — `nextSortState` has two branches, asc↔desc, no
  clear. `:846-851` draws `▲`/`▼` **only on the sorted column**; an unsorted sortable
  header draws no glyph at all.
* `:1131` — `<p className="settings-audit-line">{t("assets.auditLine")}</p>` =
  *"Every change here is recorded in the audit log by the server."* ✓
* `06-backend/apps/assets/api.py:118-127` — `asset_list` returns a **queryset** and
  `StandardPagination` slices it, so `LIMIT`/`OFFSET` reach SQL. The four filters that
  used to run in Python (`assigned`, `test_due`, `premises_id`, `service`) are queryset
  filters at `selectors.py:696-726`.
* `docker-compose.yml:130, :329, :461, :892-893` — one named `artifacts:` volume mounted
  at `/app/var/artifacts` on `backend`, `celery` and `celery-billing`. The file had **no
  top-level `volumes:` key at all** before this.

### Gap table — screen 01

| # | gap | drawing says | code says | class | fixed since 2.234.17? |
|---|---|---|---|---|---|
| 1 | KPI figures | four real numbers, always | served by `asset_kpis`; browser count is the fallback | WIRING | **YES** — `DEF-MET-4953`, `2.237.5` |
| 2 | Export saves `file.json` | pressing export gives a CSV (`AST-B-20`) | ~~one shared `artifacts:` volume across all three services~~ ⚠ superseded 2026-10-02: S3 at `t/<web name>/export/…`, no volume | MISSING PLUMBING | **YES** — `DEF-MET-4954`, `2.237.5` |
| 3 | `NFR-3` — no page reaches SQL, four filters in Python | not drawn; stated on p139 | queryset sliced by the paginator; all seven filters in SQL | MISSING PLUMBING | **YES** — `DEF-MET-4962`, `2.237.8` |
| 4 | Row actions capped at two plus `⋯` | `👁 ✎ ⋯` | up to six glyphs, no overflow | LAYOUT | **NO** — ruled out of scope |
| 5 | First / last page `⇤ ⇥` | drawn on the pager | `‹ ›` only | LAYOUT | **NO** — ruled out of scope |
| 6 | `Page x of y` | `← Page 1 of 3 →`, on both figures | absent from `DataTable`'s pager | LAYOUT | **NO** — ruled out of scope |
| 7 | `⇅` on sortable headers, third click clears | `METER # ⇅` | `▲`/`▼` on the sorted column only; two states | LAYOUT | **NO** — ruled out of scope |
| 8 | The tab's description | `Meters, where they sit, and their state` | `explainer: undefined` — the slot renders nothing | WIRING | **NO** — still live |

**Gaps 4–7 are blocked by a PO ruling, not by plumbing.** 2026-09-12, verbatim:
***"(b). It's the right fix and it touches 54 lists at once. That risk doesn't belong
inside an Assets pass"***. They left `CR-092-BRC01` for `CR-093-BRC01`, where they are
five rows: `DEF-SHL-4946` (sort), `DEF-SHL-4947` (title sizes, since fixed),
`DEF-SHL-4948` / `DEF-2453` (row-action cap), `DEF-SHL-4949` (KPI gap), `DEF-449`
(pager). `DataTable` has **54 non-test mounts**; `PageHeader` has 137.

**Built and not drawn on this screen**, each correct and none needing action: the
`+ Filter ▾` panel behind the button carries **seven** declared filters (status, type,
meter type, service, premises, assigned, test due) with the premises group rendered as a
removable chip rather than 500 checkboxes (B14 rule 9); the selection bar that appears
over the table when rows are ticked; and `?terms=` free-text resolution from `CR-089 G1`.

---

## 02 · Sub-meters — `?tab=sub_meters`

### What the drawing shows (Figure 2, p11)

Identical frame to screen 01, with four differences and one absence:

* Page-head action reads **`+ Add sub-meter`**.
* **No KPI strip** — the table starts straight under the description.
* **A description IS drawn**, in the slot under the tab strip:
  *"Sub-meters hang off a master meter and bill their own unit. Click one for its
  detail; add, edit, reassign, or retire from the row."* — two sentences, 24 words.
  **R6 (p151) proposes `Sub-meters, their master, and what they read` — 7 words**, and
  the carry-over says why the second sentence goes: *"it describes the row actions,
  which the row actions already describe."*
* **Nine columns**: `SELECT · SUB-METER # · PARENT / MASTER · SERVICE · UNIT ·
  LAST READ · INSTALLED · STATUS · ACTIONS`. `LAST READ` is right-aligned and draws `—`
  on all three rows.
* Footer `1–9 of 9 · Rows per page 50 100 200 500 1000` · `← Page 1 of 1 →`.
* Five row-action glyphs on every row (all three rows are `Installed`).

### What the code does today

`AssetRegistryPage.tsx:338-350` — `parent · service · assigned_to` (labelled
`assets.col.unit`) · `last_read` (`numeric: true`, so right-aligned) · `installed` ·
`status`, plus the shared `select` / `asset_no` head and `actions` tail. **Nine visible
columns, the drawn order exactly.** `assets.col.assetNo.sub_meters` = `'Sub-meter #'`,
`assets.col.parent` is the `Parent / master` header. `:812` passes this tab's explainer,
so it is the one tab of the six whose description slot is filled.

`assets.explainer.sub_meters` is now **`'Sub-meters bill their own unit.'` — 5 words.**
It was cut from the drawn 24 on 2026-09-12 (`DEF-MET-4961`, `2.237.5`), in all eleven
catalogues, through `10-scripts/i18n_fanin.py` rather than a re-serialisation.

### Gap table — screen 02

| # | gap | drawing says | code says | class | fixed since 2.234.17? |
|---|---|---|---|---|---|
| 1 | The description | `Sub-meters, their master, and what they read` (7 w) | `Sub-meters bill their own unit.` (5 w) | CONTENT | **PARTLY** — the 24-word defect is fixed; the words are not the drawn words |
| 2 | Row-action cap | two plus `⋯` | five glyphs | LAYOUT | NO — ruled out of scope |
| 3 | First / last page | `⇤ ⇥` | absent | LAYOUT | NO — ruled out of scope |
| 4 | `Page x of y` | `← Page 1 of 1 →` | absent | LAYOUT | NO — ruled out of scope |
| 5 | `⇅` + third click | drawn | `▲`/`▼`, two states | LAYOUT | NO — ruled out of scope |

⚠ **Gap 1 is worth a ruling, not a silent choice.** B14 rule 41 (ratified 2026-09-13) says
*"it is expected that Product UI will match extactly the way it is given in Blueprint
document"*. The shipped sentence obeys rule 32's budget and rule 33's six-word cap, and
it is **not** what R6 drew. The same applies to Inventory, Lifecycle and Map below —
**four tabs, four sentences, one decision.**

---

## 03 · Behind the meter — `?tab=behind_the_meter`

### What the drawing shows (Figure 3, p14)

* Page-head action reads **`+ Add device`**.
* The description slot carries the annotation *"no description — the tab renders none"*
  and, under it, *"same — `assets.explainer.behind_the_meter`, eleven catalogues, no
  renderer"*. **R6 proposes `Customer-side devices, their capacity and test dates`** —
  7 words.
* **A KPI strip of THREE cells**, no detail line on any of them:
  `DEVICES  7` · `EXPORTING DEVICES  0` · `EXPORTED · AUGUST  780 kWh`.
* Toolbar identical to screen 01.
* **Nine columns**: `SELECT · DEVICE # · TYPE · PREMISES · UNIT · METER ·
  EXPORT CAPACITY · NEXT TEST · STATUS · ACTIONS`. The p15 field table adds that
  **Warranty is a tenth column, hidden by default.**
* Rows: `BF-0001 Backflow preventer / 401 Quarry Hill Ct · Unit 1 / — / — / Jun 2026`;
  `BT-0001 Battery storage / 88 Cypress Row · Unit 1 / E-5001 / — / —`;
  `CE-0001 Comms endpoint / 12 Bayou Bend · Unit 1 / E-5002 / — / —`.
* Footer `1–7 of 7 · Rows per page 50 100 200 500 1000` · `← Page 1 of 1 →`.

⚠ **The document corrects its own version one on this page (p13, p15):** it had said the
*Exported* card *"is always the stated dash"*, on the authority of an `exceptions:`
footer in `AssetRegistryPage.tsx` that had gone stale. The running app shows `780 kWh`.
That is hard-won law 1 in mirror form — a comment claiming an ABSENCE the code no longer
has — and it was closed as `DEF-MET-4964`.

### What the code does today

`AssetRegistryPage.tsx:1003-1040` — three cards: `assets.kpi.devices`,
`assets.kpi.exportingDevices`, and `assets.kpi.exportedMonth` = `'Exported · {{month}}'`
whose value is the served `export_rollup.totals`, each quantity printed **with its own
unit** and joined by `·`, never summed across units (hard rule 3). No detail line on any
of the three. ✓

`:355-371` — nine visible columns in the drawn order, `warranty` declared
`defaultVisible: false`. ✓

`:842` — this tab is **not** in the `["inventory","lifecycle","map"]` list that gets an
explainer, and `:812` gives one only to `sub_meters`. **The slot renders nothing.**
`assets.explainer.behind_the_meter` exists in all eleven catalogues at 10 words and
reaches no screen.

`assets.action.add.behind_the_meter` = **`'+ Add behind-the-meter asset'`**.

### Gap table — screen 03

| # | gap | drawing says | code says | class | fixed since 2.234.17? |
|---|---|---|---|---|---|
| 1 | `DEVICES` / `EXPORTING DEVICES` figures | real numbers | served by `asset_kpis` | WIRING | **YES** — `DEF-MET-4953`, `2.237.5` |
| 2 | `EXPORTED · AUGUST` | a real quantity with its unit | `export_rollup.totals`, quantity + unit | — | **already true**; the stale trailer claiming otherwise is fixed (`DEF-MET-4964`) |
| 3 | Page-head action label | `+ Add device` | `+ Add behind-the-meter asset` | CONTENT | **NO** |
| 4 | The tab's description | `Customer-side devices, their capacity and test dates` | nothing renders | WIRING | **NO** |
| 5–8 | The four shared-table rows | as screen 01 | as screen 01 | LAYOUT | NO — ruled out of scope |

---

## 04 · Inventory — `?tab=inventory`

### What the drawing shows (Figure 4, pp16–17)

* **No page-head action at all.** p17 states it: *"Primary action — None — deliberately.
  These rows are aggregates, not creatable things."*
* A description IS drawn: *"Assets you own but have not installed. Stock here is what
  dispatch checks before assigning a meter exchange."* — 18 words. **R6 proposes
  `Spare assets on the shelf, and their value` — 8 words.**
* **A KPI strip of TWO cells**: `UNINSTALLED ASSETS  8` detailed `$1,511.00 at cost`;
  `AGED OVER 12 MONTHS  4` detailed `Warranty clock already running`.
* Annotation ② over the table: *"NO TOOLBAR ON THIS TABLE — AGGREGATE ROWS, BY DESIGN"*.
  There is **no search box, no filter row, no `↓`, no `▦` and no pagination footer.**
* **Six columns**, the last three numeric and right-aligned:
  `ASSET TYPE · SERVICE · COUNT · UNIT COST · VALUE · SUPPLIER`.
* Four rows. The asset-type name is an accent link. **The `Meter` row's UNIT COST cell
  carries a second, smaller line under the average — `$164.00 – $182.00`** — where the
  group spans prices.
* Below the table, left-aligned, one outlined accent button: **`Parts in Work →`**.
* p16's grey rail names what the PO cut on 2026-08-22 — *"Launch with counts & costs
  only"*: the Yard / On-vans split, a `Reorder at` column and its three statuses, a
  `Raise reorder` button and a stock-count import. **Out of scope, ruled — not a gap.**
* The same rail records that `Parts in Work →` was *"disabled for two waves with the two
  words `Work R5` after the screen it points at had already shipped"*, and that **it is
  live now**.

### What the code does today

`AssetInventoryTab.tsx:112-135` — two KPI cells, `assets.stock.kpi.uninstalled`
detailed `'{{amount}} at cost'`, and `assets.stock.kpi.aged` detailed
`'Warranty clock already running'`. ✓

`:137-200` — a plain `<table>` (the detail-panel table, not `DataTable`) with exactly the
six drawn headers, `count` / `unitCost` / `value` right-aligned, and — at `:176-185` —
the unit-cost range rendered as a smaller block line under the average whenever
`unit_cost_min !== unit_cost_max`. ✓

`:212-217` — `Parts in Work →` is a live `Button` navigating to `WORK_PARTS_ROUTE`. **No
disabled state, no `Work R5` string anywhere in the file.** ✓

`AssetRegistryPage.tsx:840-847` — this tab gets `explainer: t("assets.explainer.inventory")`
= **`'Assets you own, not yet installed.'`**, 6 words, cut from 18 on 2026-09-12.

⚠ `06-backend/apps/assets/selectors.py:2223-2225, :2349` — **`stock_view` now takes
`page` and `per` (default 50) and answers a `rows_window` beside the rows.**
`07-frontend/src/api/endpoints.ts:8964-8966` — `getAssetStock()` sends **no parameters**
and its `AssetStockView` type declares **no window**.

### Gap table — screen 04

| # | gap | drawing says | code says | class | fixed since 2.234.17? |
|---|---|---|---|---|---|
| 1 | `Parts in Work →` disabled over `Work R5` | live | live, and the file says so about itself | WIRING | **YES** — live since `CR-070` wave M |
| 2 | The tab's description | `Spare assets on the shelf, and their value` (8 w) | `Assets you own, not yet installed.` (6 w) | CONTENT | **PARTLY** — 18-word defect fixed, words differ from the drawing |
| 3 | The served `rows_window` reaches nothing | not drawn — a fix made after the document | server windows to 50 and describes it; the client asks for no page and reads no window | WIRING | **NO — new, and not on any register** |
| 4 | Empty state | *"Nothing in stock — every asset is installed or retired."* | one `<td colSpan={6}>` rather than the kit's `empty` block | LAYOUT | NO — low; the sentence is right, the container is not the kit's |

**Gap 3 is low-blast-radius here and high on 05a and 06** — a stock row is one asset
TYPE, so a tenant needs 51 distinct types to lose one. It is listed because it is the
same single wiring fault in all three places and wants one fix, not three.

---

## 05a · Lifecycle · Certifications & tests due — `?tab=lifecycle&section=certifications`

**Chip: NEW BUILD.** ⚠ **It is built. It landed in `2.237.5` on 2026-09-12**
(`CR-092-BRC01` step 2 lane 1, `DEF-MET-4955`) — two days after the document was read.
`AssetLifecycleTab.tsx` is 741 lines and its own header says so:
*"REBUILT 2026-09-12 … as screens 05a · 05b · 05c: three sub-tabs on the shared
DataTable in place of three hand-built stacked tables."*

### What the drawing shows (Figure 5, p19)

* Page head `Assets`, **no primary action** — p19: *"None — this is a worklist. The
  row's ✎ is the action."*
* Six tabs, `Lifecycle` active.
* **Description ① under the tab strip**: *"What is falling due and what is wearing out."*
* **A SECOND-LEVEL tab strip beneath it, three tabs**, `Certifications & tests due`
  active with an accent underline: `Certifications & tests due · Warranty & supplier ·
  Age & replacement forecast`.
* **Description ② under the sub-tab strip**: *"What is falling due, oldest lapse first."*
* **Toolbar**: `[Search asset # or premises…]` `[All]` `[Overdue ×]`
  `[Due within 90 days ×]` `[+ Filter ▾]` … `[↓]` `[▦]`.
* **Seven columns**, two carrying `⇅`:
  `ASSET ⇅ · TYPE · PREMISES · REQUIREMENT · DUE ⇅ · STATUS · ACTIONS`.
* Three rows. `STATUS` is a pill: `Overdue` accent-outlined, `Due soon` amber,
  `Scheduled` neutral. `REQUIREMENT` reads as a sentence — `Annual test`,
  `Certification, every 96 months`.
* **Two row-action glyphs and no more**: a wrench and an eye. p21's field table names
  them ⑦ `Raise work order → /assets/{id}/work-orders/new` and ⑧ `View → /assets/{id}`.
* Footer `1–3 of 3 · Rows per page 50 100 200 500 1000` · `← Page 1 of 1 →`.
* p20 states **Due ascending is the default** *"because the oldest lapse is the one that
  matters"*, and that the empty state keeps the as-built sentence *"No certifications or
  tests are on the calendar."*
* p21's legend calls seven things NEW or CHANGED: the sub-tab strip (rule 12), search
  (rule 19), filter chips (rule 12), the column chooser (rule 14), sortable headers
  (rule 13), row actions capped at two (rule 15), and the pagination footer (rule 16).
  The carry-over reconciles `9 as-built − 0 removed + 8 new = 17`.

### What the code does today

* `AssetLifecycleTab.tsx:136-145` — `LIFECYCLE_SECTIONS = ["certifications","warranty",
  "forecast"]` and `sectionFromParam`, which falls back rather than erroring on an
  unknown value (`BR-SHL-011`, the sub-tab is URL state).
* `:527-546` — the sub-tab strip, `role="tablist"`, three buttons in the drawn order,
  active one carrying `border-b-accent font-semibold text-accent`.
* `:548-549` — `<p className={SECTION_NOTE}>{t("assets.lifecycle.certs.explainer")}</p>`
  = **`'Oldest lapse first.'`** (3 words).
* `AssetRegistryPage.tsx:840-847` — the Lifecycle tab's own explainer =
  **`'What falls due, what wears out.'`** (6 words).
* `:271-336` — `certConfig`: `searchFields: ["asset_no","premises"]`,
  `searchPlaceholder` = `'Search asset # or premises…'`, **`defaultSort: { sort: "due",
  dir: "asc" }`**, one `status` filter with four options (`Overdue`, `Due within 90
  days`, `Scheduled`, `In date`), and **seven columns in the drawn order**:
  `asset_no` (sortable, identity, an accent `<Link>`) · `type_name` · `premises` ·
  `requirement` · `due` (sortable) · `status` (a `StatusPill`, tone `danger` / `warning`
  / `neutral` / `success`) · `actions`.
* `:315-334` — **exactly two** `RowAction`s: `WrenchIcon` → `raiseWorkOrderPath(row.id)`,
  gated on `writeBlockedReason`; `EyeIcon` → `assetDetailPath(row.id)`.
* `:551-578` — the `DataTable` with a `FilterBar` in `filterBarSlot` and an `empty`
  block carrying title + helper.
* `:161-169` — `requirementLabel` derives the sentence from the served `requirement`
  object, so the server never hardcodes a per-asset string.

⚠ **And the one that matters.** `06-backend/apps/assets/selectors.py:2415-2422, :2471,
:2586-2587`:

```
certifications.sort(key=lambda row: (row["due"], row["asset_no"]))
certifications_page, certifications_window = page_window(certifications, page=page, per=per)
…
"certifications": list(certifications_page),
"certifications_window": certifications_window,
```

`WINDOW_DEFAULT_PER = 50` (`selectors.py:513`). `api.py:227-233` reads `page` and `per`
off the query string. **`07-frontend/src/api/endpoints.ts:9034-9036` sends neither, and
`AssetLifecycleView` at `:9024-9032` declares no window field.**
`grep -rn "certifications_window" 07-frontend/src` returns nothing; the only readers of
the three window keys anywhere are `selectors.py` itself and
`06-backend/tests/test_cr092_asset_paging.py`.

So `AssetLifecycleTab.tsx:483-489` calls `clientPage(data.certifications, …)` over a
list that is **already only the server's first fifty**, and `totalRows={certs.total}` is
the count of that fifty.

### Gap table — screen 05a

| # | gap | drawing says | code says | class | fixed since 2.234.17? |
|---|---|---|---|---|---|
| 1 | The whole screen — sub-tabs, toolbar, sort, columns, pager, empty state | a NEW BUILD | built, 7 columns, Due-asc default, two icon actions | — | **YES — `2.237.5`, `DEF-MET-4955`** |
| 2 | The served `certifications_window` reaches nothing | not drawn — the server half landed after the document | 51st cadenced asset onward is unreachable; the footer reports the window as the total | WIRING | **NO — new, and not on any register** |
| 3 | Two filter chips at once | `Overdue ×` **and** `Due within 90 days ×` | `TableRequestState.filters` is `Record<string,string>` — one value per filter, so one chip | LAYOUT | NO — the single-select divergence is `OQ-306`, open |
| 4 | `⇅` on `ASSET` and `DUE` | drawn on both | no glyph until the column is sorted | LAYOUT | NO — ruled out of scope |
| 5 | `Page x of y`, first / last | drawn | absent | LAYOUT | NO — ruled out of scope, and the file's own trailer says so |

⚠ **Gap 2 restated in one sentence, because it is the sharpest finding in this scope:**
the server was taught to page and the screen was never taught to ask, so on any tenant
with more than fifty cadenced assets screen 05a shows fifty rows, a footer reading
`1–50 of 50`, and one page — and `tsc`, 37 lifecycle cases and 20 tab cases all pass,
because the seeded tenant has three rows.

---

## 05b · Lifecycle · Warranty & supplier — `?tab=lifecycle&section=warranty`

**Chip: NEW BUILD. Built, `2.237.5`.**

### What the drawing shows (Figure 6, pp22–23)

Same frame as 05a, `Warranty & supplier` active on the sub-tab strip.

* Description ② : *"Who covers what, and until when."*
* Toolbar: `[Search supplier or asset group…]` `[All]` `[Covered ×]` `[+ Filter ▾]` …
  `[↓]` `[▦]`.
* **Seven columns, three carrying `⇅`**: `ASSET GROUP ⇅ · SUPPLIER ⇅ · UNITS ·
  COVER ENDS ⇅ · UNDER WARRANTY · STATUS · ACTIONS`. `UNITS` and `UNDER WARRANTY` are
  right-aligned counts.
* Five rows drawn of nine. `COVER ENDS` is a month-year (`Mar 2030`, `Jan 2031`) or `—`.
  `STATUS` is a `Covered` pill or `—`.
* **One row action** — an eye. p25's carry-over: *"This table had no row action at all."*
* Footer `1–9 of 9 …` · `← Page 1 of 1 →`.
* p23: sort on `Cover ends` is *"the one that answers what falls out of warranty this
  year"*; the empty state keeps *"No supplier is recorded on any asset yet."*
* p25's carry-over reconciles `8 − 0 + 7 = 15`.

### What the code does today

`AssetLifecycleTab.tsx:339-405` — `warrantyConfig`. `searchFields:
["supplier","type_name"]`, placeholder `'Search supplier or asset group…'`, a `cover`
filter with `Covered / Expired / No cover recorded`, and the **seven drawn columns in
the drawn order**: `type_name` (sortable) · `supplier` (sortable) · `units`
(`numeric: true`) · `cover_ends` (sortable, `monthYear`) · `under_warranty`
(`numeric: true`) · `status` · `actions`. `:394-404` — **one** `RowAction`, an
`EyeIcon` to `groupDrillPath(row)`, which carries the served `tab` because a client
cannot derive one (a battery group is not on the Meters tab).

`:548` equivalent at `:583` — `assets.lifecycle.warranty.explainer` =
**`'Who covers what, until when.'`** (5 words) against the drawn *"Who covers what, and
until when."*

`selectors.py:2418-2422` explains why this list is **not** windowed: warranty groups key
off `(type, supplier)` and are *"bounded by how many kinds of thing a utility buys rather
than by how many it owns"*, so they are served whole, deliberately. **Gap 2 of 05a does
not apply here.** ✓

### Gap table — screen 05b

| # | gap | drawing says | code says | class | fixed since 2.234.17? |
|---|---|---|---|---|---|
| 1 | The whole screen | a NEW BUILD | built, 7 columns, three sortable, one eye action | — | **YES — `2.237.5`** |
| 2 | `⇅` on three headers | drawn | no glyph until sorted | LAYOUT | NO — ruled out of scope |
| 3 | `Page x of y`, first / last | drawn | absent | LAYOUT | NO — ruled out of scope |

---

## 05c · Lifecycle · Age & replacement forecast — `?tab=lifecycle&section=forecast`

**Chip: NEW BUILD. Built, `2.237.5`.**

### What the drawing shows (Figure 7, p26)

* Description ② : *"What wears out next, and what it costs."*
* Toolbar: `[Search asset group…]` `[All]` `[Past life ×]` `[+ Filter ▾]` … `[↓]` `[▦]`.
* **Seven columns, three carrying `⇅`, five right-aligned**:
  `ASSET GROUP ⇅ · AVG AGE ⇅ · EXPECTED LIFE · PAST LIFE · DUE WITHIN 12 MO ·
  REPLACEMENT COST ⇅ · ACTIONS`.
* Four rows: ages as `0.4 yrs` / `5.4 yrs`, lives as `12 yrs` / `5 yrs`, counts as bare
  integers, cost as `—` or `$857.00`.
* **One row action** — an eye.
* Footer `1–10 of 10 …` · `← Page 1 of 1 →`.
* **The `Asset value` panel is drawn as REMOVED** — p27 strikes through row ⑦
  *Buy value / Present value* and stamps it `REMOVED`; p28's carry-over quotes the
  instruction of **2026-09-11, *"remove this - Asset value"***, and states the cost in
  full: *"the two figures are computed nowhere else in the product, so a person who used
  them loses them entirely."* It is the document's **only field-bearing removal**.
* **Nothing else is drawn below the table** — no Programme total, no Turn-into-work
  panel. p28's own arithmetic notes the carry-over never dispositioned either.

### What the code does today

`AssetLifecycleTab.tsx:407-458` — `forecastConfig`. `searchFields: ["type_name"]`,
placeholder `'Search asset group…'`, an `attention` filter labelled `Replacement` with
`Past life` / `Due within 12 months`, and the **seven drawn columns in the drawn order**
with `avg_age_months` / `expected_life_years` / `past_life` / `due_within_12mo` /
`replacement_cost` all `numeric: true`. `:444-446` — replacement cost through
`MoneyCell`, two decimals displayed, a dash rather than `$0.00` when the group is
unpriceable (hard rule 2). One `EyeIcon` row action.

`:632-638` — `assets.lifecycle.forecast.explainer` = **`'What wears out next, and cost.'`**
(6 words) against the drawn *"What wears out next, and what it costs."*

`:56-58` and `:48-54` — the `Asset value` panel is gone; `asset_value` is still served
and rendered nowhere, and the file says so about itself.

`:660-687` — **the Programme total row and the Turn-into-work panel are both built.**
The build lane decided both survive and recorded why in the file header at `:69-84`:
the Programme total is *"a real served pair with no other home in the product"* and moves
outside the table body because *"a DataTable renders rows and a total is not one"*; the
panel's button is live and gated on `writeBlockedReason`.

### Gap table — screen 05c

| # | gap | drawing says | code says | class | fixed since 2.234.17? |
|---|---|---|---|---|---|
| 1 | The whole screen | a NEW BUILD | built, 7 columns, three sortable, one eye action | — | **YES — `2.237.5`** |
| 2 | `Asset value` panel | REMOVED, quoting 2026-09-11 | removed; `asset_value` served and rendered nowhere | CONTENT | **YES — `2.237.5`** |
| 3 | Programme total + Turn into work | not drawn at all | both built, below the table | LAYOUT | n/a — **built-and-not-drawn, decided and recorded**; the carry-over dispositioned neither, so no action |
| 4 | `⇅` on three headers | drawn | no glyph until sorted | LAYOUT | NO — ruled out of scope |
| 5 | `Page x of y`, first / last | drawn | absent | LAYOUT | NO — ruled out of scope |

---

## 06 · Map — `?tab=map`

### What the drawing shows (Figure 8, p30)

* Page head `Assets`, **no primary action**.
* Six tabs, `Map` active.
* Description ① : *"Every asset on real streets. Filter above the map; click a marker
  for the device card and open its full detail from there."* — 23 words. **R6 proposes
  `Every asset with coordinates, on real streets` — 7 words.**
* **A filter bar of FIVE controls in one row, above the map**, and it is visibly NOT the
  shared toolbar — there is no `All` chip, no `+ Filter ▾`, no `↓` and no `▦`:
  `[Search asset # or address…]` `[Type: All ▾]` `[Status: All ▾]` `[Service: All ▾]`
  `[Area: All ▾]`.
* **A bordered map canvas** with one accent square marker and, below it, a popup card of
  **four lines**:
  ```
  E-5001 · Meter · walk-by
  88 Cypress Row · Unit 1
  Last read 12,481 kgal · Jan 2026
  Open details →                       (accent)
  ```
  `Tiles © Esri` sits bottom-right inside the canvas.
* **Below the canvas, one row**: a three-dot legend hard left —
  `● In service   ● Needs attention   ● Pending` (green, red, grey) — and, hard right on
  the same line, **`3 of 126 assets have coordinates`**.
* p31: the empty state is *"No mapped assets yet · Premises gain coordinates from the
  geocoding run; until then the map has no markers to draw."*, and with no tile host
  *"Background map is switched off."* and the markers still draw.
* p29 carries `AST-B-06` and the withdrawal that produced it: from source alone the four
  dropdowns looked like a rule-8 breach; measured in the browser they compute
  `appearance: none` and draw the product's chevron — *"conforming by inheritance from a
  class this component never asked for"*.

### What the code does today

`AssetMapTab.tsx:459-528` — the filter bar: one `<input>` then four bare `<select>`s,
then a count line pushed right with `ml-auto` **inside the same bar**.

* Search placeholder: `assets.map.searchPlaceholder` = **`'Search asset #, premise…'`**.
* First options: `'Type · all'`, `'Status · all'`, `'Service · all'`, `'Area · all'`.
* Count line: `assets.map.showing` = **`'Showing {{shown}} of {{total}} assets'`**, where
  `total` is `rows.length` — the number of rows **received**.

`:559-585` — the legend, **three entries**: `'Healthy'` · `'Needs attention (repair,
test due, pending)'` · **`'Master meter'`** (a hollow ring, not a filled dot).

`:347-405` — the popup card, built as real DOM so `Open details →` is a wired handler.
It renders **five lines**, or six: title + type, premises · unit, *(the unit's own point,
when `point_source === "unit"`)*, last read, **`row.status_name`**, `Open details →`.

`:530-556` — the empty state and the `Background map is switched off.` sentence, both
matching the drawing. `DEF-INT-4287` (the grey rectangle on every tenant) is `fixed`.

`:429-457` — `DEF-MET-4959`: the six inert Tailwind utilities on the four selects were
removed on 2026-09-12 and **zero pixels moved**, proved by reading computed styles before
and after. The row is `partially-fixed`: the chevron and the 36px height still come from
`.view select` in `FormModal.css`, which is true of every `<select>` in the product.

⚠ `selectors.py:2604, :2638, :2718` — **`geo_view` takes `page` and `per` (default 50)
and answers `assets_window`.** `DEF-MET-4962`'s own fix note measures it:
*"the map answered 66,104 B for 123 markers and answers 26,961 B for 50 with total 123"*.
`endpoints.ts:9079-9081` — `getAssetGeo()` sends **no parameters** and reads no window.
`mapVocab(rows)` at `:240` then builds the Service and Area option lists from those same
fifty rows.

### Gap table — screen 06

| # | gap | drawing says | code says | class | fixed since 2.234.17? |
|---|---|---|---|---|---|
| 1 | The served `assets_window` reaches nothing | not drawn — the server half landed after the document | draws **50 of 123** markers; the count line reports 50 as the total; the Service and Area menus are built from the 50 | WIRING | **NO — new, and not on any register. The worst row in this scope** |
| 2 | The count line's sentence and position | `3 of 126 assets have coordinates`, bottom-right **below** the map, on the legend row | `Showing 50 of 50 assets`, inside the filter bar **above** the map | LAYOUT + CONTENT | NO. Verified: *"have coordinates"* appears nowhere in `07-frontend/src` |
| 3 | Legend entry 1 | `In service` | `Healthy` | CONTENT | NO |
| 4 | Legend entry 2 | `Needs attention` | `Needs attention (repair, test due, pending)` — 10 words | CONTENT | NO — also over B14 rule 33's 6-word cap for a fact |
| 5 | Legend entry 3 | `Pending`, a filled dot | `Master meter`, a hollow ring | CONTENT | NO — a different fact, not a reworded one |
| 6 | Dropdown first options | `Type: All`, `Status: All`, … | `Type · all`, `Status · all`, … | CONTENT | NO |
| 7 | Search placeholder | `Search asset # or address…` | `Search asset #, premise…` | CONTENT | NO |
| 8 | The popup's extra lines | four lines | five, or six with the unit's own point | LAYOUT | n/a — the status line is built-and-not-drawn; the point line is `BR-MET-1162`, **ruled 2026-09-08 after the drawing**, so the drawing is stale here and the code is right |
| 9 | `AST-B-06` — the selects conform by inheritance | *"Rendering the filter bar outside any `.view` wrapper still shows four dropdowns with the product's chevron"* | the inert utilities are gone; the chevron and height still inherit | LAYOUT | **PARTLY** — `DEF-MET-4959`, `2.237.5`; the remainder is kit-wide, not this tab's |
| 10 | Basemap | tiles draw | `tile_host` from the page policy, one home | MISSING PLUMBING | **YES** — `DEF-INT-4287`, fixed |

---

## 07 · Assign 3 assets to a unit — a dialog on `/:tenant/assets`, no address of its own

**Chips: EXISTS BEHIND · NO COMMITMENT.** p3: a screen no specification covers carries
`NO COMMITMENT`, and that absence *"is the finding, not an oversight"*. So **the drawing
is the entire specification for this one.**

### What the drawing shows (Figure 9, pp32–33)

A centred card over the registry. Top to bottom:

* **Title**, bold, left: `Assign 3 assets to a unit`. **No kicker line above it.**
* **Field 1** — label `Unit *` (asterisk accent) with a blueprint annotation badge
  `TBL · UNITS · METERING` beside it. A full-width input, placeholder `Search units...`.
  **A helper line beneath the input**: `Type to filter. 121 units on this tenant.`
* **Field 2** — label `Effective date`, no asterisk. A full-width input showing
  `09/10/2026` with a small calendar glyph at its right edge. **A helper line beneath
  the input**: `Defaults to today in the tenant's timezone.`
* **A consequence box**, accent left-border, headed `WHAT THIS WILL DO` in small caps,
  holding two short lines:
  `Three assets move from inventory onto one unit, each with its own assignment row.`
  `Nothing already billed changes.`
* **A footer, right-aligned**: `Cancel` (a text button) then `Assign ✓` (an outlined
  button).
* **Nothing else is inside the card.** The 24-word *"Bulk assignment moves inventory to
  units only…"* sentence belongs to the **selection bar behind the dialog** — p33's
  *Words* row: *"The bar says the limit out loud."*
* p33 also records the shape ruling: *"This one stays a dialog — it is two fields and a
  consequence, and it acts on a selection that only exists on the screen behind it."*

### What the code does today

`AssetRegistryPage.tsx:1183-1262`, `BulkAssignModal`:

* `:1232` — `title={t("assets.bulk.title", { count })}` = `'Assign {{count}} assets to a
  unit'` ✓
* `:1233` — `kicker={t("assets.kicker")}` = `'Assets'`. **Built and not drawn.**
* `:1242` — `<Note>{t("assets.bulk.inventoryOnly")}</Note>` — the 24-word sentence,
  **inside the dialog**, above the first field. The same string is already rendered in
  the selection bar at `:1067`, so a clerk reads it twice.
* `:1243-1251` — `SearchSelectField`, `label={t("assets.reassign.unit")}` = `'Unit'`,
  `required`, `placeholder` = `'Search units…'`. **No `help` prop.**
* `:1252-1260` — `DatePickerField`, `label` = `'Effective date'`, `prefill={props.today}`.
  **No `help` prop.**
* **No `ConsequenceBox` anywhere in the file** — `grep -n "ConsequenceBox"
  AssetRegistryPage.tsx` returns nothing, and the only `consequence=` at `:1141` belongs
  to the delete confirm.
* `assets.bulk.save` = `'Assign ✓'` ✓, `FormModal`'s footer puts Cancel before the
  commit ✓.

Both kit fields **do** take a `help` string — `FormModal.tsx:733` (`DatePickerField`) and
`:863` (`SearchSelectField`). Neither is passed here. So gap 2 below is two arguments,
not a kit change.

### Gap table — screen 07

| # | gap | drawing says | code says | class | fixed since 2.234.17? |
|---|---|---|---|---|---|
| 1 | The consequence box | `WHAT THIS WILL DO` + two lines | no `ConsequenceBox` at all | WIRING | **NO.** Also B14 rule 11 — this form writes service state |
| 2 | The two helper sentences | under each input | neither `help` prop is passed, though both fields accept one | WIRING | **NO** |
| 3 | The inventory-only sentence | on the selection bar behind the dialog, once | on the bar **and** inside the dialog | CONTENT | **NO** — rule 32's one-sentence budget, read twice |
| 4 | The kicker | no kicker above the title | `kicker="Assets"` | LAYOUT | n/a — **B14 rule 38: where a drawing and our UI rules disagree about how a form is built, the UI rules win.** Record the divergence, build nothing |

---

## The remedies R1–R6, and which of them actually reach these screens

⚠ **Read off the drawings themselves (pp140–151), the remedy titles are not what the
`00-index.md` summary table says.** The index lists R3 as *"Asset # helper moves below
its input"* and R4 as *"Label → input → helper"*; the pages read otherwise. Taken from
the page headings:

| Remedy | Page | Title, off the image | Commitment | Screens it changes | Touches § 02? |
|---|---|---|---|---|---|
| **R1** | 140–141 | *The asset gets the two doors its own rule already names* | `AST-B-02` | The asset **detail** page — `Raise work order` in the header action bar and beside `Log repair / maintenance` on the Maintenance panel | **NO.** Figure 51 draws `/assets/{id}` (`AST-02`), which is screens 08 and 12 — another lane's |
| **R2** | 141–143 | *The registry's numbers become numbers* | `AST-B-01` | **Screen 01** | **YES** — the whole of it |
| **R3** | 143–145 | *The service field offers the list it already has* | `AST-B-03` | Add-an-asset step 1 (`AST-05`) — the Service control becomes a searchable picker, the Asset # helper moves below its input, the help text is relabelled | **NO** — screen 28 |
| **R4** | 145–147 | *Every helper moves under its own input* | `AST-B-13` | *"ten fields across four screens"* — the add wizard, reassign, log repair, retire (`SCREENS 14, 16–21, 23`) | **NO** for screens 01–06. **Already satisfied on screen 07**: p33 measures the dialog as *"R12 inside the dialog: the unit picker's helper sits under its input"* |
| **R5** | 147–150 | *The opening read becomes a field a person can fill in* | `AST-B-14` | Add-an-asset step 2 (`SCREENS 29`) | **NO** |
| **R6** | 150–151 | *One description per screen, six to eight words* | `AST-B-15` | **All six tabs** — screens 01, 02, 03, 04, 05 and 06 | **YES** |

**So two of the six reach this scope, not five.** R1, R3 and R5 each draw a screen
outside § 02; R4's ten fields are all outside it and its one in-scope surface already
complies.

### R2 in full — what it requires and where each half stands

| R2's requirement | status |
|---|---|
| KPI figures from a new aggregate read over the whole filtered set, `NFR-3`-safe, four `COUNT`s on the predicate `asset_list` already builds | **BUILT.** `selectors.asset_kpis` — three queries for Meters, one for Behind the meter, constant whatever the tenant holds |
| Row actions capped at two, then `⋯`, using the existing `RowActionsMore` | **NOT BUILT** — blocked by the PO's out-of-scope ruling |
| First and last page controls, from the `count` already served | **NOT BUILT** — same ruling |
| Sort indicator `▲` → `⇅` once a third state exists | **NOT BUILT** — same ruling, and R2 itself calls it *"a change to the shared table rather than to this screen"* |

R2's own closing rail is worth carrying forward: *"It would be easy to also fix `NFR-3`
here … and it is deliberately not drawn … a remedy that also tidies what it happened to
be standing next to is a redesign wearing a fix's clothes."* `NFR-3` was nevertheless
fixed, separately and properly, as `DEF-MET-4962`.

### R6 in full — the six sentences, drawn against what ships

R6's own table (p151), beside the catalogue as it stands today:

| tab | R6: TODAY | w | R6: PROPOSED | w | **`2.261.3` ships** | w | renders? |
|---|---|---|---|---|---|---|---|
| Meters | *nothing renders* | — | `Meters, where they sit, and their state` | 7 | `Meters and behind-the-meter devices · assign to units · track lifecycle` | 11 | **NO** |
| Sub-meters | 24-word pair | 24 | `Sub-meters, their master, and what they read` | 7 | `Sub-meters bill their own unit.` | 5 | yes |
| Behind the meter | *nothing renders* | — | `Customer-side devices, their capacity and test dates` | 7 | `Behind-the-meter assets — assigned to units, tracked through their lifecycle` | 10 | **NO** |
| Inventory | 18-word pair | 18 | `Spare assets on the shelf, and their value` | 8 | `Assets you own, not yet installed.` | 6 | yes |
| Lifecycle | 9 words | 9 | `What is falling due and wearing out` | 7 | `What falls due, what wears out.` | 6 | yes |
| Map | 23-word pair | 23 | `Every asset with coordinates, on real streets` | 7 | `Every asset on real streets.` | 5 | yes |

**Two halves, and they stand differently.**

* **The word-count half is fixed** — `DEF-MET-4961`, `2.237.5`, four sentences cut in all
  eleven catalogues, each written in its own language rather than translated (B14 rule
  35), applied through `10-scripts/i18n_fanin.py` so no catalogue was re-serialised.
  `G14`'s baseline was raised by one with the key, the superseding rule and the reasoning
  stamped on the constant.
* **The rendering half is not.** `AssetRegistryPage.tsx:812` still reads
  `id === "sub_meters" ? … : undefined`. Two strings exist in eleven catalogues each and
  reach no screen — R6's own words: *"Two dead strings, and two screens with nothing
  under the title."*
* **And the four sentences that do render are not the drawn sentences.** They obey rule
  32's budget and rule 33's cap; they are different words. Under B14 rule 41 that is a
  divergence to put to the PO in one line covering all four, not four separate fixes.

---

## Summary — the counts

**50 gaps across the nine screens**, counted as one row per distinct difference:

| | count | what it is |
|---|---|---|
| **Already fixed since `2.234.17`** | **11** | The document was right and the product moved |
| **Partially fixed** | **2** | The tab descriptions (words differ from the drawing) · the map's selects (inert utilities gone, inheritance remains) |
| **Need building** | **17** | |
| **Blocked — and by a PO ruling, not by plumbing** | **18** | The four shared-table rows × 5 screens, minus overlaps |
| **Recorded divergence, no action** | **3** | 05c's Programme total + Turn-into-work · 06's popup status line · 07's kicker |
| **Blocked on missing plumbing** | **0** | Every server half in this scope is done |

### The eleven already fixed

| what | defect | version |
|---|---|---|
| The four Meters KPI figures — four em dashes on first load | `DEF-MET-4953` | `2.237.5` |
| The two Behind-the-meter KPI figures | `DEF-MET-4953` | `2.237.5` |
| The export saving `file.json` containing a 404 | `DEF-MET-4954` | `2.237.5` |
| `NFR-3` — no `LIMIT`/`OFFSET` reaching SQL, four filters in Python | `DEF-MET-4962` | `2.237.8` |
| Screens 05a, 05b, 05c — the three stacked hand-built tables | `DEF-MET-4955` | `2.237.5` |
| The `Asset value` panel removed on the quoted instruction | `DEF-MET-4955` | `2.237.5` |
| Four tab descriptions cut to six words or fewer | `DEF-MET-4961` | `2.237.5` |
| `Parts in Work →` disabled over a screen that had shipped | — | `CR-070` wave M |
| The Lifecycle wrench and `Set up an exchange rule` unguarded | `DEF-MET-4950` | `2.237.5` |
| The map's flat grey rectangle on every tenant | `DEF-INT-4287` | `CR-075` |
| Two stale trailers claiming absences the code no longer had | `DEF-MET-4964` | `2.237.5` |

### The seventeen that need building, worst first

| # | screen | what | why it matters |
|---|---|---|---|
| 1 | **06 Map** | `getAssetGeo()` asks for no page and reads no `assets_window` | 50 of 123 markers drawn; the count line reports 50 as the total; the Service and Area menus are built from the 50 |
| 2 | **05a** | `getAssetLifecycle()` asks for no page and reads no `certifications_window` | the 51st cadenced asset onward is unreachable, and the footer reports the window as the total |
| 3 | **04** | `getAssetStock()` asks for no page and reads no `rows_window` | same fault, bounded by asset-type count |
| 4 | **01** | the Meters description renders nothing | R6 / `AST-B-15` |
| 5 | **03** | the Behind-the-meter description renders nothing | R6 / `AST-B-15` |
| 6 | **07** | no consequence box | B14 rule 11 — a form writing service state |
| 7 | **07** | two helper sentences not passed | both kit fields already accept `help` |
| 8 | **07** | the inventory-only sentence rendered twice | rule 32's budget |
| 9 | **03** | `+ Add behind-the-meter asset` where the drawing says `+ Add device` | |
| 10 | **06** | count-line sentence and position | |
| 11–13 | **06** | three legend entries | one of them is a different fact, not a rewording |
| 14 | **06** | four dropdown first options | |
| 15 | **06** | the search placeholder | |
| 16 | **02, 04, 05 tabs, 06** | four descriptions that render but are not the drawn words | one decision, not four |
| 17 | **05a** | two simultaneous filter chips from one status vocabulary | needs `OQ-306` (multi-value filters) answered first · ⚠ **2026-10-02: `OQ-306` CLOSED for the SERVICE dimension only** (PO: *"Allow several services at once."*); a status dimension is still single-select, so this row still waits on its own ruling |

⚠ **Rows 1–3 are ONE fault in three places, they are new, they are on no register, and
they were introduced by a fix.** `DEF-MET-4962` taught `/assets/stock`,
`/assets/lifecycle` and `/assets/geo` to page and to describe their window; no client
wrapper was changed in the same commit. `grep -rn "assets_window\|rows_window\|
certifications_window" 07-frontend/src` returns **nothing**; the only readers anywhere
are `selectors.py` and one backend test. That is hard-won law 2 in its mirror form — a
capability that is live on the server and unreachable from the screen — and no gate in
this repository can see it, because the seeded tenant fits inside one window.

### The eighteen blocked, and by what

All eighteen are the same four shared-table rows repeated across screens 01, 02, 03, 05a,
05b and 05c: the row-action cap, first/last page, `Page x of y`, and `⇅` with a clearing
third click. They left `CR-092-BRC01` for `CR-093-BRC01` on **2026-09-12** by PO ruling —
***"(b). It's the right fix and it touches 54 lists at once. That risk doesn't belong
inside an Assets pass"*** — and they carry `DEF-SHL-4946`, `DEF-SHL-4948` / `DEF-2453`,
`DEF-SHL-4949` and `DEF-449`. Nothing here re-opens them; they are listed on each screen
so a reader comparing a drawing with a screen knows why the difference is there.

---

## Two things this pass could not check, with their numbers

1. **Nothing here was walked in a browser.** Every finding is a source and image
   comparison. B14's own status table says most of its 33 rules (numbered 1–21 and
   31–42) are RATIFIED and UNENFORCED *"because no gate in this repo reads rendered
   output"*, and hard-won law 6 has no tool behind it. Rows 1–3 of the build list in
   particular want a tenant with more than 50 geocoded assets and more than 50 cadenced
   ones before anybody calls them fixed.
2. **The window fault was inferred from the code paths, not reproduced.** The seeded
   Brazos Bend tenant has 3 certification rows and — on the document's own measurement —
   123 geocoded assets. The map case is therefore reproducible today and the lifecycle
   case is not without seeding.

---

<!-- ── Lifecycle ─────────────────────────────────────────────
  packet: `05-prototype/01 Assets Menu Blueprint.pdf` § 02 (pp4–33) and § 10 (pp139–151),
    read as 43 PNGs at scale 2 via `10-scripts/pdf/pdf_render.py` (B14 rule 42).
    Code read at `2.261.3`, branch tip `11307c79`.
  generated: 2026-09-13, CR-092 blueprint pass, lane A (registry tabs).
  method: images only for layout; the derived HTML wireframes and `08-screen-layouts.md`
    were NOT used as specification (PO clarification 2026-09-13, hard-won law 5).
    `08-screen-layouts.md` was read once for build history and found stale on
    `DEF-MET-4962`, which the register has as fixed.
  exceptions: E3 nothing was walked in a browser — see the closing section
    · E3 the three window gaps are inferred from code paths and are not reproduced
    · E4 no defect, OQ or CR id is allocated here; ids are allocated centrally
  status: MEASURED-UNRATIFIED — this pass routes, it builds nothing.
─────────────────────────────────────────────────────────── -->
