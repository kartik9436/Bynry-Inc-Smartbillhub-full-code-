# ── Trace ──────────────────────────────────────────────
# Story:    US-PAY-006 (allocation — the open bills a payment meets) ·
#           US-PAY-013 (S34 outstandings) · US-PAY-014 (the collection ladder)
#           Screens: S22 · S34 · S21
# Defect:   DEF-2416 (high) — DEF-062's "Level is due" ruling never crossed into
#           payments. `billing_seam` measured every bill at `invoices.total`, so
#           a budget-billing customer who paid exactly the level they were asked
#           for was left owing the variance, aged, and entered the ladder.
# Rules:    BR-BIL-072 (**"Level is due"** — PO 2026-08-11, closing OQ-140 and
#           DEF-062) · BR-BIL-030 (the level is read from the bill's own FROZEN
#           payload, never from today's budget status) · BR-BIL-004 (an issued
#           bill is immutable, so its total is a fact) · BR-PAY-010
#           (oldest-invoice-first; overpayment → account credit) · BR-PAY-029 /
#           BR-PAY-032 (S34 outstandings and the days-late anchor) ·
#           CLAUDE.md rule 1 · rule 2 · rule 7
# Tests:    this file
# Impacts:  apps/payments/billing_seam.py (both reads) · apps/payments/
#           open_bills.py · apps/payments/outstandings.py · apps/payments/
#           ladder.py · apps/billing/selectors.amount_due_for (the owner)
# ───────────────────────────────────────────────────────
"""**A budget customer who pays what they were asked for owes nothing.**

THE FIGURES, AND THEY ARE THE ❄️ FROZEN ONES. WE-8's July bill: trailing-12
actuals give a level of **$242**, the month's actual is **$292.87**, and the
variance of **−50.87** is budget billing working exactly as designed. The PO
ruled on 2026-08-11, verbatim *"Level is due"* — so that bill ASKS FOR $242.00
and paying $242.00 settles the month in full.

Payments measured it at `invoice.total` and reported **50.87** still open. Every
consequence of that is a customer-facing harm and none of them is subtle:

  * `GET /accounts/{id}/open-bills` showed the bill still open, so the S22
    picker offered a clerk 50.87 to aim at on a bill nobody owed;
  * `outstanding_positions` added 50.87 to the account's balance, so S34 listed
    a debtor who was not one;
  * `run_ladder` reads that balance, so the reminder and the disconnect notices
    went to a customer who had paid on time, every month, for ever.

That is `DEF-062`'s own harm one module along. Billing closed it in August with
`selectors.amount_due_for`; payments called neither that function nor anything
like it, and both modules stayed internally consistent and green.

**NOTHING HERE IS A NEW RULE OR A NEW FIGURE.** BR-BIL-072 is signed, the level
is read off the bill's frozen payload by billing's own published function, and
this file only asserts that payments asks it. The ❄️ B4/B5 figures are untouched:
292.87 is still what the bill totals, 242.00 is still what it asks for, and both
come from WE-8 unchanged.

⚠ **WHY THERE WAS NO TEST BEFORE.** The lane that found DEF-2416 deliberately
wrote none, and its reasoning was right: a test written the same hour would have
pinned **50.87** as the expected open balance and made the defect permanent. So
the case is written HERE, with the fix, which is the only order in which it can
assert the true number.

⚠ **THE RED EVIDENCE, QUOTED (hard-won law 7).** Every case below was run first
against the pre-fix seam — `balance = invoice.total − Σ allocations` — and all
six failed, five of them on the FIGURE rather than on a missing attribute:

    6 failed, 1 passed, 4 warnings in 152.64s

    E   AssertionError: BR-BIL-072 'Level is due' — the July budget bill asks
        for 242.00, not its 292.87 total
    E   AssertionError: a customer who paid the 242.00 they were asked for
        still has an open bill
    E   AssertionError: assert Decimal('50.870000') != Decimal('50.87')
    E   AssertionError: assert Decimal('92.870000') == Decimal('42.00')
    E   AssertionError: assert Decimal('337.870000') == (Decimal('242.00')
                                                        + Decimal('45.00'))
    E   AttributeError: 'OpenInvoice' object has no attribute 'amount_due'

The one that PASSED red is
`test_def2416__a_budget_bill_drafted_before_the_ruling_falls_back_to_its_total`,
and that is the point of including it: it is the case the fix must NOT change,
so a green-before and green-after is the assertion.

⚠ **THE BALANCE-FORWARD PAIR WAS PROVED RED SEPARATELY**, by putting the old
subtraction (`allocated += total - balance`) back into
`apps/billing/payments_seam.py` and running just those two:

    1 failed, 1 passed, 7 deselected, 4 warnings in 293.38s

    E   AssertionError: the previous balance is what the earlier bill ASKED for
        (242.00), not the 292.87 it totalled
    FAILED test_def2416__the_balance_forward_section_names_no_payment_nobody_made

and the ORDINARY-bill case passed on the sabotaged engine, which is what makes
the pair a check rather than one assertion: the fix had to move the budget
figure and leave ❄️ WE-1's alone, and only running both on the old code shows it
did.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest

from apps.payments import billing_seam, services

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_pay_001_record_payment import (
    CLEARED_AT,
    POSTED_AT,
    an_issued_bill,
)
from tests.test_w3_billing_models import an_account

pytestmark = pytest.mark.django_db

# ── ❄️ WE-8, verbatim (04-docs/05-modules/07-billing/08-worked-examples.md) ──
# "Trailing-12 actuals $2,904 → level **$242**. July actual 292.87 → variance
#  −50.87". BR-BIL-072: the bill ASKS for the level.
WE8_TOTAL = Decimal("292.87")
WE8_LEVEL = Decimal("242.00")
WE8_VARIANCE = Decimal("50.87")  # 292.87 − 242.00, the figure that was chased

#: What an ordinary (non-budget) bill of the same account asks for — PE-1's
#: older bill, so the regression case uses a figure this suite already trusts.
PLAIN_TOTAL = Decimal("45.00")

JULY = date(2026, 7, 1)


def a_budget_bill(tenant, account, *, number="BL-2607-018330", level=WE8_LEVEL, total=WE8_TOTAL):
    """WE-8's July bill, with the budget block stage 6 stamps onto a real draft.

    The block's shape is `apps/billing/stages`' own and is asserted verbatim by
    `tests/test_us_bil_019_budget_bill.py::test_us_bil_019_tc1c` against a bill
    the REAL pipeline produced — `level`, `actual`, `variance_movement`,
    `variance_balance`, `amount_due`. It is copied rather than imported because
    what this file tests is what PAYMENTS does with a bill that carries one, and
    dragging the rating engine into a payments test is what
    `an_issued_bill` exists to avoid.
    """
    variance = (Decimal(str(level)) - Decimal(str(total))).quantize(Decimal("0.01"))
    return an_issued_bill(
        tenant,
        account,
        number=number,
        total=total,
        issued_on=JULY,
        bill_payload={
            "budget": {
                "level": str(level),
                "actual": str(total),
                "variance_movement": str(variance),
                "variance_balance": str(variance),
                # BR-BIL-072 — the ruled answer, frozen onto the bill at issue
                # (BR-BIL-030) so a re-level in January cannot rewrite what a
                # July bill asked for.
                "amount_due": str(level),
            }
        },
    )


def pay(actor, account, amount):
    """One cleared payment through the real service — no ORM shortcuts."""
    return services.record_payment(
        actor,
        account_id=account.pk,
        amount=amount,
        posted_at=POSTED_AT,
        cleared_at=CLEARED_AT,
        confirmation="8842",
        idempotency_reference=uuid.uuid4(),
    )


def open_numbers(account):
    return sorted(
        invoice.number for invoice in billing_seam.open_invoices_for_account(account.pk).invoices
    )


def balance_of(account):
    """What `outstanding_positions` says this account owes — the figure S34
    lists and `run_ladder` chases on."""
    positions, _ = billing_seam.outstanding_positions(account_ids=[account.pk])
    for position in positions:
        if str(position.account_id) == str(account.pk):
            return position.balance
    return Decimal("0")


# ══════════════════════════════════════════════════════════════════════════
# THE READ — what the bill ASKS for
# ══════════════════════════════════════════════════════════════════════════
def test_def2416__a_budget_bill_is_open_at_its_level_and_not_at_its_total(brazos, dana):
    """**BR-BIL-072, at the seam.** 292.87 is the bill; 242.00 is the ask.

    The ISSUED total is still served beside it and is still 292.87 — BR-BIL-004
    makes it immutable and the S21 Bills tab shows it. What changed is the
    figure a payment is measured against, which is the one the PO ruled.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="ACC-1042")
        a_budget_bill(brazos, account)

        position = billing_seam.open_invoices_for_account(account.pk)
        assert len(position.invoices) == 1
        bill = position.invoices[0]

        assert bill.balance == WE8_LEVEL, (
            "BR-BIL-072 'Level is due' — the July budget bill asks for 242.00, "
            "not its 292.87 total"
        )
        assert bill.amount_due == WE8_LEVEL
        # BR-BIL-004 — the issued total is a fact and is unchanged by any of this.
        assert bill.total == WE8_TOTAL
        assert bill.allocated == Decimal("0")


