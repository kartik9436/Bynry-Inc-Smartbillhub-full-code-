# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-013 TC-17 (catch-up problems on their rows) · US-BIL-014
#           Screens: S30 (the one-time bill, step 1)
# Defect:   DEF-BIL-8322 — overlapping or out-of-order periods were refused with
#           no field and no key (PO report on 2.411.4)
# ───────────────────────────────────────────────────────
"""Two periods that share a day are named on the row that overlaps; order is not a problem.

The PO's own case: a penalty with periods **Sep 30 – Sep 30** and **Aug 30 – Sep
30**. They overlap on Sep 30 and were typed out of date order. Before the fix
the engine refused with a bare sentence and the clerk saw the frame's generic
line. Now step 1 names it — on the From of the row that starts inside the one
before it — and periods typed in any order are taken in date order.
"""

from __future__ import annotations

import pytest

from apps.billing import one_time_answer
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db


def _penalty(*periods):
    return {
        "account_id": "a",
        "kind": "backbill",
        "sub_periods": [{"period_start": s, "period_end": e} for s, e in periods],
        "reason_code": "MISSED",
        "bill_date": "2026-09-30",
        "due_days": 2,
    }


def _overlaps(problems):
    return [p for p in problems if p["message_key"] == "billing.oneTime.err.periodOverlaps"]


def test_def_bil_8322__the_pos_overlapping_pair_is_named_on_the_later_row(brazos):
    with tenant_ctx(brazos):
        problems = one_time_answer.problems_in(
            _penalty(("2026-09-30", "2026-09-30"), ("2026-08-30", "2026-09-30"))
        )
    overlaps = _overlaps(problems)
    assert [p["field"] for p in overlaps] == ["sub_periods[0].period_start"], problems


def test_def_bil_8322__periods_typed_out_of_order_are_not_a_problem_and_are_priced_in_order(brazos):
    payload = _penalty(("2026-09-01", "2026-09-30"), ("2026-08-01", "2026-08-31"))
    with tenant_ctx(brazos):
        assert _overlaps(one_time_answer.problems_in(payload)) == []
        request = one_time_answer.request_from(payload)
    assert [start.isoformat() for start, _ in request.sub_periods] == ["2026-08-01", "2026-09-01"]
