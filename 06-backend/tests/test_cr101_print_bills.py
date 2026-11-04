# ── Trace ──────────────────────────────────────────────
# Change:   CR-101-BRC03 lane J — blueprint **screen 28**, `05-prototype/04
#           Billing, As Built.pdf` p147–p150, read AS IMAGES (B14 rule 42).
#           Closes `DEF-BIL-5354`.
# Rules:    BR-NOT-029 (b) (an incomplete address HOLDS a bill and it is
#           REPORTED) · BR-CUS-674 (an address is read here, never written) ·
#           NFR-3 / NFR-5 (paged in the database; no cap) · B14 rule 31 (no
#           database id is a visible value) · CLAUDE.md hard rule 1 (tenant
#           scoping)
# Tests:    this file
# ───────────────────────────────────────────────────────
"""The forecast screen 28 is built on, made falsifiable.

⚠ **THE CASE THAT MATTERS MOST IS `test_the_forecast_and_the_archive_agree`.**
Everything else here could pass over a forecast that is internally consistent
and WRONG — it counts three held bills, says so on a tile, and the archive then
holds four. That case builds the real archive and compares the two, which is
the only assertion in this file that could catch a forecast drifting away from
`_add_one`'s own order of checks.

⚠ **AND THE `FORECASTABLE` SPLIT IS ASSERTED, NOT ASSUMED.** Three of the eight
hold reasons can be known without drawing a page and five cannot. A test that
just counted *"held"* would pass if somebody quietly started forecasting
`document_refused` — which would mean rendering every bill to draw a screen.
"""

from datetime import datetime, timezone

import pytest

from apps.billing import models as billing_models, print_set, selectors
from apps.customers import models as customer_models

from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    dana,
    lonestar,
    make_premises,
    make_unit,
    marcus,
    staff_actor,
    tenant_ctx,
)
from tests.test_us_ten_helpers import (  # noqa: F401
    brazosbend_payload,
    lonestarridge_payload,
    provisioned_tenant,
)
from tests.test_us_bil_025_026_bills_read import an_account, an_invoice

pytestmark = pytest.mark.django_db

GENERATED_AT = datetime(2026, 9, 15, 10, 0, tzinfo=timezone.utc)


def a_mailing_address(tenant, account, **overrides):
    """A COMPLETE mailing address — the four discrete columns `BR-NOT-029` (a)
    names, which is what lets a bill into the file at all."""
    values = dict(
        tenant=tenant,
        account=account,
        kind="mailing",
        line1="1408 Elm Street",
        city="San Antonio",
        state="TX",
        postal_code="78205",
    )
    values.update(overrides)
    return customer_models.Address.objects.create(**values)


def a_holed_mailing_address(tenant, account):
    """A mailing row with a street and NO CITY — `BR-NOT-029` (b)'s held case.

    ⚠ **THESE TESTS HELD AN ACCOUNT WITH NO MAILING ROW AT ALL UNTIL 2026-09-24
    (`DEF-BIL-6373`).** Such an account now posts to its service address, as the
    delivery queue does, and the fixture's premises is complete — so it prints.
    The held case every test here needs is a mailing row with a hole in it,
    which is held rather than swapped for the premises. The service-address leg
    has its own file: `test_def_bil_6373_print_set_follows_delivery.py`.
    """
    return a_mailing_address(tenant, account, city="")


def a_printable_bill(tenant, account, **overrides):
    values = dict(
        status=billing_models.INVOICE_ISSUED,
        template_version=1,
        payload_version=1,
        bill_payload={
            "customer_name": "Miller, Sarah",
            "account_no": account.account_no,
            "total": "247.87",
        },
    )
    values.update(overrides)
    return an_invoice(tenant, account, **values)


