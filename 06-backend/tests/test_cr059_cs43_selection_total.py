# ── Trace ──────────────────────────────────────────────
# Change:   CR-059 · CS-43 — "Total a selection on the server". The register's
#           acceptance line, verbatim: *"four rows on page one and two on page
#           two show `6 selected · 3,918.44` — not a blank"*.
# Story:    US-PAY-004 (S33 Record payments)   Screens: S33
# Rules:    CLAUDE.md hard rule 2 (money is a decimal STRING beside its CHAR(3)
#           code; display 2) · hard rule 1 (tenant scoping) · CS-35's own
#           sentence (*"the day's cash total must EXCLUDE credits and
#           adjustments, or it will not tie to the drawer"*) · 11b G5
#           (pagination is mandatory on every list)
# Tests:    this file
# ───────────────────────────────────────────────────────
"""CS-43 — the selection total, on the SERVER, across pages.

WHY THIS IS A CHANGE AND NOT A TIDY-UP
======================================
The Payments list is paginated **in the database** (11b G5, 50 rows a page), and
until this lane the selection bar added up the rows the browser was holding. A
tick on page two is a tick on a row page one never had, so the moment a clerk
selected across a page boundary the bar reported the wrong figure or nothing at
all — **at exactly the point they were about to press Refund on six payments.**

CS-43 is also a **PREREQUISITE for CS-41's toolbar** and CR-059 §0d.2 says the
order is not optional: build the toolbar first and it reads blank the first time
anybody pages.

THE ACCEPTANCE LINE IS THE FIRST TEST IN THIS FILE
==================================================
`test_cs43__six_across_two_pages_total_3918_44` builds **six payments whose cash
sums to 3,918.44**, pages the list at 50 a page to prove the rows genuinely
straddle two pages, and asserts the endpoint answers `count 6` and
`3,918.44` — **not a blank**.

THE RED PROOF, RUN BEFORE ANY OF THIS WAS TRUSTED GREEN (hard-won law 7)
========================================================================
Each guard was driven RED before it was believed:

  * with `apps/payments/api.py`'s route removed, every case in this file fails
    with `django.urls.exceptions.NoReverseMatch` / a 404 from the live client;
  * with `selection_total`'s `cash = qs.filter(type=PAYMENT_TYPE_PAYMENT)` line
    changed to sum `qs`, `test_cs43__a_credit_is_counted_and_not_summed` fails
    with `AssertionError: assert '3993.440000' == '3918.440000'` — the 75.00
    credit added into the drawer figure, which is the exact defect DEF-3207
    recorded on the filter-wide total;
  * with the `len(currencies) > 1` branch removed,
    `test_cs43__mixed_currencies_state_no_figure` fails on a total that added
    USD to CAD.
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from django.urls import resolve

from apps.payments import api as payments_api
from apps.payments import models, selectors, services

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import FakeUser, tenant_ctx
from tests.test_us_pay_020_023_bank_rec import an_account_of
from tests.test_us_ten_helpers import api_call
from tests.test_w3_billing_models import an_account

pytestmark = pytest.mark.django_db

POSTED_AT = datetime(2026, 8, 20, 10, 0, tzinfo=UTC)

#: The register's own acceptance figure. Six rows, four on one page and two on
#: another, adding to this. Written down rather than recomputed, so a change to
#: the amounts below has to move this line deliberately.
ACCEPTANCE_TOTAL = Decimal("3918.44")
#: The six amounts. `1000.00 + 900.00 + 800.00 + 700.00 + 500.00 + 18.44`.
SIX_AMOUNTS = (
    Decimal("1000.00"),
    Decimal("900.00"),
    Decimal("800.00"),
    Decimal("700.00"),
    Decimal("500.00"),
    Decimal("18.44"),
)


def a_payment(actor, account, amount, *, payment_type=models.PAYMENT_TYPE_PAYMENT, **extra):
    """One CLEARED payment, through the real write path.

    Carrying no bills, so every one of them lands wholly as account credit —
    which is irrelevant to a total and keeps the fixture from depending on the
    allocation engine.
    """
    kwargs = dict(
        account_id=account.pk,
        amount=amount,
        posted_at=POSTED_AT,
        cleared_at=POSTED_AT,
        method_code="cash",
        idempotency_reference=uuid.uuid4(),
        payment_type=payment_type,
    )
    if payment_type != models.PAYMENT_TYPE_PAYMENT:
        kwargs["reason_code"] = "goodwill"
    kwargs.update(extra)
    return services.record_payment(actor, **kwargs)


# ══ THE ACCEPTANCE LINE ════════════════════════════════════════════════════


def test_cs43__six_across_two_pages_total_3918_44(brazos, dana):
    """**`6 selected · 3,918.44` — not a blank.** CS-43's own acceptance line.

    The rows genuinely straddle a page: 60 payments exist, the page size is 50,
    and the six ids handed to the endpoint are drawn from BOTH pages. A browser
    holding page one could see at most four of them.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        # 60 rows in all, and the six are placed so that FOUR land on page one
        # and TWO on page two. The list sorts `-posted_at, -created_at` and every
        # row here shares a posting date, so creation order decides: eight
        # fillers, then the six, then forty-six more fillers puts the six at
        # descending positions 46-51 — either side of the 50-row boundary.
        for index in range(8):
            a_payment(dana, account, Decimal("1.00"), memo=f"early-{index}")
        selected = [str(a_payment(dana, account, amount).payment_id) for amount in SIX_AMOUNTS]
        for index in range(46):
            a_payment(dana, account, Decimal("1.00"), memo=f"later-{index}")

        page_size = 50
        ordered = list(
            selectors.payment_queryset()
            .order_by("-posted_at", "-created_at")
            .values_list("id", flat=True)
        )
        page_one = {str(one) for one in ordered[:page_size]}
        on_page_one = [one for one in selected if one in page_one]
        assert len(on_page_one) == 4, (
            "CS-43's acceptance line is FOUR rows on page one and TWO on page two; a "
            "fixture that does not straddle the boundary proves nothing — "
            f"{len(on_page_one)} of the six are on page one of {len(ordered)} rows"
        )

        answer = selectors.selection_total(selected)

        assert answer["count"] == 6, "six rows were ticked and six were counted"
        assert answer["amount"] == "3918.440000", (
            "the STORED figure travels as its exact decimal string — CLAUDE.md rule 2, "
            "never a number and never cents"
        )
        assert answer["amount_display"] == "3918.44", (
            "CS-43's acceptance line renders `6 selected · 3,918.44`. The two-place "
            "figure is served BESIDE the stored one because the client may not do "
            "money arithmetic (DEF-364)"
        )
        assert Decimal(answer["amount"]) == ACCEPTANCE_TOTAL
        assert answer["currency"] == "USD", "half of hard rule 2 is the CHAR(3) code"
        assert answer["amount_unavailable"] is None


