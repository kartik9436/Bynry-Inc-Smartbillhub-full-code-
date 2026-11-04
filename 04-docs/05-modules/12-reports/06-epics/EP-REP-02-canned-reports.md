# EP-REP-02 — Canned reports not owned elsewhere (S46 renders; S30/S32 filter touchpoints)

**Module:** reports · **Wave:** W5 · **Screens:** S46 (viewer renders; S44 entry) · **Status:** draft (BR-REP-001..018 CONFIRMED; owning cross-module BRs all CONFIRMED)

## Scope
**In:** the canned reports the reports module OWNS as read-models: **AR aging summary + DSO trend** (opening buckets aging forward) · **Billing register** (`bill_type` column/filter) + **Revenue by service & rate** (invoice-line read-model + drill-back) · **Payments by method** (`purpose` column/filter, clearing basis) · the operations set — **Read completeness** (channel-aware), **High-usage exceptions**, **New & closed accounts** (status model) · the **six audit-added reports** (BR-REP-007: corrections · back-bills/penalty · write-offs · budget status · delivery-queue health · returned mail) — each strictly a read-model citing its owning BR.
**Out:** trial balance / account ledger / by-premises / remittance (US-LED-008/009/010/014) · S42 export (US-LED-016) · the S30/S33 list screens themselves (billing/payments own them; the A14-item-6 `bill_type`/`purpose` filters on those LISTS are recorded in their packs) · queue OPERATION (re-queue = US-NOT-013/US-BIL-024; this epic reports over the same rows) · viewer/download shell (EP-REP-01) · column-unknown catalog cards (generic viewer, US-REP-002; column sets = candidate OQ, pack report R-2).
**Tables:** read-only over `invoices(+bill_type)`, `invoice_lines`, `payments(+purpose, posted_at/cleared_at)`, `allocations`, `accounts`, `account_opening_buckets`, `meter_reads(+channel)`, `correction_cases`, `write_offs`, `account_budget_status`, `outbound_messages`, delivery-return events, journal-line dimensions.

## Capability matrix (list screens only — B9 conformance)
| Screen | Search fields | Filters | Default sort | Sortable | Columns default/available | Row actions | Bulk actions | Export |
|---|---|---|---|---|---|---|---|---|
| S46 · AR aging table | account, customer | param bar (US-REP-002) + age-bucket segment | total desc | account, customer, class, buckets, total | Account · Customer · Class · Current · **1–30** · 31–60 · 61–90 · 90+ · Total / +days-late (IS-5) — ⚠ **FIVE money bands since 2026-09-24 (`P2.21`, `DEF-REP-6659`)**, superseding the four written here: `BR-REP-030` is PO-confirmed at five and the Finance blueprint p035 draws five. **No figure moved** — `current` split into `current` (not yet due) and `1–30`; every other band, the total and the tie-out are unchanged | drill → S21 | — | IS-11 (US-REP-003) |
| S46 · Billing register table | bill #, account, customer | param bar + **bill_type** (cycle\|first\|final\|rebill\|backbill\|penalty) | bill # asc | bill #, account, amount, usage | Bill # · Account · Customer · Services · Usage · Amount · Flag / +**bill_type**, cycle (IS-5) | drill → bill | — | IS-11 |
| S46 · Payments by method table | account, confirmation # | param bar + method + **purpose** (bill\|deposit\|plan_down\|prepay) | amount desc | date, method, amount | Method · Count · Amount · % / detail: Date · Account · Method · **Purpose** · Amount (IS-5) | drill → S33 row | — | IS-11 |

*(Other canned reports render KPI + table variants inside S46 per their stories; all downloads via US-REP-003.)*

## Stories

---
id: US-REP-005
epic: EP-REP-02
module: reports
screens: [S46]
wave: 5
status: draft
blocked_by: []
depends_on: [US-REP-002, US-LED-002, US-CUS-021, US-PAY-013]
journeys: [J5, J4]
rules: [BR-REP-001, BR-REP-008, BR-REP-011, BR-CUS-048, BR-PAY-032]
golden_tests: [GT-16]
finance_calc: confirmed
---
### US-REP-005 — AR aging summary + DSO trend: opening buckets age forward, posting basis

