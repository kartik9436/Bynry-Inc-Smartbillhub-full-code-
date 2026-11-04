# J12 — NSF life (pay → clear → bounce → repeat → cash-only flag at 2nd NSF → recovery)

---
id: J12
tier: 2
rules: [BR-PAY-013, BR-PAY-021, BR-PAY-002, BR-PAY-010, BR-PAY-024, BR-PAY-036, BR-BIL-001, BR-BIL-007, BR-LED-003, BR-REP-010]
stories: [US-PAY-001, US-PAY-009, US-PAY-006, US-PAY-005, US-CUS-012, US-LED-003, US-REP-007]
# journey→story wiring sweep pending: story frontmatter `journeys:` updated in a later sweep (00-e2e-design.md §6)
---

**Intent.** Two bounced checks, one account, three months. Proves the full BR-PAY-013 machine: a bounce is a CLEARING-side event (BR-PAY-021) that reverses append-only, reinstates AR at the ORIGINAL due date (the late-fee clock never reset), auto-adds the NSF charge code — the frozen PE-7 **322.87** — increments `nsf_count`, and at the tenant default N=2 trips the cash-only/no-autopay privilege flag. Recovery money is still ALWAYS taken (BR-PAY-036); nothing auto-clears the flag.

**Fixture.** Tenant brazos-bend · ACC-1042 · July bill: current 247.87 + prior 45.00 = due **292.87** (WE-1), due date **Jul 22** · NSF charge code **$30.00** (tenant-config, own GL) · NSF privilege threshold N=2 (default, config) · month-2/3 amounts and running balances **engine-computed** (00-e2e-design.md §5).

| # | Date · action | Handoff contract (what this step leaves) | Downstream assertions (bill · ledger · reports · queue · audit) | Rule |
|---|---|---|---|---|
| 1 | **Jul 18** — check **292.87** recorded (posting Jul 18 · clearing Jul 21 — both dates, always) | On-time by POSTING date; allocations per BR-PAY-010; receipt auto-queued (BR-PAY-024) | Ledger DR cash / CR AR 292.87; S32 "today total" posting basis, method mix clearing basis (BR-REP-010); audit | BR-PAY-021/022 |
| 2 | **Aug 3** — bank returns the check (clearing-side failure) → **NSF**: reversing payment row **−292.87** (append-only), allocations reversed, AR reinstated at the ORIGINAL Jul 22 due date, NSF charge **+30.00** auto-added → balance **322.87** (PE-7); `nsf_count`=1 | Original payment row untouched; reversing row + fee line linked; late-fee clock runs from Jul 22 as if the payment never happened | Ledger: reversing pair + fee line in TB (LE V-2 pattern); late fee assessable on the overdue portion after grace (BR-BIL-001); S32 failed-payments panel shows the NSF; aging jumped on posting basis; audit | **BR-PAY-013** · BR-PAY-002 |
| 3 | **Aug 5** — customer pays again (check, clears); balance chain engine-computed | `nsf_count` stays 1; no flag yet (N=2); receipt queued | Books balanced; account leaves the failed panel | BR-PAY-013 |
| 4 | **Sep 9** — the September check bounces → 2nd NSF: same reversing mechanics + $30 fee → **`nsf_count`=2 → cash-only/no-autopay privilege flag trips** (tenant default N=2) | Flag on the account, visible at payment entry and on the header | Reversing pair + fee line again; audit row for the flag trip; NSF count on account panel | **BR-PAY-013** |
| 5 | **Sep 15** — customer offers a check; staff see the flag and take **cash** instead — money is ALWAYS accepted, in any state (BR-PAY-036); allocated oldest-first; balance clears (engine-computed) | Cleared cash payment; receipt queued; acceptance changes no account state | DR cash / CR AR; aging returns to Current; collection % reflects on posting basis (BR-REP-009) | BR-PAY-036 · BR-PAY-010 |
| 6 | **Oct 1** — recovery epilogue: the cash-only flag REMAINS — no rule auto-clears it; lifting it is an explicit staff config action, audited | Flag state + full NSF history preserved on the account | Audit trail reconstructs both bounces, both fees, the flag trip and any lift — who/when at each step (hard rule 7) | BR-PAY-013 |
| 7 | **INVARIANCE** — no payment row was ever edited (reversals only); the original Jul 22 due date governed every late-fee evaluation; both NSF fees entered via the charge code, never typed | — | Append-only payments (immutability suite); tie-outs hold (BR-LED-007); receipts exist for every CLEARED payment only | BR-PAY-002 · hard rule 4 |
