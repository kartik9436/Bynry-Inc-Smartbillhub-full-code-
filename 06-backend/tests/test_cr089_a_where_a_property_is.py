"""CR-089 wave A — where a property is, and where a unit is.

⚠ **EVERY CASE HERE WAS PROVED RED BEFORE THE CODE THAT MAKES IT GREEN**, and
the pre-change failure is quoted beside the case that found it — hard-won law 7,
whose first clause is that a guard nobody has watched fail is not a guard.

WHAT THIS FILE IS ABOUT, IN ONE SENTENCE EACH:

  * `BR-MET-1162` (PO 2026-09-08) lets a UNIT carry its own map point, and the
    FALLBACK is part of the rule rather than an implementation detail — a unit
    with none reads its building's, and the answer says WHICH.
  * `PUJ-19` makes a point CORRECTABLE: `update_premises` refused `lat`/`lng`
    by name until this wave, so a property placed on the wrong side of the
    street stayed there for ever.
  * `PUJ-01` puts the sixteen properties with no point behind a filter, on a
    list that had no way to ask the question.
  * `PUJ-10` reads the GIS check as a PAIR, because the flag alone is `false`
    on all 673 properties and drawing that as *Checked* would name a person who
    never looked.

⚠ **AND ONE THING THIS FILE DELIBERATELY DOES NOT DO.** It does not assert that
a unit has no address column — that is `G85`, at merge, over every model in the
product; a test asserting it here would be a second definition of a fence that
already has one, and the weaker of the two.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from apps.metering import models, selectors, services
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import owner_for, tenant_ctx

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _in_tenant(sqlite_guc, brazos):  # noqa: F811 — the star-imported autouse fixture
    """Every case here runs inside the tenant's own context.

    ⚠ **NOT A CONVENIENCE — CLAUDE.md hard rule 1.** `RLS FORCE` is on, so a
    selector called without `app.tenant_id` set does not fail loudly: it
    answers with NOTHING, and a count assertion against an empty result is a
    test that passes for the wrong reason.

    ⚠ **IT NAMES `sqlite_guc` AS AN ARGUMENT AND THAT IS LOAD-BEARING, NOT
    TIDINESS.** Two function-scoped `autouse` fixtures have no guaranteed order
    between them, and `tenant_context` issues a real `set_config(...)` — a
    PostgreSQL function the suite's sqlite has never heard of. Without the
    dependency this fixture won the race and every case here ERRORED at setup
    with `no such function: set_config`, which reads like a broken helper and
    is really a fixture-ordering bug. Naming it makes the order a fact rather
    than a coincidence.
    """
    with tenant_ctx(brazos):
        yield


def _premises(dana, **over):
    """One property, with the owner `BR-MET-401` still requires at CREATE.

    ⚠ **THE OWNER IS SUPPLIED ON PURPOSE AND THAT IS NOT WAVE A's TO CHANGE.**
    CR-089 §2.1 reverses `metering.premises.owner_required` — PO 2026-09-08,
    *"Owner = search ( it should be optional)"* — and that reversal is **wave
    B's `B1`**. Until it lands the server refuses a create with no owner, so a
    fixture here that omitted one would fail on somebody else's rule and read
    like a fault in this wave's code. It was doing exactly that until this line.
    """
    payload = {
        "owner_id": owner_for(dana),
        "address_line": over.pop("address_line", "412 Cypress Row"),
        "city": "Silver Creek",
        "state": "TX",
        "postal_code": "78611",
        **over,
    }
    return services.create_premises(dana, payload)


# ── BR-MET-1162 — a unit's own point, and the ruled fallback ────────────────


def test_a7_a_unit_with_no_point_reads_its_building(brazos, dana):
    """The DEFAULT, and it must stay the default: all 1,109 units are here.

    RED BEFORE: `AttributeError: 'Unit' object has no attribute 'lat'` — the
    column did not exist, and `unit_point` did not either.
    """
    created = _premises(dana, lat="30.752104", lng="-98.238391")
    unit = services.create_unit(
        dana, {"premises_id": created["id"], "label": "1", "unit_type": "residential"}
    )
    row = models.Unit.objects.select_related("premises").get(pk=unit["id"])
    assert selectors.unit_point(row) == {
        "lat": "30.752104",
        "lng": "-98.238391",
        # ⚠ THE SOURCE IS THE HALF THAT MATTERS. Two coordinates alone would
        # make a flat and a cabin read identically, which is the exact thing
        # the ruling's second sentence forbids.
        "source": "premises",
    }


def test_a7_a_unit_with_its_own_point_is_the_truth_for_that_unit(brazos, dana):
    """The cabin. PO: *"where it does, that is the truth for that unit"*."""
    created = _premises(dana, lat="30.752104", lng="-98.238391")
    unit = services.create_unit(
        dana,
        {
            "premises_id": created["id"],
            "label": "Cabin 7",
            "lat": "30.760000",
            "lng": "-98.240000",
        },
    )
    row = models.Unit.objects.select_related("premises").get(pk=unit["id"])
    assert selectors.unit_point(row) == {
        "lat": "30.760000",
        "lng": "-98.240000",
        "source": "unit",
    }
    # And the payload carries BOTH: what this row holds, and the answer.
    assert unit["lat"] == "30.760000"
    assert unit["point"]["source"] == "unit"


def test_a7_neither_point_is_not_invented(brazos, dana):
    """No marker is ever made up — the map's own posture since CR-028."""
    created = _premises(dana)
    unit = services.create_unit(dana, {"premises_id": created["id"], "label": "2"})
    row = models.Unit.objects.select_related("premises").get(pk=unit["id"])
    assert selectors.unit_point(row) == {"lat": None, "lng": None, "source": "none"}


