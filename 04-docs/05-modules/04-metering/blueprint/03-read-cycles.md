# § 04 · Read cycles — the drawing against the running product

**Scope.** Blueprint entries **14, 15, 20, 21, 16, 17, 18, 19** — PDF pages **39–60**,
read AS IMAGES at scale 2 per B14 rule 42. The entries are listed in the document's
own order, which is **not** page order: 20 and 21 sit between 15 and 16 because the
detail screens belong beside the lists they open from.

**Measured at** product version **`2.261.3`**, branch `claude/hi-0jmv62`, commit
`7b1dc74f`, on **2026-09-13** — **24 versions after the blueprint was read** (`2.237.10`,
2026-09-12). Every as-built sentence below was re-established this pass; none was
copied forward from the document.

**How.** Pages 39–61 rendered with `10-scripts/pdf/pdf_render.py` and opened as PNGs.
Code read in `07-frontend/src/features/metering/RoutesCyclesPage.tsx`,
`EstimateReadModal.tsx`, `ReadsListPage.tsx`, `07-frontend/src/components/AppShell.tsx`,
`07-frontend/src/api/endpoints.ts`, `06-backend/apps/metering/api.py`,
`selectors.py`, `services.py`, `models.py`. Walked in Chromium against the deployed
join (SPA `:8080`, API `:8011`, tenant `brazosbend`, signed in as Dana Whitfield)
**at 1280 AND 1440** — both widths produced identical structure, and no page in this
scope scrolls horizontally at either.

**This file measures and routes. It builds nothing and it allocates no id.**

---

## 1 · THE DOOR QUESTION — SETTLED, AND THE DOCUMENT IS RIGHT

The blueprint's second headline claim:

> *"Routes and Cycles have no door. Both are routed, built, tested and translated;
> the sidebar renders no submenu by two PO rulings, their route constants are imported
> by nothing, and no page links to either. They open only by typing the URL."*

**CONFIRMED, still true at `2.261.3`.** The equivalent claim in the Assets blueprint
turned out false; this one does not.

### What I clicked

Signed in, waited for `/dashboard` and 2.5 s, opened **`/brazosbend/reads`** and
enumerated **every `<a href>` the page renders**, at 1280 and again at 1440:

* **13 links.** Dashboard · Plans & Rates · Premises · Assets · Accounts · **Reads** ·
  Billing · Payments · Work · Finance · Runbooks · Reports · Settings.
* **No `/reads/routes`. No `/reads/cycles`. No `?tab=cycles`.** Not in the sidebar,
  not in the tab strip (`Needs attention | All reads`, two tabs), not in the header
  action row (`+ Add reading · Estimate a missing read · Route sheet PDF · ↑ Upload reads`),
  not anywhere in the document.
* Typed both URLs directly: **both open and render correctly**, zero page errors,
  six rows each.
* Also checked **Settings → Reference data → Routes & Cycles** (SET-05), the one other
  screen about the same objects: **no link to either ops address** from there either.

### Which of the two possibilities it is

The briefing asked whether the submenu *renders only in some state* or is *declared and
not rendered*. **It is declared and not rendered — deliberately, for every module, and
there is no state in which it appears.**

`AppShell.tsx` does declare them (lines 226–230):

```
children: [
  { path: "/reads",        labelKey: "shell.nav.reads.reads" },
  { path: "/reads/routes", labelKey: "shell.nav.reads.routes" },
  { path: "/reads/cycles", labelKey: "shell.nav.reads.cycles" },
],
```

But the nav renderer (lines ~747–770) emits **one `NavLink` per top-level item and then
a comment**. There is no submenu markup in the file at all. The comment says why, and it
is a standing ruling rather than an omission:

> *"PO rulings 2026-08-10 — Plans & Rates ("no sub menu required") and then Premises
> ("same is the case with premises UI; no Sub menu"), each with a prototype screenshot:
> the sidebar renders NO submenus. Every sub-destination is the page's own tab strip …
> `children` REMAINS in the config on purpose. US-SHL-002's breadcrumb resolves its
> second crumb from it."*

**The proof that it is not a state:** Premises declares two children and Payments three,
and neither renders a submenu either — I counted 13 links on every page I loaded.
`children` is consumed by exactly one function, `breadcrumbFor()` at line 504.

**And the two route constants really are dead.** `meteringShared.tsx:109-110` exports
`READS_ROUTES_ROUTE` and `READS_CYCLES_ROUTE`; a grep across `07-frontend/src` and
`08-qa` returns **only those two definition lines**. Nothing imports either.

The 14th link that appears *on* the ops pages is the breadcrumb — `Reads › Routes` —
which points **back** to Reads. A door out, never a door in.

> **This is hard-won law 2 in its dead-UI form, twice over:** a config child nothing
> renders, and two exported constants nothing imports. `tsc`, eslint and every suite
> pass over both, because each asks whether a declared path renders a real screen —
> never whether a user can get there.

### The ruling already closes it, and closes it differently

Page 40's accent card, **ruled 2026-09-12**, verbatim:

> **"Cycle and Route — we should say Read Cycles and within that we should show Routes
> and their completion."** And: **"we will need a list view of read cycles and we will
> need a detail view of read cycles."**
>
> *"Routes stops being a screen. It becomes a section of a cycle … **The two doorless
> addresses are closed by the same change that fixes what they were saying**."*

So the remedy for the door is **not** a submenu — it is a **`Read cycles` tab on the
Reads page** (`/:tenant/reads?tab=cycles`), with `/:tenant/reads/cycles` and
`/:tenant/reads/routes` kept and **redirected**, *"the way the retired drawer's `?read=`
links are. There are tickets with these URLs in them."*

**Walked:** `/brazosbend/reads?tab=cycles` today lands on **Needs attention** and the
parameter is ignored. The remedy address does not exist.

---

## 2 · DOCUMENT CLAIMS ALREADY OVERTAKEN

The staleness runs in our favour again. **Three as-built claims inside this section are
already wrong**, and all three make the work smaller.

| # | The document says | Today |
|---|---|---|
| 1 | Entry 15 — *"Table controls: Search · filter · columns · sort · server pager — **all four, where today there are none** and the pager runs in the browser over a fetch-everything read."* | **The SERVER HALF IS BUILT.** `GET /routes` and `GET /cycles` go through `_list_params` + `_page` and answer `{count, next, previous, results}`, honouring `q`, `sort`, `dir`, `page`, `per` and `f.*` (`api.py` `routes()` / `cycles()`, landed CR-029 RC-W3b, 2026-08-23). Only the **screen** does not use it. |
| 2 | Entry 16 — the `Route` column is counted as **NEW** (`Remedy fields 9 = 5 + 4 new (tick column, **Route**, Estimate these, Send someone out)`) | **ALREADY BUILT.** The chase panel renders **six** columns including Route (`RoutesCyclesPage.tsx:336`); confirmed on screen. The as-built field count is **6, not 5**, so the remedy is **+3, not +4**. |
| 3 | Entry 18 — *"the register list it offers is **the flat seven**, not that meter's missing set"*, and the field table names the constant `READ_CHANNELS` | **IT IS FIVE, AND IT IS A DIFFERENT CONSTANT.** The dialog uses `ESTIMATE_CHANNELS` = `total, peak, mid_peak, off_peak, demand`. `READ_CHANNELS` (seven) belongs to the upload wizard and the reads list and is not imported here. **And three of the five are dead — see §5, entry 18.** |

