# ── Trace ──────────────────────────────────────────────
# Task:    Finance blueprint `P0.13` — the `JE-` series format the PO ruled
#          on 2026-09-23, verbatim: *"you need je-MMDDYY- nnnn like this
#          otherwise it will not work"*.
# Rules:   `BR-TEN-035` (numbering grammar: ≤24 chars, one counter, pad ≤8,
#          only the four date tokens) · `BR-LED-021` (a journal entry carries
#          a `JE-` number, stamped at POST)
# Code:    core/numbering.py SERIES_CATALOG[JOURNAL_ENTRY] ·
#          apps/tenancy/migrations/0048_p0_13_je_series_format.py
# ───────────────────────────────────────────────────────
"""The ruled `JE-` format, asserted rather than described.

**WHY EACH ASSERTION IS HERE AND NOT A COMMENT** (hard-won law 1 — a comment
claiming a guarantee is not the guarantee). The format was checked against the
`BR-TEN-035` grammar by hand before it was written into the catalog; a hand
check leaves nothing behind. These four assertions are that check, kept.

The grammar is not a formality here. `MAX_FORMAT_LENGTH` is **24** and the
ruled string is **22** — two characters of headroom. A later lane adding a
literal (`JE-GL-…`) would take it over, `validate_format` would start refusing
every allocation, and the first symptom would be a bill run that cannot post.
"""

from datetime import date



from core import numbering

RULED = "JE-{MM}{DD}{YY}-{0000}"


def test_the_seeded_default_is_the_format_the_po_ruled():
    """PO 2026-09-23: *"you need je-MMDDYY- nnnn like this otherwise it will
    not work"*. The FIRST option in the catalog is what provisioning seeds."""
    _group, options = numbering.SERIES_CATALOG[numbering.JOURNAL_ENTRY]
    assert options[0] == RULED


def test_the_previous_default_is_kept_as_an_option():
    """`JE-{000000}` stood from CR-005 and a tenant may already be on it, with
    numbers issued. Removing it from the picker would leave that tenant's own
    format unofferable on the screen that shows it."""
    _group, options = numbering.SERIES_CATALOG[numbering.JOURNAL_ENTRY]
    assert "JE-{000000}" in options


def test_the_ruled_format_satisfies_the_br_ten_035_grammar():
    """Four facts, measured, not asserted in prose: it validates, it is 22
    characters against a limit of 24, its pad is 4 against a limit of 8, and
    the literal prefix a clerk reads is `JE-`."""
    numbering.validate_format(RULED)  # raises if the grammar refuses it
    assert len(RULED) == 22
    assert numbering.MAX_FORMAT_LENGTH == 24
    assert numbering.pad_length(RULED) == 4
    assert numbering.MAX_PAD == 8
    assert numbering.literal_prefix(RULED) == "JE-"


def test_the_worked_figure_the_po_was_shown():
    """*An entry dated 2 August 2026, first of the series, is `JE-080226-0001`.*

    That is the sentence a human can check, and it is what makes the ruling
    testable at all: `MMDDYY` is an ORDER as much as a set of tokens, and the
    three obvious wrong orders (`DDMMYY`, `YYMMDD`, `YYYYMMDD`) all render
    strings of the same shape."""
    assert numbering.render(RULED, 1, date(2026, 8, 2)) == "JE-080226-0001"
    # The counter, not the date, is what moves inside one day.
    assert numbering.render(RULED, 43, date(2026, 8, 2)) == "JE-080226-0043"
    # A day in December, to prove `{DD}` is the day and `{MM}` the month.
    assert numbering.render(RULED, 7, date(2026, 12, 31)) == "JE-123126-0007"


def test_a_counter_that_outgrows_its_pad_keeps_every_digit():
    """`render` never truncates (BR-TEN-035 — a truncated counter could
    collide). At 12,345 the string is 23 characters and still under the limit;
    the number a clerk reads simply gets one digit longer."""
    value = numbering.render(RULED, 12345, date(2026, 8, 2))
    assert value == "JE-080226-12345"
    assert len(value) == 15


def test_the_number_does_not_sort_chronologically_and_that_is_pinned():
    """⚠ **THIS ASSERTS THE PROBLEM, ON PURPOSE.**

    `MMDDYY` puts the MONTH first, so text order is not time order. The
    blueprint's own example: `JE-011526-0001` sorts BEFORE `JE-020325-0001`
    although it is **eleven months later**. The PO ruled the format knowing it.

    A test that asserted only the happy path would leave the next lane free to
    "fix" a journal list into ordering by this string — which cannot work and
    would reorder the books on screen. This pins the behaviour, so changing it
    is a deliberate act with a red test in front of it.

    The product's own answer is `P0.10`'s: **order by `entry_date`.**
    """
    january_2026 = numbering.render(RULED, 1, date(2026, 1, 15))
    february_2025 = numbering.render(RULED, 1, date(2025, 2, 3))
    assert january_2026 == "JE-011526-0001"
    assert february_2025 == "JE-020325-0001"

    # Text order puts the 2026 entry FIRST...
    assert sorted([february_2025, january_2026]) == [january_2026, february_2025]
    # ...and it is in fact eleven months LATER than the other one.
    assert date(2026, 1, 15) > date(2025, 2, 3)
