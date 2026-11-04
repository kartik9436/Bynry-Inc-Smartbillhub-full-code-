# EP-RAT-01 — Plans

> Reconciled 2026-08-08 against PO rulings (decision log) — propagation sweep.

**Module:** rating (product name: Plans & Rates) · **Wave:** W1 · **Screens:** S9 (Plans tab), S10 · **Status:** draft

## Scope
**In:** the Plans tab of Plans & Rates (S9) and the New Plan guided wizard (S10, six steps per prototype: Basics → Services → Rate schedules → Charges & discounts → Eligibility → Review & publish). A plan is the full product bundle a customer subscribes to (BR-RAT-025 D4): per-service rate-schedule attachment (`plan_rate_schedules`), per-service base charges (`plan_services.base_charge`, BR-RAT-012/027), plan-scoped deposit / charge / penalty / tax rules (`plan_deposit_rules` / `plan_charge_rules` / `plan_penalty_rules` / `plan_tax_rules`, B2 r5 #8–#11), **plan discounts as negative-amount charge rules + budget-billing plan flag (BR-RAT-043)**, category targeting (D5, `account_types`), plan lifecycle (draft → published → archived, B2 r5 #18) and plan versioning (`plans.version` + `unit_plan_assignments.plan_version` snapshot, BR-CUS-013). **v1 plans are staff-assignment only (BR-RAT-039 as-modified).**
**Out:** rate-schedule *content* (structures/tiers/windows — EP-RAT-02) · charge-code and tax *catalogs* (EP-RAT-03; this epic only attaches them) · effective-dated tariff-version mechanics and bulk updates (EP-RAT-04) · any pricing math (EP-RAT-05/06) · assigning a plan to a unit/account (customers module, BR-CUS-010/011; this epic owns the plan side only) · self-serve plan offering and zone/route restriction (**dropped from v1 — BR-RAT-039 as-modified, PO R5-3**) · eligibility *enforcement* with verified documents (v2 — eligibility is advisory-with-audit in v1 per BR-RAT-043) · budget-billing level-pay *mechanics* (EP-BIL-06; this epic stores the plan flag only, BR-RAT-043).

> **Schema note (Eng Lead, pre-migration):** B2 r5 #18 modifies `plans`, but the only `plans` table in B2 base DDL is the **platform SKU table** (Starter/Growth/Scale). The rating plan bundle needs its own tenant-scoped table (or the platform table renamed). Mapped below as rating `plans` per r5 wording; collision flagged, not resolved here (r5 preamble: technical review owed by Eng Lead).

## Capability matrix (list screens only — B9 conformance)
| Screen | Search fields | Filters | Default sort | Sortable | Columns default/available | Row actions | Bulk actions | Export |
|---|---|---|---|---|---|---|---|---|
| S9 Plans tab | plan name, plan code | status (All/Published/Draft/Archived), service, customer class | name asc | name, base charges, accounts, status | 6 default (Plan · Services included · Rate schedules · Base charges · Accounts · Status) / 8 available (+Code, +Effective from) — IS-5 chooser | View, Edit (draft) / New version (published), Publish (draft), Archive (IS-1 deactivate-first; hard delete only when accounts = 0 and never billed) | — (v1) | CSV (IS-9) |

## Stories

---
id: US-RAT-001
epic: EP-RAT-01
module: rating
screens: [S9]
wave: 1
status: draft
blocked_by: []
depends_on: [US-TEN-007, US-SHL-006, US-SHL-007, US-SHL-008]
journeys: [J2]
rules: [BR-RAT-012, BR-RAT-024, BR-RAT-025, BR-RAT-027, BR-RAT-030]
golden_tests: []
finance_calc: confirmed
---
### US-RAT-001 — Plans list tab

**1 · Details** — As an Owner/Admin, I want a Plans tab listing every customer-facing plan with its bundled services, attached rate schedules, derived base charge, account count and lifecycle status, so that I can see the product catalog at a glance and open the wizard to add or revise a plan. Entry: sidebar → Plans & Rates (S9; Plans is the default tab; page header shows the roll-up "N plans · N rate schedules · N charge codes · effective <date>" per prototype). Exit: **+ New plan** → S10; row click → plan detail/edit; **History** → rate-change log view (EP-RAT-04). Explainer copy per prototype: "A **plan** is what customers subscribe to — a bundle of rate schedules and charges per service… A **rate schedule** defines the pricing math; plans reference them." List renders through the shared table framework per the capability-matrix row (EP-SHL-02); states per A18.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-RAT-025 | Plan-as-bundle (D4): deposit/charge/penalty/tax rules are plan-scoped with tenant defaults as fallback; category targeting via plans (D5). | CONFIRMED — PO Q&A R3 (D1–D9 blanket) |
| BR-RAT-012 / BR-RAT-027 | Base charge is per service within the plan; the plan's displayed base is **derived** (Σ service bases), never stored. | CONFIRMED — PO Q&A R1 Q2 / R5 Q9 |
| BR-RAT-024 | Services shown/selectable ⊆ the 10-service platform catalog ∩ tenant-enabled services. | CONFIRMED — PO Q&A R3 (OQ-052 + D4) |
| BR-RAT-030 | Plan lifecycle draft → published → archived: only published plans are assignable; drafts are never billed; archiving blocks new assignment but keeps history intact (existing accounts unaffected until changed). **A plan that HAS BEEN BILLED cannot be hard-deleted — and that guard is LIVE only since 2026-08-12 (DEF-079).** Until then `delete_plan` asked billing a question billing had never answered, got **0**, and permitted the delete of a historic plan with its rate schedules and every charge, deposit, penalty and tax rule; a plan LIVE on a unit was protected by the FK, a retired one was not. `apps/billing/selectors.plan_invoice_count` is published and the refusal now bites. | CONFIRMED — PO R5-4 (B2 r5 #18 enum + assignability semantics ratified); **enforcement LIVE 2026-08-12** |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Dana opens Plans & Rates with the §4 seed | 6 plan rows; header roll-up "6 plans · 7 rate schedules · 8 charge codes · effective Aug 1, 2026"; default sort name asc; Base charges column shows the derived sums (e.g. Residential Standard $30.50/mo = 18.50 + 12.00) |
| TC-2 | Filter Status = Draft | Only Vacant / Standby remains; chip + URL state per IS-4 |
| TC-3 | Search "commercial" | Small Commercial only (name match, server-side per IS-3) |
| TC-4 | Sort by Accounts desc | Residential Standard (842) first; stable secondary sort by id (IS-2) |
| TC-5 *(negative)* | Dana chooses hard Delete on Residential Standard (842 accounts) | Audit-locked: "referenced by accounts — archive instead" (IS-1); no row removed |
| TC-5b *(negative — the never-billed half, DEF-079)* | Dana chooses hard Delete on a plan with **0 accounts** that HAS been billed (its charges appear on issued invoice lines) | Refused. The "never billed" test is answered by the published counter `apps.billing.services.plan_invoice_count`, not by an unwired seam returning 0 — before 2026-08-12 this delete SUCCEEDED and took the plan's rate schedules, charges, deposit, penalty and tax rules with it (`tests/test_def_079_dark_counters.py`, written from the guard's side) |
| TC-6 *(negative)* | Marcus Vega (Billing Clerk) opens the tab | Read-only view per A4 role matrix (Plans & Rates = View for staff); + New plan renders disabled-with-reason (IS-6); server rejects a forged POST |
| TC-7 *(isolation)* | J. Okafor (Lone Star Ridge) opens Plans | Sees only "Co-op Water Basic"; automated test asserts no Brazos Bend plan id in any page/sort/search permutation (RLS `app.tenant_id`) |

**4 · Test Data** — Tenant: **Brazos Bend Utilities** (`brazosbend`, Katy TX; rating-pack fixture enables Electric, Water, Sewer, Solar, Battery per BR-RAT-024; Gas stays disabled). Plans: **Residential Standard** (RES-STD, Residential, published v3, E+W, bases 18.50/12.00 → $30.50, 842 accts) · **Residential Electric-only** (RES-E, Residential, published, E, 18.50, 184) · **Small Commercial** (COM-SM, Commercial, published, E+W, 36.00/12.00 → $48.00, 96) · **Industrial** (IND, Industrial, published, E+W+S, 160.00/12.00/8.00 → $180.00, 18) · **Solar Residential** (RES-SOL, Residential, published, E+Solar+Battery, 18.50/0/0 → $18.50, 12) · **Vacant / Standby** (STBY, Residential, **draft**, E+W, 10.00/5.00 → $15.00, 0). Isolation tenant: **Lone Star Ridge Water Co-op** (`lonestarridge`), plan "Co-op Water Basic" (W flat). Actors: Dana Whitfield (System Admin), Marcus Vega (Billing Clerk).

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Plan name + description | S9 | prototype-extracted | rating `plans.name` / **PROPOSED-SCHEMA** `plans.description` (r5 #18 names no descriptive columns; see epic schema note) | text | user-input | name unique per tenant |
| Services included | S9 | prototype-extracted (E/W/S tags) | `plan_services` rows (plan × service UNIQUE, r5 #6) → `services` catalog (r5 #1) | reference | reference-data | ⊆ tenant-enabled (BR-RAT-024) |
| Rate schedules | S9 | prototype-extracted ("Res Electric · Tiered…") | `plan_rate_schedules.tariff_id` → `tariffs.name` (r5 #7) | reference | reference-data | one schedule per service per plan (D2) |
| Base charges | S9 | prototype-extracted ("$30.50/mo") | Σ `plan_services.base_charge` — derived, never stored (r5 #6) | numeric(18,6) USD | computed-display | display 2dp |
| Accounts | S9 | prototype-extracted | count over `unit_plan_assignments` current rows (r5 #13; ⚠ cross-module read via service function, B1) | integer | computed-display | — |
| Status | S9 | prototype-extracted (Active/Draft pills) | `plans.status` (draft \| published \| archived, r5 #18) | enum | system-derived | BR-RAT-030 |
| Header roll-up | S9 | prototype-extracted | counts over `plans` / `tariffs` / `charges` | integers | computed-display | — |

**6 · Acceptance**
- Given the §4 seed, When Dana opens Plans, Then all six Brazos Bend plans render with service tags, schedule names, derived base sums and status pills, And the roll-up counts match.
- Given a plan referenced by accounts, When Delete is attempted, Then it is audit-locked and Archive is offered instead.
- Given a Lone Star Ridge session, Then zero Brazos Bend plans appear in any permutation.

**7 · Finance Calculation** — Derived plan base (BR-RAT-027, CONFIRMED): `plan_base = Σ plan_services.base_charge over the plan's services`. Worked example (§4): Residential Standard = 18.50 (E) + 12.00 (W) = **$30.50/mo** displayed. Display-only sum — no rounding beyond 2dp display (components are exact); billing of the base happens in EP-RAT-05 per B4. GT ref: —.

**8 · Open Questions** — None.

---
id: US-RAT-002
epic: EP-RAT-01
module: rating
screens: [S10]
wave: 1
status: draft
blocked_by: []
depends_on: [US-RAT-001, US-RAT-005, US-RAT-008, US-RAT-009, US-SHL-010]
journeys: [J2]
rules: [BR-RAT-012, BR-RAT-020, BR-RAT-023, BR-RAT-024, BR-RAT-025, BR-RAT-026, BR-RAT-027, BR-RAT-030, BR-RAT-039, BR-RAT-043]
golden_tests: []
finance_calc: confirmed
---
### US-RAT-002 — New Plan guided wizard (identity → services & schedules → per-service bases → plan rules → review/publish)

**1 · Details** — As an Owner/Admin, I want a guided six-step wizard — 1 Basics (name, code, customer class, description) → 2 Services (chips from the tenant-enabled catalog) → 3 Rate schedules (one schedule + base charge per ticked service) → 4 Charges & deposits & penalty & tax rules (plan-scoped attachments per r5 #8–#11; **discounts attach as negative-amount charge rules, budget billing is a plan flag — BR-RAT-043**) → 5 Eligibility & effective window (category targeting; **v1 availability is staff-assignment only — the prototype's self-serve/zone availability toggles are dropped per BR-RAT-039 as-modified**; eligibility checkboxes are **advisory-with-audit** per BR-RAT-043) → 6 Review & publish — so that a complete customer offering is assembled and published in one pass. Entry: S9 Plans tab **+ New plan**. Wizard mechanics (step rail, Save draft & exit, Cancel, Review) conform to EP-SHL-03; step 3's "Create a new rate schedule" link opens S11 and returns. Exit: **Publish plan ✓** → status published, toast → S9; **Save as draft** → status draft. Step-6 copy per prototype: publish makes the plan assignable (by staff); "no live customer is affected right now."

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-RAT-025 | D1–D9 govern the wizard's shape: rate structure not service-tied (D1) · one schedule per service per plan (D2) · plan-as-bundle with plan-scoped deposit/charge/penalty/tax rules and tenant defaults as fallback (D4/D6–D8) · category targeting via plans (D5). | CONFIRMED — PO Q&A R3 |
| BR-RAT-012 / BR-RAT-027 | Step 3 captures base charge **per service** (`plan_services.base_charge`); the review step shows the derived plan total. | CONFIRMED — PO Q&A R1/R5 |
| BR-RAT-020 / BR-RAT-023 | Step 4 deposits: **plan-level** fixed $ per consumer category (Res/Com/Ind/Gov) via `plan_deposit_rules` — supersedes the prototype's single DEPO-R checkbox; 2×-average/per-service/credit-waivers explicitly out of v1. | CONFIRMED — PO Q&A R1 D6 + R3 |
| BR-RAT-024 | **AMENDED 2026-08-21 (PO ruling, walking PLN-03 step 2 against r10) — A SERVICE THE UTILITY HAS NOT SWITCHED ON IS NOT DRAWN AT ALL.** PO verbatim: _"Second page - only services that are selected for this utility - you are showing all and UI does not match"_. **THIS REVERSES THE SECOND HALF OF THIS RULE**, which read _"disabled services render disabled, never hidden"_ and was CONFIRMED at PO Q&A R3. Step 2 now lists the tenant-ENABLED subset only; the ten-service platform catalogue is unchanged and so is per-tenant enablement, which is the FIRST half and still stands. **Worked, so the change is legible:** Silver Creek Water has water, sewer and trash switched on, so step 2 draws **three** tiles where it drew **ten** — seven of them greyed with _"Not switched on for this utility"_. **WHY THE OLD HALF EXISTED, recorded so a reversal is not mistaken for an oversight:** disabled-not-hidden is BR-SHL-025's house style — _"hiding actions on visible screens breeds 'where did it go' tickets"_ — and it let an operator SEE what the product can do and infer where to turn it on. The PO has ruled that on this step the noise costs more than the discoverability: seven dead rows above three live ones is the first screen a new tenant meets in Plans & Rates. ⚠ **THE SCOPE IS THIS STEP AND ONLY THIS STEP.** `BR-MET-003` states the same disabled-never-hidden rule for the service chips on premises and units, and `BR-SHL-025` states it for role-gated actions everywhere. **Neither is touched** — a signature covers only what was shown, and what was shown was PLN-03 step 2. **Where the enablement list is set stays discoverable**: the step names Settings → Services in its footer, which is the sentence the greyed rows used to carry. | **`BR-RAT-095`** (the canonical row for this ruling, rating 02-business-rules) · PO ruling 2026-08-21 (decision log) · was PO Q&A R3 | **CONFIRMED-AS-AMENDED (2026-08-21)** · the *never hidden* half is **SUPERSEDED (PO ruling 2026-08-21)** | `PlanWizard.test.tsx::US-RAT-002 TC-4 / BR-RAT-024` (amended, not deleted — it asserted the disabled control and now asserts the absence + the enabled tiles) |
| BR-RAT-026 | No allowance/"included units" field anywhere in the wizard — pure tiers only (schedule side owns tiers). | CONFIRMED — PO Q&A R5 Q5 |
| BR-RAT-030 | *(shared)* publish/draft lifecycle. | CONFIRMED — PO R5-4 |
| BR-RAT-039 | **v1 plans are STAFF-ASSIGNMENT ONLY** — the prototype's self-serve-signup offering and zone/route-restriction flags are dropped from v1 (no columns shipped); publishing makes a plan available to staff assignment. Step-5 eligibility checkboxes stay advisory per BR-RAT-043. | CONFIRMED-AS-MODIFIED — PO R5-3 |
| BR-RAT-043 | Plan discounts = **negative-amount charge rules** on the plan (e.g. paperless −$2.00/mo, autopay −$3.00/mo); budget billing = **plan flag** (level-pay mechanics in EP-BIL-06); eligibility (senior/CAP/low-income) is **advisory-with-audit** in v1 — staff attests at assignment, an audit row records who/when; enforced verification + document uploads = v2. | CONFIRMED — PO (closes OQ-055) |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Dana builds "Residential Standard" (RES-STD, Residential): services E+W; schedules Res Electric · Tiered / Res Water · Inclining; bases 18.50 / 12.00; charges CONN, DISC, LATE; deposits Res $150 / Com $300 / Ind $500 / Gov $0; tax rules TX State 6.25% + Fort Bend 2.00%; effective Sep 1, 2026; publishes | `plans` row (published, version 1) + 2 `plan_services` + 2 `plan_rate_schedules` + 3 `plan_charge_rules` + 4 `plan_deposit_rules` + 2 `plan_tax_rules`; review showed derived base $30.50; toast; `audit_log` `plan.published` |
| TC-2 | Step 4 penalty panel left untouched | `plan_penalty_rules` row absent (or all-NULL) → tenant defaults apply at billing time (r5 #10 fallback); review states "Late fee: tenant default" |
| TC-3 | Save draft & exit at step 3 | Draft plan persists with steps 1–3 content; reopening resumes at step 3 (EP-SHL-03); draft never appears in assignment pickers (BR-RAT-030) |
| TC-4 | Gas chip in step 2 | Renders disabled (Gas not enabled for Brazos Bend) — BR-RAT-024 |
| TC-5 *(negative)* | Publish attempted with service Water ticked but no Water schedule chosen | Blocked at review with inline error "every service needs a rate schedule" (D2); nothing published |
| TC-6 *(negative)* | Step 3 base charge entered as −5.00 | Inline validation error (base ≥ 0); Continue blocked |
| TC-7 *(negative)* | Second plan named "Residential Standard" saved | Rejected by (tenant, name) uniqueness with inline error |
| TC-8 *(isolation)* | Lone Star Ridge admin runs the wizard | Schedule picker lists only Lone Star Ridge `tariffs`; charge/tax pickers likewise; created rows carry Lone Star Ridge tenant_id |
| TC-9 | Dana ticks paperless (−$2.00/mo) and autopay (−$3.00/mo) discounts and Budget billing in step 4; the CAP-subsidy eligibility box in step 5 | 2 `plan_charge_rules` rows with **negative** amounts (recurring) + `plans.budget_billing` = true (BR-RAT-043); the CAP checkbox stores as **advisory** — assignment is never blocked by it; staff attestation + audit row happen at assignment time (customers flow); step 5 renders **no** self-serve/zone availability toggles (BR-RAT-039) |

**4 · Test Data** — Actor Dana Whitfield. Plan per TC-1 (values above). Deposit schedule: residential $150.00, commercial $300.00, industrial $500.00, government $0.00. Charge catalog rows CONN $85.00 / DISC $45.00 / LATE 1.5% min $5.00 (EP-RAT-03 seed). Discounts: paperless −$2.00/mo, autopay −$3.00/mo (negative charge rules, BR-RAT-043). Tax rows TX State Utility Tax 6.25%, Local · Fort Bend County 2.00%. Schedules from EP-RAT-02 seed. Lone Star Ridge: schedule "Co-op Water Flat", plan wizard run by J. Okafor.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Plan name / code / description | S10 step 1 | prototype-extracted | `plans.name` / **PROPOSED-SCHEMA** `plans.code`, `plans.description` (not named in r5 #18) | text | user-input | name unique per tenant; code short |
| Customer class | S10 step 1 | prototype-extracted (4 options) | **PROPOSED-SCHEMA** `plans.account_type_id` → `account_types` (r5 #12; D5 names the targeting, r5 names no column) | uuid | reference-data | platform-seeded categories |
| Service chips | S10 step 2 | prototype-extracted | `plan_services` (plan × service UNIQUE) | reference | user-input | ⊆ tenant-enabled |
| Rate schedule per service | S10 step 3 | prototype-extracted | `plan_rate_schedules.tariff_id` (plan × service UNIQUE, r5 #7) | uuid | reference-data | schedule's service must match row; same tenant |
| Base charge per service | S10 step 3 | prototype-extracted ("$18.50/mo") | `plan_services.base_charge` + `plan_services.currency` (r5 #6) | numeric(18,6) + char(3) | user-input | ≥ 0 |
| GL per service row | S10 step 3 | prototype-extracted (4100/4200/4300) | **PROPOSED-SCHEMA** `plan_services.gl_account_id` (⚠ →ledger; r5 #6 omits it) | uuid | reference-data | must exist, same tenant |
| Charge attachments | S10 step 4 | prototype-extracted (checkbox list) | `plan_charge_rules` (charge, amount_override NULL=catalog, recurrence once\|recurring\|event, taxable — r5 #9) | rows | user-input | charge active |
| Deposit schedule | S10 step 4 | B2 r5 #8 + BR-RAT-023 (supersedes prototype single checkbox) | `plan_deposit_rules` (plan × account_type UNIQUE → amount) | numeric(18,6) | user-input | ≥ 0; one row per category |
| Penalty overrides | S10 step 4 | B2 r5 #10 (D6) | `plan_penalty_rules` (late_fee_min/pct, grace_days, grace_mode; NULL → tenant default) | numeric/int/enum | user-input | grace_days 0–30 (BR-BIL-008) |
| Tax rules | S10 step 4 | B2 r5 #11 (D8) | `plan_tax_rules` (plan × jurisdiction UNIQUE; rate_override NULL=jurisdiction rate) | rows | user-input | jurisdiction is tenant-entered (BR-TEN-037) |
| Discounts & billing options | S10 step 4 | prototype-extracted (paperless −$2, autopay −$3, budget billing, CAP subsidy) | discounts = `plan_charge_rules` rows with **negative** amounts (BR-RAT-043); budget billing = **PROPOSED-SCHEMA** `plans.budget_billing` boolean (level-pay mechanics EP-BIL-06) | numeric(18,6)/bool | user-input | BR-RAT-043 (CONFIRMED — OQ-055 closed) |
| Effective from/to | S10 step 5 | prototype-extracted | **PROPOSED-SCHEMA** `plans.effective_from/effective_to` — *the prototype's self-serve/zone availability toggles are dropped from v1 (staff-assignment only, BR-RAT-039)* | date | user-input | from < to |
| Eligibility checkboxes (CAP proof / ≥25 kW / occupied) | S10 step 5 | prototype-extracted | **advisory-with-audit** — stored on the plan; staff attests at assignment, audit row records who/when; enforcement + uploads = v2 (BR-RAT-043) | bool | user-input | never blocks assignment in v1 |
| Publish / Save as draft | S10 step 6 | prototype-extracted | `plans.status` + `plans.version` (r5 #18) | enum/int | system-derived | BR-RAT-030 |

**6 · Acceptance**
- Given a completed wizard, When Dana publishes, Then plan + plan_services + plan_rate_schedules + plan_charge_rules + plan_deposit_rules (+ optional penalty/tax rules, negative-amount discount rules and the budget-billing flag) exist atomically with audit rows, the review's derived base equals Σ bases, And nothing was billed.
- Given a missing schedule, negative base, or duplicate name, Then the wizard blocks with inline errors and writes nothing.
- Given eligibility checkboxes ticked, Then they store as advisory only — no assignment is ever blocked by them in v1 (BR-RAT-043) — and no self-serve/zone availability control renders anywhere (BR-RAT-039).
- Given the isolation seed, Then no cross-tenant schedule, charge, jurisdiction or plan is ever selectable.

**7 · Finance Calculation** — Display math only (no billing here): derived plan base per US-RAT-001 §7 (Σ = 30.50, BR-RAT-027 CONFIRMED); deposit preview = `plan_deposit_rules[account_type]` fixed $ lookup (BR-RAT-020/023 CONFIRMED — e.g. Residential → $150.00, no formula); discount preview = attached negative charge rules (e.g. paperless −$2.00 + autopay −$3.00 = −$5.00/mo shown on review, BR-RAT-043). Billing-time math is EP-RAT-05's. GT ref: —.

**8 · Open Questions**
| OQ | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| OQ-055 | S10 step 4 "Discounts & billing options" + step-5 eligibility checkboxes: mechanism and enforcement? | — (resolved) | Product Owner (chat session) | **CLOSED(→BR-RAT-043)** — discounts = negative charge rules; budget billing = plan flag; eligibility advisory-with-audit v1, enforced + uploads v2 (PO) |

---
id: US-RAT-003
epic: EP-RAT-01
module: rating
screens: [S9, S10]
wave: 1
status: draft
blocked_by: []
depends_on: [US-RAT-002, US-RAT-010]
journeys: [J2]
rules: [BR-RAT-017, BR-RAT-025, BR-RAT-030, BR-RAT-037]
golden_tests: []
finance_calc: none
---
### US-RAT-003 — Plan lifecycle, versioning & category targeting maintenance

**1 · Details** — As an Owner/Admin, I want to edit a published plan safely — every content edit increments `plans.version` and is logged, existing accounts keep the version snapshotted at assignment (BR-CUS-013), archiving retires a plan from new assignment without touching history — so that seven years of bills stay reproducible while the catalog evolves. Entry: S9 row actions (Edit/New version, Publish, Archive) reopening the S10 wizard pre-filled. Exit: updated plan, `rate_change_log` entries, toast. Category targeting edits (customer class) follow the same versioned path.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-RAT-017 | Tariff/plan configuration stays reproducible for 7 years (rebill/audit). | CONFIRMED — PO Q&A R1 Q12 |
| BR-RAT-025 | D9: versioned rate changes with history/audit/compliance log. | CONFIRMED — PO Q&A R3 |
| BR-RAT-030 | *(shared)* lifecycle; archived plans keep serving already-assigned accounts until an explicit change. | CONFIRMED — PO R5-4 |
| BR-RAT-037 | A plan/tariff version that has been billed against is never edited in place: every content change = `plans.version` +1 with a `rate_change_log` before/after row (reason required); existing `unit_plan_assignments.plan_version` snapshots are untouched. | CONFIRMED — PO R5-9 (B2 r5 #13/#14 + BR-CUS-013 + BR-RAT-007/017) |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Dana edits Residential Standard: adds Sewer service (schedule Sewer · % of water, base 8.00), reason "council resolution 2026-41" | `plans.version` 3 → 4; new plan_services/plan_rate_schedules rows; `rate_change_log` row with before/after jsonb + reason + actor; existing 842 assignments still show plan_version 3 |
| TC-2 | Account A-00412 later re-assigned (customers flow) | New `unit_plan_assignments` row snapshots plan_version 4; append-only history intact (r5 #13) |
| TC-3 | Dana archives Vacant / Standby (0 accounts) | status archived; gone from assignment pickers; still listed under filter Archived |
| TC-4 | Dana publishes a draft | status draft → published; audit row `plan.published` |
| TC-5 *(negative)* | Edit save attempted with the reason field blank | Blocked: "reason is required for every rate change" (r5 #14 reason NOT NULL); no version bump, no log row |
| TC-6 *(negative)* | Direct UPDATE of a `rate_change_log` row (API/db) | Rejected — append-only compliance trail (r5 #14) |
| TC-7 *(isolation)* | Lone Star Ridge admin lists version history | Sees only Lone Star Ridge `rate_change_log` rows; Brazos Bend's plan history never appears |

**4 · Test Data** — Residential Standard v3 → v4 per TC-1 (Sewer added Sep 1, 2026, reason "council resolution 2026-41"). Archive target: Vacant / Standby (draft, 0 accounts). Account A-00412 (Miller, Sarah) on plan_version 3. Actors: Dana Whitfield; isolation J. Okafor (Lone Star Ridge).

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Plan version | S9/S10 | B2 r5 #18 | `plans.version` (int DEFAULT 1) | integer | system-derived | +1 per content change |
| Version snapshot on assignment | — | B2 r5 #13 | `unit_plan_assignments.plan_version` (append-only; ⚠ cross-module, ledger reads) | integer | system-derived | never mutated |
| Change reason | edit flow | B2 r5 #14 | `rate_change_log.reason` (NOT NULL) | text | user-input | required — compliance |
| Before/after | edit flow | B2 r5 #14 | `rate_change_log.entity` + before/after jsonb + actor | jsonb | system-derived | append-only |
| Status transitions | S9 | prototype pills + r5 #18 | `plans.status` | enum | user-input (gated) | draft→published→archived only |
| Audit | — | CLAUDE.md #7 | `audit_log` (`plan.published` / `plan.archived` / `plan.version_created`) | jsonb | system-derived | append-only |

**6 · Acceptance**
- Given a published plan, When edited with a reason, Then version increments, the log captures before/after/actor/reason, and no existing assignment snapshot changes.
- Given a blank reason or a log-row mutation, Then the operation is rejected outright.
- Given 7-year-old versions, Then plan content as of any past date is reconstructable from `rate_change_log` + `tariff_versions` (BR-RAT-017).

**7 · Finance Calculation** — N/A (no amounts computed; versioning only).

**8 · Open Questions** — None.
