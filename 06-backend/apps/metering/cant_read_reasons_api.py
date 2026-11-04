# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-MET-10609 — Settings → Reference data → Readings → Can't-read
#           reasons (decision log 2026-10-26, PO *"yes do it"*).
# Rules:    NFR-3 (paged by the server) · BR-SHL-025 (A4: Settings Full =
#           System Admin, View = Executive; the SERVICE's @require_role refuses
#           an Executive's write)
# Tests:    06-backend/tests/test_def_met_10609_cant_read_reasons.py
# Impacts:  apps/metering/api.py (`urlpatterns += cant_read_reasons_api.urlpatterns`)
# ───────────────────────────────────────────────────────
"""The can't-read reason routes — THIN by law (B8): every write is a service call.

    GET    settings/cant-read-reasons?q=&status=&page=&per=   the list (incl. off)
    POST   settings/cant-read-reasons                         add `{name}`
    PATCH  settings/cant-read-reasons/{code}                  `{name?, active?}`
    DELETE settings/cant-read-reasons/{code}                  never-used own reason
    POST   settings/cant-read-reasons/{code}/move             `{direction: up|down}`
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from django.urls import path
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.metering import cant_read_reasons
from core.pagination import StandardPagination
from core.permissions import AdminOrExecutive
from core.tenancy import require_tenant


def _actor(request: Any) -> Any:
    """Id from the session, role server-attached — never client input."""
    user = getattr(request, "user", None)
    return SimpleNamespace(
        id=getattr(user, "id", None) or getattr(user, "pk", None),
        role=getattr(request, "tenant_role", None),
    )


@api_view(["GET", "POST"])
@permission_classes([AdminOrExecutive])
def reasons(request: Any) -> Response:
    require_tenant(request)
    if request.method == "POST":
        return Response(cant_read_reasons.add_reason(_actor(request), request.data), status=201)
    q = request.query_params
    rows = cant_read_reasons.reasons_queryset(q=q.get("q"), status=q.get("status"))
    paginator = StandardPagination()
    page = list(paginator.paginate_queryset(rows, request) or [])
    return paginator.get_paginated_response(cant_read_reasons.page_rows(page))


@api_view(["PATCH", "DELETE"])
@permission_classes([AdminOrExecutive])
def reason_detail(request: Any, code: str) -> Response:
    require_tenant(request)
    if request.method == "DELETE":
        return Response(cant_read_reasons.delete_reason(_actor(request), code))
    return Response(cant_read_reasons.update_reason(_actor(request), code, request.data))


@api_view(["POST"])
@permission_classes([AdminOrExecutive])
def reason_move(request: Any, code: str) -> Response:
    require_tenant(request)
    return Response(cant_read_reasons.move_reason(_actor(request), code, request.data))


urlpatterns = [
    path("settings/cant-read-reasons", reasons),
    path("settings/cant-read-reasons/<str:code>", reason_detail),
    path("settings/cant-read-reasons/<str:code>/move", reason_move),
]


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-MET-10609
# generated: 2026-10-26 by the DEF-MET-10609 lane
