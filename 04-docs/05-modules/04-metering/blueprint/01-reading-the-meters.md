# § 02 · Reading the meters — the drawing against the running product

**Scope.** Blueprint entries **01, 02, 03, 04, 05, 06** — PDF pages **8–20** (page 21 read
too, because entry 06's rail runs onto it), read **AS IMAGES** at scale 2, and re-cropped at
scale 5–8 for the table, the column picker and the three dialogs, per **B14 rule 42**.

**Measured at** product version **`2.261.3`**, branch `claude/hi-0jmv62`, commit `7b1dc74f`,
on **2026-09-13** — **24 versions after the blueprint was read** (`2.237.10`, 2026-09-12).
Every as-built sentence below was re-established this pass. Nothing is copied forward from
the document.

**How.** Pages 8–21 rendered with `10-scripts/pdf/pdf_render.py`. Code read in
`07-frontend/src/features/metering/ReadsListPage.tsx`, `ReadDetailPage.tsx`,
`readsShared.tsx`, `07-frontend/src/components/DataTable.tsx`,
`07-frontend/src/api/endpoints.ts`, `07-frontend/src/api/paginated.ts`,
`07-frontend/src/i18n/locales/en.json`, `06-backend/apps/metering/api.py`, `selectors.py`,
`services.py`, `validation.py`, `read_import.py`. Walked in Chromium against the deployed
join (SPA `:8080`, API `:8011`, tenant `brazosbend`, signed in as Dana Whitfield) **at 1280
AND 1440** — both widths produced identical structure, and **no page in this scope scrolls
horizontally at either width**. Six readings opened (total · demand · TOU · export channels
present in the seed); the Dispute and Correct dialogs opened and read in the browser.

**This file measures and routes. It builds nothing, edits no `.tsx`, and allocates no id.**

---

## 0 · THE HEADLINE — WHAT THE DOCUMENT SAYS, AND WHAT IS TRUE TODAY

| The document's claim | State at `2.261.3` |
|---|---|
| *"The reading detail page does not open."* | **ALREADY FIXED.** Three readings opened at 1280 and 1440 with **zero page errors**. `ReadDetailPage.tsx:469` reads `historyQuery.data?.rows` |
| Entries 04, 05, 06 · *"Not walked. Entry 03 throws before its header renders, so none of its three dialogs can be reached in the running app."* | **STALE for two of the three.** Entry 04 and entry 05 were opened and read in Chromium this pass. Entry 06 is still unwalked, for a **different reason** — see §7 |
| Entry 03 field ⑯ · *"Read history rows — SERVED, UNPAGINATED"*, flow *"BREAKS AT PAGINATION"* | **STALE.** `getAssetReads` returns `PagedRows` through `readListPage` (`endpoints.ts:8772`); `endpoints.ts:8640` records that the route *"went onto the house envelope in `2.237.8`"*. The **server half is done**; the screen half is not — see gap **B27** |
| Entry 04 rail · *"the freeze is `OQ-209`, reported and unresolved"* | **STALE.** `OQ-209` reads **CLOSED (CR-038)**, ruled 2026-08-26, option (a), PO verbatim *"Never update the value backword"*. What the rail actually raises is a **different** question that `OQ-209` never asked — carried forward as **Q1** |
| *"A primary button renames itself for a door it will not open."* | **CONFIRMED, still true.** See defect **D2**. ⚠ **Could not be walked** — 0 of 24 seeded reads carry `lifecycle: "billed"` |
| Entry 02 · *"Twelve of fifteen columns are visible"* | **TRUE of the as-built.** 15 columns declared, 12 default-visible, counted in `ReadsListPage.tsx:244–307` and confirmed on screen |

**Four of the document's own as-built sentences are already overtaken; one is confirmed.**

### The count

| | build | defect | question | on screen, not drawn |
|---|---|---|---|---|
| 01 · Reads — Needs attention | 3 | 0 | 1 | — |
| 02 · Reads | 13 | 1 | 0 | 1 |
| 03 · One reading | 17 | 5 | 1 | 3 |
| 04 · Correct the reading | 3 | 0 | 1 | 0 |
| 05 · Dispute the reading | 4 | 0 | 0 | 0 |
| 06 · Clear the dispute | 4 | 1 | 0 | 0 |
| **Total** | **44** | **7** | **3** | **4** |

---

## 1 · ENTRY 01 · Reads — Needs attention · p8 · ~~`/:tenant/reads?tab=attention`~~

The drawing is **struck through**. The entry is kept rather than deleted so the next reader
finds out what happened to it. The document's ruling card, quoted as drawn:

> **Ruled 2026-09-12 — and it reverses a signed rule**
> **"Need Attention — does not add any value."** The tab goes. That supersedes `BR-MET-060`,
> which says Reads *opens* on the exceptions, and retires `US-MET-019`, the story that built
> the three counts. **Stated rather than assumed**, because a ruling that collides with a
> signed rule has to name what it displaces.
> Two of the three counts survive the move and one does not. *Flagged* and *Disputed* are
> already declared filters on All reads, so they become a filter click. ***Missing* has no
> filter and never has** — the server cannot slice the reads list that way. It moves to Read
> cycles instead.

### What is on screen today

Walked at 1440. `/:tenant/reads` with no `?tab=` **lands on Needs attention**, which has **no
table** (`tables: 0`) and renders, in this order:

```
Your day starts at the exceptions: records the cycle has not collected, readings a rule
flagged, and readings a customer has disputed. The full list is one tab away.

MISSING   18   Plan-required readings not yet collected. Counted while the reading window
               is open, and after it closes until the bill run covers that period.
               2 meter(s) could not be checked — no reading is expected of them yet.
FLAGGED   24   Show the flagged readings →
DISPUTED   0   Show the disputed readings →

Counts come from committed readings and reconcile with the slices behind them.
```

`ReadsListPage.tsx:24` states the superseded rule in its own words — *"**It lands on Needs
attention** (BR-MET-060), on EVERY open."*

| # | Route | Gap |
|---|---|---|
| **B1** | build | The **Needs attention** tab still renders and is still the landing tab. `?tab` absent must land on **All reads** |
| **B2** | build | The **three tiles** still render. *Flagged* → the declared `status` filter · *Disputed* → the declared `disputed` filter · *Missing* → entry 20, the cycle detail |
| **B3** | build | The 34-word **explainer paragraph** still renders above the tiles. It goes with the tab |

**Front end only.** `GET /reads/needs-attention` is mounted at `api.py:3056` and keeps its
other caller on the Dashboard.

**Genuinely lost, and the document records it as a cost rather than arguing against it:** the
**all-clear**. After this there is no one place that says *nothing needs attention* across the
whole tenant. Per cycle, yes; across the tenant, no.

⚠ **B1–B3 cannot start until Q2 below is settled.** The ruling that authorises them exists
in no file in this repository.

---

## 2 · ENTRY 02 · Reads · p9 · `/:tenant/reads`

Chips: `EXISTS BEHIND` · `NEW READ` · `NEW BUILD` · `MR-04 · MR-26 · MR-27 · MR-31`.
Sub-line: *"now the landing tab · every control writes itself into the URL"*.
The question the screen answers: *"Show me the reading for this meter so I can check it
against the bill."*

### What the drawing draws, read off the image

* **Header actions**, left to right: `+ Add reading` · `Estimate a missing read` ·
  `Route sheet PDF` · `↑ Upload reads` (accent-outlined, the primary).
* **Tabs**: `All reads` (active, accent underline) · `Read cycles`. **Two tabs, and neither
  is Needs attention.**
* **Toolbar**, one row: `[🔍 Search meter # or address…]` `All` `+ Filter ▾`
  `☐ Search archive` … `↓ Download CSV` `▦`.
* **COLUMNS panel, drawn open.** Heading `COLUMNS`, two columns of checkboxes —
  left ☑ Meter · Read date · Cycle · Route · Service · Premise · Previous · Current;
  right ☑ Usage · Source · Status, then ☐ ⑥ **Register** · ☐ ⑦ **Batch** · ☐ ⑧ **Plan**
  (all three in accent) and ☐ Days since prior. Footer: `↑↓ to reorder` (left) ·
  `Reset table` (right, accent). **Fifteen entries, and `Select` is not one of them.**
* **Table header**: `☐ · METER ⇅ · READ DATE ⇅ · CYCLE · ROUTE · SERVICE · PREMISE ·
  PREVIOUS · CURRENT · USAGE ⇅ · SOURCE · STATUS ⇅`. `PREVIOUS` and `CURRENT` are drawn
  **right-aligned over right-aligned figures**.
* The **first row is shaded** — the document's note says that is deliberate, *"to show the
  whole row is now the target, not the meter cell alone"*.
* **Footer**: `Showing 1–24 of 24` (left) · `Rows per page 50  ⇤ ← Page 1 of 1 → ⇥` (right).
* Beneath: *"Showing the last two years. Older readings need the archive search."*

### What matches, exactly — do not touch these

Header actions: **four, same labels, same order** (`+ Add reading`, `Estimate a missing read`,
`Route sheet PDF`, `↑ Upload reads`; the last is `variant="primary"`). Table columns: **twelve
visible, in the drawn order**. Sortable set: **Meter, Read date, Usage, Status** — exactly the
four the drawing marks `⇅`. Toolbar element order. Page title **32px** (B14 rule 40). Page-size
options `50/100/200/500/1000`. The archive checkbox and its sentence. The `E` service glyph.
The `Peak` chip on a demand row's Usage cell. No horizontal scroll at either width.

### Drawn and missing

| # | Route | Gap | Evidence |
|---|---|---|---|
| **B4** | build | **No `Read cycles` tab.** Tabs today are `Needs attention` · `All reads`. Callout ③: *"Read cycles · replaces the two doorless screens · r10 RDS-02R/02C · NEW"* | `ReadsListPage.tsx:789–798` |
| **B5** | build | `All reads` is not the landing tab. Callout ②: *"now the landing tab — `?tab` absent lands here · CHANGED"* | see B1 |
| **B6** | build | Search placeholder is **`Search meter #…`**; drawn **`Search meter # or address…`**. Callout ④ marks it `NEW READ — needs the server`: `read_list` filters `asset__asset_no__icontains` and nothing else, so the label is presently honest and the **server half must land first** | `en.json` `metering.reads.searchPlaceholder`; `ReadsListPage.tsx:318` states the reason |
| **B7** | build | Column label is **`Channel`**; drawn **`Register`**. Callout ⑥: *"RELABELLED — one word for one thing, and Register is the clerk's"* | `metering.reads.col.channel` |
| **B8** | build | **No `Plan` column at all.** Measured from the live payload: a reads row carries **53 keys and `plan` is not one of them**. Server work | walked `GET /reads?per=200` |
| **B10** | build | Picker heading is **`Columns · show / hide · ↑↓ reorder`**; drawn **`COLUMNS`**. Five-plus words where B14 rule 33 caps a heading at **three** | `en.json` `table.columns.title` — **shared**, see blast radius |
| **B11** | build | No footer hint. Drawn: `↑↓ to reorder` beside `Reset table`. As-built puts an `↑ ↓` pair on **every row** instead | `DataTable.tsx` column chooser |
| **B12** | build | The picker lists **`Select`** and lets a clerk hide the row-select column — which takes the bulk bar with it. The drawing does not offer it | measured: 16 picker rows vs the drawing's 15 |
| **B13** | build | **Row affordance is the Meter cell alone.** Measured: of 12 `<td>` in row 1, exactly one contains an `<a>`. `tr.className` is `data-table-row` with no click handler and no pointer cursor. Drawn: the whole row | walked |
| **B14** | build | Pager reads **`1–24 of 24`**. B14 rule 16 and the drawing both require **`Showing 1–24 of 24`** | `en.json` `table.pager.range` |
| **B15** | build | **No `Page x of y`.** The catalogue key `table.pager.pageOf` exists and only `ListPager.tsx:69` uses it; `DataTable.tsx:934–977` never renders it | measured: pager buttons are `Previous page`, `Next page` and nothing else |
| **B16** | build | **No first/last controls.** `DataTable` draws `‹` and `›` only; the drawing and rule 16 both draw `⇤ ← … → ⇥` | `DataTable.tsx:956–977` |
| **B17** | build | **Header and body disagree on alignment.** `PREVIOUS`/`CURRENT` `<th>` compute `text-align: left` while their `<td>` carry `cell-num` and compute `right`. The drawing right-aligns both | measured at 1440 |

### On screen and not drawn

| # | Route | Item |
|---|---|---|
| **N1** | build | *"A corrected reading appears once: the list shows the current version of each chain."* renders under the table. The drawing shows only the archive sentence there |

### Defect

*(`B9` is deliberately unused: the Batch column started as a build item and is routed as a
defect below, because the column exists and is breaching a rule today rather than merely
differing from the drawing.)*

| # | Route | Defect |
|---|---|---|
| **D1** | defect | **The `Batch` column prints a raw uuid to a clerk.** `ReadsListPage.tsx:637–644` renders `row.import_batch_id` verbatim with the explanation on `title`. **B14 rule 31** — *"nothing internal is ever visible to a utility user — not an id"* — and the rule's own escape does not apply, because a human-facing number **does** exist: `read_import_batches.batch_no`, which the detail page already shows (`RB-2609-0004`, walked). The column is `defaultVisible: false`, so it is one click from any clerk rather than on screen by default. Callout ⑦ asks for exactly this fix and marks it `NEW READ — needs the server`: `read_dict` serves 41 keys and `batch_no` is not among them |

### ⚠ Blast radius, and it is the reason B10 and B14–B16 are not Reads work

`table.columns.title`, `table.pager.range`, `table.pager.pageOf` and the pager markup all live
in **`components/DataTable.tsx`** and the **shared** `table.*` catalogue. Changing any of them
changes **every list table in the product on this screen's authority**, which is what B14
rule 38's reasoning forbids. Four of these five are also **B14 rule 16 breaches that predate
this blueprint**. They should be scoped as one shared-kit change, not folded into a Reads wave.

---

## 3 · ENTRY 03 · One reading · p12 · `/:tenant/reads/:readId`

Chips: `EXISTS BEHIND` · `NEW READ` · `NEW BUILD` · `MR-01 · MR-05 · MR-15 · MR-32 · MR-39 ·
MR-45 · MR-46 · MR-47 · MR-48 · MR-52`. Second address: `/:tenant/reads?read=<id>` (entry 19).
The question: *"Why is this reading flagged, and can I prove to a regulator where the number
came from?"*

> **Ten sections become six, and the page splits into two columns** — the left answers *is this
> number right?*, the right answers *where did it come from?* Nothing is dropped.

### What the drawing draws

**Head**: `← Reads` · kicker `READING · M-7450 · TOTAL REGISTER` · title **`Reading`** · a chip
row of **three**: ③ `High usage` (amber), then ⑮ `E Electric` and `Total register`. Actions,
right: ④ `Dispute` (outlined) · ⑤ `Override read` (accent, the primary). **No Estimate button.**

**Band**, full width, 4 across, 2px rules top and bottom:
`PREVIOUS 4,110 kWh / 08/01/2026` · `CURRENT 4,320 kWh / 08/31/2026` ·
`USAGE 210 kWh / 30 days` · `STATUS [High usage] / 11 of 12 rules passed`.

**Left column** — ⑥ `CALCULATION`: `(4,320 − 4,110) × 1 = 210 kWh`, then ⑬ *"Registers this
plan expects · Time of use · On-peak ✓ · Off-peak ✓ · Mid-peak missing · Total ✓ ·
3 of 4 · see the meter →"*. ⑦ `FLAGS`: a bordered card, **`High usage`** bold with one prose
line under it — *"154% of a 5.2 kWh average · threshold 150% · 3 readings in the average"* —
then *"Could not run · Master vs sub-meters — no master meter on this premises"* and ⑭ *"On a
demand register this line reads differently · the billable figure is the peak itself in kW,
never a difference of two peaks"*. ⑧ `HISTORY`: `v1 · current version · no corrections`, a
four-column table `READ DATE · CURRENT · USAGE · SOURCE`, and ⑨ a pager
`Showing 1–2 of 2 … Rows 50 ⇤ ← 1/1 → ⇥`.

**Right column** — ⑩ `LOCATION`: five chips `CY-001` `RT-001` `Total register` `File import`
`Walk-by`, then `2201 Cane Island Pkwy · P-00002`, then `Unit 1`, then ⑪ **`ACC-2042`** as a
live link. ⑫ `EVIDENCE`: eight rows — `Batch · File · Hash · By · At · Session · Certified ·
Approvals`.

### What is on screen today

Title **`Meter reading detail`**. Kicker `READING · M-7210 · TOTAL REGISTER`. **One** chip
(the status). **Three** actions: `Estimate` (disabled), `Dispute`, `Override read`. Body is a
**single 720px column** (`max-w-[720px]`, measured 720px at 1440); the four figures sit in a
**2 × 2 grid** (`grid-template-columns: 354px 354px`), not a 4-across band. Sections, in order:

```
HOW THIS USAGE WAS WORKED OUT · WHY THIS READING IS FLAGGED · TAGS ·
PREMISE / UNIT / ACCOUNT · COMPLIANCE METADATA · SUPERSESSION HISTORY ·
READ HISTORY (THIS METER)
```
plus three conditional ones — the dispute banner, the net-meter pair and `BILLED CORRECTIONS`.
**Ten sections, stacked.**

### Drawn and missing

| # | Route | Gap |
|---|---|---|
| **B18** | build | Title is `Meter reading detail`; drawn **`Reading`**. Four words where B14 rule 33 caps a heading at three — the drawing fixes a rule breach here, it does not create one |
| **B19** | build | **Service and register are not in the head.** ⑮, a PO ruling of 2026-09-12: both are served on the row today and both are buried — the service inside `Location`, four groups down, and the register only in the kicker. *"They belong with the identity because they decide how the number is read"* |
| **B21** | build | On a billed reading the primary must become **`Correct billed read` and be LIVE**, posting `POST /reads/{id}/billed-correction`. The endpoint is mounted at `api.py:3067` and its docstring calls it *"the ONLY door a BILLED read's correction has"*. **No front-end caller exists anywhere** (grepped: only comments and test prose). The door also needs an **invoice** field — `metering.read.invoice_required` — which the Override form has no room for |
| **B22** | build | The four figures are a **2 × 2 grid**, not a full-width 4-across `KPIStrip` band with 2px rules |
| **B23** | build | The body is **one 720px column**. Drawn: two columns at 1440, the right dropping beneath the left at narrow widths, nothing reflowing inside a section |
| **B24** | build | **Ten sections, not six** |
| **B25** | build | Heading `How this usage was worked out` → **`CALCULATION`** |
| **B26** | build | Heading `Why this reading is flagged` → **`FLAGS`** |
| **B27** | build | `HISTORY` must merge **Supersession history + Billed corrections + Read history** into one section **with a pager** (⑨, B14 rule 16). The envelope's `count` is already served and the page throws it away: `ReadDetailPage.tsx` calls `getAssetReads(asset_id, client)` with no page argument and renders `historyQuery.data?.rows` with no footer, so a meter past one page shows a truncated table **with nothing saying so** |
| **B28** | build | `LOCATION` must merge **Tags + Premise / unit / account** into one section |
| **B29** | build | `EVIDENCE` is **eight rows** with the drawn short labels (`File`, `Hash`, `By`, `At`, `Session`, `Certified`). As-built is ten rows with `Source`, `File hash (SHA-256)`, `Uploaded by`, `Uploaded at`, `Session · IP`, `Certified by uploader` |
| **B30** | build | The **account is drawn as a live link** (⑪ `ACC-2042`, `NEW READ`). As-built prints *"The account is not served on a reading; open it through the unit."* `meter_reads.account_id` is a real column in the reviewed cross-module set and `read_dict` serves **41 keys, none of them `account_id`** |
| **B31** | build | **The plan's expected register set is nowhere on this page.** ⑬. The data is already stored: the `plan_registers` rule outcome carries `expected`, `received`, `missing`, `unexpected` and `plan_model` (walked, verbatim, on M-7450). Its severity is `ok`, and `flaggedOutcomes` (`readsShared.tsx:285`) drops `ok` and `not_evaluated` — so today **a clerk looking at one TOU window cannot see that a sibling never arrived** |
| **B32** | build | ⑭ is absent. On a demand read, `CALCULATION` says only *"This reading carries no register pair, so there is no difference to show."* — walked on M-7210/demand. It never says what the billable figure **is** |
| **B33** | build | `FLAGS` renders a bold rule name **+ a `WARNING` severity badge + a `<dl>` of key/value rows**. Drawn: bold name + **one prose line**, no badge |
| **B34** | build | *"Rules that could not run"* is a separate bold heading over a `<ul>`. Drawn: one inline `Could not run · …` line inside the FLAGS card |
| **B35** | build | The calculation line reads **`Register: (46754.000000 − 44000.000000) × 10.000000 = 27540 kWh`** — a prefix the drawing does not have, and raw `NUMERIC(18,6)` operands. Drawn: `(4,320 − 4,110) × 1 = 210 kWh`. ⚠ **Display only** — the arithmetic, the operands and the served result are untouched, so no B4/B5 figure moves |

### On screen and not drawn

| # | Route | Item |
|---|---|---|
| **N2** | — | The `Estimate` button — see **Q3** |
| **N3** | build | `EVIDENCE` carries two extra rows: `Rule outcomes` (`4 of 5 rules passed`, already in the band) and `Version` (already the head of `HISTORY`) |
| **N4** | build | A **seventh** tag. Walked rows draw `ELECTRIC · CYCLE CY-004 · ROUTE RT-005 · TOTAL REGISTER · MANUAL ENTRY · AMR · DRIVE-BY`; the drawing's `LOCATION` carries **five**, with the service promoted to the head (B19) |

### Defects — five, and **four of them are not in the blueprint at all**

| # | Route | Defect |
|---|---|---|
| **D2** | defect | **A refusal sentence that is false.** On a billed reading `overrideBlockedReason` returns `metering.read.action.billedLocked` — *"This reading is already billed. Its correction has to travel with the money fix, **and that path is not built**."* The path **is** built (`api.py:3067`), and the server's own copy sends clerks to it: `metering.read.cascade_billed_recommendation` = *"This reading was billed. Correct it through the billed-correction door."* Hard-won law 2's mirror — a live screen behind a dead control — and a product telling a clerk to use a door it then denies exists. ⚠ **Not walked**: 0 of 24 seeded reads are `billed` |
| **D3** | defect | **A rule number is printed to a clerk.** `validation.py:1524` stores `{"occupied": False, "basis": "no active account on the unit (BR-MET-036)"}` and `OutcomeCard` renders the detail bag verbatim. Seen live on **2 of 2** readings opened, under `WHY THIS READING IS FLAGGED`. **B14 rule 31** names `BR-…` by family. It is stored on committed rows, so a copy edit alone will not clear the ones already written |
| **D4** | defect | **`OutcomeCard` prints raw payload keys as field labels.** `detailLabel` (`readsShared.tsx:342`) falls back to the raw key. `basis` and `occupied` render as labels today. Latent behind severity: the `plan_registers` bag carries **`plan_id`, a raw uuid** (`01a09bc5-a577-7d9b-99bc-6cea00393b46`, walked) and `basis: "BR-MET-049 — the unit's plan determines the required read set per meter"`. `plan_registers` is `ok` on every seeded read, so the day it fires the screen prints a primary key and a second rule number. B14 rule 31 |
| **D5** | defect | **Raw machine reasons reach the clerk.** Under *"Rules that could not run"*, walked verbatim: `Unit matches the tariff — maximum_register_not_priced_by_schedule_uom` (demand read) and `Unit matches the tariff — no_version_in_force` (TOU read). `reasonText` (`readsShared.tsx:347`) falls back to the raw key and neither has a `metering.read.reason.*` entry |
| **D6** | defect | **One screen spells the same quantity two ways.** The `CURRENT` tile prints `46754 kWh` and `4110 kWh` (the server's `current_value_display`, no separator); the `READ HISTORY` table four sections below prints `46,754 kWh` and `27,540 kWh` (the client's `formatQuantity`, with one). Both on one page, walked at 1440. The drawing groups: `4,110 kWh` |

---

## 4 · ENTRY 04 · Correct the reading · p16–17 · a dialog on entry 03

Chips: `EXISTS BEHIND` · `NEW BUILD` · `BLOCKED` · `MR-24 · MR-31`.
The question: *"The collector re-read it. Put the right number in without destroying the old one."*

### What the drawing draws

```
READING · MTR-0452
Correct the reading for MTR-0452
────────────────────────────────
Corrected register value *
[ 1,014 ]
In kgal. Usage and flags recompute.

Reason *
[ collector re-read ]
Stored on the correction — “collector re-read”.

The new value becomes the current reading; this one stays in the history.
────────────────────────────────
                     [ Cancel ]  [ Record the correction ]
```
`FormModal` at its declared **560px**, ink scrim 45%, 2px rules under the header and over the
footer, square corners; the helper sits **under** its input (B14 rule 39).

### Walked at 1440 — width **560px**, height 456px, and it opens

| # | Route | Gap |
|---|---|---|
| **B36** | build | **Field order.** The consequence — *"The new value becomes the current reading; this one stays in the history."* — is the **first** child, above `Corrected register value`. The drawing puts it **last**, after both fields and before the footer rule |
| **B37** | build | Value helper is **`In kWh — consumption and every rule are recomputed.`** — one sentence, eight words. Drawn: **`In kgal. Usage and flags recompute.`** — two sentences, 2 + 4. B14 rule 33: an INSTRUCTION caps at six words **per sentence**, and *"two sentences of six beat one sentence of twelve"* |
| **B38** | build | The input prefills **`46754.000000`** (walked), the raw `NUMERIC(18,6)` string. Drawn: `1,014`. ⚠ **Checked for a money risk and there is none**: `read_import._parse_decimal` (`read_import.py:816–826`) does `raw.strip().replace(",", "")` before `Decimal(text)`, so a grouped or trimmed prefill posts identically. Display only |

**Matches, verbatim:** the kicker shape, the title template, both labels with their asterisks
(rule 10), the Reason helper character-for-character, the consequence sentence
character-for-character, `Cancel` then `Record the correction`, 560px, helper-under-input.

⚠ **The drawing draws `Record the correction` greyed with a filled-in Reason.** Walked, it is
**enabled** on open with the Reason empty; the schema refuses on submit. The drawn greying is a
*state*, not a figure, so B14 rule 37 does not settle it — **recorded, not counted**, because
the drawing and the code disagree about *when* it greys rather than *whether* it can.

⚠ **Could not walk:** the billed refusal (*"a billed read is refused here and routed to the
other door"*) — no billed read in the seed.

---

## 5 · ENTRY 05 · Dispute the reading · p18–19 · a dialog on entry 03

Chips: `EXISTS BEHIND` · `NEW BUILD` · `MR-31`.
The question: *"The customer says this is wrong. Stop the bill until somebody looks."*

### What the drawing draws

```
READING · MTR-0452
Dispute the reading for MTR-0452
────────────────────────────────
▌ Under dispute: 8 kgal               ← a warning rail, amber left bar

What is the customer disputing? *
[ property reported vacant since July ]
A System Admin reads this.

The reading is not changed, and the account leaves the next bill run until a
System Admin clears it.
────────────────────────────────
                        [ Cancel ]  [ Record the dispute ]
```

### Walked at 1440 — width **560px**, height 424px, and it opens

Rendered order: consequence → figure → label → textarea → helper → Cancel → Record the dispute.

| # | Route | Gap |
|---|---|---|
| **B39** | build | **Field order is reversed at the top.** As-built puts the **consequence first** and the figure second; the drawing puts the **figure first** (as its rail) and the consequence **last**, immediately above the footer |
| **B40** | build | The figure renders as a plain `<Note>` paragraph, identical in treatment to the consequence beside it, so the two read as one block. Drawn: a **warning rail** with an amber left bar. The document names the component: `FormModal · TextField · warning rail` |
| **B41** | build | Helper is **`A System Admin decides this later from exactly this sentence — “property reported vacant since July”.`** — one sentence, ~14 words with the example inside it. Drawn: **`A System Admin reads this.`**, five words. B14 rule 33 |
| **B42** | build | The drawing moves the example **into the input** (`property reported vacant since July`), which is where B41's words went. As-built the field is empty |

**Matches, verbatim:** kicker, title template, label + asterisk, the consequence sentence
character-for-character, `Cancel` then `Record the dispute`, 560px.

⚠ **Could not walk:** the billed case. `DisputeModal` renders a `RefusalStrip` carrying
`metering.read.dispute.billedBillStands` — **51 words** — when `lifecycle === "billed"`. No
billed read is seeded, and the drawing does not draw this state, so it is **unmeasured in both
directions** and is not counted as a gap.

---

## 6 · ENTRY 06 · Clear the dispute · p20–21 · a dialog on entry 03 · **System Admin only**

Chips: `EXISTS BEHIND` · `NEW BUILD` · `MR-31`.
The question: *"I have looked. Let the account bill."*

### What the drawing draws

```
READING · MTR-0452
Clear the dispute on MTR-0452
────────────────────────────────
Note (optional)
[ site visit 09/04 — meter reads correctly ]
Stored in the audit trail.

The account returns to the next bill run and will be billed on this reading as it stands.
────────────────────────────────
                   [ Cancel ]  [ Clear it and let the account bill ]
```
The document's own note: *"The submit label is a sentence rather than a verb, because what it
does is not* clear *— it is* let the account bill*. There is **no cleared-reason column**: the
note goes to the audit trail only, and the helper says so rather than implying it lands on the
reading."*

### ⚠ NOT WALKED, and for a new reason

**0 of 24 seeded readings carry `disputed: true`**, so `read.disputed` is never true, so the
header never swaps `Dispute` for `Clear the dispute` and the dialog cannot be reached. This is
**not** the crash the document blamed — entry 03 opens fine. Read from
`ReadDetailPage.tsx:1224–1272` and the catalogue instead, and **graded UNVERIFIED for that
reason**.

| # | Route | Gap |
|---|---|---|
| **B43** | build | **Field order.** As-built: consequence → outcome paragraph → label → textarea → helper. Drawn: label → input → helper → consequence |
| **B44** | build | An **extra paragraph the drawing does not have**: `metering.read.dispute.clearOutcome` — *"Clearing records that the reading stands and the bill was always correct; if the reading is wrong, use the billed correction instead."* 23 words, two clauses, and the second half is **rationale**, which B14 rule 33 puts at **zero words on screen** |
| **B45** | build | Helper is **`Stored in the audit trail, not on the reading.`** (9 words). Drawn: **`Stored in the audit trail.`** (5). B14 rule 33 caps a FACT at six |
| **B46** | build | The drawing carries the example **in the input**; as-built the field is empty |

**Matches, verbatim:** kicker, title template, `Note (optional)` (rule 10 — correctly **no**
asterisk), the consequence sentence character-for-character, `Cancel` then
`Clear it and let the account bill`.

### Defect

| # | Route | Defect |
|---|---|---|
| **D7** | defect | **Clearing a dispute leaves no trace on the reading.** `dispute_cleared_at` and `dispute_cleared_by` are written by `services.clear_dispute`, **served** by `read_dict` (both in its 41 keys) and **typed** at `endpoints.ts:12375–12376` — and rendered **nowhere** on entry 03. `ReadDetailPage` gates the whole dispute banner on `read.disputed`, which clearing sets false, so the banner vanishes with the marker. The document states the cost exactly: *"this page shows no trace it ever happened, so the next person reopens a question that was answered."* This is a **served fact reaching no screen**, and it is the audit half of an action the product restricts to a System Admin |

---

## 7 · THE THREE QUESTIONS — BOTH SIDES, NOTHING DECIDED

> B14 rule 41: *"the only exception to the rule can be in case any rule or BR is not matching
> or contrdicting — in such case you can ask us."* These three are that case. Every other
> divergence above is ours to build.

### Q1 · A reading filed on the WRONG REGISTER is permanent, and nothing on any screen says so

**Raised by the drawing** (entry 04's rail, p18), **not decided by it.** ⚠ Checked first, per
hard-won law 13: the rail cites `OQ-209` as *"reported and unresolved"* and **`OQ-209` is
CLOSED** (CR-038, 2026-08-26, option (a); PO verbatim *"Never update the value backword"*).
What `OQ-209` settled is that the measurement freeze is lawful. **It never asked what happens
when the frozen measurement is on the wrong register.** So this is a new question, not a re-ask.

**What the code does, verified this pass.** `supersede_read` accepts **two fields — `value` and
`reason`** (`services.py:8395–8431`); it cannot move a reading to a different register, and
neither can the billed correction. That is enforced in the database: metering migration `0007`'s
trigger freezes `asset · read_at · channel · prior/current value · multiplier · consumption ·
unit`. The only line in the module that ever sets a channel is the import parser. Hard rule 4
means there is no delete to fall back on.

**Side A — what happens.** Two things at once, and only one is visible. The **right** register is
still missing: `plan_registers` warns, the meter joins the chase list, somebody estimates it —
an estimate standing in for a reading that already arrived, filed one column over. The **wrong**
register now holds a reading: **informational only**, riding along as `unexpected` in the rule
detail, **never a severity**, because the rule *"judges only the SHORTFALL"* in its own docstring.

**Side B — why it is a money path and not a tidiness question.** On a demand or TOU plan the
registers' units differ (`kW` against `kWh`, `BR-MET-143`), so the wrong column is not merely the
wrong label. This repository has already paid for it once: **`DEF-797` — 412 kW billed as 14 kWh,
`$154.00` against `$4,532.00`.**

**The four shapes the document puts on the table, quoted, and not chosen between:**
**(a)** let a correction carry a channel — **which reopens `OQ-209`** · **(b)** a re-register path
that supersedes the wrong row and creates the right one, two rows and no update — *"the only
shape that leaves hard rule 4 intact"* · **(c)** leave it and say so on screen, which today no
screen does · **(d)** **stop it at the door** — refuse at validate when a row's register is not in
that meter's expected set, where today it is a silent `unexpected`.
The document adds: *"(d) is the preventive half and costs nothing the other three cost; it is the
only one of the four this document recommends without a ruling."*

⚠ **This lane decides none of them.** `MR-24` is the specification; `B31` above would make (c)
true as a side effect, and nothing else here touches it.

---

### Q2 · The ruling that retires Needs attention exists in no file in this repository

**The signed rule, still CONFIRMED today:**

> `04-docs/05-modules/04-metering/02-business-rules.md:90`
> | `BR-MET-060` | Reads screen opens on **"Needs attention"** (Missing/Flagged/Disputed KPI chips + drill-in); full list one tab away | PO RD-12 | **CONFIRMED** | — |

**The ruling that reverses it,** quoted from the blueprint, p8:

> *"Need Attention — does not add any value."* The tab goes. That supersedes `BR-MET-060` …
> and retires `US-MET-019`.

**Grepped, this pass, across the decision log, the open-question register, the change-request
register and the module's own business rules:** `Need Attention`, `Needs attention`, `does not
add any value` — **zero hits outside `02-business-rules.md`'s statement of the rule being
reversed.** The decision log's 2026-09-12 and 2026-09-13 rows are all `CR-094` customers work.
The blueprint's own index says this of thirteen rulings including this one: *"Every August ruling
reached the repo. Not one from this session did … They cannot be grepped."*

**Side A — build it.** A PO ruling is a ruling however it arrives (law 13's last clause), it is
recorded verbatim with its date, and it names what it displaces, which is what the change process
step 2 asks of a reversal. Re-asking is the bug.

**Side B — do not build it from a PDF.** `BR-MET-060` is **CONFIRMED** in the module's business
rules and is quoted as live law in the product's own source (`ReadsListPage.tsx:24`). Hard-won
law 10 and the change process both say a reversal is written into the register **before** it is
built on. A lane that deletes a CONFIRMED rule's behaviour on the authority of a document on
another branch leaves the repo saying two things.

**This lane's reading, recorded rather than acted on:** the difference between the two sides is
**one commit of transcription, not a re-ask**. `B1–B3` are ready to build the moment the ruling
is written into `02-business-rules.md` (`BR-MET-060` → SUPERSEDED, dated, verbatim), the decision
log, and `US-MET-019`'s status — in one commit, per the fan-out rule. **What reaches the PO is
nothing; what reaches the coordinator is: do the transcription first.**

---

### Q3 · Two PO rulings, two days apart, disagree about whether a dead button is removed or kept

**This one does reach the PO.**

**Ruling A — in the repo, greppable, dated 2026-09-10, recorded 2026-09-13**
(`12-governance/02-decision-log.md`, the row headed *"FIVE PO RULINGS ON THE ACCOUNT SCREEN THAT
LIVED ONLY IN A PDF FOR THREE DAYS"*), PO verbatim:

> **(1)** *"keep all buttons on screen"* — no action is hidden by state;
> **(2)** *"keep all icon only disable them"* — the glyphs stay drawn and refuse with their
> reason rather than disappearing.

and the row's own gloss: *"law 2 warns that a control nothing feeds is dead UI, and these two say
the cure is **never to REMOVE the control** — it stays on screen, disabled, carrying its reason,
so a clerk learns what the product can do rather than meeting a different screen each time state
changes."*

**Ruling B — in the blueprint only, dated 2026-09-12** (entry 03's disposition table, p14):

> | Estimate button | **REMOVED** | **PO ruling, 2026-09-12** — approved as change 2.3. It is a
> permanent refusal rather than a state, and estimating stays reachable from two other places |

and its rail: *"It could never be enabled on this screen — estimation fills a* missing *reading
and this reading exists, so its reason was permanent rather than a state. A control that can
never become live is not a disabled control, it is a word in the wrong place."*

**As-built, walked:** `Estimate`, present, `disabled: true`, `title` = *"Estimation fills a
missing record for a meter, channel and date. This reading exists, so estimating here would
append a second one."* — i.e. **exactly what ruling A prescribes.**

**The collision is real and neither side is obviously wrong.** Ruling A is later-recorded but
earlier-made, and its decision-log row scopes it to *"the account screen"* while stating its
reasoning in general terms. Ruling B is later-made, specific to this control, and turns on a
distinction ruling A does not draw — between a refusal that is a **state** (re-offer it when the
state changes) and a refusal that is **permanent** (there is no state in which it becomes live).
Ruling B is also the only one of the two that cannot be found by grep.

**What this lane did not do:** choose. `B20` is withdrawn from the build list and sits here.
Estimating remains reachable from the Reads header (`Estimate a missing read`, live, walked) and
from a cycle's shortfall either way, so **nothing a clerk can do changes while this is open.**

**The question, in one sentence, with a figure:** *on the reading detail screen there is an
`Estimate` button that can never be pressed — it is greyed on every reading and always will be,
because estimating fills a reading that is missing and this one exists — so should it be taken
off the screen, as the Meter Reads drawing says, or stay greyed with its reason, as the account
screen's rule says?*

---

## 8 · WHAT I COULD NOT SEE, AND WHY

| Not seen | Why |
|---|---|
| Entry 03 in its **billed** state — the `Correct billed read` button, whether the rename fires, and the dispute dialog's 51-word billed refusal strip | **0 of 24 seeded readings carry `lifecycle: "billed"`** (measured over the whole list; every row is `committed`). `D2` and `B21` are read from source and from `api.py`'s route table, not from the screen |
| **Entry 06 in the browser, at all** | **0 of 24 seeded readings carry `disputed: true`**, so the header never offers `Clear the dispute`. Read from source; graded UNVERIFIED |
| The **`BILLED CORRECTIONS`** section on entry 03 | Conditional on `read.corrections.length > 0`; no correction is seeded |
| The **net-meter pair** panel | Conditional on a net meter. An `export` channel exists in the seed; I did not open one, so this is unmeasured rather than absent |
| The **column picker opened by clicking** | The picker button carries no accessible text, so my locator timed out. Its full contents were read from the rendered DOM instead — 16 rows, `Select · Meter · Read date · Cycle · Route · Service · Premise · Previous · Current · Usage · Source · Status · Channel · Days since prior · Batch · Reset table` |
| **What callout ⑧ `Plan` is for** | ⚠ **The document contradicts itself here.** The drawing puts `☐ ⑧ Plan` in the picker in accent, and the numbered callout list on p10 **runs 1–7 and stops** — there is no entry ⑧. Its own arithmetic block then reads `Remedy fields 19 = 19 − 0 removed + 0 new`, i.e. **no new field**. `B8` is written to the drawing per rule 41, and this contradiction is flagged rather than resolved |
| Whether the **`Read cycles`** tab is meant to replace `/reads/routes` and `/reads/cycles` or sit beside them | Callout ③ says *"replaces the two doorless screens"*; both are routed (`App.tsx:719–720`) and both are in `sidebarDestinations.ts`. **Entries 14/15 are another lane's scope** — `B4` records the tab's absence and nothing about the two screens' fate |

---

## 9 · METHOD NOTES

* Every drawing in this file was read **as an image**. The text layer was used only to find the
  page. On this document it returns `readstaball` for `/reads?tab=all`.
* **No `.tsx`, test, catalogue or register was edited.** No id was allocated — every gap above is
  described so the coordinator can allocate centrally.
* **Money check, per the lane brief.** Three gaps touch a figure and each was traced to the end
  before being classified: `B35` and `B38` change **display only** (`_parse_decimal` strips
  separators, so a grouped prefill posts identically); `B31` **renders a stored outcome** and
  compares nothing again. `Q1` is the only genuine money path in this scope and it is written as
  a question with both sides, deciding nothing. **No B4/B5 figure is touched by anything here.**
* **Every quantity named above carries its unit**, as the product serves it (hard rule 3).
* **Absences were verified before being stated** (`grep 'path(' 06-backend/apps/metering/api.py`
  for the routes; the live `GET /reads` payload for the row fields; `read_dict`'s own key list,
  parsed, for the 41).
