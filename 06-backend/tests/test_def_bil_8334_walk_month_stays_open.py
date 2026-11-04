"""DEF-BIL-8334 — the J70/J74 walk world is pinned to September 2026, and that month stays open.

Coordinator ruling 2026-10-01 (decision log): the demo calendar rolls with today
(`core.sample_fixture`), so a database seeded on 1 October closes SEPTEMBER, and
every J70/J74 bill — all dated in September — was refused at Send (*"this journal
entry is dated 2026-09-18, which falls inside the CLOSED fiscal period"*). The walk
is NOT re-dated relative to today, because its worked figures depend on the
month's length: Sep 12–30 is 19/30, the same case in October is 19/31, and a walk
whose expected answer moves every month cannot catch a money regression.

So the J70/J74 seed declares its walk month (`WALK_MONTH`) and leaves it open.
These cases reproduce the demo's own close of September — what `seed_demo` does
on 1 October — and then run the seed's walk-month step. Written RED FIRST (law 7).
"""

from __future__ import annotations

import importlib.util
import pathlib
from datetime import date, datetime, timezone

import pytest

from apps.ledger import close as ledger_close
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

SEED = pathlib.Path(__file__).resolve().parents[2] / "10-scripts" / "seed_j70_one_time_bill.py"
FINAL_BILL_DAY = date(2026, 9, 18)  # J74 case 5's journal date — the one Send refused


def _seed_module():
    spec = importlib.util.spec_from_file_location("seed_j70_for_8334", SEED)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def _demo_closes_september(actor):
    """What the rolling demo does on a database seeded on 1 October."""
    ledger_close.close_period(
        actor,
        period_start=date(2026, 9, 1),
        period_end=date(2026, 9, 30),
        closed_at=datetime(2026, 10, 1, 0, 13, tzinfo=timezone.utc),
        reason="demo month-end (rolling calendar)",
    )


def test_def_bil_8334__the_walk_month_is_september_2026():
    seed = _seed_module()
    assert seed.WALK_MONTH == (date(2026, 9, 1), date(2026, 9, 30))


def test_def_bil_8334__a_september_entry_is_not_refused_after_the_walk_seed_runs(brazos, dana):
    seed = _seed_module()
    with tenant_ctx(brazos):
        _demo_closes_september(dana)
        assert ledger_close.is_closed_on(FINAL_BILL_DAY), "the reproduction: September is closed"
        seed.keep_walk_month_open(brazos, dana)
        assert not ledger_close.is_closed_on(FINAL_BILL_DAY)
        entry_date, note = ledger_close.resolve_entry_date(FINAL_BILL_DAY)
    assert (entry_date, note) == (FINAL_BILL_DAY, None)


def test_def_bil_8334__an_open_walk_month_is_left_alone(brazos, dana):
    """A demo seeded in September closes August, not September: nothing to do."""
    seed = _seed_module()
    with tenant_ctx(brazos):
        seed.keep_walk_month_open(brazos, dana)
        assert not ledger_close.is_closed_on(FINAL_BILL_DAY)
