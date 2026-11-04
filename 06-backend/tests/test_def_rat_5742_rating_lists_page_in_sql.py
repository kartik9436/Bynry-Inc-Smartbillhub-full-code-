# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-RAT-5742 — every list endpoint in Plans & Rates built EVERY
#          matching row in Python and threw all but fifty away, because
#          `api._paginated` handed DRF a LIST. Filed by this lane BEFORE it was
#          fixed.
# Rules:   NFR-3 (universal server pagination) · NFR-5 (no hard caps) ·
#          BR-SHL-011 (a list URL clamps, never 4xx, and an out-of-range page
#          clamps into range) · hard rule 1 (tenant scoping — a page may not
#          reach another tenant) · hard rule 2 (money 4 dp stored / 2 displayed
#          — no figure may move) · BR-RAT-088 (the CHARGE CODE owns the base
#          amount; a pagination refactor may not change which object answers a
#          price) · BR-RAT-079 (the discount reads serve COUNTS, never
#          documents or account ids) · DEF-387 (a DERIVED value is not
#          re-implemented in SQL) · BR-CUS-1046 / DEF-CUS-5060 (the same fix,
#          one module over, whose shape this follows)
# Tests:   this file
# Impacts: apps/rating/api.py (`_prepaged` replaces `_paginated`) ·
#          apps/rating/selectors.py (`*_list_queryset` / `*_page`)
# ───────────────────────────────────────────────────────
"""DEF-RAT-5742 — Plans & Rates takes its page in the DATABASE.

RED-FIRST PROOF (hard-won law 7, and in the harness that runs it — `pytest`,
never a `__main__`): every case below was run with `pytest` against a second
worktree pinned at `caf716c13`, the tip this lane started from. The failures are
quoted in the lane report. The two that matter most:

  * `test_every_list_endpoint_asks_the_database_for_one_page` fails on the OLD
    code for all six endpoints with *"GET /plans sent no `LIMIT 50` — the page
    was taken in Python"*. It is aimed at the VIEW rather than at the new
    selector precisely so that it can fail on a tree where the new selector does
    not exist yet; a case that called `selectors.plan_page` would only ever have
    failed with `AttributeError`, which proves a function was added and nothing
    about where the page is taken.
  * `test_the_statement_count_does_not_follow_the_tenant` fails on the OLD code
    on the measured counts.

⚠ **A CASE THAT COUNTS RETURNED ROWS CANNOT TELL SQL PAGING FROM PYTHON PAGING**
and would have passed, green, throughout the whole life of this defect: DRF
sliced the built list to exactly fifty rows and served a correct `count`, a
correct `next` and correct rows. Everything about the ANSWER was right; the only
thing wrong was how much work was done to produce it. So every case here asserts
either the SQL that was sent or the number of statements it took — never a row
count on its own.

⚠ **AND THE COUNT CASES ARE WRITTEN AS *THE COST DID NOT MOVE*, NEVER AS A
NUMBER** (the form `test_cr092_asset_paging.py` argues for). An equality against
a literal goes red the day an unrelated lane adds a `select_related`, which
teaches the next reader to edit the number instead of looking at it. What
`NFR-3` promises is that the cost of ONE SCREEN is independent of how big the
tenant is, so each case builds a second, larger population and asserts the
statement count did not follow it.
"""

import re
import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.rating import api as rating_api
from apps.rating import discounts as discount_models
from apps.rating import models, selectors
from core.pagination import DEFAULT_PAGE_SIZE, ListParams

from tests.test_us_rat_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_rat_helpers import seeding_ctx, tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db

PAGE = DEFAULT_PAGE_SIZE  # 50 — IS-2's smallest page, and the one a screen opens on


