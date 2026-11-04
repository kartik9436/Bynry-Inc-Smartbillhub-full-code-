# ── Trace ──────────────────────────────────────────────
# Story:    US-LED-001 (the final-bill deposit rows) · J70 E3 (the one-time final bill)
# Rules:    BR-BIL-013 (RULED 2026-09-30, option A — the leftover deposit is REFUNDED) ·
#           OQ-248 (CLOSED 2026-09-30) · CLAUDE.md rules 2, 5, 6
# Golden:   GT-23 / WE-7 ❄️ Case A (153.50 against 142.30 → 11.20 owed back)
# Tests:    this file
# Impacts:  apps/ledger/deposit_legs.py 🔒 · apps/billing/posting_seam.py 🔒
# ───────────────────────────────────────────────────────
"""OQ-248, ruled: a closing customer's leftover deposit is REFUNDED.

PO, 2026-09-30, verbatim: *"A for deposit refund"*. The part of the deposit left
over after everything owed moves to CUSTOMER CREDIT (money owed back to the
customer) and leaves the books when the refund is paid.

Until this ruling `post_deposit_applied` REFUSED this case by name, and J70 E3
was refused at Send: a **$150.00** deposit against a **$103.67** final balance.

The entry is ONE balanced entry on the existing `deposit_applied` key, so a replay
still writes nothing twice (hard rule 6):

    DR  2300 customer deposit liability   credit        (the liability closes)
    CR  1200 accounts receivable          what is owed  (the bill is settled)
    CR  2400 customer credit balances     the excess    (owed back to them)

AR never goes negative, and the refund row already signed beside this one
(*"Refund executed | customer credit | cash"*) finds the money where it pays from.
"""

from __future__ import annotations

from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal

import pytest

from apps.billing import posting_seam
from apps.ledger import chart, deposit_legs, models, selectors

from tests.ledger_le_fixtures import make_accounts, uuid_for
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

ZERO = Decimal("0")

# ❄️ GT-23 / WE-7 Case A, transcribed — never computed here.
DEPOSIT_CREDIT = Decimal("153.50")
CASE_A_CHARGES = Decimal("142.30")
CASE_A_REFUND = Decimal("11.20")

# J70 E3, the figure the PO was shown with the ruling.
J70_DEPOSIT = Decimal("150.00")
J70_BALANCE = Decimal("103.67")
J70_REFUND = Decimal("46.33")

MOVE_OUT_ON = date(2026, 7, 31)
POSTED_AT = datetime(2026, 8, 3, 9, 15, tzinfo=dt_timezone.utc)


def lines_by_designation(tenant, entry_id):
    by_id = {
        selectors.gl_account_id_for_designation(name): name
        for name in (chart.DEPOSIT_LIABILITY, chart.AR, chart.CUSTOMER_CREDIT_BALANCE)
    }
    out = {}
    for line in models.JournalLine.objects.filter(tenant=tenant, journal_entry_id=entry_id):
        out[(by_id.get(str(line.ledger_account_id)) or by_id.get(line.ledger_account_id), line.side)] = (
            line.amount,
            str(line.account_id),
        )
    return out


def apply_deposit(account, *, source_id, credit, position):
    return deposit_legs.post_deposit_applied(
        account_id=account.id,
        source_type="invoice",
        source_id=source_id,
        credit=credit,
        closing_position=position,
        entry_date=MOVE_OUT_ON,
        posted_at=POSTED_AT,
        currency="USD",
    )


def test_oq_248__case_a_posts_the_excess_to_customer_credit_not_a_negative_receivable(
    brazos, dana
):
    """WE-7 Case A: 153.50 against 142.30 → CR AR 142.30, CR 2400 11.20, DR 2300 153.50."""
    with tenant_ctx(brazos):
        accounts = make_accounts(dana, brazos, {})
        account = accounts["ACC-1055"]
        leg = apply_deposit(
            account, source_id=uuid_for("final/WE-7A"), credit=DEPOSIT_CREDIT, position=CASE_A_CHARGES
        )

        assert leg is not None and leg.created is True
        assert leg.amount == DEPOSIT_CREDIT
        assert leg.refunded == CASE_A_REFUND
        assert models.JournalEntry.objects.count() == 1

        lines = lines_by_designation(brazos, leg.entry_id)
        assert lines[(chart.DEPOSIT_LIABILITY, models.SIDE_DEBIT)][0] == DEPOSIT_CREDIT
        assert lines[(chart.AR, models.SIDE_CREDIT)][0] == CASE_A_CHARGES
        assert lines[(chart.CUSTOMER_CREDIT_BALANCE, models.SIDE_CREDIT)][0] == CASE_A_REFUND
        # Every line names the customer, so the refund is THEIRS in the books.
        assert {acct for _amount, acct in lines.values()} == {str(account.id)}


