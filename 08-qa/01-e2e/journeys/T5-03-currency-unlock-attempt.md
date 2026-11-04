# T5-03 — Currency unlock attempt after first financial record

---
id: T5-03
tier: 5
guards: [BR-TEN-042, NFR-22]
stories: [US-TEN-006]
# journey→story wiring sweep pending: story frontmatter `journeys:` updated in a later sweep (00-e2e-design.md §6)
---

**Intent.** A tenant has exactly ONE currency, LOCKED the moment the first financial record exists (BR-TEN-042). Changing it afterwards would restate every stored NUMERIC(18,6)+CHAR(3) amount's meaning without touching a digit — the worst kind of silent corruption. The system must refuse the change at the settings UI and the API, and historical documents must never restate (NFR-22). (The positive lifecycle — choosing currency before financials — is a T7 journey; the T4 catalog lists this same refusal as transition case "currency change attempt AFTER first financial record".)

**Fixture.** Tenant brazos-bend, currency USD; first financial record exists (issued bill BL-2607-0142, $97.41 — money-triples row `flat,cycle,full`).

**Fixture amendment (2026-08-22, CR-014 / DEF-556).** The first-financial-record anchor is **ACC-2042**'s issued August bill (97.41, `flat,cycle,full`) — the invoice number is allocated by the number series at seed time (e.g. BL-2608-000049 on the 2026-08-22 stack), not the paragraph's sample “BL-2607-0142”, which collides with the signed July book.

| # | Actor + action | Expected refusal (IS-7 outcome) | Downstream assertions (nothing changed) | Guard |
|---|---|---|---|---|
| 1 | System Admin opens Settings → Regional (S8) and tries to change Currency USD → CAD | Currency control renders disabled-with-reason (IS-6): locked since first financial record; no save possible from the UI | tenant settings row unchanged; no audit row (nothing executed — BR-AUD-001 scope) | BR-TEN-042 |
| 2 | Same admin issues `PATCH /api/tenant/settings {currency: "CAD"}` | Refused 409/422 class — validation error naming the lock and the record that armed it; IS-7 inline-validation posture, not permission-denied (no role can do this) | Currency still USD on the tenant row; every money row's CHAR(3) untouched | BR-TEN-042 |
| 3 | Admin re-checks an issued document and a ledger export after the refused attempts | Bill BL-2607-0142 renders $97.41 USD exactly as issued; trial balance and export figures carry USD | Historical documents never restate on settings change; ledger balanced, unchanged | NFR-22 · BR-BIL-026 |
| 4 | Contrast case: a freshly provisioned tenant with ZERO financial records changes currency USD → CAD | Allowed: seed list USD/CAD/MXN/EUR/GBP; save → toast → audit | Change applies only because no financial record exists yet; lock arms on the first one | BR-TEN-042 |
| 5 | RECOVERY — the ratified door: there is no unlock in v1. Correct currency is chosen at onboarding BEFORE any financial record (T7 currency-lifecycle journey covers the positive path) | Admin abandons the change; UI reason text points to onboarding-time selection | No state change anywhere | BR-TEN-042 |
