# ── Trace ──────────────────────────────────────────────
# Story:    CR-038 W8 (the bill run's read analysis, brought to the prototype's
#           eight categories — r10 BIL-02.2)   Screens: S31.3
# Rules:    BR-MET-121 (PO 2026-08-26, verbatim: "when you run bill cycle you
#           pull the reading and at that time we have to decide whether it is
#           for 90 days or whrther it for 30 days or 15 days ; and if there is
#           an issue with reading days we flag it") · BR-MET-022/056 (stored,
#           self-describing outcomes — the run recomputes NOTHING) ·
#           BR-MET-020 (no threshold hardcoded) · BR-MET-027 (max 2 consecutive
#           estimates → forced field visit) · BR-BIL-006 / GT-9 / WE-13 ❄
#           (true-up: register arithmetic at the next actual, current-period
#           rates, on that bill — 53 ccf @ Aug rates = $60.95) · BR-BIL-015/061
#           + PO 2026-08-26 reaffirmed (no pre-selected default; suggestions
#           are chips) · BR-BIL-060 (bulk, one shared id, per-row actor)
# ───────────────────────────────────────────────────────
"""CR-038 W8 — the seven read-analysis cases, on real rows end to end.

RED-FIRST RECORD (hard-won law 7): the module-level tripwire in
tests/test_w3_billing_run_decisions.py went red the moment the cases were
declared — verbatim `AssertionError: assert 6 == 13` — and the tests here were
run against the pre-W8 tree first, failing on the missing selectors/module
(`AttributeError: ... has no attribute 'read_analysis'` class of failure),
before the implementation landed.
"""

from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal

import pytest

from apps.billing import decisions as billing_decisions
from apps.billing import gather, models, read_analysis, runs
from apps.billing import selectors as billing_selectors
from apps.metering import models as metering_models
from apps.metering import period_engine
from apps.metering import selectors as metering_selectors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_bil_001_prepare import (
    PERIOD_END,
    PERIOD_START,
    SERVICE_DATE,
    a_billed_unit,
    a_cycle,
    a_priced_plan,
    an_account,
)
from tests.test_us_met_reads_helpers import a_meter

pytestmark = pytest.mark.django_db


def at(day: str) -> datetime:
    return datetime.fromisoformat(f"{day}T09:00:00+00:00").astimezone(dt_timezone.utc)


def analysis_read(asset_id, *, day, consumption, unit="kWh", **overrides):
    """One committed head with the STORED facts the analysis renders — written
    directly, because these rows are the past a test starts from (the same
    posture as tests/test_us_met_reads_helpers.commit_read, with the W8 fields
    open)."""
    from apps.assets import models as asset_models

    values = dict(
        tenant_id=asset_models.Asset.objects.get(pk=asset_id).tenant_id,
        asset_id=asset_id,
        read_at=at(day),
        channel="total",
        current_value=Decimal("14212"),
        prior_value=Decimal("13800"),
        multiplier=Decimal("1"),
        consumption=Decimal(str(consumption)) if consumption is not None else None,
        unit=unit,
        source="import",
        status="ok",
        lifecycle="committed",
    )
    values.update(overrides)
    return metering_models.MeterRead.objects.create(**values)


def prepared_run(cycle):
    return runs.prepare_run(
        cycle_id=cycle.id,
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        service_date=SERVICE_DATE,
    )


def rows_for_case(result, case):
    return [row for row in result.rows if row["case"] == case]


# ── TC-1 · the cycle's own expected span (BR-MET-121, pure) ─────────────────


def test_tc1__expected_span_days_is_the_frequency_machinery_not_a_constant():
    """Monthly from 1 Aug 2026 is **31**; from 1 Feb 2026 it is **28** (the
    OQ-339 clamp's own month); Quarterly from 1 Jun 2026 is **92**; Fortnightly
    is **14**. A word outside B17 §2's vocabulary refuses rather than guessing
    Monthly."""
    assert period_engine.expected_span_days("monthly", date(2026, 8, 1)) == 31
    assert period_engine.expected_span_days("monthly", date(2026, 2, 1)) == 28
    assert period_engine.expected_span_days("quarterly", date(2026, 6, 1)) == 92
    assert period_engine.expected_span_days("Fortnightly", date(2026, 6, 1)) == 14
    with pytest.raises(ValueError):
        period_engine.expected_span_days("sometimes", date(2026, 6, 1))


