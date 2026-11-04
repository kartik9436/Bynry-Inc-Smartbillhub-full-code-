# ── Trace ──────────────────────────────────────────────
# Change:   CR-028 AST-W0 T1 (B16 §9 — seed & test data runs FIRST). Closes
#           DEF-496's seed gap: the ruled 3 × $15.00 = $45.00 walkthrough
#           (CR-019 / BR-RAT-090, PO 2026-08-21) could not be produced from the
#           tenant the product ships because no trash cart was ever seeded.
# Rules:    BR-RAT-090 (unmetered quantity = OBSERVED asset count) · BR-AST-003
#           (sub-meter parent) · BR-AST-010 (net metering) · BR-AST-042
#           (container_cart is seeded vocabulary) · BR-AST-044 (meter_type on
#           measuring assets) · BR-AST-047 (valuation lives on the device
#           record) · BR-TEN-057 (is_sample on the owning row) · BR-TEN-061
#           (removal order — subs before parents) · BR-TEN-063 (idempotent)
# Tests:    this file
# Impacts:  core/sample_fixture.py · apps/assets/sample_data.py
# ───────────────────────────────────────────────────────
"""CR-028 AST-W0-T1 — the sample seed reaches the r10 fixture shape, ADDITIVELY.

RED-FIRST PROOF (r11 step 2d): `test_the_three_cart_unit_counts_three` was run
against the seeder as it stood before this lane touched it and failed with
`assert 0 == 3` — billable_asset_count returned 0 for every unit, which is
DEF-496 exactly: a zero indistinguishable from "nobody delivered a cart".

Everything here drives the REAL seed path (rating → metering → assets sample
seeders, each through its own services) on a tenant provisioned with trash
enabled, then reads the results back through `apps.assets.selectors` — the
same read BR-RAT-090's seam uses at bill time. Nothing asserts a write
happened; everything asserts the ruling can be WALKED (DEF-496's prevention
sentence, verbatim: "a fixture test that reads the count back and requires 3
on the CR-019 walkthrough unit would go red today").
"""

import csv
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from core import sample_fixture as fixture

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    seed_physical_series,
    staff_actor,
    tenant_ctx,
)
from tests.test_us_ten_helpers import brazosbend_payload, provisioned_tenant

pytestmark = pytest.mark.django_db


@pytest.fixture()
def silvercreek(growth_plan, identity_seam):  # noqa: F811 — pytest fixture chain
    """A tenant with every fixture service ENABLED, so the trash carts seed.

    Brazos Bend enables electric+water only, and the cart block (like
    metering's) seeds only services the tenant sells — so this proof needs a
    tenant shaped like the real demo utility: water · sewer · trash, plus
    electric for the net-meter seed.
    """
    tenant, _result = provisioned_tenant(
        brazosbend_payload(
            name="Silver Creek Water (CR-028 seed proof)",
            subdomain="silvercreekcr028",
            services=["electric", "water", "sewer", "trash"],
        )
    )
    seed_physical_series(tenant)
    return tenant


@pytest.fixture()
def seeded(silvercreek):
    """The sample plant, in the orchestrator's own order (rating → metering →
    assets), through each module's real services — spec rule 4: *"Seed through
    the services a clerk's click uses, never by writing rows directly."*
    """
    from apps.assets import sample_data as assets_sample
    from apps.metering import sample_data as metering_sample
    from apps.rating import sample_data as rating_sample

    actor = staff_actor(silvercreek, "system_admin", "cr028@silvercreek.test")
    with tenant_ctx(silvercreek):
        rating_sample.seed_sample_records(actor)
        metering_sample.seed_sample_records(actor)
        assets_sample.seed_sample_records(actor)
    return silvercreek, actor


