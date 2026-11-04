"""CR-112 — the Esri Feature Service reader: paging, frames, and refusing.

Every test here is on the PURE half (`apps/integrations/gis_layer.py`), so none
of them touches a database or a network. The fixtures serve `gis.example`, which
RFC 2606 reserves and which can never resolve.

⚠ **THE FIXTURE PAGE SIZE IS 3, NOT 1000, ON PURPOSE.** A fixture that used the
most common page size would pass identically against an implementation that
hard-coded 1000 — which is exactly the bug `BR-INT-072` exists to prevent.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from apps.integrations import gis_esri_fixtures as fx
from apps.integrations.gis_layer import (
    DECLARED_WKID,
    LayerConfig,
    LayerIncomplete,
    LayerRefused,
    assemble_street,
    decimal_or_none,
    normalise_postcode,
    normalise_street,
    normalise_unit,
    read_layer_metadata,
    walk,
)

CONFIG = LayerConfig(layer_url=fx.FIXTURE_LAYER)


# ── TC-1 · the page size is READ, never assumed ─────────────────────────────


def test_page_size_comes_from_the_layer_not_from_us():
    size, object_id = read_layer_metadata(CONFIG, transport=fx.recorded_transport)
    assert size == 3, "the layer publishes 3; anything else means we assumed"
    assert object_id == "OBJECTID"


def test_a_layer_that_publishes_no_page_size_is_refused_not_guessed_at():
    with pytest.raises(LayerRefused, match="maxRecordCount"):
        read_layer_metadata(CONFIG, transport=fx.no_page_size_transport)


# ── TC-2 · the walk is complete, ordered and all-or-nothing ─────────────────


def test_the_walk_reads_every_row_across_pages():
    snapshot = walk(CONFIG, transport=fx.recorded_transport)
    assert len(snapshot) == 7
    assert snapshot.pages == 3, "7 rows at 3 a page is 3 pages"
    assert snapshot.page_size == 3
    assert snapshot.wkid == DECLARED_WKID


def test_a_pull_that_fails_half_way_returns_nothing_at_all():
    """`BR-INT-072` — a half snapshot reads as *the City deleted the rest*."""
    with pytest.raises(LayerIncomplete, match="stopped answering"):
        walk(CONFIG, transport=fx.half_way_transport)


def test_a_service_that_ignores_the_offset_is_caught_rather_than_looped_on():
    """Every page is well formed and it is the same page. This must not hang."""
    with pytest.raises(LayerIncomplete, match="resultOffset"):
        walk(CONFIG, transport=fx.stuck_offset_transport)


def test_an_empty_layer_does_not_read_the_same_as_a_refusal():
    """Law 7 — *examined nothing* and *found nothing* must be distinguishable."""
    snapshot = walk(CONFIG, transport=fx.empty_layer_transport)
    assert len(snapshot) == 0
    assert snapshot.pages == 1, "it answered once, with nothing in it"


# ── TC-3 · the frame ─────────────────────────────────────────────────────────


def test_a_projected_answer_is_refused_by_name():
    """`BR-INT-049`. Those numbers would not fit NUMERIC(9,6) anyway."""
    with pytest.raises(LayerRefused, match="EPSG:2253"):
        walk(CONFIG, transport=fx.projected_transport)


def test_a_coordinate_too_big_for_the_column_is_none_never_truncated():
    """Truncating puts the property somewhere real and wrong — worse than blank."""
    assert decimal_or_none(13312340.55) is None
    assert decimal_or_none(-83.743210) == Decimal("-83.743210")


def test_x_is_longitude_and_y_is_latitude():
    """Swapping them puts a city near 42N/83W in Iraq, which is not obvious."""
    snapshot = walk(CONFIG, transport=fx.recorded_transport)
    maple = next(one for one in snapshot.rows if one.parcel_id == "09-01-100")
    assert maple.lat == Decimal("42.280100")
    assert maple.lng == Decimal("-83.743210")


# ── TC-4 · the mapping ───────────────────────────────────────────────────────


def test_a_blank_street_is_assembled_from_its_parts_in_spoken_order():
    assert assemble_street(
        {"St_Number": "1408", "St_Dir_Pfx": "N", "St_Name": "Pecan", "St_Name_Sfx": "St"}
    ) == "1408 N Pecan St"


def test_the_assembled_branch_actually_fires_on_the_snapshot():
    snapshot = walk(CONFIG, transport=fx.recorded_transport)
    birch = next(one for one in snapshot.rows if one.parcel_id == "09-01-400")
    assert birch.address_line == "44 W Birch Ln"


def test_a_leading_zero_in_a_postcode_survives():
    """`07001` read as a number is `7001`, which is a different place."""
    snapshot = walk(CONFIG, transport=fx.recorded_transport)
    birch = next(one for one in snapshot.rows if one.parcel_id == "09-01-400")
    assert birch.postal_code == "07001"
    assert birch.postcode_key == "07001"


def test_an_unrecognised_status_is_kept_and_never_filtered():
    """Ruling 10 — their vocabulary is theirs; a dropped row is invisible."""
    snapshot = walk(CONFIG, transport=fx.recorded_transport)
    statuses = {one.status for one in snapshot.rows}
    assert "PROVISIONAL" in statuses
    assert len(snapshot) == 7, "nothing was filtered out on status"


def test_the_building_point_is_the_one_whose_unit_is_empty():
    snapshot = walk(CONFIG, transport=fx.recorded_transport)
    oak = [one for one in snapshot.rows if one.parcel_id == "09-01-200"]
    building = [one for one in oak if one.is_building_point]
    assert len(building) == 1
    assert building[0].point_id == "09-01-200-0000"


def test_a_missing_configured_field_is_reported_rather_than_read_as_blank():
    """Otherwise a renamed field reconciles as *blank theirs* on every row."""
    renamed = LayerConfig(layer_url=fx.FIXTURE_LAYER, parcel_field="PARCELNO")
    snapshot = walk(renamed, transport=fx.recorded_transport)
    assert "PARCELNO" in snapshot.attributes_missing
    assert "FULLPIN" in snapshot.attributes_present


# ── TC-5 · normalisation, both sides, never stored ──────────────────────────


@pytest.mark.parametrize(
    "left,right",
    [
        ("1408 N. Pecan St.", "1408 north pecan street"),
        ("220 Oak Ave", "220 OAK AVENUE"),
        ("330 Elm Ct", "330 elm court"),
        ("44 W Birch Ln", "44 West Birch Lane"),
    ],
)
def test_two_spellings_of_one_street_compare_equal(left, right):
    assert normalise_street(left) == normalise_street(right)


@pytest.mark.parametrize("raw,expected", [("APT 2", "2"), ("Apt. 2-B", "2b"), ("2b", "2b"),
                                          ("Unit A", "a"), ("Suite 300", "300"), ("", "")])
def test_unit_labels_reduce_to_the_label_itself(raw, expected):
    assert normalise_unit(raw) == expected


def test_zip_plus_four_compares_equal_to_five_digits():
    """Otherwise every row in the register is a difference."""
    assert normalise_postcode("48104-1234") == normalise_postcode("48104")


# ── the connector's own default ends in /query, and that must not double ────


def test_a_service_address_ending_in_query_is_not_doubled():
    """⚠ **THE CONNECTOR SEEDS EXACTLY THIS VALUE.**

    `manifests/gis_esri.py` defaults *Service address* to
    `…/FeatureServer/0/query`, because that is what a city publishes. Taken at
    face value it builds `…/query/query` — a 404 on every page. Found by reading
    the manifest, not by a test failing: the fixture uses a bare layer url and
    would have gone on passing for ever.
    """
    from apps.integrations.gis_layer import layer_base

    assert layer_base("https://x.example/FeatureServer/0/query") == (
        "https://x.example/FeatureServer/0"
    )
    assert layer_base("https://x.example/FeatureServer/0/query/") == (
        "https://x.example/FeatureServer/0"
    )
    assert layer_base("https://x.example/FeatureServer/0") == (
        "https://x.example/FeatureServer/0"
    )


def test_the_walk_works_against_a_query_suffixed_address():
    suffixed = LayerConfig(layer_url=fx.FIXTURE_LAYER + "/query")
    snapshot = walk(suffixed, transport=fx.recorded_transport)
    assert len(snapshot) == 7, "the same seven rows as the bare layer url"


def test_a_bare_host_still_gets_a_scheme():
    from apps.integrations.gis_layer import layer_base

    assert layer_base("x.example/FeatureServer/0").startswith("https://")
