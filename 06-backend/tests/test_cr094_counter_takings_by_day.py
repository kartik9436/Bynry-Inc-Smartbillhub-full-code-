# ── Trace ──────────────────────────────────────────────
# Change:   the drawer-reconciliation half of the counter-fee ruling of
#           2026-09-15. The money posts (lane H, already built and proved);
#           what nobody could do was ask the product *what did this counter
#           take TODAY, and how much of it was cash* — which is the one
#           question a clerk counting a till has to answer.
# Story:    US-LED-001 (source-event posting contracts)  Screens: the finance
#           books · `GET /counter-receipts`
# Rules:    CLAUDE.md hard rule 1 (tenant scoping) · hard rule 2 (4 dp stored,
#           2 displayed, CHAR(3), never float) · BR-PAY-025 (a deposit batch is
#           day × method — the vocabulary this read is deliberately built in) ·
#           BR-TEN-043 (a business date is never a server clock)
# Tests:    this file
# ───────────────────────────────────────────────────────
"""**THE DAY'S COUNTER TAKINGS, SPLIT BY TENDER — so a till can be counted.**

WHY THIS FILE EXISTS, AND IT IS A GAP RATHER THAN A DISAGREEMENT
---------------------------------------------------------------
The counter application fee has posted since 2026-09-15: taking `$25.00`
writes `DR 1010 Undeposited funds · CR 2400 Customer credit balances` and a
`counter_receipts` row. `tests/test_cr094_counter_receipt_posts.py` proves
that pair by account CODE and by figure and this file does not restate it.

**What was missing is the READ.** `GET /counter-receipts` filtered on `f.state`
and on nothing else, so the only questions it could answer were *everything
ever taken* and *everything still held*. A clerk balancing a drawer at 5pm
needs neither: they need **this day**, and they need the **cash** line on its
own, because a drawer holds cash and not cheques or card slips.

⚠ **AND THE MONEY IS NOT IN A DEPOSIT BATCH, WHICH IS WHY THE FIGURE HAS TO
COME FROM SOMEWHERE ELSE.** `BR-PAY-025` groups a deposit batch by day AND
method, and membership is written onto a `payments` row. A counter receipt is
deliberately NOT a `payments` row — there is no account yet — so it can never
be in a batch, and a clerk reconciling against batches alone would find the
counter cash missing every single day. That is a known, accepted cost of the
2026-09-15 design; this read is the thing that makes it survivable.

**`day × method` IS BORROWED ON PURPOSE.** It is the vocabulary the deposit
batch already uses, so the two figures a finance clerk holds side by side are
grouped the same way rather than nearly the same way.

WHAT WOULD MAKE THESE CHECKS PASS WRONGLY (law 7, habit 2)
----------------------------------------------------------
  * *"the day filter returns rows"* passes when the filter is IGNORED — every
    row comes back and the count is still non-zero. So each case asserts the
    row that must be **absent** as well as the one that must be present, and
    asserts the TOTAL, which a silently-ignored filter gets wrong.
  * *"by_method has a cash line"* passes when every tender is lumped under one
    key. So the cheque is asserted as its own line AND the cash figure is
    asserted to be less than the day's total.
  * *"it is tenant scoped"* passes trivially when the other tenant has no rows
    at all. So the second tenant is given a receipt on the SAME DAY for a
    DIFFERENT amount, and the first tenant's total is asserted to exclude it.

Every one of these was proved RED before it was trusted green; the failures are
quoted in the lane report.
"""

from __future__ import annotations

from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal

import pytest

from apps.ledger import models as ledger_models
from apps.payments import counter_receipt_models as cr_models
from apps.payments import counter_receipts
from apps.rating import models as rating_models

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    dana,
    lonestar,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

#: The PO's own figure for the application fee.
TWENTY_FIVE = Decimal("25.00")

#: Two counter days, an hour apart in the clock and a day apart in the book.
#: `12 May` is the ruling's own worked date; `13 May` is the day that must NOT
#: appear when a clerk asks for the 12th.
DAY_ONE = date(2026, 5, 12)
DAY_TWO = date(2026, 5, 13)
TAKEN_DAY_ONE = datetime(2026, 5, 12, 10, 30, tzinfo=dt_timezone.utc)
TAKEN_DAY_ONE_LATER = datetime(2026, 5, 12, 16, 5, tzinfo=dt_timezone.utc)
TAKEN_DAY_TWO = datetime(2026, 5, 13, 9, 15, tzinfo=dt_timezone.utc)


def _gl(tenant, code):
    return ledger_models.LedgerAccount.objects.get(tenant=tenant, code=code)


def _map_request_fee(tenant, account_code="4600"):
    """Give `CC-REQFEE` a `charges` row — setup, exactly as the sibling file's."""
    return rating_models.Charge.objects.create(
        tenant=tenant,
        code="CC-REQFEE",
        name="Application fee",
        charge_type="one_time",
        amount_rule="flat",
        amount=TWENTY_FIVE,
        gl_account_id=_gl(tenant, account_code).id,
    )