**1 · Details** — As Finance/Owner staff, I want the **AR aging summary** (A14 fully-built table): columns **Account · Customer · Class · Current · 1–30 · 31–60 · 61–90 · 90+ · Total** (⚠ **five money bands since 2026-09-24 — `P2.21` / `DEF-REP-6659`**; this line said four until then, `BR-REP-030` is PO-confirmed at five, and the Finance blueprint p035 draws and names five. No figure moved: `current` split in two), sum per bucket + totals footer, KPI strip (Total AR · Current · 1–30 · 31–60 · 61–90 · 90+ with %), group-by per the S46 param bar. Buckets derive from **open-invoice due-date math** (BR-CUS-016 pattern — display states never stored) **plus imported opening buckets aging forward from the cutover as-of date** (BR-CUS-048, BR-REP-008); "days late" where shown = today − the OLDEST unpaid invoice's due date (BR-PAY-032); Σ buckets foots to the AR tie-out (BR-REP-008/BR-LED-007). And the **Days sales outstanding** card (A14: "DSO trend over 12 months"): DSO = **(AR ÷ billed last 12 months) × 365, rolling, posting basis** (BR-REP-011). Both reports are billing-side money → **POSTING basis, labeled** (BR-REP-001). Class filter includes Government (BR-REP-006). Entry: S44 → viewer. Exit: IS-11 downloads (US-REP-003).

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-REP-011 | DSO = (AR ÷ billed last 12 months) × 365, rolling, posting basis. | CONFIRMED — PO RQ-3, 2026-08-08 |
| BR-REP-008 | Aging includes opening buckets aging forward; foots to the AR tie-out. | CONFIRMED — audit F-15/22, 2026-08-08 |
| BR-CUS-048 *(consumed)* | Opening balances = aged buckets, aging forward by calendar days from cutover. | CONFIRMED — PO AC-3 (GT-16) |
| BR-PAY-032 *(consumed)* | "Days late" everywhere = today − oldest unpaid invoice's due date. | CONFIRMED — PO PP-1, 2026-08-08 |
| BR-REP-001 | Billing-side money = posting basis, labeled on the header. | CONFIRMED — PO ruling 2026-08-08 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Prototype-shape render | Buckets per account + footer = Σ per bucket; KPI strip ties to footer exactly (prototype: 184,320 = 118,240 + 34,120 + 18,540 + 13,420) |
| TC-2 | Imported account A-12103, 30 days after cutover 2026-08-31 (GT-16) | Buckets read 31–60 ← 84.20 · 61–90 ← 62.10 · 90+ ← 121.00 (forward aging, BR-CUS-048); total 267.30 unchanged |
| TC-3 | Foot to tie-out | Σ report buckets = AR tie-out figure (LE-1 month: **152.32**) — any drift is the US-LED-004 red flag, never a report-side adjustment |
| TC-4 | DSO card | Value = (AR ÷ billed-last-12-mo) × 365 per BR-REP-011; 12 monthly points, rolling; posting basis |
| TC-5 *(basis label)* | Header + PDF/CSV | "Posting basis" on the aging and DSO headers and in the file basis segment — unlabeled render = FAIL (BR-REP-001) |
| TC-6 *(negative)* | Payment posted by due date but not yet cleared (BR-PAY-021) | The invoice is NOT past due — account absent from overdue buckets; the clearing date never drives aging |
| TC-7 *(isolation)* | Lone Star Ridge run | Its accounts only (RLS) |

