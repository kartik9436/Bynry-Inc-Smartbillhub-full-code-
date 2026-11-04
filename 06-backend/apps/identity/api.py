# ── Trace ──────────────────────────────────────────────
# Story:    US-IDN-001 (POST /auth/session) · US-IDN-003 (DELETE /auth/session) ·
#           US-IDN-004 (GET /users) · US-IDN-005 (POST /users · POST
#           /users/{id}/temp-password) · US-IDN-006 (PATCH /users/{id} ·
#           /deactivate · /reactivate) · US-IDN-007 (DELETE /users/{id} · GET
#           /roles) · US-IDN-008 (GET/PATCH /me · POST /me/password · GET
#           /me/permissions — the last added by PO directive 2026-08-09, not an
#           A11/11b row) · US-IDN-010 (GET/PUT /settings/security-policy)
#           Screens: S2/S3 · S8 · S48
# Rules:    BR-IDN-001/002 (sign-in, one generic failure) · BR-IDN-008/009 (SysAdmin-
#           only user mgmt, server-enforced) · BR-IDN-014 (read-only matrix, ETag) ·
#           BR-IDN-015/016/017/027 (self-service; role/email privilege guards) ·
#           BR-IDN-019/020 (policy save) · BR-IDN-022 (temp-password shown once) ·
#           BR-SHL-025 (UI gating is convenience — /me/permissions never enforces)
# Tests:    06-backend/tests/test_us_idn_00*.py (Django test client, sqlite;
#           RLS halves = G5 isolation suite)
# Impacts:  config/urls.py (route registration) · FI-01 typed client (paths are the
#           A11-as-amended ratified rows: 11b §2.2/§2.3, Addendum r2)
# ───────────────────────────────────────────────────────
"""identity API endpoints — the ratified A11 paths (11b §2.2/§2.3, PO-ratified
via A11 Addendum r2). Thin by law (B8): serializers are SHAPE-ONLY; every rule
lives in services.py (writes) / selectors.py (reads); every refusal is a
catalog exception from core.errors rendered by the BE-02 handler.

Unauthenticated surface (11b G18): POST /auth/session only. Everything else
authenticates via the identity session cookie (apps.identity.auth) and role-
gates via core.permissions (BE-04). ETag/304 on the reference-data GETs
(/roles, /settings/security-policy — 11b G6).
"""

import hashlib
import json

from django.conf import settings

from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.identity import field_pins, native, password_links, selectors, services
from apps.identity.models import PasswordLink, TenantMembership
from apps.identity.auth import (
    SESSION_COOKIE,
    IdentitySessionAuthentication,
    client_ip,
    session_cookie_max_age,
)
from core import errors, tenancy
from core.pagination import StandardPagination, parse_list_params
from apps.tenancy.api import PublicOnboardingThrottle
from core.permissions import (
    FIELD_TECHNICIAN,
    AdminOrExecutive,
    AnyTenantRole,
    FieldAppRole,
    SystemAdminOnly,
)
from apps.identity.native_auth import NativeBearerAuthentication


# ── Serializers (shape only — no business rules here, B8) ───────────────────
class SignInSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(trim_whitespace=False)
    keep_signed_in = serializers.BooleanField(default=False)  # off by default (BR-IDN-026)
    # DEF-WRK-9583 — the app the request comes from (`BR-WRK-043`). The field
    # app declares `mobile`; an absent value is the web, which is every caller
    # that existed before the phone. ⚠ **IT NEVER WIDENS ANYTHING**: it names
    # the door being knocked on, and the login's own `surface_scope` decides
    # whether that door opens (`services._surface_allowed`). A ChoiceField and
    # not a CharField, so an unknown value is a 400 rather than silently the
    # web — and `both` is a SCOPE, never a surface, so it cannot be declared.
    surface = serializers.ChoiceField(
        choices=[services.SURFACE_WEB, services.SURFACE_MOBILE],
        default=services.SURFACE_WEB,
    )


class AddUserSerializer(serializers.Serializer):
    full_name = serializers.CharField()
    email = serializers.EmailField()
    role = serializers.CharField()
    #: CR-187-BRC10 — optional; a field-app sign-in name, unique per utility.
    phone = serializers.CharField(required=False, allow_blank=True, max_length=40)


class EditUserSerializer(serializers.Serializer):
    full_name = serializers.CharField(required=False)
    email = serializers.EmailField(required=False)
    role = serializers.CharField(required=False)
    #: CR-187-BRC10 — `""` clears it; unique per utility (`phone_in_use`).
    phone = serializers.CharField(required=False, allow_blank=True, max_length=40)


class ProfileSerializer(serializers.Serializer):
    full_name = serializers.CharField(required=False)
    phone = serializers.CharField(required=False, allow_blank=True)


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(required=False, trim_whitespace=False)
    new_password = serializers.CharField(trim_whitespace=False)
    confirm_password = serializers.CharField(trim_whitespace=False)
    sign_out_other_sessions = serializers.BooleanField(default=True)  # default on (BR-IDN-016)