def test_tc2__cycle_expected_span_selector_answers_none_for_an_unruled_frequency(brazos):
    """A cycle with no frequency answers None — reported, never a guessed 30
    (BR-MET-020's fail-safe posture applied to the span)."""
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)  # the fixture sets no frequency
        assert (
            metering_selectors.cycle_expected_span_days(cycle.id, period_start=PERIOD_START) is None
        )
        cycle.frequency = "monthly"
        cycle.save(update_fields=["frequency"])
        # June 2026: 1 Jun + 1 month = 1 Jul → 30 days.
        assert (
            metering_selectors.cycle_expected_span_days(cycle.id, period_start=PERIOD_START) == 30
        )


# ── TC-3 · the analysis seam serves STORED facts, heads only ────────────────


def test_tc3__read_analysis_for_unit_serves_stored_facts_for_every_period_head(brazos, dana):
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        plan = a_priced_plan(brazos)
        unit = a_billed_unit(dana, brazos, cycle, plan, asset_no="M-8101", label="Unit A")
        asset = metering_models.MeterRead.objects.filter(tenant=brazos).first().asset_id
        # A SECOND head, earlier in the period, carrying stored outcomes and
        # the estimation trio.
        analysis_read(
            asset,
            day="2026-06-10",
            consumption="618.000000",
            status="estimated",
            source="estimated",
            current_value=None,
            estimation_method="trailing_3_daily_avg",
            consecutive_estimate_no=2,
            rule_outcomes=[{"rule": "zero", "severity": "ok", "detail": {}}],
        )

        served = metering_selectors.read_analysis_for_unit(
            unit["id"], period_start=PERIOD_START, period_end=PERIOD_END
        )

    assert len(served) == 1  # one service point
    reads = served[0]["reads"]
    assert [entry["consumption"] for entry in reads] == ["618.000000", "412.000000"]
    estimate = reads[0]
    assert estimate["estimated"] is True
    assert estimate["estimation_method"] == "trailing_3_daily_avg"
    assert estimate["consecutive_estimate_no"] == 2
    assert estimate["rule_outcomes"] == [{"rule": "zero", "severity": "ok", "detail": {}}]
    assert estimate["unit"] == "kWh"  # rule 3 — never separated from the number


# ── TC-4 · Estimated tab (task 1) ───────────────────────────────────────────


def test_tc4__estimated_row_serves_the_consecutive_count_and_suggests_never_selects(brazos, dana):
    """BR-MET-027 is the ONE rule that points: at two consecutive estimates the
    field visit is forced, so `replace_with_actual` is SUGGESTED — and the row
    is still born undecided (PO 2026-08-26: *"an auditor asking 'who chose to
    estimate M-4412?' gets a name"*)."""
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        plan = a_priced_plan(brazos)
        unit = a_billed_unit(
            dana, brazos, cycle, plan, asset_no="M-8102", label="Unit A", consumption=None
        )
        an_account(brazos, unit["id"], "A-80104")
        from apps.metering import seams as metering_seams

        point = metering_models.ServicePoint.objects.get(tenant=brazos, unit_id=unit["id"])
        asset_ids = metering_seams.asset_ids_for_service_point(point.id)
        analysis_read(
            asset_ids[0],
            day="2026-06-28",
            consumption="618.000000",
            status="estimated",
            source="estimated",
            current_value=None,
            estimation_method="trailing_3_daily_avg",
            consecutive_estimate_no=2,
        )
        prepared = prepared_run(cycle)
        result = read_analysis.analysis_rows(prepared, cycle_id=cycle.id)

    rows = rows_for_case(result, "estimated_read")
    assert len(rows) == 1
    row = rows[0]
    assert row["quantity"] == "618.000000" and row["unit"] == "kWh"
    assert row["facts"]["consecutive_estimate_no"] == 2
    assert row["facts"]["estimation_method"] == "trailing_3_daily_avg"
    assert row["suggested"] == "replace_with_actual"
    assert row["choices"] == ["keep", "replace_with_actual"]
    assert "chosen" not in row  # the module cannot serve a row born decided


# ── TC-5 · High and Low from STORED outcomes (task 2) ───────────────────────


