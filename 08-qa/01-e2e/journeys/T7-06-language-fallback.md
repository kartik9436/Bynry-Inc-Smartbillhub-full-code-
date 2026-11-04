# T7-06 — Fallback ride: missing variant → tenant default renders, never blank — and the fallback pins

---
id: T7-06
tier: 7
language: fallback (any → tenant default)
rules: [BR-NOT-006, BR-CUS-064, BR-BIL-026, TD-16]
stories: [US-NOT-005, US-NOT-006, US-BIL-022, US-NOT-011]
# journey→story wiring sweep pending: story frontmatter `journeys:` updated in a later sweep (00-e2e-design.md §6)
---

**Intent.** The whole fallback law in one journey: a preferred language with NO variant for a template class renders the TENANT-DEFAULT variant — never a blank, never an error, never a skipped document (BR-NOT-006). And because pinning includes the language variant, the fallback that actually rendered is what reprints forever — publishing the missing variant later must NOT quietly rewrite history. A blank disconnect notice is a regulatory incident; this journey is why it cannot happen.

**Fixture.** Tenant brazos-bend, default language en · account ACC-1076 Devi Patel, Residential, preferred_language=de · de variants exist for the bill class ONLY — receipt, reminder, and disconnect-notice classes have NO de variant · money-triples row `flat,cycle,none`: 97.41 unpaid → collections ladder engages.

| # | Actor + action | Expected outcome (contract) | Downstream assertions (upstream/downstream) | Rule |
|---|---|---|---|---|
| 1 | Bill run issues BL-2608-0252 ($97.41) | de bill variant exists → renders de; pin language=de | Baseline: exact-match path works for this account | BR-NOT-006 |
| 2 | Receipt event fires (deposit payment on file) — receipt class has no de variant | Tenant-default en variant renders; document produced, queued, delivered; fallback recorded on the row; pin language=en | NEVER blank, never dropped; queue row exists with a rendered artifact | BR-NOT-006 |
| 3 | Ladder reaches the regulated disconnect-notice step — no de variant for that class either | Disconnect-notice class STILL renders (tenant default en) — the regulated step is never skipped or blanked by a localization gap (BR-NOT-008 class selection unaffected) | notice_history row written; compliance chain unbroken | BR-NOT-006 · BR-NOT-008 |
| 4 | Probe: delete/absence check — a class with NO variant in ANY language cannot occur for seeded classes | Seeded template set guarantees a tenant-default variant per class (provisioning seeds, US-TEN-002); renderer's fallback target always exists | No render path can reach "no variant at all" for platform-seeded classes | BR-NOT-006 |
| 5 | Tenant publishes the missing de receipt + disconnect variants; new events fire | NEW documents select de; the step-2/3 documents keep their pinned en | Publishing affects only future documents | BR-NOT-006 · BR-BIL-026 |
| 6 | INVARIANCE — reprint step-2 receipt and step-3 notice after step 5 | Both render their pinned en fallback forever — a reprint renders its pinned language, full stop; no posting, balance, or notice_history restatement | Pin tuples immutable; ledger untouched by every event in this journey | BR-NOT-006 · BR-TEN-020 · NFR-22 |
