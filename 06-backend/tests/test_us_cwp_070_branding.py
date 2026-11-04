# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-070 (EP-CWP-12) — branding read from Company → Profile and
#           stored nowhere twice. Screens: CWP-070
# Rules:    blueprint B2 (the shared four are read-only here) · US-CWP-070
#           TC-5 (a service the tenant does not sell is refused) · B14 rule 32
# Tests:    this file — TC-1 (read-only four), TC-2 (a logo is refused and no
#           column could hold one), TC-3 (strapline reaches CWP-001), TC-4
#           (a ticked service is a chip), TC-5 (a foreign service is refused),
#           TC-6 (a colour changed in Company → Profile follows at once),
#           TC-7 (isolation), TC-8 (reset clears the portal-only four only)
# Impacts:  apps/portal/backoffice_api.py · settings_service.py · selectors.py
# ───────────────────────────────────────────────────────
"""US-CWP-070 — `GET/PUT /settings/portal/branding`."""

from types import SimpleNamespace

import pytest

from apps.portal import backoffice_api, guest_api, models, sample_data
from apps.portal.seams import tenancy_seam
from apps.tenancy import services as tenancy_services
from core import errors
from core.permissions import SYSTEM_ADMIN
from core.tenancy import tenant_context
from tests.test_us_cwp_helpers import *  # noqa: F401,F403
from tests.test_us_cwp_helpers import brand_fully, switch_on
from tests.test_us_ten_helpers import api_call


def _get(tenant, actor):
    return api_call(
        backoffice_api.portal_branding,
        "get",
        f"/api/{tenant.subdomain}/settings/portal/branding",
        user=actor.user,
        role="system_admin",
        tenant=tenant,
    )


def _put(tenant, actor, data):
    return api_call(
        backoffice_api.portal_branding,
        "put",
        f"/api/{tenant.subdomain}/settings/portal/branding",
        user=actor.user,
        role="system_admin",
        tenant=tenant,
        data=data,
    )


def _front(tenant):
    return api_call(guest_api.front, "get", f"/api/{tenant.subdomain}/portal/public/front", tenant=tenant).data


def _service_ids(tenant):
    with tenant_context(tenant.id):
        return {row["code"]: row["id"] for row in tenancy_seam.enabled_services(tenant.id)}


@pytest.mark.django_db
def test_us_cwp_070_tc1_the_shared_four_are_read_from_the_tenant_with_their_one_home(pine_hill, sarah):
    body = _get(pine_hill, sarah).data
    assert body["shared"]["trading_name"] == "Pine Hill Water & Power"
    assert body["shared"]["brand_primary_hex"] == "#EC3013"
    assert body["shared"]["brand_accent_hex"] == "#E15B47"
    assert body["shared"]["edited_at"] == "/settings/company"
    assert body["shared"]["has_logo"] is False and body["shared"]["mark"]["letters"]
    assert set(body["portal_only"]) == set(models.BRANDING_FIELDS)
    # The PICK LIST is a staff list and follows the platform catalogue's own
    # order (the same order Settings → Services draws); the tick order is the
    # FRONT PAGE's (TC-4).
    from apps.tenancy import models as tenancy_models

    catalogue = [
        row.code
        for row in tenancy_models.Service.objects.filter(
            code__in=["water", "sewer", "trash", "electric"]
        ).order_by("sort", "code")
    ]
    assert [row["code"] for row in body["services"]] == catalogue


@pytest.mark.django_db
def test_us_cwp_070_tc2_a_logo_or_a_colour_sent_here_is_refused_and_no_column_could_hold_it(pine_hill, sarah):
    for smuggled in ({"logo": "data:image/png;base64,AAAA"}, {"brand_primary_hex": "#000000"}, {"dba_name": "Two Logos Ltd"}):
        refused = _put(pine_hill, sarah, {"strapline": "fine", **smuggled})
        assert refused.status_code == errors.HTTP_STATUS_BY_CODE[errors.VAL_FORMAT]
        [error] = refused.data["field_errors"]
        assert error["field"] == next(iter(smuggled))
        assert error["message_key"] == "portal.branding.shared_field_refused"
    assert models.PortalSettings.objects.filter(tenant=pine_hill).exists() is False
    names = {field.name for field in models.PortalSettings._meta.get_fields()}
    assert not any(name.startswith("logo") for name in names)


@pytest.mark.django_db
def test_us_cwp_070_tc3_the_strapline_reaches_the_front_page(pine_hill, sarah):
    switch_on(pine_hill, sarah)
    body = _put(pine_hill, sarah, {"strapline": "  Your account, your bills — any time.  "}).data
    assert body["portal_only"]["strapline"] == "Your account, your bills — any time."
    assert body["preview"]["strapline"] == "Your account, your bills — any time."
    assert _front(pine_hill)["strapline"] == "Your account, your bills — any time."
    # B14 rule 32 made a number: more than one sentence's worth is refused.
    too_long = _put(pine_hill, sarah, {"strapline": "x" * (models.STRAPLINE_MAX_CHARS + 1)})
    assert too_long.data["field_errors"][0]["message_key"] == "portal.branding.strapline_too_long"
    assert too_long.data["field_errors"][0]["params"]["max"] == models.STRAPLINE_MAX_CHARS


