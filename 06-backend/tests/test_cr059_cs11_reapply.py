# ── Trace ──────────────────────────────────────────────
# Change:   CR-059 · CS-11 (task 37) — "Reapply a payment to a different bill".
#           §0d.1 records that **reapply exists at NO layer — the only trace in
#           the module is a comment.**
# Story:    US-PAY-006   Screens: S33 · S35
# Rules:    BR-PAY-031 (CONFIRMED — *"reapply = reversing allocation rows + new
#           rows"*) · BR-PAY-010 · CLAUDE.md hard rule 4 (a correction is NEW
#           ROWS) · rule 5 (only the ledger writes journal lines — and this
#           writes NONE) · rule 7 (audit)
# Tests:    this file
# ───────────────────────────────────────────────────────
"""CS-11 — move a payment from the bill it met to the bill it should have met.

WHY IT MATTERS TO A CUSTOMER AND NOT ONLY TO A CLERK
====================================================
The only correction available before this was to reverse the whole payment and
record it again. That leaves a `payments` row with status `reversed` on the
customer's history — **a payment that bounced when it did not** — and if the
tender was a cheque an NSF count and a cash-only flag can follow from it. A
reapply leaves the payment exactly as it stands: same number, same amount, same
dates, same receipt.

⚠ THE ONE RULE THAT IS EASY TO GET WRONG, AND ITS FIGURE
========================================================
**A reapply posts NOTHING to the ledger.** CS-11 says so and says why it says
so: *"Saying so here is what stops the next lane adding a posting call because
every other write path has one."*

Worked: a customer pays **292.87** and the clerk meets bill `BL-0141` with it;
it should have met `BL-0155`. Cash in the books stays **292.87** and receivables
relieved stays **292.87**. Had this path posted the way `record_payment` does,
the books would carry **585.74** of cash the utility never took — every time
anybody fixed a typo.

`test_cs11__nothing_reaches_the_ledger` is that assertion, counted over the
tenant's real journal lines before and after.

THE RED PROOF, RUN BEFORE ANY OF THIS WAS TRUSTED GREEN (hard-won law 7)
========================================================================
  * With `_validated_targets`' `total > available` check removed,
    `test_cs11__it_cannot_put_on_more_than_it_took_off` fails with
    `DID NOT RAISE` and the account is credited money nobody paid.
  * With `_net_by_invoice` reading only positive rows,
    `test_cs11__a_second_reapply_reads_the_current_position` fails — the money
    is taken off a bill it is no longer on, twice.
  * With `_validated_targets`' `amount > headroom` check removed,
    `test_cs11__a_bill_cannot_be_overpaid` fails and a bill goes into credit on
    a document hard rule 4 freezes forever.
"""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from apps.payments import billing_seam, models, reapply, services
from apps.payments.exceptions import PaymentRuleError

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_pay_001_record_payment import an_issued_bill
from tests.test_w3_billing_models import an_account

pytestmark = pytest.mark.django_db

THE_PAYMENT = Decimal("292.87")
PAID_AT = datetime(2026, 7, 5, 10, 0, tzinfo=UTC)
NOTICED_ON = date(2026, 8, 2)


def two_bills_and_a_payment(actor, tenant, account):
    """Two open bills, and a payment the allocator put on the OLDER one.

    `oldest_first` is the shipped default, so `BL-0141` (1 June) takes the money
    and `BL-0155` (1 July) is left open — which is the clerk's mistake, made by
    the product exactly as it is supposed to.
    """
    older = an_issued_bill(
        tenant, account, number="BL-0141", total=THE_PAYMENT, issued_on=date(2026, 6, 1)
    )
    newer = an_issued_bill(
        tenant, account, number="BL-0155", total=THE_PAYMENT, issued_on=date(2026, 7, 1)
    )
    paid = services.record_payment(
        actor,
        account_id=account.pk,
        amount=THE_PAYMENT,
        posted_at=PAID_AT,
        cleared_at=PAID_AT,
        method_code="cash",
        idempotency_reference=uuid.uuid4(),
    )
    return older, newer, paid


def journal_line_count(tenant):
    from apps.ledger import models as ledger_models

    return ledger_models.JournalLine.objects.filter(tenant=tenant).count()


