# ── Trace ──────────────────────────────────────────────
# Story:    US-PAY-013 (S34 Outstandings: AR high→low, ageing KPIs, bulk
#           actions)   Screens: S34
# Rules:    BR-PAY-029 (AR high→low) · BR-PAY-032 (days late = today − the
#           OLDEST UNPAID invoice's due date) · BR-PAY-021 (money POSTED by the
#           due date is not outstanding) · BR-CUS-015 (`accounts.balance` is a
#           CACHE — the list does not read it) · BR-PAY-015 (no autopay retry)
# ───────────────────────────────────────────────────────
"""S34's own fixture set, and the two things the list must never do.

The prototype's rows, verbatim (US-PAY-013 §4): *"A-11340 Northwind $8,240.00
(45d) · A-11024 Ridge Coffee $1,842.10 (30d) · A-10802 Novak $948.20 (91d,
90+)"*. The order, the buckets and the KPI tie-out are all asserted on those
three.

RED-PROVED FIRST (hard-won law 7): with the final `rows.sort(...,
reverse=True)` removed, TC-1 fails — the list comes back in whatever order the
invoice query produced, and the largest debtor is not first. Transcript in the
lane report.
"""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from apps.payments import outstandings, services

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_pay_001_record_payment import an_issued_bill
from tests.test_w3_billing_models import an_account

pytestmark = pytest.mark.django_db

AS_OF = date(2026, 8, 15)

#: US-PAY-013 §4, verbatim. Due dates chosen so `AS_OF − due` reproduces the
#: story's own days-late figures exactly (45 / 30 / 91).
FIXTURES = (
    ("A-11340", Decimal("8240.00"), date(2026, 7, 1), 45, "31-60"),
    ("A-11024", Decimal("1842.10"), date(2026, 7, 16), 30, "1-30"),
    ("A-10802", Decimal("948.20"), date(2026, 5, 16), 91, "90+"),
)


def _debtors(brazos, dana):
    made = []
    for index, (account_no, total, due_on, _days, _bucket) in enumerate(FIXTURES):
        account = an_account(dana, brazos, account_no=account_no)
        an_issued_bill(
            brazos,
            account,
            number=f"BL-2607-0184{index:02d}",
            total=total,
            issued_on=due_on,
            due_date=due_on,
        )
        made.append(account)
    return made


def test_us_pay_013_tc1__rows_are_balance_high_to_low_and_the_kpis_tie(brazos, dana):
    """TC-1 — *"A-11340 $8,240.00 first, then A-11024 $1,842.10, A-10802 …"*.

    And the second half of TC-1, which is the one a dashboard usually gets
    wrong: *"KPI strip bucket totals tie to the rows exactly"*. They do here by
    construction — the tiles are a fold over the same rows, not a second query.
    """
    with tenant_ctx(brazos):
        _debtors(brazos, dana)
        view = outstandings.outstandings(as_of=AS_OF)

        assert [row.account_no for row in view.rows] == ["A-11340", "A-11024", "A-10802"]
        assert view.total_owed == Decimal("8240.00") + Decimal("1842.10") + Decimal("948.20")
        bucketed = sum((Decimal(tile["amount"]) for tile in view.ageing()), Decimal("0"))
        assert bucketed == view.total_owed


def test_us_pay_013_tc1b__days_late_and_buckets_are_the_storys_own(brazos, dana):
    """BR-PAY-032's anchor, on the story's own three ages: 45 · 30 · 91."""
    with tenant_ctx(brazos):
        _debtors(brazos, dana)
        view = outstandings.outstandings(as_of=AS_OF)
        by_account = {row.account_no: row for row in view.rows}
        for account_no, _total, _due, days, bucket in FIXTURES:
            assert by_account[account_no].days_late == days
            assert by_account[account_no].bucket == bucket


def test_us_pay_013_tc2__the_age_band_filter_narrows_and_re_ties(brazos, dana):
    """TC-2 — *"Only matching rows (A-10802 in 90+); counts re-tie"*."""
    with tenant_ctx(brazos):
        _debtors(brazos, dana)
        view = outstandings.outstandings(as_of=AS_OF, bucket="90+")
        assert [row.account_no for row in view.rows] == ["A-10802"]
        assert view.total_owed == Decimal("948.20")


