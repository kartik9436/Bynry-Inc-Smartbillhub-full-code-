# EP-MET-06 — New connect worklist (`NCT-01`)

**Module:** metering (owns `connections`, B2 r4 / B18 §5.4.6) · **Wave:** CR-030 **W6** (`2.47.0`) — *not* B12's W6 · **Screens:** S86 (Accounts → **New connects** tab) · **Status:** draft

> ⚠ **THIS EPIC WAS WRITTEN AFTER THE CODE, AND SAYS SO — DEF-695, hard-won law 8.**
> S86 shipped on 2026-08-25 with **both halves built** (`connection_reads.py` +
> `NewConnectsTab.tsx` + `GET /connections` mounted) and **no user story owned it**.
> Three source files filed the finding themselves — `connection_reads.py`'s
> lifecycle block reads *"no US-ID owns this screen; hard-won law 8 says every
> screen needs a story and S86 has none, REPORTED rather than invented here"* —
> and six lanes reported it independently on 2026-08-25.
> **Every acceptance criterion below is RECOVERED FROM WHAT EXISTS**, checked
> against B18 §5.4 and against the test that asserts it. **Where B18 draws
> something the code does not do, this epic records it as NOT BUILT with the id
> that tracks it** (§8 of the story, and the summary table at the end of this
> file). Nothing here is an aspiration; a story that described one is how the
> next lane builds the wrong thing.

## Scope

**In:** the **read-only worklist** at S86 — B18 §5.4.2's eight columns over `connections`,
§5.4.1's five KPI tiles, the fixed target-date ordering, the five-leg search, the
house pagination envelope, and the **drawn-but-unserved** segment strip rendered
disabled with the server's own sentence (OQ-371, OPEN). The screen is an
**embedded tab** inside `AccountsListPage` and owns no query string (DEF-664).

