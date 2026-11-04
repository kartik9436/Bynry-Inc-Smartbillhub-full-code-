# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-002 (EP-CWP-01) — the throttle, and a lockout on the two
#           lookups worth guessing at. Screens: CWP-002 · CWP-012
# Rules:    BR-CWP-022 (sixty a minute per address — the throttle the product
#           already applies, REUSED) · BR-CWP-023 (five wrong pairs → fifteen
#           minutes, per tenant · per form · per address) · BR-CWP-025
# Tests:    this file — TC-1 (60 accepted), TC-2 (the 61st refused in five or
#           six words), TC-3 (six wrong pairs lock, and a CORRECT pair inside
#           the window is still refused), TC-4 (a second address is not
#           locked), TC-5 (locking track does not lock quick pay), TC-6 (a
#           lockout is per tenant), TC-7 (after the window a correct pair is
#           accepted and the counter is reset) · 007 TC-5 (the 61st report)
# Impacts:  apps/portal/lockout.py · guest_api.py · guards.py
# ───────────────────────────────────────────────────────
"""US-CWP-002 — the guest surface cannot be used to enumerate accounts."""

import pytest
from django.core.cache import cache

from apps.portal import guest_api, lockout
from tests.test_us_cwp_helpers import *  # noqa: F401,F403
from tests.test_us_cwp_helpers import switch_on
from tests.test_us_ten_helpers import api_call

FIRST = "198.51.100.10"
SECOND = "203.0.113.7"
REPORT = {
    "kind": "leak_or_burst",
    "location_text": "1408 Elm St, Austin TX 78702",
    "notes": "Water in the road.",
    "reporter_name": "D. Okafor",
    "reporter_phone": "(512) 555-7730",
}


@pytest.fixture(autouse=True)
def _clean_cache():
    """Both guards count in the cache, so a test that inherited another's count
    would be measuring the wrong thing."""
    cache.clear()
    yield
    cache.clear()


def _track(tenant, reference, second_fact, address=FIRST):
    return api_call(
        guest_api.track,
        "post",
        f"/api/{tenant.subdomain}/portal/public/track",
        tenant=tenant,
        data={"reference": reference, "second_fact": second_fact},
        headers={"X-Forwarded-For": address},
    )


def _report(tenant, address=FIRST):
    return api_call(
        guest_api.reports,
        "post",
        f"/api/{tenant.subdomain}/portal/public/reports",
        tenant=tenant,
        data=dict(REPORT),
        headers={"X-Forwarded-For": address},
    )


def _wrong_pairs(tenant, how_many, address=FIRST):
    last = None
    for index in range(how_many):
        last = _track(tenant, f"RP-26-{4130 + index}", "78702", address=address)
    return last


@pytest.mark.django_db
def test_us_cwp_002_tc1_and_tc2_sixty_a_minute_then_the_sixty_first_is_refused(pine_hill, sarah):
    """⚠ THE REFUSAL SENTENCE IS THE PRODUCT'S OWN, five or six words, and it
    names no internal code (B14 rule 33)."""
    import json
    import pathlib

    switch_on(pine_hill, sarah)
    accepted = 0
    refused = None
    for _ in range(61):
        response = _report(pine_hill)
        if response.status_code == 429:
            refused = response
            break
        accepted += 1
    assert accepted == 60, f"sixty a minute are accepted, got {accepted}"
    assert refused is not None and refused.status_code == 429
    assert refused.data["message_key"] == "errors.rate-limited"

    catalogues = pathlib.Path(__file__).resolve().parents[2] / "07-frontend/src/i18n/locales"
    english = json.loads((catalogues / "en.json").read_text(encoding="utf-8"))["errors.rate-limited"]
    assert len(english.split()) <= 6, english
    for path in sorted(catalogues.glob("*.json")):
        assert "errors.rate-limited" in json.loads(path.read_text(encoding="utf-8")), path.name


