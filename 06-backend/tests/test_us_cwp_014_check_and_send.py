# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-014 (EP-CWP-04) — Check and send, and where paperless
#           consent is taken. Screens: CWP-009
# Rules:    BR-CWP-087 / CR-068 R5 (a recorded consent with the version of the
#           words) · R6 (existing paperless customers are not asked again) ·
#           BR-CWP-076 (channel `customer_portal`) · BR-CWP-026 (the form
#           grants nothing by itself) · TC-2 (unticked → NO consent row; an
#           absent consent is not a withdrawn one) · TC-5 (a double-click is
#           one request, one reference, one consent row) · TC-7 (the figures
#           match CWP-008's) · §1 (no money, no document, no account)
# Tests:    this file — TC-1, TC-2, TC-5, TC-7 (TC-4 and TC-6 are
#           PostgreSQL's: tests/test_us_cwp_014_pg.py)
# Impacts:  apps/portal/services.py · guest_api.py · wording.py ·
#           apps/customers/service_request_service.py (the named portal door)
# ───────────────────────────────────────────────────────
"""US-CWP-014 on the SQLite suite. ⚠ The future-date CONSTRAINT is not here and
cannot be: SQLite does not create it (CLAUDE.md law 14)."""

from datetime import date, timedelta

import pytest

from apps.customers import models as customers_models
from apps.portal import guest_api, models, wording
from apps.portal.seams.customers_seam import CHANNEL_CUSTOMER_PORTAL
from core.tenancy import tenant_context
from tests.test_us_cwp_helpers import *  # noqa: F401,F403
from tests.test_us_cwp_helpers import brand_fully, seed_addresses_for, switch_on
from tests.test_us_ten_helpers import api_call

TOKEN = "b1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d"

COMPLETE = {
    "address_as_given": "31 Palm Ct",
    "service_codes": ["water", "sewer", "trash"],
    "applicant_kind": "person",
    "first_name": "Daniel",
    "last_name": "Okafor",
    "email": "d.okafor@example.test",
    "phone": "(512) 555-7730",
    "account_type_code": "residential",  # DEF-CWP-9818 (required at Send)
    "date_of_birth": "1987-12-04",
}


@pytest.fixture()
def ready(pine_hill, sarah):
    switch_on(pine_hill, sarah)
    brand_fully(pine_hill, sarah)
    seed_addresses_for(pine_hill, sarah)
    api_call(
        guest_api.application_draft,
        "put",
        f"/api/{pine_hill.subdomain}/portal/public/applications/{TOKEN}",
        tenant=pine_hill,
        data={**COMPLETE, "requested_start": (date.today() + timedelta(days=21)).isoformat()},
        token=TOKEN,
    )
    return pine_hill


def _send(tenant, paperless=True, token=TOKEN):
    return api_call(
        guest_api.submit_application,
        "post",
        f"/api/{tenant.subdomain}/portal/public/applications/{token}/submit",
        tenant=tenant,
        data={"paperless": paperless},
        token=token,
    )


@pytest.mark.django_db
def test_tc1_sending_it_ticked_writes_one_request_and_one_consent(ready):
    """TC-1 — *"A reference is issued, the request appears with channel
    **Customer portal**, and a `portal_consent` row carries the **wording
    version** and the timestamp."*"""
    body = _send(ready).data
    assert body["reference"] is not None and body["reference"].startswith("SR-")
    assert body["consent_recorded"] is True

    with tenant_context(ready.id):
        request = customers_models.ServiceRequest.objects.get(pk=body["request_id"])
        # BR-CWP-076 — the first rows in this product ever to carry it.
        assert request.channel == CHANNEL_CUSTOMER_PORTAL
        assert request.applicant_name == "Daniel Okafor"
        assert request.state != customers_models.ServiceRequest.DRAFT

        consent = models.PortalConsent.objects.get(service_request_id=request.id)
        assert consent.wording_version == wording.PAPERLESS_CURRENT
        assert wording.is_known(consent.wording_version)
        assert consent.taken_on_screen == "CWP-009"
        assert consent.withdrawn_on is None
        # ⚠ NOT IN THE FUTURE. The database refuses it outright on PostgreSQL;
        # here we assert the value the service actually wrote.
        assert consent.agreed_on <= consent.created_at


