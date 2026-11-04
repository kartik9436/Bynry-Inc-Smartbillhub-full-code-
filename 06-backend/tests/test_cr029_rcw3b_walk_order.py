# ── Trace ──────────────────────────────────────────────
# Change:   CR-029 (PO 2026-08-23) — Routes & Cycles. Wave RC-W3b: the NINE
#           gaps where RC-W1 landed a table, RC-W3 landed a screen, and no
#           endpoint sat between them. Item 1 — **the walk-order writer**.
#           Screens: SET-06D (Premises tab · drag-to-reorder · Print route sheet)
# Design:   04-docs/02-decisions/17-cr029-routes-cycles-design.md (B17) §3, §6
# Rules:    D3 (*"Confirmed"* — build the ordering surface) · D11 (*"Per
#           premises"* — one stop, one number, however many units) ·
#           BR-MET-033 (membership) · BR-MET-035b (config writes are System
#           Admin) · BR-MET-048 (every route change is audited) ·
#           CLAUDE.md rule 1 (tenant scoping · RLS FORCE) · rule 6
#           (idempotency posture) · rule 7 (every action is audited)
# ───────────────────────────────────────────────────────
"""RC-W3b item 1 — `walk_order`'s first writer, at the grain the PO ruled.

**THIS IS THE GAP THIS WAVE EXISTS FOR.** B17 §5 gap G5, verbatim: *"`walk_order`
exists with a uniqueness constraint and **no writer**; no screen shows it, no
route sheet consumes it."* RC-W1 gave the sequence a home
(`route_premises_orders`, metering 0020) and RC-W3 built the drag-to-reorder
that fills it — and the SAVE 404s, because nothing mounts the path. So the
product has a table, a screen and no feature.

**D11 IS THE ASSERTION THAT MATTERS.** *"Per premises"*: 1408 Elm's three units
are ONE stop at ONE number, because a reader climbs those steps once. A writer
that wrote three rows would match the screenshot's per-unit numbering and be
wrong; the first test here is that shape, spelled out.

**AND THE ROUND TRIP IS PART OF THE FEATURE** (hard-won law 2 — built is not
wired). Saving an order that the route detail cannot read back is a save the
user watches undo itself on the next refresh, with every test still green.
"""

from typing import Any

import pytest

from apps.metering import models

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import make_premises, make_unit, staff_actor, tenant_ctx

pytestmark = pytest.mark.django_db


# ── the world: one route, two stops, four units ────────────────────────────
def _world(actor) -> dict[str, Any]:
    """1408 Elm (THREE units) and 12 Cedar Ct (one), both on RT-W3B.

    The three-unit building is the whole point of D11: it must produce ONE row
    in `route_premises_orders`, not three.
    """
    from apps.metering import services

    elm = make_premises(actor, address_line="1408 Elm St")
    cedar = make_premises(actor, address_line="12 Cedar Ct")
    for label in ("Unit 1", "Unit 2", "Unit 3"):
        make_unit(actor, elm["id"], label=label)
    make_unit(actor, cedar["id"], label="Unit A")
    route = services.create_route(
        actor,
        {
            "code": "RT-W3B",
            "name": "Elm and Cedar walk",
            "route_type": "walk",
            "service_codes": ["water"],
            "premises_ids": [elm["id"], cedar["id"]],
        },
    )
    return {"route": route, "elm": elm["id"], "cedar": cedar["id"]}


def _order_rows(route_id) -> list[tuple[str, int]]:
    return [
        (str(row.premises_id), row.walk_order)
        for row in models.RoutePremisesOrder.objects.filter(route_id=route_id).order_by(
            "walk_order"
        )
    ]


