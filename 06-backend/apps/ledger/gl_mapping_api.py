# ── Trace ──────────────────────────────────────────────
# CR:       CR-197-BRC10 (GL mapping becomes one list)
# Rules:    BR-LED-800..803 · BR-LED-014 · NFR-3 (server pagination) ·
#           BR-SHL-011 (list grammar q / f.<name>) · DEF-196 (any role reads,
#           only a System Admin writes)
# Tests:    06-backend/tests/test_cr197_gl_mapping_list.py
# ───────────────────────────────────────────────────────
"""The one GL mapping list, as HTTP.

    GET  /ledger/gl-mappings/rows              one page + counts + facets
    POST /ledger/gl-mappings/rows              {act: add|edit, key, account_id}
    GET  /ledger/gl-mappings/rows/add-options  ?type=… the Add form
    GET  /ledger/gl-mappings/rows/edit-options ?key=… the Edit form
    POST /ledger/gl-mappings/rows/disable      {key}
    POST /ledger/gl-mappings/rows/enable       {key}

HUMAN-OWNED · HUMAN-REVIEW-PENDING — each write re-points where money lands.
Row in `12-governance/09-human-review-ledger.md`. No ORM here (G6); the work is
`apps/ledger/gl_mapping_list.py`. The old whole-map read
(`GET /ledger/gl-mappings`) is left serving its other callers unchanged.
"""
from __future__ import annotations

from typing import Any

from django.urls import path
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.ledger import gl_mapping_list
from core.pagination import parse_list_params
from core.permissions import SettingsReadAnyWriteSystemAdmin
from core.tenancy import require_tenant


def _actor(request: Any) -> Any:
    return request.user


def _payload(request: Any) -> dict[str, Any]:
    data = request.data
    return data if isinstance(data, dict) else {}


@api_view(["GET", "POST"])
@permission_classes([SettingsReadAnyWriteSystemAdmin])
def rows(request: Any) -> Response:
    require_tenant(request)
    if request.method == "POST":
        return Response(gl_mapping_list.save(_actor(request), _payload(request)))
    params = parse_list_params(
        request.query_params, allowed_filters=gl_mapping_list.LIST_FILTERS
    )
    return Response(gl_mapping_list.list_page(params))


@api_view(["GET"])
@permission_classes([SettingsReadAnyWriteSystemAdmin])
def add_options(request: Any) -> Response:
    require_tenant(request)
    type_ = str(request.query_params.get("type") or "").strip() or None
    return Response(gl_mapping_list.add_options(type_))


@api_view(["GET"])
@permission_classes([SettingsReadAnyWriteSystemAdmin])
def edit_options(request: Any) -> Response:
    require_tenant(request)
    return Response(gl_mapping_list.edit_options(str(request.query_params.get("key") or "")))


@api_view(["POST"])
@permission_classes([SettingsReadAnyWriteSystemAdmin])
def disable(request: Any) -> Response:
    require_tenant(request)
    return Response(gl_mapping_list.set_enabled(_actor(request), _payload(request), enabled=False))


@api_view(["POST"])
@permission_classes([SettingsReadAnyWriteSystemAdmin])
def enable(request: Any) -> Response:
    require_tenant(request)
    return Response(gl_mapping_list.set_enabled(_actor(request), _payload(request), enabled=True))


urlpatterns = [
    path("ledger/gl-mappings/rows", rows),
    path("ledger/gl-mappings/rows/add-options", add_options),
    path("ledger/gl-mappings/rows/edit-options", edit_options),
    path("ledger/gl-mappings/rows/disable", disable),
    path("ledger/gl-mappings/rows/enable", enable),
]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-197-BRC10 · decision log 2026-10-29 · BR-LED-800..803
# generated: 2026-10-29 by the CR-197-BRC10 lane
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09 — 🔒 HUMAN-REVIEW-PENDING)
# gates: tests/test_cr197_gl_mapping_list.py
# exceptions: none
# status: HUMAN-REVIEW-PENDING · VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
