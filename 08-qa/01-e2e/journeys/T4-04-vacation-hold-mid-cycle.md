# T4-04 — Active → Vacation hold mid-cycle → Active (x = billable → y = billable-base-only → billable)

---
id: T4-04
tier: 4
rules: [BR-BIL-028, BR-CUS-055, BR-MET-053, BR-REP-012, BR-BIL-004, BR-BIL-011]
stories: [US-CUS-008, US-MET-007, US-BIL-005, US-BIL-007]
# journey→story wiring sweep pending: story frontmatter `journeys:` updated in a later sweep (00-e2e-design.md §6)
---

**Intent.** x = status Active (behavior class billable); y = Vacation hold/Suspended (behavior class **billable-base-only** per the BR-CUS-055 seed) starting mid-cycle, then back to Active. The boundary matters because the hold does NOT stop billing — it changes WHAT bills: usage lines stop at the hold date (interim read), base charges and flat services continue the full month (BR-BIL-028). Getting this wrong either bills phantom usage for an empty house or silently waives base revenue. Figures come from the frozen WE-12 workbook.

**Fixture.** Tenant brazos-bend · ACC-1046, Residential Standard (WE-12 account) · hold starts **Jul 16** · interim read committed Jul 15 · hold ends Aug 10 (return read committed).

| # | Action | Upstream effect (what recomputes) | Downstream assertions | Rule |
|---|---|---|---|---|
| 1 | Clerk sets status Active → **Vacation hold** effective Jul 16 (account header action); interim read committed for Jul 15 | Status row changes to the reference-data status whose behavior class = billable-base-only; interim read enters the ratified read lifecycle (staged → committed) | audit row with before/after status; account header pill renders the new status (US-CUS-008); dunning posture unchanged (nothing is past due here) | BR-CUS-055 · BR-MET-053 |
| 2 | Jul cycle bill run | **WE-12 recompute**: usage bills through Jul 15 — TOU 60/95/160 → 13.20+13.30+14.40 · water 3.1 kgal → 12.40 · sewer 4.96; **bases + flat services continue full month**: elec 12.00 + water 8.00 + trash 18.00. Taxable **$96.26** → tax **$9.10** → total **$105.36** | bill lines exactly per WE-12; one balanced JE (DR AR 105.36 / CR revenue+tax buckets); delivery-queue row; audit | BR-BIL-028 · BR-BIL-011 |
| 3 | Harness checks reports during the hold | — | "Active accounts" KPI still COUNTS this account (Active + Marked disconnect + Vacation hold per BR-REP-012), basis-labeled headers per BR-REP-001; no usage expected on the chase list for the held span | BR-REP-012 · BR-REP-001 |
| 4 | Clerk sets **Vacation hold → Active** effective Aug 10; return read committed | Behavior class returns to billable; Aug usage bills from the Aug 10 return read forward, base again full month (Aug figures engine-computed, §5 harness — the WE-12 pattern applied to the resume boundary) | Aug bill shows usage span starting at the return read; audit row for the status change | BR-CUS-055 · BR-BIL-028 |
| 5 | **INVARIANCE** — what must NOT have changed | July's issued $105.36 bill is immutable — ending the hold NEVER re-opens or re-rates the hold-period bill; no usage line was ever created for Jul 16–31 | issued invoice/lines byte-identical; ledger for July unchanged after step 4; status history append-only with both transitions + actors | BR-BIL-004 · hard rule 4 |
