# T5-17 — Third consecutive estimate (field visit forced, never auto-estimated)

---
id: T5-17
tier: 5
guards: [BR-MET-027, BR-MET-026, BR-MET-028, BR-BIL-015]
stories: [US-MET-014, US-MET-018, US-BIL-003]
# journey→story wiring sweep pending: story frontmatter `journeys:` updated in a later sweep (00-e2e-design.md §6)
---

**Intent.** Max 2 consecutive estimates per meter; the 3rd consecutive miss FORCES a field visit and is never auto-estimated (BR-MET-027, OQ-003 closed). Estimates compound: a third straight guess can drift far from the register and turns the eventual true-up into a dispute. The estimation job must refuse to mint estimate #3, route the meter to the chase/field-visit list, and let billing make its explicit per-case choice — never a silent guess.

**Fixture.** Tenant brazos-bend · meter MTR-0522 on ACC-1188 · May read: estimated (1st consecutive, trailing-3 method) · June read: estimated (2nd consecutive) · July cycle read window closes with MTR-0522 missing again.

| # | Actor + action | Expected refusal (IS-7 outcome) | Downstream assertions (nothing changed) | Guard |
|---|---|---|---|---|
| 1 | The estimation job runs for CYC-A July over all missing meters | MTR-0522 is SKIPPED: consecutive-estimate count = 2, so no 3rd estimate is generated; other missing meters (count < 2) estimate normally per trailing-3 | Zero meter_reads row for MTR-0522/July; existing May/June rows still labeled "estimated · 1st/2nd consecutive" (BR-MET-028); no register current_value touched | BR-MET-027 · BR-MET-026 |
| 2 | System routes MTR-0522 to the field-visit force list (chase list / needs-attention) | Meter appears with reason "3rd consecutive miss — field visit required"; no staff action can substitute an estimate | Chase list row exists; completeness bar counts the meter outstanding (BR-MET-057) | BR-MET-027 · BR-MET-060 |
| 3 | Probe: clerk opens the Missing-flag fix actions and tries Estimate on MTR-0522 | The estimate action is refused/absent at count 2 — the per-flag actions (estimate / field-visit / skip) exclude estimate for a 3rd consecutive; only field-visit or skip remain | No estimated row minted; a Skip (if chosen) requires reason + audit and leaves the meter missing for billing to decide (BR-MET-030) | BR-MET-027 · BR-MET-030 |
| 4 | Billing Clerk runs RUN-2607-A; S31.2 Reads tab shows ACC-1188 with the missing meter | Per-case staff choice = estimate / hold / bill-without-service (BR-BIL-015) — and "estimate" for THIS meter is off the table per step 3; clerk holds the account | ACC-1188 enters Pending-billing queue (KPI chip, aging, escalation); no draft; ledger untouched; the CHOICE writes the audit trail (BR-BIL-015), the refusal itself writes nothing (BR-AUD-001 scope) | BR-BIL-015 · BR-MET-027 |
| 5 | RECOVERY — the ratified door: field visit obtains the ACTUAL register read (44,102 on 2026-07-16); clerk enters it manually; true-up prices by register arithmetic against the two billed estimates at current-period rates | Actual read commits; consecutive-estimate counter resets; true-up per BR-MET-029 computes (actual − last_actual) × multiplier − Σ estimated billed (machine-computed expectation — no hand math in this file); ACC-1188 bills via catch-up sub-run | Estimates reversed into truth exactly once; links from true-up to corrected estimates recorded; queue drains | BR-MET-029 · BR-BIL-015 |
