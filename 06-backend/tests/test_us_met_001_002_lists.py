# ── Trace ──────────────────────────────────────────────
# Story:    US-MET-001 (S14 Premises list tab) · US-MET-002 (S15 Units list tab)
# Rules:    BR-MET-001/002/003 · BR-MET-034 (types = Reference data) ·
#           BR-MET-035 (roles) · BR-MET-036 (occupancy DERIVED) ·
#           BR-MET-037 (delete guards) · BR-MET-046 (units never move) ·
#           BR-MET-047 (deactivation blockers) · BR-MET-048 (audit every change)
# Journeys: J2 step 1 handoff — "unit exists, occupancy derived"
# Note:     Occupancy resolves "vacant" because the customers module owns no
#           tables yet: no account can exist, so the derived answer is true BY
#           CONSTRUCTION (documented in apps/metering/seams.py), not assumed.
# ───────────────────────────────────────────────────────
"""US-MET-001 / US-MET-002 — premises & units list services, selectors, API."""

import pytest

from apps.metering import api, models, selectors, services
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

SEED = [
    ("1408 Bluestem Ln", "single_family", ["electric", "water"], "Whitfield Rentals LLC"),
    ("2201 Cane Island Pkwy", "single_family", ["electric"], "Chen, David"),
    ("500 Mason Rd Plaza", "commercial_building", ["electric", "water"], "Mason Rd Holdings"),
    ("77 Gulf Fwy Industrial", "commercial_building", ["electric"], "Northwind Mfg."),
]


def seed_premises(actor):
    return [
        make_premises(
            actor,
            address_line=address,
            premises_type=type_code,
            services_available=services_available,
            owner_manager=owner,
        )
        for address, type_code, services_available, owner in SEED
    ]


# ── US-MET-001 · S14 Premises list ──────────────────────────────────────────
def test_us_met_001_tc1__list_renders_with_rollup_and_default_sort(brazos, dana, audit_rows):
    actor = dana
    with tenant_ctx(brazos):
        created = seed_premises(actor)
        rows = [selectors.premises_detail_dict(r) for r in selectors.premises_list()]
        rollup = selectors.premises_rollup()
    assert len(rows) == 4
    # BR-MET-001: the premise number comes from the tenant series (seeded in
    # the fixture), and the default sort is premise_no asc.
    numbers = [r["premise_no"] for r in rows]
    assert numbers == sorted(numbers) and all(n and n.startswith("P-") for n in numbers)
    # AMENDED 2026-08-22 (BR-MET-101, W3 lane): the roll-up gained `common` —
    # how many units are common areas — beside the unchanged total.
    assert rollup == {"premises": 4, "units": 0, "common": 0, "vacant": 0, "pending_activation": 0}
    # BR-MET-003: only tenant-enabled services can be tagged.
    assert created[0]["services_available"] == ["electric", "water"]
    # BR-MET-048: every create wrote its audit row.
    created_rows = [r for r in audit_rows if r["action"] == "premises.created"]
    assert len(created_rows) == 4 and all(r["actor_user_id"] == dana.id for r in created_rows)


def test_us_met_001_tc2__filter_by_reference_data_type(brazos, dana):
    actor = dana
    with tenant_ctx(brazos):
        seed_premises(actor)
        rows = list(selectors.premises_list(filters={"type": "commercial_building"}))
        addresses = {r.address_line for r in rows}
    assert addresses == {"500 Mason Rd Plaza", "77 Gulf Fwy Industrial"}


def test_us_met_001_tc3__server_side_search_on_address(brazos, dana):
    actor = dana
    with tenant_ctx(brazos):
        seed_premises(actor)
        rows = list(selectors.premises_list(q="Bluestem"))
        one_char = list(selectors.premises_list(q="B"))
    assert [r.address_line for r in rows] == ["1408 Bluestem Ln"]
    assert len(one_char) == 4  # IS-3: below the 2-char floor the term is ignored


