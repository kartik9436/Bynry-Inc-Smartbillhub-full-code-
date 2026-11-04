# ── Trace ──────────────────────────────────────────────
# Story:    US-TEN-006 (S8 → Company → Regional, formats & fiscal calendar)
# Rules:    BR-TEN-081 (a typed posting DATE is midnight in the UTILITY'S OWN
#           timezone — PO 2026-08-12, OQ-153) · BR-TEN-020 (regional settings are
#           display-time transforms; storage stays UTC) · BR-TEN-043 (config is
#           event-time: the value in force when the event happens governs it) ·
#           BR-SHL-033 (a list this short is a dropdown, not a type-ahead)
# Defect:   DEF-082 — "you did not fix time zone drop down in company settings"
#           (Product Owner, 2026-08-12, working chat session)
# ───────────────────────────────────────────────────────
"""DEF-082 — the utility's own clock, chosen by a human and read by the code.

WHAT THIS FILE PROVES, AND WHY IT IS THE ROUND TRIP RATHER THAN THE CONTROL.
DEF-082 is filed as a missing control, and hard-won law 2 says a control that
writes to nothing is the same defect wearing the opposite coat. So the assertion
that matters is not "a picker exists" — it is that the value a human sets on
Settings → Company → Regional is the value `selectors.tenant_today()` reads, and
that changing it CHANGES THE DAY the product believes it is.

The worked figure is the PO's own, run backwards so it can be measured without a
payment: at **2026-08-22T04:30:00Z** a utility on `America/Chicago` (UTC−5 in
August) is still on **21 August** at 23:30, while UTC has already rolled over to
the 22nd. That one-day gap is exactly what BR-TEN-081 exists to stop, and it is
only reachable because the tenant's timezone is a stored, chosen value.

`TIMEZONE_CHOICES` is the OFFERED set (A1 §S8's eight US zones), not the
ACCEPTED set: `services._validate_regional_changes` still takes any name
`ZoneInfo` resolves, so no tenant already holding a zone outside the eight is
refused. The two tests below pin the two claims that had nothing checking them —
that every zone provisioning can store is one a human can pick back, and that
the frontend's mirrored list is still the server's list.
"""

import re
from datetime import date, datetime, timezone as dt_timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from django.utils import timezone as django_timezone

from apps.tenancy import models, selectors, services

from tests.test_us_ten_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import admin_actor, provisioned_tenant, tenant_ctx

pytestmark = pytest.mark.django_db

# The instant the PO's example straddles: 04:30 UTC on 22 August 2026. Central
# is UTC−5 that day (CDT), so the utility's own clock still says the 21st.
STRADDLE = datetime(2026, 8, 22, 4, 30, tzinfo=dt_timezone.utc)

FRONTEND_TAB = (
    Path(__file__).resolve().parents[2]
    / "07-frontend"
    / "src"
    / "features"
    / "tenancy"
    / "SettingsRegionalTab.tsx"
)


def _frozen_now(monkeypatch, moment):
    """Freeze the ONE clock `tenant_today()` reads. Not a money path (G6):
    this is the display/date-derivation clock BR-TEN-020 governs."""
    monkeypatch.setattr(django_timezone, "now", lambda: moment)


def test_def_082__the_zone_saved_on_the_screen_is_the_zone_the_date_logic_reads(
    growth_plan, identity_seam, monkeypatch
):
    """DEF-082 / BR-TEN-081 — THE ROUND TRIP.

    Set the utility's clock the way the Regional tab sets it, then ask the
    product what day it is. Houston says 21 August at the instant UTC calls the
    22nd; move the same utility to New York and it agrees with UTC. Nothing here
    reads a hardcoded zone — the ANSWER MOVES WITH THE SETTING, which is the
    whole of what the ruling depends on.
    """
    tenant, _ = provisioned_tenant()
    actor = admin_actor()
    _frozen_now(monkeypatch, STRADDLE)

    with tenant_ctx(tenant):
        saved = services.save_regional_settings(actor, {"timezone": "America/Chicago"})
        assert saved["timezone"] == "America/Chicago"
        # ...and the screen reads back what it wrote (GET /settings/regional).
        assert selectors.regional_settings()["timezone"] == "America/Chicago"
        # THE POINT: the clock every date derivation uses now speaks Central.
        assert selectors.tenant_today() == date(2026, 8, 21)
        assert STRADDLE.date() == date(2026, 8, 22)  # ...and UTC does not.

        # BR-TEN-043 (event-time): change the setting, and the next read of the
        # clock answers under the new value — no restatement, no caching.
        services.save_regional_settings(actor, {"timezone": "America/New_York"})
        assert selectors.tenant_today() == date(2026, 8, 22)

    stored = models.TenantSettings.objects.get(tenant_id=tenant.id)
    assert stored.timezone == "America/New_York"


