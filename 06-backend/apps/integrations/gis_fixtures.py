# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-042 (EP-INT-12) §4 Test Data — *"fixture latencies 300 ms
#           and 4,000 ms; candidate 1408 Pecan St · parcel 88214 · 30.2672,
#           −97.7431 (EPSG:4326)"*
# Rules:    BR-INT-022 (the breaker opens on a slow provider — and a fixture
#           that RAISES tests the wrong failure entirely; it must SLEEP) ·
#           BR-INT-048 (`C15`'s budget is a wall-clock fact, so proving it
#           needs a wall clock)
# Tests:    06-backend/tests/test_us_int_042_gis.py
# Impacts:  10-scripts/render-checks/cr069-m-address-search.mjs (the
#           walkthrough drives the same two recordings through the real
#           endpoint) · apps/integrations/services.py (the sample seed points
#           a connection at one of these hosts)
# ───────────────────────────────────────────────────────
"""The City's recorded answers — for hosts that can never resolve.

WHY A FILE, AND WHY IT IS SAFE TO SHIP
---------------------------------------
`US-INT-042` §4 names its test city as `https://gis.brazosbend.example/addr`.
**RFC 2606 reserves `.example` so that it can never resolve**, so a connection
pointed at one is a connection that could never have worked. Serving those
hosts here is therefore not a mock shadowing a real provider — it is the only
way that host can answer at all, and it can never accidentally stand in front
of a real city.

`oauth_fixtures.py` established the shape in wave H and the reason it gives
holds here: the transport is an ARGUMENT, so a rename cannot silently
disconnect it, and the recorded values are obviously synthetic.

⚠ **THE SLOW FIXTURE SLEEPS, IT DOES NOT RAISE, AND THAT IS THE WHOLE POINT
(`US-INT-022` TC-2, quoted in `runtime.py`).** *"A fixture that raises tests
the wrong failure entirely"* — a raising fixture returns instantly, the worker
is freed, and a bounded and an unbounded implementation behave identically. The
failure `C15` is about is a City that answers SLOWLY, so the fixture holds the
call for four seconds and the deadline is what ends it.

HOW A HOST CHOOSES ITS BEHAVIOUR
---------------------------------
The host itself does, so a walkthrough switches branches by editing one field
on Settings rather than by restarting anything:

    gis.brazosbend.example        → 300 ms, four candidates  (the good day)
    slow.gis.brazosbend.example   → 4,000 ms, then the same  (the breaker's day)
    empty.gis.brazosbend.example  → 300 ms, no candidates    (a real answer)
"""

from __future__ import annotations

import io
import re
import time
import urllib.error
import urllib.parse
from typing import Any

#: `US-INT-042` §4's candidate, exactly. The parcel, the coordinates and the
#: frame are the story's own figures and a test asserts them, so a drift here
#: goes red rather than quietly changing what a walkthrough proves.
PECAN_ST = {
    "parcel": "88214",
    "address": "1408 Pecan St",
    "city": "Brazos Bend",
    "state": "TX",
    "zip": "78702",
    "lat": "30.2672",
    "lng": "-97.7431",
    "frame": "EPSG:4326",
    "score": "96",
    "score_scale": "0-100",
    # ── DEF-INT-5600 / DEF-INT-5602, 2026-09-17 ─────────────────────────────
    # ⚠ **THE RECORDING CARRIED NEITHER OF THESE UNTIL THE DAY THEY WERE
    # FIXED, AND THAT IS WHY 42 PASSING TESTS SAID NOTHING ABOUT THEM.**
    # `CR-112` names TWO keys the City is the source of — `PIN` the parcel and
    # `FULLPIN` the ADDRESS POINT — plus its own `Status`. A fixture offering
    # one of the three can only ever prove the one it offers: the step that
    # reads `units.gis_point_id` could FAIL for two reasons and could never
    # PASS for any. That is hard-won law 7's *incapable of passing* shape,
    # sitting in a fixture rather than in a check.
    "point": "88214-0001",
    "status": "ACTIVE",
}

