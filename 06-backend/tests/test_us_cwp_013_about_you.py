# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-013 (EP-CWP-04) — About you: the applicant, and recognising
#           a returning customer. Screens: CWP-047
# Rules:    US-CWP-013 §2 (*"A draft holds no allocated number until submit"*) ·
#           TC-1 (close the tab, come back) · TC-2 (a returning customer is
#           flagged FOR A CLERK and the applicant is told nothing) · TC-3 (a
#           start date under three working days is refused) · TC-4 (a business
#           with no tax ID is refused) · TC-5 (an incomplete step is refused,
#           naming it, and the draft is KEPT) · TC-7 (the EXISTING matcher,
#           through the seam) · BR-CWP-031
# Tests:    this file — TC-1..TC-5 and TC-7 (TC-6 is PostgreSQL's:
#           tests/test_us_cwp_014_pg.py)
# Impacts:  apps/portal/applications.py · guest_api.py · selectors.py
# ───────────────────────────────────────────────────────
"""US-CWP-013 on the SQLite suite."""

from datetime import date, timedelta

import pytest

from apps.portal import applications, guest_api, models
from core.tenancy import tenant_context
from tests.test_us_cwp_helpers import *  # noqa: F401,F403
from tests.test_us_cwp_helpers import brand_fully, seed_addresses_for, switch_on
from tests.test_us_ten_helpers import api_call

TOKEN = "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d"


def _put(tenant, token, body):
    return api_call(
        guest_api.application_draft,
        "put",
        f"/api/{tenant.subdomain}/portal/public/applications/{token}",
        tenant=tenant,
        data=body,
        token=token,
    )


def _get(tenant, token):
    return api_call(
        guest_api.application_draft,
        "get",
        f"/api/{tenant.subdomain}/portal/public/applications/{token}",
        tenant=tenant,
        token=token,
    )


@pytest.fixture()
def pine_addresses(pine_hill, sarah):
    switch_on(pine_hill, sarah)
    brand_fully(pine_hill, sarah)
    seed_addresses_for(pine_hill, sarah)
    return pine_hill


@pytest.mark.django_db
def test_tc1_two_fields_a_closed_tab_and_it_is_all_still_there(pine_addresses):
    """TC-1 — *"Returning to the URL restores them. **No reference has been
    issued**."*"""
    _put(pine_addresses, TOKEN, {"first_name": "Daniel", "email": "d.okafor@example.test"})
    # The tab closes. Nothing is held anywhere but the server.
    body = _get(pine_addresses, TOKEN).data
    assert body["first_name"] == "Daniel"
    assert body["email"] == "d.okafor@example.test"
    # ⚠ THE HALF THAT MATTERS: no promise has been made, so no number exists.
    assert body["submitted"] is False
    assert body["reference"] is None
    with tenant_context(pine_addresses.id):
        assert models.PortalApplicationDraft.objects.count() == 1


@pytest.mark.django_db
def test_a_draft_is_created_by_the_first_keystroke_and_updated_by_the_next(pine_addresses):
    _put(pine_addresses, TOKEN, {"first_name": "D"})
    _put(pine_addresses, TOKEN, {"first_name": "Daniel", "last_name": "Okafor"})
    body = _get(pine_addresses, TOKEN).data
    assert (body["first_name"], body["last_name"]) == ("Daniel", "Okafor")
    with tenant_context(pine_addresses.id):
        assert models.PortalApplicationDraft.objects.count() == 1  # upsert, not append


