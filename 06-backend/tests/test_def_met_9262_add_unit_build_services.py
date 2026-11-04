# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-MET-9262 — the request page's *Add unit* offered all eleven
#           services and the door accepted any, so a unit could join a build
#           with a service the build does not carry. Adding a NEW service to a
#           build is what *Add service* is for.
# Found:    the New Connection end-to-end walk follow-up, 2026-10-03.
# Rules:    CR-162-BRC10 item 7 (Add unit) · B14 rule 33 (a refusal ≤ 6 words)
# Front:    07-frontend/src/features/customers/BuildAddUnitForm.dom.test.tsx
# ───────────────────────────────────────────────────────
"""*Add unit* takes the build's own services, and only those.

⚠ **WHAT WOULD MAKE THIS PASS WRONGLY** (law 7): a refusal for a service the
TENANT does not sell would pass for the wrong reason, so the refused service
here is one the utility sells and the build does not carry (water on a
battery-and-solar build), and the case asserts the message key BY NAME and that
no unit was written.
"""

from __future__ import annotations

import pytest

from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from apps.metering import models as metering_models
from core import errors
from tests.test_cr162_new_connection_lifecycle import _create
from tests.test_portal_request_to_active import _ctx, cedar, clerk  # noqa: F401 — fixtures
from tests.test_us_cwp_helpers import *  # noqa: F401,F403
from tests.test_us_met_helpers import audit_rows, staff_actor  # noqa: F401 — fixture

pytestmark = pytest.mark.django_db


def test_add_unit_refuses_a_service_the_build_does_not_carry(cedar, clerk):
    """The ADDRESS offers water (a picked property can offer more than this
    build sells) and the build carries battery and solar. Before the fix the
    door wrote Unit 2 with water: the premises check passed and nothing asked
    the build."""
    built = _create(clerk, cedar, address="9 Annex Rd", premise_type="apartment_complex", labels=("Unit 1",))
    with _ctx(cedar):
        premises_id = work_tables.Connection.objects.get(pk=built["id"]).premises_id
        # Fixture step, said out loud: the address offers water too.
        metering_models.Premises.objects.filter(pk=premises_id).update(
            services_available=["battery", "solar", "water"]
        )
        with pytest.raises(errors.ApiError) as refused:
            w6.add_unit_to_build(clerk, built["id"], {"label": "Unit 2", "services": ["battery", "water"]})
        written = metering_models.Unit.objects.filter(label="Unit 2").exists()
    assert refused.value.message_key == "metering.build.unit_service_not_on_build"
    assert refused.value.params.get("service") == "water"
    assert written is False


def test_add_unit_takes_the_builds_own_services(cedar, clerk):
    built = _create(clerk, cedar, address="10 Annex Rd", premise_type="apartment_complex", labels=("Unit 1",))
    with _ctx(cedar):
        added = w6.add_unit_to_build(clerk, built["id"], {"label": "Unit 2", "services": ["solar"]})
    assert added["services"] == ["solar"]
