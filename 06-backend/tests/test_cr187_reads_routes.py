# ── Trace ──────────────────────────────────────────────
# Change:   CR-187-BRC10 — `GET work/mobile/routes` and `GET work/mobile/routes/{id}`
#           (07-endpoints.md N5).
# Story:    US-FLD-054 · US-FLD-055 · US-FLD-057 (previous AND expected) ·
#           US-FLD-058 (customer, unit label, account) · US-FLD-062
# Rules:    BR-FLD-00074 · BR-FLD-00076 · BR-FLD-00078 · BR-FLD-00079 ·
#           BR-FLD-00087 · CLAUDE.md hard rules 1, 3, 8 · NFR-3 / NFR-5
# Tests:    this file
# ───────────────────────────────────────────────────────
"""Downloading a route: the stops as PREMISES in walk order, every meter there
with its unit, previous reading and expected range, paged and uncapped."""

from __future__ import annotations

from decimal import Decimal

import pytest

from apps.metering import field_routes, walk_order
from apps.metering import models as metering_models

from tests.test_cr187_reads_helpers import *  # noqa: F401,F403
from tests.test_cr187_reads_helpers import (
    HIGH_PCT,
    LAST_DIAL,
    LOW_PCT,
    MONTHLY,
    build_route,
    reader_actor,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


@pytest.fixture()
def world(brazos, dana):
    with tenant_ctx(brazos):
        reader = reader_actor(brazos)
        route = build_route(brazos, dana, reader)
    return {"tenant": brazos, "admin": dana, "reader": reader, "route": route}


def test_my_routes_lists_the_readers_assigned_route_with_its_counts(world):
    with tenant_ctx(world["tenant"]):
        out = field_routes.my_routes(world["reader"])
        assert out["count"] == 1
        route = out["results"][0]
        assert route["code"] == "WLK-07"
        assert (route["stops"], route["meters"], route["sent"]) == (3, 4, 0)
        assert route["services"] == ["electric"]


def test_a_route_assigned_to_nobody_else_reaches_no_other_reader(world, brazos):
    with tenant_ctx(brazos):
        other = reader_actor(brazos, email="other@brazosbendutilities.test")
        assert field_routes.my_routes(other)["count"] == 0


def test_the_stop_is_the_premises_in_the_saved_walk_order_with_its_address(world):
    w, admin = world["route"], world["admin"]
    with tenant_ctx(world["tenant"]):
        # The office walks 1322 first, then 1318, then 1320 (D11 — per premises).
        walk_order.save_premises_order(
            admin, route_id=w.route_id, order=[w.premises[2], w.premises[0], w.premises[1]]
        )
        page = field_routes.route_page(world["reader"], w.route_id)
        lines = [stop["address"]["line"] for stop in page["stops"]]
        assert lines == ["1322 Maple St", "1318 Maple St", "1320 Maple St"]
        assert [stop["position"] for stop in page["stops"]] == [1, 2, 3]
        # Every meter at the address is at the ONE stop — master and units A, B.
        maple_1318 = page["stops"][1]
        assert sorted(m["meter_no"] for m in maple_1318["meters"]) == ["MTR-0471", "MTR-0472"]
        assert sorted(m["unit_label"] for m in maple_1318["meters"]) == ["Unit A", "Unit B"]


def test_each_meter_carries_its_unit_previous_reading_and_expected_range(world):
    """R78 (PO) — both on screen. The range is the engine's own thresholds over
    the engine's own trailing average: 47,700 + 700 × 50 % … 47,700 + 700 × 150 %
    → 48,050 … 48,750."""
    w = world["route"]
    with tenant_ctx(world["tenant"]):
        page = field_routes.route_page(world["reader"], w.route_id)
        meter = next(
            m for stop in page["stops"] for m in stop["meters"] if m["meter_no"] == "MTR-0471"
        )
        register = meter["registers"][0]
        assert register["register"] == "total"
        assert register["unit"] == "kWh"  # hard rule 3
        assert Decimal(register["previous"]["value"]) == LAST_DIAL
        low = LAST_DIAL + MONTHLY * LOW_PCT / 100
        high = LAST_DIAL + MONTHLY * HIGH_PCT / 100
        assert (Decimal(register["expected"]["low"]), Decimal(register["expected"]["high"])) == (
            low,
            high,
        )
        assert register["expected"]["basis"]["trailing_reads"] == 11
        assert meter["unit_of_measure"] == "kWh"


def test_a_meter_with_no_history_says_why_there_is_no_range(brazos, dana):
    with tenant_ctx(brazos):
        reader = reader_actor(brazos)
        w = build_route(brazos, dana, reader, history=False)
        page = field_routes.route_page(reader, w.route_id)
        register = page["stops"][0]["meters"][0]["registers"][0]
        assert register["previous"] is None
        assert register["expected"] is None
        assert register["expected_absent_reason"] == "no_previous_reading"
        assert register["unit"] == "kWh"


def test_the_stop_shows_the_customer_and_account_on_supply(world, brazos):
    """R79 (PO) — the customer's name beside the unit label and account no."""
    from tests import identity_fixtures
    from apps.customers import services as customers_services

    w = world["route"]
    with tenant_ctx(brazos):
        unit_id = metering_models.Unit.objects.get(
            premises_id=w.premises[0], label="Unit A"
        ).id
        from apps.metering import services as metering_services

        try:
            from tests.test_w9_event_reads import _plan

            metering_services.assign_unit_plan(
                world["admin"], unit_id, {"tariff_id": str(_plan(brazos).id)}
            )
        except Exception:  # noqa: BLE001 — a plan helps the account door, not the test
            pass
        account = customers_services.create_account(
            world["admin"],
            {
                "unit_id": str(unit_id),
                "account_type": "residential",
                "status": "active",
                "opened_at": "2026-01-05",
                "contact": {"full_name": "Carla Ruiz"},
                "customer": identity_fixtures.customer_block("Carla Ruiz", account_type="residential"),
            },
        )
        page = field_routes.route_page(world["reader"], w.route_id)
        meter = next(
            m for stop in page["stops"] for m in stop["meters"] if m["meter_no"] == "MTR-0471"
        )
        assert meter["customer_name"] == "Carla Ruiz"
        assert meter["account_no"] == account["account_no"]


def test_paged_by_stop_and_never_capped(brazos, dana):
    """NFR-3 / NFR-5 — 60 stops come back as 50 then 10; nothing is dropped."""
    from tests.test_cr187_reads_helpers import a_meter, make_premises, make_unit

    from apps.metering import services as metering_services

    with tenant_ctx(brazos):
        reader = reader_actor(brazos)
        premises = []
        for n in range(60):
            p = make_premises(dana, address_line=f"{100 + n} Oak Ave", services_available=["electric"])
            u = make_unit(dana, p["id"], label="Unit A", services=["electric"])
            a_meter(dana, f"OAK-{n:03d}", unit_id=u["id"])
            premises.append(p["id"])
        route = metering_services.create_route(
            dana, {"code": "OAK-1", "service_code": "electric", "premises_ids": premises}
        )
        metering_models.Route.objects.filter(pk=route["id"]).update(assigned_to_id=reader.id)
        first = field_routes.route_page(reader, route["id"], per=50)
        second = field_routes.route_page(reader, route["id"], page=first["next_page"], per=50)
        assert (first["count"], len(first["stops"]), first["next_page"]) == (60, 50, 2)
        assert (len(second["stops"]), second["next_page"]) == (10, None)
        seen = {s["premises_id"] for s in first["stops"] + second["stops"]}
        assert len(seen) == 60
        assert first["route"]["meters"] == 60


def test_an_excluded_meter_is_not_downloaded(world):
    w = world["route"]
    with tenant_ctx(world["tenant"]):
        metering_models.RouteMeterExclusion.objects.create(
            tenant_id=world["tenant"].id, route_id=w.route_id, asset_id=w.meters["MTR-0472"]["id"]
        )
        page = field_routes.route_page(world["reader"], w.route_id)
        listed = [m["meter_no"] for s in page["stops"] for m in s["meters"]]
        assert "MTR-0472" not in listed
        assert page["route"]["meters"] == 3


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-FLD-054@fa5746815 (CR-187-BRC10 route-reading server lane)
# generated: 2026-10-21 by the CR-187 reads server lane
# checklist: A✔ B✔ C✔ D✔ E=deferred(no frontend in this lane) F✔ G✔ H=deferred(no 🔒 path in a test)
# gates: see the lane report
# exceptions: none
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