def _unit_id_for(index):
    """The seeded unit's id for a fixture unit_index, via metering's selector."""
    from apps.metering import selectors as metering_selectors

    unit_no = {u["unit_index"]: u["unit_no"] for u in fixture.units_flat()}[index]
    for row in metering_selectors.units_list():
        if row.unit_no == unit_no:
            return str(row.id)
    raise AssertionError(f"unit_index {index} ({unit_no}) was not seeded")


def _asset(asset_no):
    from apps.assets import models

    row = (
        models.Asset.objects.filter(asset_no=asset_no)
        .select_related("type", "status", "meter_type", "parent_asset")
        .first()
    )
    assert row is not None, f"{asset_no} is not seeded"
    return row


# ══════════════════════════════════════════════════════════════════════════
# 1 · DEF-496 closed: the ruled cart walkthrough WALKS
# ══════════════════════════════════════════════════════════════════════════


def test_the_three_cart_unit_counts_three(seeded):
    """THE DEF-496 ASSERTION — RED before this lane's seed change.

    Before: `assert 0 == 3` (no cart assets existed anywhere). Now the CR-019
    walkthrough unit carries exactly 3 in-service `container_cart` assets for
    trash, so 3 × $15.00 = $45.00 is producible from the shipped tenant, and
    the count is OBSERVED through the same three-predicate read the bill run
    uses (dated assignment · in-service behavior class · service point).
    """
    from apps.assets import selectors

    tenant, _actor = seeded
    with tenant_ctx(tenant):
        unit_id = _unit_id_for(fixture.CART_UNIT_WITH_THREE)
        count = selectors.billable_asset_count(unit_id, "trash", date(2026, 7, 31))
        assert count == 3, (
            f"the CR-019 walkthrough unit must hold exactly 3 active carts "
            f"(3 x $15.00 = $45.00, PO 2026-08-21); billable_asset_count says {count}"
        )
        # And the money the count implies is the ratified figure, restated so a
        # cart-price drift is caught beside its quantity.
        assert Decimal(fixture.TRASH_PER_CART) * count == Decimal("45.00")


def test_all_three_cart_cases_are_on_the_tenant(seeded):
    """DEF-496's prevention row asks for all three of BR-RAT-090's cases:
    three carts on one unit, one on another, none on a third — so 0 is proved
    to be a REAL answer beside real 3s, not the fixture's silence."""
    from apps.assets import selectors

    tenant, _actor = seeded
    as_of = date(2026, 7, 31)
    with tenant_ctx(tenant):
        assert (
            selectors.billable_asset_count(_unit_id_for(fixture.CART_UNIT_WITH_ONE), "trash", as_of)
            == 1
        )
        assert (
            selectors.billable_asset_count(
                _unit_id_for(fixture.CART_UNIT_WITH_NONE), "trash", as_of
            )
            == 0
        ), "the zero-cart unit is deliberate: the utility looked and there are none"


def test_carts_do_not_leak_into_the_water_count(seeded):
    """BR-RAT-090's third predicate: a unit with three carts and a water meter
    counts three for trash — and exactly one for water, not four."""
    from apps.assets import selectors

    tenant, _actor = seeded
    with tenant_ctx(tenant):
        unit_id = _unit_id_for(fixture.CART_UNIT_WITH_THREE)
        assert selectors.billable_asset_count(unit_id, "water", date(2026, 7, 31)) == 1


# ══════════════════════════════════════════════════════════════════════════
# 2 · The r10 registry shapes: master/sub · net meter · five BTM kinds
# ══════════════════════════════════════════════════════════════════════════


def test_the_master_meter_carries_its_subs(seeded):
    """r10 SET: a master meter (meter_type `master`) on the apartment block
    with sub-meters parented ON IT (BR-AST-003), so the registry's
    `Master · N units` / `Sub → M-MASTER-01` role tags have real data."""
    tenant, _actor = seeded
    with tenant_ctx(tenant):
        master = _asset(fixture.MASTER_METER["asset_no"])
        assert master.type.code == "meter"
        assert master.meter_type is not None and master.meter_type.code == "master"
        assert master.parent_asset_id is None
        subs = [_asset(row["asset_no"]) for row in fixture.master_sub_meter_plan()]
        assert len(subs) == 3
        for sub in subs:
            assert (
                sub.parent_asset_id == master.id
            ), f"{sub.asset_no} must be parented on {master.asset_no} (BR-AST-003)"
            assert sub.type.code == "sub_meter"


