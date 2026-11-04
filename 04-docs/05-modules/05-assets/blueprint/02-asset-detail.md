# Assets blueprint § 03 — one asset, read it and change it (screens 08–13)

**Scope.** Section 03 of `05-prototype/01 Assets Menu Blueprint.pdf`, pages **34–71**,
screens **08 Overview · 09 Reads · 10 Export · 11 Assignment history · 12 Work &
maintenance · 13 Audit**.

**How this was read — B14 rule 42.** Every page from 34 to 65 was rendered with
`python3 10-scripts/pdf/pdf_render.py "05-prototype/01 Assets Menu Blueprint.pdf"
/tmp/laneB 2 <pages>` (1584×1224 per page) and **opened as an image**, one at a time.
Layout, which fields sit side by side, what is a table and what is a list of facts,
panel order, column order, emphasis, the empty states and the exact on-screen words are
all read off the picture. The text layer was not used for any of it.

> ⚠ **THE PDF IS THE ONLY SPECIFICATION — PO instruction, 2026-09-13.**
> `04-docs/05-modules/05-assets/wireframes/CR-092-assets-screens.html` and
> `04-docs/05-modules/05-assets/08-screen-layouts.md` are **derived second copies** of
> these wireframes and are free to drift (hard-won law 5). **No layout, field, label,
> column or ordering in this file comes from either of them**, and nothing needed
> correcting: this lane read the PDF page images from the first minute. `08-screen-layouts.md`
> was read once, after that instruction arrived, for **build history only** — it records
> screens 05a/05b/05c BUILT at `2.237.5` and screen 14 BUILT at `2.239.9`, and names
> `DEF-MET-4962` and `DEF-AST-5107` as open. None of those is in this lane's scope and
> none of them changed a line here.

**Staleness.** The document was read at product version `2.234.17`, commit `79c659d7`.
The product is at **`2.261.3`** today. Page 2 says the staleness covers *"every sentence
about what the code does today, every field table, every route, every measured figure,
and every drawing of a screen as it is"* and **not** rulings. So every as-built claim
below was re-checked against the code on this branch, and the "already fixed" column is
the result. **A great deal has been fixed** — `CR-092-BRC01` step 2 waves B and C rebuilt
screen 08 almost entirely on 2026-09-12.

**Files censused** (all read in full):
`07-frontend/src/features/assets/AssetDetailPage.tsx` (2,129 lines) ·
`AssetUsageStrip.tsx` (509) · `AssetPanelEdits.tsx` (855) · `assetsShared.tsx` (433) ·
`AssetOverviewPanels.dom.test.tsx` (690) · `AssetDetail.test.tsx` (1,319) ·
`AssetPagedLists.dom.test.tsx` (128) · `07-frontend/src/i18n/locales/en.json` (712
`assets.*` keys) · `06-backend/apps/assets/api.py` · `selectors.py` · `seams.py` ·
`06-backend/apps/work/asset_door.py` · `06-backend/apps/work/api.py`.

**Route table verified, not grepped for:** `grep 'path(' 06-backend/apps/*/api.py`.
`apps/assets/api.py` mounts `assets/<uuid>/reads`, `/assignments`, `/maintenance`,
`/retire`, `/reassign`; `apps/work/api.py` mounts `assets/<uuid>/work-orders` and
`assets/<uuid>/work-order-templates`. There is **no** `assets/<uuid>/audit` route — the
Audit tab reads the shared `getAuditLog` filtered by entity, which is correct.

---

## Screen 08 · Overview — `/:tenant/assets/{id}` — EXISTS BEHIND · **NEW BUILD**
### pages 34–46 · figures 10, 11, 12 · commitments 12, 16, 22

### What the drawing shows

**Figure 10 — an installed AMR water meter, `M-4022`** (p35). Signed-in frame, left rail
of thirteen items, top bar with a Search box. Then, top to bottom:

* `← Assets` (red, back to the list)
* kicker **`METER · AMR`** — *the asset number is NOT in it*
* title **`M-4022`**, very large
* a green outlined pill **`Installed`**, on its own line under the title
* a place line: **`118 Bayou Bend Dr · Unit A · ACC-20194 Ruth Alvarez · Water · Installed Feb 2024`**
* action row, right-aligned, **in this order**: `Raise work order` (drawn outlined, grey
  text — the marker for NEW) · `Reassign` · `Log repair` · `Retire` · `…`
* tab strip: **Overview · Reads · Assignment history · Work & maintenance · Audit** —
  five, Overview underlined
* **two columns of panels.** Left: `Assignment`, `What's due`, `Measurement`.
  Right: `Device`, `Cost & value`, `Lifecycle`. A red pencil sits at the top-right of
  `Device`, `Cost & value`, `Lifecycle` and `Measurement`. **`Assignment` and `What's due`
  have no pencil drawn.**

Rows, read off the image, in the drawn order:

| Panel | Rows as drawn |
|---|---|
| **Assignment** | Service · Premises *(link)* · Unit *(link)* · Account *(link, `NEW`)* · Sub-meters on it *(drawn as `—`)*, then a small grey line *"No pencil here — premises, unit and account are not typed on this screen."* and a red **`Reassign →`** |
| **What's due** | Requirement · Last test · Next due · Certification due · Warranty ends *(value + a red `Expired` pill)* · Replacement forecast |
| **Measurement** | Read method · Connection size *(italic absence sentence: "Not recorded — a rate ladder that prices by size cannot price this meter")* · Multiplier · Unit of measure · Register digits |
| **Device** | Asset type · Meter type · Manufacturer / model · Device ID / serial · External reference *(`NEW`)* · Form / class · Firmware · Seal # |
| **Cost & value** | Supplier · Purchase cost · Purchase date *(`NEW`)* · Present value · Depreciation method *(`NEW`)* · Warranty term · Book value *(`NEW`)* · Treatment *(`NEW`)* |
| **Lifecycle** | Installed · Age · Expected life · Location note |

**Page 36 states the header rule in four numbered lines**, quoted:

1. *"**The header, five slots** · kicker without the number · the number once, in the
   title · the status once, in the pill · the place line leading with the **address** and
   carrying the **account**, which is served today and shown nowhere · and the multiplier
   **gone** from it, because a ×1 is configuration rather than identity."*
2. *"**Six panels, in the order they are read** · Assignment · What's due · Measurement ·
   Device · Cost & value · Lifecycle. The first two answer the questions that bring
   somebody here; the rest is reference. **All 38 facts carry over**."*
