# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-INT-10019 (PO report 2026-10-07 — Ann Arbor's Cloudflare answered
#           403 "error code: 1010" to Python's default urllib agent)
# Ruling:   decision log 2026-10-07, the SMARTBillHub-GIS User-Agent ruling
# Rules:    BR-INT-022 (the breaker counts SILENCE, never an answer) ·
#           B14 rule 33 (a fact is six words or fewer)
# Impacts:  core/gis_http.py · apps/integrations/gis_layer.py ·
#           adapters/gis_city.py · adapters/geocoder_census.py ·
#           apps/metering/geocode.py · gis.py · gis_parcels.py · gis_fixtures.py
# ───────────────────────────────────────────────────────
"""Every map or address request names us; a firewall's 403 is not our key.

**RED BEFORE, at 2.561.3 with these exact cases:** a Cloudflare `403` with the
body `error code: 1010` classified as `key` (the clerk read *"The city rejected
our key"* on a connection holding none); a *Just a moment…* page the same; the
three transports built no `Request` at all (bare `urlopen(url)`, so Python's
`Python-urllib/3.x` went out); the run row's `provider_error` was empty.

⚠ **THE HEADER IS PROVED ON THE REQUEST OBJECT EACH TRANSPORT HANDS TO
`urlopen`**, captured by replacing `urlopen` for the length of one test. That is
the only place a header can be seen without dialling anything — every other test
in this repo injects a whole fake transport, which is exactly why nothing ever
looked at what the real one sent.
"""

from __future__ import annotations

import ast
import io
import json
import urllib.error
from pathlib import Path

import pytest

from apps.integrations import gis, gis_fixtures, gis_layer, gis_parcels, models, runtime
from apps.integrations import api as integrations_api
from apps.integrations import services as integration_services
from apps.integrations.adapters.base import ConnectionView
from apps.integrations.adapters.geocoder_census import CensusGeocoderAdapter
from apps.integrations.adapters.gis_city import CityRefused, GisCityAdapter
from core import diagnostics, gis_http
from core.permissions import SYSTEM_ADMIN
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana
from tests.test_us_ten_helpers import api_call

BACKEND = Path(__file__).resolve().parents[1]
FIREWALL_KEY = "integrations.gis.city_firewall_blocked"
KEY = "integrations.gis.city_rejected_key"
MOVED = "integrations.gis.city_layer_moved"

CLOUDFLARE_1010 = "error code: 1010"
CHALLENGE_PAGE = (
    "<!DOCTYPE html><html lang=\"en-US\"><head><title>Just a moment...</title>"
    "</head><body><noscript>Enable JavaScript and cookies to continue</noscript></body></html>"
)
ARCGIS_403 = json.dumps({"error": {"code": 403, "message": "You do not have permissions to access this resource or perform this operation.", "details": []}})


def _http_error(status: int, body: str) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(
        "https://gis.a2gov.example/q", status, "refused", {}, io.BytesIO(body.encode("utf-8"))
    )


# ── 1 · the header, exactly, from the one function ──────────────────────────


def test_the_user_agent_is_our_name_our_version_and_our_address():
    expected = f"SMARTBillHub-GIS/{diagnostics.release()} (support@bynry.io)"
    assert gis_http.user_agent() == expected
    # The version is the product's, read — never a literal, never a browser.
    assert diagnostics.release() and diagnostics.release() != "unknown"
    assert "Mozilla" not in expected and "Chrome" not in expected


