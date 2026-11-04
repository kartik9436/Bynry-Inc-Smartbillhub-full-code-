# ── Trace ──────────────────────────────────────────────
# Story:    US-AST-007 (S53 log repair/inspection/test + status transition) ·
#           US-AST-008 (S54 retire — terminal) · US-AST-009 (S55 reassign
#           unit ↔ inventory, sub-meter rules, bulk assign)
# Rules:    BR-AST-018 (append-only log; test updates last_test_date) ·
#           BR-AST-020 (exactly the A5 v4 transitions; retired terminal) ·
#           BR-AST-021 (retire needs reason + date; closes the assignment) ·
#           BR-AST-022 (to-unit active / to-inventory inventory; final read) ·
#           BR-AST-030 (no un-retire — recreate with a linked audit note) ·
#           BR-AST-032 (retire = System Admin only) · BR-AST-036/038 (bulk
#           assign is inventory→unit only) · BR-AST-037 (sub-meter moves)
# Journeys: T4-15 (meter swap + final read) · T4-16 (independent sub-meter move)
# Note:     BR-AST-022's final-read CAPTURE is WIRED (CR-028 debt sweep D5,
#           2026-08-22): metering publishes capture_final_read and the read
#           commits atomically with the move. From W1 until the sweep it was
#           refused, not faked — tc1 below asserted that refusal then; the
#           end-to-end truth now lives in tests/test_cr028_final_read_capture.py
#           and tc1 asserts the wired atomicity.
# ───────────────────────────────────────────────────────
"""US-AST-007 / US-AST-008 / US-AST-009 — the asset lifecycle modals."""

import pytest

from apps.assets import models, selectors, services
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import make_asset, make_premises, make_unit, tenant_ctx

pytestmark = pytest.mark.django_db


def a_unit(actor, label="Unit A", address="1408 Elm Street"):
    premise = make_premises(actor, address_line=address)
    return make_unit(actor, premise["id"], label=label, services=["electric", "water"])


def assigned_meter(actor, unit, asset_no="M-4204", **overrides):
    payload = {
        "asset_no": asset_no,
        "service": "electric",
        "unit_id": unit["id"],
        "install_date": "2026-01-01",
    }
    payload.update(overrides)
    return make_asset(actor, **payload)


# ── US-AST-007 · S53 log repair / inspection / test ─────────────────────────
def test_us_ast_007_tc1__repair_walks_the_legal_transition_with_audit(brazos, dana, audit_rows):
    with tenant_ctx(brazos):
        unit = a_unit(dana)
        asset = assigned_meter(dana, unit)
        services.log_maintenance(
            dana, asset["id"], {"kind": "inspection", "detail": "flagged", "status": "needs_repair"}
        )
        result = services.log_maintenance(
            dana,
            asset["id"],
            {"kind": "repair", "detail": "Register head replaced", "status": "in_repair"},
        )
    assert result["resulting_status"] == "in_repair"
    actions = [r["action"] for r in audit_rows]
    assert "asset.maintenance_logged" in actions and "asset.status_changed" in actions


def test_us_ast_007_tc2__the_billing_clerk_may_complete_a_repair(brazos, dana, marcus):
    """BR-AST-038: repair transitions are performable by the Billing Clerk."""
    with tenant_ctx(brazos):
        unit = a_unit(dana)
        asset = assigned_meter(dana, unit)
        services.log_maintenance(
            dana, asset["id"], {"kind": "inspection", "detail": "flag", "status": "needs_repair"}
        )
        services.log_maintenance(
            marcus, asset["id"], {"kind": "repair", "detail": "start", "status": "in_repair"}
        )
        fixed = services.log_maintenance(
            marcus, asset["id"], {"kind": "repair", "detail": "fixed", "status": "active"}
        )
        # `asset_list` is a QUERYSET from 2026-09-12 (`DEF-MET-4951`), so it is
        # materialised HERE, inside the tenant context. Asserting on the lazy
        # object outside the block would run the SQL with no `app.tenant_id`
        # set, which under RLS yields ZERO ROWS AND NO ERROR (`DEF-2734`'s
        # shape) — and would pass anyway on the sqlite the suite runs, which
        # is hard-won law 14 exactly.
        listed = list(selectors.asset_list(filters={"status": "needs_repair"}))
    assert fixed["asset"]["status"] == "active" and listed == []


