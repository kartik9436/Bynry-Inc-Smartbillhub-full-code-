# ── Trace ──────────────────────────────────────────────
# Story:    US-IDN-001 (session issue feeds this) · US-IDN-003 (idle/absolute
#           timeout, one-tenant binding, replay = 401, trusted-device refresh) ·
#           US-IDN-002 (forced-change gate on every app request)
#           Screens: all authenticated screens (S7+); S3 redirect target
# Rules:    BR-IDN-006/026 (server-side sessions bound to ONE tenant — the control the
#           2026-08-10 path-tenancy ruling makes load-bearing; idle from tenant policy,
#           default 60 min; absolute 12 h; keep-me-signed-in 30-day refresh, off by default) ·
#           BR-IDN-022 (forced change gates every app screen) · BR-IDN-020 (IP
#           allowlist on every authenticated request) · BR-IDN-009 (role attachment
#           for BE-04 server-side RBAC) · BR-IDN-012 (deactivated = dead session)
# Tests:    06-backend/tests/test_us_idn_003_sessions.py + gate halves in
#           test_us_idn_002/010 files (RLS halves = G5 isolation suite)
# Impacts:  every api.py authentication_classes · core.permissions (reads the
#           request.tenant_role this class attaches)
# ───────────────────────────────────────────────────────
"""Session authentication for the identity endpoints (and every later module).

The httpOnly cookie carries the opaque session id (US-IDN-003 §4; uuid7 — no
separate token column is anchored, none minted). authenticate() proves, in
order: cookie → live session row → bound to THIS request's tenant (the
`/api/{tenant}/…` path segment since the PO ruling 2026-08-10) → not revoked →
within idle + absolute windows (persistent sessions silently re-establish
within the 30-day trusted-device window, BR-IDN-026) → member still
active-or-invited → request IP inside the tenant allowlist → forced-change
gate. On success it attaches `request.tenant_role` and `user.role` (the code
BE-04's checks and @require_role read) and slides `last_seen_at` — ⚠ **unless
the request says it is an automatic refresh (`X-Background-Refresh: 1`), from
2026-10-08 (`DEF-IDN-10024`)**: that one is authenticated in full and slides
nothing, so a polling page no longer keeps a session awake.

Denial routing: any session/credential problem → DRF AuthenticationFailed
(401 AUTH-001 via BE-02, no factor disclosure); IP-allowlist and forced-change
denials → 403 AUTH-002 with their BR (attempt row written centrally by BE-02);
**a session presented on another tenant's path → 404**, the one refusal that
must be indistinguishable from "no such thing here" (see the block in
authenticate(); it is the acceptance criterion of the path-tenancy ruling).

One browser, one tenant at a time (recorded by the PO with the ruling): the
cookie name is fixed, so signing into tenant B replaces the tenant-A cookie.
BR-IDN-029 is unchanged in law — users are still per-tenant rows — but a staffer
who works two utilities signs in and out rather than holding both at once.
"""

import logging

from django.conf import settings as django_settings
from drf_spectacular.extensions import OpenApiAuthenticationExtension
from rest_framework import exceptions as drf_exceptions
from rest_framework.authentication import BaseAuthentication

from apps.identity import selectors, services
from apps.identity.models import TenantMembership
from core import errors
from core import tenancy as core_tenancy

logger = logging.getLogger("smartbillhub.identity")

SESSION_COOKIE = "sbh_session"