class _Captured:
    def __init__(self) -> None:
        self.requests: list = []

    def __call__(self, request, timeout=None):  # urlopen's shape
        self.requests.append(request)

        class _Answer(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        return _Answer(b'{"features": [], "result": {"addressMatches": []}}')


def _transports():
    from apps.integrations.adapters import geocoder_census, gis_city
    from apps.metering import geocode

    return [
        ("gis_city", lambda: gis_city._urllib_transport("https://gis.a2gov.example/q?f=json", 5.0)),
        ("gis_layer", lambda: gis_layer._urllib_transport("https://gis.a2gov.example/0?f=json", 5.0)),
        ("geocoder_census", lambda: geocoder_census._urllib_transport("https://geocoding.geo.census.example/x", 5.0)),
        ("metering.geocode", lambda: geocode._urllib_transport("https://geocoding.geo.census.example/x")),
    ]


@pytest.mark.parametrize("name,call", _transports(), ids=[one[0] for one in _transports()])
def test_every_transport_sends_the_exact_header(monkeypatch, name, call):
    import urllib.request

    captured = _Captured()
    monkeypatch.setattr(urllib.request, "urlopen", captured)
    call()
    assert len(captured.requests) == 1, f"{name} did not dial through urlopen once"
    request = captured.requests[0]
    assert isinstance(request, urllib.request.Request), (
        f"{name} handed urlopen a bare URL — Python's default agent goes out"
    )
    assert request.get_header("User-agent") == (
        f"SMARTBillHub-GIS/{diagnostics.release()} (support@bynry.io)"
    )


#: The GIS and geocoder paths. A file here may not call `urlopen` itself.
GIS_PATHS = [
    "apps/integrations/gis.py",
    "apps/integrations/gis_layer.py",
    "apps/integrations/gis_parcels.py",
    "apps/integrations/gis_search.py",
    "apps/integrations/gis_match.py",
    "apps/integrations/adapters/gis_city.py",
    "apps/integrations/adapters/geocoder_census.py",
    "apps/metering/geocode.py",
]


def _calls_urlopen(path: Path) -> list[int]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    lines = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
            if name == "urlopen":
                lines.append(node.lineno)
    return lines


def test_no_file_on_the_gis_paths_calls_urlopen_itself():
    """A fourth fetcher goes RED here instead of going round the header.

    Scope is printed with the verdict (law 7: a check that cannot cover its
    whole subject says what it looked at): every `gis*.py` in integrations, the
    two adapters, and the metering geocoder.
    """
    scope = sorted(
        {*(BACKEND / p for p in GIS_PATHS), *(BACKEND / "apps/integrations").glob("gis*.py")}
    )
    scope = [p for p in scope if p.exists() and not p.name.endswith("_fixtures.py")]
    assert len(scope) >= 8, [str(p) for p in scope]
    offenders = {str(p.relative_to(BACKEND)): _calls_urlopen(p) for p in scope}
    offenders = {k: v for k, v in offenders.items() if v}
    assert offenders == {}, f"call core.gis_http.fetch_json instead: {offenders} (checked {len(scope)} files)"
    # And the one function really is the one place.
    assert _calls_urlopen(BACKEND / "core/gis_http.py") != []


# ── 2 · the classifier reads the body as well as the status ─────────────────


@pytest.mark.parametrize(
    "status,body,expected",
    [
        (403, CLOUDFLARE_1010, "firewall"),
        (403, CHALLENGE_PAGE, "firewall"),
        (403, "", "firewall"),
        (403, ARCGIS_403, gis_layer.REFUSED_KEY),
        (401, CLOUDFLARE_1010, gis_layer.REFUSED_KEY),
        (498, "", gis_layer.REFUSED_KEY),
        (499, "", gis_layer.REFUSED_KEY),
        (404, "<html>Not Found</html>", gis_layer.REFUSED_MOVED),
        (400, "", gis_layer.REFUSED_MOVED),
        (410, "", gis_layer.REFUSED_MOVED),
        (503, "", gis_layer.REFUSED_ERROR),
    ],
)
def test_the_body_says_who_refused(status, body, expected):
    assert gis_layer.refusal_reason(status, body) == expected


def test_a_code_with_no_body_keeps_todays_reading():
    """An ArcGIS `{"error": {"code": 403}}` arrives as a CODE with no body to
    read; that is ArcGIS's own voice and stays *key*."""
    assert gis_layer.refusal_reason(403) == gis_layer.REFUSED_KEY


def test_the_adapter_reads_the_body_of_a_cloudflare_403():
    def cloudflare(url, timeout_s):
        raise _http_error(403, CLOUDFLARE_1010)

    adapter = GisCityAdapter(transport=cloudflare)
    view = ConnectionView(
        provider_key=gis.PROVIDER_KEY,
        environment="production",
        config={"base_url": "https://gis.a2gov.example/arcgis/rest/services/Q/FeatureServer/0"},
    )
    with pytest.raises(CityRefused) as refused:
        adapter.search(view, {}, "2670 Sequoia", timeout_s=1.0)
    assert refused.value.reason == "firewall"
    assert refused.value.evidence == "403, error code: 1010"


def test_the_layer_walk_reads_the_body_too():
    def cloudflare(url, timeout_s):
        raise _http_error(403, CHALLENGE_PAGE)

    layer = gis_parcels.config_from_connection(
        {"base_url": "https://gis.a2gov.example/arcgis/rest/services/Q/FeatureServer/0"}
    )
    with pytest.raises(gis_layer.LayerRefused) as refused:
        gis_layer.walk(layer, transport=cloudflare)
    assert refused.value.reason == "firewall"
    assert refused.value.evidence.startswith("403, <!DOCTYPE html>")
    assert len(refused.value.evidence) <= len("403, ") + 200


def test_the_census_refusal_names_the_firewall_and_keeps_the_body():
    def cloudflare(url, timeout_s):
        raise _http_error(403, CLOUDFLARE_1010)

    view = ConnectionView(
        provider_key="geocoder_census",
        environment="production",
        config={"base_url": "https://geocoding.geo.census.gov"},
    )
    result = CensusGeocoderAdapter(transport=cloudflare).test(view, {})
    assert result.ok is False
    assert result.sentence == "The geocoder's firewall blocked us."
    assert result.provider_text == "403, error code: 1010"


def test_firewall_has_a_key_and_a_six_word_sentence_in_all_eleven_catalogues():
    assert gis_parcels.REFUSAL_KEYS["firewall"] == FIREWALL_KEY
    assert gis_parcels.REFUSAL_HEADLINES["firewall"] == "The city's firewall blocked us."
    locales = BACKEND.parent / "07-frontend" / "src" / "i18n" / "locales"
    files = sorted(locales.glob("*.json"))
    assert len(files) == 11, [one.name for one in files]
    english = json.loads((locales / "en.json").read_text(encoding="utf-8"))[FIREWALL_KEY]
    assert english == "The city's firewall blocked us."
    for one in files:
        said = json.loads(one.read_text(encoding="utf-8")).get(FIREWALL_KEY)
        assert said, f"{one.name} has no {FIREWALL_KEY}"
        if one.name != "en.json":
            assert said != english, f"{one.name} is English, not its own language (B14 rule 35)"


# ── 3 · through the real service: the amber box, the run row, the breaker ──


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


def _latest_run(tenant, connection):
    from core.tenancy import tenant_context

    with tenant_context(tenant.id):
        return (
            models.IntegrationRun.objects.filter(connection=connection)
            .order_by("-started_at")
            .first()
        )


def _breaker_count(connection) -> int:
    from core.tenancy import tenant_context

    with tenant_context(connection.tenant_id):
        connection.refresh_from_db()
    return int((dict(connection.config or {}).get("breaker") or {}).get("consecutive_timeouts") or 0)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "host,expected,evidence",
    [
        ("firewall.gis.brazosbend.example", FIREWALL_KEY, "403, error code: 1010"),
        ("challenge.gis.brazosbend.example", FIREWALL_KEY, "403, <!DOCTYPE html>"),
        ("forbidden.gis.brazosbend.example", KEY, '403, {"error":'),
        (gis_fixtures.KEY_REFUSED_HOST, KEY, "401"),
        (gis_fixtures.MOVED_HOST, MOVED, "404"),
    ],
)
def test_the_address_search_amber_box_and_its_run_row(brazos, dana, host, expected, evidence):
    from core.tenancy import tenant_context

    connection = _connect(brazos, dana, host)
    with tenant_context(brazos.id):
        answer = gis.search(brazos.id, query="2670 Sequoia")
    assert answer["reachable"] is False
    assert answer["message_key"] == expected
    run = _latest_run(brazos, connection)
    assert run is not None and run.finished_at is not None
    assert (run.provider_error or "").startswith(evidence), run.provider_error
    # BR-INT-022 — a refusal is an answer, not silence.
    assert _breaker_count(connection) == 0


