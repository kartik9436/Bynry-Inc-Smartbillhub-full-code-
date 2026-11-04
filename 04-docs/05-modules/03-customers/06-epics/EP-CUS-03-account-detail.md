# EP-CUS-03 — Account detail
> Reconciled 2026-08-08 against PO rulings (BR-CUS-046..059) — propagation sweep.

**Module:** customers (product name: Accounts) · **Wave:** W2 · **Screens:** S21 · **Status:** draft

## Scope
**In:** the S21 account detail page: header card (billing chain identity, balance, plan, last activity, status/autopay pills, service tags with meter numbers, the "all accounts for this customer" affordance per BR-CUS-054, primary + secondary action rails) and the nine tabs — Overview · Bills · Payments · Usage · Meters · Adjustments · Documents · Notes · Audit. **Tab content that belongs to other modules renders THEIR read-models via service functions (B1)**: Bills/Adjustments ← billing, Payments ← payments, Usage ← metering reads, Meters ← assets/metering, Audit ← audit_log. Customers owns the aggregation, plus Notes and Documents metadata outright.
**Out:** the S22 action modals (EP-CUS-04) · S23/S24 wizards (EP-CUS-05/06) · producing any bill/payment/adjustment row (owning modules) · the customer portal (out of scope per roadmap — portal-panel fields are capture/display-only).