**4 · Test Data** — LE-1 month (AR 152.32 = 135.90 + 16.42). GT-16 import: A-12103 buckets 84.20 / 62.10 / 0.00 / 121.00 = 267.30, cutover 2026-08-31. Prototype strip for layout (184,320 split). Class fixture incl. Government account A-11900. Actors: Norma Reyes. Isolation: J. Okafor.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Bucket columns | S46 | A14 §Fully-built + BR-CUS-016/048 | open-invoice due-date math + `account_opening_buckets` (r9 #2) aged forward | numeric(18,6) | computed-display | derived, never stored; Σ = AR tie-out |
| Class | S46 | A14 + BR-REP-006 | consumer category | enum | computed-display | 4 classes incl. Government |
| Days late (available column) | S46 | BR-PAY-032 | today − oldest unpaid due date | int/days | computed-display | single ruled definition |
| KPI strip | S46 | A14 §Fully-built | Σ over rows | $/% | computed-display | ties to footer |
| DSO trend | S46 | prototype card + BR-REP-011 | formula over AR + billed-12-mo (posting) | days | computed-display | rolling 12 points |
| Basis label | S46 | BR-REP-001 | rendered header + file segment | text | computed-display | required |

**6 · Acceptance**
- Given the fixtures, Then buckets, footer, KPI strip and the tie-out foot exactly, with opening buckets aged forward from cutover.
- Given DSO, Then the BR-REP-011 formula is the only computation and the trend is rolling posting-basis.
- Given labels/tenants, Then no unlabeled money renders and nothing crosses.

**7 · Finance Calculation** — CONFIRMED (formulas ruled; worked numbers from the workbooks): DSO formula per BR-REP-011: **(AR ÷ billed last 12 mo) × 365**. Forward aging per GT-16 fixture: A-12103 Σ buckets = **267.30**; 30 days post-cutover the 84.20/62.10/121.00 amounts sit one bucket older (US-LED-009 TC-3 verbatim). AR foot: **152.32** = 135.90 + 16.42 (LE-1).

**8 · Open Questions** — None.

---
id: US-REP-006
epic: EP-REP-02
module: reports
screens: [S46]
wave: 5
status: draft
blocked_by: []
depends_on: [US-REP-002, US-BIL-005, US-BIL-013, US-BIL-014, US-LED-002]
journeys: [J5, J2]
rules: [BR-REP-001, BR-REP-006, BR-BIL-018, BR-BIL-019]
golden_tests: []
finance_calc: confirmed
---
### US-REP-006 — Billing register (bill_type-aware) + Revenue by service & rate (invoice-line read-model)

**1 · Details** — As staff, I want two billing-side reports (POSTING basis, labeled — BR-REP-001): **① Billing register** (A14 fully-built): columns **Bill # · Account · Customer · Services · Usage · Amount · Flag** + the **`bill_type` column + filter** (cycle | first | final | rebill | backbill | penalty — A14 addendum item 6, B2 r10 #12); KPIs Bills in cycle · Average bill · Estimated · Exceptions; usage always with its explicit unit (CLAUDE.md #3 — prototype "684 kWh", "26.24 kgal"); rows = ISSUED invoices of the selected cycle/period (immutable register). **② Revenue by service & rate** (A14 fully-built): columns **Service · Rate schedule · Accounts · Usage rev · Base · Tax · Total** + totals footer + KPIs — an **invoice-line read-model with source drill-back** (A14 item 9: rate schedule is NOT a journal dimension; BR-LED-001 stands), reconciling by service to the S36 dimension view (BR-REP-002/LE-2). Services = the tenant-enabled set (BR-REP-006). Entry: S44 cards. Exit: IS-11 downloads.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-BIL-018 *(consumed)* | Back-bills price per sub-period on the tariff version in force then; reason-coded + approval-gated — the register shows them typed `backbill`. | CONFIRMED — PO new scope, 2026-08-08 |
| BR-BIL-019 *(consumed)* | Penalty bills = charge-code lines only; assessed reads priced by the engine — typed `penalty`. | CONFIRMED — PO new scope, 2026-08-08 |
| A14 item 6 / B2 r10 #12 | `bill_type` is a first-class register column + filter. | CONFIRMED — reports audit 2026-08-08 |
| A14 item 9 | Revenue by service & rate = invoice-line read-model with drill-back; rate schedule never becomes a dimension. | CONFIRMED — reports audit 2026-08-08 |
| BR-REP-001 / BR-REP-006 | Posting basis labeled; live service vocabulary. | CONFIRMED — PO ruling / audit F-17 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Register for the LE-1 month | 3 bills · billed **553.69** (247.87 + 16.42 + 289.40); average **184.56** (553.69 ÷ 3, 2dp display); WE-7B row typed `final`; usage shown with units |
| TC-2 | bill_type filter = backbill / penalty | WE-10 back-bill **305.18** and WE-11 penalty **626.42** rows return, typed correctly; `cycle` filter excludes both |
| TC-3 | Revenue by service & rate, WE-1 slice | Service split reproduces LE-2: Electric 100.60 · Water 47.50 · Sewer 15.80 · Trash 18.00 · Solar 40.00 (+ fee line); by-service totals reconcile to the S36 dimension view to the cent (BR-REP-002) |
| TC-4 | Drill-back | A rate-schedule row opens its invoice lines (source drill-back); services listed = tenant-enabled set, never a hardcoded trio (BR-REP-006) |
| TC-5 *(basis label)* | Both reports + files | "Posting basis" on headers and in the filename basis segment — unlabeled = FAIL (BR-REP-001) |
| TC-6 *(negative)* | A draft (unissued) invoice in the cycle | Never appears in the register — the register reads issued, immutable invoices only (CLAUDE.md #4 family); Estimated KPI counts estimate-flagged bills, not drafts |
| TC-7 *(isolation)* | Lone Star Ridge register | Its invoices only (RLS) |

**4 · Test Data** — LE-1 month bills (WE-1 247.87 · WE-3 16.42 · WE-7B 289.40). WE-10 back-bill 305.18 (6 period groups across tariff v3/v4). WE-11 penalty 626.42 (assessed TOU reads + TAMPER 500.00 charge code). LE-2 revenue split. Register layout per prototype (cycle 08-A sample). Actors: Sam Alvarez, Norma Reyes. Isolation: J. Okafor.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Register row | S46 | A14 §Fully-built | issued `invoices` + lines of cycle/period | row | computed-display | issued only; immutable source |
| bill_type column/filter | S46 | A14 item 6 | `invoices.bill_type` (r10 #12) | enum | computed-display | 6-value vocabulary (BR-REP-006) |
| Usage column | S46 | A14 + CLAUDE.md #3 | billed quantities + explicit unit | qty+unit | computed-display | unit always shown |
| Flag column | S46 | A14 (High/Est) | run outcome read-model (S31.2/31.3 family) | enum | computed-display | — |
| Revenue table | S46 | A14 §Fully-built + item 9 | `invoice_lines` grouped service × tariff (usage/base/tax split) | numeric(18,6) | computed-display | reconciles to S36 by service |
| Drill-back | S46 | A14 item 9 | row → source invoice lines | rows | computed-display | every figure |
| KPIs + footer | S46 | A14 | Σ over rows | $/counts | computed-display | tie exactly |

**6 · Acceptance**
- Given the fixtures, Then the register foots (553.69 / avg 184.56) with bill_type first-class and units explicit.
- Given the revenue report, Then the invoice-line read-model reconciles by service to the dimension view and every row drills back.
- Given labels/tenants, Then posting labels render everywhere and nothing crosses.

**7 · Finance Calculation** — CONFIRMED (workbook figures verbatim, fixture arithmetic only): register Σ = 247.87 + 16.42 + 289.40 = **553.69**; average = 553.69 ÷ 3 = **184.56** (2dp display). Back-bill WE-10 total **305.18** (each sub-period on ITS tariff version). Penalty WE-11 total **626.42** = usage 115.50 + tax 10.92 + TAMPER 500.00. Revenue slice = LE-2 verbatim.

**8 · Open Questions** — None.

---
id: US-REP-007
epic: EP-REP-02
module: reports
screens: [S46]
wave: 5
status: draft
blocked_by: []
depends_on: [US-REP-002, US-PAY-001, US-PAY-004]
journeys: [J5]
rules: [BR-REP-001, BR-REP-013, BR-REP-014, BR-PAY-012, BR-PAY-021]
golden_tests: []
finance_calc: confirmed
---
### US-REP-007 — Payments by method: purpose-aware, clearing basis, intents excluded

**1 · Details** — As staff, I want the **Payments by method** report (A14 card "ACH / Card / Check / Cash"): method summary (count · amount · % per method; methods = the tenant's payment-method reference data, BR-REP-006 — never a hardcoded four) + detail rows carrying the **`purpose` column + filter** (bill | deposit | plan_down | prepay — A14 addendum item 6, BR-PAY-012). It is a cash-side report → **CLEARING basis, labeled** (BR-REP-001); both `posted_at` and `cleared_at` are available detail columns (BR-PAY-021 — staff always see both dates). **Collection framings count BILL-purpose payments only; deposit/plan-down/prepay render as their own lines, never inside collection %** (BR-REP-014). Autopay **capture intents are never counted** — they are not money (BR-PAY-015, A14 item 10). Deposit-batch "day" context cross-refs BR-REP-013 (posting = drawer day; the batch surfaces themselves are payments-owned S37). Entry: S44 card. Exit: IS-11 downloads.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-PAY-012 *(consumed)* | Every payment carries a purpose bill\|deposit\|plan_down\|prepay. | CONFIRMED — PO PA-1, 2026-08-08 |
| BR-REP-014 | Collections KPIs count BILL-purpose only; other purposes = their own lines. | CONFIRMED — PO RQ-6, 2026-08-08 |
| BR-REP-001 | Cash/bank-side numbers read the CLEARING date; header labeled. | CONFIRMED — PO ruling 2026-08-08 |
| BR-PAY-021 *(consumed)* | Posting ≠ clearing — both dates always available. | CONFIRMED — PO explicit ruling, 2026-08-08 |
| BR-REP-013 *(consumed)* | Deposit-batch day = posting date (drawer day) — context note where batch references render. | CONFIRMED — PO RQ-5, 2026-08-08 |
| BR-PAY-015 *(consumed)* | Capture intents excluded from every cash figure. | CONFIRMED — PO PA-4, 2026-08-08 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | PE-10 receipt day | Check line **471.39** (292.87 + 142.30 + 36.22) · Cash line **121.78** (105.36 + 16.42) · total **593.17**; % per method over the total; detail rows tie |
| TC-2 | Purpose filter | A 150.00 deposit-purpose payment appears under `deposit`, NEVER inside any bill-collection line or % (BR-REP-014) |
| TC-3 *(basis)* | Payment posted Jul 31, cleared Aug 2 | Appears in AUGUST's clearing-basis report; July billing-side reports still treat it on-time (BR-PAY-021) — the divergence is visible via both date columns |
| TC-4 *(basis label)* | Header + files | "Clearing basis" on the header and filename basis segment — unlabeled = FAIL (BR-REP-001) |
| TC-5 *(negative)* | Open autopay capture intent in period | Not counted anywhere — intents are not money (BR-PAY-015); an "autopay scheduled" framing may reference them only outside cash totals (A14 item 10) |
| TC-6 | Method vocabulary | Methods listed = the tenant's payment-method lookup (BR-REP-006); a tenant-added method ("Money order") appears |
| TC-7 *(isolation)* | Lone Star Ridge run | Its payments only (RLS) |

**4 · Test Data** — PE-10 receipts: checks 292.87 + 142.30 + 36.22; cash 105.36 + 16.42 (payments workbook, US-PAY-005 fixture). Deposit-purpose fixture: 150.00 (WE-6 deposit). Intent fixture: 2 open intents (US-PAY-024). File: `brazos-bend_payments_by_method_2026-07_clearing_20260805.csv`. Actors: Priya Menon, Norma Reyes. Isolation: J. Okafor.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Method summary (count/amount/%) | S46 | A14 card + prototype | Σ `payments` cleared in period, by method | $/counts/% | computed-display | Σ% = 100; clearing basis |
| Purpose column/filter | S46 | A14 item 6 | `payments.purpose` (r12 #2) | enum | computed-display | 4-value vocabulary; BILL-only in collection framings |
| Posted / cleared dates | S46 | BR-PAY-021 | `payments.posted_at`, `.cleared_at` (r12 #1) | timestamps | computed-display | both available |
| Method vocabulary | S46 | BR-REP-006 | payment-method lookup (reference data) | enum | reference-data | live set |
| Basis label | S46 | BR-REP-001 | rendered header + file segment | text | computed-display | required |

**6 · Acceptance**
- Given PE-10, Then method lines foot (471.39 / 121.78 / 593.17) on the clearing basis with purposes first-class.
- Given purposes and intents, Then non-bill purposes never pollute collection framings and intents count nowhere.
- Given labels/tenants, Then the clearing label renders everywhere and nothing crosses.

**7 · Finance Calculation** — CONFIRMED (PE-10 fixture arithmetic, machine-checkable): checks 292.87 + 142.30 + 36.22 = **471.39**; cash 105.36 + 16.42 = **121.78**; total **593.17**. Collection-% interplay per BR-REP-009/014: only BILL-purpose applications enter any collection figure (LE-1 worked case: 401.37 ÷ 553.69 = **72.49%**, deposit application included, transfer + prior-period excluded — US-LED-007 §7 verbatim).

**8 · Open Questions** — None.

---
id: US-REP-008
epic: EP-REP-02
module: reports
screens: [S46]
wave: 5
status: draft
blocked_by: []
depends_on: [US-REP-002, US-MET-011, US-MET-014, US-CUS-001]
journeys: [J2]
rules: [BR-REP-006, BR-REP-012, BR-MET-049, BR-MET-021, BR-CUS-055]
golden_tests: []
finance_calc: none
---
### US-REP-008 — Operations canned set: read completeness (channel-aware) · high-usage exceptions · new & closed accounts

**1 · Details** — As staff, I want the three A14 operations reports as read-models: **① Read completeness** ("Missing / estimated by route", A14): completeness is **per plan-required channel set** (BR-MET-049, B2 r8 — TOU plans require their windows, demand plans +demand; flat = total), read rows carry the **`channel` column** (A14 item 6); **read-less services are never counted missing** (workbook WE-17 principle); estimated reads labeled with method (US-MET-014 contract); grouped by route/cycle. **② High-usage exceptions** ("Accounts over threshold", A14): read-model over the flag-engine outcomes (BR-MET-021/022) — thresholds are tenant config (BR-MET-020), **never hardcoded**; consumption always with its explicit unit (CLAUDE.md #3). **③ New & closed accounts** ("Churn and growth by month", A14): **"New" = accounts created in period, with status breakdown shown; the Active-accounts figure = Active + Marked disconnect + Vacation hold; Pending activation + Closed excluded** (BR-REP-012); statuses read the seeded, tenant-extensible lookup + behavior classes (BR-CUS-055); "Closed" = stored status Closed (BR-CUS-016 pattern). Entry: S44 cards. Exit: IS-11 downloads (CSV always; counts, no money basis — money-free reports carry no basis label, per BR-REP-001's scope = money numbers).

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-MET-049 *(consumed)* | Completeness = the plan-required channel set per meter (VEE gate billing consumes). | CONFIRMED — PO RD-2 |
| BR-MET-021/022 *(consumed)* | Flag vocabulary + engine outcomes; flags never block billing by themselves. | CONFIRMED — PO closure batch |
| BR-MET-020 *(consumed)* | Thresholds tenant-config, never hardcoded. | CONFIRMED — PO R6 (OQ-002 closure) |
| BR-REP-012 | New = created-in-period w/ status breakdown; Active KPI = Active + Marked disconnect + Vacation hold. | CONFIRMED — PO RQ-4, 2026-08-08 |
| BR-CUS-055 *(consumed)* | Status vocabulary = seeded, tenant-extensible lookup + behavior classes. | CONFIRMED — PO OQ-058 (b) |
| BR-REP-006 | Channel / status / service filters = live vocabularies. | CONFIRMED — audit F-17..21 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Completeness: unit 12A on a TOU plan, tou_off missing at window close | Meter listed incomplete naming the missing channel `tou_off` (BR-MET-049 — mirrors US-MET-011 gate outcome); flat meters judged on `total` only |
| TC-2 | Read-less services | Broadband/Trash rows never counted missing (WE-17: "completeness gate skips read-less services") |
| TC-3 | Estimated labeling | Estimated reads show per-channel estimation labels + consecutive count (US-MET-014 contract); channel column present on every read row (A14 item 6) |
| TC-4 | High-usage report | Rows = flag-engine High outcomes over the tenant's configured thresholds (BR-MET-020/021); usage shown with unit; changing the tenant threshold changes membership — no constant anywhere |
| TC-5 | New & closed month | "New" = created-in-period with status breakdown (e.g. 12 new: 9 Active, 3 Pending activation); Active KPI counts Active + Marked disconnect + Vacation hold only (BR-REP-012); Closed = stored status |
| TC-6 *(negative)* | Pending-activation account in the Active KPI; tenant-added status unmapped | Pending never counts Active (BR-REP-012); a tenant-added status renders via its behavior class (BR-CUS-055) — never dropped, never guessed |
| TC-7 *(isolation)* | Lone Star Ridge runs | Its meters/accounts/routes only (RLS) |

**4 · Test Data** — TOU meter M-7450 (unit 12A) missing tou_off (US-MET-011 TC-14 fixture); Broadband add-on account (WE-17); high-usage fixture: Ridge Coffee 26.24 kgal vs trailing average (prototype flag "High"); accounts month: 12 created (9 Active / 3 Pending), 4 closed; statuses incl. Vacation hold + tenant-added "Seasonal". Actors: Sam Alvarez. Isolation: J. Okafor.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Completeness rows | S46 | A14 card + BR-MET-049 | read-model over `meter_reads` (channel set, r8) vs plan-required set via service fn | rows/% | computed-display | read-less services excluded |
| Channel column | S46 | A14 item 6 + B2 r8 | `meter_reads.channel` | enum | computed-display | live vocabulary |
| Estimation labels | S46 | US-MET-014 contract | estimation method + consecutive count on read rows | text | computed-display | labeled, never silent |
| High-usage rows | S46 | A14 card + BR-MET-021 | flag-outcome read-model; thresholds from read-validation settings (S64) | rows | computed-display | tenant thresholds only |
| New/closed rows + Active KPI | S46 | A14 card + BR-REP-012 | `accounts.created_at` in period + status lookup (BR-CUS-055) | counts | computed-display | Active = A+MD+VH exactly |

**6 · Acceptance**
- Given the read fixtures, Then completeness is channel-set-aware, read-less services never flag, and estimates are labeled.
- Given thresholds and statuses, Then membership follows tenant config and the BR-REP-012 definitions exactly.
- Given tenants, Then nothing crosses.

**7 · Finance Calculation** — N/A (count/consumption read-models; consumption always with explicit unit per CLAUDE.md #3).

**8 · Open Questions** — None.

---
id: US-REP-009
epic: EP-REP-02
module: reports
screens: [S46]
wave: 5
status: draft
blocked_by: []
depends_on: [US-REP-002, US-BIL-015, US-BIL-013, US-BIL-014, US-BIL-019, US-PAY-012, US-PAY-016, US-NOT-013]
journeys: [J5, J6]
rules: [BR-REP-007, BR-REP-001, BR-BIL-014, BR-BIL-017, BR-BIL-016, BR-PAY-018, BR-PAY-020]
golden_tests: []
finance_calc: confirmed
---
### US-REP-009 — The six audit-added reports: corrections · back-bills/penalty · write-offs · budget status · delivery-queue health · returned mail

**1 · Details** — As staff (audience per A14 item 5), I want the six BR-REP-007 canned reports, each a pure read-model over its owning module's ratified data: **① Bill corrections** (compliance): reason code · scope (single/bulk) · approver · money deltas (credit note / rebill / balance delta) per correction case (BR-BIL-014, B2 r10 #9). **② Back-bills & penalty bills** (compliance): bill_type backbill|penalty rows with covered periods, tariff versions priced against, reason code, approver (BR-BIL-018/019). **③ Write-offs** (finance): initiator · approver · bad-debt GL · aging-at-write-off (BR-PAY-020; direct method per BR-LED-008); shown separately from collections always (BR-REP-009). **④ Budget billing status**: level · actuals · variance balance · drift vs ±re-level band · settle-up month · off-budget events (BR-BIL-017, r10 #5). **⑤ Delivery-queue health** (operations): queued/sent/delivered/failed/bounced counts + failure detail with a **link to the owning re-queue surfaces** (BR-BIL-016/BR-NOT-005 — operation stays with US-NOT-013/US-BIL-024; this report only reads the same queue rows). **⑥ Returned mail & bad addresses** (operations): delivery-return events + flagged accounts + suppression state (BR-PAY-018). Money columns = POSTING basis, labeled (BR-REP-001). Entry: S44 cards. Exit: IS-11 downloads.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-REP-007 | These six ARE the canned-set additions, as read-models of BR-BIL-014/016/017/018/019 + BR-PAY-018/020; ship wave RQ-9. | CONFIRMED — audit F-4/5/7..13, 2026-08-08 |
| BR-BIL-014 *(consumed)* | Corrections: approval-gated; NO money-bearing write before approval — the report can only ever show approved/executed money. | CONFIRMED — PO A-5 + OQ-072 closure |
| BR-BIL-017 *(consumed)* | Budget parameters (level, ±20% drift, settle-up, 2-miss drop) are tenant settings with seeded defaults. | CONFIRMED — PO A-2, 2026-08-08 |
| BR-BIL-016 / BR-NOT-005 *(consumed)* | Queue statuses queued→sent→delivered/failed/bounced; the queue is platform-wide; re-queue lives with its owners. | CONFIRMED — PO A-7 / PO volume ruling |
| BR-PAY-018 *(consumed)* | Returned mail: flag → needs-attention → paper suppressed until verified; balances unaffected. | CONFIRMED — PO PA-7, 2026-08-08 |
| BR-PAY-020 / BR-LED-008 *(consumed)* | Write-offs initiated in Payments, approved + reported in Finance; direct write-off v1. | CONFIRMED — PO PA-9 / PO LF-8 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Corrections report, WE-9 case | Row: reason "read correction 8→6 kgal" · scope single · approver (System Admin) · credit note **−247.87** · rebill **+227.95** · net **−19.92**; drills to the case |
| TC-2 | Back-bills & penalty | WE-10: backbill **305.18**, 6 covered periods, tariff v3+v4 named per sub-period, approver shown; WE-11: penalty **626.42** with assessed-read flags + TAMPER 500.00 charge-code line — no hand-typed amount anywhere (BR-BIL-019) |
| TC-3 | Write-offs | V-5 row: 135.90 · initiator (Payments) · approver (Owner) · GL 6900 Bad debt · aging-at-write-off; figure matches the S36 "Written off YTD" KPI and NEVER enters collection % (BR-REP-009) |
| TC-4 | Budget status | WE-8 row: level **242** · actuals 292.87 / 231.40 / 198.75 · variance −50.87 → −40.27 → **+2.98** · settle-up month shown; drift band = the tenant's setting (seeded ±20%) |
| TC-5 | Delivery-queue health + returned mail | Counts tie to the US-NOT-013 dashboard exactly (same rows, BR-REP-002); failures list with re-queue LINK (no send action here); returned-mail rows show flag + suppression state, balances untouched (BR-PAY-018) |
| TC-6 *(negative)* | Correction case pending approval | Appears with status pending and NO money deltas — no money-bearing rows exist before approval (BR-BIL-014); report totals exclude it |
| TC-7 *(basis label)* | Money columns on ①–④ | "Posting basis" on headers + file segments — unlabeled = FAIL (BR-REP-001) |
| TC-8 *(isolation)* | Lone Star Ridge runs | Its cases/queue/accounts only (RLS) |

**4 · Test Data** — WE-9 (−247.87 / +227.95 / −19.92, Admin-approved). WE-10 (305.18, v3→v4). WE-11 (626.42). V-5 write-off (135.90, DR 6900 / CR AR). WE-8 budget (242; −50.87/−40.27/+2.98). Queue fixture: 500-batch with 3 failed + 1 bounced (US-NOT-013 fixture). Returned mail: Park, Jenna A-11455 flagged, paper suppressed. Actors: Norma Reyes, Alex Reed. Isolation: J. Okafor.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Correction rows | S46 | A14 item 5 + BR-BIL-014 | `correction_cases` (+ linked credit_notes/rebills) r10 #9 | rows/$ | computed-display | approved money only |
| Back-bill/penalty rows | S46 | A14 item 5 + BR-BIL-018/019 | `invoices` bill_type backbill\|penalty + tariff-version refs + reason/approver | rows/$ | computed-display | engine-priced only |
| Write-off rows | S46 | A14 item 5 + BR-PAY-020 | `write_offs` (r12 #11) + GL + aging snapshot | rows/$ | computed-display | approved rows; separate from collections |
| Budget rows | S46 | A14 item 5 + BR-BIL-017 | `account_budget_status` (r10 #5) + tenant budget settings | rows/$ | computed-display | parameters = tenant settings |
| Queue-health rows | S46 | A14 item 5 + BR-BIL-016/BR-NOT-005 | `outbound_messages` statuses (r12 #16) | counts/rows | computed-display | read-only; link to owners |
| Returned-mail rows | S46 | A14 item 5 + BR-PAY-018 | delivery-return events + `accounts.bad_address` (r12 #8) | rows | computed-display | balances unaffected |
| Basis labels | S46 | BR-REP-001 | rendered on money reports | text | computed-display | required |

**6 · Acceptance**
- Given the fixtures, Then each of the six reports reproduces its owning module's rows verbatim with deltas/approvers/versions visible.
- Given pending approvals, Then no unapproved money renders anywhere; given the queue, Then this surface reads and links, never operates.
- Given labels/tenants, Then posting labels render on money reports and nothing crosses.

**7 · Finance Calculation** — CONFIRMED (workbook figures verbatim): WE-9 net = −247.87 + 227.95 = **−19.92**. WE-10 = 3 × 45.10 + 3 × 47.84 → taxable 278.82 + tax 26.36 = **305.18**. WE-11 = 115.50 + 10.92 + 500.00 = **626.42**. WE-8 variance chain: −50.87 → −40.27 → **+2.98**. V-5 write-off **135.90** (DR 6900 / CR AR at approval).

**8 · Open Questions** — None.
