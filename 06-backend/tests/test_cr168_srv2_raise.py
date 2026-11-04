# ── Trace ──────────────────────────────────────────────
# Story:    CR-168-BRC10 round 3, lane SRV-2 — the raise: P2.5, P2.9, P2.11,
#           P2.12, P2.13, P2.14, P2.16, P2.20, P2.21
# Rules:    rulings 19, 20, 22, 24, 25 · OQ-WRK-1497 CLOSED · BR-WRK-006 ·
#           BR-WRK-008 (copy, never link) · BR-WRK-027 · hard rule 6
# Tests:    this file (SQLite) · test_cr168_srv2_bulk_raise_pg.py (PostgreSQL)
# ───────────────────────────────────────────────────────
"""The raise half of `CR-168-BRC10` round 3."""

from __future__ import annotations

import pytest

from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from apps.tenancy import models as tenancy_models
from apps.work import api as work_api
from apps.work import models as work_models
from apps.work import raise_svc
from apps.work import services as work_services
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana
from tests.test_us_met_helpers import make_asset, make_premises, make_unit
from tests.test_us_ten_helpers import api_call, tenant_ctx

pytestmark = pytest.mark.django_db


def _reference():
    work_services.seed_reference_list("work_priorities", [], "test")
    work_services.seed_reference_list("work_order_types", [], "test")
    work_services.seed_reference_list("work_skills", [], "test")


def _template(tenant, name="Meter exchange", service="water", scope="per_unit"):
    return work_tables.WorkOrderTemplate.objects.create(
        tenant_id=tenant.id, name=name, scope=scope,
        service=tenancy_models.Service.objects.get(code=service), version=1,
    )


def _building(dana, address="301 Mill Pond Ln", units=3):
    premises = make_premises(dana, address_line=address, services_available=["water", "electric"])
    made = [make_unit(dana, premises["id"], label=f"Apt {101 + n}") for n in range(units)]
    return premises, made


def _meter(dana, unit, asset_no, service="water"):
    extra = {"unit": "gal", "install_date": "2026-01-15"} if service == "water" else {"install_date": "2026-01-15"}
    return make_asset(dana, asset_no=asset_no, service=service, unit_id=unit["id"], **extra)


# ══════════════════════════════════════════════════════════════════════════
# P2.11 · P2.14 · P2.20 · ruling 20 — one job, shaped by its template and asset
# ══════════════════════════════════════════════════════════════════════════


def test_a_water_template_on_an_electric_job_is_refused(dana, brazos):
    with tenant_ctx(brazos):
        _reference()
        template = _template(brazos)
        premises, _ = _building(dana)
        with pytest.raises(errors.ValidationError) as caught:
            w6.create_work_order(
                dana, None,
                {"type": "Meter exchange", "service": "electric",
                 "premises_id": premises["id"], "template_id": str(template.id)},
            )
        assert caught.value.message_key == "work.order.template_wrong_service"


def test_a_unit_only_raise_stands_on_its_building(dana, brazos):
    with tenant_ctx(brazos):
        _reference()
        premises, units = _building(dana)
        out = w6.create_work_order(dana, None, {"type": "Leak investigation", "unit_id": units[0]["id"]})
        assert out["premises_id"] == str(premises["id"])


def test_an_asset_raise_says_where_it_is(dana, brazos):
    """P2.20 — asset → service point → unit → premises, and the service."""
    with tenant_ctx(brazos):
        _reference()
        premises, units = _building(dana)
        meter = _meter(dana, units[1], "W-5041")
        out = w6.create_work_order(dana, None, {"type": "Meter exchange", "asset_id": meter["id"]})
        order = work_tables.WorkOrder.objects.get(pk=out["id"])
        assert str(order.premises_id) == str(premises["id"])
        assert str(order.unit_id) == str(units[1]["id"])
        assert order.service.code == "water"


def test_an_asset_of_another_building_is_refused(dana, brazos):
    with tenant_ctx(brazos):
        _reference()
        _premises, units = _building(dana)
        elsewhere = make_premises(dana, address_line="12 Kestrel Park", services_available=["water"])
        meter = _meter(dana, units[0], "W-5040")
        with pytest.raises(errors.ValidationError) as caught:
            w6.create_work_order(
                dana, None,
                {"type": "Meter exchange", "asset_id": meter["id"], "premises_id": elsewhere["id"]},
            )
        assert caught.value.message_key == "work.order.asset_not_on_premises"


def test_an_asset_type_chosen_means_an_asset_is_required(dana, brazos):
    """Ruling 20 — *"if asset type is selected then user needs to select asset"*."""
    with tenant_ctx(brazos):
        _reference()
        premises, units = _building(dana)
        meter = _meter(dana, units[0], "W-5040")
        from apps.work.seams import assets_seam

        type_id = assets_seam.asset_type_id(meter["id"])
        with pytest.raises(errors.ValidationError) as caught:
            w6.create_work_order(
                dana, None,
                {"type": "Meter exchange", "premises_id": premises["id"], "asset_type_id": type_id},
            )
        assert caught.value.message_key == "work.order.asset_required"


