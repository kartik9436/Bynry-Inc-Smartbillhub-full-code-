# CR-170-BRC10 — Forgot password: its own page, and back to sign-in after a forced change

**Raised:** 2026-10-05 by the Product Owner, in chat.
**Status:** **DONE — BUILT in 2.523.0 (lane PWD, 2026-10-05).** Flow, wording and go all ruled the same day (decision log 2026-10-05, the three rows that start *"FORGOT PASSWORD"*).
**Branch:** `claude/upbeat-dirac-olttw0` (`BRC10`). `allocate.py cr` answered 170 against the remote and `--verify 170` reported it free on every branch at allocation.
**Classification (`13-change-process.md` §1):** a CHANGE. The product did what `BR-IDN-023` said (an inline notice) and the PO now wants a different shape. No money rule, no signed figure, no RLS policy, no data written. The admin reset, the 7-day expiry and the password rules are unchanged.

## 0 · What arrived, in the requester's words (verbatim)

1. The flow: *"On the login screen we have forgot password option ; if user press forget password then we need redirect user to contact system admin of that utility; System Admin will reset the password from setting >user roles ; After reseting the passsword user try to login sytem will redirect to the user to set the password ; once user set the password user redirect to login page"*
2. The wording: *"Contact line … dont add this - not required; Existing vs new messages rest fo thsi is correct; Question: what contact can this page show? … already answer this - dont show any contact"*
3. The go: *"go - start when load allows"*

## 1 · What signed statements move (step 2)

| Rule | Was | Now |
|---|---|---|
| `BR-IDN-023` (CONFIRMED 2026-08-08) | *"Forgot password?" displays "Contact your administrator"* — built as an inline notice on the sign-in card, key `identity.signIn.forgotNotice`. | *Forgot password?* opens its own public page `/{tenant}/forgot-password`: heading **Forgot your password?**, **Ask your System Admin. They give you a temporary password. Sign in with it.**, and **Back to sign in**. **No contact at all** — no names, no phone, no email. The admin's *Reset temp password* is unchanged. |
| `BR-IDN-022` (CONFIRMED 2026-08-08) | After the forced change the session survived and the user went to the dashboard (`ChangePasswordPage.tsx` docstring point 4). | After the forced change is saved the session is ended through the existing sign-out (`DELETE /auth/session`, `signOut()`), and the user lands on sign-in, which shows **Password changed. Sign in again.** only on that arrival. |

No ❄️ FROZEN figure is touched.

## 2 · Impact (step 3)

| Surface | Effect |
|---|---|
| Screens | New public page; the sign-in card loses its inline notice and its *Forgot password?* becomes a link; sign-in gains a one-time note; the forced-change screen ends the session. |
| Shared UI | The 420px accent-topped card was copied by hand in `SignInPage` and `ChangePasswordPage`. It becomes one component (`components/AuthCard.tsx`, B14 rule 43) used by both and by the new page. |
| Catalogues | Three new keys and one retired key, in all eleven, through `10-scripts/i18n_fanin.py`. |
| Backend | None. The flow already exists; a test proves the temporary password stops working and the new one works after the change and sign-out. |
| Email | None sent (`BR-IDN-021`). |
| Field app | A field technician's forced change carried them to the phone. It now ends at the phone's own sign-in door with the same note — see §4. |

## 3 · Built (step 6)

| Task | Where | Proof |
|---|---|---|
| The forgot-password page, public, at `/{tenant}/forgot-password` (`ONB-06`), on the shared card | `07-frontend/src/features/identity/ForgotPasswordPage.tsx` · `components/AuthCard.tsx` · `App.tsx` · `routing/screenIds.ts` | `forgotPassword.dom.test.tsx` (routed under the real `/:tenant` path) |
| *Forgot password?* is a link; the inline notice is gone | `SignInPage.tsx` | same file |
| After the forced change: existing `signOut()` → `DELETE /auth/session`, cache cleared, `/{tenant}/signin?changed=1` | `ChangePasswordPage.tsx` (`signInAfterPasswordChange`) | same file; the stand-in server records `POST /me/password` then `DELETE /auth/session` |
| *Password changed. Sign in again.* once, the flag stripped | `SignInPage.tsx` (`PASSWORD_CHANGED_PARAM`) | same file |
| Words in eleven catalogues; `identity.signIn.forgotNotice` and `identity.changePassword.done` retired | `10-scripts/i18n_fanin.py` | G15 PASS, 0 missing / 0 extra |
| Temporary password dead, new one works, after change + sign-out | `06-backend/tests/test_cr170_forgot_password_flow.py` | SQLite 2 passed; PostgreSQL 16 (`pgtest`) 10 passed with US-IDN-002 |
| The admin's reset reachable on an ACTIVE user — `DEF-IDN-9706`, found by the walk | `SettingsUsersTab.tsx` (`actionsFor`) | `SettingsUsersTab.test.tsx` red then green |
| Walk at 1440 on PostgreSQL 16, 12 checks ALL PASS | `10-scripts/cr170_forgot_password_walk.mjs` | `08-qa/password-2026-10-05/01…06-*.png`; journey `08-qa/01-e2e/journeys/forgot-password-admin-reset.md` |

**Red first, quoted.** On `88bbc3489` (before the build) the new front-end file failed 8 of 9: *"expected null not to be null"* (no page at the address), *"Unable to find an accessible element with the role "link" and name "Back to sign in""*, *"…name "Forgot password?""* (it was a button), *"Unable to find an element with the text: Password changed. Sign in again."*, *"forgotPasswordPath is not a function"*, *"signInAfterPasswordChange is not a function"*. The no-contact case was also shown red on a planted line (*"expected 'Already a customerForgot your passwor…' not to match /\d{3}[\s.-]?\d{3,4}/"*). The back-end flow already existed, so its test was proved by mutation: with the new password not stored it fails on PostgreSQL with *"assert 201 == 401"* (the temporary password still signed in).

**Pre-existing reds, dated (law 7):** `G13` (unwired props in `RateScheduleWizard.tsx`, `moveReadsCapture.tsx`, +5) and `G33` (10 over-cap refusal strings in other modules) fail identically on `88bbc3489`, before this lane wrote a line.

**Left alone:** `components/SessionExpired.tsx` carries a fourth hand-written copy of the same card; moving it onto `AuthCard` is a separate surface. A System Admin's own row now also offers *Reset temp password* (the action is per status, not per person); the server allows it.

## 4 · Judgments that were ours

- **The page shows no utility name.** The PO ruled *"dont show any contact"* and the wording row lists no utility line. The sign-in card already says which utility you are signing in to; the forgot page needs nothing from the server, so it makes no request a stranger could use as an oracle.
- **The note travels as a one-time query flag `?changed=1`** that the sign-in page reads once and strips from the address with `replace`, so a reload or a bookmark does not show it again.
- **A field technician** (forced change reached from `/{tenant}/work/mobile/signin`) lands back on that same door, not the staff sign-in, because the staff door would refuse their login (`BR-WRK-043`).

## 5 · Version · rollback

**Version 2.523.0** (`allocate.py version --bump change`, verified at push).

**Rollback:** redeploy 2.522.x. No migration and no data change, so nothing to reverse in the database; a user mid-way through a forced change simply lands on the dashboard again as before.
