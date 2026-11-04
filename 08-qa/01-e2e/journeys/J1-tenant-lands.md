# J1 — Tenant lands

---
id: J1
tier: 1
stories: [US-TEN-001, US-TEN-002, US-TEN-003, US-TEN-007, US-LED-005]
---

<!-- FRONTMATTER ADDED 2026-08-15 (DEF-102). This file predates the convention
     and carried none, so the wiring index computed `stories: 0` and a readiness
     of None — neither ready nor unready — and this journey appeared in no count
     anyone quoted. The list above is a STRAIGHT TRANSCRIPTION of the story IDs
     already named in this file's own step table; nothing was chosen. -->
**Fixture.** (authored 2026-08-22, CR-014 — this file predated the Fixture convention and declared nothing) A provisioned tenant, and nothing more — J1 walks signup's OUTPUT, so its cohort IS provisioning's contract: tenant + owner membership + trial exist atomically (BR-TEN-010) · the SHARED chart's 13 rows present and every GL designation resolving (step 3b — per-service 41xx rows only for enabled services, BR-BIL-067) · one `tenant_services` row per signup-chosen service, each with its `revenue_account` pointer (step 3c) · reference lists populated. The seeder (`seed_journey_fixture.py seed_j1`) VERIFIES these rather than minting anything, and refuses if provisioning left a gap.

S1→S114 signup → provisioning → seeding → post-signup checklist (S62).
| # | Story | Handoff contract to next step |
|---|---|---|
| 1 | US-TEN-002* (wave-8 onboarding, IDs TBD) | wizard payload complete |
| 2 | US-TEN-001 provisioning | tenant + owner membership + trial exist, atomic (BR-TEN-010) |
| 3 | US-TEN-002 seeding | reference lists populated per fixtures; tenant-touched rows never overwritten later |
| 3b | US-LED-005 chart of accounts | the **SHARED** chart exists — cash, AR, unbilled AR, the deposit and credit liabilities, opening clearing, minimum-bill adjustment, the two fee-revenue accounts and the three expense accounts (13 rows), **and every one of the eleven GL designations resolves**. Per-service REVENUE accounts are NOT here: since the PO's OQ-115 ruling (2026-08-11, BR-BIL-067) a tenant is seeded only what it sells, so 4110/4115 arrive with Water and 4140 arrives the day Gas is switched on. Downstream may assume a designation resolves; downstream may **NOT** assume any `41xx` service account exists for a service this tenant has not enabled |
| 3c | US-TEN-007 services enabled | one `tenant_services` row per service chosen at signup, each pointing at the revenue accounts minted for it (`ledger.services.ensure_service_revenue_accounts` — the same call the S8 toggle makes later). **That pointer is a DEFAULT, not a fixture:** the tenant may re-point it through `update_tenant_service`, and no re-seed overwrites it, so anything reading a service's GL account must read `tenant_services.revenue_account` and never `chart.SERVICE_REVENUE_ACCOUNTS` . ⚠ **AND SINCE 2026-08-28 THE SAME ROW CARRIES THE MEASUREMENT DECLARATION (`BR-TEN-810`, `DEF-2310`):** provisioning leaves every service `metered=True` and `billed_uom=NULL` — *nothing declared* is *metered*, and `NULL` is *billed in the register's own unit* — and a downstream lane must read `tenancy.selectors.unmetered_service_codes()` / `service_billed_uoms()` rather than assuming a meter exists. A utility changes either through `update_tenant_service` on S8, on a service that is switched ON or OFF, and the change is FORWARD-ONLY: nothing already issued moves |
| 4 | US-TEN-003 checklist | company-profile gaps computed live; links resolve to Settings tabs |
