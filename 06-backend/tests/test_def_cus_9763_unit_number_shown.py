# ── Trace ──────────────────────────────────────────────
# Change:   CR-171-BRC10 · lane MVI-POLISH
# Defect:   DEF-CUS-9763 — the move-in list and details view named a unit by
#           its label alone (`Suite 200`) where images 01 and 03–17 draw the
#           unit number with it (`SCW-U-311 · Unit 4A`)
# Tests:    this file
# ───────────────────────────────────────────────────────
"""**A move-in names its unit by number and label, on the list and the view.**

RED-FIRST (law 7), on the base before the fix (381948c90): the list case
failed with ``assert '40 Kestrel Park · Unit 4A' == '40 Kestrel P...101 · Unit
4A'`` and the detail case with ``assert '41 Kestrel Park · Unit 4A' == '41
Kestrel P...101 · Unit 4A'`` — the unit number absent from both lines.

⚠ **WHAT WOULD MAKE THESE PASS WRONGLY:** a cell holding the number and NOT
the label would pass a number-only check, so both parts are asserted, in
order; and a fixture unit with no number would make the composition vacuous,
so the unit's own `unit_no` is asserted non-empty first.
"""

from datetime import date

import pytest

from apps.customers import move_record_reads

from tests.test_cr171_p1_04_move_ins_list import (  # noqa: F401 — shared fixtures
    _committed,
    _request,
    _rows,
    _unit,
)
from tests.test_us_met_reads_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_reads_helpers import brazos, dana, tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db


def test_the_list_unit_cell_carries_the_number_then_the_label(brazos, dana):
    with tenant_ctx(brazos):
        unit = _unit(dana, brazos, "Unit 4A")
        assert unit["unit_no"], "the fixture unit has no number, so the case proves nothing"
        _account, record = _committed(dana, unit, name="Asha Verma", on=date(2026, 10, 1))
        rows = _rows()["rows"]
    row = next(r for r in rows if r.get("move_no") == record["move_no"])
    assert row["unit"] == f"40 Kestrel Park · {unit['unit_no']} · Unit 4A"


def test_the_details_view_names_the_unit_by_number_and_label(brazos, dana):
    with tenant_ctx(brazos):
        unit = _unit(dana, brazos, "Unit 4A", address="41 Kestrel Park")
        request = _request(dana, unit, name="Owen Pratt")
        view = move_record_reads.record_detail(request.request_no)
    assert view["address_line"] == f"41 Kestrel Park · {unit['unit_no']} · Unit 4A"
    assert view["tiles"]["unit"]["unit_no"] == unit["unit_no"]
    cell = view["facts"]["request"]["unit"]
    assert (cell["unit_no"], cell["label"]) == (unit["unit_no"], "Unit 4A")
