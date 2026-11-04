# ── Trace ──────────────────────────────────────────────
# Story:    US-TEN-009 (reference-data card grid) · US-TEN-010 (per-list view,
#           search, add, edit) · US-TEN-011 (deactivate, delete, 🔒 audit-lock)
# Rules:    BR-TEN-016 · BR-TEN-029 (live counts) · BR-TEN-030 (ci-unique codes,
#           immutable once used) · BR-TEN-031 (framework vs content) ·
#           BR-TEN-033 (templates card navigation-only) · BR-TEN-034 (audit-lock)
#           · BR-TEN-036 (seeded + tenant-extensible)
# Note:     only the tenancy-owned UoM list is WIRED; other lists' handlers are
#           their owning lanes' (register_lookup_handler) — an unwired list 404s
#           (skip-until-wired), proven below. Content-routing proven with a stub
#           handler. RLS halves = G5 suite.
# ───────────────────────────────────────────────────────
"""US-TEN-009/010/011 — reference-data framework + UoM list content."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from apps.tenancy import api, models, selectors, services
from core import errors

from tests.test_us_ten_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import (
    FakeUser,
    admin_actor,
    api_call,
    audit_actions,
    lonestarridge_payload,
    provisioned_tenant,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


def _uom_id(tenant, code):
    return models.Uom.objects.get(tenant=tenant, code__iexact=code).pk


#: **HOW MANY UNITS OF MEASURE A FRESHLY PROVISIONED TENANT RECEIVES, READ FROM
#: THE FIXTURE RATHER THAN TYPED (`CR-063`, 2026-09-02).**
#:
#: ⚠ **IT WAS TYPED IN FOUR PLACES IN THIS FILE AND THE ELEVENTH UNIT BROKE ALL
#: FOUR AT ONCE**, with `assert 27 == 26` naming neither the unit that arrived
#: nor the reason. `connection` was added for **fire**, the eleventh utility
#: service, and a count typed into a test is a second, silent statement about
#: what the product contains: the catalogue grew and the literal did not.
#:
#: **NONE OF THE FOUR CASES IS ABOUT THIS NUMBER.** They are about a card showing
#: a LIVE count, a tenant-added row moving it, a short search string applying NO
#: filter, and a pagination envelope — the count is scaffolding in every one. So
#: it is derived here once and a TWELFTH unit moves nothing.
#:
#: ⚠ **THIS IS NOT A LICENCE TO DERIVE EVERY COUNT.**
#: `test_cr010_reference_list_inventory.py` states the same figure as a LITERAL
#: on purpose — its job is *"vocabulary cannot change without the record changing
#: with it"*, so a typed number is what makes a seeded-list change a visible diff
#: somebody approves. Deriving it there would delete the check. The rule is:
#: derive it where the number is INCIDENTAL, type it where the number IS the
#: assertion.
SEEDED_UOM_COUNT = len(
    json.loads(Path(services.FIXTURE_PATH).read_text(encoding="utf-8"))["uoms"]
)


# ── US-TEN-009 — card grid ──────────────────────────────────────────────────
def test_us_ten_009_tc1__cards_show_live_per_tenant_counts(growth_plan, identity_seam):
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        cards = {card["list"]: card for card in selectors.lookup_cards()}
    assert cards["uoms"]["count"] == SEEDED_UOM_COUNT  # seeded list, LIVE count (CR-010 10.2)
    # The two lists tenancy HOSTS for unwired owner lanes render their W0
    # fixture seeds (reference-data gap lane 2026-08-09, BR-TEN-036).
    assert cards["reason_codes"]["count"] == 5
    # incl. wire + money_order, and since 2026-09-23 `tap_pay` (CR-139-BRC07
    # P5.11, PO: a clerk picks it and types the terminal's reference) - DEF-TEN-9020.
    assert cards["payment_methods"]["count"] == 8
    assert cards["reason_codes"]["owner"] == "billing"  # hosting ≠ owning
    assert cards["payment_methods"]["owner"] == "payments"
    # The two customers lists were absent here (skip-until-wired) until the W2
    # customers SCHEMA + SEAM slice landed their tables, seam and handlers on
    # 2026-08-10; they now render with live counts like any other card.
    # 5 → 6 on 2026-08-25 · BR-CUS-107 (PO ruling closing DEF-701) added
    # `disconnected` / "Disconnected" / behaviour class `non_billable`, the
    # state a CUT account is in. Fixture V2.48.0.0 and migration
    # customers.0025 both deliver it; THIS ASSERTION WAS THE ONE THING THE
    # ruling did not sweep and it has been RED since (DEF-976, filed as
    # DEF-974 on this lane's own branch and renumbered at merge: two lanes
    # allocated 974 within minutes, because `file_defect.py` reads the tip of
    # the CALLER'S branch and two branches that have not met each read 973) —
    # a tenancy
    # test asserting a customers count, so neither lane had a reason to open
    # it. `test_cr010_reference_list_inventory.py` is where this figure
    # actually lives and it has said 6 since the day of the ruling.
    assert cards["account_statuses"]["count"] == 6  # BR-CUS-055 + BR-CUS-107
    assert cards["account_statuses"]["owner"] == "customers"
    # 4 → 8 on 2026-08-24 · BR-CUS-094 (PO verbatim: *"Expand the signed list
    # to seven"*). Migration customers.0019 adds `agricultural`,
    # `institutional`, `municipal` and `builder_developer` to 0003's four, and
    # marks `government` LEGACY — unselectable on new records and still a ROW,
    # which is why the count is 8 and not 7. Red since that day (DEF-976); the
    # figure lives in `test_cr010_reference_list_inventory.py`, whose own row
    # reads `("account_types": (8, 4, "fixture · PLATFORM rows,
    # migration-seeded"))` — the 4 there is r10's BADGE, not the live count,
    # and confusing the two is how this assertion looked right.
    assert cards["account_types"]["count"] == 8  # r5 #12 [D5] + BR-CUS-094
    # The templates card still has NO backend row at all (BR-TEN-033) — it is
    # client navigation, not a lookup list, so it never appears here.
    assert "templates" not in cards


def test_us_ten_009_tc4__adding_entry_bumps_card_count_live(growth_plan, identity_seam):
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        services.create_lookup_entry(
            admin_actor(), "uoms", {"code": "acre-ft", "name": "Acre-foot"}
        )
        cards = {card["list"]: card for card in selectors.lookup_cards()}
    # BR-TEN-029: computed at render, not cached. The `+ 1` is the assertion —
    # one row was just added — and it is written as arithmetic on the seeded
    # count so it keeps saying that whatever the catalogue holds.
    assert cards["uoms"]["count"] == SEEDED_UOM_COUNT + 1


def test_us_ten_009_tc5__clerk_denied_at_the_reference_data_surface(growth_plan, identity_seam):
    tenant, _ = provisioned_tenant()
    denied = api_call(api.lookup_cards, "get", user=FakeUser(), role="billing_clerk", tenant=tenant)
    assert denied.status_code == 403  # A4: Settings = System Admin only
    listing = api_call(
        api.lookups,
        "get",
        user=FakeUser(),
        role="billing_clerk",
        tenant=tenant,
        list_code="uoms",
    )
    assert listing.status_code == 403


def test_us_ten_009_tc6__counts_are_per_tenant(growth_plan, identity_seam):
    brazos, _ = provisioned_tenant()
    lonestar, _ = provisioned_tenant(lonestarridge_payload(load_defaults=False))
    with tenant_ctx(brazos):
        services.create_lookup_entry(
            admin_actor(), "uoms", {"code": "acre-ft", "name": "Acre-foot"}
        )
    with tenant_ctx(lonestar):
        cards = {card["list"]: card for card in selectors.lookup_cards()}
    assert cards["uoms"]["count"] == 0  # Lone Star Ridge unchanged (toggle was off)


# ── US-TEN-010 — view, search, add, edit ────────────────────────────────────
def test_us_ten_010_tc1__create_routes_through_owning_module_handler(
    growth_plan, identity_seam, audit_rows
):
    """BR-TEN-031: tenancy renders/routes; the OWNER's handler validates and
    writes. Proven with a stub handler registered for charge_codes."""
    tenant, _ = provisioned_tenant()
    calls = SimpleNamespace(created=[])
    # Restore the REAL handler afterwards, not None. The old teardown wrote
    # None over rating's startup-registered handler, so every test scheduled
    # after this file saw the charge_codes card vanish from lookup_cards() —
    # invisible in the full suite only because alphabetical file order happens
    # to run the completeness suite first. Found 2026-08-17 when a CR-010
    # trio run reordered them; same class as the account_statuses case below,
    # which already restores correctly.
    landed = services.LOOKUP_LISTS["charge_codes"].handler

    class StubHandler:
        def get(self, entry_id):
            return None

        def count(self):
            return 0

        def search(self, q):
            return []

        def used_by(self, row):
            return 0

        def serialize(self, row):
            return dict(row)

        def create(self, payload):
            calls.created.append(payload)
            return {"id": "stub-1", "code": payload["code"], "used_by": 0}

    services.register_lookup_handler("charge_codes", StubHandler())
    try:
        audit_rows.clear()
        with tenant_ctx(tenant):
            result = services.create_lookup_entry(
                admin_actor(),
                "charge_codes",
                {"code": "RECON", "name": "Reconnect fee", "amount": "45"},
            )
        assert calls.created[0]["code"] == "RECON"  # owner handler received it
        assert result["code"] == "RECON"
        assert "settings.lookup.created" in audit_actions(audit_rows)  # BR-TEN-016
    finally:
        services.LOOKUP_LISTS["charge_codes"].handler = landed


def test_us_ten_010_tc2__search_is_server_side_min_two_chars(growth_plan, identity_seam):
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        hit_code = selectors.lookup_page("uoms", "kg")
        hit_name = selectors.lookup_page("uoms", "gallons")
        too_short = selectors.lookup_page("uoms", "k")
    assert [r["code"] for r in hit_code] == ["kgal"]  # matches by code
    assert [r["code"] for r in hit_name] == ["kgal"]  # matches by name
    # IS-3: under 2 chars → NO filter applied, so every seeded row comes back.
    # "all of them" is the assertion; the number is scaffolding (CR-010 10.2).
    assert len(too_short) == SEEDED_UOM_COUNT


def test_us_ten_010_tc3__code_immutable_once_used_name_stays_editable(growth_plan, identity_seam):
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        kgal_id = _uom_id(tenant, "kgal")  # water's primary → Used by 1
        renamed = services.update_lookup_entry(
            admin_actor(), "uoms", kgal_id, {"name": "Thousand gallons (kgal)"}
        )
        assert renamed["name"] == "Thousand gallons (kgal)"  # name saves
        with pytest.raises(errors.BizError) as excinfo:
            services.update_lookup_entry(admin_actor(), "uoms", kgal_id, {"code": "KG"})
    assert excinfo.value.code == errors.BIZ_IMMUTABLE  # BR-TEN-030
    assert excinfo.value.br_ref == "BR-TEN-030"
    assert excinfo.value.params["used_by"] >= 1


def test_us_ten_010_tc4__case_insensitive_duplicate_names_existing_entry(
    growth_plan, identity_seam
):
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        with pytest.raises(errors.ValidationError) as excinfo:
            services.create_lookup_entry(
                admin_actor(), "uoms", {"code": "KGAL", "name": "Kilogallons again"}
            )
    fe = excinfo.value.field_errors[0]
    assert fe["field"] == "code"
    assert fe["params"]["existing"] == "kgal"  # names the existing entry


def test_us_ten_010_tc5__owner_validation_failure_writes_nothing(
    growth_plan, identity_seam, audit_rows
):
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        audit_rows.clear()
        with pytest.raises(errors.ValidationError):
            services.create_lookup_entry(admin_actor(), "uoms", {"code": "", "name": ""})
    assert audit_actions(audit_rows) == []  # nothing written, nothing audited


def test_us_ten_010_tc6__unwired_owner_list_is_404_until_its_lane_lands(growth_plan, identity_seam):
    """OQ-031 CLOSED → BR-TEN-036: enum lists become owner-module lookup tables.
    Until those lanes register handlers, the list resource does not exist here —
    404, never a guessed implementation (skip-until-wired).

    AMENDED 2026-08-10: this test kept its example one lane at a time —
    `payment_methods` until the reference-data gap lane, then the two
    customers-owned lists until the W2 customers SCHEMA + SEAM slice. EVERY
    declared list now has a registered handler, so there is no live example
    left and the MECHANISM is asserted directly instead: a declared list whose
    handler is None answers 404, exactly as an unknown list does. That
    indistinguishability is the point — a caller cannot tell "this deployment
    has not landed that lane" from "no such list", which is the same HR-1
    posture the unknown-tenant 404 takes."""
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        landed = services.LOOKUP_LISTS["account_statuses"].handler
        assert landed is not None, "the customers lane registers this handler at startup"
        services.LOOKUP_LISTS["account_statuses"].handler = None
        try:
            with pytest.raises(errors.NotFoundError):
                services.create_lookup_entry(
                    admin_actor(),
                    "account_statuses",
                    {"code": "legal_hold", "name": "Legal hold"},
                )
            with pytest.raises(errors.NotFoundError):
                selectors.lookup_page("account_statuses", None)
        finally:
            services.LOOKUP_LISTS["account_statuses"].handler = landed
        with pytest.raises(errors.NotFoundError):  # unknown list = same answer
            selectors.lookup_page("no_such_list", None)


def test_us_ten_010_tc7__same_code_lives_independently_per_tenant(growth_plan, identity_seam):
    brazos, _ = provisioned_tenant()
    lonestar, _ = provisioned_tenant(lonestarridge_payload(load_defaults=False))
    with tenant_ctx(brazos):
        services.create_lookup_entry(
            admin_actor(), "uoms", {"code": "acre-ft", "name": "Acre-foot"}
        )
    with tenant_ctx(lonestar):
        assert selectors.lookup_page("uoms", "acre") == []  # not visible
        mine = services.create_lookup_entry(
            admin_actor(), "uoms", {"code": "acre-ft", "name": "Acre-foot"}
        )  # own add succeeds independently
        assert mine["code"] == "acre-ft"


# ── US-TEN-011 — deactivate, delete, 🔒 audit-lock ──────────────────────────
def test_us_ten_011_tc1__deactivate_unused_entry(growth_plan, identity_seam, audit_rows):
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        audit_rows.clear()
        result = services.set_lookup_entry_active(
            admin_actor(), "uoms", _uom_id(tenant, "therm"), False
        )
    assert result["active"] is False
    assert "settings.lookup.deactivated" in audit_actions(audit_rows)


def test_us_ten_011_tc2__delete_unused_entry_audits_the_values(
    growth_plan, identity_seam, audit_rows
):
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        temp = services.create_lookup_entry(
            admin_actor(), "uoms", {"code": "TEMP", "name": "Temporary"}
        )
        audit_rows.clear()
        services.delete_lookup_entry(admin_actor(), "uoms", temp["id"])
        assert models.Uom.objects.filter(tenant=tenant, code="TEMP").count() == 0
    deleted = [r for r in audit_rows if r["action"] == "settings.lookup.deleted"]
    assert deleted[0]["before"]["code"] == "TEMP"  # deleted values recorded


def test_us_ten_011_tc3__deactivate_allowed_even_while_used(growth_plan, identity_seam):
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        kgal_id = _uom_id(tenant, "kgal")  # used by water tenant_services row
        result = services.set_lookup_entry_active(admin_actor(), "uoms", kgal_id, False)
        assert result["active"] is False and result["used_by"] >= 1
        # existing assignment keeps rendering (row untouched)
        assert selectors.service_row("water")["primary_uom"] == "kgal"
        # reactivation allowed at any time (BR-TEN-029)
        assert (
            services.set_lookup_entry_active(admin_actor(), "uoms", kgal_id, True)["active"] is True
        )


def test_us_ten_011_tc4__locked_delete_409_via_service_and_api(growth_plan, identity_seam):
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        kgal_id = _uom_id(tenant, "kgal")
        with pytest.raises(errors.BizError) as excinfo:
            services.delete_lookup_entry(admin_actor(), "uoms", kgal_id)
    assert excinfo.value.code == errors.BIZ_LOCKED  # 409, BR-TEN-034
    assert excinfo.value.br_ref == "BR-TEN-034"
    assert excinfo.value.params["used_by"] >= 1
    response = api_call(
        api.lookup_entry,
        "delete",
        user=FakeUser(),
        role="system_admin",
        tenant=tenant,
        list_code="uoms",
        entry_id=str(kgal_id),
    )
    assert response.status_code == 409  # identical server enforcement via API
    assert response.data["br_ref"] == "BR-TEN-034"
    assert response.data["params"]["used_by"] >= 1


def test_us_ten_011_tc5__delete_recomputes_used_by_at_commit_time(growth_plan, identity_seam):
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        recon = services.create_lookup_entry(
            admin_actor(), "uoms", {"code": "RECONU", "name": "Racing unit"}
        )
        # another admin attaches it between page-render (used_by 0) and delete
        services.update_tenant_service(
            admin_actor(), "water", {"primary_uom": "kgal", "alt_uom": "RECONU"}
        )
        with pytest.raises(errors.BizError) as excinfo:
            services.delete_lookup_entry(admin_actor(), "uoms", recon["id"])
    assert excinfo.value.params["used_by"] == 1  # fresh count wins — no orphan ref


def test_us_ten_011_tc6__lock_state_and_counts_are_per_tenant(growth_plan, identity_seam):
    brazos, _ = provisioned_tenant()
    lonestar, _ = provisioned_tenant(lonestarridge_payload(load_defaults=False))
    with tenant_ctx(brazos):
        services.set_lookup_entry_active(admin_actor(), "uoms", _uom_id(brazos, "kgal"), False)
    with tenant_ctx(lonestar):
        own = services.create_lookup_entry(
            admin_actor(), "uoms", {"code": "kgal", "name": "Kilogallons"}
        )
        assert own["active"] is True  # Lone Star Ridge's kgal unaffected


# ── API list read: pagination + ETag (11b G5/G6) ────────────────────────────
def test_us_ten_010_api__list_get_paginated_with_etag_304(growth_plan, identity_seam):
    tenant, _ = provisioned_tenant()
    response = api_call(
        api.lookups,
        "get",
        user=FakeUser(),
        role="system_admin",
        tenant=tenant,
        list_code="uoms",
    )
    assert response.status_code == 200
    assert response.data["count"] == SEEDED_UOM_COUNT  # DRF pagination envelope (CR-010 10.2)
    assert [r["code"] for r in response.data["results"]][:2] == ["Dth", "EDU"]  # Code A→Z, ASCII order — uppercase sorts first (CR-010 10.2)
    tag = response["ETag"]
    cached = api_call(
        api.lookups,
        "get",
        user=FakeUser(),
        role="system_admin",
        tenant=tenant,
        headers={"If-None-Match": tag},
        list_code="uoms",
    )
    assert cached.status_code == 304


# ── the two Reference-data lists tenancy HOSTS (gap lane 2026-08-09) ────────
# `reason_codes` (content owner billing) and `payment_methods` (content owner
# payments) were declared in LOOKUP_LISTS from W0 and seeded in the W0 fixture,
# but no module had a table or a handler, so both cards 404'd and their fixture
# rows were skipped at every provisioning. Tenancy now HOSTS both tables and
# registers both handlers — hosting ≠ owning (see the model docstrings).
@pytest.mark.parametrize(
    "list_code,seeded,sample",
    # payment_methods: 8 since `tap_pay` (DEF-TEN-9020, PO 2026-09-23).
    [
        ("reason_codes", 5, "LEAK"),
        ("payment_methods", 8, "money_order"),
        ("payment_methods", 8, "tap_pay"),
    ],
)
def test_us_ten_009_tc1__hosted_lists_render_their_seeded_cards(
    growth_plan, identity_seam, list_code, seeded, sample
):
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        rows = selectors.lookup_page(list_code, None)
        cards = {card["list"]: card for card in selectors.lookup_cards()}
    assert cards[list_code]["count"] == seeded
    codes = [row["code"] for row in rows]
    assert sample in codes
    assert codes == sorted(codes)  # Code A→Z (IS-2)
    assert all(row["is_system"] and row["active"] for row in rows)
    assert all(row["used_by"] == 0 for row in rows)  # owner lanes unwired — honest 0


@pytest.mark.parametrize(
    "list_code,new_code,new_name",
    [
        ("reason_codes", "RECONDIFF", "Reconcile difference"),
        ("payment_methods", "in_person", "In person"),
    ],
)
def test_us_ten_010_tc1__hosted_list_add_creates_a_tenant_row_with_audit(
    growth_plan, identity_seam, audit_rows, list_code, new_code, new_name
):
    tenant, _ = provisioned_tenant()
    audit_rows.clear()
    with tenant_ctx(tenant):
        created = services.create_lookup_entry(
            admin_actor(), list_code, {"code": new_code, "name": new_name}
        )
        cards = {card["list"]: card for card in selectors.lookup_cards()}
    assert created["code"] == new_code
    assert created["is_system"] is False and created["active"] is True  # BR-TEN-036
    # 8 seeded payment methods since `tap_pay` (DEF-TEN-9020).
    assert cards[list_code]["count"] == (5 if list_code == "reason_codes" else 8) + 1
    assert audit_actions(audit_rows).count("settings.lookup.created") == 1  # BR-TEN-016


@pytest.mark.parametrize(
    "list_code,shouting",
    [("reason_codes", "leak"), ("payment_methods", "ACH")],
)
def test_us_ten_010_tc4__hosted_list_duplicate_codes_refused_case_insensitively(
    growth_plan, identity_seam, list_code, shouting
):
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        with pytest.raises(errors.ValidationError) as excinfo:
            services.create_lookup_entry(
                admin_actor(), list_code, {"code": shouting, "name": "Same code, new casing"}
            )
    field_error = excinfo.value.field_errors[0]
    assert field_error["field"] == "code"  # BR-TEN-030
    assert field_error["params"]["existing"].lower() == shouting.lower()  # names the entry


@pytest.mark.parametrize(
    "list_code,model", [("reason_codes", "ReasonCode"), ("payment_methods", "PaymentMethod")]
)
def test_us_ten_011_tc4__hosted_list_seeded_row_is_never_deletable(
    growth_plan, identity_seam, list_code, model
):
    """BR-TEN-036: a SEEDED row is part of the shared vocabulary — deactivate
    it, never delete it, even at used_by 0 (apps/assets makes the same call for
    its catalogs). A tenant's OWN row still deletes while unused."""
    tenant, _ = provisioned_tenant()
    seeded_id = getattr(models, model).objects.filter(tenant=tenant, is_system=True).first().pk
    with tenant_ctx(tenant):
        with pytest.raises(errors.BizError) as excinfo:
            services.delete_lookup_entry(admin_actor(), list_code, seeded_id)
        # deactivation of the same row is always allowed (BR-TEN-029)
        deactivated = services.set_lookup_entry_active(admin_actor(), list_code, seeded_id, False)
        own = services.create_lookup_entry(
            admin_actor(), list_code, {"code": "TENANTOWN", "name": "Tenant's own"}
        )
        services.delete_lookup_entry(admin_actor(), list_code, own["id"])
    assert excinfo.value.code == "BIZ-LOCKED" and excinfo.value.br_ref == "BR-TEN-036"
    assert deactivated["active"] is False
    assert not getattr(models, model).objects.filter(tenant=tenant, code="TENANTOWN").exists()


