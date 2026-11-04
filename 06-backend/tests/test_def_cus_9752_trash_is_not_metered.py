# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-CUS-9752 — the move-in Unit step labelled Trash "Metered" for
#           a unit whose only trash asset is a 96-gallon cart (M1, TR-M1-1).
# ───────────────────────────────────────────────────────
"""A service is *Metered* on step 1 only when a READ device stands on it.

The fact is the asset type's category (meter or sub-meter) — the same fact
`needs_opening_read` already reads on each row — never "any asset at all".
"""

import pytest

from apps.customers import move_in_unit_read

from tests.test_cr171_p1_04_move_ins_list import _unit
from tests.test_def_cus_9753_only_read_devices_owe_a_read import _cart, _enable_trash
from tests.test_us_met_reads_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_reads_helpers import brazos, dana, seed_config, tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db


def test_a_cart_does_not_make_trash_metered_and_a_meter_still_does(brazos, dana):
    with tenant_ctx(brazos):
        seed_config()
        _enable_trash(dana)
        unit = _unit(
            dana, brazos, "DEF-9752",
            meters=(("E-9752", "electric", "kWh"),),
            services=("electric", "trash"),
        )
        _cart(dana, unit["id"], "TR-9752")
        table = move_in_unit_read.services_and_meters(unit["id"])
    by_service = {row["service"]: row for row in table["services"]}
    assert [m["asset_no"] for m in by_service["trash"]["meters"]] == ["TR-9752"]
    assert by_service["trash"]["metered"] is False
    assert by_service["electric"]["metered"] is True