def test_the_net_meter_is_seeded_net(seeded):
    """BR-AST-010: `net_meter` locks net_metering ON — the detail's net line
    renders from a real row. (Its export READS are metering's half — W2.)"""
    tenant, _actor = seeded
    with tenant_ctx(tenant):
        net = _asset(fixture.NET_METER["asset_no"])
        assert net.type.code == "net_meter"
        assert net.net_metering is True


def test_all_five_r10_btm_device_kinds_exist(seeded):
    """r10 draws five behind-the-meter kinds; CR-010 seeded three. The two
    the tab was missing — comms endpoint and battery storage — are additive
    (BTM_DEVICE_PLAN itself is untouched, so CR-010's own test stays green)."""
    from apps.assets import models

    tenant, _actor = seeded
    with tenant_ctx(tenant):
        seeded_types = set(
            models.Asset.objects.filter(
                tenant_id=tenant.id, is_sample=True, type__category="behind_the_meter"
            ).values_list("type__code", flat=True)
        )
    assert {
        "backflow",
        "pv",
        "ev_charger",
        "comms",
        "battery",
    } <= seeded_types, (
        f"all five r10 device kinds must be on the tenant; found {sorted(seeded_types)}"
    )


# ══════════════════════════════════════════════════════════════════════════
# 3 · Inventory (unassigned) assets, one of them aged
# ══════════════════════════════════════════════════════════════════════════


def test_inventory_holds_unassigned_stock_and_one_aged_asset(seeded):
    """The Inventory tab (B16 §4.4, D5: counts & costs only) needs stock to
    count: ≥3 sample assets with NO assignment, behavior class `available`,
    at least one purchased more than 12 months before the fixture's clock."""
    from apps.assets import models, selectors

    tenant, _actor = seeded
    with tenant_ctx(tenant):
        inventory = [
            asset
            for asset in models.Asset.objects.filter(
                tenant_id=tenant.id, is_sample=True, status__behavior_class="available"
            ).select_related("status")
            if not models.AssetAssignment.objects.filter(asset=asset).exists()
        ]
        assert len(inventory) >= 3, f"only {len(inventory)} unassigned sample assets"
        aged_bar = date(2026, 8, 14) - timedelta(days=365)
        aged = [a for a in inventory if a.purchase_date and a.purchase_date < aged_bar]
        assert aged, "at least one inventory asset must be aged past 12 months (r10 KPI)"
        # The registry's Unassigned filter — the read the tab will use — agrees.
        rows = selectors.asset_list(filters={"status": "unassigned"})
        unassigned_nos = {row.asset_no for row in rows}
        for asset in inventory:
            assert asset.asset_no in unassigned_nos


# ══════════════════════════════════════════════════════════════════════════
# 4 · Valuation on the NEW seeds (BR-AST-047 / migration 0007)
# ══════════════════════════════════════════════════════════════════════════


