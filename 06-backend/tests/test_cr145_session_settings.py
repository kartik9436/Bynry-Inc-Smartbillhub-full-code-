# ── Trace ──────────────────────────────────────────────
# Change:  CR-145-BRC08 — six session and lockout rules become per-utility
#          settings within fixed limits (PO ruling 2026-09-28, *"Im okay with
#          these limit"*). Tasks T1, T2, T3, T5, T6, T8.
# Rules:   BR-IDN-025 (CONFIRMED-AS-AMENDED — the lockout half is now two
#          per-utility settings) · BR-IDN-026 (CONFIRMED-AS-AMENDED — all four
#          of its numbers are settings; the portal gets none of its own) ·
#          BR-IDN-019 (SysAdmin edits, Executive views, Clerk cannot see)
# Tests:   this file. T4 (the migration) and T7 (isolation) are PostgreSQL-only
#          and live in tests/test_cr145_migration_pg.py, because a data
#          migration and an RLS probe proved on SQLite are proved on nothing
#          (hard-won law 14).
# ───────────────────────────────────────────────────────
"""THE SIX SETTINGS ACTUALLY TAKE EFFECT, AND THE LIMITS ACTUALLY REFUSE.

⚠ **EVERY CASE HERE CHANGES A SETTING AND THEN MEASURES THE ENGINE, NEVER THE
COLUMN.** A test that saves `lockout_max_failed = 3` and reads it back proves
the ORM works. What `CR-145` promises is that the third wrong password locks
the account — so each case below drives `services.sign_in`,
`IdentitySessionAuthentication.authenticate` or the portal's own session
issue, and asserts what the PERSON at the browser would experience.

⚠ **THE DEFAULTS ARE ASSERTED TO BE TODAY'S VALUES.** The ruling's third
clause is that nothing moves on the day this ships, and a column default is
exactly the kind of thing that gets "tidied" to a rounder number by a later
lane. `test_t1_defaults_are_todays_fixed_values` is that clause as an
assertion.
"""

import json
from datetime import timedelta

import pytest
from django.test import Client
from django.utils import timezone

from apps.identity import selectors, services
from apps.identity.auth import IdentitySessionAuthentication, session_cookie_max_age
from apps.identity.models import SecurityPolicy, Session
from tests.test_us_idn_helpers import (  # noqa: F401 (fixture import)
    BM,
    SC,
    api_get,
    api_path,
    api_put,
    api_sign_in,
    body_without_trace,
    idn,
    session_id_of,
    signed_in_client,
)

pytestmark = pytest.mark.django_db

JSON = "application/json"


def _policy(idn_env, tenant=None, **values):
    """Write a policy row straight onto the utility, bypassing the API.

    The API path is `test_t6_*`'s subject; everything else needs a utility in
    a given state, not a save that has been through the role gate.
    """
    tenant = tenant or idn_env.silvercreek
    policy, _created = SecurityPolicy.objects.get_or_create(tenant=tenant)
    for field, value in values.items():
        setattr(policy, field, value)
    policy.save()
    return policy


# ═══════════════════════════════════════════════════════════════════════════
# T1 · each setting takes effect
# ═══════════════════════════════════════════════════════════════════════════
def test_t1_defaults_are_todays_fixed_values(idn):
    """Ruling 3: *"Nothing changes for any utility on the day this ships."*

    ⚠ **READ OFF A UTILITY WITH NO POLICY ROW**, which is the state every
    utility that has never opened the Security tab is in — and therefore the
    state in which a wrong default would be invisible.
    """
    values = selectors.security_policy_values(idn.silvercreek.id)
    assert values["session_timeout_minutes"] == 60
    assert values["absolute_session_hours"] == 12
    assert values["keep_signed_in_offered"] is True
    assert values["keep_signed_in_days"] == 30
    assert values["lockout_max_failed"] == 5
    assert values["lockout_minutes"] == 15


