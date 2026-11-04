# T5-26 — Last-admin demotion (a tenant always keeps ≥1 active System Admin)

---
id: T5-26
tier: 5
guards: [BR-IDN-013]
stories: [US-IDN-006, US-IDN-007]
# journey→story wiring sweep pending: story frontmatter `journeys:` updated in a later sweep (00-e2e-design.md §6)
---

**Intent.** A tenant always retains at least one active System Admin: the LAST one cannot be demoted, deactivated, or removed (BR-IDN-013) — by anyone, including themselves. In a 1–2 staff utility this is one misclick away from a tenant nobody can administer (and v1 sends no staff auth emails to self-rescue with, NFR-14). All three exits must refuse, server-side.

**Fixture.** Tenant brazos-bend · Dana = the ONLY active System Admin · Priya = Billing Clerk · Marcus = Executive (view-only).

| # | Actor + action | Expected refusal (IS-7 outcome) | Downstream assertions (nothing changed) | Guard |
|---|---|---|---|---|
| 1 | Dana opens the user list (S-users) and tries Edit role on herself → Billing Clerk | Refused: last-active-System-Admin guard — action disabled-with-reason (IS-6); forced save refused 409 class naming the rule | Dana's user row unchanged: role still System Admin, status active; no audit row (nothing executed — BR-AUD-001 scope) | BR-IDN-013 |
| 2 | Dana tries Deactivate on herself | Same refusal — deactivation counts as losing the last admin | Status still active; sessions untouched | BR-IDN-013 |
| 3 | Dana tries Remove on herself; then replays all three via `PATCH/DELETE /api/users/{dana}` | Same refusal server-side for demote, deactivate, remove — UI gating was convenience | User row present and unchanged; tenant admin count still ≥1 (exactly 1) | BR-IDN-013 |
| 4 | Adversarial probe: Priya (Billing Clerk) attempts the same against Dana via API | Refused twice over: role gate (user management is admin-level) AND the last-admin guard behind it — permission-denied posture (IS-7) | No change; enforcement is server-side regardless of caller | BR-IDN-013 · A4 role matrix |
| 5 | RECOVERY — the ratified door: Dana promotes a second admin FIRST (edit Priya's role → System Admin, or invite a new user as System Admin), THEN her own demotion/deactivation is no longer "the last" | Promotion succeeds (confirm → toast → audit); with 2 active admins, Dana's demotion to Executive now passes | Tenant admin count never touches 0 at any instant; both role changes audited with before→after | BR-IDN-013 · BR-AUD-001 |
