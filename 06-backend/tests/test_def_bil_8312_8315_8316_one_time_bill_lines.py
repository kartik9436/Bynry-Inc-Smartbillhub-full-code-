# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-012 TC-12 (the review table) · US-BIL-032 TC-3 (the fee line)
#           Screens: S30 (the one-time bill, steps 2 and 3)
# Defects:  DEF-BIL-8312 (a fee line names no code) · DEF-BIL-8315 (one line
#           per tier, not per meter; base with no quantity or rate; trash with no
#           cart) · DEF-BIL-8316 (services out of catalogue order; trash rate
#           read as a ladder; base charge with no code; long version label)
# Drawing:  05-prototype/one-time-bill-2026-09-30/1440-05-Interim-3-review.png,
#           1440-03-Interim-2-services.png
# ───────────────────────────────────────────────────────
"""The one-time bill's lines and rates, shaped as the drawing prints them.

Every figure here is the ENGINE's line, relabelled — no money is computed. The
tier lines of one meter are summed (their amounts were already rounded per
line, so the subtotal cannot move) and the saved bill keeps the per-tier rows.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from apps.billing import one_time_answer, rating_seam

WATER = rating_seam.TariffConfig(
    service="water",
    model="tiered",
    billed_unit="kgal",
    base_charge=Decimal("8.00"),
    tiers=(
        rating_seam.Tier(upper=Decimal("5"), unit_price=Decimal("3.25")),
        rating_seam.Tier(upper=None, unit_price=Decimal("4.50")),
    ),
    base_charge_code="BASE-W",
)
TRASH = rating_seam.TariffConfig(
    service="trash",
    model="tiered",
    billed_unit="cart",
    base_charge=Decimal("3.00"),
    tiers=(rating_seam.Tier(upper=None, unit_price=Decimal("15.00")),),
    base_charge_code="BASE-T",
)


def _line(service, kind, amount, *, quantity=None, unit=None, unit_price=None, asset_label=None, **extra):
    return SimpleNamespace(
        service=service,
        kind=kind,
        amount=Decimal(amount),
        quantity=None if quantity is None else Decimal(quantity),
        unit=unit,
        unit_price=None if unit_price is None else Decimal(unit_price),
        asset_label=asset_label,
        asset_id=None,
        description=extra.get("description", ""),
        charge_id=extra.get("charge_id"),
    )


@pytest.fixture
def catalogue(monkeypatch):
    order = ("electric", "water", "gas", "sewer", "trash", "storm_water", "solar",
             "broadband", "thermal_heat", "battery", "fire")
    monkeypatch.setattr(
        one_time_answer, "_service_rank", lambda: {code: i for i, code in enumerate(order)}
    )
    monkeypatch.setattr(one_time_answer, "_unmetered", lambda: frozenset({"trash", "fire", "sewer"}))


def _bill(lines, data=None, **kwargs):
    return one_time_answer.bill_document(
        tuple(lines),
        kind="interim",
        period_start=date(2026, 9, 1),
        period_end=date(2026, 9, 30),
        currency="USD",
        subtotal=sum((line.amount for line in lines), Decimal("0")),
        total=sum((line.amount for line in lines), Decimal("0")),
        data=data or SimpleNamespace(tariffs=(WATER, TRASH), readings=()),
        **kwargs,
    )


def test_def_bil_8315__a_tiered_meter_prints_one_usage_line_and_a_base_of_1_at_its_rate(catalogue):
    bill = _bill(
        [
            _line("water", "usage", "16.25", quantity="5", unit="kgal", unit_price="3.25", asset_label="W-10442"),
            _line("water", "usage", "4.95", quantity="1.1", unit="kgal", unit_price="4.50", asset_label="W-10442"),
            _line("water", "base", "8.00", asset_label="W-10442"),
        ]
    )
    lines = bill["groups"][0]["lines"]
    assert [(l["charge"], l["quantity"], l["rate"], l["amount"]) for l in lines] == [
        ("usage", "6.1", "tiered", "21.2000"),
        ("base", "1", "8.0000", "8.0000"),
    ]
    assert bill["groups"][0]["subtotal"] == "29.2000", "the subtotal cannot move"


def test_def_bil_8315__trash_prints_per_cart_and_base_per_cart(catalogue):
    bill = _bill(
        [
            _line("trash", "usage", "15.00", quantity="1", unit="cart", unit_price="15.00"),
            _line("trash", "base", "3.00"),
        ]
    )
    usage, base = bill["groups"][0]["lines"]
    assert (usage["charge"], usage["per_unit"], usage["quantity"], usage["rate"]) == (
        "per_asset", "cart", "1", "15.00",
    )
    assert (base["charge"], base["per_unit"], base["quantity"]) == ("base", "cart", "1")
    assert "_price" not in usage, "the engine's working price is never served"


def test_def_bil_8316__lines_print_in_catalogue_order_not_alphabetical(catalogue):
    bill = _bill(
        [
            _line("water", "usage", "4.00", quantity="1", unit="kgal", unit_price="3.25", asset_label="W-1"),
            _line("trash", "usage", "15.00", quantity="1", unit="cart", unit_price="15.00"),
            _line("electric", "usage", "74.70", quantity="600", unit="kWh", unit_price="0.1245"),
        ]
    )
    assert [l["service"] for l in bill["groups"][0]["lines"]] == ["electric", "water", "trash"]


def test_def_bil_8312__a_fee_line_names_its_charge_code_quantity_and_rate(catalogue):
    bill = one_time_answer.bill_document(
        (_line("", "fee", "75.00", description="Reconnection fee", charge_id="C-1"),),
        kind="fee",
        period_start=date(2026, 9, 30),
        period_end=date(2026, 9, 30),
        currency="USD",
        subtotal=Decimal("75.00"),
        total=Decimal("75.00"),
        charge_codes={"C-1": "RECON"},
    )
    line = bill["groups"][0]["lines"][0]
    assert (line["charge"], line["code"], line["service"], line["quantity"], line["amount"]) == (
        "fee", "RECON", "Reconnection fee", "1", "75.0000",
    )


def test_def_bil_8316__rates_name_the_base_code_a_single_price_and_per_asset(catalogue, monkeypatch):
    monkeypatch.setattr(one_time_answer, "_version_from", lambda ids: {})
    rows = one_time_answer.rates_table(
        SimpleNamespace(tariffs=(TRASH, WATER)),
        warnings=(),
        lines=(),
        assets_by_id={},
        version_labels={},
    )
    assert [row["service"] for row in rows] == ["water", "trash"]
    water, trash = rows
    assert water["base_charge"]["code"] == "BASE-W"
    assert trash["rate_type"] == "per_asset"
    assert trash["usage_rate"] == {"price": "15.00", "unit": "cart"}
    assert water["usage_rate"]["tiers"][0]["price"] == "3.25"
