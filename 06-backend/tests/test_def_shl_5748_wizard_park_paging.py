# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-SHL-5748 — `GET /wizard-parks` built a dict for every parked
#           draft in the tenant and threw away all but fifty.
# Rules:    NFR-3 (universal server pagination) · NFR-5 (no hard caps) ·
#           BR-SHL-011 (an out-of-range page CLAMPS and never errors; `per`
#           clamps to the ratified sizes) · BR-SHL-048 (a parked draft relates
#           to nothing until it is executed) · CLAUDE.md hard rule 1 (a read
#           needs `app.tenant_id` set) · hard-won law 7 (prove a guard RED
#           first, and ask what would make it pass WRONGLY)
# Tests:    this file
# Impacts:  apps/tenancy/wizard_parks.py (`parks_queryset` beside `list_parks`)
#           · apps/tenancy/wizard_parks_api.py (the "Waiting on" list)
# ───────────────────────────────────────────────────────
"""DEF-SHL-5748 — the "Waiting on" page is taken in SQL, and that is asserted.

⚠ **A TEST THAT COUNTS RETURNED ROWS CANNOT TELL SQL PAGING FROM PYTHON PAGING,
AND THAT IS THE WHOLE REASON THIS DEFECT SURVIVED.** `StandardPagination` serves
the identical envelope either way — `count` / `next` / `previous` / `results`,
the same fifty rows, the same links — so every assertion in
`test_cr035_wizard_parks.py` passes on a tree that builds forty thousand dicts
to draw fifty. Hard-won law 7's second habit, applied: *what would make this
check pass wrongly?* A row count would. So the cases below assert the **SQL**.

**THE DISCRIMINATOR IS `LIMIT`, NOT A QUERY COUNT** — and that is worth stating
because a query count is the obvious instrument and it is the wrong one here.
The old code ran ONE statement (`SELECT … FROM wizard_parks` with no bound) and
the new code runs TWO (a `COUNT(*)`, then the page). **Paging in SQL makes the
number of statements go UP, from 1 to 2**, so a ceiling on the number of queries
would have been satisfied by the defect and broken by the fix. What actually
moved is that no statement fetches more rows than the screen shows, which is a
property of the statement rather than of how many there are.

⚠ **THE POPULATIONS HERE ARE SIXTY, NOT TWELVE, AND THAT IS NOT PADDING.** The
first draft of this file paged with `?per=5` — and `per` clamps to the ratified
vocabulary `(50, 100, 200, 500, 1000)`, so `5` became `50` and twelve rows all
came back on one page. **The case failed against the FIXED tree and the BROKEN
one alike**, which is exactly what a red-first run is for: a test written below
the smallest real page size cannot observe paging at all, on any tree. Sixty
rows at `per=50` is the smallest population that has a second page.

RED-FIRST PROOF (law 7), run in the harness that runs it
--------------------------------------------------------
Every case below was run with `pytest` against a second worktree pinned at the
tip this lane started from, holding the UNMODIFIED `wizard_parks.py` and
`wizard_parks_api.py`. The failures are quoted in the lane report; the shapes
were `AttributeError: module 'apps.tenancy.wizard_parks' has no attribute
'parks_queryset'`, an `AssertionError` printing the unbounded
`SELECT … FROM "wizard_parks" … ORDER BY …` with no `LIMIT` in it, and
`assert 60 == 50` where the whole table came back on page one.
"""

import re
import uuid

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from core import tenancy as core_tenancy

from apps.tenancy import wizard_parks as service
from apps.tenancy.models import WizardPark
from tests.test_us_idn_helpers import (  # noqa: F401 (fixture import)
    api_get,
    api_post,
    idn,
    signed_in_client,
)

pytestmark = pytest.mark.django_db

PARKS = "/wizard-parks"

#: The ratified default page. `per` clamps to `core.pagination.PAGE_SIZES`, so
#: there is no smaller page to ask for and a fixture below it cannot see a page
#: boundary at all.
PAGE = 50

