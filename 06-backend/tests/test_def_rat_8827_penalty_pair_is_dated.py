"""DEF-RAT-8827 — editing a penalty's EVERY-CLASS percent and minimum is DATED, never an overwrite.

Found by the charge-code walk of 2026-10-01 (`10-scripts/charge_codes_walk33.mjs`):
the clerk opened *Edit* on `LATE` (1.50%, minimum $5.00, every class), typed
1.75% and $6.00 with *Effective from 11/01/2026*, and saved. The code's two
columns were overwritten on the spot, so every overdue account was charged the
new fee THAT DAY, and no price row or version recorded the change — against
the PO's 2026-10-01 rulings that a charge code's price carries *Effective from*
and is logically killed, never overwritten.

WHAT EACH CASE PROVES (each on the production entry points — `update_charge`,
`assess_late_fee_for_plan`, `charge_row`):
  * tc1 — before 11/01 the fee is still the old terms: $542.10 overdue →
    max(1.50% × 542.10 = $8.13, $5.00) = **$8.13**; from 11/01 the new ones:
    max(1.75% × 542.10 = $9.49, $6.00) = **$9.49**.
  * tc2 — the columns are untouched and ONE dated every-class terms row exists
    from 11/01, open; nothing deleted.
  * tc3 — re-saving exactly what the screen showed writes nothing.

RED FIRST (law 7): on the tip before the fix, tc1 failed with
`assert Decimal('9.49') == Decimal('8.13')` (the 10/15 fee already charged the
new 1.75%) and tc2 found the columns at 0.0175 / 6.00 and no row.

WHAT WOULD MAKE THESE PASS WRONGLY: a fix that dated the row but read the
columns would pass tc1's 10/15 half — the 11/15 half fails it. A fix that
wrote the row and ALSO overwrote the columns would pass tc1 on 11/15 and fail
on 10/15. The GT-8 figure ($8.13) is the ❄️ frozen one and stays the answer
before the change.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from apps.billing import late_fee
from apps.rating import charge_prices, models as rating_models
from apps.rating import selectors as rating_selectors
from apps.rating import services as rating_services
from apps.rating.constants import ALL_SIZES

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import brazos, dana, make_plan, tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db

CHANGE_FROM = dt.date(2026, 11, 1)
REASON = "Board approved late-fee review, November"


def _late_copy(tenant, actor, code):
    with tenant_ctx(tenant):
        seeded = rating_models.Charge.objects.get(tenant=tenant, code="LATE", deleted_at__isnull=True)
        return rating_services.create_charge(
            actor,
            {
                "code": code,
                "name": "Late payment",
                "charge_type": "penalty",
                "kind": "plan",
                "amount_rule": "percent_with_minimum",
                "percent": "0.015",
                "min_amount": "5.00",
                "gl_account_id": str(seeded.gl_account_id) if seeded.gl_account_id else None,
            },
        )


def _plan_on(tenant, charge_id, name):
    plan = make_plan(tenant, name=name, code=name.lower().replace(" ", "-"))
    with tenant_ctx(tenant):
        rating_models.RatePlan.objects.filter(pk=plan.pk).update(late_fee_charge_id=charge_id)
    return plan


def _fee(plan, due, as_of):
    fee, _terms = late_fee.assess_late_fee_for_plan(
        rate_plan_id=plan.id,
        overdue_amount=Decimal("542.10"),
        due_date=due,
        as_of=as_of,
        grace_days=5,
        grace_mode="calendar",
        customer_class="residential",
    )
    return fee


def _edit(actor, charge_id, percent, minimum):
    return rating_services.update_charge(
        actor,
        charge_id,
        {
            "percent": percent,
            "min_amount": minimum,
            "effective_from": CHANGE_FROM.isoformat(),
            "reason": REASON,
        },
    )


def test_def_rat_8827_tc1__the_old_fee_until_the_date_and_the_new_one_from_it(brazos, dana):
    row = _late_copy(brazos, dana, "LATE-W1")
    plan = _plan_on(brazos, row["id"], "Late dated plan one")
    with tenant_ctx(brazos):
        _edit(dana, row["id"], "0.0175", "6.00")
        before = _fee(plan, dt.date(2026, 10, 1), dt.date(2026, 10, 15))
        after = _fee(plan, dt.date(2026, 11, 1), dt.date(2026, 11, 15))
    assert before == Decimal("8.13"), "a fee assessed on 10/15 must still charge 1.50%"
    assert after == Decimal("9.49"), "a fee assessed on 11/15 must charge the 1.75% from 11/01"


def test_def_rat_8827_tc2__the_columns_stay_and_one_dated_row_is_written(brazos, dana):
    row = _late_copy(brazos, dana, "LATE-W2")
    with tenant_ctx(brazos):
        _edit(dana, row["id"], "0.0175", "6.00")
        charge = rating_models.Charge.objects.get(pk=row["id"])
        assert charge.percent == Decimal("0.015") and charge.min_amount == Decimal("5.00")
        rows = list(rating_models.ChargeCodeAmount.objects.filter(charge_id=charge.id))
        assert len(rows) == 1
        only = rows[0]
        assert (only.size_class, only.customer_class) == (ALL_SIZES, None)
        assert only.percent == Decimal("0.0175") and only.min_amount == Decimal("6.00")
        assert only.effective_from == CHANGE_FROM and only.effective_to is None
        assert only.killed_at is None
        assert charge_prices.class_terms_on(charge, None, dt.date(2026, 10, 15)) is None
        # The screen's row: today's pair is still the columns; the class list stays per-class only.
        served = rating_selectors.charge_row(charge)
        assert served["class_terms"] == []


def test_def_rat_8827_tc3__resaving_what_was_shown_writes_nothing(brazos, dana):
    row = _late_copy(brazos, dana, "LATE-W3")
    with tenant_ctx(brazos):
        rating_services.update_charge(
            dana,
            row["id"],
            {"percent": "0.015", "min_amount": "5.00", "name": "Late payment fee", "reason": REASON},
        )
        assert not rating_models.ChargeCodeAmount.objects.filter(charge_id=row["id"]).exists()