def test_us_met_001_tc4__units_scope_to_the_clicked_premise(brazos, dana):
    actor = dana
    with tenant_ctx(brazos):
        premises = seed_premises(actor)
        make_unit(actor, premises[2]["id"], label="200")
        make_unit(actor, premises[2]["id"], label="220")
        make_unit(actor, premises[0]["id"], label="Unit A")
        scoped = selectors.units_list(filters={"premises_id": premises[2]["id"]})
    assert {u.label for u in scoped} == {"200", "220"}


def test_us_met_001_tc5__delete_blocked_while_the_premise_has_units(brazos, dana):
    actor = dana
    with tenant_ctx(brazos):
        premise = make_premises(actor)
        make_unit(actor, premise["id"], label="Unit A")
        with pytest.raises(errors.BizError) as caught:
            services.delete_premises(actor, premise["id"])
        assert models.Premises.objects.filter(pk=premise["id"]).exists()  # nothing removed
    assert caught.value.br_ref == "BR-MET-037"
    assert caught.value.code == errors.BIZ_LOCKED
    assert caught.value.params["alternative"] == "deactivate"


def test_us_met_001_tc6__list_failure_is_a_catalog_envelope_not_a_blank_page(brazos):
    """TC-6's A18 failed-with-retry CARD is the frontend half (no backend half
    in this packet). The backend half asserted here: a refusal leaves the
    BE-02 catalog envelope, so the card has something lawful to render."""
    with tenant_ctx(brazos):
        with pytest.raises(errors.NotFoundError):
            selectors.premises_detail("00000000-0000-0000-0000-000000000000")


def test_us_met_001_tc7__roles_are_server_enforced(brazos, marcus):
    """BR-MET-035: create/edit = System Admin + Billing Clerk; deactivate and
    delete = System Admin; Executive is view-only."""
    with tenant_ctx(brazos):
        clerk_premise = make_premises(marcus, address_line="9 Clerk Way")
        assert clerk_premise["id"]
        with pytest.raises(errors.AuthError) as denied:
            make_premises(executive_actor(), address_line="9 Exec Way")
        assert denied.value.code == errors.AUTH_PERMISSION_DENIED
        with pytest.raises(errors.AuthError):
            services.delete_premises(marcus, clerk_premise["id"])


@pytest.mark.isolation
def test_us_met_001_tc8__isolation_no_cross_tenant_premise(brazos, dana, lonestar, erin):
    """Live RLS is the G5 suite's job (sqlite cannot enforce it); the app-layer
    tenant filter is asserted here in every permutation."""
    with tenant_ctx(brazos):
        seed_premises(dana)
    with tenant_ctx(lonestar):
        make_premises(erin, address_line="4102 Ranch Rd 12", services_available=["water"])
        rows = list(selectors.premises_list())
        assert [r.address_line for r in rows] == ["4102 Ranch Rd 12"]
        assert not list(selectors.premises_list(q="Bluestem"))


# ── US-MET-002 · S15 Units list ─────────────────────────────────────────────
def test_us_met_002_tc1__units_render_with_meters_and_derived_occupancy(brazos, dana):
    actor = dana
    with tenant_ctx(brazos):
        premise = make_premises(actor)
        unit = make_unit(actor, premise["id"], label="Unit A", services=["electric"])
        master = make_asset(
            actor,
            asset_no="M-7200",
            service="electric",
            unit_id=unit["id"],
            install_date="2026-08-01",
        )
        make_asset(
            actor,
            asset_no="M-7204",
            type="sub_meter",
            service="electric",
            parent_asset_no=master["asset_no"],
            unit_id=unit["id"],
            install_date="2026-08-01",
        )
        row = selectors.unit_list_dict(selectors.unit_row(unit["id"]))
    assert row["premise_no"] == premise["premise_no"]
    assert {(m["asset_no"], m["qualifier"]) for m in row["meters"]} == {
        ("M-7200", "master"),
        ("M-7204", "sub"),
    }
    # BR-MET-036: no active account (customers owns no tables) ⇒ vacant.
    assert row["occupancy"] == "vacant" and row["status"] == "vacant"
    assert row["sub_metered"] is True