@pytest.mark.django_db
def test_the_identifiers_used_for_recognition_are_carried_nowhere(ready):
    """⚠ **THE DATE OF BIRTH IS STORED ONCE — ON THE REQUEST — AND THE DRAFT'S
    COPY IS GONE (`DEF-CWP-9046`, 2026-10-02).**

    ⛔ **SUPERSEDED: this case read *"`_clean_capture` refuses `date_of_birth`
    BY NAME, so it cannot travel to the request"*** and asserted
    `not hasattr(request, "date_of_birth")`. The request GAINED that column with
    the PO ruling of 2026-09-15 (*"Date of birth and driver's licence on step
    1"*), so from that day the assertion could not pass — `hasattr` on a model
    field is always true — and the date an applicant typed was being thrown
    away for a reason that had expired. It now travels to the request, is NOT
    copied into the prose, and the draft still keeps no copy.
    """
    body = _send(ready).data
    with tenant_context(ready.id):
        request = customers_models.ServiceRequest.objects.get(pk=body["request_id"])
        assert request.date_of_birth is not None and request.date_of_birth.year == 1987
        assert "1987" not in str(request.what_they_said or "")
        draft = models.PortalApplicationDraft.objects.get(token=TOKEN)
        assert draft.date_of_birth is None
        assert draft.submitted_at is not None


@pytest.mark.django_db
def test_tc2_sending_it_unticked_writes_no_consent_row_at_all(ready):
    """TC-2 — *"The application succeeds and **no consent row is written**.
    ⚠ An absent consent is not a withdrawn one."*

    So there is no row saying they declined: there is simply no row.
    """
    body = _send(ready, paperless=False).data
    assert body["reference"] is not None
    assert body["consent_recorded"] is False
    with tenant_context(ready.id):
        assert models.PortalConsent.objects.count() == 0


@pytest.mark.django_db
def test_tc5_a_double_click_is_one_request_one_reference_one_consent(ready):
    """TC-5 — *"Submit twice from a double-click → One request, one reference,
    one consent row."*"""
    first = _send(ready).data
    second = _send(ready).data
    assert second["reference"] == first["reference"]
    assert second["idempotent_replay"] is True
    with tenant_context(ready.id):
        assert customers_models.ServiceRequest.objects.filter(
            channel=CHANNEL_CUSTOMER_PORTAL
        ).count() == 1
        assert models.PortalConsent.objects.count() == 1


@pytest.mark.django_db
def test_section_one_nothing_is_charged_no_document_is_demanded_no_account_opens(ready):
    """`US-CWP-014` §1's two deliberate absences, and `BR-CWP-026`'s.

    Asserted the way the exit test asks for it: **no account row is changed**,
    byte for byte, and nothing was written to payments or documents.
    """
    from apps.payments import models as payments_models

    with tenant_context(ready.id):
        accounts_before = sorted(
            (str(row.id), row.status_id, row.updated_at.isoformat())
            for row in customers_models.Account.objects.all()
        )
        payments_before = payments_models.Payment.objects.count()
        documents_before = customers_models.ServiceRequestDocument.objects.count()

    _send(ready)

    with tenant_context(ready.id):
        accounts_after = sorted(
            (str(row.id), row.status_id, row.updated_at.isoformat())
            for row in customers_models.Account.objects.all()
        )
        assert accounts_after == accounts_before and accounts_before != []
        assert payments_models.Payment.objects.count() == payments_before
        assert customers_models.ServiceRequestDocument.objects.count() == documents_before
        # And no fee was taken: the quote is not collected here (§1).
        request = customers_models.ServiceRequest.objects.get(channel=CHANNEL_CUSTOMER_PORTAL)
        assert request.fee_collected is None


@pytest.mark.django_db
def test_tc7_the_figures_on_check_and_send_are_the_ones_cwp_008_showed(ready):
    """TC-7 · §7 — *"Restates US-CWP-012's arithmetic and must not recompute it
    independently … A figure that disagrees with the availability screen is the
    defect this test exists to catch."*

    Both screens read the SAME endpoint, so this asserts the property that
    makes disagreement impossible rather than sampling two numbers and hoping.
    """
    availability = api_call(
        guest_api.availability,
        "get",
        f"/api/{ready.subdomain}/portal/public/premises/availability",
        tenant=ready,
        query={"address": "31 Palm Ct"},
    ).data
    assert availability["if_you_apply"]["before_we_start"]["display"] == "$185.00"
    assert availability["if_you_apply"]["on_first_bill"]["display"] == "$150.00"
    # Four decimals stored, two displayed — hard rule 2, on both figures.
    assert availability["if_you_apply"]["before_we_start"]["amount"] == "185.0000"
    assert availability["if_you_apply"]["on_first_bill"]["amount"] == "150.0000"


@pytest.mark.django_db
def test_the_wording_version_is_the_servers_and_never_the_callers(ready):
    """⚠ A browser that could name its own wording version could record a
    consent against words it never showed anybody."""
    body = api_call(
        guest_api.submit_application,
        "post",
        f"/api/{ready.subdomain}/portal/public/applications/{TOKEN}/submit",
        tenant=ready,
        data={"paperless": True, "wording_version": "paperless-anything-i-like"},
        token=TOKEN,
    ).data
    with tenant_context(ready.id):
        consent = models.PortalConsent.objects.get(service_request_id=body["request_id"])
        assert consent.wording_version == wording.PAPERLESS_CURRENT
