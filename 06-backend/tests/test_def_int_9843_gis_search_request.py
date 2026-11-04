"""DEF-INT-9843 / 9844 / 9845 — what the address search ASKS the City, and what
comes back. Gaps 1, 7 and 8 of the PO's GIS review of 2026-10-07.

⚠ **GAP 1 (`DEF-INT-9843`).** The search sent `q=`, `limit=` and `key=` — a
geocoder's words — to an ArcGIS FeatureServer, which ignores all three. The PO
proved the working request BY HAND against the live Ann Arbor layer:

    …/FeatureServer/0/query?where=UPPER(Street) LIKE UPPER('%2670 SEQUOIA%')
        &outFields=*&outSR=4326&returnGeometry=false&f=json

and it answered *"2670 Sequoia Pkwy, Ann Arbor"*. The tests below assert the
URL the adapter now sends, parameter by parameter, and run it against a
FeatureServer-shaped recording of that answer (`gis_esri_fixtures`) that
ASSERTS the request — so a URL that drops `outSR` or goes back to `q=` fails.

⚠ **GAP 7 (`DEF-INT-9844`).** No `outSR` was sent, so a layer stored in Michigan
State Plane (`wkid` 2253) would answer in FEET and the numbers would travel as
lat/lng. Now `outSR=4326` is always sent, and an answer in any other frame is
refused whole, by name, with no coordinate surviving.

⚠ **GAP 8 (`DEF-INT-9845`).** The City's `Unit` was parsed and then dropped.

⚠ **THE RECORDING IS CONSTRUCTED, NOT CAPTURED** — this container's egress
proxy refused the one request tried on 2026-10-07 (`CONNECT tunnel failed,
response 403`). It proves OUR protocol, never Ann Arbor's data.

PROVED RED FIRST (hard-won law 7), through `pytest`, against the tip before the
fix: see the defect rows' `fixed_commit` and the CR record.
"""

from __future__ import annotations

import urllib.parse

import pytest

from apps.integrations import gis, gis_esri_fixtures
from apps.integrations.adapters.base import ConnectionView
from apps.integrations.adapters.gis_city import ForeignFrame, GisCityAdapter, candidate_from
from apps.integrations.gis_search import candidates_to_rows, where_clause

ANN_ARBOR = (
    "https://a2mapseg.a2gov.org/a2arcgis/rest/services/SEU/"
    "SEUQualifiedAddress/FeatureServer/0/query"
)
LAYER = "https://gis.example/arcgis/rest/services/Qualified/FeatureServer/0/query"


def _view(base_url: str = LAYER, field_mapping: dict | None = None) -> ConnectionView:
    config: dict = {"base_url": base_url}
    if field_mapping is not None:
        config["field_mapping"] = field_mapping
    return ConnectionView(provider_key="gis_esri", environment="production", config=config)


def _params(url: str) -> dict[str, list[str]]:
    return urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)


# ── gap 1 · the request ─────────────────────────────────────────────────────


def test_the_search_url_for_2670_sequoia_is_the_one_the_po_proved_by_hand():
    url = GisCityAdapter()._url(_view(ANN_ARBOR), "2670 Sequoia", {})
    parts = urllib.parse.urlsplit(url)
    # The `/query` the clerk typed is not doubled (`gis_layer.layer_base`).
    assert parts.path.endswith("/FeatureServer/0/query")
    assert not parts.path.endswith("/query/query")
    params = _params(url)
    assert params["where"] == ["UPPER(Street) LIKE UPPER('%2670 Sequoia%')"]
    assert params["outFields"] == ["*"]
    assert params["outSR"] == ["4326"]
    assert params["returnGeometry"] == ["true"]  # the pin needs the point
    assert params["f"] == ["json"]
    assert params["resultRecordCount"] == ["9"]  # CANDIDATE_CAP + 1


def test_no_geocoder_words_are_sent():
    params = _params(GisCityAdapter()._url(_view(), "2670 Sequoia", {"api_key": "k-123"}))
    for word in ("q", "limit", "key"):
        assert word not in params, f"{word}= is a geocoder's word and ArcGIS ignores it"


def test_the_key_travels_as_token():
    params = _params(GisCityAdapter()._url(_view(), "2670 Sequoia", {"api_key": "k-123"}))
    assert params["token"] == ["k-123"]


def test_an_open_layer_sends_no_token_at_all():
    assert "token" not in _params(GisCityAdapter()._url(_view(), "2670 Sequoia", {}))


