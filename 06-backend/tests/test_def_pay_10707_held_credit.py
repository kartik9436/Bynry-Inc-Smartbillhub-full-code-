"""DEF-PAY-10707 — money paid beyond the bill shows on the account (tester L2-01).

The tester's case, verbatim from the payments audit of 2026-10-30: *"Farid
Delacroix owes $165.00 and pays $170.00 at Hy-Vee. $165.00 pays his bill, but
his account shows Balance $0.00 and 'No credits on this account.'"*

The books were right all along — $165.00 relieved `1200 AR` and **$5.00 was
credited to `2400 Customer credit`** (BR-PAY-012). The account screen asked the
receivable alone and so told a clerk there was nothing to refund. The cell now
reads the account's NET position, 1200 + 2400, signed (BR-PAY-041).

PROVED RED FIRST (hard-won law 7), against the tip before the fix:
  * `test_farid_pays_170_on_165_and_the_header_reads_minus_5` →
    `AssertionError: assert '0.000000' == '-5.000000'`
  * `test_kevin_pays_the_same_bill_twice_and_reads_minus_259_23` →
    `AssertionError: assert '0.000000' == '-259.230000'`
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from apps.customers import selectors as customer_selectors
from apps.ledger import chart
from apps.ledger import posting as ledger_posting
from apps.ledger import selectors as ledger_selectors
from apps.payments import models as payment_models
from apps.payments import selectors as payment_selectors
from apps.payments import services as payment_services

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · marcus
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_pay_001_record_payment import an_issued_bill
from tests.test_w3_billing_models import an_account

pytestmark = pytest.mark.django_db

PAID_AT = datetime(2026, 10, 21, 15, 0, tzinfo=UTC)


def _post_bill_to_ar(bill, amount: Decimal) -> None:
    """The bill's own receivable, posted the way an issue posts it: DR 1200.

    The credit side is the minimum-bill adjustment account only because a test
    needs SOME designated account to balance against; which revenue account a
    bill credits is billing's business and nothing here reads it.
    """
    ar = ledger_selectors.gl_account_id_for_designation(chart.AR)
    other = ledger_selectors.gl_account_id_for_designation(chart.MINIMUM_BILL_ADJUSTMENT)
    dims = {"source_type": "invoice", "source_id": bill.pk, "account_id": bill.account_id}
    ledger_posting.post(
        ledger_posting.PostingRequest(
            posting_key=ledger_posting.posting_key(
                source_type="invoice", source_id=bill.pk, event="issued"
            ),
            entry_date=bill.service_date,
            posted_at=bill.issued_at,
            currency="USD",
            lines=(
                ledger_posting.PostingLine(ledger_account_id=ar, side="debit", amount=amount, **dims),
                ledger_posting.PostingLine(
                    ledger_account_id=other, side="credit", amount=amount, **dims
                ),
            ),
            source_type="invoice",
            source_id=bill.pk,
        )
    )


def _billed(tenant, account, total: str, *, number: str):
    bill = an_issued_bill(
        tenant, account, number=number, total=Decimal(total), issued_on=date(2026, 10, 1)
    )
    _post_bill_to_ar(bill, Decimal(total))
    return bill


def _pay(actor, account, amount: str, **extra):
    return payment_services.record_payment(
        actor,
        account_id=account.pk,
        amount=Decimal(amount),
        posted_at=PAID_AT,
        cleared_at=PAID_AT,
        idempotency_reference=uuid.uuid4(),
        **extra,
    )


def test_farid_pays_170_on_165_and_the_header_reads_minus_5(brazos, marcus):
    with tenant_ctx(brazos):
        account = an_account(marcus, brazos, account_no="A-00031")
        _billed(brazos, account, "165.00", number="BL-2610-000031")

        before = customer_selectors.account_detail(account.pk)
        assert before["balance"] == "165.000000"

        _pay(marcus, account, "170.00")

        after = customer_selectors.account_detail(account.pk)
        # The header: signed, the account is $5.00 in credit.
        assert after["balance"] == "-5.000000"
        # …and payments' own subledger agrees, so the Credits tab's held-credit
        # list and the header cannot tell two stories.
        assert payment_selectors.account_credit_position(account.pk) == Decimal("5.00")
        sources = payment_selectors.account_credit_sources(account.pk)
        assert [Decimal(row["contributed"]) for row in sources["sources"]] == [Decimal("5")]


def test_kevin_pays_the_same_bill_twice_and_reads_minus_259_23(brazos, marcus):
    """Online and by cheque on the same day: the second $259.23 meets nothing."""
    with tenant_ctx(brazos):
        account = an_account(marcus, brazos, account_no="A-00044")
        _billed(brazos, account, "259.23", number="BL-2610-000044")
        _pay(marcus, account, "259.23")
        assert customer_selectors.account_detail(account.pk)["balance"] == "0.000000"

        _pay(marcus, account, "259.23", confirmation="1187")
        assert customer_selectors.account_detail(account.pk)["balance"] == "-259.230000"


def test_a_deposit_is_held_and_never_reads_as_credit(brazos, marcus):
    """US-PAY-002 TC-1 — a deposit credits `deposit_liability`, not 2400, so the
    account's balance is untouched by it and no held-credit row appears."""
    with tenant_ctx(brazos):
        account = an_account(marcus, brazos, account_no="A-00052")
        _billed(brazos, account, "80.00", number="BL-2610-000052")
        _pay(marcus, account, "150.00", purpose=payment_models.PURPOSE_DEPOSIT)

        assert customer_selectors.account_detail(account.pk)["balance"] == "80.000000"
        assert payment_selectors.account_credit_sources(account.pk)["sources"] == []


def test_the_receivable_reads_are_unchanged(brazos, marcus):
    """`outstanding` and the tie-out ask about the RECEIVABLE: an account in
    credit adds nothing to it and the 1200 slice still reads 0.00."""
    from apps.ledger import reporting

    with tenant_ctx(brazos):
        account = an_account(marcus, brazos, account_no="A-00061")
        _billed(brazos, account, "165.00", number="BL-2610-000061")
        _pay(marcus, account, "170.00")

        ar_only = reporting.ar_positions(account_ids=[str(account.pk)])
        assert ar_only["positions"][str(account.pk)] == Decimal("0")
        net = reporting.ar_positions(account_ids=[str(account.pk)], with_held_credit=True)
        assert net["positions"][str(account.pk)] == Decimal("-5")