#: ⚠ **`DEF-IDN-10024` — A REQUEST NOBODY ASKED FOR DOES NOT COUNT AS ACTIVITY.**
#: HUMAN-REVIEW-PENDING (🔒 identity/sessions, AI-authored 2026-10-08, PO ruling
#: of that date: *"automatic refreshes stop counting as activity, only a real
#: request from the person slides the idle clock"*).
#:
#: Until 2026-10-08 every authenticated request slid `last_seen_at`, so a page
#: that polls — the bill run every 30 seconds, an import every 2, a job poller,
#: the field app's queue sync — kept its session awake for ever and the
#: utility's *"Sign out after"* setting never fired on it.
#:
#: **The ONE mechanism, chosen and recorded (decision log 2026-10-08):** the
#: SPA's single `fetch` (`07-frontend/src/api/client.ts`) sends this header,
#: value `1`, on every request made while NOBODY HAS TOUCHED THE PAGE for the
#: last minute — a pointer, a key, a scroll or a touch. It is decided in that
#: one place rather than tagged on each polling query, because a tag is a thing
#: the next poll forgets (hard-won law 2) and there are already five kinds of
#: poll in the front end, two of them plain `setInterval`s outside TanStack.
#:
#: **What the server does with it, and only this:** it still AUTHENTICATES the
#: request completely — tenant binding, revocation, the idle and hard limits,
#: membership, the allowed-addresses list, the forced-change gate — and simply
#: does not slide the idle clock. So a background poll is refused 401 exactly
#: when the person has been idle past the utility's limit, which is the point.
#:
#: **Trusting a client header is safe here in the only direction it can be
#: abused:** sending it can only make a session expire SOONER. A client that
#: omits it gets today's behaviour, never more than that.
BACKGROUND_REFRESH_HEADER = "HTTP_X_BACKGROUND_REFRESH"


def is_background_refresh(request) -> bool:
    """`X-Background-Refresh: 1` — sent by the SPA, never by a person."""
    return request.META.get(BACKGROUND_REFRESH_HEADER) == "1"


# BR-IDN-022: the ONLY paths reachable while a password change is owed —
# completing the change and signing out.
_FORCED_CHANGE_EXEMPT = (
    ("POST", "/me/password"),
    ("DELETE", "/auth/session"),
)


def client_ip(request) -> str | None:
    """The caller's address, trusted only as far as OUR OWN proxies (BR-IDN-020).

    `REMOTE_ADDR` is the peer that opened the connection. With nothing in front
    of the process that is the client; behind a load balancer it is the load
    balancer's address on every single request — which makes a per-tenant IP
    allowlist either admit everyone or lock the tenant out, and gives every
    caller in the world one shared throttle identity (09-infra/02 §10.15).

    `X-Forwarded-For` is not the answer on its own: it is a plain request
    header, so anything a client sends arrives in it. What IS trustworthy is
    the tail. Each proxy of ours appends the address it saw its own peer use,
    so reading the chain right-to-left walks back through OUR infrastructure
    one hop at a time — and `settings.TRUSTED_PROXY_COUNT` says how many hops
    that is. With N of our proxies the client is the Nth entry from the right
    of `XFF + [REMOTE_ADDR]`, i.e. `xff[-N]`; everything further left was
    written by someone we do not run and is ignored. A forged chain can only
    grow that ignored left-hand side, so prepending addresses moves the answer
    nowhere.

    N = 0 (the default) trusts no header at all and returns `REMOTE_ADDR`,
    exactly as this function always did. The AWS environment runs one ALB and
    therefore sets 1; the reasoning and the ladder live at the setting.

    The index is bounded by the chain length for the same reason DRF bounds
    its own (`BaseThrottle.get_ident`): a chain SHORTER than the configured
    depth means a hop did not forward, and the leftmost entry is then the
    furthest back we can honestly see. Identical arithmetic in both places is
    deliberate — the allowlist and the throttle must never disagree about who
    is calling.
    """
    remote_addr = request.META.get("REMOTE_ADDR") or None
    trusted = getattr(django_settings, "TRUSTED_PROXY_COUNT", 0) or 0
    if trusted <= 0:
        return remote_addr
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR") or ""
    chain = [hop.strip() for hop in forwarded.split(",") if hop.strip()]
    if not chain:
        return remote_addr
    return chain[-min(trusted, len(chain))]


