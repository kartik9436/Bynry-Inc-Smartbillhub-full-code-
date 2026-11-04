# ── Trace ──────────────────────────────────────────────
# Change:   CR-171-BRC10 (move-in redesign) · lane MVI-FLOW · P1.22–P1.25
# Rules:    CR-171 §6.2 J6 · J7 · images 10, 13, 14, 17, 24, 27, 28 ·
#           B14 rule 31 (the URL carries the move NUMBER, never a uuid)
# Tests:    tests/test_cr171_p1_22_cancel_move_in.py ·
#           tests/test_cr171_mvi_flow_record_doors.py
# Impacts:  config/urls.py (one include)
# ───────────────────────────────────────────────────────
"""The details view's WRITE doors on a move-in — `moves/{ref}/…`.

⚠ **A FILE OF ITS OWN, FOR `communication_api.py`'s REASON.** `customers/api.py`
is shared surface three R1b lanes hold today (LIST serves `GET /moves/{ref}`
there); a module exporting its own `urlpatterns` keeps these routes out of it.
The routes are TWO segments deep under `moves/<ref>`, so they cannot collide
with `GET /moves/{ref}`.

The READ of the record is LIST's (`move_record_reads.record_detail`); every
door here acts on the same reference and answers its own shape (CR-171 §9.FLOW).
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from django.urls import path
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from core import errors
from core.permissions import AdminOrClerk, AnyTenantRole
from core.tenancy import require_tenant

from apps.customers import (
    move_in_cancel,
    move_in_complete,
    move_in_flow,
    move_in_unit_read,
    move_out_services_read,
)


def _actor(request: Any) -> Any:
    """`service_request_api._actor`'s shape: id from the session user, ROLE
    attached by the identity layer (BE-04), never client input — the 🔒 cancel
    is `require_role`-gated and reads it."""
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


@api_view(["GET"])
@permission_classes([AdminOrClerk])
def move_cancel_preview(request: Any, ref: str) -> Response:
    """`GET /moves/{ref}/cancel-preview` — J6's confirm modal: what a cancel
    would reverse, and whether it may. Writes nothing."""
    require_tenant(request)
    return Response(move_in_cancel.preview(ref))


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def move_cancel(request: Any, ref: str) -> Response:
    """`POST /moves/{ref}/cancel` — *Cancel move-in* (🔒, images 10, 14).
    Body `{"note"?, "refund_method"? ("check" | "ach")}`."""
    require_tenant(request)
    body = _payload(request)
    return Response(
        move_in_cancel.cancel(
            _actor(request),
            ref,
            note=body.get("note"),
            refund_method=body.get("refund_method"),
        )
    )


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def move_in_date(request: Any, ref: str) -> Response:
    """`POST /moves/{ref}/move-in-date` — *Change move-in date* (image 13, J7).
    Body `{"opened_at": "YYYY-MM-DD"}`."""
    require_tenant(request)
    return Response(
        move_in_flow.change_move_in_date(_actor(request), ref, _payload(request).get("opened_at"))
    )


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def move_opening_reads(request: Any, ref: str) -> Response:
    """`POST /moves/{ref}/opening-reads` — *Enter opening read* (image 13).
    Body `{"reads": [{"meter_no", "value" | "estimate", "channel"?, "read_at"?}]}`."""
    require_tenant(request)
    return Response(
        move_in_flow.enter_opening_reads(_actor(request), ref, _payload(request).get("reads"))
    )


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def move_work_orders(request: Any, ref: str) -> Response:
    """`POST /moves/{ref}/work-orders` — *Add a work order* (images 14, 27).
    Body = the wizard's *Field visit* answer `{"template_ids"?, "orders"?}`."""
    require_tenant(request)
    return Response(move_in_flow.add_work_orders(_actor(request), ref, _payload(request)), status=201)


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def unit_move_in_facts(request: Any, unit_id: Any) -> Response:
    """`GET /units/{id}/move-in-facts` — step 1's unit card (P1.17, image 30)."""
    require_tenant(request)
    return Response(move_in_unit_read.unit_facts(unit_id))


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def unit_move_in_meters(request: Any, unit_id: Any) -> Response:
    """`GET /units/{id}/move-in-meters` — *Services and meters* (P1.18, image 30)."""
    require_tenant(request)
    return Response(move_in_unit_read.services_and_meters(unit_id))


@api_view(["POST"])
@permission_classes([AnyTenantRole])
def unit_move_in_meters_check(request: Any, unit_id: Any) -> Response:
    """`POST /units/{id}/move-in-meters/check` — *Below the last read.* per
    row (image 32). Body `{"reads": [{meter_no, value}]}`. Writes nothing."""
    require_tenant(request)
    return Response(
        move_in_unit_read.check_opening_reads(unit_id, _payload(request).get("reads"))
    )


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def unit_move_out_services(request: Any, unit_id: Any) -> Response:
    """`GET /units/{id}/move-out-services?as_of=YYYY-MM-DD` — move-out step 2's
    services, grouped by billing basis (`DEF-CUS-10051`, BR-TEN-1180).
    `as_of` is the move-out date; absent = the tenant's today; a malformed
    date is refused, never read as absent. Writes nothing; one unit's list."""
    from datetime import date as _date

    require_tenant(request)
    raw = request.query_params.get("as_of")
    as_of = None
    if raw not in (None, ""):
        try:
            as_of = _date.fromisoformat(str(raw)[:10])
        except ValueError as bad:
            raise errors.ValidationError(
                errors.VAL_FORMAT,
                message_key="customers.account.date_invalid",
                field_errors=[{"field": "as_of", "code": errors.VAL_FORMAT}],
            ) from bad
    return Response(move_out_services_read.services_by_basis(unit_id, as_of))


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def move_in_message_templates(request: Any) -> Response:
    """`GET /move-ins/message-templates?search=` — the Messaging table's
    *+ Add message* picker (P2.33, image 46). `{served, results: [{code,
    name}]}`; the two defaults are never offered. Writes nothing.

    ⚠ **REGISTERED IN THIS FILE, NOT `api.py`,** for this module's own reason
    above: `customers/api.py` is shared surface, and a literal two-segment
    `move-ins/…` path cannot collide with `move-ins/<…>` reads there."""
    require_tenant(request)
    return Response(move_in_complete.template_choices(search=request.query_params.get("search")))


urlpatterns = [
    path("moves/<str:ref>/cancel-preview", move_cancel_preview),
    path("moves/<str:ref>/cancel", move_cancel),
    path("moves/<str:ref>/move-in-date", move_in_date),
    path("moves/<str:ref>/opening-reads", move_opening_reads),
    path("moves/<str:ref>/work-orders", move_work_orders),
    path("units/<uuid:unit_id>/move-in-facts", unit_move_in_facts),
    path("units/<uuid:unit_id>/move-in-meters", unit_move_in_meters),
    path("units/<uuid:unit_id>/move-in-meters/check", unit_move_in_meters_check),
    path("units/<uuid:unit_id>/move-out-services", unit_move_out_services),
    path("move-ins/message-templates", move_in_message_templates),
]
