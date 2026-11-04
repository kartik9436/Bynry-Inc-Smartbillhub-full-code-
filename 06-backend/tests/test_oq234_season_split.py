# ── Trace ──────────────────────────────────────────────
# Story:    US-RAT-012 (usage pricing — TOU) · US-RAT-007 (seasonal structure) ·
#           US-BIL-001/004 (the bulk run) · US-BIL-012 (the one-time bill)
#           Screens: S31.2 (the run's priced lines) · the one-time bill
# Rules:    BR-RAT-034 (CONFIRMED, PO R5-7 — season boundaries split the bill
#           period pro-rata by calendar days) · BR-RAT-021 · BR-RAT-033 ·
#           BR-RAT-007 (one tariff version on the service date)
# Golden:   GT-34 (= WE-18) — the bulk-run and one-time halves of the figure
#           tests/golden/test_gt34_season_crossing_period.py pins on the engine.
# Defect:   DEF-RAT-8832 · OQ-234 CLOSED 2026-09-07 (decision log "TWO RULINGS
#           IN ONE BREATH") · built 2026-10-01 (decision log "OQ-234 BUILT")
# ───────────────────────────────────────────────────────
"""THE SEASON-CROSSING SPLIT, end to end on real rows, through BOTH bill doors.

PO, 2026-09-07, verbatim: *"please split  swithch it on"*. The ruling: a bill
period that crosses a season boundary splits pro-rata by calendar days
(BR-RAT-034), and the `seasonal` model is registered. Neither was built until
2026-10-01, and DEF-RAT-8832's walk found the cost: a Seasonal schedule saves
and reads *In force* and every bill on it is refused.

WE-18 (04-docs/05-modules/07-billing/08-worked-examples.md), the figure the PO
was shown: 15 Sep – 14 Oct, the season flips 1 Oct, 16 summer days and 14
winter days of 30; on-peak 120 kWh → 64 × 0.22 = $14.08 + 56 × 0.18 = $10.08;
usage **$82.72**, base $12.00, four authorities' tax $8.95, total **$103.67**.
Before this commit the product billed that period entirely at WINTER prices —
on-peak `120 × 0.18 = $21.60` — and the bill footed perfectly.

THE PROPERTY UNDER TEST IS *ONE PATH*. The bulk run (`runs.prepare_run` →
`runs.calculate_account`) and the one-time bill (`one_time.create`) must reach
the same figure, because both go through `gather.gather_account`, which is the
one place the served span is handed to rating and rating counts the days.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from apps.billing import models as billing_models
from apps.billing import one_time, runs
from apps.customers import models as customer_models
from apps.metering import models as metering_models
from apps.rating import models as rating_models
from apps.rating import selectors as rating_selectors
from apps.tenancy import models as tenancy_models

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import (
    make_plan,
    make_premises,
    make_unit,
    state_size_axis,
    tenant_ctx,
)
from tests.test_us_met_reads_helpers import a_meter, commit_read

pytestmark = pytest.mark.django_db

WE18_START = date(2026, 9, 15)
WE18_END = date(2026, 10, 14)
#: A period entirely inside winter — must price EXACTLY as before the split.
WINTER_START = date(2026, 10, 15)
WINTER_END = date(2026, 11, 13)

SUMMER = ("Summer", 6, 1, 9, 30)
WINTER = ("Winter", 10, 1, 5, 31)
#: (label, channel, start, end, summer price, winter price, WE-18 quantity)
WINDOWS = (
    ("On-peak", "tou_on", "14:00", "20:00", "0.220000", "0.180000", "120"),
    ("Mid-peak", "tou_mid", "06:00", "14:00", "0.140000", "0.120000", "200"),
    ("Off-peak", "tou_off", "20:00", "06:00", "0.090000", "0.080000", "380"),
)
BASE = Decimal("12.000000")
AUTHORITIES = (
    ("TX State", "0.062500"),
    ("Travis County", "0.010000"),
    ("City franchise", "0.020000"),
    ("PUC", "0.002000"),
)

WE18_USAGE = Decimal("82.72")
WE18_TOTAL = Decimal("103.67")
WE18_LINES = sorted(Decimal(x) for x in ("14.08", "10.08", "14.93", "11.20", "18.24", "14.19"))
#: The one-season answer for the winter-only period: 120×.18 + 200×.12 + 380×.08.
WINTER_LINES = sorted(Decimal(x) for x in ("21.60", "24.00", "30.40"))


def _version(tenant, plan, model):
    row = rating_selectors.plan_rate_schedules(plan.id)[0]
    version = rating_models.TariffVersion.objects.create(
        tenant=tenant,
        tariff=row["tariff"],
        model=model,
        base_charge=BASE,
        uom="kWh",
        currency="USD",
        effective_from=date(2026, 1, 1),
    )
    seasons = {}
    for label, sm, sd, em, ed in (SUMMER, WINTER):
        seasons[label] = rating_models.RateSeason.objects.create(
            tenant=tenant,
            tariff_version=version,
            label=label,
            start_month=sm,
            start_day=sd,
            end_month=em,
            end_day=ed,
        )
    state_size_axis(version, "electric")
    return version, seasons


def _base_code_and_taxes(tenant, plan):
    from tests.base_code_naming import name_base_code

    base_code, _ = rating_models.Charge.objects.get_or_create(
        tenant=tenant,
        code="BASE-ELECTRIC-OQ234",
        defaults=dict(
            name="Electric base",
            charge_type="recurring",
            amount_rule="flat",
            amount=BASE,
            service=tenancy_models.Service.objects.get(code="electric"),
            is_base=True,
        ),
    )
    name_base_code(tenant, base_code)  # DEF-RAT-9832 — unnamed bills $0.00
    for name, rate in AUTHORITIES:
        jurisdiction = rating_models.TaxJurisdiction.objects.create(
            tenant=tenant, name=name, authority=name
        )
        rating_models.Tax.objects.create(
            tenant=tenant,
            jurisdiction=jurisdiction,
            name=name,
            kind="percent",
            rate=Decimal(rate),
        )
        rating_models.PlanTaxRule.objects.create(
            tenant=tenant, rate_plan=plan, jurisdiction=jurisdiction
        )


def a_tou_world(tenant, actor, *, start, end, account_no="A-34001", asset_no="M-3401"):
    """WE-18's tariff and registers on real rows; a cycle covering the period."""
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
    account, asset, cycle = _metered_account(tenant, actor, plan, start, end, account_no, asset_no)
    # The meter's TOTAL register (700 = 120 + 200 + 380) — a real TOU meter
    # carries one (BR-MET decision 2026-09-07 (2)(c)), and it is the read the
    # meter's multiplier is answered from.
    commit_read(actor, asset["id"], day=start.isoformat(), value="0", unit="kWh")
    commit_read(
        actor,
        asset["id"],
        day=end.isoformat(),
        value="700",
        prior_value="0",
        consumption="700",
        unit="kWh",
    )
    for _label, channel, _s, _e, _summer, _winter, qty in WINDOWS:
        commit_read(
            actor,
            asset["id"],
            day=start.isoformat(),
            value="0",
            channel=channel,
            unit="kWh",
        )
        commit_read(
            actor,
            asset["id"],
            day=end.isoformat(),
            value=qty,
            channel=channel,
            prior_value="0",
            consumption=qty,
            unit="kWh",
        )
    return account, cycle


