# ── Trace ──────────────────────────────────────────────
# Change:   CR-044 §4 — "reading open balance", the one piece of work four
#           surfaces need. `DEF-1081` is the fourth of them.
#           Screens: S31 step 2 (the bill run's pre-flight) · S30 One-time bill ·
#           S30 Budget Bills · S30 Fix a bill
# Rules:    BR-BIL-035 (previous balance − payments received + this period =
#           total due — the arithmetic is signed; neither operand's WINDOW is,
#           which is OQ-217) · BR-BIL-160 (a migrated opening balance is part of
#           the previous balance, and so is what has been paid against it) ·
#           BR-PAY-041 (a negative credit position is a real DEBT) ·
#           BR-CUS-015 (`accounts.balance` is a CACHE and is not the truth) ·
#           B1 (no module computes another's half) · CLAUDE.md rule 1 (tenant
#           scoping) · rule 2 (money, never float)
# Golden:   ❄️ WE-1's 45.00 arrears half, asserted UNMOVED ·
#           ❄️ GT-16's four buckets (84.20 / 62.10 / 0.00 / 121.00 = 267.30)
# ───────────────────────────────────────────────────────
"""CR-044 §4 — what a customer already owes, askable ABOUT AN ACCOUNT.

════════════════════════════════════════════════════════════════════════════
WHY THIS IS A READER AND NOT A GATHER
════════════════════════════════════════════════════════════════════════════
`payments_seam.prior_position_for_account` already computes this and already
FOOTS by construction:

    previous_balance − payments_credits == open_balance

It asks three modules for three operands, each BY NAME, because B1 forbids one
module computing another's half: billing's own immutable `invoices.total`,
payments' `allocations`, and customers' migrated `account_opening_buckets`.

**And it has exactly ONE caller — `issue.py:1306` — which answers about an
INVOICE.** Its totals argument is built by `_prior_bill_totals(invoice)`, which
needs an invoice to exclude. Every surface that wants this figure has no invoice
to ask about:

  * the bill run's step 2 is a PRE-FLIGHT over 47 accounts, before any draft
    exists — `DEF-1081`, whose own copy says *"What each customer already owes
    … are not gathered by the run yet, so nothing here would be a figure we
    could stand behind"*;
  * the One-time bill preview prices nothing and writes nothing;
  * budget-billing eligibility is a question about an account, not a bill;
  * a correction's `the_customers_balance` section is about the customer.

So this module changes the QUESTION from *what did this invoice inherit* to
*what does this account owe*, and delegates the arithmetic unchanged. It
computes no money rule of its own and it writes nothing.

════════════════════════════════════════════════════════════════════════════
RED FIRST (hard-won law 7)
════════════════════════════════════════════════════════════════════════════
Every case below was run before `apps/billing/open_balance.py` existed and
failed on `ModuleNotFoundError: No module named 'apps.billing.open_balance'`.
The verbatim failure is in the CR-044 lane report.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from apps.billing import models
from apps.customers import models as customer_models

from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    dana,
    tenant_ctx,
)
from tests.test_us_bil_005_release_issue_api import (  # noqa: F401
    CURRENT_CHARGES,
    PRIOR_BILL_TOTAL,
    a_bill_of,
    an_actor_user,
)
from tests.test_w3_billing_models import a_run, an_account

pytestmark = pytest.mark.django_db

#: ❄️ B5 GT-16 line 55 — the four imported bands of `A-12103`, and their sum.
GT16_BUCKETS: tuple[tuple[str, Decimal], ...] = (
    (customer_models.AccountOpeningBucket.BUCKET_CURRENT, Decimal("84.20")),
    (customer_models.AccountOpeningBucket.BUCKET_31_60, Decimal("62.10")),
    (customer_models.AccountOpeningBucket.BUCKET_61_90, Decimal("0.00")),
    (customer_models.AccountOpeningBucket.BUCKET_90_PLUS, Decimal("121.00")),
)
GT16_OPENING = Decimal("267.30")
GT16_CUTOVER = date(2026, 8, 31)


def a_migrated_account(brazos, dana, *, account_no):
    """An account that ARRIVED owing money — ❄️ GT-16's own position."""
    account = an_account(dana, brazos, account_no=account_no)
    for bucket, amount in GT16_BUCKETS:
        customer_models.AccountOpeningBucket.objects.create(
            tenant=brazos,
            account=account,
            as_of=GT16_CUTOVER,
            bucket=bucket,
            amount=amount,
            currency="USD",
        )
    return account