def session_cookie_max_age(policy_values: dict, persistent: bool) -> int | None:
    """How long the session cookie survives the browser closing, or None.

    ⚠ **ONE FUNCTION FOR THREE CALL SITES, ON PURPOSE (`CR-145-BRC08`).** The
    staff session cookie is set in `apps/identity/api.py` and in
    `apps/tenancy/api.py`, and the portal's in `apps/portal/api.py`. The bug
    this fixes was the SAME bug in all three — no expiry passed anywhere — and
    three copies of the fix is three places for the next one to hide.

    **Ticked → the utility's renewal window, in seconds.** That is the same
    number `IdentitySessionAuthentication._refreshable` uses to decide whether
    to renew the session row, which is what makes the cookie and the session
    agree: a cookie outliving the renewal window would point at a session the
    server has stopped renewing, and a cookie dying inside it throws away a
    session that is still good.

    **Not ticked → `None`, which is a browser-session cookie**, and that is the
    behaviour every session in this product has had until now. It is returned
    explicitly rather than by omitting the argument, so a reader of the call
    site can see that the absence is a decision.

    ⚠ **A UTILITY THAT HAS SWITCHED *"Keep me signed in"* OFF GETS `None` EVEN
    FOR A SESSION MARKED PERSISTENT.** `services.sign_in` refuses the tick box
    in that case so no such session should be created, and `_refreshable`
    refuses to renew one that already exists — a cookie promising thirty days
    over a session nobody will renew is the *live screen behind a dead
    control* half of hard-won law 2.
    """
    if not persistent or not policy_values.get("keep_signed_in_offered", True):
        return None
    return int(policy_values["keep_signed_in_days"]) * 24 * 3600


