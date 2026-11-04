"""`CR-171-BRC10` P1.10 · P1.11 (writes) · P1.26 — what a move-in writes besides the account.

THE WORKED CASES (images 38, 40, 39; CR-171 §9.1 for the columns):

  * **Nilesh G** moves in as a PERSON with co-owner **Riya G** — *Spouse*,
    SSN 210-80-9662, *Also responsible for the bills* (image 38). The account
    gets one `account_co_owners` row, kind `co_owner`, the SSN encrypted with
    its blind index, and the audit row carries **9662** and never the SSN.
  * **Kestrel Holdings LLC** moves in as a COMPANY, trading as *Kestrel
    Bakery*, an LLC registered in Iowa, contact **Nilesh G, Owner, by email**,
    bills to the contact person, PO **PO-7781**, and one officer **Arun Mehta**
    — *Managing member*, **50%**, signs (image 40). The share is stored as
    `50.000000` (hard rule 2).
  * The move's REQUEST holds a deed uploaded as a real file, a lease whose
    reference is not a stored file, and nothing else. After Complete the
    account files the deed **by reference** — the same stored document, no new
    one — in its KYC folder, and skips the lease (P1.26, BR-CUS-073/080).

Refusals are named and write nothing: an officer's share on a person's
co-owner, company facts on a person, bills to a contact person with no
contact, a choice the list does not offer, a share of 120%.

PROVED RED FIRST (law 7): with `move_in_people` present but `services._move_in`
not yet calling it, every write case failed on its first read-back (quoted in
CR-171 §9.IDN-2) and every refusal case on `DID NOT RAISE`.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from apps.customers import co_owner_models, move_in_people
from apps.customers import models as customers_models
from apps.customers import service_request_documents as doc_files
from apps.customers import service_request_service as sr
from apps.customers import services as customers_services
from apps.customers.account_document_models import AccountDocument
from core import errors
from tests import identity_fixtures
from tests.isolation_helpers import (  # noqa: F401 — fixtures used by name
    assert_rls_scoped,
    requires_postgres,
    rls,
    rls_probe_role,
)
from tests.test_br_cus_1077_move_in_job import _move_in_request, _served_unit
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import brazos, dana, lonestar, tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db

PERSON = "Nilesh G"
COMPANY = "Kestrel Holdings LLC"
RIYA_SSN = "210-80-9662"
PDF = b"%PDF-1.7\n1 0 obj\n<< /Title (Deed, 8 Quarry Lane) >>\n" + b"D" * 2000 + b"\n%%EOF"


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


def _person_payload(**extra):
    body = {
        "account_type": "residential",
        "opened_at": "2026-10-01",
        "contact": {"full_name": PERSON, "email": "nilesh@example.test"},
        "customer": identity_fixtures.customer_block(PERSON, kind="person"),
    }
    body.update(extra)
    return body


def _company_payload(**extra):
    body = {
        "account_type": "commercial",
        "opened_at": "2026-10-01",
        "contact": {
            "full_name": PERSON,
            "job_title": "Owner",
            "email": "nilesh@example.test",
            "phone": "(732) 630-0285",
            "contact_by": "email",
        },
        "customer": identity_fixtures.customer_block(COMPANY, kind="company"),
    }
    body.update(extra)
    return body


RIYA = {
    "full_name": "Riya G",
    "relationship": "Spouse",
    "phone": "(732) 555-0144",
    "ssn": RIYA_SSN,
    "contact_by": "text",
    "responsible_for_bills": True,
}
ARUN = {
    "full_name": "Arun Mehta",
    "title": "Managing member",
    "ownership_pct": "50",
    "signs_for_company": True,
}


def _move_in(tenant, actor, payload, *, label="Unit 1", address="8 Quarry Lane"):
    with tenant_ctx(tenant):
        _premises, unit = _served_unit(actor, tenant, label=label, address=address)
        return customers_services.move_in_to_unit(actor, unit["id"], payload), unit


def _accounts_on(unit):
    return customers_models.Account.objects.filter(unit_id=unit["id"]).count()


# ═══════════════════════════════════════════════════════════════════════════
# P1.10 — co-owners and officers
# ═══════════════════════════════════════════════════════════════════════════
def test_a_persons_co_owner_is_written_encrypted_and_audited_last_four(brazos, dana, audit_rows):
    result, _unit = _move_in(brazos, dana, _person_payload(co_owners=[RIYA]))
    assert result["people"]["co_owners"] == 1
    with tenant_ctx(brazos):
        row = co_owner_models.AccountCoOwner.objects.get(account_id=result["id"])
        assert row.kind == co_owner_models.KIND_CO_OWNER
        assert row.full_name == "Riya G"
        assert row.relationship == "Spouse"
        assert row.title is None and row.ownership_pct is None
        assert row.responsible_for_bills is True
        assert row.contact_by == "text"
        assert row.ssn == RIYA_SSN and row.ssn_bidx
        # `audit_rows` is the shared capture sink (test_us_met_helpers).
        added = [r for r in audit_rows if r.get("action") == "customers.account.co_owner_added"]
        assert len(added) == 1, sorted({r.get("action") for r in audit_rows})
        text = str(added[0])
        assert "9662" in text
        assert RIYA_SSN not in text and "210809662" not in text


def test_a_companys_officer_and_its_own_facts_are_written(brazos, dana):
    result, _unit = _move_in(
        brazos,
        dana,
        _company_payload(
            co_owners=[ARUN],
            company={"trading_as": "Kestrel Bakery", "business_type": "LLC", "registered_in": "IA"},
            po_number="PO-7781",
            bills_go_to="contact_person",
        ),
    )
    assert result["people"]["co_owners"] == 1
    assert result["people"]["company_updated"] == ["business_type", "registered_in", "trading_as"]
    with tenant_ctx(brazos):
        officer = co_owner_models.AccountCoOwner.objects.get(account_id=result["id"])
        assert officer.kind == co_owner_models.KIND_OFFICER
        assert officer.title == "Managing member"
        assert officer.ownership_pct == Decimal("50.000000")
        assert officer.signs_for_company is True
        assert officer.relationship is None
        account = customers_models.Account.objects.get(pk=result["id"])
        assert account.po_number == "PO-7781"
        assert account.bills_go_to == "contact_person"
        holder = customers_models.CustomerAccount.objects.get(account_id=account.pk).customer
        assert holder.kind == "company"
        assert (holder.trading_as, holder.business_type, holder.registered_in) == (
            "Kestrel Bakery",
            "LLC",
            "IA",
        )
        contact = customers_models.Contact.objects.get(account_id=account.pk)
        assert (contact.job_title, contact.contact_by) == ("Owner", "email")


# ═══════════════════════════════════════════════════════════════════════════
# Refusals — named, and nothing written
# ═══════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize(
    "payload, key, field",
    [
        (
            _person_payload(co_owners=[{**RIYA, "ownership_pct": "50"}]),
            "customers.moveIn.people.officerOnly",
            "co_owners[0].ownership_pct",
        ),
        (
            _company_payload(co_owners=[{**ARUN, "relationship": "Spouse"}]),
            "customers.moveIn.people.coOwnerOnly",
            "co_owners[0].relationship",
        ),
        (
            _person_payload(company={"trading_as": "Nilesh Lawn Care"}),
            "customers.moveIn.people.companyOnly",
            "company",
        ),
        (
            _company_payload(contact=None, bills_go_to="contact_person"),
            "customers.moveIn.people.contactNeeded",
            "bills_go_to",
        ),
        (
            _company_payload(bills_go_to="the landlord"),
            "customers.moveIn.people.choiceUnknown",
            "bills_go_to",
        ),
        (
            _company_payload(co_owners=[{**ARUN, "ownership_pct": "120"}]),
            "customers.moveIn.people.shareRange",
            "co_owners[0].ownership_pct",
        ),
        (
            _company_payload(contact={"full_name": PERSON, "contact_by": "pigeon"}),
            "customers.moveIn.people.choiceUnknown",
            "contact.contact_by",
        ),
        (
            _person_payload(co_owners=[{"relationship": "Spouse"}]),
            "customers.contact.name_required",
            "co_owners[0].full_name",
        ),
    ],
)
def test_a_refused_value_writes_nothing_and_names_itself(brazos, dana, payload, key, field):
    with tenant_ctx(brazos):
        _premises, unit = _served_unit(dana, brazos)
        # A typed value is a ValidationError (400); a fact about the account
        # being opened — no contact, a person holder — is a BizError (409).
        with pytest.raises((errors.ValidationError, errors.BizError)) as caught:
            customers_services.move_in_to_unit(dana, unit["id"], payload)
        assert caught.value.message_key == key
        assert field in [fe["field"] for fe in caught.value.field_errors]
        assert _accounts_on(unit) == 0
        assert co_owner_models.AccountCoOwner.objects.count() == 0


def test_the_payload_keys_are_admitted_by_the_move_in_door():
    assert set(move_in_people.PAYLOAD_KEYS) <= customers_services.MOVE_IN_FIELDS
    assert {"job_title", "contact_by"} <= customers_services.CONTACT_FIELDS


# ═══════════════════════════════════════════════════════════════════════════
# P1.26 — the request's documents reach the account, by reference
# ═══════════════════════════════════════════════════════════════════════════
def test_the_requests_documents_are_filed_on_the_account_by_reference(brazos, dana, docs_dir):
    from apps.tenancy.document_models import StoredDocument

    with tenant_ctx(brazos):
        _premises, unit = _served_unit(dana, brazos, label="3B", address="8 Quarry Lane")
        request = _move_in_request(dana, address=str(unit["unit_no"]))
        deed = doc_files.attach_file(
            dana,
            request.id,
            {
                "doc_type": customers_models.ServiceRequestDocument.DOC_TENANCY_OR_DEED,
                "name": "deed.pdf",
            },
            _Upload(PDF, name="deed.pdf", content_type="application/pdf"),
        )
        sr.approve_and_raise(dana, request.id)
        stored_before = StoredDocument.objects.count()
        result = customers_services.move_in_to_unit(
            dana, unit["id"], _person_payload(service_request_id=str(request.id))
        )
        # The deed carried; the fixture's `s3://lease` reference did not.
        assert result["people"]["documents_carried"] == 1
        card = customers_models.ServiceRequestDocument.objects.get(pk=deed["id"])
        filing = AccountDocument.objects.get(account_id=result["id"])
        # BY REFERENCE: the same stored document, and no new stored object.
        assert str(filing.document_id) == card.storage_ref
        assert StoredDocument.objects.count() == stored_before
        assert filing.doc_type == "kyc"
        assert filing.uploaded_by_id == card.uploaded_by_id
        # The request keeps its own card (BR-CUS-080: one file, two cards).
        assert customers_models.ServiceRequestDocument.objects.filter(pk=card.pk).exists()


def test_no_request_carries_nothing(brazos, dana):
    result, _unit = _move_in(brazos, dana, _person_payload())
    assert result["people"] == {"co_owners": 0, "company_updated": [], "documents_carried": 0}


# ═══════════════════════════════════════════════════════════════════════════
# PostgreSQL — law 14 and RLS
# ═══════════════════════════════════════════════════════════════════════════
@requires_postgres
@pytest.mark.isolation
def test_pg_a_refusal_inside_the_commit_rolls_back_and_the_rows_are_tenant_scoped(
    brazos, lonestar, dana, rls
):
    """(1) Law 14: `contactNeeded` is raised INSIDE `_move_in`'s transaction,
    after the account row was written. On PostgreSQL the account must be gone
    and the connection still usable — the next query answers.
    (2) RLS: the co-owner row written for Brazos Bend is invisible to Lone Star
    Ridge under the non-superuser probe role."""
    with tenant_ctx(brazos):
        _premises, unit = _served_unit(dana, brazos)
        with pytest.raises(errors.BizError) as caught:
            customers_services.move_in_to_unit(
                dana, unit["id"], _person_payload(contact=None, bills_go_to="contact_person")
            )
        assert caught.value.message_key == "customers.moveIn.people.contactNeeded"
        assert _accounts_on(unit) == 0  # the connection still answers
    result, _unit = _move_in(brazos, dana, _person_payload(co_owners=[RIYA]), label="Unit 2")
    with tenant_ctx(brazos):
        row_id = co_owner_models.AccountCoOwner.objects.get(account_id=result["id"]).pk
    assert_rls_scoped(rls, "account_co_owners", owner=brazos, intruder=lonestar, owner_ids={row_id})
