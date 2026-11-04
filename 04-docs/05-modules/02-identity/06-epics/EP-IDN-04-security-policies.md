# EP-IDN-04 — Security Policies

> Reconciled 2026-08-08 against PO rulings (decision log) — propagation sweep.

**Module:** identity · **Wave:** W0 · **Screens:** S8 (Settings → Security tab) · **Status:** draft

## Scope
**In:** the Security tab of Settings (S8, A1 addendum) — **v1 sections per BR-IDN-019 as-confirmed: password policy · session timeout · IP allowlist · audit access**: **Password policy** panel (minimum length, require upper/lower/number, require symbol, expire passwords), **Access** panel (session timeout, allowed IP ranges — the prototype's 2FA-requirement toggles are **removed from the v1 tab**, BR-IDN-028), **Audit log** panel (entry point "View audit log →" → S61 per OQ-029 closure), and **Save security settings**. These values are the policy inputs enforced by EP-IDN-01 (sign-in, sessions) and EP-IDN-03 (password change). Seed defaults for new tenants are confirmed: BR-IDN-025 (password/lockout/temp-password) + BR-IDN-026 (sessions).
**Out:** the audit-log viewer itself (S61 — audit module owns the screen; tenant-scoped-only per OQ-029 closure) · the 2FA-requirement setting (**v2, deferred with the 2FA feature — BR-IDN-028**) · 2FA enrollment (v2 — US-IDN-009 deferred) · SSO configuration (Settings → Integrations, B7) · platform-level security (infrastructure, not tenant-configurable).

## Capability matrix (list screens only — B9 conformance)
| Screen | Search fields | Filters | Default sort | Sortable | Columns default/available | Row actions | Bulk actions | Export |
|---|---|---|---|---|---|---|---|---|
| — | *(no list screens in this epic — the Security tab is a form)* | | | | | | | |

## Stories

---
id: US-IDN-010
epic: EP-IDN-04
module: identity
screens: [S8]
wave: 0
status: draft
blocked_by: []
depends_on: []
journeys: []
rules: [BR-IDN-006, BR-IDN-016, BR-IDN-019, BR-IDN-020, BR-IDN-025, BR-IDN-026, BR-IDN-028]
golden_tests: []
finance_calc: none
---
### US-IDN-010 — Configure tenant security policy

**1 · Details** — As a System Admin, I want to set my utility's password rules, session timeout, and allowed IP ranges, so that staff access matches our risk tolerance. Entry: Settings (S8) → **Security** tab. Controls per prototype (2FA-requirement checkboxes **removed from the v1 tab** per BR-IDN-028): Password policy — **Minimum length** select (8 / 10 / 12; default 8), **Require upper, lower & number** checkbox (default on), **Require a symbol** checkbox (default off), **Expire passwords** select (Never / Every 90 days / Every 180 days; default **Never** — no forced expiry per BR-IDN-025, NIST 800-63); Access — **Session timeout** select (⚠ **AMENDED `CR-145-BRC08` 2026-09-28: 15 minutes / 30 minutes / 45 minutes / 1 hour**; default **1 hour** per BR-IDN-026 — the prototype's 4 hours and 8 hours are WITHDRAWN), **Hard limit after sign-in** (4–12 hours, default 12), **Offer "Keep me signed in"** on/off (default on) and **how long it lasts** (1–30 days, default 30), **Wrong passwords before lockout** (3–10, default 5) and **Lockout length** (5–60 minutes, default 15), **Allowed IP ranges (optional)** input (placeholder `e.g. 203.0.113.0/24`); Audit log panel — copy "Every configuration and money action is recorded with actor, timestamp, and before/after." + **View audit log →** button → tenant-scoped audit-log viewer **S61** (OQ-029 CLOSED); **Save security settings** button → toast. Executives see the tab read-only (A4: Settings = View); Billing Clerks get no access. Exit: stays on tab. Seed defaults for newly provisioned tenants are confirmed (BR-IDN-025/026): min 8 · upper+lower+number on · symbol optional/off · expiry Never · last-5 password-history block · lockout 5 failed → 15-min lock · temp-password validity 7 days · idle 60 min · hard limit 12 h · keep-me-signed-in offered, 30-day window. ⚠ **AMENDED `CR-145-BRC08` 2026-09-28 — THE FIGURES ABOVE DO NOT MOVE; SIX OF THEM STOP BEING PLATFORM-FIXED AND BECOME THIS TENANT'S TO EDIT** (idle ∈ 15/30/45/60 · hard limit 4–12 h · offer on/off · window 1–30 d · lockout threshold 3–10 · lockout length 5–60 min). ⚠ **"keep-me-signed-in off" IS STRUCK AND REPLACED:** what defaults ON is whether the tick box is OFFERED; the box itself still starts unticked for the user. ⚠ **THE PASSWORD HALF IS UNCHANGED AND IS NAMED HERE BECAUSE IT SITS ON THE SAME TAB** — min length, the character rules, expiry, the last-5 history block and the 7-day temporary password all stay FIXED.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-IDN-019 | Security policy is one tenant-wide record, editable by System Admin only, read-only for Executives, saved atomically and audited with before/after. **v1 sections: password policy · session timeout · IP allowlist · audit access — the 2FA-requirement section is deferred with the 2FA feature (BR-IDN-028).** New-tenant defaults per BR-IDN-025/026. | CONFIRMED — PO R1 example 2 |
| BR-IDN-025 | Seed password-policy defaults: min 8, upper+lower+number required, symbol optional, **no forced expiry** (NIST 800-63 current guidance), last-5 history block; lockout 5 failed → 15-min lock; temp password valid 7 days. ⚠ **THE LOCKOUT HALF IS NOW TWO PER-TENANT SETTINGS** — threshold 3–10 (default 5), length 5–60 min (default 15). **The password half is unchanged and stays FIXED.** | **CONFIRMED-AS-AMENDED (PO ruling 2026-09-28, `CR-145-BRC08`)** · was CONFIRMED — PO Q&A R4 (closes OQ-025) |
| BR-IDN-026 | Seed session defaults: idle timeout 60 min, hard limit 12 h; "Keep me signed in" = 30-day trusted-device refresh. ⚠ **ALL FOUR NUMBERS BECOME PER-TENANT SETTINGS AND THE IDLE RANGE NARROWS RATHER THAN WIDENS** — idle ∈ 15/30/45/60 (240 and 480 WITHDRAWN, a tenant on either migrated to 60), hard limit 4–12 h, the OFFER on/off (default on), its window 1–30 d. The customer portal gets **no setting of its own** and reads the tenant's hard limit. | **CONFIRMED-AS-AMENDED (PO ruling 2026-09-28, `CR-145-BRC08`)** · was CONFIRMED — PO Q&A R4 (closes OQ-026) |
| BR-IDN-020 | IP allowlist: comma-separated valid IPv4 CIDR blocks; empty = unrestricted; the saving admin's current IP must fall inside the new list (self-lockout guard); enforced at sign-in and on every authenticated request. | CONFIRMED — PO R1-B14 |
| BR-IDN-016 | Password-policy values govern all password sets: change (EP-IDN-03), temp-password forced change (EP-IDN-01/02) — effective immediately on save for future changes; expiry (when ≠ Never) forces a change at first sign-in past `password_changed_at` + expiry days. | CONFIRMED — PO R1-B13 |
| BR-IDN-006 | The session timeout set here is enforced by sign-in/session logic (EP-IDN-01), within the BR-IDN-026 frame (absolute 12 h). *(The former BR-IDN-004 2FA-enforcement cross-reference is removed — 2FA entirely v2, BR-IDN-028.)* | CONFIRMED — PO Q&A R4 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Alex sets min length 10 + require symbol on, saves | Toast; `security_policies` row updated; `audit_log` row `settings.security_updated` with before/after jsonb; Priya's next password change must satisfy 10 chars + symbol (`Prairie2026wind` now rejected, `Prairie-2026-wind` accepted) |
| TC-2 | A newly provisioned tenant's Security tab is opened before any edits | Confirmed seed defaults render (BR-IDN-025/026): min 8 · upper/lower/number ✓ · symbol ✗ · expire Never · timeout 1 hour · allowlist empty; **no 2FA-requirement section exists anywhere on the tab** (BR-IDN-028). ⚠ **AMENDED `CR-145-BRC08` 2026-09-28 — FIVE MORE CONTROLS MUST NOW RENDER BESIDE THE TIMEOUT — SIX SETTINGS IN ALL — EACH AT TODAY'S VALUE.** Wrong passwords before lockout **5** · lockout length **15 minutes** · hard limit after sign-in **12 hours** · offer *"Keep me signed in"* **on** · its length **30 days**, beside the **1 hour** timeout. **The defaults are today's fixed values, so nothing a person reads on this tab changes** — what changes is that five of the six are now editable where before they were not on the tab at all. ⚠ **THE STRICTER NEW-TENANT DEFAULTS WERE OFFERED AND DECLINED** (7-day renewal, 30-minute idle) — a tab asserting those is asserting a proposal, not the ruling. |
| TC-3 | Alex sets session timeout 1 hour | Subsequent activity uses the 60-minute idle window (US-IDN-003 behavior); existing sessions adopt it on their next request. ⚠ **AMENDED `CR-145-BRC08` 2026-09-28 — THE CHOICES ARE NOW 15 / 30 / 45 / 60 AND 1 HOUR IS STILL ONE OF THEM**, so this case is unchanged. **FIVE CASES BESIDE IT, ONE PER NEW SETTING**, each proving the saved value governs the very next evaluation: **15 minutes** signs an idle user out at 15 (`T11`, `test_t11_cr145_inactivity_fifteen_minutes.py`); a **4-hour** hard limit caps an active session at 4; **3** wrong passwords lock on the third; a **5-minute** lock lifts after 5 (the floor — the ceiling of **60** is proved only as an accepted save, not as a held lock); switching the offer **off** makes the public `GET auth/sign-in-options` answer `false` and refuses a sign-in that still asks for it. ⚠ **AND THE REFUSAL CASE:** a value outside its range — `session_timeout_minutes = 240`, `lockout_max_failed = 2`, a **31**-day window, and every other edge ±1 — is refused server-side with **422** naming the field and its allowed range, not merely absent from the select, because a select is not a validation; both ends of every range are **accepted**. ⚠ **Written 2026-09-28 and green**, in `06-backend/tests/test_cr145_session_settings.py` (`T1`, `T2`, `T3`); the tick box's absence on screen is `07-frontend/src/features/identity/signInKeepSignedIn.dom.test.tsx`. |
| TC-4 *(negative)* | Allowlist input `203.0.113.0/33, banana` | Inline validation error (invalid CIDR); nothing saved |
| TC-5 *(negative)* | Alex (current IP 203.0.113.7) saves allowlist `198.51.100.0/24` only | Blocked with self-lockout error "your current IP 203.0.113.7 is not in the allowed ranges"; nothing saved |
| TC-6 *(negative)* | Allowlist `203.0.113.0/24` active; Priya signs in from 192.0.2.44 | 403 at sign-in with generic denial; attempt logged; from 203.0.113.50 sign-in proceeds |
| TC-7 *(negative)* | Diana (Executive) opens the tab; then calls the save endpoint directly | Controls rendered read-only/disabled-with-reason (IS-6; A4 Settings=View); server returns 403 on save |
| TC-8 *(negative)* | Priya (Billing Clerk) requests the tab | Permission-denied state (IS-7); 403 — A4 Settings row: Billing Clerk "—" |
| TC-9 *(isolation)* | Silver Creek sets min length 12; Jordan checks Blue Mesa's Security tab and adds a user | Blue Mesa policy unchanged (its own `security_policies` row under RLS); a Blue Mesa forced change still validates against Blue Mesa's own policy |
| TC-10 | Alex clicks "View audit log →" | Navigates to the tenant-scoped audit-log viewer **S61** (OQ-029 CLOSED — design confirmed, tenant-scoped rows only); viewer behavior itself is audit-module scope |

