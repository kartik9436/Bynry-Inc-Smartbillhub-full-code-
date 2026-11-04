# ── Trace ──────────────────────────────────────────────
# Change:  CR-171-BRC10 P1.14 — the first bill carries every fee line the
#          move-in recorded and reads the counter payment (lane MVI-MONEY).
# Rules:   BR-BIL-012 (first bill one-time lines) · BR-BIL-007 (a fee is a
#          charge code) · BR-BIL-010 (a fee line carries its code's GL) ·
#          BR-PAY-012 (a deposit-purpose payment satisfies the deposit line) ·
#          B4.2 ❄️ (fees never taxed) · OQ-BIL-12788 CLOSED (a) 2026-10-05
# Golden:  none moved — tests/test_us_bil_010_first_bill.py is UNMODIFIED and
#          its WE-6 figures are re-asserted green beside this file
# ───────────────────────────────────────────────────────
"""**The first bill of a move-in that quoted a Fees table.**

The worked figure is J4's (decision log 2026-10-05): DEPOSIT **$150.00** +
CONNECT **$25.00** + RUSH **$40.00** = **$215.00** of one-time lines. The
deposit comes from the plan minus what was paid (`deposit_line_for`, unchanged);
the two FEES come from the lines the move recorded, and they REPLACE the
one-time tab's default connection charge — so `CONN` is billed once, not twice.

The account is built the way `test_us_bil_010_first_bill.py` builds it, and the
move's record and lines are written exactly as `services._move_in` writes them,
so this file proves the READ without re-running a whole move-in (that is
`test_cr171_p1_12_move_in_fees.py`'s job).
"""

from decimal import Decimal

import pytest

