# ── Trace ──────────────────────────────────────────────
# Story:    US-MET-018 (cycle completeness bar + chase list — the RESOLVER and
#           the import-time rule half) · US-MET-008 (rule outcomes on staged
#           rows) · US-MET-017 (channel groups)   Screens: S28 steps 3–4 · S25
# Rules:    BR-MET-049 (plan-driven read-set completeness — the unit's plan
#           determines the required read set per meter; TOU → per-window
#           records; demand → +demand record) · BR-MET-059 (channel model:
#           flat meter = single `total` channel) · BR-MET-015 (warnings
#           postable only via explicit accept + reason) · BR-RAT-067 (a TOU
#           window's channel is STATED by the utility, never derived) ·
#           BR-AST-029 (net meter cycle = consumption + export records)
# Journeys: J2 (read-to-cash, step 6 validation)
# CR:       CR-038 W1 (backend of plan-driven read completeness)
# ───────────────────────────────────────────────────────
"""US-MET-018 backend — the expected-register-set resolver and RULE_PLAN_REGISTERS.

The headline guard here was PROVED RED FIRST (hard-won law 7 / r11 step 2d):
`test_us_met_018_guard__tou_meter_given_only_a_total_row_is_flagged_by_name`
was written and run against the PRE-CHANGE code path before the rule existed.

RED RUN (verbatim, 2026-08-26, pre-change tree — before validation.py knew
`plan_registers` and before services.validate_read_batch grouped registers):

                outcome = outcome_named(row, "plan_registers")
    >           assert outcome is not None, (
                    "no plan_registers outcome stored on the row — BR-MET-049 is not "
                    "evaluated at import time"
                )
    E           AssertionError: no plan_registers outcome stored on the row —
                BR-MET-049 is not evaluated at import time
    E           assert None is not None

    tests/test_us_met_018_plan_registers.py:173: AssertionError
    1 failed in 83.05s

The whole fixture chain (plan + version + windows + assign + stage + validate)
ran green up to that assertion, so the red is the RULE'S absence and nothing
else. Only then was the rule built and the same test shown green, unchanged.
"""

from datetime import date, time
from decimal import Decimal

import pytest

# `completeness` is imported INSIDE the tests that need it, not here: this
# module had to be importable against the PRE-CHANGE tree so the guard test
# could be run RED before the module it proves existed (hard-won law 7).
from apps.metering import models, services, validation

