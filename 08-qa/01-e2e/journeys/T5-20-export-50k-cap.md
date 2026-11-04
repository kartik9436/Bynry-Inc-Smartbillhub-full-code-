# T5-20 — CSV export over 50,000 rows (the cap rejects)

---
id: T5-20
tier: 5
guards: [BR-SHL-016, NFR-3]
stories: [US-SHL-008, US-BIL-025, US-REP-003]
# journey→story wiring sweep pending: story frontmatter `journeys:` updated in a later sweep (00-e2e-design.md §6)
---

**Intent.** CSV exports are server-side streamed under RLS per IS-9, and any export over 50,000 rows is REJECTED (BR-SHL-016; NFR-3 — no unbounded endpoints; cap PO-revisitable but currently law). An unbounded export is a memory/timeout incident and a data-egress hazard in one. The system must refuse with the count and point at narrowing, not silently truncate.

**Fixture.** Large-tenant fixture lakeview-mud (the 40k-account planning shape, B6 capacity table) · S30 bills list unfiltered = 62,400 rows for FY totals · filtered to period 2026-07 = 3,480 rows.

| # | Actor + action | Expected refusal (IS-7 outcome) | Downstream assertions (nothing changed) | Guard |
|---|---|---|---|---|
| 1 | Clerk hits Export CSV on the unfiltered S30 bills list (62,400 rows) | Refused pre-stream: row count exceeds 50,000 — 422 class; IS-7 failed state shows the actual count and instructs narrowing filters; NO partial/truncated file is produced | Zero bytes streamed; no generated file recorded; no export audit row (nothing executed — BR-SHL-016 audits performed money-table exports; BR-AUD-001 scope) | BR-SHL-016 |
| 2 | Same probe on the audit viewer S61 (US-AUD-006 export) and a builder report export (US-REP-003 50k guard) with >50k result sets | Same refusal on every export surface — the guard is the shared IS-9/IS-11 contract, not per-screen | No files; result-set counts computed server-side before streaming | BR-SHL-016 · NFR-3 |
| 3 | Adversarial probe: `GET /api/bills/export?limit=none` styled calls trying to bypass the UI | Server enforces the cap regardless of parameters; pagination remains bounded everywhere | No unbounded endpoint exists (NFR-3); RLS still scopes every streamed row | NFR-3 · BR-SHL-016 |
| 4 | Contrast: clerk filters to period 2026-07 (3,480 rows) and exports | Allowed: server-streamed under RLS; completes | File contains exactly the filtered tenant rows; money-table export writes audit_log (BR-SHL-016) | BR-SHL-016 |
| 5 | RECOVERY — the ratified doors for big pulls: narrow filters into ≤50k slices, or use the reporting/export paths built for volume (scheduled report files per IS-11, ledger dimension CSV extracts per BR-LED-004) | Sliced exports succeed; each is audited; large analytic needs route through reports/ledger extracts | Every successful export bounded, tenant-scoped, audited | BR-SHL-016 · BR-LED-004 |
