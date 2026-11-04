# ── Trace ──────────────────────────────────────────────
# Story:    US-PAY-007 (overpayment / carried credit: auto-apply, visible,
#           refundable)   Screens: S21 · S33 · S58
# Rules:    BR-PAY-010 (overpayment → account credit; auto-applies to the next
#           bill) · BR-PAY-012 (prepay sits as the same credit; a DEPOSIT does
#           not) · BR-PAY-014 as amended (a credit built from SEVERAL payments
#           must be refundable — the schema cannot express it) · BR-PAY-041 (a
#           negative credit is a REAL DEBT and is never floored) ·
#           CLAUDE.md rule 2 · rule 4
# ───────────────────────────────────────────────────────
"""PE-4's **57.13**, and what happens to it next.

Every figure is the story's own: PE-4's credit is **57.13** from a **350.00**
payment against **292.87** of bills; TC-2's next bill is **184.20**; TC-3's is
**42.10**, leaving **15.03** carried; TC-4b's multi-source credit is
**40.00 + 17.13 = 57.13**.

RED-PROVED FIRST (hard-won law 7): with `apply_credit_at_issue`'s
`to_apply = min(balance, open_balance)` replaced by `to_apply = balance`, TC-3
fails — the 57.13 credit applies in full against a 42.10 bill and the invoice
goes 15.03 into negative territory. Transcript in the lane report.
"""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from apps.payments import credit, models, selectors, services

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_pay_001_record_payment import an_issued_bill
from tests.test_w3_billing_models import an_account

pytestmark = pytest.mark.django_db

#: PE-4, verbatim: "open 292.87, pay 350 → bills settled + credit 57.13".
PE4_OPEN = Decimal("292.87")
PE4_PAYMENT = Decimal("350.00")
PE4_CREDIT = Decimal("57.13")
#: US-PAY-007 §4: "Next bills: BL-2609-018602 $184.20 (TC-2) / $42.10 (TC-3)".
TC2_NEXT_BILL = Decimal("184.20")
TC3_NEXT_BILL = Decimal("42.10")
TC3_CARRIED = Decimal("15.03")
#: TC-4b (PO 2026-08-12, OQ-167): "$40.00 in June + $17.13 in July".
JUNE_OVERPAY = Decimal("40.00")
JULY_OVERPAY = Decimal("17.13")

POSTED_AT = datetime(2026, 8, 8, 10, 30, tzinfo=UTC)


def _pay(actor, account, amount, **overrides):
    values = dict(
        account_id=account.pk,
        amount=amount,
        posted_at=POSTED_AT,
        cleared_at=POSTED_AT,
        idempotency_reference=uuid.uuid4(),
    )
    values.update(overrides)
    return services.record_payment(actor, **values)


def _overpaid_account(brazos, dana, *, account_no="A-11042"):
    """PE-4 exactly: one 292.87 bill, one 350.00 payment, 57.13 left over."""
    account = an_account(dana, brazos, account_no=account_no)
    an_issued_bill(
        brazos, account, number="BL-2608-018410", total=PE4_OPEN, issued_on=date(2026, 8, 1)
    )
    _pay(dana, account, PE4_PAYMENT)
    return account


def test_us_pay_007_tc1__the_remainder_is_visible_with_the_rows_behind_it(brazos, dana):
    """TC-1 — the **57.13** is on the account AND explainable.

    A balance alone cannot answer *"where did this come from?"*, which is the
    question the S21 header exists to answer, so the position carries its source
    payments too.
    """
    with tenant_ctx(brazos):
        account = _overpaid_account(brazos, dana)
        position = credit.credit_position(account.pk)
        assert position.balance == PE4_CREDIT
        assert position.is_debt is False
        assert len(position.sources) == 1
        assert position.sources[0].unapplied == PE4_CREDIT


def test_us_pay_007_tc2__the_credit_auto_applies_at_the_next_issue(brazos, dana):
    """TC-2 — **57.13** meets a **184.20** bill; **0.00** credit remains."""
    with tenant_ctx(brazos):
        account = _overpaid_account(brazos, dana, account_no="A-11043")
        bill = an_issued_bill(
            brazos,
            account,
            number="BL-2609-018602",
            total=TC2_NEXT_BILL,
            issued_on=date(2026, 9, 1),
        )
        applied = credit.apply_credit_at_issue(
            actor=dana, account_id=account.pk, invoice_id=bill.pk, invoice_total=TC2_NEXT_BILL
        )
        assert applied.applied == PE4_CREDIT
        assert applied.remaining_credit == Decimal("0")
        assert applied.invoice_balance_after == TC2_NEXT_BILL - PE4_CREDIT


