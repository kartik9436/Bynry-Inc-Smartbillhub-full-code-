# ── Trace ──────────────────────────────────────────────
# Journey:  08-qa/01-e2e/journeys/JPAYLOCKBOX-a-store-file-on-a-monday-morning.md
#           check **B** — *"Every created payment's `posted_at` AND `cleared_at`
#           is the day the STORE took the money … and NOT the day of the
#           import."*
# Defect:   `DEF-PAY-6294`
# Rules:    `BR-PAY-033` · `BR-PAY-021` · `OQ-131`'s ruling — lateness is judged
#           on the day the money ARRIVED
# Change:   `CR-135-BRC07` `P1.14`
# ───────────────────────────────────────────────────────
"""The date on an imported payment is the file's, not the importer's clock.

⚠ **THIS ASSERTS A VALUE, AND THE TWO TESTS THAT ALREADY COVER THIS ADAPTER
ASSERT A KEY — WHICH IS WHY THEY PASSED OVER A LIVE DEFECT.**
`test_every_column_reaches_the_payload_and_none_is_dropped_in_the_adapter`
builds its cells as `f"x-{target}"` and asserts `"paid_at" in payload`. Both
halves are true while `payload["paid_at"]` is **None**, because a string has no
`.year` and `_payment_moment` answered `None` to everything stage 2 gives it.

**What that cost, measured rather than reasoned:** 72 payments imported on
2026-09-23 from a file whose `WHEN` column read `09/19/2026` and `09/20/2026`
were all stored `posted_at = cleared_at = 2026-09-23`. A customer who paid at
the store on the Friday before a Monday due date is recorded as paying two days
late, and `BR-PAY-021` charges them for it.

⚠ **THE CELL BELOW IS THE EXACT SHAPE `import_run_rows.mapped` HOLDS**, taken
off a real row of run `IMP-260923-02` rather than invented:
`{"amount": "25.00", "paid_on": "2026-09-19", "reference": "RG100000", …}` —
stage 2 writes `_parse_date`'s **ISO STRING**, never a `date` object. A test
that hands this function a `date` is testing a caller that does not exist.
"""
from __future__ import annotations

from datetime import date, datetime

import pytest

from apps.metering import import_runs


class _Run:
    id = "00000000-0000-0000-0000-000000000000"
    file_name = "ruiz-grocery-repaired.csv"


#: What stage 2 actually writes into `import_run_rows.mapped`, verbatim.
STAGE_TWO_CELL = "2026-09-19"


def test_a_stage_two_date_cell_becomes_an_instant_on_that_day():
    """The ISO STRING stage 2 stores, not a `date` object a caller invented."""
    moment = import_runs._payment_moment(STAGE_TWO_CELL)
    assert moment is not None, (
        "a stage-2 date cell is an ISO string and this returned None for it, so "
        "every imported payment falls back to the importer's business day"
    )
    assert moment.date() == date(2026, 9, 19)


def test_a_date_object_still_works_and_a_datetime_passes_through():
    """The two shapes that already worked keep working — this is a widening."""
    assert import_runs._payment_moment(date(2026, 9, 19)).date() == date(2026, 9, 19)
    already = datetime(2026, 9, 19, 8, 40)
    assert import_runs._payment_moment(already) is already


@pytest.mark.parametrize("cell", ["", "   ", "not-a-date", "09/19/26", None])
def test_an_unreadable_cell_is_none_rather_than_a_guess(cell):
    """`None` means *the file did not say*, and the writer then falls back to the
    operator's business day — the PO's 2026-08-12 ruling, which *"forgives
    nothing"*. Guessing a day here would be worse than the defect this file is
    about. ⚠ `09/19/26` is deliberately in this list: a two-digit year is NOT
    ISO and must not be read as year 26 (`DEF-MET-6291`)."""
    assert import_runs._payment_moment(cell) is None


def test_the_adapter_carries_the_day_through_to_the_writers_payload():
    """End of the join: the row as stage 2 stored it → the payload the writer
    takes. This is the assertion the two existing adapter tests cannot make,
    because they check that the KEY is present and never what is behind it."""
    mapped = {
        "account_ref": "A-10432",
        "amount": "25.00",
        "paid_on": STAGE_TWO_CELL,
        "reference": "RG100000",
    }
    payload = import_runs._payment_payload_from(
        mapped, run=_Run(), row_no=1, recorded_at=datetime(2026, 9, 23, 12, 0)
    )
    assert payload["paid_at"] is not None, (
        "the row said 2026-09-19 and the payload carries no day, so "
        "create_payment_from_import will post this money on the import date"
    )
    assert payload["paid_at"].date() == date(2026, 9, 19)
    # ⚠ **AND IT MUST NOT BE THE FALLBACK.** A payload whose `paid_at` equalled
    # `recorded_at` would pass the line above on a file dated the import day and
    # hide the defect again the moment the fixture's dates moved.
    assert payload["paid_at"].date() != payload["recorded_at"].date()