# ══════════════════════════════════════════════════════════════════════════
# THE PROOF — the customer pays what they were asked for
# ══════════════════════════════════════════════════════════════════════════
def test_def2416_the_proof__paying_the_level_settles_the_month(brazos, dana):
    """**242.00 in, nothing owed.** DEF-2416's own sentence, run.

    Through `record_payment` exactly as the S22 counter form sends it — the
    point being that the ORDINARY path is what got this wrong.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="ACC-1042")
        a_budget_bill(brazos, account)

        result = pay(dana, account, WE8_LEVEL)
        assert result.created is True

        assert (
            open_numbers(account) == []
        ), "a customer who paid the 242.00 they were asked for still has an open bill"
        assert balance_of(account) == Decimal(
            "0"
        ), "the ladder sees a balance for a customer who paid their level in full"


def test_def2416__the_variance_is_not_added_to_what_the_customer_owes(brazos, dana):
    """The 50.87 that used to be chased is not owed by anybody.

    Budget billing IS the variance: the customer consumes 292.87 and is asked
    for 242.00 on purpose, and the difference is settled through the settle-up
    (WE-8), not by leaving it open on a bill the utility already told them was
    242.00.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="ACC-1043")
        a_budget_bill(brazos, account)
        pay(dana, account, WE8_LEVEL)

        assert balance_of(account) != WE8_VARIANCE


