# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-PAY-10740 (a second bounce the same day charged no NSF fee)
# Rules:    BR-PAY-013 · BR-BIL-005 · BR-BIL-007 · CLAUDE.md rules 2, 4, 6, 7
# Ruling:   PO 2026-10-30, decision log "One NSF fee per bounced payment; the
#           "Pay for…" screen gets a mock-up first (PO)", item 1 — verbatim
#           *"2. Two bounces on the same day: A"*
# ───────────────────────────────────────────────────────
"""Clara Castillo's two cheques bounce on 31 Oct: two NSF fees, $60.00.

EVERY FIGURE IS THE DECISION LOG'S: cheques **$76.40** and **$40.00** both
return on 31 October; the plan's NSF is **$30.00** → two fee bills, **$60.00**,
and the account owes $76.40 + $40.00 + $60.00 = **$176.40**. A replay of the
first reversal still leaves two. Unticking the second with a reason leaves one.

RED FIRST (law 7): on the tip before the change `tc1` failed — the second
reversal reported `nsf_fee_not_raised` and one fee bill existed, because the
fee bill was keyed (account, `fee`, day).

WHAT WOULD MAKE THESE PASS WRONGLY (law 7, habit 2):
  * dropping the idempotency key altogether would pass `tc1` — `tc2` replays
    the first reversal under a NEW request reference and `tc4` raises the
    same payment's fee twice through billing's own door; both must stay at one;
  * keying on the REVERSING row would pass `tc1` and `tc2` — `tc4` asks for the
    fee twice for ONE bounced payment and must get one bill;
  * a key that changed for every other caller would pass all of these —
    `tc5` asserts the five-part key is byte-identical when no source is given.
"""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal as D

import pytest

from apps.billing import models as billing_models
from apps.billing import nsf_fee
from apps.payments import models, reversal
from core import idempotency

