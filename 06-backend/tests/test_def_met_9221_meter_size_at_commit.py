"""DEF-MET-9221 — a New Connection meter carries the size step 3 showed on its row.

Found by the New Connection end-to-end web walk (2026-10-02): every meter the walk's
eight builds fitted (16 on two buildings alone) had `size_class` NULL, while the
carts, modems, fire lines, batteries and panels beside them carried theirs — the
wizard sent meters as `{unit_label, service, asset_no}` and the commit fitted them
unsized. On a size-banded service `BR-RAT-108` picks the base charge by the meter's
size, so an unsized meter is a bill that cannot be priced (`DEF-AST-7660`).
"""

from __future__ import annotations

import pytest

from apps.assets import models as asset_models
from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from apps.tenancy import models as tenancy_models
from tests.test_new_connect_step7_messages import _address
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import make_plan, tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db


def _water_size(tenant):
    row = (
        tenancy_models.MeterSizeClass.objects.filter(tenant_id=tenant.id, service__code="water", active=True)
        .order_by("code")
        .first()
    )
    if row is None:
        pytest.skip("this tenant seeds no water size class")
    return row.code


def test_the_meter_takes_the_size_its_row_showed(dana, brazos):
    with tenant_ctx(brazos):
        size = _water_size(brazos)
        plan = make_plan(brazos)
        premises = {**_address(dana, "21 Meter Size Way"), "services_available": ["water"]}
        created = w6.create_connection(dana, {"premises": premises})
        w6.commit_connection(
            dana,
            created["id"],
            {
                "units": [{"label": "Unit 1"}, {"label": "Unit 2"}],
                "meters": [
                    {"unit_label": "Unit 1", "service": "water", "asset_no": None, "size_class": size},
                    {"unit_label": "Unit 2", "service": "water", "asset_no": None},
                ],
                "plan_assignments": [
                    {"unit_label": "Unit 1", "tariff_id": str(plan.id)},
                    {"unit_label": "Unit 2", "tariff_id": str(plan.id)},
                ],
            },
        )
        meters = {
            asset.service_point.unit.label: asset.size_class
            for asset in asset_models.Asset.objects.filter(
                tenant_id=brazos.id,
                service_point__unit__premises_id=work_tables.Connection.objects.get(pk=created["id"]).premises_id,
                type__code="meter",
            ).select_related("service_point__unit")
        }
    assert meters["Unit 1"] == size
    # A row that held no size sends none, and the meter stays unsized rather
    # than taking a size nobody chose.
    assert not meters["Unit 2"]
