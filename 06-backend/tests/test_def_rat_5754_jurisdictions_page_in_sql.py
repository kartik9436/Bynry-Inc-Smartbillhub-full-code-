# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-RAT-5754 — `GET /tax-jurisdictions` had no pager AT ALL. It
#          returned `selectors.jurisdiction_list()` straight to `Response`, so
#          the wire carried a bare `TaxJurisdiction[]`: no `count`, no `per`,
#          no page, and nothing bounding a tenant-wide read. It is the SEVENTH
#          list in Plans & Rates and the one `DEF-RAT-5742` could not find —
#          that lane grepped for `_paginated`, which by construction cannot see
#          a read that never reached the paginator at all.
# Rules:   NFR-3 (universal server pagination; `core/pagination.py` — an
#          endpoint *"has to go out of its way to be unbounded, and none may"*)
#          · NFR-5 (no hard caps anywhere) · BR-SHL-011 (a list URL clamps,
#          never 4xx) · BR-SHL-033 (a dropdown past LONG_LIST_THRESHOLD is a
#          type-ahead — so a picker that can see only page 1 is a NEW defect,
#          not a fix) · BR-TEN-037 (jurisdictions are tenant-entered; there is
#          no global registry) · hard rule 1 (tenant scoping) · DEF-RAT-5742
#          (the same fix on this module's other six lists, whose shape this
#          follows) · CR-029 RC-W5-T6 (the same wire change on `/routes` and
#          `/cycles`, whose CLIENT half this one copies)
# Tests:   this file · 07-frontend/src/api/taxJurisdictions.def5754.test.ts
#          (the client half — they are ONE commitment and neither proves the
#          fix alone)
# Impacts: apps/rating/api.py (`tax_jurisdictions` → `_prepaged`) ·
#          apps/rating/selectors.py 🔒 (`jurisdiction_list_queryset` /
#          `jurisdiction_page`; `jurisdiction_list` widened, not replaced)
# ───────────────────────────────────────────────────────
"""DEF-RAT-5754 — `GET /tax-jurisdictions` takes its page in the DATABASE.

RED-FIRST PROOF (hard-won law 7, in the harness that runs it — `pytest`, never
a `__main__`). Every case below was run with `pytest` against a second worktree
pinned at `14f7ffd59`, the tip this lane started from, BEFORE the fix existed.
The failures are quoted in the lane report. The two that matter most:

  * `test_the_endpoint_asks_the_database_for_one_page` fails on the OLD code
    with *"GET /tax-jurisdictions sent no `LIMIT 50` — the page was taken in
    Python (or not at all)"*. It is aimed at the VIEW and not at the new
    selector precisely so that it CAN fail on a tree where the new selector
    does not exist: a case calling `selectors.jurisdiction_page` would fail
    with `AttributeError`, which proves a function was added and says nothing
    about where the page is taken.
  * `test_the_wire_is_the_house_envelope` fails on the OLD code with the body
    being a `list` — which is the defect stated in one line.

⚠ **THE OLD SHAPE WAS NOT A SLOW PAGE, IT WAS NO PAGE** — which makes this
defect's red proof EASIER than `DEF-RAT-5742`'s and its regression risk WORSE.
Easier, because the envelope simply is not there and any assertion about
`count` fails loudly. Worse, because the response SHAPE changes on the wire, so
every consumer breaks at once if one is missed. There is exactly one consumer,
`getTaxJurisdictions`, and it changes in the same commit; `test_the_picker_can
_still_reach_a_jurisdiction_that_is_not_on_page_one` is the backend half of
proving that consumer still works.

⚠ **A CASE THAT COUNTS RETURNED ROWS CANNOT TELL SQL PAGING FROM PYTHON
PAGING.** Had this endpoint been wired to DRF's paginator over a built list —
the shape `DEF-RAT-5742` fixed — the rows, the `count` and the `next` link
would all have been correct and only the WORK would have been wrong. So the
paging cases here assert the SQL that was sent or the number of statements it
took, never a row count on its own.

⚠ **TWO CASES PASS ON THE OLD TREE AND THE MORE INTERESTING ONE IS A CHECK
THAT CANNOT SEE THIS DEFECT AT ALL** (law 7's *ask what would make this check
pass wrongly*, answered rather than asked). Measured: **11 failed, 2 passed**
at `14f7ffd59`.

  * `test_the_statement_count_does_not_follow_the_tenant` **PASSES on the
    unfixed code**, and that is not a weakness in the case — it is the shape
    of this defect. The old path was **ONE statement** that happened to return
    the whole tenant, so the cost lived in ROWS and never in STATEMENTS. This
    is the exact inverse of `DEF-RAT-5742`, where a statement count WAS the
    proof because `plan_row` re-queried per row. **So a lane porting that
    file's cases here and stopping at the statement count would have found
    nothing wrong with an endpoint serving a catalogue of ANY size in one
    unbounded response.** The case is kept because it pins the fixed cost at
    two statements, not because it demonstrates anything.
  * `test_the_no_argument_whole_set_read_still_works` passes on both trees by
    design: it guards the five non-screen callers of `jurisdiction_list()`,
    whose behaviour this lane deliberately did not change.

⚠ **AND `test_the_default_order_is_the_one_the_picker_has_always_had` FAILS ON
THE OLD TREE FOR A REASON THAT IS NOT THE ORDER** — `AttributeError: module
'apps.rating.selectors' has no attribute 'jurisdiction_page'`. It is a
REGRESSION guard, so on a tree where the fix exists it can only go red if this
lane reordered a live picker; on a tree where the fix does not exist it merely
says the function is absent. **That distinction is written here because an
earlier draft of this docstring claimed the case was green on both trees, and
it was not** — a docstring asserting a test property nobody re-checked is
hard-won law 1 inside a test file.
"""