class SecurityPolicySerializer(serializers.Serializer):
    pw_min_length = serializers.IntegerField(required=False)
    pw_require_mixed = serializers.BooleanField(required=False)
    pw_require_symbol = serializers.BooleanField(required=False)
    pw_expiry_days = serializers.IntegerField(required=False, allow_null=True)
    session_timeout_minutes = serializers.IntegerField(required=False)
    # `CR-145-BRC08` — the five new settings. ⚠ **A FIELD MISSING HERE IS NOT
    # REFUSED, IT IS DROPPED IN SILENCE:** DRF's `validated_data` carries only
    # declared fields, so until these five lines existed a PUT of
    # `{"lockout_max_failed": 2}` answered 200, saved nothing, and never reached
    # `_validate_policy_values` — every T2 refusal and every T1 save through the
    # API was a no-op wearing a 200. Ranges are NOT restated here: the one
    # source is `services.SETTING_LIMITS`, and this layer only checks the TYPE
    # (so `True` for a number is refused before Python's `bool ⊂ int` can store
    # it as 1).
    absolute_session_hours = serializers.IntegerField(required=False)
    keep_signed_in_offered = serializers.BooleanField(required=False)
    keep_signed_in_days = serializers.IntegerField(required=False)
    lockout_max_failed = serializers.IntegerField(required=False)
    lockout_minutes = serializers.IntegerField(required=False)
    ip_allowlist = serializers.ListField(child=serializers.CharField(), required=False)
    # PO 2026-10-21 item 2 — the field app's capture life, hours. Declared, or
    # DRF drops it in silence (the comment above is why).
    field_capture_hours = serializers.IntegerField(required=False)
    # CR-188-BRC10 — declared, or DRF drops it in silence.
    password_link_valid_days = serializers.IntegerField(required=False)


# ── Shared payload builders ─────────────────────────────────────────────────
def _membership_row(membership) -> dict:
    """One US-IDN-004 §5 list row (Name renders '—' client-side while invited)."""
    user = membership.user
    return {
        "id": str(user.id),
        "name": user.full_name,
        "email": user.email,
        # CR-187-BRC10 — the office edits it on the user (a field-app sign-in
        # name); as typed, for display.
        "phone": user.phone or None,
        "role": membership.role.code,
        "role_name": membership.role.name,
        "last_active_at": (
            membership.last_active_at.isoformat() if membership.last_active_at else None
        ),
        "status": membership.status,
    }


def _me_payload(user, membership) -> dict:
    return {
        "id": str(user.id),
        "full_name": user.full_name,
        "email": user.email,
        "phone": user.phone,
        "role": membership.role.code if membership else None,  # current tenant only (TC-8)
        "role_name": membership.role.name if membership else None,
        "must_change_password": user.must_change_password,
    }


