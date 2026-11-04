# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-BIL-8733 — a catch-up or penalty bill printed and stored a counted
#           service (trash, fire) as TWO lines a month, usage + base, where every
#           other kind prints ONE line per service.
# Ruling:   PO 2026-09-30, decision log "ONE-TIME BILL: SIX ANSWERS" (5), verbatim:
#           *"per service"* (DEF-BIL-8151's join, which only `runs.price_account`
#           applied — the back-bill pass prices through `rating_seam.price_bill`).
# Journey:  J75 cases 6 and 7 (08-qa/01-e2e/journeys/J75-six-service-one-time-bill.md)
# Impacts:  apps/billing/backbill.py 🔒 · apps/billing/counted_service_line.py 🔒
# ───────────────────────────────────────────────────────
"""A catch-up prints each month's trash as ONE line — and never joins two months.

Worked (J75 case 6 in miniature): one 96-gallon cart, $15.00 a cart, base $3.00 a
cart, August and September both whole months. Each month's trash is ONE line of
**$18.00** (1 cart at $18.00); the bill is **$36.00**. Before the fix each month
carried two lines, `$15.00` and `$3.00`.

RED before the fix (SQLite, 2026-10-01):

    AssertionError: DEF-BIL-8733: one trash line per month — got 4 lines
"""

from datetime import date
from decimal import Decimal

from apps.billing import backbill, rating_seam
from apps.billing.contracts import AccountBillingData, ServiceReading

AUG = (date(2026, 8, 1), date(2026, 8, 31))
SEP = (date(2026, 9, 1), date(2026, 9, 30))
TRASH = rating_seam.TariffConfig(
    service="trash",
    model="flat",
    billed_unit="cart",
    unit_price=Decimal("15.0000"),
    base_charge=Decimal("3.0000"),
    size_class="CART-96",
    size_label="Trash 96-gallon cart",
    per_size_line=True,
)


def _data(window):
    start, end = window
    days = (end - start).days + 1
    return AccountBillingData(
        account_id="acc-8733",
        account_no="A-8733",
        behavior_class="billable",
        currency="USD",
        tax_exempt=False,
        period_start=start,
        period_end=end,
        cycle_days=days,
        service_days=days,
        rate_plan_id="plan-8733",
        rate_plan_name="Six Rivers",
        tariffs=(TRASH,),
        readings=(
            ServiceReading(
                service_code="trash",
                consumption=None,
                absent_reason="service_not_metered",
                asset_count=1,
                asset_size_counts={"CART-96": 1},
            ),
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
            data=_data(window),
        )
        for window in (AUG, SEP)
    )
    return backbill.PreparedBackBill(
        account_id="acc-8733",
        account_no="A-8733",
        period_start=AUG[0],
        period_end=SEP[1],
        reason_code="MISSED",
        theft=False,
        cap_months=12,
        approval_mode="none",
        groups=groups,
    )


def test_8733__each_months_trash_is_one_line_and_months_are_never_joined():
    pass_ = backbill.price_back_bill(_prepared())
    trash = [
        (line, window)
        for line, window in zip(pass_.priced.lines, pass_.line_windows)
        if line.service == "trash"
    ]
    assert len(trash) == 2, (
        f"DEF-BIL-8733: one trash line per month — got {len(trash)} lines: "
        f"{[(line.kind, line.description, line.amount) for line, _w in trash]}"
    )
    assert [window for _line, window in trash] == [AUG, SEP]
    for line, _window in trash:
        assert (line.kind, line.quantity, line.unit) == ("usage", Decimal("1"), "cart")
        assert line.amount == Decimal("18.00")
    assert pass_.priced.total == Decimal("36.00")
    assert len(pass_.line_windows) == len(pass_.priced.lines)
