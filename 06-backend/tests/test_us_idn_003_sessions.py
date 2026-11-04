# ── Trace ──────────────────────────────────────────────
# Story:    US-IDN-003 — sessions and sign-out (EP-IDN-01, S48)
# Rules:    BR-IDN-006/007/026
# Tests:    per-TC below (sqlite tier; sessions is a platform table, no RLS half)
# ───────────────────────────────────────────────────────
"""US-IDN-003 TCs: server-side sessions — sign-out, idle/absolute expiry,
one-tenant binding, trusted-device refresh."""

import pytest

from apps.identity.models import SecurityPolicy, Session
from tests.test_us_idn_helpers import (  # noqa: F401 (fixture import)
    BM,
    SC,
    api_delete,
    api_get,
    api_sign_in,
    client_with_session,
    idn,
    random_uuid,
    session_id_of,
    signed_in_client,
)

pytestmark = pytest.mark.django_db


def test_us_idn_003_tc1__sign_out_revokes_server_side_and_audits(idn):
    users = idn.seed_silvercreek()
    alex = signed_in_client("alex@silvercreek.example", "Canyon2026rapids")
    response = api_delete(alex, "/auth/session")
    assert response.status_code == 204
    session = Session.objects.get(user=users.alex)
    assert session.revoked_at is not None  # revoked server-side, immediately
    (row,) = idn.rows_for("auth.sign_out")
    assert row["actor_user_id"] == users.alex.id


def test_us_idn_003_tc2__replayed_token_after_sign_out_is_401(idn):
    idn.seed_silvercreek()
    alex = signed_in_client("alex@silvercreek.example", "Canyon2026rapids")
    sid = session_id_of(alex)
    api_delete(alex, "/auth/session")
    replay = api_get(client_with_session(sid), "/me")
    assert replay.status_code == 401  # no data returned


def test_us_idn_003_tc3__idle_past_tenant_timeout_is_401(idn):
    idn.seed_silvercreek()
    SecurityPolicy.objects.create(tenant=idn.silvercreek, session_timeout_minutes=30)
    priya = signed_in_client("priya@silvercreek.example", "Meadow2026sage")
    idn.clock.advance(minutes=31)
    assert api_get(priya, "/me").status_code == 401


def test_us_idn_003_tc4__activity_slides_the_idle_window(idn):
    idn.seed_silvercreek()
    SecurityPolicy.objects.create(tenant=idn.silvercreek, session_timeout_minutes=30)
    priya = signed_in_client("priya@silvercreek.example", "Meadow2026sage")
    for _ in range(3):  # active every 20 minutes — 60 min of wall clock, no timeout
        idn.clock.advance(minutes=20)
        assert api_get(priya, "/me").status_code == 200
    idn.clock.advance(minutes=31)  # then idle past the window
    assert api_get(priya, "/me").status_code == 401


def test_us_idn_003_tc5__valid_looking_but_unknown_session_id_is_401(idn):
    idn.seed_silvercreek()
    response = api_get(client_with_session(random_uuid()), "/me")
    assert response.status_code == 401  # attempt lands in the security log


def test_us_idn_003_tc6__session_is_bound_to_one_tenant(idn):
    """AMENDED 2026-08-10 (PO path-tenancy ruling): the refusal is 404, not 401.

    Under subdomains a cross-tenant cookie was an accident the browser made
    almost impossible, and 401 "sign in again" was a fair answer. Under one
    origin it is the attack, and the answer must not distinguish "wrong tenant
    for this session" from "no such tenant" — see
    tests/test_path_tenancy_session_binding.py, which owns the full proof.
    """
    idn.seed_silvercreek()
    idn.seed_bluemesa_admin()
    jordan = signed_in_client("jordan@bluemesa.example", "Mesa2026bluff", tenant=BM)
    sid = session_id_of(jordan)
    cross = api_get(client_with_session(sid), "/me", tenant=SC)
    assert cross.status_code == 404  # no Silver Creek data, and no confirmation it exists


def test_us_idn_003_tc7__absolute_twelve_hour_cap_even_when_active(idn):
    idn.seed_silvercreek()
    SecurityPolicy.objects.create(tenant=idn.silvercreek, session_timeout_minutes=480)
    alex = signed_in_client("alex@silvercreek.example", "Canyon2026rapids")
    for _ in range(3):  # continuously active: touch every 4 h
        idn.clock.advance(hours=4)
        api_get(alex, "/me")
    # 12 h mark passed on the last advance — this request went through only if
    # still inside; the NEXT request after the mark must be 401.
    idn.clock.advance(minutes=1)
    assert api_get(alex, "/me").status_code == 401  # BR-IDN-026; fresh sign-in required


def test_us_idn_003_tc8__keep_me_signed_in_thirty_day_refresh(idn):
    idn.seed_silvercreek()
    # Checked (persistent): a 2-day-old session silently re-establishes.
    priya = signed_in_client("priya@silvercreek.example", "Meadow2026sage", keep_signed_in=True)
    idn.clock.advance(days=2)
    assert api_get(priya, "/me").status_code == 200
    # Past the 30-day trusted-device window: full sign-in required.
    idn.clock.advance(days=31)
    assert api_get(priya, "/me").status_code == 401
    # Unchecked (the default): no refresh — normal idle/absolute limits only.
    plain = signed_in_client("priya@silvercreek.example", "Meadow2026sage")
    idn.clock.advance(days=2)
    assert api_get(plain, "/me").status_code == 401