def test_t1_lockout_three_locks_on_the_third_failure(idn):
    """*"set lockout to 3, type a wrong password 3 times, the 3rd locks."*

    The 1st and 2nd are refused and leave the account usable; the 3rd is the
    one that locks it, proved by the CORRECT password being refused after it.
    """
    users = idn.seed_silvercreek()
    _policy(idn, lockout_max_failed=3)
    client = Client()

    for attempt in (1, 2):
        assert api_sign_in(client, users.priya.email, "wrong").status_code == 401
        users.priya.refresh_from_db()
        assert users.priya.locked_until is None, f"locked on attempt {attempt}, too early"

    assert api_sign_in(client, users.priya.email, "wrong").status_code == 401
    users.priya.refresh_from_db()
    assert users.priya.locked_until is not None, "the 3rd failure did not lock"
    # The proof that matters: the RIGHT password is now refused too.
    assert api_sign_in(client, users.priya.email, "Meadow2026sage").status_code == 401


def test_t1_lockout_five_minutes_unlocks_after_five(idn):
    """*"lockout 5 minutes unlocks after 5."* Frozen clock, both sides."""
    users = idn.seed_silvercreek()
    _policy(idn, lockout_max_failed=3, lockout_minutes=5)
    client = Client()
    for _ in range(3):
        api_sign_in(client, users.priya.email, "wrong")
    users.priya.refresh_from_db()
    assert users.priya.locked_until is not None

    # 4 minutes 59: still locked.
    idn.clock.advance(minutes=4, seconds=59)
    assert api_sign_in(client, users.priya.email, "Meadow2026sage").status_code == 401
    # 5 minutes 1: in again.
    idn.clock.advance(seconds=2)
    assert api_sign_in(client, users.priya.email, "Meadow2026sage").status_code == 201


def test_t1_lockout_minutes_reaches_the_audit_row(idn):
    """The trail must say the utility's number, not the old fixed 15."""
    users = idn.seed_silvercreek()
    _policy(idn, lockout_max_failed=3, lockout_minutes=45)
    client = Client()
    for _ in range(3):
        api_sign_in(client, users.priya.email, "wrong")
    rows = idn.rows_for("auth.lockout")
    assert rows, "no lockout audit row was written"
    assert rows[-1]["after"] == {"locked_minutes": 45}


def test_t1_hard_limit_four_hours_expires_at_four_hours_one_minute(idn):
    """*"hard limit 4h expires at 4h 1min."*

    ⚠ **THE SESSION IS NOT PERSISTENT**, deliberately: a persistent one would
    be REFRESHED past the hard limit rather than refused, which is `T3`'s
    subject and would make this case prove the opposite of what it says.
    """
    users = idn.seed_silvercreek()
    _policy(idn, absolute_session_hours=4)
    client = signed_in_client(users.priya.email, "Meadow2026sage")

    session = Session.objects.get(pk=session_id_of(client))
    assert session.expires_at == idn.clock() + timedelta(hours=4)

    # 3h59 — still in. ⚠ **KEPT ACTIVE ON THE WAY, OR THE IDLE RULE ANSWERS
    # INSTEAD OF THE HARD LIMIT.** The idle default is 60 minutes and its
    # ceiling is 60, so one silent 3h59 jump is refused by inactivity and says
    # nothing about the 4 hours — this case read that way until its first run
    # (2026-09-28) and failed at 3h59. A request every 59 minutes slides
    # `last_seen_at`, so only the hard limit is left to refuse.
    for _ in range(4):
        idn.clock.advance(minutes=59)
        assert api_get(client, "/me").status_code == 200
    idn.clock.advance(minutes=3)  # 3h59 from sign-in
    assert api_get(client, "/me").status_code == 200

    # 4h01 from sign-in and two minutes idle: only the hard limit can say no.
    # (It used to advance a further 4h01 — to 8h02 — which ANY limit refuses.)
    idn.clock.advance(minutes=2)
    assert api_get(client, "/me").status_code == 401


