# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-WRK-9683 (CR-168-BRC10 round 8, lane FIX-8A) — a New Connect
#           build's *Meter set* job named no meter, so the office's Accept
#           answered `work.reading.no_meter_on_order` for ever and the build
#           could never finish its last job (CON-26-0129 / WO-0047).
# Rules:    BR-WRK-003 (a reading posts to the order's own meter) · BR-MET-110
#           (Accept posts the set read) · BR-WRK-006 · OQ-WRK-1723 (OPEN — which
#           meter when a job touches two: never guessed here)
# ───────────────────────────────────────────────────────
"""A build's per-meter job stands on the meter the build fits.

The commit creates the meter (in inventory, `installed=False`) and raises the
job in the same transaction, but never told the job which meter it was for —
`DEF-WRK-9620`'s fallback walks to an IN-SERVICE meter, and a build's meter is
not in service until this very job is accepted. So the commit now hands the
job the meter it just made for that unit and service, when there is exactly
ONE; two is `OQ-WRK-1723`'s question and is left alone.
"""

from __future__ import annotations

import pytest

from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from apps.work import checklist, evidence, templates_svc
from apps.work import models as work_models

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana
from tests.test_us_met_helpers import field_actor, make_premises, tenant_ctx
from tests.test_us_wrk_047_049_evidence import _satisfy_required_photos

pytestmark = pytest.mark.django_db


def _meter_set_template(actor):
    header = templates_svc.create_draft(
        actor, {"name": "Meter set", "service": "electric", "scope": "per_asset", "sequence": 0}
    )
    tid = header["id"]
    templates_svc.replace_collection(
        actor, tid, "tasks", [{"title": "Set the meter", "est_minutes": 15}]
    )
    templates_svc.replace_collection(
        actor,
        tid,
        "readings",
        [
            {
                "prompt": "Opening register",
                "unit_of_measure": "kWh",
                "min": 0,
                "max": 99999999,
                "required": True,
                "posts_as_meter_read": True,
            }
        ],
    )
    templates_svc.publish(actor, tid)
    return work_tables.WorkOrderTemplate.objects.get(pk=tid)


def _build(actor, template, meters):
    premises = make_premises(actor, address_line="412 Walkway Ln", services_available=["electric"])
    created = w6.create_connection(actor, {"premises_id": premises["id"]})
    w6.commit_connection(
        actor,
        created["id"],
        {
            "units": [{"label": "Unit 1"}],
            "meters": meters,
            "work_orders": [
                {"template_id": str(template.id), "template_version": template.version}
            ],
        },
    )
    return work_tables.WorkOrder.objects.get(connection_id=created["id"])


def test_9683_the_build_s_meter_set_job_names_the_meter_it_fits(brazos, dana):
    with tenant_ctx(brazos):
        template = _meter_set_template(dana)
        order = _build(
            dana, template, [{"unit_label": "Unit 1", "service": "electric", "asset_no": "E-90129"}]
        )
        assert order.asset_id is not None, "the build's meter-set job names no meter"
        assert order.asset.asset_no == "E-90129"


def test_9683_the_office_accepts_it_and_the_opening_read_lands_on_that_meter(brazos, dana):
    from apps.metering import models as metering_models

    with tenant_ctx(brazos):
        template = _meter_set_template(dana)
        order = _build(
            dana, template, [{"unit_label": "Unit 1", "service": "electric", "asset_no": "E-90130"}]
        )
        oid = order.id
        tech = field_actor(oid, dana)
        for row in work_models.WorkOrderTask.objects.filter(work_order_id=oid):
            checklist.tick_task(tech, oid, row.id)
        reading = work_models.WorkOrderReading.objects.get(work_order_id=oid)
        evidence.set_reading(tech, oid, reading.id, {"value": "12", "unit": "kWh"})
        _satisfy_required_photos(tech, oid)
        w6.submit_field_result(tech, oid, outcome="passed")
        w6.accept_field_result(dana, oid)

        order.refresh_from_db()
        reads = list(
            metering_models.MeterRead.objects.filter(asset__asset_no="E-90130").values_list(
                "current_value", flat=True
            )
        )
    assert order.accepted_at is not None
    assert any(str(value).startswith("12") for value in reads), reads


def test_9683_two_meters_of_the_service_are_not_guessed_between(brazos, dana):
    """`OQ-WRK-1723`'s shape — one job, two meters: no meter is picked."""
    with tenant_ctx(brazos):
        template = _meter_set_template(dana)
        order = _build(
            dana,
            template,
            [
                {"unit_label": "Unit 1", "service": "electric", "asset_no": "E-90131"},
                {"unit_label": "Unit 1", "service": "electric", "asset_no": "E-90132"},
            ],
        )
        assert order.asset_id is None
