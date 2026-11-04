# ── Trace ──────────────────────────────────────────────
# Story:    CR-168-BRC10 round 5, lane SRV-4 — P3.34 (six screen moments tick the
#           rule's job), P3.35 (a rule shapes the failed-job retry), P3.38 (one
#           subject, one open job per template) and three defects from lane
#           FLOW-FIX's walk: DEF-WRK-9645, DEF-WRK-9647, DEF-WRK-9623.
# Rules:    BR-WRK-055 · BR-WRK-054 · BR-WRK-024 · BR-WRK-008
# ───────────────────────────────────────────────────────
"""The screen moments and the retry, with a rule beside them."""

from __future__ import annotations

import pytest

from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from apps.work import from_flows, rules
from apps.work import models as work_models
from apps.work import services as work_services

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana
from tests.test_us_met_helpers import make_premises, tenant_ctx
from tests.test_us_wrk_039_from_flows import (
    _move_out,
    _occupant,
    _published_template,
    _unit_with_plan,
)


# ── DEF-WRK-9645 · a move-in after a move-out is offered its visit ─────────
@pytest.mark.django_db
def test_9645_a_move_in_after_the_move_out_is_still_offered_field_work(dana, brazos):
    """RED on the tip: ``assert 0 >= 1`` — the offer was the OUTGOING account's
    services in force, and a move-out ends them before the move-in asks."""
    with tenant_ctx(brazos):
        _premises, unit = _unit_with_plan(dana, brazos)
        account = _occupant(dana, unit)
        _published_template(dana, name="Opening read")
        _move_out(dana, account["id"])
        offer = from_flows.propose("move_in", account["id"])
        assert offer["count"] >= 1, offer
        assert "electric" in offer["services"]


# ── DEF-WRK-9647 · a failed job's follow-up carries its service ────────────
@pytest.mark.django_db
def test_9647_the_follow_up_of_a_failed_water_job_is_a_water_job(dana, brazos):
    """RED on the tip: ``assert None == 'water'`` — the chain passed
    `service_id`, a key `create_work_order` does not read."""
    with tenant_ctx(brazos):
        premises = make_premises(dana, address_line="12 Retry Rd")
        failed = w6.create_work_order(
            dana, None, {"type": "Meter set", "service": "water", "premises_id": premises["id"]}
        )
        order = work_tables.WorkOrder.objects.get(pk=failed["id"])
        order.outcome = work_tables.OUTCOME_FAILED
        order.save(update_fields=["outcome"])
        chain = w6._failed_outcome_chain(dana, order)
        follow = work_tables.WorkOrder.objects.select_related("service").get(pk=chain["follow_up"]["id"])
        assert follow.service is not None
        assert follow.service.code == "water"


# ── P3.34 · a rule on a screen moment pre-selects its job ──────────────────
@pytest.mark.django_db
def test_p334_a_move_out_rule_ticks_its_job_on_the_screen_with_the_rules_name(dana, brazos):
    with tenant_ctx(brazos):
        _premises, unit = _unit_with_plan(dana, brazos)
        account = _occupant(dana, unit)
        final = _published_template(dana, name="Final read")
        _published_template(dana, name="Changeover read")
        rules.create_rule(
            dana,
            {"name": "Final read on move-out",
             "triggers": [{"kind": "move_out", "params": {}}],
             "template_id": final["id"]},
        )
        offer = from_flows.propose("move_out", account["id"])
        ticked = [row for row in offer["proposed"] if row.get("preselected_by")]
        assert [row["template_id"] for row in ticked] == [str(final["id"])]
        assert ticked[0]["preselected_by"]["name"] == "Final read on move-out"
        # Nothing was raised — the clerk may untick (`BR-WRK-055`).
        assert work_tables.WorkOrder.objects.count() == 0


@pytest.mark.django_db
def test_p334_the_ticked_job_is_raised_with_the_rules_priority(dana, brazos):
    with tenant_ctx(brazos):
        work_services.seed_reference_list("work_priorities", [], "test")
        high = work_models.WorkPriority.objects.get(tenant_id=brazos.id, code="HIGH")
        _premises, unit = _unit_with_plan(dana, brazos)
        account = _occupant(dana, unit)
        final = _published_template(dana, name="Final read")
        rules.create_rule(
            dana,
            {"name": "Final read on move-out",
             "triggers": [{"kind": "move_out", "params": {}}],
             "template_id": final["id"], "priority_id": str(high.id)},
        )
        result = _move_out(dana, account["id"], template_ids=[final["id"]])
        order = work_tables.WorkOrder.objects.get(pk=result["work_orders"][0]["id"])
        assert order.source == "move_out"
        assert str(order.priority_id) == str(high.id)
        assert order.due_at is not None


@pytest.mark.django_db
def test_p334_a_rule_off_ticks_nothing(dana, brazos):
    with tenant_ctx(brazos):
        _premises, unit = _unit_with_plan(dana, brazos)
        account = _occupant(dana, unit)
        final = _published_template(dana, name="Final read")
        rules.create_rule(
            dana,
            {"name": "Final read on move-out",
             "triggers": [{"kind": "move_out", "params": {}}],
             "template_id": final["id"], "enabled": False},
        )
        offer = from_flows.propose("move_out", account["id"])
        assert not [row for row in offer["proposed"] if row.get("preselected_by")]


# ── P3.38 · a screen does not raise a template already open on the subject ─
@pytest.mark.django_db
def test_p338_a_screen_does_not_raise_a_second_open_job_of_the_same_template(dana, brazos):
    with tenant_ctx(brazos):
        _premises, unit = _unit_with_plan(dana, brazos)
        account = _occupant(dana, unit)
        visit = _published_template(dana, name="Reconnect visit")
        first = from_flows.raise_for("reconnect", account["id"], [visit["id"]], dana)
        assert first["count"] == 1
        again = from_flows.raise_for("reconnect", account["id"], [visit["id"]], dana)
        assert again["count"] == 0
        assert again["already_open"] == [
            {"template_id": str(visit["id"]), "order_no": first["raised"][0]["order_no"]}
        ]


# ── P3.35 · a rule shapes the failed-job retry, never a second job ─────────
@pytest.mark.django_db
def test_p335_a_rule_on_the_failed_template_shapes_the_retry(dana, brazos):
    with tenant_ctx(brazos):
        work_services.seed_reference_list("work_priorities", [], "test")
        urgent = work_models.WorkPriority.objects.get(tenant_id=brazos.id, code="URGENT")
        exchange = _published_template(dana, name="Meter exchange", service="water")
        rules.create_rule(
            dana,
            {"name": "Retry exchanges fast",
             "triggers": [{"kind": "failed_outcome", "params": {}}],
             "template_id": exchange["id"], "priority_id": str(urgent.id)},
        )
        premises = make_premises(dana, address_line="14 Retry Rd")
        failed = w6.create_work_order(
            dana, None,
            {"type": "Meter exchange", "service": "water", "premises_id": premises["id"],
             "template_id": exchange["id"]},
        )
        order = work_tables.WorkOrder.objects.get(pk=failed["id"])
        order.outcome = work_tables.OUTCOME_FAILED
        order.save(update_fields=["outcome"])
        chain = w6._failed_outcome_chain(dana, order)
        follow = work_tables.WorkOrder.objects.get(pk=chain["follow_up"]["id"])
        assert str(follow.priority_id) == str(urgent.id)
        assert follow.rule_id is not None
        # Never a second job: the chain raised ONE follow-up.
        assert work_tables.WorkOrder.objects.filter(follows_order_id=order.id).count() == 1
