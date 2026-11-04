# ── Trace ──────────────────────────────────────────────
# Story:    US-SHL-015 (capture custom fields on input screens) · US-SHL-016
#           (display them, and include them in exports)
#           Screens: S16 S18 S21 S23 S49 S50 S51 (the eligible slots)
# Rules:    BR-SHL-036 (one control per data type; required binds INPUT
#           placements only) · BR-SHL-037 (the EXISTING envelope, keyed
#           `custom_data.<key>`) · BR-SHL-038 · BR-SHL-039 · BR-TEN-046 ·
#           BR-TEN-048 (never a money input) · BR-TEN-050
# Note:     the SERVER half. The value law is one function published by tenancy
#           (`validate_custom_data_for`) and called by each owning module, so
#           these cases exercise it directly AND through the one module whose
#           write path this lane could wire (customers → `accounts`). The
#           `assets` / `premises` / `units` / `service_points` write paths are
#           owned by lanes this one may not edit — REPORTED, not faked.
# ───────────────────────────────────────────────────────
"""EP-SHL-07 — what a screen may submit into a tenant-defined field."""

import pytest
from django.core.cache import cache

from apps.tenancy import custom_fields, services as tenancy_services
from core import errors

from tests.test_us_ten_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import (
    admin_actor,
    lonestarridge_payload,
    provisioned_tenant,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _clean_registry_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture(autouse=True)
def _asset_screens_rendered(monkeypatch):
    """`CR-161-BRC10` W1 marks every ASSET slot not-rendered until W3 builds the
    screens that draw them, and the server then refuses a new placement there.
    The cases in this file test the placement and value ENGINE using assets as
    their worked example (US-TEN-016 §4's `feeder_number` on S51/S50), so they
    stand in for W3: the asset slots are rendered for the length of a case and
    nothing else about the list moves. `tests/test_cr161_w1_custom_field_settings.py`
    owns the real, un-patched list."""
    import dataclasses

    from apps.tenancy import custom_fields as cf_law

    monkeypatch.setattr(
        cf_law,
        "SLOTS",
        tuple(
            dataclasses.replace(slot, rendered=True) if slot.entity == "assets" else slot
            for slot in cf_law.SLOTS
        ),
    )


def a_field(actor, **overrides):
    payload = {"label": "Feeder Number", "entity": "assets", "data_type": "text"}
    payload.update(overrides)
    return tenancy_services.create_custom_field(actor, payload)


def brazos_asset_fields(actor):
    """§4 test data: Brazos Bend asset `MTR-000117` carries `feeder_number` and
    `pole_tag`, both placed Input on S51 and View on S50."""
    feeder = a_field(actor, label="Feeder Number", entity="assets")
    pole = a_field(actor, label="Pole Tag", entity="assets")
    for row in (feeder, pole):
        tenancy_services.save_custom_field_placement(
            actor, row["id"], {"S51": "input", "S50": "view", "S49": "view"}
        )
    return feeder, pole


# ── US-SHL-015 — capture ────────────────────────────────────────────────────
def test_us_shl_015_tc1__two_text_fields_capture_in_display_order(growth_plan, identity_seam):
    tenant, _ = provisioned_tenant()
    actor = admin_actor()
    with tenant_ctx(tenant):
        brazos_asset_fields(actor)
        registry = tenancy_services.selectors.custom_field_registry(
            "assets", screen="S51", mode="input"
        )
        stored = tenancy_services.validate_custom_data_for(
            "assets", {"feeder_number": "F-12", "pole_tag": "P-8842"}
        )
    assert [f["key"] for f in registry] == ["feeder_number", "pole_tag"]
    assert stored == {"feeder_number": "F-12", "pole_tag": "P-8842"}


def test_us_shl_015_tc2__a_select_accepts_only_its_defined_options(growth_plan, identity_seam):
    tenant, _ = provisioned_tenant()
    actor = admin_actor()
    with tenant_ctx(tenant):
        a_field(
            actor,
            label="Service Class",
            entity="accounts",
            data_type="select",
            options=["Residential", "Commercial", "Irrigation"],
        )
        stored = tenancy_services.validate_custom_data_for(
            "accounts", {"service_class": "Commercial"}
        )
    assert stored == {"service_class": "Commercial"}


def test_us_shl_015_tc3__a_required_field_left_blank_blocks_save_with_its_own_key(
    growth_plan, identity_seam
):
    tenant, _ = provisioned_tenant()
    actor = admin_actor()
    with tenant_ctx(tenant):
        row = a_field(actor, label="Feeder Number", entity="assets", is_required=True)
        tenancy_services.save_custom_field_placement(actor, row["id"], {"S51": "input"})
        with pytest.raises(errors.ValidationError) as caught:
            # DEF-TEN-9157: the door names its screen; S51 is where it is typed.
            tenancy_services.validate_custom_data_for(
                "assets", {"feeder_number": ""}, screen="S51"
            )
    # BR-SHL-037: the EXISTING envelope, keyed so FormModal highlights the
    # control through the path it already has.
    assert caught.value.field_errors[0]["field"] == "custom_data.feeder_number"
    assert caught.value.field_errors[0]["code"] == errors.VAL_REQUIRED


def test_us_shl_015_tc4__a_tenant_with_no_fields_gets_an_empty_registry(growth_plan, identity_seam):
    """The client half of TC-4 (render NOTHING — no heading, no empty section,
    no layout shift) is the vitest suite's; the server half is that the
    registry is EMPTY rather than a section with zero rows."""
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        assert (
            tenancy_services.selectors.custom_field_registry("assets", screen="S51", mode="input")
            == []
        )
        assert tenancy_services.validate_custom_data_for("assets", {}) == {}


def test_us_shl_015_tc5__an_unknown_key_is_rejected_and_never_persisted(growth_plan, identity_seam):
    """A stale client cannot write shadow data no screen will show and no
    export will carry."""
    tenant, _ = provisioned_tenant()
    actor = admin_actor()
    with tenant_ctx(tenant):
        a_field(actor, label="Feeder Number", entity="assets")
        with pytest.raises(errors.ValidationError) as caught:
            tenancy_services.validate_custom_data_for(
                "assets", {"feeder_number": "F-12", "ghost_field": "x"}
            )
    assert [fe["field"] for fe in caught.value.field_errors] == ["custom_data.ghost_field"]


def test_us_shl_015_tc6__a_value_outside_the_option_list_is_refused(growth_plan, identity_seam):
    tenant, _ = provisioned_tenant()
    actor = admin_actor()
    with tenant_ctx(tenant):
        a_field(
            actor,
            label="Service Class",
            entity="accounts",
            data_type="select",
            options=["Residential", "Commercial"],
        )
        with pytest.raises(errors.ValidationError) as caught:
            tenancy_services.validate_custom_data_for("accounts", {"service_class": "Municipal"})
    assert caught.value.field_errors[0]["field"] == "custom_data.service_class"
    assert caught.value.field_errors[0]["params"]["value"] == "Municipal"


@pytest.mark.isolation
def test_us_shl_015_tc8__one_tenants_keys_are_rejected_on_another_tenants_write(
    growth_plan, identity_seam
):
    brazos, _ = provisioned_tenant()
    lonestar, _ = provisioned_tenant(lonestarridge_payload())
    actor = admin_actor()
    with tenant_ctx(brazos):
        brazos_asset_fields(actor)
    with tenant_ctx(lonestar):
        # A crafted POST carrying Brazos Bend's keys is rejected: Lone Star
        # Ridge's registry has no such definition, so the keys are unknown.
        with pytest.raises(errors.ValidationError) as caught:
            tenancy_services.validate_custom_data_for("assets", {"feeder_number": "F-12"})
    assert caught.value.field_errors[0]["field"] == "custom_data.feeder_number"


# ── the typed value space (BR-SHL-036, one branch per data type) ────────────
def test_us_shl_015_a_number_is_stored_as_a_string_and_never_as_a_decimal(
    growth_plan, identity_seam
):
    """BR-TEN-048 made structural. `1.5` stays `"1.5"`, `10432` stays
    `"10432"` — never grouped, never rounded, never a Decimal a later caller
    could arithmetic with. These are BR-TEN-082's own ratified literals."""
    tenant, _ = provisioned_tenant()
    actor = admin_actor()
    with tenant_ctx(tenant):
        a_field(actor, label="Multiplier", entity="assets", data_type="number")
        a_field(actor, label="Legacy Id", entity="assets", data_type="number")
        stored = tenancy_services.validate_custom_data_for(
            "assets", {"multiplier": "1.50", "legacy_id": "10,432"}
        )
    assert stored == {"multiplier": "1.5", "legacy_id": "10432"}
    assert all(isinstance(value, str) for value in stored.values())


def test_us_shl_015_a_date_is_stored_iso_whatever_the_ui_renders(growth_plan, identity_seam):
    tenant, _ = provisioned_tenant()
    actor = admin_actor()
    with tenant_ctx(tenant):
        a_field(actor, label="Installed On", entity="assets", data_type="date")
        stored = tenancy_services.validate_custom_data_for("assets", {"installed_on": "2026-03-04"})
        with pytest.raises(errors.ValidationError):
            tenancy_services.validate_custom_data_for("assets", {"installed_on": "03/04/2026"})
    assert stored == {"installed_on": "2026-03-04"}


def test_us_shl_015_multi_select_keeps_the_tenants_own_option_order(growth_plan, identity_seam):
    tenant, _ = provisioned_tenant()
    actor = admin_actor()
    with tenant_ctx(tenant):
        a_field(
            actor,
            label="Site Notes",
            entity="assets",
            data_type="multi_select",
            options=["Locked gate", "Dog on site", "Call ahead"],
        )
        stored = tenancy_services.validate_custom_data_for(
            "assets", {"site_notes": ["Dog on site", "Locked gate"]}
        )
    # Submitted out of order; stored in the tenant's DEFINED order, which is
    # what BR-TEN-082's `Locked gate, Dog on site` literal depends on.
    assert stored == {"site_notes": ["Locked gate", "Dog on site"]}


def test_us_shl_015_a_bad_value_names_its_own_control(growth_plan, identity_seam):
    tenant, _ = provisioned_tenant()
    actor = admin_actor()
    with tenant_ctx(tenant):
        a_field(actor, label="Multiplier", entity="assets", data_type="number")
        with pytest.raises(errors.ValidationError) as caught:
            tenancy_services.validate_custom_data_for("assets", {"multiplier": "abc"})
    assert caught.value.field_errors[0]["field"] == "custom_data.multiplier"
    assert caught.value.field_errors[0]["message_key"] == "customFields.not_a_number"


# ── US-SHL-016 — display and export ─────────────────────────────────────────
def test_us_shl_016_tc1__view_placements_expose_the_fields_a_detail_page_renders(
    growth_plan, identity_seam
):
    tenant, _ = provisioned_tenant()
    actor = admin_actor()
    with tenant_ctx(tenant):
        brazos_asset_fields(actor)
        on_detail = tenancy_services.selectors.custom_field_registry(
            "assets", screen="S50", mode="view"
        )
    assert [(f["key"], f["label"]) for f in on_detail] == [
        ("feeder_number", "Feeder Number"),
        ("pole_tag", "Pole Tag"),
    ]


def test_us_shl_016_tc2__list_columns_come_from_the_view_placed_fields(growth_plan, identity_seam):
    """BR-SHL-038: they are OFFERED (S49 is a view slot). Whether a column is on
    by default is the client's law and is asserted in the vitest suite —
    `customColumnConfigs` sets `defaultVisible: false` for every one."""
    tenant, _ = provisioned_tenant()
    actor = admin_actor()
    with tenant_ctx(tenant):
        brazos_asset_fields(actor)
        offered = tenancy_services.selectors.custom_field_registry(
            "assets", screen="S49", mode="view"
        )
    assert [f["label"] for f in offered] == ["Feeder Number", "Pole Tag"]


def test_us_shl_016_tc6__a_deactivated_field_leaves_detail_chooser_and_export_together(
    growth_plan, identity_seam
):
    tenant, _ = provisioned_tenant()
    actor = admin_actor()
    with tenant_ctx(tenant):
        feeder, pole = brazos_asset_fields(actor)
        tenancy_services.set_custom_field_active(actor, pole["id"], False)
        for screen in ("S50", "S49"):
            keys = [
                f["key"]
                for f in tenancy_services.selectors.custom_field_registry(
                    "assets", screen=screen, mode="view"
                )
            ]
            assert keys == ["feeder_number"]  # one surface, one answer
        # …and a value already recorded against it is NOT rejected on a later
        # write, because the write only sees the ACTIVE registry: submitting
        # the retired key is now an unknown key, which is the correct refusal.
        with pytest.raises(errors.ValidationError):
            tenancy_services.validate_custom_data_for("assets", {"pole_tag": "P-1"})


@pytest.mark.isolation
def test_us_shl_016_tc8__another_tenants_labels_appear_in_no_surface_here(
    growth_plan, identity_seam
):
    brazos, _ = provisioned_tenant()
    lonestar, _ = provisioned_tenant(lonestarridge_payload())
    actor = admin_actor()
    with tenant_ctx(brazos):
        brazos_asset_fields(actor)
    with tenant_ctx(lonestar):
        for screen in ("S49", "S50", "S51"):
            assert tenancy_services.selectors.custom_field_registry("assets", screen=screen) == []


# ── the ONE wired owning module (customers → `accounts`) ────────────────────
def test_us_shl_015_tc7__an_account_write_carries_custom_data_through_its_own_audit_row(
    growth_plan, identity_seam
):
    """US-SHL-015 TC-7: no separate audit path, because the value lives in the
    entity's OWN row and rides BR-AUD-003's whole-row before/after for free."""
    from apps.customers import services as customer_services

    tenant, _ = provisioned_tenant()
    actor = admin_actor()
    with tenant_ctx(tenant):
        a_field(
            actor,
            label="Service Class",
            entity="accounts",
            data_type="select",
            options=["Residential", "Commercial"],
        )
        cleaned = customer_services._validate_account(
            {"custom_data": {"service_class": "Commercial"}}, partial=True
        )
    assert cleaned["custom_data"] == {"service_class": "Commercial"}


def test_us_shl_015_the_accounts_write_vocabulary_accepts_custom_data(growth_plan, identity_seam):
    from apps.customers import services as customer_services

    assert "custom_data" in customer_services.CREATE_FIELDS
    assert "custom_data" in customer_services.PATCH_FIELDS


def test_us_shl_015_the_seam_resolves_rather_than_substituting_an_answer(
    growth_plan, identity_seam
):
    """DEF-075's shape, refused: an unresolved validator would silently accept
    whatever a client sent into a jsonb column. The customers seam imports
    tenancy directly and fails loudly if the contract moves."""
    from apps.customers import seams as customer_seams

    assert callable(tenancy_services.validate_custom_data_for)
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant), pytest.raises(errors.ValidationError):
        customer_seams.validate_custom_data("accounts", {"nope": 1}, screen="S18")


