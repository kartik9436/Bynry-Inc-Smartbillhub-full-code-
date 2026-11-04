# Module — reports

Report library, viewer, builder, scheduling. Owns no financial tables by design (module-boundary rule).

**Owns (B2):** none — read-models only over other modules. (Run/definition/schedule storage rows are metadata-only and pending B2 anchoring — pack report R-1, DDL 🔒.)
**Screens:** S44–S47 Reports · S7 dashboard content · chip/label consumption on S32
**Boundary rule (B1):** no other module writes this module's tables; cross-module reads via service functions only.

**v4 update (r2/r3):** + Account ledger report (S59) and By-premises summary (S60); premises = locations of ONE legal entity (no multi-entity). + Operational dashboard (S7) as EP-REP-05.

**v5 update (2026-08-09 — pack authored):** BR-REP-001..018 ALL CONFIRMED (date-basis law, dual-basis remittance, live vocabularies, canned-set additions, KPI formulas RQ-1..9, ops-chip placement RQ-7, dunning-default reading RQ-8, W6 email RQ-9, IS-11 downloads + 3-day retention). Ownership split settled: **ledger owns** the TB/account-ledger/by-premises/remittance STORIES (US-LED-007..010/014 — S44 routes to them); **reports owns** the report CENTER (S44 catalog · S46 viewer · IS-11 download pipeline · S45 runs/schedules · S47 builder) + the canned reports not owned elsewhere (AR aging/DSO, billing register w/ bill_type, revenue by service & rate, payments by method w/ purpose, read completeness, high-usage, new & closed accounts, and the six audit-added reports) + the S7 dashboard and the RQ-7 ops chips. Builder v1 = the six A14 datasets, closed list (new entities canned-only). Scheduled-report email = outbound-queue rows marked W6-deferred (BR-REP-017/BR-NOT-005); v1 delivery = download, files retained 3 days (tenant-config, IS-11). Pack: EP-REP-01..05, US-REP-001..018 (05-user-stories.md index; stories in 06-epics/). Every money surface basis-labeled per BR-REP-001 — an unlabeled money render is a test failure by contract.
