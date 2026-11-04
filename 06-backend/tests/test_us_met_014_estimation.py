# ── Trace ──────────────────────────────────────────────
# Story:    US-MET-014 (auto-estimate missing reads — trailing-3 daily average,
#           max 2 consecutive, PER CHANNEL) · US-MET-015 (true-up at the next
#           actual read + override/skip)
#           Screens: S25 · S28 step 4 · S29 · S31.2
# Rules:    BR-MET-026 (daily_avg × period days, actuals only, ≥1 actual) ·
#           BR-MET-027 (consecutive cap from CONFIG, field visit beyond it) ·
#           BR-MET-028 (labeled, status `estimated`, NO register value) ·
#           BR-MET-029 (true-up by register arithmetic) · BR-MET-058 (PER
#           CHANNEL — histories never mix) · BR-MET-062 (demand is NEVER
#           estimated) · BR-MET-020 (config over constant)
# Golden:   GT-9 — 618.000000 kWh estimated; next actual implies 700.000000
#           (a +82 correction). Expected values SIGNED via the OQ-003 closure.
# Journeys: J3 (exception handling)
# ───────────────────────────────────────────────────────
"""Estimation and true-up — QUANTITIES ONLY.

GT-9's two figures are asserted to the digit because they are signed law. No
test here reads a rate or asserts an amount: pricing the estimate is rating's
half of GT-9 and is deliberately absent from this lane.
"""

from decimal import Decimal

import pytest

from apps.metering import estimation, models, services