@pytest.mark.django_db
def test_tc3_a_start_date_two_working_days_out_is_refused(pine_addresses):
    """TC-3 — *"Refused — 'at least three working days from today'."*"""
    # ⚠ THE REFUSAL COMES BACK AS A RESPONSE, NOT AS AN EXCEPTION. The DRF
    # handler renders every `ApiError` into the B12 §3 envelope, so a test that
    # used `pytest.raises` here would be asserting on a path the browser never
    # takes — and would pass on a view that swallowed the error.
    refused = _put(
        pine_addresses, TOKEN, {"requested_start": (date.today() + timedelta(days=1)).isoformat()}
    )
    assert refused.status_code == 422
    assert refused.data["message_key"] == "portal.application.startTooSoon"
    # And a date far enough out is accepted, so the rule is a rule and not a wall.
    ok = _put(pine_addresses, TOKEN, {"requested_start": (date.today() + timedelta(days=21)).isoformat()})
    assert ok.data["requested_start"] is not None


@pytest.mark.django_db
def test_the_three_working_days_skip_the_weekend(pine_addresses):
    """*Working* days, counted the way a person counts them.

    From a Thursday, three working days is the following Tuesday — not Sunday.
    """
    thursday = date(2026, 9, 3)
    assert applications.earliest_start(thursday) == date(2026, 9, 8)
    assert thursday.weekday() == 3 and applications.earliest_start(thursday).weekday() == 1


@pytest.mark.django_db
def test_tc4_a_business_with_no_tax_id_cannot_send(pine_addresses):
    """TC-4 — *"Refused; a business is identified by company name and tax ID
    rather than date of birth."*"""
    _put(
        pine_addresses,
        TOKEN,
        {
            "address_as_given": "31 Palm Ct",
            "service_codes": ["water"],
            "applicant_kind": "business",
            "company_name": "Palm Court Coffee",
            "email": "hello@palmcourt.test",
            "phone": "(512) 555-0190",
            "account_type_code": "residential",  # DEF-CWP-9818 (required at Send)
            "requested_start": (date.today() + timedelta(days=21)).isoformat(),
        },
    )
    with tenant_context(pine_addresses.id):
        row = applications.draft_row(pine_addresses.id, TOKEN)
        assert applications.missing_before_submit(row) == ["tax_id"]
        row.tax_id = "99-0001234"
        row.save(update_fields=["tax_id"])
        assert applications.missing_before_submit(row) == []


@pytest.mark.django_db
def test_tc5_an_incomplete_step_is_refused_by_name_and_the_draft_is_kept(pine_addresses):
    """TC-5 — *"Refused, naming the step, and the draft is kept."*"""
    _put(pine_addresses, TOKEN, {"first_name": "Daniel", "last_name": "Okafor"})
    with tenant_context(pine_addresses.id):
        row = applications.draft_row(pine_addresses.id, TOKEN)
        assert applications.missing_before_submit(row)[0] == "address"
    # The refusal changed nothing: everything typed is still there.
    assert _get(pine_addresses, TOKEN).data["first_name"] == "Daniel"


@pytest.mark.django_db
def test_a_field_the_form_does_not_have_is_refused_by_name(pine_addresses):
    """A silently dropped field is a form that says it saved and did not."""
    refused = _put(pine_addresses, TOKEN, {"ssn": "123-45-6789"})
    assert refused.status_code == 422
    assert refused.data["message_key"] == "portal.application.fieldNotAccepted"
    assert refused.data["params"]["field"] == "ssn"


@pytest.mark.django_db
def test_tc7_the_returning_customer_check_runs_through_the_existing_matcher(pine_addresses):
    """TC-2 · TC-7 — the check uses `apps.customers.identity_match`, the
    counter's own matcher, and answers **True or False**.

    ⚠ Nothing about the candidate crosses the seam, which is what keeps TC-2's
    *"does not tell the applicant"* true no matter what a later serialiser does.
    """
    from apps.portal.seams import customers_seam
    from apps.portal import sample_data

    with tenant_context(pine_addresses.id):
        found = customers_seam.recognise_returning_customer(
            kind="person",
            name=sample_data.OCCUPIER_NAME,
            phone=sample_data.OCCUPIER_PHONE,
        )
        stranger = customers_seam.recognise_returning_customer(
            kind="person", name="Nobody At All", phone="(512) 555-0999"
        )
    assert found is True and isinstance(found, bool)
    assert stranger is False
