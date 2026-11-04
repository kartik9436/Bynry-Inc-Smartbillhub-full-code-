# ── Trace ──────────────────────────────────────────────
# Change:   CR-006 (routes & cycles) — the residual half of DEF-225
# Defects:  DEF-225 (a unit added to a premises already on a route never joins
#           it, so it is never read and never billed). BR-MET-083(b) closed the
#           unit-added-later path on 2026-08-17; this file closes the mirror
#           path the DRAFT boundary opened.
# Rules:    BR-MET-082 + Amendment 1 (*"any change any movement make the
#           changes to downstream"*) · BR-MET-083(a) (a premises tagged into an
#           area joins that area's ACTIVE routes) · BR-MET-076 / DEF-219 (*"a
#           draft affects nothing"* — a draft route gains nothing from a tag) ·
#           BR-MET-074 (≤1 route per service; a cascade never takes a unit off
#           another route)
# ───────────────────────────────────────────────────────
"""DEF-225's remaining hole: a tag made while the route was a DRAFT is dropped
on the floor and never paid back when the route is activated.

**The two rules that combine into a revenue hole.** BR-MET-083(a) says a premises
tagged into an area joins that area's routes. DEF-219 says a DRAFT route must
gain nothing from that tag, because *"a draft affects nothing"* and the Members
column on SET-05 counts memberships. Both are right. But `_routes_for_area`
filters `status="active"`, so the draft is skipped and **nothing ever comes back
for it** — activation re-stamps the membership the wizard set and never re-asks
the area question.

So the ordinary onboarding order loses buildings silently:

    1. draft the new water route for the North district
    2. tag the district's premises into North   ← correctly skipped, draft
    3. activate the route                        ← never re-asked

and every premises tagged at step 2 is on no route, is never read, and is never
billed. It is DEF-225's own mechanism — an upstream change that never reaches the
route — arriving from the other side.

**What this deliberately does NOT do**, because DEF-225 keeps it open and a lane
may not close an open question by choosing a value: it does not re-derive a
route's members when the route's `area_id` is CHANGED on an already-active route,
and it does not turn membership into a run-time derivation. Both remain listed on
the DEF-225 row. The scope here is exactly the deferral the draft boundary
created, paid back at the moment the deferral ends.

The RED PROOF IS INSIDE THE TESTS: the draft-boundary assertion (*"zero members
while it is a draft"*) runs in the same test, immediately before the activation,
so the test cannot pass by a fix that simply stopped honouring the draft rule.
"""

import pytest

