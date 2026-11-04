# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-001 (EP-CWP-01) · US-CWP-002 — the guard in front of every
#           guest door, widened by the PO ruling of 2026-09-03 (NFR-38–41).
# Rules:    NFR-39 (a portal request may never degrade a back-office request:
#           its own connection budget, and rate limits PER TENANT as well as
#           per address) · NFR-41 (the guest surface is the cheapest thing in
#           the product — the throttle and the lockout are the floor, not the
#           whole answer) · BR-CWP-022 (sixty a minute per address — the
#           existing throttle, reused) · BR-CWP-011 (the guest edge has its own
#           middleware) · NFR-5 (no hard cap on tenants — the budget bounds
#           requests in flight, never utilities)
# Tests:    06-backend/tests/test_us_cwp_001_load.py
# Impacts:  guest_api.py (both guards on every guest route) ·
#           config/settings/base.py (PORTAL_TENANT_RATE · PORTAL_INFLIGHT_MAX ·
#           CACHES)
# ───────────────────────────────────────────────────────
"""The portal's own middleware — two guards the staff app does not carry.

WHY TWO, AND WHY NEITHER IS THE EXISTING THROTTLE
-------------------------------------------------
`PublicOnboardingThrottle` counts requests PER ADDRESS (sixty a minute,
BR-CWP-022). That bounds one stranger. It does not bound one utility: a
busy afternoon at Pine Hill is a few hundred customers on a few hundred
addresses, each well under sixty, and together they can take every worker
the back office needs. The PO's words (2026-09-03): *"it should not hamper
performance of back office user"*. So:

1. **`PortalTenantThrottle`** — a second rate, counted PER TENANT SLUG, on
   every guest route beside the per-address one. `PORTAL_TENANT_RATE`
   (default `600/min`, ten times the per-address rate) is a DEFAULT, stated
   as one, and moves in `config/settings/base.py`. One utility's spike
   answers 429 + `Retry-After` for THAT utility's visitors and nobody else's
   (NFR-39: *"one utility's busy day is not another utility's outage"*).

1b. **`PortalSignedInThrottle`** — the same dimension for the SIGNED-IN half,
   at its own rate. ⚠ **ADDED 2026-09-05 (`DEF-CWP-3931`), BECAUSE FOR TWO DAYS
   THIS DOCSTRING DESCRIBED A PROTECTION THAT COVERED THE OTHER TRAFFIC.** The
   sentence above — *a busy afternoon at Pine Hill is a few hundred customers
   on a few hundred addresses* — describes customers who are SIGNED IN, reading
   their bills, and not one of the fifty-four authenticated endpoints carried
   either guard: `guest_api.py` was 15 of 15, `api.py` was 8 of 62 and all
   eight of those are `AllowAny`. `NFR-38` counts *"guests and signed-in
   customers together"*, and the busiest minute a utility has is the hour after
   a bill run, when signing in is bounded and everything after it was not.

2. **`portal_admission`** — the connection budget. This deployment runs
   gunicorn with a handful of SYNC workers and NO connection pool
   (`docker-entrypoint.sh`, `GUNICORN_WORKERS`, default 3), so *"the pool
   the staff app draws from"* is literally the worker count, and a portal
   spike exhausts it by occupying every worker at once. The budget is
   therefore a cap on portal requests IN FLIGHT across the deployment:
   `PORTAL_INFLIGHT_MAX` (default `GUNICORN_WORKERS − 1`, so one worker is
   always free for a clerk). A request over the budget is refused at once —
   429, `Retry-After: 1`, `errors.rate-limited` — before it touches the
   database, which is the cheapest thing a refused request can cost.

WHERE THE COUNTER LIVES, AND THE ONE LIMITATION STATED
-------------------------------------------------------
Both guards count in Django's default cache. With `CACHES` on Redis (the
deployment shape — `config/settings/base.py` wires it when `REDIS_URL` is
set) the count is shared by every worker and the budget is real. On the
per-process LocMem cache (tests, a bare `runserver`) each process counts
its own, and a sync worker never holds more than one request, so the
admission guard is exercised there only by the test that fakes a slot. The
docstring says so because a guard that looks global and is per-process is
hard-won law 1 in a middleware.

A slot that a dying process never released is a leak; the key carries a
short TTL so it heals itself, and the cost of that leak is one refused
request a minute, never a stuck door.
"""

from __future__ import annotations

import functools
from typing import Any, Callable

from django.conf import settings
from django.core.cache import cache
from rest_framework import exceptions as drf_exceptions
from rest_framework.throttling import SimpleRateThrottle

#: The in-flight counter's key and the TTL that heals a leaked slot.
INFLIGHT_KEY = "portal:inflight"
INFLIGHT_TTL_SECONDS = 60
#: What a refused request is told to wait. One second: the door is not
#: closed, it is full, and the next worker frees in well under that.
INFLIGHT_RETRY_AFTER_SECONDS = 1


