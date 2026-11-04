# ── Trace ──────────────────────────────────────────────
# Defects:  DEF-INT-9846 (PO GIS review 2026-10-07, gap 4) · DEF-INT-5620
# Rules:    BR-INT-022 (the breaker counts SILENCE, never an answer) ·
#           BR-INT-048 (the inline search answers inside its budget) ·
#           B14 rule 33 (each reason is a fact of six words or fewer)
# Impacts:  apps/integrations/adapters/gis_city.py · gis.py · gis_layer.py ·
#           gis_parcels.py · gis_fixtures.py · gis_esri_fixtures.py
# ───────────────────────────────────────────────────────
"""A City that ANSWERS and refuses us reaches the clerk as the amber box with a
reason — never as our own 500, never as *the City is not answering*.

**RED BEFORE, measured 2026-10-07 at 2.558.3 with these exact cases:** the
search with a 401, a 404 and a 503 raised `HTTPError` out of `gis.search` (the
route's `500 SYS-INTERNAL`); the `200 OK` + ArcGIS `498` body answered
`message_key = integrations.gis.city_not_answering` and moved the breaker to 1;
the parcel check's first request (`read_layer_metadata`) raised `HTTPError`
out of `gis.reconcile` (the route's 500).

⚠ **THE HOSTS ARE RECORDED, NOT MOCKED IN-LINE.** `gis_fixtures.refusal_for`
serves four `.example` hosts that refuse — 401, 404, 503 and a 200 carrying an
error body — and both recordings (the address search and the layer walk) use it,
so this file, the walkthrough and a clerk editing the connection's address all
drive the SAME code path through the real endpoints.
"""

from __future__ import annotations

import pytest

from apps.integrations import gis, gis_fixtures, gis_layer, gis_parcels, models, runtime
from apps.integrations import api as integrations_api
from apps.integrations import services as integration_services
from apps.integrations.adapters.base import ConnectionView
from apps.integrations.adapters.gis_city import CityRefused, GisCityAdapter
from core.permissions import SYSTEM_ADMIN
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana
from tests.test_us_ten_helpers import api_call

pytestmark = pytest.mark.django_db

KEY = "integrations.gis.city_rejected_key"
MOVED = "integrations.gis.city_layer_moved"
ERROR = "integrations.gis.city_service_error"

#: host → the reason key the clerk must be shown. One row per shape.
CASES = [
    (gis_fixtures.KEY_REFUSED_HOST, KEY),  # HTTP 401
    (gis_fixtures.MOVED_HOST, MOVED),  # HTTP 404
    (gis_fixtures.DOWN_HOST, ERROR),  # HTTP 503
    (gis_fixtures.TOKEN_BODY_HOST, KEY),  # 200 OK + {"error": {"code": 498}}
]


@pytest.fixture(autouse=True)
def _clear_caps():
    runtime.reset_caps()
    yield
    runtime.reset_caps()


def _connect(tenant, actor, host, *, path="/addr"):
    from core.tenancy import tenant_context

    with tenant_context(tenant.id):
        return integration_services.connect(
            actor=actor,
            tenant_id=tenant.id,
            provider_key=gis.PROVIDER_KEY,
            environment=models.ENVIRONMENT_PRODUCTION,
            config={"base_url": f"https://{host}{path}"},
            cadence=models.CADENCE_NIGHTLY,
        )


def _breaker_count(connection) -> int:
    """Read back INSIDE the tenant: `RLS FORCE` answers nothing outside it on
    PostgreSQL (hard rule 1), which SQLite would never show."""
    from core.tenancy import tenant_context

    with tenant_context(connection.tenant_id):
        connection.refresh_from_db()
    breaker = dict(connection.config or {}).get("breaker") or {}
    return int(breaker.get("consecutive_timeouts") or 0)


# ── the classifier, pure ────────────────────────────────────────────────────


def test_one_classifier_reads_an_http_status_and_an_arcgis_body_code_alike():
    assert gis_layer.refusal_reason(401) == gis_layer.REFUSED_KEY
    assert gis_layer.refusal_reason(403) == gis_layer.REFUSED_KEY
    assert gis_layer.refusal_reason(498) == gis_layer.REFUSED_KEY  # ArcGIS: invalid token
    assert gis_layer.refusal_reason("499") == gis_layer.REFUSED_KEY  # ArcGIS: token required
    assert gis_layer.refusal_reason(404) == gis_layer.REFUSED_MOVED
    assert gis_layer.refusal_reason(400) == gis_layer.REFUSED_MOVED  # field or layer gone
    assert gis_layer.refusal_reason(503) == gis_layer.REFUSED_ERROR
    # Unreadable is THEIR error, never a claim about our key.
    assert gis_layer.refusal_reason(None) == gis_layer.REFUSED_ERROR
    assert gis_layer.refusal_reason("nonsense") == gis_layer.REFUSED_ERROR


def test_every_reason_has_a_key_and_a_sentence_of_six_words_or_fewer():
    """B14 rule 33 — a FACT is six words or fewer, in every language we ship."""
    import json
    from pathlib import Path

    for reason in (gis_layer.REFUSED_KEY, gis_layer.REFUSED_MOVED, gis_layer.REFUSED_ERROR):
        assert reason in gis_parcels.REFUSAL_KEYS
        assert len(gis_parcels.REFUSAL_HEADLINES[reason].split()) <= 6
    locales = Path(__file__).resolve().parents[2] / "07-frontend" / "src" / "i18n" / "locales"
    files = sorted(locales.glob("*.json"))
    assert len(files) == 11, [one.name for one in files]
    for one in files:
        catalogue = json.loads(one.read_text(encoding="utf-8"))
        for key in (KEY, MOVED, ERROR):
            assert catalogue.get(key), f"{one.name} has no {key}"


