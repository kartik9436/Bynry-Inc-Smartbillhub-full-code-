# ── Trace ──────────────────────────────────────────────
# Story:    US-MET-003 (the unit wizard) · S15 (the units list)
# Rules:    BR-MET-119 AS AMENDED 2026-09-25 — a premises DECLARES what is
#           available at the address and a unit INHERITS that list **BY
#           DEFAULT**; a clerk may untick, so a unit's set is *within* the
#           premises' set rather than equal to it. PO, verbatim: *"the
#           premises' list is what a unit takes, the tick-list stays, and a
#           clerk may untick"* ·
#           BR-MET-003 (⊆ the tenant's ENABLED services — the outer bound) ·
#           BR-BIL-300 (service points decide what a bill charges — the reason
#           a shortfall is money rather than tidiness) ·
#           NFR-3 (every list read is paged by the server)
# Defects:  DEF-MET-6796 — `_create_unit_inner` looped `data["services"]` and
#           nothing else, so a unit created with one service ticked, or with
#           the key absent (which is every unit the Add units wizard makes),
#           held fewer service points than its address offers. The only guard
#           in the area, `_refuse_service_not_at_premises`, is a SUPERSET
#           guard and is silent about a subset.
# ───────────────────────────────────────────────────────
"""T3 and T4 — the default, the untick, and the count.

⚠ **THE FALSE PASS EACH TEST IS WRITTEN AGAINST, stated rather than implied
(hard-won law 7 habit 2).**

  * **T3** would pass wrongly on a read that returned *some* services — so it
    asserts the EXACT SET, both ways, on an address offering three of the
    tenant's services. A default of "the first one" and a default of "all of
    them" are indistinguishable on a one-service address, which is why the
    fixture offers three.
  * **T4** would pass wrongly on a query that returns nothing, and "no error"
    would read as success — so every case asserts a KNOWN NON-ZERO count and
    names the units it expects. It would also pass wrongly on a report built by
    grouping the service-point table, which can only see units that HAVE a
    point; `test_t4_a_unit_with_no_points_at_all_is_counted` is that case and it
    is the row such a report loses.
"""

import pytest

