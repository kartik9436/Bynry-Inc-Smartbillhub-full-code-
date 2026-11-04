# EP-NOT-03 — Notice generation, receipts & contracts (render + queue; triggers stay with their owners)

**Module:** notifications · **Wave:** W4 (collections/J4 + payments consumers) · **Screens:** S94–S96 (templates), S67 (contract designers), consumer surfaces S22/S24/S33/S34/S35 · **Status:** draft (BR-NOT-001..005, BR-CUS-039/044, BR-PAY-016/017/024/035, BR-REP-016 all CONFIRMED)

## Scope
**In:** the **disconnect-notice generation service** — A19 §2 tier rendering, certified-mail final, medical-hold exclusion, `notice_history` append (J4 step 2 contract) — consumed by US-CUS-015 (S22 modal), US-PAY-014 (sequence engine), US-PAY-015 (bulk modal); **reminder/dunning rendering** per the tone→tier mapping (BR-PAY-035) with tenant-config day numbers (BR-REP-016); **plan-notice + receipt rendering & queue consumption** (BR-PAY-016, BR-PAY-024); **S67 contract templates** — 4 types × consumer-category variants, effective-dated versions, e-sign-only execution (BR-NOT-001..004, BR-CUS-044).
**Out:** WHEN to send — ladder evaluation, plan-miss detection, S22/S34/S35 UI (customers/payments own the triggers and write the queue rows) · late fees + reconnect fees (billing money) · e-sign envelope transport (DocuSign seam — integrations, B7) · queue/dispatch mechanics (EP-NOT-01).

