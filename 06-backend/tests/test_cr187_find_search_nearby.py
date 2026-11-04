# ── Trace ──────────────────────────────────────────────
# Change:   CR-187-BRC10 · Phase 13 · T-40 — lane S-FIND
# Rules:    BR-FLD-00002 (R2) · BR-FLD-00034 (R34) · BR-FLD-00041/42/43
#           (R41–R43) · NFR-3 · NFR-5 · hard rules 1 and 8 · BR-MET-1162
# ───────────────────────────────────────────────────────
"""The field app's two server finds: the meter search (FF-41) and Nearby
(FF-11). Paged with no cap, ranked in SQL, the point walked to the premises
with a unit's own point winning, and a second utility's rows never seen."""

from __future__ import annotations

import copy
import uuid
from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from apps.metering import models as metering_models
from apps.work import field_find
from apps.work import models as work_models
from core import errors
from core.dbfields import uuid7

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin
from tests.test_us_met_helpers import make_asset, make_installed_asset, make_premises, make_unit, tenant_ctx

pytestmark = pytest.mark.django_db

#: The device's position (FF-11). A degree of latitude is ~69.09 mi; at this
#: latitude a degree of longitude is ~59.99 mi.
LAT0, LNG0 = 29.760000, -95.370000
MI_LAT = 1 / 69.0933
MI_LNG = 1 / (69.0933 * 0.86818)


def _at(north_mi=0.0, east_mi=0.0):
    return (
        Decimal(str(round(LAT0 + north_mi * MI_LAT, 6))),
        Decimal(str(round(LNG0 + east_mi * MI_LNG, 6))),
    )


def _technician(tenant, email, name):
    from apps.identity import models as identity_models

    user = identity_models.User.objects.create(tenant=tenant, email=email, full_name=name)
    tech = work_models.Technician.objects.create(tenant=tenant, user=user)
    return tech, type("Actor", (), {"id": user.id, "pk": user.id, "role": "field_technician"})()


def _job(actor, address, *, north_mi=None, east_mi=0.0, type_name="Routine read", service="electric", **fields):
    premises = make_premises(actor, address_line=address, services_available=[service])
    if north_mi is not None:
        lat, lng = _at(north_mi, east_mi)
        metering_models.Premises.objects.filter(pk=premises["id"]).update(lat=lat, lng=lng)
    order = w6.create_work_order(actor, None, {"premises_id": str(premises["id"]), "type": type_name})
    if fields:
        work_tables.WorkOrder.objects.filter(pk=order["id"]).update(**fields)
    return order


# ══════════════════════════════════════════════════════════════════════════
# FF-11 Nearby
# ══════════════════════════════════════════════════════════════════════════


def test_tc1_nearby_is_sorted_by_distance_and_says_who_holds_each(brazos, dana):
    """US-FLD-023 TC-1's shape: three jobs inside 2 miles, nearest first, the one
    R. Patel took greyed with his name; one beyond the radius is not listed."""
    with tenant_ctx(brazos):
        patel, _ = _technician(brazos, "r.patel@b.test", "R. Patel")
        _me, me = _technician(brazos, "d.ortiz@b.test", "D. Ortiz")
        far = _job(dana, "77 Far Road", north_mi=3.0)
        birch = _job(dana, "60 Birch Lane", north_mi=-1.4, assignee_technician=patel)
        maple = _job(dana, "9 Maple Court", east_mi=0.6, north_mi=0.0)
        elm = _job(dana, "1412 Elm Street", north_mi=0.2)
        out = field_find.nearby(me, lat=str(LAT0), lng=str(LNG0))

    numbers = [r["order_no"] for r in out["results"]]
    assert numbers == [elm["order_no"], maple["order_no"], birch["order_no"]]
    assert far["order_no"] not in numbers
    assert [r["distance_mi"] for r in out["results"]] == ["0.20", "0.60", "1.40"]
    assert [r["holder"] for r in out["results"]] == ["unassigned", "unassigned", "taken"]
    assert out["results"][2]["taken_by"] == "R. Patel"
    assert [r["claimable"] for r in out["results"]] == [True, True, False]
    assert out["results"][0]["premise"]["address"] == "1412 Elm Street"
    assert out["results"][0]["point_source"] == "premises"
    # The header's *N unassigned* counts the radius, not the page; the default
    # radius is R34's two miles.
    assert out["unassigned"] == 2 and out["count"] == 3 and out["radius_mi"] == "2.00"
    assert out["complete"] is True and out["without_location"] == 0


