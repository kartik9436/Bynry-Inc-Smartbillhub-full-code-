# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-BIL-10067 (one-time bill across a mid-period rate change)
# Ruling:   PO 2026-10-12 — decision log "ONE-TIME BILL ACROSS A MID-PERIOD RATE
#           CHANGE — NINETEEN ISSUES RECORDED, EVERY RULE CONFIRMED, BUILD
#           APPROVED"; BR-RAT-114 AMENDED 2026-10-12 (1)–(4) and Q-a..Q-e.
# Rules:    BR-RAT-114 (as amended) · BR-RAT-002 (tier limits scale with the
#           part) · BR-RAT-090 (a counted item) · CR-062 D6 (storm water's ERU
#           is on the unit) · B4.2 (one tax pass) · B4.3 ❄️ (day-weighted
#           proration, unchanged) · CLAUDE.md rules 2 and 3
# Code:     apps/billing/midperiod.py (split_plan, _apportion_evenly_by_day,
#           price_split_bill) · apps/rating/pricing/stages/price_usage.py and
#           models/capacity.py (the printed rate of a prorated per-item line)
# ───────────────────────────────────────────────────────
"""THE PO'S ONE-TIME BILL, WORKED BEFORE A LINE OF THE FIX WAS WRITTEN.

**The case (decision log 2026-10-12).** A one-time bill for 1–30 September.
Water and sewer were re-priced on 15 September, storm water on 20 September,
trash not at all. The meter read 2.9 on 31 August and 4.6 on 30 September:
**1.7 kgal**.

**The rates are this repo's own demo-utility rates** (`core/sample_fixture`
and `apps/rating/service_base_amounts`), so no figure below is invented:

    water   tiers 0–5 @ $4.00 · 5–15 @ $6.50 · 15+ @ $8.00, base $8.00
            → from 15 Sep the same tiers at $4.40 · $7.15 · $8.80 (+10%)
    sewer   90% of the water volume @ $5.00/kgal, base $9.00
            → from 15 Sep @ $5.50/kgal
    trash   $15.00 per cart, base $0.00 (OQ-317's ruled zero), 1 cart,
            unchanged
    storm   $4.50 per ERU, base $2.00, 1 ERU recorded on the unit
            → from 20 Sep @ $5.00/ERU

**The worked figures (30-day September, B4.3's day weights):**

    water 1–14 Sep   1.7 × 14/30 = 0.793333 kgal @ $4.00  =  $3.17
    water 15–30 Sep  1.7 × 16/30 = 0.906667 kgal @ $4.40  =  $3.99
          (the first tier's 5 kgal is shared by days — 2.33 and 2.67 — and
          neither part reaches it: Q-b)
    water base       ONE row                               =  $8.00
    sewer 1–14 Sep   90% × 0.793333 = 0.714 kgal @ $5.00   =  $3.57
    sewer 15–30 Sep  90% × 0.906667 = 0.816 kgal @ $5.50   =  $4.49
    sewer base       ONE row                               =  $9.00
    trash            ONE row, 1 cart × $15.00              = $15.00
    trash base       ONE row                               =  $0.00
    storm 1–19 Sep   1 ERU × $4.50 × 19/30 → rate $2.85    =  $2.85
    storm 20–30 Sep  1 ERU × $5.00 × 11/30 → rate $1.8333  =  $1.83
    storm base       ONE row                               =  $2.00
                                                   total   = $53.90

**WHAT THE CODE DID BEFORE (the RED this file was proved against):** the cut
set was COMMON, so every service was cut at 15 Sep AND 20 Sep (three parts
each — *"why 3 it is only 2 cuts"*), every base was repeated per part, the
trash cart came out as three rows whose quantity × rate did not equal the
amount, and a demand or time-of-use service crossing a change refused
outright because the apportionment dropped the peak and the window registers.

Pure: the engine is pure and the split's pricing half takes plain data, so
these run on any database in milliseconds. The cut plan is exercised through
`split_plan` itself with its reads stubbed at the seam.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from apps.billing import backbill, gather, midperiod, rating_seam, runs
from apps.billing.contracts import AccountBillingData, ServiceReading
from apps.billing.stages import measure_consumption as mc

CENT = Decimal("0.01")
SEP_1, SEP_30 = date(2026, 9, 1), date(2026, 9, 30)
SEP_14, SEP_15 = date(2026, 9, 14), date(2026, 9, 15)
SEP_19, SEP_20 = date(2026, 9, 19), date(2026, 9, 20)
CYCLE = 30


# ── the fixture's own rates ─────────────────────────────────────────────────
def _tiers(*prices: str) -> tuple[rating_seam.Tier, ...]:
    uppers = (Decimal("5"), Decimal("15"), None)
    return tuple(rating_seam.Tier(upper=u, unit_price=Decimal(p)) for u, p in zip(uppers, prices))


def water(version: str) -> rating_seam.TariffConfig:
    prices = ("4.00", "6.50", "8.00") if version == "old" else ("4.40", "7.15", "8.80")
    return rating_seam.TariffConfig(
        service="water",
        model="tiered",
        billed_unit="kgal",
        base_charge=Decimal("8.00"),
        tiers=_tiers(*prices),
        version_id=f"water-{version}",
        base_charge_code="BASE-W",
    )


def sewer(version: str) -> rating_seam.TariffConfig:
    return rating_seam.TariffConfig(
        service="sewer",
        model="percent_of_service",
        billed_unit="kgal",
        base_charge=Decimal("9.00"),
        unit_price=Decimal("5.00") if version == "old" else Decimal("5.50"),
        percent=Decimal("90"),
        basis_service="water",
        percent_basis="usage",
        version_id=f"sewer-{version}",
        base_charge_code="BASE-S",
    )


def trash() -> rating_seam.TariffConfig:
    return rating_seam.TariffConfig(
        service="trash",
        model="tiered",
        billed_unit="cart",
        base_charge=Decimal("0"),
        tiers=(rating_seam.Tier(upper=None, unit_price=Decimal("15.00")),),
        version_id="trash-v1",
        base_charge_code="BASE-T",
    )


def storm(version: str) -> rating_seam.TariffConfig:
    return rating_seam.TariffConfig(
        service="storm_water",
        model="tiered",
        billed_unit="ERU",
        base_charge=Decimal("2.00"),
        tiers=(
            rating_seam.Tier(
                upper=None, unit_price=Decimal("4.50") if version == "old" else Decimal("5.00")
            ),
        ),
        version_id=f"storm-{version}",
        base_charge_code="BASE-SW",
    )


def water_reading(amount: str | None, *, estimated: bool = False) -> ServiceReading:
    return ServiceReading(
        service_code="water",
        consumption=None if amount is None else rating_seam.Quantity(Decimal(amount), "kgal"),
        estimated=estimated,
        absent_reason=None if amount is not None else "no_read",
    )


def trash_reading() -> ServiceReading:
    return ServiceReading(
        service_code="trash", absent_reason=mc.ABSENT_SERVICE_NOT_METERED, asset_count=1
    )


def storm_reading() -> ServiceReading:
    return ServiceReading(
        service_code="storm_water",
        absent_reason=mc.ABSENT_SERVICE_NOT_METERED,
        installed_capacity=Decimal("1"),
        capacity_uom="ERU",
    )


def account(start: date, end: date, tariffs, readings) -> AccountBillingData:
    return AccountBillingData(
        account_id="acct-54",
        account_no="AC-2026-00054",
        behavior_class="billable",
        currency="USD",
        tax_exempt=False,
        period_start=start,
        period_end=end,
        cycle_days=CYCLE,
        service_days=(end - start).days + 1,
        rate_plan_id="plan-res",
        tariffs=tuple(tariffs),
        readings=tuple(readings),
    )


def segment(start: date, end: date, tariffs, readings) -> midperiod.SplitSegment:
    return midperiod.SplitSegment(
        period_start=start,
        period_end=end,
        plan_id=None,
        tariff_version_ids={t.service: t.version_id for t in tariffs},
        data=account(start, end, tariffs, readings),
    )


def _rows(priced) -> list[tuple[str, str, Decimal | None, Decimal | None, Decimal]]:
    """`(service, kind, quantity, unit_price, amount)` per line, in bill order."""
    return [
        (
            str(line.service),
            line.kind,
            None if line.quantity is None else Decimal(line.quantity),
            None if line.unit_price is None else Decimal(line.unit_price),
            Decimal(line.amount).quantize(CENT),
        )
        for line in priced.lines
        if line.kind in ("usage", "base")
    ]


def _of(rows, service, kind):
    return sorted(amount for svc, k, _q, _r, amount in rows if svc == service and k == kind)


# ══════════════════════════════════════════════════════════════════════════
# B1 · B2 — EACH SERVICE IS CUT ONLY AT ITS OWN CHANGE; SEWER FOLLOWS WATER
# ══════════════════════════════════════════════════════════════════════════
@pytest.fixture
def po_timeline(monkeypatch):
    """`split_plan`'s reads, stubbed AT THE SEAM with the PO's timeline: water
    and sewer re-priced 15 Sep, storm water 20 Sep, trash never; sewer is a
    percentage of water; one plan all month; no base charge-code change."""
    cuts = {"water": (SEP_15,), "sewer": (SEP_15,), "storm_water": (SEP_20,), "trash": ()}
    stretches = [(SEP_1, SEP_30, None)]
    monkeypatch.setattr(midperiod, "_plan_stretches", lambda unit, s, e: list(stretches))
    monkeypatch.setattr(
        midperiod,
        "_tariff_rows_for",
        lambda unit, plan: [{"service_code": code, "tariff": code} for code in cuts],
    )
    monkeypatch.setattr(
        backbill, "version_boundaries", lambda tariff, *, period_start, period_end: cuts[tariff]
    )
    monkeypatch.setattr(backbill, "charge_price_cuts_by_service", lambda codes, **kw: {})
    monkeypatch.setattr(backbill, "_percent_links", lambda rows, s, e: {"sewer": "water"})
    real_resolve = gather._resolve
    monkeypatch.setattr(
        gather,
        "_resolve",
        lambda module, name, *rest: None
        if name in ("plan_version_starts", "pricing_day")
        else real_resolve(module, name, *rest),
    )
    return stretches


def test_b1__each_service_is_cut_only_at_its_own_change(po_timeline):
    """PO: *"why 3 it is only 2 cuts … since ther eis only 1 change in that
    period for given utility service"*. Trash is ONE part; water and sewer are
    cut at 15 Sep together; storm water at 20 Sep alone. Before the fix every
    service was cut at both days: `((None, (15 Sep, 20 Sep)),)`."""
    plan = midperiod.split_plan("unit-54", period_start=SEP_1, period_end=SEP_30)
    assert plan == (
        (("trash",), ()),
        (("sewer", "water"), (SEP_15,)),
        (("storm_water",), (SEP_20,)),
    ), plan


def test_b1__a_plan_reassignment_still_cuts_every_service(po_timeline):
    """Unchanged by the ruling: a plan change on 10 Sep cuts all four services,
    and each service's own change cuts it as well."""
    po_timeline[:] = [(SEP_1, date(2026, 9, 9), "plan-a"), (date(2026, 9, 10), SEP_30, "plan-b")]
    plan = dict(midperiod.split_plan("unit-54", period_start=SEP_1, period_end=SEP_30))
    ten = date(2026, 9, 10)
    assert plan[("trash",)] == (ten,)
    assert plan[("sewer", "water")] == (ten, SEP_15)
    assert plan[("storm_water",)] == (ten, SEP_20)


