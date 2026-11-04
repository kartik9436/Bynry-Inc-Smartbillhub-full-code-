# ── Trace ──────────────────────────────────────────────
# Story:    US-WRK-007 (a work order TYPE catalogue), amended by the Product
#           Owner's ruling of 2026-09-07.  Screen: S8 Reference data / Work-018
# Rules:    BR-WRK-058 (a row with no parent IS a type, a row with a parent IS
#           a sub-type; exactly two levels, enforced in the SERVICE) ·
#           BR-TEN-012 (insert-missing) · BR-TEN-036 (a seeded row is
#           deactivatable, never deletable) · BR-TEN-026 (a service must be one
#           the tenant sells) · CLAUDE.md hard rule 1 (tenant scoping)
# Tests:    this file — the ruling, tested. The PostgreSQL half (the savepoint
#           that hard-won law 14 makes mandatory) is
#           tests/test_cr070_work_order_type_levels_pg.py
# ───────────────────────────────────────────────────────
"""The PO's nine types and forty-two sub-types, and the eight that were there.

WHAT THE RULING SAYS, IN THE TWO SENTENCES THIS FILE EXISTS TO PIN
------------------------------------------------------------------
*"This are the work order types and subtypes"* — nine types and eighteen
sub-types, supplied by the Product Owner on 2026-09-07 — and, of the
twenty-four per-service ones put back to them the same day, *"we are good with
these"* and *"this is also correct"* of the seeding rule:

    a utility that picks water and gas gets the eighteen plus the four gas
    ones; a water-only utility gets exactly the eighteen and nothing else.

**EIGHTEEN AND TWENTY-TWO.** Those two numbers are the ruling, and the two
tests that assert them provision a tenant through `provision_tenant` end to end
rather than calling the seeder — deliberately, and it is the most important
choice in this file. The seeder cannot see an enabled service at the moment
provisioning first calls it (`_seed_reference_data` runs BEFORE
`_enable_signup_services`, because a service points at UoM rows the reference
pass plants), so a test that drove the handler directly would assert eighteen
for every tenant, pass, and prove nothing. The decision log of 2026-09-07
writes that trap down; these two tests are the thing that catches it.
"""

from __future__ import annotations

import pytest

from apps.tenancy import services as tenancy_services
from apps.work import lookups as work_lookups
from apps.work import models as work_models
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar
from tests.test_us_met_helpers import staff_actor, tenant_ctx
from tests.test_us_ten_helpers import brazosbend_payload, provisioned_tenant

pytestmark = pytest.mark.django_db


def _rows(tenant):
    return {row.code: row for row in work_models.WorkOrderType.objects.filter(tenant=tenant)}


def _types(tenant):
    return {c: r for c, r in _rows(tenant).items() if r.parent_id is None}


def _sub_types(tenant):
    return {c: r for c, r in _rows(tenant).items() if r.parent_id is not None}


# ══════════════════════════════════════════════════════════════════════════
# The list itself — the PO's own nine, and their eighteen
# ══════════════════════════════════════════════════════════════════════════
def test_the_nine_types_are_the_product_owners_own_nine(lonestar):
    """Every tenant gets all nine whatever it sells — they are the SPINE."""
    assert {row.name for row in _types(lonestar).values()} == {
        "Consumer Complaint",
        "Meter Maintenance",
        "Preventive Maintenance",
        "Connection",
        "Corrective Maintenance",
        "Infrastructure Development",
        "Water Quality Monitoring",
        "Consumer Services",
        "Reading",
    }


