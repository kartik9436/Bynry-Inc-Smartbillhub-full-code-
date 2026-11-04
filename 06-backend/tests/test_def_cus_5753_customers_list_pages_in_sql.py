# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-CUS-5753 — `GET /customers` built EVERY customer the tenant
#          holds in order to draw fifty, because `api._paginated` handed DRF a
#          LIST, and then spent one further query PER PERSON on that person's
#          accounts. Filed by this lane BEFORE it was fixed (CLAUDE.md step W).
# Rules:   NFR-3 (universal server pagination) · NFR-5 (no hard caps anywhere) ·
#          BR-SHL-011 (a list URL clamps and never 4xx; an out-of-range page
#          clamps INTO range rather than serving a blank table) · hard rule 1
#          (tenant scoping — a page may not reach another tenant) ·
#          BR-CUS-092(c) (last four only; a full identifier never reaches a
#          list response) · BR-CUS-054 (the N:M link this row draws) ·
#          BR-CUS-1046 / DEF-CUS-5060 (`account_page`, the same fix on the
#          accounts list, whose shape this follows) · DEF-RAT-5742 (the same
#          fix on Plans & Rates, landed the same day, whose case shapes these
#          borrow)
# Tests:   this file
# Impacts: 06-backend/apps/customers/api.py (`_prepaged` replaces `_paginated`,
#          which is DELETED) · 06-backend/apps/customers/selectors.py
#          (`customer_list_queryset` · `customer_page` · `customer_rows`)
# ───────────────────────────────────────────────────────
"""DEF-CUS-5753 — the customers list takes its page in the DATABASE.

RED-FIRST PROOF (hard-won law 7, in the harness that runs it — `pytest`, never
a `__main__`): every case below was run against this worktree BEFORE the fix
was applied, and the failures are quoted in the lane report. The two that
carry the defect:

  * `test_the_endpoint_asks_the_database_for_one_page` fails with *"GET
    /customers sent no `LIMIT 50` — the page was taken in Python"*. It is aimed
    at the VIEW and not at the new selector on purpose, so that it can fail on a
    tree where the new selector does not exist yet; a case calling
    `selectors.customer_page` would only ever fail with `AttributeError`, which
    proves a function was added and nothing at all about where the page is taken.
  * `test_the_statement_count_does_not_follow_the_tenant` fails on the measured
    counts: **5 statements for 4 customers and 17 for 16** — one per person, so
    at the top of T5 it is of the order of 40,001 statements in one request.

⚠ **A CASE THAT COUNTS RETURNED ROWS CANNOT TELL SQL PAGING FROM PYTHON PAGING**
and would have passed, green, through the whole life of this defect: DRF sliced
the built list to exactly fifty rows and served a correct `count`, a correct
`next` and the correct people. Everything about the ANSWER was right; the only
thing wrong was how much work was done to produce it. So every case here asserts
the SQL that was sent, or the number of statements it took — never a row count
on its own. The row counts that do appear are guards on the ENVELOPE, and they
are labelled as such.

⚠ **AND THE COUNT CASES SAY *THE COST DID NOT MOVE*, NEVER A NUMBER** (the form
`test_cr092_asset_paging.py` argues for). An equality against a literal goes red
the day an unrelated lane adds a `select_related`, which teaches the next reader
to edit the number instead of looking at it. What `NFR-3` promises is that one
screen costs the same whatever the tenant's size, so each case builds a SECOND,
larger population and asserts the count did not follow it. A fixture of three
customers — which is the largest any existing customers case builds — cannot
tell 1+N from a constant, and that is how this survived.

⚠ **WHICH CASES SPEAK, AND WHICH ARE ONLY GUARDS — STATED, BECAUSE A READER
CANNOT TELL FROM A GREEN DOT.** Five fail on the unfixed tree and are the
defect: the endpoint's missing `LIMIT 50`, the `COUNT(*)`, the lazy queryset,
the statement count that follows the tenant, and the missing `LIMIT 100`. The
other seven are REGRESSION guards and pass either way by design — the envelope,
the `BR-SHL-011` clamp, the empty list, the accounts cell, `BR-CUS-092(c)`, the
`customer_list` shape and tenant isolation. They exist because the fix rebuilds
the row-building path, and none of them is evidence that the page reaches SQL.

⚠ **THE SEMANTIC GUARD IS NOT OPTIONAL.** The fix batches the per-person
`customer_accounts` read for the whole page. A batched read that returns fewer
facts, or the same facts in a different order, is a speed-up wearing a
regression's clothes, and a statement count can only get BETTER when it
happens. So the row is asserted by VALUE as well: the accounts a person holds,
in `account_no` order, with their status and their `BR-CUS-089` match columns,
and the identity cells that may never carry more than four digits.

Run with `JOBS_EAGER=false` (DEF-567).
"""