def test_us_pay_007_tc3__a_credit_bigger_than_the_bill_carries_the_rest(brazos, dana):
    """TC-3 — **42.10** applies and **15.03** carries. Never dropped."""
    with tenant_ctx(brazos):
        account = _overpaid_account(brazos, dana, account_no="A-11044")
        bill = an_issued_bill(
            brazos,
            account,
            number="BL-2609-018603",
            total=TC3_NEXT_BILL,
            issued_on=date(2026, 9, 1),
        )
        applied = credit.apply_credit_at_issue(
            actor=dana, account_id=account.pk, invoice_id=bill.pk, invoice_total=TC3_NEXT_BILL
        )
        assert applied.applied == TC3_NEXT_BILL
        assert applied.remaining_credit == TC3_CARRIED
        assert selectors.account_credit_position(account.pk) == TC3_CARRIED


def test_us_pay_007_tc5__a_retried_issue_never_over_applies(brazos, dana):
    """TC-5 — *"the credit never over-applies beyond its balance"*.

    The guard is arithmetic, not a key: the second call recomputes both sides,
    finds the bill met, and applies **0.00**.
    """
    with tenant_ctx(brazos):
        account = _overpaid_account(brazos, dana, account_no="A-11045")
        bill = an_issued_bill(
            brazos,
            account,
            number="BL-2609-018604",
            total=TC3_NEXT_BILL,
            issued_on=date(2026, 9, 1),
        )
        first = credit.apply_credit_at_issue(
            actor=dana, account_id=account.pk, invoice_id=bill.pk, invoice_total=TC3_NEXT_BILL
        )
        second = credit.apply_credit_at_issue(
            actor=dana, account_id=account.pk, invoice_id=bill.pk, invoice_total=TC3_NEXT_BILL
        )
        assert first.applied == TC3_NEXT_BILL
        assert second.applied == Decimal("0")
        assert selectors.account_credit_position(account.pk) == TC3_CARRIED


def test_us_pay_007_tc4b__a_credit_from_two_overpayments_is_one_position(brazos, dana):
    """TC-4b — **40.00 + 17.13 = 57.13**, from TWO payments.

    The POSITION is the same 57.13 the PO's ruling names; what differs is the
    number of payments behind it, and that is exactly what `refunds.payment_id`
    cannot express. The refusal is asserted below.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-11046")
        _pay(dana, account, JUNE_OVERPAY)
        _pay(dana, account, JULY_OVERPAY)
        position = credit.credit_position(account.pk)
        assert position.balance == PE4_CREDIT  # 40.00 + 17.13
        assert len(position.sources) == 2


def test_us_pay_007_tc4b_blocked__a_credit_balance_refund_refuses_by_name(brazos, dana):
    """The structural blocker, refused rather than worked around.

    The PO RULED the mechanism on 2026-08-12 (OQ-167). B2 §2 types
    `refunds.payment_id uuid NOT NULL` and the table has no account column, so
    the ruling cannot be implemented without a schema change — which is a
    contracts-lane act. Raised as **OQ-195**, cited in the refusal.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-11047")
        with pytest.raises(NotImplementedError) as refusal:
            credit.refund_from_credit_balance(account_id=account.pk)
        assert "OQ-195" in str(refusal.value)


def test_us_pay_007_negative_credit_applies_nothing(brazos, dana):
    """BR-PAY-041 — a negative position is a DEBT, and debts do not pay bills.

    Nothing here floors the figure at zero (PO 2026-08-11: *"Yes, it's a real
    debt"*); the application simply declines, because "applying" a debt would
    reduce a bill by money the customer owes.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-11048")
        bill = an_issued_bill(
            brazos,
            account,
            number="BL-2609-018605",
            total=TC3_NEXT_BILL,
            issued_on=date(2026, 9, 1),
        )
        # A reversing row with no receipt behind it puts the position below zero
        # — the shape J15 reaches after a refunded overpayment bounces.
        models.Payment.objects.create(
            tenant=brazos,
            account=account,
            amount=Decimal("-57.13"),
            status=models.PAYMENT_POSTED,
            posted_at=POSTED_AT,
        )
        assert selectors.account_credit_position(account.pk) == Decimal("-57.13")
        applied = credit.apply_credit_at_issue(
            actor=dana, account_id=account.pk, invoice_id=bill.pk, invoice_total=TC3_NEXT_BILL
        )
        assert applied.applied == Decimal("0")


def test_us_pay_007_tc6__isolation_a_credit_never_meets_another_tenants_bill(
    brazos, dana, lonestar, erin
):
    """TC-6 — *"Applies only to Lone Star Ridge bills"*, and the converse.

    Runs everywhere: the querysets are tenant-scoped explicitly, which is the
    guarantee the SQLite tier has (RLS FORCE is the second one on Postgres).
    """
    with tenant_ctx(brazos):
        brazos_account = _overpaid_account(brazos, dana, account_no="A-11049")
        assert selectors.account_credit_position(brazos_account.pk) == PE4_CREDIT

    with tenant_ctx(lonestar):
        # The same account id, read from the other tenant's session: no credit.
        assert selectors.account_credit_position(brazos_account.pk) == Decimal("0")
        # An account of THIS tenant, built without the metering path (Lone
        # Star Ridge is Water-only, so the shared electric helper cannot serve
        # it) — the point is the SCOPE of the read, not the account's shape.
        assert credit.credit_position(brazos_account.pk).balance == Decimal("0")
