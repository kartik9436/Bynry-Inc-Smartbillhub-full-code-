# T4-08 — Bill template publish v2 → v3 (pinning: old bills render v2 forever)

---
id: T4-08
tier: 4
rules: [BR-BIL-026, BR-BIL-027, BR-BIL-025, BR-NOT-002, BR-BIL-004]
stories: [US-BIL-021, US-BIL-022, US-NOT-006, US-BIL-026]
# journey→story wiring sweep pending: story frontmatter `journeys:` updated in a later sweep (00-e2e-design.md §6)
---

**Intent.** x = residential bill template v2 (current published); y = v3 published. The boundary is BR-BIL-026: template + version are PINNED on the bill at issue — a reprint or re-send renders the pinned version FOREVER; publishing affects only future bills. If a publish re-rendered history, a layout tweak would change what a customer was legally sent. No money moves in this journey; the asset under test is document reproducibility (the same law that makes DB-9's pinned template_id+version a schema fact).

**Fixture.** Tenant brazos-bend · residential bill template, v2 published · issued bill BL-2607-0142 **$97.41** pinned to v2 (money-triples row `flat,cycle,full`) · Billing Clerk drafts v3 (footer + layout change), System Admin publishes.

| # | Action | Upstream effect (what recomputes) | Downstream assertions | Rule |
|---|---|---|---|---|
| 1 | Billing Clerk creates draft v3 and test-prints | Draft version row appended; v2 stays the published version; drafts never render on real bills | test-print watermarked/draft-scoped; no delivery-queue row for a real account | BR-BIL-027 |
| 2 | System Admin PUBLISHES v3 | Version chain appends: v3 becomes the version future issues will pin; v2 remains stored, undeletable while pinned by any bill (audit-lock — the T5-02 guard) | audit row for publish (actor = Admin — Clerk cannot publish); no existing invoice row changes | BR-BIL-027 · BR-NOT-002 |
| 3 | Harness reprints BL-2607-0142 after the publish | Render resolves the PINNED tuple (template, v2) — not the current version | reprint byte-equivalent to the issue-time render: v2 layout, $97.41, original footer; reprints never recompute (BR-CUS-040 posture) | BR-BIL-026 |
| 4 | Next cycle run issues new bills | Issue stamps template v3 onto each new invoice (pin at issue); category default assignment per BR-BIL-025 unless per-account override | new bills render v3; delivery-queue rows reference the v3 render; audit | BR-BIL-026 · BR-BIL-025 |
| 5 | **INVARIANCE** — what must NOT have changed | Every bill issued before the publish still pins v2 and renders it identically, forever; v2's content bytes unmodified (append-only versions) | invoice rows' pinned template/version columns untouched; no re-render job ran against history; attempt to delete v2 refuses (cross-ref T5-02) | BR-BIL-026 · BR-BIL-004 · hard rule 4 |