from tests.test_us_met_reads_helpers import *  # noqa: F401,F403
from tests.test_us_met_reads_helpers import (  # noqa: F401
    a_meter,
    accept_warnings,
    csv_body,
    make_plan,
    make_premises,
    make_unit,
    seed_config,
    stage,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


# ── fixture plumbing ────────────────────────────────────────────────────────


def plan_with_version(
    tenant,
    *,
    name,
    model,
    service_code="electric",
    windows=(),
    demand=False,
    uom="kWh",
    effective_from=date(2026, 1, 1),
):
    """A published plan whose <service> schedule carries an ACTIVATED version.

    `make_plan` builds the plan + tariff + PlanRateSchedule link and stops
    there (no version — every pre-existing fixture resolves to
    `no_version_in_force`, which is what keeps this lane's rule out of older
    tests' way). This helper adds the version and its structure rows the way
    the rating wizard stores them — fixture data, the `make_plan` precedent,
    not a cross-module write from metering.

    `windows` is a sequence of channel names (e.g. ("tou_on", "tou_off")) —
    each becomes a TimeOfUseWindow ROW with its BR-RAT-067 stated channel, so
    a test can prove the resolver reads ROWS rather than hardcoding the
    three-window set. Pass a None channel to model a pre-BR-RAT-067 window.
    """
    from apps.rating import models as rating_models

    plan = make_plan(tenant, name=name, services=(service_code,))
    schedule_row = rating_models.PlanRateSchedule.objects.get(
        tenant=tenant, rate_plan=plan, service__code=service_code
    )
    version = rating_models.TariffVersion.objects.create(
        tenant=tenant,
        tariff=schedule_row.tariff,
        model=model,
        uom=uom,
        effective_from=effective_from,
    )
    for index, channel in enumerate(windows):
        rating_models.TimeOfUseWindow.objects.create(
            tenant=tenant,
            tariff_version=version,
            label=channel or f"window-{index}",
            day_type="weekday",
            start_time=time(6 + index * 4, 0),
            end_time=time(10 + index * 4, 0),
            unit_price=Decimal("0.10") + Decimal(index),
            channel=channel,
        )
    if demand:
        rating_models.DemandRateConfig.objects.create(
            tenant=tenant,
            tariff_version=version,
            energy_rate_per_kwh=Decimal("0.09"),
            demand_rate_per_kw=Decimal("14.50"),
        )
    return plan


def planned_meter(
    actor,
    tenant,
    plan,
    *,
    asset_no="M-7451",
    net_metering=False,
    label="Unit 3F",
    service="electric",
    uom="kWh",
):
    """A meter on a unit that HOLDS the plan (unit.rate_plan_id — the binding
    unit plan, BR-CUS-014), created through the real services."""
    premises = make_premises(
        actor, address_line=f"1408 Bluestem Ln {asset_no}", services_available=[service]
    )
    unit = make_unit(actor, premises["id"], label=label, services=[service])
    if plan is not None:
        services.assign_unit_plan(
            actor,
            unit["id"],
            {"tariff_id": str(plan.id), "effective_from": "2026-06-01", "reason": "fixture"},
        )
    asset = a_meter(actor, asset_no, unit_id=unit["id"], service=service, uom=uom)
    if net_metering:
        from apps.assets import models as asset_models

        asset_models.Asset.objects.filter(pk=asset["id"]).update(net_metering=True)
    return unit, asset


def outcome_named(row, rule):
    return next((o for o in (row.rule_outcomes or []) if o.get("rule") == rule), None)


# ── the guard, proved red first ─────────────────────────────────────────────


def test_us_met_018_guard__tou_meter_given_only_a_total_row_is_flagged_by_name(brazos, dana):
    """BR-MET-049 verbatim: "the unit's plan determines the required read set
    per meter (TOU → per-window records; demand → +demand record)". A TOU
    meter whose file carries only `total` must be flagged BY NAME — expects
    tou_on/tou_mid/tou_off/total, file has total only — as a WARNING (a person
    may accept with a reason, BR-MET-015; posting an incomplete meter is
    unruled — Open 2 — so it is deliberately NOT a hard error).

    RED FIRST: see the module docstring for the verbatim pre-change failure.
    """
    with tenant_ctx(brazos):
        seed_config()
        plan = plan_with_version(
            brazos,
            name="TOU Residential",
            model="time_of_use",
            windows=("tou_on", "tou_mid", "tou_off"),
        )
        planned_meter(dana, brazos, plan, asset_no="M-7451")

        batch = stage(dana, csv_body("M-7451,2026-08-03,1200,total"))
        services.validate_read_batch(dana, batch["id"])

        row = models.ReadImportRow.objects.get(batch_id=batch["id"], row_no=1)
        outcome = outcome_named(row, "plan_registers")
        assert outcome is not None, (
            "no plan_registers outcome stored on the row — BR-MET-049 is not "
            "evaluated at import time"
        )
        assert outcome["severity"] == validation.WARNING
        # The shortfall is named, never summarised away (BR-MET-022/056).
        assert outcome["detail"]["missing"] == ["tou_on", "tou_mid", "tou_off"]
        assert outcome["detail"]["received"] == ["total"]
        assert sorted(outcome["detail"]["expected"]) == sorted(
            ["total", "tou_on", "tou_mid", "tou_off"]
        )
        assert "tou_on/tou_mid/tou_off" in outcome["detail"]["summary"]
        assert "total only" in outcome["detail"]["summary"]
        # The row's severity is the warning — postable only via an explicit
        # accept + reason (BR-MET-015), which the next test proves.
        assert row.severity == validation.WARNING


def test_us_met_018__the_warning_is_acceptable_with_a_reason_and_posts(brazos, dana):
    """BR-MET-015: a warning is postable ONLY via explicit accept + reason —
    the incomplete TOU meter can be posted by a person who says why, because
    the billing consequence of an incomplete set is unruled (Open 2)."""
    with tenant_ctx(brazos):
        seed_config()
        plan = plan_with_version(
            brazos,
            name="TOU Residential",
            model="time_of_use",
            windows=("tou_on", "tou_mid", "tou_off"),
        )
        planned_meter(dana, brazos, plan, asset_no="M-7451")

        batch = stage(dana, csv_body("M-7451,2026-08-03,1200,total"))
        services.validate_read_batch(dana, batch["id"])
        accept_warnings(dana, batch["id"], reason="single-register install confirmed on site")
        result = services.commit_read_batch(dana, batch["id"], {"certified": True})

        assert result["counts"]["posted"] == 1


def test_us_met_018__a_complete_tou_group_passes_the_rule(brazos, dana):
    with tenant_ctx(brazos):
        seed_config()
        plan = plan_with_version(
            brazos,
            name="TOU Residential",
            model="time_of_use",
            windows=("tou_on", "tou_mid", "tou_off"),
        )
        planned_meter(dana, brazos, plan, asset_no="M-7451")

        batch = stage(
            dana,
            csv_body(
                "M-7451,2026-08-03,400,tou_on",
                "M-7451,2026-08-03,300,tou_mid",
                "M-7451,2026-08-03,500,tou_off",
                "M-7451,2026-08-03,1200,total",
            ),
        )
        services.validate_read_batch(dana, batch["id"])

        for row in models.ReadImportRow.objects.filter(batch_id=batch["id"]):
            outcome = outcome_named(row, "plan_registers")
            assert outcome is not None
            assert outcome["severity"] == validation.OK


def test_us_met_018__the_window_set_comes_from_rows_not_a_hardcoded_three(brazos, dana):
    """The resolver reads the plan's OWN TimeOfUseWindow rows (BR-RAT-067
    stated channels): a two-window schedule expects exactly those two windows
    plus total — never a hardcoded tou_on/tou_mid/tou_off."""
    with tenant_ctx(brazos):
        seed_config()
        plan = plan_with_version(
            brazos, name="Two Window TOU", model="time_of_use", windows=("tou_on", "tou_off")
        )
        planned_meter(dana, brazos, plan, asset_no="M-7452")

        batch = stage(
            dana,
            csv_body("M-7452,2026-08-03,400,tou_on", "M-7452,2026-08-03,800,total"),
        )
        services.validate_read_batch(dana, batch["id"])

        row = models.ReadImportRow.objects.get(batch_id=batch["id"], row_no=1)
        outcome = outcome_named(row, "plan_registers")
        assert outcome["severity"] == validation.WARNING
        assert outcome["detail"]["missing"] == ["tou_off"]  # tou_mid is NOT expected
        assert sorted(outcome["detail"]["expected"]) == sorted(["total", "tou_on", "tou_off"])


def test_us_met_018__demand_plan_expects_total_plus_demand(brazos, dana):
    """BR-MET-049: "demand → +demand record"."""
    with tenant_ctx(brazos):
        seed_config()
        plan = plan_with_version(brazos, name="Demand Commercial", model="demand", demand=True)
        planned_meter(dana, brazos, plan, asset_no="M-7461")

        batch = stage(dana, csv_body("M-7461,2026-08-03,52000,total"))
        services.validate_read_batch(dana, batch["id"])

        row = models.ReadImportRow.objects.get(batch_id=batch["id"], row_no=1)
        outcome = outcome_named(row, "plan_registers")
        assert outcome["severity"] == validation.WARNING
        assert outcome["detail"]["missing"] == ["demand"]
        assert sorted(outcome["detail"]["expected"]) == ["demand", "total"]


def test_us_met_018__flat_plan_with_total_only_is_complete(brazos, dana):
    """BR-MET-059: flat meter = single `total` channel — a flat plan's meter
    sending total is COMPLETE, not warned."""
    with tenant_ctx(brazos):
        seed_config()
        plan = plan_with_version(brazos, name="Flat Residential", model="flat")
        planned_meter(dana, brazos, plan, asset_no="M-7001")

        batch = stage(dana, csv_body("M-7001,2026-08-03,42864,total"))
        services.validate_read_batch(dana, batch["id"])

        row = models.ReadImportRow.objects.get(batch_id=batch["id"], row_no=1)
        outcome = outcome_named(row, "plan_registers")
        assert outcome is not None and outcome["severity"] == validation.OK


def test_us_met_018__net_metered_asset_adds_the_export_register(brazos, dana):
    """BR-AST-029: a net meter's cycle is a consumption record + an export
    record. The export expectation is an ASSET fact layered onto the plan set."""
    with tenant_ctx(brazos):
        seed_config()
        plan = plan_with_version(brazos, name="Solar Flat", model="flat")
        planned_meter(dana, brazos, plan, asset_no="M-7801", net_metering=True)

        batch = stage(dana, csv_body("M-7801,2026-08-03,900,total"))
        services.validate_read_batch(dana, batch["id"])

        row = models.ReadImportRow.objects.get(batch_id=batch["id"], row_no=1)
        outcome = outcome_named(row, "plan_registers")
        assert outcome["severity"] == validation.WARNING
        assert outcome["detail"]["missing"] == ["export"]


def test_us_met_018__no_plan_is_a_stated_absence_never_a_warning(brazos, dana):
    """US-MET-018 TC-5: a unit with no plan contributes NO required set — the
    plan determines the set (BR-MET-049). The rule reports `not_evaluated`
    with its reason on the batch summary; the row is NOT warned."""
    with tenant_ctx(brazos):
        seed_config()
        planned_meter(dana, brazos, None, asset_no="M-7999")

        batch = stage(dana, csv_body("M-7999,2026-08-03,100,total"))
        summary = services.validate_read_batch(dana, batch["id"])

        from apps.metering import completeness

        row = models.ReadImportRow.objects.get(batch_id=batch["id"], row_no=1)
        assert outcome_named(row, "plan_registers") is None  # nothing stored on the row
        gaps = {g["rule"]: g["reason"] for g in summary["unevaluated_rules"]}
        assert gaps.get("plan_registers") == completeness.REGISTERS_ABSENT_NO_PLAN


def test_us_met_018__a_window_with_no_stated_channel_is_an_absence_not_a_guess(brazos, dana):
    """BR-RAT-067: NULL channel is a REFUSAL, never a default. A plan whose
    window never stated its register cannot state a required set — reported,
    never ranked or guessed."""
    with tenant_ctx(brazos):
        seed_config()
        plan = plan_with_version(
            brazos, name="Legacy TOU", model="time_of_use", windows=("tou_on", None)
        )
        planned_meter(dana, brazos, plan, asset_no="M-7460")

        batch = stage(dana, csv_body("M-7460,2026-08-03,1200,total"))
        summary = services.validate_read_batch(dana, batch["id"])

        from apps.metering import completeness

        row = models.ReadImportRow.objects.get(batch_id=batch["id"], row_no=1)
        assert outcome_named(row, "plan_registers") is None
        gaps = {g["rule"]: g["reason"] for g in summary["unevaluated_rules"]}
        assert gaps.get("plan_registers") == completeness.REGISTERS_ABSENT_WINDOW_CHANNEL_UNSTATED


def test_us_met_018__resolver_is_derived_never_stored(brazos, dana):
    """The expected set is DERIVED on every ask (a stored expected-set would be
    a second source of truth): adding a window row changes the answer with no
    write to any metering table."""
    with tenant_ctx(brazos):
        seed_config()
        plan = plan_with_version(
            brazos, name="Growing TOU", model="time_of_use", windows=("tou_on", "tou_off")
        )
        unit, asset = planned_meter(dana, brazos, plan, asset_no="M-7462")

        from apps.metering import completeness

        resolver = completeness.PlanRegisterResolver()
        first = resolver.for_meter_row(
            unit_rate_plan_id=_plan_id_of_unit(unit["id"]),
            service_code="electric",
            service_date=date(2026, 8, 3),
            net_metering=False,
        )
        assert first.channels == ("total", "tou_on", "tou_off")

        from apps.rating import models as rating_models

        version = rating_models.TariffVersion.objects.get(
            tenant=brazos, tariff__name="Growing TOU — electric"
        )
        rating_models.TimeOfUseWindow.objects.create(
            tenant=brazos,
            tariff_version=version,
            label="Mid",
            day_type="weekday",
            start_time=time(12, 0),
            end_time=time(16, 0),
            unit_price=Decimal("0.20"),
            channel="tou_mid",
        )
        fresh = completeness.PlanRegisterResolver()  # a NEW ask — nothing was stored
        second = fresh.for_meter_row(
            unit_rate_plan_id=_plan_id_of_unit(unit["id"]),
            service_code="electric",
            service_date=date(2026, 8, 3),
            net_metering=False,
        )
        assert second.channels == ("total", "tou_on", "tou_mid", "tou_off")


def _plan_id_of_unit(unit_id):
    return models.Unit.objects.get(pk=unit_id).rate_plan_id


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-MET-018@EP-MET-03 (story + BR-MET-049/057 snapshot) · CR-038 W1
# generated: 2026-08-26 by the CR-038 W1 backend lane
# checklist: C✔ (this file) — the guard proved RED first; red output quoted in
#            the module docstring verbatim
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
