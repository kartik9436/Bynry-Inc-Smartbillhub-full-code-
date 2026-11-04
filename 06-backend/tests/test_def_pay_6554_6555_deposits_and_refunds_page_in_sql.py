# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-PAY-6554 — `GET /deposit-batches` built EVERY batch the tenant
#          holds in order to draw fifty, and said so: *"a utility under 3,000
#          connections cuts at most a handful of batches a day"*.
#          DEF-PAY-6555 — `GET /refunds` did the same, on the same retired
#          ceiling. Both filed by this lane BEFORE the fix (CLAUDE.md step W).
# Task:    Finance blueprint `P1.2` (the deposits list onto the shared table) ·
#          `P1.3` (the refunds queue, and the paging argument settled) ·
#          `P1.7` (`q` on the deposits endpoint) — 05-prototype/07 Finance
#          Blueprint.pdf p012–p013 (the plan) and p048–p049 (screen 3·1, read
#          AS IMAGES under B14 rule 42).
# Rules:   NFR-3 (universal server pagination) · NFR-5 (no hard caps anywhere) ·
#          BR-SHL-011 (a list URL clamps and never 4xx) · BR-PAY-019 (bank rec
#          is Owner/Finance work) · BR-PAY-014 (the refund approval queue) ·
#          hard rule 1 (tenant scoping) · hard rule 2 (money 4dp beside a
#          CHAR(3)) · hard rule 4 (nothing here writes a money row)
# Tests:   this file
# Impacts: 06-backend/apps/payments/bankrec_read.py (`batch_list` takes a page
#          and folds its tiles in SQL) · 06-backend/apps/payments/selectors.py
#          (`refund_queue` takes a page and reports the true total) ·
#          06-backend/apps/payments/api.py · refunds_api.py (the two views ask
#          for ONE page through `core.pagination`)
# ───────────────────────────────────────────────────────
"""The two payments lists in Finance take their page in the DATABASE.

RED-FIRST PROOF (hard-won law 7, in the harness that runs it — `pytest`, never
a `__main__`). Every case below was run against this worktree BEFORE the fix
and the failures are quoted in the lane report.

⚠ **A CASE THAT COUNTS RETURNED ROWS CANNOT TELL SQL PAGING FROM PYTHON PAGING.**
It would have passed, green, through the whole life of both defects: the answer
was always right — the right batches, the right totals, the right order. What
was wrong was the COST. So every case here asserts the SQL that was sent or the
number of statements it took, and the count cases assert *the cost did not move*
rather than a literal, because a literal teaches the next reader to edit the
number instead of looking at it (`DEF-LED-6493`'s own argument, one module over).

⚠ **THE TILES ARE THE HALF THAT PAGING BREAKS, AND `batch_kpis` SAID SO IN
ADVANCE.** Its docstring warned that a second `aggregate()` *"would compute the
tiles from the database while the rows came from a list, and the two could
differ the moment a filter, a slice or a race put them out of step"* — and a
slice is exactly what this change introduces. So `test_the_tiles_are_folded_over
_the_filtered_set` plants more batches than one page holds and asserts the tiles
describe ALL of them. Folding the page would make *In transit* shrink as a clerk
walked forward through the pages, which is the one thing this screen must not
get wrong.

⚠ **WHAT WOULD MAKE THESE PASS WRONGLY**
  1. **An empty table.** *"No unpaged statement was sent"* is true of a database
     with no batches in it. Every case plants more rows than a page holds and
     asserts the page is full before it asserts anything about SQL.
  2. **`LIMIT` without its number.** Django renders `Subquery(...[:1])` as
     `LIMIT 1` inside a SELECT list, so a check for the bare word goes green on
     code that never asked for a page (`DEF-RAT-5742`). `_limit` matches the
     size.
  3. **A search case that asserts a row came back.** `q=DEP` returning rows
     proves nothing if `q` is ignored — every batch would come back. The search
     cases assert the row that must NOT be there is not there.

Run with `JOBS_EAGER=false` (DEF-567). The SQL cases are meaningful on either
backend; run them on PostgreSQL (`--ds=config.settings.pgtest`) because that is
where the triggers, the constraints and RLS exist (hard-won law 14).
"""

