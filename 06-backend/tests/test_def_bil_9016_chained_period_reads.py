# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-012 (the one-time bill) · US-BIL-001/004 (the bulk run) ·
#           US-MET-0xx (billing's reads seam)
#           Screens: the one-time bill · S31.2 (the run's priced lines)
# Rules:    BR-MET-019 (consumption = (current − prior) × multiplier) ·
#           BR-BIL-030 (the bill prints each meter's prior and current read,
#           and they must foot) · DEF-BIL-5270 (the cycle run opens at the last
#           issued bill's closing read) · BR-RAT-034 (+ DEF-RAT-8849's
#           season-change-day reading)
# Defect:   DEF-BIL-9016
# ───────────────────────────────────────────────────────
"""A READING PARTWAY THROUGH THE PERIOD NO LONGER LOSES THE USAGE BEFORE IT.

`DEF-BIL-9016`, found 2026-10-01 while building the season-change-day reading.
Metering stores each reading as measured from the reading before it, which is
the normal case. Billing took the period's quantity from the NEWEST reading
alone. So with dials **1,000** (15 Oct, the opening), **1,200** (1 Nov) and
**1,300** (13 Nov), a one-time bill charged **100 kWh = $10.00** where **300 kWh
= $30.00** were used (winter, $0.10 a kWh). The cycle run was rescued by the
last-bill anchor for a single register, and REFUSED a time-of-use meter.

The fix is in metering's reads seam: the period's quantity is the sum of the
CHAINED readings back to the period's opening dial, and the bill's prior read
is that opening dial, so `1,000 → 1,300` charges 300 and foots.

⚠ **THE OPENING READING IS NOT COUNTED.** A reading dated the period's first
day is the dial at the instant the period opens (metering stamps a reading at
00:00 of its date); its own usage belongs to the period before. Every opening
reading below carries 50 kWh of the previous period, so a bill that counted it
would be 50 too high.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from apps.billing import models as billing_models
from apps.billing import runs
from apps.rating import models as rating_models

from tests.test_def_rat_8849_season_change_read import (
    CUT_LINES,
    CUT_USAGE,
    a_tou_world_read_on,
)
from tests.test_oq234_season_split import (
    WE18_END,
    WE18_START,
    WINDOWS,
    WINTER_END,
    WINTER_START,
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


DIALS = (("1000", "950", "50"), ("1200", "1000", "200"), ("1300", "1200", "100"))


def a_seasonal_meter(tenant, actor, *, start, end, middle, account_no, asset_no, dials=DIALS):
    """Summer $0.12, winter $0.10. Dials 1,000 (opening) → 1,200 → 1,300, chained."""
    plan = make_plan(tenant, name=f"Seasonal flat {account_no}", services=("electric",))
    version, seasons = _version(tenant, plan, "seasonal")
    for seq, (label, price) in enumerate((("Summer", "0.120000"), ("Winter", "0.100000")), 1):
        rating_models.RateTier.objects.create(
            tenant=tenant,
            tariff_version=version,
            season=seasons[label],
            seq=seq,
            from_qty=Decimal("0"),
            to_qty=None,
            unit_price=Decimal(price),
        )
    _base_code_and_taxes(tenant, plan)
    account, asset, cycle = _metered_account(tenant, actor, plan, start, end, account_no, asset_no)
    for day, (value, prior, used) in zip((start.isoformat(), middle, end.isoformat()), dials):
        commit_read(
            actor,
            asset["id"],
            day=day,
            value=value,
            prior_value=prior,
            consumption=used,
            unit="kWh",
        )
    return account, cycle


def _lines(invoice):
    return sorted((line.quantity, _round(line.amount)) for line in _usage(invoice))


# ── The coordinator's figure: 1,000 / 1,200 / 1,300 is 300 kWh, $30.00 ─────


def test_def_bil_9016_a_one_time_bill_charges_the_whole_period(brazos, dana):
    with tenant_ctx(brazos):
        account, _cycle = a_seasonal_meter(
            brazos,
            dana,
            start=WINTER_START,
            end=WINTER_END,
            middle="2026-11-01",
            account_no="A-90161",
            asset_no="M-9016",
        )
        invoice = _one_time(account, WINTER_START, WINTER_END)
        assert _lines(invoice) == [(Decimal("300"), Decimal("30.00"))]
        # BR-BIL-030 — the pair the bill prints foots against what it charges.
        readings, _unmeasured = runs.readings_for_account(
            account, period_start=WINTER_START, period_end=WINTER_END, scope_services=None
        )
        reading = next(r for r in readings if r.service_code == "electric")
        assert (reading.prior_read, reading.current_read, reading.consumption.amount) == (
            Decimal("1000"),
            Decimal("1300"),
            Decimal("300"),
        )


def test_def_bil_9016_the_bulk_run_charges_the_whole_period(brazos, dana):
    with tenant_ctx(brazos):
        _account, cycle = a_seasonal_meter(
            brazos,
            dana,
            start=WINTER_START,
            end=WINTER_END,
            middle="2026-11-01",
            account_no="A-90162",
            asset_no="M-9017",
        )
        invoice = _bulk(cycle, WINTER_START, WINTER_END)
        assert _lines(invoice) == [(Decimal("300"), Decimal("30.00"))]


# ── With seasons, the season-change-day reading still cuts ─────────────────


def test_def_bil_9016_a_one_time_bill_across_the_season_change_cuts_at_the_reading(brazos, dana):
    """200 used before 1 Oct at summer's $0.12 = $24.00, 100 after at winter's
    $0.10 = $10.00 (DEF-RAT-8849) — where the bill used to charge only 100."""
    with tenant_ctx(brazos):
        account, _cycle = a_seasonal_meter(
            brazos,
            dana,
            start=WE18_START,
            end=WE18_END,
            middle="2026-10-01",
            account_no="A-90163",
            asset_no="M-9018",
        )
        invoice = _one_time(account, WE18_START, WE18_END)
        assert _lines(invoice) == [
            (Decimal("100"), Decimal("10.00")),
            (Decimal("200"), Decimal("24.00")),
        ]


# ── A time-of-use meter on the cycle run, after an issued bill ─────────────


def test_def_bil_9016_a_tou_meter_on_the_cycle_run_bills_every_register(brazos, dana):
    """The last issued bill closed every register on 14 Sep. Before the fix the
    run refused the account (`ANCHOR_TOU_UNANCHORABLE`), because the closing
    reading was measured from 1 Oct rather than from where that bill closed.
    Now each register counts from 14 Sep: on-peak 80 + 40, cut on 1 Oct."""
    with tenant_ctx(brazos):
        plan = make_plan(brazos, name="Seasonal TOU A-90164", services=("electric",))
        version, seasons = _version(brazos, plan, "time_of_use")
        for label, channel, t_start, t_end, summer, winter, _qty in WINDOWS:
            for season, price in (("Summer", summer), ("Winter", winter)):
                rating_models.TimeOfUseWindow.objects.create(
                    tenant=brazos,
                    tariff_version=version,
                    season=seasons[season],
                    label=label,
                    day_type="weekday",
                    start_time=t_start,
                    end_time=t_end,
                    unit_price=Decimal(price),
                    channel=channel,
                )
        _base_code_and_taxes(brazos, plan)
        account, asset, cycle = _metered_account(
            brazos, dana, plan, WE18_START, WE18_END, "A-90164", "M-9019"
        )
        before = {"total": 400, "tou_on": 80, "tou_mid": 110, "tou_off": 210}
        whole = {"total": 700, "tou_on": 120, "tou_mid": 200, "tou_off": 380}
        closing_total = None
        for channel, opening in (
            ("total", 5000),
            ("tou_on", 1000),
            ("tou_mid", 2000),
            ("tou_off", 3000),
        ):
            read = commit_read(
                dana,
                asset["id"],
                day="2026-09-14",
                value=str(opening),
                channel=channel,
                prior_value=str(opening - 50),
                consumption="50",
                unit="kWh",
            )
            if channel == "total":
                closing_total = read
            day = opening + before[channel]
            commit_read(
                dana,
                asset["id"],
                day="2026-10-01",
                value=str(day),
                channel=channel,
                prior_value=str(opening),
                consumption=str(before[channel]),
                unit="kWh",
            )
            commit_read(
                dana,
                asset["id"],
                day=WE18_END.isoformat(),
                value=str(opening + whole[channel]),
                channel=channel,
                prior_value=str(day),
                consumption=str(whole[channel] - before[channel]),
                unit="kWh",
            )
        billing_models.Invoice.objects.create(
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
            bill_payload={"services": [{"code": "electric", "read_id": str(closing_total.id)}]},
        )
        invoice = _bulk(cycle, WE18_START, WE18_END)
        usage = list(_usage(invoice))
        assert sorted(_round(line.amount) for line in usage) == CUT_LINES
        assert _round(sum(line.amount for line in usage)) == CUT_USAGE


# ── An estimate the next reading measured across is not counted twice ──────


def test_def_bil_9016_an_estimate_measured_across_is_not_counted_twice(brazos, dana):
    """On-peak: an ESTIMATE of 80 on 1 Oct (no dial) and an actual 14 Oct
    reading measured from the opening dial (120). The period is 120, never
    80 + 120 = 200; with no actual reading on 1 Oct it splits by days, 64 / 56."""
    with tenant_ctx(brazos):
        account, _cycle = a_tou_world_read_on(
            brazos, dana, account_no="A-90165", asset_no="M-9020", estimated=True
        )
        invoice = _one_time(account, WE18_START, WE18_END)
        on_peak = sorted(line.quantity for line in _usage(invoice) if "On-peak" in line.description)
        assert on_peak == [Decimal("56"), Decimal("64")]


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-BIL-9016 · BR-MET-019 · BR-BIL-030 · DEF-BIL-5270 · DEF-RAT-8849
# generated: 2026-10-02 by the season-change-reading lane
# checklist: A✔ B✔ C✔ D✔ E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: pytest (PostgreSQL 16, config.settings.pgtest) ✔
# exceptions: none
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