def test_t1_inactivity_fifteen_minutes_signs_out_at_fifteen_minutes_one_second(idn):
    """*"inactivity 15 min signs out at 15 min 1s."*

    15 is a NEW choice — it did not exist before `CR-145` narrowed the list —
    so this case also proves the narrowing went the right way.
    """
    users = idn.seed_silvercreek()
    _policy(idn, session_timeout_minutes=15)
    client = signed_in_client(users.priya.email, "Meadow2026sage")

    idn.clock.advance(minutes=14, seconds=59)
    assert api_get(client, "/me").status_code == 200

    # The call above slid `last_seen_at` forward, so measure from there.
    idn.clock.advance(minutes=15, seconds=1)
    assert api_get(client, "/me").status_code == 401


def test_t1_renewal_one_day_stops_renewing_after_one_day(idn):
    """*"renewal 1 day stops renewing after 1 day."*

    A persistent session past its HARD limit is renewed while it is inside the
    renewal window and refused once it is outside — which is the whole of what
    *"Keep me signed in"* does, measured rather than described.
    """
    users = idn.seed_silvercreek()
    _policy(idn, absolute_session_hours=4, keep_signed_in_days=1)
    client = signed_in_client(users.priya.email, "Meadow2026sage", keep_signed_in=True)

    # 5 hours: past the 4-hour hard limit, inside the 1-day renewal window.
    idn.clock.advance(hours=5)
    assert api_get(client, "/me").status_code == 200, "inside the window and not renewed"

    # 25 hours from creation: outside it.
    idn.clock.advance(hours=20)
    assert api_get(client, "/me").status_code == 401


# ═══════════════════════════════════════════════════════════════════════════
# T2 · the limits refuse, by name and by range
# ═══════════════════════════════════════════════════════════════════════════
REFUSALS = [
    ("lockout_max_failed", 2),
    ("lockout_max_failed", 11),
    ("absolute_session_hours", 3),
    ("absolute_session_hours", 13),
    ("keep_signed_in_days", 0),
    ("keep_signed_in_days", 31),
    ("lockout_minutes", 4),
    ("lockout_minutes", 61),
    ("session_timeout_minutes", 10),
    # ⚠ **240 IS THE ONE THAT MATTERS.** It was a legal choice until
    # 2026-09-28 and is not one now, so a refusal here is the withdrawal
    # actually taking effect rather than merely being written down.
    ("session_timeout_minutes", 240),
]


@pytest.mark.parametrize("field,value", REFUSALS)
def test_t2_out_of_range_is_refused_naming_the_field_and_the_range(idn, field, value):
    users = idn.seed_silvercreek()
    client = signed_in_client(users.alex.email, "Canyon2026rapids")
    response = api_put(client, "/settings/security-policy", {field: value})

    assert response.status_code == 422, response.content
    body = body_without_trace(response)
    field_errors = body["field_errors"]
    named = [fe for fe in field_errors if fe["field"] == field]
    assert named, f"the refusal did not name {field}: {field_errors}"

    # …and it says what IS allowed, which is what lets a screen render the
    # range without keeping its own copy of it.
    params = named[0]["params"]
    assert ("allowed" in params) or {"min", "max"} <= set(params), params

    # Nothing was written.
    assert not SecurityPolicy.objects.filter(tenant=idn.silvercreek).exists()


@pytest.mark.parametrize(
    "field,value",
    [
        ("lockout_max_failed", 3),
        ("lockout_max_failed", 10),
        ("absolute_session_hours", 4),
        ("absolute_session_hours", 12),
        ("keep_signed_in_days", 1),
        ("keep_signed_in_days", 30),
        ("lockout_minutes", 5),
        ("lockout_minutes", 60),
        ("session_timeout_minutes", 15),
        ("session_timeout_minutes", 45),
    ],
)
def test_t2_the_edges_of_every_range_are_ACCEPTED(idn, field, value):
    """The other half, and it is not decoration.

    A validator written `min < value < max` refuses both ends and passes every
    case in the list above — *"what would make this check pass wrongly"*
    answered as a test rather than as a comment (hard-won law 7, habit 2).
    """
    users = idn.seed_silvercreek()
    client = signed_in_client(users.alex.email, "Canyon2026rapids")
    response = api_put(client, "/settings/security-policy", {field: value})
    assert response.status_code == 200, response.content
    assert getattr(SecurityPolicy.objects.get(tenant=idn.silvercreek), field) == value