#: The worked case CR-035 was ruled on — a clerk parks a move-in waiting on a
#: $150 deposit. The fixtures are that case so a failure reads as the ruling
#: rather than as `foo`/`bar`.
DEPOSIT_PARK = {
    "flow": "move_in",
    "subject_label": "Unit 12, 500 Main St",
    "subject_ref": {"unit_id": str(uuid.uuid4()), "premises_id": str(uuid.uuid4())},
    "step": 3,
    "values": {"applicant_name": "Rosa Delgado", "deposit_amount": "150.0000"},
    "waiting_on": "Waiting on a deposit",
    "park_note": "$150 deposit promised by Friday.",
    "remind_on": "2026-09-02",
}


def _clerk():
    """Priya, Billing Clerk — the person CR-035 was raised for."""
    return signed_in_client("priya@silvercreek.example", "Meadow2026sage")


def _seed(idn):
    """Silver Creek and its staff; returns the users namespace."""
    return idn.seed_silvercreek()


def _bulk_parks(idn, user, count, *, flow="move_in", start=1):
    """`count` parked drafts, written straight to the table.

    ⚠ **HARD RULE 1 — THE WRITE ENTERS THE TENANT CONTEXT THE SHIPPING KERNEL
    ENTERS.** `core.tenancy.tenant_context` is what a Celery task or a
    management command uses; outside it `app.tenant_id` is unset and a read of a
    tenant table answers nothing. It is used here rather than
    `isolation_helpers.live_tenant_context` because that helper swaps the FAKED
    connection back for the real one, which on the default SQLite tier fails on
    `no such function: set_config` — the GUC only exists on PostgreSQL.

    The endpoint is still exercised over the wire by every case; only the
    POPULATION is made this way, because sixty round trips through `POST
    /wizard-parks` to prove a `LIMIT` is a minute of nobody's time well spent.
    """
    with core_tenancy.tenant_context(idn.silvercreek.id):
        WizardPark.objects.bulk_create(
            [
                WizardPark(
                    tenant_id=idn.silvercreek.id,
                    flow=flow,
                    subject_label=f"Unit {index}, 500 Main St",
                    subject_ref={"unit_id": str(uuid.uuid4())},
                    step=3,
                    values={"applicant_name": "Rosa Delgado"},
                    waiting_on="Waiting on a deposit",
                    parked_by=user,
                )
                for index in range(start, start + count)
            ]
        )


def _park_statements(captured):
    """Every SELECT this request issued against the draft store.

    ⚠ **IT READS THE CAPTURED SQL AND NOT A COUNT.** A request signs a clerk in,
    resolves the tenant and reads a session, so the raw number moves whenever an
    unrelated lane touches the middleware; the statements against THIS table are
    the only ones this defect is about.
    """
    rows = []
    for query in captured:
        sql = query["sql"]
        if "wizard_parks" in sql.lower() and sql.lstrip()[:6].upper() == "SELECT":
            rows.append(sql)
    return rows


def _page_statements(statements):
    """The row-fetching SELECTs — everything that is not the paginator's COUNT."""
    return [sql for sql in statements if "COUNT(" not in sql.upper()]


# ── NFR-3 · the page reaches SQL ────────────────────────────────────────────


def test_parks_queryset_stays_lazy(idn):
    """The selector hands back a QUERYSET, and its slice carries a `LIMIT`.

    This is the assertion that fails with `AttributeError` on the old tree: the
    only function there was `list_parks`, which returned `list(qs…)`. A
    materialised list is not a weaker queryset — it is a different thing, and
    `paginate_queryset` treats it differently.
    """
    users = _seed(idn)
    _bulk_parks(idn, users.priya, 7)

    with core_tenancy.tenant_context(idn.silvercreek.id):
        rows = service.parks_queryset()
        assert not isinstance(rows, list), (
            "parks_queryset must stay lazy — a list here means the paginator slices "
            "in Python and no page ever reaches the database (NFR-3)"
        )
        sql, _params = rows[2:5].query.sql_with_params()
        assert "LIMIT" in sql.upper(), sql
        assert len(list(rows[2:5])) == 3


