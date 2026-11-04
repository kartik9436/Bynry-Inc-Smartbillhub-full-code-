# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-017 (find my account, CWP-016) · US-CWP-018 (prove it is
#           you, CWP-017) · US-CWP-019 (choose a password, CWP-018) ·
#           US-CWP-020 (forgotten password, CWP-019) · US-CWP-016 (the front
#           door and sign in, CWP-015). Screens: CWP-015 … CWP-019
#           ⚠ **THESE FIVE READ `016 (find my account)` … `020 (sign in)`
#           UNTIL 2026-09-05 — EVERY ONE OF THEM WRONG (`DEF-CWP-3862`).**
#           `EP-CWP-05` is the authority and NOTHING IS RENUMBERED: the SCREEN
#           ids were right and the STORY ids were not. Two series running one
#           apart make every wrong pairing look plausible — `US-CWP-018` and
#           `CWP-018` are both real and both wrong for each other — so each
#           story is cited WITH its screen above, which is the only form in
#           which a bad pairing is visible on the line.
#           ⚠ **THE TEST FUNCTION NAMES BELOW STILL CARRY THE WAVE'S IDS AND
#           ARE NOT CORRECTED HERE, DELIBERATELY.** They are not a clean
#           one-low shift: `test_us_cwp_020_tc1` is `US-CWP-016` **TC-2**, so
#           renaming them means re-deriving each case against `EP-CWP-05`'s TC
#           tables one at a time. Guessing that map would write a false claim
#           into a test name, which is worse than a recorded divergence. The
#           mapping to apply when somebody does it:
#             test_us_cwp_016_tc* = US-CWP-017 find my account
#             test_us_cwp_017_tc* = US-CWP-018 the code
#             test_us_cwp_018_tc* = US-CWP-019 the password
#             test_us_cwp_019_tc* = US-CWP-020 the reset
#             test_us_cwp_020_tc* = US-CWP-016 the front door / sign in
# Rules:    BR-CWP-030/031/032/033/034/035/036/037/038 · BR-CWP-004
# Tests:    this file
# Impacts:  apps/portal/api.py · credentials.py · session.py
# ───────────────────────────────────────────────────────
"""Wave E's disclosure rules, each as the case that would catch its breach.

⚠ **THESE RUN ON THE DEFAULT SQLITE SUITE AND PROVE NOTHING ABOUT RLS.** The
isolation half is `tests/test_us_cwp_021_pg.py` and runs on real PostgreSQL
under a non-superuser probe role (law 14). What is proved here is the
DISCLOSURE, which is application logic and is the same on both engines.
"""

from __future__ import annotations

import json

import pytest
from django.test import Client

from apps.notifications import models as notification_models
from apps.portal import models as portal_models
from core.tenancy import tenant_context
from tests.test_us_cwp_helpers import *  # noqa: F401,F403
from tests.test_us_cwp_helpers import (
    MARIA_EMAIL,
    MARIA_PASSWORD,
    elm_street_account,
    enrol_maria,
    switch_on,
)

ACCOUNT_FACTS = {"postcode": "78702", "last_name": "Alvarez"}


def portal_url(tenant, path: str) -> str:
    return f"/api/{tenant.subdomain}/portal/{path}"


def post(tenant, path: str, body: dict, client: Client | None = None):
    return (client or Client()).post(
        portal_url(tenant, path), data=json.dumps(body), content_type="application/json"
    )


def live_account(tenant, actor):
    switch_on(tenant, actor)
    return elm_street_account(tenant, actor)


# ══ US-CWP-017 (CWP-016) · BR-CWP-032 — matched discloses NOTHING ═════════


@pytest.mark.django_db
def test_us_cwp_016_tc2_a_match_carries_no_name_no_balance_no_address(pine_hill, sarah):
    """⚠ **THE ASSERTION IS OVER THE WHOLE BODY, NOT OVER THREE NAMED KEYS.**

    `BR-CWP-032` is *"has told the visitor nothing"*, and a check that named
    `name`, `balance` and `address` would pass the day somebody adds
    `customer_no`. The allow-list below is the rule; anything else is a leak.
    """
    account = live_account(pine_hill, sarah)
    response = post(
        pine_hill,
        "enrol/find-account",
        {"account_number": account.account_no, **ACCOUNT_FACTS},
    )
    assert response.status_code == 200, response.content
    body = response.json()
    assert body["matched"] is True
    allowed = {"matched", "account_ref", "sent_to", "channel", "expires_in_minutes", "reason"}
    assert set(body) <= allowed, f"the body carries {set(body) - allowed} — BR-CWP-032"
    # And the masked contact is masked: four digits, never the number.
    assert body["sent_to"].startswith("••• ••• ")
    assert "555" not in body["sent_to"]


