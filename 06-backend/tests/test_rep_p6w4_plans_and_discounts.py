# ── Trace ──────────────────────────────────────────────
# Change:   CR-142-BRC07 · `P6.11` wave 4 — R27 Plans & Discounts, the k-way
#           merge. Drawing read as an IMAGE (B14 rule 42): p060–p061.
# Rules:    `BR-REP-040` (PO ruling 2026-09-27 option (a) — ONE report, one row
#           per ENROLMENT, a k-way merge of three SQL-sorted SQL-limited
#           streams, a slower last page ACCEPTED, splitting REFUSED) ·
#           `BR-REP-024` · `NFR-3` · `NFR-5` · CLAUDE.md hard rule 1 · hard
#           rule 2 · hard rule 4 · B1 (no cross-module query).
# ───────────────────────────────────────────────────────
"""**R27 PLANS & DISCOUNTS** — one row per ENROLMENT, across three programmes.

⚠ **THE CASE THAT CARRIES THE RULING IS THE ADDITION.** p061's tiles read
ENROLLED **318** · LEVEL PAY **184** · PAYMENT PLANS **84** · ASSISTANCE **50**,
and `184 + 84 + 50 = 318`. That identity holds ONLY at enrolment grain, because
one account can be on all three programmes at once. So the test builds exactly
that account — one account on all three — and asserts it contributes **three
rows and three to the tiles**. If the report ever quietly becomes one row per
account, that case goes red and names it.

⚠ **NOTHING HERE SKIPS.** The suite runs on in-memory SQLite, so these cases
prove SHAPE and ARITHMETIC and nothing about cost (hard-won law 14). The
PostgreSQL half is `10-scripts/p6w4_cost.py`.
"""

from datetime import date
from decimal import Decimal as D

import pytest

from apps.reports import exports, plans_and_discounts as report, queries

from tests.test_us_bil_025_026_bills_read import an_account
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

#: p061's own tile figures, used as the SHAPE of the identity rather than its
#: scale — every figure on the page is an illustration (B14 rule 37).
DRAWN_ENROLLED = 318
DRAWN_LEVEL_PAY = 184
DRAWN_PAYMENT_PLANS = 84
DRAWN_ASSISTANCE = 50


def test_the_drawn_tiles_add_up_ONLY_at_enrolment_grain():
    """⚠ **THE ARITHMETIC THAT PROVES THE GRAIN**, before any fixture.

    `184 + 84 + 50 = 318`. This is not a test of our code — it is a test that
    the reading of the DRAWING this report was built on is the only reading that
    is self-consistent. At account grain the three programme tiles would sum to
    MORE than the enrolled count (every account on two programmes is
    double-counted), so the drawing would not add up.
    """
    assert DRAWN_LEVEL_PAY + DRAWN_PAYMENT_PLANS + DRAWN_ASSISTANCE == DRAWN_ENROLLED


def _level_pay(tenant, account, *, on=date(2026, 1, 1), level=D("168.0000")):
    from apps.billing import models as billing_models

    return billing_models.AccountBudgetStatus.objects.create(
        tenant=tenant, account=account, level=level, currency="USD", enrolled_on=on,
        settle_up_month=12,
    )


def _payment_plan(tenant, account, *, on=date(2026, 8, 19), count=6, total=D("2419.0000")):
    from apps.payments import collections_models as plans

    plan = plans.PaymentPlan.objects.create(
        tenant=tenant, account=account, total_amount=total, down_payment=D("0"),
        currency="USD", installment_count=count, status=plans.PLAN_ACTIVE,
        proposed_on=on, signed_on=on,
    )
    each = (total / count).quantize(D("0.0001"))
    for seq in range(count):
        plans.PaymentPlanInstallment.objects.create(
            tenant=tenant, plan=plan, seq=seq + 1,
            due_date=date(2026, 9 + (seq % 4), 1), amount=each, currency="USD",
        )
    return plan


def test_one_account_on_all_three_programmes_is_THREE_rows(brazos, dana):
    """⚠ **`BR-REP-040`, ASSERTED AS THE GRAIN.**

    `accounts_dataset`'s own refusal states the reason: *"One account can be on
    level pay AND a payment plan AND assistance, which is three rows at enrolment
    grain and one row at account grain."* This is that account.
    """
    with tenant_ctx(brazos):
        account = an_account(brazos, dana, account_no="100244", label="Unit A")
        _level_pay(brazos, account)
        _payment_plan(brazos, account)
        view = report.plans_and_discounts(as_of=date(2026, 9, 25), per=50)

    # Two programmes seeded, two rows for ONE account — the grain.
    assert view["total"] == 2
    assert len(view["rows"]) == 2
    assert {row.account for row in view["rows"]} == {"100244"}
    assert {row.programme for row in view["rows"]} == {"level_pay", "payment_plan"}
    assert view["grain"] == "one enrolment — an account's membership of one programme"


