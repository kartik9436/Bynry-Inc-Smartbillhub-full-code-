"""DEF-MET-9236 — a quote with no posting date is dated on the UTILITY's day.

Found by the New Connection end-to-end web walk (2026-10-02): `CON-26-0144` was
created at 19:48 in Chicago on 2 October with no posting date typed, and its
quote bill `BL-2610-000122` was dated **3 October** — the UTC date. An Add fee
for the real 3 October was then refused as a second fee on the same day.

⚠ WHAT WOULD MAKE THIS PASS WRONGLY: a clock that agrees in both zones. The
instant is 00:48 UTC on 3 October, which is 19:48 on 2 October in Chicago, so
the UTC answer and the utility's answer differ by a whole day.
"""

from __future__ import annotations

from datetime import date, datetime, timezone as dt_timezone
from zoneinfo import ZoneInfo

from django.utils import timezone

from apps.metering import connections as w6
from apps.tenancy import selectors as tenancy_selectors

EVENING_IN_CHICAGO = datetime(2026, 10, 3, 0, 48, tzinfo=dt_timezone.utc)


def test_no_posting_date_means_the_utilitys_today(monkeypatch):
    monkeypatch.setattr(timezone, "now", lambda: EVENING_IN_CHICAGO)
    monkeypatch.setattr(tenancy_selectors, "tenant_timezone", lambda: ZoneInfo("America/Chicago"))
    assert w6._quote_posting_date({}) == date(2026, 10, 2)
    assert w6._quote_posting_date({"quote_posting_date": ""}) == date(2026, 10, 2)


def test_a_typed_posting_date_is_kept(monkeypatch):
    monkeypatch.setattr(timezone, "now", lambda: EVENING_IN_CHICAGO)
    monkeypatch.setattr(tenancy_selectors, "tenant_timezone", lambda: ZoneInfo("America/Chicago"))
    assert w6._quote_posting_date({"quote_posting_date": "2026-09-30"}) == date(2026, 9, 30)