def _etag_of(payload) -> str:
    digest = hashlib.md5(
        json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()
    return f'"{digest}"'


def _maybe_304(request, payload):
    """11b G6 ETag/304 for reference-data GETs."""
    etag = _etag_of(payload)
    if request.headers.get("If-None-Match") == etag:
        response = Response(status=304)
    else:
        response = Response(payload)
    response["ETag"] = etag
    return response


def _resolve_target(request, user_id):
    """Current-tenant (user, membership) or 404 — an id from another tenant is
    ABSENT under this tenant's scope, so the body equals plain not-found
    (HR-1/G4; RLS enforces the same on live Postgres)."""
    tenant_id = tenancy.require_tenant(request)
    user = selectors.user_in_tenant(tenant_id, user_id)
    membership = selectors.membership_for_user(tenant_id, user.id) if user else None
    if user is None or membership is None:
        raise errors.NotFoundError()
    return tenant_id, user, membership


# ── Auth: POST /api/{tenant}/auth/session · DELETE (same path) ─────────────
class SessionView(APIView):
    """Sign-in is UNAUTHENTICATED but never tenant-less (BR-IDN-001).

    Since the PO's 2026-08-10 ruling the tenant comes from the path, so the
    route is `/api/{tenant}/auth/session`: require_tenant() resolves it FIRST
    and answers a plain 404 when the slug names no tenant — the same body a
    foreign-session request gets, so neither reveals which tenants exist.
    """

    authentication_classes: list = []  # sign-in is one of the 3 public routes (G18)
    permission_classes: list = []

    def post(self, request):
        tenant_id = tenancy.require_tenant(request)
        serializer = SignInSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        session = services.sign_in(
            tenant_id=tenant_id,
            email=serializer.validated_data["email"],
            password=serializer.validated_data["password"],
            keep_signed_in=serializer.validated_data["keep_signed_in"],
            ip=client_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
            # DEF-WRK-9583: the one caller of `sign_in` never passed this, so
            # every attempt read as the web and a field-scoped login could
            # never sign in anywhere.
            surface=serializer.validated_data["surface"],
        )
        membership = selectors.membership_for_user(tenant_id, session.user_id)
        response = Response({"user": _me_payload(session.user, membership)}, status=201)
        policy_values = selectors.security_policy_values(tenant_id)
        # CR-144-BRC07 (X3) — `Secure`, so the session cookie never travels
        # over plain HTTP. ⚠ **ONE SETTING, NOT A LITERAL**: `AUTH_COOKIE_SECURE`
        # defaults True (hard-won law 3) and is turned OFF by
        # `SBH_AUTH_COOKIE_SECURE=false` for local HTTP development.
        # ⚠ **THE NAME `sbh_session` DOES NOT MOVE** — renaming a live session
        # cookie signs every signed-in user out at once.
        # ⚠ **`CR-145-BRC08` — `max_age`, AND IT FIXES A LIVE BUG RATHER THAN
        # ADDING A FEATURE.** Until 2026-09-28 all three `set_cookie` calls in
        # this product passed NO expiry at all, which makes a browser-session
        # cookie: **"Keep me signed in" died when the browser closed**, the one
        # thing it exists to prevent. The server-side 30-day refresh
        # (`auth._refreshable`) was doing its job all along and the cookie
        # carrying it was not, so nothing in any test could see it — the
        # session row was perfectly alive and the browser had thrown away the
        # only way to name it.
        #
        # Ticked → `max_age` is the utility's renewal window in seconds, so the
        # cookie outlives the browser for exactly as long as the server would
        # renew the session behind it. Not ticked → NO `max_age`, deliberately,
        # which is the browser-session cookie that was always intended here.
        #
        # ⚠ **THE NAME `sbh_session` DOES NOT MOVE** (see above): renaming a
        # live session cookie signs every signed-in user out at once.
        response.set_cookie(
            SESSION_COOKIE,
            str(session.id),
            max_age=session_cookie_max_age(policy_values, session.persistent),
            httponly=True,
            samesite="Lax",
            secure=settings.AUTH_COOKIE_SECURE,
        )
        return response

    def delete(self, request):
        # Sign-out authenticates explicitly (the POST half must stay public,
        # so the class-level authenticators list is empty).
        authenticated = IdentitySessionAuthentication().authenticate(request)
        if authenticated is None:
            raise errors.AuthError(errors.AUTH_UNAUTHENTICATED)
        _user, session = authenticated
        services.sign_out(session=session)
        response = Response(status=204)
        response.delete_cookie(SESSION_COOKIE)
        return response


# ── Users & roles (S8 — System Admin only, BR-IDN-009) ──────────────────────
class UsersView(APIView):
    authentication_classes = [IdentitySessionAuthentication]
    permission_classes = [SystemAdminOnly]

    def get(self, request):
        tenant_id = tenancy.require_tenant(request)
        params = parse_list_params(
            request.query_params,
            allowed_sorts=tuple(selectors.USER_LIST_SORTS),
            default_sort=selectors.USER_LIST_DEFAULT_SORT,
        )
        # Capability-row default: Last active DESC; an explicit ?dir wins.
        direction = (
            params.dir
            if "dir" in request.query_params
            else (
                selectors.USER_LIST_DEFAULT_DIR
                if (params.sort or selectors.USER_LIST_DEFAULT_SORT)
                == selectors.USER_LIST_DEFAULT_SORT
                else params.dir
            )
        )
        queryset = selectors.user_list(tenant_id, sort=params.sort, direction=direction)
        paginator = StandardPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        return paginator.get_paginated_response([_membership_row(m) for m in page])

    def post(self, request):
        tenant_id = tenancy.require_tenant(request)
        serializer = AddUserSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user, membership, temp_password = services.add_user(
            actor=request.user,
            tenant_id=tenant_id,
            full_name=serializer.validated_data["full_name"],
            email=serializer.validated_data["email"],
            role_code=serializer.validated_data["role"],
            phone=serializer.validated_data.get("phone"),
        )
        body = {"user": _membership_row(membership), "temp_password": temp_password}
        # `CR-188-BRC10` (PO 2026-10-22) — the on-screen password stays, AND a
        # one-time sign-in link is emailed. Never raises: the user above is
        # created whatever the mail does; the answer says which happened.
        body["invitation_email"] = password_links.email_access_link(
            actor=request.user, user=user, purpose=PasswordLink.PURPOSE_INVITE
        )
        # `CR-187-BRC10` (`R105`) — a FIELD TECHNICIAN is created here, in
        # Settings › Users, and claims the account on the native app with a
        # six-character code. ADDITIVE: two more keys on the answer, shown once
        # like the temporary password beside them; nothing else moves.
        if membership.role.code == FIELD_TECHNICIAN:
            body.update(native.issue_activation_code(actor=request.user, user=user))
        # Temp password: displayed exactly once, never retrievable (BR-IDN-022).
        return Response(body, status=201)


class UserDetailView(APIView):
    authentication_classes = [IdentitySessionAuthentication]
    permission_classes = [SystemAdminOnly]

    def patch(self, request, user_id):
        _tenant_id, user, membership = _resolve_target(request, user_id)
        serializer = EditUserSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.update_user(
            actor=request.user,
            user=user,
            membership=membership,
            full_name=serializer.validated_data.get("full_name"),
            email=serializer.validated_data.get("email"),
            role_code=serializer.validated_data.get("role"),
            phone=serializer.validated_data.get("phone"),
        )
        membership.refresh_from_db()
        return Response({"user": _membership_row(membership)})

    def delete(self, request, user_id):
        _tenant_id, user, membership = _resolve_target(request, user_id)
        services.remove_user(actor=request.user, user=user, membership=membership)
        return Response(status=204)


class UserDeactivateView(APIView):
    authentication_classes = [IdentitySessionAuthentication]
    permission_classes = [SystemAdminOnly]

    def post(self, request, user_id):
        _tenant_id, user, membership = _resolve_target(request, user_id)
        services.deactivate_user(actor=request.user, user=user, membership=membership)
        return Response({"user": _membership_row(membership)})


class UserReactivateView(APIView):
    authentication_classes = [IdentitySessionAuthentication]
    permission_classes = [SystemAdminOnly]

    def post(self, request, user_id):
        _tenant_id, user, membership = _resolve_target(request, user_id)
        services.reactivate_user(actor=request.user, user=user, membership=membership)
        return Response({"user": _membership_row(membership)})


class UserTempPasswordView(APIView):
    authentication_classes = [IdentitySessionAuthentication]
    permission_classes = [SystemAdminOnly]

    def post(self, request, user_id):
        _tenant_id, user, membership = _resolve_target(request, user_id)
        temp_password = services.issue_temp_password(
            actor=request.user, user=user, membership=membership
        )
        user.refresh_from_db()
        return Response(
            {
                "temp_password": temp_password,  # shown once, never retrievable
                "expires_at": user.temp_password_expires_at.isoformat(),
                # `CR-188-BRC10` answer 4, *"email it as well"* — a one-time
                # link, never the password.
                "invitation_email": password_links.email_access_link(
                    actor=request.user, user=user, purpose=PasswordLink.PURPOSE_RESET
                ),
            }
        )


class UserResendInvitationView(APIView):
    """`POST users/{id}/resend-invitation` — `CR-188-BRC10`, PO answer 5:
    *"A: 'Resend invitation' on the row: a new password and a new email."*

    INVITED rows only (the person has never signed in). A new on-screen
    temporary password (`issue_temp_password`, which voids every earlier link
    and password) and a new invitation email whose link voids the old one.
    """

    authentication_classes = [IdentitySessionAuthentication]
    permission_classes = [SystemAdminOnly]

    def post(self, request, user_id):
        _tenant_id, user, membership = _resolve_target(request, user_id)
        if membership.status != TenantMembership.STATUS_INVITED:
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="BR-IDN-011",
                message_key="errors.identity.row_state_disallows",
            )
        temp_password = services.issue_temp_password(
            actor=request.user, user=user, membership=membership
        )
        user.refresh_from_db()
        return Response(
            {
                "temp_password": temp_password,
                "expires_at": user.temp_password_expires_at.isoformat(),
                "invitation_email": password_links.email_access_link(
                    actor=request.user, user=user, purpose=PasswordLink.PURPOSE_INVITE
                ),
            }
        )


