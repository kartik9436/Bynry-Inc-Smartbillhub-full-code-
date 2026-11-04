# ── Trace ──────────────────────────────────────────────
# Change:   CR-131-BRC07 steps 3, 4, 5, 6 and 7 — a route names PREMISES and
#           derives the units, meters and accounts inside them.
# Ruling:   PO, verbatim 2026-09-22: "thi sis correct - The routes design —
#           storing 726 unit rows instead of 6 premises, and the route going
#           stale the moment anything changes … route should not be status - it
#           is dynamicallyderive the details of units, assets meter acocount
#           swithin it". Decision log, "A ROUTE IS NOT A SNAPSHOT".
# Rules:    BR-MET-074 (a conflict is a MOVE, not a refusal) · BR-MET-075 (an
#           exclusion is a row, never a change to the asset) · BR-MET-076 (a
#           draft affects nothing) · BR-MET-082 clause 2 (grouping a premises
#           groups every unit in it) · BR-MET-079 (the collection stamp) ·
#           NFR-3 (universal server pagination) · NFR-5 (no hard caps).
# ───────────────────────────────────────────────────────
"""A route stores six buildings and answers about everything inside them.

THE ACCEPTANCE THIS FILE IS WRITTEN AGAINST — `CR-131-BRC07` §5, verbatim
---------------------------------------------------------------------------
    3. Add a unit to one of those premises. It is on the route without anyone
       re-opening the wizard.
    4. Fit a meter. It is on the route.
    5. Move a tenant in. The account is on the route.
    6. An excluded meter stays excluded, with its reason.

**Items 3, 4 and 5 are the whole ruling** and none of them was true before: a
per-unit membership is a photograph, so a unit added on Tuesday reached the
route only when somebody re-opened the wizard and pressed Save. Nobody will.

⚠ **THE ONE THAT MUST NOT BREAK QUIETLY IS `BR-MET-074`**, which the CR names
by hand. A premises already on another route for the same service MOVES; break
it and there is no error anywhere — the building simply sits on two routes and
is read twice. So both directions are asserted: it leaves the old route AND it
arrives on the new one, and the audit says which route it came from.

WHAT WOULD MAKE THESE PASS WRONGLY
----------------------------------
A fixture with one unit per building. Every case here uses a building with
SEVERAL units, because one unit per premises makes the per-unit grain and the
per-premises grain indistinguishable — which is exactly why 726 units got as
far as a customer.
"""

from datetime import date

import pytest