import re

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.rating import api as rating_api
from apps.rating import models, selectors
from core.pagination import DEFAULT_PAGE_SIZE, ListParams

from tests.test_us_rat_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_rat_helpers import seeding_ctx, tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db

PAGE = DEFAULT_PAGE_SIZE  # 50 — IS-2's smallest page, and the one a screen opens on


def _jurisdictions(env, count, *, offset=0, prefix="Bulk"):
    """A catalogue of a size no fixture in this repo builds.

    `bulk_create` and not the service layer: what is under test is the COST of
    reading a big catalogue, and nothing here prices anything — no case in this
    file asserts a money value.

    Names are zero-padded so that `name` ordering and creation order agree,
    which lets a case say *"the 60th row by name"* and mean something.
    """
    with seeding_ctx(env.tenant):
        models.TaxJurisdiction.objects.bulk_create(
            [
                models.TaxJurisdiction(
                    tenant=env.tenant,
                    name=f"{prefix} jurisdiction {offset + i:04d}",
                    authority=f"{prefix} authority {offset + i:04d}",
                    level="city",
                    reference_no=f"REF-{offset + i:05d}",
                )
                for i in range(count)
            ]
        )


def _request(env, **params):
    """A real DRF request for the VIEW, not a call to the selector underneath.

    ⚠ **THE VIEW IS THE THING UNDER TEST.** `_prepaged` is what replaced the
    bare `Response(selectors.jurisdiction_list())`, and a case that called
    `selectors.jurisdiction_page` directly would pass identically whether the
    ROUTE reaches it or still serves the whole tenant — which is exactly the
    shape this defect had.

    `force_authenticate` rather than `request.user = …`: DRF's `Request.user`
    re-runs the authenticators and overwrites whatever the underlying Django
    request carried, so a direct assignment silently 401s.
    """
    from rest_framework.test import APIRequestFactory, force_authenticate

    request = APIRequestFactory().get("/api/brazosbend/tax-jurisdictions", params)
    force_authenticate(request, user=env.owner)
    request.tenant_role = "system_admin"
    request.tenant_id = env.tenant.id
    return request


def _limit(queries, size):
    """The captured statements that take exactly `size` rows — the page, in SQL.

    ⚠ **`LIMIT <size>` AND NOT `LIMIT` (a false pass this had to be designed
    out of).** Django renders `LIMIT 1` inside a `Subquery(...[:1])` and
    `COUNT(*)` queries can carry limits of their own, so a check for the WORD
    `LIMIT` can go green on a tree that never paged anything. The size is the
    assertion.
    """
    return [q for q in queries if re.search(rf"\bLIMIT\s+{size}\b", q["sql"], re.I)]


