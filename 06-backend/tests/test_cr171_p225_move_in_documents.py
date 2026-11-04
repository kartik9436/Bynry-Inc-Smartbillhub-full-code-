"""`CR-171-BRC10` P2.25 — a document uploaded on the move-in wizard waits, then files.

IMAGE 39: the Customer step's *Documents* table, with no request behind it. The
clerk uploads *Tenancy or deed* before the account exists, so the file needs
somewhere to wait until **Complete**. Lane MVI-IDN left the carry to this lane
(CR §9.IDN-2, *"Not here, stated"*): build it the way the REQUEST's carry works
(`move_in_people.carry_request_documents`), on the existing document store.

THE WORKED CASE: Dana starts a move-in for **Nilesh G** at 8 Quarry Lane, 3B,
and uploads `deed.pdf` as *Tenancy or deed*. The bytes are stored once, now, as
an ACCOUNT DOCUMENT whose filing card id is minted now and carried in the
draft. Nothing is filed yet — there is no account. At Complete the card is
written on the new account with THAT id, pointing at THAT stored document, in
the KYC folder, and `documents_carried` counts it. No second stored object.

Refused by name and writing nothing: a card nobody staged, a card staged in
another utility, a card already filed, the same card twice, a stored document
of another kind (a request's), a document type the checklist does not know.
"""

from __future__ import annotations

import uuid

import pytest

from apps.customers import move_in_documents, move_in_people
from apps.customers import models as customers_models
from apps.customers import service_request_documents as doc_files
from apps.customers import service_request_service as sr
from apps.customers import services as customers_services
from apps.customers.account_document_models import AccountDocument
from core import errors
from tests import identity_fixtures
from tests.isolation_helpers import (  # noqa: F401 — fixtures used by name
    requires_postgres,
    rls,
    rls_probe_role,
)
from tests.test_br_cus_1077_move_in_job import _move_in_request, _served_unit
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import brazos, dana, lonestar, marcus, tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db

PERSON = "Nilesh G"
PDF = b"%PDF-1.7\n1 0 obj\n<< /Title (Deed, 8 Quarry Lane) >>\n" + b"D" * 2000 + b"\n%%EOF"
DEED = customers_models.ServiceRequestDocument.DOC_TENANCY_OR_DEED


@pytest.fixture()
def docs_dir(tmp_path, settings):
    settings.DOCUMENT_STORAGE_BACKEND = "filesystem"
    settings.DOCUMENT_STORAGE_ALLOW_FILESYSTEM = True
    settings.DOCUMENT_STORAGE_DIR = str(tmp_path / "documents")
    return tmp_path / "documents"


class _Upload:
    def __init__(self, payload: bytes, *, name: str, content_type: str):
        self._payload = payload
        self.name = name
        self.content_type = content_type

    def read(self) -> bytes:
        return self._payload


def _payload(**extra):
    body = {
        "account_type": "residential",
        "opened_at": "2026-10-01",
        "contact": {"full_name": PERSON, "email": "nilesh@example.test"},
        "customer": identity_fixtures.customer_block(PERSON, kind="person"),
    }
    body.update(extra)
    return body


def _stage(actor, *, name="deed.pdf", doc_type=DEED, payload=PDF, content_type="application/pdf"):
    return move_in_documents.stage(
        actor, {"doc_type": doc_type, "name": name}, _Upload(payload, name=name, content_type=content_type)
    )