from tests.test_us_met_reads_helpers import *  # noqa: F401,F403
from tests.test_us_met_reads_helpers import (  # noqa: F401
    a_meter,
    accept_warnings,
    at,
    commit_read,
    csv_body,
    seed_config,
    stage,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


class Config:
    def __init__(self, **overrides):
        defaults = dict(est_method="trailing_3_daily_avg", est_max_consecutive=2)
        defaults.update(overrides)
        for name, value in defaults.items():
            setattr(self, name, value)


GT9_HISTORY = [(Decimal("624"), 30), (Decimal("618"), 30), (Decimal("612"), 30)]


# ── BR-MET-026 / GT-9 ──────────────────────────────────────────────────────


def test_gt_9__the_trailing_3_daily_average_estimate_to_the_digit():
    """GT-9 / US-MET-014 TC-1: 612 + 618 + 624 = 1,854 kWh over 90 days →
    20.600000 kWh/day → × 30 days = 618.000000 kWh."""
    result = estimation.estimate(
        estimation.EstimationInput(
            channel="total", unit="kWh", days_in_period=30, trailing_actuals=GT9_HISTORY
        ),
        Config(),
    )
    assert result.estimated is True
    assert result.daily_average == Decimal("20.6")
    assert result.consumption == Decimal("618.0")
    assert result.unit == "kWh"  # rule 3: a quantity never travels bare
    assert result.method == "trailing_3_avg" and result.consecutive_no == 1
    assert result.detail["sum_consumption"] == "1854" and result.detail["sum_days"] == 90


def test_br_met_026__only_the_last_three_actuals_feed_the_average():
    """ "Trailing-3" is the method's own name — a fourth read must not move it."""
    with_four = estimation.estimate(
        estimation.EstimationInput(
            channel="total",
            unit="kWh",
            days_in_period=30,
            trailing_actuals=GT9_HISTORY + [(Decimal("9999"), 30)],
        ),
        Config(),
    )
    assert with_four.consumption == Decimal("618.0")


def test_br_met_026__short_history_uses_what_exists():
    result = estimation.estimate(
        estimation.EstimationInput(
            channel="total",
            unit="kWh",
            days_in_period=30,
            trailing_actuals=[(Decimal("600"), 30)],
        ),
        Config(),
    )
    assert result.estimated is True and result.consumption == Decimal("600")


def test_us_met_014_tc5__no_history_means_no_estimate_and_a_field_visit():
    result = estimation.estimate(
        estimation.EstimationInput(
            channel="total", unit="kWh", days_in_period=30, trailing_actuals=[]
        ),
        Config(),
    )
    assert result.estimated is False
    assert result.reason == "no_history"
    assert result.detail["forced_disposition"] == "field_visit"
    assert result.consumption is None  # nothing invented


def test_us_met_014_tc4_tc6__the_consecutive_cap_comes_from_config_never_a_constant():
    """BR-MET-027: Brazos Bend keeps the seeded 2 and is refused a third;
    Lone Star Ridge sets 3 and is allowed one. Same input, two verdicts."""
    spec = estimation.EstimationInput(
        channel="total",
        unit="kWh",
        days_in_period=30,
        trailing_actuals=GT9_HISTORY,
        consecutive_estimates=2,
    )
    capped = estimation.estimate(spec, Config(est_max_consecutive=2))
    assert capped.estimated is False
    assert capped.reason == "consecutive_estimate_cap_reached"
    assert capped.detail["forced_disposition"] == "field_visit"
    allowed = estimation.estimate(spec, Config(est_max_consecutive=3))
    assert allowed.estimated is True and allowed.consecutive_no == 3


def test_br_met_062__a_demand_channel_is_never_estimated():
    """PO OQ-067: a peak drives kW dollars, so an estimated peak is a dispute.
    Refused even with a full, healthy history."""
    result = estimation.estimate(
        estimation.EstimationInput(
            channel="demand", unit="kW", days_in_period=30, trailing_actuals=GT9_HISTORY
        ),
        Config(),
    )
    assert result.estimated is False and result.reason == "demand_never_estimated"


def test_br_met_020__with_no_config_there_is_no_estimate():
    result = estimation.estimate(
        estimation.EstimationInput(
            channel="total", unit="kWh", days_in_period=30, trailing_actuals=GT9_HISTORY
        ),
        None,
    )
    assert result.estimated is False and result.reason == "validation_config_missing"


def test_an_unimplemented_method_refuses_rather_than_improvising():
    """Only `trailing_3_daily_avg` is SIGNED. A tenant naming another method
    gets a refusal, not an invented arithmetic."""
    result = estimation.estimate(
        estimation.EstimationInput(
            channel="total", unit="kWh", days_in_period=30, trailing_actuals=GT9_HISTORY
        ),
        Config(est_method="seasonal_regression"),
    )
    assert result.estimated is False
    assert result.reason == "estimation_method_not_implemented"


# ── BR-MET-058: per channel ────────────────────────────────────────────────


def test_us_met_014_tc9__each_channel_estimates_from_its_own_history():
    """US-MET-014/TC-9: tou_on 630 ÷ 90 × 30 = 210.000000 · tou_mid 354 → 118 ·
    tou_off 288 → 96 · total 1,272 → 424. Σ windows = the total estimate."""
    histories = {
        "tou_on": [(Decimal("210"), 30), (Decimal("216"), 30), (Decimal("204"), 30)],
        "tou_mid": [(Decimal("118"), 30), (Decimal("121"), 30), (Decimal("115"), 30)],
        "tou_off": [(Decimal("96"), 30), (Decimal("99"), 30), (Decimal("93"), 30)],
        "total": [(Decimal("424"), 30), (Decimal("436"), 30), (Decimal("412"), 30)],
    }
    results = {
        channel: estimation.estimate(
            estimation.EstimationInput(
                channel=channel, unit="kWh", days_in_period=30, trailing_actuals=history
            ),
            Config(),
        )
        for channel, history in histories.items()
    }
    assert results["tou_on"].consumption == Decimal("210")
    assert results["tou_mid"].consumption == Decimal("118")
    assert results["tou_off"].consumption == Decimal("96")
    assert results["total"].consumption == Decimal("424")
    windows = sum(results[c].consumption for c in ("tou_on", "tou_mid", "tou_off"))
    assert windows == results["total"].consumption  # internally consistent


# ── BR-MET-029: true-up ────────────────────────────────────────────────────


def test_gt_9__true_up_is_register_arithmetic_minus_the_estimates():
    """GT-9 / US-MET-015 TC-1: (44,182 − 42,864) × 1 = 1,318.000000; minus the
    618.000000 estimated → 700.000000 kWh on the next bill (a +82 correction)."""
    result = estimation.true_up(
        estimation.TrueUpInput(
            channel="total",
            unit="kWh",
            actual_register=Decimal("44182"),
            last_actual_register=Decimal("42864"),
            multiplier=Decimal("1"),
            estimated_consumptions=[Decimal("618")],
            estimated_read_ids=["est-1"],
        )
    )
    assert result.applies is True
    assert result.register_delta == Decimal("1318.000000")
    assert result.quantity == Decimal("700")
    assert result.unit == "kWh"
    assert result.corrects_read_ids == ["est-1"]
    assert result.quantity - Decimal("618") == Decimal("82")  # GT-9's stated correction


def test_us_met_015_tc3__an_over_estimate_trues_negative_and_is_not_clamped():
    """Clamping would keep an over-billed customer over-billed. The negative
    quantity flows as a credit — pricing it is rating's job."""
    result = estimation.true_up(
        estimation.TrueUpInput(
            channel="total",
            unit="kWh",
            actual_register=Decimal("1100"),
            last_actual_register=Decimal("0"),
            multiplier=Decimal("1"),
            estimated_consumptions=[Decimal("1236")],
        )
    )
    assert result.quantity == Decimal("-136")


def test_us_met_015_tc7__with_no_standing_estimates_nothing_is_invented():
    result = estimation.true_up(
        estimation.TrueUpInput(
            channel="total",
            unit="kWh",
            actual_register=Decimal("44182"),
            last_actual_register=Decimal("42864"),
            multiplier=Decimal("1"),
            estimated_consumptions=[],
        )
    )
    assert result.applies is False and result.quantity is None


def test_us_met_015_tc10__true_up_stays_inside_one_channel_lineage():
    """M-7450 tou_on: (13,864 − 13,210) × 1 − 210 = 444.000000 kWh — computed
    from tou_on registers and tou_on estimates only (BR-MET-058)."""
    result = estimation.true_up(
        estimation.TrueUpInput(
            channel="tou_on",
            unit="kWh",
            actual_register=Decimal("13864"),
            last_actual_register=Decimal("13210"),
            multiplier=Decimal("1"),
            estimated_consumptions=[Decimal("210")],
        )
    )
    assert result.quantity == Decimal("444")


# ── the persisted half ─────────────────────────────────────────────────────


def test_us_met_014__an_estimated_read_is_stored_labeled_and_register_free(
    brazos, marcus, audit_rows
):
    """BR-MET-028: status `estimated`, method + consecutive number recorded, a
    source distinct from actuals, and NO register `current_value`."""
    with tenant_ctx(brazos):
        seed_config()
        asset = a_meter(marcus)
        commit_read(
            marcus, asset["id"], day="2026-05-05", value=41000, consumption=612, days_since_prior=30
        )
        commit_read(
            marcus, asset["id"], day="2026-06-04", value=41618, consumption=618, days_since_prior=30
        )
        commit_read(
            marcus, asset["id"], day="2026-07-04", value=42242, consumption=624, days_since_prior=30
        )
        result = services.estimate_missing_read(
            marcus,
            {
                "meter_no": "M-7001",
                "channel": "total",
                "read_at": "2026-08-03",
                "days_in_period": 30,
            },
        )
        read = models.MeterRead.objects.get(id=result["id"])
    assert result["estimated"] is True
    assert read.consumption == Decimal("618.000000")  # GT-9, persisted
    assert read.unit == "kWh" and read.status == "estimated"
    assert read.current_value is None  # BR-MET-028 — an estimate has no register
    assert read.estimation_method == "trailing_3_avg" and read.consecutive_estimate_no == 1
    assert read.source == "estimated"
    assert "read.estimated" in [r["action"] for r in audit_rows]


def test_us_met_014__estimates_never_compound_into_the_next_average(brazos, marcus):
    """BR-MET-026 "actuals only": the 618 estimate is EXCLUDED from the average
    that produces the second estimate (US-MET-014/TC-3)."""
    with tenant_ctx(brazos):
        seed_config()
        asset = a_meter(marcus)
        for day, value, consumption in (
            ("2026-05-05", 41000, 612),
            ("2026-06-04", 41618, 618),
            ("2026-07-04", 42242, 624),
        ):
            commit_read(
                marcus,
                asset["id"],
                day=day,
                value=value,
                consumption=consumption,
                days_since_prior=30,
            )
        services.estimate_missing_read(
            marcus, {"meter_no": "M-7001", "read_at": "2026-08-03", "days_in_period": 30}
        )
        second = services.estimate_missing_read(
            marcus, {"meter_no": "M-7001", "read_at": "2026-09-02", "days_in_period": 30}
        )
    assert second["estimated"] is True
    assert second["consumption"] == "618.000000"  # still the three ACTUALS
    assert second["consecutive_estimate_no"] == 2


def test_us_met_014_tc4__a_third_consecutive_estimate_is_refused(brazos, marcus):
    with tenant_ctx(brazos):
        seed_config()
        asset = a_meter(marcus)
        commit_read(
            marcus, asset["id"], day="2026-07-04", value=42242, consumption=624, days_since_prior=30
        )
        for day in ("2026-08-03", "2026-09-02"):
            services.estimate_missing_read(
                marcus, {"meter_no": "M-7001", "read_at": day, "days_in_period": 30}
            )
        third = services.estimate_missing_read(
            marcus, {"meter_no": "M-7001", "read_at": "2026-10-02", "days_in_period": 30}
        )
    assert third["estimated"] is False
    assert third["reason"] == "consecutive_estimate_cap_reached"
    assert third["detail"]["forced_disposition"] == "field_visit"


def test_gt_9__the_next_actual_read_trues_up_at_commit(brazos, marcus):
    """US-MET-015 §1: true-up runs automatically inside the read commit. The
    posted read's consumption IS the trued quantity — 700.000000 kWh."""
    with tenant_ctx(brazos):
        seed_config()
        asset = a_meter(marcus, register_digits=6)
        # EP-MET-05 §4 verbatim: May 5→Jun 4 = 612 · Jun 4→Jul 4 = 618 ·
        # Jul 4→Aug 3 = 624 (30 days each); last ACTUAL register 42,864 on
        # Aug 3, which is the baseline the true-up measures from.
        for day, value, consumption in (
            ("2026-05-05", 41010, None),
            ("2026-06-04", 41622, 612),
            ("2026-07-04", 42240, 618),
            ("2026-08-03", 42864, 624),
        ):
            commit_read(
                marcus,
                asset["id"],
                day=day,
                value=value,
                consumption=consumption,
                days_since_prior=30,
            )
        estimate = services.estimate_missing_read(
            marcus, {"meter_no": "M-7001", "read_at": "2026-09-02", "days_in_period": 30}
        )
        assert estimate["consumption"] == "618.000000"

        batch = stage(marcus, csv_body("M-7001,2026-10-02,44182,total,E,"))
        services.validate_read_batch(marcus, batch["id"])
        accept_warnings(marcus, batch["id"])
        services.commit_read_batch(marcus, batch["id"], {"certified": True})
        actual = models.MeterRead.objects.get(asset_id=asset["id"], read_at=at("2026-10-02"))
    # (44,182 − 42,864) × 1 = 1,318 − 618 estimated = 700.000000 kWh (GT-9).
    assert actual.consumption == Decimal("700.000000")
    assert actual.unit == "kWh"
    assert actual.trues_up_read_ids == [estimate["id"]]
    true_up = [o for o in actual.rule_outcomes if o["rule"] == "true_up"][0]
    assert Decimal(true_up["detail"]["register_delta"]) == Decimal("1318")
    assert Decimal(true_up["detail"]["estimated_total"]) == Decimal("618")


def test_us_met_014_tc8__estimation_history_never_crosses_tenants(brazos, lonestar, marcus, erin):
    """The same meter number in both tenants with different histories: each
    average is computed from its OWN reads only."""
    with tenant_ctx(brazos):
        seed_config()
        bb = a_meter(marcus, "M-7001", service="water", uom="gal")
        commit_read(
            marcus,
            bb["id"],
            day="2026-07-04",
            value=1000,
            consumption=Decimal("600"),
            unit="gal",
            days_since_prior=30,
        )
    with tenant_ctx(lonestar):
        seed_config()
        lsr = a_meter(erin, "M-7001", address="9 Ridge Rd", service="water", uom="gal")
        commit_read(
            erin,
            lsr["id"],
            day="2026-07-04",
            value=5000,
            consumption=Decimal("90"),
            unit="gal",
            days_since_prior=30,
        )
        result = services.estimate_missing_read(
            erin, {"meter_no": "M-7001", "read_at": "2026-08-03", "days_in_period": 30}
        )
    assert result["consumption"] == "90.000000"  # Lone Star Ridge's own history
    assert result["unit"] == "gal"
