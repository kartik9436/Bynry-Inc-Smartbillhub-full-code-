# J22 — Template life (draft → publish v2 → bills pin v2 → v3 + es-MX variant → July reprint renders v2 in its pinned language)

---
id: J22
tier: 2
rules: [BR-BIL-025, BR-BIL-026, BR-BIL-027, BR-NOT-006, BR-CUS-064, BR-AUD-018, BR-NOT-005]
stories: [US-BIL-021, US-BIL-022, US-BIL-005, US-NOT-005, US-NOT-006, US-CUS-003, US-BIL-026]
# journey→story wiring sweep pending: story frontmatter `journeys:` updated in a later sweep (00-e2e-design.md §6)
---

**Intent.** The document layer's whole covenant in one ride: templates version append-only with split rights (Clerk drafts, Admin publishes), every bill PINS template + version + resolved LANGUAGE at issue, and from that moment the pin is destiny — later versions, new language variants, even a delete attempt change nothing about what an issued bill renders. The July reprint at the end is the proof: v2, in its pinned language, forever.

**Fixture.** Tenant brazos-bend, default language en (variant seed per BR-NOT-006) · bill template (type=bill, category=Residential): v1 live · ACC-1203, Residential, `preferred_language = es-MX` (BR-CUS-064) · July run **Jul 1, 2026** · v3 + **es-MX** variant land **Aug 10** · reprint **Sep 12**.

| # | Date · action | Handoff contract (what this step leaves) | Downstream assertions (bill · ledger · reports · queue · audit) | Rule |
|---|---|---|---|---|
| 1 | **Jun 15** — Billing Clerk creates **draft v2** + test-prints (draft rights only — Clerk cannot publish) | Draft v2 alongside live v1; append-only version list | Test-print never touches any account document; no bill can pin a draft; audit | **BR-BIL-027** |
| 2 | **Jun 30** — System Admin **publishes v2** | v2 = the current version for future issues; v1 retained forever (append-only) | Publishing affects ONLY future bills — every already-issued bill still renders its own pin; audit | BR-BIL-026/027 |
| 3 | **Jul 1** — cycle run issues July bills: each bill **pins template_id + v2 + resolved language**; ACC-1203 requests es-MX but no es-MX variant exists yet → **tenant-default fallback (en)** is resolved AND RECORDED on the pin — never a blank, never an unrecorded inference | July bills pinned (bill-template, v2, en) — the pin tuple is complete including language | Template assignment resolved by consumer category with per-account override capacity (BR-BIL-025); delivery rows queue (BR-NOT-005); audit | **BR-BIL-026** · BR-NOT-006 |
| 4 | **Aug 10** — Clerk drafts / Admin publishes **v3**, and the **es-MX language variant** is added (variants per type × category × language) | v3 current; es-MX variant available for FUTURE issues | Nothing re-renders: July bills still (v2, en); the variant catalog change is data, not history surgery; audit | **BR-NOT-006** |
| 5 | **Sep 1** — September run: ACC-1203's bill now pins **(v3, es-MX)** — the variant exists, the account preference resolves | September pin tuple reflects the new world; other accounts pin (v3, en) | Per-bill pin recorded at issue as always; delivery queued; audit | BR-NOT-006 · BR-CUS-064 |
| 6 | **Sep 12** — **REPRINT the July bill** for ACC-1203 | Renders **v2 in its pinned language (en fallback, as recorded)** — forever; the reprint ignores v3, ignores the now-existing es-MX variant, recomputes nothing | Byte-identical document to the July original; reprint audited | **BR-BIL-026** · BR-NOT-006 |
| 7 | **Sep 12** — Admin attempts to **delete v2** (pinned by July bills) | **REFUSED** — a version pinned by any bill can never be deleted (audit-lock); refusal writes a security-event attempt row (the T5-02 guard, lived here) | v2 intact; attempt row in audit_log; version list still append-only | BR-BIL-027 · **BR-AUD-018** |
| 8 | **INVARIANCE** — the version timeline is v1→v2→v3 append-only with no gaps; every issued bill's pin tuple (template, version, language) is immutable and sufficient to re-render it byte-identically without consulting current state | — | No issued document ever re-rendered from a later version; rights split held at every step (Clerk draft / Admin publish); full audit chain | BR-BIL-004 · hard rule 4 |
