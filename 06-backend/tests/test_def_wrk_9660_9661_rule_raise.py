"""A rule's raise says WHERE, and its preview counts what the sweep will raise.

`DEF-WRK-9660` — a job a rule raised on an installed backflow preventer carried
`asset_id` only: no premises, no unit, so the rule's Jobs tab, the order list
and the map read *Premise —*. An installed device that measures nothing has no
service point (`BR-AST-009`); it stands on its unit through its CURRENT
ASSIGNMENT, and `_asset_walk` read only the service point. Hard rule 8: the
premises is WALKED, never stored on the asset — so the walk now takes the
assignment's unit when there is no point.

`DEF-WRK-9661` — a rule's Review said *Tonight it raises 4 jobs* where the
sweep raised 3: one subject was refused by the raise (an asset whose type the
template does not apply to) and the preview never asked. The preview, the
rule's Overview and the sweep now share ONE precondition check, so the number
promised is the number raised, and the refused are counted apart.

Runs on SQLite and on PostgreSQL (`config.settings.pgtest`) — the sweep
catches a refusal inside a SAVEPOINT, which is law 14's territory.
"""

from __future__ import annotations

import datetime as dt

import pytest

from apps.assets import models as assets_models
from apps.assets import services as asset_services
from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from apps.work import models as work_models
from apps.work import rules

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana
from tests.test_us_met_helpers import make_asset, make_premises, make_unit, tenant_ctx

pytestmark = pytest.mark.django_db

YESTERDAY = dt.date.today() - dt.timedelta(days=1)


def _template(actor, *, name, service="water"):
    header = w6.create_work_order_template(actor, {"name": name, "service": service, "sequence": 0})
    w6.publish_work_order_template(actor, header["id"])
    return header


def _installed_backflow(actor, asset_no="BF-9660"):
    premises = make_premises(actor, services_available=["electric", "water"])
    unit = make_unit(actor, premises["id"], label="Unit 9660")
    asset = asset_services.create_asset(
        actor,
        {"type": "backflow", "asset_no": asset_no, "unit_id": unit["id"], "install_date": "2024-01-01"},
    )
    assets_models.Asset.objects.filter(pk=asset["id"]).update(certification_due=YESTERDAY)
    return premises, unit, asset


def _rule(actor, template_id, name):
    return rules.create_rule(
        actor,
        {
            "name": name,
            "template_id": template_id,
            "triggers": [{"kind": "asset_age_rule", "params": {}}],
        },
    )


def test_9660_a_rule_raised_job_on_an_installed_device_names_its_premises_and_unit(brazos, dana):
    with tenant_ctx(brazos):
        premises, unit, asset = _installed_backflow(dana)
        assert assets_models.Asset.objects.get(pk=asset["id"]).service_point_id is None
        template = _template(dana, name="Backflow test")
        rule = _rule(dana, template["id"], "Backflow test due")

        report = rules.sweep(dana, rule_ids=[rule["id"]])["rules"][0]
        assert report["raised"] == 1, report

        order = work_tables.WorkOrder.objects.get(rule_id=rule["id"])
        assert str(order.asset_id) == str(asset["id"])
        assert str(order.premises_id) == str(premises["id"])
        assert str(order.unit_id) == str(unit["id"])


def test_9660_a_device_in_the_warehouse_still_stands_nowhere(brazos, dana):
    """The walk follows the device; it never invents a place. A meter in
    inventory has no point and no assignment, so a job on it names no premises.

    ⚠ AMENDED 2026-10-05 (`CR-168-BRC10` §30, lane BOARDS). This case asserted
    that the certification rule RAISED a job on the warehouse meter. The PO
    then answered (3), verbatim: *"(b) Only raise jobs for meters that are
    installed."* So the rule no longer finds it, and the walk is asserted on a
    job a clerk raises by hand on the same meter — the walk itself is unchanged.
    """
    with tenant_ctx(brazos):
        template = _template(dana, name="Bench test", service="electric")
        spare = make_asset(dana, asset_no="M-9660")
        assets_models.Asset.objects.filter(pk=spare["id"]).update(certification_due=YESTERDAY)
        rule = _rule(dana, template["id"], "Bench test due")
        assert rules.sweep(dana, rule_ids=[rule["id"]])["rules"][0]["raised"] == 0
        by_hand = w6.create_work_order(
            dana, None, {"type": "Bench test", "asset_id": spare["id"], "template_id": template["id"]}
        )
        order = work_tables.WorkOrder.objects.get(pk=by_hand["id"])
        assert order.premises_id is None and order.unit_id is None


def test_9661_the_preview_the_overview_and_the_sweep_agree(brazos, dana):
    with tenant_ctx(brazos):
        _premises, _unit, backflow = _installed_backflow(dana)
        spare = make_asset(dana, asset_no="M-9661")  # a METER, which this template does not take
        assets_models.Asset.objects.filter(pk=spare["id"]).update(certification_due=YESTERDAY)
        # INSTALLED on the backflow's unit (`CR-168-BRC10` §30 — a warehouse
        # meter is no longer a subject at all, so the refusal case needs one
        # in the ground to still be the type refusal this test is about).
        assets_models.AssetAssignment.objects.create(
            tenant_id=brazos.id, asset_id=spare["id"], unit_id=_unit["id"], from_date=dt.date(2024, 1, 1)
        )
        template = _template(dana, name="Backflow test")
        work_models.WorkOrderTemplateAssetType.objects.create(
            tenant_id=brazos.id,
            template_id=template["id"],
            asset_type_id=assets_models.Asset.objects.get(pk=backflow["id"]).type_id,
        )

        preview = rules.preview(
            {"template_id": template["id"], "triggers": [{"kind": "asset_age_rule", "params": {}}]}
        )
        assert preview["subjects"] == 2
        assert preview["would_raise"] == 1
        assert preview["cannot_raise"] == 1
        assert preview["cannot_raise_reasons"] == {"work.order.asset_type_not_on_template": 1}

        rule = _rule(dana, template["id"], "Backflow test due")
        tonight = rules.rule_detail(rule["id"])["tonight"]
        assert (tonight["would_raise"], tonight["cannot_raise"]) == (1, 1)

        report = rules.sweep(dana, rule_ids=[rule["id"]])["rules"][0]
        assert report["raised"] == preview["would_raise"] == 1
        assert report["refused"] == preview["cannot_raise"] == 1

        # After the sweep the raised one is remembered and the refused one is
        # still refused — the Overview promises nothing it will not raise.
        after = rules.rule_detail(rule["id"])["tonight"]
        assert (after["would_raise"], after["cannot_raise"]) == (0, 1)