def test_the_eighteen_base_sub_types_hang_under_the_types_the_po_named(lonestar):
    """The PO's own grouping, sub-type by sub-type. A row WITH a parent IS a
    sub-type (`BR-WRK-058`), so every one of these has a `parent_id`.

    Lone Star Ridge sells water, so it has all eighteen: they are WATER's since
    the PO's ruling of 2026-09-07 (*"gas onlyutility carry only gas meters"*).
    A tenant that did not sell water would have none of them, which is what
    `test_a_gas_only_utility_gets_gas_job_types_and_no_water_ones` asserts."""
    rows = _rows(lonestar)
    expected = {
        "Low Pressure": "Consumer Complaint",
        "No Water Supply": "Consumer Complaint",
        "Billing Issues": "Consumer Complaint",
        "Meter Change": "Meter Maintenance",
        "Meter Dispose": "Meter Maintenance",
        "Routine Inspection": "Preventive Maintenance",
        "Meter Replacement": "Preventive Maintenance",
        "Survey for New Connection": "Connection",
        "Residential Connection": "Connection",
        "Commercial Connection": "Connection",
        "Industrial Connection": "Connection",
        "Leak Repairs": "Corrective Maintenance",
        "Electrical Line": "Corrective Maintenance",
        "Main Extension": "Infrastructure Development",
        "Water Pressure": "Water Quality Monitoring",
        "Disconnection/Reconnection": "Consumer Services",
        "Water Truck Services": "Consumer Services",
        "Re-read": "Reading",
    }
    by_name = {row.name: row for row in rows.values()}
    assert set(expected) <= set(by_name), sorted(set(expected) - set(by_name))
    for name, parent_name in expected.items():
        row = by_name[name]
        assert row.parent_id is not None, name
        assert row.parent.name == parent_name, name


def test_nothing_is_three_levels_deep(brazos):
    """`BR-WRK-058` — exactly two. A seeded sub-type's parent is a TYPE."""
    for row in _sub_types(brazos).values():
        assert row.parent.parent_id is None, f"{row.code} is a grandchild"


# ══════════════════════════════════════════════════════════════════════════
# THE RULING — eighteen, and twenty-two
# ══════════════════════════════════════════════════════════════════════════
def test_a_water_only_utility_gets_exactly_the_eighteen_sub_types(lonestar):
    """*"a water-only utility gets exactly the eighteen and nothing else"*.

    Lone Star Ridge is the repo's own water-only tenant. Nine types, eighteen
    sub-types, twenty-seven rows, and nothing from any other service.
    """
    assert len(_types(lonestar)) == 9
    assert len(_sub_types(lonestar)) == 18
    others = {
        str(e["code"]) for e in work_models.SEED_SERVICE_SUB_TYPES
    }
    assert set(_rows(lonestar)) & others == set()


def test_a_gas_only_utility_gets_gas_job_types_and_no_water_ones(
    growth_plan, identity_seam
):
    """**THE 2026-09-07 RULING, AND THE ONLY TEST THAT CAN SEE IT.**

    PO verbatim: *"gas onlyutility carry only gas meters"* — a gas-only utility
    must not receive *No Water Supply* and *Water Truck Services*. Until that
    day the eighteen were unscoped and this tenant would have had all of them;
    the tag on those eighteen rows is the whole change, and this is what proves
    it arrived.

    ⚠ **AND IT ASSERTS THE COST AS WELL AS THE RULING.** A gas-only utility now
    has NO *Billing Issues*, NO *Meter Change*, NO *Re-read* and none of the
    four *Connection* rows, because those live among water's eighteen and
    several of them are not water-specific at all. That is `OQ-WRK-1764`, put
    to the PO with the rows named. The assertion is written the way it is —
    naming the absent rows rather than only counting — so that the day the
    answer lands, this test fails and says which rows it expected.
    """
    tenant, _result = provisioned_tenant(
        brazosbend_payload(
            name="Panhandle Gas Co-op",
            subdomain="panhandlegas",
            services=["gas"],
            owner={
                "full_name": "M. Boateng",
                "email": "m.boateng@panhandlegas.example",
                "password": "An0ther!passw0rd",
                "phone": None,
            },
        )
    )
    # The nine TYPES are the common spine and are never scoped.
    assert len(_types(tenant)) == 9
    # ⚠ **FIFTEEN SINCE THE EVENING OF 2026-09-07 (`DEF-WRK-4512`), AND IT WAS
    # FOUR THAT MORNING.** Gas's own four plus the ELEVEN the PO ruled common to
    # every utility: *"yes that is correct; but we will ahve to see which
    # Utility service they do"*. The first half of that sentence is what this
    # number is; the second half is `OQ-WRK-1764` and is still open.
    assert len(_sub_types(tenant)) == 15
    rows = _rows(tenant)
    assert {"GAS_LEAK_CALLOUT", "GAS_ODOUR", "GAS_PRESSURE_TEST", "GAS_LINE_PURGE"} <= set(rows)
    # The two the PO named by hand are STILL water's and still absent — this is
    # what stops the fix for DEF-WRK-4512 turning into a blanket untagging.
    assert "NO_WATER_SUPPLY" not in rows
    assert "WATER_TRUCK" not in rows
    # …and the service-neutral rows a gas utility does daily are PRESENT. This
    # loop asserted the opposite until 2026-09-07 and is inverted rather than
    # deleted, so the reversal is legible to the next reader.
    for code in ("BILLING_ISSUES", "METER_CHANGE", "RE_READ", "RESIDENTIAL_CONN"):
        assert code in rows, code