def test_b1__a_service_with_no_change_is_not_cut_at_all(po_timeline, monkeypatch):
    """Nothing changed for anybody → no cut → no split (the identity)."""
    monkeypatch.setattr(
        backbill, "version_boundaries", lambda tariff, *, period_start, period_end: ()
    )
    assert midperiod.split_plan("unit-54", period_start=SEP_1, period_end=SEP_30) == (
        (None, ()),
    )


# ══════════════════════════════════════════════════════════════════════════
# B2 · B3 · B5 · B6 · Q-b — THE PO'S BILL, PRICED
# ══════════════════════════════════════════════════════════════════════════
def po_segments() -> tuple[midperiod.SplitSegment, ...]:
    """The parts `gather_split` produces for the PO's case once B1 holds, with
    water's 1.7 kgal day-weighted exactly as `_apportion_evenly_by_day` does."""
    return (
        segment(SEP_1, SEP_30, [trash()], [trash_reading()]),
        segment(
            SEP_1,
            SEP_14,
            [water("old"), sewer("old")],
            [water_reading("0.793333", estimated=True)],
        ),
        segment(
            SEP_15,
            SEP_30,
            [water("new"), sewer("new")],
            [water_reading("0.906667", estimated=True)],
        ),
        segment(SEP_1, SEP_19, [storm("old")], [storm_reading()]),
        segment(SEP_20, SEP_30, [storm("new")], [storm_reading()]),
    )


