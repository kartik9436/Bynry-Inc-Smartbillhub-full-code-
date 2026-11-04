# ── Trace ──────────────────────────────────────────────
# Change:   CR-187-BRC10 lane MIN-VERSION — fixes DEF-FLD-10355 (no
#           minimum-version refusal for the native field app)
# Design:   04-docs/05-modules/18-field-app/07-endpoints.md §0 rule 2 + row N7 ·
#           15-release-and-rollback.md §5.2–§5.3
# Rules:    BR-FLD-00117 (R117 — a versioned wire; a version too old is refused
#           BY NAME, never served wrongly) · R113 (capture never depends on the
#           network) · hard-won law 3 (the default refuses nothing; the unsafe
#           setting is the one you type)
# Tests:    06-backend/tests/test_cr187_min_version.py
# Impacts:  every /api/{tenant}/work/mobile/* route, and the native sign-in
#           routes auth/token, auth/token/refresh, auth/activation/{check,complete}
# ───────────────────────────────────────────────────────
"""The native field app's MINIMUM VERSION — the one server piece that lets us
refuse an installed build too old to be served (07-endpoints row N7).

WHY IT EXISTS
-------------
A bad JavaScript update is undone over the air in minutes; a bad NATIVE build
cannot be recalled from the handsets that installed it (15-release §5.2). This
is what stops such a build doing harm: set `FIELD_APP_MIN_VERSION` above it and
every handset still running it is answered **426 `app_too_old`**, which the app
shows as one *Update the app* screen — never a 500 and never a wrong answer.

WHAT IS READ, AND WHAT IS NEVER REFUSED
---------------------------------------
* `X-Field-App-Version: 2.590.0` (the product version, `field-app/package.json`),
  plus `X-Field-App-Build` and `X-Field-App-Platform`, which are informational
  only — the minimum is a PRODUCT version, because that is what a release note
  names and what `allocate.py version` moves.
* **No header → never refused.** The web field app and a person with curl do not
  send it, and the web field app is the crew's fallback while a binary is halted
  (15-release §5.2). An unreadable header is read as `0.0.0`, so it is refused
  only once somebody has set a minimum.
* **The default minimum is `0.0.0`, which refuses nothing** (law 3 read the
  right way round: turning the refusal ON is the act somebody types). It is
  platform-wide and never per tenant — one binary is the same binary at every
  utility.

⚠ CAPTURED WORK IS STILL ACCEPTED FROM A TOO-OLD BUILD — DELIBERATELY
---------------------------------------------------------------------
07-endpoints §0 rule 2 and 15-release §5.3 say so in as many words: the
minimum-version refusal stops the server SERVING an old build (its day, its
jobs, its routes, a new sign-in), and *"captured work from the older build is
still accepted for sync"*. So the routes that carry captured work UP — the two
sync batches, a route's readings, a photograph's bytes, a route's turn-in — and
the two that keep the credential they travel under alive (refresh, sign-out)
are listed in `SENDS_CAPTURED_WORK` and are never refused here. The handset
keeps every unsent item either way (`field-app/src/sync/receipts.ts`), so if a
later ruling empties that list nothing is lost: the work simply waits for the
update instead of draining now.

THE SCHEMA VERSION (R117)
-------------------------
Every field-app response — success, refusal or 404 — carries
`X-Field-Schema-Version`, the wire payload's version. It is `1`: the handset
reads only `1` today (`field-app/src/sync/delta.ts` `KNOWN_SCHEMA_VERSIONS`)
and treats an absent version as the server of 2026-10-21, which is this one.
It moves only when a change cannot be made additively (07-endpoints §0 rule 1),
and the handset then refuses a version it does not know rather than store nulls.

WHERE IT RUNS
-------------
As middleware, BEFORE the tenant is resolved, so a refusal costs no database
read and the response header is on every answer including the tenant's 404.
It is scoped by PATH to the field routes and nothing else, the same set
`accept_native_bearer` covers plus the native sign-in doors — so a route a lane
adds under `work/mobile/` tomorrow is covered without anybody remembering.
"""

from __future__ import annotations

import re
from typing import Any, Callable

from django.conf import settings
from django.http import HttpResponse, JsonResponse

from core import device_clock, errors

VERSION_HEADER = "X-Field-App-Version"
BUILD_HEADER = "X-Field-App-Build"
PLATFORM_HEADER = "X-Field-App-Platform"
SCHEMA_HEADER = "X-Field-Schema-Version"

