# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-020 (EP-RBS-05) — CR-075 wave S, runbook 5.
# Rules:    BR-RBS-002 · BR-RBS-009 · BR-RBS-012 · BR-RBS-019 · BR-RBS-020 ·
#           BR-RBS-021 · BR-RBS-023 · BR-RBS-035 · RBR-09 (the meter's OWN
#           history) · CLAUDE.md hard rules 2 and 3 · B14 rules 31, 32, 33
# Tests:    this file. The PostgreSQL half is tests/test_rbs_check_runbooks_pg.py.
# Impacts:  apps/runbooks/definitions/abnormal_readings.py
# ───────────────────────────────────────────────────────
"""Runbook 5, against the rules rather than against itself.

⚠ **THE SEEDED UTILITY CANNOT EXERCISE FOUR OF THE SIX PATTERNS.** Its meters
carry four reads each over three months, and 103 of its 107 meters are sample
records the runbook's guard excludes — so a flat line, a zero streak, an
over-estimated meter and an out-of-season month have no real rows at all. They
live here. What the real database DOES produce is two spikes and a rollover over
four meters and 24 reads, and both numbers are quoted in the lane report;
neither is quoted alone.
"""

import datetime as dt
from decimal import Decimal

import pytest

from apps.runbooks.contract import BLOCK_TYPES
from apps.runbooks.definitions import abnormal_readings as ar
from apps.runbooks.engine import executor

pytestmark = pytest.mark.django_db

TODAY = dt.date(2026, 9, 7)


def _read(on, consumption, register=None, estimated=False, unit="gal", account_id="acc-1"):
    return {
        "read_id": f"r-{on}",
        "on": on,
        "channel": "total",
        "consumption": None if consumption is None else str(consumption),
        "current_value": None if register is None else str(register),
        "multiplier": "1.000000",
        "unit": unit,
        "estimated": estimated,
        "account_id": account_id,
        "is_sample": False,
    }


def _meter(asset_id="m1", asset_no="WM-01128", reads=None, is_sample=False, service="water"):
    return {
        "asset_id": asset_id,
        "asset_no": asset_no,
        "service": service,
        "unit_id": "u1",
        "premises_id": "p1",
        "is_sample": is_sample,
        "reads": list(reads or []),
    }


def _year(*quantities, estimated_from=None, unit="gal"):
    """Twelve monthly periods with the quantities given, oldest first."""
    reads = []
    for index, quantity in enumerate(quantities, start=1):
        reads.append(
            _read(
                f"2026-{index:02d}-01",
                quantity,
                register=1000 + index * 100,
                estimated=bool(estimated_from is not None and index > estimated_from),
                unit=unit,
            )
        )
    return reads


@pytest.fixture
def seams(monkeypatch):
    """Fixed answers for the four reads runbook 5 makes."""
    state = {
        "history": [_meter(reads=_year(*([500] * 6)))],
        "bills": [
            {
                "bill_id": "b1",
                "period_end": "2026-08-31",
                "currency": "USD",
                "lines": [
                    {
                        "kind": "usage",
                        "service": "water",
                        "amount": "50.0000",
                        "quantity": "500.0000",
                        "unit": "gal",
                        "description": "Water",
                    }
                ],
            }
        ],
        "facts": {"account_no": "A-1", "label": "Riverside Apts", "unit_id": "u1"},
        "occupants": {"u1": {"id": "acc-1", "account_no": "A-1"}},
        "currency": "USD",
    }
    monkeypatch.setattr(
        ar.metering_seam, "meter_read_history", lambda **kwargs: list(state["history"])
    )
    monkeypatch.setattr(
        ar.billing_seam,
        "issued_bills_for_account",
        lambda account_id, limit=14: list(state["bills"]),
    )
    monkeypatch.setattr(ar.customers_seam, "account_facts", lambda account_id: state["facts"])
    monkeypatch.setattr(
        ar.customers_seam, "accounts_for_units", lambda unit_ids: dict(state["occupants"])
    )
    monkeypatch.setattr(ar.tenancy_seam, "today", lambda: TODAY)
    monkeypatch.setattr(ar.tenancy_seam, "currency", lambda: state["currency"])
    return state


