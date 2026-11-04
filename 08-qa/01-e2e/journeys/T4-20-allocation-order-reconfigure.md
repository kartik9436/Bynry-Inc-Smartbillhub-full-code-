# T4-20 — Allocation order reconfigure (x = usage+base → taxes → fees last → y = tenant's new order; FUTURE payments only)

---
id: T4-20
tier: 4
rules: [BR-PAY-010, BR-PAY-031, BR-BIL-021, BR-PAY-002, BR-BIL-001, BR-TEN-016]
stories: [US-TEN-010, US-PAY-006, US-PAY-008]
# journey→story wiring sweep pending: story frontmatter `journeys:` updated in a later sweep (00-e2e-design.md §6)
---

**Intent.** x = the ratified default allocation order — oldest invoice first; within an invoice usage+base → taxes → fees LAST (BR-PAY-010); y = a tenant-reconfigured order. The boundary matters because allocation rows are financial history: a config change may only steer payments allocated AFTER it. Every existing allocation stands; the ONLY way to move an old allocation is the explicit Reapply flow (reversing rows + new rows, reason + audit, BR-PAY-031) — never a settings side effect. Pre-change figures are the frozen PE-2.

**Fixture.** Tenant brazos-bend · ACC-1042, open bill **$247.87** (usage+base 221.90 · taxes 20.97 · late fee 5.00 — the PE-2 shape) · payment 1: **$200.00** allocated pre-change · Admin reorders allocation Aug 12 (e.g., fees before taxes) · payment 2 on a second identically-shaped bill post-change.

| # | Action | Upstream effect (what recomputes) | Downstream assertions | Rule |
|---|---|---|---|---|
| 1 | Baseline: Clerk records payment 1, $200.00 against the $247.87 bill | Default order allocates: usage+base covered in full (221.90 partially — $200 into usage+base); **outstanding $47.87** = 21.90 usage+base remainder + 20.97 taxes + 5.00 fee (PE-2); next late fee computes on that overdue portion (WE-15c) | allocations rows written per the default order; receipt queued; balanced JE; audit | BR-PAY-010 |
| 2 | System Admin reconfigures the tenant allocation order (Settings → Billing family — "allocation order" is a seeded tenant config, nothing hardcoded) | Config row updates; NO reallocation job runs — existing allocations rows untouched at save | audit row with before/after order; PE-2's allocation rows byte-identical after save | BR-BIL-021 · BR-PAY-010 · BR-TEN-016 |
| 3 | Payment 2 arrives on the second bill after the change | Allocation engine reads the CURRENT config: the new order steers the split (per-bucket dollars engine-computed per 00-e2e-design.md §5 — no frozen workbook figure exists for a non-default order); oldest-invoice-first and overpayment→credit behavior remain per the standing rule | allocations rows for payment 2 follow the new order; outstanding composition differs from PE-2 accordingly; receipt + JE + audit | BR-PAY-010 |
| 4 | Contrast — the ratified door for OLD money: staff Reapply payment 1 | Reapply = reversing allocation rows + new rows with reason; this is a deliberate, audited human action — not a settings effect | original allocation rows preserved (reversed, never edited); reapplied rows reference them; audit | BR-PAY-031 · BR-PAY-002 |
| 5 | **INVARIANCE** — what must NOT have changed | Payment 1's allocation as saved in step 1 (until the explicit step-4 Reapply); every issued bill; the late-fee already derived from the pre-change overdue portion | allocations append-only; no bulk reallocation ever triggered by config; closed-period AR/aging reports identical before/after the save | BR-PAY-002 · BR-BIL-004 · hard rule 4 |