def _foots(position) -> bool:
    """BR-BIL-035's arithmetic, read off the answer.

    Returned rather than asserted so each case can name itself in its message.
    """
    if position.previous_balance is None or position.payments_credits is None:
        return position.open_balance is None
    return position.previous_balance - position.payments_credits == position.open_balance


# ══════════════════════════════════════════════════════════════════════════
# tc1 — ❄️ WE-1's arrears half, asked about the ACCOUNT instead of the bill
# ══════════════════════════════════════════════════════════════════════════
def test_cr044_tc1__one_unpaid_prior_bill_is_the_open_balance(brazos, dana):
    """WE-1 is `45.00 − 0.00 + 247.87 = 292.87`, and `45.00 − 0.00` is this.

    The frozen example's arrears half must come back BYTE-IDENTICAL from the
    account-shaped question, because if it does not then the run's step 2 and
    the bill itself would show a customer two different numbers for the same
    debt — which is worse than step 2 showing nothing, the state DEF-1081
    records.
    """
    from apps.billing import open_balance

    with tenant_ctx(brazos):
        run = a_run(brazos, key="2026-06|cr044-tc1")
        account = an_account(dana, brazos, account_no="A-11024")
        a_bill_of(
            brazos,
            account,
            run,
            invoice_no="BL-2606-000301",
            total=PRIOR_BILL_TOTAL,
            status=models.INVOICE_ISSUED,
            issued_at=datetime(2026, 6, 3, tzinfo=UTC),
        )
        position = open_balance.open_balance_for_account(account.pk)

    assert position.previous_balance == PRIOR_BILL_TOTAL, "❄️ WE-1's 45.00"
    assert position.payments_credits == Decimal("0")
    assert position.open_balance == PRIOR_BILL_TOTAL
    assert position.bills == 1
    assert _foots(position), position


# ══════════════════════════════════════════════════════════════════════════
# tc2 — a MIGRATED account with no invoice at all still owes ❄️ GT-16's 267.30
# ══════════════════════════════════════════════════════════════════════════
def test_cr044_tc2__a_migrated_opening_balance_is_an_open_balance(brazos, dana):
    """BR-BIL-160 — the customer who arrived owing money.

    This is the case that makes the reader worth building rather than reusing
    payments' `outstanding_positions` directly: that read is over INVOICES, and
    this account has none. A step-2 preview built on invoices alone would tell a
    clerk that a customer who arrived $267.30 in arrears is square, on the
    screen where they decide to bill them.
    """
    from apps.billing import open_balance

    with tenant_ctx(brazos):
        account = a_migrated_account(brazos, dana, account_no="A-12103")
        position = open_balance.open_balance_for_account(account.pk)

    assert position.previous_balance == GT16_OPENING
    assert position.opening_balance == GT16_OPENING
    assert position.opening_buckets == 4
    assert position.payments_credits == Decimal("0")
    assert position.open_balance == GT16_OPENING
    assert _foots(position), position


# ══════════════════════════════════════════════════════════════════════════
# tc3 — a DRAFT is never in the set, and it is not excluded BY ID
# ══════════════════════════════════════════════════════════════════════════
def test_cr044_tc3__a_draft_bill_does_not_count_itself(brazos, dana):
    """The pre-flight case, and the reason the guarantee is structural.

    Step 2 runs while the drafts for this very cycle exist. If a draft counted
    toward what the customer *already* owes, every account in the run would be
    overstated by exactly the bill about to be sent, and the total on the
    screen would be double-counted rather than merely wrong.

    The set is the LOCKED statuses, so a draft cannot appear. That is stronger
    than an id filter and it cannot rot: it stays true when the caller forgets
    to pass an exclusion, which is the whole failure mode.
    """
    from apps.billing import open_balance

    with tenant_ctx(brazos):
        run = a_run(brazos, key="2026-06|cr044-tc3")
        account = an_account(dana, brazos, account_no="A-11025")
        a_bill_of(
            brazos,
            account,
            run,
            invoice_no="BL-2606-000302",
            total=PRIOR_BILL_TOTAL,
            status=models.INVOICE_ISSUED,
            issued_at=datetime(2026, 6, 3, tzinfo=UTC),
        )
        # This cycle's draft — the one step 2 is about to review.
        a_bill_of(brazos, account, run, invoice_no="BL-2607-000303", total=CURRENT_CHARGES)
        position = open_balance.open_balance_for_account(account.pk)

    assert position.previous_balance == PRIOR_BILL_TOTAL, (
        "the draft must not be in the previous balance — it is what the customer "
        "is about to be asked for, not what they already owe"
    )
    assert position.bills == 1
    assert _foots(position), position