def test_a_water_and_gas_utility_gets_twenty_two(growth_plan, identity_seam):
    """*"a utility that picks water and gas gets the eighteen plus the four gas
    ones"*. Eighteen plus four is TWENTY-TWO, and the four are gas's own."""
    tenant, _result = provisioned_tenant(
        brazosbend_payload(
            name="Two Rivers Water & Gas",
            subdomain="tworivers",
            services=["water", "gas"],
            owner={
                "full_name": "R. Alvarez",
                "email": "r.alvarez@tworivers.example",
                "password": "An0ther!passw0rd",
                "phone": None,
            },
        )
    )
    assert len(_types(tenant)) == 9
    assert len(_sub_types(tenant)) == 22
    gas = {
        "GAS_LEAK_CALLOUT": "Consumer Complaint",
        "GAS_ODOUR": "Consumer Complaint",
        "GAS_PRESSURE_TEST": "Corrective Maintenance",
        "GAS_LINE_PURGE": "Corrective Maintenance",
    }
    rows = _rows(tenant)
    for code, parent_name in gas.items():
        assert code in rows, code
        assert rows[code].parent.name == parent_name, code
    # …and nothing from a service it does not sell.
    assert "ELEC_OUTAGE" not in rows
    assert "SEWER_BLOCKAGE" not in rows


def test_an_electric_and_water_utility_gets_the_three_electric_ones(brazos):
    """Brazos Bend sells electric and water: eighteen plus electric's three."""
    assert len(_sub_types(brazos)) == 21
    rows = _rows(brazos)
    assert {"ELEC_OUTAGE", "ELEC_VOLTAGE", "ELEC_TRANSFORMER"} <= set(rows)
    assert "GAS_LEAK_CALLOUT" not in rows


def test_switching_a_service_on_later_delivers_its_sub_types(lonestar, erin):
    """The other half of the ruling, which the PO did not have to state.

    A water-only co-op that adds Gas in March gets the four gas job types the
    signup path would have given it — same seeders, insert-missing, no
    duplicates. Without this a utility's crews could not raise a gas leak
    call-out and nothing anywhere would say why.
    """
    with tenant_ctx(lonestar):
        before = len(_sub_types(lonestar))
        tenancy_services.update_tenant_service(erin, "gas", {"enabled": True})
    assert len(_sub_types(lonestar)) == before + 4
    assert "GAS_LEAK_CALLOUT" in _rows(lonestar)


def test_a_gas_only_utility_that_adds_water_later_gets_the_eighteen(
    growth_plan, identity_seam
):
    """The mirror of the test above, and the one the 2026-09-07 ruling created.

    Before that ruling the eighteen were unscoped, so this path could not go
    wrong: every tenant already had them. Now a gas-only utility has none, and
    the day it adds water it must receive all eighteen — through the SAME
    second pass, because sign-up seeds reference data before it enables any
    service and a first pass therefore sees no service at all.
    """
    tenant, _result = provisioned_tenant(
        brazosbend_payload(
            name="Caprock Gas",
            subdomain="caprockgas",
            services=["gas"],
            owner={
                "full_name": "T. Nakamura",
                "email": "t.nakamura@caprockgas.example",
                "password": "An0ther!passw0rd",
                "phone": None,
            },
        )
    )
    assert len(_sub_types(tenant)) == 15  # gas's four + the eleven common ones
    actor = staff_actor(tenant, "system_admin", "t.nakamura@caprockgas.test")
    with tenant_ctx(tenant):
        tenancy_services.update_tenant_service(actor, "water", {"enabled": True})
    # Still 22, and the composition changed underneath it: 11 common + gas's 4
    # + water's 7, where it used to be gas's 4 + water's 18.
    assert len(_sub_types(tenant)) == 22
    rows = _rows(tenant)
    assert "NO_WATER_SUPPLY" in rows
    assert "RE_READ" in rows


