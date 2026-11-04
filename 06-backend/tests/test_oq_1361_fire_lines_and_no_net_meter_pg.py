# ── Trace ──────────────────────────────────────────────
# Rulings: PO 2026-10-02, decision log "THREE PO RULINGS IN ONE MESSAGE" —
#          (2) *"A · A fire service gets a "fire line" item with a size (2" to
#          10"), like a trash cart. The clerk picks the size on New
#          Connection."* (`OQ-1361`, fire-line half CLOSED) · (3) *"we are not
#          doing net metering right now - we are doing capacity based panel -
#          A · The net meter doesn't count toward capacity. Capacity is the
#          panels or battery only."* (`DEF-MET-9037`)
# Rules:   BR-AST-042 (the fire line is a counted, sized asset type) ·
#          BR-RAT-090 (a counted service bills the count per size) · CR-062 D1
#          (solar and battery bill the SUM of their kW) · BR-MET-112 (the
#          build is one commit) · hard-won law 14 (run on PostgreSQL:
#          `--ds=config.settings.pgtest`)
# Code:    apps/metering/connections.py (`_commit_unit_services`, the meter
#          loop's capacity-service skip) · apps/assets/selectors.py 🔒
#          (`billable_asset_count` / `billable_asset_size_classes` leave a
#          reading device out of the counted/summed population)
# ───────────────────────────────────────────────────────
"""**A NEW CONNECTION'S FIRE LINES BILL `$84.00`; A SOLAR BUILD FITS NO NET
METER AND BILLS `12 kW`; AN OLD NET METER NEVER STOPS A BILL.**

Every case starts at New Connect's ONE commit door (`commit_new_connect`) with
the payload the browser sends, stands the equipment up the way a crew would,
opens an account and runs a real bill through `runs.prepare_run` and
`runs.calculate_account` — and reads the invoice back.

⚠ **"INSTALLED" IS A FIXTURE STEP, SAID OUT LOUD.** The commit creates every
piece `installed=False` (PO 2026-09-21) and work-order completion is what
installs it; that door is `DEF-AST-5443`'s and is not built. So each case moves
the pieces to *Installed* by hand, dated before the period, which is exactly the
state a completed job leaves.

⚠ **AND THE BUILD IS ACTIVATED, THROUGH THE PRODUCT'S OWN DOOR (`DEF-BIL-9809`).**
`CR-162-BRC10` (PO 2026-10-02: *"the account opens, but billing waits until
the unit is activated"*) made a not-yet-activated build's unit DARK for billing
(`customers.activation_windows`). This file predates it and never activated,
so from `728fe0248` both new-connection cases billed `$0.00` — the right answer
for a unit nobody switched on. Each case now calls `connection_activation.
activate` and dates the activation at `INSTALL`, before the period; the
activation DAY is the one other thing set by hand.

⚠ **WHAT WOULD MAKE THESE PASS WRONGLY** (law 7, habit 2):
  * asserting the total alone — `$84.00` could be `3 × $28.00`; the case also
    asserts three pieces, their sizes, and ONE fire line of quantity 3;
  * a solar bill that passes because the net meter was never installed — the
    meter in case 3 is INSTALLED and IN SERVICE on the solar point, the exact
    state that refused the bill;
  * a skip that also drops the panels — case 2 asserts the three panels exist.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from apps.assets import models as asset_models
from apps.assets import services as asset_services
from apps.customers import models as customer_models
from apps.customers import services as customer_services
from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from apps.metering import models as metering_models
from apps.tenancy import services as tenancy_services

from tests.test_br_cus_068_master_bill import _by_service, _cycle
from tests.test_cr062_d1_installed_capacity_sums import (
    PER_KW,
    _base_charge_code,
    _declare_capacity,
    _plan_priced_per,
)
from tests.test_cr062_d1_installed_capacity_sums import _bill as _bill_solar
from tests.test_cr062_d1_installed_capacity_sums import _world as _solar_world
from tests.test_cr063_c3_fire_priced import (
    MIXED_PROPERTY,
    _assert_capacity_basis,
    _bill,
    _describe,
    _fire_lines,
    _fire_plan,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import seed_physical_series, tenant_ctx

pytestmark = pytest.mark.django_db

INSTALL = date(2026, 1, 5)
AUG_START = date(2026, 8, 1)

#: 3 panels × 4 kW. The figure the coordinator's brief and the ruling name.
TWELVE_KW = Decimal("12.000000")
#: 12 kW × $14.00 a kW (CR-062 E3's PO rate) — the solar line and the bill.
TWELVE_KW_BILL = Decimal("168.00")


def _payload(*, address, services, unit_services, plan_id, meters=()):
    """The payload `commitPlanOf` emits, keys and spellings both."""
    return {
        "premises": {
            "id": None,
            "address": address,
            "city": "Katy",
            "state": "TX",
            "postal_code": "77494",
            "premise_type": None,
            "parcel_ref": None,
            "read_route": None,
            "services_available": list(services),
        },
        "mode": "our_crew",
        "scope": "new_premise",
        "units_prefix": "Unit",
        "target_activation": None,
        "service_request_id": None,
        "connection_id": None,
        "units": [{"label": "Unit 1", "is_common_area": False}],
        "meters": list(meters),
        "unit_services": unit_services,
        "plan_assignments": [{"unit_label": "Unit 1", "tariff_id": str(plan_id)}],
        "create_owner_account": False,
        "owner": {},
        "quote_total": None,
        "occupancy": "vacant_service_off",
        "work_orders": [],
    }


def _activate_build(actor, connection_id):
    """Approve-and-switch-on, as the clerk does on the build's page — then date
    it at `INSTALL` so the whole August period is served (the CR-162 lifecycle
    test dates its activation the same way)."""
    from datetime import datetime, timezone as dt_timezone

    from apps.metering import connection_activation as activation

    ready = activation.activation_readiness(connection_id)["ready_ids"]
    assert ready, "nothing on the build is ready to activate"
    activation.activate(actor, connection_id, service_ids=ready, acknowledge_open_orders=True)
    work_tables.ConnectionService.objects.filter(pk__in=ready).update(
        activated_at=datetime(INSTALL.year, INSTALL.month, INSTALL.day, 15, tzinfo=dt_timezone.utc)
    )


def _built_unit(connection_id):
    connection = work_tables.Connection.objects.get(pk=connection_id)
    return metering_models.Unit.objects.get(premises_id=connection.premises_id, label="Unit 1")


def _pieces(unit, service):
    return list(
        asset_models.Asset.objects.filter(
            service_point__unit=unit, service_point__service__code=service
        ).order_by("asset_no")
    )


def _install(pieces):
    """The crew's visit — what a completed job leaves (see the module note)."""
    active = asset_models.AssetLifecycleStage.objects.get(tenant_id=pieces[0].tenant_id, code="active")
    ids = [piece.id for piece in pieces]
    asset_models.Asset.objects.filter(id__in=ids).update(status=active, install_date=INSTALL)
    asset_models.AssetAssignment.objects.filter(asset_id__in=ids).update(from_date=INSTALL)


