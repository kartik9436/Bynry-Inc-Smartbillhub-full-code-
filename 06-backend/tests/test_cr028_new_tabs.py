# ── Trace ──────────────────────────────────────────────
# Change:   CR-028 AST-W5 (B16 §4.4–§4.6 · §10 rulings D1/D3/D5/D6/D7,
#           PO 2026-08-22): T1 Inventory counts-&-costs (GET /assets/stock) ·
#           T2 Lifecycle three lists + Asset value sidebar (GET
#           /assets/lifecycle) · T3 Map (premises lat/lng, the Census
#           geocoder, GET /assets/geo) · T4 the "Work R5" posture (backend
#           serves NO work-order fact anywhere in these payloads)
# Rules:    BR-AST-031 (filters/counts key off the behavior CLASS, never the
#           label) · BR-AST-047 (valuation on the device record; NO finance
#           link) · hard rule 2 (money stored 4 dp, displayed 2) · hard rule 5
#           (only the ledger posting service writes journal lines — asserted
#           by ABSENCE) · §10-D5 (counts & costs ONLY: no vans, no reorder,
#           no stock table) · §10-D3 (no GL sentence anywhere) · §10-D6
#           (geocoder accepted; the selection is engineering's, recorded) ·
#           BR-MET-071 (premises.area is the EXISTING area link — reused, not
#           duplicated) · CLAUDE.md rule 3 (quantities carry explicit units)
# Tests:    this file
# Impacts:  apps/assets/selectors.py (stock_view · lifecycle_view · geo_view) ·
#           apps/assets/api.py (the three GET routes) · apps/metering
#           (premises lat/lng migration · geocode.py · geo seam reads)
# ───────────────────────────────────────────────────────
"""CR-028 AST-W5 — the three new tabs' backend, tests FIRST (r11 step 2c/2d).

RED-FIRST PROOF: the three central cases below were run against the tree as
W4 left it and their failures quoted in the lane report before any W5 code
landed (`stock_view` did not exist; `Premises` had no `lat` field; the
geocode module was absent).

Time is always PINNED (`today=` / `as_of=`) — nothing here reads a wall
clock, so the overdue/due-in-N boundaries are exact and stable.

The geocode client is tested with a STUBBED transport only: the Census
endpoint is the LIVE path's business (the management command), and no test
in this repo may touch the network.
"""

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    make_asset,
    make_premises,
    make_unit,
    staff_actor,
    tenant_ctx,
)

from apps.assets import selectors, services  # noqa: E402

pytestmark = pytest.mark.django_db

TODAY = date(2026, 8, 16)  # the r10 screenshots' own "today", pinned


def _set_coords(premises_id, lat, lng):
    """Coordinates directly on metering's OWN row — display geography, no
    service accepts them yet (the geocoder and the seed are the two writers)."""
    from apps.metering import models as met_models

    met_models.Premises.objects.filter(pk=premises_id).update(lat=Decimal(lat), lng=Decimal(lng))


@pytest.fixture()
def plant(brazos, dana):
    """A small physical plant: one premises WITH coordinates, one WITHOUT."""
    with tenant_ctx(brazos):
        prem = make_premises(dana, address_line="1408 Bluestem Ln")
        unit = make_unit(dana, prem["id"], label="Unit A")
        dark_prem = make_premises(dana, address_line="9 Nowhere Yet Rd")
        dark_unit = make_unit(dana, dark_prem["id"], label="Unit D")
        _set_coords(prem["id"], "30.245200", "-97.765100")
    return {
        "premises": prem,
        "unit": unit,
        "dark_premises": dark_prem,
        "dark_unit": dark_unit,
    }


# ══════════════════════════════════════════════════════════════════════════
# T1 · GET /assets/stock — Inventory: counts & costs ONLY (§10-D5)
# ══════════════════════════════════════════════════════════════════════════


