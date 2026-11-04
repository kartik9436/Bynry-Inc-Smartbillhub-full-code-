# ── Trace ──────────────────────────────────────────────
# Story:    US-RAT-012 (usage pricing — TOU) · US-RAT-007 (seasonal structure) ·
#           US-BIL-001/004 (the bulk run) · US-BIL-012 (the one-time bill)
#           Screens: S31.2 (the run's priced lines) · the one-time bill
# Rules:    BR-RAT-034 (CONFIRMED; AMENDED 2026-10-01 — a reading on the
#           season-change day replaces the calendar-day split) · BR-RAT-021 ·
#           BR-MET-028 (an estimate carries no dial value) · BR-MET-500
# Golden:   GT-34 (= WE-18) — the no-reading half, unchanged; this file is
#           WE-18's OTHER sentence, *"an ACTUAL read dated Oct 1 would replace
#           the split"*.
# Defect:   DEF-RAT-8849 · decision log 2026-10-01 "A METER READ TAKEN ON THE
#           SEASON-CHANGE DAY REPLACES THE DAY SPLIT" + "BUILT"
# ───────────────────────────────────────────────────────
"""A METER READ ON THE SEASON-CHANGE DAY REPLACES THE DAY SPLIT, end to end.

PO, 2026-10-01, verbatim: *"yes build the season-change day reading"*. The
example the PO was shown: 120 kWh on-peak over 15 Sep – 14 Oct, the season
changing 1 Oct. With an ACTUAL reading dated 1 Oct showing 80 before and 40
after, the bill prices **80 at summer and 40 at winter** —
`80 × $0.22 = $17.60` + `40 × $0.18 = $7.20` = **$24.80** on-peak — where the
calendar-day split (16/30, 14/30) prices **64 / 56** = `$14.08 + $10.08` =
**$24.16**.

The whole bill, at WE-18's rates (on/mid/off summer $0.22/$0.14/$0.09, winter
$0.18/$0.12/$0.08), with the 1 Oct reading cutting each window:

    on-peak   80 × 0.22 = 17.60    40 × 0.18 =  7.20
    mid-peak 110 × 0.14 = 15.40    90 × 0.12 = 10.80
    off-peak 210 × 0.09 = 18.90   170 × 0.08 = 13.60
    usage $83.50 · base $12.00 · taxable $95.50

against WE-18's day split, usage **$82.72**, total **$103.67**.

⚠ **THE READINGS ARE CHAINED, AS METERING STORES THEM.** Each reading is
measured from the one before it: 1 Oct from the opening dial, 14 Oct from 1
Oct. Until `DEF-BIL-9016` (fixed 2026-10-02) a bill took only the closing
reading's own quantity, so these worlds billed the 40 after 1 Oct and lost the
80 before it; they were first written measuring the closing reading from the
opening one to step round that. They are realistic now.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from apps.billing import gather
from apps.billing import models as billing_models
from apps.rating import models as rating_models

from tests.test_oq234_season_split import (
    WE18_END,
    WE18_LINES,
    WE18_START,
    WE18_TOTAL,
    WE18_USAGE,
    WINDOWS,
    _base_code_and_taxes,
    _bulk,
    _metered_account,
    _one_time,
    _round,
    _usage,
    _version,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import make_plan, tenant_ctx
from tests.test_us_met_reads_helpers import commit_read

pytestmark = pytest.mark.django_db

CHANGE_DAY = "2026-10-01"
#: Each window's dial on 1 Oct — the usage BEFORE the season changed.
BEFORE = {"tou_on": "80", "tou_mid": "110", "tou_off": "210"}
TOTAL_BEFORE = "400"
#: Each register's dial on the period's first day — not zero, so a bill that
#: priced a dial instead of a difference would show it.
OPENING = {"tou_on": "1000", "tou_mid": "2000", "tou_off": "3000"}

CUT_LINES = sorted(Decimal(x) for x in ("17.60", "7.20", "15.40", "10.80", "18.90", "13.60"))
CUT_USAGE = Decimal("83.50")
ON_PEAK_CUT = Decimal("24.80")
#: Tax on taxable $95.50 at WE-18's four authorities (6.25% + 1% + 2% + 0.2%).
CUT_TAX = Decimal("9.03")
CUT_TOTAL = Decimal("104.53")
ON_PEAK_DAY_SPLIT = Decimal("24.16")


def a_tou_world_read_on(tenant, actor, *, account_no, asset_no, day=CHANGE_DAY, estimated=False):
    """WE-18's tariff and registers, plus a reading of every register on `day`."""
    plan = make_plan(tenant, name=f"Seasonal TOU {account_no}", services=("electric",))
    version, seasons = _version(tenant, plan, "time_of_use")
    for label, channel, t_start, t_end, summer, winter, _qty in WINDOWS:
        for season, price in (("Summer", summer), ("Winter", winter)):
            rating_models.TimeOfUseWindow.objects.create(
                tenant=tenant,
                tariff_version=version,
                season=seasons[season],
                label=label,
                day_type="weekday",
                start_time=t_start,
                end_time=t_end,
                unit_price=Decimal(price),
                channel=channel,
            )
    _base_code_and_taxes(tenant, plan)
    account, asset, cycle = _metered_account(
        tenant, actor, plan, WE18_START, WE18_END, account_no, asset_no
    )
    start, end = WE18_START.isoformat(), WE18_END.isoformat()
    # REALISTIC CHAINED READINGS (DEF-BIL-9016): each reading is measured from
    # the one before it, as metering stores them. The OPENING readings, dated
    # the period's first day, carry the PREVIOUS period's usage and must not be
    # counted; an ESTIMATE has no dial, so the reading after it is measured
    # across it from the last real dial.
    registers = [("total", "5000", "700")] + [
        (channel, OPENING[channel], qty) for _l, channel, _s, _e, _su, _wi, qty in WINDOWS
    ]
    for channel, opening, qty in registers:
        before = TOTAL_BEFORE if channel == "total" else BEFORE[channel]
        dial_open = Decimal(opening)
        dial_day = dial_open + Decimal(before)
        dial_close = dial_open + Decimal(qty)
        commit_read(
            actor,
            asset["id"],
            day=start,
            value=str(dial_open),
            channel=channel,
            prior_value=str(dial_open - 50),
            consumption="50",
            unit="kWh",
        )
        commit_read(
            actor,
            asset["id"],
            day=day,
            value=str(dial_day),
            channel=channel,
            prior_value=str(dial_open),
            consumption=before,
            unit="kWh",
            estimated=estimated,
        )
        measured_from = dial_open if estimated else dial_day
        commit_read(
            actor,
            asset["id"],
            day=end,
            value=str(dial_close),
            channel=channel,
            prior_value=str(measured_from),
            consumption=str(dial_close - measured_from),
            unit="kWh",
        )
    return account, cycle


