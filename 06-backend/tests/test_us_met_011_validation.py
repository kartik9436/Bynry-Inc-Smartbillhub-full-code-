# ── Trace ──────────────────────────────────────────────
# Story:    US-MET-011 (config-driven validation flag engine) · US-MET-008
#           (the same catalog over staged rows) · US-MET-017 (TOU sum-sanity)
#           Screens: S25 · S28 steps 3–4 · S29 · S64
# Rules:    BR-MET-020 (thresholds are tenant CONFIG; never hardcoded; missing
#           config FAILS SAFE) · BR-MET-021 (one primary status) · BR-MET-052
#           (negative usage = hard error never auto-fixed · retired meter =
#           error · vacant unit = warning · TOU Σ≈total ±1% · duplicate key
#           (meter,date,channel)) · BR-MET-061 (sum-sanity = WARNING) ·
#           BR-MET-025 (master/sub mismatch) · BR-MET-057 (cycle read-window) ·
#           BR-MET-019 (consumption + explicit unit) · OQ-009 closure + GT-14
#           (rollover) · OQ-002 closure (seeded thresholds) · OQ-004 closure
#           (no silent unit conversion)
# Journeys: J2 step 6 · J3 (exception handling)
# ───────────────────────────────────────────────────────
"""Rule-by-rule proof of the validation engine.

Two properties matter more than any individual flag and are asserted directly:

* **No threshold is hardcoded** (BR-MET-020) — the same reading is run through
  two tenants' configs and must flag differently, and through NO config and
  must skip rather than substitute.
* **Nothing is auto-fixed** (BR-MET-052) — a wrap computes its consumption and
  is flagged; every other negative returns no consumption at all and offers no
  repair.
"""

from datetime import date
from decimal import Decimal

import pytest

from apps.metering import models, services, validation