def _po_bill():
    parent = account(
        SEP_1,
        SEP_30,
        [water("new"), sewer("new"), trash(), storm("new")],
        [water_reading("1.7"), trash_reading(), storm_reading()],
    )
    parent = AccountBillingData(**{**parent.__dict__, "split_segments": po_segments()})
    _usage, priced = midperiod.price_split_account(parent)
    return _rows(priced), priced


def test_b2__water_is_split_at_its_own_change_and_sewer_follows_it():
    """1.7 kgal: water 0.793333 @ $4.00 = $3.17 and 0.906667 @ $4.40 = $3.99;
    sewer 90% of each part's water at that part's own rate: $3.57 + $4.49."""
    rows, _ = _po_bill()
    assert _of(rows, "water", "usage") == [Decimal("3.17"), Decimal("3.99")]
    assert _of(rows, "sewer", "usage") == [Decimal("3.57"), Decimal("4.49")]


def test_q_b__each_part_gets_its_share_of_the_tier_limits_by_days():
    """10 kgal over the same split: the first tier's 5 kgal is shared by days,
    2.333333 before and 2.666667 after. 1–14 Sep: 4.666667 kgal = 2.333333 @
    $4.00 + 2.333333 @ $6.50 = $9.33 + $15.17; 15–30 Sep: 5.333333 kgal =
    2.666667 @ $4.40 + 2.666667 @ $7.15 = $11.73 + $19.07."""
    segments = (
        segment(SEP_1, SEP_14, [water("old")], [water_reading("4.666667", estimated=True)]),
        segment(SEP_15, SEP_30, [water("new")], [water_reading("5.333333", estimated=True)]),
    )
    parent = account(SEP_1, SEP_30, [water("new")], [water_reading("10")])
    parent = AccountBillingData(**{**parent.__dict__, "split_segments": segments})
    _usage, priced = midperiod.price_split_account(parent)
    assert _of(_rows(priced), "water", "usage") == sorted(
        [Decimal("9.33"), Decimal("15.17"), Decimal("11.73"), Decimal("19.07")]
    )