def _open_account(actor, tenant, unit, cycle, name):
    metering_models.ServicePoint.objects.filter(tenant=tenant, unit_id=unit.id).update(cycle=cycle)
    created = customer_services.create_account(
        actor,
        {
            "unit_id": str(unit.id),
            "account_type": "residential",
            "opened_at": AUG_START.isoformat(),
            "contact": {"full_name": name, "phone": "555-0177"},
            "customer": {
                "display_name": name,
                "kind": "person",
                "identity": {"phone": "555-0177"},
            },
            "addresses": [
                {"kind": "mailing", "line1": "1 Hose Reel Rd", "city": "Katy", "state": "TX"}
            ],
        },
    )
    customer_services.activate_account(actor, created["id"])
    return customer_models.Account.objects.get(pk=created["id"])


# ══════════════════════════════════════════════════════════════════════════
# (1) FIRE — 1 × 6" + 2 × 2" picked on New Connection bills ONE $84.00 line
# ══════════════════════════════════════════════════════════════════════════
def test_a_new_connection_with_three_fire_lines_bills_84_on_one_fire_line(brazos, dana):
    """**`1 × $60.00 + 2 × $12.00 = $84.00`, at the SEEDED prices, on ONE fire
    line of 3 connections** (PO 2026-09-30 *"per service"*).

    The equipment is what step 3 sends for a fire row of 1 × 6" with a second
    row of 2 × 2" — `[{fire_line, FL-6, 1}, {fire_line, FL-2, 2}]` — and the
    commit makes **three** fire lines, numbered `FS-`, sized, NOT installed.
    """
    with tenant_ctx(brazos):
        seed_physical_series(brazos)
        tenancy_services.update_tenant_service(dana, "fire", {"enabled": True})
        _assert_capacity_basis(brazos, "fire")
        plan = _fire_plan(brazos, dana)
        built = w6.commit_new_connect(
            dana,
            _payload(
                address="12 Hose Reel Rd",
                services=["fire"],
                plan_id=plan.id,
                unit_services=[
                    {
                        "unit_label": "Unit 1",
                        "service": "fire",
                        "equipment": [
                            {"type": "fire_line", "size_class": "FL-6", "count": 1},
                            {"type": "fire_line", "size_class": "FL-2", "count": 2},
                        ],
                    }
                ],
            ),
        )
        assert built["sized_equipment"] == 3, built
        unit = _built_unit(built["id"])
        lines = _pieces(unit, "fire")
        assert sorted(piece.size_class for piece in lines) == ["FL-2", "FL-2", "FL-6"]
        assert {piece.type.code for piece in lines} == {"fire_line"}
        assert all(piece.asset_no.startswith("FS-") for piece in lines), [
            piece.asset_no for piece in lines
        ]
        # Numbered and NOT installed — nobody has been to site (PO 2026-09-21).
        assert all(piece.install_date is None for piece in lines)
        assert {piece.status.code for piece in lines} == {"inventory"}

        _install(lines)
        _activate_build(dana, built["id"])
        cycle = _cycle(brazos, "FIRE-NC")
        _open_account(dana, brazos, unit, cycle, "Ines Okafor")
        invoice = _bill(brazos, cycle, "oq1361-fire-nc")

        fire = _fire_lines(invoice)
        assert len(fire) == 1, f"one fire line per service, got {_describe(invoice)}"
        ((amount, quantity, unit_word),) = fire
        assert amount == MIXED_PROPERTY == Decimal("84.00")
        assert (quantity, unit_word) == (Decimal("3.000000"), "connection")
        assert invoice.total == Decimal("84.00"), _describe(invoice)


