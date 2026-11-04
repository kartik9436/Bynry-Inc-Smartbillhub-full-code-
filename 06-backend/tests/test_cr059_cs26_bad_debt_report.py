# ── Trace ──────────────────────────────────────────────
# Change:   CR-059 · CS-26 · task 64 — report what was written off, and why.
# Story:    US-PAY-012   Screens: S36 (Finance · Revenue & AR)
# Rules:    BR-PAY-020 (payments owns the transaction, the ledger posts, FINANCE
#           REPORTS — CS-26 adds no new rule) · BR-PAY-1120 (a `reversed` row is
#           netted, never counted) · BR-REP-001 (a money report labels its
#           basis) · BR-REP-002 (a read-model, never a stored total) ·
#           BR-BIL-013 (billing's small-balance path is a different act) ·
#           CLAUDE.md rule 1 · rule 2 (money 4dp, percentages 6dp, CHAR(3))
# ───────────────────────────────────────────────────────
"""CS-26 on its own worked shape, to the cent and to the sixth decimal.

The spec states the answer it wants: *"uncollectible 120 days 2,840.00 · 72% ·
deceased, no estate 712.40 · 18% · bankruptcy 387.60 · 10%"*. Those three add to
**3,940.00**, and the exact shares are **72.081218 %**, **18.081218 %** and
**9.837563 %** — served at six decimals (hard rule 2) and displayed at two, which
is where CS-26's `72%` comes from.

════════════════════════════════════════════════════════════════════════════
PROVED RED FIRST (hard-won law 7)
════════════════════════════════════════════════════════════════════════════
**RUN, and quoted as OBSERVED:**

  * **the read.** At the pinned tip `7d95b1d2`, in a detached worktree, this
    file cannot be collected at all —
    `E   ImportError: cannot import name 'bad_debt' from 'apps.payments'`.
  * **the doors.** With `bad_debt.py` and `writeoffs_api.py` present but the
    `include` absent from `config/urls.py`, `test_the_bad_debt_doors_are_mounted`
    fails
    `E   django.urls.exceptions.Resolver404: {'tried': […], 'path': 'bad-debt'}`.

⚠ **THREE FURTHER MUTATIONS WERE NAMED IN THE FIRST DRAFT OF THIS DOCSTRING AND
NOT RUN, SO THE CLAIM IS WITHDRAWN RATHER THAN LEFT STANDING** (hard-won law 1,
and the `CR-059` CS-5 lane's own precedent for the same wording): counting a
`reversed` row as bad debt instead of subtracting it, quantising the share to
two decimals instead of six, and re-dating the mirror out of the window. Each is
asserted GREEN below and none has been *shown* to fail on its own.

════════════════════════════════════════════════════════════════════════════
WHAT THIS FILE DOES NOT PROVE (CLAUDE.md law 14)
════════════════════════════════════════════════════════════════════════════
Nothing here catches a database error, so no savepoint is involved and no
PostgreSQL-only behaviour is relied on. `bad_debt.py` writes nothing at all.
"""

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from django.urls import resolve

from apps.payments import bad_debt, writeoffs, writeoffs_api
from apps.payments.collections_models import (
    WRITE_OFF_REASON_BANKRUPTCY,
    WRITE_OFF_REASON_DECEASED,
    WRITE_OFF_REASON_UNCOLLECTIBLE,
    WRITE_OFF_REVERSED,
)
from apps.payments.exceptions import PaymentRuleError

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_pay_001_record_payment import an_issued_bill
from tests.test_us_ten_helpers import api_call
from tests.test_w3_billing_models import an_account

pytestmark = pytest.mark.django_db

#: CS-26's own three figures, and their sum.
UNCOLLECTIBLE = Decimal("2840.00")
DECEASED = Decimal("712.40")
BANKRUPTCY = Decimal("387.60")
TOTAL = Decimal("3940.00")

#: The exact shares of that total, at hard rule 2's six decimals.
SHARE_UNCOLLECTIBLE = "72.081218"
SHARE_DECEASED = "18.081218"
SHARE_BANKRUPTCY = "9.837563"

YEAR_START = date(2026, 1, 1)
YEAR_END = date(2026, 12, 31)
AUGUST = date(2026, 8, 15)
AUGUST_AT = datetime(2026, 8, 15, 9, 0, tzinfo=UTC)
SEPTEMBER = date(2026, 9, 20)
SEPTEMBER_AT = datetime(2026, 9, 20, 9, 0, tzinfo=UTC)
NOTE = "120+ days, 3 notices, phone contact failed ×4"


