# ── Trace ──────────────────────────────────────────────
# Change:   CR-006 (routes & cycles) — the residual half of DEF-227
# Defects:  DEF-227 (a service point inherited ANY of the unit's routes, not
#           the route for ITS OWN service). The READ half was fixed 2026-08-17
#           in `ensure_service_point`; this file is the WRITE half, which was
#           never touched and is the half that actually loses money.
# Rules:    BR-MET-033 (membership stamps the service point) · BR-MET-074 (a
#           unit is on ≤1 route PER SERVICE; a route with NO service is the
#           legacy ALL-SERVICES route — `_resolve_service`: *"a legitimate
#           answer and the one every shipped route holds"*) · BR-MET-076 ·
#           BR-MET-083 (the tagging cascade that made this reachable often)
# ───────────────────────────────────────────────────────
"""DEF-227, the half that was left: an ALL-SERVICES route must not TAKE OVER a
service point that already belongs to a route drawn for that service.

**Why the fix of 2026-08-17 was only half a fix.** DEF-227 was filed against the
READER — `ensure_service_point` asked `RouteMembership.objects.filter(unit).first()`
and got whichever membership came back first. That was fixed. But the two
STAMPERS have the same bug in the other direction:

    qs = ServicePoint.objects.filter(unit_id__in=unit_ids)
    if route.service_id:
        qs = qs.filter(service_id=route.service_id)
    qs.update(route=route, cycle=cycle)

When `route.service_id` is NULL — the all-services route, which is what every
route shipped before CR-006 gave routes a service actually is — the `if` does not
fire and the update lands on **every service point the unit has**, including one
already stamped with a water route. The water crew's meter is handed to the
all-services crew.

**And the money is in the second column of that UPDATE.** `cycle` is stamped in
the same statement, from the taking route. An all-services route with no cycle
sets `service_points.cycle_id = NULL`, and `selectors.units_in_cycle` — billing's
scope seam — reads exactly that column. So the unit does not merely get read by
the wrong crew: it drops out of the bill run and is never invoiced.

The RED PROOF IS INSIDE THE TESTS: each one asserts the specific wrong value the
old code produced (the all-services route id, and `cycle_id is None`) is NOT what
it finds, and the last test asserts the all-services route DOES still stamp the
service that has no route of its own — so a "fix" that simply stops stamping
fails here rather than passing by accident.
"""

import pytest

from apps.metering import models, selectors, services
from apps.tenancy import models as tenancy_models

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


def _active_cycle(actor, *, code):
    cycle = services.create_cycle(actor, {"code": code, "name": "Monthly", "frequency": "monthly"})
    models.Cycle.objects.filter(pk=cycle["id"]).update(status="active")
    return models.Cycle.objects.get(pk=cycle["id"])


def _active_route(actor, *, code, area=None, service_code=None, cycle=None):
    """A route created through the real service and then made active.

    `service_code` is OMITTED rather than passed as None when absent, because
    `_resolve_service` reads "key not present" as *leave the column alone* and
    "key present but empty" as *an all-services route* — and the shipped data
    holds the first shape.
    """
    payload = {
        "code": code,
        "name": f"{code} walk",
        "route_type": "walk",
    }
    if service_code is not None:
        payload["service_code"] = service_code
    if area is not None:
        payload["area_code"] = area.code
    if cycle is not None:
        payload["cycle_id"] = str(cycle.id)
    route = services.create_route(actor, payload)
    models.Route.objects.filter(pk=route["id"]).update(status="active")
    return models.Route.objects.get(pk=route["id"])


def _point(tenant, unit_id, service_code):
    return models.ServicePoint.objects.get(
        tenant_id=tenant.id, unit_id=unit_id, service__code=service_code
    )


def _fixture_unit_on_a_water_route(brazos, dana, area):
    """A unit whose WATER point is on a water route, and whose ELECTRIC point
    is on no route at all — the ordinary state of a house the utility reads for
    water on a water walk and has not yet routed for electric."""
    water_cycle = _active_cycle(dana, code="CY-WTR-227")
    # Codes chosen so `_routes_for_area`'s `order_by("code", "id")` puts the
    # ALL-SERVICES route FIRST. If it ran second the water route would win by
    # accident and the bug would hide — this ordering is load-bearing.
    all_services = _active_route(dana, code="RT-ALLSVC-227", area=area)
    water = _active_route(
        dana, code="RT-WATER-227", area=area, service_code="water", cycle=water_cycle
    )
    premises = make_premises(dana, address_line="51 Two Crews Way")
    unit = make_unit(dana, premises["id"], label="Unit A")
    services.ensure_service_point(unit["id"], "water")
    services.ensure_service_point(unit["id"], "electric")
    # The water crew's route, set the way a human sets it: on the wizard.
    services.update_route(dana, water.id, {"unit_ids": [unit["id"]]})
    assert _point(brazos, unit["id"], "water").route_id == water.id
    return premises, unit, water, all_services, water_cycle


