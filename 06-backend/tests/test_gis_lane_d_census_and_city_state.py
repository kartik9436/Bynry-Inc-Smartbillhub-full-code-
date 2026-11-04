"""GIS Lane D (PO GIS review, 2026-10-07) — gaps 10, 12, 13 and Lane B's leftovers (a), (b).

Each case names the defect it is the proof for. **Red first, on the tip at
2.560.1 (`3ae31d984`):** there was no `gis.city_state` and no `/state` route
(gap 12), `POST …/reconcile` with no layer answered `500` and left an attempt
row running (leftover a — measured in the browser too), `geocoder_census` had
no adapter so every Connect was refused *Cannot be connected yet.* (gap 13 —
measured in the browser), and the manifest called the parcel check *Nightly*
(leftover b).

⚠ **NO CASE HERE TOUCHES THE NETWORK.** The Census adapter is driven at a
`.example` host, which `census_fixtures` answers (RFC 2606: it can never
resolve, so nothing real is shadowed).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from apps.integrations import api as integrations_api
from apps.integrations import census_fixtures, gis, live_calls, models, page_policy, runtime
from apps.integrations import services as integration_services
from apps.integrations.adapters import ADAPTERS
from apps.integrations.adapters.base import ConnectionView
from apps.integrations.adapters.geocoder_census import CensusGeocoderAdapter, oneline_url
from apps.integrations.registry import REGISTRY
from core.permissions import SYSTEM_ADMIN
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana
from tests.test_us_ten_helpers import api_call

pytestmark = pytest.mark.django_db

LAYER = "https://gis.example/arcgis/rest/services/Qualified/FeatureServer/0"
LOCALES = Path(__file__).resolve().parents[2] / "07-frontend" / "src" / "i18n" / "locales"


@pytest.fixture(autouse=True)
def _clear_caps():
    runtime.reset_caps()
    yield
    runtime.reset_caps()


def _connect_city(tenant, actor, *, status=models.STATUS_WORKING, config=None, enabled=True):
    from core.tenancy import tenant_context

    with tenant_context(tenant.id):
        row = integration_services.connect(
            actor=actor,
            tenant_id=tenant.id,
            provider_key=gis.PROVIDER_KEY,
            environment=models.ENVIRONMENT_PRODUCTION,
            config={"base_url": LAYER},
            cadence=models.CADENCE_MANUAL,
        )
        models.IntegrationConnection.objects.filter(pk=row.pk).update(
            status=status,
            enabled=enabled,
            config=config if config is not None else dict(row.config or {}),
        )
        row.refresh_from_db()
    return row


def _state(tenant):
    from core.tenancy import tenant_context

    with tenant_context(tenant.id):
        return gis.city_state(tenant.id)


# ── gap 12 · the City's state, three answers ────────────────────────────────


def test_no_connection_is_none_with_the_not_connected_sentence(brazos):
    assert _state(brazos) == {"state": "none", "message_key": "integrations.gis.not_connected"}


def test_a_switched_off_connection_is_none_too(brazos, dana):
    _connect_city(brazos, dana, status=models.STATUS_OFF, enabled=False)
    assert _state(brazos)["state"] == "none"


def test_a_connection_whose_last_test_failed_is_broken_and_says_so(brazos, dana):
    _connect_city(brazos, dana, status=models.STATUS_NOT_WORKING)
    assert _state(brazos) == {
        "state": "broken",
        "message_key": "integrations.gis.connection_broken",
    }


def test_a_connection_naming_no_layer_is_broken_and_says_which(brazos, dana):
    _connect_city(brazos, dana, config={"base_url": ""})
    assert _state(brazos) == {"state": "broken", "message_key": "integrations.gis.no_layer"}


def test_a_working_or_untested_connection_says_nothing(brazos, dana):
    row = _connect_city(brazos, dana)
    assert _state(brazos) == {"state": "working", "message_key": None}
    models.IntegrationConnection.objects.filter(pk=row.pk).update(status=models.STATUS_UNTESTED)
    assert _state(brazos)["state"] == "working"


@pytest.mark.parametrize("role", ["billing_clerk", "executive", SYSTEM_ADMIN])
def test_every_role_that_works_premises_may_read_the_state(brazos, dana, role):
    """The premises and unit screens ask it; a Billing Clerk works them
    (`DEF-INT-4267`'s lesson — a settings class here would hide the answer
    from the one person the screen is for)."""
    _connect_city(brazos, dana, status=models.STATUS_NOT_WORKING)
    answer = api_call(
        integrations_api.gis_state,
        "get",
        f"/api/{brazos.subdomain}/integrations/gis_esri/state",
        user=dana.user,
        role=role,
        tenant=brazos,
        key=gis.PROVIDER_KEY,
    )
    assert answer.status_code == 200, answer.data
    assert answer.data == {"state": "broken", "message_key": "integrations.gis.connection_broken"}


def test_the_state_route_is_the_city_gis_only(brazos, dana):
    answer = api_call(
        integrations_api.gis_state,
        "get",
        f"/api/{brazos.subdomain}/integrations/sendgrid/state",
        user=dana.user,
        role=SYSTEM_ADMIN,
        tenant=brazos,
        key="sendgrid",
    )
    assert answer.status_code == 404


# ── leftover (a) · Preview with no layer: a sentence, never a 500 ───────────


def test_a_preview_with_no_layer_is_refused_by_name_and_records_nothing(brazos, dana):
    from core.tenancy import tenant_context

    _connect_city(brazos, dana, config={"base_url": ""})
    with tenant_context(brazos.id):
        before = models.IntegrationRun.objects.count()
    answer = api_call(
        integrations_api.gis_reconcile,
        "post",
        f"/api/{brazos.subdomain}/integrations/gis_esri/reconcile",
        user=dana.user,
        role=SYSTEM_ADMIN,
        tenant=brazos,
        data={"mode": "preview"},
        key=gis.PROVIDER_KEY,
    )
    assert answer.status_code == 409, answer.data
    assert answer.data["message_key"] == "integrations.gis.no_layer"
    with tenant_context(brazos.id):
        # No attempt row: nothing was dialled (`BR-INT-039` records ATTEMPTS).
        assert models.IntegrationRun.objects.count() == before


def test_runbook_20_reads_the_same_refusal_in_words(brazos, dana):
    from apps.runbooks.seams import integrations_seam
    from core.tenancy import tenant_context

    _connect_city(brazos, dana, config={"base_url": ""})
    with tenant_context(brazos.id):
        answer = integrations_seam.city_parcels(pages=1)
    assert answer["refused"] is True
    assert answer["message_key"] == "integrations.gis.no_layer"
    assert answer["headline"] == "The city layer address is missing."


# ── gap 12 · the sentences, eleven catalogues, rule 33 ──────────────────────


NEW_KEYS = (
    "integrations.gis.no_layer",
    "integrations.gis.connection_broken",
    "integrations.provider.gis_esri.operation.reconcile_parcels",
)


def test_the_new_sentences_are_in_all_eleven_catalogues_and_short():
    files = sorted(LOCALES.glob("*.json"))
    assert len(files) == 11, [one.name for one in files]
    for one in files:
        catalogue = json.loads(one.read_text(encoding="utf-8"))
        for key in NEW_KEYS:
            assert catalogue.get(key), f"{one.name} has no {key}"
    english = json.loads((LOCALES / "en.json").read_text(encoding="utf-8"))
    # B14 rule 33 — a FACT is six words or fewer; a LABEL three.
    assert len(english["integrations.gis.no_layer"].split()) <= 6
    assert len(english["integrations.gis.connection_broken"].split()) <= 6
    assert english["integrations.provider.gis_esri.operation.reconcile_parcels"] == "Parcel check"
    # Not configured and broken are two different sentences (gap 12).
    assert english["integrations.gis.not_connected"] != english["integrations.gis.connection_broken"]


# ── leftover (b) · no "Nightly" on a check nobody runs nightly ──────────────


def test_the_parcel_check_is_not_called_nightly_anywhere_on_screen():
    manifest = REGISTRY.require(gis.PROVIDER_KEY)
    operation = next(one for one in manifest.operations if one.name == "reconcile_parcels")
    assert operation.label == "Parcel check"
    assert "night" not in operation.description.lower()
    for one in sorted(LOCALES.glob("*.json")):
        catalogue = json.loads(one.read_text(encoding="utf-8"))
        word = catalogue["integrations.provider.gis_esri.operation.reconcile_parcels"]
        assert "night" not in word.lower() and "noct" not in word.lower(), (one.name, word)


# ── gap 13 · the Census geocoder can be connected and tested ────────────────


CENSUS = "https://" + census_fixtures.HOST


def test_the_census_geocoder_has_an_adapter_bound():
    assert ADAPTERS.get("geocoder_census") is CensusGeocoderAdapter
    assert REGISTRY.adapter_for("geocoder_census") is CensusGeocoderAdapter


def test_the_census_card_defaults_to_the_address_the_product_already_calls():
    manifest = REGISTRY.require("geocoder_census")
    field = next(one for one in manifest.fields if one.name == "base_url")
    assert field.default == live_calls.CENSUS_HOST == "https://geocoding.geo.census.gov"


def test_a_census_connection_can_be_made(brazos, dana):
    from core.tenancy import tenant_context

    with tenant_context(brazos.id):
        row = integration_services.connect(
            actor=dana,
            tenant_id=brazos.id,
            provider_key="geocoder_census",
            environment=models.ENVIRONMENT_PRODUCTION,
            config={"base_url": CENSUS},
            cadence=models.CADENCE_MANUAL,
        )
    assert row.provider_key == "geocoder_census"


def test_live_calls_provision_now_creates_the_census_row(brazos, dana):
    from core.tenancy import tenant_context

    with tenant_context(brazos.id):
        done = live_calls.provision(dana, brazos.id)
    assert done["geocoder_census"] == "created"


def _view(base=CENSUS):
    return ConnectionView(
        provider_key="geocoder_census", environment="production", config={"base_url": base}
    )


def test_a_census_test_geocodes_the_typed_address():
    result = CensusGeocoderAdapter().test(
        _view(), {}, recipient="4600 Silver Hill Rd, Washington, DC 20233"
    )
    assert result.ok is True
    assert result.sentence == "The geocoder answered: 1 matches."


def test_an_address_that_does_not_match_is_still_a_working_service():
    result = CensusGeocoderAdapter().test(_view(), {}, recipient="1 Nowhere Rd, Nowhere")
    assert result.ok is True
    assert result.sentence == "The geocoder answered: 0 matches."


def test_a_refusing_service_is_not_ok_and_says_so():
    result = CensusGeocoderAdapter().test(_view("https://" + census_fixtures.DOWN_HOST), {})
    assert result.ok is False
    assert result.sentence == "The geocoder refused the lookup."
    # `DEF-INT-10019` (2026-10-07) — the PO's evidence shape, `<status>, <first
    # 200 characters of the body>`; this recorded 503 has an empty body, so it is
    # the status alone. It read `HTTP 503` before that ruling.
    assert result.provider_text == "503"


def test_the_request_is_the_documented_one_line_address_call():
    assert oneline_url("https://geocoding.geo.census.gov/", "4600 Silver Hill Rd") == (
        "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"
        "?address=4600+Silver+Hill+Rd&benchmark=Public_AR_Current&format=json"
    )


def test_the_census_adapter_passes_the_conformance_kit():
    from apps.integrations import conformance

    fixture = conformance.Fixture(
        config={"base_url": CENSUS},
        good_secrets={},
        bad_secrets={},
        work=[{"ref": "P-1", "address": "4600 Silver Hill Rd, Washington, DC 20233"}],
        recipient="4600 Silver Hill Rd, Washington, DC 20233",
    )
    findings = conformance.run_kit(
        CensusGeocoderAdapter, REGISTRY.require("geocoder_census"), fixture
    )
    failed = [f"{one.case} {one.name}: {one.detail}" for one in findings if not one.ok]
    assert failed == []


# ── gap 10 · a tenant's own tile host is ADDED, nothing else moves ──────────


def test_a_tenants_own_tile_host_is_added_to_img_src_and_nothing_else_moves(brazos, dana):
    """The generated policy is ADDITIVE for a tenant's own map-tile host: it
    joins `img-src` beside everything a tenant with no City already has, and
    every other directive is byte-identical to the base."""
    from core.tenancy import tenant_context

    _connect_city(brazos, dana, config={"base_url": LAYER, "tile_url": "https://tiles.city.example"})
    with tenant_context(brazos.id):
        mine = page_policy.policy_for(brazos.id)
    parts = dict(one.strip().split(" ", 1) for one in mine.split(";"))
    base = dict(one.strip().split(" ", 1) for one in page_policy.BASE_POLICY.split(";"))
    assert "https://tiles.city.example" in parts["img-src"].split()
    for source in base["img-src"].split():
        assert source in parts["img-src"].split()
    assert {k: v for k, v in parts.items() if k != "img-src"} == {
        k: v for k, v in base.items() if k != "img-src"
    }