# ═══════════════════════════════════════════════════════════════════════════
# D11 — ONE STOP, ONE NUMBER
# ═══════════════════════════════════════════════════════════════════════════
def test_w3b_1__the_order_is_written_one_row_per_premises(brazos, dana):
    """A three-unit building is ONE stop at ONE sequence number (D11)."""
    from apps.metering import walk_order

    with tenant_ctx(brazos):
        world = _world(dana)
        saved = walk_order.save_premises_order(
            dana,
            route_id=world["route"]["id"],
            order=[
                {"premises_id": world["cedar"], "walk_order": 1},
                {"premises_id": world["elm"], "walk_order": 2},
            ],
        )

        assert _order_rows(world["route"]["id"]) == [(world["cedar"], 1), (world["elm"], 2)]
        # Four units, TWO stops — the number the PO's audit row counts.
        assert saved["resequenced"] == 2
        assert [stop["premises_id"] for stop in saved["order"]] == [world["cedar"], world["elm"]]


def test_w3b_1__reordering_swaps_positions_without_tripping_uniqueness(brazos, dana):
    """`uq_route_premises_orders_walk_order` is not deferrable, so a swap that
    updated rows in place would collide mid-write. The stop order is REPLACED
    inside one transaction."""
    from apps.metering import walk_order

    with tenant_ctx(brazos):
        world = _world(dana)
        first = [
            {"premises_id": world["elm"], "walk_order": 1},
            {"premises_id": world["cedar"], "walk_order": 2},
        ]
        walk_order.save_premises_order(dana, route_id=world["route"]["id"], order=first)
        walk_order.save_premises_order(
            dana,
            route_id=world["route"]["id"],
            order=[
                {"premises_id": world["cedar"], "walk_order": 1},
                {"premises_id": world["elm"], "walk_order": 2},
            ],
        )
        assert _order_rows(world["route"]["id"]) == [(world["cedar"], 1), (world["elm"], 2)]
        assert models.RoutePremisesOrder.objects.filter(route_id=world["route"]["id"]).count() == 2


def test_w3b_1__saving_the_same_order_twice_changes_nothing(brazos, dana):
    """CLAUDE.md rule 6's posture: a retry finds the order, it does not write a
    second one, and it says so rather than claiming a change."""
    from apps.metering import walk_order

    with tenant_ctx(brazos):
        world = _world(dana)
        payload = [
            {"premises_id": world["elm"], "walk_order": 1},
            {"premises_id": world["cedar"], "walk_order": 2},
        ]
        first = walk_order.save_premises_order(dana, route_id=world["route"]["id"], order=payload)
        second = walk_order.save_premises_order(dana, route_id=world["route"]["id"], order=payload)
        assert first["changed"] is True
        assert second["changed"] is False
        assert _order_rows(world["route"]["id"]) == [(world["elm"], 1), (world["cedar"], 2)]


# ═══════════════════════════════════════════════════════════════════════════
# THE PAYLOAD IS THE WHOLE WALK — omissions and duplicates are refused
# ═══════════════════════════════════════════════════════════════════════════
def test_w3b_1__a_payload_that_omits_a_member_is_refused(brazos, dana):
    """A saved walk with a stop missing is a premises nobody visits. The
    order names every member or it is not an order."""
    from core import errors

    from apps.metering import walk_order

    with tenant_ctx(brazos):
        world = _world(dana)
        with pytest.raises(errors.ValidationError):
            walk_order.save_premises_order(
                dana,
                route_id=world["route"]["id"],
                order=[{"premises_id": world["elm"], "walk_order": 1}],
            )
        assert models.RoutePremisesOrder.objects.filter(route_id=world["route"]["id"]).count() == 0


def test_w3b_1__a_payload_that_repeats_a_stop_is_refused(brazos, dana):
    from core import errors

    from apps.metering import walk_order

    with tenant_ctx(brazos):
        world = _world(dana)
        with pytest.raises(errors.ValidationError):
            walk_order.save_premises_order(
                dana,
                route_id=world["route"]["id"],
                order=[
                    {"premises_id": world["elm"], "walk_order": 1},
                    {"premises_id": world["elm"], "walk_order": 2},
                    {"premises_id": world["cedar"], "walk_order": 3},
                ],
            )
        assert models.RoutePremisesOrder.objects.filter(route_id=world["route"]["id"]).count() == 0