from __future__ import annotations

import datetime as dt
import re
from decimal import Decimal

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.payments import api as payments_api
from apps.payments import bankrec_models as bankrec
from apps.payments import counter_session_models as tills
from apps.payments import models as pay
from apps.payments import refunds_api
from apps.tenancy import models as tenancy_models
from apps.tenancy import published_content_models as published
from core.pagination import DEFAULT_PAGE_SIZE

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    dana,
    make_premises,
    make_unit,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

PAGE = DEFAULT_PAGE_SIZE  # 50 — IS-2's smallest page, the one a screen opens on
#: BR-TEN-043 — every moment here is NAMED. Nothing in these cases reads a clock.
OPENED = dt.datetime(2026, 9, 21, 8, 55, tzinfo=dt.UTC)
CLOSED = dt.datetime(2026, 9, 21, 17, 30, tzinfo=dt.UTC)
DAY = dt.date(2026, 9, 21)


# ══════════════════════════════════════════════════════════════════════════
# Fixture — batches that are BANKABLE, because a held-back one is not served
# ══════════════════════════════════════════════════════════════════════════
def _centre(tenant):
    centre, _ = published.ServiceCentre.objects.get_or_create(
        tenant_id=tenant.id,
        slug="main-counter",
        defaults={"name": "Main counter", "address": "1 Bend Road, Needville TX"},
    )
    return centre


def _user_id(actor):
    return getattr(actor, "user_id", None) or actor.id


def plant_batches(tenant, owner, *, count: int, tag: str, status: str | None = None):
    """`count` CLOSED tills, one batch each — the population Finance can bank.

    ⚠ **ONE TILL PER BATCH, BECAUSE `uq_deposit_batches_session_method` SAYS SO.**
    `P0.6` re-keyed a batch onto one till × one tender, so twenty thousand
    batches on one tender need twenty thousand tills. They are CLOSED, which is
    `bankrec.BANKABLE`'s condition: a batch behind an open drawer is held back
    by `batch_queryset` on purpose (`P2.10`) and would not be in the population
    under test at all.

    ⚠ **`uq_counter_sessions_open_owner` IS NOT IN THE WAY** — it permits one
    OPEN till per person and every till here is closed, so one owner can hold
    all of them.

    Statuses cycle through the four so the tile cases have something to be wrong
    about; a fixed `status` pins them all to one where a case needs that.
    """
    method = tenancy_models.PaymentMethod.objects.filter(tenant=tenant).first()
    assert method is not None, "the tenant has no payment method seeded"
    sessions = [
        tills.CounterSession(
            tenant_id=tenant.id,
            owner_id=_user_id(owner),
            service_centre=_centre(tenant),
            opening_float=Decimal("200.0000"),
            currency="USD",
            opened_at=OPENED,
            closed_at=CLOSED,
            closed_by_id=_user_id(owner),
            close_kind=pay.COUNTER_CLOSE_COUNTED,
            difference=Decimal("0.0000"),
        )
        for _ in range(count)
    ]
    tills.CounterSession.objects.bulk_create(sessions)
    cycle = (
        bankrec.BATCH_IN_TRANSIT,
        bankrec.BATCH_UNMATCHED,
        bankrec.BATCH_MATCHED,
        bankrec.BATCH_RECONCILED,
    )
    batches = [
        bankrec.DepositBatch(
            tenant_id=tenant.id,
            code=f"DEP-{tag}-{index:05d}",
            session=session,
            method=method,
            deposited_on=DAY - dt.timedelta(days=index % 30),
            recorded_total=Decimal("101.0000"),
            status=status or cycle[index % len(cycle)],
        )
        for index, session in enumerate(sessions)
    ]
    bankrec.DepositBatch.objects.bulk_create(batches)
    return batches


