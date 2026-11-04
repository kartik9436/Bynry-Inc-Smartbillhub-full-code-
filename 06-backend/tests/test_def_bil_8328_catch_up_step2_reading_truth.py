"""DEF-BIL-8328 — a catch-up's step 2 says what each period is PRICED on.

PO walk-through on 2.412.4 (screenshots `08-qa/screens/one-time-bill-po-walk-
2.412.4/6a-catch-up-waiting.png` and `6b-catch-up-estimated.png`):

  (a) with every meter still WAITING (nothing typed), the Periods panel marked
      all four periods *Actual*;
  (b) where July is split at a Jul 16 price change and the July read is shared
      by days (`DEF-BIL-8324`), the Readings table showed the WHOLE read on the
      Jul 16–31 row as *Actual 700 kWh*, while the price used 338.7 + 361.3.

Both statuses were read from the raw reading of each window; the priced
segment (the group's own data after the share and the estimate) was never
consulted. Now each period and each reading row is derived from the group the
bill is priced on: waiting, estimated or actual — and the usage shown is the
share the row is priced on.

Written RED FIRST (hard-won law 7). Pure functions: the back-bill fixture plan
cannot price on this branch (`DEF-BIL-8326`), so the groups are built by hand
in the shape `backbill.BackBillGroup` carries.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from apps.billing import one_time, one_time_answer, rating_seam
from apps.billing.contracts import ServiceReading

JUL_1, JUL_15, JUL_16, JUL_31 = date(2026, 7, 1), date(2026, 7, 15), date(2026, 7, 16), date(2026, 7, 31)


def _read(amount, *, estimated=False):
    return ServiceReading(
        service_code="electric",
        consumption=None if amount is None else rating_seam.Quantity(Decimal(amount), "kWh"),
        estimated=estimated,
        absent_reason=None if amount is not None else "no_read",
    )


def _group(start, end, reading):
    return SimpleNamespace(
        period_start=start,
        period_end=end,
        service_date=start,
        cycle_days=31,
        days=(end - start).days + 1,
        tariff_version_ids={"electric": "v-1"},
        data=SimpleNamespace(readings=(reading,), unconnected_services=()),
        label=lambda: f"{start}..{end}",
    )


def _prepared(groups):
    return SimpleNamespace(
        account_no="A-1",
        reason_code="MISSED",
        theft=False,
        cap_months=12,
        approval_mode="none",
        estimate_source="history",
        groups=groups,
        estimates=(),
    )


def test_def_bil_8328_a__a_period_whose_meter_still_waits_says_waiting_not_actual():
    body = one_time._sub_period_body(
        _prepared([_group(JUL_1, JUL_15, _read(None)), _group(JUL_16, JUL_31, _read(None))]),
        kind=one_time.KIND_BACKBILL,
    )
    periods = one_time_answer._periods(body, {}, one_time.KIND_BACKBILL)
    assert [p["reading"] for p in periods] == ["waiting", "waiting"]


def test_def_bil_8328_b__a_shared_read_shows_each_rows_share_and_its_status():
    body = one_time._sub_period_body(
        _prepared(
            [
                _group(JUL_1, JUL_15, _read("338.7", estimated=True)),
                _group(JUL_16, JUL_31, _read("361.3", estimated=True)),
            ]
        ),
        kind=one_time.KIND_BACKBILL,
    )
    periods = one_time_answer._periods(body, {}, one_time.KIND_BACKBILL)
    assert [p["reading"] for p in periods] == ["estimated", "estimated"]
    # The Jul 16–31 row: metering's raw position is the whole July read.
    position = {
        "asset_id": "e1",
        "service": "electric",
        "label": "E-55120",
        "unit": "kWh",
        "previous": {"value": "1000", "read_at": "2026-06-30"},
        "current": {"value": "1700", "read_at": "2026-07-31", "estimated": False},
        "consumption": "700",
    }
    row = one_time_answer._reading_row(
        position,
        kind=one_time.KIND_BACKBILL,
        window_end=JUL_31,
        typed={},
        period_index=1,
        estimated_services=set(),
        priced=one_time_answer._priced_read(body["groups"][1], position),
    )
    assert row["status"] == "estimated"
    assert Decimal(row["usage"]) == Decimal("361.3")


def test_def_bil_8328_c__a_whole_read_in_one_period_stays_actual():
    body = one_time._sub_period_body(
        _prepared([_group(JUL_1, JUL_31, _read("700"))]), kind=one_time.KIND_BACKBILL
    )
    assert [p["reading"] for p in one_time_answer._periods(body, {}, one_time.KIND_BACKBILL)] == [
        "actual"
    ]
    position = {
        "asset_id": "e1",
        "service": "electric",
        "label": "E-55120",
        "unit": "kWh",
        "previous": None,
        "current": None,
        "consumption": None,
    }
    row = one_time_answer._reading_row(
        position,
        kind=one_time.KIND_BACKBILL,
        window_end=JUL_31,
        typed={},
        period_index=0,
        estimated_services=set(),
        priced=one_time_answer._priced_read(body["groups"][0], position),
    )
    assert row["status"] == "actual" and Decimal(row["usage"]) == Decimal("700")
