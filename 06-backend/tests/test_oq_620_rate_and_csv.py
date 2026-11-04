# ── Trace ──────────────────────────────────────────────
# Story:    OQ-620, ruled by the Product Owner 2026-08-27 in two halves
#           Screens: RAT-02 · the rate schedule detail · the unit pricing panel
#           · BIL-04 the printable bill · every list CSV
# Rules:    OQ-620(a) (a tariff RATE displays FOUR decimals, zeros KEPT) ·
#           OQ-620(b) (a downloaded CSV shows two decimals, like the screen) ·
#           BR-SHL-250 (WHERE a value is formatted, and ONE composer per
#           runtime) · BR-MET-144 (a quantity: at most 2dp, zeros TRIMMED) ·
#           CLAUDE.md hard rule 2 (money 4/percent 6 stored, both DISPLAY 2) ·
#           hard rule 3 (a quantity carries its unit)
# Defects:  DEF-1121 (Plans & Rates printed `0.000000 – 5.000000` at
#           `8.290000`) · DEF-1123 (the CSV kernel had no QUANTITY and no
#           PERCENT kind) · DEF-1120 (BR-MET-144 implemented four times, twice
#           by halves — `documents._trim` was one of the two)
# ───────────────────────────────────────────────────────
"""THREE KINDS OF NUMBER THAT ROUND THREE DIFFERENT WAYS, PINNED TOGETHER.

WHY ONE FILE FOR ALL THREE
--------------------------
Because the failure mode is not getting one of them wrong — it is reaching for
the WRONG ONE, and every one of them produces a well-formed string. `8.29`,
`8.2900` and `8.29` are all plausible renderings of the same stored
`8.290000`, and only one is right for a given column:

    MONEY     2dp, PADDED     `$64.57`      hard rule 2 (PO re-sign 2026-08-22)
    QUANTITY  <=2dp, TRIMMED  `5 kgal`      BR-MET-144 (PO 2026-08-27)
    RATE      4dp, KEPT       `$0.1420`     OQ-620(a) (PO 2026-08-27)

So the cases sit side by side and several assert the NEGATIVE — that a rate is
NOT `8.29` and a quantity is NOT `8.00` — because a test that only checks the
right answer passes just as happily on code that reached for the neighbour and
got lucky on that value.

RED-FIRST RECORD (hard-won law 7), measured before each fix:

  * `wording.rate_text` did not exist. Every rate assertion below raised
    `AttributeError: module 'apps.rating.pricing.wording' has no attribute
    'rate_text'`.
  * `documents._trim` served BOTH a quantity and a unit price and only
    TRIMMED, so `_quantity(Decimal("26.243700"), "kgal")` returned
    `'26.2437 kgal'` where BR-MET-144 rules `'26.24 kgal'`, and
    `_rate(Decimal("8.290000"))` returned `'8.29'` where OQ-620(a) rules
    `'8.2900'`.
  * `export_kernel.QUANTITY` and `export_kernel.PERCENT` did not exist:
    `AttributeError`, and the reads CSV declared its three register columns
    `NUMBER`, which is *written as served* — `1008.000000`.

⚠ **THE FIGURES ARE THE PO's OWN, NOT THIS FILE's.** `8.2900` and `0.1420` are
the two worked examples put to them; `1008`, `26.24` and `64.57` are the three
in the CSV ruling. Nothing here invents a precision.
"""

from __future__ import annotations

from decimal import Decimal

from apps.rating.pricing import wording
from apps.tenancy import exports as export_kernel


# ── OQ-620(a) AS NARROWED 2026-10-02 · UP TO FOUR, AT LEAST TWO ─────────────
# PO, verbatim: *"Show unit prices with up to 4 decimals and keep every total
# at 2."* OQ-620(a) kept the zeros (`8.2900`); this ruling drops the zeros after
# the second place and keeps every place a price actually carries.
def test_unit_price_ruling_2026_10_02_the_figures_put_to_the_po():
    """`$0.0425` was `$0.04` under the 2-decimal rule — `$400.00` read for
    `$425.00` billed over 10,000 gallons. It now reads all four places."""
    assert wording.rate_text(Decimal("0.042500")) == "0.0425"
    assert wording.rate_text(Decimal("0.100000")) == "0.10"
    assert wording.rate_text(Decimal("12.5")) == "12.50"