def test_us_met_002_tc2__occupancy_filter_partitions_on_the_derived_value(brazos, dana):
    actor = dana
    with tenant_ctx(brazos):
        premise = make_premises(actor)
        make_unit(actor, premise["id"], label="Unit A")
        make_unit(actor, premise["id"], label="Unit B")
        vacant = selectors.units_list(filters={"occupancy": "vacant"})
        occupied = selectors.units_list(filters={"occupancy": "occupied"})
    assert {u.label for u in vacant} == {"Unit A", "Unit B"}
    assert occupied == []


def test_us_met_002_tc3__sub_metered_filter(brazos, dana):
    actor = dana
    with tenant_ctx(brazos):
        premise = make_premises(actor)
        plain = make_unit(actor, premise["id"], label="Unit A", services=["electric"])
        subbed = make_unit(actor, premise["id"], label="Apt 101", services=["electric"])
        master = make_asset(
            actor,
            asset_no="M-7300",
            service="electric",
            unit_id=plain["id"],
            install_date="2026-08-01",
        )
        make_asset(
            actor,
            asset_no="M-7301",
            type="sub_meter",
            service="electric",
            parent_asset_no=master["asset_no"],
            unit_id=subbed["id"],
            install_date="2026-08-01",
        )
        rows = selectors.units_list(filters={"occupancy": "sub_metered"})
    assert [u.label for u in rows] == ["Apt 101"]


def test_us_met_002_tc4__search_finds_a_unit_by_its_meter_number(brazos, dana):
    actor = dana
    with tenant_ctx(brazos):
        premise = make_premises(actor)
        unit = make_unit(actor, premise["id"], label="Suite 200", services=["electric"])
        make_asset(
            actor,
            asset_no="M-7204",
            service="electric",
            unit_id=unit["id"],
            install_date="2026-08-01",
        )
        rows = selectors.units_list(q="M-7204")
    assert [u.label for u in rows] == ["Suite 200"]


def test_us_met_002_tc5__delete_blocked_when_the_unit_was_ever_referenced(brazos, dana):
    actor = dana
    with tenant_ctx(brazos):
        premise = make_premises(actor)
        unit = make_unit(actor, premise["id"], label="Unit A", services=["electric"])
        make_asset(
            actor,
            asset_no="M-7001",
            service="electric",
            unit_id=unit["id"],
            install_date="2026-08-01",
        )
        with pytest.raises(errors.BizError) as caught:
            services.delete_unit(actor, unit["id"])
        assert models.Unit.objects.filter(pk=unit["id"]).exists()
    assert caught.value.br_ref == "BR-MET-037"
    assert caught.value.params["referenced_by"]["assets"] == 1
    assert caught.value.params["alternative"] == "deactivate"


def test_us_met_002_tc6__duplicate_label_within_a_premise_is_refused(brazos, dana):
    actor = dana
    with tenant_ctx(brazos):
        premise = make_premises(actor)
        make_unit(actor, premise["id"], label="Unit A")
        second = make_unit(actor, premise["id"], label="Unit B")
        with pytest.raises(errors.ValidationError) as caught:
            services.update_unit(actor, second["id"], {"label": "unit a"})
        assert caught.value.field_errors[0]["field"] == "label"
        # BR-MET-046: and a unit never moves to another premise.
        with pytest.raises(errors.BizError) as moved:
            services.update_unit(actor, second["id"], {"premises_id": premise["id"]})
        assert moved.value.br_ref == "BR-MET-046"


