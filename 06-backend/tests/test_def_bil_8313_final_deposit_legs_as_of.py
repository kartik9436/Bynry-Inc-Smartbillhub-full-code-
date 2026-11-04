# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-011 (final bill) · US-BIL-033 (one-time send)   Screens: S30
# Defect:   DEF-BIL-8313 — every final bill for an account holding a deposit
#           was refused at Send
# Rules:    BR-BIL-013 (deposit + interest apply first) · BR-CUS-057 (interest
#           accrues to the move-out day) · BR-TEN-043 / G6 (no wall clock on a
#           money path) · hard rule 5 (only the posting service writes lines)
# 🔒 ledger posting — HUMAN-REVIEW-PENDING, see 09-human-review-ledger.md
# ───────────────────────────────────────────────────────
"""DEF-BIL-8313 — the deposit legs at issue name the day the interest accrues to.

`posting_seam.emit_final_bill_deposit_legs` asked
`final_bill.deposit_credit_for(account_id)` with NO day. The customers accrual
engine answers `None` for a day nobody named — deliberately, gate G6 keeps a
wall clock off a money path — and `deposit_credit_for` then refuses by name, so
a final bill for any account holding a deposit could be previewed and drafted
and was refused at Send (J70 E3: *$150.00 held since 2025-07-01, refund due
$46.33, Send → 422*).

The day is the bill's own `period_end` — the MOVE-OUT DAY. It is the day the
preview's deposit row and `settle_final_bill` already read (`BR-CUS-056`: *"the
OUTGOING account pays the move day, so `period_end` IS `moved_out_on`"*), so the
posted legs and the settlement the clerk saw are one accrual, not two.

The first test is the wiring (which day is passed). The second runs the REAL
accrual engine — no stub — and shows the two calls side by side: without a day
it refuses, with the move-out day it answers. It is run on PostgreSQL with
`--ds=config.settings.pgtest` as well as on the default suite.
"""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest

from apps.billing import final_bill, posting_seam
from apps.billing.exceptions import BillingRuleError
from tests.test_us_bil_001_prepare import a_billed_unit, a_cycle, a_priced_plan
from tests.test_us_bil_011_final_bill import MOVE_OUT, an_account_with_deposit
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db


def _final_invoice(account_id):
    return SimpleNamespace(
        bill_type=posting_seam.BILL_TYPE_FINAL,
        account_id=account_id,
        currency="USD",
        period_end=MOVE_OUT,
        service_date=MOVE_OUT,
        pk=uuid.uuid4(),
    )


def test_def_bil_8313__the_deposit_legs_ask_for_the_interest_to_the_move_out_day(monkeypatch):
    asked = []

    def spy(account_id, as_of=None):
        asked.append((account_id, as_of))
        return final_bill.DepositCredit(
            principal=Decimal("0"), interest=Decimal("0"), currency="USD", received_on=None
        )

    monkeypatch.setattr(final_bill, "deposit_credit_for", spy)
    legs = posting_seam.emit_final_bill_deposit_legs(
        _final_invoice("ACC-1"), posted_at=datetime(2026, 6, 15, 9, 0, tzinfo=timezone.utc)
    )
    assert legs == ()
    assert asked == [("ACC-1", MOVE_OUT)]


def test_def_bil_8313__the_real_accrual_answers_for_the_move_out_day_and_refuses_for_none(
    brazos, dana
):
    with tenant_ctx(brazos):
        plan = a_priced_plan(brazos)
        unit = a_billed_unit(dana, brazos, a_cycle(brazos), plan, asset_no="M-8313", label="A")
        account = an_account_with_deposit(brazos, unit["id"], "A-8313")

        with pytest.raises(BillingRuleError):
            final_bill.deposit_credit_for(account.id)

        credit = final_bill.deposit_credit_for(account.id, MOVE_OUT)

    assert credit.exists
    assert credit.principal == Decimal("150.00")
    assert credit.currency == "USD"
    assert credit.interest is not None
