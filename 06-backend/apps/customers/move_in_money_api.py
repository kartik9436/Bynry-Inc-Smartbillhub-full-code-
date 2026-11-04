# ── Trace ──────────────────────────────────────────────
# Change:   CR-171-BRC10 P1.12 / P1.16 — the move-in's Fees table and its
#           *See full rates*, read before the account exists (lane MVI-MONEY).
#           Images 41, 42, 43.
# Rules:    BR-SHL-025 / A4 (reads: all three roles) · BR-BIL-007 · BR-RAT-108 ·
#           OQ-BIL-12788 CLOSED (a) 2026-10-05 · CLAUDE.md rule 1
# Tests:    06-backend/tests/test_cr171_p1_16_move_in_pricing.py
# ───────────────────────────────────────────────────────
"""Three READS the Billing step of the four-step move-in calls before Complete.

Its own module, mounted from `config/urls.py`, for the reason the communication
and transfer modules give: `api.py` is the file several lanes hold at once.
Nothing here writes; the commit is `POST /accounts/{id}/move-in` (or the unit
door) with `fees` / `payment` / `autopay_instrument_id` / `discount_claims` /
`tax_exemption` in its body, priced again there (`move_fees.record`).

    GET /move-ins/fees?unit_id=&account_type=&services=&size_class=
        → {rows, total, currency, deposit, services, …}  image 41's locked rows
    GET /move-ins/fees/quote?unit_id=&account_type=&code=&services=
        → one row priced from its code, or `refusal` naming why not (image 43)
    GET /move-ins/pricing?unit_id=&account_type=&services=&size_class=
        → the plan's sections narrowed to this move-in + deposit + fees + the
          asset tree per service (image 42)

`services` is a comma list of service codes (the Start ticks); absent means
every service the unit carries.
"""

from __future__ import annotations

from typing import Any

from django.urls import path
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from core import errors
from core.permissions import AnyTenantRole
from core.tenancy import require_tenant

from apps.customers import move_fees

UNIT_REQUIRED = "customers.deposit.standardNeedsUnit"
CATEGORY_REQUIRED = "customers.deposit.standardNeedsCategory"


def _args(request: Any) -> tuple[str, str, list[str] | None, str | None]:
    unit_id = str(request.query_params.get("unit_id") or "").strip()
    account_type = str(request.query_params.get("account_type") or "").strip()
    fe = []
    if not unit_id:
        fe.append({"field": "unit_id", "code": errors.VAL_REQUIRED, "message_key": UNIT_REQUIRED, "params": {}})
    if not account_type:
        fe.append(
            {"field": "account_type", "code": errors.VAL_REQUIRED, "message_key": CATEGORY_REQUIRED, "params": {}}
        )
    if fe:
        raise errors.ValidationError(fe[0]["code"], message_key=fe[0]["message_key"], field_errors=fe)
    raw = request.query_params.get("services")
    services = [one.strip() for one in raw.split(",") if one.strip()] if raw else None
    size = str(request.query_params.get("size_class") or "").strip() or None
    return unit_id, account_type, services, size


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def move_in_fees(request: Any) -> Response:
    require_tenant(request)
    unit_id, account_type, services, size = _args(request)
    return Response(move_fees.default_rows(unit_id, account_type, services=services, size_class=size))


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def move_in_fee_quote(request: Any) -> Response:
    require_tenant(request)
    unit_id, account_type, services, _size = _args(request)
    return Response(
        move_fees.quote(request.query_params.get("code"), unit_id, account_type, services=services)
    )


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def move_in_pricing(request: Any) -> Response:
    require_tenant(request)
    unit_id, account_type, services, size = _args(request)
    return Response(move_fees.move_in_pricing(unit_id, account_type, services=services, size_class=size))


urlpatterns = [
    path("move-ins/fees", move_in_fees),
    path("move-ins/fees/quote", move_in_fee_quote),
    path("move-ins/pricing", move_in_pricing),
]
