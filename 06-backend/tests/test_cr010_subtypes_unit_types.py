# ── Trace ──────────────────────────────────────────────
# Change:   CR-010 — the two CONFIRMED schema slices (PO 2026-08-17):
#           "Part-10 confirmations" 10.0 ("add them" — the account sub-type
#           tree) and A-section item 4 ("this is correct" — unit types become
#           editable rows)   Screens: S8 · S16 · S18
# Rules:    BR-CUS-067 (two-level sub-type tree, tenant rows, 12 seeded, parent
#           REQUIRED on new/edited rows) · BR-MET-084 (unit types are a seeded
#           metering reference list; validation resolves against it with a
#           legacy fallback) · BR-TEN-012 (idempotent by natural key) ·
#           BR-TEN-030/031/034/036 (the lookup-list laws)
# Tests:    this file
# Impacts:  apps/customers/{models,services,lookups}.py ·
#           apps/metering/{models,services,lookups}.py ·
#           apps/tenancy/services.py LOOKUP_LISTS + SEED_LIST_OWNERS ·
#           07-frontend referenceDataConfig.ts (the two new cards — the join
#           guard in test_def_236_premises_types_card.py enforces the pairing)
# ───────────────────────────────────────────────────────
"""CR-010's two schema slices, proved from seeding to screen contract.

Both lists follow the DEF-026 posture: the platform fixture carries NO entries
on purpose — the owning module's rule-cited constant (SEED_ACCOUNT_SUBTYPES ·
SEED_UNIT_TYPES) is the single ratified source, so there is no second copy to
drift. What THIS file proves that nothing else can:

  · the 12 sub-types land at provisioning, under the right platform parents;
  · a sub-type without a parent is refused BY NAME (the ratified tree is
    two-level — a floating sub-type is a sub-type of nothing);
  · the five unit types land as `is_system` rows and unit validation resolves
    against the TABLE, falling back to the legacy tuple only where the tenant
    holds no rows (pre-CR tenants, toggle-off tenants);
  · renaming or deleting a USED unit-type code is refused — the column is
    TEXT, not an FK, so BR-TEN-030/034 live in the handler here, where the
    premises-types twin can lean on PROTECT.
"""

import pytest

from apps.customers import models as customers_models
from apps.customers import services as customers_services
from apps.metering import models as metering_models
from apps.metering import services as metering_services
from apps.tenancy import services as tenancy_services
from core import errors

from tests.test_us_ten_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import (
    lonestarridge_payload,
    provisioned_tenant,
    tenant_ctx,
)
from tests.test_us_met_helpers import (  # noqa: F401 — brazos/dana/lonestar are fixtures
    brazos,
    dana,
    lonestar,
    make_premises,
    make_unit,
    staff_actor,
)

pytestmark = pytest.mark.django_db

#: The ratified tree, verbatim from the decision log row of 2026-08-17
#: ("Part-10 confirmations" 10.0). code → parent account_type code.
RATIFIED_TREE = {
    "single_family": "residential",
    "multi_family": "residential",
    "senior_low_income": "residential",
    "small_commercial": "commercial",
    "large_commercial": "commercial",
    "institutional_non_profit": "commercial",
    "healthcare": "commercial",
    "light_industrial": "industrial",
    "heavy_industrial": "industrial",
    "municipal_buildings": "government",
    "schools": "government",
    "parks_facilities": "government",
    # ⚠ THE THIRTEENTH — PO ruling 2026-09-07, verbatim: *"please add
    # Governtment in it"*. The GENERAL government subtype, beside the three
    # specific kinds above it. It is NOT a duplicate of the platform account
    # TYPE it sits under: this is the tenant-editable level beneath the type
    # (BR-CUS-067), which is what makes the two names legitimate at once.
    "government": "government",
}


def _subtype_handler():
    return tenancy_services.LOOKUP_LISTS["account_subtypes"].handler


# ═══════════════════════════════════════════════════════════════════════════
# Account sub-types — BR-CUS-067
# ═══════════════════════════════════════════════════════════════════════════