def test_seeding_twice_creates_nothing_the_second_time(lonestar):
    """`BR-TEN-012` — insert-missing. A replay writes nothing."""
    handler = work_lookups.WorkOrderTypeLookupHandler()
    with tenant_ctx(lonestar):
        before = handler.count()
        created = handler.seed(lonestar.id, [dict(e) for e in work_models.SEED_TYPES])
        assert created == 0
        assert handler.count() == before


# ══════════════════════════════════════════════════════════════════════════
# The eight that were there before
# ══════════════════════════════════════════════════════════════════════════
def test_a_freshly_provisioned_tenant_carries_none_of_the_retired_eight(brazos):
    """They are gone from the SEED. A tenant created today never sees them."""
    rows = _rows(brazos)
    for code, _name in work_models.RETIRED_SEED_TYPES:
        assert code not in rows, code


def test_the_migration_deactivates_the_eight_and_deletes_nothing(brazos):
    """The migration's rule, driven against a tenant that HAS the eight.

    A freshly provisioned tenant no longer carries them, which is exactly why
    this test builds them back: it is asserting what happens on a LIVE tenant
    provisioned BEFORE 2026-09-07, and the assertion is that every row SURVIVES
    — deactivated, still nameable by every work order that points at it.

    The migration's own functions are called (not re-implemented), through
    Django's live app registry. That is the same registry shape
    `apps_registry.get_model` gives a `RunPython`, so the code under test is
    the code that will run on the host.
    """
    from importlib import import_module

    from django.apps import apps as app_registry

    migration = import_module("apps.work.migrations.0023_br_wrk_058_retire_and_seed")

    with tenant_ctx(brazos):
        for code, name in work_models.RETIRED_SEED_TYPES:
            work_models.WorkOrderType.objects.create(
                tenant=brazos, code=code, name=name, is_system=True, active=True
            )
        # One of them RENAMED by its utility — a row somebody has adopted.
        adopted = work_models.WorkOrderType.objects.get(tenant=brazos, code="MAIN_REPAIR")
        adopted.name = "Watermain break"
        adopted.save(update_fields=["name"])

        before = work_models.WorkOrderType.objects.filter(tenant=brazos).count()
        retired = migration._retire_tenant(app_registry, brazos.id)

    assert retired == 7  # the eight, less the one its utility renamed
    rows = _rows(brazos)
    # NOTHING IS DELETED.
    assert work_models.WorkOrderType.objects.filter(tenant=brazos).count() == before
    for code, _name in work_models.RETIRED_SEED_TYPES:
        assert code in rows, code
    assert rows["RECONNECT"].active is False
    assert rows["READ_VERIFICATION"].active is False
    # …and the adopted one is left alone, still on.
    assert rows["MAIN_REPAIR"].name == "Watermain break"
    assert rows["MAIN_REPAIR"].active is True


def test_the_migration_delivers_the_new_list_to_a_tenant_that_predates_it(brazos):
    """The forward half: an existing tenant is brought level with a new one,
    and its own enabled services decide which sub-types it receives."""
    from importlib import import_module

    from django.apps import apps as app_registry

    migration = import_module("apps.work.migrations.0023_br_wrk_058_retire_and_seed")

    with tenant_ctx(brazos):
        # Children first: `parent` is PROTECT, so a blanket delete refuses —
        # which is the FK doing its job and is asserted directly two tests up.
        work_models.WorkOrderType.objects.filter(
            tenant=brazos, parent__isnull=False
        ).delete()
        work_models.WorkOrderType.objects.filter(tenant=brazos).delete()
        created = migration._seed_tenant(app_registry, brazos.id)

    assert created == 9 + 18 + 3  # the nine types, water's eighteen, electric's three
    assert len(_types(brazos)) == 9
    assert len(_sub_types(brazos)) == 21
    assert _rows(brazos)["RE_READ"].parent.code == "READING"
    # A replay writes nothing (BR-TEN-012).
    with tenant_ctx(brazos):
        assert migration._seed_tenant(app_registry, brazos.id) == 0


