# ── Trace ──────────────────────────────────────────────
# Story:    US-RAT-012 (usage pricing — TC-5, the TOU case) · US-RAT-015
#           (TC-1/TC-5: the model resolves through the registry, an
#           unregistered one refuses)
#           Screens: — (the per-window lines render in S31.2 and on the bill)
# Rules:    BR-RAT-021 (TOU v1 = Option B; reads arrive PRE-SPLIT per window;
#           per-season prices) · BR-RAT-033 (coverage; holidays resolve to the
#           season's off-peak = LOWEST-PRICE window) · BR-RAT-003 (no plugin
#           rounds) · BR-RAT-038 (UoM gate) · BR-RAT-044 (one interface)
# Golden:   GT-17 (= WE-1, the reference bill, recomputed from raw inputs by
#           10-scripts/03-golden-verify.py): 120 x 0.22 + 200 x 0.14 +
#           380 x 0.09 = 26.40 + 28.00 + 34.20 = 88.60 — the 4100 posting
# Tests:    this file (US-RAT-012 TC-5 + the negative paths)
# Impacts:  apps/rating/pricing/models/tou.py 🔒
# ───────────────────────────────────────────────────────
"""US-RAT-012 TC-5 — time-of-use pricing, rule by rule.

THE FIGURE THIS BINDS TO IS FROZEN, AND IT IS NOT A NEW ONE. B5's allocation
table maps the billing workbook onto GT numbers (WE-n -> GT-16+n), so the
reference bill WE-1 is GT-17, and `10-scripts/03-golden-verify.py` recomputes
its electric usage from raw inputs as check #1 of 33:

    usage = [r2(D(q) * D(p)) for q, p in [("120","0.22"),("200","0.14"),("380","0.09")]]

Sum 88.60. This file asserts the engine reaches the same number through the
plugin, and then asserts the RULES that figure does not discriminate — the
refusals, which are where a pricing engine earns its keep.
"""

from decimal import Decimal

import pytest

from apps.billing import rating_seam
from apps.rating.pricing import errors

USD = "USD"
ACCOUNT = rating_seam.AccountContext(currency=USD, tax_exempt=False)
FULL_MONTH = rating_seam.BillingPeriod(cycle_days=31, service_days=31)

#: The demo tenant's own summer window set (seed_demo `_TOU_WINDOWS`) at the
#: workbook's Residential Standard summer prices — "summer on $0.22 / mid $0.14
#: / off $0.09" ([W] §1), which is what GT-17 prices.
SUMMER_WINDOWS = (
    rating_seam.TouWindow(
        label="On-peak", unit_price=Decimal("0.22"), channel="tou_on", season="Summer"
    ),
    rating_seam.TouWindow(
        label="Mid-peak", unit_price=Decimal("0.14"), channel="tou_mid", season="Summer"
    ),
    rating_seam.TouWindow(
        label="Off-peak", unit_price=Decimal("0.09"), channel="tou_off", season="Summer"
    ),
)


def tou_tariff(**overrides):
    base = {
        "service": "electric",
        "model": "time_of_use",
        "billed_unit": "kWh",
        "base_charge": None,
        "windows": SUMMER_WINDOWS,
        "season": "Summer",
    }
    base.update(overrides)
    return rating_seam.TariffConfig(**base)


def split(on="120", mid="200", off="380", unit="kWh"):
    """WE-1's own pre-split window quantities (BR-RAT-021)."""
    return rating_seam.Quantity(
        amount=Decimal(on) + Decimal(mid) + Decimal(off),
        unit=unit,
        windows=(
            rating_seam.WindowQuantity(
                channel="tou_on", quantity=rating_seam.Quantity(Decimal(on), unit)
            ),
            rating_seam.WindowQuantity(
                channel="tou_mid", quantity=rating_seam.Quantity(Decimal(mid), unit)
            ),
            rating_seam.WindowQuantity(
                channel="tou_off", quantity=rating_seam.Quantity(Decimal(off), unit)
            ),
        ),
    )


def price(tariff, consumption, period=FULL_MONTH):
    return rating_seam.price_period(
        tariff=tariff, consumption=consumption, period=period, account=ACCOUNT
    )


def refuse(tariff, consumption, period=FULL_MONTH):
    """The same call made to the ENGINE, for the same reason
    `tests/test_us_rat_012_engine.refuse` exists (DEF-047): billing's seam
    TRANSLATES a rating refusal into `PricingRefused` so one bad account cannot
    kill a run, and a test of a rating RULE must ask rating."""
    from apps.rating import engine

    return engine.price_period(
        tariff=tariff, consumption=consumption, period=period, account=ACCOUNT
    )


