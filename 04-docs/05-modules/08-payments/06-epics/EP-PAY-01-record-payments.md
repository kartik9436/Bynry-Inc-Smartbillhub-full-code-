# EP-PAY-01 — Record payments (single entry · purpose model · bulk staged import · S33 ledger · S32 summary)

**Module:** payments · **Wave:** W4 · **Screens:** S22, S32, S33, S35 · **Status:** draft (BR-PAY-001..031 all CONFIRMED — session closed 2026-08-08; schema B2 Addendum r12)

## Scope
**In:** money-IN intake per the ratified model (07-pre-session-model.md §2, Addenda r1/r2): the single-entry form (S22 customers entry point per US-CUS-012 + the S35 Record modal — fields per BR-PAY-022 including the **posting + clearing date pair** BR-PAY-021), the **payment purpose model** bill|deposit|plan_down|prepay (BR-PAY-012, PE-6), the **staged lockbox/CSV bulk import** (BR-PAY-023, PE-5, idempotency BR-PAY-028), the S33 Record-payments ledger with its full IS-5 capability row (BR-PAY-027), and the S32 Summary tab. Method lookup seeds per BR-PAY-026. Payment numbering from the tenant PMT- series (r12 #13).
**Out:** allocation execution (EP-PAY-02, BR-PAY-010) · NSF/reversal/refund/write-off (EP-PAY-03) · outstandings + collections (EP-PAY-04) · plans (EP-PAY-05) · deposit batches + bank rec (EP-PAY-06, W5) · autopay intents + receipts (EP-PAY-07) · webhook intake execution (rails W7 — `payments.webhook_key` dedupe per BR-PAY-003/028 is schema-ready, key mechanics Eng-Lead 🔒) · QuickBooks posting + Field-visit modals on S33/S34 (integrations/field-ops — see pack report) · ledger posting (posting service 🔒, W5).
**Tables (B2 + r12):** `payments` (+ `posted_at`/`cleared_at` r12 #1, `purpose` r12 #2), `payment_import_batches` + `payment_import_rows` (r12 #3), `payment_methods` (lookup per r5 #20), number series PMT- (r12 #13). Accounts/invoices read via service functions only (B1).

## Capability matrix (list screens only — B9 conformance)
| Screen | Search fields | Filters | Default sort | Sortable | Columns default/available | Row actions | Bulk actions | Export |
|---|---|---|---|---|---|---|---|---|
| S33 · Record payments tab | account #, customer, confirmation # | type (payment/credit/adjustment), method, status (processing/cleared/failed/reversed/posted), purpose, posted/cleared date range | posted_at desc | posted_at, cleared_at, amount, account, status | Date · Account · Type · Method · Confirmation · Applied to · Amount · Status / +Posted at, Cleared at, Purpose, Deposit batch, Receipt # (IS-5) | View · Reverse · Reapply · Send receipt · Refund (status-dependent per A5) | Reverse · Reapply to bill · Send receipts (QuickBooks post = integrations, out) | CSV (IS-9) |

*(S32 is a KPI dashboard, S22/S35 are modals — no capability rows; IS-6 confirm/toast/audit governs the modals.)*

## Stories

---
id: US-PAY-001
epic: EP-PAY-01
module: payments
screens: [S22, S35, S33]
wave: 4
status: draft
blocked_by: []
depends_on: [US-BIL-005, US-CUS-012]
journeys: [J2]
rules: [BR-PAY-021, BR-PAY-022, BR-PAY-026, BR-PAY-002, BR-PAY-028]
golden_tests: []
finance_calc: confirmed
---
### US-PAY-001 — Single payment entry: posting date + clearing date, always both

**1 · Details** — As a Billing Clerk, I want to record one payment — account → amount, method, **posting date + clearing date**, reference (check/confirmation #), allocation choice (default rules; specific/carry/split per BR-PAY-001) — per BR-PAY-022, with the two dates ALWAYS separate per BR-PAY-021: **posting = when the record is posted to the system; clearing = when money is actually received. Billing consumes the posting date (a payment posted by the due date is on-time even if it clears later); NSF/failure hangs off clearing; bank rec matches on clearing.** The A2 §S22 single "Payment date" field is superseded by the two-date pair (PO ruling 2026-08-08). Entry: S21/S22 Record payment (US-CUS-012 owns that form + audit trigger; this story owns the payments service + the S35 Record modal). Exit: `payments` row (PMT- number minted, r12 #13), status per A5 (`processing` until cleared; `cleared` when cleared_at set), allocation instruction handed to US-PAY-006, receipt queued on clearing (US-PAY-025). Idempotent submit (client token; key mechanics Eng-Lead 🔒 per BR-PAY-028). Every recording writes `audit_log` (CLAUDE.md #7).

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-PAY-021 | Posting date ≠ clearing date — always both; billing consumes POSTING (on-time = posted_at ≤ due date even if cleared later); NSF/failure hangs off clearing; bank rec matches on clearing. | CONFIRMED — PO explicit ruling, 2026-08-08 (r12 #1) |
| BR-PAY-022 | Single-entry form: account → amount, method, posting+clearing dates, reference, allocation choice (default rules; specific/carry/split). | CONFIRMED — PO Lane B-1, 2026-08-08 |
| BR-PAY-026 | Method seeds: cash, check, card, ACH, wire, money order — tenant-extensible lookup (r5 #20 enum→lookup). The prototype's "Lockbox" method option is superseded: lockbox is an intake CHANNEL (BR-PAY-023); the row's method comes from the instrument. | CONFIRMED — PO Lane B-5, 2026-08-08 (channel/method reading derived from BR-PAY-023, flagged in pack report) |
| BR-PAY-002 | Payments append-only once out of processing; corrections are reversing rows (US-PAY-010), never edits. | CONFIRMED — B2 §payments, CLAUDE.md #4 |
| BR-PAY-028 | Submit idempotency (client token) + webhook_key UNIQUE for future rails; key mechanics Eng-Lead 🔒. | CONFIRMED — PO Lane B-7, 2026-08-08 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | PE-1: Marcus records check #8842, $292.87, ACC-1042, posted Aug 8 + cleared Aug 8, apply-to oldest | `payments` row PMT-2608-000412, method check, posted_at = cleared_at = Aug 8, status cleared; allocation instruction → US-PAY-006 (§7); receipt queued (US-PAY-025); audit `payment.recorded` |
| TC-2 *(posting vs clearing)* | Check posted **Aug 22** (= due date of BL-2608-018410), cleared **Aug 25** | Row: posted_at Aug 22, cleared_at Aug 25; billing's late-fee candidate run for ACC-1042 sees the payment as ON-TIME (posted_at ≤ due date, BR-PAY-021) — no late fee; bank rec (W5) matches this money on Aug 25 |
| TC-3 | Wire and money-order methods; Alex adds tenant method "Bill-pay portal" in Lookup tables | All six seeds selectable (BR-PAY-026); new tenant lookup value usable immediately; nothing hardcoded |
| TC-4 | Allocation choice = Specific bill (BL-2607-018311) / Carry as credit / Split | Instruction stored verbatim and passed to the allocation engine (US-PAY-006); specific ⇒ bill picker required. **AMENDED PO 2026-08-12 (OQ-154, *"Build the open-balance read"*): the picker must show each bill's OPEN balance, not its ISSUED total** — the two differ the moment anything has been paid, and until this read existed *"apply this payment to a specific bill"* was a confirmed staff option with nothing behind it |
| TC-5 *(negative)* | Amount 0 / negative; account id blank | Inline errors (A2 "> 0"); confirm disabled; no row |
| TC-6 *(negative)* | Double-click Record ✓; later, a direct UPDATE on the cleared row | One row only (idempotent submit, BR-PAY-028); UPDATE rejected by append-only trigger (BR-PAY-002, B2 §3) |
| TC-7 *(isolation)* | J. Okafor (Lone Star Ridge) posts a payment naming a Brazos Bend account id | Rejected (RLS + service tenant check); nothing written; Lone Star Ridge PMT- series untouched |

**4 · Test Data** — Tenant **Brazos Bend MUD**. ACC-1042 (WE-1 fixture): open BL-2607-018311 $45.00 (due Jul 22) + BL-2608-018410 $247.87 (due Aug 22; usage+base 221.90 · taxes 20.97 · late 5.00). PE-1 payment: check #8842, $292.87, Aug 8, 2026. Two-date fixture: posted Aug 22 / cleared Aug 25. Methods: tenant lookup seeded cash, check, card, ACH, wire, money order. Number series `PMT-{YYMM}-{seq}` → PMT-2608-000412. Actors: Marcus Vega (Billing Clerk), Alex Reed (System Admin). Isolation: J. Okafor, Lone Star Ridge Co-op.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Account | S22/S35 | A2 §S22 | `payments.account_id` | uuid | user-input | active tenant account |
| Amount | S22/S35 | A2 §S22 | `payments.amount` | numeric(18,6) USD | user-input | > 0 |
| Posting date | S22/S35 | BR-PAY-021/022 (supersedes A2 single "Payment date") · **PO 2026-08-12 (OQ-153)** | `payments.posted_at` (r12 #1) | date/ts | user-input | defaults today (tenant TZ per IS-8); **a TYPED date becomes MIDNIGHT IN THE UTILITY'S OWN TIMEZONE** (*"The utility's own timezone at midnigh"* — 22 Aug typed in Houston stores as 22 Aug 00:00 Central and reads as 22 August to everyone in that utility). ⚠ **Blocked by DEF-082 — the company-settings timezone dropdown does not work, so the setting this depends on cannot be chosen today.** For the LATE-FEE test billing reads the CLEARING date (BR-BIL-071, PO 2026-08-11) |
| Clearing date | S22/S35 | BR-PAY-021/022 | `payments.cleared_at` (r12 #1) | date/ts | user-input | blank = still processing; NSF/bank-rec hang off this date |
| Method | S22/S35 | A2 §S22 + BR-PAY-026 | `payments.method` (lookup, r5 #20) | lookup | user-input | active tenant methods; six seeds |
| Confirmation / check # | S22/S35 | A2 §S22 | `payments.confirmation` | text | user-input | optional |
| Apply to | S22/S35 | A2 §S22 (4 options) + BR-PAY-001 | allocation instruction → US-PAY-006 (`allocations`) | enum(+bill ref) | user-input | default oldest open bill; specific ⇒ picker |
| Per-bill OPEN balance (picker) | S22/S35 | **BR-PAY-012 / BR-PAY-001 as amended (PO 2026-08-12, OQ-154)** | open-balance read-model: issued total − net allocations per invoice (service fn, B1) — **the product could previously serve only the ISSUED total** | numeric(18,6) | system-derived | required by the *specific bill* option; never the issued total once anything has been paid |
| Memo | S22/S35 | A2 §S22 | `payments.memo` | text | user-input | optional |
| Payment number | S33 | r12 #13 | `payments` number from tenant PMT- series (BR-TEN-035 mechanism) | text | system-derived | minted at record, unique per tenant |
| Status | S33 | A5 §Payment (B2 `payment_status`) | `payments.status` (processing→cleared; failed/reversed per EP-PAY-03) | enum | system-derived | cleared requires cleared_at |
| Submit idempotency | — | BR-PAY-028 | client token + unique key 🔒 Eng-Lead | text | system-derived | duplicate submit → single row |
| Audit | — | CLAUDE.md #7 | `audit_log` `payment.recorded` | jsonb | system-derived | append-only |

**6 · Acceptance**
- Given a valid entry, When confirmed, Then exactly one `payments` row exists with BOTH dates stored, a PMT- number, and an audit row naming the actor.
- Given posted_at ≤ due date and cleared_at after it, Then billing evaluates the payment on-time (BR-PAY-021) — demoable via the late-fee candidate preview.
- Given a cleared row, Then no UPDATE/DELETE path exists — corrections are reversing rows.
- Given a cross-tenant post or a double submit, Then nothing leaks and nothing duplicates.

**7 · Finance Calculation** — CONFIRMED (PE-1, model §13 verbatim; allocation order BR-PAY-010). Check $292.87 settles ACC-1042's open items oldest-invoice-first: BL-2607-018311 **45.00** first, then BL-2608-018410 **247.87** (within-invoice order usage+base 221.90 → taxes 20.97 → fees 5.00 last — **the within-bill order is now the shipped DEFAULT of a tenant setting, PO 2026-08-12, OQ-189 → BR-PAY-010; the figures are unchanged**); account balance **0.00**. On-time test: posted_at Aug 22 ≤ due Aug 22 → on-time regardless of cleared_at Aug 25 (BR-PAY-021 — **and for the LATE-FEE test billing reads the CLEARING date, BR-BIL-071**). GT ref: GT-7 (allocation fixture family).

**8 · Open Questions** — **None open. Two closed 2026-08-12 (PO):** **OQ-154** *"Build the open-balance read"* — the *specific bill* option needs each bill's OPEN balance and the product could serve only the ISSUED total, which is a different number the moment anything has been paid. · **OQ-153** *"The utility's own timezone at midnigh"* — a typed posting date becomes midnight in the utility's own timezone (a Houston clerk typing 22 August stores 22 Aug 00:00 Central). ⚠ **Reported with it and still true: the PO said in the same breath *"you did not fix time zone drop down in company settings"* (DEF-082), so the setting this ruling depends on cannot be chosen by a utility today — the rule is ruled and unimplementable.**

---
id: US-PAY-002
epic: EP-PAY-01
module: payments
screens: [S22, S35, S33]
wave: 4
status: draft
blocked_by: []
depends_on: [US-PAY-001, US-BIL-010, US-CUS-007]
journeys: [J2]
rules: [BR-PAY-012, BR-PAY-010]
golden_tests: []
finance_calc: confirmed
---
### US-PAY-002 — Payment purpose: bill · deposit · plan-down · prepay (money with no open bill)

**1 · Details** — As a Billing Clerk, I want every payment to carry a **purpose** — `bill | deposit | plan_down | prepay` (BR-PAY-012, r12 #2, default `bill`) — so that money with no open bill lands correctly: a **pre-move-in deposit payment** (purpose deposit) links to the account's deposit position and **satisfies the first-bill deposit line when it issues** (BR-BIL-012 line, US-BIL-010); a **plan down payment** (purpose plan_down) links to its payment plan (US-PAY-017); a **customer prepay** (purpose prepay) sits as account credit and auto-applies per allocation order (BR-PAY-010, US-PAY-007). Any unapplied remainder on ANY purpose becomes account credit (BR-PAY-012). Entry: purpose select on S22/S35 Record (model §4). Exit: `payments.purpose` stored; linkage per purpose; S33 shows the purpose column (IS-5).

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-PAY-012 | Every payment carries a purpose bill\|deposit\|plan_down\|prepay; unapplied → account credit; deposit-purpose satisfies the first-bill deposit line at issue; plan-down links to its plan. | CONFIRMED — PO PA-1, 2026-08-08 (r12 #2) |
| BR-PAY-010 | Prepay/unapplied credit auto-applies to the next bill in allocation order; refundable on request (BR-CUS-061 pattern). | CONFIRMED — PO Q&A R6 (OQ-010) |
| BR-BIL-012 *(consumed)* | First bill carries the deposit line (non-taxable → deposit liability, never revenue); this story only satisfies it. | CONFIRMED — billing pack (cited) |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | PE-6: pre-move-in deposit $150.00 (purpose deposit) for ACC-1350, no bill exists yet | Payment recorded, linked to the deposit position (customers-owned read, `accounts.deposit_on_file` family); no allocation to any invoice; account credit NOT created — the money is held against the deposit line |
| TC-2 | ACC-1350's first bill issues (US-BIL-010) with deposit line $150.00 | The deposit-purpose payment satisfies the deposit line at issue (BR-PAY-012); the line shows paid; usage/base/CONN portions remain due normally |
| TC-3 | Plan down payment $50.00 (purpose plan_down) for ACC-1310's proposed plan | Payment links to the plan (US-PAY-017, PE-13 down = 50.00); plan schedule spreads the remainder; S33 purpose column shows plan-down |
| TC-4 | Prepay $200.00 (purpose prepay) on ACC-1090 with zero open bills | Carried as account credit; auto-applies to the account's next issued bill (BR-PAY-010); refundable on request via US-PAY-011 |
| TC-5 *(negative)* | Purpose deposit on an account with no deposit position; purpose plan_down with no plan in proposed/agreement_sent/active | Rejected with a named linkage error; no orphan purpose links |
| TC-6 *(isolation)* | Lone Star Ridge deposit-purpose payment | Links only to its own deposit positions/plans; Brazos Bend plan ids 404 (RLS) |

**4 · Test Data** — ACC-1350 (move-in Sep 1, 2026; plan_deposit_rules Residential $150.00 — US-BIL-010 fixture family). ACC-1310 plan per PE-13 (balance 267.30, down 50.00). ACC-1090 prepay $200.00. Actors: Marcus Vega. Isolation: J. Okafor, Lone Star Ridge.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Purpose | S22/S35 | BR-PAY-012 (model §4) | `payments.purpose` enum bill\|deposit\|plan_down\|prepay (r12 #2) | enum | user-input | default bill |
| Deposit linkage | — | BR-PAY-012 | deposit position (customers-owned read: `accounts.deposit_on_file` + `deposit_received_on`, r9 #5); satisfaction recorded against the first-bill deposit line | uuid/numeric | system-derived | requires a deposit position |
| Plan-down linkage | — | BR-PAY-012 | `payment_plans` reference on the payment (r12 family; exact column 🔒 r12 #17) | uuid | system-derived | plan must exist and be live-track |
| Prepay → credit | — | BR-PAY-012 + BR-PAY-010 | unallocated credit read-model over `payments` (carried credit, BR-CUS-061 pattern) | numeric(18,6) | system-derived | auto-applies next bill |
| Purpose column | S33 | BR-PAY-027 (IS-5 available column) | `payments.purpose` | enum | computed-display | filterable |
| Audit | — | CLAUDE.md #7 | `audit_log` `payment.recorded` (purpose in payload) | jsonb | system-derived | append-only |

**6 · Acceptance**
- Given each of the four purposes, Then the recorded payment carries the right linkage (deposit position / plan / credit / bill allocation) and S33 can filter by purpose.
- Given the first bill issuing after a deposit-purpose payment, Then its deposit line is satisfied without staff action.
- Given an unapplied remainder on any purpose, Then it sits as account credit per BR-PAY-012.

**7 · Finance Calculation** — CONFIRMED (PE-6, model §4/§13). Deposit purpose: $150.00 held against the deposit position → offsets the first bill's $150.00 deposit line at issue (no revenue, deposit-liability GL per BR-BIL-012 — posting service 🔒). Plan-down: 50.00 reduces the PE-13 spread (267.30 − 50 → schedule 5 × 36.22 + 36.20, figures owned by US-PAY-017). Prepay: 200.00 carried credit, applies per BR-PAY-010.

**8 · Open Questions** — None.

**9 · Build state (2026-08-15, payments visible-half lane)** — **ALL FOUR PURPOSES RECORD.** `apps/payments/purposes.py` resolves each one's linkage before anything is written; `payments.plan_id` (migration 0009) closes field-map **P-12**; a deposit posts DR undeposited / CR **2000 deposit liability** and is excluded from the credit position. ⚠ **TWO GAPS, BOTH ON THE DEPOSIT HALF AND BOTH ON EVERY RESULT:** nothing calls `credit.deposit_payments_for_account`, so TC-2's satisfaction of BR-BIL-012's first-bill deposit line does not happen (billing's write, US-BIL-010); and `apps.rating.selectors.deposit_requirement_for_account` is unpublished, so TC-5's refusal on an account with NO deposit position cannot fire — recordings carry `deposit_requirement_not_checked`. The S22/S35 purpose picker is **not built**: the form still sends `bill` only.

---
id: US-PAY-003
epic: EP-PAY-01
module: payments
screens: [S35, S33]
wave: 4
status: draft
blocked_by: []
depends_on: [US-PAY-001, US-PAY-006]
journeys: [J2]
rules: [BR-PAY-023, BR-PAY-028, BR-PAY-003, BR-PAY-021]
golden_tests: []
finance_calc: confirmed
---
### US-PAY-003 — Bulk lockbox/CSV: staged import (batch → validate → preview → commit)

**1 · Details** — As a Billing Clerk, I want bulk payments in via the ratified staged pattern (BR-PAY-023, the read/account-import standard): upload lockbox/CSV file (S35 Lockbox modal — prototype: "Chase BAI2 · BofA CSV supported") → `payment_import_batches` row with **file + SHA-256 compliance stamp** → per-row validation into `payment_import_rows` (account match by account # → invoice # → **name+amount heuristic FLAGGED FOR REVIEW — never auto-guessed silently**) → preview counts (matched / needs review / errors) → commit posts the matched rows as payments (each allocated per BR-PAY-010 by US-PAY-006), per-row errors skip with a report. **Idempotency = file + tags** (BR-PAY-028, OQ-044 model — re-importing the same file blocks with who/when/link). Date semantics per BR-PAY-021: posting = the import commit (record enters the system); clearing = the bank receipt date carried in the file. ⚠ **SUPERSEDED IN PART 2026-08-11 (PO ruling, OQ-131 CLOSED → BR-BIL-071): the LATE-FEE test reads the CLEARING date, never this posting date.** Both dates are still recorded exactly as written; what is superseded is any reading in which the COMMIT MOMENT decides whether a customer was late. Worked: banked 20 Aug, bill due 22 Aug, file imported 25 Aug, run 5 Sep → NOT late, no fee. BR-PAY-033 (*imports default the posting date from the file data*) is the rule that WON that contradiction. Entry: S33 header "Import lockbox". Exit: committed payments on S33 with the batch reference; review rows worked singly. Webhook intake (rails, W7) rides the same dedupe family via `payments.webhook_key` UNIQUE (BR-PAY-003) — schema-ready, no dispatch v1.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-PAY-023 | Bulk = staged import: batch → per-row validation → preview → commit; file+SHA-256 stamp; idempotency file+tags; account-match heuristics flag for review, never auto-guess silently. | CONFIRMED — PO Lane B-2, 2026-08-08 (r12 #3) |
| BR-PAY-028 | Import idempotency = file+tags; webhook_key UNIQUE for rails; key mechanics Eng-Lead 🔒. | CONFIRMED — PO Lane B-7, 2026-08-08 |
| BR-PAY-003 | Inbound payment webhooks dedupe on `webhook_key` UNIQUE (double delivery = one row) — rails-deferred, schema present. | CONFIRMED — B2 §payments |
| BR-PAY-021 | Import rows: posted_at = commit into the system; cleared_at = bank receipt date from the file. ⚠ **The *"on-time interplay for mail arrivals"* this row flagged is now RULED (PO 2026-08-11, OQ-131 CLOSED → BR-BIL-071): the late-fee test reads `cleared_at`, the ACTUAL date the money arrived, never `posted_at`.** The two column definitions here are unchanged. | CONFIRMED (the definitions) — **the on-time interplay it flagged is CLOSED 2026-08-11 → BR-BIL-071** |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | PE-5: Priya imports a 40-row lockbox file | Batch stamped file+SHA-256; validation: 38 rows clean, **2 errors** (no account match); preview shows the counts; commit posts 38 payments, 2 skipped with a per-row error report — "38 committed · 2 failed" |
| TC-2 | Row matching ladder | Account-# rows auto-match; an invoice-# row resolves to its account; a name+amount-only row lands in **needs review** — it NEVER auto-posts (BR-PAY-023); reviewer assigns the account, row commits singly |
| TC-3 *(posting vs clearing)* ⚠ **SUPERSEDED IN PART 2026-08-11 (PO ruling, OQ-131 → BR-BIL-071)** | File carries bank receipt date Aug 6; commit happens Aug 8 | Committed rows: cleared_at Aug 6 (money received), posted_at Aug 8 (record entered) — BR-PAY-021 definitions; bank rec (W5) matches on Aug 6. **WHAT STANDS:** both dates are stored, exactly as above. **WHAT IS SUPERSEDED:** this case was the CONFIRMED source of *"the posting date at import is the commit moment"*, and it contradicted BR-PAY-033 (*imports default the posting date from the file data*). The PO ruled on 2026-08-11 that the **ACTUAL date the money arrived is authoritative** for lateness — *"you llook at actual date for late fees not posting date; in your example acutla date will be 20 AUg and well within due date"* — so **BR-PAY-033's reading wins and this one loses**, and the loss is a documentation fix rather than a re-ruling. Consequence for THIS case: an Aug-6 bank receipt against a bill due Aug 7 is ON TIME even though the commit is Aug 8, and no late fee is assessed (BR-BIL-071). A test case asserting that the commit moment decides on-time would now be asserting the rejected reading. |
| TC-4 | Each committed row allocates | Allocation per BR-PAY-010 through the engine (US-PAY-006); overpaid rows carry credit; S33 rows carry the import-batch reference |
| TC-5 *(negative)* | The same file re-uploaded next morning (same file+tags) | Blocked by import idempotency — message names the original batch, who, when, link (BR-PAY-028); zero new rows |
| TC-6 *(negative)* | Malformed row (non-numeric amount / unparseable date) | Row errors at validation, listed in the report; batch still previews; commit never ingests the bad row |
| TC-7 *(isolation)* | Lone Star Ridge import naming Brazos Bend account numbers | Those rows fail account-match (no cross-tenant resolution, RLS); its batch sees only its own accounts |

**4 · Test Data** — PE-5 file: `lockbox_2026-08-06_chase.csv`, 40 rows, bank receipt date Aug 6, 2026; 2 error rows (accounts "A-99999", "A-88888" nonexistent); 1 heuristic row ("S MILLER" + $247.87 → review). SHA-256 stamp recorded. Committed example rows: A-10432/BL-2607-018204 check $247.30; A-11024 ACH $500.00. Actors: Priya Menon. Isolation: J. Okafor, Lone Star Ridge.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| File + format | S35 Lockbox | prototype-extracted (BAI2/CSV) | `payment_import_batches` (file name, SHA-256, tags — r12 #3) | file/text | user-input | supported formats; ≤ cap per import standard |
| Import idempotency | — | BR-PAY-028 | batch unique on file+tags (mechanics 🔒 r12 #17) | text | system-derived | duplicate → block who/when/link |
| Row (account ref, invoice ref, name, amount, dates, check #) | S35 preview | BR-PAY-023 | `payment_import_rows` (r12 #3) | per-column | integration | per-row validation states clean\|review\|error |
| Match ladder result | S35 preview | BR-PAY-023 (model §2) | row match status + matched `account_id` | enum/uuid | system-derived | heuristic ⇒ review, never silent |
| Preview counts | S35 | prototype-extracted (Rows/Auto-matched/Needs review/Errors) | computed over rows | counts | computed-display | ties to rows exactly |
| Commit → payments | S33 | BR-PAY-023 · **BR-BIL-071 (2026-08-11)** | `payments` rows (posted_at = commit, cleared_at = file bank date — r12 #1) + import-batch ref; **`cleared_at` is the date the LATE-FEE test reads (BR-BIL-071), so it is never left null when the file carries one** | rows | system-derived | errors skip w/ report |
| Auto-post toggle | S35 | prototype-extracted ("Auto-post the N matched payments") | commit scope flag on the batch | boolean | user-input | review rows always excluded |
| Send receipts toggle | S35 | prototype-extracted + BR-PAY-024 | receipt queue rows on clearing (US-PAY-025) | boolean | user-input | queue-write only (BR-NOT-005) |
| Webhook dedupe (rails) | — | BR-PAY-003 | `payments.webhook_key` UNIQUE (tenant, key) | text | integration | schema-ready; dispatch W7 |
| Import audit | — | CLAUDE.md #7 | `audit_log` `payment_import.committed` (batch, counts) | jsonb | system-derived | append-only |

**6 · Acceptance**
- Given the PE-5 file, Then staging, preview counts, commit results and the error report match TC-1 exactly, and the batch carries the file + SHA-256 stamp.
- Given a heuristic-only match, Then the row waits for review — nothing auto-guesses silently.
- Given a duplicate file+tags, Then the import blocks with who/when/link and writes nothing.
- Given committed rows, Then both BR-PAY-021 dates are populated per TC-3 and every payment allocated per BR-PAY-010. **And (2026-08-11, BR-BIL-071): given a committed row whose `cleared_at` falls on or before an open bill's due date, Then that bill is NOT late and no late fee is assessed, however much later the commit happened.**

**7 · Finance Calculation** — CONFIRMED (PE-5, model §13: 40-row import, 2 errors → 38 committed). Per-row money math is the allocation engine's (US-PAY-006 §7); the batch itself sums nothing money-bearing beyond Σ committed amounts = Σ row amounts (display).

**8 · Open Questions** — None.

---
id: US-PAY-004
epic: EP-PAY-01
module: payments
screens: [S33]
wave: 4
status: draft
blocked_by: []
depends_on: [US-PAY-001, US-PAY-003, US-SHL-006]
journeys: [J2]
rules: [BR-PAY-027, BR-PAY-021, BR-PAY-002]
golden_tests: []
finance_calc: none
---
### US-PAY-004 — S33 Record-payments ledger: full IS-5 capability row

**1 · Details** — As a Billing Clerk, I want the S33 ledger of payments/credits/adjustments with the full IS-5 capability row (BR-PAY-027): search (account #, customer, confirmation #), type/method/status/purpose filters + posted/cleared date ranges, dynamic columns (defaults per the prototype table: Date · Account · Type · Method · Confirmation · Applied to · Amount · Status; available extras **Posted at · Cleared at** (BR-PAY-021 — both dates always visible on demand) · Purpose · Deposit batch · Receipt #), server pagination/sort (IS-2/3/4), status-dependent row actions (View / Reverse / Reapply / Send receipt / Refund — prototype action sets per status; Cancel only while processing), bulk toolbar (Reverse · Reapply · Send receipts — selection count + $ total shown per IS-6), CSV export (IS-9). Credits/adjustments render as signed rows (type per B2 `payment_type`); autopay intent rows surface here per BR-PAY-015 (US-PAY-024 display contract). Rows are read-models — the list never mutates money (BR-PAY-002); actions route to their owning stories.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-PAY-027 | S33 = full IS-5 capability row: search / filters / dynamic columns / server pagination. | CONFIRMED — PO Lane B-6, 2026-08-08 |
| BR-PAY-021 | Posted-at and cleared-at are both first-class list columns/filters — staff always see both dates. | CONFIRMED — PO explicit ruling, 2026-08-08 |
| BR-PAY-002 | The list mutates nothing; every action routes to its owning flow (reverse → US-PAY-010, reapply → US-PAY-008, receipt → US-PAY-025, refund → US-PAY-011). | CONFIRMED — B2 §payments |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Default load | Prototype default columns, posted_at desc, server-paginated; totals row per current filter; the TC fixtures from US-PAY-001/003 all present |
| TC-2 | Filter status=processing + method=ACH; search "ACH-2028091" | Row A-11340 $8,240.00 Processing only; actions restricted to View/Cancel (status-dependent set) |
| TC-3 | Column chooser: add Posted at + Cleared at + Purpose | Both BR-PAY-021 dates render per row (Aug 22 / Aug 25 fixture distinguishable); preference persists per user (BR-SHL-013 pattern) |
| TC-4 | Bulk select 3 rows | Toolbar shows "3 selected · $988.70 total" (prototype copy); Reverse/Reapply/Send receipts route to US-PAY-010/008/025 with the selection |
| TC-5 | CSV export under an active filter | IS-9 file: current filter + visible columns, money 2dp; empty result = valid CSV with headers |
| TC-6 *(negative)* | API attempt to PATCH a row via the list endpoint | 405/forbidden — list is read-only (BR-PAY-002); no mutation route exists |
| TC-7 *(isolation)* | J. Okafor lists payments | Lone Star Ridge rows only; a Brazos Bend payment id in the detail URL 404s (RLS) |

**4 · Test Data** — Prototype S33 fixture rows verbatim: A-10432 Miller ACH $247.30 cleared (ACH-2028104, BL-2607-018204) · A-11340 Northwind ACH $8,240.00 processing · A-10891 Chen credit −$42.20 posted · A-11025 Blueprint card $328.60 failed · A-11455 Park check #4021 $100.00 cleared · adjustment ADJ-142 −$42.50. Bulk selection $988.70 (prototype). Actors: Priya Menon. Isolation: J. Okafor.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| List row | S33 | prototype-extracted (table) | read-model over `payments` (+account join via service fn) | rows | computed-display | server page/sort/filter (IS-2/3/4) |
| Type column | S33 | prototype-extracted | `payments.type` (B2 `payment_type` payment\|credit\|adjustment) | enum | computed-display | credits/adjustments signed display |
| Status column | S33 | A5 §Payment | `payments.status` (processing\|cleared\|failed\|reversed\|posted) | enum | computed-display | drives action set |
| Posted at / Cleared at columns | S33 | BR-PAY-021 | `payments.posted_at` / `.cleared_at` (r12 #1) | ts | computed-display | IS-5 available columns + range filters |
| Applied to column | S33 | prototype-extracted | read-model over `allocations` → invoice numbers | text | computed-display | multi-allocation rows list all |
| Purpose / Deposit batch / Receipt # columns | S33 | BR-PAY-012/025/024 | `payments.purpose` · `payments.deposit_batch_id` · receipt ref (RCT- series r12 #13) | enum/uuid/text | computed-display | IS-5 chooser |
| Column set | S33 | IS-5 | per-user preference (shell-owned, BR-SHL-013) | jsonb | user-input | identity column always visible |
| Bulk toolbar | S33 | prototype-extracted + IS-6 | selection → owning flows | — | user-input | count + $ total shown |
| CSV export | S33 | IS-9 | computed file | file | computed-display | filters + visible columns |

**6 · Acceptance**
- Given the capability row, Then search, filters, dynamic columns (incl. both BR-PAY-021 dates), server pagination and CSV export all work as specified.
- Given a row status, Then exactly the status-appropriate actions render, and every action routes to its owning story — the list itself never writes money.
- Given tenants, Then rows, preferences and exports never cross.

**7 · Finance Calculation** — N/A (read-model; money math lives in the owning flows).

**8 · Open Questions** — None.

---
id: US-PAY-005
epic: EP-PAY-01
module: payments
screens: [S32]
wave: 4
status: draft
blocked_by: []
depends_on: [US-PAY-001, US-PAY-013, US-PAY-024]
journeys: [J2, J4]
rules: [BR-PAY-027, BR-PAY-015, BR-PAY-018]
golden_tests: []
finance_calc: none
---
### US-PAY-005 — S32 Payments summary: today, method mix, failed, collections, needs-attention

**1 · Details** — As a Billing Clerk, I want the S32 Summary tab computed live from payments data: **Today** panel (total $ received today by posted_at, count, average — prototype "84 payments · avg $219"), **Method mix · MTD** (per-method % of cleared $), **Failed** panel (failed/NSF rows with route-to actions — Retry routes to a fresh US-PAY-001 recording, Contact opens the account; the prototype's autopay-retry is superseded by BR-PAY-015 capture-only), **Collections** panel (accounts owing, total owed, write-offs YTD from US-PAY-012 — deep link to S34), plus the **autopay-scheduled chip** (capture intents visible on S32/S33 per BR-PAY-015) and the **returned-mail needs-attention chip** (BR-PAY-018, US-PAY-016). Header actions per prototype: Import lockbox / Post adjustment / Issue credit / Record payment (each routes to its owning modal). Every figure ties to the underlying rows — no stored aggregates.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-PAY-027 | Summary figures are read-models over the same data the S33 capability row serves — counts tie to lists exactly. | CONFIRMED — PO Lane B-6 (list family) |
| BR-PAY-015 | Autopay capture intents are visible on S32/S33 ("autopay scheduled"); no charging v1. | CONFIRMED — PO PA-4, 2026-08-08 |
| BR-PAY-018 | Returned-mail needs-attention queue surfaces as an S32 chip. | CONFIRMED — PO PA-7, 2026-08-08 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Aug 8 with the PE-10 receipt set posted | Today panel = Σ posted-today payments; count/average tie to S33 filtered posted_at=today exactly |
| TC-2 | Method mix MTD | Per-method shares computed over cleared $ (cleared_at in month, BR-PAY-021 clearing side); Σ = 100% |
| TC-3 | Failed panel | Failed rows (US-PAY-009/010 outcomes) listed w/ reason; Retry opens Record payment pre-filled (a NEW row — never an edit); no autopay charging path exists (BR-PAY-015) |
| TC-4 | Collections panel + chips | "184 accounts owe $184,320" ties to S34 aggregates (US-PAY-013); write-offs YTD ties to US-PAY-012; autopay-scheduled chip = open intents count (US-PAY-024); returned-mail chip = open bad-address queue (US-PAY-016) |
| TC-5 *(negative)* | Zero payments today / no failures | Panels render zero-states per IS/A18 — no errors, no invented figures |
| TC-6 *(isolation)* | Lone Star Ridge summary | Its rows only; Brazos Bend totals never leak (RLS) |

**4 · Test Data** — Aug 8, 2026 fixtures: PE-10 receipts (checks 292.87 + 142.30 + 36.22; cash 105.36 + 16.42). Failed fixture: A-11025 Blueprint card $328.60 failed. Collections: S34 fixture set (US-PAY-013). Intents: 2 open (US-PAY-024). Returned mail: 1 open (US-PAY-016). Actors: Priya Menon. Isolation: J. Okafor.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Today total / count / avg | S32 | prototype-extracted | computed over `payments` (posted_at = today) | $/counts | computed-display | ties to S33 filter |
| Method mix MTD | S32 | prototype-extracted | computed over `payments` cleared in month by method | % | computed-display | Σ 100% |
| Failed panel rows | S32 | prototype-extracted | read-model `payments.status` failed (+reason from reversal/NSF rows) | rows | computed-display | route-to actions only |
| Collections panel | S32 | prototype-extracted | aggregates over the S34 read-model (US-PAY-013); write-offs YTD over `write_offs` (r12 #11) | $/counts | computed-display | DSO figure = GAP, see field-map discrepancy P-1 (pack report) |
| Autopay-scheduled chip | S32 | BR-PAY-015 | count over `autopay_capture_intents` open (r12 #6) | int | computed-display | ties to US-PAY-024 list |
| Returned-mail chip | S32 | BR-PAY-018 | count over open bad-address queue (r12 #8) | int | computed-display | ties to US-PAY-016 |
| Header actions | S32 | prototype-extracted | route-to modals (US-PAY-001/003, adjust/credit per US-CUS-013 family) | — | user-input | IS-6 |

**6 · Acceptance**
- Given the fixtures, Then every S32 figure ties to its underlying list exactly (no stored aggregates) and each panel deep-links to the owning screen.
- Given BR-PAY-015, Then no retry/charge path exists anywhere on S32 — failures route to manual recording or contact.
- Given tenants, Then summaries never cross.

**7 · Finance Calculation** — N/A (aggregation display only; DSO excluded pending formula — pack-report candidate OQ P-1).

**9 · Build state (2026-08-15, payments visible-half lane)** — **BACKEND COMPLETE, FRONTEND NOT STARTED.** `apps/payments/summary.py` computes all five panels and both chips with no stored aggregate anywhere, and `GET /api/{tenant}/payments/summary?as_of=YYYY-MM-DD` serves them; the collections panel DELEGATES to the S34 read-model so the two can never disagree. ⚠ **THE S32 TAB IS STILL THE PLACEHOLDER PANEL** — `PaymentsPage.tsx` does not call this endpoint, so no human can see any of it (hard-won law 2). The DSO tile is served null with its reason (BR-REP-011 is reports').

**8 · Open Questions** — None.
