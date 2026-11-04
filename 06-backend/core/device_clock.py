# ── Trace ──────────────────────────────────────────────
# Change:   FB-014 · DEF-FLD-10639 — a phone whose clock disagrees with the
#           server is never refused; every time it sends is shifted onto the
#           server's clock (PO 2026-10-28, decision log of that date).
# Rules:    BR-TEN-043 (an event date, never a wall clock) · BR-WRK-003 (the
#           close dates the meter read) · BR-WRK-020 (labour priced from
#           finished − arrived) · hard rules 1, 7
# Tests:    06-backend/tests/test_def_fld_10639_device_clock.py
# Impacts:  core/field_app_version.py (measures it on every field route) ·
#           apps/work/field_labour.py · apps/work/mobile.py · apps/work/sync.py ·
#           apps/work/field_raise.py · apps/work/shifts.py ·
#           apps/metering/field_reads.py
# HUMAN-REVIEW-PENDING — times that price labour and date meter reads; the
# rule and its worked figure were shown to the PO (ledger row 2026-10-28).
# ───────────────────────────────────────────────────────
"""The phone's clock, measured once per request, and the ONE helper that moves
a phone-clock time onto the server's clock.

THE RULE (PO 2026-10-28, verbatim: *"job should be synced with the server
accept the future time"*)
-------------------------------------------------------------------------
Every field-app call carries the phone's own clock reading at the moment it was
sent, `X-Device-Time` (ISO-8601 with its zone). `FieldAppVersionMiddleware`
reads it on every field route and computes, ONCE for the request,

    offset = server now − phone now

and every service that stores a time the phone stamped calls `correct()`,
which returns `time + offset`. Worked (the figure the PO was shown): phone
12:07:30, server 12:02:30 → offset −5 min; a job finished at 12:07 on the
phone is stored as 12:02. **No clock difference of any size, in either
direction, is ever a refusal.** Labour minutes do not move: arrival and finish
shift by the same offset.

THE LIMITATION, STATED (decision log 2026-10-28, judgment 1)
------------------------------------------------------------
The offset is measured at SEND time, so work captured offline days earlier is
corrected exactly only while the phone's clock was not changed between capture
and send. If the technician fixed the clock before syncing, the old work moves
by the NEW offset and is wrong by the size of that fix — nothing here can see
it. A shifted time still later than the server's now (possible only that way)
is CLAMPED to now, never refused.

WHAT IS NOT SHIFTED
-------------------
* **|offset| ≤ 2 s** is network delay, not a wrong clock (`DEAD_BAND_S`).
  Shifting by it would make a replayed labour item differ from the stored one
  by a fraction of a second and read as a CORRECTION. Offsets are whole seconds.
* **No reading at all** (an older build, curl, the web): there is nothing to
  measure. A time up to `NO_READING_TOLERANCE` (5 min) ahead of the server is
  clamped to now; further ahead is returned unchanged and the caller keeps its
  own refusal — without a reading a fast clock and garbage look the same.

WHERE THE ORIGINAL IS KEPT
--------------------------
`audit_fields()` is `{device_time, clock_offset_s}`; the labour audit row and
the sync's audit row carry it, and the close keeps it on the order's field data
(`device_clock`) — which is also what the office reads to say *"Phone clock was
N min fast"*. The original time is `stored − clock_offset_s` (before a clamp).
"""

from __future__ import annotations

import contextvars
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Iterator

from django.utils import timezone
from django.utils.dateparse import parse_datetime

DEVICE_TIME_HEADER = "X-Device-Time"
SERVER_TIME_HEADER = "X-Server-Time"

#: An offset this small is the network, not the clock.
DEAD_BAND_S = 2
#: The phone warns, and the office says so, beyond this (PO 2026-10-28).
WARN_AFTER_S = 5 * 60
#: With no reading, a time this far ahead is clamped to now rather than refused.
NO_READING_TOLERANCE = timedelta(minutes=5)


@dataclass(frozen=True)
class Reading:
    """One request's measurement: what the phone said and what we said."""

    device_time: datetime
    server_time: datetime
    offset_s: int

    @property
    def offset(self) -> timedelta:
        return timedelta(seconds=self.offset_s)


_current: contextvars.ContextVar[Reading | None] = contextvars.ContextVar("device_clock", default=None)


def measure(raw: Any, server_now: datetime | None = None) -> Reading | None:
    """`X-Device-Time` → a `Reading`, or None when absent or unreadable.

    A time with no zone is a time on an unknown clock and is not a reading.
    """
    if isinstance(raw, datetime):
        device = raw
    else:
        text = str(raw or "").strip()
        if not text:
            return None
        try:
            device = parse_datetime(text.replace(" ", "T"))
        except (TypeError, ValueError):
            return None
    if device is None or device.tzinfo is None:
        return None
    server = server_now or timezone.now()
    offset_s = int(round((server - device).total_seconds()))
    if abs(offset_s) <= DEAD_BAND_S:
        offset_s = 0
    return Reading(device_time=device, server_time=server, offset_s=offset_s)


@contextmanager
def measured(raw: Any, server_now: datetime | None = None) -> Iterator[Reading | None]:
    """Hold one request's reading for everything that runs inside it."""
    reading = measure(raw, server_now)
    token = _current.set(reading)
    try:
        yield reading
    finally:
        _current.reset(token)


def current() -> Reading | None:
    return _current.get()


def correct(moment: datetime | None) -> datetime | None:
    """A time the phone stamped, on the SERVER's clock. See the module header."""
    if moment is None:
        return None
    now = timezone.now()
    reading = current()
    if reading is not None:
        shifted = moment + reading.offset
        return now if shifted > now else shifted
    if now < moment <= now + NO_READING_TOLERANCE:
        return now
    return moment


def audit_fields() -> dict[str, Any]:
    """What an audit row keeps so the phone's own time can be recovered."""
    reading = current()
    if reading is None:
        return {}
    return {"device_time": reading.device_time.isoformat(), "clock_offset_s": reading.offset_s}


def server_time_header() -> str:
    return timezone.now().isoformat()