def test_tc5__high_and_low_render_the_stored_verdict_and_recompute_nothing(brazos, dana):
    """The stored detail is served VERBATIM (BR-MET-022/056). The fixture's
    ratio is deliberately not derivable from its own figures — 26.24 against
    8.40 is 312% only in the prototype's copy — and 312 is what must render,
    because the run re-deriving thresholds is the drift this posture forbids."""
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        plan = a_priced_plan(brazos)
        unit = a_billed_unit(
            dana, brazos, cycle, plan, asset_no="M-8104", label="Unit A", consumption=None
        )
        an_account(brazos, unit["id"], "A-80105")
        from apps.metering import seams as metering_seams

        point = metering_models.ServicePoint.objects.get(tenant=brazos, unit_id=unit["id"])
        asset_ids = metering_seams.asset_ids_for_service_point(point.id)
        analysis_read(
            asset_ids[0],
            day="2026-06-28",
            consumption="26.240000",
            unit="kgal",
            status="high",
            rule_outcomes=[
                {
                    "rule": "high",
                    "severity": "warning",
                    "detail": {
                        "consumption": "26.24",
                        "unit": "kgal",
                        "trailing_average": "8.40",
                        "trailing_reads": 3,
                        "ratio_pct": "312",
                        "threshold_pct": "200",
                        "absolute_floor": "1",
                        "absolute_floor_unit": "kgal",
                    },
                },
                {
                    "rule": "low",
                    "severity": "ok",
                    "detail": {"ratio_pct": "312", "threshold_pct": "25"},
                },
            ],
        )
        prepared = prepared_run(cycle)
        result = read_analysis.analysis_rows(prepared, cycle_id=cycle.id)

    high = rows_for_case(result, "high_usage")
    assert len(high) == 1
    facts = high[0]["facts"]
    assert facts["this_period"] == "26.24"
    assert facts["trailing_average"] == "8.40"
    assert facts["ratio_pct"] == "312"  # the STORED figure, not a recompute
    assert facts["threshold_pct"] == "200"
    assert facts["absolute_floor"] == "1"
    assert high[0]["suggested"] is None  # no rule names a recommended action
    # The low outcome is OK, so no low row exists — a clean read raises nothing.
    assert rows_for_case(result, "low_usage") == []


# ── TC-6 · Days threshold — BR-MET-121's home (task 3) ──────────────────────


def test_tc6__days_judgment_is_the_runs_own_and_a_quarterly_cycle_needs_no_bounds(brazos, dana):
    """THE ACCEPTANCE CASE OF THE RULING. A quarterly cycle's 92-day read
    carries an import-time WARNING (monthly bounds 25–35/20–45 cannot fit it),
    and the RUN judges it CLEAN because 92 IS the cycle's own span — verbatim
    BR-MET-121: *"A quarterly cycle therefore needs no special bounds — nothing
    blocks its readings, and billing judges the span it actually prices."* A
    52-day read on the same cycle IS flagged, judged by the cycle span, with
    the prorate suggestion the r10 rows draw."""
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        cycle.frequency = "quarterly"
        cycle.save(update_fields=["frequency"])
        plan = a_priced_plan(brazos)
        unit = a_billed_unit(
            dana, brazos, cycle, plan, asset_no="M-8105", label="Unit A", consumption=None
        )
        an_account(brazos, unit["id"], "A-80106")
        from apps.metering import seams as metering_seams

        point = metering_models.ServicePoint.objects.get(tenant=brazos, unit_id=unit["id"])
        asset_ids = metering_seams.asset_ids_for_service_point(point.id)
        stored_warning = [
            {
                "rule": "days_threshold",
                "severity": "warning",
                "detail": {
                    "days": 92,
                    "flag_bounds": [25, 35],
                    "hard_bounds": [20, 45],
                    "hard": True,
                },
            }
        ]
        healthy = analysis_read(
            asset_ids[0],
            day="2026-06-28",
            consumption="412.000000",
            days_since_prior=92,
            status="days_threshold",
            rule_outcomes=stored_warning,
        )
        prepared = prepared_run(cycle)
        clean = read_analysis.analysis_rows(prepared, cycle_id=cycle.id)
        # Now the same cycle with a 52-day span — a read pricing a window the
        # cycle does not bill.
        healthy.days_since_prior = 52
        healthy.save(update_fields=["days_since_prior"])
        prepared = prepared_run(cycle)
        flagged = read_analysis.analysis_rows(prepared, cycle_id=cycle.id)

    assert rows_for_case(clean, "days_threshold") == []  # the run's judgment wins
    rows = rows_for_case(flagged, "days_threshold")
    assert len(rows) == 1
    facts = rows[0]["facts"]
    assert facts["days"] == 52
    assert facts["expected_days"] == 92  # 1 Jun + 3 months = 1 Sep
    assert facts["judged_by"] == "cycle_span"
    assert rows[0]["suggested"] is None or rows[0]["suggested"] == "wait_next_cycle"
    # 52 < 92: the span undershoots the cycle — the r10 pairing suggests wait.
    assert rows[0]["suggested"] == "wait_next_cycle"
    assert rows[0]["choices"] == ["prorate_to_cycle_days", "wait_next_cycle", "bill_as_is"]


