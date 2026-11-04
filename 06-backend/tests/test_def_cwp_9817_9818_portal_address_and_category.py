# ── Trace ──────────────────────────────────────────────
# Defects:  DEF-CWP-9817 — Start service asked the address as ONE box; the
#           blueprint (p31) draws Street address · Town · ZIP code · unit, and
#           the match must use town and ZIP (`BR-CUS-1091`, PO 2026-09-22).
#           DEF-CWP-9818 — PO ruling 2026-10-06 (b): the applicant picks the
#           customer Category and Sub-category on step 3; the clerk can still
#           change it.
# Rules:    CLAUDE.md hard rule 8 (premises is the one address; the parts are
#           `_as_given`) · BR-CUS-070 (what was said is kept) · B14 rule 31
#           (codes and names travel to a guest, never ids)
# Runs:     SQLite (default) AND PostgreSQL 16 (`--ds=config.settings.pgtest`)
#           — the match narrows in SQL (`istartswith`, `startswith`), so the
#           PostgreSQL run is the one that proves it (law 14's posture).
# ───────────────────────────────────────────────────────
"""The address in parts, matched on all three; the category the applicant picked."""

from datetime import date, timedelta

import pytest

from apps.customers import models as customers_models
from apps.portal import applications, guest_api, models, selectors
from apps.tenancy import models as tenancy_models
from core.tenancy import tenant_context
from tests.test_us_cwp_helpers import *  # noqa: F401,F403
from tests.test_us_cwp_helpers import brand_fully, seed_addresses_for, switch_on
from tests.test_us_ten_helpers import api_call

TOKEN = "d9817c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d"
PALM = {"address": "31 Palm Ct", "city": "Austin", "postal_code": "78702"}


