# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-BIL-9793 (high, money) — CR-171 §28.1, M6 Foundry Works
# Rules:   BR-RAT-1015 / BR-BIL-1048 amendment (1) (PO 2026-09-30, option B:
#          sewer has no service point and follows water) · BR-MET-119 (a
#          premises DECLARES what services the address offers; a unit may never
#          take one it does not) · BR-BIL-300/301 (not in service prints no
#          line and lands on the clerk's review list)
# Tests:   this file
# Impacts: apps/billing/gather.py (_unconnected_plan_services, gather_account)
# ───────────────────────────────────────────────────────
"""**SEWER FOLLOWS WATER — AT AN ADDRESS THAT OFFERS SEWER.**

The PO ruled on 2026-09-30 that sewer has no service point and is billed
whenever water is. That made a missing sewer POINT unable to stop sewer. It
did not make the ADDRESS unable to: a premises declares which services it
offers (BR-MET-119), and Foundry Works' address at 5 Foundry Way offers
electric, gas, water and solar — no sewer. Its first bill nevertheless carried
`$38.25` of sewer usage and a `$9.00` sewer base, and taxed both.

Every case here prices through the real `runs.price_account` (stages 1 → 5,
the function a bill run AND the one-time bill call), so the gap is closed for
both at once.

RED BEFORE THE FIX (law 7): `tc1` and `tc4` failed on the tip with sewer in
the tariff list — quoted in each docstring.
"""

from types import SimpleNamespace

from decimal import Decimal

from apps.billing import runs
from tests.test_br_bil_300_services_rulings_2026_09_30 import (  # noqa: F401
    _gather,
    _install,
    _pricing_inputs,
    _rolled_back_resolution_chain,
    _total,
    _water,
    _world,
)

#: 5 kgal of water on the fixture's ladder: 5 × $3.25 = $16.25, plus its
#: $8.00 base. Sewer on top would be 40% × 5 = 2 kgal × $5.00 = $10.00 and its
#: own $5.00 base — `$15.00` that this file is about.
WATER_ONLY = Decimal("16.25") + Decimal("8.00")
SEWER = Decimal("10.00") + Decimal("5.00")


def _at_address(world, offered):
    """The fixture's unit, standing on a premises that offers `offered`
    (`None` = nobody was ever asked, DEF-762's third state)."""
    world["metering.unit_row"] = lambda _id: SimpleNamespace(
        id="unit-930",
        label="Unit 1",
        rate_plan_id="plan-res",
        premises=SimpleNamespace(
            id="prem-930",
            city=None,
            state=None,
            postal_code=None,
            address_line="5 Foundry Way",
            inside_city_limits=None,
            services_available=offered,
        ),
    )
    return world


def test_tc1__an_address_with_no_sewer_bills_no_sewer(monkeypatch):
    """**Foundry Works' shape: the address offers electric, gas, water and
    solar; the plan prices sewer as 40% of water; the account took water.**
    No sewer line, no sewer base — the bill is water alone, `$24.25`, where
    the tip charged `$39.25`. Sewer goes on the clerk's review list as not in
    service, exactly as a plan service the property has no point for does.

    RED ON THE TIP: `AssertionError: assert ['sewer'] == []` — sewer was
    priced because water was, with no question asked of the address.
    """
    _install(
        monkeypatch,
        _at_address(
            _world(
                plan_services=["water", "sewer"],
                unit_services=["water"],
                assets={"water": ["m-1"]},
                taken=("water",),
            ),
            ["electric", "gas", "water", "solar"],
        ),
    )
    data = _gather([_water(5)])

    assert [c.service for c in data.tariffs if c.service == "sewer"] == []
    assert "sewer" in data.unconnected_services
    priced = runs.price_account(data)
    assert {line.service for line in priced.priced.lines} == {"water"}
    assert _total(priced) == WATER_ONLY


def test_tc2__an_address_that_offers_sewer_still_bills_it_with_water(monkeypatch):
    """The ruling itself, unchanged: the address offers sewer, there is no
    sewer point and no sewer agreement, and sewer bills because water does —
    `$24.25 + $15.00 = $39.25`."""
    _install(
        monkeypatch,
        _at_address(
            _world(
                plan_services=["water", "sewer"],
                unit_services=["water"],
                assets={"water": ["m-1"]},
                taken=("water",),
            ),
            ["water", "sewer"],
        ),
    )
    data = _gather([_water(5)])

    assert sorted(c.service for c in data.tariffs) == ["sewer", "water"]
    assert "sewer" not in data.unconnected_services
    assert _total(runs.price_account(data)) == WATER_ONLY + SEWER