from tests.test_us_met_reads_helpers import *  # noqa: F401,F403
from tests.test_us_met_reads_helpers import (  # noqa: F401
    a_meter,
    at,
    commit_read,
    csv_body,
    seed_config,
    stage,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


def ctx(**kwargs) -> validation.ReadContext:
    """A ReadContext with the boring parts filled in — the engine is pure, so
    most rules can be proved without a database at all."""
    base = {
        "value": Decimal("1000"),
        "read_at": at("2026-08-03"),
        "channel": "total",
        "unit": "kWh",
        "multiplier": Decimal("1"),
        "register_digits": 5,
        "prior_value": Decimal("900"),
        "prior_read_at": at("2026-07-04"),
    }
    base.update(kwargs)
    return validation.ReadContext(**base)


def rules(outcomes):
    return {o.rule: o for o in outcomes}


class Config:
    """A stand-in for a `read_validation_settings` row — the engine reads
    attributes, so a test can vary ONE threshold without a migration."""

    def __init__(self, **overrides):
        defaults = dict(
            high_pct=Decimal("200"),
            high_abs_kwh=Decimal("50"),
            high_abs_kgal=Decimal("1"),
            low_pct=Decimal("25"),
            zero_scope="active_non_vacant",
            days_flag_min=25,
            days_flag_max=35,
            days_hard_min=20,
            days_hard_max=45,
            mismatch_default_pct=Decimal("3"),
            tou_sum_tolerance_pct=Decimal("1"),
            est_method="trailing_3_daily_avg",
            est_max_consecutive=2,
        )
        defaults.update(overrides)
        for name, value in defaults.items():
            setattr(self, name, value)


# ── consumption + rollover (BR-MET-019 · OQ-009 closure · GT-14) ────────────


def test_br_met_019__consumption_is_register_delta_times_multiplier():
    """US-MET-008 §4: M-7001 42,180 → 42,864 × 1 = 684.000000 kWh."""
    consumption, outcome = validation.compute_consumption(
        ctx(prior_value=Decimal("42180"), value=Decimal("42864"))
    )
    assert consumption == Decimal("684")
    assert outcome is None


def test_gt_14__a_full_register_wrap_auto_computes_rollover_and_flags_it():
    """GT-14 / OQ-009 CLOSED: 5-digit register, prior 99,800, current 240, ×1
    → (100,000 − 99,800) + 240 = 440. Span check: 99,560 > 50% of 100,000, so
    it is a wrap, NOT a negative read. Flagged for review, never silent."""
    consumption, outcome = validation.compute_consumption(
        ctx(prior_value=Decimal("99800"), value=Decimal("240"), register_digits=5)
    )
    assert consumption == Decimal("440")
    assert outcome.rule == "rollover" and outcome.severity == "warning"
    assert outcome.detail["register_span"] == "100000"
    assert outcome.detail["wrapped_delta"] == "440"


def test_br_met_052__any_other_negative_is_a_hard_error_that_is_never_fixed():
    """US-MET-008/TC-5 · US-MET-011/TC-11: M-7823 88,204 → 88,102, nowhere near
    a wrap. Hard error, NO consumption computed, NO auto-fix offered."""
    consumption, outcome = validation.compute_consumption(
        ctx(prior_value=Decimal("88204"), value=Decimal("88102"), register_digits=5)
    )
    assert consumption is None  # nothing invented for a value it cannot compute
    assert outcome.rule == "negative_usage" and outcome.severity == "error"
    assert outcome.detail["auto_fix"] is False
    assert outcome.detail["resolutions"] == ["investigate", "override", "reject"]


def test_rollover_needs_the_register_digits_it_is_told_about():
    """B4: "digits from asset spec". With no digits there is no span, so the
    engine cannot claim a wrap — it falls to the hard error rather than
    guessing a 5-, 6- or 9-digit register."""
    consumption, outcome = validation.compute_consumption(
        ctx(prior_value=Decimal("99800"), value=Decimal("240"), register_digits=None)
    )
    assert consumption is None and outcome.rule == "negative_usage"


# ── BR-MET-020: config or nothing ──────────────────────────────────────────


def test_us_met_011_tc9__with_no_config_row_threshold_rules_skip_and_say_so():
    """The fail-safe. NOT a fallback to the seeded numbers — those are seeded
    at provisioning, never compiled in."""
    _c, outcomes = validation.evaluate_row(ctx(trailing_actuals=[(Decimal("600"), 30)]), None)
    found = rules(outcomes)
    for rule in ("high", "low", "days_threshold"):
        assert found[rule].severity == "not_evaluated"
        assert found[rule].detail["reason"] == "validation_config_missing"
    assert {g["rule"] for g in validation.unevaluated(outcomes)} >= {"high", "low"}


def test_us_met_011_tc1__high_needs_the_ratio_and_the_absolute_floor():
    """OQ-002 closure: >200% of the trailing average AND a delta over the
    unit's absolute floor. Either one alone is not a flag."""
    history = [(Decimal("200"), 30), (Decimal("200"), 30), (Decimal("200"), 30)]
    over_both = validation._high_low_outcomes(
        ctx(trailing_actuals=history), Decimal("700"), Config()
    )
    assert rules(over_both)["high"].severity == "warning"
    assert Decimal(rules(over_both)["high"].detail["ratio_pct"]) == Decimal("350")
    assert rules(over_both)["high"].detail["threshold_pct"] == "200"

    # Ratio breached (250%) but the delta (300 − 200 = 100)… also over 50, so
    # push the floor above it: the AND-half now fails and there is no flag.
    ratio_only = validation._high_low_outcomes(
        ctx(trailing_actuals=history), Decimal("500"), Config(high_abs_kwh=Decimal("5000"))
    )
    assert rules(ratio_only)["high"].severity == "ok"


def test_us_met_011_tc7__a_changed_threshold_changes_the_verdict(brazos, marcus):
    """The proof no value is hardcoded: the SAME reading, two configs."""
    history = [(Decimal("200"), 30)]
    strict = validation._high_low_outcomes(
        ctx(trailing_actuals=history), Decimal("500"), Config(high_pct=Decimal("200"))
    )
    lenient = validation._high_low_outcomes(
        ctx(trailing_actuals=history), Decimal("500"), Config(high_pct=Decimal("300"))
    )
    assert rules(strict)["high"].severity == "warning"
    assert rules(lenient)["high"].severity == "ok"


def test_us_met_011_tc2__low_is_ratio_only_and_ignores_a_zero_read():
    history = [(Decimal("420"), 30)]
    low = validation._high_low_outcomes(ctx(trailing_actuals=history), Decimal("22"), Config())
    assert rules(low)["low"].severity == "warning"  # 5.2% < 25%
    zero = validation._high_low_outcomes(ctx(trailing_actuals=history), Decimal("0"), Config())
    assert rules(zero)["low"].severity == "ok"  # a zero read is the zero rule's


def test_oq_004__an_unconvertible_unit_reports_instead_of_half_firing():
    """OQ-004 CLOSED: no silent conversion. A raw-gallons register with no
    configured factor cannot be compared to the kgal floor, so `high` reports
    rather than flagging on the ratio alone."""
    outcomes = validation._high_low_outcomes(
        ctx(unit="gal", trailing_actuals=[(Decimal("8000"), 30)]), Decimal("26000"), Config()
    )
    high = rules(outcomes)["high"]
    assert high.severity == "not_evaluated"
    assert high.detail["reason"] == "absolute_floor_unavailable_for_unit"


def test_oq_004__a_configured_factor_expresses_the_floor_in_register_units():
    """With the tenant's factor present the floor converts — 1 kgal at 1,000
    gal/kgal is a 1,000-gal floor, applied in the register's own unit."""
    outcomes = validation._high_low_outcomes(
        ctx(
            unit="gal",
            billed_unit="kgal",
            conversion_factor=Decimal("1000"),
            trailing_actuals=[(Decimal("8400"), 30)],
        ),
        Decimal("26240"),
        Config(),
    )
    high = rules(outcomes)["high"]
    assert high.severity == "warning"
    assert high.detail["absolute_floor"] == "0.001"  # 1 kgal ÷ 1000 → per gal


def test_us_met_011_tc4__day_bounds_flag_outside_soft_and_hard(brazos):
    """Both day tiers FLAG — and since 2026-08-26 that is LAW, not merely the
    seeded shape: BR-MET-121 (PO, CR-038, verbatim *"reading is reading we
    store it as it comes"*) makes the days rule's import-time verdict WARNING
    AT MOST. This test asserted `warning` for the hard tier from the day it
    was written (2026-08-11, the engine never ERRORed here); the ruling
    ratifies it, and test_cr038_w2_mixed_cycle.py pins never-ERROR across the
    whole day range so drift goes RED. The bounds stay tenant/service config
    for flagging (BR-MET-020, unchanged)."""
    long_gap = validation._days_outcome(
        ctx(read_at=at("2026-08-25"), prior_read_at=at("2026-07-04")), Config()
    )
    assert long_gap.severity == "warning" and long_gap.detail["days"] == 52
    assert long_gap.detail["hard"] is True
    short = validation._days_outcome(
        ctx(read_at=at("2026-07-22"), prior_read_at=at("2026-07-04")), Config()
    )
    assert short.severity == "warning" and short.detail["days"] == 18
    normal = validation._days_outcome(
        ctx(read_at=at("2026-08-03"), prior_read_at=at("2026-07-04")), Config()
    )
    assert normal.severity == "ok" and normal.detail["days"] == 30


# ── BR-MET-052 catalog ─────────────────────────────────────────────────────


def test_us_met_011_tc12__a_read_on_a_retired_meter_errors(brazos, marcus):
    with tenant_ctx(brazos):
        seed_config()
        asset = a_meter(marcus, "M-7702")
        from apps.assets import models as asset_models

        asset_models.Asset.objects.filter(pk=asset["id"]).update(retire_date=date(2026, 6, 15))
        batch = stage(marcus, csv_body("M-7702,2026-08-03,1000,total,E,"))
        services.validate_read_batch(marcus, batch["id"])
        row = models.ReadImportRow.objects.get(batch_id=batch["id"], row_no=1)
    retired = [o for o in row.rule_outcomes if o["rule"] == "retired_meter"][0]
    assert retired["severity"] == "error"
    assert retired["detail"]["retired_on"] == "2026-06-15"
    assert row.severity == "error"


def test_us_met_011_tc3__a_read_on_a_vacant_unit_warns(brazos, marcus):
    """BR-MET-052 + BR-MET-036: occupancy is DERIVED from the active account.
    No account ⇒ vacant ⇒ warning, postable only via an explicit accept."""
    with tenant_ctx(brazos):
        seed_config()
        a_meter(marcus)
        batch = stage(marcus, csv_body("M-7001,2026-08-03,42864,total,E,"))
        services.validate_read_batch(marcus, batch["id"])
        row = models.ReadImportRow.objects.get(batch_id=batch["id"], row_no=1)
    vacant = [o for o in row.rule_outcomes if o["rule"] == "vacant_unit"][0]
    assert vacant["severity"] == "warning" and vacant["detail"]["occupied"] is False


def test_us_met_011_tc3__a_zero_read_flags_zero_on_an_occupied_unit():
    zero = validation._zero_outcome(ctx(unit_occupied=True), Decimal("0"), Config())
    assert zero.severity == "warning"
    # On a VACANT unit the zero is the vacant_unit rule's business, not zero's.
    assert validation._zero_outcome(ctx(unit_occupied=False), Decimal("0"), Config()) is None
    # And with the scope switched off, nothing fires at all (config over code).
    assert (
        validation._zero_outcome(ctx(unit_occupied=True), Decimal("0"), Config(zero_scope="off"))
        is None
    )


def test_us_met_011_tc13__tou_sum_sanity_flags_a_group_over_the_tolerance():
    """US-MET-008/TC-11: windows 210 + 118 + 96 = 424 vs total 430 →
    |430 − 424| ÷ 430 = 1.395…% > 1% → flagged. BR-MET-061: WARNING."""
    outcome = validation.tou_sum_sanity(
        {
            "tou_on": Decimal("210"),
            "tou_mid": Decimal("118"),
            "tou_off": Decimal("96"),
        },
        Decimal("430"),
        Config(),
    )
    assert outcome.severity == "warning"
    assert outcome.detail["window_sum"] == "424" and outcome.detail["total"] == "430"
    assert outcome.detail["deviation_pct"].startswith("1.39")
    assert outcome.detail["tolerance_pct"] == "1"


def test_us_met_017_tc1__a_consistent_tou_group_passes():
    outcome = validation.tou_sum_sanity(
        {"tou_on": Decimal("210"), "tou_mid": Decimal("118"), "tou_off": Decimal("96")},
        Decimal("424"),
        Config(),
    )
    assert outcome.severity == "ok" and outcome.detail["deviation_pct"] == "0"


def test_us_met_017_tc6__a_partial_tou_group_is_not_evaluated_not_invented():
    """Nothing is invented for the blank channels — the check simply cannot be
    computed, and says so."""
    outcome = validation.tou_sum_sanity({"tou_on": Decimal("210")}, None, Config())
    assert outcome.severity == "not_evaluated"
    assert set(outcome.detail["missing_channels"]) == {"tou_mid", "tou_off", "total"}


def test_us_met_011_tc6__master_sub_mismatch_uses_the_configured_tolerance():
    """BR-MET-025: master 12,400 vs Σ subs 11,900 = 4.03% gap > 3% → flagged."""
    over = validation._mismatch_outcome(
        ctx(submeter_consumption_sum=Decimal("11900")), Decimal("12400"), Config()
    )
    assert over.severity == "warning"
    assert over.detail["tolerance_pct"] == "3"
    # The per-master tolerance on the asset beats the tenant default.
    within = validation._mismatch_outcome(
        ctx(submeter_consumption_sum=Decimal("11900"), loss_tolerance_pct=Decimal("5")),
        Decimal("12400"),
        Config(),
    )
    assert within.severity == "ok"


def test_br_met_057__a_read_outside_the_cycle_window_warns():
    outside = validation._window_outcome(
        ctx(
            cycle_window_start=date(2026, 8, 1),
            cycle_window_end=date(2026, 8, 5),
            read_at=at("2026-08-09"),
        )
    )
    assert outside.severity == "warning"
    inside = validation._window_outcome(
        ctx(
            cycle_window_start=date(2026, 8, 1),
            cycle_window_end=date(2026, 8, 5),
            read_at=at("2026-08-03"),
        )
    )
    assert inside.severity == "ok"


def test_br_met_020__the_unratified_factor_rule_is_reported_never_guessed():
    """factor_flag is in BR-MET-021's vocabulary but NO ratified threshold
    exists for it (B2 r5 #15 has no column; US-MET-011 §5 has no row). The
    engine reports it every run rather than passing it as a silent green."""
    _c, outcomes = validation.evaluate_row(ctx(), Config())
    factor = rules(outcomes)["factor_flag"]
    assert factor.severity == "not_evaluated"
    assert factor.detail["reason"] == "threshold_not_ratified"
    assert "factor_flag" in {g["rule"] for g in validation.unevaluated(outcomes)}


def test_br_met_021__a_read_carries_exactly_one_primary_status():
    """Errors outrank warnings; `not_evaluated` is never a status."""
    _c, outcomes = validation.evaluate_row(
        ctx(prior_value=Decimal("88204"), value=Decimal("88102")), Config()
    )
    assert validation.primary_status(outcomes) == "negative_usage"
    assert validation.worst_severity(outcomes) == "error"
    clean = validation.evaluate_row(ctx(unit_occupied=True), Config())[1]
    assert validation.primary_status(clean) == "ok"


def test_claude_rule_3__a_measuring_asset_with_no_uom_cannot_post():
    """CLAUDE.md rule 3 has no "assume kWh" branch."""
    _c, outcomes = validation.evaluate_row(ctx(unit=None), Config())
    assert rules(outcomes)["unit_missing"].severity == "error"


def test_us_met_011_tc10__two_tenants_evaluate_the_same_read_differently(
    brazos, lonestar, marcus, erin
):
    """The isolation half of BR-MET-020: each tenant's reads evaluate against
    its OWN config row, and neither can see the other's."""
    with tenant_ctx(brazos):
        seed_config(low_pct=Decimal("25"))
        assert services._read_config().low_pct == Decimal("25")
    with tenant_ctx(lonestar):
        seed_config(low_pct=Decimal("40"))
        assert services._read_config().low_pct == Decimal("40")
        assert models.ReadValidationSettings.objects.filter(tenant=lonestar).count() == 1
    with tenant_ctx(brazos):
        assert services._read_config().low_pct == Decimal("25")  # unchanged by the neighbour
