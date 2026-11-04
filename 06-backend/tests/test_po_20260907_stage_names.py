# ── Trace ──────────────────────────────────────────────
# Change:  PO ruling 2026-09-07 — *"use only Inventory and Installed"*
#          Screens: S8 (Reference data → Asset statuses) · S49 asset list ·
#          the customer portal's asset list, which printed the slash
# Rules:   BR-AST-031 (stages live in Reference data; every stage maps to a
#          system behavior class so filters and billing stay sound whatever the
#          tenant renames a stage to) · BR-TEN-012 (a tenant-touched row is
#          never overwritten) · BR-TEN-071 (seeding is insert-if-absent by
#          code) · BR-TEN-077 (a content change needs a fixture version bump)
# Tests:   this file
# Impacts: apps/tenancy/fixtures/lookup_defaults.json (V2.48.0.10) ·
#          apps/assets/services.SEED_LIFECYCLE_STAGES ·
#          apps/assets/migrations/0011_po_2026_09_07_stage_names
# ───────────────────────────────────────────────────────
"""The two asset statuses that lost their second halves, and the rows already out there.

**PO ruling 2026-09-07, verbatim:** *"use only Inventory and Installed"*.
`Inventory/Spare` → **Inventory**, `Installed/Active` → **Installed**. The other
three are untouched, no code moves, and no row is added or removed.

⚠ **THE HALF THAT NEEDS A TEST IS NOT THE FIXTURE — IT IS THE TENANTS THAT
ALREADY EXIST.** Reference seeding is insert-if-absent by CODE (BR-TEN-071), so
a tenant provisioned yesterday holds `inventory` and every future seed run finds
it present and writes nothing. **A fixture edit alone reaches new tenants only**,
which the decision-log entry for this ruling says in so many words. The migration
is the delivery, and what it must NOT do is overwrite a name a tenant typed
themselves (BR-TEN-012, and BR-AST-031's own *"tenant may rename"*).

RED-FIRST PROOF (r11 step 2d), through pytest, before the fixture and the
constant moved:

    E  AssertionError: assert ['Inventory/S...ed', 'Retired'] == ['Inventory', ...]
       At index 0 diff: 'Inventory/Spare' != 'Inventory'
"""

import pytest

from apps.assets import models as assets_models
from apps.assets import services as assets_services
from apps.tenancy import services as tenancy_services

from tests.test_us_ten_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import provisioned_tenant, tenant_ctx

pytestmark = pytest.mark.django_db

#: The ruled five, in seed order. Named rather than counted — five rows is not
#: the same fact as the right five, and this ruling changed only two words.
RULED_NAMES = ["Inventory", "Installed", "Needs repair", "In repair", "Retired"]
RULED_CODES = ["inventory", "active", "needs_repair", "in_repair", "retired"]

SUPERSEDED = {"inventory": "Inventory/Spare", "active": "Installed/Active"}


def _stages(tenant):
    with tenant_ctx(tenant):
        return list(
            assets_models.AssetLifecycleStage.objects.filter(tenant_id=tenant.id).order_by(
                "created_at"
            )
        )


def test_a_new_tenant_gets_the_short_names():
    """The fixture half. Codes and behavior classes are asserted beside the
    names, because a rename that quietly moved either would be a different and
    much worse change."""
    tenant, _ = provisioned_tenant()
    rows = _stages(tenant)
    assert [row.name for row in rows] == RULED_NAMES
    assert [row.code for row in rows] == RULED_CODES
    by_code = {row.code: row.behavior_class for row in rows}
    assert by_code == {
        "inventory": "available",
        "active": "in_service",
        "needs_repair": "out_of_service",
        "in_repair": "out_of_service",
        "retired": "terminal",
    }


def test_the_ratified_constant_and_the_fixture_agree():
    """`SEED_LIFECYCLE_STAGES` is the fallback the assets seeder uses when the
    fixture list is empty, so the two are two copies of one ruling and drift
    between them is a tenant getting different words depending on which path
    seeded it."""
    fixture = tenancy_services._load_seed_fixture()["asset_statuses"]
    assert [row["name"] for row in fixture] == RULED_NAMES
    assert [name for _code, name, _cls in assets_services.SEED_LIFECYCLE_STAGES] == RULED_NAMES


def test_the_slash_is_gone_from_every_seeded_name():
    """The ruling's own reason, asserted as itself: a slash in a lookup name is
    two words competing to be the label. It also reached a customer's screen."""
    for _code, name, _cls in assets_services.SEED_LIFECYCLE_STAGES:
        assert "/" not in name, name


