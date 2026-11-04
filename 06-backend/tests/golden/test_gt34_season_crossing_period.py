# ── Trace ──────────────────────────────────────────────
# Epics:    EP-RAT-05 (rating engine core — usage pricing)
#           Screens: — (priced lines render in S31.2 and on the bill)
# Rules:    BR-RAT-034 (CONFIRMED, PO R5-7 — season boundaries split the bill
#           period pro-rata by calendar days) · BR-RAT-021 (TOU, per-season
#           prices, reads pre-split per window) · BR-RAT-003 (round per line at
#           finalization only) · B4.2 (tax base = usage + base)
# Golden:   GT-34 (= WE-18 by B5's allocation, "WE-n → GT-(16+n)") — B5 ❄️
#           FROZEN 2026-08-08; figures copied from
#           04-docs/05-modules/07-billing/08-worked-examples.md §WE-18.
# Tests:    this file
# Impacts:  apps/rating/pricing/models/tou.py 🔒 · apps/rating/pricing/season_split.py 🔒
# ───────────────────────────────────────────────────────
"""GT-34 / WE-18 — a bill period that CROSSES a season boundary is split pro-rata.

WE-18 VERBATIM (04-docs/05-modules/07-billing/08-worked-examples.md)
--------------------------------------------------------------------
  "WE-18 · Seasonal boundary mid-cycle (Sep 15 – Oct 14, season flips Oct 1)
   No boundary read → pro-rata day split 16/30 summer + 14/30 winter per window
   (electric only shown): on 120 kWh → 64×0.22=14.08 + 56×0.18=10.08; mid 200 →
   106.666667×0.14=14.93 + 93.333333×0.12=11.20; off 380 → 202.666667×0.09=18.24
   + 177.333333×0.08=14.19. Usage $82.72 + base 12 → taxable $94.72 → tax $8.95
   → total **$103.67**."

The tax is the workbook's four authorities (same file, line 11): TX State
6.25% · Travis County 1.00% · City franchise 2.00% · PUC 0.20%, each rounded on
its own line: 5.92 + 0.95 + 1.89 + 0.19 = 8.95.

WHY THIS FILE EXISTS (2026-10-01)
---------------------------------
`OQ-234` was CLOSED by the PO on 2026-09-07 — *"please split  swithch it on"* —
and the split was not built for three weeks. Through that whole time the engine
priced this exact period at ONE season (winter, the season on the 14 Oct
service date): on-peak `120 × 0.18 = $21.60` where WE-18 says `$24.16`, and
nothing compared the two because GT-34 had NO test that ran the engine — it was
absent from the frozen harness too. This file makes it engine-verified, and
`10-scripts/gates/g64_engine_verified_gts.txt` moved in the same commit.

THE DAY COUNTS ARE AN INPUT, NOT A COMPUTATION — EXACTLY AS IN PRODUCTION.
The engine holds no calendar (`OQ-234`'s design note). In the product,
`rating.selectors._season_days_between` counts them from the stored season
ranges; here they are WE-18's own "16/30 summer + 14/30 winter".
"""

from decimal import Decimal

import pytest

from apps.billing import rating_seam

from .conftest import TAXED_ACCOUNT

pytestmark = pytest.mark.golden

KWH = "kWh"

# ── INPUTS (WE-18 + the workbook's tariff, 08-worked-examples.md) ───────────
# Summer is the Residential Standard reference prices (WE-1/GT-17); winter is
# the 0.18 / 0.12 / 0.08 WE-18 multiplies by.
WINDOWS = (
    rating_seam.TouWindow("On-peak", Decimal("0.22"), channel="tou_on", season="Summer"),
    rating_seam.TouWindow("Mid-peak", Decimal("0.14"), channel="tou_mid", season="Summer"),
    rating_seam.TouWindow("Off-peak", Decimal("0.09"), channel="tou_off", season="Summer"),
    rating_seam.TouWindow("On-peak", Decimal("0.18"), channel="tou_on", season="Winter"),
    rating_seam.TouWindow("Mid-peak", Decimal("0.12"), channel="tou_mid", season="Winter"),
    rating_seam.TouWindow("Off-peak", Decimal("0.08"), channel="tou_off", season="Winter"),
)
#: "16/30 summer + 14/30 winter" — 15 Sep … 30 Sep, then 1 Oct … 14 Oct.
SEASON_DAYS = (rating_seam.SeasonDays("Summer", 16), rating_seam.SeasonDays("Winter", 14))
#: "on 120 kWh … mid 200 … off 380" — pre-split registers (BR-RAT-021).
CONSUMPTION = rating_seam.Quantity(
    amount=Decimal("700"),
    unit=KWH,
    windows=(
        rating_seam.WindowQuantity("tou_on", rating_seam.Quantity(Decimal("120"), KWH)),
        rating_seam.WindowQuantity("tou_mid", rating_seam.Quantity(Decimal("200"), KWH)),
        rating_seam.WindowQuantity("tou_off", rating_seam.Quantity(Decimal("380"), KWH)),
    ),
)
#: "+ base 12"
BASE = Decimal("12.00")
#: line 11 — "TX State 6.25% · Travis County 1.00% · City franchise 2.00% · PUC 0.20%"
TAXES = (
    rating_seam.TaxRule(code="TX State", rate=Decimal("0.0625")),
    rating_seam.TaxRule(code="Travis County", rate=Decimal("0.0100")),
    rating_seam.TaxRule(code="City franchise", rate=Decimal("0.0200")),
    rating_seam.TaxRule(code="PUC", rate=Decimal("0.0020")),
)
PERIOD = rating_seam.BillingPeriod(cycle_days=30, service_days=30)