# ══════════════════════════════════════════════════════════════════════════
# Populations. Written with `bulk_create` and NOT through the service layer,
# because what is under test is the cost of READING a catalogue of a size no
# fixture in this repo has ever built. The figures below price nothing — no
# case here asserts a money value — and the rows that DO carry a rate are
# created through `env` in the cases that read one.
# ══════════════════════════════════════════════════════════════════════════
def _plans(env, count, *, offset=0):
    with seeding_ctx(env.tenant):
        models.RatePlan.objects.bulk_create(
            [
                models.RatePlan(
                    tenant=env.tenant,
                    code=f"BULK-{offset + i:04d}",
                    name=f"Bulk plan {offset + i:04d}",
                    status="draft",
                )
                for i in range(count)
            ]
        )


def _charges(env, count, *, offset=0):
    with seeding_ctx(env.tenant):
        models.Charge.objects.bulk_create(
            [
                models.Charge(
                    tenant=env.tenant,
                    code=f"BULK-{offset + i:04d}",
                    name=f"Bulk charge {offset + i:04d}",
                    charge_type="one_time",
                    amount_rule="flat",
                    amount="45.000000",
                )
                for i in range(count)
            ]
        )


def _schedules(env, count, *, offset=0):
    with seeding_ctx(env.tenant):
        service_id = _any_service_id(env)
        models.Tariff.objects.bulk_create(
            [
                models.Tariff(
                    tenant=env.tenant,
                    name=f"Bulk schedule {offset + i:04d}",
                    service_id=service_id,
                )
                for i in range(count)
            ]
        )


def _any_service_id(env):
    from apps.tenancy import models as tenancy_models

    return (
        tenancy_models.TenantService.objects.filter(tenant=env.tenant)
        .order_by("service__code")
        .values_list("service_id", flat=True)
        .first()
    )


def _taxes(env, count, *, offset=0):
    with seeding_ctx(env.tenant):
        jurisdiction = models.TaxJurisdiction.objects.create(
            tenant=env.tenant,
            name=f"Bulk authority {offset}",
            authority=f"Bulk authority {offset}",
            level="state",
        )
        models.Tax.objects.bulk_create(
            [
                models.Tax(
                    tenant=env.tenant,
                    jurisdiction=jurisdiction,
                    name=f"Bulk tax {offset + i:04d}",
                    kind="percent",
                    rate="0.062500",
                )
                for i in range(count)
            ]
        )


def _discounts(env, count, *, offset=0):
    with seeding_ctx(env.tenant):
        discount_models.Discount.objects.bulk_create(
            [
                discount_models.Discount(
                    tenant=env.tenant,
                    code=f"BULK-{offset + i:04d}",
                    name=f"Bulk discount {offset + i:04d}",
                )
                for i in range(count)
            ]
        )


def _history(env, count, *, offset=0):
    with seeding_ctx(env.tenant):
        models.RateChangeLog.objects.bulk_create(
            [
                models.RateChangeLog(
                    tenant=env.tenant,
                    entity_type="charge",
                    entity_id=env.tenant.id,
                    reason=f"Bulk change {offset + i:04d}",
                    after={"name": f"Bulk change {offset + i:04d}"},
                )
                for i in range(count)
            ]
        )


#: Every list this module serves, as (name, the VIEW, the seeder, the table).
#: One table drives every case below, so an endpoint that is added and not
#: paged has to be added here to stay silent — which is the thing a per-endpoint
#: file cannot promise.
LISTS = [
    ("GET /plans", "plans", _plans, "rate_plans"),
    ("GET /rate-schedules", "rate_schedules", _schedules, "tariffs"),
    ("GET /charges", "charges", _charges, "charges"),
    ("GET /taxes", "taxes", _taxes, "taxes"),
    ("GET /discounts", "discounts", _discounts, "discounts"),
    ("GET /rate-changes", "rate_changes", _history, "rate_change_log"),
]

