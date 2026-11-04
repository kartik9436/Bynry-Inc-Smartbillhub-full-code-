# J15 — Overpay → credit → refund (PE-4 57.13 through the BR-PAY-037 approval chain)

---
id: J15
tier: 2
rules: [BR-PAY-010, BR-PAY-014, BR-PAY-037, BR-PAY-024, BR-PAY-021, BR-CUS-061, BR-LED-007, BR-AUD-018, BR-REP-014]
stories: [US-PAY-001, US-PAY-007, US-PAY-011, US-PAY-025, US-LED-001, US-REP-007]
# journey→story wiring sweep pending: story frontmatter `journeys:` updated in a later sweep (00-e2e-design.md §6)
---

**Intent.** Money the utility owes the customer, handled by the book: an overpayment becomes a visible carried credit (PE-4 **57.13**) that would auto-apply to the next bill — until the customer asks for it back. The refund runs the full BR-PAY-014 chain with tonight's BR-PAY-037 explicitly exercised: in v1 the SAME user holding the approver role may initiate AND approve, with both acts recorded distinctly. A second refund attempt proves refunds come only from REAL credit.

**Fixture.** Tenant brazos-bend · ACC-1042 · open balance **292.87** (WE-1 total due) · payment **350.00** check, posting Jul 19 / clearing Jul 22 · credit **57.13** (PE-4) · refund **57.13** by check (PE-9, LE V-6 pattern) · actor: Dana, System Admin (holds the approver role).

| # | Date · action | Handoff contract (what this step leaves) | Downstream assertions (bill · ledger · reports · queue · audit) | Rule |
|---|---|---|---|---|
| 1 | **Jul 19** — payment 350.00 recorded (both dates) → allocation settles the open 292.87 in full → **overpayment → account credit 57.13** (PE-4) | Credit carried on the account: visible on S21/S34, flagged to auto-apply at the next bill issue, refundable on request (the BR-CUS-061 pattern) | Ledger: DR cash 350.00 / CR AR 292.87 + CR customer-credit 57.13 — balanced; receipt queued (BR-PAY-024); posting-basis collections count only the bill-purpose portion (BR-REP-014); audit | **BR-PAY-010** |
| 2 | **Jul 24** — customer requests the money back; Dana INITIATES the refund (only from a real credit balance — engine verifies 57.13 exists) | Refund request row with initiator recorded | No money moved yet; request visible in the approval queue; audit | BR-PAY-014 |
| 3 | **Jul 24** — Dana, holding the approver role, APPROVES her own initiation — allowed in v1, both acts recorded DISTINCTLY (initiator row + approver row, same user); enforced separation-of-duties = v2 | Approval recorded; refund executable | The two distinct act records exist and name the same user — the audit trail is the control in v1; audit | **BR-PAY-037** |
| 4 | **Jul 24** — refund EXECUTES: check issued → posting **DR customer-credit / CR cash 57.13** (V-6); refund row immutable; refund receipt/notice queued | Account credit = 0.00; refund row append-only | Ledger balanced; customer-credit GL for the account ends 0.00 — tie-out exact (BR-LED-007); queue row for the refund notice (BR-NOT-005); audit | **BR-PAY-014** |
| 5 | **Jul 25** — a second refund attempt for the same 57.13 | **REFUSED** — no real credit balance remains; refusal writes a security-event attempt row; nothing else is written | Books byte-identical to step 4; attempt row in audit_log | BR-PAY-014 · **BR-AUD-018** |
| 6 | **Aug 1** — next cycle bill issues: NO credit applies (it was refunded) — full amount due (engine-computed, 00-e2e-design.md §5) | Normal bill; auto-apply had nothing to take — proving the credit truly left | Bill anatomy per BR-BIL-011; aging normal; delivery queued | BR-PAY-010 |
| 7 | **INVARIANCE** — the payment, allocations, refund and receipt rows are all append-only; the credit existed exactly Jul 19 → Jul 24 and its lifecycle is fully reconstructable; refund excluded from collection % (purpose-aware reporting) | — | No UPDATE on any money row; tie-outs hold; every step audited (hard rule 7) | BR-PAY-002 · hard rule 4 |