def test_tc7__monthly_cycle_defers_to_the_tenants_own_bounds(brazos, dana):
    """Where the cycle's span sits INSIDE the tenant's flag bounds the stored
    verdict governs — the bounds were built for this cycle, and they absorb
    read-day jitter the way BR-MET-020 intends. 52 days on a June monthly
    cycle (expected 30, bounds 25–35) is the stored WARNING, judged by
    tenant_bounds, suggested prorate (52 > 30)."""
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        cycle.frequency = "monthly"
        cycle.save(update_fields=["frequency"])
        plan = a_priced_plan(brazos)
        unit = a_billed_unit(
            dana, brazos, cycle, plan, asset_no="M-8106", label="Unit A", consumption=None
        )
        an_account(brazos, unit["id"], "A-80107")
        from apps.metering import seams as metering_seams

        point = metering_models.ServicePoint.objects.get(tenant=brazos, unit_id=unit["id"])
        asset_ids = metering_seams.asset_ids_for_service_point(point.id)
        analysis_read(
            asset_ids[0],
            day="2026-06-28",
            consumption="412.000000",
            days_since_prior=52,
            status="days_threshold",
            rule_outcomes=[
                {
                    "rule": "days_threshold",
                    "severity": "warning",
                    "detail": {
                        "days": 52,
                        "flag_bounds": [25, 35],
                        "hard_bounds": [20, 45],
                        "hard": True,
                    },
                }
            ],
        )
        prepared = prepared_run(cycle)
        result = read_analysis.analysis_rows(prepared, cycle_id=cycle.id)

    rows = rows_for_case(result, "days_threshold")
    assert len(rows) == 1
    assert rows[0]["facts"]["judged_by"] == "tenant_bounds"
    assert rows[0]["facts"]["expected_days"] == 30
    assert rows[0]["suggested"] == "prorate_to_cycle_days"


# ── TC-8 · Meter factor (task 4) ────────────────────────────────────────────


def test_tc8__a_non_unit_factor_is_shown_with_its_stored_math_and_a_x1_is_not(brazos, dana):
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        plan = a_priced_plan(brazos)
        unit = a_billed_unit(
            dana, brazos, cycle, plan, asset_no="M-8107", label="Unit A", consumption=None
        )
        an_account(brazos, unit["id"], "A-80108")
        from apps.metering import seams as metering_seams

        point = metering_models.ServicePoint.objects.get(tenant=brazos, unit_id=unit["id"])
        asset_ids = metering_seams.asset_ids_for_service_point(point.id)
        analysis_read(
            asset_ids[0],
            day="2026-06-28",
            consumption="27540.000000",
            multiplier=Decimal("10"),
            current_value=Decimal("2754"),
            prior_value=Decimal("0"),
            rule_outcomes=[
                {
                    "rule": "factor_flag",
                    "severity": "not_evaluated",
                    "detail": {"reason": "threshold_not_ratified"},
                }
            ],
        )
        prepared = prepared_run(cycle)
        result = read_analysis.analysis_rows(prepared, cycle_id=cycle.id)

    rows = rows_for_case(result, "meter_factor")
    assert len(rows) == 1
    facts = rows[0]["facts"]
    # THE STORED figure, at the column's own scale — served verbatim rather
    # than reshaped for display. This assertion was written as "10" and went
    # RED against the real row (`assert '10.000000' == '10'`), which is the
    # seam refusing to be a formatter: a consumer that trimmed the stored value
    # here would be a second spelling of the number the bill is computed from.
    # ⚠ The DISPLAY precision of a multiplier is REPORTED — CLAUDE.md rule 2
    # rules money (4dp) and percentages (6dp) and says nothing about a meter
    # factor, and r10 draws "×10".
    assert facts["multiplier"] == "10.000000"
    # Same posture for the RAW REGISTER value, and it went RED the same way
    # (`assert '2754.000000' == '2754'`): the register column is NUMERIC(.,6)
    # too, so the seam hands back the stored spelling and the screen decides
    # how to draw it. Asserting the trimmed form here would have written a
    # formatter into the contract.
    assert facts["current_value"] == "2754.000000"
    assert facts["computed"] == "27540.000000"
    # Honest about the unratified rule — served as stored, never faked.
    assert facts["factor_rule_severity"] == "not_evaluated"
    assert facts["factor_rule_reason"] == "threshold_not_ratified"
    assert rows[0]["choices"] == ["confirm_factor", "investigate"]


# ── TC-9 · Replacements (task 5) ────────────────────────────────────────────


