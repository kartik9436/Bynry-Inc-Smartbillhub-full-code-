# ── Trace ──────────────────────────────────────────────
# Story:    US-TEN-014 (card + management view) · US-TEN-015 (define a field) ·
#           US-TEN-016 (placement) · US-TEN-017 (lifecycle + the registry)
#           Screens: S8
# Rules:    BR-TEN-046 · BR-TEN-047 · BR-TEN-048 · BR-TEN-049 · BR-TEN-050 ·
#           BR-TEN-051 · BR-TEN-052 · BR-TEN-053 · CLAUDE.md rule 1 / rule 7
# Note:     the RLS half of every isolation TC is the G5 suite (Postgres only);
#           the app-layer half runs on the sqlite tier and is asserted here.
#           §4 test data is EP-TEN-09's own, verbatim: Brazos Bend's
#           `feeder_number` · `easement_ref` · `service_class` · `pole_tag`, and
#           the ten-field Accounts set for the cap.
# ───────────────────────────────────────────────────────
"""EP-TEN-09 — the tenant-defined field registry, per test case."""

import pytest
from django.core.cache import cache

from apps.tenancy import api, custom_fields, models, selectors, services
from core import errors

from tests.test_us_ten_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import (
    FakeUser,
    admin_actor,
    api_call,
    audit_actions,
    clerk_actor,
    lonestarridge_payload,
    provisioned_tenant,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


# §4 test data — EP-TEN-09 US-TEN-015 §4, the ten-field Accounts set.
CAP_KEYS = (
    "service_class",
    "feeder_zone",
    "tax_district",
    "co_op_member_no",
    "deposit_waiver_ref",
    "site_contact_role",
    "access_code",
    "hazard_note",
    "ada_flag",
    "legacy_account_no",
)


@pytest.fixture(autouse=True)
def _clean_registry_cache():
    """BR-TEN-053's cache is process-wide in the test tier (LocMem). Clearing
    between tests keeps one test's warm key out of the next one's read — the
    version bump makes that impossible in production, and a shared LocMem
    across tests would hide a missing bump rather than reveal one."""
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
    payload = {
        "label": "Feeder Number",
        "entity": "assets",
        "data_type": "text",
    }
    payload.update(overrides)
    return services.create_custom_field(actor, payload)


# ── US-TEN-014 — the card and the management view ───────────────────────────
def test_us_ten_014_tc1__empty_tenant_shows_a_card_with_count_zero(growth_plan, identity_seam):
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        card = selectors.custom_field_card()
    assert card == {"list": "custom_fields", "owner": "tenancy", "count": 0, "by_entity": {}}


def test_us_ten_014_tc2__four_fields_group_by_entity(growth_plan, identity_seam):
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
        a_field(actor, label="Feeder Zone", entity="accounts")
        a_field(actor, label="Tax District", entity="accounts")
        a_field(actor, label="Feeder Number", entity="assets")
        card = selectors.custom_field_card()
    assert card["count"] == 4
    assert card["by_entity"] == {"accounts": 3, "assets": 1}


def test_us_ten_014_tc3__search_matches_label_and_key(growth_plan, identity_seam):
    tenant, _ = provisioned_tenant()
    actor = admin_actor()
    with tenant_ctx(tenant):
        a_field(actor, label="Feeder Number", entity="assets")
        a_field(actor, label="Pole Tag", entity="assets")
        by_label = selectors.custom_field_rows(q="Feeder")
        by_key = selectors.custom_field_rows(q="feeder_num")
    assert [row["key"] for row in by_label] == ["feeder_number"]
    assert [row["key"] for row in by_key] == ["feeder_number"]


def test_us_ten_014_tc4__entity_filter_with_no_matches_is_an_empty_list_not_an_error(
    growth_plan, identity_seam
):
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        a_field(admin_actor(), label="Feeder Number", entity="assets")
        assert selectors.custom_field_rows(entity="premises") == []


def test_us_ten_014_tc5__billing_clerk_is_refused_settings(growth_plan, identity_seam):
    """A4: Settings is System Admin-only, enforced at the SERVICE layer too
    (BR-SHL-025 defence in depth), so an API bypass does not reach the write."""
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant), pytest.raises(errors.AuthError) as caught:
        services.create_custom_field(
            clerk_actor(), {"label": "X", "entity": "assets", "data_type": "text"}
        )
    assert caught.value.code == errors.AUTH_PERMISSION_DENIED


