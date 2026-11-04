# ── Trace ──────────────────────────────────────────────
# Defects:  DEF-BIL-8561 (a catch-up's Review is one group over the whole window)
#           · DEF-BIL-8565 (Subtotal + Tax did not make the Total on a first bill
#           or a penalty) · DEF-BIL-8564 (a catch-up's never-read estimate was not
#           saved in Meter Reads, and its day-shares were attempted) ·
#           DEF-BIL-8562 (an interim bill could not estimate a meter)
# Journey:  J74 cases 2, 3b, 6, 7
# Screens:  S30 (the one-time bill, steps 2 and 3)
# ───────────────────────────────────────────────────────
"""What the clerk reviews, and what issue saves: the months, the footer, the estimates.

Every figure is the ENGINE's line, relabelled or copied — no money is computed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from apps.billing import metering_seam, one_time, one_time_answer, rating_seam
from apps.billing.contracts import ServiceReading

JUL = (date(2026, 7, 1), date(2026, 7, 31))


@dataclass(frozen=True)
class _Data:
    readings: tuple
AUG = (date(2026, 8, 1), date(2026, 8, 31))


def _line(service, kind, amount, *, description="", **extra):
    return SimpleNamespace(
        service=service,
        kind=kind,
        amount=Decimal(amount),
        quantity=extra.get("quantity"),
        unit=extra.get("unit"),
        unit_price=extra.get("unit_price"),
        asset_id=None,
        description=description,
        charge_id=extra.get("charge_id"),
    )


@pytest.fixture
def plain(monkeypatch):
    monkeypatch.setattr(one_time_answer, "_service_rank", lambda: {"electric": 0, "water": 1})
    monkeypatch.setattr(one_time_answer, "_unmetered", lambda: frozenset())


def _bill(lines, *, kind, windows=None, subtotal="0", total="0"):
    return one_time_answer.bill_document(
        tuple(lines),
        kind=kind,
        period_start=JUL[0],
        period_end=AUG[1],
        currency="USD",
        subtotal=Decimal(subtotal),
        total=Decimal(total),
        line_windows=windows,
    )


def test_8561__a_catch_up_prints_one_group_per_month(plain):
    lines = [
        _line("water", "usage", "32.50", quantity=Decimal("10"), unit="kgal"),
        _line("water", "usage", "65.00", quantity=Decimal("20"), unit="kgal"),
        _line(None, "tax", "1.95"),
    ]
    bill = _bill(lines, kind="backbill", windows=(JUL, AUG, None), subtotal="97.50", total="99.45")
    assert [(g["period_start"], g["period_end"], g["subtotal"]) for g in bill["groups"]] == [
        ("2026-07-01", "2026-07-31", "32.5000"),
        ("2026-08-01", "2026-08-31", "65.0000"),
    ], "DEF-BIL-8561: one group per month, each with its own subtotal"


def test_8561__a_drafted_line_is_grouped_by_its_own_stored_month(plain):
    stored = [
        SimpleNamespace(**vars(_line("water", "usage", "32.50", quantity=Decimal("10"), unit="kgal")),
                        period_start=JUL[0], period_end=JUL[1]),
        SimpleNamespace(**vars(_line("water", "usage", "65.00", quantity=Decimal("20"), unit="kgal")),
                        period_start=AUG[0], period_end=AUG[1]),
    ]
    bill = _bill(stored, kind="backbill", subtotal="97.50", total="97.50")
    assert len(bill["groups"]) == 2


def test_8565__a_first_bills_footer_adds_up(plain):
    """Case 3b: $198.84 of services + $3.98 tax + $195.00 deposit and CONN = $397.82."""
    lines = [
        _line("water", "usage", "198.84", quantity=Decimal("16.4"), unit="kgal"),
        _line(None, "deposit", "150.00", description="Security deposit"),
        _line(None, "fee", "45.00", description="Connection fee"),
        _line(None, "tax", "3.98"),
    ]
    bill = _bill(lines, kind="first", subtotal="198.84", total="397.82")
    assert bill["one_time_charges"] == "195.0000", "DEF-BIL-8565: the deposit and CONN get a footer line"
    assert Decimal(bill["subtotal"]) + Decimal(bill["tax"][0]["amount"]) + Decimal(
        bill["one_time_charges"]
    ) == Decimal(bill["total"])


def test_8565__a_fee_bills_charge_stays_the_subtotal(plain):
    lines = [_line(None, "fee", "75.00", description="Reconnection fee"), _line(None, "tax", "1.50")]
    bill = _bill(lines, kind="fee", subtotal="75.00", total="76.50")
    assert bill["one_time_charges"] is None
    assert bill["subtotal"] == "75.0000"


def test_8734__an_untaxed_fee_bills_footer_adds_up(plain):
    """`DEF-BIL-8734` (J75 case 8): RECON $75.00 NOT taxable — the engine's
    taxable subtotal is $0.00, and the page printed Subtotal $0.00 over a Total
    of $75.00. The fee IS the bill, so it is the subtotal: $75.00 + no tax = $75.00."""
    lines = [_line(None, "fee", "75.00", description="Reconnection fee")]
    bill = _bill(lines, kind="fee", subtotal="0", total="75.00")
    assert bill["one_time_charges"] is None
    assert bill["subtotal"] == "75.0000", "DEF-BIL-8734: an untaxed fee is still the bill's subtotal"
    assert Decimal(bill["subtotal"]) + sum(Decimal(t["amount"]) for t in bill["tax"]) == Decimal(bill["total"])


# ── DEF-BIL-8564: what a catch-up saves into Meter Reads at issue ───────────


def _invoice(payload):
    return SimpleNamespace(
        bill_payload=payload,
        account=SimpleNamespace(unit_id="unit-1"),
        period_end=date(2026, 9, 30),
        pk="inv-1",
        bill_run_id="run-1",
    )


@pytest.mark.django_db
def test_8564__a_catch_up_saves_only_the_stretch_no_reading_measured(monkeypatch):
    saved = []

    def record(**kwargs):
        saved.append(kwargs)
        return {"recorded": True, "read_id": "r"}

    monkeypatch.setattr(
        metering_seam, "import_module", lambda name: SimpleNamespace(record_billed_estimate=record)
    )
    payload = {
        "bill_type": "backbill",
        # a day-share of a real reading — must NOT be saved (the reading is on file)
        "services": [
            {"code": "water", "asset_id": "m1", "read_id": None, "estimate": {"amount": "3.29", "unit": "kgal"}}
        ],
        "back_bill": {
            "estimates": [
                {"service_code": "water", "asset_id": "m1", "quantity": "3.29", "unit": "kgal",
                 "period_end": "2026-07-15", "source": "day_weighted", "unmeasured": False},
                {"service_code": "water", "asset_id": "m2", "quantity": "6.0", "unit": "kgal",
                 "period_end": "2026-08-31", "source": "metering", "unmeasured": True},
            ]
        },
    }
    outcome = metering_seam.record_billed_estimates(_invoice(payload))
    assert outcome.recorded == 1
    assert [(row["asset_id"], row["read_on"], row["consumption"]) for row in saved] == [
        ("m2", date(2026, 8, 31), "6.0")
    ], "DEF-BIL-8564: only the never-read stretch, on ITS last day"


# ── DEF-BIL-8562: an interim meter estimated on step 2 ──────────────────────


def test_8562__an_interim_meter_with_no_reading_takes_the_meters_own_estimate(monkeypatch):
    asked = []

    def estimate(unit_id, *, service_code, period_start, period_end, asset_id=None):
        asked.append((service_code, period_start, period_end, asset_id))
        return (Decimal("6.0"), "kgal", None)

    monkeypatch.setattr(one_time.backbill, "_metering_estimate", estimate)
    monkeypatch.setattr(one_time.single, "billable_account", lambda account_id: SimpleNamespace(unit_id="u1"))
    data = _Data(
        readings=(ServiceReading(service_code="water", consumption=None, absent_reason="no_read"),)
    )
    request = one_time.OneTimeRequest(
        account_id="a1",
        kind="interim",
        readings=({"asset_id": "W-10460-id", "service": "water", "role": "estimate"},),
    )
    out = one_time.with_clerk_estimates(
        data, request, period_start=date(2026, 9, 1), period_end=date(2026, 9, 30)
    )
    reading = out.readings[0]
    assert reading.consumption == rating_seam.Quantity(amount=Decimal("6.0"), unit="kgal")
    assert reading.estimated and reading.read_id is None, (
        "an estimate carries no read, so issue saves it into Meter Reads (DEF-BIL-8280's path)"
    )
    assert asked == [("water", date(2026, 9, 1), date(2026, 9, 30), "W-10460-id")]


def test_8562__a_meter_with_a_reading_is_never_estimated(monkeypatch):
    monkeypatch.setattr(
        one_time.backbill, "_metering_estimate", lambda *a, **k: pytest.fail("a read always wins")
    )
    monkeypatch.setattr(one_time.single, "billable_account", lambda account_id: SimpleNamespace(unit_id="u1"))
    read = ServiceReading(
        service_code="water", consumption=rating_seam.Quantity(Decimal("6.1"), "kgal"), read_id="r1"
    )
    request = one_time.OneTimeRequest(
        account_id="a1", kind="interim", readings=({"asset_id": "m", "service": "water", "role": "estimate"},)
    )
    data = _Data(readings=(read,))
    assert one_time.with_clerk_estimates(
        data, request, period_start=date(2026, 9, 1), period_end=date(2026, 9, 30)
    ) is data
