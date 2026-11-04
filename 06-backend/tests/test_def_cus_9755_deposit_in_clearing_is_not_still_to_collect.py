# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-CUS-9755 — right after the clerk takes the deposit by check at
#           move-in, the move's Billing tab reads "Deposit taken $0.00 · Still
#           to collect $150.00" (M1, MVI-26-0008, check 2041 processing).
# Boundary: DEF-BIL-9751 (ruled 2026-10-06, (a)) counts a processing deposit as
#           PAID for the first bill only; `taken` is still the cleared register.
# ───────────────────────────────────────────────────────
"""A deposit in the drawer is not money still to collect.

`taken` stays what it was — the cleared deposit register (BR-CUS-670) — so
nothing about what counts as held moves. What changes is the third line: the
deposit-purpose money recorded and not yet cleared is served on its own
(`awaiting_clearance`) and is not counted as still to collect.
"""

from decimal import Decimal

import pytest

from apps.customers import move_record_reads
from apps.customers.moves import MoveRecord
from tests.test_cr171_p1_12_move_in_fees import _move_in, _pay_now, _world
from tests.test_us_met_helpers import *  # noqa: F401,F403
from tests.test_us_met_helpers import brazos, dana, tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db


def _money(result):
    record = MoveRecord.objects.get(account_id=result["id"], kind="move_in")
    return move_record_reads.record_detail(record.move_no)["money_taken"]


def test_a_check_not_yet_cleared_is_awaiting_clearance_not_still_to_collect(brazos, dana):
    with tenant_ctx(brazos):
        _unit_, _plan, outgoing = _world(dana, brazos)
        result = _move_in(dana, outgoing, payment=_pay_now("215.00"))
        money = _money(result)
    assert Decimal(money["assessed"]["value"]) == Decimal("150")
    # What counts as taken is unchanged (DEF-BIL-9751 moved the first bill only).
    assert Decimal(money["taken"]["value"] or "0") == Decimal("0")
    assert Decimal(money["awaiting_clearance"]["value"]) == Decimal("150")
    assert Decimal(money["still_to_collect"]["value"]) == Decimal("0")


def test_a_cleared_deposit_has_nothing_awaiting_and_nothing_still_to_collect(brazos, dana):
    with tenant_ctx(brazos):
        _unit_, _plan, outgoing = _world(dana, brazos)
        result = _move_in(dana, outgoing, payment=_pay_now("215.00"))
        money = _money(result)
    assert Decimal(money["taken"]["value"]) == Decimal("150")
    assert money["awaiting_clearance"]["value"] is None
    assert money["awaiting_clearance"]["unavailable"]["code"] == "no_deposit_awaiting_clearance"
    assert Decimal(money["still_to_collect"]["value"]) == Decimal("0")


def test_nothing_paid_is_still_to_collect_in_full(brazos, dana):
    with tenant_ctx(brazos):
        _unit_, _plan, outgoing = _world(dana, brazos)
        result = _move_in(dana, outgoing, payment=_pay_now("65.00"))
        money = _money(result)
    # $65.00 cannot be the deposit (never taken partly) — the whole $150.00 is owed.
    assert money["awaiting_clearance"]["value"] is None
    assert money["awaiting_clearance"]["unavailable"]["code"] == "no_deposit_awaiting_clearance"
    assert Decimal(money["still_to_collect"]["value"]) == Decimal("150")