@pytest.fixture()
def stock(brazos, dana, plant):
    """The Inventory world: three costed uninstalled assets (one AGED), one
    costless cart in stock, and one INSTALLED meter that must never count."""
    with tenant_ctx(brazos):
        make_asset(
            dana,
            asset_no="W-5100",
            service="water",
            unit="kgal",
            purchase_cost="164.00",
            purchase_date="2025-03-10",  # AGED: > 12 months before 2026-08-16
            supplier="Badger Meter",
            expected_life_years=15,
        )
        make_asset(
            dana,
            asset_no="W-5101",
            service="water",
            unit="kgal",
            purchase_cost="171.00",
            purchase_date="2026-07-15",  # the LATEST purchase = the price shown
            supplier="Neptune",
            expected_life_years=15,
        )
        make_asset(
            dana,
            asset_no="BF-0002",
            type="backflow",
            purchase_cost="247.00",
            purchase_date="2026-06-02",
            supplier="Watts Water",
        )
        # A cart in stock with NO recorded cost: counted, never priced.
        make_asset(dana, asset_no="CART-0099", type="container_cart")
        # An INSTALLED meter with a cost — in service, NOT stock.
        make_asset(
            dana,
            asset_no="M-4021",
            service="electric",
            unit="kWh",
            purchase_cost="164.00",
            unit_id=plant["unit"]["id"],
            install_date="2024-03-12",
        )
    return brazos


def test_w5_t1__stock_aggregates_the_uninstalled_by_type(stock):
    """RED-FIRST CASE 1 (quoted in the lane report):
    `AttributeError: module 'apps.assets.selectors' has no attribute
    'stock_view'` before this lane's backend landed."""
    with tenant_ctx(stock):
        view = selectors.stock_view(today=TODAY)
    kpis = view["kpis"]
    # Uninstalled = behavior CLASS `available` (BR-AST-031), NEVER the label:
    # 2 water meters + 1 backflow + 1 cart; the installed M-4021 is absent.
    assert kpis["uninstalled"] == 4
    # $ at cost = SUM of the KNOWN purchase costs, stored 4 dp (rule 2):
    # 164 + 171 + 247. The costless cart adds nothing and fakes nothing.
    assert kpis["value_at_cost"] == "582.0000"
    assert kpis["aged_over_12_months"] == 1  # W-5100, bought 2025-03-10
    assert kpis["currency"] == "USD"

    rows = {row["type"]: row for row in view["rows"]}
    meters = rows["meter"]
    assert meters["count"] == 2
    # Representative unit cost = the LATEST purchase (what restocking costs
    # today); the range rides beside it when costs vary within the type.
    assert meters["unit_cost"] == "171.0000"
    assert meters["unit_cost_min"] == "164.0000"
    assert meters["unit_cost_max"] == "171.0000"
    assert meters["value"] == "335.0000"
    assert sorted(meters["suppliers"]) == ["Badger Meter", "Neptune"]
    # HONEST-EMPTY: the schema records an asset's service only through the
    # service point minted at ASSIGNMENT, so never-assigned stock has no
    # service on record — r10's per-stock-line service tag has no data source
    # (reported in the lane close-out, not invented).
    assert meters["services"] == []
    assert meters["tab"] == "meters"

    cart = rows["container_cart"]
    assert cart["count"] == 1
    # No recorded cost serves NULL — "nobody recorded a cost" must never
    # render as $0.00 (the maintenance_lifetime_cost discipline).
    assert cart["unit_cost"] is None
    assert cart["value"] is None


def test_w5_t1__stock_serves_no_reorder_and_no_van_fact_anywhere(stock):
    """§10-D5 RULED: 'Launch with counts & costs only.' No vans, no reorder
    thresholds, no stock statuses — asserted on the whole serialized payload
    so a future key cannot sneak in under a new name."""
    with tenant_ctx(stock):
        view = selectors.stock_view(today=TODAY)
    payload = json.dumps(view).lower()
    for banned in ("reorder", "van", "yard", "stock_location"):
        assert banned not in payload, f"D5 forbids {banned!r} on the stock payload"
    # And no asset_stock_policies table exists anywhere in the app.
    from django.apps import apps as django_apps

    assert not any(
        model._meta.db_table == "asset_stock_policies" for model in django_apps.get_models()
    ), "OQ-249 parks the parts-stock table; D5 kept it parked"


