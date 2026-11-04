# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-CWP-9717 (the portal address showed the API's host)
# Rules:    PO ruling 2026-10-05, verbatim: *"(a) A setting per environment:
#           each host names its public address, for example
#           https://app-sand.bynry.com. The address is always the same, whoever
#           opens the page."* · CLAUDE.md hard-won laws 3 and 4
# Tests:    tests/test_def_cwp_9717_portal_address_host.py
# ───────────────────────────────────────────────────────
"""THE ONE PLACE THE SERVER LEARNS WHERE CUSTOMERS AND STAFF OPEN THE APP.

Since `CR-144-BRC07` (2.388.0) the front end is static files on its own host
(`app-sand.bynry.com`) and the browser calls the API on another
(`api-smart360-sandbox.bynry.com`). So the host a request ARRIVED on is the
API's, and nothing a customer should ever be sent to. An address the server
hands out for a person to type, scan or click is therefore built from
`settings.PUBLIC_APP_ORIGIN`, typed per environment, and never from the request.

It is not the browser's `Origin` header either, though that would have worked
on the Settings screen: a QR code on a bill or a link in a letter is built by a
background job where no browser exists, and the PO's ruling is that the
address is the same whoever opens the page.

⚠ **FAILS CLOSED (law 3).** Unset, or written as anything but a bare
`scheme://host[:port]` — a trailing slash, a path, a wildcard, credentials —
answers `None`, and the caller shows no address rather than a guessed one. A
malformed value is logged once per read so the cause is findable.

⚠ **LAW 4: a host that already has a `.env` does not get this value from
`.env.example`.** It has to be typed on each host.
"""

from __future__ import annotations

import logging
from urllib.parse import urlencode, urlsplit

from django.conf import settings

logger = logging.getLogger(__name__)

_SCHEMES = frozenset({"https", "http"})


def public_app_origin() -> str | None:
    """`PUBLIC_APP_ORIGIN` when it is a bare web origin, else `None`."""
    value = (getattr(settings, "PUBLIC_APP_ORIGIN", "") or "").strip()
    if not value:
        return None
    parts = urlsplit(value)
    bare = (
        parts.scheme in _SCHEMES
        and bool(parts.hostname)
        and "*" not in value
        and parts.username is None
        and parts.password is None
        and parts.path == ""
        and not parts.query
        and not parts.fragment
        and value == f"{parts.scheme}://{parts.netloc}"
    )
    if not bare:
        logger.error(
            "PUBLIC_APP_ORIGIN=%r is not a bare origin such as https://app.bynry.com; "
            "no public address will be shown until it is corrected",
            value,
        )
        return None
    return value


def public_app_link(
    path: str,
    query: dict[str, str] | None = None,
    *,
    fragment: dict[str, str] | None = None,
) -> str | None:
    """An ABSOLUTE address a person can click: `PUBLIC_APP_ORIGIN` + `path`.

    `CR-188-BRC10` (PO 2026-10-22, answer 3: *"add one server setting for the
    product's public address"*). **That setting is `PUBLIC_APP_ORIGIN`, which
    already existed** (`DEF-CWP-9717`); a second variable for the same fact is
    two places to type it and two values to drift apart, so this builds on the
    one reader above instead of minting `PUBLIC_APP_URL`.

    `path` starts with `/` — e.g. `/blue-mesa/set-password`. `query` and
    `fragment` are each encoded with `urlencode`, so a token never breaks the
    address it travels in.

    ⚠ **A ONE-TIME SECRET GOES IN `fragment`, NEVER IN `query`** (decision log
    2026-10-22, *"One-time link secrets travel in the URL FRAGMENT"*). A
    browser never sends the part after `#` to any server, so the web server,
    a proxy or a CDN cannot log it; a query string is logged by all three.
    `/blue-mesa/set-password#token=…`. The page reads it from the fragment and
    takes it off the address bar.

    ⚠ **FAILS CLOSED (law 3):** no usable origin → `None`, and the caller says
    *not sent* rather than mailing a relative path nobody can open.
    """
    origin = public_app_origin()
    if origin is None:
        return None
    clean = "/" + str(path or "").lstrip("/")
    link = f"{origin}{clean}"
    if query:
        link = f"{link}?{urlencode(query)}"
    if fragment:
        link = f"{link}#{urlencode(fragment)}"
    return link
