"""**47.84 kW + 10 kW = 57.84 kW × $14.00 = $809.76 — NOT 2 × $14.00 = $28.00.**

`DEF-RAT-10220`. The Product Owner's report of 2026-10-17 (Ann Arbor
Sustainable Energy): a Municipal Solar rate at $14 per kW, a size class
`SOL-P47.84 · Solar Panal 47.84` added under Settings, two PV assets on one unit
(the 47.84 and a built-in `SOL-P10`), and the draft read **2 KW @ $14.00 =
$28.00**. Two causes, both fixed here:

  1. the rate's unit was saved `KW`, the capacity is in `kW`, and
     `bills_installed_capacity` compared them EXACTLY, so the bill fell to the
     COUNT of panels; and
  2. a tenant-added size class had a code and a name and NO capacity, so its kW
     could only ever be unknown.

PO, verbatim, on the shape of the fix: *"do not hard code anything - we need to
stay with logi and make logical corrections; it should able to handle dyanmic
capacities and calcualte based on logic"*. So this file proves the arithmetic
on SEVERAL capacities (47.84, 10, 3.5, 120) and on a SECOND summing service
(battery), never only on the PO's own pair; it proves trash and fire still
COUNT; and it proves another tenant's figure can never answer.

The decision log entry is *"2026-10-17 — SOLAR/BATTERY BILL THE SUM OF
INSTALLED kW; A TENANT-ADDED SIZE CARRIES ITS OWN CAPACITY"*.
"""

from decimal import Decimal

import pytest

from apps.billing import gather
from apps.rating import models as rating_models
from apps.rating.pricing import errors as pricing_errors
from apps.rating.pricing.stages import normalize
from apps.tenancy import models as tenancy_models
from apps.tenancy import selectors as tenancy_selectors
from apps.tenancy import service_size_classes as sizes
from apps.tenancy import services as tenancy_services
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import make_plan, tenant_ctx  # noqa: F401
from tests.test_br_cus_068_master_bill import _by_service
from tests import test_cr062_d1_installed_capacity_sums as d1

pytestmark = pytest.mark.django_db

PER_KW = Decimal("14.000000")
PO_TOTAL = Decimal("809.76")
PO_UNDERCHARGE = Decimal("28.00")


def _size(tenant, code, service_code, capacity, name=None):
    """A tenant's OWN size-class row, written straight to the table so a test
    can also hold the legacy state the Settings form now refuses (a summing
    size with no capacity)."""
    return tenancy_models.MeterSizeClass.objects.create(
        tenant=tenant,
        code=code,
        name=name or code,
        service=tenancy_models.Service.objects.get(code=service_code),
        capacity=None if capacity is None else Decimal(capacity),
        is_system=False,
        active=True,
    )


def _usage(invoice):
    return [line for line in invoice.lines.all() if line.quantity is not None]


# ══════════════════════════════════════════════════════════════════════════
# (1) THE PO's OWN FIGURE, AS THE CLERK TYPED THE UNIT
# ══════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("typed_unit", ["KW", "kW", " kw "])
def test_tc1__po_tenant_size_plus_builtin_bill_the_sum_whatever_the_unit_case(
    brazos, dana, typed_unit
):
    """**SOL-P47.84 (47.84 kW, a tenant's own size) + SOL-P10 (10 kW) on a
    FLAT $14.00-per-kW schedule = 57.84 kW = `$809.76`.** Before: `$28.00`."""
    with tenant_ctx(brazos):
        _size(brazos, "SOL-P47.84", "solar", "47.84", name="Solar Panal 47.84")
        cycle, _unit, _account = d1._world(
            dana,
            brazos,
            cycle_code="KW-1",
            code="solar",
            kind="pv",
            uom=typed_unit,
            rate=PER_KW,
            specs=("SOL-P47.84", "SOL-P10"),
        )
        rating_models.TariffVersion.objects.filter(tenant=brazos, uom=typed_unit).update(model="flat")

        invoice = d1._bill(brazos, cycle, f"def-rat-10220-tc1-{typed_unit.strip()}")

        assert _by_service(invoice)["solar"] == PO_TOTAL
        assert invoice.total != PO_UNDERCHARGE
        usage = _usage(invoice)
        assert len(usage) == 1
        # Hard rule 3 — the quantity says what it is: the capacity's own unit.
        assert (usage[0].quantity, usage[0].unit) == (Decimal("57.840000"), "kW")


