"""`DEF-CUS-9828` (N2, PO 2026-10-06) — after Approve and raise the build, New
Connect receives EVERY answer the request holds, and the request's documents
reach the owner's account at Create, LINKED and not copied.

THE WORKED CASE (the PO's own walk): Kyle Mark applies online for Haustin
Towers 2, Apt-12, with a photo ID. The clerk approves it into a new
connection. The build's `prefill` must carry the town, state and ZIP he gave,
Apt-12, the sub-type, where the bill goes, the utility's own answers, his
language, his co-applicant, his SSN and licence as LAST FOUR only, and the
photo ID — and the master account opened at Create must hold that same stored
photo ID (one stored file, two filing cards).

Through the clerk's own doors: the portal's Start service, `approve_and_raise`,
`connection_detail` (what `GET /connections/{id}` serves) and
`commit_new_connect`.
"""

from __future__ import annotations

import pytest

from apps.customers import models as customers_models
from apps.customers import service_request_documents as doc_files
from apps.customers.account_document_models import AccountDocument
from apps.metering import connection_reads
from apps.work import connection_models as work_tables
from tests.test_portal_request_to_active import (  # noqa: F401 — fixtures used by name
    _apply,
    _approve,
    _build,
    _ctx,
    cedar,
    clerk,
)
from tests.test_us_cwp_helpers import *  # noqa: F401,F403 — growth_plan · identity_seam · throttle
from tests.test_us_met_helpers import *  # noqa: F401,F403

pytestmark = pytest.mark.django_db

PDF = b"%PDF-1.7\n1 0 obj\n<< /Title (Photo ID) >>\n" + b"P" * 1500 + b"\n%%EOF"
SSN = "123-45-6789"
LICENCE = "D1234-5678-4321"


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


def _kyle(cedar, clerk):
    """Kyle Mark's request, approved into a draft build, with every answer set."""
    request_id, _ = _apply(
        cedar,
        token="a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b9828",
        services=["water"],
        first="Kyle",
        last="Mark",
        email="kyle.mark@example.test",
        phone="(512) 555-0128",
        address="Haustin Towers 2",
        unit="Apt-12",
    )
    with _ctx(cedar):
        residential = customers_models.AccountType.objects.get(tenant=cedar, code="residential")
        subtype = customers_models.AccountSubtype.objects.create(
            tenant=cedar, account_type=residential, code="nct01_tower", name="High-rise"
        )
        row = customers_models.ServiceRequest.objects.get(pk=request_id)
        row.address_city_as_given = "Austin"
        row.address_state_as_given = "TX"
        row.address_postal_code_as_given = "78701"
        row.billing_address_same = False
        row.billing_line1_as_given = "PO Box 4471"
        row.billing_city_as_given = "Austin"
        row.billing_state_as_given = "TX"
        row.billing_postal_code_as_given = "78767"
        row.custom_data = {"accounts": {"name_on_dte_bill": "K. Mark", "dte_account_number": "DTE-0091"}}
        row.preferred_language = "es-MX"
        row.co_applicant_name = "Maya Mark"
        row.co_applicant_email = "maya@example.test"
        row.co_applicant_phone = "(512) 555-0129"
        row.ssn = SSN
        row.drivers_licence = LICENCE
        row.save()
        doc_files.attach_file(
            clerk,
            request_id,
            {
                "doc_type": customers_models.ServiceRequestDocument.DOC_PROOF_OF_IDENTITY,
                "name": "kyle-photo-id.pdf",
            },
            _Upload(PDF, name="kyle-photo-id.pdf", content_type="application/pdf"),
        )
    _approve(clerk, cedar, request_id, outcome="new_connection", category="residential")
    with _ctx(cedar):
        customers_models.ServiceRequest.objects.filter(pk=request_id).update(
            account_subtype=subtype
        )
    return request_id


def test_the_build_prefill_carries_every_answer_the_request_holds(cedar, clerk, docs_dir):
    request_id = _kyle(cedar, clerk)
    with _ctx(cedar):
        prefill = connection_reads.connection_detail(
            work_tables.Connection.objects.get(service_request_id=request_id).id
        )["prefill"]
    assert prefill["address_as_given"] == "Haustin Towers 2"
    assert prefill["address_unit_as_given"] == "Apt-12"
    assert (
        prefill["address_city_as_given"],
        prefill["address_state_as_given"],
        prefill["address_postal_code_as_given"],
    ) == ("Austin", "TX", "78701")
    assert prefill["account_subtype_code"] == "nct01_tower"
    assert prefill["mailing_address"]["line1"] == "PO Box 4471"
    assert prefill["mailing_address"]["postal_code"] == "78767"
    assert prefill["account_custom_data"] == {
        "name_on_dte_bill": "K. Mark",
        "dte_account_number": "DTE-0091",
    }
    assert prefill["preferred_language"] == "es-MX"
    assert prefill["co_applicant"] == {
        "name": "Maya Mark",
        "email": "maya@example.test",
        "phone": "(512) 555-0129",
    }
    assert (prefill["ssn_last4"], prefill["driving_licence_last4"]) == ("6789", "4321")
    assert SSN not in str(prefill) and LICENCE not in str(prefill), "last four only, never the number"
    [doc] = prefill["documents"]
    assert doc["name"] == "kyle-photo-id.pdf"
    assert doc["file_present"] is True
    assert "uploaded_by" not in doc, "no database id is served (B14 rule 31)"


def test_create_files_the_requests_documents_on_the_owner_account_by_reference(
    cedar, clerk, docs_dir
):
    request_id = _kyle(cedar, clerk)
    built, draft, premises, units = _build(
        clerk,
        cedar,
        request_id,
        address="Haustin Towers 2",
        postal_code="78701",
        services=["water"],
        labels=("Apt-12", "Apt-14"),
        owner={
            "name": "Kyle Mark",
            "email": "kyle.mark@example.test",
            "phone": "(512) 555-0128",
            "party_kind": "person",
            "identity": {"phone": "(512) 555-0128"},
            "account_type": "residential",
        },
    )
    with _ctx(cedar):
        card = customers_models.ServiceRequestDocument.objects.get(request_id=request_id)
        filings = list(AccountDocument.objects.filter(account_id=draft.owner_account_id))
        assert len(filings) == 1, "the request's photo ID did not reach the owner's account"
        assert str(filings[0].document_id) == str(card.storage_ref), "linked, not copied"
        assert filings[0].uploaded_by_id == card.uploaded_by_id
