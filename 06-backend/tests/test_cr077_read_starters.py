# ── Trace ──────────────────────────────────────────────
# Change:  CR-077 — the READING import starters, the last unbuilt piece of the
#          PO's 2026-09-07 ruling: *"it is required for - Premises, Units,
#          Meters, Sub meter,s Assets, Parts, Accounts, Reading - including all
#          readings - Flat, Demand based, Seasonal, Peak , off peak, etc"*.
# Rules:   BR-MET-032 (import is a STANDARD, rules-based process: ONE published
#          template, mapping re-detected on EVERY upload, no per-vendor memory)
#          · BR-MET-013 (auto-detect by header) · BR-MET-059 (an absent channel
#          is the flat meter's `total`) · BR-MET-049 (a demand meter is TWO
#          records) · BR-MET-051 (the reset is NOTED, and on the DEMAND row) ·
#          BR-AST-029 (a net cycle is one `total` and one `export` sharing a
#          `read_at`) · BR-MET-014 (a row that states nothing inherits the
#          batch tag)
# Tests:   this file
# ───────────────────────────────────────────────────────
"""The four reading starters, and why there is no fifth.

⚠ **THE COUNT IS FOUR AND IT IS MEASURED, NOT PREFERRED.** A read shape is a
FILE LAYOUT — how many rows one meter contributes for one date, and which
register each carries:

  · flat AND tiered  ONE row. A tier is a bracket in the PRICE LIST; the file
                     that feeds it is one number.
  · time of use      THREE rows, one per window.
  · demand           TWO rows, energy plus the peak register, and the reset
                     flag means something ONLY on the peak row.
  · net metering     TWO rows, energy plus `export`.

**Seasonal is not one of them.** A season is a property of the price list,
resolved from the date on the reading, so a seasonal read is a flat read on a
date — and a fifth starter would teach a clerk to look for a column no parser
reads. `test_seasonal_is_not_a_shape` is what keeps that decision from being
quietly reversed by somebody reading the PO's list literally.

╔══════════════════════════════════════════════════════════════════════════╗
║  THE TRAP THIS FILE IS WRITTEN AGAINST — the Parts import's, verbatim     ║
╚══════════════════════════════════════════════════════════════════════════╝
**A target's column set is the OWNING MODULE'S WRITER'S SIGNATURE, not its
table's.** The parts template offered a column the writer refuses, and every
row came back rejected AT THE WRITE, with no stage-3 rule able to catch it.

Here the writer's signature is `read_import.TEMPLATE_COLUMNS` — the same dict
`parse_csv` maps a header against — so:

  * `test_every_starter_header_is_the_allow_list` reads that dict rather than a
    copy of it, and would go red the day a column is added to the parser and
    not to the starters;
  * `test_a_starter_cannot_name_a_column_the_parser_refuses` proves the guard
    inside `_shape_row` FIRES, so a starter naming an unreadable column cannot
    be committed at all — it raises at import time, before any clerk sees it;
  * every starter is put through the REAL `parse_csv` and asserted to produce
    ZERO parse errors, which is the check the parts lane did not have.

╔══════════════════════════════════════════════════════════════════════════╗
║  WHAT WOULD MAKE THESE CHECKS PASS WRONGLY                               ║
╚══════════════════════════════════════════════════════════════════════════╝
  1. **A starter with no rows.** Every parse assertion is trivially true of an
     empty file. Each case asserts the ROW COUNT it expects, by shape, and the
     counts are the measured 1/3/2/2 rather than "more than zero".
  2. **A mapping that is `None` for a column and therefore never read.** So the
     mapping case asserts every published header resolves to its OWN target,
     not merely that the required three are present.
  3. **Channels compared against a list in this file.** They are compared
     against `metering.models.CHANNELS`, which is where the vocabulary lives.
"""

import pytest

from apps.metering import models as metering_models
from apps.metering import read_import

pytestmark = pytest.mark.django_db


def _rows(shape: str):
    """`(filename, header, parsed rows)` through the REAL parser."""
    filename, body = read_import.starter_csv(shape)
    mapping, headers, parsed = read_import.parse_csv(body.encode("utf-8"))
    return filename, mapping, headers, parsed


# ── the shape set ───────────────────────────────────────────────────────────
def test_there_are_exactly_four_shapes():
    assert read_import.SHAPE_CODES == ("flat", "tou", "demand", "net")


def test_seasonal_is_not_a_shape():
    """A season is the price list's, not the file's — so there is no starter.

    Refused BY NAME with the four codes, never folded to the flat one: a
    starter that quietly falls back is how a clerk ends up with the wrong file
    and no way to tell.
    """
    assert "seasonal" not in read_import.READ_SHAPES
    with pytest.raises(ValueError) as raised:
        read_import.starter_csv("seasonal")
    assert "flat" in str(raised.value) and "tou" in str(raised.value)