def test_the_street_field_is_the_tenants():
    """`field_mapping` (`BR-INT-037`) — the next city does not call it `Street`."""
    url = GisCityAdapter()._url(_view(field_mapping={"street": "FULLADDR"}), "12 Oak", {})
    assert _params(url)["where"] == ["UPPER(FULLADDR) LIKE UPPER('%12 Oak%')"]


def test_a_typed_quote_and_a_typed_wildcard_are_escaped():
    assert where_clause("O'Brien") == "UPPER(Street) LIKE UPPER('%O''Brien%')"
    assert where_clause("x' or '1'='1") == "UPPER(Street) LIKE UPPER('%x'' or ''1''=''1%')"
    # `_` and `%` are characters a clerk typed, not wildcards.
    assert where_clause("1_2") == "UPPER(Street) LIKE UPPER('%1\\_2%') ESCAPE '\\'"
    assert where_clause("50%") == "UPPER(Street) LIKE UPPER('%50\\%%') ESCAPE '\\'"


def test_a_field_name_that_is_not_an_identifier_is_refused():
    with pytest.raises(ValueError):
        where_clause("12 Oak", "Street) OR (1=1")


def test_the_nightly_walk_still_sends_what_it_always_sent():
    """One builder now serves both callers; the walk's URL must not move."""
    from apps.integrations import gis_layer

    url = gis_layer._query_url(
        gis_layer.LayerConfig(layer_url=LAYER), offset=3, size=3, order_by="OBJECTID",
        api_key="k",
    )
    assert list(_params(url)) == [
        "where", "outFields", "outSR", "returnGeometry", "f",
        "resultOffset", "resultRecordCount", "orderByFields", "token",
    ]
    assert _params(url)["outSR"] == ["4326"]


def test_2670_sequoia_comes_back_from_the_recorded_featureserver():
    adapter = GisCityAdapter(transport=gis_esri_fixtures.search_transport)
    found = adapter.search(_view(), {}, "2670 Sequoia", timeout_s=1.0)
    assert [one["address_line"] for one in found] == ["2670 Sequoia Pkwy", "2670 Sequoia Pkwy"]
    assert found[0]["city"] == "Ann Arbor"
    assert found[0]["frame"] == "EPSG:4326"
    assert found[0]["lat"] == "42.300000" and found[0]["lng"] == "-83.790000"


# ── gap 7 · the frame ───────────────────────────────────────────────────────


def test_an_answer_in_michigan_state_plane_is_refused_by_name():
    adapter = GisCityAdapter(transport=gis_esri_fixtures.projected_search_transport)
    with pytest.raises(ForeignFrame) as caught:
        adapter.search(_view(), {}, "2670 Sequoia", timeout_s=1.0)
    assert caught.value.wkid == 2253
    assert "EPSG:2253" in str(caught.value)


def test_the_refusal_is_logged(caplog):
    adapter = GisCityAdapter(transport=gis_esri_fixtures.projected_search_transport)
    with caplog.at_level("WARNING", logger="apps.integrations.adapters.gis_city"):
        with pytest.raises(ForeignFrame):
            adapter.search(_view(), {}, "2670 Sequoia", timeout_s=1.0)
    assert any("EPSG:2253" in record.getMessage() for record in caplog.records)


def test_the_settings_test_button_says_refused_not_found():
    result = GisCityAdapter(transport=gis_esri_fixtures.projected_search_transport).test(
        _view(), {}, recipient="2670 Sequoia"
    )
    assert result.ok is False
    # `scrub` masks a run of digits on this path (it cannot tell a frame code
    # from a secret), so the NAME of the refusal is what is asserted.
    assert "coordinates are not ours to store" in (result.provider_text or "")


def test_the_refusal_has_its_own_catalogue_key():
    assert gis.REFUSAL_FOREIGN_FRAME == "integrations.gis.foreign_frame"
    assert gis.REFUSAL_FOREIGN_FRAME != gis.REFUSAL_CITY_NOT_ANSWERING


# ── gap 8 · the unit ────────────────────────────────────────────────────────


def test_the_citys_unit_arrives_on_the_candidate():
    adapter = GisCityAdapter(transport=gis_esri_fixtures.search_transport)
    found = adapter.search(_view(), {}, "2670 Sequoia", timeout_s=1.0)
    assert [one["unit"] for one in found] == [None, "A"]
    assert [one["point"] for one in found] == ["09-00-00-000-001-0000", "09-00-00-000-001-000A"]


