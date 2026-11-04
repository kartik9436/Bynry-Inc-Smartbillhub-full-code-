"""Lane CF-1 (2026-10-18) — ONE customer form across the create screens.

THE RULING (decision log *"2026-10-18 — CUSTOMER DATA AND UI CONSISTENT ACROSS
THE CREATE SCREENS, MOVE-IN AS THE REFERENCE"* and its *Same day* paragraphs),
PO verbatim: *"Move in UI is latest and correct"*, *"ALSO DATA COLECTED IS NOT
LOST"*. Built from the drawing set
`04-docs/05-modules/03-customers/wireframes/customer-forms-2026-10-18/`.

THE SEARCH RESULTS TABLE (images 01, 10): each row carries the customer's date
of birth, the LAST FOUR of their phone, and how many of ALL their accounts are
open — counted before the rows are cut at the server's bound.

    **Maria Lopez**, born **1988-04-12**, phone **(734) 555-0182**, SSN
    **123-45-4471**, holds three accounts: two closed, one open.
      → row: `date_of_birth` 1988-04-12 · `phone_last4` 0182 ·
        `accounts.count` 3 · `accounts.open_count` 1

Run on PostgreSQL:

    CELERY_BROKER_URL=memory:// JOBS_EAGER=false python -m pytest -q \\
      --ds=config.settings.pgtest --create-db tests/test_cf1_customer_forms_2026_10_18.py
"""

from __future__ import annotations

import pytest
from django.utils import timezone

from apps.audit import models as audit_models
from apps.customers import api as customers_api
from apps.customers import identity_match
from apps.customers import models as customers_models
from apps.customers import service_request_reads as reads
from apps.customers import service_request_service as sr
from apps.customers import services as customers_services
from core import errors
from tests.ledger_le_fixtures import make_accounts
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import brazos, dana, tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db

PURPOSE = {"purpose": "search_customer_id"}


def _post(actor, tenant, body):
    from rest_framework.test import APIRequestFactory, force_authenticate

    request = APIRequestFactory().post("/api/x/customers/match", body, format="json")
    force_authenticate(request, user=actor.user)
    request.tenant_role = actor.role
    request.tenant_id = tenant.id
    with tenant_ctx(tenant):
        return customers_api.customers_match(request)


def _maria(tenant, actor):
    with tenant_ctx(tenant):
        accounts = make_accounts(actor, tenant, {}, service="electric")
        maria = customers_models.Customer.objects.create(
            tenant=tenant, kind="person", display_name="Maria Lopez", customer_no="C-00412"
        )
        maria.date_of_birth = "1988-04-12"
        maria.phone = "(734) 555-0182"
        identity_match.set_identifier(maria, "ssn", "123-45-4471")
        maria.save()
        rows = list(accounts.values())
        for account in rows:
            customers_models.CustomerAccount.objects.create(
                tenant_id=tenant.id, customer=maria, account=account, match_tier="strong"
            )
        # Two closed, the rest open — the open count is the server's to count.
        closed = rows[:2]
        for account in closed:
            customers_models.Account.objects.filter(pk=account.pk).update(closed_at=timezone.now())
    return maria, rows


def test_cf1_search_row_carries_date_of_birth_phone_last_four_and_open_count(brazos, dana):
    maria, rows = _maria(brazos, dana)
    response = _post(dana, brazos, {"kind": "person", "name": "Maria Lopez", "ssn": "123-45-4471", **PURPOSE})
    assert response.status_code == 200, response.data
    found = response.data["search"]["customers"]
    assert [row["customer_no"] for row in found] == ["C-00412"]
    row = found[0]
    assert row["verdict"] == "found"
    assert row["date_of_birth"] == "1988-04-12"
    assert row["phone_last4"] == "0182"
    # The search's rows carry the phone as its LAST FOUR only. (New
    # Connection's Q5 `candidates`, served beside it on the same door, is not
    # this table's and is unchanged.)
    assert "555-0182" not in str(response.data["search"])
    assert row["accounts"]["count"] == len(rows)
    assert row["accounts"]["open_count"] == len(rows) - 2


# ═══════════════════════════════════════════════════════════════════════════
# THE STAFF SERVICE REQUEST — every value the shared form asks is SAVED
# ═══════════════════════════════════════════════════════════════════════════
#
#   **Maria Lopez** applies at the counter: born 1988-04-12, SSN 123-45-4471,
#   licence MI-L-552-118-903, government ID ending 9001, contact by text, a
#   co-applicant **Daniel Lopez** (spouse, responsible for bills, born
#   1986-09-30, SSN 987-65-2208, licence MI-D-111), mail to **PO Box 2210,
#   Ypsilanti, MI 48197**, paperless ON, text reminders ON, language es.
#   → the request reads every one of those back (identifiers as last four).