# ══════════════════════════════════════════════════════════════════════════
# 1 · THE PAGE IS TAKEN IN SQL — the cases that go red on the old code
# ══════════════════════════════════════════════════════════════════════════
def test_the_endpoint_asks_the_database_for_one_page(env):
    """`NFR-3`: the page is a SQL `LIMIT`, not a Python slice of the tenant."""
    with tenant_ctx(env.tenant):
        _jurisdictions(env, PAGE + 10)
        with CaptureQueriesContext(connection) as ctx:
            body = rating_api.tax_jurisdictions(_request(env)).data

    limited = _limit(ctx.captured_queries, PAGE)
    assert limited, (
        "GET /tax-jurisdictions sent no `LIMIT 50` — the page was taken in "
        f"Python (or not at all), which is DEF-RAT-5754. Statements: "
        f"{len(ctx.captured_queries)}"
    )
    assert any("tax_jurisdictions" in q["sql"] for q in limited), (
        "a `LIMIT 50` was sent, but not over `tax_jurisdictions` — the page is "
        "being taken somewhere other than this list's own query"
    )
    assert body["count"] == PAGE + 10, "the count must be the WHOLE set, not the page"
    assert len(body["results"]) == PAGE


def test_the_wire_is_the_house_envelope(env):
    """`count` / `next` / `previous` / `results`, in that order — and NOT a
    bare array, which is the defect in one line.

    The KEY ORDER is asserted because this product has two live list
    conventions (`g114_envelope_allowed.txt` records both) and a third spelling
    of the same four facts is what `paginated.ts` exists to prevent.
    """
    with tenant_ctx(env.tenant):
        _jurisdictions(env, 3)
        body = rating_api.tax_jurisdictions(_request(env)).data

    assert not isinstance(body, list), (
        "GET /tax-jurisdictions served a BARE ARRAY — that is DEF-RAT-5754 "
        "exactly, and it is the shape no other tenant-wide list in this "
        "product serves"
    )
    assert list(body.keys()) == ["count", "next", "previous", "results"]
    assert body["count"] == 3
    assert body["previous"] is None


def test_the_total_is_a_sql_count_and_not_a_len(env):
    """The other half of `NFR-3`, and the half that is easy to lose.

    A page taken in SQL whose total is still `len(everything)` has MOVED the
    cost, not removed it — the whole tenant is still built, just for a number.
    Read at the SELECTOR here so that nothing else in the view can make it pass
    wrongly.
    """
    with tenant_ctx(env.tenant):
        _jurisdictions(env, PAGE + 10)
        with CaptureQueriesContext(connection) as ctx:
            rows, total = selectors.jurisdiction_page(ListParams())

    assert total == PAGE + 10
    assert len(rows) == PAGE
    assert any("COUNT(*)" in q["sql"].upper() for q in ctx.captured_queries), (
        "the envelope's `count` was not a SQL COUNT(*) — it is a `len()` over "
        "rows somebody built, which is the cost this defect is about"
    )
    assert len(ctx.captured_queries) == 2, (
        "one page should cost exactly two statements — the COUNT and the "
        f"LIMIT/OFFSET. Got {len(ctx.captured_queries)}"
    )


def test_the_statement_count_does_not_follow_the_tenant(env):
    """`NFR-3`'s actual promise: the cost of ONE SCREEN is independent of how
    big the tenant is.

    ⚠ **WRITTEN AS *THE COST DID NOT MOVE*, NEVER AS A LITERAL** (the form
    `test_cr092_asset_paging.py` argues for). An equality against a number goes
    red the day an unrelated lane adds a `select_related`, which teaches the
    next reader to edit the number instead of looking at it.
    """
    with tenant_ctx(env.tenant):
        _jurisdictions(env, 60)
        with CaptureQueriesContext(connection) as small:
            rating_api.tax_jurisdictions(_request(env))

        _jurisdictions(env, 180, offset=1000)
        with CaptureQueriesContext(connection) as large:
            rating_api.tax_jurisdictions(_request(env))

    assert len(large.captured_queries) == len(small.captured_queries), (
        "the statement count followed the catalogue — 60 rows cost "
        f"{len(small.captured_queries)} and 240 cost {len(large.captured_queries)}"
    )