import re

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.customers import api as customers_api
from apps.customers import models as customers_models
from apps.customers import selectors as customers_selectors
from apps.metering import models as metering_models
from core.pagination import DEFAULT_PAGE_SIZE, ListParams

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    dana,
    erin,
    lonestar,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

PAGE = DEFAULT_PAGE_SIZE  # 50 — IS-2's smallest page, and the one a screen opens on
ENVELOPE = {"count", "next", "previous", "results"}


# ══════════════════════════════════════════════════════════════════════════
# Fixture — people who HOLD something, because an empty person hides the bug
# ══════════════════════════════════════════════════════════════════════════
def plant_customers(tenant, *, people: int, tag: str, accounts_each: int = 2) -> int:
    """`people` customers, each holding `accounts_each` real accounts.

    ⚠ **A PAGE OF BARE CUSTOMERS WOULD STILL SHOW THE STATEMENT COUNT AND WOULD
    HIDE EVERYTHING ELSE.** The per-row read this test exists to catch is a read
    of what HANGS OFF the person — the `customer_accounts` links and, through
    them, each account's number, kind and status. Plant people with no accounts
    and the semantic guard below has nothing to compare, so the batched read
    could drop every cell and stay green: `DEF-1549`'s fixture gap, which
    `test_def2723_accounts_list_statement_count.py` records one screen over.

    An account must be ANCHORED (`ck_accounts_anchored`) and a `regular` one
    must name a unit (`ck_accounts_regular_has_unit`), so each gets a real unit
    on a real premises rather than a bare row.
    """
    premises = metering_models.Premises.objects.create(
        tenant=tenant, address_line=f"1408 Elm St {tag}", city="Ottumwa", state="IA"
    )
    status = customers_models.AccountStatus.objects.filter(tenant=tenant).first()
    assert status is not None, "the tenant has no account status seeded"
    account_type = customers_models.AccountType.objects.filter(tenant=tenant).first()
    for index in range(people):
        person = customers_models.Customer.objects.create(
            tenant=tenant,
            customer_no=f"C-{tag}{index:05d}",
            kind="person",
            display_name=f"Ruiz {tag}{index:05d}",
        )
        for seat in range(accounts_each):
            unit = metering_models.Unit.objects.create(
                tenant=tenant, premises=premises, label=f"Unit {tag}{index}-{seat}"
            )
            account = customers_models.Account.objects.create(
                tenant=tenant,
                unit=unit,
                premises_id=premises.id,
                account_no=f"A-{tag}{index:04d}{seat}",
                status=status,
                account_type=account_type,
            )
            customers_models.CustomerAccount.objects.create(
                tenant=tenant,
                customer=person,
                account=account,
                match_tier="strong",
                match_basis="name+dob+ssn",
            )
    return people


def _request(tenant, actor, **params):
    """A real DRF request for the VIEW, not a call to the selector underneath it.

    ⚠ **THE VIEW IS THE THING UNDER TEST IN THE SQL CASE.** `_prepaged` is what
    replaced `_paginated`, and a case that called `selectors.customer_page`
    directly would pass identically whether the ROUTE reaches it or still builds
    the whole tenant — which is exactly the shape this defect had.

    `force_authenticate` rather than `request.user = …`: DRF's `Request.user`
    re-runs the authenticators and overwrites whatever the underlying Django
    request carried, so a direct assignment silently 401s.
    """
    request = _factory().get("/api/brazosbend/customers", params)
    _authenticate(request, actor)
    request.tenant_role = "system_admin"
    request.tenant_id = tenant.id
    return request


def _factory():
    from rest_framework.test import APIRequestFactory

    return APIRequestFactory()


def _authenticate(request, actor):
    from rest_framework.test import force_authenticate

    force_authenticate(request, user=actor.user)


def _limit_50(queries):
    """The captured statements that take FIFTY rows — the page, in SQL.

    ⚠ **`LIMIT 50` AND NOT `LIMIT`**, the false pass `DEF-RAT-5742` had to
    design itself out of: Django renders a `Subquery(...[:1])` as `LIMIT 1`
    inside a SELECT list, so a check for the bare word can go green on code that
    never asked the database for a page at all.
    """
    return [q for q in queries if re.search(r"\bLIMIT\s+50\b", q["sql"], re.I)]


