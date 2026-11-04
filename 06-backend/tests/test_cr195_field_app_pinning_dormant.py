# ── Trace ──────────────────────────────────────────────
# Change:   CR-195-BRC10 — field-app certificate pinning dropped as a go-live
#           requirement, kept dormant (decision log 2026-10-28, PO "start A1")
# Rules:    hard-won law 2's mirror (no visible control that does nothing)
# Tests:    this file
# ───────────────────────────────────────────────────────
"""The Security tab is told whether to show the *Field app certificates* card.

Pinning is off in every field-app build, so the card that edits the pins is a
control that does nothing. ONE platform setting, `SBH_FIELD_APP_PINNING_ENABLED`
(default false), is served on the security-policy read as
`field_app_pinning_enabled`; the screen hides the card on false. The stored
lists, the card's own endpoint and the phone's settings answer are untouched,
so turning the setting on brings the card back with no new work.

WHAT WOULD MAKE THIS PASS WRONGLY: serving the flag on the GET but not on the
PUT's answer — the screen replaces its copy with the PUT's, so the card would
vanish after every Save while pinning was on. Both are asserted.
"""

from __future__ import annotations

import pytest
from django.test import override_settings

from tests.test_us_idn_helpers import (  # noqa: F401 (fixture import)
    api_get,
    api_put,
    idn,
    signed_in_client,
)

pytestmark = pytest.mark.django_db

POLICY = "/settings/security-policy"
PINS = "/settings/security-policy/field-app-pins"


def _admin(env):
    env.seed_silvercreek()
    return signed_in_client("alex@silvercreek.example", "Canyon2026rapids")


def test_the_card_is_hidden_by_default(idn):
    body = api_get(_admin(idn), POLICY).json()
    assert body["field_app_pinning_enabled"] is False


@override_settings(FIELD_APP_PINNING_ENABLED=True)
def test_one_setting_brings_it_back_on_the_read_and_on_the_save(idn):
    alex = _admin(idn)
    assert api_get(alex, POLICY).json()["field_app_pinning_enabled"] is True
    saved = api_put(alex, POLICY, {"session_timeout_minutes": 30})
    assert saved.status_code == 200, saved.content
    assert saved.json()["field_app_pinning_enabled"] is True


def test_the_flag_is_not_a_setting_a_utility_can_save(idn):
    alex = _admin(idn)
    saved = api_put(alex, POLICY, {"session_timeout_minutes": 30, "field_app_pinning_enabled": True})
    assert saved.status_code == 200, saved.content
    assert saved.json()["field_app_pinning_enabled"] is False


def test_the_stored_data_and_its_endpoint_stay(idn):
    # Dormant, not deleted: the card's own read still answers.
    body = api_get(_admin(idn), PINS).json()
    assert body["source"] == "default"
    assert len(body["pins"]) >= 2