def test_b3__one_base_row_per_service_when_the_base_price_did_not_change():
    """Q-a: water $8.00, sewer $9.00, trash $0.00, storm water $2.00 — ONE row
    each, the whole month. Before the fix water printed $3.73 + $4.27, sewer
    $4.20 + $4.80 and storm water $1.27 + $0.73."""
    rows, _ = _po_bill()
    assert _of(rows, "water", "base") == [Decimal("8.00")]
    assert _of(rows, "sewer", "base") == [Decimal("9.00")]
    assert _of(rows, "trash", "base") == [Decimal("0.00")]
    assert _of(rows, "storm_water", "base") == [Decimal("2.00")]


def test_b3__the_one_base_row_names_no_part_of_the_month():
    """A whole-month base row carries no `· 2026-09-01 to 2026-09-14` stamp —
    it was not cut, so a stamp would tell the customer it was."""
    _rows_, priced = _po_bill()
    bases = [line for line in priced.lines if line.kind == "base" and line.service == "water"]
    assert len(bases) == 1
    assert " to 2026-09-" not in bases[0].description


def test_b3__two_base_rows_only_when_the_base_price_itself_changed():
    """The base charge code repriced $8.00 → $9.00 on 15 Sep: the base is cut
    too, 14/30 × 8 + 16/30 × 9 = $3.73 + $4.80 (DEF-BIL-9012's arithmetic)."""
    new = water("new")
    new = rating_seam.TariffConfig(**{**new.__dict__, "base_charge": Decimal("9.00")})
    segments = (
        segment(SEP_1, SEP_14, [water("old")], [water_reading("0.793333", estimated=True)]),
        segment(SEP_15, SEP_30, [new], [water_reading("0.906667", estimated=True)]),
    )
    parent = account(SEP_1, SEP_30, [new], [water_reading("1.7")])
    parent = AccountBillingData(**{**parent.__dict__, "split_segments": segments})
    _usage, priced = midperiod.price_split_account(parent)
    assert _of(_rows(priced), "water", "base") == [Decimal("3.73"), Decimal("4.80")]


