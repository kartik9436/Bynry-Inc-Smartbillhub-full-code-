"""DEF-MET-9230 — a New Connection's units join the Read route picked on step 2.

Found by the New Connection end-to-end web walk (2026-10-02, stage 13): every unit of
the eight builds sat on no route and no billing cycle (their service points had
`route_id`/`cycle_id` NULL, where the sample premises had both), so no cycle run could
reach a new build and the master account's first bill was refused *no billing cycle*.
`create_premises` joins the PREMISES' units to the chosen route, and a New Connection
creates its premises before its units — the join had nothing to act on.
"""

from __future__ import annotations

import pytest

from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from apps.metering import derivation
from apps.metering import models as metering_models
from tests.test_new_connect_step7_messages import _address
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import make_plan, tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db


def test_every_new_unit_is_on_the_route_step_2_picked(dana, brazos):
    with tenant_ctx(brazos):
        cycle = metering_models.Cycle.objects.create(
            tenant=brazos, code="CY-NCW-9230", name="New builds cycle"
        )
        route = metering_models.Route.objects.create(
            tenant=brazos, code="RT-NCW-9230", name="New builds walk", route_type="walk",
            cycle=cycle, status="active",
        )
        plan = make_plan(brazos)
        created = w6.create_connection(dana, {"premises": _address(dana, "30 Route Join Way")})
        w6.commit_connection(
            dana,
            created["id"],
            {
                "premises": {"read_route": "RT-NCW-9230"},
                "units": [{"label": "Unit 1"}, {"label": "Unit 2"}],
                "plan_assignments": [
                    {"unit_label": "Unit 1", "tariff_id": str(plan.id)},
                    {"unit_label": "Unit 2", "tariff_id": str(plan.id)},
                ],
            },
        )
        premises_id = work_tables.Connection.objects.get(pk=created["id"]).premises_id
        on_route = set(
            metering_models.RouteMembership.objects.filter(route=route).values_list(
                "unit__label", flat=True
            )
        )
        units = dict(
            metering_models.Unit.objects.filter(premises_id=premises_id).values_list("id", "label")
        )
        # What the BILL RUN asks (BR-MET-082, CR-131): the building is on the
        # route's set, so its units are in the route's cycle.
        in_cycle = set(derivation.units_in_cycle(cycle.id))
    assert set(units.values()) == {"Unit 1", "Unit 2"}
    assert on_route == set(units.values())
    assert {str(unit_id) for unit_id in units} <= in_cycle


def test_no_route_picked_joins_nothing(dana, brazos):
    with tenant_ctx(brazos):
        plan = make_plan(brazos)
        created = w6.create_connection(dana, {"premises": _address(dana, "31 No Route Way")})
        w6.commit_connection(
            dana,
            created["id"],
            {
                "units": [{"label": "Unit 1"}, {"label": "Unit 2"}],
                "plan_assignments": [{"unit_label": "Unit 1", "tariff_id": str(plan.id)}],
            },
        )
        premises_id = work_tables.Connection.objects.get(pk=created["id"]).premises_id
        assert not metering_models.RouteMembership.objects.filter(unit__premises_id=premises_id).exists()
