# ── Trace ──────────────────────────────────────────────
# Change:   CR-006 (PO ruling 2026-08-17) — *"when we add premises you should
#           allow to select areas and sub areas on premises"*
#           Screens: S16 (add premises) · S14 (edit premises) · S8 (Areas &
#           sub-areas) · r10 SET-06.2 (the picker whose filter this feeds)
# Defects:  DEF-220 (nothing could tag a premises, so the area filter could only
#           ever return zero rows) · DEF-221 (no screen could create a
#           sub-area) · DEF-225 (a unit added to a routed premises never joined
#           it, so it was never read and never billed) · DEF-227 (a service
#           point inherited ANY of the unit's routes, not its own service's)
# Rules:    BR-MET-071 (premises carry an area) · BR-MET-072 (the filter is
#           multi-select and a parent matches its sub-areas) · BR-MET-066b (two
#           levels, exactly) · BR-MET-074 (membership is per SERVICE; a move is
#           confirmed on screen) · BR-MET-082 + Amendment 1 (a route is a
#           cascade, not a list) · BR-MET-083 (this change) · CLAUDE.md rules 1, 7
# ───────────────────────────────────────────────────────
"""BR-MET-083 — the tagging cascade, asserted against the sentences it comes from.

**The acceptance test for the whole piece is `test_the_area_filter_now_returns
_more_than_zero_rows`.** Before this change the SET-06 route picker's area chips
took it from *"9 premises match"* to *"0 premises match"* every time, because
`premises.area_id` had never held a value on any tenant: the column shipped, the
filter shipped, and the write path did not exist. Both halves were built and
neither could reach the other.

The rest of the file defends BR-MET-083's four BOUNDARIES, and those are the
cases worth having: the cascade is easy to build so that it also does three
things nobody asked for — moving units off live routes, growing draft routes, and
un-routing a premises when its tag changes. Each of those has a test here saying
it must not happen.
"""

import pytest

