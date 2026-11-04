# ── Trace ──────────────────────────────────────────────
# Defects:  DEF-IDN-10022 (password expiry never enforced) · DEF-IDN-10023 (the
#           last-5 history the Security tab promises did not exist) ·
#           DEF-IDN-10024 (a polling page kept its session awake for ever)
# Ruling:   PO 2026-10-08 — decision log "THE SECURITY TAB'S SETTINGS ARE MADE
#           TRUE", verbatim: "go - build the last 5 passwords check"
# Rules:    BR-IDN-022 (forced change) · BR-IDN-025 (expiry setting, last-5
#           history, temp password 7 days) · BR-IDN-026 (idle sign-out) ·
#           CLAUDE.md hard rule 1 (RLS FORCE) · hard-won laws 1, 2, 7, 14
# Code:     apps/identity/services.py (password_expired, _refuse_reused_password,
#           _record_outgoing_password) · apps/identity/auth.py
#           (BACKGROUND_REFRESH_HEADER) · migrations/0010
# ───────────────────────────────────────────────────────
"""The three Security-tab settings that did not do what the screen said.

Runs on the default SQLite suite AND on PostgreSQL 16 (`--ds=config.settings.
pgtest`); the RLS cases at the bottom are PostgreSQL only, because SQLite has
no row-level security (hard-won law 14).

The worked figures are the ones put to the PO: a 90-day policy, a password
changed 91 days ago lands on the change-password page and one changed 89 days
ago signs in normally.
"""

from datetime import timedelta

import pytest
from django.test import Client

from apps.identity import services
from apps.identity.models import PasswordHistory, SecurityPolicy, Session, User
from tests.isolation_helpers import (  # noqa: F401 — `rls` needs `rls_probe_role`
    assert_denied_without_context,
    assert_rls_scoped,
    assert_write_into_other_tenant_refused,
    requires_postgres,
    rls,
    rls_probe_role,
    writing_as_tenant,
)
from tests.test_us_idn_helpers import (  # noqa: F401 (fixture import)
    api_get,
    api_post,
    api_sign_in,
    idn,
    session_id_of,
    signed_in_client,
)

pytestmark = pytest.mark.django_db

PRIYA = "priya@silvercreek.example"
PRIYA_PW = "Meadow2026sage"
REUSED = "errors.identity.password_recently_used"
BACKGROUND = {"HTTP_X_BACKGROUND_REFRESH": "1"}


def _policy(idn, **values):
    with writing_as_tenant(idn.silvercreek):
        SecurityPolicy.objects.create(tenant=idn.silvercreek, **values)


def _set_user(idn, user, **fields):
    with writing_as_tenant(idn.silvercreek):
        User.objects.filter(pk=user.pk).update(**fields)


def _change(client, new, current=None):
    body = {"new_password": new, "confirm_password": new}
    if current is not None:
        body["current_password"] = current
    return api_post(client, "/me/password", body)


# ── 1 · Password expiry (DEF-IDN-10022) ──────────────────────────────────────
def test_expiry_91_days_on_a_90_day_policy_lands_on_the_forced_change(idn):
    users = idn.seed_silvercreek()
    _policy(idn, pw_expiry_days=90)
    _set_user(idn, users.priya, password_changed_at=idn.clock() - timedelta(days=91))

    client = Client()
    response = api_sign_in(client, PRIYA, PRIYA_PW)
    assert response.status_code == 201
    assert response.json()["user"]["must_change_password"] is True
    gated = api_get(client, "/me")
    assert gated.status_code == 403
    assert gated.json()["message_key"] == "errors.auth.password_change_required"
    (row,) = idn.rows_for("auth.sign_in")
    assert row["after"]["password_expired"] is True


def test_expiry_89_days_on_a_90_day_policy_signs_in_normally(idn):
    users = idn.seed_silvercreek()
    _policy(idn, pw_expiry_days=90)
    _set_user(idn, users.priya, password_changed_at=idn.clock() - timedelta(days=89))

    client = Client()
    response = api_sign_in(client, PRIYA, PRIYA_PW)
    assert response.status_code == 201
    assert response.json()["user"]["must_change_password"] is False
    assert api_get(client, "/me").status_code == 200


