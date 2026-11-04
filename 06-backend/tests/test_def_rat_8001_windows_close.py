# ── Trace ──────────────────────────────────────────────
# Defect: DEF-RAT-8001 — `create_rate_schedule_version` and
#         `_apply_batch_to_schedule` closed `selectors.latest_version(tariff)`,
#         which is ONE row. Once two windows are open, every later activation
#         closes the newest and steps over the rest, so the overlap never
#         heals. Ottumwa Water Works reached four versions of one sewer
#         schedule in force on 2026-10-29.
# Rules:  B2 §2 (no overlapping in-force windows per tariff) · BR-RAT-037 (a
#         CHANGE is a new row with a NEW window) · BR-RAT-104 / BR-RAT-1016
#         verb 2 (a CORRECTION restates the SAME window and is NOT closed) ·
#         BR-RAT-031 (a dateless draft has no window)
# ───────────────────────────────────────────────────────
"""Wave B3 — three versions in sequence, and EXACTLY ONE stays open.

⚠ **PROVED RED FIRST, in a clean worktree at the commit before the fix
(`31ce6115a`), against the code as it stood (hard-won law 7).** Three of the
seven cases in this file and its sibling failed and four passed — the four
that describe behaviour that was already right. This file's red was
`…a_second_open_window_is_closed_too_not_stepped_over`, verbatim:

    AssertionError: [(date(2026, 8, 1), None),
                     (date(2026, 8, 16), date(2026, 12, 31)),
                     (date(2027, 1, 1), None)]
    assert […] == […]
      Left contains one more item: (date(2027, 1, 1), None)

Read the first tuple: **`2026-08-01` was still open** after a rate change
dated `2027-01-01`. `create_rate_schedule_version` closed
`selectors.latest_version` — the `2026-08-16` row — and stepped straight over
the older one, which is Ottumwa's mechanism exactly.

⚠ **SQLITE CANNOT SHOW THE OTHER HALF.** `rating/0047`'s exclusion constraint
is PostgreSQL-only (hard-won law 14), so on the default suite these assertions
are the ONLY thing standing between a clerk and two open windows. The database
half is `tests/test_def_rat_8000_no_overlap_pg.py`.
"""

from datetime import date, timedelta

import pytest

from apps.rating import models, selectors, services

from tests.test_us_rat_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_rat_helpers import RES_WATER_TIERS, tenant_ctx

pytestmark = pytest.mark.django_db


def _tiers(price):
    return [{"from_qty": "0", "to_qty": None, "unit_price": price}]


def _change(env, tariff_id, effective_from, price):
    with tenant_ctx(env.tenant):
        return services.create_rate_schedule_version(
            env.admin,
            tariff_id,
            {
                "model": "tiered",
                "uom": "kgal",
                "reason": f"Board-approved rate change effective {effective_from}",
                "effective_from": effective_from,
                "structure": {"tiers": _tiers(price)},
            },
        )


def _windows(env, tariff_id):
    with tenant_ctx(env.tenant):
        tariff = models.Tariff.objects.get(pk=tariff_id)
        return [
            (v.effective_from, v.effective_to)
            for v in selectors.activated_versions(tariff)
            .filter(superseded_by__isnull=True)
            .order_by("effective_from")
        ]


def test_def_rat_8001__three_versions_in_sequence_leave_exactly_one_open(env):
    """The plain case: file two rate changes over a live schedule."""
    water = env.tiered_schedule("Res Water · Inclining", "water", RES_WATER_TIERS)
    _change(env, water["id"], "2026-10-01", "4.10")
    _change(env, water["id"], "2027-01-01", "4.40")

    windows = _windows(env, water["id"])
    assert windows == [
        (date(2026, 8, 1), date(2026, 9, 30)),
        (date(2026, 10, 1), date(2026, 12, 31)),
        (date(2027, 1, 1), None),
    ], windows
    assert sum(1 for _f, to in windows if to is None) == 1


