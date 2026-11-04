# EP-IDN-01 — Authentication

> Reconciled 2026-08-08 against PO rulings (decision log) — propagation sweep.

**Module:** identity · **Wave:** W0 · **Screens:** S2, S3, S48 (sign-out entry) · **Status:** draft

## Scope
**In:** email + password sign-in at the tenant subdomain (S3 / sign-in card on S2), forgot-password assist under the v1 no-email model (S3 link → the forgot-password page `/{tenant}/forgot-password`, *"Ask your System Admin…"*, no contact shown — **AMENDED 2026-10-05, `CR-170-BRC10`**, was a "Contact your administrator" notice; System-Admin-issued temporary passwords — BR-IDN-021/022/023), server-side sessions with idle/absolute timeout (BR-IDN-026), and sign-out (S48 user menu).
**Out:** the 2FA challenge and forced-enrollment step at sign-in — **entirely v2 per BR-IDN-028** (was In pre-reconciliation) · user CRUD and roles (EP-IDN-02) · self-service profile (EP-IDN-03) · security-policy configuration (EP-IDN-04) · SSO (`sso_links` exists in B2 but has no UI — B7 build seam, B2 O-13) · customer-portal auth (no portal screens in v1) · tenant provisioning / owner-signup login creation (S114, tenancy module).

## Capability matrix (list screens only — B9 conformance)
| Screen | Search fields | Filters | Default sort | Sortable | Columns default/available | Row actions | Bulk actions | Export |
|---|---|---|---|---|---|---|---|---|
| — | *(no list screens in this epic)* | | | | | | | |

## Stories

---
id: US-IDN-001
epic: EP-IDN-01
module: identity
screens: [S2, S3]
wave: 0
status: draft
blocked_by: []
depends_on: []
journeys: []
rules: [BR-IDN-001, BR-IDN-002, BR-IDN-003, BR-IDN-004, BR-IDN-025, BR-IDN-028]
golden_tests: []
finance_calc: none
---
### US-IDN-001 — Sign in with email and password

