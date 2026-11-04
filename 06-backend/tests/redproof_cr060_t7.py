"""RED PROOFS for CR-060 T7 (CLAUDE.md hard-won law 7).

Each case DISABLES one guard — through `monkeypatch`, so **no live file is
edited** (DEF-3101: a red-proof harness that mutates a live file overlapped a
push and shipped a money control as a bare `pass` for one commit) — and asserts
the DAMAGE that guard exists to prevent. **These cases PASS when the guard is
removed.** That is the point: each one reproduces the failure, with its figure,
so the guard is demonstrably load-bearing rather than assumed to be.

Run explicitly:
    pytest tests/redproof_cr060_t7.py -q

The filename deliberately does NOT start with `test_`, so an ordinary suite run
never collects it (`pyproject.toml` sets no `python_files`, so pytest's default
`test_*.py` applies). It is a scaffold kept in the repo so the next lane can
re-run the proof instead of taking a lane report's word for it.

WHAT THEY MEASURED, 2026-09-02:

  1. closed-period refusal removed → the accrual posted **dated 31 August,
     inside a CLOSED August**. It did NOT forward into September as the first
     draft of this proof predicted: `posting.post()` does not resolve or refuse
     a closed-period date at all, and every live caller happens to do it for
     itself. That is a defect in its own right and is filed.
  2. period-scoped posting key replaced with a per-press one → `1210` went
     **68.04 → 136.08**: the utility owed twice for the same water.
  3. unit check removed → 10,000 gallons priced at the per-thousand-gallon rate
     produced **$31,000.00** of water revenue instead of **$31.00**.
"""

from datetime import datetime, timezone as dt_timezone
from decimal import Decimal

import pytest

from apps.ledger import close, models, unbilled_accrual

from tests.test_cr060_t7_unbilled_accrual import (  # noqa: F401
    AUGUST_END,
    AUGUST_START,
    POSTED_AT,
    TOTAL_ACCRUAL,
    _balance,
    brazos,
    dana,
    tenant_ctx,
    the_worked_month,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403

pytestmark = pytest.mark.django_db


def test_redproof_1__without_the_closed_period_refusal_the_entry_lands_in_september(
    brazos, dana, monkeypatch
):
    """Disable the closed-period check and August's revenue posts anyway.

    With the guard the accrual REFUSES and the closed month is byte-identical —
    C2's own proof. Without it the entry lands **dated 31 August, inside the
    closed month**, and a closed month's trial balance moves. See the body: the
    damage is worse than this proof's first draft predicted, and the reason is a
    defect in the posting service that is filed separately.
    """
    with tenant_ctx(brazos):
        the_worked_month(brazos, dana)
        close.close_period(
            dana,
            period_start=AUGUST_START,
            period_end=AUGUST_END,
            closed_at=datetime(2026, 9, 5, 10, 0, tzinfo=dt_timezone.utc),
            reason="red proof",
        )
        # THE GUARD, REMOVED: the preview no longer notices the closed period.
        real = unbilled_accrual.preview_unbilled_revenue

        def blind(*, period_start, period_end):
            preview = real(period_start=period_start, period_end=period_end)
            return type(preview)(**{**preview.__dict__, "period_is_closed": False})

        monkeypatch.setattr(unbilled_accrual, "preview_unbilled_revenue", blind)

        result = unbilled_accrual.accrue_unbilled_revenue(
            dana, period_start=AUGUST_START, period_end=AUGUST_END, posted_at=POSTED_AT
        )
        entry = models.JournalEntry.objects.get(pk=result.entry_id)
        # THE DAMAGE, AND IT IS WORSE THAN THIS PROOF FIRST PREDICTED.
        #
        # The first draft asserted `entry_date > AUGUST_END` — that BR-TEN-038
        # would forward the entry into September. It does not, and the reason
        # matters: `posting.post()` takes the book date its CALLER gives it and
        # does not resolve the period itself (that is why `manual_je` resolves
        # before it posts, and why this module REFUSES before it posts). So with
        # the refusal removed the entry lands dated **31 August, inside the
        # CLOSED month** — the closed period's trial balance moves, which is the
        # one thing BR-LED-006 and BR-LED-017 promise cannot happen.
        assert entry.entry_date == AUGUST_END, entry.entry_date
        assert close.is_period_closed(AUGUST_START, AUGUST_END) is True


def test_redproof_2__without_a_period_scoped_posting_key_the_receivable_doubles(
    brazos, dana, monkeypatch
):
    """Give the second press a different key and 1210 goes to 136.08.

    The replay guard is the KEY, not the button. With one key per period the
    second press returns the first entry; with a fresh key it posts again.
    """
    with tenant_ctx(brazos):
        the_worked_month(brazos, dana)
        unbilled_accrual.accrue_unbilled_revenue(
            dana, period_start=AUGUST_START, period_end=AUGUST_END, posted_at=POSTED_AT
        )
        assert _balance(brazos, "1210") == TOTAL_ACCRUAL

        # THE GUARD, REMOVED: a key that is not one-per-period.
        monkeypatch.setattr(
            unbilled_accrual,
            "accrual_posting_key",
            lambda **kwargs: "unbilled_revenue_accrual|second-press|accrued",
        )
        unbilled_accrual.accrue_unbilled_revenue(
            dana,
            period_start=AUGUST_START,
            period_end=AUGUST_END,
            posted_at=datetime(2026, 9, 1, 9, 30, tzinfo=dt_timezone.utc),
        )
        # THE DAMAGE: the utility is owed twice for the same water.
        assert _balance(brazos, "1210") == Decimal("136.08")


def test_redproof_3__without_the_unit_check_gallons_are_priced_as_thousands(
    brazos, dana, monkeypatch
):
    """Read gallons against a price quoted per THOUSAND gallons.

    With the guard the readings are excluded and counted by name. Without it the
    same ten readings price at the kgal rate and the accrual is wrong by three
    orders of magnitude in the WRONG direction — and it looks entirely
    plausible, which is why the check is a refusal and not a conversion.

    ⚠ The mismatch is BUILT by the fixture, never edited in: a committed read is
    immutable on PostgreSQL (`meter_reads_value_immutable`, BR-MET-053) and is
    not on SQLite. See `the_worked_month`, and hard-won law 14.
    """
    from apps.ledger import billing_seam

    with tenant_ctx(brazos):
        the_worked_month(brazos, dana, water_read_unit="gal")

        # THE GUARD, REMOVED: the priced line reports no unit, so nothing can
        # disagree with the read's.
        real = billing_seam.last_priced_usage

        def unitless(**kwargs):
            outcome = real(**kwargs)
            prices = {
                key: type(row)(**{**row.__dict__, "unit": None})
                for key, row in (outcome.prices or {}).items()
            }
            return type(outcome)(
                prices=prices,
                last_billed_period_end=outcome.last_billed_period_end,
                problems=outcome.problems,
            )

        monkeypatch.setattr(billing_seam, "last_priced_usage", unitless)

        preview = unbilled_accrual.preview_unbilled_revenue(
            period_start=AUGUST_START, period_end=AUGUST_END
        )
        # THE DAMAGE: **10 GALLONS** of water priced at the per-THOUSAND-gallon
        # rate. The accrual credits **$31.00** of water revenue for water worth
        # **$0.031** — a thousandfold overstatement that reads as an ordinary
        # figure on an ordinary month, which is exactly why the unit is checked
        # and never converted.
        water = next(row for row in preview.services if row.service_code == "water")
        assert water.unit == "gal"
        assert water.amount == Decimal("31.00"), water.amount