def test_no_expiry_policy_never_expires_a_password(idn):
    """`None` is BR-IDN-025's 'no forced expiry' default — unchanged."""
    users = idn.seed_silvercreek()
    _set_user(idn, users.priya, password_changed_at=idn.clock() - timedelta(days=4000))
    response = api_sign_in(Client(), PRIYA, PRIYA_PW)
    assert response.json()["user"]["must_change_password"] is False


def test_an_empty_change_date_reads_the_day_the_login_was_created(idn):
    users = idn.seed_silvercreek()
    _policy(idn, pw_expiry_days=90)
    _set_user(
        idn, users.priya, password_changed_at=None, created_at=idn.clock() - timedelta(days=91)
    )
    response = api_sign_in(Client(), PRIYA, PRIYA_PW)
    assert response.json()["user"]["must_change_password"] is True


def test_a_wrong_password_on_an_expired_login_says_nothing_about_expiry(idn):
    users = idn.seed_silvercreek()
    _policy(idn, pw_expiry_days=90)
    _set_user(idn, users.priya, password_changed_at=idn.clock() - timedelta(days=91))
    response = api_sign_in(Client(), PRIYA, "not-her-password")
    assert response.status_code == 401
    users.priya.refresh_from_db()
    assert users.priya.must_change_password is False
    assert users.priya.failed_attempts == 1


def test_a_temp_password_follows_the_temp_path_untouched_by_expiry(idn):
    """A temporary password has its own 7-day clock; the expiry setting never
    re-flags it, never moves its expiry and the change is still a RESET."""
    users = idn.seed_silvercreek()
    _policy(idn, pw_expiry_days=90)
    alex = signed_in_client("alex@silvercreek.example", "Canyon2026rapids")
    temp = api_post(alex, f"/users/{users.priya.id}/temp-password").json()["temp_password"]
    _set_user(idn, users.priya, created_at=idn.clock() - timedelta(days=400))
    users.priya.refresh_from_db()
    temp_expiry = users.priya.temp_password_expires_at

    priya = Client()
    response = api_sign_in(priya, PRIYA, temp)
    assert response.json()["user"]["must_change_password"] is True
    users.priya.refresh_from_db()
    assert users.priya.temp_password_expires_at == temp_expiry
    assert _change(priya, "Prairie2026wind").status_code == 204
    assert idn.rows_for("auth.password_reset")
    # …and an expired temp password still signs in never.
    temp2 = api_post(alex, f"/users/{users.priya.id}/temp-password").json()["temp_password"]
    idn.clock.advance(days=8)
    assert api_sign_in(Client(), PRIYA, temp2).status_code == 401


def test_the_forced_change_after_expiry_refuses_the_same_password_and_takes_a_new_one(idn):
    users = idn.seed_silvercreek()
    _policy(idn, pw_expiry_days=90)
    _set_user(idn, users.priya, password_changed_at=idn.clock() - timedelta(days=91))
    priya = Client()
    api_sign_in(priya, PRIYA, PRIYA_PW)

    refused = _change(priya, PRIYA_PW)
    assert refused.status_code == 422
    assert refused.json()["field_errors"][0]["message_key"] == REUSED

    assert _change(priya, "Prairie2026wind").status_code == 204
    users.priya.refresh_from_db()
    assert users.priya.must_change_password is False
    assert users.priya.password_changed_at == idn.clock()
    assert idn.rows_for("auth.password_changed")  # a CHANGE, not a reset
    assert not idn.rows_for("auth.password_reset")
    # The next sign-in is normal: the clock restarted on the change.
    again = api_sign_in(Client(), PRIYA, "Prairie2026wind")
    assert again.json()["user"]["must_change_password"] is False


