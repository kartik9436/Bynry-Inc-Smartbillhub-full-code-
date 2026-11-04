# T6-04 — Approval chains: correction · refund · write-off · adjustment · cross-period reversal (initiator vs approver, both recorded)

---
id: T6-04
tier: 6
roles: [Billing Clerk, System Admin, Executive]
gates: [BR-BIL-014, BR-PAY-014, BR-PAY-020, BR-CUS-038, BR-PAY-011, BR-PAY-030]
stories: [US-BIL-015, US-BIL-016, US-BIL-017, US-PAY-010, US-PAY-011, US-PAY-012, US-CUS-013]
# journey→story wiring sweep pending: story frontmatter `journeys:` updated in a later sweep (00-e2e-design.md §6)
---

**Intent.** Five money actions are approval-GATED workflows, each with a different ratified approver set: correction = System Admin ONLY (OQ-072 v1) · refund = System Admin ONLY · write-off = System Admin/Executive · adjustment = System Admin/Executive · paid/cross-period reversal = System Admin/Executive. This journey runs each chain end-to-end with initiator ≠ approver, proves the WRONG approver refused server-side, and asserts the recorded pair (requested_by/approved_by · case approver) on every executed chain. NO money-bearing write exists before any approval. Self-approval note: the only ratified same-person ruling is for CORRECTIONS — v1 explicitly permits the same System Admin to initiate AND approve, both recorded (EP-BIL-04 test data, OQ-072 v1); every "self-approval refused" in the corpus is a ROLE refusal (a Clerk holds no approve right at all). No same-user separation-of-duties rule exists for the other four chains — nothing beyond the role gates is asserted here (flagged to the PO in the pack report).

**Fixture.** Tenant brazos-bend · Priya = Billing Clerk (initiator) · Dana = System Admin · Marcus = Executive · figures from money-triples: bill BL-2607-0142 $97.41 (`flat,cycle,full`) · correction target credit note −97.41 / rebill 76.35 / delta 21.06 (`flat,rebill` note) · refund credit 48.71 (`flat,cycle,over150`) · write-off 97.41 (`flat,cycle,none`) · adjustment −5.00 late-fee waiver on the `flat,cycle,partial60` account (balance 43.96 = 38.96 + 5.00) · PMT-3308 cross-period card payment 97.41 (T5-10 fixture).

| # | Actor + action | Allowed? / Denied? | Expected outcome | Downstream assertions | Gate |
|---|---|---|---|---|---|
| 1 | CHAIN A (correction) — Priya builds COR-0091: reason → scope → impact preview; tries execute | ALLOWED (build) / DENIED (execute) | Preview persists as THE approval artifact; execute 403 approval-required (T5-11) | Zero money-bearing writes; workflow rows only | BR-BIL-014 |
| 2 | Marcus (Executive) tries to approve COR-0091 | DENIED | Correction approval = System Admin only in v1 — Executive's adjustment/write-off approve right does not extend here | 403-class; case pending; zero writes | BR-BIL-014 |
| 3 | Dana approves; Priya executes | ALLOWED | Staged idempotent execution | Credit note −97.41 · rebill 76.35 · GL reversals balanced · delta 21.06; `correction_cases` records initiator Priya + approver Dana + timestamps; audit chain | BR-BIL-014 |
| 4 | CHAIN A′ (same-person, the ratified exception) — Dana initiates correction COR-0092 herself AND approves it | ALLOWED | OQ-072 v1: initiator/approver may be the same (System Admin); BOTH recorded on the case | Case shows initiator = approver = Dana, both timestamped — the trail, not a block, is the v1 control | BR-BIL-014 (OQ-072 v1) |
| 5 | CHAIN B (refund) — Priya initiates REF-0027 from the real credit 48.71; tries to self-approve | ALLOWED (initiate) / DENIED (approve) | Clerk holds no approve right — role refusal, server-enforced | `refunds.requested_by` = Priya; no execution/posting/receipt; zero money writes | BR-PAY-014 |
| 6 | Marcus tries to approve REF-0027 | DENIED | Refund approval is Admin-ONLY — Executive refused | 403-class; zero writes | BR-PAY-014 |
| 7 | Dana approves REF-0027; execution check v1 | ALLOWED | `approved_by` = Dana (r12 #5); check/ACH only (card = W7 rails) | Immutable refund row; credit 48.71 → 0.00; DR customer-credit / CR cash 48.71 balanced; receipt queued; audit `refund.approved/issued` | BR-PAY-014 |
| 8 | CHAIN C (write-off) — Priya initiates WO-0032 (97.41, reason, bad-debt GL, required note); tries to approve her own request | ALLOWED (initiate) / DENIED (approve) | Approval refused as a ROLE gate (Clerk = request only) | Pending record; NO balance/ledger effect; audit `write_off.requested` only | BR-PAY-020 · A4 approval row |
| 9 | Marcus approves WO-0032 in Finance | ALLOWED | Executive holds the A4 write-off approve right; approval is where money begins | Balance 97.41 → 0.00; DR bad-debt / CR AR 97.41 balanced; `approved_by` = Marcus recorded beside initiator Priya; finance reports pick it up | BR-PAY-020 |
| 10 | CHAIN D (adjustment) — Priya requests −5.00 "Waive late fee" (approval flag defaults ON); probes: untick the flag; approve herself | ALLOWED (request) / DENIED (untick; approve) | Flag editable by the Owner/Finance-mapped roles only; approver = System Admin/Executive; server enforces regardless of UI state | Request queued; balance unchanged (43.96); zero money writes on both probes | BR-CUS-038 |
| 11 | Marcus approves the adjustment | ALLOWED | Consequence message pre-confirm (BR-BIL-009) | Adjustment row −5.00 referencing the bill; balance 43.96 → 38.96; both request + approval audited | BR-CUS-038 |
| 12 | CHAIN E (cross-period reversal) — Priya attempts to reverse PMT-3308 (paid + cross-period) with no approval | DENIED | Approval-required 403; consequence preview renders but confirm is gated (T5-10) | No reversing rows anywhere; ledger unchanged | BR-PAY-011 |
| 13 | Marcus approves; Priya re-runs the reversal | ALLOWED | Admin/Executive approval satisfied; consequence message → explicit confirm | Reversing payment + allocations + JE linked to PMT-3308; originals immutable; approval + execution both audited with distinct actors | BR-PAY-011 · BR-PAY-030 |
| 14 | CROSS-CHECK — S61 filter action-type `approval`, today | ALLOWED | Every approval above (3, 4, 7, 9, 11, 13) appears with actor + related approval ref; the denied probes (2, 5, 6, 8, 10, 12) left NO approval rows | Approval trail complete; denial trail absent (attempt-logging not ratified — BR-AUD-001 scope) | BR-AUD-009 · BR-AUD-004 |