def test_every_cr028_seed_carries_its_valuation(seeded):
    """BR-AST-047: cost/supplier/life live ON THE DEVICE RECORD. Every asset
    this CR added declares purchase_cost (4dp string in the fixture — rule 2),
    purchase_date, supplier and expected_life_years; costs sit in the r10
    ballpark and suppliers are the four r10 names."""
    suppliers_seen = set()
    tenant, _actor = seeded
    with tenant_ctx(tenant):
        for entry in fixture.cr028_asset_plan():
            valuation = entry["valuation"]
            # Rule 2 at the declaration: money is a string, parsing exactly.
            assert isinstance(valuation["purchase_cost"], str)
            cost = Decimal(valuation["purchase_cost"])
            assert (
                Decimal("118") <= cost <= Decimal("412")
            ), f"{entry['asset_no']}: {cost} is outside the r10 cost ballpark"
            assert 10 <= valuation["expected_life_years"] <= 20
            assert valuation["supplier"] in fixture.CR028_SUPPLIERS
            suppliers_seen.add(valuation["supplier"])
            row = _asset(entry["asset_no"])
            assert row.purchase_cost == cost
            assert row.purchase_date == date.fromisoformat(valuation["purchase_date"])
            assert row.supplier == valuation["supplier"]
            assert row.expected_life_years == valuation["expected_life_years"]
        assert len(suppliers_seen) >= 3, "the supplier column needs variety to group by"
        # The backflow keeps its BR-AST-027 test cadence (12 months, seeded).
        spare_backflow = _asset("BF-0002")
        assert spare_backflow.test_interval_months == 12


# ══════════════════════════════════════════════════════════════════════════
# 4b · DEF-597 — the spec §4 case-3 retirement actually HAPPENS
# ══════════════════════════════════════════════════════════════════════════


def test_the_replaced_meter_is_retired_with_its_assignment_closed(seeded):
    """DEF-597 — RED before the CR-028 debt sweep.

    Before: `_retire_the_replaced_meter` passed a narrative string as the
    `reason` ("replaced — sample data (spec §4 case 3 …)"), which is not in
    BR-AST-021's ratified set, so `retire_asset` refused and the except
    swallowed it — every seeded tenant carried TWO active meters on the
    case-3 unit and the read chain never crossed serials. Now the seeder uses
    the ratified reason `replaced` + `replaced_by` naming the new serial, and
    a failure raises instead of logging."""
    from apps.assets import models

    tenant, _actor = seeded
    old_no = f"W-{5000 + fixture.CASE_METER_REPLACED:04d}"
    new_no = f"W-{9000 + fixture.CASE_METER_REPLACED:04d}"
    with tenant_ctx(tenant):
        old = _asset(old_no)
        assert old.status.code == "retired", (
            f"{old_no} must be retired by the seeder (spec §4 case 3); "
            f"it is {old.status.code} — DEF-597"
        )
        assert old.retire_reason == "replaced", "BR-AST-021's ratified reason, verbatim"
        assert old.retire_date == date(2026, 6, 30)
        assert (
            old.replaced_by_asset is not None and old.replaced_by_asset.asset_no == new_no
        ), "the retire names its replacement — the lawful home for the case-3 narrative link"
        # BR-AST-021: the current assignment closes at the retire date.
        assignment = models.AssetAssignment.objects.filter(
            tenant_id=tenant.id, asset=old
        ).first()
        assert assignment is not None
        assert assignment.to_date == date(2026, 6, 30), (
            "the old serial's assignment must CLOSE at the retire date "
            f"(got to_date={assignment.to_date})"
        )
        # And the replacement is on the SAME unit from July — the crossing chain.
        new = _asset(new_no)
        new_assignment = models.AssetAssignment.objects.filter(
            tenant_id=tenant.id, asset=new, to_date__isnull=True
        ).first()
        assert new_assignment is not None
        assert str(new_assignment.unit_id) == _unit_id_for(fixture.CASE_METER_REPLACED)
        assert new_assignment.from_date == date(2026, 7, 1)


# ══════════════════════════════════════════════════════════════════════════
# 5 · Idempotency and removal-order compatibility
# ══════════════════════════════════════════════════════════════════════════


def test_a_replay_writes_nothing(seeded):
    """BR-TEN-063 — every new block is idempotent on asset_no."""
    from apps.assets import models, sample_data

    tenant, actor = seeded
    with tenant_ctx(tenant):
        before = models.Asset.objects.filter(tenant_id=tenant.id).count()
        written = sample_data.seed_sample_records(actor)
        after = models.Asset.objects.filter(tenant_id=tenant.id).count()
    assert written == 0
    assert after == before


