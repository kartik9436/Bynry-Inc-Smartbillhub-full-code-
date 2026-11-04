# ── Trace ──────────────────────────────────────────────
# Change:   CR-187-BRC10 Phase 13, lane S-ORDER — the new routes through the
#           REAL stack: session sign-in, path tenancy, permission classes.
# Rules:    `07-endpoints.md` §0 rules 3, 10 · DEF-WRK-9593 (FieldAppRole) ·
#           WorkTemplateListRead (the office list does not admit the
#           technician; the mobile catalogue does) · hard rule 1
# Code:     apps/work/field_orders_api.py
# ───────────────────────────────────────────────────────
"""A signed-in field technician reaches the field routes and not the office's.

The service tests call functions; these go through `POST /auth/session` and
the URL resolver, which is the path a handset takes (the shape of
`test_def_wrk_9583_field_sign_in.py`, whose lesson was that a door tested by
function alone shipped broken)."""

from __future__ import annotations

import pytest
from django.test import Client

from apps.identity.models import User

from tests.isolation_helpers import writing_as_tenant
from tests.test_us_idn_helpers import (  # noqa: F401 — fixture used by name
    JSON,
    SC,
    api_path,
    idn,
)

pytestmark = pytest.mark.django_db

TECH = ("field.cr187@silvercreek.example", "T. Osei", "Prairie2026grass")


@pytest.fixture()
def tech_client(idn):
    user, _membership = idn.make_user(
        idn.silvercreek, TECH[0], TECH[1], password=TECH[2], role="field_technician"
    )
    with writing_as_tenant(idn.silvercreek):
        User.objects.filter(pk=user.pk).update(surface_scope="mobile")
    client = Client()
    response = client.post(
        api_path("/auth/session", SC),
        data={"email": TECH[0], "password": TECH[2], "surface": "mobile"},
        content_type=JSON,
    )
    assert response.status_code == 201, response.content
    return client


def test_the_mobile_catalogue_admits_the_technician_and_the_office_list_does_not(tech_client):
    mobile = tech_client.get(api_path("/work/mobile/templates", SC))
    office = tech_client.get(api_path("/work/templates", SC))
    assert mobile.status_code == 200, mobile.content
    assert set(mobile.json()) >= {"count", "next", "previous", "results"}
    assert office.status_code == 403


@pytest.mark.parametrize("path", ["/work/acceptance-queue", "/work/field-raised"])
def test_the_office_queues_refuse_the_technician(tech_client, path):
    assert tech_client.get(api_path(path, SC)).status_code == 403


def test_a_raise_with_no_key_is_refused_by_name_through_the_stack(tech_client):
    """A login with no technician PROFILE is refused before anything else;
    with one, the missing key is named. Either way: no order, no 500."""
    response = tech_client.post(api_path("/work/mobile/orders", SC), data={}, content_type=JSON)
    assert response.status_code in (403, 422), response.content
    assert response.json().get("message_key") in (
        "work.raise.field_only",
        "work.raise.capture_key_required",
    )


def test_a_claim_on_an_unknown_job_is_a_404_through_the_stack(tech_client):
    response = tech_client.post(
        api_path("/work/mobile/jobs/01a10711-e839-7fba-a5e0-3762f041dd2e/claim", SC),
        data={},
        content_type=JSON,
    )
    assert response.status_code == 404