def test_cs43__the_route_is_mounted():
    """Hard-won law 2 — *built is not wired*, asserted on the RESOLVER.

    ⚠ **THIS CASE EXISTS BECAUSE THE ONE BELOW CANNOT DO ITS JOB.** `api_call`
    invokes the view FUNCTION directly, which is what makes it a fast unit-level
    harness — and it means every case using it passes with the route deleted
    from `urlpatterns`. That was PROVED, not assumed: removing
    `path("payments/selection-total", …)` and re-running left
    `test_cs43__the_endpoint_answers_it_over_http` **green**. A selector nothing
    serves is a total the bar can never show, which is exactly the shape CR-059
    was reopened over — code that exists and a screen that cannot do the thing.

    So the wiring is asserted where wiring lives: the URL resolves to THIS view,
    and the two literal `payments/…` paths beside it still resolve to theirs
    (a `payments/<id>` pattern added above them would swallow all three).
    """
    assert (
        resolve("/api/brazos/payments/selection-total").func
        is payments_api.payments_selection_total
    )
    assert resolve("/api/brazos/payments").func is payments_api.payments
    assert resolve("/api/brazos/payments/summary").func is payments_api.payments_summary


def test_cs43__the_endpoint_answers_it_over_http(brazos, dana):
    """The same figure through the view a screen actually calls.

    The body shape, the status code and the two money members, exercised through
    the DRF view rather than the selector — so a serialisation that dropped
    `amount_display` would fail here even though the selector is right.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        selected = [str(a_payment(dana, account, amount).payment_id) for amount in SIX_AMOUNTS]

    response = api_call(
        payments_api.payments_selection_total,
        "post",
        user=FakeUser(),
        role="billing_clerk",
        tenant=brazos,
        data={"payment_ids": selected},
    )
    assert response.status_code == 200, response.data
    assert response.data["count"] == 6
    assert response.data["amount_display"] == "3918.44"


# ══ WHAT IT MUST NOT DO ════════════════════════════════════════════════════


def test_cs43__an_empty_selection_is_not_zero(brazos, dana):
    """Nothing ticked answers `null` with a reason — never `0.00`.

    `$0.00` on that bar reads as *"these rows are worth nothing"*; the clerk has
    selected nothing at all. Two different sentences on a screen somebody is
    about to press Refund on.
    """
    with tenant_ctx(brazos):
        answer = selectors.selection_total([])
        assert answer["count"] == 0
        assert answer["amount"] is None
        assert answer["amount_display"] is None
        assert answer["amount_unavailable"] == "no_rows"


def test_cs43__a_credit_is_counted_and_not_summed(brazos, dana):
    """CS-35's rule, applied to a SELECTION: the cash figure excludes credits.

    Verbatim: *"the day's cash total must EXCLUDE credits and adjustments, or it
    will not tie to the drawer"*. So six cash payments plus one 75.00 goodwill
    credit is **seven selected · 3,918.44**, with one row named as excluded — the
    drawer holds 3,918.44 and the figure ties to it.

    **RED PROOF:** summing `qs` instead of `cash` fails here with
    `assert '3993.440000' == '3918.440000'`.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        selected = [str(a_payment(dana, account, amount).payment_id) for amount in SIX_AMOUNTS]
        credit = a_payment(
            dana,
            account,
            Decimal("75.00"),
            payment_type=models.PAYMENT_TYPE_CREDIT,
        )
        selected.append(str(credit.payment_id))

        answer = selectors.selection_total(selected)
        assert answer["count"] == 7, "every ticked row is COUNTED"
        assert answer["amount"] == "3918.440000", "and only the cash is SUMMED"
        assert (
            answer["excluded_count"] == 1
        ), "the screen states the absence rather than implying the total covers it"


