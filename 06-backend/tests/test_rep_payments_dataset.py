# ── Trace ──────────────────────────────────────────────
# Change:   CR-142-BRC07 · the `payments` dataset query (lane DS-PAYMENTS).
#           Drawings read as IMAGES (B14 rule 42): R1 p051–p052 · R2 p052 ·
#           R3 p052–p053 · R9/R10 p053 · R11/R12 p054 · R14 p055 · R19 p057 ·
#           R20 p058 · §7.2/§7.2.2 p083–p086 · §7.5/§7.6 p087.
# Rules:    NFR-3 (pagination in SQL) · NFR-5 (no hard caps) · BR-REP-001 (a
#           money report names its basis) · BR-REP-014 (collection framings
#           count BILL-purpose payments only) · BR-REP-024 (never a 0 where a
#           figure is not derivable) · BR-PAY-012 (purpose) · BR-PAY-021 (both
#           dates) · CLAUDE.md hard rule 2 (money is a Decimal, never a float)
#           · hard rule 4 (this path writes nothing)
# ───────────────────────────────────────────────────────
"""THE `payments` DATASET — one row per PAYMENT, and the grain that was wrong.

⚠ **EVERY CASE ASSERTS A KNOWN NON-ZERO COUNT.** A query returning nothing
reads as *"no error"* — the commonest false pass in this repository — so no
case here is satisfied by an empty answer, and the one case that asserts a
ZERO (a page past the end) sits beside a positive one **in the same fixture**,
so an empty fixture fails the positive case before the zero can pass.

⚠ **NOTHING HERE SKIPS.** A `pytest.skip` that fires when a fixture lacks
something is a false pass — a sibling's `cycle` case skipped silently and its
file reported green over the one assertion that mattered. Every fixture below
CREATES what it needs.

⚠ **AND THE SUITE RUNS ON IN-MEMORY SQLITE** (`config/settings/test.py`
hardcodes it and ignores `DATABASE_URL`), so these cases prove the SHAPE and
the ARITHMETIC and cannot prove anything about LIMIT/OFFSET cost, the query
plan or RLS. That is hard-won law 14; the PostgreSQL half is
`10-scripts/ds_payments_dataset_cost.py` and its figures are in the lane report.
"""

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from apps.payments import models as payment_models
from apps.payments import payments_dataset as dataset
from apps.reports import datasets

from tests.test_us_bil_025_026_bills_read import an_account
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_rep_canned_reports import a_cleared_payment, a_method

pytestmark = pytest.mark.django_db

UTC = timezone.utc

SEP = {"start": date(2026, 9, 1), "end": date(2026, 9, 30)}

#: Five payments, chosen so every assertion names a NUMBER rather than a shape.
#: Four are BILL-purpose and one is a DEPOSIT, which is the whole point of the
#: grain finding: a deposit has NO `allocations` row, so an allocation-grain
#: dataset would serve four rows and a total of 448.55 for a day on which the
#: utility took 598.55 in five payments.
BILL_AMOUNTS = (Decimal("169.52"), Decimal("120.40"), Decimal("84.00"), Decimal("74.63"))
DEPOSIT_AMOUNT = Decimal("150.00")
BILL_TOTAL = Decimal("448.55")
GRAND_TOTAL = Decimal("598.55")
PAYMENTS = 5


def _five(tenant, actor):
    """Four bill payments and one deposit, all cleared inside September.

    Written through the ORM rather than `services.record_payment`, for the
    reason `test_us_rep_canned_reports.a_cleared_payment` already records: this
    file asserts the READ MODEL, and dragging the ledger posting service in
    would make a reporting failure indistinguishable from a posting failure.
    """
    account = an_account(tenant, actor, account_no="100244", contact_name="Ruiz, Marisol")
    cash = a_method(tenant, "cash", "Cash")
    cheque = a_method(tenant, "check", "Cheque")
    for index, amount in enumerate(BILL_AMOUNTS):
        a_cleared_payment(
            tenant,
            account,
            amount=amount,
            method=cash if index % 2 == 0 else cheque,
            cleared_on=date(2026, 9, 8 + index),
            purpose=payment_models.PURPOSE_BILL,
        )
    a_cleared_payment(
        tenant,
        account,
        amount=DEPOSIT_AMOUNT,
        method=cash,
        cleared_on=date(2026, 9, 12),
        purpose=payment_models.PURPOSE_DEPOSIT,
    )
    return account


