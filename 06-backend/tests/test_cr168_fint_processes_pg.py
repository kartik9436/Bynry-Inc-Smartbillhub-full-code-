# ── Trace ──────────────────────────────────────────────
# Change:   CR-168-BRC10 P3.40 — each process raises on PostgreSQL, red first
#           (round 9, lane FIN-T). Completes what `test_cr168_srv4_rules_pg.py`
#           began with four overnight processes in one night.
# Rules:    BR-WRK-024 (a rule-raised job stamps its rule and its PROCESS's
#           label — `DEF-WRK-4096`) · BR-WRK-033 · BR-WRK-055 · hard-won laws
#           7 and 14
# ───────────────────────────────────────────────────────
"""ONE CASE PER PROCESS, on the database the product runs on.

`rule_processes.PROCESSES` holds twelve: six overnight, five screen moments and
the failed-job retry (the blueprint's *thirteen* was the order table's label
count at the time; `test_every_process_has_a_case_here` keeps this file and the
constant the same set). Each case raises ONE job through the path that process
really takes and re-reads it in a NEW transaction, so an aborted savepoint
cannot pass for a raise.

RED FIRST (law 7). `DEF-WRK-4096` — wave M stamped `rule.source_module`
(`payments`, `billing`, `assets`, `reads`) where the order table's CHECK accepts
only the process labels, so the database refused four overnight processes of
five and the sweep logged and moved on. Re-run with `_raise_one` stamping the
module again, the six overnight cases go red on PostgreSQL 16
(`assert 0 == 1`, raised nothing) — quoted in `CR-168-BRC10` §35.
"""

from __future__ import annotations

import datetime as dt
from datetime import datetime, timezone as dt_tz
from decimal import Decimal

import pytest

from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from apps.metering import models as metering_models
from apps.work import from_flows, rule_processes, rules
from apps.work import models as work_models
from apps.work import services as work_services
from apps.work.seams import billing_seam, metering_seam, payments_seam

from tests.isolation_helpers import requires_postgres
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana
from tests.test_us_met_helpers import make_installed_asset, make_premises, tenant_ctx
from tests.test_us_wrk_039_from_flows import _occupant, _published_template, _unit_with_plan

pytestmark = [pytest.mark.django_db, requires_postgres]

TODAY = dt.date.today()
#: The processes this file has a case for — compared with the constant below.
COVERED: frozenset[str] = frozenset({
    "dunning_auto", "billing_exception", "asset_age_rule", "compliance_calendar",
    "high_usage_alert", "meter_read", "move_in", "move_out", "transfer", "reconnect",
    "new_connect", "failed_outcome",
})


def _case(key):
    assert key in COVERED, key
    return key


def _rule(actor, key, template_id, params=None, **extra):
    return rules.create_rule(
        actor,
        {"name": f"P3.40 {key}", "triggers": [{"kind": key, "params": params or {}}],
         "template_id": template_id, **extra},
    )


def _one_rule_job(tenant, key):
    """Re-read in a NEW transaction — an aborted night keeps nothing."""
    with tenant_ctx(tenant):
        rows = list(work_tables.WorkOrder.objects.filter(rule_id__isnull=False).values_list("source", flat=True))
    assert rows == [key], rows


# ── the six overnight processes ─────────────────────────────────────────────


def test_dunning_auto_raises_under_its_label(brazos, dana, monkeypatch):
    key = _case("dunning_auto")
    with tenant_ctx(brazos):
        _premises, unit = _unit_with_plan(dana, brazos)
        account = _occupant(dana, unit)
        monkeypatch.setattr(
            payments_seam, "expired_final_notices",
            lambda **_: [{"account_id": str(account["id"]), "notice_on": "2026-09-30", "tier": 3}],
        )
        _rule(dana, key, _published_template(dana, name="Disconnect visit")["id"], {"grace_days": 2})
        assert rules.sweep(dana)["raised"] == 1
    _one_rule_job(brazos, key)


def test_billing_exception_raises_under_its_label(brazos, dana, monkeypatch):
    key = _case("billing_exception")
    with tenant_ctx(brazos):
        _premises, unit = _unit_with_plan(dana, brazos)
        account = _occupant(dana, unit)
        monkeypatch.setattr(
            billing_seam, "unresolved_breaks",
            lambda **_: [{"account_id": str(account["id"]), "stage": "rate", "reason": "no plan"}],
        )
        _rule(dana, key, _published_template(dana, name="Read verification")["id"])
        assert rules.sweep(dana)["raised"] == 1
    _one_rule_job(brazos, key)


def test_asset_age_rule_raises_under_its_label(brazos, dana):
    key = _case("asset_age_rule")
    from apps.assets import models as assets_models

    with tenant_ctx(brazos):
        aged = make_installed_asset(dana, asset_no="AST-34001")
        assets_models.Asset.objects.filter(pk=aged["id"]).update(
            certification_due=TODAY - dt.timedelta(days=1)
        )
        _rule(dana, key, _published_template(dana, name="Meter exchange")["id"])
        assert rules.sweep(dana)["raised"] == 1
    _one_rule_job(brazos, key)


def test_compliance_calendar_raises_under_its_label(brazos, dana):
    key = _case("compliance_calendar")
    from apps.assets import models as assets_models

    with tenant_ctx(brazos):
        due = make_installed_asset(dana, asset_no="AST-34002")
        assets_models.Asset.objects.filter(pk=due["id"]).update(
            certification_due=TODAY + dt.timedelta(days=10)
        )
        _rule(dana, key, _published_template(dana, name="Backflow test")["id"], {"days_ahead": 30})
        assert rules.sweep(dana)["raised"] == 1
    _one_rule_job(brazos, key)