def test_the_unit_is_read_through_the_tenants_field_mapping():
    feature = {
        "attributes": {"PIN": "P1", "FULLPIN": "P1-2", "Street": "9 Elm St", "SUITE": "2"},
        "geometry": {"x": -83.0, "y": 42.0},
    }
    from apps.integrations import gis_layer

    config = gis_layer.field_names_from({"unit": "SUITE"})
    assert candidate_from(feature, config)["unit"] == "2"


def test_the_unit_reaches_the_wire_shape():
    adapter = GisCityAdapter(transport=gis_esri_fixtures.search_transport)
    found = adapter.search(_view(), {}, "2670 Sequoia", timeout_s=1.0)
    assert [gis.presented(one)["unit"] for one in found] == [None, "A"]


def test_the_grouping_bridge_now_sees_a_building_and_its_unit():
    """What `group_by_building` was blocked on — reported, not wired here."""
    adapter = GisCityAdapter(transport=gis_esri_fixtures.search_transport)
    rows = candidates_to_rows(adapter.search(_view(), {}, "2670 Sequoia", timeout_s=1.0))
    assert [row.is_building_point for row in rows] == [True, False]
    # The unit's point is its FULLPIN, not the parcel.
    assert rows[1].point_id == "09-00-00-000-001-000A"


# ── through the service, on a real tenant ───────────────────────────────────

from tests.test_us_met_helpers import *  # noqa: E402,F401,F403 — brazos · dana


@pytest.fixture(autouse=True)
def _clear_caps():
    from apps.integrations import runtime

    runtime.reset_caps()
    yield
    runtime.reset_caps()


def _connect(tenant, actor):
    from apps.integrations import models
    from apps.integrations import services as integration_services

    return integration_services.connect(
        actor=actor,
        tenant_id=tenant.id,
        provider_key=gis.PROVIDER_KEY,
        environment=models.ENVIRONMENT_PRODUCTION,
        config={"base_url": LAYER},
        cadence=models.CADENCE_NIGHTLY,
    )


@pytest.mark.django_db
def test_the_endpoint_service_carries_the_unit(brazos, dana, monkeypatch):
    from core.tenancy import tenant_context

    monkeypatch.setattr(
        gis.gis_fixtures, "transport_for", lambda url: gis_esri_fixtures.search_transport
    )
    with tenant_context(brazos.id):
        _connect(brazos, dana)
        answer = gis.search(brazos.id, query="2670 Sequoia")
    assert answer["reachable"] is True and answer["message_key"] is None
    assert sorted((one["unit"] or "") for one in answer["candidates"]) == ["", "A"]


@pytest.mark.django_db
def test_the_endpoint_service_refuses_a_state_plane_answer_by_name(brazos, dana, monkeypatch):
    from apps.integrations import models
    from core.tenancy import tenant_context

    monkeypatch.setattr(
        gis.gis_fixtures, "transport_for", lambda url: gis_esri_fixtures.projected_search_transport
    )
    with tenant_context(brazos.id):
        connection = _connect(brazos, dana)
        answer = gis.search(brazos.id, query="2670 Sequoia")
        summaries = list(
            models.IntegrationRun.objects.filter(connection=connection).values_list(
                "summary", "failed"
            )
        )
    # Loud, and named — never "no match", never "not answering".
    assert answer["message_key"] == gis.REFUSAL_FOREIGN_FRAME
    assert answer["reachable"] is True
    # Not one projected number travels.
    assert answer["candidates"] == []
    assert any("EPSG:2253" in (summary or "") and failed == 1 for summary, failed in summaries)


@pytest.mark.django_db
def test_create_refuses_a_state_plane_recheck_and_writes_nothing(brazos, dana, monkeypatch):
    from core.tenancy import tenant_context

    monkeypatch.setattr(
        gis.gis_fixtures, "transport_for", lambda url: gis_esri_fixtures.projected_search_transport
    )
    with tenant_context(brazos.id):
        _connect(brazos, dana)
        with pytest.raises(gis.GisRefusal) as refusal:
            gis.create_premises(
                dana,
                brazos.id,
                parcel="09-00-00-000-001",
                typed={"address_line": "2670 Sequoia", "premises_type": "single_family"},
            )
    assert refusal.value.message_key == gis.REFUSAL_FOREIGN_FRAME
