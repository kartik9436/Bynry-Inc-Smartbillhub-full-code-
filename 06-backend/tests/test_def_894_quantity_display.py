# ── Trace ──────────────────────────────────────────────
# Story:    DEF-894 — every quantity rendered six decimal places on screen and
#           in print   Screens: S25 · S29 · RDS-01 · RDS-04
# Rules:    BR-MET-144 (PO 2026-08-27: a quantity DISPLAYS at most two
#           decimals, trailing zeros trimmed; storage stays at six) ·
#           BR-MET-019 (storage precision) · CLAUDE.md hard rule 3
# ───────────────────────────────────────────────────────
"""The display rule, pinned — because the figure came from the PO.

RED-FIRST RECORD (hard-won law 7). Before `quantity_display` existed, the
server composed `f"{read.consumption} {read.unit}"` in five places and the
route sheet in a sixth, so every one of these cases produced the STORED string:
`8.000000 kgal` where the PO ruled `8 kgal`. Each assertion below fails against
that composition, which is what the live app was doing at v2.61.1.

⚠ **AND THE TRIM IS THE HALF THAT MONEY DOES NOT SHARE.** `$8.00` is right and
`8.00 kgal` is noise: a currency's precision is a property of the currency, and
a quantity's is what the meter measured. So this suite asserts `"8"` and NOT
`"8.00"` — a fix that reached two decimals and stopped would pass a careless
reading of the ruling and still be wrong.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from apps.metering import quantity_display


@pytest.mark.parametrize(
    ("stored", "shown"),
    [
        # The four figures on the PO's own screenshots, at v2.61.1.
        ("8.000000", "8"),
        ("1008.000000", "1008"),
        ("1016.000000", "1016"),
        ("684.000000", "684"),
        # The prototype's own draws — r10 is the ratified reference (PO
        # 2026-08-16), and it has shown these three the whole time.
        ("3.720000", "3.72"),
        ("26.240000", "26.24"),
        ("14.000000", "14"),
        # A quantity that genuinely has decimals keeps them, to two.
        ("1412.500000", "1412.5"),
        # More than two rounds HALF-UP, the direction B4 rounds money.
        ("8.126000", "8.13"),
        ("8.124000", "8.12"),
        ("0.005000", "0.01"),
        # Zero is a real measured answer and stays one character.
        ("0.000000", "0"),
    ],
)
def test_def894__a_quantity_shows_at_most_two_decimals_and_no_trailing_zeros(stored, shown):
    assert quantity_display.quantity_text(Decimal(stored)) == shown
    assert quantity_display.quantity_text(stored) == shown


def test_def894__a_whole_number_keeps_no_decimal_point_at_all():
    """The half of the ruling a two-decimal fix would miss."""
    assert quantity_display.quantity_text("8.000000") == "8"
    assert quantity_display.quantity_text("8.000000") != "8.00"


def test_def894__an_absent_quantity_is_absent_and_never_a_zero():
    """BR-MET-106's own rule, held at the display layer too: an unread month is
    ABSENT, never `0`. A formatter that answered "0" for None would state that
    a meter measured nothing, which is a different and false fact."""
    assert quantity_display.quantity_text(None) is None
    assert quantity_display.quantity_with_unit(None, "kgal") is None


def test_def894__a_quantity_with_no_unit_is_refused_a_rendering():
    """CLAUDE.md hard rule 3, made structural. A bare number in a column headed
    Usage is read as the tenant's own unit by whoever is looking at it, so the
    pair renders together or not at all — the screens have a sentence for the
    absence."""
    assert quantity_display.quantity_with_unit("8.000000", None) is None
    assert quantity_display.quantity_with_unit("8.000000", "") is None
    assert quantity_display.quantity_with_unit("8.000000", "kgal") == "8 kgal"


def test_def894__an_unparseable_value_degrades_rather_than_breaking_the_page():
    """This runs on the last step before a screen. A display helper that raised
    over an odd value would turn a rendering problem into an outage."""
    assert quantity_display.quantity_text("not a number") == "not a number"


def test_def894__the_stored_precision_is_untouched():
    """The rule governs what is WRITTEN for a person, not what is stored.
    BR-MET-019's six places and the engine's arithmetic are unaffected: nothing
    round-trips through this function, and this asserts the boundary rather
    than trusting the docstring (hard-won law 1)."""
    stored = Decimal("8.126000")
    assert quantity_display.quantity_text(stored) == "8.13"
    assert stored == Decimal("8.126000"), "the formatter must not mutate its input"