def test_tc3__an_address_nobody_asked_about_follows_water_as_today(monkeypatch):
    """`services_available` NULL means nobody was ever asked (DEF-762), which
    is not *offers nothing*. Narrowing on it would take sewer off every bill
    at an address created before premises could record services — so it
    narrows nothing, and sewer bills with water exactly as on the tip."""
    _install(
        monkeypatch,
        _at_address(
            _world(
                plan_services=["water", "sewer"],
                unit_services=["water"],
                assets={"water": ["m-1"]},
                taken=("water",),
            ),
            None,
        ),
    )
    data = _gather([_water(5)])

    assert sorted(c.service for c in data.tariffs) == ["sewer", "water"]
    assert _total(runs.price_account(data)) == WATER_ONLY + SEWER


def test_tc4__no_agreements_on_file_still_bills_no_sewer_where_none_is_offered(monkeypatch):
    """The other door into the same overcharge: an account with NO agreements
    on file narrows nothing (BR-BIL-1048 (2), option C) — but it cannot buy a
    service its address does not offer either. Water alone, `$24.25`.

    RED ON THE TIP: `AssertionError: assert ['sewer'] == []`.
    """
    _install(
        monkeypatch,
        _at_address(
            _world(
                plan_services=["water", "sewer"],
                unit_services=["water"],
                assets={"water": ["m-1"]},
                taken=None,
            ),
            ["water"],
        ),
    )
    data = _gather([_water(5)])

    assert [c.service for c in data.tariffs if c.service == "sewer"] == []
    assert _total(runs.price_account(data)) == WATER_ONLY


# ══════════════════════════════════════════════════════════════════════════
# SIGNED 2026-10-06 — the statement the PO approved, figure for figure
# ══════════════════════════════════════════════════════════════════════════
#: The tax this file prices with (8.25%), so "the tax on $47.25" is a number.
SIGNED_TAX_RATE = Decimal("0.0825")


def _foundry_works(offered):
    """Foundry Works' own figures: sewer is 90% of water, its base `$9.00`;
    8.5 kgal of water → 7.65 kgal of sewer × `$5.00` = `$38.25`."""
    world = _at_address(
        _world(
            plan_services=["water", "sewer"],
            unit_services=["water"],
            assets={"water": ["m-1"]},
            taken=("water",),
        ),
        offered,
    )

    def ninety_percent(tariff, service_date, *size, **kw):
        inputs = _pricing_inputs(tariff, service_date, *size, **kw)
        return {**inputs, "percent": "90"} if tariff.service == "sewer" else inputs

    world["rating.pricing_inputs"] = ninety_percent
    world["rating.base_charge_from_charge_code"] = lambda service_code, **_k: {
        "amount": {"water": "8.00", "sewer": "9.00"}[service_code],
        "code": f"BASE-{service_code.upper()}",
        "refusal": None,
    }
    world["rating.plan_tax_rules"] = lambda *_a, **_k: [
        {"code": "STATE+LOCAL", "rate": str(SIGNED_TAX_RATE), "tax_id": "TAX-TX"}
    ]
    return world


def test_the_statement_the_po_signed_on_2026_10_06(monkeypatch):
    """**PO, verbatim, 2026-10-06: *"S1–S8 approve"*** — S1, shown as:
    *"Foundry Works never started sewer, so its first bill no longer carries
    $38.25 sewer usage and $9.00 sewer base, and its tax falls by the tax on
    $47.25. Sewer is billed only where the address offers sewer."*

    The same account priced twice through `runs.price_account`: at an address
    that offers sewer (the ruling of 2026-09-30, unchanged) the bill carries
    sewer usage `$38.25` and sewer base `$9.00`; at 5 Foundry Way (electric,
    gas, water, solar) it carries neither, its taxable amount falls by exactly
    `$47.25`, and its tax by the tax on `$47.25`.
    """
    _install(monkeypatch, _foundry_works(["water", "sewer"]))
    offered = runs.price_account(_gather([_water("8.5")])).priced
    assert [(l.kind, l.amount) for l in offered.lines if l.service == "sewer"] == [
        ("usage", Decimal("38.25")),
        ("base", Decimal("9.00")),
    ]

    _install(monkeypatch, _foundry_works(["electric", "gas", "water", "solar"]))
    foundry = runs.price_account(_gather([_water("8.5")])).priced
    assert [l for l in foundry.lines if l.service == "sewer"] == []
    assert offered.taxable_subtotal - foundry.taxable_subtotal == Decimal("47.25")
    assert offered.tax_total - foundry.tax_total == (
        Decimal("47.25") * SIGNED_TAX_RATE
    ).quantize(Decimal("0.01"))
