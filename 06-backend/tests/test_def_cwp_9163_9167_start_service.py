# ── Trace ──────────────────────────────────────────────
# Defects:  DEF-CWP-9166 (the applicant can VIEW their own uploaded file) ·
#           DEF-CWP-9167 (one attach row per required document — PO ruling
#           2026-10-02, option A — and the requirement reaches the clerk) ·
#           DEF-CWP-9163 (the mailing address, if different, is captured and
#           becomes the account's kind='mailing' row through the customers
#           module's own door)
# Rules:    BR-TEN-003 (existence must not leak) · BR-CWP-026 (a public form
#           never changes an account) · CLAUDE.md hard rule 8 (mailing is the
#           named exception, never a premises address)
# ───────────────────────────────────────────────────────
"""The start-service form's five defects, the server's half.

⚠ **WHAT WOULD MAKE THESE PASS WRONGLY, ASKED FIRST** (law 7 habit 2):
  * *"the applicant can open their file"* passes if ANY token opens ANY file —
    so the same file is asked for under another draft's token, another
    utility and after it was removed, and each must be 404;
  * *"the requirement is recorded"* passes if every file is recorded as the
    same thing — so two files carry two different requirements and both are
    read back, on the draft AND on the clerk's request;
  * *"the mailing address reaches the account"* passes if the account door
    copies the SERVICE address — so the mailing address here is a different
    street in a different city, and the premises is checked untouched.

RUN WITH `JOBS_EAGER=false --reuse-db`.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.customers import models as customers_models
from apps.customers import portal_seam
from apps.customers import service_request_reads
from apps.customers import services as customer_services
from apps.portal import applications, guest_api, models
from core.tenancy import tenant_context
from tests.test_us_cwp_helpers import *  # noqa: F401,F403
from tests.test_us_cwp_helpers import brand_fully, seed_addresses_for, switch_on
from tests.test_us_ten_helpers import api_call

TOKEN = "d9163a4e-5f6a-4b7c-8d9e-0f1a2b3c4d5e"
OTHER_TOKEN = "d9167b5f-6a7b-4c8d-9e0f-1a2b3c4d5e6f"

PDF = b"%PDF-1.7\n1 0 obj\n<< /Title (Proof of address) >>\n" + b"T" * 3000 + b"\n%%EOF"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + b"P" * 2000

COMPLETE = {
    "address_as_given": "31 Palm Ct",
    "service_codes": ["water", "solar"],
    "applicant_kind": "person",
    "first_name": "Amara",
    "last_name": "Okafor",
    "email": "amara.okafor@example.test",
    "phone": "(281) 555-0144",
    "account_type_code": "residential",  # DEF-CWP-9818 (required at Send)
}

MAILING = {
    "mailing_same_as_service": False,
    "mailing_line1": "PO Box 4417",
    "mailing_line2": "",
    "mailing_city": "Ottumwa",
    "mailing_state": "Iowa",
    "mailing_postal_code": "52501",
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
    _save(pine_hill, {})
    return pine_hill


def _save(tenant, extra, token=TOKEN):
    return api_call(
        guest_api.application_draft,
        "put",
        f"/api/{tenant.subdomain}/portal/public/applications/{token}",
        tenant=tenant,
        data={
            **COMPLETE,
            "requested_start": (date.today() + timedelta(days=21)).isoformat(),
            **extra,
        },
        token=token,
    )


def _upload(tenant, payload, name, content_type, requirement=None, token=TOKEN):
    data = {"file": SimpleUploadedFile(name, payload, content_type=content_type)}
    if requirement is not None:
        data["requirement"] = requirement
    return api_call(
        guest_api.application_documents,
        "post",
        f"/api/{tenant.subdomain}/portal/public/applications/{token}/documents",
        tenant=tenant,
        data=data,
        body_format="multipart",
        token=token,
    )


def _view(tenant, document_id, token=TOKEN):
    return api_call(
        guest_api.application_document_content,
        "get",
        f"/api/{tenant.subdomain}/portal/public/applications/{token}/documents/{document_id}/content",
        tenant=tenant,
        token=token,
        document_id=str(document_id),
    )


def _remove(tenant, document_id, token=TOKEN):
    return api_call(
        guest_api.application_document,
        "delete",
        f"/api/{tenant.subdomain}/portal/public/applications/{token}/documents/{document_id}",
        tenant=tenant,
        token=token,
        document_id=str(document_id),
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


def _by_name(draft_body, name):
    return next(one for one in draft_body["documents"] if one["name"] == name)


# ── DEF-CWP-9167 · one attach row per required document ─────────────────────


@pytest.mark.django_db
def test_the_draft_names_the_documents_it_asks_for_in_order(ready):
    body = _save(ready, {}).data
    assert body["document_requirements"] == ["photo_id", "proof_of_address"]


@pytest.mark.django_db
def test_each_file_records_which_requirement_it_meets(ready):
    _upload(ready, PNG, "licence.png", "image/png", requirement="photo_id")
    answer = _upload(ready, PDF, "power-bill.pdf", "application/pdf", requirement="proof_of_address")
    assert answer.status_code == 200, answer.data
    assert _by_name(answer.data, "licence.png")["requirement"] == "photo_id"
    assert _by_name(answer.data, "power-bill.pdf")["requirement"] == "proof_of_address"


@pytest.mark.django_db
def test_a_file_with_no_requirement_still_works_as_other(ready):
    answer = _upload(ready, PDF, "old-style.pdf", "application/pdf")
    assert answer.status_code == 200, answer.data
    assert _by_name(answer.data, "old-style.pdf")["requirement"] is None


@pytest.mark.django_db
def test_an_unknown_requirement_is_refused_by_name_and_nothing_is_kept(ready):
    refused = _upload(ready, PDF, "x.pdf", "application/pdf", requirement="birth_certificate")
    assert refused.status_code == 422, refused.data
    assert refused.data["message_key"] == "portal.application.documentRequirementUnknown"
    with tenant_context(ready.id):
        assert models.PortalApplicationDocument.objects.count() == 0


@pytest.mark.django_db
def test_on_send_the_clerk_sees_which_file_is_which(ready):
    _upload(ready, PNG, "licence.png", "image/png", requirement="photo_id")
    _upload(ready, PDF, "power-bill.pdf", "application/pdf", requirement="proof_of_address")
    _upload(ready, PDF, "anything.pdf", "application/pdf")
    sent = _send(ready)
    assert sent.status_code == 200, sent.data
    with tenant_context(ready.id):
        kinds = dict(
            customers_models.ServiceRequestDocument.objects.filter(
                request_id=sent.data["request_id"]
            ).values_list("name", "doc_type")
        )
    assert kinds == {
        "licence.png": "proof_of_identity",
        "power-bill.pdf": "proof_of_address_or_occupancy",
        "anything.pdf": "other",
    }


# ── DEF-CWP-9166 · the applicant views their own file ───────────────────────


@pytest.mark.django_db
def test_the_applicant_opens_their_own_file_with_safe_headers(ready, audit_rows):
    body = _upload(ready, PDF, 'bill "march".pdf', "application/pdf", requirement="proof_of_address").data
    document_id = _by_name(body, 'bill "march".pdf')["id"]
    view = _view(ready, document_id)
    assert view.status_code == 200
    assert view.content == PDF
    assert view["Content-Type"] == "application/pdf"
    assert view["Content-Disposition"].startswith('inline; filename="bill march.pdf"')
    assert view["X-Content-Type-Options"] == "nosniff"
    assert "default-src 'none'" in view["Content-Security-Policy"]
    assert "no-store" in view["Cache-Control"]
    assert "portal.application_document.viewed" in [r["action"] for r in audit_rows]


@pytest.mark.django_db
def test_another_draft_cannot_open_the_file(ready):
    body = _upload(ready, PNG, "licence.png", "image/png", requirement="photo_id").data
    document_id = _by_name(body, "licence.png")["id"]
    _save(ready, {}, token=OTHER_TOKEN)
    # Proved first: the same id IS readable under its own token.
    assert _view(ready, document_id).status_code == 200
    assert _view(ready, document_id, token=OTHER_TOKEN).status_code == 404


@pytest.mark.django_db
def test_another_utility_cannot_open_the_file(ready, oak_ridge, elena):
    body = _upload(ready, PNG, "licence.png", "image/png", requirement="photo_id").data
    document_id = _by_name(body, "licence.png")["id"]
    switch_on(oak_ridge, elena)
    assert _view(oak_ridge, document_id).status_code == 404


@pytest.mark.django_db
def test_a_removed_file_and_a_nonsense_id_are_not_found(ready):
    body = _upload(ready, PNG, "licence.png", "image/png", requirement="photo_id").data
    document_id = _by_name(body, "licence.png")["id"]
    _remove(ready, document_id)
    assert _view(ready, document_id).status_code == 404
    assert _view(ready, "not-a-uuid").status_code == 404


@pytest.mark.django_db
def test_a_sent_applications_files_are_no_longer_served_to_the_guest(ready):
    body = _upload(ready, PNG, "licence.png", "image/png", requirement="photo_id").data
    document_id = _by_name(body, "licence.png")["id"]
    assert _send(ready).status_code == 200
    assert _view(ready, document_id).status_code == 404


# ── DEF-CWP-9163 · the mailing address, if different ────────────────────────


@pytest.mark.django_db
def test_same_as_service_is_the_default_and_asks_for_nothing(ready):
    body = _save(ready, {}).data
    assert body["mailing_same_as_service"] is True
    with tenant_context(ready.id):
        draft = applications.draft_row(ready.id, TOKEN)
        assert "mailing" not in applications.missing_before_submit(draft)


@pytest.mark.django_db
def test_an_unticked_box_is_saved_and_the_state_name_becomes_its_code(ready):
    body = _save(ready, MAILING).data
    assert body["mailing_same_as_service"] is False
    assert body["mailing_line1"] == "PO Box 4417"
    assert body["mailing_city"] == "Ottumwa"
    assert body["mailing_state"] == "IA"
    assert body["mailing_postal_code"] == "52501"


@pytest.mark.django_db
def test_a_malformed_zip_and_an_unknown_state_are_refused(ready):
    bad_zip = _save(ready, {**MAILING, "mailing_postal_code": "5250"})
    assert bad_zip.status_code == 422
    assert bad_zip.data["message_key"] == "portal.application.mailingZipFormat"
    bad_state = _save(ready, {**MAILING, "mailing_state": "Atlantis"})
    assert bad_state.status_code == 422
    assert bad_state.data["message_key"] == "portal.application.mailingStateUnknown"


@pytest.mark.django_db
def test_an_unticked_box_with_no_address_is_refused_at_send_naming_the_step(ready):
    _save(ready, {"mailing_same_as_service": False, "mailing_line1": "PO Box 4417"})
    refused = _send(ready)
    assert refused.status_code == 422, refused.data
    assert refused.data["message_key"] == "portal.application.stepIncomplete"
    assert refused.data["params"]["step"] == "mailing"


@pytest.mark.django_db
def test_the_clerk_sees_it_and_the_account_door_carries_it_as_mailing(ready):
    _save(ready, MAILING)
    sent = _send(ready)
    assert sent.status_code == 200, sent.data
    request_id = sent.data["request_id"]
    with tenant_context(ready.id):
        request = customers_models.ServiceRequest.objects.get(pk=request_id)
        expected = {
            "line1": "PO Box 4417",
            "line2": None,
            "city": "Ottumwa",
            "state": "IA",
            "postal_code": "52501",
        }
        assert portal_seam.application_mailing_address(request) == expected
        detail = service_request_reads.detail(request_id)
        assert detail["applicant"]["application_mailing_address"] == expected
        # The customers module's own account-opening door carries it as the
        # ONE kind='mailing' row — and nothing the clerk typed is overridden.
        carried = customer_services._carry_request_decisions({}, request_id)
        assert carried["addresses"] == [
            {"kind": "mailing", "line1": "PO Box 4417", "city": "Ottumwa", "state": "IA", "postal_code": "52501"}
        ]
        typed = [{"kind": "mailing", "line1": "1 Clerk Way"}]
        assert customer_services._carry_request_decisions({"addresses": typed}, request_id)[
            "addresses"
        ] == typed


@pytest.mark.django_db
def test_a_ticked_box_carries_no_mailing_address(ready):
    _save(ready, {**MAILING, "mailing_same_as_service": True})
    request_id = _send(ready).data["request_id"]
    with tenant_context(ready.id):
        request = customers_models.ServiceRequest.objects.get(pk=request_id)
        assert portal_seam.application_mailing_address(request) is None
        assert "addresses" not in customer_services._carry_request_decisions({}, request_id)