# ══════════════════════════════════════════════════════════════════════════
# (2) SOLAR — 3 × 4 kW on New Connection fits NO net meter and bills 12 kW
# ══════════════════════════════════════════════════════════════════════════
def _solar_plan(tenant, actor):
    tenancy_services.update_tenant_service(actor, "solar", {"enabled": True})
    _declare_capacity(tenant, "solar")
    plan = _plan_priced_per(tenant, "solar", uom="kW", rate=PER_KW)
    _base_charge_code(tenant, "solar")
    return plan


def test_a_solar_new_connection_fits_no_net_meter_and_bills_twelve_kw(brazos, dana):
    """**3 × 4 kW = 12 kW × $14.00 = `$168.00`, and no meter on the solar point.**

    The `meters` row for solar is what an OLD browser bundle still sends
    (`takesAMeter("solar")` answered true until this change). The commit leaves
    it out — PO 2026-10-02: *"we are not doing net metering right now"* — and
    says so on `unavailable`, rather than refusing the whole build over a row
    the clerk never chose.

    RED before the fix: the commit made `M-…` on the solar point, and once it
    was installed the bill refused `installed_capacity_undetermined`.
    """
    with tenant_ctx(brazos):
        seed_physical_series(brazos)
        plan = _solar_plan(brazos, dana)
        built = w6.commit_new_connect(
            dana,
            _payload(
                address="40 Sunfield Ct",
                services=["solar"],
                plan_id=plan.id,
                meters=[{"unit_label": "Unit 1", "service": "solar", "asset_no": None}],
                unit_services=[
                    {
                        "unit_label": "Unit 1",
                        "service": "solar",
                        "equipment": [{"type": "pv", "size_class": "SOL-P4", "count": 3}],
                    }
                ],
            ),
        )
        unit = _built_unit(built["id"])
        pieces = _pieces(unit, "solar")
        assert [piece.type.code for piece in pieces] == ["pv", "pv", "pv"], [
            (piece.asset_no, piece.type.code) for piece in pieces
        ]
        assert [piece.size_class for piece in pieces] == ["SOL-P4"] * 3
        assert built["manifest"]["meters"] == 0
        assert [row["code"] for row in built["unavailable"] if row.get("field") == "meters"] == [
            "no_net_meter_on_a_capacity_service"
        ]

        _install(pieces)
        _activate_build(dana, built["id"])
        cycle = _cycle(brazos, "SOL-NC")
        _open_account(dana, brazos, unit, cycle, "Priya Nair")
        invoice = _bill(brazos, cycle, "def-met-9037-solar-nc")

        assert _by_service(invoice)["solar"] == TWELVE_KW_BILL, _describe(invoice)
        usage = [line for line in invoice.lines.all() if line.quantity is not None]
        assert [(line.quantity, line.unit) for line in usage] == [(TWELVE_KW, "kW")]
        assert invoice.total == TWELVE_KW_BILL