Two further document claims in this section were already marked fixed by the document
itself and are confirmed live: entry 17's cycle half (the `A route / A cycle` segment
exists and works) and entry 19's `?read=` forwarding (`ReadsListPage.tsx:695-702`).

**Not a document claim, but worth recording:** `/:tenant/reads/cycles/:id` and
`/:tenant/reads/routes/:id` — the two remedy addresses — already resolve to the honest
**"This screen is not built yet"** screen with the correct breadcrumb, not to a 404 or a
blank. A ticket pasted at either address lands somewhere that explains itself.

---

## 3 · THE ENTRIES, DRAWN

Quoted from the pictures. Strings are copied exactly.

### Entry 14 · Routes — p40 — **RETIRED BY RULING**

The heading is struck through. `~~/:tenant/reads/routes~~ — the address redirects; the
content moves into entry 20`.

> *"WAS: a top-level list of every route with its collection progress — and nothing in
> the product linked to it. Nine columns, no toolbar, client-side paging, a date column
> printing a clock a day early, and a Collected column counting readings beside a Meters
> column counting meters.*
> *NOW: RETIRED as a screen by PO ruling of 2026-09-12. Every column survives, inside the
> cycle it belongs to — see entry 20."*

**Not drawn.** Three dispositions given:

| | |
|---|---|
| Where its content went | *"All nine columns move into entry 20's **Routes** section, under the cycle whose window they are measured against. Cycle stops being a column there, because the cycle is the page."* |
| What is genuinely lost | *"**The all-routes view.** A supervisor who wants "every route in the utility, one list" no longer has one … Recorded as a cost of the ruling rather than argued against it; if it bites, the answer is a Routes tab, not the old orphan screen."* |
| The address | *"**Kept and redirected** to the Read cycles tab."* |

### Entry 15 · Read cycles — the list — p40–42

Address: **`/:tenant/reads?tab=cycles`** · was `~~/:tenant/reads/cycles~~`, which had no door.
The question: *"Which cycles can I bill on Friday, and which are short?"*

Drawn as a **tab of the Reads page**, not a page of its own. Header identical to entry 02:
title **Reads**, actions in this order — `+ Add reading` · `Estimate a missing read` ·
`Route sheet PDF` · **`↑ Upload reads`** (primary). Tab strip: `All reads` | **`Read cycles`**.

Toolbar, left to right: search box **`Search cycle or route…`** · an `All` chip ·
`+ Filter ▾`. Right: `↓ Download CSV` and a columns/density icon button.

**Table — NINE columns, in this order:**

`CYCLE ⇅` · `ROUTES` · `FREQUENCY` · `READ WINDOW ⇅` · `BILL DATE ⇅` · `METERS` ·
`REGISTERS COLLECTED` · `WINDOW` · `STATUS`

Row as drawn: `CY-001` · chips `RT-001` `RT-003` · `Monthly · day 1 · 3 days` ·
`09/01/2026 – 09/03/2026` · `11/05/2026 due 11/25` · `5` · `0 of 18 · 5 meters short` ·
pill `Closed 9 days ago` · pill `In progress`.

Footer: `Showing 1–6 of 6` · `Rows per page 50` · `Page 1 of 1` with first/prev/next/last.

The five numbered notes:

1. Read cycles tab · replaces both doorless addresses · **NEW**
2. Search · cycle code and route code · UI-RULES 12 · **NEW READ**
3. Meters · `cycle.expected` · **UNCHANGED** — *"and now the only meter count on the row"*
4. **Registers collected** · the chase read · `BR-MET-057` · **RELABELLED** from *Completeness*,
   *"because it counts registers and the column beside it counts meters"*
5. **Window** · derived from the window dates against the tenant's today · **NEW** —
   *"replaces "0 days left", which said that nine days after the window shut"*

**⚠ A stop-sign card on the same page, and it is a blocker on two of those five:**

> **"Two of these depend on a disagreement nobody has settled."** The **Window** pill and
> the **Registers collected** figure are both computed from the cycle's window — and **two
> derivations of "the current window" give different answers**. Measured on one day: the
> cycle row printed August while the completeness engine answered September. … **Build
> these two on the fork and you get a screen that disagrees with itself.** It is a filed
> backend disagreement, not a design question, and it needs settling before ⑤ and ④ are
> trustworthy. **Everything else on this drawing is safe to build now.**

**Spec table:** *Primary action* — *"None on the list. `BR-MET-011` puts every create, edit
and delete in Settings, and this file imports no mutation wrapper at all."* ·
*Write surfaces* — *"**Detail** the row opens entry 20. **Add / edit / update NOTHING**, by
rule."* · *States* — loading table skeleton; empty *"No cycles are configured yet."* **plus
`Add a cycle in Settings →`, which it lacks today**; failed reason + Retry; domain state
before the window opens.

### Entry 20 · A cycle — the detail — p42–48 — **A NEW SCREEN**

Address: **`/:tenant/reads/cycles/:cycleId`** · opened by a row on entry 15.
The question: *"CY-001 is short. Which routes, which meters, and what do I do about it
before Friday?"*

> *"It is the second half of the ruling — **"within that we should show Routes and their
> completion"**. Retiring entry 14 moved nine columns with nowhere to go; this is where
> they went. Everything drawn here is **served today** by an endpoint the product already
> answers … **No new endpoint is proposed.**"*

**Header** (identical on every tab): breadcrumb `Reads › Read cycles` · back link
`← Read cycles` · kicker `CYCLE · MONTHLY` · title **`CY-001`** (32px) · status pills
**with the identity, not in the action row** — `In progress` and `Window closed 9 days ago` ·
roll-up line `Read window 09/01 – 09/03/2026 · billed 11/05/2026, due 11/25 · 2 routes ·
5 meters · 0 of 18 registers` · actions right-aligned: `Reading sheet` · `Route sheet` ·
`…` · **`↑ Upload reads`** (primary, pre-scoped to this cycle).