def test_w3b_1__two_stops_may_not_claim_one_position(brazos, dana):
    from core import errors

    from apps.metering import walk_order

    with tenant_ctx(brazos):
        world = _world(dana)
        with pytest.raises(errors.ValidationError):
            walk_order.save_premises_order(
                dana,
                route_id=world["route"]["id"],
                order=[
                    {"premises_id": world["elm"], "walk_order": 1},
                    {"premises_id": world["cedar"], "walk_order": 1},
                ],
            )


def test_w3b_1__a_premises_that_is_not_on_the_route_is_refused(brazos, dana):
    from core import errors

    from apps.metering import walk_order

    with tenant_ctx(brazos):
        world = _world(dana)
        stranger = make_premises(dana, address_line="9 Nowhere Rd")
        with pytest.raises(errors.ValidationError):
            walk_order.save_premises_order(
                dana,
                route_id=world["route"]["id"],
                order=[
                    {"premises_id": world["elm"], "walk_order": 1},
                    {"premises_id": world["cedar"], "walk_order": 2},
                    {"premises_id": stranger["id"], "walk_order": 3},
                ],
            )


# ═══════════════════════════════════════════════════════════════════════════
# THE AUDIT ROW THE PO'S OWN SCREENSHOT SHOWS
# ═══════════════════════════════════════════════════════════════════════════
def test_w3b_1__the_resequence_is_audited(brazos, dana, audit_rows):
    """SET-06D's change log draws *"Walking order changed · 4 members
    resequenced"*, so the row has to carry the count as well as the fact."""
    from apps.metering import walk_order

    with tenant_ctx(brazos):
        world = _world(dana)
        walk_order.save_premises_order(
            dana,
            route_id=world["route"]["id"],
            order=[
                {"premises_id": world["elm"], "walk_order": 1},
                {"premises_id": world["cedar"], "walk_order": 2},
            ],
        )
    rows = [row for row in audit_rows if row.get("action") == "route.premises_order_changed"]
    assert len(rows) == 1
    assert str(rows[0]["entity_id"]) == str(world["route"]["id"])
    assert rows[0]["entity_type"] == "route"
    assert rows[0]["after"]["resequenced"] == 2


# ═══════════════════════════════════════════════════════════════════════════
# TENANCY — hard rule 1
# ═══════════════════════════════════════════════════════════════════════════
def test_w3b_1__another_tenants_route_is_absent(brazos, dana, lonestar, erin):
    """An unknown id, a malformed id and another tenant's id are ONE answer."""
    from core import errors

    from apps.metering import walk_order

    with tenant_ctx(brazos):
        world = _world(dana)
    with tenant_ctx(lonestar):
        with pytest.raises(errors.NotFoundError):
            walk_order.save_premises_order(
                erin,
                route_id=world["route"]["id"],
                order=[{"premises_id": world["elm"], "walk_order": 1}],
            )


def test_w3b_1__a_billing_clerk_may_not_resequence_a_route(brazos, dana):
    """BR-MET-035b — reads are open to every role, config WRITES are System
    Admin. The service refuses whoever calls it from anywhere."""
    from core import errors

    from apps.metering import walk_order

    with tenant_ctx(brazos):
        world = _world(dana)
        clerk = staff_actor(brazos, "billing_clerk", "clerk@walkorder.test")
        with pytest.raises(errors.AuthError):
            walk_order.save_premises_order(
                clerk,
                route_id=world["route"]["id"],
                order=[
                    {"premises_id": world["elm"], "walk_order": 1},
                    {"premises_id": world["cedar"], "walk_order": 2},
                ],
            )


