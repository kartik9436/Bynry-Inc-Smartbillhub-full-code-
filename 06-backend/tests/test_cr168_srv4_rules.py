# ── Trace ──────────────────────────────────────────────
# Story:    CR-168-BRC10 round 5, lane SRV-4 — P3.30–P3.38, P3.61, P3.65 and
#           DEF-WRK-4096 / DEF-WRK-4097.
# Rules:    BR-WRK-033 · BR-WRK-024 · BR-WRK-055 · BR-WRK-054 · BR-MET-027 ·
#           CLAUDE.md hard rule 3 (a consumption figure carries its unit)
# ───────────────────────────────────────────────────────
"""Every overnight process raises its job, under its OWN label.

⚠ **THE ESCAPE THIS FILE CLOSES (`DEF-WRK-4096`).** Every raise-path test in
wave M used the ASSETS trigger — the one source string coincidentally valid in
both vocabularies — so no test ever swept a payments, billing or reads rule,
and four of five triggers raised nothing for a month with 25 cases green. So
here there is ONE case per overnight process, each asserting the job exists
AND what *Raised by* reads.

The subject READERS for dunning and billing are stood in for (their seams are
other modules' and are tested there); the raise path, the stamp and the memory
are the real code. The two NEW readers (`compliance_calendar`, `meter_read`)
and the narrowed continuous-flow reader read real rows.

`tests/test_cr168_srv4_rules_pg.py` runs the sweep on PostgreSQL (law 14).
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
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana
from tests.test_us_met_helpers import make_installed_asset, tenant_ctx
from tests.test_us_wrk_039_from_flows import _occupant, _unit_with_plan

YESTERDAY = dt.date.today() - dt.timedelta(days=1)


def _template(actor, *, name="Meter exchange", service="electric"):
    header = w6.create_work_order_template(actor, {"name": name, "service": service, "sequence": 0})
    w6.publish_work_order_template(actor, header["id"])
    return header


def _legacy_rule(actor, template_id, *, name, source_module, trigger_kind, params=None):
    """A rule written the way the wave M builder writes it today — module and
    trigger name. The five rules every tenant already holds look like this."""
    return rules.create_rule(
        actor,
        {
            "name": name,
            "source_module": source_module,
            "trigger_kind": trigger_kind,
            "template_id": template_id,
            "params": params or {},
        },
    )


def _sweep_one(actor, rule_id):
    result = rules.sweep(actor, rule_ids=[rule_id])
    return result["rules"][0]


# ══════════════════════════════════════════════════════════════════════════
# DEF-WRK-4096 — one case per overnight process; each raises, each labelled
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_4096_a_final_notice_rule_raises_and_the_job_reads_dunning_auto(dana, brazos, monkeypatch):
    with tenant_ctx(brazos):
        _premises, unit = _unit_with_plan(dana, brazos)
        account = _occupant(dana, unit)
        template = _template(dana)
        monkeypatch.setattr(
            payments_seam,
            "expired_final_notices",
            lambda **_: [{"account_id": str(account["id"]), "notice_on": "2026-09-30", "tier": 3}],
        )
        rule = _legacy_rule(
            dana, template["id"], name="Disconnect for non-pay",
            source_module="payments", trigger_kind="final_notice_expired_unpaid",
            params={"grace_days": 2},
        )
        report = _sweep_one(dana, rule["id"])
        assert report["raised"] == 1, report
        order = work_tables.WorkOrder.objects.get(rule_id=rule["id"])
        assert order.source == "dunning_auto"
        assert order.source_ref == "Disconnect for non-pay"


@pytest.mark.django_db
def test_4096_a_billing_exception_rule_raises_and_reads_billing_exception(dana, brazos, monkeypatch):
    with tenant_ctx(brazos):
        _premises, unit = _unit_with_plan(dana, brazos)
        account = _occupant(dana, unit)
        template = _template(dana)
        monkeypatch.setattr(
            billing_seam,
            "unresolved_breaks",
            lambda **_: [{"account_id": str(account["id"]), "stage": "rate", "reason": "no plan"}],
        )
        rule = _legacy_rule(
            dana, template["id"], name="Read verification",
            source_module="billing", trigger_kind="billing_exception_unresolved",
        )
        assert _sweep_one(dana, rule["id"])["raised"] == 1
        assert work_tables.WorkOrder.objects.get(rule_id=rule["id"]).source == "billing_exception"


@pytest.mark.django_db
def test_4096_the_asset_age_rule_reads_asset_age_rule_not_the_assets_door(dana, brazos):
    with tenant_ctx(brazos):
        template = _template(dana)
        asset = make_installed_asset(dana, asset_no="AST-04412")  # §30: installed
        from apps.assets import models as assets_models

        assets_models.Asset.objects.filter(pk=asset["id"]).update(certification_due=YESTERDAY)
        rule = _legacy_rule(
            dana, template["id"], name="Asset age rule",
            source_module="assets", trigger_kind="asset_past_certification_life",
        )
        assert _sweep_one(dana, rule["id"])["raised"] == 1
        order = work_tables.WorkOrder.objects.get(rule_id=rule["id"])
        # `assets` means *raised from the Assets door* (BR-WRK-056). A rule's job
        # must be told apart from a clerk's on any report grouping by source.
        assert order.source == "asset_age_rule"


def _water_meter(actor, asset_no):
    from tests.test_cr168_srv2_raise import _building, _meter

    _premises, units = _building(actor, address=f"{asset_no} Leak Ln", units=1)
    return _meter(actor, units[0], asset_no, service="water")


def _electric_meter(actor, asset_no):
    from tests.test_cr168_srv2_raise import _building, _meter

    _premises, units = _building(actor, address=f"{asset_no} Spark St", units=1)
    return _meter(actor, units[0], asset_no, service="electric")


def _reads(tenant, asset, values, *, unit, estimate=False, start=dt.date(2026, 5, 1)):
    """One committed read a month, oldest first, each carrying its unit."""
    for n, value in enumerate(values):
        day = start + dt.timedelta(days=31 * n)
        metering_models.MeterRead.objects.create(
            tenant_id=tenant.id,
            asset_id=asset["id"],
            read_at=datetime(day.year, day.month, day.day, tzinfo=dt_tz.utc),
            current_value=None if estimate else Decimal(1000 + 10 * n),
            consumption=Decimal(str(value)),
            unit=unit,
            source="manual",
            lifecycle="committed",
        )


@pytest.mark.django_db
def test_4096_a_continuous_flow_rule_raises_and_reads_high_usage_alert(dana, brazos):
    with tenant_ctx(brazos):
        template = _template(dana, name="Leak investigation", service="water")
        meter = _water_meter(dana, "W-7100")
        _reads(brazos, meter, [4, 5, 6], unit="gal")
        rule = _legacy_rule(
            dana, template["id"], name="Leak investigation",
            source_module="reads", trigger_kind="continuous_flow_alarm",
            params={"service": "water", "unit": "gal", "consecutive_reads": 3,
                    "minimum_consumption": "0"},
        )
        assert _sweep_one(dana, rule["id"])["raised"] == 1
        order = work_tables.WorkOrder.objects.get(rule_id=rule["id"])
        assert order.source == "high_usage_alert"
        assert str(order.asset_id) == str(meter["id"])


# ── DEF-WRK-4097 · an electric meter is never in a water leak rule ─────────
@pytest.mark.django_db
def test_4097_an_electric_meter_that_uses_power_every_month_is_not_a_water_leak(dana, brazos):
    with tenant_ctx(brazos):
        template = _template(dana, name="Leak investigation", service="water")
        water = _water_meter(dana, "W-7101")
        electric = _electric_meter(dana, "E-7101")
        _reads(brazos, water, [4, 5, 6], unit="gal")
        _reads(brazos, electric, [400, 500, 600], unit="kWh")
        rule = rules.create_rule(
            dana,
            {
                "name": "Leak investigation",
                "triggers": [
                    {"kind": "high_usage_alert",
                     "params": {"service": "water", "unit": "gal", "minimum_consumption": "0"}},
                ],
                "template_id": template["id"],
            },
        )
        report = _sweep_one(dana, rule["id"])
        assert report["subjects"] == 1, report
        assert {str(o.asset_id) for o in work_tables.WorkOrder.objects.filter(rule_id=rule["id"])} == {
            str(water["id"])
        }


@pytest.mark.django_db
def test_4097_the_minimum_is_compared_only_in_its_own_unit(dana, brazos):
    """Hard rule 3: `5` against kgal and `5` against gal are different amounts.
    A meter whose readings are in another unit breaks the run; it is never
    converted and never compared as a bare number."""
    with tenant_ctx(brazos):
        template = _template(dana, name="Leak investigation", service="water")
        in_gal = _water_meter(dana, "W-7102")
        in_kgal = _water_meter(dana, "W-7103")
        _reads(brazos, in_gal, [40, 50, 60], unit="gal")
        _reads(brazos, in_kgal, [40, 50, 60], unit="kgal")
        rule = rules.create_rule(
            dana,
            {
                "name": "Leak in gallons",
                "triggers": [
                    {"kind": "high_usage_alert",
                     "params": {"service": "water", "unit": "gal", "minimum_consumption": "30"}},
                ],
                "template_id": template["id"],
            },
        )
        assert _sweep_one(dana, rule["id"])["subjects"] == 1


@pytest.mark.django_db
def test_4097_a_continuous_flow_rule_with_no_service_is_refused_at_save(dana, brazos):
    with tenant_ctx(brazos):
        template = _template(dana, name="Leak investigation", service="water")
        with pytest.raises(errors.ValidationError) as caught:
            rules.create_rule(
                dana,
                {
                    "name": "Leak anywhere",
                    "triggers": [{"kind": "high_usage_alert", "params": {"unit": "gal"}}],
                    "template_id": template["id"],
                },
            )
        assert caught.value.message_key == "work.rules.param_required"


# ══════════════════════════════════════════════════════════════════════════
# P3.32 · the two new overnight readers
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_p332_certification_due_soon_raises_ahead_of_the_date_and_reads_compliance_calendar(
    dana, brazos
):
    with tenant_ctx(brazos):
        template = _template(dana)
        # INSTALLED (`CR-168-BRC10` §30, `BR-WRK-066`).
        soon = make_installed_asset(dana, asset_no="BF-0001")
        later = make_installed_asset(dana, asset_no="BF-0002")
        past = make_installed_asset(dana, asset_no="BF-0003")
        from apps.assets import models as assets_models

        today = dt.date.today()
        assets_models.Asset.objects.filter(pk=soon["id"]).update(
            certification_due=today + dt.timedelta(days=20)
        )
        assets_models.Asset.objects.filter(pk=later["id"]).update(
            certification_due=today + dt.timedelta(days=45)
        )
        # Already past: the asset-age rule's subject, never this one's.
        assets_models.Asset.objects.filter(pk=past["id"]).update(certification_due=YESTERDAY)
        rule = rules.create_rule(
            dana,
            {
                "name": "Backflow test due",
                "triggers": [{"kind": "compliance_calendar", "params": {"days_ahead": 30}}],
                "template_id": template["id"],
            },
        )
        report = _sweep_one(dana, rule["id"])
        assert report["raised"] == 1, report
        order = work_tables.WorkOrder.objects.get(rule_id=rule["id"])
        assert order.source == "compliance_calendar"
        assert str(order.asset_id) == str(soon["id"])


@pytest.mark.django_db
def test_p332_due_soon_needs_a_lead_time(dana, brazos):
    with tenant_ctx(brazos):
        template = _template(dana)
        with pytest.raises(errors.ValidationError) as caught:
            rules.create_rule(
                dana,
                {
                    "name": "Backflow test due",
                    "triggers": [{"kind": "compliance_calendar", "params": {}}],
                    "template_id": template["id"],
                },
            )
        assert caught.value.message_key == "work.rules.param_required"


@pytest.mark.django_db
def test_p332_the_estimate_limit_raises_a_visit_at_meter_read_settings_own_figure(dana, brazos):
    """`BR-MET-027`: at `est_max_consecutive` estimates in a row the visit is
    forced. The limit is Meter-read settings' own (seeded 2), never a figure on
    the rule."""
    with tenant_ctx(brazos):
        template = _template(dana, name="Re-read", service="water")
        at_limit = _water_meter(dana, "W-7200")
        below = _water_meter(dana, "W-7201")
        _reads(brazos, at_limit, [10], unit="gal")
        _reads(brazos, at_limit, [11, 12], unit="gal", estimate=True, start=dt.date(2026, 6, 1))
        _reads(brazos, below, [10, 11], unit="gal")
        _reads(brazos, below, [12], unit="gal", estimate=True, start=dt.date(2026, 7, 2))
        rule = rules.create_rule(
            dana,
            {
                "name": "Estimate limit visit",
                "triggers": [{"kind": "meter_read", "params": {}}],
                "template_id": template["id"],
            },
        )
        report = _sweep_one(dana, rule["id"])
        assert report["raised"] == 1, report
        order = work_tables.WorkOrder.objects.get(rule_id=rule["id"])
        assert order.source == "meter_read"
        assert str(order.asset_id) == str(at_limit["id"])


# ══════════════════════════════════════════════════════════════════════════
# P3.30 · the processes served once · P3.65 several triggers · P3.38
# ══════════════════════════════════════════════════════════════════════════


def test_p330_every_process_key_is_a_label_the_order_table_accepts():
    from apps.work import rule_processes

    keys = [p.key for p in rule_processes.PROCESSES]
    assert len(keys) == len(set(keys))
    assert set(keys) <= set(work_tables.WORK_ORDER_SOURCES), set(keys) - set(work_tables.WORK_ORDER_SOURCES)
    # `BR-PAY-036`: a payment alone never books a reconnection.
    assert "payment_received" not in keys
    # Thirteen since `BR-WRK-067` (PO 2026-10-22): a route finding is a
    # process a rule can be written on (`rule_processes.MOMENT_ARRIVAL`).
    assert len(keys) == 13


@pytest.mark.django_db
def test_p330_the_process_list_is_served_with_its_settings(dana, brazos):
    with tenant_ctx(brazos):
        listed = rules.processes()
        by_key = {row["key"]: row for row in listed["results"]}
        assert by_key["high_usage_alert"]["moment"] == "overnight"
        assert by_key["move_in"]["moment"] == "screen"
        assert by_key["failed_outcome"]["moment"] == "retry"
        assert [p["name"] for p in by_key["high_usage_alert"]["params"]] == [
            "service", "consecutive_reads", "minimum_consumption", "unit",
        ]
        # The estimate limit is Meter-read settings' own figure, read-only.
        assert by_key["meter_read"]["params"][0]["kind"] == "setting"
        assert listed["settings"]["est_max_consecutive"] == 2


@pytest.mark.django_db
def test_p365_two_triggers_on_one_meter_raise_one_job(dana, brazos):
    with tenant_ctx(brazos):
        template = _template(dana, name="Meter exchange", service="water")
        meter = _water_meter(dana, "W-7300")
        _reads(brazos, meter, [4, 5, 6], unit="gal")
        from apps.assets import models as assets_models

        assets_models.Asset.objects.filter(pk=meter["id"]).update(certification_due=YESTERDAY)
        rule = rules.create_rule(
            dana,
            {
                "name": "Two reasons",
                "triggers": [
                    {"kind": "asset_age_rule", "params": {}},
                    {"kind": "high_usage_alert",
                     "params": {"service": "water", "unit": "gal", "minimum_consumption": "0"}},
                ],
                "template_id": template["id"],
            },
        )
        assert [t["kind"] for t in rule["triggers"]] == ["asset_age_rule", "high_usage_alert"]
        report = _sweep_one(dana, rule["id"])
        assert report["raised"] == 1, report
        assert work_tables.WorkOrder.objects.filter(rule_id=rule["id"]).count() == 1


@pytest.mark.django_db
def test_p365_a_rule_needs_at_least_one_trigger(dana, brazos):
    with tenant_ctx(brazos):
        template = _template(dana)
        with pytest.raises(errors.ValidationError) as caught:
            rules.create_rule(
                dana, {"name": "Nothing", "triggers": [], "template_id": template["id"]}
            )
        assert caught.value.message_key == "work.rules.trigger_required"


@pytest.mark.django_db
def test_p338_a_template_already_open_on_the_subject_is_not_raised_again(dana, brazos):
    """One subject, one open job per template — whoever raised the first."""
    with tenant_ctx(brazos):
        template = _template(dana)
        asset = make_installed_asset(dana, asset_no="AST-05001")  # §30: installed
        from apps.assets import models as assets_models

        assets_models.Asset.objects.filter(pk=asset["id"]).update(certification_due=YESTERDAY)
        # A clerk raised the exchange from the asset's own door first.
        w6.create_work_order(
            dana, None,
            {"asset_id": asset["id"], "type": "Meter exchange", "template_id": template["id"],
             "source": "assets"},
        )
        rule = rules.create_rule(
            dana,
            {"name": "Asset age rule",
             "triggers": [{"kind": "asset_age_rule", "params": {}}],
             "template_id": template["id"]},
        )
        report = _sweep_one(dana, rule["id"])
        assert report["subjects"] == 1
        assert report["raised"] == 0
        assert report["already_open"] == 1


@pytest.mark.django_db
def test_p361_a_rule_says_when_it_last_fired_and_how_many_jobs_it_raised(dana, brazos):
    with tenant_ctx(brazos):
        template = _template(dana)
        rule = rules.create_rule(
            dana,
            {"name": "Asset age rule",
             "triggers": [{"kind": "asset_age_rule", "params": {}}],
             "template_id": template["id"]},
        )
        assert rule["last_fired_at"] is None
        assert rule["jobs_raised"] == 0
        for n in (1, 2):
            asset = make_installed_asset(dana, asset_no=f"AST-0600{n}")  # §30: installed
            from apps.assets import models as assets_models

            assets_models.Asset.objects.filter(pk=asset["id"]).update(certification_due=YESTERDAY)
        rules.sweep(dana)
        again = rules.rule_dict(rules.rule(rule["id"]))
        assert again["jobs_raised"] == 2
        assert again["this_month"] == 2
        assert again["last_fired_at"] is not None


@pytest.mark.django_db
def test_p331_a_legacy_move_in_rule_is_a_screen_moment_and_raises_nothing_overnight(
    dana, brazos, monkeypatch
):
    """Ruling 10: a customer moving in is a moment a clerk stands in. A rule
    on it pre-selects the job on that screen; the overnight sweep never adds a
    second visit to a move-in whose clerk raised one or chose *No visit
    needed*."""
    from apps.work.seams import customers_seam

    with tenant_ctx(brazos):
        template = _template(dana)
        called = []
        monkeypatch.setattr(
            customers_seam, "completed_occupancies", lambda **kw: called.append(kw) or []
        )
        rule = _legacy_rule(
            dana, template["id"], name="Move-in / move-out",
            source_module="accounts", trigger_kind="occupancy_completed",
            params={"within_days": 7},
        )
        report = _sweep_one(dana, rule["id"])
        assert report["raised"] == 0
        assert called == [], "the overnight sweep must not read a screen moment"
        assert rule["triggers"][0]["kind"] == "move_in"
