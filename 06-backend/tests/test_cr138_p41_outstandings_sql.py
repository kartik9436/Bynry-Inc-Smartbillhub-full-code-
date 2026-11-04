# ── Trace ──────────────────────────────────────────────
# Change:  CR-138-BRC07 `P4.1` — page and sort `GET /outstandings` in SQL.
# Defect:  DEF-PAY-4221 — the `NFR-3` breach `CLAUDE.md` names by name:
#          *"Unpaginated ON PURPOSE … one row per DEBTOR at a utility under
#          3,000 connections"*, and it sorts in Python.
# Defect:  DEF-PAY-6255 — `outstanding_positions` ASSIGNED its `problems`
#          tuple where every other branch concatenates, so the negative-credit
#          sentence was erased by the undated-bill one.
# Rules:   `NFR-3` (universal server pagination) · `NFR-5` (no hard caps) ·
#          BR-PAY-029 (AR high→low) · BR-PAY-032 (days late) · BR-PAY-041
#          (a negative credit is a real debt) · BR-BIL-072 (❄️ "Level is due")
#          · US-PAY-013 TC-1 (the KPI strip ties to the rows) · CLAUDE.md
#          hard rule 1 (tenant scoping) · hard rule 2 (money is never a float).
# ───────────────────────────────────────────────────────
"""The debtor list is cut in SQL, and it still answers exactly what it did.

⚠ **THE ONLY TEST THAT MATTERS HERE IS THE EQUIVALENCE ONE, AND IT IS WHY
`outstanding_positions` IS STILL IN THE FILE.** A rewrite of a money read is
worth nothing if it is *plausible*; the old function is the specification, so
the new one is compared to it debtor by debtor and field by field on a seeded
tenant. That comparison is what caught the first draft of the credit leg
summing `payments` with NO filter at all — it passed a 2,030-row comparison
because the fixture it ran on happened to hold no `processing` payment and no
deposit (hard-won law 7: *ask what would make this check pass wrongly*), and
the fixture now holds one of every row whose treatment is a rule.

RED-PROVED FIRST (hard-won law 7), **through `pytest`, which is the harness
that will run these** — law 7's second half is that a red proof through the
wrong entry point is no proof of the thing that matters, and `run_gates` runs
GATES, not this file. An earlier draft of this line said `run_gates`' harness
and was simply naming the wrong tool:
  * with the SQL `ORDER BY` replaced by the old `rows.sort(...)`,
    `test_page_two_continues_page_one` fails — every page comes back holding
    the same fifty debtors.
  * with `credit_applied` dropped, `test_matches_the_unpaged_read` fails on
    the account carrying an overpayment.
  * with `DEF-PAY-6255`'s `problems = (…)` restored,
    `test_both_problems_travel_together` fails.
"""

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps.payments import billing_seam, models, outstandings

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_pay_001_record_payment import an_issued_bill
from tests.test_w3_billing_models import an_account

pytestmark = pytest.mark.django_db

AS_OF = date(2026, 9, 23)


def _debtor(brazos, dana, *, owed: str, days_late: int, suffix: str, due_date=...):
    """One account with one open bill of `owed`, `days_late` days past due."""
    due = AS_OF - timedelta(days=days_late) if due_date is ... else due_date
    account = an_account(dana, brazos, account_no=f"SQL-{suffix}")
    an_issued_bill(
        brazos,
        account,
        number=f"BL-CR138-{suffix}",
        total=Decimal(owed),
        issued_on=AS_OF - timedelta(days=max(days_late, 0) + 1),
        due_date=due,
    )
    return account


# ══════════════════════════════════════════════════════════════════════════
# TC-1 · THE SQL READ ANSWERS WHAT THE PYTHON READ ANSWERED
# ══════════════════════════════════════════════════════════════════════════