**⚠ TAB COUNT — THE DOCUMENT CONTRADICTS ITSELF, AND THE DRAWINGS WIN.** The spec table
says *"**Four** — Overview · Routes 2 · Still to read 5 · History"*, and note 6 on p43 lists
the same four. **All five drawings show FIVE tabs** — `Overview | Routes 2 | Still to read 5 |
**All reads 13** | History` — and the document carries a full *"All reads — the tab"* section
(p46–47) with its own drawing and its own three notes. Per B14 rule 42 the image is the
specification: **build five.** (Recorded as a document defect in §7, not a PO question.)

`BR-SHL-011` makes the open tab URL state, so each tab is separately addressable.

**Overview tab** — a `Panel` (not a KPI band), then a two-column body:

* ⑦ **COLLECTION** — three figures that belong to one question:
  `REGISTERS COLLECTED` **0** of 18, sub-line ⑧ *"5 meters × their plan's registers"* ·
  `METERS SHORT` **5**, sub-line *"of 5"* · `WINDOW` **Closed**, sub-line *"9 days ago"*.
  Then ⑨ a named line: *"Short registers · **total** on 3 meters · **tou_mid** on MTR-0471 ·
  **demand** on MTR-0488"*.
* ⑩ **ROUTES** (left) — seven columns: `ROUTE` · `NAME` · `READER` · `METERS` · `REGISTERS` ·
  `LAST READ` · `STATUS`. Rows `RT-001 / North Elm / J. Alvarez / 3 / 0 of 11 / 08/01/2026 /
  In progress` and `RT-003 / Cypress Row / Unassigned / 2 / 0 of 7 / …`. Footer
  `Showing 1–2 of 2 · Rows 50 · 1/1`.
* ⑪ **SCHEDULE** (right) — `Frequency Monthly` · `Starts Day 1` · `Days to complete 3` ·
  `Next window 10/01 – 10/03`, then ⑫ `Manage in Settings →`.
* **BILLING** (right) — `Bill date 11/05/2026` · `Due date 11/25/2026` · `Accounts 5`, then
  one line: *"5 meters are short. Estimate or read them first."*

**Routes tab** — toolbar `Search route or reader…` · `All` · `+ Filter ▾` · `↓ Download CSV` ·
columns icon. Eight columns: `ROUTE ⇅` · `NAME` · `READER` · `PREMISES` · `METERS` ·
`REGISTERS COLLECTED` · `SHORT` · `LAST READ ⇅` · `STATUS`, plus row actions (upload for this
route · print its sheet · reassign). `REGISTERS COLLECTED` reads `0 of 11 · 0%`; `SHORT` is a
pill reading `3 meters`. One floor note, 8 words: *"Every figure is measured against this
cycle's window."*

> *"**the column that made it unreadable is gone**: there is no `Cycle` column, because the
> cycle is the page, and no bare `Collected` counting readings beside a `Meters` counting
> meters. Each row carries the two numbers that answer different questions — **how many
> registers arrived** and **how many meters are short**."*

**Still to read tab** — this is entry 16, drawn in place. Toolbar: `Search meter or address…`
then **register chips that count by what is missing**: `All 5` · `Total register (3)` ·
`On/off-peak (1)` · `Demand (1)` · `↓ Download CSV`. Below, the product's dark **bulk bar**
appears on selection: `2 selected` — `Estimate these` · `Send someone out` (disabled until
selection) · `Clear`.

Nine columns: tick · `METER` (a link) · `PREMISES` · `UNIT` · `REGISTERS STILL NEEDED`
(the missing one **in bold**) · `PLAN` · `ROUTE` · `DAYS LEFT` · `LAST ACTUAL`.
`DAYS LEFT` reads **−9**, negative once the window shuts. Server pager. Floor note:
*"MTR-0501 has no actual reading. It cannot be estimated."*

**All reads tab** — entry 02's reads table, pre-filtered by a removable `Cycle CY-001 ×`
chip. Eleven columns: tick · `METER ⇅` · `READ DATE ⇅` · `ROUTE` · `PREMISE` · `PREVIOUS` ·
`CURRENT` · `USAGE ⇅` · `REGISTER` · `SOURCE` · `STATUS ⇅`. Every quantity carries its unit
(`8,210 kWh`, `412 kW`, `4,110 kgal`). Floor note: *"Last window, 08/2026. This window has
no readings yet."* **No new endpoint** — `f.cycle` is one of the six filters `GET /reads`
already declares.

**History tab** — drawn with a warning `Panel` reading **`NOTHING SERVES THIS YET`**:
*"This tab needs one endpoint that does not exist. Everything else on this page is served
today."* Eight columns: `PERIOD ⇅` · `READ WINDOW` · `REGISTERS COLLECTED` · `METERS SHORT` ·
`ESTIMATED` · `BILL DATE` · `STATUS`. The `ESTIMATED` column is why the tab exists —
*"a cycle reading 100% on estimates is not the same as a cycle read by a person."*

**Four actions and only four**, plus one escape, drawn as a table:
`↑ Upload reads` (primary) · `Reading sheet` (secondary) · `Route sheet` (secondary) ·
`Estimate these` and `Send someone out` (on the shortfall) · `Manage in Settings →` (escape).

> **What is deliberately NOT here:** *"no **Close the window**, no **Reopen**, no **Bill this
> cycle**. The window is derived from dates and cannot be closed by hand; billing is the
> billing module's run and putting a trigger here would be a second way to start it."*

### Entry 21 · A route — the detail — p49–54 — **A NEW SCREEN**

Address: **`/:tenant/reads/routes/:routeId?window=2026-09`** · opened by a route row on entry 20.

> **PO ruling 2026-09-13**, verbatim: *"what if User click on Route link — we will have to
> give a details view of Route. this view should be similar to details view of Cycle."*
>
> *"**The one thing a cycle page never needs:** a route can be walked on **more than one
> cycle**, and this one is on two. *"0 of 11 collected"* has no denominator until a window
> is named, so the header carries the window this page is measured against — **PO ruling:
> option A, its own address with a selector**, defaulting to the cycle you arrived from."*

Header: breadcrumb `Reads › Read cycles › CY-001 › RT-001` · back `← CY-001` ·
kicker `ROUTE · NORTH ELM` · title `RT-001` · pills `In progress`, `Reader · J. Alvarez` ·
roll-up `3 stops · 3 meters · 0 of 11 registers · last read 08/01/2026` · then a labelled
control **`Measured against  CY-001 · 09/01 – 09/03/2026 ▾`**. Actions: `Route sheet` ·
`…` · `↑ Upload reads`.

**Five tabs:** `Overview` · `Stops 3` · `Still to read 3` · `All reads 8` · `History`.

* **Overview** — the same three-figure `COLLECTION` panel scoped to the route
  (`0 of 11` · `3` short · `Closed`), then **THE WALK** (`Stops 3` · `Meters 3` ·
  `Reader J. Alvarez` · `Excluded premises 1`) and **CYCLES** (`CY-001 Monthly`,
  `CY-007 Quarterly`) with the one-line reason the selector exists.