# ── the address search, through the real service and the real route ───────


@pytest.mark.parametrize("host,expected", CASES)
def test_a_refusing_city_is_the_amber_box_with_its_reason(brazos, dana, host, expected):
    from core.tenancy import tenant_context

    connection = _connect(brazos, dana, host)
    with tenant_context(brazos.id):
        answer = gis.search(brazos.id, query="1408 Pec")
    assert answer["reachable"] is False
    assert answer["message_key"] == expected
    assert answer["candidates"] == []
    # BR-INT-022 — the City ANSWERED, so the breaker counts nothing.
    assert _breaker_count(connection) == 0
    # BR-INT-039 — the attempt is on the record, closed, as a failure.
    with tenant_context(brazos.id):
        run = (
            models.IntegrationRun.objects.filter(connection=connection)
            .order_by("-started_at")
            .first()
        )
    assert run is not None and run.finished_at is not None and run.failed == 1


@pytest.mark.parametrize("host,expected", CASES)
def test_the_search_route_answers_200_and_never_our_500(brazos, dana, host, expected):
    _connect(brazos, dana, host)
    response = api_call(
        integrations_api.address_search,
        "get",
        f"/api/{brazos.subdomain}/integrations/{gis.PROVIDER_KEY}/address-search",
        user=dana.user,
        role=SYSTEM_ADMIN,
        tenant=brazos,
        query={"q": "1408 Pec"},
        key=gis.PROVIDER_KEY,
    )
    assert response.status_code == 200, response.data
    assert response.data["reachable"] is False
    assert response.data["message_key"] == expected


def test_four_refusals_in_a_row_never_open_the_breaker(brazos, dana):
    """The breaker opens on SILENCE (three in a row). A rotated key answering
    401 on every keystroke must never stop us dialling a City that is up."""
    from core.tenancy import tenant_context

    connection = _connect(brazos, dana, gis_fixtures.TOKEN_BODY_HOST)
    with tenant_context(brazos.id):
        for _ in range(4):
            answer = gis.search(brazos.id, query="1408 Pec")
            assert answer["message_key"] == KEY
    assert _breaker_count(connection) == 0


def test_the_adapter_translates_rather_than_re_raising_the_transport_error():
    def unauthorised(url, timeout_s):
        return gis_fixtures.refusal_for(f"https://{gis_fixtures.KEY_REFUSED_HOST}/addr")

    adapter = GisCityAdapter(transport=unauthorised)
    view = ConnectionView(
        provider_key=gis.PROVIDER_KEY,
        environment="production",
        config={"base_url": f"https://{gis_fixtures.KEY_REFUSED_HOST}/addr"},
    )
    with pytest.raises(CityRefused) as refused:
        adapter.search(view, {}, "1408 Pec", timeout_s=1.0)
    assert refused.value.reason == gis_layer.REFUSED_KEY
    assert refused.value.status == 401


# ── the pick's re-check ─────────────────────────────────────────────────────


def test_a_refused_re_check_is_a_sentence_and_never_a_downgrade(brazos, dana):
    from core.tenancy import tenant_context

    _connect(brazos, dana, gis_fixtures.MOVED_HOST)
    with tenant_context(brazos.id):
        with pytest.raises(gis.GisRefusal) as refusal:
            gis.create_premises(
                dana,
                brazos.id,
                parcel="88214",
                typed={"address_line": "1408 Pecan St", "owner_id": owner_for(dana, "Whitfield Rentals LLC")},
            )
    assert refusal.value.message_key == MOVED


# ── the parcel check (gis.reconcile → gis_layer.walk), the path Runbook 20 binds to ──


@pytest.mark.parametrize("host,expected", CASES)
def test_the_parcel_check_stops_with_the_reason_and_never_500s(brazos, dana, host, expected):
    _connect(brazos, dana, host, path="/arcgis/rest/services/Qualified/FeatureServer/0")
    response = api_call(
        integrations_api.gis_reconcile,
        "post",
        f"/api/{brazos.subdomain}/integrations/{gis.PROVIDER_KEY}/reconcile",
        user=dana.user,
        role=SYSTEM_ADMIN,
        tenant=brazos,
        data={"mode": "preview"},
        key=gis.PROVIDER_KEY,
    )
    assert response.status_code == 200, response.data
    assert response.data["stopped"] is True
    assert response.data["stop_reason_key"] == expected
    assert response.data["applied"] == {}


def test_silence_on_the_parcel_check_is_still_silence_and_names_no_reason(brazos, dana):
    """A socket that never opens is not a refusal: the run stops, says nothing
    about a key, and keeps the general sentence."""
    def unreachable(url, timeout_s):
        import urllib.error

        raise urllib.error.URLError(ConnectionRefusedError(111, "Connection refused"))

    layer = gis_parcels.config_from_connection(
        {"base_url": f"https://{gis_fixtures.FAST_HOST}/arcgis/rest/services/Q/FeatureServer/0"}
    )
    with pytest.raises(gis_layer.LayerIncomplete):
        gis_layer.walk(layer, transport=unreachable)
