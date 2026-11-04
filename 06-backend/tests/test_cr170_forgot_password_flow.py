# ── Trace ──────────────────────────────────────────────
# Change:   CR-170-BRC10 — forgot password (PO 2026-10-05, decision log
#           *"FORGOT PASSWORD"*): ask the System Admin → admin resets → forced
#           new password → the session ends → sign in again with the new one.
# Rules:    BR-IDN-022 (as amended 2026-10-05) · BR-IDN-023 (as amended
#           2026-10-05) · BR-IDN-005 · BR-IDN-021 (no email) · BR-IDN-025 (7 days)
# Tests:    the server half of the PO's whole flow, end to end, through HTTP.
# ───────────────────────────────────────────────────────
"""The PO's forgot-password flow, as the SERVER sees it, in one walk.

Nothing on the server changed for `CR-170-BRC10`: the admin reset, the 7-day
temporary password, the forced change and the sign-out all already existed.
What changed is that the screen now ENDS the session after the forced change
(through the existing `DELETE /auth/session`) and sends the person to sign in
again. So this file proves the thing that sign-in-again depends on — that after
the change and the sign-out **the temporary password is dead and the new one
works** — and it proves it through the same four requests the screens make,
rather than through the service functions underneath them.

It runs on SQLite with the ordinary suite and on real PostgreSQL under
`config.settings.pgtest` (RLS `FORCE` on), and both were run for this change.
"""

from django.test import Client

from tests.test_us_idn_helpers import (  # noqa: F401 (fixture import)
    api_delete,
    api_get,
    api_post,
    api_sign_in,
    idn,
    live_sessions_for,
    signed_in_client,
)

import pytest

pytestmark = pytest.mark.django_db

PRIYA = "priya@silvercreek.example"
NEW_PASSWORD = "Harbor2026tide"


def test_cr170__reset_change_sign_out_then_only_the_new_password_works(idn):
    users = idn.seed_silvercreek()

    # 1 · The System Admin resets Priya on Settings › Users & roles.
    alex = signed_in_client("alex@silvercreek.example", "Canyon2026rapids")
    issued = api_post(alex, f"/users/{users.priya.id}/temp-password")
    assert issued.status_code == 200
    temp = issued.json()["temp_password"]

    # 2 · Priya signs in with the temporary password and owes a change.
    priya = Client()
    signed_in = api_sign_in(priya, PRIYA, temp)
    assert signed_in.status_code == 201
    assert signed_in.json()["user"]["must_change_password"] is True

    # 3 · She sets a new password (the forced change asks for no current one).
    changed = api_post(
        priya,
        "/me/password",
        {"new_password": NEW_PASSWORD, "confirm_password": NEW_PASSWORD},
    )
    assert changed.status_code == 204

    # 4 · The screen ends the session through the EXISTING sign-out.
    signed_out = api_delete(priya, "/auth/session")
    assert signed_out.status_code == 204
    assert live_sessions_for(users.priya) == 0
    assert api_get(priya, "/me").status_code == 401  # that browser holds nothing now

    # 5 · The temporary password no longer works…
    replay = api_sign_in(Client(), PRIYA, temp)
    assert replay.status_code == 401
    assert replay.json()["message_key"] == "errors.auth.sign_in_failed"

    # 6 · …and the new one does, straight into the product, no change owed.
    again = Client()
    fresh = api_sign_in(again, PRIYA, NEW_PASSWORD)
    assert fresh.status_code == 201
    assert fresh.json()["user"]["must_change_password"] is False
    assert api_get(again, "/me").status_code == 200


def test_cr170__sign_out_is_admitted_while_a_change_is_still_owed(idn):
    """The screen's sign-out must also work for someone who walks AWAY from the
    forced change — `_FORCED_CHANGE_EXEMPT` admits `DELETE /auth/session`."""
    users = idn.seed_silvercreek()
    alex = signed_in_client("alex@silvercreek.example", "Canyon2026rapids")
    temp = api_post(alex, f"/users/{users.priya.id}/temp-password").json()["temp_password"]
    priya = signed_in_client(PRIYA, temp)
    assert api_get(priya, "/me").status_code == 403  # gated until the change
    assert api_delete(priya, "/auth/session").status_code == 204
    assert live_sessions_for(users.priya) == 0
