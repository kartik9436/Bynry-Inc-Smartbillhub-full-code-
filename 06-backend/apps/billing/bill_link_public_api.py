# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-BIL-10531 — the bill email's direct PDF link (PO 2026-10-22,
#           *"b direct PDF link"*)
# Rules:    NFR-39 (the guest throttles: per address AND per tenant, and the
#           connection budget) · BR-TEN-003 (the tenant comes from the path) ·
#           CLAUDE.md hard rule 1 · decision log 2026-10-22 *"One-time link
#           secrets travel in the URL FRAGMENT"* (the secret is POSTed in the
#           BODY; no route here takes it in the address) · enumeration safety
#           (ONE answer for every link that does not open)
# Tests:    06-backend/tests/test_def_bil_10531_bill_link.py
# Impacts:  config/urls.py · 07-frontend/src/portal/bill-link/
# ───────────────────────────────────────────────────────
"""THE BILL LINK'S EDGE — unauthenticated, throttled, and owned by billing.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — an unauthenticated door that hands out a
bill. AI-authored 2026-10-22; row in `12-governance/09-human-review-ledger.md`.

    POST  /api/{tenant}/bill-links/open       {"token"} → the page's facts
    POST  /api/{tenant}/bill-links/document   {"token"} → the kept PDF

⚠ **POST, AND THE TOKEN IN THE BODY — NEVER IN THE PATH OR THE QUERY.** The
agreement link's door (`customers/agreement_public_api.py`) carries its token
in the path, where every web server, proxy and CDN logs it. This door is the
fragment ruling's shape: the page reads the secret from after `#` and sends it
here in a JSON body, so no logged address ever holds it.

⚠ **NO AUTHENTICATION, ON PURPOSE** — `authentication_classes([])`: a stale
staff or portal cookie must neither 401 the customer nor enter any context. The
token IS the capability. It wears the portal's GUEST guards exactly, as the
agreement door does, because it faces the same strangers.

⚠ **ONE ANSWER FOR EVERY LINK THAT DOES NOT OPEN** — `200 {"state":
"unavailable", "support_phone": …}`, the utility's own public number.
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

from apps.billing import bill_link_seam, bill_links
from core.document_response import document_http_response
from core.tenancy import require_tenant

_THROTTLES, _admission = bill_link_seam.guest_guards()


def _no_store(response: Any) -> Any:
    response["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
    response["Referrer-Policy"] = "no-referrer"
    return response


def _token(request: Any) -> Any:
    body = request.data if isinstance(request.data, dict) else {}
    return body.get("token")


def _unavailable() -> Response:
    return _no_store(Response(bill_links.public_unavailable()))


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes(_THROTTLES)
@_admission
def bill_link_open(request: Any) -> Response:
    require_tenant(request)
    try:
        view = bill_links.public_view(_token(request))
    except bill_links.LinkUnavailable:
        return _unavailable()
    return _no_store(Response({"state": "open", **view}))


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes(_THROTTLES)
@_admission
def bill_link_document(request: Any) -> Any:
    require_tenant(request)
    try:
        payload, name = bill_links.public_document(_token(request))
    except bill_links.LinkUnavailable:
        return _unavailable()
    return _no_store(
        document_http_response(
            payload=payload, content_type="application/pdf", name=name, inline=False
        )
    )


urlpatterns = [
    path("bill-links/open", bill_link_open),
    path("bill-links/document", bill_link_document),
]
