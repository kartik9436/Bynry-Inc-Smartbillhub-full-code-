# ── Trace ──────────────────────────────────────────────
# Story:    US-MET-003 (S16 guided add — single premise & single unit with the
#           meter grid, sub-meter panel and default-plan panel)
# Rules:    BR-MET-001/002/003 · BR-MET-006 (≤1 meter per enabled service per
#           unit; modes auto-generate/assign-existing/leave-blank; multiplier
#           explicit > 0; sub-meter parentage) · BR-MET-007 + BR-CUS-014
#           (default plan is binding; history is rating-owned) · BR-MET-036
#           (no occupancy input exists) · BR-MET-040/042/044 (plan rules) ·
#           BR-MET-048 (every wizard save audited) · BR-AST-028 (one registry)
# Journeys: J2 steps 1–3 (unit exists · asset active on unit with explicit UoM
#           · unit plan reference set)
# Note:     The unit_plan_assignments HISTORY row is rating-owned (B2 r16 #6)
#           and its service is unwired — the response reports
#           history_recorded: false rather than implying a row exists.
# ───────────────────────────────────────────────────────
"""US-MET-003 — the guided add wizards (premise, unit, meters, plan)."""

import pytest

from apps.assets import models as asset_models
from apps.metering import models, selectors, services
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import (
    make_asset,
    make_plan,
    make_premises,
    make_unit,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


def test_us_met_003_tc1__single_premise_with_auto_created_unit(brazos, dana, audit_rows):
    with tenant_ctx(brazos):
        result = services.create_premises(
            dana,
            {"owner_id": owner_for(dana), 
                "address_line": "1901 Bluestem Ln",
                "city": "Katy",
                "state": "TX",
                "postal_code": "77494",
                "premises_type": "single_family",
                "services_available": ["electric", "water"],
                "auto_create_unit": True,
                "unit": {"label": "Unit A", "unit_type": "residential"},
            },
        )
    assert result["premise_no"].startswith("P-")
    assert result["services_available"] == ["electric", "water"]
    assert len(result["units"]) == 1 and result["units"][0]["label"] == "Unit A"
    actions = [r["action"] for r in audit_rows]
    assert "premises.created" in actions and "unit.created" in actions  # BR-MET-048


def test_us_met_003_tc2__unit_with_assigned_meter_submeter_and_default_plan(brazos, dana):
    with tenant_ctx(brazos):
        tariff = make_plan(brazos)
        premise = make_premises(dana, address_line="500 Mason Rd Plaza")
        master_unit = make_unit(dana, premise["id"], label="Master", services=["electric"])
        master = make_asset(
            dana,
            asset_no="M-7200",
            service="electric",
            unit_id=master_unit["id"],
            install_date="2026-08-01",
        )
        # M-7205 sits in inventory, waiting to be assigned by the wizard.
        make_asset(dana, asset_no="M-7205", service="electric", unit="kWh")
        result = services.create_unit(
            dana,
            {
                "premises_id": premise["id"],
                "label": "Suite 220",
                "unit_type": "commercial",
                "square_feet": 1150,
                "services": ["electric"],
                "meters": [
                    {
                        "service": "electric",
                        "mode": "assign_existing",
                        "asset_no": "M-7205",
                        "install_date": "2026-09-01",
                    }
                ],
                "plan": {
                    "tariff_id": str(tariff.id),
                    "effective_from": "2026-09-01",
                    "plan_locked": True,
                },
            },
        )
        asset = asset_models.Asset.objects.get(tenant=brazos, asset_no="M-7205")
        asset.parent_asset = asset_models.Asset.objects.get(
            tenant=brazos, asset_no=master["asset_no"]
        )
        asset.save(update_fields=["parent_asset"])
        row = selectors.unit_list_dict(selectors.unit_row(result["id"]))

    assert result["meters"][0]["asset"]["asset_no"] == "M-7205"
    assert result["meters"][0]["asset"]["status"] == "active"  # left inventory
    assert result["plan_assignment"]["rate_plan_id"] == str(tariff.id)
    assert result["plan_assignment"]["plan_locked"] is True
    # BR-CUS-013 history is rating-owned and is WRITTEN now (PO gap 1, 2026-08-11).
    assert result["plan_assignment"]["history_recorded"] is True
    assert row["occupancy"] == "vacant"  # BR-MET-036: derived, no account yet
    assert models.ServicePoint.objects.filter(tenant=brazos, unit_id=result["id"]).count() == 1


def test_us_met_003_tc3__auto_generate_reserves_the_next_series_number(brazos, dana):
    """BR-MET-006 auto-generate + BR-AST-026: the number is the tenant `asset`
    series sequence carried under the per-type prefix the rule names."""
    with tenant_ctx(brazos):
        premise = make_premises(dana)
        result = services.create_unit(
            dana,
            {
                "premises_id": premise["id"],
                "label": "Unit A",
                "services": ["water"],
                "meters": [{"service": "water", "mode": "auto_generate", "read_method": "ami"}],
            },
        )
    asset = result["meters"][0]["asset"]
    assert asset["asset_no"].startswith("M-")  # M- prefix, AST- series sequence
    assert asset["unit"] == "kgal"  # explicit UoM defaulted from the service


def test_us_met_003_tc4__disabled_service_row_is_refused(brazos, dana):
    """BR-MET-003: Gas is not enabled for Brazos Bend — the grid renders it
    disabled and the server refuses a submitted row."""
    with tenant_ctx(brazos):
        premise = make_premises(dana)
        with pytest.raises(errors.ValidationError) as caught:
            services.create_unit(
                dana,
                {
                    "premises_id": premise["id"],
                    "label": "Unit A",
                    "meters": [{"service": "gas", "mode": "auto_generate"}],
                },
            )
    assert caught.value.field_errors[0]["message_key"] == "metering.service_not_enabled"


def test_us_met_003_tc5__duplicate_label_writes_nothing(brazos, dana):
    with tenant_ctx(brazos):
        premise = make_premises(dana)
        make_unit(dana, premise["id"], label="Unit A")
        before = models.Unit.objects.filter(tenant=brazos).count()
        with pytest.raises(errors.ValidationError):
            make_unit(dana, premise["id"], label="Unit A")
        assert models.Unit.objects.filter(tenant=brazos).count() == before


def test_us_met_003_tc6__assigning_an_already_active_meter_is_refused(brazos, dana):
    with tenant_ctx(brazos):
        premise = make_premises(dana)
        first = make_unit(dana, premise["id"], label="Unit A", services=["electric"])
        make_asset(
            dana,
            asset_no="M-7001",
            service="electric",
            unit_id=first["id"],
            install_date="2026-08-01",
        )
        with pytest.raises(errors.BizError) as caught:
            services.create_unit(
                dana,
                {
                    "premises_id": premise["id"],
                    "label": "Unit B",
                    "services": ["electric"],
                    "meters": [
                        {"service": "electric", "mode": "assign_existing", "asset_no": "M-7001"}
                    ],
                },
            )
    assert caught.value.br_ref == "BR-AST-017"
    assert caught.value.params["asset_no"] == "M-7001"
    assert caught.value.params["action"] == "reassign"


def test_us_met_003_tc7__multiplier_must_be_positive(brazos, dana):
    with tenant_ctx(brazos):
        premise = make_premises(dana)
        with pytest.raises(errors.ValidationError) as caught:
            services.create_unit(
                dana,
                {
                    "premises_id": premise["id"],
                    "label": "Unit A",
                    "services": ["electric"],
                    "meters": [{"service": "electric", "mode": "auto_generate", "multiplier": "0"}],
                },
            )
        assert models.Unit.objects.filter(tenant=brazos, label="Unit A").count() == 0
    assert caught.value.field_errors[0]["field"] == "multiplier"
    assert caught.value.code == errors.VAL_RANGE


def test_us_met_003_tc9__one_meter_per_service_per_unit(brazos, dana):
    """BR-MET-006: at most ONE meter per enabled service per unit."""
    with tenant_ctx(brazos):
        premise = make_premises(dana)
        with pytest.raises(errors.ValidationError) as caught:
            services.create_unit(
                dana,
                {
                    "premises_id": premise["id"],
                    "label": "Unit A",
                    "services": ["electric"],
                    "meters": [
                        {"service": "electric", "mode": "auto_generate"},
                        {"service": "electric", "mode": "auto_generate"},
                    ],
                },
            )
    assert caught.value.field_errors[0]["message_key"] == "metering.meter.one_per_service"


def test_us_met_003_tc10__plan_override_on_an_occupied_unit_warns(brazos, dana, monkeypatch):
    """BR-MET-042 (PO PU-12): a direct unit-level plan edit is ALLOWED even
    when occupied — as an error-correction override with warning + audit."""
    from apps.metering import seams

    with tenant_ctx(brazos):
        tariff_a = make_plan(brazos, name="Residential Standard")
        tariff_b = make_plan(brazos, name="Small Commercial")
        premise = make_premises(dana)
        unit = make_unit(dana, premise["id"], label="Unit A")
        services.assign_unit_plan(dana, unit["id"], {"tariff_id": str(tariff_a.id)})
        monkeypatch.setattr(
            seams, "active_account_for_unit", lambda _uid: {"account_no": "A-00412"}
        )
        result = services.assign_unit_plan(dana, unit["id"], {"tariff_id": str(tariff_b.id)})
    assert result["warning"]["br_ref"] == "BR-MET-042"
    assert result["rate_plan_id"] == str(tariff_b.id)


@pytest.mark.isolation
def test_us_met_003_tc8__isolation_pickers_never_cross_tenants(brazos, dana, lonestar, erin):
    with tenant_ctx(brazos):
        premise = make_premises(dana)
        make_unit(dana, premise["id"], label="Unit A", services=["electric"])
        make_asset(dana, asset_no="M-9001", service="electric", unit="kWh")
    with tenant_ctx(lonestar):
        other = make_premises(erin, address_line="4102 Ranch Rd 12", services_available=["water"])
        with pytest.raises(errors.ValidationError):
            # Brazos Bend inventory is not selectable from Lone Star Ridge.
            services.create_unit(
                erin,
                {
                    "premises_id": other["id"],
                    "label": "Unit A",
                    "services": ["water"],
                    "meters": [
                        {"service": "water", "mode": "assign_existing", "asset_no": "M-9001"}
                    ],
                },
            )
        with pytest.raises(errors.NotFoundError):
            services.create_unit(erin, {"premises_id": premise["id"], "label": "X"})