def test_us_ast_007_tc3__inspection_can_flag_an_active_asset(brazos, dana):
    with tenant_ctx(brazos):
        unit = a_unit(dana)
        asset = assigned_meter(dana, unit, asset_no="M-4021")
        result = services.log_maintenance(
            dana, asset["id"], {"kind": "inspection", "detail": "noisy", "status": "needs_repair"}
        )
    assert result["asset"]["status"] == "needs_repair"
    # BR-AST-006: the row-action set switches with the state.
    assert result["asset"]["actions"] == ["view", "log_repair", "reassign", "retire"]


def test_us_ast_007_tc5__illegal_transition_is_rejected_server_side(brazos, dana):
    """BR-AST-020: active → in_repair must pass through needs_repair."""
    with tenant_ctx(brazos):
        unit = a_unit(dana)
        asset = assigned_meter(dana, unit, asset_no="M-4021")
        with pytest.raises(errors.BizError) as caught:
            services.log_maintenance(
                dana, asset["id"], {"kind": "repair", "detail": "x", "status": "in_repair"}
            )
        assert models.Asset.objects.get(pk=asset["id"]).status.code == "active"
    assert caught.value.br_ref == "BR-AST-020"
    assert (caught.value.params["from"], caught.value.params["to"]) == ("active", "in_repair")


def test_us_ast_007_tc6__kind_and_detail_are_required(brazos, dana):
    with tenant_ctx(brazos):
        asset = make_asset(dana, asset_no="M-5099", service="electric", unit="kWh")
        with pytest.raises(errors.ValidationError) as caught:
            services.log_maintenance(dana, asset["id"], {"detail": ""})
        assert models.AssetMaintenance.objects.filter(tenant=brazos).count() == 0
    fields = {e["field"] for e in caught.value.field_errors}
    assert fields == {"kind", "detail"}


@pytest.mark.isolation
def test_us_ast_007_tc7__isolation_maintenance_never_crosses_tenants(brazos, dana, lonestar, erin):
    with tenant_ctx(brazos):
        unit = a_unit(dana)
        asset = assigned_meter(dana, unit)
    with tenant_ctx(lonestar):
        with pytest.raises(errors.NotFoundError):
            services.log_maintenance(erin, asset["id"], {"kind": "repair", "detail": "x"})
    with tenant_ctx(brazos):
        assert models.AssetMaintenance.objects.filter(tenant=brazos).count() == 0


# ── US-AST-008 · S54 retire ─────────────────────────────────────────────────
def test_us_ast_008_tc1__retire_closes_the_assignment_and_records_the_replacement(
    brazos, dana, audit_rows
):
    with tenant_ctx(brazos):
        unit = a_unit(dana, label="200", address="500 Main")
        asset = assigned_meter(dana, unit)
        replacement = make_asset(dana, asset_no="M-5100", service="electric", unit="kWh")
        result = services.retire_asset(
            dana,
            asset["id"],
            {"reason": "failed", "retire_date": "2026-08-08", "replaced_by": "M-5100"},
        )
        history = selectors.assignments(asset["id"])
    assert result["status"] == "retired" and result["retire_reason"] == "failed"
    assert result["replaced_by"] == replacement["asset_no"]
    assert history[0]["to_date"] == "2026-08-08"  # BR-AST-021
    assert "asset.retired" in [r["action"] for r in audit_rows]


def test_us_ast_008_tc2__retired_assets_leave_active_views_but_stay_queryable(brazos, dana):
    with tenant_ctx(brazos):
        unit = a_unit(dana)
        asset = assigned_meter(dana, unit)
        services.retire_asset(dana, asset["id"], {"reason": "end_of_life"})
        # `asset_list` is a QUERYSET from 2026-09-12 (`DEF-MET-4951`), so it is
        # materialised HERE, inside the tenant context. Asserting on the lazy
        # object outside the block would run the SQL with no `app.tenant_id`
        # set, which under RLS yields ZERO ROWS AND NO ERROR (`DEF-2734`'s
        # shape) — and would pass anyway on the sqlite the suite runs, which
        # is hard-won law 14 exactly.
        default_rows = list(selectors.asset_list())
        retired = list(selectors.asset_list(filters={"status": "retired"}))
        detail = selectors.asset_detail(asset["id"])
    assert default_rows == [] and [a.asset_no for a in retired] == ["M-4204"]
    assert detail["actions"] == ["view"]  # BR-AST-006 retired = View only


def test_us_ast_008_tc3__an_unassigned_inventory_asset_can_be_retired(brazos, dana):
    with tenant_ctx(brazos):
        asset = make_asset(dana, asset_no="BAT-0904", type="battery", unit=None)
        result = services.retire_asset(dana, asset["id"], {"reason": "removed"})
    assert result["status"] == "retired"