class UserActivationCodeView(APIView):
    """`POST users/{id}/activation-code` — a NEW code for the native app
    (`CR-187-BRC10`, `R105`): the one the office gave was lost, or seven days
    passed. Every earlier unused code of the login is void at once. The code is
    shown once, never retrievable — the temporary password's rule (BR-IDN-022).
    System Admin only, like every other user-management act (BR-IDN-009)."""

    authentication_classes = [IdentitySessionAuthentication]
    permission_classes = [SystemAdminOnly]

    def post(self, request, user_id):
        _tenant_id, user, _membership = _resolve_target(request, user_id)
        return Response(native.issue_activation_code(actor=request.user, user=user), status=201)


# ── The native field app (CR-187-BRC10) ─────────────────────────────────────
class NativeAuthThrottle(PublicOnboardingThrottle):
    """The native sign-in doors are public, so they are throttled per address
    like the other public routes (11b G12). 30 a minute: a depot of twelve
    technicians signing in on one wi-fi at 07:30 fits; a guesser does not, and
    the utility's own lockout still counts every wrong password per login."""

    rate = "30/min"
    scope = "native_auth"


class ActivationThrottle(PublicOnboardingThrottle):
    """FF-56/57: ten a minute per address. A code is six characters, so the
    door that checks it is the tightest in the product; each code also burns
    after `native.ACTIVATION_MAX_FAILED` wrong emails."""

    rate = "10/min"
    scope = "native_activation"


class _ActivationLookupLimit(PublicOnboardingThrottle):
    """`DEF-FLD-10580` — the utility-free lookup door's limit, PLATFORM-WIDE.

    PO 2026-10-24 (decision log, *"MQ-006: THE CODE FROM THE OFFICE SETS THE
    UTILITY"*): no utility's Settings › Security can apply before the code has
    named the utility, so this door is held by one platform limit —
    `ACTIVATION_LOOKUP_MAX_TRIES` per `ACTIVATION_LOOKUP_WINDOW_S` (seed 10 per
    15 minutes, env-overridable, read at call time) — counted twice: once per
    network address and once per device. Once the code HAS named the utility,
    wrong emails against it follow that utility's own lockout count
    (`native.activation_max_failed`), unchanged.

    DRF's rate string cannot say *per 15 minutes*, so the window is read from
    settings here rather than squeezed into one."""

    rate = "settings"

    def get_rate(self):  # noqa: D401 — DRF hook
        return "settings"

    def parse_rate(self, rate):  # noqa: ARG002 — DRF hook
        return (
            int(getattr(settings, "ACTIVATION_LOOKUP_MAX_TRIES", 10)),
            int(getattr(settings, "ACTIVATION_LOOKUP_WINDOW_S", 15 * 60)),
        )


class ActivationLookupAddressThrottle(_ActivationLookupLimit):
    """Per network address (the same `get_ident` every throttle here uses)."""

    scope = "activation_lookup_ip"