@pytest.mark.isolation
def test_us_ten_014_tc6__a_second_tenant_sees_none_of_the_first_tenants_fields(
    growth_plan, identity_seam
):
    brazos, _ = provisioned_tenant()
    lonestar, _ = provisioned_tenant(lonestarridge_payload())
    actor = admin_actor()
    with tenant_ctx(brazos):
        for label in ("Feeder Number", "Easement Ref", "Service Class", "Pole Tag"):
            entity = "accounts" if label == "Service Class" else "assets"
            a_field(
                actor,
                label=label,
                entity=entity,
                **(
                    {"data_type": "select", "options": ["A", "B"]}
                    if label == "Service Class"
                    else {}
                ),
            )
        assert selectors.custom_field_card()["count"] == 4
    with tenant_ctx(lonestar):
        assert selectors.custom_field_card()["count"] == 0
        assert selectors.custom_field_rows() == []
        # And no Lone Star Ridge screen gains a field.
        assert selectors.custom_field_registry("assets") == []


# ── US-TEN-015 — define a field ─────────────────────────────────────────────
def test_us_ten_015_tc1__key_is_derived_from_the_label_and_shown_read_only(
    growth_plan, identity_seam
):
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        row = a_field(admin_actor(), label="Feeder Number", entity="assets", data_type="text")
    assert row["key"] == "feeder_number"
    assert row["entity"] == "assets"
    assert row["is_active"] is True


def test_us_ten_015_tc2__select_options_keep_the_order_they_were_given(growth_plan, identity_seam):
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        row = a_field(
            admin_actor(),
            label="Service Class",
            entity="accounts",
            data_type="select",
            options=["Residential", "Commercial", "Irrigation"],
        )
        reloaded = selectors.custom_field_row(row["id"])
    assert row["options"] == ["Residential", "Commercial", "Irrigation"]
    assert reloaded["options"] == ["Residential", "Commercial", "Irrigation"]


def test_us_ten_015_tc3__editing_the_label_keeps_the_key_and_the_row(growth_plan, identity_seam):
    tenant, _ = provisioned_tenant()
    actor = admin_actor()
    with tenant_ctx(tenant):
        row = a_field(actor, label="Feeder Number", entity="assets")
        edited = services.update_custom_field(actor, row["id"], {"label": "Feeder ID"})
    assert edited["label"] == "Feeder ID"
    assert edited["key"] == "feeder_number"
    assert edited["id"] == row["id"]  # updated in place, never recreated


def test_us_ten_015_tc4__the_key_cannot_be_changed_through_the_api(growth_plan, identity_seam):
    tenant, _ = provisioned_tenant()
    actor = admin_actor()
    with tenant_ctx(tenant):
        row = a_field(actor, label="Feeder Number", entity="assets")
        with pytest.raises(errors.ValidationError) as caught:
            services.update_custom_field(actor, row["id"], {"key": "feeder_id"})
        assert selectors.custom_field_row(row["id"])["key"] == "feeder_number"
    fields = {fe["field"] for fe in caught.value.field_errors}
    assert fields == {"key"}
    assert caught.value.field_errors[0]["message_key"] == (
        "settings.customFields.immutable_after_create"
    )


def test_us_ten_015_tc5__the_eleventh_active_accounts_field_is_refused_by_the_cap(
    growth_plan, identity_seam, audit_rows
):
    tenant, _ = provisioned_tenant()
    actor = admin_actor()
    with tenant_ctx(tenant):
        for key in CAP_KEYS:
            a_field(actor, label=key.replace("_", " ").title(), entity="accounts")
        before = models.CustomField.objects.count()
        audit_before = len(audit_rows)
        with pytest.raises(errors.BizError) as caught:
            a_field(actor, label="Route Note", entity="accounts")
        assert models.CustomField.objects.count() == before  # nothing is written
        assert len(audit_rows) == audit_before  # and no create is recorded
    assert caught.value.code == errors.BIZ_CAP
    assert caught.value.br_ref == "BR-TEN-051"
    assert caught.value.params == {"entity": "accounts", "active": 10, "cap": 10}