def test_us_ast_008_tc4__retired_is_terminal_for_every_action(brazos, dana):
    with tenant_ctx(brazos):
        unit = a_unit(dana)
        asset = assigned_meter(dana, unit)
        services.retire_asset(dana, asset["id"], {"reason": "failed"})
        for call in (
            lambda: services.log_maintenance(
                dana, asset["id"], {"kind": "repair", "detail": "x", "status": "active"}
            ),
            lambda: services.reassign_asset(
                dana, asset["id"], {"to_inventory": True, "record_final_read": False}
            ),
            lambda: services.update_asset(dana, asset["id"], {"seal_no": "X"}),
            lambda: services.retire_asset(dana, asset["id"], {"reason": "failed"}),
        ):
            with pytest.raises(errors.BizError) as caught:
                call()
            assert caught.value.code == errors.BIZ_IMMUTABLE


def test_us_ast_008_tc5__replacement_must_be_a_living_same_tenant_asset(brazos, dana):
    with tenant_ctx(brazos):
        unit = a_unit(dana)
        asset = assigned_meter(dana, unit)
        gone = make_asset(dana, asset_no="M-9000", service="electric", unit="kWh")
        services.retire_asset(dana, gone["id"], {"reason": "end_of_life"})
        with pytest.raises(errors.ValidationError) as unknown:
            services.retire_asset(
                dana, asset["id"], {"reason": "replaced", "replaced_by": "M-9999"}
            )
        with pytest.raises(errors.ValidationError) as retired:
            services.retire_asset(
                dana, asset["id"], {"reason": "replaced", "replaced_by": "M-9000"}
            )
    assert unknown.value.field_errors[0]["message_key"] == "assets.replacement_unknown"
    assert retired.value.field_errors[0]["message_key"] == "assets.replacement_is_retired"


def test_us_ast_008_tc6__a_retired_asset_can_never_be_hard_deleted(brazos, dana):
    with tenant_ctx(brazos):
        unit = a_unit(dana)
        asset = assigned_meter(dana, unit)
        services.retire_asset(dana, asset["id"], {"reason": "failed"})
        with pytest.raises(errors.BizError) as caught:
            services.delete_asset(dana, asset["id"])
    assert caught.value.br_ref == "BR-AST-013"
    assert caught.value.params["alternative"] == "retire"


def test_us_ast_008_tc8__a_mistaken_retirement_is_corrected_by_recreation(brazos, dana, audit_rows):
    """BR-AST-030: no un-retire path exists anywhere; the new asset's audit
    trail carries a LINKED note referencing the retired one."""
    with tenant_ctx(brazos):
        asset = make_asset(dana, asset_no="BAT-0904", type="battery", unit=None)
        services.retire_asset(dana, asset["id"], {"reason": "removed"})
        recreated = services.create_asset(
            dana,
            {
                "type": "battery",
                "asset_no": "BAT-0904-R",
                "recreated_from_asset_id": asset["id"],
            },
        )
    assert not hasattr(services, "unretire_asset")
    link = [r for r in audit_rows if r["action"] == "asset.recreated_from_retired"][0]
    assert link["after"]["replaces_retired_asset_id"] == asset["id"]
    assert recreated["status"] == "inventory"


def test_us_ast_008_tc9__retire_is_system_admin_only(brazos, dana, marcus):
    with tenant_ctx(brazos):
        asset = make_asset(dana, asset_no="M-4310", service="electric", unit="kWh")
        with pytest.raises(errors.AuthError) as caught:
            services.retire_asset(marcus, asset["id"], {"reason": "failed"})
    assert caught.value.code == errors.AUTH_PERMISSION_DENIED  # BR-AST-032


@pytest.mark.isolation
def test_us_ast_008_tc7__isolation_replacement_cannot_cross_tenants(brazos, dana, lonestar, erin):
    with tenant_ctx(brazos):
        replacement = make_asset(dana, asset_no="M-5100", service="electric", unit="kWh")
    with tenant_ctx(lonestar):
        mine = make_asset(erin, asset_no="W-1000", service="water", unit="kgal")
        with pytest.raises(errors.ValidationError) as caught:
            services.retire_asset(
                erin, mine["id"], {"reason": "replaced", "replaced_by": replacement["id"]}
            )
    assert caught.value.field_errors[0]["message_key"] == "assets.replacement_unknown"