def _written_off(
    brazos, dana, *, account_no, amount, reason, approved_on=AUGUST, posted_at=AUGUST_AT
):
    """One APPROVED write-off of `amount` — request then approve, as a human does."""
    account = an_account(dana, brazos, account_no=account_no)
    an_issued_bill(
        brazos,
        account,
        number=f"BL-2605-{account_no[-5:]}",
        total=amount,
        issued_on=date(2026, 5, 16),
        due_date=date(2026, 5, 16),
    )
    requested = writeoffs.request_write_off(
        dana,
        account_id=account.pk,
        amount=amount,
        reason=reason,
        note=NOTE,
        requested_on=approved_on,
    )
    approved = writeoffs.approve_write_off(
        actor=dana,
        write_off_id=requested.write_off_id,
        approved_on=approved_on,
        posted_at=posted_at,
    )
    return account, approved


def _cs26_shape(brazos, dana):
    """CS-26's three worked rows, on three accounts."""
    _written_off(
        brazos,
        dana,
        account_no="A-20001",
        amount=UNCOLLECTIBLE,
        reason=WRITE_OFF_REASON_UNCOLLECTIBLE,
    )
    _written_off(
        brazos, dana, account_no="A-20002", amount=DECEASED, reason=WRITE_OFF_REASON_DECEASED
    )
    _written_off(
        brazos, dana, account_no="A-20003", amount=BANKRUPTCY, reason=WRITE_OFF_REASON_BANKRUPTCY
    )


# ══════════════════════════════════════════════════════════════════════════
# 1 · THE ADDRESS
# ══════════════════════════════════════════════════════════════════════════


def test_the_bad_debt_doors_are_mounted():
    """Through `config/urls.py`, and the STATIC segment first so `bad-debt` and
    `bad-debt/accounts` never swallow one another."""
    assert resolve("/api/brazos/bad-debt").func is writeoffs_api.bad_debt_report
    assert resolve("/api/brazos/bad-debt/accounts").func is writeoffs_api.bad_debt_accounts


# ══════════════════════════════════════════════════════════════════════════
# 2 · CS-26's OWN WORKED SHAPE
# ══════════════════════════════════════════════════════════════════════════


def test_bad_debt_by_reason_reproduces_the_specs_own_figures(brazos, dana):
    """2,840.00 · 712.40 · 387.60 = **3,940.00**, and the shares foot to 100%."""
    with tenant_ctx(brazos):
        _cs26_shape(brazos, dana)
        report = bad_debt.bad_debt(start=YEAR_START, end=YEAR_END)

        assert report["net"] == "3940.0000"
        assert report["written_off"] == "3940.0000"
        assert report["reversed"] == "0.0000"
        assert report["count"] == 3
        assert report["currency"] == "USD"
        # BR-REP-001 — a money report labels its basis, always.
        assert report["basis"] == "approved_on"

        rows = {row["reason"]: row for row in report["by_reason"]}
        assert rows[WRITE_OFF_REASON_UNCOLLECTIBLE]["net"] == "2840.0000"
        assert rows[WRITE_OFF_REASON_DECEASED]["net"] == "712.4000"
        assert rows[WRITE_OFF_REASON_BANKRUPTCY]["net"] == "387.6000"

        # Hard rule 2 — percentages to SIX. The screen shows CS-26's 72%.
        assert rows[WRITE_OFF_REASON_UNCOLLECTIBLE]["share_percent"] == SHARE_UNCOLLECTIBLE
        assert rows[WRITE_OFF_REASON_DECEASED]["share_percent"] == SHARE_DECEASED
        assert rows[WRITE_OFF_REASON_BANKRUPTCY]["share_percent"] == SHARE_BANKRUPTCY
        assert sum(Decimal(row["share_percent"]) for row in report["by_reason"]) == Decimal(
            "99.999999"
        )

        # Largest first — a board reads the top line.
        assert [row["reason"] for row in report["by_reason"]] == [
            WRITE_OFF_REASON_UNCOLLECTIBLE,
            WRITE_OFF_REASON_DECEASED,
            WRITE_OFF_REASON_BANKRUPTCY,
        ]
        # Every amount travels with its CHAR(3) code (hard rule 2, DEF-099).
        assert {row["currency"] for row in report["by_reason"]} == {"USD"}


