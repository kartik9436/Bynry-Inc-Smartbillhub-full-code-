# ── Trace ──────────────────────────────────────────────
# Change:   CR-187-BRC10 — the field app's route-reading routes,
#           `04-docs/05-modules/18-field-app/07-endpoints.md` N1, N5, N6, N12.
# Story:    US-FLD-040 · US-FLD-041 · US-FLD-042 · US-FLD-054 · US-FLD-060 ·
#           US-FLD-061 · US-FLD-062
#           Screens: RW-01, RW-03, RW-06, RW-09, RW-17, RW-18, RW-19, RW-20,
#           RW-25, RW-26, RW-27
# Rules:    `07-endpoints.md` §0 (additive only · tenant from the credential,
#           never the payload · idempotent on a key minted at capture · proved
#           on PostgreSQL · paged, no cap · a technician sees only their own ·
#           money is never written) · BR-FLD-00082 · BR-FLD-00087
# Tests:    06-backend/tests/test_cr187_reads_sync.py ·
#           06-backend/tests/test_cr187_reads_routes.py
# Impacts:  apps/metering/api.py (`urlpatterns += field_reads_api.urlpatterns`)
# ───────────────────────────────────────────────────────
"""The route-reading routes — THIN by law (B8): every write is a service call,
every read a selector; no ORM here.

Mounted under `work/mobile/…` because that is the field app's address space and
`07-endpoints.md` proposes exactly these shapes; OWNED by metering, which owns
meter reads, routes and cycles. Auth is today's session and `FieldAppRole`
(any office role and the field technician). The native token sign-in is another
lane's and is not built here.

    GET  work/mobile/routes                       my routes (RW-01)
    GET  work/mobile/routes/{id}?page=&per=       one page of stops (RW-03…06)
    POST work/mobile/reads/sync                   ≤ 50 route items (RW-26)
    PUT  work/mobile/reads/photos/{photo_id}      a route photograph's bytes
    GET  work/mobile/reads/photos/{photo_id}      its link's state (DEF-FLD-10357)
    GET  work/mobile/reads/photos/{photo_id}/content  its bytes, own only (FB-030)
    GET  work/mobile/reads/history              my turned-in reads, 14 days (FB-030)
    POST work/mobile/routes/{id}/turn-in          the receipt (RW-25…27)
    GET  work/mobile/cant-read-reasons            the utility's list (RW-17)
    POST work/mobile/cant-read-reasons            add one — System Admin
    PATCH work/mobile/cant-read-reasons/{code}    (de)activate — System Admin
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from django.urls import path
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from apps.metering import field_history, field_read_photos, field_reads, field_routes
from core import errors
from core.permissions import SYSTEM_ADMIN, FieldAppRole
from core.tenancy import require_tenant


def _actor(request: Any) -> Any:
    """The acting user: id from the session, role server-attached — never
    client input (R127: the tenant and the person come from the credential)."""
    user = getattr(request, "user", None)
    return SimpleNamespace(
        id=getattr(user, "id", None) or getattr(user, "pk", None),
        role=getattr(request, "tenant_role", None),
    )


def _body(request: Any) -> dict[str, Any]:
    data = request.data
    return data if isinstance(data, dict) else {}


@api_view(["GET"])
@permission_classes([FieldAppRole])
def my_routes(request: Any) -> Response:
    """`GET work/mobile/routes?on=&page=&per=` — RW-01."""
    require_tenant(request)
    q = request.query_params
    return Response(
        field_routes.my_routes(_actor(request), on=q.get("on"), page=q.get("page"), per=q.get("per"))
    )


@api_view(["GET"])
@permission_classes([FieldAppRole])
def route_page(request: Any, route_id: Any) -> Response:
    """`GET work/mobile/routes/{id}?on=&page=&per=` — RW-03 … RW-06."""
    require_tenant(request)
    q = request.query_params
    return Response(
        field_routes.route_page(
            _actor(request), route_id, on=q.get("on"), page=q.get("page"), per=q.get("per")
        )
    )


@api_view(["POST"])
@permission_classes([FieldAppRole])
def reads_sync(request: Any) -> Response:
    """`POST work/mobile/reads/sync` — RW-26. One answer per item; a SAVEPOINT
    per item (hard-won law 14 — `field_reads`' module docstring)."""
    require_tenant(request)
    return Response(field_reads.sync_reads(_actor(request), _body(request)))


@api_view(["PUT", "GET"])
@parser_classes([MultiPartParser, FormParser])
@permission_classes([FieldAppRole])
def reads_photo(request: Any, photo_id: Any) -> Response:
    """`PUT work/mobile/reads/photos/{photo_id}` — a ROUTE photograph's bytes,
    to the link its declaration made (`DEF-FLD-10357`; the job door's
    `work/mobile/photos/{id}` shape). A multipart `file`, one per request
    (R124). A hash that is not the declared one is refused 409 and nothing is
    kept. `GET` answers the link's state (`pending` · `landed`)."""
    require_tenant(request)
    if request.method == "GET":
        found = field_read_photos.link_answer_for(photo_id)
        if found is None:
            raise errors.deny_as_not_found("BR-TEN-003")
        return Response(found)
    content_type = str(request.content_type or "")
    if content_type.startswith("multipart/"):
        upload = request.FILES.get("file")
        data = upload.read() if upload is not None else b""
        content_type = getattr(upload, "content_type", "") or "image/jpeg"
    else:
        data = request.body
    return Response(field_read_photos.receive_bytes(_actor(request), photo_id, data, content_type))


@api_view(["GET"])
@permission_classes([FieldAppRole])
def reads_photo_content(request: Any, photo_id: Any) -> Any:
    """`GET work/mobile/reads/photos/{photo_id}/content` — FB-030: a route
    photograph's bytes, own work only; shown on the phone, never kept."""
    from django.http import HttpResponse

    require_tenant(request)
    payload, content_type = field_history.route_photo_content(_actor(request), photo_id)
    response = HttpResponse(payload, content_type=content_type)
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response


@api_view(["GET"])
@permission_classes([FieldAppRole])
def reads_history(request: Any) -> Response:
    """`GET work/mobile/reads/history?page=&per=` — FB-030: the reader's own
    turned-in readings of the last 14 days, paged (the refill of a new phone)."""
    require_tenant(request)
    q = request.query_params
    return Response(field_history.reads_history(_actor(request), page=q.get("page"), per=q.get("per")))


@api_view(["POST"])
@permission_classes([FieldAppRole])
def route_turn_in(request: Any, route_id: Any) -> Response:
    """`POST work/mobile/routes/{id}/turn-in` — RW-25 … RW-27. Never a gate."""
    require_tenant(request)
    return Response(field_reads.turn_in(_actor(request), route_id, _body(request)))


@api_view(["GET", "POST"])
@permission_classes([FieldAppRole])
def cant_read_reasons(request: Any) -> Response:
    """`GET` the list (any field-app caller) · `POST` a utility's own reason
    (System Admin only — the Settings half of R82's *tenant-extensible*)."""
    require_tenant(request)
    actor = _actor(request)
    if request.method == "POST":
        _require_admin(actor)
        return Response(field_reads.add_cant_read_reason(actor, _body(request)), status=201)
    include = str(request.query_params.get("include_inactive", "")).lower() in ("1", "true")
    return Response(field_reads.cant_read_reasons(include_inactive=include))


@api_view(["PATCH"])
@permission_classes([FieldAppRole])
def cant_read_reason(request: Any, code: str) -> Response:
    """`PATCH work/mobile/cant-read-reasons/{code}` `{active}` — System Admin."""
    require_tenant(request)
    actor = _actor(request)
    _require_admin(actor)
    return Response(field_reads.set_cant_read_reason_active(actor, code, _body(request)))


def _require_admin(actor: Any) -> None:
    if actor.role != SYSTEM_ADMIN:
        raise errors.AuthError(errors.AUTH_PERMISSION_DENIED, br_ref="BR-TEN-036")


urlpatterns = [
    path("work/mobile/routes", my_routes),
    path("work/mobile/routes/<uuid:route_id>", route_page),
    path("work/mobile/routes/<uuid:route_id>/turn-in", route_turn_in),
    path("work/mobile/reads/sync", reads_sync),
    path("work/mobile/reads/photos/<uuid:photo_id>", reads_photo),
    path("work/mobile/reads/photos/<uuid:photo_id>/content", reads_photo_content),
    path("work/mobile/reads/history", reads_history),
    path("work/mobile/cant-read-reasons", cant_read_reasons),
    path("work/mobile/cant-read-reasons/<str:code>", cant_read_reason),
]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-FLD-040@fa5746815 (CR-187-BRC10 route-reading server lane — 07-endpoints.md N1, N5, N6, N12)
# generated: 2026-10-21 by the CR-187 reads server lane
# checklist: A✔ B✔ C✔ D✔ E=deferred(the native app lanes build the screens) F✔ G✔ H=deferred(no 🔒 path in this file)
# gates: see the lane report
# exceptions: mounted under work/mobile/ (the field app's address space) though metering owns it — REPORTED · OpenAPI schema not regenerated (one generated file, law 5 — the coordinator's)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