MARIA_REQUEST = {
    "channel": "walk_in",
    "applicant_kind": "person",
    "applicant_name": "Maria Lopez",
    "applicant_email": "maria.lopez@example.com",
    "applicant_phone": "(734) 555-0182",
    "address_as_given": "143 Willow Bend Dr",
    "date_of_birth": "1988-04-12",
    "ssn": "123-45-4471",
    "drivers_licence": "MI-L-552-118-903",
    "gov_id_last4": "TX-77-9001",
    "contact_by": "text",
    "preferred_language": "es",
    "co_applicants": [
        {
            "full_name": "Daniel Lopez",
            "relationship": "spouse",
            "responsible_for_bills": True,
            "phone": "(734) 555-0144",
            "email": "dan.lopez@example.com",
            "date_of_birth": "1986-09-30",
            "ssn": "987-65-2208",
            "driving_licence": "MI-D-111",
            "contact_by": "email",
        }
    ],
    "mailing_same": False,
    "mailing_line1": "PO Box 2210",
    "mailing_line2": "",
    "mailing_city": "Ypsilanti",
    "mailing_state": "MI",
    "mailing_postal_code": "48197",
    "paperless": True,
    "sms_reminders": True,
}


def _seed_series(tenant):
    from apps.tenancy import models as tenancy_models

    tenancy_models.NumberSeries.objects.update_or_create(
        tenant=tenant,
        series="service_request",
        defaults={"format": "SR-{YY}-{0000}", "next_number": 1},
    )


def test_cf1_request_saves_every_field_of_the_shared_form_and_reads_it_back(brazos, dana):
    with tenant_ctx(brazos):
        _seed_series(brazos)
        request = sr.create_request(dana, dict(MARIA_REQUEST))
        detail = reads.detail(request.id)
    applicant = detail["applicant"]
    assert applicant["name"] == "Maria Lopez"
    assert applicant["email"] == "maria.lopez@example.com"
    assert applicant["phone"] == "(734) 555-0182"
    assert applicant["language"] == "es"
    assert applicant["date_of_birth"] == "1988-04-12"
    assert applicant["identifier"]["ssn_last4"] == "4471"
    assert applicant["identifier"]["drivers_licence_last4"] == "8903"
    # Move-in's Government ID — the LAST FOUR is all that is ever kept.
    assert applicant["gov_id_last4"] == "9001"
    assert applicant["contact_by"] == "text"
    assert applicant["preferences"] == {"paperless": True, "sms_reminders": True}
    assert applicant["mailing_address"] == {
        "same": False,
        "line1": "PO Box 2210",
        "line2": None,
        "city": "Ypsilanti",
        "state": "MI",
        "postal_code": "48197",
    }
    [card] = applicant["co_applicants"]
    assert card == {
        "full_name": "Daniel Lopez",
        "relationship": "spouse",
        "phone": "(734) 555-0144",
        "email": "dan.lopez@example.com",
        "contact_by": "email",
        "date_of_birth": "1986-09-30",
        "responsible_for_bills": True,
        "ssn_last4": "2208",
        "driving_licence_last4": "D111",
    }
    # The three old columns are mirrored from the first card.
    assert applicant["co_applicant"]["name"] == "Daniel Lopez"
    # The older billing columns carry the same answer (every reader agrees).
    place = detail["location_and_services"]
    assert place["billing_address_same"] is False
    assert place["billing_line1_as_given"] == "PO Box 2210"
    # BR-CUS-092(c) — no full identifier anywhere on the read, or in the audit.
    blob = str(detail)
    for secret in ("123-45-4471", "987-65-2208", "MI-L-552-118-903", "MI-D-111", "TX-77-9001"):
        assert secret not in blob
    with tenant_ctx(brazos):
        audits = str(list(audit_models.AuditLog.objects.filter(entity_id=str(request.id)).values()))
    for secret in ("123-45-4471", "987-65-2208", "MI-D-111"):
        assert secret not in audits
    # The co-applicant's identifiers are CIPHERTEXT in the row, never clear.
    with tenant_ctx(brazos):
        raw = customers_models.ServiceRequest.objects.values_list("co_applicants", flat=True).get(
            pk=request.id
        )
    assert "987-65-2208" not in str(raw)


