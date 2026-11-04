# ── Trace ──────────────────────────────────────────────
# Change:  CR-186-BRC10 · T14 — ONE balance formula, every reader.
# Defect:  DEF-PAY-10340 — every balance reader excluded only `processing`
#          (and deposits), so a `failed` payment (a cheque voided at the
#          counter) and a lone `cancelled` row counted as money received.
# Ruling:  decision log 2026-10-21, *"The payment lifecycle, stated by the PO
#          for every method"*, rulings 3, 4 and 6 — PO verbatim: *"when paymet
#          is posted ; we need to change the opening balance formalue so that
#          opening balance reflect the new opening balance; if payment is
#          cancled then it will not be considered … you will ahve to take
#          refunds or credits into account while calcualting opening
#          balance"*.
# Rules:   BR-BIL-035 · BR-PAY-041 (signed credit position) · US-PAY-002 TC-1
#          (a deposit is never credit) · CLAUDE.md hard rule 2 (money)
# ───────────────────────────────────────────────────────
"""The balance counts `posted` and `cleared` payments, and nothing else.

THE FORMULA, AS RULED (2026-10-21)
----------------------------------
    balance = Σ issued bills' own charges + migrated opening
            − Σ payments in status `posted` or `cleared`
              (reversing rows, status `reversed`, negative; deposits excluded)
            + Σ refunds issued or cleared
    credits are CREDIT-type payment rows and ride the same sum.

`cancelled`, `failed` and `processing` NEVER count. The one statement of that
set is `apps.payments.balance_rule.BALANCE_COUNTED_PAYMENT_STATUSES`; every
reader below reads it.

THE FIGURES SHOWN TO THE PO
---------------------------
A $150.00 bill and $120.00 posted → **$30.00**. A $20.00 refund issued on top
→ **$50.00**.

RED FIRST (hard-won law 7)
--------------------------
Before the fix `test_a_failed_payment_never_reduces_the_balance` failed on
every reader with the $50.00 failed cheque taken off: 100.00 where 150.00 is
owed. The CONTROL (`test_the_ruled_figures_150_less_120_posted_is_30`) is what
makes the red mean something — a reader that counted nothing at all would pass
the failed case and fail this one.

⚠ **THIS RUNS ON SQLITE AND THE STATUSES ARE PLANTED.** The immutability
trigger does not exist on SQLite, so a payment recorded `processing` (no
clearing date, so no allocation, which is exactly a voided cheque's shape) is
moved to the status under test with an UPDATE — the same posture
`test_cr137_p3_5_cancelled_is_not_unapplied_cash` takes and records. This is a
test of ARITHMETIC; the trigger is PostgreSQL's question.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from apps.billing import models as billing_models
from apps.payments import models as payment_models
from apps.payments import services

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import brazos, dana, lonestar, tenant_ctx  # noqa: F401
from tests.test_us_bil_005_release_issue_api import a_bill_of  # noqa: F401
from tests.test_w3_billing_models import a_run, an_account

pytestmark = pytest.mark.django_db

BILL = Decimal("150.00")
POSTED = Decimal("120.00")
REFUND = Decimal("20.00")
FAILED = Decimal("50.00")
ISSUED_AT = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)
PAID_AT = datetime(2026, 10, 14, 0, 0, tzinfo=UTC)


def a_150_bill(tenant, actor, *, account_no):
    account = an_account(actor, tenant, account_no=account_no)
    run = a_run(tenant, key=f"2026-10|cr186-{account_no}")
    a_bill_of(
        tenant,
        account,
        run,
        invoice_no=f"BL-2610-{account_no[-6:]}",
        total=BILL,
        status=billing_models.INVOICE_ISSUED,
        issued_at=ISSUED_AT,
    )
    return account


def a_payment_in(actor, account, amount, status, *, payment_type=None):
    """A payment in `status`, made the way that status can really arise.

    * `posted`: recorded through `record_payment`, which since CR-186-BRC10
      writes `posted`, applies it to the bill and journals it at posting.
    * `cleared`: recorded, then moved `posted` → `cleared` with its clearing
      date. That is the one move `payments/0051` allows a posted row, and it is
      what bank reconciliation does.
    * anything else (`failed`, `processing`, `cancelled`): a row INSERTED in
      that status, never applied and never journalled. A posted row may not be
      UPDATEd into these, because `payments/0051`'s trigger refuses it on
      PostgreSQL, and this file used to plant them that way (it passed only on
      SQLite, hard-won law 14).
    """
    from django.utils import timezone as dj_timezone

    extra = {}
    if payment_type is not None:
        extra = {"payment_type": payment_type, "reason_code": "goodwill"}
    if status in (payment_models.PAYMENT_POSTED, payment_models.PAYMENT_CLEARED):
        recorded = services.record_payment(
            actor,
            account_id=account.pk,
            amount=amount,
            method_code="card",
            posted_at=PAID_AT,
            idempotency_reference=uuid.uuid4(),
            **extra,
        )
        if status == payment_models.PAYMENT_CLEARED:
            payment_models.Payment.objects.filter(pk=recorded.payment_id).update(
                status=status, cleared_at=dj_timezone.now()
            )
        return payment_models.Payment.objects.get(pk=recorded.payment_id)
    return payment_models.Payment.objects.create(
        tenant_id=account.tenant_id,
        account=account,
        payment_no=f"PMT-2610-{uuid.uuid4().hex[:8].upper()}",
        type=payment_type or payment_models.PAYMENT_TYPE_PAYMENT,
        method=services._method("card"),
        amount=amount,
        currency="USD",
        status=status,
        purpose=payment_models.PURPOSE_BILL,
        posted_at=PAID_AT,
    )


def a_refund(tenant, account, amount, status=payment_models.REFUND_ISSUED):
    return payment_models.Refund.objects.create(
        tenant=tenant,
        account=account,
        amount=amount,
        currency="USD",
        status=status,
        issued_at=PAID_AT,
    )


def every_reader(account):
    """The account's balance as each reader states it — one dict, so a
    failure names the reader that disagrees.

    `consumer-info` is the Invoice Cloud reader and has no formula of its own:
    it is `integrations.seams.customers.balance_map`, which is
    `billing.open_balance`, which asks payments. `credit` is the signed credit
    position, compared through the bill: balance = bill − credit."""
    from apps.billing import open_balance
    from apps.integrations.seams import customers as customers_seam
    from apps.payments import billing_seam, credit, selectors

    key = str(account.pk)
    single = open_balance.open_balance_for_account(account.pk).open_balance
    batched = open_balance.open_balances_for_accounts([key])[key].open_balance
    consumer_info = Decimal(customers_seam.balance_map([account])[key])
    position = selectors.account_credit_position(account.pk)
    bulk = billing_seam.credit_positions_for_accounts([key])[key]
    unapplied = sum(
        (row.amount - credit._applied_of(row) for row in credit._unapplied_by_payment(account.pk)),
        Decimal("0"),
    )
    received = billing_seam.payments_received_for_account(account.pk)
    by_type = billing_seam.payments_received_by_type_for_accounts({key: (None, None)})[key][
        "received"
    ]
    # CR-186-BRC10: a payment is APPLIED at posting, so what the bills still
    # owe is the bill less its allocations, and the credit position is what is
    # held beyond them. Balance = still owed on bills − credit, the identity
    # `billing.open_balance.whole_account` states. (Before CR-186 a `processing`
    # payment never met the bill, so `BILL − credit` happened to be the same.)
    owed = sum(
        (bill.balance for bill in billing_seam.open_invoices_for_account(account.pk).invoices),
        Decimal("0"),
    )
    return {
        "open_balance_for_account": single,
        "open_balances_for_accounts": batched,
        "consumer_info_opening_balance": consumer_info,
        "owed_less_account_credit_position": owed - position,
        "owed_less_credit_positions_for_accounts": owed - bulk,
        "owed_less_unapplied_by_payment": owed - unapplied,
        "bill_less_payments_received_for_account": BILL - received,
        "bill_less_payments_received_by_type": BILL - by_type,
    }


def _all_equal(readings: dict, expected: Decimal) -> list[str]:
    return [f"{name}={value}" for name, value in readings.items() if value != expected]


def test_the_ruled_figures_150_less_120_posted_is_30_and_a_20_refund_makes_50(brazos, dana):
    """The PO's two figures — and the CONTROL that makes the failed case
    below mean something."""
    with tenant_ctx(brazos):
        account = a_150_bill(brazos, dana, account_no="A-186001")
        a_payment_in(dana, account, POSTED, payment_models.PAYMENT_POSTED)
        wrong = _all_equal(every_reader(account), Decimal("30.00"))
        assert not wrong, f"$150 bill − $120 posted must read 30.00 everywhere: {wrong}"

        a_refund(brazos, account, REFUND)
        readings = every_reader(account)
        # `_unapplied_by_payment` lists PAYMENTS and attributes no refund back
        # to them, by its own docstring (*"the rows sum to the position only
        # while nothing has been refunded yet"*), so it is not a balance once a
        # refund exists and is left out of this half.
        readings.pop("owed_less_unapplied_by_payment")
        wrong = _all_equal(readings, Decimal("50.00"))
        assert not wrong, f"…and a $20 refund issued makes it 50.00: {wrong}"


def test_a_cleared_payment_counts_exactly_like_a_posted_one(brazos, dana):
    with tenant_ctx(brazos):
        account = a_150_bill(brazos, dana, account_no="A-186002")
        a_payment_in(dana, account, POSTED, payment_models.PAYMENT_CLEARED)
        wrong = _all_equal(every_reader(account), Decimal("30.00"))
    assert not wrong, wrong


def test_a_failed_payment_never_reduces_the_balance(brazos, dana):
    """`DEF-PAY-10340`. RED before the fix: 100.00 on every reader."""
    with tenant_ctx(brazos):
        account = a_150_bill(brazos, dana, account_no="A-186003")
        a_payment_in(dana, account, FAILED, payment_models.PAYMENT_FAILED)
        wrong = _all_equal(every_reader(account), BILL)
    assert not wrong, f"a $50 failed payment was counted as money received: {wrong}"


def test_a_cancelled_payment_never_reduces_the_balance(brazos, dana):
    """A `cancelled` row is never counted — the original AND its reversing
    row. Planted alone here, so a reader that netted the pair by luck would
    still be caught."""
    with tenant_ctx(brazos):
        account = a_150_bill(brazos, dana, account_no="A-186004")
        a_payment_in(dana, account, FAILED, payment_models.PAYMENT_CANCELLED)
        wrong = _all_equal(every_reader(account), BILL)
    assert not wrong, f"a $50 cancelled payment was counted as money received: {wrong}"


def test_a_processing_payment_still_never_counts(brazos, dana):
    with tenant_ctx(brazos):
        account = a_150_bill(brazos, dana, account_no="A-186005")
        a_payment_in(dana, account, FAILED, payment_models.PAYMENT_PROCESSING)
        wrong = _all_equal(every_reader(account), BILL)
    assert not wrong, wrong


def test_a_reversing_row_counts_negative_so_a_bounce_nets_out(brazos, dana):
    """$120 posted, then a `reversed` row of −$120 (the bounce): back to 150."""
    with tenant_ctx(brazos):
        account = a_150_bill(brazos, dana, account_no="A-186006")
        original = a_payment_in(dana, account, POSTED, payment_models.PAYMENT_POSTED)
        payment_models.Payment.objects.create(
            tenant=brazos,
            account=account,
            payment_no="PMT-2610-REV186",
            type=payment_models.PAYMENT_TYPE_PAYMENT,
            method=original.method,
            amount=-POSTED,
            currency="USD",
            status=payment_models.PAYMENT_REVERSED,
            purpose=payment_models.PURPOSE_BILL,
            posted_at=PAID_AT,
            reverses_payment=original,
        )
        wrong = _all_equal(every_reader(account), BILL)
    assert not wrong, wrong


def test_a_credit_note_is_a_credit_type_row_and_counts(brazos, dana):
    """Ruling 6: *"A credit note already counts as a CREDIT-type payment row"*.
    A $20 goodwill credit, posted, takes $20 off."""
    with tenant_ctx(brazos):
        account = a_150_bill(brazos, dana, account_no="A-186007")
        a_payment_in(
            dana,
            account,
            REFUND,
            payment_models.PAYMENT_POSTED,
            payment_type=payment_models.PAYMENT_TYPE_CREDIT,
        )
        wrong = _all_equal(every_reader(account), Decimal("130.00"))
    assert not wrong, wrong


def test_a_deposit_never_counts_whatever_its_status(brazos, dana):
    """US-PAY-002 TC-1, unchanged by the ruling."""
    with tenant_ctx(brazos):
        account = a_150_bill(brazos, dana, account_no="A-186008")
        donor = a_payment_in(dana, account, FAILED, payment_models.PAYMENT_CANCELLED)
        # Inserted whole rather than UPDATEd: on PostgreSQL the immutability
        # trigger refuses a purpose change on a posted row, correctly.
        payment_models.Payment.objects.create(
            tenant=brazos,
            account=account,
            payment_no="PMT-2610-DEP186",
            type=payment_models.PAYMENT_TYPE_PAYMENT,
            method=donor.method,
            amount=FAILED,
            currency="USD",
            status=payment_models.PAYMENT_POSTED,
            purpose=payment_models.PURPOSE_DEPOSIT,
            posted_at=PAID_AT,
        )
        wrong = _all_equal(every_reader(account), BILL)
    assert not wrong, wrong


def test_the_counted_set_is_exactly_posted_cleared_and_reversed():
    """The constant itself — so widening it is a red test that names the
    ruling, not a silent change to every balance in the product."""
    from apps.payments import balance_rule

    assert set(balance_rule.BALANCE_COUNTED_PAYMENT_STATUSES) == {
        payment_models.PAYMENT_POSTED,
        payment_models.PAYMENT_CLEARED,
        payment_models.PAYMENT_REVERSED,
    }
    never = set(payment_models.PAYMENT_STATUSES) - set(
        balance_rule.BALANCE_COUNTED_PAYMENT_STATUSES
    )
    assert never == {
        payment_models.PAYMENT_PROCESSING,
        payment_models.PAYMENT_FAILED,
        payment_models.PAYMENT_CANCELLED,
    }


def test_another_utility_cannot_see_this_balance(brazos, lonestar, dana):
    """Tenant isolation on the reads: Lone Star asking about a Brazos account
    gets nothing counted from Brazos' payments."""
    from apps.payments import billing_seam

    with tenant_ctx(brazos):
        account = a_150_bill(brazos, dana, account_no="A-186009")
        a_payment_in(dana, account, POSTED, payment_models.PAYMENT_POSTED)
    with tenant_ctx(lonestar):
        assert billing_seam.payments_received_for_account(account.pk) == Decimal("0")
        assert billing_seam.credit_positions_for_accounts([str(account.pk)]) == {
            str(account.pk): Decimal("0")
        }
