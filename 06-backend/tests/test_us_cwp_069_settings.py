# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-069 (EP-CWP-12) — portal settings: the address, the switch
#           and the five. Screens: CWP-069
# Rules:    BR-CWP-007 · CR-068 R8 · hard-won law 3 · A4 settings_lookups ·
#           CLAUDE.md hard rule 7 (audit)
# Tests:    this file — TC-1 (address + QR), TC-2 (no second column), TC-3
#           (defaults), TC-4 (self-read off → nothing offers it), TC-5 (off →
#           holding; no notification row changes), TC-6 (the counts the
#           product can count), TC-7 (readings off is a reason, not a zero),
#           TC-8 (isolation), TC-9 (a clerk is refused), TC-10 is a link on
#           the screen (SettingsCustomerPortalTab.test.tsx)
# Impacts:  apps/portal/backoffice_api.py · settings_service.py · selectors.py
# ───────────────────────────────────────────────────────
"""US-CWP-069 — `GET/PUT /settings/portal` and `GET /settings/portal/qr.svg`."""

import pytest
from django.urls import resolve

from apps.notifications import models as notifications_models
from apps.portal import backoffice_api, guest_api, models, qr
from core import errors
from tests.test_us_cwp_helpers import *  # noqa: F401,F403
from tests.test_us_cwp_helpers import switch_on
from tests.test_us_ten_helpers import api_call


def _get(tenant, actor, role="system_admin"):
    return api_call(
        backoffice_api.portal_settings,
        "get",
        f"/api/{tenant.subdomain}/settings/portal",
        user=actor.user,
        role=role,
        tenant=tenant,
    )


def _put(tenant, actor, data, role="system_admin"):
    return api_call(
        backoffice_api.portal_settings,
        "put",
        f"/api/{tenant.subdomain}/settings/portal",
        user=actor.user,
        role=role,
        tenant=tenant,
        data=data,
    )


@pytest.mark.django_db
def test_us_cwp_069_tc1_the_address_is_the_slug_as_a_path_and_a_qr_code_encodes_it(pine_hill, sarah, settings):
    settings.PUBLIC_APP_ORIGIN = "https://app.bynry.com"
    body = _get(pine_hill, sarah).data
    assert body["address"]["slug"] == "pine-hill"
    assert body["address"]["path"] == "/pine-hill/portal"
    # The host is the environment's PUBLIC_APP_ORIGIN, never the one the request
    # arrived on (DEF-CWP-9717). This line asserted `http://testserver/…` — the
    # request's own host — until 2026-10-05, which is the defect written as a
    # test: on one host the two are the same string, so it could never go red.
    assert body["address"]["url"] == "https://app.bynry.com/pine-hill/portal"
    svg = api_call(
        backoffice_api.portal_qr,
        "get",
        f"/api/{pine_hill.subdomain}/settings/portal/qr.svg",
        user=sarah.user,
        role="system_admin",
        tenant=pine_hill,
    )
    assert svg.status_code == 200
    assert svg["Content-Type"].startswith("image/svg+xml")
    assert b"<svg" in svg.content
    # ⚠ **THE NAMESPACE IS THE WHOLE TEST — `DEF-CWP-3720`.** Everything above
    # this line was TRUE of a body no browser could draw. `segno.svg_inline()`
    # is built for pasting INTO an HTML document, where the surrounding HTML
    # parser supplies the SVG namespace, so it emits none of its own. Served as
    # its own `image/svg+xml` document and loaded through `<img src>`, the
    # browser parses it as XML, finds `<svg>` in no namespace, and draws
    # nothing: the Settings screen showed a broken-image icon and its alt text
    # from the day this shipped, with a 200, the right content type and the
    # address present in the body. The one byte string that decides whether the
    # picture appears is this one.
    assert qr.SVG_NAMESPACE.encode() in svg.content
    assert svg.content.lstrip().startswith(b"<?xml")
    # And it really encodes the address a customer would type, not the slug.
    assert b"<path" in svg.content
    download = api_call(
        backoffice_api.portal_qr,
        "get",
        f"/api/{pine_hill.subdomain}/settings/portal/qr.svg",
        user=sarah.user,
        role="system_admin",
        tenant=pine_hill,
        query={"download": "1"},
    )
    assert download["Content-Disposition"] == 'attachment; filename="pine-hill-portal-qr.svg"'


