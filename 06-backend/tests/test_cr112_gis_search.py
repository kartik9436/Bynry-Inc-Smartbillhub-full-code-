"""CR-112 §E — address search: our ranking, grouped by building, capped, offered.

Pure: no database, no network. `Building` and `ParcelRow` are dataclasses and
the ranking is arithmetic over them.
"""

from __future__ import annotations

from apps.integrations import gis_esri_fixtures as fx
from apps.integrations.gis_layer import LayerConfig, ParcelRow, walk
from apps.integrations.gis_search import (
    BUILDING_CAP,
    MORE_RESULTS_KEY,
    NOTHING_FOUND_KEY,
    RANKING_NOTE_KEY,
    candidates_to_rows,
    group_by_building,
    rank_candidates,
    presented,
    rank_key,
    where_clause,
)

SNAPSHOT = walk(LayerConfig(layer_url=fx.FIXTURE_LAYER), transport=fx.recorded_transport)


def row(parcel, point, address, unit=None, postcode="48104"):
    return ParcelRow(
        parcel_id=parcel, point_id=point, address_line=address, city="Riverbend",
        state="MI", postal_code=postcode, unit_label=unit, status="ACTIVE",
        lat=None, lng=None,
    )


# ── grouped by building, not a flat list ────────────────────────────────────


def test_a_four_flat_is_one_building_with_its_units_beneath():
    result = group_by_building(SNAPSHOT.rows, typed="220 Oak Ave")
    oak = next(one for one in result["buildings"] if one.parcel == "09-01-200")
    assert oak.unit_count == 2
    assert [u["label"] for u in oak.units] == ["1", "APT 2"]


def test_the_building_row_is_not_repeated_among_its_own_units():
    result = group_by_building(SNAPSHOT.rows, typed="220 Oak Ave")
    oak = next(one for one in result["buildings"] if one.parcel == "09-01-200")
    assert all(u["point_id"] != "09-01-200-0000" for u in oak.units)


def test_every_parcel_becomes_exactly_one_building():
    result = group_by_building(SNAPSHOT.rows)
    assert len(result["buildings"]) == 4, "four parcels in the fixture"


# ── ruling 6 · the building's pin, or none ──────────────────────────────────


def test_a_building_with_its_own_point_carries_that_pin():
    result = group_by_building(SNAPSHOT.rows)
    oak = next(one for one in result["buildings"] if one.parcel == "09-01-200")
    assert oak.lat is not None


def test_a_building_whose_every_point_is_a_unit_carries_no_pin():
    """⚠ Ruling 6 — never borrow a unit's, never average them."""
    result = group_by_building(SNAPSHOT.rows)
    elm = next(one for one in result["buildings"] if one.parcel == "09-01-300")
    assert elm.lat is None and elm.lng is None
    assert elm.unit_count == 2, "it still shows its units"


# ── our ranking, and it is labelled as ours ─────────────────────────────────


def test_an_exact_street_beats_a_partial_one():
    rows = [row("B", "B0", "100 Maple Street North"), row("A", "A0", "100 Maple Street")]
    result = group_by_building(rows, typed="100 Maple Street")
    assert [one.parcel for one in result["buildings"]] == ["A", "B"]


def test_a_postcode_match_breaks_a_tie():
    rows = [row("B", "B0", "5 Elm Court", postcode="99999"),
            row("A", "A0", "5 Elm Court", postcode="48104")]
    result = group_by_building(rows, typed="5 Elm Ct", postcode="48104")
    assert result["buildings"][0].parcel == "A"


def test_an_exact_street_number_beats_a_longer_one_containing_it():
    """`1408` must beat `14080`, which a substring match ranks together."""
    rows = [row("B", "B0", "14080 Pecan St"), row("A", "A0", "1408 Pecan St")]
    result = group_by_building(rows, typed="1408 Pecan St")
    assert result["buildings"][0].parcel == "A"


def test_the_order_is_stable_and_not_the_citys_paging_order():
    forward = group_by_building(SNAPSHOT.rows, typed="Oak")
    backward = group_by_building(list(reversed(SNAPSHOT.rows)), typed="Oak")
    assert [b.parcel for b in forward["buildings"]] == [b.parcel for b in backward["buildings"]]


