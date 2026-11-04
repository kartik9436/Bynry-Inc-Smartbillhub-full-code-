# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-MET-10588 — two read windows for one cycle (MQ-033, PO
#           2026-10-24, decision log "MQ-033 read formats: SUMMARY CONFIRMED",
#           task (9) "route assignment + one read window").
# Rules:    OQ-340 (the first run anchors; `effective_start_day` served) ·
#           B17 §2 ("start day + N days IS the read window") · BR-MET-016's
#           duplicate clause and BR-MET-057's window (both read
#           `_cycle_window_for` / `window_for_period`)
# Tests:    this file
# ───────────────────────────────────────────────────────
"""One cycle, one read window, on every surface — with Brookfield's figure.

`CY-001`: stored start day **10**, first run on the **14th**, **5** days to
complete. Settings printed **14–18**; Reads printed **10/10–10/14** off the
stored day. Every derivation below must answer 14 Oct … 18 Oct.
"""

from __future__ import annotations

from datetime import date, datetime, timezone as dt_timezone

import pytest

from apps.metering import completeness, period_engine, selectors, services
from apps.metering import models as metering_models

from tests.test_us_met_reads_helpers import *  # noqa: F401,F403
from tests.test_us_met_reads_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

ANCHOR = date(2026, 10, 20)
WINDOW = (date(2026, 10, 14), date(2026, 10, 18))


@pytest.fixture()
def cy001(brazos, dana):
    with tenant_ctx(brazos):
        made = services.create_cycle(
            dana, {"code": "CY-001", "name": "Cycle 1", "frequency": "monthly"}
        )
        # The stored day and the first run disagree — OQ-340 lets a human save
        # that; written straight to the row so no wizard default moves it.
        metering_models.Cycle.objects.filter(pk=made["id"]).update(
            start_day=10, days_to_complete=5, first_run_date=date(2026, 10, 14)
        )
        return metering_models.Cycle.objects.get(pk=made["id"])


def test_the_engine_answers_the_effective_window(cy001):
    assert period_engine.cycle_read_window(cy001, ANCHOR) == WINDOW


def test_the_read_check_uses_the_same_window(brazos, cy001):
    """BR-MET-016's duplicate clause and the staging context read this one."""
    read_at = datetime(2026, 10, 20, 9, 0, tzinfo=dt_timezone.utc)
    with tenant_ctx(brazos):
        assert services._cycle_window_for(cy001, read_at) == WINDOW


def test_the_chase_list_period_uses_the_same_window(brazos, cy001):
    with tenant_ctx(brazos):
        assert completeness.window_for_period(cy001, ANCHOR) == WINDOW


def test_the_reads_cycle_row_prints_what_settings_prints(brazos, cy001):
    """The Reads cycle list and page read `window_start`/`window_end`; Settings
    reads `effective_start_day`. They now describe one window."""
    with tenant_ctx(brazos):
        row = selectors.cycle_dict(cy001, as_of=ANCHOR)
    assert row["effective_start_day"] == 14
    assert row["start_day"] == 10  # the operator's value is not rewritten
    assert (row["window_start"], row["window_end"]) == ("2026-10-14", "2026-10-18")


def test_a_cycle_with_no_first_run_still_reads_its_stored_day(brazos, dana):
    """Nothing anchors it, so the stored day is the only fact there is."""
    with tenant_ctx(brazos):
        made = services.create_cycle(
            dana, {"code": "CY-002", "name": "Cycle 2", "frequency": "monthly"}
        )
        metering_models.Cycle.objects.filter(pk=made["id"]).update(
            start_day=10, days_to_complete=5, first_run_date=None
        )
        row = metering_models.Cycle.objects.get(pk=made["id"])
    assert period_engine.cycle_read_window(row, ANCHOR) == (
        date(2026, 10, 10),
        date(2026, 10, 14),
    )