# ── the grain, and the money an allocation grain would have dropped ─────────
def test_the_deposit_is_a_row_because_the_grain_is_one_payment(brazos, dana):
    """Five rows and 598.55 — not four rows and 448.55.

    ⚠ **THIS IS THE FINDING, ASSERTED RATHER THAN DESCRIBED.**
    `apps/reports/datasets.py` declared this dataset's grain as *"one payment
    allocation"*, and `apps/payments/services.py` writes NO `allocations` row
    for a payment whose purpose does not allocate (`if not linkage.allocates:`
    — a deposit, a prepay and a plan-down all take that branch). So an
    allocation-grain query serves four of these five rows and a smaller day,
    and a smaller day does not read as wrong. It reads as a quieter Tuesday.
    """
    with tenant_ctx(brazos):
        _five(brazos, dana)
        answer = dataset.payments_dataset(**SEP)

    assert answer["total"] == PAYMENTS, "five payments cleared in September"
    assert len(answer["rows"]) == PAYMENTS
    assert answer["totals"]["amount"] == GRAND_TOTAL, (
        "the total is every payment, deposits included — an allocation grain would say "
        f"{BILL_TOTAL}"
    )
    purposes = {row.purpose for row in answer["rows"]}
    assert payment_models.PURPOSE_DEPOSIT in purposes, (
        "the deposit must be a ROW, not only a number inside the total"
    )
    assert answer["grain"] == "one payment"


def test_bill_purpose_is_published_apart_from_the_total(brazos, dana):
    """BR-REP-014, structural: 448.55 beside 598.55, four beside five.

    A caller computing a collection percentage reaches for the bill-purpose
    figure and CANNOT reach a total with the deposit folded into it.
    """
    with tenant_ctx(brazos):
        _five(brazos, dana)
        totals = dataset.payments_dataset(**SEP)["totals"]

    assert totals["bill_purpose_amount"] == BILL_TOTAL
    assert totals["bill_purpose_payments"] == 4
    assert totals["amount"] == GRAND_TOTAL
    assert totals["bill_purpose_amount"] != totals["amount"], (
        "BR-REP-014 is only structural while the two figures actually differ in the fixture"
    )


# ── money is a Decimal, hard rule 2 ─────────────────────────────────────────
def test_every_money_figure_leaves_as_a_decimal(brazos, dana):
    """Never a float and never cents — hard rule 2, asserted by TYPE."""
    with tenant_ctx(brazos):
        _five(brazos, dana)
        answer = dataset.payments_dataset(**SEP)

    assert answer["rows"], "the fixture must produce rows for this case to mean anything"
    for row in answer["rows"]:
        assert isinstance(row.amount, Decimal), f"{row.payment_no} left as {type(row.amount)}"
        assert row.currency == "USD" and len(row.currency) == 3  # CHAR(3)
    assert isinstance(answer["totals"]["amount"], Decimal)


# ── NFR-3: the page is cut in SQL and the last page is not the slow one ─────
def test_a_page_is_cut_and_the_totals_still_foot_to_the_whole_set(brazos, dana):
    """Two rows on the page, five in `total`, and the total is still 598.55.

    ⚠ **THE TILES FOOT TO THE DEBT, NOT TO THE PAGE.** That is the premise
    `/outstandings`'s withdrawn docstring got backwards: `totals` is a SQL
    aggregate over the whole FILTERED set whether a page is cut or not.
    """
    with tenant_ctx(brazos):
        _five(brazos, dana)
        first = dataset.payments_dataset(**SEP, per=2, page=1)
        last = dataset.payments_dataset(**SEP, per=2, page=3)

    assert len(first["rows"]) == 2 and first["pages"] == 3 and first["total"] == PAYMENTS
    assert first["totals"]["amount"] == GRAND_TOTAL, "page 1's tiles show the whole set"
    assert len(last["rows"]) == 1, "five rows at two per page leaves one on page three"
    assert last["totals"]["amount"] == GRAND_TOTAL, "the last page's tiles show the same set"
    seen = {row.payment_id for row in first["rows"]} | {row.payment_id for row in last["rows"]}
    assert len(seen) == 3, "a page must not repeat a row it already served"


