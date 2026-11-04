"""**DEF-CUS-9726 — ONE definition of "the opening read for this move-in".**

The chip (`move_in_list.status_of_record`, and the list's filter and tile)
said *Waiting on a read* because a meter had no committed read ON OR AFTER
the move-in date, while the record's own reads table (`opening_reads`, the
*Opening reads* tile and *Still open*) capped reads AS OF that date and
counted an OLDER head — the previous occupant's last read — as this move-in's
opening read. Reproduced on lane DETAIL's MVI-26-0004: tiles *3 of 3*, chip
*Waiting on a read*, nothing on *Still open*.

The definition both now read (decision log 2026-10-05, *"DEF-CUS-9726"*):
**a meter's opening read for a move-in is its FIRST committed read dated on or
after the move-in date.** A read dated before it is the unit's *last read*
(image 24 draws the two in separate columns), never this tenancy's opening.

⚠ **WHAT WOULD MAKE THESE PASS WRONGLY** (law 7, habit 2):

  * **A fixture with no old read.** The bug needs a head BEFORE the move-in;
    E-9726 carries one, dated two days earlier, so the as-of read has
    something to mistake for an opening read.
  * **Agreement by both being empty.** The case asserts the chip is
    *Waiting on a read* AND the table names exactly the one unread meter, so
    the two cannot agree by each saying nothing.
  * **The newest read standing in for the opening.** A cycle read twenty days
    later must not replace the opening read the clerk took three days in.
"""

from datetime import timedelta

import pytest

from apps.customers import move_in_list, move_record_reads

from tests.test_cr171_p1_04_move_ins_list import TODAY, _asset_id, _committed, _rows, _unit
from tests.test_us_met_reads_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_reads_helpers import brazos, commit_read, dana, seed_config, tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db


def _two_meter_move_in(actor, tenant):
    seed_config()
    unit = _unit(
        actor, tenant, "DEF-9726",
        meters=(("E-9726", "electric", "kWh"), ("W-9726", "water", "kgal")),
        services=("electric", "water"),
    )
    on = TODAY - timedelta(days=2)
    # The previous occupant's last read on E — BEFORE this move-in.
    commit_read(actor, _asset_id(unit, "E-9726"), day=(on - timedelta(days=2)).isoformat(), value="3817")
    # W is read on the move-in day itself (the move-in's own opening read).
    _account, record = _committed(actor, unit, name="Read, Opal", on=on, reads=(("W-9726", "2531"),))
    return unit, on, record


def _opening(page):
    return {row["register"].split(" · ")[0]: row for row in page["opening_reads"]["rows"]}


def test_the_chip_and_the_reads_table_agree_on_one_record(brazos, dana):
    with tenant_ctx(brazos):
        _unit_row, _on, record = _two_meter_move_in(dana, brazos)
        page = move_record_reads.record_detail(record["move_no"])
        assert page["status"] == move_in_list.STATUS_WAITING_ON_A_READ
        reads = _opening(page)
        assert reads["W-9726"]["how"] == move_record_reads.HOW_READ
        assert reads["E-9726"]["how"] == move_record_reads.HOW_NOT_ESTIMATED, reads["E-9726"]
        assert page["tiles"]["opening_reads"]["taken"] == 1
        assert page["tiles"]["opening_reads"]["of"] == 2
        still = [row["register"] for row in page["still_open"] if row["kind"] == "opening_read"]
        assert still == ["E-9726"]
        # The list row's cell says the same of the same record.
        row = next(r for r in _rows()["rows"] if r["reference"] == record["move_no"])
        assert row["status"] == move_in_list.STATUS_WAITING_ON_A_READ


def test_a_later_read_completes_it_and_the_first_one_is_the_opening(brazos, dana):
    with tenant_ctx(brazos):
        unit, on, record = _two_meter_move_in(dana, brazos)
        e = _asset_id(unit, "E-9726")
        commit_read(dana, e, day=(on + timedelta(days=1)).isoformat(), value="3829")
        commit_read(dana, e, day=(on + timedelta(days=20)).isoformat(), value="4100")
        page = move_record_reads.record_detail(record["move_no"])
        assert page["status"] == move_in_list.STATUS_COMPLETED
        reads = _opening(page)
        assert reads["E-9726"]["how"] == move_record_reads.HOW_READ
        assert reads["E-9726"]["read_at"] == (on + timedelta(days=1)).isoformat()
        assert float(reads["E-9726"]["reading"]) == 3829
        assert page["tiles"]["opening_reads"]["taken"] == page["tiles"]["opening_reads"]["of"] == 2
        assert not [row for row in page["still_open"] if row["kind"] == "opening_read"]