def test_unit_price_keeps_four_places_and_never_fewer_than_two():
    """The two properties a careless fix loses, asserted both ways.

    Trimming like a QUANTITY would print `12` and `0`; cutting to MONEY's two
    would print `0.04`. Neither is a unit price.
    """
    assert wording.rate_text(Decimal("8.290000")) == "8.29"  # was `8.2900`
    assert wording.rate_text(Decimal("0.142000")) == "0.142"  # was `0.1420`
    assert wording.rate_text(Decimal("0.042500")) != "0.04"
    assert wording.rate_text(Decimal("12")) == "12.00"  # padded to the floor
    assert wording.rate_text(Decimal("0")) == "0.00"
    assert wording.rate_text(Decimal("100")) == "100.00"  # never `1E+2`


def test_oq620a_a_rate_rounds_half_up_at_the_fourth_place():
    """B4's direction, at the rate's own place rather than money's."""
    assert wording.rate_text(Decimal("0.14205")) == "0.1421"  # AT the tie -> up
    assert wording.rate_text(Decimal("0.142049")) == "0.142"  # below -> down, zero dropped
    assert wording.rate_text(Decimal("-0.14205")) == "-0.1421"  # away from zero


def test_oq620a_the_three_rules_disagree_on_one_stored_value():
    """The whole reason this file exists: one figure, three right answers.

    `8.500000` is `8.50` as a rate, `8.5` as a quantity, and `8.50` as money
    — and since 2026-10-02 the rate differs from the quantity rather than from
    money (`8.290000` reads `8.29` as all three; it read `8.2900` as a rate
    under OQ-620(a)'s zeros-kept form, now superseded).
    """
    stored = Decimal("8.500000")
    assert wording.rate_text(stored) == "8.50"
    assert wording.quantity_text(stored) == "8.5"
    assert wording.rate_text(stored) != wording.quantity_text(stored)


def test_oq620a_a_rate_composer_never_mutates_what_it_was_given():
    """Display only — storage stays at BR-RAT-003's six places."""
    stored = Decimal("0.142000")
    wording.rate_text(stored)
    assert stored == Decimal("0.142000")


# ── DEF-1121 · THE TIER ROW, WHOSE TWO HALVES OBEY DIFFERENT RULES ──────────
def test_def1121_a_tier_row_composes_its_bounds_and_its_price_differently():
    """`0 – 5 kgal` at `8.2900` — the row the PO met as `0.000000 – 5.000000`.

    This is the case DEF-1121 could not be fixed without a ruling: the bounds
    and the price sit in one row and round in opposite directions.
    """
    assert wording.quantity_with_unit(Decimal("0.000000"), "kgal") == "0 kgal"
    assert wording.quantity_with_unit(Decimal("5.000000"), "kgal") == "5 kgal"
    assert wording.rate_text(Decimal("8.290000")) == "8.29"


def test_def1121_a_bound_with_no_unit_is_refused_rather_than_printed_bare():
    """CLAUDE.md hard rule 3, and why the sibling is allowed to be null.

    A version that records no UoM has a data problem; a bare `5` in a column
    headed *From* is read as the tenant's own unit by whoever is looking.
    """
    assert wording.quantity_with_unit(Decimal("5.000000"), None) is None
    assert wording.quantity_with_unit(Decimal("5.000000"), "") is None
    # An OPEN top tier has no upper bound and must stay absent, never `0`.
    assert wording.quantity_with_unit(None, "kgal") is None


def test_def1121_the_two_backend_composers_of_br_met_144_agree():
    """BR-SHL-250 §4 — one rule, one composer per runtime, and a test where
    the module boundary forces two.

    `apps/rating/pricing` is pure and may not import metering, so BR-MET-144
    exists on both sides. This is the assertion that keeps them equal, and
    BR-SHL-250 §4 records what happened without one: four implementations, two
    of them half, and `26.24` on one screen against `26.2437` on another.
    """
    from apps.metering import quantity_display

    for raw in ("0.000000", "5.000000", "8.290000", "26.243700", "684.000000",
                "3.720000", "1008.000000", "0.000001", "8.125"):
        assert wording.quantity_text(Decimal(raw)) == quantity_display.quantity_text(
            Decimal(raw)
        ), raw