# ══════════════════════════════════════════════════════════════════════════
# tc4 — the BATCH form: DEF-1081's own shape, 47 accounts before a run
# ══════════════════════════════════════════════════════════════════════════
def test_cr044_tc4__the_batch_form_agrees_with_the_single_form(brazos, dana):
    """DEF-1081 — step 2 reviews a cohort, not one customer.

    Two requirements, and the second is the one that makes the batch form worth
    having at all:

      1. it must agree with the single-account answer for every account, or the
         run's step 2 and the customer's own bill would disagree;
      2. an account with NOTHING open must still be answerable — as a zero
         position, not as a missing key. A caller that has to guess whether a
         missing account means "owes nothing" or "was not asked" will guess, and
         `None` and `0.00` are the two things this module exists to keep apart.
    """
    from apps.billing import open_balance

    with tenant_ctx(brazos):
        run = a_run(brazos, key="2026-06|cr044-tc4")
        owing = an_account(dana, brazos, account_no="A-11026")
        a_bill_of(
            brazos,
            owing,
            run,
            invoice_no="BL-2606-000304",
            total=PRIOR_BILL_TOTAL,
            status=models.INVOICE_ISSUED,
            issued_at=datetime(2026, 6, 3, tzinfo=UTC),
        )
        migrated = a_migrated_account(brazos, dana, account_no="A-12104")
        square = an_account(dana, brazos, account_no="A-11027")

        ids = [owing.pk, migrated.pk, square.pk]
        answers = open_balance.open_balances_for_accounts(ids)
        singles = {str(a): open_balance.open_balance_for_account(a) for a in ids}

    assert set(answers) == {str(a) for a in ids}, "every account asked about is answered about"
    for key, single in singles.items():
        assert answers[key].open_balance == single.open_balance, key
        assert answers[key].previous_balance == single.previous_balance, key

    assert answers[str(owing.pk)].open_balance == PRIOR_BILL_TOTAL
    assert answers[str(migrated.pk)].open_balance == GT16_OPENING
    assert answers[str(square.pk)].open_balance == Decimal("0"), (
        "an account with nothing open owes 0.00 — a real figure, and not the "
        "same statement as 'nobody could ask'"
    )


# ══════════════════════════════════════════════════════════════════════════
# tc5 — an unreachable seam answers None, and None is NOT 0.00
# ══════════════════════════════════════════════════════════════════════════
def test_cr044_tc5__an_unreachable_seam_is_none_and_never_zero(brazos, dana, monkeypatch):
    """The rule every one of the four surfaces renders as `—`.

    Zero means *this customer owes nothing from before*. None means *nobody
    could ask*. A screen that printed `0.00` on an unreachable seam would tell
    a clerk about to bill 47 people that all of them are square, and the reason
    would be invisible — which is precisely the defect BR-BIL-160 was written
    for, one screen earlier in the same flow.

    The problem travels WITH the answer so the caller can say why, rather than
    having to invent a sentence for an absence it cannot explain.
    """
    from apps.billing import open_balance, payments_seam

    monkeypatch.setattr(payments_seam, "_resolve", lambda *a, **k: None)

    with tenant_ctx(brazos):
        run = a_run(brazos, key="2026-06|cr044-tc5")
        account = an_account(dana, brazos, account_no="A-11028")
        a_bill_of(
            brazos,
            account,
            run,
            invoice_no="BL-2606-000305",
            total=PRIOR_BILL_TOTAL,
            status=models.INVOICE_ISSUED,
            issued_at=datetime(2026, 6, 3, tzinfo=UTC),
        )
        position = open_balance.open_balance_for_account(account.pk)

    assert position.open_balance is None, "unreachable is an absence, never a zero"
    assert position.previous_balance is None
    assert position.problems, "and the reason travels with it"
    assert _foots(position), position


