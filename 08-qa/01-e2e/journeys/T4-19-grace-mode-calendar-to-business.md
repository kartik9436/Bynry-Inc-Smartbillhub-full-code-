# T4-19 — Grace mode calendar → business days (x = calendar counting → y = business counting; next due-date evaluation only)

---
id: T4-19
tier: 4
rules: [BR-BIL-002, BR-BIL-008, BR-BIL-024, BR-PAY-021, BR-BIL-004, BR-TEN-016]
stories: [US-TEN-010, US-PAY-014]
# journey→story wiring sweep pending: story frontmatter `journeys:` updated in a later sweep (00-e2e-design.md §6)
---

**Intent.** x = grace counted in CALENDAR days from due date; y = BUSINESS days (the tenant setting BR-BIL-002 makes switchable). The boundary matters because the same 5-day grace lands on different dates under each mode — the frozen WE-15 pair: calendar mode, due Jul 20 → fee applies from **Jul 26**; business mode, due Fri Jul 17 → fee applies from **Jul 24**. The switch must govern only evaluations that RUN after the change; fees already assessed under the old mode, and on-time determinations already made, are history.

**Fixture.** Tenant brazos-bend · grace 5 days (BR-BIL-008 default) · bill A due **Jul 20**, evaluated under calendar mode pre-change · mode switched Aug 1 · bill B due **Fri Aug 14** (the WE-15e weekday shape), evaluated under business mode.

| # | Action | Upstream effect (what recomputes) | Downstream assertions | Rule |
|---|---|---|---|---|
| 1 | Baseline under calendar mode: bill A (due Jul 20) unpaid; grace evaluation runs | Fee boundary = due + 5 CALENDAR days → fee applies from **Jul 26**; a payment POSTED Jul 25 escapes the fee (posting date is what billing consumes) | evaluation outcome recorded; if fee assessed, the $5 floor per WE-15; audit | BR-BIL-002 · WE-15(d) · BR-PAY-021 |
| 2 | System Admin switches grace mode **calendar → business** (Settings → Billing defaults, S66 family) | Config value flips; nothing re-evaluates at save time — no job re-walks past due dates | audit row with before/after mode; zero fee lines created/removed at save | BR-BIL-002 · BR-TEN-016 |
| 3 | Harness re-reads bill A's state after the switch | — | bill A's fee outcome unchanged — its evaluation is DONE; no retro re-evaluation under business counting (which would have moved its boundary) | BR-BIL-004 · hard rule 4 |
| 4 | NEXT evaluation: bill B due Fri Aug 14, unpaid; grace runs after the switch | Boundary = due + 5 BUSINESS days — weekend days don't count (the WE-15e shape: due Fri Jul 17 → from Jul 24); bill B's fee applies from **Fri Aug 21** by the same business-day counting, engine-verified | fee (if assessed) = max($5, % × overdue) per the standing formula; audit names mode used; due date itself never moved (due = bill date + cycle due-days, BR-BIL-024 — grace mode changes counting, not due dates) | BR-BIL-002 · BR-BIL-001 · BR-BIL-024 |
| 5 | **INVARIANCE** — what must NOT have changed | Every past on-time/late determination; every assessed fee; every issued bill's due date | issued lines byte-identical; the mode change touched one config row + audit; closed-period fee revenue identical before/after | BR-BIL-004 · BR-TEN-016 · hard rule 4 |