#: The selector pair behind each of the six, for the cases that read the
#: selector rather than the wire.
#:
#: ⚠ **BY NAME, RESOLVED AT CALL TIME, AND THAT IS NOT STYLE.** Binding
#: `selectors.plan_page` here would make this MODULE fail to import on a tree
#: where the fix is absent, so the red-first run would collect nothing and the
#: view-level cases — the ones that actually demonstrate the defect — would
#: never get to speak. Resolved lazily, the old tree runs the whole file: the
#: view cases fail on the missing `LIMIT 50`, and these fail with a plain
#: `AttributeError` that says the selector did not exist.
PAGES = {
    "GET /plans": ("plan_page", "plan_list"),
    "GET /rate-schedules": ("schedule_page", "schedule_list"),
    "GET /charges": ("charge_page", "charge_list"),
    "GET /taxes": ("tax_page", "tax_list"),
    "GET /discounts": ("discount_page", "discount_list"),
    "GET /rate-changes": ("history_page", "history_list"),
}


def _pair(label):
    page_name, list_name = PAGES[label]
    return getattr(selectors, page_name), getattr(selectors, list_name)


def _request(env, **params):
    """A real DRF request for the VIEW, not a call to the selector underneath it.

    ⚠ **THE VIEW IS THE THING UNDER TEST IN THE SQL CASE.** `_prepaged` is what
    replaced `_paginated`, and a case that called `selectors.plan_page` directly
    would pass identically whether the ROUTE reaches it or still builds the
    whole catalogue — which is exactly the shape this defect had.

    `force_authenticate` rather than `request.user = …`: DRF's `Request.user`
    re-runs the authenticators and overwrites whatever the underlying Django
    request carried, so a direct assignment silently 401s.
    """
    from rest_framework.test import APIRequestFactory, force_authenticate

    request = APIRequestFactory().get("/api/brazosbend/plans", params)
    force_authenticate(request, user=env.owner)
    request.tenant_role = "system_admin"
    request.tenant_id = env.tenant.id
    return request


def _limit_50(queries):
    """The captured statements that take FIFTY rows — the page, in SQL.

    ⚠ **`LIMIT 50` AND NOT `LIMIT` (a false pass this case had to be designed
    out of).** `plan_queryset` annotates two `Subquery(...[:1])` expressions,
    which Django renders as `LIMIT 1` INSIDE the SELECT list, and the plans
    roll-up runs its own counts. A check for the word `LIMIT` would therefore
    have gone green on the unfixed code for `GET /plans` — reporting success
    over the one endpoint with the worst breach in it.
    """
    return [q for q in queries if re.search(r"\bLIMIT\s+50\b", q["sql"], re.I)]


# ══════════════════════════════════════════════════════════════════════════
# 1 · THE PAGE IS TAKEN IN SQL — the case that goes red on the old code
# ══════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("label,view_name,seed,table", LISTS, ids=[row[0] for row in LISTS])
def test_every_list_endpoint_asks_the_database_for_one_page(env, label, view_name, seed, table):
    """`NFR-3`: the page is a SQL `LIMIT`, not a Python slice of the tenant."""
    view = getattr(rating_api, view_name)
    with tenant_ctx(env.tenant):
        seed(env, PAGE + 10)
        with CaptureQueriesContext(connection) as ctx:
            body = view(_request(env)).data
    limited = _limit_50(ctx.captured_queries)
    assert limited, (
        f"{label} sent no `LIMIT 50` — the page was taken in Python, which is "
        f"DEF-RAT-5742. Statements: {len(ctx.captured_queries)}"
    )
    assert any(table in q["sql"] for q in limited), (
        f"{label} sent a `LIMIT 50`, but not over {table!r} — the page is being "
        f"taken somewhere other than the list's own query"
    )
    assert body["count"] == PAGE + 10, "the count must be the WHOLE set, not the page"
    assert len(body["results"]) == PAGE