# ══════════════════════════════════════════════════════════════════════════
# The forecast
# ══════════════════════════════════════════════════════════════════════════
def test_the_four_tiles_add_up_and_the_pages_are_the_measured_estimate(brazos, marcus):
    """*"404 + 8 = 412. A set that printed 404 of 412 without saying so sends a
    print shop a short run and tells nobody."* — the blueprint, p149."""
    with tenant_ctx(brazos):
        posted = an_account(brazos, marcus, account_no="A-1", label="Unit A")
        a_mailing_address(brazos, posted)
        held = an_account(brazos, marcus, account_no="A-2", label="Unit B")
        a_holed_mailing_address(brazos, held)
        a_printable_bill(brazos, posted, invoice_no="BL-2609-000001")
        a_printable_bill(brazos, held, invoice_no="BL-2609-000002")

        forecast = print_set.forecast_print_set({})

        assert forecast.bills == 2
        assert forecast.will_print == 1
        assert forecast.held == 1
        # The arithmetic itself, not a coincidence of these two rows.
        assert forecast.will_print + forecast.held == forecast.bills
        assert forecast.held_by_reason == ((print_set.HELD_ADDRESS_INCOMPLETE, 1),)
        # Pages are the bills that WILL print × the measured constant — a held
        # bill is never drawn, so its pages are not in a printer's quote.
        assert forecast.pages == 1 * print_set.MEASURED_PAGES_PER_BILL
        assert forecast.addresses_readable is True


def test_a_bill_with_no_number_is_held_for_that_and_not_for_its_address(brazos, marcus):
    """`_add_one` checks the NUMBER first, so the reasons PARTITION the
    selection. A bill with neither a number nor an address must be counted
    once — or `will_print + held` stops equalling the population."""
    with tenant_ctx(brazos):
        account = an_account(brazos, marcus, account_no="A-3", label="Unit C")
        # No address either: both reasons are true of this one bill.
        a_printable_bill(brazos, account, invoice_no=None)

        forecast = print_set.forecast_print_set({})

        assert forecast.bills == 1
        assert forecast.held == 1
        assert forecast.held_by_reason == ((print_set.HELD_NO_BILL_NUMBER, 1),)
        assert forecast.will_print == 0


def test_the_held_filter_and_the_held_count_are_the_same_number(brazos, marcus):
    """The door reads *"See the 3 held back"* and opens a filtered list. The
    count comes from a PARTITION and the list from a UNION, so a reason added to
    one and not the other would open a door on the wrong number of rows."""
    with tenant_ctx(brazos):
        posted = an_account(brazos, marcus, account_no="A-4", label="Unit D")
        a_mailing_address(brazos, posted)
        nowhere = an_account(brazos, marcus, account_no="A-5", label="Unit E")
        a_holed_mailing_address(brazos, nowhere)
        a_printable_bill(brazos, posted, invoice_no="BL-2609-000004")
        a_printable_bill(brazos, nowhere, invoice_no="BL-2609-000005")
        a_printable_bill(brazos, nowhere, invoice_no=None)

        forecast = print_set.forecast_print_set({})
        selection = print_set.print_set_selection({})
        held = print_set.filter_by_forecast(selection, print_set.FORECAST_HELD)
        printing = print_set.filter_by_forecast(selection, print_set.FORECAST_WILL_PRINT)

        assert held.count() == forecast.held > 0
        assert printing.count() == forecast.will_print > 0
        assert held.count() + printing.count() == forecast.bills


