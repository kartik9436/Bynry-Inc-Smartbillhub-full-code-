# ── Trace ──────────────────────────────────────────────
# Change:   CR-192-BRC10 — MQ-033 Settings → Reads: the read FORMATS routes
#           (task 10 of 13, the server; the screens are task 11, the phone
#           task 12).
# Rules:    BR-MET-1210 … BR-MET-1218 · NFR-3 (every list paged on the
#           server) · BR-SHL-011 (a list URL never 4xx-es over its params) ·
#           BR-SHL-025 (A4: Settings Full = System Admin, View = Executive;
#           the SERVICE's @require_role refuses an Executive's write)
# Tests:    06-backend/tests/test_mq033_read_formats.py
# Impacts:  apps/metering/api.py (`urlpatterns += read_formats_api.urlpatterns`)
# ───────────────────────────────────────────────────────
"""The read-format routes — THIN by law (B8): every write is a service call.

    GET    settings/read-formats?service=&status=&q=&page=&per=   the list
    POST   settings/read-formats                                  create
    GET    settings/read-formats/defaults                         per service
    PUT    settings/read-formats/defaults/{service}               set / clear
    GET    settings/read-formats/versions/{version_id}            one version
    GET    settings/read-formats/{id}                             one format
    PATCH  settings/read-formats/{id}                             name/service/note
    GET    settings/read-formats/{id}/versions?page=&per=         its versions
    POST   settings/read-formats/{id}/questions                   add (draft)
    POST   settings/read-formats/{id}/questions/reorder           reorder (draft)
    PATCH  settings/read-formats/{id}/questions/{key}             edit (draft)
    DELETE settings/read-formats/{id}/questions/{key}             delete (draft)
    POST   settings/read-formats/{id}/publish                     publish
    POST   settings/read-formats/{id}/new-draft                   edit a published one
    POST   settings/read-formats/{id}/retire                      retire
    PUT    cycles/{id}/read-format                                set / clear
    PUT    routes/read-format                                     one or many routes
    GET    routes/{id}/read-format                                what it resolves to
    GET    work/mobile/read-formats/versions/{version_id}         the handset's copy
    GET    reads/answer-questions?q=&key=&page=&per=              Answer filter (task 13)
    GET    reads/photos/{photo_id}/content                        a photo answer (task 13)
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from django.urls import path
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.metering import read_answers_office, read_formats
from core.pagination import StandardPagination
from core.permissions import AdminOrExecutive, AnyTenantRole, FieldAppRole
from core.tenancy import require_tenant


def _actor(request: Any) -> Any:
    """Id from the session, role server-attached — never client input."""
    user = getattr(request, "user", None)
    return SimpleNamespace(
        id=getattr(user, "id", None) or getattr(user, "pk", None),
        role=getattr(request, "tenant_role", None),
    )


def _body(request: Any) -> Any:
    return request.data


def _page(request: Any, rows: Any, serializer: Any) -> Response:
    """One page in the DRF envelope, sliced by the DATABASE (NFR-3)."""
    paginator = StandardPagination()
    page = list(paginator.paginate_queryset(rows, request) or [])
    return paginator.get_paginated_response(serializer(page))


@api_view(["GET", "POST"])
@permission_classes([AdminOrExecutive])
def formats(request: Any) -> Response:
    require_tenant(request)
    if request.method == "POST":
        return Response(read_formats.create_format(_actor(request), _body(request)), status=201)
    q = request.query_params
    rows = read_formats.formats_queryset(service=q.get("service"), status=q.get("status"), q=q.get("q"))
    return _page(request, rows, read_formats.list_page_rows)


@api_view(["GET", "PATCH"])
@permission_classes([AdminOrExecutive])
def format_detail(request: Any, format_id: Any) -> Response:
    require_tenant(request)
    if request.method == "PATCH":
        return Response(read_formats.update_format(_actor(request), format_id, _body(request)))
    return Response(read_formats.get_format(format_id))


@api_view(["GET"])
@permission_classes([AdminOrExecutive])
def format_versions(request: Any, format_id: Any) -> Response:
    require_tenant(request)
    rows = read_formats.versions_queryset(format_id)
    return _page(
        request, rows, lambda page: [read_formats.version_dict(v, with_questions=False) for v in page]
    )


@api_view(["GET"])
@permission_classes([AdminOrExecutive])
def version_detail(request: Any, version_id: Any) -> Response:
    require_tenant(request)
    return Response(read_formats.get_version(version_id))


@api_view(["POST"])
@permission_classes([AdminOrExecutive])
def questions(request: Any, format_id: Any) -> Response:
    require_tenant(request)
    return Response(read_formats.add_question(_actor(request), format_id, _body(request)), status=201)


@api_view(["POST"])
@permission_classes([AdminOrExecutive])
def questions_reorder(request: Any, format_id: Any) -> Response:
    require_tenant(request)
    return Response(read_formats.reorder_questions(_actor(request), format_id, _body(request)))


@api_view(["PATCH", "DELETE"])
@permission_classes([AdminOrExecutive])
def question_detail(request: Any, format_id: Any, key: str) -> Response:
    require_tenant(request)
    if request.method == "DELETE":
        return Response(read_formats.delete_question(_actor(request), format_id, key))
    return Response(read_formats.update_question(_actor(request), format_id, key, _body(request)))


@api_view(["POST"])
@permission_classes([AdminOrExecutive])
def publish(request: Any, format_id: Any) -> Response:
    require_tenant(request)
    return Response(read_formats.publish(_actor(request), format_id, _body(request) or {}))


@api_view(["POST"])
@permission_classes([AdminOrExecutive])
def new_draft(request: Any, format_id: Any) -> Response:
    require_tenant(request)
    return Response(read_formats.new_draft(_actor(request), format_id))


@api_view(["POST"])
@permission_classes([AdminOrExecutive])
def retire(request: Any, format_id: Any) -> Response:
    require_tenant(request)
    return Response(read_formats.retire(_actor(request), format_id))


@api_view(["GET"])
@permission_classes([AdminOrExecutive])
def defaults(request: Any) -> Response:
    require_tenant(request)
    return Response(read_formats.defaults())


@api_view(["PUT"])
@permission_classes([AdminOrExecutive])
def default_for_service(request: Any, service: str) -> Response:
    require_tenant(request)
    return Response(read_formats.set_service_default(_actor(request), service, _body(request)))


@api_view(["GET", "PUT"])
@permission_classes([AdminOrExecutive])
def cycle_read_format(request: Any, cycle_id: Any) -> Response:
    require_tenant(request)
    if request.method == "GET":
        # MQ-033 task 11 — the cycle screen reads the pointer it edits; the
        # cycle row's own serializer is task 9's to change, so the read is here.
        return Response(read_formats.cycle_format(cycle_id))
    return Response(read_formats.set_cycle_format(_actor(request), cycle_id, _body(request)))


@api_view(["PUT"])
@permission_classes([AdminOrExecutive])
def routes_read_format(request: Any) -> Response:
    require_tenant(request)
    return Response(read_formats.set_route_formats(_actor(request), _body(request)))


@api_view(["GET"])
@permission_classes([AdminOrExecutive])
def route_read_format(request: Any, route_id: Any) -> Response:
    require_tenant(request)
    return Response(read_formats.route_resolution(route_id))


@api_view(["GET"])
@permission_classes([FieldAppRole])
def mobile_version(request: Any, version_id: Any) -> Response:
    """The handset's copy of one PUBLISHED version — what it caches by id."""
    require_tenant(request)
    return Response(read_formats.get_version(version_id, published_only=True))


