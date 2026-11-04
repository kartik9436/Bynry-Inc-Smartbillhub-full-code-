# ── Trace ──────────────────────────────────────────────
# Change:   CR-194-BRC10 — the office's routes for refused field work (PO
#           2026-10-26, *"store on both"*): list, detail, Mark reviewed, Apply
#           to the job. The copies ARRIVE through the two sync doors.
# Rules:    `07-endpoints.md` §0 — rule 1 additive only · rule 3 (the tenant
#           from the path and the session) · rule 9 (paged, no cap) · hard
#           rules 1 and 7 · BR-WRK-071
# Tests:    06-backend/tests/test_cr194_refused_field_work.py
# Impacts:  apps/work/api.py (`urlpatterns += …`, one line)
# ───────────────────────────────────────────────────────
"""Refused field work, as routes — in their own file for `field_orders_api.py`'s
reason: `apps/work/api.py` is shared by several lanes, so a merge touches one
line there rather than sixty."""

from __future__ import annotations

from typing import Any

from django.urls import path
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.work import refused_items
from apps.work.api import _actor, _envelope, _payload
from core.pagination import parse_list_params
from core.permissions import AnyTenantRole, WorkOrdersReadAnyWriteAdminOrClerk
from core.tenancy import require_tenant


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def office_refused_items(request: Any) -> Response:
    """`GET /work/refused-items?status=open|reviewed|applied|applied_later|all
    &reason=&technician=&kind=&q=&page=&per=` — newest refusal first; `counts`
    per status over the other filters; `facets` for the filter menus."""
    require_tenant(request)
    params = parse_list_params(request.query_params, allowed_sorts=(), default_sort=None)
    qp = request.query_params
    result = refused_items.office_page(
        status=qp.get("status"),
        reason=qp.get("reason"),
        technician=qp.get("technician"),
        kind=qp.get("kind"),
        q=qp.get("q"),
        page=params.page,
        per=params.per,
    )
    return Response({**_envelope(request, result), "counts": result["counts"], "facets": result["facets"]})


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def office_refused_item(request: Any, item_id: Any) -> Response:
    """`GET /work/refused-items/{id}` — the work as sent, its photographs, and
    whether *Apply to the job* can be offered."""
    require_tenant(request)
    return Response(refused_items.office_detail(item_id))


@api_view(["POST"])
@permission_classes([WorkOrdersReadAnyWriteAdminOrClerk])
def office_refused_item_review(request: Any, item_id: Any) -> Response:
    """`POST /work/refused-items/{id}/review` — `{note?}`: *Mark reviewed*."""
    require_tenant(request)
    return Response(refused_items.mark_reviewed(_actor(request), item_id, _payload(request)))


@api_view(["POST"])
@permission_classes([WorkOrdersReadAnyWriteAdminOrClerk])
def office_refused_item_apply(request: Any, item_id: Any) -> Response:
    """`POST /work/refused-items/{id}/apply` — *Apply to the job*: the kind's
    normal apply path, as the office person, when the service accepts it now."""
    require_tenant(request)
    return Response(refused_items.apply_to_job(_actor(request), item_id))


urlpatterns = [
    path("work/refused-items", office_refused_items, name="work_refused_items"),
    path("work/refused-items/<uuid:item_id>", office_refused_item, name="work_refused_item"),
    path(
        "work/refused-items/<uuid:item_id>/review",
        office_refused_item_review,
        name="work_refused_item_review",
    ),
    path(
        "work/refused-items/<uuid:item_id>/apply",
        office_refused_item_apply,
        name="work_refused_item_apply",
    ),
]