# ══════════════════════════════════════════════════════════════════════════
# The tenants that already exist — the half a fixture bump cannot reach
# ══════════════════════════════════════════════════════════════════════════


# The migration's OWN functions are called below, never re-implemented: a test
# that renames the rows itself and then asserts they are renamed is a test of
# nothing (law 7's *"what would make this check pass wrongly"*).


def test_the_migration_renames_a_row_a_tenant_still_holds():
    """⚠ **THE CASE THE WHOLE RULING TURNS ON.** A tenant provisioned before
    today holds `Inventory/Spare`; nothing re-seeds a changed name, so without
    this it keeps the slash for ever."""
    import importlib
    from types import SimpleNamespace

    from django.apps import apps as app_registry
    from django.db import connection

    migration = importlib.import_module("apps.assets.migrations.0011_po_2026_09_07_stage_names")

    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        # Put the tenant back where a pre-ruling tenant actually is.
        for code, was in SUPERSEDED.items():
            assets_models.AssetLifecycleStage.objects.filter(
                tenant_id=tenant.id, code=code
            ).update(name=was)

    migration.shorten_stage_names(app_registry, SimpleNamespace(connection=connection))

    rows = {row.code: row.name for row in _stages(tenant)}
    assert rows["inventory"] == "Inventory"
    assert rows["active"] == "Installed"


def test_the_migration_leaves_a_name_the_tenant_typed_alone():
    """BR-TEN-012 + BR-AST-031's *"tenant may rename"*. There is no
    touch-tracking column, so the row's own CONTENT is the only evidence that
    nobody has edited it — and that evidence is used as the whole test rather
    than as a hint."""
    import importlib
    from types import SimpleNamespace

    from django.apps import apps as app_registry
    from django.db import connection

    migration = importlib.import_module("apps.assets.migrations.0011_po_2026_09_07_stage_names")

    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        assets_models.AssetLifecycleStage.objects.filter(
            tenant_id=tenant.id, code="inventory"
        ).update(name="In the yard")
        assets_models.AssetLifecycleStage.objects.filter(tenant_id=tenant.id, code="active").update(
            name="Installed/Active"
        )

    migration.shorten_stage_names(app_registry, SimpleNamespace(connection=connection))

    rows = {row.code: row.name for row in _stages(tenant)}
    assert rows["inventory"] == "In the yard", "a tenant's own word for their own process"
    assert rows["active"] == "Installed", "and the untouched one still moves"


def test_the_migration_is_reversible():
    """A rollback must be able to put the words back, or the change cannot be
    undone on a host that has run it."""
    import importlib
    from types import SimpleNamespace

    from django.apps import apps as app_registry
    from django.db import connection

    migration = importlib.import_module("apps.assets.migrations.0011_po_2026_09_07_stage_names")

    tenant, _ = provisioned_tenant()
    migration.restore_stage_names(app_registry, SimpleNamespace(connection=connection))
    rows = {row.code: row.name for row in _stages(tenant)}
    assert rows["inventory"] == "Inventory/Spare"
    assert rows["active"] == "Installed/Active"


# ── Lifecycle ─────────────────────────────────────────────
# packet: decision log 2026-09-07 (four rulings on the seeded reference lists) +
#         BR-AST-031 + BR-TEN-012/071/077 + CLAUDE.md hard rules 1 and 7 +
#         hard-won law 14 (the per-tenant savepoint in the migration)
# generated: 2026-09-07 by the tenant-provisioning lane
# checklist: A✔ B✔ C✔ D=deferred(no API half — the lookup card already serves
#            this list) E=deferred(no frontend half — the screens print the
#            stored name and print the new one by themselves) F✔ G✔
#            H=deferred(PO 2026-08-09)
# gates: pytest tests/test_po_20260907_stage_names.py
# exceptions: the migration is exercised by calling its own functions against
#             the live app registry rather than through `migrate` — the suite's
#             database is built once per session from all migrations, so a
#             second forward run inside a test is the only way to observe it
#             acting on rows a test can control. The historical-model half
#             (`apps.get_model`) is identical either way for a data-only
#             migration that adds no field · `07-frontend/src/features/assets/
#             AssetLifecycle.test.tsx` still uses the LONG names as its own
#             fixture data; they are arbitrary labels there and assert nothing
#             about the seed, so they are left rather than swept into a lane
#             that is not theirs — REPORTED
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
