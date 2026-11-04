"""`CR-164-BRC10` item 11 — New Connection step 1's owner lookup, PO ruling Q5.

THE WORKED CASE, as it was put to the PO on 2026-10-02 and ruled:

    **Rosa Alvarez**, born **1974-03-02**, SSN **123-45-6789**, is on file.

      * a clerk types SSN 123-45-6789 under any name      → **match**
      * a clerk types her licence TX-DL-4417               → **match**
      * a clerk types "Alvarez, Rosa" and 1974-03-02       → **possible match**
      * a clerk types "Alvarez, Rosa" alone                → nothing
      * a clerk types 1974-03-02 alone                     → nothing
      * a company with her Tax ID-free name                → nothing (BR-CUS-1022)
      * another utility's clerk types her SSN              → nothing (hard rule 1)

Each case calls the VIEW through DRF, not the function under it, so a route
that forgot to mount it or a view that dropped the tenant fails here.
"""

from __future__ import annotations

import pytest

from apps.customers import api as customers_api
from apps.customers import identity_match
from apps.customers import models as customers_models
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import brazos, dana, erin, lonestar, tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db

NAME = "Alvarez, Rosa"
DOB = "1974-03-02"
SSN = "123-45-6789"
LICENCE = "TX-DL-4417"


def _rosa(tenant):
    with tenant_ctx(tenant):
        customer = customers_models.Customer.objects.create(
            tenant=tenant, kind="person", display_name=NAME, customer_no="C-90001"
        )
        customer.date_of_birth = DOB
        identity_match.set_identifier(customer, "ssn", SSN)
        identity_match.set_identifier(customer, "driving_licence", LICENCE)
        customer.save()
    return customer


def _post(actor, tenant, body):
    from rest_framework.test import APIRequestFactory, force_authenticate

    request = APIRequestFactory().post("/api/x/customers/match", body, format="json")
    force_authenticate(request, user=actor.user)
    request.tenant_role = actor.role
    request.tenant_id = tenant.id
    with tenant_ctx(tenant):
        return customers_api.customers_match(request)


def test_an_ssn_alone_is_a_match_and_shows_last_four_only(brazos, dana):
    _rosa(brazos)
    response = _post(dana, brazos, {"kind": "person", "name": "Someone Else", "ssn": SSN})
    assert response.status_code == 200
    assert response.data["verdict"] == "match"
    row = response.data["candidates"][0]
    assert row["customer_no"] == "C-90001"
    assert row["ssn_last4"] == "6789"
    assert SSN not in str(response.data) and "123456789" not in str(response.data)


def test_a_licence_alone_is_a_match(brazos, dana):
    _rosa(brazos)
    response = _post(dana, brazos, {"kind": "person", "driving_licence": LICENCE})
    assert response.data["verdict"] == "match"


def test_name_and_date_of_birth_is_a_possible_match(brazos, dana):
    _rosa(brazos)
    response = _post(dana, brazos, {"kind": "person", "name": NAME, "date_of_birth": DOB})
    assert response.data["verdict"] == "possible"
    assert response.data["candidates"][0]["customer_no"] == "C-90001"


@pytest.mark.parametrize(
    "body",
    [
        {"kind": "person", "name": NAME},
        {"kind": "person", "date_of_birth": DOB},
        {"kind": "person", "name": NAME, "date_of_birth": "1980-01-01"},
        {"kind": "company", "name": NAME},
        {"name": NAME, "ssn": SSN},
    ],
)
def test_nothing_else_is_a_match(brazos, dana, body):
    _rosa(brazos)
    response = _post(dana, brazos, body)
    assert response.data == {"verdict": None, "candidates": []}


def test_another_utility_never_finds_her(brazos, lonestar, dana, erin):
    _rosa(brazos)
    response = _post(erin, lonestar, {"kind": "person", "ssn": SSN})
    assert response.data == {"verdict": None, "candidates": []}


def test_the_route_is_mounted_above_the_customer_wildcard():
    routes = [str(p.pattern) for p in customers_api.urlpatterns]
    assert routes.index("customers/match") < routes.index("customers/<str:customer_id>")