@pytest.mark.parametrize("label", list(PAGES), ids=list(PAGES))
def test_the_total_is_a_sql_count_and_not_a_len(env, label):
    """The envelope's `count` is `COUNT(*)` over the filtered set.

    ⚠ **THIS IS THE OTHER HALF OF `NFR-3` AND IT IS EASY TO LOSE.** A page taken
    in SQL whose total is still `len(everything)` has moved the cost and not
    removed it — the tenant is still built, just for a number. Read at the
    SELECTOR here rather than at the view, because `GET /plans` also serves
    `rating_rollup`, which issues counts of its own and would make this case
    pass wrongly on the wire.
    """
    page_fn, _ = _pair(label)
    seed = dict((row[0], row[2]) for row in LISTS)[label]
    with tenant_ctx(env.tenant):
        seed(env, PAGE + 10)
        with CaptureQueriesContext(connection) as ctx:
            rows, total = page_fn(ListParams(page=1, per=PAGE))
    assert total == PAGE + 10 and len(rows) == PAGE
    assert any("COUNT(" in q["sql"].upper() for q in ctx.captured_queries), (
        f"{label}'s total was counted in Python — the whole set was built to produce it"
    )


# ══════════════════════════════════════════════════════════════════════════
# 2 · THE COST DOES NOT FOLLOW THE TENANT
# ══════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize(
    "label,view_name,seed",
    [(row[0], row[1], row[2]) for row in LISTS if row[0] in ("GET /plans", "GET /rate-schedules")],
    ids=["GET /plans", "GET /rate-schedules"],
)
def test_the_statement_count_does_not_follow_the_tenant(env, label, view_name, seed):
    """One screen costs the same on a big utility as on a small one (`NFR-3`).

    These two lists are the ones whose ROW BUILDER reads the database: `plan_row`
    issues two statements per plan (`plan_services` and `plan_rate_schedules`)
    and `schedule_card` issues several per schedule. So on the unfixed code the
    cost grew with the CATALOGUE, and this case measures exactly that and
    nothing else — it doubles the population and requires the number not to
    move.
    """
    view = getattr(rating_api, view_name)
    with tenant_ctx(env.tenant):
        seed(env, PAGE + 10)
        with CaptureQueriesContext(connection) as small:
            view(_request(env))
        seed(env, PAGE + 10, offset=1000)
        with CaptureQueriesContext(connection) as large:
            view(_request(env))
    assert len(large.captured_queries) == len(small.captured_queries), (
        f"{label} cost {len(small.captured_queries)} statements at {PAGE + 10} rows and "
        f"{len(large.captured_queries)} at {2 * (PAGE + 10)} — the cost is following the "
        f"tenant, which is DEF-RAT-5742"
    )


# ══════════════════════════════════════════════════════════════════════════
# 3 · THE ENVELOPE DID NOT CHANGE
# ══════════════════════════════════════════════════════════════════════════
ENVELOPE = ("count", "next", "previous", "results")


@pytest.mark.parametrize("label,view_name,seed,table", LISTS, ids=[row[0] for row in LISTS])
def test_the_envelope_is_the_house_one_and_page_two_is_a_different_page(
    env, label, view_name, seed, table
):
    """`count` / `next` / `previous` / `results`, in that order, exactly as the
    thirty endpoints that still hand the paginator a queryset serve it. A second
    envelope shape on five catalogue screens would be a client-side special case
    for ever."""
    view = getattr(rating_api, view_name)
    with tenant_ctx(env.tenant):
        seed(env, PAGE + 10)
        first = view(_request(env, page=1)).data
        second = view(_request(env, page=2)).data
    assert tuple(first)[:4] == ENVELOPE, f"{label} changed the envelope: {tuple(first)}"
    assert first["count"] == second["count"] == PAGE + 10
    assert len(first["results"]) == PAGE and len(second["results"]) == 10
    assert first["results"] != second["results"], (
        f"{label} page 2 is page 1 — the page is not reaching SQL"
    )
    assert first["next"] and not first["previous"]
    assert second["previous"] and not second["next"]
    assert "page=2" in first["next"]
    assert "page=" not in second["previous"], (
        "the link back to page 1 REMOVES the parameter, exactly as DRF builds it"
    )