#: The header the field app sends its device id in (`httpAuthApi.ts`).
DEVICE_ID_HEADER = "HTTP_X_DEVICE_ID"


class ActivationLookupDeviceThrottle(_ActivationLookupLimit):
    """Per device id — the `X-Device-Id` header the field app sends. A request
    with no device id counts against its address instead, so leaving the
    header off buys nothing."""

    scope = "activation_lookup_device"

    def get_cache_key(self, request, view):
        device = str(request.META.get(DEVICE_ID_HEADER) or "").strip()[:200]
        ident = f"device:{device}" if device else f"addr:{self.get_ident(request)}"
        return self.cache_format % {"scope": self.scope, "ident": ident}


def _one_identifier(data: dict) -> str:
    """`CR-187-BRC10` — the sign-in field: `identifier` (work email OR
    phone number), or the older `email` (additive: an app that still sends
    `email` keeps working). Neither ⇒ refused by name, VAL-001."""
    typed = str(data.get("identifier") or data.get("email") or "").strip()
    if not typed:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            field_errors=[{"field": "identifier", "code": errors.VAL_REQUIRED, "params": {}}],
            br_ref="BR-IDN-001",
        )
    return typed


class NativeTokenSerializer(serializers.Serializer):
    #: A work email or a phone number — `@` makes it an email (`phones.py`).
    identifier = serializers.CharField(max_length=320, required=False, allow_blank=True)
    #: The original field, kept so an older app build still signs in.
    email = serializers.EmailField(required=False, allow_blank=True)
    password = serializers.CharField(trim_whitespace=False)
    device_id = serializers.CharField(max_length=200)
    device_name = serializers.CharField(required=False, allow_blank=True, default="")


class NativeRefreshSerializer(serializers.Serializer):
    refresh_token = serializers.CharField()
    device_id = serializers.CharField(required=False, allow_blank=True, default="")


class ActivationCheckSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=32)
    identifier = serializers.CharField(max_length=320, required=False, allow_blank=True)
    email = serializers.CharField(max_length=320, required=False, allow_blank=True)


class ActivationCompleteSerializer(serializers.Serializer):
    activation_ticket = serializers.CharField()
    password = serializers.CharField(trim_whitespace=False)
    device_id = serializers.CharField(max_length=200)
    device_name = serializers.CharField(max_length=80)


class NativeTokenView(APIView):
    """`POST auth/token` — sign in on the native app → bearer tokens.
    `DELETE auth/token` — sign out THIS sign-in (the bearer in the header).

    Public for the same reason `auth/session` is: a caller who could already
    authenticate would not be signing in. DELETE authenticates by hand, as the
    cookie's sign-out does, so the POST half can stay public."""

    authentication_classes: list = []
    permission_classes: list = []
    throttle_classes = [NativeAuthThrottle]

    def post(self, request):
        tenant_id = tenancy.require_tenant(request)
        serializer = NativeTokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        payload = native.sign_in_native(
            tenant_id=tenant_id,
            identifier=_one_identifier(data),
            password=data["password"],
            device_id=data["device_id"],
            device_name=data.get("device_name", ""),
            ip=client_ip(request),
        )
        return Response(payload, status=201)

    def delete(self, request):
        tenancy.require_tenant(request)
        authenticated = NativeBearerAuthentication().authenticate(request)
        if authenticated is None:
            raise errors.AuthError(errors.AUTH_UNAUTHENTICATED)
        _user, token = authenticated
        native.sign_out_native(token=token)
        return Response(status=204)


class NativeTokenRefreshView(APIView):
    """`POST auth/token/refresh` — `{refresh_token, device_id?}` → a new pair.
    Single use; a spent token presented again ends the sign-in for both."""

    authentication_classes: list = []
    permission_classes: list = []
    throttle_classes = [NativeAuthThrottle]

    def post(self, request):
        tenant_id = tenancy.require_tenant(request)
        serializer = NativeRefreshSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        return Response(
            native.refresh_native(
                tenant_id=tenant_id,
                refresh_token=data["refresh_token"],
                device_id=data.get("device_id") or None,
                ip=client_ip(request),
            )
        )


class ActivationLookupSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=32)


class ActivationLookupView(APIView):
    """`POST /api/auth/activation/lookup` — `{code}` → `{tenant, utility_name}`
    (`DEF-FLD-10580`, PO 2026-10-24: *"the code from the office sets the
    utility"*). NO utility in the path: the phone is one build for every
    utility and knows only the code. Public, throttled per address AND per
    device, one refusal for every way a code can be wrong
    (`native.lookup_activation_code`)."""

    authentication_classes: list = []
    permission_classes: list = []
    throttle_classes = [ActivationLookupAddressThrottle, ActivationLookupDeviceThrottle]

    def post(self, request):
        serializer = ActivationLookupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(native.lookup_activation_code(code=serializer.validated_data["code"]))


class ActivationCheckView(APIView):
    """`POST auth/activation/check` — FF-56: `{code, identifier}` (a work email
    or phone number; `email` still accepted) → who the account
    is for, the utility, its password rules, and a ticket for FF-57."""

    authentication_classes: list = []
    permission_classes: list = []
    throttle_classes = [ActivationThrottle]

    def post(self, request):
        tenant_id = tenancy.require_tenant(request)
        serializer = ActivationCheckSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        return Response(
            native.check_activation(
                tenant_id=tenant_id, code=data["code"], identifier=_one_identifier(data)
            )
        )


