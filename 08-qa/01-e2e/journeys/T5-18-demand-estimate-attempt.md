# T5-18 — Demand estimate attempt (a peak is NEVER estimated)

---
id: T5-18
tier: 5
guards: [BR-MET-062, BR-MET-058, BR-MET-051, BR-MET-049]
stories: [US-MET-014, US-MET-017]
# journey→story wiring sweep pending: story frontmatter `journeys:` updated in a later sweep (00-e2e-design.md §6)
---

**Intent.** A missing `demand`-channel value is NEVER auto-estimated — it always forces a field visit (BR-MET-062: "a peak drives kW dollars; an estimated peak is a dispute"). Estimation is per-channel (BR-MET-058), so the kWh channels of the same meter may estimate from their own history while demand must not — the journey proves the engine makes exactly that split and that no estimated demand row can exist anywhere, ever.

**Fixture.** Tenant brazos-bend · Commercial-TOU-demand fixture account ACC-2077 · meter MTR-0713, required channels `total · tou_on · tou_mid · tou_off · demand` (BR-MET-049) · July cycle read: TOU channels missing AND demand missing (reader skipped the site).

| # | Actor + action | Expected refusal (IS-7 outcome) | Downstream assertions (nothing changed) | Guard |
|---|---|---|---|---|
| 1 | Estimation job runs for the missing MTR-0713 channels | kWh channels (total + TOU windows) estimate independently from their own trailing histories (1st consecutive); the `demand` channel is REFUSED — no estimate generated, reason "demand never estimated — field visit required" | Estimated rows exist only for kWh channels, each labeled method + consecutive no; ZERO meter_reads row with channel=demand status=estimated — asserted for this meter and as a GLOBAL invariant across the whole database | BR-MET-062 · BR-MET-058 |
| 2 | MTR-0713 routes to the field-visit list for the demand value | Chase-list row cites the missing demand channel; completeness stays incomplete (plan requires demand) so billing is gated exactly as T5-13 | No draft bill for ACC-2077; no demand line priced; kW rate never applied to a guessed peak | BR-MET-062 · BR-MET-049 |
| 3 | Probe: clerk opens fix actions on the missing demand read and looks for Estimate | Estimate is absent/refused for channel=demand regardless of consecutive count (this is stricter than BR-MET-027's 2-estimate allowance — demand gets ZERO) | No estimated demand row; Skip (reason + audit) leaves the account for billing's explicit per-case choice | BR-MET-062 · BR-MET-030 |
| 4 | Probe: `POST /api/reads {meter: MTR-0713, channel: demand, status: estimated, ...}` direct | Refused at validation — estimated status on a demand channel is not writable by any path | Nothing written; audit: attempt-logging not ratified (BR-AUD-001 scope) — assert zero read rows | BR-MET-062 |
| 5 | RECOVERY — the ratified door: field visit reads the demand register (peak 42.7 kW, reset noted per BR-MET-051); clerk enters it via channel-based manual entry (US-MET-017) | Actual demand row commits (channel=demand, status=ok); completeness passes; ACC-2077 bills via catch-up sub-run with the demand line priced on the ACTUAL peak | Exactly one demand value per cycle, always actual; register reset recorded; issue-side writes audited | BR-MET-051 · BR-MET-049 |