# ══════════════════════════════════════════════════════════════════════════
# (2) SEVERAL CAPACITIES, A SECOND SUMMING SERVICE — nothing about solar
# ══════════════════════════════════════════════════════════════════════════
def test_tc2__battery_sums_tenant_sizes_of_three_point_five_and_one_twenty(brazos, dana):
    """**Battery: 3.5 kW + 120 kW (both tenant sizes) + BAT-10 (built-in) =
    133.5 kW, at $3.00 per `kw` = `$400.50`.** No code anywhere names battery,
    and the unit is typed lower-case."""
    with tenant_ctx(brazos):
        _size(brazos, "BAT-3.5", "battery", "3.5")
        _size(brazos, "BAT-120", "battery", "120")
        cycle, _unit, _account = d1._world(
            dana,
            brazos,
            cycle_code="BAT-1",
            code="battery",
            kind="battery",
            uom="kw",
            rate=Decimal("3.000000"),
            specs=("BAT-3.5", "BAT-120", "BAT-10"),
        )

        invoice = d1._bill(brazos, cycle, "def-rat-10220-tc2")

        assert _by_service(invoice)["battery"] == Decimal("400.50")
        assert [(u.quantity, u.unit) for u in _usage(invoice)] == [(Decimal("133.500000"), "kW")]


def test_tc3__the_tenant_row_wins_over_the_ladder_for_a_builtin_code(brazos):
    """A built-in size's capacity is DATA on its row: a tenant that records
    SOL-P10 as 12 kW bills 12 kW. The ladder is the seed source only."""
    with tenant_ctx(brazos):
        row = tenancy_models.MeterSizeClass.objects.get(tenant=brazos, code="SOL-P10")
        assert row.capacity == Decimal("10.0000"), "the seed carries the ladder's figure"
        tenancy_models.MeterSizeClass.objects.filter(pk=row.pk).update(capacity=Decimal("12"))
        caps = tenancy_selectors.size_class_capacities("solar")
        assert sizes.total_capacity("solar", ["SOL-P10", "SOL-P2"], caps) == Decimal("14.0000")
        # with no rows at all, the ladder answers (a tenant never seeded)
        assert sizes.total_capacity("solar", ["SOL-P10"]) == Decimal("10.0000")


# ══════════════════════════════════════════════════════════════════════════
# (3) THE COUNTING SERVICES DO NOT MOVE
# ══════════════════════════════════════════════════════════════════════════
def test_tc4__trash_still_counts_three_carts_forty_five_dollars(brazos, dana):
    with tenant_ctx(brazos):
        cycle, _unit, _account = d1._world(
            dana,
            brazos,
            cycle_code="CART-9",
            code="trash",
            kind="container_cart",
            uom="CART",  # case changes nothing: trash sums in no unit
            rate=Decimal("15.000000"),
            specs=("CART-96", "CART-96", "CART-35"),
        )
        invoice = d1._bill(brazos, cycle, "def-rat-10220-tc4")
        assert _by_service(invoice)["trash"] == Decimal("45.00")
        assert [(u.quantity, u.unit) for u in _usage(invoice)] == [(Decimal("3.000000"), "CART")]


def test_tc5__fire_still_counts_and_a_capacity_on_a_fire_row_is_never_summed():
    assert sizes.fire_charge({"FL-6": 1, "FL-2": 2}) == Decimal("84.00")
    with pytest.raises(sizes.NotACapacityService):
        sizes.total_capacity("fire", ["FL-6"], {"fl-6": Decimal("6")})


# ══════════════════════════════════════════════════════════════════════════
# (4) AN UNKNOWN CAPACITY REFUSES AND NAMES THE ASSET
# ══════════════════════════════════════════════════════════════════════════
def test_tc6__a_tenant_size_with_no_capacity_refuses_naming_the_asset(brazos, dana):
    with tenant_ctx(brazos):
        _size(brazos, "SOL-P47.84", "solar", None)
        cycle, _unit, _account = d1._world(
            dana,
            brazos,
            cycle_code="KW-6",
            code="solar",
            kind="pv",
            uom="KW",
            rate=PER_KW,
            specs=("SOL-P47.84", "SOL-P10"),
        )
        with pytest.raises(gather.GatherProblem) as refusal:
            d1._bill(brazos, cycle, "def-rat-10220-tc6")
        problem = refusal.value
        assert problem.reason == "installed_capacity_undetermined"
        assert problem.message_key == "billing.check.capacityUnknownAssets"
        # `_equipment` numbers the assets PV-SO001, PV-SO002 in spec order;
        # only the first has a size with no capacity.
        assert problem.message_params["assets"] == "PV-SO001"
        assert problem.clerk_detail == "PV-SO001: size has no capacity."


