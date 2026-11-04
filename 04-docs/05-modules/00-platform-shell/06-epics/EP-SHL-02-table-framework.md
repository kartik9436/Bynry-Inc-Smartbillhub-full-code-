# EP-SHL-02 — Shared table framework (IS-2…IS-6 + IS-9)

**Module:** platform-shell · **Wave:** W0 · **Screens:** no own S-number — the framework component every list screen consumes (S14, S15, S17, S25, S30, S33, S34, S37, S45, S49, S108 among others) · **Status:** draft

## Scope
**In:** the single reusable table component implementing B9 IS-2 (server pagination + sorting), IS-3 (per-list search), IS-4 (filters with URL persistence), IS-5 (dynamic column chooser — **interim ⋮ spec; visual polish blocked on OQ-013**), IS-6 (row action dropdowns + multi-select with dark bulk bar), and IS-9 (CSV export), composing A18 states (via EP-SHL-04 components). Configuration is declarative: each screen's epic declares a capability-matrix row (B9), and the framework renders exactly that — no bespoke tables.
**Out:** every screen's actual columns/filters/actions (owned by the consuming module's epic), the modals actions open (consuming modules), A18 component internals (EP-SHL-04), preference storage internals (EP-SHL-05 — consumed here), money math of any kind (framework displays server-provided values only).

## Capability matrix (list screens only — B9 conformance)
The framework **defines the row vocabulary**; normative rows live in each consuming module's epic. Illustrative example only (non-normative — the accounts module owns the real row):

| Screen | Search fields | Filters | Default sort | Sortable | Columns default/available | Row actions | Bulk actions | Export |
|---|---|---|---|---|---|---|---|---|
| *S17 Accounts (example)* | account_no, name | status, class, service | balance desc | account_no, name, balance, status | 7 default / 12 available | per row state | reminder, export | CSV |

## Stories

---
id: US-SHL-006
epic: EP-SHL-02
module: platform-shell
screens: [S17, S25, S30, S33, S34]
wave: 0
status: draft
blocked_by: []
depends_on: [US-SHL-011]
journeys: []
rules: [BR-SHL-010, BR-SHL-011, BR-SHL-012]
golden_tests: []
finance_calc: none
---
### US-SHL-006 — Table core: server pagination, sorting & per-list search

