# ── Trace ──────────────────────────────────────────────
# Story:    US-WRK-004 (EP-WRK-01) — the Work rail entry becomes the shell; its
#           Orders tab lists every open order across every connection and
#           every account (`GET /work-orders`). US-WRK-001 — an order with no
#           connection is in the list and its connection is null.
# Rules:    BR-WRK-001 (Work owns the list) · BR-WRK-006 (the premise comes
#           from whichever anchor the order has) · BR-SHL-011 (q/page/per) ·
#           A4 (any tenant role may read this family) · OQ-371 (the New
#           connects segments still refuse — unchanged by this wave) ·
#           CLAUDE.md hard rule 1
# Tests:    this file — the route resolves through config/urls.py; the list;
#           the dash; search; the clerk may read; isolation; OQ-371 untouched
# ───────────────────────────────────────────────────────
"""US-WRK-004 / US-WRK-001 — `GET /work-orders`, the Orders tab's read."""

from __future__ import annotations

import pytest
from django.urls import resolve

from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from apps.work import api as work_api
from apps.work import services as work_services
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · marcus · erin
from tests.test_us_met_helpers import field_close  # CR-168 P1.34 — close as the field
from tests.test_us_met_helpers import make_premises, make_unit, tenant_ctx
from tests.test_us_ten_helpers import api_call

pytestmark = pytest.mark.django_db


def _list(tenant, actor, role, query=None):
    return api_call(
        work_api.work_orders,
        "get",
        f"/api/{tenant.subdomain}/work-orders",
        user=actor.user,
        role=role,
        tenant=tenant,
        query=query,
    )


def _a_build_with_orders(actor, address, orders):
    premises = make_premises(actor, address_line=address)
    unit = make_unit(actor, premises["id"])
    created = w6.create_connection(actor, {"premises_id": premises["id"]})
    connection = work_tables.Connection.objects.get(pk=created["id"])
    w6.add_connection_service(actor, connection.id, service_code="water", unit_id=unit["id"])
    for order_type in orders:
        w6.create_work_order(actor, connection.id, {"type": order_type, "service": "water"})
    return connection


def test_us_wrk_004_the_route_resolves_through_config_urls():
    """A future lane cannot lose the include silently (config/urls.py's rule)."""
    match = resolve("/api/brazosbend/work-orders")
    assert match.func is work_api.work_orders


def test_us_wrk_004_the_list_holds_every_open_order_across_two_builds_and_no_build(dana, brazos):
    with tenant_ctx(brazos):
        first = _a_build_with_orders(dana, "500 Main St", ["Meter set", "Service drop"])
        second = _a_build_with_orders(dana, "Ridgeway Mews", ["Tap and service line"])
        cedar = make_premises(dana, address_line="77 Cedar Ct", services_available=["water"])
        # `DEF-WRK-4636` — a LIVE seed type. This read *Leak investigation*, one
        # of the eight types `work/0023` retired on 2026-09-07 (BR-WRK-058); a
        # retired name resolves to no type, so the job carried no priority and
        # the case below went red for a month. *Consumer Complaint* is the PO's
        # own spine type and seeds at HIGH.
        leak = work_services.raise_work_order(
            dana, {"type": "Consumer Complaint", "service": "water", "premises_id": cedar["id"]}
        )
        # A completed order that nobody accepted is the approval queue's, not this list's.
        finished = w6.create_work_order(dana, first.id, {"type": "Gas tap", "service": "water"})
        field_close(dana, finished["id"], field_data={"ok": True}, outcome="passed")

    data = _list(brazos, dana, "system_admin").data
    assert set(data) == {"count", "next", "previous", "results"}
    rows = {row["order_no"]: row for row in data["results"]}
    assert data["count"] == 4 and len(rows) == 4
    assert finished["order_no"] not in rows

    by_connection = {
        row["connection"]["connection_no"] for row in rows.values() if row["connection"]
    }
    assert by_connection == {first.connection_no, second.connection_no}

    cedar_row = rows[leak["order_no"]]
    assert cedar_row["connection"] is None  # the screen draws a dash here
    assert cedar_row["premise"]["address"] == "77 Cedar Ct"
    assert cedar_row["service"] == "water"
    assert cedar_row["state"] == "planned" and cedar_row["outcome"] is None

    main_st = rows[next(no for no, row in rows.items() if row["type"] == "Meter set")]
    assert main_st["premise"]["address"] == "500 Main St"  # the CONNECTION's premises
    assert main_st["connection"]["connection_no"] == first.connection_no

    # ⚠ **AMENDED BY CR-070 WAVE G (2026-09-05), AND WAVE A WROTE THE RELEASE
    # CONDITION ITSELF.** This case read *"sorted by order number, ascending"*,
    # under an `OrdersPage.tsx` comment saying *"the server fixes the order
    # (order number, ascending) **until the dispatcher's columns exist**"*. They
    # exist now, so the clause has expired: `BR-WRK-018` says lists sort by RANK
    # THEN DUE TIME and `Work-007`'s footer says so in words a clerk reads —
    # *sorted by priority then due time*. A hold that named its own release,
    # released by the wave that met it (hard-won law 2's mirror clause).
    #
    # ⚠ **AND THE OBSERVATION REALLY MOVED — IT IS NOT THE SAME ASSERTION WITH A
    # NEW COMMENT.** *Consumer Complaint* is a seeded job type (it read *Leak
    # investigation* until that type was retired — `DEF-WRK-4636`) and carries
    # a default priority of HIGH (rank 2); *Meter set*, *Service
    # drop* and *Tap and service line* match no catalogue row, so they carry no
    # priority at all. The leak therefore sorts FIRST although it was raised
    # LAST, which is the whole point of the change, and the three with no
    # priority sort last rather than first — a job nobody prioritised is not
    # more urgent than one somebody marked High.
    numbers = [row["order_no"] for row in data["results"]]
    assert numbers[0] == leak["order_no"], "the only prioritised job leads, whenever it was raised"
    assert numbers[1:] == sorted(numbers[1:]), "with no priority and no due date, by order number"
    assert rows[leak["order_no"]]["priority"]["code"] == "HIGH"
    assert all(rows[no]["priority"] is None for no in numbers[1:])