def test_a_template_restricted_to_another_asset_type_is_refused(dana, brazos):
    with tenant_ctx(brazos):
        _reference()
        _premises, units = _building(dana)
        meter = _meter(dana, units[0], "W-5040")
        template = _template(brazos, name="Hydrant flush")
        work_models.WorkOrderTemplateAssetType.objects.create(
            tenant_id=brazos.id, template_id=template.id,
            asset_type_id="00000000-0000-0000-0000-0000000000ff",
        )
        with pytest.raises(errors.ValidationError) as caught:
            w6.create_work_order(
                dana, None,
                {"type": "Hydrant flush", "asset_id": meter["id"], "template_id": str(template.id)},
            )
        assert caught.value.message_key == "work.order.asset_type_not_on_template"


# ══════════════════════════════════════════════════════════════════════════
# P2.5 · P2.9 — assign at the raise (ruling 25), through the one raise
# ══════════════════════════════════════════════════════════════════════════


def test_a_job_raised_with_an_assignee_is_scheduled_to_them(dana, brazos):
    from apps.identity import models as identity_models

    with tenant_ctx(brazos):
        _reference()
        premises, units = _building(dana)
        user = identity_models.User.objects.create(
            tenant_id=brazos.id, email="patel@b.test", full_name="R. Patel"
        )
        patel = work_models.Technician.objects.create(tenant_id=brazos.id, user=user)
        priority = work_models.WorkPriority.objects.get(tenant_id=brazos.id, code="NORMAL")
    response = api_call(
        work_api.work_orders, "post", f"/api/{brazos.subdomain}/work-orders",
        user=dana.user, role="system_admin", tenant=brazos,
        data={
            "type": "Leak investigation", "service": "water",
            "premises_id": premises["id"], "unit_id": units[0]["id"],
            "priority_id": str(priority.id), "due_on": "2026-10-09",
            "window_start": "2026-10-08T08:00:00-05:00", "window_end": "2026-10-08T12:00:00-05:00",
            "technician_notes": "Gate code 4471",
            "assignee": {"technician_id": str(patel.id)},
        },
    )
    assert response.status_code == 200, response.data
    with tenant_ctx(brazos):
        order = work_tables.WorkOrder.objects.get(pk=response.data["id"])
        assert order.assignee_technician_id == patel.id
        assert order.dispatch_state == "scheduled"
        assert order.technician_notes == "Gate code 4471"
        assert order.priority_id == priority.id
        assert order.window_start is not None
        # `due_on` 2026-10-09 is the END of that day in the utility's zone.
        from apps.work.seams import tenancy_seam

        local = order.due_at.astimezone(tenancy_seam.tenant_timezone())
        assert (local.date().isoformat(), local.hour, local.minute) == ("2026-10-09", 23, 59)
        assert work_models.WorkOrderAssignment.objects.filter(work_order=order, act="assign").count() == 1


def test_a_raise_ignores_an_area_ruling_24(dana, brazos):
    with tenant_ctx(brazos):
        _reference()
        area = tenancy_models.Area.objects.create(tenant_id=brazos.id, code="NE", name="North East")
        premises, _ = _building(dana)
        out = raise_svc.raise_work_order(
            dana, {"type": "Leak investigation", "premises_id": premises["id"], "area_id": str(area.id)}
        )
        assert work_tables.WorkOrder.objects.get(pk=out["id"]).area_id is None


# ══════════════════════════════════════════════════════════════════════════
# P2.12 — bulk raise: one job per unit, an answer per job, idempotent
# ══════════════════════════════════════════════════════════════════════════


def test_bulk_raise_one_job_per_unit_and_a_refusal_does_not_stop_the_rest(dana, brazos):
    with tenant_ctx(brazos):
        _reference()
        template = _template(brazos)
        premises, units = _building(dana)
        _other, foreign = _building(dana, address="500 Main St", units=1)
        answer = raise_svc.bulk_raise(
            dana,
            {"template_id": str(template.id), "type": "Meter exchange",
             "premises_id": premises["id"], "idempotency_key": "press-1",
             "unit_ids": [units[0]["id"], foreign[0]["id"], units[2]["id"]]},
        )
        assert (answer["done"], answer["failed"], answer["replayed"]) == (2, 1, False)
        assert [r["ok"] for r in answer["results"]] == [True, False, True]
        assert answer["results"][1]["reason"] == "work.order.unit_not_on_premises"
        assert answer["results"][0]["unit"] == {"label": "Apt 101"}
        made = work_tables.WorkOrder.objects.filter(tenant_id=brazos.id, template_id=template.id)
        assert made.count() == 2
        assert {o.scope for o in made} == {"per_unit"}  # copied from the template


