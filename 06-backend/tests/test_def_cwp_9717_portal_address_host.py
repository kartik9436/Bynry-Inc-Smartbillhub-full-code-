# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-CWP-9717 — Settings › Configure › Customer portal › Overview
#           showed *Your portal address* on the API's host.
# Rules:    PO ruling 2026-10-05 (decision log, "THE CUSTOMER PORTAL'S ADDRESS
#           COMES FROM A SETTING PER ENVIRONMENT"), verbatim: *"(a) A setting
#           per environment: each host names its public address, for example
#           https://app-sand.bynry.com. The address is always the same, whoever
#           opens the page."* · CLAUDE.md hard-won law 3 (defaults fail closed)
# Code:     core/public_origin.py · apps/portal/backoffice_api.py
# ───────────────────────────────────────────────────────
"""The portal address is `PUBLIC_APP_ORIGIN` + `/{slug}/portal`, never the host
the API was called on.

Every request below arrives on the API's own host, which is what a browser on a
two-host deployment does since `CR-144-BRC07`. Before the fix the address read
`https://api-smart360-sandbox.bynry.com/pine-hill/portal` — the host the call
arrived on — and the QR code encoded the same wrong address.
"""

import pytest

from apps.portal import backoffice_api, qr
from core import public_origin
from tests.test_us_cwp_helpers import *  # noqa: F401,F403
from tests.test_us_ten_helpers import api_call

API_HOST = "api-smart360-sandbox.bynry.com"
APP_ORIGIN = "https://app-sand.bynry.com"


def _get(tenant, actor):
    return api_call(
        backoffice_api.portal_settings,
        "get",
        f"/api/{tenant.subdomain}/settings/portal",
        user=actor.user,
        role="system_admin",
        tenant=tenant,
        headers={"Host": API_HOST},
    )


def _qr(tenant, actor, monkeypatch):
    encoded: list[str] = []
    real = qr.portal_qr_svg

    def spy(url, **kwargs):
        encoded.append(url)
        return real(url, **kwargs)

    monkeypatch.setattr(qr, "portal_qr_svg", spy)
    response = api_call(
        backoffice_api.portal_qr,
        "get",
        f"/api/{tenant.subdomain}/settings/portal/qr.svg",
        user=actor.user,
        role="system_admin",
        tenant=tenant,
        headers={"Host": API_HOST},
    )
    return response, encoded


@pytest.mark.django_db
def test_the_address_is_the_public_app_host_whatever_host_the_api_was_called_on(
    pine_hill, sarah, settings
):
    settings.PUBLIC_APP_ORIGIN = APP_ORIGIN
    settings.ALLOWED_HOSTS = [API_HOST]
    address = _get(pine_hill, sarah).data["address"]
    assert address["url"] == "https://app-sand.bynry.com/pine-hill/portal"
    assert API_HOST not in address["url"]


@pytest.mark.django_db
def test_the_qr_code_encodes_the_public_app_address(pine_hill, sarah, settings, monkeypatch):
    settings.PUBLIC_APP_ORIGIN = APP_ORIGIN
    settings.ALLOWED_HOSTS = [API_HOST]
    response, encoded = _qr(pine_hill, sarah, monkeypatch)
    assert response.status_code == 200
    assert encoded == ["https://app-sand.bynry.com/pine-hill/portal"]


@pytest.mark.django_db
def test_unset_the_address_is_absent_and_the_qr_code_is_refused_never_the_api_host(
    pine_hill, sarah, settings, monkeypatch
):
    # Law 3: a host that forgets the setting shows no address it would have to
    # guess, and draws no QR code a customer could scan to the wrong place.
    settings.PUBLIC_APP_ORIGIN = ""
    settings.ALLOWED_HOSTS = [API_HOST]
    assert _get(pine_hill, sarah).data["address"]["url"] is None
    response, encoded = _qr(pine_hill, sarah, monkeypatch)
    assert response.status_code == 500
    assert encoded == []


@pytest.mark.parametrize(
    "value",
    [
        "app-sand.bynry.com",  # no scheme
        "https://app-sand.bynry.com/",  # trailing slash
        "https://app-sand.bynry.com/portal",  # a path
        "https://*.bynry.com",  # a wildcard
        "ftp://app-sand.bynry.com",  # not a web scheme
        "https://app-sand.bynry.com?x=1",  # a query
        "https://user@app-sand.bynry.com",  # credentials
    ],
)
def test_a_malformed_value_is_treated_as_unset(settings, value):
    settings.PUBLIC_APP_ORIGIN = value
    assert public_origin.public_app_origin() is None


@pytest.mark.parametrize(
    "value",
    ["https://app-sand.bynry.com", "https://app.bynry.com", "http://localhost:5173", "http://127.0.0.1:5715"],
)
def test_a_bare_origin_is_accepted_as_written(settings, value):
    settings.PUBLIC_APP_ORIGIN = value
    assert public_origin.public_app_origin() == value
