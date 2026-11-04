# ── Trace ──────────────────────────────────────────────
# Story:    US-IDN-005 — add a user (admin-set temporary password, no-email v1;
#           EP-IDN-02, S8)
# Rules:    BR-IDN-005/008/009/010/011/021/022/025 (+ BR-IDN-029 · BR-IDN-030
#           add-on-deactivated-email → 409 pointing to Reactivate, PO 2026-08-09)
# Tests:    per-TC below; TC-9's RLS half = G5 suite
# ───────────────────────────────────────────────────────
"""US-IDN-005 TCs: create → invited + one-time temp password → first sign-in
activation; duplicates, resets, lockout."""

import re
from datetime import timedelta

import pytest
from django.test import Client

from apps.identity.models import TenantMembership, User
from tests.test_us_idn_helpers import (  # noqa: F401 (fixture import)
    BM,
    api_get,
    api_post,
    api_sign_in,
    idn,
    signed_in_client,
)

pytestmark = pytest.mark.django_db

TEMP_PASSWORD_SHAPE = re.compile(r"^[A-Za-z2-9]{4}-[A-Za-z2-9]{4}-[A-Za-z2-9]{4}$")


def _add(client, full_name, email, role="billing_clerk", tenant=None):
    payload = {"full_name": full_name, "email": email, "role": role}
    if tenant:
        return api_post(client, "/users", payload, tenant=tenant)
    return api_post(client, "/users", payload)


def test_us_idn_005_tc1__create_user_invited_with_one_time_temp_password(idn):
    users = idn.seed_silvercreek()
    alex = signed_in_client("alex@silvercreek.example", "Canyon2026rapids")
    response = _add(alex, "Tom Nguyen", "tom@silvercreek.example")
    assert response.status_code == 201
    body = response.json()
    assert TEMP_PASSWORD_SHAPE.match(body["temp_password"])  # displayed exactly once
    assert body["user"]["status"] == "invited"
    assert body["user"]["role"] == "billing_clerk"
    tom = User.objects.get(tenant=idn.silvercreek, email="tom@silvercreek.example")
    assert tom.must_change_password is True
    assert tom.temp_password_expires_at == idn.clock() + timedelta(days=7)  # BR-IDN-025
    membership = TenantMembership.objects.get(user=tom)
    assert membership.invited_by_id == users.alex.id
    (row,) = idn.rows_for("user.invited")
    assert row["actor_user_id"] == users.alex.id
    assert row["after"]["email"] == "t***@silvercreek.example"  # PII masked (BR-AUD-006)


def test_us_idn_005_tc2__email_existing_in_another_tenant_creates_fresh_user(idn):
    idn.seed_silvercreek()
    jordan_bm, _ = idn.seed_bluemesa_admin()
    bm_hash_before = jordan_bm.password_hash
    alex = signed_in_client("alex@silvercreek.example", "Canyon2026rapids")
    response = _add(alex, "Jordan Ellis", "jordan@bluemesa.example", role="executive")
    assert response.status_code == 201  # a NEW Silver Creek user (BR-IDN-029)
    temp = response.json()["temp_password"]
    jordan_bm.refresh_from_db()
    assert jordan_bm.password_hash == bm_hash_before  # Blue Mesa user untouched
    # First Silver Creek sign-in + forced change flips the SC membership active.
    sc_jordan = signed_in_client("jordan@bluemesa.example", temp)
    assert (
        api_post(
            sc_jordan,
            "/me/password",
            {"new_password": "Willow2026brook", "confirm_password": "Willow2026brook"},
        ).status_code
        == 204
    )
    sc_user = User.objects.get(tenant=idn.silvercreek, email="jordan@bluemesa.example")
    assert TenantMembership.objects.get(user=sc_user).status == "active"


def test_us_idn_005_tc3__duplicate_email_in_this_tenant_rejected(idn):
    idn.seed_silvercreek()
    alex = signed_in_client("alex@silvercreek.example", "Canyon2026rapids")
    response = _add(alex, "Priya Again", "priya@silvercreek.example")
    assert response.status_code == 409
    assert response.json()["message_key"] == "errors.identity.already_a_member"
    assert User.objects.filter(email__iexact="priya@silvercreek.example").count() == 1


def test_us_idn_005_br030__add_on_deactivated_email_409_points_to_reactivate(idn):
    # BR-IDN-030 (PO 2026-08-09): a deactivated email is never freed for
    # re-use; the returning person is REACTIVATED, never re-added.
    users = idn.seed_silvercreek()  # carla's membership is deactivated
    alex = signed_in_client("alex@silvercreek.example", "Canyon2026rapids")
    response = _add(alex, "Carla Ortiz", "carla@silvercreek.example")
    assert response.status_code == 409
    body = response.json()
    assert body["code"] == "BIZ-STATE"
    assert body["br_ref"] == "BR-IDN-030"
    assert body["message_key"] == "errors.identity.email_deactivated_reactivate"
    assert body["params"]["user_id"] == str(users.carla.id)  # → Reactivate row action
    assert User.objects.filter(email__iexact="carla@silvercreek.example").count() == 1


