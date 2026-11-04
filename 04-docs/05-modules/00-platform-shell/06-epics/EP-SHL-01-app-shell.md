# EP-SHL-01 — App shell

**Module:** platform-shell · **Wave:** W0 · **Screens:** shell chrome (no own S-number; hosts S7–S48 and every authenticated screen) · **Status:** draft

## Scope
**In:** the authenticated frame every module renders inside — collapsible left sidebar (240px expanded / 64px collapsed, persisted per user), topbar (breadcrumb/title, global search across accounts/premises/bills/payments, notifications bell), sidebar footer user block opening the S48 user menu. Routing model per A9 / 04-docs/README §Global Layout (nested routes, per-module sub-state in URL).
**Out:** the public screens (S1–S6, S110–S114 — tenancy/identity modules), the content each module renders inside the frame, the table framework (EP-SHL-02), toasts (EP-SHL-04), the storage layer for preferences (EP-SHL-05 — consumed here), auth/session issuance (identity module).

## Capability matrix (list screens only — B9 conformance)
N/A — the shell owns no list screens. Conformance rows are declared by each consuming module's epic. The global-search results popover is a grouped quick-picker, not a list screen; its behavior is specified in US-SHL-003 (mechanics inherit IS-3).

## Stories

---
id: US-SHL-001
epic: EP-SHL-01
module: platform-shell
screens: [shell-chrome, S7, S8, S17, S30, S36, S49]
wave: 0
status: draft
blocked_by: []
depends_on: [US-SHL-013]
journeys: []
rules: [BR-SHL-001, BR-SHL-002, BR-SHL-003]
golden_tests: []
finance_calc: none
---
### US-SHL-001 — Collapsible sidebar navigation

**1 · Details** — As any staff user (System Admin, Billing Clerk, Executive), I want a collapsible left sidebar listing the app's modules in the canonical order, so that I can move between modules and reclaim horizontal space on dense tables. Entry: every authenticated route renders inside the shell. Exit: clicking an item routes to that module's default view. Order **as twice amended — CURRENT (PO rulings 2026-08-10 and 2026-08-16 / prototype r10, CR-003): Dashboard · Plans & Rates · Premises · Assets · Accounts · Reads · Billing · Payments · Work · Finance · Reports · Settings** — twelve items. Settings moved SECOND→LAST (2026-08-10); Premises and Assets swapped and **Work** was inserted before Finance (2026-08-16). Work resolves to a not-built-yet screen; the module is OQ-249. Sections with sub-areas show an expandable submenu (Plans & Rates: Plans/Rates/Charge Codes/Taxes & Fees; Premises: Premises/Units; Reads: Reads/Routes/Cycles; Payments: Summary/Record payments/Outstandings; Finance: its five tabs); Billing is a tabbed page with **no** submenu (04-docs/README §Screens 10). Collapsed shows inline-SVG icons only (A12: no icon font). The toggle persists per user (storage via US-SHL-013). Screens cited: shell chrome hosting S7 (Dashboard) through every module screen; S49 Assets list as the Assets target.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| BR-SHL-001 | Sidebar is ~240px expanded / ~64px collapsed with a toggle; item order **as amended THREE times is Dashboard, Plans & Rates, Premises, Assets, Accounts, Reads, Billing, Payments, Work, Finance, Runbooks, Reports, Settings — THIRTEEN items** (Settings SECOND→LAST per PO 2026-08-10; Premises/Assets swapped and Work inserted per PO 2026-08-16 + prototype r10, CR-003; **Runbooks inserted above Reports per PO 2026-09-06, *“Nav bar will have Runbook as menu item - above reports module.”*, CR-075**). ⚠ **This row read *“as twice amended … twelve”* until 2026-09-06.** Runbooks resolves to the not-built-yet screen until `RBS-001` lands in `CR-075` wave D, and the hold ships with the test that fires when it expires (`navHoldExpiry.test.tsx`). Sections with sub-areas expose expandable submenus; Billing has none. Icons are inline SVG using currentColor. | CONFIRMED — 04-docs/README §Global Layout & Navigation, A9, A1 addendum r4 (Assets), A12 §Icons |
| BR-SHL-002 | The collapsed/expanded state persists per user **and per tenant**, server-side, in `user_preferences` key `shell.sidebar_collapsed` (boolean); default expanded on first login; applied on shell mount before first paint (no flash of wrong width). | PROPOSED — 04-docs/README §Interactions confirms "persists"; storage location and tenant scoping derived from EP-SHL-05 `user_preferences` design |
| BR-SHL-003 | Sidebar items a role has no access to are hidden (A18 §6 "nav item is hidden where possible"); a direct deep-link to a hidden module renders the A18 §6 permission-denied block with no data behind it. Per A4 addendum: Billing Clerk sees no Settings and no Finance; Executive sees all items. | CONFIRMED — A18 §6, A4 addendum (2026-08-07) |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Alex Reed clicks the sidebar toggle on S7 | Sidebar animates 240→64px; labels hidden; icons remain; toggle again restores 240px |
| TC-2 | Alex collapses the sidebar, signs out, signs back in | Sidebar renders collapsed on first paint (pref read from `user_preferences`, no width flash) |
| TC-3 | Alex navigates to /billing | Billing item shows the active highlight; previously active item loses it |
| TC-4 | Jordan Blake (Billing Clerk) signs in | Settings and Finance items are absent from the sidebar; all other nine items render |
| TC-5 (negative) | Jordan deep-links to /finance | A18 §6 block: "You don't have access to this." + helper + "Back to Dashboard"; no Finance data fetched or rendered behind it |
| TC-6 (isolation) | Alex holds memberships in Silver Creek Utilities and Harbor Point Water; he collapses the sidebar while in Silver Creek, then switches to Harbor Point | Harbor Point session shows the default (expanded) state — the preference row is scoped (user_id, tenant_id) and does not leak across tenants |

