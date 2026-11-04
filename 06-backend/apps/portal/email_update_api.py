# ── Trace ──────────────────────────────────────────────
# Change:   CR-189-BRC10 — the five anonymous routes behind
#           `/{tenant}/portal/update-email` (CWP-019U).
# Rules:    decision log 2026-10-22 (CR-189 entries) · BR-CWP-023 · BR-CWP-030 ·
#           BR-CWP-033 · BR-CWP-034 · BR-CWP-047 (no-store) · NFR-39 (the same
#           per-address and per-tenant throttles every guest door wears)
# Tests:    06-backend/tests/test_cr189_portal_update_email.py
# Impacts:  config/urls.py (one include) · apps/portal/email_update.py
# ───────────────────────────────────────────────────────
"""`POST /api/{tenant}/portal/update-email/…` — thin edges over `email_update`.

Its own URLconf so this change stays out of `api.py`, which two sibling lanes
are editing the same day (CLAUDE.md law 11). Each view reads the body, calls
one function and returns its dict. Nothing here decides anything; the rules and
their reasons are in `email_update.py`.

Every route is anonymous, so each wears the enrolment routes' throttles and
the connection budget, and every answer is `no-store`.
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

from apps.portal import email_update, lockout
from apps.portal import session as portal_session
from apps.portal.guards import PortalSignedInThrottle, PortalTenantThrottle, portal_admission
from apps.tenancy.api import PublicOnboardingThrottle
from core.tenancy import require_tenant


def _body(request: Any) -> dict[str, Any]:
    return request.data if isinstance(request.data, dict) else {}


def _answer(payload: dict[str, Any]) -> Response:
    response = Response(payload)
    response["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
    return response


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([PublicOnboardingThrottle, PortalTenantThrottle])
@portal_admission
def find(request: Any) -> Response:
    """Step 1 — the three bill facts. `matched` + masked options, or a refusal."""
    tenant_id = require_tenant(request)
    body = _body(request)
    return _answer(
        email_update.find(
            tenant_id,
            address=lockout.address_of(request),
            account_no=body.get("account_number"),
            postcode=body.get("postcode"),
            name=body.get("last_name"),
        )
    )


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([PublicOnboardingThrottle, PortalTenantThrottle])
@portal_admission
def send_code(request: Any) -> Response:
    """Step 2 — a code to the ONE contact on file the person picked."""
    tenant_id = require_tenant(request)
    body = _body(request)
    return _answer(
        email_update.send_code(tenant_id, ref=body.get("ref"), option_key=body.get("option"))
    )


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([PublicOnboardingThrottle, PortalTenantThrottle])
@portal_admission
def verify_code(request: Any) -> Response:
    """Step 3 — `ok`, `wrong`, `expired` or `locked`."""
    tenant_id = require_tenant(request)
    body = _body(request)
    return _answer(email_update.verify_code(tenant_id, ref=body.get("ref"), code=body.get("code")))


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([PublicOnboardingThrottle, PortalTenantThrottle])
@portal_admission
def new_email(request: Any) -> Response:
    """Step 4 — a confirmation code to the NEW address (the same answer always)."""
    tenant_id = require_tenant(request)
    body = _body(request)
    return _answer(
        email_update.start_confirmation(tenant_id, ref=body.get("ref"), email=body.get("email"))
    )


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([PublicOnboardingThrottle, PortalTenantThrottle])
@portal_admission
def confirm(request: Any) -> Response:
    """Step 5 — the change itself, the notice to the old address, the reset link."""
    tenant_id = require_tenant(request)
    body = _body(request)
    return _answer(
        email_update.confirm(
            tenant_id, ref=body.get("ref"), code=body.get("code"), email=body.get("email")
        )
    )


# ── The SIGNED-IN change (PO 2026-10-22, Q2 option A; DEF-CWP-10401) ────────
# A code to the NEW address, then the contact email and the sign-in email move
# together. The session decides whose login and which accounts; the body names
# only the address and the code.


@api_view(["POST"])
@authentication_classes([portal_session.PortalSessionAuthentication])
@permission_classes([portal_session.IsPortalCustomer])
@throttle_classes([PortalSignedInThrottle])
@portal_admission
def signed_in_start(request: Any) -> Response:
    """`POST my-details/email/start` — a code to the address typed."""
    return _answer(
        email_update.start_signed_in_change(request.user, email=_body(request).get("email"))
    )


@api_view(["POST"])
@authentication_classes([portal_session.PortalSessionAuthentication])
@permission_classes([portal_session.IsPortalCustomer])
@throttle_classes([PortalSignedInThrottle])
@portal_admission
def signed_in_confirm(request: Any) -> Response:
    """`POST my-details/email/confirm` — the code back; both addresses move."""
    body = _body(request)
    return _answer(
        email_update.confirm_signed_in_change(
            request.user, ref=body.get("ref"), code=body.get("code"), email=body.get("email")
        )
    )


urlpatterns = [
    path("portal/my-details/email/start", signed_in_start),
    path("portal/my-details/email/confirm", signed_in_confirm),
    path("portal/update-email/find", find),
    path("portal/update-email/send-code", send_code),
    path("portal/update-email/verify-code", verify_code),
    path("portal/update-email/new-email", new_email),
    path("portal/update-email/confirm", confirm),
]