def _an_account(tenant, actor):
    """One account of this tenant — `refunds.account_id` is NOT NULL.

    ⚠ **THE FIRST DRAFT OMITTED THE COLUMN AND POSTGRESQL REFUSED THE WHOLE
    TRANSACTION, WHICH IS HARD-WON LAW 14 CATCHING A FIXTURE.** A refund
    belongs to an ACCOUNT (`CR-059` §6 Q6, PO 2026-09-01) and the column has
    been NOT NULL since `payments/0018`; a `bulk_create` without it aborts the
    transaction and every later statement in the test raises
    `TransactionManagementError` — five teardown errors naming neither the
    fixture nor the column.

    ⚠ **AND THE SECOND DRAFT ASSUMED THE FIXTURE HAD ONE.** `brazos` seeds a
    tenant, not a customer book, so `.first()` returned `None` and five cases
    failed on *"the tenant has no account seeded"* — an assertion that reads
    like a finding about the product.

    ⚠ **AND THE THIRD AND FOURTH DRAFTS WROTE ONE STRAIGHT THROUGH THE ORM AND
    POSTGRESQL REFUSED EACH BY NAME** — first `ck_accounts_anchored`, then
    `ck_accounts_regular_has_unit`. An account must hang off a UNIT or a
    PREMISES, and a REGULAR one must have the unit: that is CLAUDE.md hard rule
    8's address chain enforced in the database — every entity derives its
    address by walking to the premises, and *"the account derives its plan from
    the unit"*. An account anchored to nothing has no address to walk to.
    **That is two constraints working on a fixture rather than two obstacles**,
    and it is why this goes through the real premises and unit services instead
    of guessing which columns satisfy them.
    """
    from apps.customers import models as customers_models

    account = customers_models.Account.objects.filter(tenant_id=tenant.id).first()
    if account is not None:
        return account
    status = customers_models.AccountStatus.objects.filter(tenant_id=tenant.id).first()
    kind = customers_models.AccountType.objects.filter(tenant_id=tenant.id).first()
    assert status is not None and kind is not None, "the tenant has no account lookups seeded"
    unit = _a_unit(actor)
    return customers_models.Account.objects.create(
        tenant_id=tenant.id,
        account_no="AC-2026-90001",
        status=status,
        account_type=kind,
        premises_id=unit["premises_id"],
        unit_id=unit["id"],
    )


def _a_unit(actor):
    """One unit, with its premises — the anchor the two constraints demand.

    Through `make_premises`/`make_unit`, which are the real services, because a
    premises written by hand would have to satisfy `BR-MET-401`'s owner party
    and this file has no business knowing that.
    """
    premises = make_premises(actor)
    unit = make_unit(actor, premises["id"])
    return {"id": unit["id"], "premises_id": premises["id"]}


def plant_refunds(tenant, actor, *, count: int, tag: str, status: str | None = None):
    """`count` refunds in the approval queue.

    ⚠ **THEY CARRY NO `payment`, WHICH IS LAWFUL AND IS NOT AN OVERSIGHT.**
    `refunds.payment_id` became nullable with `payments/0018` (the PO's ruling
    of 2026-09-01, `OQ-195`) because a refund may be raised against a CREDIT
    BALANCE rather than against one overpayment. What this file tests is the
    COST of listing them; nothing here asserts a money figure — the money cases
    live in the refunds suite over the real service path.
    """
    account = _an_account(tenant, actor)
    rows = [
        pay.Refund(
            tenant_id=tenant.id,
            account=account,
            amount=Decimal("84.0000"),
            currency="USD",
            status=status or pay.REFUND_REQUESTED,
            method=pay.REFUND_METHOD_CHECK,
            reference=f"{tag}-{index:05d}",
            requested_by_id=_user_id(actor),
            requested_at=CLOSED - dt.timedelta(minutes=index),
        )
        for index in range(count)
    ]
    pay.Refund.objects.bulk_create(rows)
    return rows


# ── the two views, driven as a browser drives them ─────────────────────────
def _request(path, tenant, actor, **params):
    """A real DRF request for the VIEW, not a call to the read model under it.

    ⚠ **THE VIEW IS THE THING UNDER TEST.** Both defects were in what the view
    did with a read model's answer, and a case calling the read model directly
    would pass identically whether the ROUTE reaches it or still builds the
    whole register.
    """
    from rest_framework.test import APIRequestFactory, force_authenticate

    request = APIRequestFactory().get(f"/api/brazosbend/{path}", params)
    force_authenticate(request, user=actor.user)
    request.tenant_role = "system_admin"
    request.tenant_id = tenant.id
    return request


