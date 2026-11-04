# ── Trace ──────────────────────────────────────────────
# Defects:  DEF-INT-4251 (the Census geocoder had no connection record) · the
#           PO GIS review gap 13, 2026-10-07 (this file — the connection could
#           not be made at all) · see `12-governance/10-defect-log.csv`
# Rules:    BR-INT-019 (a test is ONE real instance) · BR-INT-037 (data, not
#           code) · BR-INT-049 🔒 (a coordinate carries its frame) · CR-028 D6
#           (the geocoder fills EMPTY coordinates only — `apps/metering/geocode.py`)
# Tests:    06-backend/tests/test_gis_lane_d_census_and_city_state.py
# ───────────────────────────────────────────────────────
"""THE US CENSUS GEOCODER, AS AN ADAPTER — so its card can be connected and tested.

WHAT WAS WRONG (PO GIS review gap 13, 2026-10-07)
-------------------------------------------------
`manifests/geocoder_census.py` declared the provider LIVE with an operation, a
test action (*"Geocode one address you type."*) and a service address — and
`adapters/__init__.py` bound no adapter to it. Every **Connect** on its card was
therefore refused *"Cannot be connected yet."* by `services._adapter_or_refuse`,
and `live_calls.provision`, which connects it through the same door, could not
have created its row either. The card said *not set up* over a call
`apps/metering/geocode.py` has been making since `CR-028` — the exact gap
`DEF-INT-4251` was filed to close, closed on paper and not in the dictionary
(hard-won law 2: built is not wired).

WHAT A TEST DOES — ONE REAL LOOKUP
-----------------------------------
`test()` sends the address the person typed (or the Census Bureau's own sample,
their headquarters) to `/geocoder/locations/onelineaddress` on the connection's
**Service address** and says how many matches came back. No key, no account:
the service is free and public (`auth.mode == "none"`).

HOW TO TEST IT BY HAND — the command the PO asked to be written down
-----------------------------------------------------------------------
From any machine that can reach the internet (this build sandbox cannot — its
egress proxy refuses the host)::

    curl -sS 'https://geocoding.geo.census.gov/geocoder/locations/onelineaddress?address=4600+Silver+Hill+Rd%2C+Washington%2C+DC+20233&benchmark=Public_AR_Current&format=json'

A working service answers JSON whose ``result.addressMatches[0].coordinates`` is
about ``{"x": -76.92744, "y": 38.845985}`` — ``x`` is LONGITUDE. An empty
``addressMatches`` list is still a working service (the address did not match).
Then, in the product: Settings → Integrations → **Census geocoder** → Connect
(Service address ``https://geocoding.geo.census.gov``) → **Test** with an
address of your own. And from the API host, the batch that fills empty
coordinates: ``python manage.py geocode_premises --tenant <web name>``.

⚠ **A `.example` SERVICE ADDRESS IS ANSWERED FROM A RECORDING** (RFC 2606: it
can never resolve, so nothing real is shadowed — `gis_fixtures`' rule). Tests
use it; a utility never should, which is why the manifest's default is now the
real address.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
from collections.abc import Callable, Mapping, Sequence
from decimal import Decimal, InvalidOperation
from typing import Any

from apps.integrations.adapters.base import (
    ITEM_FAILED,
    ITEM_SUCCEEDED,
    Adapter,
    ConnectionView,
    FieldErrors,
    ItemResult,
    RunResult,
    TestResult,
)
from apps.integrations.scrubbing import scrub
from core import gis_http

#: The one path, under whatever Service address the connection names.
ONELINE_PATH = "/geocoder/locations/onelineaddress"
#: The benchmark `apps/metering/geocode.py` already asks for — one answer shape.
BENCHMARK = "Public_AR_Current"
#: What a Test sends when nobody typed an address: the Census Bureau's own
#: documented sample, their headquarters (`apps/metering/geocode.py`'s record).
SAMPLE_ADDRESS = "4600 Silver Hill Rd, Washington, DC 20233"
TIMEOUT_S = 10.0

Transport = Callable[[str, float], Any]


def _urllib_transport(url: str, timeout_s: float) -> Any:
    """The live call — the only network touch in this file.

    `DEF-INT-10019` — through `core.gis_http.fetch_json`, the one function that
    sends `User-Agent: SMARTBillHub-GIS/<version> (support@bynry.io)`; a bare
    `urlopen` sent Python's default agent, which a CDN may refuse.
    """
    return gis_http.fetch_json(url, timeout_s)


def oneline_url(base_url: str, address: str) -> str:
    """The request a by-hand test makes, built ONCE so the docstring's command
    and the adapter cannot disagree."""
    base = str(base_url or "").strip().rstrip("/")
    query = urllib.parse.urlencode({"address": address, "benchmark": BENCHMARK, "format": "json"})
    return f"{base}{ONELINE_PATH}?{query}"


def matches_of(payload: Any) -> list[dict[str, Any]]:
    """`[{address, lat, lng}]` — `x` is LONGITUDE and is swapped exactly here."""
    found: list[dict[str, Any]] = []
    rows = ((payload or {}).get("result") or {}).get("addressMatches") or [] if isinstance(payload, Mapping) else []
    for row in rows:
        coordinates = (row or {}).get("coordinates") or {}
        try:
            lat = Decimal(str(coordinates["y"]))
            lng = Decimal(str(coordinates["x"]))
        except (KeyError, InvalidOperation, TypeError):
            continue
        found.append({"address": str(row.get("matchedAddress") or ""), "lat": lat, "lng": lng})
    return found


class CensusGeocoderAdapter(Adapter):
    """The US Census geocoder. Four methods and no fifth."""

    key = "geocoder_census"

    def __init__(self, transport: Transport | None = None) -> None:
        self._transport = transport

    def _send(self, url: str) -> Any:
        if self._transport is not None:
            return self._transport(url, TIMEOUT_S)
        from apps.integrations import census_fixtures

        recorded = census_fixtures.transport_for(url)
        return (recorded or _urllib_transport)(url, TIMEOUT_S)

    def validate(self, config: Mapping[str, Any]) -> FieldErrors:
        """Nothing beyond the manifest's own `url` check — the honest answer."""
        return []

    def test(
        self,
        conn: ConnectionView,
        secrets: Mapping[str, str],
        *,
        recipient: str | None = None,
    ) -> TestResult:
        """`BR-INT-019` — one real lookup of the typed address (or the sample)."""
        address = (recipient or "").strip() or SAMPLE_ADDRESS
        url = oneline_url(dict(conn.config or {}).get("base_url") or "", address)
        started = time.monotonic()
        try:
            payload = self._send(url)
        except urllib.error.HTTPError as exc:
            # B14 rule 33 — a fact, six words at most; their words underneath.
            #
            # ⚠ `DEF-INT-10019` — a `403` whose body is not the service's own
            # JSON came from a firewall or CDN in front of it, and says so; the
            # status and the first 200 characters of the body go to the run row.
            body = gis_http.error_body(exc)
            blocked = exc.code == 403 and not gis_http.is_json_object(body)
            return TestResult(
                ok=False,
                sentence=(
                    "The geocoder's firewall blocked us."
                    if blocked
                    else "The geocoder refused the lookup."
                ),
                provider_text=scrub(gis_http.evidence(exc.code, body)),
            )
        except (urllib.error.URLError, OSError, ValueError) as exc:
            return TestResult(
                ok=False,
                sentence="The geocoder is not answering.",
                provider_text=scrub(str(exc)),
            )
        if not isinstance(payload, Mapping) or "result" not in payload:
            return TestResult(
                ok=False,
                sentence="The geocoder sent an unreadable answer.",
                provider_text=scrub(json.dumps(payload)[:300] if payload is not None else ""),
            )
        found = matches_of(payload)
        elapsed = int((time.monotonic() - started) * 1000)
        return TestResult(
            ok=True,
            # Six words. A zero is still a working service — it answered.
            sentence=f"The geocoder answered: {len(found)} matches.",
            provider_text=f"{elapsed} ms",
        )

    def execute(
        self,
        conn: ConnectionView,
        secrets: Mapping[str, str],
        work: Sequence[Mapping[str, Any]],
    ) -> RunResult:
        """One lookup per address, per-item outcomes, never a boolean."""
        items: list[ItemResult] = []
        base = dict(conn.config or {}).get("base_url") or ""
        for one in work:
            address = str(one.get("address") or "").strip()
            ref = str(one.get("ref") or address)
            if not address:
                items.append(ItemResult(ref=ref, outcome=ITEM_FAILED, detail="no address"))
                continue
            try:
                found = matches_of(self._send(oneline_url(base, address)))
            except Exception as exc:  # noqa: BLE001 — their refusal, per item
                items.append(
                    ItemResult(ref=ref, outcome=ITEM_FAILED, detail=address, provider_text=scrub(str(exc)))
                )
                continue
            items.append(
                ItemResult(
                    ref=ref,
                    outcome=ITEM_SUCCEEDED if found else ITEM_FAILED,
                    detail=address if found else f"{address} · no match",
                )
            )
        return RunResult(items=tuple(items), confirmed=True)

    def describe(self, conn: ConnectionView) -> str:
        base = str(dict(conn.config or {}).get("base_url") or "").strip()
        return f"{base} · Census geocoder" if base else "Census geocoder"


# ── Lifecycle ─────────────────────────────────────────────
# packet: PO GIS review 2026-10-07 gap 13 (Lane D) — the adapter the manifest was missing
# generated: 2026-10-07 by GIS Lane D
# checklist: A✔ B=n/a(the card is the existing connector screen) C✔ D✔ E=n/a F✔ G✔ H=n/a
# gates: pytest tests/test_gis_lane_d_census_and_city_state.py (recorded `.example` host; no test touches the network) · the conformance kit runs this class unchanged
# exceptions: the live call was NOT made from this sandbox (egress proxy) — the by-hand command above is the record of how to make it
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