def test_cs43__all_credits_state_no_cash_figure(brazos, dana):
    """A selection of nothing but credits states no cash — `no_cash_rows`.

    `0.00` would read as *"we took nothing"*; the fact is *"nothing here was
    cash"*. The same distinction `no_rows` draws one case up.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        credit = a_payment(dana, account, Decimal("75.00"), payment_type=models.PAYMENT_TYPE_CREDIT)
        answer = selectors.selection_total([str(credit.payment_id)])
        assert answer["count"] == 1
        assert answer["amount"] is None
        assert answer["amount_unavailable"] == "no_cash_rows"
        assert answer["excluded_count"] == 1


def test_cs43__mixed_currencies_state_no_figure(brazos, dana):
    """USD + CAD is not 200.00 of anything (CLAUDE.md rule 2's CHAR(3) half).

    **RED PROOF:** with the `len(currencies) > 1` branch removed this fails on a
    total that had added two currencies together.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        usd = a_payment(dana, account, Decimal("100.00"))
        # Written directly: `record_payment` takes the ACCOUNT's currency and an
        # account in a second currency is not a thing this product builds. What
        # is under test is the refusal, and the refusal reads the rows.
        cad = models.Payment.objects.create(
            tenant=brazos,
            account=account,
            payment_no="PMT-CAD-1",
            amount=Decimal("100.00"),
            currency="CAD",
            status=models.PAYMENT_CLEARED,
            posted_at=POSTED_AT,
            cleared_at=POSTED_AT,
        )
        answer = selectors.selection_total([str(usd.payment_id), str(cad.pk)])
        assert answer["count"] == 2
        assert answer["amount"] is None
        assert answer["amount_display"] is None
        assert answer["amount_unavailable"] == "mixed_currencies"


def test_cs43__another_tenants_id_is_not_totalled(brazos, lonestar, dana, erin):
    """CLAUDE.md hard rule 1 — a selection cannot reach across a tenant.

    And it does not FAIL over one, which is the other half: `requested` and
    `count` differ, the total covers what this tenant actually has, and the bar
    still shows a figure. A stale selection is a normal thing for a screen to
    hold; refusing the whole total over one id would leave it blank, which is
    the outcome CS-43 exists to remove.
    """
    with tenant_ctx(lonestar):
        # Lone Star Ridge is WATER-ONLY and metering correctly refuses an
        # electric unit there (VAL-005), so the service is a parameter.
        other_account = an_account_of(erin, lonestar, service="water")
        theirs = a_payment(erin, other_account, Decimal("500.00"))

    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        mine = a_payment(dana, account, Decimal("100.00"))
        answer = selectors.selection_total([str(mine.payment_id), str(theirs.payment_id)])
        assert answer["requested"] == 2
        assert answer["count"] == 1, "the other tenant's row is simply not there"
        assert answer["amount"] == "100.000000"
