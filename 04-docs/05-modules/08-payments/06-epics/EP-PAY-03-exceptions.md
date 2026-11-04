# EP-PAY-03 — Exceptions: NSF · reversals · refunds · write-offs

**Module:** payments · **Wave:** W4 (write-off approval surfaces in Finance, W5 reporting) · **Screens:** S33, S34, S35, S58 · **Status:** draft (BR-PAY-001..031 all CONFIRMED — session closed 2026-08-08; schema B2 Addendum r12)

## Scope
**In:** the money-out-of-band flows per the ratified model (§5/§6, PE-7/8/9): **NSF** (BR-PAY-013 — reversing row, allocations reversed, AR reinstated at the ORIGINAL due date, NSF charge code auto-added, nsf_count + privilege flag), **reversals** with windows + approval + plain-language consequence messaging (BR-PAY-011/030, BR-PAY-002), **refunds** from real credit balances with Admin approval (BR-PAY-014, S58), and **write-offs** initiated in Payments / approved in Finance (BR-PAY-020, r12 #11). All ledger effects are handoffs to the posting service 🔒 (model §12) — payments writes no journal lines (CLAUDE.md #5).
**Out:** bank-rec-triggered NSF detection UI (US-PAY-022 triggers this epic's flows) · card refunds (rails W7 per BR-PAY-014) · collections-agency handoff (prototype checkbox — no ratified rule, see pack report) · billing's void flows (US-BIL-027) · dunning/collection sequence (EP-PAY-04).
**Tables (B2 + r12):** `payments` (reversing rows), `allocations` (reversing rows), `refunds` (+ requested_by/approved_by r12 #5), `write_offs` (r12 #11), `accounts.nsf_count` + privilege flag (r12 #12), NSF charge code via `charges` (rating-owned read, BR-BIL-007).

## Capability matrix (list screens only — B9 conformance)
No new list screens — flows launch from S33/S34 rows and bulk toolbars (US-PAY-004/013 capability rows) and the S58 modal. IS-6 confirm/toast/audit governs every modal.

## Stories

---
id: US-PAY-009
epic: EP-PAY-03
module: payments
screens: [S35, S33, S21]
wave: 4
status: draft
blocked_by: []
depends_on: [US-PAY-001, US-PAY-006]
journeys: [J2, J4]
rules: [BR-PAY-013, BR-PAY-002, BR-PAY-021, BR-BIL-007]
golden_tests: []
finance_calc: confirmed
---
### US-PAY-009 — NSF: reversing row, original due date stands, fee auto-added, privilege flag

**1 · Details** — As a Billing Clerk, when a cleared check bounces I want the NSF flow (BR-PAY-013, PE-7): a **reversing payment row** (append-only, BR-PAY-002), **allocations reversed** (reversing rows, US-PAY-008 mechanics), **AR reinstated at the ORIGINAL due date — the late-fee clock never resets**, the tenant's **NSF charge code auto-added** through the billing charge-line service (BR-BIL-007 — the $30 is the tenant's code amount, never typed or hardcoded), **nsf_count++**, and at N NSFs (default 2, tenant config) the account gets the **cash-only / no-autopay privilege flag**. NSF hangs off the CLEARING side (BR-PAY-021): the trigger is a clearing failure (bank return / US-PAY-022 rec finding / manual mark from S33 Reverse with reason NSF). Ledger: reversing pair + fee line via the posting handoff (model §12) — posting service 🔒. Customer notification rides the outbound queue (BR-NOT-005; channel deferral per rails). Entry: S33 Reverse (reason NSF) / S40 rec resolution. Exit: balance reinstated + fee; flags updated; audit.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-PAY-013 | NSF: reversing row + allocations reversed; AR reinstated at the ORIGINAL due date (late-fee clock never resets); NSF charge code auto-added; nsf_count++; N NSFs (default 2, config) → cash-only/no-autopay flag. | CONFIRMED — PO PA-2, 2026-08-08 (PE-7) |
| BR-PAY-002 | Reversal = new reversing row; the bounced payment row itself is never edited. | CONFIRMED — B2 §payments |
| BR-PAY-021 | NSF/failure hangs off the clearing date, never the posting date. | CONFIRMED — PO explicit ruling, 2026-08-08 |
| BR-BIL-007 *(consumed)* | NSF fee = tenant charge code (UI $30 is a sample); billing owns the fee line write. | CONFIRMED — B4 §NSF (cited) |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | PE-7: ACC-1042's cleared check $292.87 bounces | Reversing payment row **−292.87**; allocation reversing rows re-open BL-2607-018311 (45.00) + BL-2608-018410 (247.87); NSF charge code line **+$30.00** (tenant code) → balance **322.87**; audit `payment.nsf` |
| TC-2 *(posting vs clearing / due-date)* | Original due date Aug 22; NSF lands Sep 2 | Reinstated AR keeps due date **Aug 22** — late-fee grace runs from Aug 22, NOT from the NSF date (BR-PAY-013: the clock never resets); NSF event timestamps off the clearing failure (BR-PAY-021) |
| TC-3 | nsf_count and the privilege flag | ACC-1042 nsf_count 0→1; a second NSF (fixture ACC-1455) hits the tenant N=2 → cash-only/no-autopay flag set; flag visible on the account header; tenant N changed to 3 → third NSF required (config, not constant) |
| TC-4 | Notification | Customer NSF notice row written to the outbound queue (BR-NOT-005) — print v1, email/SMS rows deferred per their rails; `notice_history` appended |
| TC-5 *(negative)* | NSF attempted on a payment that never cleared (still processing) | Rejected — NSF is a clearing failure (BR-PAY-021); processing payments cancel instead (A5 action set) |
| TC-6 *(negative)* | UPDATE attempt on the original or reversing row | Blocked — append-only triggers (BR-PAY-002, B2 §3) |
| TC-7 *(isolation)* | Lone Star Ridge NSF | Its charge codes, counts, flags only; Brazos Bend NSF code invisible (RLS) |

**4 · Test Data** — PE-7 verbatim: ACC-1042, cleared check 292.87 (PE-1 payment PMT-2608-000412), bounce Sep 2, 2026; tenant NSF charge code `NSF` $30.00 (Brazos Bend charge codes, sample per B4); balance after 322.87; original due Aug 22. Privilege fixture: ACC-1455 (Park) second NSF; tenant nsf_privilege_n = 2. Actors: Priya Menon; bank return advice Chase. Isolation: Lone Star Ridge NSF code $25.00.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Reversing payment row | S33 | BR-PAY-013 | `payments` new row (negative/reversing, references original; status reversed on the pair) | numeric(18,6) | system-derived | append-only |
| Allocation reversal | — | BR-PAY-013 | `allocations` reversing rows (US-PAY-008 mechanics) | numeric(18,6) | system-derived | re-opens exactly the allocated amounts |
| Original due date kept | S34/S21 | BR-PAY-013 | reinstated AR reads the invoice's own `invoices.due_date` — nothing rewritten | date | system-derived | late-fee clock from the original date |
| NSF fee line | S21/S30 | BR-PAY-013 + BR-BIL-007 | billing charge-line service → line with `charge_id` = NSF code (B2 `charges`, own GL) | numeric(18,6) | reference-data | amount from the code, never typed |
| nsf_count | S21 header | BR-PAY-013 | `accounts.nsf_count` (r12 #12) | int | system-derived | increments per NSF |
| Privilege flag | S21/S34 | BR-PAY-013 | cash-only/no-autopay flag (r12 #12) | boolean | system-derived | at tenant N (default 2, config) |
| NSF notice | — | BR-PAY-013 + BR-NOT-005 | `outbound_messages` row (r12 #16) + `notice_history` (r12 #7) | rows | system-derived | queue-write only, never inline send |
| Ledger handoff | — | model §12 | posting service 🔒: reversing pair + fee line | rows | system-derived | payments writes no journal lines |
| Audit | — | CLAUDE.md #7 | `audit_log` `payment.nsf` (payment, fee, counts) | jsonb | system-derived | append-only |

**6 · Acceptance**
- Given PE-7, Then the reversing row, reversed allocations, $30 code fee and 322.87 balance all exist exactly, and the reinstated AR keeps its original due date.
- Given N NSFs per tenant config, Then the privilege flag sets — and moves when the config moves.
- Given a processing payment, Then NSF is impossible; given issued rows, edits are impossible.
- Given tenants, Then codes, counts and flags never cross.

**7 · Finance Calculation** — CONFIRMED (PE-7, model §5 verbatim). Cleared check 292.87 bounces → reversing payment row **−292.87** (append-only, BR-PAY-002), allocations reversed, AR reinstated at the ORIGINAL due date (late-fee clock never reset), NSF charge code **+$30** (tenant-config) auto-added → balance **322.87**. Ledger: reversing pair + fee line (posting service 🔒).

**8 · Open Questions** — None.

---
id: US-PAY-010
epic: EP-PAY-03
module: payments
screens: [S35, S33]
wave: 4
status: draft
blocked_by: []
depends_on: [US-PAY-001, US-PAY-006]
journeys: [J2]
rules: [BR-PAY-011, BR-PAY-030, BR-PAY-002]
golden_tests: []
finance_calc: confirmed
---
### US-PAY-010 — Reverse: windows (ACH 60d · card 120d · check unlimited), approval path, consequence messaging

**1 · Details** — As a Billing Clerk, I want the Reverse flow (S35 modal, row or bulk from S33) governed by BR-PAY-011: **windows ACH 60 days · card 120 days · check unlimited (NSF)**; a reversal of a PAID/cross-period payment requires **Admin/Executive approval**; execution is ALWAYS **reversing entries** (payment + allocation reversing rows, BR-PAY-002); and a **plain-language consequence message** renders before confirm (BR-PAY-030): which bills re-open, the balance effect, whether approval is needed, the ledger effect. Modal fields per prototype: reason (Bank chargeback / Data-entry error / Customer dispute / NSF — NSF reason routes to US-PAY-009), memo, "Restore original bill balances" (always on — reversing allocations are not optional; the prototype checkbox is display of the consequence, not a choice), "Notify customers" (queue-write, BR-NOT-005). PE-8: a window-blocked reversal does not dead-end — it routes to the approval path. Entry: S33 Reverse. Exit: reversing rows; balances re-open; audit `payment.reversed`.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-PAY-011 | Reversal windows: ACH 60d, card 120d, check unlimited (NSF); paid/cross-period requires Admin/Executive approval; always reversing entries; consequence message before confirm. | CONFIRMED — PO Q&A R6 (OQ-012 closure) |
| BR-PAY-030 | Plain-language consequence messaging before confirm (extends BR-PAY-011). | CONFIRMED — PO Lane B-9, 2026-08-08 |
| BR-PAY-002 | Reversal = new reversing rows; nothing edited or deleted. | CONFIRMED — B2 §payments |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Reverse an ACH payment on day 30, reason Data-entry error | Within window; consequence message ("BL-2607-018204 re-opens by $247.30; balance rises to …; ledger reversing pair") → confirm → reversing payment + allocation rows; audit `payment.reversed` |
| TC-2 | PE-8: reverse an ACH payment on day 61 | Window blocked → the flow routes to the APPROVAL path (Admin/Executive), not a dead end; on approval the same reversing execution runs; approval recorded (who/when) |
| TC-3 | Cross-period reversal (payment in a closed month) | Approval required regardless of window (BR-PAY-011); reversing entries post to the earliest open period per BR-TEN-038 (posting service 🔒) |
| TC-4 | Check reversal at 8 months, reason NSF | Allowed — check unlimited (NSF); routes through US-PAY-009 (fee + counts) |
| TC-5 | Bulk reverse 3 selected ($988.70) | Per-payment consequence summary; one confirm; per-row reversing pairs; any row needing approval splits into the approval path |
| TC-6 *(negative)* | Staff (non-Admin/Executive) attempts to approve their own blocked reversal | Server-enforced role check rejects; UI state irrelevant |
| TC-7 *(negative)* | API DELETE on a payment row | Blocked — append-only (BR-PAY-002); reversal is the only path |
| TC-8 *(isolation)* | Reversal request naming a Lone Star Ridge payment id | 404 (RLS); nothing written |

**4 · Test Data** — A-10432 ACH $247.30 (ACH-2028104) posted Jul 10 — TC-1 at Aug 9 (day 30), TC-2 variant posted Jun 9 (day 61 on Aug 9). Cross-period fixture: payment posted Jul 28, July closed Aug 5 (BR-TEN-038). Check fixture: #4021 $100.00 posted Jan 12, NSF found Sep. Bulk: prototype 3 × $988.70. Actors: Priya Menon (request), Alex Reed (System Admin approval). Isolation: J. Okafor.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Reason | S35 Reverse | prototype-extracted (4 options) | reversal reason on the reversing row + audit | enum | user-input | required; NSF ⇒ US-PAY-009 |
| Memo | S35 Reverse | prototype-extracted | audit payload | text | user-input | optional |
| Window evaluation | — | BR-PAY-011 | computed: method + days since posted; paid/cross-period detection | enum | system-derived | server-side; UI mirrors |
| Approval record | — | BR-PAY-011 | approval on the reversal event (Admin/Executive, who/when — r12 family, DDL 🔒 #17) | uuid/ts | user-input | server-enforced role |
| Reversing rows | S33 | BR-PAY-002/011 | `payments` reversing row + `allocations` reversing rows | numeric(18,6) | system-derived | append-only; balances re-open exactly |
| Consequence message | S35 | BR-PAY-030 | rendered from computed effects (bills, balance, approval, ledger) | text | computed-display | always before confirm |
| Notify customers | S35 | prototype-extracted + BR-NOT-005 | `outbound_messages` rows (r12 #16) | rows | user-input | queue-write only |
| Ledger handoff | — | model §12 | posting service 🔒 reversing pair | rows | system-derived | balanced |
| Audit | — | CLAUDE.md #7 | `audit_log` `payment.reversed` (+`.approved`) | jsonb | system-derived | append-only |

**6 · Acceptance**
- Given each method window, Then in-window reversals execute and out-of-window/paid/cross-period ones route to approval — never a dead end, never a silent pass (PE-8).
- Given confirm, Then the consequence message always precedes it and reversing rows fully re-open the affected bills.
- Given roles, Then approval is server-enforced; given tenants, nothing crosses.

**7 · Finance Calculation** — CONFIRMED (BR-PAY-011 mechanics; PE-8 path). Worked (TC-1): reversing payment −247.30 + allocation reversing rows re-open BL-2607-018204 by 247.30; account balance rises by exactly 247.30. No fee attaches to a non-NSF reversal (fees are BR-PAY-013's).

**8 · Open Questions** — None.

---
id: US-PAY-011
epic: EP-PAY-03
module: payments
screens: [S58, S33]
wave: 5
status: draft
blocked_by: []
depends_on: [US-PAY-007, US-BIL-011]
journeys: [J2, J5]
rules: [BR-PAY-014, BR-PAY-002, BR-PAY-024]
golden_tests: []
finance_calc: confirmed
---
### US-PAY-011 — Refunds: only from real credit, Admin approval, check/ACH v1, immutable + receipt

**1 · Details** — As Finance/Owner staff, I want refunds per BR-PAY-014 (PE-9): **only from a real credit balance** (US-PAY-007 position; final-bill refunds arrive via the US-BIL-011 path-1 handoff), request → **Admin approval** (r12 #5 requested_by/approved_by) → execute **check/ACH v1** (card refund waits for rails W7) → posting **DR customer-credit / CR cash** (posting service 🔒) → **immutable refund row + receipt** (queue-write per BR-PAY-024/BR-NOT-005). S58 modal fields per prototype (design r2): account (credit balance required), amount, method Check/ACH, check #/trace, reason (Overpayment / Closed account credit / Duplicate payment / Deposit return), status **Issued / Cleared / Void** (B2 r2 refund status set — Void is a status transition with reversing posting, never a delete). Entry: S58 (Finance GL tab "Record refund") / S33 row Refund / customer payout request (US-PAY-007 TC-4). Exit: refund row; credit drawn down; audit.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-PAY-014 | Refunds only from a real credit balance; Admin approval; check/ACH v1 (card = rails W7); DR customer-credit / CR cash; immutable row + receipt. **⚠ AMENDED 2026-08-12 (PO): (a) OQ-167 — a credit built from TWO overpayments must be refundable, so a refund is raised against the CREDIT BALANCE, not against one payment, and the clerk chooses refund or credit; (b) OQ-135 — a customer owing on ANOTHER of their accounts is OFFSET FIRST and the refund is what remains.** | CONFIRMED — PO PA-3, 2026-08-08 (r12 #5) · **amended PO 2026-08-12 (OQ-167, OQ-135)** |
| BR-CUS-054 *(consumed)* | *"Another account"* means the CUSTOMER ENTITY; the link is N:M, so a jointly-held account counts every holder's other accounts — a shared surname or address counts for nothing. | CONFIRMED — PO OQ-057 (b); scope recorded 2026-08-12 |
| BR-CUS-015 *(consumed)* | `accounts.balance` is a CACHE: good enough to stop a payout leaving, **not** good enough to subtract from one — so the refund REFUSES and the offset is a balance transfer. | CONFIRMED — Eng-Lead reading recorded 2026-08-12 under OQ-135 |
| BR-PAY-002 | Refund rows append-only; Void = status transition + reversing posting. | CONFIRMED — B2 §payments + B2 r2 (refund status issued\|cleared\|void) |
| BR-PAY-024 | Refund receipt/notice auto-queued (delivery queue; print v1). | CONFIRMED — PO Lane B-3 (family) |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | PE-9: refund ACC-1042's credit **57.13**, check #10241, reason Overpayment | Request → Alex approves → refund row (Issued), credit position → 0.00; posting handoff DR customer-credit 57.13 / CR cash 57.13; receipt queued; audit `refund.issued` |
| TC-2 | Final-bill refund handoff (US-BIL-011 Case A, 11.20) | Billing's path-1 handoff creates the refund request here; same approval + execution; linkage to the final bill recorded |
| TC-3 | Check clears at the bank | Status Issued → Cleared (cleared date recorded — bank-rec matches refunds on the clearing side, BR-PAY-021 family) |
| TC-4 | Void an issued-but-lost check | Status → Void with reversing posting (credit restored 57.13); new refund issuable; no row deleted |
| TC-5 *(negative)* | Refund attempt for $80.00 against a $57.13 credit; refund on an account with zero credit | Rejected — refunds only from a real credit balance (BR-PAY-014); amount ≤ credit |
| TC-8 *(PO 2026-08-12, OQ-167)* | The credit is built from **two** overpayments — **$40.00** in June and **$17.13** in July — and the customer asks for the **$57.13** back | Refundable. The refund names the **credit balance**, not a single payment (`refunds.payment_id` cannot express two); the clerk is offered **refund OR credit** and picks — *"it will be manula decision"* — and the product performs neither automatically |
| TC-9 *(PO 2026-08-12, OQ-135)* | The same customer holds the **$57.13** credit here and **$948.20** overdue by 91 days on another of their accounts (final notice already sent) | **Refund REFUSED** — *"offset first"*. The arrear is met by an offset applied as a **balance transfer** through the reviewed writer; only what remains, if anything, is refundable. The cross-account figure comes from `accounts.balance`, a cache good enough to stop the payout and not to net it down (BR-CUS-015) |
| TC-10 *(PO 2026-08-12, OQ-135 scope)* | The credit sits on a **jointly-held** account; a different customer shares the payee's surname and service address | Every holder's other accounts are in scope (`customer_accounts` N:M); the same-surname/same-address stranger is **not** — offsetting there would move money between strangers |
| TC-6 *(negative)* | Clerk tries to self-approve; card method chosen | Approval is Admin-only, server-enforced; card disabled with the W7 rails note (BR-PAY-014) |
| TC-7 *(isolation)* | Lone Star Ridge refund | Draws only its own credit positions; Brazos Bend accounts unreachable (RLS) |
| TC-11 *(PO 2026-09-23, OQ-PAY-12614 — the case SHOWN)* | Dana sends a refund of **$91.60** by check **#10241** but types **#10214** at issue | **Correctable** through *Correct check number* (`POST /refunds/{id}/correct-reference`, Admin or Billing Clerk, required note): the row reads #10241, the $91.60 does not move, and `audit_log` holds #10214 → #10241. **Refused:** any other write of the number (database, `payments/0043`); the amount, account, method, memo or tender through the same door; a refund with no number yet (the first number is Issue's); a canceled refund. `06-backend/tests/test_cr141_refund_check_number_correction.py` |

**4 · Test Data** — PE-9 verbatim: ACC-1042 credit 57.13 (from PE-4) → refund 57.13, check #10241, Aug 15, 2026. Final-bill fixture: US-BIL-011 Case A refund 11.20 (ACC with deposit credit 153.50 vs final 142.30). Void fixture: check lost in mail. Actors: Norma Reyes (Finance, request), Alex Reed (System Admin, approve). Isolation: Lone Star Ridge credit $12.00.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Account (credit required) | S58 | prototype-extracted ("Search account with a credit balance") | `refunds.payment_id` → credit row; account via payment — ⚠ **single-payment shape SUPERSEDED by PO 2026-08-12 (OQ-167): a refund must be raisable against the CREDIT BALANCE, since $40.00 + $17.13 = $57.13 has no single `payment_id`** | uuid | user-input | credit balance > 0; **no arrear on the customer's other accounts (offset first, OQ-135)** |
| Offset check (other accounts) | S58 | **PO 2026-08-12 (OQ-135)** · BR-CUS-054 | `apps/customers/selectors.arrears_on_other_accounts` over `customer_accounts` (N:M) — read-only; the offset itself is a balance transfer through the reviewed writer | numeric(18,6) | system-derived | refund REFUSES while an arrear stands; never netted off the `accounts.balance` cache (BR-CUS-015) |
| Refund-or-credit election | S58 | **PO 2026-08-12 (OQ-167)** | staff choice recorded on the request (*"it will be manula decision"*) | enum(refund\|credit) | user-input | required; the product offers both and chooses neither |
| Amount | S58 | prototype-extracted | `refunds.amount` | numeric(18,6) USD | user-input | 0 < x ≤ credit balance |
| Method | S58 | prototype-extracted (Check/ACH) + BR-PAY-014 | `refunds.method` (B2 r2: check\|ach) | enum | user-input | card disabled → W7 |
| Check # / trace | S58 · **on ISSUE, not on Raise** | prototype-extracted; the ACT is the blueprint's (`06 Payments Page Blueprint.pdf` p078 ② — *"the only record of which cheque this was"*) | `refunds.reference` (B2 r2 reference/check_no) | text | user-input | **required for check, AT ISSUE** — ⚠ this row read *"required for check"* with no act until 2026-09-23, and it was collected on RAISE, which asks for the number of a cheque nobody has written yet (`DEF-PAY-6331`). The requirement did not change; the act it is enforced at did. ~~**WRITE-ONCE** from `payments/0041`: NULL → set, never changed — a wrongly written cheque is VOIDED and re-raised (TC-4).~~ ⚠ **AMENDED 2026-09-23 BY PO RULING (`OQ-PAY-12614`, option b — *"(b) Allow a correction, the same way you allowed it for payments on 2 September"*; `CR-141-BRC07`):** written at ISSUE and **write-once for every writer but one** — a number KEYED wrongly is replaced through `POST /refunds/{id}/correct-reference` (Admin or Billing Clerk, a required note, `audit_log` `refund.reference_corrected` with the old number and the new; `payments/0043`'s trigger refuses every other rewrite). A check written for the wrong AMOUNT is still VOIDED and re-raised (TC-4). Only the number is correctable — memo and method were not put to the PO and are refused by name (TC-11). `POST /accounts/{id}/refunds` refuses a `reference` BY NAME |
| Reason | S58 | prototype-extracted (4 options) | `refunds.reason` | enum/text | user-input | required |
| Status | S58 | B2 r2 (issued\|cleared\|void) | `refunds.status` | enum | system-derived (+user transition) | void = reversing posting, never delete |
| Requested / approved by | — | BR-PAY-014 | `refunds.requested_by` / `.approved_by` + timestamps (r12 #5) | uuid/ts | user-input | Admin approval server-enforced |
| Posting handoff | — | BR-PAY-014 (model §12) | posting service 🔒: DR customer-credit / CR cash | rows | system-derived | balanced |
| Receipt/notice | — | BR-PAY-024 + BR-NOT-005 | `outbound_messages` row (r12 #16) | rows | system-derived | queue-write only |
| Audit | — | CLAUDE.md #7 | `audit_log` `refund.requested/approved/issued/voided` · **`refund.reference_corrected`** (2026-09-23, `CR-141-BRC07`: `before`/`after` carry the replaced check number and the new one — and `audit_log` is pruned on its one schedule, `OQ-1340`, so this is NOT a permanent record of the old number) | jsonb | system-derived | append-only |

**6 · Acceptance**
- Given PE-9, Then the refund draws the credit to zero, posts DR customer-credit / CR cash via the handoff, and the immutable row + receipt exist.
- Given no or insufficient credit, Then the refund is impossible; given card, v1 refuses with the rails note.
- Given approval, Then it is Admin-only and server-enforced; given Void, the credit restores by reversing entries.

**7 · Finance Calculation** — CONFIRMED (PE-9, model §13 verbatim: refund **57.13** — the PE-4 credit). Posting: DR customer-credit 57.13 / CR cash 57.13 (model §12 row "Refund"). Final-bill variant: refund **11.20** (US-BIL-011 Case A figure, cited not recomputed). **Multi-source credit (PO 2026-08-12, OQ-167):** the same **57.13** reached as **40.00 + 17.13** refunds identically — the amount does not change, only the number of payments behind it. **Offset case (PO 2026-08-12, OQ-135):** **57.13** credit against **948.20** overdue elsewhere pays out **nothing**.

**8 · Open Questions** — **None open. Two closed 2026-08-12 (PO):** **OQ-167** — *"user can do a refund or issue a credit - it will be manula decision, provide a mecahnism to complete the tasks"*; the structural blocker was `refunds.payment_id uuid NOT NULL` (B2 §2), so the mechanism owed is a refund raised against the **credit balance**. · **OQ-135** — *"offset first"*; a credit of **$57.13** against **$948.20** overdue on another account of the same customer entity pays nothing, and the offset is a **balance transfer**, not a subtraction from a cached balance (BR-CUS-015 · `apps/billing/final_bill._prior_balance` draws the same line).

---
id: US-PAY-012
epic: EP-PAY-03
module: payments
screens: [S34, S35]
wave: 4
status: draft
blocked_by: []
depends_on: [US-PAY-013]
journeys: [J4, J5]
rules: [BR-PAY-020, BR-PAY-002]
golden_tests: []
finance_calc: confirmed
---
### US-PAY-012 — Write-offs: initiated in Payments, approved + reported in Finance

**1 · Details** — As a Billing Clerk, I want to INITIATE a write-off from the outstandings surface (S34 bulk / S35 Write-off modal / S33 failed-row action) per BR-PAY-020: reason (prototype set: Uncollectible after 120 days / Customer bankruptcy / Deceased · no estate / Below write-off threshold), bad-debt GL account, **audit note required** — and have it **APPROVED in Finance by Owner/Admin** before any money-bearing write; on approval the `write_offs` row (r12 #11) closes the balance, the ledger posts **DR bad debt / CR AR** (posting service 🔒, model §12), and Finance reports it (write-offs YTD on S32/S36). Payments owns the transaction record; ledger posts; finance reports (BR-PAY-020 three-way split). The prototype's "Send to collections agency instead" and "Flag for future deposit" checkboxes have NO ratified rule — excluded from v1 scope, flagged in the pack report (never silently decided). Small-balance AUTO write-offs at final bill are billing's (BR-BIL-013 path 5) — this story is the manual collections write-off. Entry: S34/S35/S33. Exit: approved write-off; balance zero; audit chain.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-PAY-020 | Write-offs: INITIATED in Payments (S34/S35, operational), APPROVED + reported in Finance (Owner/Admin, bad-debt GL); payments owns the transaction record, ledger posts, finance reports. | CONFIRMED — PO PA-9 + PM placement, 2026-08-08 (r12 #11) |
| BR-PAY-002 | Write-off rows append-only; an erroneous write-off is corrected by a reversing entry, never an edit. | CONFIRMED — B2 §payments (family) |
| BR-BIL-013 *(boundary)* | Small-balance settlement write-offs (≤ tenant $5 default) are billing's automatic path — out of this flow. | CONFIRMED — billing pack (cited) |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Priya initiates write-off of A-10802 Novak $948.20, reason "Uncollectible after 120 days", GL 6100, note recorded | Pending-approval record; NO balance/ledger effect yet (approval gates money, BR-PAY-020); audit `write_off.requested` |
| TC-2 | Alex (Owner/Admin) approves in Finance | `write_offs` row approved (approved_by/when); balance → 0.00; posting handoff DR 6100 Bad Debt 948.20 / CR 1200 AR 948.20; write-offs YTD on S32/S36 includes it |
| TC-3 | Bulk write-off, 4 selected $11,642.90 (prototype) | One request, per-account rows; approval covers the reviewed set; per-account results listed |
| TC-4 | A payment arrives after write-off | Recorded normally (US-PAY-001); recovery handling posts as a new credit event against the account — the write-off row is never edited (BR-PAY-002) |
| TC-5 *(negative)* | Missing audit note; clerk attempts to approve own request | Note required (prototype "Required"); approval Owner/Admin only, server-enforced |
| TC-6 *(negative)* | UPDATE/DELETE on an approved write_offs row | Blocked — append-only |
| TC-7 *(isolation)* | Lone Star Ridge write-off | Its GL accounts + approvals only; Brazos Bend rows invisible (RLS) |

**4 · Test Data** — A-10802 Novak, P.: balance $948.20, 91 days late, final notice sent Aug 1 (prototype S34 row). Bulk: prototype selection $11,642.90. GL: 6100 Bad Debt Expense (prototype S36 chart). Note: "120+ days, 3 notices, phone contact failed ×4". Actors: Priya Menon (initiate), Alex Reed (Owner/Admin approve), Norma Reyes (Finance reporting). Isolation: J. Okafor.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Reason | S35 Write-off | prototype-extracted (5 options; "Sent to collections agency" excluded — no BR, pack report) | `write_offs.reason` (r12 #11) | enum/text | user-input | required |
| Bad-debt GL | S35 | prototype-extracted + BR-PAY-020 | `write_offs` GL ref → `ledger_accounts` (bad-debt designation, r10 #2/#11) | uuid | reference-data | tenant chart rows only |
| Audit note | S35 | prototype-extracted ("Required") | audit payload + `write_offs` note | text | user-input | required |
| Approval | Finance surface | BR-PAY-020 | `write_offs.approved_by` + timestamp (r12 #11) | uuid/ts | user-input | Owner/Admin, server-enforced; money gated behind it |
| Balance closure | S34/S21 | BR-PAY-020 | account balance read-model → 0 on approval | numeric(18,6) | system-derived | exact AR amount |
| Posting handoff | — | model §12 | posting service 🔒: DR bad debt / CR AR | rows | system-derived | balanced |
| Write-offs YTD | S32/S36 | prototype-extracted | computed over `write_offs` approved | $ | computed-display | finance reporting |
| Deposit-flag / agency checkboxes | S35 | prototype-extracted — **no ratified rule** | NOT in v1 scope (pack-report candidates P-4/P-5) | — | — | excluded, never silently decided |
| Audit | — | CLAUDE.md #7 | `audit_log` `write_off.requested/approved` | jsonb | system-derived | append-only |

**6 · Acceptance**
- Given an initiation, Then nothing money-bearing exists until Owner/Admin approval; on approval the balance closes, the DR bad-debt / CR AR handoff posts, and finance reporting picks it up.
- Given bulk, Then approval binds the reviewed set with per-account results.
- Given later recovery, Then new rows record it — the write-off row never changes.
- Given tenants, Then GL, approvals and reports never cross.

**7 · Finance Calculation** — CONFIRMED (BR-PAY-020 + model §12 row "Write-off": AR ↓ · DR bad debt / CR AR). Worked (TC-2): DR 6100 **948.20** / CR 1200 **948.20** — balanced; account balance 948.20 → 0.00. Bulk Σ = Σ per-account AR (prototype fixture 11,642.90, display).

**9 · Build state (2026-08-15, payments visible-half lane)** — **BACKEND COMPLETE, NO SCREEN.** `write_offs` exists (migration 0009, frozen deny-by-default by 0010); `apps/payments/writeoffs.py` requests (no money) and approves (DR write-off / CR AR through the ledger seam, and the plan closure OQ-171 ruled); `POST /api/{tenant}/write-offs` and `POST /api/{tenant}/write-offs/{id}/approve` serve both. ⚠ **Owed:** the S35 Write-off modal and the S34 bulk action (no frontend), and the Finance approval queue on S36. **BR-PAY-020 says *Owner/Admin* and A4 has no such role** — approval is A4's System Admin, recorded in the decision log and on the human-review row rather than decided silently.

**8 · Open Questions** — None.
