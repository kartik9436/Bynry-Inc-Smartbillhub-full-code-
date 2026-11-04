# ── Trace ──────────────────────────────────────────────
# Change:  CR-089 wave C task C5 (PUJ-15) · DEF-AST-4690
# Rules:   BR-AST-004 (every asset sits on exactly one category tab) ·
#          BR-AST-042 (the type vocabulary, tenant-extensible) ·
#          BR-TEN-012 (a tenant-touched row is never overwritten) ·
#          BR-TEN-036 (a seeded row is deactivatable, never deletable) ·
#          BR-TEN-071 (reference seeding is insert-if-absent BY CODE) ·
#          BR-RAT-024 / CR-063 (fire is the eleventh utility service)
# Tests:   this file
# Impacts: apps/assets/migrations/0013_def_ast_4690_fire_line_type ·
#          apps/assets/services.SEED_ASSET_TYPES
# ───────────────────────────────────────────────────────
"""The fire service line, on the tenants that already existed.

`CR-063` appended `fire_line` to `SEED_ASSET_TYPES` as the thirteenth type. **A
fixture reaches new tenants only**, and `ensure_reference_catalogs()` — which is
insert-if-absent by code and WOULD heal this — runs lazily off whatever request
happens to touch it. So on 2026-09-09 the development estate held three
different catalogues from one fixture: seven tenants with the row, one that
acquired it on 2026-09-08 as a side effect of unrelated traffic, and two
(`oak-ridge`, `silver-creek-water2`) with nine behind-the-meter types and no way
to tag a fire line at all.

RED-FIRST PROOF (r11 step 2d), run through pytest with the migration's own
`get_or_create` short-circuited to `(None, False)` — the whole file green with
it restored, and this one test red without it:

    FAILED tests/test_def_ast_4690_fire_line_type.py::
           test_the_migration_gives_the_row_to_a_tenant_that_lacks_it
    1 failed, 7 deselected, 4 warnings in 208.72s

The assertion that fires is `assert row is not None, "the tenant still cannot
tag a fire line"`. ⚠ **The `-q` run above prints only the summary line, so the
message itself is quoted from the source and not from the transcript** — said
plainly rather than pasted as though it had been observed.
"""

import importlib
from types import SimpleNamespace

import pytest
from django.apps import apps as app_registry
from django.db import connection

from apps.assets import models as assets_models
from apps.assets import services as assets_services

from tests.test_us_ten_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import provisioned_tenant, tenant_ctx

pytestmark = pytest.mark.django_db

MIGRATION = importlib.import_module("apps.assets.migrations.0013_def_ast_4690_fire_line_type")

#: The three families and their ratified sizes — `2 · 1 · 10`, thirteen in all.
#: Written as the SPLIT rather than as a total, because "thirteen types" and
#: "the right thirteen" are different facts and only one of them is the rule.
FAMILY_SIZES = {"meters": 2, "sub_meters": 1, "behind_the_meter": 10}


def _types(tenant):
    with tenant_ctx(tenant):
        return list(assets_models.AssetType.objects.filter(tenant_id=tenant.id))


def _fire(tenant):
    with tenant_ctx(tenant):
        return assets_models.AssetType.objects.filter(
            tenant_id=tenant.id, code=MIGRATION.FIRE_CODE
        ).first()


def _run_forward():
    MIGRATION.add_fire_line_type(app_registry, SimpleNamespace(connection=connection))


def test_a_new_tenant_gets_thirteen_types_in_three_families():
    """The fixture half, asserted as the SPLIT the product's three registry tabs
    are partitioned by (BR-AST-004)."""
    tenant, _ = provisioned_tenant()
    rows = _types(tenant)
    sizes = {family: 0 for family in FAMILY_SIZES}
    for row in rows:
        sizes[row.category] = sizes.get(row.category, 0) + 1
    assert sizes == FAMILY_SIZES
    assert _fire(tenant) is not None


