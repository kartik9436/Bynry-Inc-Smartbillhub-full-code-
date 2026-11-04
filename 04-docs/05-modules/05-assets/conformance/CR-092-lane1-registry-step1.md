# CR-092-BRC01 · step 1 · lane 1 — THE ASSETS REGISTRY, READ AGAINST ITS BLUEPRINT

**One address, `/:tenant/assets`. Six tabs and one dialog.** Blueprint screens
**01 Meters · 02 Sub-meters · 03 Behind the meter · 04 Inventory ·
05/05a/05b/05c Lifecycle · 06 Map**, plus screen **07**, the bulk-assign dialog.

> **THIS FILE IDENTIFIES AND FIXES NOTHING** (CR-092 §6, PO ruling 2026-09-10).
> No component, catalogue, route, stylesheet or test was changed by this lane.
> The one-word fixes are written down here as words. What it produced: this
> document and **twelve rows, `DEF-MET-4953` … `DEF-MET-4964`**.

**Read at:** `0a1a677d9`, the tip of `claude/hi-0jmv62`, 2026-09-11.
**Source document:** artifact *The Assets menu, screen by screen*, 4,414 lines,
read at `2.234.17` / `79c659d7d`.

---

## 0 · HOW THIS WAS MEASURED, AND WHAT THAT BUYS

The blueprint's baseline was already proved current (CR-092 §3: seven asset
files byte-identical between `79c659d7d` and this tip). This lane did not
re-derive it. It did two things instead: **re-read every file it was about to
write a finding about**, and **booted the product and measured**.

**The stack.** No app was running in this container and the port-8401 stack
named in the dispatch was gone with the restart, so one was booted the way
`10-scripts/11-smoke-stack.sh` prescribes, on private ports: Django on
`127.0.0.1:8511` against the existing Postgres, `vite build` then `server.mjs`
on `8512` with the `/api` pass-through. **Nothing was seeded, migrated or
written** — every navigation in the walk is a GET and no control that writes was
clicked. Measurements at **1440** and **1280**; Chromium from `/opt/pw-browsers`.

⚠ **THE TENANT IS SMALL AND THAT CHANGES WHAT SOME NUMBERS MEAN.** Brazos Bend
here holds **11 assets — 8 meters, 1 sub-meter, 2 devices, 0 geocoded premises**,
against the blueprint's **126 assets / 109 meters / 3 geocoded**. Where that
matters it is said at the finding. It works *for* two findings: an 8-row tenant
fits one page, so the KPI strip renders figures on load and the dash could be
provoked by a filter alone, which is the sharper half of the defect.

**What could not be checked, with its number, is in §6.** A declared blind spot
with no number attached is indistinguishable from an empty one.

---

## 1 · THE VERDICT, ONE LINE EACH

| spec / rule | blueprint says | this lane | row |
|---|---|---|---|
| `AST-B-01` KPI figures | defect, screens 01·02·03·04 | **CONFIRMED, screens 01 and 03 ONLY** | `DEF-MET-4953` |
| `AST-B-20` Download saves a 404 | defect | **CONFIRMED from source; deliberately not reproduced locally** | `DEF-MET-4954` |
| `AST-B-11` Lifecycle has no toolkit | defect, B14 12·13·14·16 | **CONFIRMED, and it is 12·13·14·16·17·36** | `DEF-MET-4955` |
| `AST-B-06` Map dropdowns | fragility | **CONFIRMED and wider than stated** | `DEF-MET-4959` |
| `AST-B-15` descriptions | defect, six screens, 6–8 word convention | **SPLIT: FOUR breach rule 33 (and three also rule 32); two are a PO RULING, not a defect** | `DEF-MET-4961` |
| B14 rule 15, five controls | violation | **CONFIRMED, measured** | `DEF-MET-4956` |
| B14 rule 13, sort never clears | violation | **CONFIRMED, measured** | `DEF-MET-4957` |
| B14 rule 16, no first/last | violation | **CONFIRMED — and it is four clauses, not two** | `DEF-MET-4958` |
| `BR-SHL-025` on tabs 04 and 05 | violation on both | **CONFIRMED on 05; DISPUTED on 04** | `DEF-MET-4960` |
| `R11` shell anchors | two off-scale | **CONFIRMED, and a third; one blueprint figure not reproducible** | `DEF-MET-4963` |
| `NFR-3` the list is unbounded | one endpoint | **CONFIRMED — and it is FOUR endpoints** | `DEF-MET-4962` |
| — | — | **NEW: two more stale trailers of the shape it generalised** | `DEF-MET-4964` |