def test_tc9__a_mid_cycle_swap_lists_both_segments_and_totals_the_chain(brazos, dana):
    """Old meter final + new meter start, on ONE service point (assets keeps
    retired meters on the seam for exactly this). The segments total is a
    QUANTITY sum over stored consumptions — no money is computed — and the
    prorate-both-segments choice is offered, recorded, and held at the named
    pricing boundary (the pricing seam prices the single latest head)."""
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        plan = a_priced_plan(brazos)
        unit = a_billed_unit(
            dana, brazos, cycle, plan, asset_no="M-8108", label="Unit A", consumption=None
        )
        an_account(brazos, unit["id"], "A-80109")
        replacement = a_meter(dana, asset_no="M-8109", unit_id=unit["id"])
        from apps.metering import seams as metering_seams

        point = metering_models.ServicePoint.objects.get(tenant=brazos, unit_id=unit["id"])
        asset_ids = metering_seams.asset_ids_for_service_point(point.id)
        assert len(asset_ids) == 2  # one service point, two meters — the swap
        old_id = next(a for a in asset_ids if str(a) != str(replacement["id"]))
        analysis_read(
            old_id,
            day="2026-06-14",
            consumption="230.000000",
            current_value=Decimal("14030"),
        )
        analysis_read(
            str(replacement["id"]),
            day="2026-06-28",
            consumption="182.000000",
            prior_value=Decimal("0"),
            current_value=Decimal("182"),
        )
        prepared = prepared_run(cycle)
        result = read_analysis.analysis_rows(prepared, cycle_id=cycle.id)

    rows = rows_for_case(result, "replacement")
    assert len(rows) == 1
    facts = rows[0]["facts"]
    assert facts["old_final_quantity"] == "230.000000"
    assert facts["new_start_quantity"] == "182.000000"
    assert facts["segment_count"] == 2
    assert facts["segments_total"] == "412.000000"  # the chain already totals
    assert rows[0]["unit"] == "kWh"
    assert rows[0]["choices"] == ["prorate_both_segments", "bill_as_is", "investigate"]


# ── TC-10 · True-up money (task 6, 🔒) ──────────────────────────────────────


def test_tc10__true_up_prices_the_trued_quantity_through_ratings_own_engine(brazos, dana):
    """WE-13 ❄'s mechanics on this fixture's own figures: the committed actual
    already carries the register-arithmetic quantity (53), and its worth on
    THIS bill at current-period rates is the ENGINE's answer — 53 × 1.15 =
    **60.95**, the worked example's own dollar figure. The client never sums
    (BR-SHL-023): the amount arrives served."""
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        plan = a_priced_plan(brazos, price="1.150000")
        unit = a_billed_unit(
            dana, brazos, cycle, plan, asset_no="M-8110", label="Unit A", consumption=None
        )
        an_account(brazos, unit["id"], "A-80110")
        from apps.metering import seams as metering_seams

        point = metering_models.ServicePoint.objects.get(tenant=brazos, unit_id=unit["id"])
        asset_ids = metering_seams.asset_ids_for_service_point(point.id)
        estimate = analysis_read(
            asset_ids[0],
            day="2026-06-05",
            consumption="42.000000",
            status="estimated",
            source="estimated",
            current_value=None,
            estimation_method="trailing_3_daily_avg",
            consecutive_estimate_no=1,
        )
        analysis_read(
            asset_ids[0],
            day="2026-06-28",
            consumption="53.000000",
            trues_up_read_ids=[str(estimate.id)],
            rule_outcomes=[
                {
                    "rule": "true_up",
                    "severity": "ok",
                    "detail": {
                        "applies": True,
                        "quantity": "53.000000",
                        "register_delta": "95.000000",
                        "estimated_total": "42.000000",
                        "corrects_read_ids": [str(estimate.id)],
                    },
                }
            ],
        )
        prepared = prepared_run(cycle)
        result = read_analysis.analysis_rows(prepared, cycle_id=cycle.id)

    rows = rows_for_case(result, "true_up")
    assert len(rows) == 1
    row = rows[0]
    assert row["quantity"] == "53.000000" and row["unit"] == "kWh"
    assert row["amount"] == "60.95"  # WE-13's own figure, from the engine's line
    assert row["currency"] == "USD"
    assert row["facts"]["register_delta"] == "95.000000"
    assert row["facts"]["estimated_total"] == "42.000000"
    assert row["facts"]["corrects_count"] == 1
    assert row["suggested"] == "apply_next_bill"  # BR-BIL-006's own sentence
    assert row["choices"] == ["apply_next_bill", "hold"]