def test_tc7__another_tenants_capacity_never_answers(brazos, lonestar, dana):
    """Lonestar records SOL-P47.84 at 99 kW; Brazos's row of the same code has
    none. Brazos refuses — it is never billed at Lonestar's 99."""
    with tenant_ctx(lonestar):
        _size(lonestar, "SOL-P47.84", "solar", "99")
        assert tenancy_selectors.size_class_capacities("solar")["sol-p47.84"] == Decimal("99.0000")
    with tenant_ctx(brazos):
        _size(brazos, "SOL-P47.84", "solar", None)
        assert "sol-p47.84" not in tenancy_selectors.size_class_capacities("solar")
        cycle, _unit, _account = d1._world(
            dana,
            brazos,
            cycle_code="KW-7",
            code="solar",
            kind="pv",
            uom="kW",
            rate=PER_KW,
            specs=("SOL-P47.84",),
        )
        with pytest.raises(gather.GatherProblem) as refusal:
            d1._bill(brazos, cycle, "def-rat-10220-tc7")
        assert refusal.value.message_params["assets"] == "PV-SO001"


# ══════════════════════════════════════════════════════════════════════════
# (5) SETTINGS — the size carries its capacity, for summing services only
# ══════════════════════════════════════════════════════════════════════════
def _create(actor, payload):
    return tenancy_services.create_lookup_entry(actor, "service_size_classes", payload)


def _refusal_key(fn):
    with pytest.raises(errors.ValidationError) as caught:
        fn()
    return caught.value.field_errors[0]["message_key"]


def test_tc8__settings_stores_capacity_to_four_places_for_summing_services(brazos, dana):
    with tenant_ctx(brazos):
        tenancy_services.update_tenant_service(dana, "solar", {"enabled": True})
        tenancy_services.update_tenant_service(dana, "trash", {"enabled": True})
        made = _create(dana, {"code": "SOL-P47.84", "name": "Solar Panal 47.84", "service": "solar", "capacity": "47.84"})
        assert made["capacity"] == "47.8400"
        assert made["capacity_uom"] == "kW"
        assert tenancy_models.MeterSizeClass.objects.get(pk=made["id"]).capacity == Decimal("47.8400")

        no_cap = {"code": "SOL-X", "name": "X", "service": "solar"}
        assert _refusal_key(lambda: _create(dana, no_cap)) == "settings.sizeClasses.capacityRequired"
        for bad in ("0", "-1", "1.23456", "abc", 2.5):
            assert (
                _refusal_key(lambda: _create(dana, {**no_cap, "capacity": bad}))
                == "settings.sizeClasses.capacityInvalid"
            ), bad
        cart = {"code": "CART-X", "name": "Cart", "service": "trash", "capacity": "5"}
        assert _refusal_key(lambda: _create(dana, cart)) == "settings.sizeClasses.capacityNotApplicable"
        plain = _create(dana, {"code": "CART-Y", "name": "Cart Y", "service": "trash"})
        assert plain["capacity"] is None

        # Edit: change the figure; clearing it on a summing size is refused.
        changed = tenancy_services.update_lookup_entry(
            dana, "service_size_classes", made["id"], {"capacity": "3.5"}
        )
        assert changed["capacity"] == "3.5000"
        assert (
            _refusal_key(
                lambda: tenancy_services.update_lookup_entry(
                    dana, "service_size_classes", made["id"], {"capacity": ""}
                )
            )
            == "settings.sizeClasses.capacityRequired"
        )


def test_tc9__services_settings_publishes_the_summing_unit_from_configuration(brazos):
    with tenant_ctx(brazos):
        assert tenancy_selectors.service_row("solar")["capacity_uom"] == "kW"
        assert tenancy_selectors.service_row("battery")["capacity_uom"] == "kW"
        assert tenancy_selectors.service_row("trash")["capacity_uom"] is None
        assert tenancy_selectors.service_row("fire")["capacity_uom"] is None
        assert tenancy_selectors.service_row("water")["capacity_uom"] is None