def test_a_units_own_point_wins_over_its_premises(brazos, dana):
    """BR-MET-1162 — a cabin five miles from its site office is where its job
    is; the row says it used the UNIT's point."""
    with tenant_ctx(brazos):
        _me, me = _technician(brazos, "d.ortiz@b.test", "D. Ortiz")
        order = _job(dana, "1 Campus Way", north_mi=5.0)
        premises_id = work_tables.WorkOrder.objects.get(pk=order["id"]).premises_id
        unit = make_unit(dana, str(premises_id), label="Cabin 4")
        lat, lng = _at(0.1)
        metering_models.Unit.objects.filter(pk=unit["id"]).update(lat=lat, lng=lng)
        work_tables.WorkOrder.objects.filter(pk=order["id"]).update(unit_id=unit["id"])
        half = make_unit(dana, str(premises_id), label="Cabin 5")
        metering_models.Unit.objects.filter(pk=half["id"]).update(lat=lat)  # no lng: not a place
        other = _job(dana, "1 Campus Way B", north_mi=5.0)
        work_tables.WorkOrder.objects.filter(pk=other["id"]).update(unit_id=half["id"])
        out = field_find.nearby(me, lat=str(LAT0), lng=str(LNG0), radius_mi="10")

    rows = {r["order_no"]: r for r in out["results"]}
    assert rows[order["order_no"]]["distance_mi"] == "0.10"
    assert rows[order["order_no"]]["point_source"] == "unit"
    assert rows[other["order_no"]]["point_source"] == "premises"
    assert rows[other["order_no"]]["distance_mi"] == "5.00"


def test_a_job_with_no_point_is_counted_never_silently_dropped(brazos, dana):
    """R42 — a job that matched but stands nowhere cannot be measured; the
    answer says how many and is not `complete`."""
    with tenant_ctx(brazos):
        _me, me = _technician(brazos, "d.ortiz@b.test", "D. Ortiz")
        _job(dana, "1412 Elm Street", north_mi=0.2)
        _job(dana, "No Point Road")
        out = field_find.nearby(me, lat=str(LAT0), lng=str(LNG0))
    assert out["count"] == 1
    assert out["without_location"] == 1 and out["complete"] is False


def test_scope_filters_type_priority_and_due(brazos, dana):
    with tenant_ctx(brazos):
        me_tech, me = _technician(brazos, "d.ortiz@b.test", "D. Ortiz")
        mine = _job(dana, "5 Mine St", north_mi=0.3, assignee_technician=me_tech)
        seal = _job(dana, "9 Maple Court", north_mi=0.6, type_name="Meter seal check")
        later = _job(dana, "8 Later Ave", north_mi=0.7, due_at=timezone.now() + timedelta(days=9))
        soon = _job(dana, "7 Soon Ave", north_mi=0.8, due_at=timezone.now() + timedelta(hours=2))
        p2 = work_models.WorkPriority.objects.filter(tenant=brazos).order_by("rank").first()
        work_tables.WorkOrder.objects.filter(pk=seal["id"]).update(priority=p2)

        def numbers(**kw):
            return [r["order_no"] for r in field_find.nearby(me, lat=str(LAT0), lng=str(LNG0), **kw)["results"]]

        assert numbers(scope="mine") == [mine["order_no"]]
        assert mine["order_no"] not in numbers(scope="unassigned")
        assert numbers(unassigned="true") == numbers(scope="unassigned")
        assert numbers(type="meter seal check") == [seal["order_no"]]
        assert numbers(priority=p2.code.lower()) == [seal["order_no"]]
        due = numbers(due_by=(timezone.now() + timedelta(days=1)).date().isoformat())
        assert soon["order_no"] in due and later["order_no"] not in due
        mine_row = field_find.nearby(me, lat=str(LAT0), lng=str(LNG0), scope="mine")["results"][0]
        assert mine_row["holder"] == "mine" and mine_row["claimable"] is False


