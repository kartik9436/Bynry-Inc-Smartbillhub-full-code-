# T5-16 — Read on a retired meter (error stands; the swap flow is the door)

---
id: T5-16
tier: 5
guards: [BR-MET-052, BR-MET-015, BR-MET-016]
stories: [US-MET-008, US-AST-008, US-AST-009]
# journey→story wiring sweep pending: story frontmatter `journeys:` updated in a later sweep (00-e2e-design.md §6)
# Assets grounding: retirement-is-terminal is exercised via US-AST-008 ("Retire an asset (terminal)") — no assets
# BR-ID is asserted beyond that; the read-side refusal cites BR-MET-052 (read on retired meter = error).
---

**Intent.** A read filed against a RETIRED meter is a VEE ERROR (BR-MET-052): retired assets no longer measure anything on a unit, so accepting their reads would bill consumption from a meter that isn't there — the classic symptom of an unrecorded meter swap. The error must stand until resolved by an explicit disposition; if a swap really happened, the asset-reassign flow with final-read capture is the ratified path.

**Fixture.** Tenant brazos-bend · meter MTR-0299 retired 2026-06-30 (US-AST-008, terminal; replacement MTR-0451 active on Unit 4B since 2026-07-01) · July import file contains a row: MTR-0299, 2026-07-14, 45,340, channel `total`.

| # | Actor + action | Expected refusal (IS-7 outcome) | Downstream assertions (nothing changed) | Guard |
|---|---|---|---|---|
| 1 | Clerk imports the July file; validation runs at staging | The MTR-0299 row flags severity ERROR "read on retired meter" (retirement date shown); the MTR-0451 rows validate normally | Staged only; zero meter_reads committed for MTR-0299; retired asset row untouched (terminal state stands) | BR-MET-052 |
| 2 | Clerk attempts batch commit with the error unresolved | Refused: errors must be resolved before post — 422 class, IS-7 inline-validation listing the blocking row | No committed read on MTR-0299; billing inputs for Unit 4B come only from MTR-0451 | BR-MET-015 |
| 3 | Probe: clerk tries manual single entry (US-MET-007) against MTR-0299 directly | Same ERROR at validation — the guard is meter-state-driven, not import-path-driven | Nothing committed; audit: disposition rows (when made) are the ratified trail (BR-MET-015) | BR-MET-052 |
| 4 | Probe: clerk attempts to un-retire MTR-0299 to sneak the read through | Retirement is terminal (US-AST-008) — no reactivate action exists on a retired asset | Asset status unchanged; assignment history intact | US-AST-008 scope |
| 5 | RECOVERY — the ratified doors: (a) the value belongs to replacement MTR-0451 → REJECT the row, re-file under the correct meter; (b) the read predates retirement → correct the DATE and re-validate; (c) an unrecorded swap is discovered mid-cycle → asset reassign flow with final-read capture (US-AST-009) records the closing read on the old meter and opens the new one, then reads import cleanly | Chosen disposition stored with reason per row; commit proceeds once errors clear; the final read on the retiring meter enters through the reassign flow, not the bulk file | Unit 4B's July consumption computes across the swap correctly (final read + opening read); lineage complete and visible | BR-MET-015 · US-AST-009 |
