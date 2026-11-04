# ── Trace ──────────────────────────────────────────────
# Change:   CR-187-BRC10 · Phase 13 · T-40 (search, nearby) and T-41 (alerts)
#           — lane S-FIND
# Endpoints: 07-endpoints.md N9, N11, N25
# Tests:    06-backend/tests/test_cr187_find_*.py
# ───────────────────────────────────────────────────────
"""The field app's find and alert routes — THIN, like `api.py` (B8 / LAW 0).

In their own file, and spliced into `api.urlpatterns` by one line, because
`api.py` is ~2,500 lines that several lanes edit at once and a pathspec commit
takes the whole file (hard-won law 11, mechanism two).

    GET  /work/mobile/assets/search?q=&page=&per=          FF-41  (N9)
    GET  /work/mobile/nearby?lat=&lng=&radius_mi=&scope=
         &type=&priority=&due_by=&page=&per=                 FF-11  (N11)
    GET  /work/mobile/alerts?page=&per=                      FF-42  (N25)
    POST /work/mobile/alerts/{id}/ack                        FF-43  (N25, R28)
    GET  /work/field-alerts?state=&page=&per=                office (R28's list)
    POST /work/field-alerts                                  office sends one (N25)
    GET  /work/mobile/settings                               the phone's settings (OQ-FLD-12797)

Every route is path-tenanted (`/api/{tenant}/…`) and reads the tenant from the
session, never a body (07-endpoints.md §0 rule 3).
"""

from __future__ import annotations

from typing import Any

from django.urls import path
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.work import field_alerts, field_find
from apps.work.seams import identity_seam
from core import errors
from core.permissions import FieldAppRole, WorkOrdersReadAnyWriteAdminOrClerk
from core.tenancy import require_tenant


def _actor(request: Any) -> Any:
    from apps.work.api import _actor as api_actor

    return api_actor(request)


def _payload(request: Any) -> dict[str, Any]:
    data = request.data
    if not isinstance(data, dict):
        raise errors.ValidationError(errors.VAL_FORMAT, message_key="metering.payload_not_object")
    return data


def _per(request: Any) -> Any:
    """`per` is the product's word (`core.pagination`); `page_size` is what the
    older field routes read, so both are accepted."""
    return request.query_params.get("per") or request.query_params.get("page_size") or 50


@api_view(["GET"])
@permission_classes([FieldAppRole])
def mobile_asset_search(request: Any) -> Response:
    """`GET /work/mobile/assets/search?q=` — the whole utility's meters (N9)."""
    require_tenant(request)
    params = request.query_params
    return Response(
        field_find.search_assets(
            _actor(request), q=params.get("q"), page=params.get("page") or 1, per=_per(request)
        )
    )


@api_view(["GET"])
@permission_classes([FieldAppRole])
def mobile_nearby(request: Any) -> Response:
    """`GET /work/mobile/nearby` — open work around the device, nearest first (N11)."""
    require_tenant(request)
    params = request.query_params
    return Response(
        field_find.nearby(
            _actor(request),
            lat=params.get("lat"),
            lng=params.get("lng"),
            radius_mi=params.get("radius_mi"),
            scope=params.get("scope"),
            unassigned=params.get("unassigned"),
            type=params.get("type"),
            priority=params.get("priority"),
            due_by=params.get("due_by"),
            page=params.get("page") or 1,
            per=_per(request),
        )
    )


@api_view(["GET"])
@permission_classes([FieldAppRole])
def mobile_alerts(request: Any) -> Response:
    """`GET /work/mobile/alerts` — this technician's alerts, an unanswered
    emergency first (FF-42)."""
    require_tenant(request)
    return Response(
        field_alerts.my_alerts(
            _actor(request), page=request.query_params.get("page") or 1, per=_per(request)
        )
    )


@api_view(["POST"])
@permission_classes([FieldAppRole])
def mobile_alert_ack(request: Any, alert_id: Any) -> Response:
    """`POST /work/mobile/alerts/{id}/ack` — the technician answers (R28).
    Idempotent; another technician's alert is a 404."""
    require_tenant(request)
    return Response(field_alerts.acknowledge(_actor(request), alert_id))


@api_view(["GET", "POST"])
@permission_classes([WorkOrdersReadAnyWriteAdminOrClerk])
def field_alerts_office(request: Any) -> Response:
    """`GET /work/field-alerts?state=all|awaiting_ack|overdue` — the dispatcher's
    list; `POST` sends one alert to one technician's handset (N25)."""
    require_tenant(request)
    if request.method == "POST":
        return Response(field_alerts.send_alert(_actor(request), _payload(request)), status=201)
    params = request.query_params
    return Response(
        field_alerts.office_alerts(
            state=params.get("state"), page=params.get("page") or 1, per=_per(request)
        )
    )



@api_view(["GET"])
@permission_classes([FieldAppRole])
def mobile_settings(request: Any) -> Response:
    """`GET /work/mobile/settings` — the settings a handset keeps and obeys.

    Today one: `field_app_pins`, the certificate pins the office keeps on
    Settings › Security (`OQ-FLD-12797`). **The phone adopts this list only
    when it arrived over a connection already pinned by its current set**, and
    refuses one that would leave it with no unexpired pin — that is the
    handset's half (`field-app/src/security/pins.ts`); this half only serves
    the utility's own active, unexpired keys."""
    require_tenant(request)
    return Response({"field_app_pins": identity_seam.field_app_pins()})

#: Spliced into `apps.work.api.urlpatterns` at its head. Every path is a
#: literal or a uuid converter, and none shares a prefix-and-depth with a
#: looser pattern there (`work/technicians/<str:slug>` is three segments with
#: `technicians` as its second; `work/mobile/...` and `work/field-alerts` are not).
urlpatterns = [
    path("work/mobile/assets/search", mobile_asset_search),
    path("work/mobile/nearby", mobile_nearby),
    path("work/mobile/alerts", mobile_alerts),
    path("work/mobile/settings", mobile_settings),
    path("work/mobile/alerts/<uuid:alert_id>/ack", mobile_alert_ack),
    path("work/field-alerts", field_alerts_office),
]