def test_the_scoping_migration_takes_water_rows_off_a_gas_only_utility(
    growth_plan, identity_seam
):
    """`work/0024` — the correction for a host that migrated between the two
    rulings of 2026-09-07, driven against a tenant in exactly that state.

    A gas-only utility provisioned today never gets water's eighteen, so this
    test puts them there first — which is what `work/0023` did on any host that
    migrated in the two hours before the second ruling landed. The assertion is
    that they come back OFF, that nothing is deleted, and that gas's own four
    are untouched.
    """
    from importlib import import_module

    from django.apps import apps as app_registry

    migration = import_module("apps.work.migrations.0024_br_wrk_058_scope_water_sub_types")

    tenant, _result = provisioned_tenant(
        brazosbend_payload(
            name="Llano Gas Supply",
            subdomain="llanogas",
            services=["gas"],
            owner={
                "full_name": "P. Sandoval",
                "email": "p.sandoval@llanogas.example",
                "password": "An0ther!passw0rd",
                "phone": None,
            },
        )
    )
    water = [e for e in work_models.SEED_BASE_SUB_TYPES if e.get("service") == "water"]
    # SEVEN since 2026-09-07: the eleven service-neutral rows lost their water
    # tag when the PO ruled them common (`DEF-WRK-4512`). What is left is the
    # rows that are genuinely about water.
    assert len(water) == 7
    with tenant_ctx(tenant):
        parents = {r.code: r for r in work_models.WorkOrderType.objects.filter(tenant=tenant)}
        for entry in water:
            work_models.WorkOrderType.objects.create(
                tenant=tenant,
                code=str(entry["code"]),
                name=str(entry["name"]),
                parent=parents[str(entry["parent_code"])],
                is_system=True,
                active=True,
            )
        # One of them RENAMED — a row this utility has made its own.
        # ⚠ **IT WAS `RE_READ` UNTIL 2026-09-07 AND HAD TO MOVE.** That row is
        # now one of the eleven COMMON sub-types, so it carries no water tag,
        # `_retract_tenant` never considers it, and the case would have been
        # testing nothing while still passing. `WATER_PRESSURE` is still
        # water's, so the "a renamed row is left alone" property is exercised.
        adopted = work_models.WorkOrderType.objects.get(tenant=tenant, code="WATER_PRESSURE")
        adopted.name = "Pressure at the tap"
        adopted.save(update_fields=["name"])

        before = work_models.WorkOrderType.objects.filter(tenant=tenant).count()
        retracted = migration._retract_tenant(app_registry, tenant.id)

    assert retracted == 6  # water's SEVEN, less the one it renamed
    rows = _rows(tenant)
    # NOTHING IS DELETED.
    assert work_models.WorkOrderType.objects.filter(tenant=tenant).count() == before
    assert rows["NO_WATER_SUPPLY"].active is False
    assert rows["WATER_TRUCK"].active is False
    # …the adopted one is left alone and stays on…
    assert rows["WATER_PRESSURE"].name == "Pressure at the tap"
    assert rows["WATER_PRESSURE"].active is True
    # …a COMMON row is never retracted at all, whatever this utility sells…
    assert rows["RE_READ"].active is True
    # …and gas's own four are untouched.
    for code in ("GAS_LEAK_CALLOUT", "GAS_ODOUR", "GAS_PRESSURE_TEST", "GAS_LINE_PURGE"):
        assert rows[code].active is True, code
    # A replay changes nothing (BR-TEN-010).
    with tenant_ctx(tenant):
        assert migration._retract_tenant(app_registry, tenant.id) == 0


def test_the_scoping_migration_leaves_a_water_utility_completely_alone(lonestar):
    """The guard that keeps `0024` a correction rather than a new rule: a
    utility that sells water keeps all eighteen, and the function returns
    before touching a single row."""
    from importlib import import_module

    from django.apps import apps as app_registry

    migration = import_module("apps.work.migrations.0024_br_wrk_058_scope_water_sub_types")
    with tenant_ctx(lonestar):
        assert migration._retract_tenant(app_registry, lonestar.id) == 0
    assert len([r for r in _sub_types(lonestar).values() if r.active]) == 18