@pytest.mark.django_db
def test_us_cwp_002_tc3_six_wrong_pairs_lock_and_a_correct_pair_is_still_refused(pine_hill, sarah):
    switch_on(pine_hill, sarah)
    reference = _report(pine_hill).data["reference"]

    for index in range(4):
        response = _track(pine_hill, f"RP-26-{4130 + index}", "78702")
        assert response.data["message_key"] == "portal.track.notFound", index

    fifth = _track(pine_hill, "RP-26-4134", "78702")
    assert fifth.data["message_key"] == "portal.track.notFound"

    sixth = _track(pine_hill, "RP-26-4135", "78702")
    assert sixth.data["message_key"] == "portal.track.locked"
    assert sixth.data["params"]["minutes"] == 15

    # ⚠ AND A CORRECT PAIR INSIDE THE WINDOW IS STILL REFUSED. Guessing until
    # you are right is exactly the attack.
    correct = _track(pine_hill, reference, "78702")
    assert correct.data["message_key"] == "portal.track.locked"


@pytest.mark.django_db
def test_us_cwp_002_tc4_a_second_address_is_not_locked(pine_hill, sarah):
    switch_on(pine_hill, sarah)
    reference = _report(pine_hill).data["reference"]
    _wrong_pairs(pine_hill, 6, address=FIRST)
    assert _track(pine_hill, reference, "78702", address=FIRST).data["message_key"] == "portal.track.locked"
    assert _track(pine_hill, reference, "78702", address=SECOND).status_code == 200


@pytest.mark.django_db
def test_us_cwp_002_tc5_locking_track_does_not_lock_quick_pay(pine_hill, sarah):
    """The two doors are different doors. Quick pay's own endpoint is wave P's;
    the LOCK is per form from the first commit, so it cannot be forgotten
    later."""
    switch_on(pine_hill, sarah)
    _wrong_pairs(pine_hill, 6)
    key = str(pine_hill.id)
    assert lockout.is_locked(key, lockout.FORM_TRACK, FIRST) is True
    assert lockout.is_locked(key, lockout.FORM_QUICK_PAY, FIRST) is False


@pytest.mark.django_db
def test_us_cwp_002_tc6_a_lockout_is_per_tenant(pine_hill, sarah, oak_ridge, elena):
    """⚠ Locking `/pine-hill` leaves `/oak-ridge` open from the same address."""
    switch_on(pine_hill, sarah)
    switch_on(oak_ridge, elena)
    oak_reference = _report(oak_ridge).data["reference"]
    _wrong_pairs(pine_hill, 6)
    assert _track(pine_hill, oak_reference, "78702").data["message_key"] == "portal.track.locked"
    assert _track(oak_ridge, oak_reference, "78702").status_code == 200


@pytest.mark.django_db
def test_us_cwp_002_tc7_after_the_window_a_correct_pair_is_accepted_and_the_counter_resets(
    pine_hill, sarah
):
    """The window is fifteen minutes of wall clock, so the test expires the key
    rather than waiting: what it proves is that a cleared lock accepts, and that
    a success clears the counter behind it."""
    switch_on(pine_hill, sarah)
    reference = _report(pine_hill).data["reference"]
    _wrong_pairs(pine_hill, 6)
    key = str(pine_hill.id)
    assert lockout.is_locked(key, lockout.FORM_TRACK, FIRST) is True

    cache.delete(f"portal:lock:until:{key}:{lockout.FORM_TRACK}:{FIRST}")  # the window elapsing
    assert _track(pine_hill, reference, "78702").status_code == 200
    assert cache.get(f"portal:lock:attempts:{key}:{lockout.FORM_TRACK}:{FIRST}") is None

    # And the count really is back to zero: four more wrong pairs do not lock.
    _wrong_pairs(pine_hill, 4)
    assert lockout.is_locked(key, lockout.FORM_TRACK, FIRST) is False