def test_cr010__the_twelve_subtypes_seed_at_provisioning(growth_plan, identity_seam):
    """PO 2026-08-17: "add them". Each row under its ratified parent, every one
    is_system (BR-TEN-036).

    ⚠ **THE NAME SAYS TWELVE AND `RATIFIED_TREE` NOW HOLDS THIRTEEN**, since
    the PO added Government on 2026-09-07. The function name is left alone so
    `git log -S` still finds both halves of the list's history on one
    identifier — the same reason `test_the_three_defaults_seed_for_a_fresh_
    tenant` still says three."""
    tenant, result = provisioned_tenant()
    assert "account_subtypes" not in result["reference_seed"]["skipped"]
    with tenant_ctx(tenant):
        rows = list(
            customers_models.AccountSubtype.objects.filter(tenant=tenant).select_related(
                "account_type"
            )
        )
    tree = {row.code: row.account_type.code for row in rows}
    assert tree == RATIFIED_TREE
    assert all(row.is_system and row.active for row in rows)


def test_cr010__subtype_seed_replay_writes_nothing(growth_plan, identity_seam):
    """BR-TEN-012: idempotent by natural key; a tenant rename survives."""
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        renamed = customers_models.AccountSubtype.objects.get(tenant=tenant, code="healthcare")
        renamed.name = "Hospitals & clinics (renamed by the tenant)"
        renamed.save(update_fields=["name", "updated_at"])
        assert customers_services.ensure_account_subtypes() == 0
        renamed.refresh_from_db()
        assert renamed.name == "Hospitals & clinics (renamed by the tenant)"
        assert customers_models.AccountSubtype.objects.filter(tenant=tenant).count() == 13


def test_cr010__the_card_serves_parent_code_and_name(growth_plan, identity_seam):
    """The S8 card's second level: every row says which type it sits under —
    the server's own `parent_code`/`parent_name`, the BR-MET-066b keys the ONE
    list view already renders."""
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        handler = _subtype_handler()
        assert handler is not None, "account_subtypes has no registered handler"
        assert handler.count() == 13
        serialized = {
            row["code"]: row for row in (handler.serialize(r) for r in handler.search(None))
        }
    assert serialized["single_family"]["parent_code"] == "residential"
    assert serialized["single_family"]["parent_name"] == "Residential"
    assert serialized["schools"]["parent_code"] == "government"


def test_cr010__a_tenant_can_add_its_own_subtype_under_a_type(growth_plan, identity_seam):
    """The PO's item-1 sentence: the rows are the tenant's to extend."""
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        handler = _subtype_handler()
        row = handler.create({"code": "church", "name": "Church", "parent_code": "commercial"})
        assert row.is_system is False
        assert row.account_type.code == "commercial"
        # 13 seeded (PO 2026-09-07 added Government) + the tenant's own = 14.
        assert handler.count() == 14


def test_cr010__a_subtype_without_a_parent_is_refused_by_name(growth_plan, identity_seam):
    """The tree is two-level BY RULING — a floating sub-type is refused, and
    the refusal names the field the S8 picker draws (`parent_code`)."""
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        handler = _subtype_handler()
        with pytest.raises(errors.ValidationError) as caught:
            handler.create({"code": "floating", "name": "Floating"})
        assert caught.value.message_key == "customers.lookups.parent_required"
        with pytest.raises(errors.ValidationError) as caught:
            handler.create({"code": "floating", "name": "Floating", "parent_code": ""})
        assert caught.value.message_key == "customers.lookups.parent_required"


def test_cr010__an_unknown_parent_is_refused_with_the_allowed_set(growth_plan, identity_seam):
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        handler = _subtype_handler()
        with pytest.raises(errors.ValidationError) as caught:
            handler.create({"code": "x", "name": "X", "parent_code": "cooperative"})
    assert caught.value.message_key == "customers.lookups.parent_unknown"
    assert caught.value.params["allowed"] == [
        "residential",
        "commercial",
        "industrial",
        "government",
    ]


