# identity — Flows & States

> Fleshed out 2026-08-09 from BR-IDN-001..029 + EP-IDN-01..04. Screens: S3 Sign-in (card on S2) · S48 User menu · S8 Settings → Users & roles / Security. Governing model: **identity is PER-TENANT (BR-IDN-029)** — the same email in two tenants is two separate users; uniqueness = (tenant, email); membership 1:1 simplification = Eng-Lead disposition (B2 r11). **v1 sends NO staff auth emails (BR-IDN-021)**; 2FA is entirely v2 (BR-IDN-028).

## 1. Sign-in flow (US-IDN-001, BR-IDN-001/002/029)

```
request at ‹tenant›.smartbillhub.app → tenant resolved from SUBDOMAIN FIRST, never client input (BR-IDN-001/029, B3)
  → (tenant, email) credential check + ACTIVE membership required (BR-IDN-001)
  → lock check (§2) → pass: server-side session created, app.tenant_id set server-side → Dashboard S7 + audit auth.sign_in
  → any failure (bad password / unknown email / inactive membership / locked / voided-expired temp password):
      ONE generic message, identical timing — no enumeration, no factor disclosure (BR-IDN-002)
2FA challenge / forced enrollment: v2 only (BR-IDN-028 — no 2FA setting, enrollment, or menu item in v1)
```

## 2. Lockout state machine (BR-IDN-003/025)

`UNLOCKED ──(5 consecutive failed attempts)──→ LOCKED 15 min (correct password refused with the generic error; audit auth.sign_in_failed ×5 + auth.lockout) ──(15 min lapse)──→ UNLOCKED`. Thresholds live in the security policy seed (BR-IDN-025), never hardcoded.

## 3. Session lifecycle (US-IDN-003, BR-IDN-006/007/026)

```
CREATED (sign-in — server-side record bound to ONE (user, tenant))
  → ACTIVE (last_seen_at slides on activity)
  → EXPIRED  idle > tenant policy timeout (default 60 min, config 30 min–8 h — BR-IDN-026)
  | EXPIRED  absolute 12 h — caps even continuously active sessions (BR-IDN-026)
  | REVOKED  sign-out (BR-IDN-007, → public S1/S2)
  | REVOKED  membership deactivated (BR-IDN-012) · "sign out other sessions" on password change (BR-IDN-016)
             · forced-change completion revokes ALL prior sessions (BR-IDN-005)
"Keep me signed in" = 30-day trusted-device refresh, OFF by default (BR-IDN-026)
cross-tenant presentation of a session token → 401/403 (one tenant per session)
policy timeout changes apply to existing sessions at their NEXT request (EP-IDN-04 TC-3)
```

## 4. Temporary-password flow — reset AND invite (US-IDN-002/005, BR-IDN-021/022/023/025/005)

```
"Forgot password?" (S3) → its own page /{tenant}/forgot-password: ask your System Admin, NO contact shown — no form, no token, no email (BR-IDN-023 as amended 2026-10-05, CR-170-BRC10; was a static "Contact your administrator" notice)
System Admin issues temp password from the user's S8 row (or at user creation)
  → shown ONCE on screen, never retrievable (BR-IDN-022) → valid 7 days (BR-IDN-025) → audit auth.temp_password_issued
  → user signs in with it → FORCED-CHANGE screen gates every app screen (BR-IDN-022)
  → policy-compliant change (BR-IDN-016) → ALL prior sessions revoked + audit auth.password_reset (BR-IDN-005)
  → this session ENDED too (DELETE /auth/session) → S3 shows "Password changed. Sign in again." once → sign in with the new password → Dashboard (BR-IDN-022 as amended 2026-10-05, CR-170-BRC10)
Reset temp password action voids the prior temp password immediately (BR-IDN-011)
expired (> 7 d) or voided temp password → generic sign-in error (BR-IDN-002)
```

## 5. Membership state machine (US-IDN-005/006/007, BR-IDN-011/012/013/022)

```
INVITED (created with temp password not yet changed; Name renders "—")
  ──(first sign-in + forced change complete)──→ ACTIVE (BR-IDN-011/022)
ACTIVE ──(Deactivate, confirm modal)──→ DEACTIVATED  sign-in blocked + that tenant's sessions revoked at once; row + history kept (BR-IDN-012)
DEACTIVATED ──(Reactivate)──→ ACTIVE (existing password works again)
REMOVE = membership row delete only — 🔒 audit-locked (blocked) while referenced by tenant records (BR-IDN-012)
GUARD on every transition: a tenant always retains ≥1 active System Admin — the last one cannot be
  demoted, deactivated, or removed (BR-IDN-013)
all transitions: System Admin only, server-enforced (BR-IDN-009); audited with before/after
```

## 6. Role change (US-IDN-006, BR-IDN-008/009)

`pick among exactly the 3 predefined platform roles (System Admin / Billing Clerk / Executive — not tenant-editable, BR-IDN-008) → membership role_id updated → new permissions apply on the user's very NEXT request (no re-login) → audit user.role_changed before/after`. Last-admin guard per §5 (BR-IDN-013).

## 7. Security-policy save flow (US-IDN-010, BR-IDN-019/020/025/026)

```
one tenant-wide record; System Admin edits, Executive views (BR-IDN-019)
seed defaults: password min 8 · upper+lower+number · symbol optional · NO forced expiry · last-5 history block
  · lockout 5→15 min · temp password 7 d (BR-IDN-025) · idle 60 min / absolute 12 h / keep-signed-in 30 d (BR-IDN-026)
IP allowlist: valid IPv4 CIDRs; empty = unrestricted; SELF-LOCKOUT GUARD — the saving admin's current IP must be
  inside the ranges or save is blocked; enforced at sign-in AND per request (BR-IDN-020)
save: atomic + before/after audit (BR-IDN-019); 2FA-requirement section does not exist in v1 (BR-IDN-028)
```

## 8. Self-service (US-IDN-008, BR-IDN-015/016/017/027)

`user menu (S48) → Change password: requires CURRENT password + tenant policy; "sign out other sessions" default ON revokes all but current (BR-IDN-016)` · `My profile: name/phone editable; role read-only; email changed only by a System Admin in v1, no verification mail (sending + verification enforcement = v2), every email change audited (BR-IDN-017/027)` · 2FA menu item/modal: (no v1 flow — entirely v2, BR-IDN-028).

Journeys: none owned — identity is the substrate for every J-flow's session context.