## Capability matrix (list screens only — B9 conformance)
No new list screens (the S8 templates-card list row is in EP-NOT-02's matrix; S34/S35 lists are payments-owned).

## Stories

---
id: US-NOT-009
epic: EP-NOT-03
module: notifications
screens: [S94, S22, S34, S35]
wave: 4
status: draft
blocked_by: []
depends_on: [US-NOT-001, US-NOT-007, US-PAY-014, US-PAY-015]
journeys: [J4]
rules: [BR-CUS-039, BR-PAY-017, BR-NOT-005]
golden_tests: []
finance_calc: none
---
### US-NOT-009 — Disconnect-notice generation: tiers, certified final, medical-hold exclusion, notice_history

**1 · Details** — As the system, I want ONE disconnect-notice generation service that every trigger surface calls — the S22 modal (US-CUS-015), the sequence engine (US-PAY-014), the S35 bulk modal (US-PAY-015) — rendering the requested tier from the published S94 template (A19 §2: **tier 1 10-day informative · tier 2 5-day firmer · tier 3 48-hour final**): {balance}, {pay_by_date}/{cut_date}, {reconnect_fee} read from the tenant charge codes (BR-BIL-007 — never hardcoded), {state_puc_ref} + regulatory footer on the final tier. **Certified mail is REQUIRED and forced for the final tier** (paper v1-complete per BR-PAY-017; TX PUC constraint noted in A15); **SMS supplements the mailed notice, never replaces it** (A19 rule 3). **Medical-hold accounts are excluded**: generation REFUSES and records the skip — **every send AND skip appends `notice_history`** (r12 #7; J4 step 2: "notice_history appended; medical-hold skipped; certified mail on final tier"). Output = queue rows only (BR-NOT-005) — the letter dispatches via the print/certified seam, never inline. Entry: tier + account(s) from a trigger owner. Exit: rendered artifacts queued; notice_history rows; collection state advanced by the owner (US-PAY-014).

**THE RECORD IS READABLE, ADDED 2026-08-16 (DEF-128) — `GET /notices`.** `notice_history`
had a writer from 2026-08-11 (`apps/payments/notices.record_notice`) and **no reader at
all**, so every letter and every skip this rule produces was recorded where no surface
could open it — and this is the trail a utility shows a regulator when a customer says
they were never told. The read is published in payments (the owning module, B1) and served
through `apps/notifications/payments_seam.py`.

**`f.certified=true` IS THE CERTIFIED-MAIL REGISTER, and it is a TIER filter.** BR-CUS-039
makes certified mail a property of the **48-hour final tier** and of no other, so asking
for "certified" can never hand back the 10-day letters. Each row states `certified_mail`.

**THE CERTIFIED NUMBER IS NULL ON EVERY ROW AND THE RESPONSE SAYS WHY.** It arrives on the
print provider's response at dispatch (field map §3, r10 #8) and no provider adapter exists
on any channel — delivery is out of this release by PO ruling (2026-08-15). A tracking
number is never fabricated onto a legal record.

**SKIPS ARE SERVED BY DEFAULT** (J4 step 2): an account excluded for a medical hold must
never be indistinguishable from one nobody ever chased. **Money carries its currency** —
`reconnect_fee` is served as a STRING at NUMERIC(18,6) fidelity beside the tenant's CHAR(3)
code, never as a JSON number (CLAUDE.md rule 2). **An unreadable record answers
`available: false`**, never an empty list.

⚠ **NO GENERATION ENDPOINT WAS MINTED HERE.** `POST /accounts/{id}/notices` (11b §2.6, S22
modal 5) and `POST /collections/notices` (§2.9, S34 bulk) are the customers' and payments'
doors this §1 already names, and `apps/customers/services.send_disconnect_notice` refuses
today naming OQ-133/136/137. Where an account stands on the ladder is unruled; a second
door would be notifications deciding it.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-CUS-039 | Tiers per A19 §2; certified mail REQUIRED for final (SMS never stands alone); reconnect fee from tenant charge codes; medical-hold excluded; each send appends notice_history. | CONFIRMED — PO closure batch, 2026-08-08 |
| BR-PAY-017 | 10-day → 5-day → 48h certified final; paper v1-complete; medical-hold excluded; email/SMS ride the queue when their rails land. | CONFIRMED — PO PA-6, 2026-08-08 |
| BR-NOT-005 | Notice output = outbound queue rows; never sent inline. | CONFIRMED — PO ruling, 2026-08-08 |
| A19 rule 3 | SMS never stands alone for disconnection — the certified letter is the legal instrument. | CONFIRMED — A19 r8 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Tier-1 for A-11024 (US-PAY-014 ladder step) | 10-day letter rendered from published S94 version — "past due in the amount of $1,842.10… pay by {pay_by_date}" + assistance/plan offer; paper queue row; notice_history append (tier, template version, channel, when) |
| TC-2 | Tier-3 (48-hour) for A-11340 | Certified-mail forced ON (server-side even if forged off — US-CUS-015 TC-6 pair); regulatory footer + {state_puc_ref} + medical/critical-care line rendered; certified number from provider response lands on the queue row |
| TC-3 | Tier-2 with SMS elected | SMS queue row written ONLY alongside the letter row — a notice request with SMS-only is rejected (rule 3) |
| TC-4 *(negative)* | Any tier requested for medical-hold A-11020 | Generation refuses; NOTHING queued; notice_history records the SKIP with reason medical_hold (J4 contract) |
| TC-5 *(negative)* | Reconnect-fee token with no RECON charge code configured | Render fails with a config error naming the charge code — the fee is never invented or defaulted (BR-BIL-007) |
| TC-6 *(batch pacing)* | Bulk tier-1 to 1,200 accounts (US-PAY-015) | 1,200 letter rows queued instantly; dispatch drains in tenant-config batches (default 500 → 3 batches) at provider pace — never one burst (BR-NOT-005) |
| TC-7 *(isolation)* | notice_history + queue query | Lone Star Ridge sees only its own notices (RLS) |
| TC-8 *(surface, added 2026-08-16)* | `GET /notices` after a final-tier letter and a 10-day letter | Both rows served, newest first; the final-tier row reads `certified_mail: true` and `reconnect_fee: "45.00"` beside the tenant's currency |
| TC-9 *(surface, added 2026-08-16)* | `GET /notices?f.certified=true` on the same data | The 10-day row is absent — the register narrows to `final_48_hour` and nothing else — and `certified_number` is `null` with `certified_number_unavailable` in `problems` |
| TC-10 *(surface, added 2026-08-16)* | The payments read unpublished | `available: false` with `notice_history_read_unpublished`, and an EMPTY list. "We cannot show you" and "this customer was never contacted" must never render the same |

**4 · Test Data** — Brazos Bend: A-11024 Ridge Coffee $1,842.10 (tiers 1–2), A-11340 final-tier fixture (cut date Aug 18 2026), A-11020 medical hold (skip fixture — EP-PAY-04 §4), RECON charge code $45.00; missing-RECON negative on a fresh tenant fixture. Bulk fixture: 1,200 accounts, batch 500. Template: disconnect v2 published. Isolation: Lone Star Ridge A-2201.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Tier + account(s) request | S22/S34/S35 | prototype-extracted (owner modals) | service call params from trigger owners | enum/uuid | user-input (upstream) | tier ∈ 3 |
| Tier render | — | A19 §2 + BR-CUS-039 | published S94 version via US-NOT-005 | pdf | system-derived | pinned at queue-write |
| Reconnect fee token | rendered letter | BR-BIL-007 (via BR-CUS-039) | tenant charge-code read (rating/billing-owned) | numeric USD | reference-data | display-only; missing = error |
| Certified-mail forcing | — | BR-CUS-039 + A19 §2 tier 3 | channel constraint on final tier | flag | system-derived | server-enforced |
| Certified number | queue row | A19 r8 (certified-mail number) | provider response (r10 #8) | text | integration | final tier |
| Medical-hold exclusion | — | A15 + BR-CUS-039 | account flag read (customers-owned) → refuse + skip record | boolean | reference-data | hard block |
| notice_history append (send AND skip) | S21/S34 surfaces | r12 #7 + J4 step 2 | `notice_history` append-only | rows | system-derived | every send and every skip |
| Queue rows | — | BR-NOT-005 | `outbound_messages` (r12 #16) | rows | system-derived | letter mandatory; SMS supplemental |

**6 · Acceptance**
- Given any trigger surface, Then the same service renders the tier per A19 §2 with the fee from the charge catalog and queues — never sends — the artifacts.
- Given the final tier, Then certified mail cannot be omitted and the regulatory footer renders.
- Given medical hold, Then nothing is sent and the skip is on notice_history.
- Given a bulk send, Then dispatch is batched at provider pace; given tenants, Then notices never cross.

**7 · Finance Calculation** — N/A — no money math (balance/fee values arrive in the merge context; the reconnect fee applies only on actual reconnection by billing). Ref: PE-15.

**8 · Open Questions** — **OQ-243 (BLOCKING, minted 2026-08-16): this class has no body, and the three tier bodies §1 quotes have one slot between them.** §1 says the service renders *"the requested tier from the published S94 template"*, and `notification_templates` is unique on `(code, category, language)` — no tier column, no tier token in `catalogs.disconnect_notice`, and no conditional in the renderer. So one published body serves all three tiers: seeding tier 1 sends the 10-day wording as the 48-hour CERTIFIED letter, seeding tier 3 opens a first reminder with *"NOTICE OF DISCONNECTION"*. **And the regulatory rights footer A19 r8 requires of this class** — dispute rights, medical hold, weather suppression, weekend/holiday suppression, the PUC complaint line — **is written in no signed document**, while `mandatory_content` makes `{state_puc_ref}` non-removable (TC-6). Until it is ruled, the platform seeds NO disconnect-notice body and generation refuses by name (DEF-163): everything in §1 except the words is built and tested.

---
id: US-NOT-010
epic: EP-NOT-03
module: notifications
screens: [S95, S34, S35]
wave: 4
status: draft
blocked_by: []
depends_on: [US-NOT-001, US-NOT-007, US-PAY-014, US-PAY-015]
journeys: [J4]
rules: [BR-PAY-035, BR-PAY-017, BR-REP-016, BR-NOT-005]
golden_tests: []
finance_calc: none
---
### US-NOT-010 — Reminder/dunning rendering: the tone→tier mapping + tenant-config day numbers

**1 · Details** — As the system, I want reminder rendering locked to the ratified **tone→tier mapping** (BR-PAY-035): **friendly = due+3 reminder · firm = 10-day · final = 5-day/48h — free-text tones do not exist**. The S35 modal's Tone select (Friendly/Firm/Final warning, prototype-extracted) and the sequence engine's steps (US-PAY-014) both resolve through this one mapping to the template set: **Dunning 1/2/3 are the reminder stages of the BR-PAY-017 sequence** (BR-REP-016) — their banner day numbers render from the tenant cadence config (seeded 7/14/30), the ladder steps from the tenant ladder settings (seeded due+3/10-day/5-day/48h) — day numbers are config, never constants. Dunning renders as a **courtesy reminder** (no regulatory footer — A19 rule 2) and **escalates INTO the disconnect notice** (A19 r8) — the 10-day/5-day/48h notice steps render via US-NOT-009, not here. Every rendered reminder appends `notice_history` (send AND skip) and outputs queue rows only (BR-NOT-005). Entry: tone or ladder step + account(s). Exit: queued reminder artifacts + history rows.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-PAY-035 | Tone options map to the dunning-tier templates (friendly = due+3 · firm = 10-day · final = 5-day/48h); free-text tones do not exist. | CONFIRMED — PO PP-5, 2026-08-08 |
| BR-REP-016 | Dunning 1/2/3 = reminder stages of the BR-PAY-017 sequence; 7/14/30 are seeded defaults of the tenant-config cadence. | CONFIRMED — PO RQ-8, 2026-08-08 |
| BR-PAY-017 | The ladder + its intervals are tenant-config; manual sends use the same ladder, channels and exclusions. | CONFIRMED — PO PA-6, 2026-08-08 |
| A19 rule 2 | Dunning ≠ disconnect notice: reminder content, no regulatory footer. | CONFIRMED — A19 r8 |
| BR-NOT-005 | Output = queue rows only. | CONFIRMED — PO ruling |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Ladder due+3 step for BL-2607-018206 | Friendly reminder rendered (Dunning stage 1 content: unpaid-bill table, days-late, plan offer, NO footer); queue row + notice_history |
| TC-2 | Priya picks tone "Firm" in S35 | Resolves via the BR-PAY-035 mapping to the 10-day step's reminder rendering — same mapping as the engine, no separate path |
| TC-3 | Tenant cadence 7/14/30 → 10/20/35 | Stage banners + days-late labels render from config; no constant anywhere (BR-REP-016; US-NOT-007 TC-3 pair) |
| TC-4 | Escalation boundary | The ladder's 10-day/5-day/48h NOTICE steps route to US-NOT-009 (disconnect class, regulated); dunning never renders a cut date it doesn't have |
| TC-5 *(negative)* | API reminder request with tone "urgent-custom" | Rejected — free-text tones do not exist (BR-PAY-035) |
| TC-6 *(batch pacing)* | Bulk reminder to 2,400 accounts (S34 bulk action) | 2,400 rows queued instantly; dispatched in 5 batches of 500 (default) at provider pace — never one burst |
| TC-7 *(isolation)* | Lone Star Ridge reminder run | Its ladder config (reminder due+3) + its rows only (RLS; EP-PAY-04 §4 isolation fixture) |

**4 · Test Data** — Brazos Bend: BL-2607-018206 due Jul 6 2026 unpaid (A-11024); ladder seeded due+3/10-day/5-day/48h; cadence seeds 7/14/30 + changed fixture 10/20/35; bulk 2,400-account fixture; tone fixtures Friendly/Firm/Final. Actors: system job; Priya Menon (S35). Isolation: Lone Star Ridge (reminder due+3).

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Tone select | S35 | prototype-extracted + BR-PAY-035 | mapping to ladder-step template — no free text | enum | user-input | 3 values only |
| Tone→tier mapping | — | BR-PAY-035 | fixed resolution friendly=due+3 · firm=10-day · final=5-day/48h | map | reference-data | single mapping for engine + modal |
| Stage day numbers | rendered reminder | BR-REP-016 | tenant cadence config (S70; r14 #5 keys) | ints | reference-data | seeded 7/14/30 |
| Ladder step context | — | BR-PAY-017 | collection state read (r12 #7, payments-owned) | enum | system-derived | engine advances it, not this story |
| Reminder render | — | A19 r8 dunning row + A19 rule 2 | published S95 version via US-NOT-005 | pdf/html | system-derived | no regulatory footer class |
| notice_history append | S34/S21 | r12 #7 + J4 | `notice_history` append-only | rows | system-derived | send AND skip |
| Queue rows | — | BR-NOT-005 | `outbound_messages` | rows | system-derived | channels per rails (email W6/SMS v1.1 markers) |

**6 · Acceptance**
- Given a tone or a ladder step, Then one shared mapping resolves it to the dunning-stage rendering — free text impossible.
- Given tenant cadence changes, Then rendered day numbers follow config.
- Given the regulated steps, Then rendering routes to the disconnect class (US-NOT-009), keeping dunning a courtesy reminder.
- Given bulk sends, Then queue + batched dispatch; given tenants, Then config and rows never cross.

**7 · Finance Calculation** — N/A — no money math (late-fee amounts computed by billing — BR-BIL-001/008; this story renders them). Ref: PE-15.

**8 · Open Questions** — None (residual precision on which template body renders the manual "firm" tone at the 10-day step = candidate note in the pack report — mapping itself is ratified).

---
id: US-NOT-011
epic: EP-NOT-03
module: notifications
screens: [S96, S33, S35]
wave: 4
status: draft
blocked_by: []
depends_on: [US-NOT-001, US-NOT-005, US-PAY-018, US-PAY-025]
journeys: [J2, J4]
rules: [BR-PAY-024, BR-PAY-016, BR-NOT-005]
golden_tests: []
finance_calc: none
---
### US-NOT-011 — Receipts + plan-notice rendering & queue consumption

**1 · Details** — **Deferred-wave note: receipt/plan-notice PRINT renders + dispatches in v1; the payment-receipt email and payment-received SMS classes render v1 but their SEND adapters defer (email → W6, SMS → v1.1 — US-NOT-003).** As the system, I want the queue rows written by payments to render and dispatch correctly: **receipts** — auto-queued on every CLEARED payment (BR-PAY-024, r12 #4; clearing per BR-PAY-021), rendered from the published S96 receipt version (one transaction — A19 r8) for print, the "Payment receipt" email class and "Payment received" SMS class for their rails; manual re-send from S35 = NEW rows, never edits (US-PAY-025 contract); **plan notices** — reminder −3d, missed +1d, void (BR-PAY-016, tenant-config seeds 3/1/2) arrive as queue rows + `notice_history` appends from US-PAY-018; this story dispatches them content-agnostically — the A19 r8 16-template set contains **no plan-notice body**; the content gap is flagged in the pack report (candidate N-1), NOT decided here: rows carry their template code and dispatch blocks safely on an unpublished/absent template (same behavior as any missing published version). Entry: queue rows from US-PAY-018/025. Exit: rendered artifacts dispatched per channel rails.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-PAY-024 | Receipt auto-queued on every cleared payment (delivery queue; print v1); manual re-send from S35. | CONFIRMED — PO Lane B-3 (PE-14, r12 #4) |
| BR-PAY-016 | Plan notices (reminder −3d · missed +1d · void at 2nd miss) via the delivery queue; tenant-config defaults. | CONFIRMED — PO PA-5, 2026-08-08 (r12 #9) |
| BR-NOT-005 | All of the above are queue rows first; dispatcher sends. | CONFIRMED — PO ruling |
| A19 r8 (receipt + email/SMS rows) | Receipt = one transaction, no due date; receipt email shortest of the set; payment-received SMS shortest in the system. | CONFIRMED — A19 r8 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | PMT-2608-0455 clears $247.30 | Receipt row (US-PAY-025) renders S96 v1: amount, method ACH, confirmation RCT-2608-0455, applied-to BL-2607-018206, balance $412.80 → $165.50, processed-by Priya Menon; print dispatches v1 |
| TC-2 | Receipt email/SMS rows | Render fine v1 (preview-able); rest `queued` with deferred markers — no send before W6/v1.1 (US-NOT-003 contract) |
| TC-3 | Manual re-send from S35 | NEW queue rows rendering the same pinned version; audited; no money event (US-PAY-025 TC pattern) |
| TC-4 | Plan reminder row for ACC-1310 (−3d) | Dispatch path accepts the row; notice_history already appended by the writer; with no published plan-notice template the row HOLDS with a missing-template error surfaced on the dashboard — never silently dropped, never invented content |
| TC-5 *(negative)* | Receipt row requested at POSTING (not clearing) | No row — receipts trigger on CLEARING only (BR-PAY-021 via US-PAY-025); posting-only payment produces nothing |
| TC-6 *(negative)* | Duplicate clearing event | No duplicate receipt row (US-NOT-001 TC-5 pair) |
| TC-7 *(isolation)* | Lone Star Ridge receipts | Own rows/templates only (RLS) |

**4 · Test Data** — Brazos Bend: PMT-2608-0455 $247.30 ACH cleared Aug 9 2026 (posted Aug 8 — both dates per BR-PAY-021), receipt RCT-2608-0455; re-send fixture same payment; plan fixture ACC-1310 reminder Aug 12 (installment $36.22 due Aug 15 — EP-PAY-05 schedule). Posting-only fixture: check posted, uncleared. Isolation: Lone Star Ridge PMT-0301.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Receipt queue row | — | BR-PAY-024 + r12 #4 | `outbound_messages` (payment ref, template `receipt`, channel, status) | rows | system-derived | clearing-triggered only |
| Receipt render | S33/S35 surfaces | A19 r8 receipt row | published S96 version via US-NOT-005 | pdf | system-derived | one transaction; no due date |
| Receipt email/SMS classes | — | A19 r8 email/SMS tables | payment-receipt email + payment-received SMS versions | html/text | system-derived | deferred rails (W6/v1.1) |
| Re-send | S35/S33 | BR-PAY-024 | new queue rows (never edits), audited | rows | user-input | not a money event |
| Plan-notice rows | — | BR-PAY-016 + r12 #9 | `outbound_messages` + `notice_history` (written by US-PAY-018) | rows | system-derived | queue-write upstream |
| Plan-notice body | — | **GAP — pack report N-1 (candidate OQ)** | no template class in the A19 16-set; dispatch holds on missing published template | — | — | never invented |

**6 · Acceptance**
- Given a cleared payment, Then the receipt renders per A19 (one transaction, no due date) and print dispatches; email/SMS rows wait on their rails.
- Given re-send, Then new rows render the pinned version with an audit trail and zero money effect.
- Given plan-notice rows, Then they dispatch content-agnostically and HOLD visibly when their template is absent — content is never invented.
- Given tenants, Then receipts and notices never cross.

**7 · Finance Calculation** — N/A — no money math (balances before/after computed by payments; rendered here). Ref: PE-14.

**8 · Open Questions** — None (plan-notice template content = candidate N-1 in the pack report, routed to the Product Owner by the orchestrator).

---
id: US-NOT-012
epic: EP-NOT-03
module: notifications
screens: [S67, S24]
wave: 4
status: draft
blocked_by: []
depends_on: [US-NOT-005, US-NOT-006, US-CUS-018]
journeys: [J4]
rules: [BR-NOT-001, BR-NOT-002, BR-NOT-003, BR-NOT-004, BR-CUS-044]
golden_tests: []
finance_calc: none
---
### US-NOT-012 — S67 contract templates: 4 types × category variants, effective-dated versions, e-sign-only

**1 · Details** — As a System Admin, I want the S67 **Contracts group** in the templates card with designers for the four v1 contract types (BR-NOT-004): **① Payment-plan agreement** (A19 §3 layout: header, terms with installment schedule table + down payment, conditions — autopay from {payment_method}, dunning/disconnect paused while current, default clause voiding on {missed_count} missed —, signature block), **② Service agreement** (move-in/new connection), **③ Deposit agreement/receipt**, **④ Autopay authorization form** (recurring ACH/card debit — NACHA-required for recurring ACH). Each type carries **per-consumer-category variants** — Residential / Commercial / Industrial / Government **plus a default fallback** — and generation picks the variant by the account's category (BR-NOT-001, consistent with the S91/S92 designer pattern per BR-NOT-003). Versions are **effective-dated** (BR-NOT-002): generation renders the version in effect; a generated or signed contract **permanently references the exact version used** (never re-rendered — BR-TEN-017 consistency). Execution is **customer e-signature ALONE** — the countersign block is dropped (BR-CUS-044; A19 addendum c); the e-sign envelope travels the DocuSign seam (B7) and the signed document lands in account documents (US-CUS-018/US-PAY-017 contract). Entry: S8 templates card → Contracts group; generation calls from customers/payments flows. Exit: rendered contract → e-sign → signed PDF pinned to its version.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-NOT-001 | Per-consumer-category variants (Res/Com/Ind/Gov) + default fallback; generation picks by account category. | CONFIRMED — PO 2026-08-08 |
| BR-NOT-002 | Effective-date versioned; generated/signed contracts permanently reference the exact version used. | CONFIRMED — PO 2026-08-08 |
| BR-NOT-003 | Variant pattern consistent with the existing designers; contracts extend it to all four categories. | CONFIRMED — derived consistency note (ratified) |
| BR-NOT-004 | Four v1 types: payment-plan agreement · service agreement · deposit agreement/receipt · autopay authorization (NACHA-required for recurring ACH). | CONFIRMED — PO 2026-08-08 |
| BR-CUS-044 | Payment-plan agreement executes via the customer's e-signature alone; activation ONLY on signature. | CONFIRMED — PO closure batch, 2026-08-08 (A19 addendum c) |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Contracts group on S8 | Four types listed, each expandable to its category variants + default; designer opens per the S91–S106 pattern (BR-TEN-040) |
| TC-2 | Plan agreement generated for commercial A-11024 (US-CUS-018 flow) | Commercial variant renders A19 §3 blocks — schedule table 5 × $36.22 + $36.20, down $50, default clause {missed_count}=2 (from tenant plan config) — pinned to the version effective today |
| TC-3 | Industrial account, no industrial variant published | Default-fallback variant renders (BR-NOT-001); no error, no wrong-category document |
| TC-4 | Version effective-dating | v2 effective Sep 1: generation Aug 20 → v1; Sep 2 → v2; the Aug 20 contract signed Sep 5 still references v1 (BR-NOT-002) |
| TC-5 *(negative)* | Rendered agreement inspected for a countersign block | Absent — customer e-signature alone (BR-CUS-044; A19 §3 corrected); an API activation without a signature event is rejected (US-PAY-017 TC-7 pair) |
| TC-6 *(negative)* | Delete attempted on a version referenced by a signed contract | Blocked forever (US-NOT-006 audit-lock; BR-NOT-002) |
| TC-7 *(isolation)* | Lone Star Ridge contracts | Own variants/versions; signed docs scoped (RLS) |

**4 · Test Data** — Brazos Bend: plan-agreement fixture per EP-PAY-05 (balance $267.30, down $50, 6 installments 5 × $36.22 + $36.20 — remainder-on-final per BR-CUS-043); categories Res/Com/Ind/Gov; commercial fixture A-11024; industrial-fallback fixture A-11602; service-agreement v1 eff Jan 1 / v2 eff Sep 1 2026; autopay-authorization fixture with ACH mandate text block (NACHA note). Actors: Alex Reed (publish), Marcus Vega (generation via S24). Isolation: Lone Star Ridge service agreement v1.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Contract types (4) | S67 | BR-NOT-004 + BR-TEN-040 | contract template registry rows (US-NOT-006 lifecycle; DDL Eng-Lead 🔒) | rows | reference-data | exactly the four v1 types |
| Category variants + default | S67 | BR-NOT-001 | variant rows per type (Res/Com/Ind/Gov + default) | rows | user-input | fallback mandatory |
| Effective-dated versions | S67 | BR-NOT-002 | effective_from on version rows (US-NOT-006) | date | user-input | picks version in effect |
| A19 §3 blocks (plan agreement) | S67 ① | A19 §3 + addendum c | template body: terms/schedule/conditions/signature | text | user-input | no countersign block |
| Variant resolution | — | BR-NOT-001 | account consumer-category read (customers-owned) | enum | reference-data | category → variant → default |
| E-sign envelope | S24 step 3 | BR-CUS-044 | DocuSign seam (⚠ integrations B7); signed pdf → account documents | event/pdf | integration | signature alone activates |
| Signed-contract version ref | — | BR-NOT-002 | permanent template+version reference on the signed record | uuid/int | system-derived | never re-rendered |

**6 · Acceptance**
- Given the Contracts group, Then all four types exist with category variants + default fallback, on the standard designer lifecycle.
- Given generation, Then the account's category picks the variant, the effective date picks the version, and the reference is permanent once generated/signed.
- Given execution, Then the customer's e-signature alone completes the contract — no countersign anywhere.
- Given tenants, Then variants, versions and signed documents never cross.

**7 · Finance Calculation** — N/A — no money math (installment schedule math is BR-CUS-043, computed by payments; rendered here).

**8 · Open Questions** — **OQ-244 (minted 2026-08-16): the payment-plan agreement's instalment SCHEDULE has no merge token, so type ① cannot be seeded either.** A19 §3 catalogues every token of the agreement verbatim except *"schedule table (# · due date · amount · remaining)"*, which is a repeating block over the plan's instalment rows and cannot be expressed by single-value substitution — a customer would e-sign an agreement stating *"557.13 over 4 instalments"* and not one due date or amount. BR-NOT-002 also makes every contract version effective-dated, so a platform-seeded agreement needs an `effective_from` a human chose rather than the day provisioning ran. **OQ-206** still covers types ②③④, which have a ratified TYPE and no content at all. The lifecycle, the category variants, the effective dating and BR-CUS-044's e-signature-only execution are built; no contract body is seeded (DEF-163).
