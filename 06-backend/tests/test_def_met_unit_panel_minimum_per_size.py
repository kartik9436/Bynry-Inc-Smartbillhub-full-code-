# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-MET-8823 — a unit's plan panel showed the rate-schedule
#          VERSION's minimum, a figure billing stopped charging on 2026-10-01
# Rules:   BR-RAT-028 mode (A) AMENDED — PO 2026-10-01, option A, *"A · Minimum
#          per size - this is correct"* (decision log "PER-SIZE MINIMUM BUILT"
#          and "A METER WITH NO RECORDED SIZE GETS NO MINIMUM") · G142 (one
#          version lookup) · B14 rules 31 and 33
# Tests:   this file
# ───────────────────────────────────────────────────────
"""The unit's schedule panel shows the minimum for the size the unit HAS.

Worked figures, Water — Residential: 5/8" `$15.00`, 1" `$25.00`, 2" `$40.00`.
A unit with one 1" water connection shows **$25.00** — the figure
`rating.selectors.pricing_inputs` hands billing for that connection — and never
the version's own `minimum_bill`, which `rating/0053` emptied and billing no
longer reads.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from apps.metering import selectors
from apps.metering import services as metering_services
from apps.rating import models as rating_models
from apps.rating import selectors as rating_selectors

from tests.test_us_met_reads_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_reads_helpers import (
    a_meter,
    make_plan,
    make_premises,
    make_unit,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

MINIMUM = {"W-58": Decimal("15.00"), "W-1": Decimal("25.00"), "W-2": Decimal("40.00")}


def _water_schedule(tenant, *, version_minimum=None, rows=MINIMUM):
    plan = make_plan(tenant, name="Water Residential", services=("water",))
    bound = rating_models.PlanRateSchedule.objects.get(rate_plan_id=plan.id)
    version = rating_models.TariffVersion.objects.create(
        tenant=tenant,
        tariff=bound.tariff,
        model="flat",
        uom="kgal",
        currency="USD",
        minimum_bill=version_minimum,
        effective_from=date(2026, 1, 1),
    )
    for size, minimum in rows.items():
        rating_models.RateSizeRow.objects.create(
            tenant=tenant, tariff_version=version, size_class=size, minimum_bill=minimum
        )
    return plan, bound.tariff


def _unit_with_water_meter(actor, plan, size_class):
    premise = make_premises(actor, address_line="12 Mill Race Rd", services_available=["water"])
    unit = make_unit(actor, premise["id"], label="Unit A", services=["water"])
    a_meter(
        actor,
        asset_no="M-4401",
        service="water",
        uom="kgal",
        unit_id=unit["id"],
        size_class=size_class,
    )
    metering_services.assign_unit_plan(actor, unit["id"], {"tariff_id": str(plan.id)})
    return unit


def _water_floor(unit_id):
    body = selectors.unit_pricing(unit_id)
    return next(row for row in body["minimum_charges"]["schedules"] if row["service"] == "water")


def test_a_1_inch_connection_shows_the_1_inch_minimum(brazos, dana):
    """The reproduction: $25.00, not the version's figure."""
    with tenant_ctx(brazos):
        plan, tariff = _water_schedule(brazos, version_minimum=Decimal("99.00"))
        unit = _unit_with_water_meter(dana, plan, "W-1")
        floor = _water_floor(unit["id"])
        billed = rating_selectors.pricing_inputs(tariff, selectors.seams.tenant_today(), "W-1")

    assert floor["minimum_bill_display"] == "25.00"
    assert Decimal(floor["minimum_bill"]) == billed["minimum_bill"] == Decimal("25.00")
    assert floor["size_label"] == 'Water 1"'
    assert floor["minimum_state"] == "size_minimum"
    # The leftover version figure is not on the panel anywhere.
    assert "99.00" not in str(floor)


def test_a_size_with_no_minimum_shows_no_minimum(brazos, dana):
    with tenant_ctx(brazos):
        plan, _tariff = _water_schedule(brazos, rows={**MINIMUM, "W-34": None})
        unit = _unit_with_water_meter(dana, plan, "W-34")
        floor = _water_floor(unit["id"])

    assert floor["minimum_bill"] is None
    assert floor["minimum_bill_display"] is None
    assert floor["size_label"] == 'Water 3/4"'
    assert floor["minimum_state"] == "size_has_no_minimum"


def test_a_connection_with_no_recorded_size_shows_no_minimum(brazos, dana):
    """PO 2026-10-01: a meter with no recorded size gets no minimum."""
    with tenant_ctx(brazos):
        plan, _tariff = _water_schedule(brazos, version_minimum=Decimal("99.00"))
        unit = _unit_with_water_meter(dana, plan, None)
        floor = _water_floor(unit["id"])

    assert floor["minimum_bill"] is None
    assert floor["minimum_bill_display"] is None
    assert floor["size_label"] is None
    assert floor["minimum_state"] == "no_size_recorded"