# ── the allow list ──────────────────────────────────────────────────────────
def test_every_starter_header_is_the_allow_list():
    """The header row IS `TEMPLATE_COLUMNS`' published names, in its order.

    Read off the parser's own dict — not a copy — so a column added to
    `TEMPLATE_COLUMNS` and not to `_shape_row`'s output fails here.
    """
    expected = tuple(aliases[0] for aliases in read_import.TEMPLATE_COLUMNS.values())
    assert read_import.PUBLISHED_HEADERS == expected
    for shape in read_import.SHAPE_CODES:
        _filename, _mapping, headers, _parsed = _rows(shape)
        assert tuple(headers) == expected, shape


def test_every_column_maps_itself_with_nothing_typed_by_hand():
    """Stage 2 has nothing left to do — BR-MET-013's auto-detect, on our own
    file. Every published header resolves to its OWN target."""
    for shape in read_import.SHAPE_CODES:
        _filename, mapping, _headers, _parsed = _rows(shape)
        for target, aliases in read_import.TEMPLATE_COLUMNS.items():
            assert mapping.get(target) == aliases[0], f"{shape}: {target} unmapped"


def test_a_starter_cannot_name_a_column_the_parser_refuses():
    """`_shape_row`'s guard FIRES — proved, not assumed (hard-won law 7).

    This is the Parts trap made impossible: a starter naming a column
    `parse_row` does not read raises where it is written, at import time.
    """
    with pytest.raises(ValueError) as raised:
        read_import._shape_row(meter_id="M-1", unit_of_measure="kWh")
    assert "unit_of_measure" in str(raised.value)


# ── every starter parses clean ──────────────────────────────────────────────
@pytest.mark.parametrize(
    ("shape", "row_count"),
    [("flat", 1), ("tou", 3), ("demand", 2), ("net", 2)],
)
def test_every_starter_parses_with_no_errors(shape, row_count):
    _filename, _mapping, _headers, parsed = _rows(shape)
    assert len(parsed) == row_count
    for row in parsed:
        assert row.errors == [], f"{shape} row {row.row_no}: {row.errors}"
        assert row.meter_no_raw
        assert row.read_at is not None
        assert row.value is not None
        assert row.channel in metering_models.CHANNELS


# ── each shape teaches its own layout ───────────────────────────────────────
def test_flat_is_one_number_per_meter():
    """One row, the flat meter's one register, and NO service stated.

    An empty `service` inherits the batch tag (BR-MET-014), which is the honest
    default for the one shape that is not about a service: flat and tiered is
    every utility this product sells, and stating `E` would teach a water
    utility to write it.
    """
    _filename, _mapping, _headers, parsed = _rows("flat")
    (row,) = parsed
    assert row.channel == metering_models.CHANNEL_TOTAL
    assert row.service is None
    assert row.demand_reset is False


def test_time_of_use_is_three_registers_on_one_date():
    _filename, _mapping, _headers, parsed = _rows("tou")
    assert [row.channel for row in parsed] == list(metering_models.TOU_WINDOW_CHANNELS)
    assert len({row.read_at for row in parsed}) == 1
    assert len({row.meter_no_raw for row in parsed}) == 1


def test_demand_is_two_records_and_the_reset_rides_the_peak_row():
    """BR-MET-049 + BR-MET-051, in the file a clerk is handed.

    The reset is asserted to be on the DEMAND row and OFF the energy one — not
    merely present somewhere — because `parse_row` refuses a reset on any other
    channel BY NAME, so a starter that put it on the energy row would be
    rejected on upload.
    """
    _filename, _mapping, _headers, parsed = _rows("demand")
    energy, peak = parsed
    assert energy.channel == metering_models.CHANNEL_TOTAL
    assert energy.demand_reset is False
    assert peak.channel == metering_models.CHANNEL_DEMAND
    assert peak.demand_reset is True
    assert energy.read_at == peak.read_at


def test_net_metering_is_energy_plus_export():
    """BR-AST-029: one `total` record and one `export` record sharing a date."""
    _filename, _mapping, _headers, parsed = _rows("net")
    taken, sent = parsed
    assert taken.channel == metering_models.CHANNEL_TOTAL
    assert sent.channel == metering_models.CHANNEL_EXPORT
    assert taken.read_at == sent.read_at
    assert taken.meter_no_raw == sent.meter_no_raw


# ── one source for the published template ───────────────────────────────────
def test_the_published_template_is_the_demand_starter():
    """`reads_template.csv` and the demand starter are ONE file, not two copies.

    `DEF-616`'s lesson (one list maintained next to another). The bytes are also
    unchanged from what this address has served since CR-038 W4, which is the
    compatibility half: the spec and the front end name this file.
    """
    filename, body = read_import.starter_csv(read_import.SHAPE_DEMAND)
    assert filename == "reads_template.csv"
    assert read_import.template_csv() == body
    assert body.splitlines()[1].startswith(",M-7001,2026-08-03,42864,total,E,walk_by,Access ok,no")
