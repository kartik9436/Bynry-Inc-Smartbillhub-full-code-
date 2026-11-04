# T5-13 — TOU incomplete channel set (the completeness gate holds billing)

---
id: T5-13
tier: 5
guards: [BR-MET-049, BR-MET-059, BR-MET-061, BR-BIL-015]
stories: [US-MET-008, US-MET-017, US-MET-018, US-BIL-002]
# journey→story wiring sweep pending: story frontmatter `journeys:` updated in a later sweep (00-e2e-design.md §6)
---

**Intent.** The unit's plan determines the REQUIRED read set per meter — a TOU plan needs per-window channel records (BR-MET-049, channel model BR-MET-059) — and completeness is enforced as a VEE validation BEFORE billing. A TOU account with a missing window must never be priced on a partial set (the missing window's kWh would be silently dropped or mis-priced). The gate must hold the account out of drafts, visibly, until the set is complete.

**Fixture.** Tenant brazos-bend · Commercial-TOU fixture account ACC-2077 (the design §5 Commercial-TOU-demand family) · meter MTR-0713 requires channels `total · tou_on · tou_mid · tou_off` · July import supplies total 2,140 / tou_on 512 / tou_off 1,124 — **`tou_mid` missing**.

| # | Actor + action | Expected refusal (IS-7 outcome) | Downstream assertions (nothing changed) | Guard |
|---|---|---|---|---|
| 1 | Clerk commits the July batch for MTR-0713 (three of four required channels) | Rows commit individually (each valid alone) — but the plan-driven completeness VEE marks the meter's period set INCOMPLETE: missing `tou_mid` | Three meter_reads rows exist (one per channel, BR-MET-059); no synthetic `tou_mid` row invented; completeness bar + chase list show the gap (BR-MET-057) | BR-MET-049 · BR-MET-059 |
| 2 | Billing Clerk starts run RUN-2607-A; opens S31.2 "Check what we found" → Reads tab | ACC-2077 listed as a reads-completeness exception (completeness % per BR-MET-049); it cannot silently reach drafts | No draft bill for ACC-2077; the other 1,239 accounts draft normally; zero priced lines exist for the incomplete meter | BR-MET-049 · BR-BIL-015 |
| 3 | Clerk attempts to force-issue ACC-2077 from the exceptions table | Refused: the per-case choices are estimate / hold / bill-without-service (BR-BIL-015) — "price the partial TOU set" is not offered anywhere | Account enters Pending-billing queue if held (KPI chip, aging); ledger untouched; audit: the per-case CHOICE writes the trail when made (BR-BIL-015), the refusal itself writes nothing (BR-AUD-001 scope) | BR-BIL-015 |
| 4 | Adversarial probe: clerk hand-enters a `tou_mid` value of 504 so that Σwindows equals total exactly, then edits `total` to force agreement | Manual channel entry is allowed (US-MET-017) — but the TOU sum-sanity check (Σwindows vs total ±1%) runs as WARNING requiring explicit accept + reason; committed rows are never editable (supersede only) | Any accepted warning stores disposition+reason (BR-MET-015); no silent pass; original rows immutable | BR-MET-061 · BR-MET-053 |
| 5 | RECOVERY — the ratified door: obtain the real `tou_mid` read (manual channel entry US-MET-017, or per-channel estimation from its own trailing history if the estimate rules allow, BR-MET-058); completeness turns green; bill via catch-up sub-run | Fourth channel row commits; VEE completeness passes; catch-up sub-run (parent-linked, scope-keyed) prices ACC-2077 on the full window set from the account snapshot | Exactly one bill for ACC-2077; TOU lines priced per window; queue drains; all issue-side writes audited | BR-MET-049 · BR-MET-058 · BR-BIL-015 |
