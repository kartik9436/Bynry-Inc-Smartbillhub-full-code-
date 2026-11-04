# ── Trace ──────────────────────────────────────────────
# Defects: DEF-AST-8097 (devices sheet has no Service/Size/UoM/Parent — carts
#          never counted) · DEF-AST-8098 (meters/sub-meters lack UoM, net
#          metering, digits, allocation rule, loss tolerance) · DEF-AST-8099
#          (re-upload silently skips billing fields) · DEF-AST-8100 (only the
#          first error per row shown) · DEF-AST-8101 (downloads not in the
#          six-group order)
# Ruling:  PO 2026-09-30 — the asset-upload rows at the top of
#          12-governance/02-decision-log.md; the plan is
#          04-docs/05-modules/05-assets/12-asset-upload-fix-plan.md (U1–U15)
# Rules:   BR-AST-034 (template; re-upload clause SUPERSEDED 2026-09-30) ·
#          BR-AST-012 (kept: audit before/after, forward-only) · BR-AST-538
#          (the four allocation methods) · BR-RAT-090 (a counted service
#          counts its assets through the service point)
# Tests:   this file (U12)
# Impacts: apps/metering/import_runs.py · apps/metering/import_rules.py ·
#          apps/assets/services.py · apps/assets/selectors.py ·
#          apps/tenancy/selectors.py · apps/metering/seams.py
# ───────────────────────────────────────────────────────
"""Plan U12 — one test per new column, RED first, then the five named cases.

RED-FIRST PROOF: this file was run against the branch base `70c3cc7de`
(a clean `git worktree`, before any U2–U8 change) and every case below failed
there — the column tests on `KeyError`/missing header, the device-count case
on `0 != 2` (a device sheet could not name a service, so no cart had a service
point), the override case on the multiplier staying `1`, the three-problem
case on a problem holding ONE sentence, and the order cases on the header
lists. The receipt is quoted in the lane's report; GREEN is this tree.

⚠ **BASE PER ASSET IS NOT ASSERTED.** The plan's worked figure is 2 carts at
`$15.00` + `$3.00` base each = `$36.00` (PO 2026-09-30, option B). That base
arithmetic is `DEF-BIL-8095`, another lane's work and not landed on this
branch, so the device case asserts what THIS lane owns — the COUNT the bill
multiplies, `billable_asset_count(unit, "trash") == 2` — and says so here
rather than asserting `$33.00` and pretending it is the ruling.
"""

from __future__ import annotations

import csv
import io
from decimal import Decimal

import pytest

from apps.assets import models as asset_models
from apps.assets import selectors as asset_selectors
from apps.metering import import_rules, import_runs, seams as metering_seams
from apps.metering import models as metering_models
from apps.metering import services as metering_services

