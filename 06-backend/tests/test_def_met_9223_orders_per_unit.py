# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-MET-9223 — every New Connection work order was raised on the
#           whole build; a per-unit job is now one order per unit.
# Found:    the New Connection end-to-end web walk, 2026-10-02 / 03 (all eight
#           builds: S2 raised 16 orders, 0 with a unit).
# Rules:    BR-WRK-006 (an order's anchors) · BR-MET-112 (both or neither)
# Front:    07-frontend/src/features/customers/newConnectOrdersPerUnit9223.test.ts
# ───────────────────────────────────────────────────────
"""The commit raises what `commitWorkOrdersOf` sends: one order per entry, each
on the unit (and service) the entry names.

⚠ **WHAT WOULD MAKE THIS PASS WRONGLY**: a count of orders would pass over two
orders on the same unit, so the case reads each order's unit back.
"""

import pytest

from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from tests.test_def_met_5441_the_commit_door import _wizard_plan
from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import brazos, dana, tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db


def test_a_per_unit_job_on_two_units_is_two_orders(dana, brazos):
    """DEF-MET-9223 — what `commitWorkOrdersOf` now sends for a per-unit
    *Meter set* on a 2-unit build: one entry per unit, and one order on each."""
    with tenant_ctx(brazos):
        header = w6.create_work_order_template(
            dana, {"name": "Meter set", "service": "electric", "sequence": 0, "scope": "per_unit"}
        )
        w6.publish_work_order_template(dana, header["id"])
        template = work_tables.WorkOrderTemplate.objects.get(pk=header["id"])
        entry = {"template_id": str(template.id), "template_version": template.version}
        plan = _wizard_plan(
            units=[{"label": "Apt 1"}, {"label": "Apt 2"}],
            unit_services=[
                {"unit_label": "Apt 1", "service": "electric"},
                {"unit_label": "Apt 2", "service": "electric"},
            ],
            work_orders=[
                {**entry, "unit_label": "Apt 1", "service": "electric"},
                {**entry, "unit_label": "Apt 2", "service": "electric"},
            ],
        )
        built = w6.commit_new_connect(dana, plan)
        orders = list(
            work_tables.WorkOrder.objects.filter(connection_id=built["id"]).select_related("unit", "service")
        )
    assert sorted((o.unit.label, o.service.code) for o in orders) == [
        ("Apt 1", "electric"),
        ("Apt 2", "electric"),
    ]
