# ── Trace ──────────────────────────────────────────────
# Rulings: PO 2026-10-01 (decision log "SIX PO RULINGS IN ONE MESSAGE"):
#          (6) OQ-217, verbatim *"A · Show the whole account: last bill $34.00 −
#          paid $120.00 + new charges $37.25 = $48.75 credit, nothing to pay"*;
#          (1) *"A · Ask for new charges + this month's instalment: $62 + $45 =
#          $107, with the rest of the plan shown as not yet due."*
# Defects: DEF-BIL-8670 (a paid bill in credit asks its full total) ·
#          DEF-BIL-8412 (Apply next bill billed exactly like Apply to this bill)
# Rows:    BULK-CHG-58 · BULK-CHG-61
# Rules:   BR-BIL-1065 · BR-BIL-1061 · BR-BIL-035 (arithmetic unchanged;
#          ❄️ WE-1 45.00 − 0.00 + 247.87 = 292.87)
# Code:    apps/billing/issue._stamp_balance_forward · open_balance.whole_account
#          · apps/payments/billing_seam.payments_received_for_account /
#          plan_instalments_for_bill · documents._summary
# ───────────────────────────────────────────────────────
"""The bill's balance forward reads the whole account since the last bill.

Each case is the PO's own worked figure, written RED FIRST (law 7): before the
change the overpaid bill printed *previous 0.00 · payments 0.00 · total due
37.25* and the plan bill asked $332.00.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from apps.billing import documents, issue
from apps.billing import models as billing_models

from tests.test_bbr_fixed_charge_next_bill import _setup
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

UTC = timezone.utc


def _bill(tenant, account, *, no, total, start, end, issued_at=None):
    return billing_models.Invoice.objects.create(
        tenant=tenant,
        account=account,
        service_date=end,
        period_start=start,
        period_end=end,
        status=billing_models.INVOICE_ISSUED if issued_at else billing_models.INVOICE_DRAFT,
        currency="USD",
        subtotal=Decimal(total),
        invoice_no=no,
        issued_at=issued_at,
        due_date=None,
        tax_total=Decimal("0"),
        total=Decimal(total),
    )


def _pay(tenant, account, amount, posted_at, *, against=None, applied=None):
    from apps.payments import models as payment_models

    payment = payment_models.Payment.objects.create(
        tenant=tenant,
        account=account,
        amount=Decimal(amount),
        currency="USD",
        status=payment_models.PAYMENT_CLEARED,
        posted_at=posted_at,
    )
    if against is not None:
        payment_models.Allocation.objects.create(
            tenant=tenant, payment=payment, invoice=against, amount=Decimal(applied)
        )
    return payment


def _money(block, key):
    return Decimal(block[key]).quantize(Decimal("0.01"))


def _total_due_printed(bill):
    fields, _absent = documents._summary(bill, bill.bill_payload, "USD")
    return {f.label: f.value for f in fields}


# ══════════════════════════════════════════════════════════════════════════
# (6) OQ-217 — THE OVERPAID CUSTOMER: $34.00 − $120.00 + $37.25 = $48.75 credit
# ══════════════════════════════════════════════════════════════════════════
# BULK-CHG-58
def test_overpaid_customer_sees_a_48_75_credit_and_nothing_to_pay(brazos, dana):
    with tenant_ctx(brazos):
        _cycle, account, _asset = _setup(brazos, dana, account_no="A-07001", asset_no="M-7001", base="8")
        september = _bill(
            brazos, account, no="BL-2609-070001", total="34.00",
            start=date(2026, 9, 1), end=date(2026, 9, 30),
            issued_at=datetime(2026, 10, 1, 9, 0, tzinfo=UTC),
        )
        _pay(brazos, account, "120.00", datetime(2026, 10, 5, 12, 0, tzinfo=UTC), against=september, applied="34.00")
        october = _bill(
            brazos, account, no="BL-2610-070001", total="37.25",
            start=date(2026, 10, 1), end=date(2026, 10, 31),
        )
        block = issue._stamp_balance_forward(october, currency="USD", due_date=date(2026, 11, 22))
        october.refresh_from_db()
        printed = _total_due_printed(october)

    assert _money(block, "previous_balance") == Decimal("34.00")
    assert _money(block, "payments_credits") == Decimal("120.00")
    assert _money(block, "current_charges") == Decimal("37.25")
    assert _money(block, "total_due") == Decimal("-48.75")
    assert block["basis"] == issue.BALANCE_FORWARD_BASIS == "whole_account_since_last_bill"
    assert printed["Total due"] == "0.00 USD · credit 48.75 USD"


def test_we1_is_unmoved_45_minus_0_plus_247_87(brazos, dana):
    """❄️ WE-1: one unpaid 45.00 prior bill and 247.87 of current charges."""
    with tenant_ctx(brazos):
        _cycle, account, _asset = _setup(brazos, dana, account_no="A-07002", asset_no="M-7002", base="8")
        _bill(
            brazos, account, no="BL-2608-070002", total="45.00",
            start=date(2026, 8, 1), end=date(2026, 8, 31),
            issued_at=datetime(2026, 9, 1, 9, 0, tzinfo=UTC),
        )
        current = _bill(
            brazos, account, no="BL-2609-070002", total="247.87",
            start=date(2026, 9, 1), end=date(2026, 9, 30),
        )
        block = issue._stamp_balance_forward(current, currency="USD")
    assert (
        _money(block, "previous_balance"),
        _money(block, "payments_credits"),
        _money(block, "total_due"),
    ) == (Decimal("45.00"), Decimal("0.00"), Decimal("292.87"))


def test_a_bill_paid_in_full_reads_like_a_statement_100_minus_100(brazos, dana):
    """OQ-217's own consequence, now the other way: paid last month's $100.00 in
    full → 100.00 − 100.00, not 0.00 − 0.00."""
    with tenant_ctx(brazos):
        _cycle, account, _asset = _setup(brazos, dana, account_no="A-07003", asset_no="M-7003", base="8")
        august = _bill(
            brazos, account, no="BL-2608-070003", total="100.00",
            start=date(2026, 8, 1), end=date(2026, 8, 31),
            issued_at=datetime(2026, 9, 1, 9, 0, tzinfo=UTC),
        )
        _pay(brazos, account, "100.00", datetime(2026, 9, 10, 9, 0, tzinfo=UTC), against=august, applied="100.00")
        current = _bill(
            brazos, account, no="BL-2609-070003", total="60.00",
            start=date(2026, 9, 1), end=date(2026, 9, 30),
        )
        block = issue._stamp_balance_forward(current, currency="USD")
    assert (_money(block, "previous_balance"), _money(block, "payments_credits"), _money(block, "total_due")) == (
        Decimal("100.00"),
        Decimal("100.00"),
        Decimal("60.00"),
    )


# ══════════════════════════════════════════════════════════════════════════
# DEF-BIL-8412 — Apply next bill: the payment is on the NEXT bill, not this one
# ══════════════════════════════════════════════════════════════════════════
# BULK-CHG-58
@pytest.mark.parametrize("deferred", [False, True], ids=["apply_this_bill", "apply_next_bill"])
def test_apply_next_bill_moves_the_payment_to_the_next_bill(brazos, dana, monkeypatch, deferred):
    """August $200.00 (issued Sep 1). $120.00 posted Oct 1, after September's
    period. *Apply to this bill*: September 200 − 120 + 50 = 130. *Apply next
    bill*: September 200 − 0 + 50 = 250, and October counts the 120:
    250 − 120 + 60 = 190."""
    with tenant_ctx(brazos):
        _cycle, account, _asset = _setup(
            brazos, dana, account_no=f"A-0700{4 + deferred}", asset_no=f"M-700{4 + deferred}", base="8"
        )
        august = _bill(
            brazos, account, no=f"BL-2608-07000{4 + deferred}", total="200.00",
            start=date(2026, 8, 1), end=date(2026, 8, 31),
            issued_at=datetime(2026, 9, 1, 9, 0, tzinfo=UTC),
        )
        _pay(brazos, account, "120.00", datetime(2026, 10, 1, 15, 0, tzinfo=UTC), against=august, applied="120.00")
        september = _bill(
            brazos, account, no=f"BL-2609-07000{4 + deferred}", total="50.00",
            start=date(2026, 9, 1), end=date(2026, 9, 30),
        )
        monkeypatch.setattr(issue, "_defers_late_payments", lambda invoice: deferred)
        sep_block = issue._stamp_balance_forward(september, currency="USD")
        billing_models.Invoice.objects.filter(pk=september.pk).update(
            status=billing_models.INVOICE_ISSUED,
            issued_at=datetime(2026, 10, 2, 9, 0, tzinfo=UTC),
        )
        monkeypatch.setattr(issue, "_defers_late_payments", lambda invoice: False)
        october = _bill(
            brazos, account, no=f"BL-2610-07000{4 + deferred}", total="60.00",
            start=date(2026, 10, 1), end=date(2026, 10, 31),
        )
        oct_block = issue._stamp_balance_forward(october, currency="USD")

    sep = (_money(sep_block, "previous_balance"), _money(sep_block, "payments_credits"), _money(sep_block, "total_due"))
    octo = (_money(oct_block, "previous_balance"), _money(oct_block, "payments_credits"), _money(oct_block, "total_due"))
    if deferred:
        assert sep == (Decimal("200.00"), Decimal("0.00"), Decimal("250.00"))
        assert sep_block["payments_through"] == "2026-09-30"
        assert octo == (Decimal("250.00"), Decimal("120.00"), Decimal("190.00"))
    else:
        assert sep == (Decimal("200.00"), Decimal("120.00"), Decimal("130.00"))
        assert "payments_through" not in sep_block
        assert octo == (Decimal("130.00"), Decimal("0.00"), Decimal("190.00"))


def test_apply_next_bill_is_read_from_the_runs_current_decision():
    from apps.billing import decisions

    assert decisions.CHOICE_APPLY_NEXT_BILL == "apply_next_bill"
    assert issue._defers_late_payments(billing_models.Invoice()) is False


# ══════════════════════════════════════════════════════════════════════════
# (1) THE PAYMENT-PLAN BILL — $62 + $45 = $107; $225 not yet due
# ══════════════════════════════════════════════════════════════════════════
# BULK-CHG-61
def test_a_plan_customers_bill_asks_new_charges_plus_this_months_instalment(brazos, dana):
    from apps.payments.collections_models import PaymentPlan, PaymentPlanInstallment

    with tenant_ctx(brazos):
        _cycle, account, _asset = _setup(brazos, dana, account_no="A-07010", asset_no="M-7010", base="8")
        _bill(
            brazos, account, no="BL-2608-070010", total="270.00",
            start=date(2026, 8, 1), end=date(2026, 8, 31),
            issued_at=datetime(2026, 9, 1, 9, 0, tzinfo=UTC),
        )
        plan = PaymentPlan.objects.create(
            tenant=brazos, account=account, total_amount=Decimal("270"), installment_count=6,
            status="active", proposed_on=date(2026, 9, 20), signed_on=date(2026, 9, 21),
        )
        for seq in range(1, 7):
            PaymentPlanInstallment.objects.create(
                tenant=brazos, plan=plan, seq=seq,
                due_date=date(2026, 9 + seq, 15) if seq <= 3 else date(2027, seq - 3, 15),
                amount=Decimal("45"),
            )
        current = _bill(
            brazos, account, no="BL-2609-070010", total="62.00",
            start=date(2026, 9, 1), end=date(2026, 9, 30),
        )
        # Due 22 Oct: the 15 Oct instalment is this month's; five are not yet due.
        block = issue._stamp_balance_forward(current, currency="USD", due_date=date(2026, 10, 22))
        current.refresh_from_db()
        printed = _total_due_printed(current)

    assert _money(block, "total_due") == Decimal("107.00")
    assert _money(block, "plan_due_now") == Decimal("45.00")
    assert _money(block, "plan_not_yet_due") == Decimal("225.00")
    # BR-BIL-035's own lines are untouched: 270 − 0 + 62; the plan line is extra.
    assert (_money(block, "previous_balance"), _money(block, "payments_credits")) == (
        Decimal("270.00"),
        Decimal("0.00"),
    )
    assert printed["Payment plan, not yet due"] == "-225.00 USD"
    assert printed["Total due"] == "107.00 USD"


def test_a_bill_without_a_plan_carries_no_plan_line(brazos, dana):
    with tenant_ctx(brazos):
        _cycle, account, _asset = _setup(brazos, dana, account_no="A-07011", asset_no="M-7011", base="8")
        current = _bill(
            brazos, account, no="BL-2609-070011", total="62.00",
            start=date(2026, 9, 1), end=date(2026, 9, 30),
        )
        block = issue._stamp_balance_forward(current, currency="USD", due_date=date(2026, 10, 22))
    assert "plan_not_yet_due" not in block
    assert _money(block, "total_due") == Decimal("62.00")


def test_the_worked_figures_foot():
    assert Decimal("34.00") - Decimal("120.00") + Decimal("37.25") == Decimal("-48.75")
    assert Decimal("62") + Decimal("45") == Decimal("107")
    assert Decimal("270") - Decimal("0") + Decimal("62") - Decimal("225") == Decimal("107")