# ══════════════════════════════════════════════════════════════════════════
# 1 · THE PAGE IS TAKEN IN SQL — the case that goes red on the old code
# ══════════════════════════════════════════════════════════════════════════
def test_the_endpoint_asks_the_database_for_one_page(brazos, dana):
    """`NFR-3`: the page is a SQL `LIMIT`, not a Python slice of the tenant."""
    with tenant_ctx(brazos):
        plant_customers(brazos, people=PAGE + 10, tag="a", accounts_each=1)
        with CaptureQueriesContext(connection) as ctx:
            body = customers_api.customers(_request(brazos, dana)).data

    limited = _limit_50(ctx.captured_queries)
    assert limited, (
        "GET /customers sent no `LIMIT 50` — the page was taken in Python, which "
        f"is DEF-CUS-5753. Statements: {len(ctx.captured_queries)}"
    )
    assert any("customers" in q["sql"] for q in limited), (
        "GET /customers sent a `LIMIT 50`, but not over `customers` — the page is "
        "being taken somewhere other than the list's own query"
    )
    # Envelope guards. TRUE ON THE BROKEN CODE TOO, and here only so that a
    # fix cannot buy its speed by serving the wrong page.
    assert body["count"] == PAGE + 10, "the count must be the WHOLE set, not the page"
    assert len(body["results"]) == PAGE


def test_the_total_is_a_sql_count_and_not_a_len(brazos, dana):
    """The other half of `NFR-3`, and the half that is easy to lose.

    A page taken in SQL whose total is still `len(everything)` has MOVED the
    cost rather than removed it — the whole tenant is still built, just for a
    number.
    """
    with tenant_ctx(brazos):
        plant_customers(brazos, people=PAGE + 10, tag="b", accounts_each=1)
        with CaptureQueriesContext(connection) as ctx:
            rows, total = customers_selectors.customer_page(ListParams(page=1, per=PAGE))

    assert total == PAGE + 10 and len(rows) == PAGE
    assert any("COUNT(" in q["sql"].upper() for q in ctx.captured_queries), (
        "the customers total was counted in Python — the whole tenant was built to "
        "produce one number"
    )


def test_the_list_queryset_is_lazy(brazos, dana):
    """`customer_list_queryset` is a QuerySet and its slice compiles to a LIMIT.

    A `list` here means the paginator slices in Python and the page can never
    reach the database, whatever the view then does with it.
    """
    with tenant_ctx(brazos):
        plant_customers(brazos, people=7, tag="c", accounts_each=1)
        qs = customers_selectors.customer_list_queryset(ListParams())
        assert not isinstance(
            qs, list
        ), "customer_list_queryset must stay lazy — a list here is the NFR-3 breach"
        sql, _params = qs[2:5].query.sql_with_params()
        assert "LIMIT" in sql.upper()
        assert len(list(qs[2:5])) == 3


# ══════════════════════════════════════════════════════════════════════════
# 2 · THE COST DOES NOT FOLLOW THE TENANT
# ══════════════════════════════════════════════════════════════════════════
def test_the_statement_count_does_not_follow_the_tenant(brazos, dana):
    """One screen costs the same whatever the utility's size.

    **RED BEFORE THE FIX, measured on this harness:** `GET /customers` cost 5
    statements over 4 customers and 17 over 16 — one per person, every one of
    them a read of that person's accounts.
    """
    with tenant_ctx(brazos):
        small_n = plant_customers(brazos, people=4, tag="d")
        with CaptureQueriesContext(connection) as ctx:
            customers_api.customers(_request(brazos, dana))
        small = len(ctx.captured_queries)

        large_n = small_n + plant_customers(brazos, people=12, tag="e")
        with CaptureQueriesContext(connection) as ctx:
            customers_api.customers(_request(brazos, dana))
        large = len(ctx.captured_queries)

    per_person = (large - small) / (large_n - small_n)
    print(
        f"\nDEF-CUS-5753 GET /customers: {small} statements for {small_n} customers, "
        f"{large} for {large_n} — {per_person:.2f} per customer added"
    )
    assert large <= small, (
        f"GET /customers cost {small} statements for {small_n} customers and {large} "
        f"for {large_n} — {per_person:.2f} EXTRA PER PERSON. That is a query per row "
        f"on a list a landlord-heavy utility lives in, and at the top of T5 it is of "
        f"the order of 40,001 statements in one request (DEF-CUS-5753). Batch the "
        f"page's `customer_accounts` read the way `account_rows` already batches its "
        f"seven."
    )


