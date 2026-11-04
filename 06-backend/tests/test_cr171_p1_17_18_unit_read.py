# ── Trace ──────────────────────────────────────────────
# Change:   CR-171-BRC10 (move-in redesign) · lane MVI-FLOW · P1.17 · P1.18
# Rules:    image 30 / 31 / 32 · BR-CUS-1101 · BR-MET-036 · BR-AST-003 ·
#           CLAUDE.md hard rules 3 · 8
# Tests:    this file
# ───────────────────────────────────────────────────────
"""**Step 1's two reads — the unit card and the Services and meters table.**

RED-FIRST (law 7): written before `move_in_unit_read` existed; first run
`ImportError: cannot import name 'move_in_unit_read'`.

⚠ **WHAT WOULD MAKE THESE PASS WRONGLY** (law 7, habit 2):

  * **A nested table that passes because it is flat.** The meter case asserts
    the sub-meter is a CHILD of its meter and NOT a top-level row.
  * **A last read that is the usage, not the dial.** The read asserted is the
    committed index (1,024) with its unit, never a consumption figure.
  * **A first-occupant flag that passes because the unit is empty.** The
    history case closes a real tenancy and asserts it is named as previous.
"""

from datetime import date

import pytest
from django.urls import resolve

from apps.customers import move_in_flow_api, move_in_unit_read, moves
from apps.customers import services as customers_services

from tests import identity_fixtures
from tests.test_us_met_reads_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_reads_helpers import (  # noqa: F401
    a_meter,
    commit_read,
    make_premises,
    make_unit,
    seed_config,
    tenant_ctx,
)
from tests.move_out_draft_isolation import billable_unit
from tests.test_w9_event_reads import _account_on, _plan

pytestmark = pytest.mark.django_db


def _water_unit(actor, tenant):
    from apps.assets import services as asset_services
    from apps.metering import services as metering_services

    premises = make_premises(actor, services_available=["water", "electric"])
    unit = make_unit(actor, premises["id"], label="Unit 3B", services=["water", "electric"])
    metering_services.assign_unit_plan(actor, unit["id"], {"tariff_id": str(_plan(tenant, "water").id)})
    meter = a_meter(actor, "W-5000", unit_id=unit["id"], service="water", uom="kgal", register_digits=6)
    asset_services.create_asset(
        actor,
        {
            "type": "sub_meter",
            "asset_no": "W-5000-S1",
            "service": "water",
            "unit": "kgal",
            "read_method": "manual",
            "parent_asset_no": "W-5000",
            "unit_id": unit["id"],
            "install_date": "2026-01-05",
            "status": "active",
            "register_digits": 5,
        },
    )
    return premises, unit, meter


def test_the_routes_resolve_through_the_root_urlconf():
    uid = "0190a1b2-0000-7000-8000-000000000001"
    assert resolve(f"/api/brazos/units/{uid}/move-in-facts").func is move_in_flow_api.unit_move_in_facts
    assert resolve(f"/api/brazos/units/{uid}/move-in-meters").func is move_in_flow_api.unit_move_in_meters
    assert (
        resolve(f"/api/brazos/units/{uid}/move-in-meters/check").func
        is move_in_flow_api.unit_move_in_meters_check
    )


def test_the_unit_card_reads_building_unit_owner_and_history(brazos, dana):
    with tenant_ctx(brazos):
        seed_config()
        premises, unit, _meter = _water_unit(dana, brazos)
        facts = move_in_unit_read.unit_facts(unit["id"])
    assert facts["unit"]["unit_no"] == unit["unit_no"]
    assert facts["unit"]["occupancy"] == "vacant"
    # Hard rule 8 — the address is the premises', walked to.
    assert facts["unit"]["address"]["line1"] == premises["address_line"]
    assert facts["building"]["premise_no"] == premises["premise_no"]
    assert set(facts["building"]) >= {
        "premises_type",
        "inside_city_limits",
        "area_code",
        "parcel",
        "parcel_verified",
        "routes",
    }
    assert facts["history"]["first_occupant"] is True
    assert facts["history"]["previous"] is None
    # One assignment, no change — 0, and the key is never absent.
    assert facts["history"]["plan_changes"] == 0