def test_us_ten_015_tc6__duplicate_key_within_one_entity_is_refused(growth_plan, identity_seam):
    tenant, _ = provisioned_tenant()
    actor = admin_actor()
    with tenant_ctx(tenant):
        a_field(
            actor, label="Service Class", entity="accounts", data_type="select", options=["A", "B"]
        )
        with pytest.raises(errors.ValidationError) as caught:
            a_field(actor, label="Service Class", entity="accounts")
    assert caught.value.field_errors[0]["message_key"] == "settings.customFields.duplicate_key"


def test_us_ten_015_tc7__an_entity_outside_the_eight_is_refused(growth_plan, identity_seam):
    """`invoices` is append-only (DB-4) and receives a SNAPSHOT, never an
    editable field; the rating tables are the calculation boundary.

    ⚠ `payments` LEFT THIS LIST 2026-10-02 (`CR-161-BRC10` W5, PO R3: *"Payments
    IN as capture-at-entry only"*) — it is now an entity, written at the
    payment's INSERT and never editable; `journal_entries` (R2, never) takes its
    place. `tests/test_cr161_w5_payment_custom_fields.py` owns the payments case.

    ⚠ `meter_reads` LEFT THIS LIST 2026-10-02 too (`CR-161-BRC10` W4, Part 2 row
    11: *"Manual reading entry · Reading import … Never used in the bill
    calculation"*); `chart_of_accounts` (R3, never) takes its place.
    `tests/test_cr161_w4_custom_fields.py` owns the readings case."""
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        for entity in ("invoices", "tariffs", "chart_of_accounts", "journal_entries"):
            with pytest.raises(errors.ValidationError) as caught:
                a_field(admin_actor(), entity=entity)
            assert caught.value.field_errors[0]["field"] == "entity"


def test_us_ten_015_tc8__create_update_and_deactivate_each_write_an_audit_row(
    growth_plan, identity_seam, audit_rows
):
    tenant, _ = provisioned_tenant()
    actor = admin_actor()
    with tenant_ctx(tenant):
        row = a_field(actor, label="Feeder Number", entity="assets")
        services.update_custom_field(actor, row["id"], {"label": "Feeder ID"})
        services.set_custom_field_active(actor, row["id"], False)
    actions = audit_actions(audit_rows)
    assert "custom_field.created" in actions
    assert "custom_field.updated" in actions
    assert "custom_field.deactivated" in actions
    updated = [r for r in audit_rows if r["action"] == "custom_field.updated"][0]
    assert updated["before"]["label"] == "Feeder Number"
    assert updated["after"]["label"] == "Feeder ID"


def test_us_ten_015_tc9__the_cap_is_per_tenant_per_entity(growth_plan, identity_seam):
    brazos, _ = provisioned_tenant()
    lonestar, _ = provisioned_tenant(lonestarridge_payload())
    actor = admin_actor()
    with tenant_ctx(brazos):
        for key in CAP_KEYS:
            a_field(actor, label=key.replace("_", " ").title(), entity="accounts")
        # …and a first PREMISES field still succeeds, because the cap is per entity.
        assert a_field(actor, label="Easement Ref", entity="premises")["key"] == "easement_ref"
    with tenant_ctx(lonestar):
        assert a_field(actor, label="Service Class", entity="accounts")["key"] == "service_class"


def test_us_ten_015_options_are_required_and_at_least_two_for_a_select(growth_plan, identity_seam):
    """US-TEN-015 §5: "required and ≥2 when type is select/multi_select"."""
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        for options in (None, [], ["Only One"]):
            with pytest.raises(errors.ValidationError) as caught:
                a_field(
                    admin_actor(),
                    label="Service Class",
                    entity="accounts",
                    data_type="select",
                    options=options,
                )
            assert caught.value.field_errors[0]["field"] == "options"


