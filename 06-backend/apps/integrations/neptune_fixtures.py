# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-028 · US-INT-031 · US-INT-035 (CR-069 wave K) —
#           "recorded Neptune-shaped fixtures, no network"
# Rules:    BR-INT-019 (`test()` is the smallest real instance) · BR-INT-003
#           (a secret never leaves this module in the clear) · BR-INT-046
#           (a run is not finished until the file is collected)
# Tests:    06-backend/tests/test_us_int_028_token_walk.py ·
#           06-backend/tests/test_us_int_031_submit_poll_collect.py ·
#           06-backend/tests/test_us_int_035_safety_parameters.py
# Impacts:  apps/integrations/adapters/meters_neptune360.py (`HEAD_END_CLIENT`
#           is the seam these bind to) ·
#           10-scripts/render-checks/cr069-k-building-the-file.mjs
# ───────────────────────────────────────────────────────
"""Recorded head-end answers, so no test ever dials a water meter cloud.

WHY A FILE AND NOT A `mock.patch`
----------------------------------
The same argument `oauth_fixtures.py` already makes for wave H: the adapter
takes its transport from a module SEAM that a test binds and unbinds, so a test
that patched a name instead would keep passing on the day somebody renamed it —
and the path it covers carries a real utility's head-end credential.

WHAT THESE ARE
--------------
The shapes below are reduced to the keys the adapter actually reads. They are
recordings in the sense that matters — the field names and their types are the
provider's, not ours — and they are deliberately NOT real tokens: `RECORDED`
in the value makes it impossible to mistake one for a leaked secret in a grep.

⚠ **THREE EXPORT FIXTURES, AND THE ASYMMETRY IS THE WHOLE POINT** (`US-INT-031`
§4). `v1` answers *building* four times and then hands back a **link**; `v2`
answers *building* four times and then hands back a **handle**; `never_ready`
answers *building* for ever. One runner serves all three, because
`result_delivery` is a declared value and not a branch — a single fixture would
have covered one path and left the other two to the first real utility.

⚠ **AND THE WINDOW-REFUSAL FIXTURE IS THE ONE PEOPLE FORGET** (`US-INT-028`
TC-4). A manifest that asks for a thirty-day window against a provider capped
at seven is refused BY THE PROVIDER, naming the parameter — we do not narrow it
quietly on our side, because a silent narrowing means the walk we recorded is
not the walk we made.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

# ⚠ Synthetic by construction. The word RECORDED in every value makes a fixture
# impossible to mistake for a live credential in a log, a grep or a screenshot.
RECORDED_TOKEN = "RECORDED-NEPTUNE-BEARER-NOT-A-REAL-TOKEN"
RECORDED_SITE_ID = "BRAZOS-01"
RECORDED_API_KEY = "RECORDED-N360-PAIR-NOT-A-REAL-KEY"
#: What the credential's masked hint reads as on the card (`••••N360`).
RECORDED_HINT_TAIL = "N360"

#: Their token endpoint's answer. `expires_in` is THEIR number and the manifest
#: repeats it as `ttl_seconds`; if the two ever disagree, the manifest is wrong
#: and the walk fails at minute eleven.
TOKEN_RESPONSE: dict[str, Any] = {
    "token_type": "Bearer",
    "expires_in": 600,
    "access_token": RECORDED_TOKEN,
}

#: One meter's last reading — what `test()` asks for (`BR-INT-019`: the
#: SMALLEST REAL instance, never *does the API key parse*).
ONE_READING_RESPONSE: dict[str, Any] = {
    "readings": [
        {
            "meterId": "MTR-2210",
            "readAt": "2026-09-05T06:02:00Z",
            "value": "184.0000",
            "unitOfMeasure": "GAL",
            "actualConsumption": True,
        }
    ],
    "page": 1,
    "pageSize": 1,
    "hasMore": False,
}

#: Their refusal when a manifest asks for a window wider than they allow. ⚠ It
#: NAMES THE PARAMETER, which is what `US-INT-028` TC-4 asserts we record.
WINDOW_TOO_WIDE_RESPONSE: dict[str, Any] = {
    "error": "windowDays exceeds the maximum of 7",
    "parameter": "windowDays",
}

#: The vendor's four *not yet* answers before the file exists.
BUILDING_RESPONSE: dict[str, Any] = {"status": "building"}
#: v1 — a URL. v2 — an identifier we go and collect by.
READY_LINK_RESPONSE: dict[str, Any] = {
    "status": "ready",
    "downloadUrl": "https://api.neptune360.example/exports/RECORDED-EXPORT-0042.csv",
}
READY_HANDLE_RESPONSE: dict[str, Any] = {"status": "ready", "exportId": "EXP-RECORDED-0042"}
#: What collecting by handle hands back.
COLLECTED_BY_HANDLE_RESPONSE: dict[str, Any] = {
    "artifactUrl": "https://api.neptune360.example/artifacts/EXP-RECORDED-0042",
    "records": 1240,
}

#: How many *building* answers each export fixture gives before it is ready.
BUILDS_FOR = 4


def readings_page(*, page: int, page_size: int, records: int) -> dict[str, Any]:
    """One page of readings, in their shape.

    `records` is how many rows this page holds — never `page_size` by
    construction, because the LAST page of a window is short and a fixture that
    always returned a full page would let a runner that ignores `hasMore` pass.
    """
    return {
        "readings": [
            {
                "meterId": f"MTR-{2000 + index}",
                "readAt": "2026-09-05T06:02:00Z",
                "value": "184.0000",
                "unitOfMeasure": "GAL",
                "actualConsumption": True,
            }
            for index in range(records)
        ],
        "page": page,
        "pageSize": page_size,
        "hasMore": records >= page_size,
    }


class RecordedHeadEnd:
    """A head-end that answers from the recordings above and dials nothing.

    Bound to `adapters.meters_neptune360.HEAD_END_CLIENT` by a test, and
    unbound after it. It keeps three things a test asserts on:

      * `calls` — every request made, in order, with its parameters. This is
        how `US-INT-028` TC-2 asserts *the runner requested exactly 5,000 ·
        150 · 100* rather than asserting that a constant exists somewhere.
      * `mints` — how many times the token endpoint was asked. TC-1's **≥ 11**.
      * `bearer_seen` — every Authorization header presented, so TC-6 can prove
        one tenant never presents another's token.

    ⚠ **IT REFUSES A CALL WITH NO BEARER, WHICH IS WHAT MAKES THE MINT COUNT
    MEAN ANYTHING.** A recorded client that answered happily without one would
    let a runner that never minted at all pass every test in this wave — law 7's
    *incapable of failing* shape, in the one place it would be least visible.
    """

    def __init__(
        self,
        *,
        export_fixture: str = "v1_link",
        window_cap_days: int = 7,
        records_per_page: Sequence[int] | None = None,
    ) -> None:
        self.export_fixture = export_fixture
        self.window_cap_days = window_cap_days
        #: Per call to a readings page, how many rows come back. Cycled.
        self.records_per_page = tuple(records_per_page or (12,))
        self.calls: list[dict[str, Any]] = []
        self.mints = 0
        self.bearer_seen: list[str] = []
        self._polls = 0

    # ── the transport seam's one method ────────────────────────────────────
    def call(
        self,
        *,
        method: str,
        url: str,
        headers: Mapping[str, str] | None = None,
        payload: Mapping[str, Any] | None = None,
        timeout_s: int = 30,
    ) -> dict[str, Any]:
        headers = dict(headers or {})
        payload = dict(payload or {})
        self.calls.append({"method": method, "url": url, "payload": payload})
        if url.endswith("/oauth/token"):
            self.mints += 1
            return dict(TOKEN_RESPONSE)
        bearer = headers.get("Authorization", "")
        self.bearer_seen.append(bearer)
        if not bearer.startswith("Bearer "):
            # ⚠ See the class docstring: without this, a runner that never
            # minted would pass every case in the wave.
            return {"error": "missing bearer token", "parameter": "Authorization"}
        if "/exports" in url:
            return self._export_answer(method, payload)
        window_days = int(payload.get("windowDays") or 0)
        if window_days > self.window_cap_days:
            return dict(WINDOW_TOO_WIDE_RESPONSE)
        page = int(payload.get("page") or 1)
        page_size = int(payload.get("pageSize") or 1)
        if page_size == 1:
            return dict(ONE_READING_RESPONSE)
        records = self.records_per_page[(page - 1) % len(self.records_per_page)]
        return readings_page(page=page, page_size=page_size, records=records)

    def _export_answer(self, method: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        # ⚠ A COLLECT IS NOT ANOTHER POLL, and a fixture that could not tell
        # them apart would make the `handle` path untestable: the second call
        # would answer *ready* for ever and no artifact would ever arrive.
        if payload.get("collect"):
            return dict(COLLECTED_BY_HANDLE_RESPONSE)
        # ⚠ NEITHER IS THE SUBMIT, and getting this wrong shifts every figure
        # the screen shows by one. `BUILDS_FOR = 4` means *they answered
        # **building** to four ASKS*, so S142 reads *asked them 4 times* and the
        # fifth ask is the one that is ready. Counting the POST that started the
        # job as an ask would make the sentence say three.
        if method.upper() == "POST":
            return dict(BUILDING_RESPONSE)
        self._polls += 1
        if self.export_fixture == "never_ready":
            return dict(BUILDING_RESPONSE)
        if self._polls <= BUILDS_FOR:
            return dict(BUILDING_RESPONSE)
        if self.export_fixture == "v2_handle":
            return dict(READY_HANDLE_RESPONSE)
        return dict(READY_LINK_RESPONSE)


def recorded_config() -> dict[str, Any]:
    """The non-secret half of a Brazos Bend Neptune connection."""
    return {"site_id": RECORDED_SITE_ID}


def recorded_secrets() -> dict[str, str]:
    """The long-lived pair. `••••N360` is what the card shows for it."""
    return {"api_key": RECORDED_API_KEY}


__all__ = [
    "BUILDING_RESPONSE",
    "BUILDS_FOR",
    "COLLECTED_BY_HANDLE_RESPONSE",
    "ONE_READING_RESPONSE",
    "READY_HANDLE_RESPONSE",
    "READY_LINK_RESPONSE",
    "RECORDED_API_KEY",
    "RECORDED_HINT_TAIL",
    "RECORDED_SITE_ID",
    "RECORDED_TOKEN",
    "RecordedHeadEnd",
    "TOKEN_RESPONSE",
    "WINDOW_TOO_WIDE_RESPONSE",
    "readings_page",
    "recorded_config",
    "recorded_secrets",
]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-INT-028 · 031 · 035 (EP-INT-07/08/09) + BR-INT-046/047/050
# generated: 2026-09-06 by the CR-069 wave K build lane
# checklist: A✔ B=n/a(fixtures) C✔ D=n/a E=n/a F✔ G✔ H=n/a
# gates: pytest tests/test_us_int_028_token_walk.py tests/test_us_int_031_submit_poll_collect.py tests/test_us_int_035_safety_parameters.py
# exceptions: none — every value here is synthetic and says so in its own text
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
