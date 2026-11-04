# ── Trace ──────────────────────────────────────────────
# Story:    US-MET-002 (S15 units)   Change: CR-089 wave J (`PUJ-46`, `PUJ-55`)
# Rules:    BR-MET-095 (a unit MAY move, and the move is a DATED EVENT) ·
#           BR-MET-1161 (an address lives on `premises` and every other entity
#           walks to it) · BR-MET-1162 (a unit may carry its own point) ·
#           BR-MET-082 clause 2 (grouping a premises groups every unit in it)
# Defects:  DEF-511 (nothing counts bills for a single unit)
# ───────────────────────────────────────────────────────
"""`GET /units/{id}/move-preview` — the seven consequences, before the press.

**THE ONE TEST THAT MATTERS HERE IS THE PREDICTION TEST.** The screen's whole
claim is *"after this move the meter will be read by RT-DYN3S and billed on
CY-DYN3"*, and the only honest way to check a prediction is to make it, then
perform the move, then read what actually happened. `test_the_route_it_predicts
_is_the_route_the_move_produces` does exactly that — it would go red if
`routes_if_moved` and `routes_for_unit` ever drifted apart, which is the one
failure a preview can have that nobody would otherwise notice.
"""

import pytest

from apps.metering import derivation, move_preview, seams, services

from tests import cr029_dynamism_fixtures as dyn
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db


def _routed_pair(actor, tenant, suffix):
    """Two buildings on two different water routes, and a unit on the first.

    The shape is `cr029_dynamism_fixtures.unit_moved_between_premises` STOPPED
    ONE STEP EARLIER — that fixture performs the move, and a preview has to be
    read before it.
    """
    north = dyn.make_area(tenant, f"N-{suffix}", "North")
    south = dyn.make_area(tenant, f"S-{suffix}", "South")
    cycle_n = dyn.active_cycle(actor, f"CY-N-{suffix}")
    cycle_s = dyn.active_cycle(actor, f"CY-S-{suffix}")
    north_route = dyn.active_route(
        actor,
        code=f"RT-N-{suffix}",
        name="North water walk",
        area=north,
        service_code="water",
        cycle=cycle_n,
    )
    south_route = dyn.active_route(
        actor,
        code=f"RT-S-{suffix}",
        name="South water walk",
        area=south,
        service_code="water",
        cycle=cycle_s,
    )
    source = dyn.make_premises(actor, f"2200 Riverbend Ct #{suffix}", area_code=north.code)
    target = dyn.make_premises(actor, f"77 Gulf Fwy #{suffix}", area_code=south.code)
    unit = dyn.make_unit(actor, source["id"], label="Unit A")
    services.ensure_service_point(unit["id"], "water")
    services.update_route(actor, north_route.id, {"unit_ids": [unit["id"]]})
    return {
        "unit": unit,
        "source": source,
        "target": target,
        "north_route": north_route,
        "south_route": south_route,
        "north_cycle": cycle_n,
        "south_cycle": cycle_s,
    }


def test_the_route_it_predicts_is_the_route_the_move_produces(brazos, dana):
    """`PUJ-46` — *"Route 12 · Cycle 3 → Route 4 · Cycle 1"*, and it is true.

    ⚠ **A PREVIEW IS ONLY WORTH ANYTHING IF IT AGREES WITH WHAT HAPPENS.** So
    this asserts the prediction, then performs the move, then asserts the
    product's own answer is the same one. It is the only assertion in this file
    that could catch `routes_if_moved` drifting away from `routes_for_unit`.
    """
    with tenant_ctx(brazos):
        world = _routed_pair(dana, brazos, "P1")
        unit_id = world["unit"]["id"]

        preview = move_preview.move_preview(unit_id, world["target"]["id"])
        water = [row for row in preview["routes"] if row["service_code"] == "water"]
        assert len(water) == 1
        predicted = water[0]
        assert predicted["from"]["route_code"] == world["north_route"].code
        assert predicted["from"]["cycle_code"] == world["north_cycle"].code
        assert predicted["to"]["route_code"] == world["south_route"].code
        assert predicted["to"]["cycle_code"] == world["south_cycle"].code
        assert predicted["changes"] is True

        services.move_unit(
            dana,
            unit_id,
            {
                "premises_id": world["target"]["id"],
                # The tenant's own business date (BR-TEN-043) — a
                # literal here is refused as a FUTURE move the day the
                # fixture clock falls behind it.
                "effective_date": str(seams.tenant_today()),
                "reason": "CR-089 wave J — the preview said this would happen.",
            },
        )

        after = derivation.routes_for_unit(unit_id)["water"]

    assert after.route_code == predicted["to"]["route_code"]
    assert after.cycle_code == predicted["to"]["cycle_code"]


def test_without_a_destination_the_preview_states_only_the_from_side(brazos, dana):
    """The screen opens before a destination is chosen and still has something
    true to say — what this unit carries today."""
    with tenant_ctx(brazos):
        world = _routed_pair(dana, brazos, "P2")
        preview = move_preview.move_preview(world["unit"]["id"])

    assert preview["to"] is None
    assert preview["from"]["address_line"] == world["source"]["address_line"]
    water = [row for row in preview["routes"] if row["service_code"] == "water"][0]
    assert water["from"]["route_code"] == world["north_route"].code
    # ⚠ NOT `False`-BY-DEFAULT AND NOT `True`: with no destination there is
    # nothing to compare, and `changes` says so by being false rather than by
    # claiming the route survives a move nobody has described yet.
    assert water["to"] is None
    assert water["changes"] is False


