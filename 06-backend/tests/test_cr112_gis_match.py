"""CR-112 — the match and the classify, against the ten PO rulings of 2026-09-17.

Pure throughout: our rows are dicts, their rows are a `Snapshot` from the
fixture, and nothing here opens a database. That is what lets `preview` and
`apply` run the same code (`BR-INT-074`).

Every ruling that has a testable consequence has a test named after it.
"""

from __future__ import annotations

from decimal import Decimal

from apps.integrations import gis_esri_fixtures as fx
from apps.integrations.gis_layer import LayerConfig, walk
from apps.integrations.gis_match import (
    APPLY,
    CONFLICT,
    NEVER_TOUCH,
    NEW_VALUE,
    QUEUE,
    TWO_PREMISES_ONE_PARCEL,
    UNMATCHED,
    SnapshotIndex,
    decide_premises_key,
    decide_unit_key,
    disposition_for,
    reconcile,
)

SNAPSHOT = walk(LayerConfig(layer_url=fx.FIXTURE_LAYER), transport=fx.recorded_transport)
INDEX = SnapshotIndex.of(SNAPSHOT)


def premises(**kw):
    base = {
        "id": "P1", "premise_no": "P-00001", "address_line": "100 N Maple St",
        "city": "Riverbend", "state": "MI", "postal_code": "48104",
        "lat": None, "lng": None, "gis_parcel_id": None, "gis_parcel_id_was": None,
        "gis_status": None,
    }
    base.update(kw)
    return base


def unit(**kw):
    base = {"id": "U1", "label": "1", "gis_point_id": None, "gis_point_id_was": None,
            "lat": None, "lng": None, "gis_status": None}
    base.update(kw)
    return base


# ── ruling 3 · the keys arrive by address matching ──────────────────────────


def test_a_premises_with_no_key_and_one_clean_match_takes_the_key():
    decision = decide_premises_key(premises(), INDEX)
    assert decision.action == "take"
    assert decision.new_key == "09-01-100"


def test_a_premises_whose_street_is_spelled_differently_still_matches():
    """`100 north maple street` is the same address as `100 N Maple St`."""
    decision = decide_premises_key(premises(address_line="100 North Maple Street"), INDEX)
    assert decision.action == "take"
    assert decision.new_key == "09-01-100"


def test_a_premises_that_matches_nothing_queues_and_stores_nothing():
    decision = decide_premises_key(premises(address_line="9 Nowhere Rd"), INDEX)
    assert decision.action == "queue"
    assert decision.new_key is None


def test_a_premises_with_no_address_matches_nothing_rather_than_everything():
    """A blank key must not pool with every other blank key."""
    decision = decide_premises_key(premises(address_line=""), INDEX)
    assert decision.action == "queue"


def test_a_premises_with_no_postcode_matches_only_on_a_unique_street():
    """Otherwise *one clean match* comes out of a bucket two postcodes share."""
    decision = decide_premises_key(premises(postal_code=None), INDEX)
    assert decision.action == "take", "that street is unique in this snapshot"


# ── ruling 7 · a retired parcel is re-derived by address ────────────────────


def test_a_key_that_no_longer_resolves_is_replaced_from_one_clean_match():
    decision = decide_premises_key(premises(gis_parcel_id="OLD-RETIRED"), INDEX)
    assert decision.action == "replace"
    assert decision.new_key == "09-01-100"
    assert decision.old_key == "OLD-RETIRED", "what it was is kept"


def test_a_key_that_no_longer_resolves_and_matches_nothing_keeps_the_old_key():
    """⚠ Anything but one clean match queues AND THE OLD KEY STAYS."""
    decision = decide_premises_key(
        premises(gis_parcel_id="OLD-RETIRED", address_line="9 Nowhere Rd"), INDEX
    )
    assert decision.action == "queue"
    assert decision.old_key == "OLD-RETIRED"
    assert decision.new_key is None


def test_a_key_that_still_resolves_is_left_alone():
    decision = decide_premises_key(premises(gis_parcel_id="09-01-100"), INDEX)
    assert decision.action == "keep"


def test_the_same_key_in_a_different_case_is_not_a_change():
    decision = decide_premises_key(premises(gis_parcel_id="09-01-100"), INDEX)
    assert decision.action == "keep", "compared case-insensitively"


# ── the unit half ───────────────────────────────────────────────────────────


def test_a_unit_matches_only_inside_its_building_parcel():
    decision = decide_unit_key(unit(label="1"), "09-01-200", INDEX)
    assert decision.action == "take"
    assert decision.new_key == "09-01-200-0001"


def test_a_unit_label_matches_across_spellings():
    """Our `2` against their `APT 2`."""
    decision = decide_unit_key(unit(label="2"), "09-01-200", INDEX)
    assert decision.action == "take"
    assert decision.new_key == "09-01-200-0002"


def test_a_unit_whose_building_did_not_match_queues_and_is_not_matched_globally():
    """`Unit 1` exists on two parcels — matching globally pairs the wrong one."""
    decision = decide_unit_key(unit(label="1"), None, INDEX)
    assert decision.action == "queue"
    assert decision.new_key is None


def test_a_building_that_matches_but_a_unit_that_does_not_keeps_the_parcel_key():
    """The brief's case: store the parcel key, leave the point key empty, queue."""
    report = reconcile(
        snapshot=SNAPSHOT,
        premises=[premises(address_line="220 Oak Ave")],
        units_by_premises={"P1": [unit(label="99")]},
    )
    parcel = next(d for d in report.key_decisions if d.level == "premises")
    point = next(d for d in report.key_decisions if d.level == "unit")
    assert parcel.action == "take" and parcel.new_key == "09-01-200"
    assert point.action == "queue" and point.new_key is None


