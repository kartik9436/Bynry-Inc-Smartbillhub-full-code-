# ── Trace ──────────────────────────────────────────────
# Change:   CR-190-BRC10 lane AGREEMENT — the public acceptance page's three
#           doors (PO 2026-10-22: *"direct customer to screen where weshow them
#           the aggrement and customer can check a box and put a date and they
#           can submit"*; answer 4, *"No"* to accepting inside the portal)
# Rules:    NFR-39 (the guest throttles: per address AND per tenant, and the
#           connection budget) · BR-TEN-003 (the tenant comes from the path) ·
#           CLAUDE.md hard rule 1 · enumeration safety (ONE answer for every
#           link that does not open)
# Tests:    06-backend/tests/test_cr190_agreements.py
# Impacts:  config/urls.py · 07-frontend/src/portal/agreements/
# ───────────────────────────────────────────────────────
"""THE AGREEMENT LINK'S EDGE — unauthenticated, throttled, and owned by customers.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — an unauthenticated door that WRITES (the
acceptance). AI-authored 2026-10-22; row in `12-governance/09-human-review-
ledger.md`.

    GET   /api/{tenant}/agreements/public/{token}            the page's facts
    GET   /api/{tenant}/agreements/public/{token}/document   the PDF as sent
    POST  /api/{tenant}/agreements/public/{token}/accept     tick + date + name

⚠ **WHY THIS IS NOT IN `apps/portal`.** The acceptance is a write to an
account's agreement (customers' table), and the portal surface may write in its
seven declared places only (`portal/write_points.py`, G81). The PO ruled the
link is NOT part of the signed-in portal (answer 4), so it is not a portal write
point either: it is the customers module's own door, reached by a link. It
wears the portal's GUEST guards exactly (`PublicOnboardingThrottle`,
`PortalTenantThrottle`, `portal_admission`) because it faces the same strangers.

⚠ **NO AUTHENTICATION, ON PURPOSE** — `authentication_classes([])`: a stale
staff or portal cookie must neither 401 the customer nor enter any context. The
token IS the capability; nothing else is read before it matches.

⚠ **ONE ANSWER FOR EVERY LINK THAT DOES NOT OPEN.** Unknown, used, expired and
voided all answer `200 {"state": "unavailable", "support_phone": …}` — the
utility's own number, which is public on its front page anyway. A 404 for one
and a 410 for another would tell a stranger which tokens once existed.
"""

from __future__ import annotations

from typing import Any

from django.urls import path
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
    throttle_classes,
)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.customers import agreements
from apps.portal.guards import PortalTenantThrottle, portal_admission
from apps.tenancy.api import PublicOnboardingThrottle
from core.document_response import document_http_response
from core.tenancy import require_tenant


def _no_store(response: Any) -> Any:
    response["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
    response["Referrer-Policy"] = "no-referrer"  # the token never leaves in a Referer
    return response


def _unavailable() -> Response:
    return _no_store(Response(agreements.public_unavailable()))


def _client_ip(request: Any) -> str | None:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip() or None
    return request.META.get("REMOTE_ADDR") or None


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([PublicOnboardingThrottle, PortalTenantThrottle])
@portal_admission
def agreement_page(request: Any, token: str) -> Response:
    require_tenant(request)
    try:
        view = agreements.public_view(token)
    except agreements.LinkUnavailable:
        return _unavailable()
    return _no_store(Response({"state": "open", **view}))


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([PublicOnboardingThrottle, PortalTenantThrottle])
@portal_admission
def agreement_document(request: Any, token: str) -> Any:
    require_tenant(request)
    try:
        payload, name = agreements.public_document(token)
    except agreements.LinkUnavailable:
        return _unavailable()
    return _no_store(
        document_http_response(
            payload=payload, content_type="application/pdf", name=name, inline=False
        )
    )


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([PublicOnboardingThrottle, PortalTenantThrottle])
@portal_admission
def agreement_accept(request: Any, token: str) -> Response:
    require_tenant(request)
    body = request.data if isinstance(request.data, dict) else {}
    try:
        answer = agreements.accept(
            token,
            agreed=body.get("agreed"),
            accepted_date=body.get("date"),
            typed_name=body.get("name"),
            ip=_client_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT"),
        )
    except agreements.LinkUnavailable:
        return _unavailable()
    return _no_store(Response(answer))


urlpatterns = [
    path("agreements/public/<str:token>", agreement_page),
    path("agreements/public/<str:token>/document", agreement_document),
    path("agreements/public/<str:token>/accept", agreement_accept),
]
