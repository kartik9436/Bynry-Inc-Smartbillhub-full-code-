# ── Trace ──────────────────────────────────────────────
# Defects: DEF-MET-9773 (a sub-meter of a different size from its main meter
#          made the connection's size unresolved, so the account could not be
#          priced — CR-171-BRC10 matrix case M2, Rosa Delgado, 300 Willow Court
#          Apt 2B: main W-M2 3/4" `W-34`, irrigation sub-meter SW-M2 5/8" `W-58`)
# Rules:   BR-AST-500 (the asset carries the connection's size class) ·
#          BR-AST-003 (a sub-meter or device hangs off a meter) ·
#          decision log 2026-08-27 (two METERS disagreeing answer None) ·
#          decision log 2026-10-06 (DEF-MET-9773 — the main meter sizes the
#          connection; what hangs under it on the same connection does not)
# Tests:   this file
# ───────────────────────────────────────────────────────
"""The connection's size is the MAIN meter's — a sub-meter under it is not a
second claim on it.

Rosa's water is priced at the 3/4-inch size of her main meter. Her 5/8-inch
irrigation sub-meter stands UNDER that meter on the same connection
(BR-AST-003), and it measures part of what the main meter already measures; it
is not a second connection and it does not say how big the connection is. Until
2.549.x `connection_size_for` read a size off every asset on the point, saw
`W-34` and `W-58`, called that a disagreement and answered None — so her first
bill refused *"This connection's size is not recorded"* although both sizes
were recorded.

What did NOT move, and each has a case below:
  * two MAIN meters on one connection with two different sizes still answer
    None, and the bill still refuses by name (decision log 2026-08-27);
  * a sub-meter whose parent stands on ANOTHER unit — an apartment submetered
    off the building's master — is the top of ITS unit's connection, so its own
    size still prices that unit.
"""

from __future__ import annotations

import pytest

from apps.assets import services as asset_services
from apps.billing import gather
from apps.metering import selectors as metering_selectors

from tests.test_def_438_parity import _account_on, _water_plan
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import make_unit, tenant_ctx

pytestmark = pytest.mark.django_db

WATER_3_4 = "W-34"
WATER_5_8 = "W-58"
WATER_2_INCH = "W-2"


def _sub_meter(actor, *, asset_no, parent_no, unit_id, size_class):
    return asset_services.create_asset(
        actor,
        {
            "type": "sub_meter",
            "asset_no": asset_no,
            "service": "water",
            "unit": "kgal",
            "read_method": "manual",
            "multiplier": "1",
            "parent_asset_no": parent_no,
            "unit_id": unit_id,
            "install_date": "2026-01-05",
            "status": "active",
            "size_class": size_class,
        },
    )


def test_a_differently_sized_sub_meter_does_not_unresolve_its_main_meters_size(
    brazos, dana
):
    """M2's shape: main 3/4" (`W-34`), irrigation sub-meter 5/8" (`W-58`)
    under it on the same connection. The connection is 3/4"."""
    with tenant_ctx(brazos):
        plan = _water_plan(brazos)
        account, unit, main, _delta = _account_on(brazos, dana, plan, size_class=WATER_3_4)
        sub = _sub_meter(
            dana,
            asset_no="SW-9001",
            parent_no=main["asset_no"],
            unit_id=unit["id"],
            size_class=WATER_5_8,
        )
        assert sub["size_class"] == WATER_5_8
        # Fixture sanity: the sub-meter IS on the same connection, or this case
        # would pass without exercising the fix.
        point = metering_selectors._service_point_for(account.unit_id, "water")
        on_point = {str(a) for a in metering_selectors.seams.asset_ids_for_service_point(point.id)}
        assert {main["id"], sub["id"]} <= on_point

        assert metering_selectors.connection_size_for(account.unit_id, "water") == WATER_3_4
        # The identical answer through billing's own resolver — the hop the bill
        # run, the first-bill preview and the move-in's Billing step all take.
        assert gather._connection_size_for(account.unit_id, "water") == WATER_3_4
        # The bulk Check's inline size fix writes to the SAME set the size is
        # read from — the main meter, never the sub-meter's own recorded 5/8".
        assert metering_selectors.connection_asset_ids_for(account.unit_id, "water") == [
            main["id"]
        ]


def test_an_unsized_main_is_still_unresolved_even_when_its_sub_meter_has_a_size(
    brazos, dana
):
    """The sub-meter does not stand in for a main meter nobody sized: the
    connection's size is unrecorded, and the meter named is the MAIN one."""
    with tenant_ctx(brazos):
        plan = _water_plan(brazos)
        account, unit, main, _delta = _account_on(brazos, dana, plan, size_class=None)
        _sub_meter(
            dana,
            asset_no="SW-9001",
            parent_no=main["asset_no"],
            unit_id=unit["id"],
            size_class=WATER_5_8,
        )
        assert metering_selectors.connection_size_for(account.unit_id, "water") is None
        assert metering_selectors.unsized_meters_for(account.unit_id, "water") == [
            main["asset_no"]
        ]


def test_two_main_meters_that_disagree_still_answer_None(brazos, dana):
    """The 2026-08-27 refusal is kept: two METERS on one connection with two
    different sizes is a data error a human must settle."""
    with tenant_ctx(brazos):
        plan = _water_plan(brazos)
        account, unit, _main, _delta = _account_on(brazos, dana, plan, size_class=WATER_3_4)
        asset_services.create_asset(
            dana,
            {
                "type": "meter",
                "asset_no": "M-9002",
                "service": "water",
                "unit": "kgal",
                "read_method": "manual",
                "multiplier": "1",
                "unit_id": unit["id"],
                "install_date": "2026-01-05",
                "status": "active",
                "size_class": WATER_2_INCH,
            },
        )
        assert metering_selectors.connection_size_for(account.unit_id, "water") is None
        assert gather._connection_size_for(account.unit_id, "water") is None


def test_a_sub_meter_whose_parent_is_on_another_unit_sizes_its_own_unit(brazos, dana):
    """An apartment submetered off the building's master meter: on the
    apartment's connection the sub-meter is the top, so its size is the
    apartment's size. Excluding every sub-meter would have unpriced it."""
    with tenant_ctx(brazos):
        plan = _water_plan(brazos)
        account, unit, main, _delta = _account_on(brazos, dana, plan, size_class=WATER_3_4)
        apartment = make_unit(dana, unit["premises_id"], label="Unit B", services=["water"])
        _sub_meter(
            dana,
            asset_no="SW-9002",
            parent_no=main["asset_no"],
            unit_id=apartment["id"],
            size_class=WATER_5_8,
        )
        assert metering_selectors.connection_size_for(apartment["id"], "water") == WATER_5_8
        assert metering_selectors.connection_size_for(account.unit_id, "water") == WATER_3_4
