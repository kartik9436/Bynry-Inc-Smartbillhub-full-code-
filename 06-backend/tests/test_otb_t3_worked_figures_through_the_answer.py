"""T3 — the 2026-09-30 worked figures, through the one-time bill's ANSWER.

Build plan T3; EP-BIL-03's `OTB` fixture figures. The engine half of each
figure is `tests/test_br_bil_300_services_rulings_2026_09_30.py`'s (the per-meter
lane, B1/B5/B6): it proves `runs.price_account` charges them. This file proves
the other half — that what the redrawn screen RECEIVES says the same thing —
by pushing the engine's own priced pass for each world through
`one_time_answer`'s composers, exactly as `POST /billing/one-time/preview` does:

  * **`$58.40`** — two water meters, 6.1 kgal each, tiers $3.25 to 5 kgal then
    $4.50, base $8.00 each: two meter-labelled line sets, two rate rows at
    `29.2000` each, and a bill total of `58.4000` (PO 2026-09-30, *"both meter
    should be build in metered case also - as a speearte line"*).
  * **`$36.00`** — two trash carts at $15.00 with a $3.00 base each: one service
    row counting TWO, a bill total of `36.0000` (PO 2026-09-30, option B).
  * **Sewer 40%, no service point** — sewer follows water: its row is
    `follows_basis` with water as the basis and NO asset, and its one line is a
    `percent` line of `24.4000` (40% × 12.2 kgal at $5.00, `BR-RAT-1015`).

These are the tenant's fixture VALUES, not signed law — no ❄️ B4/B5 figure is
touched, so `G64`'s engine-verified record does not move.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from apps.billing import one_time, one_time_answer, runs
from apps.billing.contracts import ServiceReading
from tests.test_br_bil_300_services_rulings_2026_09_30 import (  # noqa: F401
    PERIOD_END,
    PERIOD_START,
    _gather,
    _install,
    _rolled_back_resolution_chain,
    _water,
    _world,
)

METERS = {"m-1": {"label": "W-10442"}, "m-2": {"label": "W-10443"}}


def _answer(data, priced):
    lines = tuple(priced.priced.lines)
    warnings = tuple(priced.warnings)
    bill = one_time_answer.bill_document(
        lines,
        kind=one_time.KIND_INTERIM,
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        currency="USD",
        subtotal=priced.priced.taxable_subtotal,
        total=priced.priced.total,
        data=data,
        warnings=warnings,
        assets_by_id=METERS,
    )
    rates = one_time_answer.rates_table(
        data, warnings=warnings, lines=lines, assets_by_id=METERS, version_labels={}
    )
    return bill, rates


def test_t3__two_water_meters_answer_two_labelled_line_sets_and_58_40(monkeypatch):
    _install(
        monkeypatch,
        _world(plan_services=["water"], unit_services=["water"], assets={"water": ["m-1", "m-2"]}),
    )
    data = _gather([_water("6.1", asset_id="m-1"), _water("6.1", asset_id="m-2")])
    bill, rates = _answer(data, runs.price_account(data))

    assert bill["total"] == "58.4000"
    lines = [line for group in bill["groups"] for line in group["lines"]]
    by_meter: dict[str, Decimal] = {}
    for line in lines:
        by_meter[line["asset_label"]] = by_meter.get(line["asset_label"], Decimal("0")) + Decimal(
            line["amount"]
        )
    assert by_meter == {"W-10442": Decimal("29.2000"), "W-10443": Decimal("29.2000")}
    assert [(row["asset_label"], row["amount"]) for row in rates] == [
        ("W-10442", "29.2000"),
        ("W-10443", "29.2000"),
    ]
    assert all(row["rate_type"] == "tiered" for row in rates)
    assert {line["rate"] for line in lines if line["charge"] == "usage"} == {"tiered"}


def test_t3__two_carts_answer_a_count_of_two_and_36_00(monkeypatch):
    _install(
        monkeypatch,
        _world(
            plan_services=["trash"],
            unit_services=["trash"],
            assets={"trash": ["c-1", "c-2"]},
            size_groups={"trash": {"CART-96": 2}},
        ),
    )
    data = _gather(
        [
            ServiceReading(
                service_code="trash",
                absent_reason="service_not_metered",
                asset_count=2,
                asset_size_counts={"CART-96": 2},
            )
        ]
    )
    priced = runs.price_account(data)
    bill, _rates = _answer(data, priced)
    assert bill["total"] == "36.0000"
    services = one_time_answer.services_table(
        data,
        warnings=tuple(priced.warnings),
        assets={
            "trash": [{"asset_id": "c-1", "label": "C-1"}, {"asset_id": "c-2", "label": "C-2"}]
        },
        taken=None,
        unconnected=(),
        not_taken=(),
    )
    assert [(row["service"], row["status"], row["count"]) for row in services] == [
        ("trash", "billed", 2)
    ]


def test_t3__sewer_with_no_point_follows_water_as_one_percent_line(monkeypatch):
    _install(
        monkeypatch,
        _world(
            plan_services=["water", "sewer"],
            unit_services=["water"],
            assets={"water": ["m-1", "m-2"]},
        ),
    )
    data = _gather([_water("6.1", asset_id="m-1"), _water("6.1", asset_id="m-2")])
    priced = runs.price_account(data)
    bill, rates = _answer(data, priced)

    sewer = [
        line for group in bill["groups"] for line in group["lines"] if line["service"] == "sewer"
    ]
    percent = [line for line in sewer if line["charge"] == "percent"]
    assert [line["amount"] for line in percent] == ["24.4000"]
    assert percent[0]["asset_label"] is None, "sewer has no meter of its own"
    services = one_time_answer.services_table(
        data,
        warnings=tuple(priced.warnings),
        assets={"water": [{"asset_id": "m-1", "label": "W-10442"}]},
        taken=None,
        unconnected=tuple(data.unconnected_services),
        not_taken=(),
    )
    sewer_row = next(row for row in services if row["service"] == "sewer")
    assert sewer_row["status"] == "follows_basis"
    assert sewer_row["basis_service"] == "water" and sewer_row["assets"] == []
    sewer_rate = next(row for row in rates if row["service"] == "sewer")
    assert sewer_rate["rate_type"] == "percent_of_service"
    assert sewer_rate["usage_rate"]["basis_service"] == "water"


def test_t3__the_worked_window_is_the_fixtures():
    assert (PERIOD_START, PERIOD_END) == (date(2026, 6, 1), date(2026, 6, 30))