# The END-TO-END half of US-SHL-016 for `accounts` — a real account created
# through the customers service, its `custom_data` recorded and read back off
# `GET /accounts/{id}` — lives in tests/test_us_cus_003_account_write.py, beside
# the premises/unit/plan fixtures it needs. It is not duplicated here: an
# assertion over the SOURCE of the selector (which is what this slot held first)
# would still have passed if the key were emitted with the wrong value.


def test_us_shl_015_the_eight_entities_and_six_types_are_the_signed_sets(
    growth_plan, identity_seam
):
    """B2 r17.1/r17.2, verbatim. A ninth entity or a seventh type here would be
    this lane inventing schema — ⚠ AND THE NINTH IS RULED: `payments`, PO
    2026-10-02 (`CR-161-BRC10` W5, R3 *"Payments IN as capture-at-entry only"*,
    BR-TEN-046 as amended). Further record types arrive wave by wave with their
    own ruling and their own migration — W4's five did (`tenancy/0057`,
    `metering/0067`), in the PO's Part 1 order."""
    assert custom_fields.ENTITIES == (
        "premises",
        "units",
        "service_points",
        "assets",
        "accounts",
        "contacts",
        "addresses",
        "service_agreements",
        "payments",
        "customers",
        "work_orders",
        "meter_reads",
        "routes",
        "areas",
    )
    assert custom_fields.DATA_TYPES == (
        "text",
        "number",
        "date",
        "boolean",
        "select",
        "multi_select",
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-SHL-015@a1c9f04 (story+rules snapshot over EP-SHL-07-custom-field-rendering.md +
#         00-platform-shell/02-business-rules.md BR-SHL-036..039)
# generated: 2026-08-15 by story-coder (tenant custom-fields lane)
# checklist: A✔ B✔ C✔ D✔ E=deferred(the client half is the vitest suite) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff --select E4,E7,E9,F✔ black✔ · see the lane report for counts and for the checks proved RED first
# exceptions: the `assets` · `premises` · `units` · `service_points` WRITE paths are not wired to the published validator — those modules are owned by other lanes and this one may not edit them. The validator is published, tested, and wired into `accounts` (customers); the remaining four are REPORTED in the lane report with the one-line call each needs
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