# ═══════════════════════════════════════════════════════════════════════════
# The wait, then the filing
# ═══════════════════════════════════════════════════════════════════════════
def test_a_staged_document_is_stored_now_and_filed_at_complete_by_its_card(brazos, dana, docs_dir):
    from apps.tenancy.document_models import StoredDocument

    with tenant_ctx(brazos):
        _premises, unit = _served_unit(dana, brazos, label="3B", address="8 Quarry Lane")
        staged = _stage(dana)
        assert staged["name"] == "deed.pdf"
        assert staged["doc_type"] == DEED
        assert staged["size_bytes"] == len(PDF)
        card = staged["card_id"]
        # Stored now, filed nowhere yet: there is no account to file it on.
        stored = StoredDocument.objects.get(source_id=card)
        assert stored.kind == "account_document" and stored.source_type == "account_document"
        assert not AccountDocument.objects.filter(pk=card).exists()
        stored_before = StoredDocument.objects.count()

        result = customers_services.move_in_to_unit(
            dana, unit["id"], _payload(documents=[{"card_id": card, "doc_type": DEED}])
        )
        assert result["people"]["documents_carried"] == 1
        filing = AccountDocument.objects.get(account_id=result["id"])
        assert str(filing.pk) == card  # the card minted at upload
        assert filing.document_id == stored.pk  # by reference
        assert filing.doc_type == "kyc"
        assert filing.uploaded_by_id == dana.user.id
        assert StoredDocument.objects.count() == stored_before  # no copy


def test_the_staged_and_the_requests_documents_are_counted_together(brazos, dana, docs_dir):
    with tenant_ctx(brazos):
        _premises, unit = _served_unit(dana, brazos, label="3B", address="8 Quarry Lane")
        request = _move_in_request(dana, address=str(unit["unit_no"]))
        doc_files.attach_file(
            dana,
            request.id,
            {"doc_type": customers_models.ServiceRequestDocument.DOC_PROOF_OF_IDENTITY, "name": "id.pdf"},
            _Upload(PDF, name="id.pdf", content_type="application/pdf"),
        )
        sr.approve_and_raise(dana, request.id)
        staged = _stage(dana)
        result = customers_services.move_in_to_unit(
            dana,
            unit["id"],
            _payload(
                service_request_id=str(request.id),
                documents=[{"card_id": staged["card_id"], "doc_type": DEED}],
            ),
        )
        assert result["people"]["documents_carried"] == 2
        assert AccountDocument.objects.filter(account_id=result["id"]).count() == 2


def test_no_documents_key_changes_nothing(brazos, dana):
    with tenant_ctx(brazos):
        _premises, unit = _served_unit(dana, brazos)
        result = customers_services.move_in_to_unit(dana, unit["id"], _payload())
    assert result["people"] == {"co_owners": 0, "company_updated": [], "documents_carried": 0}


# ═══════════════════════════════════════════════════════════════════════════
# Refusals — named, and nothing written
# ═══════════════════════════════════════════════════════════════════════════
def _refused(actor, tenant, rows, *, key, field):
    with tenant_ctx(tenant):
        _premises, unit = _served_unit(actor, tenant, label=f"R{uuid.uuid4().hex[:4]}")
        with pytest.raises(errors.ValidationError) as caught:
            customers_services.move_in_to_unit(actor, unit["id"], _payload(documents=rows))
        assert caught.value.message_key == key
        assert field in [fe["field"] for fe in caught.value.field_errors]
        assert customers_models.Account.objects.filter(unit_id=unit["id"]).count() == 0


def test_a_card_nobody_staged_is_refused(brazos, dana, docs_dir):
    _refused(
        dana,
        brazos,
        [{"card_id": str(uuid.uuid4()), "doc_type": DEED}],
        key="customers.moveIn.documents.notStaged",
        field="documents[0]",
    )


def test_a_card_already_filed_is_refused(brazos, dana, docs_dir):
    with tenant_ctx(brazos):
        _premises, unit = _served_unit(dana, brazos, label="3B")
        staged = _stage(dana)
        row = {"card_id": staged["card_id"], "doc_type": DEED}
        customers_services.move_in_to_unit(dana, unit["id"], _payload(documents=[row]))
    _refused(dana, brazos, [row], key="customers.moveIn.documents.notStaged", field="documents[0]")


def test_the_same_card_twice_is_refused(brazos, dana, docs_dir):
    with tenant_ctx(brazos):
        staged = _stage(dana)
    row = {"card_id": staged["card_id"], "doc_type": DEED}
    _refused(dana, brazos, [row, row], key="customers.moveIn.documents.twice", field="documents[1]")


