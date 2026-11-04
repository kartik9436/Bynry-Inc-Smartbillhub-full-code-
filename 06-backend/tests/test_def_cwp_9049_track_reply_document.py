# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-CWP-9049 — after a clerk's *Ask for more*, the applicant had no
#           way to send a second document. Found by the 21-walk (W14,
#           2026-10-02): Track said *More info needed* and nothing else; the
#           sent application's upload door answers 409.
# Rules:    BR-CWP-023 (the track lockout) · BR-CWP-024 (progress, never data)
#           · BR-SHL-031 (10 MB) · CR-158-BRC10 (PDF/JPG/PNG, five per
#           application) · BR-TEN-003 (existence must not leak) · hard rule 7
# Tests:    this file
# ───────────────────────────────────────────────────────
"""The Track page's *Add a document*, through the route a browser calls.

⚠ **WHAT WOULD MAKE THESE PASS WRONGLY, ASKED FIRST** (law 7 habit 2):
  * *"the file was accepted"* passes if the door files it nowhere — so the
    happy case reads the BYTES back off the REQUEST, through customers' own
    reader, and counts the request's files before and after;
  * *"a request not asked is refused"* passes if every upload is refused —
    so the same file on the same request is accepted the moment a clerk asks;
  * *"another utility cannot"* passes if the reference simply does not exist
    there — so the probe uses the REAL reference and the REAL second fact.

RUN WITH `JOBS_EAGER=false --reuse-db`.
"""

from __future__ import annotations

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.customers import models as customers_models
from apps.customers import service_request as rules
from apps.customers import service_request_documents as doc_files
from apps.customers import service_request_service as sr
from apps.portal import guest_api
from core.tenancy import tenant_context
from tests.test_cr158_portal_application_documents import (  # noqa: F401
    PDF,
    PNG,
    _draft,
    _send,
    _upload,
    docs_dir,
    ready,
)
from tests.test_us_cwp_helpers import *  # noqa: F401,F403
from tests.test_us_cwp_helpers import switch_on
from tests.test_us_ten_helpers import api_call

HTML = b"<html><script>fetch('/api/x')</script></html>"
ZIP = "78704"  # `COMPLETE`'s address resolves to Pine Hill's seeded 31 Palm Ct


def _reply(tenant, reference, second_fact, payload, name, content_type="application/pdf"):
    return api_call(
        guest_api.track_document,
        "post",
        f"/api/{tenant.subdomain}/portal/public/track/documents",
        tenant=tenant,
        data={
            "reference": reference,
            "second_fact": second_fact,
            "file": SimpleUploadedFile(name, payload, content_type=content_type),
        },
        body_format="multipart",
        headers={"X-Forwarded-For": "203.0.113.49"},
    )


def _track(tenant, reference, second_fact):
    return api_call(
        guest_api.track,
        "post",
        f"/api/{tenant.subdomain}/portal/public/track",
        tenant=tenant,
        data={"reference": reference, "second_fact": second_fact},
        headers={"X-Forwarded-For": "203.0.113.49"},
    )


def _sent_with_one_file(tenant):
    _upload(tenant, PDF, "tenancy-agreement.pdf")
    sent = _send(tenant)
    assert sent.status_code == 200, sent.data
    return sent.data["request_id"], sent.data["reference"]


def _ask_for_more(clerk, tenant, request_id):
    with tenant_context(tenant.id):
        moved = sr.transition(
            clerk,
            request_id,
            rules.REQUEST_INFO,
            reason="ID unreadable",
            info_needed=[rules.NEEDS_IDENTITY_PROOF],
            message_to_applicant="Please send a clearer photo of your ID.",
        )
        assert moved.state == rules.MORE_INFO


def _phone():
    return "(512) 555-7730"  # `COMPLETE`'s phone — the second fact Track accepts


@pytest.mark.django_db
def test_track_says_a_file_may_be_sent_only_once_a_clerk_has_asked(ready, pine_clerk):
    request_id, reference = _sent_with_one_file(ready)
    before = _track(ready, reference, _phone())
    assert before.status_code == 200, before.data
    assert before.data["can_add_document"] is False
    assert before.data["documents_left"] == 0

    _ask_for_more(pine_clerk, ready, request_id)
    after = _track(ready, reference, _phone())
    assert after.data["status"] == rules.MORE_INFO
    assert after.data["can_add_document"] is True
    assert after.data["documents_left"] == 4, "five per application, one already sent"


