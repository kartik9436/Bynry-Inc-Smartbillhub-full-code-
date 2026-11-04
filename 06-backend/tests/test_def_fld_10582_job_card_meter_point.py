# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-FLD-10582 (beta MQ-015, CR-187-BRC10) — the phone showed *No
#           customer*, *No asset* and a greyed *Navigate* on a job with all three
# Rules:    BR-WRK-006 (the asset anchor) · BR-WRK-008 (copies vs live reads) ·
#           CLAUDE.md hard rule 8 + BR-MET-1162 (a unit's own point wins, and
#           the wire says which) · hard rule 1 (tenant scope)
# Tests:    this file · test_def_fld_10582_job_card_meter_point_pg.py (RLS) ·
#           field-app/tests/sync/def_fld_10582_job_card.test.ts (the handset)
# ───────────────────────────────────────────────────────
"""The job card and bundle carry the meter, the point and the customer — and the
SHAPE the handset test is built from is the shape this server returns.

`field-app/tests/sync/support/serverJob.json` is the handset's copy of one card
and one bundle. The last case here builds a real job and compares KEY SETS with
that file, so the phone's test cannot drift onto a shape the server never sends
(MQ-015 hid exactly that way: the handset tests seeded rows straight into the
handset database and never met the wire)."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from apps.metering import connections as w6
from apps.metering import models as metering_models
from apps.work import connection_models as work_tables
from apps.work import dispatch, mobile
from apps.work import models as work_models
from apps.work import services as work_services

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · marcus
from tests.test_us_met_helpers import make_asset, make_premises, make_unit
from tests.test_us_ten_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

FIXTURE = (
    Path(__file__).resolve().parents[2] / "field-app" / "tests" / "sync" / "support" / "serverJob.json"
)


def _reference():
    for code in ("work_priorities", "work_order_types", "work_hold_reasons"):
        work_services.seed_reference_list(code, [], "test")


def _technician(tenant, email="d-ortiz@brazos.test", name="D. Ortiz"):
    from apps.identity import models as identity_models

    user = identity_models.User.objects.create(tenant_id=tenant.id, email=email, full_name=name)
    return work_models.Technician.objects.create(tenant_id=tenant.id, user=user)


def _as(tech):
    return SimpleNamespace(id=tech.user_id, role="field_technician")


def _in_service(asset_id):
    from apps.assets import models as assets_models

    stage = assets_models.AssetLifecycleStage.objects.filter(behavior_class="in_service").first()
    assets_models.Asset.objects.filter(pk=asset_id).update(status=stage)


def _meter_on(actor, unit_id, service="water", asset_no="W-5000", **fields):
    """A meter standing on the unit's `service` point."""
    from apps.assets import models as assets_models
    from apps.metering import services as metering_services

    metering_services.ensure_service_point(unit_id, service)
    point = metering_models.ServicePoint.objects.get(unit_id=unit_id, service__code=service)
    unit_of = {"water": "gal", "electric": "kWh"}[service]
    asset = make_asset(actor, asset_no=asset_no, service=service, unit=unit_of, **fields)
    assets_models.Asset.objects.filter(pk=asset["id"]).update(service_point=point)
    return asset


def _site(actor, address="1400 Elm Street", *, premises_point=None, unit_point=None):
    premises = make_premises(actor, address_line=address, services_available=["water", "electric"])
    unit = make_unit(actor, premises["id"], label="Unit A")
    if premises_point:
        metering_models.Premises.objects.filter(pk=premises["id"]).update(
            lat=Decimal(premises_point[0]), lng=Decimal(premises_point[1])
        )
    if unit_point:
        metering_models.Unit.objects.filter(pk=unit["id"]).update(
            lat=Decimal(unit_point[0]), lng=Decimal(unit_point[1])
        )
    return premises, unit


def _job(actor, premises, unit=None, **anchors):
    body = {"type": "Meter exchange", "service": "water", "premises_id": premises["id"]}
    if unit is not None:
        body["unit_id"] = unit["id"]
    body.update(anchors)
    return w6.create_work_order(actor, None, body)["id"]


