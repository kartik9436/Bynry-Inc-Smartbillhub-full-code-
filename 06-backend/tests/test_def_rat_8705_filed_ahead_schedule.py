# ── Trace ──────────────────────────────────────────────
# Defects: DEF-RAT-8705 (the wizard's "We could not count the bills." on a
#          schedule whose only live version starts after today) and the money
#          half of DEF-RAT-8703 (does a correction of that version price from
#          its start date?). The PO's beta report of 2026-10-01, v2.418.9,
#          tenant ottumwa-water-works.
# Rules:   BR-RAT-007 (a period prices on the version in force on the SERVICE
#          date) · BR-RAT-104 / BR-RAT-1016 verb 2 (a correction keeps the
#          window) · BR-RAT-1044 (the corrected row's end is
#          max(correction date, its start)) · US-RAT-004 §5 (the status pill is
#          DERIVED: a version in force -> active, none -> draft, a future
#          version adds the "Change scheduled" note) · DEF-RAT-5831 (a schedule
#          filed ahead of time reads Draft, one screen one answer) · CLAUDE.md
#          hard-won law 7 (proved red first, in the harness that runs it).
# Tests:   the PostgreSQL run of THIS file is the money proof:
#          DJANGO_SETTINGS_MODULE=config.settings.pgtest DATABASE_URL=… pytest <this file>
# ───────────────────────────────────────────────────────
"""**A SCHEDULE FILED AHEAD OF TIME: WHAT THE WIZARD COUNTS, AND WHAT PRICES.**

The PO corrected `Sample — Residential water (inclining tiers)` at 00:52 on
1 October their time — which was still **30 September** on the server and on
the utility's own clock. The schedule's only live version started on
**1 October**, so nothing was in force *today*.

⚠ **PROVED RED FIRST (hard-won law 7).** Against `1129ec6b4`, the tip this was
written on, the two count cases failed and the rest passed — the rest pin
behaviour that was already right (the window, the pricing, the derived status)
so a later change cannot take it away. The failure, verbatim:

    test_def_rat_8705__a_filed_ahead_version_counts_its_bills_as_zero_not_unknown
    AssertionError: a version that has not started has priced no bill — 0, not
    "billing could not answer"
    assert None == 0

⚠ **WHAT WOULD MAKE THESE PASS WRONGLY**, asked rather than assumed:

  * **THE CLOCK.** Every case here sets the UTILITY's today through the seam
    the money path reads (`seams.tenant_today`), because on the real wall clock
    of the day this was written the version would already be in force and the
    count case would pass for the wrong reason.
  * **A STUB THAT ALWAYS ANSWERS 0.** The count is asserted against the id the
    seam was ASKED about, so a fix that returned 0 without asking billing about
    the corrected row fails `…_asks_billing_about_the_row_the_screen_corrects`.
  * **`None` FLATTENED TO 0.** `…_billing_not_answering_is_still_unknown` keeps
    DEF-079's distinction: when billing cannot answer the screen must still say
    so.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps.rating import models, seams, selectors, services

from tests.test_us_rat_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_rat_helpers import RES_WATER_TIERS, tenant_ctx

pytestmark = pytest.mark.django_db

START = date(2026, 10, 1)
END = date(2026, 12, 31)
THE_DAY_BEFORE = date(2026, 9, 30)
FIXED = [
    {"from_qty": "0", "to_qty": "5", "unit_price": "4.2400"},
    {"from_qty": "5", "to_qty": "15", "unit_price": "6.8900"},
    {"from_qty": "15", "to_qty": None, "unit_price": "8.4800"},
]
REASON = "+6% across tiers · PUC #W-2025-1184"


@pytest.fixture
def clock(monkeypatch):
    def _set(day: date) -> None:
        monkeypatch.setattr(seams, "tenant_today", lambda: day)

    return _set


def _filed_ahead(env):
    """A schedule whose ONLY live version runs 2026-10-01 → 2026-12-31."""
    return env.tiered_schedule(
        "Res Water · Inclining",
        "water",
        RES_WATER_TIERS,
        effective_from=START.isoformat(),
        effective_to=END.isoformat(),
    )


def _detail(env, tariff_id):
    with tenant_ctx(env.tenant):
        return selectors.schedule_detail(tariff_id)


def _correct(env, tariff_id, version_id):
    with tenant_ctx(env.tenant):
        return services.correct_rate_schedule_version(
            env.admin,
            tariff_id,
            str(version_id),
            {"model": "tiered", "uom": "kgal", "reason": REASON, "structure": {"tiers": FIXED}},
        )


def _in_force(env, tariff_id, day):
    with tenant_ctx(env.tenant):
        return selectors.in_force_version(models.Tariff.objects.get(pk=tariff_id), day)


# ── DEF-RAT-8705 · THE COUNT ──────────────────────────────────────────────


def test_def_rat_8705__a_filed_ahead_version_counts_its_bills_as_zero_not_unknown(env, clock):
    clock(THE_DAY_BEFORE)
    water = _filed_ahead(env)
    detail = _detail(env, water["id"])
    assert detail["status"] == "draft", "nothing is in force on 30 September"
    assert detail["current_version"]["effective_from"] == START.isoformat()
    assert detail["current_version_issued_bills"] == 0, (
        "a version that has not started has priced no bill — 0, not "
        '"billing could not answer"'
    )


def test_def_rat_8705__asks_billing_about_the_row_the_screen_corrects(env, clock, monkeypatch):
    clock(THE_DAY_BEFORE)
    water = _filed_ahead(env)
    asked: list[str] = []

    def _count(version_id):
        asked.append(str(version_id))
        return 7

    monkeypatch.setattr(seams, "tariff_version_issued_bills", _count)
    detail = _detail(env, water["id"])
    assert asked == [detail["current_version"]["id"]], (
        "the figure must describe the version the wizard's Fix an error corrects"
    )
    assert detail["current_version_issued_bills"] == 7


def test_def_rat_8705__billing_not_answering_is_still_unknown(env, clock, monkeypatch):
    """DEF-079's distinction survives: `None` from billing stays `None`."""
    clock(THE_DAY_BEFORE)
    water = _filed_ahead(env)
    monkeypatch.setattr(seams, "tariff_version_issued_bills", lambda version_id: None)
    assert _detail(env, water["id"])["current_version_issued_bills"] is None