# ── US-TEN-016 — placement ──────────────────────────────────────────────────
def test_us_ten_016_tc1__input_on_s51_and_view_on_s50(growth_plan, identity_seam):
    tenant, _ = provisioned_tenant()
    actor = admin_actor()
    with tenant_ctx(tenant):
        row = a_field(actor, label="Feeder Number", entity="assets")
        placed = services.save_custom_field_placement(
            actor, row["id"], {"S51": "input", "S50": "view", "S49": "view"}
        )
        on_s51 = selectors.custom_field_registry("assets", screen="S51", mode="input")
        on_s50 = selectors.custom_field_registry("assets", screen="S50", mode="view")
    assert placed["placement"] == {"S51": "input", "S50": "view", "S49": "view"}
    assert [f["key"] for f in on_s51] == ["feeder_number"]
    assert [f["key"] for f in on_s50] == ["feeder_number"]


def test_us_ten_016_tc2__input_only_does_not_display_elsewhere(growth_plan, identity_seam):
    tenant, _ = provisioned_tenant()
    actor = admin_actor()
    with tenant_ctx(tenant):
        row = a_field(
            actor,
            label="Service Class",
            entity="accounts",
            data_type="select",
            options=["Residential", "Commercial"],
        )
        services.save_custom_field_placement(actor, row["id"], {"S18": "input"})
        # S18 captures it…
        assert selectors.custom_field_registry("accounts", screen="S18", mode="input")
        # …and S21 shows nothing until a View placement is added.
        assert selectors.custom_field_registry("accounts", screen="S21", mode="view") == []
        services.save_custom_field_placement(actor, row["id"], {"S18": "input", "S21": "view"})
        assert selectors.custom_field_registry("accounts", screen="S21", mode="view")


def test_us_ten_016_tc3__not_shown_removes_the_screen_and_keeps_the_values(
    growth_plan, identity_seam
):
    tenant, _ = provisioned_tenant()
    actor = admin_actor()
    with tenant_ctx(tenant):
        row = a_field(actor, label="Feeder Number", entity="assets")
        services.save_custom_field_placement(actor, row["id"], {"S51": "input", "S50": "view"})
        # R4 (CR-161-BRC10): hiding the INPUT screen while a View stays would
        # leave a field nobody collects, which is refused — so the case hides
        # the View screen instead; what it proves is unchanged.
        hidden = services.save_custom_field_placement(
            actor, row["id"], {"S51": "input", "S50": "not_shown"}
        )
        assert hidden["placement"] == {"S51": "input"}
        assert selectors.custom_field_registry("assets", screen="S50", mode="view") == []
        # Placing it again brings it straight back — nothing about the
        # definition or its stored values was destroyed.
        back = services.save_custom_field_placement(
            actor, row["id"], {"S51": "input", "S50": "view"}
        )
        assert back["placement"] == {"S51": "input", "S50": "view"}


def test_us_ten_016_tc4__a_money_screen_is_not_an_eligible_slot(growth_plan, identity_seam):
    """S31 is the Run Bills wizard. It is absent from the allow-list, so a
    placement naming it cannot be stored — BR-TEN-052 backing BR-TEN-048."""
    tenant, _ = provisioned_tenant()
    actor = admin_actor()
    with tenant_ctx(tenant):
        row = a_field(actor, label="Service Class", entity="accounts")
        for screen in ("S31", "S12", "S13"):
            with pytest.raises(errors.ValidationError) as caught:
                services.save_custom_field_placement(actor, row["id"], {screen: "input"})
            assert caught.value.field_errors[0]["message_key"] == (
                "settings.customFields.slot_not_eligible"
            )


def test_us_ten_016_tc5__slot_entity_mismatch_is_refused(growth_plan, identity_seam):
    tenant, _ = provisioned_tenant()
    actor = admin_actor()
    with tenant_ctx(tenant):
        row = a_field(actor, label="Service Class", entity="accounts")
        with pytest.raises(errors.ValidationError):
            # S50 is an ASSET slot; this field is on accounts.
            services.save_custom_field_placement(actor, row["id"], {"S50": "view"})