def test_us_pay_013_tc3__a_bill_paid_by_the_due_date_leaves_the_list(brazos, dana):
    """TC-3 — *"Row gone — posted_at ≤ due date makes it not outstanding"*.

    No special case produces this and that is the point: the payment wrote its
    allocation rows, so the bill's computed balance is 0.00 and it is not an
    outstanding bill. A list built on `accounts.balance` (a cache, BR-CUS-015)
    would still be chasing this customer.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-11042")
        an_issued_bill(
            brazos,
            account,
            number="BL-2608-018410",
            total=Decimal("292.87"),
            issued_on=date(2026, 8, 1),
            due_date=date(2026, 8, 22),
        )
        services.record_payment(
            dana,
            account_id=account.pk,
            amount=Decimal("292.87"),
            posted_at=datetime(2026, 8, 22, 16, 5, tzinfo=UTC),
            cleared_at=datetime(2026, 8, 25, 9, 0, tzinfo=UTC),
            idempotency_reference=uuid.uuid4(),
        )
        view = outstandings.outstandings(as_of=date(2026, 8, 23))
        assert view.rows == ()


def test_us_pay_013_no_dso_is_invented(brazos, dana):
    """The DSO tile is served NULL with its reason (BR-REP-011 is reports')."""
    with tenant_ctx(brazos):
        _debtors(brazos, dana)
        payload = outstandings.outstandings(as_of=AS_OF).as_dict()
        assert payload["totals"]["dso_days"] is None
        assert "dso_not_computed_here" in {p["code"] for p in payload["problems"]}


def test_us_pay_013_tc7__isolation_rows_never_cross(brazos, dana, lonestar):
    """TC-7 — *"Lone Star Ridge rows only"*.

    The read is tenant-scoped through billing's own published queryset; from the
    other tenant's session the Brazos Bend debtors simply do not exist.
    """
    with tenant_ctx(brazos):
        _debtors(brazos, dana)
        assert len(outstandings.outstandings(as_of=AS_OF).rows) == 3
    with tenant_ctx(lonestar):
        assert outstandings.outstandings(as_of=AS_OF).rows == ()


def test_us_pay_013_def_099__every_money_body_carries_its_currency(brazos, dana):
    """**DEF-099** — an amount with no currency is HALF of CLAUDE.md rule 2.

    Money is `NUMERIC(18,6)` **and** `CHAR(3)`. Both endpoints served every
    figure with no code at all, so the screen had to fetch a third endpoint
    purely to discover what money it was rendering — and the alternative it
    rejected, assuming `USD`, prints a confidently wrong symbol on a tenant
    that does not bill in dollars.

    Asserted on BOTH bodies in one test because they shared one defect: a guard
    on only one of them would let the other drift straight back.

    RED-PROVED: with the `"currency"` member removed from either handler this
    fails with `KeyError: 'currency'` on that body. It could not have been
    caught before, because 35 endpoint tests passed while both bodies were
    silent about their own currency.
    """
    from tests.test_us_ten_helpers import api_call
    from tests.test_us_met_helpers import FakeUser
    from apps.payments import api as payments_api

    with tenant_ctx(brazos):
        _debtors(brazos, dana)

    for view, name in (
        (payments_api.outstandings, "outstandings"),
        (payments_api.payments_summary, "payments/summary"),
    ):
        response = api_call(
            view,
            "get",
            user=FakeUser(),
            role="billing_clerk",
            tenant=brazos,
            query={"as_of": AS_OF.isoformat()},
        )
        assert response.status_code == 200, f"{name} -> {response.status_code}"
        body = response.data
        assert "currency" in body, (
            f"{name} serves money with no CHAR(3) code. Rule 2 is a PAIR, and a body of "
            "bare numbers forces every reader to guess or go and ask."
        )
        assert body["currency"] == "USD"
        assert len(body["currency"]) == 3
# ── CR-059 CS-38 · task 25 — the two halves of the chased figure ───────────
def test_cs38__the_row_carries_what_the_bills_say_and_what_credit_came_off():
    """`balance` is NET of the account's credit; both halves reach the wire.

    ⛔ **THEY DID NOT UNTIL 2026-09-02, AND THAT IS THE WHOLE DEFECT.**
    `billing_seam.outstanding_positions` has carried `gross_balance` and
    `credit_applied` since CS-38 landed and says in its own docstring why — *"a
    clerk asked why a notice says 222.30 when the bill says 247.30 needs the two
    halves and not a subtraction they have to guess at"* — and this read model
    took `position.balance` and dropped both on the floor. So a **25.00**
    goodwill concession, posted to the books and **written to the customer**,
    moved the figure on S34 and was invisible on it: the row read **222.30**
    with nothing to tell it from a bill of 222.30.

    ❄️ GT-6's figures, and none of them moves here.
    """
    row = outstandings.OutstandingRow(
        account_id="acc-1",
        account_no="A-10802",
        customer_name="Ajinkya Kulkarni",
        balance=Decimal("222.30"),
        days_late=6,
        bucket=outstandings.BUCKET_CURRENT,
        open_bills=1,
        gross_balance=Decimal("247.30"),
        credit_applied=Decimal("25.00"),
    )
    body = row.as_dict()
    # Four decimals like every other money figure on this body (hard rule 2).
    assert body["balance"] == "222.3000"
    assert body["gross_balance"] == "247.3000"
    assert body["credit_applied"] == "25.0000"


def test_cs38__an_unstated_gross_is_null_and_never_the_net():
    """UNKNOWN IS NOT THE NET. A deployment whose seam predates CS-38 states no
    gross, and echoing `balance` back would invent *"the bills came to exactly
    this"* out of *"we cannot say what the bills came to"* — DEF-127's shape on
    the one figure a collection notice is built from.

    `credit_applied` is `0.0000` rather than null on such a row because zero
    credit IS the answer: nothing came off, and the screen draws nothing.
    """
    row = outstandings.OutstandingRow(
        account_id="acc-2",
        account_no="A-10803",
        customer_name=None,
        balance=Decimal("100.00"),
        days_late=None,
        bucket=outstandings.BUCKET_CURRENT,
        open_bills=1,
    )
    body = row.as_dict()
    assert body["gross_balance"] is None
    assert body["gross_balance"] != body["balance"]
    assert body["credit_applied"] == "0.0000"
