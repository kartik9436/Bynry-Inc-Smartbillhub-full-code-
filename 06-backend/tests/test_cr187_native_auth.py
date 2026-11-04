# ── Trace ──────────────────────────────────────────────
# Change:   CR-187-BRC10 — the native field app's sign-in, server half
#           (07-endpoints.md N24; Security §1/§4; AD-21; R105, R113, R115, R127)
# Rules:    BR-IDN-002/006/012/020/022/025 · BR-WRK-059/060 · hard rule 7
# Tests:    this file (SQLite) · test_cr187_native_auth_pg.py (PostgreSQL 16)
# ───────────────────────────────────────────────────────
"""The native app's bearer tokens, devices, capture credential and activation.

Every case drives the real routes through Django's test client under the real
`/api/{tenant}/…` paths, with the identity suite's `idn` fixture (a controllable
clock on `services._now`, a recording audit sink, two tenants).
"""

from __future__ import annotations

import json
from datetime import timedelta

import pytest
from django.core.cache import cache
from django.test import Client
from django.urls import get_resolver

from apps.identity import native
from apps.identity.auth import IdentitySessionAuthentication
from apps.identity.models import ActivationCode, NativeToken, TenantMembership
from apps.identity.native_auth import NativeBearerAuthentication
from apps.work import mobile
from apps.work import models as work_models
from core import tenancy as core_tenancy
from tests.isolation_helpers import writing_as_tenant
from tests.test_us_idn_helpers import (  # noqa: F401 (fixture import)
    BM,
    JSON,
    SC,
    api_path,
    idn,
    signed_in_client,
)

PASSWORD = "Valley2026river"
DEVICE = "a1b2c3d4-handset-0001"


@pytest.fixture()
def field(idn):  # noqa: F811
    """Silver Creek with Dana, a field technician holding a technician profile,
    and Alex, the System Admin. The throttles' cache is cleared so one test's
    calls never count against another's."""
    cache.clear()
    users = idn.seed_silvercreek()
    dana, dana_m = idn.make_user(
        idn.silvercreek, "dana@silvercreek.example", "Dana Ortiz",
        password=PASSWORD, role="field_technician",
    )
    with writing_as_tenant(idn.silvercreek):
        tech = work_models.Technician.objects.create(tenant=idn.silvercreek, user=dana)
    idn.users, idn.dana, idn.dana_m, idn.tech = users, dana, dana_m, tech
    yield idn
    cache.clear()


def _token(email="dana@silvercreek.example", password=PASSWORD, device=DEVICE, tenant=SC, name="Van 14 tablet"):
    return Client().post(
        api_path("/auth/token", tenant),
        data={"email": email, "password": password, "device_id": device, "device_name": name},
        content_type=JSON,
    )


def _bearer(access: str) -> dict:
    return {"HTTP_AUTHORIZATION": f"Bearer {access}"}


def _get(path, access, tenant=SC):
    return Client().get(api_path(path, tenant), **_bearer(access))


def _post(path, access, payload=None, tenant=SC):
    return Client().post(api_path(path, tenant), data=payload or {}, content_type=JSON, **_bearer(access))


def _reason(response):
    return json.loads(response.content).get("params", {}).get("reason")


# ── POST auth/token ──────────────────────────────────────────────────────────
def test_sign_in_returns_a_one_hour_access_token_and_stores_only_hashes(field):
    response = _token()
    assert response.status_code == 201, response.content
    body = response.json()
    assert body["token_type"] == "Bearer"
    assert body["expires_in"] == 3600
    assert body["access_token"].startswith("sbh_fa_") and body["refresh_token"].startswith("sbh_fr_")
    assert body["user"]["display_name"] == "Dana Ortiz" and body["user"]["role"] == "field_technician"
    assert body["device"] == {"device_id": DEVICE, "name": "Van 14 tablet"}
    with writing_as_tenant(field.silvercreek):
        rows = list(NativeToken.objects.filter(user=field.dana))
    assert {r.kind for r in rows} == {"access", "refresh"}
    stored = {r.token_hash for r in rows}
    assert body["access_token"] not in stored and body["refresh_token"] not in stored
    assert native.hash_token(body["access_token"]) in stored
    assert "auth.token_issued" in field.actions()


def test_a_bearer_reaches_the_field_routes(field):
    access = _token().json()["access_token"]
    assert _get("/work/mobile/today", access).status_code == 200
    assert _get("/work/mobile/devices", access).status_code == 200