def test_the_page_reaches_sql(idn):
    """`GET /wizard-parks` over sixty drafts: the page is a `LIMIT`.

    ⚠ **THE OLD CODE FAILED HERE ON THE `LIMIT`, NOT ON THE ROWS.** It served
    this `count` and this `next` link over a `SELECT` with no bound at all.
    """
    users = _seed(idn)
    _bulk_parks(idn, users.priya, 60)
    clerk = _clerk()

    with CaptureQueriesContext(connection) as ctx:
        response = api_get(clerk, PARKS)
    assert response.status_code == 200

    statements = _park_statements(ctx.captured_queries)
    pages = _page_statements(statements)
    assert pages, f"no SELECT reached wizard_parks at all: {statements}"
    for sql in pages:
        assert "LIMIT" in sql.upper(), (
            "a row-fetching SELECT with no LIMIT means the whole match set came "
            f"back and Python threw it away (NFR-3): {sql}"
        )
    assert any("COUNT(" in sql.upper() for sql in statements), (
        "the paginator's COUNT(*) is missing, so `count` was computed by "
        "measuring a list it had already built"
    )


def test_no_statement_outgrows_the_screen(idn):
    """The bound in the SQL is the page size, and the wire agrees with it.

    Stated as *the LIMIT equals the page* rather than *a LIMIT exists*, because
    a `LIMIT` over a subquery that had already fetched everything would satisfy
    the weaker sentence.
    """
    users = _seed(idn)
    _bulk_parks(idn, users.priya, 60)
    clerk = _clerk()

    with CaptureQueriesContext(connection) as ctx:
        response = api_get(clerk, PARKS)
    assert response.status_code == 200

    pages = _page_statements(_park_statements(ctx.captured_queries))
    assert pages
    limits = {int(m.group(1)) for sql in pages for m in re.finditer(r"LIMIT\s+(\d+)", sql, re.I)}
    assert limits == {PAGE}, f"the statement asked the database for {limits or 'no bound'}"
    assert len(response.json()["results"]) == PAGE
    assert response.json()["count"] == 60


def test_query_shape_does_not_move_with_the_population(idn):
    """Three drafts and sixty-three: the same statements, and still bounded.

    ⚠ **A COUNT MEASURED ONCE PASSES ON A ONE-ROW FIXTURE FOR EVER**, which is
    how the sibling registry defect (DEF-MET-4951) survived against a tenant
    holding 126 assets. So the population is grown inside the case and the shape
    is asserted to be INDEPENDENT of it.

    It also guards the `select_related("parked_by")` that `row_dict` needs: the
    list prints who is waiting, and without the join that is one query per row —
    an N+1 that hides perfectly behind a correct envelope.
    """
    users = _seed(idn)
    clerk = _clerk()

    _bulk_parks(idn, users.priya, 3)
    with CaptureQueriesContext(connection) as small:
        assert api_get(clerk, PARKS).status_code == 200
    small_statements = _park_statements(small.captured_queries)

    _bulk_parks(idn, users.priya, 60, start=100)
    with CaptureQueriesContext(connection) as large:
        response = api_get(clerk, PARKS)
    assert response.status_code == 200
    large_statements = _park_statements(large.captured_queries)

    assert len(large_statements) == len(small_statements), (
        "the number of statements against the draft store moved with the number "
        f"of drafts: {len(small_statements)} at 3 rows, "
        f"{len(large_statements)} at 63 — that is a query per row"
    )
    for sql in _page_statements(large_statements):
        assert "LIMIT" in sql.upper(), sql
    assert len(response.json()["results"]) == PAGE


# ── the envelope and the clamp are UNCHANGED (regression) ───────────────────


def test_the_envelope_is_byte_for_byte_the_drf_one(idn):
    """`count` / `next` / `previous` / `results`, and nothing else.

    A second envelope shape on one screen is a client-side special case for
    ever — the sentence `customers.api._prepaged` makes about the accounts list.
    """
    users = _seed(idn)
    _bulk_parks(idn, users.priya, 60)
    clerk = _clerk()

    body = api_get(clerk, PARKS).json()
    assert set(body) == {"count", "next", "previous", "results"}
    assert body["count"] == 60
    assert len(body["results"]) == PAGE
    assert body["previous"] is None
    assert "page=2" in body["next"]

    second = api_get(clerk, f"{PARKS}?page=2").json()
    assert second["count"] == 60
    assert len(second["results"]) == 10
    assert second["previous"] is not None
    assert second["next"] is None

    #: Newest first, and the two pages do not overlap — the ordering survived
    #: moving into SQL, which a Python page would also have preserved and which
    #: is therefore asserted here rather than left implied.
    first_ids = {row["id"] for row in body["results"]}
    assert first_ids.isdisjoint({row["id"] for row in second["results"]})


