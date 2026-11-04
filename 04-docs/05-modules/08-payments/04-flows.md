# payments — Flows & States

> Fleshed out 2026-08-08 from the ratified model (`07-pre-session-model.md`, Addenda r1/r2) and BR-PAY-001..031. Exact DB enum spellings + keys = Eng-Lead 🔒 (B2 r12 #17); the transitions below are the ratified behavior. Screens: S22/S32–S35/S37–S40/S58 (A1); state machines: A5.

## 1. Intake → allocation → batches → rec (the money-in pipeline)

```
INTAKE  single S22/S35 (US-PAY-001, BR-PAY-021/022) · bulk lockbox/CSV staged import (US-PAY-003, BR-PAY-023)
        · webhook (rails W7 — webhook_key dedupe schema-ready, BR-PAY-003/028) · purpose bill|deposit|plan_down|prepay (US-PAY-002, BR-PAY-012)
  → payments row: posted_at (record enters system) + cleared_at (money received) — ALWAYS both (BR-PAY-021)
  → ALLOCATION (US-PAY-006, BR-PAY-001/010 + BR-PAY-038): oldest invoice first; within invoice
    usage+base → taxes → the TENANT-DEFINED class → fees LAST (four classes since PO 2026-08-11, OQ-109);
    ** ↳ THAT ORDER IS THE SHIPPED DEFAULT OF A TENANT SETTING (PO 2026-08-12, OQ-189):**
        *"better to let user set the sequence"* — a utility, a submetering operator and an HOA are
        three businesses with three regulators. Default figure unchanged: $120.00 on a $128.88 bill
        meets 100.58 → 8.30 → 11.12, late fee LAST at 0.00. Setting lives in Settings → Configure.
    ** ↳ NAMED EXCEPTION (PO 2026-08-12, OQ-139): an INSTALMENT payment reaches THE PLAN FIRST**,
        not the oldest bill (PE-13's 36.22 before October's 184.20); short of the instalment,
        NOTHING reaches the current bill — a part-paid instalment is still a missed one (BR-PAY-012);
        overpayment → carried credit (US-PAY-007); staff instruction oldest|specific|carry|split
        (*specific* is served by the OPEN-BALANCE read the PO ordered built, OQ-154);
        Reapply = reversing+new rows (US-PAY-008, BR-PAY-031)
  → RECEIPT auto-queued on clearing (US-PAY-025, BR-PAY-024) — outbound-table write only (BR-NOT-005)
  → DEPOSIT BATCH day × method by **posted_at** day — the physical drawer day (BR-PAY-025 /
        BR-REP-013, PO ruling RQ-5; corrected 2026-08-11, DEF-065), DEP- series (US-PAY-020)
  → BANK REC (FINANCE, S38–S40, Owner/Finance — BR-PAY-019): statement import → auto-match amount + date ±3d (finance setting)
        → exceptions: reason + GL in the S40 modal (US-PAY-022, PE-11 −5.00); a CARD day reconciles
        **NET with the fee as its own line to 6800** (BR-PAY-040, PO 2026-08-11); the FEE MAY BE
        **DERIVED from the shortfall** (PO 2026-08-12, OQ-160: 5,120.40 taken − 4,972.90 credited
        = 147.50) and a difference in the WRONG direction is REFUSED — a bank crediting more than
        we recorded has not charged a fee; matching is **MANY-TO-ONE** since PO 2026-08-12 (OQ-161:
        2,840.00 + 14,280.00 banked as ONE 17,120.00 credit) → reconcile → LOCK
        (BR-PAY-004; Unreconcile = only reversal, US-PAY-023 — and it does NOT take the cash back
        out of the books, PO 2026-08-12, OQ-163)
  → **RECONCILIATION REALISES THE CASH** (BR-PAY-039, PO 2026-08-11): the receipt held DR 1010
        Undeposited funds; reconciling posts DR 1000 Cash / CR 1010 through the ledger service 🔒
```
**Billing consumes posted_at** (on-time = posted ≤ due date even if cleared later); **NSF + bank rec consume cleared_at** (BR-PAY-021).

## 2. Payment states (A5 + B2 `payment_status`)

`processing → cleared` (cleared_at set) · `failed` (clearing failure) · `reversed` (reversing-row pair, US-PAY-010) · `posted` (credit/adjustment rows). Append-only once out of processing (BR-PAY-002): corrections are ALWAYS new reversing rows — payment, allocation, refund, write-off alike.

## 3. NSF state machine (BR-PAY-013, PE-7 — hangs off clearing)

```
cleared payment → clearing failure (bank return / S40 rec finding / manual NSF reason)
  → reversing payment row (−amount) + allocation reversing rows
  → AR reinstated at the ORIGINAL due date (late-fee clock never resets)
  → NSF charge code auto-added (tenant code via billing charge line, BR-BIL-007)
  → nsf_count++ ; at tenant N (default 2) → cash-only / no-autopay privilege flag
  → customer notice (queue-write) · ledger: reversing pair + fee line (posting service 🔒)
```

## 4. Reversal flow (BR-PAY-011/030, PE-8)

`request (reason) → window check: ACH 60d · card 120d · check unlimited (NSF) → [in window → consequence message → reversing rows] | [blocked / paid / cross-period → Admin/Executive approval → same reversing execution]`. Consequence messaging ALWAYS precedes confirm; closed-period reversals post forward per BR-TEN-038 (posting service 🔒).

## 5. Refund state machine (BR-PAY-014, PE-9 — S58)

`request (real credit balance only) → Admin approval (requested_by/approved_by, r12 #5) → execute check/ACH (card = rails W7) → Issued → Cleared | Void (reversing posting, credit restored)`. Posting: DR customer-credit / CR cash. Immutable rows; receipt queued.

## 6. Write-off (BR-PAY-020)

`initiate in Payments (S34/S35: reason + bad-debt GL + note) → approve in Finance (Owner/Admin) → write_offs row · balance → 0 · DR bad debt / CR AR (posting 🔒) · finance reports (YTD)`. No money-bearing write before approval; recovery = new rows, never edits. (Small-balance final-bill write-offs are billing's — BR-BIL-013 path 5.)

## 7. Collection sequence (BR-PAY-017, PE-15 — all tenant-config)

```
due+3 friendly reminder → due+grace LATE FEE (billing, BR-BIL-001/008) → tier-1 10-day notice → tier-2 5-day → 48h CERTIFIED FINAL
```
Paper v1; certified required on final (A19 rule 3); **medical-hold excluded** (A15); email + SMS text-to-pay rows written to the outbound queue from day one, dispatched when their channels land (email W6, SMS Twilio seam). Every send AND skip appends `notice_history` (J4 step 2); collection state per account = tier + last/next dates (r12 #7). Stops: payment POSTED by due date (BR-PAY-021) · active+current payment plan (pause, §8) · settle · **a partial payment that meets the tenant's threshold % of outstanding (PO 2026-08-12, OQ-136 — $150 of $948 = 15.8% does NOT stop it; 25% needs $237.00, 50% needs $474.00; the % is a Settings → Configure value)** · **a balance under the tenant's collection floor, default $25.00, which governs the WHOLE ladder and not just the late fee (PO 2026-08-12, OQ-137/OQ-157 — $2.40 unpaid buys no $8.00 certified letter)**. **RESTART: after a BOUNCE the ladder returns to RUNG 1 (PO 2026-08-12, OQ-133 — a $1,842.10 bill whose 5 Jul cheque bounced three weeks later gets the full ladder again), because the payment that stopped it never existed.** Returned mail (BR-PAY-018, PE-16): delivery record returned → `accounts.bad_address` → needs-attention queue/banner → paper suppressed until verified (config) — balances unaffected.

## 8. Payment-plan lifecycle (BR-CUS-043/044 + BR-PAY-016, PE-13)

```
proposed → agreement_sent (S67 template ①, DocuSign seam) → ACTIVE on customer e-signature ALONE
   → [current: dunning + disconnect PAUSED **over the arrears this plan spreads only**;
      the CURRENT month's bill is due every month and is chased normally
      — PO 2026-08-11, BR-BIL-073; late-fee suspension per-plan election]
   → [a MISSED instalment lifts the pause the NEXT DAY — PO 2026-08-12, OQ-170,
      *"Immediate"*, no grace: PE-13's 36.22 unpaid 1 Oct → chasing resumes 2 Oct,
      the plan still ACTIVE and nobody dropped]
   → closed (final installment posted **OR the utility WRITES THE ARREARS OFF** —
      PO 2026-08-12, OQ-171: a write-off closes the plan and the account may take a
      new one; the product supplies the mechanism and the report, never the decision)
   ✗ void — **SUPERSEDED (PO 2026-08-11, OQ-141): there is no void.** A missed
     instalment is recorded and CHASED; the plan stays active to write-off.
```
Schedule: (total − down) ÷ n, 2dp half-up, remainder on FINAL (PE-13: 267.30 − 50 over 6 → 5 × 36.22 + 36.20). Notices: reminder −3d · missed day+1 — both queue-writes. **The void notice is superseded with the void.** Installment on-time = posted_at ≤ installment due date (BR-PAY-021). One live plan per account.

**What a customer on a plan owes each month (PO ruling 2026-08-11, OQ-138 CLOSED → BR-BIL-073):** the instalment **AND** the current bill. Worked on PE-13: **36.22 + 184.20 = 220.42** in October, not 36.22. ~~Which of the two a PARTIAL payment meets is **OQ-139, still OPEN**~~ — **OQ-139 CLOSED 2026-08-12 (PO): *"plan first"*.** The instalment is met FIRST — a NAMED EXCEPTION to oldest-invoice-first, scoped to instalment payments only — and **short of the instalment nothing reaches the current bill**, so a part-paid instalment is still a missed one and the dunning pause lifts the next day. `apps/customers/payment_plan.split_payment_between` no longer raises.

## 9. Deposit batch states (B2 `batch_status`, BR-PAY-004/025)

`in_transit → unmatched | matched → reconciled (LOCKED — totals + membership immutable) → [Unreconcile (Owner/Finance, audited) → unmatched]`. Batches group money; **the RECONCILE posts** (BR-PAY-039 — DR cash / CR undeposited, plus one line per explained difference to its own GL, BR-PAY-019/040), and ~~Unreconcile mirrors that entry back out (OQ-163)~~ **⚠ OQ-163 CLOSED 2026-08-12 (PO): *"no keep it as it is - Utility will balance the books by manual journal entry"* — UNRECONCILE DOES NOT TAKE THE CASH BACK OUT OF THE BOOKS.** The PE-10 batch's 471.39 entries stand; un-reconciling only unlinks the batch, and a utility that needs the entry undone posts a manual journal entry (BR-LED-003). The product SHOWS the position correctly; it does not reverse it automatically. **A BOUNCE inside a LOCKED batch does not break the lock** (PO 2026-08-12, OQ-134): the total stays 2,840.00 and the bounce is new rows plus the utility's bounce fee, recorded in payments on the payment (BR-PAY-004). **The batch CODE now carries the year and the banking DATE is a field in its own right** (PO 2026-08-12, OQ-162 — the old year-less `DEP-0805-CHK` repeated itself twelve months on; a code is a label, never a data store). **SHIPPED 2026-08-15**: codes render `DEP-{YY}{MM}{DD}-{METHOD}`, and the date they name is read off `deposit_batches.deposited_on`, never parsed back out of the string. ⚠ The model §12 line *"Deposit batch / bank rec | none (grouping)"* is superseded on the LEDGER column by BR-PAY-039: cutting a batch still posts nothing, but reconciling one is now the event that realises the cash. PE-10: DEP-260808-CHK 471.39 · DEP-260808-CSH 121.78; PE-11: −5.00 bank fee explained.

## 10. Autopay v1 (BR-PAY-015, PE-12)

`enrollment + method stored (customers, BR-CUS-059 capture-only) → bill issue records capture INTENT dated the due date (r12 #6, status awaiting-rails) → visible S32/S33 "autopay scheduled" → staff record the actual money (US-PAY-001)`. No charging path exists before rails (W7); the intent record is the W7 execution contract.

## 11. Receipts (BR-PAY-024, PE-14)

`payment clears (cleared_at) → receipt row per active channel to outbound_messages (BR-NOT-005; print v1, email/SMS deferred markers) → RCT- number → dispatcher sends → manual re-send from S35 (new rows, audited)`.

Journeys: J2 step 10 (record + allocate) · J4 (collections/plans/write-off) · J5 step 1 (batches reconciled + locked).