---

## 2 · SCREEN BY SCREEN

### Screen 01 · Meters — `?tab=meters`, and the bare address

**Claimed:** a KPI strip with two states; no description; server search, filter,
sort and pagination; 5 row-action controls; `asset_list` returns a materialised
list.

**Verified.**

* **The tab strip draws SEVEN** — Meters · Sub-meters · Behind the meter ·
  Inventory · Lifecycle · Map · Imports. Six are this work's; the seventh is out
  of scope by instruction and nothing here is filed against it.
* **The description slot is not empty — it does not exist.** The rendered
  `page-header` has exactly two children, `page-header-top` and
  `page-header-tabs`. `AssetRegistryPage.tsx:801` passes an explainer only when
  the tab is `sub_meters`. **See §5.1 before calling this a defect.**
* **KPI cards, measured twice.** With 8 rows on one page all four carry figures
  (*Meters in service 7 · 1 masters · 1 subs · 71% AMI*). Add one filter —
  `?tab=meters&per=200&f.status=uninstalled` — and **four elements carry
  `data-kpi-absent`**: four em-dashes under four headings, with the whole result
  set on the page. `kpiRowsComplete` (`assetsShared.tsx:252-264`) requires an
  empty search, zero filters, page 1 and `rowCount >= totalRows`, so a filter
  alone is sufficient and no tenant over one page ever sees a number.
* **Row actions: counts of 3,5,5,5,5,5,5,5 and no overflow control anywhere.**
  An installed row draws View · Edit · Reassign · Log repair · Retire. The rule
  is two plus `…`.
* **Sort cycles `desc → asc → desc`.** Three clicks, read off the URL each time.
  `nextSortState` (`DataTable.tsx:53-59`) has two branches and no clear.
* **The pager renders the range, the size selector, `‹` and `›` — nothing else.**
  See §3, rule 16: it is short of four clauses, not two.
* **The toolbar itself is correct** — a true search placeholder naming six
  things, the `All` pill, filter fields, Download CSV, the column chooser with
  per-column move controls and Reset. Rule 12 is met on 01, 02 and 03.
* **`asset_list` returns `list(qs.order_by(...))`** (`selectors.py:495`) and
  `paginate_queryset` slices that list (`api.py:117-121`). Confirmed. §4.

**Missed by the blueprint:** the page size is not remembered (§3 rule 16); the
footer has no `Page x of y` at all though the wireframe draws one.

### Screen 02 · Sub-meters — `?tab=sub_meters`

**Verified.** Description renders, **24 words in two sentences**. Five row-action
controls on the one row. Pager as 01. **No KPI strip at all** — 0 cards, by the
same ruling that governs 01's, and so `AST-B-01` does not reach this screen.

### Screen 03 · Behind the meter — `?tab=behind_the_meter`

**Verified.** No description (same ruling as 01). **Three KPI cards: Devices 2 ·
Exporting devices 0 · Exported · August 122 kWh.** The first two are counted in
the browser and dash under a filter; **the third is a served rollup and carries
a real quantity with its unit** — which is the blueprint's own correction of its
first version, and it holds here on different data. The file's trailer still
says that card *"is always the stated dash"*; that is the stale-trailer class,
§5.4.

### Screen 04 · Inventory — `?tab=inventory`

**Verified.** Description renders, **18 words in two sentences**. **Two KPI
cards, both SERVED** (`GET /assets/stock`): *Uninstalled assets 2* and *Aged over
12 months 0 · Warranty clock already running*. No toolbar and no pager, which is
correct — four aggregate lines have nothing to search or page — and the drill on
a type name carries a real accessible name (*View uninstalled Meter in the
registry*). **`Parts in Work →` renders live and enabled.** See §5.3 for why
that is not a `BR-SHL-025` breach.

### Screen 05 · Lifecycle — `?tab=lifecycle` (05a/05b/05c are the drawn answer)

**Verified, and this is the flattest reading in the module.** Three tables,
measured: **0 sortable headers · 0 pagination footers · 0 search boxes · 1
row-action control in the whole tab** (the wrench, on the certifications table).
They are a local `TABLE` class string (`AssetLifecycleTab.tsx:85`), not
`DataTable`.