class ActivationCompleteView(APIView):
    """`POST auth/activation/complete` — FF-57: own password + device name →
    signed in (the same answer as `POST auth/token`)."""

    authentication_classes: list = []
    permission_classes: list = []
    throttle_classes = [ActivationThrottle]

    def post(self, request):
        tenant_id = tenancy.require_tenant(request)
        serializer = ActivationCompleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        payload = native.complete_activation(
            tenant_id=tenant_id,
            activation_ticket=data["activation_ticket"],
            password=data["password"],
            device_id=data["device_id"],
            device_name=data["device_name"],
            ip=client_ip(request),
        )
        return Response(payload, status=201)


class RolesView(APIView):
    authentication_classes = [IdentitySessionAuthentication]
    permission_classes = [SystemAdminOnly]

    def get(self, request):
        # BR-IDN-014: read-only platform catalog + the signed A4 grid; no
        # mutating method exists on this route (US-IDN-007 TC-4 → 405).
        return _maybe_304(request, selectors.roles_matrix())


# ── The emailed one-time sign-in link (`CR-188-BRC10`) ─────────────────────
class PasswordLinkThrottle(PublicOnboardingThrottle):
    """Ten a minute per address — the activation door's rate. A token is 256
    bits, so the throttle is about load, not guessing."""

    rate = "10/min"
    scope = "password_link"


class PasswordLinkCheckSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=200)


class PasswordLinkCompleteSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=200)
    new_password = serializers.CharField(trim_whitespace=False)
    confirm_password = serializers.CharField(trim_whitespace=False)


class PasswordLinkCheckView(APIView):
    """`POST auth/password-link/check` — `{token}` → who it is for, the utility
    and its password rules. Public and throttled; one refusal for every way a
    link can be dead (BR-IDN-002). POST, so the token never sits in a log."""

    authentication_classes: list = []
    permission_classes: list = []
    throttle_classes = [PasswordLinkThrottle]

    def post(self, request):
        tenant_id = tenancy.require_tenant(request)
        serializer = PasswordLinkCheckSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(
            password_links.check_link(tenant_id=tenant_id, token=serializer.validated_data["token"])
        )


class PasswordLinkCompleteView(APIView):
    """`POST auth/password-link/complete` — the person's own password. Spends
    the link, activates an invited membership, ends every session; the person
    then signs in (BR-IDN-022 as amended 2026-10-05)."""

    authentication_classes: list = []
    permission_classes: list = []
    throttle_classes = [PasswordLinkThrottle]

    def post(self, request):
        tenant_id = tenancy.require_tenant(request)
        serializer = PasswordLinkCompleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        password_links.complete_link(
            tenant_id=tenant_id,
            token=data["token"],
            new_password=data["new_password"],
            confirm_password=data["confirm_password"],
        )
        return Response(status=204)


# ── The sign-in screen's one public question (`CR-145-BRC08`) ──────────────
class SignInOptionsView(APIView):
    """`GET auth/sign-in-options` — is *"Keep me signed in"* offered here?

    ⚠ **IT IS PUBLIC BECAUSE THE SCREEN THAT ASKS IT IS.** The sign-in form is
    rendered before anybody has a session, so a signed-in read cannot answer
    it. Without this, a utility that switches the tick box off would still see
    it drawn, and the person ticking it would be refused at sign-in with no
    idea why — hard-won law 2's mirror, a live control over a dead setting.

    ⚠ **IT RETURNS ONE BOOLEAN AND IT IS THE WHOLE OF THE READ.** Not the
    policy, not the limits, not the timeouts, not the lockout numbers. Those
    are an attacker's reconnaissance — *"this utility locks after three
    attempts for five minutes"* tells a password sprayer exactly how to pace
    itself — and none of them changes what the sign-in FORM looks like. The
    serialiser here is a literal dict rather than the policy payload with
    fields removed, because a filter is one edit away from leaking and a
    literal is not.

    ⚠ **AND IT DISCLOSES NO TENANT.** An unknown utility gets the DEFAULT
    answer (`True`), never a 404 — a 404 here would turn this into a free
    "does this utility exist" oracle for anyone who can spell a subdomain,
    which is the same enumeration `BR-IDN-002` forbids one door along.
    `require_tenant` has already refused a slug that resolves to nothing, so
    what is left is the ordinary case of a tenant with no policy row.

    Throttled exactly as the other public reads are (11b G12):
    `PublicOnboardingThrottle`, 60/min.
    """

    authentication_classes: list = []
    permission_classes: list = []
    throttle_classes = [PublicOnboardingThrottle]

    def get(self, request):
        tenant_id = tenancy.require_tenant(request)
        offered = selectors.security_policy_values(tenant_id)["keep_signed_in_offered"]
        return Response({"keep_signed_in_offered": bool(offered)})


