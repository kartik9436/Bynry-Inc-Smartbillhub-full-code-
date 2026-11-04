"""DEF-MET-10013 — picking a UNIT row from the City's address search.

The City answers *2670 Sequoia* with the building's own point AND unit A's, on
one parcel (`gis_esri_fixtures.SEQUOIA_FEATURES`). Until this fix the write's
live re-check (`C16`) took the FIRST row carrying the picked parcel — whichever
the City happened to list first — so the premises' point and the one unit's
point key depended on the City's order, and nothing said which row the clerk
had actually picked.

Now the screen sends the picked row's own point key (`point`), and:

  * the PREMISES takes the BUILDING's point (hard rule 8 — the premises is the
    building; a unit refines it by LABEL);
  * the unit the create makes under the City's label takes the UNIT's own point
    and key (`BR-MET-1162`);
  * with no `point` sent (an older screen), the building's row is preferred over
    a unit's, never the City's order.

PROVED RED FIRST (hard-won law 7) through pytest against the tip before the fix.
"""

from __future__ import annotations

import copy
from decimal import Decimal

import pytest

from apps.integrations import gis, gis_esri_fixtures
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana
from tests.test_us_met_helpers import owner_for

LAYER = "https://gis.example/arcgis/rest/services/Qualified/FeatureServer/0/query"
BUILDING_POINT = "09-00-00-000-001-0000"
UNIT_POINT = "09-00-00-000-001-000A"


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


def _unit_first(url: str, timeout_s: float):
    """The same answer with the unit listed BEFORE its building."""
    page = gis_esri_fixtures.search_transport(url, timeout_s)
    page["features"] = list(reversed(copy.deepcopy(page["features"])))
    return page


def _create(brazos, dana, monkeypatch, *, transport, point, units):
    from apps.metering import models as metering_models
    from core.tenancy import tenant_context

    monkeypatch.setattr(gis.gis_fixtures, "transport_for", lambda url: transport)
    with tenant_context(brazos.id):
        _connect(brazos, dana)
        typed = {
            "address_line": "2670 Sequoia Pkwy",
            "premises_type": "single_family",
            "owner_id": owner_for(dana, "Whitfield Rentals LLC"),
            "units": units,
        }
        kwargs = {"parcel": "09-00-00-000-001", "typed": typed}
        if point is not None:
            kwargs["point"] = point
        created = gis.create_premises(dana, brazos.id, **kwargs)
        premises = metering_models.Premises.objects.get(pk=created["id"])
        units_now = {
            unit.label: unit
            for unit in metering_models.Unit.objects.filter(premises_id=premises.pk)
        }
    return premises, units_now


@pytest.mark.django_db
def test_a_unit_pick_gives_the_premises_the_buildings_point(brazos, dana, monkeypatch):
    premises, units = _create(
        brazos, dana, monkeypatch,
        transport=_unit_first, point=UNIT_POINT, units=[{"label": "A"}],
    )
    assert (premises.lat, premises.lng) == (Decimal("42.300000"), Decimal("-83.790000"))
    assert premises.gis_parcel_id == "09-00-00-000-001"


@pytest.mark.django_db
def test_a_unit_pick_puts_the_units_own_point_on_the_unit(brazos, dana, monkeypatch):
    _premises, units = _create(
        brazos, dana, monkeypatch,
        transport=gis_esri_fixtures.search_transport, point=UNIT_POINT, units=[{"label": "A"}],
    )
    unit = units["A"]
    assert unit.gis_point_id == UNIT_POINT
    assert (unit.lat, unit.lng) == (Decimal("42.300010"), Decimal("-83.790010"))


@pytest.mark.django_db
def test_without_a_point_the_building_row_wins_not_the_citys_order(brazos, dana, monkeypatch):
    premises, units = _create(
        brazos, dana, monkeypatch,
        transport=_unit_first, point=None, units=[{"label": "1"}],
    )
    assert (premises.lat, premises.lng) == (Decimal("42.300000"), Decimal("-83.790000"))
    assert units["1"].gis_point_id == BUILDING_POINT


@pytest.mark.django_db
def test_a_building_pick_is_unchanged(brazos, dana, monkeypatch):
    premises, units = _create(
        brazos, dana, monkeypatch,
        transport=gis_esri_fixtures.search_transport, point=BUILDING_POINT, units=[{"label": "1"}],
    )
    assert (premises.lat, premises.lng) == (Decimal("42.300000"), Decimal("-83.790000"))
    assert units["1"].gis_point_id == BUILDING_POINT
    # A building pick puts no point of its own on the unit: it reads its
    # building's (`BR-MET-1162`'s fallback).
    assert units["1"].lat is None


@pytest.mark.django_db
def test_a_point_the_city_no_longer_returns_is_refused(brazos, dana, monkeypatch):
    with pytest.raises(gis.GisRefusal) as refusal:
        _create(
            brazos, dana, monkeypatch,
            transport=gis_esri_fixtures.search_transport,
            point="09-00-00-000-001-000Z", units=[{"label": "Z"}],
        )
    assert refusal.value.message_key == gis.REFUSAL_PARCEL_GONE