@pytest.mark.django_db
def test_the_run_row_reads_exactly_403_error_code_1010(brazos, dana):
    from core.tenancy import tenant_context

    connection = _connect(brazos, dana, "firewall.gis.brazosbend.example")
    with tenant_context(brazos.id):
        for _ in range(4):
            gis.search(brazos.id, query="2670 Sequoia")
    assert _latest_run(brazos, connection).provider_error == "403, error code: 1010"
    assert _breaker_count(connection) == 0


@pytest.mark.django_db
def test_the_parcel_check_preview_names_the_firewall_and_keeps_the_body(brazos, dana):
    connection = _connect(
        brazos, dana, "firewall.gis.brazosbend.example",
        path="/arcgis/rest/services/Qualified/FeatureServer/0",
    )
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
    assert response.data["stop_reason_key"] == FIREWALL_KEY
    assert _latest_run(brazos, connection).provider_error == "403, error code: 1010"
    assert _breaker_count(connection) == 0


def test_the_scrub_keeps_a_providers_error_code_and_nothing_else():
    """`1010` is four digits, so the account rule masked it and the run row read
    `403, error code: ••••`. Only digits right after *error code* survive."""
    from apps.integrations.scrubbing import scrub

    assert scrub("403, error code: 1010") == "403, error code: 1010"
    assert scrub("403, Error Code 1020") == "403, Error Code 1020"
    assert scrub("error code: 1010 for account 44710021") == "error code: 1010 for account ••••"
    assert scrub("account 4471 refused") == "account •••• refused"