**4 · Test Data** — Tenant A: Silver Creek Utilities, subdomain `silvercreek.smartbillhub.app`, tenant_id `0198a3f2-4b7d-7c31-9e42-8d1f6a2b3c01`. Tenant B: Harbor Point Water, `harborpoint.smartbillhub.app`, tenant_id `0198a3f2-9d02-7a15-b7c8-4e5f6a7b8c02`. Users: alex.reed@silvercreekutilities.com (System Admin in Silver Creek, Billing Clerk in Harbor Point), jordan.blake@silvercreekutilities.com (Billing Clerk). Preference row: `(user_id: alex, tenant_id: silvercreek, key: 'shell.sidebar_collapsed', value: true)`.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Sidebar collapsed state | shell chrome | 04-docs/README §Interactions ("persists collapsed/expanded") | PROPOSED-SCHEMA `user_preferences.value` under key `shell.sidebar_collapsed` (see US-SHL-013) | boolean (jsonb) | user-input | true/false only |
| Nav item visibility per role | shell chrome | A4 addendum matrix | computed from `roles`/`role_permissions` via `tenant_memberships.role_id` | — | computed-display | hidden when role lacks module access |
| Active module highlight | shell chrome | prototype-extracted (sidebar active state) | none (route-derived) | — | computed-display | matches current route's module |

**6 · Acceptance** — Given Alex is signed in to Silver Creek with the sidebar expanded, When he clicks the toggle and then reloads the app, Then the sidebar renders at 64px on first paint, shows icons only, and the eleven items appear in the canonical order; And Given Jordan (Billing Clerk) is signed in, Then Settings and Finance never render in her sidebar and a direct /finance URL shows the permission-denied block.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---
id: US-SHL-002
epic: EP-SHL-01
module: platform-shell
screens: [shell-chrome, S21, S31, S39]
wave: 0
status: draft
blocked_by: []
depends_on: []
journeys: []
rules: [BR-SHL-004]
golden_tests: []
finance_calc: none
---
### US-SHL-002 — Topbar breadcrumb & title