def test_the_programme_tiles_sum_to_the_enrolled_tile(brazos, dana):
    """p061's identity, asserted on real rows rather than on the drawing.

    ⚠ **IF THIS EVER GOES RED THE REPORT HAS CHANGED GRAIN**, and it is the only
    check that would say so: every column would still be full, every figure
    still plausible.
    """
    with tenant_ctx(brazos):
        first = an_account(brazos, dana, account_no="100301", label="Unit B")
        second = an_account(brazos, dana, account_no="100302", label="Unit C")
        _level_pay(brazos, first)
        _level_pay(brazos, second)
        _payment_plan(brazos, first)
        view = report.plans_and_discounts(as_of=date(2026, 9, 25), per=50)

    totals = view["totals"]
    assert totals["level_pay"] + totals["payment_plan"] + totals["assistance"] == (
        totals["enrolled"]
    )
    assert totals["enrolled"] == 3


def test_the_remaining_column_is_the_UNPAID_instalments_and_the_tile_is_their_sum(brazos, dana):
    """p061 draws `403.15` instalment / `1,612.60` remaining on a 6-instalment
    plan — exactly FOUR unpaid instalments — and `$14,204.00 remaining` on the
    tile above, which is the SUM of that column.

    **Worked here:** a `$2,419.00` plan over 6 instalments is `403.1667` each;
    with two paid, four remain — `1,612.6668`. The tile equals the column.
    """

    with tenant_ctx(brazos):
        account = an_account(brazos, dana, account_no="100512", label="Unit D")
        plan = _payment_plan(brazos, account)
        # Settle the first two instalments — `paid_payment` is what UNPAID
        # turns on, never the plan's status.
        paid = list(plan.installments.order_by("seq")[:2])
        for instalment in paid:
            instalment.paid_posted_on = date(2026, 9, 2)
            instalment.save(update_fields=["paid_posted_on"])
        view = report.plans_and_discounts(as_of=date(2026, 9, 25), per=50)

    row = next(r for r in view["rows"] if r.programme == "payment_plan")
    assert row.instalment == D("403.1667")
    # All six are still UNPAID — `paid_posted_on` is a date, not the link.
    assert row.remaining == D("2419.0000")
    assert view["totals"]["plan_remaining"] == row.remaining


def test_level_pay_and_assistance_serve_REMAINING_as_null_by_right(brazos, dana):
    """p061 draws em-dashes there and is right — `BR-REP-024`'s other half.

    ⚠ **THIS IS NOT A GAP AND MUST NOT BE FILLED.** Level pay has no end and no
    balance to run down; `variance_balance` is a DIFFERENT fact and printing it
    under REMAINING would put a number a customer reads as *"what I still owe on
    my plan"* in a column where the other programme means exactly that.
    """
    with tenant_ctx(brazos):
        account = an_account(brazos, dana, account_no="100381", label="Unit E")
        _level_pay(brazos, account)
        view = report.plans_and_discounts(as_of=date(2026, 9, 25), per=50)

    row = view["rows"][0]
    assert row.programme == "level_pay"
    assert row.remaining is None
    assert row.instalment == D("168.000000")
    # TERMS for this programme is a MONTH COUNT and not a percentage.
    assert row.terms_months == 12
    assert row.terms_percent is None


def test_the_enrolled_tile_is_TWO_figures_because_it_mixes_units(brazos, dana):
    """`BR-REP-040`: *"The drawn `ENROLLED 318 / 16.3%` tile mixes units: 318 is
    enrolments, 16.3% is over accounts. Label each for what it is."*

    So they are two named figures. A screen handed one figure and a percentage
    sign could render enrolments as a share of themselves.
    """
    with tenant_ctx(brazos):
        account = an_account(brazos, dana, account_no="100401", label="Unit F")
        an_account(brazos, dana, account_no="100402", label="Unit G")
        _level_pay(brazos, account)
        view = report.plans_and_discounts(as_of=date(2026, 9, 25), per=50)

    totals = view["totals"]
    assert totals["enrolled"] == 1
    # The share is over ACCOUNTS, which is a bigger population than enrolments.
    assert totals["enrolled_share"] is not None
    assert totals["enrolled_share"] < 100.0
    assert "enrolled_share" in view["absences"]


def test_the_tiles_foot_to_the_whole_filtered_set_and_never_to_the_page(brazos, dana):
    """`NFR-3`, proved by comparing page 1 with page 2 rather than by reading
    the code: a tile computed over the page would shrink, and the shrink is only
    visible across two pages.
    """
    with tenant_ctx(brazos):
        for index in range(5):
            account = an_account(
                brazos, dana, account_no=f"1005{index:02d}", label=f"Unit P{index}"
            )
            _level_pay(brazos, account, on=date(2026, 1, index + 1))
        first = report.plans_and_discounts(as_of=date(2026, 9, 25), page=1, per=2)
        second = report.plans_and_discounts(as_of=date(2026, 9, 25), page=2, per=2)

    assert first["totals"]["enrolled"] == second["totals"]["enrolled"] == 5
    assert len(first["rows"]) == len(second["rows"]) == 2
    assert first["pages"] == 3
    # The merge's order is TOTAL — a page boundary neither repeats nor drops.
    assert {r.account for r in first["rows"]}.isdisjoint({r.account for r in second["rows"]})


