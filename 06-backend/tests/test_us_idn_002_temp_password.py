# ── Trace ──────────────────────────────────────────────
# Story:    US-IDN-002 — forgot password / admin-issued temporary password
#           (no-email v1; EP-IDN-01, S3/S8)
# Rules:    BR-IDN-002/005/016/021/022/023/025
# Tests:    per-TC below; TC-8's RLS half = G5 suite (app-filter half runs here)
# ───────────────────────────────────────────────────────
"""US-IDN-002 TCs. TC-1 is the forgot-password PAGE (BR-IDN-023 as amended
2026-10-05, `CR-170-BRC10`; until then an inline "Contact your administrator"
notice) — no endpoint is minted for it, so it has no backend half. The whole
flow's server half is `test_cr170_forgot_password_flow.py`."""

from datetime import timedelta

import pytest
from django.test import Client

from tests.isolation_helpers import (  # noqa: F401 (fixture import)
    assert_denied_without_context,
    assert_rls_scoped,
    assert_write_into_other_tenant_refused,
    live_tenant_context,
    requires_postgres,
    rls,
    rls_probe_role,
)
from tests.test_us_idn_helpers import (  # noqa: F401 (fixture import)
    BM,
    api_get,
    api_post,
    api_sign_in,
    idn,
    live_sessions_for,
    signed_in_client,
)

pytestmark = pytest.mark.django_db


@pytest.mark.skip(
    reason="TC-1 is the forgot-password page (CR-170-BRC10) — BR-IDN-023 mints no "
    "endpoint, no token, no email; nothing exists server-side to test (frontend-half "
    "only: forgotPassword.dom.test.tsx)"
)
def test_us_idn_002_tc1__forgot_password_static_notice():
    raise NotImplementedError


def test_us_idn_002_tc2__admin_issues_temp_password_shown_once(idn):
    users = idn.seed_silvercreek()
    alex = signed_in_client("alex@silvercreek.example", "Canyon2026rapids")
    response = api_post(alex, f"/users/{users.priya.id}/temp-password")
    assert response.status_code == 200
    body = response.json()
    assert len(body["temp_password"]) == 14  # Xxxx-Xxxx-Xxxx, displayed once
    users.priya.refresh_from_db()
    assert users.priya.must_change_password is True
    assert users.priya.temp_password_expires_at == idn.clock() + timedelta(days=7)
    (row,) = idn.rows_for("auth.temp_password_issued")  # active member = issue flavor
    assert row["actor_user_id"] == users.alex.id


def test_us_idn_002_tc3__temp_sign_in_forces_change_then_revokes_prior_sessions(idn):
    users = idn.seed_silvercreek()
    prior = signed_in_client("priya@silvercreek.example", "Meadow2026sage")
    alex = signed_in_client("alex@silvercreek.example", "Canyon2026rapids")
    temp = api_post(alex, f"/users/{users.priya.id}/temp-password").json()["temp_password"]

    idn.clock.advance(days=2)
    priya = signed_in_client("priya@silvercreek.example", temp)
    changed = api_post(
        priya,
        "/me/password",
        {"new_password": "Harbor2026tide", "confirm_password": "Harbor2026tide"},
    )
    assert changed.status_code == 204
    users.priya.refresh_from_db()
    assert users.priya.must_change_password is False
    assert live_sessions_for(users.priya) == 1  # ALL prior sessions revoked (BR-IDN-005)
    assert api_get(prior, "/me").status_code == 401
    assert len(idn.rows_for("auth.password_reset")) == 1
    assert api_get(priya, "/me").status_code == 200  # then Dashboard


def test_us_idn_002_tc4__temp_password_dead_after_change(idn):
    users = idn.seed_silvercreek()
    alex = signed_in_client("alex@silvercreek.example", "Canyon2026rapids")
    temp = api_post(alex, f"/users/{users.priya.id}/temp-password").json()["temp_password"]
    priya = signed_in_client("priya@silvercreek.example", temp)
    api_post(
        priya,
        "/me/password",
        {"new_password": "Harbor2026tide", "confirm_password": "Harbor2026tide"},
    )
    replay = api_sign_in(Client(), "priya@silvercreek.example", temp)
    assert replay.status_code == 401
    assert replay.json()["message_key"] == "errors.auth.sign_in_failed"


