# EP-CUS-01 — Accounts list
> Reconciled 2026-08-08 against PO rulings (BR-CUS-046..059) — propagation sweep.

**Module:** customers (product name: Accounts) · **Wave:** W2 · **Screens:** S17 · **Status:** draft

## Scope
**In:** the Accounts list (S17): the all-accounts table with service tags, balance and derived aging status; header roll-up KPIs; search + status segments; entry points to New account (S18), Move-in (S19), Move-out (S20) and Account detail (S21); CSV export. Renders through the shared table framework (EP-SHL-02) per the capability-matrix row; states per A18 (IS-7). The capability row is now PO-CONFIRMED (BR-CUS-053) and supersedes the earlier B9 draft where they differ (+meter # search, +filters, default sort name A→Z).
**Out:** account creation/lifecycle (EP-CUS-02) · account detail content (EP-CUS-03) · bulk AR actions (payments S34 owns collections bulk) · bulk account IMPORT (EP-CUS-07) · the S17 drawer variant seen in older prototype exports (the full-page S21 is canonical per A1).

## Capability matrix (list screens only — B9 conformance)
| Screen | Search fields | Filters | Default sort | Sortable | Columns default/available | Row actions | Bulk actions | Export |
|---|---|---|---|---|---|---|---|---|
| S17 Accounts list | account #, customer name, service address, meter # (BR-CUS-053) | status segments All/Current/Past due/Closed (derived states, BR-CUS-016) + filters status · category · plan · autopay · balance > 0 (BR-CUS-053) | customer name A→Z (BR-CUS-053) | account #, name, balance, last bill, status | 7 default (Account · Name · Premise · Services · Balance · Last bill · Status) / 10 available (+Plan, +Autopay, +Since) — IS-5 chooser | row click → S21 (no row dropdown in prototype) | — (v1; AR bulk lives in S34) | CSV (IS-9) |

## Stories

---
id: US-CUS-001
epic: EP-CUS-01
module: customers
screens: [S17]
wave: 2
status: draft
blocked_by: []
depends_on: [US-SHL-006, US-SHL-014]
journeys: []
rules: [BR-CUS-015, BR-CUS-016, BR-CUS-017, BR-CUS-053, BR-CUS-055]
golden_tests: []
finance_calc: none
---
### US-CUS-001 — Accounts list table & header roll-up

**1 · Details** — As a Billing Clerk, I want an all-accounts table showing account #, customer, premise/unit, service tags, balance, last bill date and status, with a header roll-up ("1,247 accounts · $184,320 outstanding · 18 past-due 60+" per prototype), so that I can see the whole customer base and its AR posture at a glance. Entry: sidebar → Accounts. Exit: row click → S21; page actions → S18/S19/S20/Export. Table behavior (pagination, sort, chooser, export) conforms to the capability-matrix row above (IS-2/5/9, now BR-CUS-053-confirmed); no story text restates B9.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-CUS-015 | S17 list contract: columns per the capability matrix; service tags render one tag per active service agreement; Balance shows the cached `accounts.balance` (ledger remains source of truth per B2). Search/filter/sort specifics are superseded by BR-CUS-053 where they differ. | PROPOSED — prototype S17 + B2 `accounts.balance` comment + B9 |
| BR-CUS-053 | S17 capability row per AC-8: search account # / customer name / service address / meter #; filters status · category · plan · autopay · balance > 0; default sort customer name A→Z; columns via the IS-5 chooser. | CONFIRMED — PO AC-8 |
| BR-CUS-016 | Stored status comes from the account-status lookup; display states "Current / 30d past / 60+ past" are DERIVED from open-invoice due-date math (and opening-bucket age post-import, BR-CUS-048) and never stored — mirrors the A5 invoice-status addendum pattern. Vocabulary is now CONFIRMED per BR-CUS-055. | PROPOSED (derivation rule) / vocabulary CONFIRMED — BR-CUS-055 |
| BR-CUS-055 | Status vocabulary: **Pending activation · Active · Marked disconnect · Vacation hold/Suspended · Closed** — seeded in Reference data, tenant-extensible, behavior-class mapped (billable / billable-base-only / non-billable / terminal; the seed status→class assignment is OQ-064 — display unaffected). | CONFIRMED — PO OQ-058 (b); class seed mapping OPEN — OQ-064 |
| BR-CUS-017 | An account belongs to exactly one unit (B2 `accounts.unit_id`), never to a premises; at most ONE active account per unit at a time (occupancy derives from it, BR-MET-036). Enforcement: PROPOSED-SCHEMA partial unique index on `accounts(tenant_id, unit_id) WHERE status='active'`. | PROPOSED — derived from B2 DDL + BR-MET-036 + prototype S15 copy ("Accounts attach to units, not to premises") |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Marcus opens Accounts with the §4 seed | 8 rows default-sorted by customer name A→Z (BR-CUS-053: Blueprint Studio first); header roll-up "8 accounts · $11,704.30 outstanding · 1 past-due 60+"; A-10432 shows tags E+W, balance $247.30, status Current; A-11512 shows Pending activation (BR-CUS-055 seeded label), $0.00, last bill "—" |
| TC-2 | Sort by Balance desc | A-11340 ($8,240.00) first; stable secondary sort by id (IS-2) |
| TC-3 | A-11455 has an issued invoice 62 days past due | Row renders derived "60+ past" pill; stored status remains Active (BR-CUS-016 — aging is never stored) |
| TC-4 | Column chooser adds Plan + Autopay; filter autopay=on (BR-CUS-053) | Columns persist per user (IS-5/BR-SHL-027); filter narrows to A-10432; export follows visible set (IS-9) |
| TC-5 *(negative)* | A second active account is inserted for unit U-10432-A via forged API call | Rejected by the one-active-account-per-unit constraint (BR-CUS-017); no row created |
| TC-6 *(negative)* | Priya Menon (Executive) opens the list | View only per A4 (Premises/Accounts = View for Executive); + New account / Move-in / Move-out render disabled-with-reason (IS-6); server rejects a forged POST |
| TC-7 *(isolation)* | J. Okafor (Lone Star Ridge) opens Accounts | Sees only A-20011; automated test asserts no Brazos Bend account id/name/balance in any page/sort/search permutation (RLS `app.tenant_id`) |

**4 · Test Data** — Tenant **Brazos Bend Utilities** (`brazosbend`, Katy TX; plans/deposits from the EP-RAT-01 seed). Accounts: **A-10432** Miller, Sarah · 1408 Elm St · Unit A · E(M-4021)+W(M-4022) · RES-STD v3 · $247.30 · Current · since Feb 2024 · autopay ACH · deposit $150.00 — **A-10891** Chen, David · 2201 Cedar Ln · E+W+S · $412.80 · Current — **A-11024** Ridge Coffee Co. · 500 Main · Suite 200 · COM-SM · E+W · $1,842.10 · 30d past — **A-11025** Blueprint Studio · 500 Main · 210 · E · $328.60 · Current — **A-11340** Northwind Mfg. · 77 Industrial Way · IND · E+W+S · $8,240.00 · 30d past — **A-11455** Park, Jenna · 901 Hillside Ave · E+W · $542.10 · 60+ past (invoice due Jun 7, 2026; today Aug 8, 2026) — **A-11512** Rodriguez, M. · 3450 Oak Ridge Dr · E+W · $0.00 · Pending activation — **A-11603** Thompson, R. · 88 Pine Vista · E · $91.40 · Current. Isolation tenant **Lone Star Ridge Water Co-op** (`lonestarridge`): A-20011 Cobb, Daniel · Co-op Water Basic · $64.00. Actors: Marcus Vega (Billing Clerk), Priya Menon (Executive), J. Okafor (Lone Star Ridge clerk).

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Account # | S17 | prototype-extracted (`A-#####`) | `accounts.account_no` (UNIQUE per tenant; allocated from the tenancy account series, BR-TEN-035) | text | system-derived | unique (tenant, account_no) |
| Name | S17 | prototype-extracted | `contacts.full_name` (is_primary; customer entity per BR-CUS-054 — see US-CUS-002) | text | reference-data | — |
| Premise | S17 | prototype-extracted ("1408 Elm St · A") | `accounts.unit_id` → units → premises (⚠ cross-module read, B1 service function) | text | computed-display | — |
| Services | S17 | prototype-extracted (svc tags E/W/S) | `service_agreements` active rows → `services` catalog (r5 #1) | reference | computed-display | active agreements only |
| Balance | S17 | prototype-extracted (`$0.00` 2dp) | `accounts.balance` (cached; ledger = truth) | numeric(18,6) USD | system-derived | display 2dp |
| Last bill | S17 | prototype-extracted ("Jul 15") | latest issued invoice date (⚠ billing read-model, B1) | date | computed-display | "—" when none |
| Status pill | S17 | prototype-extracted (Current/30d past/60+ past/Pending) | `accounts.status` (BR-CUS-055 seeded lookup + tenant additions) + derived aging (BR-CUS-016) | lookup + derived | system-derived | vocabulary per BR-CUS-055; behavior-class seed mapping OQ-064 |
| Header roll-up | S17 | prototype-extracted | counts/sums over `accounts` + open invoices | int/numeric | computed-display | — |

**6 · Acceptance**
- Given the §4 seed, When Marcus opens Accounts, Then all eight rows render name-A→Z with tags, cached balances, derived status pills (BR-CUS-055 labels) and the correct roll-up.
- Given a unit with an active account, When a second active account is attempted, Then the write is rejected.
- Given a Lone Star Ridge session, Then zero Brazos Bend rows appear in any permutation.

**7 · Finance Calculation** — N/A (balances displayed from cache; no amounts computed here).

**8 · Open Questions**
| OQ | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| OQ-058 | Account status lifecycle beyond B2's pending → active → closed | Nothing — closed | Product Owner (chat session) | CLOSED(→BR-CUS-055) — option (b): Pending activation · Active · Marked disconnect · Vacation hold/Suspended · Closed, seeded in Reference data, tenant-extensible (PO) |
| OQ-064 *(minted at reconciliation)* | Status→behavior-class SEED assignment (BR-CUS-055 names the four classes, not the mapping; is Marked disconnect billable or billable-base-only?) | Nothing here — billing W3 consumption only; list/pills/imports buildable | Product Owner (chat session) | OPEN |

---
id: US-CUS-002
epic: EP-CUS-01
module: customers
screens: [S17]
wave: 2
status: draft
blocked_by: []
depends_on: [US-SHL-006, US-SHL-007, US-CUS-001]
journeys: []
rules: [BR-CUS-015, BR-CUS-016, BR-CUS-053, BR-CUS-054]
golden_tests: []
finance_calc: none
---
### US-CUS-002 — Search, status segments & wizard entry points

**1 · Details** — As a Billing Clerk, I want to find any account by account #, name, address or meter # (BR-CUS-053) and slice the list by status segment (All / Current / Past due / Closed) plus the AC-8 filters (status · category · plan · autopay · balance > 0), so that walk-in and phone interactions resolve in seconds; and I want the New account / Move-in / Move-out page actions to open the right wizard. **Search-by-customer note (BR-CUS-054):** a name search resolves against the CUSTOMER entity — matching a customer linked to several accounts (landlord case) returns ALL of that customer's account rows, not just the first. Entry: S17 toolbar. Exit: filtered list; segment + search state in the URL (IS-4); wizard buttons → S18/S19/S20. Search mechanics per IS-3 (server-side, debounced, min 2 chars); this story declares only the searched fields (capability matrix).

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-CUS-053 | Search covers account #, customer name, service address and meter #; filters status · category · plan · autopay · balance > 0; segments remain the four prototype values. | CONFIRMED — PO AC-8 |
| BR-CUS-054 | Name search matches the customer entity; one customer ↔ many accounts means a customer hit returns every linked account row ("all accounts for this customer" view enabled). | CONFIRMED — PO OQ-057 (b) |
| BR-CUS-015 | *(shared)* list contract per the capability matrix. | PROPOSED — prototype S17 toolbar + B9 |
| BR-CUS-016 | *(shared)* "Past due" segment = accounts with any issued invoice past due date, or opening-bucket overdue age post-import (derived); "Closed" = stored status Closed (BR-CUS-055). | PROPOSED (derivation) / vocabulary CONFIRMED — BR-CUS-055 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Search "Elm" | A-10432 only (service-address match); ✕ clears (IS-3) |
| TC-2 | Search "11024"; search "M-4021" | A-11024 (account-number match, prefix "A-" optional); A-10432 (meter-# match, BR-CUS-053) |
| TC-3 | Segment "Past due" | A-11024, A-11340, A-11455 only; segment persists in URL (IS-4) |
| TC-4 | Segment "Closed" with no closed accounts in seed | Zero-results-after-filter state per A18 (IS-7), with clear-filter affordance |
| TC-5 | Marcus clicks Move-out | S20 opens with its own account search (US-CUS-005); Cancel returns to S17 with segment/search state intact |
| TC-6 *(negative)* | Search "M" (1 char) | No query issued (IS-3 min 2 chars); list unchanged |
| TC-7 *(isolation)* | J. Okafor searches "Miller" | Zero results; the query provably scopes to Lone Star Ridge (RLS) |

**4 · Test Data** — Seed of US-CUS-001 §4. Today = Aug 8, 2026 (drives the Past-due derivation: A-11024/A-11340 due Jul 8; A-11455 due Jun 7). Customer-entity search fixture rides the EP-CUS-07 seed (Bluebonnet Property Group LLC ×3 accounts — asserted in US-CUS-019 TC-2).

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Search box | S17 | prototype-extracted + BR-CUS-053 (adds meter #) | query over `accounts.account_no`, customer name via `customers`/`contacts` (BR-CUS-054), unit/premises address, asset # (⚠ cross-module reads) | text | user-input | IS-3 |
| Status segment + filters | S17 | prototype-extracted (All/Current/Past due/Closed radios) + BR-CUS-053 (status · category · plan · autopay · balance > 0) | derived filter over `accounts.status` (BR-CUS-055 lookup) + invoice due-date math + account attrs | enum | user-input | BR-CUS-016/053 |
| Page actions | S17 | prototype-extracted (Export / Move-out / Move-in / + New account) | navigation only (S18/S19/S20; export per IS-9) | — | user-input | role-gated per A4 |

**6 · Acceptance**
- Given the seed, When Marcus combines segment Past due + search "Ridge", Then only A-11024 renders and the URL round-trips the state.
- Given a customer with several linked accounts, When their name is searched, Then every linked account row returns (BR-CUS-054).
- Given a 1-character search, Then no server query fires.
- Given Lone Star Ridge, Then Brazos Bend names never match.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None (OQ-058 CLOSED→BR-CUS-055, tracked on US-CUS-001 with the OQ-064 residue).