from apps.metering import models, selectors, services
from apps.tenancy import models as tenancy_models

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import (
    audit_actions,
    make_premises,
    make_unit,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


def make_area(tenant, code, name, parent=None):
    return tenancy_models.Area.objects.create(
        tenant_id=tenant.id, code=code, name=name, parent=parent
    )


def _active_cycle(actor, *, code):
    cycle = services.create_cycle(actor, {"code": code, "name": "Monthly", "frequency": "monthly"})
    models.Cycle.objects.filter(pk=cycle["id"]).update(status="active")
    return models.Cycle.objects.get(pk=cycle["id"])


def _draft_route(actor, *, code, area, service_code="electric", cycle=None):
    payload = {
        "code": code,
        "name": f"{code} walk",
        "route_type": "walk",
        "service_code": service_code,
        "area_code": area.code,
        "status": "draft",
    }
    if cycle is not None:
        payload["cycle_id"] = str(cycle.id)
    row = services.create_route(actor, payload)
    assert row["status"] == "draft"
    return models.Route.objects.get(pk=row["id"])


def test_activating_a_drafted_route_picks_up_the_premises_tagged_while_it_was_a_draft(
    brazos, dana
):
    """DEF-225, arriving from the draft side. The tag at step 2 is correctly
    ignored while the route is a draft; if activation does not re-ask, the tag
    is lost forever and the building is never read."""
    with tenant_ctx(brazos):
        north = make_area(brazos, "N-ACT", "North")
        route = _draft_route(dana, code="RT-ACT-1", area=north)

        premises = make_premises(dana, address_line="61 Drafted Way", area_code="N-ACT")
        unit = make_unit(dana, premises["id"], label="Unit A", services=["electric"])

        # DEF-219's boundary, asserted HERE so that a "fix" which simply let
        # drafts take members would fail this line instead of passing below.
        assert selectors.route_members(route.id) == [], "a draft gains nothing from a tag"

        services.update_route(dana, route.id, {"status": "active"})

        members = selectors.route_members(route.id)
    assert [m["unit_id"] for m in members] == [unit["id"]], (
        "the pre-fix code left this list EMPTY — the premises tagged into North "
        "while the route was drafted was never read and never billed"
    )


def test_the_recovered_premises_reaches_the_bill_run(brazos, dana):
    """The money, asserted at billing's own scope seam rather than on the
    membership table — `units_in_cycle` reads `service_points.cycle_id`, so a
    membership that does not reach the stamp is a membership a bill run cannot
    see (BR-MET-082 Amendment 1)."""
    with tenant_ctx(brazos):
        north = make_area(brazos, "N-ACT2", "North")
        cycle = _active_cycle(dana, code="CY-ACT2")
        route = _draft_route(dana, code="RT-ACT-2", area=north, cycle=cycle)

        premises = make_premises(dana, address_line="63 Drafted Way", area_code="N-ACT2")
        unit = make_unit(dana, premises["id"], label="Unit A", services=["electric"])
        assert selectors.units_in_cycle(cycle.id) == [], "a draft affects no bill run"

        services.update_route(dana, route.id, {"status": "active"})

        scoped = selectors.units_in_cycle(cycle.id)
    assert scoped == [unit["id"]], "the pre-fix code returned [] — nothing was ever invoiced"


def test_a_sub_area_premises_is_picked_up_by_the_parents_activated_route(brazos, dana):
    """The area question is asked DOWNWARD here (a route for South covers South
    and South · SE), which is the same statement `_routes_for_area` reads upward
    for a single premises. One rule, two directions, and they must agree."""
    with tenant_ctx(brazos):
        south = make_area(brazos, "S-ACT", "South")
        south_east = make_area(brazos, "S-ACT-E", "South East", parent=south)
        route = _draft_route(dana, code="RT-ACT-3", area=south)

        premises = make_premises(dana, address_line="65 Sub Way", area_code=south_east.code)
        unit = make_unit(dana, premises["id"], label="Unit A", services=["electric"])

        services.update_route(dana, route.id, {"status": "active"})
        members = selectors.route_members(route.id)
    assert [m["unit_id"] for m in members] == [unit["id"]]


def test_activation_never_takes_a_unit_off_another_active_route(brazos, dana):
    """BR-MET-083 boundary 2, restated for this path. A move between routes of
    the same service is BR-MET-074's move and the CR requires it be confirmed
    on screen (*"selecting moves them, with confirm"*). Activating a route on
    another screen is not that confirmation, so the cascade only ever fills a
    gap."""
    with tenant_ctx(brazos):
        north = make_area(brazos, "N-ACT4", "North")
        incumbent = services.create_route(
            dana,
            {
                "code": "RT-ACT-4A",
                "name": "incumbent",
                "route_type": "walk",
                "service_code": "electric",
                "status": "active",
            },
        )
        premises = make_premises(dana, address_line="67 Held Way", area_code="N-ACT4")
        unit = make_unit(dana, premises["id"], label="Unit A", services=["electric"])
        services.update_route(dana, incumbent["id"], {"unit_ids": [unit["id"]]})

        newcomer = _draft_route(dana, code="RT-ACT-4B", area=north)
        services.update_route(dana, newcomer.id, {"status": "active"})

        assert [m["unit_id"] for m in selectors.route_members(incumbent["id"])] == [unit["id"]]
        assert selectors.route_members(newcomer.id) == [], "a gap-filler, never a thief"


def test_activation_without_an_area_changes_nothing(brazos, dana):
    """A route with no area covers nothing by area, so activating it must not
    sweep the tenant's untagged premises into it. The no-op case is the one a
    cascade gets wrong most expensively."""
    with tenant_ctx(brazos):
        premises = make_premises(dana, address_line="69 Untagged Way")
        make_unit(dana, premises["id"], label="Unit A", services=["electric"])
        row = services.create_route(
            dana,
            {
                "code": "RT-ACT-5",
                "name": "no area",
                "route_type": "walk",
                "service_code": "electric",
                "status": "draft",
            },
        )
        services.update_route(dana, row["id"], {"status": "active"})
        assert selectors.route_members(row["id"]) == []


def test_an_activation_that_states_its_members_is_not_argued_with(brazos, dana):
    """The boundary that keeps this from being a re-derivation. SET-06 step 2
    lets an admin pick a DELIBERATE SUBSET of an area's premises, and a request
    that activates the route AND states its member list is that admin saying so
    in the same breath. Adding the rest of the area on top would overrule a
    human decision made one field away — so the cascade sits out any request
    that carries a membership, and repays the tag on the next
    activation-shaped one instead."""
    with tenant_ctx(brazos):
        north = make_area(brazos, "N-ACT7", "North")
        route = _draft_route(dana, code="RT-ACT-7", area=north)
        chosen_premises = make_premises(dana, address_line="73 Chosen Way", area_code="N-ACT7")
        chosen = make_unit(dana, chosen_premises["id"], label="Unit A", services=["electric"])
        other_premises = make_premises(dana, address_line="75 Not Chosen Way", area_code="N-ACT7")
        make_unit(dana, other_premises["id"], label="Unit A", services=["electric"])

        services.update_route(
            dana, route.id, {"status": "active", "unit_ids": [chosen["id"]]}
        )

        members = selectors.route_members(route.id)
    assert [m["unit_id"] for m in members] == [chosen["id"]], (
        "the admin named one unit in the same request; the area must not add the other"
    )


def test_the_activation_cascade_is_audited_on_the_route(brazos, dana, audit_rows):
    """CR-006: *"All CRUD audit-logged (who, when, before/after member
    counts)"*. A utility asking "why did RT-ACT-6 open with 1 member when I
    drafted it empty" has to find the answer on the route."""
    with tenant_ctx(brazos):
        north = make_area(brazos, "N-ACT6", "North")
        route = _draft_route(dana, code="RT-ACT-6", area=north)
        premises = make_premises(dana, address_line="71 Audited Way", area_code="N-ACT6")
        make_unit(dana, premises["id"], label="Unit A", services=["electric"])
        del audit_rows[:]
        services.update_route(dana, route.id, {"status": "active"})
    assert "route.members_cascaded" in audit_actions(audit_rows)