**4 · Test Data** — Silver Creek starting policy = the confirmed seed defaults (BR-IDN-025/026): min 8 · upper/lower/number on · symbol off · expire Never · timeout 60 min · allowlist empty; TC-1/TC-9 then configure stricter values. IPs (TEST-NET): admin 203.0.113.7 · staff-inside 203.0.113.50 · outside 192.0.2.44 · second range 198.51.100.0/24. Passwords: `Prairie2026wind` (10, no symbol) vs `Prairie-2026-wind` (symbol).

**5 · Data Fields / Mapping**
All targets below are **PROPOSED-SCHEMA** — B2 has no security-policy table; proposed: `security_policies` (identity module, tenant-scoped, RLS + FORCE, one row per tenant, `UNIQUE(tenant_id)`).
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Minimum length | S8 Security | prototype-extracted (8/10/12) | **PROPOSED-SCHEMA** `security_policies.pw_min_length` | integer | user-input | ∈ {8,10,12}; default 8 (BR-IDN-025) |
| Require upper, lower & number | S8 Security | prototype-extracted | **PROPOSED-SCHEMA** `security_policies.pw_require_mixed` | boolean | user-input | default on (BR-IDN-025) |
| Require a symbol | S8 Security | prototype-extracted | **PROPOSED-SCHEMA** `security_policies.pw_require_symbol` | boolean | user-input | default off (BR-IDN-025) |
| Expire passwords | S8 Security | prototype-extracted (Never/90/180) | **PROPOSED-SCHEMA** `security_policies.pw_expiry_days` (null = Never) | integer days | user-input | ∈ {null,90,180}; default Never (BR-IDN-025) |
| Session timeout | S8 Security | prototype-extracted (30 m/1 h/4 h/8 h) | **PROPOSED-SCHEMA** `security_policies.session_timeout_minutes` | integer minutes | user-input | ⚠ **AMENDED `CR-145-BRC08` 2026-09-28: ∈ {15,30,45,60}**; default 60 (BR-IDN-026). **240 and 480 are refused server-side**, not merely dropped from the select. |
| Hard limit after sign-in | S8 Security | `CR-145-BRC08` (PO ruling 2026-09-28) | **PROPOSED-SCHEMA** `security_policies` — new column | integer hours | user-input | 4–12; default 12. Read by the staff session AND by the customer portal, which has no setting of its own. |
| Offer "Keep me signed in" | S8 Security | `CR-145-BRC08` (PO ruling 2026-09-28) | **PROPOSED-SCHEMA** `security_policies` — new column | boolean | user-input | default **on**. Off = the tick box is not rendered on the sign-in screen at all. |
| "Keep me signed in" length | S8 Security | `CR-145-BRC08` (PO ruling 2026-09-28) | **PROPOSED-SCHEMA** `security_policies` — new column | integer days | user-input | 1–30; default 30. The sign-in cookie's `max_age` FOLLOWS this value; it is not a seventh setting. |
| Wrong passwords before lockout | S8 Security | `CR-145-BRC08` (PO ruling 2026-09-28) | **PROPOSED-SCHEMA** `security_policies` — new column | integer | user-input | 3–10; default 5 (BR-IDN-025 as amended) |
| Lockout length | S8 Security | `CR-145-BRC08` (PO ruling 2026-09-28) | **PROPOSED-SCHEMA** `security_policies` — new column | integer minutes | user-input | 5–60; default 15 (BR-IDN-025 as amended) |
| Allowed IP ranges | S8 Security | prototype-extracted (placeholder CIDR) | **PROPOSED-SCHEMA** `security_policies.ip_allowlist` cidr[] (empty = unrestricted) | cidr[] | user-input | valid IPv4 CIDRs; self-lockout guard |
| View audit log → | S8 Security | prototype-extracted (toast only); target = S61 per OQ-029 closure | reads `audit_log` (audit module) via S61 | — | computed-display | tenant-scoped rows only |
| Save security settings | S8 Security | prototype-extracted | atomic UPDATE + `audit_log` row | — | user-input | System Admin only |

