# T4-09 — Template language variant added (x = es-MX account renders tenant-default fallback → y = renders the es-MX variant)

---
id: T4-09
tier: 4
rules: [BR-NOT-006, BR-CUS-064, BR-NOT-002, BR-BIL-026, NFR-37, TD-16]
stories: [US-NOT-006, US-NOT-005, US-BIL-022]
# journey→story wiring sweep pending: story frontmatter `journeys:` updated in a later sweep (00-e2e-design.md §6)
---

**Intent.** x = no es-MX variant exists for the residential bill template, so an es-MX-preferring account's documents render the tenant-default language via the BR-NOT-006 fallback (never a blank); y = the es-MX variant is published, and the NEXT document renders es-MX. The boundary matters twice: the fallback must be lossless before the variant exists, and the variant's arrival must be FUTURE-ONLY — the pinning tuple includes the language (B2 r15 #3), so a document issued under the English fallback reprints in English forever. Adding a language is a DATA change, never code (NFR-37); documents always render server-side for batch + pinning reproducibility (TD-16).

**Fixture.** Tenant brazos-bend, default language English · ACC-1049 with `preferred_language = es-MX` (BR-CUS-064) · residential bill template: English variant published; es-MX variant absent, then authored + published.

| # | Action | Upstream effect (what recomputes) | Downstream assertions | Rule |
|---|---|---|---|---|
| 1 | Jul cycle issues ACC-1049's bill BEFORE the variant exists | Variant resolution (type × category × language) finds no es-MX row → falls back to the tenant default (English); pin records the tuple ACTUALLY used, English included | bill renders complete English document — never blank, never mixed; delivery-queue row; pinned tuple = (template, version, en) | BR-NOT-006 |
| 2 | Clerk drafts the **es-MX language variant**; System Admin publishes it | Template variant chain gains the es-MX row (data change only — no deploy, NFR-37); version lifecycle per BR-NOT-002 | audit row; no existing document re-renders at publish | BR-NOT-006 · NFR-37 |
| 3 | Aug cycle issues ACC-1049's next bill | Variant resolution now matches es-MX → the document renders the es-MX variant server-side (TD-16); pin = (template, version, es-MX) | Aug bill fully es-MX; tenant-entered data (names, addresses) passes through untranslated (TD-16); queue + audit rows | BR-NOT-006 · BR-CUS-064 · TD-16 |
| 4 | Harness reprints the Jul bill after the variant exists | Render resolves the PINNED language: English | Jul reprint byte-equivalent English — "a reprint renders its pinned language forever" | BR-NOT-006 · BR-BIL-026 |
| 5 | **INVARIANCE** — what must NOT have changed | No document issued before step 2 changed language; the English variant's content untouched; accounts with other preferences unaffected | pinned tuples on all historical documents unmodified; variant chain append-only; zero re-render jobs against history | BR-NOT-006 · hard rule 4 |