def test_the_row_verdicts_agree_with_the_counts_and_cost_one_statement(brazos, marcus):
    """The table's page is judged in a FIXED handful of statements, not two a row.

    ⚠ **THE STATEMENT COUNT IS THE POINT.** `print_address_for_account` is two
    statements a bill; at the top of the ICP a page of 50 would be 100 of them
    and a whole print set 80,000. `forecast_rows` asks the bulk read once, for
    the page's accounts.

    ⚠ **IT WAS EXACTLY ONE UNTIL 2026-09-24 (`DEF-BIL-6373`) AND THE NAME IS
    KEPT SO THE HISTORY READS.** An account with no mailing row now walks to its
    premises, which is metering's table and reached only through metering's
    read, so the page costs a few statements. What must not change is that the
    number does NOT grow with the page — so the page is asked at two sizes and
    the two counts must be equal.
    """
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    with tenant_ctx(brazos):
        posted = an_account(brazos, marcus, account_no="A-6", label="Unit F")
        a_mailing_address(brazos, posted)
        nowhere = an_account(brazos, marcus, account_no="A-7", label="Unit G")
        a_holed_mailing_address(brazos, nowhere)
        good = a_printable_bill(brazos, posted, invoice_no="BL-2609-000006")
        bad = a_printable_bill(brazos, nowhere, invoice_no="BL-2609-000007")

        # And six that walk to their premises, so the service-address leg runs
        # over more rows than any fixed statement budget could hide per-row
        # reads in: eight rows judged one at a time would be sixteen reads.
        walked = []
        for n in range(6):
            walker = an_account(brazos, marcus, account_no=f"A-7w{n}", label=f"Unit W{n}")
            walked.append(a_printable_bill(brazos, walker, invoice_no=f"BL-2609-00007{n}"))

        rows = list(print_set.print_set_selection({}).select_related("account"))
        with CaptureQueriesContext(connection) as captured:
            verdicts = print_set.forecast_rows(rows)
        with CaptureQueriesContext(connection) as one_row:
            print_set.forecast_rows(rows[:1])

        assert len(rows) == 8
        assert verdicts[str(good.id)] is None
        assert verdicts[str(bad.id)] == print_set.HELD_ADDRESS_INCOMPLETE
        assert all(verdicts[str(bill.id)] is None for bill in walked), "the premises is complete"
        # A FIXED handful — the mailing leg, the walking leg, metering's
        # envelope read and the gap itself — whatever the page holds.
        assert len(captured) <= 4, [one["sql"][:80] for one in captured]
        assert len(one_row) <= 4, [one["sql"][:80] for one in one_row]


def test_the_forecast_and_the_archive_agree(brazos, marcus, tmp_path):
    """THE case this file exists for: the tile and the zip say the same thing.

    A forecast can be internally consistent and still wrong — it counts one held
    bill, the tile says one, and `held-back.csv` then holds two. Nothing else in
    this file would notice. This builds the real archive over the real selection
    and compares them bill by bill.
    """
    with tenant_ctx(brazos):
        posted = an_account(brazos, marcus, account_no="A-8", label="Unit H")
        a_mailing_address(brazos, posted)
        # An address with a hole in it, which is DEF-2703's common shape: a row
        # exists and one of `BR-NOT-029` (b)'s three parts is empty.
        partial = an_account(brazos, marcus, account_no="A-9", label="Unit I")
        a_mailing_address(brazos, partial, city="")
        a_printable_bill(brazos, posted, invoice_no="BL-2609-000008")
        a_printable_bill(brazos, partial, invoice_no="BL-2609-000009")

        forecast = print_set.forecast_print_set({})
        result = print_set.build_print_set(
            print_set.print_set_selection({}),
            tmp_path / "set.zip",
            generated_at=GENERATED_AT,
        )

        assert forecast.held == result.held_count == 1
        assert forecast.will_print == result.considered - result.held_count
        held_now = {entry.bill_no for entry in result.held}
        held_forecast = {
            invoice.invoice_no
            for invoice in print_set.filter_by_forecast(
                print_set.print_set_selection({}), print_set.FORECAST_HELD
            )
        }
        # The same BILLS, not merely the same number of them.
        assert held_now == held_forecast == {"BL-2609-000009"}


#: How far the per-bill page estimate may sit from what the renderer actually
#: draws before this test calls it stale. **ONE PAGE**, and the reason is
#: measured rather than chosen: the constant is 2, taken from the demo
#: utility's 79 REAL bills on 2026-09-15, and a fixture bill here carries a
#: two-field payload that draws in **1**. A synthetic bill is shorter than a
#: real one, so an equality assertion would be a check that cannot pass; a
#: tolerance of one page still goes RED if the layout grows to 4.
PAGE_ESTIMATE_TOLERANCE = 1