def test_us_wrk_004_search_matches_the_order_the_address_and_the_connection(dana, brazos):
    with tenant_ctx(brazos):
        build = _a_build_with_orders(dana, "500 Main St", ["Meter set"])
        cedar = make_premises(dana, address_line="77 Cedar Ct", services_available=["water"])
        leak = work_services.raise_work_order(
            dana, {"type": "Leak investigation", "premises_id": cedar["id"]}
        )

    assert {
        r["order_no"] for r in _list(brazos, dana, "system_admin", {"q": "Cedar"}).data["results"]
    } == {leak["order_no"]}
    assert _list(brazos, dana, "system_admin", {"q": build.connection_no}).data["count"] == 1
    assert _list(brazos, dana, "system_admin", {"q": leak["order_no"]}).data["count"] == 1
    assert _list(brazos, dana, "system_admin", {"q": "nothing like this"}).data["count"] == 0
    # BR-SHL-011: an out-of-range page clamps to the last page, never errors;
    # `per=75` clamps DOWN to 50 and two rows fit on one page, so there is no
    # next and no previous — the whole list is the answer.
    clamped = _list(brazos, dana, "system_admin", {"page": "99", "per": "75"}).data
    assert clamped["count"] == 2 and len(clamped["results"]) == 2
    assert clamped["next"] is None and clamped["previous"] is None


def test_us_wrk_004_a_billing_clerk_may_read_the_list(marcus, dana, brazos):
    """A4: this family gives every tenant role a read; the writes are gated
    where they live (wave B's routes)."""
    with tenant_ctx(brazos):
        cedar = make_premises(dana, address_line="77 Cedar Ct")
        work_services.raise_work_order(
            dana, {"type": "Leak investigation", "premises_id": cedar["id"]}
        )
    response = _list(brazos, marcus, "billing_clerk")
    assert response.status_code == 200 and response.data["count"] == 1


def test_us_wrk_004_tc5_lone_star_ridge_lists_only_its_own(dana, erin, brazos, lonestar):
    with tenant_ctx(brazos):
        cedar = make_premises(dana, address_line="77 Cedar Ct")
        work_services.raise_work_order(
            dana, {"type": "Leak investigation", "premises_id": cedar["id"]}
        )
    with tenant_ctx(lonestar):
        theirs = make_premises(erin, address_line="1 Ridge Rd", services_available=["water"])
        mine = work_services.raise_work_order(
            erin, {"type": "Backflow test", "premises_id": theirs["id"]}
        )
    data = _list(lonestar, erin, "system_admin").data
    assert data["count"] == 1 and data["results"][0]["order_no"] == mine["order_no"]
    assert _list(brazos, dana, "system_admin").data["count"] == 1


def test_us_wrk_004_tc2_the_new_connects_segments_still_refuse_on_oq_371(dana, brazos):
    """US-WRK-004 TC-2 (negative): `Work-001`'s four segments are exactly as
    they were — a named refusal, and this wave changed nothing about it."""
    from apps.metering import connection_reads

    with tenant_ctx(brazos):
        with pytest.raises(NotImplementedError) as refused:
            connection_reads.list_connections(segment="waiting")
        assert str(refused.value) == "OQ-371"
        assert connection_reads.list_connections(segment="all")["rows"] == []


def test_us_wrk_004_an_unknown_premises_is_absent_not_forbidden(dana, brazos):
    import uuid

    with tenant_ctx(brazos):
        with pytest.raises(errors.NotFoundError):
            work_services.raise_work_order(
                dana, {"type": "Leak investigation", "premises_id": str(uuid.uuid4())}
            )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-WRK-004@87b94265 · US-WRK-001@87b94265 (EP-WRK-01) · 07-endpoints.md §1 · A4
# generated: 2026-09-03 by the CR-070 wave A build lane
# checklist: A✔ B✔ C✔ D✔ E✔(OrdersPage.tsx) F✔ G✔ H=n/a
# gates: RED PROVED FIRST — with `state__in=OPEN_WORK_ORDER_STATES` removed from the seam, the completed order appears and `the_list_holds_every_open_order…` fails on `count == 4`; quoted in the lane report
# exceptions: US-WRK-004 TC-1, TC-3, TC-4 and TC-6 are screen assertions and live in the frontend suites (WorkShell.test.tsx · OrdersPage.test.tsx · sidebarReachability.test.tsx)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