**1 · Details** — As any staff user, I want the topbar to show where I am (breadcrumb/title) derived from the route, so that deep screens (a batch detail, a wizard step, an account tab) stay orientable and shareable. Entry: shell mount; updates on every route change (A9 routing model: `/billing`, `/billing/run?step=`, `/accounts/:id?tab=`, `/finance/deposits/:batchId`, `/reports/:reportName`). Exit: breadcrumb ancestor segments are clickable links back up the hierarchy. Screens cited: shell chrome; depth examples S21 (Accounts › A-10432), S31 (Billing › Run bills), S39 (Finance › Deposits & Bank › Batch DEP-0806).

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| BR-SHL-004 | Breadcrumb pattern: `Module` on a module root; `Module › Sub-context` for tabs, wizards, and details (detail context = the record's human identifier, e.g. account_no, batch id — never a UUID). Ancestor segments are links; the leaf is plain text. The browser tab title mirrors it: `‹leaf› · SMARTBillHub`. Wizard step changes update `?step=` but not the breadcrumb leaf (the wizard name is the leaf). | PROPOSED — 04-docs/README §Global Layout names "breadcrumb/title" without a pattern; hierarchy derived from the A9 routing model and prototype page headers |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Navigate to /accounts | Breadcrumb "Accounts"; tab title "Accounts · SMARTBillHub" |
| TC-2 | Open account A-10432 (S21) | Breadcrumb "Accounts › A-10432"; "Accounts" is a link back to the list preserving its prior URL state (IS-4) |
| TC-3 | Enter Run Bills (S31) and advance to step 3 | Breadcrumb stays "Billing › Run bills"; URL carries `?step=3` |
| TC-4 | Open batch detail (S39) from Deposits | Breadcrumb "Finance › Deposits & Bank › DEP-0806"; both ancestors clickable |
| TC-5 (negative) | Deep-link /accounts/0198ffff-dead-7000-a000-000000000000 (no such account in this tenant) | Content region shows the A18 §4 failed pattern ("We couldn't find this account.") with a back action; breadcrumb falls back to "Accounts"; no crash, no blank shell |

**4 · Test Data** — Account A-10432 (Maria Delgado) in Silver Creek Utilities; deposit batch DEP-0806 dated 2026-08-06; bad-id URL as in TC-5.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Breadcrumb segments | shell chrome | 04-docs/README §Global Layout ("breadcrumb/title") | none (route-derived; detail leaf reads the record's display id, e.g. `accounts.account_no`) | text | computed-display | leaf never a raw UUID |
| Browser tab title | shell chrome | derived (BR-SHL-004) | none | text | computed-display | mirrors breadcrumb leaf |

**6 · Acceptance** — Given Alex opens Finance › Deposits & Bank and clicks batch DEP-0806, When the batch detail renders, Then the breadcrumb reads "Finance › Deposits & Bank › DEP-0806" with two clickable ancestors, And the browser tab reads "DEP-0806 · SMARTBillHub", And clicking "Deposits & Bank" returns to the tab with its previous filters intact.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---
id: US-SHL-003
epic: EP-SHL-01
module: platform-shell
screens: [shell-chrome, S14, S17, S21, S30, S33]
wave: 0
status: draft
blocked_by: []
depends_on: [US-MET-001, US-MET-002]
journeys: []
rules: [BR-SHL-005, BR-SHL-006]
golden_tests: []
finance_calc: none
---
### US-SHL-003 — Global search (accounts · premises · bills · payments)

**1 · Details** — As any staff user, I want one topbar search that finds **premises, units, assets, master accounts, regular accounts, customers, bills, payments and service requests** by their everyday identifiers, so that I can jump to a record without knowing which module owns it. ⚠ **AMENDED 2026-09-03 — FOUR GROUPS BECAME NINE** (PO: *"Universal search will search premises , unit assets , master, regular account , customer id, bill, payment, requests - if you have to increase the length of search bar please increase it"*). The search bar is widened to match, and the placeholder no longer lists the groups — nine will not fit and B14 rule 32 caps a description at one sentence, so it names the ACT (*"Search"*) rather than enumerating what is searched. Entry: focus the topbar search on any authenticated screen. Behavior inherits IS-3 mechanics (server-side, 300 ms debounce, min 2 chars, ✕ clears). Results render in a popover grouped by entity; selecting a row deep-links to it; each group has a "View all in ‹module›" link opening the module list (S17 Accounts, S14 Premises, S30 Billing, S33 Payments) with the query applied as its list search. Exit: navigate to a result, press Esc, or click away (popover closes, IS-10 focus rules). Screens cited: shell chrome (search lives in the topbar); deep-link targets S21/S17/S14/S30/S33.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| BR-SHL-005 | **Scope and fields AS AMENDED 2026-09-05 (`CR-073`) — FIFTEEN groups, in this order.** The nine below are unchanged; **six append at 10–15 and nothing is renumbered**: **Work orders** — `work_orders.order_no` (a NULL-numbered order is not findable: no identifier to render, and rule 31 forbids its uuid); **Work order templates** — `work_order_templates.name` **and** `template_no` (NULL until publish, so the NAME is the label and both are searched); **Parts** — `parts.part_no` as an IDENTIFIER and `parts.name` as a DESCRIPTION, so only the number is in the prefix band; **Workforce** — `technicians` (name via `identity.User`, read through a seam) **and** `crews`, ONE group because `Work-023` is one table, opening the crews LIST because only a person has a detail screen; **Plans** — `rate_plans.code` + `name`; **Charge codes** — `charges.code` + `name`. **None of the six carries money**, though two have decimal columns (`BR-RAT-035`: a charge amount is a seed, not a price). Reads and finance were excluded BY NAME by the PO. **The original nine:** **Premises** — `premises.premise_no`, `premises.name`, `premises.address_line`; **Units** — `units.unit_no`, `units.label`; **Assets** — `assets.asset_no`, `assets.serial_no` (BR-AST-026: the uuid is NEVER displayed); **Master accounts** — `accounts.account_no` + primary `contacts.full_name`, `kind='master'`; **Accounts** — the same two fields, `kind='regular'`; **Customers** — `customers.customer_no` (the PO's *"customer id"* is the NUMBER, never the database id); **Bills** — `invoices.invoice_no`; **Payments** — `payments.payment_no`, `payments.confirmation`; **Service requests** — `service_requests.request_no`. Max 5 rows per group, ranked prefix-match-first then most-recently-updated; each row shows identifier + one context line, and money as its stored decimal beside its currency (displayed 2dp by the client, hard rule 2). Zero total results render the A18 §2 pattern ("No results for '‹query›'."). Mechanics per IS-3 — not restated. **Premises is the ONLY group that admits free text** (name + street), and that is signed rather than chosen — it is this rule's own field list, and TC-2 depends on it. ⚠ **Amended 2026-10-29 (`CR-200-BRC10`): units now admit their building's address too, and both groups match word by word — BR-SHL-005 in the module's business rules.** | **CONFIRMED as amended twice** — PO ruling 2026-09-03 (12-governance/02-decision-log.md, commit 275c4afa) superseded the four-group scope; PO ruling 2026-09-05 (`CR-073`) supersedes the nine-group one. `GET /search?q=` is served by `apps/tenancy/search_api.py` and remains a PROPOSED addition to A11 (the addendum row is REPORTED) |
| BR-SHL-006 | Isolation and permission: the search query executes with `app.tenant_id` set and RLS FORCE active; a result set must never contain another tenant's rows — this is release-blocking (test_tenant_isolation class). Entity groups the caller's role cannot view are omitted entirely (per A4 addendum all three roles can view all four entities in v1, but the rule guards future roles). | CONFIRMED — CLAUDE.md hard rule 1, B3 tenancy-and-security, A4 addendum |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Alex types "A-104" | Accounts group lists A-10432 · Maria Delgado · 118 Cedar Ridge Dr (≤5 rows); Enter/click routes to /accounts/{id} (S21) |
| TC-2 | Type "Cedar" | Premises group lists Cedar Ridge Apartments; "View all in Premises" opens S14 with `q=Cedar` applied |
| TC-3 | Type "BL-2608" | Bills group lists invoice BL-2608-018410 ($148.63, A-10432); selecting it opens the bill from S30 |
| TC-4 | Type "PMT-88213" | Payments group lists the $247.30 payment; selecting opens it in S33 context |
| TC-5 (negative) | Type a single character "A" | No request fired (min 2 chars, IS-3); popover shows nothing |
| TC-6 (negative) | Search backend returns 500 | Popover shows the A18 §4 failed pattern with Retry; no stale results shown; retry re-issues the query |
| TC-7 (isolation — mandatory) | Account A-20991 (Dan Okafor) exists only in Harbor Point Water. In a Silver Creek session, search "A-20991" and "Okafor" | Zero results for both; automated isolation test seeds both tenants, runs the search under each tenant context, and asserts no row from the other tenant is ever returned |
| TC-8 | Type "zzzz" | "No results for 'zzzz'." per A18 §2; no create action offered |
| TC-9 (rank — the ratified order, added 2026-09-03) | Two accounts match "A-104": `A-10432` updated a week ago (a PREFIX match) and `B-9A-104` updated a minute ago (a SUBSTRING match) | `A-10432` is FIRST. The rank is prefix-then-recency, so a newer substring match never outranks an older prefix match; and where two prefix matches compete the newer wins. A test that passes under plain-substring or plain-recency ordering is not this test |
| TC-10 (the five new groups, added 2026-09-03) | Type an asset number, a serial number, a customer number, a request number and a master account's number | Each returns its OWN group — Assets, Assets, Customers, Service requests, Master accounts — and a master account never appears in the regular Accounts group |
| TC-11 (rule 31, added 2026-09-03) | Any query returning any row | **No uuid is the visible value of any cell in the popover.** Every row shows a B2 identifier as its label; the record id travels for the deep link only. An asset shows `asset_no`, never its hidden uuid (BR-AST-026) |
| TC-12 (omission, not emptiness — added 2026-09-03) | A role that cannot view payments searches a term that matches a payment | **No Payments group renders at all** — not a heading over zero rows. The group is dropped server-side by `core.search`, so the client is never given it to filter (BR-SHL-006) |

**4 · Test Data** — Silver Creek: account A-10432 (Maria Delgado, 118 Cedar Ridge Dr, Unit 3B), premises "Cedar Ridge Apartments" (24 units), invoice BL-2608-018410 total $148.63, payment confirmation PMT-88213 $247.30 (ACH, 2026-08-05). Harbor Point: account A-20991 (Dan Okafor, 7 Pier Rd), premises "Harborview Flats". Queries: "A-104", "Cedar", "BL-2608", "PMT-88213", "A-20991", "Okafor", "zzzz", "A".

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Search query `q` | shell chrome | 04-docs/README §Global Layout (topbar "global search") | none (transient request param) | text | user-input | min 2 chars; debounced 300 ms (IS-3) |
| Result: account row | popover | B2 customers | `accounts.account_no`, `contacts.full_name`, `premises.address_line` | text | computed-display | tenant-scoped read only |
| Result: premises/unit row | popover | B2 metering | `premises.name`, `premises.address_line`, `units.label` | text | computed-display | tenant-scoped read only |
| Result: bill row | popover | B2 billing | `invoices.invoice_no`, `invoices.total` | text / NUMERIC(18,6) shown 2dp | computed-display | display-rounding only; no write |
| Result: payment row | popover | B2 payments | `payments.confirmation`, `payments.amount` | text / NUMERIC(18,6) shown 2dp | computed-display | display-rounding only; no write |

**6 · Acceptance** — Given both tenants are seeded per §4, When Alex (Silver Creek session) types "Cedar", Then within one debounce interval the popover shows a Premises group containing Cedar Ridge Apartments and an Accounts group containing A-10432, And no Harbor Point row appears; When he presses Enter on A-10432, Then the app routes to that account's detail (S21); And the automated isolation suite proves searches under either tenant context never return the other tenant's rows.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---
id: US-SHL-004
epic: EP-SHL-01
module: platform-shell
screens: [shell-chrome]
wave: 0
status: draft
blocked_by: []
depends_on: []
journeys: []
rules: [BR-SHL-007]
golden_tests: []
finance_calc: none
---
### US-SHL-004 — Notifications bell

**1 · Details** — As any staff user, I want a topbar notifications bell with an unread badge and a popover of recent events, so that things needing my attention (failed payments, unmatched deposits, billing-run exceptions) surface without polling each module. Entry: bell is always visible in the topbar (04-docs/README §Global Layout names "notifications" in the top bar). Exit: selecting a notification deep-links to its subject; mark-all-read clears the badge. **Unblocked (OQ-019 CLOSED → BR-SHL-026):** the v1 event catalog is confirmed — (1) billing run completed/failed · (2) payment failures · (3) approvals waiting · (4) import results with exception counts · (5) integration broken — guiding principle: pending / attention-required items. Read-state persistence, retention, and storage (new table vs extending `notifications`, which remains the customer-delivery log) are story-level Eng mechanics at build.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| BR-SHL-007 | Bell shows an unread-count badge (capped display "9+"), a popover listing recent events newest-first with per-item and mark-all read actions; items deep-link to their subject record; feed is strictly tenant-scoped. Event catalog per BR-SHL-026; read state/retention are Eng mechanics at build. | CONFIRMED (→ BR-SHL-026 event set) |

**3 · Test Cases** *(event catalog per BR-SHL-026)*

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | 3 unread events exist for Silver Creek | Badge shows "3"; opening the popover lists them newest-first |
| TC-2 | Click an event about payment PMT-88213 | Routes to that payment's context; item becomes read; badge decrements |
| TC-3 | Mark all read | Badge clears; items remain listed as read |
| TC-4 (negative) | No events exist | No badge; popover shows "You're all caught up." (empty-state per A18 §1 shape, copy TBD with OQ-019) |
| TC-5 (isolation) | Harbor Point has 5 unread events; Alex opens Silver Creek | Badge and popover reflect Silver Creek only; automated test asserts no cross-tenant event rows |

**4 · Test Data** — Silver Creek events (illustrative pending OQ-019): "Payment failed · A-10432 · $148.63", "Deposit DEP-0806 doesn't match bank · –$100.00", "Billing run 08-A: 11 missing reads". Harbor Point: 5 events on account A-20991.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Unread count | shell chrome | GAP — bell shown in README §Global Layout; no event source specified | GAP (B2 `notifications` is the customer-delivery log, not a staff feed) — OQ-019 | integer | computed-display | badge caps at "9+" |
| Notification item (event type, subject link, read state, timestamp) | shell chrome | GAP | GAP — OQ-019 | — | — | — |

**6 · Acceptance** — Given N unread tenant-scoped events (catalog per BR-SHL-026), When the shell mounts, Then the bell badges N, the popover lists the events newest-first with working deep-links and read actions, and no other tenant's events ever appear.

**7 · Finance Calculation** — N/A.

**8 · Open Questions**

| OQ-ID | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| OQ-019 (CLOSED → BR-SHL-026) | Staff notifications bell: which events feed it (catalog + triggering modules), is read state per-user or per-tenant, what retention/pruning applies, and is it stored in a new table or an extension of `notifications`? | US-SHL-004 (whole story) | Product Owner (chat session) | CLOSED (→ BR-SHL-026; read-state/retention/storage = Eng mechanics at build) |

---
id: US-SHL-005
epic: EP-SHL-01
module: platform-shell
screens: [shell-chrome, S48, S1, S2]
wave: 0
status: draft
blocked_by: []
depends_on: [US-SHL-001, US-IDN-003, US-IDN-008]
journeys: []
rules: [BR-SHL-008, BR-SHL-009]
golden_tests: []
finance_calc: none
---
### US-SHL-005 — Sidebar footer user block & user menu (S48)

**1 · Details** — As any authenticated user (any of the three roles — self-service applies to everyone per A4 addendum 2026-08-07), I want the sidebar footer user block (avatar · name · role) to open the S48 user menu, so that I can manage my own profile, password, and 2FA, and sign out. Entry: click the footer block on any authenticated screen. Menu opens **upward** with: My profile · Change password · Two-factor authentication · Sign out (A1 addendum "User account menu"). The first three open modals (modal shell per A12; focus trap + Esc/✕/backdrop close per IS-10): Change password (current/new/confirm + policy hint + "sign out other sessions"), Two-factor (authenticator app or SMS, QR + 6-digit code), My profile (name, email, phone; role read-only). Sign out returns to the public Pricing/sign-in screens (S1/S2). Exit: modal close → shell; sign out → S1/S2. Auth mechanics (password verify, 2FA enrollment, session revocation) are identity-module services; this story owns the shell surfaces.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| BR-SHL-008 | User block renders avatar (initials derived from `users.full_name` — no avatar upload exists in B2 or the prototype), full name, and the role name for the **current tenant** membership. It is a button opening an upward menu with exactly: My profile, Change password, Two-factor authentication, Sign out — the first three as modals per the A1 addendum field lists; role is read-only in My profile. | CONFIRMED — A1 addendum "User account menu" (2026-08-07), A4 addendum "Self-service account" |
| BR-SHL-009 | Sign out ends the session, clears all tenant context and client caches (no tenant data readable after), and returns to the public Pricing/sign-in screen; subsequent deep-links to authenticated routes redirect to sign-in. | CONFIRMED — A1 addendum ("Sign out (returns to the public Pricing/sign-in screen)"); cache-clearing derived from B3 tenancy hygiene |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Alex clicks the footer block | Menu opens upward with the four items in order; block shows "AR · Alex Reed · System Admin" |
| TC-2 | Open My profile | Modal shows name/email/phone editable, role "System Admin" read-only; Esc closes without saving (IS-10) |
| TC-3 | Open Change password | Fields current/new/confirm, policy hint, "sign out other sessions" toggle present; save with correct current password succeeds with confirmation toast |
| TC-4 (negative) | Change password with wrong current password | Inline field error per A18 §5 on the current-password field; no password changed; modal stays open |
| TC-5 | Sign out | App lands on S1/S2 public screen; pressing Back or deep-linking /dashboard redirects to sign-in; no tenant data renders from cache |
| TC-6 (isolation) | Alex switches to his Harbor Point membership | User block role reads "Billing Clerk" (role is per-membership, not global); profile modal shows the same identity but Harbor Point role |

**4 · Test Data** — alex.reed@silvercreekutilities.com, full_name "Alex Reed", phone +1 (208) 555-0142; System Admin in Silver Creek, Billing Clerk in Harbor Point. Password attempt: current "Wr0ng-pass!" (fails), "Correct-h0rse!" (succeeds). 2FA: authenticator app, code 481-334.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Avatar initials | shell chrome | prototype-extracted (user block) | derived from `users.full_name` | text (2 chars) | computed-display | first letters of first/last name |
| Display name | shell chrome / S48 | A1 addendum | `users.full_name` | text | reference-data | read via identity |
| Role label | shell chrome / S48 | A1 addendum, A4 addendum | `tenant_memberships.role_id` → `roles.name` | text | computed-display | current tenant's membership only |
| Profile name/email/phone | S48 My profile | A1 addendum | `users.full_name` / `users.email` / `users.phone` | text / citext / text | user-input | email format; write via identity service |
| Password fields | S48 Change password | A1 addendum | `users.password_hash` (via identity service only) | — | user-input | policy hint per Settings → Security; never stored client-side |
| 2FA method + code | S48 Two-factor | A1 addendum | identity module (enrollment tables per identity epics) | — | user-input | 6-digit code |

**6 · Acceptance** — Given Alex is signed in to Silver Creek, When he opens the user menu, Then exactly the four A1-addendum items render and each of the three modals opens with its specified fields; When he signs out, Then he lands on the public Pricing/sign-in screen and /dashboard no longer renders without re-authentication.

**7 · Finance Calculation** — N/A.

**8 · Open Questions**

| OQ-ID | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| OQ-020 | 04-docs/README §Global Layout lists a "theme" item in the account menu; the A1 S48 addendum omits it. A1 wins for screens, so this story builds the four-item menu — but is a theme switcher in v1 scope at all (and if so, where does the choice persist — `user_preferences`)? | Nothing — menu built per A1; scope/polish only | Product Owner (chat session) | OPEN |

---
```yaml
id: US-SHL-020
epic: EP-SHL-01
module: platform-shell
screens: [S9, S14, S15, S49, S50, S21, S30, S32]
wave: 2
status: draft
blocked_by: []
depends_on: [US-SHL-001]
journeys: []
rules: [BR-SHL-044]
golden_tests: []
finance_calc: none
```
### US-SHL-020 — One page header for every screen

**1 · Details** — As a staff user, I want every screen to put its title, its actions and its guidance in the same places, so that I learn the product once instead of once per screen. As the platform, I want that to be one component rather than a convention, so a new screen conforms by default rather than by diligence.

**Why this story exists.** The PO walked the prototype screen by screen on 2026-08-10 — Plans & Rates (4 tabs), Premises (2), Assets (3), Meter detail (5) — and found every one using the same skeleton while the app had each screen inventing its own. That is why each looked misplaced in a *different* way, and why fixing them individually would have been the wrong move (DEF-021).

**The skeleton, in order:**
```
← back                                        (detail screens only)
KICKER
H1                        [status] [secondary…] [ONE primary]
roll-up / subtitle line
────────────────────────────────────────────────────────────
tab strip
per-tab explainer
content
```

**2 · Business Rules**
| BR-ID | Statement | Status |
|---|---|---|
| BR-SHL-044 | One shared `PageHeader`, taking tabs as config. **(a)** The primary action is per-TAB, not per-page — the same slot renders `+ New plan` → `+ New rate schedule` → `+ New charge code` → `+ New tax or fee`. **(b)** The explainer changes with the tab. **(c)** A tab may have NO header action at all, and may instead carry one inside its body — so the slot must accept empty | CONFIRMED — PO prototype diff 2026-08-10 |

**3 · Test Cases**
| TC-# | Scenario | Expected |
|---|---|---|
| TC-1 | Plans & Rates, each of the four tabs | Primary action label changes per tab; History stays a secondary beside it |
| TC-2 | Same, each tab | Explainer text changes with the tab and renders BELOW the strip |
| TC-3 | Meter detail → Audit | No header action renders; the header does not collapse or shift |
| TC-4 | Meter detail → Maintenance | Header carries `Reassign · Log repair · Retire`; `+ Log repair` renders in the BODY |
| TC-5 | Detail screens | `← Assets` back-link renders above the kicker; list screens render none |
| TC-6 | Every screen using the component | Exactly ONE element has the primary class — a header cannot offer two primaries |
| TC-7 (neg) | A screen declares a tab with no explainer | Renders no empty paragraph and no layout shift |
| TC-8 (isolation) | Any screen, two tenants | Header content is per-tenant data; no label leaks across |
| TC-9 | Visual conformance gate | Each converted screen diffs clean against its prototype frame |

**4 · Test Data** — Silver Creek Water, the prototype's own fixture: Plans & Rates roll-up "6 plans · 4 rate schedules · 12 charge codes · effective Aug 1, 2026"; Meter M-4021 header "Electric · ×10 · installed Mar 2024 · assigned to 1408 Elm Street · Unit A".

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Kicker · title · roll-up | all | prototype-extracted | none — props | text | computed-display | title required; roll-up optional |
| Tab config (label, explainer, action) | all | prototype-extracted | none — per-screen constant | — | reference-data | at most one primary per tab |
| Back link | detail screens | prototype-extracted | none | text + route | computed-display | absent on list screens |

**6 · Acceptance** — **Given** a screen declares its tabs with labels, explainers and actions, **when** a user moves between tabs, **then** the title block stays put while the primary action and the guidance change with the tab; **and** a screen that declares no action for a tab renders a header with an empty action slot rather than a shifted layout.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None. (The prototype is the ratified source for layout; every property above is drawn from it, not proposed.)

---

#### Addendum r1 — how the primary action reaches the header (found during conversion, 2026-08-10)

Converting Plans & Rates surfaced a constraint the story did not anticipate: **the per-tab primary actions are not uniformly hoistable.**

| Tab | Action | Liftable to config? |
|---|---|---|
| Plans | `navigate(NEW_PLAN_ROUTE)` | ✅ pure navigation |
| Rate schedules | `navigate(...)` | ✅ |
| Charge codes | `setAdding(true)` | ❌ **local `useState` in the tab body** |
| Taxes & fees | `setAdding(true)` | ❌ |

A frame cannot reach a child's `useState`, so `PageHeaderTab.primaryAction` as a plain config value only serves half the tabs. Three ways out, and the third is the one to build:

| Option | Why not / why |
|---|---|
| Lift `adding` state into the frame | The frame acquires state belonging to four different tabs; every new tab widens it. Rejected |
| Give every action a route (`?add=1`) | Turns a modal into navigation and changes behaviour to suit the layout. Rejected — the layout must serve the screen, not the reverse |
| **Header action SLOT** — the frame renders an empty node in the action row; the active tab body renders its own button into it through context | **Build this.** State stays where it lives, the button appears where the prototype puts it, and a tab that renders nothing leaves the row empty, which TC-3 already requires |

The slot is the same shape as the existing `RefusalNotice`/`GuardedButton` composition, so the tab bodies keep their RBAC treatment (BR-SHL-025: a Clerk sees the button, disabled, with the reason) rather than that logic migrating into the frame.

**Consequence for `PageHeaderTab`:** `primaryAction?: ReactNode` stays for the navigation cases; the slot covers the stateful ones. Both render into the same node, so the header renders at most one primary either way (TC-6 unchanged).

**TC-10 (added):** a tab whose action lives in its body renders that button in the HEADER action row, not in the body — and the body's own `.rating-tab-actions` container disappears with it.

**r2 — the slot mechanism, reconsidered (2026-08-10).** The context slot above has a defect of its own: this repo tests components with `renderToStaticMarkup` (there is no DOM library in `package.json`), and a context slot registers its button in an **effect** — effects do not run under static rendering. TC-10 would then be provable only by a Playwright journey, and TC-1/TC-3/TC-6 would weaken with it.

**Preferred instead:** give each tab a `render()` returning `{ action, body }`, so the frame receives both from one call. No context, no effects, everything stays provable in the fast suite. `PageHeaderTab.primaryAction` remains for the pure-navigation tabs. Build this shape unless it fails on contact.

**r2 confirmed on contact (2026-08-10) — as built.** The shape held. Plans & Rates is converted and every TC below is asserted against static markup in the fast suite, which was the whole reason r2 rejected the context slot.

The contract, as built, in `ratingShared.tsx`:

```ts
export interface RatingTabParts {
  action?: ReactNode;   // rendered by the frame into the header's ONE primary slot
  body: ReactNode;      // everything below the header
}
export type RatingTabRender = (parts: RatingTabParts) => ReactNode;
```

`render` is **required** on all five tabs, not optional: a tab that forgot to hand its action up would render the button nowhere and every test would still pass. Making it required turns that into a compile error — it caught four call sites the moment the type landed.

Two things r2 did not anticipate, both built and tested:

| Found | Answer |
|---|---|
| A tab's early returns (`PermissionDenied`, `FailedWithRetry`) skipped the header entirely, so a failed read collapsed the page to a bare error card | **Every** return path goes through `render()`. A failed read keeps its header and tab strip, and offers no action — there is nothing to add to a list that would not load |
| `activeTabId="history"` fell back to the first tab, putting the Plans explainer and `+ New plan` on a screen that is not Plans | An `activeTabId` that matches NO tab now selects **none**. History is a sibling destination — the prototype gives it a top-right button, not a fifth tab |

**BR-SHL-025 stays in the tab body.** The tab hands up a `GuardedButton`, so a Clerk still sees the button disabled with its reason; the header renders whatever it is handed and knows nothing about roles.

**DEF-021 corrections made in the same pass:** the kicker "Plans & Rates" rendered directly above the H1 "Plans & Rates" — the prototype head has no kicker, and the duplicate is gone. The one page-level explainer became four per-tab explainers, taken verbatim from prototype lines 799 / 815 / 865 / 883 with their `<b>` stripped.