# ── TC-11 · the surface: one endpoint, recorded dispositions, bulk ──────────


def test_tc11__exceptions_dict_serves_analysis_rows_undecided_and_joins_choices(brazos, dana):
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        plan = a_priced_plan(brazos)
        unit = a_billed_unit(
            dana, brazos, cycle, plan, asset_no="M-8111", label="Unit A", consumption=None
        )
        from apps.metering import seams as metering_seams

        point = metering_models.ServicePoint.objects.get(tenant=brazos, unit_id=unit["id"])
        asset_ids = metering_seams.asset_ids_for_service_point(point.id)
        analysis_read(
            asset_ids[0],
            day="2026-06-28",
            consumption="618.000000",
            status="estimated",
            source="estimated",
            current_value=None,
            estimation_method="trailing_3_daily_avg",
            consecutive_estimate_no=1,
        )
        an_account(brazos, unit["id"], "A-80001")
        run = models.BillRun.objects.create(
            tenant=brazos,
            cycle=cycle,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            bill_date=SERVICE_DATE,
            idempotency_key="w8|tc11",
        )

        body = billing_selectors.exceptions_dict(run)
        est_rows = [row for row in body["rows"] if row["case"] == "estimated_read"]
        assert len(est_rows) == 1
        assert est_rows[0]["chosen"] is None  # born undecided — the reaffirmed rule
        assert est_rows[0]["suggested"] is None  # 1st estimate: no rule points
        assert body["counts"]["estimated_read"] == 1
        assert body["analysis_gaps"] == []

        # Record a disposition through the SAME door the classic cases use —
        # per-row actor recording is the decision table's own machinery.
        bulk_id, rows = billing_decisions.resolve_cases(
            bill_run=run,
            case_id=est_rows[0]["id"],
            choice="keep",
            case_ids=[est_rows[0]["id"]],
            decided_by=dana.user,
        )
        assert bulk_id is not None  # a bulk of one is still a bulk (BR-BIL-060)
        assert all(row.decided_by_id == dana.user.id for row in rows)
        assert all(row.bulk_action_id == bulk_id for row in rows)

        body = billing_selectors.exceptions_dict(run)
        est_rows = [row for row in body["rows"] if row["case"] == "estimated_read"]
        assert est_rows[0]["chosen"] == "keep"


# ── TC-12 · the holding choices hold, at their NAMED boundaries ─────────────


def test_tc12__replace_with_actual_and_prorate_hold_the_account_out(brazos, dana):
    """`replace_with_actual` holds because billing the refused estimate would
    un-make the clerk's decision; `prorate_to_cycle_days` holds at the NAMED
    pricing boundary (no signed rule scales a consumption to N days) rather
    than billing money the clerk explicitly asked to change."""
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        plan = a_priced_plan(brazos)
        unit = a_billed_unit(dana, brazos, cycle, plan, asset_no="M-8112", label="Unit A")
        account = an_account(brazos, unit["id"], "A-80002")
        run = models.BillRun.objects.create(
            tenant=brazos,
            cycle=cycle,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            bill_date=SERVICE_DATE,
            idempotency_key="w8|tc12",
        )
        billing_decisions.record_decision(
            bill_run=run,
            account_id=str(account.id),
            case="estimated_read",
            choice="replace_with_actual",
            reason="customer disputes the estimate — send a reader",
            decided_by=dana.user,
        )
        prepared = prepared_run(cycle)
        assert [d.account_no for d in prepared.ready] == ["A-80002"]
        applied = billing_decisions.apply_decisions(prepared, bill_run=run)

        assert applied.ready == ()  # the account waits for the actual read
        exclusion = models.BillRunExclusion.objects.get(bill_run=run)
        assert exclusion.reason_code == "staff_replace_with_actual_estimated_read"

        # The prorate boundary, same machinery: a NEW decision supersedes and
        # the account still holds — now at the pricing boundary by name.
        billing_decisions.record_decision(
            bill_run=run,
            account_id=str(account.id),
            case="days_threshold",
            choice="prorate_to_cycle_days",
            decided_by=dana.user,
        )
        applied = billing_decisions.apply_decisions(prepared, bill_run=run)
        assert applied.ready == ()