def test_t2_a_boolean_is_not_a_number(idn):
    """`isinstance(True, int)` is True in Python, so `True` would land in
    `lockout_minutes` as 1 and be stored if the type were not checked first."""
    users = idn.seed_silvercreek()
    client = signed_in_client(users.alex.email, "Canyon2026rapids")
    response = client.put(
        api_path("/settings/security-policy"),
        data=json.dumps({"lockout_minutes": True}),
        content_type=JSON,
    )
    assert response.status_code == 422, response.content


# ═══════════════════════════════════════════════════════════════════════════
# T3 · "Keep me signed in" switched off
# ═══════════════════════════════════════════════════════════════════════════
def test_t3_the_request_asking_for_it_is_refused(idn):
    users = idn.seed_silvercreek()
    _policy(idn, keep_signed_in_offered=False)
    client = Client()
    response = api_sign_in(client, users.priya.email, "Meadow2026sage", keep_signed_in=True)

    assert response.status_code == 422, response.content
    body = body_without_trace(response)
    assert body["field_errors"][0]["field"] == "keep_signed_in"
    # ⚠ NOT the generic sign-in failure: the credentials were correct and
    # nothing about the account is being disclosed.
    assert body["message_key"] != services.GENERIC_SIGN_IN_MESSAGE_KEY
    # No session was opened.
    assert not Session.objects.filter(user=users.priya).exists()


def test_t3_signing_in_WITHOUT_it_still_works_when_it_is_off(idn):
    """The refusal must be about the tick box and nothing else."""
    users = idn.seed_silvercreek()
    _policy(idn, keep_signed_in_offered=False)
    client = Client()
    assert api_sign_in(client, users.priya.email, "Meadow2026sage").status_code == 201


def test_t3_and_no_renewal_ever_happens(idn):
    """*"…and no renewal ever happens."*

    ⚠ **THE SESSION IS CREATED WHILE THE SETTING IS ON AND THE SETTING IS
    THEN SWITCHED OFF.** Refusing the tick box at sign-in only closes the door
    to NEW persistent sessions; an admin turning the switch off has said
    something about unattended browsers, and the sessions already out there
    must stop renewing too. This is the case that would pass if
    `_refreshable` read only `keep_signed_in_days`.
    """
    users = idn.seed_silvercreek()
    _policy(idn, absolute_session_hours=4, keep_signed_in_days=30)
    client = signed_in_client(users.priya.email, "Meadow2026sage", keep_signed_in=True)
    session = Session.objects.get(pk=session_id_of(client))
    assert session.persistent is True

    _policy(idn, keep_signed_in_offered=False)

    idn.clock.advance(hours=5)  # past the hard limit, deep inside 30 days
    assert api_get(client, "/me").status_code == 401


def test_t3_public_read_says_whether_the_tick_box_is_offered(idn):
    """B13 — the one boolean the SIGN-IN FORM needs, with no session."""
    idn.seed_silvercreek()
    stranger = Client()

    response = stranger.get(api_path("/auth/sign-in-options"))
    assert response.status_code == 200, response.content
    assert json.loads(response.content) == {"keep_signed_in_offered": True}

    _policy(idn, keep_signed_in_offered=False)
    response = stranger.get(api_path("/auth/sign-in-options"))
    assert json.loads(response.content) == {"keep_signed_in_offered": False}


def test_t3_the_public_read_discloses_nothing_else(idn):
    """⚠ It must not become a window onto the lockout or timeout numbers —
    *"this utility locks after three attempts"* paces a password sprayer."""
    idn.seed_silvercreek()
    _policy(idn, lockout_max_failed=3, lockout_minutes=5, session_timeout_minutes=15)
    body = json.loads(Client().get(api_path("/auth/sign-in-options")).content)
    assert set(body) == {"keep_signed_in_offered"}