def a_seasonal_world(tenant, actor, *, start, end, account_no="A-34101", asset_no="M-3501"):
    """Structure = Seasonal: one flat price per season, one total register.

    Summer $0.12, winter $0.10 per kWh, 300 kWh measured.
    """
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
    commit_read(actor, asset["id"], day=start.isoformat(), value="1000", unit="kWh")
    commit_read(
        actor,
        asset["id"],
        day=end.isoformat(),
        value="1300",
        prior_value="1000",
        consumption="300",
        unit="kWh",
    )
    return account, cycle


def _metered_account(tenant, actor, plan, start, end, account_no, asset_no):
    from apps.metering import services as metering_services

    cycle = metering_models.Cycle.objects.create(
        tenant=tenant,
        code=f"C-{account_no}",
        start_day=start.day,
        days_to_complete=(end - start).days + 1,
    )
    premises = make_premises(actor, address_line=f"{asset_no} Season Ln")
    unit = make_unit(actor, premises["id"], label=account_no, services=["electric"])
    asset = a_meter(actor, asset_no=asset_no, unit_id=unit["id"])
    metering_models.ServicePoint.objects.filter(tenant=tenant, unit_id=unit["id"]).update(
        cycle=cycle
    )
    metering_services.assign_unit_plan(
        actor, unit["id"], {"tariff_id": str(plan.id), "effective_from": "2026-01-01"}
    )
    account = customer_models.Account.objects.create(
        tenant=tenant,
        unit_id=unit["id"],
        account_no=account_no,
        status=customer_models.AccountStatus.objects.get(tenant=tenant, code="active"),
        account_type=customer_models.AccountType.objects.first(),
    )
    return account, asset, cycle


def _bulk(cycle, start, end):
    prepared = runs.prepare_run(
        cycle_id=cycle.id, period_start=start, period_end=end, service_date=end
    )
    assert prepared.ready, (prepared.blocked, prepared.decisions, prepared.silent)
    return runs.calculate_account(prepared.ready[0], service_date=end)