#: The wire payload's schema version (R117). See the module docstring.
FIELD_SCHEMA_VERSION = 1

#: 426 Upgrade Required — the client must change before it is served.
HTTP_UPGRADE_REQUIRED = 426
REASON_APP_TOO_OLD = "app_too_old"
#: An existing generic key, deliberately: the native app words this refusal
#: itself from `params.reason` (FF *Update the app*), and the web — which never
#: sends the header — can never receive it.
MESSAGE_KEY = "errors.biz-state"
BR_REF = "BR-FLD-00117"

#: `/api/{tenant}/` then a field-app route. `rest` is what is matched below.
_FIELD_ROUTE = re.compile(
    r"^/api/[^/]+/(?P<rest>"
    r"work/mobile/.+"
    r"|auth/token(?:/refresh)?"
    r"|auth/activation/(?:check|complete)"
    r")/?$"
)

_UUID = r"[0-9a-fA-F-]{36}"

#: (method or None for any, pattern over `rest`) — the routes that carry
#: captured work up, and the two that keep its credential alive. Never refused.
SENDS_CAPTURED_WORK: tuple[tuple[str | None, re.Pattern[str]], ...] = (
    ("POST", re.compile(r"^work/mobile/sync/?$")),
    ("POST", re.compile(rf"^work/mobile/jobs/{_UUID}/sync/?$")),
    ("POST", re.compile(r"^work/mobile/reads/sync/?$")),
    (None, re.compile(rf"^work/mobile/photos/{_UUID}/?$")),
    ("POST", re.compile(rf"^work/mobile/routes/{_UUID}/turn-in/?$")),
    ("POST", re.compile(r"^auth/token/refresh/?$")),
    ("DELETE", re.compile(r"^auth/token/?$")),
)

_VERSION = re.compile(r"^\s*(\d+)(?:\.(\d+))?(?:\.(\d+))?")


def parse_version(text: str | None) -> tuple[int, int, int]:
    """`2.590.0` → (2, 590, 0). Missing parts are 0; unreadable is (0, 0, 0)."""
    match = _VERSION.match(text or "")
    if not match:
        return (0, 0, 0)
    return tuple(int(part or 0) for part in match.groups())  # type: ignore[return-value]


def minimum_version() -> str:
    return str(getattr(settings, "FIELD_APP_MIN_VERSION", "") or "0.0.0").strip() or "0.0.0"


def field_route(path: str) -> str | None:
    """The part after `/api/{tenant}/` when `path` is a field-app route, else None."""
    match = _FIELD_ROUTE.match(path)
    return match.group("rest") if match else None


def sends_captured_work(method: str, rest: str) -> bool:
    return any((m is None or m == method) and p.match(rest) for m, p in SENDS_CAPTURED_WORK)


def too_old_refusal(version: str, minimum: str) -> JsonResponse:
    body = errors.http_series_refusal_body(
        MESSAGE_KEY,
        br_ref=BR_REF,
        reason=REASON_APP_TOO_OLD,
        minimum=minimum,
        version=version,
    )
    return JsonResponse(body, status=HTTP_UPGRADE_REQUIRED)


class FieldAppVersionMiddleware:
    """Refuse a too-old field-app build; stamp the schema version on every field response."""

    def __init__(self, get_response: Callable[[Any], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: Any) -> HttpResponse:
        rest = field_route(request.path_info)
        if rest is None:
            return self.get_response(request)

        response: HttpResponse | None = None
        sent = request.headers.get(VERSION_HEADER)
        if sent is not None and not sends_captured_work(request.method, rest):
            minimum = minimum_version()
            if parse_version(sent) < parse_version(minimum):
                response = too_old_refusal(sent.strip(), minimum)
        if response is None:
            # FB-014 (DEF-FLD-10639) — the phone's clock, measured once for the
            # whole request; every phone-stamped time is shifted by it
            # (`core/device_clock.py`). Never a refusal.
            with device_clock.measured(request.headers.get(device_clock.DEVICE_TIME_HEADER)):
                response = self.get_response(request)
        response[SCHEMA_HEADER] = str(FIELD_SCHEMA_VERSION)
        # …and the server's own, so the phone can measure the difference and
        # warn the technician (FF-50) without waiting for a sync answer.
        response[device_clock.SERVER_TIME_HEADER] = device_clock.server_time_header()
        return response