# ── DEF-1123 · THE CSV MIRRORS THE SCREEN ───────────────────────────────────
def test_def1123_the_three_figures_from_the_csv_ruling():
    """*"(a) Two decimals, like the screen - this is okay"*, worked."""
    assert export_kernel.format_value(Decimal("1008.000000"), export_kernel.QUANTITY, None) == "1008"
    assert export_kernel.format_value(Decimal("26.243700"), export_kernel.QUANTITY, None) == "26.24"
    assert export_kernel.format_value(Decimal("64.5700"), export_kernel.MONEY, None) == "64.57"


def test_def1123_a_csv_quantity_trims_and_a_csv_money_pads():
    """The two kinds differ in the FILE exactly as they differ on the screen.

    Asserted as a pair because the failure is using one kind for the other, and
    `1008` vs `1008.00` is the visible difference.
    """
    assert export_kernel.format_value(Decimal("1008.000000"), export_kernel.QUANTITY, None) != "1008.00"
    assert export_kernel.format_value(Decimal("1008.000000"), export_kernel.MONEY, None) == "1008.00"


def test_def1123_there_is_no_percent_kind_either_and_that_is_the_finding():
    """⚠ **I BUILT ONE AND TOOK IT BACK OUT — OQ-621.**

    DEF-1123 reported that IS-9 had no PERCENT kind and that percentages
    therefore exported at six places against hard rule 2's display-two. The
    kind was written, and then the only exported percent column in the product
    turned out to hold a **FRACTION**: `charges.percent` stores `0.015000` for
    one and a half percent, so quantizing to two places writes `0.02` and
    destroys it. `test_be_list_export.py` said so in its own assertion and
    caught it on the first run.

    The real gap is bigger and is not ours: the file writes `0.015000` where
    the SCREEN renders `1.50%` (`selectors._display_percent` multiplies by a
    hundred), so the two disagree about the UNIT, not the precision. OQ-620(b)
    ruled on precision; rescaling a column by 100 in a file somebody already
    parses is a different decision. Asked as OQ-621.

    Asserted rather than merely commented, so that a lane adding the kind back
    has to delete this case and read why it existed.
    """
    assert not hasattr(export_kernel, "PERCENT")

    from apps.rating import exports as rating_exports

    kinds = {column.name: column.kind for column in rating_exports.CHARGES.columns}
    assert kinds["percent"] == export_kernel.NUMBER


def test_def1123_an_absent_figure_stays_absent_in_the_file():
    """`None` is an empty cell, never a zero — BR-MET-106 in a CSV."""
    assert export_kernel.format_value(None, export_kernel.QUANTITY, None) == ""


def test_def1123_an_unparseable_value_is_written_through_unchanged():
    """`format_money`'s standing rule: an export never quietly changes a value."""
    assert export_kernel.format_quantity("pending") == "pending"


def test_def1123_the_reads_export_declares_its_registers_as_quantities():
    """The wiring, not just the formatter — hard-won law 2.

    A kind nothing declares is a kind that changes no file, and IS-9's whole
    defect was that a quantity fell through to `NUMBER` by accident.
    """
    from apps.metering import exports as metering_exports

    kinds = {column.name: column.kind for column in metering_exports.READS.columns}
    for header in ("prior_value", "current_value", "consumption"):
        assert kinds[header] == export_kernel.QUANTITY, header


def test_def1123_there_is_still_no_rate_kind_and_that_is_deliberate():
    """OQ-620(b)'s open half, asserted so it cannot be closed by accident.

    A rate exporting at two places would print a figure that cannot reproduce
    its own line. Until the PO confirms the one remaining line, no `RATE` kind
    exists and the tax `rate` column stays `NUMBER`, visibly.

    ⚠ **WHEN THAT CONFIRMATION ARRIVES, THIS CASE IS PART OF THE CHANGE** —
    delete it in the same commit that adds the kind, rather than leaving a test
    that asserts the absence of the thing you just built.
    """
    assert not hasattr(export_kernel, "RATE")

    from apps.rating import exports as rating_exports

    kinds = {column.name: column.kind for column in rating_exports.TAXES.columns}
    assert kinds["rate"] == export_kernel.NUMBER
