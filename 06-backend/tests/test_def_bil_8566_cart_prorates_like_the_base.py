# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-BIL-8566 — a part month charged the per-cart trash charge WHOLE
#          while the base beside it was prorated ($15.00 in each half of a July
#          cut at a price change; $15.00 on an 18-day final bill).
# Ruling:  PO 2026-10-01 (decision log "SIX PO RULINGS IN ONE MESSAGE", (5)),
#          verbatim: *"A · Cart shrinks too: $9.00"* — 18/30 × $15.00.
# Rules:   BR-RAT-004 / B4.3 (calendar-day proration) · BR-RAT-090 (a counted
#          service's quantity is a COUNT) · BR-RAT-002 (metered tiers scale the
#          BOUND, never the quantity — untouched here)
# Rows:    BULK-CHG-59
# Code:    apps/rating/pricing/stages/price_usage.py (`per_size_line` usage
#          lines take the period factor, exactly as `_base_lines` does)
# ───────────────────────────────────────────────────────
"""The trash cart on a part month prorates exactly as the base does.

THE WORKED FIGURES (written before the fix, red first — law 7)
--------------------------------------------------------------
    one cart, 18 of 30 days  18/30 × $15.00 = **$9.00**   (was $15.00)
                             base 18/30 × $3.00 = $1.80   (unchanged)
    two carts, 18 of 30      18/30 × $30.00 = $18.00
    July cut at the 16th     15/31 × $15.00 = 7.2580… → $7.26
                             16/31 × $15.00 = 7.7419… → $7.74  (was $15.00 + $15.00)
    a whole month            $15.00                    (unchanged)

A METERED tiered service is not a counted one: its quantity is what the meter
measured and only the tier BOUND scales (BR-RAT-002). That is pinned below so the
cart rule cannot leak into water.
"""

from __future__ import annotations

from decimal import Decimal

from apps.billing import rating_seam

USD = "USD"
ACCOUNT = rating_seam.AccountContext(currency=USD, tax_exempt=False)


def _period(service_days: int, cycle_days: int = 30) -> rating_seam.BillingPeriod:
    return rating_seam.BillingPeriod(cycle_days=cycle_days, service_days=service_days)


def _trash(base: str | None = "3.00") -> rating_seam.TariffConfig:
    """Trash as `gather._per_size_configs` builds it: one unbounded tier per
    size at $15.00 a cart, the size group's base, `per_size_line=True`."""
    return rating_seam.TariffConfig(
        service="trash",
        model="tiered",
        billed_unit="cart",
        base_charge=None if base is None else Decimal(base),
        tiers=(rating_seam.Tier(upper=None, unit_price=Decimal("15.00")),),
        per_size_line=True,
        size_label="96 gal cart",
    )


def _carts(count: int, period: rating_seam.BillingPeriod) -> rating_seam.RatedBill:
    return rating_seam.price_period(
        tariff=_trash(),
        consumption=rating_seam.Quantity(amount=Decimal(count), unit="cart"),
        period=period,
        account=ACCOUNT,
    )


def test_def_bil_8566__one_cart_on_18_of_30_days_is_nine_dollars():
    bill = _carts(1, _period(18))
    [usage] = bill.lines_of("usage")
    assert usage.amount == Decimal("9.00")
    # The count is still the count: one cart, never 0.6 of one.
    assert usage.quantity == Decimal("1")
    assert bill.sole_line("base").amount == Decimal("1.80")


def test_def_bil_8566__two_carts_on_18_of_30_days_is_eighteen_dollars():
    [usage] = _carts(2, _period(18)).lines_of("usage")
    assert usage.amount == Decimal("18.00")


def test_def_bil_8566__each_half_of_a_july_cut_at_a_price_change_prorates():
    """DEF-BIL-8566's own case: Unit E's July, Jul 1–15 and Jul 16–31."""
    [first] = _carts(1, _period(15, 31)).lines_of("usage")
    [second] = _carts(1, _period(16, 31)).lines_of("usage")
    assert (first.amount, second.amount) == (Decimal("7.26"), Decimal("7.74"))
    assert first.amount + second.amount == Decimal("15.00")


def test_def_bil_8566__a_whole_month_is_unchanged():
    [usage] = _carts(1, _period(30)).lines_of("usage")
    assert usage.amount == Decimal("15.00")


def test_def_bil_8566__a_metered_tiered_service_still_never_scales_its_quantity():
    """BR-RAT-002: 3 kgal on a half month, tiers 0–2 @ $3.00 / above @ $4.50 →
    the bound scales to 1: 1 × 3.00 + 2 × 4.50 = $12.00. Not $6.00."""
    water = rating_seam.TariffConfig(
        service="water",
        model="tiered",
        billed_unit="kgal",
        base_charge=None,
        tiers=(
            rating_seam.Tier(upper=Decimal("2"), unit_price=Decimal("3.00")),
            rating_seam.Tier(upper=None, unit_price=Decimal("4.50")),
        ),
    )
    bill = rating_seam.price_period(
        tariff=water,
        consumption=rating_seam.Quantity(amount=Decimal("3"), unit="kgal"),
        period=_period(15),
        account=ACCOUNT,
    )
    assert sum(line.amount for line in bill.lines_of("usage")) == Decimal("12.00")


def test_def_bil_8566__the_worked_figures_foot():
    assert Decimal(18) / Decimal(30) * Decimal("15.00") == Decimal("9.00")
    assert round(Decimal(15) / Decimal(31) * Decimal("15.00"), 2) == Decimal("7.26")
    assert round(Decimal(16) / Decimal(31) * Decimal("15.00"), 2) == Decimal("7.74")