def test_every_reason_is_listed_even_when_unused(brazos, dana):
    """A screen must be able to draw a zero row rather than silently dropping a
    category nobody used this year."""
    with tenant_ctx(brazos):
        _written_off(
            brazos,
            dana,
            account_no="A-20010",
            amount=UNCOLLECTIBLE,
            reason=WRITE_OFF_REASON_UNCOLLECTIBLE,
        )
        report = bad_debt.bad_debt(start=YEAR_START, end=YEAR_END)
        assert len(report["reasons"]) == 4
        assert len(report["by_reason"]) == 1


def test_by_month_is_chronological_and_foots_to_the_total(brazos, dana):
    with tenant_ctx(brazos):
        _written_off(
            brazos,
            dana,
            account_no="A-20011",
            amount=UNCOLLECTIBLE,
            reason=WRITE_OFF_REASON_UNCOLLECTIBLE,
        )
        _written_off(
            brazos,
            dana,
            account_no="A-20012",
            amount=DECEASED,
            reason=WRITE_OFF_REASON_DECEASED,
            approved_on=SEPTEMBER,
            posted_at=SEPTEMBER_AT,
        )
        report = bad_debt.bad_debt(start=YEAR_START, end=YEAR_END)
        assert [row["period"] for row in report["by_month"]] == ["2026-08", "2026-09"]
        assert report["by_month"][0]["net"] == "2840.0000"
        assert report["by_month"][1]["net"] == "712.4000"
        assert sum(Decimal(row["net"]) for row in report["by_month"]) == Decimal("3552.40")


def test_the_window_is_honoured_and_is_never_a_clock(brazos, dana):
    """BR-TEN-043 / gate G6 — a board pack re-run at midnight is the same
    document."""
    with tenant_ctx(brazos):
        _cs26_shape(brazos, dana)
        august_only = bad_debt.bad_debt(start=date(2026, 8, 1), end=date(2026, 8, 31))
        assert august_only["net"] == "3940.0000"
        july_only = bad_debt.bad_debt(start=date(2026, 7, 1), end=date(2026, 7, 31))
        assert july_only["net"] == "0.0000"
        assert july_only["count"] == 0
        # A share of nothing is NOT zero percent — `summary.py`'s zero-state.
        assert july_only["by_reason"] == []
        with pytest.raises(PaymentRuleError):
            bad_debt.bad_debt(start=YEAR_END, end=YEAR_START)


# ══════════════════════════════════════════════════════════════════════════
# 3 · CS-25 MEETS CS-26 — a reversal is NETTED, never counted
# ══════════════════════════════════════════════════════════════════════════


def test_a_reversal_is_netted_not_counted(brazos, dana):
    """A write-off approved in August and reversed in September nets to **0.00**
    over the year — and appears in BOTH months, because that is what happened."""
    with tenant_ctx(brazos):
        _account, approved = _written_off(
            brazos,
            dana,
            account_no="A-20020",
            amount=Decimal("948.20"),
            reason=WRITE_OFF_REASON_UNCOLLECTIBLE,
        )
        writeoffs.reverse_write_off(
            dana,
            write_off_id=approved.write_off_id,
            reversed_on=SEPTEMBER,
            posted_at=SEPTEMBER_AT,
            reason="raised against the wrong account",
        )
        report = bad_debt.bad_debt(start=YEAR_START, end=YEAR_END)
        assert report["written_off"] == "948.2000"
        assert report["reversed"] == "948.2000"
        assert report["net"] == "0.0000"
        # Both rows are real history and both are counted as rows.
        assert report["count"] == 2

        months = {row["period"]: row for row in report["by_month"]}
        assert months["2026-08"]["written_off"] == "948.2000"
        assert months["2026-08"]["reversed"] == "0.0000"
        assert months["2026-09"]["written_off"] == "0.0000"
        assert months["2026-09"]["reversed"] == "948.2000"
        # August's own answer does NOT change retroactively.
        august = bad_debt.bad_debt(start=date(2026, 8, 1), end=date(2026, 8, 31))
        assert august["net"] == "948.2000"

        # A zero (or negative) denominator gives None, never 0.000000.
        assert report["by_reason"][0]["share_percent"] is None