def test_us_cwp_069_tc2_the_address_is_stored_once_on_the_tenant_and_nowhere_here():
    names = {field.name for field in models.PortalSettings._meta.get_fields()}
    for forbidden in ("subdomain", "address", "slug", "url", "portal_address"):
        assert forbidden not in names, forbidden
    # And the branding four are not here either (US-CWP-070 TC-2's other half).
    for forbidden in ("logo", "logo_bytes", "brand_primary_hex", "brand_accent_hex", "dba_name"):
        assert forbidden not in names, forbidden


@pytest.mark.django_db
def test_us_cwp_069_tc3_a_brand_new_tenant_is_off_with_self_read_the_one_switch_off(pine_hill, sarah):
    body = _get(pine_hill, sarah).data
    assert models.PortalSettings.objects.filter(tenant=pine_hill).exists() is False  # a read never writes
    assert body["is_live"] is False
    assert body["switches"] == {
        "quick_pay_enabled": True,
        "self_read_enabled": False,
        "plans_enabled": True,
        "requests_enabled": True,
        "outage_reporting_enabled": True,
    }


@pytest.mark.django_db
def test_us_cwp_069_tc4_self_read_off_reaches_the_guest_payload_and_the_other_switches_stand(pine_hill, sarah):
    switch_on(pine_hill, sarah, self_read_enabled=True)
    _put(pine_hill, sarah, {"self_read_enabled": False})
    front = api_call(guest_api.front, "get", f"/api/{pine_hill.subdomain}/portal/public/front", tenant=pine_hill).data
    assert front["switches"]["self_read_enabled"] is False
    assert front["switches"]["quick_pay_enabled"] is True
    # ⚠ **SELF-READ IS THE ONE SWITCH WITH NO CARD**, so turning it off must
    # move nothing on the front page. Since 2026-09-05 all six cards are sent
    # (PO: *"for completess have them on screen"*), so "nothing moved" is now
    # checked as *the same four are usable*, not as *the same four exist*.
    usable = [card["key"] for card in front["cards"] if card["available"]]
    assert usable == ["pay_bill", "report_problem", "start_service", "what_things_cost"]
    assert len(front["cards"]) == 6
    # The endpoint half — CWP-035's route refusing — is wave J's, with the
    # route itself; asserted absent today so its arrival rewrites this case.
    from django.urls import Resolver404

    with pytest.raises(Resolver404):
        resolve(f"/api/{pine_hill.subdomain}/portal/readings")


@pytest.mark.django_db
def test_us_cwp_069_tc5_turning_the_portal_off_shows_the_holding_page_and_moves_no_notification(pine_hill, sarah, audit_rows):
    switch_on(pine_hill, sarah)
    before = notifications_models.OutboundMessage.objects.count()
    body = _put(pine_hill, sarah, {"is_live": False}).data
    assert body["is_live"] is False
    front = api_call(guest_api.front, "get", f"/api/{pine_hill.subdomain}/portal/public/front", tenant=pine_hill).data
    assert front["is_live"] is False and front["cards"] == []
    assert notifications_models.OutboundMessage.objects.count() == before
    # Hard rule 7: the switch is an action a customer feels, so it is audited,
    # with exactly the field that moved.
    row = [one for one in audit_rows if one["action"] == "portal_settings.update" and "is_live" in one["after"]][-1]
    assert row["before"] == {"is_live": True} and row["after"] == {"is_live": False}
    assert row["entity_type"] == "portal_settings"