@pytest.mark.django_db
def test_a_reply_lands_on_the_request_the_clerk_is_waiting_on(ready, pine_clerk, audit_rows):
    request_id, reference = _sent_with_one_file(ready)
    _ask_for_more(pine_clerk, ready, request_id)

    sent = _reply(ready, reference, _phone(), PNG, "clearer-id.png", "image/png")
    assert sent.status_code == 200, sent.data
    assert sent.data["documents_left"] == 3

    with tenant_context(ready.id):
        rows = list(
            customers_models.ServiceRequestDocument.objects.filter(request_id=request_id).order_by(
                "uploaded_at", "id"
            )
        )
        assert [r.name for r in rows] == ["tenancy-agreement.pdf", "clearer-id.png"]
        assert rows[1].uploaded_by_id is None and rows[1].verification_state == "not_checked"
        # THE CENTRAL ASSERTION: the bytes come back off the request.
        assert doc_files.fetch_bytes(request_id, rows[1].id) == PNG
        # The state does not move — a clerk decides straight from more_info.
        request = customers_models.ServiceRequest.objects.get(pk=request_id)
        assert request.state == rules.MORE_INFO
        # The clerk's History shows the customer replied, and so may the customer.
        replied = customers_models.ServiceRequestEvent.objects.filter(
            request_id=request_id, note_type="customer_replied:document"
        )
        assert [(e.note, e.internal) for e in replied] == [("clearer-id.png", False)]
    actions = [r["action"] for r in audit_rows]
    assert "service_request.customer_replied" in actions
    assert "customers.service_request_document.attached_from_portal" in actions


@pytest.mark.django_db
def test_a_request_nobody_asked_about_refuses_a_file(ready, pine_clerk):
    request_id, reference = _sent_with_one_file(ready)
    refused = _reply(ready, reference, _phone(), PDF, "unasked.pdf")
    assert refused.status_code == 409, refused.data
    with tenant_context(ready.id):
        assert customers_models.ServiceRequestDocument.objects.filter(request_id=request_id).count() == 1
    # The same file, the moment a clerk asks, is taken — the refusal was the state.
    _ask_for_more(pine_clerk, ready, request_id)
    assert _reply(ready, reference, _phone(), PDF, "unasked.pdf").status_code == 200


@pytest.mark.django_db
def test_a_decided_request_refuses_a_file(ready, pine_clerk):
    request_id, reference = _sent_with_one_file(ready)
    _ask_for_more(pine_clerk, ready, request_id)
    with tenant_context(ready.id):
        sr.refuse_request(
            pine_clerk,
            request_id,
            reason="Not our area",
            reason_code=rules.REFUSAL_REASONS[0],
            message_to_applicant="We cannot serve this address.",
        )
    refused = _reply(ready, reference, _phone(), PDF, "late.pdf")
    assert refused.status_code == 409, refused.data


@pytest.mark.django_db
def test_the_file_rules_are_the_applications_own(ready, pine_clerk):
    request_id, reference = _sent_with_one_file(ready)
    _ask_for_more(pine_clerk, ready, request_id)
    wrong = _reply(ready, reference, _phone(), HTML, "notes.pdf")
    assert wrong.status_code == 415
    big = _reply(ready, reference, _phone(), PDF + b"x" * (10 * 1024 * 1024), "scan.pdf")
    assert big.status_code == 413
    # Four more fit (five per application), the sixth is refused by name.
    for n in range(4):
        assert _reply(ready, reference, _phone(), PDF, f"page-{n}.pdf").status_code == 200
    sixth = _reply(ready, reference, _phone(), PDF, "page-5.pdf")
    assert sixth.status_code == 422, sixth.data
    assert sixth.data["message_key"] == "portal.application.documentLimit"
    with tenant_context(ready.id):
        assert customers_models.ServiceRequestDocument.objects.filter(request_id=request_id).count() == 5


@pytest.mark.django_db
def test_a_wrong_second_fact_is_not_found_and_stores_nothing(ready, pine_clerk):
    request_id, reference = _sent_with_one_file(ready)
    _ask_for_more(pine_clerk, ready, request_id)
    miss = _reply(ready, reference, "99999", PDF, "guess.pdf")
    assert miss.status_code == 409
    assert miss.data["message_key"] == "portal.track.notFound"
    with tenant_context(ready.id):
        assert customers_models.ServiceRequestDocument.objects.filter(request_id=request_id).count() == 1


@pytest.mark.django_db
def test_another_utility_cannot_send_a_file_to_this_request(ready, pine_clerk, oak_ridge, elena):
    request_id, reference = _sent_with_one_file(ready)
    _ask_for_more(pine_clerk, ready, request_id)
    switch_on(oak_ridge, elena)
    foreign = _reply(oak_ridge, reference, _phone(), PDF, "foreign.pdf")
    assert foreign.status_code in (404, 409)
    assert foreign.data.get("message_key") in ("portal.track.notFound", "errors.not-found")
    with tenant_context(ready.id):
        assert customers_models.ServiceRequestDocument.objects.filter(request_id=request_id).count() == 1
