# ── Trace ──────────────────────────────────────────────
# Change:   CR-187-BRC10 — `Authorization: Bearer <access token>` for the
#           native field app, beside the cookie (`bearer-on-work-mobile` in
#           field-app/src/security/authApi.ts `SERVER_GAPS`)
# Rules:    BR-IDN-006 (one tenant per credential; a foreign path ⇒ 404, never
#           403 and never a silent switch) · BR-IDN-012 (deactivated = dead) ·
#           BR-IDN-020 (allowed addresses on every request) · BR-IDN-022
#           (forced change) · hard rule 1 (the row is read under RLS FORCE)
# Tests:    06-backend/tests/test_cr187_native_auth.py · _pg.py
# Impacts:  every route `accept_native_bearer` is applied to — today every
#           `/api/{tenant}/work/mobile/*` route (apps/work/api.py)
# ───────────────────────────────────────────────────────
"""The native app's bearer authentication — and the ONE place it is switched on.

HUMAN-REVIEW-PENDING — 🔒 identity/auth, AI-authored 2026-10-21; ledger row
owed by the coordinator.

WHAT IT CHECKS, IN ORDER (mirroring `IdentitySessionAuthentication`)
--------------------------------------------------------------------
1. `Authorization: Bearer sbh_fa_…` — anything else is *"not mine"* (`None`),
   so the cookie class behind it runs and a browser is byte-for-byte unaffected.
2. **The tenant the token names against the tenant the PATH names.** Different,
   or a path naming no tenant at all → **404** through `deny_as_not_found`,
   exactly the cookie's answer (`BR-IDN-006`). This runs BEFORE any row is read,
   which is what lets the row live under RLS FORCE (`identity/0011`) rather than
   in an exempt table like `sessions`.
3. The row, by SHA-256, under the path tenant's context: unknown → 401;
   revoked → 401 (`params.reason = device_signed_out` when the office signed the
   handset out, else `token_revoked`); expired → 401 `access_token_expired`.
4. Membership still active-or-invited (BR-IDN-012), the request address inside
   the utility's allowed list (BR-IDN-020, 403), no forced change owed (403).
5. Attaches `request.tenant_role` and `user.role` — what `FieldAppRole` and the
   services read — and returns `(user, token_row)`, so a view can read the
   handset (`request.auth.device_uid`) FROM THE CREDENTIAL, never from a body
   (`R127`).

It writes nothing per request: no idle clock (an access token's hour is a hard
limit, not a sliding one).

WHERE IT IS ON — `accept_native_bearer`
---------------------------------------
Not the DRF default, deliberately: the bearer authorises talking to the FIELD
routes and nothing else (Security §1). `accept_native_bearer(urlpatterns,
prefix)` puts it in front of the cookie on every route under a prefix, in ONE
line at the bottom of the module that owns those routes — so a route another
lane adds tomorrow under `work/mobile/` is covered without anybody remembering
to decorate it. `tests/test_cr187_native_auth.py` asserts the exact set.
"""

from __future__ import annotations

from typing import Any

from drf_spectacular.extensions import OpenApiAuthenticationExtension
from rest_framework import exceptions as drf_exceptions
from rest_framework.authentication import BaseAuthentication

from apps.identity import native, selectors, services
from apps.identity.auth import IdentitySessionAuthentication, client_ip
from apps.identity.models import NativeToken, TenantMembership
from core import errors

SCHEME = "Bearer"


def bearer_of(request: Any) -> str | None:
    header = request.META.get("HTTP_AUTHORIZATION", "") or ""
    parts = header.split(maxsplit=1)
    if len(parts) != 2 or parts[0] != SCHEME:
        return None
    return parts[1].strip()


class NativeBearerAuthentication(BaseAuthentication):
    """`Authorization: Bearer <access token>` → `(user, NativeToken)`."""

    def authenticate(self, request: Any):
        plaintext = bearer_of(request)
        if not plaintext or native.parse_tenant(plaintext, native.ACCESS_PREFIX) is None:
            return None  # not ours — the cookie class decides

        # ── BR-IDN-006: the token's tenant against the path's, before any read.
        tenant_id = getattr(request, "tenant_id", None)
        named = native.parse_tenant(plaintext, native.ACCESS_PREFIX)
        if getattr(request, "tenant_slug", None) is None:
            # A platform path has no tenant to match and no field route lives
            # on one. Refused as unauthenticated rather than adopted.
            raise drf_exceptions.AuthenticationFailed()
        if tenant_id is None or str(named) != str(tenant_id):
            raise errors.deny_as_not_found(br_ref="BR-IDN-006")

        token = (
            NativeToken.objects.filter(
                token_hash=native.hash_token(plaintext), kind=NativeToken.KIND_ACCESS
            )
            .select_related("user")
            .first()
        )
        if token is None:
            raise native.refusal("token_unknown")
        if token.revoked_at is not None:
            raise native.refusal(
                native.REASON_DEVICE_SIGNED_OUT
                if token.revoked_reason == native.REASON_DEVICE_SIGNED_OUT
                else "token_revoked"
            )
        if services._now() >= token.expires_at:
            raise native.refusal("access_token_expired")

        user = token.user
        membership = selectors.membership_for_user(token.tenant_id, user.id)
        if membership is None or membership.status == TenantMembership.STATUS_DEACTIVATED:
            raise native.refusal("token_revoked")  # BR-IDN-012

        policy_values = selectors.security_policy_values(token.tenant_id)
        if not services._check_ip_allowed(policy_values, client_ip(request)):
            raise errors.AuthError(errors.AUTH_PERMISSION_DENIED, br_ref="BR-IDN-020")
        if user.must_change_password:
            raise errors.AuthError(
                errors.AUTH_PERMISSION_DENIED,
                message_key="errors.auth.password_change_required",
                params={"reason": "password_change_required"},
                br_ref="BR-IDN-022",
            )

        user.role = membership.role.code
        request.tenant_role = membership.role.code
        return (user, token)

    def authenticate_header(self, request: Any) -> str:
        return 'Bearer realm="smartbillhub"'


def accept_native_bearer(urlpatterns: list, prefix: str) -> list:
    """Put the bearer in FRONT of the cookie on every route under `prefix`.

    Only on a route whose authenticators are exactly the platform default
    (`[IdentitySessionAuthentication]`); anything else is left as it is and
    the sweep test names it, because a route that chose its own authenticators
    chose them for a reason this helper cannot see.

    Mutates each view's DRF class attribute, which is what DRF reads per
    request (`APIView.get_authenticators`) and what the default-authentication
    registry sweep reads too. Returns the list unchanged, for one-line use.
    """
    for pattern in urlpatterns:
        route = str(getattr(pattern, "pattern", ""))
        view_class = getattr(getattr(pattern, "callback", None), "cls", None)
        if view_class is None or not route.startswith(prefix):
            continue
        if list(view_class.authentication_classes) == [IdentitySessionAuthentication]:
            view_class.authentication_classes = [
                NativeBearerAuthentication,
                IdentitySessionAuthentication,
            ]
    return urlpatterns


class NativeBearerScheme(OpenApiAuthenticationExtension):
    """Publish the bearer in the OpenAPI contract, as the cookie is published."""

    target_class = NativeBearerAuthentication
    name = "nativeBearer"

    def get_security_definition(self, auto_schema) -> dict:
        return {
            "type": "http",
            "scheme": "bearer",
            "description": (
                "The native field app's one-hour access token (POST /api/{tenant}/auth/token), "
                "bound to ONE tenant and one handset: presented on another tenant's path it is "
                "refused 404. Accepted on /api/{tenant}/work/mobile/* only."
            ),
        }
