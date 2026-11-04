"""DEF-MET-9250 — a building a CASCADE puts on a route reaches the bill run.

Found by the custom-fields walk (one-time bill refused every seeded Brazos Bend
account, "No billing cycle") and traced in the New Connection walk: `A-10432` at
`P-00053` sits on `RT-005` (area IND) by per-unit route rows only. `RT-005` holds a
hand-picked building, so the derivation defines it by its picks — *"the area fills
an empty route, it does not overrule a picked one"* — and a cascade that wrote unit
rows only had put the unit on no cycle. 21 of 71 routed Brazos Bend properties.

⚠ WHAT WOULD MAKE THESE PASS WRONGLY: asserting the unit row or the service-point
stamp (both were written all along) — each case asks `units_in_cycle`, the bill
run's own question. And a fix that ADDED a pick to an area route that had none,
which would drop every other building in the area: the second case asserts the
area route stays pick-free and keeps both buildings.
"""

from __future__ import annotations

import pytest

from apps.metering import models, selectors

from tests import cr029_dynamism_fixtures as dyn
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db


def test_a_unit_cascaded_onto_a_PICKED_area_route_is_in_its_cycle(brazos, dana):
    with tenant_ctx(brazos):
        area = dyn.make_area(brazos, "IND-9246", "Industrial")
        cycle = dyn.active_cycle(dana, "CY-9246")
        picked = dyn.make_premises(dana, "1 Picked Way", area_code=area.code)
        picked_unit = dyn.make_unit(dana, picked["id"], label="Unit 1")
        route = dyn.active_route(
            dana,
            code="RT-9246",
            name="Industrial electric",
            area=area,
            service_code="electric",
            cycle=cycle,
            unit_ids=[picked_unit["id"]],
        )
        assert models.RoutePremisesMembership.objects.filter(route=route).count() == 1
        # …later, a building is created into the same area and gets a unit.
        late = dyn.make_premises(dana, "53 Cascade Way", area_code=area.code)
        late_unit = dyn.make_unit(dana, late["id"], label="Unit A")
        on_route_rows = models.RouteMembership.objects.filter(
            route=route, unit_id=late_unit["id"]
        ).exists()
        scoped = {str(value) for value in selectors.units_in_cycle(cycle.id)}
    assert on_route_rows, "the cascade put the unit on the route"
    assert str(picked_unit["id"]) in scoped
    assert str(late_unit["id"]) in scoped, "and the bill run can see it"


def test_an_area_route_with_no_pick_stays_an_area_route(brazos, dana):
    with tenant_ctx(brazos):
        area = dyn.make_area(brazos, "N-9246", "North")
        cycle = dyn.active_cycle(dana, "CY-9246N")
        route = dyn.active_route(
            dana, code="RT-9246N", name="North electric", area=area, service_code="electric", cycle=cycle
        )
        first = dyn.make_premises(dana, "1 North Way", area_code=area.code)
        first_unit = dyn.make_unit(dana, first["id"], label="Unit 1")
        second = dyn.make_premises(dana, "2 North Way", area_code=area.code)
        second_unit = dyn.make_unit(dana, second["id"], label="Unit 1")
        picks = models.RoutePremisesMembership.objects.filter(route=route).count()
        scoped = {str(value) for value in selectors.units_in_cycle(cycle.id)}
    assert picks == 0, "a cascade must not turn an area route into a picked one"
    assert {str(first_unit["id"]), str(second_unit["id"])} <= scoped