# ══════════════════════════════════════════════════════════════════════════
# 2 · THE PICKER — BR-SHL-033. Paging the server is only half a fix.
# ══════════════════════════════════════════════════════════════════════════
def test_the_picker_can_still_reach_a_jurisdiction_that_is_not_on_page_one(env):
    """A jurisdiction past the page size is still REACHABLE — by page and by
    search — or this "fix" removed a row a clerk could previously choose.

    ⚠ **THIS IS THE CASE THE WHOLE COMMITMENT TURNS ON.** `SearchSelectField`
    filters client-side and resolves the selected option's LABEL out of the
    same array, so a picker handed one page loses the type-ahead past row 50
    AND renders blank when reopening a tax whose jurisdiction sits past row 50.
    The client's answer is to follow `count`; this case proves the SERVER can
    be followed. Its client half is
    `07-frontend/src/api/taxJurisdictions.def5754.test.ts`, and neither half
    proves the fix alone.
    """
    with tenant_ctx(env.tenant):
        _jurisdictions(env, PAGE + 10)
        target = (
            models.TaxJurisdiction.objects.filter(tenant_id=env.tenant.id)
            .order_by("name", "id")[PAGE + 5]
        )

        first = rating_api.tax_jurisdictions(_request(env)).data
        second = rating_api.tax_jurisdictions(_request(env, page=2)).data
        searched = rating_api.tax_jurisdictions(_request(env, q=target.name)).data

    on_first = {row["id"] for row in first["results"]}
    assert str(target.id) not in on_first, (
        "the fixture is not exercising the case — the target must NOT be on "
        "page 1, or this case proves nothing"
    )
    assert str(target.id) in {row["id"] for row in second["results"]}, (
        "a jurisdiction past page 1 was unreachable by page — the picker "
        "would silently lose it (BR-SHL-033)"
    )
    assert [row["id"] for row in searched["results"]] == [str(target.id)], (
        "search did not find a jurisdiction past page 1 — so a type-ahead "
        "moved onto the server would not find it either"
    )
    # Following `count` from page 1 reaches the whole set — the client's loop,
    # stated as a server property so the two halves cannot drift.
    assert first["count"] == PAGE + 10
    assert first["next"] is not None


def test_the_default_order_is_the_one_the_picker_has_always_had(env):
    """`name`, then `id` — UNCHANGED by this lane.

    ⚠ **THIS IS A REGRESSION GUARD, NOT A DEMONSTRATION OF THE DEFECT.** A
    pager that quietly reorders a live picker changes what a clerk sees without
    changing what the product can do, which is harm no other case here would
    catch. It also pins the TIEBREAKER, without which a `LIMIT`/`OFFSET` may
    serve one row on two pages and omit a third.

    On the unfixed tree it fails with `AttributeError: … has no attribute
    'jurisdiction_page'` — the function is absent, which says nothing about
    order. Only on a tree where the fix exists does a red here mean what the
    name says.
    """
    with tenant_ctx(env.tenant):
        _jurisdictions(env, 5, prefix="Zeta")
        _jurisdictions(env, 5, prefix="Alpha")
        whole = [row["name"] for row in selectors.jurisdiction_list()]
        page_one, _ = selectors.jurisdiction_page(ListParams())

    assert whole == sorted(whole), "the whole-set read is no longer name-ordered"
    assert [row["name"] for row in page_one] == whole[: len(page_one)], (
        "a page is no longer a PREFIX of the whole ordered set — the page and "
        "the list disagree about order, so following `count` would skip rows"
    )


def test_the_no_argument_whole_set_read_still_works(env):
    """`jurisdiction_list()` with NO arguments is unchanged — five callers
    depend on it (`seed_demo` three times, `sample_data` twice) and none of
    them passes params. Widening the signature rather than replacing it is what
    keeps them working."""
    with tenant_ctx(env.tenant):
        _jurisdictions(env, PAGE + 10)
        rows = selectors.jurisdiction_list()

    assert len(rows) == PAGE + 10, (
        "the whole-set read started paging — `seed_demo` and `sample_data` "
        "index the catalogue through it and would silently miss rows"
    )
    assert set(rows[0]) == {"id", "name", "authority", "level", "reference_no"}, (
        "the ROW shape moved; this lane changed the envelope, never the row"
    )