# ══ THE MECHANISM BR-PAY-031 HAS DESCRIBED SINCE THE SCHEMA SHIPPED ════════


def test_cs11__the_money_moves_to_the_other_bill(brazos, dana):
    """Reversing allocation rows plus new ones, in one transaction.

    The bill it left re-opens at **292.87** and the bill it met falls to **0**,
    and both figures come from `billing_seam.allocated_so_far`, which sums NET —
    so the negative mirror row is what re-opens the first bill and nothing was
    edited or deleted.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        older, newer, paid = two_bills_and_a_payment(dana, brazos, account)

        assert billing_seam.allocated_so_far(older.pk) == THE_PAYMENT, "it met the older bill"
        assert billing_seam.allocated_so_far(newer.pk) == Decimal("0")

        moved = reapply.reapply_payment(
            dana,
            payment_id=paid.payment_id,
            targets=({"invoice_id": str(newer.pk), "amount": THE_PAYMENT},),
            reason="the customer named the July bill",
            on_date=NOTICED_ON,
        )

        assert moved.released_total == THE_PAYMENT
        assert moved.applied_total == THE_PAYMENT
        assert moved.credit_carried == Decimal("0")
        assert billing_seam.allocated_so_far(older.pk) == Decimal("0"), "BL-0141 re-opened"
        assert billing_seam.allocated_so_far(newer.pk) == THE_PAYMENT, "BL-0155 is met"

        # BR-PAY-031's own words — nothing was edited and nothing removed.
        rows = list(models.Allocation.objects.filter(payment_id=paid.payment_id))
        assert len(rows) == 3, "the original row, its negative mirror, and the new one"
        assert sorted(row.amount for row in rows) == [
            -THE_PAYMENT,
            THE_PAYMENT,
            THE_PAYMENT,
        ]


def test_cs11__nothing_reaches_the_ledger(brazos, dana):
    """⚠ **THE RULE THIS WHOLE SPEC IS WRITTEN AROUND.**

    *"The cash total has not changed — only which bill it met — so a reapply
    that posted would DOUBLE-COUNT the money."* Counted over the tenant's real
    journal lines, not asserted from a flag.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        _older, newer, paid = two_bills_and_a_payment(dana, brazos, account)
        before = journal_line_count(brazos)

        result = reapply.reapply_payment(
            dana,
            payment_id=paid.payment_id,
            targets=({"invoice_id": str(newer.pk), "amount": THE_PAYMENT},),
            reason="typo",
            on_date=NOTICED_ON,
        )

        assert journal_line_count(brazos) == before, (
            "a reapply posts NO journal entry. Posting here would put 585.74 of cash in the "
            "books for a 292.87 payment, every time anybody fixed a typo"
        )
        assert any(
            problem["code"] == "nothing_posted_to_the_ledger" for problem in result.problems
        ), "and it is stated on the wire, because every other write path in the module posts"


def test_cs11__the_payment_row_is_untouched(brazos, dana):
    """The customer's history gains no `reversed` row — the point of CS-11.

    Reverse-and-record was the only correction before this, and it stamps
    `reversed` on a payment that never bounced.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        _older, newer, paid = two_bills_and_a_payment(dana, brazos, account)
        before = models.Payment.objects.get(pk=paid.payment_id)
        was = (before.status, before.amount, before.posted_at, before.payment_no)

        reapply.reapply_payment(
            dana,
            payment_id=paid.payment_id,
            targets=({"invoice_id": str(newer.pk), "amount": THE_PAYMENT},),
            reason="typo",
            on_date=NOTICED_ON,
        )
        after = models.Payment.objects.get(pk=paid.payment_id)
        assert (after.status, after.amount, after.posted_at, after.payment_no) == was
        assert models.Payment.objects.filter(reverses_payment_id=paid.payment_id).count() == 0, (
            "no reversing row exists — this is not a reversal and a customer's history "
            "must not say it was"
        )


def test_cs11__it_can_split_across_two_bills(brazos, dana):
    """The clerk names the bills, so a 292.87 can meet two of them.

    `targets` is EXPLICIT and this path accepts no allocation ORDER: a reapply
    exists because the automatic order was wrong, so re-running it would undo
    the correction.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        older, newer, paid = two_bills_and_a_payment(dana, brazos, account)

        moved = reapply.reapply_payment(
            dana,
            payment_id=paid.payment_id,
            targets=(
                {"invoice_id": str(older.pk), "amount": Decimal("100.00")},
                {"invoice_id": str(newer.pk), "amount": Decimal("192.87")},
            ),
            reason="the customer split it",
            on_date=NOTICED_ON,
        )
        assert moved.applied_total == THE_PAYMENT
        assert billing_seam.allocated_so_far(older.pk) == Decimal("100.00")
        assert billing_seam.allocated_so_far(newer.pk) == Decimal("192.87")