def test_a_type_with_sub_types_cannot_be_deleted(brazos):
    """The PROTECT FK is the backstop; the refusal is the message."""
    handler = work_lookups.WorkOrderTypeLookupHandler()
    with tenant_ctx(brazos):
        parent = work_models.WorkOrderType.objects.get(tenant=brazos, code="READING")
        with pytest.raises(errors.BizError) as refused:
            handler.delete(parent)
    assert refused.value.message_key == "work.types.delete_blocked_sub_types"
    assert refused.value.params["sub_types"] == 1  # Re-read


# ══════════════════════════════════════════════════════════════════════════
# The depth cap — three refusals, `AreaLookupHandler`'s own three
# ══════════════════════════════════════════════════════════════════════════
def test_a_sub_type_may_not_itself_be_a_parent(brazos):
    """The grandchild refusal. *Re-read* already has a parent, so nothing may
    hang under it — `BR-WRK-058`, and the message names both rows."""
    handler = work_lookups.WorkOrderTypeLookupHandler()
    with tenant_ctx(brazos):
        with pytest.raises(errors.ValidationError) as refused:
            handler.create(
                {"code": "RE_READ_URGENT", "name": "Urgent re-read", "parent_code": "RE_READ"}
            )
    assert refused.value.message_key == "work.types.parent_is_sub_type"
    assert refused.value.params["picked"] == "RE_READ"
    assert refused.value.params["picked_parent"] == "READING"


def test_a_type_cannot_be_its_own_parent(brazos):
    handler = work_lookups.WorkOrderTypeLookupHandler()
    with tenant_ctx(brazos):
        row = handler.create({"code": "SPOT_CHECK", "name": "Spot check"})
        with pytest.raises(errors.ValidationError) as refused:
            handler.update(row, {"parent_code": "SPOT_CHECK"})
    assert refused.value.message_key == "work.types.parent_self"


def test_an_unknown_parent_code_is_refused_by_name(brazos):
    handler = work_lookups.WorkOrderTypeLookupHandler()
    with tenant_ctx(brazos):
        with pytest.raises(errors.ValidationError) as refused:
            handler.create({"code": "X", "name": "X", "parent_code": "NOPE"})
    assert refused.value.message_key == "work.types.parent_unknown"
    assert refused.value.params["picked"] == "NOPE"


def test_a_type_that_already_has_sub_types_cannot_become_one(brazos):
    """The third level arriving from the other direction — the one
    `_resolve_parent` cannot see, because it looks at the PARENT."""
    handler = work_lookups.WorkOrderTypeLookupHandler()
    with tenant_ctx(brazos):
        reading = work_models.WorkOrderType.objects.get(tenant=brazos, code="READING")
        with pytest.raises(errors.ValidationError) as refused:
            handler.update(reading, {"parent_code": "COMPLAINT"})
    assert refused.value.message_key == "work.types.has_sub_types"
    assert refused.value.params["count"] == 1


def test_clearing_a_parent_promotes_a_sub_type_back_to_top_level(brazos):
    """Blank is a real answer, not an omission — the same thing it means on the
    areas card, and the handler reads an ABSENT key as "leave it alone"."""
    handler = work_lookups.WorkOrderTypeLookupHandler()
    with tenant_ctx(brazos):
        row = work_models.WorkOrderType.objects.get(tenant=brazos, code="RE_READ")
        handler.update(row, {"parent_code": ""})
        row.refresh_from_db()
        assert row.parent_id is None
        # …and an update that does not mention the key leaves it where it is.
        handler.update(row, {"name": "Re-read (repeat)"})
        row.refresh_from_db()
        assert row.parent_id is None