def test_def_rat_8705__a_version_in_force_is_still_the_one_counted(env, clock, monkeypatch):
    """Regression: with a version in force, the count is still ITS count."""
    clock(date(2026, 11, 15))
    water = _filed_ahead(env)
    asked: list[str] = []
    monkeypatch.setattr(
        seams, "tariff_version_issued_bills", lambda version_id: asked.append(str(version_id)) or 0
    )
    detail = _detail(env, water["id"])
    assert detail["status"] == "active"
    assert asked == [detail["current_version"]["id"]]


# ── DEF-RAT-8703 · THE MONEY QUESTION ─────────────────────────────────────


def test_def_rat_8703__the_correction_prices_from_its_start_date_and_not_a_day_before(env, clock):
    """**WAS THE RATE CHARGING FROM 1 OCTOBER?** Yes — the correction does, and
    nothing prices 30 September. Read through `in_force_version`, which is
    the function the live bill run calls (BR-RAT-007)."""
    clock(THE_DAY_BEFORE)
    water = _filed_ahead(env)
    original = _detail(env, water["id"])["current_version"]
    answer = _correct(env, water["id"], original["id"])

    correction = answer["current_version"]
    assert correction["id"] != original["id"]
    assert _in_force(env, water["id"], THE_DAY_BEFORE) is None
    for day in (START, START + timedelta(days=45), END):
        row = _in_force(env, water["id"], day)
        assert row is not None and str(row.id) == correction["id"], day
    assert _in_force(env, water["id"], END + timedelta(days=1)) is None, (
        "the window the clerk filed ends on 31 December and the correction "
        "keeps it (BR-RAT-104)"
    )
    with tenant_ctx(env.tenant):
        prices = [
            Decimal(str(tier.unit_price))
            for tier in models.RateTier.objects.filter(
                tenant_id=env.tenant.id, tariff_version_id=correction["id"]
            ).order_by("seq")
        ]
    assert prices == [Decimal("4.24"), Decimal("6.89"), Decimal("8.48")]


def test_def_rat_8703__the_list_says_draft_and_scheduled_until_the_day_then_active(env, clock):
    """US-RAT-004 §5 and DEF-RAT-5831, unchanged: the LIST was right on
    30 September. What the PO saw was the toast disagreeing with it."""
    clock(THE_DAY_BEFORE)
    water = _filed_ahead(env)
    original = _detail(env, water["id"])["current_version"]
    _correct(env, water["id"], original["id"])
    before = _detail(env, water["id"])
    assert (before["status"], before["scheduled_change"]) == ("draft", START.isoformat())

    clock(START)
    on_the_day = _detail(env, water["id"])
    assert (on_the_day["status"], on_the_day["scheduled_change"]) == ("active", None)