class IdentitySessionAuthentication(BaseAuthentication):
    """DRF authentication backed by the identity `sessions` table."""

    def authenticate(self, request):
        session_id = request.COOKIES.get(SESSION_COOKIE)
        if not session_id:
            return None  # unauthenticated — role-gated views 401 via BE-04/BE-02

        now = services._now()
        session = selectors.session_by_id(session_id)
        if session is None or session.revoked_at is not None:
            # US-IDN-003 TC-2/TC-5: replay of a revoked/unknown id — the
            # attempt lands in the security log; the answer discloses nothing.
            logger.warning("revoked/unknown session presented (path=%s)", request.path)
            raise drf_exceptions.AuthenticationFailed()

        # ── the control the one-origin move makes load-bearing ────────────
        # One tenant per session (US-IDN-003 TC-6 / BR-IDN-006). Until
        # 2026-08-10 the browser enforced this for free: one host, one cookie
        # jar. `/api/{tenant}/…` is ONE origin, so a tenant-A cookie now
        # travels to tenant-B paths and this check is the ONLY thing standing
        # between them.
        #
        # The answer is 404 — never 403 (which would confirm tenant B exists,
        # HR-1 / 11b G4) and never a silent switch to the session's own tenant
        # (which would serve A's data at B's URL and quietly desync the SPA).
        # deny_as_not_found() renders a body byte-identical to any other 404
        # and records the denial server-side only (BR-AUD-018 attempt row).
        tenant_id = getattr(request, "tenant_id", None)
        if getattr(request, "tenant_slug", None) is None:
            # A PLATFORM path (/api/jobs/{id}, /api/exports…): no slug to match,
            # so the session's own tenant IS the scope (see
            # core.tenancy.adopt_session_tenant for why that is server-side
            # truth rather than client input).
            tenant_id = core_tenancy.adopt_session_tenant(request, session.tenant_id)
        elif tenant_id is None or session.tenant_id != tenant_id:
            # Covers both halves of the leak: a path naming a tenant that does
            # not exist, and a path naming one that does but is not this
            # session's. They MUST be indistinguishable.
            raise errors.deny_as_not_found(br_ref="BR-IDN-006")

        policy_values = selectors.security_policy_values(session.tenant_id)
        idle_limit = policy_values["session_timeout_minutes"] * 60
        idle_expired = (now - session.last_seen_at).total_seconds() > idle_limit
        absolute_expired = now > session.expires_at
        if idle_expired or absolute_expired:
            if self._refreshable(session, now, policy_values) and not services.password_expired(
                session.user, policy_values, now
            ):
                # `DEF-IDN-10022` — a "Keep me signed in" renewal is a sign-in
                # nobody typed, so it must not carry an EXPIRED password past
                # the expiry for up to the utility's renewal days. Refusing the
                # renewal sends the person to the sign-in page, and the sign-in
                # sends them to the forced change.
                services.refresh_persistent_session(session)  # BR-IDN-026, TC-8
            else:
                raise drf_exceptions.AuthenticationFailed()

        user = session.user
        membership = selectors.membership_for_user(session.tenant_id, user.id)
        if membership is None or membership.status == TenantMembership.STATUS_DEACTIVATED:
            # BR-IDN-012: deactivation kills access at once, mid-session.
            raise drf_exceptions.AuthenticationFailed()

        if not services._check_ip_allowed(policy_values, client_ip(request)):
            # BR-IDN-020: enforced on every authenticated request → 403 +
            # BR-AUD-018 attempt row (written centrally by BE-02).
            raise errors.AuthError(errors.AUTH_PERMISSION_DENIED, br_ref="BR-IDN-020")

        if user.must_change_password and not self._forced_change_exempt(request):
            # BR-IDN-022 (US-IDN-002 TC-7): no app surface until the change.
            raise errors.AuthError(
                errors.AUTH_PERMISSION_DENIED,
                message_key="errors.auth.password_change_required",
                br_ref="BR-IDN-022",
            )

        if not is_background_refresh(request):
            # Sliding idle window (TC-4) — a person's request only; an
            # automatic refresh is authenticated above and slides nothing
            # (`DEF-IDN-10024`, see `BACKGROUND_REFRESH_HEADER`).
            services.touch_session(session)
        user.role = membership.role.code  # for @require_role service guards
        request.tenant_role = membership.role.code  # for BE-04 permission classes
        return (user, session)

    @staticmethod
    def _refreshable(session, now, policy_values) -> bool:
        """BR-IDN-026: persistent + unrevoked + inside the utility's window.

        ⚠ **TWO THINGS MOVED HERE ON 2026-09-28 (`CR-145-BRC08`), AND ONLY ONE
        OF THEM IS THE OBVIOUS ONE.**

        The obvious one: the window was a fixed 30 days
        (`services.TRUSTED_DEVICE_REFRESH_DAYS`) and is now the utility's
        `keep_signed_in_days`, 1 to 30.

        The one worth writing down: **a utility that has switched
        *"Keep me signed in"* OFF stops renewing, including for sessions that
        were created while it was on.** Refusing the tick box at sign-in
        (`services.sign_in`) only closes the door to NEW persistent sessions;
        an admin who turns the setting off has said something about unattended
        browsers on their premises, and there is no reading of that sentence
        under which the persistent sessions already out there keep renewing
        for another month. So the switch is read HERE too, which is what `T3`'s
        second half asserts — *"and no renewal ever happens"*.

        `policy_values` is passed in rather than read again: `authenticate`
        read it four lines up for the idle limit, and this is on every
        authenticated request in the product.
        """
        if not session.persistent:
            return False
        if not policy_values["keep_signed_in_offered"]:
            return False
        age = now - session.created_at
        return age.total_seconds() <= policy_values["keep_signed_in_days"] * 24 * 3600

    @staticmethod
    def _forced_change_exempt(request) -> bool:
        path = request.path.rstrip("/") or "/"
        return any(
            request.method == method and path.endswith(suffix)
            for method, suffix in _FORCED_CHANGE_EXEMPT
        )

    def authenticate_header(self, request) -> str:
        return 'Session realm="smartbillhub"'