@pytest.mark.django_db
def test_us_cwp_070_tc4_a_ticked_service_becomes_a_chip_in_the_order_listed(pine_hill, sarah):
    switch_on(pine_hill, sarah)
    ids = _service_ids(pine_hill)
    _put(pine_hill, sarah, {"front_page_service_ids": [ids["electric"], ids["water"]]})
    chips = _front(pine_hill)["services"]
    # The wireframe's *Water · Sewer · Trash · Electric* is the utility's own
    # order, so the stored list IS the order — not the catalogue's, not A–Z.
    assert [chip["code"] for chip in chips] == ["electric", "water"]
    assert all(set(chip) == {"code", "name", "color"} for chip in chips)  # rule 31: no id to a guest


@pytest.mark.django_db
def test_us_cwp_070_tc5_a_service_the_tenant_does_not_sell_is_not_offered_and_is_refused(pine_hill, sarah, oak_ridge):
    offered = {row["code"] for row in _get(pine_hill, sarah).data["services"]}
    assert "gas" not in offered and "fire" not in offered
    # A platform service id the tenant has not enabled — gas — is refused.
    from apps.tenancy import models as tenancy_models

    gas = tenancy_models.Service.objects.get(code="gas")
    refused = _put(pine_hill, sarah, {"front_page_service_ids": [str(gas.id)]})
    assert refused.data["field_errors"][0]["message_key"] == "portal.branding.service_not_sold"
    not_a_list = _put(pine_hill, sarah, {"front_page_service_ids": "water"})
    assert not_a_list.data["field_errors"][0]["message_key"] == "portal.branding.services_not_list"


@pytest.mark.django_db
def test_us_cwp_070_tc6_a_colour_changed_in_company_profile_follows_immediately(pine_hill, sarah):
    switch_on(pine_hill, sarah)
    assert _front(pine_hill)["tenant"]["brand_primary_hex"] == "#EC3013"
    with tenant_context(pine_hill.id):
        tenancy_services.save_company_profile(
            SimpleNamespace(id=sarah.user.id, role=SYSTEM_ADMIN), {"brand_primary_hex": "#123456"}
        )
    assert _front(pine_hill)["tenant"]["brand_primary_hex"] == "#123456"
    assert _get(pine_hill, sarah).data["shared"]["brand_primary_hex"] == "#123456"


@pytest.mark.django_db
def test_us_cwp_070_tc7_an_oak_ridge_admin_sees_oak_ridges_brand(pine_hill, sarah, oak_ridge, elena):
    brand_fully(pine_hill, sarah)
    body = _get(oak_ridge, elena).data
    assert body["shared"]["trading_name"] == "Oak Ridge Water"
    assert body["shared"]["brand_primary_hex"] == "#0B6E4F"
    assert body["portal_only"]["strapline"] is None
    assert [row["code"] for row in body["services"]] == ["water"]
    assert "Pine Hill" not in str(body) and "#EC3013" not in str(body)


@pytest.mark.django_db
def test_us_cwp_070_tc8_reset_clears_the_portal_only_fields_and_touches_nothing_shared(pine_hill, sarah, audit_rows):
    """⚠ **THE PORTAL-ONLY SET IS SIX SINCE 2026-09-05, NOT FIVE AND NOT FOUR.**
    `quick_service_categories` joined it with `CR-068` wave C (`US-CWP-015`) and
    `request_errands` with wave J (`US-CWP-060`, `CWP-046`'s errand cards) — both
    are the utility's own list and both are saved through this same door, because
    a second door for one list would be a second set of rules. The case is
    unchanged in every other respect; only the count moved.

    ⚠ **AND THAT IS TWICE NOW, WHICH IS THE POINT WORTH LEAVING BEHIND
    (`DEF-CWP-3825`).** This assertion is an EXACT dict equality, so every wave
    that adds a portal-only field turns it red — correctly, because a field
    silently joining the reset's blast radius is exactly what it exists to
    catch. `US-CWP-060` added `request_errands` and did not come back here, so
    the branch was red on somebody else's story. The count is now written in the
    first line of this docstring so the next wave can see what it is changing."""
    switch_on(pine_hill, sarah)
    brand_fully(pine_hill, sarah)
    body = _put(
        pine_hill,
        sarah,
        {"strapline": None, "front_page_service_ids": [], "office_hours_text": None, "emergency_phone": None},
    ).data
    assert body["portal_only"] == {
        "strapline": None,
        "front_page_service_ids": [],
        "office_hours_text": None,
        "emergency_phone": None,
        # Not cleared: the reset names the four fields it sends, and a field a
        # caller did not name is left alone (`_validate_branding` never invents
        # a change). Pine Hill runs the seeded six, so its own list is empty.
        "quick_service_categories": [],
        # Same posture, one wave later: `CWP-046`'s errand cards are the
        # utility's own list, the reset does not name them, so the reset does
        # not touch them.
        "request_errands": [],
    }
    assert body["shared"]["brand_primary_hex"] == "#EC3013"
    assert body["shared"]["trading_name"] == "Pine Hill Water & Power"
    row = models.PortalSettings.objects.get(tenant=pine_hill)
    assert row.is_live is True and row.quick_pay_enabled is True  # the switches did not move
    reset_row = [one for one in audit_rows if one["action"] == "portal_settings.update"][-1]
    assert reset_row["before"]["strapline"] == sample_data.PINE_HILL["branding"]["strapline"]
    assert reset_row["after"]["strapline"] is None
