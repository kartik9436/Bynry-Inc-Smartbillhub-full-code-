# ── Trace ──────────────────────────────────────────────
# Story:    US-IDN-001 — sign in with email and password (EP-IDN-01, S2/S3)
# Rules:    BR-IDN-001/002/003/025 (BR-IDN-004/028: 2FA TCs v2-deferred)
# Tests:    per-TC below; RLS halves of the isolation TCs = G5 suite (sqlite
#           cannot RLS — the app-filter half runs here honestly)
# ───────────────────────────────────────────────────────
"""US-IDN-001 TCs at the service/API tier (Django test client, sqlite)."""

import pytest
from django.test import Client

from apps.identity.models import Session
from tests.test_us_idn_helpers import (  # noqa: F401 (fixture import)
    SC,
    api_sign_in,
    body_without_trace,
    idn,
)

pytestmark = pytest.mark.django_db


def test_us_idn_001_tc1__correct_credentials_create_session_and_audit(idn):
    users = idn.seed_silvercreek()
    response = api_sign_in(Client(), "alex@silvercreek.example", "Canyon2026rapids")
    assert response.status_code == 201
    body = response.json()
    assert body["user"]["email"] == "alex@silvercreek.example"
    assert body["user"]["role"] == "system_admin"
    assert response.cookies["sbh_session"]["httponly"]
    session = Session.objects.get(user=users.alex)
    assert session.tenant_id == idn.silvercreek.id
    assert session.revoked_at is None
    # audit_log row auth.sign_in with actor + timestamp (timestamp = insert-time)
    (row,) = idn.rows_for("auth.sign_in")
    assert row["actor_user_id"] == users.alex.id
    users.alex_m.refresh_from_db()
    assert users.alex_m.last_active_at is not None


def test_us_idn_001_tc2__wrong_password_generic_error_no_session(idn):
    users = idn.seed_silvercreek()
    response = api_sign_in(Client(), "alex@silvercreek.example", "wrong-password")
    assert response.status_code == 401
    body = response.json()
    assert body["message_key"] == "errors.auth.sign_in_failed"  # the ONE message
    assert body["field_errors"] == []  # no field-level disclosure (BR-IDN-002)
    assert Session.objects.filter(user=users.alex).count() == 0


def test_us_idn_001_tc3__unknown_email_response_identical_to_wrong_password(idn):
    idn.seed_silvercreek()
    wrong_password = api_sign_in(Client(), "alex@silvercreek.example", "wrong-password")
    unknown_email = api_sign_in(Client(), "nobody@silvercreek.example", "whatever123")
    assert unknown_email.status_code == wrong_password.status_code == 401
    # Bodies identical modulo the per-response trace id — no user enumeration.
    assert body_without_trace(unknown_email) == body_without_trace(wrong_password)
    assert Session.objects.count() == 0


def test_us_idn_001_tc4__deactivated_membership_denied_generically(idn):
    users = idn.seed_silvercreek()
    response = api_sign_in(Client(), "carla@silvercreek.example", "River2026stone")
    assert response.status_code == 401
    assert response.json()["message_key"] == "errors.auth.sign_in_failed"
    assert Session.objects.filter(user=users.carla).count() == 0


@pytest.mark.skip(reason="v2-deferred — BR-IDN-028: no 2FA challenge ships in v1")
def test_us_idn_001_tc5__totp_challenge_v2():
    raise NotImplementedError


@pytest.mark.skip(reason="v2-deferred — BR-IDN-028: no 2FA requirement setting in v1")
def test_us_idn_001_tc6__forced_enrollment_v2():
    raise NotImplementedError


def test_us_idn_001_tc7__cross_tenant_credentials_denied(idn):
    # App half of the isolation TC: Jordan is a Blue Mesa user only — at the
    # silvercreek subdomain the (tenant, email) pair does not exist
    # (BR-IDN-029), so the one generic error answers. RLS half = G5 suite.
    idn.seed_silvercreek()
    jordan, _ = idn.seed_bluemesa_admin()
    response = api_sign_in(Client(), "jordan@bluemesa.example", "Mesa2026bluff", tenant=SC)
    assert response.status_code == 401
    assert response.json()["message_key"] == "errors.auth.sign_in_failed"
    assert Session.objects.filter(tenant=idn.silvercreek).count() == 0


def test_us_idn_001_tc8__five_failures_lock_fifteen_minutes(idn):
    users = idn.seed_silvercreek()
    for _ in range(5):
        assert api_sign_in(Client(), "alex@silvercreek.example", "bad-pass").status_code == 401
    assert len(idn.rows_for("auth.sign_in_failed")) == 5
    assert len(idn.rows_for("auth.lockout")) == 1
    # 6th attempt with the CORRECT password 2 minutes later — still refused.
    idn.clock.advance(minutes=2)
    locked = api_sign_in(Client(), "alex@silvercreek.example", "Canyon2026rapids")
    assert locked.status_code == 401
    # DEF-IDN-10620 (PO 2026-10-27): a lock is NAMED, with the utility's minutes.
    assert locked.json()["message_key"] == "auth.sign_in.locked"
    assert locked.json()["params"]["minutes"] == 15
    # After the 15-minute lock lapses, correct credentials sign in.
    idn.clock.advance(minutes=14)
    assert api_sign_in(Client(), "alex@silvercreek.example", "Canyon2026rapids").status_code == 201
    assert Session.objects.filter(user=users.alex).count() == 1