def test_a_bearer_reaches_nothing_but_the_field_routes(field):
    access = _token().json()["access_token"]
    assert _get("/me", access).status_code == 401
    assert _get("/users", access).status_code == 401


def test_no_device_id_is_refused(field):
    response = Client().post(
        api_path("/auth/token"),
        data={"email": "dana@silvercreek.example", "password": PASSWORD},
        content_type=JSON,
    )
    assert response.status_code == 422


def test_wrong_password_is_the_one_generic_failure(field):
    response = _token(password="nope")
    assert response.status_code == 401
    assert response.json()["message_key"] == "errors.auth.sign_in_failed"


def test_brute_force_locks_the_login_on_the_native_door_too(field):
    for _ in range(5):  # the utility's default lockout count
        assert _token(password="wrong-guess").status_code == 401
    locked = _token()  # the RIGHT password, while locked
    assert locked.status_code == 401
    assert "auth.lockout" in field.actions()
    field.clock.advance(minutes=16)
    assert _token().status_code == 201


def test_a_temporary_password_is_sent_to_activation_not_signed_in(field):
    field.make_user(
        field.silvercreek, "tess@silvercreek.example", "Tess Lane", password="Temp-Tess-2026",
        role="field_technician", status=TenantMembership.STATUS_INVITED, must_change=True,
        temp_expires=field.clock() + timedelta(days=7),
    )
    response = _token(email="tess@silvercreek.example", password="Temp-Tess-2026")
    assert response.status_code == 403
    assert _reason(response) == "password_change_required"


# ── expiry, refresh, revoke ─────────────────────────────────────────────────
def test_an_expired_access_token_is_refused_and_says_so(field):
    access = _token().json()["access_token"]
    field.clock.advance(minutes=61)
    response = _get("/work/mobile/devices", access)
    assert response.status_code == 401
    assert _reason(response) == "access_token_expired"


def test_refresh_works_once_and_a_second_use_ends_the_sign_in(field):
    first = _token().json()
    refresh = Client().post(
        api_path("/auth/token/refresh"),
        data={"refresh_token": first["refresh_token"], "device_id": DEVICE},
        content_type=JSON,
    )
    assert refresh.status_code == 200, refresh.content
    second = refresh.json()
    assert second["access_token"] != first["access_token"]
    assert _get("/work/mobile/devices", second["access_token"]).status_code == 200
    # the old access token was rotated out
    assert _get("/work/mobile/devices", first["access_token"]).status_code == 401

    again = Client().post(
        api_path("/auth/token/refresh"), data={"refresh_token": first["refresh_token"]}, content_type=JSON
    )
    assert again.status_code == 401
    assert _reason(again) == "token_revoked"
    # reuse revoked the whole family — the NEW pair is dead too
    assert _get("/work/mobile/devices", second["access_token"]).status_code == 401
    assert "auth.token_reuse_detected" in field.actions()
    assert "auth.token_refreshed" in field.actions()


def test_refresh_from_another_handset_is_refused(field):
    first = _token().json()
    response = Client().post(
        api_path("/auth/token/refresh"),
        data={"refresh_token": first["refresh_token"], "device_id": "some-other-phone"},
        content_type=JSON,
    )
    assert response.status_code == 401


def test_revoke_signs_out_this_sign_in(field):
    first = _token().json()
    response = Client().delete(api_path("/auth/token"), **_bearer(first["access_token"]))
    assert response.status_code == 204
    refused = _get("/work/mobile/devices", first["access_token"])
    assert refused.status_code == 401 and _reason(refused) == "token_revoked"
    stale = Client().post(
        api_path("/auth/token/refresh"), data={"refresh_token": first["refresh_token"]}, content_type=JSON
    )
    assert stale.status_code == 401
    assert "auth.token_revoked" in field.actions()


def test_a_deactivated_technician_is_refused_mid_token(field):
    access = _token().json()["access_token"]
    with writing_as_tenant(field.silvercreek):
        TenantMembership.objects.filter(pk=field.dana_m.pk).update(
            status=TenantMembership.STATUS_DEACTIVATED
        )
    assert _get("/work/mobile/devices", access).status_code == 401


