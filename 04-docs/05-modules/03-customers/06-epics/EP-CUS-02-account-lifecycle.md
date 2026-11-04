# EP-CUS-02 — Account lifecycle (new account · move-in · move-out)
> Reconciled 2026-08-08 against PO rulings (BR-CUS-046..059) — propagation sweep.

**Module:** customers (product name: Accounts) · **Wave:** W2 · **Screens:** S18, S19, S20 · **Status:** draft

## Scope
**In:** the three guided lifecycle wizards — S18 New Account (6 steps: Customer → Service address → Plan → Billing prefs → Deposit → Review), S19 Move-In (5 steps: Find unit → Customer → Start & read → Plan & deposit → Review), S20 Move-Out (4 steps: Find account → Date & final read → Final bill & deposit → Close-out) — plus the two cross-cutting mechanics they share: the account attribute snapshot written at assignment (BR-CUS-012/BR-CUS-014 sc.1, incl. solar/battery capacity units) and deposit application per the rate-plan deposit schedule (BR-RAT-020/023). Customer identity now creates or links a first-class `customers` entity (BR-CUS-054). Wizard mechanics (step rail, save-draft, resume) conform to EP-SHL-03.
**Out:** the final bill itself — a billing W3 run variant; US-CUS-005 defines only the handoff contract (BR-CUS-031) · rendering the welcome pack / agreements (notifications, A19/BR-NOT-004) · unit/premises creation (EP-MET-01) · plan content (EP-RAT-01/02) · payment-method tokenization and autopay EXECUTION (W7 rails — capture-only v1 per BR-CUS-059) · mid-tenancy plan changes (EP-CUS-05) · bulk brownfield onboarding (EP-CUS-07).

