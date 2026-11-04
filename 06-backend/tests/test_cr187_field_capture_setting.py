# ── Trace ──────────────────────────────────────────────
# Change:   CR-187-BRC10 — the PO's correction of 2026-10-21 (decision log
#           *"Field app: the PO corrects four of the ten answers"* item 2):
#           the capture credential's life comes FROM SETTINGS.
# Rules:    BR-WRK-060 (the 7-day seed) · BR-IDN-019 (SysAdmin edits, the
#           Security tab) · hard rule 7 (the change is audited) · law 3
# Tests:    this file (SQLite)
# ───────────────────────────────────────────────────────
"""The field app's capture life is the UTILITY'S setting, not the process's.

PO, verbatim: *"this should come from settings"*. Settings → Security holds
`field_capture_hours` (seeded 168 = 7 days); the capture token and the native
refresh token are both given that life, and the capture token's answer says
when it ends so the phone can use it.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from django.utils import timezone

from apps.identity import services
from apps.identity.models import SecurityPolicy
from tests.isolation_helpers import writing_as_tenant
from tests.test_cr187_native_auth import (  # noqa: F401 (fixture import)
    _post,
    _register,
    _token,
    field,
)
from tests.test_us_idn_helpers import (  # noqa: F401 (fixture import)
    api_get,
    api_put,
    idn,
    signed_in_client,
)

pytestmark = pytest.mark.django_db

PATH = "/settings/security-policy"


def _admin(env):
    return signed_in_client(env.users.alex.email, "Canyon2026rapids")


def _set_hours(env, hours):
    with writing_as_tenant(env.silvercreek):
        SecurityPolicy.objects.update_or_create(
            tenant_id=env.silvercreek.id, defaults={"field_capture_hours": hours}
        )


def test_the_seed_is_seven_days_and_the_read_serves_it_with_its_choices(field):
    body = api_get(_admin(field), PATH).json()
    assert body["field_capture_hours"] == 168
    limits = body["limits"]["field_capture_hours"]
    assert limits["default"] == 168
    # One hour to thirty days, 36 (the design's figure) and 168 on the list.
    assert limits["choices"] == [1, 12, 24, 36, 48, 72, 168, 336, 720]


def test_a_system_admin_saves_it_and_the_change_is_audited_before_and_after(field):
    response = api_put(_admin(field), PATH, {"field_capture_hours": 36})
    assert response.status_code == 200, response.content
    assert response.json()["field_capture_hours"] == 36
    row = field.rows_for("settings.security_updated")[-1]
    assert row["before"] == {"field_capture_hours": 168}
    assert row["after"] == {"field_capture_hours": 36}


@pytest.mark.parametrize("hours", [0, 2, 721, 24 * 365])
def test_a_life_off_the_list_is_refused_by_name(field, hours):
    response = api_put(_admin(field), PATH, {"field_capture_hours": hours})
    assert response.status_code == 422, response.content
    errors = response.json()["field_errors"]
    assert errors[0]["field"] == "field_capture_hours"
    assert errors[0]["params"]["allowed"] == list(services.FIELD_CAPTURE_HOURS_CHOICES)


def test_the_capture_token_carries_the_utilitys_life_and_when_it_ends(field):
    _set_hours(field, 36)
    access = _token().json()["access_token"]
    _register(access)
    before = timezone.now()
    issued = _post("/work/mobile/capture-token", access).json()
    assert issued["max_age_seconds"] == 36 * 3600
    ends = datetime.fromisoformat(issued["expires_at"])
    assert before + timedelta(hours=36) - timedelta(seconds=5) <= ends
    assert ends <= timezone.now() + timedelta(hours=36)


def test_the_refresh_token_follows_the_same_setting(field):
    _set_hours(field, 12)
    assert _token().json()["refresh_expires_in"] == 12 * 3600


def test_a_utility_that_never_opened_the_tab_gets_seven_days_on_both(field):
    access_body = _token().json()
    assert access_body["refresh_expires_in"] == 7 * 24 * 3600
    _register(access_body["access_token"])
    issued = _post("/work/mobile/capture-token", access_body["access_token"]).json()
    assert issued["max_age_seconds"] == 7 * 24 * 3600


def test_a_shorter_life_expires_a_token_already_on_the_handset(field):
    """The token is checked against the setting AS IT STANDS — shortening the
    life is the safe direction and reaches tokens already issued (law 3)."""
    from apps.work import mobile
    from core import errors
    from core import tenancy as core_tenancy

    access = _token().json()["access_token"]
    _register(access)
    token = _post("/work/mobile/capture-token", access).json()["capture_token"]
    _set_hours(field, 1)
    later = timezone.now() + timedelta(hours=2)
    from unittest import mock

    with mock.patch("django.core.signing.time.time", return_value=later.timestamp()):
        with core_tenancy.tenant_context(field.silvercreek.id):
            with pytest.raises(errors.AuthError) as raised:
                mobile.captor_from_token(token)
    assert raised.value.message_key == "work.mobile.capture_token_expired"