def test_us_idn_002_tc5__temp_password_expired_on_day_eight(idn):
    users = idn.seed_silvercreek()
    alex = signed_in_client("alex@silvercreek.example", "Canyon2026rapids")
    temp = api_post(alex, f"/users/{users.priya.id}/temp-password").json()["temp_password"]
    idn.clock.advance(days=8)
    response = api_sign_in(Client(), "priya@silvercreek.example", temp)
    assert response.status_code == 401
    assert response.json()["message_key"] == "errors.auth.sign_in_failed"


def test_us_idn_002_tc6__forced_change_rejects_policy_violating_password(idn):
    users = idn.seed_silvercreek()
    alex = signed_in_client("alex@silvercreek.example", "Canyon2026rapids")
    temp = api_post(alex, f"/users/{users.priya.id}/temp-password").json()["temp_password"]
    priya = signed_in_client("priya@silvercreek.example", temp)
    rejected = api_post(
        priya,
        "/me/password",
        {"new_password": "creekside", "confirm_password": "creekside"},  # no upper/number
    )
    assert rejected.status_code == 422
    fields = {e["field"] for e in rejected.json()["field_errors"]}
    assert fields == {"new_password"}
    users.priya.refresh_from_db()
    assert users.priya.must_change_password is True  # stays on the forced-change screen


def test_us_idn_002_tc7__every_app_surface_gated_until_change(idn):
    users = idn.seed_silvercreek()
    alex = signed_in_client("alex@silvercreek.example", "Canyon2026rapids")
    temp = api_post(alex, f"/users/{users.priya.id}/temp-password").json()["temp_password"]
    priya = signed_in_client("priya@silvercreek.example", temp)
    gated = api_get(priya, "/me")  # any app request before completing the change
    assert gated.status_code == 403
    assert gated.json()["message_key"] == "errors.auth.password_change_required"
    assert gated.json()["br_ref"] == "BR-IDN-022"


def test_us_idn_002_tc8__cross_tenant_issue_returns_404(idn):
    # App-filter half: under Blue Mesa's scope Priya's id is ABSENT → 404 with
    # a body identical to plain not-found (HR-1). RLS half = G5 suite.
    users = idn.seed_silvercreek()
    idn.seed_bluemesa_admin()
    jordan = signed_in_client("jordan@bluemesa.example", "Mesa2026bluff", tenant=BM)
    response = api_post(jordan, f"/users/{users.priya.id}/temp-password", tenant=BM)
    assert response.status_code == 404
    users.priya.refresh_from_db()
    assert users.priya.must_change_password is False  # nothing changed


@pytest.mark.isolation
@requires_postgres
def test_us_idn_002_tc8_rls__cross_tenant_row_invisible_under_rls(idn, rls):
    """US-IDN-002 TC-8, RLS half — the 404 above holds even with no app filter.

    The app-filter half proves the endpoint answers 404. This proves the row is
    not merely filtered but UNREACHABLE under Blue Mesa's `app.tenant_id`: a
    forged lookup by id returns nothing, and a forged write (the temp-password
    reset itself, as raw DML) touches zero rows and leaves Priya untouched.
    """
    users = idn.seed_silvercreek()
    idn.seed_bluemesa_admin()

    assert_rls_scoped(
        rls,
        "users",
        owner=idn.silvercreek,
        intruder=idn.bluemesa,
        owner_ids={str(users.priya.id)},
    )
    with live_tenant_context(idn.bluemesa.id):
        assert rls.count("users", "id = %s", [str(users.priya.id)]) == 0
        # The write half: Blue Mesa cannot force Priya onto the change screen.
        assert (
            rls.affected(
                "UPDATE users SET must_change_password = true WHERE id = %s",
                [str(users.priya.id)],
            )
            == 0
        )
    # Re-read AS SILVER CREEK. The row is Silver Creek's, so its own context is
    # the only one that can see it — reading with context cleared now returns
    # zero rows and raises `User.DoesNotExist`, which is the deny-by-default
    # half of hard rule 1 doing its job, not the row having gone.
    with live_tenant_context(idn.silvercreek.id):
        users.priya.refresh_from_db()
    assert users.priya.must_change_password is False  # nothing changed

    # And Blue Mesa cannot claim her row for itself (policy WITH CHECK).
    assert_write_into_other_tenant_refused(
        rls, "users", owner=idn.silvercreek, intruder=idn.bluemesa
    )
    assert_denied_without_context(rls, "users")