* **Stops** — `Search premises…` · `Route sheet` · `↓ Download CSV`. Six columns:
  `STOP` · `PREMISES` · `UNIT` · `METER` · `SERVICE` · `REGISTERS EXPECTED` · `LAST READ` ·
  `STATUS`. **One row per PREMISES, not per meter** (CR-029 D11). An excluded premises
  **keeps its row** and says why — `— · 17 Pecan Way · Excluded · vacant since 06/2026 ·
  Not walked`. Footer `Showing 1–3 of 3 stops · 1 excluded`. **Drawn read-only**, with a
  warning panel naming the open question: *"whether a clerk may reorder a walk from Reads,
  or only from Settings, **is not ruled**."*
* **Still to read** — the cycle's chase list narrowed to this route **and carrying the stop
  number**. Floor note: *"A demand register is never estimated. Send someone out."*
* **All reads** — the same table filtered by `Route RT-001 ×` (`f.route`, the sixth declared filter).
* **History** — **served, unlike the cycle's**: `GET /routes/{id}/read-windows`, *"served since
  CR-029 RC-W3b and wrapped as `getRouteReadWindows`. **It is called by nothing today.**"*
  Columns `WINDOW ⇅` · `CYCLE` · `REGISTERS COLLECTED` · `METERS SHORT` · `ESTIMATED` ·
  `READER` · `COMPLETED` · `STATUS`, showing **both** cycles in one list.

Screen health as drawn: **SERVED, every figure on all five tabs** — *"the only new screen in
this document with nothing unserved behind it, and one of its endpoints has been waiting
three weeks for a caller."*

### Entry 16 · Meters still to read — p54–56 — **a section, not a panel**

> *"was a panel behind a table cell on entry 15 — no address of its own; now the **Still to
> read** section of entry 20."* Drawn in place as entry 20's ⑥; not drawn twice.