def test_w5_t1__the_stock_route_is_served(stock):
    from apps.assets import api as assets_api

    response = api_call(  # noqa: F405 — star import from the shared helpers
        assets_api.asset_stock,
        "get",
        user=FakeUser(),  # noqa: F405
        role="system_admin",
        tenant=stock,
    )
    assert response.status_code == 200
    assert response.data["kpis"]["uninstalled"] == 4


# ══════════════════════════════════════════════════════════════════════════
# T2 · GET /assets/lifecycle — three lists + the Asset value panel (D3: no GL)
# ══════════════════════════════════════════════════════════════════════════


@pytest.fixture()
def lifecycle_world(brazos, dana, plant):
    with tenant_ctx(brazos):
        unit_id = plant["unit"]["id"]
        # Backflow, annual test (BR-AST-027 seeds interval 12), OVERDUE:
        # last test 2025-01-18 → due 2026-01-18, 210 days before TODAY.
        make_asset(
            dana,
            asset_no="BF-3301",
            type="backflow",
            unit_id=unit_id,
            install_date="2020-01-18",
            last_test_date="2025-01-18",
            supplier="Watts Water",
            warranty_end="2027-01-31",
            purchase_cost="246.00",
            purchase_date="2020-01-18",
            expected_life_years=12,
        )
        # Backflow, DUE IN 17 DAYS: last test 2025-09-02 → due 2026-09-02.
        make_asset(
            dana,
            asset_no="BF-3318",
            type="backflow",
            last_test_date="2025-09-02",
            supplier="Watts Water",
            warranty_end="2023-06-30",  # expired cover
        )
        # Meter, 96-month recertification (seeded), IN DATE: due 2026-11-12.
        make_asset(
            dana,
            asset_no="M-4310",
            service="electric",
            unit="kWh",
            last_test_date="2018-11-12",
            install_date="2010-06-01",  # 16 yrs+ old — PAST its 15-year life
            purchase_cost="118.00",
            purchase_date="2010-06-01",
            expected_life_years=15,
            supplier="Neptune",
            warranty_end="2032-06-30",
        )
        # Second meter of the same group, young, same supplier + cover.
        make_asset(
            dana,
            asset_no="M-4400",
            service="electric",
            unit="kWh",
            install_date="2024-03-12",
            purchase_cost="164.00",
            purchase_date="2024-03-12",
            expected_life_years=15,
            supplier="Neptune",
            warranty_end="2032-06-30",
        )
        # Device with an EXPLICIT future certification (no interval): SCHEDULED.
        make_asset(
            dana,
            asset_no="PV-1204",
            type="pv",
            test_interval_months=None,
            certification_due="2027-03-04",
        )
    return brazos


def test_w5_t2__certifications_due_derive_status_and_requirement_from_data(
    lifecycle_world,
):
    """RED-FIRST CASE 2 (quoted in the lane report):
    `AttributeError: module 'apps.assets.selectors' has no attribute
    'lifecycle_view'` before this lane's backend landed."""
    with tenant_ctx(lifecycle_world):
        view = selectors.lifecycle_view(today=TODAY)
    certs = view["certifications"]
    # Soonest first.
    assert [row["asset_no"] for row in certs] == [
        "BF-3301",
        "BF-3318",
        "M-4310",
        "PV-1204",
    ]
    by_no = {row["asset_no"]: row for row in certs}

    overdue = by_no["BF-3301"]
    assert overdue["due"] == "2026-01-18"
    assert overdue["status"] == "overdue"
    # Requirement WORDING derives from the DATA (interval 12 → annual test) —
    # never a hardcoded per-asset string.
    assert overdue["requirement"] == {"kind": "annual_test", "interval_months": 12}
    assert overdue["premises"] == "1408 Bluestem Ln"

    due_soon = by_no["BF-3318"]
    assert due_soon["status"] == "due_soon"
    assert due_soon["days_until"] == 17  # r10's own "Due in 17 days"

    in_date = by_no["M-4310"]
    assert in_date["status"] == "in_date"
    # A measuring asset on the seeded 96-month interval is an accuracy
    # recertification (BR-AST-027's own vocabulary), derived, not stored.
    assert in_date["requirement"] == {
        "kind": "accuracy_recertification",
        "interval_months": 96,
    }

    scheduled = by_no["PV-1204"]
    assert scheduled["status"] == "scheduled"  # EXPLICIT future date, no cadence
    assert scheduled["requirement"] == {"kind": "certification", "interval_months": None}


