# T5-25 — IP allowlist self-lockout (the guard refuses the save that locks you out)

---
id: T5-25
tier: 5
guards: [BR-IDN-020, BR-IDN-019, NFR-12]
stories: [US-IDN-010, US-IDN-001]
# journey→story wiring sweep pending: story frontmatter `journeys:` updated in a later sweep (00-e2e-design.md §6)
---

**Intent.** The tenant IP allowlist accepts valid IPv4 CIDRs, empty = unrestricted, is enforced at sign-in AND per request — and the saving admin's CURRENT IP must be inside the list (BR-IDN-020). Without the self-lockout guard, one typo locks every staff member out of their own utility, including the only person who could fix it. The system must refuse the save, name the admin's current IP, and keep the old policy in force.

**Fixture.** Tenant brazos-bend · System Admin Dana on IP **203.0.113.7** · current policy: allowlist empty (unrestricted) · attempted new allowlist: `198.51.100.0/24` only (excludes 203.0.113.7).

| # | Actor + action | Expected refusal (IS-7 outcome) | Downstream assertions (nothing changed) | Guard |
|---|---|---|---|---|
| 1 | Dana opens S8 Security and saves allowlist `198.51.100.0/24` | Refused: inline form validation (IS-7) — "your current IP 203.0.113.7 is not inside the allowlist"; atomic save aborts | Security-policy record unchanged (allowlist still empty); no before/after audit row (nothing saved — BR-IDN-019 audits the atomic save; BR-AUD-001 scope) | BR-IDN-020 |
| 2 | Dana retries via `PUT /api/security-policy` with the same list | Server-side re-check of the caller's request IP against the submitted CIDRs — same refusal (422 class) | Policy row untouched; sign-in and per-request enforcement continue on the OLD (empty) list | BR-IDN-020 |
| 3 | Probe: malformed entries — `300.1.1.0/24`, `198.51.100.0/33`, bare text | Refused as invalid IPv4 CIDRs, per-entry inline errors | Nothing saved; validation is field-level, atomic-save semantics hold | BR-IDN-020 · BR-IDN-019 |
| 4 | Contrast: Dana saves `198.51.100.0/24, 203.0.113.0/28` (her IP inside) | Save succeeds: atomic, with before/after audit row; enforcement switches to the new list at sign-in and per request | Policy row updated once; audit row present (BR-IDN-019); a colleague on 192.0.2.5 is now refused at sign-in (allowlist enforcement working as configured) | BR-IDN-020 · BR-IDN-019 |
| 5 | Harness verifies per-request enforcement after step 4 | Requests from IPs outside the list are refused (permission-denied posture) even with a valid session; requests from inside proceed | No data leaks to out-of-list callers; Dana never locked out (her IP is inside by construction of the guard) | BR-IDN-020 · NFR-12 |
| 6 | RECOVERY — the ratified door: to restrict to an office range you are not currently on, include BOTH ranges (current + target), migrate, then remove the old range from inside the new one; empty list remains the ratified "unrestricted" state | Each save passes the self-lockout check because the saving admin is always inside the surviving list | Policy transitions are always survivable; every save audited | BR-IDN-020 |