from apps.billing import first_bill
from apps.billing.exceptions import BillingRuleError
from apps.customers import moves
from apps.customers.move_in_extras import MoveFeeLine
from apps.rating import models as rating_models
from apps.rating.pricing.contracts import TAX_BASE_KINDS
from tests.test_us_bil_005_issue import a_run
from tests.test_us_bil_010_first_bill import (
    CONN_AMOUNT,
    MOVED_IN_ON,
    _a_conn_charge,
    _a_deposit_rule,
    _a_first_bill_world,
    _prepare,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403
from tests.test_us_met_helpers import brazos, dana, tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db

RUSH = Decimal("40.0000")


def _rush(tenant, gl_account_id):
    row, _ = rating_models.Charge.objects.get_or_create(
        tenant=tenant, code="RUSH", defaults={"name": "Same-day connection", "charge_type": "one_time"}
    )
    row.amount = RUSH
    row.gl_account_id = gl_account_id
    row.save()
    return row


def _recorded(tenant, account, lines):
    record = moves.record_move(kind=moves.KIND_MOVE_IN, account_id=account.id, effective_on=MOVED_IN_ON)
    for seq, (kind, code, amount, charge) in enumerate(lines, start=1):
        MoveFeeLine.objects.create(
            tenant=tenant,
            move_record_id=record["move_record_id"],
            seq=seq,
            kind=kind,
            source="plan" if seq < 3 else "charge_code",
            charge_code_id=charge.id if charge is not None else None,
            code=code,
            description=charge.name if charge is not None else "Security deposit",
            amount=amount,
        )
    return record


def _one_timers(data, account):
    with_lines = first_bill.first_bill_data(
        data, moved_in_on=MOVED_IN_ON, account_type_id=account.account_type_id
    )
    return [line for line in with_lines.fees if line.kind in ("fee", "deposit")]


def test_p1_14__j4s_215_lands_on_the_first_bill_and_conn_is_billed_once(brazos, dana):
    with tenant_ctx(brazos):
        _cycle, plan, account = _a_first_bill_world(brazos, dana)
        _a_deposit_rule(brazos, plan, account)
        conn = _a_conn_charge(brazos)
        rush = _rush(brazos, conn.gl_account_id)
        _recorded(
            brazos,
            account,
            [
                ("deposit", "DEPOSIT", Decimal("150.0000"), None),
                ("fee", "CONN", CONN_AMOUNT, conn),
                ("fee", "RUSH", RUSH, rush),
            ],
        )
        lines = _one_timers(_prepare(account), account)

    assert [(line.kind, line.description, line.amount) for line in lines] == [
        ("deposit", first_bill.DEPOSIT_DESCRIPTION, Decimal("150.00")),
        ("fee", "Connection charge", CONN_AMOUNT),
        ("fee", "Same-day connection", RUSH),
    ]
    assert sum(line.amount for line in lines) == Decimal("215.00")
    # OQ-BIL-12788 (a) + B4.2 — structurally out of the tax base, and flagged so.
    assert all(line.kind not in TAX_BASE_KINDS for line in lines)
    assert all(line.taxable is False for line in lines)
    assert [str(line.charge_id) for line in lines if line.kind == "fee"] == [str(conn.id), str(rush.id)]


def test_p1_14__the_draft_issues_the_215_untaxed(brazos, dana):
    """Through the same `calculate_first_bill` a real draft uses."""
    with tenant_ctx(brazos):
        _cycle, plan, account = _a_first_bill_world(brazos, dana)
        _a_deposit_rule(brazos, plan, account)
        conn = _a_conn_charge(brazos)
        rush = _rush(brazos, conn.gl_account_id)
        _recorded(
            brazos,
            account,
            [("fee", "CONN", CONN_AMOUNT, conn), ("fee", "RUSH", RUSH, rush)],
        )
        draft = first_bill.calculate_first_bill(
            _prepare(account),
            bill_run=a_run(brazos, key="2026-06|cr171-first"),
            moved_in_on=MOVED_IN_ON,
            account_type_id=account.account_type_id,
        )
        one_timers = {
            line.description: line.amount
            for line in draft.lines.all()
            if line.kind in ("fee", "deposit")
        }
    assert one_timers == {
        first_bill.DEPOSIT_DESCRIPTION: Decimal("150.00"),
        "Connection charge": CONN_AMOUNT,
        "Same-day connection": RUSH,
    }


def test_p1_14__an_account_no_fee_table_opened_keeps_the_default_conn(brazos, dana):
    """§8.3 — the old wizard's first bill is unchanged: deposit + CONN."""
    with tenant_ctx(brazos):
        _cycle, plan, account = _a_first_bill_world(brazos, dana)
        _a_deposit_rule(brazos, plan, account)
        _a_conn_charge(brazos)
        lines = _one_timers(_prepare(account), account)
    assert [(line.kind, line.amount) for line in lines] == [
        ("deposit", Decimal("150.00")),
        ("fee", CONN_AMOUNT),
    ]


def test_p1_14__a_recorded_fee_with_no_gl_is_refused_at_draft(brazos, dana):
    with tenant_ctx(brazos):
        _cycle, _plan, account = _a_first_bill_world(brazos, dana)
        _a_conn_charge(brazos)
        rush = _rush(brazos, None)
        _recorded(brazos, account, [("fee", "RUSH", RUSH, rush)])
        with pytest.raises(BillingRuleError) as raised:
            _one_timers(_prepare(account), account)
    assert raised.value.br_ref == "BR-BIL-010"


def test_p1_14__a_waived_deposit_is_not_billed_on_the_first_bill(brazos, dana):
    """BR-CUS-1050 — a deposit a clerk waived is not owed, so the first bill
    must not charge it. `DEF-BIL-9709` (red first: a waived $150.00 billed)."""
    with tenant_ctx(brazos):
        _cycle, plan, account = _a_first_bill_world(brazos, dana)
        _a_deposit_rule(brazos, plan, account)
        _a_conn_charge(brazos)
        account.deposit_waived_amount = Decimal("150.0000")
        account.deposit_waive_reason = "Hardship"
        account.save(update_fields=["deposit_waived_amount", "deposit_waive_reason"])
        lines = _one_timers(_prepare(account), account)
    assert [line.kind for line in lines] == ["fee"], "a waived $150.00 deposit billed anyway"


def test_the_statement_the_po_signed_on_2026_10_06(brazos, dana):
    """⚖️ THE HUMAN SIGN-OFF, ASSERTED SO DRIFT GOES RED (PO 2026-10-06,
    decision log *"SIX MOVE-IN MONEY FILES SIGNED"*, verbatim: *"Money-file
    review: approve these six? - all good - go ahead"*). Statement 3 of six,
    exactly as shown:

    *"Rosa's first bill shows the $25.00 and $40.00 fees once each, untaxed,
    plus the $150.00 deposit unless she already paid it. A deposit the clerk
    waived for hardship is not charged."*

    One account, three states, in the order that lets one account show all
    three: nothing paid → the deposit is billed; waived → it is not; the waive
    lifted and $150.00 paid as deposit → it is not.
    """
    from apps.payments import models as payment_models
    from tests.test_us_pay_007_credit import _pay

    with tenant_ctx(brazos):
        _cycle, plan, account = _a_first_bill_world(brazos, dana)
        _a_deposit_rule(brazos, plan, account)
        conn = _a_conn_charge(brazos)
        rush = _rush(brazos, conn.gl_account_id)
        _recorded(brazos, account, [("fee", "CONN", CONN_AMOUNT, conn), ("fee", "RUSH", RUSH, rush)])

        unpaid = _one_timers(_prepare(account), account)

        account.deposit_waived_amount = Decimal("150.0000")
        account.deposit_waive_reason = "Hardship"
        account.save(update_fields=["deposit_waived_amount", "deposit_waive_reason"])
        waived = _one_timers(_prepare(account), account)

        account.deposit_waived_amount = None
        account.deposit_waive_reason = None
        account.save(update_fields=["deposit_waived_amount", "deposit_waive_reason"])
        _pay(dana, account, Decimal("150.00"), purpose=payment_models.PURPOSE_DEPOSIT)
        paid = _one_timers(_prepare(account), account)

    fees = [("fee", Decimal("25.00")), ("fee", Decimal("40.00"))]
    # The $25.00 and $40.00 fees once each, untaxed, plus the $150.00 deposit.
    assert [(line.kind, line.amount) for line in unpaid] == [("deposit", Decimal("150.00")), *fees]
    assert all(line.taxable is False and line.kind not in TAX_BASE_KINDS for line in unpaid)
    # A deposit the clerk waived for hardship is not charged.
    assert [(line.kind, line.amount) for line in waived] == fees
    # Unless she already paid it.
    assert [(line.kind, line.amount) for line in paid] == fees
