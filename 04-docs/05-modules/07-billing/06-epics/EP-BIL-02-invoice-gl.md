# EP-BIL-02 — Invoice anatomy, GL stamping & the posting handoff

**Module:** billing · **Wave:** W3 · **Screens:** S30 (line detail), S56 (Finance → account-mapping panel), S41 (Taxes & Remittance read-side), S66 · **Status:** draft (BR-BIL-001..029 all CONFIRMED — session closed 2026-08-08)

## Scope
**In:** the three-layer bill anatomy (model §3): one customer document · N GL-coded `invoice_lines` · one balanced journal entry per bill (BR-BIL-010/011); per-line `gl_account_id` stamped at issue with history never re-mapped; tax lines per authority with the B4.2 base and account-level exemption (GT-10/11); the Finance account-mapping settings page (service→revenue with optional usage/base split · tax authority→liability · charge codes carry their own GL · AR / deposit-liability / opening-clearing / write-off designations — B2 r10 #2) and the balanced posting handoff contract consumed by the ledger posting service (J2 step 11, J5 trial balance). **Plus (2026-08-10, PO modularity request):** the pipeline's two TERMINAL stages — assemble-document (6) and post-to-ledger (7) — and the contract that keeps a refactor honest: **GT-1..61 reproduce identically no matter how the engine is restructured internally** (BR-BIL-038, US-BIL-030).
**Out:** posting execution + trial balance surfaces (ledger, W5 — S56 rendering of balances) · rating math that produces the pre-tax amounts (EP-RAT-05 🔒) · tax authority CRUD (EP-RAT-03/S13, r6.5) · remittance filings (S41 is finance's read of stamped tax lines) · the tenant COA seed content (B2 O-14 — finance + Eng Lead) · the front five pipeline stages and the orchestrator (EP-BIL-01, US-BIL-029) · the rule-type plugin interfaces (EP-RAT-05, US-RAT-015) · any change to B4/B5, which are ❄ frozen and which US-BIL-030 exists to protect, not to touch.
**Tables (B2 + r10):** `invoices`, `invoice_lines` (+`gl_account_id`). ⚠ **`service_gl_map`, `tax_authority_gl_map` and the GL designations (AR / deposit-liability / opening-clearing / write-off) are NOT billing's tables — PO ruling 2026-08-11 closing OQ-106: the LEDGER owns them** (EP-LED-02 §Scope, amended the same day). Billing READS them through a seam to stamp `invoice_lines.gl_account_id` at issue (BR-BIL-010), and US-BIL-009 SURFACES the mapping page; neither is ownership. A designation is an ATTRIBUTE on a ledger account, and utility services carry them too, so the ledger derives its roll-up from both.

## Capability matrix (list screens only — B9 conformance)
| Screen | Search fields | Filters | Default sort | Sortable | Columns default/available | Row actions | Bulk actions | Export |
|---|---|---|---|---|---|---|---|---|
| — | *(no list screens owned — S56's mapping panel is a settings form; bills lists are EP-BIL-07)* | | | | | | | |

## Stories

---
id: US-BIL-007
epic: EP-BIL-02
module: billing
screens: [S30]
wave: 3
status: draft
blocked_by: []
depends_on: [US-RAT-012, US-RAT-013, US-BIL-009]
journeys: [J2, J5]
rules: [BR-BIL-004, BR-BIL-010, BR-BIL-011]
golden_tests: []
finance_calc: confirmed
---
### US-BIL-007 — Bill anatomy: one document, N GL-coded lines, one balanced entry

**1 · Details** — As the system (on behalf of finance), I want every bill stored as three deliberate layers (model §3): (1) the customer **document** rendered from the pinned template; (2) **`invoice_lines`** — one row per charge component (each usage block/tier/TOU window if itemized, each base, capacity, minimum-bill adjustment, each tax authority, each fee), each carrying quantity, unit, unit_price, amount (rounded half-up 2dp at finalization, B4.4), a `taxable` flag, and a **stamped `gl_account_id`**; (3) the **balanced journal entry** produced by the posting service from the issued lines (DR AR total / CR per-GL buckets) — so that one bill is many records by GL code (PO directive) and finance can slice revenue per GL without parsing documents. Consumption lines always carry an explicit unit (CLAUDE.md #3). Line detail is visible on the bill detail view (US-BIL-026).

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-BIL-010 | Every invoice line carries a GL account resolved from the Finance account-mapping page and stamped onto the line at issue — later mapping edits never re-map history. | CONFIRMED — PO Billing A-1 option (a), 2026-08-08 |
| BR-BIL-011 | One bill = one customer document + N GL-coded invoice lines + one balanced journal entry (DR AR total / CR per-GL buckets); ledger posting service is the sole writer. | CONFIRMED — PO directive 2026-08-08 · B1/B2 |
| BR-BIL-004 | Issued lines are append-only forever; corrections are new rows (credit note/rebill). | CONFIRMED — B2 §billing, CLAUDE.md #4 |
| B4.4 *(cited)* | Rounding per line, half-up, 2dp, at finalization only; NUMERIC(18,6) upstream. | CONFIRMED — finance 2026-08-07 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Run the WE-1 fixture → issue | Exactly **15 `invoice_lines`** rows matching the WE-1 table (3 TOU + elec base + 2 water tiers + water base + sewer + trash + solar capacity + 4 tax authorities + late fee); every usage row has quantity + explicit unit + unit_price; taxable flags: 10 ✔ / 4 tax rows — / late fee ✘ |
| TC-2 | GL stamps on WE-1 | 4100 ×3 (TOU), 4105, 4110 ×2, 4115, 4120, 4130, 4150, 2200/2201/2202/2203, 4200 — per the mapping at issue time |
| TC-3 | Posting layer (W5 consumes) | One JE: DR 1200 AR 247.87; CR buckets exactly §7; balanced trigger passes; J5 trial balance ties |
| TC-4 | Minimum-bill fixture (WE-3) | Line set includes "Minimum bill adjustment" +5.40 flagged taxable; tax rows compute on 15.00 (US-BIL-008 math) |
| TC-5 *(negative)* | A line INSERT with amount but no unit on a usage-based row; a line with no `gl_account_id` at issue | Both rejected — explicit unit required on usage (CLAUDE.md #3); issue fails atomically if any line cannot resolve a GL (mapping incomplete → staff fixes US-BIL-009, nothing partial issues) |
| TC-6 *(negative)* | UPDATE attempted on an issued line's amount/GL | Rejected by immutability triggers (B2 §3) |
| TC-7 *(isolation)* | Lone Star Ridge line query | RLS returns only its lines; a forged query with a Brazos Bend invoice id returns nothing |
| TC-8 *(negative — 2026-08-12, OQ-152)* | A bill whose lines make one **GL bucket sum below zero** reaches issue — reachable today, since a discount is a negative charge rule (BR-RAT-045 / OQ-055) | **The bill REFUSES to issue** (PO 2026-08-12, *"refuse the bill"*). It does **not** post a debit of the absolute value to the other side of the entry: a negative bucket means the bill's own lines contradict each other, and issuing it would put a figure in the books that no line explains. The refusal names the bucket and surfaces as a break row like any other stage failure, so the rest of the run issues (BR-BIL-055) |

**4 · Test Data** — WE-1 (ACC-1042, Jul 1–31): lines/amounts verbatim from the workbook — on-peak 120 kWh × 0.22 = 26.40 · mid 200 × 0.14 = 28.00 · off 380 × 0.09 = 34.20 · elec base 12.00 · water T1 5 kgal × 4.00 = 20.00 · T2 3 × 6.50 = 19.50 · water base 8.00 · sewer 40% × 39.50 = 15.80 · trash 18.00 · solar 4 × 10 = 40.00 · state 13.87 · county 2.22 · city 4.44 · PUC 0.44 · late fee 5.00. WE-3 minimum-bill account ACC-2007 (water-only, 0.4 kgal). Isolation: Lone Star Ridge invoice LSR-2608-000102.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Line description/qty/unit/unit_price/amount | S30 detail | model §3 + B2 DDL | `invoice_lines.description/quantity/unit/unit_price/amount` | numeric(18,6) + text | system-derived (engine) | amount 2dp at finalization (B4.4); unit explicit on usage |
| Taxable flag | — | B4.2 schema note | `invoice_lines.taxable` (B4 "Schema impact") | boolean | system-derived | usage/base/minimum/capacity ✔ · fees/late ✘ · tax rows — |
| GL stamp | — | BR-BIL-010 | `invoice_lines.gl_account_id` (r10 #1, FK ledger_accounts ⚠ reviewed interface) | uuid | system-derived | resolved at issue; frozen |
| Service / tariff version / charge refs | — | B2 DDL | `invoice_lines.service/tariff_version_id/charge_id` | enum/uuid | system-derived | tariff version = in force at service date |
| Line period | — | B2 DDL | `invoice_lines.period_start/period_end` | date | system-derived | supports back-bill period groups (US-BIL-013) |
| Invoice totals | S30 | B2 DDL | `invoices.subtotal/tax_total/total` | numeric(18,6) | system-derived | = Σ lines by class |
| Posting handoff | — (contract) | BR-BIL-011 | consumed by posting service 🔒; source = invoice | rows | system-derived | DR AR = Σ CR buckets |

**6 · Acceptance**
- Given the WE-1 issue, Then the 15 lines, flags, units and GL stamps match §4/§7 exactly, and totals equal Σ lines.
- Given the posting layer, Then exactly one balanced JE per bill exists (W5), written only by the posting service.
- Given an unmappable line or a unit-less usage row, Then issue fails atomically with a staff-fixable message.
- Given issued lines, Then no update path exists — ever.

**7 · Finance Calculation** — CONFIRMED (WE-1/BS-1, workbook verbatim). Current charges = Σ non-tax lines 226.90 + tax 20.97 = **247.87**; total due = 247.87 + prior 45.00 = **292.87**. Posting: DR 1200 AR **247.87** / CR 4100 **88.60** · 4105 **12.00** · 4110 **39.50** · 4115 **8.00** · 4120 **15.80** · 4130 **18.00** · 4150 **40.00** · 2200–2203 **20.97** · 4200 **5.00** — balanced. Ref: BS-1.

**8 · Open Questions** — None.

---
id: US-BIL-008
epic: EP-BIL-02
module: billing
screens: [S30, S41]
wave: 3
status: draft
blocked_by: []
depends_on: [US-BIL-007, US-RAT-009, US-CUS-003]
journeys: [J2]
rules: [BR-BIL-021]
golden_tests: [GT-10, GT-11]
finance_calc: confirmed
---
### US-BIL-008 — Tax lines per authority + account-level exemption

**1 · Details** — As the system (on behalf of finance), I want tax computed per B4.2 at finalization: base = usage + base + minimum-bill + capacity lines only (fees and late charges NEVER taxed); one line **per tax authority**, each rounded half-up individually; and when the account carries the tax-exempt flag, ALL tax lines vanish regardless of service (account-level exemption, GT-11) — so that S41 Taxes & Remittance can report collected-by-authority straight off stamped lines. Authority rates are tenant reference data per jurisdiction (r6.5 taxes model); the liability GL per authority comes from the mapping (US-BIL-009). Exemption certificate capture/expiry remains a B4 PLACEHOLDER owned by finance — the flag itself (BR-CUS pack, `accounts.tax_exempt`) is live and this story consumes it.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| B4.2 tax base *(cited)* | Tax base = usage + base (+ minimum-bill adjustment and capacity, taxable-like-base per GT-13/GT-15); fees and late charges NOT taxed. | CONFIRMED — B4.2 (finance 2026-08-07) + GT-13/GT-15 fixtures |
| B4.2 exemption *(cited)* | Exemption is account-level — exempt regardless of service; flag on `accounts`. | CONFIRMED — B4.2 (finance 2026-08-07) |
| BR-BIL-021 | Tax authorities (+ rates) are tenant-configured reference data, seeded, never hardcoded. | CONFIRMED — PO Lane B-2, 2026-08-08 |
| B4.4 *(cited)* | Per-authority line rounded half-up 2dp each at finalization. | CONFIRMED — finance 2026-08-07 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | WE-1 taxable base 221.90 | Four tax lines: state 6.25% → **13.87** · county 1.00% → **2.22** · city 2.00% → **4.44** · PUC 0.20% → **0.44**; tax_total **20.97**; late fee 5.00 excluded from the base |
| TC-2 | Same bill, ACC-1042 flagged tax-exempt (WE-2) | Zero tax lines; current **226.90**, total **271.90** — exemption removes every authority regardless of service |
| TC-3 | Minimum-bill account (WE-3) | Tax computes on the floored 15.00 (incl. the +5.40 adjustment line): 0.94 + 0.15 + 0.30 + 0.03 = **1.42**; total **16.42** |
| TC-4 | First bill (WE-6) | Tax on taxable 102.53 = **9.70**; deposit 150.00 and CONN 25.00 both untaxed (deposit → liability, fee class) |
| TC-5 *(negative)* | A charge-code fee line flagged taxable by a forged write | Rejected — fees/late are never taxable (B4.2); the `taxable` flag on fee lines is system-set ✘ |
| TC-6 *(negative)* | Authority rate changed mid-period without an effective date | Rejected — rate changes are dated (r6.5 effective_from/to); bills price on the rate in force at service date |
| TC-7 *(isolation)* | Lone Star Ridge (different state, 2 authorities) | Its bills carry its two authority lines only; Brazos Bend's four never appear (tenant-scoped jurisdictions, BR-TEN-037) |
| TC-8 *(2026-08-12, OQ-148 — the per-authority cent on the reference bill)* | The **$100.58** taxable base of the reference bill, split State 6.25% / Harris County 1.00% / City of Katy 1.00% | **6.29 + 1.01 + 1.01 = 8.31**, and the reference bill's total becomes **$117.02**. The single combined rule gave **8.30**: splitting one tax rule into three authorities moves the bill by **one cent** because **each authority rounds its own line** (B4.4, already asserted by TC-1's four-line shape). ⚠ **B5 is NOT edited — the ❄️ frozen line stands and an ADDENDUM records the split and the new figure** (PO 2026-08-12, *"Confirm $8.31 and the frozen figure gets an addendum"*), the same route the 4160/4170 re-sign took |
| TC-9 *(2026-08-12, OQ-145/OQ-147 — who chooses the account and who numbers it)* | A tenant adds *Harris County* | The tenant **must point it at a liability account** — the product does not mint one silently (*"make them choose"*); where a NEW account is needed **its 2200-series code is GENERATED, never typed** (*"Generated"*). ⚠ **An Eng-Lead disposition inside that, flagged because it was not shown to the PO:** the allocator takes the next NUMBER, not the lowest unused one, so a tenant holding 2200-01/02/03 who retires Harris County (2200-02) gets **2200-04** and 2200-02 is gone for good — a code that meant one authority in March and another in June would make every earlier remittance report read wrong, silently |
| TC-10 *(2026-08-12, OQ-146 — the authority has no account yet)* | A **$117** bill whose authority carries no liability account reaches a bill run | The **run reports it** as a break naming the authority and the other accounts continue (*"let the run report it"*); the tenant is **not** blocked at setup from adding the authority. That bill still does not issue — BR-BIL-010's stamp is atomic and a guessed account remits money to the wrong government |

**4 · Test Data** — Brazos Bend authorities (workbook §1): TX State 6.25% · Travis County 1.00% · City franchise 2.00% · PUC 0.20% (effective 9.45%). Fixtures: WE-1 (20.97 = 13.87+2.22+4.44+0.44), WE-2 (exempt → 226.90/271.90), WE-3 (1.42 on 15.00), WE-6 (9.70 on 102.53), WE-11 penalty (10.92 on 115.50; TAMPER 500.00 untaxed). Isolation: Lone Star Ridge — 2 authorities (state + county fixture).

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Tax line per authority | S30 detail | model §9 + B4.2 | `invoice_lines` (one row per authority; description = authority name; `gl_account_id` = authority liability GL via `tax_authority_gl_map`) | numeric(18,6) USD | system-derived | rounded half-up each (B4.4) |
| Tax base | — | B4.2 | computed: Σ `invoice_lines.amount` where taxable | numeric(18,6) | system-derived | fees/late excluded by flag |
| Exemption flag | S30/S21 | B4.2 | `accounts.tax_exempt` (+`tax_exempt_ref`) — customers-owned read | boolean | reference-data | account-level; certificate capture = B4 PLACEHOLDER (finance) — flag consumption only here |
| Authority + rate | S13/S41 | r6.5 taxes model | `taxes` (+jurisdiction, percent, liability_gl_account_id, effective dates) — rating-owned read | numeric | reference-data | dated changes only |
| tax_total | S30 | B2 DDL | `invoices.tax_total` | numeric(18,6) | system-derived | = Σ tax lines |

**6 · Acceptance**
- Given the WE-1 base, Then the four authority lines and tax_total match §7 to the cent, with fees excluded.
- Given an exempt account, Then zero tax lines exist on any service (WE-2 totals exact).
- Given minimum-bill/capacity/first-bill fixtures, Then tax computes on the taxable line set exactly as WE-3/WE-6.
- Given tenant authorities, Then rates come from dated reference data — never constants.

**7 · Finance Calculation** — CONFIRMED (B4.2/B4.4; workbook verbatim). `tax_line(a) = round_half_up(rate_a × Σ taxable_lines, 2)` per authority. Worked (WE-1): base 221.90 → 13.87 + 2.22 + 4.44 + 0.44 = **20.97**. Exempt (WE-2): tax 0 → current **226.90**, total **271.90**. Minimum-bill (WE-3): base 15.00 → 0.94 + 0.15 + 0.30 + 0.03 = **1.42** → total **16.42**. GT refs: **GT-10, GT-11** (+GT-13 interaction proven by WE-3).

**8 · Open Questions** — None (exemption-certificate capture stays a B4 PLACEHOLDER with finance; the flag path is fully specified). **OQ-148 · OQ-145 · OQ-146 · OQ-147 all CLOSED 2026-08-12 — see TC-8/9/10 and BR-BIL-069.** ⚠ **One consequence is owed elsewhere and is stated rather than assumed:** the **$8.31 / $117.02** figures need a **B5 ADDENDUM** (HUMAN-GUIDE §6), which is not this epic's write; and BR-BIL-064/068's worked examples still quote the pre-split **$117.01**, marked as such where they stand.

---
id: US-BIL-009
epic: EP-BIL-02
module: billing
screens: [S56, S66]
wave: 3
status: draft
blocked_by: []
depends_on: [US-RAT-008, US-RAT-009, US-TEN-010]
journeys: [J2, J5]
rules: [BR-BIL-010, BR-BIL-011, BR-BIL-013]
golden_tests: []
finance_calc: confirmed
---
### US-BIL-009 — Finance account-mapping page + the balanced posting handoff contract

**1 · Details** — As a System Admin (with finance), I want a Settings → Finance **account-mapping page** (S56 mapping panel): per-service revenue GL with an optional usage/base split, per tax authority → liability GL, charge codes showing their own GL (edited on the charge, S12), plus the designations — Accounts Receivable, deposit liability, opening-balance clearing, and the write-off account — over a seeded chart (full COA = B2 O-14, finance + Eng Lead), tenant-editable — so that every line issued after my edit stamps the new GL while history keeps its stamps forever (BR-BIL-010). And I want the posting handoff contract explicit: per issued bill, {invoice id, account, service_date, per-GL bucket sums, AR total, currency} consumed ONLY by the ledger posting service (BR-BIL-011; J2 step 11; J5 trial balance ties). ⚠ **AMENDED 2026-08-11 — BUILT.** This sentence read *"Until W5, handoffs persist unposted; the posting call is stubbed at the boundary — no fake ledger rows"*. Nothing persists unposted and nothing is stubbed: `apps/billing/posting_seam.py` builds the handoff from the ISSUED invoice and its stamped lines and calls `apps.ledger.posting.post` inside the issue transaction, keyed `invoice|<id>|issued` so a resumed release replays onto the same entry (hard rule 6). The "no fake ledger rows" half stands and always will — billing writes none, and `ledger/0004`'s sole-writer trigger is what makes that structural.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-BIL-010 | Mapping page: service→revenue (optional usage/base split) · tax authority→liability · charge codes carry their own GL · AR/deposit-liability/clearing designations; stamped per line at issue; edits never re-map history. | CONFIRMED — PO Billing A-1 option (a), 2026-08-08 |
| BR-BIL-011 | Posting = one balanced JE per bill; posting service sole writer; billing never writes journal lines. | CONFIRMED — PO directive 2026-08-08 · CLAUDE.md #5 |
| BR-BIL-013 *(designation share)* | Write-off GL designation lives in this mapping (small-balance write-off path, OQ-070 closed). | CONFIRMED — r10 #2/#11 |
| BR-CUS-025 *(consumed)* | Deposits post to deposit liability, never revenue — the deposit-liability designation is the target for first-bill deposit lines (WE-6). | CONFIRMED — BR-BIL-012 text ("non-taxable → deposit liability, never revenue") |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Admin opens the mapping page (Brazos Bend) | Rows: 8 enabled services × revenue GL (Electric split usage 4100 / base 4105; Water 4110/4115; Sewer 4120; Trash 4130; Solar 4150 …); 4 tax authorities → 2200–2203; designations AR 1200, deposit liability, opening clearing, write-off; charge codes listed read-only with their GLs |
| TC-2 | Electric usage mapping edited 4100 → 4101, then a new bill issues | New lines stamp 4101; all previously issued lines still read 4100 (BR-BIL-010); edit audited |
| TC-3 | WE-6 first bill issues | Deposit 150.00 line stamps the deposit-liability designation (never a revenue GL); CONN 25.00 stamps the CONN charge code's GL |
| TC-4 | W5 posting consumes the WE-1 handoff | JE per §7; Σ per-GL CR = DR AR; J5 trial balance debits = credits |
| TC-5 *(negative)* | Admin blanks the Water revenue mapping, then a water bill tries to issue | Issue fails atomically, naming the unmapped service; nothing partial (US-BIL-007 TC-5 pair); mapping page shows the gap |
| TC-6 *(negative)* | A billing code path INSERTs into `journal_lines`; a handoff replay fires twice | Insert forbidden (sole writer, CLAUDE.md #5); replay no-ops on the per-invoice posting guard (🔒 key mechanics Eng-Lead) |
| TC-7 *(isolation)* | Lone Star Ridge mapping | Its own chart + mappings; Brazos Bend GLs never selectable (RLS) |

**4 · Test Data** — Brazos Bend mapping per the WE-1 sample chart: 4100/4105 electric, 4110/4115 water, 4120 sewer, 4130 trash, 4150 solar capacity, 4200 fees (LATE); tax 2200 state · 2201 county · 2202 city · 2203 PUC; designations: 1200 AR, deposit liability (WE-6 target), opening clearing (r9 #3 seed), write-off. Handoff fixture: WE-1 buckets per §7. Edit fixture: 4100 → 4101 on Sep 1, 2026. Actors: Alex Reed + Diana Chen (finance). Isolation: Lone Star Ridge chart.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Service → revenue GL (+usage/base split) | S56 panel | BR-BIL-010 | `service_gl_map` (r10 #2) | uuid(s) | user-input | active tenant chart rows only |
| Tax authority → liability GL | S56 panel | BR-BIL-010 | `tax_authority_gl_map` (r10 #2) | uuid | user-input | one per authority |
| Charge-code GL | S12 (read-only echo on S56) | BR-BIL-007/010 | `charges` GL ref (existing schema) | uuid | reference-data | edited on the charge |
| AR / deposit-liability / clearing / write-off designations | S56 panel | BR-BIL-010/013 | designation rows (r10 #2) | uuid | user-input | exactly one each |
| Seeded chart | — | B2 O-14 | `ledger_accounts` seed (finance + Eng Lead own content) | rows | reference-data | tenant-editable labels; codes per COA |
| Posting handoff (per bill) | — (contract) | BR-BIL-011 | consumed by posting service 🔒 — **BUILT 2026-08-11**; nothing is persisted unposted (this cell read *"persisted unposted until W5"*) | rows | system-derived | balanced by construction, and REFUSED naming the delta when it is not; per-invoice idempotency guard 🔒 = `invoice\|<id>\|issued` |
| Mapping audit | — | CLAUDE.md #7 | `audit_log` `gl_mapping.updated` | jsonb | system-derived | append-only |

**6 · Acceptance**
- Given the mapping page, Then all four sections render over the seeded chart and every edit is audited.
- Given a mapping edit, Then only future issues stamp the new GL — issued history is untouched.
- Given the WE-1 handoff, Then W5 posting produces the §7 entry balanced, and a replay never duplicates.
- Given an unmapped service, Then issue fails atomically with a staff-fixable message; given cross-tenant access, nothing leaks.

**7 · Finance Calculation** — CONFIRMED (WE-1 verbatim): handoff buckets = Σ stamped line amounts per GL → DR 1200 AR **247.87** / CR 4100 **88.60** · 4105 **12.00** · 4110 **39.50** · 4115 **8.00** · 4120 **15.80** · 4130 **18.00** · 4150 **40.00** · 2200–2203 **20.97** · 4200 **5.00**. First-bill designation check (WE-6): deposit **150.00** → deposit liability (never revenue), CONN **25.00** → its charge-code GL. Ref: BS-1.

**8 · Open Questions** — None (COA seed content = B2 O-14, already routed to finance + Eng Lead).

---
```yaml
id: US-BIL-028
epic: EP-BIL-02
module: billing
screens: [S30, S31]
wave: 2
status: draft
blocked_by: []
depends_on: [US-TEN-015, US-BIL-003]
journeys: []
rules: [BR-BIL-030]
golden_tests: []
finance_calc: none
```
### US-BIL-028 — Stamp the custom-field snapshot onto the invoice at issue

**1 · Details** — As the platform, I must capture the custom-field values an invoice depends on **at the moment it is issued**, so that editing master data next March cannot rewrite last January's bill. Nothing reads the snapshot in R2 — the template variables that consume it land in R3 (US-NOT-016). It is stamped anyway, because the alternative is unrecoverable.

**Why R2 and not R3.** You cannot retroactively reconstruct what an account looked like six months ago. If R2 issues real invoices with no snapshot column, every invoice from that period is permanently unable to render custom fields, and the tempting repair is a live join to master data — the exact violation this story exists to prevent. Stamp early, render later. This is a one-way door; the master-data columns are not.

**2 · Business Rules**
| BR-ID | Statement | Status |
|---|---|---|
| BR-BIL-030 | At issue, the invoice stamps `invoices.custom_snapshot` from the active custom fields of the account and its related property entities. **The snapshot holds strings only** — every value is display-formatted at stamp time using the tenant's Regional settings (IS-8). Rendering reads the snapshot; it never joins to master data. This mirrors DB-8 (stamped `gl_account_id`) and DB-9 (pinned `template_id` + version), which exist for the same reason: a later edit must not reach backwards into an issued document | PROPOSED — derives from CLAUDE.md #4 (financial immutability), DB-4, DB-8, DB-9; PO ruling 2026-08-10 ("allow it") |

**Why strings only.** This is the structural half of BR-TEN-048. A `number` custom field becomes `"1234"` in the snapshot, so arithmetic on it is impossible without an explicit parse — which the G6 gate can grep for. The rule stops depending on anyone's discipline. It also pins the formatting, so a reprint in 2029 renders exactly as the original did.

**The G6 exception, stated plainly.** BR-TEN-048 bans `custom_data` under `apps/billing/`, and this story is billing code that must read it. Resolution: `apps/rating/` remains an absolute ban, and billing gets **one allowlisted module** (`apps/billing/custom_snapshot.py`) whose only job is to copy values into the stamp. It returns `dict[str, str]` and there is no typed accessor anywhere that returns a number from it.

**3 · Test Cases**
| TC-# | Scenario | Expected |
|---|---|---|
| TC-1 | Issue a bill for an account with `service_class = "Commercial"` | `invoices.custom_snapshot` contains `{"account.service_class": "Commercial"}` |
| TC-2 | Change the account's `service_class` to "Irrigation" after issue, re-read the invoice | Snapshot still reads "Commercial". The issued document did not move |
| TC-3 | A `number` custom field valued 1234 | Snapshot holds the **string** `"1234"`, not the number 1234 |
| TC-4 | A `date` custom field with tenant format `MM/DD/YYYY` | Snapshot holds the formatted string; a later Regional-settings change does not alter it. ⚠ **UNRESOLVED TENSION, REPORTED 2026-08-12 AND NOT CHOSEN HERE:** this rule formats at stamp time from the tenant's **Regional settings (IS-8)**, while the literal chosen under the PO's *"application decide the format for time being"* grant prints a date as **ISO `2026-03-04`** precisely to avoid the `03/04/2026` ambiguity (TC-10). The two cannot both be true for the same string. Which wins is a question for the PO — it is the same grant, and it is the item most likely to be wrong for a real customer |
| TC-5 | Account with no custom fields defined | `custom_snapshot` is `{}` — never null, and the bill run is unaffected |
| TC-6 (neg) | Deactivated field at issue time | Excluded from the snapshot (BR-TEN-050); already-issued invoices keep theirs |
| TC-9 *(2026-08-12, OQ-125/OQ-118 — where the snapshot PRINTS)* | An issued bill carries `account.member_no = "10432"`, a multiplier `1.5`, a date, a yes/no and a multi-select | All of them print in the bill's **remark / note section** — **ONE section carries every custom field**; the eight custom-field areas do not each get a designed place on the page (PO 2026-08-12, *"in remark or note section on bill - applicationd eicde the format for time being"*). Format is the **application's call FOR THE TIME BEING** — a deliberate temporary grant, not a permanent rule |
| TC-10 *(2026-08-12 — the four literals under the grant, each asserted so withdrawing it goes RED)* | The same five values rendered | **`10432`, not `10,432`** (the field definition cannot tell an identifier from a meter multiplier, and grouping an identifier is wrong) · **`1.5`** · **`2026-03-04` (ISO 8601), deliberately not `03/04/2026`** — which is 4 March in Madrid and 3 April in Houston, on a string frozen into an append-only row · **`Locked gate, Dog on site`** in the tenant's stored order. ⚠ **The fifth is HUMAN-REVIEW-PENDING and is the one to put back to the PO:** a boolean prints **`Yes` / `No` IN ENGLISH, on a bill that may be Spanish.** These four are Eng-Lead dispositions under the grant, NOT PO rulings |
| TC-11 (neg) *(2026-08-12 — the grant covers formatting, never invention)* | A `number` field holding `"abc"`, a `date` holding `"the 4th"`, a `boolean` holding `"yes"` | Each is **REFUSED per bill** and named — the temporary grant lets the application choose how a valid value LOOKS, never what an invalid one means |
| TC-7 (neg) | G6 gate over a patch adding `custom_data` to `apps/rating/engine.py` | Merge-blocking FAIL naming BR-TEN-048 |
| TC-8 (neg) | G6 gate over `apps/billing/` outside the allowlisted module | FAIL. Inside `custom_snapshot.py` it passes |
| TC-9 | Re-issue / correction (new row per DB-4) | The correction stamps its own snapshot at its own issue time; the original row is untouched |
| TC-10 (isolation) | Brazos Bend and Lone Star Ridge bill runs in the same window | Each invoice carries only its own tenant's values; no key from the other tenant's registry appears |

**4 · Test Data** — Brazos Bend account `ACC-1042`, `service_class = "Commercial"`, premises `easement_ref = "ESM-77"`, billed 2026-09-01. Post-issue edit to "Irrigation" on 2026-09-14 for TC-2. Lone Star Ridge `LSR-ACC-0003` with no definitions.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Custom snapshot | S30 · S31 (not displayed in R2) | GAP — PO 2026-08-10 | **PROPOSED-SCHEMA** `invoices.custom_snapshot jsonb NOT NULL DEFAULT '{}'` | jsonb, **string values only** | system-derived at issue | keys namespaced `<entity>.<key>`; every value a string; append-only with the invoice row (DB-4) |

**6 · Acceptance** — **Given** an account carrying custom values, **when** its bill is issued and the values are then edited, **then** the invoice's snapshot still holds what was true at issue; **and** the G6 gate fails any patch that reads `custom_data` from the rating engine or from billing outside the one allowlisted module.

**7 · Finance Calculation** — N/A, and structurally so: the snapshot is strings.

**8 · Open Questions**
| OQ-ID | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| OQ-076 (CLOSED 2026-08-10 — PO: "Dont put SSN on invoices"; tenant-defined PII is excluded from `invoices.custom_snapshot`. Mechanism opt-in vs opt-out pending confirmation) | A tenant can define a field holding PII ("SSN last 4"). Stamping copies it into `invoices`, which are immutable (DB-4) and long-retained — so an erasure request lands on rows we are forbidden to modify, and BR-TEN-044's day-91 deletion does not reach them. Proposed: a `contains_pii` flag on the definition that excludes a field from snapshots entirely — usable on screens, never stamped onto a bill | the stamp filter in `custom_snapshot.py` | Product Owner + compliance | **OPEN** |

---
id: US-BIL-030
epic: EP-BIL-02
module: billing
screens: [S30, S56]
wave: 3
status: draft
blocked_by: []
depends_on: [US-BIL-005, US-BIL-007, US-BIL-009, US-BIL-029, US-RAT-015]
journeys: [J2, J5]
rules: [BR-BIL-037, BR-BIL-038, BR-BIL-011, BR-BIL-030, BR-BIL-032, BR-BIL-033]
golden_tests: [GT-1, GT-2, GT-3, GT-5, GT-8, GT-10, GT-11, GT-13, GT-15]
finance_calc: confirmed
---
### US-BIL-030 — The terminal stages (assemble-document · post-to-ledger) and GT-1..61 as the refactor contract

**1 · Details** — As finance, I want one guarantee in writing and in CI: **however the billing engine is restructured inside, GT-1..61 come out identical** (BR-BIL-038). Stages 1–5 are covered by US-BIL-029; this story closes the pipeline at its two terminal stages and pins the contract that makes the whole modularity exercise safe.

**Stage 6 — assemble-document.** The stamped instance (`bill_payload` + `payload_version`, BR-BIL-030) is built **before** issue, because a bill that cannot render must never become immutable (BR-BIL-033, OQ-089). It must tie out to its own rows — `bill_payload.total == invoices.total` and the payload's line set reconciles to `invoice_lines` (BR-BIL-032) — because the redundancy is deliberate and silent drift between the two would be invisible.

**Stage 7 — post-to-ledger.** Billing **emits** {invoice id, account, service_date, per-GL bucket sums, AR total, currency} and writes nothing; the ledger posting service is the sole writer (BR-BIL-011, CLAUDE.md #5, US-BIL-009's contract).

**The contract itself.** GT-1..61 are the billing-math contract (B5 ❄, finance-signed 2026-08-08, harness `10-scripts/03-golden-verify.py` 33/33). Two clauses give BR-BIL-038 teeth rather than good intentions: (a) a commit may not both move a stage boundary and change a golden expected value — a B5 change needs a finance re-sign via HUMAN-GUIDE §6, never an inline edit; (b) the suite executes the pipeline's **public entry point**, never a stage's internals, so a refactor cannot quietly retarget the tests at the thing it just changed. This is hard-won law 1 made mechanical: the guarantee is a test, not a sentence in a docstring.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-BIL-038 | GT-1..61 reproduce to the digit across any internal restructuring; boundary moves and golden-value changes never share a commit; the suite runs the public entry point only. | PROPOSED — derived from the B5 ❄ freeze banner + CLAUDE.md 🔒 + hard-won law 7 |
| BR-BIL-037 | *(shared)* stages 6 and 7 are the terminal stages of the seven-stage pipeline; stage 7 emits and never writes. | PROPOSED — derived from model §3/§6 + B1 + BR-BIL-010/011 |
| BR-BIL-030 | The bill is locked at issue: the complete document instance is stamped and a reprint renders that instance forever, joining nothing live. | CONFIRMED — PO 2026-08-10 |
| BR-BIL-032 | The instance ties out to its rows: `bill_payload.total == invoices.total` and the payload's lines reconcile to `invoice_lines`; DB-17 still binds — tenant-defined data in the payload is display-only. | PROPOSED — derived from DB-3 · DB-17 · BR-BIL-030 |
| BR-BIL-033 | Render before issue; a failed render refuses the issue — stage 6 is a precondition of issuing. | CONFIRMED — PO 2026-08-10 (OQ-089) |
| BR-BIL-011 | One balanced JE per bill, written only by the posting service; billing emits the handoff. | CONFIRMED — PO directive 2026-08-08 · B1/B2 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 *(the contract)* | Full **GT-1..61** executed through the pipeline's public entry point | Every fixture reproduces its signed figure — GT-1 **108.88** · GT-2 usage **13.74** · GT-3 base **15.25** · GT-5 **343.60** · GT-8 **8.13** · GT-10 **116.01** · GT-11 **108.71** · GT-13 adj **6.90** / tax **2.06** · GT-15 **40.00** + **24.00**; the `10-scripts/03-golden-verify.py` harness stays 33/33 |
| TC-2 *(refactor drill)* | Split stage 4 into two internal steps and merge two helpers inside stage 3; re-run TC-1 | Output identical to the digit; **no** golden file is touched by the patch. This is the drill that proves the contract is real rather than declared |
| TC-3 *(stage 6 tie-out)* | WE-1 issued | `bill_payload.total` **292.87** equals the invoice's rendered total; the payload's line set reconciles 1:1 to the 15 `invoice_lines`; a reprint renders from the payload and joins nothing live (BR-BIL-030) |
| TC-4 *(stage 7 handoff)* | WE-1 handoff consumed (W5) | DR 1200 AR **247.87** = Σ CR buckets (§7) exactly; the balanced-pair trigger passes; J5 trial balance ties |
| TC-5 *(negative — the two-change rule)* | A commit that both moves a stage boundary and edits a GT expected value | Gate **fails**, naming BR-BIL-038 and HUMAN-GUIDE §6: a signed figure changes only by finance re-sign, never alongside a refactor. Proven RED first (hard-won law 7) |
| TC-6 *(negative — retargeting)* | A patch points the golden suite at a stage's internal function instead of the pipeline entry point | Gate fails — the suite must exercise the same door the bill run uses, or a refactor could pass by testing itself |
| TC-7 *(negative — sole writer)* | Stage 7, or any billing code path, attempts `INSERT INTO journal_lines` | Rejected (CLAUDE.md #5); the handoff persists unposted until W5, with no fake ledger rows (US-BIL-009 TC-6 pair) |
| TC-8 *(negative — payload drift)* | A forged payload whose total disagrees with `invoices.total`, or a payload missing a line present in `invoice_lines` | Tie-out test fails naming the delta (BR-BIL-032); drift can never be silent |
| TC-9 *(negative — unrenderable bill)* | Stage 6 render raises for one account during issue | That bill does not issue (BR-BIL-033); nothing immutable is created; the rest of the batch issues normally |
| TC-10 *(isolation)* | The golden suite executed under two tenant contexts in one process | Each tenant's fixtures produce their own signed figures; no fixture resolves another tenant's tariff, mapping or number series (RLS probe) |

**4 · Test Data** — **GT-1..61** as signed (B5, finance 2026-08-08): the legacy unit fixtures GT-1..15 verbatim, plus the workbook allocations WE-n → GT-(16+n), PE-n → GT-(34+n), LE-n → GT-(50+n), GT-61 deposit interest ($150 @ 2.0%, 89 mo → $22.25). Terminal-stage fixture: **WE-1** (Brazos Bend, ACC-1042) — 15 lines, current **247.87**, prior 45.00, total due **292.87**, posting DR 1200 AR 247.87 / CR 4100 88.60 · 4105 12.00 · 4110 39.50 · 4115 8.00 · 4120 15.80 · 4130 18.00 · 4150 40.00 · 2200–2203 20.97 · 4200 5.00. Refactor-drill patch: stage-4 split (TC-2). Unrenderable fixture: pinned template referencing a variable the payload does not carry (TC-9). Isolation: **Lone Star Ridge** invoice LSR-2608-000102 and its own two tax authorities.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Pipeline public entry point | — | BR-BIL-037/038 | code-only; **no table** — the single callable the run and the golden suite both use | — | system-derived | the suite may target nothing else (TC-6) |
| Document instance (stage 6 out) | S30 detail | BR-BIL-030/031 | `invoices.bill_payload jsonb NOT NULL` + `invoices.payload_version` | jsonb/int | system-derived at issue | built before issue (BR-BIL-033); ties out to rows (BR-BIL-032) |
| Template pin | S30 | BR-BIL-026 | `invoices.template_id` + `.template_version` (r10 #3) | uuid/int | system-derived | reprint renders the pinned version forever |
| Payload ↔ rows tie-out | — | BR-BIL-032 | assertion over `bill_payload.total` vs `invoices.total`, payload lines vs `invoice_lines` | numeric(18,6) | system-derived | equality; drift fails the test |
| Posting handoff (stage 7 out) | — (contract) | BR-BIL-011 · US-BIL-009 | {invoice id, account, service_date, per-GL bucket sums, AR total, currency} consumed by the posting service 🔒 | rows | system-derived | DR AR = Σ CR buckets; billing writes nothing |
| Golden harness reference | — | B5 ❄ + CLAUDE.md | `10-scripts/03-golden-verify.py` (33/33) — **referenced, never modified by this story** | — | system-derived | a B5 change needs HUMAN-GUIDE §6 finance re-sign |
| Two-change gate | — | BR-BIL-038 | CI check over the patch: boundary move + golden-value edit in one commit ⇒ FAIL | — | system-derived | proven RED before trusted green |

**6 · Acceptance**
- **Given** the full GT-1..61 suite run through the pipeline's public entry point, **then** every signed figure reproduces to the digit and the harness stays 33/33. ⚠ **THE TWO HALVES OF THAT SENTENCE ARE NOT THE SAME EVIDENCE (DEF-2846, corrected 2026-09-01).** "The harness stays 33/33" is `10-scripts/03-golden-verify.py`, which recomputes B4/B5's own figures and **never runs the pipeline** — it cannot witness this criterion at all. The half that can is **engine-verified**: `06-backend/tests/golden/`, today **14 of the 61** (GT-1..11, 16, 24, 47). So this criterion is demonstrable for 14 GTs and is an intention for the other 47.
- **Given** a deliberate internal restructuring of a stage, **then** the suite is unchanged and untouched — that is the demo.
- **Given** an issued bill, **then** its stamped payload ties out to its rows and a reprint joins nothing live.
- **Given** a render failure, **then** the bill does not issue; **given** any billing write to `journal_lines`, **then** it is rejected.
- **Given** a commit that moves a boundary and edits a golden value together, **then** CI refuses it naming HUMAN-GUIDE §6.
- **Given** two tenants, **then** the suite proves isolation as well as arithmetic.

**7 · Finance Calculation** — **CONFIRMED (B5 ❄ finance-signed 2026-08-08; WE-1/BS-1 verbatim). This story computes nothing new — it pins what is already signed.**
Terminal-stage arithmetic for WE-1: **stage 6** `total_due = current_charges + prior_balance` = 247.87 + 45.00 = **292.87**, stamped into `bill_payload` (BR-BIL-030) and equal to `invoices.total` by BR-BIL-032. **Stage 7** `DR AR = Σ CR buckets`: DR 1200 **247.87** / CR 4100 **88.60** · 4105 **12.00** · 4110 **39.50** · 4115 **8.00** · 4120 **15.80** · 4130 **18.00** · 4150 **40.00** · 2200–2203 **20.97** · 4200 **5.00** — balanced.
Invariance targets quoted from B5 as signed: **GT-1** 108.88 · **GT-2** 13.74 usage · **GT-3** 15.25 base · **GT-5** 343.60 · **GT-8** 8.13 · **GT-10** 116.01 · **GT-11** 108.71 · **GT-13** +6.90 / 2.06 · **GT-15** 40.00 + 24.00. Refs: **GT-1..61**, BS-1.

**8 · Open Questions** — None. *(Nothing here asks for a new decision: B5 is signed, the two terminal stages are ratified by BR-BIL-011/030/033, and BR-BIL-038 only writes down the discipline that keeps them true through a refactor.)*
