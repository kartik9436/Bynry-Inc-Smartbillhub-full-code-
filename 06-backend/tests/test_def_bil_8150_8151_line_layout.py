# ── Trace ──────────────────────────────────────────────
# Defects: DEF-BIL-8150 (a per-meter minimum top-up named no meter and no
#          service) · DEF-BIL-8151 (a counted service printed as two lines)
# Rulings: PO 2026-09-30, decision log "ONE-TIME BILL: SIX ANSWERS" —
#          (4) *"consider them 2 lines anc charge"* (the minimum applies to
#          EACH meter, each on its own line) · (5) *"per service"* (ONE line
#          per counted service, count and sizes in the line; amount unchanged)
# Code:    apps/rating/pricing/stages/apply_charges.py (🔒 — the top-up's
#          asset_id) · apps/billing/stages/assemble_document._service_id_for
#          (the top-up's service) · apps/billing/counted_service_line.py +
#          apps/billing/runs.price_account (the one-line layout)
# PG:      tests/test_otb_t2_money_paths_pg.py proves both on the stored rows
# ───────────────────────────────────────────────────────
"""**WHICH METER A MINIMUM BELONGS TO, AND ONE LINE PER COUNTED SERVICE.**

Both are LAYOUT and IDENTITY. Every figure below is the one the engine already
produced before the fix; what changes is which line carries it.

RED BEFORE THE FIX (run against the tip, 2026-09-30, SQLite):

    tc1  AssertionError: assert [None] == ['m-2']      (the top-up named no meter)
    tc3  AssertionError: assert 2 == 1                 (usage $30.00 + base $6.00)
    tc4  AssertionError: assert 3 == 1                 (FL-2, FL-6 and the base)
"""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest

from apps.billing import counted_service_line, rating_seam, runs
from apps.billing.contracts import ServiceReading
from apps.billing.stages import assemble_document as stage6

from tests import test_br_bil_300_services_rulings_2026_09_30 as rulings


@pytest.fixture(autouse=True)
def _rolled_back_resolution_chain(settings, monkeypatch):
    """The rulings file's own autouse fixture, taken here explicitly."""
    settings.BILLING_RESOLUTION_STEPS = ""
    monkeypatch.setattr(runs, "_continuity_decisions", lambda *_a, **_k: [])


def _minimum_world():
    def with_minimum(tariff, service_date, *size, **kw):
        inputs = rulings._pricing_inputs(tariff, service_date, *size, **kw)
        if getattr(tariff, "service", None) == "water":
            inputs = {
                **inputs,
                "minimum_bill": "10.00",
                "model": "flat",
                "unit_price": "1.00",
                "tiers": [],
            }
        return inputs

    world = rulings._world(
        plan_services=["water"], unit_services=["water"], assets={"water": ["m-1", "m-2"]}
    )
    world["rating.pricing_inputs"] = with_minimum
    world["rating.base_charge_from_charge_code"] = lambda service_code, **_k: {
        "amount": "0.00",
        "code": "BASE-W",
        "refusal": None,
    }
    return world


def _sum(lines):
    return sum((line.amount for line in lines), Decimal("0"))


# ══════════════════════════════════════════════════════════════════════════
# DEF-BIL-8150 · THE MINIMUM NAMES ITS METER
# ══════════════════════════════════════════════════════════════════════════
def test_tc1__the_minimum_top_up_names_the_meter_it_tops_up(monkeypatch):
    """**Minimum `$10.00`; meter A `$14.00`, meter B `$6.00`** → meter A
    `$14.00`, meter B `$6.00 + $4.00 = $10.00`, bill `$24.00`.

    PO 2026-09-30 (*"SIX ANSWERS"* (4)), verbatim: *"consider them 2 lines anc
    charge"*. The money was already right; the `$4.00` named no meter."""
    rulings._install(monkeypatch, _minimum_world())
    data = rulings._gather(
        [rulings._water("14", asset_id="m-1"), rulings._water("6", asset_id="m-2")]
    )
    priced = runs.price_account(data).priced

    tops = [line for line in priced.lines if line.kind == "minimum_adjustment"]
    assert [line.asset_id for line in tops] == ["m-2"]
    assert [line.service for line in tops] == ["water"]
    assert [line.amount for line in tops] == [Decimal("4.00")]
    by_meter = {
        meter: _sum(line for line in priced.lines if line.asset_id == meter)
        for meter in ("m-1", "m-2")
    }
    assert by_meter == {"m-1": Decimal("14.00"), "m-2": Decimal("10.00")}
    assert priced.total == Decimal("24.00")


