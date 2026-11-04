# T4-10 — Account preferred-language change (x = en → y = es-MX; next document switches, pinned documents never do)

---
id: T4-10
tier: 4
rules: [BR-CUS-064, BR-NOT-006, BR-BIL-026, TD-16]
stories: [US-CUS-009, US-NOT-005, US-BIL-023]
# journey→story wiring sweep pending: story frontmatter `journeys:` updated in a later sweep (00-e2e-design.md §6)
---

**Intent.** x = account preferred_language en; y = es-MX. The boundary is the split BR-CUS-064 draws: document delivery picks the matching template language variant AT RENDER TIME for FUTURE documents, while every already-issued document keeps its pinned language forever (pinning tuple includes language). A language preference is customer data, not a re-statement lever — if flipping it re-rendered history, the "what did we send this customer" audit answer would change with a dropdown.

**Fixture.** Tenant brazos-bend · ACC-1042, preferred_language **en** · issued Jul bill BL-2607-0142 **$97.41** pinned (template, version, en) · es-MX variant published for the residential bill template (T4-09 end-state).

| # | Action | Upstream effect (what recomputes) | Downstream assertions | Rule |
|---|---|---|---|---|
| 1 | Clerk edits the account: preferred_language en → **es-MX** | `accounts.preferred_language` updates (B2 r15 #2); nothing renders, queues, or posts at edit time | audit row with before/after; account detail shows the new preference (US-CUS-009 panel) | BR-CUS-064 |
| 2 | Aug cycle issues the account's next bill | Variant resolution reads the account's CURRENT preference → es-MX variant selected; server-side render; pin = (template, version, es-MX) | Aug document fully es-MX; delivery-queue row references the es-MX render; audit | BR-CUS-064 · BR-NOT-006 · TD-16 |
| 3 | A receipt and a reminder notice generate for the account after step 1 | Every notification-class document resolves the same way — type × category × language, account preference first, tenant default fallback if a class lacks the variant | each document either es-MX (variant exists) or complete tenant-default fallback (variant absent) — never blank, never mixed | BR-NOT-006 |
| 4 | Harness reprints Jul's BL-2607-0142 after the change | Render resolves the PINNED tuple: en | Jul reprint byte-equivalent English, $97.41 — preference changes never touch pinned documents | BR-BIL-026 · BR-NOT-006 |
| 5 | **INVARIANCE** — what must NOT have changed | Every document issued before step 1 keeps its pinned language and bytes; no money field anywhere moved (language is presentation, storage stays UTC + NUMERIC + CHAR(3)) | pinned tuples on history unmodified; ledger, AR, and report figures identical before/after; only the account row + audit trail changed | BR-CUS-064 · BR-TEN-020 · hard rule 4 |