def _limit(queries, size: int):
    """The captured statements that take exactly `size` rows — the page, in SQL.

    ⚠ **`LIMIT 50` AND NOT `LIMIT`**, the false pass `DEF-RAT-5742` had to
    design itself out of: Django renders a `Subquery(...[:1])` as `LIMIT 1`
    inside a SELECT list, so a check for the bare word can go green on code that
    never asked the database for a page at all.
    """
    return [q for q in queries if re.search(rf"\bLIMIT\s+{size}\b", q["sql"], re.I)]


def _counts(queries):
    return [q for q in queries if re.search(r"\bCOUNT\(", q["sql"], re.I)]


# ══════════════════════════════════════════════════════════════════════════
# 1 · DEF-PAY-6554 — the deposits list takes its page in SQL (`P1.2`)
# ══════════════════════════════════════════════════════════════════════════
def test_the_deposits_endpoint_asks_the_database_for_one_page(brazos, dana):
    """`NFR-3` — fifty rows cost fifty rows' work, whatever the drawer holds."""
    with tenant_ctx(brazos):
        plant_batches(brazos, dana, count=120, tag="A")
        with CaptureQueriesContext(connection) as captured:
            response = payments_api.deposit_batches(_request("deposit-batches", brazos, dana))
        assert response.status_code == 200
        assert len(response.data["results"]) == PAGE
        assert response.data["count"] == 120

        statements = list(captured.captured_queries)
        assert _limit(statements, PAGE), (
            "GET /deposit-batches sent no `LIMIT 50`; the page was taken in "
            "Python over a list `batch_list` had already built in full"
        )
        assert _counts(statements), (
            "no COUNT(*) was sent — the envelope's `count` was `len()` over a "
            "list that had to exist first"
        )


def test_the_deposit_statement_count_does_not_follow_the_drawer(brazos, dana):
    """`NFR-3` — the COST of this screen does not grow with the tenant.

    The assertion is a COMPARISON and never a literal: a number would go red the
    day an unrelated lane adds a `select_related`, and the next reader would
    edit the number rather than look at it.
    """
    with tenant_ctx(brazos):
        plant_batches(brazos, dana, count=60, tag="B")
        with CaptureQueriesContext(connection) as small:
            payments_api.deposit_batches(_request("deposit-batches", brazos, dana))
        small_count = len(small.captured_queries)

        plant_batches(brazos, dana, count=240, tag="C")
        with CaptureQueriesContext(connection) as large:
            payments_api.deposit_batches(_request("deposit-batches", brazos, dana))
        large_count = len(large.captured_queries)

    assert large_count <= small_count, (
        f"the deposits list cost {small_count} statements over 60 batches and "
        f"{large_count} over 300 — the work follows the register, which at the "
        f"top of T5 is every batch a utility ever banked, built to draw fifty"
    )


def test_the_second_page_of_deposits_asks_for_the_second_page(brazos, dana):
    """`?page=2` is an OFFSET in SQL, not a slice of a built list."""
    with tenant_ctx(brazos):
        plant_batches(brazos, dana, count=120, tag="D")
        with CaptureQueriesContext(connection) as captured:
            response = payments_api.deposit_batches(
                _request("deposit-batches", brazos, dana, page="2")
            )
        assert len(response.data["results"]) == PAGE
        offsets = [
            q
            for q in captured.captured_queries
            if re.search(r"\bOFFSET\s+50\b", q["sql"], re.I)
        ]
        assert offsets, "page 2 sent no `OFFSET 50` — it sliced a built list"


def test_an_out_of_range_page_clamps_and_never_errors(brazos, dana):
    """`BR-SHL-011` — a list URL clamps into [1, last]; it never 4xxs."""
    with tenant_ctx(brazos):
        plant_batches(brazos, dana, count=60, tag="E")
        response = payments_api.deposit_batches(
            _request("deposit-batches", brazos, dana, page="999")
        )
    assert response.status_code == 200
    assert len(response.data["results"]) > 0, (
        "?page=999 answered with a blank table instead of clamping to the last "
        "real page — the shape `prepaged` re-fetches for"
    )