Dispositions: the five as-built columns **UNCHANGED**; the panel **MOVED** out from behind a
table cell; the heading *"Meters still to read on CY-002"* **REMOVED** (*"the cycle is the
page"*); the 17-word standfirst **REMOVED** (*"B14 rule 33: rationale is zero words on
screen"*); `Close` **REMOVED** (*"it is a section, not an overlay"*); `Meter` **RELABELLED** to
a link (*"A list of meters you cannot open is a list you have to re-find"*).

> **"The pager is not a nicety here."** *"The chase list is **unpaginated and sorted in
> Python** (`completeness.py:894, :913`), and the only bound stated anywhere is a code
> comment: *"Bounded by the cycle's own membership (<3,000 connections)"*. **That ceiling was
> retired on 2026-09-06** — the ICP now reaches 40,000 accounts — so the comment is not a
> bound, it is a note about a world that no longer exists. `NFR-3` and `NFR-5` both apply."*

### Entry 17 · Route sheet — p56–57 — dialog → print tab

A dialog on entry 02; the sheet opens at `/api/{tenant}/{routes|cycles}/{id}/route-sheet`
in a new tab. The question: *"Print me the walk for tomorrow."*

Drawn: kicker `READS` · title **`Route sheet`** · a **segmented control** labelled
`Print the sheet for` with `A route` / `A cycle` · then a **searchable** picker `Route *`
showing `🔍 RT-04 · North Elm ▾` · help line **"Opens in a new tab. Print or save as PDF."** ·
footer `Cancel` then `Open the sheet` (primary).

> *"The scope is a **segmented choice rather than two buttons**, because it is one question
> with two answers — *what are you holding?* — and the picker below it changes with the
> answer. Choosing a scope clears the other one's selection, so the schema can never hold a
> route id and a cycle id at once."*

Health as drawn: **SERVED, two option lists unbounded** — `GET /routes` and `GET /cycles`
*"every page, fetched whole"*.

### Entry 18 · Estimate a missing read — p58–60 — dialog

> *"a dialog on entry 02 — it had its own route, `/reads/estimate`, and the PO took it
> away"* (PO on the live app at v2.61.1: *"this can be modal - instead of page"*).
> The question: *"The meter could not be read and the bill run is Friday. Put a lawful
> number in."*

Drawn: `Meter number *` (`MTR-0463`) · **`Register *`** — `🔍 Total register ▾` with the help
line **"This meter is short of one."** · `Read date *` (`08/31/2026`) with
*"The period comes from the last reading."* · then **the answer rendered as a child of the
form**: a bordered block reading **`Estimated 412 kWh`** over *"Trailing 3-month daily average ·
estimate 1 of 2 · no register value"*. Footer `Close` then `Estimate` (primary).

> *"**Two changes.** The 25-word lede is gone — rule 33 caps rationale at zero on screen …
> And the **Register list offers this meter's MISSING set**, not the flat seven: as built it
> lists every register in the product, including ones the meter does not have."*

And an accent card on the bulk question:

> *"**Bulk:** `POST /reads/bulk-estimate` **exists and works** (`api.py:2137 →
> services.bulk_estimate_reads:9840`) … **Nothing in the front end calls it.** This is the
> module's third *served-with-no-caller* … **That surface is entry 20.** … **put the bulk
> control on entry 20 (drawn), and default this dialog's register list to that meter's
> missing set. Neither needs a new endpoint.**"*

### Entry 19 · The retired drawer address — p60–61 — an address, not a screen

`/:tenant/reads?read=<id>` → forwards to entry 03. *"Not a screen — an address. It is listed
as its own entry so that nobody later finds a URL nothing in this document describes."*
`ReadsListPage.tsx:697-702` forwards with `navigate(…, {replace: true})`.

---

## 4 · WHAT IS BUILT TODAY

Established this pass — code read, then walked at 1280 and 1440.

### The two ops pages

Both live at their own addresses, both render, **neither has a door** (§1).

| | `/:tenant/reads/routes` (`RoutesOpsPage`) | `/:tenant/reads/cycles` (`CyclesOpsPage`) |
|---|---|---|
| Title / sub | `Routes` · *"Collection progress per route for the current read window."* | `Cycles` · *"Read window, bill date and expected-versus-collected for each billing cycle."* |
| Columns | **9**: Route · Type · Service(s) · Assigned to · Cycle · Meters · Collected · Last completion · Status | **10**: Cycle · Routes · Frequency · Start day · Days to complete · Read window · Bill date · Meters · Completeness · Status |
| Rows seeded | 6 | 6 |
| Actions | `Manage in Settings →` + a CSV export button | same, plus `Chase 5 meters` inside the Completeness cell |
| Search / filter / columns / sort | **none of the four** | **none of the four** |
| Pager | present, **client-side** (`ListPager` + `pageSlice`) | same |
| Floor note | *"Completeness and progress derive from committed reads — nothing on this page is a stored counter, and nothing on it can be edited."* (22 words) | identical string |
| Page errors | none | none |
| h1 size | 32px ✔ B14 rule 40 | 32px ✔ |

CY-001's Completeness cell reads, on one line: **`0 of 18  0%  0 days left  Chase 5 meters`**,
with `METERS 5` in the column beside it. Both halves of the document's complaint reproduce
exactly: **18 has no stated basis on screen**, and **`0 days left` prints ten days after the
window shut** (window `09/01 – 09/03/2026`, measured `2026-09-13`).

### The data path, precisely

* **The server paginates.** `routes()` and `cycles()` call `selectors.routes_page` /
  `cycles_page` through `_list_params(...)` and return `_page(...)` — the
  `{count, next, previous, results}` envelope.
* **The screen throws the pagination away.** `RoutesCyclesPage.tsx` calls `getRoutes(client)`
  / `getCycles(client)`, which are `listAll()` — a loop that **fetches every page and
  concatenates them** (`endpoints.ts:2163-2174`) — and then windows the result in the browser.
* **The paged wrappers already exist and are already used elsewhere.** `getRoutesPage` and
  `getCyclesPage` (`endpoints.ts:2264-2276`) are called by
  `SettingsRoutesCyclesTab.tsx:616,621`. SET-05 has a real toolbar; the ops tabs do not.
* **Sorts served:** routes — `code, name, route_type, area_code, cycle_code, status`
  (+ `members`, `meters` sorted post-derivation). Cycles — `code, name, frequency,
  start_day, days_to_complete, lifecycle_status` (+ `accounts`).
* **Filters served:** routes — `cycle, type, status, service, area`. Cycles — `status,
  frequency` only.
* **Search served:** `q` matches `code` **or** `name`, minimum two characters, on both.

### The chase panel (entry 16), as built

Opens from `Chase 5 meters` on the CY-001 row. Six columns:
`Unit | Premises | Meter | Route | Registers still needed | Days left`. Five rows.
Heading *"Meters still to read on CY-001"* with a `Close` button, and a hint
*"Each one is short of a register its plan needs. Read it, or estimate it before the bill
run."* Missing registers are **named, not counted** (`Total register · On-peak · Mid-peak ·
Off-peak`) — which the drawing keeps. `Days left` prints **0** on every row. No tick column,
no bulk bar, no pager, and the meter is **text, not a link**.

### Entry 17 as built

`Route sheet PDF` on the Reads header opens `RouteSheetModal`. Confirmed on screen:
kicker `READS` · title `Route sheet` · segmented `Print the sheet for` → `A route` / `A cycle`
(values `routes` / `cycles`) · a plain `<select>` with `Choose a route…` and all six seeded
routes · help *"Opens print-ready in a new tab; your browser's Print / Save as PDF makes the
PDF."* · footer `Cancel`, `Open the sheet`. The option lists come from
`ReadsListPage.tsx:497,503` — `getRoutes` / `getCycles`, i.e. `listAll`, **every route and
every cycle in the tenant, fetched whole**.

### Entry 18 as built

`Estimate a missing read` opens `EstimateReadModal`. Confirmed on screen: a **28-word lede**
*"When a meter could not be read, this works out the consumption from that meter's own recent
actual readings. It never guesses a rate and it never rounds."* · `Meter number *` ·
**`Channel *`** (a plain select) · `Date of the missing reading *` · a **26-word** note
*"The length of the period is worked out from this meter's last actual reading. You do not
enter it, so the calculation cannot be nudged."* · footer `Cancel`, `Work out the estimate`.

The Channel select offers exactly five options:
**`Total consumption` · `Peak` · `Mid-peak` · `Off-peak` · `Demand (peak kW)`**.

---

## 5 · THE DIFFERENCE, BOTH DIRECTIONS

### Entry 14 · Routes — the three biggest

| | Gap | Direction | Route |
|---|---|---|---|
| 14-a | **The screen still exists and is still reachable by URL.** The ruling retires it and redirects the address to the Read cycles tab. Six seeded routes render at `/brazosbend/reads/routes` today. | built, no longer drawn | **BUILD** — the redirect, once entry 15's tab exists. Do not delete the address: *"There are tickets with these URLs in them."* |
| 14-b | **The all-routes view disappears with it.** No screen anywhere then lists every route in the utility in one table. | drawn absence | **BUILD** — record the loss in the decision log when the redirect lands. The document already rules the remedy if it bites: *"a Routes tab, not the old orphan screen."* |
| 14-c | `Collected` counts **readings** and sits beside `Meters`, which counts **meters** — the unreadable pair the ruling names. Live: `RT-001 … Meters 3 · Collected 8`. | built, wrong | **BUILD** — dies with the screen; it is entry 20's Routes tab that fixes it. |

### Entry 15 · Read cycles — the three biggest

| | Gap | Direction | Route |
|---|---|---|---|
| 15-a | **The tab does not exist.** `/:tenant/reads?tab=cycles` lands on Needs attention and ignores the parameter; the list lives at a doorless page instead. This is the door fix and the ruling in one. | drawn, not built | **BUILD** |
| 15-b | **The pager is client-side over a fetch-everything read, and the server pager it needs is already there.** `getRoutes`/`getCycles` → `listAll` walks every page. `NFR-3` and `NFR-5`. The fix is to call `getRoutesPage`/`getCyclesPage`, which exist. | drawn, not built | **BUILD** — smaller than the document says (§2 #1) |
| 15-c | **Ten columns, not nine, and two of them say the wrong thing.** `Start day` + `Days to complete` should fold into `Frequency` (*"Monthly · day 1 · 3 days"*); `Completeness` should be `Registers collected`; `0 days left` should be a `Window` pill that can say `Closed 9 days ago`. Live it prints `0 days left` ten days after close. | built, wrong | **BUILD**, but ⑤ and ④ are **BLOCKED** on the window fork — see Q4 |

Also, smaller: no toolbar at all (drawn: search on cycle **and route** code, `All` chip,
`+ Filter ▾`, columns button); `⇅` on three columns, of which **only `CYCLE` is served** —
`CYCLE_SORTS` has no `read_window` or `bill_date` key; the drawn search matches **route**
code, which `cycles_queryset` does not (`code`/`name` of the cycle only); the empty state
lacks `Add a cycle in Settings →`; and the 22-word floor note is **rationale on screen**,
which B14 rule 33 caps at zero (the drawing replaces it with an 8-word fact).

### Entry 20 · A cycle — the detail — the three biggest

| | Gap | Direction | Route |
|---|---|---|---|
| 20-a | **The whole screen is absent.** `/brazosbend/reads/cycles/<id>` renders *"This screen is not built yet."* Five tabs, four panels and two tables. | drawn, not built | **BUILD** |
| 20-b | **`Estimate these` and `Send someone out` are drawn on the shortfall table, and `POST /reads/bulk-estimate` has been served with no caller since CR-038.** This is the delivery of a deferral the code itself wrote down. | drawn, not built | **BUILD** — but see **Q1** (BR-MET-011) and **Q2** (module boundary) first |
| 20-c | **History is the one tab nothing serves.** Drawn with an explicit `NOTHING SERVES THIS YET` panel so it can be dropped from wave one without moving anything. | drawn, not served | **BUILD, last** — or drop it and keep the four-tab shape; the document engineers exactly that choice |

Also: the tab strip is **five, not four** (the document's own prose says four while all five
of its drawings say five — see §7); the drawn header is the shared `PageHeader` with pills
beside the identity (DEF-966) and a 32px title; `Manage in Settings →` moves into the
Schedule panel; ⑧ and ⑨ (the denominator explained, and short registers named by channel)
are both **NEW READ** and are the reason the screen is worth having.

### Entry 21 · A route — the detail — the three biggest

| | Gap | Direction | Route |
|---|---|---|---|
| 21-a | **The whole screen is absent.** `/brazosbend/reads/routes/<id>` renders *"This screen is not built yet."* | drawn, not built | **BUILD** |
| 21-b | **`GET /routes/{id}/read-windows` is served, wrapped as `getRouteReadWindows`, and called by nothing** — three weeks now. It is the History tab, and it is the one History in this section that already has its endpoint. | built, not wired | **BUILD** — hard-won law 2 |
| 21-c | **The window selector is the whole reason the screen has its own address.** A route can be walked on two cycles, so `0 of 11` means nothing until a window is named. PO ruled **option A** on 2026-09-13 — *"its own address with a selector"*, `?window=2026-09`, defaulting to the cycle you arrived from. | drawn, not built | **BUILD** — and **WRITE THE RULING DOWN FIRST** (§7) |

Also: the Stops table is **one row per premises, not per meter** (CR-029 D11) and keeps
excluded premises with their reason — the drawing is explicit that *"a stop that vanishes
from a walk is a stop a reader will look for."* The walk order is drawn **read-only** and
the drawing itself names the unruled question (see Q3).

### Entry 16 · Meters still to read — the three biggest

| | Gap | Direction | Route |
|---|---|---|---|
| 16-a | **The chase list is unpaginated and sorted in Python** (`completeness.py:894, :913`), and its only stated bound is a code comment naming the **retired** `<3,000 connections` ceiling. `NFR-3` + `NFR-5`, and the comment is now false as well as insufficient. | built, wrong | **BUILD** (pager) **+ DEFECT** (the comment states a bound that was retired 2026-09-06) |
| 16-b | **No tick column and no bulk bar**, so the only place in the product where the derived pending rows are selectable does not exist — which is exactly where `POST /reads/bulk-estimate` was deferred to. | drawn, not built | **BUILD** (with 20-b) |
| 16-c | **`Days left` prints `0` after the window shuts**, on every row, instead of a negative. Same fault as entry 15's `0 days left`. | built, wrong | **DEFECT** |

Smaller, and one of them is already fixed: the `Route` column is **already built** (§2 #2);
`Meter` is text rather than a link to the asset; the `PLAN` and `LAST ACTUAL` columns are
absent; the drawn column order is `Meter · Premises · Unit`, live it is `Unit · Premises ·
Meter`; the heading and `Close` should go when it becomes a section; and the 19-word,
two-sentence hint is an **instruction over rule 33's six-words-per-sentence cap**.

### Entry 17 · Route sheet — the three biggest

This is the closest match in the section. Nothing is missing structurally.

| | Gap | Direction | Route |
|---|---|---|---|
| 17-a | **Both option lists are unbounded** — `listAll` over `GET /routes` and `GET /cycles`, every page fetched whole, on every open of Reads. At the top of the ICP that is a select with thousands of options. | built, wrong | **BUILD** — a searchable/typeahead picker, which is what the drawing shows (`🔍 RT-04 · North Elm ▾`) |
| 17-b | **The help line is one 16-word sentence** — *"Opens print-ready in a new tab; your browser's Print / Save as PDF makes the PDF."* B14 rule 33 caps an instruction at **six words per sentence**, and *"two sentences of six beat one sentence of twelve."* The drawing shows the compliant form: *"Opens in a new tab. Print or save as PDF."* | built, wrong | **DEFECT** |
| 17-c | The picker is a plain `<select>`; the drawing shows a **searchable** field. Same root as 17-a. | built, wrong | **BUILD** (with 17-a) |

### Entry 18 · Estimate a missing read — the three biggest

> ⚠ **THIS ENTRY TOUCHES MONEY.** An estimate becomes a `meter_reads` row and a bill line.
> Nothing below changes a figure, a rounding or a unit, and **no B4/B5 figure is involved** —
> but step 2 must not treat this as an ordinary screen fix.

| | Gap | Direction | Route |
|---|---|---|---|
| **18-a** | **THREE OF THE FIVE REGISTERS THE DIALOG OFFERS ARE REFUSED BY THE SERVER BY NAME. A TOU METER CANNOT BE ESTIMATED FROM THIS DIALOG AT ALL.** See below — proved, not inferred. | built, broken | **DEFECT — highest in this section** |
| 18-b | **The register list is not this meter's missing set.** It is a hardcoded five, so a clerk picks from registers the meter does not have. The drawing's help line — *"This meter is short of one."* — is the whole point. | drawn, not built | **BUILD** (`MR-42`) |
| 18-c | **A 28-word lede and a 26-word note, both pure rationale.** B14 rule 33: *"RATIONALE — why the product works this way, why a control is absent — is ZERO WORDS ON SCREEN."* The drawing keeps **one** sentence, on the absent `days` input, and rewrites it for the clerk. | built, wrong | **BUILD** (copy) |

Also: the field is labelled **`Channel`**; the drawing and `BR-MET-057`'s vocabulary say
**`Register`** — and every other screen in this section says *register* (`Registers still
needed`, `Registers collected`, `Registers expected`). And the estimate answer is drawn as a
**child of the form**, read over the inputs that produced it, with its unit
(`Estimated 412 kWh`) — which the live component already does correctly (`EstimateFigure`
refuses to render a figure with no unit, per CLAUDE.md rule 3).

#### 18-a in full, because it is the finding of this pass

`EstimateReadModal.tsx:135-142`:

```
/**
 * BR-MET-059's channel vocabulary, as the SERVER defines it
 * (`apps/metering/models.CHANNELS`). ...
 */
export const ESTIMATE_CHANNELS = ["total", "peak", "mid_peak", "off_peak", "demand"] as const;
```

**The server's vocabulary is not that.** `06-backend/apps/metering/models.py:1220`:

```
CHANNELS: tuple[str, ...] = ("total", "tou_on", "tou_mid", "tou_off", "export", "demand", "generation")
```

`services.estimate_missing_read` refuses anything outside it, before any row is written:

```
channel = _text(data.get("channel"), 40) or models.CHANNEL_TOTAL
if channel not in models.CHANNELS:
    fe.append(_field_error("channel", errors.VAL_FORMAT, "metering.read.channel_unknown"))
```

**Proved on the running stack, with a meter number that cannot exist so that
`_refuse_fields` raises before anything could be created — nothing was written:**

| channel posted | result |
|---|---|
| `total` | accepted by the channel check |
| `peak` | **`VAL-002 · metering.read.channel_unknown`** |
| `mid_peak` | **`VAL-002 · metering.read.channel_unknown`** |
| `off_peak` | **`VAL-002 · metering.read.channel_unknown`** |
| `demand` | accepted by the channel check (then refused by `BR-MET-062`, by design) |
| `tou_on` | accepted by the channel check — **and the dialog does not offer it** |

So of the five registers a clerk can pick, **exactly one — `Total consumption` — can produce
an estimate.** `Demand` is offered deliberately so its refusal can explain itself
(`BR-MET-062`). The other three are dead, and they are precisely the TOU windows a TOU meter
is most often short of — which is the case the drawing puts on screen twice
(`tou_mid on MTR-0471`, and `MTR-0471 · 1408 Elm · On-peak, **Mid-peak**, Off-peak`).

**Why nothing caught it:** the docstring asserts the guarantee it breaks — hard-won law 1 —
and the three wrong words are in all eleven locale catalogues
(`metering.estimate.channelOption.peak / mid_peak / off_peak`), so the strings resolve, the
select renders, `tsc` passes and no test posts a TOU channel through this dialog. The refusal
even has a catalogue entry (*"«{{value}}» is not a register on this meter."*), so the clerk
gets a sentence — a true one, about a value the product itself put in the list.

`escape_reason` for the register row: *no check anywhere compares a front-end enum against
the server enum it claims to copy; the docstring asserting the copy is the only statement of
it, and it is wrong.*

### Entry 19 · The retired drawer address

**No gaps.** `/brazosbend/reads?read=<id>` forwards with `{replace: true}`
(`ReadsListPage.tsx:697-702`). Matches the drawing exactly.

---

## 6 · GAPS BY KIND

Counted from §5. Items that dissolve into a larger one are not double-counted.

| Kind | Count | The big ones |
|---|---|---|
| **BUILD** | **17** | Entry 20 (whole screen) · entry 21 (whole screen) · entry 15's tab · the server pager on three lists · the bulk bar · the redirect from entry 14 |
| **DEFECT** | **6** | **18-a (the three dead registers — money path)** · `days left` printing 0 after close, twice · two rule-33 copy breaches (17-b, 16-c's hint) · the retired-ceiling comment in `completeness.py` |
| **QUESTION** | **4** | Q1–Q4 below |
| **DOCUMENT DEFECT** | **4** | §2's three overtaken claims + the four-vs-five tab count |

Of the **19 drawings** in pages 39–60, **two screens (entries 20 and 21, thirteen drawings
between them) do not exist at all** and open onto *"This screen is not built yet."*
Two entries (17, 19) match. Three (14, 15, 16) exist and are wrong in the specific ways the
ruling names. One (18) is broken in a way the blueprint did not find.

---

## 7 · QUESTIONS — BOTH SIDES QUOTED, NOTHING DECIDED

Per B14 rule 41, the only thing that reaches the PO is **a drawing that contradicts a signed
rule**. Four qualify. Each is written with both sides and **no recommendation**.

### Q1 · Entry 20 puts two write actions on a screen a signed rule calls read-only

**The signed rule** — `BR-MET-011`, CONFIRMED (PO closure batch, 2026-08-08), verbatim from
`04-docs/05-modules/04-metering/02-business-rules.md`:

> *"S26/S27 are read-only operational views; **all CRUD in Settings**; progress derives from
> committed reads, never stored counters"*

`RoutesCyclesPage.tsx` enforces it by construction and says so: *"this file imports no
mutation wrapper at all. There is no create, edit, deactivate or delete on the page, not
disabled — ABSENT."*

**The drawing** puts `Estimate these` and `Send someone out` on entry 20's Still-to-read
table, and answers the objection itself:

> *"Every create, edit and delete of a cycle lives in Settings (`BR-MET-011`). That is not a
> gap to be filled here: a cycle's frequency, its start day and its window length are
> configuration, and putting an edit on this page would put the same field in two places.
> **So this screen acts on the reading work, never on the cycle's definition.**"*

**The gap between them:** the rule as written says *all* CRUD, not *all cycle CRUD*. The
drawing narrows it to the cycle's **definition** and leaves the **reading work** writable.
That narrowing is stated by the document, not by the PO.

### Q2 · `Send someone out` is a Reads screen writing into Work

**The signed rule** — CLAUDE.md, module map: *"Cross-module writes are forbidden; cross-module
FKs are the reviewed interface set (B2 §2)."* Work *"OWNS crews, technicians, … work orders …
and writes none of them [others]. **G78 fails a foreign write from its first commit.**"*

**The drawing**, which flags it in red type itself:

> *"**Send someone out** · On the shortfall · Raises a visit for the ticked meters · The
> **work** module — **and this is the one action that crosses a module boundary, so it is
> drawn and flagged, not assumed**."*

**The gap:** the drawing knows it is asking for a cross-module write and declines to assume
the answer. Whether Reads raises the visit through a Work seam, hands off to Work's own
screen, or the control does not ship in wave one is not ruled.

### Q3 · Who may reorder a walk

**The signed position** — `BR-MET-011` again (route configuration is Settings'), and
`SET-06D` numbers the stops there.

**The drawing** (entry 21, Stops tab), in a warning panel on the screen itself:

> *"The walk order is stored and printed on the route sheet. `PUT /routes/{id}/premises-order`
> is served and writes it. **Whether a clerk may reorder a walk from Reads, or only from
> Settings, is not ruled** — `BR-MET-011` puts route configuration in Settings, and `SET-06D`
> numbers these stops there. **Drawn read-only until somebody rules.** `Manage in Settings →`"*

**The gap:** the endpoint exists and writes; the drawing shows the table read-only and names
the absence rather than filling it. This is the drawing asking, not contradicting — but it is
the PO's to answer and it will block the Stops tab's write half.

### Q4 · The window fork — a **blocker**, not a preference

**The drawing's own stop-sign card** (entry 15, p41):

> *"The **Window** pill and the **Registers collected** figure are both computed from the
> cycle's window — and **two derivations of "the current window" give different answers**.
> Measured on one day: the cycle row printed August while the completeness engine answered
> September. The screen works around it today by passing the row's own window into the chase
> call, so both halves of one line describe one period.*
>
> *Build these two on the fork and you get **a screen that disagrees with itself**. It is a
> **filed backend disagreement**, not a design question, and it needs settling before ⑤ and ④
> are trustworthy. Everything else on this drawing is safe to build now."*

**⚠ I could not find the filed row, and I am stating that rather than assuming it exists.**
Searched `12-governance/10-defect-log.csv` for `two derivations`, `current window`,
`window disagree`, and every `chase`/`completeness` row; searched
`12-governance/01-open-questions.md` for `window` narrowed to cycle/completeness. The only
"two derivations" row is **`DEF-139`**, which is a different one — the ledger's balance
against payments' bill-based balance. **Step 2 must locate or file it before building entry
15's ④ and ⑤**; a blocker nobody can name is a blocker nobody will honour.

---

## 8 · WHAT SHOULD BE FILED — no ids allocated here

Use `10-scripts/file_defect.py … --id-module MET` (or `GOV` for the document rows) and
`allocate.py … --verify` at push time. **Do not take a number by hand.**

**Defects (6)**
1. The Estimate dialog offers three registers the server refuses by name; a TOU meter cannot
   be estimated. Money path. Proof in §5, 18-a. **High.**
2. `Days left` / `0 days left` prints zero after the window has closed — entry 15's
   Completeness cell and entry 16's chase table, one fault in two places.
3. `metering.reads.routeSheet.help` is a 16-word single sentence; B14 rule 33 caps an
   instruction at six words per sentence.
4. `metering.cycles.chase.hint` is a 19-word, two-sentence instruction over the same cap.
5. `completeness.py`'s bound comment states the `<3,000 connections` ceiling retired on
   2026-09-06, and the chase list is unpaginated and sorted in Python — `NFR-3`, `NFR-5`.
6. `metering.ops.notCollectedWhy` still says *"The reads module is not wired yet"*. Reads is
   wired and the ops page shows real collected counts. **I could not make this string render
   with the seeded data, so whether it is reachable is unverified** — file it as copy that
   states something false, and let step 2 decide whether the path is dead as well.

**Document defects (4)** — against this blueprint, which is 24 versions stale
1. Entry 15's *"today there are none"* on table controls: the server half is built.
2. Entry 16's `Route` column counted as NEW: already built; as-built is 6 fields, not 5.
3. Entry 18's *"the flat seven"* and the constant it names: it is `ESTIMATE_CHANNELS`, five.
4. Entry 20's *"Four"* tabs against five in all five of its own drawings.

**Open questions (4)** — Q1–Q4 of §7. Q4 is a **blocker** on two fields.

**Write-backs owed before any of this is built (step W).** The index warns that thirteen
rulings live in the blueprint and nowhere else. **Three of them are in this section**, and
none is greppable today:

* **2026-09-12** — *"Cycle and Route — we should say Read Cycles and within that we should
  show Routes and their completion"* / *"we will need a list view of read cycles and we will
  need a detail view of read cycles."* This **retires entry 14 as a screen** and needs a
  supersedes stamp against whatever `BR-MET-` rule names S26 as a screen.
* **2026-09-13** — *"what if User click on Route link — we will have to give a details view of
  Route. this view should be similar to details view of Cycle."*
* **2026-09-13** — the window selector: **option A**, its own address with a selector,
  defaulting to the cycle you arrived from.

Each belongs in `12-governance/02-decision-log.md` verbatim with its date, and in the
module's `02-business-rules.md`. A ruling that exists in one PDF on the default branch is
one deleted file away from never having happened.

---

## 9 · WHAT I COULD NOT SEE, AND WHY

Stated so that a zero here is not mistaken for a pass.

1. **Paging beyond page one.** The tenant seeds **6 routes and 6 cycles**, so the pager
   rendered `Page 1 of 1` with both arrows disabled. The tables were **populated, not empty**
   — the columns and rows below are real matches, not vacuous ones — but **I did not exercise
   a second page on any list in this section**, and I did not seed one. The `NFR-3` findings
   are from reading `listAll`, `routes_page` and `cycles_page`, not from watching a pager break.
2. **Entry 20 and entry 21 could not be walked**, because they do not exist. Everything said
   about them is read from the drawing and from the endpoints behind it.
3. **Whether `cycles_page` scales.** It builds `rows = list(qs)` and derives **every** row
   before `_page` slices — so the wire is paged and the query is not. I did not measure it and
   make no claim about what it costs at 40,000.
4. **Dialog fit.** My measurement caught `.modal-overlay` rather than the card, so the height
   I recorded (900) says nothing. If fit matters, use
   `10-scripts/render-checks/account-dialog-fit.mjs`, which measures the card.
5. **The printed sheet itself.** Entry 17 opens `/api/{tenant}/{routes|cycles}/{id}/route-sheet`
   in a new tab; I opened the **dialog** and did not open the sheet.
6. **The refusal a clerk actually sees for 18-a.** I proved the server refusal against a
   meter that does not exist, so both a meter error and the channel error came back. I did
   **not** submit the dialog against a real TOU meter, because that would write. What a clerk
   sees on the real path is inferred from the catalogue entry, not observed.
7. **Q4's filed row.** Searched and not found (§7). An absence I could not prove, only fail
   to find.

---

## 10 · HOW TO RE-RUN THIS

```bash
# the drawing, as images — the PDF is on the DEFAULT branch
git show "origin/claude/confirm-understanding-3ktufc:05-prototype/03 SMARTBillHub — Meter Reads blueprint.pdf" > /tmp/reads.pdf
mkdir -p /tmp/readsC
python3 10-scripts/pdf/pdf_render.py /tmp/reads.pdf /tmp/readsC 2 39,40,41,42,43,44,45,46,47,48,49,50,51,52,53,54,55,56,57,58,59,60
# then open each PNG with the Read tool. Scale 4 for the dense cycle tables.

# the product — the deployed join, not the vite dev server
cd 07-frontend && npx vite build
API_PROXY_TARGET=http://127.0.0.1:8011 PORT=8080 node server.mjs &
# sign in, wait for /dashboard then ~2.5s, then walk
#   /brazosbend/reads · /reads/routes · /reads/cycles · /reads?tab=cycles
#   /reads/cycles/<id> · /reads/routes/<id> · settings/reference-data/routes-cycles
# at 1280 AND 1440. Copy the createRequire(...)+resolveChromium() block from
# 10-scripts/render-checks/account-dialog-fit.mjs; do NOT import "playwright".
```

The door check is one line of page script and it is the one worth keeping:

```js
[...document.querySelectorAll('a[href]')].map(a => a.getAttribute('href'))
  .filter(h => h.includes('/reads/routes') || h.includes('/reads/cycles'))
```

Run it on `/:tenant/reads`. **It returns `[]` today.** When it stops returning `[]`, the
door exists — and that is the assertion that should land in the same commit as entry 15's
tab, per hard-won law 2's second half: *when you write a hold, write the test that fires
when the hold expires.*