def test_a7_a_unit_point_can_be_cleared_back_to_the_building(brazos, dana):
    """Clearing is an ANSWER, not an absence — *this unit has no point of its
    own after all* — and the unit goes back to reading its building's."""
    created = _premises(dana, lat="30.752104", lng="-98.238391")
    unit = services.create_unit(
        dana,
        {"premises_id": created["id"], "label": "3", "lat": "30.76", "lng": "-98.24"},
    )
    services.update_unit(dana, unit["id"], {"lat": None, "lng": None})
    row = models.Unit.objects.select_related("premises").get(pk=unit["id"])
    assert row.lat is None
    assert selectors.unit_point(row)["source"] == "premises"


def test_a7_half_a_point_is_refused_on_a_unit(brazos, dana):
    """⚠ **HALF A POINT IS NEITHER PLACED NOR FALLEN BACK**, and the rule has
    no third state. Every reader downstream quietly tolerates it, which is
    precisely why it has to be refused at the field."""
    created = _premises(dana)
    with pytest.raises(errors.ValidationError) as caught:
        services.create_unit(dana, {"premises_id": created["id"], "label": "4", "lat": "30.76"})
    assert "metering.unit.point_needs_both" in str(caught.value.field_errors)


def test_a7_a_unit_still_cannot_be_given_an_address(brazos, dana):
    """`BR-MET-1162` narrows the COORDINATE clause and only that clause. PO:
    *"The address half stands."*

    RED BEFORE would have been the opposite: widening `known` by hand is how a
    unit quietly acquires a second address, and this is the case that says the
    widening stopped where the ruling did.
    """
    created = _premises(dana)
    with pytest.raises(errors.ValidationError) as caught:
        services.create_unit(
            dana, {"premises_id": created["id"], "label": "5", "city": "Silver Creek"}
        )
    assert "metering.unknown_field" in str(caught.value.field_errors)


# ── PUJ-19 — a point can be corrected ───────────────────────────────────────


def test_a6_a_wrong_pin_can_be_corrected_on_the_edit_form(brazos, dana):
    """RED BEFORE, and this is the whole of `PUJ-19`:

        metering.unknown_field on field 'lat'

    `_validate_premises` refused both coordinates on the PARTIAL path by name,
    deliberately — the only writers were the City and a deterministic seed. The
    consequence was that a property on the wrong side of the street stayed
    there, and no screen in the product could move it.
    """
    created = _premises(dana, lat="30.752104", lng="-98.238391")
    updated = services.update_premises(
        dana, created["id"], {"lat": "30.752900", "lng": "-98.239100"}
    )
    assert updated["lat"] == "30.752900"
    row = models.Premises.objects.get(pk=created["id"])
    assert row.lat == Decimal("30.752900")