def _card(tech, oid):
    day = mobile.today(_as(tech), days=7)
    return next(c for c in day["jobs"] if c["id"] == str(oid))


# ══════════════════════════════════════════════════════════════════════════
# The meter
# ══════════════════════════════════════════════════════════════════════════
def test_the_card_names_the_jobs_own_asset(brazos, dana):
    with tenant_ctx(brazos):
        _reference()
        tech = _technician(brazos)
        premises, unit = _site(dana)
        meter = _meter_on(dana, unit["id"], model="Neptune T-10", serial_no="88-2041")
        oid = _job(dana, premises, unit, asset_id=meter["id"])
        dispatch.record_act(dana, oid, {"act": "assign", "technician_id": str(tech.id)}, push=False)
        card = _card(tech, oid)

    assert card["meter"] == {
        "id": str(meter["id"]),
        "asset_no": "W-5000",
        "serial_no": "88-2041",
        "model": "Neptune T-10",
        "size_class": card["meter"]["size_class"],
        "service": "water",
    }
    assert "badge" not in card["meter"]


def test_a_job_on_a_unit_names_the_one_in_service_meter_there(brazos, dana):
    with tenant_ctx(brazos):
        _reference()
        tech = _technician(brazos)
        premises, unit = _site(dana)
        meter = _meter_on(dana, unit["id"])
        _in_service(meter["id"])
        oid = _job(dana, premises, unit)
        dispatch.record_act(dana, oid, {"act": "assign", "technician_id": str(tech.id)}, push=False)
        card = _card(tech, oid)
    assert card["meter"]["asset_no"] == "W-5000"


def test_two_meters_on_the_unit_is_no_guess(brazos, dana):
    with tenant_ctx(brazos):
        _reference()
        tech = _technician(brazos)
        premises, unit = _site(dana)
        first = _meter_on(dana, unit["id"])
        _in_service(first["id"])
        second = make_asset(dana, asset_no="W-5001", service="water", unit="gal")
        from apps.assets import models as assets_models

        assets_models.Asset.objects.filter(pk=second["id"]).update(
            service_point_id=assets_models.Asset.objects.get(pk=first["id"]).service_point_id
        )
        _in_service(second["id"])
        oid = _job(dana, premises, unit)
        dispatch.record_act(dana, oid, {"act": "assign", "technician_id": str(tech.id)}, push=False)
        card = _card(tech, oid)
    assert card["meter"] is None


def test_a_meter_exchanged_on_the_server_is_the_new_meter_on_the_next_card(brazos, dana):
    """Read at use, never copied: re-anchoring the job moves the card."""
    with tenant_ctx(brazos):
        _reference()
        tech = _technician(brazos)
        premises, unit = _site(dana)
        old = _meter_on(dana, unit["id"])
        oid = _job(dana, premises, unit, asset_id=old["id"])
        dispatch.record_act(dana, oid, {"act": "assign", "technician_id": str(tech.id)}, push=False)
        assert _card(tech, oid)["meter"]["asset_no"] == "W-5000"
        new = make_asset(dana, asset_no="W-6000", service="water", unit="gal")
        work_tables.WorkOrder.objects.filter(pk=oid).update(asset_id=new["id"])
        assert _card(tech, oid)["meter"]["asset_no"] == "W-6000"


# ══════════════════════════════════════════════════════════════════════════
# The point — hard rule 8 / BR-MET-1162
# ══════════════════════════════════════════════════════════════════════════
def test_the_premises_point_is_on_the_card_and_says_so(brazos, dana):
    with tenant_ctx(brazos):
        _reference()
        tech = _technician(brazos)
        premises, unit = _site(dana, premises_point=("30.267153", "-97.743057"))
        oid = _job(dana, premises, unit)
        dispatch.record_act(dana, oid, {"act": "assign", "technician_id": str(tech.id)}, push=False)
        premise = _card(tech, oid)["premise"]
    assert premise["address"] == "1400 Elm Street"
    assert (premise["lat"], premise["lng"], premise["position_source"]) == (
        "30.267153", "-97.743057", "premises",
    )