**1 · Details** — As a staff user (any of the 3 predefined roles), I want to sign in with my work email and password at my utility's subdomain, so that I reach the dashboard and work under my role's permissions. Entry: public Pricing (S1) → Welcome gateway (S2) sign-in card, or direct link to Sign-in (S3). Fields per prototype: **Work email**, **Password**, **Keep me signed in** checkbox, **Forgot password?** link, **Sign in →** button. Exit: → Dashboard (S7) on success; inline error and stay on failure. *(The prototype's 2FA-challenge exit is v2-deferred — no 2FA challenge or forced enrollment ships in v1, BR-IDN-028.)* The tenant is resolved from the request subdomain, never from client input (B3).

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-IDN-001 | Sign-in requires verified credentials (`users.password_hash`) **and** an active `tenant_memberships` row for the tenant resolved from the subdomain; `app.tenant_id` is set server-side per B3. | CONFIRMED — PO R1-B (B3 session-context propagation + B2 identity DDL) |
| BR-IDN-002 | All authentication failures return one generic message; the response never discloses whether the email exists, the password failed, or the membership is inactive. | CONFIRMED — PO R1-B11 (OWASP-standard; prototype is silent) |
| BR-IDN-003 | Repeated failed sign-ins lock the account: **5 failed attempts → 15-minute lock** (values per BR-IDN-025, which closed OQ-025). | CONFIRMED — PO Q&A R4 (BR-IDN-025) |
| BR-IDN-004 | Tenant-policy 2FA requirement (all staff / Executives only) forces the 6-digit challenge and enrollment. **v2-deferred: no 2FA challenge, requirement setting, or enrollment ships in v1** (BR-IDN-028 — 2FA entirely v2). | CONFIRMED rule, DEFERRED to v2 — BR-IDN-028 (PO R1 example review) |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Alex (active System Admin) submits correct email + password at `silvercreek.smartbillhub.app` | Session created; redirected to Dashboard S7; `audit_log` row `auth.sign_in` with actor + timestamp |
| TC-2 *(negative)* | Alex submits a wrong password | Generic "email or password is incorrect" inline error; no session; no field-level disclosure |
| TC-3 *(negative)* | Unknown email `nobody@silvercreek.example` submitted | Identical generic error and response timing as TC-2 (no user enumeration) |
| TC-4 *(negative)* | User whose Silver Creek membership is `deactivated` submits correct credentials | Sign-in denied with the same generic error; no session |
| TC-5 *(v2-deferred — BR-IDN-028)* | Diana (Executive, TOTP enrolled) signs in with correct credentials | *Not built in v1.* v2 expectation retained: 2FA challenge shown; correct 6-digit code → Dashboard; wrong code → challenge error, no session |
| TC-6 *(v2-deferred — BR-IDN-028)* | Tenant policy = "Require 2FA for all staff"; Priya (not enrolled) signs in | *Not built in v1* (no 2FA-requirement setting exists in v1 — BR-IDN-028). v2 expectation retained: forced into enrollment before any app screen |
| TC-7 *(isolation)* | Jordan (member of Blue Mesa only) submits correct credentials at `silvercreek.smartbillhub.app` | Denied with the generic error (no Silver Creek membership); no Silver Creek data returned; RLS `app.tenant_id` never set to Silver Creek for Jordan |
| TC-8 *(negative)* | 5 consecutive wrong passwords for Alex, then a 6th attempt with the **correct** password 2 minutes later | 6th attempt refused with the same generic error; after the lock lapses, correct credentials sign in; `audit_log` rows `auth.sign_in_failed` ×5 + `auth.lockout`. ⚠ **AMENDED `CR-145-BRC08` 2026-09-28 — THE 5 AND THE 15 ARE SILVER CREEK'S CONFIGURED VALUES, NOT THE PLATFORM'S.** They are still 5 and 15 because those are the DEFAULTS (`BR-IDN-025` as amended), so this case's numbers do not move and it must go on passing unchanged. **What changed is why it holds:** the threshold is now the tenant's `lockout_max_failed` (3–10) and the lock its `lockout_minutes` (5–60), read per tenant. |

**4 · Test Data**
- Tenant A: **Silver Creek Water**, subdomain `silvercreek`. Tenant B: **Blue Mesa Utilities**, subdomain `bluemesa`.
- `alex@silvercreek.example` / `Canyon2026rapids` — System Admin, active.
- `priya@silvercreek.example` / `Meadow2026sage` — Billing Clerk, active.
- `diana@silvercreek.example` / `Vista2026peak` — Executive, active. *(v2 fixture, retained for deferred TC-5: TOTP secret `JBSWY3DPEHPK3PXP`, valid code e.g. `492817`, invalid `111111`.)*
- `jordan@bluemesa.example` / `Mesa2026bluff` — System Admin at Blue Mesa only.
- Deactivated member: `carla@silvercreek.example` / `River2026stone`, membership status `deactivated`.
- Lockout values: 5 failed attempts → 15-minute lock (BR-IDN-025).

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Work email | S2/S3 | prototype-extracted (placeholder `alex@utility.com`) | `users.email` | citext | user-input | email format; required |
| Password | S2/S3 | prototype-extracted | verified against `users.password_hash` | text (never stored raw) | user-input | required; never logged |
| Keep me signed in | S2/S3 | prototype-extracted | **PROPOSED-SCHEMA** `sessions.persistent` (new table, see US-IDN-003) | boolean | user-input | ⚠ **AMENDED `CR-145-BRC08` 2026-09-28:** the tick box is offered only when the tenant offers it (default **on**); its refresh window is the tenant's, **1–30 days, default 30**. The box itself still starts unticked for the user. |
| Tenant (from subdomain) | — | B3 §session propagation | `tenants.subdomain` (tenancy, read via service) | text | system-derived | must resolve to live tenant |
| Membership check | — | B2 identity | `tenant_memberships` + **PROPOSED-SCHEMA** `tenant_memberships.status` | enum invited\|active\|deactivated | system-derived | must be `active` |
| Lockout counter | — | BR-IDN-025 | **PROPOSED-SCHEMA** `users.failed_attempts` + `users.locked_until` (or session-store equivalent) | int / timestamptz | system-derived | 5 fails → locked 15 min |
| Sign-in audit | — | S8 Security panel copy | `audit_log` (action `auth.sign_in` / `auth.sign_in_failed` / `auth.lockout`) | jsonb | system-derived | append-only |

**6 · Acceptance**
- Given an active Silver Creek member with correct credentials, When they sign in at `silvercreek.smartbillhub.app`, Then they land on the Dashboard with `app.tenant_id` = Silver Creek and an `auth.sign_in` audit row exists.
- Given any invalid combination (bad password / unknown email / deactivated or missing membership), When submitted, Then one identical generic error is shown and no session exists.
- Given 5 consecutive failed attempts, When a 6th sign-in is tried within 15 minutes, Then it is refused with the generic error even with correct credentials (BR-IDN-025).
- *(v2-deferred — BR-IDN-028)* Given a 2FA-enrolled user, When credentials pass, Then the dashboard is unreachable until a valid 6-digit code is entered.

**7 · Finance Calculation** — N/A

**8 · Open Questions**
| OQ | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| OQ-025 | Lockout/throttle thresholds (part of security-policy defaults) | — (resolved) | Product Owner (chat session) | **CLOSED(→BR-IDN-025)** — 5 failed → 15-min lock (PO Q&A R4) |

---
id: US-IDN-002
epic: EP-IDN-01
module: identity
screens: [S3, S8]
wave: 0
status: draft
blocked_by: []
depends_on: [US-IDN-003, US-IDN-010]
journeys: []
rules: [BR-IDN-002, BR-IDN-005, BR-IDN-016, BR-IDN-021, BR-IDN-022, BR-IDN-023, BR-IDN-025]
golden_tests: []
finance_calc: none
---
### US-IDN-002 — Forgot password / admin-issued temporary password (no-email v1)

**1 · Details** — As a staff user who forgot my password, I want a clear path back in, so that I regain access via my System Admin — v1 sends **no staff auth emails** (BR-IDN-021; OQ-028 closed). Flow: **Forgot password?** on S3 opens its own public page `/{tenant}/forgot-password` (ONB-06) — **Forgot your password?** · **Ask your System Admin. They give you a temporary password. Sign in with it.** · **Back to sign in**, and **no contact at all** (BR-IDN-023 as amended 2026-10-05, `CR-170-BRC10`; until then a static "Contact your administrator" notice); a System Admin issues a new temporary password from the user's row on Users & roles (S8), shown **once on screen** (BR-IDN-022/023); the temp password is valid **7 days** (BR-IDN-025) and forces a password change at first sign-in, before any app screen (BR-IDN-022); the successful change revokes all the user's existing sessions and writes an audit row (BR-IDN-005 as-reworked). Exit: S3 sign-in with the temp password → forced-change screen → **the session is ended and the user lands on S3 with *Password changed. Sign in again.*** → sign-in with the new password → Dashboard (BR-IDN-022 as amended 2026-10-05, `CR-170-BRC10`; until then the forced change went straight to the Dashboard). *(Reworked from the pre-ruling emailed-reset-link design; the earlier request-form/link/token flow does not ship in v1.)*

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-IDN-023 | Password reset v1: a System Admin issues a new temporary password; "Forgot password?" opens its own page — ask your System Admin, **no contact shown** — no request form, no token, no email. | CONFIRMED-AS-AMENDED 2026-10-05 (`CR-170-BRC10`) · was CONFIRMED — PO Q&A R4 (derived from BR-IDN-021), when it displayed "Contact your administrator" |
| BR-IDN-021 | v1 sends NO staff auth emails; email verification is a v2 feature. | CONFIRMED — PO Q&A R2 (closes OQ-028) |
| BR-IDN-022 | The user must change the temporary password at first sign-in — a forced-change screen gates every app screen until done. | CONFIRMED — PO Q&A R4 |
| BR-IDN-025 | Temporary passwords are valid 7 days; an expired temp password cannot sign in — the admin issues a new one. | CONFIRMED — PO Q&A R4 (closes OQ-025) |
| BR-IDN-005 | (as-reworked R2, no-email) The admin temp password replaces reset/invite links entirely in v1; a successful forced change revokes **all** the user's existing sessions and is audited. | CONFIRMED-REWORKED — identity rules BR-IDN-005 |
| BR-IDN-016 | The new password set at forced change must satisfy the tenant password policy. | CONFIRMED — PO R1-B13 |
| BR-IDN-002 | Sign-in attempts with voided or expired temp passwords fail with the one generic message. | CONFIRMED — PO R1-B11 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Priya clicks **Forgot password?** on S3 | Opens `/{tenant}/forgot-password`: *Forgot your password?* · *Ask your System Admin. They give you a temporary password. Sign in with it.* · *Back to sign in*; no contact, no email field, no token created, no email sent (BR-IDN-021/023 as amended 2026-10-05, `CR-170-BRC10`) |
| TC-2 | Alex (System Admin) issues a temp password from Priya's S8 row | Temp password `Vr8k-Tq2m-Zw5c` displayed exactly once on screen to Alex; `must_change_password` set; expiry = issue + 7 days; audit row `auth.temp_password_issued` (actor Alex, subject Priya) |
| TC-3 | Priya signs in with the temp password on day 2 and sets `Harbor2026tide` (meets policy) on the forced-change screen | Sign-in lands only on the forced-change screen; on change: password updated, `must_change_password` cleared, **all** her prior sessions revoked, audit row `auth.password_reset`; then the session is ended and she lands on S3 with *Password changed. Sign in again.*; she signs in with `Harbor2026tide` and reaches the Dashboard (amended 2026-10-05, `CR-170-BRC10`) |
| TC-4 *(negative)* | The temp password is tried again after TC-3 | Generic sign-in error (BR-IDN-002); no session; no change |
| TC-5 *(negative)* | A temp password is tried on day 8 (past the 7-day validity, BR-IDN-025) | Generic sign-in error; no session; a fresh temp password must be issued |
| TC-6 *(negative)* | Forced-change screen: new password `creekside` (no upper/number) submitted | Inline policy violation error; password unchanged; user stays on the forced-change screen |
| TC-7 *(negative)* | Priya requests a Dashboard URL directly after temp-password sign-in but before completing the change | Redirected to the forced-change screen — no app screen reachable until the change (BR-IDN-022) |
| TC-8 *(isolation)* | Jordan (Blue Mesa System Admin) calls the issue-temp-password endpoint with the id of Priya's Silver Creek membership | 404 under Blue Mesa's `app.tenant_id` (RLS); no temp password issued; nothing changes |

**4 · Test Data** — Users from US-IDN-001. Temp password (system-generated, shown once): `Vr8k-Tq2m-Zw5c`, issued Aug 8, 2026 10:00 CT → expires Aug 15, 2026 10:00 CT (7 days, BR-IDN-025). New password `Harbor2026tide`; failing password `creekside`. Tenant policy: min 8, require upper/lower/number (Silver Creek).

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Forgot password? (link) | S3 | prototype-extracted link; target reworked per BR-IDN-023 | — (links to the forgot-password page, `CR-170-BRC10`; no DB write) | — | computed-display | — |
| Temp password (issue action) | S8 row action (GAP — modal designed post-prototype; no-email rework) | BR-IDN-022/023 | `users.password_hash` (temp value) + **PROPOSED-SCHEMA** `users.must_change_password` boolean, `users.temp_password_expires_at` timestamptz | text (never stored raw) | system-derived | expiry = issue + 7 days (BR-IDN-025); System Admin only (BR-IDN-009) |
| New password / confirm (forced change) | forced-change screen (GAP — derived from S48 change-pw modal) | derived | `users.password_hash` | text | user-input | tenant policy (BR-IDN-016); confirm must match |
| Session revocation | — | BR-IDN-005 (as-reworked) | **PROPOSED-SCHEMA** `sessions.revoked_at` | timestamptz | system-derived | all rows for user on successful change |
| Audit | — | S8 Security panel copy | `audit_log` (`auth.temp_password_issued` / `auth.password_reset`) | jsonb | system-derived | append-only |

**6 · Acceptance**
- Given a forgotten password, When "Forgot password?" is clicked, Then the forgot-password page opens — ask your System Admin, no contact shown, no form, no token, no email (BR-IDN-021/023 as amended 2026-10-05, `CR-170-BRC10`).
- Given an unexpired temp password, When the user signs in and completes the forced change with a policy-compliant password, Then sign-in works with the new password only, every prior session is dead, and audit rows exist for issue + change.
- Given an expired (> 7 days) or already-replaced temp password, When tried, Then sign-in is refused with the generic error.

**7 · Finance Calculation** — N/A

**8 · Open Questions**
| OQ | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| OQ-025 | Reset/invite token lifetime (with policy defaults) | — (resolved) | Product Owner (chat session) | **CLOSED(→BR-IDN-025)** — temp password valid 7 days (PO Q&A R4) |
| OQ-028 | Which sender delivers staff auth emails (reset/invite)? | — (resolved; story unblocked) | Product Owner (chat session) | **CLOSED(→BR-IDN-021..023)** — v1 sends no staff auth emails; admin-managed temp passwords (PO Q&A R2) |

---
id: US-IDN-003
epic: EP-IDN-01
module: identity
screens: [S48]
wave: 0
status: draft
blocked_by: []
depends_on: [US-IDN-001, US-IDN-010]
journeys: []
rules: [BR-IDN-006, BR-IDN-007, BR-IDN-026]
golden_tests: []
finance_calc: none
---
### US-IDN-003 — Sessions and sign-out

**1 · Details** — As a signed-in staff user, I want my session to be tracked server-side, expire after inactivity, and end cleanly when I choose **Sign out** from the user menu (S48), so that unattended or shared machines don't expose tenant data. Entry: session is created by US-IDN-001; Sign out is the last item of the S48 popover. Exit: sign-out returns to the public Pricing/sign-in screen (prototype `doLogout` → pricing; A6 addendum). Sessions are the substrate for "sign out other sessions" (US-IDN-008), deactivation revocation (US-IDN-006), and the Security-tab timeout (US-IDN-010).

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-IDN-006 | Sessions are server-side records bound to (user, tenant); idle timeout comes from the tenant security policy — **default 60 minutes** (tenant-configurable 30 min–8 h); **absolute lifetime 12 hours**; revocation is server-side and immediate; **"Keep me signed in" = 30-day trusted-device refresh, off by default** (values per BR-IDN-026, which closed OQ-026). | CONFIRMED — PO Q&A R4 (BR-IDN-026) |
| BR-IDN-007 | Sign out ends the current session and returns to the public screen; re-login is required to return. | CONFIRMED — A6 addendum 2026-08-07 (user-menu actions) + A1 addendum |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Alex clicks Sign out in S48 | Session row revoked server-side; browser lands on public Pricing/sign-in; `audit_log` row `auth.sign_out` |
| TC-2 *(negative)* | An API request replays the session token from TC-1 after sign-out | 401; no data returned |
| TC-3 | Tenant timeout configured 30 minutes; Priya idle 31 minutes | Next request 401 → redirected to S3 with a "signed out for inactivity" notice. ⚠ **AMENDED `CR-145-BRC08` 2026-09-28 — 30 SURVIVES THE NARROWING AND THIS CASE IS UNCHANGED.** The choices become **15 / 30 / 45 / 60**, so 30 is still offered; **240 and 480 are WITHDRAWN** and a tenant on either is migrated to 60. |
| TC-4 | Priya active every few minutes | Session's `last_seen_at` slides; no timeout at 31 minutes of wall-clock |
| TC-5 *(negative)* | A request presents a syntactically valid but revoked/unknown session id | 401; attempt appears in security log; no `app.tenant_id` set |
| TC-6 *(isolation)* | Marcus holds an active Blue Mesa session; the same session token is presented against `silvercreek.smartbillhub.app` | 401/403 — a session is bound to one tenant; no Silver Creek data; switching tenants requires a fresh sign-in (multi-tenant switch is A17 #13, open) |
| TC-7 *(negative)* | Alex stays continuously active for 12 hours | Next request after the 12-hour mark is 401 — the hard limit caps even active sessions (BR-IDN-026); fresh sign-in required. ⚠ **AMENDED `CR-145-BRC08` 2026-09-28 — 12 IS NOW SILVER CREEK'S SETTING RATHER THAN THE PLATFORM'S CONSTANT**, and stays 12 because that is the default, so this case's figure does not move. **A SECOND CASE IS NOT A REWRITE OF THIS ONE:** a tenant configured to the floor of **4 hours** must 401 at the 4-hour mark. ⚠ **WRITTEN 2026-09-28 and green** — `06-backend/tests/test_cr145_session_settings.py::test_t1_hard_limit_four_hours_expires_at_four_hours_one_minute` (still 200 at 3 h 59 min of activity, 401 at 4 h 01 min). |
| TC-8 | Priya signs in with **Keep me signed in** checked, closes the browser, returns after 2 days | Trusted-device refresh silently re-establishes a session (within the tenant's renewal window, 30 days at Silver Creek); returning after 31 days → full sign-in required; unchecked → no refresh, normal idle/hard-limit rules only. ⚠ **AMENDED `CR-145-BRC08` 2026-09-28, AND THIS CASE CARRIED A CLAIM THAT WAS ALREADY FALSE.** *"Closes the browser, returns after 2 days"* **did not work in the built product**: all three `set_cookie` calls passed no expiry, so the cookie died with the browser and the 30-day server-side refresh had nothing to travel in. Wiring the cookie's lifetime to the tick box is what makes this case true for the first time — **it is a fix, not a feature.** **TWO FURTHER CASES, BOTH WRITTEN 2026-09-28 AND GREEN in `06-backend/tests/test_cr145_session_settings.py`:** the window is **1–30 days** — a **1-day** window stops renewing after one day (`test_t1_renewal_one_day_stops_renewing_after_one_day`); and *"Keep me signed in"* may now be **switched off per utility**, in which case the tick box is **not offered at all**, a sign-in that still asks for it is **refused by name** (`identity.signIn.keepSignedInUnavailable`, not the generic failure), and a persistent session that already exists is **never renewed** (`test_t3_the_request_asking_for_it_is_refused`, `test_t3_and_no_renewal_ever_happens`). ⚠ **"off by default" IS STRUCK** — the OFFER defaults ON (`BR-IDN-026` as amended). |

**4 · Test Data** — Silver Creek policy `session_timeout_minutes = 30` (a configured value; the seed default for new tenants is **60 min** per BR-IDN-026). Hard limit 12 h; keep-me-signed-in trusted-device window 30 days (BR-IDN-026). ⚠ **AMENDED `CR-145-BRC08` 2026-09-28:** all three are now per-tenant settings at their DEFAULTS — idle ∈ 15/30/45/60, hard limit 4–12 h, renewal window 1–30 days — so this fixture is unchanged and stays valid. **The floors are exercised case by case rather than as one fixture** (idle 15 → `T11`, hard limit 4 h, window 1 day, offer OFF → `T1`/`T3` in `test_cr145_session_settings.py`), each on top of this fixture with the one value changed. Marcus: active membership at Blue Mesa (System Admin) and invited at Silver Creek. Session ids: UUID v7; tokens opaque, httpOnly.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Session record | — | derived (no UI) | **PROPOSED-SCHEMA** `sessions` (platform table: id, user_id, tenant_id, persistent bool, created_at, last_seen_at, expires_at, revoked_at, ip inet, user_agent text) | — | system-derived | one active tenant per session; hard-limit expiry = the tenant's setting, **4–12 h, default 12** (BR-IDN-026 as amended by `CR-145-BRC08`, 2026-09-28) |
| Idle timeout | S8 Security | prototype-extracted (options 30 min/1 h/4 h/8 h) | **PROPOSED-SCHEMA** `security_policies.session_timeout_minutes` (see US-IDN-010) | integer minutes | reference-data | ⚠ **AMENDED `CR-145-BRC08` 2026-09-28: the option set is now ∈ {15, 30, 45, 60}, default 60.** The prototype's 4 h and 8 h are **WITHDRAWN**; a tenant holding 240 or 480 is migrated to 60. |
| Keep me signed in | S2/S3 | prototype-extracted checkbox | **PROPOSED-SCHEMA** `sessions.persistent` + trusted-device refresh token (the tenant's window) | boolean | user-input | ⚠ **AMENDED `CR-145-BRC08` 2026-09-28:** whether the box is OFFERED is the tenant's choice (default **on**); its window is **1–30 days, default 30**. The cookie's own lifetime FOLLOWS this box and is not a seventh setting. |
| Sign out (menu item) | S48 | A1 addendum user menu | `sessions.revoked_at` | timestamptz | user-input → system-derived | current session only |

**6 · Acceptance**
- Given a signed-in user, When they sign out, Then the session is dead server-side (replay = 401) and the public screen is shown.
- Given a tenant timeout of N minutes, When a session is idle > N minutes, Then the next request is rejected and the user is returned to sign-in with an inactivity notice.
- Given continuous activity, When a session passes **the tenant's hard limit** (4–12 h, default 12), Then re-authentication is required (BR-IDN-026 as amended by `CR-145-BRC08`, 2026-09-28).
- Given a tenant that has switched *"Keep me signed in"* OFF, When the sign-in screen renders, Then the tick box is not offered at all and no persistent session can be created (`CR-145-BRC08`, 2026-09-28).
- Given a session bound to tenant A, When presented against tenant B, Then it is rejected.

**7 · Finance Calculation** — N/A

**8 · Open Questions**
| OQ | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| OQ-026 | Default idle timeout; "Keep me signed in" lifetime and idle interaction | — (resolved) | Product Owner (chat session) | **CLOSED(→BR-IDN-026)** — idle 60 m / absolute 12 h / keep-signed-in 30 d (PO Q&A R4) |

---
```yaml
id: US-IDN-011
epic: EP-IDN-01
module: identity
screens: []
wave: 1
status: built            # 2026-08-15 — see the AMENDMENT under §8
blocked_by: []           # was [OQ-078]; CLOSED 2026-08-10 ("leave it as it is")
depends_on: [US-IDN-001]
journeys: []
rules: [BR-IDN-027]
golden_tests: []
finance_calc: none
```
### US-IDN-011 — Reaching your utility's sign-in from a page that has no tenant

**1 · Details** — As a staff user who opened the marketing site rather than my utility's address, I want to get to my own sign-in page, so that I am not stuck on a public page whose "Sign in" link cannot know where to send me. Entry: the public nav's Sign in → `/signin-help`. I type the web address my utility chose at signup and land on `/{tenant}/signin`.

**Why this story exists at all.** Tenancy became path-based on 2026-08-10, which made sign-in per-tenant (`/{tenant}/signin`) and left the public pages with a Sign-in link that has no tenant to point at. The ruling named `/signin-help` as the destination; no A1 screen and no A13 copy were ever written for it, so the route shipped pointing at the W0 placeholder and rendered the literal string "SMARTBillHub — W0 scaffold" on a public page until the PO found it on the first live deployment. **The gate stack caught the deeper defect:** a traced file with no US-ID. This story is that ID.

**No screen ID is claimed.** A1 has no entry for this route and CLAUDE.md forbids renumbering; S72 is a *proposal* riding with OQ-078, not an assignment.

**2 · Business Rules**
| BR-ID | Statement | Status |
|---|---|---|
| BR-IDN-027 | The tenant-less sign-in landing **performs no lookup of any kind.** It validates the typed address against the BR-TEN-011 grammar and forwards to `/{tenant}/signin`; it never asks the server whether that utility exists. Every lookup here is a membership oracle: by email it would confirm membership to anyone who guessed an address (and BR-IDN-021 already bars staff auth emails from v1 surfaces), by utility name it would confirm which utilities exist on the platform. Both are the disclosure BR-IDN-006 exists to prevent. The reserved-name list is likewise not mirrored client-side | PROPOSED — derives from BR-IDN-006 (wrong tenant is indistinguishable from missing tenant) + BR-IDN-021; PO ruling 2026-08-10 named the route |

**3 · Test Cases**
| TC-# | Scenario | Expected |
|---|---|---|
| TC-1 | Open `/signin-help` | A real page renders — no "W0 scaffold" marker anywhere in the markup |
| TC-2 | Type `brazosbend`, submit | Navigates to `/brazosbend/signin` |
| TC-3 | Type `no-such-utility-here`, submit | Navigates to `/no-such-utility-here/signin`, which renders **identically** to a real tenant's sign-in. Unknown is indistinguishable from real |
| TC-4 (neg) | Type `Not A Slug!` | Rejected locally with an inline message; no navigation, no request |
| TC-5 (neg) | Type `ab` (2 chars) or a leading/trailing hyphen | Rejected — the page enforces exactly BR-TEN-011's 3–63 grammar, the same rule `selectors.subdomain_problem` applies server-side |
| TC-6 (neg) | Type a reserved name such as `api` | Accepted by the client and forwarded like any other name — the reserved list is server knowledge and is not mirrored |
| TC-7 (isolation) | Any address, real or invented | No network request leaves the page, so there is nothing to leak and no timing difference to measure |

**4 · Test Data** — `brazosbend` (real), `silver-creek-water-work` (the PO's own signup fixture, 2026-08-10), `no-such-utility-here` (invented), `Not A Slug!`, `ab`, `-leading`, `trailing-`, `api`, 63×`a`, 64×`a`.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Utility web address | `/signin-help` | GAP — route named by PO ruling 2026-08-10, no A1 screen | **none — never persisted, never sent** | text | user-input | BR-TEN-011 grammar, client-side only |

**6 · Acceptance** — **Given** I am on the public site with no tenant in scope, **when** I click Sign in and type my utility's web address, **then** I land on that utility's sign-in page — **and** an address that does not exist behaves exactly like one that does, because the page never asks.

**7 · Finance Calculation** — N/A.

**8 · Open Questions**
| OQ-ID | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| OQ-078 | The genuine recovery path for a user who has **lost** the address. Every in-product lookup is a membership oracle (BR-IDN-027), so the answer probably lives outside the page — Eng recommends an emailed "your utilities" link to the address on file, which tells the requester nothing they did not already control | the recovery branch of `/signin-help`; whether S72 is minted at all | Product Owner | **OPEN** |

> **AMENDMENT 2026-08-15 (build lane) — OQ-078 IS CLOSED AND THE ROW ABOVE IS THE STALE VERSION.** The PO answered on **2026-08-10**: **"leave it as it is."** Building the URL from a slug the user types, with no lookup by email, is the ruled trade — an email-based lookup would confirm membership to any stranger who guessed an address (BR-IDN-006/BR-IDN-021). **So no recovery feature is added and S72 is not minted.** The copy under the form (`signinHelp.noAddress`) points at the one channel that leaks nothing — a colleague already signed in, who has the address in their own browser bar. That sentence IS the ruling and the page now says so in its own docstring.
>
> **What this lane changed** (the page itself shipped 2026-08-10 and was already wired into `App.tsx`):
> * **The file finally CLAIMS the story.** Its Trace header said `Story: (none — see below)` because the page was written before the story existed — the reverse of the usual failure, and G1/G3 were what forced the story into being. It now cites US-IDN-011 and BR-IDN-027.
> * **Three stale comments corrected — hard-won law 1, three times in one route.** `tenantPath.ts`'s `SIGNIN_HELP_ROUTE` docstring, that file's Lifecycle `exceptions:` line, and the routing comment in `App.tsx` all still said the route *"renders the W0 marker"*. It has not since **2026-08-10**, when this page replaced the placeholder — the comments outlived the defect by five days. Each now carries the correction and its date rather than being silently deleted.
> * **TC-2, TC-3, TC-6 and TC-7 are asserted instead of deferred.** They stood as one `it.todo` ("navigation is a Playwright journey") since the page shipped. Navigation is — but WHERE the page decides to send you is a pure function of what you typed, and it is the only behaviour this page has. `signInHelpDestination(typed)` is extracted, the submit handler calls it, and the TCs assert it: a real address and an invented one produce the **same shape** (TC-3, which is the membership-oracle rule itself), a reserved name like `api` is forwarded like any other (TC-6), and the BR-TEN-011 grammar refuses locally with no request (TC-4/TC-5/TC-7).