def test_def2416__a_budget_customer_who_pays_short_still_owes_the_rest(brazos, dana):
    """Paying 200.00 against a 242.00 ask leaves **42.00** — not 92.87.

    The fix is not "budget bills are settled"; it is that they are measured at
    what was asked. A short payment still leaves a real, chaseable balance and
    the ladder still runs.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="ACC-1044")
        a_budget_bill(brazos, account)
        pay(dana, account, Decimal("200.00"))

        position = billing_seam.open_invoices_for_account(account.pk)
        assert len(position.invoices) == 1
        assert position.invoices[0].balance == Decimal("42.00")
        assert balance_of(account) == Decimal("42.00")


# ══════════════════════════════════════════════════════════════════════════
# THE REGRESSION GUARD — every other bill is untouched
# ══════════════════════════════════════════════════════════════════════════
def test_def2416__an_ordinary_bill_is_still_measured_at_its_total(brazos, dana):
    """A bill with no budget block asks for its total, exactly as it always did.

    `amount_due_for` returns `invoice.total` for such a bill by its own
    contract, so this is the case that proves the change is scoped to the bills
    the ruling is about.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="ACC-1045")
        an_issued_bill(brazos, account, number="BL-2607-018311", total=PLAIN_TOTAL, issued_on=JULY)

        position = billing_seam.open_invoices_for_account(account.pk)
        assert len(position.invoices) == 1
        assert position.invoices[0].balance == PLAIN_TOTAL
        assert position.invoices[0].amount_due == PLAIN_TOTAL
        assert balance_of(account) == PLAIN_TOTAL