def test_cf1_def_cus_10223_a_business_tax_id_is_saved_encrypted_and_refused_on_a_person(brazos, dana):
    from django.db import connection

    with tenant_ctx(brazos):
        _seed_series(brazos)
        request = sr.create_request(
            dana,
            {
                "channel": "walk_in",
                "applicant_kind": "business",
                "applicant_name": "Kestrel Bakery LLC",
                "address_as_given": "9 Mill St",
                "tax_id": "47-1234567",
            },
        )
        detail = reads.detail(request.id)
        with connection.cursor() as cursor:
            cursor.execute("SELECT tax_id FROM service_requests WHERE id = %s", [str(request.id)])
            stored = cursor.fetchone()[0]
        with pytest.raises(errors.BizError) as refused:
            sr.create_request(dana, {**MARIA_REQUEST, "tax_id": "47-1234567"})
    assert detail["applicant"]["identifier"]["tax_id_last4"] == "4567"
    assert detail["applicant"]["identifier"]["tax_id_present"] is True
    assert stored and "1234567" not in stored  # ciphertext, never the number
    assert refused.value.message_key == "customers.serviceRequest.notAskedOfThisApplicant"


def test_cf1_a_card_re_sent_without_its_ssn_keeps_the_stored_one(brazos, dana):
    """The capture screen is only ever shown a card's last four, so a PATCH
    that re-sends the card blank must not wipe the stored number."""
    with tenant_ctx(brazos):
        _seed_series(brazos)
        request = sr.create_request(dana, dict(MARIA_REQUEST))
        card = {key: value for key, value in MARIA_REQUEST["co_applicants"][0].items()}
        card.pop("ssn")
        card.pop("driving_licence")
        card["phone"] = "(734) 555-0199"
        sr.update_request(dana, request.id, {"co_applicants": [card]})
        rows = sr.co_applicant_rows(customers_models.ServiceRequest.objects.get(pk=request.id), decrypt=True)
    assert rows[0]["phone"] == "(734) 555-0199"
    assert rows[0]["ssn"] == "987-65-2208"
    assert rows[0]["driving_licence"] == "MI-D-111"


def test_cf1_migration_0087_copies_billing_to_mailing_and_deletes_nothing(brazos, dana):
    """Data step of `customers/0087`, run against rows written the OLD way."""
    import importlib

    from django.apps import apps as django_apps
    from django.db import connection

    migration = importlib.import_module("apps.customers.migrations.0087_cf1_request_customer_form")
    with tenant_ctx(brazos):
        _seed_series(brazos)
        parts = sr.create_request(dana, {**MARIA_REQUEST, "co_applicants": []})
        one_box = sr.create_request(dana, {**MARIA_REQUEST, "co_applicants": []})
        # Rewind both rows to the shape a pre-0087 request has.
        customers_models.ServiceRequest.objects.filter(pk=parts.pk).update(
            mailing_same=True,
            mailing_line1=None,
            mailing_city=None,
            mailing_state=None,
            mailing_postal_code=None,
            billing_address_same=False,
            billing_line1_as_given="PO Box 4471",
            billing_city_as_given="Round Rock",
            billing_state_as_given="TX",
            billing_postal_code_as_given="78664",
        )
        customers_models.ServiceRequest.objects.filter(pk=one_box.pk).update(
            mailing_same=True,
            mailing_line1=None,
            mailing_city=None,
            mailing_state=None,
            mailing_postal_code=None,
            billing_address_same=False,
            billing_line1_as_given=None,
            billing_city_as_given=None,
            billing_state_as_given=None,
            billing_postal_code_as_given=None,
            billing_address_as_given="c/o Rivera, 18 Oak Lane, Austin TX",
        )

        class _Editor:
            pass

        editor = _Editor()
        editor.connection = connection
        migration.copy_billing_to_mailing(django_apps, editor)
        migration.copy_billing_to_mailing(django_apps, editor)  # idempotent
        got = {
            row["id"]: row
            for row in customers_models.ServiceRequest.objects.filter(pk__in=[parts.pk, one_box.pk]).values()
        }
    a, b = got[parts.pk], got[one_box.pk]
    assert (a["mailing_same"], a["mailing_line1"], a["mailing_city"], a["mailing_state"], a["mailing_postal_code"]) == (
        False,
        "PO Box 4471",
        "Round Rock",
        "TX",
        "78664",
    )
    assert a["billing_line1_as_given"] == "PO Box 4471"  # nothing deleted
    assert (b["mailing_same"], b["mailing_line1"]) == (False, "c/o Rivera, 18 Oak Lane, Austin TX")
    assert b["billing_address_as_given"] == "c/o Rivera, 18 Oak Lane, Austin TX"


