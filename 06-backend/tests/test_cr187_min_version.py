# ── Trace ──────────────────────────────────────────────
# Change:   CR-187-BRC10 lane MIN-VERSION — fixes DEF-FLD-10355
# Design:   07-endpoints.md §0 rule 2 + row N7 · 15-release-and-rollback.md §5.3
# Rules:    BR-FLD-00117 (R117) · R113
# Tests:    this file (SQLite). No PostgreSQL twin: the middleware reads no
#           table and writes none — a refusal is answered before the tenant
#           is resolved.
# ───────────────────────────────────────────────────────
"""The minimum field-app version, driven through the real `/api/{tenant}/…`
paths with Django's test client, and the schema version on every field answer.

RED PROOF (law 7), recorded in the lane report: with the middleware line taken
out of `MIDDLEWARE`, every HTTP case below that expects 426 or the schema header
failed (`assert 201 == 426`, `KeyError: 'X-Field-Schema-Version'`); put back,
all pass.
"""

from __future__ import annotations

import json
import uuid

import pytest
from django.test import Client, override_settings

from core import field_app_version as fav
from core import refusal_catalogue
from tests.test_cr187_native_auth import DEVICE, PASSWORD, _bearer, field  # noqa: F401 (fixture)
from tests.test_us_idn_helpers import JSON, SC, api_path, idn  # noqa: F401 (fixture)

OLD = {"HTTP_X_FIELD_APP_VERSION": "2.580.0", "HTTP_X_FIELD_APP_BUILD": "6", "HTTP_X_FIELD_APP_PLATFORM": "android"}
NEW = {"HTTP_X_FIELD_APP_VERSION": "2.590.0", "HTTP_X_FIELD_APP_BUILD": "7", "HTTP_X_FIELD_APP_PLATFORM": "ios"}
MIN = "2.590.0"


def _sign_in(**headers):
    return Client().post(
        api_path("/auth/token"),
        data={"email": "dana@silvercreek.example", "password": PASSWORD, "device_id": DEVICE, "device_name": "Van 14"},
        content_type=JSON,
        **headers,
    )


def _body(response) -> dict:
    return json.loads(response.content)


# ── the pure parts ───────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    ("text", "parsed"),
    [("2.590.0", (2, 590, 0)), ("2.590", (2, 590, 0)), ("10.0.1-beta", (10, 0, 1)), ("", (0, 0, 0)), ("abc", (0, 0, 0)), (None, (0, 0, 0))],
)
def test_versions_are_compared_as_numbers_not_text(text, parsed):
    assert fav.parse_version(text) == parsed
    assert fav.parse_version("2.590.0") > fav.parse_version("2.59.9")  # text order would say otherwise


@pytest.mark.parametrize(
    ("path", "rest"),
    [
        ("/api/silvercreek/work/mobile/today", "work/mobile/today"),
        ("/api/silvercreek/work/mobile/routes", "work/mobile/routes"),
        ("/api/silvercreek/auth/token", "auth/token"),
        ("/api/silvercreek/auth/token/refresh", "auth/token/refresh"),
        ("/api/silvercreek/auth/activation/check", "auth/activation/check"),
        ("/api/silvercreek/auth/activation/complete", "auth/activation/complete"),
        ("/api/silvercreek/work/orders", None),
        ("/api/silvercreek/me", None),
        ("/api/silvercreek/auth/login", None),
        ("/api/exports", None),
    ],
)
def test_only_the_field_routes_are_in_scope(path, rest):
    assert fav.field_route(path) == rest


def test_the_refusal_key_resolves_to_a_sentence():
    refusal_catalogue.assert_resolves(fav.MESSAGE_KEY, raised_by="FieldAppVersionMiddleware")


def test_the_default_minimum_refuses_nothing():
    assert fav.minimum_version() == "0.0.0"