class IdentitySessionScheme(OpenApiAuthenticationExtension):
    """Publish the cookie in the OpenAPI contract (BE-11 / FI-01).

    ADDED 2026-08-10 with the platform-wide authentication default. Until then
    most views inherited DRF's own defaults, so drf-spectacular published
    `basicAuth` plus a `cookieAuth` named `sessionid` on every one of them —
    two schemes this product has never had. Making IdentitySessionAuthentication
    the default removes both, and without an extension it declares nothing at
    all: 120 operations that require a session would document no security
    whatsoever. This says the true thing instead.

    Registration happens on import of this module, which the DRF settings
    themselves trigger (DEFAULT_AUTHENTICATION_CLASSES names the class above),
    so it cannot be missed by a generator run — asserted in
    tests/test_be11_openapi.py rather than assumed.
    """

    target_class = IdentitySessionAuthentication
    name = "sessionCookie"

    def get_security_definition(self, auto_schema) -> dict:
        return {
            "type": "apiKey",
            "in": "cookie",
            "name": SESSION_COOKIE,
            "description": (
                "Server-side session (identity `sessions` table), set httpOnly by "
                "POST /api/{tenant}/auth/session and bound to that ONE tenant "
                "(BR-IDN-006): presented on another tenant's path it is refused 404. "
                "The browser sends it automatically; no client code reads it."
            ),
        }


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-IDN-003@402b6db (EP-IDN-01 session story; also US-IDN-001/002@402b6db gate halves — hash = sha256/7 of the source epic)
# generated: 2026-08-09 by story-coder v1 (identity W0 feature-story lane, backend only) · AMENDED 2026-08-10 by story-coder (path-tenancy lane — PO ruling 2026-08-10) · AMENDED 2026-08-10 by story-coder (deploy-blocker lane — 09-infra/02 §10.14/§10.15)
# checklist: A✔ B✔ C✔ D✔ E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: py_compile✔ · pytest tests -m "not golden and not isolation" 323-green-0-fail at handoff (shared tree, concurrent tenancy lane active) · run_gates 11-PASS/0-FAIL✔ · trace_lint✔ · mypy NOT run — flagged, deferred with the CI lane · [path-tenancy lane 2026-08-10] ruff✔ black✔ · suite `pytest tests -m "not golden and not isolation"` 818 passed / 9 skipped (788 baseline) · `-m isolation` 32 passed / 12 skipped (29 baseline) · run_gates 11-PASS/0-FAIL/1-SKIP✔ · trace_lint✔ · no migration in this lane · [deploy-blocker lane 2026-08-10] ruff✔ black✔ · pytest tests/test_be_trusted_proxy.py 11 passed · tests/test_be_default_authentication.py 28 passed · suite `pytest tests -m "not golden and not isolation"` 868 passed / 9 skipped (818 baseline) · `-m isolation` 32 passed / 12 skipped (32 baseline) · run_gates 11-PASS/0-FAIL/1-SKIP✔ · trace_lint✔
# exceptions: idle-expiry 401 carries the generic AUTH-001 envelope (BE-02 has no per-cause message key — the S3 "signed out for inactivity" notice is a frontend-half concern, reported) · trusted-device refresh re-establishes the same row (see services.py disposition) · [path-tenancy lane 2026-08-10] a session presented on another tenant's path is now 404 (deny_as_not_found, BR-IDN-006), not 401 — US-IDN-003 TC-6 amended with it; on the three no-tenant PLATFORM paths the session's own tenant is adopted as the scope (core.tenancy.adopt_session_tenant) · [deploy-blocker lane 2026-08-10] this class is now the DRF DEFAULT rather than a per-view declaration (config/settings/base.py) — the four genuinely public routes opt out with `authentication_classes = []`, which is asserted as an exact list by tests/test_be_default_authentication.py so a fifth cannot appear unnoticed · client_ip() no longer means REMOTE_ADDR: it honours X-Forwarded-For to the depth of settings.TRUSTED_PROXY_COUNT (default 0 = unchanged behaviour; AWS with one ALB sets 1), arithmetic deliberately identical to DRF's BaseThrottle.get_ident so BR-IDN-020 and the throttle cannot disagree · BR-IDN-020 remains IPv4-only (services._check_ip_allowed) — widening it to IPv6 is a PO question, REPORTED not decided · NEW IdentitySessionScheme publishes the cookie in the OpenAPI contract; without it the default would have left 120 session-protected operations documenting no security at all (the old schema advertised basicAuth + a `sessionid` cookie, neither of which this product has ever had)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
