# T7-03 — Language ride: es-MX (a locale is not its parent — exact match or tenant default, never es)

---
id: T7-03
tier: 7
language: es-MX
rules: [BR-CUS-064, BR-NOT-006, BR-TEN-042, TD-16, IS-11]
stories: [US-CUS-003, US-NOT-005, US-NOT-006, US-BIL-022, US-SHL-013]
# journey→story wiring sweep pending: story frontmatter `journeys:` updated in a later sweep (00-e2e-design.md §6)
---

**Intent.** es-MX is a DISTINCT seeded locale (BR-TEN-042 — PO "Mexican", recorded as es-MX). Variant resolution must match it exactly when an es-MX variant exists, and when one does not, the ratified fallback is the TENANT DEFAULT (BR-NOT-006) — not the es parent. There is no locale-chain fallback in the law; this journey proves none was invented.

**Fixture.** Tenant brazos-bend, default language en · account ACC-1057 Rosa Chavez, Residential, preferred_language=es-MX · bill class has BOTH es and es-MX variants published; receipt class has es but NO es-MX variant · money-triples row `flat,cycle,full`: 97.41 issued and paid in full.

| # | Actor + action | Expected outcome (contract) | Downstream assertions (upstream/downstream) | Rule |
|---|---|---|---|---|
| 1 | Preferred language es-MX set on ACC-1057 | Stored as the es-MX locale key exactly (B2 r15 #2); pickers list es and es-MX as separate entries | Audit row on the account edit | BR-CUS-064 · BR-TEN-042 |
| 2 | Bill run issues BL-2608-0222 ($97.41) | Renderer selects (bill, Residential, **es-MX**) — NOT the es variant, though one exists; pin records language=es-MX | The es and es-MX bill variants are distinct rows; selection is exact-match | BR-NOT-006 · TD-16 |
| 3 | Payment clears → receipt queues, but the receipt class has no es-MX variant | Fallback fires to the TENANT DEFAULT (en) variant — explicitly NOT the es variant; the receipt row and its pin record the actually-rendered language=en + a fallback-fired fact | Never blank (BR-NOT-006); zero es selections anywhere in this journey | BR-NOT-006 |
| 4 | Tenant later publishes an es-MX receipt variant; a NEW receipt is generated | New receipt selects es-MX; the step-3 receipt's pin still says en | Forward-only: publishing affects only future documents (BR-BIL-026 posture) | BR-NOT-006 · BR-BIL-026 |
| 5 | CSV export of the account's bills/payments | ISO/neutral per IS-11 — locale es-MX never reaches headers, decimals (97.41 plain 2dp) or dates | IS-11 · TD-16 #4 contract holds | IS-11 |
| 6 | INVARIANCE — reprint the step-3 receipt after step 4's variant publish | Renders pinned language=en fallback forever; no re-resolution against today's variant catalog; postings/history unchanged throughout | Pin tuple immutable; ledger untouched | BR-NOT-006 · BR-TEN-020 · NFR-22 |