def test_bulk_raise_repeated_key_returns_the_first_answer_and_raises_nothing(dana, brazos):
    with tenant_ctx(brazos):
        _reference()
        template = _template(brazos)
        premises, units = _building(dana)
        body = {"template_id": str(template.id), "type": "Meter exchange",
                "premises_id": premises["id"], "idempotency_key": "press-2",
                "unit_ids": [u["id"] for u in units]}
        first = raise_svc.bulk_raise(dana, dict(body))
        again = raise_svc.bulk_raise(dana, dict(body))
        assert again["replayed"] is True
        assert again["results"] == first["results"]
        assert work_tables.WorkOrder.objects.filter(tenant_id=brazos.id, template_id=template.id).count() == 3


def test_bulk_raise_per_asset_when_an_asset_type_is_chosen(dana, brazos):
    with tenant_ctx(brazos):
        _reference()
        template = _template(brazos)
        premises, units = _building(dana)
        meters = [_meter(dana, u, f"W-50{40 + n}") for n, u in enumerate(units)]
        from apps.work.seams import assets_seam

        type_id = assets_seam.asset_type_id(meters[0]["id"])
        with pytest.raises(errors.ValidationError) as caught:
            raise_svc.bulk_raise(
                dana, {"template_id": str(template.id), "type": "Meter exchange",
                       "premises_id": premises["id"], "idempotency_key": "press-3",
                       "asset_type_id": type_id, "unit_ids": [units[0]["id"]]},
            )
        assert caught.value.message_key == "work.order.asset_required"
        answer = raise_svc.bulk_raise(
            dana, {"template_id": str(template.id), "type": "Meter exchange",
                   "premises_id": premises["id"], "idempotency_key": "press-4",
                   "asset_type_id": type_id, "asset_ids": [m["id"] for m in meters[:2]]},
        )
        assert answer["done"] == 2
        assert [r["asset"]["asset_no"] for r in answer["results"]] == ["W-5040", "W-5041"]


def test_bulk_raise_refuses_an_empty_selection_and_a_missing_key(dana, brazos):
    with tenant_ctx(brazos):
        with pytest.raises(errors.ValidationError) as caught:
            raise_svc.bulk_raise(dana, {"idempotency_key": "k", "unit_ids": []})
        assert caught.value.message_key == "work.raise.selection_empty"
        with pytest.raises(errors.ValidationError) as missing:
            raise_svc.bulk_raise(dana, {"unit_ids": ["x"]})
        assert missing.value.message_key == "work.raise.key_required"


def test_bulk_raise_api(dana, brazos):
    with tenant_ctx(brazos):
        _reference()
        premises, units = _building(dana, units=2)
    response = api_call(
        work_api.work_orders_bulk_raise, "post", f"/api/{brazos.subdomain}/work-orders/bulk-raise",
        user=dana.user, role="system_admin", tenant=brazos,
        data={"type": "Leak investigation", "service": "water", "premises_id": premises["id"],
              "unit_ids": [u["id"] for u in units], "idempotency_key": "api-1"},
    )
    assert response.status_code == 200, response.data
    assert response.data["done"] == 2


# ══════════════════════════════════════════════════════════════════════════
# P2.16 · ruling 22 — the assets on the ticked units; P2.21 — an asset's templates
# ══════════════════════════════════════════════════════════════════════════


def test_raise_assets_pages_searches_and_says_choose_one(dana, brazos):
    with tenant_ctx(brazos):
        _reference()
        _premises, units = _building(dana)
        _meter(dana, units[0], "W-5040")
        _meter(dana, units[0], "M-MASTER-01")
        _meter(dana, units[1], "W-5041")
        page = raise_svc.raise_assets(unit_ids=[u["id"] for u in units])
        assert page["total"] == 3
        by_no = {r["asset_no"]: r for r in page["rows"]}
        assert by_no["W-5040"]["shares_unit"] is True
        assert by_no["W-5041"]["shares_unit"] is False
        assert by_no["W-5041"]["unit"]["label"] == "Apt 102"
        assert by_no["W-5041"]["premises"]["address"] == "301 Mill Pond Ln"
        assert by_no["W-5041"]["service"]["code"] == "water"
        found = raise_svc.raise_assets(unit_ids=[u["id"] for u in units], q="master")
        assert [r["asset_no"] for r in found["rows"]] == ["M-MASTER-01"]


