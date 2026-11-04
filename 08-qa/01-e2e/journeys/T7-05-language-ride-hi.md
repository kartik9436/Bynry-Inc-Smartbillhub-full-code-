# T7-05 — Language ride: hi (non-Latin script end-to-end — catalogs, documents, queue, files)

---
id: T7-05
tier: 7
language: hi
rules: [BR-CUS-064, BR-NOT-006, BR-SHL-030, BR-TEN-042, NFR-37, TD-16, IS-11]
stories: [US-CUS-003, US-NOT-005, US-NOT-006, US-BIL-022, US-PAY-025, US-SHL-013]
# journey→story wiring sweep pending: story frontmatter `journeys:` updated in a later sweep (00-e2e-design.md §6)
---

**Intent.** Hindi is the seeded language (BR-TEN-042) that proves the pipeline is script-agnostic: Devanagari template variants and catalog strings are DATA (NFR-37), the server-side renderer and PDF path carry them without mojibake, and every boundary that must stay ASCII/ISO (CSV headers, decimals, dates, IDs) stays ASCII/ISO. Content assertions remain structural — variant selected, encoding intact — never invented copy.

**Fixture.** Tenant brazos-bend, default language en · account ACC-1071 Anita Sharma, Residential, preferred_language=hi · hi variants published for bill + receipt; reminder class has NO hi variant (fallback probe) · money-triples row `flat,cycle,none`: 97.41 issued, unpaid, next_late_fee 5.00 · clerk Priya Nair, per-user UI language hi (BR-SHL-030 override).

| # | Actor + action | Expected outcome (contract) | Downstream assertions (upstream/downstream) | Rule |
|---|---|---|---|---|
| 1 | Preferred language hi on ACC-1071; Priya sets her own UI override to hi | Account field and per-user setting stored server-side as separate facts (B2 r15 #2/#4) — one drives documents, the other drives one user's chrome | Both writes audited | BR-CUS-064 · BR-SHL-030 |
| 2 | Bill run issues BL-2608-0241 ($97.41) | Variant (bill, Residential, **hi**) selected; pin records language=hi; PDF renders with the Devanagari-capable document pipeline (UTF-8 throughout) | Rendered artifact stored/queued without encoding loss; delivery rows queue | BR-NOT-006 · TD-16 |
| 3 | Account goes past due → reminder generated, but reminder class has no hi variant | Tenant-default (en) variant renders — never blank; fallback fact recorded on the row | The one missing variant does not block the ladder; regulated-class behavior unaffected | BR-NOT-006 |
| 4 | Priya (UI hi) vs a second clerk (UI en) work the same S30 list | Each sees their OWN language from platform catalogs (client-side, TD-16 #1); hi catalog is a data asset — same build, no code fork | Identical data rows under both UIs; catalog owned by platform-shell (B2 r16 #6) | BR-SHL-030 · NFR-37 |
| 5 | CSV export of the account's bills | snake_case ASCII headers, 97.41 plain 2dp, ISO dates; file is valid UTF-8; NO Devanagari leaks into headers, codes, or IDs | IS-11 contract byte-identical in structure to T7-01 step 5 | IS-11 · TD-16 #4 |
| 6 | INVARIANCE — reprint BL-2608-0241 after the tenant later publishes a hi reminder variant | Bill reprint renders pinned hi tuple; step-3's reminder keeps its pinned en fallback; nothing re-resolves, no posting/history change | Pins immutable; late-fee math (5.00 next fee per triples) untouched by any language event | BR-NOT-006 · BR-TEN-020 · NFR-22 |
