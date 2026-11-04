# ── Trace ──────────────────────────────────────────────
# Change:   CR-183-BRC10 — temporary stop (PO rulings B1–B4, 2026-10-14).
# Rules:    BR-CUS-1120 · BR-CUS-1121 · BR-SHL-025 (the role is checked by the
#           service, `@require_role`, whatever the door)
# Tests:    06-backend/tests/test_cr183_temporary_stop.py
# ───────────────────────────────────────────────────────
"""The staff doors onto `temporary_stop` — thin: parse, call, answer.

    POST  service-requests/{id}/temporary-stop/approve   approve the ask (T3)
    GET   accounts/{id}/temporary-stop                   the account's card (T7)
    POST  accounts/{id}/temporary-stop                   start one at the counter (T7)
    PATCH temporary-stops/{id}                           move its dates (T7)
    POST  temporary-stops/{id}/end                       end it today (T7)

Every rule lives in `temporary_stop.py`; this file holds none.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from django.urls import path
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.customers import service_request_reads as reads
from apps.customers import temporary_stop
from core import errors
from core.permissions import AdminOrClerk
from core.tenancy import require_tenant


def _actor(request: Any) -> Any:
    """B12 §6a — id from the session user, ROLE server-attached (BE-04)."""
    user = getattr(request, "user", None)
    return SimpleNamespace(
        id=getattr(user, "id", None) or getattr(user, "pk", None),
        role=getattr(request, "tenant_role", None),
        user=user,
    )


def _payload(request: Any) -> dict[str, Any]:
    data = request.data
    if not isinstance(data, dict):
        raise errors.ValidationError(errors.VAL_FORMAT, message_key="customers.payload_not_object")
    return data


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def approve(request: Any, request_id: str) -> Response:
    """Approve a *Temporary stop* or *Restart now* request. Dates may be sent
    (the clerk agreed different ones); `field_visit_needed` must be a literal
    `true` to count, so a string `"false"` is never read as a yes."""
    require_tenant(request)
    body = _payload(request)
    answer = temporary_stop.approve_request(
        _actor(request),
        request_id,
        stop_from=body.get("stop_from"),
        restart_on=body.get("restart_on"),
        field_visit_needed=body.get("field_visit_needed") is True,
        note=body.get("note"),
    )
    return Response({**reads.detail(request_id), "temporary_stop_result": answer})


@api_view(["GET", "POST"])
@permission_classes([AdminOrClerk])
def account_stop(request: Any, account_id: str) -> Response:
    require_tenant(request)
    if request.method == "GET":
        return Response(temporary_stop.for_account(account_id))
    body = _payload(request)
    answer = temporary_stop.start_from_account(
        _actor(request),
        account_id,
        stop_from=body.get("stop_from"),
        restart_on=body.get("restart_on"),
        reason=body.get("reason"),
        field_visit_needed=body.get("field_visit_needed") is True,
    )
    return Response({**temporary_stop.for_account(account_id), "warnings": answer["warnings"]}, status=201)


@api_view(["PATCH"])
@permission_classes([AdminOrClerk])
def stop_item(request: Any, stop_id: str) -> Response:
    require_tenant(request)
    body = _payload(request)
    answer = temporary_stop.change_dates(
        _actor(request), stop_id, stop_from=body.get("stop_from"), restart_on=body.get("restart_on")
    )
    return Response(answer)


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def stop_end(request: Any, stop_id: str) -> Response:
    require_tenant(request)
    return Response(temporary_stop.end_now(_actor(request), stop_id))


urlpatterns = [
    path("service-requests/<str:request_id>/temporary-stop/approve", approve),
    path("accounts/<uuid:account_id>/temporary-stop", account_stop),
    path("temporary-stops/<uuid:stop_id>", stop_item),
    path("temporary-stops/<uuid:stop_id>/end", stop_end),
]