# ── BR-IDN-006: a token on another tenant's path is a 404 ───────────────────
def test_a_token_on_another_tenants_path_is_404_like_the_cookie(field):
    field.seed_bluemesa_admin()
    access = _token().json()["access_token"]
    # `today` and not `devices`: `today` answers 200 with an EMPTY DAY for a
    # login with no profile, so only the auth class's tenant check can make it
    # a 404 — `devices` 404s on its own and hid a sabotaged guard (red proof,
    # 2026-10-21).
    foreign = _get("/work/mobile/today", access, tenant=BM)
    assert foreign.status_code == 404
    assert _get("/work/mobile/devices", access, tenant=BM).status_code == 404
    # byte-identical to a plain not-found (HR-1)
    body = foreign.json()
    body.pop("trace_id")
    assert body == {
        "code": None, "message_key": "errors.not-found", "params": {}, "field_errors": [], "br_ref": None,
    }
    # and the same token still works at home
    assert _get("/work/mobile/devices", access).status_code == 200


def test_a_refresh_token_on_another_tenants_path_is_404(field):
    field.seed_bluemesa_admin()
    refresh = _token().json()["refresh_token"]
    response = Client().post(
        api_path("/auth/token/refresh", BM), data={"refresh_token": refresh}, content_type=JSON
    )
    assert response.status_code == 404


# ── devices and the office's remote sign-out ────────────────────────────────
def _register(access, **payload):
    return _post("/work/mobile/devices", access, {"name": "Van 14 tablet", "platform": "android", **payload})


def test_a_handset_registers_by_name_without_a_push_token(field):
    access = _token().json()["access_token"]
    response = _register(access)
    assert response.status_code == 200, response.content
    body = response.json()
    assert body["device_uid"] == DEVICE and body["name"] == "Van 14 tablet"
    assert body["push_registered"] is False and body["created"] is True
    listing = _get("/work/mobile/devices", access).json()
    assert listing["count"] == 1 and listing["results"][0]["name"] == "Van 14 tablet"
    # the device id came from the CREDENTIAL — a body naming another is ignored
    other = _register(access, device_id="spoofed-handset")
    assert other.json()["device_uid"] == DEVICE


def test_a_push_token_is_optional_and_never_echoed(field):
    access = _token().json()["access_token"]
    body = _register(access, push_token="fcm-token-abcdef123456").json()
    assert body["push_registered"] is True and body["last_four"] == "3456"
    assert "fcm-token-abcdef123456" not in json.dumps(body)


def test_the_web_push_registration_is_unchanged(field):
    client = signed_in_client("priya@silvercreek.example", "Meadow2026sage")
    # Priya is a clerk with no technician profile: the old refusal, unchanged
    response = client.post(api_path("/work/mobile/devices"), data={"token": "x"}, content_type=JSON)
    assert response.status_code == 404


def test_office_remote_sign_out_tells_the_phone_and_holds_its_captures(field):
    signin = _token().json()
    access = signin["access_token"]
    device = _register(access).json()
    capture = _post("/work/mobile/capture-token", access).json()
    assert capture["device"]["device_id"] == device["device_id"]

    office = signed_in_client("alex@silvercreek.example", "Canyon2026rapids")
    listing = office.get(api_path("/work/technicians/dana-ortiz/devices"))
    assert listing.status_code == 200 and listing.json()["count"] == 1
    out = office.post(
        api_path(f"/work/technicians/dana-ortiz/devices/{device['device_id']}/sign-out"),
        content_type=JSON,
    )
    assert out.status_code == 200, out.content
    assert out.json()["signed_out"] is True and out.json()["tokens_revoked"] == 2

    # the signal: 401 with params.reason = device_signed_out, on a call AND on refresh
    refused = _get("/work/mobile/devices", access)
    assert refused.status_code == 401 and _reason(refused) == "device_signed_out"
    stale = Client().post(
        api_path("/auth/token/refresh"), data={"refresh_token": signin["refresh_token"]}, content_type=JSON
    )
    assert stale.status_code == 401 and _reason(stale) == "device_signed_out"

    # a capture credential minted before the sign-out: refused on the strict
    # read, and on the sync's second read the captor is named — HELD, not lost
    with core_tenancy.tenant_context(field.silvercreek.id):
        from core import errors

        with pytest.raises(errors.AuthError) as strict:
            mobile.captor_from_token(capture["capture_token"])
        actor, tech = mobile.captor_from_token(capture["capture_token"], allow_expired=True)
    assert strict.value.message_key == "work.mobile.capture_token_expired"
    assert tech.id == field.tech.id
    assert "work.device_signed_out" in field.actions()
    assert "auth.device_tokens_revoked" in field.actions()

    # a fresh password sign-in and re-registration works again
    again = _token().json()["access_token"]
    assert _register(again).json()["signed_out"] is False
    assert _post("/work/mobile/capture-token", again).status_code == 200


