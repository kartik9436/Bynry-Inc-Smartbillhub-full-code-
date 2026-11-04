# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-CWP-3994 — the tenant's date format and time zone reach the
#           STAFF app and not the portal. `DEF-SHL-3964` built the provider and
#           de-prop-drilled 160 call sites, and it was green everywhere,
#           because nobody asked whether the portal was INSIDE the provider —
#           it is that component's sibling in the route tree, so it never was.
#           And the endpoint the staff shell reads is staff-only anyway, so the
#           values had no way to arrive. This file is the BACKEND half: the two
#           settings on the portal's own payload.
# Rules:    IS-8 (Settings → Company → Regional & Formats feeds every date) ·
#           BR-SHL-023 (tenant TZ + regional format, ONE formatting path) ·
#           BR-CWP-012 (the portal reads through the owning module's seam) ·
#           BR-CWP-005 (the tenant in context is the tenant on the path) ·
#           hard-won law 3 (defaults fail closed — no invented format)
# ───────────────────────────────────────────────────────
"""`GET /portal/public/front` carries the tenant's Regional settings.

⚠ **THE ASSERTION THAT MATTERS IS THE ONE THAT CHANGES THE VALUE.** A test that
reads the payload once proves a key exists; it cannot tell a served setting
from a hardcoded string, and a hardcoded string is exactly what `DEF-SHL-3964`
was. Every case below that asserts a format SETS it first and then reads it
back, and `test_..._follows_a_change` sets it twice.
"""

import pytest

from apps.portal import guest_api
from apps.tenancy import models as tenancy_models
from tests.test_us_cwp_helpers import *  # noqa: F401,F403
from tests.test_us_cwp_helpers import switch_on
from tests.test_us_ten_helpers import api_call


def _front(tenant):
    return api_call(
        guest_api.front, "get", f"/api/{tenant.subdomain}/portal/public/front", tenant=tenant
    ).data


def _set_regional(tenant, *, timezone=None, date_format=None, language="en"):
    """Write the Regional columns the Settings screen writes.

    ⚠ **`language` JOINED THIS PAYLOAD ON 2026-09-07 (`DEF-CWP-4440`,
    `BR-CWP-105`) AND IS PINNED HERE ON PURPOSE.** The whole-dict assertions
    below are worth keeping exactly as they are — an exact comparison is what
    notices a field somebody adds without meaning to — but they can only stay
    exact if every key is deterministic. The provisioned tenant is seeded with
    `en-US`, so leaving the column alone would make these tests assert a seed
    value and go red the day provisioning changes. Pinning it keeps the
    assertion about THIS defect's two fields while still failing on a
    surprise third.
    """
    row, _ = tenancy_models.TenantSettings.objects.get_or_create(tenant_id=tenant.id)
    if timezone is not None:
        row.timezone = timezone
    if date_format is not None:
        row.date_format = date_format
    row.language = language
    row.save(update_fields=["timezone", "date_format", "language"])
    return row


@pytest.mark.django_db
def test_the_front_payload_carries_the_tenants_own_date_format(pine_hill, sarah):
    switch_on(pine_hill, sarah)
    _set_regional(pine_hill, timezone="America/Chicago", date_format="DD-MMM-YY")
    body = _front(pine_hill)
    assert body["regional"] == {
        "timezone": "America/Chicago",
        "date_format": "DD-MMM-YY",
        "language": "en",
    }


@pytest.mark.django_db
def test_a_format_changed_in_settings_follows_to_the_portal_immediately(pine_hill, sarah):
    """TC — the customer-facing half of the PO's own sentence.

    *"date and time format is set in the settings … but date shown everywhere
    in the product does not change with that format change."* This is the
    server side of *changes with it*: the payload is read, the setting is
    changed, the payload is read again, and the two answers differ. Nothing is
    cached and no sync runs between them.
    """
    switch_on(pine_hill, sarah)
    _set_regional(pine_hill, timezone="UTC", date_format="MM/DD/YYYY")
    assert _front(pine_hill)["regional"]["date_format"] == "MM/DD/YYYY"

    _set_regional(pine_hill, timezone="America/Chicago", date_format="DD/MM/YYYY")
    after = _front(pine_hill)["regional"]
    assert after["date_format"] == "DD/MM/YYYY"
    assert after["timezone"] == "America/Chicago"


@pytest.mark.django_db
def test_an_unset_setting_travels_as_an_absence_and_never_as_a_default(pine_hill, sarah):
    """hard-won law 3, and `DEF-SHL-3964` is what the other answer costs.

    The defect was built entirely out of a plausible default: the old helper
    fell through to `MM/DD/YYYY` and `UTC` on every screen, forever, with no
    crash and no blank to notice, and a Texas utility read every timestamp five
    hours out. A caller that cannot tell *not set* from *the tenant says
    MM/DD/YYYY* would repeat that, so the absence stays an absence here.
    """
    switch_on(pine_hill, sarah)
    row, _ = tenancy_models.TenantSettings.objects.get_or_create(tenant_id=pine_hill.id)
    row.timezone = None
    row.date_format = None
    # ⚠ The language answers to the same rule and is cleared here so all THREE
    # absences are asserted together (`DEF-CWP-4440`): a tenant who has chosen
    # no language must not be served English, or the portal could never fall
    # through to the reader's own browser.
    row.language = None
    row.save(update_fields=["timezone", "date_format", "language"])
    assert _front(pine_hill)["regional"] == {
        "timezone": None,
        "date_format": None,
        "language": None,
    }


@pytest.mark.django_db
def test_the_holding_page_carries_it_too(pine_hill):
    """A tenant whose portal is OFF still serves the holding page, and a date
    can appear on it. The payload shape does not change with the switch."""
    _set_regional(pine_hill, timezone="Europe/Berlin", date_format="DD.MM.YYYY")
    body = _front(pine_hill)
    assert body["is_live"] is False
    assert body["regional"] == {
        "timezone": "Europe/Berlin",
        "date_format": "DD.MM.YYYY",
        "language": "en",
    }


@pytest.mark.django_db
def test_one_tenants_format_never_reaches_another(pine_hill, sarah, oak_ridge, elena):
    """BR-CWP-005 / hard rule 1 — the read is scoped to the tenant on the path,
    and this is the case that would catch a seam reading the context tenant
    while answering for another."""
    switch_on(pine_hill, sarah)
    switch_on(oak_ridge, elena)
    _set_regional(pine_hill, timezone="America/Chicago", date_format="DD-MMM-YY")
    _set_regional(oak_ridge, timezone="Asia/Kolkata", date_format="DD-MM-YYYY")

    assert _front(pine_hill)["regional"]["date_format"] == "DD-MMM-YY"
    assert _front(oak_ridge)["regional"]["date_format"] == "DD-MM-YYYY"
    assert _front(pine_hill)["regional"]["timezone"] == "America/Chicago"
