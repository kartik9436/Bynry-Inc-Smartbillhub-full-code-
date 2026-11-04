# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-CUS-10050 — Move-in step 1, *Services and meters*: a *Fetch
#           reading* icon on each metered row. PO ruling 2026-10-11, verbatim:
#           *"this si correct 0 fix it"*. DEF-CUS-10051 (Move-out step 2) is
#           the next caller, and is why `as_of` exists today.
# Rules:    hard rule 3 (a reading always travels with its unit) · hard-won
#           law 1 (never a reading we did not receive) · B2 §2 (integrations
#           owns connections; this reads its OWN table and writes nothing) ·
#           B14 rule 33 (each sentence ≤ 6 words)
# Tests:    06-backend/tests/test_def_cus_10050_fetch_meter_reading.py
# Impacts:  apps/integrations/api.py (one route) · 07-frontend
#           features/metering/FetchMeterReading.tsx (the one caller today)
# ───────────────────────────────────────────────────────
"""One meter's reading, asked of the utility's meter head-end, right now.

WHAT IT ANSWERS
---------------
`fetch(tenant_id, meter_no=…, as_of=…)` → `{result, reading, message_key}`,
the shape `gis.check_address` already gives the premises form, so the two
"ask the connector one question while a clerk waits" doors read alike:

* **`not_connected`** — no meter head-end (a connector in the `meters`
  category) is connected here: no row, or one switched off, disabled or never
  set up. Nothing is dialled.
* **`fetched`** — `reading` is `{meter_no, value, unit, read_on}`. `value` is a
  decimal STRING (never a float), `unit` is the head-end's own and is always
  present (hard rule 3), `read_on` is `YYYY-MM-DD`.
* **`no_reading`** — the head-end answered and holds nothing for this meter
  (on or before `as_of`, when one is given).
* **`unavailable`** — a head-end is connected and could not answer: its last
  test failed, no live client is bound on this deployment, it raised, or it
  answered a reading with no unit. ⚠ The no-client case carries its own key,
  `connected_no_read`, with `params.provider` — *"Neptune 360 connected. No
  reading fetched."* (PO 2026-10-11) — because *"Provider could not give a
  reading."* read as the provider failing when the product cannot ask it.

⚠ **NO LIVE CLIENT IS BOUND ON THIS DEPLOYMENT, AND THIS FILE SAYS SO RATHER
THAN PRETENDING** — the same posture as `adapters/meters_neptune360.py`'s
`HEAD_END_CLIENT`. `READING_CLIENTS` maps a provider key to an object with one
method, `latest(connection, *, meter_no, as_of)`, and it is EMPTY here. So a
utility with a connected head-end is told `unavailable`, truthfully, until a
client is bound; a test binds a stub. It is a separate seam from the adapter
because the adapter protocol is four public methods and the conformance kit
refuses a fifth; a one-meter question is not one of the four.

⚠ **`as_of` IS ENFORCED HERE AS WELL AS PASSED ON.** A move-out asks for the
reading on or last before the move-out date. A client that answers with a
later reading has not answered that question, so it is `no_reading` rather
than a figure the clerk would record against the wrong day.

**It writes nothing** — no read, no run row, no audit row. What a reading
MEANS is metering's: the value goes into a box the clerk can still overwrite,
and only the wizard's own commit records it.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Protocol

from apps.integrations import models
from apps.integrations.registry import REGISTRY, Registry
from core import errors

#: The manifest category every meter head-end declares (Neptune, Sensus,
#: Badger, Itron) — read from the registry, never a list typed here.
METERS_CATEGORY = "meters"

RESULT_FETCHED = "fetched"
RESULT_NOT_CONNECTED = "not_connected"
RESULT_NO_READING = "no_reading"
RESULT_UNAVAILABLE = "unavailable"

#: In all eleven catalogues (≤ 6 words each, B14 rule 33).
KEY_NOT_CONNECTED = "integrations.meterReading.not_connected"
KEY_NO_READING = "integrations.meterReading.no_reading"
KEY_UNAVAILABLE = "integrations.meterReading.unavailable"
#: PO 2026-10-11 (decision log, *"neptupe is connected, but no reading
#: fetched"*): a head-end switched on with no reading client bound on this
#: deployment is NAMED, so the clerk does not read it as the provider failing.
KEY_CONNECTED_NO_READ = "integrations.meterReading.connected_no_read"
KEY_METER_REQUIRED = "integrations.meterReading.meter_required"
KEY_BAD_DATE = "integrations.meterReading.bad_date"


class MeterReadingClient(Protocol):
    """What this door needs of a head-end, and the whole of it.

    `latest` returns `{"value", "unit", "read_on"}` for the newest reading on
    or before `as_of` (newest of all when `as_of` is None), or `None` when the
    head-end holds none. It may raise; a raise is `unavailable`.
    """

    def latest(
        self,
        connection: models.IntegrationConnection,
        *,
        meter_no: str,
        as_of: date | None,
    ) -> Mapping[str, Any] | None: ...


#: The seam — EMPTY on this deployment (see the module docstring).
READING_CLIENTS: dict[str, MeterReadingClient] = {}


def _answer(
    result: str,
    message_key: str | None,
    reading: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    answer: dict[str, Any] = {"result": result, "reading": reading, "message_key": message_key}
    if params:
        # Only a sentence with values carries them; every other answer keeps
        # the three-key shape callers already compare against.
        answer["params"] = params
    return answer


def _is_connected(row: models.IntegrationConnection) -> bool:
    return bool(row.enabled) and row.status not in (models.STATUS_OFF, models.STATUS_NOT_SET_UP)


def head_end_for(
    tenant_id: Any, registry: Registry = REGISTRY
) -> models.IntegrationConnection | None:
    """The connected meter head-end: production first, then by provider key
    so two connected head-ends answer the same way every time."""
    keys = [one.key for one in registry.all() if one.category == METERS_CATEGORY]
    rows = [
        row
        for row in models.IntegrationConnection.objects.filter(
            tenant_id=tenant_id, provider_key__in=keys
        )
        if _is_connected(row)
    ]
    rows.sort(
        key=lambda row: (
            0 if row.environment == models.ENVIRONMENT_PRODUCTION else 1,
            row.provider_key,
        )
    )
    return rows[0] if rows else None


def parse_as_of(raw: Any) -> date | None:
    """`YYYY-MM-DD` or absent; anything else is refused in words."""
    if raw is None or str(raw).strip() == "":
        return None
    try:
        return date.fromisoformat(str(raw).strip())
    except ValueError as exc:
        raise errors.ValidationError(errors.VAL_FORMAT, message_key=KEY_BAD_DATE) from exc


def _reading_date(raw: Any) -> date | None:
    if isinstance(raw, date):
        return raw
    try:
        return date.fromisoformat(str(raw or "")[:10])
    except ValueError:
        return None


def fetch(
    tenant_id: Any,
    *,
    meter_no: Any,
    as_of: date | None = None,
    registry: Registry = REGISTRY,
) -> dict[str, Any]:
    """See the module docstring for the four results. Nothing is written."""
    number = str(meter_no or "").strip()
    if not number:
        raise errors.ValidationError(errors.VAL_REQUIRED, message_key=KEY_METER_REQUIRED)
    row = head_end_for(tenant_id, registry)
    if row is None:
        return _answer(RESULT_NOT_CONNECTED, KEY_NOT_CONNECTED)
    if row.status == models.STATUS_NOT_WORKING:
        return _answer(RESULT_UNAVAILABLE, KEY_UNAVAILABLE)
    client = READING_CLIENTS.get(row.provider_key)
    if client is None:
        manifest = registry.get(row.provider_key)
        provider = manifest.display_name if manifest is not None else row.provider_key
        return _answer(RESULT_UNAVAILABLE, KEY_CONNECTED_NO_READ, params={"provider": provider})
    try:
        got = client.latest(row, meter_no=number, as_of=as_of)
    except Exception:  # noqa: BLE001 — a head-end's failure is this door's answer
        return _answer(RESULT_UNAVAILABLE, KEY_UNAVAILABLE)
    if got is None or got.get("value") in (None, ""):
        return _answer(RESULT_NO_READING, KEY_NO_READING)
    try:
        value = Decimal(str(got.get("value")))
    except InvalidOperation:
        return _answer(RESULT_UNAVAILABLE, KEY_UNAVAILABLE)
    unit = str(got.get("unit") or "").strip()
    read_on = _reading_date(got.get("read_on"))
    if not unit or read_on is None or not value.is_finite():
        # Hard rule 3: a reading with no unit is not a reading we may show.
        return _answer(RESULT_UNAVAILABLE, KEY_UNAVAILABLE)
    if as_of is not None and read_on > as_of:
        return _answer(RESULT_NO_READING, KEY_NO_READING)
    return _answer(
        RESULT_FETCHED,
        None,
        {"meter_no": number, "value": str(value), "unit": unit, "read_on": read_on.isoformat()},
    )


__all__ = [
    "KEY_BAD_DATE",
    "KEY_CONNECTED_NO_READ",
    "KEY_METER_REQUIRED",
    "KEY_NOT_CONNECTED",
    "KEY_NO_READING",
    "KEY_UNAVAILABLE",
    "READING_CLIENTS",
    "RESULT_FETCHED",
    "RESULT_NOT_CONNECTED",
    "RESULT_NO_READING",
    "RESULT_UNAVAILABLE",
    "MeterReadingClient",
    "fetch",
    "head_end_for",
    "parse_as_of",
]