def _on_peak(usage):
    return [line for line in usage if "On-peak" in line.description]


# ── The PO's 80 / 40, through the BULK RUN ─────────────────────────────────


def test_def_rat_8849_the_80_40_reading_through_the_bulk_run(brazos, dana):
    with tenant_ctx(brazos):
        _account, cycle = a_tou_world_read_on(brazos, dana, account_no="A-88491", asset_no="M-8849")
        invoice = _bulk(cycle, WE18_START, WE18_END)
        usage = list(_usage(invoice))
        on_peak = _on_peak(usage)
        assert sorted(line.quantity for line in on_peak) == [Decimal("40"), Decimal("80")]
        assert _round(sum(line.amount for line in on_peak)) == ON_PEAK_CUT
        assert sorted(_round(line.amount) for line in usage) == CUT_LINES
        assert _round(sum(line.amount for line in usage)) == CUT_USAGE


# ── … and through a ONE-TIME bill, the same figure ─────────────────────────


def test_def_rat_8849_the_80_40_reading_through_a_one_time_bill(brazos, dana):
    with tenant_ctx(brazos):
        account, _cycle = a_tou_world_read_on(brazos, dana, account_no="A-88492", asset_no="M-8850")
        invoice = _one_time(account, WE18_START, WE18_END)
        usage = list(_usage(invoice))
        assert sorted(_round(line.amount) for line in usage) == CUT_LINES
        assert _round(sum(line.amount for line in _on_peak(usage))) == ON_PEAK_CUT
        assert _round(sum(line.amount for line in usage)) == CUT_USAGE
        # Base $12.00 + the tax four authorities charge on $95.50.
        assert _round(invoice.subtotal) == CUT_USAGE + Decimal("12.00")
        assert (_round(invoice.tax_total), _round(invoice.total)) == (CUT_TAX, CUT_TOTAL)