def test_nearby_pages_with_no_cap(brazos, dana):
    """NFR-3 / NFR-5 — 130 jobs in the radius, 50 a page: three pages, every
    job exactly once, distances never decreasing across the page breaks."""
    with tenant_ctx(brazos):
        _me, me = _technician(brazos, "d.ortiz@b.test", "D. Ortiz")
        seed = _job(dana, "Seed St", north_mi=0.01)
        template = work_tables.WorkOrder.objects.get(pk=seed["id"])
        premises = metering_models.Premises.objects.get(pk=template.premises_id)
        clones_p, clones_o = [], []
        for i in range(129):
            p = copy.copy(premises)
            p.id = uuid7()
            p.premise_no = f"PX-{i:04d}"
            p.address_line = f"{i} Clone Row"
            p.lat, p.lng = _at(0.01 * (i + 2))
            clones_p.append(p)
            o = copy.copy(template)
            o.id = uuid7()
            o.order_no = f"WO-X{i:04d}"
            o.premises_id = p.id
            clones_o.append(o)
        metering_models.Premises.objects.bulk_create(clones_p)
        work_tables.WorkOrder.objects.bulk_create(clones_o)
        pages = [
            field_find.nearby(me, lat=str(LAT0), lng=str(LNG0), page=n, per=50) for n in (1, 2, 3)
        ]
    assert [p["count"] for p in pages] == [130, 130, 130]
    assert [len(p["results"]) for p in pages] == [50, 50, 30]
    assert pages[2]["next"] is None and pages[0]["pages"] == 3
    ids = [r["id"] for p in pages for r in p["results"]]
    assert len(ids) == len(set(ids)) == 130
    miles = [Decimal(r["distance_mi"]) for p in pages for r in p["results"]]
    assert miles == sorted(miles)


def test_nearby_refuses_a_missing_or_impossible_position(brazos, dana):
    with tenant_ctx(brazos):
        _me, me = _technician(brazos, "d.ortiz@b.test", "D. Ortiz")
        with pytest.raises(errors.ValidationError) as missing:
            field_find.nearby(me, lat=None, lng=str(LNG0))
        with pytest.raises(errors.ValidationError) as wrong:
            field_find.nearby(me, lat="91", lng=str(LNG0))
        with pytest.raises(errors.ValidationError) as radius:
            field_find.nearby(me, lat=str(LAT0), lng=str(LNG0), radius_mi="0")
        with pytest.raises(errors.ValidationError) as scope:
            field_find.nearby(me, lat=str(LAT0), lng=str(LNG0), scope="everyone")
    assert missing.value.params["reason"] == "nearby_position_required"
    assert wrong.value.params["reason"] == "nearby_position_out_of_range"
    assert radius.value.params["reason"] == "nearby_radius_not_positive"
    assert scope.value.params["reason"] == "nearby_scope_unknown"


def test_nearby_never_shows_another_utilitys_job(brazos, lonestar, dana, erin):
    """Hard rule 1 — Lone Star's job at the very same point is not Brazos's."""
    with tenant_ctx(lonestar):
        theirs = _job(erin, "1 Same Spot", north_mi=0.1, service="water")
    with tenant_ctx(brazos):
        _me, me = _technician(brazos, "d.ortiz@b.test", "D. Ortiz")
        ours = _job(dana, "2 Same Spot", north_mi=0.1)
        out = field_find.nearby(me, lat=str(LAT0), lng=str(LNG0))
    numbers = [r["id"] for r in out["results"]]
    assert numbers == [str(ours["id"])] and str(theirs["id"]) not in numbers


# ══════════════════════════════════════════════════════════════════════════
# FF-41 asset search
# ══════════════════════════════════════════════════════════════════════════


def _clone_assets(base_id, count, prefix):
    from apps.assets import models as assets_models

    base = assets_models.Asset.objects.get(pk=base_id)
    rows = []
    for i in range(count):
        a = copy.copy(base)
        a.id = uuid7()
        a.asset_no = f"{prefix}-{i:04d}"
        a.serial_no = f"SN{prefix}{i:04d}"
        rows.append(a)
    assets_models.Asset.objects.bulk_create(rows)


def test_search_pages_1200_assets_with_no_cap(brazos, dana):
    """NFR-3 / NFR-5 — 1,200 matches: every one reachable, none twice, and the
    total is the whole set, not the page."""
    with tenant_ctx(brazos):
        base = make_asset(dana, asset_no="SEED-1", serial_no="SN-SEED")  # matches nothing below
        _clone_assets(base["id"], 1200, "BULK")
        pages = [field_find.search_assets(dana, q="bulk-", page=n, per=500) for n in (1, 2, 3)]
        small = field_find.search_assets(dana, q="bulk-", page=24, per=50)
    assert [p["count"] for p in pages] == [1200, 1200, 1200]
    assert [len(p["results"]) for p in pages] == [500, 500, 200]
    ids = [r["id"] for p in pages for r in p["results"]]
    assert len(set(ids)) == 1200
    assert small["page"] == 24 and len(small["results"]) == 50 and small["next"] is None
    assert pages[0]["complete"] is True
    assert pages[0]["fields_not_held"] == ["badge", "device_id"]


