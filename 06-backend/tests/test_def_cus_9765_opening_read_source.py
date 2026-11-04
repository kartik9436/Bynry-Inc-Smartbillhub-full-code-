# ── Trace ──────────────────────────────────────────────
# Change:   CR-171-BRC10 · lane MVI-POLISH
# Defect:   DEF-CUS-9765 — the move-in details view's Unit & reads table had no
#           Source column (image 24: *Entered at move-in*)
# Tests:    this file
# ───────────────────────────────────────────────────────
"""**An opening-read row says which event its reading was entered for.**

The fact already lives on the reading (`meter_reads.event_context`, written
`move_in` by the move-in's own read door — `test_cr171_mvi_flow_record_doors`);
it was dropped on the way to the record page, so the screen had nothing to draw
image 24's SOURCE from.

RED-FIRST (law 7), on the base before the fix: ``KeyError: 'event'``.

⚠ **WHAT WOULD MAKE THIS PASS WRONGLY:** a row that hard-codes ``move_in``
would pass the read row, so the rows read BEFORE anything was entered are
asserted to carry no event at all.
"""

import pytest

from apps.customers import move_in_flow, move_record_reads, moves
from apps.customers import services as customers_services

from tests import identity_fixtures
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import brazos, dana, tenant_ctx  # noqa: F401
from tests.test_us_met_reads_helpers import seed_config
from tests.test_w9_event_reads import _metered_unit

pytestmark = pytest.mark.django_db


def test_the_opening_read_row_carries_its_event(brazos, dana):
    with tenant_ctx(brazos):
        seed_config()
        unit = _metered_unit(dana, brazos, label="Unit S")
        moved = customers_services.move_in_to_unit(
            dana,
            unit["id"],
            {
                "account_type": "residential",
                "opened_at": "2026-08-20",
                "contact": {"full_name": "Verma, Asha"},
                "customer": identity_fixtures.customer_block("Verma, Asha", account_type="residential"),
            },
        )
        record = moves.MoveRecord.objects.get(pk=moved["move_record_id"])
        before = move_record_reads.record_detail(record.move_no)["opening_reads"]["rows"]
        move_in_flow.enter_opening_reads(dana, record.move_no, [{"meter_no": "M-9101", "value": "43566"}])
        after = move_record_reads.record_detail(record.move_no)["opening_reads"]["rows"]
    # Unread: nothing was entered, so no event — never a guessed one.
    assert all(row.get("event", "absent") in (None, "absent") for row in before)
    read = [row for row in after if row["register"].startswith("M-9101")]
    assert read, after
    assert read[0]["how"] == move_record_reads.HOW_READ
    assert read[0]["event"] == "move_in"