**Missed by the blueprint, three things:**

1. **Rule 17.** `certifications` and `warranty_groups` each render a `colSpan`
   empty row; **`age_forecast.rows.map(...)` has no empty branch** — a tenant
   with no expected-life data gets a header, no rows, and a bare *Programme*
   total.
2. **Rule 36.** Hand-rolling a table where the kit declares one is the rule-36
   clause in its own words, and the blueprint cites 12/13/14/16 only.
3. **Two as-built elements are absent from screen 05c's carry-over table** — the
   **Programme total row** and the whole **Turn into work** panel (its heading,
   its *N due for exchange* sentence and its live *Set up an exchange rule*
   button → `WORK_RULES_ROUTE`). 05c's own arithmetic does not close either:
   it counts 10 as-built elements and then lists 9 unchanged + 1 relabelled +
   1 removed = 11. Whoever builds 05c must decide where those two go.

### Screen 06 · Map — `?tab=map`

**Verified, and `AST-B-06` is real and larger than written.** The four selects
declare `min-h-8 border border-divider bg-surface px-2 py-1 text-sm` and set no
`appearance`. Measured with `getComputedStyle`:

| | in place, inside `main.view` | the SAME element re-parented outside it |
|---|---|---|
| `appearance` | `none` | **`auto`** |
| chevron | the product's gradients | **none — the browser's own control** |
| `min-height` | 36px | **32px** |
| `padding` | 6px 30px 6px 10px | **4px 8px** |

`.view select` (`FormModal.css:423`) supplies all four, and `.view` is on
`<main>` (`AppShell.tsx:1011`). **So the component's own Tailwind classes are
inert on three properties as well as the chevron** — `.view select` outranks a
utility on specificity. Rename that wrapper and four dropdowns change size and
lose their chevron with every check green.

Description renders, **23 words in two sentences**.

### Screen 07 · Assign N assets to a unit

**Not opened** — the dialog needs row ticks and every tick is a step toward a
write. Its markup was read and nothing in it contradicts the blueprint. **Blind
spot, recorded: 0 of 1 dialog states walked.**

---

## 3 · THE RULE VIOLATIONS, WITH THEIR MEASUREMENTS

| rule | what it says | measured | enforced? |
|---|---|---|---|
| **15** | icons, **max 2 + `…`** | **5** in a cell, **0** overflow controls; `RowActionsMore` exists and **1** screen in the product uses it | **Partly.** G37 holds the icon, the name and the icon's single owner, and says in its own docstring it does not check the cap |
| **13** | asc → desc → **clear** | `desc` → `asc` → `desc` | **No.** Empty column in B14; shared component, so every list fails identically |
| **16** | range · size · **⇤** ← **Page x of y** → **⇥**, size **remembered** | range ✓ · size ✓ · ‹ ✓ · › ✓ · **no ⇤ · no ⇥ · no Page x of y · size NOT remembered**. ⚠ The first three were already `DEF-2449` and `DEF-449`, open since 2026-08-30; **only the page-size clause is new** | **No.** B14 names "shared DataTable", which guarantees only that every screen is wrong the same way |
| **12 · 14 · 16 · 17 · 36** | toolbar · chooser · pager · empty state · compose the kit | **none of them, on all three Lifecycle tables** | **No.** G43 holds the toolbar contract for lists declaring `searchFields`; a hand-built table declares none and is outside the gate by construction |
| **18** (80% cap) | descriptions cap at 80% | **MET** — `max-width: 80%`, 896px rendered, on all four tabs that render one | G43 clause (b) checks only for the wrong Tailwind cap |
| **33** (words per sentence) | an INSTRUCTION caps at **6 words per sentence** | **every rendered description breaches**: sentences of 11, 13, 7, 11, 9, 5 and 18 words | **No.** Nothing counts a word on a screen |
| **32** (one sentence) | one sentence per section | **Sub-meters 2 · Inventory 2 · Map 2 · Lifecycle 1** | **No.** Rule 32's own status column says clauses 1, 3 and 4 are unenforced |
| **`BR-SHL-025`** | a forbidden action is disabled with its reason | the Lifecycle **wrench** carries no `reason`; `writeBlockedReason` occurs **once** in each tab file, in the type declaration | **No — and G13 cannot see it.** G13 asks whether a prop has a caller. It does |
| **`R11`** | one scale: 4·8·12·16·20·24·32 | rail item **9px 12px**, gap **10px** · status pill **2px 9px**, gap **5px** · `main.view` **24/24/56/24** | **No.** The CR-016 browser check reads type sizes and control heights, not padding |
| **`R11`, the parts that PASS** | | table cell **8px 12px** · body **13.5px** · header **12px** · KPI cell **16×20**, gap **6** · page title **32px** | rule 20 is gated and green |