def _run(params=None):
    definition = ar.RUNBOOK
    ctx = executor.build_context(
        definition,
        tenant_id="t",
        params={
            "service": "water",
            "window_months": 12,
            "spike_above_own_median": "300.000000",
            "drop_below_own_median": "20.000000",
            "zero_reads_in_a_row": 3,
            "identical_reads_in_a_row": 4,
            "estimated_more_than": 4,
            "ignore_usage_under": 200,
            **(params or {}),
        },
    )
    return executor.execute(definition, ctx=ctx)


def _blocks(result):
    return {block["block"]: block["payload"] for block in result.report}


def _checked(result, step):
    return (result.set_results.get(step) or {}).get("checked") or {}


def _row(result, index=0):
    return _blocks(result)["records"]["rows"][index]["cells"]


# ── the declaration ───────────────────────────────────────────────────────


def test_it_is_a_check_whose_unit_of_work_is_the_meter(seams):
    """`BR-RBS-019` — 2,842 meters with 31,904 reads is one record per METER."""
    assert ar.RUNBOOK.is_check
    assert ar.RUNBOOK.ports == ()
    assert ar.RUNBOOK.subject_type == "meter"
    assert len(ar.RUNBOOK.steps) == 8
    assert [one.mode for one in ar.RUNBOOK.steps].count("per_record") == 1


# ── the guard ─────────────────────────────────────────────────────────────


def test_a_sample_meter_is_guarded_counted_and_seen_by_no_step(seams):
    """`BR-RBS-012` / `BR-RBS-035` — pinned, excluded, and VISIBLE as a count."""
    seams["history"] = [
        _meter("m1", "WM-1", _year(*([500] * 6))),
        _meter("m2", "WM-2", _year(*([500] * 6)), is_sample=True),
    ]
    result = _run()
    assert len(result.subjects) == 2
    assert [one.subject_id for one in result.guarded] == ["m2"]
    assert result.counts[executor.OUTCOME_SKIPPED] == 1
    assert _checked(result, ar.STEP_YEAR)["meters"] == 1


# ── the six patterns ──────────────────────────────────────────────────────


def test_a_spike_is_measured_against_the_meters_own_median(seams):
    """`RBR-09` — a restaurant and a retired couple are both normal."""
    seams["history"] = [_meter(reads=_year(400, 500, 600, 500, 27540, 400))]
    result = _run()
    assert result.records[0].outcome == ar.PATTERN_SPIKE
    assert _checked(result, ar.STEP_SPIKES)["meters_spiking"] == 1


def test_a_meter_with_no_median_is_unjudgeable_and_never_a_spike(seams):
    """A first build that read `None` as `0` would flag every new meter."""
    seams["history"] = [_meter(reads=[_read("2026-01-01", None)])]
    result = _run()
    assert _checked(result, ar.STEP_SPIKES)["meters_with_no_median_to_judge"] == 1
    assert _checked(result, ar.STEP_SPIKES)["meters_spiking"] == 0


def test_usage_under_the_floor_never_produces_a_spectacular_percentage(seams):
    """The card's own reason for the floor: a vacant unit at 40 gallons."""
    seams["history"] = [_meter(reads=_year(10, 12, 11, 10, 190, 10))]
    assert _checked(_run(), ar.STEP_SPIKES)["meters_spiking"] == 0


def test_three_zero_reads_in_a_row_are_a_zero_streak(seams):
    seams["history"] = [_meter(reads=_year(500, 500, 0, 0, 0, 500))]
    result = _run()
    assert result.records[0].outcome == ar.PATTERN_ZERO
    assert result.records[0].reason == "3 zero reads in a row."


def test_four_identical_reads_are_a_flat_line_and_zeros_are_not(seams):
    """A stuck meter still reports a number; a vacant house does not, and the
    two carry different fixes."""
    seams["history"] = [_meter(reads=_year(800, 800, 800, 800))]
    result = _run()
    assert result.records[0].outcome == ar.PATTERN_FLAT
    assert result.records[0].fix_route == "assets"
    assert result.records[0].data["fix_label"] == "Order a test →"

    seams["history"] = [_meter(reads=_year(0, 0, 0, 0))]
    assert _run().records[0].outcome == ar.PATTERN_ZERO


