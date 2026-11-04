# T5-02 — Delete a pinned template version (audit-lock stands)

---
id: T5-02
tier: 5
guards: [BR-BIL-026, BR-BIL-027, BR-NOT-006, NFR-8, NFR-33]
stories: [US-BIL-021, US-BIL-022, US-NOT-006]
# journey→story wiring sweep pending: story frontmatter `journeys:` updated in a later sweep (00-e2e-design.md §6)
---

**Intent.** A template version pinned by ANY bill can never be deleted — even by a System Admin. Pinning is what makes every issued document reproducible forever (reprint renders the pinned version byte-equivalent, NFR-33); deleting a pinned version would silently orphan issued financial documents. The system must refuse the delete and offer the only ratified evolution path: publish a new version for FUTURE bills.

**Fixture.** Tenant brazos-bend · template "Residential bill" version **v2 (en)** pinned at issue by BL-2607-0142 (2026-07-05) · draft v3 exists.

| # | Actor + action | Expected refusal (IS-7 outcome) | Downstream assertions (nothing changed) | Guard |
|---|---|---|---|---|
| 1 | System Admin opens the template version list and attempts Delete on v2 | Action disabled-with-reason (IS-6): "pinned by N bills — audit-locked"; server refuses a forced call (409 class, permission-denied posture is NOT used — this is a state lock, not a role gate) | template_versions row for v2 untouched; version chain intact (append-only) | BR-BIL-027 · NFR-8 |
| 2 | Same admin attempts `DELETE /api/templates/residential-bill/versions/v2` directly | Refused 409 class; error names the audit-lock and links the pinning bills | No row deleted; BL-2607-0142.pinned_template_version still v2 (en); audit: attempt-logging not ratified (BR-AUD-001 scope = executed destructive actions) — assert zero deletions | BR-BIL-027 |
| 3 | Clerk reprints BL-2607-0142 after the refused delete | Reprint renders v2 (en) byte-equivalent to the issue-time document — pinned version AND pinned language variant | Rendered output identical; no re-render against v3/draft; delivery record appended for the reprint only | BR-BIL-026 · BR-NOT-006 · NFR-33 |
| 4 | Billing Clerk attempts to delete an UNPINNED draft version (v3-draft) — contrast case | Allowed for drafts (drafts are not pinned by anything); confirm modal → toast → audit row | Only the draft row removed; published/pinned versions untouched | BR-BIL-027 · BR-AUD-001 |
| 5 | RECOVERY — the ratified door: System Admin publishes v3; future issues pin v3, history keeps v2 forever | Publish succeeds (Admin-only right); publishing affects only future bills | New bills pin v3; BL-2607-0142 reprints still render v2; v2 retained FOREVER (NFR-8) | BR-BIL-026 · BR-BIL-027 |