from tests.test_cr108_w1_one_time_fee_lines_and_books import a_one_time_account
from tests.test_def_pay_10698_nsf_fee import (
    _fee_bills,
    _list_on_plan,
    _nsf_code,
    _owed,
    _plan_of,
)
from tests.test_us_bil_001_prepare import (  # noqa: F401
    a_billed_unit,
    a_cycle,
    a_priced_plan,
    an_account,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_pay_001_record_payment import a_payment, an_issued_bill

pytestmark = pytest.mark.django_db

FIRST_CHEQUE = D("76.40")
SECOND_CHEQUE = D("40.00")
NSF_PRICE = D("30.00")
TWO_FEES = D("60.00")
RETURNED_31_OCT = datetime(2026, 10, 31, 10, 0, tzinfo=UTC)


def _clara(brazos, dana, suffix):
    """Clara Castillo: one account on a plan listing NSF $30.00, two bills and
    the two cheques that paid them."""
    account = a_one_time_account(brazos, dana, account_no=f"A-CC{suffix}", asset_no=f"M-CC{suffix}")
    _list_on_plan(brazos, _plan_of(account), _nsf_code(brazos))
    an_issued_bill(
        brazos, account, number=f"BL-CC{suffix}-1", total=FIRST_CHEQUE, issued_on=date(2026, 10, 1)
    )
    an_issued_bill(
        brazos,
        account,
        number=f"BL-CC{suffix}-2",
        total=SECOND_CHEQUE,
        issued_on=date(2026, 10, 2),
    )
    first = models.Payment.objects.get(
        pk=a_payment(dana, account, amount=FIRST_CHEQUE, confirmation="5101").payment_id
    )
    second = models.Payment.objects.get(
        pk=a_payment(dana, account, amount=SECOND_CHEQUE, confirmation="5102").payment_id
    )
    return account, first, second


def _bounce(actor, payment, **overrides):
    values = dict(
        payment_id=payment.pk,
        returned_on=RETURNED_31_OCT,
        reason=models.REVERSAL_REASON_NSF,
        idempotency_reference=uuid.uuid4(),
    )
    values.update(overrides)
    return reversal.reverse_payment(actor, **values)


def _fee_total(account):
    return sum((bill.total for bill in _fee_bills(account)), D("0"))


def test_def_pay_10740_tc1__two_cheques_bounce_on_31_oct_two_fees_60_00(brazos, dana, marcus):
    with tenant_ctx(brazos):
        account, first, second = _clara(brazos, dana, "1")
        a = _bounce(dana, first)
        b = _bounce(dana, second)
        assert a.nsf_fee_status == "charged"
        assert b.nsf_fee_status == "charged", "the second bounce is its own fee"
        assert b.nsf_fee_amount == NSF_PRICE
        assert _fee_bills(account).count() == 2
        assert all(bill.status == billing_models.INVOICE_ISSUED for bill in _fee_bills(account))
        assert _fee_total(account) == TWO_FEES
        assert _owed(account) == FIRST_CHEQUE + SECOND_CHEQUE + TWO_FEES == D("176.40")


def test_def_pay_10740_tc2__replaying_the_first_bounce_still_leaves_two(brazos, dana, marcus):
    with tenant_ctx(brazos):
        account, first, second = _clara(brazos, dana, "2")
        key = uuid.uuid4()
        _bounce(dana, first, idempotency_reference=key)
        _bounce(dana, second)
        same_request = _bounce(dana, first, idempotency_reference=key)
        new_request = _bounce(dana, first)
        assert same_request.created is False
        assert new_request.created is False, "already reversed — nothing written"
        assert _fee_bills(account).count() == 2
        assert _fee_total(account) == TWO_FEES
        assert _owed(account) == D("176.40")


def test_def_pay_10740_tc3__unticking_the_second_with_a_reason_leaves_one(brazos, dana, marcus):
    with tenant_ctx(brazos):
        account, first, second = _clara(brazos, dana, "3")
        _bounce(dana, first)
        b = _bounce(dana, second, charge_nsf_fee=False, nsf_fee_waive_reason="bank error")
        assert b.nsf_fee_status == "nsf_fee_waived"
        assert _fee_bills(account).count() == 1
        assert _fee_total(account) == NSF_PRICE
        assert _owed(account) == FIRST_CHEQUE + SECOND_CHEQUE + NSF_PRICE == D("146.40")


def test_def_pay_10740_tc4__one_bounced_payment_is_charged_once_through_billings_door(
    brazos, dana, marcus
):
    """Billing's own door, asked twice for ONE bounced payment: one bill, and
    the second answer is the named refusal — inside its SAVEPOINT (law 14), so
    on PostgreSQL the caller's transaction is still usable afterwards."""
    with tenant_ctx(brazos):
        account, first, _second = _clara(brazos, dana, "4")
        on = RETURNED_31_OCT.date()
        one = nsf_fee.raise_nsf_fee(dana, account_id=account.pk, on_date=on, payment_id=first.pk)
        two = nsf_fee.raise_nsf_fee(dana, account_id=account.pk, on_date=on, payment_id=first.pk)
        assert one["status"] == "charged"
        assert two["status"] == "nsf_fee_not_raised"
        assert two["invoice_id"] is None
        assert _fee_bills(account).count() == 1, "the transaction is still usable"


def test_def_pay_10740_tc5__every_other_caller_keeps_its_key_byte_for_byte():
    """The reconnection fee, the cut bill, quote bills and every one-time run
    pass no source; their key is the signed five-part string, unchanged."""
    acct = "018f0000-0000-0000-0000-0000000000a1"
    day = date(2026, 10, 31)
    plain = idempotency.one_time_run_key(
        account_id=acct, bill_type="fee", period_start=day, period_end=day
    )
    assert plain == f"one-time|{acct}|fee|2026-10-31|2026-10-31"
    payment = "018f0000-0000-0000-0000-0000000000b2"
    keyed = idempotency.one_time_run_key(
        account_id=acct,
        bill_type="fee",
        period_start=day,
        period_end=day,
        source=f"nsf:{payment}",
    )
    assert keyed == f"one-time|{acct}|fee|2026-10-31|2026-10-31|nsf:{payment}"
    for bad in ("a|b", "  "):
        with pytest.raises(idempotency.IdempotencyKeyError):
            idempotency.one_time_run_key(
                account_id=acct, bill_type="fee", period_start=day, period_end=day, source=bad
            )


def test_def_pay_10746__a_bounce_on_an_account_outside_the_billable_set_still_reverses(
    brazos, marcus
):
    """`DEF-PAY-10746` (lane LBX-A's `test_cr186_paycore::test_t13`): the
    account of a $90.00 cheque is not in the billable set, so no fee bill can
    be raised for it. The reversal must still commit, and the fee is NAMED as
    not priced — never a raise out of `reverse_payment`, never a $0.00."""
    from tests.test_cr186_paycore import _pay, _row
    from tests.test_us_met_helpers import staff_actor

    admin = staff_actor(brazos, role="system_admin", email=f"adm-{uuid.uuid4().hex[:6]}@x.test")
    with tenant_ctx(brazos):
        cheque = _row(_pay(marcus, brazos, "90.00", method="check"))
        bounced = _bounce(admin, cheque)
        assert bounced.created is True, "the reversal stands"
        assert bounced.amount == D("-90.00")
        assert bounced.nsf_fee_status == "nsf_fee_cannot_be_priced"
        assert bounced.nsf_fee_amount is None
        assert "nsf_fee_cannot_be_priced" in {p["code"] for p in bounced.problems}
        assert (
            billing_models.Invoice.objects.filter(
                account_id=cheque.account_id, bill_type="fee"
            ).count()
            == 0
        )


def test_def_pay_10742__the_testers_cheque_4103_on_a_closed_account_still_reverses(
    brazos, dana, marcus
):
    """`DEF-PAY-10742` (lane LBX-B, the tester's case): cheque 4103 $154.00 is
    on an account that has since been CLOSED. A closed account is out of the
    billable set (BR-CUS-055), so no NSF fee can be priced — and the bounce
    still reverses, naming why, with nothing charged."""
    from apps.customers import models as customer_models

    with tenant_ctx(brazos):
        account = a_one_time_account(brazos, dana, account_no="A-CC5", asset_no="M-CC5")
        _list_on_plan(brazos, _plan_of(account), _nsf_code(brazos))
        an_issued_bill(
            brazos, account, number="BL-CC5-1", total=D("154.00"), issued_on=date(2026, 10, 1)
        )
        cheque = models.Payment.objects.get(
            pk=a_payment(dana, account, amount=D("154.00"), confirmation="4103").payment_id
        )
        account.status = customer_models.AccountStatus.objects.get(tenant=brazos, code="closed")
        account.save(update_fields=["status"])

        bounced = _bounce(dana, cheque)

        assert bounced.created is True, "the reversal stands on a closed account"
        assert bounced.amount == D("-154.00")
        assert bounced.nsf_fee_status == "nsf_fee_cannot_be_priced"
        assert bounced.nsf_fee_amount is None
        assert _fee_bills(account).count() == 0
