# EP-CUS-07 — Account onboarding (brownfield import)

**Module:** customers (product name: Accounts) · **Wave:** W2 · **Screens:** S17 (entry) → **S68 Import accounts wizard** (assigned per OQ-063 closure, 2026-08-08) · **Status:** draft

## Scope
**In:** bulk migration of an existing utility's account base at cutover, per the PO onboarding rulings (BR-CUS-046..052): CSV upload against the published account template (BR-CUS-046 + customer-external-ref columns per BR-CUS-054), the source→target value-mapping step (BR-CUS-052), opening balances as AGED BUCKETS (BR-CUS-048), the balanced opening-journal-entry HANDOFF to ledger (BR-CUS-049 — customers writes no journal lines, B1), and deposits-on-file with ORIGINAL receipt dates feeding interest accrual (BR-CUS-050/057). Import mechanics = the platform standard (BR-CUS-051, same discipline as S52 assets / S28 reads): staged → per-row errors → skip-errors ON → "N created · N failed" → 10,000-row cap. Migration order enforced, not assumed: Premises → Units+Plans → Assets → **Accounts** → opening reads (BR-CUS-047) — rows referencing missing units error, never auto-create.
**Out:** premises/unit import (US-MET-004) · asset import (US-AST-010) · opening READS import (S28, metering — runs AFTER accounts per BR-CUS-047) · historical invoice/payment-level history (rejected/deferred by the PO — BR-CUS-048 chose buckets over invoice-level) · ledger posting execution (W5 posting service — this epic defines the contract only) · greenfield single-account creation (EP-CUS-02) · autopay method tokenization/drafting (W7; capture-only per BR-CUS-059).
**Tables:** customers-owned `accounts`/`contacts`/`addresses` + PROPOSED-SCHEMA Lane C batch #3 set flagged per story (`customers`, `customer_accounts`, `account_opening_buckets`, import staging + value-map tables, deposit-interest columns, credit-tier rule params, status lookup seed incl. Vacation hold). Reads/plans/assets referenced via service functions only (B1).

## Capability matrix (list screens only — B9 conformance)
| Screen | Search fields | Filters | Default sort | Sortable | Columns default/available | Row actions | Bulk actions | Export |
|---|---|---|---|---|---|---|---|---|
| — | *(no list screens — the import wizard is a staged full-page flow (screen ID pending OQ-063); its error-row review table is wizard-embedded, mirroring S52/S28)* | | | | | | | |

## Stories

---
id: US-CUS-019
epic: EP-CUS-07
module: customers
screens: [S17, S68]
wave: 2
status: draft
blocked_by: []
depends_on: [US-MET-004, US-AST-010, US-RAT-002, US-CUS-003, US-TEN-012]
journeys: [J2]
rules: [BR-CUS-017, BR-CUS-046, BR-CUS-047, BR-CUS-051, BR-CUS-054, BR-CUS-059, BR-CUS-060]
golden_tests: []
finance_calc: none
---
### US-CUS-019 — Bulk account upload against the published template (customer-linked, premises-first)