@pytest.mark.django_db
def test_us_cwp_016_tc3_a_wrong_surname_answers_exactly_what_an_unknown_number_does(
    pine_hill, sarah
):
    """Two different failures, one indistinguishable body (`BR-CWP-032`)."""
    account = live_account(pine_hill, sarah)
    wrong_name = post(
        pine_hill,
        "enrol/find-account",
        {"account_number": account.account_no, "postcode": "78702", "last_name": "Nobody"},
    )
    unknown = post(
        pine_hill,
        "enrol/find-account",
        {"account_number": "ACC-00000-Z", **ACCOUNT_FACTS},
    )
    assert wrong_name.status_code == unknown.status_code == 200
    # Compared as BYTES, not as parsed dicts: two bodies that differ only in
    # key order are two bodies, and a person reading a response sees the bytes.
    assert wrong_name.content == unknown.content, (
        "a wrong surname and an unknown account number must be refused identically "
        f"— {wrong_name.content!r} vs {unknown.content!r} (BR-CWP-032)"
    )


@pytest.mark.django_db
def test_us_cwp_016_tc4_three_wrong_tries_lock_the_form_for_fifteen_minutes(pine_hill, sarah):
    """`BR-CWP-036` — three, not five. The enrolment form is a public guessing
    surface and a staff sign-in page behind a VPN is not."""
    live_account(pine_hill, sarah)
    reasons = [
        post(pine_hill, "enrol/find-account", {"account_number": "ACC-00000-Z", **ACCOUNT_FACTS})
        .json()
        .get("reason")
        for _ in range(3)
    ]
    assert reasons[:2] == ["not_matched", "not_matched"], reasons
    assert reasons[2] == "locked", reasons
    # A CORRECT set inside the window is refused too — that is what makes it a
    # lockout rather than a delay.
    account = elm_street_account(pine_hill, sarah)
    correct = post(
        pine_hill,
        "enrol/find-account",
        {"account_number": account.account_no, **ACCOUNT_FACTS},
    ).json()
    assert correct["matched"] is False and correct["reason"] == "locked"


@pytest.mark.django_db
def test_us_cwp_016_tc5_the_code_goes_to_the_stored_contact_and_nowhere_else(pine_hill, sarah):
    """`BR-CWP-033` — the outbound row's DESTINATION is asserted, not the screen."""
    account = live_account(pine_hill, sarah)
    body = post(
        pine_hill,
        "enrol/find-account",
        {"account_number": account.account_no, **ACCOUNT_FACTS},
    ).json()
    with tenant_context(pine_hill.id):
        row = portal_models.PortalOneTimeCode.objects.get(pk=body["account_ref"])
        queued = notification_models.OutboundMessage.objects.get(pk=row.outbound_message_id)
        contact = customer_contact(pine_hill, account)
    assert queued.recipient_address == contact, (
        "the code was queued to an address that is not the contact on file (BR-CWP-033)"
    )
    # ⚠ AND ON THE SMS CHANNEL ONLY — `source_type="portal"` carries NO print
    # floor, so nothing posts a six-digit login code by letter.
    assert queued.channel == notification_models.CHANNEL_SMS
    with tenant_context(pine_hill.id):
        printed = notification_models.OutboundMessage.objects.filter(
            source_type="portal", channel=notification_models.CHANNEL_PRINT
        ).count()
    assert printed == 0, "a one-time code was queued for POST — see SOURCE_TYPES `portal`"


def customer_contact(tenant, account):
    from apps.customers import models as customers_models

    with tenant_context(tenant.id):
        contact = (
            customers_models.Contact.objects.filter(tenant_id=tenant.id, account_id=account.pk)
            .order_by("-is_primary", "created_at")
            .first()
        )
    return contact.phone or str(contact.email)


@pytest.mark.django_db
def test_us_cwp_017_tc4_an_account_with_no_contact_dead_ends(pine_hill, sarah):
    """`BR-CWP-034` — it must NEVER fall back to something weaker, so the
    answer names the dead end and carries no `account_ref` to go on with."""
    from apps.customers import models as customers_models

    account = live_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        customers_models.Contact.objects.filter(account_id=account.pk).update(
            phone=None, email=None
        )
    body = post(
        pine_hill,
        "enrol/find-account",
        {"account_number": account.account_no, **ACCOUNT_FACTS},
    ).json()
    assert body["matched"] is True
    assert body["reason"] == "no_contact_on_file"
    assert body["account_ref"] is None