def test_w5_t2__the_due_soon_window_boundaries_are_exact(brazos, dana):
    """30 days inclusive is due_soon; 31 is not; due TODAY is due in 0 days,
    not overdue — the boundary the clerk plans a truck roll by."""
    with tenant_ctx(brazos):
        make_asset(dana, asset_no="BF-A", type="backflow", last_test_date="2025-08-16")
        make_asset(dana, asset_no="BF-B", type="backflow", last_test_date="2025-09-15")
        make_asset(dana, asset_no="BF-C", type="backflow", last_test_date="2025-09-16")
        make_asset(dana, asset_no="BF-D", type="backflow", last_test_date="2025-08-15")
        view = selectors.lifecycle_view(today=TODAY)
    by_no = {row["asset_no"]: row for row in view["certifications"]}
    assert by_no["BF-A"]["status"] == "due_soon"  # due 2026-08-16 = today → 0 days
    assert by_no["BF-A"]["days_until"] == 0
    assert by_no["BF-B"]["status"] == "due_soon"  # due 2026-09-15 → 30 days
    assert by_no["BF-B"]["days_until"] == 30
    assert by_no["BF-C"]["status"] == "in_date"  # due 2026-09-16 → 31 days out
    assert by_no["BF-D"]["status"] == "overdue"  # due 2026-08-15 → yesterday


def test_w5_t2__warranty_groups_by_type_and_supplier(lifecycle_world):
    with tenant_ctx(lifecycle_world):
        view = selectors.lifecycle_view(today=TODAY)
    groups = {(g["type"], g["supplier"]): g for g in view["warranty_groups"]}
    meters = groups[("meter", "Neptune")]
    assert meters["units"] == 2
    assert meters["cover_ends"] == "2032-06-30"
    assert meters["under_warranty"] == 2
    assert meters["status"] == "covered"
    backflows = groups[("backflow", "Watts Water")]
    assert backflows["units"] == 2
    # Cover ends = the LATEST cover in the group; one unit's cover has lapsed.
    assert backflows["cover_ends"] == "2027-01-31"
    assert backflows["under_warranty"] == 1
    assert backflows["status"] == "covered"


def test_w5_t2__age_forecast_counts_past_life_and_prices_the_programme(
    lifecycle_world,
):
    with tenant_ctx(lifecycle_world):
        view = selectors.lifecycle_view(today=TODAY)
    rows = {row["type"]: row for row in view["age_forecast"]["rows"]}
    meters = rows["meter"]
    # M-4310: installed 2010-06-01 → 194 months; M-4400: 2024-03-12 → 29.
    assert meters["avg_age_months"] == 111  # (194 + 29) // 2 = 111 (floor)
    assert meters["expected_life_years"] == 15
    assert meters["past_life"] == 1  # M-4310 is 16 yrs into a 15-yr life
    assert meters["due_within_12mo"] == 1  # the same unit; M-4400 is young
    # Replacement cost = due count × the LATEST unit cost in the group.
    assert meters["replacement_cost"] == "164.0000"
    programme = view["age_forecast"]["programme"]
    assert programme["units"] >= 1
    assert Decimal(programme["cost"]) >= Decimal("164.0000")