def test_a_rollover_is_read_off_the_register_and_not_off_the_consumption(seams):
    """Metering's estimation can leave consumption positive across a rollover."""
    seams["history"] = [
        _meter(
            reads=[
                _read("2026-01-01", 500, register=9900),
                _read("2026-02-01", 500, register=120),
            ]
        )
    ]
    result = _run()
    assert result.records[0].outcome == ar.PATTERN_ROLLOVER
    assert _checked(result, ar.STEP_ROLLOVER)["compared_on"] == (
        "the register reading, never the consumption"
    )


def test_more_than_four_estimated_of_twelve_is_over_estimated(seams):
    seams["history"] = [_meter(reads=_year(*([500] * 12), estimated_from=6))]
    result = _run()
    assert _checked(result, ar.STEP_ESTIMATED)["meters_over_estimated"] == 1
    assert result.records[0].outcome in (ar.PATTERN_FLAT, ar.PATTERN_ESTIMATED)


def test_out_of_season_says_how_many_meters_could_be_compared(seams):
    """⚠ With a twelve-month window there is ONE same-month sample, and one
    sample is not a history. Reporting *none out of season* over that is
    hard-won law 7's *zero over a scope it silently excludes*."""
    seams["history"] = [_meter(reads=_year(*([500] * 12)))]
    checked = _checked(_run(), ar.STEP_SEASON)
    assert checked["meters_with_a_same_month_comparison"] == 0
    assert checked["window_gives_one_sample_per_month"] is True


def test_a_meter_matching_two_patterns_carries_one_and_names_the_rest(seams):
    """The table is one row per meter; the others travel in `meta`."""
    seams["history"] = [
        _meter(reads=[_read("2026-01-01", 0, register=900)] + _year(0, 0, 0)[:3])
    ]
    result = _run()
    row = _blocks(result)["records"]["rows"][0]
    assert row["meta"]["pattern"] in {ar.PATTERN_ZERO, ar.PATTERN_ROLLOVER}
    assert row["meta"]["also_matched"]


# ── the money ─────────────────────────────────────────────────────────────


def test_revenue_at_risk_is_the_missing_units_at_what_the_account_last_paid(seams):
    """500 gal a month × 4 flat months × $0.10 a gallon = $200.0000."""
    seams["history"] = [_meter(reads=_year(500, 500, 500, 500))]
    result = _run()
    assert Decimal(result.records[0].data["price_per_unit"]) == Decimal("0.1000")
    assert Decimal(result.records[0].data["at_risk"]) == Decimal("200.0000")
    assert _row(result)["at_risk"] == {
        "kind": "money",
        "amount": "200.0000",
        "currency": "USD",
    }


def test_a_meter_whose_account_never_billed_reads_an_em_dash_and_not_zero(seams):
    """⚠ An unknown is not a zero, and a zero sorts to the bottom of a list
    ranked by money — which hides the meter a clerk should see first."""
    seams["bills"] = []
    seams["history"] = [_meter(reads=_year(500, 500, 500, 500))]
    result = _run()
    assert result.records[0].data["at_risk"] is None
    assert _row(result)["at_risk"] == {"kind": "text", "text": "—"}


def test_a_rollover_and_an_over_estimated_meter_carry_no_money(seams):
    """`RB-105`'s own table: *$0.00* against both."""
    seams["history"] = [
        _meter(
            reads=[
                _read("2026-01-01", 500, register=9900),
                _read("2026-02-01", 500, register=120),
            ]
        )
    ]
    assert _run().records[0].data["at_risk"] is None


def test_the_money_tile_reads_an_em_dash_when_nothing_could_be_priced(seams):
    seams["bills"] = []
    seams["history"] = [_meter(reads=_year(500, 500, 500, 500))]
    tile = next(one for one in _blocks(_run())["kpis"]["tiles"] if one["id"] == "at_risk")
    assert tile["value"] == {"kind": "text", "text": "—"}
    assert tile["detail"] == "1 of 1 could not be priced"