@pytest.mark.django_db
def test_us_cwp_002_the_lock_is_not_a_table(pine_hill, sarah):
    """`US-CWP-002` §8, verbatim: *"the lockout state is deliberately NOT a
    table"*. Asserted so a later lane cannot 'improve' it into one without this
    going red."""
    from django.apps import apps as django_apps

    switch_on(pine_hill, sarah)
    _wrong_pairs(pine_hill, 6)
    tables = {model._meta.db_table for model in django_apps.get_models()}
    assert not any("lockout" in name or "attempt" in name for name in tables), sorted(tables)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CWP-002@d6d31c46 (EP-CWP-01 §3 cases, written before the code)
# generated: 2026-09-04 by the CR-068 wave B build lane
# checklist: A✔ B✔ C✔ D✔ E=n/a(test file) F✔ G✔ H=n/a
# gates: pytest tests/test_us_cwp_002_lockout.py
# exceptions: TC-7's fifteen minutes are expired by deleting the cache key rather than by sleeping — what is proved is that a cleared lock accepts and a success resets the counter, and the TTL itself is asserted on the constant
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────


# ══ DEF-CWP-10710 (audit L3-02) — a forged X-Forwarded-For is not a new address ══


def _behind_proxies(settings, count):
    """Set the ONE setting both the throttle and the lock read. Assigning
    `REST_FRAMEWORK` fires `setting_changed`, which DRF answers by reloading
    `api_settings` — so `NUM_PROXIES` moves exactly as a deployment's would."""
    settings.TRUSTED_PROXY_COUNT = count
    settings.REST_FRAMEWORK = {**settings.REST_FRAMEWORK, "NUM_PROXIES": count}


@pytest.mark.django_db
def test_def_cwp_10710_rotating_the_header_with_no_proxy_still_locks_after_five(
    pine_hill, sarah, settings
):
    """No trusted proxy (the default): the header is the visitor's own words and
    is not read at all. Six wrong pairs, each carrying a DIFFERENT
    `X-Forwarded-For`, from one real peer — the sixth is locked."""
    _behind_proxies(settings, 0)
    switch_on(pine_hill, sarah)
    answers = [
        _track(pine_hill, f"RP-26-{4130 + n}", "78702", address=f"10.9.8.{n}").data["message_key"]
        for n in range(6)
    ]
    assert answers[:5] == ["portal.track.notFound"] * 5, answers
    assert answers[5] == "portal.track.locked", answers


@pytest.mark.django_db
def test_def_cwp_10710_behind_one_proxy_a_forged_prefix_moves_nothing(pine_hill, sarah, settings):
    """One load balancer of ours: it APPENDS the address it saw. A visitor
    prepending a fresh fake address on every guess is still the same visitor,
    because the lock reads the hop our proxy wrote — the throttle's identity."""
    _behind_proxies(settings, 1)
    switch_on(pine_hill, sarah)
    answers = [
        _track(pine_hill, f"RP-26-{4130 + n}", "78702", address=f"10.9.8.{n}, {FIRST}").data[
            "message_key"
        ]
        for n in range(6)
    ]
    assert answers[5] == "portal.track.locked", answers
    assert lockout.is_locked(str(pine_hill.id), lockout.FORM_TRACK, FIRST) is True


def test_def_cwp_10710_the_lock_and_the_throttle_name_the_same_caller(settings):
    """One identity, read one way: `address_of` IS DRF's `get_ident`, at every
    proxy depth, including a chain shorter than the depth."""
    from rest_framework.test import APIRequestFactory
    from rest_framework.throttling import BaseThrottle

    chains = ("", "1.1.1.1", "1.1.1.1, 2.2.2.2", "1.1.1.1, 2.2.2.2, 3.3.3.3")
    for count in (0, 1, 2):
        _behind_proxies(settings, count)
        for chain in chains:
            request = APIRequestFactory().get("/x", REMOTE_ADDR="9.9.9.9")
            if chain:
                request.META["HTTP_X_FORWARDED_FOR"] = chain
            assert lockout.address_of(request) == BaseThrottle().get_ident(request), (count, chain)
            if count == 0:
                assert lockout.address_of(request) == "9.9.9.9"
