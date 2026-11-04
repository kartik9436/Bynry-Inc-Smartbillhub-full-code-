# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-357 (the seed wrote exactly ONE version per priced object)
# Rules:    BR-RAT-007 (a bill prices on the version in force at the SERVICE
#           date) · BR-RAT-037 (a version is never written without a reason) ·
#           BR-TEN-063 (sample seeding is idempotent)
# ───────────────────────────────────────────────────────
"""The fixture's version history, asserted as SHAPE rather than as row count.

WHY THIS FILE EXISTS
--------------------
The seed wrote one version per object, so every Versions tab in the product
rendered a single row and `SUPERSEDED` was always an em-dash. Nothing failed:
one version is a perfectly valid count and the screens render it correctly.

The damage was to the tests, not the screens. **An assertion that billing picks
the version in force on the usage date cannot fail when there is only one
version to pick** — so the whole of BR-RAT-007 was nominally covered and
actually untestable.

These assertions pin the three STATES r10 draws, not the number three: a lane
adding a fourth version should not have to edit this file, and a lane collapsing
the history to one should not get away with it.
"""

from __future__ import annotations

from datetime import date

from core import sample_fixture as fixture


def _history():
    return fixture.WATER_VERSION_HISTORY


def test_the_history_produces_a_superseded_a_current_and_a_future_version():
    """r10's three states, against the fixture's own clock.

    v1 is seeded at 2026-06-01 by `_schedule_payloads`; the two rows here are
    what turn it into a history.
    """
    dates = [date.fromisoformat(row[0]) for row in _history()]
    v1 = date(2026, 6, 1)
    today = date(2026, 8, 20)

    superseded_by = [d for d in dates if v1 < d <= today]
    not_yet_in_force = [d for d in dates if d > today]

    assert superseded_by, "v1 is never superseded — the SUPERSEDED column stays an em-dash"
    assert not_yet_in_force, (
        "no version is dated ahead, so the DATED banner claims behaviour the "
        "fixture cannot exhibit and DEF-280's diff has nothing to render"
    )


def test_no_version_starts_inside_the_billed_june_period__BR_RAT_007():
    """The guard that keeps this fixture from re-pricing history.

    June is a BILLED period. A version effective inside it would change what an
    already-issued bill prices to, which is precisely what dated versions exist
    to prevent — r10 says it plainly: *"a January bill for December usage uses
    v3 even after v4 activates."*
    """
    june_end = date(2026, 6, 30)
    for effective_from, reason, _tiers in _history():
        assert date.fromisoformat(effective_from) > june_end, (
            f"version {effective_from!r} ({reason}) starts on or before the end "
            "of the billed June period and would re-price an issued bill"
        )


def test_every_version_carries_an_authored_reason__BR_RAT_037_and_DEF_280():
    """The `CHANGE` column is a sentence a person wrote, not a derived diff.

    DEF-280 renders every structural change as the literal string `{...}`; the
    fix is to capture the sentence at version creation, and this asserts the
    fixture supplies one to capture.
    """
    for effective_from, reason, _tiers in _history():
        assert reason.strip(), f"version {effective_from} has no reason (BR-RAT-037)"
        assert "{" not in reason, "a reason is prose, not a serialized structure"


def test_the_prices_are_DERIVED_from_the_base_tiers_not_typed():
    """The figures live in `core/sample_fixture.py`, whose own rule is *"every
    figure cited; none invented"* — and they are computed from `WATER_TIERS` by
    a stated uplift rather than written out.

    Three literals (4.24 / 6.89 / 8.48) would be individually well-formed and
    would drift silently the moment the base tiers changed. This asserts the
    derivation, so the fixture cannot come apart from itself.
    """
    from decimal import ROUND_HALF_UP, Decimal

    base = [Decimal(price) for _lo, _hi, price in fixture.WATER_TIERS]
    for (_from, _reason, tiers), factor in zip(
        _history(), (fixture.WATER_V2_UPLIFT, fixture.WATER_V3_UPLIFT)
    ):
        expected = [
            (p * Decimal(factor)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) for p in base
        ]
        assert [Decimal(t) for t in tiers] == expected


def test_the_prices_actually_move_between_versions():
    """A history whose versions all price identically tests nothing — it would
    satisfy every count assertion and still make BR-RAT-007 unfalsifiable."""
    tier_sets = [row[2] for row in _history()]
    assert len(set(tier_sets)) == len(tier_sets), "two versions carry identical prices"
