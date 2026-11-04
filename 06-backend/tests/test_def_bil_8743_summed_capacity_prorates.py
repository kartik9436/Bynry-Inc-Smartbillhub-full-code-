# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-BIL-8743 — a solar or battery charge priced per kW on the SUMMED
#           capacity (CR-062 D1) was charged WHOLE on a part period.
# Rules:    B4.3 / BR-RAT-004 (proration by calendar days) · B5 WE-16 / GT-31
#           (*"Solar 4 units activated Jul 22 → 10/31 days × $40.00 = $12.90"*) ·
#           GT-15 as amended by the PO 2026-08-11 (*"BOTH lines prorate"*: solar
#           AND battery) · DEF-BIL-8566 (the counted service's twin, *"Cart
#           shrinks too"*)
# Journey:  J75 cases 3, 4, 5 (08-qa/01-e2e/journeys/J75-six-service-one-time-bill.md)
# Impacts:  apps/billing/stages/measure_consumption.py 🔒 ·
#           apps/rating/pricing/stages/price_usage.py 🔒 · normalize.py 🔒
# ───────────────────────────────────────────────────────
"""A summed capacity charge prorates on a part period, like its base.

Worked: 2 × SOL-P2 + 1 × SOL-P4 = 8 kW at $14.00 a kW, base SOL-P2 $2.00 /
SOL-P4 $3.00. The account opened 16 September: 15 of September's 30 days.

  * capacity  8 kW × $14.00 × 15/30 = **$56.00**   (was $112.00, whole)
  * base      $7.00 × 15/30         = **$3.50**    (already prorated)

The kW quantity is NOT scaled — the customer still has 8 kW installed; only
the money is, exactly as one cart stays one cart on DEF-BIL-8566's line.

RED before the fix (SQLite, 2026-10-01):

    AssertionError: DEF-BIL-8743: 8 kW for 15 of 30 days is $56.00 — got 112.000000
"""

from datetime import date
from decimal import Decimal

import pytest

from tests.test_capacity_base_by_size import (  # noqa: F401 — the fixture world and its autouse cycle seam
    PER_KW,
    SEP_END,
    SEP_START,
    _calculate,
    _lines,
    _prepare,
    _price_by_size,
    _the_unit_bills_on_a_cycle,
)
from tests.test_cr062_d1_installed_capacity_sums import _world
from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db


def _solar(dana, brazos, tag, opened):
    from apps.customers import models as customer_models

    cycle, _unit, account = _world(
        dana,
        brazos,
        cycle_code=tag,
        code="solar",
        kind="pv",
        uom="kW",
        rate=PER_KW,
        specs=("SOL-P2", "SOL-P2", "SOL-P4"),
    )
    _price_by_size(
        brazos, "solar", "BASE-SOL", {"SOL-P2": Decimal("2.00"), "SOL-P4": Decimal("3.00")}
    )
    customer_models.Account.objects.filter(pk=account.pk).update(opened_at=opened)
    prepared = _prepare(cycle, start=SEP_START, end=SEP_END)
    assert prepared.ready, [str(b) for b in prepared.blocked]
    return cycle, prepared.ready[0]


def test_8743__a_part_period_prorates_the_summed_kw_charge(brazos, dana):
    with tenant_ctx(brazos):
        cycle, data = _solar(dana, brazos, "CAP-8743", date(2026, 9, 16))
        assert (data.service_days, data.cycle_days) == (15, 30)
        invoice = _calculate(brazos, cycle, data, "cap-8743", start=SEP_START, end=SEP_END)
        lines = _lines(invoice, "solar")

    usage = [line for line in lines if line.kind == "usage"]
    base = [line for line in lines if line.kind == "base"]
    assert len(usage) == 1
    assert usage[0].amount == Decimal("56.00"), (
        f"DEF-BIL-8743: 8 kW for 15 of 30 days is $56.00 — got {usage[0].amount}"
    )
    assert (usage[0].quantity, usage[0].unit) == (Decimal("8.000000"), "kW"), (
        "the kW installed is never scaled"
    )
    assert [b.amount for b in base] == [Decimal("3.500000")]
    assert invoice.total == Decimal("59.50")


def test_8743__a_whole_month_is_unchanged(brazos, dana):
    """A factor of 1: 8 kW × $14.00 = $112.00 + $7.00 base, as `test_capacity_base_by_size::test_c`."""
    with tenant_ctx(brazos):
        cycle, data = _solar(dana, brazos, "CAP-8743W", date(2026, 8, 1))
        invoice = _calculate(brazos, cycle, data, "cap-8743w", start=SEP_START, end=SEP_END)
    assert invoice.total == Decimal("119.00")
