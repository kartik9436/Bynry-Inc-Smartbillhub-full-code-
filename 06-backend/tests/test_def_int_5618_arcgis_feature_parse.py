"""DEF-INT-5618 — the live address search could not parse an ArcGIS answer.

⚠ **THIS IS THE GOING-LIVE BLOCKER FOR THE FIRST CITY CONNECTOR CUSTOMER, AND
IT FAILED IN THE ONE WAY NOTHING WOULD HAVE CAUGHT.** `GisCityAdapter._rows`
correctly picks the `features` array out of an ArcGIS FeatureServer reply and
then handed each feature to `candidate_from`, which read FLAT, lower-case keys
— `parcel`, `address`, `lat`, `x`. An ArcGIS feature carries neither: its
fields live under `attributes` and its coordinates under `geometry`. So every
field read empty, every feature was dropped for having no parcel and no
address, `search` returned `[]`, the endpoint answered **200 with an empty
list**, and the screen drew *"The City has no match for that."* — on every
address in the city, looking exactly like a healthy connector against a city
that simply has no record of you.

⚠ **WHY NO TEST CAUGHT IT: EVERY FIXTURE IN THIS REPO IS FLAT.** `gis_fixtures`
records the shape `candidate_from` reads, so the parser and its fixtures agreed
with each other and both disagreed with ArcGIS. **The fixtures below are built
from the FIELD NAMES THE BRIEF DOCUMENTS for Ann Arbor's layer — `PIN`,
`FULLPIN`, `Street`, `City`, `State`, `Zip`, `Unit`, `Status`, with `geometry`
as `x`/`y` — and deliberately NOT from reading `candidate_from`.** Building a
fixture by reading the parser it is meant to test is how this defect was born;
doing it again here would reproduce it exactly.

**PROVED RED BEFORE IT WAS TRUSTED GREEN** (hard-won law 7), through
`pytest`, which is the harness that runs it.

⚠ **NOTHING HERE PROVES ANYTHING ABOUT ANN ARBOR'S REAL DATA.** Their server is
unreachable from this environment (`curl` → 000; inside Django, *Tunnel
connection failed: 403 Forbidden*). These are hand-shaped payloads in the
DOCUMENTED shape. One real call from a deployment that can reach the City is
what confirms the field names, and it is worth making before the customer is
told they are live.
"""

from __future__ import annotations

from decimal import Decimal

from apps.integrations.adapters.gis_city import candidate_from

# ── the documented Ann Arbor layer, in ArcGIS's own shape ───────────────────
# `attributes` for the fields, `geometry` for the point, `x` = longitude and
# `y` = latitude — which is the reverse of how a coordinate is spoken aloud.
ARCGIS_FEATURE = {
    "attributes": {
        "PIN": "09-09-29-201-013",
        "FULLPIN": "09-09-29-201-013-0002",
        "Street": "500 E Washington St",
        "City": "Ann Arbor",
        "State": "MI",
        "Zip": "48104",
        "Unit": "2",
        "Status": "ACTIVE",
    },
    "geometry": {"x": -83.7430, "y": 42.2808},
}


def test_an_arcgis_feature_becomes_a_candidate_at_all():
    """⚠ **THE WHOLE DEFECT IN ONE ASSERTION.** Before the fix this returned
    `None`, so a city whose every row is well-formed produced zero candidates
    and the screen said the City had no match."""
    one = candidate_from(ARCGIS_FEATURE)
    assert one is not None, (
        "an ArcGIS feature must produce a candidate; returning None here is "
        "DEF-INT-5618 and it reads on screen as 'the City has no match'"
    )
    assert one["parcel"] == "09-09-29-201-013"
    assert one["address_line"] == "500 E Washington St"


def test_the_second_key_travels_too():
    """`FULLPIN` → `unit.gis_point_id`, the PO's mapping of 2026-09-17. A
    premises key with no point key leaves every unit unmatched."""
    one = candidate_from(ARCGIS_FEATURE)
    assert one is not None
    assert one["point"] == "09-09-29-201-013-0002"