def test_cs11__what_no_bill_takes_stays_as_credit(brazos, dana):
    """Leaving part of it as account credit is a lawful outcome, and it is stated.

    The remainder is not lost and it is not forced on to a bill: BR-PAY-010's
    carried credit is drawn down by the next issue.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        _older, newer, paid = two_bills_and_a_payment(dana, brazos, account)

        moved = reapply.reapply_payment(
            dana,
            payment_id=paid.payment_id,
            targets=({"invoice_id": str(newer.pk), "amount": Decimal("200.00")},),
            reason="only 200 of it belongs there",
            on_date=NOTICED_ON,
        )
        assert moved.applied_total == Decimal("200.00")
        assert moved.credit_carried == Decimal("92.87")

        from apps.payments import selectors

        assert selectors.account_credit_position(account.pk) == Decimal("92.87")


# ══ WHAT IT REFUSES, AND WHY EACH REFUSAL IS MONEY ═════════════════════════


def test_cs11__it_cannot_put_on_more_than_it_took_off(brazos, dana):
    """The sums must foot, or the reapply invents money.

    **RED PROOF:** with the `total > available` check removed this fails with
    `DID NOT RAISE` and 292.87 of payment settles 400.00 of bills.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        older, newer, paid = two_bills_and_a_payment(dana, brazos, account)

        with pytest.raises(PaymentRuleError) as refusal:
            reapply.reapply_payment(
                dana,
                payment_id=paid.payment_id,
                targets=(
                    {"invoice_id": str(older.pk), "amount": THE_PAYMENT},
                    {"invoice_id": str(newer.pk), "amount": THE_PAYMENT},
                ),
                reason="too much",
                on_date=NOTICED_ON,
            )
        assert "money the customer never paid" in str(refusal.value)
        assert billing_seam.allocated_so_far(older.pk) == THE_PAYMENT, "nothing moved"


def test_cs11__a_bill_cannot_be_overpaid(brazos, dana):
    """Money a bill cannot absorb belongs in the credit balance, not on the bill.

    A document in credit is a document hard rule 4 freezes forever, so nobody
    can go back and fix it.

    **RED PROOF:** with the headroom check removed this fails with `DID NOT
    RAISE`.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        older, newer, paid = two_bills_and_a_payment(dana, brazos, account)
        # A smaller newer bill: 292.87 cannot all go on to 50.00 of debt.
        small = an_issued_bill(
            brazos, account, number="BL-0160", total=Decimal("50.00"), issued_on=date(2026, 7, 15)
        )

        with pytest.raises(PaymentRuleError) as refusal:
            reapply.reapply_payment(
                dana,
                payment_id=paid.payment_id,
                targets=({"invoice_id": str(small.pk), "amount": THE_PAYMENT},),
                reason="all of it on to the small bill",
                on_date=NOTICED_ON,
            )
        assert "can take 50" in str(refusal.value).replace("50.000000", "50")


def test_cs11__another_accounts_bill_is_refused(brazos, dana):
    """A reapply moves money BETWEEN one account's own bills.

    Money that belongs on another account's bill is a cross-account movement
    with its own writer (CS-32) and its own balanced entry; doing it here would
    relieve one account's receivable with another's cash and post nothing at all
    to say so.
    """
    from tests.test_us_pay_020_023_bank_rec import an_account_of

    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        _older, _newer, paid = two_bills_and_a_payment(dana, brazos, account)
        stranger = an_account_of(dana, brazos, service="electric")
        theirs = an_issued_bill(
            brazos,
            stranger,
            number="BL-0199",
            total=THE_PAYMENT,
            issued_on=date(2026, 7, 1),
        )

        with pytest.raises(PaymentRuleError) as refusal:
            reapply.reapply_payment(
                dana,
                payment_id=paid.payment_id,
                targets=({"invoice_id": str(theirs.pk), "amount": THE_PAYMENT},),
                reason="wrong account",
                on_date=NOTICED_ON,
            )
        assert "not an open bill of account" in str(refusal.value)


def test_cs11__a_reapply_needs_a_reason(brazos, dana):
    """Hard rule 7's row is where the answer lives months later."""
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        _older, newer, paid = two_bills_and_a_payment(dana, brazos, account)
        with pytest.raises(PaymentRuleError) as refusal:
            reapply.reapply_payment(
                dana,
                payment_id=paid.payment_id,
                targets=({"invoice_id": str(newer.pk), "amount": THE_PAYMENT},),
                reason="  ",
                on_date=NOTICED_ON,
            )
        assert "needs a reason" in str(refusal.value)