def test_cf1_the_request_carries_its_identifiers_people_and_contact_facts_into_the_move_in(brazos, dana):
    """`_carry_request_decisions(..., carry_people=True)` — the move-in door's
    own carry: only where the payload is silent, and nothing the clerk removed
    is added back."""
    with tenant_ctx(brazos):
        _seed_series(brazos)
        request = sr.create_request(dana, dict(MARIA_REQUEST))
        carried = customers_services._carry_request_decisions(
            {
                "customer": {"display_name": "Maria Lopez", "kind": "person", "identity": {"phone": "(734) 555-0182"}},
                "contact": {"full_name": "Maria Lopez"},
                # The screen kept Daniel's card and could not send his SSN.
                "co_owners": [{"full_name": "Daniel Lopez", "relationship": "spouse"}],
            },
            request.id,
            carry_people=True,
        )
        nothing_kept = customers_services._carry_request_decisions(
            {"customer": {"display_name": "Maria Lopez", "kind": "person"}}, request.id, carry_people=True
        )
    identity = carried["customer"]["identity"]
    assert identity["ssn"] == "123-45-4471"
    assert identity["driving_licence"] == "MI-L-552-118-903"
    assert identity["date_of_birth"] == "1988-04-12"
    assert identity["phone"] == "(734) 555-0182"
    assert carried["contact"]["gov_id_last4"] == "9001"
    assert carried["contact"]["contact_by"] == "text"
    assert carried["co_owners"] == [
        {
            "full_name": "Daniel Lopez",
            "relationship": "spouse",
            "ssn": "987-65-2208",
            "driving_licence": "MI-D-111",
        }
    ]
    # The clerk unticked co-owners: nothing is added back.
    assert "co_owners" not in nothing_kept


# ═══════════════════════════════════════════════════════════════════════════
# Task 13 — New Connection's owner step: the shared form's answers reach the
# owner's account. Worked case: Kyle Mark's request (the fixture of
# `test_def_cus_9828_build_prefill_everything`); the clerk types a mailing
# address of PO Box 2210, Ypsilanti MI 48197, Contact by *text*, government ID
# 9001, and keeps the request's co-applicant Maya Mark — whose SSN the screen
# was only ever shown as its last four.
# ═══════════════════════════════════════════════════════════════════════════
from tests.test_def_cus_9828_build_prefill_everything import _kyle, docs_dir  # noqa: E402,F401
from tests.test_portal_request_to_active import _build, _ctx, cedar, clerk  # noqa: E402,F401
from tests.test_us_cwp_helpers import *  # noqa: E402,F401,F403 — growth_plan · identity_seam · throttle

MAYA_SSN = "321-54-9876"


def _kyle_owner(**extra):
    owner = {
        "name": "Kyle Mark",
        "email": "kyle.mark@example.test",
        "phone": "(512) 555-0128",
        "party_kind": "person",
        "identity": {"phone": "(512) 555-0128"},
        "account_type": "residential",
    }
    owner.update(extra)
    return owner


def _kyle_build(cedar, clerk, request_id, owner):
    _build(
        clerk,
        cedar,
        request_id,
        address="Haustin Towers 2",
        postal_code="78701",
        services=["water"],
        labels=("Apt-12", "Apt-14"),
        owner=owner,
    )


def test_cf1_def_cus_10222_new_connect_owner_mailing_and_contact_reach_the_account(cedar, clerk, docs_dir):
    from apps.work import connection_models as work_tables

    request_id = _kyle(cedar, clerk)
    _kyle_build(
        cedar,
        clerk,
        request_id,
        _kyle_owner(
            addresses=[
                {"kind": "mailing", "line1": "PO Box 2210", "city": "Ypsilanti", "state": "MI", "postal_code": "48197"}
            ],
            contact_by="text",
            gov_id_last4="9001",
        ),
    )
    with _ctx(cedar):
        draft = work_tables.Connection.objects.get(service_request_id=request_id)
        mailing = list(
            customers_models.Address.objects.filter(account_id=draft.owner_account_id, kind="mailing").values_list(
                "line1", "city", "state", "postal_code"
            )
        )
        contact = customers_models.Contact.objects.filter(account_id=draft.owner_account_id, is_primary=True).first()
    assert mailing == [("PO Box 2210", "Ypsilanti", "MI", "48197")], (
        "DEF-CUS-10222 — the mailing address typed on New Connect never reached the account"
    )
    assert contact is not None
    assert (contact.contact_by, contact.gov_id_last4) == ("text", "9001")