def _one_time(account, start, end):
    body = one_time.create(
        one_time.OneTimeRequest(
            account_id=str(account.id),
            kind=one_time.KIND_INTERIM,
            period_start=start,
            period_end=end,
        ),
        run_by=None,
        actor=None,
    )
    return billing_models.Invoice.objects.get(pk=body["invoice_id"])


def _usage(invoice):
    return billing_models.InvoiceLine.objects.filter(invoice=invoice, kind="usage")


def _round(value):
    return Decimal(value).quantize(Decimal("0.01"))


# ── WE-18 through the BULK RUN ─────────────────────────────────────────────


def test_oq234_we18_through_the_bulk_run(brazos, dana):
    with tenant_ctx(brazos):
        _account, cycle = a_tou_world(brazos, dana, start=WE18_START, end=WE18_END)
        invoice = _bulk(cycle, WE18_START, WE18_END)
        usage = list(_usage(invoice))
        assert sorted(_round(line.amount) for line in usage) == WE18_LINES
        assert _round(sum(line.amount for line in usage)) == WE18_USAGE
        assert _round(invoice.total) == WE18_TOTAL
        # Each window's two shares add back to the register that was read.
        on_peak = [line.quantity for line in usage if "On-peak" in line.description]
        assert sum(on_peak) == Decimal("120")


# ── WE-18 through a ONE-TIME bill (interim) ────────────────────────────────


def test_oq234_we18_through_a_one_time_bill(brazos, dana):
    with tenant_ctx(brazos):
        account, _cycle = a_tou_world(
            brazos, dana, start=WE18_START, end=WE18_END, account_no="A-34002", asset_no="M-3402"
        )
        invoice = _one_time(account, WE18_START, WE18_END)
        usage = list(_usage(invoice))
        assert sorted(_round(line.amount) for line in usage) == WE18_LINES
        assert _round(sum(line.amount for line in usage)) == WE18_USAGE
        assert _round(invoice.total) == WE18_TOTAL


# ── A period inside one season is unchanged ────────────────────────────────


def test_oq234_a_period_inside_one_season_prices_exactly_as_before(brazos, dana):
    with tenant_ctx(brazos):
        _account, cycle = a_tou_world(
            brazos,
            dana,
            start=WINTER_START,
            end=WINTER_END,
            account_no="A-34003",
            asset_no="M-3403",
        )
        invoice = _bulk(cycle, WINTER_START, WINTER_END)
        usage = list(_usage(invoice))
        assert sorted(_round(line.amount) for line in usage) == WINTER_LINES
        # no season wording on an unsplit line — byte-identical descriptions
        assert all("days)" not in line.description for line in usage)


# ── A Seasonal schedule bill is no longer refused (DEF-RAT-8832) ───────────


def test_oq234_a_seasonal_schedule_bills_inside_one_season(brazos, dana):
    """300 kWh in winter at $0.10 = $30.00 — the bill DEF-RAT-8832 found refused
    with *"No tariff model plugin registered for seasonal"*."""
    with tenant_ctx(brazos):
        account, _cycle = a_seasonal_world(brazos, dana, start=WINTER_START, end=WINTER_END)
        invoice = _one_time(account, WINTER_START, WINTER_END)
        usage = list(_usage(invoice))
        assert [_round(line.amount) for line in usage] == [Decimal("30.00")]


def test_oq234_a_seasonal_schedule_splits_a_season_crossing_period(brazos, dana):
    """300 kWh over 16 summer + 14 winter days: 160 × 0.12 = $19.20 plus
    140 × 0.10 = $14.00 — through the bulk run, the same path as WE-18."""
    with tenant_ctx(brazos):
        _account, cycle = a_seasonal_world(
            brazos, dana, start=WE18_START, end=WE18_END, account_no="A-34102", asset_no="M-3502"
        )
        invoice = _bulk(cycle, WE18_START, WE18_END)
        usage = sorted(_round(line.amount) for line in _usage(invoice))
        assert usage == [Decimal("14.00"), Decimal("19.20")]


# ── Lifecycle ─────────────────────────────────────────────
# packet: OQ-234 (CLOSED 2026-09-07) · DEF-RAT-8832 · WE-18/GT-34 · BR-RAT-034
# generated: 2026-10-01 by the season-split lane — proved RED on tip b1b382638 on PostgreSQL 16 first: 4 failed, 1 passed — both WE-18 cases billed [21.60, 24.00, 30.40] (winter throughout) where WE-18 is six split lines; both seasonal cases raised `UnknownPricingModel: no tariff model plugin registered for 'seasonal'`; the inside-one-season case PASSED on the tip, which is the guarantee it states
# checklist: A✔ B✔ C✔ D✔ E=deferred(no-frontend-half — the wizard already offers Seasonal) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: pytest (PostgreSQL 16, config.settings.pgtest) ✔
# exceptions: none
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