**1 · Details** — As a staff user on any list screen (Accounts S17, Reads S25, Bills S30, Payments S33, Outstandings S34, …), I want tables that page, sort, and search on the server per one shared standard, so that 3,000-connection datasets stay fast and every list behaves identically. Entry: any list screen renders the framework with its capability-matrix config. Mechanics are IS-2 (page sizes 50/100/200/500/1000, default 50 — PO 2026-08-09, click-header sort with direction toggle, stable secondary sort by id, sorted column indicated) and IS-3 (server-side, 300 ms debounce, min 2 chars, declared fields only, ✕ clears) — declared here as conformance, not restated. States compose A18: loading skeleton while fetching, zero-results-after-filter, failed-with-retry; the consuming screen supplies its own empty-list copy/CTA. Exit: row navigation/actions per the consuming screen. A11 confirms server-side pagination for the large lists.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| BR-SHL-010 | One framework, no bespoke tables: every list screen must render through the shared component, configured declaratively from its epic's capability-matrix row (search fields, filters, default sort, sortable set, columns, actions, export). A list capability absent from the matrix row is not rendered. | PROPOSED — derived from B9 preamble ("defined ONCE… screens declare conformance via a capability-matrix row") |
| BR-SHL-011 | URL state contract for all framework state: `q` (search), `sort`/`dir`, `page`/`per`, and `f.‹name›=` per filter (IS-4 requires URL persistence). URLs are shareable/bookmarkable and restore full state. Unknown params are ignored; invalid values (bad sort field, out-of-range page, per not in 50/100/200/500/1000 — PO 2026-08-09) fall back to defaults or clamp — never an error screen. | PROPOSED — IS-4 mandates URL persistence; the param grammar and fallback behavior are derived |
| BR-SHL-012 | State composition: the framework owns loading-skeleton (6–10 rows), zero-results-after-filter, and failed-with-retry rendering (A18 §2–4 via EP-SHL-04 components); the consuming screen supplies only empty-list copy + create action (A18 §1). An empty table header with zero rows must never render. | CONFIRMED — A18 §1–4 (composition split PROPOSED, derived from A18's shared-pattern intent) |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Open S17 Accounts (60 Silver Creek accounts seeded) | 50 rows + pager "1–50 of 60" (default 50, PO 2026-08-09); page-size options 50/100/200/500/1000; default sort per the screen's matrix row with the sorted column visually indicated |
| TC-2 | Click the "Balance" header twice | Sort toggles asc→desc; ties broken by id (stable); URL carries `sort=balance&dir=desc` |
| TC-3 | Type "Delgado" in the list search | One debounced request after 300 ms; only declared search fields queried; rows filter to Maria Delgado's account; ✕ clears and restores |
| TC-4 | While fetching page 2 | Skeleton rows render (6–10 grey bars), never a bare spinner; rows replace skeleton on load |
| TC-5 (negative) | Load URL `?page=999&per=37&sort=nonsense` | Page clamps to the last real page, `per` falls back to 50 (PO 2026-08-09), sort falls back to the screen default; list renders normally, no error |
| TC-6 (negative) | List endpoint returns 500 | A18 §4 failed card with Retry; Retry re-issues the identical query |
| TC-7 (isolation) | Seed 60 Silver Creek + 40 Harbor Point accounts; open S17 in each tenant context | Silver Creek session totals 60, Harbor Point 40; automated test asserts no row id from the other tenant ever appears in any page/sort/search permutation |

**4 · Test Data** — Silver Creek: 60 accounts A-10401…A-10460 (balances $0.00–$1,240.55, incl. A-10432 Maria Delgado $148.63); Harbor Point: 40 accounts A-20951…A-20990. Search terms: "Delgado", "A-104". URLs per TC-5.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| `q`, `sort`, `dir`, `page`, `per` | all list screens | B9 IS-2/IS-3/IS-4 | none (URL state → list-endpoint params per A11) | text/int | user-input | per BR-SHL-011 fallbacks |
| Framework config (per screen) | all list screens | that screen's capability-matrix row | none (declarative config, doc-sourced) | — | reference-data | must match the epic's matrix row |
| Row data | all list screens | consuming module's spec | consuming module's B2 tables (read-only here) | — | computed-display | rendered as provided; money cells tabular numerals (A12) |

**6 · Acceptance** — Given S17 is seeded per §4, When Alex pages, sorts by balance, and searches "Delgado", Then each interaction issues one server request, the URL always reflects the full state and restores it on paste in a fresh session, skeletons cover loading, and the isolation suite proves no cross-tenant row in any permutation.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---
id: US-SHL-007
epic: EP-SHL-02
module: platform-shell
screens: [S17, S30, S33, S34]
wave: 0
status: draft
blocked_by: []
depends_on: [US-SHL-006, US-SHL-013]
journeys: []
rules: [BR-SHL-011, BR-SHL-013]
golden_tests: []
finance_calc: none
---
### US-SHL-007 — Filters with URL persistence & dynamic column chooser

**1 · Details** — As a staff user, I want AND-combined filters shown as clearable chips with the whole state in the URL, and a per-table column chooser whose choices follow me, so that I can share exact views with a colleague and shape wide tables (S34 Outstandings is the widest) to my work. Filters per IS-4 (declared per screen, AND-combined, chips + clear-all, URL-persisted). Columns per IS-5: show/hide + reorder, per-user persisted, identity column always visible, export follows the visible set — **interim visual spec: ⋮ menu top-right of the table header; final pattern pending design (OQ-013 — polish only, build proceeds on the interim spec per the OQ registry)**. Entry: any list screen with filters/columns declared. Exit: state persists in URL (filters) and `user_preferences` (columns, via US-SHL-013).

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| BR-SHL-011 | *(shared with US-SHL-006)* URL state contract incl. `f.‹name›=` filter params; graceful fallback on unknown/invalid values. | PROPOSED — see US-SHL-006 |
| BR-SHL-013 | Column preferences persist per (user, tenant, screen) in `user_preferences` key `table.‹screen›.columns` — an ordered array of visible column keys. The identity column (declared in the screen's matrix row) cannot be hidden (its hide control renders disabled). A "Reset to default" restores the matrix-row default set. Preferences never widen data access — they only hide/show columns the screen already serves. | PROPOSED — IS-5 confirms per-user persistence + identity-column lock; key scheme, tenant scoping, and reset derived (storage via EP-SHL-05) |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | On S34, apply filters Age bucket = "60+" and Class = "Residential" | Rows match both (AND); two chips render with a clear-all; URL carries `f.age=60plus&f.class=residential` |
| TC-2 | Copy that URL, open in a fresh session (same tenant, same role) | Identical filters, chips, page, and sort restore from the URL alone |
| TC-3 | Open the ⋮ column menu on S34, hide "Credit tier", move "Balance" first | Table re-renders instantly; after sign-out/sign-in the arrangement persists (read from `user_preferences`) |
| TC-4 (negative) | Attempt to hide the identity column (Account #) | Control is disabled; column remains visible |
| TC-5 (negative) | Load URL with `f.bogus=1` | Unknown filter ignored; remaining state applies; no error |
| TC-6 | Click "Clear all" on the chips | All filters removed, `f.*` params dropped from the URL, full result set returns |
| TC-7 (isolation) | Jordan hides columns on S34 in Silver Creek; Alex opens S34 in Silver Creek; Alex opens S34 in Harbor Point | Jordan's prefs never affect Alex (per-user); Alex's Silver Creek arrangement does not apply in Harbor Point (per-tenant row scoping) |

**4 · Test Data** — S34 seeded with 184 outstanding accounts (per prototype), incl. A-10432 ($148.63, 30–60 bucket, Residential) and A-10457 ($1,240.55, 60+, Commercial). Column set default: Account # · Name · Balance · Age · Class · Last payment · Credit tier. Preference row: `(user: jordan, tenant: silvercreek, key: 'table.S34.columns', value: ["balance","account_no","name","age","class","last_payment"])`.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Filter values `f.*` | all list screens | B9 IS-4 | none (URL state → list-endpoint params) | text | user-input | must be a declared filter; else ignored |
| Visible-column set + order | all list screens | B9 IS-5 | PROPOSED-SCHEMA `user_preferences.value` key `table.‹screen›.columns` | jsonb array of column keys | user-input | subset of the screen's available columns; identity column always included |
| Column-chooser trigger (⋮) | all list screens | B9 IS-5 interim spec | none | — | computed-display | placement interim until OQ-013 |

**6 · Acceptance** — Given S34 is seeded per §4, When Jordan filters to 60+/Residential, hides Credit tier, and shares the URL with Alex, Then Alex sees the same filtered rows (URL state) but his own column arrangement (user-scoped prefs), And Jordan's arrangement survives sign-out and never leaks to another tenant or user.

**7 · Finance Calculation** — N/A.

**8 · Open Questions**

| OQ-ID | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| OQ-013 *(pre-existing — referenced, not minted here)* | IS-5 dynamic-columns visual pattern | Visual polish only — interim ⋮ spec unblocks build (per OQ registry) | Product Owner (chat session) + design | CLOSED (→ BR-SHL-027; epic cell synced 2026-08-09) |

---
id: US-SHL-008
epic: EP-SHL-02
module: platform-shell
screens: [S33, S34, S30, S31.3]
wave: 0
status: draft
blocked_by: []
depends_on: [US-SHL-006, US-SHL-014]
journeys: []
rules: [BR-SHL-014, BR-SHL-015, BR-SHL-016]
golden_tests: []
finance_calc: none
---
### US-SHL-008 — Row actions, bulk selection bar & CSV export

**1 · Details** — As a staff user, I want per-row action dropdowns, multi-select with the dark bulk-action bar (live count + running $ total on money tables — Payments S33, Outstandings S34, Run Bills case tables S31.3), and CSV export, so that batch work (reminders, write-offs, exports) is one motion instead of row-by-row. Behavior per IS-6 (row dropdown options vary by row state per A2; header checkbox + dark inverted bar; destructive/money actions: modal → explicit confirm → toast → `audit_log`; role-forbidden actions disabled-with-reason — gating detail in US-SHL-014) and IS-9 (export respects current filters + visible columns, money 2dp, UTF-8, filename `‹screen›-‹tenant›-‹YYYYMMDD›.csv`) — conformance, not restated. The framework renders the actions and invokes the consuming screen's handlers; the modals and their writes belong to the consuming modules.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| BR-SHL-014 | Selection semantics: the header checkbox selects the **current page**; selection persists while paging within the same query state (q/filters/sort); any change to q or filters clears the selection (the selected set may no longer match); the bulk bar shows the live count and offers "Clear selection". | PROPOSED — IS-6 defines the bar and count; cross-page behavior underivable from the prototype, derived from least-surprise |
| BR-SHL-015 | The running $ total on money tables is a **display-only** sum of the selected rows' server-provided amounts, rendered at 2 dp with tabular numerals; it performs no rounding decision and is never written anywhere (money math is B4-owned; CLAUDE.md "do not touch"). | PROPOSED — IS-6 names the running total; display-only constraint derived from CLAUDE.md hard rules 2/4 |
| BR-SHL-016 | CSV export executes server-side under the caller's tenant context (RLS) as a synchronous streamed download honoring the IS-9 contract; requests over 50,000 rows are rejected with "Narrow your filters to export." Exports from money tables (S30, S33, S34) write an `audit_log` row (who, screen, filter state, row count). | PROPOSED — IS-9 defines the contract; execution mode, size guard, and export auditing derived (audit extends CLAUDE.md rule 7's spirit to bulk money reads) |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | On S33, select 3 payments ($247.30, $89.10, $412.00) | Dark inverted bar appears: "3 selected · $748.40"; per IS-6 styling |
| TC-2 | Page to page 2 (same filters), select 2 more, return to page 1 | Bar reads "5 selected"; page-1 selections still checked |
| TC-3 | Change a filter while 5 rows are selected | Selection clears; bar disappears |
| TC-4 | Open a row's action dropdown on S34 for a 60+ account vs a current account | Option sets differ by row state (per A2 declarations of the consuming screen) |
| TC-5 | Export S34 filtered to 60+/Residential with "Credit tier" hidden | File `outstandings-silvercreek-20260808.csv`, UTF-8, only visible columns, only filtered rows, money at 2 dp; an `audit_log` row records the export |
| TC-6 (negative) | Trigger a bulk write-off and dismiss the confirm modal (Esc) | No action executes, no toast, no `audit_log` write, selection unchanged |
| TC-7 (negative) | Export request that would return 62,000 rows | Rejected with "Narrow your filters to export."; no file download starts |
| TC-8 (isolation) | Run the S33 export in a Silver Creek session while Harbor Point payments exist | CSV contains zero Harbor Point rows; automated test diffs exported ids against tenant ownership |

**4 · Test Data** — S33 Silver Creek: payments PMT-88213 $247.30 (ACH), PMT-88214 $89.10 (Card), PMT-88215 $412.00 (Check), 30 more across two pages; Harbor Point: 12 payments. S34: 184 outstanding accounts per US-SHL-007 §4. Export date 2026-08-08 → filename `outstandings-silvercreek-20260808.csv`.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Row/bulk selection set | money + multi-select lists | B9 IS-6 | none (client state) | array of row ids | user-input | cleared on query-state change (BR-SHL-014) |
| Running $ total | S33/S34/S31.3 bulk bar | B9 IS-6 | none — sum of served `payments.amount` / `accounts.balance` values | display currency, 2 dp | computed-display | display-only; tabular numerals (A12) |
| Export file | list screens with Export | B9 IS-9 | none (streamed from the screen's B2 tables under RLS) | CSV UTF-8 | system-derived | filename `‹screen›-‹tenant›-‹YYYYMMDD›.csv`; ≤50,000 rows |
| Export audit entry | money-table exports | derived (BR-SHL-016) | `audit_log` (append-only) | jsonb detail | system-derived | who/screen/filters/row-count |

**6 · Acceptance** — Given S33 is seeded per §4, When Jordan selects three payments, Then the dark bar shows "3 selected · $748.40"; When she exports the filtered S34 view, Then the CSV matches visible columns + active filters at 2 dp with the specified filename and an audit row exists; And no export or selection ever includes another tenant's rows.

**7 · Finance Calculation** — N/A (the running total and CSV money values are display-only renderings of server-provided amounts; no rule from B4 is exercised).

**8 · Open Questions** — None.
