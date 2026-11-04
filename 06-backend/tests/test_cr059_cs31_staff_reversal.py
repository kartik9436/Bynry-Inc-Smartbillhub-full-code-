# ── Trace ──────────────────────────────────────────────
# Change:   CR-059 · CS-31 · task 35 — the general Reverse. The CR calls it
#           *"the single largest hole"*: a wrong amount, a duplicate, a
#           chargeback and a disputed payment are all routine and none of them
#           had any lawful path, because `SUPPORTED_REASONS` was `(nsf,)` and
#           the other three were refused by name.
# Story:    US-PAY-010 (the staff reverse) · US-PAY-009 (the bounce, unchanged)
#           Screens: S33 · S35 · S36
# Rules:    BR-PAY-011 (windows · approval · consequence message — the three
#           clauses that were never built) · BR-PAY-013 (the bounce rule, and
#           its NAME is the boundary) · BR-PAY-1070 (Admin-only, on the SERVICE)
#           · BR-TEN-043 / gate G6 (the caller names the day) · B14 rule 31
# ───────────────────────────────────────────────────────
"""CS-31's own case, and the three clauses that had to exist before it could run.

**THE CASE, VERBATIM FROM THE CR:** *"A customer hands over a cheque for 100.00.
The clerk types 1,000.00 and presses Record. Two minutes later they see it."*
Before today the account was left **900.00 in credit** — money the customer never
paid, which the next bill would spend silently and correctly, because the product
believed the row.

Every figure below is that case or `PE-7`'s, and none of them is invented here.
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from apps.payments import models, reversal, reversal_rules, selectors
from apps.payments.exceptions import PaymentRuleError

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_pay_001_record_payment import (
    PE4_CREDIT,
    PE4_PAYMENT,
    a_payment,
    pe1_bills,
)
from tests.test_w3_billing_models import an_account

pytestmark = pytest.mark.django_db

#: CS-31's own worked figures.
TYPED = Decimal("1000.00")
MEANT = Decimal("100.00")
STRANDED_CREDIT = Decimal("900.00")

#: The business day the correction is made. An INPUT, never a clock (G6).
CORRECTED_ON = datetime(2026, 7, 20, 9, 30, tzinfo=UTC)


def _tender(tenant, code):
    """The tenant's own `payment_methods` row for a code, or None.

    Seeded by provisioning (`ach`, `card`, `check`, `cash`, `lockbox`, `wire`,
    `money_order`). Read rather than created, so the test exercises the same
    lookup the product does.
    """
    from apps.tenancy import models as tenancy_models

    return tenancy_models.PaymentMethod.objects.filter(tenant_id=tenant.id, code=code).first()


def _paid(tenant, actor, *, amount=TYPED, tender="check", posted=CORRECTED_ON):
    """An account with a payment on it, at the tender the window rule names."""
    account = an_account(actor, tenant)
    recorded = a_payment(actor, account, amount=amount, posted_at=posted, cleared_at=posted)
    payment = models.Payment.objects.get(pk=recorded.payment_id)
    method = _tender(tenant, tender)
    if method is not None:
        # A tender is a lookup row, not a payment column the service writes, so
        # it is set here rather than through `record_payment`'s own arguments.
        models.Payment.objects.filter(pk=payment.pk).update(method_id=method.id)
        payment.refresh_from_db()
    return account, payment


# ══════════════════════════════════════════════════════════════════════════
# 1 · ALL FOUR REASONS HAVE A PATH — the hole CS-31 opens with
# ══════════════════════════════════════════════════════════════════════════


def test_all_four_reversal_reasons_are_supported(brazos, dana):
    """`SUPPORTED_REASONS` was `(nsf,)` for three weeks. It is the column now."""
    assert reversal.SUPPORTED_REASONS == models.REVERSAL_REASONS
    assert len(reversal.SUPPORTED_REASONS) == 4
    for reason in ("nsf", "bank_chargeback", "data_entry_error", "customer_dispute"):
        assert reason in reversal.SUPPORTED_REASONS


def test_the_thousand_pound_typo_can_be_undone(brazos, dana):
    """CS-31's own case, end to end: 1,000.00 typed for 100.00, corrected.

    The reversing row is **−1,000.00** and the account's credit position comes
    back to **0.00** — the 900.00 the customer never paid stops being money the
    next bill can spend.
    """
    with tenant_ctx(brazos):
        account, payment = _paid(brazos, dana)
        assert selectors.account_credit_position(account.pk) == TYPED

        result = reversal.reverse_payment(
            dana,
            payment_id=payment.pk,
            returned_on=CORRECTED_ON,
            reason=models.REVERSAL_REASON_DATA_ENTRY_ERROR,
            memo="typed 1,000.00 for 100.00",
            idempotency_reference=uuid.uuid4(),
        )
        assert result.created is True
        assert result.amount == -TYPED
        assert result.credit_reversed == TYPED
        assert selectors.account_credit_position(account.pk) == Decimal("0.00")
        # The stranded 900.00 CS-31 names is the difference between what was
        # typed and what was handed over, and it is gone.
        assert TYPED - MEANT == STRANDED_CREDIT


def test_a_staff_correction_counts_no_returned_payment_against_the_customer(brazos, dana):
    """BR-PAY-013's name IS the boundary, and CS-31 asks for it out loud.

    *"A staff reversal never increments the NSF count, never sets the cash-only
    flag and never queues the bounce letter — the engine already branches on the
    reason for exactly this, and the rule should say so out loud so nobody
    removes the branch."* This is the test that makes removing it go red.
    """
    with tenant_ctx(brazos):
        _account, payment = _paid(brazos, dana)
        result = reversal.reverse_payment(
            dana,
            payment_id=payment.pk,
            returned_on=CORRECTED_ON,
            reason=models.REVERSAL_REASON_DATA_ENTRY_ERROR,
            idempotency_reference=uuid.uuid4(),
        )
        # `None` is "we did not count", which is a different fact from zero.
        assert result.nsf_count is None
        assert result.cash_only_no_autopay is None
        assert result.privilege_flag_tripped is False
        # …and the plan says so in words BEFORE it is done, which is what a
        # clerk actually needs: they are correcting our record, not telling the
        # customer their payment failed.
        plan = reversal_rules.reversal_plan(
            payment, reason=models.REVERSAL_REASON_DATA_ENTRY_ERROR, on=CORRECTED_ON.date()
        )
        assert "staff_reversal_charges_no_returned_item_fee" in {
            problem["code"] for problem in plan["problems"]
        }


# ══════════════════════════════════════════════════════════════════════════
# 2 · CLAUSE ONE — THE WINDOW, PER TENDER, AS A REASON AND NOT A BOOLEAN
# ══════════════════════════════════════════════════════════════════════════


def test_an_ach_outside_sixty_days_is_refused_with_the_window_in_the_message(brazos, dana):
    """BR-PAY-011: ACH 60 days. CS-31 wants the sentence, not a boolean.

    *"this ACH cleared 74 days ago — outside the 60-day window"*.
    """
    paid_on = datetime(2026, 5, 1, 10, 0, tzinfo=UTC)
    with tenant_ctx(brazos):
        _account, payment = _paid(brazos, dana, tender="ach", posted=paid_on)
        if payment.method_id is None:
            pytest.skip("this tenant seeds no `ach` payment method")
        with pytest.raises(PaymentRuleError) as refusal:
            reversal.reverse_payment(
                dana,
                payment_id=payment.pk,
                returned_on=CORRECTED_ON,  # 2026-07-20 — 80 days later
                reason=models.REVERSAL_REASON_CUSTOMER_DISPUTE,
                idempotency_reference=uuid.uuid4(),
            )
        assert "60" in str(refusal.value)
        assert "ach" in str(refusal.value)
        assert "80 days ago" in str(refusal.value)


def test_a_card_has_a_hundred_and_twenty_days_and_an_ach_has_sixty(brazos, dana):
    """The two limits BR-PAY-011 sets, read off the module rather than retyped."""
    assert reversal_rules.REVERSAL_WINDOW_DAYS["ach"] == 60
    assert reversal_rules.REVERSAL_WINDOW_DAYS["card"] == 120
    # A cheque is UNLIMITED and the rule says so by name — this is the value
    # `None` means, and it is why a bounce needs no window at all.
    assert reversal_rules.REVERSAL_WINDOW_DAYS["check"] is None


def test_a_cheque_is_unlimited_so_an_old_one_still_corrects(brazos, dana):
    """BR-PAY-011 puts cheques on an unlimited window. 200 days is fine."""
    paid_on = datetime(2026, 1, 1, 10, 0, tzinfo=UTC)
    with tenant_ctx(brazos):
        _account, payment = _paid(brazos, dana, tender="check", posted=paid_on)
        result = reversal.reverse_payment(
            dana,
            payment_id=payment.pk,
            returned_on=CORRECTED_ON,
            reason=models.REVERSAL_REASON_DATA_ENTRY_ERROR,
            idempotency_reference=uuid.uuid4(),
        )
        assert result.created is True


def test_a_tender_the_rule_never_named_gets_no_window_and_says_so(brazos, dana):
    """A 60-day limit on a wire would be a refusal nobody agreed to.

    The rule names three tenders and this product seeds seven. The four it does
    not name are unlimited and every plan carries the gap by name, so somebody
    can rule on it rather than discover it.
    """
    paid_on = datetime(2026, 1, 1, 10, 0, tzinfo=UTC)
    with tenant_ctx(brazos):
        _account, payment = _paid(brazos, dana, tender="wire", posted=paid_on)
        if payment.method_id is None:
            pytest.skip("this tenant seeds no `wire` payment method")
        plan = reversal_rules.reversal_plan(
            payment, reason=models.REVERSAL_REASON_DATA_ENTRY_ERROR, on=CORRECTED_ON.date()
        )
        assert plan["window"]["named_by_the_rule"] is False
        assert plan["window"]["unlimited"] is True
        assert plan["window"]["within"] is True
        assert "window_not_named_by_the_rule" in {p["code"] for p in plan["problems"]}


def test_the_window_never_applies_to_a_bounce(brazos, dana):
    """A returned item is the BANK's decision and arrives when the bank says.

    An ACH bounce 80 days later is recorded, because refusing it would refuse to
    write down something that has already happened — the money is gone whatever
    this product says.
    """
    paid_on = datetime(2026, 5, 1, 10, 0, tzinfo=UTC)
    with tenant_ctx(brazos):
        _account, payment = _paid(brazos, dana, tender="ach", posted=paid_on)
        result = reversal.reverse_payment(
            dana,
            payment_id=payment.pk,
            returned_on=CORRECTED_ON,
            reason=models.REVERSAL_REASON_NSF,
            idempotency_reference=uuid.uuid4(),
        )
        assert result.created is True
        plan = reversal_rules.reversal_plan(
            payment, reason=models.REVERSAL_REASON_NSF, on=CORRECTED_ON.date()
        )
        assert plan["window_applies"] is False
        assert plan["can_reverse"] is True


# ══════════════════════════════════════════════════════════════════════════
# 3 · CLAUSE TWO — APPROVAL WHEN AN ISSUED BILL RE-OPENS
# ══════════════════════════════════════════════════════════════════════════


def test_a_payment_applied_to_an_issued_bill_needs_an_approval(brazos, dana):
    """BR-PAY-011: *"paid/cross-period requires Admin/Executive approval"*.

    The refusal NAMES the trigger, so a clerk is told what to go and get rather
    than that something is wrong.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        pe1_bills(brazos, account)
        recorded = a_payment(dana, account, amount=Decimal("292.87"))
        payment = models.Payment.objects.get(pk=recorded.payment_id)

        with pytest.raises(PaymentRuleError) as refusal:
            reversal.reverse_payment(
                dana,
                payment_id=payment.pk,
                returned_on=CORRECTED_ON,
                reason=models.REVERSAL_REASON_DATA_ENTRY_ERROR,
                idempotency_reference=uuid.uuid4(),
            )
        assert reversal_rules.APPROVAL_BILL_ISSUED in str(refusal.value)
        # NOTHING was written — the refusal is before the transaction.
        assert models.Payment.objects.filter(reverses_payment_id=payment.pk).count() == 0


