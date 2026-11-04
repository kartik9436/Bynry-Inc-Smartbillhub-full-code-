# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-SHL-10621 — no application rate limit on signed-in API calls
#           (VAPT rate-limiting finding).
# Ruling:   decision log 2026-10-27 "VAPT round: five findings ruled" (2) — PO:
#           *"2- yes - would need a documentation on how this has to be set up
#           and controlled from WAF"*; limits as proposed in
#           09-infra/06-vapt-remediation-2026-10.md §2 "Proposed limits".
# Tests:    06-backend/tests/test_def_shl_vapt_rate_limits.py
# ───────────────────────────────────────────────────────
"""The four APPLICATION rate limits, A1–A4 of the remediation document.

    A1  every signed-in call, per USER ......... RATE_USER_PER_MIN   (300)
    A2  every signed-in call, per UTILITY ...... RATE_TENANT_PER_MIN (3000)
    A3  heavy actions, per USER ................ RATE_HEAVY_PER_MIN  (10)
    A4  field-app sync, per PHONE .............. RATE_DEVICE_PER_MIN (120)

All four are DRF throttles in `REST_FRAMEWORK["DEFAULT_THROTTLE_CLASSES"]`, so
they apply to every view that does not declare its own `throttle_classes`. The
public doors that DO declare their own (sign-in, activation, the portal, bill
and agreement links, the partner API) keep exactly the limits they had: a view's
own list replaces the defaults, which is the "exclude them only by their own
classes" the document asks for. A1, A2 and A4 count only SIGNED-IN requests (an
anonymous request has no user, utility or phone to count against — the WAF's
per-address rules W1–W3 are what bound those).

A refusal is 429 with `Retry-After` and `message_key: api.error.rate_limited`
(*"Too many requests. Wait a moment."*) — `AppThrottled` carries the key and
`core.errors.drf_exception_handler` renders it. The older public-door throttles
still answer `errors.rate-limited`, unchanged.

⚠ **RATES ARE READ FROM SETTINGS ON EVERY REQUEST, NOT AT IMPORT.** The four
`RATE_*_PER_MIN` settings come from the environment (`config/settings/base.py`)
so DevOps can tune them on the task definition without a release, and
`APP_RATE_LIMITS_ENABLED` switches all four off — which `config/settings/test.py`
does, so the suite is never throttled by accident. The throttle tests switch
them back on, deliberately.

⚠ **THE COUNTERS LIVE IN THE DEFAULT CACHE, AND THAT IS SHARED ONLY WHEN
`CACHE_URL` IS SET** (`config/settings/base.py`, "The default cache — SHARED
when Redis is there, per-process otherwise"). Without it every gunicorn worker
on every ECS task counts on its own, so a 300-a-minute limit is 300 × workers ×
tasks. The limits still refuse a runaway client — they are just looser than
written — and the deployment must set `CACHE_URL` for them to mean what they
say. Hard-won law 4: setting it in a template reaches no host that already has
its environment.

WHAT IS "HEAVY" (A3) — one list, by METHOD and PATH, below. It is a list rather
than a marker on each view because the views live in nine modules and a list
can be read in one place; `tests/test_def_shl_vapt_rate_limits.py` proves every
pattern matches at least one real route, so a pattern that matches nothing goes
red rather than silently protecting nothing (law 7). Reading a report on screen
is NOT heavy (it is paged and A1 bounds it); running one on demand is.
"""

from __future__ import annotations

import re
from typing import Any

from django.conf import settings
from rest_framework import exceptions as drf_exceptions
from rest_framework.throttling import SimpleRateThrottle

RATE_LIMITED_KEY = "api.error.rate_limited"

#: A3 — heavy actions. POST only, matched against the request path with any
#: trailing slash removed. Each names the act, not the module.
HEAVY_ACTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
    (label, re.compile(pattern))
    for label, pattern in (
        ("export", r"/(?:exports|export)$"),
        ("finance export batch", r"/finance/export/batches$"),
        ("import upload", r"/(?:imports|import|payment-imports)$"),
        ("import commit or load", r"/imports/(?:[^/]+/)?(?:commit|load)$"),
        ("payment import commit", r"/payment-imports/[^/]+/commit$"),
        ("bulk action", r"/bulk(?:-[a-z-]+)?$"),
        ("bill run start", r"/billing/runs$"),
        ("bill run step", r"/billing/runs/[^/]+/(?:calculate|issue|release|catch-up)$"),
        ("print set", r"/billing/print-sets$"),
        ("collections run", r"/collections/run$"),
        ("report run now", r"/reports/schedules/[^/]+/run-now$"),
        ("runbook run", r"/runbooks/[^/]+/runs$"),
        ("integration run", r"/integrations/[^/]+/(?:run|export)$"),
    )
)

#: A4 — the field app's sync doors (the native app and the web field app).
DEVICE_SYNC_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"/work/mobile/sync$"),
    re.compile(r"/work/mobile/jobs/[^/]+/sync$"),
    re.compile(r"/work/mobile/reads/sync$"),
)