def test_us_rat_012_tc5_tou_reproduces_gt17_electric_usage():
    """TC-5 — three windows, three lines, and the frozen 88.60."""
    bill = price(tou_tariff(), split())
    lines = bill.lines_of("usage")
    assert [line.amount for line in lines] == [
        Decimal("26.40"),
        Decimal("28.00"),
        Decimal("34.20"),
    ]
    assert sum(line.amount for line in lines) == Decimal("88.60")
    # Every line names its window and carries its own quantity and unit.
    assert [line.description for line in lines] == [
        "electric usage — On-peak",
        "electric usage — Mid-peak",
        "electric usage — Off-peak",
    ]
    assert {line.unit for line in lines} == {"kWh"}
    assert all(line.taxable for line in lines)  # B4.2: usage is in the tax base


def test_us_rat_012_tc5_tou_windows_are_priced_per_season():
    """BR-RAT-021 — a winter bill must never reach a summer price."""
    windows = SUMMER_WINDOWS + (
        rating_seam.TouWindow(
            label="All day", unit_price=Decimal("0.13"), channel="tou_off", season="Winter"
        ),
    )
    bill = price(
        tou_tariff(windows=windows, season="Winter"),
        rating_seam.Quantity(
            amount=Decimal("700"),
            unit="kWh",
            windows=(
                rating_seam.WindowQuantity(
                    channel="tou_off", quantity=rating_seam.Quantity(Decimal("700"), "kWh")
                ),
            ),
        ),
    )
    (line,) = bill.lines_of("usage")
    # 700 x 0.13 = 91.00 — the winter all-day price (US-RAT-006 TC-1), NOT any
    # of the three summer prices.
    assert line.amount == Decimal("91.00")
    assert line.unit_price == Decimal("0.13")


def test_us_rat_012_tou_never_rounds_inside_the_plugin():
    """BR-RAT-003 — a plugin returns NUMERIC(18,6); finalization rounds once."""
    from apps.rating.pricing import contracts
    from apps.rating.pricing.models import tou

    (line,) = tou.price(
        contracts.SubscriptionContext(service="electric", currency=USD),
        contracts.MeasuredUsage(
            billed_quantity=Decimal("3"),
            unit="kWh",
            raw_quantity=Decimal("3"),
            multiplier=Decimal("1"),
            windows=(contracts.WindowUsage(channel="tou_on", quantity=Decimal("3"), unit="kWh"),),
        ),
        contracts.ModelConfig(
            model="time_of_use",
            billed_unit="kWh",
            windows=(
                contracts.TouWindowSpec(
                    label="On-peak", unit_price=Decimal("0.225"), channel="tou_on"
                ),
            ),
        ),
    )
    # 3 x 0.225 = 0.675 — NOT 0.68. The plugin hands the fraction on.
    assert line.amount == Decimal("0.675")


# ── The refusals. Every one is "never price a zero" (hard-won law 3). ────────


def test_us_rat_012_tou_refuses_when_no_window_was_measured():
    """BR-RAT-021 — an unread register is UNKNOWN, never a zero-usage month."""
    with pytest.raises(errors.RatingError) as excinfo:
        refuse(tou_tariff(), rating_seam.Quantity(amount=Decimal("700"), unit="kWh"))
    assert "pre-split" in str(excinfo.value)


def test_us_rat_012_tou_refuses_a_single_missing_window():
    """The dangerous case: two of three registers read, and the third silent."""
    partial = rating_seam.Quantity(
        amount=Decimal("320"),
        unit="kWh",
        windows=(
            rating_seam.WindowQuantity(
                channel="tou_on", quantity=rating_seam.Quantity(Decimal("120"), "kWh")
            ),
            rating_seam.WindowQuantity(
                channel="tou_mid", quantity=rating_seam.Quantity(Decimal("200"), "kWh")
            ),
        ),
    )
    with pytest.raises(errors.MissingWindowQuantity) as excinfo:
        refuse(tou_tariff(), partial)
    message = str(excinfo.value)
    assert "Off-peak" in message and "tou_off" in message


def test_us_rat_012_tou_refuses_a_measured_register_the_tariff_does_not_price():
    """Dropping it would lose real kWh; billing it at another window's rate
    would overcharge. Neither is visible on the finished bill."""
    surplus = split()
    surplus = rating_seam.Quantity(
        amount=surplus.amount,
        unit="kWh",
        windows=surplus.windows,
    )
    two_window_tariff = tou_tariff(windows=SUMMER_WINDOWS[:2])
    with pytest.raises(errors.TariffConfigError) as excinfo:
        refuse(two_window_tariff, surplus)
    assert "tou_off" in str(excinfo.value)


