# T5-27 — Tie-out drift injection (red flag + release blocker, detected live)

---
id: T5-27
tier: 5
guards: [BR-LED-007, BR-LED-001, NFR-17]
hard_rules: [5]
stories: [US-LED-004, US-LED-001]
# journey→story wiring sweep pending: story frontmatter `journeys:` updated in a later sweep (00-e2e-design.md §6)
# HARNESS NOTE: step 2's injection is a TEST-ONLY superuser write in a sandboxed database, simulating the sole
# possible cause of drift per BR-LED-007 ("only possible via posting-service bypass"). It exercises the DETECTOR;
# it is not a supported code path and must never exist outside the isolation sandbox.
---

**Intent.** Subledger tie-outs render live on S36 — deposit-liability GL = Σ deposits held · AR GL = Σ account balances · tax payable = remittance outstanding — and ANY drift is a red flag AND a release blocker (BR-LED-007, NFR-17). Drift is only possible if something bypassed the posting service (hard rule 5), i.e. a defect. This journey proves both halves: the application refuses out-of-service ledger writes, and when a bypass is simulated anyway, the detector fires loudly instead of the books lying quietly.

**Fixture.** Sandboxed clone of tenant brazos-bend at a green state: all three tie-outs equal · deposit-liability GL balance $12,450.00 = Σ deposits held.

| # | Actor + action | Expected refusal (IS-7 outcome) | Downstream assertions | Guard |
|---|---|---|---|---|
| 1 | Application-level probe: a module attempts to write journal_lines without the posting service (contract check across billing/payments/customers code paths) | No such path exists — the ledger posting service is the SOLE writer; module writes route through posting contracts only (US-LED-001) | Every journal_lines row traces to a posting-service call; zero out-of-service writes in the green state | hard rule 5 · BR-LED-001 |
| 2 | Harness (sandbox superuser) injects a one-sided journal line: DR deposit-liability $500.00, no balancing credit — simulating a posting-service bypass defect | The write "succeeds" at the DB (that IS the simulated defect) — the refusal under test is downstream: the books must not present as healthy | Deposit-liability GL now $11,950.00 ≠ Σ deposits held $12,450.00 — drift of $500.00 exists | BR-LED-007 |
| 3 | Finance user opens S36 | Tie-out panel renders the deposit-liability row RED-FLAGGED with the computed drift; the other two tie-outs still green; no auto-"correction" is attempted (the system never papers over drift) | Flag visible without any manual refresh ritual; drift amount and the two sides shown; underlying rows untouched by the detector (read-only check) | BR-LED-007 |
| 4 | CI/release pipeline runs the tie-out suite against the sandbox | Release BLOCKED: any drift = release blocker, zero tolerance | Pipeline failure names the tie-out and the drift; no deploy proceeds while drift exists | BR-LED-007 · NFR-17 |
| 5 | Probe: user attempts to dismiss/acknowledge the red flag away | No dismiss path exists — the flag derives from the equality check and clears ONLY when the books re-balance | Flag persists across sessions/roles while drift exists | BR-LED-007 |
| 6 | RECOVERY — the ratified door: fix the DEFECT (the bypass), then repair the books through the posting service — a balanced correcting JE (Finance role, reason + audit) restoring the $500.00; never a direct row edit (T5-01) | Correcting entry posts balanced; deposit-liability GL returns to $12,450.00 = Σ deposits held; tie-out re-renders green; release gate passes | Injected row remains in history (append-only) with its balanced correction linked; full audit trail of the repair | BR-LED-003 · BR-LED-007 · hard rule 5 |
