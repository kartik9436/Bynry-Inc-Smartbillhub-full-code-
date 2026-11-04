# ── Trace ──────────────────────────────────────────────
# Defects:  DEF-BIL-8160 (continuity judged from one page of past runs,
#           abandoned runs counted) · DEF-BIL-8204 (its duplicate: the first
#           50 runs of the WHOLE TENANT, cancelled runs not skipped)
# Code:     apps/billing/run_scope.py _check_continuity
# Plan:     15-bulk-bill-run-build-plan.md B2
# ───────────────────────────────────────────────────────
"""Continuity is judged against THIS CYCLE's real last run, whatever else the
tenant has run since.

The old screen worked continuity out in the browser from `GET /billing/runs`'
first page: fifty rows, newest period first, ACROSS EVERY CYCLE. So the failure
was never "a cycle has more than fifty runs" — the newest fifty of one cycle
still include its newest run — it was ANOTHER cycle's newer runs filling the
page, and this cycle's last run falling off it. `test_bulk_run_scope.py`'s
sixty-run cases seed one cycle only, so they cannot tell the old read from
the new one; this case can.

The world: cycle A last ran for May 2026. Cycle B has sixty one-day runs from
2 May to 30 June 2026, every one of them a newer period than A's. A clerk
scopes A for July. The truth is a gap — June was never billed on A — and the
old page, holding only B's newest fifty, saw no previous run on A at all and
warned of nothing.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from apps.billing import models as billing_models
from tests.test_bulk_run_scope import a_cycle, a_published_template, a_run, check, warning
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import brazos, tenant_ctx  # noqa: F401
from tests.test_us_ten_helpers import (  # noqa: F401
    brazosbend_payload,
    provisioned_tenant,
)

pytestmark = pytest.mark.django_db

MAY = (date(2026, 5, 1), date(2026, 5, 31))


def test_another_cycles_newer_runs_do_not_hide_this_cycles_last_run(brazos):
    with tenant_ctx(brazos):
        cycle_a = a_cycle(brazos, code="SC-A")
        cycle_b = a_cycle(brazos, code="SC-B")
        may = a_run(brazos, cycle_a, *MAY, run_no="RUN-A-0005")
        first_b = date(2026, 5, 2)
        for offset in range(60):
            day = first_b + timedelta(days=offset)
            a_run(brazos, cycle_b, day, day, run_no=f"RUN-B-{offset + 1:04d}")
        # The old read's page: the tenant's newest fifty periods. A is not on it.
        page = list(
            billing_models.BillRun.objects.order_by("-period_start", "-created_at", "-id")[:50]
        )
        assert may not in page
        result = check(
            cycle_a,
            a_published_template(),
            period_start="2026-07-01",
            period_end="2026-07-31",
            bill_date="2026-08-01",
        )
    assert result.previous_run["run_id"] == str(may.pk)
    assert result.continuity["state"] == "gap"
    assert warning(result, "period_gap").params == {
        "from": "2026-06-01",
        "to": "2026-06-30",
        "days": 30,
    }
    assert "first_run" not in result.codes()