def test_a_requests_stored_document_cannot_be_filed_through_this_key(brazos, dana, docs_dir):
    with tenant_ctx(brazos):
        request = _move_in_request(dana, address="Unit 9")
        card = doc_files.attach_file(
            dana, request.id, {"doc_type": DEED, "name": "deed.pdf"},
            _Upload(PDF, name="deed.pdf", content_type="application/pdf"),
        )
    # The request card's id IS a stored document's `source_id` — of a REQUEST
    # document. Only the kind and source type tell it from a staged card.
    _refused(
        dana,
        brazos,
        [{"card_id": card["id"], "doc_type": DEED}],
        key="customers.moveIn.documents.notStaged",
        field="documents[0]",
    )


def test_a_type_the_checklist_does_not_know_is_refused(brazos, dana, docs_dir):
    with tenant_ctx(brazos):
        staged = _stage(dana)
    _refused(
        dana,
        brazos,
        [{"card_id": staged["card_id"], "doc_type": "horoscope"}],
        key="customers.serviceRequest.documentTypeUnknown",
        field="documents[0].doc_type",
    )


def test_staging_refuses_what_an_account_upload_refuses(brazos, dana, docs_dir):
    from apps.customers.account_documents import UploadRefused

    with tenant_ctx(brazos):
        with pytest.raises(UploadRefused) as caught:
            _stage(dana, name="run.exe", content_type="application/x-msdownload", payload=b"MZ" * 50)
        assert caught.value.status == 415
        with pytest.raises(errors.ValidationError) as caught:
            _stage(dana, doc_type="horoscope")
        assert caught.value.message_key == "customers.serviceRequest.documentTypeUnknown"


# ═══════════════════════════════════════════════════════════════════════════
# The checklist a clerk reads (image 33, *Required ones come from Settings*)
# ═══════════════════════════════════════════════════════════════════════════
def test_the_required_list_is_the_move_in_checklist_in_designed_order(brazos, dana):
    with tenant_ctx(brazos):
        assert move_in_documents.required_types() == []  # ships unticked (BR-CUS-095)
        sr.set_document_requirement(dana, request_type="move_in", doc_type=DEED, required=True)
        sr.set_document_requirement(
            dana,
            request_type="move_in",
            doc_type=customers_models.ServiceRequestDocument.DOC_PROOF_OF_IDENTITY,
            required=True,
        )
        assert move_in_documents.required_types() == ["proof_of_identity", DEED]


def test_the_payload_key_is_admitted_by_the_move_in_door():
    assert "documents" in move_in_people.PAYLOAD_KEYS
    assert set(move_in_people.PAYLOAD_KEYS) <= customers_services.MOVE_IN_FIELDS


# ═══════════════════════════════════════════════════════════════════════════
# The doors — a billing clerk stages and reads (AdminOrClerk)
# ═══════════════════════════════════════════════════════════════════════════
def _view(actor, tenant, method, path, view, data=None, **kwargs):
    from rest_framework.test import APIRequestFactory, force_authenticate

    factory = APIRequestFactory()
    request = (
        factory.post(path, data, format="multipart")
        if method == "post"
        else factory.get(path, data or {})
    )
    force_authenticate(request, user=actor.user)
    request.tenant_role = actor.role
    request.tenant_id = tenant.id
    with tenant_ctx(tenant):
        return view(request, **kwargs)