# ── through the real stack ───────────────────────────────────────────────────
@override_settings(FIELD_APP_MIN_VERSION=MIN)
def test_a_build_below_the_minimum_is_refused_426_by_name(field):
    response = _sign_in(**OLD)
    assert response.status_code == 426, response.content
    body = _body(response)
    assert set(body) == {"code", "message_key", "params", "field_errors", "br_ref", "trace_id"}  # BE-02
    assert body["code"] is None
    assert body["params"]["reason"] == "app_too_old"
    assert body["params"]["minimum"] == MIN
    assert body["params"]["version"] == "2.580.0"
    assert body["br_ref"] == "BR-FLD-00117"
    assert response["X-Field-Schema-Version"] == "1"


@override_settings(FIELD_APP_MIN_VERSION=MIN)
def test_a_build_at_the_minimum_is_served(field):
    response = _sign_in(**NEW)
    assert response.status_code == 201, response.content
    assert response["X-Field-Schema-Version"] == "1"


@override_settings(FIELD_APP_MIN_VERSION=MIN)
def test_no_header_is_never_refused(field):
    """The web field app and curl send no version; they are never refused."""
    response = _sign_in()
    assert response.status_code == 201, response.content


@override_settings(FIELD_APP_MIN_VERSION=MIN)
def test_an_old_build_is_refused_its_day_but_its_captured_work_still_lands(field):
    access = _sign_in(**NEW).json()["access_token"]
    day = Client().get(api_path("/work/mobile/today"), **_bearer(access), **OLD)
    assert day.status_code == 426 and _body(day)["params"]["reason"] == "app_too_old"

    # 07-endpoints §0 rule 2: captured work from the older build is still accepted.
    # A job id that is not this tenant's answers on its merits (404/4xx) — never 426.
    sent = Client().post(
        api_path(f"/work/mobile/jobs/{uuid.uuid4()}/sync"),
        data={"items": []}, content_type=JSON, **_bearer(access), **OLD,
    )
    assert sent.status_code != 426, sent.content
    assert sent["X-Field-Schema-Version"] == "1"
    reads = Client().post(api_path("/work/mobile/reads/sync"), data={"items": []}, content_type=JSON, **_bearer(access), **OLD)
    assert reads.status_code != 426, reads.content


@override_settings(FIELD_APP_MIN_VERSION=MIN)
def test_the_web_staff_routes_are_untouched(field):
    response = Client().get(api_path("/me"), **OLD)
    assert response.status_code != 426
    assert "X-Field-Schema-Version" not in response


def test_with_the_default_minimum_an_old_build_is_served(field):
    response = _sign_in(**OLD)
    assert response.status_code == 201, response.content


def test_every_field_answer_carries_the_schema_version_even_a_refusal(field):
    response = Client().get(api_path("/work/mobile/today"))  # no credential → refused
    assert response.status_code in (401, 403)
    assert response["X-Field-Schema-Version"] == "1"


def test_the_sends_list_names_only_routes_that_exist():
    """A pattern that matches no real route is a guard over nothing (law 7)."""
    from django.urls import get_resolver

    routes: list[str] = []

    def walk(patterns, prefix=""):
        for p in patterns:
            if hasattr(p, "url_patterns"):
                walk(p.url_patterns, prefix + str(p.pattern))
            else:
                routes.append(prefix + str(p.pattern))

    walk(get_resolver().url_patterns)
    tenant_prefix = "^api/[-a-zA-Z0-9_]+/"
    rests = []
    for route in routes:
        if not route.startswith(tenant_prefix):
            continue
        rest = route[len(tenant_prefix):]
        for name in ("order_id", "photo_id", "route_id"):
            rest = rest.replace(f"<uuid:{name}>", str(uuid.uuid4()))
        rests.append(rest)
    assert len(rests) > 100, f"read only {len(rests)} tenant routes"
    for method, pattern in fav.SENDS_CAPTURED_WORK:
        assert any(pattern.match(r) for r in rests), f"{method} {pattern.pattern} matches no route"