def test_w5_t2__asset_value_panel_totals_buy_and_present_value(lifecycle_world):
    with tenant_ctx(lifecycle_world):
        view = selectors.lifecycle_view(today=TODAY)
        # The panel's present value is the SUM of the same asset_book_value
        # the detail serves — computed here independently so drift goes RED.
        expected_present = Decimal("0")
        expected_buy = Decimal("0")
        for asset in selectors.asset_list():  # default set = the non-terminal fleet
            if asset.purchase_cost is not None:
                expected_buy += asset.purchase_cost
            book = selectors.asset_book_value(asset, as_of=TODAY)
            if book is not None:
                expected_present += Decimal(book["book_value"])
    panel = view["asset_value"]
    assert Decimal(panel["buy_value"]) == expected_buy
    assert Decimal(panel["present_value"]) == expected_present
    assert panel["currency"] == "USD"


def test_w5_t2__no_gl_sentence_anywhere_in_the_lifecycle_payload(lifecycle_world):
    """§10-D3 RULED: the r10 'Cost to Finance' sidebar (Depreciation · 'Posts
    to 5300 O&M and 5400 Depreciation' · 'Open Cost & Margin') is OMITTED.
    Asserted over the whole serialized payload AND the selector source."""
    with tenant_ctx(lifecycle_world):
        view = selectors.lifecycle_view(today=TODAY)
    payload = json.dumps(view)
    for banned in ("5300", "5400", "Cost & Margin", "Depreciation Aug"):
        assert banned not in payload
    source = Path(selectors.__file__).read_text(encoding="utf-8")
    assert "5300" not in source.replace("no GL", "")  # comments may say "no GL"
    # Hard rule 5 by absence: nothing in assets imports the ledger app.
    assert "apps.ledger" not in source
    assert "apps.ledger" not in Path(services.__file__).read_text(encoding="utf-8")


def test_w5_t2__the_lifecycle_route_is_served(lifecycle_world):
    from apps.assets import api as assets_api

    response = api_call(  # noqa: F405
        assets_api.asset_lifecycle,
        "get",
        user=FakeUser(),  # noqa: F405
        role="system_admin",
        tenant=lifecycle_world,
    )
    assert response.status_code == 200
    assert "certifications" in response.data
    assert "warranty_groups" in response.data
    assert "age_forecast" in response.data
    assert "asset_value" in response.data


# ══════════════════════════════════════════════════════════════════════════
# T3 · GET /assets/geo — every asset standing on a geocoded premises
# ══════════════════════════════════════════════════════════════════════════


@pytest.fixture()
def geo_world(brazos, dana, plant):
    with tenant_ctx(brazos):
        unit_id = plant["unit"]["id"]
        make_asset(
            dana,
            asset_no="M-MASTER-01",
            service="water",
            unit="kgal",
            meter_type="master",
            unit_id=unit_id,
            install_date="2026-01-05",
        )
        make_asset(
            dana,
            asset_no="SM-7201",
            type="sub_meter",
            service="water",
            unit="kgal",
            parent_asset_no="M-MASTER-01",
            unit_id=unit_id,
            install_date="2026-01-05",
        )
        # On the premises WITHOUT coordinates — must be absent from the map.
        make_asset(
            dana,
            asset_no="M-DARK-01",
            service="electric",
            unit="kWh",
            unit_id=plant["dark_unit"]["id"],
            install_date="2026-01-05",
        )
        # In inventory — no premises, no marker.
        make_asset(dana, asset_no="M-5099X", service="electric", unit="kWh")
    return brazos