#: Frame 66.1 draws FOUR matches and its blue bar counts them, so the recording
#: carries four. Two are strong and two are close, which is what makes the two
#: WORDS on screen provable rather than asserted about one row.
RECORDED_CANDIDATES: tuple[dict[str, Any], ...] = (
    PECAN_ST,
    {
        "parcel": "88215",
        "point": "88215-0002",
        "status": "ACTIVE",
        "address": "1408 Pecan St, Unit 2",
        "city": "Brazos Bend",
        "state": "TX",
        "zip": "78702",
        "lat": "30.2672",
        "lng": "-97.7431",
        "frame": "EPSG:4326",
        "score": "91",
        "score_scale": "0-100",
    },
    {
        "parcel": "88301",
        "point": "88301-0001",
        "status": "ACTIVE",
        "address": "1408 Pecan Grove Rd",
        "city": "Brazos Bend",
        "state": "TX",
        "zip": "78703",
        "lat": "30.2701",
        "lng": "-97.7502",
        "frame": "EPSG:4326",
        "score": "64",
        "score_scale": "0-100",
    },
    {
        "parcel": "88302",
        "point": "88302-0001",
        "status": "RETIRED",
        "address": "1408 Pecan St W",
        "city": "Brazos Bend",
        "state": "TX",
        "zip": "78702",
        "lat": "30.2688",
        "lng": "-97.7440",
        "frame": "EPSG:4326",
        "score": "58",
        "score_scale": "0-100",
    },
)

FAST_HOST = "gis.brazosbend.example"
SLOW_HOST = "slow.gis.brazosbend.example"
EMPTY_HOST = "empty.gis.brazosbend.example"

#: ── `DEF-INT-5620` / `DEF-INT-9846` · A CITY THAT ANSWERS AND REFUSES US ──
#: ⚠ **NO FIXTURE COULD MAKE THE CITY SAY NO UNTIL 2026-10-07, AND THAT WAS
#: THE WHOLE ESCAPE** — every recording returned rows or slept, so the branch a
#: real City takes after a key rotation or a layer move ran in no test and no
#: walkthrough. Four hosts, one per shape a refusal arrives in. HAND-SHAPED,
#: not recorded (hard-won law 1): the statuses are HTTP's and the `498` body is
#: ArcGIS's documented *invalid token* answer, not a capture from a real city.
KEY_REFUSED_HOST = "key.gis.brazosbend.example"  # HTTP 401
MOVED_HOST = "moved.gis.brazosbend.example"  # HTTP 404
DOWN_HOST = "down.gis.brazosbend.example"  # HTTP 503
TOKEN_BODY_HOST = "token.gis.brazosbend.example"  # 200 OK + an ArcGIS 498 error body

#: ── `DEF-INT-10019` · 2026-10-07 · A 403, AND WHO SAID IT ────────────────
#: Three hosts that all answer `403`, told apart only by the BODY — which is
#: the whole of that defect. `firewall.` is the PO's capture from the live
#: server (Ann Arbor's Cloudflare refusing Python's default agent, body
#: `error code: 1010`, verbatim); `challenge.` is a Cloudflare *Just a moment…*
#: page, HAND-SHAPED to its documented form; `forbidden.` is ArcGIS's own
#: documented `403` JSON, which must stay *key*.
FIREWALL_HOST = "firewall.gis.brazosbend.example"  # 403 + "error code: 1010"
CHALLENGE_HOST = "challenge.gis.brazosbend.example"  # 403 + a challenge page
ARCGIS_FORBIDDEN_HOST = "forbidden.gis.brazosbend.example"  # 403 + ArcGIS JSON

_REFUSING_STATUS = {KEY_REFUSED_HOST: 401, MOVED_HOST: 404, DOWN_HOST: 503}
_REFUSING_403_BODY = {
    FIREWALL_HOST: b"error code: 1010",
    CHALLENGE_HOST: (
        b'<!DOCTYPE html><html lang="en-US"><head><title>Just a moment...</title>'
        b"</head><body><noscript>Enable JavaScript and cookies to continue"
        b"</noscript></body></html>"
    ),
    ARCGIS_FORBIDDEN_HOST: (
        b'{"error":{"code":403,"message":"You do not have permissions to access '
        b'this resource or perform this operation.","details":[]}}'
    ),
}