**Out:** **S87**, the eight-step New Connect wizard (`POST /connections` and every other
write path in B18 §5.4.6 — `connections.py`'s lane) · **S88** / `NCT-02`, the connection
detail (no route in this application) · work-order detail and templates screens
(B18 §11 task 6.14, ⛔ D1 — no screen ids left) · the segment PARTITION itself
(OQ-371 — nothing in this epic decides it) · the `service_characteristics` shape
(W6 task 6.9a, BR-MET-108) · the owner/master build account (BR-MET-116, S87 step 9)
· the *"your service is live"* dispatch (OQ-372) · seed data for §5.4.8's eight rows
(a data lane's) · export (`POST /exports` registers no `connections` resource).

**Tables:** metering-owned `connections` · `connection_services` · `work_orders`
(read through `connections.py`'s own derivations — `order_progress()`,
`service_progress()`, `connection_state()` — never re-implemented) · `premises`
(join) · `customers.service_requests` read across the **declared** cross-module FK
`connections.service_request_id` (B2 §2's reviewed interface set — a READ, not a
cross-module write).

## Capability matrix (list screens only — B9 conformance)

| Screen | Search fields | Filters | Default sort | Sortable | Columns default/available | Row actions | Bulk actions | Export |
|---|---|---|---|---|---|---|---|---|
| **S86** `NCT-01` | connection # · premise # · premise name · premise address · request # · applicant name (the five things §5.4.2's placeholder names, six columns ORed by `_search`) | **Five segments DRAWN, ONE SERVED.** `All` (served) · `In progress` · `Waiting` · `Partly activated` · `Done` — the four render **disabled carrying the server's sentence** (BR-SHL-025); any other value raises `NotImplementedError("OQ-371")` | `target_activation` ASC, **nulls LAST**, `id` tiebreak — B18 §5.4.2's footnote, *"Sorted by target date, soonest first — the next thing due is at the top"* | **NONE.** `list_connections` accepts no `sort`/`dir`; no column is declared `sortable`, so `DataTable` draws no control. An unknown param is ignored, never refused (BR-SHL-011) | **Default (8, B18 §5.4.2):** CONNECTION · PREMISE · UNITS · SERVICES · ORDERS · TARGET · WAITING ON · STATE. **Available (+2, off by default):** APPLICANT · REQUEST # — declared so the column chooser can turn on the two search legs whose hits would otherwise look arbitrary | **NONE.** `NCT-02`/S88 has no route in this application, so a 👁 view icon would link onto nothing (hard-won law 2). No actions column is rendered at all — not a disabled one per row | **NONE** | **NONE** — `POST /exports` registers no `connections` resource, so BR-SHL-010 keeps the control unrendered |

## Stories

---
id: US-MET-021
epic: EP-MET-06
module: metering
screens: [S86]
wave: 6                  # CR-030 W6 (`2.47.0`) — NOT B12's wave 6
status: blocked
blocked_by: [OQ-371]     # the segment strip only; the list, the tiles and the columns are BUILT
depends_on: [US-MET-001, US-MET-004]
# ⚠ THE REAL UPSTREAM HAS NO STORY TO NAME. A connection is created FROM AN
# APPROVED SERVICE REQUEST (B18 §5.4.6 `POST /connections`), and S83/S84/S85 —
# the request front door — own no story either: `J26-request-to-service.md`
# carries `stories: []` for exactly this reason and marks US-CUS-024..026 OWED.
# Naming an id that no register row answers is the failure J26 avoided, so the
# dependency is stated here in words instead.
journeys: []             # J26 stops at the approved request; no journey reaches the connection worklist — REPORTED, not invented
rules: [BR-SHL-010, BR-SHL-011, BR-SHL-012, BR-SHL-013, BR-SHL-025, BR-TEN-003, BR-MET-104, BR-MET-116]
golden_tests: []
finance_calc: none
---
### US-MET-021 — The new-connect worklist: seven open builds, 42 units, and the four tabs that are switched off

**1 · Details** — As a **connections dispatcher** at a North American utility of up to 40,000 accounts (*"a small utility"* until the ICP ruling of 2026-09-06), I want the Accounts screen's **New connects** tab to list every build in flight — its number, its premise, how many units it touches, which services it carries, **how many work orders of how many are done**, when it is due, what it is waiting on and what state it is in — above a five-tile strip that tells me how much is open and what the oldest thing is, so that a 25-unit job is visible as **25 units of risk rather than one row** (B18 §5.4.1's `UNITS AWAITING ENERGISATION 42 across the 7 open builds`).

**Entry:** S17 Accounts → tab **New connects** (`AccountsListPage.tsx`, `ACCOUNTS_BUILT_TABS`; the tab mounts `NewConnectsTab`). **There is no standalone `/connections` route** in `App.tsx` (measured 2026-08-25), so this is always the embedded copy. **Exit:** none — the row goes nowhere.

**What it calls:** `GET /connections` → `apps/metering/api.connections` → `connection_reads.list_connections(segment, q, page, per)`. Registered from **metering** because metering owns `connections` (B2 r4 / B18 §5.4.6). Read-only on purpose: every write path in §5.4.6's endpoint table belongs to S87's lane.

**⚠ THE ASYMMETRY THAT IS THE POINT OF THE READ MODEL, AND IT IS DELIBERATE.** `Connection.state` says of itself *"`state` IS A CACHE of `derive_connection_state()`"*. So **a ROW reports the derivation** — `connections.connection_state(row)`, run over that build's own service rows, because the row is where a person reads a state and a drifted cache would put the wrong badge on the PO's own screen — while **a TILE counts the cached column**, because *"a derived state cannot be a `WHERE` clause"* and deriving five tiles per connection would be two queries per row over the whole table. `test_w6_list_a_stale_cache_cannot_reach_the_row` forces the two apart on purpose, so which is which is a fact the suite states rather than a claim a docstring makes (hard-won law 1).

**⚠ CR-032 — THE PRODUCT WORD IS `activated`, AND B18 STILL DRAWS *"Partly energised"*.** PO 2026-08-25, verbatim: *"instead of energise can we use activated"*. Shipped in `2.46.0`; `connections.py`'s tokens are `ACTIVATED` / `PARTLY_ACTIVATED` and the old names are **gone, not aliased**. B18 is stamped rather than rewritten — rewriting a quotation to match a later ruling destroys the evidence that the ruling changed anything. **The UI ships the new word**, and a test asserts the string `energis` appears nowhere on the tab.

**⛔ FIVE THINGS `NCT-01` DRAWS THAT THIS STORY DOES NOT DELIVER**, each with the id that tracks it — see §8:
1. **Four of five segment tabs** (OQ-371, OPEN — disabled with the server's sentence).
2. **The `+ New connect` primary and `Export`** (BR-SHL-010 — no S87 route, no `connections` export resource; the empty-state CTA is drawn **disabled with that reason**).
3. **A row action, or any way into `NCT-02`** (S88 has no route — law 2).
4. **A sort control** (the server fixes the order).
5. **The superscript tab count** `New Connect ⁷` (`PageHeaderTab` has no count slot; `components/PageHeader.tsx` is another lane's file).

**⛔ AND ONE PRICE THE USER PAYS, STATED: a page or a search inside this tab does not survive a reload and cannot be pasted to a colleague.** The tab owns no query string — it never imports `useSearchParams` — because DEF-664 measured that two components serialising into one query string silently overwrite each other, and the READ half is the one that is easy to forget: an embedded list that parsed the outer page's `?page=3&q=smith` would open New connects on page 3 of a search somebody typed into the accounts list. Namespacing the parameters is **BR-SHL-011's to settle, not a lane's** (DEF-664's own words). Unlike Requests, there is no standalone screen to go to instead.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| BR-SHL-011 | *"URL state grammar `q/sort/dir/page/per/f.‹name›`; shareable; unknown/invalid values fall back or clamp, **never error**"*. Applied: `per` clamps through `core.pagination.clamp_page_size` (50/100/200/500/1000), `page` clamps into `[1, last]`, garbage falls back to 1, and `sort`/`dir` are **declared empty** and ignored rather than refused. | CONFIRMED — PO R1-B4 (B9 / IS-4) |
| BR-SHL-011 *(embedded exception)* | An **embedded** list inside a tab owns NO query string: it neither reads nor writes one, and its page/search live in component state for as long as the tab is mounted. The *"shareable"* clause of BR-SHL-011 is therefore **not met on S86**, deliberately. | **PROPOSED** — derivation of DEF-664 (two components serialising into one query string overwrite each other). ⛔ **DEF-664 states the real fix is namespacing the params, and that it is BR-SHL-011's to settle, not a lane's.** Recorded as a divergence, not a decision |
| BR-SHL-010 | *"One shared table framework; config declared per screen via B9 capability-matrix row; **undeclared capabilities don't render**"*. Applied: no export control (no `connections` export resource), no primary (no S87 route), no actions column (no S88 route). | CONFIRMED — PO R1-B3 |
| BR-SHL-025 | A control that cannot be used renders **DISABLED WITH ITS REASON**, never hidden — *"a control that vanishes sends somebody hunting for it"*. Applied to the four unserved segment tabs (the reason rides on `title`, the slot `GuardedButton` uses for the same job everywhere else) and to the empty-state CTA. | CONFIRMED |
| BR-SHL-012 | The framework owns skeleton / zero-results / failed states; the screen supplies only empty-list copy + CTA. **Applied with one sharp edge asserted: a FAILED read never renders the empty state** — *"No new connects yet"* over a 500 asserts *"you have none"*, which is a different and false claim. | CONFIRMED — A18 §1–4 |
| BR-SHL-013 | Column prefs per (user, tenant, screen), keyed on the screen id. Applied: `TableConfig.screenId = "S86"` (`NEW_CONNECTS_TABLE_SCREEN`), which is also what puts `data-screen="S86"` on the mount. | CONFIRMED — IS-5 |
| BR-TEN-003 | Tenant resolution. `connection_reads._tenant_id()` raises `AuthError(AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")` when no tenant is set — hard rule 1's failure is an error, not a missing filter. | CONFIRMED |
| CLAUDE.md hard rule 1 *(cited, not restated)* | Never touch a tenant table without `app.tenant_id`; RLS `FORCE` is on (migration 0027). The app-layer `filter(tenant_id=…)` is convenience; RLS is the law. | CONFIRMED — hard rule |
| **The row/tile asymmetry** | A ROW reports `connection_state()` (the DERIVATION); a TILE counts the cached `connections.state` column. They agree in the product because `refresh_connection_state()` is the only writer and every write path calls it. | **PROPOSED** — derivation of `Connection.state`'s own declared contract (*"`state` IS A CACHE"*); pinned by `test_w6_list_a_stale_cache_cannot_reach_the_row` |
| **The five tile formulas** | B18 §5.4.1 draws figures and captions and **defines no formula**, so §5.4.8's eight seeded rows are the only published statement of what each figure means. Each tile is the ONE arithmetic that reproduces the drawn number over those eight rows (worked in §7). | **PROPOSED** — derivation from §5.4.1's drawn figures + §5.4.8's eight rows |
| **`open` includes `draft`; `cancelled` is excluded** | Not one of the eight drawn rows is a `draft` or a `cancelled`, so the drawing **does not discriminate on either**. A cancelled build is not *"service being established"* under any reading; a draft somebody started and has not submitted is unfinished work and is counted. | **PROPOSED** — this module's reading of an **untested boundary**, REPORTED rather than presented as drawn |
| **`oldest` starts at `submitted_at`, falling back to `created_at`** | *"a build becomes the utility's to deliver when it is requested, not when someone opened a draft"*; a draft that was never submitted has no submission, so its creation is the only date it has. `NCT-02` heads the same figure *"Started Aug 12"*. | **PROPOSED** — derivation from `NCT-02`'s header + §5.4.1's *"19 days"* |
| BR-MET-104 *(context, not implemented here)* | The flat-service pricing characteristic lives on the **UNIT** (PO 2026-08-24, closing OQ-348: *"(a) a characteristic on the service point - we ahve it on unit"*). Nothing on S86 reads or writes one; the SHAPE is W6 task 6.9a (BR-MET-108) and is not this screen's. | CONFIRMED — PO 2026-08-24 |
| BR-MET-116 *(context, not implemented here)* | A multi-unit build's charges are invoiced to the developer through a **master account**, anchored on the premises' common-area unit; *"unit will be all vacant right now"* (PO 2026-08-25). S86 shows no money and creates no account. | CONFIRMED — PO 2026-08-25 (OQ-373 CLOSED) |
| OQ-371 | **Which exclusive segment holds a build that is `partly_activated` AND waiting?** No segment function exists. `segment=all` is served; every other value raises `NotImplementedError("OQ-371")`. | **OPEN — blocking the S86 segment strip** |
| OQ-375 | **Is `waiting_on` an eight-value vocabulary or free text?** It is an unconstrained `TextField`; the `WAITING ON INSPECTION` tile matches the single literal `inspection`, case-insensitively and exactly. | **OPEN — non-blocking, and the drawn tile is an undercount while it is open** |

**3 · Test Cases**

*(Every case names the test that already asserts it, so the story and the suite cannot drift apart. Backend: `06-backend/tests/test_w6_connection_list.py`. Frontend: `07-frontend/src/features/customers/NewConnectsTab.test.tsx`.)*

| TC | Scenario | Expected | Asserted by |
|---|---|---|---|
| TC-1 | Dana opens Accounts → **New connects** with §5.4.8's eight rows seeded | The eight drawn columns render `CON-26-0117`: premise `500 Main Street`, units **25**, services `E W S T +1`, orders **5 of 7**, target Sep 30, waiting on `inspection`, state **Partly activated** | `test_w6_list_a_row_reads_as_the_screen_draws_it` · FE *"§5.4.2 — the eight drawn columns render the drawn row"* |
| TC-2 | The KPI strip over those eight rows | **7 · 2 · 3 · 42**, and `OLDEST` = **19 days · CON-26-0119 · permit** — the arithmetic worked in §7 | `test_w6_list_the_five_drawn_kpi_figures_come_out_of_the_eight_seeded_rows` · FE *"§5.4.1 — the five drawn figures reach the strip"* |
| TC-3 | `CON-26-0126` (`partly_activated`) and `CON-26-0117` (`partly_activated`) both wait on `inspection`, while `CON-26-0121` (`in_progress`) waits on `materials` | `WAITING ON INSPECTION` = **2** across **two different states** — which is exactly why `waiting_on` is a column of its own beside STATE and is not the hold's reason | `test_w6_list_the_tiles_count_two_different_states_as_one_waiting_number` |
| TC-4 | `CON-26-0117` — 25 units, 5 services, **seven** work orders (§8's batching proof) | `ORDERS` serves `{done: 5, total: 7}` and renders as the FRACTION `5 of 7` over an accent underline — *"not a percentage, not a bar alone. The fraction is readable; a bar is not."* A build with **0 of 7** draws no fill at all: zero of zero is not complete | `test_w6_list_orders_is_done_of_total_and_the_25_unit_build_keeps_its_seven` · FE *"ORDERS draws a fraction over an underline, and a build with no orders draws no full bar"* |
| TC-5 | A later connection is raised on a premise that already holds 40 units and touches 3 of them; a per-premise service (`unit_id` NULL — the main tap) is on it too | `UNITS` reads **3** — not 40 and not 4. A build's units are the ones its SERVICES name, and a per-premise service belongs to the build and to no unit | `test_w6_list_units_count_only_the_units_this_build_services` |
| TC-6 | The list is ordered; `CON-26-0124` has **no** target date | Target ASC, soonest first (`CON-26-0110` Aug 14 at the top); the **no-target build sorts LAST** and renders `—` — *"a missing date is not the most urgent thing on the list"* — with `id` breaking ties so row 26 does not reappear on page 2 (IS-2) | `test_w6_list_is_sorted_by_target_date_soonest_first` · `test_w6_list_a_build_with_no_target_sorts_last` · FE *"a build with no target renders a dash and is not given a date"* |
| TC-7 | Dana searches `Foundry`, then `SR-26-0043`, then the applicant's surname | All five things the placeholder names match — connection #, premise (no/name/address), request # and applicant name — the last two through the **declared** FK `connections.service_request_id`; both are carried on the row so a clerk can see why it matched | `test_w6_list_search_matches_the_five_things_the_placeholder_names` |
| TC-8 | A cached `connections.state` is forced out of step with the build's own service rows | The **ROW** shows the derivation and the **TILE** shows the cache — the stale cache cannot reach the row | `test_w6_list_a_stale_cache_cannot_reach_the_row` |
| TC-9 *(negative)* | A client requests `?segment=waiting` (one of the four `NCT-01` draws) | `NotImplementedError("OQ-371")` **by name**; the endpoint does **not** swallow it into an empty list — a segment that silently returned every build is the worst of the three outcomes. ⚠ **The view lets it surface as a ≥500**: a named refusal rather than a 404, because *"a 404 reads as a typo and this is a decision nobody has taken"*. See §8 for the inconsistency with S90 | `test_w6_list_every_segment_but_all_refuses_by_name` · `test_w6_list_endpoint_refuses_a_segment_it_was_never_told_how_to_build` |
| TC-10 *(negative)* | A later lane adds a `segment_for()`, a precedence map or a state→segment table to `connection_reads` | **RED.** No such function exists and a test asserts its absence — *"the failure mode here is not a crash, it is a build sitting quietly under the wrong tab on the PO's own screen while every test passes"* | `test_w6_list_no_segment_rule_is_shipped` |
| TC-11 *(negative)* | The screen renders before any response, then the response arrives | Before: the strip holds **only `All`** — the four unserved names are read off the payload, never typed into the screen, so *"the screen does not yet know what it cannot do"*. After: five tabs, `All` selected, four **disabled carrying the server's own sentence**, and **the route is never called to discover the refusal** | FE *"⛔ OQ-371 — five segments are drawn, four are DISABLED carrying the server's reason"* · FE *"the segment strip holds only `All` before the first response — it does not invent the other four"* |
| TC-12 *(negative)* | `?page=abc&per=75`, then a page past the end | Clamped, **never a 4xx**: `per` → the nearest house size, `page` → `[1, last]`, and both come back as the values that were USED, so a caller that asked for page 99 is told it got page 3 of 50-row pages | `test_w6_list_pagination_clamps_and_never_errors` |
| TC-13 *(negative)* | The tenant has no connections at all | `OLDEST` reads **"None open"**, never `0 days` — *"0 days"* is a different claim from *"there is none"* (the DEF-127 judgment, one column over) | `test_w6_list_an_empty_tenant_has_no_oldest_rather_than_a_zero` · FE *"§5.4.1 — OLDEST states there is none rather than printing `0 days`"* |
| TC-14 *(negative)* | `GET /connections` fails | The failure state renders with a retry — and **never the empty state**, which would assert *"you have none"* over a read that did not happen | FE *"a failed read never renders the empty state — that would assert 'you have none'"* |
| TC-15 *(negative)* | The tenant has no builds, so the empty state renders with its `+ New connect` CTA | The CTA is **disabled with its reason** — *"The new-connect wizard is not built yet, so this cannot start here."* — not a live button onto nothing (BR-SHL-025 / law 2) | FE *"BR-SHL-025 / law 2 — the empty state's CTA is DISABLED with its reason, not a button onto nothing"* |
| TC-16 *(isolation — tenant data)* | Erin (Lone Star Ridge) calls `GET /connections` while Brazos Bend holds all eight builds | **None of Brazos Bend's rows, and none of its tiles.** Every count and every row is scoped by `app.tenant_id`; RLS `FORCE` is the law and the app-layer filter is convenience (CLAUDE.md hard rule 1) | `test_w6_list_is_tenant_scoped` |
| TC-17 | A clerk reads the tab after CR-032 | The word `energis` appears **nowhere** on it; the state pill and the tile read **`Partly activated`** | FE *"CR-032 — the tab says `activated`, and the word `energis` appears nowhere on it"* |
| TC-18 | The tab is mounted and opened | It **calls** `GET /connections` — *"the endpoint is not merely wired in a comment"* (law 2) — and the route resolves through metering's own `urlpatterns` | FE *"law 2 — the tab CALLS `GET /connections`"* · `test_w6_list_endpoint_is_mounted` |
| TC-19 | The response envelope | The house DRF shape (`count`/`next`/`previous`/`results`) with `kpis` and `segment` riding alongside — one shape for every list, because *"eight shipped call sites once read two of these endpoints as bare arrays"* | `test_w6_list_endpoint_answers_the_house_envelope_with_the_kpi_strip` |
| TC-20 | The sentence a utility user reads for the switched-off tabs | Carries **no** `OQ-`, `BR-`, `§`, route or module name (G28 / CR-016); the provenance lives on `br_ref`/`tracks`, and `tracks: "OQ-371"` is what makes the absence expire when the question closes | `test_w6_list_endpoint_states_the_absence_in_words_a_utility_can_read` |
| TC-21 | Every string on the tab | No raw translation key ever reaches the screen — every call site carries a `defaultValue`. ⛔ **One exception is declared:** `searchPlaceholder` is deliberately **left unset**, because `DataTable` renders it through `t(key)` with no fallback and would print the literal `customers.newConnects.list.searchPlaceholder`; the box shows the shared *"Search this list"* until the locale lane adds §5.4.2's own sentence | FE *"no raw translation key reaches the screen — every call site carries a defaultValue"* |
| TC-22 *(NOT BUILT — recorded, not claimed)* | A dispatcher pages to 2, searches `Foundry`, and reloads | The page and the search are **lost**; the URL is the Accounts page's and carries neither. **No test asserts this** — it holds by construction (`useSearchParams` is not imported in `NewConnectsTab.tsx`) — and it is DEF-664's deliberate trade, not a defect of this story | — (tracked by **DEF-664**; the namespacing fix is BR-SHL-011's) |

**4 · Test Data** — Tenant **Brazos Bend Utilities** (`brazos`), actor **Dana Whitfield**, System Admin (`dana`); isolation actor **Erin** on **Lone Star Ridge** (`erin`, `lonestar`) — the fixtures `test_w6_connection_list.py` already uses. Rows = B18 §5.4.8's eight, verbatim (state given in the product word, CR-032):

| Connection | Premise | Units | Services | Orders | Target | Waiting on | State |
|---|---|---|---|---|---|---|---|
| CON-26-0110 | 3450 Oak Ridge Dr | 1 | E W | 5 of 5 | Aug 14 | — | `activated` |
| CON-26-0119 | 77 Foundry Row | 1 | E W G | 5 of 9 | Sep 08 | permit | `on_hold` |
| CON-26-0121 | 14 Willow Bend | 1 | E W | 2 of 5 | Sep 15 | materials | `in_progress` |
| CON-26-0126 | 8 Quarry Lane | 1 | E W G | 3 of 9 | Sep 22 | inspection | `partly_activated` |
| **CON-26-0117** | **500 Main Street** | **25** | E W S T **+1** | **5 of 7** | Sep 30 | inspection | `partly_activated` |
| CON-26-0128 | 240 Sable Court | 1 | E W | 2 of 5 | Oct 02 | — | `partly_activated` |
| CON-26-0124 | 12 Harbour View | 1 | E W B | 0 of 7 | Oct 12 | — | `requested` |
| CON-26-0122 | Kestrel Park ph. 2 | 12 | E W S | 1 of 6 | Nov 01 | site access | `in_progress` |

**`CON-26-0117` is the batching proof and must stay in the seed exactly as it is: 25 units, 5 services, and SEVEN orders** (B18 §5.4.8 — *"a lane that produces 76 has broken §8"*). It links back to `SR-26-0043`. Search fixtures: `Foundry` (premise), `SR-26-0043` (request #), the applicant name on that request. Free-text fixture for OQ-375: a ninth build waiting on **`"site inspection"`**, which the `WAITING ON INSPECTION` tile does **not** count — it reads 2, not 3. ⛔ **The eight rows are not seeded yet** — §5.4.8's seed is a data lane's task (B18 §11 W6) and is not part of this story.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| `CONNECTION` | S86 col 1 (identity) | B18 §5.4.2 | `connections.connection_no` | text | system-derived | series already in the catalog (§5.4.6) |
| `PREMISE` | S86 col 2 | B18 §5.4.2 | `premises.address_line` → falls back to `.name` → falls back to `.premise_no` | text | computed-display | never blank — three fallbacks |
| `UNITS` | S86 col 3 | B18 §5.4.2 (the `UNITS AWAITING…` caption) | `COUNT(DISTINCT connection_services.unit_id) WHERE unit_id IS NOT NULL`, grouped once for the whole page | int | computed-display | per-premise services (`unit_id` NULL) excluded, never counted as a unit |
| `SERVICES` | S86 col 4 | B18 §5.4.2 · §5.4.9 (`E W S T +1`) | `connection_services.service`, in `service_progress()`'s sorted order | enum list | computed-display | the **`+N` overflow is the SCREEN's** (`SERVICE_BADGE_LIMIT = 4`, read off the drawing); the server sends the whole set |
| `ORDERS` | S86 col 5 | B18 §5.4.2 (*"`5 of 9` over an accent progress underline"*) | `work_orders` via `connections.order_progress()` → `{done, total}` | int/int | computed-display | **no ratio is computed server-side**; the percentage is a width and is `aria-hidden` |
| `TARGET` | S86 col 6 | B18 §5.4.2 | `connections.target_activation` | date | user-input | nullable → `—`, and sorts last |
| `WAITING ON` | S86 col 7 | B18 §5.4.2 | `connections.waiting_on` | **free text** | user-input | ⛔ **unconstrained `TextField`** — §5.4 enumerates eight reasons and none is enforced (**OQ-375**) |
| `STATE` | S86 col 8 | B18 §5.4.3 (seven states, per service) | `connections.connection_state(row)` — the **DERIVATION**, never the cached `connections.state` column | enum | computed-display | tone (`success`/`warning`/`neutral`) is the **SCREEN's**; B18 draws none for this column |
| `APPLICANT` / `REQUEST #` | S86, declared **off by default** | not drawn as columns; §5.4.2 names both as SEARCH legs | `customers.service_requests.applicant_name` / `.request_no`, via the declared FK `connections.service_request_id` (⚠ cross-module READ, B2 §2) | text | computed-display | carried so a search hit is explicable; the column chooser turns them on |
| KPI `open` · `waiting_on_inspection` · `partly_activated` | S86 strip | B18 §5.4.1 | aggregates over the **cached** `connections.state` column (+ `waiting_on__iexact`) | int | computed-display | §7 |
| KPI `units_awaiting_activation` | S86 strip | B18 §5.4.1 (*"42 across the 7 open builds"*) | Σ per-build distinct `connection_services.unit_id` over OPEN builds | int | computed-display | ⚠ **GAP — the LABEL and the ARITHMETIC disagree.** 42 counts every unit of an open build, including already-live units of a partly-activated one; the *awaiting* reading is not computable from anything signed. The arithmetic wins and the divergence is REPORTED, not reconciled |
| KPI `oldest` | S86 strip | B18 §5.4.1 (*"19 days · CON-26-0119 · waiting on permit"*) | `Coalesce(connections.submitted_at, connections.created_at)`, earliest OPEN build; days + `connection_no` + `waiting_on` served together so the tile needs no second call | int/text | computed-display | `None` when nothing is open — never `0` |
| Segment strip | S86 toolbar | B18 §5.4.2 · §5.4.9 | ⛔ **GAP — no column, no function, no table.** `SEGMENTS_DRAWN_BUT_UNSERVED` is carried **only** so the screen can disable the four by name | — | — | **OQ-371** |
| Column preference key | S86 | BR-SHL-013 | `user_preferences` key `table.S86.columns` (`TableConfig.screenId = "S86"`) | jsonb | system-derived | identity column unhideable |
| Page / search state | S86 | BR-SHL-011 · **DEF-664** | ⛔ **GAP — nowhere.** Component state only; no query string is read or written | — | user-input | does not survive a reload |
| Audit | — | CLAUDE.md #7 | **none — no money action and no write on this screen** | — | — | read-only surface |

**6 · Acceptance**

- **Given** §5.4.8's eight builds, **When** a dispatcher opens the New connects tab, **Then** the eight drawn columns render every row, `CON-26-0117` reads `5 of 7` over 25 units, and the strip reads **7 · 2 · 3 · 42 · 19 days**.
- **Given** a build with no target date, **Then** it renders `—` and sorts **last**, and no column offers a sort control.
- **Given** any of the four unserved segments, **Then** the tab renders it **visible, disabled and carrying the server's own sentence**, the screen never calls the route to find that out, and no code path anywhere maps a state to a segment.
- **Given** a cached state that has drifted, **Then** the ROW shows the derivation while the TILE shows the cache, and the two are asserted separately.
- **Given** a garbage `page`/`per`, **Then** the list clamps and answers; **given** a failed read, **Then** the error state renders and the empty state does not.
- **Given** an empty tenant, **Then** `OLDEST` says *"None open"* and the empty state's CTA is disabled with its reason.
- **Given** a Lone Star Ridge session, **Then** neither a row nor a tile of Brazos Bend's is reachable.
- **Given** any further work on this story, **Then** OQ-371 is **not** answered by choosing a value (prime directive).

**7 · Finance Calculation** — **N/A. No money appears on S86.** B18 §9's money map puts the connection quote on **S87 step 7** (`$14,435.00`, BR-MET-113/116), not on the worklist, and no column, tile or payload field on this screen carries a currency.

What this screen *does* compute is the **five drawn tiles**, and because §5.4.1 defines no formula they are worked here against §5.4.8's eight rows — the same discipline a money formula would get:

```
open                      = |{c : c.state ∉ {activated, cancelled}}|
                          = 8 rows − 1 activated (CON-26-0110) − 0 cancelled          = 7   ✔ drawn 7
waiting_on_inspection     = |{c ∈ open : lower(c.waiting_on) = 'inspection'}|
                          = CON-26-0126 + CON-26-0117                                 = 2   ✔ drawn 2
partly_activated          = |{c : c.state = partly_activated}|
                          = CON-26-0126 + CON-26-0117 + CON-26-0128                   = 3   ✔ drawn 3
units_awaiting_activation = Σ over OPEN builds of |distinct connection_services.unit_id|
                          = 1 + 1 + 1 + 25 + 1 + 1 + 12                               = 42  ✔ drawn 42
                            (CON-26-0110's single unit excluded — that build is finished)
oldest                    = min(coalesce(submitted_at, created_at)) over OPEN builds
                          → 19 days · CON-26-0119 · permit                                  ✔ drawn
```

⚠ **`units_awaiting_activation` is the one that does not foot to its own caption**, and the arithmetic is shipped rather than the label: 42 counts every unit of an open build, including units of `CON-26-0117` that are already live. Nothing published says how many of its 25 are activated, so the *awaiting* reading is **not computable from anything signed**. **GT ref: none** — no golden test applies; these are not money figures.

**8 · Open Questions**

| OQ | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| OQ-371 | **When a connection is both `Partly activated` and waiting on something, which list segment holds it?** `CON-26-0126` satisfies `Waiting` and `Partly energised` at once and the strip is exclusive. (A) waiting wins · (B) state wins · (C) the segments are filters, not a partition. | **S86's segment strip only.** The list, the eight columns, the five tiles, the search, the sort and the pagination are all built and shipped; four of five tabs are disabled with the server's sentence | Product Owner (chat session) | **OPEN — blocking** |
| OQ-375 | **Is `waiting_on` an eight-value vocabulary, a tenant-extensible lookup, or free text?** One clerk typing *"site inspection"* makes the drawn `WAITING ON INSPECTION 2` read **1**, with nothing visibly wrong on any screen and no gate able to see it. | The **accuracy of a drawn KPI**; nothing structural. The column and the tile ship | Product Owner (chat session) | **OPEN — non-blocking, and the tile is wrong while it is open** |
| — *(no OQ minted by this story)* | Every gap S86 carries already has an id. **This story mints nothing, deliberately:** naming an id that no register row answers is the failure `J26` avoided when it wrote `stories: []` rather than cite a story that does not exist. | — | — | — |
| ⛔ **OWED, no id** | **`units_awaiting_activation`'s label and its arithmetic disagree** (§7). Either the tile is re-captioned *"units on open builds"*, or the design states how a partly-activated build's already-live units are excluded — which needs a per-unit activation fact nothing publishes today. | Nothing — the drawn figure ships | Product Owner (chat session), via a register row this lane may not write | **REPORTED — a register row is OWED** (`connection_reads.py` §2 filed the same finding) |
| ⛔ **OWED, no id** | **The same refusal behaves two ways on two sibling worklists.** `GET /connections?segment=waiting` surfaces as a **≥500** (`test_w6_list_endpoint_refuses_a_segment_it_was_never_told_how_to_build` asserts `status_code >= 500`), while `GET /disconnects?segment=at_notice` is caught and translated into a readable `ValidationError` with `message_key="customers.disconnects.segment.unavailable"` (US-CUS-028). One unruled-segment problem, two different answers to a client asking for a tab the screen was told not to offer. | Nothing today — **both screens disable their tabs client-side, so neither refusal is reachable through the UI.** It becomes reachable the moment anything calls the API directly | Product Owner / Eng Lead, via a **defect** row this lane may not write | **REPORTED — a defect row is OWED** (found while writing this story, 2026-08-25) |
| **DEF-664** *(a defect, not a question)* | An embedded tab owns no query string, so page and search do not survive a reload and cannot be shared. The fix is **namespacing the list params, which is BR-SHL-011's to settle, not a lane's**. | Shareability of S86's list state | already filed | **FILED — the embed's trade, accepted and stated** |

---

## What B18 draws that the code does NOT do — S86

| B18 draws | Built? | Tracked by |
|---|---|---|
| §5.4.2 five exclusive segments | **No — one served**; four disabled with the server's sentence | **OQ-371** (OPEN) |
| §5.4.1 `UNITS AWAITING ENERGISATION` as *awaiting* | **No** — the figure is *units on open builds*; the label is not computable | **OWED, no id** (REPORTED) |
| §5.4 eight `waiting_on` reasons as a vocabulary | **No** — free text; the tile matches one literal word | **OQ-375** (OPEN) |
| §5.4.9 `+ New connect` primary → S87 | **No** — no wizard route; the empty-state CTA is disabled with the reason | BR-SHL-010 / law 2 · **S87 out of scope** |
| §5.4.9 `Export` | **No** — `POST /exports` registers no `connections` resource | BR-SHL-010 |
| `NCT-02` / S88 detail, reachable from a row | **No** — no route; **no actions column at all** | law 2 · **S88 out of scope** |
| `New Connect ⁷` superscript tab count | **No** — `PageHeaderTab` has no count slot | another lane's file |
| A shareable / reloadable list URL (BR-SHL-011 *"shareable"*) | **No** — embedded tabs own no query string | **DEF-664** |
| §5.4.2's own search placeholder in the box | **No** — the key would render raw; the shared *"Search this list"* is used | locale lane (key REPORTED) |
| §5.4.8's eight seeded rows | **No** — the seed is a data lane's task | B18 §11 W6 (data) |