def _take(*, source_id, receipt_no, amount, taken_at, method_code="cash", source_ref=None):
    """Money over the counter, through payments' own door.

    Called directly rather than through `collect_fee` for one reason: the
    collection stamps `taken_at` from the clock, and a test about DAYS cannot
    be written against a clock it does not control (BR-TEN-043's own argument,
    one layer down). `test_payments_own_replay_guard_holds_when_called_directly`
    establishes that this door is a real caller and not a back way in.
    """
    return counter_receipts.record_counter_receipt(
        source_type="service_request",
        source_id=source_id,
        source_ref=source_ref or f"SR-26-{str(source_id)[-4:]}",
        receipt_no=receipt_no,
        amount=amount,
        currency="USD",
        method_code=method_code,
        taken_at=taken_at,
    )


def _totals(**kw):
    return counter_receipts.list_totals(counter_receipts.list_queryset(**kw))


# ═══════════════════════════════════════════════════════════════════════════
# 1 · THE DAY — the filter, and the row that must be ABSENT
# ═══════════════════════════════════════════════════════════════════════════
def test_the_day_filter_returns_only_that_days_takings(brazos, dana):
    """`$25.00` on the 12th and `$40.00` on the 13th → the 12th reads `$25.0000`.

    The absent row is asserted as well as the present one: a filter that is
    silently ignored returns BOTH and totals `$65.0000`, which is the false
    pass this case exists to refuse.
    """
    import uuid

    with tenant_ctx(brazos):
        _map_request_fee(brazos)
        first, second = uuid.uuid4(), uuid.uuid4()
        _take(source_id=first, receipt_no="RCP-26-4471", amount=TWENTY_FIVE, taken_at=TAKEN_DAY_ONE)
        _take(
            source_id=second,
            receipt_no="RCP-26-4472",
            amount=Decimal("40.00"),
            taken_at=TAKEN_DAY_TWO,
        )

        day_one = list(counter_receipts.list_queryset(taken_on=DAY_ONE))
        assert [row.receipt_no for row in day_one] == ["RCP-26-4471"]
        assert "RCP-26-4472" not in [row.receipt_no for row in day_one]
        assert _totals(taken_on=DAY_ONE)["taken"] == "25.0000"

        day_two = list(counter_receipts.list_queryset(taken_on=DAY_TWO))
        assert [row.receipt_no for row in day_two] == ["RCP-26-4472"]
        assert _totals(taken_on=DAY_TWO)["taken"] == "40.0000"

        # …and with no day asked for, nothing has changed: both are there.
        assert _totals()["taken"] == "65.0000"
        assert _totals()["count"] == 2


# ═══════════════════════════════════════════════════════════════════════════
# 2 · THE TENDER — a drawer holds CASH, and the figure has to say so
# ═══════════════════════════════════════════════════════════════════════════
def test_the_day_total_splits_by_tender_so_a_drawer_can_be_counted(brazos, dana):
    """`$25.00` cash and `$30.00` by cheque on one day → cash reads `$25.0000`.

    **This is the case the whole read exists for.** A clerk counts notes and
    coin; a cheque is not in the drawer. A `taken` of `$55.0000` with no split
    cannot be balanced against anything, so the day total carries `by_method`.

    ⚠ **THE LINE COMES BACK AS `check` AND NOT `cheque`, AND THAT IS CORRECT.**
    Two vocabularies meet here: the capture screen says `cheque`
    (`ServiceRequest.FEE_METHOD_CHEQUE`, British spelling) and the tenant's own
    seeded payment method is `check` (`BR-PAY-026`'s six seeds), with
    `FEE_METHOD_TO_TENDER` the whole of the translation. `by_method` groups by
    the **tender** the receipt actually resolved to, which is the right one of
    the two: it is what the deposit batch groups by, so a finance clerk holding
    both figures sees one word rather than two. **This test asserted `cheque`
    first and went red on real PostgreSQL**, which is how the distinction was
    found — it is written down here so the next reader does not "fix" it back.
    """
    import uuid

    with tenant_ctx(brazos):
        _map_request_fee(brazos)
        _take(
            source_id=uuid.uuid4(),
            receipt_no="RCP-26-4471",
            amount=TWENTY_FIVE,
            taken_at=TAKEN_DAY_ONE,
            method_code="cash",
        )
        _take(
            source_id=uuid.uuid4(),
            receipt_no="RCP-26-4473",
            amount=Decimal("30.00"),
            taken_at=TAKEN_DAY_ONE_LATER,
            method_code="cheque",
        )

        totals = _totals(taken_on=DAY_ONE)
        assert totals["taken"] == "55.0000"
        by_method = {row["method"]: row["taken"] for row in totals["by_method"]}
        assert by_method["cash"] == "25.0000"
        # `check`, the TENANT's tender code — see the docstring above.
        assert by_method["check"] == "30.0000"
        # The lump-everything-under-one-key false pass:
        assert Decimal(by_method["cash"]) < Decimal(totals["taken"])
        # Every tender line carries the currency beside it (hard rule 2).
        assert {row["currency"] for row in totals["by_method"]} == {"USD"}