def test_requested_and_rejected_are_counted_nowhere(brazos, dana):
    """Neither ever posted. Either one inside a bad-debt total would be money
    the utility never gave up."""
    with tenant_ctx(brazos):
        pending = an_account(dana, brazos, account_no="A-20030")
        an_issued_bill(
            brazos,
            pending,
            number="BL-2605-20030",
            total=UNCOLLECTIBLE,
            issued_on=date(2026, 5, 16),
            due_date=date(2026, 5, 16),
        )
        requested = writeoffs.request_write_off(
            dana,
            account_id=pending.pk,
            amount=UNCOLLECTIBLE,
            reason=WRITE_OFF_REASON_UNCOLLECTIBLE,
            note=NOTE,
            requested_on=AUGUST,
        )
        report = bad_debt.bad_debt(start=YEAR_START, end=YEAR_END)
        assert report["net"] == "0.0000"
        assert report["count"] == 0

        writeoffs.reject_write_off(
            dana,
            write_off_id=requested.write_off_id,
            rejected_on=AUGUST,
            reason="wrong account",
        )
        after = bad_debt.bad_debt(start=YEAR_START, end=YEAR_END)
        assert after["net"] == "0.0000"
        assert after["count"] == 0


# ══════════════════════════════════════════════════════════════════════════
# 4 · THE LEDGER TIE-OUT — CS-26 asks for one, and it is computed separately
# ══════════════════════════════════════════════════════════════════════════


def test_the_ledger_agrees_with_the_payments_rows(brazos, dana):
    """Two independent readings of the same fact, served side by side.

    This module sums its own rows; the ledger sums `journal_lines` on
    `source_type='write_off'` against the account the tenant DESIGNATES
    `write_off`. Neither derives from the other.
    """
    with tenant_ctx(brazos):
        _cs26_shape(brazos, dana)
        report = bad_debt.bad_debt(start=YEAR_START, end=YEAR_END)
        assert report["ledger"]["available"] is True
        assert report["ledger"]["net"] == "3940.0000"
        assert report["ledger"]["agrees"] is True
        assert report["ledger"]["account_code"] is not None
        assert not [
            problem
            for problem in report["problems"]
            if problem["code"] == "ledger_disagrees_with_payments"
        ]


def test_the_ledger_nets_a_reversal_from_the_other_side(brazos, dana):
    """The approval DEBITS the write-off account and the CS-25 mirror CREDITS
    it, so the books reach 0.00 the same way the rows do."""
    with tenant_ctx(brazos):
        _account, approved = _written_off(
            brazos,
            dana,
            account_no="A-20040",
            amount=Decimal("948.20"),
            reason=WRITE_OFF_REASON_UNCOLLECTIBLE,
        )
        writeoffs.reverse_write_off(
            dana,
            write_off_id=approved.write_off_id,
            reversed_on=SEPTEMBER,
            posted_at=SEPTEMBER_AT,
            reason="raised against the wrong account",
        )
        report = bad_debt.bad_debt(start=YEAR_START, end=YEAR_END)
        assert report["net"] == "0.0000"
        assert report["ledger"]["net"] == "0.0000"
        assert report["ledger"]["agrees"] is True


def test_the_two_totals_are_computed_twice_and_agree(brazos, dana):
    """`counted_row_totals` asks the DATABASE for the same two figures the
    report sums in Python, so a refactor of the loop cannot quietly change what
    a board is shown."""
    with tenant_ctx(brazos):
        _cs26_shape(brazos, dana)
        report = bad_debt.bad_debt(start=YEAR_START, end=YEAR_END)
        counted = bad_debt.counted_row_totals(start=YEAR_START, end=YEAR_END)
        assert counted["net"] == report["net"]
        assert counted["written_off"] == report["written_off"]
        assert counted["reversed"] == report["reversed"]
        assert counted["count"] == report["count"]


# ══════════════════════════════════════════════════════════════════════════
# 5 · WHAT IT DOES NOT ANSWER, SAID OUT LOUD
# ══════════════════════════════════════════════════════════════════════════