def test_a_bigger_page_is_a_bigger_limit_and_not_more_queries(brazos, dana):
    """`NFR-5` has no cap: `per=100` is a bigger `LIMIT`, not more statements.

    ⚠ **THE STATEMENT-COUNT HALF OF THIS CASE CANNOT FAIL ON THE OLD CODE AND
    IS NOT PRETENDED TO** (law 7 habit 2 — ask what would make a check pass
    wrongly). The old path built the whole tenant for BOTH page sizes, so its
    count was identically bad at 50 and at 100 and this case was green on it.
    The `LIMIT 100` assertion is what makes it speak: it is the page size
    REACHING THE DATABASE, which is the only thing `per` should change.
    """
    with tenant_ctx(brazos):
        plant_customers(brazos, people=120, tag="f", accounts_each=1)
        with CaptureQueriesContext(connection) as ctx:
            fifty = customers_api.customers(_request(brazos, dana, per=50)).data
        small, small_sql = len(ctx.captured_queries), list(ctx.captured_queries)
        with CaptureQueriesContext(connection) as ctx:
            hundred = customers_api.customers(_request(brazos, dana, per=100)).data
        large, large_sql = len(ctx.captured_queries), list(ctx.captured_queries)

    assert len(fifty["results"]) == 50 and len(hundred["results"]) == 100
    assert _limit_50(small_sql), "per=50 did not reach the database as a LIMIT"
    assert [q for q in large_sql if re.search(r"\bLIMIT\s+100\b", q["sql"], re.I)], (
        "per=100 did not reach the database as a LIMIT — the page size is being "
        "applied in Python, so asking for more rows costs the whole tenant either way"
    )
    assert large <= small, (
        f"doubling the page size doubled the work: {small} statements at per=50 and "
        f"{large} at per=100"
    )


# ══════════════════════════════════════════════════════════════════════════
# 3 · THE ENVELOPE IS THE ONE EVERY OTHER LIST SERVES
# ══════════════════════════════════════════════════════════════════════════
def test_the_envelope_is_byte_for_byte_the_shared_one(brazos, dana):
    """`count` / `next` / `previous` / `results`, with DRF's own link grammar.

    A second envelope shape on one screen is a client-side special case for
    ever — the sentence `_prepaged`'s own docstring makes.
    """
    with tenant_ctx(brazos):
        plant_customers(brazos, people=120, tag="g", accounts_each=1)
        first = customers_api.customers(_request(brazos, dana)).data
        second = customers_api.customers(_request(brazos, dana, page=2)).data
        third = customers_api.customers(_request(brazos, dana, page=3)).data

    assert ENVELOPE <= set(first), "GET /customers is not in the shared envelope"
    assert first["count"] == second["count"] == third["count"] == 120
    assert first["previous"] is None, "page 1 has no previous"
    assert "page=2" in first["next"]
    # DRF REMOVES the parameter for page 1 rather than writing `page=1`, and
    # `_prepaged` copies that exactly — a client comparing URLs must not meet
    # two spellings of the first page.
    assert "page=" not in second["previous"]
    assert "page=2" in third["previous"]
    assert third["next"] is None, "the last page has no next"
    assert len(third["results"]) == 20
    ids = [row["id"] for row in first["results"]] + [row["id"] for row in second["results"]]
    assert len(set(ids)) == len(ids), "a row appeared on two pages — the order is not total"


def test_an_out_of_range_page_clamps_into_range(brazos, dana):
    """`BR-SHL-011` — clamp, never error, and never a blank table.

    `parse_list_params` clamps `page` to ≥ 1 and cannot know the LAST page, so
    `_prepaged` re-clamps and re-asks. Without that, `?page=999` on a two-page
    list serves an empty `results` beside a `previous` link to page 998.
    """
    with tenant_ctx(brazos):
        plant_customers(brazos, people=60, tag="h", accounts_each=1)
        far = customers_api.customers(_request(brazos, dana, page=999)).data
        rubbish = customers_api.customers(_request(brazos, dana, page="not-a-page")).data

    assert far["count"] == 60
    assert len(far["results"]) == 10, "?page=999 must serve the LAST page, not a blank table"
    assert far["next"] is None
    assert far["previous"] is not None
    assert len(rubbish["results"]) == 50, "a garbage page falls back to the first one"
    assert rubbish["previous"] is None


