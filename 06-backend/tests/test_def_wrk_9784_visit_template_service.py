# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-WRK-9784 — a move-in's Field visit offered visit templates of
#           ANOTHER service, and Complete then raised NO work order at all (M6,
#           Foundry Works Fabrication Inc.: water's *Opening read* picked for
#           electric meter E-M6, water's *Reconnect visit* for gas meter G-M6).
# Rules:    BR-WRK-008 (a template is a service's job) · BR-WRK-055 (the flow
#           never waits on a RAISE) · BR-WRK-006 (*For* names a meter on the
#           flow's own unit) · CLAUDE.md hard-won law 14 (run on PostgreSQL:
#           `--ds=config.settings.pgtest`)
# Tests:    this file
# ───────────────────────────────────────────────────────
"""**A visit row raises a template of its meter's service, or is refused by name
before the move-in commits — never a move-in that completes and books nothing.**

⚠ **WHAT WOULD MAKE THESE PASS WRONGLY** (law 7, habit 2):

  * **A refusal for another reason.** Each refusal case asserts the named
    `message_key` AND that no account was written for the unit.
  * **A typed row that raises because the offer held nothing else.** The typed
    case publishes a WATER template of the row's type and puts the row on an
    ELECTRIC meter, so the old `_default_template` had a wrong answer to pick.
  * **A log line asserted by its absence of failure.** The log case asserts the
    record's level, logger and the refusal it names.
  * **A seed test that passes on a water-only tenant.** Brazos sells electric
    AND water; the case asserts BOTH services hold every visit template.
"""

from __future__ import annotations

import logging

import pytest

from apps.customers import models as customers_models
from apps.customers import services as customers_services
from apps.work import connection_models as work_tables
from apps.work import from_flows, templates_svc
from apps.work import models as work_models
from core import errors

from tests import identity_fixtures
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana
from tests.test_us_met_helpers import make_asset, tenant_ctx
from tests.test_us_wrk_039_from_flows import _occupant, _unit_with_plan

pytestmark = pytest.mark.django_db

NAME = "Foundry Works Fabrication Inc."


def _type(tenant, code="RR-9784", name="Re-read (9784)"):
    return work_models.WorkOrderType.objects.create(tenant=tenant, code=code, name=name)


def _template(actor, *, name, service, type_id):
    header = templates_svc.create_draft(
        actor,
        {"name": name, "service": service, "scope": "per_asset", "sequence": 0, "type_id": str(type_id)},
    )
    templates_svc.replace_collection(actor, header["id"], "tasks", [{"title": "Read the meter"}])
    templates_svc.publish(actor, header["id"])
    return header["id"]


def _unit_with_two_meters(actor, tenant):
    """M6's shape, cut to two services: an electric AND a water meter on one unit."""
    _premises, unit = _unit_with_plan(actor, tenant, label="Bay 3", address_line="5 Foundry Way")
    make_asset(actor, asset_no="E-9784", unit_id=str(unit["id"]), install_date="2024-01-15", status="active")
    make_asset(
        actor,
        asset_no="W-9784",
        service="water",
        unit="kgal",
        unit_id=str(unit["id"]),
        install_date="2024-01-15",
        status="active",
    )
    return unit


def _payload(**overrides):
    body = {
        "account_type": "residential",
        "opened_at": "2026-08-01",
        "contact": {"full_name": NAME},
        "customer": identity_fixtures.customer_block(NAME, account_type="residential"),
    }
    body.update(overrides)
    return body


# ═══════════════════════════════════════════════════════════════════════════
# (a) a wrong pick is refused at the step — by name, before anything is written
# ═══════════════════════════════════════════════════════════════════════════
def test_a_water_template_for_an_electric_meter_is_refused_before_the_move_in_commits(brazos, dana):
    with tenant_ctx(brazos):
        kind = _type(brazos)
        water = _template(dana, name="Opening read", service="water", type_id=kind.id)
        unit = _unit_with_two_meters(dana, brazos)
        with pytest.raises(errors.ValidationError) as refused:
            customers_services.move_in_to_unit(
                dana,
                unit["id"],
                _payload(
                    field_visit={
                        "orders": [{"type_id": str(kind.id), "template_id": water, "asset_no": "E-9784"}]
                    }
                ),
            )
        assert refused.value.message_key == "work.order.template_wrong_service"
        assert refused.value.params["field"] == "field_visit.orders[0].template_id"
        assert customers_models.Account.objects.filter(unit_id=unit["id"]).count() == 0


