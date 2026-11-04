# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-CUS-10051 — move-out step 2, every service on the unit grouped
#           by billing basis (PO 2026-10-11, *"this is correct"*).
# Rules:    BR-TEN-1180 · BR-RAT-015 · BR-RAT-090 · B14 rule 31
# Tests:    this file
# ───────────────────────────────────────────────────────
"""``GET /units/{id}/move-out-services`` — one unit carrying a METERED water
meter, a SHARE sewer at 80% of water usage, and two CAPACITY trash carts.

⚠ **WHAT WOULD MAKE THESE PASS WRONGLY** (law 7, habit 2):

  * **A share that passes because it is metered.** Sewer is declared ``share``
    on the tenant and asserted ABSENT from the metered group, and its percent is
    the schedule's stored ``80``, not a constant.
  * **A cart counted as a meter.** The carts are asserted absent from the
    metered group's ``asset_nos`` and present, counted 2, under capacity.
  * **A size printed as a code.** ``size_name`` must be the tenant's NAME.
"""

from datetime import date
from decimal import Decimal

import pytest
from django.urls import resolve

from apps.customers import move_in_flow_api, move_out_services_read

from tests.test_us_met_reads_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_reads_helpers import (  # noqa: F401
    a_meter,
    make_premises,
    make_unit,
    seed_config,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


def _declare(tenant, service, basis):
    from apps.tenancy import models as tenancy_models

    tenancy_models.TenantService.objects.filter(tenant=tenant, service__code=service).update(
        billing_basis=basis, enabled=True
    )


def _plan_with_sewer_share(tenant):
    """A published plan binding water and sewer; sewer's version is 80% of
    water USAGE, in force from 2026-01-01."""
    from apps.rating import models as rating_models
    from apps.tenancy import models as tenancy_models

    plan, _ = rating_models.RatePlan.objects.get_or_create(
        tenant=tenant, name="DEF-CUS-10051", defaults={"code": "def-10051", "status": "published"}
    )
    water = tenancy_models.Service.objects.get(code="water")
    sewer = tenancy_models.Service.objects.get(code="sewer")
    for service in (water, sewer):
        tariff, _ = rating_models.Tariff.objects.get_or_create(
            tenant=tenant, name=f"10051 {service.code}", service=service
        )
        rating_models.PlanRateSchedule.objects.get_or_create(
            tenant=tenant, rate_plan=plan, service=service, defaults={"tariff": tariff}
        )
        if service.code == "sewer":
            rating_models.TariffVersion.objects.create(
                tenant=tenant,
                tariff=tariff,
                model="percent_of_service",
                currency="USD",
                uom="kgal",
                percent=Decimal("80"),
                basis_service=water,
                percent_basis="usage",
                effective_from=date(2026, 1, 1),
            )
    return plan


def _world(actor, tenant):
    from apps.assets import services as asset_services
    from apps.metering import services as metering_services

    _declare(tenant, "water", "metered")
    _declare(tenant, "sewer", "share")
    _declare(tenant, "trash", "capacity")
    services = ["water", "sewer", "trash"]
    premises = make_premises(actor, services_available=services)
    unit = make_unit(actor, premises["id"], label="Unit 7", services=services)
    plan = _plan_with_sewer_share(tenant)
    metering_services.assign_unit_plan(actor, unit["id"], {"tariff_id": str(plan.id)})
    a_meter(actor, "W-5042", unit_id=unit["id"], service="water", uom="kgal")
    for n in (1, 2):
        asset_services.create_asset(
            actor,
            {
                "type": "container_cart",
                "asset_no": f"CART-{n:04d}",
                "service": "trash",
                "size_class": "CART-96",
                "unit_id": str(unit["id"]),
                "install_date": "2026-01-05",
            },
        )
    return unit


def test_the_route_resolves_through_the_root_urlconf():
    uid = "0190a1b2-0000-7000-8000-000000000001"
    assert (
        resolve(f"/api/brazos/units/{uid}/move-out-services").func
        is move_in_flow_api.unit_move_out_services
    )


def test_every_service_on_the_unit_grouped_by_billing_basis(brazos, dana):
    with tenant_ctx(brazos):
        seed_config()
        unit = _world(dana, brazos)
        answer = move_out_services_read.services_by_basis(unit["id"], date(2026, 10, 31))

    assert answer["as_of"] == "2026-10-31"
    assert {row["service"]: row["billing_basis"] for row in answer["services"]} == {
        "water": "metered",
        "sewer": "share",
        "trash": "capacity",
    }
    # METERED — water's meter, and nothing else.
    assert answer["metered"] == [{"service": "water", "asset_nos": ["W-5042"]}]
    # SHARE — sewer at the schedule's stored 80, of water usage, from W-5042.
    [sewer] = answer["share"]
    assert sewer["service"] == "sewer"
    assert Decimal(sewer["percent"]) == Decimal("80")
    assert sewer["percent_basis"] == "usage"
    assert sewer["basis_service"] == "water"
    assert sewer["source_asset_nos"] == ["W-5042"]
    assert sewer["terms_absent"] is None
    # CAPACITY — two 96-gallon carts, counted, named (never the code).
    [carts] = answer["capacity"]
    assert carts["service"] == "trash"
    assert carts["count"] == 2
    assert sorted(carts["asset_nos"]) == ["CART-0001", "CART-0002"]
    assert carts["size_class"] == "CART-96"
    assert carts["size_name"] and carts["size_name"] != "CART-96"


def test_a_share_with_no_plan_states_the_absence_and_invents_no_percent(brazos, dana):
    with tenant_ctx(brazos):
        seed_config()
        _declare(brazos, "water", "metered")
        _declare(brazos, "sewer", "share")
        premises = make_premises(dana, services_available=["water", "sewer"])
        unit = make_unit(dana, premises["id"], label="Unit 8", services=["water", "sewer"])
        answer = move_out_services_read.services_by_basis(unit["id"], date(2026, 10, 31))
    [sewer] = answer["share"]
    assert sewer["percent"] is None
    assert sewer["terms_absent"] == "unit_has_no_plan"


def test_the_door_answers_and_refuses_a_malformed_date(brazos, dana):
    from tests.test_us_met_helpers import FakeUser, api_call

    with tenant_ctx(brazos):
        seed_config()
        unit = _world(dana, brazos)
    ok = api_call(
        move_in_flow_api.unit_move_out_services,
        "get",
        user=FakeUser(dana.id),
        role="billing_clerk",
        tenant=brazos,
        query={"as_of": "2026-10-31"},
        unit_id=unit["id"],
    )
    assert ok.status_code == 200, ok.data
    assert ok.data["as_of"] == "2026-10-31"
    assert [row["service"] for row in ok.data["capacity"]] == ["trash"]
    bad = api_call(
        move_in_flow_api.unit_move_out_services,
        "get",
        user=FakeUser(dana.id),
        role="billing_clerk",
        tenant=brazos,
        query={"as_of": "31/10/2026"},
        unit_id=unit["id"],
    )
    assert bad.status_code == 422
    assert bad.data["message_key"] == "customers.account.date_invalid"
