# ── Trace ──────────────────────────────────────────────
# Story:    US-AST-001 (S49 registry — 3 tabs, search, status filter) ·
#           US-AST-002 (S51 add a single asset) · US-AST-003 (edit specs;
#           delete only unreferenced inventory) · US-TEN-009 (S8 Reference-data
#           card grid: "Meter types 5", TC-1) · US-TEN-010 (per-list add/edit,
#           ci-duplicate refusal, per-tenant independence) · US-TEN-011
#           (system rows never deletable; a referenced row is locked)
# Rules:    BR-AST-001/004/005/006/007 · BR-AST-003/008/009/010/011 ·
#           BR-AST-012/013 · BR-AST-026 (3-identifier model) · BR-AST-031
#           (lifecycle stages = Reference data with behavior classes) ·
#           BR-AST-032 (roles) · BR-AST-033 (dup asset # hard / dup serial
#           warn) · BR-AST-042 (seeded Container/Cart + Modem/CPE) ·
#           BR-AST-043 (meter_types + read_methods are TWO separate seeded,
#           tenant-extensible lists; assets.read_method references the
#           read_methods catalog) · BR-AST-044 (an asset carries BOTH
#           classifications — asset_type AND meter_type — alongside
#           read_method; all three catalog FKs with PROTECT, meter_type
#           nullable; meter_type is a registry filter per BR-SHL-011) ·
#           BR-TEN-030/031/034/036 (ci-unique codes,
#           owner validates, delete lock, seeded + tenant-extensible)
# Journeys: J2 step 2 — "asset active on unit, UoM explicit, register digits set"
# Note:     The W1 migrations create `asset_types` / `asset_lifecycle_stages`
#           EMPTY and tenancy's provisioning fixture routes no entries for
#           them, so the assets lane seeds both idempotently from the ratified
#           sets (A5 v4 stages + BR-AST-004/009/042 types). Asserted below.
# ───────────────────────────────────────────────────────
"""US-AST-001 / US-AST-002 / US-AST-003 — the asset registry."""

import pytest

from django.db.models.deletion import ProtectedError