def test_matches_the_unpaged_read(brazos, dana):
    """Every debtor, every field — the old function IS the specification."""
    with tenant_ctx(brazos):
        for index, (owed, late) in enumerate(
            [("948.20", 91), ("1842.10", 30), ("8240.00", 45), ("12.00", 3)]
        ):
            _debtor(brazos, dana, owed=owed, days_late=late, suffix=str(index))

        old, _ = billing_seam.outstanding_positions()
        by_id = {str(row.account_id): row for row in old}

        seen: dict[str, billing_seam.OutstandingPosition] = {}
        page = 1
        while True:
            view = billing_seam.outstanding_positions_page(
                as_of=AS_OF, bands=outstandings.AGEING_BANDS, page=page, per=2
            )
            if not view.positions:
                break
            for row in view.positions:
                seen[str(row.account_id)] = row
            page += 1

        assert set(seen) == set(by_id), "the paged read lost or invented a debtor"
        for account_id, expected in by_id.items():
            got = seen[account_id]
            assert got.balance == expected.balance
            assert got.gross_balance == expected.gross_balance
            assert got.credit_applied == expected.credit_applied
            assert got.oldest_due_on == expected.oldest_due_on
            assert got.invoice_count == expected.invoice_count
            assert got.undated == expected.undated


def test_the_balance_is_a_decimal_and_never_a_float(brazos, dana):
    """Hard rule 2 — money does not become a binary fraction in SQL either."""
    with tenant_ctx(brazos):
        _debtor(brazos, dana, owed="948.20", days_late=91, suffix="money")
        view = billing_seam.outstanding_positions_page(as_of=AS_OF, bands=outstandings.AGEING_BANDS)
        for row in view.positions:
            assert isinstance(row.balance, Decimal)
            assert isinstance(row.gross_balance, Decimal)
            assert isinstance(row.credit_applied, Decimal)
        assert isinstance(view.total_owed, Decimal)


# ══════════════════════════════════════════════════════════════════════════
# TC-2 · `NFR-3` — THE PAGE IS CUT BY THE SERVER, AND IT MOVES
# ══════════════════════════════════════════════════════════════════════════


def test_page_two_continues_page_one(brazos, dana):
    """The page is a WINDOW, not a re-sort of the same rows.

    ⛔ The defect this is written for: a list sorted in Python after the rows
    are fetched serves the same fifty debtors on every page, and a clerk
    paging through 40,000 of them never reaches the second one.
    """
    with tenant_ctx(brazos):
        owed = ["500.00", "400.00", "300.00", "200.00", "100.00"]
        for index, amount in enumerate(owed):
            _debtor(brazos, dana, owed=amount, days_late=40, suffix=f"p{index}")

        first = outstandings.outstandings(as_of=AS_OF, page=1, per=2)
        second = outstandings.outstandings(as_of=AS_OF, page=2, per=2)
        third = outstandings.outstandings(as_of=AS_OF, page=3, per=2)

        assert [row.balance for row in first.rows] == [Decimal("500"), Decimal("400")]
        assert [row.balance for row in second.rows] == [Decimal("300"), Decimal("200")]
        assert [row.balance for row in third.rows] == [Decimal("100")]
        ids = [row.account_id for row in first.rows + second.rows + third.rows]
        assert len(set(ids)) == 5, "a debtor appeared on two pages"


def test_no_cap_anywhere(brazos, dana):
    """`NFR-5` — `per` is a page size and the list has no maximum.

    Asking for every debtor at once is a legal request and is answered; the
    count on the body is a COUNT and never a ceiling.
    """
    with tenant_ctx(brazos):
        for index in range(7):
            _debtor(brazos, dana, owed=f"{100 + index}.00", days_late=40, suffix=f"c{index}")
        view = outstandings.outstandings(as_of=AS_OF, page=1, per=1000)
        assert len(view.rows) == 7
        assert view.total_accounts == 7
        assert view.as_dict()["debtors_window"]["count"] == 7
        assert view.as_dict()["debtors_window"]["pages"] == 1