def test_removal_still_deletes_subs_before_the_master(seeded):
    """BR-TEN-061: the new master is a PARENT (self-FK PROTECT), so it must be
    deletable AFTER its subs — the removal order the seeder already keeps. No
    CR-028 asset carries a read, so none may be retained."""
    from apps.assets import models, sample_data

    tenant, _actor = seeded
    with tenant_ctx(tenant):
        result = sample_data.remove_sample_records()
        retained = {row["label"] for row in result["retained"]}
        for asset_no in fixture.cr028_asset_numbers():
            assert (
                f"meter {asset_no}" not in retained
            ), f"{asset_no} was retained on removal — the order or a FK is wrong"
            assert not models.Asset.objects.filter(tenant_id=tenant.id, asset_no=asset_no).exists()


# ══════════════════════════════════════════════════════════════════════════
# 6 · AST-W0-T2 — the import fixture files (headers pinned to B16 §4.7b)
# ══════════════════════════════════════════════════════════════════════════

FIXTURES = Path(__file__).parent / "fixtures" / "cr028"

#: B16 §4.7b, verbatim: the meters target's source columns (+ one deliberately
#: ignorable LEGACY column — the field map's explicit "— ignore —" case).
METERS_HEADER = [
    "METER_NO",
    "METER_TYPE",
    "SERVICE",
    "READ_METHOD",
    "MULTIPLIER",
    "UNIT_REF",
    "MFR",
    "MODEL",
    "INSTALL_DT",
    "CERT_DUE",
    "WARRANTY_END",
    "SUPPLIER",
    "COST",
    "LEGACY",
]
#: "Sub-meters target adds PARENT_MTR … ALLOC_PCT" — added to the base set.
SUBMETERS_HEADER = [*METERS_HEADER[:-1], "PARENT_MTR", "ALLOC_PCT"]
#: "Devices target adds DEVICE_TYPE · PREMISE_ID · TEST_FREQ · NEXT_TEST ·
#: EXPORT_KW" — the §4.7 diagram's "+" reads as added to the base set.
DEVICES_HEADER = [
    *METERS_HEADER[:-1],
    "DEVICE_TYPE",
    "PREMISE_ID",
    "TEST_FREQ",
    "NEXT_TEST",
    "EXPORT_KW",
]


def _rows(name):
    with (FIXTURES / name).open() as handle:
        reader = csv.reader(handle)
        header = next(reader)
        return header, list(reader)


def test_the_meters_fixture_covers_every_declared_rule_case():
    """~20 rows per W0-T2: happy · blank UNIT_REF (BR-AST-045 → inventory) ·
    duplicate + blank meter numbers · bad unit ref · non-integer multiplier ·
    future CERT_DUE · the LEGACY column the map must offer to ignore."""
    header, rows = _rows("assets_meters.csv")
    assert header == METERS_HEADER, "headers are B16 §4.7b's, exactly"
    assert len(rows) == 20
    by_col = [dict(zip(header, row)) for row in rows]
    assert sum(1 for r in by_col if not r["UNIT_REF"]) >= 3, "blank unit ⇒ inventory rows"
    numbers = [r["METER_NO"] for r in by_col if r["METER_NO"]]
    assert len(numbers) != len(set(numbers)), "a duplicate meter number is present"
    assert any(not r["METER_NO"] for r in by_col), "a blank meter number is present"
    assert any(r["UNIT_REF"] == "SCW-U-999" for r in by_col), "a bad unit ref is present"
    assert any(r["MULTIPLIER"] not in ("", "1", "200") for r in by_col), "non-integer multiplier"
    assert any(r["CERT_DUE"] > "2029" for r in by_col), "a far-future CERT_DUE is present"
    assert all(r["LEGACY"] for r in by_col), "the ignorable LEGACY column is populated"