# ── An ESTIMATE on the boundary does not cut: WE-18 stays $82.72 / $103.67 ──


def test_def_rat_8849_an_estimated_reading_on_the_boundary_keeps_the_day_split(brazos, dana):
    with tenant_ctx(brazos):
        _account, cycle = a_tou_world_read_on(
            brazos, dana, account_no="A-88493", asset_no="M-8851", estimated=True
        )
        invoice = _bulk(cycle, WE18_START, WE18_END)
        usage = list(_usage(invoice))
        assert sorted(line.quantity for line in _on_peak(usage)) == [Decimal("56"), Decimal("64")]
        assert _round(sum(line.amount for line in _on_peak(usage))) == ON_PEAK_DAY_SPLIT
        assert sorted(_round(line.amount) for line in usage) == WE18_LINES
        assert _round(sum(line.amount for line in usage)) == WE18_USAGE
        assert _round(invoice.total) == WE18_TOTAL


# ── A reading on ANOTHER day does not cut: still 64 / 56 ───────────────────


def test_def_rat_8849_a_reading_not_on_the_change_day_keeps_the_day_split(brazos, dana):
    with tenant_ctx(brazos):
        _account, cycle = a_tou_world_read_on(
            brazos, dana, account_no="A-88494", asset_no="M-8852", day="2026-09-30"
        )
        invoice = _bulk(cycle, WE18_START, WE18_END)
        usage = list(_usage(invoice))
        assert sorted(line.quantity for line in _on_peak(usage)) == [Decimal("56"), Decimal("64")]
        assert sorted(_round(line.amount) for line in usage) == WE18_LINES
        assert _round(invoice.total) == WE18_TOTAL


# ── The realistic CHAINED world, anchored on the cycle run (seasonal model) ──


def test_def_rat_8849_seasonal_chained_reads_on_the_cycle_run(brazos, dana):
    """Summer $0.12, winter $0.10. The last issued bill closed the meter at
    1,000 on 14 Sep; metering stored 1 Oct as `1,200 − 1,000 = 200` and 14 Oct
    as `1,300 − 1,200 = 100`. The run opens at 1,000 (DEF-BIL-5270), measures
    300, and the 1 Oct reading cuts it: `200 × 0.12 = $24.00` +
    `100 × 0.10 = $10.00` = **$34.00**, where the day split (160 / 140) is
    `$19.20 + $14.00` = $33.20."""
    with tenant_ctx(brazos):
        plan = make_plan(brazos, name="Seasonal flat A-88495", services=("electric",))
        version, seasons = _version(brazos, plan, "seasonal")
        for seq, (label, price) in enumerate((("Summer", "0.120000"), ("Winter", "0.100000")), 1):
            rating_models.RateTier.objects.create(
                tenant=brazos,
                tariff_version=version,
                season=seasons[label],
                seq=seq,
                from_qty=Decimal("0"),
                to_qty=None,
                unit_price=Decimal(price),
            )
        _base_code_and_taxes(brazos, plan)
        account, asset, cycle = _metered_account(
            brazos, dana, plan, WE18_START, WE18_END, "A-88495", "M-8853"
        )
        closed = commit_read(
            dana,
            asset["id"],
            day="2026-09-14",
            value="1000",
            prior_value="900",
            consumption="100",
            unit="kWh",
        )
        commit_read(
            dana,
            asset["id"],
            day=CHANGE_DAY,
            value="1200",
            prior_value="1000",
            consumption="200",
            unit="kWh",
        )
        commit_read(
            dana,
            asset["id"],
            day=WE18_END.isoformat(),
            value="1300",
            prior_value="1200",
            consumption="100",
            unit="kWh",
        )
        invoice = billing_models.Invoice.objects.create(
            tenant=brazos,
            account=account,
            status=billing_models.INVOICE_ISSUED,
            period_start=date(2026, 8, 15),
            period_end=date(2026, 9, 14),
            service_date=date(2026, 9, 14),
            currency="USD",
            total=Decimal("0.000000"),
            subtotal=Decimal("0.000000"),
            tax_total=Decimal("0.000000"),
            bill_payload={"services": [{"code": "electric", "read_id": str(closed.id)}]},
        )
        assert invoice.pk
        bill = _bulk(cycle, WE18_START, WE18_END)
        usage = sorted(_round(line.amount) for line in _usage(bill))
        assert usage == [Decimal("10.00"), Decimal("24.00")]
        assert sorted(line.quantity for line in _usage(bill)) == [Decimal("100"), Decimal("200")]


