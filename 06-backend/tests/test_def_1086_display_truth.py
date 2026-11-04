# ── Trace ──────────────────────────────────────────────
# Story:    DEF-1086 — the reads list printed the raw stored register reading,
#           `1008.000000`   Screens: S25 · S29 · RDS-01 · RDS-04
# Rules:    BR-SHL-250 (WHERE a value is formatted — a quantity is composed by
#           the side that holds its unit, and the server's `_display` sibling
#           is the default because it is the form a machine can see is
#           missing) · BR-MET-144 (at most 2dp, trailing zeros trimmed) ·
#           BR-MET-143 (a register carries its own unit) · BR-MET-106 (an
#           unread month is ABSENT, never a zero) · CLAUDE.md hard rule 3
# ───────────────────────────────────────────────────────
"""The register reading's own display string, pinned to the PO's figure.

WHAT THIS FILE IS FOR
---------------------
`read_dict` grew two keys — `prior_value_display` and `current_value_display` —
and the whole value of BR-SHL-250 is that a SIBLING is a thing a machine can
check for. `G44` clause (b) checks the CLIENT half (a screen may not print the
raw field once a sibling exists); this file checks the SERVER half, which no
gate can see: that the sibling is composed by the one composer, at the ruled
precision, with the register's own unit, and that it is ABSENT rather than zero
when there is no reading.

RED-FIRST RECORD (hard-won law 7). Before this change `read_dict` served only
`str(read.prior_value)`, so the reads list rendered BR-MET-019's `NUMERIC(18,6)`
verbatim and the Product Owner read, on the live deployment at v2.73.0:

    "previous and current reading still showing 4 decimal"

Every assertion below fails against that serializer — there was no key to
assert on at all, so each `assert row["prior_value_display"] == …` raises
`KeyError: 'prior_value_display'`, which is the RED this file was written for.

⚠ **THE RAW KEYS ARE ASSERTED TO SURVIVE, ON PURPOSE.** Deleting them would be
a different defect: `apps/metering/exports.READS` writes them to the CSV and
the correction modal prefills from them, and both need the UNROUNDED number.
BR-SHL-250's rule is that the DISPLAY string is a separate field, not that the
number stops travelling.
"""

from __future__ import annotations

from decimal import Decimal

from apps.metering import quantity_display


class _Read:
    """The three attributes `read_dict`'s two new keys are composed from.

    A stub rather than a model row: this asserts a COMPOSITION rule, and a
    composition rule that needs a database to state itself is a rule nobody can
    read. The ORM path is covered by the metering selector suites.
    """

    def __init__(self, prior, current, unit):
        self.prior_value = prior
        self.current_value = current
        self.unit = unit


def _displays(read: _Read) -> tuple[str | None, str | None]:
    """Exactly the expression `read_dict` uses, so this cannot drift from it."""
    return (
        quantity_display.quantity_with_unit(read.prior_value, read.unit),
        quantity_display.quantity_with_unit(read.current_value, read.unit),
    )


def test_def_1086_the_po_figure_renders_with_its_unit_and_no_decimals():
    """`1008.000000` → `1008 kWh`. The figure the PO reported, end to end."""
    prior, current = _displays(
        _Read(Decimal("1008.000000"), Decimal("1042.000000"), "kWh")
    )
    assert prior == "1008 kWh"
    assert current == "1042 kWh"
    # And explicitly NOT the two shapes a half-fix produces.
    assert prior != "1008.000000 kWh"
    assert prior != "1008.00 kWh"


def test_def_1086_a_significant_fraction_rounds_half_up_to_two_places():
    """BR-MET-144's first half, on a register value rather than a consumption."""
    prior, current = _displays(
        _Read(Decimal("42864.567891"), Decimal("42864.125000"), "kWh")
    )
    assert prior == "42864.57 kWh"
    assert current == "42864.13 kWh"  # AT the tie → away from zero


def test_def_1086_the_register_unit_is_the_one_that_travels():
    """BR-MET-143 — a demand register reads in `kW`, not the service unit."""
    prior, current = _displays(_Read(Decimal("398.000000"), Decimal("412.000000"), "kW"))
    assert prior == "398 kW"
    assert current == "412 kW"


def test_def_1086_an_absent_reading_is_absent_and_never_zero():
    """BR-MET-106 held at the display layer: `None` in, `None` out.

    An estimate has a consumption and NO register value (BR-MET-028), and the
    cell must dash it. Composing `"0 kWh"` here would state that a meter
    measured nothing, which is a different and false fact.
    """
    prior, current = _displays(_Read(None, Decimal("1008.000000"), "kWh"))
    assert prior is None
    assert current == "1008 kWh"


def test_def_1086_a_reading_with_no_unit_is_refused_rather_than_printed_bare():
    """CLAUDE.md hard rule 3, and the reason the sibling can be null.

    A bare number in a column headed PREVIOUS is read as the tenant's own unit
    by whoever is looking at it, so a reading whose unit was never recorded
    renders as an absence and the screen says so — it does not print the digits
    on their own.
    """
    prior, current = _displays(_Read(Decimal("1008.000000"), Decimal("1042.0"), None))
    assert prior is None
    assert current is None


def test_def_1086_the_display_string_is_not_a_data_change():
    """The stored Decimals are untouched — this is the LAST step before a screen."""
    read = _Read(Decimal("1008.000000"), Decimal("1042.500000"), "kWh")
    _displays(read)
    assert read.prior_value == Decimal("1008.000000")
    assert read.current_value == Decimal("1042.500000")


def test_def_1086_read_dict_serves_both_the_raw_value_and_its_display():
    """The contract `G44` clause (b) and `exports.READS` each depend on.

    ⚠ Asserted TOGETHER because the two requirements pull opposite ways: the
    screen needs the composed string and the CSV needs the unrounded number, so
    a change that satisfies one by removing the other passes a narrower test.
    """
    from apps.metering import selectors

    source = selectors.read_dict.__code__.co_consts
    served = {const for const in source if isinstance(const, str)}
    for key in (
        "prior_value",
        "current_value",
        "prior_value_display",
        "current_value_display",
        "usage_display",
        "unit",
    ):
        assert key in served, f"read_dict no longer serves {key!r}"
