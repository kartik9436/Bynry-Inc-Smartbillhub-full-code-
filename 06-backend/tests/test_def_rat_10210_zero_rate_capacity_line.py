# ── Trace ──────────────────────────────────────────────
# Ruling:  12-governance/02-decision-log.md, 2026-10-17 — "A $0.00 CAPACITY
#          LINE IS LEFT OFF THE BILL; MUNICIPAL SOLAR IS SETUP, NOT CODE"
#          (PO: "please start these changes", read as yes to option B).
# Defect:  DEF-RAT-10210
# Code:    apps/rating/pricing/stages/price_usage.py (🔒)
# ───────────────────────────────────────────────────────
"""**A CAPACITY LINE PRICED AT A $0 RATE IS NOT ON THE BILL.**

A utility that charges solar or battery a flat monthly fee states the fee as
the base charge code (`BASE-SOL $25.00`) and the per-kW rate as `$0`. Before
this change every such bill printed `solar 6 kW × $0.00 = $0.00` beside the
real $25.00. The PO ruled the $0.00 line off the bill and the portal; the
base charge and the tax do not move.

WHAT DECIDES IT — THE RATE, NOT THE AMOUNT. A line is left off only when the
RATE it was priced at is exactly zero. A real rate times zero installed
kilowatts still prints (`0 kW × $4.00 = $0.00`, case 6) — that line tells a
clerk the equipment sums to zero, which is a fact worth seeing, and nothing in
the ruling hides it. A unit whose equipment has no recorded size is still
refused before pricing (`installed_capacity_unresolved`, case 4), which is the
ruling's *"installed equipment must still be recorded on each unit"*.

RED FIRST: cases 1 and 5 failed on the tip `73ca85ccb` (the bill held a second
solar line `6 kW @ $0.00 = $0.00`; the stage emitted the zero line). Cases 2,
4, 6 and 7 were green before and stay green: they are the discriminators that
prove the change hides nothing else.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from apps.billing import models as billing_models
from apps.billing import gather, runs
from apps.rating import models as rating_models
from apps.rating import services as rating_services
from apps.rating.pricing import contracts
from apps.rating.pricing.stages import price_usage

from tests.test_capacity_base_by_size import _calculate, _lines, _prepare
from tests.test_cr062_d1_installed_capacity_sums import _world
from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import tenant_ctx

AUG_START, AUG_END = date(2026, 8, 1), date(2026, 8, 31)


@pytest.fixture(autouse=True)
def _the_unit_bills_on_a_cycle(monkeypatch):
    """`BR-BIL-1066` needs the unit's cycle NAME; supplied through the seam, as
    `test_capacity_base_by_size.py` does. No figure here moves."""
    from apps.metering import selectors as _metering_selectors

    monkeypatch.setattr(
        _metering_selectors,
        "cycle_terms_for_unit",
        lambda unit_id: {"code": "C-01", "name": "Cycle 1", "due_days": 21},
    )


def _solar_world(dana, brazos, tag, *, per_kw, base, specs, tax):
    cycle, _unit, _account = _world(
        dana, brazos, cycle_code=tag, code="solar", kind="pv", uom="kW", rate=per_kw, specs=specs
    )
    rating_models.Charge.objects.filter(tenant=brazos, is_base=True, service__code="solar").update(
        amount=base
    )
    if tax:
        jurisdiction = rating_models.TaxJurisdiction.objects.create(
            tenant=brazos, name=f"Town {tag}", authority=f"Town {tag}"
        )
        levy = rating_models.Tax.objects.create(
            tenant=brazos,
            jurisdiction=jurisdiction,
            name=f"Town {tag} tax",
            kind="percent",
            rate=Decimal("0.04"),
        )
        plan = rating_models.RatePlan.objects.get(tenant=brazos, name="solar only")
        rating_services.attach_tax_to_plan(
            dana, plan.id, {"tax": str(levy.id), "reason": "DEF-RAT-10210"}
        )
    return cycle


def _solar_bill(dana, brazos, tag, *, per_kw, base, specs=("SOL-P2", "SOL-P4"), tax=True):
    """`specs` panels (SOL-P2 = 2 kW + SOL-P4 = 4 kW → 6 kW), priced `per_kw`
    per kW, BASE-SOL flat `base`, a 4% tax attached to the plan."""
    with tenant_ctx(brazos):
        cycle = _solar_world(dana, brazos, tag, per_kw=per_kw, base=base, specs=specs, tax=tax)
        prepared = _prepare(cycle)
        assert prepared.ready, [
            (getattr(b, "reason", None), str(getattr(b, "detail", b))[:200])
            for b in prepared.blocked
        ]
        invoice = _calculate(brazos, cycle, prepared.ready[0], tag.lower())
        lines = _lines(invoice, "solar")
        taxes = [line for line in invoice.lines.all() if line.kind == "tax"]
        return invoice, lines, taxes


# (1) ─────────────────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_1__a_zero_rate_solar_bill_carries_the_base_only(brazos, dana):
    """6 kW on a $0/kW schedule, BASE-SOL $25.00, 4% tax → ONE solar line
    $25.00, NO $0.00 capacity line, tax $1.00 on $25.00, total $26.00."""
    invoice, lines, taxes = _solar_bill(
        dana, brazos, "Z0-1", per_kw=Decimal("0"), base=Decimal("25.00")
    )
    assert [(line.kind, line.amount) for line in lines] == [("base", Decimal("25.000000"))]
    assert sum(t.amount for t in taxes) == Decimal("1.000000")
    assert invoice.total == Decimal("26.00")


# (2) ─────────────────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_2__a_four_dollar_schedule_still_prints_six_kw_times_four(brazos, dana):
    """The Municipal Solar shape: 6 kW × $4.00 = $24.00 + $10.00 base + 4% tax
    $1.36 = **$35.36**. Unchanged by this change."""
    invoice, lines, taxes = _solar_bill(
        dana, brazos, "Z0-2", per_kw=Decimal("4.00"), base=Decimal("10.00")
    )
    usage = [line for line in lines if line.kind == "usage"]
    base = [line for line in lines if line.kind == "base"]
    assert [(u.quantity, u.unit, u.unit_price, u.amount) for u in usage] == [
        (Decimal("6.000000"), "kW", Decimal("4.000000"), Decimal("24.000000"))
    ]
    assert [b.amount for b in base] == [Decimal("10.000000")]
    assert sum(t.amount for t in taxes) == Decimal("1.360000")
    assert invoice.total == Decimal("35.36")


# (4) ─────────────────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_4__equipment_with_no_recorded_size_is_still_refused_at_a_zero_rate(brazos, dana):
    """A panel whose size was never recorded cannot be summed: the account is
    still held before pricing, though the rate is $0 — hiding the line must
    not let a unit with unknown equipment bill silently."""
    with tenant_ctx(brazos):
        cycle = _solar_world(
            dana,
            brazos,
            "Z0-4",
            per_kw=Decimal("0"),
            base=Decimal("25.00"),
            specs=(None,),
            tax=False,
        )
        with pytest.raises(gather.GatherProblem, match="INSTALLED CAPACITY"):
            prepared = _prepare(cycle)
            assert prepared.ready, "held at prepare — fine, but then nothing below runs"
            run = billing_models.BillRun.objects.create(
                tenant=brazos,
                cycle=cycle,
                period_start=AUG_START,
                period_end=AUG_END,
                idempotency_key="z0-4",
            )
            runs.calculate_account(prepared.ready[0], bill_run=run, service_date=AUG_END)


# ── the engine stage itself ───────────────────────────────────────────────────
def _stage_lines(*, rate, units, model="flat", installed_sum_line=True):
    """Price one solar service through stage 3 directly, whole month."""
    config = contracts.ModelConfig(
        model=model,
        billed_unit="kW",
        unit_price=rate if model == "flat" else None,
        capacity=(
            contracts.CapacitySpec(unit_label="kW", rate_per_unit=rate)
            if model == "capacity"
            else None
        ),
        base_charge=Decimal("25"),
        installed_sum_line=installed_sum_line and model != "capacity",
    )
    source = contracts.NormalizedInput(
        subscription=contracts.SubscriptionContext(service="solar", currency="USD"),
        usage=contracts.MeasuredUsage(
            billed_quantity=units, unit="kW", raw_quantity=units, multiplier=Decimal("1")
        ),
        config=config,
        period=contracts.PeriodShape(cycle_days=31, service_days=31, factor=Decimal(1)),
    )
    priced = price_usage.price_usage(source)
    return priced.usage_lines, priced.base_lines


# (5) ─────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("model", ["flat", "capacity"])
def test_5__the_stage_drops_a_zero_rate_capacity_line(model):
    usage, base = _stage_lines(rate=Decimal("0"), units=Decimal("6"), model=model)
    assert usage == ()
    assert [b.amount for b in base] == [Decimal("25")]


# (6) ─────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("model", ["flat", "capacity"])
def test_6__zero_kw_at_a_real_rate_prints_and_six_kw_at_four_prints(model):
    """Documented: only a $0 RATE hides the line. 0 kW × $4.00 = $0.00 STILL
    prints, so a clerk sees equipment that sums to zero."""
    zero_kw, _ = _stage_lines(rate=Decimal("4"), units=Decimal("0"), model=model)
    assert [(line.quantity, line.unit_price, line.amount) for line in zero_kw] == [
        (Decimal("0"), Decimal("4"), Decimal("0"))
    ]
    six_kw, _ = _stage_lines(rate=Decimal("4"), units=Decimal("6"), model=model)
    assert [(line.quantity, line.unit_price, line.amount) for line in six_kw] == [
        (Decimal("6"), Decimal("4"), Decimal("24"))
    ]


# (7) ─────────────────────────────────────────────────────────────────────────
def test_7__a_metered_zero_rate_line_is_not_a_capacity_line_and_stays():
    """A flat METERED tariff at $0 (no `installed_sum_line`, no capacity
    spec) is outside the ruling and is emitted exactly as before."""
    usage, _ = _stage_lines(
        rate=Decimal("0"), units=Decimal("6"), model="flat", installed_sum_line=False
    )
    assert [(line.amount, line.unit_price) for line in usage] == [(Decimal("0"), Decimal("0"))]