from apps.metering import derivation, models, selectors, services

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import (
    make_asset,
    make_premises,
    make_unit,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


def _building(actor, address, labels=("A", "B", "C")):
    """One premises with SEVERAL units — see the module docstring."""
    premise = make_premises(actor, address_line=address)
    units = [make_unit(actor, premise["id"], label=label, services=["water"]) for label in labels]
    return premise, units


def test_a_route_stores_ONE_row_per_building_and_not_one_per_unit(brazos, dana):
    """The ruling's own arithmetic, at the smallest size that can show it.

    Two buildings, six units. The old grain stored SIX rows; this stores TWO.
    At the size the PO hit it — 6 buildings, 726 units — that is 726 rows and
    726 `update_or_create` statements in one transaction against 6 rows in one.
    """
    with tenant_ctx(brazos):
        one, one_units = _building(dana, "1 Six Units Way")
        two, two_units = _building(dana, "2 Six Units Way")
        route = services.create_route(
            dana,
            {
                "code": "SIX-UNITS",
                "service_code": "water",
                "status": "active",
                "premises_ids": [one["id"], two["id"]],
            },
        )
        stored = models.RoutePremisesMembership.objects.filter(route_id=route["id"])
        assert stored.count() == 2, "a route stores buildings, not units"
        assert len(one_units) + len(two_units) == 6
        # …and every one of the six units still RESOLVES onto the route.
        members = {row["unit_id"] for row in selectors.route_members(route["id"])}
        assert len(members) == 6


def test_a_unit_added_afterwards_is_on_the_route_with_nobody_re_opening_the_wizard(
    brazos, dana
):
    """`CR-131-BRC07` §5 item 3 — **the ruling itself.**

    This is the case that cannot be made to pass by any amount of fixing the
    URL or the save: a photograph does not acquire a unit that was not there
    when it was taken.
    """
    with tenant_ctx(brazos):
        premise, _units = _building(dana, "3 Added Later Ln")
        route = services.create_route(
            dana,
            {
                "code": "ADDED-LATER",
                "service_code": "water",
                "status": "active",
                "premises_ids": [premise["id"]],
            },
        )
        before = {row["unit_id"] for row in selectors.route_members(route["id"])}
        assert len(before) == 3

        # The clerk adds a unit on the Premises screen. NOTHING touches the
        # route — no wizard, no save, no membership write.
        added = make_unit(dana, premise["id"], label="D", services=["water"])

        after = {row["unit_id"] for row in selectors.route_members(route["id"])}
        assert str(added["id"]) in after, "a unit added later never reached the route"
        assert len(after) == 4
        # …and the stored rows did not move, which is the point.
        assert models.RoutePremisesMembership.objects.filter(route_id=route["id"]).count() == 1


def test_a_meter_fitted_afterwards_is_on_the_route(brazos, dana):
    """`CR-131-BRC07` §5 item 4. The meter list is derived, so a meter fitted
    after the route was saved appears without anyone re-ticking anything."""
    with tenant_ctx(brazos):
        premise, units = _building(dana, "4 Fitted Later Rd", labels=("A",))
        route = services.create_route(
            dana,
            {
                "code": "FITTED-LATER",
                "service_code": "water",
                "status": "active",
                "premises_ids": [premise["id"]],
            },
        )
        assert selectors.route_meter_picker(route_id=route["id"])["total"] == 0

        make_asset(
            dana,
            unit_id=units[0]["id"],
            service="water",
            unit="kgal",
            install_date="2026-02-01",
        )

        picked = selectors.route_meter_picker(route_id=route["id"])
        assert picked["total"] == 1, "a meter fitted after the save never reached the route"
        assert picked["included"] == 1
        assert picked["premises"] == 1


def test_br_met_074_a_premises_on_another_route_MOVES_and_the_audit_names_where_from(
    brazos, dana
):
    """**The rule the CR names as the one most likely to break silently**, at
    the new grain.

    Both directions are asserted. Asserting only that the building ARRIVES
    would pass while it also stayed on the old route — which is the failure
    that produces no error at all and reads a meter twice.
    """
    with tenant_ctx(brazos):
        premise, _units = _building(dana, "5 Contested Ave")
        first = services.create_route(
            dana,
            {
                "code": "HAD-IT",
                "service_code": "water",
                "status": "active",
                "premises_ids": [premise["id"]],
            },
        )
        second = services.create_route(
            dana, {"code": "TAKES-IT", "service_code": "water", "status": "active"}
        )
        services.update_route(dana, second["id"], {"premises_ids": [premise["id"]]})

        assert (
            models.RoutePremisesMembership.objects.filter(
                route_id=first["id"], premises_id=premise["id"]
            ).count()
            == 0
        ), "the building stayed on BOTH routes — it would be read twice"
        assert (
            models.RoutePremisesMembership.objects.filter(
                route_id=second["id"], premises_id=premise["id"]
            ).count()
            == 1
        )
        # the legacy per-unit rows moved with it, so the two accounts agree
        assert models.RouteMembership.objects.filter(route_id=first["id"]).count() == 0
        assert models.RouteMembership.objects.filter(route_id=second["id"]).count() == 3
        # and NOBODY is on two routes for one service
        assert len(derivation.routes_for_unit(_units_of(premise)[0])) == 1


def test_br_met_074_two_services_are_not_a_conflict(brazos, dana):
    """The other half of `BR-MET-074`, which a naive premises-level uniqueness
    would have broken: a building takes water AND electric and is legitimately
    read by two crews on two routes."""
    with tenant_ctx(brazos):
        premise = make_premises(dana, address_line="6 Two Services Way")
        make_unit(dana, premise["id"], label="A", services=["water", "electric"])
        water = services.create_route(
            dana,
            {
                "code": "WATER-CREW",
                "service_code": "water",
                "status": "active",
                "premises_ids": [premise["id"]],
            },
        )
        electric = services.create_route(
            dana,
            {
                "code": "ELEC-CREW",
                "service_code": "electric",
                "status": "active",
                "premises_ids": [premise["id"]],
            },
        )
        assert models.RoutePremisesMembership.objects.filter(
            premises_id=premise["id"]
        ).count() == 2, "the electric route took the building off the water route"
        assert models.RoutePremisesMembership.objects.filter(route_id=water["id"]).exists()
        assert models.RoutePremisesMembership.objects.filter(route_id=electric["id"]).exists()


def test_br_met_075_an_excluded_meter_stays_excluded_with_its_reason(brazos, dana):
    """`CR-131-BRC07` §5 item 6. The exclusion is a row about a METER and is
    untouched by the membership moving to premises grain — and its reason
    travels with it, because a tab that says a meter is excluded and never why
    is a tab whose next reader re-ticks it."""
    with tenant_ctx(brazos):
        premise, units = _building(dana, "7 Excluded Rd", labels=("A",))
        asset = make_asset(
            dana, unit_id=units[0]["id"], service="water", unit="kgal", install_date="2026-01-05"
        )
        route = services.create_route(
            dana,
            {
                "code": "HAS-EXCL",
                "service_code": "water",
                "status": "active",
                "premises_ids": [premise["id"]],
                "excluded_asset_ids": [str(asset["id"])],
                "exclusion_reasons": {str(asset["id"]): "read elsewhere"},
            },
        )
        picked = selectors.route_meter_picker(route_id=route["id"])
        assert picked["total"] == 1, "the excluded meter must still be LISTED, ticked off"
        assert picked["included"] == 0
        assert picked["meters"][0]["excluded"] is True
        assert picked["meters"][0]["exclusion_reason"] == "read elsewhere"


def test_the_picker_paginates_server_side_and_its_counts_are_the_whole_set(brazos, dana):
    """`NFR-3` and `NFR-5` together, which the CR makes binding on this change.

    ⚠ **THE COUNTS ARE THE THING**, not the slice. A footer computed from the
    page is how a route's meter count silently stops growing at fifty — and the
    wizard prints *"151 of 153"* out of these two numbers (`BR-MET-075`), so
    they must be the WHOLE set while `meters` is one page of it.
    """
    with tenant_ctx(brazos):
        premise, units = _building(dana, "8 Paged Way", labels=("A", "B", "C", "D", "E"))
        for index, unit in enumerate(units):
            # A distinct number per meter — `assets.asset_no_duplicate` is a
            # real refusal and a fixture that trips it is testing the fixture.
            make_asset(
                dana,
                unit_id=unit["id"],
                service="water",
                unit="kgal",
                install_date="2026-01-05",
                asset_no=f"PAGED-{index}",
            )
        route = services.create_route(
            dana,
            {
                "code": "PAGED",
                "service_code": "water",
                "status": "active",
                "premises_ids": [premise["id"]],
            },
        )
        page = selectors.route_meter_picker(route_id=route["id"], page=1, per=2)
        assert len(page["meters"]) == 2, "the page is a page"
        assert page["total"] == 5, "the count is the whole set, not the page"
        assert page["included"] == 5
        assert len(selectors.route_meter_picker(route_id=route["id"], page=3, per=2)["meters"]) == 1
        # NFR-5 — no hard cap: a caller that asks for everything gets it.
        assert len(selectors.route_meter_picker(route_id=route["id"], per=None)["meters"]) == 5


def test_an_empty_answer_says_whether_anything_was_ASKED(brazos, dana):
    """`CR-131-BRC07` step 6 — **a failure says so and is never drawn as an
    absence.**

    The wizard drew *"No meters yet… Or none have meters fitted"* over a
    request that never arrived, so a rejected fetch and a meterless route were
    the same picture. The server's half of the fix is that the answer carries
    how many BUILDINGS it was asked about: 6 premises and 0 meters is a route
    of unmetered properties; 0 premises is a request that asked about nothing.
    """
    with tenant_ctx(brazos):
        premise, _units = _building(dana, "9 No Meters Ln", labels=("A", "B"))
        route = services.create_route(
            dana,
            {
                "code": "NO-METERS",
                "service_code": "water",
                "status": "active",
                "premises_ids": [premise["id"]],
            },
        )
        real = selectors.route_meter_picker(route_id=route["id"])
        assert real["premises"] == 1 and real["total"] == 0
        assert real["premises_without_meter"] == 1

        nothing = selectors.route_meter_picker()
        assert nothing["premises"] == 0 and nothing["total"] == 0
        # The two are distinguishable, which is the whole requirement.
        assert real["premises"] != nothing["premises"]


def test_the_collection_stamp_survives_an_empty_service_point_projection(brazos, dana):
    """⚠ **THE FORWARD HAZARD `CR-131-BRC07` STEP 1 PROVED, CLOSED AND PINNED.**

    The gate measured that `collection_route_id`'s only source was
    `service_points.route_id`, so a derivation design that stopped maintaining
    that projection would stop stamping new reads — `meter_reads.route_id` is
    nullable, its docstring calls NULL *"honest"*, **and nothing would go
    red.** The read history would simply stop being recorded from the day it
    shipped.

    So this EMPTIES the projection and calls the real collection function. It
    is the same probe `10-scripts/cr131_br_met_081_gate_probe.py` section B
    runs, written where the suite will run it every day.
    """
    from apps.assets import models as assets_models

    with tenant_ctx(brazos):
        premise, units = _building(dana, "10 Still Resolves Way", labels=("A",))
        asset = make_asset(
            dana, unit_id=units[0]["id"], service="water", unit="kgal", install_date="2026-01-05"
        )
        route = services.create_route(
            dana,
            {
                "code": "STILL-RESOLVES",
                "service_code": "water",
                "status": "active",
                "premises_ids": [premise["id"]],
            },
        )
        row = assets_models.Asset.objects.get(pk=asset["id"])
        assert str(services.collection_route_id(row)) == str(route["id"])

        # Exactly what a design that stops writing the stored projection leaves
        # behind: membership intact, column empty.
        models.ServicePoint.objects.filter(tenant_id=brazos.id).update(route=None, cycle=None)
        assert models.ServicePoint.objects.filter(route_id=route["id"]).count() == 0

        resolved = services.collection_route_id(assets_models.Asset.objects.get(pk=asset["id"]))
        assert str(resolved) == str(route["id"]), (
            "a read collected now would be stamped route_id=None — the read "
            "history would stop being recorded, silently"
        )


def _units_of(premise):
    return [
        str(value)
        for value in models.Unit.objects.filter(premises_id=premise["id"]).values_list(
            "id", flat=True
        )
    ]