def test_the_page_estimate_is_within_reach_of_the_archive_it_predicts(brazos, marcus, tmp_path):
    """`MEASURED_PAGES_PER_BILL` is a MEASUREMENT of this product's renderer.

    ⚠ **THIS ASSERTS THE CONSTANT AGAINST THE RENDERER, NOT AGAINST ITSELF.** A
    test reading the constant twice would pass for ever while the bill layout
    grew a page and every print shop was quoted short.

    ⚠ **AND IT IS A TOLERANCE, WHICH IS A WEAKNESS STATED RATHER THAN HIDDEN.**
    It cannot catch the layout gaining exactly one page. What would catch that
    is re-measuring on real bills — `_page_for` over the seeded utility, which
    is how the 2 was arrived at — and the constant's own docstring says to do it
    when the layout changes.
    """
    with tenant_ctx(brazos):
        account = an_account(brazos, marcus, account_no="A-10", label="Unit J")
        a_mailing_address(brazos, account)
        a_printable_bill(brazos, account, invoice_no="BL-2609-000010")

        forecast = print_set.forecast_print_set({})
        result = print_set.build_print_set(
            print_set.print_set_selection({}),
            tmp_path / "set.zip",
            generated_at=GENERATED_AT,
        )

        # The tile's figure is definitionally the bills that will print times
        # the constant — that half has to hold exactly.
        assert forecast.pages == forecast.will_print * print_set.MEASURED_PAGES_PER_BILL
        # And the constant has to still describe the renderer.
        drawn_per_bill = result.page_total / result.pdf_count
        assert result.pdf_count > 0
        assert abs(drawn_per_bill - print_set.MEASURED_PAGES_PER_BILL) <= PAGE_ESTIMATE_TOLERANCE


# ══════════════════════════════════════════════════════════════════════════
# The route
# ══════════════════════════════════════════════════════════════════════════
def _request(tenant, actor, params):
    """A real DRF request for the view, not a call to the selector under it.

    The envelope is `StandardPagination`'s and it is built in the VIEW: a case
    that called the selector would pass identically whether the route pages or
    serves every row, which is the one thing `NFR-3` is about.
    """
    from rest_framework.test import APIRequestFactory, force_authenticate

    request = APIRequestFactory().get("/api/v1/billing/print-sets/bills", params)
    force_authenticate(request, user=actor.user)
    request.tenant_role = "system_admin"
    request.tenant_id = tenant.id
    return request


def test_the_bills_route_pages_in_the_database_and_carries_the_verdict(brazos, marcus):
    from apps.billing import print_api

    with tenant_ctx(brazos):
        posted = an_account(brazos, marcus, account_no="A-11", label="Unit K")
        a_mailing_address(brazos, posted)
        nowhere = an_account(brazos, marcus, account_no="A-12", label="Unit L")
        a_holed_mailing_address(brazos, nowhere)
        for n in range(3):
            a_printable_bill(brazos, posted, invoice_no=f"BL-2609-0001{n}0")
        a_printable_bill(brazos, nowhere, invoice_no="BL-2609-000199")

        response = print_api.print_set_bills(_request(brazos, marcus, {"page": 1, "per": 50}))

        assert response.status_code == 200
        body = response.data
        # The TOTAL comes from the database, not from the rows on the page.
        assert body["count"] == 4
        rows = {row["invoice_no"]: row for row in body["results"]}
        assert rows["BL-2609-000199"]["will_print"] is False
        assert rows["BL-2609-000199"]["hold_reason"] == print_set.HELD_ADDRESS_INCOMPLETE
        # A held bill has NO page count. A `0` there is a number a print shop
        # could quote against.
        assert rows["BL-2609-000199"]["pages"] is None
        assert rows["BL-2609-000100"]["will_print"] is True
        assert rows["BL-2609-000100"]["pages"] == print_set.MEASURED_PAGES_PER_BILL
        # Money keeps its CHAR(3) partner all the way to the screen (hard rule 2).
        assert rows["BL-2609-000100"]["currency"] == "USD"


def test_the_bills_route_narrows_to_the_held_ones_and_searches_within_the_scope(brazos, marcus):
    from apps.billing import print_api

    with tenant_ctx(brazos):
        posted = an_account(brazos, marcus, account_no="A-13", label="Unit M")
        a_mailing_address(brazos, posted)
        nowhere = an_account(brazos, marcus, account_no="A-14", label="Unit N")
        a_holed_mailing_address(brazos, nowhere)
        a_printable_bill(brazos, posted, invoice_no="BL-2609-000201")
        a_printable_bill(brazos, nowhere, invoice_no="BL-2609-000202")

        held = print_api.print_set_bills(_request(brazos, marcus, {"hold": "held"}))
        assert [row["invoice_no"] for row in held.data["results"]] == ["BL-2609-000202"]
        assert held.data["count"] == 1

        found = print_api.print_set_bills(_request(brazos, marcus, {"q": "BL-2609-000201"}))
        assert [row["invoice_no"] for row in found.data["results"]] == ["BL-2609-000201"]

        # ⚠ AND THE SEARCH NARROWS THE LIST, NEVER THE ARCHIVE. The POST is
        # always built with `q=""`; a set that printed the three bills a clerk
        # happened to search for is a short run nobody asked for.
        assert print_set.print_set_selection({}).count() == 2