def test_b5__trash_unchanged_is_one_row_one_cart_times_the_rate():
    rows, _ = _po_bill()
    trash_usage = [r for r in rows if r[0] == "trash" and r[1] == "usage"]
    assert trash_usage == [("trash", "usage", Decimal("1"), Decimal("15.00"), Decimal("15.00"))]


def test_b5_b6__storm_water_counts_its_eru_and_quantity_times_rate_is_the_amount():
    """1 ERU on each part (never 0), cut at 20 Sep: $2.85 + $1.83. The printed
    rate is the part's rate for the part's days, so 1 × $2.85 = $2.85 and
    1 × $1.8333 = $1.83 — the customer can multiply the line and get it."""
    rows, _ = _po_bill()
    storm_rows = sorted(
        (r for r in rows if r[0] == "storm_water" and r[1] == "usage"), key=lambda r: r[4]
    )
    assert [r[4] for r in storm_rows] == [Decimal("1.83"), Decimal("2.85")]
    for _svc, _kind, quantity, rate, amount in storm_rows:
        assert quantity == Decimal("1"), "storm water must count its ERU, never 0"
        assert (quantity * rate).quantize(CENT) == amount, (quantity, rate, amount)


def test_b5__every_row_foots_quantity_times_rate():
    rows, _ = _po_bill()
    for svc, kind, quantity, rate, amount in rows:
        if kind != "usage" or quantity is None or rate is None:
            continue
        if svc in ("water", "sewer"):
            continue  # tiered lines foot per tier, asserted above
        assert (quantity * rate).quantize(CENT) == amount, (svc, quantity, rate, amount)


def test_the_po_bill_totals_fifty_three_ninety():
    _rows_, priced = _po_bill()
    assert Decimal(priced.total).quantize(CENT) == Decimal("53.90")