3. *"**Seven rows that were already on the wire** — account, external reference, purchase
   date, depreciation method, allocation rule, loss tolerance, book value and its
   treatment. Marked **NEW** on the drawing."*
4. *"**A pencil per panel**, not one Edit for twenty-three fields. *What's due* has none:
   nothing on it is typed, every row is derived."*

**Eight header states drawn** (p36–38), each in its own box:

| Drawn state | What the header shows |
|---|---|
| An installed meter | as figure 10 |
| A meter in inventory (`AST-04412`) | pill `Inventory`, place line *"In inventory · unassigned · never installed"*, actions **`Assign` (greyed) · `Edit` · `Delete`** and **nothing else** |
| A sub-meter (`S-2001`) | place line *"Sub of **E-5000** · 118 Bayou Bend Dr · Unit 1 · ACC-20194 Ruth Alvarez · Water"* — the master is a **link** |
| A backflow preventer with a lapsed test (`BF-0001`) | an **attention strip** below the pill: a left rule, `⚠ Annual test overdue 11 days · due 06/15/2026`, and a red **`Raise work order →`** on its own line; the place line sits *below* the strip |
| A master meter (`M-MASTER-01`) | place line *"Apt 101 · 3 sub-meters on it · ACC-20201 Bayou Bend HOA · Water · Installed Jan 2026"* |
| A warranty that has run out (`W-5002`) | the **same strip in the quieter register** — grey-brown rule, `Warranty ended 03/2026`, **no control** |
| A retired meter (`W-5004`) | pill `Retired`, two place lines (*"Retired 08/14/2026 · Failed accuracy test · Replaced by W-5021"* / *"Last at 118 Bayou Bend Dr · Unit 1"*), and **only the `…` box** — every other action gone |
| Nothing due (`W-5001`) | **no strip at all** — *"which is what makes it worth reading when it appears"* |

**Figure 11 — a sub-meter (p39).** Four panels only: `Assignment` (with a **Parent master**
row, `E-5000 → NEW`) and `Measurement` on the left; `Device` and `Lifecycle` on the right.
Measurement gains three rows no other kind has: **Allocation share · Allocation rule
(`NEW`) · Loss tolerance (`NEW`)**.

**Figure 12 — a backflow preventer (p40).** Assignment has a **`Linked meter  W-5001 →
NEW`** row where a sub-meter has *Parent master*. **No Measurement panel at all** — the
caption says *"a device stores no reading, so the rows are absent rather than dashed. Same
reason it has no Reads tab, one level down."* What's due carries `Next due 06/15/2026` with
a red **`Overdue 11 days`** pill beside it.

**Carry-over table (p40–41), and its arithmetic (p41, verbatim):**

```
Facts on the as-built    40 rendered rows – 2 duplicates = 38 distinct
  carried over           38
  removed                 0
  added                   7   (+ export capacity, on an inverter)
Panels                    5 → 6
Rows per panel, worst    23 → 9                          ✓ reconciles
```

