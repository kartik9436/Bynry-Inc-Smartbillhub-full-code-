# ── Trace ──────────────────────────────────────────────
# Defects:  DEF-BIL-8560 (sewer on a multi-month catch-up / penalty was priced on
#           the COMBINED water of every month sharing a pricing call) ·
#           DEF-BIL-8561 (a catch-up / penalty lost its months and, on every
#           month but the first, its meters)
# Journey:  J74 cases 6 and 7 (08-qa/01-e2e/journeys/J74-one-time-bill-end-to-end.md)
# Rules:    BR-RAT-1015 (sewer = 40% of THAT period's water) · BR-BIL-018 ·
#           OQ-155 (tax ONCE over the whole bill) · US-BIL-013 §5
# Impacts:  apps/billing/backbill.py 🔒 · apps/billing/stages/assemble_document.py
# ───────────────────────────────────────────────────────
"""A catch-up prices each month on that month's own water, and keeps its months.

Worked (J74 case 6 in miniature): water $3.25/kgal flat, sewer 40% of water at
$5.00/kgal. August used 10 kgal, September 20 kgal, both whole months.

  * August sewer   = 40% × 10 = 4 kgal → **$20.00**
  * September sewer = 40% × 20 = 8 kgal → **$40.00**

Before the fix both months shared ONE pricing call (both weigh 1), so the engine
added the two months' water together as one basis and billed **12 kgal, $60.00,
twice** — $120.00 of sewer for $60.00 of it.

The same pass now says which month each line bills (`line_windows`) and gives
every metered line back its meter — the bill-level channel the later months ride
to the taxed call drops `asset_id` on the way.
"""

from datetime import date
from decimal import Decimal

from apps.billing import backbill, rating_seam
from apps.billing.contracts import AccountBillingData, ServiceReading

AUG = (date(2026, 8, 1), date(2026, 8, 31))
SEP = (date(2026, 9, 1), date(2026, 9, 30))
METER = "meter-w1"
WATER = rating_seam.TariffConfig(
    service="water",
    model="flat",
    billed_unit="kgal",
    unit_price=Decimal("3.2500"),
    asset_id=METER,
)
SEWER = rating_seam.TariffConfig(
    service="sewer",
    model="percent_of_service",
    billed_unit="kgal",
    percent=Decimal("40"),
    basis_service="water",
    percent_basis="usage",
    tiers=(rating_seam.Tier(upper=None, unit_price=Decimal("5.0000")),),
)


def _data(window, kgal):
    start, end = window
    days = (end - start).days + 1
    return AccountBillingData(
        account_id="acc-8560",
        account_no="A-8560",
        behavior_class="billable",
        currency="USD",
        tax_exempt=False,
        period_start=start,
        period_end=end,
        cycle_days=days,
        service_days=days,
        rate_plan_id="plan-8560",
        rate_plan_name="Elm St",
        tariffs=(WATER, SEWER),
        readings=(
            ServiceReading(
                service_code="water",
                consumption=rating_seam.Quantity(Decimal(kgal), "kgal"),
                read_id=f"read-{start.month}",
                asset_id=METER,
            ),
            ServiceReading(service_code="sewer", consumption=None, absent_reason="no_meter"),
        ),
    )


def _prepared():
    groups = tuple(
        backbill.BackBillGroup(
            period_start=window[0],
            period_end=window[1],
            service_date=window[0],
            cycle_days=(window[1] - window[0]).days + 1,
            tariff_version_ids={},
            data=_data(window, kgal),
        )
        for window, kgal in ((AUG, "10"), (SEP, "20"))
    )
    return backbill.PreparedBackBill(
        account_id="acc-8560",
        account_no="A-8560",
        period_start=AUG[0],
        period_end=SEP[1],
        reason_code="MISSED",
        theft=False,
        cap_months=12,
        approval_mode="none",
        groups=groups,
    )


def _sewer_usage(pass_):
    return [line for line in pass_.priced.lines if line.service == "sewer" and line.kind == "usage"]


def test_8560__each_months_sewer_is_forty_percent_of_that_months_water():
    pass_ = backbill.price_back_bill(_prepared())
    sewer = _sewer_usage(pass_)
    assert [line.quantity for line in sewer] == [Decimal("4"), Decimal("8")], (
        "DEF-BIL-8560: each month's sewer is 40% of THAT month's water, never of the months combined"
    )
    assert [line.amount for line in sewer] == [Decimal("20.00"), Decimal("40.00")]
    # And the bill foots: water 10 + 20 kgal at $3.25 = $97.50, sewer $60.00.
    assert pass_.priced.total == Decimal("157.50")


def test_8561__every_line_says_which_month_it_bills():
    pass_ = backbill.price_back_bill(_prepared())
    lines = pass_.priced.lines
    windows = pass_.line_windows
    assert len(windows) == len(lines)
    by_month = {
        (line.service, line.kind, window): line.amount
        for line, window in zip(lines, windows)
        if line.kind == "usage"
    }
    assert by_month[("water", "usage", AUG)] == Decimal("32.50")
    assert by_month[("water", "usage", SEP)] == Decimal("65.00")
    assert by_month[("sewer", "usage", AUG)] == Decimal("20.00")
    assert by_month[("sewer", "usage", SEP)] == Decimal("40.00")


def test_8561__every_metered_line_keeps_its_meter_in_every_month():
    pass_ = backbill.price_back_bill(_prepared())
    water = [line for line in pass_.priced.lines if line.service == "water" and line.kind == "usage"]
    assert len(water) == 2
    assert [line.asset_id for line in water] == [METER, METER], (
        "DEF-BIL-8561: September's water line lost its meter on the bill-level channel"
    )