def test_the_asset_count_is_what_changes_address(brazos, dana, monkeypatch):
    """`PUJ-46`'s furthest-reaching line: the assets travel and re-address.

    The count is the assets module's own answer, read through the declared seam
    — this module never counts them itself, so the seam is what is stubbed.
    """
    with tenant_ctx(brazos):
        world = _routed_pair(dana, brazos, "P3")
        monkeypatch.setattr(
            seams, "assets_on_unit", lambda unit_id: [{"id": "a"}, {"id": "b"}, {"id": "c"}]
        )
        preview = move_preview.move_preview(world["unit"]["id"], world["target"]["id"])

    assert preview["assets"]["count"] == 3


def test_bill_count_appears_the_day_billing_answers(brazos, dana, monkeypatch):
    """`PUJ-55` / `DEF-511` — THE HOLD, AND THE TEST THAT FIRES WHEN IT EXPIRES.

    ⚠ **THIS IS HARD-WON LAW 2's SECOND HALF WRITTEN DOWN AS CODE.** The screen
    states an absence — *"nothing counts bills for a single unit yet"* — and a
    stated absence rots the moment somebody publishes the fact. So this asserts
    BOTH halves in one place:

      * with `apps.billing.selectors.issued_bill_count_for_unit` absent, the
        preview answers `None` — *nobody could count them*, which the screen
        prints as a stated absence and NEVER as a zero (`DEF-1813`'s asymmetry,
        `DEF-127`'s third state);
      * the moment that ONE function exists, the number is served, with no
        change to this module and none to the client.

    A lane publishing the billing selector and not seeing this file go from one
    branch to the other has published half a feature.
    """
    with tenant_ctx(brazos):
        world = _routed_pair(dana, brazos, "P4")
        unit_id = world["unit"]["id"]

        # HALF ONE — today. `None`, and it is not 0.
        silent = move_preview.move_preview(unit_id)
        assert silent["bills"]["count"] is None

        # HALF TWO — the day billing publishes the contract the seam declares.
        monkeypatch.setattr(seams, "issued_bill_count_for_unit", lambda _unit: 14)
        answered = move_preview.move_preview(unit_id)

    assert answered["bills"]["count"] == 14


def test_a_unit_with_its_own_point_keeps_it_and_says_so(brazos, dana):
    """`BR-MET-1162` — the pin moves only for a unit reading its building's."""
    from apps.metering import models

    with tenant_ctx(brazos):
        world = _routed_pair(dana, brazos, "P5")
        unit_id = world["unit"]["id"]

        borrowed = move_preview.move_preview(unit_id, world["target"]["id"])
        models.Unit.objects.filter(pk=unit_id).update(lat="30.752104", lng="-98.238391")
        owned = move_preview.move_preview(unit_id, world["target"]["id"])

    assert borrowed["point"]["moves"] is True
    assert owned["point"]["source"] == "unit"
    assert owned["point"]["moves"] is False


def test_an_unknown_destination_is_a_refusal_not_a_preview_of_absences(brazos, dana):
    """A 404 on either id, before any figure is assembled — a preview that
    answered *no assets, no accounts, no route* for a premises that does not
    exist would be making three claims and none of them checked."""
    from core import errors

    with tenant_ctx(brazos):
        world = _routed_pair(dana, brazos, "P6")
        with pytest.raises(errors.NotFoundError):
            move_preview.move_preview(world["unit"]["id"], "00000000-0000-0000-0000-000000000000")
        with pytest.raises(errors.NotFoundError):
            move_preview.move_preview("00000000-0000-0000-0000-000000000000")


def test_the_override_changes_nothing_for_every_other_caller(brazos, dana):
    """`Resolution`'s new keyword is optional, and *optional* has to be proved.

    `units_in_cycle`, `members_of_route` and `route_for_unit` all build a
    `Resolution` with no override; this asserts the answer is identical to the
    one the same call gives when the override map is empty, so a future edit
    that made the override unconditional goes red here rather than in a bill
    run's scope.
    """
    with tenant_ctx(brazos):
        world = _routed_pair(dana, brazos, "P7")
        unit_id = world["unit"]["id"]
        plain = derivation.Resolution([unit_id]).routes_of(unit_id)
        empty = derivation.Resolution([unit_id], premises_override={}).routes_of(unit_id)
        moved = derivation.routes_if_moved(unit_id, world["target"]["id"])

    assert {code: row.route_code for code, row in plain.items()} == {
        code: row.route_code for code, row in empty.items()
    }
    assert plain["water"].route_code == world["north_route"].code
    # …and it is not a no-op either: through the one public door, the same unit
    # resolves to the DESTINATION's route. Both halves matter — an override that
    # changed nothing would make the preview a lie, and one that changed
    # something without being asked would move a bill run's scope.
    assert moved["water"].route_code == world["south_route"].code
