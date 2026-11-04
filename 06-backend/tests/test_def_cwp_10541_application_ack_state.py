"""`DEF-CWP-10541` — a portal application's acknowledgement carries the state.

Found on the `DEF-CWP-10539` browser walk: Kyle Mark's Start service email read
*"900 Walk Lane, Rosenberg, 77471"* while the application screen had shown
*"900 Walk Lane, Rosenberg, TX 77471"*. The portal asks no state; the form
shows the matched premises' state, else the utility's own
(`selectors.draft_service_address`). The request now receives that same state
(`selectors.draft_service_state`) at Send.

Driven through the REAL Send endpoint, and the email is RENDERED by the
dispatcher's `render_for_dispatch`, so the sentence asserted is the one the
applicant reads.

⚠ **WHAT WOULD MAKE THIS PASS WRONGLY** (law 7, habit 2): a tenant whose
profile state is blank prints no state and could still pass a check on the
street alone — so the utility's state is set to *Texas* and the case asserts
the two-letter `TX` between town and ZIP; and a typed state the applicant
never gave would also read TX — the portal sends none, so TX can only come from
the utility's profile.

Runs on SQLite and on PostgreSQL (`--ds=config.settings.pgtest`).
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from apps.customers import models as customer_models
from apps.notifications import models as notification_models
from apps.notifications import rendering, seed_templates, service_request_events
from apps.portal import guest_api
from apps.tenancy.models import Tenant
from core.tenancy import tenant_context
from tests.test_us_cwp_helpers import *  # noqa: F401,F403
from tests.test_us_cwp_helpers import brand_fully, switch_on
from tests.test_us_ten_helpers import api_call

pytestmark = pytest.mark.django_db

TOKEN = "d1054100-5f6a-4b7c-8d9e-0f1a2b3c4d5e"

DRAFT = {
    "address_as_given": "900 Walk Lane",
    "address_city_as_given": "Rosenberg",
    "address_postal_code_as_given": "77471",
    "service_codes": ["water"],
    "applicant_kind": "person",
    "first_name": "Kyle",
    "last_name": "Mark",
    "email": "kyle.mark@example.test",
    "phone": "(281) 555-0142",
    "account_type_code": "residential",
}


def _call(tenant, fn, method, suffix, data):
    return api_call(
        fn,
        method,
        f"/api/{tenant.subdomain}/portal/public/applications/{TOKEN}{suffix}",
        tenant=tenant,
        data=data,
        token=TOKEN,
    )


def test_the_application_acknowledgement_reads_rosenberg_tx_77471(pine_hill, sarah):
    switch_on(pine_hill, sarah)
    brand_fully(pine_hill, sarah)
    Tenant.objects.filter(pk=pine_hill.id).update(state="Texas")
    with tenant_context(pine_hill.id):
        seed_templates.seed_notice_templates(sarah, on_date=date(2026, 10, 22))
    saved = _call(
        pine_hill,
        guest_api.application_draft,
        "put",
        "",
        {**DRAFT, "requested_start": (date.today() + timedelta(days=21)).isoformat()},
    )
    assert saved.status_code == 200, saved.data
    sent = _call(pine_hill, guest_api.submit_application, "post", "/submit", {"paperless": False})
    assert sent.status_code in (200, 201), sent.data
    with tenant_context(pine_hill.id):
        request = customer_models.ServiceRequest.objects.get(request_no=sent.data["reference"])
        assert request.address_state_as_given == "TX"
        [row] = notification_models.OutboundMessage.objects.filter(
            source_type=service_request_events.SOURCE_SERVICE_REQUEST,
            source_id=str(request.id),
        )
        art = rendering.render_for_dispatch(row)
    assert "900 Walk Lane, Rosenberg, TX 77471" in art.body, art.body