def test_tc2__stage_6_writes_the_minimum_service_and_leaves_the_plan_floor_bare():
    """A per-service top-up stores its service; the plan floor (BR-RAT-028
    mode B, `service=None`) stores none; neither is ever refused, because the
    top-up's GL account is the minimum-bill DESIGNATION, not the service map."""
    usage = SimpleNamespace(subscription=SimpleNamespace(account_no="AC-1"))
    ids = {"water": "svc-water"}
    per_service = SimpleNamespace(service="water", description="Minimum bill adjustment")
    floor = SimpleNamespace(service=None, description="Minimum bill adjustment")
    unknown = SimpleNamespace(service="nope", description="Minimum bill adjustment")

    assert stage6._service_id_for(per_service, "minimum_adjustment", ids, usage) == "svc-water"
    assert stage6._service_id_for(floor, "minimum_adjustment", ids, usage) is None
    assert stage6._service_id_for(unknown, "minimum_adjustment", ids, usage) is None


# ══════════════════════════════════════════════════════════════════════════
# DEF-BIL-8151 · ONE LINE PER COUNTED SERVICE
# ══════════════════════════════════════════════════════════════════════════
def _carts(monkeypatch):
    rulings._install(
        monkeypatch,
        rulings._world(
            plan_services=["trash"],
            unit_services=["trash"],
            assets={"trash": ["c-1", "c-2"]},
            size_groups={"trash": {"CART-96": 2}},
        ),
    )
    return rulings._gather(
        [
            ServiceReading(
                service_code="trash",
                absent_reason="service_not_metered",
                asset_count=2,
                asset_size_counts={"CART-96": 2},
            )
        ]
    )


def test_tc3__two_carts_are_one_36_dollar_line(monkeypatch):
    """**2 carts × ($15.00 + $3.00) = ONE `$36.00` line**, quantity 2 carts at
    `$18.00` — PO 2026-09-30 (*"SIX ANSWERS"* (5)), verbatim: *"per service"*.
    Was usage `$30.00` + base `$6.00`."""
    priced = runs.price_account(_carts(monkeypatch)).priced

    trash = [line for line in priced.lines if line.service == "trash"]
    assert len(trash) == 1, [(line.kind, line.amount) for line in trash]
    (line,) = trash
    assert line.amount == Decimal("36.00")
    assert (line.kind, line.quantity, line.unit) == ("usage", Decimal("2"), "cart")
    assert line.unit_price == Decimal("18.00")
    assert line.quantity * line.unit_price == line.amount
    assert priced.total == Decimal("36.00")


def test_tc4__a_fire_property_with_two_sizes_is_one_line_and_the_same_money(monkeypatch):
    """**One 6" line and two 2" lines is ONE fire line** — PO: CR-063's
    *"on two bill lines"* is superseded for LAYOUT, the amount is not. This
    fixture prices every size at `$60.00` with a `$9.00` base per asset
    (the rulings file's world): `3 × $60.00 + 3 × $9.00 = $207.00`, the figure
    the three lines summed to before. Two sizes have no single rate, so the
    line prints none."""
    rulings._install(
        monkeypatch,
        rulings._world(
            plan_services=["fire"],
            unit_services=["fire"],
            assets={"fire": ["f-1", "f-2", "f-3"]},
            size_groups={"fire": {"FL-6": 1, "FL-2": 2}},
        ),
    )
    data = rulings._gather(
        [
            ServiceReading(
                service_code="fire",
                absent_reason="service_not_metered",
                asset_count=3,
                asset_size_counts={"FL-6": 1, "FL-2": 2},
            )
        ]
    )
    priced = runs.price_account(data).priced

    fire = [line for line in priced.lines if line.service == "fire"]
    assert len(fire) == 1, [(line.kind, line.description, line.amount) for line in fire]
    assert fire[0].amount == Decimal("207.00")
    assert (fire[0].quantity, fire[0].unit, fire[0].unit_price) == (
        Decimal("3"),
        "connection",
        None,
    )
    assert priced.total == Decimal("207.00")


def _line(kind, amount, *, service="trash", taxable=True, quantity=None, unit=None, version="v"):
    return rating_seam.RatedLine(
        kind=kind,
        description=f"{service} - 96 gal cart" if kind == "usage" else f"{service} base charge",
        amount=Decimal(amount),
        taxable=taxable,
        quantity=None if quantity is None else Decimal(quantity),
        unit=unit,
        unit_price=Decimal("15.00") if kind == "usage" else None,
        service=service,
        tariff_version_id=version,
    )


def _bill(*lines):
    total = _sum(lines)
    return rating_seam.RatedBill(
        lines=tuple(lines),
        taxable_subtotal=total,
        tax_total=Decimal("0"),
        fee_total=Decimal("0"),
        total=total,
        currency="USD",
    )


