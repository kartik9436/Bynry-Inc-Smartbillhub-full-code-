# ── Trace ──────────────────────────────────────────────
# Change:   CR-059 · CS-20 · task 30 — "Accrue deposit interest", the CR's own
#           *"blocks closing ANY account that holds a deposit — which is every
#           residential account at a utility that takes deposits."*
# Story:    US-CUS-023 §7   Screens: S21 · S20 · S66
# Rules:    BR-CUS-057 (CONFIRMED — tenant-set simple annual rate, default 0%,
#           accruing monthly from the ORIGINAL receipt date) · BR-CUS-050 ·
#           BR-CUS-025 (a deposit is a liability) · BR-TEN-043 / gate G6
# Golden:   ❄️ GT-61 — $150 @ 2.0%, 89 months → **$22.25** (B5, FROZEN) ·
#           WE-7 — $150 @ 2%, 14 months → **$3.50**
# ───────────────────────────────────────────────────────
"""BR-CUS-057's two signed figures, and the four answers that are not numbers.

**EVERY EXPECTATION HERE IS TRANSCRIBED, NEVER RECOMPUTED.** `22.25` and `3.50`
are written as literals with the line they came from quoted beside them; a test
that derived them from this module's own formula would agree with a broken one.

The RED proof is in the lane report: at the pinned tip this file will not
collect (`ImportError: cannot import name 'deposit_interest'`) and
`move_out_settlement` reports `deposit_interest_not_accrued` on every account
that holds a deposit.
"""

from datetime import date
from decimal import Decimal

import pytest

from apps.customers import deposit_interest, models
from apps.customers.services import record_deposit_movement

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_w3_billing_models import an_account

pytestmark = pytest.mark.django_db

#: ❄️ B5, `04-docs/02-decisions/05-golden-tests.md`, verbatim: *"**GT-61 =
#: deposit interest** (BR-CUS-057; $150 @ 2.0%, 89 mo → $22.25)"*.
GT61_PRINCIPAL = Decimal("150.00")
GT61_RATE_PERCENT = Decimal("2.0")
GT61_MONTHS = 89
GT61_INTEREST = Decimal("22.25")

#: WE-7, quoted by `move_out_settlement`'s own gap reason: *"$3.50 on a $150
#: deposit held 14 months at 2%"*.
WE7_MONTHS = 14
WE7_INTEREST = Decimal("3.50")


# ══════════════════════════════════════════════════════════════════════════
# 1 · THE TWO FROZEN FIGURES
# ══════════════════════════════════════════════════════════════════════════


def test_gt61_is_reproduced_exactly():
    """❄️ GT-61 — $150 at 2.0% for 89 months is **$22.25**. FROZEN (B5).

    89 months is 7 years and 5 months, which is why this is the figure worth
    freezing: it is long enough that rounding the rate, or a monthly amount,
    before summing would show. Nothing here is quantised until the end.
    """
    received = date(2019, 2, 2)
    # 89 months after 2 February 2019 is 2 July 2026 — stated rather than
    # computed, so the month arithmetic is under test too.
    as_of = date(2026, 7, 2)
    assert deposit_interest.completed_months(received, as_of) == GT61_MONTHS

    assert (
        deposit_interest.accrued(
            principal=GT61_PRINCIPAL,
            annual_rate_percent=GT61_RATE_PERCENT,
            received_on=received,
            as_of=as_of,
        )
        == GT61_INTEREST
    )


def test_we7_is_reproduced_exactly():
    """WE-7 — $150 at 2% for 14 months is **$3.50**.

    The figure `move_out_settlement` has been quoting in its own refusal for
    weeks while being unable to produce it.
    """
    received = date(2026, 2, 2)
    as_of = date(2027, 4, 2)  # 14 months later
    assert deposit_interest.completed_months(received, as_of) == WE7_MONTHS
    assert (
        deposit_interest.accrued(
            principal=Decimal("150.00"),
            annual_rate_percent=Decimal("2"),
            received_on=received,
            as_of=as_of,
        )
        == WE7_INTEREST
    )