def test_a_page_past_the_end_clamps_rather_than_erroring(brazos, dana):
    """BR-SHL-011: a list URL never 4xx-es over its params.

    ⚠ **THE ONE ZERO-ADJACENT ASSERTION IN THIS FILE, AND IT SITS BESIDE A
    POSITIVE ONE IN THE SAME FIXTURE** — `page=99` clamps onto the last page
    and serves the row that is really there, so an empty fixture fails this
    case instead of passing it.
    """
    with tenant_ctx(brazos):
        _five(brazos, dana)
        answer = dataset.payments_dataset(**SEP, per=2, page=99)

    assert answer["page"] == 3, "99 clamps to the last page, it does not 404 and does not empty"
    assert len(answer["rows"]) == 1, "and the last page still has its row"


def test_the_sort_is_honoured_and_reverses(brazos, dana):
    """A sort the query does not honour would be a live caret over a dead control."""
    with tenant_ctx(brazos):
        _five(brazos, dana)
        asc = dataset.payments_dataset(**SEP, sort="amount", direction="asc")
        desc = dataset.payments_dataset(**SEP, sort="amount", direction="desc")

    assert len(asc["rows"]) == PAYMENTS
    amounts = [row.amount for row in asc["rows"]]
    assert amounts == sorted(amounts), "asc must actually ascend"
    assert [row.amount for row in desc["rows"]] == sorted(amounts, reverse=True)
    assert asc["rows"][0].amount == Decimal("74.63"), "the smallest payment leads ascending"


# ── the export: a separate function with no page to inherit ─────────────────
def test_the_export_takes_no_page_and_no_per(brazos, dana):
    """`payments_dataset_stream` yields EVERY row and has no argument to cut one.

    ⚠ **THIS IS THE DEFECT THAT NEARLY SHIPPED ON THE BILLING REGISTER**: when
    it started paging, its export silently inherited the screen's fifty rows
    and produced a valid-looking file of 50 from a 38,000-row report. A flag
    would have had the same bug; a missing parameter cannot — so the absence is
    asserted on the SIGNATURE, not only on the row count.
    """
    import inspect

    parameters = inspect.signature(dataset.payments_dataset_stream).parameters
    assert "page" not in parameters, "an export with a `page` can inherit a screen's page"
    assert "per" not in parameters, "an export with a `per` can inherit a screen's page size"

    with tenant_ctx(brazos):
        _five(brazos, dana)
        streamed = list(dataset.payments_dataset_stream(**SEP))

    assert len(streamed) == PAYMENTS, "the stream serves every row, not a page of them"
    assert sum(row.amount for row in streamed) == GRAND_TOTAL


# ── R1's four group-bys — the drawing's own warning ─────────────────────────
def test_all_four_groupings_the_drawing_declares_are_served(brazos, dana):
    """p052, verbatim: *"Group by switches this between method, teller, purpose
    and day. **Four reports, one row.**"*

    `apps/payments/reporting.payments_by_method` groups by METHOD and by
    nothing else, and `teller` is a declared column of this dataset with no
    source anywhere in that function. All four are asserted here, each by a
    number.
    """
    with tenant_ctx(brazos):
        _five(brazos, dana)
        by_method = dataset.payment_groups(group_by="method", **SEP)
        by_purpose = dataset.payment_groups(group_by="purpose", **SEP)
        by_day = dataset.payment_groups(group_by="day", **SEP)
        by_teller = dataset.payment_groups(group_by="teller", **SEP)

    assert len(by_method["rows"]) == 2, "cash and cheque"
    assert len(by_purpose["rows"]) == 2, "bill and deposit"
    # ⚠ FIVE, not four. The four bill payments clear on the 8th, 9th, 10th and
    # 11th and the deposit clears on the 12th — five distinct days. This case
    # was written asserting four and the assertion is what found the miscount,
    # which is the only reason to spell a count out rather than derive it.
    assert len(by_day["rows"]) == 5, "the 8th, 9th, 10th, 11th and the deposit's 12th"
    assert len(by_teller["rows"]) == 1, "one group: every fixture payment predates tills"
    for answer in (by_method, by_purpose, by_day, by_teller):
        assert answer["totals"]["amount"] == GRAND_TOTAL, (
            "a grouping must not lose or duplicate money — Σ groups == Σ payments"
        )
        assert sum(row.count for row in answer["rows"]) == PAYMENTS