# ══════════════════════════════════════════════════════════════════════════
# Q-c · Q-d — TIME-OF-USE AND DEMAND, APPORTIONED BY DAYS THROUGH THE REAL
# `_apportion_evenly_by_day`
# ══════════════════════════════════════════════════════════════════════════
def _apportioned(monkeypatch, period_reading, tariffs_by_part):
    """Two parts with no read of their own, apportioned from the period read."""
    monkeypatch.setattr(runs, "_readings_for", lambda unit_id, **kw: ((period_reading,), ()))
    gathered = [
        (
            start,
            end,
            None,
            {},
            account(
                start,
                end,
                [tariff],
                [ServiceReading(service_code=tariff.service, absent_reason="no_read")],
            ),
        )
        for start, end, tariff in tariffs_by_part
    ]
    out, estimates = midperiod._apportion_evenly_by_day(
        "unit-54", gathered, period_start=SEP_1, period_end=SEP_30, scope_services=None
    )
    segments = tuple(
        midperiod.SplitSegment(
            period_start=start,
            period_end=end,
            plan_id=None,
            tariff_version_ids={},
            data=data,
            estimates=estimates.get(index, ()),
        )
        for index, (start, end, _p, _v, data) in enumerate(out)
    )
    last = tariffs_by_part[-1][2]
    parent = account(SEP_1, SEP_30, [last], [period_reading])
    parent = AccountBillingData(**{**parent.__dict__, "split_segments": segments})
    _usage, priced = midperiod.price_split_account(parent)
    return priced


def demand(version: str) -> rating_seam.TariffConfig:
    old = version == "old"
    return rating_seam.TariffConfig(
        service="electric",
        model="demand",
        billed_unit="kWh",
        base_charge=Decimal("180.00"),
        energy_rate_per_kwh=Decimal("0.0850") if old else Decimal("0.0900"),
        demand_rate_per_kw=Decimal("11.00") if old else Decimal("12.00"),
        version_id=f"demand-{version}",
    )


def test_q_d__demand_kwh_split_by_days_and_the_peak_charged_once_at_the_end_rate(monkeypatch):
    """3,000 kWh and a 20 kW peak; energy $0.085 → $0.090 and demand $11.00 →
    $12.00 from 15 Sep. kWh by days: 1,400 @ $0.085 = $119.00 and 1,600 @
    $0.090 = $144.00. The month's peak ONCE, at the rate in force at the end:
    20 kW × $12.00 = $240.00. Base ONE row $180.00. Before the fix the split
    dropped the peak and the account refused (MissingDemandQuantity)."""
    period = ServiceReading(
        service_code="electric",
        consumption=rating_seam.Quantity(
            Decimal("3000"), "kWh", demand=rating_seam.Quantity(Decimal("20"), "kW")
        ),
    )
    priced = _apportioned(
        monkeypatch, period, [(SEP_1, SEP_14, demand("old")), (SEP_15, SEP_30, demand("new"))]
    )
    rows = _rows(priced)
    kwh = sorted(r[4] for r in rows if r[1] == "usage" and r[3] in (Decimal("0.0850"), Decimal("0.0900")))
    kw = [r for r in rows if r[1] == "usage" and r[2] is not None and r[0] == "electric" and r[4] >= Decimal("200")]
    assert kwh == [Decimal("119.00"), Decimal("144.00")], rows
    assert [(r[2], r[3], r[4]) for r in kw] == [
        (Decimal("20"), Decimal("12.00"), Decimal("240.00"))
    ], rows
    assert _of(rows, "electric", "base") == [Decimal("180.00")]
    assert Decimal(priced.total).quantize(CENT) == Decimal("683.00")


def tou(version: str) -> rating_seam.TariffConfig:
    old = version == "old"
    return rating_seam.TariffConfig(
        service="electric",
        model="time_of_use",
        billed_unit="kWh",
        base_charge=Decimal("12.00"),
        windows=(
            rating_seam.TouWindow(
                label="On-peak", unit_price=Decimal("0.22" if old else "0.24"), channel="tou_on"
            ),
            rating_seam.TouWindow(
                label="Off-peak", unit_price=Decimal("0.08" if old else "0.09"), channel="tou_off"
            ),
        ),
        version_id=f"tou-{version}",
    )