def test_the_rate_is_a_percentage_and_not_a_fraction():
    """`2.000000` means 2%, and reading it as 0.02% is the silent error.

    The Settings field carries a per-cent unit and the column is `NUMERIC(18,6)`
    (hard rule 2 — percentages at six decimals). A fraction reading pays a
    hundredth of what is owed and nobody notices for a year.
    """
    one_year = deposit_interest.accrued(
        principal=Decimal("150.00"),
        annual_rate_percent=Decimal("2"),
        received_on=date(2026, 1, 1),
        as_of=date(2027, 1, 1),
    )
    assert one_year == Decimal("3.00"), "2% of 150.00 for one year is 3.00, not 0.03"


# ══════════════════════════════════════════════════════════════════════════
# 2 · "COMPLETED MONTHS" — the judgment, asserted so it cannot drift
# ══════════════════════════════════════════════════════════════════════════


def test_a_month_completes_on_the_anniversary_day():
    """Received 2 February is ONE month old on 2 March, not on 1 March."""
    assert deposit_interest.completed_months(date(2026, 2, 2), date(2026, 3, 1)) == 0
    assert deposit_interest.completed_months(date(2026, 2, 2), date(2026, 3, 2)) == 1
    assert deposit_interest.completed_months(date(2026, 2, 2), date(2026, 3, 31)) == 1


def test_a_short_month_completes_on_its_last_day():
    """Decision log 2026-09-03 — the clamp, and why it is not a detail.

    A deposit received on **31 January** is one month old on **28 February**.
    A naive day-of-month comparison gives ZERO, and would under-pay every
    customer who paid on a 29th, 30th or 31st for the rest of their tenancy.
    """
    assert deposit_interest.completed_months(date(2026, 1, 31), date(2026, 2, 28)) == 1
    assert deposit_interest.completed_months(date(2026, 1, 31), date(2026, 2, 27)) == 0
    # …and the following month, where the 31st does exist, is unaffected.
    assert deposit_interest.completed_months(date(2026, 1, 31), date(2026, 3, 30)) == 1
    assert deposit_interest.completed_months(date(2026, 1, 31), date(2026, 3, 31)) == 2


def test_a_date_before_the_money_arrived_accrues_nothing():
    """Never negative: interest running backwards makes the customer owe us."""
    assert deposit_interest.completed_months(date(2026, 5, 1), date(2026, 2, 1)) == 0
    assert deposit_interest.accrued(
        principal=Decimal("150.00"),
        annual_rate_percent=Decimal("2"),
        received_on=date(2026, 5, 1),
        as_of=date(2026, 2, 1),
    ) == Decimal("0")


def test_a_zero_rate_is_a_real_answer_of_zero():
    """BR-CUS-057's DEFAULT is 0%, and that is the ordinary case.

    Zero here is not an absence: the customer is owed their principal back and
    the settlement can complete. Only an UNREADABLE rate answers None.
    """
    assert deposit_interest.accrued(
        principal=Decimal("150.00"),
        annual_rate_percent=Decimal("0"),
        received_on=date(2019, 2, 2),
        as_of=date(2026, 7, 2),
    ) == Decimal("0")


# ══════════════════════════════════════════════════════════════════════════
# 3 · THE ACCOUNT-LEVEL READ — and the three answers that are None
# ══════════════════════════════════════════════════════════════════════════


def test_an_account_holding_no_deposit_answers_zero_not_none(brazos, dana):
    """Nothing to accrue on. These accounts were never blocked and must not be."""
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        assert deposit_interest.deposit_interest_accrued(account.pk, date(2026, 7, 2)) == Decimal(
            "0"
        )