# ── EXPECTED (WE-18, copied) ────────────────────────────────────────────────
EXPECTED_USAGE_LINES = [
    Decimal("14.08"),  # on  64 × 0.22          (summer)
    Decimal("14.93"),  # mid 106.666667 × 0.14  (summer)
    Decimal("18.24"),  # off 202.666667 × 0.09  (summer)
    Decimal("10.08"),  # on  56 × 0.18          (winter)
    Decimal("11.20"),  # mid 93.333333 × 0.12   (winter)
    Decimal("14.19"),  # off 177.333333 × 0.08  (winter)
]
EXPECTED_USAGE = Decimal("82.72")
EXPECTED_TAXABLE = Decimal("94.72")
EXPECTED_TAX = Decimal("8.95")
EXPECTED_TOTAL = Decimal("103.67")
#: The figure the engine produced on this window until 2026-10-01 — WINTER for
#: the whole period. Kept so the test states what it moved FROM.
ONE_SEASON_ON_PEAK = Decimal("21.60")


def _price(season_days):
    return rating_seam.price_period(
        tariff=rating_seam.TariffConfig(
            service="electric",
            model="time_of_use",
            billed_unit=KWH,
            base_charge=BASE,
            windows=WINDOWS,
            # the season on the 14 Oct service date — what the caller resolved
            # before the split, and still resolves.
            season="Winter",
            season_days=season_days,
        ),
        consumption=CONSUMPTION,
        period=PERIOD,
        account=TAXED_ACCOUNT,
        taxes=TAXES,
    )


def test_gt34_a_season_crossing_period_splits_pro_rata_by_calendar_days():
    bill = _price(SEASON_DAYS)
    usage = bill.lines_of("usage")
    assert [line.amount for line in usage] == EXPECTED_USAGE_LINES
    assert sum(line.amount for line in usage) == EXPECTED_USAGE
    # The quantities foot to the registers: 64+56, 106.666667+93.333333, ...
    assert [line.quantity for line in usage] == [
        Decimal("64.000000"),
        Decimal("106.666667"),
        Decimal("202.666667"),
        Decimal("56.000000"),
        Decimal("93.333333"),
        Decimal("177.333333"),
    ]
    assert bill.sole_line("base").amount == BASE
    assert bill.taxable_subtotal == EXPECTED_TAXABLE
    assert bill.tax_total == EXPECTED_TAX
    assert bill.total == EXPECTED_TOTAL
    # Each split line names its season and its days, so the customer can see
    # why one window has two lines.
    assert "Summer, 16 of 30 days" in usage[0].description
    assert "Winter, 14 of 30 days" in usage[3].description


def test_gt34_the_one_season_answer_it_replaces():
    """No shares = the old behaviour, and it is the $21.60 OQ-234 recorded."""
    bill = _price(())
    on_peak = bill.lines_of("usage")[0]
    assert on_peak.amount == ONE_SEASON_ON_PEAK
    assert on_peak.amount != EXPECTED_USAGE_LINES[0] + EXPECTED_USAGE_LINES[3]


# ── Lifecycle ─────────────────────────────────────────────
# packet: GT-34 (= WE-18, 04-docs/05-modules/07-billing/08-worked-examples.md) · OQ-234 CLOSED 2026-09-07 · DEF-RAT-8832
# generated: 2026-10-01 by the season-split lane — RED on the tip b1b382638: `AttributeError: module 'apps.billing.rating_seam' has no attribute 'SeasonDays'`; the same WE-18 window end to end on that tip billed usage lines 21.60 / 24.00 / 30.40 (winter throughout) — tests/test_oq234_season_split.py
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — pure-math fixture) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: pytest tests/golden ✔ · G64 ✔
# exceptions: none — every asserted figure is WE-18's own.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
