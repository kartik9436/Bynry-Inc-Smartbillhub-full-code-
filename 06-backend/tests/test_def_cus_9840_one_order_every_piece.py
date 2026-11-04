# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-CUS-9840 (PO report 2026-10-06, New Connect step 3 pieces).
# Ruling:   decision log 2026-10-06, "EXTRA SOLAR PANELS ON ONE UNIT: ONE WORK
#           ORDER FOR THE SERVICE, ONE ASSET PER PANEL — PO RULING (a)".
# Rules:    BR-RAT-090 (count or sum what is installed) · CR-063 (fire counts) ·
#           CR-162-BRC10 (activation installs a build's earmarked assets).
# Law 14:   run on PostgreSQL with `--ds=config.settings.pgtest` as well as the
#           default suite — the activation is one transaction.
# ───────────────────────────────────────────────────────
"""**One work order for a unit's service installs EVERY piece of it.**

The PO, ruling (a) on 2026-10-06: *"We can create 1 work order for all panels ;
but … we have to create those many assets and tag them to unit. since we want
to track them and bill them accordingly"*. The worked figure shown: Unit 1 has
three solar panels, 1 kW + 10 kW + 10 kW, and one work order; when it is
complete all three are installed, and the bill counts **21 kW** (× $14.00 =
$294.00 — the price is rating's, not asserted here).

The same for batteries (summed), trash carts and fire lines (counted).

⚠ **WHAT WOULD MAKE THESE PASS WRONGLY** (law 7, habit 2):
  * counting the RESPONSE's `assets_installed` — every asset is read back from
    its own row, by unit and service, with its stage and date;
  * three assets on THREE service points that the activation happens to sweep
    — the case asserts they stand on ONE point (the unit's one service);
  * a build whose pieces were already installed at Create — the case asserts
    all three are In stock with no date before the activation.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from apps.assets import models as asset_models
from apps.metering import connection_activation as activation
from apps.metering import connections as w6
from apps.metering import seams

from tests.test_cr162_new_connection_lifecycle import _complete, _orders, _unit
from tests.test_portal_request_to_active import (  # noqa: F401 — fixtures
    EQUIPMENT_TYPE,
    _ctx,
    _plan,
    cedar,
    clerk,
)
from tests.test_us_cwp_helpers import *  # noqa: F401,F403 — growth_plan · identity_seam

pytestmark = pytest.mark.django_db

#: Each service's pieces on Unit 1, as step 3's `piecesBySize` sends them.
PIECES = {
    "solar": [("SOL-P1", 1), ("SOL-P10", 2)],
    "battery": [("BAT-5", 1), ("BAT-10", 2)],
    "trash": [("CART-96", 2), ("CART-64", 1)],
    "fire": [("FL-6", 1), ("FL-2", 2)],
}
#: What the bill reads off those pieces — a SUM in kW, or a COUNT.
SUMMED = {"solar": Decimal("21"), "battery": Decimal("25")}


def _build(clerk, tenant, service):
    plan = _plan(tenant)
    with _ctx(tenant):
        return w6.commit_new_connect(
            clerk,
            {
                "premises": {
                    "id": None,
                    "address": f"9840 {service.title()} Way",
                    "city": "Austin",
                    "state": "TX",
                    "postal_code": "78701",
                    "premise_type": "single_family",
                    "parcel_ref": None,
                    "read_route": None,
                    "services_available": [service],
                },
                "mode": "our_crew",
                "scope": "new_premise",
                "units_prefix": "Unit",
                "target_activation": None,
                "service_request_id": None,
                "units": [{"label": "Unit 1", "is_common_area": False}],
                "meters": [],
                "unit_services": [
                    {
                        "unit_label": "Unit 1",
                        "service": service,
                        "equipment": [
                            {"type": EQUIPMENT_TYPE[service], "size_class": size, "count": count}
                            for size, count in PIECES[service]
                        ],
                    }
                ],
                "plan_assignments": [{"unit_label": "Unit 1", "tariff_id": str(plan.id)}],
                "create_owner_account": False,
                "owner": {},
                "quote_total": None,
                "occupancy": "vacant_service_off",
                "work_orders": [],
            },
        )


def _pieces(tenant, connection_id, service):
    with _ctx(tenant):
        unit = _unit(tenant, connection_id, "Unit 1")
        return list(
            asset_models.Asset.objects.filter(
                service_point__unit=unit, service_point__service__code=service
            )
            .select_related("status")
            .order_by("asset_no")
        )


@pytest.mark.parametrize("service", sorted(PIECES))
def test_one_work_order_installs_every_piece_of_the_service(cedar, clerk, service):
    built = _build(clerk, cedar, service)
    cid = built["id"]
    expected = sum(count for _size, count in PIECES[service])

    # At Create: one asset per piece, on the unit's ONE service point, none fitted.
    before = _pieces(cedar, cid, service)
    assert len(before) == expected == 3
    assert len({a.service_point_id for a in before}) == 1
    assert {a.status.code for a in before} == {"inventory"}
    assert all(a.install_date is None for a in before)
    assert sorted(a.size_class for a in before) == sorted(
        size for size, count in PIECES[service] for _ in range(count)
    )

    # ONE work order for the unit's service — ruling (a) — and it completes.
    orders = _orders(clerk, cedar, cid, "Unit 1", services=(service,))
    assert len(orders) == 1
    _complete(cedar, [orders[0]["id"]])

    with _ctx(cedar):
        readiness = activation.activation_readiness(cid)
        row = next(r for r in readiness["rows"] if r["service"] == service)
        assert row["ready"] is True
        activation.activate(clerk, cid, service_ids=[row["id"]])

    # EVERY piece is Installed, from the activation's date.
    after = _pieces(cedar, cid, service)
    assert len(after) == 3
    assert {a.status.code for a in after} == {"active"}
    with _ctx(cedar):
        today = seams.tenant_today()
    assert {a.install_date for a in after} == {today}

    # And the bill reads all of them: a SUM of kW, or a COUNT.
    with _ctx(cedar):
        unit = _unit(cedar, cid, "Unit 1")
        codes = seams.billable_asset_size_classes(unit.id, service, today)
        count = seams.billable_asset_count(unit.id, service, today)
    assert count == 3
    assert codes is not None and len(codes) == 3
    if service in SUMMED:
        assert seams.total_installed_capacity(service, list(codes)) == SUMMED[service]


# ── Step 3's *3 panels · 21 kW* reads the ladder the bill reads ─────────────
def test_the_size_list_serves_each_sizes_capacity_from_the_ratified_ladder(growth_plan, identity_seam):
    """`GET /lookups/service_size_classes` carries `capacity` and its unit for a
    service that SUMS, and `null` for one that COUNTS — so step 3 can say
    *21 kW* without a kW typed per size in the screen."""
    from apps.tenancy import api as tenancy_api

    from tests.test_us_ten_helpers import FakeUser, api_call, provisioned_tenant

    tenant, _ = provisioned_tenant()
    response = api_call(
        tenancy_api.lookups,
        "get",
        user=FakeUser(),
        role="billing_clerk",
        tenant=tenant,
        query={"per": 200},
        list_code="service_size_classes",
    )
    assert response.status_code == 200, response.data
    rows = {row["code"]: row for row in response.data["results"]}
    assert (rows["SOL-P10"]["capacity"], rows["SOL-P10"]["capacity_uom"]) == ("10.0000", "kW")
    assert (rows["SOL-P1"]["capacity"], rows["SOL-P1"]["capacity_uom"]) == ("1.0000", "kW")
    assert (rows["BAT-5"]["capacity"], rows["BAT-5"]["capacity_uom"]) == ("5.0000", "kW")
    # Counted, never summed: a cart and a fire line carry no capacity.
    assert (rows["CART-96"]["capacity"], rows["CART-96"]["capacity_uom"]) == (None, None)
    assert (rows["FL-6"]["capacity"], rows["FL-6"]["capacity_uom"]) == (None, None)


# ═══════════════════════════════════════════════════════════════════════════
# THE STATEMENT THE PO SIGNED ON 2026-10-06 ("S9–S13 approve", S11)
# ═══════════════════════════════════════════════════════════════════════════
def test_the_statement_the_po_signed_on_2026_10_06(growth_plan, identity_seam):
    """**SIGNED 2026-10-06 (S11)** — review-ledger AMENDMENT row *"SIGN-OFF
    RECORDED (S11 of S9–S13)"* for `DEF-CUS-9840`; decision log *"S9–S13
    SIGNED"*.

    Shown to the PO, verbatim: *"To show '3 panels · 21 kW' on New Connect, the
    size list now also tells the screen each size's capacity (1 kW, 10 kW). It
    changes no price and no bill."* PO, verbatim: *"S9–S13 approve"*.

    * *"each size's capacity (1 kW, 10 kW)"* — `SOL-P1` serves `1.0000` kW and
      `SOL-P10` `10.0000` kW.
    * *"3 panels · 21 kW"* — 1 + 10 + 10 from the SERVED figures is 21 kW, the
      very sum the bill takes off the same three codes
      (`seams.total_installed_capacity`, `BR-RAT-090`).
    * *"It changes no price and no bill"* — the row carries exactly two keys
      more than the list served before (`capacity`, `capacity_uom`) and every
      other key unchanged; the read writes nothing; and the bill's sum does not
      read the list at all (it is the ladder's, with or without this read).

    NOT carried by the statement, and stays on the agenda: the work-order and
    activation figure on the PENDING row (*"21 kW × $14.00 = $294.00"*) — the
    PO was shown the size list, not the bill.
    """
    from apps.tenancy import api as tenancy_api
    from apps.tenancy import models as tenancy_models
    from apps.tenancy.services import ServiceSizeClassLookupHandler

    from tests.test_us_ten_helpers import FakeUser, api_call, provisioned_tenant, tenant_ctx

    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        before = sorted(
            tenancy_models.MeterSizeClass.objects.filter(tenant_id=tenant.id).values_list("code", "updated_at")
        )
    response = api_call(
        tenancy_api.lookups,
        "get",
        user=FakeUser(),
        role="billing_clerk",
        tenant=tenant,
        query={"per": 200},
        list_code="service_size_classes",
    )
    assert response.status_code == 200, response.data
    rows = {row["code"]: row for row in response.data["results"]}

    # ── "each size's capacity (1 kW, 10 kW)" ──
    assert (rows["SOL-P1"]["capacity"], rows["SOL-P1"]["capacity_uom"]) == ("1.0000", "kW")
    assert (rows["SOL-P10"]["capacity"], rows["SOL-P10"]["capacity_uom"]) == ("10.0000", "kW")

    # ── "3 panels · 21 kW" — the screen's sum is the bill's sum ──
    panels = ["SOL-P1", "SOL-P10", "SOL-P10"]
    on_screen = sum(Decimal(rows[code]["capacity"]) for code in panels)
    assert (len(panels), on_screen) == (3, Decimal("21"))
    with tenant_ctx(tenant):
        assert seams.total_installed_capacity("solar", panels) == on_screen

        # ── "It changes no price and no bill" ──
        handler = ServiceSizeClassLookupHandler()
        for row in tenancy_models.MeterSizeClass.objects.filter(tenant_id=tenant.id, code__in=["SOL-P1", "SOL-P10"]):
            served = handler.serialize(row)
            plain = super(ServiceSizeClassLookupHandler, handler).serialize(row)
            assert set(served) - set(plain) == {"capacity", "capacity_uom"}
            assert {key: served[key] for key in plain} == plain
        after = sorted(
            tenancy_models.MeterSizeClass.objects.filter(tenant_id=tenant.id).values_list("code", "updated_at")
        )
    assert after == before, "the size list is a read; it wrote nothing"