def test_the_by_service_gap_is_reported_by_name(brazos, dana):
    """CS-26's *why* names *"by reason, by month and by SERVICE"* and its
    deliverable names only the first two. Nothing attributes a write-off across
    the services an account takes, so the gap is raised as an open question
    rather than approximated — the prime directive's *implement to the boundary,
    name the gap*."""
    with tenant_ctx(brazos):
        _cs26_shape(brazos, dana)
        report = bad_debt.bad_debt(start=YEAR_START, end=YEAR_END)
        codes = {problem["code"] for problem in report["problems"]}
        assert "bad_debt_not_split_by_service" in codes
        assert "excludes_billing_small_balance_write_offs" in codes
        by_service = [
            problem
            for problem in report["problems"]
            if problem["code"] == "bad_debt_not_split_by_service"
        ]
        assert bad_debt.OQ_BY_SERVICE in by_service[0]["detail"]


# ══════════════════════════════════════════════════════════════════════════
# 6 · THE ROWS BEHIND A BAR
# ══════════════════════════════════════════════════════════════════════════


def test_the_account_list_matches_the_bar_it_came_from(brazos, dana):
    with tenant_ctx(brazos):
        _cs26_shape(brazos, dana)
        listed = bad_debt.bad_debt_accounts(
            start=YEAR_START, end=YEAR_END, reason=WRITE_OFF_REASON_UNCOLLECTIBLE
        )
        assert len(listed["rows"]) == 1
        assert listed["rows"][0]["amount"] == "2840.0000"
        assert listed["rows"][0]["account_no"] == "A-20001"
        assert listed["rows"][0]["currency"] == "USD"
        assert listed["rows"][0]["reverses_write_off_id"] is None
        with pytest.raises(PaymentRuleError):
            bad_debt.bad_debt_accounts(start=YEAR_START, end=YEAR_END, reason="agency_referral")


def test_a_reversing_row_is_distinguishable_in_the_account_list(brazos, dana):
    """A report that could not tell a correction from a second write-off would
    double-count the very rows it nets."""
    with tenant_ctx(brazos):
        _account, approved = _written_off(
            brazos,
            dana,
            account_no="A-20050",
            amount=Decimal("948.20"),
            reason=WRITE_OFF_REASON_UNCOLLECTIBLE,
        )
        writeoffs.reverse_write_off(
            dana,
            write_off_id=approved.write_off_id,
            reversed_on=SEPTEMBER,
            posted_at=SEPTEMBER_AT,
            reason="raised against the wrong account",
        )
        listed = bad_debt.bad_debt_accounts(start=YEAR_START, end=YEAR_END)
        assert len(listed["rows"]) == 2
        reversing = [row for row in listed["rows"] if row["status"] == WRITE_OFF_REVERSED]
        assert len(reversing) == 1
        assert reversing[0]["reverses_write_off_id"] == approved.write_off_id
        assert reversing[0]["reversal_reason"] == "raised against the wrong account"


# ══════════════════════════════════════════════════════════════════════════
# 7 · THE DOOR
# ══════════════════════════════════════════════════════════════════════════


def test_the_report_over_http(brazos, dana):
    with tenant_ctx(brazos):
        _cs26_shape(brazos, dana)
    response = api_call(
        writeoffs_api.bad_debt_report,
        "get",
        user=dana.user,
        role="system_admin",
        tenant=brazos,
        query={"f.start": YEAR_START.isoformat(), "f.end": YEAR_END.isoformat()},
    )
    assert response.status_code == 200
    assert response.data["net"] == "3940.0000"
    assert response.data["by_reason"][0]["share_percent"] == SHARE_UNCOLLECTIBLE


def test_the_report_refuses_a_missing_window(brazos, dana):
    """No default and no clock: a default of *"this year"* computed on the
    server would be a clock read in the server's timezone (G6)."""
    refused = api_call(
        writeoffs_api.bad_debt_report,
        "get",
        user=dana.user,
        role="system_admin",
        tenant=brazos,
        query={"f.start": YEAR_START.isoformat()},
    )
    assert refused.status_code == 422, refused.data


def test_an_executive_may_read_the_report(brazos, dana):
    """A4 Reports: Staff/Clerk read, Executive full. It writes nothing."""
    from tests.test_us_met_helpers import staff_actor

    with tenant_ctx(brazos):
        _cs26_shape(brazos, dana)
        exec_actor = staff_actor(brazos, "executive", "eve@brazosbendutilities.test")
    response = api_call(
        writeoffs_api.bad_debt_report,
        "get",
        user=exec_actor.user,
        role="executive",
        tenant=brazos,
        query={"f.start": YEAR_START.isoformat(), "f.end": YEAR_END.isoformat()},
    )
    assert response.status_code == 200
    assert response.data["net"] == "3940.0000"
