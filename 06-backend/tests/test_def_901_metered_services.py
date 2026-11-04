# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-901 (PO, 2026-08-27, live app v2.61.1) — read-validation
#          thresholds offered for services that can never produce a reading.
#          PO verbatim: *"are these settings applicable to sewer"*.
# Rules:   BR-TEN-162 (a settings screen offers no configuration this tenant's
#          own estate can never make fire; the test is the ESTATE, never the
#          service code; fail toward SHOWING) · BR-AST-009 (a measuring type
#          declares a service and an explicit UoM) · BR-MET-119 (premises →
#          units → meters: a meter fits only a slot the address offers) ·
#          BR-RAT-015 (sewer is priced as a percentage of the water usage
#          charge) · BR-RAT-090 (an unmetered service's quantity is a COUNT)
# Impacts: apps/assets/selectors.metered_service_codes ·
#          GET /assets/metered-services · SettingsReadValidation.tsx
# ───────────────────────────────────────────────────────
"""DEF-901 — *does this tenant actually meter this service?*

The S64 read-validation page drew a full threshold form per **ENABLED**
service: a high-use threshold, a days window, a zero-read rule and a
`Save Sewer thresholds` button for a service that reads no register at all.
Fourteen inputs of configuration that can never fire, offered for tuning.

**THE TRAP THIS FILE EXISTS TO PIN SHUT** is the fix that looks obvious and is
wrong: a hard-coded list of "unmetered services". Sewer is normally derived
from water and trash is a flat per-cart charge — but a utility that genuinely
meters sewer exists, and on that tenant the form must appear. Every case below
is written against the ESTATE, and `test_a_sewer_meter_makes_sewer_metered` is
the one that fails the hard-coded version.

⚠ **THE GRAIN IS "STANDING ON A SERVICE POINT", AND IT IS THE SCHEMA'S, NOT A
CHOICE.** B2 r4 records an asset's service only through the service point
minted when it is ASSIGNED to a unit, and un-assigning or retiring an asset
releases that seat (`apps/assets/services` sets `service_point = None`). So a
spare in inventory has no service on record — `stock_view`'s own docstring
says the same thing about r10's stock service tag — and a tenant that has
pulled its last sewer meter reads as not metering sewer, which is TRUE of the
readings it will take next cycle. `test_a_spare_in_inventory_is_not_an_estate`
pins that grain so the next reader meets it as a fact rather than a surprise.

RED PROOFS (each broken first, per hard-won law 7 — transcripts in the lane
report):
  · drop `type__code__in=MEASURING_TYPES` from the selector
      → `test_a_trash_cart_does_not_make_trash_metered` goes red: a cart is an
        asset on a trash service point and would make trash "metered".
  · hard-code `{"electric", "water"}` as the metered set
      → `test_a_sewer_meter_makes_sewer_metered` goes red.
"""

import pytest

from apps.assets import selectors as asset_selectors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import (
    make_asset,
    make_premises,
    make_unit,
    provisioned_tenant,
    seed_physical_series,
    staff_actor,
    tenant_ctx,
)
from tests.test_us_ten_helpers import brazosbend_payload

pytestmark = pytest.mark.django_db

#: The four services this defect is argued over. Sewer and trash are here
#: because the PO asked about sewer and because trash is the OTHER service that
#: reads no register — it is billed as a COUNT of carts (BR-RAT-090).
WET_SERVICES = ["water", "sewer", "trash"]


@pytest.fixture()
def wet_utility(growth_plan, identity_seam):  # noqa: F405
    """A utility that SELLS water, sewer and trash — the shape DEF-901 is about.

    Selling a service and metering it are different facts, and this fixture
    exists to keep them apart: every service below is ENABLED, which is the
    only thing the broken page ever asked.
    """
    tenant, _ = provisioned_tenant(
        brazosbend_payload(
            name="Silver Creek Water",
            subdomain="silvercreekwater",
            services=WET_SERVICES,
            owner={
                "full_name": "R. Alvarez",
                "email": "r.alvarez@silvercreekwater.test",
                "password": "An0ther!passw0rd",
                "phone": None,
            },
        )
    )
    seed_physical_series(tenant)
    return tenant


@pytest.fixture()
def rosa(wet_utility):
    return staff_actor(wet_utility, "system_admin", "r.alvarez@silvercreekwater.test")


def a_unit_offering(actor, services, *, address, label="Unit A"):
    """BR-MET-119's chain, built honestly: the ADDRESS offers the services, the
    unit inherits them, and only then may a meter be fitted into one."""
    premises = make_premises(actor, address_line=address, services_available=list(services))
    return make_unit(actor, premises["id"], label=label, services=list(services))


# ══════════════════════════════════════════════════════════════════════════
# The estate is the test (BR-TEN-162 clause 1)
# ══════════════════════════════════════════════════════════════════════════
def test_a_tenant_with_no_assets_meters_nothing(wet_utility, rosa):
    """An EMPTY result is a positive answer — *this register holds no measuring
    asset* — and not a "could not tell". A brand-new tenant looks like this,
    and it is why the screen says so in words instead of drawing nothing."""
    with tenant_ctx(wet_utility):
        assert asset_selectors.metered_service_codes() == []