def test_an_out_of_range_page_clamps_and_never_errors(idn):
    """BR-SHL-011 — `?page=999` on a two-page list serves the LAST page.

    `StandardPagination.get_page_number` does this clamp for the queryset path.
    It is asserted here because the endpoint CHANGED which path it is on.
    """
    users = _seed(idn)
    _bulk_parks(idn, users.priya, 60)
    clerk = _clerk()

    response = api_get(clerk, f"{PARKS}?page=999")
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 60
    assert len(body["results"]) == 10, "the clamp served a blank table, not the last page"
    assert body["next"] is None

    #: And garbage clamps the same way rather than 422-ing a list.
    assert api_get(clerk, f"{PARKS}?page=banana").status_code == 200


def test_the_row_shape_did_not_move(idn):
    """`row_dict` now runs over the PAGE; it must still produce the same row.

    Parked through the WIRE, not in bulk, so the shape asserted is the one a
    wizard actually creates. `parked_by_name` is the member that would break
    silently: it reads `park.parked_by.full_name`, so it depends on the
    `select_related` travelling with the queryset into the paginator.
    """
    _seed(idn)
    clerk = _clerk()
    assert api_post(clerk, PARKS, DEPOSIT_PARK).status_code == 201

    row = api_get(clerk, PARKS).json()["results"][0]
    assert set(row) >= {
        "id",
        "flow",
        "subject_label",
        "subject_ref",
        "step",
        "values",
        "waiting_on",
        "park_note",
        "remind_on",
        "parked_at",
        "parked_by",
        "parked_by_name",
        "age_days",
    }
    assert row["parked_by_name"] == "Priya Menon", "the parker's name is gone — the join was lost"
    assert row["subject_label"] == "Unit 12, 500 Main St"
    assert row["flow"] == "move_in"
    assert isinstance(row["age_days"], int)


def test_the_filters_still_narrow_in_sql(idn):
    """`?flow=` and `?mine=` are filters on the QUERYSET, not on the page.

    ⚠ **THIS IS THE CASE THAT WOULD HAVE CAUGHT A LAZY FIX.** Both populations
    are larger than one page, so a filter applied to the fifty rows a caller was
    handed would answer *ten* where the truth is sixty — hard-won law 7's
    *reporting zero over a scope it silently excludes*, in a list control.
    """
    users = _seed(idn)
    _bulk_parks(idn, users.priya, 60, flow="move_in")
    _bulk_parks(idn, users.alex, 55, start=500, flow="move_out")
    clerk = _clerk()

    move_outs = api_get(clerk, f"{PARKS}?flow=move_out").json()
    assert move_outs["count"] == 55
    assert {row["flow"] for row in move_outs["results"]} == {"move_out"}

    mine = api_get(clerk, f"{PARKS}?mine=true").json()
    assert mine["count"] == 60, "?mine= is Priya's own drafts, and Alex parked the other 55"

    everything = api_get(clerk, PARKS).json()
    assert everything["count"] == 115, "?mine= is a FILTER and not a boundary"


# ── the seam contract the fix deliberately did NOT change ───────────────────


def test_list_parks_still_returns_a_real_list(idn):
    """`list_parks` is kept, and kept MATERIALISED, on purpose.

    Its remaining caller is `apps.customers.seams.wizard_park_rows`, whose own
    caller `sample_data` **deletes rows while iterating what it is handed**.
    That is safe over a list and is safe over a queryset only by accident of the
    result cache, so the fixture path keeps the list and the SCREEN gets the
    queryset. This case is what stops a later lane "simplifying" the two into
    one — the docstring says so, and a docstring is not a guarantee (law 1).
    """
    users = _seed(idn)
    _bulk_parks(idn, users.priya, 3)

    with core_tenancy.tenant_context(idn.silvercreek.id):
        rows = service.list_parks(flow="move_in")
    assert isinstance(rows, list)
    assert len(rows) == 3
    assert all(isinstance(row, WizardPark) for row in rows)