def test_another_technicians_device_cannot_be_signed_out_by_slug_mismatch(field):
    access = _token().json()["access_token"]
    device = _register(access).json()
    office = signed_in_client("alex@silvercreek.example", "Canyon2026rapids")
    response = office.post(
        api_path(f"/work/technicians/nobody-here/devices/{device['device_id']}/sign-out"),
        content_type=JSON,
    )
    assert response.status_code == 404


# ── the capture credential, bound to the registration ───────────────────────
def test_capture_token_needs_a_registered_handset_and_carries_the_signed_life(field):
    access = _token().json()["access_token"]
    unregistered = _post("/work/mobile/capture-token", access)
    assert unregistered.status_code == 409
    assert _reason(unregistered) == "device_not_registered"
    _register(access)
    issued = _post("/work/mobile/capture-token", access).json()
    # BR-WRK-060's 7 days is the SEED of the utility's setting (PO 2026-10-21).
    assert issued["max_age_seconds"] == 7 * 24 * 3600
    with core_tenancy.tenant_context(field.silvercreek.id):
        _actor, tech = mobile.captor_from_token(issued["capture_token"])
    assert tech.id == field.tech.id


def test_capture_life_is_the_utilitys_setting_not_the_processs(field, settings):
    """PO 2026-10-21, *"this should come from settings"*: the retired process
    setting moves nothing; the Security tab's `field_capture_hours` does
    (`tests/test_cr187_field_capture_setting.py` owns the rest)."""
    from apps.identity.models import SecurityPolicy

    settings.WORK_CAPTURE_TOKEN_MAX_AGE_S = 36 * 3600  # retired — ignored
    access = _token().json()["access_token"]
    _register(access)
    assert _post("/work/mobile/capture-token", access).json()["max_age_seconds"] == 7 * 24 * 3600
    with writing_as_tenant(field.silvercreek):
        SecurityPolicy.objects.update_or_create(
            tenant_id=field.silvercreek.id, defaults={"field_capture_hours": 36}
        )
    assert _post("/work/mobile/capture-token", access).json()["max_age_seconds"] == 36 * 3600


# ── activation (FF-56 / FF-57) ──────────────────────────────────────────────
def _office_adds_technician(field, email="marco@silvercreek.example", name="Marco Ruiz"):
    office = signed_in_client("alex@silvercreek.example", "Canyon2026rapids")
    response = office.post(
        api_path("/users"), data={"full_name": name, "email": email, "role": "field_technician"},
        content_type=JSON,
    )
    assert response.status_code == 201, response.content
    return office, response.json()


def _check(code, email):
    return Client().post(
        api_path("/auth/activation/check"), data={"code": code, "email": email}, content_type=JSON
    )


def _complete(ticket, password="Harbor2026light", device="marco-phone", name="Marco's phone"):
    return Client().post(
        api_path("/auth/activation/complete"),
        data={"activation_ticket": ticket, "password": password, "device_id": device, "device_name": name},
        content_type=JSON,
    )


def test_the_office_gets_a_code_when_it_adds_a_technician(field):
    _office, body = _office_adds_technician(field)
    code = body["activation_code"]
    assert len(code) == 6 and code.isalnum() and code.upper() == code
    with writing_as_tenant(field.silvercreek):
        stored = list(ActivationCode.objects.values_list("code_hmac", flat=True))
    assert code not in stored  # an HMAC, never the code
    assert "auth.activation_code_issued" in field.actions()


def test_an_office_user_gets_no_code(field):
    office = signed_in_client("alex@silvercreek.example", "Canyon2026rapids")
    response = office.post(
        api_path("/users"),
        data={"full_name": "Pat", "email": "pat@silvercreek.example", "role": "billing_clerk"},
        content_type=JSON,
    )
    assert response.status_code == 201 and "activation_code" not in response.json()


def test_activation_check_then_complete_signs_in(field):
    _office, body = _office_adds_technician(field)
    code = body["activation_code"]
    checked = _check(code[:3].lower() + " " + code[3:], "Marco@SilverCreek.example")
    assert checked.status_code == 200, checked.content
    info = checked.json()
    assert info["display_name"] == "Marco Ruiz" and info["role"] == "field_technician"
    assert info["utility_name"] == "Silver Creek Water"
    assert info["password_policy"]["min_length"] == 8
    done = _complete(info["activation_ticket"])
    assert done.status_code == 201, done.content
    tokens = done.json()
    assert tokens["device"] == {"device_id": "marco-phone", "name": "Marco's phone"}
    assert "auth.activation_completed" in field.actions()
    # the membership is active and the password is the technician's own
    signin = _token(email="marco@silvercreek.example", password="Harbor2026light", device="marco-phone")
    assert signin.status_code == 201