def test_cs11__a_processing_payment_has_met_nothing(brazos, dana):
    """The money has not arrived, so there is nothing to move (BR-PAY-021)."""
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        newer = an_issued_bill(
            brazos, account, number="BL-0155", total=THE_PAYMENT, issued_on=date(2026, 7, 1)
        )
        pending = services.record_payment(
            dana,
            account_id=account.pk,
            amount=THE_PAYMENT,
            posted_at=PAID_AT,
            cleared_at=None,
            method_code="check",
            confirmation="8842",
            idempotency_reference=uuid.uuid4(),
        )
        with pytest.raises(PaymentRuleError) as refusal:
            reapply.reapply_payment(
                dana,
                payment_id=pending.payment_id,
                targets=({"invoice_id": str(newer.pk), "amount": THE_PAYMENT},),
                reason="too early",
                on_date=NOTICED_ON,
            )
        assert "still processing" in str(refusal.value)


def test_cs11__a_second_reapply_reads_the_current_position(brazos, dana):
    """The net position is what a second correction works from — never the original rows.

    A payment already reapplied once has moved; taking the money off the bill it
    is NO LONGER on would take it off twice.

    **RED PROOF:** with `_net_by_invoice` reading only positive rows this fails,
    because the original bill still looks met.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        older, newer, paid = two_bills_and_a_payment(dana, brazos, account)

        reapply.reapply_payment(
            dana,
            payment_id=paid.payment_id,
            targets=({"invoice_id": str(newer.pk), "amount": THE_PAYMENT},),
            reason="first correction",
            on_date=NOTICED_ON,
        )
        plan = reapply.reapply_plan(payment_id=paid.payment_id)
        met = {row["invoice_id"] for row in plan["meets"]}
        assert met == {str(newer.pk)}, "it is on BL-0155 now and NOT on BL-0141"

        # And a second correction moves it back, working from that position.
        second = reapply.reapply_payment(
            dana,
            payment_id=paid.payment_id,
            targets=({"invoice_id": str(older.pk), "amount": THE_PAYMENT},),
            reason="and back again",
            on_date=NOTICED_ON,
        )
        assert second.released_total == THE_PAYMENT
        assert billing_seam.allocated_so_far(older.pk) == THE_PAYMENT
        assert billing_seam.allocated_so_far(newer.pk) == Decimal("0")


def test_cs11__the_plan_names_bills_by_number(brazos, dana):
    """B14 rule 31 — *"no database id is ever the visible value of a field."*"""
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        older, _newer, paid = two_bills_and_a_payment(dana, brazos, account)

        plan = reapply.reapply_plan(payment_id=paid.payment_id)
        assert plan["meets"][0]["invoice_number"] == "BL-0141"
        # The STORED decimal, at the column's own precision — CLAUDE.md rule 2.
        # Compared by VALUE and not by spelling: a screen renders the two-place
        # figure from its own display member, and pinning the string here would
        # make this test an assertion about formatting rather than about money.
        assert Decimal(plan["meets"][0]["amount"]) == THE_PAYMENT
        assert Decimal(plan["applied_total"]) == THE_PAYMENT