def test_us_rat_012_tou_refuses_a_window_measured_in_the_wrong_unit():
    """BR-RAT-038 — the UoM gate applies PER WINDOW, not once per service."""
    mixed = rating_seam.Quantity(
        amount=Decimal("700"),
        unit="kWh",
        windows=(
            rating_seam.WindowQuantity(
                channel="tou_on", quantity=rating_seam.Quantity(Decimal("120"), "kWh")
            ),
            rating_seam.WindowQuantity(
                channel="tou_mid", quantity=rating_seam.Quantity(Decimal("200"), "therm")
            ),
            rating_seam.WindowQuantity(
                channel="tou_off", quantity=rating_seam.Quantity(Decimal("380"), "kWh")
            ),
        ),
    )
    with pytest.raises(errors.UomMismatch):
        refuse(tou_tariff(), mixed)


def test_us_rat_012_tc5_price_order_does_not_decide_the_bill():
    """**THE PROOF THAT THE INFERENCE IS GONE (BR-RAT-067, OQ-236 CLOSED).**

    Until 2026-08-16 a window's register was derived from its PRICE RANK —
    dearest = `tou_on`, cheapest = `tou_off` — so the prices, not the utility,
    decided which meter reading was billed at which rate.

    This tariff states the registers in the OPPOSITE order to the price rank:
    the cheapest window (0.09) is the one measured on `tou_on`. A perfectly
    legal configuration, and under price rank an impossible one to express.

        stated (this test)   tou_on 120 x 0.09 + tou_mid 200 x 0.14
                             + tou_off 380 x 0.22
                           = 10.80 + 28.00 + 83.60 = 122.40
        price rank (gone)    dearest 0.22 -> tou_on's 120 kWh
                           = 26.40 + 28.00 + 34.20 =  88.60

    So the two answers differ by 33.80 on one bill, and the old resolver could
    only ever produce the second.

    ⚠ **THIS TEST CANNOT ITSELF GO RED AGAINST THE OLD RESOLVER, and saying so
    is the point (hard-won law 1).** It hands the plugin a `TouWindow` whose
    channel is already decided, so it proves the plugin honours a statement and
    nothing about where the statement came from. The resolver lived one module
    up, in `selectors.pricing_inputs`, and the red-proof that it is gone is
    `tests/test_us_rat_006_tc9_window_register.py`, which goes through the
    stored row: with `_window_channels` restored those assertions fail with
    `assert 'tou_off' == 'tou_on'` and `assert Decimal('34.20') ==
    Decimal('10.80')`.
    """
    reversed_statement = (
        # Same three windows, same three registers, same three prices — only the
        # PAIRING is the other way round, and it is the utility's to state.
        rating_seam.TouWindow(
            label="On-peak", unit_price=Decimal("0.09"), channel="tou_on", season="Summer"
        ),
        rating_seam.TouWindow(
            label="Mid-peak", unit_price=Decimal("0.14"), channel="tou_mid", season="Summer"
        ),
        rating_seam.TouWindow(
            label="Off-peak", unit_price=Decimal("0.22"), channel="tou_off", season="Summer"
        ),
    )
    bill = price(tou_tariff(windows=reversed_statement), split())
    by_window = {line.description: line.amount for line in bill.lines_of("usage")}
    assert by_window["electric usage — On-peak"] == Decimal("10.80")  # 120 x 0.09
    assert by_window["electric usage — Mid-peak"] == Decimal("28.00")  # 200 x 0.14
    assert by_window["electric usage — Off-peak"] == Decimal("83.60")  # 380 x 0.22
    assert sum(by_window.values()) == Decimal("122.40")


def test_us_rat_012_tc5_the_order_windows_arrive_in_cannot_move_a_cent():
    """A tariff's window ORDER is presentation. Every one of the six orderings
    of the demo tenant's summer schedule must produce the same 88.60 against the
    same registers — including the two that sort the prices ascending, which is
    what a bulk price change can silently produce (BR-RAT-067)."""
    import itertools

    totals = set()
    for ordering in itertools.permutations(SUMMER_WINDOWS):
        bill = price(tou_tariff(windows=ordering), split())
        totals.add(
            (
                sum(line.amount for line in bill.lines_of("usage")),
                frozenset((line.description, line.amount) for line in bill.lines_of("usage")),
            )
        )
    assert len(totals) == 1, "the window order changed the bill"
    assert next(iter(totals))[0] == Decimal("88.60")  # ❄️ B5 GT-17, unmoved


