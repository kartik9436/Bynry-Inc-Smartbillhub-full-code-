# EP-RAT-03 — Charge Codes & Taxes/Fees

> Reconciled 2026-08-08 against PO rulings — OQ-053/054/055 closures applied (BR-RAT-041/042/043).

**Module:** rating (product name: Plans & Rates) · **Wave:** W1 · **Screens:** S9 (Charge codes + Taxes & fees tabs), S12, S13 · **Status:** draft

## Scope
**In:** the Charge codes tab of S9 + New Charge Code guided form (S12: Basics → Amount & behavior → Review & save) — the tenant's global catalog of non-usage line items (D7: catalog + plan attachment with amounts via `plan_charge_rules`); and the Taxes & fees tab + New Tax/Fee guided form (S13: Jurisdiction → Rate & base → Remittance → Review & save) with **tenant-entered jurisdictions** (BR-TEN-037) and plan attachment via `plan_tax_rules` (D8). Amount forms: flat, percent-of-bill, percent-with-minimum (charges); percent-of-subtotal, flat-per-bill, per-unit (taxes).
**Out:** applying charges/taxes to bills (EP-RAT-05 computes taxes; billing applies event charges) · the LATE fee *formula execution* (billing module, BR-BIL-008/GT-8 — this epic stores the code's percent/min) · plan-side attachment UI (EP-RAT-01 step 4 — this epic owns the catalogs and the attachment *rules*) · tax remittance filing workflows (Finance S41 — this epic stores the remittance config it reads) · the "Formula" amount rule option (underdetermined — OQ-053) and the per-unit tax "Applies above" threshold (OQ-054).

## Capability matrix (list screens only — B9 conformance)
| Screen | Search fields | Filters | Default sort | Sortable | Columns default/available | Row actions | Bulk actions | Export |
|---|---|---|---|---|---|---|---|---|
| S9 Charge codes tab | code, description | type (All/Recurring/One-time/Refundable/Penalty), service, status | code asc | code, description, type, amount | 6 default (Code · Description · Type · Service · Amount · GL account) / 8 available (+Taxable, +Used by plans) — IS-5 | Edit, Deactivate (IS-1 — delete only when referenced by 0 plans and 0 invoice lines) | — (v1) | CSV (IS-9) |
| S9 Taxes & fees tab | name, authority | jurisdiction level, service, remittance frequency, status | name asc | name, rate, remittance | 5 default (Jurisdiction · Applies to · Rate · Remittance · GL account) / 7 available (+Effective from, +Filing form) — IS-5 | Edit (new effective row), Deactivate (IS-1) | — (v1) | CSV (IS-9) |

## Stories

---
id: US-RAT-008
epic: EP-RAT-03
module: rating
screens: [S9, S12]
wave: 1
status: draft
blocked_by: []
depends_on: [US-TEN-002, US-SHL-006, US-SHL-007, US-SHL-008]
journeys: [J2, J4]
rules: [BR-RAT-005, BR-RAT-025, BR-RAT-035]
golden_tests: []
finance_calc: confirmed
---
### US-RAT-008 — Charge codes tab + New Charge Code (S12) + plan attachment rules

**1 · Details** — As an Owner/Admin, I want a charge-code catalog (Code · Description · Type · Service · Amount · GL) and a 3-step New Charge Code form — Basics (code, description, service scope Any|specific, type Recurring/One-time/Refundable/Penalty) → Amount & behavior (amount rule Flat / Percent of bill / Percent with minimum / Formula; amount, minimum, maximum; GL account; taxable selector; auto-apply / staff-waivable / separate-line toggles) → Review & save — so that every fee, deposit and penalty a plan can carry is defined once and attached with per-plan overrides (`plan_charge_rules.amount_override`, recurrence, taxable — r5 #9). Entry: S9 Charge codes tab **+ New charge code**. Exit: saved code → catalog; available to every plan's step 4.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-RAT-025 | D7: charge codes are a global (tenant) catalog; plans attach them with amounts/overrides; recurrence once\|recurring\|event; per-attachment taxable flag. | CONFIRMED — PO Q&A R3 |
| BR-RAT-035 | Charge-code identity: code unique per tenant; service scope Any or one service; IS-1 deactivate-first (audit-lock while any plan or invoice line references it); amounts NUMERIC(18,6), sample values from the prototype (NSF $30, reconnect $45) are seeds, never constants (B4 §NSF). **THE INVOICE-LINE HALF OF THE AUDIT LOCK IS LIVE ONLY SINCE 2026-08-12 (DEF-079)** — it asked billing how many ISSUED lines named the code, billing published no counter, the seam answered **0**, and a charge code appearing on real bills read as never used and stayed freely editable. `apps/billing/selectors.charge_line_count` is now published and the lock engages. | PROPOSED — derived from B2 `charges` DDL (UNIQUE (tenant_id, code)) + S12 + B4 CONFIRMED "samples only"; **the plan-attachment lock was always live, the ISSUED-LINE lock since 2026-08-12** |
| BR-RAT-005 | Fees and late charges are **never** part of the tax base (context for the taxable selector: a charge marked taxable joins the taxable base only if the B4.2 rule permits — fees/late do not; see US-RAT-013). | CONFIRMED — B4.2 (finance 2026-08-07) |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Dana opens the tab with the §4 seed | 8 rows (BASE-E … NSF) matching the prototype table; LATE renders amount "1.5% or $5 min"; default sort code asc |
| TC-2 | Dana creates TAMPER · "Meter tampering" · Penalty · Any · flat $250.00 · GL 4910 · not taxable · staff-waivable | `charges` row written; appears in catalog and in S10 step-4 checkbox list; audit `charge.created` |
| TC-3 | Percent-with-minimum: LATE re-created as 1.5% min $5.00 | `charges.percent = 0.015`, `charges.min_amount = 5.00`; review shows "1.5% or $5 min" |
| TC-4 | Plan attachment override: Small Commercial attaches CONN at $95.00 | `plan_charge_rules.amount_override = 95.00` (catalog stays $85.00); recurrence `once` |
| TC-5 *(negative)* | Second code "CONN" saved | Rejected by (tenant, code) uniqueness with inline error |
| TC-6 *(negative)* | Flat amount entered as −85 | Inline error (amount ≥ 0; credits/discounts are not negative charges pending OQ-055) |
| TC-7 *(negative)* | Deactivate then Delete on DEPO-R (attached to 4 plans) | Deactivate allowed (audit row); Delete audit-locked "attached to 4 plans" (IS-1) |
| TC-7b *(negative — the issued-line lock, DEF-079)* | Edit/Delete on a charge code attached to **no plan** but named on **issued invoice lines** | Audit-locked naming the issued-line count, via the published `apps.billing.services.charge_line_count`. Before 2026-08-12 this read as **0 uses** and the code stayed editable (`tests/test_def_079_dark_counters.py`) |
| TC-8 *(negative)* | Amount rule "Formula" selected | Option renders but Continue is blocked with "formula charges pending definition (OQ-053)"; no schema write path |
| TC-9 *(isolation)* | Lone Star Ridge creates its own "CONN" at $60.00 | Coexists with Brazos Bend's CONN $85.00; neither tenant sees the other's catalog |
| TC-10 *(PO ruling 2026-10-06 11 (a), BR-BIL-008 as amended)* | Type Penalty on New/Edit charge code; `LATE` grace 5 then 10 calendar days; bill due 1 Nov, $100.00 unpaid | Step 1 asks **Grace days** (starts at Billing defaults' grace, 5) and **Counted in** (Calendar / Business days); 31 refused; Review and View details show *5 calendar days*. Grace 5 → $5.00 assessed from 7 Nov; grace 10 → nothing until 12 Nov. A plan shows the code's grace under *When*; a plan override stated before the ruling reads *(this plan)* and still applies. `tests/test_po_20261006_grace_on_late_fee_code.py` · `chargeCodeGrace.dom.test.tsx` |

**4 · Test Data** — Brazos Bend catalog (per prototype): BASE-E $18.50/mo · BASE-W $12.00/mo · BASE-S $8.00/mo (all Recurring — display/GL rows; the billed base amount lives in `plan_services.base_charge`, BR-RAT-012) · CONN One-time $85.00 GL 4900 · DISC One-time $45.00 GL 4900 · DEPO-R Refundable $150.00 GL 2400 · LATE Penalty 1.5%/min $5.00 GL 4910 · NSF Penalty $30.00 GL 4910. New: TAMPER $250.00. Lone Star Ridge: CONN $60.00. Actor: Dana Whitfield.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Code / Description | S12 step 1 | prototype-extracted | `charges.code` / `charges.name` | text | user-input | code unique per tenant; short |
| Applies to service | S12 step 1 | prototype-extracted (Any + 6 services) | **PROPOSED-SCHEMA** `charges.service` (NULL = any; B2 has no column) | enum/NULL | user-input | tenant-enabled or Any |
| Charge type | S12 step 1 | prototype-extracted (4 cards) | **PROPOSED-SCHEMA** `charges.charge_type` (recurring\|one_time\|refundable\|penalty; B2 has no column) | enum | user-input | from option set |
| Amount rule + Amount/Min/Max | S12 step 2 | prototype-extracted | `charges.amount` / `charges.percent` / `charges.min_amount` + **PROPOSED-SCHEMA** `charges.max_amount` | numeric(18,6) | user-input | ≥ 0; percent as fraction |
| Amount rule "Formula" | S12 step 2 | prototype-extracted (radio, no fields) | **GAP** — semantics/grammar undefined | — | user-input | OQ-053 (CLOSED→BR-RAT-041) |
| GL account | S12 step 2 | prototype-extracted (4900/4910/2400/4100) | `charges.gl_account_id` (⚠ →ledger) | uuid | reference-data | must exist, same tenant |
| Taxable selector | S12 step 2 | prototype-extracted (Not taxable / state+local / state only) | **PROPOSED-SCHEMA** `charges.taxable_default` (per-plan override in `plan_charge_rules.taxable`, r5 #9); effective taxation still bounded by B4.2 (fees never taxed) | enum/bool | user-input | BR-RAT-005 bound |
| Behavior toggles (auto-apply / waivable / separate line) | S12 step 2 | prototype-extracted | **PROPOSED-SCHEMA** `charges.auto_apply`, `charges.staff_waivable`, `charges.separate_line` | bool | user-input | waive requires reason code (IS-6) |
| Grace days + Counted in (penalty only) | S12 step 1 | PO ruling 2026-10-06 11 (a) | `charges.grace_days` (0–30) / `charges.grace_mode` (calendar\|business), `rating/0066` | int / enum | user-input; starts at `tenant_settings.late_grace_*` | 0–30, NULL on non-penalty |
| Plan attachment | S10 step 4 | B2 r5 #9 | `plan_charge_rules` (plan × charge UNIQUE; amount_override, recurrence, taxable) | rows | user-input | charge active |

**6 · Acceptance**
- Given the seed, When the tab opens, Then the catalog matches the prototype rows including the "1.5% or $5 min" rendering.
- Given a new code saved, Then it exists once per tenant, is attachable to plans with overrides, and every create/edit/deactivate writes audit.
- Given a duplicate code, negative amount, referenced delete, or the Formula rule, Then the action blocks with the stated reason.

**7 · Finance Calculation** — Amount forms stored here (executed by billing/EP-RAT-05): flat → `amount`; percent → `percent × base_amount`; percent-with-minimum → `max(min_amount, percent × base_amount)` — worked example (GT-8 fixture, rule CONFIRMED B4.1): LATE on overdue portion $542.10 → max(5.00, 0.015 × 542.10) = max(5.00, 8.1315) = **$8.13** (half-up 2dp at finalization, BR-RAT-003). Charge lines never enter the tax base (BR-RAT-005, GT-10). Ref: **GT-8** context (billing executes), **GT-10** (exclusion).

**8 · Open Questions**
| OQ | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| OQ-053 (CLOSED→BR-RAT-041) | S12 "Formula" amount rule: is a formula-defined charge in v1 scope, and if so what grammar/inputs (B2 `charges` has only amount/percent/min)? | The Formula option only — flat/percent/percent-min fully buildable | Product Owner (chat session) | OPEN |

---
id: US-RAT-009
epic: EP-RAT-03
module: rating
screens: [S9, S13]
wave: 1
status: draft
blocked_by: []
depends_on: [US-TEN-002, US-SHL-006, US-SHL-007, US-SHL-008]
journeys: [J2]
rules: [BR-RAT-005, BR-RAT-006, BR-RAT-025, BR-RAT-036]
golden_tests: [GT-10]
finance_calc: confirmed
---
### US-RAT-009 — Taxes & fees tab + New Tax/Fee (S13) with tenant-entered jurisdictions + plan tax rules

**1 · Details** — As an Owner/Admin, I want a Taxes & fees tab (Jurisdiction · Applies to · Rate · Remittance · GL) and a 4-step New Tax/Fee form — Jurisdiction (name, authority, reference/permit #, level Federal/State/County/City/Special district, applies-to services) → Rate & base (Percent of subtotal / Flat per bill / Per unit of usage) → Remittance (liability GL, remit-to, frequency, filing form, effective window) → Review & save — with jurisdictions **entered by the tenant** (no global registry, BR-TEN-037), so that taxes attach to bills automatically by jurisdiction and service and remittance reports have their config. Plans attach jurisdictions via `plan_tax_rules` with optional `rate_override` (r5 #11). Entry: S9 Taxes & fees tab **+ New tax or fee**. Exit: saved tax → list; effective from the stated date.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-RAT-005 / BR-RAT-006 | Tax base = usage + base charge only (fees/late never taxed); exemption is account-level regardless of service. | CONFIRMED — B4.2 (finance 2026-08-07); GT-10/GT-11 |
| BR-RAT-025 | D8: tax rules attach via plan + account-level exemption; plan_tax_rules rate_override NULL = jurisdiction rate. | CONFIRMED — PO Q&A R3 + B2 r5 #11 |
| BR-TEN-037 | Tax jurisdictions are tenant-entered (no global registry). | CONFIRMED — PO Q&A R6 (OQ-032) |
| BR-RAT-036 | Tax computation forms: **percent-of-subtotal** = rate × taxable base per B4.2; **flat-per-bill** = fixed amount per bill (or once per fiscal year); **per-unit** = rate × billed usage quantity in the stated unit. The prototype's taxable-base checkboxes for "Fees" and "Other taxes (tax-on-tax)" are **removed** — B-doc wins over prototype (B4.2: fees and late are NEVER taxed; no tax-on-tax); only Usage and Base remain selectable. Taxes never compound. | Percent base CONFIRMED (B4.2); flat/per-unit forms PROPOSED — prototype-extracted (S13 cards, "$0.85 PUC fee", "$0.25/kgal") |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Dana opens the tab with the §4 seed | 4 rows: TX State Utility Tax 6.25% · Local Fort Bend County 2.00% · PUC Regulatory Fee $0.85 flat/bill (Electric) · Water Conservation Surcharge $0.25/kgal; remittance + GL columns filled |
| TC-2 | Dana creates "City Franchise Fee": City level, Electric, percent 1.50%, base Usage+Base, remit Quarterly · City of Katy, GL 2303, effective Sep 1, 2026 | Tax + tenant jurisdiction rows written; review matches; audit `tax.created` |
| TC-3 | Percent form step 2 | Taxable-base panel offers **only** "Usage charges" and "Base service charges" (both default on); no Fees / tax-on-tax option renders (BR-RAT-036 — B4.2 wins over the prototype checkboxes) |
| TC-4 | Plan attachment: Residential Standard attaches TX State + Fort Bend; Senior plan attaches TX State with rate_override 0.00 | `plan_tax_rules` rows (plan × jurisdiction UNIQUE); override NULL = jurisdiction rate; account-level `tax_exempt` still zeroes everything (B4.2) |
| TC-5 *(negative)* | Percent rate entered as −2 or blank | Inline error; Continue blocked |
| TC-6 *(negative)* | Same jurisdiction attached to the same plan twice | Rejected by plan × jurisdiction uniqueness (r5 #11) |
| TC-7 *(negative)* | Per-unit form's "Applies above" filled ("Tier 3 only") | Field renders but save is blocked with "threshold semantics pending (OQ-054)"; plain per-unit (no threshold) saves fine |
| TC-8 *(isolation)* | Lone Star Ridge enters jurisdiction "Hays County 0.50%" | Invisible to Brazos Bend; each tenant's jurisdiction list is fully its own (BR-TEN-037) |

**4 · Test Data** — Brazos Bend taxes: **TX State Utility Tax** (Texas Comptroller, State, all services, 6.25%, Monthly, GL 2300) · **Local · Fort Bend County** (County, all services, 2.00%, Monthly, GL 2301) · **PUC Regulatory Fee** (State/special, Electric, $0.85 flat/bill, Quarterly · TX PUC, GL 2302) · **Water Conservation Surcharge** (Special district · TWDB, Water, $0.25/kgal, Annual, GL 2304; threshold left blank pending OQ-054). Combined percent rate for GT worked examples: 6.25 + 2.00 = **8.25%**. Lone Star Ridge: Hays County 0.50%. Actor: Dana Whitfield.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Tax/fee name | S13 step 1 | prototype-extracted | `taxes.name` | text | user-input | required |
| Authority / Reference-permit # / Level | S13 step 1 | prototype-extracted | `tax_jurisdictions` — **tenant-scoped per BR-TEN-037** (supersedes B2's platform note/O-12) + **PROPOSED-SCHEMA** `tax_jurisdictions.level`, `.reference_no` | text/enum | user-input | level from 5-option set |
| Applies-to services | S13 step 1 | prototype-extracted (chips) | **PROPOSED-SCHEMA** `taxes.services service_type[]` (B2 has no column) | enum[] | user-input | ⊆ tenant-enabled |
| Computation form | S13 step 2 | prototype-extracted (3 cards) | **PROPOSED-SCHEMA** `taxes.kind` (percent\|flat_per_bill\|per_unit; B2 has only `rate`) | enum | user-input | one form per tax |
| Percent rate + base includes | S13 step 2 | prototype-extracted + B4.2 | `taxes.rate` (fraction, e.g. 0.0625) + **PROPOSED-SCHEMA** `taxes.base_includes_usage/base_includes_base` (fees/tax-on-tax not representable — BR-RAT-036) | numeric(18,6) | user-input | > 0; B4.2 bound |
| Flat amount + frequency | S13 step 2 | prototype-extracted ($0.85; every bill / once per fiscal year) | **PROPOSED-SCHEMA** `taxes.flat_amount`, `taxes.flat_frequency` | numeric(18,6)/enum | user-input | ≥ 0 |
| Per-unit amount + unit | S13 step 2 | prototype-extracted ($0.25 / kgal) | **PROPOSED-SCHEMA** `taxes.unit_amount`, `taxes.unit` | numeric(18,6)/text | user-input | unit must match service billed unit (BR-RAT-038) |
| "Applies above" threshold | S13 step 2 | prototype-extracted ("Tier 3 only") | **GAP** — semantics undefined (quantity vs tier ref) | — | user-input | OQ-054 (CLOSED→BR-RAT-042) |
| Liability GL / Remit to / Frequency / Filing form | S13 step 3 | prototype-extracted | `taxes` remittance fields — **PROPOSED-SCHEMA** `.liability_gl_account_id` (⚠ →ledger), `.remit_to`, `.remit_frequency`, `.filing_form` | uuid/text/enum | user-input | GL must exist |
| Effective from/to | S13 step 3 | prototype-extracted | **PROPOSED-SCHEMA** `taxes.effective_from/effective_to` (rate changes = new row, BR-RAT-037 discipline) | date | user-input | from < to |
| Plan attachment + override | S10 step 4 | B2 r5 #11 | `plan_tax_rules` (plan × jurisdiction UNIQUE; rate_override) | rows | user-input | unique pair |

**6 · Acceptance**
- Given the seed, When the tab opens, Then all four taxes render with rate, remittance and GL exactly as configured.
- Given the percent form, Then the taxable-base panel can only express the B4.2-legal base (usage/base) — fees and tax-on-tax are not offerable.
- Given plan attachments, Then plan × jurisdiction pairs are unique, overrides apply, and account-level exemption still zeroes tax (GT-11).
- Given cross-tenant sessions, Then jurisdiction lists never leak.

**7 · Finance Calculation** — Percent tax (CONFIRMED, B4.2): `tax = rate × Σ(taxable lines: usage + base)` — worked example (GT-10 fixture): usage 82.08 + base 18.50 = 100.58 taxable; 8.25% × 100.58 = 8.29785 → **$8.30** (half-up 2dp per line, BR-RAT-003); late fee 8.13 excluded → total 100.58 + 8.13 + 8.30 = **$116.01**. Flat form: $0.85/bill added as its own line (not in any base). Per-unit form: 0.25 × 3.72 kgal = 0.93 → **$0.93** line. Ref: **GT-10** (base), **GT-11** (exemption).

**8 · Open Questions**
| OQ | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| OQ-054 (CLOSED→BR-RAT-042) | S13 per-unit tax "Applies above" (Water Conservation Surcharge shown as "Water · Tier 3 · $0.25/kgal"): is the threshold a usage quantity or a tier reference, and how does a tax resolve tier numbering across plans with different tier tables? | Threshold-limited per-unit taxes only — plain per-unit buildable | Product Owner (chat session) | OPEN |