def test_cr010__an_edit_cannot_blank_the_parent(growth_plan, identity_seam):
    """The picker always sends `parent_code`; an empty one is refused rather
    than silently promoting the row to a level the tree does not have."""
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        handler = _subtype_handler()
        row = handler.search("healthcare").first()
        with pytest.raises(errors.ValidationError):
            handler.update(row, {"parent_code": ""})
        moved = handler.update(row, {"parent_code": "industrial"})
        assert moved.account_type.code == "industrial"


def test_cr010__a_seeded_subtype_deactivates_but_never_deletes(growth_plan, identity_seam):
    """BR-TEN-036, the same law every seeded list enforces."""
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        handler = _subtype_handler()
        seeded = handler.search("schools").first()
        assert seeded.is_system
        handler.set_active(seeded, False)
        assert handler.get(seeded.pk).active is False
        with pytest.raises(errors.BizError):
            handler.delete(seeded)


def test_cr010__duplicate_subtype_codes_refuse_case_insensitively(growth_plan, identity_seam):
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        handler = _subtype_handler()
        with pytest.raises(errors.ValidationError):
            handler.create({"code": "HEALTHCARE", "name": "Duplicate", "parent_code": "commercial"})


def test_cr010__a_tenant_extension_never_leaks(growth_plan, identity_seam):
    """Both tenants hold the seeded 13; isolation is proved on the tenant's
    own extension (the sqlite tier of the premises_types precedent — the live
    RLS policy is 0002's, unchanged by the 0011 column)."""
    brazos, _ = provisioned_tenant()
    lonestar, _ = provisioned_tenant(lonestarridge_payload())
    handler = _subtype_handler()
    with tenant_ctx(brazos):
        handler.create({"code": "church", "name": "Church", "parent_code": "commercial"})
    with tenant_ctx(lonestar):
        assert handler.count() == 13
        codes = {handler.serialize(row)["code"] for row in handler.search(None)}
    assert "church" not in codes


# ═══════════════════════════════════════════════════════════════════════════
# Unit types — BR-MET-084 (CR-010 A-4: "this is correct")
# ═══════════════════════════════════════════════════════════════════════════


def _unit_type_handler():
    return tenancy_services.LOOKUP_LISTS["unit_types"].handler


def test_cr010__the_five_unit_types_seed_at_provisioning(brazos):
    """The US-MET-002 §5 option set becomes rows: five, is_system, named with
    the product's own established display copy."""
    with tenant_ctx(brazos):
        rows = list(metering_models.UnitType.objects.filter(tenant=brazos))
        handler = _unit_type_handler()
        assert handler is not None, "unit_types has no registered handler"
        assert handler.count() == 5
    assert {(r.code, r.name) for r in rows} == set(metering_services.SEED_UNIT_TYPES)
    assert all(r.is_system and r.active for r in rows)


def test_cr010__unit_validation_resolves_against_the_table(brazos, dana):
    """The whole point of A-4: a tenant-added type is USABLE on a unit, and
    the stored value is the row's canonical code (case-insensitive input)."""
    with tenant_ctx(brazos):
        _unit_type_handler().create({"code": "storage", "name": "Storage locker"})
        premises = make_premises(dana, address_line="9 Locker Rd")
        made = make_unit(dana, premises["id"], label="L-1", unit_type="STORAGE")
        stored = metering_models.Unit.objects.get(pk=made["id"])
    assert stored.unit_type == "storage"


def test_cr010__an_unknown_unit_type_refuses_with_the_tenant_set(brazos, dana):
    with tenant_ctx(brazos):
        premises = make_premises(dana, address_line="10 Unknown Way")
        with pytest.raises(errors.ValidationError) as caught:
            make_unit(dana, premises["id"], unit_type="warehouse")
    assert caught.value.params["allowed"] == sorted(c for c, _ in metering_services.SEED_UNIT_TYPES)


