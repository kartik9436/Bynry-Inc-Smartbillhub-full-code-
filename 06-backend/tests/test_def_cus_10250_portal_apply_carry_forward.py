# ── Trace ──────────────────────────────────────────────
# Defects:  DEF-CUS-10225 (customer data inconsistent across the create
#           screens) · DEF-CUS-10250 (the portal form asks Move-in's fields) ·
#           DEF-CUS-10251 (a portal request is approved only once staff set its
#           category) · DEF-CUS-10252 (the portal mailing address never
#           reached the move-in it led to)
# Rulings:  PO 2026-10-18, decision log *"CUSTOMER DATA AND UI CONSISTENT
#           ACROSS THE CREATE SCREENS"* and its *"Same day"* paragraphs: no
#           category on the portal, staff set it before Approve (*"this is
#           correct"*); last 4 of SSN only (*"okay"*); email optional; *"ALSO
#           DATA COLECTED IS NOT LOST"*
# Rules:    hard rule 1 (tenant context) · hard rule 7 (audit) · BR-CUS-092(c)
#           (an identifier is stored encrypted and served last four only) ·
#           hard-won law 14 (run on PostgreSQL: `--ds=config.settings.pgtest`)
# Journey:  08-qa/01-e2e/journeys/JCWPREQUESTTOACTIVE-portal-request-to-active-customer.md
# ───────────────────────────────────────────────────────
"""**Every field the applicant typed online, all the way to the account.**

Portal → staff request → Approve → move-in, and → new connection, through the
real doors (`PUT` the draft, `POST` a file, `POST` submit; the clerk's service
calls; `POST units/{id}/move-in`), reading every value back from the TABLES.

⚠ **WHAT WOULD MAKE THESE PASS WRONGLY** (law 7, habit 2):
  * reading the response instead of the row — every value is read back off the
    database row it should be on;
  * asserting the SSN last four from the read projection only — the raw column
    is read too, and must NOT hold the four digits in the clear;
  * an Approve refusal that passes because SOMETHING refused — the refusal is
    asserted by its message key, and the same request is then approved.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection

from apps.customers import co_owner_models
from apps.customers import models as customers_models
from apps.customers import service_request_api
from apps.customers import service_request_service as sr
from apps.portal import applications, guest_api
from apps.portal import models as portal_models
from core import errors

from tests.test_portal_request_to_active import (  # noqa: F401 — fixtures
    OPENED,
    SIX,
    _approve,
    _build,
    _ctx,
    _served_premises,
    _unit_move_in,
    cedar,
    clerk,
)
from tests.test_us_cwp_helpers import *  # noqa: F401,F403 — growth_plan · identity_seam · throttle
from tests.test_us_ten_helpers import api_call

pytestmark = pytest.mark.django_db

PDF = b"%PDF-1.7\n1 0 obj\n<< /Title (Photo ID) >>\n" + b"P" * 2000 + b"\n%%EOF"


def _db_id(pk):
    """A uuid as the raw column holds it — SQLite keeps 32 hex characters."""
    return pk.hex if connection.vendor == "sqlite" else str(pk)


def _start() -> str:
    return (date.today() + timedelta(days=21)).isoformat()


#: Image 04's sample applicant — every box filled.
EVERYTHING = {
    "address_as_given": "143 Willow Bend Dr",
    "address_unit_as_given": "Unit 1",
    "service_codes": ["water"],
    "applicant_kind": "person",
    "first_name": "Maria",
    "last_name": "Lopez",
    "phone": "(734) 555-0182",
    "email": "maria.lopez@example.com",
    "contact_by": "text",
    "date_of_birth": "1988-04-12",
    "ssn_last4": "4471",
    "co_applicant": True,
    "co_applicant_name": "Daniel Lopez",
    # DEF-CUS-10257 — Move-in's own code, never free text.
    "co_applicant_relationship": "spouse",
    "co_applicant_phone": "(734) 555-0144",
    "co_applicant_email": "dan.lopez@example.com",
    "co_applicant_date_of_birth": "1986-09-30",
    "mailing_same_as_service": False,
    "mailing_line1": "PO Box 2210",
    "mailing_line2": "Suite 4",
    "mailing_city": "Ypsilanti",
    "mailing_state": "MI",
    "mailing_postal_code": "48197",
    "paperless": True,
    "text_reminders": True,
    "preferred_language": "es",
}


def _put(tenant, token, body):
    return api_call(
        guest_api.application_draft,
        "put",
        f"/api/{tenant.subdomain}/portal/public/applications/{token}",
        tenant=tenant,
        data=body,
        token=token,
    )


def _upload(tenant, token):
    return api_call(
        guest_api.application_documents,
        "post",
        f"/api/{tenant.subdomain}/portal/public/applications/{token}/documents",
        tenant=tenant,
        data={
            "file": SimpleUploadedFile("maria-id.pdf", PDF, content_type="application/pdf"),
            "requirement": "photo_id",
        },
        body_format="multipart",
        token=token,
    )


def _send(tenant, token):
    return api_call(
        guest_api.submit_application,
        "post",
        f"/api/{tenant.subdomain}/portal/public/applications/{token}/submit",
        tenant=tenant,
        data={"paperless": True},
        token=token,
    )


def _apply_everything(tenant, token, **over):
    body = {**EVERYTHING, "requested_start": _start(), **over}
    saved = _put(tenant, token, body)
    assert saved.status_code in (200, 201), saved.data
    uploaded = _upload(tenant, token)
    assert uploaded.status_code in (200, 201), uploaded.data
    sent = _send(tenant, token)
    assert sent.status_code in (200, 201), sent.data
    return sent.data["request_id"]


# ═══════════════════════════════════════════════════════════════════════════
# 1 · THE DRAFT — every new box saved and read back
# ═══════════════════════════════════════════════════════════════════════════
def test_the_draft_saves_and_reads_back_every_move_in_field(cedar):
    token = "f0a1b2c3-d4e5-4f60-8a9b-10250aaaa001"
    saved = _put(cedar, token, {**EVERYTHING, "requested_start": _start()})
    assert saved.status_code in (200, 201), saved.data
    back = saved.data
    for key, value in EVERYTHING.items():
        if key == "service_codes":
            assert back[key] == value
            continue
        assert back[key] == value, key
    assert back["locales"] == ["en", "es"]
    with _ctx(cedar):
        row = portal_models.PortalApplicationDraft.objects.get(token=token)
        assert row.ssn_last4 == "4471"
        assert row.co_applicant_date_of_birth.isoformat() == "1986-09-30"
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT ssn_last4 FROM portal_application_drafts WHERE id = %s", [_db_id(row.pk)]
            )
            raw = cursor.fetchone()[0]
        assert raw and "4471" not in raw, "the four digits are stored encrypted"


def test_email_is_optional_and_the_category_is_not_asked(cedar):
    token = "f0a1b2c3-d4e5-4f60-8a9b-10250aaaa002"
    body = {**EVERYTHING, "requested_start": _start(), "email": None}
    body.pop("ssn_last4")
    assert _put(cedar, token, body).status_code in (200, 201)
    with _ctx(cedar):
        row = applications.draft_row(cedar.id, token)
        assert row.account_type_code is None
        assert applications.missing_before_submit(row) == []


def test_the_mobile_phone_is_still_required(cedar):
    token = "f0a1b2c3-d4e5-4f60-8a9b-10250aaaa003"
    assert _put(cedar, token, {**EVERYTHING, "requested_start": _start(), "phone": None}).status_code in (200, 201)
    with _ctx(cedar):
        assert applications.missing_before_submit(applications.draft_row(cedar.id, token)) == ["contact"]


@pytest.mark.parametrize(
    "value", ["123-45-6789", "123456789", "44", "44a1"], ids=["full-dashed", "full", "short", "letter"]
)
def test_only_the_last_four_of_the_ssn_is_accepted(cedar, value):
    token = "f0a1b2c3-d4e5-4f60-8a9b-10250aaaa004"
    refused = _put(cedar, token, {"ssn_last4": value})
    assert refused.status_code == 422, refused.data
    assert refused.data["message_key"] == "portal.application.ssnLast4Format"


def test_no_full_ssn_or_licence_is_taken_online(cedar):
    token = "f0a1b2c3-d4e5-4f60-8a9b-10250aaaa005"
    for field in ("ssn", "drivers_licence"):
        refused = _put(cedar, token, {field: "123456789"})
        assert refused.status_code == 422, field
        assert refused.data["message_key"] == "portal.application.fieldNotAccepted"


@pytest.mark.parametrize(
    "field,value,key",
    [
        ("email", "maria@", "portal.application.emailFormat"),
        ("co_applicant_email", "dan.example.com", "portal.application.emailFormat"),
        ("phone", "555-01", "portal.application.phoneFormat"),
        ("co_applicant_phone", "(734) 555-01445", "portal.application.phoneFormat"),
        ("contact_by", "pigeon", "portal.application.contactByUnknown"),
        # DEF-CUS-10257 — free text reached Move-in's card as a raw key.
        ("co_applicant_relationship", "Spouse", "portal.application.relationshipUnknown"),
    ],
)
def test_format_checks_refuse_a_malformed_value(cedar, field, value, key):
    token = "f0a1b2c3-d4e5-4f60-8a9b-10250aaaa006"
    refused = _put(cedar, token, {field: value})
    assert refused.status_code == 422, refused.data
    assert refused.data["message_key"] == key


def test_a_ticked_co_applicant_must_be_named(cedar):
    token = "f0a1b2c3-d4e5-4f60-8a9b-10250aaaa007"
    body = {**EVERYTHING, "requested_start": _start(), "co_applicant_name": None}
    assert _put(cedar, token, body).status_code in (200, 201)
    with _ctx(cedar):
        assert applications.missing_before_submit(applications.draft_row(cedar.id, token)) == [
            "co_applicant"
        ]
    refused = _send(cedar, token)
    assert refused.status_code == 422
    assert refused.data["params"]["step"] == "co_applicant"


def test_the_portal_contact_list_is_the_customers_one():
    assert applications.CONTACT_BY == customers_models.CONTACT_BY


def test_the_portal_relationship_list_is_move_ins_one():
    """DEF-CUS-10257 — Move-in's co-owner card offers these four codes
    (`CoOwnerCards.RELATIONSHIPS`); the portal card offers the same four, so a
    portal co-applicant reaches Move-in as a value its card can name."""
    assert applications.RELATIONSHIPS == ("spouse", "partner", "family", "other")


# ═══════════════════════════════════════════════════════════════════════════
# 2 · SEND — the request holds everything, and the clerk's read serves it
# ═══════════════════════════════════════════════════════════════════════════
def test_send_carries_every_field_onto_the_request(cedar):
    token = "f0a1b2c3-d4e5-4f60-8a9b-10250aaaa010"
    request_id = _apply_everything(cedar, token)
    with _ctx(cedar):
        row = customers_models.ServiceRequest.objects.get(pk=request_id)
        assert row.applicant_name == "Maria Lopez"
        assert (row.applicant_phone, row.applicant_email) == (
            "(734) 555-0182",
            "maria.lopez@example.com",
        )
        assert row.contact_by == "text"
        assert row.date_of_birth.isoformat() == "1988-04-12"
        assert row.applicant_ssn_last4 == "4471"
        assert row.ssn is None, "four digits are not a full SSN"
        # ONE card on lane CF-1's `co_applicants` — the columns the staff
        # capture writes — and the three legacy columns mirrored from it.
        [card] = row.co_applicants
        assert (
            card["full_name"],
            card["relationship"],
            card["phone"],
            card["email"],
            card["date_of_birth"],
        ) == ("Daniel Lopez", "spouse", "(734) 555-0144", "dan.lopez@example.com", "1986-09-30")
        assert row.co_applicant_name == "Daniel Lopez"
        assert (row.paperless, row.sms_reminders, row.preferred_language) == (True, True, "es")
        assert row.mailing_same is False
        assert (
            row.mailing_line1,
            row.mailing_line2,
            row.mailing_city,
            row.mailing_state,
            row.mailing_postal_code,
        ) == ("PO Box 2210", "Suite 4", "Ypsilanti", "MI", "48197")
        # Mirrored for every reader that predates the rename (CF-1).
        assert (
            row.billing_line1_as_given,
            row.billing_line2_as_given,
            row.billing_city_as_given,
            row.billing_state_as_given,
            row.billing_postal_code_as_given,
        ) == ("PO Box 2210", "Suite 4", "Ypsilanti", "MI", "48197")
        assert row.account_type_id is None, "the portal asks no category"
        docs = list(customers_models.ServiceRequestDocument.objects.filter(request=row))
        assert [(d.name, d.doc_type) for d in docs] == [("maria-id.pdf", docs[0].doc_type)]
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT applicant_ssn_last4 FROM service_requests WHERE id = %s", [_db_id(row.pk)]
            )
            raw = cursor.fetchone()[0]
        assert raw and "4471" not in raw, "stored encrypted"
        draft = portal_models.PortalApplicationDraft.objects.get(token=token)
        assert draft.ssn_last4 is None, "stored once — on the request"
        detail = service_request_api._detail(request_id)
    applicant = detail["applicant"]
    assert applicant["contact_by"] == "text"
    assert applicant["date_of_birth"] == "1988-04-12"
    assert applicant["identifier"]["ssn_last4"] == "4471"
    assert applicant["identifier"]["ssn_present"] is False, "no full SSN was given"
    [card] = applicant["co_applicants"]
    assert (card["full_name"], card["relationship"], card["phone"], card["email"], card["date_of_birth"]) == (
        "Daniel Lopez",
        "spouse",
        "(734) 555-0144",
        "dan.lopez@example.com",
        "1986-09-30",
    )
    assert applicant["preferences"] == {"paperless": True, "sms_reminders": True}
    assert applicant["category_to_be_set"] is True
    mailing = applicant["mailing_address"]
    assert (mailing["same"], mailing["line1"], mailing["postal_code"]) == (False, "PO Box 2210", "48197")


def test_an_unticked_co_applicant_does_not_travel(cedar):
    token = "f0a1b2c3-d4e5-4f60-8a9b-10250aaaa011"
    request_id = _apply_everything(cedar, token, co_applicant=False)
    with _ctx(cedar):
        row = customers_models.ServiceRequest.objects.get(pk=request_id)
        assert (row.co_applicant_name, row.co_applicants) == (None, [])


# ═══════════════════════════════════════════════════════════════════════════
# 3 · APPROVE — refused until staff set the category (image 05)
# ═══════════════════════════════════════════════════════════════════════════
def test_approve_is_refused_until_the_category_is_set(cedar, clerk):
    token = "f0a1b2c3-d4e5-4f60-8a9b-10250aaaa020"
    with _ctx(cedar):
        premises, (unit,), _plan = _served_premises(
            clerk, cedar, address="143 Willow Bend Dr", postal_code="48108"
        )
    request_id = _apply_everything(cedar, token)
    with _ctx(cedar):
        sr.update_request(
            clerk,
            request_id,
            {"picked_premises_id": str(premises["id"]), "picked_unit_id": str(unit["id"])},
        )
        sr.resolve_address(clerk, request_id)
        sr.link_customer(clerk, request_id, customer_id=None, tier=None)
        with pytest.raises(errors.BizError) as refused:
            sr.approve_and_raise(clerk, request_id, outcome="move_in")
        assert refused.value.message_key == "customers.serviceRequest.categoryFirst"
        row = customers_models.ServiceRequest.objects.get(pk=request_id)
        assert row.state == customers_models.ServiceRequest.SUBMITTED, "nothing moved"
        sr.set_customer_category(clerk, request_id, account_type_code="residential")
        assert service_request_api._detail(request_id)["applicant"]["category_to_be_set"] is False
        out = sr.approve_and_raise(clerk, request_id, outcome="move_in")
        assert "raised" in out["job"], out["job"]


# ═══════════════════════════════════════════════════════════════════════════
# 4 · THE WHOLE FLOW — portal → request → approve → move-in, nothing lost
# ═══════════════════════════════════════════════════════════════════════════
def _move_in_payload_from(detail, request_id, *, account_type):
    """What the Move-in wizard sends after prefilling from the request — every
    value read off the clerk's own `GET /service-requests/{id}`, none retyped."""
    applicant = detail["applicant"]
    [co] = applicant["co_applicants"]
    mailing = applicant["mailing_address"]
    prefs = applicant["preferences"]
    return {
        "account_type": account_type,
        "opened_at": OPENED,
        "contact": {
            "full_name": applicant["name"],
            "email": applicant["email"],
            "phone": applicant["phone"],
            "contact_by": applicant["contact_by"],
        },
        "customer": {
            "display_name": applicant["name"],
            "kind": "person",
            "identity": {
                "phone": applicant["phone"],
                "date_of_birth": applicant["date_of_birth"],
            },
        },
        "co_owners": [
            {
                "full_name": co["full_name"],
                "relationship": co["relationship"],
                "phone": co["phone"],
                "email": co["email"],
                "date_of_birth": co["date_of_birth"],
            }
        ],
        "addresses": [
            {
                "kind": "mailing",
                "line1": mailing["line1"],
                "line2": mailing["line2"],
                "city": mailing["city"],
                "state": mailing["state"],
                "postal_code": mailing["postal_code"],
            }
        ],
        "paperless": prefs["paperless"],
        "sms_reminders": prefs["sms_reminders"],
        "preferred_language": applicant["language"],
        "service_request_id": request_id,
    }