Dispositions: Specifications (23 rows) **SPLIT** into five of the six panels · Asset #
(row 1) **MOVED** to the title · Status (row 21) **MOVED** to the pill · Parent (rows 10
and 27) **MERGED** to one row plus a link · Last test date (rows 18 and 39) **MERGED** ·
Warranty & supplier (5 rows) **SPLIT** (term → Cost & value, date → What's due) ·
Lifecycle (4 rows) **SPLIT** · Test & certification (3 rows) **MOVED** whole into What's
due · Account/premises/unit **UNCHANGED · now linked** · Every label **UNCHANGED** ·
Anything at all **REMOVED — none**.

**Interaction design — seven decisions (p46–47):** the account is a link · the master is a
link · edit per panel · What's due carries its action · absence names its consequence ·
status said once · the header earns its attention strip. The cost box on p47 reads
`NO SERVER CHANGE AT ALL`; the only non-free item is the absence sentences, which are
eleven catalogue keys each.

### What the code does today

| Thing | Where |
|---|---|
| Page header, kicker, title, pill, place line | `AssetDetailPage.tsx:470-575` |
| Kicker composition | `AssetDetailPage.tsx:477-479` |
| Place line (`rollupParts`) | `AssetDetailPage.tsx:425-461`, rendered at `:492-498` |
| Attention strip | `assetAttention` `:749-759`, `AttentionStrip` `:762-821`, mounted `:486-491` |
| Header action set | `:502-569` |
| Tab set, derived | `assetDetailTabsFor` `:159-169`; `ASSET_DETAIL_TABS` `:125-131` |
| Panel set, derived | `ASSET_OVERVIEW_PANELS` `:689-696`, `assetOverviewPanelsFor` `:718-725` |
| Two-column split | `OverviewTab` `:954-960` |
| Panel pencil | `PanelPencil` `:829-846`; five dialogs in `AssetPanelEdits.tsx` |
| Assignment panel | `:970-1064` |
| What's due panel | `DuePanel` `:1083-1152` |
| Measurement panel | `:1168-1250` |
| Device panel | `:1255-1299` |
| Cost & value panel | `:1306-1415` |
| Lifecycle panel | `:1419-1475` |
| Account link | `:1041-1049` |
| Master link | `:1010-1020` |
| Lifetime cost, both halves named | `:1373-1396`; served by `selectors.py:998-1007` → `seams.py:268-284` → `apps/work/asset_door.py:119` |
| Open work count | `:1147-1149` |
| Raise work order control | `raiseWorkRefusal` `:264-273`, `RaiseWorkOrderControl` `:286-306` |

**Verified present, not assumed:** `linked_meter` is served at `selectors.py:1159-1166` for
a behind-the-meter asset; `parent_asset_no`/`parent_asset_id` at `selectors.py:418/422`;
`billing_chain.account` is read at `AssetDetailPage.tsx:979`; `external_ref`,
`purchase_date`, `depreciation_method`, `allocation_rule`, `loss_tolerance_pct`,
`book_value_amount` and `book_value_treatment` all render.

### Gap table — screen 08

| # | Gap | Drawing says | Code says | Class | Fixed since 2.234.17? |
|---|---|---|---|---|---|
| 08-1 | Asset number said twice | kicker `METER · AMR`, number only in the title | kicker is `[type_name, asset_no, meter_type_name].join(" · ")` → `Meter · M-4022 · AMR` (`:477-479`) | CONTENT | **No** |
| 08-2 | Place line order and contents | `118 Bayou Bend Dr · Unit A · ACC-20194 Ruth Alvarez · Water · Installed Feb 2024` — address first, account carried, multiplier **gone** | `Water · ×1 · installed Feb 2024 · assigned to 118 Bayou Bend Dr · Unit A` (`:425-461`) — service first, multiplier still there, **no account at all**, and an extra word *"assigned to"* | CONTENT + LAYOUT | **No.** The account is on the payload, so this is wiring over live plumbing |
| 08-3 | Edit and Delete under the overflow | `Raise work order · Reassign · Log repair · Retire · …`, with Edit and Delete inside `…` (p41: *"Edit and Delete under the overflow"*) | six visible buttons, no overflow (`:502-569`); `components/PageHeader.tsx` has **no** overflow control | LAYOUT | **No.** Needs a kit addition (B14 rules 36/38: add it to the kit, do not hand-roll it) |
| 08-4 | Assignment label | `Premises` | `Premise` (`assets.chain.premises`) | CONTENT | **No** |
| 08-5 | Sub-meter row label and its absence | `Sub-meters on it`, drawn as `—` on a meter with none | label `Sub-meters`; the **row is omitted entirely** when `sub_assets` is empty (`:1050`) — absence by DATA, which `AST-R-03` says is drawn as a dash | CONTENT | **No** |
| 08-6 | A device's own hook | `Linked meter  W-5001 →` (fig 12) | renders under `Parent / master` (`assets.col.parent`), because the same `parent_asset_no` field serves both kinds (`:1010-1020`) | CONTENT | **No.** `linked_meter` is served separately and is unused on this panel |
| 08-7 | What's due label | `Last test` | `Last test date` (`assets.spec.lastTest`) | CONTENT | **No** |
| 08-8 | What's due label | `Warranty ends` | `Cover ends` (`assets.valuation.coverEnds`) | CONTENT | **No** |
| 08-9 | Cost & value absences | `Book value — NEW` and `Treatment — NEW` drawn as rows with a dash | both rows render **only when non-null** (`:1397`, `:1406`) — same `AST-R-03` fault as 08-5 | CONTENT | **No** |
| 08-10 | *What's due* pencil | p36 line 4: *"What's due has none"*, and figure 10 draws no pencil on it | a pencil is passed (`:918`) and `EditWhatsDue` exists (`AssetPanelEdits.tsx:206`) | — | **N/A — the document contradicts itself.** `00-index.md`'s own screen list carries **screen 16 "Edit · What's due", NEW BUILD, `PATCH /assets/{id}`**. Screen 16 is the later and more specific statement and the code follows it. **No work; recorded.** |
| 08-11 | Assignment's rationale line | *"No pencil here — premises, unit and account are not typed on this screen."* | absent | — | **N/A — the drawing breaks a signed rule.** B14 rule 33: *RATIONALE — why a control is absent — is **ZERO WORDS ON SCREEN***. The code is right. This is rule 41's one legitimate question if anybody wants it built. **No work; recorded.** |
| 08-12 | Retired header | only the `…` box (p38) | `RaiseWorkOrderControl` always renders, disabled, carrying its reason (`:509`, `:294-299`) | — | **N/A — superseded by a later ruling.** `BR-AST-534`, PO 2026-09-12: *"a) Show it disabled, with the reason"*. The ruling post-dates the drawing. **No work; recorded.** |

### Already fixed since `2.234.17` — verified in the code, one by one

| Screen-08 commitment | Evidence |
|---|---|
| Six panels, cut by the question each answers | `ASSET_OVERVIEW_PANELS` `:689-696`; test `AssetOverviewPanels.dom.test.tsx:287` |
| Panel set DERIVED, one function (`AST-R-08`) | `assetOverviewPanelsFor` `:718-725` |
| Panel order fixed, gaps close, never reorders (`AST-R-11`) | `:954-960`; test `:316` (subsequence assertion) |
| Attention strip, two registers, **silent when healthy** (`AST-B-22`) | `:749-821`; tests `:331-368` (TC-A1…A4) |
| The account is a **link** | `:1041-1049`; test `:595` |
| The master is a **link** (`AST-R-07`) | `:1010-1020`; test `:600` |
| A pencil per panel, not one form over 23 fields (`AST-B-25`) | `PanelPencil` `:829-846`; `AssetPanelEdits.tsx` — five dialogs, Measurement carrying a second confirm step |
| External reference rendered | `:1291-1293` |
| Purchase date rendered | `:1331-1339` |
| Depreciation method rendered | `:1354-1362` |
| Allocation rule + loss tolerance rendered, in **words** | `:1224-1239`; test `:534-566` |
| Book value + treatment rendered | `:1397-1412` |
| One honest lifetime cost, both halves named (`AST-B-21`) | `:1373-1396` + the `apps/work` seam |
| Open work orders count (`AST-B-16`) | `:1147-1149` |
| `Raise work order` on the header (`AST-B-02`, door 1 of 4) | `:509` |
| Status no longer a labelled row; asset # no longer a Specifications row (`AST-R-09`) | the 23-row `Specifications` panel no longer exists |

**Carry-over arithmetic re-checked against the code: it reconciles.** All seven
*already-on-the-wire* rows render. Worst panel is **Cost & value at 9 rows** (supplier,
purchase cost, purchase date, present value, depreciation method, warranty term, lifetime
cost, book value, treatment) — the document's `23 → 9` holds. Nothing was removed.
One note: the document's `Panels 5 → 6` counts the device variant's old `Test &
certification` panel; the code's own comment at `:667` says *"THIS REPLACES FOUR PANELS
WITH SIX"*, counting the meter variant. Both are true of different kinds.

### The fifteen AST-R rules — **PROPOSED, NOT RATIFIED**

p44 states it plainly: *"They are **PROPOSED, not ratified** — B14 is the authority and
none of these has been put to the PO yet."* **So none of them is law.** They are not
citable, a screen that breaks one is not in breach, and nothing here should be enforced as
a rule. They are recorded because eleven of them describe behaviour the code already has
and are useful as test names.

⚠ **THE DOCUMENT GIVES THIS SET FOUR DIFFERENT COUNTS AND THE RULES ARE NUMBERED TO 16.**
p44 prose says *"Fifteen rules"*; the table on p44–46 runs **AST-R-01 through AST-R-16**;
the summary on p46 says *"Ten of these **thirteen** are assertions about the DOM"*; and
screen 08's own *Rules* row on p42 cites *"AST-R-01–13"*. That is B14's rule-count rot in
a new family (CLAUDE.md: *"count the status table; never trust a number in a pointer"*).
**Sixteen are drawn. All sixteen are below.**

| Rule | What it says | Checkable how (the document's own column) | Does the code do it today? |
|---|---|---|---|
| **AST-R-01** PROPOSED | One template, every kind — the tab set and panel set vary, the structure and order never do | Human review | **Yes** — one component, `AssetDetailPage.tsx` |
| **AST-R-02** PROPOSED | A panel or row a kind cannot have is **ABSENT, not empty** | Machine | **Yes** for panels (a device has no Measurement); test `:298` |
| **AST-R-03** PROPOSED | Absence by KIND is silent; absence by DATA is **stated** (a dash, and a consequence where there is one) | Machine | **Partial** — the connection-size sentence is exemplary (`:1184-1191`), but three rows are omitted rather than dashed: sub-meters (08-5), book value and treatment (08-9) |
| **AST-R-04** PROPOSED | Measurement belongs to measuring kinds only | Machine | **Yes** — `:721-724`; test `:298` |
| **AST-R-05** PROPOSED | Allocation belongs to sub-meters only; a null share is *metered, not allocated* and **never a zero** | Machine | **Yes** — `:1211-1220`; tests `:534-566` |
| **AST-R-06** PROPOSED | Export capacity belongs to an exporting device, in **kW**, never money | Machine | **Yes** — `:1242-1247` |
| **AST-R-07** PROPOSED | Every kind names what it hangs off, **as a link** | Machine | **Partial** — sub-meter master ✓, master's sub-meters ✓, a device's **linked meter renders under the wrong label** (08-6) |
| **AST-R-08** PROPOSED | The tab set and panel set are **DERIVED**, never written per screen | Machine (grep) | **Yes** — `assetDetailTabsFor` `:159`, `assetOverviewPanelsFor` `:718` |
| **AST-R-09** PROPOSED | A fact is said once | Machine, cheap | **No** — the asset number is in the kicker *and* the title (08-1) |
| **AST-R-10** PROPOSED | No database id is ever a visible value (B14 rule 31, restated) | Machine, cheap | **Yes** — test `:605` (TC-L3) |
| **AST-R-11** PROPOSED | Panel order is fixed and does not vary by kind; a skipped panel **closes the gap** | Machine | **Yes** — test `:316` |
| **AST-R-12** PROPOSED | A panel label is at most two words and names the question | Machine, trivial | **Yes** — test `:612` (TC-L4) |
| **AST-R-13** PROPOSED | Adding a kind is a four-line change | Human review | Untested by construction; the two deriving functions make it plausible |
| **AST-R-14** PROPOSED | A field's helper is **one line, ≤ ten words**, and never wraps | Machine, trivial | **Yes inside the panel dialogs** — every `assets.panel.help.*` string is ≤ 8 words. **Not everywhere:** `assets.form.sizeClassHelp` is **36 words** and still ships (used by screen 14, outside this lane) |
| **AST-R-15** PROPOSED | Two columns are two **fields** — never one input with a delimiter | Machine | **Yes in the Device dialog** — two inputs, joined client-side (`AssetPanelEdits.tsx:585-589`). The server's edit door still takes them joined, which the code says out loud |
| **AST-R-16** PROPOSED | Every choice control names where its options come from, on the drawing (`SET`/`TBL`/`FIX`/`NONE`) | *"Eye. Nothing mechanical can check this"* | **A drawing convention, not a product rule.** Nothing to build |

---

## Screen 09 · Reads — `?tab=reads` — EXISTS BEHIND
### pages 47–52 · figures 13, 14, 15 · commitments 19, 23, 24

### What the drawing shows

**Figure 13 (p48) — an AMI water meter, `W-5001`.** Same header. Tab strip with **Reads**
underlined. Then **two stacked panels**:

1. **`Consumption · last 12 months`** — a sub-line *"Total register · 12 months (kgal)  ·
   Window 12 months"*, a chart area, an axis caption *"Sep 2025 to Aug 2026"*, then a
   **three-cell KPI row separated by vertical rules**: `AVG / MONTH` **1,182 kgal** /
   *last 12 months* · `PEAK MONTH` **1,510 kgal** / *Aug 2026* · `LOW MONTH` **672 kgal** /
   *Feb 2026*. A footnote: *"Figures are calculated from this meter's own readings."*
2. **`Reads`** — a **toolbar** drawn as one row: a search input reading
   **`Search a date, a reading or a source...`**, then chips **`All` `Committed`
   `Estimated` `Disputed`**, then **`+ Filter ▾`**, then right-aligned **`↓ Download`** and
   **`▦ Columns`**. Table columns, in order: **DATE · READING · IMPORT · SOURCE · STATUS ·
   ACTIONS**, `IMPORT` right-aligned, `STATUS` a green **`Committed`** pill, `ACTIONS` a
   red eye glyph. Footer: **`1–50 of 1,460   Rows per page 50 100 200 500 1000`** left,
   `⇤ ← Page 1 of 30 → ⇥` right. Under it, in red: *"**NEW** — the toolbar and the pager.
   Today this panel is a bare table: no search, no filter, no column chooser, no download,
   and no pagination at any of the four layers."*

**Figure 14 (p49) — a net meter `E-5001`.** One more column, **`EXPORT (NET)`**, between
IMPORT and SOURCE. Caption: *"a flat meter draws **five** columns, not six with a column of
dashes. A **0 kWh** export is a real measurement and survives; it is never rendered as a
dash."* **No ACTIONS column drawn here.**

**Figure 15 (p49–50) — a time-of-use meter `E-5000`.** A **`CHANNEL`** column marked
`NEW`, second, holding `Total · On-peak · Off-peak · Peak demand`; four rows share one
date; the demand row reads `4.2 kW` where every other row is kWh. **No ACTIONS column.**

The *Table controls* row on p50 is explicit: *"**NEW — the shared toolkit.** … **None of
the five exists today**, and the pagination half is unpaginated at all four layers —
endpoint, selector, seam and component. Specifications `AST-B-19` and `AST-B-23`."*
*Write surfaces* is **NOTHING**. Empty states are **two different sentences**: the strip
says *"No readings on this meter yet."*, the table says *"No reads yet."*

### What the code does today

* `ReadsTab` — `AssetDetailPage.tsx:1568-1651`. Mounts `AssetUsageStrip` then a
  `<section>` holding a **hand-built `<table className={TABLE}>`** (`ReadRows`
  `:1479-1566`) and a `ListPager`.
* `AssetUsageStrip.tsx` — one chart **per register** with `avg_per_month`, `peak`, `low`
  metrics and a 12/24-month window (`WINDOWS` at `:63`), drawn through the shared
  `KPIStrip`. The "several charts, never one" reasoning is in its own header.
* Columns rendered: Date · *Channel (only when the meter has more than one register,
  `:1492-1495`)* · Reading · Import · *Export (only when `net_metering`)* · Source ·
  Status. **No Actions column.**
* Pagination is **server-side**: `apps/assets/api.py:280-282` uses `StandardPagination`
  over `selectors.asset_read_dates_page`, and the count is READ DATES rather than rows —
  reasoned in the view's own docstring.

### Gap table — screen 09

| # | Gap | Drawing says | Code says | Class | Fixed since 2.234.17? |
|---|---|---|---|---|---|
| 09-1 | No toolbar at all | search + 4 filter chips + `+ Filter ▾` + `↓ Download` + `▦ Columns` | none of the five (`:1605-1648`) | LAYOUT + **MISSING PLUMBING** — `GET /assets/{id}/reads` accepts only `page`/`per` (`api.py:280`), so search and the status filter need query parameters that do not exist | **No** |
| 09-2 | Hand-built table, not the kit | *"the shared toolkit"*; `AST-B-23`: *"Every list inside an asset is the same list, with the same controls"* | a raw `<table>` with a local `TABLE` class string (`:220-221`) instead of `DataTable` + `FilterBar` | LAYOUT | **No** |
| 09-3 | Status is a pill | a green outlined **`Committed`** pill | the served code rendered verbatim as text (`:1559`) | CONTENT | **No.** The file's own `exceptions: E3` says no signed vocabulary maps `Source`/`Status` to display words |
| 09-4 | Pagination | `1–50 of 1,460 · Rows per page 50 100 200 500 1000 · Page 1 of 30` | `ListPager` with `PAGE_SIZES = [50,100,200,500,1000]`, driven by a real server page | — | **YES — fixed.** `AST-B-19` is built, at SQL, at all four layers |
| 09-5 | Channel column | a `CHANNEL` column when the meter has more than one register | exactly that, and only then (`:1492-1495, 1502, 1520`) | — | **YES — fixed.** `AST-B-24` is built |
| 09-6 | ACTIONS column | figure 13 draws one; figures 14 and 15 do **not** | none | — | **N/A — the frames disagree.** B14 rule 37: build the shape both frames agree on. **No work; recorded.** |

**Counts: 3 gaps to build (one of them blocked on missing plumbing), 2 already fixed,
1 no-action.**

---

## Screen 10 · Export — `?tab=export` — EXISTS BEHIND · **NO COMMITMENT**
### pages 53–54 · figure 16

### What the drawing shows

**Figure 16 (p54) — a rooftop PV inverter, `PV-0001`.** Kicker **`ROOFTOP PV · PV-0001`**
(the as-built kicker, number included), pill `Installed`, place line *"Electric · Installed
Mar 2025 · 88 Cypress Row · Unit 1"*. Actions: **only `Reassign` and `Retire`** — two
buttons, no Raise work order, no Log repair, no `…`. Tab strip **Overview · Export ·
Assignment history · Work & maintenance · Audit** with **Export** underlined. One panel:

* heading **`Export`**
* a grey sub-line: **`Read from the net meter this inverter is linked to — E-5001.`**
* a table with columns **DATE · CHANNEL · QUANTITY · UNIT** (QUANTITY right-aligned)
* an empty state, centred across the table: **`No export records on the linked meter yet.`**
* **no toolbar and no pager**

*Table controls*: **None**. *Write surfaces*: **NOTHING on all four**. Health is
**UNVERIFIED — not walked**: the seeded tenant had no exporting inverter, so the document
read this screen from source only and graded nothing.

### What the code does today

`ExportTab` — `AssetDetailPage.tsx:1656-1767`. Reads the **linked meter's** reads through
the same `getAssetReads`, filters client-side to rows with an export value, and renders
columns **Date · Export (net) · Source · Status**, plus a `ListPager` added by
`DEF-AST-5117`. The sub-line is `Measured by <meter · net →>` (`assets.export.measuredBy` +
`assets.export.open`). Empty state is `assets.export.empty` = *"No export records yet."*

### Gap table — screen 10

| # | Gap | Drawing says | Code says | Class | Fixed since 2.234.17? |
|---|---|---|---|---|---|
| 10-1 | Column set | `DATE · CHANNEL · QUANTITY · UNIT` | `Date · Export (net) · Source · Status` | CONTENT | No — **and there is NO COMMITMENT**, so nothing is scoped to it |
| 10-2 | Panel sentence | *"Read from the net meter this inverter is linked to — E-5001."* | *"Measured by E-5001 · net →"* | CONTENT | No — no commitment |
| 10-3 | Empty state | *"No export records on the linked meter yet."* | *"No export records yet."* | CONTENT | No — no commitment |
| 10-4 | Header actions | two only (`Reassign`, `Retire`) | the server's action set plus the always-present `Raise work order` | — | **N/A** — the drawing is an as-built read of an unwalked screen, and `BR-AST-534` post-dates it |
| 10-5 | Pager | none drawn | a `ListPager` **is** rendered | — | **Built-but-not-drawn**, and correct: `AST-B-19` names screen 10 explicitly (*"screen 10 … calls the SAME reads endpoint against the linked meter"*). The filter still runs over one page, and the code says so at `:1681-1686` |

**Counts: 0 to build. 3 drawn/built differences recorded, 2 items where the code is ahead
of the drawing.** A NO COMMITMENT chip means *"the absence is the finding, not an
oversight"* (p3) — these rows exist so a later scoping has them, not as work.

---

## Screen 11 · Assignment history — `?tab=assignments` — EXISTS BEHIND
### pages 55–57 · figure 17 · commitments 19, 23

### What the drawing shows

**Figure 17 (p56) — `W-5001`, three addresses.** One panel:

* heading **`Assignment history`**
* explainer, grey: **`Assignment history is append-only and never overlaps — a correction closes a row and opens a new one.`**
* **toolbar**: search reading **`Search a premises, a unit or who moved it...`**, chips
  **`All` `Current` `Closed`**, **`+ Filter ▾`**, right-aligned **`↓ Download`** and
  **`▦ Columns`**
* columns, in order: **FROM · TO · PREMISE · UNIT · FINAL READ (`NEW`) · BY · ACTIONS**
* the newest row's **TO** cell holds a green **`Current`** pill, not a date
* **PREMISE** and **UNIT** cells are **red links** (`118 Bayou Bend Dr →`, `Unit 1 →`)
* **FINAL READ** holds `0012044 · 01/14/2026 →` on closed rows and `—` on the current one
* **ACTIONS** is a red eye glyph
* footer **`1–3 of 3   Rows per page 50 100 200`**, `⇤ ← Page 1 of 1 → ⇥`
* red caption: *"**NEW** — the toolbar, the pager and the Final read column. `final_read_id`
  is served on every row today and rendered nowhere, and it is the one fact a billing
  dispute about a move actually needs."*

*Variation by kind*: **none — "Checked, not assumed."** *Write surfaces*: **NOTHING**,
append-only by rule. *Walked*: empty on the seeded asset. Data-flow note, verbatim:
`asset_assignments.final_read_id is a DEFERRED FK and is UNADDABLE: meter_reads is
partitioned on (tenant_id, read_at, id), so no unique(id) exists to reference.` Health
of the Final read field is **SERVED, no FK**.

### What the code does today

`AssignmentsTab` — `AssetDetailPage.tsx:1771-1852`. Hand-built table with columns
**From · To · Premise · Unit · By**, `<strong>Current</strong>` in the To cell, plain-text
premises and unit, and a `ListPager`. Server pagination at `apps/assets/api.py:260-262`
over `selectors.assignments_page`, newest first (`selectors.py:1171+`).
Row payload (`endpoints.ts` `AssetAssignmentRow`): `id · from_date · to_date · current ·
unit_id · unit_label · premise_address · by · final_read_id`.

### Gap table — screen 11

| # | Gap | Drawing says | Code says | Class | Fixed since 2.234.17? |
|---|---|---|---|---|---|
| 11-1 | No toolbar | search + `All/Current/Closed` + `+ Filter ▾` + `↓ Download` + `▦ Columns` | none (`:1792-1850`) | LAYOUT + **MISSING PLUMBING** (`GET /assets/{id}/assignments` takes only `page`/`per`) | **No** |
| 11-2 | FINAL READ column | `0012044 · 01/14/2026 →`, a reading value, a date and a link | no column. `final_read_id` **is** served (`selectors.py:1220`) but only as a **uuid**, which B14 rule 31 forbids showing | **MISSING PLUMBING** — the row needs the read's value and date, not its id | **No** |
| 11-3 | ACTIONS column | a red eye glyph per row | none | LAYOUT | **No** |
| 11-4 | Premise and Unit are links | both red links | plain text (`:1823-1824`). `unit_id` is served so the Unit link is reachable today; **`premises_id` is not on the row** | WIRING (unit) + **MISSING PLUMBING** (premises) | **No** |
| 11-5 | `Current` is a pill | green outlined pill in the TO cell | `<strong>Current</strong>` (`:1818`) | CONTENT | **No** |
| 11-6 | Pagination | `1–3 of 3 · Rows per page 50 100 200` | `ListPager` over a real server page | — | **YES — fixed.** `AST-B-19` |
| 11-7 | Explainer sentence | *"Assignment history is append-only and never overlaps — a correction closes a row and opens a new one."* | `assets.assignments.appendOnly`, **character for character the same** | — | Already correct |

**Counts: 5 gaps to build, of which 2 are blocked on missing plumbing (11-2 and the
premises half of 11-4). 1 already fixed.**

---

## Screen 12 · Work & maintenance — `?tab=work` — EXISTS BEHIND · **NEW BUILD**
### pages 58–62 · figures 18, 19 · commitments 02, 18, 19, 21, 23

### What the drawing shows

A grey rail on p58 states the problem: **the same question has two answers in two modules.**
`asset_maintenance.cost` is summed into *Lifetime cost* on this tab; `work_order_cost_lines`
is totalled on Work's performance tab; *"reaches the ASSET: NOWHERE"*. *"So a meter whose
repairs all went through work orders shows a lifetime cost that misses every one of them."*
Both are captured and post nowhere, so it is *"a **display** problem, not a ledger one"* —
and *"the strongest argument for the merge. Two tabs could show two costs and look correct.
One tab cannot."*

**Figure 18 (p59) — `W-5001`, the Open work half.** Tab strip now reads **Overview · Reads ·
Assignment history · Work & maintenance · Audit**, with **Work & maintenance** underlined.
**Immediately under it, a second-level strip: `Open work` | `History`**, with **Open work**
underlined — *"the default sub-tab — the half you can act on, so it is the half you land
on"* (figure 19's caption). Then one panel:

* heading **`Open work`**, explainer **`Jobs raised and not yet done. Raised in Work, read here.`**
* toolbar: search **`Search work order #, type or technician...`**, chips **`Open`
  (selected) `Overdue` `Unassigned` `All`**, **`+ Filter ▾`**, right **`↓ Download`**
  **`▦ Columns`**
* columns: **WORK ORDER # · TYPE · STATE · RAISED · RAISED BY (`NEW`) · EXPECTED
  COMPLETION (`NEW`) · TECHNICIAN · ACTIONS**. Work order # is a red link; STATE is a pill
  (`Dispatched` green outline, `Overdue` red outline); TECHNICIAN shows `—` when nobody is
  assigned; ACTIONS holds an eye and a two-way arrow.
* below the table, a red **`Raise work order`** button

**Figure 19 / p60 — the History half.** Same header, `History` underlined in the
second-level strip. One panel:

* heading **`History`**, explainer **`What has actually happened, newest first. Each row says what kind of record it is.`**
* toolbar: search **`Search what happened, who did it or a work order #...`**, chips
  **`All` (selected) `Jobs` `Repairs` `Tests`**, **`+ Filter ▾`**, right `↓ Download`
  `▦ Columns`
* columns: **DATE · RECORD · WHAT · WHO · WORK ORDER · COST · OUTCOME**, COST right-aligned
* **RECORD is a pill naming the kind of row** — `Job completed` (green), `Repair logged`,
  `Job raised`, `Test logged` — and **work-order events are interleaved with maintenance
  entries in one date-ordered list**
* footer `1–4 of 4   Rows per page 50 100 200`, pager right
* below it, left: a red **`Log repair / maintenance`** button; right, on the same line:
  **`Logged on the asset $84.00 · Jobs on this asset $138.42 · Lifetime $222.42 NEW`**
* a final grey caption: *"A repair and a job are paired by **date**, never by a key —
  `BR-WRK-056` forbids a column on `asset_maintenance`. A row with no job on its date keeps
  the dash, which is the 2024 test above."*

*How you get here* (p60): *"It **replaces** **Maintenance & repairs** and **Work**, which
were two tabs answering one question. Inside it, **two sub-tabs** — the same second-level
shape the Lifecycle registry tab needs, and **URL state like every other tab**
(`BR-SHL-011`), so a person can link to either half."* *Tabs*: *"**five** on a meter or
sub-meter · five on an exporting inverter · **four** on a plain device. **One fewer than
before the merge, on every kind.**"* *Table controls*: *"**Open work** — no toolbar; a
handful of open jobs per asset, and the filter that matters (open vs all) is the split
itself. **History** — the standard pager."* *Walked*: **"Not walked — the merged tab does
not exist."**

### What the code does today

* The tab id is **`maintenance`**, so the address is **`?tab=maintenance`**
  (`ASSET_DETAIL_TABS` `:125-131`; `selectTab` `:365-369`).
* The label is **`Maintenance & repairs`** (`assets.detail.tab.maintenance`), or
  **`Tests & maintenance`** on a plain device (`:416-421`).
* `MaintenanceTab` (`:1971-2120`) renders **two stacked panels with no sub-tab strip**:
  `OpenWorkPanel` (`:1868-1969`) then a `Maintenance history` section.
* Open work columns: **Work order # (link) · Type · State (pill) · Raised · Expected
  completion · Technician**. No Actions column. No toolbar. `Raise work order` sits under
  the table (`:1962-1966`).
* History columns: **Date · Type · Technician · Detail · Work order · Cost · Outcome**.
  The work-order cell is the by-date index from `apps/work` (`:2074`). No toolbar.
  `+ Log repair` sits **above** the table (`:2034-2036`). A `ListPager` (`:2096-2107`) then
  a single line **`Lifetime maintenance {amount}`** (`:2113-2115`).
* Both halves already page server-side: `apps/assets/api.py:304-306`.

**The cross-module read — verified, and it holds.** `GET /assets/{id}/work-orders` is
mounted by **`apps/work/api.py:1681`**, not by assets; the browser calls it through
`features/work/workEndpoints.listAssetWorkOrders`. The cost rollup travels the other way
through a named seam: `apps/assets/seams.py:268-284` resolves
`apps.work.asset_door.cost_rollup_for_asset`. `apps/work/asset_door.py`'s own docstring
states the design — *"`apps/assets/**` gains no line of code at all"* — and `G78`
(`10-scripts/gates/g78_work_writes_nothing_foreign.py`) is the gate. **Nothing in this
merge requires a foreign write, and none is proposed.**

### Gap table — screen 12

| # | Gap | Drawing says | Code says | Class | Fixed since 2.234.17? |
|---|---|---|---|---|---|
| 12-1 | The address | `/:tenant/assets/{id}?tab=work` | `?tab=maintenance` | WIRING | **No** |
| 12-2 | The tab label | **`Work & maintenance`** | `Maintenance & repairs`, and `Tests & maintenance` on a device | CONTENT | **No** |
| 12-3 | Two sub-tabs with URL state | `Open work` \| `History`, Open work default, linkable (`BR-SHL-011`) | two panels stacked, no strip, no URL state | LAYOUT + WIRING | **No.** The pattern exists to copy: `AssetLifecycleTab.tsx:139, 528` does exactly this for screens 05a–05c |
| 12-4 | Open work: `RAISED BY` column | drawn, marked `NEW` | absent | **MISSING PLUMBING** — the document's own field table grades it **NOT SERVED**: *"`assigned_by` and `accepted_by` exist, `raised_by` does not"* | **No** |
| 12-5 | Open work: ACTIONS column | eye + reassign glyphs | absent | LAYOUT | **No** |
| 12-6 | History: the `RECORD` column | a pill per row — `Job raised · Job completed · Repair logged · Test logged` — with **work-order events interleaved into the list** | a `Type` column carrying only `asset_maintenance.kind`; work orders appear only as a by-date reference on a maintenance row | CONTENT + **MISSING PLUMBING** (the merged list needs work-order events served as history rows) | **No** |
| 12-7 | History: the three-figure foot | `Logged on the asset $84.00 · Jobs on this asset $138.42 · Lifetime $222.42` | one line, `Lifetime maintenance {amount}`, from the maintenance endpoint only | CONTENT | **Partly.** The three-figure arithmetic **is** built — `AST-B-21`, at `:1373-1396` — but it renders on screen 08's **Cost & value** panel, not here. Moving/mirroring it is client-only |
| 12-8 | History: toolbar | search + `All/Jobs/Repairs/Tests` + `+ Filter ▾` + `↓ Download` + `▦ Columns` | none | LAYOUT + MISSING PLUMBING | **No** |
| 12-9 | `Log repair / maintenance` placement | below the table, left, beside the cost line | above the table (`:2034`) | LAYOUT | **No** |
| 12-10 | Open work toolbar | Figure 18 draws one | none | — | **N/A — the document contradicts itself.** p60's *Table controls* row says *"**Open work** — no toolbar"*. The prose is the more specific statement and the code matches it. **No work; recorded.** |
| 12-11 | Technician when unassigned | a dash | *"Nobody yet"* (`work.orders.atPlace.nobody`) | — | **N/A — a deliberate, filed divergence**, reasoned at `:1947-1954`: a blank cell reads as a bug, and the premises and account tabs already print this key |
| 12-12 | `Raise work order` under Open work | drawn | built (`:1962-1966`) | — | **YES — fixed.** `AST-B-02`, door 2 of 4, landed 2026-09-12 |
| 12-13 | Work order # as a link into Work | drawn red | built (`:1911-1922`) | — | **YES — fixed** |
| 12-14 | `Expected completion` column | drawn, marked `NEW` | built (`:1901`, `:1940-1946`) | — | **YES — fixed.** Part of `AST-B-18`; `priority` is still deliberately absent (`:2124`) because `_scoped_row` is shared with the premises and account tabs |
| 12-15 | Pagination on History | `1–4 of 4 · Rows per page 50 100 200` | `ListPager` over a real server page | — | **YES — fixed.** `AST-B-19` / `DEF-AST-5117` |

**Counts: 9 gaps to build, of which 2 are blocked on missing plumbing (12-4, 12-6).
4 already fixed. 2 no-action.**

**What the merge needs, stated once.** Nothing in it is a foreign write. It needs (a) a
client-side sub-tab strip carrying URL state, copied from `AssetLifecycleTab`; (b) one new
tab id and its five catalogue keys; (c) a `raised_by` field on Work's scoped work-order row
— **Work's change, in Work's module, served through the door it already owns**; (d) a
history read that interleaves work-order events with maintenance entries, which is
`apps/work` publishing events on the existing `GET /assets/{id}/work-orders` and the
browser merging the two lists by date, exactly as the cost rollup already does. **No table
in `apps/work` is written from `apps/assets` and no column is added to
`asset_maintenance`** — `BR-WRK-056` forbids the second and `G78` refuses the first.

---

## Screen 13 · Audit — `?tab=audit` — EXISTS BEHIND · **NO COMMITMENT**
### pages 63–65 · figure 20

### What the drawing shows

A grey rail first, headed **"One sentence this tab must never grow"**: hard rule 4 was
narrowed on 2026-09-02 so three columns on `payments` can be corrected in place, the
replaced value then lives only in `audit_log`, and `audit_log` is pruned. *"Whether such a
row is exempt from pruning is `OQ-1340` and is **OPEN**. Until it is answered, no screen,
document or docstring may describe this path as a permanent record of the old value. **This
tab does not, today. It is listed here so that nobody adds the sentence.**"*

**Figure 20 (p63) — an inventory meter, `AST-04412`.** Kicker **`METER · AST-04412 · AMI`**
(the as-built kicker, number included), title `AST-04412`, pill `Inventory`, place line
*"×1 · In inventory · unassigned"*. Actions: **`Assign`** and a red **`Delete`**. Tab strip
with **Audit** underlined. One panel:

* heading **`Audit`**
* columns **WHEN · WHO · ACTION · WHAT CHANGED**
* one row: `09/10/2026 14:02 · Dana Whitfield · asset.created · AST-04412 created in Inventory`
* a red link below: **`Open the full audit log →`**

*Table controls*: *"Whatever the shared `AuditTab` offers — this screen composes the same
component premises, units and accounts use, rather than drawing its own."* *Write
surfaces*: **NOTHING, on principle.** *Walked*: **"Opened. Rendered. Zero failed requests."**
Health **SERVED**.

### What the code does today

`AssetDetailPage.tsx:617-626` — a `<section>` with an `<h3>Audit</h3>` mounting the shared
`AuditTab` imported from `features/metering/PremisesDetailPage` (`:88`). The shared
component (`PremisesDetailPage.tsx:2592+`) reads `getAuditLog` filtered by entity, offers a
search box and an **action filter built from the events this record actually has**, and
renders a `ButtonLink` to `auditViewerPath(...)` labelled `metering.audit.openViewer`.

### Gap table — screen 13

| # | Gap | Drawing says | Code says | Class | Fixed since 2.234.17? |
|---|---|---|---|---|---|
| 13-1 | Nothing | four columns, one row, `Open the full audit log →` | the shared `AuditTab`, which draws that and more | — | Matches. **NO COMMITMENT and nothing to build** |
| 13-2 | Toolbar richer than drawn | a bare table | search + an action filter + the shared table | — | **Built-but-not-drawn, and correct**: the document's own *Table controls* row delegates to *"whatever the shared `AuditTab` offers"* |
| 13-3 | Kicker carries the asset number | figure 20 draws `METER · AST-04412 · AMI` — an **as-built** drawing, so it is describing the fault, not prescribing it | `Meter · AST-04412 · AMI` (`:477-479`) | CONTENT | **No — and it is the same defect as 08-1**, since one header serves every tab. Fixing 08-1 fixes this |
| 13-4 | The pruning sentence | *"This tab does not, today. It is listed here so that nobody adds the sentence."* | nothing on screen says it | — | **Correct as-is. Do not add it** while `OQ-1340` is open |

**Counts: 0 gaps of its own. 1 inherited from screen 08 (the kicker). 1 standing
prohibition to honour.**

---

## Summary — concrete counts

| Screen | Chips | Gaps to build | Already fixed since `2.234.17` | Blocked on missing plumbing | No-action findings |
|---|---|---|---|---|---|
| **08 Overview** | EXISTS BEHIND · NEW BUILD | **9** | **16** | 0 | 3 |
| **09 Reads** | EXISTS BEHIND | **3** | **2** | 1 (09-1: no search/filter query params) | 1 |
| **10 Export** | EXISTS BEHIND · NO COMMITMENT | **0** | 0 | 0 | 5 recorded differences |
| **11 Assignment history** | EXISTS BEHIND | **5** | **1** | 2 (11-2 final read value; 11-4 premises id) | 0 |
| **12 Work & maintenance** | EXISTS BEHIND · NEW BUILD | **9** | **4** | 2 (12-4 `raised_by`; 12-6 interleaved events) | 2 |
| **13 Audit** | EXISTS BEHIND · NO COMMITMENT | **0** (1 inherited) | 0 | 0 | 2 |
| **Total** | | **26** | **23** | **5** | **13** |

**Read that first column against the second.** Twenty-three of the forty-nine differences
this section describes **are already gone**, almost all of them landed by `CR-092-BRC01`
step 2 on 2026-09-12 — twenty-seven change-versions after the document was read. The
biggest single piece of work in the whole blueprint, screen 08's six-panel redesign, is
**built, derived and tested**; what is left of it is nine small things, eight of them
labels, one word orders and one kit control.

**The three biggest gaps per screen:**

* **08** — the asset number is still printed twice (kicker *and* title) · the place line
  neither leads with the address nor carries the account and still shows the multiplier ·
  Edit and Delete are visible buttons where the drawing puts them under a `…` the kit does
  not have.
* **09** — no toolbar at all, and the reads endpoint takes no search or filter parameter to
  build one on · the panel is a hand-built table rather than the shared `DataTable` +
  `FilterBar` · the status renders as a raw served code instead of a pill.
* **10** — no commitment; the three recorded differences are a different column set, a
  different panel sentence and a different empty state. **Nothing to schedule.**
* **11** — the `FINAL READ` column, which the document calls *"the one fact a billing
  dispute about a move actually needs"* and which is blocked because only the read's **uuid**
  is served · no toolbar · the premises and unit cells are plain text where the drawing
  links them.
* **12** — the merge is only half done: the Open work panel was added to the old tab, but
  there are **no sub-tabs, no URL state, and the tab is still `?tab=maintenance` labelled
  *Maintenance & repairs*** · the History list does not interleave work-order events and has
  no `RECORD` column · the three-figure cost line is built but sits on screen 08 instead of
  under History.
* **13** — nothing of its own; it inherits screen 08's kicker fault, and it carries a
  standing prohibition (do not add a "permanent record" sentence while `OQ-1340` is open).

**Two document faults worth carrying forward.** The AST-R set is given **four different
counts in one section** (fifteen in the prose, sixteen in the table, thirteen in the
summary, `01–13` in screen 08's own Rules row) — B14's rule-count rot in a new family. And
the *What's due* pencil is **forbidden on page 36 and specified as screen 16 in the same
document**; the code follows screen 16.

**Nothing in this pass was built, and no register, id or product file was touched.**
