# T7-04 — Language ride: de (language changes strings; Regional settings — not language — govern formats)

---
id: T7-04
tier: 7
language: de
rules: [BR-CUS-064, BR-NOT-006, BR-TEN-042, IS-8, TD-16, IS-11]
stories: [US-CUS-003, US-NOT-005, US-NOT-006, US-BIL-022, US-TEN-006, US-SHL-013]
# journey→story wiring sweep pending: story frontmatter `journeys:` updated in a later sweep (00-e2e-design.md §6)
---

**Intent.** German is the ride where string-language and number/date FORMATS would most tempt an implementer to couple (1.234,56 vs 1,234.56). The ratified split: the language variant supplies the STRINGS (BR-NOT-006); dates/numbers/currency render per the tenant's Regional settings (IS-8), server-side for documents (TD-16 #4). An account choosing de on a US tenant gets German strings with the tenant's formats — the renderer must not invent per-language format switching.

**Fixture.** Tenant brazos-bend, default language en, Regional settings = US formats, currency USD · account ACC-1063 Klaus Brandt, Commercial, preferred_language=de · de variants published for bill + receipt (Commercial category per BR-NOT-006 tuple) · money-triples row `tiered,cycle,full`: taxable 63.30 + tax 5.99 = 69.29, paid full.

| # | Actor + action | Expected outcome (contract) | Downstream assertions (upstream/downstream) | Rule |
|---|---|---|---|---|
| 1 | Preferred language de on ACC-1063 | Stored; audited | Picker shows the seeded set incl. de (BR-TEN-042) | BR-CUS-064 |
| 2 | Bill run issues BL-2608-0230 ($69.29) | Variant (bill, **Commercial**, de) selected — category AND language dimensions both honored; pin = template + version + language=de | Commercial de variant ≠ Residential de variant (distinct rows) | BR-NOT-006 · TD-16 |
| 3 | Inspect the rendered document's format inputs | Amounts/dates formatted per TENANT Regional settings (IS-8) server-side; language de changed strings only; stored values remain NUMERIC(18,6) + CHAR(3) + UTC | 69.29 renders under tenant formats; no de-specific decimal-comma transform was applied or stored | IS-8 · BR-TEN-020 |
| 4 | Payment 69.29 clears → receipt queues | Receipt variant (receipt, Commercial, de) selected; queue row records resolved language | Zero fallback events (variants exist) | BR-NOT-006 |
| 5 | CSV export of the bill row | Plain 2dp `69.29`, ISO dates, snake_case headers — CSV is untouched by language AND by Regional display formats (IS-11: files are ISO regardless) | IS-11 · TD-16 #4 | IS-11 |
| 6 | INVARIANCE — tenant edits Regional format settings after issue; reprint BL-2608-0230 | Regional/format settings are display-time transforms only; the settings edit restates NO stored value, posting, or history row; reprint renders the pinned de tuple | Settings save audited (BR-TEN-016); ledger untouched | BR-TEN-020 · BR-NOT-006 · NFR-22 |
