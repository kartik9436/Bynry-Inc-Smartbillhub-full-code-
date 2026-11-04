# EP-CUS-04 — Account action modals
> Reconciled 2026-08-08 against PO rulings (BR-CUS-046..059) — propagation sweep.

**Module:** customers (product name: Accounts) · **Wave:** W4 · **Screens:** S22 · **Status:** draft

## Scope
**In:** the seven S22 modals launched from the S21 header — Record payment, Adjust, Send statement, Print bill, Issue credit, Disconnect notice, Add note. These stories define the **account-side flow** (fields, validation, confirm → toast → audit per IS-6) and the **handoff** into the owning module's service: payments (record/allocate — BR-PAY-001/010), billing (adjustment/credit rows, immutability — BR-BIL-004/BR-CUS-037), notifications (statement/notice rendering per A19). Customers writes none of the financial tables itself.
**Out:** allocation/posting engines (payments/ledger) · the S34/S35 payments-module bulk variants of these modals · template content (A19/S91+ designers) · reversal flows (payments, BR-PAY-011) · autopay drafting (W7 rails — capture-only v1, BR-CUS-059).

## Capability matrix (list screens only — B9 conformance)
No list screens — all seven are modals (quick single actions per design README). IS-6 governs confirm/toast/audit; IS-10 modal accessibility.

## Stories

---
id: US-CUS-012
epic: EP-CUS-04
module: customers
screens: [S22, S21]
wave: 4
status: draft
blocked_by: []
depends_on: [US-CUS-008, US-CUS-010]
journeys: [J2]
rules: [BR-CUS-037, BR-CUS-059, BR-PAY-001, BR-PAY-010, BR-PAY-002]
golden_tests: [GT-7]
finance_calc: confirmed
---
### US-CUS-012 — Record payment modal

**1 · Details** — As a Billing Clerk, I want the Record payment modal — Current balance (read), Amount (defaults to balance), Payment date (defaults today), Method (ACH/Card/Check/Cash/Lockbox), Confirmation/check #, Apply to (Oldest open bill / Specific bill / Carry as credit / Split), Memo — per A2 §S22, so that counter/phone payments post immediately with correct allocation. Entry: S21 primary action or Payments-tab button. Exit: **Record payment ✓** → payments service call → toast ("Payment recorded") → S21 refreshed. **Handoff:** the payments service owns the payment row, allocation rows (BR-PAY-010 order) and idempotency (CLAUDE.md #6); this story owns the form, validation, the Apply-to instruction and the audit trigger. **Autopay note (BR-CUS-059):** enrollment is capture-only in v1 — no autopay draft ever originates from customers; until the W7 rails land, this modal (plus payments-module lockbox/import paths) is how EVERY payment enters, autopay-enrolled accounts included.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-CUS-037 | S22 money modals are entry points only: they validate, confirm (IS-6), call the owning service, and write `audit_log` — never financial tables directly. | PROPOSED — B1 + CLAUDE.md module map |
| BR-CUS-059 | Autopay is capture-only in v1: enrollment + method are stored and displayed (US-CUS-003/006), execution begins when the payment rails land (W7), no re-enrollment. The modal's method field records how THIS payment arrived; it never implies or schedules drafting. | CONFIRMED — PO OQ-059 (autopay part) |
| BR-PAY-001 | Apply-to default "Oldest open bill"; options specific/carry/split. | CONFIRMED — A2 §Record payment (cited) |
| BR-PAY-010 | Allocation order (oldest invoice first; within invoice usage+base → taxes → fees last; overpayment → account credit; tenant-configurable). | CONFIRMED — PO R6 / OQ-010 closure (cited) |
| BR-PAY-002 | Recorded payments are append-only; the modal offers no edit — corrections via Reverse (payments). | CONFIRMED — B2 (cited) |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Marcus records $247.30 ACH, apply-to oldest, conf ACH-2028104 | Payments service called once; allocation per BR-PAY-010; balance → $0.00; toast; `audit_log` `payment.recorded` (actor, amount, method) |
| TC-2 | Amount field default; account is autopay-enrolled | Pre-fills the current balance $247.30; editable; the modal renders normally — enrollment never blocks or auto-substitutes manual recording (BR-CUS-059) |
| TC-3 | Partial $100.00 against invoice $145.70 (usage+base 134.60, tax 11.10) | Apply-to oldest → allocation usage+base $100.00; tax remains unpaid last (§7); remaining balance $45.70 |
| TC-4 | Overpayment $300.00 on balance $247.30, apply-to oldest | $247.30 allocated; $52.70 carried as account credit (BR-PAY-010); UI states the carry before confirm |
| TC-5 *(negative)* | Amount 0 or negative | Inline error "> 0" (A2 validation); confirm disabled |
| TC-6 *(negative)* | Double-click on Record payment ✓ | One payment row — idempotent submit (client token + payments idempotency; key scheme human-owned) |
| TC-7 *(isolation)* | Forged request posting a payment to a Lone Star Ridge account from a Brazos Bend session | Rejected; RLS + service tenant check; nothing written |

