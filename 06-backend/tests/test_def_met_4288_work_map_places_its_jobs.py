# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-MET-4288 — every work order on `WRK-09` read *not on the map*,
#          because the estate the jobs stand on was never given coordinates.
#          Reported by the Product Owner from the deployed build `v2.208.1`:
#          *"map is Work is not orking at all"* — an empty box over
#          *"NOT ON THE MAP · 19 JOBS"*.
# Rules:   CLAUDE.md hard rule 8 / `BR-MET-1161` (a coordinate is the PREMISES'
#          and is reached by walking to it — a work order declares no `lat`) ·
#          `BR-WRK-002` (coordinates come through the seam) · hard-won law 7
#          (a check that reports a number over a scope it silently excludes)
# Tests:   this file
# Impacts: apps/metering/sample_data.py (STREET_GEO · fixture_addresses ·
#          premises_geo_report · where apply_premises_geo is CALLED) ·
#          apps/work/dispatch.py map_pins (unchanged — it was already right)
# ───────────────────────────────────────────────────────
"""THE WORK MAP HAD NO PINS, AND THE CODE THAT DREW IT WAS CORRECT.

**Both halves of this defect are about the FIXTURE, and neither is about the
map.** `dispatch.map_pins` walks `connection → premises` exactly as hard rule 8
requires and returns every order it cannot place WITH ITS REASON rather than
dropping it — so the screen was telling the truth about data that could not be
drawn, which is why nothing anywhere read as broken.

The two independent causes, either of which alone keeps the map empty:

1. **THE ADDRESS FILTER WAS AN ALLOW-LIST OF ONE ESTATE.**
   `apply_premises_geo()` filtered `address_line__in premises_plan()` — the 44
   §2 premises — and the eight addresses every seeded WORK ORDER stands on come
   from `cr030_premises_plan()`. They were excluded by construction and in
   silence, and their streets had no anchor in `STREET_GEO` either.
2. **IT RAN BEFORE THOSE ROWS EXISTED.** The call sat beside
   `_ensure_cycle_and_route`, which is *before* `_seed_cr030_estate` and the
   `_seed_w6_*` blocks. So even with the filter widened, a fill pass at that
   point could not have seen a single one of them.

⚠ **WHY THE FIRST TEST BELOW HAS NO DATABASE IN IT.** The cheapest guard against
this recurring is the one that asks the fixture whether it can place every
address it invents — no tenant, no migrations, no seed. The next estate that
arrives on a new street fails this in under a second instead of shipping a blank
map to a Product Owner.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from apps.metering import connections as w6
from apps.metering import models as met_models
from apps.metering import sample_data as metering_sample
from apps.work import dispatch
from apps.work import services as work_services
from core import sample_fixture as fixture
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin
from tests.test_us_met_helpers import tenant_ctx


# ══════════════════════════════════════════════════════════════════════════
# The pure half — the fixture can place every address it invents
# ══════════════════════════════════════════════════════════════════════════


def test_def_met_4288_every_address_this_fixture_invents_has_a_street_anchor():
    """The guard that would have caught it, and it needs no database.

    ⚠ It NAMES the addresses it cannot place rather than counting the ones it
    can, because a count of what was filled is indistinguishable from a complete
    job (hard-won law 7). Every seed run printed a healthy number over three
    estates it was never looking at.
    """
    unplaceable = sorted(
        {
            address
            for address in metering_sample.fixture_addresses()
            if metering_sample._coords_for(address) is None
        }
    )
    assert unplaceable == [], (
        "these sample addresses stand on a street with no line in STREET_GEO, "
        "so their premises get no coordinates and every work order, asset and "
        "map pin on them silently has nowhere to be drawn"
    )


def test_def_met_4288_all_four_estates_are_in_the_address_set_not_just_the_first():
    """`premises_plan()` was 44 of 79 addresses and the fill pass saw only those.

    The three that were missing are where every seeded WORK ORDER stands.
    """
    covered = set(metering_sample.fixture_addresses())
    plan = {entry["address_line"] for entry in fixture.premises_plan()}
    estate = {entry["address_line"] for entry in fixture.cr030_premises_plan()}
    seats = {
        entry["address_line"]
        for entry in (*metering_sample.W6_SEATS, *metering_sample.W7_SEATS)
    }
    assert plan <= covered
    assert estate <= covered, "the estate the CR-030 accounts stand on"
    assert seats <= covered, "the new-connection and move seats the jobs stand on"
    assert len(estate) == 8
    assert len(seats) >= 20


def test_def_met_4288_a_suffix_that_is_also_a_street_resolves_to_the_longer_one():
    """`14 Willow Bend` and `103 Willow Bend Dr` are two different places.

    The lookup is a suffix match over a table two estates write into, so the
    longest anchor has to win or the answer depends on typing order — a coin
    toss that reads exactly like a correct lookup.
    """
    short = metering_sample._coords_for("14 Willow Bend")
    long = metering_sample._coords_for("103 Willow Bend Dr")
    assert short is not None and long is not None
    assert short[0] != long[0] or short[1] != long[1]


def test_def_met_4288_the_geo_pass_runs_after_the_last_block_that_plants_a_premises():
    """Cause 2, and a source check is the only thing that can see it.

    Widening the address filter fixes nothing while the pass runs before the
    rows exist — the two causes are independent and a fix for either alone
    leaves the map exactly as empty.
    """
    import inspect

    body = inspect.getsource(metering_sample.seed_sample_records)
    fill = body.index("apply_premises_geo()")
    for planted in ("_seed_cr030_estate(", "_seed_w6_w7_seats(", "_seed_w6_connections("):
        assert body.index(planted) < fill, (
            f"{planted} plants premises AFTER the coordinates are filled, so "
            "those rows keep lat/lng NULL and nothing on any map can draw them"
        )


def test_def_met_4288_every_anchor_sits_in_the_one_austin_box():
    """One `fitBounds` has to frame the whole demo estate, so a stray anchor
    would zoom the map out over an ocean and read as *no pins*."""
    for street, (lat, lng) in metering_sample.STREET_GEO.items():
        assert Decimal("30.15") < Decimal(lat) < Decimal("30.35"), street
        assert Decimal("-97.85") < Decimal(lng) < Decimal("-97.60"), street


# ══════════════════════════════════════════════════════════════════════════
# The database half — a job at an estate address lands ON the map
# ══════════════════════════════════════════════════════════════════════════


ESTATE_ADDRESS = "1408 Elm Street"
#: A network job at a corner — no premises, and nobody can fix that. It stays in
#: the strip forever and it is the reason the strip exists.
NOWHERE = "Elm St & 3rd"


def _sample_premises(actor, address):
    """A premises the SAMPLE SEEDER planted — `BR-TEN-057`'s tag, set the way
    `sample_data._tag` sets it, because `create_premises` takes no such field
    and the fill pass selects on exactly this."""
    created = make_premises(  # noqa: F405
        actor, address_line=address, services_available=["water"]
    )
    met_models.Premises.objects.filter(pk=created["id"]).update(is_sample=True)
    return created


def _job(actor, address):
    work_services.seed_reference_list("work_priorities", [], "test")
    work_services.seed_reference_list("work_order_types", [], "test")
    premises = _sample_premises(actor, address)
    return w6.create_work_order(
        actor,
        None,
        {"type": "Leak investigation", "service": "water", "premises_id": premises["id"]},
    )


@pytest.mark.django_db
def test_def_met_4288_an_estate_address_gains_coordinates(brazos, dana):
    """`1408 Elm Street` is the address every account screenshot uses and the
    seat `CON-26-0110` stands on. It had no coordinate for eleven days."""
    with tenant_ctx(brazos):
        created = _sample_premises(dana, ESTATE_ADDRESS)
        assert metering_sample.apply_premises_geo() == 1
        row = met_models.Premises.objects.get(pk=created["id"])
        assert row.lat is not None and row.lng is not None
        assert Decimal("30.15") < row.lat < Decimal("30.35")
        assert Decimal("-97.85") < row.lng < Decimal("-97.60")
        # Idempotent — a replay writes nothing and an operator's pin survives.
        assert metering_sample.apply_premises_geo() == 0


@pytest.mark.django_db
def test_def_met_4288_a_real_premises_is_never_given_a_fictional_pin(brazos, dana):
    """⚠ **`is_sample` IS THE FENCE, AND IT IS LOAD-BEARING.**

    The fill pass stopped filtering by address so that the next estate is
    covered without an edit — which means the only thing keeping an Austin
    fixture coordinate off a REAL utility's address is this flag. A premises a
    clerk typed is geocoded by `manage.py geocode_premises`, which asks the US
    Census Bureau; a made-up pin on it would put a crew in the wrong street.
    """
    with tenant_ctx(brazos):
        # Deliberately ON an anchored street, so only the flag can refuse it.
        real = make_premises(dana, address_line="9 Main St")  # noqa: F405
        assert met_models.Premises.objects.get(pk=real["id"]).is_sample is False
        assert metering_sample.apply_premises_geo() == 0
        assert met_models.Premises.objects.get(pk=real["id"]).lat is None


@pytest.mark.django_db
def test_def_met_4288_the_report_names_what_it_could_not_place(brazos, dana):
    """Law 7 — a check that cannot cover its whole subject prints what it
    skipped beside what it checked."""
    with tenant_ctx(brazos):
        _sample_premises(dana, "4 Nowhere Particular")
        _sample_premises(dana, ESTATE_ADDRESS)
        before = metering_sample.premises_geo_report()
        assert before["without_coordinates"] == 2
        assert before["unanchored"] == ["4 Nowhere Particular"]
        assert before["unplaceable_addresses"] == []

        assert metering_sample.apply_premises_geo() == 1
        after = metering_sample.premises_geo_report()
        assert after["without_coordinates"] == 1
        assert after["unanchored"] == ["4 Nowhere Particular"]


@pytest.mark.django_db
def test_def_met_4288_a_job_at_an_estate_address_is_a_pin_and_not_a_strip_row(brazos, dana):
    """The whole defect, in one assertion pair.

    ⚠ **THE ORDER CARRIES NO COORDINATE AND NEVER WILL** — hard rule 8. It is a
    pin because the PREMISES it walks to has one, which is why fixing the
    fixture fixes the map with no change to `apps/work` at all.
    """
    with tenant_ctx(brazos):
        order = _job(dana, ESTATE_ADDRESS)

        before = dispatch.map_pins()
        assert before["pins"] == []
        assert [one["order_no"] for one in before["unplaced"]] == [order["order_no"]]
        assert before["unplaced"][0]["reason"] == "premises_not_geocoded"

        metering_sample.apply_premises_geo()

        after = dispatch.map_pins()
        assert [one["order_no"] for one in after["pins"]] == [order["order_no"]]
        assert after["unplaced"] == []
        pin = after["pins"][0]
        assert isinstance(pin["lat"], float) and isinstance(pin["lng"], float)
        assert pin["address"] == ESTATE_ADDRESS
        assert after["total"] == 1


@pytest.mark.django_db
def test_def_met_4288_a_job_with_no_premises_stays_named_in_the_strip(brazos, dana):
    """The strip is not a bug list and must not empty itself.

    A network job at a corner has no place and nobody can give it one; the map
    that silently dropped it would be lying about the day. `no_premises` is a
    different fact from `premises_not_geocoded` and only the second is fixable.
    """
    with tenant_ctx(brazos):
        work_services.seed_reference_list("work_priorities", [], "test")
        work_services.seed_reference_list("work_order_types", [], "test")
        # Anchored on a SPARE METER in inventory (`BR-WRK-006` needs one of the
        # four anchors and this is the cheapest that reaches no premises).
        spare = make_asset(dana)  # noqa: F405
        order = w6.create_work_order(
            dana,
            None,
            {"type": "Bench test", "service": "electric", "asset_id": spare["id"]},
        )
        metering_sample.apply_premises_geo()
        answer = dispatch.map_pins()
        assert answer["pins"] == []
        row = next(one for one in answer["unplaced"] if one["order_no"] == order["order_no"])
        assert row["reason"] == "no_premises"
        assert row["address"] is None


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-MET-4288 (PO report 2026-09-06) + CLAUDE.md hard rule 8 verbatim
# generated: 2026-09-06 by the CR-075 map lane
# checklist: A✔ B=n/a C✔ D=n/a E=n/a F✔ G✔ H=n/a
# gates: pytest tests/test_def_met_4288_work_map_places_its_jobs.py
# exceptions: the ordering guard reads SOURCE, and it is the only thing that can see cause 2 — a behaviour test cannot distinguish "filtered out" from "did not exist yet"
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
