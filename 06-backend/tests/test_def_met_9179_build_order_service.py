# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-MET-9179 (CR-163-BRC10 item 15) — the commit stamped each work
#           order with its TEMPLATE's own service and dropped the unit, so on
#           the PO's Battery/Solar build G Trade Tower (CON-26-0136) a
#           whole-build order read Water and another read Fire.
#           DEF-CUS-9177 (item 1) — the raise door wrote a picked `unit_id`
#           unread.
# Rules:    BR-WRK-006 (an order's anchors) · BR-MET-112 (both or neither) ·
#           HR-1 (another tenant's id is a 404)
# ───────────────────────────────────────────────────────
"""Which service and which unit a build's work order stands on.

⚠ **WHAT WOULD MAKE THESE PASS WRONGLY.** Asserting the manifest's COUNT of
orders — which is what every earlier commit test did, and why this defect lived
— would pass over a wrong service. So each case reads the ORDER ROWS back from
the table and asserts the service CODE and the unit on each.
"""

import pytest

from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from apps.metering import models as metering_models
from core import errors
from tests.test_def_met_5441_the_commit_door import _wizard_plan
from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import (
    brazos,
    dana,
    lonestar,
    make_premises,
    make_unit,
    tenant_ctx,
)  # noqa: F401

pytestmark = pytest.mark.django_db


def _published(actor, name, service):
    header = w6.create_work_order_template(actor, {"name": name, "service": service, "sequence": 0})
    w6.publish_work_order_template(actor, header["id"])
    return work_tables.WorkOrderTemplate.objects.get(pk=header["id"])


def _orders(connection_id):
    return {
        row.type: row
        for row in work_tables.WorkOrder.objects.filter(connection_id=connection_id).select_related(
            "service", "unit"
        )
    }


def test_a_template_service_the_build_does_not_carry_is_not_stamped(dana, brazos):
    """G Trade Tower in miniature: the build carries ELECTRIC only; one
    whole-build template is a WATER template and one is ELECTRIC.

    RED PROVED: on the tip before this fix the water order read
    `service.code == "water"` and this case failed on the first assertion.
    """
    with tenant_ctx(brazos):
        water = _published(dana, "Installation Template", "water")
        electric = _published(dana, "Service drop check", "electric")
        plan = _wizard_plan(
            unit_services=[{"unit_label": "Apt 1", "service": "electric"}],
            work_orders=[
                {"template_id": str(water.id), "template_version": water.version},
                {"template_id": str(electric.id), "template_version": electric.version},
            ],
        )
        built = w6.commit_new_connect(dana, plan)
        orders = _orders(built["id"])

    assert (
        orders["Installation Template"].service_id is None
    ), "a Water template on an electric-only build must not read Water"
    assert orders["Service drop check"].service.code == "electric"
    # Neither row named a unit, so both stand on the WHOLE build.
    assert orders["Installation Template"].unit_id is None
    assert orders["Service drop check"].unit_id is None


def test_a_row_naming_a_unit_stands_on_that_unit(dana, brazos):
    with tenant_ctx(brazos):
        electric = _published(dana, "Meter set at unit", "electric")
        plan = _wizard_plan(
            units=[{"label": "Apt 1"}, {"label": "Apt 2"}],
            unit_services=[
                {"unit_label": "Apt 1", "service": "electric"},
                {"unit_label": "Apt 2", "service": "electric"},
            ],
            work_orders=[
                {
                    "template_id": str(electric.id),
                    "template_version": electric.version,
                    "unit_label": "Apt 2",
                }
            ],
        )
        built = w6.commit_new_connect(dana, plan)
        order = _orders(built["id"])["Meter set at unit"]

    assert order.unit is not None and order.unit.label == "Apt 2"
    assert order.service.code == "electric"


def test_the_raise_door_refuses_a_unit_of_another_building(dana, brazos):
    """`DEF-CUS-9177` — the form's unit is checked against the build's premises."""
    with tenant_ctx(brazos):
        built = w6.commit_new_connect(dana, _wizard_plan())
        elsewhere = make_premises(
            dana, address_line="77 Other Street", services_available=["electric"]
        )
        stranger = make_unit(dana, elsewhere["id"], label="Unit Z")
        with pytest.raises(errors.ValidationError) as refused:
            w6.create_work_order(
                dana, built["id"], {"type": "Inspection", "unit_id": stranger["id"]}
            )
        assert refused.value.message_key == "work.order.unit_not_on_build"

        own = metering_models.Unit.objects.filter(
            premises_id=work_tables.Connection.objects.get(pk=built["id"]).premises_id
        ).first()
        made = w6.create_work_order(
            dana, built["id"], {"type": "Inspection", "unit_id": str(own.id)}
        )
        assert str(work_tables.WorkOrder.objects.get(pk=made["id"]).unit_id) == str(own.id)


def test_the_raise_door_answers_404_for_another_tenants_unit(dana, brazos, lonestar):
    from tests.test_us_met_helpers import staff_actor

    with tenant_ctx(lonestar):
        other = staff_actor(lonestar, "system_admin", "ana@lonestar.test")
        theirs = make_unit(
            other, make_premises(other, services_available=["water"])["id"], label="Theirs"
        )
    with tenant_ctx(brazos):
        built = w6.commit_new_connect(dana, _wizard_plan())
        with pytest.raises(errors.NotFoundError):
            w6.create_work_order(dana, built["id"], {"type": "Inspection", "unit_id": theirs["id"]})