def _assert_account_holds_everything(tenant, account_id):
    with _ctx(tenant):
        account = customers_models.Account.objects.get(pk=account_id)
        assert (account.paperless, account.sms_reminders, account.preferred_language) == (
            True,
            True,
            "es",
        )
        contact = customers_models.Contact.objects.get(account=account)
        assert (contact.full_name, contact.email, contact.phone, contact.contact_by) == (
            "Maria Lopez",
            "maria.lopez@example.com",
            "(734) 555-0182",
            "text",
        )
        holder = (
            customers_models.CustomerAccount.live(tenant_id=tenant.id, account_id=account_id)
            .select_related("customer")
            .get()
            .customer
        )
        assert holder.display_name == "Maria Lopez"
        assert holder.date_of_birth.isoformat() == "1988-04-12"
        co = co_owner_models.AccountCoOwner.objects.get(account_id=account_id)
        assert (co.full_name, co.relationship, co.phone, co.email, co.date_of_birth.isoformat()) == (
            "Daniel Lopez",
            "spouse",
            "(734) 555-0144",
            "dan.lopez@example.com",
            "1986-09-30",
        )
        mailing = customers_models.Address.objects.get(account_id=account_id, kind="mailing")
        assert (mailing.line1, mailing.line2, mailing.city, mailing.state, mailing.postal_code) == (
            "PO Box 2210",
            "Suite 4",
            "Ypsilanti",
            "MI",
            "48197",
        )
        from apps.customers.account_document_models import AccountDocument

        assert AccountDocument.objects.filter(account_id=account_id).count() == 1, (
            "the applicant's document reaches the account"
        )