def test_the_plans_rollup_still_rides_beside_the_envelope(env):
    """⚠ **SPREAD, DO NOT PASS.** `_paginated` appended `extra` onto the DRF
    body after the four keys; `_prepaged` has to do the same or the S9 header
    roll-up — six counts the screen draws above the table — silently becomes a
    dash. It is the `DEF-AST-4120` shape, and nothing else in this file would
    notice it."""
    with tenant_ctx(env.tenant):
        _plans(env, PAGE + 10)
        body = rating_api.plans(_request(env)).data
    assert "rollup" in body, "the S9 header roll-up was dropped from the envelope"
    assert tuple(body) == (*ENVELOPE, "rollup"), (
        "the roll-up must come AFTER the four keys, where `_paginated` put it"
    )
    assert body["rollup"]["plans"] >= PAGE + 10


# ══════════════════════════════════════════════════════════════════════════
# 4 · BR-SHL-011 — clamp, never error
# ══════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("label,view_name,seed,table", LISTS, ids=[row[0] for row in LISTS])
def test_an_out_of_range_page_clamps_to_the_last_page(env, label, view_name, seed, table):
    """`BR-SHL-011`: an out-of-range page clamps into range and never errors.

    ⚠ **THE PARSER CANNOT DO THIS CLAMP AND `StandardPagination` IS NO LONGER IN
    THIS PATH.** `parse_list_params` clamps `page` to >= 1 and has counted
    nothing, so it cannot know the last page; `get_page_number` did the rest for
    the queryset path and this path does not go through it. Without the re-clamp
    in `_prepaged`, `?page=999` on a two-page list serves an EMPTY table with a
    `previous` link to page 998 — which is not an error and is therefore exactly
    the kind of wrong a screen shows in silence.
    """
    with tenant_ctx(env.tenant):
        seed(env, PAGE + 10)
        body = getattr(rating_api, view_name)(_request(env, page=999)).data
    assert body["count"] == PAGE + 10
    assert len(body["results"]) == 10, f"{label} served a blank table for an out-of-range page"
    assert body["next"] is None and body["previous"], "the clamped page is the LAST page"


def test_page_zero_and_a_garbage_page_both_open_on_page_one(env):
    """The other end of the same rule — neither may 4xx."""
    with tenant_ctx(env.tenant):
        _charges(env, PAGE + 10)
        for raw in (0, -3, "banana"):
            body = rating_api.charges(_request(env, page=raw)).data
            assert len(body["results"]) == PAGE and body["previous"] is None, raw


# ══════════════════════════════════════════════════════════════════════════
# 5 · A PAGE IS THE WHOLE LIST, SLICED — no figure and no ordering moved
# ══════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("label", list(PAGES), ids=list(PAGES))
def test_a_page_is_the_whole_answer_sliced(env, label):
    """The SQL page and the whole ordered list must not be able to disagree.

    ⚠ **THIS IS THE HARD-RULE-2 AND `BR-RAT-088` GUARD.** The row builders were
    not touched by this change and must not be: `charge_row` is still the one
    place a charge code's base amount is answered, `tax_row` still renders a
    rate at its six stored places with its two-place display companion. Asserting
    the page is byte-identical to the same slice of the list that shipped is how
    a later 'simplification' of one path goes red instead of quietly moving a
    price.
    """
    page_fn, list_fn = _pair(label)
    seed = dict((row[0], row[2]) for row in LISTS)[label]
    with tenant_ctx(env.tenant):
        seed(env, PAGE + 10)
        whole = list_fn(ListParams(page=1, per=PAGE))
        first, total = page_fn(ListParams(page=1, per=PAGE))
        second, _ = page_fn(ListParams(page=2, per=PAGE))
    assert total == len(whole)
    assert first == whole[:PAGE]
    assert second == whole[PAGE : 2 * PAGE]


