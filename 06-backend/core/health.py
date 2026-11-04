# ── Trace ──────────────────────────────────────────────
# HUMAN-REVIEW-PENDING — 🔒 sensitive path (MIDDLEWARE ORDER). This module is
# the FIRST entry of config/settings/base.py MIDDLEWARE, so it runs ahead of
# SecurityMiddleware, CommonMiddleware and TenantContextMiddleware. Row in
# 12-governance/09-human-review-ledger.md (CR-144-BRC07).
#
# Change:   CR-144-BRC07 — ECS Fargate behind an Application Load Balancer.
#           Tasks H1 and H2.
# Rules:    decision log 2026-09-28, ruling 2 (verbatim): the health path is
#           `/api/health`, NOT `/api/smart360/health/` — every `/api/<segment>/`
#           is read as a customer slug by core/tenancy.py, so a health path
#           shaped like one would ask for a utility called `smart360`. It must
#           need no sign-in, and it is answered by MIDDLEWARE PLACED FIRST.
# Tests:    tests/test_health.py (proved RED before this file existed — 400 on
#           the private-IP host, 301 through the HTTPS redirect)
# Impacts:  every deployed environment. This answer decides whether an ECS task
#           is allowed to serve traffic at all.
# ───────────────────────────────────────────────────────
"""The load balancer's probe: `200 {"status":"ok"}`, and nothing else.

WHY MIDDLEWARE AND NOT A VIEW — THIS IS NOT A STYLE CHOICE
==========================================================
The Application Load Balancer addresses the ECS task by its **private IP**, so
the health request arrives with `Host: 10.0.1.23`. `ALLOWED_HOSTS` carries the
public API name (`api-smart360.bynry.com`) and does not — must not — carry an
address that changes with every task placement. Django's host validation runs
in `HttpRequest.get_host()`, long before any URL is resolved, so it answers
**400 and a health VIEW is never reached**, whatever it is mounted on.

Measured before this file was written, with the test that now guards it:

    AssertionError: 400 for Host: 10.0.1.23 — Django refused the balancer's own
    address before the probe could answer

The same case, one line down, is the HTTPS redirect:

    AssertionError: 301 — the probe was redirected instead of answered

`SECURE_SSL_REDIRECT` is set by `SecurityMiddleware`, and the balancer speaks
**plain HTTP to port 8000**. A 301 is not a 200, so every task would fail its
check and be replaced, forever. That is why this middleware must stay ahead of
`SecurityMiddleware` as well as ahead of the host check.

WHY IT IS SHALLOW ON PURPOSE
============================
**No database. No Redis. No session.** A probe that queries the database turns
a slow database into *no service at all*: every task fails its check, every
task is replaced, and the outage is manufactured by the monitoring rather than
reported by it. This answer says one thing — *this Python process is accepting
and answering HTTP* — and that is the only thing a load balancer's target
health is allowed to mean.

⚠ **SO IT IS NOT A READINESS CHECK AND NOTHING MAY LATER MAKE IT ONE**
(hard-won law 1 — the comment is not the guarantee, so there is a test):
`tests/test_health.py::test_health_answers_with_the_database_unreachable`
makes every connection attempt raise and still demands a 200. An edit that
adds so much as a `SELECT 1` goes red there rather than in production.

THE TWO SPELLINGS
=================
`/api/health` **and** `/api/health/`. `CommonMiddleware`'s `APPEND_SLASH` runs
*after* this one and would never see the request, so a balancer configured with
either spelling must work. Answering both here costs one tuple membership test
and removes an entire class of "the target group says unhealthy and the app is
fine" incident.

⚠ **`health` IS ALREADY RESERVED AND WAS BEFORE THIS FILE** — `NON_TENANT_SEGMENTS`
in `core/tenancy.py` and `RESERVED_SUBDOMAINS` in `apps/tenancy/selectors.py`,
with `test_be01_tc16` asserting the second is a superset of the first. So no
customer can ever be named `health` and shadow this path. `core/tenancy.py`
carried the comment *"health — the load-balancer probe (09-infra; no Django
route yet)"*: the reservation was made and the route never was, until now. That
comment is amended in the same commit as this file.
"""

from __future__ import annotations

import json
from collections.abc import Callable

from django.http import HttpRequest, HttpResponse

#: Both spellings, because `APPEND_SLASH` runs later in the chain and this
#: middleware returns before it.
HEALTH_PATHS = frozenset({"/api/health", "/api/health/"})

#: The only methods a load-balancer probe uses. Everything else is refused, so
#: this path can never become an accidental write surface sitting in front of
#: every guard in the product.
HEALTH_METHODS = frozenset({"GET", "HEAD"})

_BODY = json.dumps({"status": "ok"}).encode("utf-8")


class HealthCheckMiddleware:
    """Answers `/api/health` before Django validates anything about the request.

    ⚠ **IT IS FIRST IN THE CHAIN, WHICH MAKES A BUG HERE A PRODUCT-WIDE
    OUTAGE.** Everything that is not one of the two health paths is passed
    straight on, untouched, on the same line it arrived. There is deliberately
    no configuration, no regular expression and no prefix match:
    `tests/test_health.py::test_health_does_not_swallow_other_paths` holds that
    shut.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        #: `request.path` is decoded from `PATH_INFO` and needs no host, no
        #: session and no database — which is the whole point of being here.
        if request.path not in HEALTH_PATHS:
            return self.get_response(request)

        if request.method not in HEALTH_METHODS:
            response = HttpResponse(status=405, content_type="application/json")
            response["Allow"] = "GET, HEAD"
            return response

        response = HttpResponse(_BODY, content_type="application/json")
        #: A probe answer is never cached — by the balancer, by a proxy, or by
        #: anything else that might later sit in front of it.
        response["Cache-Control"] = "no-store"
        if request.method == "HEAD":
            #: `CommonMiddleware` normally strips a HEAD body and it runs after
            #: this one, so it is stripped here instead.
            response.content = b""
        return response