def test_tc10__migration_backfills_a_builtin_row_and_keeps_a_tenant_value(brazos):
    import importlib

    from django.apps import apps as django_apps
    from django.db import connection

    module = importlib.import_module("apps.tenancy.migrations.0064_def_rat_10220_size_class_capacity")
    with tenant_ctx(brazos):
        tenancy_models.MeterSizeClass.objects.filter(tenant=brazos, code="BAT-20").update(capacity=None)
        tenancy_models.MeterSizeClass.objects.filter(tenant=brazos, code="BAT-25").update(capacity=Decimal("26"))

        class _Editor:
            pass

        editor = _Editor()
        editor.connection = connection
        module.forwards(django_apps, editor)
        with tenant_ctx(brazos):
            got = dict(
                tenancy_models.MeterSizeClass.objects.filter(
                    tenant=brazos, code__in=["BAT-20", "BAT-25", "W-2"]
                ).values_list("code", "capacity")
            )
    assert got["BAT-20"] == Decimal("20.0000")
    assert got["BAT-25"] == Decimal("26.0000")
    assert got["W-2"] is None


# ══════════════════════════════════════════════════════════════════════════
# (6) ONE UNIT RULE AT BOTH POINTS — generic, never a KW special case
# ══════════════════════════════════════════════════════════════════════════
def test_tc11__one_unit_rule_at_both_comparison_points():
    from core.units import same_unit, unit_key

    assert unit_key(" K W ") == "k w"
    assert same_unit("KW", "kW") and same_unit(" kwh", "kWh") and same_unit("ERU", "eru")
    assert not same_unit("kWh", "MWh")
    assert not same_unit("", "")
    assert not same_unit(None, None)
    normalize._gate_uom("KWH", "kWh", "electric")  # spelling — passes
    with pytest.raises(pricing_errors.UomMismatch):
        normalize._gate_uom("MWh", "kWh", "electric")  # a different unit — refuses

    class _Reading:
        capacity_uom = "kW"

    class _Tariff:
        billed_unit = "KW"

    from apps.billing.stages.measure_consumption import bills_installed_capacity

    assert bills_installed_capacity(_Reading(), _Tariff())
    _Tariff.billed_unit = "panel"
    assert not bills_installed_capacity(_Reading(), _Tariff())



# ══════════════════════════════════════════════════════════════════════════
# (7) DEF-BIL-10221 — the one-time Services row says the kW, not "2 KW"
# ══════════════════════════════════════════════════════════════════════════
def test_tc12__one_time_services_row_names_the_installed_total_not_a_count_in_kw(monkeypatch):
    """Found by this defect's walk: the bill line read 57.84 kW × $14.00 =
    $809.76 while the Services row above it read *"2 KW · PV-00001,
    PV-00002"* and *"Billed · 2 KW"* — the asset COUNT labelled with the price
    unit. A summing row carries the installed total and no count unit; a
    COUNTING row (trash, 3 carts) keeps its count unit exactly as before."""
    from types import SimpleNamespace

    from apps.billing import one_time_answer

    monkeypatch.setattr(one_time_answer, "_unmetered", lambda: frozenset({"solar", "trash"}))
    monkeypatch.setattr(one_time_answer, "_service_rank", lambda: {"trash": 0, "solar": 1})
    data = SimpleNamespace(
        tariffs=(
            SimpleNamespace(service="solar", billed_unit="KW", model="flat"),
            SimpleNamespace(service="trash", billed_unit="cart", model="flat"),
        ),
        readings=(
            SimpleNamespace(service_code="solar", capacity_uom="kW", installed_capacity=Decimal("57.8400")),
            SimpleNamespace(service_code="trash", capacity_uom=None, installed_capacity=None),
        ),
    )
    assets = {
        "solar": [{"asset_id": "a", "label": "PV-00001"}, {"asset_id": "b", "label": "PV-00002"}],
        "trash": [
            {"asset_id": "c", "label": "CART-1"},
            {"asset_id": "d", "label": "CART-2"},
            {"asset_id": "e", "label": "CART-3"},
        ],
    }
    rows = {
        row["service"]: row
        for row in one_time_answer.services_table(
            data, warnings=(), assets=assets, taken=None, unconnected=(), not_taken=()
        )
    }
    assert rows["solar"]["count_unit"] is None
    assert rows["solar"]["installed"] == {"quantity": "57.84", "unit": "kW"}
    assert rows["trash"]["count_unit"] == "cart"
    assert rows["trash"].get("installed") is None
