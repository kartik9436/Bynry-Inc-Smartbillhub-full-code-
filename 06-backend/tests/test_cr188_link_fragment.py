"""One-time link secrets travel in the URL FRAGMENT, never the query string.

Decision log 2026-10-22 (coordinator, lane MERGE-ACCESS): a browser never sends
the part after `#` to any server, so a web server, proxy or CDN log cannot hold
the secret; a query string is logged by all three. `core.public_origin.
public_app_link` takes the secret as `fragment=` and both emailed links — the
staff set-password link (CR-188-BRC10) and the customer portal's reset link
(DEF-CWP-10381) — use it. Links already emailed with `?token=` keep working:
the server reads the secret from the POST body, never from a URL, and both
pages read the fragment first and the query second.
"""

from __future__ import annotations

from urllib.parse import parse_qs, urlsplit

from core import public_origin

ORIGIN = "https://app.example.test"


def test_fragment_is_encoded_after_the_hash(settings):
    settings.PUBLIC_APP_ORIGIN = ORIGIN
    link = public_origin.public_app_link("/blue-mesa/set-password", fragment={"token": "a+b/c="})
    parts = urlsplit(link)
    assert link.startswith(f"{ORIGIN}/blue-mesa/set-password#token=")
    assert parts.query == ""
    assert parse_qs(parts.fragment) == {"token": ["a+b/c="]}


def test_query_and_fragment_together_keep_their_places(settings):
    settings.PUBLIC_APP_ORIGIN = ORIGIN
    link = public_origin.public_app_link("/x", {"lang": "fr"}, fragment={"ref": "1", "token": "t"})
    assert link == f"{ORIGIN}/x?lang=fr#ref=1&token=t"


def test_no_origin_still_fails_closed_with_a_fragment(settings):
    settings.PUBLIC_APP_ORIGIN = ""
    assert public_origin.public_app_link("/x", fragment={"token": "t"}) is None


def test_the_portal_reset_link_carries_both_halves_in_the_fragment(settings):
    from apps.portal import credentials

    settings.PUBLIC_APP_ORIGIN = ORIGIN
    issued = credentials.IssuedCode(row_id="row-1", channel="email", masked="m", code="secret")
    link = credentials.reset_link("pine-hill", issued)
    parts = urlsplit(link)
    assert parts.path == "/pine-hill/portal/forgot-password"
    assert parts.query == "", "a one-time secret in the query string reaches server logs"
    assert parse_qs(parts.fragment) == {"ref": ["row-1"], "token": ["secret"]}
