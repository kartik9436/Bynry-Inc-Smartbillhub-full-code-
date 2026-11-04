"""The move-in wizard's document doors — `CR-171-BRC10` P2.25 (lane MVI-WIZ-CUST).

Its own module, mounted from `config/urls.py`, for the reason the money and
flow modules give: `api.py` is the file several lanes hold at once.

    GET  /move-ins/documents/required   → {required: [doc_type, …]}  image 33's locked rows
    POST /move-ins/documents (multipart: file, doc_type, name?)
                                        → 201 {card_id, doc_type, name, size_bytes, content_type}
    GET  /move-ins/documents/{card_id}/content?as=view|download → the file (open before Complete)
    POST /accounts/{id}/co-owners/{coOwnerId}/photo-id (multipart: file, name?)
                                        → 201 {co_owner_id, photo_id, document_id}  P2.24, after Complete

The card is filed on the account by the move-in commit's `documents` key
(`move_in_people`). `AdminOrClerk` throughout: a billing clerk runs move-ins.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from django.urls import path
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from apps.customers import account_documents
from apps.customers import move_in_documents as staging
from core import errors
from core.permissions import AdminOrClerk
from core.tenancy import require_tenant


def _actor(request: Any) -> Any:
    user = getattr(request, "user", None)
    return SimpleNamespace(
        id=getattr(user, "id", None) or getattr(user, "pk", None),
        role=getattr(request, "tenant_role", None),
    )


@api_view(["GET"])
@permission_classes([AdminOrClerk])
def move_in_documents_required(request: Any) -> Response:
    require_tenant(request)
    return Response({"required": staging.required_types()})


@api_view(["POST"])
@permission_classes([AdminOrClerk])
@parser_classes([MultiPartParser, FormParser, JSONParser])
def move_in_documents(request: Any) -> Response:
    require_tenant(request)
    payload = {k: v for k, v in (request.data or {}).items() if k != "file"}
    try:
        staged = staging.stage(
            _actor(request), payload, request.FILES.get("file")
        )
    except account_documents.UploadRefused as refusal:
        # 413 / 415 — the same transport rows `POST /accounts/{id}/documents` answers.
        return Response(
            errors.http_series_refusal_body(refusal.message_key, br_ref=refusal.br_ref, **refusal.params),
            status=refusal.status,
        )
    return Response(staged, status=201)


@api_view(["GET"])
@permission_classes([AdminOrClerk])
def move_in_document_content(request: Any, card_id: str) -> Any:
    """The staged file itself — the account document content view's headers,
    taken from that view rather than restated."""
    from django.http import HttpResponse

    from apps.customers.service_request_api import DOCUMENT_CSP, _content_disposition

    require_tenant(request)
    mode = str(request.query_params.get("as") or "view")
    served = staging.content(_actor(request), card_id, mode)
    response = HttpResponse(served["payload"], content_type=served["content_type"])
    response["Content-Disposition"] = _content_disposition(served["inline"], served["name"])
    response["X-Content-Type-Options"] = "nosniff"
    response["Content-Security-Policy"] = DOCUMENT_CSP
    response["Cache-Control"] = "private, no-store"
    response["Content-Length"] = str(len(served["payload"]))
    return response


@api_view(["POST"])
@permission_classes([AdminOrClerk])
@parser_classes([MultiPartParser, FormParser, JSONParser])
def co_owner_photo_id(request: Any, account_id: str, co_owner_id: str) -> Response:
    """P2.24 — a co-owner's photo ID, filed once the account exists
    (`move_in_people.attach_photo_id`); 413 / 415 as an account upload."""
    from apps.customers import move_in_people

    require_tenant(request)
    payload = {k: v for k, v in (request.data or {}).items() if k != "file"}
    try:
        answer = move_in_people.attach_photo_id(
            _actor(request), account_id, co_owner_id, payload, request.FILES.get("file")
        )
    except account_documents.UploadRefused as refusal:
        return Response(
            errors.http_series_refusal_body(refusal.message_key, br_ref=refusal.br_ref, **refusal.params),
            status=refusal.status,
        )
    return Response(answer, status=201)


urlpatterns = [
    path("move-ins/documents/required", move_in_documents_required),
    path("move-ins/documents", move_in_documents),
    path("move-ins/documents/<str:card_id>/content", move_in_document_content),
    path("accounts/<str:account_id>/co-owners/<str:co_owner_id>/photo-id", co_owner_photo_id),
]