def test_us_met_002_tc7__occupancy_can_never_be_written(brazos, dana):
    """BR-MET-036: the wizard captures no occupancy input and the API refuses
    one — occupancy is derived, always."""
    actor = dana
    with tenant_ctx(brazos):
        premise = make_premises(actor)
        unit = make_unit(actor, premise["id"], label="Unit A")
        with pytest.raises(errors.ValidationError) as caught:
            services.update_unit(actor, unit["id"], {"occupancy": "occupied"})
    assert caught.value.field_errors[0]["message_key"] == "metering.unit.occupancy_is_derived"
    assert not any(f.name == "occupancy" for f in models.Unit._meta.get_fields())


def test_us_met_002_tc8__api_list_paginates_and_deactivate_is_admin_only(brazos, dana):
    actor = dana
    with tenant_ctx(brazos):
        premise = make_premises(actor)
        unit = make_unit(actor, premise["id"], label="Unit A")
    response = api_call(
        api.units, "get", user=FakeUser(), role="billing_clerk", tenant=brazos, query={"per": "50"}
    )
    assert response.status_code == 200 and response.data["count"] == 1
    denied = api_call(
        api.unit_deactivate,
        "post",
        user=FakeUser(),
        role="billing_clerk",
        tenant=brazos,
        unit_id=unit["id"],
    )
    assert denied.status_code == 403  # BR-MET-035 server-enforced


@pytest.mark.isolation
def test_us_met_002_tc9__isolation_same_label_in_two_tenants(brazos, dana, lonestar, erin):
    with tenant_ctx(brazos):
        premise = make_premises(dana)
        make_unit(dana, premise["id"], label="Unit A")
    with tenant_ctx(lonestar):
        other = make_premises(erin, address_line="4102 Ranch Rd 12", services_available=["water"])
        make_unit(erin, other["id"], label="Unit A")  # per-tenant uniqueness
        rows = selectors.units_list()
        assert len(rows) == 1 and str(rows[0].premises_id) == other["id"]


def test_us_met_001_tc9__api_list_carries_the_rollup_and_create_returns_location(brazos, dana):
    """The S14 surface end-to-end: paginated list + header roll-up, the
    Reference-data type list, and a 201 + Location on create."""
    with tenant_ctx(brazos):
        premise = make_premises(dana)
        make_unit(dana, premise["id"], label="Unit A", services=["electric"])
        # BR-MET-401 — resolved HERE, inside the tenant context. `owner_for`
        # reads `premises_owners` and so needs `app.tenant_id` set; called down
        # in the `data={...}` literal it raises AUTH-003, because the api_call
        # helper sets the tenant INSIDE the request and not around the argument
        # expression that builds it.
        api_owner_id = owner_for(dana)
    listed = api_call(api.premises, "get", user=FakeUser(), role="system_admin", tenant=brazos)
    assert listed.status_code == 200 and listed.data["count"] == 1
    # AMENDED 2026-08-22 (BR-MET-101, W3 lane): `common` rides in the roll-up.
    assert listed.data["rollup"] == {
        "premises": 1,
        "units": 1,
        "common": 0,
        "vacant": 1,
        "pending_activation": 0,
    }
    types = api_call(
        api.premises_types, "get", user=FakeUser(), role="billing_clerk", tenant=brazos
    )
    assert types.status_code == 200 and len(types.data) == 6  # BR-MET-034 seeded set (6 since CR-010 item 4, "government_building")
    created = api_call(
        api.premises,
        "post",
        user=FakeUser(),
        role="system_admin",
        tenant=brazos,
        # BR-MET-401 / DEF-650 — the owner is REQUIRED at creation (PO
        # 2026-08-27: *"without owner how you can create premsies"*), so the
        # HTTP door refuses a payload without one. That refusal IS the rule; the
        # test names an owner rather than the guard being weakened for it.
        data={"address_line": "9 API Way", "owner_id": api_owner_id},
    )
    assert created.status_code == 201 and created["Location"].startswith("/premises/")
    detail = api_call(
        api.premises_detail,
        "get",
        user=FakeUser(),
        role="executive",
        tenant=brazos,
        premises_id=premise["id"],
    )
    assert detail.status_code == 200 and len(detail.data["unit_rows"]) == 1