# ══════════════════════════════════════════════════════════════════════════
# 3 · BR-SHL-011 · NFR-5 · hard rule 1
# ══════════════════════════════════════════════════════════════════════════
def test_an_out_of_range_page_clamps_to_the_last_page(env):
    """`BR-SHL-011`: clamp, never error — and serve the LAST page's rows, not
    an empty table with a `previous` link into nowhere."""
    with tenant_ctx(env.tenant):
        _jurisdictions(env, PAGE + 10)
        body = rating_api.tax_jurisdictions(_request(env, page=999)).data

    assert body["count"] == PAGE + 10
    assert len(body["results"]) == 10, "the clamp did not re-fetch the last page"
    assert body["next"] is None


def test_page_zero_and_a_garbage_page_both_open_on_page_one(env):
    with tenant_ctx(env.tenant):
        _jurisdictions(env, PAGE + 10)
        zero = rating_api.tax_jurisdictions(_request(env, page=0)).data
        junk = rating_api.tax_jurisdictions(_request(env, page="nonsense")).data
        first = rating_api.tax_jurisdictions(_request(env)).data

    assert [r["id"] for r in zero["results"]] == [r["id"] for r in first["results"]]
    assert [r["id"] for r in junk["results"]] == [r["id"] for r in first["results"]]
    assert zero["previous"] is None and junk["previous"] is None


def test_an_unknown_sort_falls_back_and_never_errors(env):
    """`BR-SHL-011`: an undeclared sort falls back to the default rather than
    4xx-ing, and an undeclared `f.*` is ignored rather than becoming a column a
    client picked."""
    with tenant_ctx(env.tenant):
        _jurisdictions(env, 5)
        fallen = rating_api.tax_jurisdictions(_request(env, sort="reference_no")).data
        default = rating_api.tax_jurisdictions(_request(env)).data
        filtered = rating_api.tax_jurisdictions(
            _request(env, **{"f.level": "city"})
        ).data

    assert [r["id"] for r in fallen["results"]] == [r["id"] for r in default["results"]]
    assert filtered["count"] == 5, "an UNDECLARED filter narrowed the set"


def test_a_thousand_row_page_is_served_whole(env):
    """`NFR-5`: no cap anywhere. `per=1000` returns 1,000 rows — which is also
    what the client's follow-the-count loop asks for on every request."""
    with tenant_ctx(env.tenant):
        _jurisdictions(env, 1200)
        body = rating_api.tax_jurisdictions(_request(env, per=1000)).data

    assert body["count"] == 1200
    assert len(body["results"]) == 1000


def test_a_page_never_reaches_another_tenants_catalogue(env, other_env):
    """Hard rule 1 + `BR-TEN-037`. A `LIMIT`/`OFFSET` walks an ORDERED set, so
    a missing tenant predicate does not show up as a wrong row count — it shows
    up as somebody else's row on page two."""
    with tenant_ctx(other_env.tenant):
        _jurisdictions(other_env, 80, prefix="Intruder")
    with tenant_ctx(env.tenant):
        _jurisdictions(env, 5, prefix="Ours")
        first = rating_api.tax_jurisdictions(_request(env)).data
        second = rating_api.tax_jurisdictions(_request(env, page=2)).data

    assert first["count"] == 5, "the COUNT crossed the tenant boundary"
    names = [row["name"] for row in first["results"]] + [
        row["name"] for row in second["results"]
    ]
    assert all(name.startswith("Ours") for name in names), (
        f"another tenant's jurisdictions reached this page: {names}"
    )


def test_search_narrows_in_the_database_and_reaches_the_authority(env):
    """IS-3's two-character minimum, applied in SQL, over the three columns a
    clerk actually has in front of them."""
    with tenant_ctx(env.tenant):
        _jurisdictions(env, 40, prefix="Travis")
        _jurisdictions(env, 40, offset=500, prefix="Hays")
        with CaptureQueriesContext(connection) as ctx:
            by_name = rating_api.tax_jurisdictions(_request(env, q="Hays")).data
        by_authority = rating_api.tax_jurisdictions(_request(env, q="Travis authority")).data
        by_reference = rating_api.tax_jurisdictions(_request(env, q="REF-00507")).data
        one_char = rating_api.tax_jurisdictions(_request(env, q="H")).data

    assert by_name["count"] == 40
    assert by_authority["count"] == 40
    assert by_reference["count"] == 1
    assert one_char["count"] == 80, "a single character narrowed — IS-3 says two"
    assert any("LIKE" in q["sql"].upper() for q in ctx.captured_queries), (
        "the search was applied to built rows rather than in SQL, so the whole "
        "catalogue is still being read to answer it"
    )