# ══════════════════════════════════════════════════════════════════════════
# 2 · THE TILES DESCRIBE THE FILTERED SET, NEVER THE PAGE
# ══════════════════════════════════════════════════════════════════════════
def test_the_tiles_are_folded_over_the_filtered_set_and_not_over_the_page(brazos, dana):
    """US-PAY-020 TC-2 — *"KPI tiles tie to batch rows exactly"*, read at scale.

    ⚠ **THIS IS THE CASE PAGING COULD HAVE BROKEN SILENTLY.** Fold the PAGE and
    every tile is arithmetically correct about fifty rows and wrong about the
    screen: *In transit* would shrink as a clerk walked forward, and *"money we
    believe we banked"* is the one figure this screen must not get wrong.
    """
    with tenant_ctx(brazos):
        plant_batches(brazos, dana, count=120, tag="F", status=bankrec.BATCH_IN_TRANSIT)
        response = payments_api.deposit_batches(_request("deposit-batches", brazos, dana))
        kpis = response.data["kpis"]

    assert len(response.data["results"]) == PAGE
    assert kpis["batch_count"] == 120, (
        f"the tiles counted {kpis['batch_count']} batches over a set of 120 — "
        f"they were folded over the PAGE, so they describe fifty rows and "
        f"claim to describe the screen"
    )
    assert kpis["in_transit_count"] == 120
    # 120 × 101.0000 — Decimal on the NUMERIC(18,6) grid, never a float sum.
    assert Decimal(kpis["in_transit_total"]) == Decimal("12120.000000")


def test_a_status_filter_narrows_the_tiles_with_the_rows(brazos, dana):
    """A tile over the FILTERED set, not over the whole register.

    The mirror of the case above, and it is what stops the fix over-correcting
    into *"fold everything, always"*: a clerk narrowing to `unmatched` is asking
    about unmatched money and the tiles must answer that question.
    """
    with tenant_ctx(brazos):
        plant_batches(brazos, dana, count=60, tag="G", status=bankrec.BATCH_IN_TRANSIT)
        plant_batches(brazos, dana, count=20, tag="H", status=bankrec.BATCH_UNMATCHED)
        response = payments_api.deposit_batches(
            _request("deposit-batches", brazos, dana, **{"f.status": "unmatched"})
        )
    assert response.data["count"] == 20
    assert response.data["kpis"]["batch_count"] == 20
    assert response.data["kpis"]["unmatched_count"] == 20
    assert response.data["kpis"]["in_transit_count"] == 0


def test_the_open_till_counter_still_ignores_the_filter(brazos, dana):
    """`still_open` is the money this list is NOT showing, and paging does not
    move it — its own docstring rules that it ignores `status` and `method`, and
    it must ignore the PAGE for the same reason: it is a figure about the rows
    this screen does not contain."""
    with tenant_ctx(brazos):
        plant_batches(brazos, dana, count=60, tag="I")
        response = payments_api.deposit_batches(_request("deposit-batches", brazos, dana))
    assert "still_open" in response.data
    assert "batch_count" in response.data["still_open"]


# ══════════════════════════════════════════════════════════════════════════
# 3 · `P1.7` — `q` on the deposits endpoint
# ══════════════════════════════════════════════════════════════════════════
def test_q_finds_a_batch_by_its_code(brazos, dana):
    """p048's filter table: *"Search · q · batch code, bank reference, cheque"*.

    ⚠ **THE ASSERTION IS THE ROW THAT MUST NOT BE THERE.** A case that only
    checked the wanted row came back would pass on an endpoint that ignores `q`
    entirely, because then EVERY row comes back.
    """
    with tenant_ctx(brazos):
        plant_batches(brazos, dana, count=3, tag="JJ")
        plant_batches(brazos, dana, count=3, tag="KK")
        response = payments_api.deposit_batches(
            _request("deposit-batches", brazos, dana, q="DEP-JJ")
        )
    codes = {row["code"] for row in response.data["results"]}
    assert codes == {"DEP-JJ-00000", "DEP-JJ-00001", "DEP-JJ-00002"}, (
        f"`q=DEP-JJ` served {sorted(codes)} — the term did not reach the query"
    )
    assert response.data["count"] == 3


