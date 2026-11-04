# ── Trace ──────────────────────────────────────────────
# Change:  CR-168-BRC10 round 8, lane FIX-8B — the server halves of:
#            DEF-WRK-9678 — the order's customer carries OUR customer number
#            DEF-WRK-9690 — Duplicate on a work order (beta #28)
#            DEF-WRK-9694 — a visit row a clerk adds raises the flow's template
#            DEF-WRK-9676 — the demo's build jobs carry their starter template
# Tests:   this file. Each case was run on the tip BEFORE the fix first and
#          failed; the failures are quoted in CR-168 §30.
# ───────────────────────────────────────────────────────
from __future__ import annotations

import pytest

from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from apps.work import api as work_api
from apps.work import dispatch
from apps.work import models as work_models
from apps.work import services as work_services

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana · marcus
from tests.test_us_met_helpers import make_premises
from tests.test_us_ten_helpers import api_call, tenant_ctx

pytestmark = pytest.mark.django_db


def _reference():
    for code in ("work_priorities", "work_order_types", "work_hold_reasons"):
        work_services.seed_reference_list(code, [], "test")


# ── DEF-WRK-9678 ───────────────────────────────────────────────────────────
def test_def_wrk_9678_the_order_names_the_holders_customer_number(brazos, marcus):
    from apps.customers import selectors as customers_selectors
    from apps.customers import services as customers_services
    from tests.test_us_cus_003_account_write import _create_payload, _unit_with_plan

    with tenant_ctx(brazos):
        _reference()
        unit = _unit_with_plan(marcus, brazos)
        account = customers_services.create_account(marcus, _create_payload(unit["id"]))
        expected = customers_selectors.customer_nos_for([account["id"]]).get(str(account["id"]))
        assert expected, "the fixture account has no customer number to show"
        from apps.metering import models as metering_models

        unit_row = metering_models.Unit.objects.get(pk=unit["id"])
        raised = w6.create_work_order(
            marcus,
            None,
            {
                "type": "Leak investigation",
                "service": "water",
                "premises_id": str(unit_row.premises_id),
                "account_id": account["id"],
            },
        )
        detail = dispatch.order_row(raised["id"])
        assert detail["customer"]["customer_no"] == expected


# ── DEF-WRK-9690 ───────────────────────────────────────────────────────────
def test_def_wrk_9690_duplicate_raises_the_same_job_again_unassigned(dana, brazos):
    with tenant_ctx(brazos):
        _reference()
        premises = make_premises(dana, address_line="12 Mill Pond Ln", services_available=["water"])
        first = w6.create_work_order(
            dana, None, {"type": "Leak investigation", "service": "water", "premises_id": premises["id"]}
        )

        response = api_call(
            work_api.work_order_duplicate,
            "post",
            f"/api/work-orders/{first['id']}/duplicate",
            user=dana.user,
            role="system_admin",
            tenant=brazos,
            data={},
            order_id=first["id"],
        )
        assert response.status_code == 201, response.data
        made = response.data
        assert made["order_no"] and made["order_no"] != first["order_no"]
        assert made["from_order_no"] == first["order_no"]
        copy = work_tables.WorkOrder.objects.get(pk=made["id"])
        original = work_tables.WorkOrder.objects.get(pk=first["id"])
        assert copy.premises_id == original.premises_id
        assert copy.type == original.type
        assert copy.service_id == original.service_id
        assert copy.source == "dispatcher"
        assert copy.assignee_technician_id is None and copy.assignee_crew_id is None
        assert copy.state == "planned" and copy.is_gate is False


def test_def_wrk_9690_duplicate_of_another_tenants_order_is_not_found(dana, brazos):
    import uuid

    with tenant_ctx(brazos):
        response = api_call(
            work_api.work_order_duplicate,
            "post",
            "/api/work-orders/x/duplicate",
            user=dana.user,
            role="system_admin",
            tenant=brazos,
            data={},
            order_id=str(uuid.uuid4()),
        )
        assert response.status_code == 404


# ── DEF-WRK-9694 ───────────────────────────────────────────────────────────
def test_def_wrk_9694_a_typed_visit_row_raises_the_flows_template(dana, brazos):
    """WALK-B W2: a row a clerk adds names a TYPE. The raised job must carry the
    flow's published template of that type, so its checklist reaches the phone."""
    from apps.customers import services as customers_services
    from tests.test_us_wrk_039_from_flows import MOVE_OUT_DAY, _occupant, _unit_with_plan

    with tenant_ctx(brazos):
        re_read = work_models.WorkOrderType.objects.create(tenant=brazos, code="RR-9694", name="Re-read (test)")
        # Two published templates of the same type: the move-out's own visit
        # (named for it) and another — the named one must win.
        for name in ("Opening read", "Final read"):
            header = w6.create_work_order_template(
                dana, {"name": name, "service": "electric", "sequence": 0, "type_id": str(re_read.id)}
            )
            w6.publish_work_order_template(dana, header["id"])
        final = work_tables.WorkOrderTemplate.objects.get(tenant=brazos, name="Final read")
        _premises, unit = _unit_with_plan(dana, brazos)
        account = _occupant(dana, unit)

        result = customers_services.move_out(
            dana,
            account["id"],
            {"moved_out_on": MOVE_OUT_DAY, "field_visit": {"orders": [{"type_id": str(re_read.id)}]}},
        )

        raised = result["work_orders"]
        assert len(raised) == 1
        order = work_tables.WorkOrder.objects.get(pk=raised[0]["id"])
        assert order.template_id == final.id, "the typed row raised no template — the phone has no checklist"
        assert order.type_ref_id == re_read.id
        assert order.source == "move_out"


def test_def_wrk_9694_a_type_no_template_carries_still_raises_by_type(dana, brazos):
    from apps.customers import services as customers_services
    from tests.test_us_wrk_039_from_flows import MOVE_OUT_DAY, _occupant, _unit_with_plan

    with tenant_ctx(brazos):
        pull = work_models.WorkOrderType.objects.create(tenant=brazos, code="PM-9694", name="Pull meter (test)")
        _premises, unit = _unit_with_plan(dana, brazos)
        account = _occupant(dana, unit)
        result = customers_services.move_out(
            dana,
            account["id"],
            {"moved_out_on": MOVE_OUT_DAY, "field_visit": {"orders": [{"type_id": str(pull.id)}]}},
        )
        order = work_tables.WorkOrder.objects.get(pk=result["work_orders"][0]["id"])
        assert order.template_id is None and order.type_ref_id == pull.id


# ── DEF-WRK-9676 ───────────────────────────────────────────────────────────
def test_def_wrk_9676_a_build_job_is_raised_from_its_starter_template(dana, brazos):
    """The demo's build jobs are named after the starter templates the same
    run publishes; each is raised FROM that template so it carries its skill
    and checklist — and linking it moves no gate."""
    from apps.metering import sample_data

    with tenant_ctx(brazos):
        header = w6.create_work_order_template(
            dana, {"name": "Meter set", "service": "electric", "sequence": 2, "is_gate": True}
        )
        w6.publish_work_order_template(dana, header["id"])
        assert sample_data._w6_template_of("electric", "Meter set") == {
            "template_id": str(header["id"]),
            "is_gate": False,
        }
        # A starter the tenant renamed or never published: raised by name, as before.
        assert sample_data._w6_template_of("electric", "Nothing by this name") == {}