# ── US-AST-009 · S55 reassign ───────────────────────────────────────────────
def test_us_ast_009_tc1__final_read_capture_is_atomic_with_the_move(brazos, dana):
    """BR-AST-022: capture and move are ONE transaction — WIRED by the CR-028
    debt sweep (D5). Until 2026-08-22 this test asserted the refusal
    (BIZ-COMPLETENESS) because `capture_final_read` did not exist; the move
    now commits WITH its committed manual read, and the closing assignment
    row carries the read's id. The full end-to-end matrix (date input, error
    refusals, child strip) lives in tests/test_cr028_final_read_capture.py."""
    from apps.metering import models as met_models

    with tenant_ctx(brazos):
        first = a_unit(dana)
        second = a_unit(dana, label="224", address="2200 Riverside")
        # make_asset directly: assigned_meter's positional `unit` (the UNIT
        # row) collides with the payload's `unit` (the UoM — rule 3).
        asset = make_asset(
            dana,
            asset_no="M-4022",
            service="water",
            unit="kgal",
            unit_id=first["id"],
            install_date="2026-01-01",
        )
        result = services.reassign_asset(
            dana,
            asset["id"],
            {
                "unit_id": second["id"],
                "effective_date": "2026-08-08",
                "final_read_value": "1421.0",
            },
        )
        history = selectors.assignments(asset["id"])
        read = met_models.MeterRead.objects.get(id=result["final_read"]["id"])
    assert result["assigned_unit_id"] == second["id"]
    closed = [row for row in history if row["to_date"] is not None]
    assert len(closed) == 1 and str(closed[0]["final_read_id"]) == result["final_read"]["id"]
    assert read.source == "manual" and read.source_detail == "final_read"
    assert read.unit == "kgal"  # rule 3 — the asset's OWN UoM


def test_us_ast_009_tc2__assigning_from_inventory_opens_the_first_row(brazos, dana):
    with tenant_ctx(brazos):
        unit = a_unit(dana, label="Bldg 1", address="77 Industrial Way")
        asset = make_asset(dana, asset_no="M-5099", service="electric", unit="kWh")
        result = services.reassign_asset(
            dana,
            asset["id"],
            {"unit_id": unit["id"], "effective_date": "2026-08-08", "service": "electric"},
        )
        # `asset_list` is a QUERYSET from 2026-09-12 (`DEF-MET-4951`), so it is
        # materialised HERE, inside the tenant context. Asserting on the lazy
        # object outside the block would run the SQL with no `app.tenant_id`
        # set, which under RLS yields ZERO ROWS AND NO ERROR (`DEF-2734`'s
        # shape) — and would pass anyway on the sqlite the suite runs, which
        # is hard-won law 14 exactly.
        unassigned = list(selectors.asset_list(filters={"status": "unassigned"}))
    assert result["status"] == "active"  # BR-AST-020 inventory →(assign)→ active
    assert unassigned == []


def test_us_ast_009_tc3__moving_to_inventory_returns_the_status(brazos, dana):
    with tenant_ctx(brazos):
        unit = a_unit(dana)
        asset = assigned_meter(dana, unit, asset_no="M-4310")
        result = services.reassign_asset(
            dana, asset["id"], {"to_inventory": True, "record_final_read": False}
        )
        history = selectors.assignments(asset["id"])
        # `asset_list` is a QUERYSET from 2026-09-12 (`DEF-MET-4951`), so it is
        # materialised HERE, inside the tenant context. Asserting on the lazy
        # object outside the block would run the SQL with no `app.tenant_id`
        # set, which under RLS yields ZERO ROWS AND NO ERROR (`DEF-2734`'s
        # shape) — and would pass anyway on the sqlite the suite runs, which
        # is hard-won law 14 exactly.
        unassigned = list(selectors.asset_list(filters={"status": "unassigned"}))
    assert result["status"] == "inventory"  # BR-AST-022
    assert history[0]["to_date"] is not None
    assert [a.asset_no for a in unassigned] == ["M-4310"]


def test_us_ast_009_tc4__non_measuring_assets_move_without_a_read(brazos, dana):
    with tenant_ctx(brazos):
        first = a_unit(dana)
        second = a_unit(dana, label="224", address="2200 Riverside")
        asset = make_asset(
            dana,
            asset_no="COM-4420",
            type="comms",
            unit=None,
            unit_id=first["id"],
            install_date="2026-01-01",
        )
        result = services.reassign_asset(
            dana, asset["id"], {"unit_id": second["id"], "effective_date": "2026-08-08"}
        )
    assert result["assigned_unit_id"] == second["id"]


def test_us_ast_009_tc5__effective_date_before_the_current_from_date_is_refused(brazos, dana):
    with tenant_ctx(brazos):
        first = a_unit(dana)
        second = a_unit(dana, label="224", address="2200 Riverside")
        asset = make_asset(
            dana,
            asset_no="COM-4420",
            type="comms",
            unit=None,
            unit_id=first["id"],
            install_date="2026-06-01",
        )
        with pytest.raises(errors.ValidationError) as caught:
            services.reassign_asset(
                dana, asset["id"], {"unit_id": second["id"], "effective_date": "2026-01-01"}
            )
        assert len(selectors.assignments(asset["id"])) == 1  # BR-AST-017 no overlap
    assert caught.value.field_errors[0]["message_key"] == "assets.effective_before_from_date"