def test_q_c__each_time_of_use_window_is_split_by_days_at_that_parts_prices(monkeypatch):
    """On-peak 300 kWh and off-peak 600 kWh; on $0.22 → $0.24, off $0.08 →
    $0.09 from 15 Sep. On: 140 @ $0.22 = $30.80 + 160 @ $0.24 = $38.40; off:
    280 @ $0.08 = $22.40 + 320 @ $0.09 = $28.80. Base ONE row $12.00. Before
    the fix the split dropped the window registers and the account refused
    (MissingWindowQuantity)."""
    period = ServiceReading(
        service_code="electric",
        consumption=rating_seam.Quantity(
            Decimal("900"),
            "kWh",
            windows=(
                rating_seam.WindowQuantity(
                    channel="tou_on", quantity=rating_seam.Quantity(Decimal("300"), "kWh")
                ),
                rating_seam.WindowQuantity(
                    channel="tou_off", quantity=rating_seam.Quantity(Decimal("600"), "kWh")
                ),
            ),
        ),
    )
    priced = _apportioned(
        monkeypatch, period, [(SEP_1, SEP_14, tou("old")), (SEP_15, SEP_30, tou("new"))]
    )
    rows = _rows(priced)
    assert _of(rows, "electric", "usage") == sorted(
        [Decimal("30.80"), Decimal("38.40"), Decimal("22.40"), Decimal("28.80")]
    ), rows
    assert _of(rows, "electric", "base") == [Decimal("12.00")]


def seasonal_tariff() -> rating_seam.TariffConfig:
    return rating_seam.TariffConfig(
        service="electric",
        model="seasonal",
        billed_unit="kWh",
        base_charge=Decimal("12.00"),
        season="summer",
        season_tiers=(
            rating_seam.SeasonTiers(
                season="summer",
                tiers=(rating_seam.Tier(upper=None, unit_price=Decimal("0.12")),),
            ),
            rating_seam.SeasonTiers(
                season="winter",
                tiers=(rating_seam.Tier(upper=None, unit_price=Decimal("0.10")),),
            ),
        ),
        season_days=(
            rating_seam.SeasonDays(season="summer", days=14),
            rating_seam.SeasonDays(season="winter", days=16),
        ),
        version_id="seasonal-v1",
    )


def test_q_e__a_season_change_cuts_like_a_rate_change():
    """Summer $0.12 through 14 Sep, winter $0.10 from 15 Sep, 900 kWh, no rate
    change: by days, 420 @ $0.12 = $50.40 and 480 @ $0.10 = $48.00, base ONE
    row. ⚠ NOT RED BEFORE THE FIX: BR-RAT-034's season split (GT-34) already
    cuts by days inside the engine; this pins that Q-e is the same arithmetic
    as a rate change and that nothing here moved it."""
    data = account(
        SEP_1,
        SEP_30,
        [seasonal_tariff()],
        [
            ServiceReading(
                service_code="electric",
                consumption=rating_seam.Quantity(Decimal("900"), "kWh"),
            )
        ],
    )
    priced = runs.price_account(data).priced
    rows = _rows(priced)
    assert _of(rows, "electric", "usage") == [Decimal("48.00"), Decimal("50.40")], rows
    assert _of(rows, "electric", "base") == [Decimal("12.00")]


# ══════════════════════════════════════════════════════════════════════════
# THE CUT AND THE APPORTIONMENT TOGETHER — the PO's 0.79 + 0.91
# ══════════════════════════════════════════════════════════════════════════
def test_the_po_reading_is_one_point_seven_and_splits_point_seven_nine_and_point_nine_one(
    monkeypatch,
):
    """2.9 → 4.6 = 1.7 kgal, no read on 15 Sep: 1.7 × 14/30 = 0.793333 and
    1.7 × 16/30 = 0.906667 — the PO's *"0.79 kgal + 0.91 kgal"*."""
    period = water_reading("1.7")
    monkeypatch.setattr(runs, "_readings_for", lambda unit_id, **kw: ((period,), ()))
    gathered = [
        (s, e, None, {}, account(s, e, [water(v)], [water_reading(None)]))
        for s, e, v in ((SEP_1, SEP_14, "old"), (SEP_15, SEP_30, "new"))
    ]
    out, _est = midperiod._apportion_evenly_by_day(
        "unit-54", gathered, period_start=SEP_1, period_end=SEP_30, scope_services=None
    )
    amounts = [data.readings[0].consumption.amount for *_x, data in out]
    assert amounts == [Decimal("0.793333"), Decimal("0.906667")]
    assert all(data.readings[0].estimated for *_x, data in out)


