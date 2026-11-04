# EP-IDN-03 — Self-Service Account

> Reconciled 2026-08-08 against PO rulings (decision log) — propagation sweep.

**Module:** identity · **Wave:** W0 · **Screens:** S48 (user menu + My profile / Change password modals) · **Status:** draft

## Scope
**In:** the sidebar-footer user menu (S48 — avatar · name · role button opening the upward popover: **3 items in v1 — My profile, Change password, Sign out** per BR-IDN-028) and its two v1 modals: **My profile** (name, email, phone; role read-only — email fully editable with **no verification email sent in v1**, BR-IDN-027), **Change password** (current/new/confirm + policy hint + sign-out-other-sessions). Available to **every authenticated user, any role** — self-service is distinct from user management (A4 addendum 2026-08-07).
**Out:** the Two-factor menu item and modal — **entirely v2 per BR-IDN-028** (US-IDN-009 deferred below) · Sign out behavior (US-IDN-003) · admin user management (EP-IDN-02) · the tenant-wide 2FA requirement setting (v2, with the 2FA feature — BR-IDN-028) · avatar upload (not in design) · email sending/verification enforcement (v2 — BR-IDN-021/027).

## Capability matrix (list screens only — B9 conformance)
| Screen | Search fields | Filters | Default sort | Sortable | Columns default/available | Row actions | Bulk actions | Export |
|---|---|---|---|---|---|---|---|---|
| — | *(no list screens in this epic)* | | | | | | | |

## Stories

---
id: US-IDN-008
epic: EP-IDN-03
module: identity
screens: [S48]
wave: 0
status: draft
blocked_by: []
depends_on: [US-IDN-002, US-IDN-003, US-IDN-010]
journeys: []
rules: [BR-IDN-015, BR-IDN-016, BR-IDN-021, BR-IDN-027]
golden_tests: []
finance_calc: none
---
### US-IDN-008 — My profile & change password