def test_def_rat_8001__a_second_open_window_is_closed_too_not_stepped_over(env):
    """⚠ THE DEFECT ITSELF, AND THE ONLY ASSERTION THAT WAS RED.

    An estate that already holds two open windows — which is how Ottumwa's
    sewer schedule looked — must come back to ONE after the next rate change.
    The old code closed `latest_version` alone, so the OLDER open row survived
    every subsequent change for ever.
    """
    water = env.tiered_schedule("Res Water · Inclining", "water", RES_WATER_TIERS)
    with tenant_ctx(env.tenant):
        tariff = models.Tariff.objects.get(pk=water["id"])
        first = selectors.latest_version(tariff)
        # A second open window, planted the way a real one arrives: a row whose
        # `effective_to` nobody ever filled. Written through the ORM rather
        # than through a service, because no service can produce it any more —
        # which is the point of the fix.
        models.TariffVersion.objects.create(
            tenant_id=first.tenant_id,
            tariff=tariff,
            model=first.model,
            currency=first.currency,
            uom=first.uom,
            percent_basis=first.percent_basis,
            effective_from=first.effective_from + timedelta(days=15),
            effective_to=None,
        )
    assert sum(1 for _f, to in _windows(env, water["id"]) if to is None) == 2

    _change(env, water["id"], "2027-01-01", "4.40")

    windows = _windows(env, water["id"])
    still_open = [w for w in windows if w[1] is None]
    assert still_open == [(date(2027, 1, 1), None)], windows
    # And every older window now ends the day before the new one starts or
    # earlier — nothing was stepped over.
    assert all(to is not None and to < date(2027, 1, 1) for _f, to in windows[:-1]), windows


def test_def_rat_8001__a_correction_is_not_closed_and_keeps_its_window(env):
    """BR-RAT-104 / BR-RAT-1016 verb 2 — the row this must NOT touch.

    A corrected row's window is settled at the moment it is corrected and is
    never moved afterwards. It has already stopped pricing
    (`in_force_version` skips it), and rewriting its window would falsify the
    filing history a regulator reads. A later rate change must leave it alone.

    ⚠ **THIS READ *"a corrected row keeps its DATES for ever"* UNTIL
    `BR-RAT-1044` (PO ruling 2026-09-29), AND THE ASSERTION BELOW IS WHY THE
    SENTENCE HAD TO MOVE AND THE TEST DID NOT.** The correction itself now
    stamps `effective_to` on the row it supersedes — `max(the correction
    date, its effective_from)`, so the register shows when the wrong version
    stopped being used. This case captures the window AFTER the correction
    and asserts a later rate change does not touch it, which is exactly the
    guarantee that still holds. What is no longer true is *the corrected row
    never has an end date*; what is still true, and is what
    `_close_open_windows_before` promises, is *nothing moves it afterwards*.
    """
    water = env.tiered_schedule("Res Water · Inclining", "water", RES_WATER_TIERS)
    with tenant_ctx(env.tenant):
        tariff = models.Tariff.objects.get(pk=water["id"])
        original = selectors.latest_version(tariff)
        services.correct_rate_schedule_version(
            env.admin,
            water["id"],
            str(original.id),
            {
                "model": "tiered",
                "uom": "kgal",
                "reason": "Tier 1 was typed as 32.00 and the board approved 3.20",
                "structure": {"tiers": _tiers("3.20")},
            },
        )
        original.refresh_from_db()
        corrected_window = (original.effective_from, original.effective_to)
        assert original.superseded_by_id is not None

    _change(env, water["id"], "2027-01-01", "4.40")

    with tenant_ctx(env.tenant):
        original.refresh_from_db()
    assert (original.effective_from, original.effective_to) == corrected_window
    # exactly one LIVE open window, and the superseded row is not one of them
    assert sum(1 for _f, to in _windows(env, water["id"]) if to is None) == 1