# ══ US-CWP-018 (CWP-017) · the code ═══════════════════════════════════════


def issue_and_read_code(tenant, account):
    """Find the account, then read the code off the QUEUE — which is exactly
    what the demo does while W6 is not activated."""
    body = post(
        tenant, "enrol/find-account", {"account_number": account.account_no, **ACCOUNT_FACTS}
    ).json()
    with tenant_context(tenant.id):
        row = portal_models.PortalOneTimeCode.objects.get(pk=body["account_ref"])
        queued = notification_models.OutboundMessage.objects.get(pk=row.outbound_message_id)
    return body["account_ref"], queued.render_context["code"]


@pytest.mark.django_db
def test_us_cwp_017_tc1_the_code_off_the_queue_is_accepted_once(pine_hill, sarah):
    account = live_account(pine_hill, sarah)
    ref, code = issue_and_read_code(pine_hill, account)
    first = post(pine_hill, "enrol/verify-code", {"account_ref": ref, "code": code}).json()
    assert first["result"] == "ok"
    # SINGLE USE — `consumed_at` is set, so the same code is now `wrong`.
    again = post(pine_hill, "enrol/verify-code", {"account_ref": ref, "code": code}).json()
    assert again["result"] == "wrong"


@pytest.mark.django_db
def test_us_cwp_017_tc5_a_resend_invalidates_the_first_code(pine_hill, sarah):
    """Without `superseded_at` the first message still works after the second
    arrives — so a code read over somebody's shoulder stays live for its whole
    ten minutes even though the person asked for a new one."""
    account = live_account(pine_hill, sarah)
    first_ref, first_code = issue_and_read_code(pine_hill, account)
    second_ref, second_code = issue_and_read_code(pine_hill, account)
    assert first_ref != second_ref and first_code != second_code
    stale = post(pine_hill, "enrol/verify-code", {"account_ref": first_ref, "code": first_code})
    assert stale.json()["result"] == "wrong"
    fresh = post(pine_hill, "enrol/verify-code", {"account_ref": second_ref, "code": second_code})
    assert fresh.json()["result"] == "ok"


@pytest.mark.django_db
def test_us_cwp_017_tc6_six_wrong_codes_lock_it(pine_hill, sarah):
    account = live_account(pine_hill, sarah)
    ref, _code = issue_and_read_code(pine_hill, account)
    results = [
        post(pine_hill, "enrol/verify-code", {"account_ref": ref, "code": "000000"}).json()[
            "result"
        ]
        for _ in range(6)
    ]
    assert results[:5] == ["wrong"] * 5, results
    assert results[5] == "locked", results


# ══ US-CWP-019 (CWP-018) · the password and the consequence panel ═════════


@pytest.mark.django_db
def test_us_cwp_018_tc3_eight_characters_are_refused_where_the_tenant_asks_for_twelve(
    pine_hill, sarah
):
    """`BR-CWP-037` — the policy is READ, never hardcoded."""
    from apps.identity.models import SecurityPolicy

    account = live_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        SecurityPolicy.objects.update_or_create(
            tenant_id=pine_hill.id, defaults={"pw_min_length": 12}
        )
    ref, code = issue_and_read_code(pine_hill, account)
    post(pine_hill, "enrol/verify-code", {"account_ref": ref, "code": code})
    refused = post(
        pine_hill,
        "enrol/set-password",
        {"account_ref": ref, "email": MARIA_EMAIL, "password": "Abcdefg1", "otp_channel": "sms"},
    )
    assert refused.status_code == 422, refused.content
    assert "too_short" in refused.json()["failures"]
    assert refused.json()["min_length"] == 12


@pytest.mark.django_db
def test_us_cwp_018_tc4_set_password_is_guarded_on_the_endpoint_not_the_wizard(
    pine_hill, sarah
):
    """Post straight to it with a code that was never proved → 404. A screen
    order is not a security control (`US-CWP-019` TC-4 — the story is *choose
    a password*; the function name's `018` is the wave's, `DEF-CWP-3862`)."""
    account = live_account(pine_hill, sarah)
    ref, _code = issue_and_read_code(pine_hill, account)  # issued, NEVER verified
    straight = post(
        pine_hill,
        "enrol/set-password",
        {"account_ref": ref, "email": MARIA_EMAIL, "password": "Elm-Street-1408", "otp_channel": "sms"},
    )
    assert straight.status_code == 404, straight.content
    with tenant_context(pine_hill.id):
        assert portal_models.PortalCredential.objects.count() == 0