def test_def_082__every_zone_provisioning_can_store_is_one_a_human_can_pick_back(
    growth_plan, identity_seam
):
    """The claim in `services.US_STATE_TIMEZONES`' own comment — *"Values are
    constrained to the eight zones the S8 type-ahead offers"* — asserted rather
    than believed (hard-won law 1). A signup that seeds a zone the settings
    screen cannot offer leaves a utility unable to re-choose its own clock,
    which is DEF-082 arriving through the back door.
    """
    offered = set(selectors.TIMEZONE_CHOICES)
    seeded = set(services.US_STATE_TIMEZONES.values())
    assert seeded <= offered, f"provisioning can store zones nobody can pick: {seeded - offered}"

    # Every offered name must be one the SERVER would accept back (the same
    # ZoneInfo vocabulary `_validate_regional_changes` validates against), so
    # the screen can never offer a value its own Save would refuse.
    for name in selectors.TIMEZONE_CHOICES:
        assert ZoneInfo(name) is not None

    # A brand-new Texas utility lands on a real zone, not on UTC-by-omission.
    assert services.default_timezone_for_state("TX") == "America/Chicago"


def test_def_082__the_screen_offers_exactly_the_server_list(growth_plan, identity_seam):
    """The Regional tab MIRRORS this tuple in TypeScript (it is a client-side
    copy of a server vocabulary, the same pattern the file already uses for
    currencies and date formats). Nothing compared the two copies, so a zone
    added on one side and not the other would ship silently — the failure mode
    the whole stale-claim family in the defect register keeps repeating.
    """
    source = FRONTEND_TAB.read_text(encoding="utf-8")
    match = re.search(r"TIMEZONE_OPTIONS:\s*readonly string\[\]\s*=\s*\[(.*?)\]", source, re.S)
    assert match is not None, "SettingsRegionalTab.tsx no longer declares TIMEZONE_OPTIONS"
    on_screen = tuple(re.findall(r'"([^"]+)"', match.group(1)))
    assert on_screen == selectors.TIMEZONE_CHOICES


def test_def_082__a_stored_zone_outside_the_offered_eight_is_still_offerable(
    growth_plan, identity_seam
):
    """A tenant CAN hold a zone outside the eight — the server accepts any IANA
    name and always has (`America/Detroit` is the live example: Michigan spans
    two zones and the map defaults it to New York). The options a screen renders
    must therefore always CONTAIN the stored value, or the utility's own clock
    renders as an empty box and one Save silently re-chooses it.
    """
    assert "America/Detroit" not in selectors.TIMEZONE_CHOICES
    assert selectors.timezone_options("America/Detroit")[0] == "America/Detroit"
    assert set(selectors.TIMEZONE_CHOICES) <= set(selectors.timezone_options("America/Detroit"))
    # A stored zone that IS one of the eight adds nothing and reorders nothing.
    assert selectors.timezone_options("America/Chicago") == selectors.TIMEZONE_CHOICES
    assert selectors.timezone_options(None) == selectors.TIMEZONE_CHOICES


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-TEN-006@0733260 (story+rules snapshot hash — EP-TEN-05; the DEF-082 defect lane, whose field US-TEN-006 §5 owns)
# generated: 2026-08-15 by story-coder v1 (DEF-082 tenant-timezone lane)
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: proved RED first (law 7) — 3 failed / 1 passed on `AttributeError: module 'apps.tenancy.selectors' has no attribute 'TIMEZONE_CHOICES'`; the round-trip test was the one that PASSED, which is the lane's finding: the backend clock already worked and only the screen did not. After the fix 4 passed. Backend suite 2081 passed / 132 skipped / 1 xfailed✔ · ruff✔ black✔
# exceptions: the WRITE half of BR-TEN-081 is NOT asserted here — anchoring a
#   typed calendar date at tenant-midnight lives in apps/payments/api._moment,
#   outside this lane's territory, and it still anchors at midnight UTC.
#   REPORTED, not silently fixed (see the it.todo in the frontend twin).
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
