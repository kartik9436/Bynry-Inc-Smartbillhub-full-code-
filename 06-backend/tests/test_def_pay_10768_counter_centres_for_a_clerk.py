# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-PAY-10768 (payments audit L1-11 — "A counter can't be opened for
#           Main office", still blocked for the payments clerk on 2026-10-30)
# Rules:    A4 settings_lookups (a Billing Clerk has no Settings read — unchanged)
#           · BR-PAY-1160 (a counter is a till AT a place)
# ───────────────────────────────────────────────────────
"""The clerk who opens a till can read the places a till can be opened at.

*Start counter* read the Settings reference-data list, which A4 closes to a
Billing Clerk, so for the role that actually runs a counter the list came back
403 and *Main office* could never be chosen. `GET /counters/service-centres` is
payments' own read of the same rows: slug and name, nothing else.
"""

import pytest
from django.urls import resolve

from apps.payments import counters_api
from apps.tenancy import published_content_api
from apps.tenancy import published_content_models as places

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos
from tests.test_us_met_helpers import FakeUser, tenant_ctx
from tests.test_us_ten_helpers import api_call

pytestmark = [pytest.mark.django_db]


@pytest.fixture()
def centres(brazos):
    with tenant_ctx(brazos):
        for slug, name, shown in (("main", "Main office", True), ("depot", "Depot", False)):
            places.ServiceCentre.objects.create(
                tenant=brazos, slug=slug, name=name, address="101 Bend Road", is_shown_to_customers=shown
            )


def test_def_pay_10768__a_billing_clerk_reads_the_centres_a_till_can_be_at(brazos, centres):
    view = resolve("/api/brazosbend/counters/service-centres").func
    response = api_call(view, "get", role="billing_clerk", tenant=brazos, user=FakeUser())
    assert response.status_code == 200, response.data
    # Hidden from the portal is not hidden from the clerk at the depot window.
    assert response.data == {
        "centres": [{"slug": "depot", "name": "Depot"}, {"slug": "main", "name": "Main office"}]
    }


def test_def_pay_10768__the_settings_read_stays_closed_to_the_clerk(brazos, centres):
    """A4 is signed and unchanged: the fix is a second door, not a wider first one."""
    response = api_call(
        published_content_api.service_centres, "get", role="billing_clerk", tenant=brazos, user=FakeUser()
    )
    assert response.status_code == 403


def test_def_pay_10768__the_static_path_is_not_read_as_a_counter_id():
    assert resolve("/api/brazosbend/counters/service-centres").func is counters_api.counter_centres