from tests.test_def962_def963_assets_template import (  # noqa: F401 — fixtures
    ALL_OFF,
    _estate,
    ottumwa,
    ottumwa_admin,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import make_premises, make_unit, tenant_ctx

pytestmark = pytest.mark.django_db

# ══════════════════════════════════════════════════════════════════════════
# The PO-confirmed tables, typed out ONCE, from the plan document — the thing
# the code must match. A column added out of place turns these red.
# ══════════════════════════════════════════════════════════════════════════

PLAN_METERS = [
    "asset_no", "external_ref", "serial_no",
    "unit_ref",
    "service", "size_class", "unit", "multiplier", "net_metering",
    "meter_type", "read_method", "register_digits", "manufacturer", "model",
    "install_date", "certification_due", "warranty_end",
    "supplier", "purchase_cost",
]  # fmt: skip
PLAN_SUBMETERS = [
    "asset_no", "external_ref", "serial_no",
    "unit_ref", "parent_asset_no",
    "service", "unit", "multiplier", "allocation_share_pct", "allocation_rule",
    "loss_tolerance_pct",
    "meter_type", "read_method", "register_digits", "manufacturer", "model",
    "install_date", "certification_due", "warranty_end",
    "supplier", "purchase_cost",
]  # fmt: skip
PLAN_DEVICES = [
    "asset_no", "type", "external_ref", "serial_no",
    "premises", "unit_ref", "parent_asset_no",
    "service", "size_class", "unit", "export_capacity_kw",
    "manufacturer", "model",
    "install_date", "test_interval_months", "certification_due", "warranty_end",
    "supplier", "purchase_cost",
]  # fmt: skip
PLAN = {
    import_runs.TARGET_ASSETS_METERS: PLAN_METERS,
    import_runs.TARGET_ASSETS_SUBMETERS: PLAN_SUBMETERS,
    import_runs.TARGET_ASSETS_DEVICES: PLAN_DEVICES,
}
REQUIRED = {
    import_runs.TARGET_ASSETS_METERS: {"service"},
    import_runs.TARGET_ASSETS_SUBMETERS: {"service", "parent_asset_no"},
    import_runs.TARGET_ASSETS_DEVICES: {"type", "service"},
}
COUNTS = {
    import_runs.TARGET_ASSETS_METERS: 19,
    import_runs.TARGET_ASSETS_SUBMETERS: 21,
    import_runs.TARGET_ASSETS_DEVICES: 19,
}


def _declared(target):
    return list(import_runs.EXPLICIT_COLUMNS_BY_TARGET[target])


def _csv(header, rows):
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(header)
    for row in rows:
        writer.writerow([row.get(name, "") for name in header])
    return buffer.getvalue()


def _labels(target):
    return {c["target"]: c["label"] for c in import_runs.EXPLICIT_COLUMNS_BY_TARGET[target]}


def _file(target, rows):
    """A file whose HEADERS are the sheet's own labels — what an operator who
    filled in our template uploads. `rows` are dicts keyed by FIELD."""
    labels = _labels(target)
    fields = [f for f in PLAN[target] if any(f in row for row in rows)]
    header = [labels[f] for f in fields]
    return _csv(header, [{labels[k]: v for k, v in row.items()} for row in rows])


def _stages(actor, target, content, write_mode="insert"):
    run = import_runs.extract(
        actor,
        {
            "target": target,
            "source_kind": "file",
            "file_name": f"{target}.csv",
            "content": content,
            "session_ref": "sess_u12",
            "write_mode": write_mode,
        },
    )
    import_runs.transform(
        actor, run["id"], {"mapping": run["detected_mapping"], "row_handling": ALL_OFF}
    )
    import_runs.validate(actor, run["id"], write_mode)
    return run["id"]


def _problems(run_id):
    run = metering_models.ImportRun.objects.get(pk=run_id)
    return {row["row_no"]: row["problem"] for row in import_runs.rejects(run)}


def _load(actor, run_id, write_mode="insert"):
    return import_runs.load(actor, run_id, {"write_mode": write_mode, "approved": True})


def _read_csv(run_id, kind):
    _name, body = import_runs.results_csv(run_id, kind)
    return list(csv.reader(io.StringIO("".join(body))))


def _asset(external_ref):
    return asset_models.Asset.objects.get(external_ref=external_ref)


# ══════════════════════════════════════════════════════════════════════════
# U2 — the three sheets, in the plan's order, with its required flags
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("target", list(PLAN))
def test_U2_each_sheet_is_the_plan_table_in_order(target):
    fields = [c["target"] for c in _declared(target)]
    assert fields == PLAN[target]
    assert len(fields) == COUNTS[target]


@pytest.mark.parametrize("target", list(PLAN))
def test_U2_required_columns_are_the_ruled_one_to_three(target):
    required = {c["target"] for c in _declared(target) if c["required"]}
    assert required == REQUIRED[target]


@pytest.mark.parametrize("target", list(PLAN))
def test_U2_the_six_groups_run_in_order_on_every_sheet(target):
    order = import_runs.ASSET_COLUMN_GROUPS
    groups = [c["group"] for c in _declared(target)]
    assert [order.index(g) for g in groups] == sorted(order.index(g) for g in groups)
    assert set(groups) == set(order)


# ══════════════════════════════════════════════════════════════════════════
# Downloads — the template/sample, the failures file and the result file all
# follow the plan order (PO confirmation 2026-09-30)
# ══════════════════════════════════════════════════════════════════════════


def _in_plan_order(target, fields):
    known = [f for f in fields if f in PLAN[target]]
    positions = [PLAN[target].index(f) for f in known]
    return positions == sorted(positions), known


@pytest.mark.parametrize("target", list(PLAN))
def test_DOWNLOAD_the_template_header_follows_the_plan_order(ottumwa, ottumwa_admin, target):
    with tenant_ctx(ottumwa):
        _estate(ottumwa_admin)
        header = next(csv.reader(import_runs.sample_csv(target)[1].splitlines()))
        by_label = {v: k for k, v in _labels(target).items()}
        fields = [by_label.get(h, h) for h in header]
        assert fields == PLAN[target], fields


#: result-file column → the plan field it reports.
SUCCESS_FIELD = {
    "asset_number": "asset_no",
    "asset_type": "type",
    "external_reference": "external_ref",
    "serial_number": "serial_no",
    "unit_assigned": "unit_ref",
    "master_meter": "parent_asset_no",
    "linked_meter": "parent_asset_no",
    "service": "service",
    "connection_size": "size_class",
    "size": "size_class",
    "unit_of_measure": "unit",
    "multiplier": "multiplier",
    "net_metering": "net_metering",
    "register_digits": "register_digits",
    "allocation_share_pct": "allocation_share_pct",
    "allocation_rule": "allocation_rule",
    "loss_tolerance_pct": "loss_tolerance_pct",
    "export_capacity_kw": "export_capacity_kw",
}


@pytest.mark.parametrize("target", list(PLAN))
def test_DOWNLOAD_the_result_file_header_follows_the_plan_order(target):
    columns = list(import_runs.SUCCESS_COLUMNS_BY_TARGET[target])
    assert columns[-1] == "billing_changes"
    fields = [SUCCESS_FIELD[c] for c in columns[:-1]]
    ok, known = _in_plan_order(target, fields)
    assert ok, known
    # the new and 💲 fields are ON the result file
    billing = set(import_runs.asset_billing_fields(target))
    assert billing <= set(fields), billing - set(fields)


def test_DOWNLOAD_the_failures_file_is_re_ordered_into_the_plan_order(ottumwa, ottumwa_admin):
    """An operator's file in a shuffled order comes back in the plan's order,
    every cell still under its own header, the two reason columns last."""
    with tenant_ctx(ottumwa):
        _estate(ottumwa_admin)
        labels = _labels(import_runs.TARGET_ASSETS_DEVICES)
        shuffled = ["purchase_cost", "service", "serial_no", "type", "external_ref"]
        header = [labels[f] for f in shuffled]
        content = _csv(
            header,
            [
                {
                    labels["purchase_cost"]: "12.00",
                    labels["service"]: "electricity-nope",
                    labels["serial_no"]: "SER-1",
                    labels["type"]: "container_cart",
                    labels["external_ref"]: "FAIL-1",
                }
            ],
        )
        run_id = _stages(ottumwa_admin, import_runs.TARGET_ASSETS_DEVICES, content)
        _load(ottumwa_admin, run_id)
        rows = _read_csv(run_id, "failures")
        by_label = {v: k for k, v in labels.items()}
        fields = [by_label[h] for h in rows[0][:-2]]
        assert fields == [f for f in PLAN_DEVICES if f in shuffled]
        assert rows[0][-2:] == ["why_it_failed", "how_to_fix_it"]
        cells = dict(zip(rows[0], rows[1]))
        assert cells[labels["serial_no"]] == "SER-1"
        assert cells[labels["purchase_cost"]] == "12.00"


# ══════════════════════════════════════════════════════════════════════════
# U3/U6 — one test per NEW column: the header maps, the value is written
# ══════════════════════════════════════════════════════════════════════════


def _one_meter(actor, target, extra, unit_label=None, ext="NEW-1", **kw):
    row = {"external_ref": ext, "service": "water", **extra}
    if unit_label:
        row["unit_ref"] = unit_label
    run_id = _stages(actor, target, _file(target, [row]))
    assert _problems(run_id) == {}, _problems(run_id)
    _load(actor, run_id)
    return _asset(ext)


@pytest.mark.parametrize(
    "target,field,cell,column,expected",
    [
        (import_runs.TARGET_ASSETS_METERS, "unit", "ccf", "unit", "ccf"),
        (import_runs.TARGET_ASSETS_METERS, "net_metering", "yes", "net_metering", True),
        (import_runs.TARGET_ASSETS_METERS, "register_digits", "6", "register_digits", 6),
        (import_runs.TARGET_ASSETS_SUBMETERS, "unit", "ccf", "unit", "ccf"),
        (
            import_runs.TARGET_ASSETS_SUBMETERS,
            "allocation_rule",
            "Split equally",
            "allocation_rule",
            "equal",
        ),
        (
            import_runs.TARGET_ASSETS_SUBMETERS,
            "loss_tolerance_pct",
            "5",
            "loss_tolerance_pct",
            Decimal("5"),
        ),
        (import_runs.TARGET_ASSETS_SUBMETERS, "register_digits", "10", "register_digits", 10),
    ],
)
def test_U6_each_new_meter_column_is_written(
    ottumwa, ottumwa_admin, target, field, cell, column, expected
):
    with tenant_ctx(ottumwa):
        units = _estate(ottumwa_admin)
        extra = {field: cell}
        if target == import_runs.TARGET_ASSETS_SUBMETERS:
            from apps.assets import services as asset_services

            parent = asset_services.create_asset_for_unit(
                actor=ottumwa_admin,
                unit_id=units[-1][1]["id"],
                service_point_id=None,
                payload={"type": "meter", "service": "water", "read_method": "ami"},
            )
            extra["parent_asset_no"] = parent["asset_no"]
        asset = _one_meter(ottumwa_admin, target, extra)
        assert getattr(asset, column) == expected


def test_U6_device_service_size_and_uom_are_written_and_seat_on_the_trash_point(
    ottumwa, ottumwa_admin
):
    with tenant_ctx(ottumwa):
        units = _estate(ottumwa_admin)
        label = units[0][1]["label"]
        row = {
            "type": "container_cart",
            "external_ref": "CART-1",
            "unit_ref": label,
            "service": "trash",
            "size_class": "CART-64",
            "unit": "",
        }
        run_id = _stages(ottumwa_admin, import_runs.TARGET_ASSETS_DEVICES, _file(
            import_runs.TARGET_ASSETS_DEVICES, [row]))  # fmt: skip
        assert _problems(run_id) == {}, _problems(run_id)
        _load(ottumwa_admin, run_id)
        cart = _asset("CART-1")
        assert cart.size_class == "CART-64"
        assert cart.service_point is not None
        assert cart.service_point.service.code == "trash"


def test_U6_device_parent_links_to_a_meter_of_the_same_service(ottumwa, ottumwa_admin):
    from apps.assets import services as asset_services

    with tenant_ctx(ottumwa):
        units = _estate(ottumwa_admin)
        meter = asset_services.create_asset_for_unit(
            actor=ottumwa_admin,
            unit_id=units[0][1]["id"],
            service_point_id=None,
            payload={"type": "meter", "service": "water", "read_method": "ami"},
        )
        row = {
            "type": "backflow",
            "external_ref": "BF-1",
            "unit_ref": units[0][1]["label"],
            "service": "water",
            "parent_asset_no": meter["asset_no"],
        }
        target = import_runs.TARGET_ASSETS_DEVICES
        run_id = _stages(ottumwa_admin, target, _file(target, [row]))
        assert _problems(run_id) == {}, _problems(run_id)
        _load(ottumwa_admin, run_id)
        assert _asset("BF-1").parent_asset.asset_no == meter["asset_no"]


# ══════════════════════════════════════════════════════════════════════════
# The named cases
# ══════════════════════════════════════════════════════════════════════════


def test_U12_two_carts_uploaded_on_the_devices_sheet_are_COUNTED_on_the_unit(
    ottumwa, ottumwa_admin
):
    """The bill multiplies this count. `2 x ($15.00 + $3.00) = $36.00` needs
    base-per-asset (`DEF-BIL-8095`, not landed) — the COUNT is this lane's."""
    with tenant_ctx(ottumwa):
        units = _estate(ottumwa_admin)
        unit = units[0][1]
        rows = [
            {"type": "container_cart", "external_ref": f"CART-{n}", "unit_ref": unit["label"],
             "service": "trash", "size_class": "CART-64"}
            for n in (1, 2)
        ]  # fmt: skip
        target = import_runs.TARGET_ASSETS_DEVICES
        run_id = _stages(ottumwa_admin, target, _file(target, rows))
        assert _problems(run_id) == {}
        _load(ottumwa_admin, run_id)
        today = metering_seams.tenant_today()
        assert asset_selectors.billable_asset_count(unit["id"], "trash", today) == 2


def test_DEF_AST_8360_a_devices_receipt_never_says_the_carts_are_wired_to_no_services(
    ottumwa, ottumwa_admin
):
    """The U14 browser walk: two carts seated on the trash point, and the
    receipt drew *"Wired to no services: 2"* because `with_services` (an
    accounts-only figure) was sent as `0` for every target. Absent = not said."""
    with tenant_ctx(ottumwa):
        unit = _estate(ottumwa_admin)[0][1]
        rows = [
            {"type": "container_cart", "external_ref": f"CART-{n}", "unit_ref": unit["label"],
             "service": "trash", "size_class": "CART-64"}
            for n in (1, 2)
        ]  # fmt: skip
        target = import_runs.TARGET_ASSETS_DEVICES
        receipt = _load(ottumwa_admin, _stages(ottumwa_admin, target, _file(target, rows)))
        assert receipt["counts"]["created"] == 2
        assert "with_services" not in receipt["receipt"]
        assert _asset("CART-1").service_point.service.code == "trash"


def test_U12_a_size_from_another_services_list_is_refused_by_name(ottumwa, ottumwa_admin):
    with tenant_ctx(ottumwa):
        units = _estate(ottumwa_admin)
        row = {"type": "container_cart", "external_ref": "CART-W", "service": "trash",
               "unit_ref": units[0][1]["label"], "size_class": "W-58"}  # fmt: skip
        target = import_runs.TARGET_ASSETS_DEVICES
        problems = _problems(_stages(ottumwa_admin, target, _file(target, [row])))
        assert "W-58 is a size for Water, not for Trash." in problems[1]


def test_U12_a_blank_unit_of_measure_takes_the_services_default(ottumwa, ottumwa_admin):
    with tenant_ctx(ottumwa):
        units = _estate(ottumwa_admin)
        row = {"type": "container_cart", "external_ref": "CART-U", "service": "trash",
               "unit_ref": units[0][1]["label"], "unit": ""}  # fmt: skip
        target = import_runs.TARGET_ASSETS_DEVICES
        run_id = _stages(ottumwa_admin, target, _file(target, [row]))
        assert _problems(run_id) == {}
        _load(ottumwa_admin, run_id)
        default = metering_seams.service_default_uom("trash")
        assert default
        assert _asset("CART-U").unit == default


def test_U12_three_problems_on_one_row_are_all_reported(ottumwa, ottumwa_admin):
    """Wrong-service size, a unit not on the list, a parent not on file."""
    with tenant_ctx(ottumwa):
        units = _estate(ottumwa_admin)
        row = {"type": "container_cart", "external_ref": "CART-3P", "service": "trash",
               "unit_ref": units[0][1]["label"], "size_class": "W-58",
               "unit": "furlongs", "parent_asset_no": "M-NOPE"}  # fmt: skip
        target = import_runs.TARGET_ASSETS_DEVICES
        problem = _problems(_stages(ottumwa_admin, target, _file(target, [row])))[1]
        assert "W-58 is a size for Water, not for Trash." in problem
        assert "furlongs is not a unit of measure" in problem
        assert "M-NOPE was not loaded" in problem


def test_U5_a_unit_without_the_devices_service_refuses_the_row_by_name(
    ottumwa, ottumwa_admin
):
    with tenant_ctx(ottumwa):
        premises = make_premises(
            ottumwa_admin, address_line="9 Water Only Rd", city="Ottumwa", state="IA",
            postal_code="52501", services_available=["water"],
        )  # fmt: skip
        unit = make_unit(ottumwa_admin, premises["id"], label="Only Water")
        row = {"type": "container_cart", "external_ref": "CART-NS", "service": "trash",
               "unit_ref": unit["label"]}  # fmt: skip
        target = import_runs.TARGET_ASSETS_DEVICES
        problems = _problems(_stages(ottumwa_admin, target, _file(target, [row])))
        assert "Unit Only Water has no Trash service." in problems[1]


@pytest.mark.parametrize(
    "field,cell,sentence",
    [
        ("register_digits", "3", "3 register digits is outside 4 to 10."),
        ("allocation_rule", "bogus", "bogus is not an allocation rule."),
        ("loss_tolerance_pct", "120", "above 100%"),
    ],
)
def test_U4_submeter_range_and_list_checks(ottumwa, ottumwa_admin, field, cell, sentence):
    from apps.assets import services as asset_services

    with tenant_ctx(ottumwa):
        units = _estate(ottumwa_admin)
        parent = asset_services.create_asset_for_unit(
            actor=ottumwa_admin,
            unit_id=units[-1][1]["id"],
            service_point_id=None,
            payload={"type": "meter", "service": "water", "read_method": "ami"},
        )
        row = {"external_ref": "SUB-X", "service": "water",
               "parent_asset_no": parent["asset_no"], field: cell}  # fmt: skip
        target = import_runs.TARGET_ASSETS_SUBMETERS
        problems = _problems(_stages(ottumwa_admin, target, _file(target, [row])))
        assert sentence in problems[1]


def test_U12_re_upload_OVERRIDES_billing_fields_audited_and_forward_only(
    ottumwa, ottumwa_admin, audit_rows
):
    """PO: *"we need to override it in case of upload"* — and BR-AST-012 kept:
    audited before/after, a stored read never restated, the result file lists
    the change old → new."""
    with tenant_ctx(ottumwa):
        units = _estate(ottumwa_admin)
        target = import_runs.TARGET_ASSETS_METERS
        first = {"external_ref": "OVR-1", "service": "water", "multiplier": "1",
                 "size_class": "W-58", "unit_ref": units[0][1]["label"],
                 "install_date": "2026-01-01"}  # fmt: skip
        run_id = _stages(ottumwa_admin, target, _file(target, [first]))
        assert _problems(run_id) == {}
        _load(ottumwa_admin, run_id)
        meter = _asset("OVR-1")
        metering_services.capture_opening_read(
            asset_id=meter.id, value="100", read_at="2026-01-02", actor=ottumwa_admin
        )
        read = metering_models.MeterRead.objects.get(asset_id=meter.id)
        stored = (read.current_value, read.multiplier, read.unit)

        second = {"asset_no": meter.asset_no, "external_ref": "OVR-1", "service": "water",
                  "multiplier": "2", "size_class": "W-2"}  # fmt: skip
        run2 = _stages(ottumwa_admin, target, _file(target, [second]), write_mode="upsert")
        assert _problems(run2) == {}, _problems(run2)
        _load(ottumwa_admin, run2, write_mode="upsert")

        meter.refresh_from_db()
        assert meter.multiplier == Decimal("2")
        assert meter.size_class == "W-2"
        # forward-only: the stored read is exactly what it was
        read = metering_models.MeterRead.objects.get(asset_id=meter.id)
        assert (read.current_value, read.multiplier, read.unit) == stored
        # audited before/after
        edits = [
            r for r in audit_rows
            if r["action"] == "asset.updated" and str(r["entity_id"]) == str(meter.id)
        ]
        assert edits, "the override is audited"
        assert edits[-1]["before"]["multiplier"] != edits[-1]["after"]["multiplier"]
        # listed per asset in the result file
        rows = _read_csv(run2, "successes")
        cells = dict(zip(rows[0], rows[1]))
        # `DEF-AST-8363`: the column is headed in words, like the template.
        assert "Multiplier: 1 → 2" in cells["Billing changes"]
        assert "Connection size: W-58 → W-2" in cells["Billing changes"]


def test_U7_a_re_upload_never_moves_or_re_types_an_asset(ottumwa, ottumwa_admin):
    """Insert-only columns stay insert-only: the unit is the Reassign screen's."""
    with tenant_ctx(ottumwa):
        units = _estate(ottumwa_admin)
        target = import_runs.TARGET_ASSETS_METERS
        run_id = _stages(ottumwa_admin, target, _file(target, [
            {"external_ref": "STAY-1", "service": "water",
             "unit_ref": units[0][1]["label"], "install_date": "2026-01-01"}]))  # fmt: skip
        _load(ottumwa_admin, run_id)
        meter = _asset("STAY-1")
        run2 = _stages(ottumwa_admin, target, _file(target, [
            {"asset_no": meter.asset_no, "external_ref": "STAY-1", "service": "water",
             "unit_ref": units[1][1]["label"]}]), write_mode="upsert")  # fmt: skip
        _load(ottumwa_admin, run2, write_mode="upsert")
        seat = asset_models.AssetAssignment.objects.get(asset=meter, to_date__isnull=True)
        assert str(seat.unit_id) == str(units[0][1]["id"])


def test_allocation_rule_resolver_takes_code_or_words():
    assert import_rules.allocation_rule_code("RUBS") == "rubs"
    assert import_rules.allocation_rule_code("By floor area") == "sqft"
    assert import_rules.allocation_rule_code("nope") is None
    assert import_rules.allocation_rule_code("") is None