def test_a_clerk_stages_through_the_door_and_reads_the_checklist(brazos, marcus, docs_dir):
    from django.core.files.uploadedfile import SimpleUploadedFile

    from apps.customers import move_in_documents_api as api

    upload = SimpleUploadedFile("deed.pdf", PDF, content_type="application/pdf")
    response = _view(
        marcus, brazos, "post", "/api/x/move-ins/documents", api.move_in_documents,
        {"file": upload, "doc_type": DEED},
    )
    assert response.status_code == 201, response.data
    assert response.data["name"] == "deed.pdf"
    card = response.data["card_id"]
    opened = _view(
        marcus, brazos, "get", f"/api/x/move-ins/documents/{card}/content",
        api.move_in_document_content, card_id=card,
    )
    assert opened.status_code == 200
    assert opened.content == PDF
    assert opened["Content-Disposition"].startswith("inline")
    assert opened["X-Content-Type-Options"] == "nosniff"
    required = _view(marcus, brazos, "get", "/api/x/move-ins/documents/required", api.move_in_documents_required)
    assert required.status_code == 200
    assert required.data == {"required": []}


# ═══════════════════════════════════════════════════════════════════════════
# PostgreSQL — the whole road, and another utility's card
# ═══════════════════════════════════════════════════════════════════════════
@requires_postgres
@pytest.mark.isolation
def test_pg_filed_at_complete_and_another_utilitys_card_is_not_found(
    brazos, lonestar, dana, docs_dir, rls
):
    """On PostgreSQL: the staged card files inside `_move_in`'s transaction
    (its savepoint, law 14), and a card staged at Brazos Bend is NOT STAGED to
    Lone Star Ridge — the same answer as a card nobody staged (HR-1)."""
    with tenant_ctx(brazos):
        _premises, unit = _served_unit(dana, brazos, label="3B")
        staged = _stage(dana)
        result = customers_services.move_in_to_unit(
            dana, unit["id"], _payload(documents=[{"card_id": staged["card_id"], "doc_type": DEED}])
        )
        assert AccountDocument.objects.filter(account_id=result["id"], pk=staged["card_id"]).exists()
        other = _stage(dana, name="lease.pdf")
    # Lone Star Ridge is a water-only fixture, so its side is asked at the
    # door that decides it — `move_in_people.pop`, before any write.
    with tenant_ctx(lonestar):
        with pytest.raises(errors.ValidationError) as caught:
            move_in_people.pop({"documents": [{"card_id": other["card_id"], "doc_type": DEED}]})
        assert caught.value.message_key == "customers.moveIn.documents.notStaged"
    with tenant_ctx(brazos):  # and it is still staged at home
        assert move_in_people.pop(
            {"documents": [{"card_id": other["card_id"], "doc_type": DEED}]}
        ).documents


# ═══════════════════════════════════════════════════════════════════════════
# P2.24 — a co-owner's photo ID, filed once the account exists (image 25)
# ═══════════════════════════════════════════════════════════════════════════
RIYA = {"full_name": "Riya G", "relationship": "Spouse", "responsible_for_bills": True}


def test_a_co_owners_photo_id_is_filed_on_the_account_and_named_on_the_row(brazos, dana, docs_dir):
    """Riya G was added at Complete with *No ID*; the clerk uploads her photo
    ID on the Account tab. It is filed on the account (KYC) and the co-owner
    row points at that filing — the read then says she has an ID."""
    from apps.customers import co_owner_models, move_in_people as people

    with tenant_ctx(brazos):
        _premises, unit = _served_unit(dana, brazos, label="3B")
        result = customers_services.move_in_to_unit(dana, unit["id"], _payload(co_owners=[RIYA]))
        row = co_owner_models.AccountCoOwner.objects.get(account_id=result["id"])
        assert row.photo_id_document_id is None
        answer = people.attach_photo_id(
            dana, result["id"], row.pk, {"name": "riya-id.jpg"},
            _Upload(b"\xff\xd8\xff" + b"J" * 900, name="riya-id.jpg", content_type="image/jpeg"),
        )
        row.refresh_from_db()
        filing = AccountDocument.objects.get(pk=row.photo_id_document_id)
        assert str(filing.account_id) == str(result["id"]) and filing.doc_type == "kyc"
        assert answer == {"co_owner_id": str(row.pk), "photo_id": True, "document_id": str(filing.pk)}