def test_us_ten_011_tc6__hosted_list_rows_are_per_tenant(growth_plan, identity_seam):
    brazos, _ = provisioned_tenant()
    lonestar, _ = provisioned_tenant(lonestarridge_payload(load_defaults=False))
    with tenant_ctx(brazos):
        services.create_lookup_entry(
            admin_actor(), "reason_codes", {"code": "TAMPERADJ", "name": "Tamper adjustment"}
        )
    with tenant_ctx(lonestar):
        # toggle was OFF at signup (BR-TEN-012) — nothing seeded, nothing leaked
        assert selectors.lookup_page("reason_codes", None) == []
        assert selectors.lookup_page("payment_methods", None) == []
    # (RLS FORCE half of this TC = G5 isolation suite on live Postgres)


def test_us_ten_010_api__hosted_list_add_and_list_through_the_endpoint(growth_plan, identity_seam):
    tenant, _ = provisioned_tenant()
    created = api_call(
        api.lookups,
        "post",
        user=FakeUser(),
        role="system_admin",
        tenant=tenant,
        data={"code": "ESCHEAT", "name": "Escheatment write-off"},
        list_code="reason_codes",
    )
    assert created.status_code == 201 and created.data["code"] == "ESCHEAT"
    listed = api_call(
        api.lookups,
        "get",
        user=FakeUser(),
        role="system_admin",
        tenant=tenant,
        list_code="payment_methods",
    )
    assert listed.status_code == 200 and listed.data["count"] == 8  # tap_pay, DEF-TEN-9020


# ── the one-line registry gap: `read_methods` (BR-AST-043) ──────────────────
def test_us_ten_009_tc1__read_methods_resolves_through_tenancys_registry(growth_plan):
    """apps/assets has registered a ReadMethod handler since BR-AST-043 landed,
    but tenancy's LOOKUP_LISTS had no `read_methods` entry, so registration
    logged a skip-until-wired warning at every startup and the card could never
    render. The entry mirrors its twin `meter_types` (owner "metering")."""
    definition = services.LOOKUP_LISTS["read_methods"]
    assert definition.owner == services.LOOKUP_LISTS["meter_types"].owner == "metering"
    assert definition.handler is not None  # registered by apps.assets.lookups.register()
    assert services.lookup_handler("read_methods") is definition.handler
    assert type(definition.handler).__name__ == "ReadMethodLookupHandler"