from apps.assets import lookups, models, selectors, services
from apps.tenancy import selectors as tenancy_selectors
from apps.tenancy import services as tenancy_services
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import (
    FakeUser,
    api_call,
    executive_actor,
    make_asset,
    make_premises,
    make_unit,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


def a_unit(actor, label="Unit A", address="1408 Elm Street"):
    premise = make_premises(actor, address_line=address)
    return make_unit(actor, premise["id"], label=label, services=["electric", "water"])


# ── the reference catalogs the registry keys off (BR-AST-031/004) ───────────
def test_us_ast_001_tc0__stage_and_type_catalogs_seed_idempotently(brazos, dana):
    with tenant_ctx(brazos):
        first = services.ensure_reference_catalogs()
        second = services.ensure_reference_catalogs()
        stages = {s["code"]: s for s in selectors.lifecycle_stages()}
        types = {t["code"]: t for t in selectors.asset_types()}
    # AMENDED 2026-08-10 (DEF-017): the four asset catalogs are now seeded by
    # PROVISIONING, routed tenancy -> metering -> assets from the platform
    # fixture, so ensure_reference_catalogs() finds them already there and
    # creates NOTHING on either call. That is a stronger statement of the same
    # law it always made — the catalog is idempotent whoever filled it — and
    # the ratified value set below is still asserted in full.
    assert first["asset_lifecycle_stages"] == 0 and second["asset_lifecycle_stages"] == 0
    assert len(stages) == len(services.SEED_LIFECYCLE_STAGES)
    # A5 v4 stage set with the BR-AST-031 behavior classes.
    assert {c: s["behavior_class"] for c, s in stages.items()} == {
        "inventory": "available",
        "active": "in_service",
        "needs_repair": "out_of_service",
        "in_repair": "out_of_service",
        "retired": "terminal",
    }
    assert all(s["is_system"] for s in stages.values())  # deactivatable, never deletable
    # BR-AST-004 tab partition + BR-AST-042 seeded device types.
    assert types["meter"]["category"] == "meters"
    assert types["sub_meter"]["category"] == "sub_meters"
    assert types["container_cart"]["category"] == "behind_the_meter"
    assert types["modem_cpe"]["category"] == "behind_the_meter"


def test_us_ast_001_tc1__meters_tab_lists_only_meters_and_net_meters(brazos, dana):
    with tenant_ctx(brazos):
        unit = a_unit(dana)
        make_asset(
            dana,
            asset_no="M-4021",
            type="net_meter",
            service="electric",
            multiplier="10",
            unit_id=unit["id"],
            install_date="2024-03-12",
        )
        make_asset(dana, asset_no="M-5099", service="electric", unit="kWh")  # inventory spare
        make_asset(dana, asset_no="BAT-0904", type="battery", unit=None)
        rows = [selectors.asset_dict(a) for a in selectors.asset_list(filters={"tab": "meters"})]
    assert [r["asset_no"] for r in rows] == ["M-4021", "M-5099"]  # asset_no A→Z default sort
    assert rows[0]["net_metering"] is True and rows[0]["multiplier"] == "10.000000"
    assert rows[1]["status"] == "inventory"
    # BR-AST-006: inventory rows offer Assign/Edit/Delete.
    assert rows[1]["actions"] == ["assign", "edit", "delete"]


def test_us_ast_001_tc2__sub_meters_tab_shows_the_parent(brazos, dana):
    with tenant_ctx(brazos):
        unit = a_unit(dana)
        master = make_asset(
            dana,
            asset_no="M-MASTER-12",
            service="electric",
            unit_id=unit["id"],
            install_date="2026-01-01",
        )
        make_asset(
            dana,
            asset_no="SM-8801",
            type="sub_meter",
            service="electric",
            parent_asset_no=master["asset_no"],
            unit_id=unit["id"],
            install_date="2026-01-01",
        )
        rows = [
            selectors.asset_dict(a) for a in selectors.asset_list(filters={"tab": "sub_meters"})
        ]
    assert [r["asset_no"] for r in rows] == ["SM-8801"]
    assert rows[0]["parent_asset_no"] == "M-MASTER-12"


def test_us_ast_001_tc3__behind_the_meter_tab_and_derived_test_due_chip(brazos, dana):
    with tenant_ctx(brazos):
        unit = a_unit(dana)
        backflow = make_asset(
            dana,
            asset_no="BF-3301",
            type="backflow",
            unit=None,
            unit_id=unit["id"],
            install_date="2024-01-01",
            last_test_date="2025-06-02",
            test_interval_months=12,
        )
        rows = [
            selectors.asset_dict(a)
            for a in selectors.asset_list(filters={"tab": "behind_the_meter"})
        ]
        stored = models.Asset.objects.get(tenant=brazos, asset_no="BF-3301")
    assert [r["asset_no"] for r in rows] == ["BF-3301"]
    # BR-AST-007: derived chip, stored status unchanged.
    assert backflow["test_due"] is True and stored.status.code == "active"


def test_us_ast_001_tc4__unassigned_filter_is_the_absence_of_a_current_assignment(brazos, dana):
    with tenant_ctx(brazos):
        unit = a_unit(dana)
        make_asset(
            dana,
            asset_no="M-4021",
            service="electric",
            unit_id=unit["id"],
            install_date="2026-01-01",
        )
        make_asset(dana, asset_no="M-5099", service="electric", unit="kWh")
        rows = selectors.asset_list(filters={"status": "unassigned"})
    assert [a.asset_no for a in rows] == ["M-5099"]  # BR-AST-005


def test_us_ast_001_tc5__search_and_filter_and_combine(brazos, dana):
    with tenant_ctx(brazos):
        unit = a_unit(dana, address="1408 Elm Street")
        other = a_unit(dana, label="200", address="500 Main")
        make_asset(
            dana,
            asset_no="M-4021",
            service="electric",
            serial_no="3894-A2210",
            unit_id=unit["id"],
            install_date="2026-01-01",
        )
        make_asset(
            dana, asset_no="M-4204", service="water", unit_id=other["id"], install_date="2026-01-01"
        )
        by_address = selectors.asset_list(q="1408 Elm", filters={"status": "active"})
        by_serial = selectors.asset_list(q="3894-A2210")
        by_number = selectors.asset_list(q="M-42")
    assert [a.asset_no for a in by_address] == ["M-4021"]
    assert [a.asset_no for a in by_serial] == ["M-4021"]  # BR-AST-041 serial search
    assert [a.asset_no for a in by_number] == ["M-4204"]  # US-AST-001 TC-5 wording


def test_us_ast_001_tc6__default_view_hides_retired_and_all_includes_it(brazos, dana):
    with tenant_ctx(brazos):
        make_asset(dana, asset_no="M-5099", service="electric", unit="kWh")
        services.retire_asset(
            dana,
            make_asset(dana, asset_no="M-5098", service="electric", unit="kWh")["id"],
            {"reason": "end_of_life"},
        )
        default_rows = selectors.asset_list()
        retired_rows = selectors.asset_list(filters={"status": "retired"})
        all_rows = selectors.asset_list(filters={"status": "all"})
    assert [a.asset_no for a in default_rows] == ["M-5099"]
    assert [a.asset_no for a in retired_rows] == ["M-5098"]  # BR-AST-005
    assert len(all_rows) == 2


@pytest.mark.isolation
def test_us_ast_001_tc7__isolation_same_asset_number_in_two_tenants(brazos, dana, lonestar, erin):
    with tenant_ctx(brazos):
        make_asset(dana, asset_no="M-4021", service="electric", unit="kWh")
    with tenant_ctx(lonestar):
        make_asset(erin, asset_no="M-4021", service="water", unit="kgal")
        rows = selectors.asset_list(filters={"status": "all"})
        assert len(rows) == 1 and str(rows[0].tenant_id) == str(lonestar.id)


# ── US-AST-002 · S51 add a single asset ─────────────────────────────────────
def test_us_ast_002_tc1__assign_on_create_opens_the_first_assignment_row(brazos, dana, audit_rows):
    with tenant_ctx(brazos):
        unit = a_unit(dana, label="200", address="500 Main")
        asset = make_asset(
            dana,
            asset_no="M-5100",
            service="electric",
            unit="kWh",
            manufacturer_model="Itron · OpenWay",
            serial_no="IT-88412",
            unit_id=unit["id"],
            install_date="2026-08-08",
        )
        history = selectors.assignments(asset["id"])
    assert asset["status"] == "active"  # BR-AST-011
    assert asset["manufacturer"] == "Itron" and asset["model"] == "OpenWay"
    assert history[0]["from_date"] == "2026-08-08" and history[0]["current"] is True
    assert "asset.created" in [r["action"] for r in audit_rows]


def test_us_ast_002_tc2__leave_in_inventory_creates_it_unassigned(brazos, dana):
    with tenant_ctx(brazos):
        asset = make_asset(dana, asset_no="BAT-0905", type="battery", unit=None)
    assert asset["status"] == "inventory" and asset["assigned"] is False
    assert asset["tab"] == "behind_the_meter"


def test_us_ast_002_tc3__net_meter_locks_the_net_metering_flag(brazos, dana):
    with tenant_ctx(brazos):
        asset = make_asset(
            dana, asset_no="M-4021", type="net_meter", service="electric", net_metering=False
        )
        # BR-AST-010: unavailable for non-measuring BTM types.
        with pytest.raises(errors.ValidationError) as caught:
            make_asset(dana, asset_no="PV-1180", type="pv", unit=None, net_metering=True)
    assert asset["net_metering"] is True
    assert caught.value.field_errors[0]["message_key"] == "assets.net_metering_unavailable"


def test_us_ast_002_tc4__sub_meter_carries_its_parent(brazos, dana):
    with tenant_ctx(brazos):
        parent = make_asset(dana, asset_no="M-MASTER-12", service="electric", unit="kWh")
        child = make_asset(
            dana,
            asset_no="SM-8804",
            type="sub_meter",
            service="electric",
            parent_asset_no="M-MASTER-12",
        )
    assert child["parent_asset_no"] == parent["asset_no"] and child["tab"] == "sub_meters"


def test_us_ast_002_tc5__duplicate_asset_number_is_a_hard_block(brazos, dana):
    with tenant_ctx(brazos):
        make_asset(dana, asset_no="M-4021", service="electric", unit="kWh")
        with pytest.raises(errors.BizError) as caught:
            make_asset(dana, asset_no="M-4021", service="water", unit="kgal")
        assert models.Asset.objects.filter(tenant=brazos).count() == 1
    assert caught.value.br_ref == "BR-AST-033" and caught.value.code == errors.BIZ_STATE


def test_us_ast_002_tc6__measuring_type_needs_a_service_and_an_explicit_uom(brazos, dana):
    with tenant_ctx(brazos):
        with pytest.raises(errors.ValidationError) as caught:
            services.create_asset(dana, {"type": "meter", "asset_no": "M-6000"})
    fields = {e["field"] for e in caught.value.field_errors}
    assert fields == {"service", "unit"}  # BR-AST-009 + CLAUDE.md rule 3


def test_us_ast_002_tc7__sub_meter_without_a_parent_is_refused(brazos, dana):
    with tenant_ctx(brazos):
        with pytest.raises(errors.ValidationError) as caught:
            make_asset(dana, asset_no="SM-9999", type="sub_meter", service="electric")
    assert caught.value.field_errors[0]["message_key"] == "assets.parent_required"


def test_us_ast_002_tc9__duplicate_serial_warns_but_allows(brazos, dana, audit_rows):
    with tenant_ctx(brazos):
        make_asset(dana, asset_no="M-4021", service="electric", unit="kWh", serial_no="3894-A2210")
        second = make_asset(
            dana, asset_no="M-5100", service="electric", unit="kWh", serial_no="3894-A2210"
        )
    assert second["warnings"][0]["existing_asset_no"] == "M-4021"  # BR-AST-033
    created = [r for r in audit_rows if r["action"] == "asset.created"][-1]
    assert created["after"]["warnings"][0]["code"] == "duplicate_serial"  # acknowledgement audited


def test_us_ast_002_tc10__asset_number_auto_allocates_with_the_per_type_prefix(brazos, dana):
    """BR-AST-026: padded sequence from the tenant `asset` series (AST-{00000}
    seeded at provisioning) carried under the per-type prefix the rule names."""
    with tenant_ctx(brazos):
        meter = services.create_asset(dana, {"type": "meter", "service": "electric", "unit": "kWh"})
        sub_parent = meter["asset_no"]
        sub = services.create_asset(
            dana,
            {
                "type": "sub_meter",
                "service": "electric",
                "unit": "kWh",
                "parent_asset_no": sub_parent,
            },
        )
        battery = services.create_asset(dana, {"type": "battery"})
    assert meter["asset_no"].startswith("M-") and meter["asset_no"][2:].isdigit()
    assert sub["asset_no"].startswith("SM-")
    assert battery["asset_no"].startswith("BAT-")


# ── US-AST-003 · edit + delete ──────────────────────────────────────────────
def test_us_ast_003_tc1__edit_writes_before_and_after(brazos, dana, audit_rows):
    with tenant_ctx(brazos):
        asset = make_asset(dana, asset_no="M-4310", service="electric", unit="kWh")
        updated = services.update_asset(
            dana, asset["id"], {"manufacturer_model": "Honeywell · A3 Turbo"}
        )
    assert (updated["manufacturer"], updated["model"]) == ("Honeywell", "A3 Turbo")
    row = [r for r in audit_rows if r["action"] == "asset.updated"][0]
    assert row["before"]["manufacturer"] is None and row["after"]["manufacturer"] == "Honeywell"


def test_us_ast_003_tc2__billing_affecting_edit_warns_forward_only(brazos, dana, monkeypatch):
    """BR-AST-012: with reads on the asset the change applies from now on only
    — the response NAMES the fields and the read count; nothing is restated."""
    from apps.assets import seams

    with tenant_ctx(brazos):
        asset = make_asset(dana, asset_no="M-4021", service="electric", unit="kWh", multiplier="10")
        monkeypatch.setattr(seams, "read_count_for_asset", lambda _id: 7)
        updated = services.update_asset(dana, asset["id"], {"multiplier": "1"})
    warning = updated["warnings"][0]
    assert warning["br_ref"] == "BR-AST-012" and warning["reads"] == 7
    assert warning["fields"] == ["multiplier"] and updated["multiplier"] == "1.000000"


def test_us_ast_003_tc3__unreferenced_inventory_deletes(brazos, dana, audit_rows):
    with tenant_ctx(brazos):
        asset = make_asset(dana, asset_no="M-5099", service="electric", unit="kWh")
        services.delete_asset(dana, asset["id"])
        assert not models.Asset.objects.filter(tenant=brazos).exists()
    assert "asset.deleted" in [r["action"] for r in audit_rows]


def test_us_ast_003_tc4__delete_on_an_assigned_asset_is_blocked_server_side(brazos, dana):
    with tenant_ctx(brazos):
        unit = a_unit(dana)
        asset = make_asset(
            dana,
            asset_no="M-4021",
            service="electric",
            unit_id=unit["id"],
            install_date="2026-01-01",
        )
        with pytest.raises(errors.BizError) as caught:
            services.delete_asset(dana, asset["id"])
        assert models.Asset.objects.filter(pk=asset["id"]).exists()
    assert caught.value.br_ref == "BR-AST-013"
    assert caught.value.params["alternative"] == "retire"


def test_us_ast_003_tc5__delete_blocked_by_assignment_history(brazos, dana):
    with tenant_ctx(brazos):
        unit = a_unit(dana)
        asset = make_asset(
            dana,
            asset_no="BAT-0904",
            type="battery",
            unit=None,
            unit_id=unit["id"],
            install_date="2026-01-01",
        )
        services.reassign_asset(
            dana, asset["id"], {"to_inventory": True, "record_final_read": False}
        )
        with pytest.raises(errors.BizError) as caught:
            services.delete_asset(dana, asset["id"])
    assert caught.value.params["referenced_by"]["assignments"] == 1


def test_us_ast_003_tc6__clerk_may_edit_but_never_delete(brazos, dana, marcus):
    with tenant_ctx(brazos):
        asset = make_asset(dana, asset_no="M-4310", service="electric", unit="kWh")
        services.update_asset(marcus, asset["id"], {"seal_no": "TX-88121"})  # BR-AST-032
        with pytest.raises(errors.AuthError) as caught:
            services.delete_asset(marcus, asset["id"])
        with pytest.raises(errors.AuthError):
            services.update_asset(executive_actor(), asset["id"], {"seal_no": "X"})
    assert caught.value.code == errors.AUTH_PERMISSION_DENIED
    response = api_call(
        api_module().asset_detail,
        "delete",
        user=FakeUser(),
        role="billing_clerk",
        tenant=brazos,
        asset_id=asset["id"],
    )
    assert response.status_code == 403


def api_module():
    from apps.assets import api

    return api


@pytest.mark.isolation
def test_us_ast_003_tc7__isolation_cross_tenant_edit_is_not_found(brazos, dana, lonestar, erin):
    with tenant_ctx(brazos):
        asset = make_asset(dana, asset_no="M-5099", service="electric", unit="kWh")
    with tenant_ctx(lonestar):
        with pytest.raises(errors.NotFoundError):
            services.update_asset(erin, asset["id"], {"seal_no": "X"})
        with pytest.raises(errors.NotFoundError):
            services.delete_asset(erin, asset["id"])


def test_us_ast_001_tc9__api_surface_answers_through_the_catalog_envelope(brazos, dana):
    """S49/S50/S54 end-to-end: tab filter, detail, and the BE-02 envelope for a
    duplicate asset # (409, BR-AST-033) and a clerk retire attempt (403,
    BR-AST-032) — the UI gating is convenience, this is the enforcement."""
    from apps.assets import api

    created = api_call(
        api.assets,
        "post",
        user=FakeUser(),
        role="system_admin",
        tenant=brazos,
        data={"type": "meter", "service": "electric", "unit": "kWh"},
    )
    assert created.status_code == 201 and created["Location"].startswith("/assets/")
    listed = api_call(
        api.assets,
        "get",
        user=FakeUser(),
        role="executive",
        tenant=brazos,
        query={"f.tab": "meters"},
    )
    assert listed.status_code == 200 and listed.data["count"] == 1
    detail = api_call(
        api.asset_detail,
        "get",
        user=FakeUser(),
        role="executive",
        tenant=brazos,
        asset_id=created.data["id"],
    )
    assert detail.status_code == 200 and detail.data["specs"]["register_digits"] == 9
    duplicate = api_call(
        api.assets,
        "post",
        user=FakeUser(),
        role="system_admin",
        tenant=brazos,
        data={
            "type": "meter",
            "service": "electric",
            "unit": "kWh",
            "asset_no": created.data["asset_no"],
        },
    )
    assert duplicate.status_code == 409 and duplicate.data["br_ref"] == "BR-AST-033"
    denied = api_call(
        api.asset_retire,
        "post",
        user=FakeUser(),
        role="billing_clerk",
        tenant=brazos,
        asset_id=created.data["id"],
        data={"reason": "failed"},
    )
    assert denied.status_code == 403


# ── BR-AST-043 · the two S8 Reference-data catalogs (PO 2026-08-09) ─────────
# `meter_types` = what the meter IS · `read_methods` = how the read is
# COLLECTED. Both were ratified on the S8 card grid (US-TEN-009 TC-1 "Meter
# types 5") and declared in tenancy's LOOKUP_LISTS long before any table backed
# them — the card was dead. Neither list is B2's `meter_source` enum
# ('ami','manual','import'), which stays the read-source marker on meter_reads.
def test_us_ten_009_tc1__meter_types_catalog_seeds_the_five_ratified_entries(brazos):
    with tenant_ctx(brazos):
        first = services.ensure_reference_catalogs()
        second = services.ensure_reference_catalogs()
        rows = {row["code"]: row for row in selectors.meter_types()}
    # DEF-017: provisioning seeds this catalog now, so ensure_reference_catalogs()
    # creates nothing — the five ratified entries are asserted below regardless
    # of which path put them there.
    assert first["meter_types"] == 0 and second["meter_types"] == 0  # idempotent
    assert set(rows) == {"ami", "amr", "walk_by", "sub_meter", "master"}
    # Names verbatim from BR-AST-043 (which carries the prototype card's casing).
    assert [rows[code]["name"] for code in ("ami", "amr", "walk_by", "sub_meter", "master")] == [
        "AMI",
        "AMR",
        "walk-by",
        "sub-meter",
        "master",
    ]
    # BR-TEN-036: seeded rows are deactivatable, never deletable.
    assert all(row["is_system"] and row["active"] for row in rows.values())


def test_us_ten_009_tc1__read_methods_catalog_seeds_the_eight_ratified_entries(brazos):
    """⚠ **FIVE UNTIL 2026-08-27, EIGHT SINCE — BR-MET-142, the PO ruling that
    closed `OQ-392` by DELEGATING the choice** (*"(a) Rule each onto one of the
    five or you can add new categories"*).

    RED FIRST, verbatim, on the seed constant growing:

        AssertionError: assert {'ami', 'amr'...'mobile', ...} == {'ami', 'amr'...e', 'walk_by'}
          Extra items in the left set:
          'self_read'
          'drive_by'
          'field_visit'

    The first five are BR-AST-043's, unchanged and asserted in their original
    ORDER — the picker is ordered by this tuple's index, so a clerk who knows
    where Mobile sits still finds it there. The last three are appended.
    """
    with tenant_ctx(brazos):
        first = services.ensure_reference_catalogs()
        second = services.ensure_reference_catalogs()
        rows = {row["code"]: row for row in selectors.read_methods()}
    # DEF-017: seeded at provisioning — see the meter_types twin above.
    assert first["read_methods"] == 0 and second["read_methods"] == 0
    assert set(rows) == {
        "ami",
        "amr",
        "walk_by",
        "manual",
        "mobile",
        "drive_by",
        "self_read",
        "field_visit",
    }
    assert [
        rows[code]["name"]
        for code in (
            "ami",
            "amr",
            "walk_by",
            "manual",
            "mobile",
            "drive_by",
            "self_read",
            "field_visit",
        )
    ] == [
        "AMI",
        "AMR",
        "walk-by",
        "Manual",
        "Mobile",
        "Drive-by",
        "Self-read",
        "Field visit",
    ]
    assert all(row["is_system"] and row["active"] for row in rows.values())


def test_us_ten_010_tc1__meter_types_add_routes_through_the_registered_owner_handler(brazos, dana):
    """BR-TEN-031: tenancy renders/routes, the OWNER validates and writes. The
    meter_types card is live end-to-end — LOOKUP_LISTS declares it, this lane
    registers the handler, the count is computed at render (BR-TEN-029)."""
    with tenant_ctx(brazos):
        services.ensure_reference_catalogs()
        created = tenancy_services.create_lookup_entry(
            dana, "meter_types", {"code": "ultrasonic", "name": "Ultrasonic"}
        )
        cards = {card["list"]: card for card in tenancy_selectors.lookup_cards()}
    assert created["code"] == "ultrasonic"
    assert created["is_system"] is False and created["used_by"] == 0  # tenant-added
    assert cards["meter_types"]["count"] == 6  # BR-TEN-036: seeded 5 + the tenant's own


def test_us_ten_010_tc4__catalog_duplicate_codes_are_refused_case_insensitively(brazos):
    with tenant_ctx(brazos):
        services.ensure_reference_catalogs()
        for handler, shouting in (
            (lookups.MeterTypeLookupHandler(), "AMI"),
            (lookups.ReadMethodLookupHandler(), "Walk_By"),
        ):
            with pytest.raises(errors.ValidationError) as excinfo:
                handler.create({"code": shouting, "name": "Same code, new casing"})
            field_error = excinfo.value.field_errors[0]
            assert field_error["field"] == "code"  # BR-TEN-030
            assert field_error["params"]["existing"] == shouting.lower()  # names the entry


def test_us_ten_010_tc5__seeded_catalog_rows_are_never_deletable(brazos):
    """BR-TEN-036 / BR-AST-043: a system row may be deactivated but never
    deleted — even at Used-by 0. A tenant's OWN row deletes freely."""
    with tenant_ctx(brazos):
        services.ensure_reference_catalogs()
        for handler, code in (
            (lookups.MeterTypeLookupHandler(), "master"),
            (lookups.ReadMethodLookupHandler(), "mobile"),
        ):
            seeded = handler.model.objects.get(tenant=brazos, code=code)
            assert handler.used_by(seeded) == 0  # nothing references it
            with pytest.raises(errors.BizError) as excinfo:
                handler.delete(seeded)
            assert excinfo.value.code == errors.BIZ_LOCKED
            handler.set_active(seeded, False)  # deactivation IS allowed
            assert handler.model.objects.get(pk=seeded.pk).active is False
            own = handler.create({"code": "tenant_added", "name": "Tenant added"})
            handler.delete(own)
            assert handler.model.objects.filter(pk=own.pk).exists() is False


def test_us_ten_010_tc7__catalog_entries_live_independently_per_tenant(
    brazos, dana, lonestar, erin
):
    with tenant_ctx(brazos):
        services.ensure_reference_catalogs()
        lookups.MeterTypeLookupHandler().create({"code": "ultrasonic", "name": "Ultrasonic"})
    with tenant_ctx(lonestar):
        services.ensure_reference_catalogs()
        assert "ultrasonic" not in {row["code"] for row in selectors.meter_types()}
        mine = lookups.MeterTypeLookupHandler().create({"code": "Ultrasonic", "name": "Own add"})
        assert mine.code == "Ultrasonic"  # the same code, independently owned
        assert len(selectors.meter_types()) == 6


@pytest.mark.isolation
def test_us_ten_010_tc7__isolation_catalog_rows_never_cross_tenants(brazos, dana, lonestar, erin):
    """⚠ **THE PROBE CODE WAS `drive_by` UNTIL 2026-08-27 — DEF-882, and this is
    the case where the wrong placeholder was most dangerous.** Once BR-MET-142
    seeded `drive_by` into every tenant, the final assertion was *"the code
    brazos invented has not leaked to lonestar"* about a code **lonestar was
    seeded with**, so it failed on isolation working perfectly. A placeholder
    the product can adopt turns an isolation guard into a false alarm.
    """
    with tenant_ctx(brazos):
        services.ensure_reference_catalogs()
        lookups.ReadMethodLookupHandler().create({"code": "drone", "name": "Drone flyover"})
    with tenant_ctx(lonestar):
        services.ensure_reference_catalogs()
        handler = lookups.ReadMethodLookupHandler()
        rows = list(handler.search(None))
        assert {str(row.tenant_id) for row in rows} == {str(lonestar.id)}
        assert "drone" not in {row.code for row in rows}
        # And the seeded eight ARE there, so this can never pass vacuously on a
        # tenant whose catalogue failed to seed at all.
        assert "drive_by" in {row.code for row in rows}


def test_us_ast_002_tc11__an_asset_carries_both_classifications_independently(brazos, dana):
    """BR-AST-044 (PO 2026-08-09): `asset_type` says what kind of DEVICE it is,
    `meter_type` says what class of METER it is, and the two are independent —
    a plain asset_type=meter is legitimately meter_type=ami, amr, walk_by,
    sub_meter or master. Both are catalog FKs; both round-trip by code."""
    with tenant_ctx(brazos):
        ami_meter = make_asset(
            dana, asset_no="M-7001", service="electric", unit="kWh", meter_type="AMI"
        )
        master = make_asset(
            dana, asset_no="M-7002", service="electric", unit="kWh", meter_type="master"
        )
        walk_by = make_asset(
            dana,
            asset_no="M-7003",
            service="electric",
            unit="kWh",
            meter_type="walk-by",  # display casing + hyphen, resolved to walk_by
            read_method="walk_by",
        )
        stored = models.Asset.objects.select_related("type", "meter_type").get(pk=ami_meter["id"])
        catalog_row = models.MeterType.objects.get(tenant=brazos, code="ami")
    # Same asset_type, three different meter types — no coupling either way.
    assert {a["type"] for a in (ami_meter, master, walk_by)} == {"meter"}
    assert [a["meter_type"] for a in (ami_meter, master, walk_by)] == ["ami", "master", "walk_by"]
    assert ami_meter["meter_type_name"] == "AMI" and master["meter_type_name"] == "master"
    assert stored.meter_type_id == catalog_row.id  # the FK, not a copied string
    assert stored.type.code == "meter"  # asset_types FK untouched by the new one
    # All three classifications on the SAME row, each with its display name.
    assert (walk_by["meter_type"], walk_by["read_method"]) == ("walk_by", "walk_by")
    assert walk_by["type_name"] == "Meter" and walk_by["read_method_name"] == "walk-by"


def test_us_ast_002_tc13__meter_type_is_unavailable_on_non_measuring_assets(brazos, dana):
    """BR-AST-044 as amended (PO 2026-08-09): meter_type is a MEASURING-asset
    classification. Setting one on a battery or a PV panel is refused the same
    way BR-AST-010 refuses net-metering there — the field is unavailable, not
    merely left blank, so a mis-tagged battery can never reach the registry."""
    with tenant_ctx(brazos):
        with pytest.raises(errors.ValidationError) as caught:
            make_asset(dana, asset_no="BAT-0905", type="battery", unit=None, meter_type="ami")
        refused = caught.value.field_errors[0]
        # The same asset without the field is still perfectly legal.
        battery = make_asset(dana, asset_no="BAT-0906", type="battery", unit=None)
        # And a real meter still accepts it.
        meter = make_asset(
            dana, asset_no="M-7010", service="electric", unit="kWh", meter_type="ami"
        )
    assert refused["field"] == "meter_type"
    assert refused["message_key"] == "assets.meter_type_unavailable"
    assert refused["params"]["type"] == "battery"
    assert battery["meter_type"] is None
    assert meter["meter_type"] == "ami"


def test_us_ast_002_tc12__meter_type_is_null_on_non_measuring_and_pre_existing_assets(brazos, dana):
    """BR-AST-044: `meter_type` is NULLABLE — non-measuring assets leave it
    null, and an asset created without one (every row that predates the rule,
    which migration 0004 backfilled with nothing) simply carries null."""
    with tenant_ctx(brazos):
        battery = make_asset(dana, asset_no="BAT-0904", type="battery", unit=None)
        untagged = make_asset(dana, asset_no="M-5099", service="electric", unit="kWh")
        rows = models.Asset.objects.filter(tenant=brazos, meter_type__isnull=True)
        unknown_refused = None
        with pytest.raises(errors.ValidationError) as caught:
            make_asset(dana, asset_no="M-7009", service="electric", unit="kWh", meter_type="ami2")
        unknown_refused = caught.value.field_errors[0]
    assert battery["meter_type"] is None and battery["meter_type_name"] is None
    assert untagged["meter_type"] is None  # no default guessed from asset_type
    assert {r.asset_no for r in rows} == {"BAT-0904", "M-5099"}
    # Unknown code refused naming the tenant's own set — never coerced to null.
    assert unknown_refused["field"] == "meter_type"
    assert unknown_refused["code"] == errors.VAL_UNKNOWN_LOOKUP
    assert set(unknown_refused["params"]["allowed"]) == {
        "ami",
        "amr",
        "walk_by",
        "sub_meter",
        "master",
    }


def test_us_ast_003_tc8__meter_type_edits_forward_without_a_billing_warning(
    brazos, dana, audit_rows, monkeypatch
):
    """BR-AST-044 + BR-AST-012: a mis-tagged meter is re-classified like any
    spec field — audited before/after, and NOT forward-only-warned even with
    reads on the asset, because meter_type is a classification and no rate,
    quantity or invoice line is derived from it (recorded on update_asset)."""
    from apps.assets import seams

    with tenant_ctx(brazos):
        asset = make_asset(
            dana, asset_no="M-7010", service="electric", unit="kWh", meter_type="amr"
        )
        monkeypatch.setattr(seams, "read_count_for_asset", lambda _id: 7)
        retagged = services.update_asset(dana, asset["id"], {"meter_type": "ami"})
        cleared = services.update_asset(dana, asset["id"], {"meter_type": None})
        # The contrast: a genuinely billing-affecting field still warns.
        billing = services.update_asset(dana, asset["id"], {"multiplier": "10"})
    assert retagged["meter_type"] == "ami" and retagged["warnings"] == []
    assert cleared["meter_type"] is None  # clearing is legal — the column is nullable
    assert billing["warnings"][0]["fields"] == ["multiplier"]  # BR-AST-012 unchanged
    edit = [r for r in audit_rows if r["action"] == "asset.updated"][0]
    assert edit["before"]["meter_type"] == "amr" and edit["after"]["meter_type"] == "ami"


def test_us_ast_001_tc10__registry_filters_by_meter_type(brazos, dana):
    """BR-AST-044 + BR-AST-041/BR-SHL-011: `f.meter_type` is a first-class
    registry filter beside the type/status ones, AND-combined with them."""
    from apps.assets import api

    with tenant_ctx(brazos):
        make_asset(dana, asset_no="M-7001", service="electric", unit="kWh", meter_type="ami")
        make_asset(dana, asset_no="M-7002", service="electric", unit="kWh", meter_type="ami")
        make_asset(dana, asset_no="M-7003", service="electric", unit="kWh", meter_type="amr")
        make_asset(dana, asset_no="BAT-0904", type="battery", unit=None)  # no meter type
        ami = selectors.asset_list(filters={"meter_type": "ami"})
        amr = selectors.asset_list(filters={"meter_type": "AMR"})  # case-insensitive
        untagged = selectors.asset_list(filters={"meter_type": "none"})
        combined = selectors.asset_list(filters={"meter_type": "ami", "tab": "meters"})
        # `asset_list` is a QUERYSET from 2026-09-12 (`DEF-MET-4951`), so it is
        # materialised HERE, inside the tenant context. Asserting on the lazy
        # object outside the block would run the SQL with no `app.tenant_id`
        # set, which under RLS yields ZERO ROWS AND NO ERROR (`DEF-2734`'s
        # shape) — and would pass anyway on the sqlite the suite runs, which
        # is hard-won law 14 exactly.
        crossed = list(selectors.asset_list(filters={"meter_type": "ami", "type": "battery"}))
    assert [a.asset_no for a in ami] == ["M-7001", "M-7002"]
    assert [a.asset_no for a in amr] == ["M-7003"]
    assert [a.asset_no for a in untagged] == ["BAT-0904"]  # what still needs classifying
    assert [a.asset_no for a in combined] == ["M-7001", "M-7002"]
    assert crossed == []  # AND, never OR (IS-4)
    listed = api_call(
        api.assets,
        "get",
        user=FakeUser(),
        role="executive",
        tenant=brazos,
        query={"f.meter_type": "ami"},
    )
    assert listed.status_code == 200 and listed.data["count"] == 2
    assert {r["meter_type_name"] for r in listed.data["results"]} == {"AMI"}


def test_us_ten_011_tc5__a_meter_type_in_use_is_locked_and_its_code_immutable(brazos, dana):
    """BR-AST-044 turns the meter_types card's used-by count LIVE (it was
    honestly 0 while nothing referenced the catalog). With a real count the two
    BR-TEN rules bite: the code is immutable once used (BR-TEN-030) and a
    referenced row cannot be deleted (BR-TEN-034) — with PROTECT enforcing the
    same law one layer down, in the database."""
    with tenant_ctx(brazos):
        services.ensure_reference_catalogs()
        handler = lookups.MeterTypeLookupHandler()
        tenant_added = tenancy_services.create_lookup_entry(
            dana, "meter_types", {"code": "ultrasonic", "name": "Ultrasonic"}
        )
        asset = make_asset(
            dana, asset_no="M-7020", service="electric", unit="kWh", meter_type="ultrasonic"
        )
        row = models.MeterType.objects.get(tenant=brazos, code="ultrasonic")
        assert handler.used_by(row) == 1  # live, not the old hardcoded 0
        assert handler.serialize(row)["used_by"] == 1

        with pytest.raises(errors.BizError) as renamed:  # BR-TEN-030
            tenancy_services.update_lookup_entry(
                dana, "meter_types", str(row.pk), {"code": "ultrasonic_v2"}
            )
        with pytest.raises(errors.BizError) as deleted:  # BR-TEN-034
            tenancy_services.delete_lookup_entry(dana, "meter_types", str(row.pk))
        with pytest.raises(ProtectedError):  # the DB refuses too (PROTECT)
            row.delete()
        # The NAME stays editable while used, and renaming is fine once free.
        tenancy_services.update_lookup_entry(dana, "meter_types", str(row.pk), {"name": "US meter"})
        services.update_asset(dana, asset["id"], {"meter_type": "ami"})
        assert handler.used_by(row) == 0
        tenancy_services.delete_lookup_entry(dana, "meter_types", str(row.pk))
        assert not models.MeterType.objects.filter(pk=row.pk).exists()
    assert renamed.value.code == errors.BIZ_IMMUTABLE and renamed.value.br_ref == "BR-TEN-030"
    assert deleted.value.code == errors.BIZ_LOCKED and deleted.value.br_ref == "BR-TEN-034"
    assert deleted.value.params["used_by"] == 1
    assert tenant_added["used_by"] == 0  # counted from zero at creation


def test_us_ten_011_tc4__read_method_resolves_to_the_catalog_row_and_locks_it(brazos, dana):
    """BR-AST-043: `assets.read_method` REFERENCES read_methods (superseding
    B2 r4's plain value). Used-by is live (BR-TEN-034) and PROTECT makes the
    lock structural, not just a service check.

    ⚠ **THE TENANT-ADDED CODE WAS `drive_by` UNTIL 2026-08-27 AND THAT IS
    DEF-882.** It was chosen as a plausible word *no tenant had*, and on
    2026-08-27 BR-MET-142 seeded it — so this test began asserting that the
    product refuses a duplicate of its own seed:

        core.errors.ValidationError: VAL-002 (assets.lookups.duplicate_code)

    `drone` replaces it, and the replacement is the point: a test's invented
    placeholder must be a word **the product can never adopt**, not a plausible
    one it has not adopted YET. `drone` is already this repo's probe for exactly
    this (`test_cr038_w3_read_method`, `UploadReadsPage.test.tsx`).
    """
    with tenant_ctx(brazos):
        asset = make_asset(dana, asset_no="M-6001", read_method="AMI")  # code, case-insensitive
        row = models.Asset.objects.select_related("read_method").get(pk=asset["id"])
        ami = models.ReadMethod.objects.get(tenant=brazos, code="ami")
        assert row.read_method_id == ami.id
        assert asset["read_method"] == "ami" and asset["read_method_name"] == "AMI"
        handler = lookups.ReadMethodLookupHandler()
        assert handler.used_by(ami) == 1  # the BR-TEN-034 delete-lock input, live
        tenant_added = handler.create({"code": "drone", "name": "Drone flyover"})
        services.update_asset(dana, asset["id"], {"read_method": "drone"})
        assert handler.used_by(ami) == 0 and handler.used_by(tenant_added) == 1
        with pytest.raises(ProtectedError):  # PROTECT: the DB refuses too
            tenant_added.delete()
        # BR-AST-043 enumerates the seeded set — EIGHT since BR-MET-142, five
        # before it. B2 r4's fourth plain value 'na' has no counterpart in any
        # of them and is not accepted (a tenant may ADD it).
        with pytest.raises(errors.ValidationError) as excinfo:
            make_asset(dana, asset_no="M-6002", read_method="na")
    field_error = excinfo.value.field_errors[0]
    assert field_error["field"] == "read_method"
    assert field_error["code"] == errors.VAL_UNKNOWN_LOOKUP
    assert set(field_error["params"]["allowed"]) == {
        "ami",
        "amr",
        "walk_by",
        "manual",
        "mobile",
        "drive_by",
        "self_read",
        "field_visit",
        "drone",
    }


# ── CR-028 AST-W1 — the r10 registry columns (B16 §4.8, 2026-08-22) ─────────
def test_cr028_w1__row_serves_service_capacity_warranty_and_next_test(brazos, dana):
    """Every row now carries service · export_capacity_kw · warranty_end ·
    next_test — read-only facts for r10's column sets; quantities and dates,
    never money (BR-AST-016/025)."""
    from datetime import date as d
    from decimal import Decimal

    with tenant_ctx(brazos):
        unit = a_unit(dana)
        made = make_asset(
            dana,
            asset_no="M-4021",
            service="electric",
            unit_id=unit["id"],
            install_date="2024-03-12",
        )
        stored = models.Asset.objects.get(pk=made["id"])
        # The AST-W2-T1 columns are read here and written elsewhere — fixture
        # writes go straight to the ORM, the commit_read precedent.
        stored.export_capacity_kw = Decimal("24.0")
        stored.warranty_end = d(2030, 9, 1)
        stored.certification_due = d(2027, 3, 1)
        stored.save()
        served = selectors.asset_dict(selectors.asset_row(made["id"]))
    assert served["service"] == "electric"  # via the service point, seam-read
    assert served["export_capacity_kw"] == "24.000000"  # decimal STRING, 18,6 container
    assert served["warranty_end"] == "2030-09-01"
    # The EXPLICIT certification_due wins over the BR-AST-007 derivation.
    assert served["next_test"] == "2027-03-01"


def test_cr028_w1__next_test_derives_when_no_explicit_certification_due(brazos, dana):
    with tenant_ctx(brazos):
        made = make_asset(
            dana,
            asset_no="M-4022",
            last_test_date="2025-06-02",
            test_interval_months=12,
        )
        served = selectors.asset_dict(selectors.asset_row(made["id"]))
        bare = selectors.asset_dict(selectors.asset_row(make_asset(dana, asset_no="M-4023")["id"]))
    assert served["next_test"] == "2026-06-02"  # last test + 12 months
    # No cert due, no test history: the column is None — a dash, never a guess.
    assert bare["next_test"] is None


def test_cr028_w1__meters_rows_carry_the_served_child_count(brazos, dana):
    """The Role column's `Master · N units` tag reads sub_count off the row —
    the SERVER's own count of children, never a client-side guess."""
    with tenant_ctx(brazos):
        unit = a_unit(dana)
        master = make_asset(
            dana,
            asset_no="M-MASTER-12",
            service="electric",
            unit_id=unit["id"],
            install_date="2024-02-01",
        )
        for n in (1, 2):
            make_asset(
                dana,
                asset_no=f"SM-880{n}",
                type="sub_meter",
                service="electric",
                parent_asset_no=master["asset_no"],
                unit_id=unit["id"],
                install_date="2024-02-01",
            )
        rows = {
            r["asset_no"]: r
            for r in (
                selectors.asset_dict(a) for a in selectors.asset_list(filters={"tab": "meters"})
            )
        }
        standard = selectors.asset_dict(
            selectors.asset_row(make_asset(dana, asset_no="M-5099")["id"])
        )
    assert rows["M-MASTER-12"]["sub_count"] == 2
    assert standard["sub_count"] == 0
    # Sub-meter rows carry the sub-tab facts instead, not a child count.
    with tenant_ctx(brazos):
        sub_rows = [
            selectors.asset_dict(a) for a in selectors.asset_list(filters={"tab": "sub_meters"})
        ]
    assert all("sub_count" not in r for r in sub_rows)


def test_cr028_w1_def592__sub_meter_row_serves_the_last_read_summary(brazos, dana):
    """DEF-592: the Sub-meters tab's Last-read column — the newest committed
    lineage head, QUANTITY with its explicit unit + the read date, served
    through the metering seam (assets asks, never joins)."""
    from tests.test_us_met_reads_helpers import commit_read

    with tenant_ctx(brazos):
        unit = a_unit(dana)
        master = make_asset(
            dana,
            asset_no="M-MASTER-12",
            service="electric",
            unit_id=unit["id"],
            install_date="2024-02-01",
        )
        sub = make_asset(
            dana,
            asset_no="SM-8801",
            type="sub_meter",
            service="electric",
            parent_asset_no=master["asset_no"],
            unit_id=unit["id"],
            install_date="2024-02-01",
        )
        # No committed read yet: the summary is None — a dash on screen, and
        # never a zero (the DEF-079 distinction, display edition).
        before = selectors.asset_dict(selectors.asset_row(sub["id"]))
        commit_read(dana, sub["id"], day="2026-07-03", value=1000, consumption=900)
        commit_read(dana, sub["id"], day="2026-08-03", value=3140, consumption=2140)
        after = selectors.asset_dict(selectors.asset_row(sub["id"]))
    assert before["last_read"] is None
    assert after["last_read"]["consumption"] == "2140.000000"  # 18,6 container, served verbatim
    assert after["last_read"]["unit"] == "kWh"  # CLAUDE.md rule 3 — explicit
    assert after["last_read"]["read_at"] == "2026-08-03"  # the NEWEST head
    # And the master's premises rides the row for r10's Parent / master cell.
    assert after["parent_premises"] == "1408 Elm Street"
