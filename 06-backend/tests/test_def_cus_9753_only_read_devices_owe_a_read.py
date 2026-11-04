# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-CUS-9753 — a trash cart (fire line, PV array) counted as an
#           unread METER, so a move-in stayed *Waiting on a read* for ever and
#           a route counted every cart among its *meters short*.
# Rules:    BR-AST-004 (the asset type's category: meters | sub_meters |
#           behind_the_meter) · DEF-CUS-9726 (the opening read is the FIRST
#           read on or after the move-in date — must still hold)
# CR:       CR-171-BRC10 P4.02, M1 (MVI-26-0008, TR-M1-1)
# ───────────────────────────────────────────────────────
"""Only a device that is READ owes a read.

The fact is the asset TYPE's category (`assets.selectors.READ_DEVICE_CATEGORIES`
— meters and sub-meters), never the service's name: a tenant may add a type of
its own (BR-TEN-036), and a cart is a cart because its type says so.

⚠ WHAT WOULD MAKE THESE PASS WRONGLY (law 7, habit 2): a unit with no meter at
all (the chip would say *no meters*, not *completed*), or a meter left unread
(the chip would rightly wait). So the unit carries two meters AND a cart, both
meters are read on the move-in day, and the cart is the only thing unread.
"""

from datetime import date, timedelta

import pytest

from apps.assets import services as asset_services
from apps.customers import move_in_list, move_record_reads
from apps.metering import completeness
from apps.metering import selectors as metering_selectors

from tests.test_cr171_p1_04_move_ins_list import TODAY, _asset_id, _committed, _rows, _unit
from tests.test_us_met_reads_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_reads_helpers import brazos, commit_read, dana, seed_config, tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db


def _cart(actor, unit_id, asset_no):
    return asset_services.create_asset(
        actor,
        {
            "type": "container_cart",
            "asset_no": asset_no,
            "service": "trash",
            "unit_id": str(unit_id),
            "install_date": "2026-01-05",
        },
    )


def _enable_trash(actor):
    from apps.tenancy import services as tenancy_services

    tenancy_services.update_tenant_service(actor, "trash", {"enabled": True})


def _move_in_with_a_cart(actor, tenant, *, read_both=True):
    seed_config()
    _enable_trash(actor)
    unit = _unit(
        actor, tenant, "DEF-9753",
        meters=(("E-9753", "electric", "kWh"), ("W-9753", "water", "kgal")),
        services=("electric", "water", "trash"),
    )
    _cart(actor, unit["id"], "TR-9753")
    on = TODAY - timedelta(days=2)
    reads = (("E-9753", "4300"), ("W-9753", "315")) if read_both else (("W-9753", "315"),)
    _account, record = _committed(actor, unit, name="Collins, Avery", on=on, reads=reads)
    return unit, on, record


def test_a_cart_owes_no_opening_read_and_the_move_in_completes(brazos, dana):
    with tenant_ctx(brazos):
        _unit_row, _on, record = _move_in_with_a_cart(dana, brazos)
        page = move_record_reads.record_detail(record["move_no"])
        registers = [row["register"].split(" · ")[0] for row in page["opening_reads"]["rows"]]
        assert "TR-9753" not in registers, registers
        assert page["tiles"]["opening_reads"]["taken"] == page["tiles"]["opening_reads"]["of"] == 2
        assert not [row for row in page["still_open"] if row["kind"] == "opening_read"]
        assert page["status"] == move_in_list.STATUS_COMPLETED
        row = next(r for r in _rows()["rows"] if r["reference"] == record["move_no"])
        assert row["status"] == move_in_list.STATUS_COMPLETED


def test_an_unread_meter_beside_the_cart_still_waits(brazos, dana):
    # The half that is the deliverable: DEF-CUS-9726's rule still bites.
    with tenant_ctx(brazos):
        _unit_row, _on, record = _move_in_with_a_cart(dana, brazos, read_both=False)
        page = move_record_reads.record_detail(record["move_no"])
        assert page["status"] == move_in_list.STATUS_WAITING_ON_A_READ
        still = [row["register"] for row in page["still_open"] if row["kind"] == "opening_read"]
        assert still == ["E-9753"]


def test_a_read_before_the_move_in_is_still_not_the_opening_read(brazos, dana):
    # DEF-CUS-9726 unchanged: the previous occupant's read does not count.
    with tenant_ctx(brazos):
        unit, on, record = _move_in_with_a_cart(dana, brazos, read_both=False)
        commit_read(dana, _asset_id(unit, "E-9753"), day=(on - timedelta(days=3)).isoformat(), value="4100")
        page = move_record_reads.record_detail(record["move_no"])
        assert page["status"] == move_in_list.STATUS_WAITING_ON_A_READ


def test_the_cycle_expects_no_read_from_a_cart(brazos, dana):
    from tests.test_def_1813_unmetered_count import _world

    with tenant_ctx(brazos):
        cycle, _unit_row, _account, carts = _world(dana, brazos, cycle_code="C9753", carts=3)
        assert len(carts) == 3
        expected = completeness._expected_meters(cycle.id, date(2026, 8, 31))
        assert [m.asset_no for m in expected] == []


def test_the_route_meter_picker_lists_no_cart(brazos, dana):
    with tenant_ctx(brazos):
        unit, _on, _record = _move_in_with_a_cart(dana, brazos)
        answer = metering_selectors.reads_for_unit(unit["id"])
        assert sorted(m["asset_no"] for m in answer["meters"]) == ["E-9753", "W-9753"]
        dates = metering_selectors.latest_read_dates_for_units([str(unit["id"])])
        assert sorted(m["asset_no"] for m in dates[str(unit["id"])]["meters"]) == ["E-9753", "W-9753"]