def test_the_same_reversal_goes_through_once_an_approval_is_given(brazos, dana):
    """BR-PAY-037's v1 posture — the approver may be the same person, recorded.

    Inventing a stricter separation here would be this module overturning a
    signed rule; what it does instead is make the second act deliberate.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        pe1_bills(brazos, account)
        recorded = a_payment(dana, account, amount=Decimal("292.87"))
        payment = models.Payment.objects.get(pk=recorded.payment_id)

        result = reversal.reverse_payment(
            dana,
            payment_id=payment.pk,
            returned_on=CORRECTED_ON,
            reason=models.REVERSAL_REASON_DATA_ENTRY_ERROR,
            approval="approved by D. Whitfield — cheque was recorded on the wrong account",
            idempotency_reference=uuid.uuid4(),
        )
        assert result.created is True
        assert result.amount == Decimal("-292.87")


def test_a_bounce_on_the_same_paid_bill_needs_no_approval(brazos, dana):
    """The boundary again, in the case that matters most.

    A bounced cheque against an issued bill is the ORDINARY case — J12's whole
    chain — and requiring an approval for it would have broken a signed path to
    add a control nobody asked for on it.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        pe1_bills(brazos, account)
        recorded = a_payment(dana, account, amount=Decimal("292.87"))
        payment = models.Payment.objects.get(pk=recorded.payment_id)

        result = reversal.reverse_payment(
            dana,
            payment_id=payment.pk,
            returned_on=CORRECTED_ON,
            reason=models.REVERSAL_REASON_NSF,
            idempotency_reference=uuid.uuid4(),
        )
        assert result.created is True
        plan = reversal_rules.reversal_plan(
            payment, reason=models.REVERSAL_REASON_NSF, on=CORRECTED_ON.date()
        )
        assert plan["approval"]["required"] is False