def test_us_ten_016_tc6__required_binds_input_placements_only(growth_plan, identity_seam):
    tenant, _ = provisioned_tenant()
    actor = admin_actor()
    with tenant_ctx(tenant):
        row = a_field(actor, label="Feeder Number", entity="assets", is_required=True)
        # R4 (CR-161-BRC10): a field shown somewhere must be collected
        # somewhere, so the View placement on S49 travels with Input on S51.
        services.save_custom_field_placement(actor, row["id"], {"S51": "input", "S49": "view"})
        registry = selectors.custom_field_registry("assets")
        # A View-only placement never blocks a save: the value half is asked
        # with require_input=False on a view render.
        assert custom_fields.validate_custom_data(registry, {}, require_input=False) == {}
        # DEF-TEN-9157 — required binds on the screen it is TYPED IN on (S51)
        # and on no other screen: S50 and S49 never block.
        assert custom_fields.validate_custom_data(registry, {}, screen="S50") == {}
        assert custom_fields.validate_custom_data(registry, {}, screen="S49") == {}
        with pytest.raises(errors.ValidationError):
            custom_fields.validate_custom_data(registry, {}, screen="S51")


def test_us_ten_016_tc7__placement_change_is_audited(growth_plan, identity_seam, audit_rows):
    tenant, _ = provisioned_tenant()
    actor = admin_actor()
    with tenant_ctx(tenant):
        row = a_field(actor, label="Feeder Number", entity="assets")
        services.save_custom_field_placement(actor, row["id"], {"S51": "input"})
    changed = [r for r in audit_rows if r["action"] == "custom_field.placement_changed"]
    assert len(changed) == 1
    assert changed[0]["before"]["placement"] == {}
    assert changed[0]["after"]["placement"] == {"S51": "input"}


@pytest.mark.isolation
def test_us_ten_016_tc8__another_tenants_placement_renders_nothing_here(growth_plan, identity_seam):
    brazos, _ = provisioned_tenant()
    lonestar, _ = provisioned_tenant(lonestarridge_payload())
    actor = admin_actor()
    with tenant_ctx(brazos):
        row = a_field(actor, label="Feeder Number", entity="assets")
        services.save_custom_field_placement(actor, row["id"], {"S51": "input", "S50": "view"})
    with tenant_ctx(lonestar):
        assert selectors.custom_field_registry("assets", screen="S50", mode="view") == []


# ── US-TEN-017 — lifecycle and the registry ─────────────────────────────────
def test_us_ten_017_tc1__deactivate_hides_the_field_and_keeps_the_values(
    growth_plan, identity_seam
):
    tenant, _ = provisioned_tenant()
    actor = admin_actor()
    with tenant_ctx(tenant):
        row = a_field(actor, label="Pole Tag", entity="assets")
        services.save_custom_field_placement(actor, row["id"], {"S51": "input", "S50": "view"})
        services.set_custom_field_active(actor, row["id"], False)
        assert selectors.custom_field_registry("assets", screen="S50", mode="view") == []
        assert selectors.custom_field_registry("assets") == []
        stored = selectors.custom_field_row(row["id"])
    # The DEFINITION and its placement both survive — only `is_active` moved.
    assert stored["is_active"] is False
    assert stored["placement"] == {"S51": "input", "S50": "view"}


def test_us_ten_017_tc2__reactivation_returns_the_field_intact(growth_plan, identity_seam):
    tenant, _ = provisioned_tenant()
    actor = admin_actor()
    with tenant_ctx(tenant):
        row = a_field(actor, label="Pole Tag", entity="assets")
        services.save_custom_field_placement(actor, row["id"], {"S51": "input", "S50": "view"})
        services.set_custom_field_active(actor, row["id"], False)
        back = services.set_custom_field_active(actor, row["id"], True)
        assert [f["key"] for f in selectors.custom_field_registry("assets")] == ["pole_tag"]
    assert back["placement"] == {"S51": "input", "S50": "view"}
    assert back["is_active"] is True


