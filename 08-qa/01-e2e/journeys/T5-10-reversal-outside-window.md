# T5-10 — Payment reversal outside its window / cross-period without approval

---
id: T5-10
tier: 5
guards: [BR-PAY-011, BR-PAY-030, BR-PAY-002, NFR-15]
stories: [US-PAY-010]
# journey→story wiring sweep pending: story frontmatter `journeys:` updated in a later sweep (00-e2e-design.md §6)
---

**Intent.** Reversal windows are ratified per rail — ACH 60 days, card 120 days, check unlimited (NSF) — and any reversal of a PAID or cross-period payment requires Admin/Executive approval, always as reversing entries with plain-language consequence messaging before confirm (BR-PAY-011/030). The system must refuse a window-exceeded reversal (no override path is ratified) and refuse a cross-period reversal attempted without the approval, leaving the payment, its allocations, and the ledger untouched.

**Fixture.** Tenant brazos-bend · PMT-3301: ACH $97.41 on ACC-1042 (money-triples row `flat,cycle,full`), cleared **75 days ago** · PMT-3308: card $97.41 cleared 20 days ago against a bill in a prior (closed) period · actor Priya, Billing Clerk.

| # | Actor + action | Expected refusal (IS-7 outcome) | Downstream assertions (nothing changed) | Guard |
|---|---|---|---|---|
| 1 | Priya opens PMT-3301 (ACH, day 75) and selects Reverse | Refused: ACH window is 60 days — 409/422 class; IS-7 failed state names the rail, the window, and the elapsed days; no approval path is offered (none is ratified for window-exceeded) | payments row untouched; allocations rows untouched; account balance unchanged; ledger balanced, unchanged; audit: attempt-logging not ratified (BR-AUD-001 scope) — assert zero money writes | BR-PAY-011 |
| 2 | Priya replays the same via `POST /api/payments/PMT-3301/reverse` | Same server-side refusal — UI window check was convenience only | Identical no-change assertions; no reversing row minted | BR-PAY-011 · NFR-15 |
| 3 | Priya attempts Reverse on PMT-3308 (card, in-window, but paid + cross-period) WITHOUT Admin/Executive approval | Refused: approval-required — IS-7 permission-denied posture (403 class); consequence message previews what a reversal WOULD do (reversing entries, balance effect, prior-period handling) but confirm is gated | No reversing payment row, no reversing allocations, no reversing JE; closed-period totals untouched (any eventual reversal auto-forwards per BR-TEN-038 / T5-09) | BR-PAY-011 · BR-PAY-030 |
| 4 | Contrast: NSF on a CHECK payment cleared 200 days ago | Allowed — check window is unlimited (NSF); the T2 NSF journey carries the money assertions (reinstatement per money-triples `flat,cycle,nsf`: outstanding 127.41, next_late_fee 5.00) | Reversal proceeds only on this ratified rail/window combination | BR-PAY-011 · BR-PAY-013 |
| 5 | RECOVERY — the ratified door for step 3: System Admin (or Executive) approves; Priya re-runs the reversal | Consequence message → explicit confirm → reversing rows post (payment + allocations + JE), all linked to PMT-3308; original rows immutable | Reversing entries balanced; every step audited (BR-AUD-001); allocations rebuilt per BR-PAY-010 on re-application | BR-PAY-011 · BR-PAY-002 |