*The prototype's 2FA-requirement checkboxes ("Require 2FA for all staff" / "for Executives only") are removed from the v1 tab — the `two_factor_requirement` column ships with the v2 2FA feature (BR-IDN-028).* ⚠ **THE SECOND SENTENCE OF THIS NOTE WAS AMENDED BY `CR-145-BRC08` ON 2026-09-28 AND IS THE MOST MISLEADING LINE ON THIS PAGE IF READ STALE.** It read: *"Lockout thresholds (5 → 15 min), last-5 history, temp-password validity (7 d) and the absolute session lifetime (12 h) are platform-fixed v1 values per BR-IDN-025/026, not tab controls."* **THREE OF THOSE FOUR ARE NOW TAB CONTROLS** — the lockout threshold, the lockout length and the hard limit after sign-in. **The last-5 history block and the 7-day temporary password are the two that really do stay platform-fixed**, and they are the reason this note is amended rather than deleted: a lane that deletes it loses the only statement that those two are NOT settings, which is exactly the guarantee nobody would then be checking.*

**6 · Acceptance**
- Given a System Admin, When they save any policy change, Then one atomic update lands with a before/after audit row, a toast confirms, and the new values govern the very next password set, sign-in, and session-idle evaluation.
- Given a newly provisioned tenant, When the tab first renders, Then the BR-IDN-025/026 seed defaults are shown and no 2FA-requirement section exists (BR-IDN-028).
- Given an allowlist that would exclude the saving admin's current IP, When saved, Then the save is refused with the self-lockout reason.
- Given any other tenant, When this tenant's policy changes, Then the other tenant's enforcement is untouched.

**7 · Finance Calculation** — N/A

**8 · Open Questions**
| OQ | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| OQ-025 | Password-policy defaults for newly provisioned tenants + lockout thresholds + token lifetimes | — (resolved; story unblocked) | Product Owner (chat session) | **CLOSED(→BR-IDN-025)** — proposed defaults confirmed (PO Q&A R4) |
| OQ-026 | Session-timeout default for new tenants + "Keep me signed in" semantics | — (resolved; story unblocked) | Product Owner (chat session) | **CLOSED(→BR-IDN-026)** — idle 60 m / absolute 12 h / keep-signed-in 30 d (PO Q&A R4) |
| OQ-029 | "View audit log →" target screen | — (resolved; TC-10 routed to S61) | Product Owner (chat session) | **CLOSED(→A1 S61)** — design confirmed + tenant-scoped-only constraint (PO Q&A R4) |