def test_us_ten_017_tc3__no_delete_route_exists_at_any_layer(growth_plan, identity_seam):
    """BR-TEN-050. Three assertions, because "no delete" has three layers."""
    # 1 — no service.
    assert not hasattr(services, "delete_custom_field")
    # 2 — no route accepts DELETE.
    assert "DELETE" not in api.custom_field_item.cls().allowed_methods
    assert "DELETE" not in api.custom_fields_collection.cls().allowed_methods
    # 3 — the endpoint answers 405 rather than 404-by-accident.
    tenant, _ = provisioned_tenant()
    actor = admin_actor()
    with tenant_ctx(tenant):
        row = a_field(actor, label="Pole Tag", entity="assets")
    response = api_call(
        api.custom_field_item,
        "delete",
        user=FakeUser(),
        tenant=tenant,
        role="system_admin",
        field_id=row["id"],
    )
    assert response.status_code == 405


def test_us_ten_017_tc4__deactivating_frees_cap_headroom(growth_plan, identity_seam):
    tenant, _ = provisioned_tenant()
    actor = admin_actor()
    with tenant_ctx(tenant):
        made = [
            a_field(actor, label=key.replace("_", " ").title(), entity="accounts")
            for key in CAP_KEYS
        ]
        with pytest.raises(errors.BizError):
            a_field(actor, label="Route Note", entity="accounts")
        services.set_custom_field_active(actor, made[0]["id"], False)
        # The 11th now fits, because a deactivated field is retired vocabulary.
        assert a_field(actor, label="Route Note", entity="accounts")["key"] == "route_note"


def test_us_ten_017_tc5__a_definition_write_bumps_the_version_and_supersedes_the_key(
    growth_plan, identity_seam
):
    tenant, _ = provisioned_tenant()
    actor = admin_actor()
    with tenant_ctx(tenant):
        first = a_field(actor, label="Feeder Number", entity="assets")
        v1 = models.TenantSettings.objects.get(tenant_id=tenant.id).custom_field_version
        warm = selectors.custom_field_registry("assets")
        key_v1 = selectors.custom_field_cache_key("assets", v1)
        assert cache.get(key_v1) is not None  # the read warmed it
        assert [f["key"] for f in warm] == ["feeder_number"]

        services.update_custom_field(actor, first["id"], {"label": "Feeder ID"})
        v2 = models.TenantSettings.objects.get(tenant_id=tenant.id).custom_field_version
        assert v2 == v1 + 1
        # The NEXT read reflects the change — a new key, not a purged one. The
        # old key is still in the cache and is now unreachable, which is the
        # point of BR-TEN-053: there is no delete fan-out to get wrong.
        assert [f["label"] for f in selectors.custom_field_registry("assets")] == ["Feeder ID"]
        assert cache.get(key_v1) is not None


def test_us_ten_017_tc6__a_dead_cache_degrades_to_postgres_and_never_fails_the_request(
    growth_plan, identity_seam, monkeypatch
):
    tenant, _ = provisioned_tenant()
    actor = admin_actor()

    class DeadCache:
        def get(self, *a, **kw):
            raise ConnectionError("redis: connection refused")

        def set(self, *a, **kw):
            raise ConnectionError("redis: connection refused")

    monkeypatch.setattr(selectors, "_custom_field_cache", lambda: DeadCache())
    with tenant_ctx(tenant):
        a_field(actor, label="Feeder Number", entity="assets")
        rows = selectors.custom_field_registry("assets")
    assert [f["key"] for f in rows] == ["feeder_number"]  # screens still render


@pytest.mark.isolation
def test_us_ten_017_tc7__the_cache_key_carries_the_tenant_and_one_tenant_cannot_read_another(
    growth_plan, identity_seam
):
    """Redis has no RLS — it hands over any key it is asked for. So the
    assertion is made against the CACHE ITSELF, not through a selector that
    would filter by tenant anyway and prove nothing."""
    brazos, _ = provisioned_tenant()
    lonestar, _ = provisioned_tenant(lonestarridge_payload())
    actor = admin_actor()
    with tenant_ctx(brazos):
        a_field(actor, label="Feeder Number", entity="assets")
        selectors.custom_field_registry("assets")  # warm Brazos Bend
        brazos_version = models.TenantSettings.objects.get(tenant_id=brazos.id).custom_field_version
        brazos_key = selectors.custom_field_cache_key("assets", brazos_version)
    with tenant_ctx(lonestar):
        rows = selectors.custom_field_registry("assets")
        lonestar_version = models.TenantSettings.objects.get(
            tenant_id=lonestar.id
        ).custom_field_version
        lonestar_key = selectors.custom_field_cache_key("assets", lonestar_version)
    assert rows == []  # Lone Star Ridge gets its own, empty registry
    assert brazos_key != lonestar_key
    assert str(brazos.id) in brazos_key and str(lonestar.id) in lonestar_key
    # The two keys hold different payloads, so no version collision could ever
    # serve one tenant's definitions to the other.
    assert cache.get(brazos_key) != cache.get(lonestar_key)


