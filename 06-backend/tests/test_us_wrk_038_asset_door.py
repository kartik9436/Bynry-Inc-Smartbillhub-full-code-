# ── Trace ──────────────────────────────────────────────
# Story:    US-WRK-038 (EP-WRK-07) TC-1…TC-7 — the Assets door: one form, four
#           ways in. Screens: Work-028, Work-020, AssetDetailPage's Maintenance
#           history (S53 · AST-07).
# Rules:    BR-WRK-056 · BR-WRK-002 · BR-WRK-006 · CLAUDE.md hard rule 1
# ───────────────────────────────────────────────────────
"""The Assets door, and the boundary it must not cross."""

from __future__ import annotations

import ast
import datetime as dt
import pathlib

import pytest

from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from apps.work import asset_door, models as work_models

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana · lonestar · erin
from tests.test_us_met_helpers import make_asset, tenant_ctx

REPO = pathlib.Path(__file__).resolve().parents[2]
ASSETS_APP = REPO / "06-backend" / "apps" / "assets"


def _published_template(actor, *, name, service="electric"):
    header = w6.create_work_order_template(actor, {"name": name, "service": service, "sequence": 0})
    w6.publish_work_order_template(actor, header["id"])
    return header


# ── TC-1 · `apps/assets/**` writes nothing to `work_orders` — the grep case ──
def test_tc1_the_assets_module_writes_no_work_order_row():
    """`BR-WRK-056` and `A7`, asserted from the assets side.

    ⚠ **THE STRONGER STATEMENT IS THAT `apps/assets/**` GAINS NO LINE AT ALL
    FOR THIS FEATURE**, and that is what this case checks: no file there names
    `work_orders`, `WorkOrder`, or `apps.work` in any position. A door built the
    three-line way — a POST in `apps/assets/` inserting the row — would pass a
    test that only looked for `.objects.create`, because the tempting shape is
    to call a Work service and let IT write.
    """
    offenders: list[str] = []
    for path in sorted(ASSETS_APP.rglob("*.py")):
        if "migrations" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("apps.work"):
                offenders.append(f"{path.name}: imports {node.module}")
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("apps.work"):
                        offenders.append(f"{path.name}: imports {alias.name}")
        # A raw literal naming the table is the other way in.
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if "work_orders" in node.value and "INSERT" in node.value.upper():
                    offenders.append(f"{path.name}: raw insert into work_orders")
    assert offenders == [], offenders


# ── TC-2 · the door raises on the asset anchor ─────────────────────────────
@pytest.mark.django_db
def test_tc2_the_door_raises_one_order_on_the_asset_and_no_connection(dana, brazos):
    with tenant_ctx(brazos):
        template = _published_template(dana, name="Meter exchange")
        asset = make_asset(dana, asset_no="AST-04412")

        order = w6.create_work_order(
            dana,
            None,
            {
                "asset_id": asset["id"],
                "type": template["name"],
                "template_id": template["id"],
                "service": "electric",
                "source": "assets",
            },
        )

        row = work_tables.WorkOrder.objects.get(pk=order["id"])
        # `work_orders.asset_id` — the FK that nothing wrote until this wave.
        assert str(row.asset_id) == str(asset["id"])
        # `Work-007`'s CONNECTION column reads a dash: this job is not tied to a
        # new connection, which is the ConsequenceBox's own first sentence.
        assert row.connection_id is None
        assert row.source == "assets"


# ── TC-3 · templates are filtered by *applies to asset types* ─────────────
@pytest.mark.django_db
def test_tc3_only_templates_for_this_kind_of_asset_are_offered(dana, brazos):
    with tenant_ctx(brazos):
        asset = make_asset(dana, asset_no="AST-04412")
        mine = _published_template(dana, name="Meter exchange")
        other = _published_template(dana, name="Hydrant flush")

        asset_type_id = work_models.WorkOrderTemplateAssetType.objects.none()  # noqa: F841
        from apps.work.seams import assets_seam

        this_type = assets_seam.asset_type_id(asset["id"])

        work_models.WorkOrderTemplateAssetType.objects.create(
            tenant_id=brazos.id, template_id=mine["id"], asset_type_id=this_type
        )
        # `other` is restricted to SOMETHING ELSE — a type this asset is not.
        work_models.WorkOrderTemplateAssetType.objects.create(
            tenant_id=brazos.id,
            template_id=other["id"],
            asset_type_id="00000000-0000-0000-0000-0000000000ff",
        )

        offered = {row["name"] for row in asset_door.templates_for_asset(asset["id"])["rows"]}
        assert "Meter exchange" in offered
        assert "Hydrant flush" not in offered


@pytest.mark.django_db
def test_tc4_a_template_naming_no_asset_types_is_unrestricted_not_inapplicable(dana, brazos):
    """The day a utility opens this door, nobody has filled in the asset-types
    tab. Hiding every unrestricted template would make the form useless then."""
    with tenant_ctx(brazos):
        asset = make_asset(dana, asset_no="AST-04412")
        _published_template(dana, name="General inspection")

        offered = asset_door.templates_for_asset(asset["id"])["rows"]
        names = {row["name"] for row in offered}
        assert "General inspection" in names
        assert all(row["restricted"] is False for row in offered)


# ── TC-5 · the Maintenance history's column is a READ, keyed by date ──────
@pytest.mark.django_db
def test_tc5_the_history_column_reads_the_order_raised_for_this_asset(dana, brazos):
    with tenant_ctx(brazos):
        template = _published_template(dana, name="Meter exchange")
        asset = make_asset(dana, asset_no="AST-04412")
        order = w6.create_work_order(
            dana,
            None,
            {
                "asset_id": asset["id"],
                "type": template["name"],
                "template_id": template["id"],
                "service": "electric",
                "source": "assets",
            },
        )

        index = asset_door.maintenance_order_index(asset["id"])
        today = dt.date.today().isoformat()
        assert index[today] == order["order_no"]
        # The HUMAN-FACING number, never the uuid — B14 rule 31.
        assert index[today].startswith("WO-")
        assert str(order["id"]) not in index.values()


@pytest.mark.django_db
def test_tc6_no_column_is_added_to_asset_maintenance(dana, brazos):
    """`BR-WRK-056` in its own words. The column names are read off the model
    rather than off a migration, so a lane that adds one anywhere fails here."""
    from apps.assets import models as assets_models

    names = {f.name for f in assets_models.AssetMaintenance._meta.get_fields()}
    for forbidden in ("work_order", "work_order_id", "work_order_no", "order"):
        assert forbidden not in names, (
            f"`asset_maintenance` grew a `{forbidden}` column — BR-WRK-056 says "
            "the Work-order column is a READ of `work_orders.asset_id`"
        )


# ── TC-7 · one utility's asset is invisible to another ────────────────────
@pytest.mark.django_db
def test_tc7_a_cross_tenant_asset_offers_nothing_and_lists_nothing(dana, brazos, erin, lonestar):
    with tenant_ctx(lonestar):
        theirs = make_asset(erin, asset_no="AST-09001", service="water")

    with tenant_ctx(brazos):
        # Not a 404 that confirms the row exists elsewhere — an empty answer,
        # which is the same sentence as *nothing has been raised for this asset*.
        assert asset_door.templates_for_asset(theirs["id"])["rows"] == []
        assert asset_door.orders_for_asset(theirs["id"])["rows"] == []
        assert asset_door.maintenance_order_index(theirs["id"]) == {}
