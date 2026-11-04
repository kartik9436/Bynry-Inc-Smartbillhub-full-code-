# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-WRK-9620 — a per-meter job raised from a move-out, move-in,
#           transfer or reconnect carried no meter, so the office could never
#           accept it (`work.reading.no_meter_on_order`, WO-0046..WO-0049).
# Change:   CR-168-BRC10 lane FIELD-FIX
# Rules:    BR-WRK-006 (an order stands on an anchor) · BR-WRK-003 (a reading
#           posts to the order's own meter) · BR-WRK-055 · BR-MET-110 ·
#           OQ-WRK-1723 (OPEN — which meter, when a job touches two)
# ───────────────────────────────────────────────────────
"""A *per meter* job raised from a customer flow stands on the meter.

The flow's anchor is the ACCOUNT, and that stays. What was missing is the one
fact a *per asset* template needs: WHICH meter. The account's service point for
the template's service has it, walked through the seams (`BR-WRK-002`).

⚠ **ONLY WHERE THE ANSWER IS ONE METER.** Two in-service meters on the
service is a question, not a derivation (the shape `OQ-WRK-1723` asks one level
down), so the job is raised exactly as before — on the account, with no meter —
and Accept goes on refusing it in words. Nothing here guesses.
"""

from __future__ import annotations

import pytest

from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from apps.work import checklist, templates_svc
from apps.work import models as work_models

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana
from tests.test_us_met_helpers import field_actor, make_asset, tenant_ctx
from tests.test_us_wrk_039_from_flows import _move_out, _occupant, _unit_with_plan
from tests.test_us_wrk_047_049_evidence import _satisfy_required_photos

pytestmark = pytest.mark.django_db

ONE_POSTING_READING = [
    {
        "prompt": "Final read",
        "unit_of_measure": "kWh",
        "min": 0,
        "max": 99999,
        "required": True,
        "posts_as_meter_read": True,
    }
]
PHOTO_TASKS = [
    {"title": "Read the dial", "est_minutes": 4, "photo_required": True},
    {"title": "Seal and tidy", "est_minutes": 3},
]


def _per_meter_template(actor, *, scope="per_asset", name="Final read — residential"):
    header = templates_svc.create_draft(
        actor, {"name": name, "service": "electric", "scope": scope, "sequence": 0}
    )
    tid = header["id"]
    templates_svc.replace_collection(actor, tid, "tasks", PHOTO_TASKS)
    templates_svc.replace_collection(actor, tid, "readings", ONE_POSTING_READING)
    templates_svc.publish(actor, tid)
    return tid


def _fit_meter(actor, unit, asset_no):
    return make_asset(
        actor,
        asset_no=asset_no,
        service="electric",
        unit="kWh",
        unit_id=str(unit["id"]),
        install_date="2024-01-15",
    )


def test_9620_a_move_out_per_meter_job_stands_on_the_units_meter(brazos, dana):
    with tenant_ctx(brazos):
        _premises, unit = _unit_with_plan(dana, brazos)
        meter = _fit_meter(dana, unit, "E-30461")
        account = _occupant(dana, unit)
        tid = _per_meter_template(dana)

        result = _move_out(dana, account["id"], template_ids=[tid])
        order = work_tables.WorkOrder.objects.get(pk=result["work_orders"][0]["id"])

    # The anchor it already had stays, and the meter is added beside it.
    assert str(order.account_id) == str(account["id"])
    assert str(order.asset_id) == str(meter["id"]), "the per-meter job carries no meter"
    assert order.source == "move_out"


def test_9620_the_office_can_accept_it_and_the_reading_lands_on_that_meter(brazos, dana):
    """End to end: raised by the move-out, closed by the field, accepted by
    Dana — and the final read is the meter's."""
    from apps.metering import models as metering_models

    with tenant_ctx(brazos):
        _premises, unit = _unit_with_plan(dana, brazos)
        _fit_meter(dana, unit, "E-30462")
        account = _occupant(dana, unit)
        tid = _per_meter_template(dana)
        oid = _move_out(dana, account["id"], template_ids=[tid])["work_orders"][0]["id"]

        tech = field_actor(oid, dana)
        for row in work_models.WorkOrderTask.objects.filter(work_order_id=oid):
            checklist.tick_task(tech, oid, row.id)
        reading = work_models.WorkOrderReading.objects.get(work_order_id=oid)
        from apps.work import evidence

        evidence.set_reading(tech, oid, reading.id, {"value": "48221", "unit": "kWh"})
        _satisfy_required_photos(tech, oid)
        w6.submit_field_result(tech, oid, outcome="passed")
        w6.accept_field_result(dana, oid)

        order = work_tables.WorkOrder.objects.get(pk=oid)
        reads = list(
            metering_models.MeterRead.objects.filter(asset__asset_no="E-30462").values_list(
                "current_value", flat=True
            )
        )

    assert order.accepted_by_id is not None
    assert any(str(v).startswith("48221") for v in reads), reads


def test_9620_two_meters_on_the_service_are_not_guessed_between(brazos, dana):
    """`OQ-WRK-1723`'s shape — which meter is a question. Raised as before, on
    the account alone; no meter is picked."""
    with tenant_ctx(brazos):
        _premises, unit = _unit_with_plan(dana, brazos)
        _fit_meter(dana, unit, "E-30463")
        _fit_meter(dana, unit, "E-30464")
        account = _occupant(dana, unit)
        tid = _per_meter_template(dana)

        result = _move_out(dana, account["id"], template_ids=[tid])
        order = work_tables.WorkOrder.objects.get(pk=result["work_orders"][0]["id"])

    assert order.asset_id is None
    assert str(order.account_id) == str(account["id"])


def test_9620_a_per_premise_job_is_left_on_the_account(brazos, dana):
    with tenant_ctx(brazos):
        _premises, unit = _unit_with_plan(dana, brazos)
        _fit_meter(dana, unit, "E-30465")
        account = _occupant(dana, unit)
        tid = _per_meter_template(dana, scope="per_premise", name="Site check")

        result = _move_out(dana, account["id"], template_ids=[tid])
        order = work_tables.WorkOrder.objects.get(pk=result["work_orders"][0]["id"])

    assert order.asset_id is None
