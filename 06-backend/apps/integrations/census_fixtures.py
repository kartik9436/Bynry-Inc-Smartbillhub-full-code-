"""Recorded answers for a Census geocoder at a `.example` address — tests and walkthroughs only.

Same rule as `gis_fixtures`: **RFC 2606 reserves `.example` so it can never
resolve**, so a connection pointed at one could never have worked, and answering
it here shadows nothing real. Every other host returns `None` from
`transport_for` and is dialled for real by `adapters/geocoder_census.py`.

    geocoding.geo.census.example        → the documented sample matches; any
                                          other address answers zero matches
    down.geocoding.geo.census.example   → HTTP 503

The match is the Census Bureau's own documented sample answer (their
headquarters), recorded in `apps/metering/geocode.py`'s docstring.
"""

from __future__ import annotations

import io
import urllib.error
import urllib.parse
from typing import Any

HOST = "geocoding.geo.census.example"
DOWN_HOST = "down.geocoding.geo.census.example"
RESERVED_SUFFIX = ".example"

SAMPLE_MATCH = {
    "matchedAddress": "4600 SILVER HILL RD, WASHINGTON, DC, 20233",
    "coordinates": {"x": -76.92744, "y": 38.845985},
}


def recorded_transport(url: str, timeout_s: float) -> Any:
    """url → the parsed JSON the service would send."""
    parts = urllib.parse.urlsplit(url)
    if parts.hostname == DOWN_HOST:
        raise urllib.error.HTTPError(url, 503, "Service Unavailable", {}, io.BytesIO(b""))
    address = (urllib.parse.parse_qs(parts.query).get("address") or [""])[0]
    matched = "4600 SILVER HILL" in address.upper()
    return {
        "result": {
            "input": {"address": {"address": address}, "benchmark": {"benchmarkName": "Public_AR_Current"}},
            "addressMatches": [SAMPLE_MATCH] if matched else [],
        }
    }


def transport_for(url: str) -> Any:
    """The recorded transport for a `.example` host, else `None` (dial for real)."""
    host = urllib.parse.urlsplit(url if "://" in url else f"https://{url}").hostname or ""
    return recorded_transport if host.endswith(RESERVED_SUFFIX) else None