# ═══════════════════════════════════════════════════════════════════════════
# T5 · the portal follows the utility, and has no setting of its own
# ═══════════════════════════════════════════════════════════════════════════
def test_t5_the_portal_hard_limit_follows_the_utility(idn):
    """`portal/session.py`'s `ABSOLUTE_LIFETIME_HOURS = 12` was fixed."""
    from apps.portal.seams import identity_seam

    assert identity_seam.absolute_session_hours(idn.silvercreek.id) == 12
    _policy(idn, absolute_session_hours=4)
    assert identity_seam.absolute_session_hours(idn.silvercreek.id) == 4


def test_t5_the_portal_idle_setting_follows_the_utility(idn):
    """It already did; this pins the PAIR, which is what the ruling asked for."""
    from apps.portal.seams import identity_seam

    assert identity_seam.session_timeout_minutes(idn.silvercreek.id) == 60
    _policy(idn, session_timeout_minutes=15)
    assert identity_seam.session_timeout_minutes(idn.silvercreek.id) == 15


def test_t5_the_portal_has_no_setting_of_its_own(idn):
    """PO: *"one setting is less for an admin to get wrong."*

    The absence is asserted, because an absence is invisible to every other
    check in this repo: a `portal_absolute_session_hours` column arriving on
    `SecurityPolicy` would break the ruling and no test would notice.
    """
    columns = {field.name for field in SecurityPolicy._meta.get_fields()}
    assert not [name for name in columns if name.startswith("portal_")], columns


# ═══════════════════════════════════════════════════════════════════════════
# T6 · who may save, who may look, who may not
# ═══════════════════════════════════════════════════════════════════════════
def test_t6_only_system_admin_saves(idn):
    """⚠ **20 MINUTES BECAME 30 ON 2026-09-29 AND THE CASE IS UNCHANGED IN
    SUBSTANCE.** The Security redesign made `lockout_minutes` a dropdown of
    5/10/15/30/45/60, so 20 is refused by NAME now and this case would have
    asserted a 422 against the ROLE gate — it is about who may save, not about
    what may be saved. The two `403` cases below still send 20 on purpose: a
    refusal that never reaches the validator is the point of them.
    """
    users = idn.seed_silvercreek()
    client = signed_in_client(users.alex.email, "Canyon2026rapids")
    assert api_put(client, "/settings/security-policy", {"lockout_minutes": 30}).status_code == 200


def test_t6_executive_reads_and_cannot_save(idn):
    users = idn.seed_silvercreek()
    client = signed_in_client(users.diana.email, "Vista2026peak")
    assert api_get(client, "/settings/security-policy").status_code == 200
    assert api_put(client, "/settings/security-policy", {"lockout_minutes": 20}).status_code == 403


def test_t6_billing_clerk_is_refused_both_ways(idn):
    users = idn.seed_silvercreek()
    client = signed_in_client(users.priya.email, "Meadow2026sage")
    assert api_get(client, "/settings/security-policy").status_code == 403
    assert api_put(client, "/settings/security-policy", {"lockout_minutes": 20}).status_code == 403


def test_t6_the_read_carries_the_limits_so_no_screen_keeps_a_copy(idn):
    """B8 — the choices travel WITH the policy.

    ⚠ **AMENDED 2026-09-29: THESE FOUR WERE RANGES AND ARE CHOICE LISTS NOW.**
    The approved Settings → Security redesign turned every typed number into a
    dropdown (PO: *"(a) Short dropdown, list chosen from real use -
    Dropdown"*), so `{"min": 3, "max": 10, …}` is not what this read serves any
    more. **The thing `CR-145` T6 actually asserts is unchanged and is what is
    asserted below**: whatever an admin may choose travels with the policy, so
    no screen keeps a copy of it. The lists themselves are pinned in
    `tests/test_security_redesign_choice_lists.py`, which owns the redesign.
    """
    users = idn.seed_silvercreek()
    client = signed_in_client(users.alex.email, "Canyon2026rapids")
    body = json.loads(api_get(client, "/settings/security-policy").content)

    limits = body["limits"]
    assert limits["session_timeout_minutes"]["choices"] == [15, 30, 45, 60]
    assert limits["lockout_max_failed"]["choices"] == [3, 4, 5, 6, 7, 8, 9, 10]
    assert limits["lockout_minutes"]["choices"] == [5, 10, 15, 30, 45, 60]
    assert limits["absolute_session_hours"]["choices"] == [4, 5, 6, 7, 8, 9, 10, 11, 12]
    assert limits["keep_signed_in_days"]["choices"] == [1, 7, 14, 30]
    for field, default in (
        ("lockout_max_failed", 5),
        ("lockout_minutes", 15),
        ("absolute_session_hours", 12),
        ("keep_signed_in_days", 30),
    ):
        assert limits[field]["default"] == default, field
    assert limits["keep_signed_in_offered"] == {"boolean": True, "default": True}