def test_portal_to_move_in_loses_nothing(cedar, clerk):
    token = "f0a1b2c3-d4e5-4f60-8a9b-10250aaaa030"
    with _ctx(cedar):
        premises, (unit,), _plan = _served_premises(
            clerk, cedar, address="143 Willow Bend Dr", postal_code="48108"
        )
    request_id = _apply_everything(cedar, token)
    _approve(clerk, cedar, request_id, outcome="move_in", pick=(premises["id"], unit["id"]))
    with _ctx(cedar):
        detail = service_request_api._detail(request_id)
    moved = _unit_move_in(
        cedar,
        clerk,
        unit["id"],
        _move_in_payload_from(detail, request_id, account_type="residential")
        | {"services": ["water"], "initial_reads": [{"meter_no": "WM-140", "value": "100"}]},
    )
    assert moved.status_code == 201, moved.data
    _assert_account_holds_everything(cedar, moved.data["id"])


def test_portal_to_new_connection_loses_nothing(cedar, clerk):
    token = "f0a1b2c3-d4e5-4f60-8a9b-10250aaaa031"
    request_id = _apply_everything(cedar, token, address_as_given="9 Juniper Bend", address_unit_as_given=None)
    _approve(clerk, cedar, request_id, outcome="new_connection")
    _built, _draft, _premises, units = _build(
        clerk, cedar, request_id, address="9 Juniper Bend", postal_code="48108", services=["water"]
    )
    with _ctx(cedar):
        detail = service_request_api._detail(request_id)
    moved = _unit_move_in(
        cedar,
        clerk,
        units["Unit 1"].id,
        _move_in_payload_from(detail, request_id, account_type="residential"),
    )
    assert moved.status_code == 201, moved.data
    _assert_account_holds_everything(cedar, moved.data["id"])