# ── Security tab (S8 — BR-IDN-019: SysAdmin edits, Executive views) ─────────
class SecurityPolicyView(APIView):
    authentication_classes = [IdentitySessionAuthentication]

    def get_permissions(self):
        if self.request.method == "PUT":
            return [SystemAdminOnly()]
        return [AdminOrExecutive()]  # A4: Settings — Executive View, Clerk none

    def get(self, request):
        tenant_id = tenancy.require_tenant(request)
        return _maybe_304(request, _with_platform_flags(selectors.security_policy_values(tenant_id)))

    def put(self, request):
        tenant_id = tenancy.require_tenant(request)
        serializer = SecurityPolicySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.save_security_policy(
            actor=request.user,
            tenant_id=tenant_id,
            values=dict(serializer.validated_data),
            actor_ip=client_ip(request),
        )
        return Response(_with_platform_flags(selectors.security_policy_values(tenant_id)))


def _with_platform_flags(values: dict) -> dict:
    """The Security tab's read, plus the PLATFORM's say on what it shows.

    `field_app_pinning_enabled` (`CR-195-BRC10`, PO 2026-10-28 *"start A1"*):
    false hides the *Field app certificates* card, because no field-app build
    pins. Added HERE and not in `selectors.security_policy_values`, which is
    also the sign-in engine's read and holds only what a utility may set; it
    is not a field of `SecurityPolicySerializer`, so a PUT carrying it is
    ignored. Served on the PUT's answer too — the screen replaces its copy
    with that answer, so leaving it off would hide the card after every Save.
    """
    return {**values, "field_app_pinning_enabled": bool(getattr(settings, "FIELD_APP_PINNING_ENABLED", False))}


class SecurityPolicyAuditView(APIView):
    """`GET settings/security-policy/audit` — the Audit log card under Save.

    The approved redesign of 2026-09-29 puts a full-width card below the Save
    button showing **the last five changes made on this tab**, not the
    platform-wide log (PO: *"keep it here only in this screen"*). `View all →`
    on that card opens S61, which is where the whole log and its paging live.

    ⚠ **SAME ROLE GATE AS THE POLICY READ, ON PURPOSE.** A System Admin edits
    and an Executive views (`BR-IDN-019`); a Billing Clerk cannot see the
    Security tab at all, and a history of it is the same disclosure as the
    values it lists. A gate of its own here would be a second answer to one
    question.

    ⚠ **NO ETag/304.** `_maybe_304` is for reference data that rarely moves
    (/roles, the policy itself). This read changes every time anybody saves,
    and it carries timestamps, so a cached answer is the one thing a history
    card must never give.

    ⚠ **NO PAGE ENVELOPE, AND THAT IS NOT AN `NFR-3` BREACH.** The read is a
    fixed five rows over a bounded scan (`audit_seam.SCAN_LIMIT`), so it does
    not grow with the tenant; the unbounded view of the same data is S61,
    which pages.
    """

    authentication_classes = [IdentitySessionAuthentication]
    permission_classes = [AdminOrExecutive]

    def get(self, request):
        tenant_id = tenancy.require_tenant(request)
        return Response(selectors.security_policy_audit_card(tenant_id))


class FieldAppPinsView(APIView):
    """`GET/PUT settings/security-policy/field-app-pins` — the field app's
    certificate pins, the "Field app certificates" card on Settings › Security
    (`OQ-FLD-12797`, PO 2026-10-24: *"use settings - security values set in
    staff portal"*).

    A PUT carries the WHOLE list (`{"pins": [...]}`) — add and deactivate are
    both "the list as it should be", so one validator sees the result the
    phones will get and can refuse a list that would strand them
    (`field_pins.validate_pins`). Same role gate as the policy itself
    (`BR-IDN-019`): a System Admin edits, an Executive views.

    ⚠ **NO ETag/304.** The derived `status` and `days_left` move with the
    calendar, so a cached answer would go on calling a key *Valid* the day it
    starts to expire.
    """

    authentication_classes = [IdentitySessionAuthentication]

    def get_permissions(self):
        if self.request.method == "PUT":
            return [SystemAdminOnly()]
        return [AdminOrExecutive()]

    def get(self, request):
        tenant_id = tenancy.require_tenant(request)
        return Response(field_pins.pins_payload(tenant_id))

    def put(self, request):
        tenant_id = tenancy.require_tenant(request)
        data = request.data if isinstance(request.data, dict) else {}
        return Response(
            field_pins.save_pins(actor=request.user, tenant_id=tenant_id, pins=data.get("pins"))
        )


# ── Self-service (S48 — any authenticated role, own row only) ───────────────
class MeView(APIView):
    authentication_classes = [IdentitySessionAuthentication]
    permission_classes = [FieldAppRole]  # DEF-WRK-9593 — the technician too

    def get(self, request):
        tenant_id = tenancy.require_tenant(request)
        membership = selectors.membership_for_user(tenant_id, request.user.id)
        return Response(_me_payload(request.user, membership))

    def patch(self, request):
        if "role" in request.data:
            # US-IDN-008 TC-7: privilege-escalation guard — role is NEVER
            # editable via profile (BR-IDN-027); denied attempt audited (BE-02).
            raise errors.AuthError(errors.AUTH_PERMISSION_DENIED, br_ref="BR-IDN-027")
        if "email" in request.data:
            # BR-IDN-017 v1 (11b §2.2 ratified row): email changes go through
            # the System-Admin users endpoint. E2 tension with US-IDN-008 TC-2
            # reported, not resolved here.
            raise errors.AuthError(errors.AUTH_PERMISSION_DENIED, br_ref="BR-IDN-017")
        serializer = ProfileSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.update_profile(
            actor=request.user,
            full_name=serializer.validated_data.get("full_name"),
            phone=serializer.validated_data.get("phone"),
        )
        tenant_id = tenancy.require_tenant(request)
        membership = selectors.membership_for_user(tenant_id, request.user.id)
        return Response(_me_payload(request.user, membership))