def test_history_names_the_previous_tenancy(brazos, dana):
    with tenant_ctx(brazos):
        seed_config()
        _premises, unit, meter = _water_unit(dana, brazos)
        # DEF-CUS-10127 — the move-out below drafts the final bill or refuses
        # (DEF-CUS-10093, 2.574.0): the unit needs a cycle, a price in force
        # and the water meter read on the move day.
        billable_unit(dana, brazos, unit["id"], services=("water",), uoms={"water": "kgal"})
        commit_read(
            dana, meter["id"], day="2026-08-19", value="1024", prior_value="1012",
            consumption="12.000000", unit="kgal",
        )
        from apps.assets import models as asset_models

        sub = asset_models.Asset.objects.get(tenant=brazos, asset_no="W-5000-S1")
        commit_read(
            dana, sub.id, day="2026-08-19", value="512", prior_value="508",
            consumption="4.000000", unit="kgal",
        )
        gone = _account_on(dana, unit["id"], name="Duarte, Rui")
        closed = customers_services.move_out(dana, gone["id"], {"moved_out_on": "2026-08-19"})
        # The refusal is not weakened: billing really drafted the final bill.
        assert closed["final_bill"]["outcome"] == "drafted", closed["final_bill"]
        facts = move_in_unit_read.unit_facts(unit["id"])
    assert facts["history"]["first_occupant"] is False
    assert facts["history"]["previous"]["account_no"] == gone["account_no"]
    assert facts["history"]["previous"]["closed_at"] == "2026-08-19"


def test_services_and_meters_nests_the_sub_meter_and_reads_the_dial(brazos, dana):
    with tenant_ctx(brazos):
        seed_config()
        _premises, unit, meter = _water_unit(dana, brazos)
        commit_read(dana, meter["id"], day="2026-10-04", value="1024", unit="kgal")
        table = move_in_unit_read.services_and_meters(unit["id"])

    by_service = {row["service"]: row for row in table["services"]}
    assert set(by_service) == {"water", "electric"}
    assert all(row["start"] is True for row in table["services"])
    water = by_service["water"]
    assert water["metered"] is True
    assert [m["asset_no"] for m in water["meters"]] == ["W-5000"]  # the sub-meter is NOT top level
    top = water["meters"][0]
    assert top["kind"] == "meter"
    assert top["reads_as"] == {"multiplier": "1.000000", "digits": 6}
    assert top["last_read"]["unit"] == "kgal"
    assert top["last_read"]["read_at"].startswith("2026-10-04")
    assert float(top["last_read"]["value"]) == 1024
    assert [c["asset_no"] for c in top["children"]] == ["W-5000-S1"]
    assert top["children"][0]["kind"] == "sub_meter"
    assert top["children"][0]["last_read"] is None  # never a zero
    # A service with a point and no meter is UNMETERED, never dropped.
    assert by_service["electric"]["metered"] is False and by_service["electric"]["meters"] == []
    assert table["counts"] == {
        "services": 2,
        "meters": 2,
        "devices": 0,
        "opening_reads_needed": 2,
    }


def test_below_the_last_read_is_answered_per_row_before_complete(brazos, dana):
    with tenant_ctx(brazos):
        seed_config()
        _premises, unit, meter = _water_unit(dana, brazos)
        commit_read(dana, meter["id"], day="2026-10-04", value="1024", unit="kgal")
        answer = move_in_unit_read.check_opening_reads(
            unit["id"],
            [
                {"meter_no": "W-5000", "value": "1000"},
                {"meter_no": "W-5000", "value": "1031"},
                {"meter_no": "W-5000-S1", "value": "214"},
                {"meter_no": "W-5000", "value": "abc"},
            ],
        )
    rows = answer["rows"]
    assert [r["below_last_read"] for r in rows] == [True, False, None, None]
    assert rows[0]["unit"] == "kgal"