@pytest.mark.django_db
def test_us_cwp_018_tc5_the_consequence_panel_needs_a_consumed_code(pine_hill, sarah):
    """`BR-CWP-039` — the first screen in the flow that may show a balance, and
    it may only because the person has proved they hold the contact on file."""
    account = live_account(pine_hill, sarah)
    ref, code = issue_and_read_code(pine_hill, account)
    early = post(pine_hill, "enrol/consequences", {"account_ref": ref})
    assert early.status_code == 404, "the panel was served before the code was proved"
    post(pine_hill, "enrol/verify-code", {"account_ref": ref, "code": code})
    panel = post(pine_hill, "enrol/consequences", {"account_ref": ref})
    assert panel.status_code == 200, panel.content
    body = panel.json()
    assert body["account_no"] == account.account_no
    assert body["cannot"] == ["close_account", "change_owner", "move_out"]
    # ⚠ NEVER CACHED — the response says so to the browser too (BR-CWP-047).
    assert "no-store" in panel["Cache-Control"]


# ══ US-CWP-020 (CWP-019) · the reset ══════════════════════════════════════


@pytest.mark.django_db
def test_us_cwp_019_tc2_both_reset_answers_are_byte_identical(pine_hill, sarah, settings):
    """`BR-CWP-038`, and the check is on the BYTES.

    ⚠ **AND THE SIDE EFFECT IS THE HALF A BYTE COMPARISON CANNOT SEE** — no
    email is queued for the address with no login, which is asserted separately
    below.
    """
    # A reset link is only minted when the app's public address is known
    # (`DEF-CWP-10381`: no address, no link, nothing queued).
    settings.PUBLIC_APP_ORIGIN = "https://app.example.test"
    switch_on(pine_hill, sarah)
    enrol_maria(pine_hill, sarah)
    with_login = post(pine_hill, "auth/forgot-password", {"email": MARIA_EMAIL})
    without = post(pine_hill, "auth/forgot-password", {"email": "nobody@example.test"})
    assert with_login.status_code == without.status_code == 200
    assert with_login.content == without.content, (
        f"{with_login.content!r} vs {without.content!r} — BR-CWP-038"
    )
    with tenant_context(pine_hill.id):
        resets = portal_models.PortalOneTimeCode.objects.filter(
            purpose=portal_models.PURPOSE_RESET
        )
        assert resets.count() == 1, "a reset was minted for an address with no login"


# ══ US-CWP-020 · sign in, and the staff credential ════════════════════════


@pytest.mark.django_db
def test_us_cwp_020_tc1_a_staff_email_and_password_get_the_ordinary_failure(pine_hill, sarah):
    """`BR-CWP-004`. **And no session row is written**, which is the half that
    says this is not a branch that found them and refused."""
    switch_on(pine_hill, sarah)
    refused = post(
        pine_hill,
        "auth/sign-in",
        {"email": sample_data.PINE_HILL["signup"]["owner"]["email"], "password": "whatever"},
    )
    assert refused.status_code == 401
    assert refused.json()["reason"] == "wrong"
    with tenant_context(pine_hill.id):
        assert portal_models.PortalSession.objects.count() == 0


@pytest.mark.django_db
def test_us_cwp_020_tc3_a_customer_signs_in_and_the_session_is_scoped_to_this_utility(
    pine_hill, sarah, oak_ridge, elena
):
    """One tenant per session. A Pine Hill cookie presented on Oak Ridge's path
    answers 404 — never 403, which would confirm Oak Ridge exists."""
    switch_on(pine_hill, sarah)
    switch_on(oak_ridge, elena)
    enrol_maria(pine_hill, sarah)
    client = Client()
    signed_in = post(
        pine_hill, "auth/sign-in", {"email": MARIA_EMAIL, "password": MARIA_PASSWORD}, client
    )
    assert signed_in.status_code == 200, signed_in.content
    mine = client.get(portal_url(pine_hill, "session"))
    assert mine.status_code == 200, mine.content
    assert mine.json()["account_count"] == 1
    theirs = client.get(portal_url(oak_ridge, "session"))
    assert theirs.status_code == 404, theirs.content