**1 · Details** — As a System Admin migrating a utility off its legacy system, I want to upload the account base as one CSV against the **published account template** (BR-CUS-046) — customer external ref + customer/contact columns, account # (blank → auto from the tenancy series), REQUIRED premises/unit ref, category/sub-type, plan override, status, deposit $ + original date, tax-exempt, autopay enrollment, aged opening-balance buckets, since date — see the staged preview with per-row errors, and commit with skip-errors ON, so that 1,200 legacy accounts land in one pass instead of 1,200 wizards. Entry: S17 header **Import accounts** (wizard = S68 per OQ-063 closure). Flow: upload → stage/validate → **value-mapping step (US-CUS-020)** → review counts → commit → **"N created · N failed"** summary with downloadable error report (BR-CUS-051). Rows sharing a `customer_ref` create/link ONE `customers` row with many accounts (BR-CUS-054 — landlord case). Premises-first discipline per BR-CUS-047: unit refs must resolve to existing units or the row errors. Opening buckets and deposits on each accepted row are handled by US-CUS-021/023; the template has **no bill-delivery-day column** (dropped, BR-CUS-060) and autopay is an enrollment flag only (capture-only, BR-CUS-059). J2: committed rows satisfy the step-4 handoff (account active where mapped so, plan snapshot from **the unit's plan — never the override**, deposit position set) ahead of the opening-reads import (step 5, S28). **⚠ TWO 2026-08-12 PO RULINGS CHANGE THIS IMPORT.** **(1) THE RETIRED PLAN COLUMN (OQ-166, delegated *"decide for me"* and decided):** the column lost its destination on 2026-08-11 when the account-side plan table was superseded, so **the row IMPORTS, the override is NOT applied, and the importer raises a per-row notice naming the unit's actual plan and the value it discarded** — silent only when the two already agree. Rejecting the row would fail a whole cutover over a legacy column that means nothing; ignoring it silently is worse, because a utility would believe they had set a plan and find out at the first bill run. **Worked:** row **412** says *unit `2205 Cedar Ln · Unit B`, plan `C1`*; the unit is on **RES-STD**; the account is created on **RES-STD** and the row reports **"plan C1 ignored — this unit is on RES-STD"**. **(2) RE-IMPORT MATCHES ON SOMETHING IN THE FILE (OQ-165):** *"Match on something in the file"* — the importer finds its key in the file (the customer reference, the unit reference, or a stated combination), **never on an id it minted**, because a corrected re-upload changes the bytes and the `file+tags` key stops matching.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-CUS-046 | EP-CUS-07 approved; template columns per AC-1 (account # auto-option, customer + contact, REQUIRED premises/unit ref, category/sub-type, ~~plan override~~, status, deposit $ + date, tax-exempt, autopay enrollment, opening balance, since date). **AMENDED PO 2026-08-12 (OQ-166): a row carrying the retired plan-override column IMPORTS, the column is NOT applied, and the row REPORTS what was discarded** (row 412: *"plan C1 ignored — this unit is on RES-STD"*). | CONFIRMED — PO AC-1 · **amended PO 2026-08-12** |
| BR-CUS-054 | Customer is a first-class entity: the template's `customer_ref` column groups account rows — one distinct ref = one `customers` row + N `customer_accounts` links; a ref matching an EXISTING tenant customer links instead of duplicating. PROPOSED-SCHEMA: `customers` + `customer_accounts` (Lane C batch #3). | CONFIRMED (entity + linkage) — PO OQ-057 (b); ref-matching mechanics PROPOSED — derivation from "multiple account rows link to one customer" |
| BR-CUS-047 | Migration order Premises → Units+Plans → Assets → Accounts → opening reads; account rows referencing missing units are row errors — never auto-created. **AMENDED PO 2026-08-12 (OQ-165): a RE-IMPORTED cutover file matches on something IN THE FILE — the customer reference, the unit reference, or a stated combination — never on an id the system minted.** | CONFIRMED — PO AC-2 · **amended PO 2026-08-12** |
| BR-CUS-051 | Import mechanics = the standard: staged (nothing writes until commit) → per-row errors with reasons → skip-errors ON default → "N created · N failed" summary always shown → 10,000-row cap. PLUS derivation: a row whose account # already exists (in-tenant or in-file) is a ROW ERROR — accounts are money-bearing, so there is NO spec-update re-upload path (unlike assets BR-AST-034); post-cutover corrections go through normal flows/J6. | CONFIRMED (standard) — PO AC-6 / duplicate-#-errors PROPOSED — derivation from financial immutability (CLAUDE.md #4), flagged for PO |
| BR-CUS-017 | *(shared)* at most one ACTIVE account per unit — enforced at import: a second active-status row for the same unit errors. | PROPOSED — B2 DDL + BR-MET-036 |
| BR-CUS-059 / BR-CUS-060 | Autopay column = enrollment flag, capture-only (execution W7, no re-enrollment); NO bill-delivery-day column — the preference is dropped, cycles decide bill dates. | CONFIRMED — PO OQ-059 final |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Dana uploads `bbu-accounts-cutover.csv` (1,240 rows) | Stage created; preview "1,240 rows · 1,213 valid · 27 errors" with per-row reasons; NOTHING written to `accounts`/`customers` yet (BR-CUS-051) |
| TC-2 | `customer_ref` CUST-118 (Bluebonnet Property Group LLC) appears on 3 rows (500 Main · Suites 201/202/203) | On commit: ONE `customers` row + THREE accounts + three `customer_accounts` links (BR-CUS-054); an S17 search on "Bluebonnet" later returns all three accounts |
| TC-3 | Commit with skip-errors ON | "1,213 created · 27 failed" summary + downloadable error report (BR-CUS-051); Active-mapped accounts derive unit occupancy (BR-MET-036); batch recorded; one `audit_log` `account.bulk_imported` (actor, counts, batch id) |
| TC-4 | 96 rows with account # blank | Numbers auto-allocated from the tenancy account series (BR-TEN-035); allocations listed in the result report |
| TC-4b *(PO 2026-08-12, OQ-165)* | Dana fixes one misspelt street name in `bbu-accounts-cutover.csv` and re-uploads the corrected file | **No duplicates.** The bytes changed so the `file+tags` key no longer matches, but the importer matches **row by row on a key IN the file** — without it, the **1,144** rows carrying explicit account numbers all error as duplicates while the **96** blank-number rows quietly create **96 new accounts** on units that already have one (and a row imported as *Pending activation* or *Closed* is caught by BR-CUS-017 not at all) |
| TC-4c *(PO 2026-08-12, OQ-166)* | Row **412**: unit `2205 Cedar Ln · Unit B`, plan override `C1`; the unit is on **RES-STD** | The row **IMPORTS** and the account is created on **RES-STD**; the override is **not applied**; the result report carries **"plan C1 ignored — this unit is on RES-STD"**. A row whose override already equals the unit's plan reports nothing |
| TC-5 *(negative)* | 14 rows reference unit "77 Industrial Way · Bldg C" (never imported) | Row errors "unit not found — import premises/units first (BR-CUS-047)"; never auto-created; the other rows unaffected |
| TC-6 *(negative)* | `bbu-oversize.csv` with 11,600 rows | Rejected at upload — exceeds the 10,000-row cap (BR-CUS-051); nothing staged |
| TC-7 *(negative)* | Two rows map to unit U-11024-201 both with status → Active; plus 3 rows whose account # `A-10432` already exists | Second-active row errors (BR-CUS-017); duplicate-# rows error (BR-CUS-051 derivation) — no silent update of a live account |
| TC-8 *(isolation)* | J. Okafor (Lone Star Ridge) uploads a file whose unit column names "1408 Elm Street · Unit A" and whose `customer_ref` values match Brazos Bend refs | Unit rows error "unit not found" (tenant-scoped resolution); customer_ref matching never touches Brazos Bend `customers`; committed rows carry Lone Star Ridge tenant_id (RLS) |