def test_tc13__an_unpublished_analysis_seam_is_a_named_gap_not_seven_clean_tabs(
    brazos, dana, monkeypatch
):
    """'Nothing flagged' and 'could not look' are different facts — the
    `_dispute_hold_for` posture, applied to the analysis."""
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        plan = a_priced_plan(brazos)
        a_billed_unit(dana, brazos, cycle, plan, asset_no="M-8113", label="Unit A")
        prepared = prepared_run(cycle)

    real_resolve = gather._resolve

    def missing_analysis(module, attribute, kind="selectors"):
        if attribute == "read_analysis_for_unit":
            return None
        return real_resolve(module, attribute, kind)

    monkeypatch.setattr(gather, "_resolve", missing_analysis)
    result = read_analysis.analysis_rows(prepared, cycle_id=cycle.id)
    assert result.rows == ()
    assert [gap["code"] for gap in result.gaps] == ["metering_read_analysis_unpublished"]


# ── TC-14 · DEF-790's carried flags — an UNBILLABLE head raises no case ─────


def test_tc14__a_read_the_run_cannot_bill_raises_no_analysis_row(brazos, dana):
    """**The DEF-790 input change, met head on.** Group-rule flags now travel
    onto the committed read, so a TOU meter whose windows do not sum commits
    with `status='tou_sum_sanity'` and lands in
    `metering.selectors.UNBILLABLE_READ_STATUSES`.

    The pricing seam (`billing_reads_for_unit`) takes the LATEST head and,
    finding it unbillable, prices nothing — the service becomes
    `READ_ABSENT_FLAGGED` and the run raises its `missing_read` case with
    BR-BIL-015's three choices. That read therefore ALREADY has a surface and
    an owner.

    So the analysis must raise nothing about it. Offering `bill_as_is` on a
    days row for a read the run refuses to bill is a disposition that cannot be
    honoured — the clerk records a decision, the account still does not bill,
    and the audit trail says a human chose something the machine ignored.

    RED FIRST (law 7): before `_priced_read` learned the difference, this test
    failed verbatim
    `AssertionError: assert ['days_thresh... 'high_usage'] == []` /
    `Left contains 2 more items, first extra item: 'days_threshold'`
    — two contradictory dispositions offered on the flagged read.
    """
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        plan = a_priced_plan(brazos)
        unit = a_billed_unit(
            dana, brazos, cycle, plan, asset_no="M-8114", label="Unit A", consumption=None
        )
        an_account(brazos, unit["id"], "A-80114")
        from apps.metering import seams as metering_seams

        point = metering_models.ServicePoint.objects.get(tenant=brazos, unit_id=unit["id"])
        asset_ids = metering_seams.asset_ids_for_service_point(point.id)
        analysis_read(
            asset_ids[0],
            day="2026-06-28",
            consumption="26.240000",
            unit="kgal",
            # DEF-790: the group rule's verdict, CARRIED onto the committed
            # read rather than left behind on the staged row.
            status="tou_sum_sanity",
            days_since_prior=52,
            rule_outcomes=[
                {
                    "rule": "high",
                    "severity": "warning",
                    "detail": {
                        "consumption": "26.24",
                        "unit": "kgal",
                        "trailing_average": "8.40",
                        "ratio_pct": "312",
                        "threshold_pct": "200",
                    },
                },
                {
                    "rule": "days_threshold",
                    "severity": "warning",
                    "detail": {"days": 52, "flag_bounds": [25, 35], "hard_bounds": [20, 45]},
                },
                {
                    "rule": "tou_sum_sanity",
                    "severity": "error",
                    "detail": {"reason": "windows_do_not_sum"},
                },
            ],
        )
        prepared = prepared_run(cycle)
        result = read_analysis.analysis_rows(prepared, cycle_id=cycle.id)

    assert sorted({row["case"] for row in result.rows}) == []
    # And the analysis says nothing about a seam it could reach — the absence
    # is a JUDGMENT, not a gap.
    assert result.gaps == ()


# ── TC-15/16 · the PO's RATIFIED true-up case, and what a refusal shows ──────
#
# PO ruling 2026-08-27, verbatim: *"Item 7 Ratify the true-up figure - Confirm
# the figure and its refusal behaviour are ratified and pinned by a test"*.
#
# The ratification covers the worked case that was put to the PO in plain
# English — two estimated cycles totalling **1,236 kWh**, an actual reading
# landing at **1,410 kWh**, trued up by **+174 kWh**, priced by the ENGINE on
# that account's own tariff — and the refusal behaviour beside it: when pricing
# cannot answer, the clerk sees the QUANTITY with the refusal named, never a
# number nobody computed.
#
# TC-10 above already pins WE-13's own 53 ccf / $60.95. It does NOT pin either
# half of what was ratified, which is why these two exist: a signature covers
# only what was shown, and what was shown must go red when it drifts
# (CLAUDE.md sensitive-paths, part 2 of the sign-off definition).