> **Schema note (Eng Lead, pre-migration):** B2 `service_agreements.tariff_id` predates the r5/r6 plan model and BR-CUS-014. Under BR-CUS-014 sc.6 billing prices from the ACCOUNT plan snapshot, and the unit side lives in `unit_plan_assignments` — leaving `service_agreements.tariff_id` redundant/divergence-prone. Mapped below with `service_agreements` carrying only the account↔service_point linkage; the tariff_id disposition (drop vs keep-synced) is flagged for Eng Lead review, not resolved here. The account-side snapshot itself has no B2 home → PROPOSED-SCHEMA `account_plan_assignments` (BR-CUS-029). Same discipline applies to `contacts` re-homing under the BR-CUS-054 `customers` entity (Lane C batch #3): flagged for Eng Lead, not decided in stories.  ⚠ **`account_plan_assignments` is SUPERSEDED (PO 2026-08-11)** — no account-side plan table is built; the plan lives once on `units.rate_plan_id` and the account derives it. See BR-CUS-029.

## Capability matrix (list screens only — B9 conformance)
No list screens — S18/S19/S20 are guided full pages (README: creation/large flows are full pages). In-wizard pickers (unit table, customer results, account results) are modal-scoped result sets, not B9 lists.

## Stories

---
id: US-CUS-003
epic: EP-CUS-02
module: customers
screens: [S18]
wave: 2
status: draft
blocked_by: []
depends_on: [US-MET-003, US-RAT-002, US-TEN-012, US-SHL-010]
journeys: [J2]
rules: [BR-CUS-010, BR-CUS-012, BR-CUS-014, BR-CUS-017, BR-CUS-018, BR-CUS-019, BR-CUS-020, BR-CUS-021, BR-CUS-022, BR-CUS-023, BR-CUS-028, BR-CUS-045, BR-CUS-054, BR-CUS-058, BR-CUS-059, BR-CUS-060]
golden_tests: [GT-3]
finance_calc: confirmed
---
### US-CUS-003 — New Account wizard (S18, six steps)

**1 · Details** — As a Billing Clerk, I want a six-step guided page — 1 Customer identity (type Individual/Business/Government, name, DOB, ID type/number, phone, email, mailing address, automatic duplicate check that CREATES OR LINKS a first-class customer entity per BR-CUS-054) → 2 Service address (premises + unit picker showing only vacant/reserved units, services available at the unit with their meters, service start date, initial read source) → 3 Plan (unit default plan pre-filled and its inherited services/schedules/bases DISPLAYED; override allowed) → 4 Billing & communication preferences (autopay is CAPTURE-ONLY per BR-CUS-059; the prototype's "Bill delivery day" selector is NOT BUILT — dropped per BR-CUS-060) → 5 Deposit & credit (plan deposit rule read-only; credit tier shown as a COMPUTED display per BR-CUS-058; collect-now / add-to-first-bill / waive-with-reason) → 6 Review & create — so that a first-time customer becomes a billable account in one pass. Entry: S17 **+ New account**. Exit: **Create account ✓** → account created (status per BR-CUS-018), snapshot written (US-CUS-006), deposit handled (US-CUS-007), toast → S21; **Save draft & exit** → resumable draft. Step-3 override behavior is BR-CUS-014 sc.2: the chosen plan writes back to the unit + a `unit_plan_assignments` history row (source `new_connection`) — unit and account never diverge (BR-CUS-010). J2 step 4 handoff: account active, plan version snapshot saved, deposit rule applied.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-CUS-010 / BR-CUS-014 sc.2 | Plan override at account creation updates the unit's plan assignment + history row; unit and account never diverge. | CONFIRMED — PO Q&A R1 (D10) + PO PU-9 scenarios |
| BR-CUS-012 | The wizard captures the confirmed account attribute set (type, sub-type, plan version snapshot, deposit, tax-exempt, autopay, credit tier — now computed per BR-CUS-058, billing cycle, payment method, portal access, service address, status, since-date, solar/battery capacity units). | CONFIRMED — PO Q&A R1 (D10 + Q10); storage per US-CUS-006 |
| BR-MET-040 | Plan is REQUIRED at account activation; a unit without a plan blocks with a message. | CONFIRMED — PO PU-10 |
| BR-CUS-017 | *(shared)* one active account per unit; the picker cannot select an occupied unit. | PROPOSED |
| BR-CUS-018 | S18 is a six-step guided page with Save-draft/resume (EP-SHL-03); a draft account is status `pending`, is never billed, never derives occupancy, and does not block the unit for other move-ins. | PROPOSED — prototype S18 + A5 (Pending activation per BR-CUS-055) + BR-MET-036 |
| BR-CUS-019 | Step 1 runs an advisory duplicate check (match on name+DOB, ID last-4, email, phone against existing customer records); staff decides — no hard block. A match resolves by LINKING the new account to the existing `customers` row (BR-CUS-054), never by copy-on-create. | PROPOSED (advisory behavior — prototype "We'll check for duplicates automatically") / linkage CONFIRMED — BR-CUS-054 |
| BR-CUS-054 | Customer is a first-class entity: step 1 creates a `customers` row (or links an existing one); one edit updates every linked account; PROPOSED-SCHEMA `customers` + `customer_accounts` (Lane C batch #3). | CONFIRMED — PO OQ-057 (b) |
| BR-CUS-020 | Unit pickers in S18/S19 offer only vacant or reserved units; occupied units never appear. | PROPOSED — prototype step-2/step-1 copy ("Only vacant or reserved units are available") |
| BR-CUS-021 | An initial read per active meter is captured (source AMI-pull / manual / estimate-from-prior-3) through the metering commit path (append-only, BR-MET-017); it is the register from which billing picks up. | PROPOSED — prototype S18 step 2 / S19 step 3 + BR-MET-017  ⚠ **THE PREFILL IS THE BOX'S OPENING VALUE — PO ruling 2026-08-27, verbatim *"(a) Box opens with 42,864 in it"* (`OQ-394` CLOSED).** The CR-038 W9 lane's empty-box divergence is reversed and the reading's DATE rides with the number on the control. See BR-CUS-021 in `../02-business-rules.md` for the cost the PO ruled with in front of them. |
| BR-CUS-022 | First bill starts at the service start date, prorated to cycle end by calendar days, base + usage (B4.3); alternative "next cycle start" per S19. | CONFIRMED (proration rule — B4.3, GT-3) / option set PROPOSED (prototype) |
| BR-CUS-023 | Deposit amount = `plan_deposit_rules[account_type]` fixed $ (no formula); handling options collect-now / add-to-first-bill / waive-with-reason-code. | CONFIRMED (amount rule — BR-RAT-020/023) / handling options PROPOSED (prototype step 5) |
| BR-CUS-058 | Credit tier is COMPUTED from payment history (seeded default rule: 12-mo window — 0 lates = A, 1–2 = B, 3+ = C; parameters tenant-configurable; informational display). Step 5's "Credit check result" renders the computed tier, never a manual entry; a brand-new customer shows "No payment history" plus the seeded-rule outcome (0 lates → A) — display copy PROPOSED. | CONFIRMED (computed, in V1) — PO OQ-062 (b); new-customer display copy PROPOSED — derivation |
| BR-CUS-028 / BR-CUS-059 / BR-CUS-060 | Step-4 preferences: paperless, autopay enrollment (CAPTURE-ONLY v1 — stored + displayed; execution begins at W7 rails, no re-enrollment), budget billing (selects a budget-flagged plan per BR-RAT-043), SMS reminders, statement language (English-only v1 per IS-8 — Español renders disabled). "Bill delivery day" is DROPPED (BR-CUS-060): cycles decide bill dates; "bill me on the 15th" = cycle assignment. | CONFIRMED (autopay capture-only + delivery-day drop) — PO OQ-059 final / capture set PROPOSED (prototype) |
| BR-CUS-045 | Contact PII (email, DOB, ID last-4) stores per B2 contacts columns; gov ID tokenized (B2 note), high-sensitivity columns app-layer encrypted per the OQ-016 closure. | PROPOSED — B2 §customers + OQ-016 closure |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Marcus creates Elena Rivera (Individual, DL ****4218, +1 281 555-0100, elena.rivera@example.com) on P-11800 / Unit A, start Aug 15 2026, keeps unit default RES-STD, paperless+SMS on, deposit collect-now | Account A-12048 created active; NEW `customers` row + `customer_accounts` link (BR-CUS-054) + contacts + addresses rows; `service_agreements` rows for E+W started Aug 15; snapshot + deposit per US-CUS-006/007; initial reads committed (E 40,120 / W 128,400); audit `account.created`; toast → S21 |
| TC-2 | Step 3 displays inheritance | Unit default plan pre-selected ("Residential Standard · $30.50/mo base (unit default)"); "What they'll be billed for" table shows the inherited schedules + bases from the plan (Res Electric · Tiered $18.50 / Res Water · Inclining $12.00); unit's assets (M-5001, W-5001) shown in step 2 — display-only, no re-attachment |
| TC-3 | Marcus overrides step 3 to Senior / Low-income | Review shows Senior; on create, `unit_plan_assignments` gains a row (Senior, source `new_connection`, actor Marcus, prior RES-STD row closed) — BR-CUS-014 sc.2; account snapshot = Senior current version |
| TC-4 | Save draft & exit at step 4; reopen | Draft resumes at step 4 (EP-SHL-03); account status Pending activation; unit still offered to other move-ins (BR-CUS-018) |
| TC-5 | Step 1 duplicate check: name+phone matching Nguyen, Thao | Advisory match panel lists the candidate; **Use existing customer** links the new account to Thao's `customers` row via `customer_accounts` (BR-CUS-054 — a later contact edit updates all her accounts); **Create new** makes a separate customer; Marcus decides (BR-CUS-019) |
| TC-6 *(negative)* | Unit U-11602-103 has no default plan and Marcus skips step-3 selection | Create blocked with message "plan required at activation" (BR-MET-040); nothing written |
| TC-7 *(negative)* | Service start date before today with initial read source "AMI · pull today's reading" | Inline error — a backdated start cannot use a today-pull read; source must be Manual/Estimate (BR-CUS-021) |
| TC-8 *(isolation)* | J. Okafor runs S18 | Premises/unit/plan pickers list only Lone Star Ridge rows; created rows carry Lone Star Ridge tenant_id; duplicate check never matches Brazos Bend customers |

**4 · Test Data** — Tenant Brazos Bend Utilities. New customer **Elena Rivera** (Individual, DOB 03/18/1991, DL ****4218, +1 (281) 555-0100, elena.rivera@example.com, mailing = service). Unit: P-11800 · 1408 Elm Street · **Unit A** (vacant, E meter M-5001 + W meter W-5001, default plan RES-STD v3). Plans per EP-RAT-01 seed (RES-STD $30.50 = 18.50 E + 12.00 W; Senior / Low-income $12.00). Deposit schedule: residential $150.00 / commercial $300.00 / industrial $500.00 / government $0.00. Account number allocated from the tenancy account series → **A-12048**. Start date Aug 15, 2026 (cycle 08-B, 31-day month). Duplicate fixture: existing customer Thao Nguyen (one linked account). Actors: Marcus Vega; isolation J. Okafor.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Customer type | S18 step 1 | prototype-extracted (Individual/Business/Government) | `accounts.account_type_id` → `account_types` (r5 #12/#19; Government is a seeded type) + **PROPOSED-SCHEMA** `customers.kind` (BR-CUS-054) | uuid/enum | user-input | platform-seeded set |
| Full name / DOB / phone / email | S18 step 1 | prototype-extracted | **PROPOSED-SCHEMA** `customers` (display_name) + `contacts` rows (`.full_name`/`.dob`/`.phone`/`.email`, is_primary=true) — contacts re-home to the customer entity so one edit updates all linked accounts (BR-CUS-054; Eng Lead disposition per epic schema note) | text/date | user-input | email format; PII per BR-CUS-045 |
| ID type + number | S18 step 1 | prototype-extracted (DL/State ID/Passport/SSN-4/EIN) | `contacts.gov_id_last4` (tokenized) + **PROPOSED-SCHEMA** `contacts.gov_id_type` | text | user-input | last-4 only stored |
| Mailing address | S18 step 1 | prototype-extracted ("Same as service") | `addresses` (kind mailing; omitted = same-as-service) | text | user-input | — |
| Duplicate-check results | S18 step 1 | prototype-extracted (hint copy) | query over `customers` + `contacts` (BR-CUS-054 — the customer master IS the dedupe target; link via `customer_accounts`) | — | computed-display | advisory only (BR-CUS-019) |
| Premise + Unit picker | S18 step 2 | prototype-extracted | `accounts.unit_id` → `units` (⚠ cross-module FK, reviewed set B2 §2) | uuid | user-input | vacant/reserved only (BR-CUS-020) |
| Services at unit + meters | S18 step 2 | prototype-extracted (svc-dots with meter #s) | display from `asset_assignments`/unit services (⚠ metering/assets read) → creates `service_agreements` rows on create | reference | computed-display → system-derived | one SA row per active service |
| Service start date | S18 step 2 | prototype-extracted | `accounts.opened_at` + `service_agreements.started_on` | date | user-input | BR-CUS-022 |
| Initial read + source | S18 step 2 / review | prototype-extracted (AMI/Manual/Estimate) | `meter_reads` via metering service (⚠ B1 — customers never writes metering tables) | numeric + enum | user-input / integration | BR-CUS-021; append-only |
| Plan (default + override) | S18 step 3 | prototype-extracted ("(unit default)") | account snapshot (**PROPOSED-SCHEMA** `account_plan_assignments`, US-CUS-006) + writeback `unit_plan_assignments` (r5 #13, source new_connection) | uuid + int | user-input | published plans only (BR-RAT-030); BR-CUS-014 sc.2 |  ⚠ **`account_plan_assignments` is SUPERSEDED (PO 2026-08-11)** — no account-side plan table is built; the plan lives once on `units.rate_plan_id` and the account derives it. See BR-CUS-029.
| "What they'll be billed for" table | S18 step 3 | prototype-extracted | display from `plan_services` + `plan_rate_schedules` (⚠ rating read) | reference | computed-display | — |
| Paperless / SMS reminders / autopay / budget billing | S18 step 4 | prototype-extracted (4 checkboxes) | `accounts.autopay` (B2) + **PROPOSED-SCHEMA** `accounts.paperless`, `accounts.sms_reminders`, `accounts.budget_billing` | boolean | user-input | autopay CAPTURE-ONLY v1 (BR-CUS-059); budget per BR-RAT-043 |
| Statement language | S18 step 4 | prototype-extracted (English/Español) | **PROPOSED-SCHEMA** `accounts.statement_language` | text | user-input | English-only v1 (IS-8); Español disabled |
| ~~Bill delivery day~~ | S18 step 4 | prototype-extracted (Default/Day 8/Day 15) | **DROPPED (BR-CUS-060)** — selector not built; cycles decide bill dates (BR-MET-009); "bill me on the 15th" = cycle assignment | — | — | — |
| Deposit rule (read-only) + handling + waive reason | S18 step 5 | prototype-extracted + BR-RAT-020/023 | `rate_plans`→`plan_deposit_rules[account_type]` (r5 #8) → `accounts.deposit_on_file` per US-CUS-007 | numeric(18,6) | reference-data / user-input | BR-CUS-023; reason required when waived |
| Credit check result / tier | S18 step 5 | prototype-extracted ("Passed · standard tier") | `accounts.credit_tier` — COMPUTED per BR-CUS-058 (cached; rule params **PROPOSED-SCHEMA** `credit_tier_rules`, Lane C batch #3); NOT an input field | text | computed-display | seeded rule 12-mo/0/1–2/3+; informational |
| New account # | S18 step 6 | prototype-extracted ("A-12048") | `accounts.account_no` from tenancy `number_series` (BR-TEN-035) | text | system-derived | unique per tenant |
| Create / Save as draft | S18 step 6 | prototype-extracted | `accounts.status` (Pending activation → Active on create per BR-CUS-018) + `audit_log` | lookup | system-derived | vocabulary per BR-CUS-055 |

**6 · Acceptance**
- Given a completed wizard, When Marcus creates, Then customer (new or linked) + account + contact + address + service agreements + snapshot + deposit + initial reads + audit rows exist atomically, the unit derives Occupied, And J2 step-4 handoff holds (account active, plan version snapshot saved, deposit rule applied).
- Given a plan override, Then the unit's assignment history gains the override row and unit = account plan.
- Given a duplicate match accepted, Then the account links to the EXISTING customer and no duplicate customer row exists.
- Given a unit with no plan and no selection, Then creation blocks with the BR-MET-040 message and writes nothing.

**7 · Finance Calculation** — Two CONFIRMED display references, no new math: deposit = `plan_deposit_rules[residential]` = **$150.00** fixed lookup (BR-RAT-020/023 — worked detail in US-CUS-007 §7); first-bill proration note = calendar days, base + usage (B4.3): start Aug 15 in a 31-day cycle → base fraction 17/31 × 30.50 = **$16.73** shown as "prorated first bill" guidance (billing computes the invoice). GT ref: GT-3 (rule confirmed).

**8 · Open Questions**
| OQ | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| OQ-057 | Customer-vs-account entity separation depth | Nothing — closed | Product Owner (chat session) | CLOSED(→BR-CUS-054) — option (b): first-class customer entity, N:M accounts; dedupe links, one edit updates all (PO) |
| OQ-059 | Step-4 preference execution in v1 (autopay drafting; bill-delivery-day semantics; budget-billing interaction) | Nothing — closed | Product Owner (chat session) | CLOSED(→BR-CUS-059/060) — autopay CAPTURE-ONLY v1 (execution W7, no re-enrollment); bill-delivery-day DROPPED (cycles decide bill dates); budget-billing per BR-RAT-043 (PO confirmed) |
| OQ-062 | Credit tier & credit check source/value set | Nothing — closed | Product Owner (chat session) | CLOSED(→BR-CUS-058) — option (b): COMPUTED from payment history, seeded 12-mo rule (0=A, 1–2=B, 3+=C), tenant-configurable, informational; in V1 (PO) |

---
id: US-CUS-004
epic: EP-CUS-02
module: customers
screens: [S19]
wave: 2
status: draft
blocked_by: []
depends_on: [US-MET-002, US-MET-010, US-RAT-002, US-CUS-003]
journeys: [J2]
rules: [BR-CUS-010, BR-CUS-014, BR-CUS-019, BR-CUS-020, BR-CUS-021, BR-CUS-022, BR-CUS-023, BR-CUS-024, BR-CUS-054, BR-CUS-056, BR-CUS-1101, BR-MET-044]
golden_tests: [GT-3]
finance_calc: confirmed
---
### US-CUS-004 — Move-In wizard (S19, seven steps)

⚠ **THE HEADING SAID *five steps* AND THE FLOW HAS NOT HAD FIVE SINCE
2026-09-12.** `CR-094-BRC01` wave H made it six (Account preferences + Deposit)
and `BR-CUS-1101` made it seven on 2026-09-25 (**Services**, at position 2).
`moveShared.MOVE_IN_STEPS` is the one declared list and the only thing to count;
the §1 prose below still describes the five-step shape and is amended only where
this lane's step touches it.

**1 · Details** — As a Billing Clerk, I want a five-step move-in — 1 Find unit (vacant/reserved search; row shows status, services, **default plan** prefilled from the last tenancy per BR-MET-044) → 2 Customer (search existing/returning CUSTOMERS — the BR-CUS-054 entity, with their prior/other accounts listed — or create new) → 3 Start & read (move-in date; Bill from = move-in date (prorate) / next cycle start; initial reads pre-filled from the prior occupant's final read; when chained from a same-day S20 move-out, start auto-sets to move-out day + 1 per BR-CUS-056) → 4 Plan & deposit (unit default pre-selected; override per BR-CUS-014 sc.2; deposit carry-forward from a prior account of the SAME customer via the `customer_accounts` linkage, collect new, or waive; billing prefs) → 5 Review & confirm — so that a vacant unit gets its next occupant in ~90 seconds. ⚠ **A step **2 · Services** sits between 1 and 2 since 2026-09-25 (`BR-CUS-1101`): *which of this unit's services does this account take*, pre-ticked with the unit's own service points, and the account is opened with one `service_agreements` row per service taken and none for the rest. **No page of the Accounts blueprint draws it** — its move-in pages (p072–p078) draw six steps and show *Services available* as a read-only panel saying *"Nothing on this panel is an input"* — so it is built to our UI standard (B14 rule 44) from the shared kit's tick-list (rule 43). Entry: S17 **Move-in** or S20 close-out chain ("Also schedule a move-in for the next tenant"). Exit: **Complete move-in ✓** → new account (new account #), unit derives Occupied, dunning state resets, toast → S21. This is J2 step 4: account active, plan version snapshot saved, deposit rule applied.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-CUS-014 sc.2 / BR-CUS-010 | Move-in plan override writes back to the unit + history row (source `move_in`); unit and account never diverge. | CONFIRMED — PO PU-9 sc.2 |
| BR-MET-044 | The unit KEEPS its last plan after move-out as the next-tenant prefill (changeable, no silent revert) — this is what step 1's "Default plan" column and step 4's pre-selection show. | CONFIRMED — PO PU-15 (= BR-CUS-014 sc.5) |
| BR-CUS-021 | Initial reads: prior final read pre-fills; entered value ≥ prior final for same register (else rollover/exception path per metering); committed via metering service. | PROPOSED — prototype step-3 hint + BR-MET-015/017  ⚠ **THE PREFILL IS THE BOX'S OPENING VALUE — PO ruling 2026-08-27, verbatim *"(a) Box opens with 42,864 in it"* (`OQ-394` CLOSED).** The CR-038 W9 lane's empty-box divergence is reversed and the reading's DATE rides with the number on the control. See BR-CUS-021 in `../02-business-rules.md` for the cost the PO ruled with in front of them. |
| BR-CUS-022 | Bill from = move-in date (prorate per B4.3/GT-3) or next cycle start. | CONFIRMED (proration) / options PROPOSED |
| BR-CUS-056 | Same-day turnover: the OUTGOING account pays the move day (billed through the move-day reading); the incoming account starts the NEXT day from the same reading — no gap, no double-bill. The chained flow enforces start = move-out day + 1. | CONFIRMED — PO OQ-060 (a) |
| BR-CUS-023 / BR-CUS-024 | Deposit = category-fixed from the plan's schedule; a returning customer's refundable deposit held on a prior account may carry forward instead of a new collection (S19 step 4); carry-forward linkage = same `customers` entity via `customer_accounts` (BR-CUS-054). | CONFIRMED (amount + linkage) / carry-forward mechanics PROPOSED |
| BR-CUS-054 | *(shared)* step-2 search resolves customers (entity), listing each match's linked accounts; "returning customer" = existing `customers` row gaining a new `customer_accounts` link. | CONFIRMED — PO OQ-057 (b) |
| BR-CUS-019 | *(shared)* customer search/dedupe advisory. | PROPOSED (advisory) / linkage CONFIRMED — BR-CUS-054 |
| BR-CUS-020 | *(shared)* vacant/reserved units only. | PROPOSED |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Marcus moves Thomas Nguyen (returning customer, prior A-11208 closed Jul 2025) into U-10432-B, move-in Aug 15 2026, bill from move-in date, keeps unit default RES-STD, carries the $150 deposit forward | New account **A-12049** active, LINKED to Thomas's existing `customers` row (BR-CUS-054); snapshot RES-STD v3; `unit_plan_assignments` untouched (no override); deposit_on_file 150.00 carried from A-11208 via the customer linkage (US-CUS-007); initial reads E 88,412 / W 132,180 committed; unit Occupied (derived); audit `account.created` + `deposit.carried` |
| TC-2 | Step 1 lists vacant units | U-10432-B row shows Vacant, tags E+W, Default plan "Residential Standard" (BR-MET-044 prefill); occupied units absent |
| TC-3 | Step 4 override to Residential Electric-only | Warning that Water service has no schedule on that plan (plan-services mismatch surfaced); on confirm, `unit_plan_assignments` gains override row (source `move_in`) — BR-CUS-014 sc.2 |
| TC-4 | Bill from = "Next cycle start" | No proration note; snapshot effective from cycle start; J2 handoff records the billing start date |
| TC-5 *(negative)* | Initial read entered as 88,000 (< prior final 88,410) on the same register | Inline error → routes to the metering negative-read exception path (BR-MET-015); commit blocked until resolved |
| TC-6 *(negative)* | Move-in attempted on U-10432-A (occupied by A-10432); separately, a chained same-day move-in whose start date is edited back to the move-out day | Unit not offered / forged submit rejected by BR-CUS-017 one-active-per-unit; the backdated chained start blocks — the outgoing account owns the move day (BR-CUS-056) |
| TC-7 *(isolation)* | J. Okafor's step-2 customer search for "Nguyen" | Zero results — customer search scopes to Lone Star Ridge (RLS) |
| TC-8 | **`BR-CUS-1101` — the PO's own scenario.** The premises offers six services, the unit has six service points, five carry a meter or an asset; on the new **step 2 · Services** Marcus unticks gas, sewer and broadband and leaves electric, water and trash | The account is opened with **exactly three** `service_agreements` rows, and **no row of any kind — open or closed — exists for gas, sewer or broadband**. S17/S21 show three service chips. ⛔ Both halves are asserted: *three exist* was true before this rule too, and only *the other three were not created* can tell the two apart |
| TC-9 *(negative)* | The clerk's browser sends `services: ["electric","solar"]` for a unit with no solar point; separately, `services: []` | Refused **naming `solar`**, with the unit's own offer beside it (`customers.move_in.service_not_at_unit`); the empty list refused as `customers.move_in.services_required`. Nothing is written either time — BR-SHL-019, the refusal is the whole act. **A clerk cannot buy a connection that does not exist** |
| TC-10 | Step 2 is left exactly as it opens — every service pre-ticked — and, separately, the clerk unticks every one and presses **Continue** | The payload omits `services` entirely (absent = all of them, which is what *I changed nothing* means) and the account takes all six. With nothing ticked, Continue **blocks and says why** at the button — *"Tick at least one service."* — rather than doing nothing, which is the shape three defects have already been filed under on these wizards |
| TC-11 | An account that took three of six moves out, while a neighbouring account at another unit holds six | The three are closed on the move-out day, `started_on` untouched, rows never deleted (hard rule 4); **the neighbour's six are untouched** — the half that fails if the close ever stops being scoped to the account |

**4 · Test Data** — Unit **U-10432-B** (1408 Elm St · Unit B, vacant, E M-4023 prior final 88,410 / W M-4024 prior final 132,180, last plan RES-STD v3). Returning customer **Thomas Nguyen** (thomas.nguyen@example.com, existing `customers` row; prior account A-11208 closed Jul 2025, deposit $150.00 held-refundable). Move-in Aug 15, 2026 · cycle 08-B (31 days). Same-day chain fixture per US-CUS-005 TC-8 (move-out Aug 14 → chained start Aug 15). Actors: Marcus Vega; isolation J. Okafor.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Unit search + row (status/services/default plan) | S19 step 1 | prototype-extracted | `units` + `unit_plan_assignments` current row (⚠ metering read) | reference | computed-display | vacant/reserved only |
| Customer search + prior accounts | S19 step 2 | prototype-extracted | `customers` + `customer_accounts` (+ their closed `accounts`) — BR-CUS-054 entity (PROPOSED-SCHEMA, Lane C batch #3) | text | computed-display | advisory (BR-CUS-019) |
| New-customer quick fields | S19 step 2 | prototype-extracted (name/phone/email) | `customers` row + `contacts` row (BR-CUS-054) | text | user-input | subset of S18 step 1; rest editable later |
| Move-in date + Bill from | S19 step 3 | prototype-extracted | `accounts.opened_at` / `service_agreements.started_on` + billing-start instruction | date + enum | user-input | BR-CUS-022; chained same-day ⇒ start = move-out day + 1 (BR-CUS-056) |
| Initial reads table (prior final / initial / source) | S19 step 3 | prototype-extracted | `meter_reads` via metering service (⚠ B1) | numeric + enum | user-input / integration | BR-CUS-021; same-day chain reuses the move-out reading (BR-CUS-056) |
| Plan (prefill + override) | S19 step 4 | prototype-extracted ("(unit default)") | snapshot (US-CUS-006) + `unit_plan_assignments` writeback (source move_in) | uuid + int | user-input | BR-CUS-014 sc.2; published only |
| Deposit disposition (carry / collect / waive) | S19 step 4 | prototype-extracted (3 radios) | `accounts.deposit_on_file` + carry-forward via `customer_accounts` linkage (BR-CUS-054) per US-CUS-007 | numeric(18,6) | user-input | BR-CUS-023/024; carry ⇒ same customer entity |
| Billing prefs (paperless/autopay) | S19 step 4 | prototype-extracted | as US-CUS-003 step-4 mapping | boolean | user-input | autopay capture-only (BR-CUS-059) |
| Review + new account # | S19 step 5 | prototype-extracted ("A-12049") | `accounts` row; number from tenancy series | — | system-derived | — |

**6 · Acceptance**
- Given a vacant unit and a returning customer, When Marcus completes move-in, Then a NEW account exists (fresh number) linked to the SAME customer entity, the plan snapshot equals the unit plan (or the override synced both ways), initial reads are committed, the deposit is carried per election, And the unit derives Occupied.
- Given an initial read below the prior final, Then commit blocks into the metering exception path.
- Given a same-day chain, Then the incoming start is the day after move-out and cannot be backdated onto the move day.
- Given J2, Then step-5 handoff fields (account active, snapshot, deposit) are all present for the read-import step.

**7 · Finance Calculation** — First-bill proration per **GT-3 (CONFIRMED, B4.3)**: calendar days, base + usage both prorated. Worked example (§4): move-in Aug 15 of a 31-day cycle → 17 remaining days incl. start; base 17/31 × 30.50 = 16.7258… → **$16.73** (2dp half-up at finalization, B4.4); usage prorated on the same day basis by the engine (EP-RAT-05). Deposit: fixed **$150.00** carry-forward — no differential math at move-in. GT ref: GT-3.

**8 · Open Questions**
| OQ | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| OQ-057 | *(shared with US-CUS-003)* returning-customer search + deposit carry-forward linkage | Nothing — closed | Product Owner (chat session) | CLOSED(→BR-CUS-054) — customer entity; carry rides `customer_accounts` (PO) |
| OQ-060 | *(shared with US-CUS-005)* same-day move-out/move-in boundary-day ownership | Nothing — closed | Product Owner (chat session) | CLOSED(→BR-CUS-056) — option (a): outgoing pays the move day; incoming starts next day from the same reading (PO) |

---
id: US-CUS-005
epic: EP-CUS-02
module: customers
screens: [S20]
wave: 2
status: draft
blocked_by: []
depends_on: [US-CUS-004, US-CUS-007, US-MET-010]
journeys: [J2]
rules: [BR-CUS-014, BR-CUS-025, BR-CUS-030, BR-CUS-031, BR-CUS-056, BR-CUS-057, BR-MET-036, BR-MET-044, BR-BIL-004]
golden_tests: [GT-3]
finance_calc: confirmed
---
### US-CUS-005 — Move-Out wizard (S20, four steps) & final-bill handoff

**1 · Details** — As a Billing Clerk, I want a four-step move-out — 1 Find account → 2 Date & final read (move-out date, reason, final reads per meter with Δ usage) → 3 Final bill & deposit (prorated final-bill PREVIEW; deposit disposition: apply to final bill first, remainder refund via ACH / mailed check / carry to new account) → 4 Close-out (send final statement, deposit disposition letter, return unit to Vacant, stop dunning, optional chained move-in) — so that an account closes cleanly and the unit is free for the next tenant. **Move-day rule (BR-CUS-056):** the outgoing account PAYS THE MOVE DAY — the final bill runs through the move-day reading, and a chained move-in starts the next day from that same reading (no gap, no double-bill). Entry: S17 **Move-out** or S21 header action. Exit: **Complete move-out ✓** → account closed, toast → S21; **Complete & start move-in →** chains into S19 with start = move-out day + 1. **Boundary:** this story records the final-bill INTENT and its inputs; the final bill itself is produced by billing (W3) from the handoff contract (BR-CUS-031) — customers never writes invoices (CLAUDE.md module map, B1).

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-CUS-014 sc.5 / BR-MET-044 | On move-out the unit KEEPS its last plan as the next-tenant prefill; no assignment row is closed retroactively, the account snapshot history simply ends. | CONFIRMED — PO PU-9 sc.5 / PU-15 |
| BR-MET-036 | Unit flips to Vacant by derivation (active account closed) — never manually set. | CONFIRMED — PO PU-3 |
| BR-CUS-025 | Deposit settlement: held deposit + accrued interest (BR-CUS-057) is applied to ~~the final bill FIRST~~ **EVERYTHING OUTSTANDING at closure**; only the remainder refunds (per the step-3 hint). ⚠ **AMENDED PO 2026-08-12 (OQ-158, *"everything outstanding"*):** a customer leaving with a final bill AND an older arrear has the deposit applied against the **whole closing position** — applying it to the final bill alone would refund a customer who still owes money (worked: a **$120.84** arrear sits inside the settled base, so the product stops refunding **$90.14**). **This is also the ONLY moment the deposit moves** — a mid-plan differential does not exist (PO 2026-08-12, OQ-179 → BR-CUS-042/062). Refund executes via the payments `refunds` path (B2 r2) — customers records the instruction. The prototype's static sample (applied –$0.00 while $184.20 due) contradicts its own hint and is treated as mock data, not a rule. | PROPOSED (apply-first) — S20 step-3 hint + B2 r2 / interest component CONFIRMED — BR-CUS-057 |
| BR-CUS-057 | *(shared)* deposit interest: tenant-set simple annual rate (default 0%), monthly accrual from the original receipt date, pays out at refund/closure — the disposition's "Interest accrued" line is the BR-CUS-057 accrual (engine per US-CUS-023 §7), no longer a stub. | CONFIRMED — PO OQ-061 (b) |
| BR-CUS-030 | Move-out flow: final read committed via metering; `accounts.closed_at` = move-out date; status → Closed (BR-CUS-055); dunning/collections activity stops for the account; close-out checklist actions (statement, disposition letter) queue via notifications. | PROPOSED — prototype S20 step 4 |
| BR-CUS-031 | Final-bill handoff contract to billing (W3): {account_id, move-out date, committed final reads, plan snapshot as of service dates (BR-CUS-014 sc.6), prior balance, deposit disposition instruction incl. accrued interest, refund method}. Billing prorates per B4.3 THROUGH the move day (BR-CUS-056) and issues the immutable final invoice (BR-BIL-004). | PROPOSED — derived from S20 + B4.3 + module boundaries |
| BR-CUS-056 | Same-day move-out/move-in: outgoing pays the move day (billed through the move-day reading); incoming starts next day from the same reading — no gap, no double-bill. | CONFIRMED — PO OQ-060 (a); closes BR-CUS-032 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Marcus moves out A-10432 on Aug 14 2026 (reason "Tenant lease ended"), final reads E 43,148 / W 133,940, refund ACH | Final reads committed; account closed_at Aug 14, status Closed; unit U-10432-A derives Vacant; handoff record per BR-CUS-031 queued for billing (billed THROUGH Aug 14, BR-CUS-056); deposit instruction "apply-first, ACH remainder"; audit `account.closed` |
| TC-2 | Step 3 preview renders | Prorated lines match §7 (base E $8.35, base W $5.42, tax $4.83, total $184.20 with prior balance); labeled PREVIEW — no invoice row exists (BR-BIL-004; billing W3 issues it) |
| TC-3 | Step 4 chain "Complete & start move-in →" | Move-out commits, then S19 opens pre-scoped to U-10432-A with the final reads as prior-final prefill and start date locked to Aug 15 (move day + 1, BR-CUS-056) |
| TC-4 | Refund method "Carry to new account" | Instruction recorded; carry executes only into a new account of the SAME customer entity (BR-CUS-024 via `customer_accounts`, BR-CUS-054) |
| TC-5 *(negative)* | Final read E entered as 42,000 (< prior 42,864) | Blocked into the metering negative-read exception (BR-MET-015); wizard cannot complete until resolved |
| TC-6 *(negative)* | Move-out date before the last issued bill's period end | Blocked with message — issued bills are untouched (BR-BIL-004); corrections route via J6, not move-out backdating |
| TC-7 *(isolation)* | J. Okafor searches step 1 for "Miller" | Zero results (RLS); Lone Star Ridge accounts only |
| TC-8 | Same-day turnover: move-out Aug 14 chains a move-in for the same unit | Outgoing final bill includes Aug 14 (14/31 proration per §7); incoming account starts Aug 15 with initial read = final read 43,148 — the shared day bills exactly once (BR-CUS-056) |

**4 · Test Data** — Account **A-10432** (Miller, Sarah · U-10432-A · RES-STD v3 · prior balance $120.84 · deposit $150.00 + interest accrued $3.20 (BR-CUS-057 accrual at the tenant's configured rate) · autopay ACH Chase ••••4021). Move-out **Aug 14, 2026** (14 days of the 31-day Aug cycle — move day included per BR-CUS-056). Final reads: M-4021 E 43,148 (prior 42,864, Δ 284 kWh) · M-4022 W 133,940 (prior 132,120, Δ 1.82 kgal). Reasons list: Tenant lease ended / Owner sold property / Downgrade · hardship / Deceased / Other. Actors: Marcus Vega; isolation J. Okafor.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Account search | S20 step 1 | prototype-extracted (name/acct/meter/address) | `accounts` + `contacts` + asset # (⚠ assets read) | text | user-input | active accounts only |
| Move-out date | S20 step 2 | prototype-extracted | `accounts.closed_at` + `service_agreements.ended_on` | date | user-input | ≥ opened_at; chained move-in starts next day (BR-CUS-056) |
| Reason | S20 step 2 | prototype-extracted (5 options) | **BUILT 2026-09-20** `accounts.close_reason` — five FIXED codes with a CHECK, **not** the lookup/tenant-extensible shape this row proposed (PO ruling, option A; the reasoning is in the decision log and `OQ-CUS-12512` is whether it widens) | enum | user-input | required on the screen, optional at the door |
| Final reads + source | S20 step 2 | prototype-extracted | `meter_reads` via metering service (⚠ B1; append-only) | numeric + enum | user-input / integration | BR-MET-015/017; move-day reading owns the boundary (BR-CUS-056) |
| Final-bill preview lines | S20 step 3 | prototype-extracted | computed display from handoff inputs — **no invoice write** | numeric USD | computed-display | B4.3 through the move day; BR-BIL-004 |
| Deposit disposition (on file / interest / applied / refund) | S20 step 3 | prototype-extracted | `accounts.deposit_on_file` + `accounts.deposit_interest_accrued` (**PROPOSED-SCHEMA** column; accrual CONFIRMED per BR-CUS-057) + refund instruction → payments `refunds` (⚠ B1) | numeric(18,6) | computed-display / user-input | BR-CUS-025 |
| Refund method | S20 step 3 | prototype-extracted (ACH / check / carry) | refund instruction field on the handoff record | enum | user-input | carry ⇒ same customer entity (BR-CUS-054) |
| Close-out checklist | S20 step 4 | prototype-extracted (5 checkboxes) | notification queue instructions (⚠ notifications) + unit vacancy derivation (BR-MET-036) | boolean | user-input | dunning stop per BR-CUS-030 |

**6 · Acceptance**
- Given an active account, When move-out completes, Then the account is closed, the unit derives Vacant with its plan retained as prefill, the final reads are committed, And a complete BR-CUS-031 handoff record exists for billing — with no invoice row written by customers.
- Given the §4 fixture, Then the step-3 preview reproduces the §7 numbers exactly, including the move day.
- Given a same-day chain, Then the move day bills once to the outgoing account and the incoming account starts the next day from the same reading.
- Given a final read below prior, Then the wizard blocks into the metering exception path.

**7 · Finance Calculation** — Display-only preview; billing computes the invoice from the same CONFIRMED rule (B4.3: calendar days, base + usage prorated; move day owned by the outgoing account per BR-CUS-056; rounding B4.4 half-up 2dp per line). Worked example (§4, 14/31 days incl. the move day): base E = 14/31 × 18.50 = 8.3548… → **8.35**; base W = 14/31 × 12.00 = 5.4193… → **5.42**; usage E 284 kWh → **38.94**, W 1.82 kgal → **5.82** (engine-priced, prototype figures); tax 8.25% × (38.94+5.82+8.35+5.42 = 58.53) = 4.8287… → **4.83** (tax base = usage+base only, B4.2); + prior balance 120.84 → **total $184.20** ✓ prototype. Deposit settlement per BR-CUS-025: (150.00 + interest 3.20 per BR-CUS-057) applied first → remainder due 184.20 − 153.20 = **$31.00**, refund $0.00 (the prototype's "refund $153.20" sample contradicts its own apply-first hint — rule follows the hint; flagged in BR-CUS-025). GT ref: GT-3 (calendar-day rule; move-out mirror).

**8 · Open Questions**
| OQ | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| OQ-060 | Same-day move-out/move-in boundary-day + read ownership | Nothing — closed | Product Owner (chat session) | CLOSED(→BR-CUS-056) — option (a): outgoing pays the move day, billed through the move-day reading; incoming starts next day from the same reading (PO) |
| OQ-061 | *(shared with US-CUS-007/009)* deposit interest v1 scope, rate source, accrual method | Nothing — closed | Product Owner (chat session) | CLOSED(→BR-CUS-057) — option (b): tenant-set simple annual rate, default 0%, monthly accrual, payout at refund/closure; engine per US-CUS-023 §7 (PO) |

---
id: US-CUS-006
epic: EP-CUS-02
module: customers
screens: [S18, S19, S21]
wave: 2
status: draft
blocked_by: []
depends_on: [US-RAT-003, US-CUS-003]
journeys: [J2]
rules: [BR-CUS-011, BR-CUS-012, BR-CUS-013, BR-CUS-014, BR-CUS-029, BR-CUS-055, BR-CUS-058]
golden_tests: []
finance_calc: none
---
### US-CUS-006 — Account attribute snapshot at assignment (incl. solar/battery capacity units)

**1 · Details** — As the system (on behalf of billing, audit and compliance), I want every account creation/move-in/plan-change to write the account's OWN attribute snapshot — plan + version, account type/sub-type, deposit held, tax-exempt, autopay, credit tier (now a COMPUTED cache per BR-CUS-058, never a captured input), billing cycle, payment method ref, portal access flag, service address, status, since-date, and solar/battery **capacity units** — so that billing prices from the account's snapshot as of service date (BR-CUS-014 sc.6) and the snapshot never silently drifts when the catalog changes (BR-CUS-013). Capacity units are captured per service (solar/battery) effective-dated in `account_capacities` (B2 r5 #5); EP-RAT-06 reads them for capacity charges — this story owns the capture UI on S18/S21 and the write path. No screen of its own beyond the wizard fields + S21 edit affordances.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-CUS-012 | The attribute set (verbatim list above) is the confirmed account model. | CONFIRMED — PO Q&A R1 (D10 + Q10) |
| BR-CUS-013 | Plan snapshot at assignment: later plan edits create a new version; the account keeps its assigned version until an explicit change. | CONFIRMED — D10 confirmation |
| BR-CUS-014 sc.1/sc.6 | At assignment the account saves its own snapshot (plan+version, category, deposit, autopay, tax-exempt); billing prices from the account's plan snapshot as of service date; unit + account histories feed audit, compliance and by-premises ledger. | CONFIRMED — PO PU-9 scenarios 1 & 6 |
| BR-CUS-011 | Assignment history keeps who/when/from→to/reason/source. | CONFIRMED — PO Q&A R1 (D10) |
| BR-CUS-058 | `accounts.credit_tier` is a COMPUTED cache refreshed from payment history by the seeded rule (12-mo window; 0=A, 1–2=B, 3+=C; params tenant-configurable via **PROPOSED-SCHEMA** `credit_tier_rules`); it is NOT part of the user-entered snapshot and has no edit affordance. | CONFIRMED (computed, in V1) — PO OQ-062 (b) |
| BR-CUS-055 | Status stores against the seeded, tenant-extensible account-status lookup (Pending activation · Active · Marked disconnect · Vacation hold/Suspended · Closed). | CONFIRMED — PO OQ-058 (b) |
| BR-CUS-029 | Storage: the account-side snapshot is an APPEND-ONLY `account_plan_assignments` table (account, rate_plan_id, plan_version, assigned_from/to, source new_connection\|move_in\|change_plan, actor, reason) mirroring `unit_plan_assignments` — B2 has no account-plan column today; `service_agreements.tariff_id` is superseded (epic schema note). Scalar attributes snapshot onto `accounts` columns; capacity units effective-date in `account_capacities`. | PROPOSED-SCHEMA — derived from BR-CUS-014 sc.1/6 + BR-CUS-011 + B2 r5 #5/#13 |  ⚠ **`account_plan_assignments` is SUPERSEDED (PO 2026-08-11)** — no account-side plan table is built; the plan lives once on `units.rate_plan_id` and the account derives it. See BR-CUS-029.

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | A-12048 created on RES-STD (current version 3) | `account_plan_assignments` row {RES-STD, v3, from Aug 15, source new_connection, actor Marcus}; accounts columns populated per BR-CUS-012; `credit_tier` populated by the BR-CUS-058 computation, not from any wizard field |  ⚠ **`account_plan_assignments` is SUPERSEDED (PO 2026-08-11)** — no account-side plan table is built; the plan lives once on `units.rate_plan_id` and the account derives it. See BR-CUS-029.
| TC-2 | Dana later publishes RES-STD v4 (rating flow) | A-12048's snapshot row still v3 (BR-CUS-013); billing for Aug prices v3 (BR-CUS-014 sc.6) |
| TC-3 | Solar account A-12050 created with solar 4 units + battery 2 units | Two `account_capacities` rows (service solar units 4.000000; battery 2.000000, effective_from = start date); EP-RAT-06 reads them via service function |
| TC-4 | Capacity units edited on S21 effective Sep 1 | Old row effective_to Aug 31, new row from Sep 1 — effective-dated, never overwritten |
| TC-5 *(negative)* | Direct UPDATE on an `account_plan_assignments` row; separately, an API attempt to SET `credit_tier` | Assignment update rejected — append-only (BR-CUS-029, mirrors r5 #13); the tier write rejected — computed field, no input path (BR-CUS-058) |  ⚠ **`account_plan_assignments` is SUPERSEDED (PO 2026-08-11)** — no account-side plan table is built; the plan lives once on `units.rate_plan_id` and the account derives it. See BR-CUS-029.
| TC-6 *(negative)* | Capacity units entered as −2 | Inline error: units ≥ 0 (B2 r5 #5) |
| TC-7 *(isolation)* | Lone Star Ridge session queries snapshots | Only Lone Star Ridge assignment rows visible (RLS on the new table — FORCE per B2 §3) |

**4 · Test Data** — A-12048 (Elena Rivera, RES-STD v3, Aug 15 2026). Solar fixture: **A-12050** Whitaker, Joan · Solar Residential (RES-SOL) · solar 4 units @ tenant unit-label "panel-kW" · battery 2 units (matches the GT-15 fixture: $10/$12 rates → $40.00 + $24.00 lines, priced by EP-RAT-06 not here). Version bump: RES-STD v3 → v4 Sep 2026 (rating US-RAT-003 fixture).

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Plan + version snapshot | S18/S19 (write), S21 header (read) | BR-CUS-012/013/014 | **PROPOSED-SCHEMA** `account_plan_assignments` (append-only; fields per BR-CUS-029) | uuid + int | system-derived | source enum; never mutated |  ⚠ **`account_plan_assignments` is SUPERSEDED (PO 2026-08-11)** — no account-side plan table is built; the plan lives once on `units.rate_plan_id` and the account derives it. See BR-CUS-029.
| Account type / sub-type | S18 step 1 | B2 r5 #12/#19 | `accounts.account_type_id` / `.account_subtype_id` | uuid | user-input | subtype tenant-defined |
| Deposit held | S18 step 5 | BR-CUS-012 | `accounts.deposit_on_file` | numeric(18,6) | system-derived | per US-CUS-007 |
| Tax-exempt (+ref/expiry) | S21 edit | B4.2 schema note | `accounts.tax_exempt` / `.tax_exempt_ref` / `.tax_exempt_expires` | bool/text/date | user-input | exemption is account-level (B4.2) |
| Autopay + payment method ref | S18 step 4 / S21 | BR-CUS-012 | `accounts.autopay` + **PROPOSED-SCHEMA** `accounts.autopay_method_id` → payment_methods (⚠ payments) | bool + uuid | user-input | capture-only v1 (BR-CUS-059) |
| Credit tier | S21 (display) | BR-CUS-012 + BR-CUS-058 | `accounts.credit_tier` (computed cache; rule params **PROPOSED-SCHEMA** `credit_tier_rules`) | text | system-derived (computed) | seeded rule; informational; no edit path |
| Billing cycle | S18 (via unit/premises) | BR-CUS-012 | cycle linkage via unit → route → cycle (⚠ metering read) — snapshot field on assignment row | uuid | system-derived | BR-MET-009 |
| Portal access flag | S21 Overview | BR-CUS-012 | **PROPOSED-SCHEMA** `accounts.portal_enabled` — portal itself out of v1 scope (roadmap) | boolean | user-input | capture-only v1 |
| Status + since-date | — | BR-CUS-012 | `accounts.status` (BR-CUS-055 seeded lookup) / `.opened_at` | lookup/date | system-derived | vocabulary per BR-CUS-055 |
| Solar/battery capacity units | S18/S21 | BR-CUS-012 + B2 r5 #5 | `account_capacities` (account, service, units ≥ 0, effective_from/to) | numeric(18,6) | user-input | ≥ 0; effective-dated |

**6 · Acceptance**
- Given any assignment event, Then an append-only snapshot row exists with plan+version, source, actor and dates, And later catalog edits never change it.
- Given capacity units, Then they store per service, effective-dated, and are readable by rating via service function only.
- Given the credit tier, Then it is only ever written by the BR-CUS-058 computation.
- Given J2, Then step-4 handoff "plan version snapshot saved" is satisfied by this story's write.

**7 · Finance Calculation** — N/A (capture only; capacity pricing is EP-RAT-06/GT-15, deposit math US-CUS-007).

**8 · Open Questions** — None — OQ-058/059/062 are CLOSED (BR-CUS-055 / BR-CUS-059+060 / BR-CUS-058); closure rows live on US-CUS-001 and US-CUS-003 §8.

---
id: US-CUS-007
epic: EP-CUS-02
module: customers
screens: [S18, S19, S20]
wave: 2
status: draft
blocked_by: []
depends_on: [US-RAT-002, US-CUS-003]
journeys: [J2]
rules: [BR-RAT-020, BR-RAT-023, BR-CUS-023, BR-CUS-024, BR-CUS-025, BR-CUS-054, BR-CUS-057]
golden_tests: []
finance_calc: confirmed
---
### US-CUS-007 — Deposit application per rate-plan deposit rules

**1 · Details** — As a Billing Clerk, I want the deposit determined automatically from the assigned plan's deposit schedule (`plan_deposit_rules[account_type]`, fixed $ per consumer category) with the three handling elections (collect now / add to first bill / waive with reason) at creation, carry-forward at move-in, and apply-first settlement at move-out — so that deposits are consistent, liability-tracked and auditable. This story owns the deposit fields inside S18 step 5, S19 step 4 and S20 step 3 plus the `deposit_on_file` write path; collection itself (ACH/card) and refunds execute through payments services (B1 — customers never writes payments tables). Interest on held deposits accrues per BR-CUS-057 (engine owned by US-CUS-023 — the old OQ-061 stub is retired).

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-RAT-020 / BR-RAT-023 | Deposits v1 = fixed $ per consumer category, PLAN-level via `plan_deposit_rules`; 2×-average, per-service amounts and credit-tier waivers explicitly OUT of v1. | CONFIRMED — PO Q&A R1 D6 + R3 (cited, not restated) |
| BR-CUS-023 | Handling elections collect-now / add-to-first-bill / waive-with-reason-code; waive reasons from a tenant lookup; "add to first bill" hands a deposit line instruction to billing. | CONFIRMED (amount) / elections PROPOSED — prototype S18 step 5 |
| BR-CUS-024 / BR-CUS-054 | Carry-forward: a refundable deposit held on a prior closed account of the SAME customer entity may transfer to the new account instead of a new collection (S19); linkage = `customer_accounts` (BR-CUS-054). | CONFIRMED (linkage) / carry mechanics PROPOSED — prototype S19 step 4 |
| BR-CUS-025 | *(shared)* deposit is a liability (never revenue); applied to ~~the final bill first~~ **everything outstanding** at move-out (PO 2026-08-12, OQ-158); remainder refunds via payments `refunds`. **It is never recomputed or partly returned mid-tenancy — a plan change moves no deposit money (PO 2026-08-12, OQ-179).** | PROPOSED (mechanics) · **scope AMENDED PO 2026-08-12** |
| BR-CUS-057 | Deposit interest: tenant-set SIMPLE annual rate, default 0%, monthly accrual from the original receipt date, payout at refund/closure. Display slots (S21 "Interest accrued", S20 disposition) render the accrued value; engine + worked math in US-CUS-023 §7. | CONFIRMED — PO OQ-061 (b) |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | A-12048 (residential) created on RES-STD, collect now | deposit_on_file 150.000000; payments collection reference recorded; audit `deposit.collected`; ledger liability posting happens in W5 (handoff noted, not written here) |
| TC-2 | Commercial account created on COM-SM | Deposit resolves $300.00 from the same schedule — category drives amount, not the plan's services |
| TC-3 | Waive with reason "Property manager guarantee" | deposit_on_file 0; waive reason + actor stored; audit `deposit.waived` |
| TC-4 | Move-in carry-forward (US-CUS-004 TC-1) | A-11208's held deposit transfers within the same customer entity (BR-CUS-054): old account's deposit released, A-12049 deposit_on_file 150.00, original receipt date PRESERVED (interest continuity per BR-CUS-050/057), single audit chain `deposit.carried` |
| TC-5 | Move-out settlement (US-CUS-005 §7) | Applied-first instruction recorded; remainder-due/refund per US-CUS-005 §7; interest term computed per BR-CUS-057 (US-CUS-023 §7 engine — at the tenant default 0% the term is 0.00) |
| TC-6 *(negative)* | "Add to first bill" elected, then staff attempts a second collect-now for the same account | Blocked — one deposit position per account; election is exclusive (BR-CUS-023) |
| TC-7 *(negative)* | Waive elected with reason "—" (blank) | Inline error: reason required (BR-CUS-023) |
| TC-8 *(isolation)* | Lone Star Ridge account creation | Deposit schedule read from Lone Star Ridge's plan rules only; Brazos Bend amounts never leak (RLS) |

**4 · Test Data** — Brazos Bend deposit schedule (EP-RAT-01 seed): residential **$150.00** / commercial **$300.00** / industrial **$500.00** / government **$0.00**. Fixtures: A-12048 residential collect-now; Ridge Coffee-style commercial fixture on COM-SM; waive reasons lookup (Long-standing customer / Property manager guarantee / Credit tier A+ — note tier-based waivers are OUT of v1 per BR-RAT-020, so "Credit tier A+" is recorded as a reason string only, no automation). Lone Star Ridge: Co-op Water Basic, residential $75.00.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Deposit rule (read-only) | S18 step 5 / S19 step 4 | BR-RAT-020/023 | `plan_deposit_rules` (rate_plan × account_type → amount; r5 #8, r6 rename) — ⚠ rating read | numeric(18,6) | reference-data | fixed lookup |
| Handling election | S18 step 5 / S19 step 4 | prototype-extracted | **PROPOSED-SCHEMA** `accounts.deposit_election` (collect_now \| first_bill \| waived \| carried) | enum | user-input | exclusive |
| Waive reason | S18 step 5 | prototype-extracted | **PROPOSED-SCHEMA** waive-reason lookup + `accounts.deposit_waive_reason_id` | uuid | user-input | required when waived |
| Deposit on file | S21 / S20 | prototype-extracted | `accounts.deposit_on_file` (+ **PROPOSED-SCHEMA** `.deposit_received_on` — original receipt date, BR-CUS-050/US-CUS-023) | numeric(18,6) USD | system-derived | ≥ 0 |
| Interest accrued | S21 / S20 | prototype-extracted ($3.20) | **PROPOSED-SCHEMA** `accounts.deposit_interest_accrued` — accrual CONFIRMED per BR-CUS-057 (engine US-CUS-023 §7; tenant rate default 0%) | numeric(18,6) | system-derived | BR-CUS-057 |
| Carry-forward source | S19 step 4 | prototype-extracted | prior account of the same customer via `customer_accounts` (BR-CUS-054, PROPOSED-SCHEMA) | uuid | user-input | same customer entity |
| Refund instruction | S20 step 3 | prototype-extracted | handoff to payments `refunds` (method, amount) — ⚠ B1 | enum + numeric | user-input | BR-CUS-025 |

**6 · Acceptance**
- Given any category, Then the deposit amount is exactly the plan schedule's fixed $ — never computed.
- Given each election, Then deposit_on_file, audit rows and downstream instructions match TC-1/3/4/5.
- Given the interest display, Then v1 renders the BR-CUS-057 accrual (0.00 at the default rate) — no stub, no guessed rate.

**7 · Finance Calculation** — CONFIRMED, lookup not formula (BR-RAT-020/023): `deposit = plan_deposit_rules[rate_plan, account_type].amount`. Worked example: RES-STD + residential → **$150.00**; COM-SM + commercial → **$300.00**. Settlement at move-out (BR-CUS-025, PROPOSED): `applied = min(deposit_on_file + interest, final_bill_total)`; `refund = deposit_on_file + interest − applied` — with §4/US-CUS-005 numbers: applied min(153.20, 184.20) = 153.20 → remainder due $31.00, refund $0.00 (interest per BR-CUS-057; worked accrual in US-CUS-023 §7). GT ref: — (deposit-interest GT flagged per the BR-CUS-057 Test column — number to be allocated at the golden-test freeze).

**8 · Open Questions**
| OQ | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| OQ-061 | *(minted here; shared with US-CUS-005/009)* Deposit interest: v1 scope, rate source and accrual method | Nothing — closed | Product Owner (chat session) | CLOSED(→BR-CUS-057) — option (b): tenant-set simple annual rate, default 0%, monthly accrual, payout at refund/closure; accrual from original receipt date (PO) |