def test_a_reading_dated_on_the_change_day_wins_over_the_even_split(monkeypatch):
    """A read on 14 Sep of 0.5 and 1.2 by 30 Sep measures each part: nothing is
    derived (BR-RAT-114, unchanged) — 0.5 and 1.2, not 0.79 and 0.91."""
    monkeypatch.setattr(runs, "_readings_for", lambda unit_id, **kw: pytest.fail("not asked"))
    gathered = [
        (SEP_1, SEP_14, None, {}, account(SEP_1, SEP_14, [water("old")], [water_reading("0.5")])),
        (SEP_15, SEP_30, None, {}, account(SEP_15, SEP_30, [water("new")], [water_reading("1.2")])),
    ]
    out, est = midperiod._apportion_evenly_by_day(
        "unit-54", gathered, period_start=SEP_1, period_end=SEP_30, scope_services=None
    )
    assert [data.readings[0].consumption.amount for *_x, data in out] == [
        Decimal("0.5"),
        Decimal("1.2"),
    ]
    assert est == {}


# ══════════════════════════════════════════════════════════════════════════
# THE COORDINATOR'S WALK OF 2026-10-12 (05-prototype/otb-before-2026-10-12)
# ══════════════════════════════════════════════════════════════════════════
def test_parts_add_back_to_the_meter_never_799_999999(monkeypatch):
    """800 kWh cut at 15 and 20 Sep: 14, 5 and 11 days of 30. Each share is
    quantized to 6 places, so they summed to 799.999999 on the draft. The last
    part takes the remainder: 373.333333 + 133.333333 + 293.333334 = 800."""
    period = ServiceReading(
        service_code="electric", consumption=rating_seam.Quantity(Decimal("800"), "kWh")
    )
    monkeypatch.setattr(runs, "_readings_for", lambda unit_id, **kw: ((period,), ()))
    parts = ((SEP_1, SEP_14), (SEP_15, SEP_19), (SEP_20, SEP_30))
    gathered = [
        (
            s,
            e,
            None,
            {},
            account(
                s,
                e,
                [demand("new")],
                [ServiceReading(service_code="electric", absent_reason="no_read")],
            ),
        )
        for s, e in parts
    ]
    out, _est = midperiod._apportion_evenly_by_day(
        "unit-12", gathered, period_start=SEP_1, period_end=SEP_30, scope_services=None
    )
    amounts = [data.readings[0].consumption.amount for *_x, data in out]
    assert amounts == [Decimal("373.333333"), Decimal("133.333333"), Decimal("293.333334")]
    assert sum(amounts) == Decimal("800")


def test_q_b__an_interim_part_falls_back_to_the_whole_window_never_its_own_length(monkeypatch):
    """Where the cycle's calendar cannot be read, a part of an interim bill was
    divided by ITS OWN length — a factor of 1, so every part got the FULL first
    tier (the walk's 800 kWh at $91.60, below both prices). It falls back to the
    whole window's 30 days, as the final bill always did: 1–14 Sep is 14/30."""
    from apps.billing import final_bill, one_time

    monkeypatch.setattr(final_bill, "_closing_cycle_days", lambda unit_id, *, as_of: None)
    monkeypatch.setattr(
        gather,
        "_resolve",
        lambda module, name, *rest: (lambda account_id: {"unit_id": "unit-12"})
        if name == "account_detail"
        else None,
    )
    request = one_time.OneTimeRequest(
        account_id="acct-12", kind="interim", period_start=SEP_1, period_end=SEP_30
    )
    per_part = one_time._interim_part_cycle_days(request)
    assert per_part(SEP_1, SEP_14) == 30
    assert per_part(SEP_15, SEP_19) == 30