def test_latitude_and_longitude_are_not_swapped():
    """⚠ **THE ONE ERROR HERE THAT IS NOT OBVIOUS ON SCREEN.** ArcGIS names the
    pair `x`/`y`, so reading them in the spoken order puts a property near
    42N/83W into Iraq — a plausible-looking number in the wrong hemisphere,
    where 0,0 in the Atlantic would at least announce itself."""
    one = candidate_from(ARCGIS_FEATURE)
    assert one is not None
    # The NUMBER, not its spelling: `gis_layer.decimal_or_none` quantises to
    # the six places `NUMERIC(9,6)` holds, so the string is `42.280800`.
    # Asserting the text would be asserting a formatting choice.
    assert Decimal(one["lat"]) == Decimal("42.2808"), "latitude is geometry.y"
    assert Decimal(one["lng"]) == Decimal("-83.7430"), "longitude is geometry.x"


def test_the_postcode_keeps_a_leading_zero():
    """⚠ **TEXT, NEVER A NUMBER.** A New England postcode loses its first digit
    the moment it passes through anything numeric, and `04401` reading as
    `4401` is a wrong address that still looks like an address."""
    feature = {
        "attributes": {**ARCGIS_FEATURE["attributes"], "Zip": "04401"},
        "geometry": dict(ARCGIS_FEATURE["geometry"]),
    }
    one = candidate_from(feature)
    assert one is not None
    assert one["postal_code"] == "04401"


def test_the_citys_own_word_for_its_own_record_survives():
    """Ruling 10 of 2026-09-17 — `Status` is stored as given and never
    filtered. We do not own their vocabulary."""
    one = candidate_from(ARCGIS_FEATURE)
    assert one is not None
    assert one["status"] == "ACTIVE"


def test_the_flat_shape_still_works_exactly_as_before():
    """⚠ **THE REGRESSION THAT WOULD COST MOST.** Every recorded fixture in this
    repo is flat, and so is every city that answers a geocoder rather than a
    FeatureServer. The fix must ADD a shape, never swap one for another."""
    flat = candidate_from({"parcel": "88214", "address": "1408 Pecan St"})
    assert flat is not None
    assert flat["parcel"] == "88214"
    assert flat["address_line"] == "1408 Pecan St"


def test_a_feature_with_no_usable_field_is_still_dropped():
    """The refusal that already existed must survive the new shape: a row with
    no parcel key is a nicely formatted address a clerk could have typed, and
    offering it makes the two cases identical on screen (`OQ-INT-1471`)."""
    assert candidate_from({"attributes": {"Street": "500 E Washington St"}}) is None


# ═══════════════════════════════════════════════════════════════════════════
# The SECOND silent zero — an ArcGIS query error arrives as HTTP 200
# ═══════════════════════════════════════════════════════════════════════════


def test_an_arcgis_error_is_not_reported_as_no_matches():
    """⚠ **ARCGIS REPORTS A FAILED QUERY WITH HTTP 200 AND AN `error` OBJECT.**

    A wrong field name, an expired token or a layer that has moved all come
    back `200 OK` with no `features` array — which read, one layer up, as *the
    city has no record of that address*. So a connector misconfigured on the
    day it went live would say **"The City has no match for that."** for every
    address, for ever, and nothing anywhere would be red.

    ⚠ **THIS ASSERTED `ProviderTimeout` UNTIL 2026-10-07, A RECORDED
    COMPROMISE THAT IS NOW OVER (`DEF-INT-5620`, `DEF-INT-9846`).** That
    reached the clerk as *the City is not answering* — untrue, it answered and
    refused us — and moved the breaker, which counts silence only. It is a
    `CityRefused` now, and a `400` from a FeatureServer (a field or a layer it
    no longer has) is classified *moved*, which `gis.search` shows as
    *"The city's map layer has moved."*
    """
    import pytest

    from apps.integrations import gis_layer
    from apps.integrations.adapters.base import ConnectionView
    from apps.integrations.adapters.gis_city import CityRefused, GisCityAdapter

    def refusing_transport(url: str, timeout_s: float) -> dict:
        return {
            "error": {
                "code": 400,
                "message": "Unable to complete operation.",
                "details": ["Invalid field: PARCELID"],
            }
        }

    adapter = GisCityAdapter(transport=refusing_transport)
    view = ConnectionView(
        provider_key="gis_esri",
        environment="production",
        config={"base_url": "https://gis.example/addr"},
    )
    with pytest.raises(CityRefused) as refused:
        adapter.search(view, {}, "500 E Washington", timeout_s=1.0)
    assert refused.value.reason == gis_layer.REFUSED_MOVED