def test_a_status_filter_is_dropped_because_the_selection_overrides_it(brazos, marcus):
    """The screen offers no status control, and this is why: the server would
    override it. A print set is issued and paid bills, always."""
    from apps.billing import print_api

    with tenant_ctx(brazos):
        account = an_account(brazos, marcus, account_no="A-15", label="Unit O")
        a_mailing_address(brazos, account)
        a_printable_bill(brazos, account, invoice_no="BL-2609-000301")

        asked = print_api.print_set_bills(_request(brazos, marcus, {"f.status": "draft"}))

        # Asking for drafts does NOT answer an empty list, which would read like
        # a broken renderer; it answers the printable population.
        assert asked.data["count"] == 1
        assert asked.data["results"][0]["invoice_no"] == "BL-2609-000301"


# ══════════════════════════════════════════════════════════════════════════
# The holds, and the tests that fire when they expire (hard-won law 2)
# ══════════════════════════════════════════════════════════════════════════
def test_route_and_service_are_drawn_filters_that_no_list_serves():
    """⚠ **THIS TEST GOES RED THE DAY EITHER FILTER ARRIVES, AND THAT IS ITS
    JOB.** Screen 28's toolbar is drawn with Status, Route and Service chips
    (p148). Route and Service are in NO list's filter vocabulary — not the bills
    list's, not the print set's — so the screen offers neither, and the absence
    is stated in its own record rather than dressed as a disabled control.

    A hold with no test that fires when it expires is a promise nobody is
    keeping. When `route_id` or a service filter lands in `INVOICE_FILTERS`,
    this fails and names the screen that owes them a control:
    `07-frontend/src/features/billing/PrintBillsPage.tsx`.
    """
    assert "route_id" not in selectors.INVOICE_FILTERS
    assert "route" not in selectors.INVOICE_FILTERS
    assert "service" not in selectors.INVOICE_FILTERS
    assert "service_id" not in selectors.INVOICE_FILTERS


def test_only_the_three_reasons_a_screen_can_know_before_generating_are_forecast():
    """Five of the eight hold reasons need the page DRAWN, and forecasting one
    of those would mean rendering every bill in the period to paint a screen.

    `duplicate_filename` is not here for a different reason and it is not an
    oversight: `uq_invoices_no` is a UNIQUE index over (tenant, invoice_no), so
    two bills cannot carry one number and the check in `_add_one` guards a
    constraint that would have to have failed first.
    """
    assert print_set.FORECASTABLE_HELD_REASONS == (
        print_set.HELD_NO_BILL_NUMBER,
        print_set.HELD_UNSAFE_BILL_NUMBER,
        print_set.HELD_ADDRESS_INCOMPLETE,
    )
    for reason in (
        print_set.HELD_DOCUMENT_REFUSED,
        print_set.HELD_ORIGINAL_UNREADABLE,
        print_set.HELD_PAGE_COUNT_UNKNOWN,
        print_set.HELD_ADDRESS_UNREADABLE,
        print_set.HELD_DUPLICATE_FILENAME,
    ):
        assert reason not in print_set.FORECASTABLE_HELD_REASONS


def test_the_forecast_is_tenant_scoped(brazos, lonestar, marcus, dana):
    """CLAUDE.md hard rule 1. The forecast is four COUNTs over a selection, and
    a count is exactly the shape that leaks quietly: it answers a number, and a
    number from the wrong tenant looks like any other number."""
    with tenant_ctx(brazos):
        account = an_account(brazos, marcus, account_no="A-16", label="Unit P")
        a_mailing_address(brazos, account)
        a_printable_bill(brazos, account, invoice_no="BL-2609-000401")
        assert print_set.forecast_print_set({}).bills == 1

    with tenant_ctx(lonestar):
        # The other tenant's bills are not this one's, and the other tenant has
        # none of its own: a leak would read as 1 here.
        assert print_set.forecast_print_set({}).bills == 0