def test_share_is_recomputed_and_never_averaged(brazos, dana):
    """§7.2.2: *"% share — non-additive — must be recomputed from its
    components, never averaged."*

    The deposit is 150.00 of 598.55, which is 25.06%. Asserted as a number.
    """
    with tenant_ctx(brazos):
        _five(brazos, dana)
        by_purpose = dataset.payment_groups(group_by="purpose", **SEP)

    shares = {row.key: row.share_pct for row in by_purpose["rows"]}
    assert shares[payment_models.PURPOSE_DEPOSIT] is not None
    assert round(shares[payment_models.PURPOSE_DEPOSIT], 2) == Decimal("25.06"), (
        "150.00 / 598.55 = 25.06% — recomputed here, never stored and never folded"
    )
    assert round(sum(shares.values()), 2) == Decimal("100.00")


def test_an_unknown_grouping_is_refused_by_name(brazos, dana):
    """Not silently defaulted to method: a grouping nobody serves must say so."""
    with tenant_ctx(brazos):
        _five(brazos, dana)
        with pytest.raises(ValueError) as refusal:
            dataset.payment_groups(group_by="route", **SEP)
    assert "route" in str(refusal.value) and "method" in str(refusal.value)


# ── BR-REP-024: a named gap, never a silent zero ────────────────────────────
def test_the_ageing_columns_are_named_as_a_different_grain_not_served_as_zero(brazos, dana):
    """The eight semi-additive columns are ABSENT with a reason, not 0.00.

    ⚠ A balance summed across time is the canonical wrong answer §7.2.2 opens
    with. Serving `current = 0.00` on a payment row would make a footer appear
    and the footer would be meaningless.
    """
    with tenant_ctx(brazos):
        _five(brazos, dana)
        answer = dataset.payments_dataset(**SEP)

    codes = {problem["code"] for problem in answer["problems"]}
    assert "a_balance_as_at_a_date_is_not_a_property_of_a_payment" in codes
    row = answer["rows"][0]
    for column in ("current", "d1_30", "d31_60", "d61_90", "d90_plus", "deposits_held"):
        assert not hasattr(row, column), (
            f"{column} is a balance as at a date — its grain is one ACCOUNT, and serving it "
            "here as a zero would produce a footing total nobody asked for"
        )


def test_a_payment_posted_here_and_cleared_later_is_counted_here(brazos, dana):
    """`DEF-PAY-10321` (PO ruling 2026-10-21) — the POSTING date decides.

    Posted 30 September, cleared 2 October: it was absent from a
    clearing-basis September until the ruling; it is September's now, and the
    retired *"posted in this window, cleared outside it"* problem is not served.
    """
    with tenant_ctx(brazos):
        account = _five(brazos, dana)
        cash = a_method(brazos, "cash", "Cash")
        payment_models.Payment.objects.create(
            tenant=brazos,
            account=account,
            method=cash,
            amount=Decimal("500.00"),
            currency="USD",
            status=payment_models.PAYMENT_CLEARED,
            purpose=payment_models.PURPOSE_BILL,
            posted_at=datetime(2026, 9, 30, 10, 0, tzinfo=UTC),
            cleared_at=datetime(2026, 10, 2, 10, 0, tzinfo=UTC),
        )
        answer = dataset.payments_dataset(**SEP)
        october = dataset.payments_dataset(start=date(2026, 10, 1), end=date(2026, 10, 31))

    assert answer["total"] == PAYMENTS + 1, "the late-clearing payment is September's"
    assert october["total"] == 0
    codes = {problem["code"] for problem in answer["problems"]}
    assert "payments_posted_in_this_window_cleared_outside_it" not in codes