class MePermissionsView(APIView):
    """GET /me/permissions — the caller's OWN effective permission set.

    Why it exists (PO directive 2026-08-09, "create endpoints for all and
    integrate"): `/roles` serves the whole grid and is System-Admin-only, so a
    Billing Clerk or Executive had no way to discover what they may reach — the
    Settings UI had to probe each tab and read the 403. This route answers the
    caller's own A4 row and nothing else: no other role's cells, no catalog
    enumeration, no cross-tenant data (the role comes from the membership of
    the path-resolved tenant, server-attached, never client input).

    It is UI-gating CONVENIENCE (BR-SHL-025 / 11b G13): every endpoint still
    enforces its own gate, and a client that lies about this payload gains
    nothing. ETag/304 like the other reference reads (11b G6).
    """

    authentication_classes = [IdentitySessionAuthentication]
    permission_classes = [AnyTenantRole]

    def get(self, request):
        tenant_id = tenancy.require_tenant(request)
        membership = selectors.membership_for_user(tenant_id, request.user.id)
        if membership is None:
            # Auth already refuses a non-member; defence in depth, never a
            # silently empty permission set.
            raise errors.AuthError(errors.AUTH_PERMISSION_DENIED, br_ref="BR-IDN-010")
        payload = selectors.permission_set_for_role(membership.role.code)
        if payload is None:  # platform catalog missing = broken deployment, loud
            raise errors.SysError(
                errors.SYS_INTERNAL, message_key="errors.identity.role_catalog_missing"
            )
        return _maybe_304(request, payload)


class MePasswordView(APIView):
    authentication_classes = [IdentitySessionAuthentication]
    permission_classes = [FieldAppRole]  # DEF-WRK-9593 — the technician too

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.change_password(
            actor=request.user,
            current_password=serializer.validated_data.get("current_password"),
            new_password=serializer.validated_data["new_password"],
            confirm_password=serializer.validated_data["confirm_password"],
            sign_out_other_sessions=serializer.validated_data["sign_out_other_sessions"],
            current_session=request.auth,
        )
        return Response(status=204)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-IDN-001@402b6db (EP-IDN-01; also US-IDN-002/003@402b6db · US-IDN-004/005/006/007@9d61512 · US-IDN-008@c4e29d2 · US-IDN-010@493ea2f — hash = sha256/7 of each source epic)
# generated: 2026-08-09 by story-coder v1 (identity W0 feature-story lane, backend only) · AMENDED 2026-08-09 by story-coder (API-gap lane: GET /me/permissions) · AMENDED 2026-08-10 by story-coder (path-tenancy lane — PO ruling 2026-08-10)
# checklist: A✔ B✔ C✔ D✔ E=deferred(no-frontend-half — screens come later) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: py_compile✔ · pytest tests -m "not golden and not isolation" 323-green-0-fail at handoff (shared tree, concurrent tenancy lane active) · run_gates 11-PASS/0-FAIL✔ (G9 active: catalog exceptions only, no ORM in this file) · trace_lint✔ · mypy NOT run — flagged, deferred with the CI lane · [API-gap lane 2026-08-09] ruff✔(E4/E7/E9/F on the app files — the test tier carries the repo's pre-existing F811 fixture-import pattern) black✔ · suite `pytest tests -m "not golden and not isolation"` 682 passed / 7 skipped / 47 deselected (green at handoff in a SHARED tree — concurrent tenancy/settings + billing/payments lanes landed work during this lane; 594 was the baseline when this lane started, this lane adds 26 active TCs + 2 isolation halves) · run_gates 11-PASS/0-FAIL/1-SKIP✔ (this lane adds no migration and no 🔒 guarded file; a transient G7 FAIL seen mid-lane was a CONCURRENT lane's un-ledgered migration and cleared when they landed its row) · trace_lint✔ · mypy NOT INSTALLED in this environment (recorded, not skipped silently) · [path-tenancy lane 2026-08-10] ruff✔ black✔ · suite `pytest tests -m "not golden and not isolation"` 818 passed / 9 skipped (788 baseline) · `-m isolation` 32 passed / 12 skipped (29 baseline) · run_gates 11-PASS/0-FAIL/1-SKIP✔ · trace_lint✔ · no migration in this lane
# exceptions: PATCH /me rejects email per the ratified 11b row (E2 vs US-IDN-008 TC-2 reported) · sign-in response shape minimal (A11 row anchors path + rules, not a body — flagged for the client lane) · ETag on /roles + /settings/security-policy per 11b G6 · API-gap lane 2026-08-09: GET /me/permissions is a NEW path with no A11/11b row (PO directive "create endpoints for all and integrate") — REPORTED for the A11 addendum; it reuses the /roles matrix source rather than re-transcribing A4, serves only the caller's own cells, and grants nothing (BR-SHL-025) · [path-tenancy lane 2026-08-10] sign-in/sign-out moved to /api/{tenant}/auth/session; an unknown tenant slug is a plain 404 from require_tenant, identical to the foreign-session answer
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
