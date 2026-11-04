# ── Trace ──────────────────────────────────────────────
# Change:   CR-168-BRC10 P3.42 — customers and metering, six screens read the
#           pre-selection (round 9, lane FIN-T). Builds on P3.34
#           (`from_flows._preselect`, `rules.preselection`, `rules.shape_by_rule`).
# Rules:    BR-WRK-055 (a screen moment never raises by itself; *No visit
#           needed* is a recorded choice) · BR-WRK-024 (a rule-raised order
#           stamps its rule) · BR-WRK-018 (the rule's priority sets the promise)
# ───────────────────────────────────────────────────────
"""What the six screens read, and what the save does with it.

* the three *Field visit* TABLES (move-in, move-out, transfer) read
  `GET /work/raise-options` → `preselected[moment]` — a typed row per rule;
* a row the rule put there carries `rule_id`, and the raise stamps it only
  when it is still an enabled rule on that moment of the row's job type;
* the reconnect row raises the rule's template for its service;
* the new connection's step 6 reads `preselected_by` on
  `/connections/proposed-work-orders`, and step 9 applies the rule's priority.
* the routed request has NO screen of its own any more (BR-WRK-055 amended
  2026-10-04, `DEF-WRK-9623`): it reaches field work through its child flow.
"""

from __future__ import annotations

import pytest

from apps.customers import reconnect_read
from apps.customers import services as customers_services
from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from apps.work import from_flows, rules
from apps.work import models as work_models
from apps.work import services as work_services

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_wrk_039_from_flows import (
    MOVE_OUT_DAY,
    _occupant,
    _published_template,
    _unit_with_plan,
)

pytestmark = pytest.mark.django_db


def _typed_template(actor, tenant, *, name, type_code, service="electric"):
    kind = work_models.WorkOrderType.objects.create(tenant=tenant, code=type_code, name=name)
    header = w6.create_work_order_template(
        actor, {"name": name, "service": service, "sequence": 0, "type_id": str(kind.id)}
    )
    w6.publish_work_order_template(actor, header["id"])
    return kind, header


def _rule(actor, *, name, moment, template_id, **extra):
    return rules.create_rule(
        actor,
        {"name": name, "triggers": [{"kind": moment, "params": {}}],
         "template_id": template_id, **extra},
    )


def test_the_field_visit_table_reads_the_rules_row_for_its_moment(dana, brazos):
    with tenant_ctx(brazos):
        work_services.seed_reference_list("work_priorities", [], "test")
        high = work_models.WorkPriority.objects.get(tenant_id=brazos.id, code="HIGH")
        crew = work_models.Crew.objects.create(tenant=brazos, name="Crew B — West", kind="crew")
        kind, final = _typed_template(dana, brazos, name="Final read", type_code="FR-P342")
        _rule(dana, name="Final read on move-out", moment="move_out", template_id=final["id"],
              priority_id=str(high.id), assign_to={"kind": "crew", "id": str(crew.id)})

        options = from_flows.raise_options()

    assert options["preselected"]["move_out"] == [
        {
            "rule": {"id": options["preselected"]["move_out"][0]["rule"]["id"],
                     "name": "Final read on move-out"},
            "type_id": str(kind.id),
            "priority_id": str(high.id),
            "holder": f"crew:{crew.id}",
        }
    ]
    # A rule on ONE moment puts nothing on the others.
    assert "move_in" not in options["preselected"]
    assert "transfer" not in options["preselected"]


def test_a_rule_turned_off_puts_nothing_in_the_table(dana, brazos):
    with tenant_ctx(brazos):
        _kind, final = _typed_template(dana, brazos, name="Final read", type_code="FR-P342B")
        _rule(dana, name="Off", moment="move_in", template_id=final["id"], enabled=False)
        assert from_flows.raise_options()["preselected"] == {}


def test_the_row_the_rule_added_is_raised_naming_the_rule(dana, brazos):
    with tenant_ctx(brazos):
        kind, final = _typed_template(dana, brazos, name="Final read", type_code="FR-P342C")
        rule = _rule(dana, name="Final read on move-out", moment="move_out",
                     template_id=final["id"])
        _premises, unit = _unit_with_plan(dana, brazos)
        account = _occupant(dana, unit)
        result = customers_services.move_out(
            dana, account["id"],
            {"moved_out_on": MOVE_OUT_DAY,
             "field_visit": {"orders": [{"type_id": str(kind.id), "rule_id": rule["id"]}]}},
        )
        order = work_tables.WorkOrder.objects.get(pk=result["work_orders"][0]["id"])
        assert str(order.rule_id) == str(rule["id"])
        assert str(order.template_id) == str(final["id"])