def test_a_deposit_with_no_receipt_date_answers_NONE_and_never_a_guess(brazos, dana):
    """The CR's own ⚠: *"a single wrong start date is wrong on every account at once"*.

    A register row that predates BR-CUS-050's stamping has no clock start, and
    substituting the account's opening date would silently under- or over-pay
    every such customer. It REPORTS instead, and the settlement stays closed.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        models.Account.objects.filter(pk=account.pk).update(
            deposit_on_file=Decimal("150.00"), deposit_received_on=None
        )
        assert deposit_interest.deposit_interest_accrued(account.pk, date(2026, 7, 2)) is None


def test_an_account_that_is_not_this_tenants_answers_None(brazos, dana):
    """CLAUDE.md rule 1. An id from nowhere is not an account holding nothing."""
    import uuid

    with tenant_ctx(brazos):
        assert deposit_interest.deposit_interest_accrued(uuid.uuid4(), date(2026, 7, 2)) is None


def test_the_register_stamps_the_receipt_date_and_the_engine_reads_it(brazos, dana):
    """BR-CUS-050 end to end — the date the money arrived drives the accrual.

    The deposit goes on through `record_deposit_movement`, which is the only
    writer of `accounts.deposit_on_file`, so this exercises the same column the
    settlement reads rather than a value typed straight into the row.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        movement = record_deposit_movement(
            account.pk, Decimal("150.00"), actor=dana, received_on=date(2019, 2, 2)
        )
        assert movement.held_after == Decimal("150.00")

        account.refresh_from_db()
        assert account.deposit_received_on == date(2019, 2, 2)

        # The tenant's seeded rate is BR-CUS-057's DEFAULT of 0%, so the answer
        # is a real zero — and it is an ANSWER, which is the whole point: this
        # account can now be closed.
        answer = deposit_interest.deposit_interest_accrued(account.pk, date(2026, 7, 2))
        assert answer is not None
        assert answer == Decimal("0")


def test_a_second_deposit_does_not_restart_the_interest_clock(brazos, dana):
    """BR-CUS-050, and the register already guarantees it — asserted from HERE.

    A second deposit on an account that already holds one must not re-stamp the
    receipt date, or the customer who has been with the utility longest is
    quietly paid the least. The guarantee lives in `record_deposit_movement`;
    this is the test that fails if somebody relaxes it, because the consequence
    is only visible from the accrual side.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        record_deposit_movement(
            account.pk, Decimal("150.00"), actor=dana, received_on=date(2019, 2, 2)
        )
        record_deposit_movement(
            account.pk, Decimal("50.00"), actor=dana, received_on=date(2026, 6, 1)
        )
        account.refresh_from_db()
        assert account.deposit_on_file == Decimal("200.00")
        assert account.deposit_received_on == date(2019, 2, 2), (
            "the ORIGINAL receipt date stands — BR-CUS-050 — or the customer who paid first "
            "is paid interest from the day somebody topped their deposit up"
        )


# ══════════════════════════════════════════════════════════════════════════
# 4 · THE THING THIS UNBLOCKS — a closing account, settled
# ══════════════════════════════════════════════════════════════════════════


def test_the_move_out_settlement_stops_gapping_on_a_stated_day(brazos, dana):
    """CS-20's headline, proved where it actually bit.

    `move_out_settlement` fails CLOSED on `deposit_interest_not_accrued`, so an
    account holding a deposit could not be settled by anybody. With the engine
    published AND a day stated, the term is answered and the gap is gone.
    """
    from apps.customers import move_out_settlement

    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        record_deposit_movement(
            account.pk, Decimal("150.00"), actor=dana, received_on=date(2026, 2, 2)
        )
        account.refresh_from_db()

        answered = move_out_settlement._deposit_interest(account, date(2026, 7, 2))
        assert answered is not None, "the engine answers, so the settlement is not blocked"

        # …and with NO day stated it still reports, which is the fail-closed
        # posture unchanged: BR-TEN-043 forbids this layer picking one.
        assert move_out_settlement._deposit_interest(account, None) is None