from apps.metering import api as metering_api
from apps.metering import models, selectors, services
from core.pagination import ListParams, parse_list_params

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import (
    FakeUser,
    api_call,
    make_premises,
    make_unit,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


def _codes(unit_id) -> list[str]:
    """The service codes a unit actually holds, in the order they were made."""
    return [point["service"] for point in selectors.service_points_for(unit_id)]


def _params(**overrides):
    query = {"per": "50", "page": "1"}
    query.update({k: str(v) for k, v in overrides.items()})
    return parse_list_params(
        query,
        allowed_sorts=tuple(selectors.UNIT_SORTS),
        default_sort=selectors.UNIT_DEFAULT_SORT,
        allowed_filters=tuple(metering_api.UNIT_FILTERS),
    )


def _gap_params(**overrides):
    """The same params with the **Missing services** filter engaged.

    ⚠ **THROUGH `parse_list_params` AND `f.missing_services`, NOT A DICT.** The
    filter reaches the selector as a URL param a clerk's browser sends, so the
    vocabulary (`metering_api.UNIT_FILTERS`) is exercised too — a filter the
    parser drops would leave every case below passing over an UNFILTERED list,
    which is hard-won law 7's *structurally incapable of failing*.
    """
    return _params(**{"f.missing_services": "yes", **overrides})


def _gap_page(**overrides):
    """One page of the units list under the filter: `(rows, total)`.

    This is the shape the SCREEN reads — `GET /units` with the chip on — rather
    than a selector written for a second table. The retired
    `GET /units/service-gaps` is what these cases used to call.
    """
    return selectors.units_page(_gap_params(**overrides))


# ══════════════════════════════════════════════════════════════════════════
# T3 · unticking at creation makes fewer points; the default makes all of them
# ══════════════════════════════════════════════════════════════════════════


@pytest.fixture()
def every_service_address(brazos, dana):
    """An address offering EVERY service this tenant sells — both of them.

    ⚠ **TWO, NOT ONE, AND IT IS THE WHOLE POINT OF THE FIXTURE.** On a
    one-service address *inherit everything* and *inherit the first thing*
    produce the same answer, so a test written on one would pass either way and
    prove nothing about what was built. Two separates them.

    ⚠ **AND IT IS TWO RATHER THAN THREE BECAUSE `brazos` SELLS TWO** — Electric
    and Water (`tests/test_us_met_helpers.py::brazos`). `BR-MET-003` is asked
    first and `_clean_services` refuses `sewer` outright, so an address offering
    a service the utility does not sell cannot be created here at all.
    """
    with tenant_ctx(brazos):
        premises = make_premises(
            dana,
            address_line="14 Sandhill Cross",
            services_available=["electric", "water"],
        )
    return premises


def test_t3_the_default_takes_every_service_the_premises_offers(brazos, dana, every_service_address):
    """No `services` key → the address answers, in full and in its own order."""
    with tenant_ctx(brazos):
        unit = make_unit(dana, every_service_address["id"], label="Unit Default")
        assert _codes(unit["id"]) == ["electric", "water"]


def test_t3_unticking_makes_fewer_points(brazos, dana, every_service_address):
    """A partial list is HONOURED — the ruling's *a clerk may untick*."""
    with tenant_ctx(brazos):
        unit = make_unit(
            dana, every_service_address["id"], label="Unit Partial", services=["water"]
        )
        assert _codes(unit["id"]) == ["water"]


def test_t3_an_empty_list_is_an_answer_and_is_honoured(brazos, dana, every_service_address):
    """`services: []` is a clerk unticking everything, not an absent key.

    ⚠ This is the assertion that separates the ruling from the obvious
    implementation. `data.get("services") or []` — the shape the defect had —
    treats `[]` and a missing key identically, so a default written with `or`
    would pass every other test in this file and silently overrule the clerk
    here.
    """
    with tenant_ctx(brazos):
        unit = make_unit(dana, every_service_address["id"], label="Unit None", services=[])
        assert _codes(unit["id"]) == []


def test_t3_the_default_is_a_subset_of_the_offer_and_never_a_superset(brazos, dana):
    """`_refuse_service_not_at_premises` is untouched, in both directions.

    The address offers water only; the tenant sells electric. The default must
    take water and nothing else, and asking for electric must still be refused
    with the rule's own message.
    """
    from core import errors

    with tenant_ctx(brazos):
        premises = make_premises(
            dana, address_line="9 Heron Walk", services_available=["water"]
        )
        unit = make_unit(dana, premises["id"], label="Unit W")
        assert _codes(unit["id"]) == ["water"]
        with pytest.raises(errors.ValidationError) as caught:
            services.ensure_service_point(unit["id"], "electric")
        assert caught.value.message_key == "metering.service_not_at_premises"


def test_t3_a_never_asked_address_inherits_nothing(brazos, dana):
    """`NULL` is not an empty list (`DEF-756`/`DEF-762`).

    An address nobody has been asked about has provisioned nothing, so the
    default takes nothing — and the create SUCCEEDS rather than dying on a
    service nobody typed.
    """
    with tenant_ctx(brazos):
        premises = make_premises(dana, address_line="3 Never Asked Ln")
        models.Premises.objects.filter(pk=premises["id"]).update(services_available=None)
        unit = make_unit(dana, premises["id"], label="Unit Unknown")
        assert _codes(unit["id"]) == []


def test_t3_the_default_reaches_the_premises_create_s_inline_unit(brazos, dana):
    """The default lives in the SERVICE layer, so every door has it.

    `POST /premises` with `auto_create_unit` never sends a `services` key and
    never could — there is no tick-list on that step. It inherits anyway.
    """
    with tenant_ctx(brazos):
        created = services.create_premises(
            dana,
            {
                "address_line": "88 Willow Bend",
                "city": "Katy",
                "state": "TX",
                "postal_code": "77494",
                "premises_type": "single_family",
                "services_available": ["electric", "water"],
                "owner_manager": "Whitfield Rentals LLC",
                "owner_id": __import__(
                    "tests.test_us_met_helpers", fromlist=["owner_for"]
                ).owner_for(dana, "Whitfield Rentals LLC"),
                "auto_create_unit": True,
                "unit": {"label": "Unit 1", "unit_type": "residential"},
            },
        )
        assert _codes(created["units"][0]["id"]) == ["electric", "water"]


# ══════════════════════════════════════════════════════════════════════════
# T4 · the gap report counts correctly
# ══════════════════════════════════════════════════════════════════════════


def test_t4_the_report_counts_a_partly_ticked_unit_and_names_what_is_missing(
    brazos, dana, every_service_address
):
    with tenant_ctx(brazos):
        short = make_unit(
            dana, every_service_address["id"], label="Unit Short", services=["water"]
        )
        make_unit(dana, every_service_address["id"], label="Unit Full")
        rows, total = _gap_page()
        assert total == 1
        assert [row["id"] for row in rows] == [str(short["id"])]
        # The row is an ordinary S15 row now, so the three facts are the units
        # list's own keys: what the ADDRESS offers, what this unit HOLDS, and
        # the difference derived once in `unit_list_dict`.
        assert rows[0]["services"] == ["electric", "water"]
        assert rows[0]["metered_services"] == ["water"]
        assert rows[0]["missing_services"] == ["electric"]
        # And the count the toolbar draws is the same number as the list's.
        assert selectors.units_gap_count(_params()) == 1


def test_t4_a_unit_with_no_points_at_all_is_counted(brazos, dana, every_service_address):
    """**THE ROW THE OBVIOUS IMPLEMENTATION LOSES.**

    A report built by counting the service-point table and grouping by unit can
    only see units that HAVE a point, so a unit with none — the worst case, and
    every unit the Add units wizard has ever made — is absent from it and the
    total reads low and plausible.
    """
    with tenant_ctx(brazos):
        empty = make_unit(dana, every_service_address["id"], label="Unit Empty", services=[])
        assert selectors.service_points_for(empty["id"]) == []
        rows, total = _gap_page()
        assert total == 1
        assert rows[0]["id"] == str(empty["id"])
        assert rows[0]["metered_services"] == []
        assert rows[0]["missing_services"] == ["electric", "water"]


def test_t4_a_unit_that_holds_everything_is_not_counted(brazos, dana, every_service_address):
    """The default path leaves nothing behind — the report is empty, and it is
    empty because every unit is whole rather than because the query is wrong.

    Asserted beside a POSITIVE case in the same fixture, because a zero on its
    own cannot tell the two apart.
    """
    with tenant_ctx(brazos):
        make_unit(dana, every_service_address["id"], label="Unit A")
        make_unit(dana, every_service_address["id"], label="Unit B")
        _rows, total = _gap_page()
        assert total == 0
        assert selectors.units_gap_count(_params()) == 0
        short = make_unit(
            dana, every_service_address["id"], label="Unit C", services=["water"]
        )
        _rows2, total2 = _gap_page()
        assert total2 == 1
        assert _rows2[0]["id"] == str(short["id"])
        assert selectors.units_gap_count(_params()) == 1


def test_t4_an_address_that_offers_nothing_leaves_nobody_short(brazos, dana):
    """`[]` and `NULL` are different answers and NEITHER can make a unit short.

    An address that offers nothing has nothing to be short of, and an address
    nobody has been asked about has provisioned nothing (`BR-MET-119`). A
    report that treated either as a gap would report every legacy address in
    the utility as a shortfall on the day it shipped.
    """
    with tenant_ctx(brazos):
        answered_none = make_premises(
            dana, address_line="1 Nothing Here", services_available=[]
        )
        never_asked = make_premises(dana, address_line="2 Never Asked")
        models.Premises.objects.filter(pk=never_asked["id"]).update(services_available=None)
        make_unit(dana, answered_none["id"], label="Unit N")
        make_unit(dana, never_asked["id"], label="Unit U")
        _rows, total = _gap_page()
        assert total == 0


def test_t4_the_report_pages_in_sql_and_the_total_is_the_whole_set(
    brazos, dana, every_service_address
):
    """`NFR-3`: `total` is the shortfall, not the page (`NFR-5`: no cap).

    Five short units, a page of two — the page carries two and the total says
    five. A report whose count came from the page would say two, which is the
    exact shape `DEF-PAY-4221` records on four other reads.
    """
    with tenant_ctx(brazos):
        for n in range(5):
            make_unit(
                dana, every_service_address["id"], label=f"Unit S{n}", services=["water"]
            )
        rows, total = _gap_page()
        assert total == 5
        assert len(rows) == 5
        # ⚠ **`ListParams` DIRECTLY, AND NOT THROUGH `parse_list_params`.**
        # `per` CLAMPS to the `IS-2` vocabulary, whose smallest value is 50
        # (`core.pagination.PAGE_SIZES`), so `?per=2` legitimately comes back as
        # 50 and a page of two cannot be asked for through a URL. That clamp is
        # `BR-SHL-011`'s and is tested where it lives; what this case is about
        # is whether the SELECTOR cuts a page and counts the whole set, so it is
        # handed the two numbers straight. Seeding 51 units to page through a
        # URL would test the clamp a second time and this not at all.
        page_one, total_one = selectors.units_page(
            ListParams(
                q="", sort=None, dir="asc", page=1, per=2,
                filters={"missing_services": "yes"},
            )
        )
        page_two, total_two = selectors.units_page(
            ListParams(
                q="", sort=None, dir="asc", page=2, per=2,
                filters={"missing_services": "yes"},
            )
        )
        assert (total_one, total_two) == (5, 5)
        assert len(page_one) == 2 and len(page_two) == 2
        assert {row["id"] for row in page_one}.isdisjoint({row["id"] for row in page_two})


def test_t4_a_deleted_unit_is_not_a_shortfall(brazos, dana, every_service_address):
    """A unit taken out of service is not a service the utility fails to bill.

    Asserted against a live short unit in the same tenant, so the zero is a
    narrowing and not an empty query.
    """
    with tenant_ctx(brazos):
        gone = make_unit(dana, every_service_address["id"], label="Unit Gone", services=[])
        live = make_unit(dana, every_service_address["id"], label="Unit Live", services=[])
        _rows, before = _gap_page()
        assert before == 2
        services.delete_unit(dana, gone["id"])
        rows, after = _gap_page()
        assert after == 1
        assert rows[0]["id"] == str(live["id"])


def test_t4_the_report_is_tenant_scoped(brazos, lonestar, dana, every_service_address):
    """CLAUDE.md hard rule 1 — another tenant's shortfall is not this one's."""
    from tests.test_us_met_helpers import owner_for, staff_actor

    with tenant_ctx(lonestar):
        erin = staff_actor(lonestar, "system_admin", "admin@lonestarridge.test")
        foreign = make_premises(
            erin,
            address_line="9 Ridge Rd",
            services_available=["water"],
            owner_manager="Ridge Property LLC",
            owner_id=owner_for(erin, "Ridge Property LLC"),
        )
        make_unit(erin, foreign["id"], label="Unit Foreign", services=[])
        _rows, lonestar_total = _gap_page()
        assert lonestar_total == 1
    with tenant_ctx(brazos):
        make_unit(dana, every_service_address["id"], label="Unit Home", services=[])
        rows, brazos_total = _gap_page()
        assert brazos_total == 1
        assert rows[0]["label"] == "Unit Home"


# ══════════════════════════════════════════════════════════════════════════
# A3 · THE FILTER IS WIRED, AND THE RETIRED ENDPOINT IS GONE
# ══════════════════════════════════════════════════════════════════════════
#
# PO ruling 2026-09-28, verbatim: *"the Units "Missing services" block — filter
# or leave it. - filter"*. These cases replace the ones that went through
# `GET /units/service-gaps`, and they assert the two halves that can each be
# wrong on their own: the units list HONOURS the filter, and the address the
# retired client called is no longer answered.


def test_a3_the_units_list_honours_the_filter_at_its_own_address(
    brazos, dana, every_service_address
):
    """**A selector nothing routes to is not a filter.**

    Every case above would pass over a view that dropped `f.missing_services`
    before it reached the selector — the list would simply return everything
    and each assertion about a SELECTOR would still hold. So this one goes
    through the view, with the param spelled the way the client spells it.
    """
    with tenant_ctx(brazos):
        short = make_unit(dana, every_service_address["id"], label="Unit API", services=["water"])
        make_unit(dana, every_service_address["id"], label="Unit Whole")
    response = api_call(
        metering_api.units,
        "get",
        user=FakeUser(),
        role="system_admin",
        tenant=brazos,
        query={"f.missing_services": "yes", "per": "50", "page": "1"},
    )
    assert response.status_code == 200
    assert response.data["count"] == 1
    row = response.data["results"][0]
    assert row["id"] == str(short["id"])
    assert row["missing_services"] == ["electric"]


def test_a3_the_count_is_served_whether_or_not_the_filter_is_on(
    brazos, dana, every_service_address
):
    """⚠ **THE COUNT IS THE DELIVERABLE, NOT THE FILTER CONTROL.**

    `DEF-MET-6796` exists because the shortfall was INVISIBLE, and a filter
    nobody switches on is invisible in exactly the same way. So the units list
    serves `service_gap_count` on EVERY read.

    **The false pass this is written against:** a count computed FROM the
    result set would be right when the filter is on and would read `0` — or
    the whole list — when it is off, and the case would pass if it only ever
    asked one way. So it asks BOTH ways and demands the SAME number, over a
    list whose own `count` differs between them.
    """
    with tenant_ctx(brazos):
        make_unit(dana, every_service_address["id"], label="Unit Short", services=["water"])
        make_unit(dana, every_service_address["id"], label="Unit Whole")
    off = api_call(
        metering_api.units, "get", user=FakeUser(), role="system_admin", tenant=brazos,
        query={"per": "50", "page": "1"},
    )
    on = api_call(
        metering_api.units, "get", user=FakeUser(), role="system_admin", tenant=brazos,
        query={"f.missing_services": "yes", "per": "50", "page": "1"},
    )
    assert off.data["count"] == 2 and on.data["count"] == 1
    assert off.data["service_gap_count"] == 1
    assert on.data["service_gap_count"] == 1


def test_a3_the_filter_composes_with_the_search(brazos, dana):
    """**WHY THE PO ASKED FOR A FILTER RATHER THAN A BLOCK.**

    The block could be combined with nothing. Searching *Willow Bend* with the
    filter on must return the short units AT THAT ADDRESS and no other — and
    the count beside the control must narrow with it, because the question a
    clerk can act on is *how many of what I am looking at are short*.
    """
    from tests.test_us_met_helpers import owner_for

    with tenant_ctx(brazos):
        willow = make_premises(
            dana,
            address_line="88 Willow Bend",
            services_available=["electric", "water"],
            owner_manager="Whitfield Rentals LLC",
            owner_id=owner_for(dana, "Whitfield Rentals LLC"),
        )
        elsewhere = make_premises(
            dana,
            address_line="12 Cypress Row",
            services_available=["electric", "water"],
            owner_manager="Whitfield Rentals LLC",
            owner_id=owner_for(dana, "Whitfield Rentals LLC"),
        )
        here = make_unit(dana, willow["id"], label="Willow Short", services=["water"])
        make_unit(dana, elsewhere["id"], label="Cypress Short", services=["water"])
        # Both are short; only one is on Willow Bend.
        assert _gap_page()[1] == 2
        rows, total = _gap_page(q="Willow Bend")
        assert total == 1
        assert rows[0]["id"] == str(here["id"])
        assert selectors.units_gap_count(_params(q="Willow Bend")) == 1


def test_a3_the_route_is_no_longer_registered(brazos):
    """**THE RETIRED ADDRESS, ASSERTED ABSENT (hard rule 8's lesson).**

    `GET /units/service-gaps` is deleted. An absence is invisible to every
    other check this repo has — retiring an address kind once broke an account
    header line that would have returned null forever with `tsc` and every test
    green — so the absence is asserted by name here, and a client left calling
    it cannot be answered by a silent 404 with the suite still green.
    """
    patterns = {str(route.pattern) for route in metering_api.urlpatterns}
    assert "units/service-gaps" not in patterns
    assert not hasattr(metering_api, "units_service_gaps")
    # And the address that REPLACED it is registered, so this case cannot pass
    # by the whole module having failed to import its routes.
    assert "units" in patterns
