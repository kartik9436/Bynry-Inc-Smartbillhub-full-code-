# T7-07 — Per-user UI language override vs tenant default (chrome is personal; documents don't care)

---
id: T7-07
tier: 7
language: per-user override (tenant en · user hi)
rules: [BR-SHL-030, BR-TEN-042, BR-CUS-064, TD-16]
stories: [US-SHL-005, US-SHL-013, US-TEN-006]
# journey→story wiring sweep pending: story frontmatter `journeys:` updated in a later sweep (00-e2e-design.md §6)
---

**Intent.** Three language settings coexist and never bleed into each other: tenant default (BR-TEN-042, S8 Regional), per-user UI override (BR-SHL-030, server-stored profile setting), account preferred language (BR-CUS-064, documents only). This journey turns each knob and proves the other two hold still — including the TD-16 #3 seam: the server emits error CODES + parameters, and each user's client translates them, so no translated string is ever stored.

**Fixture.** Tenant brazos-bend, default language en · users: Priya Nair (override → hi), Dana Kim (no override) · account ACC-1042 Maria Delgado preferred_language=es with an issued es-pinned bill (T7-02 fixture) · both users logged in concurrently.

| # | Actor + action | Expected outcome (contract) | Downstream assertions (upstream/downstream) | Rule |
|---|---|---|---|---|
| 1 | Priya sets UI language hi in her user menu (S48 profile) | Per-user override stored SERVER-side (B2 r15 #4); takes effect for Priya only; save audited | Dana's session unchanged, mid-session | BR-SHL-030 |
| 2 | Both users open the same S30 list | Priya sees hi chrome, Dana sees en chrome, over identical data rows; strings from platform client-side catalogs (TD-16 #1) | Tenant-entered reference data is NOT machine-translated (TD-16 #5) — tenant-authored names render as authored for both users | BR-SHL-030 · TD-16 |
| 3 | Admin changes TENANT default en→es (S8 Regional) | New default applies to users WITHOUT an override (Dana → es on next render); Priya's hi override still wins; settings save audited (BR-TEN-016) | Precedence: user override > tenant default; no user profile rows were rewritten by the tenant-level save | BR-TEN-042 · BR-SHL-030 |
| 4 | Priya submits an invalid form (server-side validation trips) | Server responds with a CODE + parameters, language-neutral; Priya's client renders it in hi; the same error to Dana would render es | No translated strings in API payloads or stored data (TD-16 #3) | TD-16 |
| 5 | Priya reprints ACC-1042's bill while her UI is hi | Document renders its PINNED es tuple — the viewing user's UI language never influences document rendering (documents follow account language, server-side) | BR-NOT-006 pin honored; chrome around the document stays hi | BR-CUS-064 · BR-NOT-006 · TD-16 |
| 6 | INVARIANCE — Priya clears her override; tenant default restored en | Every language edit in this journey was a settings/preference write: zero documents, postings, balances, or history rows changed anywhere | Audit rows exist for steps 1/3/6 saves; ledger untouched | BR-TEN-020 · BR-TEN-016 · NFR-22 |
