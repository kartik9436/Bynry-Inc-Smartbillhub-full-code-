# ── Trace ──────────────────────────────────────────────
# Change:   CR-158-BRC10 — a customer attaches documents to a portal
#           new-service application; the clerk opens them on the request.
#           PO 2026-10-01: "you need to allow customer to upload documents and
#           save those document to server for that Utility - and then clark
#           should able to view those document in new request". DF-4 is
#           superseded for the new-service request ONLY.
# Rules:    BR-SHL-031 (10 MB) · BR-CWP-026 · BR-TEN-003 (existence must not
#           leak) · CLAUDE.md hard rule 1 · hard rule 7 (audit)
# Tests:    this file (SQLite) · test_cr158_portal_application_documents_pg.py
#           (the RLS half, which SQLite cannot hold)
# ───────────────────────────────────────────────────────
"""The applicant's documents, end to end through the routes a browser calls.

⚠ **WHAT WOULD MAKE THESE PASS WRONGLY, ASKED FIRST** (law 7 habit 2):
  * *"a document row exists"* passes over a reference to nothing — so the
    hand-over case reads the BYTES back out of the store and compares them;
  * *"the upload was refused"* passes if every upload is refused — so each
    refusal case also proves a good file on the same draft is accepted;
  * *"staff cannot see an abandoned draft's file"* passes vacuously if nothing
    was ever uploaded — so the case uploads first, and counts the store.

RUN WITH `JOBS_EAGER=false --reuse-db`.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.customers import models as customers_models
from apps.customers import service_request_api
from apps.customers import service_request_documents as doc_files
from apps.portal import guest_api, models
from apps.tenancy.document_models import StoredDocument
from core.tenancy import tenant_context
from tests.test_us_cwp_helpers import *  # noqa: F401,F403
from tests.test_us_cwp_helpers import brand_fully, seed_addresses_for, switch_on
from tests.test_us_ten_helpers import api_call

TOKEN = "c158c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d"

PDF = b"%PDF-1.7\n1 0 obj\n<< /Title (Tenancy agreement) >>\n" + b"T" * 3000 + b"\n%%EOF"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + b"P" * 2000
JPG = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00" + b"J" * 2000
HTML = b"<html><script>fetch('/api/x')</script></html>"

COMPLETE = {
    "address_as_given": "31 Palm Ct",
    "service_codes": ["water", "solar"],
    "applicant_kind": "person",
    "first_name": "Daniel",
    "last_name": "Okafor",
    "email": "d.okafor@example.test",
    "phone": "(512) 555-7730",
    "account_type_code": "residential",  # DEF-CWP-9818 (required at Send)
}


@pytest.fixture()
def docs_dir(tmp_path, settings):
    settings.DOCUMENT_STORAGE_BACKEND = "filesystem"
    settings.DOCUMENT_STORAGE_ALLOW_FILESYSTEM = True
    settings.DOCUMENT_STORAGE_DIR = str(tmp_path / "documents")
    return tmp_path / "documents"


@pytest.fixture()
def ready(pine_hill, sarah, docs_dir):
    switch_on(pine_hill, sarah)
    brand_fully(pine_hill, sarah)
    seed_addresses_for(pine_hill, sarah)
    _draft(pine_hill)
    return pine_hill


def _draft(tenant, token=TOKEN):
    return api_call(
        guest_api.application_draft,
        "put",
        f"/api/{tenant.subdomain}/portal/public/applications/{token}",
        tenant=tenant,
        data={**COMPLETE, "requested_start": (date.today() + timedelta(days=21)).isoformat()},
        token=token,
    )


def _upload(tenant, payload, name, content_type="application/pdf", token=TOKEN):
    return api_call(
        guest_api.application_documents,
        "post",
        f"/api/{tenant.subdomain}/portal/public/applications/{token}/documents",
        tenant=tenant,
        data={"file": SimpleUploadedFile(name, payload, content_type=content_type)},
        body_format="multipart",
        token=token,
    )


def _remove(tenant, document_id, token=TOKEN):
    return api_call(
        guest_api.application_document,
        "delete",
        f"/api/{tenant.subdomain}/portal/public/applications/{token}/documents/{document_id}",
        tenant=tenant,
        token=token,
        document_id=document_id,
    )


def _send(tenant, token=TOKEN):
    return api_call(
        guest_api.submit_application,
        "post",
        f"/api/{tenant.subdomain}/portal/public/applications/{token}/submit",
        tenant=tenant,
        data={"paperless": False},
        token=token,
    )


def _content(tenant, actor, request_id, document_id, mode):
    return api_call(
        service_request_api.service_request_document_content,
        "get",
        f"/api/{tenant.subdomain}/service-requests/{request_id}/documents/{document_id}/content",
        tenant=tenant,
        user=actor.user,
        role="billing_clerk",
        query={"as": mode},
        request_id=str(request_id),
        document_id=str(document_id),
    )


# ── the customer's side ─────────────────────────────────────────────────────


@pytest.mark.django_db
def test_a_customer_attaches_a_file_and_the_draft_lists_it(ready, audit_rows):
    response = _upload(ready, PDF, "tenancy-agreement.pdf")
    assert response.status_code == 200, response.data
    docs = response.data["documents"]
    assert [d["name"] for d in docs] == ["tenancy-agreement.pdf"]
    assert docs[0]["content_type"] == "application/pdf"
    assert docs[0]["size_bytes"] == len(PDF)
    assert docs[0]["uploaded_at"]
    # The limits the screen states come from the server, so they cannot drift.
    assert response.data["document_limits"] == {
        "types": ["application/pdf", "image/jpeg", "image/png"],
        "max_bytes": 10 * 1024 * 1024,
        "max_files": 5,
    }
    # The bytes are held on the draft row, exactly as sent.
    with tenant_context(ready.id):
        row = models.PortalApplicationDocument.objects.get()
        assert bytes(row.payload) == PDF
    assert any(r["action"] == "portal.application_document.uploaded" for r in audit_rows)


@pytest.mark.django_db
def test_the_type_is_read_from_the_bytes_never_from_the_browser(ready):
    """An HTML page sent as `image/png` is refused BY NAME with a 415; a real
    JPEG sent as `application/octet-stream` is accepted and recorded as what
    its bytes say it is."""
    refused = _upload(ready, HTML, "photo.png", content_type="image/png")
    assert refused.status_code == 415
    assert refused.data["message_key"] == "portal.application.documentTypeNotAllowed"
    assert refused.data["params"]["name"] == "photo.png"
    assert refused.data["params"]["allowed"] == "PDF, JPG, PNG"

    accepted = _upload(ready, JPG, "licence.jpg", content_type="application/octet-stream")
    assert accepted.status_code == 200
    assert [d["content_type"] for d in accepted.data["documents"]] == ["image/jpeg"]


@pytest.mark.django_db
def test_an_oversized_file_is_refused_by_name_and_nothing_is_kept(ready):
    big = b"%PDF-1.7\n" + b"x" * (10 * 1024 * 1024)
    refused = _upload(ready, big, "whole-house-scan.pdf")
    assert refused.status_code == 413
    assert refused.data["message_key"] == "portal.application.documentTooLarge"
    assert refused.data["params"] == {"name": "whole-house-scan.pdf", "max_mb": 10}
    with tenant_context(ready.id):
        assert models.PortalApplicationDocument.objects.count() == 0
    # …and a file at the limit is still welcome.
    assert _upload(ready, PNG, "plan.png").status_code == 200


@pytest.mark.django_db
def test_a_sixth_file_is_refused_and_the_five_stay(ready):
    for n in range(5):
        assert _upload(ready, PDF, f"page-{n}.pdf").status_code == 200
    sixth = _upload(ready, PDF, "page-5.pdf")
    assert sixth.status_code == 422
    assert sixth.data["message_key"] == "portal.application.documentLimit"
    assert sixth.data["params"]["max"] == 5
    with tenant_context(ready.id):
        assert models.PortalApplicationDocument.objects.count() == 5


@pytest.mark.django_db
def test_a_file_can_be_taken_back_before_sending(ready):
    first = _upload(ready, PDF, "wrong-scan.pdf").data["documents"][0]["id"]
    _upload(ready, PNG, "right-scan.png")
    after = _remove(ready, first)
    assert after.status_code == 200
    assert [d["name"] for d in after.data["documents"]] == ["right-scan.png"]


@pytest.mark.django_db
def test_a_file_on_an_abandoned_draft_never_reaches_the_utility(ready):
    """Nothing is filed in the document store until the application is SENT:
    the store is write-once for seven years and its register lists every row
    to staff, so a file on a draft nobody sent must never be there."""
    _upload(ready, PDF, "never-sent.pdf")
    with tenant_context(ready.id):
        assert StoredDocument.objects.count() == 0
        assert customers_models.ServiceRequestDocument.objects.count() == 0
        assert models.PortalApplicationDocument.objects.count() == 1


# ── the hand-over at submit ─────────────────────────────────────────────────


@pytest.mark.django_db
def test_on_submit_both_files_go_to_the_request_and_read_back_byte_for_byte(ready):
    _upload(ready, PDF, "tenancy-agreement.pdf")
    _upload(ready, PNG, "photo-id.png")
    sent = _send(ready)
    assert sent.status_code == 200, sent.data
    request_id = sent.data["request_id"]
    with tenant_context(ready.id):
        rows = list(
            customers_models.ServiceRequestDocument.objects.filter(request_id=request_id).order_by(
                "uploaded_at", "id"
            )
        )
        assert [r.name for r in rows] == ["tenancy-agreement.pdf", "photo-id.png"]
        assert {r.doc_type for r in rows} == {"other"}
        assert {r.verification_state for r in rows} == {"not_checked"}
        assert all(r.uploaded_by_id is None for r in rows)
        # THE CENTRAL ASSERTION: the bytes come back out of the store.
        assert doc_files.fetch_bytes(request_id, rows[0].id) == PDF
        assert doc_files.fetch_bytes(request_id, rows[1].id) == PNG
        # The held copies are gone — the store has them now.
        assert models.PortalApplicationDocument.objects.count() == 0
    # And the draft can no longer take a file.
    late = _upload(ready, PDF, "late.pdf")
    assert late.status_code == 409


@pytest.mark.django_db
def test_a_submit_with_no_files_is_unchanged(ready):
    sent = _send(ready)
    assert sent.status_code == 200
    with tenant_context(ready.id):
        assert customers_models.ServiceRequestDocument.objects.count() == 0


# ── the clerk's side ────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_the_clerk_opens_and_downloads_with_safe_headers_and_both_are_audited(
    ready, pine_clerk, audit_rows
):
    _upload(ready, PDF, 'lease "final".pdf')
    request_id = _send(ready).data["request_id"]
    with tenant_context(ready.id):
        doc = customers_models.ServiceRequestDocument.objects.get(request_id=request_id)

    view = _content(ready, pine_clerk, request_id, doc.id, "view")
    assert view.status_code == 200
    assert view.content == PDF
    assert view["Content-Type"] == "application/pdf"
    assert view["Content-Disposition"].startswith('inline; filename="lease final.pdf"')
    assert "filename*=UTF-8''lease%20%22final%22.pdf" in view["Content-Disposition"]
    assert view["X-Content-Type-Options"] == "nosniff"
    assert "default-src 'none'" in view["Content-Security-Policy"]
    assert "no-store" in view["Cache-Control"]

    download = _content(ready, pine_clerk, request_id, doc.id, "download")
    assert download.status_code == 200
    assert download["Content-Disposition"].startswith("attachment;")

    actions = [r["action"] for r in audit_rows]
    assert "customers.service_request_document.viewed" in actions
    assert "customers.service_request_document.downloaded" in actions


@pytest.mark.django_db
def test_another_utility_cannot_open_the_file(ready, oak_ridge, elena):
    _upload(ready, PDF, "tenancy-agreement.pdf")
    request_id = _send(ready).data["request_id"]
    with tenant_context(ready.id):
        doc = customers_models.ServiceRequestDocument.objects.get(request_id=request_id)
    foreign = _content(oak_ridge, elena, request_id, doc.id, "view")
    assert foreign.status_code == 404


@pytest.mark.django_db
def test_a_draft_token_from_another_utility_cannot_take_a_file(ready, oak_ridge, elena):
    switch_on(oak_ridge, elena)
    refused = _upload(oak_ridge, PDF, "x.pdf")
    assert refused.status_code == 404