# ══════════════════════════════════════════════════════════════════════════
# What the card reads
# ══════════════════════════════════════════════════════════════════════════
def test_the_card_is_told_the_parent_the_level_and_the_count(brazos):
    """The four hierarchical keys the shared Reference-data view reads. The two
    named for AREAS are the SELF-PARENTED wire contract every hierarchical
    handler publishes, not this list's vocabulary — `DEF-TEN-4478` states it in
    the view and the serializer repeats it."""
    handler = work_lookups.WorkOrderTypeLookupHandler()
    with tenant_ctx(brazos):
        reading = handler.serialize(
            work_models.WorkOrderType.objects.get(tenant=brazos, code="READING")
        )
        re_read = handler.serialize(
            work_models.WorkOrderType.objects.get(tenant=brazos, code="RE_READ")
        )
    assert reading["parent_code"] is None
    assert reading["parent_name"] is None
    assert reading["is_sub_area"] is False
    assert reading["sub_area_count"] == 1
    assert re_read["parent_code"] == "READING"
    assert re_read["parent_name"] == "Reading"
    assert re_read["is_sub_area"] is True
    assert re_read["sub_area_count"] == 0


def test_no_database_id_is_ever_the_visible_value(brazos):
    """B14 rule 31 — the card shows `parent_name`, and `parent_id` rides along
    only so an edit can send it back. A screen that drew the id would be
    drawing a uuid at a clerk."""
    handler = work_lookups.WorkOrderTypeLookupHandler()
    with tenant_ctx(brazos):
        row = work_models.WorkOrderType.objects.get(tenant=brazos, code="RE_READ")
        payload = handler.serialize(row)
    assert payload["parent_name"] == "Reading"
    assert payload["parent_id"] == str(row.parent_id)


# ══════════════════════════════════════════════════════════════════════════
# Tenant isolation — CLAUDE.md hard rule 1
# ══════════════════════════════════════════════════════════════════════════
def test_a_sub_type_added_by_one_utility_is_invisible_to_another(brazos, lonestar):
    """The application layer's half; the database's is the `_pg` file."""
    handler = work_lookups.WorkOrderTypeLookupHandler()
    with tenant_ctx(brazos):
        handler.create(
            {"code": "HYDRANT_FLUSH", "name": "Hydrant flush", "parent_code": "PREVENTIVE"}
        )
    with tenant_ctx(lonestar):
        codes = {row.code for row in handler.search(None)}
    assert "HYDRANT_FLUSH" not in codes
    assert "PREVENTIVE" in codes  # its own nine are seeded


def test_a_parent_in_another_tenant_is_indistinguishable_from_an_absent_one(
    brazos, lonestar
):
    """`_resolve_parent` scopes to the tenant in context, so another utility's
    code is *unknown* rather than *forbidden* — the same answer an absent one
    gets, which is what stops the refusal being an existence oracle."""
    handler = work_lookups.WorkOrderTypeLookupHandler()
    with tenant_ctx(brazos):
        handler.create({"code": "BRAZOS_ONLY", "name": "Brazos only"})
    with tenant_ctx(lonestar):
        with pytest.raises(errors.ValidationError) as refused:
            handler.create({"code": "Y", "name": "Y", "parent_code": "BRAZOS_ONLY"})
    assert refused.value.message_key == "work.types.parent_unknown"


# ══════════════════════════════════════════════════════════════════════════
# The two consequences the PO's list carries, stated so nobody re-derives them
# ══════════════════════════════════════════════════════════════════════════
def test_reading_re_read_exists_and_work_writes_no_meter_read(brazos):
    """*Reading → Re-read* means a meter read can raise field work, which is a
    Work↔Meter Reads seam. Work READS reads and writes none of them (`CR-070`
    §2(a)); `G78` fails a foreign write from anywhere under `apps/work/`. This
    asserts the sub-type exists and that the module's read door is the seam."""
    from apps.work.seams import metering_seam

    assert "RE_READ" in _rows(brazos)
    assert hasattr(metering_seam, "meters_in_continuous_flow")


def test_billing_issues_is_a_job_no_crew_has_to_visit(brazos):
    """*Consumer Complaint → Billing Issues* puts a billing complaint in the
    field-work module, deliberately. So a type must be able to exist with NO
    default template, NO estimated duration and NO customer-present flag —
    nothing that assumes somebody drives to an address."""
    row = _rows(brazos)["BILLING_ISSUES"]
    assert row.default_template_id is None
    assert row.est_duration is None
    assert row.customer_present is False