def test_an_all_services_route_does_not_take_over_a_water_routed_point(brazos, dana):
    """DEF-227's write half, through BR-MET-083(a)'s cascade — the path that
    made a rare bug ordinary, because tagging a premises now touches every
    active route the area has instead of only the one a human opened."""
    with tenant_ctx(brazos):
        north = make_area(brazos, "N-227", "North")
        premises, unit, water, all_services, water_cycle = _fixture_unit_on_a_water_route(
            brazos, dana, north
        )

        services.update_premises(dana, premises["id"], {"area_code": "N-227"})

        point = _point(brazos, unit["id"], "water")
    assert point.route_id != all_services.id, (
        "DEF-227: the all-services route took the water point — this is the "
        "exact value the pre-fix code wrote"
    )
    assert point.route_id == water.id, "the water meter stays on the water crew's walk"
    assert point.cycle_id == water_cycle.id


def test_the_stolen_point_falls_out_of_the_bill_run(brazos, dana):
    """The money. `units_in_cycle` reads `service_points.cycle_id`, and the
    UPDATE that stole the point wrote `cycle = None` because the all-services
    route has no cycle. Silent, and the unit is simply never invoiced."""
    with tenant_ctx(brazos):
        north = make_area(brazos, "N-227B", "North")
        premises, unit, water, _all_services, water_cycle = _fixture_unit_on_a_water_route(
            brazos, dana, north
        )
        assert unit["id"] in selectors.units_in_cycle(water_cycle.id)

        services.update_premises(dana, premises["id"], {"area_code": "N-227B"})

        scoped = selectors.units_in_cycle(water_cycle.id)
        point = _point(brazos, unit["id"], "water")
    assert point.cycle_id is not None, "the pre-fix code wrote NULL here"
    assert unit["id"] in scoped, "a tagged premises must not vanish from its own bill run"


def test_the_route_wizard_cannot_steal_it_either(brazos, dana):
    """The same UPDATE lives in `_stamp_service_points`, the wizard's own
    stamper, so the cascade is not the only way in: editing the ALL-SERVICES
    route and adding this unit by hand walks the identical line."""
    with tenant_ctx(brazos):
        north = make_area(brazos, "N-227C", "North")
        _premises, unit, water, all_services, water_cycle = _fixture_unit_on_a_water_route(
            brazos, dana, north
        )

        services.update_route(dana, all_services.id, {"unit_ids": [unit["id"]]})

        water_point = _point(brazos, unit["id"], "water")
        electric_point = _point(brazos, unit["id"], "electric")
    assert water_point.route_id == water.id, "DEF-227: still the water crew's"
    assert water_point.cycle_id == water_cycle.id
    # …and the all-services route DOES take the service that has no route of
    # its own. A fix that just stopped stamping would pass the two assertions
    # above and fail this one.
    assert electric_point.route_id == all_services.id


def test_a_service_specific_route_still_stamps_its_own_service(brazos, dana):
    """The control. Nothing in this change may narrow the ordinary case: a
    water route stamps water points and leaves electric alone (BR-MET-033)."""
    with tenant_ctx(brazos):
        north = make_area(brazos, "N-227D", "North")
        water_cycle = _active_cycle(dana, code="CY-WTR-227D")
        water = _active_route(
            dana, code="RT-WATER-227D", area=north, service_code="water", cycle=water_cycle
        )
        premises = make_premises(dana, address_line="55 Control Way")
        unit = make_unit(dana, premises["id"], label="Unit A")
        services.ensure_service_point(unit["id"], "water")
        services.ensure_service_point(unit["id"], "electric")

        services.update_route(dana, water.id, {"unit_ids": [unit["id"]]})

        assert _point(brazos, unit["id"], "water").route_id == water.id
        assert _point(brazos, unit["id"], "electric").route_id is None
        assert premises is not None
