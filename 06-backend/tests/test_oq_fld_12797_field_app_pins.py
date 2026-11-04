# ── Trace ──────────────────────────────────────────────
# Change:   CR-187-BRC10 — closes the build of OQ-FLD-12797 (decision log
#           2026-10-24 "FOUR PO ANSWERS ON THE FIELD APP'S OPEN QUESTIONS" (3))
# Rules:    12-security.md §4 (two pins, documented rotation) · hard rule 1
#           (the list is the utility's, RLS) · hard rule 7 (audited before/after)
# Tests:    this file (SQLite); the PG half is test_oq_fld_12797_field_app_pins_pg.py
# ───────────────────────────────────────────────────────
"""The field app's certificate pins come from Settings › Security.

PO, verbatim: *"plese dont hardcode it use settings - security values set in
staff portal"*. Worked example from the ruling: the issuer renews in 2027; the
office adds the new issuer's key in December 2026; every phone picks it up at
its next sync; no app update.
"""

from __future__ import annotations

import datetime as dt

import pytest

from apps.identity import field_pins
from apps.identity.models import SecurityPolicy
from tests.isolation_helpers import writing_as_tenant
from tests.test_cr187_native_auth import (  # noqa: F401 (fixture import)
    _get,
    _register,
    _token,
    field,
)
from tests.test_us_idn_helpers import (  # noqa: F401 (fixture import)
    BM,
    api_get,
    api_put,
    idn,
    signed_in_client,
)

pytestmark = pytest.mark.django_db

PATH = "/settings/security-policy/field-app-pins"
X1 = "C5+lpZ7tcVwmwQIMcRtPbsQtWLABXhQzejna0wHFr8M="
GTS = "hxqRlPTu1bMS/0DITB1SSu0vd4u/8l8TjPgfaAp63Gc="
X2 = "diGVwiVYbubAI3RW4hB9xU8e/CH2GnkuvVFZE8zmgzI="
G2 = "i7WTqTvh0OioIruIfFR4kMPnBqrS2rdiVPl/s2uC/CY="


def _admin(env):
    return signed_in_client(env.users.alex.email, "Canyon2026rapids")


def _exec(env):
    return signed_in_client(env.users.diana.email, "Vista2026peak")


def _pin(spki, label, not_after="2035-06-04", active=True):
    return {"spki_sha256": spki, "label": label, "not_after": not_after, "active": active}


def _defaults():
    return [_pin(X1, "ISRG Root X1"), _pin(GTS, "GTS Root R1", "2036-06-22")]


def _field_errors(response):
    return [(e["field"], e["message_key"]) for e in response.json()["field_errors"]]


# ── the read ────────────────────────────────────────────────────────────────
def test_a_utility_that_never_edited_the_list_is_served_the_platform_default(field):
    body = api_get(_admin(field), PATH).json()
    assert body["source"] == "default"
    assert [(p["label"], p["spki_sha256"], p["status"]) for p in body["pins"]] == [
        ("ISRG Root X1", X1, "valid"),
        ("GTS Root R1", GTS, "valid"),
    ]
    # The ruling's figures are served, not typed into the screen.
    assert body["warning_days"] == 60
    assert body["min_valid"] == 2


def test_the_default_comes_from_settings_not_from_code(field, settings):
    settings.FIELD_APP_DEFAULT_PINS = [
        {"spki_sha256": X2, "label": "ISRG Root X2", "not_after": "2040-09-17"},
        {"spki_sha256": G2, "label": "DigiCert G2", "not_after": "2038-01-15"},
    ]
    body = api_get(_admin(field), PATH).json()
    assert [p["spki_sha256"] for p in body["pins"]] == [X2, G2]


def test_a_malformed_default_fails_loudly(field, settings):
    from django.core.exceptions import ImproperlyConfigured

    settings.FIELD_APP_DEFAULT_PINS = [{"spki_sha256": "nope", "label": "x", "not_after": "2030-01-01"}]
    with pytest.raises(ImproperlyConfigured):
        field_pins.default_pins()


