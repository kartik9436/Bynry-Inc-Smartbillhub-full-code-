# ── Trace ──────────────────────────────────────────────
# Story:    US-IDN-001/003 (/auth/session) · US-IDN-004..007 (/users*, /roles) ·
#           US-IDN-008 (/me, /me/password, /me/permissions) ·
#           US-IDN-010 (/settings/security-policy)
# Rules:    the ratified A11 paths (11b §2.2/§2.3, Addendum r2) — verbatim, no
#           extra routes, no mutating route on /roles (BR-IDN-014); the single
#           non-A11 route (/me/permissions) is the PO's 2026-08-09 directive
# Tests:    06-backend/tests/test_us_idn_00*.py (resolve through these routes)
# Impacts:  config/urls.py (includes this module)
# ───────────────────────────────────────────────────────
"""identity URL registration — exactly the ratified paths, nothing more.

All of them are TENANT-SCOPED, so config/urls.py mounts this list under
`/api/{tenant}/` (PO ruling 2026-08-10): sign-in is per-tenant at
`POST /api/{tenant}/auth/session` and sign-out at the same path with DELETE.
BR-IDN-001 is unchanged in substance — the tenant is still resolved FIRST and
the credentials are still checked as (tenant, email); only the SOURCE of the
tenant moved from the Host's first label to the path's first segment.
"""

from django.urls import path

from apps.identity import api

urlpatterns = [
    path("auth/session", api.SessionView.as_view()),
    # `CR-145-BRC08` — public, throttled, one boolean. The sign-in FORM has to
    # know whether to draw the *"Keep me signed in"* box, and it is drawn
    # before anybody has a session. See the view's docstring for why it
    # returns one field and not the policy.
    path("auth/sign-in-options", api.SignInOptionsView.as_view()),
    # `CR-187-BRC10` — the native field app (N24). Four PUBLIC, throttled
    # doors (a caller who could already authenticate would not be signing in
    # or claiming an account) and one System-Admin route. Additive: the
    # cookie's `auth/session` above is unchanged.
    path("auth/token", api.NativeTokenView.as_view()),
    path("auth/token/refresh", api.NativeTokenRefreshView.as_view()),
    path("auth/activation/check", api.ActivationCheckView.as_view()),
    path("auth/activation/complete", api.ActivationCompleteView.as_view()),
    path("users/<uuid:user_id>/activation-code", api.UserActivationCodeView.as_view()),
    path("users", api.UsersView.as_view()),
    path("users/<uuid:user_id>", api.UserDetailView.as_view()),
    path("users/<uuid:user_id>/deactivate", api.UserDeactivateView.as_view()),
    path("users/<uuid:user_id>/reactivate", api.UserReactivateView.as_view()),
    path("users/<uuid:user_id>/temp-password", api.UserTempPasswordView.as_view()),
    # `CR-188-BRC10` — Resend invitation (PO answer 5) and the two PUBLIC,
    # throttled doors of the emailed one-time sign-in link.
    path("users/<uuid:user_id>/resend-invitation", api.UserResendInvitationView.as_view()),
    path("auth/password-link/check", api.PasswordLinkCheckView.as_view()),
    path("auth/password-link/complete", api.PasswordLinkCompleteView.as_view()),
    path("roles", api.RolesView.as_view()),
    path("settings/security-policy", api.SecurityPolicyView.as_view()),
    # The Audit log card of the 2026-09-29 Security redesign — the last five
    # changes made ON THIS TAB, same role gate as the read above. It has no
    # A11/11b row yet and is REPORTED for the addendum, exactly as
    # /me/permissions below is.
    path("settings/security-policy/audit", api.SecurityPolicyAuditView.as_view()),
    # OQ-FLD-12797 (PO 2026-10-24) — the field app's certificate pins, the
    # "Field app certificates" card on the same tab. No A11/11b row yet; reported.
    path("settings/security-policy/field-app-pins", api.FieldAppPinsView.as_view()),
    path("me", api.MeView.as_view()),
    path("me/password", api.MePasswordView.as_view()),
    # PO directive 2026-08-09 — the one route here with no A11/11b row yet
    # (reported for the addendum): any signed-in member reads THEIR OWN A4 row.
    path("me/permissions", api.MePermissionsView.as_view()),
]

# ── Lifecycle ─────────────────────────────────────────────
# packet: US-IDN-001@402b6db (route table for the EP-IDN-01..04 lanes — hash = sha256/7 of the lead source epic)
# generated: 2026-08-09 by story-coder v1 (identity W0 feature-story lane, backend only) · AMENDED 2026-08-09 by story-coder (API-gap lane: /me/permissions) · AMENDED 2026-08-10 by story-coder (path-tenancy lane — PO ruling 2026-08-10)
# checklist: A✔ B=deferred(routing only — TCs live with the views/services) C✔ D✔ E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: py_compile✔ · pytest tests -m "not golden and not isolation" 323-green-0-fail at handoff (shared tree, concurrent tenancy lane active) · run_gates 11-PASS/0-FAIL✔ · trace_lint✔ · mypy NOT run — flagged, deferred with the CI lane · [API-gap lane 2026-08-09] suite 682 passed / 7 skipped / 47 deselected · run_gates 11-PASS/0-FAIL/1-SKIP✔ (this lane adds no migration and no 🔒 guarded file; a transient G7 FAIL seen mid-lane was a CONCURRENT lane's un-ledgered migration and cleared when they landed its row) · trace_lint✔ · [path-tenancy lane 2026-08-10] ruff✔ black✔ · suite `pytest tests -m "not golden and not isolation"` 818 passed / 9 skipped (788 baseline) · `-m isolation` 32 passed / 12 skipped (29 baseline) · run_gates 11-PASS/0-FAIL/1-SKIP✔ · trace_lint✔ · no migration in this lane
# exceptions: /me/permissions has no A11/11b row — PO directive 2026-08-09, REPORTED for the addendum · [path-tenancy lane 2026-08-10] the whole list is mounted under /api/{tenant}/ by config/urls.py; no route text changed
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
