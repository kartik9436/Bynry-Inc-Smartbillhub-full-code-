# EP-LED-03 — S36 Revenue & AR, trial balance, ledger reports (S36 · S56 · S59 · S60)

**Module:** ledger · **Wave:** W5 · **Screens:** S36, S56, S59, S60 · **Status:** draft (BR-LED-001..016 + BR-REP-001..018 all CONFIRMED; schema B2 Addendum r13)

## Scope
**In:** the read-model surfaces over journal-line dimensions (BR-REP-002 — never a side-maintained number): **S36 Revenue & AR** with the full KPI strip + revenue-by-service + billed-vs-collected + aging + adjustments panels and the tie-out panel render (BR-LED-016, BR-LED-007 via US-LED-004; A1 addendum 2026-08-08) · **S56 trial balance** with period + premises filters, dimension expansion and export (BR-LED-009; J5 step-2 contract: *debits=credits, premises filter resolves via unit chain*) · **Account ledger report S59** with the FULL source vocabulary + running balance (BR-LED-010, BR-REP-008) · **By-premises summary S60** (BR-LED-011). Every download per IS-11 (BR-REP-018); every money number basis-labeled (BR-REP-001).
**Out:** tie-out computation (US-LED-004) · manual-JE list (EP-LED-04) · remittance report (EP-LED-05) · the generic report library/viewer/builder S44–S47 (reports module) · deposits/bank surfaces S37–S40 (payments EP-PAY-06).
**Tables:** read-only over `journal_entries`/`journal_lines` (+dimensions r13 #1), `ledger_accounts`, registers (accounts, invoices, payments, write_offs, account_opening_buckets).

## Capability matrix (list screens only — B9 conformance)
| Screen | Search fields | Filters | Default sort | Sortable | Columns default/available | Row actions | Bulk actions | Export |
|---|---|---|---|---|---|---|---|---|
| S56 · Trial balance | GL code, name | period, premises (A14 r2) | code asc | code, name, type, debit, credit | GL account · Name · Type · Debit · Credit / +QBO ref, Xero ref (IS-5) | Expand → dimension breakdown (BR-LED-009) | — | Export trial balance: CSV + PDF (IS-11) |

*(S36 is a dashboard tab — KPI/panel layout, no IS-2 list. S59/S60 are parameterized report viewers — parameter bar + result table per A14, downloads per IS-11.)*

## Stories

---
id: US-LED-007
epic: EP-LED-03
module: ledger
screens: [S36]
wave: 5
status: draft
blocked_by: []
depends_on: [US-LED-002, US-LED-004, US-BIL-005, US-PAY-012]
journeys: [J5]
rules: [BR-LED-016, BR-LED-007, BR-LED-015]
golden_tests: []
finance_calc: confirmed
---
### US-LED-007 — S36 Revenue & AR: KPI strip + panels, all dimension-derived, basis-labeled

**1 · Details** — As Finance/Owner staff, I want the S36 Revenue & AR tab rendered ENTIRELY from journal-line dimensions (BR-LED-016: "revenue, collected, AR, aging buckets — all dimension-derived"; BR-REP-002): the **KPI strip** — Billed this month · Collected (with collection % per BR-REP-009) · Still owed (accounts count + DSO per BR-REP-011) · Written off YTD (prototype layout) — the **Revenue by service** table (Service · Usage revenue · Base & fees · Tax · Total billed · Collected, per prototype; services = the tenant-enabled set, BR-REP-006), **Billed vs collected · last 12 months** chart, **Who owes you** aging panel (Current/31–60/61–90/90+ with % — imported opening buckets age forward per BR-CUS-048), the **Adjustments & credits** panel (credits/debits/late fees + pending-approval link), and the **tie-out panel** (computed by US-LED-004). **Every header labels its date basis** (BR-REP-001: billed/revenue/AR/aging/collection % = POSTING; nothing unlabeled). Collections KPIs count BILL-purpose payments only (BR-REP-014); capture intents excluded (A14 item 10). Entry: sidebar Finance. Exit: numbers that foot to the trial balance and registers to the cent.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-LED-016 | S36 KPI strip: revenue, collected, AR, aging buckets — all dimension-derived. | CONFIRMED — PO LB-8, 2026-08-08 |
| BR-LED-007 | Tie-out panel renders on S36 (computation = US-LED-004). | CONFIRMED — PO LF-7, 2026-08-08 |
| BR-REP-001 *(consumed)* | Billing-side numbers = POSTING date; every KPI/report header labels its basis. | CONFIRMED — PO ruling 2026-08-08 |
| BR-REP-009 *(consumed)* | Collection % = cash applied to bills in period ÷ billed in period, posting basis; applied deposits count; write-offs excluded, shown separately. | CONFIRMED — PO RQ-1, 2026-08-08 |
| BR-REP-011 *(consumed)* | DSO = (AR ÷ billed last 12 months) × 365, rolling, posting basis. | CONFIRMED — PO RQ-3, 2026-08-08 |
| BR-REP-014 *(consumed)* | Collections KPIs count BILL-purpose payments only. | CONFIRMED — PO RQ-6, 2026-08-08 |
| BR-LED-015 | Money-export actions from the tab audit. | CONFIRMED — PO LB-7, 2026-08-08 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 *(balance)* | LE-1 month renders | Billed **553.69** = Σ issued invoice postings; Collected **401.37** (247.87 payment applied to the period bill + 153.50 applied deposit; the 45.00 prior-period application excluded per BR-REP-009); collection % **72.49%**; Still owed **152.32** = AR tie-out; all foot to the S56 trial balance |
| TC-2 | Revenue by service table | Rows = LE-2 dimensions (Electric 100.60 · Water 47.50 · Sewer 15.80 · Trash 18.00 · Solar 40.00 + fee line); services listed = tenant-enabled set, never a hardcoded trio (BR-REP-006) |
| TC-3 | Aging panel | Buckets derived from open-invoice due-date math + opening buckets aged forward from cutover (BR-CUS-048); Σ buckets = Still owed KPI |
| TC-4 | Basis labels | Every KPI/panel header carries "posting basis"; write-offs render as their own KPI, never inside collection % (BR-REP-009); deposit/plan-down/prepay purposes never in Collected (BR-REP-014) |
| TC-5 *(negative)* | KPI computed from the `accounts.balance` cache diverges from dimension-derived AR (simulated bypass) | The strip reads dimensions; the divergence surfaces as US-LED-004 drift red flag — no silent cache number ever renders |
| TC-6 *(isolation)* | Lone Star Ridge S36 | Its dimensions only (RLS); Brazos Bend figures never leak into any panel |

**4 · Test Data** — LE-1/LE-2/LE-6 verbatim (billed 553.69 = 247.87 + 16.42 + 289.40; payment 292.87 of which 247.87 applied to the period bill; deposit applied 153.50; transfer 135.90 — not collected; AR 152.32). Write-off KPI fixture: V-5 135.90 (separate). Prototype layout reference: KPI strip / two-column panels / 12-month chart. Actors: Norma Reyes, Alex Reed. Isolation: J. Okafor.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Billed KPI | S36 | prototype-extracted + BR-LED-016 | Σ issue-entry AR debits in period (dimensions) | numeric(18,6) | computed-display | posting basis, labeled |
| Collected KPI + % | S36 | prototype-extracted + BR-REP-009 | Σ applications to period bills (allocations→journal dimensions) + applied deposits | numeric(18,6)/% | computed-display | BILL purpose only; write-offs excluded |
| Still owed + DSO | S36 | prototype-extracted + BR-REP-011 | AR dimension total; DSO formula | numeric/days | computed-display | = AR tie-out figure |
| Written off YTD | S36 | prototype-extracted + BR-PAY-020 | approved `write_offs` (r12 #11) | numeric(18,6) | computed-display | separate KPI |
| Revenue by service | S36 | prototype-extracted + BR-LED-001 | revenue lines grouped by `service` dimension | rows | computed-display | tenant-enabled services (BR-REP-006) |
| Aging panel | S36 | prototype-extracted + BR-CUS-048 | open-invoice due-date math + opening buckets aged forward | rows | computed-display | Σ = AR |
| Adjustments panel | S36 | prototype-extracted | adjustments/credit_notes read-model + pending-approval count | rows | computed-display | link-out, no writes here |
| Basis labels | S36 | BR-REP-001 | rendered labels | text | computed-display | required everywhere |

**6 · Acceptance**
- Given the LE-1 month, Then every KPI and panel foots to the trial balance and registers to the cent, from dimensions only.
- Given the strip, Then collection % and DSO follow their ruled formulas exactly and every header names its basis.
- Given a cache/dimension divergence, Then it can only surface as a tie-out red flag; given tenants, panels never cross.

**7 · Finance Calculation** — CONFIRMED (composed strictly from LE-1 figures + BR-REP-009): billed-in-period = 247.87 + 16.42 + 289.40 = **553.69**; cash applied to period bills = 247.87 + applied deposit 153.50 = **401.37**; collection % = 401.37 ÷ 553.69 = **72.49%** (transfer 135.90 and prior-period 45.00 excluded; write-offs separate). DSO formula per BR-REP-011: (AR ÷ billed-12-mo) × 365. Aging Σ = **152.32** = Still owed.

**8 · Open Questions** — ~~None.~~ **AMENDED 2026-08-11 (ledger reporting lane, on building §1).** Three of the strip's figures are NOT derivable from journal-line dimensions, and BR-LED-016's *"revenue, collected, AR, aging buckets — all dimension-derived"* holds for two of the four:

| Figure | State | Why |
|---|---|---|
| Billed **553.69** · Still owed **152.32** · accounts owing · revenue by service · written-off YTD | **BUILT**, dimension-derived, foots to the trial balance | Σ over `journal_lines`; the AR row of the trial balance IS the Still-owed KPI |
| Collected **COLUMN** 446.37 | **BUILT** (LE-6's own KPI figure: 292.87 payment + 153.50 applied deposit) | Σ AR credits from cash sources + the deposit-application entries |
| **Collection % (72.49%)** | **NOT DERIVABLE** — returned `None` with the reason | BR-REP-009's numerator is *cash applied to bills IN PERIOD* (**401.37**), and a payment entry credits AR in ONE lump with `source_id` = the payment. Which bill it met lives in payments' `allocations`. The ratio this module COULD compute is 446.37 ÷ 553.69 = **80.62%** — a different ratio wearing the ruled one's name, and it is never returned. Read wanted BY NAME: `apps.payments.selectors.allocated_to_invoices_issued_between(start, end)` |
| **Aging buckets** | **NOT DERIVABLE** — returned `None`; the TOTAL they must sum to (152.32) IS reported | a journal line carries no DUE DATE, and `account_opening_buckets` (B2 r9 #2 / BR-CUS-048) is unbuilt |
| **DSO** | **NOT RENDERED** — **OQ-178** | the formula is exact, the twelve-month denominator is not, for a tenant younger than a year: LE-1's month alone gives (152.32 ÷ 553.69) × 365 = **100.4 days**, a collections emergency computed from two months |
| Per-service **Tax** and **Collected** columns (prototype table) | **NOT DERIVABLE** | a tax line carries no `service` dimension (BR-BIL-069 gives tax its own ACCOUNT per authority, not a service) and cash carries no invoice attribution. LE-2 states the revenue slice and states no per-service tax |

Also amended: **TC-4's cash figures now distinguish REALISED from UNDEPOSITED** (PO ruling 2026-08-11, OQ-143). LE-1's *"1000 Cash 442.87"* renders as **1000 150.00 + 1010 292.87** until the bank confirms; the two are never summed into one "cash" number, and **598.69 = 598.69 is untouched**. Whether a cash DEPOSIT is also undeposited on receipt is **OQ-177**. Built: `apps/ledger/reporting.revenue_and_ar` / `.cash_position` / `.trial_balance`.

---
id: US-LED-008
epic: EP-LED-03
module: ledger
screens: [S56]
wave: 5
status: draft
blocked_by: []
depends_on: [US-LED-002, US-LED-005]
journeys: [J5]
rules: [BR-LED-009, BR-LED-015]
golden_tests: []
finance_calc: confirmed
---
### US-LED-008 — Trial balance (S56): period + premises filters, dimension expansion, export

**1 · Details** — As Finance/Owner staff, I want the read-only **trial balance** on the S56 General ledger tab (A1 r2; A14 r2 columns: GL account · Name · Type · Debit · Credit; **balanced totals footer**): filterable by **period** (derived from fiscal settings, BR-TEN-022 — month/quarter/custom per prototype) and by **premises** (resolves via the account→unit→premises dimension chain, BR-MET-046 — J5 step-2 contract), where **any GL line expands to its dimensions** (BR-LED-009: service / account / premises+unit / source / authority breakdown, A14 item 9), with **Export trial balance** per IS-11 (CSV + PDF with basis label, filters echoed). Posting-basis label on the header (BR-REP-001). Entry: Finance → General ledger tab (J5 step 2). Exit: debits = credits, always; exported file per IS-11 contract.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-LED-009 | Trial balance screen: period + premises filters, any GL line expands to its dimensions, export. | CONFIRMED — PO LB-1, 2026-08-08 (LE-1) |
| BR-TEN-022 *(consumed)* | Periods computed from fiscal settings, not stored. | CONFIRMED — PO R2-B5 |
| BR-MET-046 *(consumed)* | Premises filter resolves via the never-breaking unit chain. | CONFIRMED — PO PU-19 |
| BR-REP-018 *(consumed)* | Download per IS-11 (CSV always + PDF; basis label; filters echoed). | CONFIRMED — PO 2026-08-08 |
| BR-LED-015 | Trial-balance export (money export) writes audit_log. | CONFIRMED — PO LB-7, 2026-08-08 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 *(balance)* | LE-1 period selected | Exactly the LE-1 table: 1000 Cash DR 442.87 · 1200 AR DR 152.32 · deposit interest exp DR 3.50 · revenue CR 506.31 · tax CR 47.38 · 2300 CR 0.00 · 3000 CR 45.00 — footer **598.69 = 598.69 ✔** with "Balanced" |
| TC-2 | Premises filter = 500 Main St | Only lines whose premises dimension = 500 Main St; footer still balances for AR/revenue legs shown with their counterpart context; unit chain resolves per BR-MET-046 (J5 step-2 handoff) |
| TC-3 | Expand the revenue row | Dimension breakdown = LE-2 (by service; drill continues to account/premises/source lines) |
| TC-4 | Export | CSV per IS-11 (snake_case headers, plain 2dp, ISO dates, filename `{tenant}_trial_balance_{period}_{basis}_{generated}.csv`) + PDF skeleton (letterhead, filters echoed, POSTING basis label, generated-by); audit `report.exported` |
| TC-5 *(negative)* | A period with a simulated posting-service bypass (unbalanced state) | The screen cannot render it as balanced — discrepancy surfaces via the US-LED-004 red flag; no client-side "rebalancing" exists |
| TC-6 *(isolation)* | Lone Star Ridge trial balance | Its entries only; premises dropdown lists only its premises (RLS) |

**4 · Test Data** — LE-1 verbatim (table + totals 598.69). Periods: July 2026, Q3 2026, custom Aug 1–15 (fiscal settings per US-TEN-006 fixture). Premises: 500 Main St, Oak Grove, Marina Bay. Export file: `brazos-bend_trial_balance_2026-07_posting_20260805.csv`. Actors: Norma Reyes. Isolation: J. Okafor.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| TB row | S56 | A14 r2 | Σ `journal_lines` per `ledger_accounts` row for the period | numeric(18,6) | computed-display | debits = credits in footer, always |
| Period filter | S56 | prototype-extracted + BR-TEN-022 | computed periods from fiscal settings | enum/dates | user-input | month/quarter/custom |
| Premises filter | S56 | A14 r2 | `journal_lines.premises_id` (r13 #1) | uuid | user-input | tenant premises only |
| Dimension expansion | S56 | BR-LED-009 | line dimensions under the GL row | rows | computed-display | same rows, regrouped |
| Balanced footer | S56 | A14 r2 | Σ DR vs Σ CR | numeric(18,6) | computed-display | equality asserted |
| Export | S56 | IS-11 | streamed file (IS-9 guards, 50k cap, money-export audit) | file | computed-display | CSV + PDF; basis labeled |

**6 · Acceptance**
- Given the LE-1 period, Then the table reproduces LE-1 verbatim and foots 598.69 = 598.69.
- Given filters and expansion, Then premises resolves via the chain and every GL line opens to its dimensions.
- Given export, Then the IS-11 contract holds exactly; given tenants, nothing crosses.

**7 · Finance Calculation** — CONFIRMED (LE-1 verbatim): DR 442.87 + 152.32 + 3.50 = **598.69** · CR 506.31 + 47.38 + 0.00 + 45.00 = **598.69** ✔. Tie-out cross-check: AR row 152.32 = 135.90 + 16.42 (BR-LED-007).

**8 · Open Questions** — ~~None.~~ **AMENDED 2026-08-15 (DEF-112 lane, on building the SCREEN).** `GET /ledger/trial-balance` had been SERVED since 2026-08-11 with **no caller**; S56 now renders it at **Finance → General ledger** (`07-frontend/src/features/ledger/GeneralLedgerPage.tsx`), together with the US-LED-013 journal list, which the prototype does not draw on this tab and which is the ONLY place a DRAFT entry is visible in the product.

**⚠ 598.69 IS THE WHOLE BOOK AND 553.69 IS THE JULY WINDOW, and both are LE-1.** LE-1's opening-balance entry is dated BEFORE July, so the July-windowed trial balance foots at **553.69 = 553.69** and the cumulative book at **598.69 = 598.69**. TC-1's table is the cumulative one. The screen asks for the tenant's own accounting period (BR-TEN-022, served on `GET /settings/regional`) and therefore shows the WINDOWED figure; nothing here re-derives either, and `tests/test_us_led_016_export.py` records the same distinction for the export.

Four parts of §1 are NOT built and each is stated ON SCREEN rather than dropped:

- **TC-2's PREMISES FILTER** — `journal_lines.premises_id` is NULL on every row (US-LED-002 unbuilt) and the endpoint accepts no such param. A dropdown that accepted a premises and changed nothing would make the report LOOK filtered.
- **TC-3's DIMENSION EXPANSION** — there is no read model for one entry's LINES with their dimensions. `GET /ledger/journal-entries/{id}` is NAMED by 11b §2.10 and is NOT SERVED; the read that closes it is `apps.ledger.reporting.journal_entry_detail(entry_id)`, already reported by the ledger API lane. No chevron is drawn on a row that would expand to nothing.
- **TC-4's EXPORT** — `POST /reports/{key}/export` is served by no deployment (TD-17, no job runner), so the control renders DISABLED WITH ITS REASON (BR-SHL-025) rather than vanishing.
- **The prototype's account-mapping TABLE** — five hardcoded source→account rows would be a claim about this tenant's chart. The panel is a LINK to Settings → Configure, where BR-LED-014 puts the live mapping.

**TC-5 IS THE ASSERTION THIS SCREEN TURNS ON and it is green:** an unbalanced period renders UNBALANCED with the served `difference` beside it and an alert saying a journal line was written outside the posting service. There is no client-side rebalancing anywhere in the file — no money value is added, compared or rounded in it at all. **RED-PROVED:** forcing the footer to say *Balanced* fails with `AssertionError: expected '<div class="met-panel">…' not to contain 'Balanced'`. **And an EMPTY period renders as visibly EMPTY** (*"This is an empty book, not a balanced one"*), which is DEF-110's warning taken seriously: the E2E fixture holds one bill dated 30 June, so a July close today would foot 0 = 0 at every step and a tidy green tick would make that look like success.

---
id: US-LED-009
epic: EP-LED-03
module: ledger
screens: [S59]
wave: 5
status: draft
blocked_by: []
depends_on: [US-LED-002, US-CUS-022, US-PAY-001]
journeys: [J5]
rules: [BR-LED-010, BR-LED-015]
golden_tests: []
finance_calc: confirmed
---
### US-LED-009 — Account ledger report (S59): full source vocabulary + running balance → PDF/CSV

**1 · Details** — As staff (also reachable as the "Download ledger" intent from Account detail, A1 r2), I want the **Account ledger report**: params **Account · Premises (location) · From · To** (A14 r2) → dated rows with columns **Date · Type · Reference · Description · Charge · Payment · Running balance** and a period-totals footer → **PDF + CSV** per IS-11 (BR-LED-010). The **Type column carries the FULL source vocabulary** (BR-REP-008): bill · payment · adjustment · refund · **deposit · write-off · opening · remittance · manual JE · transfer** — so the report **foots to the AR tie-out** (nothing invisible); imported opening buckets appear as the opening row and **age forward from the cutover as-of date** (BR-CUS-048). Rows are the account's journal-dimension read-model (BR-REP-002; B2 r2: derived view over the source documents). Posting-basis label on the header (BR-REP-001). Entry: Reports → Account ledger / S21 "Download ledger". Exit: a ledger any auditor can foot.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-LED-010 | Account ledger report: account + premises + date range → dated charges/payments/adjustments + running balance → PDF/CSV. | CONFIRMED — PO LB-2, 2026-08-08 |
| BR-REP-008 *(consumed)* | Type = full source vocabulary (incl. deposit, write-off, opening, remittance, manual JE, transfer); foots to the AR tie-out; opening buckets age forward. | CONFIRMED — reports audit F-15/22, 2026-08-08 |
| BR-CUS-048 *(consumed)* | Opening balances = aged buckets, aging forward from cutover. | CONFIRMED — PO AC-3 (GT-16) |
| BR-REP-018 *(consumed)* | Downloads per IS-11. | CONFIRMED — PO 2026-08-08 |
| BR-LED-015 | Ledger download (money export) audits. | CONFIRMED — PO LB-7, 2026-08-08 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 *(balance)* | ACC-1042, Jul 1–31 | Rows: opening balance **45.00** → bill BL-… **+247.87** → running **292.87** → payment **−292.87** → running **0.00**; footer totals charge 247.87 / payment 292.87; closing = 0.00 |
| TC-2 | ACC-1055 (WE-7B) same range | Vocabulary exercised: final bill +289.40 · deposit application −153.50 (Type=deposit) · transfer −135.90 (Type=transfer, ref ACC-0009) → closing 0.00; the master account's ledger shows the +135.90 transfer-in |
| TC-3 | Imported account A-12103 | Opening row 267.30 dated at cutover 2026-08-31 (Type=opening, GT-16); 30 days later unpaid, aging reads 31–60 ← 84.20 · 61–90 ← 62.10 · 90+ ← 121.00 (forward aging) |
| TC-4 | Premises filter + downloads | Premises param restricts via the account's unit→premises; PDF (letterhead, params echoed, POSTING basis label) + CSV per IS-11; audit `report.exported` |
| TC-5 | Foot to tie-out | Σ closing balances of all account ledgers for the period = AR tie-out figure (BR-REP-008) — LE-1: 135.90 + 16.42 = **152.32** |
| TC-6 *(negative)* | From > To, or an account id outside the tenant | Param validation rejects the range; foreign account 404s (RLS) — never an empty-but-plausible report |
| TC-7 *(isolation)* | Lone Star Ridge run | Its accounts only; premises list its own (RLS) |

**4 · Test Data** — ACC-1042 (500 Main St): opening 45.00, bill 247.87, payment 292.87. ACC-1055 (Marina Bay): 289.40 / −153.50 / −135.90; master ACC-0009 +135.90. A-12103 buckets 84.20/62.10/0.00/121.00 = 267.30, cutover 2026-08-31 (GT-16). Files: `brazos-bend_account_ledger_ACC-1042_2026-07_posting_20260805.csv`. Actors: Sam Alvarez (Staff), Norma Reyes. Isolation: J. Okafor.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Params (account, premises, from, to) | S59 | A14 r2 | query over account dimension read-model (B2 r2 derived view) | uuid/dates | user-input | tenant scope; From ≤ To |
| Type | S59 | BR-REP-008 | `journal_lines.source_type` vocabulary | enum | computed-display | full vocabulary, nothing hidden |
| Reference / Description | S59 | A14 r2 | source document number/memo | text | computed-display | drills to source |
| Charge / Payment / Running balance | S59 | A14 r2 | signed amounts + cumulative | numeric(18,6) | computed-display | running = prior + charge − payment |
| Opening row | S59 | BR-CUS-048/049 | opening JE + `account_opening_buckets` (r9 #2) | numeric(18,6) | system-derived | dated at cutover; ages forward |
| Downloads | S59 | IS-11 | streamed PDF/CSV | file | computed-display | basis label; params echoed; audit |

**6 · Acceptance**
- Given ACC-1042, Then the rows, running balance and footer reproduce the fixture exactly.
- Given the vocabulary accounts, Then deposit/transfer/opening rows appear as first-class types and the report foots to the AR tie-out.
- Given params/roles/tenants, Then validation, RLS and IS-11 hold.

**7 · Finance Calculation** — CONFIRMED (fixture arithmetic, machine-checkable): running balance r_n = r_{n−1} + charge_n − payment_n. Worked (ACC-1042): 45.00 + 247.87 = **292.87**; 292.87 − 292.87 = **0.00** ✔. Foot: Σ closings 135.90 + 16.42 = **152.32** = AR tie-out (LE-1). Opening: GT-16 A-12103 Σ buckets = **267.30**.

**8 · Open Questions** — ~~None.~~ **AMENDED 2026-08-11 (ledger reporting lane, on building §1).** §1, §3 TC-1/TC-2/TC-5 and §7 are **BUILT and green** (`apps/ledger/reporting.account_ledger`): ACC-1042 opens at 45.00, bills to 292.87, pays to 0.00; ACC-1055 exercises **deposit** and **transfer** as first-class Types; the four closings **0.00 + 16.42 + 0.00 + 135.90 = 152.32** equal the AR control to the cent. Three parts of §1 are NOT:

- **The premises parameter (TC-4)** — not offered. Same cause as US-LED-010: `premises_id` is NULL on every journal line (US-LED-002 unbuilt). A parameter that accepted a premises and changed nothing would make the report LOOK filtered, which is worse than not having it.
- **TC-3's FORWARD AGING** — not assertable. `account_opening_buckets` (B2 r9 #2 / BR-CUS-048, GT-16) is unbuilt, so A-12103's 84.20 / 62.10 / 121.00 have nowhere to come from. The opening ROW itself works: an `opening_balance`-sourced entry renders as Type **opening** when the window contains it.
- **The Reference column** shows the source document's **UUID**, not `BL-2607-018204`. A journal line carries the invoice's id; turning it into a number is a per-source-type read that neither billing nor payments publishes. Asked BY NAME: `apps.billing.selectors.invoice_numbers_for(ids)` / `apps.payments.selectors.payment_numbers_for(ids)`. Reported on every result rather than left blank — a blank Reference is the column failing silently.

**BR-REP-008's vocabulary is complete and an UNKNOWN source is shown as itself**, never bucketed under a familiar word: *nothing invisible* is enforced with `type_mapped=False` rather than assumed.

---
id: US-LED-010
epic: EP-LED-03
module: ledger
screens: [S60]
wave: 5
status: draft
blocked_by: []
depends_on: [US-LED-002]
journeys: [J5]
rules: [BR-LED-011, BR-LED-015]
golden_tests: []
finance_calc: confirmed
---
### US-LED-010 — By-premises summary report (S60): billed / collected / owed + collection %

**1 · Details** — As Finance/Owner staff (the by-premises reporting deliverable — single legal entity, premises = locations, A14 r3), I want the **By-premises summary**: params **Period · Service · Group by (Premises | Premises → Unit)**; columns **Premises (location) · Units · Services · Billed · Collected · Owed · Collection %**; KPI strip (premises count, billed, collected, owed) + all-premises totals footer; **PDF/CSV** per IS-11 (BR-LED-011). Figures come from the premises/unit dimensions on journal lines (BR-LED-001; the chain never breaks per BR-MET-046); collection % per BR-REP-009 (applied deposits count as collected; write-offs excluded); posting-basis label (BR-REP-001). Entry: Reports → By-premises summary. Exit: LE-6 to the cent.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-LED-011 | By-premises summary: billed/collected/owed + collection % per premises (unit chain, BR-MET-046). | CONFIRMED — PO LB-3, 2026-08-08 (LE-6) |
| BR-MET-046 *(consumed)* | Units never move between premises — chain integrity. | CONFIRMED — PO PU-19 |
| BR-REP-009 *(consumed)* | Collection % definition (posting basis; deposits applied count; write-offs separate). | CONFIRMED — PO RQ-1, 2026-08-08 |
| BR-REP-018 *(consumed)* | Downloads per IS-11. | CONFIRMED — PO 2026-08-08 |
| BR-LED-015 | Report export audits. | CONFIRMED — PO LB-7, 2026-08-08 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 *(balance)* | LE-6 period, group by Premises | 500 Main St: billed **247.87** · collected **292.87** · owed **0** · **100%** \| Oak Grove: **16.42 / 0 / 16.42 / 0%** \| Marina Bay: billed **289.40** · collected **153.50** (deposit) · transferred **135.90** shown · owed **0** at premises (owed sits on the master account) — LE-6 verbatim; footer sums the columns |
| TC-2 | Group by Premises → Unit | Marina Bay expands to its units; unit rows sum to the premises row exactly |
| TC-3 | Service filter = Water | Only water-dimension amounts; footer recomputes; services list = tenant-enabled set (BR-REP-006) |
| TC-4 | Downloads + labels | KPI strip ties to rows; PDF/CSV per IS-11 with POSTING basis label + params echoed; audit row |
| TC-5 *(negative)* | A unit deactivated + recreated mid-period (BR-MET-046 lifecycle) | Historical lines keep their stamped premises/unit — the report is stable; no orphan/unassigned money row ever appears |
| TC-6 *(isolation)* | Lone Star Ridge run | Its premises only (RLS) |

**4 · Test Data** — LE-6 verbatim (500 Main St / Oak Grove / Marina Bay; WE-1/WE-3/WE-7B money). KPI strip: 3 premises · billed 553.69 · collected 446.37 (292.87 + 153.50) · owed 16.42 at premises level + 135.90 master-held. File: `brazos-bend_by_premises_2026-07_posting_20260805.csv`. Actors: Alex Reed. Isolation: J. Okafor (premises "Cedar Flats").

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Params (period, service, group-by) | S60 | A14 r3 | query over premises/unit dimensions (r13 #1) | enum/dates | user-input | tenant scope |
| Billed / Collected / Owed | S60 | A14 r3 + BR-LED-011 | Σ journal lines per premises (posting basis) | numeric(18,6) | computed-display | Σ units = premises row |
| Collection % | S60 | BR-REP-009 | cash applied to premises bills ÷ billed per premises | % | computed-display | deposits applied count; write-offs excluded |
| Transferred indicator | S60 | LE-6 / BR-BIL-013 | transfer-source lines shown distinctly | numeric(18,6) | computed-display | not "collected", not "owed at premises" |
| KPI strip + footer | S60 | A14 r3 | computed over rows | counts/$ | computed-display | ties exactly |
| Downloads | S60 | IS-11 | streamed PDF/CSV | file | computed-display | basis labeled; audited |

**6 · Acceptance**
- Given the LE-6 period, Then the three premises rows render verbatim with the transfer shown distinctly and the footer/KPIs tying.
- Given unit grouping, service filters, and downloads, Then sums, vocabularies and IS-11 hold exactly.
- Given the unit lifecycle, Then history never moves; given tenants, nothing crosses.

**7 · Finance Calculation** — CONFIRMED (LE-6 verbatim + BR-REP-009): 500 Main St % = cash applied to the period bill 247.87 ÷ billed 247.87 = **100%** (the Collected COLUMN shows 292.87 total cash landed; the 45.00 prior-period application is excluded from the %) · Oak Grove 0 ÷ 16.42 = **0%** · Marina Bay: collected 153.50 (deposit applied), transferred 135.90, owed at premises **0**. Footer billed Σ = **553.69**.

**8 · Open Questions** — ~~None.~~ **AMENDED 2026-08-11 (ledger reporting lane): THIS STORY IS BLOCKED ON US-LED-002 AND THE BLOCK IS MEASURED.**

§5 above says the figures are *"Σ journal lines per premises (posting basis)"*. **Every journal line in the product carries `premises_id = NULL` and `unit_id = NULL`.** Nothing stamps either: `apps/billing/posting_seam.py` reports `premises_and_unit_dimensions_not_resolved` on every bill, `apps/payments/ledger_seam.py` passes only `source_type` / `source_id` / `account_id`, and `apps/ledger/posting.py` carries the columns without resolving the chain — because customers publishes no account → unit read and metering no unit → premises read. **US-LED-002 is the story; it is unbuilt.**

`apps/ledger/reporting.by_premises_summary` therefore returns **`available=False`** with `unattributed_billed = 553.69` — LE-6's own footer figure — rather than an empty table (which reads as *"no activity this period"*) or a single *Unassigned* row (which sorts, exports and reads like a premises). The refusal is a measurement.

**RESOLVING THE CHAIN AT READ TIME WAS CONSIDERED AND REFUSED.** It is exactly the defect TC-5 tests for: a read-time join moves LAST YEAR'S money the day a unit is deactivated and recreated, and BR-MET-046's chain guarantee is about the STAMP, not about the join. `tests/test_us_led_010_by_premises.py` asserts structurally that no such join exists in the module.

LE-6's three rows are transcribed in that test file as `LE6_ROWS`, so the assertions flip to the ratified figures the day the dimension arrives, with no re-derivation. **What DOES work is the same query grouped two other ways** — by service (LE-2) and by authority (LE-3) — which is the evidence that the dimension model is right and one stamp is missing.