@pytest.mark.django_db
def test_us_cwp_069_tc6_the_counts_are_the_ones_the_product_can_count_today(pine_hill, sarah):
    switch_on(pine_hill, sarah)
    body = _get(pine_hill, sarah).data
    by_key = {row["key"]: row for row in body["usage"]}
    # A real zero over service_requests carrying the portal channel.
    assert by_key["requests_from_portal"] == {"key": "requests_from_portal", "count": 0, "reason": None}
    # The story's §4 figures (412 of 1,180 enrolled · 268 signed in) count rows
    # in tables wave E creates; until then those rows are ABSENT, not zero.
    assert "customers_enrolled" not in by_key and "signed_in_this_month" not in by_key


@pytest.mark.django_db
def test_us_cwp_069_tc7_readings_off_is_a_reason_and_never_a_zero(pine_hill, sarah):
    switch_on(pine_hill, sarah)  # self-read stays OFF (R8)
    body = _get(pine_hill, sarah).data
    readings = next(row for row in body["usage"] if row["key"] == "readings_sent_in")
    assert readings["count"] is None and readings["reason"] == "readings_off"
    # Switch it on: with no reading path yet (wave J) the row is absent rather
    # than a zero that would read as nobody using it.
    _put(pine_hill, sarah, {"self_read_enabled": True})
    keys = [row["key"] for row in _get(pine_hill, sarah).data["usage"]]
    assert "readings_sent_in" not in keys


@pytest.mark.django_db
def test_us_cwp_069_tc8_an_oak_ridge_admin_reads_oak_ridges_address_and_switches(pine_hill, sarah, oak_ridge, elena):
    switch_on(pine_hill, sarah, quick_pay_enabled=False)
    body = _get(oak_ridge, elena).data
    assert body["address"]["path"] == "/oak-ridge/portal"
    assert body["is_live"] is False and body["switches"]["quick_pay_enabled"] is True
    assert "pine-hill" not in str(body)


@pytest.mark.django_db
def test_us_cwp_069_tc9_a_billing_clerk_is_refused_and_an_executive_may_only_read(pine_hill, pine_clerk, pine_exec):
    assert _get(pine_hill, pine_clerk, role="billing_clerk").status_code == 403
    assert _put(pine_hill, pine_clerk, {"is_live": True}, role="billing_clerk").status_code == 403
    assert _get(pine_hill, pine_exec, role="executive").status_code == 200
    assert _put(pine_hill, pine_exec, {"is_live": True}, role="executive").status_code == 403
    assert models.PortalSettings.objects.filter(tenant=pine_hill).exists() is False


@pytest.mark.django_db
def test_us_cwp_069_a_switch_must_be_a_boolean_and_an_unknown_key_is_refused_by_name(pine_hill, sarah):
    refused = _put(pine_hill, sarah, {"is_live": "yes"})
    assert refused.status_code == errors.HTTP_STATUS_BY_CODE[errors.VAL_FORMAT]
    assert refused.data["field_errors"][0]["message_key"] == "portal.settings.switch_not_boolean"
    smuggled = _put(pine_hill, sarah, {"is_live": True, "strapline": "through the wrong door"})
    assert smuggled.data["field_errors"][0] ["field"] == "strapline"
    assert smuggled.data["field_errors"][0]["message_key"] == "portal.settings.unknown_field"
    assert models.PortalSettings.objects.filter(tenant=pine_hill).exists() is False  # nothing partial


@pytest.mark.django_db
def test_us_cwp_069_the_back_office_routes_live_in_the_portal_module(pine_hill):
    assert resolve(f"/api/{pine_hill.subdomain}/settings/portal").func is backoffice_api.portal_settings
    assert resolve(f"/api/{pine_hill.subdomain}/settings/portal/branding").func is backoffice_api.portal_branding
    assert resolve(f"/api/{pine_hill.subdomain}/settings/portal/qr.svg").func is backoffice_api.portal_qr