def test_keep_me_signed_in_does_not_renew_past_an_expired_password(idn):
    users = idn.seed_silvercreek()
    _policy(idn, pw_expiry_days=90, session_timeout_minutes=30)
    _set_user(idn, users.priya, password_changed_at=idn.clock() - timedelta(days=80))
    priya = signed_in_client(PRIYA, PRIYA_PW, keep_signed_in=True)
    idn.clock.advance(days=5)  # idle past 30 min, inside the renewal window
    assert api_get(priya, "/me").status_code == 200  # day 85: renewed
    idn.clock.advance(days=6)  # day 91: the password has expired
    assert api_get(priya, "/me").status_code == 401  # no renewal → sign in again


# ── 2 · The last five passwords (DEF-IDN-10023) ──────────────────────────────
SEQUENCE = [
    "Prairie2026wind1",
    "Prairie2026wind2",
    "Prairie2026wind3",
    "Prairie2026wind4",
    "Prairie2026wind5",
    "Prairie2026wind6",
]


def _walk_through_six(priya):
    current = PRIYA_PW
    for new in SEQUENCE:
        response = _change(priya, new, current=current)
        assert response.status_code == 204, response.content
        current = new
    return current


def test_the_current_and_each_of_the_last_five_are_refused_and_the_sixth_oldest_is_allowed(idn):
    users = idn.seed_silvercreek()
    priya = signed_in_client(PRIYA, PRIYA_PW)
    current = _walk_through_six(priya)  # current = wind6; history = wind5..wind1

    for reused in [current, *SEQUENCE[:-1]]:
        refused = _change(priya, reused, current=current)
        assert refused.status_code == 422, reused
        assert refused.json()["field_errors"][0]["message_key"] == REUSED
        assert refused.json()["field_errors"][0]["field"] == "new_password"
    users.priya.refresh_from_db()
    from django.contrib.auth.hashers import check_password

    assert check_password(current, users.priya.password_hash)  # nothing changed

    # The ORIGINAL password is now the sixth-oldest — allowed again.
    assert _change(priya, PRIYA_PW, current=current).status_code == 204


def test_history_is_pruned_to_five_and_holds_hashes_not_passwords(idn):
    users = idn.seed_silvercreek()
    priya = signed_in_client(PRIYA, PRIYA_PW)
    _walk_through_six(priya)
    with writing_as_tenant(idn.silvercreek):
        rows = list(PasswordHistory.objects.filter(user_id=users.priya.id))
    assert len(rows) == services.PASSWORD_HISTORY_BLOCK == 5
    for row in rows:
        assert row.tenant_id == idn.silvercreek.id
        assert "Prairie" not in row.password_hash and "Meadow" not in row.password_hash
        assert "$" in row.password_hash  # a Django hasher string


def test_a_reset_records_the_old_password_so_the_forced_change_cannot_return_to_it(idn):
    users = idn.seed_silvercreek()
    alex = signed_in_client("alex@silvercreek.example", "Canyon2026rapids")
    temp = api_post(alex, f"/users/{users.priya.id}/temp-password").json()["temp_password"]
    priya = Client()
    api_sign_in(priya, PRIYA, temp)
    refused = _change(priya, PRIYA_PW)
    assert refused.status_code == 422
    assert refused.json()["field_errors"][0]["message_key"] == REUSED
    assert _change(priya, "Prairie2026wind").status_code == 204
    # The temporary password itself never took a history slot.
    with writing_as_tenant(idn.silvercreek):
        assert PasswordHistory.objects.filter(user_id=users.priya.id).count() == 1


# ── 3 · The idle clock (DEF-IDN-10024) ───────────────────────────────────────
def _last_seen(client):
    return Session.objects.get(pk=session_id_of(client)).last_seen_at