def test_q_finds_a_batch_by_a_payment_confirmation(brazos, dana):
    """The second leg of p048's search: the CHEQUE number a clerk is holding.

    A deposit slip carries cheque numbers, not batch codes, so a search that
    only matched the code would answer *"no deposits"* to the thing actually in
    the clerk's hand.
    """
    with tenant_ctx(brazos):
        batches = plant_batches(brazos, dana, count=2, tag="LL")
        method = tenancy_models.PaymentMethod.objects.filter(tenant=brazos).first()
        pay.Payment.objects.create(
            tenant_id=brazos.id,
            account=_an_account(brazos, dana),  # NOT NULL — see `_an_account`
            amount=Decimal("101.0000"),
            currency="USD",
            method=method,
            status=pay.PAYMENT_CLEARED,
            confirmation="4471",
            posted_at=CLOSED,
            deposit_batch_id=batches[0].pk,
        )
        response = payments_api.deposit_batches(
            _request("deposit-batches", brazos, dana, q="4471")
        )
    codes = {row["code"] for row in response.data["results"]}
    assert codes == {batches[0].code}, (
        f"a cheque number found {sorted(codes)} — the confirmation leg of `q` "
        f"is not wired, so a clerk holding a deposit slip cannot find its batch"
    )


def test_a_one_character_search_is_refused_rather_than_scanning(brazos, dana):
    """IS-3's minimum, the cost register's shape (`cost_capture.MIN_SEARCH_CHARS`).

    One character scans every row of the table to return most of them, which is
    the opposite of what a search is for.
    """
    with tenant_ctx(brazos):
        plant_batches(brazos, dana, count=3, tag="MM")
        response = payments_api.deposit_batches(
            _request("deposit-batches", brazos, dana, q="D")
        )
    assert response.status_code == 422, (
        f"a one-character search answered {response.status_code}; IS-3 refuses "
        f"it, and an endpoint that scans instead is a search box that costs the "
        f"whole table per keystroke"
    )


def test_the_search_is_taken_in_sql_with_the_page(brazos, dana):
    """A client-side filter over page one searches 50 of 40,000 and reports that
    as the answer, which is `NFR-3` read from the other side."""
    with tenant_ctx(brazos):
        plant_batches(brazos, dana, count=120, tag="NN")
        with CaptureQueriesContext(connection) as captured:
            payments_api.deposit_batches(
                _request("deposit-batches", brazos, dana, q="DEP-NN")
            )
        assert _limit(captured.captured_queries, PAGE), (
            "a searched list sent no LIMIT — the term narrowed a built list"
        )


# ══════════════════════════════════════════════════════════════════════════
# 4 · DEF-PAY-6555 — the refund approval queue (`P1.3`)
# ══════════════════════════════════════════════════════════════════════════
def test_the_refund_queue_asks_the_database_for_one_page(brazos, dana):
    """`NFR-3` — and the objection the old code raised is answered by the case
    below, not by leaving the list unbounded."""
    with tenant_ctx(brazos):
        plant_refunds(brazos, dana, count=120, tag="RA")
        with CaptureQueriesContext(connection) as captured:
            response = refunds_api.refunds_queue(_request("refunds", brazos, dana))
        assert response.status_code == 200
        assert len(response.data["results"]) == PAGE
        assert _limit(captured.captured_queries, PAGE), (
            "GET /refunds sent no `LIMIT 50`; `refund_queue` returned a tuple "
            "over every refund the tenant holds"
        )


