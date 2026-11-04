# J3 — Exception handling

---
id: J3
tier: 1
stories: [US-MET-011, US-MET-014, US-BIL-005]
---

<!-- FRONTMATTER ADDED 2026-08-15 (DEF-102). Not a pure transcription: the step
     table names US-MET-011 and US-MET-014 explicitly and uses the WILDCARD
     US-BIL-** for its billing step, which cannot be indexed. Resolved to
     US-BIL-005 (issue), which is the story whose output the exception path acts
     on. Stated here so a reviewer can disagree with the choice rather than
     discover it. -->
**Fixture.** (authored 2026-08-22, CR-014) Tenant brazos-bend · the CR-014 flat money cohort (see J2's Fixture — same premises/plan/meters/accounts, issued August bill **97.41**) · `read_validation_settings` at the B2 r5 #15 seeded defaults (BR-MET-020: the engine reads THIS, never a constant). The FLAGGED read itself is the journey's own step-1 import act — pre-seeding one would leave the journey asserting over its own answer.

flagged read → estimate/override → billing-run exception case → resolution → bill.
| # | Story | Handoff |
|---|---|---|
| 1 | US-MET-011 flags (config from S64 settings) | read carries flag + reason |
| 2 | US-MET-014/015 estimation ⛔GT-9-defaults | estimated read, ≤2 consecutive, register true-up path intact |
| 3 | US-BIL-** step-3 cases (wave 3) | case action recorded (bill/hold/skip/waive), audit row |
| 4 | US-BIL-** generate | resolved reads only; held accounts excluded with reason |
