# ── Trace ──────────────────────────────────────────────
# Story:    CR-168-BRC10 round 5, lane SRV-4 — P3.40 (each process raises on
#           PostgreSQL), DEF-WRK-4096, DEF-WRK-4097, P3.38, P3.65.
# Rules:    BR-WRK-033 · BR-WRK-024 · hard-won law 14 · CLAUDE.md hard rule 3
# ───────────────────────────────────────────────────────
"""The overnight sweep on a REAL PostgreSQL.

Two things the SQLite suite cannot show: the per-subject SAVEPOINT holding when
one subject is refused in the middle of a night that raises for SEVERAL
processes (law 14), and the continuous-flow reader's window function
(`ROW_NUMBER() OVER (PARTITION BY asset ORDER BY read_at DESC)`) answering the
same subjects on the database the product runs on.

RED FIRST (law 7), on the tip before the fix: the four-process night raised
ONE job of four (`assert 1 == 4`) — only the asset-age rule's, under the label
`assets`; the other three were refused `work.order.source_unknown` and logged.
"""

from __future__ import annotations

import datetime as dt
from datetime import datetime, timezone as dt_tz
from decimal import Decimal

import pytest

from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from apps.metering import models as metering_models
from apps.work import models as work_models
from apps.work import rules
from apps.work.seams import billing_seam, payments_seam

from tests.isolation_helpers import requires_postgres
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana
from tests.test_us_met_helpers import make_installed_asset, tenant_ctx
from tests.test_us_wrk_039_from_flows import _occupant, _unit_with_plan

pytestmark = [pytest.mark.django_db, requires_postgres]

YESTERDAY = dt.date.today() - dt.timedelta(days=1)


def _template(actor, *, name, service="electric"):
    header = w6.create_work_order_template(actor, {"name": name, "service": service, "sequence": 0})
    w6.publish_work_order_template(actor, header["id"])
    return header


def _water_meter(actor, asset_no):
    from tests.test_cr168_srv2_raise import _building, _meter

    _premises, units = _building(actor, address=f"{asset_no} Main", units=1)
    return _meter(actor, units[0], asset_no, service="water")


def _reads(tenant, asset, values, *, unit):
    for n, value in enumerate(values):
        day = dt.date(2026, 5, 1) + dt.timedelta(days=31 * n)
        metering_models.MeterRead.objects.create(
            tenant_id=tenant.id, asset_id=asset["id"],
            read_at=datetime(day.year, day.month, day.day, tzinfo=dt_tz.utc),
            current_value=Decimal(1000 + n), consumption=Decimal(str(value)),
            unit=unit, source="manual", lifecycle="committed",
        )


def test_four_processes_one_night_each_job_under_its_own_label(brazos, dana, monkeypatch):
    with tenant_ctx(brazos):
        _premises, unit = _unit_with_plan(dana, brazos)
        account = _occupant(dana, unit)
        monkeypatch.setattr(
            payments_seam, "expired_final_notices",
            lambda **_: [{"account_id": str(account["id"]), "notice_on": "2026-09-30", "tier": 3}],
        )
        monkeypatch.setattr(
            billing_seam, "unresolved_breaks",
            lambda **_: [
                {"account_id": str(account["id"]), "stage": "rate", "reason": "no plan"},
                # A subject that cannot be raised — an account that does not
                # exist. Refused INSIDE its savepoint; the night goes on.
                {"account_id": "00000000-0000-0000-0000-000000000000", "stage": "x", "reason": "y"},
            ],
        )
        exchange = _template(dana, name="Meter exchange")
        disconnect = _template(dana, name="Disconnect visit")
        verify = _template(dana, name="Read verification")
        leak = _template(dana, name="Leak investigation", service="water")
        aged = make_installed_asset(dana, asset_no="AST-08801")  # §30 (BR-WRK-066): installed
        from apps.assets import models as assets_models

        assets_models.Asset.objects.filter(pk=aged["id"]).update(certification_due=YESTERDAY)
        wet = _water_meter(dana, "W-8801")
        _reads(brazos, wet, [4, 5, 6], unit="kgal")
        # Written in wave M's shape (module + trigger name) — the shape every
        # tenant's five seeded rules already have, and one the tip accepts, so
        # this case runs unchanged on both sides of the fix.
        for name, module, trigger, template, params in (
            ("Disconnect for non-pay", "payments", "final_notice_expired_unpaid", disconnect,
             {"grace_days": 2}),
            ("Read verification", "billing", "billing_exception_unresolved", verify, {}),
            ("Asset age rule", "assets", "asset_past_certification_life", exchange, {}),
            ("Leak investigation", "reads", "continuous_flow_alarm", leak,
             {"service": "water", "unit": "kgal", "minimum_consumption": "0"}),
        ):
            rules.create_rule(
                dana,
                {"name": name, "source_module": module, "trigger_kind": trigger,
                 "template_id": template["id"], "params": params},
            )

        result = rules.sweep(dana)
        assert result["raised"] == 4, result

    with tenant_ctx(brazos):
        # Re-read in a NEW transaction: an aborted night would have kept nothing.
        sources = sorted(
            work_tables.WorkOrder.objects.filter(rule_id__isnull=False).values_list("source", flat=True)
        )
        assert sources == ["asset_age_rule", "billing_exception", "dunning_auto", "high_usage_alert"]
        assert work_models.WorkOrderRuleRaise.objects.count() == 4


def test_the_window_reader_takes_only_the_last_reads_on_postgres(brazos, dana):
    """A meter that leaked a year ago and stopped is not in continuous flow:
    only its LAST three readings count, cut by the window in SQL."""
    from apps.work.seams import metering_seam

    with tenant_ctx(brazos):
        stopped = _water_meter(dana, "W-8802")
        flowing = _water_meter(dana, "W-8803")
        _reads(brazos, stopped, [9, 9, 9, 0], unit="kgal")
        _reads(brazos, flowing, [0, 9, 9, 9], unit="kgal")
        found = metering_seam.meters_in_continuous_flow(
            consecutive_reads=3, minimum_consumption="0", service_code="water", unit="kgal"
        )
        assert [row["asset_id"] for row in found] == [str(flowing["id"])]