def test_def_idn_7501_the_two_password_dropdowns_are_served_too(idn):
    """DEF-IDN-7501 (server half) — the Security tab typed `[8, 10, 12]` and
    `[null, 90, 180]` out by hand because the read did not send them, which is
    the SignupWizard eleventh-service failure in a new place.

    ⚠ **THE VALUES ARE THE ONES THE SERVER ALREADY ENFORCED, AND NO RULE
    MOVED.** The password rules are outside `CR-145` (*"the password rules are
    NOT in this change and stay fixed"*); this only PUBLISHES them. `null` is
    a real choice — "never expires" — so it is served, and it is the default.
    """
    users = idn.seed_silvercreek()
    client = signed_in_client(users.alex.email, "Canyon2026rapids")
    limits = json.loads(api_get(client, "/settings/security-policy").content)["limits"]

    # ⚠ **AMENDED 2026-09-29**: the entry now also carries `unit` and the
    # rendered `options`, because the redesign puts the unit inside the option
    # and the audit card must print the same words. The NUMBERS below are what
    # this case is about and they have not moved; the option text is pinned in
    # `tests/test_security_redesign_choice_lists.py`.
    assert limits["pw_min_length"]["choices"] == [8, 10, 12]
    assert limits["pw_min_length"]["default"] == 8
    assert limits["pw_expiry_days"]["choices"] == [None, 90, 180]
    assert limits["pw_expiry_days"]["default"] is None


@pytest.mark.parametrize(
    "field,value,allowed",
    [
        # The refusal's `allowed` is exactly what it was before DEF-IDN-7501:
        # the expiry refusal never listed `null`, because "choose never" is
        # not something a refusal needs to tell a person.
        ("pw_min_length", 9, [8, 10, 12]),
        ("pw_expiry_days", 30, [90, 180]),
    ],
)
def test_def_idn_7501_the_password_refusals_did_not_move(idn, field, value, allowed):
    users = idn.seed_silvercreek()
    client = signed_in_client(users.alex.email, "Canyon2026rapids")
    response = api_put(client, "/settings/security-policy", {field: value})
    assert response.status_code == 422, response.content
    named = [fe for fe in body_without_trace(response)["field_errors"] if fe["field"] == field]
    assert len(named) == 1, named  # one refusal per field, never two validators
    assert named[0]["params"] == {"allowed": allowed}
    assert named[0]["message_key"] == "errors.identity.option_not_allowed"


def test_def_idn_7501_never_and_each_length_are_still_accepted(idn):
    users = idn.seed_silvercreek()
    client = signed_in_client(users.alex.email, "Canyon2026rapids")
    for payload in ({"pw_expiry_days": None}, {"pw_expiry_days": 180}, {"pw_min_length": 12}):
        assert api_put(client, "/settings/security-policy", payload).status_code == 200, payload


def test_t6_saving_writes_before_and_after_for_the_new_fields(idn):
    """B11 — the audit row covers the five new settings, not only the six old."""
    users = idn.seed_silvercreek()
    _policy(idn, lockout_max_failed=5, lockout_minutes=15)
    client = signed_in_client(users.alex.email, "Canyon2026rapids")
    # ⚠ **40 BECAME 45 ON 2026-09-29** — `lockout_minutes` is a dropdown of
    # 5/10/15/30/45/60 now and 40 is not on it. What this case asserts, the
    # before/after pair covering the new columns, is untouched.
    api_put(client, "/settings/security-policy", {"lockout_max_failed": 8, "lockout_minutes": 45})

    rows = idn.rows_for("settings.security_updated")
    assert rows, "no audit row for the save"
    row = rows[-1]
    assert row["before"] == {"lockout_max_failed": 5, "lockout_minutes": 15}
    assert row["after"] == {"lockout_max_failed": 8, "lockout_minutes": 45}