def test_w5_t3__geo_serves_only_assets_whose_premises_has_coordinates(geo_world):
    """RED-FIRST CASE 3 (quoted in the lane report): before the migration the
    coordinate write itself failed —
    `django.core.exceptions.FieldDoesNotExist: Premises has no field named
    'lat'` — and `selectors.geo_view` did not exist."""
    with tenant_ctx(geo_world):
        view = selectors.geo_view()
    rows = {row["asset_no"]: row for row in view["assets"]}
    assert set(rows) == {"M-MASTER-01", "SM-7201"}

    master = rows["M-MASTER-01"]
    # NUMERIC(9,6) served as strings — never floats (the money discipline
    # applied to coordinates: the wire carries what the column stores).
    assert master["lat"] == "30.245200"
    assert master["lng"] == "-97.765100"
    assert master["role"] == {"kind": "master", "count": 1}
    assert master["premises"] == "1408 Bluestem Ln"
    assert master["unit"] == "Unit A"
    assert master["service"] == "water"
    assert master["behavior_class"] == "in_service"
    assert master["status_name"]
    # id addresses the popup's "Open details →"; asset_no is what a human reads.
    assert master["id"]

    sub = rows["SM-7201"]
    assert sub["role"] == {"kind": "sub", "parent": "M-MASTER-01"}


def test_w5_t3__geo_payload_carries_no_work_order_fact(geo_world):
    """§10-D7: r10's popup shows `WO-4204` lines; Work is R5, so the payload
    carries NO wo key and NO WO-string anywhere."""
    with tenant_ctx(geo_world):
        view = selectors.geo_view()
    payload = json.dumps(view).lower()
    assert '"wo"' not in payload
    assert "work_order" not in payload


def test_w5_t3__the_geo_route_is_served(geo_world):
    from apps.assets import api as assets_api

    response = api_call(  # noqa: F405
        assets_api.asset_geo,
        "get",
        user=FakeUser(),  # noqa: F405
        role="system_admin",
        tenant=geo_world,
    )
    assert response.status_code == 200
    assert len(response.data["assets"]) == 2


# ══════════════════════════════════════════════════════════════════════════
# T3 · the Census geocoder — STUBBED transport; tests never touch the network
# ══════════════════════════════════════════════════════════════════════════


def _census_payload(lng, lat):
    """The Census one-line endpoint's answer shape (documented, stubbed)."""
    return {
        "result": {
            "addressMatches": [
                {"coordinates": {"x": lng, "y": lat}},
            ]
        }
    }


def test_w5_t3__geocode_address_reads_the_census_match(brazos):
    from apps.metering import geocode

    calls = []

    def transport(url):
        calls.append(url)
        return _census_payload(-76.92744, 38.845985)

    result = geocode.geocode_address(
        "4600 Silver Hill Rd, Washington, DC 20233", transport=transport
    )
    assert result == (Decimal("38.845985"), Decimal("-76.92744"))
    assert len(calls) == 1
    assert "geocoding.geo.census.gov" in calls[0]
    # The address travels URL-encoded, never raw.
    assert " " not in calls[0]


def test_w5_t3__geocode_address_answers_none_on_no_match_and_on_failure(brazos):
    from apps.metering import geocode

    assert (
        geocode.geocode_address(
            "1 Nowhere", transport=lambda url: {"result": {"addressMatches": []}}
        )
        is None
    )

    def broken(url):
        raise OSError("connection refused")

    # A transport failure is a None + a log line — never an exception that
    # kills the whole batch, and NEVER an invented coordinate.
    assert geocode.geocode_address("1 Nowhere", transport=broken) is None


def test_w5_t3__geocode_missing_fills_only_the_blank_rows_and_is_idempotent(brazos, dana):
    from apps.metering import geocode
    from apps.metering import models as met_models

    with tenant_ctx(brazos):
        filled = make_premises(dana, address_line="1 Already Geocoded Way")
        blank = make_premises(dana, address_line="2 Needs Coordinates Ct")
        make_premises(dana, address_line="3 Unmatchable Pl")  # the named failure
        _set_coords(filled["id"], "30.100000", "-97.100000")

        def transport(url):
            if "Unmatchable" in url or "Unmatchable" in url.replace("+", " "):
                return {"result": {"addressMatches": []}}
            return _census_payload(-97.765100, 30.245200)

        summary = geocode.geocode_missing(transport=transport)
        assert summary["filled"] == 1
        # The failure is reported BY NAME, never silently skipped.
        assert summary["failed"] == ["3 Unmatchable Pl"]

        row = met_models.Premises.objects.get(pk=blank["id"])
        assert row.lat == Decimal("30.245200")
        assert row.lng == Decimal("-97.765100")
        # A set value is NEVER overwritten — the already-geocoded row kept its
        # coordinates even though the stub would have answered differently.
        kept = met_models.Premises.objects.get(pk=filled["id"])
        assert kept.lat == Decimal("30.100000")

        # Idempotent: a second run re-asks ONLY for the still-blank failure.
        calls = []

        def counting(url):
            calls.append(url)
            return {"result": {"addressMatches": []}}

        second = geocode.geocode_missing(transport=counting)
        assert second["filled"] == 0
        assert len(calls) == 1  # only "3 Unmatchable Pl" — never the filled rows