def test_us_ast_009_tc8__independent_sub_meter_move_is_allowed_with_a_warning(brazos, dana):
    with tenant_ctx(brazos):
        home = a_unit(dana, label="102", address="Vega Apts")
        target = a_unit(dana, label="105", address="Vega Apts 105")
        master = make_asset(
            dana,
            asset_no="M-MASTER-12",
            service="electric",
            unit_id=home["id"],
            install_date="2026-01-01",
        )
        child = make_asset(
            dana,
            asset_no="SM-8801",
            type="sub_meter",
            service="electric",
            parent_asset_no=master["asset_no"],
            unit_id=home["id"],
            install_date="2026-01-01",
        )
        result = services.reassign_asset(
            dana,
            child["id"],
            {"unit_id": target["id"], "effective_date": "2026-08-08", "record_final_read": False},
        )
    warning = result["warnings"][0]
    assert warning["br_ref"] == "BR-AST-037" and warning["parent"] == "M-MASTER-12"
    assert result["assigned_unit_id"] == target["id"]  # the move still happens


def test_us_ast_009_tc9__moving_a_parent_moves_its_children_by_default(brazos, dana):
    with tenant_ctx(brazos):
        home = a_unit(dana, label="102", address="Vega Apts")
        target = a_unit(dana, label="105", address="Vega Apts 105")
        master = make_asset(
            dana,
            asset_no="M-MASTER-12",
            service="electric",
            unit_id=home["id"],
            install_date="2026-01-01",
        )
        for asset_no in ("SM-8801", "SM-8802"):
            make_asset(
                dana,
                asset_no=asset_no,
                type="sub_meter",
                service="electric",
                parent_asset_no=master["asset_no"],
                unit_id=home["id"],
                install_date="2026-01-01",
            )
        moved = services.reassign_asset(
            dana,
            master["id"],
            {"unit_id": target["id"], "effective_date": "2026-08-08", "record_final_read": False},
        )
        declined_target = a_unit(dana, label="106", address="Vega Apts 106")
        declined = services.reassign_asset(
            dana,
            master["id"],
            {
                "unit_id": declined_target["id"],
                "effective_date": "2026-08-09",
                "record_final_read": False,
                "move_children": False,
            },
        )
    assert {c["asset_no"] for c in moved["children_moved"]} == {"SM-8801", "SM-8802"}
    assert declined["children_moved"] == []
    assert declined["warnings"][-1]["code"] == "children_not_moved"  # BR-AST-037


def test_us_ast_009_tc10__bulk_assign_is_inventory_to_unit_only(brazos, dana, audit_rows):
    with tenant_ctx(brazos):
        target = a_unit(dana, label="Bldg 1", address="77 Industrial Way")
        occupied_unit = a_unit(dana)
        spare_a = make_asset(dana, asset_no="M-5099", service="electric", unit="kWh")
        spare_b = make_asset(dana, asset_no="BAT-0904", type="battery", unit=None)
        active = assigned_meter(dana, occupied_unit, asset_no="M-4021")
        result = services.bulk_assign(
            dana,
            {
                "effective_date": "2026-08-08",
                "assignments": [
                    {"asset_id": spare_a["id"], "unit_id": target["id"], "service": "electric"},
                    {"asset_id": spare_b["id"], "unit_id": target["id"]},
                    {"asset_id": active["id"], "unit_id": target["id"]},
                ],
            },
        )
    assert result["assigned"] == 2 and result["failed"] == 1
    # BR-AST-036/038: no bulk unit→unit path exists; the row names the reason.
    assert result["errors"][0]["reason"] == "not_inventory"
    assert result["errors"][0]["alternative"] == "single_reassign_or_file_import"
    assert "asset.bulk_assigned" in [r["action"] for r in audit_rows]


@pytest.mark.isolation
def test_us_ast_009_tc7__isolation_unit_picker_never_crosses_tenants(brazos, dana, lonestar, erin):
    with tenant_ctx(brazos):
        unit = a_unit(dana)
    with tenant_ctx(lonestar):
        mine = make_asset(erin, asset_no="W-1000", service="water", unit="kgal")
        with pytest.raises(errors.NotFoundError):
            services.reassign_asset(
                erin, mine["id"], {"unit_id": unit["id"], "record_final_read": False}
            )