# ═══════════════════════════════════════════════════════════════════════════
# THE ROUND TRIP — the screen reads back what it saved (hard-won law 2)
# ═══════════════════════════════════════════════════════════════════════════
def test_w3b_1__the_saved_order_is_what_the_route_detail_serves_back(brazos, dana):
    """`GET /routes/{id}` is what SET-06D re-reads after a save. Cedar first
    must still be Cedar first — through `premises_order` (the ruled grain) AND
    through the membership hint the shipped screen folds into stops."""
    from apps.metering import selectors, walk_order

    with tenant_ctx(brazos):
        world = _world(dana)
        walk_order.save_premises_order(
            dana,
            route_id=world["route"]["id"],
            order=[
                {"premises_id": world["cedar"], "walk_order": 1},
                {"premises_id": world["elm"], "walk_order": 2},
            ],
        )
        detail = selectors.route_detail(world["route"]["id"])

    assert [stop["premises_id"] for stop in detail["premises_order"]] == [
        world["cedar"],
        world["elm"],
    ]
    # The membership the screen actually folds into stops (`premisesStops`
    # orders by the lowest per-unit hint) must agree with the ruled order, or
    # the save appears to undo itself on the next refresh.
    seen: list[str] = []
    for member in detail["membership"]:
        if member["premises_id"] not in seen:
            seen.append(member["premises_id"])
    assert seen == [world["cedar"], world["elm"]]


def test_w3b_1__editing_the_route_does_not_lose_the_saved_walk_order(brazos, dana):
    """⚠ **THE SILENT UNDO THIS TEST EXISTS FOR.**

    `services._set_route_membership` writes `walk_order=None` for every
    premises-selected member on EVERY route edit — so renaming a route through
    the wizard wiped the per-unit column, and a screen that ordered its stops
    by that column would draw insertion order again while
    `route_premises_orders` still held the saved walk. Nothing would have
    failed: the table is right, the endpoint is right, and the walk a person
    saved is gone from the only place they look.

    The served order is therefore DERIVED from the ruled table, not read from
    the column it projects into.
    """
    from apps.metering import selectors, services, walk_order

    with tenant_ctx(brazos):
        world = _world(dana)
        walk_order.save_premises_order(
            dana,
            route_id=world["route"]["id"],
            order=[
                {"premises_id": world["cedar"], "walk_order": 1},
                {"premises_id": world["elm"], "walk_order": 2},
            ],
        )
        # The wizard's own save: same members, a new name.
        services.update_route(
            dana,
            world["route"]["id"],
            {
                "name": "Elm and Cedar walk (renamed)",
                "premises_ids": [world["elm"], world["cedar"]],
            },
        )
        detail = selectors.route_detail(world["route"]["id"])

    assert [stop["premises_id"] for stop in detail["premises_order"]] == [
        world["cedar"],
        world["elm"],
    ]
    seen: list[str] = []
    for member in detail["membership"]:
        if member["premises_id"] not in seen:
            seen.append(member["premises_id"])
    assert seen == [world["cedar"], world["elm"]]
    # And the hint the screen sorts by is the STOP's number (D11), not the
    # per-unit column's — every unit of Cedar Ct carries stop 1.
    cedar_hints = {
        member["walk_order"]
        for member in detail["membership"]
        if member["premises_id"] == world["cedar"]
    }
    assert cedar_hints == {1}


# ═══════════════════════════════════════════════════════════════════════════
# THE ROUTE IS MOUNTED — an endpoint nobody can call is the same defect
# ═══════════════════════════════════════════════════════════════════════════
def test_w3b_1__put_premises_order_is_mounted_and_answers(brazos, dana):
    from django.urls import resolve

    from apps.metering import api

    from tests.test_us_ten_helpers import api_call

    with tenant_ctx(brazos):
        world = _world(dana)

    match = resolve(f"/api/brazosbend/routes/{world['route']['id']}/premises-order")
    assert match.func is api.route_premises_order

    response = api_call(
        api.route_premises_order,
        "put",
        user=dana.user,
        role="system_admin",
        tenant=brazos,
        data={
            "order": [
                {"premises_id": world["cedar"], "walk_order": 1},
                {"premises_id": world["elm"], "walk_order": 2},
            ]
        },
        route_id=world["route"]["id"],
    )
    assert response.status_code == 200
    assert response.data["resequenced"] == 2