def test_selling_a_service_is_not_metering_it(wet_utility, rosa):
    """**THE DEFECT IN ONE ASSERTION.** All three services are ENABLED — which
    is the entire test the broken page applied — and none of them is metered."""
    from apps.metering import seams as metering_seams

    with tenant_ctx(wet_utility):
        assert set(metering_seams.enabled_service_codes()) >= set(WET_SERVICES)
        assert asset_selectors.metered_service_codes() == []


def test_a_water_meter_makes_water_metered_and_nothing_else(wet_utility, rosa):
    with tenant_ctx(wet_utility):
        unit = a_unit_offering(rosa, WET_SERVICES, address="12 Cedar Row")
        make_asset(
            rosa,
            asset_no="M-9001",
            service="water",
            unit="kgal",
            unit_id=unit["id"],
            install_date="2026-01-05",
        )
        assert asset_selectors.metered_service_codes() == ["water"]


def test_a_trash_cart_does_not_make_trash_metered(wet_utility, rosa):
    """BR-RAT-090: three carts on a unit bill as a COUNT of three carts. A cart
    is an asset and produces no reading, so no threshold could ever judge one.

    ⚠ This is the case a naive *"has any asset on this service"* read gets
    wrong, and it is why the selector filters on MEASURING_TYPES first.
    """
    with tenant_ctx(wet_utility):
        unit = a_unit_offering(rosa, WET_SERVICES, address="14 Cedar Row")
        make_asset(
            rosa,
            type="container_cart",
            asset_no="C-7001",
            service="trash",
            unit=None,
            unit_id=unit["id"],
            install_date="2026-01-05",
        )
        assert "trash" not in asset_selectors.metered_service_codes()


def test_a_sewer_meter_makes_sewer_metered(wet_utility, rosa):
    """**THE RULE IS NOT "sewer never has meters".**

    Sewer is normally a percentage of the water usage charge (BR-RAT-015) and
    reads no register — but a utility that genuinely meters it exists, and on
    that tenant the thresholds are real configuration a clerk must be able to
    reach. Hard-coding a set of unmetered service codes passes every other case
    in this file and fails this one, which is exactly what it is here for.
    """
    with tenant_ctx(wet_utility):
        unit = a_unit_offering(rosa, WET_SERVICES, address="16 Cedar Row")
        make_asset(
            rosa,
            asset_no="M-9002",
            service="sewer",
            unit="kgal",
            unit_id=unit["id"],
            install_date="2026-01-05",
        )
        assert "sewer" in asset_selectors.metered_service_codes()


def test_a_spare_in_inventory_is_not_an_estate(wet_utility, rosa):
    """THE GRAIN, PINNED. B2 r4 records an asset's service only through the
    service point minted at ASSIGNMENT, so a meter that has never stood
    anywhere carries no service and cannot make one metered. Asserted rather
    than left to be discovered, because it is the one case where the answer
    surprises a reader who expects "does this tenant own a sewer meter"."""
    with tenant_ctx(wet_utility):
        make_asset(rosa, asset_no="M-9003", service="sewer", unit="kgal")
        assert asset_selectors.metered_service_codes() == []


def test_result_is_sorted_and_deduplicated(wet_utility, rosa):
    with tenant_ctx(wet_utility):
        unit = a_unit_offering(rosa, WET_SERVICES, address="18 Cedar Row")
        second = a_unit_offering(rosa, WET_SERVICES, address="20 Cedar Row", label="Unit B")
        make_asset(
            rosa,
            asset_no="M-9004",
            service="water",
            unit="kgal",
            unit_id=unit["id"],
            install_date="2026-01-05",
        )
        make_asset(
            rosa,
            asset_no="M-9005",
            service="water",
            unit="kgal",
            unit_id=second["id"],
            install_date="2026-01-05",
        )
        make_asset(
            rosa,
            asset_no="M-9006",
            service="sewer",
            unit="kgal",
            unit_id=unit["id"],
            install_date="2026-01-05",
        )
        assert asset_selectors.metered_service_codes() == ["sewer", "water"]


# ══════════════════════════════════════════════════════════════════════════
# The wire (GET /assets/metered-services)
# ══════════════════════════════════════════════════════════════════════════
def test_endpoint_serves_the_estate(wet_utility, rosa):
    from apps.assets import api

    with tenant_ctx(wet_utility):
        unit = a_unit_offering(rosa, WET_SERVICES, address="22 Cedar Row")
        make_asset(
            rosa,
            asset_no="M-9007",
            service="water",
            unit="kgal",
            unit_id=unit["id"],
            install_date="2026-01-05",
        )
    response = api_call(  # noqa: F405
        api.asset_metered_services,
        "get",
        user=FakeUser(),  # noqa: F405
        role="system_admin",
        tenant=wet_utility,
    )
    assert response.status_code == 200
    assert response.data == {"services": ["water"]}
