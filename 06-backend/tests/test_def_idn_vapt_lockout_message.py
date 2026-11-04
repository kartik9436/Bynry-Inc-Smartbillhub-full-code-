# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-IDN-10620 — a locked sign-in said "That email or password is
#           incorrect" instead of how long to wait.
# Ruling:   decision log 2026-10-27 "VAPT round: five findings ruled" — PO:
#           *"the lockout period, account lock after x wrong passwords should
#           not be hardcoded, it should follow what the user mentions in the
#           settings and the same message has to appear when the user was
#           locked out"*.
# Doc:      09-infra/06-vapt-remediation-2026-10.md §2, Test table rows 1–4.
# Rules:    BR-IDN-025 (CONFIRMED-AS-AMENDED by CR-145-BRC08: N and M are the
#           utility's) · BR-IDN-002 (one generic failure — narrowed here for the
#           locked state, by the PO's request; see services.LOCKED_MESSAGE_KEY).
# ───────────────────────────────────────────────────────
"""The locked message names the UTILITY'S minutes, on the web and the phone.

Red first, without the change: every assertion on `auth.sign_in.locked` fails,
because the lock answered `errors.auth.sign_in_failed` with no params.
"""

import pytest
from django.core.cache import cache
from django.test import Client

from apps.identity.models import SecurityPolicy
from tests.isolation_helpers import writing_as_tenant
from tests.test_us_idn_helpers import JSON, SC, api_path, api_sign_in, idn  # noqa: F401

pytestmark = pytest.mark.django_db

LOCKED = "auth.sign_in.locked"
GENERIC = "errors.auth.sign_in_failed"
PRIYA_PASSWORD = "Meadow2026sage"


def _policy(env, **values):
    policy, _ = SecurityPolicy.objects.get_or_create(tenant=env.silvercreek)
    for field, value in values.items():
        setattr(policy, field, value)
    policy.save()


def _body(response):
    return response.json()


@pytest.mark.parametrize("max_failed,minutes", [(3, 5), (5, 15)])
def test_def_idn_10620__the_attempt_that_locks_says_the_utilitys_minutes(idn, max_failed, minutes):
    """Test rows 1 and 4: 3/5 locks on the 3rd and says 5; 5/15 on the 5th, 15."""
    users = idn.seed_silvercreek()
    _policy(idn, lockout_max_failed=max_failed, lockout_minutes=minutes)
    client = Client()
    for attempt in range(1, max_failed):
        refused = api_sign_in(client, users.priya.email, "wrong")
        assert refused.status_code == 401
        assert _body(refused)["message_key"] == GENERIC, f"attempt {attempt} named the lock early"
        assert "minutes" not in _body(refused)["params"]
    locking = api_sign_in(client, users.priya.email, "wrong")
    assert locking.status_code == 401
    assert _body(locking)["message_key"] == LOCKED
    assert _body(locking)["params"]["minutes"] == minutes


def test_def_idn_10620__the_right_password_while_locked_gets_the_same_message(idn):
    """Test row 2, then row 3: locked → same message; after the window → signed in."""
    users = idn.seed_silvercreek()
    _policy(idn, lockout_max_failed=3, lockout_minutes=5)
    client = Client()
    for _ in range(3):
        api_sign_in(client, users.priya.email, "wrong")
    idn.clock.advance(minutes=2)
    locked = api_sign_in(client, users.priya.email, PRIYA_PASSWORD)
    assert locked.status_code == 401
    assert _body(locked)["message_key"] == LOCKED
    # The utility's SETTING, never the time left — the message the PO approved.
    assert _body(locked)["params"]["minutes"] == 5
    idn.clock.advance(minutes=3, seconds=1)
    assert api_sign_in(client, users.priya.email, PRIYA_PASSWORD).status_code == 201


