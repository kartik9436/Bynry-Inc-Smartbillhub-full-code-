# T4-01 — Plan change mid-cycle (x = old plan snapshot → y = new plan snapshot, split-period bill)

---
id: T4-01
tier: 4
rules: [BR-CUS-014, BR-CUS-041, BR-CUS-029, BR-CUS-011, BR-CUS-062, BR-BIL-004, BR-BIL-011]
stories: [US-CUS-016, US-CUS-017, US-CUS-006, US-RAT-012, US-BIL-007]
# journey→story wiring sweep pending: story frontmatter `journeys:` updated in a later sweep (00-e2e-design.md §6)
---

**Intent.** x = account billed on plan snapshot P-old; y = account billed on plan snapshot P-new, changed mid-cycle via the S23 Change-plan flow. The boundary matters because billing prices from the ACCOUNT'S plan snapshot as of service date (BR-CUS-014 sc.6): a mid-cycle change must produce ONE bill with TWO period-labeled groups — days before the effective date priced on P-old, days from it on P-new, base + usage prorated by calendar days (B4.3, GT-3) — and must NEVER reprice already-issued history. Upstream = the snapshot chain; downstream = the split bill, one balanced posting, and the audit trail on both unit and account sides.

**Fixture.** Tenant brazos-bend · ACC-1042 (Residential Standard, active, cycle Jul 1–31) · target plan "Residential Standard v2-shape" (published, service-compatible per BR-RAT-030) · change effective Jul 16. Split-group dollar values are engine-computed per 00-e2e-design.md §5 (04-e2e-expected-gen.py); the proration law they follow is the WE-6/WE-18 pattern (B4.3).

**Fixture amendment (2026-08-22, CR-014 · DEF-556).** Seeded by `seed_journey_fixture.seed_t4_01` over the shared flat cohort. The changing account is **ACC-2042** on the **August** cycle, not ACC-1042 on Jul 1–31: an issued bill posts its journal entry at its service date, and ACC-1042's July is the finance-signed WE-1 **247.87** inside a month that foots at **553.69** (OQ-218: test data is shaped to fit signed figures, never the other way round). The target plan is **E2E Flat Residential v2-shape**, published and electric-compatible. Nothing signed moves — this journey's split-group dollar values are engine-computed per 00-e2e-design.md §5, so the account and the month are not what it asserts.

| # | Action | Upstream effect (what recomputes) | Downstream assertions | Rule |
|---|---|---|---|---|
| 1 | Billing Clerk opens S23 on ACC-1042, picks the new published plan, effective **custom Jul 16** (≥ current unbilled period start) | Proration preview renders: two sub-periods Jul 1–15 / Jul 16–31, base and usage both prorated by calendar days; no write yet | Preview only — zero rows written before confirm | BR-CUS-041 · B4.3 |
| 2 | Clerk confirms (step 3) | APPEND-ONLY snapshot chain: old `account_plan_assignments` row closed `assigned_to = Jul 15`; new row `assigned_from = Jul 16`, source `change_plan`, actor + reason; `unit_plan_assignments` history row written IN SYNC (unit and account never diverge) | audit_log rows for both account- and unit-side changes (who/when/from→to/reason); notification per US-CUS-017 written to the outbound queue (BR-NOT-005), never sent inline | BR-CUS-014 sc.3 · BR-CUS-029 · BR-CUS-011 |
| 3 | Cycle bill run executes for Jul (period Jul 1–31) | Rating engine resolves the snapshot AS OF EACH SERVICE DATE: Jul 1–15 priced on P-old, Jul 16–31 on P-new; tier spans scale to each prorated sub-period (BR-RAT-002); bases prorated 15/31 + 16/31 | Bill = ONE document, two period-labeled line groups, each line GL-stamped; figures engine-computed (§5 harness); ONE balanced JE (DR AR / CR per-GL buckets) via posting service only | BR-CUS-014 sc.6 · BR-BIL-011 · GT-3 |
| 4 | Harness inspects reports + queues after issue | — | S7/S36 billed-revenue KPI moves by the issued total, POSTING basis, header labeled (BR-REP-001); delivery-queue row per channel (BR-BIL-016); audit rows for issue | BR-REP-001 · BR-BIL-016 |
| 5 | **INVARIANCE** — what must NOT have changed | No recompute of any prior period: June's issued bill byte-identical; no proration reaches back before Jul 16's boundary except the ratified split of the CURRENT unbilled period | Deposit held stays exactly as set at move-in — plan change triggers NO deposit recompute in v1 (BR-CUS-062); all prior `account_plan_assignments` rows immutable (append-only chain intact); ledger trial balance for June unchanged | BR-BIL-004 · BR-CUS-062 · hard rule 4 |
