# identity — Field Map

One row per field. Origin: user-input | system-derived | reference-data | integration | computed-display. Rows cite A2 § or "prototype-extracted"; underivable = GAP (mint an OQ).

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation | Status |
|---|---|---|---|---|---|---|---|
| Work email | S2/S3 | prototype-extracted | users.email | citext | user-input | email format; required | mapped |
| Password (sign-in) | S2/S3 | prototype-extracted | verified vs users.password_hash | text | user-input | required; never logged | mapped |
| Keep me signed in | S2/S3 | prototype-extracted | sessions.persistent | boolean | user-input | — | PROPOSED-SCHEMA (new `sessions` table) |
| Forgot-password email | S3 → GAP form | prototype link only | users.email | citext | user-input | email format | mapped (form design GAP) |
| Reset/invite/email-change token | email links | GAP — standard flow | auth_tokens (user_id, purpose, token_hash, expires_at, used_at) | text (hashed) | system-derived | single-use; unexpired | PROPOSED-SCHEMA (new platform table) |
| Session record | — | derived (no UI) | sessions (user_id, tenant_id, persistent, last_seen_at, expires_at, revoked_at, ip, user_agent) | — | system-derived | one tenant per session | PROPOSED-SCHEMA |
| User list — Name | S8 Users & roles | prototype-extracted | users.full_name | text | reference-data | "—" while invited | mapped |
| User list — Email | S8 Users & roles | prototype-extracted | users.email | citext | reference-data | — | mapped |
| User list — Role | S8 Users & roles | prototype-extracted | roles.name via tenant_memberships.role_id | text | reference-data | 1 of 3 predefined | mapped |
| User list — Last active | S8 Users & roles | prototype-extracted | tenant_memberships.last_active_at | timestamptz | system-derived | null = "Never" | PROPOSED-SCHEMA (new column) |
| User list — Status | S8 Users & roles | prototype-extracted (pills) | tenant_memberships.status (invited\|active\|deactivated) | enum | system-derived | — | PROPOSED-SCHEMA (new column) |
| Invite — Name / Email / Role | S8 invite modal | prototype-extracted | users.full_name · users.email · tenant_memberships.role_id | text/citext/uuid | user-input | email unique-per-tenant membership; role 1 of 3 | mapped |
| Invite — Send invitation email now | S8 invite modal | prototype-extracted (default on) | — (dispatch flag) | boolean | user-input | — | mapped (no column) |
| Invite bookkeeping | S8 | derived | tenant_memberships.invited_at / invited_by | timestamptz/uuid | system-derived | — | PROPOSED-SCHEMA (new columns) |
| RBAC matrix rows/cells | S8 Users & roles | prototype-extracted + A4 addendum | permissions · roles · role_permissions | text | reference-data | read-only, platform catalog | mapped |
| Profile — Name / Phone | S48 profile modal | prototype-extracted | users.full_name · users.phone | text | user-input | name required; phone optional | mapped |
| Profile — Email (pending change) | S48 profile modal | prototype-extracted | users.email after verification; users.pending_email meanwhile | citext | user-input | unique per tenant (BR-IDN-029); v1 admin-only change, no verification (BR-IDN-017); verified | PROPOSED-SCHEMA (pending_email column) |
| Profile — Role (read-only) | S48 profile modal | prototype-extracted; label per A4 | roles.name via current membership | text | computed-display | not writable | mapped |
| Change pw — current/new/confirm | S48 change-pw modal | prototype-extracted | users.password_hash | text | user-input | current verifies; policy; confirm match | mapped |
| Change pw — Sign out other sessions | S48 change-pw modal | prototype-extracted (default on) | sessions.revoked_at (all but current) | boolean | user-input | — | PROPOSED-SCHEMA (`sessions`) |
| Password-changed bookkeeping | — | derived (expiry policy) | users.password_changed_at | timestamptz | system-derived | set on change/reset | PROPOSED-SCHEMA (new column) |
| 2FA — Method | S48 2FA modal | prototype-extracted (app/SMS segment) | users.two_factor_method (none\|totp\|sms) | enum | user-input | ALL 2FA deferred v2 (BR-IDN-028; OQ-027 superseded) | PROPOSED-SCHEMA (new column) |
| 2FA — TOTP secret (QR) | S48 2FA modal | prototype-extracted (QR block) | users.totp_secret (encrypted — app-layer per OQ-016 closure) | text (encrypted) | system-derived | server-generated; write-only | PROPOSED-SCHEMA (new column) |
| 2FA — 6-digit code | S48 2FA modal | prototype-extracted | verified, not stored | 6 digits | user-input | must verify; rate-limited | mapped (no column) |
| 2FA — SMS number | S48 2FA modal | GAP — field not shown | users.two_factor_phone | text | user-input | possession-verified | PROPOSED-SCHEMA (new column) |
| 2FA — enrolled at | — | derived | users.two_factor_enrolled_at | timestamptz | system-derived | — | PROPOSED-SCHEMA (new column) |
| Security — Minimum length | S8 Security | prototype-extracted (8/10/12) | security_policies.pw_min_length | integer | user-input | ∈ {8,10,12} | PROPOSED-SCHEMA (new `security_policies` table) |
| Security — Require upper/lower/number | S8 Security | prototype-extracted | security_policies.pw_require_mixed | boolean | user-input | — | PROPOSED-SCHEMA |
| Security — Require a symbol | S8 Security | prototype-extracted | security_policies.pw_require_symbol | boolean | user-input | — | PROPOSED-SCHEMA |
| Security — Expire passwords | S8 Security | prototype-extracted (Never/90/180) | security_policies.pw_expiry_days (null = Never) | integer days | user-input | ∈ {null,90,180} | PROPOSED-SCHEMA |
| Security — 2FA requirement | S8 Security | prototype-extracted (2 checkboxes) | security_policies.two_factor_requirement (none\|all_staff\|executives) | enum | user-input | mutually exclusive | PROPOSED-SCHEMA |
| Security — Session timeout | S8 Security | prototype-extracted (30 m–8 h) | security_policies.session_timeout_minutes | integer minutes | user-input | ∈ {30,60,240,480}; default OQ-026 | PROPOSED-SCHEMA |
| Security — Allowed IP ranges | S8 Security | prototype-extracted (CIDR placeholder) | security_policies.ip_allowlist | cidr[] | user-input | valid IPv4 CIDRs; self-lockout guard | PROPOSED-SCHEMA |
| Security — View audit log → | S8 Security | prototype-extracted (toast only) | reads audit_log (audit module) | — | computed-display | viewer = S61, tenant-scoped-only (OQ-029 CLOSED) | ok |