def test_w5_t3__the_command_refuses_off_postgres(brazos):
    """`geocode_premises` is the LIVE path (it talks to the network and writes
    a tenant table) — like load_sample_data it refuses to run where tenant
    context cannot be a Postgres GUC."""
    from django.core.management import call_command
    from django.core.management.base import CommandError
    from django.db import connection

    if connection.vendor == "postgresql":  # pragma: no cover - sqlite suite
        pytest.skip("this half of the guard only exists off postgres")
    with pytest.raises(CommandError):
        call_command("geocode_premises", "--tenant", "brazosbend")


# ══════════════════════════════════════════════════════════════════════════
# T3 · the seeded coordinates — deterministic, no network, never overwriting
# ══════════════════════════════════════════════════════════════════════════


def test_w5_t3__every_fixture_street_has_deterministic_seed_coordinates():
    from apps.metering import sample_data as metering_sample
    from core import sample_fixture as fixture

    for street in fixture.STREETS:
        assert street in metering_sample.STREET_GEO, f"{street} has no seed anchor"
    # And the three r10 area names ride the EXISTING area vocabulary
    # (BR-MET-071) — no second area column was invented (B16 §6's own
    # "reconcile, not duplicate" note, applied to `area`).
    from apps.metering import models as met_models

    field_names = {f.name for f in met_models.Premises._meta.get_fields()}
    assert "lat" in field_names and "lng" in field_names
    assert "geo_area" not in field_names


def test_w5_t3__the_seed_backfill_fills_blanks_and_keeps_set_values(brazos, dana):
    from apps.metering import models as met_models
    from apps.metering import sample_data as metering_sample
    from core import sample_fixture as fixture

    plan_addresses = [entry["address_line"] for entry in fixture.premises_plan()]
    with tenant_ctx(brazos):
        first = make_premises(dana, address_line=plan_addresses[0])
        second = make_premises(dana, address_line=plan_addresses[1])
        # ⚠ **THE PASS SELECTS ON `is_sample` FROM 2026-09-06 (`DEF-MET-4288`).**
        # It used to filter on `premises_plan()`'s 44 addresses, which excluded
        # the three estates added after it — including every one the seeded WORK
        # ORDERS stand on — by construction and in silence. It now asks *is this
        # one of ours*, so a new estate is covered with no edit; `create_premises`
        # takes no such field, so a test that means *the seeder planted this* has
        # to say so the way `sample_data._tag` does.
        met_models.Premises.objects.filter(
            pk__in=[first["id"], second["id"]]
        ).update(is_sample=True)
        _set_coords(first["id"], "1.000000", "2.000000")

        written = metering_sample.apply_premises_geo()
        assert written == 1  # only the blank row gained coordinates

        # And the other half of that fence, asserted here because this is the
        # test that owns the backfill: a REAL address a clerk typed keeps no pin
        # from this pass. It is `manage.py geocode_premises`' job, against the US
        # Census Bureau, and an invented coordinate would send a crew to the
        # wrong street.
        real = make_premises(dana, address_line=plan_addresses[2])
        assert metering_sample.apply_premises_geo() == 0
        assert met_models.Premises.objects.get(pk=real["id"]).lat is None

        kept = met_models.Premises.objects.get(pk=first["id"])
        assert kept.lat == Decimal("1.000000")  # never overwritten
        filled = met_models.Premises.objects.get(pk=second["id"])
        assert filled.lat is not None and filled.lng is not None
        # Austin-area shape, r10's own ballpark — and DETERMINISTIC: a replay
        # writes nothing and computes the same coordinates.
        assert Decimal("30.15") < filled.lat < Decimal("30.35")
        assert Decimal("-97.85") < filled.lng < Decimal("-97.60")
        again = metering_sample.apply_premises_geo()
        assert again == 0
        assert met_models.Premises.objects.get(pk=second["id"]).lat == filled.lat