# ── The cut itself: which reading counts, and when nothing is cut ─────────


def _register(day, value, *, read_id, estimated=False, channel="total", asset="m1", mult="1"):
    return {
        "read_id": read_id,
        "day": day,
        "channel": channel,
        "asset_id": asset,
        "current_value": None if estimated else Decimal(value),
        "multiplier": Decimal(mult),
        "estimated": estimated,
        "billable": True,
    }


CHANGES = [date(2026, 10, 1)]


def test_def_rat_8849_an_actual_reading_wins_over_an_estimate_that_day():
    registers = (  # newest first, as metering orders them
        _register("2026-10-14", "120", read_id="c"),
        _register("2026-10-01", "0", read_id="e", estimated=True),
        _register("2026-10-01", "80", read_id="b"),
    )
    assert gather._cut_register(Decimal("120"), registers, "total", CHANGES) == (
        Decimal("80"),
        Decimal("40"),
    )


def test_def_rat_8849_the_last_actual_reading_that_day_counts():
    registers = (
        _register("2026-10-14", "120", read_id="c"),
        _register("2026-10-01", "85", read_id="b2"),
        _register("2026-10-01", "80", read_id="b1"),
    )
    assert gather._cut_register(Decimal("120"), registers, "total", CHANGES) == (
        Decimal("85"),
        Decimal("35"),
    )


def test_def_rat_8849_the_factor_the_closing_reading_used_scales_the_later_season():
    registers = (
        _register("2026-10-14", "12", read_id="c", mult="10"),
        _register("2026-10-01", "8", read_id="b", mult="10"),
    )
    assert gather._cut_register(Decimal("120"), registers, "total", CHANGES) == (
        Decimal("80"),
        Decimal("40"),
    )


@pytest.mark.parametrize(
    "registers",
    [
        # only an estimate that day
        (
            _register("2026-10-14", "120", read_id="c"),
            _register("2026-10-01", "0", read_id="e", estimated=True),
        ),
        # the boundary reading is on another meter (an exchange)
        (
            _register("2026-10-14", "120", read_id="c"),
            _register("2026-10-01", "80", read_id="b", asset="m0"),
        ),
        # an estimated closing reading has no dial to subtract from
        (
            _register("2026-10-14", "0", read_id="c", estimated=True),
            _register("2026-10-01", "80", read_id="b"),
        ),
        # a part below zero — the reading is not inside what this bill measured
        (_register("2026-10-14", "300", read_id="c"), _register("2026-10-01", "80", read_id="b")),
    ],
)
def test_def_rat_8849_nothing_is_cut_where_the_subtraction_would_be_a_fiction(registers):
    assert gather._cut_register(Decimal("120"), registers, "total", CHANGES) is None


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-RAT-8849 · decision log 2026-10-01 "A METER READ TAKEN ON THE SEASON-CHANGE DAY REPLACES THE DAY SPLIT" · BR-RAT-034 · WE-18/GT-34
# generated: 2026-10-01 by the season-change-reading lane
# checklist: A✔ B✔ C✔ D✔ E=deferred(no-frontend-half — lines already name their season) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: pytest (PostgreSQL 16, config.settings.pgtest) ✔
# exceptions: none
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