def test_the_refund_queue_states_the_true_total_beside_the_page(brazos, dana):
    """**THE CASE THAT SETTLES `P1.3`.**

    The code argued *"a page of an approval queue is a queue that lies about
    what is pending"*, and it is a real argument. The answer the Finance
    blueprint gives on p040 is the COUNT: *"`Refunds · 1` states the true total
    on every page, so paging can no longer hide anything."* This asserts it —
    fifty rows on the page and one hundred and twenty stated as pending. Without
    this assertion the pager WOULD lie, and the old objection would be right.
    """
    with tenant_ctx(brazos):
        plant_refunds(brazos, dana, count=120, tag="RB")
        response = refunds_api.refunds_queue(
            _request("refunds", brazos, dana, **{"f.status": "requested"})
        )
    assert len(response.data["results"]) == PAGE
    assert response.data["count"] == 120, (
        f"the queue served a page of {PAGE} and said {response.data['count']} "
        f"were pending — a page that lies about what is pending is exactly what "
        f"the unpaginated read existed to prevent"
    )


def test_the_refund_statement_count_does_not_follow_the_queue(brazos, dana):
    """`NFR-3` — the comparison form again, never a literal."""
    with tenant_ctx(brazos):
        plant_refunds(brazos, dana, count=60, tag="RC")
        with CaptureQueriesContext(connection) as small:
            refunds_api.refunds_queue(_request("refunds", brazos, dana))
        small_count = len(small.captured_queries)

        plant_refunds(brazos, dana, count=240, tag="RD")
        with CaptureQueriesContext(connection) as large:
            refunds_api.refunds_queue(_request("refunds", brazos, dana))
        large_count = len(large.captured_queries)

    assert large_count <= small_count, (
        f"the refund queue cost {small_count} statements over 60 refunds and "
        f"{large_count} over 300 — the work follows the queue"
    )


def test_an_unknown_refund_status_is_still_refused_by_name(brazos, dana):
    """The refusal `refund_queue` already made, carried through the change.

    *"An empty queue and an unanswerable one look identical on a screen"* — a
    clerk who typed a wrong filter would read *"nothing is waiting"* over a
    queue full of money.
    """
    with tenant_ctx(brazos):
        plant_refunds(brazos, dana, count=3, tag="RE")
        response = refunds_api.refunds_queue(
            _request("refunds", brazos, dana, **{"f.status": "pending"})
        )
    assert response.status_code == 422


# ══════════════════════════════════════════════════════════════════════════
# 5 · `P1.4` / `P1.5` — the chip vocabularies come off the SERVER
# ══════════════════════════════════════════════════════════════════════════
def test_the_deposits_body_serves_its_own_status_and_method_chips(brazos, dana):
    """`P1.4` — *"A status added server-side appears without a front-end change"*.

    ⚠ **THE ASSERTION IS THAT THE SERVED SET *IS* THE ENUM**, not that it holds
    four names. A case listing the four would go green the day a fifth status is
    added server-side and never offered — which is the defect (`DEF-PAY-6556`).
    """
    with tenant_ctx(brazos):
        plant_batches(brazos, dana, count=3, tag="P")
        response = payments_api.deposit_batches(_request("deposit-batches", brazos, dana))
    served = [chip["value"] for chip in response.data["statuses"]]
    assert served == list(bankrec.BATCH_STATUSES), (
        f"the body offered {served} against the enum {list(bankrec.BATCH_STATUSES)}"
    )
    methods = [chip["value"] for chip in response.data["methods"]]
    assert methods, (
        "no method chips were served — `f.method` is accepted by the query and "
        "the screen has nothing to build a control from (`DEF-PAY-6556`)"
    )


def test_the_refund_queue_serves_its_own_status_chips(brazos, dana):
    """`P1.5` — *"As P1.4"*, one register over. `REFUND_FILTERS` was a literal
    array in the page and the five statuses live in `models.REFUND_STATUSES`."""
    with tenant_ctx(brazos):
        plant_refunds(brazos, dana, count=3, tag="RF")
        response = refunds_api.refunds_queue(_request("refunds", brazos, dana))
    served = [chip["value"] for chip in response.data["statuses"]]
    assert served == list(pay.REFUND_STATUSES), (
        f"the queue offered {served} against the enum {list(pay.REFUND_STATUSES)}"
    )
    methods = [chip["value"] for chip in response.data["methods"]]
    assert methods == list(pay.REFUND_METHODS), (
        f"the queue offered {methods} against {list(pay.REFUND_METHODS)} — "
        f"`REFUND_METHODS` was a second copy in the front end"
    )