def test_no_page_asked_for_means_the_whole_filtered_list(brazos, dana):
    """`per=None` — the endpoint's own default until `DEF-PAY-6271` closes.

    ⚠ **THIS IS A CONTRACT CASE, NOT A CONVENIENCE ONE.** `GET /outstandings`
    pages only when the caller sends `page` or `per`, because screen 7·1
    declares ten sortable columns and a search this read cannot honour and a
    page cut underneath them is a search box that searches fifty rows of forty
    thousand. So *no page asked for* has to mean **every matching debtor**, and
    it has to keep meaning that until somebody deliberately changes it — which
    is what this case is for.

    ⚠ **AND `per` COMES BACK `null` RATHER THAN A NUMBER.** A page size the
    caller did not choose must not be reported as one they did; `pages` is 1
    because there is one body, and `count` is the debtor count either way.
    """
    with tenant_ctx(brazos):
        for index in range(7):
            _debtor(brazos, dana, owed=f"{100 + index}.00", days_late=40, suffix=f"w{index}")

        whole = outstandings.outstandings(as_of=AS_OF, per=None)
        assert len(whole.rows) == 7, "a caller that asked for no page got a page"
        body = whole.as_dict()
        assert body["debtors_window"]["per"] is None
        assert body["debtors_window"]["page"] == 1
        assert body["debtors_window"]["pages"] == 1
        assert body["debtors_window"]["count"] == 7
        # The tiles are the same tiles either way — they were never a fold
        # over the rows, so an unpaged body cannot make them agree by accident.
        paged = outstandings.outstandings(as_of=AS_OF, page=1, per=2)
        assert paged.as_dict()["ageing"] == body["ageing"]
        assert paged.total_owed == whole.total_owed


def test_an_out_of_range_page_clamps_and_says_which_page_it_served(brazos, dana):
    """BR-SHL-011 — *"invalid values fall back or clamp, NEVER error"*.

    ⚠ And the CLAMPED page is what comes back on the body. A client that
    overshoots and is told it is on page 9,999 of 2 has no way to recover
    except by guessing, and an empty body with a `count` of 2,030 reads
    exactly like a broken screen.
    """
    with tenant_ctx(brazos):
        for index in range(3):
            _debtor(brazos, dana, owed=f"{100 + index}.00", days_late=40, suffix=f"x{index}")

        over = outstandings.outstandings(as_of=AS_OF, page=9999, per=2)
        assert over.as_dict()["debtors_window"]["pages"] == 2
        assert over.as_dict()["debtors_window"]["page"] == 2
        assert len(over.rows) == 1

        for asked in (0, -5):
            low = outstandings.outstandings(as_of=AS_OF, page=asked, per=2)
            assert low.as_dict()["debtors_window"]["page"] == 1
            assert len(low.rows) == 2

        # An EMPTY list clamps to page 1 rather than to page 0.
        empty = outstandings.outstandings(as_of=AS_OF, bucket="current", page=7, per=2)
        assert empty.as_dict()["debtors_window"]["page"] == 1
        assert empty.as_dict()["debtors_window"]["pages"] == 1
        assert empty.rows == ()


def test_sorts_in_sql_and_the_module_does_not_sort():
    """BR-PAY-029's order is an `ORDER BY`, asserted by reading the source.

    ⚠ **A SOURCE ASSERTION, DELIBERATELY.** A behavioural test cannot tell an
    SQL `ORDER BY` from a Python `sort()` over one page — both come back in
    the right order — and the whole defect was a Python sort over a list the
    server had already materialised. `test_us_pay_013_outstandings.py` uses
    the same technique to assert this module reads no clock.
    """
    import inspect

    source = inspect.getsource(outstandings.outstandings)
    assert "rows.sort(" not in source
    assert ".sort(" not in source


def test_sort_and_direction_travel_to_sql(brazos, dana):
    with tenant_ctx(brazos):
        _debtor(brazos, dana, owed="100.00", days_late=5, suffix="s1")
        _debtor(brazos, dana, owed="900.00", days_late=95, suffix="s2")

        ascending = outstandings.outstandings(as_of=AS_OF, sort="balance", direction="asc")
        assert ascending.rows[0].balance == Decimal("100")

        by_age = outstandings.outstandings(as_of=AS_OF, sort="days_late", direction="desc")
        assert by_age.rows[0].days_late == 95


# ══════════════════════════════════════════════════════════════════════════
# TC-3 · US-PAY-013 TC-1 — THE TILES STILL TIE TO THE DEBT, NOT TO THE PAGE
# ══════════════════════════════════════════════════════════════════════════


