# ── Trace ──────────────────────────────────────────────
# Story:    US-AST-004 (S50 header + Overview, full specifications) ·
#           US-AST-006 (Assignment history, Maintenance & repairs, Audit tabs)
# Rules:    BR-AST-007 (Test-due chip DERIVED) · BR-AST-014 (extended specs are
#           capture-only) · BR-AST-015 (register_digits 1–9, DEFAULT 9) ·
#           BR-AST-017 (assignment history append-only, non-overlapping, one
#           current row) · BR-AST-018 (maintenance append-only; a test entry
#           updates last_test_date) · BR-AST-019 (Audit tab renders audit_log
#           and never writes) · BR-AST-039 (live billing chain) · BR-AST-044
#           (the S50 header block shows ALL THREE classifications: asset_type ·
#           meter_type · read_method)
# Note:     US-AST-005 (Reads tab) is NOT built in this lane — `meter_reads` is
#           the W2 reads lane's table (B2 r16 #4), so there is no read history
#           to render and none is invented. Reported in the build report.
# ───────────────────────────────────────────────────────
"""US-AST-004 / US-AST-006 — asset detail, history and maintenance reads."""

import pytest

from apps.assets import models, selectors, services
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import make_asset, make_premises, make_unit, tenant_ctx

pytestmark = pytest.mark.django_db


def a_unit(actor, label="Unit A", address="1408 Elm Street"):
    premise = make_premises(actor, address_line=address)
    return make_unit(actor, premise["id"], label=label, services=["electric", "water"])


def test_us_ast_004_tc1__overview_carries_the_extended_spec_set(brazos, dana):
    with tenant_ctx(brazos):
        unit = a_unit(dana)
        asset = make_asset(
            dana,
            asset_no="M-4021",
            type="net_meter",
            service="electric",
            multiplier="10",
            unit_id=unit["id"],
            install_date="2024-03-12",
            serial_no="3894-A2210",
            form_class="2S",
            register_digits=5,
            firmware_version="5.2.1",
            seal_no="TX-88121",
            warranty_end="2029-03-12",
            last_test_date="2026-06-02",
            test_interval_months=24,
            location_note="left side wall, behind gate",
        )
        detail = selectors.asset_detail(asset["id"])
    specs = detail["specs"]
    assert specs["form_class"] == "2S" and specs["register_digits"] == 5
    assert specs["firmware_version"] == "5.2.1" and specs["seal_no"] == "TX-88121"
    assert specs["warranty_end"] == "2029-03-12"
    assert specs["last_test_date"] == "2026-06-02" and specs["test_interval_months"] == 24
    assert specs["location_note"] == "left side wall, behind gate"
    assert detail["test_due"] is False  # 2026-06-02 + 24 mo has not elapsed


def test_us_ast_004_tc2__billing_chain_ends_honestly_at_the_unit(brazos, dana):
    """BR-AST-039: Premises → Unit → active Account. The account leg is null
    because the customers module owns no tables (W2) — never a fabricated one."""
    with tenant_ctx(brazos):
        unit = a_unit(dana)
        asset = make_asset(
            dana,
            asset_no="M-4021",
            service="electric",
            unit_id=unit["id"],
            install_date="2026-01-01",
        )
        chain = selectors.asset_detail(asset["id"])["billing_chain"]
    assert chain["premise_address"] == "1408 Elm Street" and chain["unit_label"] == "Unit A"
    assert chain["account"] is None


def test_us_ast_004_tc3__test_due_chip_shows_without_touching_the_stored_status(brazos, dana):
    with tenant_ctx(brazos):
        asset = make_asset(
            dana,
            asset_no="BF-3301",
            type="backflow",
            unit=None,
            last_test_date="2025-06-02",
            test_interval_months=12,
        )
        detail = selectors.asset_detail(asset["id"])
        stored = models.Asset.objects.get(pk=asset["id"])
    assert detail["test_due"] is True and stored.status.code == "inventory"
    assert detail["specs"]["register_digits"] == 9  # BR-AST-015 default