def test_us_rat_012_tou_refuses_a_window_whose_register_was_never_stated():
    """BR-RAT-067 clause 1 — a window configured before the utility could say
    which register it reads is REFUSED BY NAME. It is not resolved by price, and
    it is not priced at $0.00: a window priced at zero is a charge the bill
    forgives every month until somebody notices."""
    unstated = (
        rating_seam.TouWindow(label="Peak", unit_price=Decimal("0.22"), channel=None),
        rating_seam.TouWindow(label="Quiet", unit_price=Decimal("0.09"), channel=None),
    )
    with pytest.raises(errors.TariffConfigError) as excinfo:
        refuse(tou_tariff(windows=unstated, season=None), split())
    message = str(excinfo.value)
    # BY NAME: the clerk is told which window and where to fix it.
    assert "'Peak'" in message
    assert "which meter register" in message
    assert "S11" in message
    # And never a price: no line, no zero, no bill.
    assert "0.00" not in message.replace("122.40", "").replace("88.60", "")


def test_us_rat_012_tou_refuses_two_windows_that_name_one_register():
    """BR-RAT-067 clause 2 — one register holds ONE number for the period, so
    two windows on it would bill it once and drop the other window's money with
    nothing on the bill to show for it."""
    doubled = (
        rating_seam.TouWindow(
            label="On-peak", unit_price=Decimal("0.22"), channel="tou_on", season="Summer"
        ),
        rating_seam.TouWindow(
            label="Shoulder", unit_price=Decimal("0.18"), channel="tou_on", season="Summer"
        ),
    )
    with pytest.raises(errors.TariffConfigError) as excinfo:
        refuse(tou_tariff(windows=doubled), split())
    message = str(excinfo.value)
    assert "'On-peak'" in message and "'Shoulder'" in message
    assert "tou_on" in message


def test_us_rat_012_tou_refuses_day_types_priced_differently():
    """OQ-233 — one register per window for the whole month means there is no
    weekend-only quantity to apply a weekend-only price to."""
    disagreeing = (
        rating_seam.TouWindow(
            label="On-peak",
            unit_price=Decimal("0.22"),
            channel="tou_on",
            season="Summer",
            day_type="weekday",
        ),
        rating_seam.TouWindow(
            label="On-peak",
            unit_price=Decimal("0.11"),
            channel="tou_on",
            season="Summer",
            day_type="weekend",
        ),
    )
    with pytest.raises(errors.TariffConfigError) as excinfo:
        refuse(
            tou_tariff(windows=disagreeing),
            rating_seam.Quantity(
                amount=Decimal("120"),
                unit="kWh",
                windows=(
                    rating_seam.WindowQuantity(
                        channel="tou_on", quantity=rating_seam.Quantity(Decimal("120"), "kWh")
                    ),
                ),
            ),
        )
    assert "OQ-233" in str(excinfo.value)


def test_us_rat_012_tou_refuses_a_season_the_tariff_does_not_price():
    """BR-RAT-033 — the seasons must cover the year. A gap is a refusal, not a
    free month (OQ-234's neighbour: this is the UNCOVERED case, not the
    period-spans-two-seasons one)."""
    with pytest.raises(errors.TariffConfigError) as excinfo:
        refuse(tou_tariff(season="Shoulder"), split())
    assert "Shoulder" in str(excinfo.value)


def test_us_rat_012_tou_refuses_a_tariff_with_no_windows_at_all():
    with pytest.raises(errors.TariffConfigError):
        refuse(tou_tariff(windows=()), split())


def test_us_rat_012_tou_is_pure():
    """US-RAT-012 TC-8, extended to this plugin: same in, same out, no writes."""
    first = price(tou_tariff(), split())
    second = price(tou_tariff(), split())
    assert [line.amount for line in first.lines] == [line.amount for line in second.lines]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RAT-012@70a0044 (the four frozen sources: 04-docs/02-decisions/05-golden-tests.md · 04-docs/02-decisions/04-money-math-rules.md · 04-docs/05-modules/06-rating/06-epics/EP-RAT-05-engine.md · 04-docs/05-modules/06-rating/02-business-rules.md)
# generated: 2026-08-16 by the pricing-engines lane (EP-RAT-05 US-RAT-012 TC-5)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests/test_us_rat_012_tou.py✔ · 10-scripts/03-golden-verify.py 33 PASS/0 FAIL✔
# exceptions: every figure here is either recomputed by the frozen harness (88.60 and its three addends) or derived from a CONFIRMED rule and labelled as derived (the 91.00 winter line, the 0.675 no-rounding probe). No new figure is presented as frozen.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