def test_activation_code_is_single_use(field):
    _office, body = _office_adds_technician(field)
    info = _check(body["activation_code"], "marco@silvercreek.example").json()
    assert _complete(info["activation_ticket"]).status_code == 201
    assert _complete(info["activation_ticket"], password="Another2026pass").status_code == 401
    assert _check(body["activation_code"], "marco@silvercreek.example").status_code == 401


def test_activation_code_expires_after_seven_days(field):
    _office, body = _office_adds_technician(field)
    field.clock.advance(days=7, minutes=1)
    response = _check(body["activation_code"], "marco@silvercreek.example")
    assert response.status_code == 401
    assert _reason(response) == "activation_code_not_accepted"


def test_activation_wrong_email_is_refused_and_five_burn_the_code(field):
    _office, body = _office_adds_technician(field)
    code = body["activation_code"]
    for _ in range(5):
        wrong = _check(code, "someone@else.example")
        assert wrong.status_code == 401 and _reason(wrong) == "activation_code_not_accepted"
    # burnt: even the right email is refused now
    assert _check(code, "marco@silvercreek.example").status_code == 401
    assert "auth.activation_failed" in field.actions()


def test_activation_burn_count_is_the_utilitys_lockout_setting(field):
    """PO 2026-10-22, *"this should come from security settings"*: a utility
    whose Settings › Security lockout count is 3 burns a code at the third
    wrong email, not the fifth."""
    from apps.identity.models import SecurityPolicy

    with writing_as_tenant(field.silvercreek):
        SecurityPolicy.objects.update_or_create(
            tenant_id=field.silvercreek.id, defaults={"lockout_max_failed": 3}
        )
    _office, body = _office_adds_technician(field)
    code = body["activation_code"]
    for _ in range(3):
        assert _check(code, "someone@else.example").status_code == 401
    assert _check(code, "marco@silvercreek.example").status_code == 401


def test_activation_refuses_a_weak_password_without_burning_the_code(field):
    _office, body = _office_adds_technician(field)
    info = _check(body["activation_code"], "marco@silvercreek.example").json()
    weak = _complete(info["activation_ticket"], password="short")
    assert weak.status_code == 422
    assert _complete(info["activation_ticket"]).status_code == 201


def test_a_new_code_voids_the_old_one(field):
    office, body = _office_adds_technician(field)
    user_id = body["user"]["id"]
    again = office.post(api_path(f"/users/{user_id}/activation-code"), content_type=JSON)
    assert again.status_code == 201
    assert _check(body["activation_code"], "marco@silvercreek.example").status_code == 401
    assert _check(again.json()["activation_code"], "marco@silvercreek.example").status_code == 200


def test_activation_is_rate_limited(field):
    for _ in range(10):
        _check("ZZZZZZ", "x@y.example")
    assert _check("ZZZZZZ", "x@y.example").status_code == 429


# ── the cookie path is unchanged, and the bearer is where it should be ──────
def test_the_web_cookie_still_signs_in_and_reaches_the_field_routes(field):
    client = signed_in_client("alex@silvercreek.example", "Canyon2026rapids")
    assert client.get(api_path("/me")).status_code == 200
    assert client.get(api_path("/work/mobile/today")).status_code == 200


def _routes():
    def walk(resolver, prefix=""):
        for pattern in resolver.url_patterns:
            if hasattr(pattern, "url_patterns"):
                yield from walk(pattern, prefix + str(pattern.pattern))
            else:
                yield prefix + str(pattern.pattern), getattr(pattern.callback, "cls", None)

    for route, cls in walk(get_resolver()):
        yield route.replace("^api/[-a-zA-Z0-9_]+/", "api/{tenant}/"), cls


def test_the_bearer_is_on_every_field_route_and_on_nothing_else():
    """A route added under `work/mobile/` by ANY module goes red here until it
    takes the bearer; the bearer appearing anywhere else goes red too."""
    field_routes, missing, elsewhere = [], [], []
    for route, cls in _routes():
        if cls is None:
            continue
        has_bearer = NativeBearerAuthentication in list(cls.authentication_classes)
        if route.startswith("api/{tenant}/work/mobile/"):
            field_routes.append(route)
            if list(cls.authentication_classes) != [NativeBearerAuthentication, IdentitySessionAuthentication]:
                missing.append(route)
        elif has_bearer:
            elsewhere.append(route)
    assert len(field_routes) >= 15, field_routes  # 19 on 2026-10-21
    assert missing == [] and elsewhere == []