# ══════════════════════════════════════════════════════════════════════════
# CR-028 debt sweep D10 — tenant isolation of the three W5 tab reads
# ══════════════════════════════════════════════════════════════════════════
#
# stock/lifecycle/geo are AGGREGATES over the whole fleet — precisely the
# query shape that leaks when a filter is forgotten (HR-1). W5 shipped them
# with no isolation probe; this is the suite-pattern probe (the registry's
# tc7 shape): seed both tenants, read as each, assert the other's rows are
# nowhere in the answer — not as a count, not as a supplier, not as a marker.


@pytest.mark.isolation
def test_d10__stock_lifecycle_and_geo_answer_only_the_tenant_in_context(
    brazos, dana, lonestar, erin, plant
):
    import json as _json

    from tests.test_us_met_helpers import make_asset, make_premises, make_unit

    with tenant_ctx(lonestar):
        # Lone Star Ridge is the WATER-ONLY isolation tenant — its premises
        # and unit must declare exactly the service it sells (BR-MET-003).
        foreign_prem = make_premises(
            erin, address_line="9 Foreign Rd", services_available=["water"]
        )
        _set_coords(foreign_prem["id"], "10.000000", "20.000000")
        foreign_unit = make_unit(erin, foreign_prem["id"], label="F1", services=["water"])
        make_asset(
            erin,
            asset_no="LS-9001",
            service="water",
            unit="kgal",
            purchase_cost="999.00",
            purchase_date="2020-01-01",
            supplier="Foreign Supply Co",
            expected_life_years=10,
        )
        make_asset(
            erin,
            asset_no="LS-9002",
            service="water",
            unit="kgal",
            unit_id=foreign_unit["id"],
            install_date="2020-01-01",
        )

    with tenant_ctx(brazos):
        make_asset(
            dana,
            asset_no="W-5100",
            service="water",
            unit="kgal",
            purchase_cost="164.00",
            purchase_date="2026-01-01",
            supplier="Badger Meter",
            expected_life_years=15,
        )
        make_asset(
            dana,
            asset_no="W-5101",
            service="water",
            unit="kgal",
            unit_id=plant["unit"]["id"],
            install_date="2026-01-01",
        )
        stock = selectors.stock_view(today=TODAY)
        life = selectors.lifecycle_view(today=TODAY)
        geo = selectors.geo_view()

    # The counts are brazos's own — the foreign spare must not inflate them.
    assert stock["kpis"]["uninstalled"] == 1
    # And no foreign identifier or supplier reaches ANY corner of any payload.
    blob = _json.dumps([stock, life, geo], default=str)
    for foreign in ("LS-9001", "LS-9002", "Foreign Supply Co", "9 Foreign Rd"):
        assert foreign not in blob, f"{foreign} leaked into a brazos aggregate"
    # The brazos marker set is its own assigned asset on its geocoded premises.
    geo_assets = {row["asset_no"] for row in geo["assets"]}
    assert "W-5101" in geo_assets

    # And the mirror: lonestar's aggregates carry nothing of brazos.
    with tenant_ctx(lonestar):
        mirror = _json.dumps(
            [
                selectors.stock_view(today=TODAY),
                selectors.lifecycle_view(today=TODAY),
                selectors.geo_view(),
            ],
            default=str,
        )
    for own in ("W-5100", "W-5101", "Badger Meter"):
        assert own not in mirror, f"{own} leaked into a lonestar aggregate"
