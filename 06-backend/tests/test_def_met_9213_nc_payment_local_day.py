"""DEF-MET-9213 — a payment taken at New Connection's Create keeps the day the clerk typed.

Found by the New Connection end-to-end web walk (2026-10-02), building S1, on a
utility on America/Chicago: step 4's card payment was dated **10/02/2026** and the
request's Charges tab showed **10/01/2026**. The commit anchored the typed date at
midnight **UTC** (`connections._moment_of`), which is 19:00 the evening before in
Chicago, and every screen reads the instant back in the utility's own zone.

`OQ-153` is CLOSED (PO 2026-08-12): *midnight in the UTILITY'S OWN timezone*.
`DEF-094` fixed the same fault in `payments.api._moment`; `tenancy.selectors.
tenant_timezone` is the one derivation both halves read (BR-TEN-081).
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import pytest

from apps.metering import connections as w6
from apps.tenancy import models as tenancy_models
from tests.test_us_met_helpers import *  # noqa: F401,F403
from tests.test_us_met_helpers import brazos, tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db

CHICAGO = ZoneInfo("America/Chicago")


def _on_chicago(tenant):
    with tenant_ctx(tenant):
        tenancy_models.TenantSettings.objects.update_or_create(
            tenant_id=tenant.id, defaults={"timezone": "America/Chicago"}
        )


def test_the_typed_day_is_the_day_the_utility_sees(brazos):
    """2 October typed → 2 October in Chicago (05:00 UTC in CDT), never 1 October."""
    _on_chicago(brazos)
    with tenant_ctx(brazos):
        moment = w6._moment_of(date(2026, 10, 2))
    assert moment.astimezone(CHICAGO).date() == date(2026, 10, 2)
    assert moment == datetime(2026, 10, 2, 5, 0, tzinfo=UTC)


def test_a_utility_on_utc_is_unchanged(brazos):
    """The green case for a utility that has not chosen a zone: midnight UTC."""
    with tenant_ctx(brazos):
        tenancy_models.TenantSettings.objects.filter(tenant_id=brazos.id).update(timezone="UTC")
        moment = w6._moment_of(date(2026, 10, 2))
    assert moment == datetime(2026, 10, 2, 0, 0, tzinfo=UTC)