**4 · Test Data** — A-10432, balance $247.30 (open BL-2607-018204), autopay-enrolled ACH Chase ••••4021 (capture-only, BR-CUS-059). Partial fixture: A-12048 with open invoice $145.70 (usage+base $134.60 + tax $11.10 — the prototype draft-bill split). Payment date Aug 8, 2026. Methods per A2 option set. Actors: Marcus Vega; isolation J. Okafor.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Current balance | S22 | A2 §S22 (read) | `accounts.balance` | numeric USD | computed-display | — |
| Amount | S22 | A2 §S22 | `payments.amount` via payments service (⚠ B1) | numeric(18,6) | user-input | > 0 |
| Payment date | S22 | A2 §S22 (default today; timezone UNKNOWN → tenant Regional settings per IS-8) | `payments.received_at` | date | user-input | ≤ today + tenant TZ |
| Method | S22 | A2 §S22 (5 options) | `payments.method` (lookup per r5 #20) | enum | user-input | active methods; records arrival channel only — never schedules drafting (BR-CUS-059) |
| Confirmation / check # | S22 | A2 §S22 | `payments.reference` | text | user-input | optional |
| Apply to | S22 | A2 §S22 (4 options) | allocation instruction → `allocations` rows (⚠ payments, BR-PAY-010) | enum (+bill ref) | user-input | specific ⇒ bill picker |
| Memo | S22 | A2 §S22 | `payments.memo` | text | user-input | optional |
| Audit | — | CLAUDE.md #7 | `audit_log` `payment.recorded` | jsonb | system-derived | every money action |

**6 · Acceptance**
- Given a valid payment, When confirmed, Then exactly one payment + its allocations exist (owned by payments), balance updates, And an audit row names the actor.
- Given partial/overpayment, Then allocation follows BR-PAY-010 exactly and the UI states carry-as-credit before confirm.
- Given an autopay-enrolled account, Then manual recording works unchanged and nothing auto-drafts (BR-CUS-059).
- Given a forged cross-tenant post, Then nothing is written.

**7 · Finance Calculation** — Allocation per **BR-PAY-010 (CONFIRMED)**, computed by payments; account-side worked example for TC-3 (GT-7 fixture shape): invoice $145.70 = usage+base 134.60 + tax 11.10; payment 100.00 → usage+base gets min(100.00, 134.60) = **100.00**, taxes 0, fees 0; invoice open remainder 45.70; account balance 45.70. Overpayment (TC-4): 300.00 − 247.30 = **52.70** carried as credit, auto-applies to the next invoice. GT ref: GT-7.

**8 · Open Questions** — None — OQ-059 CLOSED(→BR-CUS-059/060): autopay capture-only, execution begins W7; bill-delivery-day dropped. Manual recording is unaffected either way.

---
id: US-CUS-013
epic: EP-CUS-04
module: customers
screens: [S22, S21]
wave: 4
status: draft
blocked_by: []
depends_on: [US-CUS-008, US-CUS-010]
journeys: [J6]
rules: [BR-CUS-037, BR-CUS-038, BR-BIL-004, BR-BIL-009]
golden_tests: [GT-6]
finance_calc: confirmed
---
### US-CUS-013 — Adjust & Issue credit modals

**1 · Details** — As a Billing Clerk (request) with Owner/Finance approval (A4), I want the Adjust modal — Direction (Credit reduces / Debit increases), Amount, Reason code (Billing error correction / Meter error / Leak credit / Goodwill credit / Dispute resolution / Waive late fee), Apply to bill (latest / open balance), GL account, "Requires supervisor approval" (default on) — and the Issue credit modal — Credit amount, Reason (Goodwill / Promotional / Dispute resolution / Referral / Service outage credit), Apply (next bill / current open bill / refund to customer), Memo visible on bill, Notify by email — so that balance corrections are reasoned, approved, GL-coded and audited. Both post through billing/payments services as NEW rows; issued invoices are never edited (BR-BIL-004 — J6 is the correction journey). Entry: S21 actions. Exit: confirm → (approval queue if flagged) → toast → S21.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-CUS-037 | *(shared)* entry-point-only; adjustment/credit rows are billing/payments-owned; ledger effects post in W5 via the posting service only. | PROPOSED — B1 + CLAUDE.md #5 |
| BR-CUS-038 | "Requires supervisor approval" defaults ON; approver = Owner/Finance per A2 note, mapping to System Admin / Executive in the confirmed 3-role model (Billing Clerk = request only, A4 addendum). Approval is server-enforced. | PROPOSED — A2 §Adjust + A4 addendum |
| BR-BIL-004 | Corrections are NEW rows referencing the original (credit-note pattern, GT-6); no UPDATE on issued invoices. | CONFIRMED — B2/CLAUDE.md #4 (cited) |
| BR-BIL-009 | Before posting, the UI states the consequence in plain language (balance effect, approval need, ledger entries). | CONFIRMED — PO R6 / OQ-012 closure (cited) |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Marcus posts Adjust: Credit $42.50, reason Leak credit, apply to BL-2606-018091, GL 4200 Water Revenue, approval on | Request enters approval queue; Priya (Executive) approves → adjustment row −42.50 referencing the bill; balance falls; consequence message shown pre-confirm; audit `adjustment.posted` + `adjustment.approved` |
| TC-2 | Issue credit $15.00 Goodwill, apply next bill, memo "Thank you for 2 years of service", notify on | Credit row created; applies to next issued invoice; customer email queued (A19 "Credit issued" — memo is the customer-visible reason); audit `credit.issued` |
| TC-3 | Direction Debit $18.20, reason Billing error correction | Balance increases; same approval/audit path — debits are never silent |
| TC-4 | Credit apply = "Refund to customer" | Routes a refund instruction to payments `refunds` (B2 r2); no cash movement from customers. **AMENDED PO 2026-08-12: payments applies the two refund rulings before any money leaves — (a) a customer owing on ANOTHER of their accounts is OFFSET FIRST and the refund is what remains (OQ-135, *"offset first"*: $57.13 credit against $948.20 overdue pays nothing, BR-CUS-054), and (b) a refund may be raised against the CREDIT BALANCE rather than one payment, with the clerk choosing refund or credit (OQ-167: $40.00 + $17.13 = $57.13). Customers still writes neither table** |
| TC-5 *(negative)* | Marcus (Clerk) attempts to bypass by unticking approval | Checkbox editable by Owner/Finance only (A2 note); server enforces regardless of UI state (BR-CUS-038) |
| TC-6 *(negative)* | Amount 0 / blank reason | Inline errors; confirm disabled (A2: amount > 0, reason required) |
| TC-7 *(isolation)* | Approval queue viewed by Lone Star Ridge Executive | Contains only Lone Star Ridge requests (RLS) |

**4 · Test Data** — A-10432: leak-credit fixture per prototype (ADJ-142, −$42.50, BL-2606-018091, approved by a supervisor); goodwill credit $15.00; debit correction $18.20 (ADJ-089 shape). GL options per A2 (4100 Electric Revenue / 4200 Water Revenue / 4910 Penalties — illustrative subset; real list = tenant ledger accounts). Actors: Marcus Vega (request), Priya Menon (approve), Dana Whitfield (approve alt); isolation J. Okafor.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Direction | S22 Adjust | A2 §Adjust | adjustment sign (credit −/debit +) on the billing-owned adjustment row (⚠ B1) | enum | user-input | required |
| Amount | S22 Adjust / Credit | A2 §Adjust · prototype Credit modal | adjustment/credit `amount` numeric(18,6) | numeric USD | user-input | > 0 |
| Reason code | S22 Adjust / Credit | A2 (6 options) / prototype (5 options) | reason lookup (tenant-extensible per BR-TEN-036 pattern) | enum | user-input | required |
| Apply to bill / Apply | S22 | A2 (latest/open) · prototype (next/current/refund) | target invoice ref or refund instruction (⚠ billing/payments) | enum + uuid | user-input | refund ⇒ payments path |
| GL account | S22 Adjust | A2 §Adjust | `ledger_accounts` ref on the adjustment (⚠ ledger read; posting via service only, CLAUDE.md #5) | uuid | reference-data | tenant chart |
| Requires approval | S22 Adjust | A2 §Adjust (default on; Owner/Finance only) | approval workflow state | boolean | user-input (gated) | BR-CUS-038 |
| Memo (visible on bill) | S22 Credit | prototype-extracted | credit memo — renders on A19 "Credit issued" email + bill line | text | user-input | customer-visible |
| Notify by email | S22 Credit | prototype-extracted | notification instruction (⚠ notifications) | boolean | user-input | default on |
| Audit | — | CLAUDE.md #7 | `audit_log` rows | jsonb | system-derived | every money action |

**6 · Acceptance**
- Given an approval-flagged adjustment, Then it takes effect only after a System Admin/Executive approves, And both request and approval are audited.
- Given any adjustment/credit, Then the original invoice is untouched and the new row references it (GT-6 pattern).
- Given the consequence message, Then it renders before every confirm.

**7 · Finance Calculation** — Sign convention (A2 CONFIRMED-extracted): Credit reduces balance, Debit increases. Worked example: balance 247.30 → leak credit −42.50 → **204.80**; goodwill credit 15.00 applied next bill reduces the NEXT invoice, not today's balance (apply=next-bill semantics). Correction referencing per GT-6: credit note carries the original invoice ref; original stays immutable. GT ref: GT-6.

**8 · Open Questions** — None.

---
id: US-CUS-014
epic: EP-CUS-04
module: customers
screens: [S22, S21]
wave: 4
status: draft
blocked_by: []
depends_on: [US-CUS-008, US-CUS-010]
journeys: []
rules: [BR-CUS-037, BR-CUS-040]
golden_tests: []
finance_calc: none
---
### US-CUS-014 — Send statement & Print bill modals

**1 · Details** — As a Billing Clerk, I want Send statement — Statement type (Current cycle / Trailing 12 months / Custom range / Move-out final), Period from/to, Delivery (email to the primary contact / mail via print vendor / SMS with link), Preview PDF — and Print bill — Bill picker (issued bills with date + amount), rendered preview, Copies, Include return envelope — so that customers get documents on demand. Rendering uses the tenant's A19 templates (Statement variant; Bill residential/commercial per account type); delivery goes through notifications (tenant mailbox per B7). No data changes (A6: side effects = sends only).

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-CUS-040 | Statement ≠ bill (A19 rule 1): the statement is a dated ledger over the range with the "not a bill, nothing is due" disclaimer; Print bill re-renders an ISSUED invoice verbatim from stored lines — reprints NEVER recompute (BR-BIL-004). | PROPOSED — A19 §1 + templates revision rules 1/6 |
| BR-CUS-037 | *(shared)* modal → notifications/render service; the send is recorded (delivery log), nothing financial changes. | PROPOSED — A6 (S22 statement/print rows: no data changed) |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Send statement, trailing 12 months, email | Statement PDF rendered from the ledger read-model (charges/payments/adjustments/running balance per A19 §1 variant); includes the nothing-is-due disclaimer; email via tenant mailbox; delivery recorded |
| TC-2 | Move-out final statement type on closed A-11208 | Range preset to tenancy dates; renders; available on closed accounts |
| TC-3 | Print bill BL-2607-018204, 2 copies | PDF matches the stored invoice lines exactly ($247.30); commercial account (A-11024) uses the commercial template (PO #, tax ID, per-meter table per A19) |
| TC-4 *(negative)* | Custom range with from > to | Inline error; no render |
| TC-5 *(negative)* | Print bill attempted for the draft BL-2608-018320 | Draft bills not listed — only issued invoices printable (BR-CUS-040/BR-BIL-004) |
| TC-6 *(isolation)* | Render service called with a foreign account id | Denied (tenant check + RLS); no document produced |

**4 · Test Data** — A-10432 (statement range Aug 2025–Aug 2026; bills per EP-CUS-03 fixture; email sarah.miller@example.com). Commercial fixture A-11024 Ridge Coffee Co. (PO #CC-2026-88, Tax ID 74-3820184 per prototype bill sample). Delivery channels: email (tenant mailbox), mail (print vendor seam, B7), SMS link.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Statement type + period | S22 Statement | prototype-extracted (4 types) | ledger read-model params (B2 r2 "Account ledger" derived view) | enum + dates | user-input | from ≤ to |
| Delivery checkboxes | S22 Statement | prototype-extracted | notification instructions (⚠ notifications; channels per A15) | boolean | user-input | ≥ 1 channel |
| Bill picker | S22 Print | prototype-extracted | issued `invoices` for the account (⚠ billing read) | uuid | user-input | issued only |
| Copies / envelope insert | S22 Print | prototype-extracted | print-job params | int/bool | user-input | copies ≥ 1 |
| Rendered documents | both | A19 §1 | template render (statement variant / bill res/com) — no table writes; delivery logged in notifications | pdf | system-derived | template versioned (A19 rule 6) |

**6 · Acceptance**
- Given a statement send, Then the document is a range ledger with the disclaimer, delivered per elections, and logged.
- Given a bill reprint, Then it byte-matches the stored invoice content (no recompute).
- Given a draft bill, Then it is not printable.

**7 · Finance Calculation** — N/A (renders stored amounts; running balance comes from the B2 r2 account-ledger derived view).

**8 · Open Questions** — None.

---
id: US-CUS-015
epic: EP-CUS-04
module: customers
screens: [S22, S21]
wave: 4
status: draft
blocked_by: []
depends_on: [US-CUS-008]
journeys: [J4]
rules: [BR-CUS-035, BR-CUS-037, BR-CUS-039, BR-BIL-007]
golden_tests: []
finance_calc: none
---
### US-CUS-015 — Disconnect notice & Add note modals

**1 · Details** — As a Billing Clerk, I want Send disconnect notice — Notice tier (1st 10-day / 2nd 5-day / Final 48-hr), Service-cut date, Reconnect fee (read-only, from the tenant charge code), Delivery (email+SMS / certified mail / door-hanger via field ops), live preview — and Add note — Title, Body, Pin to top, Visible-to-customer flag — so that collections notices and account annotations happen from the account page. The notice renders A19 §2 tier content and appends to `notice_history` (J4 step 2 contract); notes per BR-CUS-035. Medical-hold accounts are excluded from disconnect notices (A15/A19 tier-3 rule).

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-CUS-039 | Disconnect notice: tier content per A19 §2; certified mail REQUIRED for the final tier (SMS never stands alone — A19 rule 3); reconnect fee displayed from the tenant charge-code catalog, never hardcoded (BR-BIL-007); medical-hold accounts excluded; each send appends `notice_history`. | PROPOSED — A19 §2 + A15 + BR-BIL-007 |
| BR-CUS-035 | *(shared)* Add note writes `account_notes` (US-CUS-011). | PROPOSED-SCHEMA |
| BR-CUS-037 | *(shared)* the notice send routes through notifications; no balance change. | PROPOSED — A6 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Marcus sends 2nd notice on A-11024, cut date Aug 18 2026, email+SMS + certified | Notice rendered per A19 tier-2 ("FINAL REMINDER… reconnect fee of $45.00 applies"); `notice_history` appended; delivery + audit rows |
| TC-2 | Final (48-hr) tier selected | Certified-mail checkbox forced ON and locked (A19 tier 3: certified + regulatory footer + {state_puc_ref}); preview shows the medical/critical-care line |
| TC-3 | Reconnect fee display | Read-only $45.00 from the tenant RECON charge code — changing the charge code changes the display (BR-BIL-007) |
| TC-4 | Add note "Customer called about leak", pinned | Note row per US-CUS-011 TC-3; toast |
| TC-5 *(negative)* | Disconnect notice attempted on medical-hold fixture A-11455 | Blocked with explanation (A15 medical-hold exclusion); nothing sent, nothing appended |
| TC-6 *(negative)* | Final tier with certified mail somehow unticked (forged) | Server rejects — regulatory requirement enforced server-side (IS-6 principle) |
| TC-7 *(isolation)* | Notice history query cross-tenant | Scoped; Lone Star Ridge sees only its own notices (RLS) |

**4 · Test Data** — A-11024 Ridge Coffee Co. (balance $1,842.10, 30d past) for tiers 1–2; A-11340 for final-tier fixture; A-11455 flagged medical hold (exclusion fixture). Reconnect fee: tenant charge code RECON $45.00 (sample value — tenant-configured per BR-BIL-007). Cut date Aug 18, 2026. Actors: Marcus Vega; isolation J. Okafor.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Notice tier | S22 Disconnect | prototype-extracted (3 tiers) | notice instruction → notifications; content per A19 §2 | enum | user-input | tier rules (certified for final) |
| Service-cut date | S22 Disconnect | prototype-extracted | notice token {cut_date} | date | user-input | > today; suppression windows are template/notification rules (A19) |
| Reconnect fee | S22 Disconnect | prototype-extracted ($45.00 read-only) | `charges` catalog lookup (⚠ rating read; BR-BIL-007) | numeric USD | reference-data | display-only |
| Delivery elections | S22 Disconnect | prototype-extracted (3 checkboxes) | notification channels (A15) | boolean | user-input | final ⇒ certified forced |
| Notice history append | — | A6 (S22 row: notice_history) | `notice_history` (⚠ notifications/payments collections model) | row | system-derived | J4 step-2 contract |
| Note fields | S22 Note | prototype-extracted | `account_notes` (US-CUS-011 mapping) | text/bool | user-input | title or body required |

**6 · Acceptance**
- Given a tier selection, Then the rendered notice matches A19 §2 for that tier, the fee comes from the charge catalog, And notice_history gains a row (J4 contract).
- Given medical hold, Then the send is blocked with a reason.
- Given the final tier, Then certified mail cannot be omitted.

**7 · Finance Calculation** — N/A (no amounts computed; the reconnect fee is displayed, applied only on actual reconnection by billing).

**8 · Open Questions** — None (medical-hold flag storage rides A15/notifications pack; display here is read-only).