**1 · Details** — As any signed-in staff user, I want to edit my own name, email and phone, and change my password (optionally killing my other sessions), so that my account stays current and safe without asking an admin. Entry: S48 user menu → **My profile** or **Change password**. My profile modal (prototype): Name, Email, Phone editable; **Role read-only** (shown "Owner · System Admin" — prototype copy predates the A4 role rename; render as the current tenant's `roles.name`, A1/A4 win over prototype copy). Email changes go through the full standard process but **no verification email is sent in v1** — the change applies directly and is audit-logged (BR-IDN-027/021; verification enforcement activates in v2). Change password modal: Current / New / Confirm password, hint "Min 8 chars incl. upper, lower & number (per tenant policy)", **Sign out other sessions** checkbox (default on), **Update password ✓**. Exit: toast; menu closes.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-IDN-015 | Every authenticated user (any role) manages their **own** profile and password via the user menu; this is distinct from user management (System Admin only). | CONFIRMED — A4 addendum 2026-08-07 (self-service) |
| BR-IDN-016 | Change password requires the correct current password; the new password must satisfy the tenant password policy (incl. last-5 history block per BR-IDN-025); "Sign out other sessions" (default on) revokes every session except the current one; the event is audited. | CONFIRMED — PO R1-B13 |
| BR-IDN-027 | Email is captured and changeable via the full standard process in v1; **NO emails are sent** (sending + verification enforcement activate in v2); every email change is audit-logged; global uniqueness (`users.email` UNIQUE) enforced at save; role is never editable through profile (server rejects the field). | CONFIRMED — PO R1-A5 (reworks BR-IDN-017) |
| BR-IDN-021 | v1 sends no staff auth emails (applies to email-change verification too). | CONFIRMED — PO Q&A R2 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Priya edits her name → "Priya Menon-Rao" and phone → +1 (512) 555-0139 | `users` row updated; toast; audit row `user.profile_updated`; new name visible in the S8 user list and sidebar footer |
| TC-2 | Priya changes email to `priya.menon@silvercreek.example` | Uniqueness checked; `users.email` updated atomically — **no verification email sent** (BR-IDN-027/021); audit row `user.email_changed` with before/after; her next sign-in uses the new address only |
| TC-3 *(negative)* | Change password with wrong current password | "Current password is incorrect" error; nothing changes; no session revoked |
| TC-4 *(negative)* | New password `creekside` (fails policy) | Inline policy error citing the tenant policy; unchanged |
| TC-5 *(negative)* | New ≠ Confirm | Inline mismatch error; unchanged |
| TC-6 | Successful change with "Sign out other sessions" on; Priya has 3 active sessions | Password updated; the 2 **other** sessions revoked (replay → 401); current session survives; audit row `auth.password_changed` |
| TC-7 *(negative)* | Priya's PATCH payload includes `role: "System Admin"` | Role field rejected/ignored server-side (privilege escalation guard); membership role unchanged; denied attempt audited |
| TC-8 *(isolation)* | Marcus (Billing Clerk at Silver Creek, System Admin at Blue Mesa) opens My profile while signed in at Silver Creek | Role field shows **Billing Clerk** — the current tenant's membership only; nothing reveals his Blue Mesa role |
| TC-9 *(negative)* | Priya submits email `jordan@bluemesa.example` (already another user's identifier IN THIS TENANT) | Rejected by per-tenant uniqueness (BR-IDN-029) with an inline error; no change. The same email existing in a DIFFERENT tenant is NOT a conflict and is never revealed |

**4 · Test Data** — Users from US-IDN-004; Priya's current password `Meadow2026sage`, new `Prairie2026wind`, failing `creekside`. New email `priya.menon@silvercreek.example`; colliding email `jordan@bluemesa.example`. Priya's sessions: desktop (current), laptop, tablet. Marcus active at both tenants (US-IDN-004 data).

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Name | S48 profile modal | prototype-extracted ("Alex Reed") | `users.full_name` | text | user-input | required |
| Email | S48 profile modal | prototype-extracted | `users.email` — updated directly in v1, no verification email (BR-IDN-027); the `users.pending_email` + `auth_tokens` verification path is the **v2 seam** | citext | user-input | email format; globally unique; change audit-logged |
| Phone | S48 profile modal | prototype-extracted ("+1 (512) 555-0184") | `users.phone` | text | user-input | optional |
| Role (read-only) | S48 profile modal | prototype-extracted; label per A4 | `roles.name` via current tenant's `tenant_memberships.role_id` | text | computed-display | not writable |
| Current / New / Confirm password | S48 change-pw modal | prototype-extracted | `users.password_hash` | text | user-input | current verifies; new meets tenant policy (incl. last-5 history, BR-IDN-025); confirm matches |
| Sign out other sessions | S48 change-pw modal | prototype-extracted (default on) | **PROPOSED-SCHEMA** `sessions.revoked_at` (all but current) | boolean | user-input | — |
| Password-expiry bookkeeping | — | S8 Security "Expire passwords" (default Never per BR-IDN-025) | **PROPOSED-SCHEMA** `users.password_changed_at` | timestamptz | system-derived | set on every change/reset |

**6 · Acceptance**
- Given any signed-in user, When they save profile edits, Then their own `users` row updates (role untouched) and the change is audited.
- Given a correct current password and a policy-compliant new one, When updated with sign-out-others on, Then only the current session remains alive.
- Given an email change with a unique valid address, When submitted, Then it takes effect immediately with a before/after audit row and **no email is sent** (v1 — BR-IDN-027).

**7 · Finance Calculation** — N/A

**8 · Open Questions**
| OQ | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| OQ-028 | Sender for the email-change verification message | — (resolved; TC-2 reworked to no-email) | Product Owner (chat session) | **CLOSED(→BR-IDN-021..023)** — v1 sends no staff auth emails; verification enforcement is v2 (PO Q&A R2; BR-IDN-027) |

---
id: US-IDN-009
epic: EP-IDN-03
module: identity
screens: [S48]
wave: 0
status: deferred   # v2 per BR-IDN-028
blocked_by: []
depends_on: [US-IDN-010]
journeys: []
rules: [BR-IDN-004, BR-IDN-015, BR-IDN-018, BR-IDN-028]
golden_tests: []
finance_calc: none
---
### US-IDN-009 — Two-factor authentication (authenticator app or SMS)

> **Deferred in full to v2 — BR-IDN-028 (PO R1):** no 2FA enrollment, no 2FA requirement setting, no 2FA user-menu item ships in v1 (the S48 popover has 3 items: Profile / Change password / Sign out). Authenticator AND SMS are both v2 — supersedes BR-IDN-024's authenticator-only-v1. Content below is retained as the v2 reference; do not build.
>
> **2026-08-15 — A BUILD OF THIS STORY WAS REQUESTED AND WAS DECLINED ON THIS RULE. Recorded so the next agent does not re-litigate it.** The lane instruction was *"authenticator-only in v1; SMS is deferred because it needs a provider integration that is out of this release"* — **that is BR-IDN-024, which BR-IDN-028 SUPERSEDED** (`02-business-rules.md`: BR-IDN-024 CONFIRMED PO Q&A R4 2026-08-08, then BR-IDN-028 CONFIRMED PO R1 — *"Two-factor authentication is entirely v2 (authenticator AND SMS — supersedes BR-IDN-024's authenticator-only-v1)"*). Nothing in `12-governance/01-open-questions.md` or `02-decision-log.md` reopens it, and **OQ-027's own closure records exactly this history**: closed to authenticator-only, *"then superseded by BR-IDN-028"*.
>
> Building the authenticator path would therefore have meant implementing a superseded rule over a CONFIRMED one, and it would have contradicted four other places that already depend on BR-IDN-028: the S48 popover ships **3 items** (EP-IDN-03 §In), the Security tab ships **no 2FA section** (EP-IDN-04 / BR-IDN-019), `11b-api-audit.md` records **"none in v1 — mint no endpoint"** for S48 2FA, and EP-INT-04 sequences SSO *"consistent with 2FA v2"*. It would also have created a security surface — a TOTP secret at rest — with no OQ-016 crypto kernel to protect it. **Nothing was built.** Reversing this needs a PO ruling that supersedes BR-IDN-028, recorded in `12-governance/02-decision-log.md` before any code, per CLAUDE.md law 9.

**1 · Details** — As any signed-in staff user, I want to add a second sign-in step using an authenticator app (or SMS), so that a stolen password alone can't open my utility's data. Entry: S48 user menu → **Two-factor authentication** modal (prototype): copy "Add a second step at sign-in.", **Method** segment — Authenticator app (default) / SMS —, QR block ("Scan this QR in your authenticator app"), **Enter 6-digit code**, **Enable 2FA ✓** / Cancel. Exit: toast; subsequent sign-ins challenge for a code (US-IDN-001/TC-5). Disable later per A6 addendum ("enrolls TOTP/SMS second factor — disable later").

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-IDN-028 | Two-factor authentication is **entirely v2** (authenticator AND SMS); v1 ships no enrollment, no requirement setting, no menu item. | CONFIRMED — PO R1 example review |
| BR-IDN-018 | Enrollment activates only after a correct 6-digit code proves possession (TOTP from the QR-provisioned secret, or a code texted to a verified number); disable requires re-authentication (password) and is **blocked while any of the user's tenant memberships sits under a policy requiring 2FA for their role**; enable/disable are audited. | PROPOSED (v2 mechanics) — prototype 2FA modal + A6 addendum; deferred with the feature per BR-IDN-028 |
| BR-IDN-004 | Tenant policy (S8 Security) can require 2FA for all staff or Executives only — enforced at sign-in (EP-IDN-01) and as the disable-guard here. | CONFIRMED rule, DEFERRED to v2 — BR-IDN-028 |
| BR-IDN-015 | Self-service: each user enrolls/disables their own second factor only. | CONFIRMED — A4 addendum (self-service) |

**3 · Test Cases** *(v2 reference — none run in v1)*
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Priya selects Authenticator app; scans QR; enters the current TOTP code | 2FA enabled (`method=totp`); recovery of the secret impossible via API (write-only); toast; audit row `auth.2fa_enabled`; next sign-in challenges her |
| TC-2 *(negative)* | Priya enters a wrong/expired code `111111` at enrollment | "Code doesn't match" error; 2FA **not** enabled; no partial state persists |
| TC-3 | Diana (already enrolled) reopens the modal | Shows enrolled state with a Disable path (A6 "disable later"); re-entering setup regenerates a fresh secret only after re-verification |
| TC-4 *(negative)* | Diana attempts Disable while Silver Creek policy = "Require 2FA for all staff" | Blocked with reason "your utility requires two-factor for your role" (IS-6 disabled-with-reason + server 409/422) |
| TC-5 | Silver Creek policy = "Require 2FA for Executives only"; Priya (Billing Clerk) disables after re-entering her password | 2FA off; audit row `auth.2fa_disabled`; next sign-in is password-only |
| TC-6 *(negative)* | SMS method chosen while no SMS provider (Twilio, B7 seam) is connected for the platform | SMS option rendered disabled-with-reason (IS-6); TOTP path unaffected |
| TC-7 *(isolation)* | Marcus enrolls TOTP while signed in at Blue Mesa; then signs in at Silver Creek | The second factor is platform-level (`users`), so Silver Creek sign-in also challenges — but each tenant's *requirement* policy is read only from that tenant's own `security_policies` row; Silver Creek's policy never governs his Blue Mesa session and vice versa |

**4 · Test Data** — TOTP secret `JBSWY3DPEHPK3PXP`; valid rolling code from that secret (e.g. `492817` at the fixture timestamp), invalid `111111`. Diana pre-enrolled (US-IDN-001 data). Policies: Silver Creek "all staff" for TC-4 → switched to "Executives only" for TC-5. SMS test number `+1 (512) 555-0139`.

**5 · Data Fields / Mapping** *(v2 reference)*
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Method (Authenticator / SMS) | S48 2FA modal | prototype-extracted (segment, app default) | **PROPOSED-SCHEMA** `users.two_factor_method` enum none\|totp\|sms | enum | user-input | v2 — BR-IDN-028 |
| TOTP secret (via QR) | S48 2FA modal | prototype-extracted (QR block) | **PROPOSED-SCHEMA** `users.totp_secret` — encrypted at rest (approach = OQ-016, existing) | text (encrypted) | system-derived | generated server-side; write-only |
| 6-digit code | S48 2FA modal | prototype-extracted (placeholder `000000`) | verified against secret / SMS code — not stored | 6 digits | user-input | must verify; rate-limited |
| SMS number | S48 2FA modal | GAP — field not shown in prototype | **PROPOSED-SCHEMA** `users.two_factor_phone` (verified copy, distinct from profile phone) | text | user-input | possession-verified |
| Enrollment timestamp | — | derived | **PROPOSED-SCHEMA** `users.two_factor_enrolled_at` | timestamptz | system-derived | — |

**6 · Acceptance** *(v2 reference)*
- Given an unenrolled user, When they scan the QR and enter a valid code, Then 2FA is on, audited, and enforced at their next sign-in.
- Given a wrong code, When submitted, Then enrollment does not activate and no secret is left half-enabled.
- Given a tenant policy requiring 2FA for the user's role, When disable is attempted, Then it is refused with the policy reason.

**7 · Finance Calculation** — N/A

**8 · Open Questions**
| OQ | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| OQ-027 | Does SMS 2FA ship in wave 0 (requires the Twilio seam, B7)? | — (resolved; story deferred) | Product Owner (chat session) | **CLOSED(→BR-IDN-024)** — authenticator-only v1 confirmed (PO Q&A R4), then **superseded by BR-IDN-028**: 2FA entirely v2, authenticator AND SMS |