def test_an_unpaid_payment_needs_no_approval_at_all(brazos, dana):
    """A payment sitting entirely as credit re-opens no bill, so nobody signs."""
    with tenant_ctx(brazos):
        _account, payment = _paid(brazos, dana)
        plan = reversal_rules.reversal_plan(
            payment, reason=models.REVERSAL_REASON_DATA_ENTRY_ERROR, on=CORRECTED_ON.date()
        )
        assert plan["approval"]["required"] is False
        assert plan["consequences"]["bills_reopening"] == []


# ══════════════════════════════════════════════════════════════════════════
# 4 · CLAUSE THREE — THE CONSEQUENCE MESSAGE, COMPOSED BY THE SERVER
# ══════════════════════════════════════════════════════════════════════════


def test_the_plan_lists_every_bill_that_reopens_and_by_how_much(brazos, dana):
    """CS-31: *"listing every bill that re-opens and by how much"*.

    ⚠ **B14 rule 31 — BY NUMBER.** `invoice_id` is a uuid and is not in this
    payload at all, so no screen can print one even by accident.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        pe1_bills(brazos, account)
        recorded = a_payment(dana, account, amount=Decimal("292.87"))
        payment = models.Payment.objects.get(pk=recorded.payment_id)

        plan = reversal_rules.reversal_plan(
            payment, reason=models.REVERSAL_REASON_DATA_ENTRY_ERROR, on=CORRECTED_ON.date()
        )
        rows = plan["consequences"]["bills_reopening"]
        assert rows, "a payment that met a bill must list it"
        assert Decimal(plan["consequences"]["bills_reopening_total"]) == Decimal("292.87")
        for row in rows:
            assert set(row) == {"bill_no", "amount", "currency"}
            assert "id" not in row


def test_the_plan_says_when_the_credit_goes_below_zero(brazos, dana):
    """PO ruling 2026-08-11, `OQ-132`: *"Yes, it's a real debt"* — said BEFORE.

    The PO's own chain, unchanged: pay **350.00** against **292.87** open, which
    leaves **57.13** of credit; refund that 57.13 by cheque, which takes the
    credit to **0.00**; and now reversing the payment takes back a credit that
    is no longer there, so the account goes to **−57.13**.

    CS-31 wants that figure on the screen BEFORE the clerk confirms rather than
    discovered on the account afterwards, and this asserts the preview says it.
    """
    from apps.payments import refunds

    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        pe1_bills(brazos, account)
        recorded = a_payment(dana, account, amount=PE4_PAYMENT)
        payment = models.Payment.objects.get(pk=recorded.payment_id)
        assert selectors.account_credit_position(account.pk) == PE4_CREDIT  # 57.13

        requested = refunds.request_refund(
            dana,
            payment_id=payment.pk,
            amount=PE4_CREDIT,
            method=models.REFUND_METHOD_CHECK,
            reference="10241",  # PE-9's cheque number
            requested_at=datetime(2026, 7, 19, 9, 0, tzinfo=UTC),
        )
        refunds.approve_refund(
            dana,
            refund_id=requested.refund_id,
            approved_at=datetime(2026, 7, 19, 9, 30, tzinfo=UTC),
        )
        refunds.issue_refund(
            dana,
            refund_id=requested.refund_id,
            issued_at=datetime(2026, 7, 19, 10, 0, tzinfo=UTC),
        )
        assert selectors.account_credit_position(account.pk) == Decimal("0.00")

        plan = reversal_rules.reversal_plan(
            payment, reason=models.REVERSAL_REASON_DATA_ENTRY_ERROR, on=CORRECTED_ON.date()
        )
        assert Decimal(plan["consequences"]["credit_taken_back"]) == PE4_CREDIT
        assert Decimal(plan["consequences"]["credit_after"]) == -PE4_CREDIT
        assert plan["consequences"]["credit_goes_negative"] is True


def test_the_plan_names_the_approval_queue_it_does_not_have(brazos, dana):
    """Hard-won law 1 — the gap is REPORTED rather than implied by silence.

    CS-31's own Data line reads *"None"*, and a reversal that waits for somebody
    needs a table. So the requirement is built and the waiting list is not, and
    every plan says which is which.
    """
    with tenant_ctx(brazos):
        _account, payment = _paid(brazos, dana)
        plan = reversal_rules.reversal_plan(
            payment, reason=models.REVERSAL_REASON_DATA_ENTRY_ERROR, on=CORRECTED_ON.date()
        )
        codes = {problem["code"] for problem in plan["problems"]}
        assert "no_durable_approval_queue" in codes
        assert "staff_reversal_role_unchanged_br_pay_1070" in codes
        assert "staff_reversal_charges_no_returned_item_fee" in codes
