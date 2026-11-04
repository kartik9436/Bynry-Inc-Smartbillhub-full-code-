# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-MET-8362 — on a premises holding more than 200 assets, a unit's
#           Assets tab drew '—' for service, size and status, because the tab
#           read the PREMISES' registry capped at per=200 and filtered it in the
#           browser by `assigned_unit_id`.
# Rules:    NFR-3 (universal server pagination) · NFR-5 (no hard caps) ·
#           BR-AST-041 (the registry's capability row) · BR-SHL-011 (`f.‹name›`)
# Journey:  08-qa/01-e2e/journeys/J71-asset-upload-carts-and-fire-lines-to-the-bill.md
# ───────────────────────────────────────────────────────
"""`GET /assets?f.unit_id=` — the unit's own assets, asked of the server.

**WHY THE POPULATION IS 205 AND NOT 5.** The defect was invisible to every
fixture in this repo because every fixture holds a handful of assets per
premises, so page 1 of the premises always held them all. The case below
builds the shape the browser walk built — a premises with more than 200 assets,
where the unit under test holds asset numbers that sort AFTER the first 200 —
and asks for that unit's rows. Before the fix `f.unit_id` was not in
`ASSET_FILTERS`, `parse_list_params` dropped it (unknown params are ignored,
never an error), and the answer was the first page of the WHOLE registry.
"""

import datetime
import uuid

import pytest

from apps.assets import api as assets_api
from apps.assets import models, selectors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import (
    FakeUser,
    api_call,
    make_asset,
    make_premises,
    make_unit,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

CROWD = 203


def _crowd(template_id, unit_id, count, prefix):
    """`count` copies of one asset, each seated on `unit_id` — the bulk-upload
    shape, built in two statements rather than `count` service calls."""
    template = models.Asset.objects.get(pk=template_id)
    clones = []
    for i in range(count):
        clone = models.Asset.objects.get(pk=template_id)
        clone.pk = uuid.uuid4()
        clone.asset_no = f"{prefix}-{i:05d}"
        clone.serial_no = None
        clones.append(clone)
    models.Asset.objects.bulk_create(clones)
    models.AssetAssignment.objects.bulk_create(
        [
            models.AssetAssignment(
                tenant_id=template.tenant_id,
                asset_id=clone.pk,
                unit_id=unit_id,
                from_date=datetime.date(2026, 9, 1),
            )
            for clone in clones
        ]
    )


def _premises_past_the_old_page(actor):
    premise = make_premises(actor, address_line="1408 Elm St")
    unit_a = make_unit(actor, premise["id"], label="Bulk A", services=["electric", "water"])
    unit_b = make_unit(actor, premise["id"], label="Unit B", services=["electric", "water"])
    # Unit A's crowd sorts FIRST ("A-…"), so a premises page of 200 is all Unit A.
    seed = make_asset(actor, asset_no="A-SEED", service="water", unit="kgal", unit_id=unit_a["id"], install_date="2026-09-01")
    _crowd(seed["id"], unit_a["id"], CROWD, "A")
    # Unit B's two sort LAST ("Z-…") — exactly where the walk found its dashes.
    make_asset(actor, asset_no="Z-00001", service="water", unit="kgal", unit_id=unit_b["id"], install_date="2026-09-01")
    make_asset(actor, asset_no="Z-00002", service="electric", unit="kWh", unit_id=unit_b["id"], install_date="2026-09-01")
    return premise, unit_a, unit_b


def test_the_selector_narrows_to_one_unit(brazos, dana):
    with tenant_ctx(brazos):
        premise, _unit_a, unit_b = _premises_past_the_old_page(dana)
        on_premises = selectors.asset_list(filters={"premises_id": premise["id"]}).count()
        on_b = [a.asset_no for a in selectors.asset_list(filters={"unit_id": unit_b["id"]})]
    assert on_premises > 200, "the fixture must reproduce the >200 premises"
    assert on_b == ["Z-00001", "Z-00002"]


def test_the_endpoint_answers_the_units_assets_with_their_registry_fields(brazos, dana):
    """The browser walk's reproduction, at the API: Unit B's rows come back with
    service, size and status filled — the three columns that drew '—'."""
    with tenant_ctx(brazos):
        _premise, _unit_a, unit_b = _premises_past_the_old_page(dana)
        response = api_call(
            assets_api.assets,
            "get",
            user=FakeUser(),
            role="system_admin",
            tenant=brazos,
            query={"f.unit_id": unit_b["id"], "f.status": "all", "per": "50"},
        )
    assert response.status_code == 200
    results = response.data["results"]
    assert response.data["count"] == 2
    assert [row["asset_no"] for row in results] == ["Z-00001", "Z-00002"]
    for row in results:
        assert row["assigned_unit_id"] == unit_b["id"]
        assert row["service"] in ("water", "electric")
        assert row["size_class"]
        assert row["status"]


def test_the_unit_filter_is_paged_by_the_server(brazos, dana):
    """NFR-3: the unit's own list is a page with an honest count, not a cap."""
    with tenant_ctx(brazos):
        _premise, unit_a, _unit_b = _premises_past_the_old_page(dana)
        response = api_call(
            assets_api.assets,
            "get",
            user=FakeUser(),
            role="system_admin",
            tenant=brazos,
            query={"f.unit_id": unit_a["id"], "per": "50", "page": "5"},
        )
    assert response.status_code == 200
    # 204 on the unit: four pages of 50 and a fifth of four — the unit's own
    # list is not capped anywhere, including at the old 200.
    assert response.data["count"] == CROWD + 1
    assert [row["asset_no"] for row in response.data["results"]] == [
        "A-00200",
        "A-00201",
        "A-00202",
        "A-SEED",
    ]