def test_us_ast_004_tc4__inventory_detail_reads_unassigned(brazos, dana):
    with tenant_ctx(brazos):
        asset = make_asset(dana, asset_no="BAT-0904", type="battery", unit=None)
        detail = selectors.asset_detail(asset["id"])
    assert detail["assigned"] is False and detail["billing_chain"]["unit_id"] is None
    assert detail["actions"] == ["assign", "edit", "delete"]


def test_us_ast_004_tc5__register_digits_bounds_and_default(brazos, dana):
    with tenant_ctx(brazos):
        asset = make_asset(dana, asset_no="M-5099", service="electric", unit="kWh")
        with pytest.raises(errors.ValidationError) as caught:
            services.update_asset(dana, asset["id"], {"register_digits": 0})
        with pytest.raises(errors.ValidationError):
            services.update_asset(dana, asset["id"], {"register_digits": "abc"})
        cleared = services.update_asset(dana, asset["id"], {"register_digits": ""})
    assert caught.value.field_errors[0]["message_key"] == "assets.register_digits_range"
    assert cleared["specs"]["register_digits"] if "specs" in cleared else True
    assert models.Asset.objects.get(pk=asset["id"]).register_digits == 9


def test_us_ast_004_tc6__unknown_asset_id_is_a_lawful_not_found(brazos):
    with tenant_ctx(brazos):
        with pytest.raises(errors.NotFoundError):
            selectors.asset_detail("00000000-0000-0000-0000-000000000000")
        with pytest.raises(errors.NotFoundError):
            selectors.asset_detail("not-a-uuid")


def test_us_ast_004_tc8__detail_header_carries_all_three_classifications(brazos, dana):
    """BR-AST-044 (PO 2026-08-09, "display them in meter details view"): the
    S50 header block carries asset_type AND meter_type AND read_method, each
    as code + display name. A non-measuring asset shows the classifications it
    honestly has — meter_type null, never an invented one."""
    with tenant_ctx(brazos):
        unit = a_unit(dana)
        meter = make_asset(
            dana,
            asset_no="M-4021",
            service="electric",
            unit="kWh",
            meter_type="ami",
            read_method="ami",
            unit_id=unit["id"],
            install_date="2026-01-01",
        )
        battery = make_asset(dana, asset_no="BAT-0904", type="battery", unit=None, read_method=None)
        detail = selectors.asset_detail(meter["id"])
        bare = selectors.asset_detail(battery["id"])
    assert detail["classifications"] == {
        "asset_type": {"code": "meter", "name": "Meter"},
        "meter_type": {"code": "ami", "name": "AMI"},
        "read_method": {"code": "ami", "name": "AMI"},
    }
    # The flat row keys the S49 list reads carry the same three, unchanged.
    assert (detail["type"], detail["meter_type"], detail["read_method"]) == ("meter", "ami", "ami")
    assert detail["meter_type_name"] == "AMI"
    assert bare["classifications"]["asset_type"] == {"code": "battery", "name": "Battery storage"}
    assert bare["classifications"]["meter_type"] is None
    assert bare["classifications"]["read_method"] is None


@pytest.mark.isolation
def test_us_ast_004_tc7__isolation_cross_tenant_detail_is_not_found(brazos, dana, lonestar, erin):
    with tenant_ctx(brazos):
        asset = make_asset(dana, asset_no="M-4021", service="electric", unit="kWh")
    with tenant_ctx(lonestar):
        mine = make_asset(erin, asset_no="M-4021", service="water", unit="kgal")
        with pytest.raises(errors.NotFoundError):
            selectors.asset_detail(asset["id"])
        assert selectors.asset_detail(mine["id"])["unit"] == "kgal"


# ── US-AST-006 · history tabs ───────────────────────────────────────────────
def test_us_ast_006_tc1__assignment_history_is_contiguous_and_non_overlapping(brazos, dana):
    with tenant_ctx(brazos):
        first = a_unit(dana)
        second = a_unit(dana, label="224", address="2200 Riverside")
        asset = make_asset(
            dana, asset_no="M-4022", service="water", unit_id=first["id"], install_date="2024-03-12"
        )
        services.reassign_asset(
            dana,
            asset["id"],
            {
                "unit_id": second["id"],
                "effective_date": "2026-08-08",
                "record_final_read": False,
            },
        )
        history = selectors.assignments(asset["id"])
    assert [(h["from_date"], h["to_date"]) for h in history] == [
        ("2026-08-08", None),
        ("2024-03-12", "2026-08-08"),
    ]
    assert history[0]["current"] is True and history[1]["current"] is False
    # BR-AST-017 records the acting USER — and since CR-028 AST-W2 T6 the
    # selector serves their display NAME, not the raw uuid (the deployed
    # W-5000 defect B16 §4.8 measured). staff_actor names the row role.title().
    assert history[0]["by"] == "System_Admin"