DEVICE_ID_HEADER = "HTTP_X_DEVICE_ID"


class AppThrottled(drf_exceptions.Throttled):
    """A 429 from A1–A4, rendered with `api.error.rate_limited`."""

    message_key = RATE_LIMITED_KEY


def heavy_action(request: Any) -> str | None:
    """The A3 label for this request, or None when it is not a heavy action."""
    if request.method != "POST":
        return None
    path = request.path.rstrip("/")
    for label, pattern in HEAVY_ACTION_PATTERNS:
        if pattern.search(path):
            return label
    return None


def device_sync(request: Any) -> bool:
    path = request.path.rstrip("/")
    return request.method == "POST" and any(p.search(path) for p in DEVICE_SYNC_PATTERNS)


def _signed_in_user(request: Any) -> Any | None:
    user = getattr(request, "user", None)
    if user is None or not getattr(user, "is_authenticated", False):
        return None
    if getattr(user, "pk", None) is None:
        return None
    return user


def _tenant_of(request: Any) -> str | None:
    tenant = getattr(getattr(request, "auth", None), "tenant_id", None) or getattr(
        request, "tenant_id", None
    )
    return str(tenant) if tenant is not None else None


class _AppRateThrottle(SimpleRateThrottle):
    """One of A1–A4: a per-minute rate from settings, switchable off."""

    setting_name = ""
    default_per_minute = 0

    def __init__(self) -> None:  # noqa: D401 — DRF builds one per request
        # SimpleRateThrottle reads `self.rate` in __init__; ours comes from
        # settings, read now, so `override_settings` and a changed env both apply.
        self.rate = self.get_rate()
        self.num_requests, self.duration = self.parse_rate(self.rate)

    def get_rate(self) -> str:
        per_minute = int(getattr(settings, self.setting_name, self.default_per_minute))
        return f"{max(per_minute, 1)}/min"

    def ident_for(self, request: Any, view: Any) -> str | None:  # pragma: no cover - abstract
        raise NotImplementedError

    def get_cache_key(self, request: Any, view: Any) -> str | None:
        ident = self.ident_for(request, view)
        if ident is None:
            return None  # not counted by this limit
        return self.cache_format % {"scope": self.scope, "ident": ident}

    def allow_request(self, request: Any, view: Any) -> bool:
        if not getattr(settings, "APP_RATE_LIMITS_ENABLED", True):
            return True
        if super().allow_request(request, view):
            return True
        raise AppThrottled(wait=self.wait())


class UserRateThrottle(_AppRateThrottle):
    """A1 — every signed-in call, per user (within their utility)."""

    scope = "app_user"
    setting_name = "RATE_USER_PER_MIN"
    default_per_minute = 300

    def ident_for(self, request: Any, view: Any) -> str | None:
        user = _signed_in_user(request)
        return None if user is None else f"{_tenant_of(request)}:{user.pk}"


class TenantRateThrottle(_AppRateThrottle):
    """A2 — every signed-in call, per utility."""

    scope = "app_tenant"
    setting_name = "RATE_TENANT_PER_MIN"
    default_per_minute = 3000

    def ident_for(self, request: Any, view: Any) -> str | None:
        if _signed_in_user(request) is None:
            return None
        return _tenant_of(request)


class HeavyActionThrottle(_AppRateThrottle):
    """A3 — exports, imports, report runs, bill runs, bulk actions; per user."""

    scope = "app_heavy"
    setting_name = "RATE_HEAVY_PER_MIN"
    default_per_minute = 10

    def ident_for(self, request: Any, view: Any) -> str | None:
        user = _signed_in_user(request)
        if user is None or heavy_action(request) is None:
            return None
        return f"{_tenant_of(request)}:{user.pk}"


class DeviceSyncThrottle(_AppRateThrottle):
    """A4 — field-app sync, per phone. The phone is the native token's own
    handset id; the web field app (a cookie, no token) is counted by the
    `X-Device-Id` header it sends, else by the person."""

    scope = "app_device"
    setting_name = "RATE_DEVICE_PER_MIN"
    default_per_minute = 120

    def ident_for(self, request: Any, view: Any) -> str | None:
        user = _signed_in_user(request)
        if user is None or not device_sync(request):
            return None
        device = getattr(getattr(request, "auth", None), "device_uid", None) or request.META.get(
            DEVICE_ID_HEADER
        )
        who = f"device:{device}" if device else f"user:{user.pk}"
        return f"{_tenant_of(request)}:{who}"


#: The defaults, in the order DRF evaluates them. Referenced by name from
#: `REST_FRAMEWORK["DEFAULT_THROTTLE_CLASSES"]`.
DEFAULT_THROTTLE_CLASSES = [
    "core.throttling.HeavyActionThrottle",
    "core.throttling.DeviceSyncThrottle",
    "core.throttling.UserRateThrottle",
    "core.throttling.TenantRateThrottle",
]