def test_us_idn_005_tc4__invalid_email_rejected_inline(idn):
    idn.seed_silvercreek()
    alex = signed_in_client("alex@silvercreek.example", "Canyon2026rapids")
    response = _add(alex, "No Body", "not-an-email")
    assert response.status_code == 422  # IS-7 inline validation
    assert User.objects.filter(tenant=idn.silvercreek).count() == 5  # nothing created


def test_us_idn_005_tc5__reset_temp_password_voids_the_prior_one(idn):
    users = idn.seed_silvercreek()  # marcus invited with temp "Temp-Mrcs-2026"
    alex = signed_in_client("alex@silvercreek.example", "Canyon2026rapids")
    response = api_post(alex, f"/users/{users.marcus.id}/temp-password")
    assert response.status_code == 200
    new_temp = response.json()["temp_password"]
    # The previous temp password is void immediately; the new one signs in.
    assert api_sign_in(Client(), "marcus@silvercreek.example", "Temp-Mrcs-2026").status_code == 401
    assert api_sign_in(Client(), "marcus@silvercreek.example", new_temp).status_code == 201
    (row,) = idn.rows_for("user.temp_password_reset")  # invited row = reset flavor
    assert row["actor_user_id"] == users.alex.id


def test_us_idn_005_tc6__first_sign_in_forced_change_activates_membership(idn):
    idn.seed_silvercreek()
    alex = signed_in_client("alex@silvercreek.example", "Canyon2026rapids")
    temp = _add(alex, "Tom Nguyen", "tom@silvercreek.example").json()["temp_password"]
    idn.clock.advance(days=3)
    tom = signed_in_client("tom@silvercreek.example", temp)
    assert (
        api_post(
            tom,
            "/me/password",
            {"new_password": "Willow2026brook", "confirm_password": "Willow2026brook"},
        ).status_code
        == 204
    )
    tom_user = User.objects.get(tenant=idn.silvercreek, email="tom@silvercreek.example")
    assert tom_user.must_change_password is False
    assert TenantMembership.objects.get(user=tom_user).status == "active"  # BR-IDN-011
    assert len(idn.rows_for("auth.password_reset")) == 1
    # Row shows his name (it was captured at creation) — list half in US-IDN-004.
    assert tom_user.full_name == "Tom Nguyen"


def test_us_idn_005_tc7__voided_or_expired_temp_password_fails_generically(idn):
    users = idn.seed_silvercreek()
    alex = signed_in_client("alex@silvercreek.example", "Canyon2026rapids")
    # Voided by a reset:
    api_post(alex, f"/users/{users.marcus.id}/temp-password")
    voided = api_sign_in(Client(), "marcus@silvercreek.example", "Temp-Mrcs-2026")
    assert voided.status_code == 401
    assert voided.json()["message_key"] == "errors.auth.sign_in_failed"
    # Expired on day 8 (BR-IDN-025):
    temp = _add(alex, "Tom Nguyen", "tom@silvercreek.example").json()["temp_password"]
    idn.clock.advance(days=8)
    expired = api_sign_in(Client(), "tom@silvercreek.example", temp)
    assert expired.status_code == 401
    assert expired.json()["message_key"] == "errors.auth.sign_in_failed"


def test_us_idn_005_tc8__executive_calling_create_gets_403(idn):
    idn.seed_silvercreek()
    diana = signed_in_client("diana@silvercreek.example", "Vista2026peak")
    response = _add(diana, "No Body", "nobody@silvercreek.example")
    assert response.status_code == 403  # server-side (BR-IDN-009)
    assert not User.objects.filter(email__iexact="nobody@silvercreek.example").exists()


def test_us_idn_005_tc9__new_user_invisible_in_the_other_tenant(idn):
    # App-filter half; RLS half = G5 suite.
    idn.seed_silvercreek()
    idn.seed_bluemesa_admin()
    alex = signed_in_client("alex@silvercreek.example", "Canyon2026rapids")
    _add(alex, "Tom Nguyen", "tom@silvercreek.example")
    jordan = signed_in_client("jordan@bluemesa.example", "Mesa2026bluff", tenant=BM)
    rows = api_get(jordan, "/users", tenant=BM).json()["results"]
    assert "tom@silvercreek.example" not in [row["email"] for row in rows]


def test_us_idn_005_tc10__lockout_applies_to_temp_password_attempts(idn):
    idn.seed_silvercreek()
    alex = signed_in_client("alex@silvercreek.example", "Canyon2026rapids")
    temp = _add(alex, "Tom Nguyen", "tom@silvercreek.example").json()["temp_password"]
    for _ in range(5):
        assert (
            api_sign_in(Client(), "tom@silvercreek.example", "Wrong-Temp-0000").status_code == 401
        )
    assert len(idn.rows_for("auth.lockout")) == 1
    # 6th attempt with the CORRECT temp password — refused (15-minute lock).
    refused = api_sign_in(Client(), "tom@silvercreek.example", temp)
    assert refused.status_code == 401
    assert refused.json()["message_key"] == "errors.auth.sign_in_failed"