def test_the_submeters_fixture_covers_the_parent_rules():
    header, rows = _rows("assets_submeters.csv")
    assert header == SUBMETERS_HEADER
    assert len(rows) == 10
    by_col = [dict(zip(header, row)) for row in rows]
    assert any(r["PARENT_MTR"] == "M-GONE-77" for r in by_col), "missing-master case"
    assert any(not r["PARENT_MTR"] for r in by_col), "blank-parent case"
    # W-5011 is the fixture's RETIRED meter (CASE_METER_REPLACED = 11) — the
    # retired-master placeholder rides a master the seed really retires.
    retired_no = f"W-{5000 + fixture.CASE_METER_REPLACED:04d}"
    assert any(r["PARENT_MTR"] == retired_no for r in by_col), "retired-master case"
    assert any(not r["UNIT_REF"] for r in by_col), "blank unit (accepted → inventory)"
    assert any(r["ALLOC_PCT"] for r in by_col), "an allocated (non-metered) share"


def test_the_devices_fixture_covers_all_five_kinds_and_the_test_rules():
    header, rows = _rows("assets_devices.csv")
    assert header == DEVICES_HEADER
    assert len(rows) == 10
    by_col = [dict(zip(header, row)) for row in rows]
    kinds = {r["DEVICE_TYPE"] for r in by_col}
    assert {"backflow", "pv", "ev_charger", "comms", "battery"} <= kinds
    assert any(r["PREMISE_ID"] == "P-99999" for r in by_col), "bad premises ref"
    assert any(
        r["TEST_FREQ"] and not r["NEXT_TEST"] for r in by_col
    ), "TEST_FREQ set with NEXT_TEST missing (W → derive from install date)"
    exporting = [r for r in by_col if r["EXPORT_KW"]]
    assert exporting and all(
        r["DEVICE_TYPE"] == "pv" for r in exporting
    ), "EXPORT_KW rides the inverter and only the inverter"


def test_the_100k_generator_shares_the_meters_header_and_is_deterministic(tmp_path):
    """make_100k.py must chase the SAME columns as the hand fixture (one
    target, one column set) and produce byte-identical output on replay —
    the runner's stage-1 SHA-256 must be stable to be assertable."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("make_100k", FIXTURES / "make_100k.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.HEADER == METERS_HEADER
    assert module.DEFAULT_ROWS == 100_000, "CR-026's cap, exactly"
    first = module.generate(tmp_path / "a.csv", rows=500)
    second = module.generate(tmp_path / "b.csv", rows=500)
    assert first == second, "two runs must be byte-identical (fixed seed)"
    with (tmp_path / "a.csv").open() as handle:
        rows = list(csv.reader(handle))
    assert rows[0] == METERS_HEADER
    assert len(rows) == 501
    # And the generated 100k file itself is never committed (hard-won law 5).
    assert not list(FIXTURES.glob("*100k*.csv")), "the generated CSV must not be committed"
    assert "*.generated.csv" in (FIXTURES / ".gitignore").read_text()


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-028 / B16 §9 AST-W0-T1+T2 + DEF-496 + BR-RAT-090 (PO 2026-08-21) + BR-AST-045/047 (PO 2026-08-22)
# generated: 2026-08-22 by story-coder (CR-028 AST-W0 lane)
# checklist: A✔ B✔ C=n/a(no API half) D=n/a E=n/a F✔ G✔ H=deferred(PO 2026-08-09)
# gates: see the lane report
# exceptions: the cart assertion was proved RED against the unmodified seeder (assert 0 == 3) before the seed change landed — quoted in the module docstring · export reads for the net meter are metering's half (W2) and deliberately NOT asserted here · the W0-T2 fixture tests pin FILES and HEADERS, not runner behavior — the three targets are AST-W3's build, and these CSVs are the cases §3-style declared for it in advance (r11 2c: cases before code)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