# ── The office reads the answers (`CR-192-BRC10` task 13) ─────────────────
@api_view(["GET"])
@permission_classes([AnyTenantRole])
def answer_questions(request: Any) -> Response:
    """`GET reads/answer-questions?q=&key=&page=&per=` — the Reads list's
    Answer filter vocabulary: questions of PUBLISHED formats, server-paged
    (NFR-3). Any office role, because the Reads list is (a clerk filters it;
    Settings → Reads is not theirs)."""
    require_tenant(request)
    q = request.query_params
    rows = read_answers_office.answer_questions_queryset(q=q.get("q"), keys=q.getlist("key"))
    return _page(request, rows, read_answers_office.answer_question_rows)


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def answer_photo_content(request: Any, photo_id: Any) -> Any:
    """`GET reads/photos/{photo_id}/content` — a photograph answer's bytes,
    same-origin (`DEF-WRK-9594`'s reason), never kept by a shared cache."""
    from django.http import HttpResponse

    require_tenant(request)
    payload, content_type = read_answers_office.photo_bytes(photo_id)
    response = HttpResponse(payload, content_type=content_type)
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response


urlpatterns = [
    path("reads/answer-questions", answer_questions),
    path("reads/photos/<uuid:photo_id>/content", answer_photo_content),
    path("settings/read-formats", formats),
    path("settings/read-formats/defaults", defaults),
    path("settings/read-formats/defaults/<str:service>", default_for_service),
    path("settings/read-formats/versions/<uuid:version_id>", version_detail),
    path("settings/read-formats/<uuid:format_id>", format_detail),
    path("settings/read-formats/<uuid:format_id>/versions", format_versions),
    path("settings/read-formats/<uuid:format_id>/questions", questions),
    path("settings/read-formats/<uuid:format_id>/questions/reorder", questions_reorder),
    path("settings/read-formats/<uuid:format_id>/questions/<str:key>", question_detail),
    path("settings/read-formats/<uuid:format_id>/publish", publish),
    path("settings/read-formats/<uuid:format_id>/new-draft", new_draft),
    path("settings/read-formats/<uuid:format_id>/retire", retire),
    path("cycles/<uuid:cycle_id>/read-format", cycle_read_format),
    path("routes/read-format", routes_read_format),
    path("routes/<uuid:route_id>/read-format", route_read_format),
    path("work/mobile/read-formats/versions/<uuid:version_id>", mobile_version),
]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-192-BRC10 (MQ-033 task 10 — read formats server; decision log 2026-10-24 ×3)
# generated: 2026-10-24 by lane MQ033-SERVER
# checklist: A✔ B✔ C✔ D✔ E=deferred(task 11 builds Settings → Reads) F✔ G✔ H=deferred(no 🔒 path in this file)
# gates: see the lane report
# exceptions: none
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