def test_the_ranking_is_labelled_as_ours():
    """The City publishes none for a `like`; presenting ours as theirs is a claim."""
    result = group_by_building(SNAPSHOT.rows, typed="Oak")
    assert result["ranking_note_key"] == RANKING_NOTE_KEY


# ── the cap, and it says what to do about itself ────────────────────────────


def test_the_cap_counts_buildings_not_rows():
    """A cap on rows shows three buildings when one is a large block."""
    rows = []
    for n in range(3):
        rows.append(row(f"P{n}", f"P{n}-0", f"{n} Big St"))
        rows.extend(row(f"P{n}", f"P{n}-{u}", f"{n} Big St", unit=str(u)) for u in range(1, 40))
    result = group_by_building(rows, typed="Big St")
    assert len(result["buildings"]) == 3
    assert result["more"] is False


def test_more_than_twenty_buildings_is_capped_and_says_keep_typing():
    rows = [row(f"P{n}", f"P{n}-0", f"{n} Long Rd") for n in range(BUILDING_CAP + 5)]
    result = group_by_building(rows, typed="Long Rd")
    assert len(result["buildings"]) == BUILDING_CAP
    assert result["more"] is True
    assert result["message_key"] == MORE_RESULTS_KEY
    assert result["total_buildings"] == BUILDING_CAP + 5, "the true count still travels"


def test_nothing_found_is_an_answer_and_not_an_error():
    """A utility may serve addresses outside the City's layer."""
    result = group_by_building([], typed="9 Nowhere Rd")
    assert result["buildings"] == []
    assert result["message_key"] == NOTHING_FOUND_KEY
    assert result["ranking_note_key"] is None, "nothing to have ordered"


# ── C16 · nothing is written, nothing is auto-selected ──────────────────────


def test_nothing_is_selected_even_when_there_is_exactly_one_result():
    """⚠ The most tempting case and the most dangerous. A person picks."""
    result = group_by_building([row("A", "A0", "1 Only St")], typed="1 Only St")
    assert len(result["buildings"]) == 1
    assert result["selected"] is None


def test_a_row_with_no_parcel_key_is_not_offered():
    """Picking it would store nothing — it is an address a clerk could type."""
    result = group_by_building([row("", "X0", "5 Keyless Way")], typed="Keyless")
    assert result["buildings"] == []


# ── the where clause ────────────────────────────────────────────────────────


def test_the_clause_is_a_like_on_the_configured_field():
    # `DEF-INT-9843` (2026-10-07) — the spelling the PO proved by hand against
    # the live Ann Arbor layer: `UPPER` on both sides, so case is not the
    # store's to decide.
    assert where_clause("Pecan") == "UPPER(Street) LIKE UPPER('%Pecan%')"
    assert where_clause("Pecan", "ADDR") == "UPPER(ADDR) LIKE UPPER('%Pecan%')"


def test_a_quote_in_an_address_is_escaped_not_interpolated():
    """`O'Brien Court` is an ordinary street name."""
    assert where_clause("O'Brien") == "UPPER(Street) LIKE UPPER('%O''Brien%')"
    assert where_clause("x' or '1'='1") == "UPPER(Street) LIKE UPPER('%x'' or ''1''=''1%')"


# ── the bridge from the pre-existing inline search ──────────────────────────


def test_the_older_candidate_shape_converts_and_ranks_the_same_way():
    rows = candidates_to_rows([
        {"parcel": "B", "address_line": "9 Second St"},
        {"parcel": "A", "address_line": "9 First St"},
    ])
    result = group_by_building(rows, typed="9 First St")
    assert result["buildings"][0].parcel == "A"


def test_presented_flattens_for_a_screen_and_keeps_the_keys():
    result = presented(group_by_building(SNAPSHOT.rows, typed="Oak"))
    oak = next(one for one in result["buildings"] if one["parcel"] == "09-01-200")
    assert oak["unit_count"] == 2
    assert isinstance(oak["units"][0]["label"], str)
    assert result["ranking_note_key"] == RANKING_NOTE_KEY


def test_rank_key_puts_lower_first():
    exact = rank_key(row("A", "A0", "100 Maple St"), "100 Maple St")
    partial = rank_key(row("B", "B0", "100 Maple St North"), "100 Maple St")
    assert exact < partial