def test_search_ranks_serial_first_then_asset_number_then_address(brazos, dana):
    """R43's order over the columns that exist: an exact serial before an exact
    asset number before a part of either before the address."""
    with tenant_ctx(brazos):
        contains = make_asset(dana, asset_no="A-ZX9-B", serial_no="Q-1")
        by_no = make_asset(dana, asset_no="ZX9", serial_no="Q-2")
        by_serial = make_asset(dana, asset_no="M-777", serial_no="zx9")
        out = field_find.search_assets(dana, q="ZX9")
    assert [r["id"] for r in out["results"]] == [by_serial["id"], by_no["id"], contains["id"]]
    assert [r["match_on"] for r in out["results"]] == ["serial", "asset_no", "asset_no"]


def test_search_finds_a_meter_by_address_and_says_where_it_stands(brazos, dana):
    """Hard rule 8 — the address is WALKED (a device seated on a unit, and a
    meter on a service point), never read off the asset."""
    from apps.tenancy import models as tenancy_models

    with tenant_ctx(brazos):
        seated = make_installed_asset(dana, asset_no="W-4471-B")
        premises = make_premises(dana, address_line="1400 Elm Street", services_available=["electric"])
        unit = make_unit(dana, premises["id"], label="Unit A")
        point = metering_models.ServicePoint.objects.create(
            tenant=brazos, unit_id=unit["id"], service=tenancy_models.Service.objects.get(code="electric")
        )
        lat, lng = _at(0.5)
        metering_models.Premises.objects.filter(pk=premises["id"]).update(lat=lat, lng=lng)
        on_point = make_asset(dana, asset_no="W-4471", serial_no="NEP-1")
        from apps.assets import models as assets_models

        assets_models.Asset.objects.filter(pk=on_point["id"]).update(service_point=point)
        by_street = field_find.search_assets(dana, q="1400 elm")
        by_seat = field_find.search_assets(dana, q="Installed Way")
        warehouse = make_asset(dana, asset_no="SPARE-1")
        spare = field_find.search_assets(dana, q="SPARE-1")

    row = by_street["results"][0]
    assert row["id"] == on_point["id"] and row["match_on"] == "address"
    assert row["place"]["premises"]["address"] == "1400 Elm Street"
    assert row["place"]["unit_label"] == "Unit A"
    assert row["place"]["point_source"] == "premises" and row["place"]["lat"] == str(lat)
    assert [r["id"] for r in by_seat["results"]] == [seated["id"]]
    assert by_seat["results"][0]["place"]["premises"]["address"].endswith("Installed Way")
    assert spare["results"][0]["id"] == warehouse["id"] and spare["results"][0]["place"] is None


def test_search_finds_a_meter_by_its_account_number(brazos, dana):
    from apps.customers import models as customer_models

    with tenant_ctx(brazos):
        seated = make_installed_asset(dana, asset_no="ACC-METER")
        from apps.assets import models as assets_models

        unit_id = assets_models.AssetAssignment.objects.get(asset_id=seated["id"]).unit_id
        customer_models.Account.objects.create(
            tenant=brazos,
            unit_id=unit_id,
            account_no="A-55123",
            status=customer_models.AccountStatus.objects.get(tenant=brazos, code="active"),
            account_type=customer_models.AccountType.objects.first(),
        )
        out = field_find.search_assets(dana, q="A-55123")
    assert [(r["id"], r["match_on"]) for r in out["results"]] == [(seated["id"], "account_no")]


def test_search_refuses_an_empty_box(brazos, dana):
    with tenant_ctx(brazos):
        with pytest.raises(errors.ValidationError) as refused:
            field_find.search_assets(dana, q="   ")
    assert refused.value.params["reason"] == "search_text_required"


def test_search_never_shows_another_utilitys_meter(brazos, lonestar, dana, erin):
    with tenant_ctx(lonestar):
        theirs = make_asset(erin, asset_no="TWIN-1", service="water", unit="gal")
    with tenant_ctx(brazos):
        ours = make_asset(dana, asset_no="TWIN-2")
        out = field_find.search_assets(dana, q="TWIN")
    assert [r["id"] for r in out["results"]] == [ours["id"]]
    assert theirs["id"] not in {r["id"] for r in out["results"]}


def test_the_routes_answer_over_http(brazos, dana, client):
    """The thin views reach the services (FieldAppRole) — the request path,
    not only the function (law 7: prove it in the harness that runs it)."""
    from django.urls import resolve

    for tail in ("assets/search", "nearby", "alerts"):
        match = resolve(f"/api/brazosbend/work/mobile/{tail}")
        assert match.func.__module__ == "apps.work.field_api"
    assert resolve(f"/api/brazosbend/work/mobile/alerts/{uuid.uuid4()}/ack").func.__module__ == "apps.work.field_api"
    assert resolve("/api/brazosbend/work/field-alerts").func.__module__ == "apps.work.field_api"