## Capability matrix (list screens only — B9 conformance)
Tab tables inside S21 (scoped to one account; identity column = the document/row #):
| Screen | Search fields | Filters | Default sort | Sortable | Columns default/available | Row actions | Bulk actions | Export |
|---|---|---|---|---|---|---|---|---|
| S21 Bills tab | bill #, cycle | status segments All/Paid/Open/Void | issue date desc | issue date, due date, total, status | 9 (Bill # · Cycle · Issue date · Due date · Usage · Subtotal · Tax · Total · Status) — IS-5 chooser | row click → bill detail (billing screen) | — | CSV (IS-9) |
| S21 Payments tab | confirmation # | — | date desc | date, amount, status | 6 (Date · Method · Confirmation · Applied to · Amount · Status) | — (+ Record payment button → S22) | — | CSV |
| S21 Adjustments tab | — | — | date desc | date, amount | 6 (Date · Adjustment # · Reason · Applied to · Amount · Approved by) | — (+ New adjustment → S22 Adjust) | — | CSV |
| S21 Notes tab | note text | — | pinned first, then date desc | date | card list (title · body · author · date) | — (+ Add note → S22) | — | — |

## Stories

---
id: US-CUS-008
epic: EP-CUS-03
module: customers
screens: [S21]
wave: 2
status: draft
blocked_by: []
depends_on: [US-CUS-001, US-CUS-006, US-SHL-002]
journeys: []
rules: [BR-CUS-016, BR-CUS-033, BR-CUS-034, BR-CUS-054, BR-CUS-055, BR-CUS-058]
golden_tests: []
finance_calc: none
---
### US-CUS-008 — Detail header, status pills & action rails

**1 · Details** — As any staff role, I want the S21 header to show the billing chain (Account A-#### · customer name · service address incl. unit · "Since <month year>"), status + autopay pills, service tags with meter numbers (ELECTRIC · M-4021), the Balance block (amount + due date), the Plan block (name + derived base "$30.50/mo base"), Last activity, the primary actions (Record payment · Adjust · Move-out) and the secondary rail (Send statement · Print bill · Issue credit · Change plan · Disconnect notice · Payment plan · Add note) — plus, on the customer name, the **"all accounts for this customer →" affordance (BR-CUS-054)** that opens S17 filtered to every account linked to this customer (the landlord case) — so that one glance answers "who, where, what plan, what's owed" and every account action is one click away. Entry: S17 row click and deep links (`acctDetailId` in URL per README routing). Exit: modals (S22), wizards (S20/S23/S24), the customer-accounts view, ← Accounts. Role gating: actions render disabled-with-reason per IS-6/A4 (Executive = view; approval-gated actions per A4).

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-CUS-033 | Header contract (fields verbatim above); Balance = cached `accounts.balance` with next due date from the oldest open invoice; Plan block shows the SNAPSHOT plan (BR-CUS-014 sc.1), not the unit's — they are equal by construction, and the snapshot is what billing uses (sc.6). | PROPOSED — prototype S21 header + BR-CUS-014 |
| BR-CUS-054 | "All accounts for this customer": the header customer name carries an affordance listing/linking every `customer_accounts`-linked account of this customer; a customer-level edit (contact details) updates all of them. No prototype artwork exists for the affordance (post-prototype PO ruling) — flagged for the design session, built as a link chip meanwhile. | CONFIRMED (capability) — PO OQ-057 (b); artwork PROPOSED |
| BR-CUS-016 / BR-CUS-055 | Pills: stored status from the BR-CUS-055 seeded lookup (Pending activation · Active · Marked disconnect · Vacation hold/Suspended · Closed + tenant additions) + derived aging; "Autopay on" pill from `accounts.autopay` (capture-only v1, BR-CUS-059 — the pill signals enrollment, not drafting). | PROPOSED (derivation) / vocabulary CONFIRMED — BR-CUS-055 |
| BR-CUS-058 | Any credit-tier display on S21 renders the COMPUTED value (BR-CUS-058 seeded rule); the tier is never editable from the header or edit affordances. | CONFIRMED — PO OQ-062 (b) |
| BR-CUS-034 | *(shared)* header reads other modules only via service functions; no cross-module writes from S21. | PROPOSED — B1 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Marcus opens A-10432 | Header: "Account A-10432 · Active · Autopay on", Miller, Sarah, 1408 Elm Street · Unit A · Katy, TX 77494 · Since Feb 2024; tags ELECTRIC · M-4021 / WATER · M-4022; Balance $247.30 · Due Aug 25; Plan "Residential Standard · $30.50/mo base"; Last activity "ACH payment · Aug 6 · 07:15"; customer name carries "all accounts for this customer →" (one account here — the chip still renders, BR-CUS-054) |
| TC-2 | Plan version bumps in the catalog (RES-STD v4); separately, a customer linked to 3 accounts opens any of them | Header still shows the account's snapshot v3 values (BR-CUS-013/014); the customer chip lists all 3 linked accounts and jumps between them (BR-CUS-054) |
| TC-3 | Deep link `/accounts/10432?tab=bills` | Detail opens on Bills tab; URL round-trips (IS-4 pattern) |
| TC-4 *(negative)* | Priya (Executive) opens A-10432 | All seven money/action buttons disabled-with-reason (A4: Accounts = View for Executive); server rejects forged action calls |
| TC-5 *(negative)* | Closed account A-11208 opened; Vacation hold/Suspended fixture A-11603 opened | Closed: Move-out / Record payment / Change plan / Payment plan disabled ("account closed"); Print bill & statement remain available (history is readable). Vacation hold: status pill renders the BR-CUS-055 label; action gating BEYOND the pill follows the behavior class — seed mapping pending OQ-064, so v1 gates only on Closed |
| TC-6 *(isolation)* | J. Okafor requests /accounts/10432 by URL | 404/permission-denied per A18 — the id resolves only inside its tenant (RLS) |

**4 · Test Data** — A-10432 per EP-CUS-01 §4 (balance $247.30 due Aug 25 2026; RES-STD v3; autopay ACH Chase ••••4021; last activity ACH payment Aug 6 07:15). Closed fixture A-11208 (Nguyen, closed Jul 2025). Vacation-hold fixture A-11603 (Thompson, R. — status Vacation hold/Suspended per BR-CUS-055). Multi-account customer fixture: Bluebonnet Property Group LLC ×3 accounts (EP-CUS-07 seed). Actors: Marcus Vega, Priya Menon, J. Okafor.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Account # + name + address + since | S21 header | prototype-extracted | `accounts.account_no` / customer display name via `customers`/`contacts` (BR-CUS-054) / unit→premises address (⚠ read) / `accounts.opened_at` | text/date | computed-display | — |
| "All accounts for this customer" chip | S21 header | BR-CUS-054 (PO ruling — no prototype artwork; flagged for design) | `customer_accounts` links for the header customer | reference | computed-display | lists every linked account, tenant-scoped |
| Status + autopay pills | S21 header | prototype-extracted | `accounts.status` (BR-CUS-055 seeded lookup) + derived aging + `accounts.autopay` | lookup/bool | system-derived | BR-CUS-016/055; autopay = enrollment only (BR-CUS-059) |
| Service tags + meter #s | S21 header | prototype-extracted | `service_agreements` + `asset_assignments` (⚠ assets read) | reference | computed-display | active only |
| Balance + due | S21 header | prototype-extracted | `accounts.balance` + oldest open invoice due_date (⚠ billing read) | numeric USD/date | system-derived | 2dp display |
| Plan block | S21 header | prototype-extracted | snapshot (`account_plan_assignments` current) + derived base Σ `plan_services.base_charge` (⚠ rating read) | text/numeric | computed-display | BR-CUS-014 sc.1 |  ⚠ **`account_plan_assignments` is SUPERSEDED (PO 2026-08-11)** — no account-side plan table is built; the plan lives once on `units.rate_plan_id` and the account derives it. See BR-CUS-029.
| Last activity | S21 header | prototype-extracted | latest audit_log/payment event for the account (⚠ read) | text | computed-display | — |
| Action rails | S21 header | prototype-extracted (10 actions) | navigation to S22/S20/S23/S24 | — | user-input | role + state gated (IS-6, A4); status behavior classes pending OQ-064 |

**6 · Acceptance**
- Given A-10432, Then every header field renders per TC-1 and matches the underlying rows, including the customer chip.
- Given a multi-account customer, Then the chip lists all linked accounts and navigates between them.
- Given a role or account state that forbids an action, Then the button is disabled-with-reason and the server enforces it.
- Given a foreign-tenant URL, Then the account never resolves.

**7 · Finance Calculation** — N/A (displays cached/derived amounts only).

**8 · Open Questions** — None new (OQ-058 CLOSED→BR-CUS-055; the behavior-class seed mapping residue is OQ-064, tracked on US-CUS-001 — v1 gates actions only on Closed until ruled).

---
id: US-CUS-009
epic: EP-CUS-03
module: customers
screens: [S21]
wave: 2
status: draft
blocked_by: []
depends_on: [US-CUS-008]
journeys: []
rules: [BR-CUS-028, BR-CUS-034, BR-CUS-045, BR-CUS-054, BR-CUS-057, BR-CUS-058]
golden_tests: []
finance_calc: none
---
### US-CUS-009 — Overview tab (recent bills, usage trend, customer/payment/deposit/portal panels)

**1 · Details** — As any staff role, I want the Overview tab's two-column digest — left: Recent bills (last 4, → Bills tab) and Usage trend (12-month bars, → Usage tab); right: Customer panel (name, email, phone, DOB, masked ID, mailing address — edits here update the CUSTOMER entity and therefore every linked account, BR-CUS-054), Payment method panel (method + masked ref, autopay/verification status, → Update method), Deposit & credit panel (On file / Interest accrued per BR-CUS-057 / Credit tier computed per BR-CUS-058), Portal access panel (last login, paperless, SMS) — so that 90% of phone calls end on this one tab. All left-column and payment data are read-models of other modules (BR-CUS-034); the right-column panels render customers-owned attributes.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-CUS-034 | *(shared)* Recent bills ← billing read-model; usage bars ← metering reads; payment method ← payments `payment_methods` — service functions only. | PROPOSED — B1 |
| BR-CUS-054 | Customer-panel data belongs to the first-class customer entity; an edit propagates to all linked accounts ("one edit updates all"). | CONFIRMED — PO OQ-057 (b) |
| BR-CUS-045 | *(shared)* PII display: DOB and ID render masked ("DL ****4218"); full values never leave the server. | PROPOSED — B2 PII columns + OQ-016 closure |
| BR-CUS-057 | Interest accrued = the BR-CUS-057 accrual (tenant-set simple annual rate, default 0%, monthly from the original receipt date — engine US-CUS-023 §7); the old OQ-061 stub is retired. | CONFIRMED — PO OQ-061 (b) |
| BR-CUS-058 | Credit tier displays the COMPUTED value (seeded rule: 12-mo window, 0 lates = A, 1–2 = B, 3+ = C; tenant-configurable params; informational); tooltip states the basis ("0 late payments in the last 12 months"). | CONFIRMED (computed, in V1) — PO OQ-062 (b); tooltip copy PROPOSED |
| BR-CUS-028 | *(shared)* Paperless/SMS render from preference fields; autopay display = enrollment only (capture-only v1, BR-CUS-059); portal last-login is display-only and EMPTY in v1 — the customer portal is out of scope (roadmap "pending deliberate decision"); panel shows "Portal not enabled in v1" instead of fabricated data. | PROPOSED (prefs) / autopay CONFIRMED — BR-CUS-059 / portal deferred per roadmap |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Marcus opens Overview on A-10432 | Recent bills = last 4 issued (Jul→Apr, amounts $247.30/$228.10/$219.40/$232.80, status Paid); usage bars for 12 months; "All bills →" jumps to Bills tab |
| TC-2 | Customer panel; Marcus corrects the phone number | Sarah Miller, sarah.miller@example.com, +1 (512) 555-0184, DOB 04/12/1987, "ID: DL ****4218" (masked), Mailing: Same as service; the phone edit writes the customer entity and reflects on every account linked to Sarah (BR-CUS-054); audit row |
| TC-3 | Deposit & credit panel | On file $150.00 · Interest accrued $3.20 (BR-CUS-057 accrual at the tenant's configured rate — $0.00 at the 0% default) · Credit tier A (computed per BR-CUS-058; tooltip "0 late payments in the last 12 months") |
| TC-4 | Portal access panel in v1 | Paperless On · SMS On from preference fields; portal last-login area renders the v1 placeholder (no invented login data) |
| TC-5 *(negative)* | API response for the Customer panel inspected; separately, a forged PATCH sets `credit_tier` = "A+" | Full gov-ID/DOB never present beyond masked display fields (BR-CUS-045); the tier write is rejected — computed field, no input path (BR-CUS-058) |
| TC-6 *(negative)* | Account with zero bills (A-11512 pending) | Recent-bills panel shows the A18 empty state, not an error |
| TC-7 *(isolation)* | J. Okafor loads any Brazos Bend account id | Denied; his own A-20011 Overview shows only Lone Star Ridge data (RLS) |

**4 · Test Data** — A-10432 fixture (bills/payments per prototype: BL-2607-018204 $247.30 Paid … BL-2604-017842 $232.80 Paid; payment method ACH · Chase ••••4021, bank verified; deposit $150.00, interest $3.20 per BR-CUS-057 at the tenant fixture rate, tier A computed — 0 lates in 12 mo; paperless On, SMS On). Empty-state fixture A-11512 (Pending activation, no bills).

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Recent bills (4) | S21 Overview | prototype-extracted | invoices read-model (⚠ billing) | rows | computed-display | last 4 issued |
| Usage trend bars | S21 Overview | prototype-extracted | monthly sums over `meter_reads` (⚠ metering) | numeric kWh/kgal | computed-display | explicit unit (CLAUDE.md #3) |
| Customer panel | S21 Overview | prototype-extracted | `customers` + `contacts` (masked DOB/ID) + `addresses` — edits write the customer entity (BR-CUS-054, PROPOSED-SCHEMA) | text | computed-display / user-input | BR-CUS-045; one edit updates all linked accounts |
| Payment method panel | S21 Overview | prototype-extracted ("ACH · Chase •••• 4021 · Bank verified") | `payment_methods` (⚠ payments read); Update method → payments flow | text | computed-display | masked ref only; autopay = enrollment display (BR-CUS-059) |
| Deposit on file / Interest / Credit tier | S21 Overview | prototype-extracted | `accounts.deposit_on_file` / **PROPOSED-SCHEMA** `.deposit_interest_accrued` (BR-CUS-057 accrual) / `.credit_tier` (computed cache, BR-CUS-058; rule params **PROPOSED-SCHEMA** `credit_tier_rules`) | numeric/text | system-derived | BR-CUS-057 / BR-CUS-058 |
| Portal panel (last login, paperless, SMS) | S21 Overview | prototype-extracted | **PROPOSED-SCHEMA** `accounts.paperless`, `.sms_reminders`, `.portal_enabled`; last-login **GAP-deferred** (portal out of v1 scope per roadmap — no OQ minted, decision already recorded) | bool | system-derived | v1 placeholder for portal data |

**6 · Acceptance**
- Given A-10432, Then all four panels + both left cards render per TC-1..4 with masked PII, the BR-CUS-057 interest accrual and the BR-CUS-058 computed tier.
- Given a customer-panel edit, Then it propagates to every linked account.
- Given no bills, Then the empty state renders.
- Given v1, Then no portal login data is fabricated and no tier is writable.

**7 · Finance Calculation** — N/A (stored/derived display only; interest accrual math lives in US-CUS-023 §7, tier rule in BR-CUS-058).

**8 · Open Questions**
| OQ | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| OQ-061 | *(shared)* deposit interest accrual | Nothing — closed | Product Owner (chat session) | CLOSED(→BR-CUS-057) — tenant-set simple annual rate, default 0%, monthly accrual, payout at refund/closure (PO) |
| OQ-062 | *(shared)* credit-tier value set/source | Nothing — closed | Product Owner (chat session) | CLOSED(→BR-CUS-058) — computed from payment history, seeded 12-mo rule, tenant-configurable, informational; in V1 (PO) |

---
id: US-CUS-010
epic: EP-CUS-03
module: customers
screens: [S21]
wave: 2
status: draft
blocked_by: []
depends_on: [US-CUS-008]
journeys: []
rules: [BR-CUS-034, BR-BIL-004, BR-PAY-002]
golden_tests: []
finance_calc: none
---
### US-CUS-010 — Financial tabs: Bills · Payments · Adjustments (read-models with boundaries)

**1 · Details** — As any staff role, I want the three financial tabs — Bills (bill #, cycle, issue/due dates, usage, subtotal, tax, total, status incl. "Draft (in run)"), Payments (date, method, confirmation, applied-to, amount, status — deposits shown with status "Held"), Adjustments (date, adjustment #, reason, applied-to, signed amount, approved-by) — rendered from billing/payments read-models scoped to this account, so that the full money history is visible without leaving the account. **Boundary:** these tabs WRITE NOTHING; "+ Record payment" and "+ New adjustment" open the S22 modals (EP-CUS-04) which call the owning modules' services. Table behavior per the capability-matrix rows.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-CUS-034 | *(shared)* financial rows come from billing/payments via service functions; customers holds no copy. | PROPOSED — B1 |
| BR-BIL-004 | Issued invoices/lines are immutable — the Bills tab offers NO edit affordance on any issued row; drafts display as "Draft (in run)" and link to the run, not to an editor. | CONFIRMED — B2 §billing, CLAUDE.md #4 (cited) |
| BR-PAY-002 | Payments are append-only once out of processing; the tab shows reversals as their own rows, never mutated originals. | CONFIRMED — B2 §payments (cited) |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Bills tab on A-10432 | 6 rows incl. BL-2608-018320 "Draft (in run)" ($145.70) and 5 Paid; totals = subtotal + tax per row; status vocabulary per the A5 addendum (draft/issued/paid/void/corrected + derived open/overdue) |
| TC-2 | Payments tab | 6 rows incl. deposit DEPO-4218 $150.00 status Held; confirmation search filters (capability row) |
| TC-3 | Adjustments tab | ADJ-142 Leak credit −$42.50 applied to BL-2606-018091 approved by Alex Reed; credits render signed-negative |
| TC-4 | Bill status filter Open on a fully paid account | Zero-results-after-filter state (IS-7/A18) |
| TC-5 *(negative)* | Any mutation attempt on an issued bill row via the tab's API surface | No such endpoint exists from customers; direct billing-API forgery rejected per BR-BIL-004 — asserted in the immutability suite |
| TC-6 *(isolation)* | Read-model queries under J. Okafor's session | Return only Lone Star Ridge rows even when passed a Brazos Bend account id (service functions re-check tenant, RLS backstop) |

**4 · Test Data** — A-10432 bills/payments/adjustments exactly per the prototype tables (BL-2603…BL-2608; ACH-2028104/2028010/2027918/2027822, ch_1P41yM, DEPO-4218; ADJ-142/-089/-034 with approvers Alex Reed / Priya Menon).

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Bills rows | S21 Bills | prototype-extracted | `invoices` + `invoice_lines` aggregates (⚠ billing read-model per A11 S21 read-model note) | rows | computed-display | immutable display |
| Bill status | S21 Bills | prototype-extracted + A5 addendum | `invoices.status` + derived open/overdue | enum | system-derived | BR-BIL-004 |
| Payments rows | S21 Payments | prototype-extracted | `payments` + `allocations` (⚠ payments) | rows | computed-display | append-only display |
| Deposit rows in Payments | S21 Payments | prototype-extracted (DEPO-4218 · Held) | deposit position (US-CUS-007) surfaced in the payment ledger read-model | row | computed-display | status Held |
| Adjustments rows | S21 Adjustments | prototype-extracted | adjustments read-model (⚠ billing/payments per B2) with approved_by | rows | computed-display | signed amounts |

**6 · Acceptance**
- Given A-10432, Then all three tabs reproduce the fixture rows with correct statuses, signs and links.
- Given an issued invoice, Then no edit path exists from S21.
- Given a cross-tenant id, Then read-models return nothing.

**7 · Finance Calculation** — N/A (renders owning-module amounts verbatim).

**8 · Open Questions** — None.

---
id: US-CUS-011
epic: EP-CUS-03
module: customers
screens: [S21]
wave: 2
status: draft
blocked_by: []
depends_on: [US-CUS-008, US-MET-010, US-AST-002]
journeys: []
rules: [BR-CUS-034, BR-CUS-035, BR-CUS-036, BR-MET-017]
golden_tests: []
finance_calc: none
---
### US-CUS-011 — Operational tabs: Usage · Meters · Documents · Notes · Audit

**1 · Details** — As any staff role, I want the five operational tabs — Usage (per-service segmented 12/24-month chart + KPI strip: avg/month, peak, low, YoY, water avg), Meters (assigned meters table: #, service, type, install date, multiplier, last read/date, health + per-meter read log), Documents (metadata list with type + upload), Notes (card list, pinned first, + Add note) and Audit (timestamp/user/action/object/details, account-scoped) — so that operational history lives with the account. Usage/Meters/Audit are read-models (metering, assets, audit); **Notes and Documents metadata are customers-owned tables** (PROPOSED-SCHEMA).

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-CUS-034 | *(shared)* Usage ← meter_reads; Meters ← assets/asset_assignments; Audit ← audit_log filtered to the account's object graph. | PROPOSED — B1 |
| BR-CUS-035 | Notes: customers-owned `account_notes` (title, body, author, created_at, pinned, customer_visible flag); IS-1 audited edits; `customer_visible` is CAPTURED but inert in v1 (portal out of scope, roadmap). | PROPOSED-SCHEMA — prototype Notes tab + S22 Add-note modal |
| BR-CUS-036 | Documents: customers-owned `account_documents` metadata (name, type from lookup System/Contract/KYC/Payment/Correspondence, uploaded_by, uploaded_at, size, storage ref); system-generated documents (welcome pack, signed agreements, deposit letters) attach automatically; files retained per the 7-year policy (OQ-017 closure). | PROPOSED-SCHEMA — prototype Documents tab |
| BR-MET-017 | Read log rows link to their import batch; posted reads append-only — the Meters tab renders lineage heads, never edits. | PROPOSED (cited from metering) |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Usage tab, Electric, 24 months | Chart + KPI strip (avg 628 kWh, peak 842 Jul 2026, low 412 Feb 2026, YoY +8.2%, water avg 3.42 kgal); units always explicit |
| TC-2 | Meters tab | M-4021 (AMI · Itron OpenWay CENTRON, installed Feb 12 2024, ×1, last 43,148 Aug 3 06:12, Healthy) + M-4022; read log for M-4021 shows 4 dated reads with source and "Partial cycle" note |
| TC-3 | Marcus adds a pinned note "Customer called about leak" | `account_notes` row (author, timestamp, pinned); renders first; audit `note.created` |
| TC-4 | Upload "Leak_Repair_Invoice.pdf" type Correspondence | Metadata row + storage ref; size shown; audit `document.uploaded` |
| TC-5 | Audit tab | Account-scoped events newest-first (payment applied, autopay enrollment captured, bill generated, adjustment posted, account created…) — rendered from audit_log, read-only |
| TC-6 *(negative)* | Attempt to delete the signed service agreement document | Blocked — system/contract documents are audit-locked (IS-1 🔒 pattern); deactivate/supersede only |
| TC-7 *(negative)* | Note saved with empty title and body | Inline validation error; nothing written |
| TC-8 *(isolation)* | J. Okafor's audit tab query with a Brazos Bend account id | Denied; audit reads are tenant-scoped (S61 constraint: tenant-scoped-only, OQ-029 closure) |

**4 · Test Data** — A-10432 fixtures per prototype: meters M-4021/M-4022 with read logs; documents Welcome_Pack_A-10432.pdf (System) · Signed_Service_Agreement.pdf (Contract) · ID_Verification.png (KYC) · ACH_Authorization.pdf (Payment) · Leak_Repair_Invoice.pdf (Correspondence); notes "Leak credit request approved" (Alex Reed, Jun 22 2026) · "Autopay enrollment confirmed" (System) · "Move-in complete" (Alex Reed); audit rows per prototype Audit tab.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Usage chart + KPIs | S21 Usage | prototype-extracted | aggregates over `meter_reads` (⚠ metering) | numeric + unit | computed-display | explicit unit |
| Meters table + read log | S21 Meters | prototype-extracted | `assets` + `asset_assignments` + `meter_reads` (⚠ assets/metering) | rows | computed-display | lineage heads (BR-MET-017) |
| Note (title/body/pinned/customer-visible) | S21 Notes + S22 modal | prototype-extracted | **PROPOSED-SCHEMA** `account_notes` (tenant_id, account_id, title, body, author_id, pinned, customer_visible, timestamps) | text/bool | user-input | title or body required; visible flag inert v1 |
| Document metadata | S21 Documents | prototype-extracted | **PROPOSED-SCHEMA** `account_documents` (name, type_id → lookup, uploaded_by, size, storage_ref) | text/int | user-input / system-derived | type from lookup; 7-yr retention |
| Audit rows | S21 Audit | prototype-extracted | `audit_log` filtered to account object graph (read-only) | jsonb | computed-display | append-only |

**6 · Acceptance**
- Given A-10432, Then all five tabs reproduce the fixtures, with Notes/Documents writable (customers-owned) and Usage/Meters/Audit strictly read-only.
- Given a system contract document, Then deletion is audit-locked.
- Given cross-tenant access, Then every tab query is denied.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None (portal visibility flag inert per roadmap; no new OQ).