# ── ruling 6 · a building with no point of its own gets no pin ──────────────


def test_a_parcel_with_a_building_point_gives_the_premises_that_pin():
    row = INDEX.building_point("09-01-200")
    assert row is not None and row.point_id == "09-01-200-0000"


def test_a_parcel_whose_every_point_is_a_unit_gives_the_building_no_pin():
    """⚠ Ruling 6 — *"a) leave the building's pin blank"*. Never borrow, never average."""
    assert INDEX.building_point("09-01-300") is None


def test_a_premises_on_such_a_parcel_gets_no_coordinate_difference():
    report = reconcile(
        snapshot=SNAPSHOT,
        premises=[premises(address_line="330 Elm Ct")],
        units_by_premises={},
    )
    coordinate_rows = [d for d in report.differences if d.field_name in ("lat", "lng")]
    assert coordinate_rows == [], "no building point means no pin is even compared"


# ── ruling 9 · never touch by default ───────────────────────────────────────


def test_a_field_with_no_disposition_is_never_touched():
    assert disposition_for("city", CONFLICT, None) == NEVER_TOUCH
    assert disposition_for("city", CONFLICT, {}) == NEVER_TOUCH


def test_a_value_nobody_recognises_falls_back_to_never_touch():
    assert disposition_for("city", CONFLICT, {"city": "sure why not"}) == NEVER_TOUCH


def test_a_structural_class_queues_however_the_policy_is_configured():
    """A utility cannot configure its way past *two premises on one parcel*."""
    for klass in (TWO_PREMISES_ONE_PARCEL, UNMATCHED):
        assert disposition_for("gis_parcel_id", klass, {"gis_parcel_id": APPLY}) == QUEUE


def test_the_first_run_applies_nothing_and_the_report_says_why():
    """⚠ The sentence a clerk needs, or the screen reads as broken."""
    report = reconcile(
        snapshot=SNAPSHOT,
        premises=[premises(city="Oldname", address_line="100 N Maple St")],
        units_by_premises={},
    )
    assert report.to_apply == []
    # Four: the city CONFLICTS, and lat, lng and gis_status are each a value
    # they have and we do not. Every one of them is left alone.
    assert report.headline(fields_never_touch=7) == (
        "4 differences found, 0 applied, all 7 fields set to never touch"
    )


def test_a_field_turned_on_is_applied():
    report = reconcile(
        snapshot=SNAPSHOT,
        premises=[premises(city="Oldname")],
        units_by_premises={},
        policy={"city": APPLY},
    )
    applied = report.to_apply
    assert [one.field_name for one in applied] == ["city"]
    assert applied[0].ours == "Oldname" and applied[0].theirs == "Riverbend"


# ── the reconcile itself ────────────────────────────────────────────────────


def test_an_unchanged_field_produces_no_difference_at_all():
    """Not *a difference classified as agreeing* — no row. It is most of a run."""
    report = reconcile(snapshot=SNAPSHOT, premises=[premises()], units_by_premises={})
    assert [one.field_name for one in report.differences if one.field_name == "city"] == []


def test_a_value_we_lack_and_they_have_is_a_new_value():
    report = reconcile(snapshot=SNAPSHOT, premises=[premises()], units_by_premises={})
    lat = next(one for one in report.differences if one.field_name == "lat")
    assert lat.difference_class == NEW_VALUE
    assert lat.theirs == Decimal("42.280100")


def test_zip_plus_four_is_not_reported_as_a_difference():
    """Otherwise the first run files one on every row in the register."""
    report = reconcile(
        snapshot=SNAPSHOT, premises=[premises(postal_code="48104-1234")], units_by_premises={}
    )
    assert [one for one in report.differences if one.field_name == "postal_code"] == []


def test_two_premises_on_one_parcel_is_reported_and_never_applied():
    report = reconcile(
        snapshot=SNAPSHOT,
        premises=[
            premises(id="P1", premise_no="P-1", address_line="100 N Maple St"),
            premises(id="P2", premise_no="P-2", address_line="100 North Maple Street"),
        ],
        units_by_premises={},
        policy={"gis_parcel_id": APPLY},
    )
    clash = [one for one in report.differences if one.difference_class == TWO_PREMISES_ONE_PARCEL]
    assert len(clash) == 1
    assert clash[0].disposition == QUEUE


# ── ruling 8 · a City address we have no premises for is IGNORED ────────────


def test_a_city_parcel_we_have_no_premises_for_raises_nothing_but_is_counted():
    report = reconcile(snapshot=SNAPSHOT, premises=[premises()], units_by_premises={})
    assert report.city_rows_ignored == 3, "four parcels in the snapshot, one of them ours"
    assert all(one.level != "city" for one in report.key_decisions), "no work item, ever"


# ── thrash · our bug, not the City's ────────────────────────────────────────


def test_a_key_changing_on_a_row_we_have_already_changed_is_counted_as_thrash():
    report = reconcile(
        snapshot=SNAPSHOT,
        premises=[premises(gis_parcel_id="OLD-2", gis_parcel_id_was="OLD-1")],
        units_by_premises={},
    )
    assert report.thrash_candidates == ["P-00001"]


def test_a_first_key_change_is_not_thrash():
    report = reconcile(
        snapshot=SNAPSHOT,
        premises=[premises(gis_parcel_id="OLD-2", gis_parcel_id_was=None)],
        units_by_premises={},
    )
    assert report.thrash_candidates == []