# ══════════════════════════════════════════════════════════════════════════
# (3) AN EXISTING NET METER ON A SOLAR UNIT — the bill neither moves nor stops
# ══════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("kind", ["meter", "net_meter"])
def test_an_installed_meter_on_a_solar_point_does_not_change_or_refuse_the_bill(
    brazos, dana, kind
):
    """**Three 4 kW panels and an installed, unsized meter on the same solar
    point: 12 kW, `$168.00`, exactly as without the meter.**

    `meter` is the shape New Connect wrote until today (`DEF-MET-9037`: type
    `meter`, no size); `net_meter` is the catalogue's own net-meter type. Both
    are READ devices, never panels, so neither is counted or summed.

    RED before the fix: `prepare_run` blocked the account on
    `installed_capacity_undetermined`, because the meter's empty size sat beside
    the panels in the summed population.
    """
    with tenant_ctx(brazos):
        cycle, unit, _account = _solar_world(
            dana,
            brazos,
            cycle_code=f"SOL-NM-{kind}",
            code="solar",
            kind="pv",
            uom="kW",
            rate=PER_KW,
            specs=("SOL-P4", "SOL-P4", "SOL-P4"),
        )
        payload = {
            "type": kind,
            "asset_no": f"NM-{kind[:3].upper()}1",
            "service": "solar",
            "unit": "kWh",
            "read_method": "manual",
            "unit_id": str(unit["id"]),
            "install_date": INSTALL.isoformat(),
        }
        if kind == "net_meter":
            payload["net_metering"] = True
        asset_services.create_asset(dana, payload)
        meter = asset_models.Asset.objects.get(asset_no=payload["asset_no"])
        assert meter.size_class is None
        assert meter.status.behavior_class == "in_service"
        assert meter.service_point.service.code == "solar"

        invoice = _bill_solar(brazos, cycle, f"def-met-9037-existing-{kind}")

        assert _by_service(invoice)["solar"] == TWELVE_KW_BILL, _describe(invoice)
        usage = [line for line in invoice.lines.all() if line.quantity is not None]
        assert [(line.quantity, line.unit) for line in usage] == [(TWELVE_KW, "kW")]
        assert invoice.total == TWELVE_KW_BILL