def test_a6_a_latitude_outside_the_world_is_refused(brazos, dana):
    """A clerk typing the LONGITUDE into the latitude box is the ordinary
    mistake this path now has to survive; unrefused it puts a marker in the
    Southern Ocean with every test green."""
    created = _premises(dana)
    with pytest.raises(errors.ValidationError) as caught:
        services.update_premises(dana, created["id"], {"lat": "-98.238391", "lng": "30.75"})
    assert "metering.premises.coordinate_range" in str(caught.value.field_errors)


# ── PUJ-01 — the list can find the properties with no point ─────────────────


def test_a8_needs_a_location_finds_exactly_the_unplaced(brazos, dana):
    """RED BEFORE: `premises_list` had no `location` branch and
    `PREMISES_FILTERS` did not name it — so the chip was DROPPED by
    `parse_list_params` (*"undeclared filter names are ignored"*) and the list
    answered with the whole tenant, which reads exactly like a filter that
    found everything. That is `DEF-836`'s shape on this same list."""
    _premises(dana, address_line="1 Placed St", lat="30.75", lng="-98.23")
    _premises(dana, address_line="2 Unplaced St")
    _premises(dana, address_line="3 Unplaced St")

    needs = selectors.premises_list(filters={"location": "needs_location"})
    placed = selectors.premises_list(filters={"location": "placed"})
    assert needs.count() == 2
    assert placed.count() == 1
    assert sorted(row.address_line for row in needs) == ["2 Unplaced St", "3 Unplaced St"]
    # ⚠ AND AN UNKNOWN VALUE FALLS THROUGH RATHER THAN ANSWERING EMPTY: an
    # empty list would read as *none of your properties are placed*.
    assert selectors.premises_list(filters={"location": "banana"}).count() == 3


def test_def4740_the_map_filter_separates_checked_from_merely_placed(brazos, dana):
    """RED BEFORE (2026-09-10): the branch offered `placed` and nothing else, so
    a clerk could ask *is there a point at all* and could NOT ask *which of
    these still needs a person's eye* — which is over half of the work the GIS
    wave exists to end. The blueprint draws three states and argues for the
    split in its own words: *"a point that arrived from an address lookup and a
    point a person has seen against the city map are different degrees of
    confidence."*

    ⚠ **`gis_unchecked` IS `False` ON EVERY ROW BELOW AND THAT IS THE TRAP.**
    It is `NOT NULL DEFAULT false`, so filtering *Checked* on the boolean would
    return all three — the whole estate, reported as verified by a person who
    does not exist. The STAMP is what separates them, here and on the screen
    (`premisesMapState` in `PremisesListPage.tsx` reads the same two facts).
    """
    checked = _premises(dana, address_line="1 Checked St", lat="30.75", lng="-98.23")
    _premises(dana, address_line="2 Unverified St", lat="30.76", lng="-98.24")
    _premises(dana, address_line="3 Unplaced St")
    # The stamp is written by the service, never by the fixture — the same path
    # a clerk pressing the control goes down.
    services.update_premises(dana, checked["id"], {"gis_unchecked": False})

    assert [
        row.address_line for row in selectors.premises_list(filters={"location": "checked"})
    ] == ["1 Checked St"]
    assert [
        row.address_line
        for row in selectors.premises_list(filters={"location": "placed_unchecked"})
    ] == ["2 Unverified St"]
    # The three partition the tenant: every property is in exactly one.
    assert selectors.premises_list(filters={"location": "needs_location"}).count() == 1
    assert selectors.premises_list(filters={"location": "placed"}).count() == 2
    assert selectors.premises_list().count() == 3


# ── PUJ-10 — the GIS check is a PAIR, and the default is not an answer ──────