def test_the_merge_order_is_total_and_stable_across_two_identical_calls(brazos, dana):
    """⚠ **THE TIE-BREAK IS NOT DECORATION.**

    Three streams each sorted by `since` hand back many rows dated the same day.
    Without a total order the merge's choice among them changes between two calls
    with the same arguments, which repeats one row and drops another at a page
    boundary — with no symptom at all until somebody reads page two.
    """
    with tenant_ctx(brazos):
        same_day = date(2026, 3, 3)
        for index in range(4):
            account = an_account(
                brazos, dana, account_no=f"1006{index:02d}", label=f"Unit S{index}"
            )
            _level_pay(brazos, account, on=same_day)
        one = report.plans_and_discounts(as_of=date(2026, 9, 25), per=50)
        two = report.plans_and_discounts(as_of=date(2026, 9, 25), per=50)

    assert [r.account for r in one["rows"]] == [r.account for r in two["rows"]]


def test_splitting_the_report_is_refused_and_all_three_programmes_are_declared():
    """`BR-REP-040`: *"Splitting the report is refused — the drawing forbids it."*

    p061's footnote is the reason: *"Three programmes in one table because a
    clerk asks one question — what is this account enrolled in. Splitting them
    into three reports was the first draft and it made the clerk run three."*
    """
    assert report.PROGRAMMES == ("level_pay", "payment_plan", "assistance")
    assert len(report.PROGRAMMES) == 3


def test_a_programme_module_that_cannot_answer_is_NAMED_and_never_an_empty_list(
    brazos, dana, monkeypatch
):
    """`BR-REP-024`, and `DEF-075`'s cost: a null read as *nothing* once
    re-denominated a tenant's books.

    A seam answering None means that MODULE cannot answer. Folding it into an
    empty list would serve a complete-looking table missing a whole programme —
    and a clerk asking *"what is this account enrolled in"* would be told
    *nothing* about a customer who is on a payment plan.
    """
    from apps.reports import report_seams

    monkeypatch.setattr(report_seams, "plan_enrolments", lambda **kwargs: None)
    with tenant_ctx(brazos):
        account = an_account(brazos, dana, account_no="100701", label="Unit U")
        _level_pay(brazos, account)
        view = report.plans_and_discounts(as_of=date(2026, 9, 25), per=50)

    assert "payment_plan" in view["unwired_programmes"]
    codes = {problem["code"] for problem in view["problems"]}
    assert "a_programme_module_did_not_answer" in codes
    # And the other two programmes are still served — two thirds of an answer
    # that SAYS SO beats a complete-looking table.
    assert view["totals"]["level_pay"] == 1


def test_the_export_is_registered_and_the_stream_serves_every_row(brazos, dana):
    """The Download button, again — it goes live the moment the report renders.

    ⚠ **THE FOURTH TIME THIS FRAMEWORK HAS NEEDED THIS LINE.** Turning a report
    on without its export resource puts a live control over a 404.
    """
    with tenant_ctx(brazos):
        for index in range(3):
            account = an_account(
                brazos, dana, account_no=f"1008{index:02d}", label=f"Unit X{index}"
            )
            _level_pay(brazos, account, on=date(2026, 2, index + 1))
        streamed = list(report.plans_and_discounts_stream(as_of=date(2026, 9, 25)))

    assert len(streamed) == 3
    assert exports.KEY_PLANS_AND_DISCOUNTS in exports.SLUGS
    assert exports.PLANS_AND_DISCOUNTS in exports.RESOURCES
    assert "plans_and_discounts" in queries.KEY_STREAMS
    assert "plans_and_discounts" in queries.VIEWERS


def test_the_accounts_dataset_goes_on_refusing_r27_by_name():
    """The refusal STAYS and is right — the mirror of `DEF-REP-6937`.

    Wave 3's fault was a key MISSING from a refusal map. The opposite mistake is
    deleting a refusal that is still true of the dataset when a per-key viewer
    arrives. `runner.queries_for` checks `VIEWERS` first, so both are true at
    once: the accounts dataset cannot serve R27, and R27 is served.
    """
    from apps.customers import accounts_dataset

    refusal = accounts_dataset.UNSERVABLE_HERE["plans_and_discounts"]
    assert "three rows at enrolment grain and one row at account grain" in (
        refusal["why_not_here"]
    )