# ═══════════════════════════════════════════════════════════════════════════
# (b) a valid pick raises the work order at Complete
# ═══════════════════════════════════════════════════════════════════════════
def test_an_electric_template_for_the_electric_meter_is_raised_at_complete(brazos, dana):
    with tenant_ctx(brazos):
        kind = _type(brazos)
        _template(dana, name="Opening read", service="water", type_id=kind.id)
        electric = _template(dana, name="Opening read", service="electric", type_id=kind.id)
        unit = _unit_with_two_meters(dana, brazos)
        result = customers_services.move_in_to_unit(
            dana,
            unit["id"],
            _payload(
                field_visit={
                    "orders": [{"type_id": str(kind.id), "template_id": electric, "asset_no": "E-9784"}]
                }
            ),
        )
        assert [w["code"] for w in result.get("warnings", []) if w["code"].startswith("work_")] == []
        assert len(result["work_orders"]) == 1
        order = work_tables.WorkOrder.objects.get(pk=result["work_orders"][0]["id"])
        assert str(order.template_id) == str(electric)
        assert order.asset.asset_no == "E-9784"
        assert order.source == "move_in" and order.source_ref == result["move_no"]


def test_a_typed_row_on_an_electric_meter_does_not_borrow_waters_template(brazos, dana):
    """The row names a TYPE and a meter. Water holds the only template of that
    type, so the old default picked it, Work refused it and nothing was raised."""
    with tenant_ctx(brazos):
        kind = _type(brazos)
        _template(dana, name="Opening read", service="water", type_id=kind.id)
        unit = _unit_with_two_meters(dana, brazos)
        result = customers_services.move_in_to_unit(
            dana,
            unit["id"],
            _payload(field_visit={"orders": [{"type_id": str(kind.id), "asset_no": "E-9784"}]}),
        )
        assert len(result["work_orders"]) == 1, result.get("warnings")
        order = work_tables.WorkOrder.objects.get(pk=result["work_orders"][0]["id"])
        assert order.template_id is None and order.type_ref_id == kind.id
        assert order.asset.asset_no == "E-9784"


def test_a_typed_row_takes_its_meters_own_service_template(brazos, dana):
    with tenant_ctx(brazos):
        kind = _type(brazos)
        _template(dana, name="Opening read", service="water", type_id=kind.id)
        electric = _template(dana, name="Opening read", service="electric", type_id=kind.id)
        unit = _unit_with_two_meters(dana, brazos)
        account = _occupant(dana, unit)
        answer = from_flows.raise_orders_for(
            "move_in", account["id"], [{"type_id": str(kind.id), "asset_no": "E-9784"}], dana
        )
        order = work_tables.WorkOrder.objects.get(pk=answer["raised"][0]["id"])
    assert str(order.template_id) == str(electric)


# ═══════════════════════════════════════════════════════════════════════════
# a raise that fails is never silent — warned to the clerk AND logged
# ═══════════════════════════════════════════════════════════════════════════
def test_a_raise_that_fails_is_logged_with_its_refusal(brazos, dana, caplog, monkeypatch):
    def refuse(*_args, **_kwargs):
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP, message_key="work.order.template_wrong_service"
        )

    monkeypatch.setattr(from_flows, "raise_orders_for", refuse)
    with tenant_ctx(brazos), caplog.at_level(logging.WARNING, logger="smartbillhub.customers"):
        answer = customers_services._raise_flow_work(
            dana, flow_kind="move_in", flow_id="x", template_ids=[], orders=[{"type_id": "t"}]
        )
    assert answer["work_orders"] == []
    assert [w["code"] for w in answer["warnings"]] == ["work_orders_not_raised"]
    logged = [r for r in caplog.records if r.name == "smartbillhub.customers"]
    assert logged and logged[0].levelno == logging.WARNING
    assert "work.order.template_wrong_service" in logged[0].getMessage()
    assert "flow=move_in" in logged[0].getMessage()


# ═══════════════════════════════════════════════════════════════════════════
# the sample set: every metered service gets its visit templates
# ═══════════════════════════════════════════════════════════════════════════
def test_every_metered_service_gets_the_flow_visit_templates(brazos, dana):
    from apps.metering import sample_data

    with tenant_ctx(brazos):
        services = [m.code for m in sample_data.estate().metered]
        assert {"electric", "water"} <= set(services), services
        sample_data._seed_flow_visit_templates(dana)
        sample_data._seed_flow_visit_templates(dana)  # idempotent
        for code in services:
            names = set(
                work_tables.WorkOrderTemplate.objects.filter(
                    tenant=brazos, service__code=code, version__gte=1, active=True
                ).values_list("name", flat=True)
            )
            for name, _type_code in sample_data.FLOW_VISIT_TEMPLATES:
                assert name in names, f"{code} has no '{name}'"
        assert (
            work_tables.WorkOrderTemplate.objects.filter(tenant=brazos, name="Opening read").count()
            == len(services)
        )