class PortalTenantThrottle(SimpleRateThrottle):
    """Sixty a minute per address is BR-CWP-022; this is the second
    dimension — per UTILITY — so one tenant's spike is bounded on its own
    (NFR-39). The rate is read from settings at instantiation so a
    deployment (and a test) can move it without touching code."""

    scope = "portal_tenant"

    def get_rate(self) -> str:
        return getattr(settings, "PORTAL_TENANT_RATE", "600/min")

    def get_cache_key(self, request: Any, view: Any) -> str | None:
        slug = getattr(request, "tenant_slug", None)
        if not slug:
            # A request that named no tenant is refused by require_tenant
            # before it costs anything; there is nothing to count it against.
            return None
        return self.cache_format % {"scope": self.scope, "ident": slug}


class PortalSignedInThrottle(SimpleRateThrottle):
    """The per-tenant rate for the SIGNED-IN half of the portal.

    ⚠ **WHY THIS IS NOT `PortalTenantThrottle` WITH ITS 600/min
    (`DEF-CWP-3931`).** That figure was chosen as ten times the sixty-a-minute
    per-ADDRESS guest rate, for a surface a stranger reaches. The signed-in
    half is a different shape of traffic and a rate that is too low there does
    not protect anybody — **it refuses real customers**, which is a worse
    failure than the gap it closes.

    **Where `3000/min` comes from, so the next lane can argue with the
    arithmetic rather than the number.** The busiest minute a utility has is
    the hour after a bill run, when a notification goes out and customers open
    the app at once. A tenant here is under 3,000 connections (`CLAUDE.md`); a
    burst of ~300 of them arriving inside one minute, each session costing
    roughly eight reads (home, accounts, the bill list, one bill, usage), is
    ~2,400 requests in that minute. `3000/min` clears that with headroom and
    still catches a runaway — it is a ceiling on ABUSE, not a shaper of normal
    peaks. **It is deliberately loose and is stated as such**; the figure that
    would actually bound this is a MEASURED one (`NFR-42`'s load case — 500
    concurrent portal users with the back office working — which nothing yet
    runs), and this rate is here so the dimension exists rather than to be the
    final answer.

    **The protection that does the real work on this half is the in-flight
    budget below**, which is what keeps a worker free for a clerk (`NFR-39`).
    This rate is the fairness dimension between tenants (`NFR-39`'s third
    isolation: *one utility's busy day is not another utility's outage*).
    """

    scope = "portal_signed_in"

    def get_rate(self) -> str:
        return getattr(settings, "PORTAL_SIGNED_IN_TENANT_RATE", "3000/min")

    def get_cache_key(self, request: Any, view: Any) -> str | None:
        slug = getattr(request, "tenant_slug", None)
        if not slug:
            return None
        return self.cache_format % {"scope": self.scope, "ident": slug}


def _budget() -> int:
    return int(getattr(settings, "PORTAL_INFLIGHT_MAX", 2))


def _take_slot() -> bool:
    """Reserve one in-flight slot, or say the budget is spent.

    `add` seeds the key with its TTL exactly once; `incr` is atomic on every
    backend Django ships. Over budget the increment is undone in the same
    breath, so a refused request never holds what it was refused.
    """
    cache.add(INFLIGHT_KEY, 0, INFLIGHT_TTL_SECONDS)
    try:
        current = cache.incr(INFLIGHT_KEY)
    except ValueError:  # the key expired between add and incr — seed again
        cache.set(INFLIGHT_KEY, 1, INFLIGHT_TTL_SECONDS)
        current = 1
    if current > _budget():
        _release_slot()
        return False
    return True


def _release_slot() -> None:
    try:
        cache.decr(INFLIGHT_KEY)
    except ValueError:
        pass  # already expired: nothing held, nothing to give back


def inflight() -> int:
    """How many portal requests are being served right now (for a test and
    for a health read; never for a decision)."""
    return int(cache.get(INFLIGHT_KEY, 0) or 0)


def portal_admission(view: Callable[..., Any]) -> Callable[..., Any]:
    """Wrap a portal or guest VIEW FUNCTION in the connection budget.

    Applied OUTSIDE DRF's `@api_view` so the refusal is raised inside DRF's
    handling — `Throttled` renders as the 429 envelope with `Retry-After`
    (core.errors) — while the slot is held for exactly the view's own
    duration and released on every exit, exception included.
    """

    # ⚠ **IDEMPOTENT, AND THAT IS LOAD-BEARING (`DEF-CWP-3931`).** Wrapping a
    # view twice would take TWO slots for one request and silently halve the
    # budget for that route — a fault with no symptom but a busier-looking
    # portal. When the guard was extended from the eight unauthenticated views
    # to all sixty-two, the eight already had it; this marker is why that could
    # be done mechanically instead of by reading each one.
    if getattr(view, "_portal_admitted", False):
        return view

    @functools.wraps(view)
    def guarded(request: Any, *args: Any, **kwargs: Any) -> Any:
        if not _take_slot():
            raise drf_exceptions.Throttled(wait=INFLIGHT_RETRY_AFTER_SECONDS)
        try:
            return view(request, *args, **kwargs)
        finally:
            _release_slot()

    guarded._portal_admitted = True  # type: ignore[attr-defined]
    return guarded