def test_cf1_new_connect_carries_the_request_co_applicants_numbers_by_name(cedar, clerk, docs_dir):
    from apps.customers import co_owner_models
    from apps.work import connection_models as work_tables

    request_id = _kyle(cedar, clerk)
    with _ctx(cedar):
        customers_models.ServiceRequest.objects.filter(pk=request_id).update(
            co_applicants=[
                identity_match.seal_co_applicant(
                    {"full_name": "Maya Mark", "relationship": "family", "ssn": MAYA_SSN, "driving_licence": None}
                )
            ]
        )
    _kyle_build(
        cedar, clerk, request_id, _kyle_owner(co_owners=[{"full_name": "Maya Mark", "relationship": "family"}])
    )
    with _ctx(cedar):
        draft = work_tables.Connection.objects.get(service_request_id=request_id)
        [maya] = co_owner_models.AccountCoOwner.objects.filter(account_id=draft.owner_account_id)
    assert maya.full_name == "Maya Mark"
    assert maya.ssn == MAYA_SSN, "the request's stored SSN was not carried onto the card the clerk kept"


def test_cf1_def_cus_10233_new_connect_saves_moves_ins_tax_exemption_and_discount_claims(
    cedar, clerk, docs_dir, monkeypatch
):
    """DEF-CUS-10233 — New Connect's charges step draws Move-in's Tax and
    Discounts panels (image 02) and the owner's account is written by
    Move-in's own code (`move_in_preferences`): rating's certificate row, the
    certificate FILE in the KYC folder, the claim through customers' claim
    door — and the BLANKET exemption columns stay unset (`DEF-CUS-9724`).

    Worked case: Kyle's build, exemption *Religious organisation* on the city
    tax, certificate IA-EX-2231 issued 2026-01-15, expiring 2027-01-15, file
    `exemption.pdf`; one claim of the plan's SENIOR discount."""
    import base64
    import uuid

    from apps.customers import discounts as customers_discounts
    from apps.customers.account_document_models import AccountDocument
    from apps.work import connection_models as work_tables
    from apps.rating import discount_services
    from apps.rating import models as rating_models
    from tests.test_cr013_p4_tax_model import a_tax

    senior = str(uuid.uuid4())
    claimed = []

    def claim(actor, account_id, programme_id, household_size=None):
        claimed.append((str(account_id), programme_id))
        return {"claimed": True, "status": "pending"}

    monkeypatch.setattr(customers_discounts, "claim_assistance", claim)
    monkeypatch.setattr(discount_services, "discount_ids_carried", lambda account_id, on_day: {senior})
    request_id = _kyle(cedar, clerk)
    with _ctx(cedar):
        tax, _jurisdiction = a_tax(cedar, "City", name="City utility tax", kind="percent")
        category = rating_models.TaxExemptionCategory.objects.create(
            tenant=cedar, tax=tax, code="CHURCH", name="Religious organisation"
        )
    _kyle_build(
        cedar,
        clerk,
        request_id,
        _kyle_owner(
            tax_exempt=False,
            tax_exemption={
                "category_id": str(category.id),
                "certificate_ref": "IA-EX-2231",
                "issued_on": "2026-01-15",
                "expires_on": "2027-01-15",
                "certificate": {
                    "name": "exemption.pdf",
                    "content_type": "application/pdf",
                    "content_base64": base64.b64encode(b"%PDF-1.4 exemption").decode(),
                },
            },
            discount_claims=[{"discount_id": senior}],
        ),
    )
    with _ctx(cedar):
        draft = work_tables.Connection.objects.get(service_request_id=request_id)
        account = customers_models.Account.objects.get(pk=draft.owner_account_id)
        certificates = list(
            rating_models.TaxExemptionCertificate.objects.filter(account_id=account.pk).values_list(
                "certificate_ref", "issued_on", "expires_on"
            )
        )
        filed = list(
            AccountDocument.objects.filter(account_id=account.pk, doc_type="kyc").values_list(
                "document__display_name", flat=True
            )
        )
    assert [(ref, str(issued), str(expires)) for ref, issued, expires in certificates] == [
        ("IA-EX-2231", "2026-01-15", "2027-01-15")
    ], "the exemption certificate typed on New Connect never reached rating"
    assert any(name.endswith("-exemption.pdf") and name.startswith("account-documents/") for name in filed), (
        "the certificate file was not filed on the owner's account"
    )
    assert claimed == [(str(account.pk), senior)], "the discount claim never reached Move-in's claim door"
    assert (account.tax_exempt, account.tax_exempt_ref, account.tax_exempt_expires) == (False, None, None)