def test_us_ast_006_tc2__maintenance_log_lists_newest_first(brazos, dana):
    with tenant_ctx(brazos):
        unit = a_unit(dana)
        asset = make_asset(
            dana,
            asset_no="M-4021",
            service="electric",
            unit_id=unit["id"],
            install_date="2024-03-12",
        )
        services.log_maintenance(
            dana,
            asset["id"],
            {"kind": "inspection", "date": "2025-01-14", "detail": "Comms module replaced"},
        )
        services.log_maintenance(
            dana,
            asset["id"],
            {
                "kind": "inspection",
                "date": "2026-06-02",
                "detail": "Annual accuracy check — passed",
            },
        )
        rows = selectors.maintenance(asset["id"])
    assert [r["date"] for r in rows] == ["2026-06-02", "2025-01-14"]
    assert rows[0]["detail"] == "Annual accuracy check — passed"


def test_us_ast_006_tc3__every_asset_action_left_an_audit_row(brazos, dana, audit_rows):
    """BR-AST-019: the Audit tab renders audit_log; every lifecycle action,
    edit and maintenance entry must have written one."""
    with tenant_ctx(brazos):
        unit = a_unit(dana)
        asset = make_asset(
            dana,
            asset_no="M-4021",
            service="electric",
            unit_id=unit["id"],
            install_date="2026-01-01",
        )
        services.update_asset(dana, asset["id"], {"seal_no": "TX-88121"})
        services.log_maintenance(dana, asset["id"], {"kind": "inspection", "detail": "checked"})
    actions = [r["action"] for r in audit_rows if r["entity_type"] == "asset"]
    assert {"asset.created", "asset.updated", "asset.maintenance_logged"} <= set(actions)


def test_us_ast_006_tc4__a_test_entry_updates_last_test_date_and_clears_the_chip(brazos, dana):
    with tenant_ctx(brazos):
        asset = make_asset(
            dana,
            asset_no="BF-3301",
            type="backflow",
            unit=None,
            last_test_date="2025-06-02",
            test_interval_months=12,
        )
        assert selectors.asset_detail(asset["id"])["test_due"] is True
        services.log_maintenance(
            dana, asset["id"], {"kind": "test", "date": "2026-08-08", "detail": "annual test"}
        )
        after = selectors.asset_detail(asset["id"])
    assert after["specs"]["last_test_date"] == "2026-08-08"  # BR-AST-018
    assert after["test_due"] is False  # BR-AST-007 chip clears


def test_us_ast_006_tc5__history_rows_are_append_only(brazos, dana):
    """BR-AST-017/018: corrections are new rows — the module exposes no update
    or delete verb for either history table (a service-surface assertion)."""
    from apps.assets import api

    assert not hasattr(services, "update_maintenance")
    assert not hasattr(services, "delete_maintenance")
    assert not hasattr(services, "update_assignment")
    assert not hasattr(services, "delete_assignment")
    routes = {p.pattern._route for p in api.urlpatterns}
    assert "assets/<uuid:asset_id>/maintenance" in routes
    assert not any("assignments/" in r for r in routes)


@pytest.mark.isolation
def test_us_ast_006_tc6__isolation_history_never_crosses_tenants(brazos, dana, lonestar, erin):
    with tenant_ctx(brazos):
        unit = a_unit(dana)
        asset = make_asset(
            dana,
            asset_no="M-4021",
            service="electric",
            unit_id=unit["id"],
            install_date="2026-01-01",
        )
    with tenant_ctx(lonestar):
        with pytest.raises(errors.NotFoundError):
            selectors.assignments(asset["id"])
        with pytest.raises(errors.NotFoundError):
            selectors.maintenance(asset["id"])