def test_a_background_refresh_does_not_slide_the_idle_clock_and_a_person_does(idn):
    idn.seed_silvercreek()
    _policy(idn, session_timeout_minutes=30)
    priya = signed_in_client(PRIYA, PRIYA_PW)
    signed_in_at = _last_seen(priya)

    idn.clock.advance(minutes=20)
    assert api_get(priya, "/me", **BACKGROUND).status_code == 200  # authenticated…
    assert _last_seen(priya) == signed_in_at  # …and slid nothing

    assert api_get(priya, "/me").status_code == 200  # a person's request
    assert _last_seen(priya) == idn.clock()  # slides


def test_idle_expiry_still_refuses_a_polled_request(idn):
    """The bill-run page: polled every 30 s, nobody there. 30-minute policy."""
    idn.seed_silvercreek()
    _policy(idn, session_timeout_minutes=30)
    priya = signed_in_client(PRIYA, PRIYA_PW)
    for _ in range(60):  # 30 minutes of polls, every 30 seconds
        idn.clock.advance(seconds=30)
        assert api_get(priya, "/me", **BACKGROUND).status_code == 200
    idn.clock.advance(minutes=1)  # 31 minutes since the person last did anything
    assert api_get(priya, "/me", **BACKGROUND).status_code == 401
    assert api_get(priya, "/me").status_code == 401  # and the session is gone


def test_a_header_value_other_than_1_is_a_normal_request(idn):
    idn.seed_silvercreek()
    _policy(idn, session_timeout_minutes=30)
    priya = signed_in_client(PRIYA, PRIYA_PW)
    idn.clock.advance(minutes=20)
    assert api_get(priya, "/me", HTTP_X_BACKGROUND_REFRESH="0").status_code == 200
    assert _last_seen(priya) == idn.clock()


# ── 4 · Row-level security on the new table (PostgreSQL only) ────────────────
@requires_postgres
def test_password_history_is_enabled_AND_forced(db):
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT c.relrowsecurity, c.relforcerowsecurity FROM pg_class c "
            "JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = 'public' AND c.relname = 'password_history'"
        )
        assert cursor.fetchone() == (True, True)


@requires_postgres
def test_password_history_is_scoped_by_the_policy_not_by_the_app(idn, rls):
    """Read under `sbh_rls_probe`, a role RLS applies to — no application
    `filter(tenant_id=…)` is in the path. Both halves: USING and WITH CHECK."""
    idn.seed_silvercreek()
    idn.seed_bluemesa_admin()
    priya = signed_in_client(PRIYA, PRIYA_PW)
    assert _change(priya, "Prairie2026wind", current=PRIYA_PW).status_code == 204
    assert_denied_without_context(rls, "password_history")
    assert_rls_scoped(rls, "password_history", owner=idn.silvercreek, intruder=idn.bluemesa)
    message = assert_write_into_other_tenant_refused(
        rls, "password_history", owner=idn.silvercreek, intruder=idn.bluemesa
    )
    assert "row-level security" in message


# ── 5 · DevOps: what address does the server see? (read-only) ────────────────
def test_client_ip_check_shows_what_the_allowlist_will_compare(settings):
    from io import StringIO

    from django.core.management import call_command

    out = StringIO()
    settings.TRUSTED_PROXY_COUNT = 0
    call_command("client_ip_check", remote_addr="10.0.3.7", xff="203.0.113.9", stdout=out)
    assert "TRUSTED_PROXY_COUNT = 0" in out.getvalue()
    assert "client_ip=10.0.3.7" in out.getvalue()  # behind a load balancer: the balancer

    out = StringIO()
    settings.TRUSTED_PROXY_COUNT = 1
    call_command("client_ip_check", remote_addr="10.0.3.7", xff="203.0.113.9", stdout=out)
    assert "client_ip=203.0.113.9" in out.getvalue()  # the caller


def test_client_ip_check_lists_recorded_sign_in_addresses(idn):
    from io import StringIO

    from django.core.management import call_command

    idn.seed_silvercreek()
    signed_in_client(PRIYA, PRIYA_PW, ip="198.51.100.4")
    out = StringIO()
    call_command("client_ip_check", stdout=out)
    assert "198.51.100.4" in out.getvalue()
    assert "priya" not in out.getvalue()