def test_def_idn_10620__a_changed_setting_changes_the_message(idn):
    """The minutes are READ at the refusal, so a utility that changes its
    setting while someone is locked out tells them the new number."""
    users = idn.seed_silvercreek()
    _policy(idn, lockout_max_failed=3, lockout_minutes=5)
    client = Client()
    for _ in range(3):
        api_sign_in(client, users.priya.email, "wrong")
    _policy(idn, lockout_minutes=30)
    locked = api_sign_in(client, users.priya.email, PRIYA_PASSWORD)
    assert _body(locked)["params"]["minutes"] == 30


def test_def_idn_10620__an_unknown_email_never_gets_the_locked_message(idn):
    """The trade-off is bounded: only a REAL, locked login says it is locked.
    An address that does not exist answers the generic sentence however many
    times it is tried, so the message names no account that is not there."""
    idn.seed_silvercreek()
    _policy(idn, lockout_max_failed=3, lockout_minutes=5)
    client = Client()
    for _ in range(6):
        refused = api_sign_in(client, "nobody@silvercreek.example", "wrong")
        assert _body(refused)["message_key"] == GENERIC


def test_def_idn_10620__the_locked_answer_still_costs_a_password_hash(idn, monkeypatch):
    """Timing equalisation is kept: the locked branch runs one hash, as the
    wrong-password and unknown-email branches do, so it is not the fast path."""
    from apps.identity import services

    users = idn.seed_silvercreek()
    _policy(idn, lockout_max_failed=3, lockout_minutes=5)
    client = Client()
    for _ in range(3):
        api_sign_in(client, users.priya.email, "wrong")
    calls = []
    real = services.check_password
    monkeypatch.setattr(services, "check_password", lambda *a, **k: calls.append(1) or real(*a, **k))
    api_sign_in(client, users.priya.email, PRIYA_PASSWORD)
    assert len(calls) == 1


# ── the field app's native door ─────────────────────────────────────────────
DANA = "dana@silvercreek.example"
DANA_PASSWORD = "Valley2026river"


def _token(password):
    return Client().post(
        api_path("/auth/token", SC),
        data={"email": DANA, "password": password, "device_id": "handset-1", "device_name": "Van 14"},
        content_type=JSON,
    )


def test_def_idn_10620__the_native_door_says_the_same_thing(idn):
    from apps.work import models as work_models

    cache.clear()
    idn.seed_silvercreek()
    dana, _ = idn.make_user(
        idn.silvercreek, DANA, "Dana Ortiz", password=DANA_PASSWORD, role="field_technician"
    )
    with writing_as_tenant(idn.silvercreek):
        work_models.Technician.objects.create(tenant=idn.silvercreek, user=dana)
    _policy(idn, lockout_max_failed=3, lockout_minutes=5)
    for _ in range(2):
        assert _token("wrong").json()["message_key"] == GENERIC
    locking = _token("wrong")
    assert locking.status_code == 401
    assert locking.json()["message_key"] == LOCKED
    assert locking.json()["params"]["minutes"] == 5
    locked = _token(DANA_PASSWORD)
    assert locked.status_code == 401
    assert locked.json()["message_key"] == LOCKED and locked.json()["params"]["minutes"] == 5
    idn.clock.advance(minutes=5, seconds=1)
    assert _token(DANA_PASSWORD).status_code == 201
    cache.clear()


def test_def_idn_10620__the_sentence_is_in_all_eleven_catalogues():
    import json
    import pathlib

    locales = pathlib.Path(__file__).resolve().parents[2] / "07-frontend/src/i18n/locales"
    files = sorted(locales.glob("*.json"))
    assert len(files) == 11
    for path in files:
        catalogue = json.loads(path.read_text(encoding="utf-8"))
        for key in (LOCKED, "field.signIn.error.locked"):
            assert "{{minutes}}" in catalogue[key], (path.name, key)
    english = json.loads((locales / "en.json").read_text(encoding="utf-8"))
    assert english[LOCKED] == "Too many wrong attempts. Try again in {{minutes}} minutes."
    assert english["field.signIn.error.locked"] == english[LOCKED]