def test_an_empty_result_is_a_whole_envelope(brazos, dana):
    """Nobody matching is a list of nobody, not a refusal and not a null."""
    with tenant_ctx(brazos):
        plant_customers(brazos, people=3, tag="i", accounts_each=1)
        body = customers_api.customers(_request(brazos, dana, q="nobody-by-that-name")).data

    assert ENVELOPE <= set(body)
    assert body["count"] == 0 and body["results"] == []
    assert body["next"] is None and body["previous"] is None


# ══════════════════════════════════════════════════════════════════════════
# 4 · THE ROW STILL SAYS THE SAME THINGS (the batched read's semantic guard)
# ══════════════════════════════════════════════════════════════════════════
def test_the_page_still_names_every_account_a_person_holds(brazos, dana):
    """The landlord case, which is the whole reason `customer_accounts` is N:M.

    ⚠ **A STATEMENT COUNT CANNOT SEE A DROPPED CELL** — it only gets better when
    one goes. So the batched read is asserted by VALUE: the count, the numbers,
    their ORDER, the status the account is in and the `BR-CUS-089` columns that
    say how the link was made.
    """
    with tenant_ctx(brazos):
        plant_customers(brazos, people=2, tag="j", accounts_each=3)
        body = customers_api.customers(_request(brazos, dana)).data

    row = next(r for r in body["results"] if r["customer_no"] == "C-j00000")
    assert row["account_count"] == 3
    numbers = [entry["account_no"] for entry in row["accounts"]]
    assert numbers == sorted(numbers), (
        "the accounts under a person must stay in account_no order — a batched read "
        "that reorders a cell is a regression a statement count cannot see"
    )
    assert numbers == ["A-j00000", "A-j00001", "A-j00002"]
    first = row["accounts"][0]
    assert first["status_code"] and first["status_name"], "the status cell went missing"
    assert first["kind"], "the account kind cell went missing"
    assert (first["match_tier"], first["match_basis"]) == ("strong", "name+dob+ssn")


def test_no_full_identifier_reaches_the_paged_list(brazos, dana):
    """`BR-CUS-092(c)` re-proved on the path that changed.

    The row-building path moved, so the rule that governs it is re-asserted
    here rather than left to the case that covers the OLD path: *"the full value
    is never in a list response"*, and an identifier that reaches a browser is
    in devtools, in a proxy log and in the HAR file attached to a ticket.
    """
    with tenant_ctx(brazos):
        plant_customers(brazos, people=2, tag="k", accounts_each=1)
        body = customers_api.customers(_request(brazos, dana)).data

    for row in body["results"]:
        identity = row["identity"]
        assert set(identity) == {
            "date_of_birth",
            "ssn_held",
            "ssn_last4",
            "driving_licence_held",
            "driving_licence_last4",
            "tax_id_held",
            "tax_id_last4",
        }
        for key in ("ssn", "driving_licence", "tax_id"):
            assert key not in row, f"{key} itself is on the list row"
        for key in ("ssn_last4", "driving_licence_last4", "tax_id_last4"):
            assert identity[key] is None or len(identity[key]) == 4


def test_customer_list_keeps_the_shape_its_callers_read(brazos, dana):
    """The stable API did not move: every matching row, ordered, as a list.

    A dozen cases and `customer_edit`'s own read-back call `customer_list`, so
    splitting the queryset out from under it may not change what it answers.
    """
    with tenant_ctx(brazos):
        plant_customers(brazos, people=60, tag="m", accounts_each=1)
        every = customers_selectors.customer_list(ListParams())
        searched = customers_selectors.customer_list(ListParams(q="C-m00007"))
        descending = customers_selectors.customer_list(ListParams(sort="customer_no", dir="desc"))

    assert isinstance(every, list) and len(every) == 60, "customer_list still returns them all"
    assert [row["customer_no"] for row in searched] == ["C-m00007"], "the search legs still work"
    assert descending[0]["customer_no"] > descending[-1]["customer_no"]


def test_the_page_never_reaches_another_tenant(brazos, dana, lonestar, erin):
    """Hard rule 1. A page taken in SQL is still one tenant's page."""
    with tenant_ctx(lonestar):
        plant_customers(lonestar, people=4, tag="n", accounts_each=1)
    with tenant_ctx(brazos):
        plant_customers(brazos, people=2, tag="p", accounts_each=1)
        body = customers_api.customers(_request(brazos, dana)).data

    assert body["count"] == 2, "the count leaked another tenant's people"
    assert {row["customer_no"] for row in body["results"]} == {"C-p00000", "C-p00001"}