def test_oq_248__the_j70_figure_150_against_103_67_leaves_46_33_owed_back(brazos, dana):
    with tenant_ctx(brazos):
        accounts = make_accounts(dana, brazos, {})
        leg = apply_deposit(
            accounts["ACC-1055"], source_id=uuid_for("final/J70-E3"), credit=J70_DEPOSIT, position=J70_BALANCE
        )
        lines = lines_by_designation(brazos, leg.entry_id)
        assert lines[(chart.AR, models.SIDE_CREDIT)][0] == J70_BALANCE
        assert lines[(chart.CUSTOMER_CREDIT_BALANCE, models.SIDE_CREDIT)][0] == J70_REFUND
        assert leg.refunded == J70_REFUND


def test_oq_248__nothing_owed_refunds_the_whole_deposit_and_writes_no_zero_ar_line(brazos, dana):
    """A closing position of zero (or already in credit) owes nothing: all of it goes back."""
    with tenant_ctx(brazos):
        accounts = make_accounts(dana, brazos, {})
        for seed, position in (("zero", ZERO), ("credit", Decimal("-4.00"))):
            leg = apply_deposit(
                accounts["ACC-1055"], source_id=uuid_for(f"final/{seed}"), credit=J70_DEPOSIT, position=position
            )
            lines = lines_by_designation(brazos, leg.entry_id)
            assert (chart.AR, models.SIDE_CREDIT) not in lines
            assert lines[(chart.CUSTOMER_CREDIT_BALANCE, models.SIDE_CREDIT)][0] == J70_DEPOSIT
            assert leg.refunded == J70_DEPOSIT


def test_oq_248__replaying_the_refund_case_writes_nothing_twice(brazos, dana):
    with tenant_ctx(brazos):
        accounts = make_accounts(dana, brazos, {})
        source_id = uuid_for("final/replay")
        first = apply_deposit(accounts["ACC-1055"], source_id=source_id, credit=DEPOSIT_CREDIT, position=CASE_A_CHARGES)
        again = apply_deposit(accounts["ACC-1055"], source_id=source_id, credit=DEPOSIT_CREDIT, position=CASE_A_CHARGES)
        assert again.created is False and again.entry_id == first.entry_id
        assert models.JournalEntry.objects.count() == 1


def test_oq_248__the_signed_case_b_is_unchanged_and_refunds_nothing(brazos, dana):
    with tenant_ctx(brazos):
        accounts = make_accounts(dana, brazos, {})
        leg = apply_deposit(
            accounts["ACC-1055"], source_id=uuid_for("final/WE-7B"), credit=DEPOSIT_CREDIT, position=Decimal("289.40")
        )
        lines = lines_by_designation(brazos, leg.entry_id)
        assert leg.refunded == ZERO
        assert (chart.CUSTOMER_CREDIT_BALANCE, models.SIDE_CREDIT) not in lines
        assert lines[(chart.AR, models.SIDE_CREDIT)][0] == DEPOSIT_CREDIT


def test_oq_248__the_preview_posts_the_refund_instead_of_refusing(brazos, dana):
    """The Send card's books panel asks the same question of the same two figures."""
    with tenant_ctx(brazos):
        make_accounts(dana, brazos, {})

        class Deposit:
            exists = True
            total = J70_DEPOSIT
            interest = ZERO

        preview = posting_seam.preview_bill_entries(
            bill_type=posting_seam.BILL_TYPE_FINAL,
            charges=Decimal("60.00"),
            currency="USD",
            deposit=Deposit(),
            closing_position=J70_BALANCE,
        )
        assert preview.refused is False and preview.posts is True
        by_event = {entry.event: entry for entry in preview.entries}
        applied = by_event[posting_seam.EVENT_DEPOSIT_APPLIED]
        assert applied.amount == J70_BALANCE
        assert applied.credit.designation == posting_seam.AR_DESIGNATION
        refunded = by_event[posting_seam.EVENT_DEPOSIT_REFUNDED]
        assert refunded.amount == J70_REFUND
        assert refunded.debit.designation == posting_seam.DEPOSIT_LIABILITY_DESIGNATION
        assert refunded.credit.designation == posting_seam.CREDIT_BALANCE_DESIGNATION
