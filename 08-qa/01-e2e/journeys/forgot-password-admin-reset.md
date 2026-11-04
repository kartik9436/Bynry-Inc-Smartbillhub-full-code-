# Forgot password — ask the System Admin, admin resets, forced new password, back to sign-in

---
id: forgot-password-admin-reset
roles: [System Admin, any staff user]
gates: [BR-IDN-021, BR-IDN-022, BR-IDN-023, BR-IDN-025, BR-IDN-005]
stories: [US-IDN-002]
change: CR-170-BRC10
walk: 10-scripts/cr170_forgot_password_walk.mjs
screenshots: 08-qa/password-2026-10-05/
---

**Intent.** The PO's flow of 2026-10-05, verbatim: *"On the login screen we have forgot password option ; if user press forget password then we need redirect user to contact system admin of that utility; System Admin will reset the password from setting >user roles ; After reseting the passsword user try to login sytem will redirect to the user to set the password ; once user set the password user redirect to login page"*. No email is sent at any step (`BR-IDN-021`). The forgot page shows **no contact at all** (PO: *"dont show any contact"*).

**Fixture.** Tenant `brazosbend` · Dana = System Admin (`dana@brazosbendutilities.com`) · one ACTIVE staff user who has forgotten their password.

| # | Actor + action | Expected outcome | Assertions | Gate |
|---|---|---|---|---|
| 1 | Dana opens Settings › Users & roles and picks *Reset temp password* on the user's row, then confirms | A temporary password is shown once, valid 7 days; the old password stops working immediately | Panel shows the password and *"Shown once…"*; audit `auth.temp_password_issued` | BR-IDN-023 · BR-IDN-025 |
| 2 | The user, signed out, taps *Forgot password?* on `/{tenant}/signin` | Opens `/{tenant}/forgot-password`: **Forgot your password?** · **Ask your System Admin. They give you a temporary password. Sign in with it.** · **Back to sign in** | No name, phone, email or utility name on the card; no request to the server; *Back to sign in* returns to `/{tenant}/signin` | BR-IDN-023 (amended 2026-10-05) |
| 3 | The user signs in with the temporary password | Lands on `/{tenant}/change-password`, outside the app shell | Every other read refused until the change | BR-IDN-022 |
| 4 | The user types a new password twice and saves | The change is saved; the screen ends the session through the existing sign-out (`DELETE /auth/session`) | `POST /me/password` 204 then `DELETE /auth/session` 204; `GET /me` 401 afterwards | BR-IDN-022 (amended 2026-10-05) · BR-IDN-005 |
| 5 | — | Lands on `/{tenant}/signin` showing **Password changed. Sign in again.** | The `?changed=1` flag is stripped from the address; a plain visit to sign-in shows no note; the temporary password is now refused with the one generic line | BR-IDN-022 · BR-IDN-002 |
| 6 | The user signs in with the new password | Reaches the dashboard; no change owed | `must_change_password` false | BR-IDN-022 |

**Field technician variant.** A technician's forced change (reached from `/{tenant}/work/mobile/signin`) returns to that same door with the note, and their *Forgot password?* page's *Back to sign in* returns there too (`BR-WRK-043`: the staff door would refuse their login). Proved by `forgotPassword.dom.test.tsx`, not walked.

**Proof.** Front end: `07-frontend/src/features/identity/forgotPassword.dom.test.tsx` (routed under the real `/:tenant` path). Back end: `06-backend/tests/test_cr170_forgot_password_flow.py` on SQLite and PostgreSQL 16. Walk: the script above at 1440, six screenshots in `08-qa/password-2026-10-05/`.