from apps.metering import models, selectors, services
from apps.tenancy import models as tenancy_models
from apps.tenancy import selectors as tenancy_selectors
from apps.tenancy import services as tenancy_services
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import (
    make_premises,
    make_unit,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


def make_area(tenant, code, name, parent=None):
    return tenancy_models.Area.objects.create(
        tenant_id=tenant.id, code=code, name=name, parent=parent
    )


# ═══════════════════════════════════════════════════════════════════════════
# DEF-220 · THE WRITE PATH — *"when we add premises you should allow to select
# areas and sub areas on premises"*
# ═══════════════════════════════════════════════════════════════════════════


def test_a_premises_can_be_created_with_an_area(brazos, dana):
    """The PO's sentence, at its most literal: adding a premises tags it.

    This is the half that did not exist. `_validate_premises` refused every
    field it did not know and `area_code` was not in the known set, so the API
    answered VAL-FORMAT `metering.unknown_field` and the column stayed NULL on
    every tenant that has ever run this product.
    """
    with tenant_ctx(brazos):
        make_area(brazos, "NORTH-D", "North district")
        row = make_premises(dana, address_line="7 Tagged Way", area_code="NORTH-D")
    assert row["area_code"] == "NORTH-D"
    assert row["area_name"] == "North district"


def test_the_tag_survives_a_reload(brazos, dana):
    """A form field that writes and does not read back is a field that looks
    saved and is not. The tag is asserted from a FRESH read, not from the
    create response, because those are two different code paths and only the
    second is what a user sees after a refresh."""
    with tenant_ctx(brazos):
        make_area(brazos, "EAST-D", "East district")
        created = make_premises(dana, address_line="9 Reload Rd", area_code="EAST-D")
        reread = selectors.premises_detail(created["id"])
    assert reread["area_code"] == "EAST-D"
    assert reread["area_path"] == "East district"


def test_a_premises_can_be_tagged_to_a_SUB_area_and_reads_back_as_parent_child(brazos, dana):
    """*"areas and sub areas"* — BOTH levels, and the second is the one r10's
    card is half-named after. `area_path` is the "South · SE" string the
    picker already renders for its own rows, so the two never diverge, and
    `area_parent_code` is what lets an edit form re-open on the right LEVEL
    without a second request."""
    with tenant_ctx(brazos):
        south = make_area(brazos, "SOUTH-D", "South")
        make_area(brazos, "SOUTH-SE", "SE", parent=south)
        row = make_premises(dana, address_line="11 Sub Way", area_code="SOUTH-SE")
    assert row["area_code"] == "SOUTH-SE"
    assert row["area_parent_code"] == "SOUTH-D"
    assert row["area_path"] == "South · SE"


def test_an_edit_can_tag_an_untagged_premises_and_can_clear_it(brazos, dana):
    """Two directions, and the third case is the one that bites: a PATCH that
    does NOT mention the area must leave it alone, or renaming a premises
    would silently untag it."""
    with tenant_ctx(brazos):
        make_area(brazos, "WEST-D", "West district")
        row = make_premises(dana, address_line="13 Edit Ct")
        assert row["area_code"] is None

        tagged = services.update_premises(dana, row["id"], {"area_code": "WEST-D"})
        assert tagged["area_code"] == "WEST-D"

        renamed = services.update_premises(dana, row["id"], {"city": "Fulshear"})
        assert renamed["area_code"] == "WEST-D", "a PATCH that omits the area must not untag"

        cleared = services.update_premises(dana, row["id"], {"area_code": ""})
    assert cleared["area_code"] is None


def test_an_unknown_area_is_refused_by_name_on_the_premises_field(brazos, dana):
    """The refusal a user can act on. `metering.premises.area_unknown`, not the
    route's message key — the two are read on different screens."""
    with tenant_ctx(brazos):
        with pytest.raises(errors.ValidationError) as caught:
            make_premises(dana, address_line="15 Bad Ln", area_code="NOT-A-REAL-AREA")
    assert caught.value.field_errors[0]["message_key"] == "metering.premises.area_unknown"


def test_an_area_from_another_tenant_is_unknown_here(brazos, lonestar, dana):
    """CLAUDE.md rule 1. `areas` is per-tenant, so another tenant's code must
    resolve to nothing rather than to their row."""
    with tenant_ctx(lonestar):
        make_area(lonestar, "THEIRS", "Their district")
    with tenant_ctx(brazos):
        with pytest.raises(errors.ValidationError) as caught:
            make_premises(dana, address_line="17 Leak Ave", area_code="THEIRS")
    assert caught.value.field_errors[0]["message_key"] == "metering.premises.area_unknown"


# ═══════════════════════════════════════════════════════════════════════════
# THE ACCEPTANCE TEST FOR THE WHOLE PIECE
# ═══════════════════════════════════════════════════════════════════════════


def test_the_area_filter_now_returns_more_than_zero_rows(brazos, dana):
    """DEF-220, stated as the number the PO would see.

    *"ticking any chip took the picker from "9 premises match" to "0 premises
    match""*. The filter was correct; it had no data. Three premises, two
    tagged NORTH-F, and the chip must return exactly those two — not zero, and
    not all three.
    """
    with tenant_ctx(brazos):
        make_area(brazos, "NORTH-F", "North")
        make_premises(dana, address_line="1 Filter St", area_code="NORTH-F")
        make_premises(dana, address_line="2 Filter St", area_code="NORTH-F")
        make_premises(dana, address_line="3 Elsewhere St")

        all_rows = selectors.route_premises_picker(areas=[])
        filtered = selectors.route_premises_picker(areas=["NORTH-F"])
    assert len(all_rows) == 3
    assert len(filtered) == 2, "the whole point of the change: not zero"
    assert {row["address_line"] for row in filtered} == {"1 Filter St", "2 Filter St"}
    assert {row["area_path"] for row in filtered} == {"North"}


# ═══════════════════════════════════════════════════════════════════════════
# DEF-221 · SUB-AREA CREATION — the card is called "Areas & sub-areas"
# ═══════════════════════════════════════════════════════════════════════════


def test_a_sub_area_created_through_the_lookup_api_reads_back_with_its_parent(brazos, dana):
    """The DEAD BRANCH, alive. `RoutesCyclesWizards.tsx` renders
    `parent_name ? "${parent_name} · ${name}" : name` in TWO dropdowns, and
    nothing in the product could ever produce a `parent_name` — the editor only
    sent code, name and detail. The backend validation was already there."""
    with tenant_ctx(brazos):
        tenancy_services.create_lookup_entry(dana, "areas", {"code": "MID-D", "name": "Midtown"})
        child = tenancy_services.create_lookup_entry(
            dana, "areas", {"code": "MID-N", "name": "Midtown North", "parent_code": "MID-D"}
        )
        listed = tenancy_selectors.lookup_page("areas", None)
    assert child["parent_code"] == "MID-D"
    assert child["parent_name"] == "Midtown"
    assert child["is_sub_area"] is True
    by_code = {row["code"]: row for row in listed}
    assert (
        by_code["MID-D"]["is_sub_area"] is False
    ), "a top-level row must stay pickable as a parent"
    assert by_code["MID-N"]["parent_name"] == "Midtown", (
        "the LIST must carry parent_name too — the picker's dropdown reads the list, "
        "not the create response"
    )


# ═══════════════════════════════════════════════════════════════════════════
# BR-MET-083(a) · TAGGING JOINS THE AREA'S ROUTES
# BR-MET-082: *"any change any movement make the changes to downstream"*
# ═══════════════════════════════════════════════════════════════════════════


def _active_route(actor, tenant, *, code, area, service_code="electric"):
    route = services.create_route(
        actor,
        {
            "code": code,
            "name": f"{code} walk",
            "route_type": "walk",
            "service_code": service_code,
            "area_code": area.code,
        },
    )
    models.Route.objects.filter(pk=route["id"]).update(status="active")
    return models.Route.objects.get(pk=route["id"])


def test_tagging_a_premises_into_an_area_puts_it_on_that_areas_route(brazos, dana):
    """The purpose, not the letter. A route drawn for NORTH and a premises
    tagged NORTH were two facts that never met — `routes.area_id` has existed
    since CR-006 and never paid out once. Nobody re-opens the route wizard."""
    with tenant_ctx(brazos):
        north = make_area(brazos, "N-CASC", "North")
        route = _active_route(dana, brazos, code="RT-CASC-1", area=north)
        premises = make_premises(dana, address_line="21 Cascade Way")
        unit = make_unit(dana, premises["id"], label="Unit A")

        assert selectors.route_members(route.id) == [], "no membership before the tag"

        result = services.update_premises(dana, premises["id"], {"area_code": "N-CASC"})
        members = selectors.route_members(route.id)
    assert [m["unit_id"] for m in members] == [unit["id"]]
    assert result["routes_joined"] == [
        {"route_id": str(route.id), "route_code": "RT-CASC-1", "units": 1}
    ]


def test_a_premises_created_straight_into_an_area_joins_with_its_first_unit(brazos, dana):
    """S16's guided add creates the premises AND its first unit in ONE
    transaction, so the cascade has to run after the units — a cascade that ran
    first would find no units and silently do nothing, which is the failure
    mode hardest to notice."""
    with tenant_ctx(brazos):
        north = make_area(brazos, "N-CASC2", "North")
        route = _active_route(dana, brazos, code="RT-CASC-2", area=north)
        created = make_premises(
            dana,
            address_line="23 Guided Way",
            area_code="N-CASC2",
            auto_create_unit=True,
            unit={"label": "Unit A", "unit_type": "residential"},
        )
        members = selectors.route_members(route.id)
    # The unit joins through clause (b) — `_create_unit_inner` reads its
    # premises' AREA routes, which is exactly why (b) is not sibling-only. By
    # the time the premises-level cascade runs the unit is already there, so IT
    # reports nothing: the two paths must not double-count.
    assert created["units"][0]["routes_joined"] == [
        {"route_id": str(route.id), "route_code": "RT-CASC-2", "units": 1}
    ]
    assert created["routes_joined"] == [], "the premises cascade must not re-add what (b) added"
    assert len(members) == 1


def test_a_sub_area_premises_joins_the_PARENTS_route(brazos, dana):
    """BR-MET-083 boundary 3, and it is the same direction the FILTER already
    reads: a parent matches its sub-areas. A utility that draws one route for
    South and then splits South into SE and SW has not un-routed half the
    district."""
    with tenant_ctx(brazos):
        south = make_area(brazos, "S-CASC", "South")
        south_east = make_area(brazos, "S-CASC-E", "South East", parent=south)
        route = _active_route(dana, brazos, code="RT-CASC-3", area=south)
        premises = make_premises(dana, address_line="25 Sub Way")
        make_unit(dana, premises["id"], label="Unit A")

        services.update_premises(dana, premises["id"], {"area_code": south_east.code})
        members = selectors.route_members(route.id)
    assert len(members) == 1, "a premises in South · SE belongs to South's route"


def test_the_cascade_reaches_billings_scope_seam(brazos, dana):
    """BR-MET-082 Amendment 1 named the blast radius: `units_in_cycle` is
    BILLING's scope seam (`apps/billing/runs.py` asks it which units a run
    covers) and it filters `service_points.cycle_id`. Membership that does not
    reach that stamp is membership a bill run cannot see, so the assertion is
    made THERE and not on the membership table."""
    with tenant_ctx(brazos):
        north = make_area(brazos, "N-BILL", "North")
        cycle = services.create_cycle(
            dana, {"code": "CY-BILL", "name": "Monthly", "frequency": "monthly"}
        )
        models.Cycle.objects.filter(pk=cycle["id"]).update(status="active")
        route = _active_route(dana, brazos, code="RT-BILL", area=north)
        models.Route.objects.filter(pk=route.id).update(cycle_id=cycle["id"])

        premises = make_premises(dana, address_line="27 Billed Way")
        unit = make_unit(dana, premises["id"], label="Unit A")
        services.ensure_service_point(unit["id"], "electric")

        assert selectors.units_in_cycle(cycle["id"]) == [], "not in the run before the tag"
        services.update_premises(dana, premises["id"], {"area_code": "N-BILL"})
        scoped = selectors.units_in_cycle(cycle["id"])
    assert scoped == [unit["id"]], "tagged into the area = in the next bill run"


def test_the_cascade_is_audited_on_the_route_that_changed(brazos, dana, audit_rows):
    """CR-006: *"All CRUD audit-logged (who, when, before/after member
    counts)"*. A utility asking "why did RT-AUD grow by one unit" must find the
    answer on the ROUTE, not buried in a premises row on another screen."""
    with tenant_ctx(brazos):
        north = make_area(brazos, "N-AUD", "North")
        route = _active_route(dana, brazos, code="RT-AUD", area=north)
        premises = make_premises(dana, address_line="29 Audited Way")
        make_unit(dana, premises["id"], label="Unit A")
        services.update_premises(dana, premises["id"], {"area_code": "N-AUD"})
    cascades = [row for row in audit_rows if row["action"] == "route.members_cascaded"]
    assert len(cascades) == 1
    assert cascades[0]["entity_type"] == "route"
    assert str(cascades[0]["entity_id"]) == str(route.id)
    assert cascades[0]["after"]["reason"] == "premises_area_tagged"
    assert cascades[0]["before"]["members"] == 0
    assert cascades[0]["after"]["members"] == 1


# ── The three things the cascade must NOT do ───────────────────────────────


def test_a_cascade_never_takes_a_unit_off_another_route(brazos, dana):
    """BR-MET-083 boundary 2. Moving a unit between routes is BR-MET-074's
    MOVE, and the CR requires it be confirmed on screen — *"selecting moves
    them, with confirm"*. A move triggered by a dropdown on the premises form
    is a move nobody agreed to, so a cascade only ever fills a gap."""
    with tenant_ctx(brazos):
        north = make_area(brazos, "N-KEEP", "North")
        held = _active_route(dana, brazos, code="RT-HELD", area=None or north)
        models.Route.objects.filter(pk=held.id).update(area=None)  # not an area route
        area_route = _active_route(dana, brazos, code="RT-AREA", area=north)

        premises = make_premises(dana, address_line="31 Held Way")
        unit = make_unit(dana, premises["id"], label="Unit A")
        services.update_route(dana, held.id, {"unit_ids": [unit["id"]]})
        assert len(selectors.route_members(held.id)) == 1

        result = services.update_premises(dana, premises["id"], {"area_code": "N-KEEP"})
        still_held = selectors.route_members(held.id)
        area_members = selectors.route_members(area_route.id)
    assert len(still_held) == 1, "the unit must stay on the route a human put it on"
    assert area_members == [], "and must NOT be added to the area route"
    assert result["routes_joined"] == []


def test_a_DRAFT_route_gains_nothing_from_a_tag(brazos, dana):
    """BR-MET-083 boundary 1, which is DEF-219's ruling one level over: *"a
    draft is a thing that has not happened yet and must not have consequences a
    person can see"*. SET-05's Members column counts memberships, so a draft
    that grew from the premises form would be visible on the one screen
    everybody looks at."""
    with tenant_ctx(brazos):
        make_area(brazos, "N-DRAFT", "North")
        draft = services.create_route(
            dana,
            {
                "code": "RT-DRAFT",
                "name": "Draft walk",
                "route_type": "walk",
                "service_code": "electric",
                "area_code": "N-DRAFT",
                "status": "draft",
            },
        )
        assert draft["status"] == "draft"
        premises = make_premises(dana, address_line="33 Draft Way")
        make_unit(dana, premises["id"], label="Unit A")
        result = services.update_premises(dana, premises["id"], {"area_code": "N-DRAFT"})
        members = selectors.route_members(draft["id"])
    assert members == []
    assert result["routes_joined"] == []


def test_changing_a_tag_never_takes_a_premises_OFF_a_route(brazos, dana):
    """BR-MET-083 boundary 4. DEF-219 was a draft emptying a LIVE route from a
    screen nobody expected to do it; a tag change that un-routed a premises
    would be the same defect with a different trigger. Removing a premises from
    a route is the wizard's job, where it is confirmed and audited.

    ⚠ **AMENDED BY CR-029 D4 (PO 2026-08-23, *"yes member resolve at run
    time"*), AND THE BOUNDARY ITSELF IS UNCHANGED.** This is B17 §5's first
    audit row — *"a premises moved between areas (keeps old routes)"* — which
    D4 rules must re-scope at the next use. So the two halves separate:

    * **the STORED row survives**, exactly as this boundary says. Nothing
      deleted it, and the wizard is still the only thing that removes a
      premises from a route; and
    * **the DERIVED answer follows the tag**, because *"who is on this route
      right now"* is asked of the current area tag rather than read back from
      the row (`selectors.route_members` → `apps.metering.derivation`).

    The assertion below therefore moved from `route_members` to
    `stored_route_members`, which is the reader this boundary was always about.
    """
    with tenant_ctx(brazos):
        north = make_area(brazos, "N-MOVE", "North")
        make_area(brazos, "E-MOVE", "East")
        route = _active_route(dana, brazos, code="RT-MOVE", area=north)
        premises = make_premises(dana, address_line="35 Moved Way", area_code="N-MOVE")
        make_unit(dana, premises["id"], label="Unit A")
        services.update_premises(dana, premises["id"], {"area_code": "N-MOVE"})
        assert len(selectors.route_members(route.id)) == 1

        services.update_premises(dana, premises["id"], {"area_code": "E-MOVE"})
        stored = selectors.stored_route_members(route.id)
        derived = selectors.route_members(route.id)
    assert len(stored) == 1, "re-tagging is not a removal — the wizard owns removal"
    assert derived == [], (
        "…and the East premises is no longer read by the North route (CR-029 D4). "
        "Its own area's route reads it — B17 §5 row 1, and "
        "tests/test_cr029_rcw4_derivation.py asserts the arrival half."
    )


# ═══════════════════════════════════════════════════════════════════════════
# BR-MET-083(b) · DEF-225 — a unit added to a routed premises joins it
# ═══════════════════════════════════════════════════════════════════════════


def test_a_unit_added_to_a_premises_already_on_a_route_joins_it(brazos, dana):
    """DEF-225's exact shape, and it is the shape no existing fixture had:
    **create the route FIRST, then add the unit.** Every route fixture in this
    repo creates the route and asserts in the same breath, so none of them
    could express the passage of time — which is why a unit that was never read
    and never billed passed every test in the suite."""
    with tenant_ctx(brazos):
        north = make_area(brazos, "N-LATER", "North")
        route = _active_route(dana, brazos, code="RT-LATER", area=north)
        premises = make_premises(dana, address_line="37 Later Way", area_code="N-LATER")
        first = make_unit(dana, premises["id"], label="Unit A")
        services.update_premises(dana, premises["id"], {"area_code": "N-LATER"})
        assert [m["unit_id"] for m in selectors.route_members(route.id)] == [first["id"]]

        # …and now, later, a second unit in the same building.
        second = make_unit(dana, premises["id"], label="Unit B")
        members = {m["unit_id"] for m in selectors.route_members(route.id)}
    assert second["routes_joined"] == [
        {"route_id": str(route.id), "route_code": "RT-LATER", "units": 1}
    ]
    assert members == {first["id"], second["id"]}


def test_the_late_unit_reaches_the_bill_run(brazos, dana):
    """DEF-225's consequence, asserted where it hurts. *"A utility adds Unit B
    to a serviced building; nobody is warned; Unit B is never read and never
    invoiced until somebody notices the money is missing."*"""
    with tenant_ctx(brazos):
        north = make_area(brazos, "N-LATE2", "North")
        cycle = services.create_cycle(
            dana, {"code": "CY-LATE", "name": "Monthly", "frequency": "monthly"}
        )
        models.Cycle.objects.filter(pk=cycle["id"]).update(status="active")
        route = _active_route(dana, brazos, code="RT-LATE2", area=north)
        models.Route.objects.filter(pk=route.id).update(cycle_id=cycle["id"])

        premises = make_premises(dana, address_line="39 Late Way", area_code="N-LATE2")
        make_unit(dana, premises["id"], label="Unit A")
        services.update_premises(dana, premises["id"], {"area_code": "N-LATE2"})

        late = make_unit(dana, premises["id"], label="Unit B")
        services.ensure_service_point(late["id"], "electric")
        scoped = selectors.units_in_cycle(cycle["id"])
    assert late["id"] in scoped, "the unit added later must be in the next bill run"


def test_a_unit_added_to_an_UNROUTED_premises_joins_nothing(brazos, dana):
    """The cascade must be a no-op when there is nothing to cascade — a
    cascade that invented a route for an untagged building would be worse than
    the bug it replaces."""
    with tenant_ctx(brazos):
        premises = make_premises(dana, address_line="41 Nowhere Way")
        make_unit(dana, premises["id"], label="Unit A")
        second = make_unit(dana, premises["id"], label="Unit B")
    assert second["routes_joined"] == []


# ═══════════════════════════════════════════════════════════════════════════
# DEF-227 · a service point inherits ITS OWN service's route
# ═══════════════════════════════════════════════════════════════════════════


def test_service_point_inherits_its_own_services_route(brazos, dana):
    """DEF-227. BR-MET-074 made a unit able to hold one membership PER SERVICE
    and `ensure_service_point` still asked for `.first()` — correct while a
    unit had at most one, a coin-flip the day it could have two. Every fixture
    in the repo gives a unit exactly one membership, so `.first()` and "the
    right one" were the same row and no test could tell them apart."""
    with tenant_ctx(brazos):
        north = make_area(brazos, "N-SVC", "North")
        water = _active_route(dana, brazos, code="RT-WATER", area=north, service_code="water")
        electric = _active_route(dana, brazos, code="RT-ELEC", area=north, service_code="electric")
        premises = make_premises(dana, address_line="43 Two Crews Way")
        unit = make_unit(dana, premises["id"], label="Unit A")
        services.update_route(dana, water.id, {"unit_ids": [unit["id"]]})
        services.update_route(dana, electric.id, {"unit_ids": [unit["id"]]})

        services.ensure_service_point(unit["id"], "electric")
        point = models.ServicePoint.objects.get(
            tenant_id=brazos.id, unit_id=unit["id"], service__code="electric"
        )
    assert point.route_id == electric.id, "the electric meter is not read by the water crew"