**1280 behaves.** No page-level horizontal scroll on any of the six tabs
(`scrollWidth` 1280 = `clientWidth` 1280). The three registry tables are wider
than their wrapper and scroll **inside** it, which is the allowed pattern.
Below 1280 was not measured and is not in scope: this is a clerk and
utility-admin surface.

---

## 4 · `NFR-3`, SIZED HONESTLY AGAINST 40,000

**The blueprint files one endpoint. There are four.**

| read | what it materialises | queries, measured |
|---|---|---|
| `GET /assets` `selectors.py:495` | the whole match set; the paginator slices a **Python list**, so no `LIMIT`/`OFFSET` reaches SQL | unfiltered **1** |
| …with `f.assigned=true` | + one query **per matching row** (`_current_assignment`) | **9** over 8 rows |
| …with `f.service=water` | + a seam call per row (`_service_of`) | **15** over 8 rows |
| …with both | | **23**, to return **one row** |
| `GET /assets/stock` `:1812` | every `available` asset; **no page parameter exists** | **7** |
| `GET /assets/lifecycle` `:1903` | `fleet = list(...)` — **every non-retired asset**, then three Python passes; **no page parameter exists** | **9** |
| `GET /assets/geo` `:2078` | every non-retired asset on a geocoded premises, in ONE payload, filtered in the browser; **no page parameter exists** | **1 — AND THAT NUMBER IS WORTHLESS** (§6) |

Measured with `CaptureQueriesContext` against real Postgres on an 11-asset
tenant. **The loop is over the match set and never over the page**, so the shape
is linear in the tenant: at 40,000 assets `f.assigned=true` is of the order of
**40,001 queries in one HTTP request**. The list row costs **1,013 bytes**
serialised (8,108 bytes / 8 rows), which is what the map would send in one
response.

**Correct at T7, and the top of T5 is 13× further on.** Same shape as
`DEF-PAY-4221`. The envelope is honest; the query behind it is not.

---

## 5 · WHERE THIS LANE DISAGREES

### 5.1 `AST-B-15` is two findings, and the bigger half is a PO RULING

The two blank tabs are **not** an oversight. `B16 §10-D9`, put to the PO on
2026-08-22 — *"Two Assets tabs still show explainer prose where r10 draws a
4-card KPI grid … **Confirm: drop the prose, draw the KPI grids.**"* — and
answered: ***"D9 RULED — draw the KPI grids"***. The code says so at
`AssetRegistryPage.tsx:796-801`, and **`AssetRegistry.test.tsx:760-784` asserts
the absence by name, citing D9**.

**Counted the way a reader will ask it: of the six tabs, TWO are ruled blank and
FOUR render a description, and all four are over rule 33's budget.**

