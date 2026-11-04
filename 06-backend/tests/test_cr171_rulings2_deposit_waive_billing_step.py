# ── Trace ──────────────────────────────────────────────
# Change:  CR-171-BRC10 lane RULINGS-2 — PO ruling (7) of 2026-10-05, decision
#          log "A CLERK CAN STILL WAIVE THE DEPOSIT", verbatim: "(a). Clerks
#          use it today, the server already supports it, and the fix for
#          'waived deposit still billed' is already in place."
# Rules:   BR-CUS-1050 (a Billing Clerk or System Admin waives, with a reason)
#          · DEF-BIL-9709 (a waived deposit is not billed on the first bill)
#          · move_fees.DEPOSIT_NOT_OWED (no deposit row beside a waive)
# ───────────────────────────────────────────────────────
"""**The new Billing step's waive is the server's existing one.**

The body below is exactly what `billingModel.billingPayload` sends once the
clerk presses *Waive deposit* on the Fees table's deposit row and gives a
reason: the deposit row is LEFT OUT of `fees`, and `deposit` is
`{decision: "waived", amount, waive_reason}` — what the old Deposit step sent.

Worked: $150.00 deposit + $25.00 CONN + $40.00 RUSH = $215.00; waived, the
move-in charges **$65.00**, Pay now takes $65.00 by check, no deposit line is
written, the waive and its reason are kept on the account, and the first bill
does not bill the $150.00 (`first_bill._deposit_waived`).

Marcus is a Billing Clerk — the ruling's "clerks use it today".
"""

from decimal import Decimal

import pytest

from apps.billing import first_bill
from apps.customers import models as customers_models
from tests.test_cr171_p1_12_move_in_fees import _move_in, _pay_now, _world, _lines, _paid
from tests.test_us_met_helpers import *  # noqa: F401,F403
from tests.test_us_met_helpers import brazos, marcus, tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db

WAIVED_STEP_BODY = dict(
    fees=[
        {"kind": "fee", "source": "plan", "code": "CONN", "amount": "25.0000"},
        {"kind": "fee", "source": "charge_code", "code": "RUSH", "amount": "40.0000"},
    ],
    deposit={"decision": "waived", "amount": "150.0000", "waive_reason": "Hardship"},
)


def test_ruling_7__the_billing_steps_waive_charges_65_and_keeps_the_reason(brazos, marcus):
    with tenant_ctx(brazos):
        _unit, _plan, outgoing = _world(marcus, brazos)
        result = _move_in(marcus, outgoing, payment=_pay_now("65.0000"), **WAIVED_STEP_BODY)
        account = customers_models.Account.objects.get(pk=result["id"])
        lines = [line.code for line in _lines(result["id"])]
        paid = _paid(result["id"])
        waived_on_first_bill = first_bill._deposit_waived(account.id)
    assert lines == ["CONN", "RUSH"], "a waived deposit writes no deposit line"
    assert Decimal(result["fees"]["total"]) == Decimal("65.0000")
    assert paid == {"prepay": Decimal("65.000000")}
    assert account.deposit_waived_amount == Decimal("150.0000")
    assert account.deposit_waive_reason == "Hardship"
    assert waived_on_first_bill is True, "the first bill must not charge the $150.00"


def test_ruling_7__add_to_bill_puts_65_on_the_first_bill(brazos, marcus):
    with tenant_ctx(brazos):
        _unit, _plan, outgoing = _world(marcus, brazos)
        result = _move_in(marcus, outgoing, payment={"mode": "add_to_bill"}, **WAIVED_STEP_BODY)
    assert Decimal(result["payment"]["on_first_bill"]) == Decimal("65.0000")