def _ratified_true_up_fixture(brazos, dana, *, price="1.150000"):
    """The PO's own worked case as rows: estimates billing 1,236, an actual
    whose register span is 1,410, and 174 left to carry on THIS bill."""
    cycle = a_cycle(brazos)
    plan = a_priced_plan(brazos, price=price)
    unit = a_billed_unit(
        dana, brazos, cycle, plan, asset_no="M-8117", label="Unit R", consumption=None
    )
    an_account(brazos, unit["id"], "A-80117")
    from apps.metering import seams as metering_seams

    point = metering_models.ServicePoint.objects.get(tenant=brazos, unit_id=unit["id"])
    asset_ids = metering_seams.asset_ids_for_service_point(point.id)
    # Two estimated cycles — 618 + 618 = 1,236 kWh already billed.
    first = analysis_read(
        asset_ids[0],
        day="2026-06-04",
        consumption="618.000000",
        status="estimated",
        source="estimated",
        current_value=None,
        estimation_method="trailing_3_daily_avg",
        consecutive_estimate_no=1,
    )
    second = analysis_read(
        asset_ids[0],
        day="2026-06-12",
        consumption="618.000000",
        status="estimated",
        source="estimated",
        current_value=None,
        estimation_method="trailing_3_daily_avg",
        consecutive_estimate_no=2,
    )
    # The actual: the register actually moved 1,410; 1,236 is already billed;
    # 174 is the register arithmetic that this bill carries (BR-MET-029/WE-13 ❄).
    analysis_read(
        asset_ids[0],
        day="2026-06-27",
        consumption="174.000000",
        trues_up_read_ids=[str(first.id), str(second.id)],
        rule_outcomes=[
            {
                "rule": "true_up",
                "severity": "ok",
                "detail": {
                    "applies": True,
                    "quantity": "174.000000",
                    "register_delta": "1410.000000",
                    "estimated_total": "1236.000000",
                    "corrects_read_ids": [str(first.id), str(second.id)],
                },
            }
        ],
    )
    return cycle


def test_tc15__the_ratified_true_up_case_shows_174_priced_by_the_engine(brazos, dana):
    """RATIFIED 2026-08-27. 1,236 kWh billed on estimates, an actual span of
    1,410 kWh, **+174 kWh** carried on this bill — and the money beside it is
    the engine's own usage line on this account's tariff (174 × 1.15 =
    **200.10**), never a rate `read_analysis.py` holds."""
    with tenant_ctx(brazos):
        cycle = _ratified_true_up_fixture(brazos, dana)
        prepared = prepared_run(cycle)
        result = read_analysis.analysis_rows(prepared, cycle_id=cycle.id)

    rows = rows_for_case(result, "true_up")
    assert len(rows) == 1
    row = rows[0]
    # The three figures the PO was shown, in the clerk's own row.
    assert row["facts"]["estimated_total"] == "1236.000000"
    assert row["facts"]["register_delta"] == "1410.000000"
    assert row["quantity"] == "174.000000"
    assert row["unit"] == "kWh"  # hard rule 3 — never assumed
    assert row["facts"]["corrects_count"] == 2
    # And its worth: the ENGINE's line, not this module's arithmetic.
    assert row["amount"] == "200.10"
    assert row["currency"] == "USD"
    assert "pricing_gap" not in row["facts"]
    assert row["suggested"] == "apply_next_bill"


def test_tc16__when_pricing_refuses_the_clerk_still_sees_174_and_the_reason(
    brazos, dana, monkeypatch
):
    """The other half of what was ratified: a refusal shows the QUANTITY with
    the refusal NAMED. No amount, no currency, no guessed number — and the row
    does not vanish, because a clerk who cannot see the reading cannot act on
    it."""

    def refuses(**_kwargs):
        raise read_analysis.rating_seam.PricingRefused(
            "no priceable component for kWh on this tariff"
        )

    with tenant_ctx(brazos):
        cycle = _ratified_true_up_fixture(brazos, dana)
        prepared = prepared_run(cycle)
        monkeypatch.setattr(read_analysis.rating_seam, "price_period", refuses)
        result = read_analysis.analysis_rows(prepared, cycle_id=cycle.id)

    rows = rows_for_case(result, "true_up")
    assert len(rows) == 1
    row = rows[0]
    assert row["quantity"] == "174.000000" and row["unit"] == "kWh"
    assert row["amount"] is None and row["currency"] is None
    assert "no priceable component for kWh" in row["facts"]["pricing_gap"]
    # The row is still actionable — the refusal names itself, it does not hide.
    assert row["suggested"] == "apply_next_bill"