def test_a_rule_id_that_does_not_fit_the_row_is_not_stamped_and_the_job_still_stands(dana, brazos):
    """`BR-WRK-055` — a rule turned off (or of another type) between the screen
    opening and the save must not lose the visit."""
    with tenant_ctx(brazos):
        kind, final = _typed_template(dana, brazos, name="Final read", type_code="FR-P342D")
        other, _pull = _typed_template(dana, brazos, name="Pull meter", type_code="PM-P342D")
        rule = _rule(dana, name="Final read on move-out", moment="move_out",
                     template_id=final["id"])
        _premises, unit = _unit_with_plan(dana, brazos)
        account = _occupant(dana, unit)
        result = customers_services.move_out(
            dana, account["id"],
            {"moved_out_on": MOVE_OUT_DAY,
             "field_visit": {"orders": [{"type_id": str(other.id), "rule_id": rule["id"]}]}},
        )
        order = work_tables.WorkOrder.objects.get(pk=result["work_orders"][0]["id"])
        assert order.rule_id is None


def test_the_reconnect_row_raises_the_rules_template_for_its_service(dana, brazos, monkeypatch):
    first = {"template_id": "t-first", "service": {"code": "water", "name": "Water"}}
    ruled = {"template_id": "t-ruled", "service": {"code": "water", "name": "Water"},
             "preselected_by": {"id": "r1", "name": "Reconnect water"}}
    monkeypatch.setattr(
        reconnect_read.seams, "propose_flow_work_orders",
        lambda kind, flow_id: {"proposed": [first, ruled]},
    )
    assert reconnect_read._reconnect_template_for("acct", "water") == ["t-ruled"]
    monkeypatch.setattr(
        reconnect_read.seams, "propose_flow_work_orders",
        lambda kind, flow_id: {"proposed": [first]},
    )
    assert reconnect_read._reconnect_template_for("acct", "water") == ["t-first"]


def test_step_6_reads_the_new_connection_rule_and_step_9_takes_its_priority(dana, brazos):
    from apps.work import api as work_api
    from tests.test_us_ten_helpers import api_call

    with tenant_ctx(brazos):
        work_services.seed_reference_list("work_priorities", [], "test")
        urgent = work_models.WorkPriority.objects.get(tenant_id=brazos.id, code="URGENT")
        survey = _published_template(dana, name="Site survey", service="electric")
        _rule(dana, name="Survey every build", moment="new_connect",
              template_id=survey["id"], priority_id=str(urgent.id))
    answer = api_call(
        work_api.proposed_work_orders, "get",
        f"/api/{brazos.subdomain}/connections/proposed-work-orders",
        user=dana.user, role="system_admin", tenant=brazos, query={"services": "electric"},
    )
    assert answer.status_code == 200, answer.data
    ticked = [row for row in answer.data["proposed"] if row.get("preselected_by")]
    assert [row["template_id"] for row in ticked] == [str(survey["id"])]
    assert ticked[0]["preselected_by"]["name"] == "Survey every build"
    # A water-only build is not offered the electric rule's job.
    water = api_call(
        work_api.proposed_work_orders, "get",
        f"/api/{brazos.subdomain}/connections/proposed-work-orders",
        user=dana.user, role="system_admin", tenant=brazos, query={"services": "water"},
    )
    assert not [row for row in water.data["proposed"] if row.get("preselected_by")]

    with tenant_ctx(brazos):
        premises = make_premises(dana, address_line="9 Survey Ln")  # noqa: F405
        order = w6.create_work_order(
            dana, None,
            {"premises_id": premises["id"], "type": "Site survey",
             "template_id": str(survey["id"]), "source": work_tables.SOURCE_NEW_CONNECT},
        )
        w6._shape_retry_by_rule(dana, order["id"], str(survey["id"]), work_tables.SOURCE_NEW_CONNECT)
        row = work_tables.WorkOrder.objects.get(pk=order["id"])
        assert str(row.priority_id) == str(urgent.id)
        assert row.rule_id is not None and row.due_at is not None
