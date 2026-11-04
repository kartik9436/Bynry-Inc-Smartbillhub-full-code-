# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-WRK-9687 (CR-168-BRC10 round 8, lane FIX-8A) — the seeded rule
#           *Backflow test due* raised the template *Meter exchange —
#           residential*, which names meters only, so every backflow preventer
#           it found was refused `work.order.asset_type_not_on_template`
#           (BF-0901: 1 found, 0 raised, 1 refused, an ERROR every night).
# Rules:    BR-WRK-016 (a rule raises a published template) · US-WRK-037 ·
#           BR-TEN-056/057 (sample data)
# ───────────────────────────────────────────────────────
"""Every seeded rule raises a template that applies to what it sweeps: the
backflow rule a backflow test, done to a backflow preventer."""

from __future__ import annotations

import datetime as dt

import pytest

from apps.assets import models as assets_models
from apps.assets import services as asset_services
from apps.metering import connections as w6
from apps.work import rules, sample_data as work_sample, templates_svc
from apps.work.seams import assets_seam
from apps.work.rules_models import WorkOrderRule

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana
from tests.test_us_met_helpers import make_premises, make_unit, tenant_ctx

pytestmark = pytest.mark.django_db


def _publish_exchange_for_meters(actor):
    """The demo's exchange template as `sample_field_work` fills it: done TO a
    Meter (`asset_types: ("Meter",)`)."""
    header = templates_svc.create_draft(
        actor,
        {"name": work_sample.EXCHANGE_TEMPLATE_NAME, "service": "water", "scope": "per_asset",
         "sequence": 0},
    )
    meter = assets_seam.asset_type_ids_of_names(["Meter"])
    templates_svc.replace_collection(
        actor, header["id"], "asset-types", [{"asset_type_id": str(meter[0])}]
    )
    templates_svc.publish(actor, header["id"])


def test_9687_the_seeded_backflow_rule_raises_on_a_backflow_preventer(dana, brazos):
    with tenant_ctx(brazos):
        _publish_exchange_for_meters(dana)
        work_sample.seed_sample_records(dana)
        rule = WorkOrderRule.objects.get(name="Backflow test due")

        premises = make_premises(dana, services_available=["water"])
        unit = make_unit(dana, premises["id"], label="Unit 9687")
        device = asset_services.create_asset(
            dana,
            {"type": "backflow", "asset_no": "BF-0901", "unit_id": unit["id"],
             "install_date": "2024-01-01"},
        )
        assets_models.Asset.objects.filter(pk=device["id"]).update(
            certification_due=dt.date.today() + dt.timedelta(days=15)
        )
        assert w6.asset_raise_refusal(rule.template_id, device["id"]) is None, (
            "the backflow rule's template does not apply to a backflow preventer"
        )

        WorkOrderRule.objects.filter(pk=rule.pk).update(enabled=True)
        report = rules.sweep(dana, rule_ids=[str(rule.id)])["rules"][0]
        assert (report["raised"], report.get("refused", 0)) == (1, 0), report