def test_def_pay_10321__the_14_oct_card_payment_is_in_the_14_oct_window(brazos, dana):
    """The PO's worked figure, 2026-10-21: *"a card payment taken 14 Oct and
    reconciled 16 Oct"* → it appears in the 14 Oct report.

    $40.00 is in 14 Oct and not 16 Oct, before reconciliation (`posted`, no
    clearing date) and after it (`cleared`, 16 Oct) — in the page, the totals,
    the stream and the day grouping. A cancelled $25.00 is never counted.
    """
    oct_14 = {"start": date(2026, 10, 14), "end": date(2026, 10, 14)}
    oct_16 = {"start": date(2026, 10, 16), "end": date(2026, 10, 16)}
    with tenant_ctx(brazos):
        account = _five(brazos, dana)
        card = a_method(brazos, "card", "Card")
        taken = datetime(2026, 10, 14, 15, 0, tzinfo=UTC)
        payment = payment_models.Payment.objects.create(
            tenant=brazos,
            account=account,
            method=card,
            amount=Decimal("40.00"),
            currency="USD",
            status=payment_models.PAYMENT_POSTED,
            purpose=payment_models.PURPOSE_BILL,
            posted_at=taken,
        )
        payment_models.Payment.objects.create(
            tenant=brazos,
            account=account,
            method=card,
            amount=Decimal("25.00"),
            currency="USD",
            status=payment_models.PAYMENT_CANCELLED,
            purpose=payment_models.PURPOSE_BILL,
            posted_at=taken,
        )

        def check():
            day = dataset.payments_dataset(**oct_14, group_by=("day",))
            assert day["total"] == 1
            assert day["totals"]["amount"] == Decimal("40.00")
            assert [row.payment_id for row in day["rows"]] == [str(payment.pk)]
            assert [g["measures"]["amount"] for g in day["groups"]] == [Decimal("40.00")]
            assert [r.payment_id for r in dataset.payments_dataset_stream(**oct_14)] == [
                str(payment.pk)
            ]
            grouped = dataset.payment_groups(group_by="method", **oct_14)
            assert grouped["totals"]["amount"] == Decimal("40.00")
            assert dataset.payments_dataset(**oct_16)["total"] == 0

        check()
        payment_models.Payment.objects.filter(pk=payment.pk).update(
            status=payment_models.PAYMENT_CLEARED,
            cleared_at=datetime(2026, 10, 16, 11, 0, tzinfo=UTC),
        )
        check()


def test_the_basis_is_named_on_every_answer(brazos, dana):
    """BR-REP-001: an unlabeled money render is a defect by contract. The
    POSTING date since 2026-10-21 (`DEF-PAY-10321`); it was `clearing`."""
    with tenant_ctx(brazos):
        _five(brazos, dana)
        assert dataset.payments_dataset(**SEP)["basis"] == "posting"
        assert dataset.payment_groups(group_by="method", **SEP)["basis"] == "posting"


# ── the declaration and the query may not drift ─────────────────────────────
def test_the_registry_and_this_query_agree_about_paging_and_sorting(brazos, dana):
    """`P2.12` reads the FIELD; this reads both and fails when they disagree.

    ⚠ **A DATASET ONCE DECLARED `paginates=False` ABOUT A READ MODEL THAT HAD
    NEVER BEEN WRITTEN** and a Phase 2 task went green on it. A declaration is
    a claim until a test finds the code that honours it, so this case calls the
    query rather than trusting the flag.
    """
    with tenant_ctx(brazos):
        _five(brazos, dana)
        paged = dataset.payments_dataset(**SEP, per=2, page=1)

    assert datasets.PAYMENTS.paginates is True
    assert len(paged["rows"]) == 2 and paged["pages"] == 3, (
        "the flag says this dataset pages, so the query must actually cut a page"
    )


def test_this_module_writes_nothing(brazos, dana):
    """Hard rules 4, 5 and 7 — asserted on the SOURCE, because a read that
    wrote would pass every other case in this file."""
    import inspect

    source = inspect.getsource(dataset)
    for forbidden in (".save(", ".delete(", ".create(", ".update(", ".bulk_create("):
        assert forbidden not in source, (
            f"{forbidden} in a payments READ — hard rule 4 makes `payments` append-only and "
            "`apps/payments/amendments.py` is the ONE endpoint that may touch it"
        )


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-142-BRC07 · the `payments` dataset query
# generated: 2026-09-27 by lane DS-PAYMENTS
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