@pytest.fixture()
def pine(pine_hill, sarah):
    switch_on(pine_hill, sarah)
    brand_fully(pine_hill, sarah)
    seed_addresses_for(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        tenancy_models.Tenant.objects.filter(pk=pine_hill.id).update(state="TX")
        commercial, _ = customers_models.AccountType.objects.get_or_create(
            tenant_id=pine_hill.id, code="commercial", defaults={"name": "Commercial", "sort_order": 20}
        )
        customers_models.AccountType.objects.filter(pk=commercial.pk).update(active=True, legacy=False)
        residential, _ = customers_models.AccountType.objects.get_or_create(
            tenant_id=pine_hill.id, code="residential", defaults={"name": "Residential", "sort_order": 10}
        )
        customers_models.AccountType.objects.filter(pk=residential.pk).update(active=True, legacy=False)
        # A category the utility has STOPPED offering (Settings › Stop offering
        # sets `legacy`, DEF-CUS-9808) — must not be offered or accepted.
        stopped, _ = customers_models.AccountType.objects.get_or_create(
            tenant_id=pine_hill.id, code="stopped_kind", defaults={"name": "Stopped kind"}
        )
        customers_models.AccountType.objects.filter(pk=stopped.pk).update(legacy=True, active=True)
        customers_models.AccountSubtype.objects.get_or_create(
            tenant_id=pine_hill.id,
            code="healthcare_9818",
            defaults={"name": "Healthcare", "account_type": commercial},
        )
        customers_models.AccountSubtype.objects.get_or_create(
            tenant_id=pine_hill.id,
            code="single_family_9818",
            defaults={"name": "Single-family", "account_type": residential},
        )
    return pine_hill


def _availability(tenant, **query):
    path = f"/api/{tenant.subdomain}/portal/public/premises/availability?" + "&".join(
        f"{k}={v.replace(' ', '+')}" for k, v in query.items()
    )
    return api_call(guest_api.availability, "get", path, tenant=tenant)


def _put(tenant, body, token=TOKEN):
    return api_call(
        guest_api.application_draft,
        "put",
        f"/api/{tenant.subdomain}/portal/public/applications/{token}",
        tenant=tenant,
        data=body,
        token=token,
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


# ── DEF-CWP-9817 · the match uses town and ZIP ──────────────────────────────


@pytest.mark.django_db
def test_street_town_and_zip_that_agree_with_the_register_are_matched(pine):
    body = _availability(pine, **PALM).data
    assert body["matched"] is True
    # The address AS WE HOLD IT, in the one US form every later step uses.
    assert body["address"] == "31 Palm Ct, Austin, TX 78702"


@pytest.mark.django_db
def test_the_right_street_in_the_wrong_zip_is_not_matched(pine):
    """THE RED PROOF. The one-box matcher read the street alone, so `31 Palm Ct`
    in ANOTHER town's ZIP was taken for Pine Hill's — a stranger shown another
    address's services and fees. On street + town + ZIP it is not ours, and a
    person looks at it (`US-CWP-012` TC-2: not a refusal)."""
    body = _availability(pine, address="31 Palm Ct", city="Austin", postal_code="78701").data
    assert body["matched"] is False
    assert body["offered"]  # still an Apply route, with services to tick


@pytest.mark.django_db
def test_a_draft_saved_in_parts_is_matched_on_all_three_and_shows_the_premises(pine):
    _put(
        pine,
        {
            "address_as_given": "31 palm court",  # how a person types it
            "address_city_as_given": "Austin",
            "address_postal_code_as_given": "78702",
            "address_unit_as_given": "12",
        },
    )
    with tenant_context(pine.id):
        row = applications.draft_row(pine.id, TOKEN)
        assert row.matched_premises_id is not None
        # BR-CUS-070 — what they SAID is kept, byte for byte.
        assert (row.address_as_given, row.address_city_as_given) == ("31 palm court", "Austin")
        view = selectors.draft_view(row)
    # BR-CUS-1091 — matched, so the PREMISES is what shows; the unit is their label.
    assert view["service_address"] == "31 Palm Ct, #12, Austin, TX 78702"


@pytest.mark.django_db
def test_an_address_we_do_not_hold_is_shown_in_us_form_from_the_parts(pine):
    """The PO's screenshot read *"Haustin Towers 2"*: what was typed, in one
    box. An address we do not hold now reads as an envelope does, with the
    utility's own state (the portal asks none)."""
    _put(
        pine,
        {
            "address_as_given": "1841 Quarry Hill Ct",
            "address_city_as_given": "Silver Creek",
            "address_postal_code_as_given": "78611",
            "address_unit_as_given": "Apt 12",
        },
    )
    with tenant_context(pine.id):
        row = applications.draft_row(pine.id, TOKEN)
        assert row.matched_premises_id is None
        view = selectors.draft_view(row)
    assert view["service_address"] == "1841 Quarry Hill Ct, Apt 12, Silver Creek, TX 78611"


@pytest.mark.django_db
def test_a_malformed_service_zip_is_refused(pine):
    refused = _put(pine, {"address_as_given": "31 Palm Ct", "address_postal_code_as_given": "7870"})
    assert refused.status_code == 422
    assert refused.data["message_key"] == "portal.application.mailingZipFormat"
    assert _put(pine, {"address_postal_code_as_given": "78702-1234"}).status_code == 200


def test_the_us_line_writes_a_bare_unit_number_with_a_hash():
    assert selectors.us_address_line("9 Elm St", "2B", "Austin", "TX", "78702") == (
        "9 Elm St, #2B, Austin, TX 78702"
    )
    assert selectors.us_address_line("9 Elm St", "Apt 2B", "Austin", None, "78702") == (
        "9 Elm St, Apt 2B, Austin, 78702"
    )
    assert selectors.us_address_line("9 Elm St") == "9 Elm St"


# ── DEF-CWP-9818 · the applicant's category ─────────────────────────────────


@pytest.mark.django_db
def test_the_draft_offers_only_the_categories_a_new_record_may_have(pine):
    view = _put(pine, {"first_name": "Kyle"}).data
    codes = [row["code"] for row in view["categories"]]
    assert "commercial" in codes and "residential" in codes
    assert "stopped_kind" not in codes  # Stop offering means not offered
    commercial = next(row for row in view["categories"] if row["code"] == "commercial")
    assert {"code": "healthcare_9818", "name": "Healthcare"} in commercial["subcategories"]
    # B14 rule 31 — no id travels to a stranger.
    assert all("id" not in row for row in view["categories"])


@pytest.mark.django_db
def test_a_stopped_category_and_a_foreign_sub_category_are_refused(pine):
    refused = _put(pine, {"account_type_code": "stopped_kind"})
    assert refused.status_code == 422
    assert refused.data["message_key"] == "portal.application.categoryNotOffered"
    # Healthcare is Commercial's, not Residential's.
    refused = _put(pine, {"account_type_code": "residential", "account_subtype_code": "healthcare_9818"})
    assert refused.status_code == 422
    assert refused.data["message_key"] == "portal.application.subcategoryNotOffered"
    ok = _put(pine, {"account_type_code": "commercial", "account_subtype_code": "healthcare_9818"})
    assert ok.status_code == 200
    assert (ok.data["account_type_code"], ok.data["account_subtype_code"]) == (
        "commercial",
        "healthcare_9818",
    )


@pytest.mark.django_db
def test_the_category_is_no_longer_required_before_send(pine):
    """⚠ **SUPERSEDED 2026-10-18 — `DEF-CUS-10250`.** This test asserted that a
    draft with no category was refused at Send (`DEF-CWP-9818`, PO 2026-10-06
    (b)). The PO then ruled *"this is correct"* to *"the portal version of the
    shared customer form does NOT ask the customer for internal
    classifications … staff set the category when they review the request, and
    it is required before the request can be approved"* — so the refusal moved
    to Approve (`test_def_cus_10250_portal_apply_carry_forward`), and Send no
    longer asks it."""
    _put(
        pine,
        {
            "address_as_given": "31 Palm Ct",
            "address_city_as_given": "Austin",
            "address_postal_code_as_given": "78702",
            "service_codes": ["water"],
            "first_name": "Kyle",
            "last_name": "Mark",
            "email": "kyle@example.test",
            "phone": "(512) 555-0101",
            "requested_start": (date.today() + timedelta(days=21)).isoformat(),
        },
    )
    with tenant_context(pine.id):
        row = applications.draft_row(pine.id, TOKEN)
        assert applications.missing_before_submit(row) == []


@pytest.mark.django_db
def test_send_carries_the_parts_and_the_pick_onto_the_request(pine, audit_rows):
    _put(
        pine,
        {
            "address_as_given": "1841 Quarry Hill Ct",
            "address_city_as_given": "Silver Creek",
            "address_postal_code_as_given": "78611",
            "address_unit_as_given": "Apt 12",
            "service_codes": ["water"],
            "first_name": "Kyle",
            "last_name": "Mark",
            "email": "kyle@example.test",
            "phone": "(512) 555-0101",
            "requested_start": (date.today() + timedelta(days=21)).isoformat(),
            "account_type_code": "commercial",
            "account_subtype_code": "healthcare_9818",
        },
    )
    body = _send(pine).data
    with tenant_context(pine.id):
        request = customers_models.ServiceRequest.objects.select_related(
            "account_type", "account_subtype"
        ).get(pk=body["request_id"])
        # BR-CUS-1091's own columns — what was SAID, for the Approve match.
        assert request.address_as_given == "1841 Quarry Hill Ct"
        assert request.address_city_as_given == "Silver Creek"
        assert request.address_postal_code_as_given == "78611"
        # ⛔ Read `is None  # never asked, never invented` from 2026-10-06
        # (aa3e68d30) until 2026-10-23: DEF-CWP-10541 (9a765717e) now sends the
        # state the form SHOWED — the matched premises', else the utility's own
        # (`selectors.draft_service_state`). Never asked, still never invented.
        assert request.address_state_as_given == "TX"
        # The applicant's pick IS the request's Type / Sub-category.
        assert request.account_type.code == "commercial"
        assert request.account_subtype.code == "healthcare_9818"
    # The pick a stranger made is audited like the clerk's (hard rule 7's posture).
    picked = [r for r in audit_rows if r["action"] == "service_request.category_set"]
    assert picked and picked[-1]["after"]["account_type"] == "commercial"
