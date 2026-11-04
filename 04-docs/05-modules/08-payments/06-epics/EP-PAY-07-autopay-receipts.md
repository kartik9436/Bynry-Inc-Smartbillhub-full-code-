# EP-PAY-07 — Autopay capture-intents (v1) & receipts

**Module:** payments · **Wave:** W4 · **Screens:** S32, S33, S35 · **Status:** draft (BR-PAY-001..031 all CONFIRMED — session closed 2026-08-08; schema B2 Addendum r12)

## Scope
**In:** **autopay v1 = capture-INTENT** (BR-PAY-015, PE-12, confirming the BR-CUS-059 reading): enrollment + method are stored/displayed by customers; **bill issue records a capture intent dated the due date** (`autopay_capture_intents`, r12 #6), visible on S32/S33 as "autopay scheduled"; **staff record the actual money** (US-PAY-001) — real charging arrives with the payment rails (W7). And **receipts** (BR-PAY-024, PE-14): auto-queued on **every cleared payment** (print v1 via the platform outbound queue, BR-NOT-005), RCT- numbered (r12 #13), manual re-send from the S35 Receipts modal.
**Out:** enrollment capture UI (customers, BR-CUS-059/US-CUS-003) · actual charging/drafting + autopay authorization form execution (rails W7; NACHA form = BR-NOT-004 ④, notifications) · receipt template design (S67/notifications) · dispatcher mechanics (BR-NOT-005, Eng-Lead 🔒).
**Tables (B2 + r12):** `autopay_capture_intents` (r12 #6), `outbound_messages` (r12 #16), RCT- number series (r12 #13).

## Capability matrix (list screens only — B9 conformance)
No new list screens — intents render on S32 (chip) and S33 (rows/column per US-PAY-004); receipts actions live on S33/S35.

## Stories

---
id: US-PAY-024
epic: EP-PAY-07
module: payments
screens: [S32, S33]
wave: 4
status: draft
blocked_by: []
depends_on: [US-BIL-005, US-CUS-003, US-CUS-012, US-PAY-001]
journeys: [J2]
rules: [BR-PAY-015, BR-CUS-059, BR-PAY-021]
golden_tests: []
finance_calc: confirmed
---
### US-PAY-024 — Autopay capture-intents: bill issue records the intent; staff record the money

**1 · Details** — As the payments service, when a bill issues for an autopay-enrolled account (enrollment + method stored/displayed by customers per BR-CUS-059 — capture-only), I want a **capture intent** recorded: account, invoice, amount = bill total due, **scheduled_on = the due date**, status per r12 #6 (**awaiting-rails v1** — no charge is ever attempted before W7). Intents are **visible on S32 ("autopay scheduled" chip) and S33** (BR-PAY-015) so counter staff can answer "will this draft?" — the v1 answer is always: staff record the actual money when it arrives (US-PAY-001); the display marks an intent **fulfilled when its invoice settles** (computed display state over allocations — presentational derivation, noted in the pack report; the stored status set is r12 #6's). A payment posted by the due date keeps the account on-time per BR-PAY-021 whatever the intent shows. No retry/charge action exists anywhere v1 (supersedes the prototype's "Retry autopay"). When rails land (W7), the dispatcher-side execution consumes these same intents — the v1 record IS the W7 contract. Entry: bill issue (US-BIL-005 event). Exit: intent rows + display.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-PAY-015 | Autopay v1 = capture-INTENT: enrollment + method stored; bill issue records intent dated the due date, visible on S32/S33; staff record the actual money; real charging = rails (W7). | CONFIRMED — PO PA-4, 2026-08-08 (r12 #6, PE-12) |
| BR-CUS-059 | Enrollment is capture-only; no drafting originates anywhere in v1; no re-enrollment at rails. | CONFIRMED — PO OQ-059 (autopay part) |
| BR-PAY-021 | On-time-ness stays a posting-date fact — the intent never substitutes for money. | CONFIRMED — PO explicit ruling, 2026-08-08 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | PE-12: BL-2608-018410 issues for autopay-enrolled ACC-1042 (ACH ••4021) | Intent row: invoice, amount 292.87 (total due), scheduled_on Aug 22 (due date), status awaiting-rails; S32 chip +1; S33 shows "autopay scheduled Aug 22" |
| TC-2 | Sarah pays at the counter Aug 20 (US-PAY-001) | Payment records normally — enrollment never blocks manual recording (BR-CUS-059); invoice settles → the S33/S32 display marks the intent fulfilled; no charge was ever attempted |
| TC-3 *(posting vs clearing)* | Manual payment posted Aug 22, cleared Aug 25 | Account on-time per posted_at (BR-PAY-021); the intent's scheduled_on Aug 22 is display metadata, never an on-time substitute |
| TC-4 | Non-enrolled account's bill issues | No intent row — intents exist only for enrolled accounts |
| TC-5 *(negative)* | Any v1 code path attempts to charge the stored method (or a "Retry autopay" action) | Impossible — no charging path exists before rails (BR-PAY-015); prototype retry action superseded |
| TC-6 *(negative)* | Duplicate intent on issue retry | One intent per (invoice) — idempotent with the issue guard (🔒 Eng-Lead) |
| TC-7 *(isolation)* | Lone Star Ridge issue | Intents for its accounts only (RLS) |

**4 · Test Data** — PE-12: ACC-1042, autopay-enrolled ACH Chase ••4021 (capture-only, US-CUS-003 fixture), BL-2608-018410 total due 292.87, due Aug 22, 2026; counter payment Aug 20 variant + posted-Aug-22/cleared-Aug-25 variant. Non-enrolled: ACC-1103. Actors: system (issue event), Marcus Vega (counter). Isolation: J. Okafor.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Intent row | S32/S33 | BR-PAY-015 | `autopay_capture_intents` (account, invoice, amount, scheduled_on, status — r12 #6) | row | system-derived | one per enrolled-account bill at issue |
| scheduled_on | S33 | BR-PAY-015 ("dated the due date") | `autopay_capture_intents.scheduled_on` = `invoices.due_date` | date | system-derived | never user-set |
| Status | S33 | r12 #6 | intent status (awaiting-rails v1) | enum | system-derived | no charge transitions before W7 |
| Fulfilled display state | S32/S33 | BR-PAY-015 (display) | computed over invoice settlement (`allocations`) — presentational, not stored (pack report P-7) | flag | computed-display | derivation noted, not decided |
| Enrollment + method read | S21/S33 | BR-CUS-059 | customers-owned read (`payment_methods.is_autopay`, `accounts.autopay`) | boolean/ref | reference-data | display only |
| "Autopay scheduled" chip | S32 | BR-PAY-015 | count over open intents | int | computed-display | ties to rows |
| Audit | — | CLAUDE.md #7 | `audit_log` `autopay_intent.recorded` | jsonb | system-derived | append-only |

**6 · Acceptance**
- Given an enrolled account's bill issue, Then exactly one intent exists, dated the due date, visible on S32/S33 — and NOTHING ever attempts a charge in v1.
- Given the actual money recorded manually, Then everything behaves as a normal payment and the intent display resolves.
- Given issue retries, Then intents never duplicate; given tenants, intents never cross.

**7 · Finance Calculation** — CONFIRMED (PE-12: autopay intent → manual record; model §8). No money computed: intent.amount = invoice total due (292.87 cited from the WE-1/PE-1 fixture); on-time-ness remains the posting-date rule (BR-PAY-021).

**8 · Open Questions** — None.

**9 · Build state (2026-08-15, payments visible-half lane)** — **THE TABLE AND THE SERVICE EXIST; NOTHING RECORDS AN INTENT.** `autopay_capture_intents` (migration 0009) carries ONE status and `apps/payments/autopay.py` records one intent per invoice, dated the due date, with the fulfilled state COMPUTED from `allocations` (BR-PAY-034 / P-7). `GET /api/{tenant}/autopay-intents` reads them and there is deliberately no POST and no action route. ⚠ **NOTHING CALLS `record_intent_at_issue`** — BR-PAY-015 puts the trigger at BILL ISSUE (`apps/billing/issue.py`, US-BIL-005) and that module belongs to another lane; every result carries `intent_recording_has_no_caller`. The S32 chip counts real rows and the S33 column is not built.

---
id: US-PAY-025
epic: EP-PAY-07
module: payments
screens: [S35, S33]
wave: 4
status: draft
blocked_by: []
depends_on: [US-PAY-001, US-BIL-023]
journeys: [J2]
rules: [BR-PAY-024, BR-NOT-005, BR-PAY-021]
golden_tests: []
finance_calc: none
---
### US-PAY-025 — Receipts: auto-queued on every cleared payment; manual re-send from S35

**1 · Details** — As the payments service, I want a **receipt auto-queued on every cleared payment** (BR-PAY-024, PE-14): the clearing event (cleared_at set — BR-PAY-021's money-received side) writes one receipt row per active channel to the **platform outbound queue** (BR-NOT-005 — written, never sent inline; **print v1**, email/SMS rows written with deferral markers until their rails land), rendered from the tenant receipt template (B2 `notification_templates` code `receipt`; tokens per prototype: {first_name} {amount} {date} {balance} {confirmation}), numbered from the **RCT- series** (r12 #13) and referenced on the S33 row. And I want **manual re-send** from the S35 Receipts modal (row/bulk from S33): channel elections with eligibility counts (email/SMS opt-in), attach-PDF election, "Send N receipts ✓" — every re-send a new queue row, audited, never a money event. Reversed/NSF'd payments do not re-issue receipts (their notices are US-PAY-009/010's). Entry: clearing event / S35 modal. Exit: queue rows + receipt numbers.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-PAY-024 | Receipt auto-queued on every cleared payment (delivery queue; print v1); manual re-send from S35. | CONFIRMED — PO Lane B-3, 2026-08-08 (PE-14, r12 #4) |
| BR-NOT-005 | Receipt rows are outbound-table writes; the dispatcher sends in tenant-config batches. | CONFIRMED — PO volume ruling, 2026-08-08 (r12 #16) |
| BR-PAY-021 | The trigger is CLEARING (money actually received) — posting alone queues nothing. | CONFIRMED — PO explicit ruling, 2026-08-08 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | PE-14: the PE-1 check clears Aug 8 | Receipt RCT-2608-000389 queued (print row dispatchable v1; email/SMS rows with deferral markers per channel config); tokens filled (Sarah, $292.87, Aug 8, $0.00, PMT-2608-000412); S33 row shows the receipt # |
| TC-2 *(posting vs clearing)* | Payment posted Aug 22, cleared Aug 25 | NO receipt at posting; receipt queues on Aug 25 clearing (BR-PAY-021/024 — receipts follow money received) |
| TC-3 | Lockbox commit (US-PAY-003) with "Send receipts" elected | One receipt per committed cleared row — all queue writes, batched by the dispatcher (BR-NOT-005); no inline sends at any volume |
| TC-4 | Manual re-send, 3 selected on S35 | Elections honored (email 3/3, SMS 2/3 opt-in, print); new queue rows; toast "Send 3 receipts ✓"; audit `receipt.resent` |
| TC-5 *(negative)* | Re-send attempted for a processing (uncleared) payment; inline SMTP call attempted from the receipt path | No receipt exists to re-send (clearing-triggered); inline send forbidden — queue only (BR-NOT-005) |
| TC-6 *(isolation)* | Lone Star Ridge receipts | Its RCT- series, templates and queue rows only (RLS) |

**4 · Test Data** — PE-1/PE-14: PMT-2608-000412 ($292.87, ACC-1042/Sarah Miller) cleared Aug 8, 2026 → RCT-2608-000389. Posted-Aug-22/cleared-Aug-25 fixture (US-PAY-001 TC-2). Lockbox: PE-5's 38 committed rows. S35 selection: 3 payments (prototype: email 3/3, SMS 2/3). Template: tenant `receipt` v1 (tokens per prototype preview). Actors: system; Priya Menon (re-send). Isolation: J. Okafor.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Receipt queue row | — | BR-PAY-024 + BR-NOT-005 | `outbound_messages` (r12 #16/#4): payment ref, template, channel, status queued | rows | system-derived | on clearing only; one per active channel |
| Receipt number | S33 | r12 #13 | RCT- tenant series ref on the receipt | text | system-derived | unique per tenant |
| Template + tokens | S35 preview | prototype-extracted + B2 `notification_templates` (code `receipt`) | template render ({first_name},{amount},{date},{balance},{confirmation}) | text/pdf | computed-display | notifications-owned content |
| Channel elections + opt-ins | S35 | prototype-extracted | queue rows per elected channel; deferral markers on email/SMS (US-BIL-023 pattern) | boolean/counts | user-input | opt-in respected; ≥1 channel |
| Attach PDF | S35 | prototype-extracted | render election on the queue row | boolean | user-input | print/PDF v1 |
| Re-send | S35/S33 | BR-PAY-024 | new queue rows (never edits) | rows | user-input | audited; not a money event |
| Audit | — | CLAUDE.md #7 | `audit_log` `receipt.queued/resent` | jsonb | system-derived | append-only |

**6 · Acceptance**
- Given a clearing, Then the receipt queues automatically with correct tokens and an RCT- number — and never before clearing.
- Given bulk clearing (lockbox), Then every receipt is a queue row drained by the dispatcher — zero inline sends.
- Given re-send, Then elections and opt-ins are honored, new rows are written, and the action is audited.
- Given tenants, Then series, templates and rows never cross.

**7 · Finance Calculation** — N/A (receipts move documents; figures on the receipt are the payment's own — PE-14).

**8 · Open Questions** — None.