# ═══════════════════════════════════════════════════════════════════════════
# T8 · the cookie's expiry
# ═══════════════════════════════════════════════════════════════════════════
def test_t8_ticked_sets_max_age_to_the_renewal_days(idn):
    """⚠ **THIS IS THE LIVE BUG.** All three `set_cookie` calls passed NO
    expiry, so the cookie died when the browser closed — the one thing *"Keep
    me signed in"* exists to prevent."""
    users = idn.seed_silvercreek()
    _policy(idn, keep_signed_in_days=7)
    client = Client()
    response = api_sign_in(client, users.priya.email, "Meadow2026sage", keep_signed_in=True)
    assert response.status_code == 201

    morsel = response.cookies["sbh_session"]
    assert morsel["max-age"] == 7 * 24 * 3600


def test_t8_not_ticked_is_a_browser_session_cookie(idn):
    users = idn.seed_silvercreek()
    client = Client()
    response = api_sign_in(client, users.priya.email, "Meadow2026sage")
    assert response.status_code == 201
    # Django renders "no expiry" as an EMPTY max-age, which is what a
    # browser-session cookie is.
    assert response.cookies["sbh_session"]["max-age"] == ""


def test_t8_the_helper_refuses_to_promise_what_the_utility_switched_off(idn):
    """A cookie promising 30 days over a session `_refreshable` will not renew
    is the *live control over a dead setting* half of hard-won law 2."""
    on = {"keep_signed_in_offered": True, "keep_signed_in_days": 30}
    off = {"keep_signed_in_offered": False, "keep_signed_in_days": 30}
    assert session_cookie_max_age(on, True) == 30 * 24 * 3600
    assert session_cookie_max_age(on, False) is None
    assert session_cookie_max_age(off, True) is None


def test_t8_the_refreshable_check_reads_the_utility_not_a_constant(idn):
    """Straight at `_refreshable`, because the route above can only reach it
    through a whole request and this is the function the ruling moved."""
    users = idn.seed_silvercreek()
    client = signed_in_client(users.priya.email, "Meadow2026sage", keep_signed_in=True)
    session = Session.objects.get(pk=session_id_of(client))
    now = idn.clock() + timedelta(days=10)

    assert IdentitySessionAuthentication._refreshable(
        session, now, {"keep_signed_in_offered": True, "keep_signed_in_days": 30}
    )
    assert not IdentitySessionAuthentication._refreshable(
        session, now, {"keep_signed_in_offered": True, "keep_signed_in_days": 1}
    )


def test_t8_the_four_constants_are_gone_from_services(idn):
    """⚠ **THE ABSENCE IS ASSERTED.** A lane re-adding `LOCKOUT_MINUTES = 15`
    beside the policy read would give this product two sources for one number,
    and the one nobody reads is the one that stays right."""
    for name in (
        "LOCKOUT_MAX_FAILED",
        "LOCKOUT_MINUTES",
        "ABSOLUTE_SESSION_HOURS",
        "TRUSTED_DEVICE_REFRESH_DAYS",
    ):
        assert not hasattr(services, name), f"{name} is back in services.py"

    # …and the two the ruling explicitly did NOT move are still there.
    assert services.TEMP_PASSWORD_VALID_DAYS == 7
    assert services.PASSWORD_HISTORY_BLOCK == 5


