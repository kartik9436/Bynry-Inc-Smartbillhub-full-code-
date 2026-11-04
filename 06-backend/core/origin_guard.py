# ── Trace ──────────────────────────────────────────────
# HUMAN-REVIEW-PENDING — 🔒 sensitive path (MIDDLEWARE ORDER; this refuses
# requests before any view or permission class runs). Row in
# 12-governance/09-human-review-ledger.md (CR-144-BRC07).
#
# Change:   CR-144-BRC07 (X2) — ECS Fargate behind an Application Load Balancer,
#           SPA on a separate host.
# Rules:    decision log 2026-09-28 ruling 1 (two hosts: `app[-env].bynry.com`
#           and `api-smart360[-env].bynry.com`) · hard-won law 3 (defaults fail
#           closed) · hard-won law 7 (a check that cannot fail is worse than no
#           check — the blind spot below is stated with a reason, not hidden)
# Tests:    tests/test_cr144_cors_and_origin.py
# Impacts:  every state-changing API call in the product.
# ───────────────────────────────────────────────────────
"""Refuse a state-changing request whose `Origin` is not our own front end.

WHY THIS EXISTS ON TOP OF CORS — AND IT IS THE SUBTLE ONE
=========================================================
Three facts, each innocent, which together are a cross-site request forgery:

1. **`app-dev.bynry.com` and `api-smart360-dev.bynry.com` are the SAME SITE.**
   "Site" for a cookie means the registrable domain — `bynry.com` — not the
   host. So `SameSite=Lax` does **not** separate them, and a session cookie
   rides along from **any** `*.bynry.com` page to the API.
2. **DRF's default parsers accept form posts.** A plain HTML `<form method=post>`
   is not a "simple request" the browser asks permission for; the browser just
   sends it.
3. **The session authenticator has no CSRF check.** `IdentitySessionAuthentication`
   is a custom cookie class — DRF only enforces CSRF for its own
   `SessionAuthentication`.

**CORS does not close this.** CORS governs what a browser is willing to SHOW a
script; it never stops the request being SENT. A form POST from a page on
another `bynry.com` host arrives at the API with a valid session cookie, does
the write, and the browser merely hides the response from the attacker. The
damage is already done — hiding the receipt is not a defence.

So the check is server-side, before any view runs.

WHAT IT CHECKS, AND THE BLIND SPOT NAMED OUT LOUD
=================================================
A state-changing method (`POST`, `PUT`, `PATCH`, `DELETE`) **carrying an
`Origin` header** must carry one we allow. A browser sends `Origin` on every
one of these, cross-site or not, so for a browser this is complete.

⚠ **A REQUEST WITH NO `Origin` HEADER AT ALL IS ALLOWED THROUGH, AND THAT IS A
DECISION RATHER THAN AN OVERSIGHT** (law 7: a check must say what it does not
cover). `curl`, the partner surface at `/api/partner/v1/…`, inbound payment
webhooks and every server-to-server caller send no `Origin`, and none of them
is reachable from a browser's cookie jar. Refusing them would break the
integrations this product sells and would defend nothing: the attack this
module exists for **requires** a browser, and a browser always sends the header.
The forgery risk that remains is a client that can set arbitrary headers — and
such a client can set the cookie directly and never needed the victim at all.

⚠ **AND THIS IS DEFENCE IN DEPTH, NOT THE ONLY LOCK.** `SameSite=Lax` still
blocks a top-level cross-SITE form post from outside `bynry.com`. This guard is
what covers the inside of our own registrable domain, which `Lax` cannot see.

WHAT IT DOES NOT DO
===================
It does not touch `GET`, `HEAD` or `OPTIONS`. `OPTIONS` in particular is the
CORS preflight and must reach `CorsMiddleware` to be answered; refusing it here
would make every cross-origin call fail with a preflight error and the cause
would read as a CORS misconfiguration.

The health probe never reaches this module — `core.health.HealthCheckMiddleware`
answers first — and it only ever sees `GET`/`HEAD` anyway.

⚠ **THE REFUSAL BODY IS UNREACHABLE BY ANY BROWSER, WHICH IS WHY IT CARRIES NO
CATALOGUE ENTRY.** The only caller that can trigger it is cross-origin, so the
browser hides this response from the script that provoked it. It uses the
envelope shape every other refusal uses so a developer reading a log sees the
familiar fields; the `message_key` is deliberately NOT added to the eleven
locale catalogues, because a string no clerk can ever see is a string that will
rot unread. Stated here rather than left to be discovered.
"""

from __future__ import annotations

import json
from collections.abc import Callable

from django.conf import settings
from django.http import HttpRequest, HttpResponse

from core import errors

#: Methods that can change state. `GET`/`HEAD` are excluded because they must
#: not change state in the first place, and `OPTIONS` because it is the CORS
#: preflight and has to reach `CorsMiddleware`.
STATE_CHANGING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def _allowed_origins() -> frozenset[str]:
    """The exact origins this API will act for.

    ⚠ **EXACT STRINGS, NEVER A SUFFIX MATCH.** A `endswith(".bynry.com")` test
    is the bug this module exists to close, not a shortcut to it.
    """
    return frozenset(getattr(settings, "ORIGIN_GUARD_ALLOWED_ORIGINS", []) or [])


def _own_origin(request: HttpRequest) -> str | None:
    """This API's own origin, so a same-origin tool (the DRF browsable API, the
    OpenAPI UI) is not refused by its own server. `get_host()` has already been
    validated against `ALLOWED_HOSTS` by the time any middleware after the host
    check sees it, so this cannot be spoofed into allowing an outside origin."""
    try:
        host = request.get_host()
    except Exception:  # SuspiciousOperation — the host check will refuse it anyway
        return None
    return f"{request.scheme}://{host}"


class OriginGuardMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if request.method in STATE_CHANGING_METHODS:
            origin = request.headers.get("Origin")
            if origin:
                permitted = set(_allowed_origins())
                own = _own_origin(request)
                if own:
                    permitted.add(own)
                if origin not in permitted:
                    return self._refuse(origin)
        return self.get_response(request)

    @staticmethod
    def _refuse(origin: str) -> HttpResponse:
        body = errors.http_series_refusal_body(
            "errors.cross-origin-refused",
            br_ref="CR-144-BRC07",
            origin=origin,
        )
        return HttpResponse(
            json.dumps(body).encode("utf-8"),
            status=403,
            content_type="application/json",
        )