def test_a_units_own_point_wins_and_says_so(brazos, dana):
    with tenant_ctx(brazos):
        _reference()
        tech = _technician(brazos)
        premises, unit = _site(
            dana, premises_point=("30.267153", "-97.743057"), unit_point=("30.268000", "-97.744000")
        )
        oid = _job(dana, premises, unit)
        dispatch.record_act(dana, oid, {"act": "assign", "technician_id": str(tech.id)}, push=False)
        premise = _card(tech, oid)["premise"]
    assert (premise["lat"], premise["lng"], premise["position_source"]) == (
        "30.268000", "-97.744000", "unit",
    )


def test_no_point_recorded_is_null_never_invented(brazos, dana):
    with tenant_ctx(brazos):
        _reference()
        tech = _technician(brazos)
        premises, unit = _site(dana)
        oid = _job(dana, premises, unit)
        dispatch.record_act(dana, oid, {"act": "assign", "technician_id": str(tech.id)}, push=False)
        premise = _card(tech, oid)["premise"]
    assert (premise["lat"], premise["lng"], premise["position_source"]) == (None, None, None)


def test_other_callers_of_premise_of_only_gain_keys(brazos, dana):
    """`selectors._premise_of`'s other callers (the Orders list, Nearby, the
    alerts) read `id`/`premise_no`/`address`; those three are unchanged."""
    from apps.work import selectors

    with tenant_ctx(brazos):
        _reference()
        premises, unit = _site(dana)
        oid = _job(dana, premises, unit)
        order = work_tables.WorkOrder.objects.get(pk=oid)
        out = selectors._premise_of(order)
    assert out["id"] == str(premises["id"]) and out["address"] == "1400 Elm Street"
    assert set(out) == {"id", "premise_no", "address", "lat", "lng", "position_source"}


# ══════════════════════════════════════════════════════════════════════════
# The handset's copy of the shape is the server's shape
# ══════════════════════════════════════════════════════════════════════════
def test_the_handset_fixture_has_the_servers_card_and_bundle_keys(brazos, marcus):
    from apps.customers import services as customers_services
    from tests.test_us_cus_003_account_write import _create_payload, _unit_with_plan

    with tenant_ctx(brazos):
        _reference()
        tech = _technician(brazos)
        unit = _unit_with_plan(marcus, brazos)
        account = customers_services.create_account(marcus, _create_payload(unit["id"]))
        customers_services.update_account_contact(
            marcus, account["id"], {"full_name": "Sarah Miller", "phone": "(512) 555-0114"}
        )
        unit_row = metering_models.Unit.objects.get(pk=unit["id"])
        metering_models.Premises.objects.filter(pk=unit_row.premises_id).update(
            lat=Decimal("30.267153"), lng=Decimal("-97.743057")
        )
        meter = make_asset(marcus, asset_no="W-5000", service="water", unit="gal", model="Neptune T-10")
        oid = _job(marcus, {"id": str(unit_row.premises_id)}, unit, asset_id=meter["id"])
        dispatch.record_act(marcus, oid, {"act": "assign", "technician_id": str(tech.id)}, push=False)
        card = _card(tech, oid)
        pack = mobile.bundle(_as(tech), oid)

    assert pack["customer"]["name"] == "Sarah Miller"
    assert pack["card"]["meter"]["asset_no"] == "W-5000"
    assert pack["card"]["premise"]["position_source"] == "premises"

    fixture = json.loads(FIXTURE.read_text())
    # The card: every key the server sends, and the nested premise and meter.
    # (The bundle's `card` is the same card; the handset support adds it.)
    for served, copy in ((card, fixture["card"]), (pack["card"], fixture["card"])):
        assert set(copy) == set(served), sorted(set(copy) ^ set(served))
        assert set(copy["premise"]) == set(served["premise"])
        assert set(copy["meter"]) == set(served["meter"])
    # The bundle: every key the handset copy carries is one the server sends,
    # and the customer is the server's shape exactly.
    assert set(fixture["bundle"]) <= set(pack), set(fixture["bundle"]) - set(pack)
    assert set(fixture["bundle"]["customer"]) == set(pack["customer"])