def test_the_money_tile_declares_priced_and_never_posting(seams):
    """`DEF-RBS-4350` — this money was never posted anywhere."""
    tile = next(one for one in _blocks(_run())["kpis"]["tiles"] if one["id"] == "at_risk")
    assert tile["basis"] == "priced"


# ── the sparkline ─────────────────────────────────────────────────────────


def test_a_period_with_no_reading_is_left_out_rather_than_plotted_as_zero(seams):
    """⚠ **THE FIRST BUILD PLOTTED EVERY GAP AS `0.0`.** A meter's first read has
    no prior and therefore no consumption, so every sparkline in the fleet began
    with a dive to the floor — a shape a clerk reads as *it stopped*."""
    seams["history"] = [
        _meter(reads=[_read("2026-01-01", None, register=100)] + _year(500, 27540, 500))
    ]
    row = _row(_run())
    assert row["year"]["points"] == [500.0, 27540.0, 500.0]
    assert _run().records[0].data["periods_with_no_reading"] == 1


def test_the_mark_lands_on_the_spike_in_the_plotted_list(seams):
    """The dot IS the finding; marking a raw index puts it on the wrong month."""
    seams["history"] = [
        _meter(reads=[_read("2026-01-01", None, register=100)] + _year(500, 27540, 500))
    ]
    assert _row(_run())["year"]["markAt"] == 1


def test_the_sparkline_label_carries_the_unit(seams):
    """Hard rule 3 — a quantity carries its unit, in the label."""
    assert _row(_run({"identical_reads_in_a_row": 3}))["year"]["label"] == "water · gal"


# ── the report ────────────────────────────────────────────────────────────


def test_every_block_name_is_one_of_the_twelve(seams):
    assert {block["block"] for block in _run().report} <= set(BLOCK_TYPES)


def test_the_rows_are_ranked_by_revenue_at_risk(seams):
    """The card: *the flat-lined apartment block is at the top rather than the
    vacant unit*."""
    seams["history"] = [
        _meter("m1", "WM-SMALL", _year(100, 100, 100, 100)),
        _meter("m2", "WM-BIG", _year(5000, 5000, 5000, 5000)),
    ]
    rows = _blocks(_run())["records"]["rows"]
    assert rows[0]["cells"]["meter"]["text"] == "WM-BIG"


def test_an_unpriced_meter_sorts_after_every_priced_one(seams):
    seams["history"] = [
        _meter("m1", "WM-UNPRICED", _year(500, 500, 500, 500)),
        _meter("m2", "WM-PRICED", _year(500, 500, 500, 500)),
    ]
    seams["occupants"] = {"u1": {"id": "acc-1", "account_no": "A-1"}}
    rows = _blocks(_run())["records"]["rows"]
    assert rows[0]["cells"]["at_risk"]["kind"] == "money"


def test_the_account_column_is_filled_by_walking_the_unit(seams):
    """`meter_reads.account_id` is nullable, and a column with a heading and no
    content is not a column."""
    seams["history"] = [
        _meter(
            reads=[
                _read(f"2026-0{index}-01", 500, account_id=None) for index in range(1, 5)
            ]
        )
    ]
    assert _row(_run())["account"]["text"] == "Riverside Apts"


def test_no_pattern_code_and_no_rule_id_reaches_a_drawn_cell(seams):
    seams["history"] = [_meter(reads=_year(500, 500, 500, 500))]
    for row in _blocks(_run())["records"]["rows"]:
        drawn = " ".join(
            str(cell.get("text") or cell.get("label") or "") for cell in row["cells"].values()
        )
        assert "BR-" not in drawn
        assert "out_of_season" not in drawn
        assert "m1" != drawn


def test_the_action_is_disabled_with_a_short_reason(seams):
    action = _blocks(_run())["action"]
    assert action["enabled"] is False
    assert len(action["reason"].split()) <= 7


def test_a_clean_fleet_says_so_rather_than_drawing_an_empty_table(seams):
    seams["history"] = [_meter(reads=_year(500, 520, 480, 510, 495, 505))]
    blocks = _blocks(_run())
    assert blocks["verdict"]["word"] == "Nothing odd"
    assert blocks["records"]["empty"]["title"] == "Every meter looks normal."