def test_us_ten_017_tc8__deactivating_warns_and_never_blocks(growth_plan, identity_seam):
    """OQ-075 is CLOSED — warn, do not block (PO 2026-08-10). The story text
    still asks for a stub of that question by name and is STALE; the registry is
    the live record, and G8 fails a stub citing a closed question."""
    tenant, _ = provisioned_tenant()
    actor = admin_actor()
    with tenant_ctx(tenant):
        row = a_field(actor, label="Pole Tag", entity="assets")
        result = services.set_custom_field_active(actor, row["id"], False)
    assert result["is_active"] is False  # it PROCEEDED
    warning = result["template_warning"]
    assert warning["affected_templates"] == []
    # …and it says WHY the list is empty, so the day US-NOT-016 lands the caller
    # is holding a sentence that has become false rather than a silent zero.
    assert warning["basis"] == "no_template_variable_binding_in_r2"
    assert warning["story"] == "US-NOT-016"


# ── the endpoint surface (the API half of the four stories) ─────────────────
def test_us_ten_014_tc2b__the_management_endpoint_serves_the_table(growth_plan, identity_seam):
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        a_field(admin_actor(), label="Feeder Number", entity="assets")
    response = api_call(
        api.custom_fields_collection, "get", user=FakeUser(), tenant=tenant, role="system_admin"
    )
    assert response.status_code == 200
    assert [row["key"] for row in response.data] == ["feeder_number"]


def test_us_ten_017_tc5b__the_registry_endpoint_refuses_an_uncovered_entity(
    growth_plan, identity_seam
):
    tenant, _ = provisioned_tenant()
    response = api_call(
        api.custom_field_registry,
        "get",
        user=FakeUser(),
        tenant=tenant,
        role="billing_clerk",
        query={"entity": "invoices"},
    )
    assert response.status_code == 422


def test_us_ten_017_registry_endpoint_is_open_to_every_staff_role(growth_plan, identity_seam):
    """A meter tech filling in S51 is not a System Admin. The DEFINITIONS are
    tenant configuration, not tenant secrets."""
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        row = a_field(admin_actor(), label="Feeder Number", entity="assets")
        services.save_custom_field_placement(admin_actor(), row["id"], {"S51": "input"})
    response = api_call(
        api.custom_field_registry,
        "get",
        user=FakeUser(),
        tenant=tenant,
        role="billing_clerk",
        query={"entity": "assets", "screen": "S51", "mode": "input"},
    )
    assert response.status_code == 200
    assert [f["key"] for f in response.data["fields"]] == ["feeder_number"]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-TEN-015@a1c9f04 (story+rules snapshot over EP-TEN-09-custom-fields.md +
#         01-tenancy/02-business-rules.md BR-TEN-046..053 +
#         12-governance/01-open-questions.md OQ-075)
# generated: 2026-08-15 by story-coder (tenant custom-fields lane)
# checklist: A✔ B✔ C✔ D✔ E=deferred(no-frontend-half — the vitest suites carry it) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff --select E4,E7,E9,F✔ black✔ · see the lane report for counts and for the checks proved RED first
# exceptions: the RLS half of TC-6/TC-8/TC-11-shaped cases is the G5 Postgres suite (tests/isolation) — the app-layer half is asserted here on the sqlite tier and neither is claimed as the other · US-TEN-017 TC-8 asserts the OQ-075 RULING rather than the stub the story text still asks for; the registry says CLOSED and G8 fails a stub citing a closed question — REPORTED
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
