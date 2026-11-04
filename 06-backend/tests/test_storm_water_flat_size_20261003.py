"""Storm water's seeded size "Flat" = 2 ERU (PO ruling 2026-10-03, option A).

PO verbatim: *"A Keep charging per unit, and add a size for a single flat, e.g.
"Flat" = 2 ERU"*. Worked figure shown to the PO: 3 flats × "Apartment building"
6 ERU × $4.50 = $81.00; 3 flats × "Flat" 2 ERU × $4.50 = $27.00.

Asserted: the seed carries it at 2 ERU (and nothing else moved), and
`tenancy/0058` gives it to an existing tenant ONLY where that tenant's
storm-water list is still the untouched seed.
"""

from __future__ import annotations

import importlib
from decimal import Decimal

import pytest
from django.apps import apps as global_apps

from apps.tenancy import models as tenancy_models
from apps.tenancy import service_size_classes as ssc

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

SEEDED = {
    "SW-SF": "Single-family home",
    "SW-DUP": "Two-unit home",
    "SW-APT": "Apartment building",
    "SW-COM-S": "Small commercial",
    "SW-COM-L": "Large commercial",
}


def _migration():
    return importlib.import_module("apps.tenancy.migrations.0058_storm_water_flat_size")


def test_flat_is_seeded_at_two_eru_and_the_other_five_did_not_move():
    rows = {row.code: (row.name, row.capacity) for row in ssc.size_class_records_for_service("storm_water")}
    assert rows["SW-FLAT"] == ("Flat", Decimal(2))
    assert ssc.capacity_of("storm_water", "SW-FLAT") == Decimal(2)
    for code, name in SEEDED.items():
        assert rows[code][0] == name
    assert rows["SW-APT"][1] == Decimal(6)
    # The worked figure: per unit, at the $4.50 an ERU the PO was shown.
    per_eru = Decimal("4.50")
    assert 3 * ssc.capacity_of("storm_water", "SW-FLAT") * per_eru == Decimal("27.00")
    assert 3 * ssc.capacity_of("storm_water", "SW-APT") * per_eru == Decimal("81.00")


def _as_old_seed(tenant_id):
    """The tenant's storm-water list exactly as seeded before 2026-10-03."""
    service = tenancy_models.Service.objects.get(code="storm_water")
    size = tenancy_models.MeterSizeClass.objects
    size.filter(tenant_id=tenant_id, code__iexact="SW-FLAT").delete()
    size.filter(tenant_id=tenant_id, service=service).exclude(code__in=list(SEEDED)).delete()
    for code, name in SEEDED.items():
        size.update_or_create(
            tenant_id=tenant_id,
            code=code,
            defaults={"name": name, "service": service, "is_system": True, "active": True},
        )


def _flat(tenant_id):
    return tenancy_models.MeterSizeClass.objects.filter(tenant_id=tenant_id, code="SW-FLAT").first()


def test_an_untouched_storm_water_list_gains_flat_once(brazos):
    with tenant_ctx(brazos):
        _as_old_seed(brazos.id)
        assert _migration().add_flat_for_tenant(global_apps, brazos.id) == "added"
        row = _flat(brazos.id)
        assert (row.name, row.service.code, row.is_system, row.active) == (
            "Flat",
            "storm_water",
            True,
            True,
        )
        # A replay adds nothing.
        assert _migration().add_flat_for_tenant(global_apps, brazos.id) == "skipped"


def test_a_utility_that_edited_its_storm_water_list_is_left_alone(brazos):
    with tenant_ctx(brazos):
        _as_old_seed(brazos.id)
        tenancy_models.MeterSizeClass.objects.filter(tenant_id=brazos.id, code="SW-APT").update(
            name="Apartment block"
        )
        assert _migration().add_flat_for_tenant(global_apps, brazos.id) == "left_edited"
        assert _flat(brazos.id) is None
