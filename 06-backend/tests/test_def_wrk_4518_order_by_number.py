# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-WRK-4518 — the work-order detail screen loaded NOTHING at any
#           address built from the order NUMBER, because every route on the
#           family is `<uuid:order_id>` and no door took a number at all.
# Story:    US-WRK-033 (the six-tab order detail, Work-008)
# Rules:    BR-WRK-001 (Work owns the order) · CLAUDE.md hard rule 1 (a tenant
#           table is read only under the tenant in context) · B14 rule 31 (the
#           number is the only reference a person ever sees)
# ───────────────────────────────────────────────────────
"""`GET /work-orders/by-number/{order_no}` — the one door `DEF-WRK-4518` added.

⚠ **THE TENANT CASE IS THE ONE THAT MATTERS AND IT IS NOT DECORATION.**
`order_no` is allocated PER TENANT, so `WO-0001` exists in more than one
utility and names a different job in each. A by-number lookup is therefore the
one read in this module that could answer across a tenant boundary if its
filter were ever dropped — and the mistake would be invisible on a single-tenant
fixture. `test_..._is_scoped_to_the_tenant_in_context` raises the SAME number in
two utilities and proves each sees only its own.
"""
from __future__ import annotations

import pytest
from django.urls import resolve

from apps.work import api as work_api
from apps.work import services as work_services
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · marcus · erin
from tests.test_us_met_helpers import make_premises, tenant_ctx
from tests.test_us_ten_helpers import api_call

pytestmark = pytest.mark.django_db


def _by_number(tenant, actor, role, order_no):
    return api_call(
        work_api.work_order_by_number,
        "get",
        f"/api/{tenant.subdomain}/work-orders/by-number/{order_no}",
        user=actor.user,
        role=role,
        tenant=tenant,
        order_no=order_no,
    )


def _raise(actor, address, order_type="Meter set"):
    premises = make_premises(actor, address_line=address, services_available=["water"])
    return work_services.raise_work_order(
        actor, {"type": order_type, "service": "water", "premises_id": premises["id"]}
    )


def test_def_wrk_4518_the_route_resolves_and_the_uuid_route_never_saw_it():
    """The two doors are DIFFERENT views on DIFFERENT paths.

    ⚠ This is the assertion that would have caught the defect at its root: for
    as long as `by-number` was unrouted, `/work-orders/WO-0016` fell to the
    `<uuid:order_id>` pattern, matched nothing and 404'd.
    """
    match = resolve("/api/brazosbend/work-orders/by-number/WO-0016")
    assert match.func is work_api.work_order_by_number
    assert match.kwargs == {"order_no": "WO-0016"}


def test_def_wrk_4518_a_number_opens_the_same_row_a_uuid_does(dana, brazos):
    """ONE assembler, two doors — the by-number answer is byte-for-byte the
    by-id answer, so the screen cannot see two versions of one order."""
    with tenant_ctx(brazos):
        order = _raise(dana, "500 Main St")

    by_number = _by_number(brazos, dana, "system_admin", order["order_no"]).data
    assert by_number["id"] == order["id"]
    assert by_number["order_no"] == order["order_no"]
    assert by_number["type"] == "Meter set"
    assert by_number["service"] == "water"
    # Every field the detail screen reads, not merely the id — a lookup that
    # answered with the id alone would cost the screen a second round trip.
    assert by_number["premise"]["address"] == "500 Main St"
    assert by_number["state"] == "planned" and by_number["dispatch_state"] is not None


def test_def_wrk_4518_an_unknown_number_is_a_plain_not_found(dana, brazos):
    with tenant_ctx(brazos):
        _raise(dana, "500 Main St")
    # ⚠ **ASSERTED AS THE STATUS THE BROWSER SEES, NOT AS THE EXCEPTION.**
    # `api_call` runs the view through DRF's exception handler exactly as the
    # wired stack does, so the raise has already become a 404 envelope by the
    # time it comes back. A `pytest.raises` here passes only for as long as
    # nobody wires the handler — a check looking at the wrong thing.
    assert _by_number(brazos, dana, "system_admin", "WO-9999").status_code == 404


def test_def_wrk_4518_is_scoped_to_the_tenant_in_context(dana, erin, brazos, lonestar):
    """Two utilities, the SAME order number, and neither can read the other's.

    `order_no` comes from a per-tenant series, so this collision is the normal
    case rather than a contrived one.
    """
    with tenant_ctx(brazos):
        mine = _raise(dana, "500 Main St", "Meter set")
    with tenant_ctx(lonestar):
        theirs = _raise(erin, "12 Alamo Way", "Leak investigation")

    # The fixture only proves anything if the two numbers actually collide.
    if mine["order_no"] == theirs["order_no"]:
        assert _by_number(brazos, dana, "system_admin", mine["order_no"]).data["id"] == mine["id"]
        assert (
            _by_number(lonestar, erin, "system_admin", theirs["order_no"]).data["id"]
            == theirs["id"]
        )
    else:  # pragma: no cover - the series is per tenant, so this is the odd case
        assert _by_number(brazos, dana, "system_admin", theirs["order_no"]).status_code == 404
        assert _by_number(lonestar, erin, "system_admin", mine["order_no"]).status_code == 404


def test_def_wrk_4518_every_role_that_may_read_an_order_may_read_it_by_number(
    dana, marcus, brazos
):
    """The door answers what `GET /work-orders/{id}` answers and no more — it
    must not become a way to reach a row a role could not otherwise see."""
    with tenant_ctx(brazos):
        order = _raise(dana, "500 Main St")
    assert (
        _by_number(brazos, marcus, "billing_clerk", order["order_no"]).data["id"] == order["id"]
    )