def test_cr010__a_deactivated_type_is_not_resurrected_by_the_legacy_fallback(brazos, dana):
    """BR-TEN-034's spirit: deactivating a row stops it being pickable — even
    though 'commercial' is also in the legacy tuple, the tenant's own row wins
    and its deactivation is honoured."""
    with tenant_ctx(brazos):
        handler = _unit_type_handler()
        row = handler.search("commercial").filter(code="commercial").first()
        handler.set_active(row, False)
        premises = make_premises(dana, address_line="11 Retired St")
        with pytest.raises(errors.ValidationError):
            make_unit(dana, premises["id"], unit_type="commercial")


def test_cr010__a_tenant_with_no_rows_keeps_the_legacy_vocabulary(growth_plan, identity_seam):
    """The safe fallback: a tenant provisioned with the S111 toggle OFF has no
    unit_type rows (the list is DISCRETIONARY, BR-TEN-067) and can still
    create a unit with a legacy code — nothing ever stored goes invalid."""
    tenant, _ = provisioned_tenant(
        lonestarridge_payload(
            subdomain="toggleoffutil",
            load_defaults=False,
            owner={
                "full_name": "T. Off",
                "email": "t.off@toggleoff.test",
                "password": "An0ther!passw0rd",
                "phone": None,
            },
        )
    )
    actor = staff_actor(tenant, "system_admin", "admin@toggleoff.test")
    with tenant_ctx(tenant):
        assert metering_models.UnitType.objects.filter(tenant=tenant).count() == 0
        premises = make_premises(actor, address_line="12 Legacy Ln", services_available=["water"])
        made = make_unit(actor, premises["id"], unit_type="residential")
        assert metering_models.Unit.objects.get(pk=made["id"]).unit_type == "residential"
        with pytest.raises(errors.ValidationError) as caught:
            make_unit(actor, premises["id"], label="Unit B", unit_type="warehouse")
    assert caught.value.params["allowed"] == list(metering_services.UNIT_TYPES)


def test_cr010__a_used_unit_type_freezes_its_code_and_refuses_delete(brazos, dana):
    """`units.unit_type` is TEXT, not an FK — no PROTECT will save us, so the
    handler itself is BR-TEN-030/034's enforcement and this is its proof."""
    with tenant_ctx(brazos):
        handler = _unit_type_handler()
        row = handler.create({"code": "storage", "name": "Storage locker"})
        premises = make_premises(dana, address_line="13 Frozen Ct")
        make_unit(dana, premises["id"], unit_type="storage")
        assert handler.used_by(row) == 1
        with pytest.raises(errors.BizError) as frozen:
            handler.update(row, {"code": "locker"})
        assert frozen.value.message_key == "metering.lookups.code_frozen_in_use"
        handler.update(row, {"name": "Storage locker (renamed)"})  # name stays free
        with pytest.raises(errors.BizError) as locked:
            handler.delete(row)
        assert locked.value.message_key == "metering.lookups.row_in_use_not_deletable"
        # an UNUSED tenant row deletes; a SEEDED row never does (BR-TEN-036)
        unused = handler.create({"code": "kiosk", "name": "Kiosk"})
        handler.delete(unused)
        seeded = handler.search("common").first()
        with pytest.raises(errors.BizError):
            handler.delete(seeded)


def test_cr010__a_unit_type_extension_never_leaks(brazos, lonestar):
    handler = _unit_type_handler()
    with tenant_ctx(brazos):
        handler.create({"code": "storage", "name": "Storage locker"})
    with tenant_ctx(lonestar):
        assert handler.count() == 5
        codes = {handler.serialize(row)["code"] for row in handler.search(None)}
    assert "storage" not in codes


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-010 "Part-10 confirmations" 10.0 + A-section items 1/4
#         (12-governance/02-decision-log.md, 2026-08-17)
# generated: 2026-08-18 by the CR-010 account-subtypes/unit-types lane
# checklist: A✔ B✔ C✔ D✔ E✔(the two cards in referenceDataConfig.ts) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: this file · tests/test_def_236_premises_types_card.py (the join guard
#        demands the cards) · tests/test_reference_data_completeness.py (the
#        registry/seeder set equation)
# exceptions: none
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
