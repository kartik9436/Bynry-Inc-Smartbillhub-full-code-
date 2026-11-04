# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-233 (the reads-history delete guard is bypassed by moving the
#           premises away first) · DEF-243 (the guard's unit hop was dead code)
# Change:   CR-006 (SET-05 Routes & Cycles)   Screens: SET-05
# Rules:    BR-MET-079 (a route with reads history cannot be DELETED, only
#           deactivated) · BR-MET-008 (the membership lock one layer above) ·
#           BR-MET-074 (a membership conflict MOVES) · BR-MET-033 (membership
#           stamps the service point — the mutable link that caused this)
# ───────────────────────────────────────────────────────
"""DEF-233 — the route stamp, and the guard that now survives a membership move.

**The general prevention this file exists to install**, quoted from the defect
row so a later lane cannot mistake it for an ordinary regression test:

    "any guard that reads a MUTABLE link must have a test that MUTATES that
    link and then asserts the guard still fires"

Every pre-existing test of BR-MET-079 creates the route, stamps it and deletes
it in one breath. Not one of them MOVES the premises first, which is why a
guard that could be defeated by a two-click membership edit had a green suite
over it for a day.
"""

from datetime import date

import pytest

from apps.assets import models as assets_models
from apps.metering import models, services
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import (
    make_asset,
    make_premises,
    make_unit,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


def _premises_with_meter(actor, address, label="A"):
    premise = make_premises(actor, address_line=address)
    unit = make_unit(actor, premise["id"], label=label, services=["water"])
    asset = make_asset(
        actor, unit_id=unit["id"], service="water", unit="kgal", install_date="2026-01-05"
    )
    return premise, unit, asset


def _read_on(tenant, asset_id, route_id, day=date(2026, 7, 1)):
    """A committed read carrying the collection stamp — what `_post_row` now
    writes. Deliberately created with NO import batch, because that is the
    shape every read on the shipped fixture actually has (all 135 of them)."""
    return models.MeterRead.objects.create(
        tenant_id=tenant.id,
        asset_id=asset_id,
        route_id=route_id,
        read_at=day,
        unit="kgal",
        source="manual",
    )


def test_collection_route_id_resolves_from_the_service_point(brazos, dana):
    """The stamp's SOURCE. If this cannot resolve, the stamp is always NULL and
    the guard silently falls back to the sources DEF-233 defeated."""
    with tenant_ctx(brazos):
        premise, _unit, asset = _premises_with_meter(dana, "1 Stamp Way")
        route = services.create_route(
            dana,
            {"code": "STAMP-1", "service_code": "water", "premises_ids": [premise["id"]]},
        )
        resolved = services.collection_route_id(
            assets_models.Asset.objects.get(pk=asset["id"])
        )
        assert str(resolved) == str(route["id"])


def test_guard_survives_a_membership_move(brazos, dana):
    """**THE DEF-233 CASE.** The seeded Route 1 refused deletion naming 135
    reads at 14:00 and was DELETED at 15:00, because the premises had been
    moved to another route in between.

    ⚠ **THE RED PROOF IS INSIDE THIS TEST, DELIBERATELY.** Asserting only that
    the delete refuses would pass again the day someone reintroduces the old
    sources, so the two defeated sources are asserted to be EXACTLY ZERO first.
    The guard therefore has one leg to stand on — the stamp — and if that leg
    is removed this test fails on the refusal rather than passing by accident.
    """
    with tenant_ctx(brazos):
        premise, _unit, asset = _premises_with_meter(dana, "2 Moved Rd")
        route_a = services.create_route(
            dana, {"code": "MOVE-A", "service_code": "water", "premises_ids": [premise["id"]]}
        )
        _read_on(brazos, asset["id"], route_a["id"])

        # BR-MET-074 — putting the same premises on another route MOVES it.
        route_b = services.create_route(
            dana, {"code": "MOVE-B", "service_code": "water", "premises_ids": [premise["id"]]}
        )
        assert str(route_b["id"]) != str(route_a["id"])

        # ── the two sources DEF-233 defeated, each proved dead on this data ──
        assert (
            models.ServicePoint.objects.filter(
                tenant_id=brazos.id, route_id=route_a["id"]
            ).count()
            == 0
        ), "the move unstamped every service point — this is the hole"
        assert (
            models.MeterRead.objects.filter(
                tenant_id=brazos.id, import_batch__route_id=route_a["id"]
            ).count()
            == 0
        ), "no import batch exists — the documented 'durable link' cannot fire"

        # ── and the guard still counts the read, because the READ carries it ──
        assert services.route_read_history_count(route_a["id"]) == 1

        with pytest.raises(errors.BizError) as caught:
            services.delete_route(dana, route_a["id"])
    assert caught.value.message_key == "metering.route.delete_blocked_read_history"
    assert caught.value.params["alternative"] == "deactivate"


def test_the_stamp_is_not_rewritten_when_the_meter_moves_on(brazos, dana):
    """History is about WHERE IT WAS READ, not where the meter lives now.

    ⚠ **THIS TEST'S FIRST EXPECTATION WAS WRONG AND THE CORRECTION IS KEPT,
    because it is the design question the union answers and the next lane will
    ask it too.** It asserted `count(route_b) == 0` immediately after the move
    and got 1. The code is right and the assertion was not: while route B holds
    the meter, the "service points currently stamped" source counts the read —
    the CONSERVATIVE direction this guard deliberately errs in, since an
    under-count deletes a route that has history and an over-count only refuses
    a delete that `deactivate` still serves.

    **And the over-count is harmless precisely there:** while route B has
    members at all, BR-MET-008's membership lock already refuses its deletion,
    so the read-history figure cannot be the thing standing in the way. The
    provenance claim only becomes observable once route B is EMPTIED — which is
    exactly when it matters, and is what this now asserts.
    """
    with tenant_ctx(brazos):
        premise, _unit, asset = _premises_with_meter(dana, "3 Provenance Ave")
        route_a = services.create_route(
            dana, {"code": "PROV-A", "service_code": "water", "premises_ids": [premise["id"]]}
        )
        read = _read_on(brazos, asset["id"], route_a["id"])
        route_b = services.create_route(
            dana, {"code": "PROV-B", "service_code": "water", "premises_ids": [premise["id"]]}
        )
        read.refresh_from_db()
        assert str(read.route_id) == str(route_a["id"]), "the stamp never follows the meter"

        # Empty route B. BR-MET-008 is now satisfied for it, so the read-history
        # figure is the only thing that could refuse — and it must not.
        services.update_route(dana, route_b["id"], {"premises_ids": []})
        assert services.route_read_history_count(route_b["id"]) == 0
        services.delete_route(dana, route_b["id"])

        # Route A was the one actually read, and keeps its history for good.
        assert services.route_read_history_count(route_a["id"]) == 1


def test_a_route_never_read_still_deletes(brazos, dana):
    """The guard must not become "refuses always". A route emptied of members
    with NO read history is still deletable — that is the behaviour
    BR-MET-079 deliberately leaves alone, and an over-eager fix would remove
    the only way to clean up a mistyped route."""
    with tenant_ctx(brazos):
        premise, _unit, _asset = _premises_with_meter(dana, "4 Never Read St")
        route = services.create_route(
            dana, {"code": "CLEAN-1", "service_code": "water", "premises_ids": [premise["id"]]}
        )
        services.update_route(dana, route["id"], {"premises_ids": []})
        assert services.route_read_history_count(route["id"]) == 0
        services.delete_route(dana, route["id"])
        assert not models.Route.objects.filter(tenant_id=brazos.id, id=route["id"]).exists()


def test_def243_assets_unit_is_a_uom_string_not_a_unit_key(brazos, dana):
    """**DEF-243 — why the old guard's second hop could never match.**

    It filtered `asset__unit__in=<metering.Unit uuids>`. `assets.unit` is the
    explicit-UoM TEXT column CLAUDE.md rule 3 requires — `Asset` has no key to
    `metering.units` at all; that hop goes through `AssetAssignment`. So the
    filter compared 'kgal' against a uuid, matched nothing, and reported zero
    WITHOUT ERRORING, which is the only reason it survived review.

    Pinned as a fact about the schema so that reinstating the old filter fails
    here with an explanation rather than silently under-counting again.
    """
    with tenant_ctx(brazos):
        _premise, unit, asset = _premises_with_meter(dana, "5 Uom Ln")
        row = assets_models.Asset.objects.get(pk=asset["id"])
        assert row.unit == "kgal"
        assert isinstance(row.unit, str)
        assert not hasattr(row, "unit_id"), "Asset.unit is a UoM string, never a Unit FK"
        # the real hop, and it does resolve
        assert assets_models.AssetAssignment.objects.filter(
            tenant_id=brazos.id, asset_id=asset["id"], unit_id=unit["id"]
        ).exists()