**4 · Test Data** — Tenant **Brazos Bend Utilities**, cutover **Aug 31, 2026**, legacy system "CivicCIS". File `bbu-accounts-cutover.csv`, 1,240 rows; sample row: `CUST-091, Individual, "Harmon, Luis", 1984-06-02, luis.harmon@example.com, +1 (281) 555-0177, same-as-service, L-4482, "2205 Cedar Ln · Unit B", RES, , R1, ACT, 150.00, 2019-03-14, N, Y, 84.20, 62.10, 0.00, 121.00, 2019-03-14` → creates **A-12103**. Landlord fixture: CUST-118 Bluebonnet Property Group LLC ×3 rows. Error mix (27): 14 unknown unit ("Bldg C"), 8 unmapped legacy values (US-CUS-020 fixture: 5 × status `LGL`, 3 × category `MUN`), 3 duplicate account #, 2 second-active-per-unit. Oversize file `bbu-oversize.csv` 11,600 rows. Actors: Dana Whitfield (System Admin); isolation J. Okafor (Lone Star Ridge).

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| CSV file / batch | import wizard (OQ-063) | BR-CUS-046 published template | **PROPOSED-SCHEMA** `account_import_batches` (tenant, filename, uploaded_by, row/valid counts, committed_at) + `account_import_rows` (batch, row_no, raw jsonb, errors jsonb, account_id NULL until commit) — mirrors the S28/S52 staging pattern | file/CSV UTF-8 | user-input | header row; ≤10,000 rows (BR-CUS-051) |
| customer_ref (column) | import wizard | BR-CUS-054 (PO ruling — not in the AC-1 verbatim list; added so many rows link one customer) | **PROPOSED-SCHEMA** `customers.external_ref` (UNIQUE per tenant) + `customer_accounts` links | text | user-input | distinct ref → one customer; existing ref → link |
| customer type / name / DOB / email / phone / mailing address (columns) | import wizard | BR-CUS-046 "customer + contact" | **PROPOSED-SCHEMA** `customers` (kind, display_name) + `contacts`/`addresses` rows (PII per BR-CUS-045; contacts re-home to the customer entity — Eng Lead disposition, EP-CUS-02 schema-note pattern) | text/date | user-input | email format; PII masked display |
| account # (column, optional) | import wizard | BR-CUS-046 "auto-option" | `accounts.account_no` (tenancy `number_series`, BR-TEN-035) | text | user-input / system-derived | unique per tenant; existing # = row error (BR-CUS-051 derivation) |
| premises/unit ref (column, REQUIRED) | import wizard | BR-CUS-046/047 | `accounts.unit_id` (⚠ cross-module FK, B2 §2) | text → uuid | user-input | must resolve to an existing tenant unit (BR-CUS-047) |
| category / sub-type (columns) | import wizard | BR-CUS-046 | `accounts.account_type_id` / `.account_subtype_id` (r5 #12/#19) — via value mapping (US-CUS-020) | text → uuid | user-input | mapped values only (BR-CUS-052) |
| plan override (column, RETIRED) | import wizard | BR-CUS-046 · **PO 2026-08-12 (OQ-166)** | ~~blank → unit's plan; value → account snapshot (`account_plan_assignments`, BR-CUS-029) + unit writeback per BR-CUS-014 sc.2~~ — **the column has NO destination: `account_plan_assignments` is SUPERSEDED (PO 2026-08-11) and customers may not write metering's `units.rate_plan_id` (B1 / DB-16). RULED 2026-08-12: the row IMPORTS, the value is DISCARDED, and a per-row notice names the unit's actual plan and the value dropped** | text (read, not stored) | user-input | **never applied**; notice raised unless the override already equals the unit's plan |
| status (column) | import wizard | BR-CUS-046 | `accounts.status` → BR-CUS-055 seeded lookup via value mapping (US-CUS-020) | text → lookup | user-input | mapped values only |
| deposit $ + original date (columns) | import wizard | BR-CUS-046/050 | per US-CUS-023 | numeric(18,6)/date | user-input | US-CUS-023 rules |
| tax-exempt (column) | import wizard | BR-CUS-046 | `accounts.tax_exempt` (+`.tax_exempt_ref` optional) | bool/text | user-input | B4.2 account-level |
| autopay enrollment (column) | import wizard | BR-CUS-046 + BR-CUS-059 | `accounts.autopay` — capture-only v1; no method tokenization at import (W7) | boolean | user-input | BR-CUS-059 |
| opening-balance buckets (4 columns) | import wizard | BR-CUS-048 | per US-CUS-021 | numeric(18,6) USD | user-input | US-CUS-021 rules |
| since date (column) | import wizard | BR-CUS-046 | `accounts.opened_at` | date | user-input | ≤ cutover |
| ~~bill delivery day~~ | — | BR-CUS-060 | DROPPED — no template column; cycles decide bill dates ("bill me on the 15th" = cycle assignment) | — | — | — |
| Preview counts / result summary / error report | import wizard | BR-CUS-051 | computed over `account_import_rows` | text/jsonb | computed-display | "N created · N failed" always shown |
| Audit | — | CLAUDE.md #7 | `audit_log` `account.bulk_imported` | jsonb | system-derived | append-only |

**6 · Acceptance**
- Given a staged file, Then valid/error counts and per-row reasons render and no `accounts`/`customers` row exists until commit.
- Given commit with skip-errors ON, Then exactly the valid rows create, the "N created · N failed" summary always shows with the error report, And rows sharing a customer_ref link to ONE customer.
- Given a row referencing a missing unit, a duplicate account #, or a second active account on a unit, Then that row errors and the rest import.
- Given a row carrying the **retired plan override**, Then it IMPORTS on the unit's plan and the result report names what was discarded — never rejected, never silent (PO 2026-08-12, OQ-166).
- Given a **corrected re-upload** of the same cutover file, Then rows are matched on a key IN THE FILE and nothing duplicates (PO 2026-08-12, OQ-165).
- Given a Lone Star Ridge session, Then unit and customer_ref resolution never crosses tenants.

**7 · Finance Calculation** — N/A (no amounts computed; buckets/deposits handled in US-CUS-021/023).

**8 · Open Questions**
| OQ | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| OQ-063 *(minted here)* | The import wizard has no A1 screen ID (S17 is only the entry; S61–S67 taken, S68 next free in the reserved block) | Ticket vocabulary only — wizard buildable | Product Owner (chat session) | CLOSED — S68 assigned |
| OQ-165 | A re-typed cutover file has no natural key for the rows whose account number the SYSTEM allocated, so importing it twice creates them twice (1,144 duplicate-errors + **96 new accounts** on occupied units) | Was: the corrected-file re-upload path | Product Owner (chat session) | **CLOSED 2026-08-12** — *"Match on something in the file"*: the importer keys on the customer reference, the unit reference or a stated combination, **never on an id it minted**. The `file+tags` key still catches the identical-bytes case |
| OQ-166 | The template's `plan_override` column lost its destination on 2026-08-11 — what should a row carrying one do? | Was: rows carrying a plan override (they errored) | Product Owner (chat session) | **CLOSED 2026-08-12 — DELEGATED (*"decide for me"*) and decided:** the row **imports**, the column is **not applied**, and the row **reports what was discarded** (row 412 → *"plan C1 ignored — this unit is on RES-STD"*). Rejecting fails a cutover over a meaningless legacy column; ignoring silently lets a utility believe they set a price they did not |

---
id: US-CUS-020
epic: EP-CUS-07
module: customers
screens: [S17, S68]
wave: 2
status: draft
blocked_by: []
depends_on: [US-CUS-019, US-TEN-010]
journeys: []
rules: [BR-CUS-051, BR-CUS-052, BR-CUS-055]
golden_tests: []
finance_calc: none
---
### US-CUS-020 — Source→target value-mapping step (legacy codes → tenant reference data)

**1 · Details** — As a System Admin, I want the wizard to pause after staging and show every DISTINCT legacy value found in the mapped columns — status, category, sub-type, plan code — each with a select of this tenant's reference-data targets (BR-CUS-055 statuses incl. Vacation hold/Suspended; account types/sub-types r5 #12/#19; published rate plans), so that legacy codes land on OUR vocabulary before anything is accepted (BR-CUS-052: "DB values will change"). Unmapped values leave their rows in error (rules-based import standard); the chosen mapping is SAVED per import batch for audit, so six months later anyone can answer "what did legacy `VAC` become?". Entry: automatic step between staging and review in US-CUS-019's flow. Exit: all mappings set (or deliberately left unmapped → those rows error) → review counts recompute.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-CUS-052 | Imports include a SOURCE→TARGET VALUE-MAPPING step: legacy codes (statuses, categories, plan codes…) map to this tenant's reference-data values before acceptance; unmapped values error per the rules-based standard. | CONFIRMED — PO AC-7 (PM interpretation flagged in the rules file: applied to the import wizard) |
| BR-CUS-055 | Status targets = the seeded, tenant-extensible account-status lookup (Pending activation · Active · Marked disconnect · Vacation hold/Suspended · Closed + tenant additions); behavior-class seed mapping tracked as OQ-064 (does not block mapping). | CONFIRMED (vocabulary) — PO OQ-058 (b) |
| BR-CUS-052 (persistence) | The batch's value map is stored (source column, source value, target ref, mapped_by, mapped_at) and immutable after commit — audit evidence, and the prefill offered on the tenant's NEXT account import (no cross-tenant reuse). | PROPOSED — derivation of "mapping saved per import batch for audit"; next-import prefill flagged (BR-MET-032 banned mapping memory for READ column mapping — value maps are a different object; PO may align) |
| BR-CUS-051 | *(shared)* unmapped-value rows follow the standard error path — skip-errors ON imports the rest. | CONFIRMED — PO AC-6 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | After staging TC-1 of US-CUS-019 | Mapping step lists distinct source values per domain — status: ACT · VAC · PND · CLS · DIS · LGL; category: RES · COM · GOV · MUN; plan: R1 · C1 — each with occurrence counts and a target select scoped to tenant reference data |
| TC-2 | Dana maps VAC → "Vacation hold/Suspended", DIS → "Marked disconnect", PND → "Pending activation", ACT → Active, CLS → Closed, R1 → RES-STD v3, C1 → COM-SM | All rows carrying those values re-validate clean; review counts update live |
| TC-3 | Legacy `LGL` (legal hold) has no seeded equivalent; Dana adds tenant status "Legal hold" in Reference data (BR-CUS-055 tenant-extensible, US-TEN-010) and maps LGL → it | Mapping accepts the tenant-added row; the 5 LGL rows validate; behavior class of the new status follows the reference-data definition (OQ-064 seed pending for the seeded five) |
| TC-4 *(negative)* | Category `MUN` left unmapped; commit with skip-errors ON | The 3 MUN rows fail with "unmapped value: category MUN"; summary counts them in "N failed"; error report names column + value (BR-CUS-052) |
| TC-5 *(negative)* | Forged request maps ACT → a non-existent status id / an archived plan | Rejected server-side — targets must be ACTIVE tenant reference-data rows / published plans; nothing stored |
| TC-6 *(isolation)* | J. Okafor's mapping step | Target selects list only Lone Star Ridge statuses/types/plans; his saved maps invisible to Brazos Bend (RLS) |

**4 · Test Data** — Source values per US-CUS-019 §4 (CivicCIS codes ACT/VAC/PND/CLS/DIS/LGL; RES/COM/GOV/MUN; R1/C1). Targets: Brazos Bend seeded statuses per BR-CUS-055 + tenant-added "Legal hold"; account types residential/commercial/government (+ industrial unused); plans RES-STD v3, COM-SM (EP-RAT-01 seed). Batch: `bbu-accounts-cutover.csv` map, 11 mappings, mapped_by Dana Whitfield, Aug 31 2026. Isolation: Lone Star Ridge Co-op Water Basic.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Distinct source values + counts | import wizard (OQ-063) | BR-CUS-052 | computed over `account_import_rows.raw` | text/int | computed-display | per mapped column |
| Target selects (status / category / sub-type / plan) | import wizard | BR-CUS-052/055 | account-status lookup (BR-TEN-036 pattern) / `account_types`+`account_subtypes` / `rate_plans` (⚠ rating read) | uuid | user-input | active/published targets only, tenant-scoped |
| Saved value map | — | BR-CUS-052 ("saved per import batch for audit") | **PROPOSED-SCHEMA** `account_import_value_maps` (batch_id, source_column, source_value, target_kind, target_id, mapped_by, mapped_at) — immutable post-commit | rows | system-derived | one row per (batch, column, source value) |
| Unmapped-value row errors | import wizard | BR-CUS-052 + BR-CUS-051 | `account_import_rows.errors` | jsonb | computed-display | names column + value |

**6 · Acceptance**
- Given staged rows, Then every distinct legacy value in the mapped columns is listed with a tenant-scoped target select, and unmapped values hold their rows in error.
- Given a committed batch, Then its value map is stored immutably and inspectable (who mapped what, when).
- Given tenant-extensible statuses, Then a tenant-added status is a valid mapping target.
- Given cross-tenant access, Then neither targets nor saved maps leak.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None new (behavior-class seed mapping = OQ-064, tracked on US-CUS-001; next-import prefill flagged inside the BR-CUS-052 persistence row, not blocking).

---
id: US-CUS-021
epic: EP-CUS-07
module: customers
screens: [S17, S68]
wave: 2
status: draft
blocked_by: []
depends_on: [US-CUS-019, US-CUS-020]
journeys: [J4]
rules: [BR-CUS-048, BR-CUS-051]
golden_tests: [GT-16]
finance_calc: proposed
---
### US-CUS-021 — Opening balances as aged buckets (aging correct from day one)

**1 · Details** — As a System Admin (on behalf of collections and finance), I want each imported account's opening balance captured as AGED BUCKETS — Current / 31–60 / 61–90 / 90+ days past due as of the cutover date — not a lump sum, so that aging reports, collections tiers and late fees are correct from day one (BR-CUS-048; lump-sum and invoice-level were explicitly rejected/deferred by the PO). The four template columns per row become immutable `account_opening_buckets` rows tied to the import batch; `accounts.balance` caches their sum; the aging display (BR-CUS-016 derivation) reads bucket age advancing by calendar days from the cutover as-of date. Collections (J4) treats bucket age exactly like invoice-due-date age: a 90+ bucket is notice-eligible on day one. Downstream: US-CUS-022 posts the balancing opening JEs. No screen of its own — the four columns live in US-CUS-019's template; totals surface on the review step and, post-commit, on S17/S21 balances.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-CUS-048 | Opening balances = AGED BUCKETS (Current / 31–60 / 61–90 / 90+ per account) at cutover, so aging, collections and late fees are correct from day one; lump-sum and invoice-level rejected/deferred. | CONFIRMED — PO AC-3 (option B) |
| BR-CUS-048 (forward aging) | Buckets age forward by CALENDAR DAYS from the cutover as-of date (an amount imported 45 days past due is 75 days past due 30 days later); the aging display derives — never re-stored (BR-CUS-016 pattern). Late-fee math on the overdue portion (BR-BIL-008/GT-8) reads the bucket-derived overdue amount; the fee itself is billing's (W3). | PROPOSED — derivation of "correct from day one"; finance confirms at GT-16 freeze |
| BR-CUS-048 (integrity) | `accounts.balance` = Σ bucket amounts exactly (cached; ledger becomes truth once US-CUS-022 posts); bucket rows are immutable — corrections via J6 adjustments, never edits. | PROPOSED — derivation from B2 `accounts.balance` comment + CLAUDE.md #4 |
| BR-CUS-051 | *(shared)* non-numeric or negative bucket values are row errors (negative = credit balance, held on OQ-065). | CONFIRMED (standard) / credit-balance handling OPEN — OQ-065 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | A-12103 imports with buckets 84.20 / 62.10 / 0.00 / 121.00 (as of Aug 31 2026) | Four `account_opening_buckets` rows (one may be zero-suppressed — see TC-5 note) + `accounts.balance` 267.30; S17 row shows $267.30 with derived "60+ past" pill (90+ bucket present); §7 math exact |
| TC-2 | Aging report 30 days later (Sep 30), nothing paid | A-12103 ages forward: 31–60 ← 84.20 · 61–90 ← 62.10 · 90+ ← 121.00 — derived, not re-stored (GT-16 forward-aging fixture) |
| TC-3 | Collections day one (J4) | A-12103's 90+ $121.00 makes it notice-eligible under the A19 tiers without any invoice existing; the overdue portion for late-fee math = 62.10 + 121.00 = 183.10 (fee computed by billing W3, GT-8 formula) |
| TC-4 *(negative)* | Row with bucket "abc" and row with bucket −45.00 | Both row errors: non-numeric; negative = legacy credit balance held pending OQ-065 (error message cites the OQ — no guessed handling); rest of file unaffected |
| TC-5 | Row with all four buckets blank/0.00 | Account imports with balance 0.00; no bucket rows, no opening JE (US-CUS-022 skips it) |
| TC-6 *(isolation)* | Lone Star Ridge aging query | Sees only its own bucket rows (RLS FORCE on the new table per B2 §3); a forged query with a Brazos Bend account id returns nothing |

**4 · Test Data** — Cutover Aug 31, 2026. A-12103 (Harmon, Luis): Current 84.20 · 31–60 62.10 · 61–90 0.00 · 90+ 121.00 → $267.30. Batch totals: 1,213 created accounts, Σ opening balances **$184,320.55** (matches the S17 roll-up fixture family). Zero-balance fixture: A-12140 (all buckets blank). Error fixtures: bucket "abc"; bucket −45.00 (CivicCIS credit customer CUST-204 — held on OQ-065). Isolation: Lone Star Ridge batch, 210 accounts, Σ $12,480.00.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| ob_current / ob_31_60 / ob_61_90 / ob_90_plus (columns) | import wizard (OQ-063) | BR-CUS-048 | **PROPOSED-SCHEMA** `account_opening_buckets` (tenant_id, account_id, import_batch_id, as_of date, bucket current\|d31_60\|d61_90\|d90_plus, amount numeric(18,6), currency char(3); UNIQUE (account, bucket); append-only, RLS FORCE) | numeric(18,6) USD | user-input | ≥ 0 (negative → OQ-065 error); blank = 0 |
| Cutover as-of date | import wizard (batch level) | BR-CUS-049 ("dated at cutover") | `account_opening_buckets.as_of` (= batch cutover date) | date | user-input | one date per batch |
| Opening balance (derived) | review step / S17 / S21 | BR-CUS-048 | `accounts.balance` = Σ buckets (cached) | numeric(18,6) USD | system-derived | exact sum, no rounding (already 2dp inputs) |
| Derived aging display | S17 / S21 pills, aging report | BR-CUS-016 pattern + BR-CUS-048 | bucket age + calendar days since as_of — computed, never stored | enum | computed-display | GT-16 forward-aging rule |

**6 · Acceptance**
- Given the §4 fixture, Then bucket rows + cached balance match §7 exactly and the day-one aging report reproduces the buckets verbatim.
- Given 30 days of no activity, Then the derived aging advances one band with no data rewrite.
- Given a negative or non-numeric bucket, Then the row errors citing OQ-065 / the standard, and nothing partial is written for it.
- Given J4, Then bucket-derived age feeds notice eligibility exactly like invoice age.

**7 · Finance Calculation** — Rule CONFIRMED (BR-CUS-048), fixture PROPOSED until the GT-16 freeze: `opening_balance = ob_current + ob_31_60 + ob_61_90 + ob_90_plus`. Worked example (A-12103): 84.20 + 62.10 + 0.00 + 121.00 = **$267.30** → `accounts.balance` 267.30; overdue portion day one = 62.10 + 0.00 + 121.00 = **$183.10** (late-fee base per GT-8, computed by billing); forward aging Sep 30 = 31–60 84.20 · 61–90 62.10 · 90+ 121.00. GT ref: **GT-16**.

**8 · Open Questions**
| OQ | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| OQ-065 *(minted here)* | Opening CREDIT balances (legacy overpayment): negative Current bucket, carried account credit (BR-PAY-010 pattern), or excluded from import? | Credit-balance rows only — debit import + JEs buildable; such rows error citing OQ-065 | Product Owner (chat session) | OPEN |

---
id: US-CUS-022
epic: EP-CUS-07
module: customers
screens: [S17, S68]
wave: 2
status: draft
blocked_by: []
depends_on: [US-CUS-021]
journeys: [J5]
rules: [BR-CUS-048, BR-CUS-049]
golden_tests: [GT-16]
finance_calc: proposed
---
### US-CUS-022 — Opening journal entries: the balanced AR↔clearing handoff to ledger

**1 · Details** — As the system (on behalf of finance), I want every committed import batch to emit a HANDOFF record set from which the **ledger posting service** (W5, 🔒 human-owned per CLAUDE.md) posts one balanced opening journal entry per account with an opening balance — **DR Accounts Receivable / CR Opening-balance clearing**, dated at the cutover date, immutable — so that the trial balance ties to the migrated AR from the first close (J5) and corrections happen only through J6. **Boundary (B1):** customers writes `account_opening_buckets` and this contract; it NEVER writes `journal_entries`/`journal_lines` — only the posting service does (CLAUDE.md #5). Until W5 lands, the handoff rows persist unposted and the posting call is stubbed at the boundary; no interim fake ledger rows. Contract per account: {import_batch_id, account_id, cutover_date (= JE entry_date), bucket amounts, total, currency, AR ledger-account ref, opening-clearing ledger-account ref}; idempotency: one JE set per (tenant, import_batch, account) — re-posting no-ops (key mechanics human-owned, CLAUDE.md #6). No screen of its own; posted results appear on ledger surfaces (S56 trial balance) in W5.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-CUS-049 | Opening balances post as balanced opening journal entries (AR ↔ opening-balance clearing), dated at cutover, immutable; corrections via J6 only. | CONFIRMED — PO AC-4 |
| BR-CUS-049 (granularity + accounts) | One JE per account (source_type `opening_balance`, source_id = the account's bucket set) so the AR subledger ties per account; the two ledger accounts are SEEDED tenant chart rows ("Accounts receivable", "Opening balance clearing" — codes per the tenant COA, B2 O-14) referenced by the contract, never hardcoded amounts-side. | PROPOSED — derivation from BR-CUS-049 + B2 r2 account-ledger view; seed flagged in Lane C batch #3 |
| BR-CUS-048 | *(shared)* JE total per account = Σ that account's buckets exactly. | CONFIRMED — PO AC-3 |
| CLAUDE.md #4/#5 *(cited, not restated)* | No UPDATE/DELETE on journal entries/lines; balanced pairs; only the posting service writes journal lines. | CONFIRMED — hard rules |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Batch commit (US-CUS-019 TC-3) | One handoff record per account with balance > 0 (1,213 − zero-balance accounts); each carries batch id, account, cutover date Aug 31 2026, bucket amounts, total, currency, AR + clearing refs |
| TC-2 | Posting service (W5) consumes the batch | Per account: JE dated 2026-08-31, source_type `opening_balance`; lines DR AR = total, CR clearing = total (balanced trigger passes); tenant check Σ JEs = $184,320.55 = clearing credit; J5 trial balance ties (debits = credits) |
| TC-3 | Correction after posting: A-12103's 90+ bucket was $21.00 too high | NO edit to bucket rows or the JE — a J6 adjustment (credit −21.00, reason "migration correction", approval per BR-CUS-038) posts its own reversing pair; original opening JE untouched |
| TC-4 *(negative)* | Direct UPDATE/DELETE attempted on a posted opening JE or its lines | Rejected by the append-only/immutability triggers (B2 §3); audit intact |
| TC-5 *(negative)* | A customers-module code path attempts to INSERT `journal_lines` directly; separately, the posting call fires twice for the same batch | Insert forbidden (B1 — only the posting service writes ledger rows); the double post no-ops on the (tenant, batch, account) idempotency guard — exactly one JE set exists |
| TC-6 *(isolation)* | Posting invoked with a Brazos Bend batch id under a Lone Star Ridge session GUC | Nothing posts — RLS on buckets/handoff + tenant re-check in the service; Lone Star Ridge's own batch posts only its 210 accounts |

**4 · Test Data** — Brazos Bend batch per US-CUS-021 §4: 1,213 accounts, Σ $184,320.55, cutover Aug 31 2026; A-12103 total $267.30. Seeded chart refs: "1200 Accounts receivable" (asset), "1290 Opening balance clearing" (asset-contra/clearing) — illustrative codes, tenant COA governs (B2 O-14). Correction fixture: −$21.00 J6 adjustment on A-12103. Isolation: Lone Star Ridge batch Σ $12,480.00.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Handoff record (per account) | — (service contract) | BR-CUS-049 | **PROPOSED-SCHEMA** — either a derived view over `account_opening_buckets` + batch, or a thin `opening_je_handoffs` table (batch_id, account_id, total, posted_at NULL, journal_entry_id NULL) — shape flagged for Eng Lead, not decided here | rows | system-derived | one per account with balance > 0 |
| JE entry_date | — | BR-CUS-049 "dated at cutover" | `journal_entries.entry_date` = batch cutover date (written by the posting service) | date | system-derived | = `account_opening_buckets.as_of` |
| JE source linkage | — | B2 `journal_entries.source_type/source_id` | source_type `opening_balance` (new value — flagged), source_id → account bucket set/batch | text/uuid | system-derived | polymorphic ref per B2 O-4 discipline |
| DR / CR lines | — | BR-CUS-049 | `journal_lines` (side debit AR / credit clearing, amount = total ≥ 0) — posting service only | numeric(18,6) | system-derived | balanced trigger (B2 §3) |
| AR / clearing account refs | — | BR-CUS-049 | `ledger_accounts` seeded rows (⚠ ledger read) — **PROPOSED seed** in Lane C batch #3 | uuid | reference-data | must exist in tenant chart |
| Posting idempotency | — | CLAUDE.md #6 | one JE set per (tenant, import_batch, account) — exact key mechanics human-owned | — | system-derived | double post no-ops |

**6 · Acceptance**
- Given a committed batch, Then a complete, balanced handoff record exists per nonzero account with the cutover date and both ledger refs — and customers has written zero journal rows.
- Given W5 posting, Then per-account JEs balance, Σ ties to the imported AR, and the J5 trial balance closes.
- Given any correction, Then it is a new J6 row referencing the original; the opening JE and buckets never change.
- Given a re-post or a cross-tenant post, Then nothing duplicates and nothing leaks.

**7 · Finance Calculation** — Rule CONFIRMED (BR-CUS-049), fixture PROPOSED until the GT-16 freeze. Per account: `DR AR = CR clearing = Σ buckets`. Worked example (A-12103): DR 1200 Accounts receivable **267.30** / CR 1290 Opening balance clearing **267.30** — entry_date 2026-08-31, source `opening_balance`. Batch: Σ DR = Σ CR = **$184,320.55**; after posting, the clearing account's credit balance equals the total migrated AR (it drains only via J6 corrections or a finance-directed reclass — finance's call at freeze, not decided here). GT ref: **GT-16**.

**8 · Open Questions** — None new (OQ-065 credit-balance rows tracked on US-CUS-021 would flow through this contract once ruled; ledger-account seed codes ride the tenant COA work, B2 O-14).

---
id: US-CUS-023
epic: EP-CUS-07
module: customers
screens: [S17, S68]
wave: 2
status: draft
blocked_by: []
depends_on: [US-CUS-019, US-CUS-020, US-CUS-007]
journeys: [J2]
rules: [BR-CUS-025, BR-CUS-050, BR-CUS-057]
golden_tests: []
finance_calc: proposed
---
### US-CUS-023 — Deposits-on-file import with original receipt dates + interest accrual start

**1 · Details** — As a System Admin, I want each imported account's held deposit captured with its ORIGINAL receipt date (BR-CUS-050) — not the cutover date — so that deposit interest (BR-CUS-057: tenant-set simple annual rate, default 0%, monthly accrual, payout at refund/closure) accrues from the TRUE date and a 2019 deposit refunds with seven years of interest, not one day's. Template columns `deposit_amount` + `deposit_received_on` (US-CUS-019) write `accounts.deposit_on_file` + the receipt date; the accrual engine (shared with US-CUS-007 — the old `NotImplementedError("OQ-061")` stub is RETIRED) computes monthly from the receipt date at the tenant's configured rate. Deposit liability remains a liability, never revenue (BR-CUS-025); the ledger side (deposit liability opening JE) is explicitly OUT here — flagged to the W5 ledger pack alongside US-CUS-022's contract, not invented. At move-out the imported deposit + accrued interest settles per BR-CUS-025/US-CUS-005.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-CUS-050 | Deposits import with their ORIGINAL receipt dates; interest accrual runs from the true date per the OQ-061 outcome (BR-CUS-057). | CONFIRMED — PO AC-5 |
| BR-CUS-057 | Deposit interest = tenant-set SIMPLE annual rate, default 0%, accrues monthly, pays out at refund/closure; accrual from the original receipt date. | CONFIRMED — PO OQ-061 (b) |
| BR-CUS-057 (engine derivation) | Monthly accrual = `deposit_on_file × annual_rate ÷ 12`, credited on each monthly anniversary of the receipt date, simple (no compounding — interest never joins the base); v1 computes history at the CURRENT tenant rate (the AC-1 template has no legacy-accrued-interest column, so recompute-from-true-date is the only BR-consistent reading). | PROPOSED — derivation of BR-CUS-057 + BR-CUS-050/AC-1; finance confirms with the deposit-interest GT |
| BR-CUS-050 (validation) | `deposit_received_on` is REQUIRED when `deposit_amount` > 0 (a deposit without its true date defeats the ruling); amount ≥ 0. | PROPOSED — derivation of "with their ORIGINAL receipt dates" |
| BR-CUS-025 | *(shared)* deposit is a liability, never revenue; at move-out deposit + accrued interest applies to the final bill FIRST, remainder refunds via payments. | PROPOSED — S20 hint + B2 r2; interest term now CONFIRMED per BR-CUS-057 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | A-12103 row: deposit 150.00, received 2019-03-14 | `deposit_on_file` 150.000000 + receipt date stored; S21 Deposit panel shows On file $150.00 with the true date; audit `deposit.imported` |
| TC-2 | Brazos Bend sets deposit interest rate 2.0% (S66 Billing defaults); accrual to cutover Aug 31 2026 | 89 full months since 2019-03-14 → accrued **$22.25** (§7); `deposit_interest_accrued` renders on S21/S20 |
| TC-3 | Tenant at the DEFAULT rate (0%) | Accrued = $0.00 forever until the tenant sets a rate — no silent platform rate (BR-CUS-057) |
| TC-4 *(negative)* | Row with deposit 150.00 and `deposit_received_on` blank; row with deposit −50.00 | Both row errors (date required with amount > 0; amount ≥ 0); rest of file unaffected (BR-CUS-051 standard) |
| TC-5 | A-12103 later moves out with final bill $92.30 | Settlement per BR-CUS-025/US-CUS-005 §7 shape: applied = min(150.00 + 22.25, 92.30) = 92.30 → refund $79.95 via payments `refunds`; the OQ-061 stub no longer exists in this path |
| TC-6 *(isolation)* | Lone Star Ridge import + its own 1.0% rate | Accruals use ONLY that tenant's rate and rows; Brazos Bend's 2.0% never leaks (RLS + tenant-scoped setting) |

**4 · Test Data** — A-12103: $150.00 received 2019-03-14 (CivicCIS receipt R-88213). Rates: Brazos Bend 2.0% simple annual (fixture; DEFAULT is 0%) → $0.25/month; Lone Star Ridge 1.0%. Cutover Aug 31 2026 → 89 full months (2019-03-14 → 2026-08-14; the Aug 14→31 stub month has not accrued). Error rows: date-blank deposit; −$50.00. Move-out settlement fixture per TC-5. Actors: Dana Whitfield; isolation J. Okafor.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| deposit_amount (column) | import wizard (OQ-063) | BR-CUS-046/050 | `accounts.deposit_on_file` | numeric(18,6) USD | user-input | ≥ 0 |
| deposit_received_on (column) | import wizard | BR-CUS-050 | **PROPOSED-SCHEMA** `accounts.deposit_received_on date` (Lane C batch #3) | date | user-input | required when amount > 0; ≤ cutover |
| Tenant interest rate | S66 Billing defaults | BR-CUS-057 | **PROPOSED-SCHEMA** tenant billing settings `deposit_interest_rate_annual numeric(18,6) DEFAULT 0` | numeric fraction | reference-data | ≥ 0; tenant-set, default 0% |
| Interest accrued | S21 Overview / S20 step 3 | BR-CUS-057 | `accounts.deposit_interest_accrued` (PROPOSED-SCHEMA column from EP-CUS-02 — rule now CONFIRMED, stub retired) | numeric(18,6) USD | system-derived | monthly accrual per §7 |
| Deposit election on import | — | BR-CUS-046 | `accounts.deposit_election` = `carried`-equivalent import value — **flag:** the EP-CUS-02 enum (collect_now\|first_bill\|waived\|carried) may gain `imported` (Lane C note), not decided here | enum | system-derived | exclusive per account |
| Deposit liability opening JE | — | BR-CUS-025 + BR-CUS-049 pattern | **GAP-flagged to the W5 ledger pack** — deposit liability ↔ clearing at cutover mirrors US-CUS-022 but was not in the PO AC rulings; customers writes nothing | — | — | flagged, not invented |

**6 · Acceptance**
- Given a deposit row, Then amount + original date store and display, and a missing date with a positive amount errors the row.
- Given a tenant rate, Then accrual = §7 exactly from the true receipt date; at 0% it is 0.00.
- Given a later move-out, Then deposit + accrued interest settle apply-first per BR-CUS-025 with no OQ-061 stub anywhere in the path.
- Given two tenants, Then rates and accruals never cross.

**7 · Finance Calculation** — Rule CONFIRMED (BR-CUS-057), engine derivation PROPOSED pending the deposit-interest GT: `monthly_accrual = deposit_on_file × annual_rate ÷ 12`, credited each monthly anniversary of `deposit_received_on`, simple interest (base never compounds); `accrued(d) = full_months(deposit_received_on → d) × monthly_accrual`. Worked example (A-12103, rate 2.0%): 150.00 × 0.02 ÷ 12 = 0.25/month; full months 2019-03-14 → 2026-08-31 = 89 → accrued **$22.25**; payout at refund/closure only (TC-5: applied 92.30, refund 79.95). Default-rate check: 0% → **$0.00**. GT ref: — the deposit-interest GT required by the BR-CUS-057 Test column is FLAGGED for number allocation at the golden-test freeze (only GT-16 was allocated to this pack).

**8 · Open Questions** — None new (deposit-liability opening JE flagged in §5 to the W5 ledger pack; OQ-065 credit balances tracked on US-CUS-021).
