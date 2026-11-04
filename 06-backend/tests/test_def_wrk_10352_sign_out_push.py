# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-WRK-10352 — a native sign-out left the handset's push token on
#           `work.TechnicianDevice`, so a technician who signed out of one
#           utility (to sign into another) went on getting its job alerts, and
#           so would the next person to pick the phone up.
# Rules:    BR-WRK-002 (identity asks work's service; never writes its table) ·
#           BR-WRK-059 (a push token follows the signed-in technician) ·
#           BR-WRK-060 / R132 (the registration and its capture credential stay)
# Tests:    this file (SQLite) · test_def_wrk_10352_sign_out_push_pg.py
# ───────────────────────────────────────────────────────
"""Sign out → the push token is gone, the registration row is not."""

from __future__ import annotations

import pytest
from django.test import Client

from apps.work import models as work_models
from tests.isolation_helpers import writing_as_tenant
from tests.test_cr187_native_auth import DEVICE, PASSWORD, _bearer, _post, _token, field  # noqa: F401
from tests.test_us_idn_helpers import BM, SC, api_path, idn  # noqa: F401

BM_PASSWORD = "Mesa2026sunrise"
PUSH = "ExponentPushToken[brazos-0001]"


def _register(access, tenant=SC, push=PUSH):
    return _post(
        "/work/mobile/devices",
        access,
        {"name": "Van 14 tablet", "platform": "android", "push_token": push},
        tenant=tenant,
    )


def _sign_out(access, tenant=SC):
    return Client().delete(api_path("/auth/token", tenant), **_bearer(access))


def _row(tenant, technician):
    with writing_as_tenant(tenant):
        return work_models.TechnicianDevice.objects.get(
            tenant=tenant, technician=technician, device_uid=DEVICE
        )


@pytest.fixture()
def two(field):  # noqa: F811
    """Dana at Silver Creek (from `field`) and Ben at Blue Mesa, same handset."""
    ben, _ = field.make_user(
        field.bluemesa, "ben@bluemesa.example", "Ben Okafor",
        password=BM_PASSWORD, role="field_technician",
    )
    with writing_as_tenant(field.bluemesa):
        field.ben_tech = work_models.Technician.objects.create(tenant=field.bluemesa, user=ben)
    return field


def test_sign_out_clears_the_push_token_and_keeps_the_row(two):
    access = _token().json()["access_token"]
    assert _register(access).status_code == 200
    before = _row(two.silvercreek, two.tech)
    assert before.token == PUSH

    assert _sign_out(access).status_code == 204
    after = _row(two.silvercreek, two.tech)
    assert after.pk == before.pk  # the row, and so the capture binding, stays
    assert after.token is None
    assert after.active is True and after.capture_epoch == before.capture_epoch
    assert after.device_uid == DEVICE
    assert "work.device_push_released" in two.actions()


def test_signing_in_again_and_registering_puts_the_token_back(two):
    access = _token().json()["access_token"]
    _register(access)
    _sign_out(access)
    again = _token().json()["access_token"]
    assert _register(again).status_code == 200
    assert _row(two.silvercreek, two.tech).token == PUSH


def test_sign_out_with_no_push_token_is_a_quiet_no_op(two):
    access = _token().json()["access_token"]
    assert _post(
        "/work/mobile/devices", access, {"name": "Van 14 tablet", "platform": "android"}
    ).status_code == 200
    assert _sign_out(access).status_code == 204
    assert _row(two.silvercreek, two.tech).token is None
    assert "work.device_push_released" not in two.actions()


def test_another_utility_on_the_same_handset_is_never_touched(two):
    """Brazos-and-Lone-Star's shape: the same phone registered at two utilities.
    Registering, and signing out, at B leaves A's row exactly as it was."""
    silver = _token().json()["access_token"]
    _register(silver)
    mesa = _token(email="ben@bluemesa.example", password=BM_PASSWORD, tenant=BM).json()[
        "access_token"
    ]
    assert _register(mesa, tenant=BM, push="ExponentPushToken[mesa-0002]").status_code == 200
    assert _row(two.silvercreek, two.tech).token == PUSH  # B's register: A untouched

    assert _sign_out(mesa, tenant=BM).status_code == 204
    assert _row(two.bluemesa, two.ben_tech).token is None
    assert _row(two.silvercreek, two.tech).token == PUSH  # B's sign-out: A untouched

    assert _sign_out(silver).status_code == 204
    assert _row(two.silvercreek, two.tech).token is None