def test_an_executive_views_and_cannot_save(field):
    assert api_get(_exec(field), PATH).status_code == 200
    assert api_put(_exec(field), PATH, {"pins": _defaults()}).status_code == 403


def test_a_clerk_sees_nothing(field):
    clerk = signed_in_client(field.users.priya.email, "Meadow2026sage")
    assert api_get(clerk, PATH).status_code == 403


# ── the save: the worked example ────────────────────────────────────────────
def test_the_office_adds_the_new_issuers_key_and_it_is_audited_before_and_after(field):
    new = [*_defaults(), _pin(X2, "ISRG Root X2", "2040-09-17")]
    response = api_put(_admin(field), PATH, {"pins": new})
    assert response.status_code == 200, response.content
    body = response.json()
    assert body["source"] == "utility"
    assert [p["label"] for p in body["pins"]] == ["ISRG Root X1", "GTS Root R1", "ISRG Root X2"]
    row = field.rows_for("settings.field_app_pins_updated")[-1]
    assert row["before"] == {"field_app_pins": None}  # the platform default was in force
    assert [p["spki_sha256"] for p in row["after"]["field_app_pins"]] == [X1, GTS, X2]


def test_then_the_old_key_is_deactivated_and_the_change_is_audited(field):
    api_put(_admin(field), PATH, {"pins": [*_defaults(), _pin(X2, "ISRG Root X2", "2040-09-17")]})
    rotated = [_pin(X1, "ISRG Root X1", active=False), _pin(GTS, "GTS Root R1", "2036-06-22"), _pin(X2, "ISRG Root X2", "2040-09-17")]
    response = api_put(_admin(field), PATH, {"pins": rotated})
    assert response.status_code == 200, response.content
    statuses = {p["label"]: p["status"] for p in response.json()["pins"]}
    assert statuses == {"ISRG Root X1": "inactive", "GTS Root R1": "valid", "ISRG Root X2": "valid"}
    row = field.rows_for("settings.field_app_pins_updated")[-1]
    assert row["before"]["field_app_pins"][0]["active"] is True
    assert row["after"]["field_app_pins"][0]["active"] is False


# ── validation ──────────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    "bad",
    [
        "not base64!",
        "C5+lpZ7tcVwmwQIMcRtPbsQtWLABXhQzejna0wHFr8",  # 31 bytes' worth
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",  # 36 bytes
        "",
    ],
)
def test_a_hash_that_is_not_base64_of_32_bytes_is_refused_by_name(field, bad):
    response = api_put(_admin(field), PATH, {"pins": [*_defaults(), _pin(bad, "Bad")]})
    assert response.status_code == 422, response.content
    assert ("pins[2].spki_sha256", "errors.identity.pin_hash_invalid") in _field_errors(response)


def test_a_key_listed_twice_a_missing_label_and_a_bad_date_are_each_named(field):
    pins = [*_defaults(), _pin(X1, "Again"), _pin(X2, "  "), _pin(G2, "G2", "31/12/2030")]
    response = api_put(_admin(field), PATH, {"pins": pins})
    assert response.status_code == 422
    assert set(_field_errors(response)) >= {
        ("pins[2].spki_sha256", "errors.identity.pin_duplicate"),
        ("pins[3].label", "errors.identity.pin_label_required"),
        ("pins[4].not_after", "errors.identity.pin_date_invalid"),
    }


def test_a_save_leaving_fewer_than_two_active_pins_is_refused_and_nothing_is_written(field):
    pins = [_pin(X1, "ISRG Root X1"), _pin(GTS, "GTS Root R1", "2036-06-22", active=False)]
    response = api_put(_admin(field), PATH, {"pins": pins})
    assert response.status_code == 422
    assert _field_errors(response) == [("pins", "errors.identity.pins_too_few")]
    assert response.json()["field_errors"][0]["params"] == {"min": 2}
    with writing_as_tenant(field.silvercreek):
        assert not SecurityPolicy.objects.filter(tenant_id=field.silvercreek.id).exists()
    assert field.rows_for("settings.field_app_pins_updated") == []