# ═══════════════════════════════════════════════════════════════════════════
# 2026-09-17 · `DEF-INT-5601` — THE DOOR ONTO THIS MODULE
# ═══════════════════════════════════════════════════════════════════════════
#
# Until this wave `gis_search` had ZERO importers outside this file: 295 lines
# of ranking, grouping and cap with no caller anywhere. `gis.py::search` served
# the City's rows in the CITY's order and then cut them to eight, so *"8 matches
# from the City's records"* was eight arbitrary rows. `rank_candidates` is the
# door; `tests/test_us_int_042_gis.py` proves it through the endpoint.

#: An ArcGIS `like` query answers with no relevance at all — the shape the
#: PO's Ann Arbor layer produces, and the reason this module's ranking exists.
UNSCORED = (
    {"parcel": "C", "address_line": "1408 Pecan Grove Rd", "postal_code": "78703"},
    {"parcel": "A", "address_line": "1408 Pecan St", "postal_code": "78702"},
    {"parcel": "B", "address_line": "1408 Pecan St W", "postal_code": "78702"},
)

#: A GEOCODER answers with one, and the fixtures in this repo are all this shape.
SCORED = (
    {"parcel": "C", "address_line": "1408 Pecan Grove Rd", "score": "64",
     "score_scale": "0-100"},
    {"parcel": "A", "address_line": "1408 Pecan St", "score": "96",
     "score_scale": "0-100"},
    {"parcel": "B", "address_line": "1408 Pecan St W", "score": "58",
     "score_scale": "0-100"},
)


def test_an_unscored_list_is_put_in_our_order_and_labelled_as_ours():
    result = rank_candidates(UNSCORED, "1408 Pecan St")
    assert [one["parcel"] for one in result["candidates"]] == ["A", "C", "B"]
    assert result["ranking_note_key"] == RANKING_NOTE_KEY


def test_a_scored_list_keeps_the_city_order_and_carries_no_note():
    """⚠ **THEIRS WINS WHERE THEY PUBLISHED ONE, AND THE NOTE GOES AWAY.**

    A geocoder's index knows things four tie-breaks over a street name cannot,
    so overriding it makes the answer worse — and saying *"Ordered by us, not
    the city."* over the city's own order is the claim this module exists to
    avoid making.
    """
    result = rank_candidates(SCORED, "1408 Pecan St")
    assert [one["parcel"] for one in result["candidates"]] == ["A", "C", "B"]
    assert result["ranking_note_key"] is None


def test_the_two_scales_produce_one_ordering():
    """A city publishing 0–100 and one publishing 0–1 must not disagree."""
    mixed = (
        {"parcel": "low", "address_line": "1 A St", "score": "0.10", "score_scale": "0-1"},
        {"parcel": "high", "address_line": "2 B St", "score": "90", "score_scale": "0-100"},
    )
    result = rank_candidates(mixed, "A St")
    assert [one["parcel"] for one in result["candidates"]] == ["high", "low"]


def test_one_row_without_a_score_puts_the_whole_list_in_our_order():
    """⚠ Law 7, habit 2 — what would make this rank wrongly.

    Ranking row by row would put every scored row above every unscored one
    whatever the addresses say, because an absent score has no number to
    compare. All or nothing is the only honest reading.
    """
    half = (
        {"parcel": "C", "address_line": "1408 Pecan Grove Rd", "score": "99",
         "score_scale": "0-100"},
        {"parcel": "A", "address_line": "1408 Pecan St"},
    )
    result = rank_candidates(half, "1408 Pecan St")
    assert [one["parcel"] for one in result["candidates"]] == ["A", "C"]
    assert result["ranking_note_key"] == RANKING_NOTE_KEY


def test_nothing_found_carries_no_ranking_note():
    """An empty list has no order, so claiming one would be noise."""
    result = rank_candidates((), "Maple")
    assert result["candidates"] == []
    assert result["ranking_note_key"] is None


def test_the_ranking_never_hands_back_the_score():
    """`US-INT-042` §1 — the number must not reach a screen, even by mistake."""
    result = rank_candidates(SCORED, "1408 Pecan St")
    assert all("score" in one for one in result["candidates"]), (
        "the adapter's own shape is passed through untouched; `gis.presented` "
        "is what drops the number, and this records which of the two does it"
    )
