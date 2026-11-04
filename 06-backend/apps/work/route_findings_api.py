# ── Trace ──────────────────────────────────────────────
# Change:   CR-187-BRC10 lane FINDINGS — the routes for a route finding
#           (`BR-WRK-067`): the office's list and its *Create work order…*,
#           and the reader's own finding and *Create work order* on the phone.
#           The finding itself ARRIVES through the reads door
#           (`POST work/mobile/reads/sync`, kind `finding`).
# Rules:    `07-endpoints.md` §0 — rule 1 additive only · rule 3 (the tenant
#           from the path and the session) · rule 7 (a repeat changes nothing)
#           · rule 9 (paged, no cap) · rule 10 (a technician sees only their
#           own: 404, never 403) · hard rule 1
# Tests:    06-backend/tests/test_cr187_route_findings.py
# Impacts:  apps/work/api.py (`urlpatterns += …`, one line)
# ───────────────────────────────────────────────────────
"""Route findings, as routes — in their own file for `field_orders_api.py`'s
reason: `apps/work/api.py` is shared by several lanes, so a merge touches one
line there rather than eighty."""

from __future__ import annotations

from typing import Any

from django.urls import path
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.work import route_findings
from apps.work.api import _actor, _envelope, _payload
from core.pagination import parse_list_params
from core.permissions import AnyTenantRole, FieldAppRole, WorkOrdersReadAnyWriteAdminOrClerk
from core.tenancy import require_tenant


# ── mobile ────────────────────────────────────────────────────────────────
@api_view(["GET"])
@permission_classes([FieldAppRole])
def mobile_finding_options(request: Any) -> Response:
    """`GET /work/mobile/findings/options` — RW-21's kinds and urgencies, and
    the priorities *Create work order* offers."""
    require_tenant(request)
    return Response(route_findings.finding_options())


@api_view(["GET"])
@permission_classes([FieldAppRole])
def mobile_finding(request: Any, key: str) -> Response:
    """`GET /work/mobile/findings/{key}` — the caller's own finding, by the
    key minted at capture: open, or the job it became."""
    require_tenant(request)
    return Response(route_findings.mobile_finding(_actor(request), key))


@api_view(["POST"])
@permission_classes([FieldAppRole])
def mobile_finding_work_order(request: Any, key: str) -> Response:
    """`POST /work/mobile/findings/{key}/work-order` — `{template_id,
    priority_id?}`. 201 with the job; 200 `duplicate: true` when the finding
    already has one (by rule or by an earlier press)."""
    require_tenant(request)
    answer = route_findings.mobile_create(_actor(request), key, _payload(request))
    return Response(answer, status=200 if answer.get("duplicate") else 201)


# ── office ────────────────────────────────────────────────────────────────
@api_view(["GET"])
@permission_classes([AnyTenantRole])
def office_findings(request: Any) -> Response:
    """`GET /work/route-findings?status=open|work_order_created|all&page=` —
    newest first; `counts` over every status."""
    require_tenant(request)
    params = parse_list_params(request.query_params, allowed_sorts=(), default_sort=None)
    result = route_findings.office_page(
        status=request.query_params.get("status"), page=params.page, per=params.per
    )
    return Response({**_envelope(request, result), "counts": result["counts"]})


@api_view(["POST"])
@permission_classes([WorkOrdersReadAnyWriteAdminOrClerk])
def office_finding_work_order(request: Any, finding_id: Any) -> Response:
    """`POST /work/route-findings/{id}/work-order` — `{template_id,
    priority_id?}`: the office's *Create work order…*. Once per finding."""
    require_tenant(request)
    answer = route_findings.office_create(_actor(request), finding_id, _payload(request))
    return Response(answer, status=200 if answer.get("duplicate") else 201)


urlpatterns = [
    path("work/mobile/findings/options", mobile_finding_options, name="mobile_finding_options"),
    path("work/mobile/findings/<str:key>", mobile_finding, name="mobile_finding"),
    path(
        "work/mobile/findings/<str:key>/work-order",
        mobile_finding_work_order,
        name="mobile_finding_work_order",
    ),
    path("work/route-findings", office_findings, name="work_route_findings"),
    path(
        "work/route-findings/<uuid:finding_id>/work-order",
        office_finding_work_order,
        name="work_route_finding_work_order",
    ),
]