# ═══════════════════════════════════════════════════════════════════════════
# 3 · THE TENANT — another utility's drawer is never in this one's figure
# ═══════════════════════════════════════════════════════════════════════════
def test_the_day_figure_is_tenant_scoped(brazos, lonestar, dana):
    """Hard rule 1, asserted where it would actually be lost.

    The second tenant is given a receipt on the SAME DAY for a DIFFERENT
    amount, so a read that dropped the tenant scope would total `$95.0000`
    rather than `$25.0000` — a figure a clerk would carry to a bank.
    """
    import uuid

    with tenant_ctx(brazos):
        _map_request_fee(brazos)
        _take(
            source_id=uuid.uuid4(),
            receipt_no="RCP-26-4471",
            amount=TWENTY_FIVE,
            taken_at=TAKEN_DAY_ONE,
        )
    with tenant_ctx(lonestar):
        _map_request_fee(lonestar)
        _take(
            source_id=uuid.uuid4(),
            receipt_no="RCP-26-9001",
            amount=Decimal("70.00"),
            taken_at=TAKEN_DAY_ONE,
        )

    with tenant_ctx(brazos):
        totals = _totals(taken_on=DAY_ONE)
        assert totals["taken"] == "25.0000"
        assert totals["count"] == 1
    with tenant_ctx(lonestar):
        assert _totals(taken_on=DAY_ONE)["taken"] == "70.0000"


# ═══════════════════════════════════════════════════════════════════════════
# 4 · THE TIE-OUT — the day's cash agrees with what the books were told
# ═══════════════════════════════════════════════════════════════════════════
def test_the_days_takings_agree_with_1010_on_the_trial_balance(brazos, dana):
    """The point of the figure: it must equal what collection debited.

    `$25.00` cash + `$30.00` cheque on the 12th → the day reads `$55.0000`, and
    `1010 Undeposited funds` has been debited `55.0000` by those same two
    collections. If the read and the ledger ever disagree, the clerk has one
    place to look — and this case is what makes that claim true rather than
    hopeful.
    """
    import uuid

    with tenant_ctx(brazos):
        _map_request_fee(brazos)
        for receipt_no, amount, method in (
            ("RCP-26-4471", TWENTY_FIVE, "cash"),
            ("RCP-26-4473", Decimal("30.00"), "cheque"),
        ):
            _take(
                source_id=uuid.uuid4(),
                receipt_no=receipt_no,
                amount=amount,
                taken_at=TAKEN_DAY_ONE,
                method_code=method,
            )

        day = _totals(taken_on=DAY_ONE)
        assert day["taken"] == "55.0000"

        debited = sum(
            line.amount
            for line in ledger_models.JournalLine.objects.filter(
                journal_entry__tenant=brazos,
                journal_entry__source_type="counter_receipt",
                ledger_account__code="1010",
                side="debit",
            )
        )
        assert debited == Decimal("55.0000")
        assert Decimal(day["taken"]) == debited


# ═══════════════════════════════════════════════════════════════════════════
# 5 · THE STATE FILTER STILL WORKS, AND THE TWO COMPOSE
# ═══════════════════════════════════════════════════════════════════════════
def test_the_day_and_the_state_filter_compose(brazos, dana):
    """A day filter must not quietly replace the filter that was already there.

    Both receipts are `held`, so `state='held'` on the 12th is still `$25.0000`
    and `state='earned'` on the 12th is empty — which is also the case that
    proves an empty result states NO money figure rather than a zero
    (`DEF-099`'s rule, which a new filter is exactly how you would break).
    """
    import uuid

    with tenant_ctx(brazos):
        _map_request_fee(brazos)
        _take(
            source_id=uuid.uuid4(),
            receipt_no="RCP-26-4471",
            amount=TWENTY_FIVE,
            taken_at=TAKEN_DAY_ONE,
        )
        _take(
            source_id=uuid.uuid4(),
            receipt_no="RCP-26-4472",
            amount=Decimal("40.00"),
            taken_at=TAKEN_DAY_TWO,
        )

        assert _totals(taken_on=DAY_ONE, state=cr_models.RECEIPT_HELD)["taken"] == "25.0000"

        empty = _totals(taken_on=DAY_ONE, state=cr_models.RECEIPT_EARNED)
        assert empty["count"] == 0
        assert empty["taken"] is None
        assert empty["currency"] is None
        assert empty["by_method"] == []