**So filing the blank tabs as a defect and "fixing" them reverses a PO ruling —
and CR-092 §2 says no signed statement is reversed by any of this ("None. Not
one.").** That sentence is wrong for this one row, and a step-2 lane that
believes it will quietly overturn D9 while editing a test that says so.

**The order that keeps the ruling:** fix `DEF-MET-4953` first. D9's premise is a
grid that shows numbers; today it shows dashes, which is why the tabs carry
neither. Serve the four counts and the premise is true again — **and then
nothing at all is owed on screens 01 and 03**, and the two catalogue keys
(`assets.explainer.meters`, `.behind_the_meter`, live in all eleven catalogues,
9 and 8 real words) are dead **by ruling** and should be retired rather than
wired. `AssetRegistryPage.tsx:801`'s own comment already says dropping the
KEYS was not its lane's call; it is somebody's.

### 5.2 The "six to eight word convention" is not in this repository — and the real cap is STRICTER, which corrects this lane's own first reading

Grepped `04-docs/`, `12-governance/` and `05-prototype/` for *"six to eight"*,
*"6–8 words"*, *"6-8 words"*: **zero hits.** B14 rule 18 caps the **width**, and
that is **MET** (measured `max-width: 80%`, 896px rendered, on all four tabs).

**Two ratified rules do reach this copy, and they are different rules.**

* **Rule 33** — *on-screen text is capped by what it is FOR*. A tab description
  is an INSTRUCTION, and the cap is **six words PER SENTENCE**. It also says,
  in terms, that *"two sentences of six beat one sentence of twelve"*.
* **Rule 32** — *one sentence per section* (PO 2026-08-31, *"too much content -
  desctiption is too much for clark to read"*).

Measured **per sentence**, which is what rule 33 asks for:

| tab | sentence 1 | sentence 2 | rule 33 | rule 32 |
|---|---|---|---|---|
| Sub-meters | 11w | 13w | **breach ×2** | breach |
| Inventory | 7w | 11w | **breach ×2** | breach |
| Lifecycle | **9w** | — | **BREACH** | conforms |
| Map | 5w ✓ | 18w | **breach** | breach |

⚠ **THIS CORRECTS `DEF-MET-4961`, WHICH THIS LANE FILED CITING RULE 32 ALONE
AND CONCLUDED THAT LIFECYCLE CONFORMS AND SHOULD NOT BE TOUCHED.** Under rule
33 its nine words breach, so **all four rendered descriptions are over budget,
not three** — and the row's citation is incomplete rather than wrong. The two
blank tabs remain §5.1's ruling and are not part of the count either way. **The
target both rules agree on: one sentence of six words or fewer.**

The escape is worth naming because it is this lane's own: `CLAUDE.md` summarises
rule 33 as *"a refusal sentence caps at five or six words"*, which is a pointer
to one of its five kinds, and reading the pointer instead of the rule is what
produced the incomplete citation. **B14 is the authority; its summary in
`CLAUDE.md` is not** — which is the same lesson that line already carries about
its own rule COUNT, five times over.

### 5.3 `BR-SHL-025` does not reach `Parts in Work →`

The rule gates **forbidden actions** — *"gating driven by server-provided
permission set only; server independently enforces every mutating call"*. That
button navigates to the parts register, a **read** screen a read-only role may
open. `AssetInventoryTab.tsx:72-74` says as much in its own words. **The
Lifecycle wrench half stands** — it opens the raise-work-order form, which
writes.

### 5.4 `AST-B-01`'s screen list

The spec names screens **01, 02, 03, 04**. Measured: **02 renders no KPI strip
at all**, **04 is entirely served**, and on **03** only two of three cards are
client-counted. It reaches **01 and 03**.

### 5.5 One blueprint measurement could not be reproduced

It reports the screen body as **24/16/32**. `main.view` on this tip computes
**24px 24px 56px 24px**. The element it measured is not identified closely
enough to re-measure, so this is recorded as a disagreement rather than a
correction. Every other spacing figure it gives was reproduced exactly.

---

## 6 · WHAT THIS LANE COULD **NOT** CHECK, AND THE NUMBER

1. **`GET /assets/geo`'s real cost. 0 geocoded premises on this tenant**, so
   `geo_view` returned at its first branch and the "1 query" measurement says
   nothing. Its payload is unbounded by construction; its cost is unmeasured.
2. **Behaviour above one page. 8 meters here against 109 there.** Everything
   about page 2 is read from the code and from the blueprint's own walk.
3. **`AST-B-20` end to end. Not reproduced locally, on purpose** —
   `config.settings.local` defaults `JOBS_EAGER` to true, so the job runs
   in-process and the download would have succeeded, proving nothing about a
   deployment that sets it false. Verified from source instead: `grep` for a
   line beginning `volumes:` in `docker-compose.yml` returns **nothing**.
4. **Three empty states.** The Lifecycle forecast table's missing empty branch
   is read from source; the seeded tenant has 5 forecast rows and the state
   cannot be reached from the screen. Same for the registry's empty and failed
   states: **0 of 3 non-happy states walked** on screens 01–03.
5. **Screen 07, the bulk-assign dialog: 0 states walked** (every route into it
   starts a write).
6. **Read-only-role rendering: not walked.** The session was System Admin. The
   `BR-SHL-025` findings are read from source — the absent `reason` prop and the
   once-only identifier — not from a clerk's screen.
7. **The Imports tab: deliberately untouched**, 0 observations, out of scope.

---

## 7 · THE ROWS FILED — AND THE FOUR OF THEM THAT WERE ALREADY SOMEBODY'S

⚠ **THIS LANE CHECKED THE REGISTER'S MAXIMUM AND NOT ITS CONTENTS, AND FOUR OF
ITS TWELVE ROWS WERE ALREADY FILED.** Recorded here rather than quietly closed,
because the escape is more useful than the rows:

| mine | already filed as | marked |
|---|---|---|
| `DEF-MET-4956` rule 15, five controls | `DEF-SHL-4948` (lane 6, same day — counted **14** tables product-wide and names this registry) and `DEF-2453` | **duplicate** |
| `DEF-MET-4957` rule 13, sort never clears | `DEF-SHL-4946` (lane 6, same day, same file and lines) | **duplicate** |
| `DEF-MET-4958` the pager | `DEF-2449` and `DEF-449`, **open since 2026-08-30** | **duplicate** — the one clause neither carries, *the page size is not remembered*, is §3's and belongs on `DEF-2449` |
| `DEF-MET-4960` `BR-SHL-025` | `DEF-MET-4950` (lane 6, same day, same two files) | **duplicate** — and §5.3 **disagrees** with its Inventory half |

**`DEF-MET-4962` (NFR-3) is left OPEN deliberately and it overlaps
`DEF-MET-4951`**, which covers the list half only. The three other unpaginated
endpoints and the measured query counts exist nowhere else. A step-2 lane should
fix the two together and close 4951 with it.

**The escape, stated plainly:** `file_defect.py` allocates the next id against
the remote and answers *"is this number free"* — which is a different question
from *"has somebody already filed this finding"*, and nothing in this repository
asks the second one. On a product-wide component (`DataTable`, `RowActions`) the
odds are high and the search is one grep. **Grep the register for the SUBJECT
before filing a shared-component row**, not for the id.

⚠ **AND THE ID RACE HAPPENED TOO, EXACTLY AS LAW 11 DESCRIBES IT.** These rows
were allocated in the block beginning **4946**; lane 6 pushed **4946–4952**
while this document was being written, so **seven of the twelve numbers had been
taken by somebody else by the time the push came round** (four of them under a
different module prefix, and two — `DEF-MET-4950` and `DEF-MET-4951` — under the
same one, which would have been a true collision). Re-derived from the pinned tip
at push time and renumbered to `4953`…`4964`, with the register rebuilt as the
tip's bytes plus twelve appended lines and the prefix proved byte-identical.
That is the law's own procedure catching the law's own failure mode, and it cost
one command.

## 7b · THE TWELVE

`DEF-MET-4953` KPI figures · `4954` export saves a 404 · `4955` Lifecycle has no
toolkit · `4956` five row actions · `4957` sort never clears · `4958` the pager's
four missing clauses · `4959` the map's inherited dropdowns · `4960` the unguarded
wrench and the dead prop · `4961` the tab descriptions (see §5.2 — its citation is incomplete) · `4962` NFR-3,
four unbounded reads · `4963` three off-scale anchors · `4964` two more stale
trailers.

Each carries its `AST-B-##` in the title where one applies, so a reader holding
the blueprint can find what became of it. **Eleven of the twelve escape the same
way and it is worth counting rather than repeating: no gate in this repository
reads rendered output.** The twelfth (`4964`) escapes differently and more
interestingly — `G38` was built for stated absences and covers the other
audience: a sentence rendered to a **user**. An absence stated to the next
**engineer**, in the trailer convention `G11` makes mandatory, is read by
nothing at all.

---

## Trace

* **Packet:** `CR-092-BRC01` §3 §4 §6 · the blueprint's sections 01, 02 and 09 ·
  `B14` (**thirty** rules, numbered 1–21 and 31–39 — corrected 2026-09-11, `DEF-4952`) · `B16 §10-D9` · `NFR-3` · `NFR-5` · `BR-SHL-025` ·
  `BR-AST-004/006/031`.
* **Measured at** `0a1a677d9`, 2026-09-11, on a stack booted per
  `10-scripts/11-smoke-stack.sh` (private ports 8511/8512, no seed, no write),
  at 1440 and 1280.
* **Status:** step 1 complete. **Nothing in this lane was fixed.**