# ══════════════════════════════════════════════════════════════════════════
# tc6 — the basis is STAMPED, because OQ-217 may move it
# ══════════════════════════════════════════════════════════════════════════
def test_cr044_tc6__the_answer_states_which_window_it_was_read_over(brazos, dana):
    """OQ-217 moved the window (ruled 2026-10-01) and this is how a later reader survives it.

    BR-BIL-035 signs the ARITHMETIC and names neither operand's WINDOW. This
    reads over the still-open bills, which reproduces ❄️ WE-1 exactly. The
    consequence a reader must know: a prior bill settled IN FULL leaves the set
    with its payment, so a customer who paid last month sees `0.00 − 0.00`
    rather than `100.00 − 100.00`. The TOTAL DUE is identical either way.

    `issue.py` already stamps this onto the immutable bill for the same reason.
    A figure on a screen that cannot say which definition produced it is a
    figure nobody can reconcile against the bill beside it.
    """
    from apps.billing import issue, open_balance

    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-11029")
        position = open_balance.open_balance_for_account(account.pk)

    assert position.basis, "the window is a VALUE, not a comment"
    assert position.basis_oq == "OQ-217"
    # The reader RESTATES issue.py's two constants rather than importing them
    # (a read module must not import a write path to borrow two strings), and
    # hard-won law 1 says a docstring claiming they agree is not the guarantee.
    # This is the guarantee: the screen and the immutable bill name the same
    # window, or this goes RED.
    assert open_balance.BALANCE_FORWARD_BASIS == issue.BALANCE_FORWARD_BASIS
    assert open_balance.BALANCE_FORWARD_BASIS_OQ == issue.BALANCE_FORWARD_BASIS_OQ


# ══════════════════════════════════════════════════════════════════════════
# tc7 — a money figure NEVER travels without its CHAR(3) (CLAUDE.md rule 2)
# ══════════════════════════════════════════════════════════════════════════
def test_cr044_tc7__the_figure_carries_the_currency_it_is_owed_in(brazos, dana):
    """Two sources, one rule, and neither is a tenant default.

    The account that HAS been billed owes in the currency its bills were written
    in — billing's own column. The account that has only been MIGRATED has no
    bill to read, and its currency is on the opening bucket, which is customers'
    record. Both are the owner's recorded fact; nothing falls back to the other
    and nothing invents a third.

    The case that makes this necessary is tc2's: a migrated account with no
    invoice anywhere owes ❄️ GT-16's **267.30**, and a screen with an amount and
    no currency cannot print it (`MoneyCell` refuses, DEF-151) — so the figure
    the reader was built for would have been the one it could not show.
    """
    from apps.billing import open_balance

    with tenant_ctx(brazos):
        run = a_run(brazos, key="2026-06|cr044-tc7")
        billed = an_account(dana, brazos, account_no="A-11030")
        a_bill_of(
            brazos,
            billed,
            run,
            invoice_no="BL-2606-000306",
            total=PRIOR_BILL_TOTAL,
            status=models.INVOICE_ISSUED,
            issued_at=datetime(2026, 6, 3, tzinfo=UTC),
        )
        migrated = a_migrated_account(brazos, dana, account_no="A-12105")
        square = an_account(dana, brazos, account_no="A-11031")

        from_bill = open_balance.open_balance_for_account(billed.pk)
        from_bucket = open_balance.open_balance_for_account(migrated.pk)
        nothing = open_balance.open_balance_for_account(square.pk)

    assert from_bill.currency == "USD", "the currency the customer was BILLED in"
    assert from_bucket.currency == "USD", (
        "the migrated account has no bill to read a currency from — it comes off "
        "the opening bucket, which is customers' own record"
    )
    assert nothing.currency is None, (
        "no bill and no migration: there is no figure to print a currency for, "
        "and inventing one would be a guess about what a customer pays in"
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-044 §4 (04-docs/05-modules/07-billing/10-cr044-workflow-design.md) ·
#         DEF-1081 · BR-BIL-035 · BR-BIL-160 · BR-PAY-041 · ❄️ WE-1 · ❄️ GT-16
# generated: 2026-08-27 by the CR-044 lane
# gates: RED PROVED FIRST — all six cases run against a tree with no
#         `apps/billing/open_balance.py`; verbatim failure in the lane report
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