def test_an_asset_is_offered_only_its_own_services_templates(dana, brazos):
    with tenant_ctx(brazos):
        _reference()
        _premises, units = _building(dana)
        meter = _meter(dana, units[0], "W-5040")
        _template(brazos, name="Water meter exchange", service="water")
        _template(brazos, name="Electric meter exchange", service="electric")
        offered = raise_svc.templates_for_asset(meter["id"])
        assert [r["name"] for r in offered["rows"]] == ["Water meter exchange"]
        assert offered["total"] == 1
        assert offered["asset"]["service_code"] == "water"


# ══════════════════════════════════════════════════════════════════════════
# Lane RAISE's additions (relayed 2026-10-04): what the screens send and read
# ══════════════════════════════════════════════════════════════════════════


def test_bulk_raise_carries_type_source_custom_fields_and_a_window(dana, brazos):
    with tenant_ctx(brazos):
        _reference()
        premises, units = _building(dana, units=2)
        kind = work_models.WorkOrderType.objects.filter(tenant_id=brazos.id, active=True).first()
        answer = raise_svc.bulk_raise(
            dana,
            {"type": kind.name, "type_id": str(kind.id), "service": "water",
             "premises_id": premises["id"], "source": "dispatcher", "custom_data": {},
             "window_start": "2026-10-08T08:00:00-05:00", "window_end": "2026-10-08T12:00:00-05:00",
             "unit_ids": [u["id"] for u in units], "idempotency_key": "raise-extra-1"},
        )
        assert answer["done"] == 2, answer
        for result in answer["results"]:
            order = work_tables.WorkOrder.objects.get(pk=result["id"])
            assert order.type_ref_id == kind.id
            assert order.source == "dispatcher"
            assert order.window_start is not None and order.window_end is not None


def test_raise_assets_serve_location_and_last_read(dana, brazos):
    from datetime import datetime, timezone as dt_tz
    from decimal import Decimal

    from apps.metering import models as metering_models

    with tenant_ctx(brazos):
        _reference()
        _premises, units = _building(dana, units=1)
        meter = _meter(dana, units[0], "W-5040")
        from apps.assets import models as assets_models

        assets_models.Asset.objects.filter(pk=meter["id"]).update(location_note="Front boundary box")
        metering_models.MeterRead.objects.create(
            tenant_id=brazos.id, asset_id=meter["id"], read_at=datetime(2026, 8, 11, tzinfo=dt_tz.utc),
            current_value=Decimal("2546"), unit="kgal", source="manual",
        )
        row = raise_svc.raise_assets(unit_ids=[units[0]["id"]])["rows"][0]
        assert row["location"] == "Front boundary box"
        assert row["unit"]["id"] == str(units[0]["id"])
        assert row["last_read"] == {"reading": "2546.000000", "unit": "kgal", "on": "2026-08-11"}


def test_templates_list_filters_by_job_type_asset_type_and_raisable(dana, brazos):
    from apps.work import selectors

    with tenant_ctx(brazos):
        _reference()
        kind = work_models.WorkOrderType.objects.filter(tenant_id=brazos.id, active=True).first()
        mine = _template(brazos, name="Typed one")
        work_tables.WorkOrderTemplate.objects.filter(pk=mine.id).update(type_id=kind.id)
        _template(brazos, name="Untyped one")
        draft = _template(brazos, name="Typed draft")
        work_tables.WorkOrderTemplate.objects.filter(pk=draft.id).update(type_id=kind.id, version=0)
        page = selectors.templates_page(job_type=str(kind.id), raisable=True)
        # `DEF-WRK-9612` (lane SRV-3): a template naming NO job type applies to
        # every type, so the untyped one is offered beside the typed one; the
        # unpublished draft still is not.
        assert sorted(r["name"] for r in page["rows"]) == ["Typed one", "Untyped one"]
        restricted = _template(brazos, name="Hydrant only")
        work_models.WorkOrderTemplateAssetType.objects.create(
            tenant_id=brazos.id, template_id=restricted.id,
            asset_type_id="00000000-0000-0000-0000-0000000000ff",
        )
        other_type = "00000000-0000-0000-0000-0000000000ee"
        names = {r["name"] for r in selectors.templates_page(asset_type=other_type)["rows"]}
        assert "Hydrant only" not in names and "Untyped one" in names


def test_units_list_narrows_by_unit_type_for_the_raise_chips(dana, brazos):
    """Image 14's *Residential · Commercial* chips — `f.unit_type` on `/units`."""
    from apps.metering import models as metering_models
    from apps.metering import selectors as metering_selectors

    with tenant_ctx(brazos):
        premises, units = _building(dana, units=2)
        metering_models.Unit.objects.filter(pk=units[0]["id"]).update(unit_type="commercial")
        metering_models.Unit.objects.filter(pk=units[1]["id"]).update(unit_type="residential")
        rows = metering_selectors.units_queryset(
            filters={"premises_id": premises["id"], "unit_type": "commercial"}
        )
        assert [str(u.id) for u in rows] == [str(units[0]["id"])]