def test_the_seeded_fire_row_is_behind_the_meter_and_named_for_a_clerk():
    """`fire_line` is BTM and not a meter: `CR-063` says fire is *"Capacity
    based - this will behave exactly like trash"*, and a trash cart is not
    read. If this ever moved to `meters` the Assets tab would promise a reading
    that never comes."""
    seeded = {code: (name, category) for code, name, category in assets_services.SEED_ASSET_TYPES}
    assert seeded[MIGRATION.FIRE_CODE] == (MIGRATION.FIRE_NAME, MIGRATION.FIRE_CATEGORY)
    assert MIGRATION.FIRE_CATEGORY == "behind_the_meter"


# ══════════════════════════════════════════════════════════════════════════
# The tenants that already exist — the half a fixture bump cannot reach
# ══════════════════════════════════════════════════════════════════════════
#
# The migration's OWN function is called below and never re-implemented: a test
# that inserts the row itself and then asserts the row is there is a test of
# nothing (law 7's *"what would make this check pass wrongly"*).


def test_the_migration_gives_the_row_to_a_tenant_that_lacks_it():
    """⚠ **THE CASE THE WHOLE DEFECT TURNS ON.** `oak-ridge` and
    `silver-creek-water2`, put back exactly where they are today."""
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        assets_models.AssetType.objects.filter(
            tenant_id=tenant.id, code=MIGRATION.FIRE_CODE
        ).delete()
    assert _fire(tenant) is None, "the fixture for this case is wrong"

    _run_forward()

    row = _fire(tenant)
    assert row is not None, "the tenant still cannot tag a fire line"
    assert row.name == MIGRATION.FIRE_NAME
    assert row.category == "behind_the_meter"
    assert row.is_system is True
    assert row.active is True


def test_it_runs_twice_without_making_a_second_row():
    """BR-TEN-071 is insert-if-absent, and a `migrate` is re-run on every
    deploy that has ever been rolled back and forward."""
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        assets_models.AssetType.objects.filter(
            tenant_id=tenant.id, code=MIGRATION.FIRE_CODE
        ).delete()
    _run_forward()
    _run_forward()
    with tenant_ctx(tenant):
        assert (
            assets_models.AssetType.objects.filter(
                tenant_id=tenant.id, code=MIGRATION.FIRE_CODE
            ).count()
            == 1
        )


def test_it_leaves_a_row_the_tenant_has_renamed_alone():
    """BR-TEN-012. A utility that calls it *Fire main* keeps that word — the
    migration only ever CREATES, so a row that exists is never touched."""
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        assets_models.AssetType.objects.filter(
            tenant_id=tenant.id, code=MIGRATION.FIRE_CODE
        ).update(name="Fire main", is_system=False)

    _run_forward()

    row = _fire(tenant)
    assert row.name == "Fire main"
    assert row.is_system is False


def test_it_leaves_a_row_the_tenant_has_deactivated_deactivated():
    """BR-TEN-036 — a seeded row is DEACTIVATABLE, never deletable. A utility
    that does not sell fire and has switched the type off must not find it back
    in their picker after a deploy."""
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        assets_models.AssetType.objects.filter(
            tenant_id=tenant.id, code=MIGRATION.FIRE_CODE
        ).update(active=False)

    _run_forward()

    assert _fire(tenant).active is False


def test_the_reverse_refuses_where_a_fire_line_is_already_tagged():
    """A rollback does not take a utility's own assets' parent with it. The
    type is `PROTECT`ed by `assets.type`, so a delete would raise; it declines
    per tenant instead and says so in the log."""
    tenant, owner = provisioned_tenant()
    with tenant_ctx(tenant):
        fire = assets_models.AssetType.objects.get(tenant_id=tenant.id, code=MIGRATION.FIRE_CODE)
        stage = assets_models.AssetLifecycleStage.objects.filter(
            tenant_id=tenant.id, code="inventory"
        ).first()
        assets_models.Asset.objects.create(
            tenant_id=tenant.id, asset_no="FS-9001", type=fire, status=stage
        )

    MIGRATION.remove_fire_line_type(app_registry, SimpleNamespace(connection=connection))

    assert _fire(tenant) is not None, "a tagged fire line lost its type on rollback"


def test_the_reverse_removes_an_untouched_unused_row():
    """The other half of the pair: with nothing standing on it, the row this
    migration wrote is the row it takes back."""
    tenant, _ = provisioned_tenant()

    MIGRATION.remove_fire_line_type(app_registry, SimpleNamespace(connection=connection))

    assert _fire(tenant) is None
