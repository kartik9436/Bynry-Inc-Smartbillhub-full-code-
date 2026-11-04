"""`DEF-CUS-10043` — the Approve dialog's *Search customer*, by the request's ID.

PO 2026-10-11: *"please use existing customer ID search function … use existing
rule"*. The route asks `owner_lookup`'s move-in *Search customer ID* with the
identity the request holds; these cases pin that it is the SAME rule (a request
naming nobody on file is `new`) and that the route answers over HTTP.
"""
from __future__ import annotations

import pytest

from apps.customers import identity_match, owner_lookup
from apps.customers import service_request_api as api
from apps.customers import service_request_service as sr
from tests.test_cr094_applicant_messages_block import CAPTURE
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx  # noqa: F401
from tests.test_us_ten_helpers import api_call

pytestmark = pytest.mark.django_db


def test_a_request_naming_nobody_on_file_is_new_by_the_same_rule(brazos, dana):
    with tenant_ctx(brazos):
        request = sr.create_request(dana, CAPTURE)
        answer = owner_lookup.search_for_request(sr.request_row(request.id))
        same = owner_lookup.search_evidence(
            identity_match.evidence_from_service_request(sr.request_row(request.id))
        )
    assert answer["result"] == owner_lookup.RESULT_NEW
    assert answer == same


def test_the_route_answers_over_http(brazos, dana):
    with tenant_ctx(brazos):
        request = sr.create_request(dana, CAPTURE)
    got = api_call(
        api.service_request_customer_search,
        "get",
        f"/api/brazos/service-requests/{request.id}/customer-search",
        user=dana.user,
        role="system_admin",
        tenant=brazos,
        request_id=str(request.id),
    )
    assert got.status_code == 200
    assert got.data["result"] in owner_lookup.SEARCH_RESULTS