def test_tc5__the_join_keeps_every_total_and_the_other_lines_in_place():
    water = _line("usage", "20.00", service="water", quantity="6", unit="kgal")
    bill = _bill(
        water,
        _line("usage", "30.00", quantity="2", unit="cart"),
        _line("base", "6.00"),
        _line("tax", "1.00", service=None),
    )
    joined = counted_service_line.one_line_per_counted_service(bill, frozenset({"trash"}))

    assert [line.kind for line in joined.lines] == ["usage", "usage", "tax"]
    assert joined.lines[0] is water
    assert joined.lines[1].description == "trash - 2 × 96 gal cart"
    assert joined.lines[1].amount == Decimal("36.00")
    assert (joined.total, joined.taxable_subtotal, joined.tax_total) == (
        bill.total,
        bill.taxable_subtotal,
        bill.tax_total,
    )
    assert _sum(joined.lines) == _sum(bill.lines)


@pytest.mark.parametrize(
    "base",
    [
        _line("base", "6.00", taxable=False),  # a line that disagrees on tax
        _line("base", "6.00", version="other"),  # two provenances
    ],
)
def test_tc6__a_join_that_would_misstate_the_lines_is_not_made(base):
    bill = _bill(_line("usage", "30.00", quantity="2", unit="cart"), base)
    assert counted_service_line.one_line_per_counted_service(bill, frozenset({"trash"})) is bill


def test_tc7__a_metered_service_is_never_joined():
    bill = _bill(
        _line("usage", "20.00", service="water", quantity="6", unit="kgal"),
        _line("base", "8.00", service="water"),
    )
    assert counted_service_line.one_line_per_counted_service(bill, frozenset({"trash"})) is bill
    assert counted_service_line.one_line_per_counted_service(bill, frozenset()) is bill


# ══════════════════════════════════════════════════════════════════════════
# THE ONE-TIME BILL PRINTS BOTH THE WAY THE STORED BILL HOLDS THEM
# ══════════════════════════════════════════════════════════════════════════
def _document(data, priced):
    from apps.billing import one_time, one_time_answer

    return one_time_answer.bill_document(
        priced.lines,
        kind=one_time.KIND_INTERIM,
        period_start=rulings.PERIOD_START,
        period_end=rulings.PERIOD_END,
        currency="USD",
        subtotal=priced.total,
        total=priced.total,
        data=data,
        assets_by_id={"m-1": {"label": "W-1"}, "m-2": {"label": "W-2"}},
    )


def test_tc8__the_answer_prints_the_carts_as_one_per_asset_line(monkeypatch):
    """Contract §2's `per_asset` charge: 2 carts, `$36.00`, one row."""
    data = _carts(monkeypatch)
    doc = _document(data, runs.price_account(data).priced)

    (line,) = [row for row in doc["groups"][0]["lines"] if row["service"] == "trash"]
    assert (line["charge"], line["quantity"], line["unit"], line["amount"]) == (
        "per_asset",
        "2",
        "cart",
        "36.0000",
    )


def test_tc9__the_answer_prints_the_minimum_under_meter_b(monkeypatch):
    """Contract §2's `minimum` charge, on meter B's label: W-1 `$14.00`,
    W-2 `$6.00 + $4.00 = $10.00`."""
    rulings._install(monkeypatch, _minimum_world())
    data = rulings._gather(
        [rulings._water("14", asset_id="m-1"), rulings._water("6", asset_id="m-2")]
    )
    doc = _document(data, runs.price_account(data).priced)

    rows = doc["groups"][0]["lines"]
    assert [(r["asset_label"], r["amount"]) for r in rows if r["charge"] == "minimum"] == [
        ("W-2", "4.0000")
    ]
    by_label: dict = {}
    for row in rows:
        label = row["asset_label"]
        by_label[label] = by_label.get(label, Decimal("0")) + Decimal(row["amount"])
    assert by_label == {"W-1": Decimal("14.0000"), "W-2": Decimal("10.0000")}


# ══════════════════════════════════════════════════════════════════════════
# DEF-BIL-8153 · THE ONE-TIME ANSWER NO LONGER SAYS A TAXABLE FEE IS UNTAXED
# ══════════════════════════════════════════════════════════════════════════
def test_tc10__the_fee_tax_absence_is_gone_from_the_wire():
    """`OQ-812` was ruled and the ❄️ B4.2 addendum re-signed on 2026-09-30
    (RECON $75.00 at 8.25% → $81.19), and the fee-tax lane built it. The
    `unavailable` row telling a clerk a taxable fee *"still charges $0.00 of
    tax"* is DELETED, not reworded. RED on the tip before the fix: the code
    was still in `ONE_TIME_UNAVAILABLE`."""
    from apps.billing import one_time

    codes = {row["code"] for row in one_time.ONE_TIME_UNAVAILABLE}
    assert "a_fee_bill_charges_no_tax_on_a_taxable_charge_code" not in codes
    assert all("$0.00 of tax" not in row["detail"] for row in one_time.ONE_TIME_UNAVAILABLE)