# ══════════════════════════════════════════════════════════════════════════
# 6 · THE DERIVED PATHS STILL NARROW (DEF-387's reasoning, kept)
# ══════════════════════════════════════════════════════════════════════════
def test_a_derived_filter_still_narrows_and_still_pages(env):
    """`f.status` on taxes, `f.type` on discounts and `f.structure` on schedules
    read a value DERIVED from the version in force, not a column. They are NOT
    re-implemented in SQL — `DEF-387` records why — so each one is served by the
    `O(tenant)` fallback, which must still narrow and must still page.

    ⚠ **THE PREDICATE IS NAMED RATHER THAN HIDDEN**, which is the difference
    between an exception somebody can count and a check reporting zero over a
    scope it silently excludes.
    """
    with tenant_ctx(env.tenant):
        _taxes(env, PAGE + 10)
        _discounts(env, PAGE + 10)
        assert selectors.tax_list_is_sql_pageable(ListParams())
        assert not selectors.tax_list_is_sql_pageable(ListParams(filters={"status": "active"}))
        assert selectors.discount_list_is_sql_pageable(ListParams(filters={"type": "all"}))
        assert not selectors.discount_list_is_sql_pageable(
            ListParams(filters={"verification": "annual"})
        )
        assert selectors.schedule_list_is_sql_pageable(ListParams(sort="name"))
        assert not selectors.schedule_list_is_sql_pageable(ListParams(sort="accounts"))
        assert not selectors.schedule_list_is_sql_pageable(
            ListParams(filters={"structure": "tiered"})
        )

        narrow = ListParams(page=1, per=PAGE, filters={"status": "active"})
        rows, total = selectors.tax_page(narrow)
        whole = selectors.tax_list(narrow)
    assert total == len(whole) and rows == whole[:PAGE]
    assert all(row["status"] == "active" for row in rows), (
        "the fallback stopped narrowing — a derived filter that pages but does "
        "not filter is worse than one that does neither"
    )


def test_a_derived_sort_still_orders_the_whole_set_and_not_the_page(env):
    """The seven derived schedule sorts order EVERY matching card and then take
    the page — never the other way round, which would sort fifty arbitrary rows
    and call it an ordering."""
    with tenant_ctx(env.tenant):
        _schedules(env, PAGE + 10)
        params = ListParams(page=2, per=PAGE, sort="status", dir="desc")
        rows, total = selectors.schedule_page(params)
        whole = selectors.schedule_list(params)
    assert total == len(whole)
    assert rows == whole[PAGE : 2 * PAGE]


# ══════════════════════════════════════════════════════════════════════════
# 7 · HARD RULE 1 — a page reaches one tenant
# ══════════════════════════════════════════════════════════════════════════
def test_a_page_never_reaches_another_tenants_catalogue(env, other_env):
    """Hard rule 1. The `WHERE tenant_id` moved from `plan_list` into
    `plan_list_queryset`; this is the case that says it travelled."""
    with tenant_ctx(env.tenant):
        _charges(env, PAGE + 10)
    with tenant_ctx(other_env.tenant):
        _charges(other_env, 3, offset=9000)
        rows, total = selectors.charge_page(ListParams(page=1, per=PAGE))
    assert total == 3, "the count crossed a tenant boundary"
    assert all(row["code"].startswith("BULK-9") for row in rows)


# ══════════════════════════════════════════════════════════════════════════
# 8 · NFR-5 — nothing here caps anything
# ══════════════════════════════════════════════════════════════════════════
def test_a_thousand_row_page_is_served_whole(env):
    """`NFR-5`: no hard caps. `per=1000` is the top of the IS-2 vocabulary and
    it must return a thousand rows, not a capped fifty — the fix must not have
    bought its speed with a ceiling somebody has to remove at T4."""
    with tenant_ctx(env.tenant):
        _charges(env, 120)
        body = rating_api.charges(_request(env, per=1000)).data
    assert body["count"] == 120 and len(body["results"]) == 120
    assert body["next"] is None and body["previous"] is None
