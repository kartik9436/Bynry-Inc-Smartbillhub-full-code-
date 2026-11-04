# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-BIL-10128 — move-out step 3 said "The draft bill is not
#           generated · Sewer: reading needed" for sewer billed as "90.00% of
#           Water usage" (PO screenshot, Ottumwa Water Works, 2026-10-14;
#           decision log "G1–G4 APPROVED" item 1).
# Rules:    BR-BIL-015 (a metered service with no read still stops the bill —
#           the negative case below) · BR-RAT-015 (sewer prices a percentage
#           of water and has no reading of its own) · DEF-990/1060 (a base-only
#           tariff is owed no read)
# Tests:    this file
# ───────────────────────────────────────────────────────
"""`final_bill.missing_values` asks the ENGINE which values are missing.

The pre-check read each gathered READING's reason. Metering answers `no_meter`
for a sewer point that has no meter and never will, and only stage 2 turns that
into `tariff_prices_no_consumption` — the exempt reason — because whether a
read was ever owed is a fact about the TARIFF. So the draft refused a bill the
engine would have priced.

⚠ **WHAT WOULD MAKE THESE PASS WRONGLY** (law 7, habit 2):

  * **An exemption by service CODE.** The usage and charge cases use the same
    `sewer` code as the negative case where sewer's tariff is `flat`; only the
    tariff's MODEL changes, so a fix keyed on the name `sewer` fails there.
  * **A fix that exempts every `no_meter`.** The water case keeps metering's
    own `no_reading_supplied` and the flat-sewer case keeps `no_meter`; both
    must still be listed.
  * **A pre-check that passes but a draft that does not price.** The two
    positive cases also run `runs.price_account` on the same data and assert a
    sewer line, so "not listed" and "the engine prices it" are one claim.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from apps.billing import final_bill, metering_seam, rating_seam, runs, single
from apps.billing.contracts import AccountBillingData, ServiceReading

UNIT_ID = "0190a1b2-0000-7000-8000-00000000a128"


@pytest.fixture(autouse=True)
def _no_database(monkeypatch):
    """`missing_values` reaches the database only for the unit's meter NAMES."""
    monkeypatch.setattr(
        single, "billable_account", lambda _account_id: SimpleNamespace(unit_id=UNIT_ID)
    )
    monkeypatch.setattr(
        metering_seam,
        "meter_numbers_for_units",
        lambda _ids: {UNIT_ID: {"water": ["W-5040"], "sewer": []}},
    )


WATER = rating_seam.TariffConfig(
    service="water",
    model="flat",
    billed_unit="kgal",
    base_charge=Decimal("10.0000"),
    unit_price=Decimal("5.0000"),
)


def _sewer_share(basis: str) -> rating_seam.TariffConfig:
    return rating_seam.TariffConfig(
        service="sewer",
        model="percent_of_service",
        billed_unit="kgal",
        base_charge=Decimal("0"),
        unit_price=Decimal("5.0000") if basis == "usage" else None,
        percent=Decimal("90"),
        basis_service="water",
        percent_basis=basis,
    )


def _data(*readings: ServiceReading, tariffs) -> AccountBillingData:
    return AccountBillingData(
        account_id="acc-10128",
        account_no="ACC-06",
        behavior_class="billable",
        currency="USD",
        tax_exempt=True,
        period_start=date(2026, 10, 1),
        period_end=date(2026, 10, 14),
        cycle_days=31,
        service_days=14,
        rate_plan_id="plan-10128",
        tariffs=tuple(tariffs),
        readings=tuple(readings),
    )


WATER_READ = ServiceReading(
    service_code="water",
    consumption=rating_seam.Quantity(amount=Decimal("22"), unit="kgal"),
)
SEWER_NO_METER = ServiceReading(service_code="sewer", absent_reason="no_meter")
WATER_UNREAD = ServiceReading(service_code="water", absent_reason="no_reading_supplied")


@pytest.mark.parametrize("basis", ["usage", "charge"])
def test_sewer_priced_as_a_percent_of_water_is_not_a_missing_value(basis):
    data = _data(WATER_READ, SEWER_NO_METER, tariffs=(WATER, _sewer_share(basis)))

    assert final_bill.missing_values(data, account_id="acc-10128") == []
    # ... and the engine really does price it, with a sewer line.
    priced = runs.price_account(data).priced
    sewer_lines = [line for line in priced.lines if line.service == "sewer"]
    assert sewer_lines, [line.description for line in priced.lines]
    assert any(line.amount > 0 for line in sewer_lines)


def test_a_genuinely_missing_water_reading_is_still_named():
    data = _data(WATER_UNREAD, SEWER_NO_METER, tariffs=(WATER, _sewer_share("usage")))

    missing = final_bill.missing_values(data, account_id="acc-10128")

    assert missing == [{"service": "water", "meters": ["W-5040"], "what": "reading"}]


def test_sewer_on_a_consumption_priced_tariff_with_no_meter_is_still_named():
    """BR-MET-134 / DEF-161: only the pricing MODEL exempts it."""
    flat_sewer = rating_seam.TariffConfig(
        service="sewer", model="flat", billed_unit="kgal", unit_price=Decimal("4.0000")
    )
    data = _data(WATER_READ, SEWER_NO_METER, tariffs=(WATER, flat_sewer))

    missing = final_bill.missing_values(data, account_id="acc-10128")

    assert [row["service"] for row in missing] == ["sewer"]


def test_a_base_only_tariff_is_owed_no_reading():
    base_only_sewer = rating_seam.TariffConfig(
        service="sewer",
        model="flat",
        billed_unit="kgal",
        base_charge=Decimal("22.5000"),
        base_only=True,
    )
    data = _data(WATER_READ, SEWER_NO_METER, tariffs=(WATER, base_only_sewer))

    assert final_bill.missing_values(data, account_id="acc-10128") == []


def test_a_keyed_estimate_metering_could_not_give_is_named_as_such():
    """`DEF-BIL-10052`'s second kind of gap survives the change of source."""
    data = _data(
        ServiceReading(service_code="water", absent_reason="estimate_unavailable:no_history"),
        SEWER_NO_METER,
        tariffs=(WATER, _sewer_share("usage")),
    )

    missing = final_bill.missing_values(data, account_id="acc-10128")

    assert missing == [{"service": "water", "meters": ["W-5040"], "what": "estimate_no_history"}]
