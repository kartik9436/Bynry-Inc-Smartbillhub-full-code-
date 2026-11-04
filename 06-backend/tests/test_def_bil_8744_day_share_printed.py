# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-BIL-8744 — a part-month per-kW line printed the FULL rate beside
#           the amount DEF-BIL-8743 cut down by days: "6 kW · $14.00 · $53.20"
#           on a 19-of-30-day first bill, so quantity × rate ≠ amount.
# Rules:    B4.3 (proration by calendar days — UNCHANGED, no amount moves) ·
#           `billing/0039` (`pricing_trace` stores service_days / cycle_days)
# Journey:  J75 cases 3, 4, 5 (08-qa/01-e2e/journeys/J75-six-service-one-time-bill.md)
# ───────────────────────────────────────────────────────
"""Every line cut down by days says by how many, and then it foots.

Worked: 8 kW of solar at $14.00 a kW, opened 16 September → 15 of 30 days.
The engine charges `8 × $14.00 × 15/30 = $56.00` (DEF-BIL-8743, unchanged).
The stored line prints `8 kW · $14.0000 · $56.00` — `8 × 14 = 112 ≠ 56` — and
now carries `day_share = {days: 15, of: 30}`, so it reads
`8 kW · $14.0000 · 15/30 days · $56.00`.

THE INVARIANT, asserted over every service line of the bill: either
`quantity × rate` rounds to the amount, or the line carries a day share and
`quantity × rate × days ÷ of` does.

RED with the share withheld (`"day_share": None`, SQLite, 2026-10-01):

    AssertionError: DEF-BIL-8744: 8 kW × $14.00 = $112.00 beside $56.00 must say 15/30 days
    AssertionError: DEF-BIL-8744: lines that do not foot: [{… 'quantity': '8.000000',
        'unit': 'kW', 'unit_price': '14.000000', 'amount': '56.000000' …}]
"""

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

import pytest

from apps.billing import day_share, documents, selectors
from tests.test_capacity_base_by_size import (  # noqa: F401 — the fixture world and its autouse cycle seam
    SEP_END,
    SEP_START,
    _calculate,
    _the_unit_bills_on_a_cycle,
)
from tests.test_def_bil_8743_summed_capacity_prorates import _solar
from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

CENT = Decimal("0.01")


def _cents(value) -> Decimal:
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)


def _foots(row: dict) -> bool:
    """quantity × rate (× days ÷ of, where the line says so) = amount."""
    quantity, rate, amount = row["quantity"], row["unit_price"], row["amount"]
    if quantity is None or rate is None:
        return True
    whole = Decimal(quantity) * Decimal(rate)
    share = row.get("day_share")
    if share:
        whole = whole * Decimal(share["days"]) / Decimal(share["of"])
    return _cents(whole) == _cents(amount)


def _bill(brazos, dana, tag, opened):
    with tenant_ctx(brazos):
        cycle, data = _solar(dana, brazos, tag, opened)
        invoice = _calculate(brazos, cycle, data, tag.lower(), start=SEP_START, end=SEP_END)
        stored = list(invoice.lines.order_by("created_at"))
        rows = selectors._line_rows(stored)
        groups, _absent = documents._groups(stored, "USD", invoice.bill_payload or {})
        doc_lines = [line for group in groups for line in group.lines]
    return invoice, rows, doc_lines


def test_8744__the_prorated_kw_line_carries_its_days_and_foots(brazos, dana):
    invoice, rows, doc_lines = _bill(brazos, dana, "CAP-8744", date(2026, 9, 16))
    # The printed document says it on the description (its Rate cell truncates).
    assert [line.description for line in doc_lines if "15/30 days" in line.description], [
        line.description for line in doc_lines
    ]
    usage = [row for row in rows if row["kind"] == "usage" and row["unit"] == "kW"]
    assert len(usage) == 1
    line = usage[0]
    # The money is 2.428.1's, untouched.
    assert _cents(line["amount"]) == Decimal("56.00")
    assert (Decimal(line["quantity"]), Decimal(line["unit_price"])) == (Decimal(8), Decimal(14))
    assert line["day_share"] == {
        "days": 15,
        "of": 30,
    }, "DEF-BIL-8744: 8 kW × $14.00 = $112.00 beside $56.00 must say 15/30 days"
    assert day_share.words(line["day_share"]) == "15/30 days"
    assert invoice.total == Decimal("59.50")


def test_8744__every_line_foots_with_its_share(brazos, dana):
    _, rows, _ = _bill(brazos, dana, "CAP-8744F", date(2026, 9, 16))
    assert rows
    bad = [row for row in rows if not _foots(row)]
    assert not bad, f"DEF-BIL-8744: lines that do not foot: {bad}"


def test_8744__a_whole_month_carries_no_share(brazos, dana):
    _, rows, _ = _bill(brazos, dana, "CAP-8744W", date(2026, 8, 1))
    assert all(row["day_share"] is None for row in rows)
    assert all(_foots(row) for row in rows)


@pytest.mark.parametrize(
    "quantity,rate,amount,days,of,expected",
    [
        # J75 Six Rivers first bill: 6 kW × $14.00 × 19/30 = $53.20.
        ("6", "14.000000", "53.200000", 19, 30, {"days": 19, "of": 30}),
        # J75 battery: 5 kW × $3.00 × 19/30 = $9.50.
        ("5", "3.000000", "9.500000", 19, 30, {"days": 19, "of": 30}),
        # A whole month foots by itself.
        ("6", "14.000000", "84.000000", 30, 30, None),
        # A part month whose line already foots (a metered line) says nothing.
        ("8.6", "5.580000", "47.990000", 19, 30, None),
        # A line that does not foot for some OTHER reason is never labelled.
        ("6", "14.000000", "50.000000", 19, 30, None),
        # No days stored (a line written before `billing/0039`).
        ("6", "14.000000", "53.200000", None, None, None),
    ],
)
def test_8744__the_share_is_stated_only_where_it_explains_the_amount(
    quantity, rate, amount, days, of, expected
):
    got = day_share.day_share(
        kind="usage",
        quantity=quantity,
        rate=rate,
        amount=amount,
        service_days=days,
        cycle_days=of,
    )
    assert got == expected


def test_8744__base_tax_and_fee_lines_never_carry_a_share():
    for kind in ("base", "tax", "fee", "deposit", "discount"):
        assert (
            day_share.day_share(
                kind=kind,
                quantity="6",
                rate="14",
                amount="53.20",
                service_days=19,
                cycle_days=30,
            )
            is None
        )