def test_tiles_describe_the_whole_list_not_the_page(brazos, dana):
    """The argument that kept this list unpaginated, tested instead of assumed."""
    with tenant_ctx(brazos):
        for index, (owed, late) in enumerate(
            [("100.00", 95), ("200.00", 95), ("300.00", 40), ("400.00", 5)]
        ):
            _debtor(brazos, dana, owed=owed, days_late=late, suffix=f"t{index}")

        page = outstandings.outstandings(as_of=AS_OF, page=1, per=1)
        assert len(page.rows) == 1
        assert page.total_accounts == 4
        assert page.total_owed == Decimal("1000")

        tiles = {row["bucket"]: row for row in page.as_dict()["ageing"]}
        assert tiles["90+"]["amount"] == "300.0000"
        assert tiles["90+"]["accounts"] == 2
        assert tiles["31-60"]["accounts"] == 1
        assert tiles["1-30"]["accounts"] == 1
        assert sum(int(row["accounts"]) for row in page.as_dict()["ageing"]) == 4


def test_the_band_in_sql_agrees_with_bucket_for_on_every_boundary(brazos, dana):
    """The `CASE` and `bucket_for` are one rule expressed twice — they agree.

    Every boundary day of A2's four bands, plus the two `current` cases: a
    bill not yet due, and a bill with no due date at all (BR-PAY-032).
    """
    with tenant_ctx(brazos):
        days = [-1, 0, 1, 30, 31, 60, 61, 90, 91, 400]
        for index, late in enumerate(days):
            _debtor(brazos, dana, owed=f"{1000 + index}.00", days_late=late, suffix=f"b{index}")

        view = outstandings.outstandings(as_of=AS_OF, per=1000)
        counted: dict[str, int] = {}
        for row in view.rows:
            assert row.bucket == outstandings.bucket_for(row.days_late)
            counted[row.bucket] = counted.get(row.bucket, 0) + 1
        tiles = {row["bucket"]: int(row["accounts"]) for row in view.as_dict()["ageing"]}
        for bucket, expected in counted.items():
            assert tiles[bucket] == expected, f"tile {bucket} disagrees with the rows in it"


def test_a_bucket_filter_narrows_the_list_and_its_tiles(brazos, dana):
    with tenant_ctx(brazos):
        _debtor(brazos, dana, owed="100.00", days_late=95, suffix="f1")
        _debtor(brazos, dana, owed="200.00", days_late=10, suffix="f2")

        view = outstandings.outstandings(as_of=AS_OF, bucket="90+")
        assert [row.balance for row in view.rows] == [Decimal("100")]
        assert view.total_accounts == 1
        assert view.total_owed == Decimal("100")


# ══════════════════════════════════════════════════════════════════════════
# TC-4 · DEF-PAY-6255 — BOTH SENTENCES TRAVEL, AND ONE DOES NOT ERASE THE OTHER
# ══════════════════════════════════════════════════════════════════════════


def test_both_problems_travel_together(brazos, dana):
    """A tenant with an undated bill AND an account in negative credit.

    ⛔ `outstanding_positions` ASSIGNED its problems tuple in the undated
    branch, so on a tenant holding both — which is most of them — the
    `negative_credit_not_added_to_chase` sentence was silently dropped and
    BR-PAY-041's real debt went unmentioned on S34.
    """
    with tenant_ctx(brazos):
        _debtor(brazos, dana, owed="75.00", days_late=0, suffix="undated", due_date=None)

        owing = _debtor(brazos, dana, owed="500.00", days_late=40, suffix="neg")
        # A refund that has LEFT the utility with no payment behind it puts
        # this account's credit position below zero (BR-PAY-041's real debt).
        models.Refund.objects.create(
            id=uuid.uuid4(),
            tenant_id=brazos.id,
            account_id=owing.id,
            amount=Decimal("25.00"),
            currency="USD",
            status=models.REFUND_ISSUED,
        )

        _, old_problems = billing_seam.outstanding_positions()
        codes_old = {problem["code"] for problem in old_problems}
        view = outstandings.outstandings(as_of=AS_OF)
        codes_new = {problem["code"] for problem in view.problems}

        for code in ("unpaid_bill_without_due_date", "negative_credit_not_added_to_chase"):
            assert code in codes_old, f"{code} was erased from the unpaged read"
            assert code in codes_new, f"{code} was erased from the paged read"
