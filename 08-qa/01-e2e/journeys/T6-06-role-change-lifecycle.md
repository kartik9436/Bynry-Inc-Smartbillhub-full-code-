# T6-06 — Role-change lifecycle: promotion powers up on the very NEXT request; demotion powers down the same way; the last-admin guard holds

---
id: T6-06
tier: 6
roles: [System Admin, Billing Clerk]
gates: [BR-IDN-008, BR-IDN-009, BR-IDN-012, BR-IDN-013, BR-BIL-027, BR-AUD-009]
stories: [US-IDN-004, US-IDN-006, US-IDN-007, US-BIL-021]
# journey→story wiring sweep pending: story frontmatter `journeys:` updated in a later sweep (00-e2e-design.md §6)
---

**Intent.** Roles are a live security boundary, not a login-time snapshot. The ratified rule is stronger than "next session": a role change applies to the user's VERY NEXT REQUEST (US-IDN-006 TC-1 + acceptance — "Priya's next request carries Executive permissions"), and deactivation revokes live sessions IMMEDIATELY (BR-IDN-012 — in-flight request → 401). This journey promotes a Clerk to System Admin, proves the new powers live without re-login, demotes her, proves the powers die on the next request of the SAME session (no stale-permission window), and re-verifies the last-admin guard at the exact moment it becomes relevant (full three-exit sweep = T5-26).

**Fixture.** Tenant brazos-bend · Dana = System Admin · Priya = Billing Clerk holding an ACTIVE session throughout (no sign-out at any step) · Tom = Billing Clerk with 2 active sessions · template "Residential bill" draft v4 (publish = the Admin-only litmus action, BR-BIL-027).

| # | Actor + action | Allowed? / Denied? | Expected outcome | Downstream assertions | Gate |
|---|---|---|---|---|---|
| 1 | BASELINE — Priya (Clerk) tries to publish template v4 and to open S61 | DENIED (both) | Publish = System Admin only; S61 = System Admin + Executive | 403-class each; zero writes | BR-BIL-027 · BR-AUD-009 |
| 2 | ADVERSARIAL — Priya calls `PATCH /api/users/{priya}` on her own membership → System Admin | DENIED | Self-promotion via API refused 403 server-side — with an audit row for the denied attempt (the ONE ratified attempt-audit, US-IDN-006 TC-6) | Membership role unchanged; audit row present for this denial specifically | BR-IDN-009 |
| 3 | Dana edits Priya's role: Billing Clerk → System Admin (3-role select, confirm → toast) | ALLOWED | Role change chooses among the 3 predefined roles only; user management = Admin only | `tenant_memberships.role_id` updated; audit `user.role_changed` with before/after; tenant now has 2 active admins | BR-IDN-009 · BR-IDN-008 |
| 4 | Priya's very NEXT request in her EXISTING session: publish template v4 | ALLOWED | New permissions apply to the next request — no re-login, no session cycling needed | Publish succeeds (Admin right); future bills pin v4; audit; the same session that got 403 in step 1 now passes | US-IDN-006 acceptance · BR-BIL-027 |
| 5 | Priya (same session) opens Settings → Reference data and S61 | ALLOWED | Full Admin surface live: settings edit + audit viewer both serve | Settings save audits per BR-TEN-016; S61 renders | A4 grid · BR-AUD-009 |
| 6 | Dana demotes Priya back: System Admin → Billing Clerk (2 admins exist, so no last-admin conflict) | ALLOWED | Demotion passes because Dana remains an active admin — the count never touches 0 | Audit `user.role_changed` before/after; active-admin count 2 → 1 | BR-IDN-009 · BR-IDN-013 |
| 7 | Priya's very next request in the SAME still-open session: republish probe + Settings save + S61 | DENIED (all) | Powers die as fast as they arrived — no stale-permission window on a live session | 403-class each; zero writes; her Clerk powers (T6-02 set) still work | US-IDN-006 acceptance · BR-BIL-027 |
| 8 | GUARD — Dana (now the only active System Admin again) attempts self-demotion | DENIED | Last-admin guard: the last one cannot be demoted, deactivated, or removed — full sweep incl. API replays and the recovery door = T5-26 | Membership unchanged; active-admin count stays 1; zero writes | BR-IDN-013 |
| 9 | DEACTIVATION CONTRAST — Dana deactivates Tom (Clerk, 2 live sessions) | ALLOWED | Deactivation is IMMEDIATE, not next-request: both sessions revoked at once; Tom's in-flight request → 401; sign-in refused | Membership row kept (deactivate-first, history intact); audit `user.deactivated`; reactivation later restores sign-in with existing password (audit `user.reactivated`) | BR-IDN-012 |
| 10 | CROSS-CHECK — Dana reviews S61 for the day | ALLOWED | Rows present: step-2 denied-attempt row, both role changes (before/after), deactivate/reactivate — a complete lifecycle trail | Role history lives in audit; the memberships table holds only current state (BR-IDN-010) | BR-AUD-009 · BR-AUD-003 |
