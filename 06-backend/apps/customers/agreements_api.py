"""The staff doors onto click-to-accept agreements (CR-190-BRC10) — thin.

    GET   accounts/{id}/agreements                      Sent / Accepted / Expired
    POST  accounts/{id}/agreements                      send one (any Contracts template)
    POST  accounts/{id}/agreements/{requestId}/resend   a new link; the old one voided

Every rule lives in `agreements.py`; this file holds none. Reading is any
tenant role (an Executive views an account); sending is Admin or Clerk.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from django.urls import path
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.customers import agreements
from core import errors
from core.permissions import AdminOrClerk, AnyTenantRole
from core.tenancy import require_tenant


def _actor(request: Any) -> Any:
    user = getattr(request, "user", None)
    return SimpleNamespace(
        id=getattr(user, "id", None) or getattr(user, "pk", None),
        role=getattr(request, "tenant_role", None),
        user=user,
    )


def _refused(refusal: agreements.AgreementRefused) -> errors.BizError:
    return errors.BizError(
        errors.BIZ_STATE,
        br_ref="CR-190-BRC10",
        message_key=refusal.message_key,
        params={"code": refusal.code},
    )


@api_view(["GET", "POST"])
@permission_classes([AnyTenantRole])
def account_agreements(request: Any, account_id: str) -> Response:
    require_tenant(request)
    if request.method == "POST":
        if not AdminOrClerk().has_permission(request, None):
            raise errors.AuthError(errors.AUTH_PERMISSION_DENIED, br_ref="BR-IDN-009")
        body = request.data if isinstance(request.data, dict) else {}
        try:
            result = agreements.issue(
                _actor(request), account_id, str(body.get("template_code") or "")
            )
        except agreements.AgreementRefused as refusal:
            raise _refused(refusal) from None
        return Response(result["request"], status=201)
    return Response({"results": agreements.requests_for_account(account_id)})


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def resend_agreement(request: Any, account_id: str, request_id: str) -> Response:
    require_tenant(request)
    try:
        result = agreements.resend(_actor(request), account_id, request_id)
    except agreements.AgreementRefused as refusal:
        raise _refused(refusal) from None
    return Response(result["request"], status=201)


urlpatterns = [
    path("accounts/<uuid:account_id>/agreements", account_agreements),
    path("accounts/<uuid:account_id>/agreements/<uuid:request_id>/resend", resend_agreement),
]