def test_a3_a_property_nobody_checked_is_not_reported_as_checked(brazos, dana):
    """⚠ **THIS IS THE CASE THAT MATTERS MOST AND IT IS THE EASIEST TO GET
    WRONG.** `gis_unchecked` is `NOT NULL DEFAULT false`, so on all 673
    properties it reads *false* — and a screen drawing *false* as **Checked**
    would tell a clerk the whole estate had been verified by a person who does
    not exist. The stamp is what separates them."""
    created = _premises(dana)
    detail = selectors.premises_detail_dict(models.Premises.objects.get(pk=created["id"]))
    assert detail["gis_unchecked"] is False
    assert detail["gis_checked_at"] is None
    assert detail["gis_checked_by"] is None


def test_a4_marking_checked_records_who_and_when(brazos, dana):
    """RED BEFORE: the columns did not exist, so the ruling's *"with who and
    when"* had nowhere to live and the screen could only ever say *Checked*."""
    created = _premises(dana, gis_unchecked=True)
    assert created["gis_checked_at"] is None

    updated = services.update_premises(dana, created["id"], {"gis_unchecked": False})
    assert updated["gis_unchecked"] is False
    assert updated["gis_checked_at"] is not None
    # `dana` is the test actor namespace; the USER row is what the selector names.
    assert updated["gis_checked_by"] == (dana.user.full_name or dana.user.email)


def test_a4_withdrawing_the_check_clears_the_checker(brazos, dana):
    """A stale checker beside an unchecked flag is worse than no checker."""
    created = _premises(dana, gis_unchecked=False)
    services.update_premises(dana, created["id"], {"gis_unchecked": False})
    withdrawn = services.update_premises(dana, created["id"], {"gis_unchecked": True})
    assert withdrawn["gis_checked_at"] is None
    assert withdrawn["gis_checked_by"] is None


def test_a4_an_unrelated_edit_does_not_re_date_the_check(brazos, dana):
    """The stamp fires on an EXPLICIT statement about the flag and on nothing
    else — renaming a property must not claim somebody re-checked it."""
    created = _premises(dana)
    services.update_premises(dana, created["id"], {"gis_unchecked": False})
    stamped = selectors.premises_detail_dict(models.Premises.objects.get(pk=created["id"]))
    services.update_premises(dana, created["id"], {"name": "Cypress Row Apartments"})
    after = selectors.premises_detail_dict(models.Premises.objects.get(pk=created["id"]))
    assert after["gis_checked_at"] == stamped["gis_checked_at"]
    assert after["gis_checked_by"] == stamped["gis_checked_by"]


# ── PUJ-49 — the equipment map reads a unit's own point ─────────────────────


def test_a9_a_units_own_point_wins_on_the_map(brazos, dana):
    """RED BEFORE: `unit_premises_geo_index` selected `premises__lat` outright,
    so **a park of twelve cabins drew ONE pin at the site office** with eleven
    markers stacked underneath it — twelve meters at twelve places, reported as
    one."""
    created = _premises(dana, lat="30.752104", lng="-98.238391")
    flat = services.create_unit(dana, {"premises_id": created["id"], "label": "Flat 1"})
    cabin = services.create_unit(
        dana,
        {"premises_id": created["id"], "label": "Cabin 7", "lat": "30.76", "lng": "-98.24"},
    )
    index = selectors.unit_premises_geo_index()
    assert index[flat["id"]]["lat"] == "30.752104"
    assert index[flat["id"]]["point_source"] == "premises"
    assert index[cabin["id"]]["lat"] == "30.760000"
    assert index[cabin["id"]]["point_source"] == "unit"


def test_a9_a_unit_with_its_own_point_on_an_unplaced_building_is_still_drawn(brazos, dana):
    """⚠ **THE FILTER HAD TO MOVE WITH THE COALESCE AND THIS IS WHY.** It read
    `premises__lat__isnull=False`, which EXCLUDED the very case the ruling was
    written for — a pad on a parcel nobody has placed — silently, with the map
    looking perfectly healthy."""
    created = _premises(dana)  # the building has no point at all
    pad = services.create_unit(
        dana,
        {"premises_id": created["id"], "label": "Pad 3", "lat": "30.77", "lng": "-98.25"},
    )
    index = selectors.unit_premises_geo_index()
    assert pad["id"] in index
    assert index[pad["id"]]["point_source"] == "unit"