def test_def2416__a_budget_bill_drafted_before_the_ruling_falls_back_to_its_total(brazos, dana):
    """No block, no level — and it is the bill's total, stated rather than guessed.

    `amount_due_for`'s own contract: *"A budget bill drafted before this lane
    shipped has no block and falls back to its total."* Payments must not invent
    a level for it, and this case is what stops a future edit from doing so.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="ACC-1046")
        an_issued_bill(
            brazos,
            account,
            number="BL-2607-018331",
            total=WE8_TOTAL,
            issued_on=JULY,
            bill_payload={"lines": []},
        )

        position = billing_seam.open_invoices_for_account(account.pk)
        assert position.invoices[0].balance == WE8_TOTAL
        assert balance_of(account) == WE8_TOTAL


# ══════════════════════════════════════════════════════════════════════════
# THE TWO READS AGREE — which is the whole shape of this defect
# ══════════════════════════════════════════════════════════════════════════
def test_def2416__the_bill_read_and_the_outstandings_read_answer_the_same(brazos, dana):
    """One question, two seam functions, one answer.

    DEF-2416's escape_reason is *"no gate compares two modules' answers to the
    same question"*. This is the cheap version of that gate for the two reads
    that are inside ONE module and were both wrong: whatever
    `open_invoices_for_account` says a bill owes, `outstanding_positions` sums.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="ACC-1047")
        a_budget_bill(brazos, account)
        an_issued_bill(brazos, account, number="BL-2607-018311", total=PLAIN_TOTAL, issued_on=JULY)

        position = billing_seam.open_invoices_for_account(account.pk)
        summed = sum((invoice.balance for invoice in position.invoices), Decimal("0"))

        assert summed == WE8_LEVEL + PLAIN_TOTAL == Decimal("287.00")
        assert balance_of(account) == summed


# ══════════════════════════════════════════════════════════════════════════
# THE NEXT BILL'S BALANCE-FORWARD SECTION — the surface the fix could have
# broken, and did not
# ══════════════════════════════════════════════════════════════════════════
def test_def2416__the_balance_forward_section_names_no_payment_nobody_made(brazos, dana):
    """**Three lines that foot AND are all true** (BR-BIL-035 · BR-BIL-072).

    `apps/billing/payments_seam.prior_position_for_account` builds the previous
    balance / payments & credits / open balance block that the NEXT bill prints,
    and it used to derive the middle line by subtraction — `total − balance`.
    That was exact for as long as every bill's ask was its total.

    The moment payments started measuring a budget bill at its LEVEL, the same
    subtraction would have printed **"Previous balance 292.87 · Payments &
    credits 50.87 · Open balance 242.00"** on the bill of a customer who had
    paid NOTHING: three lines that add up, one of them a claim about a payment
    that does not exist.

    So both operands come from the seam's own carried facts and the block foots
    by construction. Nothing was paid here, so the middle line is 0.00.
    """
    from apps.billing import customers_seam, payments_seam

    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="ACC-1048")
        bill = a_budget_bill(brazos, account)

        position = payments_seam.prior_position_for_account(
            account.pk,
            totals_by_invoice_id={str(bill.pk): bill.total},
            opening=customers_seam.opening_position_for_account(account.pk),
        )
        assert position.previous_balance == WE8_LEVEL, (
            "the previous balance is what the earlier bill ASKED for (242.00), not the "
            "292.87 it totalled"
        )
        assert position.payments_credits == Decimal("0"), (
            "nobody paid anything, so 'Payments & credits' must be 0.00 — the old "
            "subtraction would have printed the 50.87 variance here"
        )
        assert position.open_balance == WE8_LEVEL
        # BR-BIL-035 — the guarantee the whole block exists for.
        assert position.previous_balance - position.payments_credits == position.open_balance


def test_def2416__an_ordinary_prior_bill_foots_exactly_as_it_always_did(brazos, dana):
    """❄️ WE-1, unmoved: one unpaid 45.00 prior bill gives `45.00 − 0.00`.

    `amount_due` equals `total` for every bill that is not budget-billing, so
    the frozen figure this block was built on is byte-identical.
    """
    from apps.billing import customers_seam, payments_seam

    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="ACC-1049")
        bill = an_issued_bill(
            brazos, account, number="BL-2607-018311", total=PLAIN_TOTAL, issued_on=JULY
        )

        position = payments_seam.prior_position_for_account(
            account.pk,
            totals_by_invoice_id={str(bill.pk): bill.total},
            opening=customers_seam.opening_position_for_account(account.pk),
        )
        assert position.previous_balance == PLAIN_TOTAL
        assert position.payments_credits == Decimal("0")
        assert position.open_balance == PLAIN_TOTAL
