"""`S148`'s read — the money table, the master split, and the routes.

⚠ **TC-2 IS THE ONE THAT MATTERS AND IT IS WRITTEN FROM A REAL DEFECT.** The
first draft of `_paid_since` added the reconnection fee to `outstanding_at_cut`,
which ALREADY CONTAINS IT — so on a case where nobody had paid a cent it reported
**$75.00 paid**. A receipt for a payment that never happened, on the screen whose
entire job is to state what is owed. It was found by reading the live payload in
a browser, not by a test, which is why there is a test now.

⚠ **WHAT A FALSE PASS WOULD LOOK LIKE HERE, ASKED BEFORE TRUSTING ANY OF IT**
(hard-won law 7, habit 2). The dangerous shape is a test that builds its own
figures and asserts its own arithmetic — it would pass whatever
`reconnect_read` did, because both sides would be the same expression written
twice. So every case below asserts against a figure that is **stated as a
literal**, taken from the case the fixture actually writes, and the footing case
asserts the RELATION between the served lines rather than recomputing them.
"""

from __future__ import annotations

from decimal import Decimal

from django.urls import resolve

from apps.customers import reconnect_read


class _Case:
    """The two columns the money table reads, and nothing else."""

    def __init__(self, at_cut, cut_on="2026-09-20", disposition="held"):
        self.outstanding_at_cut = at_cut
        self.cut_on = cut_on
        self.deposit_disposition = disposition


FEE = {"stored": "75.0000", "display": "75.00"}


def test_paid_since_is_zero_when_nothing_has_been_paid():
    """`DSC-26-0005`: recorded $139.80 at the cut, $139.80 owed now, $0.00 paid.

    ⛔ **THE FIRST DRAFT ANSWERED $75.00 HERE.** `outstanding_at_cut` already
    contains the fee — the column's own docstring says so — so adding it again
    invented a payment.
    """
    line = reconnect_read._paid_since(
        _Case(Decimal("139.8000")), balance=Decimal("139.8000"), fee=FEE
    )
    assert line["amount"]["display"] == "0.00"


def test_paid_since_reports_what_actually_arrived():
    """$139.80 recorded, $64.80 owed now → **$75.00** paid since the cut."""
    line = reconnect_read._paid_since(
        _Case(Decimal("139.8000")), balance=Decimal("64.8000"), fee=FEE
    )
    assert line["amount"]["display"] == "75.00"


def test_paid_since_is_an_absence_and_never_a_zero_when_the_ledger_cannot_be_read():
    """`DEF-127` — *"no payments"* and *"we could not tell"* are different cells."""
    line = reconnect_read._paid_since(_Case(Decimal("139.8000")), balance=None, fee=FEE)
    assert line["amount"] is None
    assert line["unavailable"]["code"] == "balance_unreadable"


def test_the_arrears_line_takes_the_fee_back_out():
    """The drawing shows arrears and fee as TWO lines, so the first is net of the second."""
    assert reconnect_read._at_cut_less_fee(_Case(Decimal("139.8000")), FEE) == Decimal("64.8000")


def test_the_arrears_line_refuses_to_split_when_the_fee_cannot_be_read():
    """Printing the whole recorded position beside a fee line would state it twice."""
    assert reconnect_read._at_cut_less_fee(_Case(Decimal("139.8000")), None) is None


def test_the_money_table_foots_against_the_ledger_and_is_not_summed_on_screen():
    """TC-1 — arrears + fee − paid since == still owed, on the served lines.

    ⚠ **IT ASSERTS THE RELATION AND RECOMPUTES NOTHING.** `still_owed` is
    `_balance_for`, read once (`DEF-CUS-6050`); this case exists to prove the
    lines a clerk reads add up to the figure that admits the customer back.
    """
    case = _Case(Decimal("139.8000"))
    arrears = reconnect_read._at_cut_less_fee(case, FEE)
    paid = Decimal(
        reconnect_read._paid_since(case, balance=Decimal("139.8000"), fee=FEE)["amount"]["stored"]
    )
    assert arrears + Decimal(FEE["stored"]) - paid == Decimal("139.8000")


def test_the_warning_is_absent_on_a_settled_account():
    """A sentence reading *$0.00 still owed* is a sentence with no reader."""
    assert reconnect_read._warning(Decimal("0")) is None
    assert reconnect_read._warning(None) is None


def test_the_warning_states_the_figure_when_money_is_owed():
    """`BR-CUS-1097` on screen — a figure and four words, and nothing else."""
    warning = reconnect_read._warning(Decimal("879.5000"))
    assert warning["code"] == "still_owed_you_may_continue"
    assert warning["amount"]["display"] == "879.50"


def test_the_live_refusal_is_reported_rather_than_hidden():
    """⛔ `not_settled` is against `BR-CUS-1097` (`DEF-CUS-6742`) and is SHOWN.

    A screen that hides a refusal the server will make offers a button that does
    not work, and hiding it is how a signed rule stays unbuilt while every screen
    looks finished.
    """
    refusal = reconnect_read._commit_refusal(
        {"blockers": ({"code": "not_settled", "br_ref": "`DSC-02.4`"},)}
    )
    assert refusal == {"code": "not_settled", "br_ref": "`DSC-02.4`"}


def test_no_refusal_is_reported_when_the_engine_would_accept():
    """The day `reconnect_blockers` drops the clause, this answers `None` itself."""
    assert reconnect_read._commit_refusal({"blockers": ()}) is None


def test_both_routes_resolve_through_config_urls():
    """TC-6's backend half — the include cannot be lost or reordered silently.

    ⚠ **RESOLVED THROUGH `config/urls.py`, NOT THROUGH THE MODULE'S OWN
    `urlpatterns`**, which is the same guarantee `test_disconnect_record_page.py`
    takes for the record: a module that declares a path nobody includes is a
    route that does not exist, and the module's own list cannot see that.

    ⚠ **IDENTITY, NOT `__name__`, AND THE FIRST DRAFT USED `__name__` AND WAS
    A CHECK THAT COULD NOT FAIL.** DRF's `@api_view` returns a wrapper called
    `view`, so EVERY route in this product answers `"view"` — the assertion
    could not tell two views apart at all, and it went red only because it
    compared `"view"` with the name I expected. Had I expected `"view"` it
    would have passed over any include, in any order. The record test one file
    over records the identical mistake; I made it again anyway, which is why
    running a new guard matters more than writing it (hard-won law 7).
    """
    from apps.customers import disconnect_record as dr

    assert resolve("/api/brazosbend/disconnects/dsc-26-0005/reconnect").func is (
        reconnect_read.reconnect_read
    )
    assert resolve("/api/brazosbend/disconnects/dsc-26-0005/reconnect/work-orders").func is (
        reconnect_read.reconnect_raise_work_order
    )
    # And the sibling keeps its own address: `disconnects/<ref>` must not be
    # swallowed by, nor swallow, the two-segment route beside it.
    assert resolve("/api/brazosbend/disconnects/dsc-26-0005").func is dr.disconnect_record
