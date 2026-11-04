# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-015 (EP-CWP-04) — ask for a quick service. Screens: CWP-010
# Rules:    BR-CWP-026 (may create work, NEVER change an account) · BR-CWP-076
#           (channel `customer_portal`) · BR-CWP-028 (ends on a reference) ·
#           TC-2 (a bill question names the bill) · TC-3 (⚠ assert the account
#           row is byte-identical afterwards) · TC-4 (requests off → the cards
#           are absent AND the endpoint refuses) · TC-6 (a category only the
#           other utility configured is not offered here) · TC-7 (a renamed
#           category shows its new label)
# Tests:    this file
# Impacts:  apps/portal/selectors.py · guest_api.py · services.py
# ───────────────────────────────────────────────────────
"""US-CWP-015 on the SQLite suite."""

import pytest

from apps.customers import models as customers_models
from apps.portal import guest_api, sample_data, settings_service
from apps.portal.seams.customers_seam import CHANNEL_CUSTOMER_PORTAL
from core.tenancy import tenant_context
from tests.test_us_cwp_helpers import *  # noqa: F401,F403
from tests.test_us_cwp_helpers import brand_fully, seed_addresses_for, switch_on
from tests.test_us_ten_helpers import api_call


def _cards(tenant):
    return api_call(
        guest_api.quick_services,
        "get",
        f"/api/{tenant.subdomain}/portal/public/quick-services",
        tenant=tenant,
    ).data["categories"]


def _ask(tenant, **body):
    return api_call(
        guest_api.quick_request,
        "post",
        f"/api/{tenant.subdomain}/portal/public/requests",
        tenant=tenant,
        data=body,
    )


@pytest.fixture()
def pine(pine_hill, sarah):
    switch_on(pine_hill, sarah)
    brand_fully(pine_hill, sarah)
    seed_addresses_for(pine_hill, sarah)
    return pine_hill


@pytest.mark.django_db
def test_tc1_a_re_read_ask_ends_on_a_reference_the_clerk_can_read(pine):
    """TC-1 — *"A reference, and a clerk sees the tenant's own re-read
    category."*"""
    assert [row["code"] for row in _cards(pine)][:3] == [
        "re_read",
        "missed_collection",
        "copy_of_bill",
    ]
    body = _ask(
        pine,
        category="re_read",
        name="Daniel Okafor",
        phone="(512) 555-7730",
        address="1408 Elm St",
        details="The reading is double last month's.",
    ).data
    assert body["reference"].startswith("SR-")
    with tenant_context(pine.id):
        request = customers_models.ServiceRequest.objects.get(pk=body["request_id"])
        assert request.channel == CHANNEL_CUSTOMER_PORTAL
        # There is NO `category` column on this table (`DEF-CWP-3701`), so the
        # card's own label is what a clerk reads, in words.
        assert "A meter reading looks wrong" in request.what_they_said or "re_read" in request.what_they_said


@pytest.mark.django_db
def test_tc2_a_bill_question_needs_the_bill_number_and_the_row_names_it(pine):
    """TC-2 — *"Requires the bill number, and the resulting row **names that
    bill**."*"""
    # ⚠ A REFUSAL IS A RESPONSE, NOT AN EXCEPTION — the DRF handler renders
    # every `ApiError` into the B12 §3 envelope, which is what the browser sees.
    refused = _ask(
        pine, category="bill_question", name="D. Okafor", phone="(512) 555-7730", address="1408 Elm St"
    )
    assert refused.status_code == 422
    assert refused.data["message_key"] == "portal.request.billNumberRequired"

    body = _ask(
        pine,
        category="bill_question",
        name="D. Okafor",
        phone="(512) 555-7730",
        address="1408 Elm St",
        bill_number="BL-2608-0141",
    ).data
    with tenant_context(pine.id):
        request = customers_models.ServiceRequest.objects.get(pk=body["request_id"])
        assert "BL-2608-0141" in request.what_they_said