# ═══════════════════════════════════════════════════════════════════════════
# DEF-CUS-10258 — the sub-category staff set at Approve reaches Move-in as a
# value its form can show (found on the walk: Review printed the row's id)
# ═══════════════════════════════════════════════════════════════════════════
def test_the_sub_category_set_at_approve_opens_move_in_as_its_code(cedar, clerk):
    from apps.customers import move_in_request

    token = "f0a1b2c3-d4e5-4f60-8a9b-10250aaaa040"
    with _ctx(cedar):
        premises, (unit,), _plan = _served_premises(
            clerk, cedar, address="143 Willow Bend Dr", postal_code="48108"
        )
    request_id = _apply_everything(cedar, token)
    with _ctx(cedar):
        subtype = (
            customers_models.AccountSubtype.objects.filter(
                tenant_id=cedar.id, active=True, account_type__code="residential"
            )
            .order_by("code")
            .first()
        )
        assert subtype is not None, "the seeded residential sub-categories"
        sr.update_request(
            clerk,
            request_id,
            {"picked_premises_id": str(premises["id"]), "picked_unit_id": str(unit["id"])},
        )
        sr.set_customer_category(
            clerk, request_id, account_type_code="residential", account_subtype_id=subtype.id
        )
        seeded = move_in_request.form(request_id)["values"]["customer"]
        # The CODE — Move-in's sub-category list is keyed by code
        # (`accountSubtypeName`), so an id shows as no choice and as itself.
        assert seeded["account_subtype"] == subtype.code
        # Saved back with that code, the request keeps the same row.
        move_in_request.save_form(clerk, request_id, {"values": {"customer": seeded}, "step": 2})
        row = customers_models.ServiceRequest.objects.get(pk=request_id)
        assert row.account_subtype_id == subtype.id