def test_a_photo_id_for_another_accounts_co_owner_is_not_found(brazos, dana, docs_dir):
    from apps.customers import co_owner_models, move_in_people as people

    with tenant_ctx(brazos):
        _p1, unit_a = _served_unit(dana, brazos, label="A1")
        _p2, unit_b = _served_unit(dana, brazos, label="B1", address="9 Birch Ct")
        first = customers_services.move_in_to_unit(dana, unit_a["id"], _payload(co_owners=[RIYA]))
        second = customers_services.move_in_to_unit(dana, unit_b["id"], _payload())
        row = co_owner_models.AccountCoOwner.objects.get(account_id=first["id"])
        with pytest.raises(errors.NotFoundError):
            people.attach_photo_id(
                dana, second["id"], row.pk, {"name": "x.jpg"},
                _Upload(b"\xff\xd8\xff" + b"J" * 900, name="x.jpg", content_type="image/jpeg"),
            )
        assert AccountDocument.objects.filter(account_id=second["id"]).count() == 0


def test_the_photo_id_door_answers_201_and_the_details_read_serves_the_handle(brazos, marcus, dana, docs_dir):
    from django.core.files.uploadedfile import SimpleUploadedFile

    from apps.customers import co_owner_models
    from apps.customers import move_in_documents_api as api
    from apps.customers import move_record_reads

    with tenant_ctx(brazos):
        _premises, unit = _served_unit(dana, brazos, label="3B")
        result = customers_services.move_in_to_unit(dana, unit["id"], _payload(co_owners=[RIYA]))
        row = co_owner_models.AccountCoOwner.objects.get(account_id=result["id"])
        account = customers_models.Account.objects.get(pk=result["id"])
        served = move_record_reads._co_owners(account)
        assert served[0]["id"] == str(row.pk) and served[0]["photo_id"] is False
    upload = SimpleUploadedFile("riya-id.jpg", b"\xff\xd8\xff" + b"J" * 900, content_type="image/jpeg")
    response = _view(
        marcus, brazos, "post", f"/api/x/accounts/{result['id']}/co-owners/{row.pk}/photo-id",
        api.co_owner_photo_id, {"file": upload}, account_id=str(result["id"]), co_owner_id=str(row.pk),
    )
    assert response.status_code == 201, response.data
    with tenant_ctx(brazos):
        assert move_record_reads._co_owners(account)[0]["photo_id"] is True


def test_another_utility_cannot_file_a_photo_id_on_this_utilitys_co_owner(
    brazos, lonestar, dana, docs_dir
):
    """HR-1 / BR-TEN-003: Lone Star Ridge naming Brazos Bend's account and
    co-owner gets the 404 a missing one gets, nothing is filed, and the row
    still reads *No ID* at home.

    ⚠ **THREE LAYERS, MEASURED (law 7).** Removing `attach_photo_id`'s own
    tenant lookup alone stays GREEN on both databases, because
    `account_documents.file_document` re-resolves the account under the tenant
    and refuses; on PostgreSQL the forced RLS policy refuses as well. With BOTH
    code lookups removed, SQLite (no RLS) goes red — *"DID NOT RAISE
    NotFoundError"* — so this run on any database is the one that proves the
    code's scoping, and the PostgreSQL run proves the policy behind it."""
    from apps.customers import co_owner_models, move_in_people as people

    with tenant_ctx(brazos):
        _premises, unit = _served_unit(dana, brazos, label="3B")
        result = customers_services.move_in_to_unit(dana, unit["id"], _payload(co_owners=[RIYA]))
        row = co_owner_models.AccountCoOwner.objects.get(account_id=result["id"])
    with tenant_ctx(lonestar):
        with pytest.raises(errors.NotFoundError):
            people.attach_photo_id(
                dana, result["id"], row.pk, {"name": "x.jpg"},
                _Upload(b"\xff\xd8\xff" + b"J" * 900, name="x.jpg", content_type="image/jpeg"),
            )
    with tenant_ctx(brazos):
        row.refresh_from_db()
        assert row.photo_id_document_id is None
        assert AccountDocument.objects.filter(account_id=result["id"]).count() == 0