def refusal_for(url: str) -> Any:
    """What a refusing recorded host answers, or `None` for every other host.

    Raises `HTTPError` for the three status hosts — exactly what `urllib`
    raises — and RETURNS the error body for the `200 OK` one, because that is
    what makes ArcGIS's shape dangerous: it is a successful response. Shared by
    this file's search recording and `gis_esri_fixtures`' layer recording, so
    the address search and the parcel check refuse the same way on one host.
    """
    host = urllib.parse.urlsplit(url if "://" in url else f"https://{url}").hostname or ""
    status = _REFUSING_STATUS.get(host)
    if status is not None:
        raise urllib.error.HTTPError(url, status, "refused", {}, io.BytesIO(b""))
    body = _REFUSING_403_BODY.get(host)
    if body is not None:
        raise urllib.error.HTTPError(url, 403, "Forbidden", {}, io.BytesIO(body))
    if host == TOKEN_BODY_HOST:
        return {"error": {"code": 498, "message": "Invalid token.", "details": []}}
    return None

#: `US-INT-042` §4's two latencies, in SECONDS.
FAST_LATENCY_S = 0.300
SLOW_LATENCY_S = 4.000

#: The suffix this module will answer for, and nothing outside it. A real city
#: cannot end in `.example`, so this cannot shadow one.
RESERVED_SUFFIX = ".example"


def serves(url: str) -> bool:
    """Whether the recorded transport may answer this address at all."""
    host = urllib.parse.urlsplit(url if "://" in url else f"https://{url}").hostname or ""
    return host.endswith(RESERVED_SUFFIX)


def recorded_transport(url: str, timeout_s: float, *, sleep: Any = time.sleep) -> Any:
    """url → parsed JSON, after the latency the HOST declares.

    ⚠ It sleeps the FULL declared latency and lets the caller's deadline be
    what ends the call. Capping the sleep at `timeout_s` would make the slow
    branch answer late-but-successfully, which is the branch that must fail.
    """
    parts = urllib.parse.urlsplit(url if "://" in url else f"https://{url}")
    host = parts.hostname or ""
    if not host.endswith(RESERVED_SUFFIX):
        raise ValueError(f"the recorded City serves only {RESERVED_SUFFIX} hosts, not {host!r}")
    refused = refusal_for(url)
    if refused is not None:
        return refused
    query = dict(urllib.parse.parse_qsl(parts.query))
    # ⚠ **THE RECORDING SPEAKS THE FEATURESERVER'S DIALECT NOW (`DEF-INT-9843`).**
    # It read `q=` until 2026-10-07, which is exactly why the adapter could send
    # `q=` to a real ArcGIS layer for a month with every test green: the test
    # City understood the same wrong question the code asked. It now reads the
    # typed text out of the `where` the adapter sends, and refuses a request
    # without `outSR=4326` (`DEF-INT-9844`) rather than answering it.
    if query.get("outSR") != "4326":
        raise AssertionError(f"outSR was {query.get('outSR')!r}, not 4326")
    typed = typed_from_where(query.get("where") or "").strip().lower()

    if host == SLOW_HOST:
        sleep(SLOW_LATENCY_S)
    else:
        sleep(FAST_LATENCY_S)

    if host == EMPTY_HOST or not typed:
        return {"candidates": []}
    matches = [one for one in RECORDED_CANDIDATES if typed in one["address"].lower()]
    return {"candidates": matches}


def typed_from_where(where: str) -> str:
    """The clerk's text back out of `gis_search.where_clause`'s `LIKE`.

    Only what this recording needs: the text between `'%` and `%'`, with the
    doubled quote and any LIKE escapes undone. Not a SQL parser and not used
    anywhere but a `.example` host.
    """
    match = re.search(r"LIKE UPPER\('%(.*)%'\)", where)
    if not match:
        return ""
    text = match.group(1).replace("''", "'")
    return re.sub(r"\\(.)", r"\1", text)


def transport_for(base_url: str) -> Any:
    """The transport a connection at `base_url` should use, or `None`.

    `None` means *dial it for real*. Returning the recorded one for every host
    would be a fixture in production; returning it for `.example` only is the
    honest reading of a reserved name.
    """
    return recorded_transport if serves(base_url) else None


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-INT-042@this-commit (EP-INT-12 §4 Test Data verbatim; US-INT-022 TC-2's sleeping-fixture rule)
# generated: 2026-09-06 by the CR-069 wave M build lane
# checklist: A✔ B=n/a C✔ D=n/a E=n/a F✔ G✔ H=n/a
# gates: pytest tests/test_us_int_042_gis.py
# exceptions: none — the module refuses any host outside the reserved suffix, by name
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
