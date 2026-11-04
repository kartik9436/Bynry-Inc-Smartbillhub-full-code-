# ── Trace ──────────────────────────────────────────────
# Change:   CR-193-BRC10 — MQ-040 STEP 1 (decision log 2026-10-26)
# Rules:    `07-endpoints.md` §0 rule 1 (ADDITIVE ONLY — every route here is
#           new) · rule 3 (the tenant from the path and the session) · rule 7
#           (idempotent on the key minted at capture) · rule 9 (paged) · rule
#           10 (a technician sees only their own) · hard rules 1, 7
# Tests:    06-backend/tests/test_cr193_shifts.py
# Impacts:  apps/work/api.py (`urlpatterns += shifts_api.urlpatterns`, one line)
# ───────────────────────────────────────────────────────
"""A technician's week, End shift and Submit the day, as routes — THIN.

    GET  /work/mobile/week?from=YYYY-MM-DD                  FF-46's week
    POST /work/mobile/shift/end      {key, at?, capture_token?}       FF-46 End shift
    POST /work/mobile/timesheet/submit {date, key, capture_token?}   FF-47 Submit the day
    GET|POST /work/mobile/availability {key, at, value, capture_token?} FF-45 (FB-033, `availability.py`)
    GET|PUT    /work/technicians/{slug}/working-days        the office
    GET|POST   /work/technicians/{slug}/exceptions          the office (paged)
    PATCH|DELETE /work/technicians/{slug}/exceptions/{id}   the office
    GET        /work/technicians/{slug}/timesheets          the office (paged)

The office's writes are `WorkOrdersReadAnyWriteAdminOrClerk` — the class the
technician's page already writes with (`PATCH /work/technicians/{slug}`): the
utility's admin and the clerk, who is the dispatcher in this product. The two
phone writes take the CAPTOR's token (`mobile.door_actor`), like every other
own door the handset's outbox sends through.

In their own file and spliced into `api.urlpatterns` by one line, because
`api.py` is shared by several lanes (hard-won law 11).
"""

from __future__ import annotations

from typing import Any

from django.urls import path
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.work import availability, mobile, shifts
from apps.work.api import _actor, _envelope, _payload
from core.pagination import parse_list_params
from core.permissions import FieldAppRole, WorkOrdersReadAnyWriteAdminOrClerk
from core.tenancy import require_tenant


def _door(request: Any) -> tuple[Any, dict[str, Any]]:
    payload = _payload(request)
    return mobile.door_actor(_actor(request), payload), mobile.without_capture_token(payload)


def _page_params(request: Any) -> Any:
    return parse_list_params(request.query_params, allowed_filters=(), allowed_sorts=(), default_sort=None)


@api_view(["GET"])
@permission_classes([FieldAppRole])
def mobile_week(request: Any) -> Response:
    """`GET /work/mobile/week?from=` — seven days and today's shift."""
    require_tenant(request)
    return Response(shifts.week(_actor(request), request.query_params.get("from")))


@api_view(["POST"])
@permission_classes([FieldAppRole])
def mobile_shift_end(request: Any) -> Response:
    """`POST /work/mobile/shift/end` — BR-WRK-069; `duplicate: true` on a resend."""
    require_tenant(request)
    actor, body = _door(request)
    return Response(shifts.end_shift(actor, body))


@api_view(["POST"])
@permission_classes([FieldAppRole])
def mobile_timesheet_submit(request: Any) -> Response:
    """`POST /work/mobile/timesheet/submit` — BR-WRK-070; `duplicate: true` on a resend."""
    require_tenant(request)
    actor, body = _door(request)
    return Response(shifts.submit_day(actor, body))


@api_view(["GET", "POST"])
@permission_classes([FieldAppRole])
def mobile_availability(request: Any) -> Response:
    """`POST /work/mobile/availability` — FB-033, one tap from FF-45 through the
    outbox; `duplicate: true` on a resend. `GET` — the status the office
    holds, read back by the phone after each sync."""
    require_tenant(request)
    if request.method == "POST":
        actor, body = _door(request)
        return Response(availability.record(actor, body))
    return Response(availability.current(_actor(request)))


@api_view(["GET", "PUT"])
@permission_classes([WorkOrdersReadAnyWriteAdminOrClerk])
def technician_working_days(request: Any, slug: str) -> Response:
    require_tenant(request)
    if request.method == "PUT":
        return Response(shifts.set_working_days(_actor(request), slug, _payload(request)))
    return Response(shifts.working_days(slug))


@api_view(["GET", "POST"])
@permission_classes([WorkOrdersReadAnyWriteAdminOrClerk])
def technician_exceptions(request: Any, slug: str) -> Response:
    require_tenant(request)
    if request.method == "POST":
        return Response(shifts.add_exception(_actor(request), slug, _payload(request)), status=201)
    params = _page_params(request)
    return Response(_envelope(request, shifts.exceptions_page(slug, page=params.page, per=params.per)))


@api_view(["PATCH", "DELETE"])
@permission_classes([WorkOrdersReadAnyWriteAdminOrClerk])
def technician_exception(request: Any, slug: str, exception_id: Any) -> Response:
    require_tenant(request)
    if request.method == "DELETE":
        shifts.remove_exception(_actor(request), slug, exception_id)
        return Response(status=204)
    return Response(shifts.edit_exception(_actor(request), slug, exception_id, _payload(request)))


@api_view(["GET"])
@permission_classes([WorkOrdersReadAnyWriteAdminOrClerk])
def technician_timesheets(request: Any, slug: str) -> Response:
    require_tenant(request)
    params = _page_params(request)
    return Response(_envelope(request, shifts.timesheets_page(slug, page=params.page, per=params.per)))


urlpatterns = [
    path("work/mobile/week", mobile_week, name="mobile_week"),
    path("work/mobile/shift/end", mobile_shift_end, name="mobile_shift_end"),
    path("work/mobile/timesheet/submit", mobile_timesheet_submit, name="mobile_timesheet_submit"),
    path("work/mobile/availability", mobile_availability, name="mobile_availability"),
    path("work/technicians/<str:slug>/working-days", technician_working_days),
    path("work/technicians/<str:slug>/exceptions/<uuid:exception_id>", technician_exception),
    path("work/technicians/<str:slug>/exceptions", technician_exceptions),
    path("work/technicians/<str:slug>/timesheets", technician_timesheets),
]