def test_an_expired_pin_does_not_count_toward_the_two(field):
    pins = [*_defaults(), _pin(X2, "ISRG Root X2", "2040-09-17")]
    pins[1]["not_after"] = "2020-01-01"  # GTS "expired"
    pins[2]["active"] = False
    response = api_put(_admin(field), PATH, {"pins": pins})
    assert response.status_code == 422
    assert _field_errors(response) == [("pins", "errors.identity.pins_too_few")]


def test_a_list_sharing_no_key_with_todays_is_refused_because_phones_could_never_fetch_it(field):
    pins = [_pin(X2, "ISRG Root X2", "2040-09-17"), _pin(G2, "DigiCert G2", "2038-01-15")]
    response = api_put(_admin(field), PATH, {"pins": pins})
    assert response.status_code == 422
    assert _field_errors(response) == [("pins", "errors.identity.pins_keep_one_current")]


def test_a_missing_or_wrong_shaped_list_is_refused(field):
    assert api_put(_admin(field), PATH, {}).status_code == 422
    assert api_put(_admin(field), PATH, {"pins": "x"}).status_code == 422


def test_the_sixty_day_warning(field):
    today = dt.date(2026, 10, 24)
    assert field_pins.status_of(_pin(X1, "a", "2026-12-23"), today) == ("expiring", 60)
    assert field_pins.status_of(_pin(X1, "a", "2026-12-24"), today) == ("valid", 61)
    assert field_pins.status_of(_pin(X1, "a", "2026-10-24"), today) == ("expiring", 0)
    assert field_pins.status_of(_pin(X1, "a", "2026-10-23"), today) == ("expired", -1)
    assert field_pins.status_of(_pin(X1, "a", "2026-10-23", active=False), today)[0] == "inactive"


# ── the phone ───────────────────────────────────────────────────────────────
def test_the_phone_is_served_its_utilitys_active_unexpired_pins_over_the_field_route(field):
    api_put(_admin(field), PATH, {"pins": [*_defaults(), _pin(X2, "ISRG Root X2", "2040-09-17", active=False)]})
    access = _token().json()["access_token"]
    _register(access)
    response = _get("/work/mobile/settings", access)
    assert response.status_code == 200, response.content
    assert response.json()["field_app_pins"] == [
        {"spki_sha256": X1, "label": "ISRG Root X1", "not_after": "2035-06-04"},
        {"spki_sha256": GTS, "label": "GTS Root R1", "not_after": "2036-06-22"},
    ]


def test_one_utilitys_list_never_reaches_another_utilitys_phones(field):
    """Blue Mesa's admin edits Blue Mesa's list; Silver Creek's phone still gets
    the platform default. A per-utility list cannot break another utility."""
    jordan, _m = field.seed_bluemesa_admin()
    blue = signed_in_client(jordan.email, "Mesa2026bluff", tenant=BM)
    mine = [*_defaults(), _pin(X2, "ISRG Root X2", "2040-09-17")]
    assert api_put(blue, PATH, {"pins": mine}, tenant=BM).status_code == 200
    assert api_get(_admin(field), PATH).json()["source"] == "default"
    access = _token().json()["access_token"]
    _register(access)
    served = [p["spki_sha256"] for p in _get("/work/mobile/settings", access).json()["field_app_pins"]]
    assert served == [X1, GTS]


def test_the_office_route_refuses_a_phone_bearer(field):
    access = _token().json()["access_token"]
    from django.test import Client

    from tests.test_us_idn_helpers import api_path

    response = Client().get(api_path(PATH), HTTP_AUTHORIZATION=f"Bearer {access}")
    assert response.status_code in (401, 403)