# ═══════════════════════════════════════════════════════════════════════════
# T9 · the nightly sweep deletes only what is finished with
# ═══════════════════════════════════════════════════════════════════════════
def test_t9_the_sweep_deletes_expired_and_signed_out_and_NEVER_a_live_one(idn):
    from apps.identity import session_cleanup

    users = idn.seed_silvercreek()
    now = timezone.now()

    live = Session.objects.create(
        user=users.priya,
        tenant=idn.silvercreek,
        last_seen_at=now,
        expires_at=now + timedelta(hours=8),
    )
    idle_but_not_expired = Session.objects.create(
        user=users.priya,
        tenant=idn.silvercreek,
        last_seen_at=now - timedelta(days=3),  # long idle — still NOT expired
        expires_at=now + timedelta(hours=8),
    )
    expired = Session.objects.create(
        user=users.priya,
        tenant=idn.silvercreek,
        last_seen_at=now - timedelta(hours=20),
        expires_at=now - timedelta(hours=1),
    )
    signed_out = Session.objects.create(
        user=users.alex,
        tenant=idn.silvercreek,
        last_seen_at=now,
        expires_at=now + timedelta(hours=8),
        revoked_at=now,
    )

    deleted = session_cleanup.purge_staff_sessions(idn.silvercreek.id)
    assert deleted == 2, deleted

    surviving = set(Session.objects.values_list("pk", flat=True))
    assert live.pk in surviving
    # ⚠ AN IDLE SESSION IS NOT AN EXPIRED ONE. A persistent one is REFRESHED
    # past its idle window, so a sweep that read the idle rule would be
    # deleting rows the authenticator is still willing to renew.
    assert idle_but_not_expired.pk in surviving
    assert expired.pk not in surviving
    assert signed_out.pk not in surviving


def test_t9_a_row_that_is_both_expired_and_signed_out_is_counted_once(idn):
    """The filter is a UNION of two conditions, so the overlap must not
    double-count — a count is what the operator reads."""
    from apps.identity import session_cleanup

    users = idn.seed_silvercreek()
    now = timezone.now()
    Session.objects.create(
        user=users.priya,
        tenant=idn.silvercreek,
        last_seen_at=now,
        expires_at=now - timedelta(hours=1),
        revoked_at=now,
    )
    assert session_cleanup.purge_staff_sessions(idn.silvercreek.id) == 1


def test_t9_one_utilitys_sweep_leaves_anothers_rows_alone(idn):
    """The app-layer half. The DATABASE half is `test_cr145_migration_pg.py`."""
    from apps.identity import session_cleanup

    users = idn.seed_silvercreek()
    jordan, _m = idn.seed_bluemesa_admin()
    now = timezone.now()

    Session.objects.create(
        user=users.priya,
        tenant=idn.silvercreek,
        last_seen_at=now,
        expires_at=now - timedelta(hours=1),
    )
    neighbour = Session.objects.create(
        user=jordan,
        tenant=idn.bluemesa,
        last_seen_at=now,
        expires_at=now - timedelta(hours=1),
    )

    assert session_cleanup.purge_staff_sessions(idn.silvercreek.id) == 1
    assert Session.objects.filter(pk=neighbour.pk).exists()


def test_t9_the_beat_entry_is_declared_AND_installed(idn):
    """Hard-won law 2: a correct schedule and an INSTALLED one are two claims.

    `install()` is called from `IdentityConfig.ready()`; this asserts the
    entry it produces, against a stand-in app, so no broker is needed.
    """
    from types import SimpleNamespace

    from apps.identity import session_cleanup

    schedule = session_cleanup.beat_schedule()
    assert set(schedule) == {"identity.session_cleanup"}
    assert schedule["identity.session_cleanup"]["task"] == session_cleanup.CLEANUP_TASK

    registered = {}
    fake = SimpleNamespace(
        conf=SimpleNamespace(beat_schedule={"someone.else": {}}),
        task=lambda name, bind: (lambda fn: registered.setdefault(name, fn) or fn),
    )
    result = session_cleanup.install(fake)
    assert result["installed"] is True
    # ⚠ It UPDATES rather than replaces — two modules sharing the dict means
    # whichever `ready()` runs last would otherwise erase the other's entry.
    assert "someone.else" in fake.conf.beat_schedule
    assert "identity.session_cleanup" in fake.conf.beat_schedule
    assert set(registered) == {session_cleanup.CLEANUP_TASK, session_cleanup.CLEANUP_ONE_TASK}