@pytest.mark.django_db
def test_tc3_asking_to_change_the_account_holder_changes_no_account(pine):
    """TC-3 — *"Accepted as a **request a clerk judges** — and nothing on the
    account changes. ⚠ Assert the account row is byte-identical afterwards."*"""
    with tenant_context(pine.id):
        before = sorted(
            (str(row.id), row.status_id, row.account_type_id, row.updated_at.isoformat())
            for row in customers_models.Account.objects.all()
        )
    body = _ask(
        pine,
        category="other",
        name="Someone Else",
        phone="(512) 555-0111",
        address="1408 Elm St",
        details="Please put the account in my name instead.",
    ).data
    assert body["reference"] is not None  # it becomes WORK, which is the point
    with tenant_context(pine.id):
        after = sorted(
            (str(row.id), row.status_id, row.account_type_id, row.updated_at.isoformat())
            for row in customers_models.Account.objects.all()
        )
    assert after == before and before != []


@pytest.mark.django_db
def test_tc4_a_utility_with_requests_off_offers_no_cards_and_refuses_the_endpoint(pine, sarah):
    """TC-4 — both halves. ⚠ **BR-CWP-002: the refusal is at the EDGE**, because
    a screen that simply hides the cards is defeated by calling the endpoint."""
    with tenant_context(pine.id):
        settings_service.save_settings(sarah, pine.id, {"requests_enabled": False})
    assert _cards(pine) == []
    refused = _ask(
        pine, category="re_read", name="D. Okafor", phone="(512) 555-7730", address="1408 Elm St"
    )
    assert refused.status_code == 409
    assert refused.data["message_key"] == "portal.request.notOffered"


@pytest.mark.django_db
def test_tc6_a_category_only_the_other_utility_configured_is_not_offered_here(
    pine, oak_ridge, elena
):
    """TC-6 — *"A category configured only by Oak Ridge → Not offered on Pine
    Hill's form."*"""
    switch_on(oak_ridge, elena)
    brand_fully(oak_ridge, elena, sample_data.OAK_RIDGE)
    with tenant_context(oak_ridge.id):
        settings_service.save_branding(
            elena,
            oak_ridge.id,
            {"quick_service_categories": sample_data.OAK_RIDGE["quick_services"]},
        )
    assert "standpipe_permit" in [row["code"] for row in _cards(oak_ridge)]
    assert "standpipe_permit" not in [row["code"] for row in _cards(pine)]
    # And naming it on Pine Hill's endpoint is refused before anything is written.
    refused = _ask(
        pine, category="standpipe_permit", name="D. Okafor", phone="(512) 555-7730", address="1408 Elm St"
    )
    assert refused.status_code == 422
    assert refused.data["message_key"] == "portal.request.categoryUnknown"


@pytest.mark.django_db
def test_tc7_a_renamed_category_shows_the_utilitys_own_words(oak_ridge, elena):
    """TC-7 — *"The renamed label appears — the six cards read from the tenant's
    configuration, not from a hardcoded list."*"""
    switch_on(oak_ridge, elena)
    with tenant_context(oak_ridge.id):
        settings_service.save_branding(
            elena,
            oak_ridge.id,
            {"quick_service_categories": sample_data.OAK_RIDGE["quick_services"]},
        )
    labels = {row["code"]: row["label"] for row in _cards(oak_ridge)}
    assert labels["re_read"] == "Check my meter reading"
    assert len(labels) == 3  # its own three, not the seeded six


@pytest.mark.django_db
def test_a_contact_and_an_address_are_required_because_a_request_nobody_can_answer_is_not_work(pine):
    """A name and a phone so we can answer; an address because `customers`
    refuses a request about nowhere (`BR-CUS-070`), and a screen that made it
    optional would be accepted by the form and refused by the service."""
    for missing in ("name", "phone", "address"):
        body = {
            "category": "re_read",
            "name": "D. Okafor",
            "phone": "(512) 555-7730",
            "address": "1408 Elm St",
        }
        body[missing] = ""
        refused = _ask(pine, **body)
        assert refused.status_code == 422, missing
        assert refused.data["message_key"] == "portal.request.fieldRequired"