def test_high_usage_alert_raises_under_its_label(brazos, dana):
    key = _case("high_usage_alert")
    from tests.test_cr168_srv2_raise import _building, _meter

    with tenant_ctx(brazos):
        _premises, units = _building(dana, address="34 Flow St", units=1)
        wet = _meter(dana, units[0], "W-34003", service="water")
        for n in range(3):
            day = dt.date(2026, 5, 1) + dt.timedelta(days=31 * n)
            metering_models.MeterRead.objects.create(
                tenant_id=brazos.id, asset_id=wet["id"],
                read_at=datetime(day.year, day.month, day.day, tzinfo=dt_tz.utc),
                current_value=Decimal(1000 + n), consumption=Decimal("5"),
                unit="kgal", source="manual", lifecycle="committed",
            )
        _rule(dana, key, _published_template(dana, name="Leak check", service="water")["id"],
              {"service": "water", "unit": "kgal", "minimum_consumption": "0"})
        assert rules.sweep(dana)["raised"] == 1
    _one_rule_job(brazos, key)


def test_meter_read_raises_under_its_label(brazos, dana, monkeypatch):
    """The estimate-limit READER is P3.32's and has its own cases; this one is
    about the RAISE, so the reader answers one installed meter."""
    key = _case("meter_read")
    with tenant_ctx(brazos):
        meter = make_installed_asset(dana, asset_no="AST-34004")
        monkeypatch.setattr(
            metering_seam, "meters_at_estimate_limit",
            lambda: [{"asset_id": str(meter["id"]), "estimates": 3, "run_ends": "2026-09-30"}],
        )
        _rule(dana, key, _published_template(dana, name="Forced read")["id"])
        assert rules.sweep(dana)["raised"] == 1
    _one_rule_job(brazos, key)


# ── the five screen moments: the clerk's raise takes the rule's shape ──────


@pytest.mark.parametrize("key", ["move_in", "move_out", "transfer", "reconnect"])
def test_a_screen_moment_raises_the_ticked_job_naming_its_rule(brazos, dana, key):
    _case(key)
    with tenant_ctx(brazos):
        work_services.seed_reference_list("work_priorities", [], "test")
        high = work_models.WorkPriority.objects.get(tenant_id=brazos.id, code="HIGH")
        _premises, unit = _unit_with_plan(dana, brazos)
        account = _occupant(dana, unit)
        template = _published_template(dana, name=f"Visit {key}")
        _rule(dana, key, template["id"], priority_id=str(high.id))
        offer = from_flows.propose(key, account["id"])
        assert [r["template_id"] for r in offer["proposed"] if r.get("preselected_by")] == [
            str(template["id"])
        ]
        raised = from_flows.raise_for(key, account["id"], [template["id"]], dana)
        assert raised["count"] == 1
    with tenant_ctx(brazos):
        order = work_tables.WorkOrder.objects.get(pk=raised["raised"][0]["id"])
        assert order.source == key
        assert order.rule_id is not None and str(order.priority_id) == str(high.id)


def test_new_connect_takes_its_rules_shape_at_the_commit(brazos, dana):
    key = _case("new_connect")
    with tenant_ctx(brazos):
        work_services.seed_reference_list("work_priorities", [], "test")
        urgent = work_models.WorkPriority.objects.get(tenant_id=brazos.id, code="URGENT")
        survey = _published_template(dana, name="Site survey")
        _rule(dana, key, survey["id"], priority_id=str(urgent.id))
        premises = make_premises(dana, address_line="34 Build Ln")
        order = w6.create_work_order(
            dana, None,
            {"premises_id": premises["id"], "type": "Site survey",
             "template_id": str(survey["id"]), "source": work_tables.SOURCE_NEW_CONNECT},
        )
        w6._shape_retry_by_rule(dana, order["id"], str(survey["id"]), work_tables.SOURCE_NEW_CONNECT)
    with tenant_ctx(brazos):
        row = work_tables.WorkOrder.objects.get(pk=order["id"])
        assert row.source == key
        assert row.rule_id is not None and str(row.priority_id) == str(urgent.id)


# ── the retry ───────────────────────────────────────────────────────────────


def test_failed_outcome_shapes_the_one_retry(brazos, dana):
    key = _case("failed_outcome")
    with tenant_ctx(brazos):
        work_services.seed_reference_list("work_priorities", [], "test")
        urgent = work_models.WorkPriority.objects.get(tenant_id=brazos.id, code="URGENT")
        exchange = _published_template(dana, name="Meter exchange", service="water")
        _rule(dana, key, exchange["id"], priority_id=str(urgent.id))
        premises = make_premises(dana, address_line="34 Retry Rd")
        failed = w6.create_work_order(
            dana, None,
            {"type": "Meter exchange", "service": "water", "premises_id": premises["id"],
             "template_id": exchange["id"]},
        )
        order = work_tables.WorkOrder.objects.get(pk=failed["id"])
        order.outcome = work_tables.OUTCOME_FAILED
        order.save(update_fields=["outcome"])
        chain = w6._failed_outcome_chain(dana, order)
    with tenant_ctx(brazos):
        follow = work_tables.WorkOrder.objects.get(pk=chain["follow_up"]["id"])
        assert follow.rule_id is not None and str(follow.priority_id) == str(urgent.id)
        assert work_tables.WorkOrder.objects.filter(follows_order_id=failed["id"]).count() == 1


def test_every_process_has_a_case_here():
    """A thirteenth process added to the constant without a case here fails."""
    assert {p.key for p in rule_processes.PROCESSES} == COVERED
