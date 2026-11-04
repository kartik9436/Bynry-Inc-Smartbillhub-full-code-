# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-CUS-9789 — Cancel move-in closed the account and refunded
#           NOTHING when the money taken at the counter was still processing.
#           DEF-CUS-9790 — after Change move-in date the move-in itself still
#           read the OLD date on the details view and the Move-ins list.
# Rules:    CR-171 §6.2 J6 / J7 · §9.FLOW (a committed move-in's date is
#           `accounts.opened_at`) · BR-CUS-152 · BR-PAY-021 (posting vs
#           clearing) · US-PAY-004 (Cancel only while processing) · decision
#           log 2026-10-06 *"WHICH READ COUNTS A PROCESSING DEPOSIT"* · CLAUDE.md
#           hard rules 4 · 5 · 7 · hard-won law 14
# Tests:    this file (SQLite + the cancel on PostgreSQL 16, see below)
# ───────────────────────────────────────────────────────
"""**Money that has not arrived is called off, not refunded; a moved date moves
everywhere a clerk reads it.**

DEF-CUS-9789, M1's figure: Avery pays **$175.00 by cheque 2041** at move-in —
$150.00 deposit + $25.00 connection — and it has not cleared. Cancelling the
move-in calls off BOTH payments through payments' own Cancel (each original
`processing → cancelled` plus a −amount `cancelled` row, audited), refunds
nothing (nothing arrived), releases nothing, posts nothing, closes the account.

DEF-CUS-9790: a committed move-in moved from 1 August to 3 August reads
3 August on the details view (chip and *Moved in on*) and on the Move-ins list.

RED FIRST (law 7): on the tip before this change the cancel test read
`called_off` absent and both payments still `processing`; the date tests read
`2026-08-01`.

WHAT WOULD MAKE THESE PASS WRONGLY (law 7, habit 2): payments recorded cleared
(the status is read back as `processing` first); a cancel that only moved a
status (the reversing rows and their amounts are read back); a list read that
happened to sort the row away (the row is found by its number).

PostgreSQL 16:

    DATABASE_URL="postgres://…" DJANGO_SETTINGS_MODULE=config.settings.pgtest \\
      JOBS_EAGER=false pytest -q -p no:xdist tests/test_def_cus_9789_9790_move_in_cancel_and_date.py
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from django.db import connection

from apps.customers import models as customers_models
from apps.customers import move_in_cancel, move_in_flow, move_in_list, move_record_reads, moves
from apps.payments import models as payment_models
from apps.payments.deposit_release_models import DepositRelease
from tests.isolation_helpers import requires_postgres
from tests.test_cr171_mvi_flow_record_doors import _committed
from tests.test_cr171_p1_12_move_in_fees import _move_in, _pay_now, _world
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import audit_rows, brazos, dana, tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db

M1_FEES = [
    {"kind": "deposit", "source": "plan", "amount": "150.00"},
    {"kind": "fee", "source": "plan", "code": "CONN", "amount": "25.00"},
]


def _avery(actor, tenant):
    """$175.00 by cheque 2041, NOT cleared — the wizard's counter default."""
    _unit, _plan, outgoing = _world(actor, tenant)
    result = _move_in(
        actor, outgoing, fees=M1_FEES, payment=_pay_now("175.00", confirmation="2041")
    )
    record = moves.MoveRecord.objects.get(account_id=result["id"], kind=moves.KIND_MOVE_IN)
    return result, record


def _originals(account_id):
    return list(
        payment_models.Payment.objects.filter(
            account_id=account_id, reverses_payment__isnull=True
        ).order_by("amount")
    )


def _reversing(account_id):
    return sorted(
        (row.amount, row.status)
        for row in payment_models.Payment.objects.filter(
            account_id=account_id, reverses_payment__isnull=False
        )
    )


# ═══════════════════════════════════════════════════════════════════════════
# DEF-CUS-9789 · CANCEL CALLS OFF UNCLEARED COUNTER MONEY
# ═══════════════════════════════════════════════════════════════════════════
def test_avery_cancel_calls_off_the_uncleared_cheque_and_refunds_nothing(brazos, dana, audit_rows):
    with tenant_ctx(brazos):
        result, record = _avery(dana, brazos)
        account_id = result["id"]
        before = _originals(account_id)
        assert [(p.amount, p.status) for p in before] == [
            (Decimal("25.000000"), payment_models.PAYMENT_PROCESSING),
            (Decimal("150.000000"), payment_models.PAYMENT_PROCESSING),
        ], "the fixture must hold the cheque UNCLEARED, as the wizard records it"

        preview = move_in_cancel.preview(record.move_no)
        assert preview["allowed"] is True, preview["refusal"]
        assert sorted(line["amount"] for line in preview["reverses"]["called_off"]) == [
            "150.0000",
            "25.0000",
        ]
        assert {line["confirmation"] for line in preview["reverses"]["called_off"]} == {"2041"}
        assert preview["reverses"]["refund"]["amount"] == "0.0000"

        answer = move_in_cancel.cancel(dana, record.move_no)

        assert [(p.amount, p.status) for p in _originals(account_id)] == [
            (Decimal("25.000000"), payment_models.PAYMENT_CANCELLED),
            (Decimal("150.000000"), payment_models.PAYMENT_CANCELLED),
        ]
        assert _reversing(account_id) == [
            (Decimal("-150.000000"), payment_models.PAYMENT_CANCELLED),
            (Decimal("-25.000000"), payment_models.PAYMENT_CANCELLED),
        ]
        # Nothing arrived, so nothing is refunded, released or posted.
        assert not payment_models.Refund.objects.filter(account_id=account_id).exists()
        assert not DepositRelease.objects.filter(account_id=account_id).exists()
        assert not payment_models.Payment.objects.filter(
            account_id=account_id, journal_entry_id__isnull=False
        ).exists()
        account = customers_models.Account.objects.get(pk=account_id)
        assert move_in_cancel.is_cancelled(account)
    assert answer["refund"] is None
    assert answer["deposit_released"] is None
    assert sorted(line["amount"] for line in answer["called_off"]) == ["150.0000", "25.0000"]
    assert all(line["reversing_payment_no"] for line in answer["called_off"])
    cancelled = [r for r in audit_rows if r.get("action") == "payment.cancelled"]
    assert len(cancelled) == 4, "both originals and both reversing rows are audited (hard rule 7)"
    closed = [r for r in audit_rows if r.get("action") == "account.move_in_cancelled"]
    assert len(closed) == 1 and len(closed[0]["after"]["called_off"]) == 2


def test_a_payment_payments_would_not_cancel_refuses_the_whole_cancel(brazos, dana, monkeypatch):
    """A processing payment its own Cancel refuses: the move-in cancel is
    refused before anything is written — never half-done."""
    from apps.payments import cancel as payment_cancel

    with tenant_ctx(brazos):
        result, record = _avery(dana, brazos)
        monkeypatch.setattr(payment_cancel, "refusal_for", lambda p: payment_cancel.REFUSED_MONEY_IS_POSTED)
        preview = move_in_cancel.preview(record.move_no)
        assert preview["allowed"] is False
        assert preview["refusal"]["message_key"] == "customers.moveIn.cancel.paymentNotCallable"
        with pytest.raises(Exception):
            move_in_cancel.cancel(dana, record.move_no)
        account = customers_models.Account.objects.get(pk=result["id"])
        assert not move_in_cancel.is_cancelled(account)
        assert {p.status for p in _originals(result["id"])} == {payment_models.PAYMENT_PROCESSING}


def test_the_statement_the_po_signed_on_2026_10_06(brazos, dana, monkeypatch):
    """**PO, verbatim, 2026-10-06: *"S1–S8 approve"*** — S4, shown as:
    *"Avery paid $175.00 by cheque 2041 at move-in and it has not cleared.
    Cancelling calls off the cheque — nothing is refunded because nothing
    arrived — and closes the account. A cleared payment is refunded as before:
    Nilesh's cleared $175.00 → one $175.00 refund."* with the shown addendum
    *"(Also: every uncleared payment on that account is called off, and if one
    can't be, the whole cancel is refused.)"*

    Three households, one per clause: Avery (uncleared, called off), Nilesh
    (cleared, ONE $175.00 refund), and a third whose payment Cancel refuses
    (the whole cancel refused, nothing written).
    """
    from apps.payments import cancel as payment_cancel
    from tests.test_cr171_oq_cus_12790_cancel_refund import _nilesh

    with tenant_ctx(brazos):
        # Avery — $175.00 by cheque 2041, not cleared.
        avery, avery_record = _avery(dana, brazos)
        paid = _originals(avery["id"])
        assert sum(p.amount for p in paid) == Decimal("175.000000")
        assert {p.confirmation for p in paid} == {"2041"}
        answer = move_in_cancel.cancel(dana, avery_record.move_no)
        # Every uncleared payment on the account is called off …
        assert {p.status for p in _originals(avery["id"])} == {payment_models.PAYMENT_CANCELLED}
        assert sum(amount for amount, _s in _reversing(avery["id"])) == Decimal("-175.000000")
        # … nothing is refunded because nothing arrived …
        assert not payment_models.Refund.objects.filter(account_id=avery["id"]).exists()
        # … and the account is closed.
        assert move_in_cancel.is_cancelled(customers_models.Account.objects.get(pk=avery["id"]))
        assert answer["refund"] is None

        # Nilesh — $175.00 cleared → ONE $175.00 refund, as before.
        nilesh, nilesh_record = _nilesh(dana, brazos)
        move_in_cancel.cancel(dana, nilesh_record.move_no)
        assert [
            (row.amount, row.status)
            for row in payment_models.Refund.objects.filter(account_id=nilesh["id"])
        ] == [(Decimal("175.000000"), payment_models.REFUND_REQUESTED)]

        # If one can't be called off, the whole cancel is refused.
        third, third_record = _avery(dana, brazos)
        monkeypatch.setattr(
            payment_cancel, "refusal_for", lambda p: payment_cancel.REFUSED_MONEY_IS_POSTED
        )
        refused = move_in_cancel.preview(third_record.move_no)
        assert refused["allowed"] is False
        assert refused["refusal"]["message_key"] == "customers.moveIn.cancel.paymentNotCallable"
        with pytest.raises(Exception):
            move_in_cancel.cancel(dana, third_record.move_no)
        assert not move_in_cancel.is_cancelled(customers_models.Account.objects.get(pk=third["id"]))
        assert {p.status for p in _originals(third["id"])} == {payment_models.PAYMENT_PROCESSING}


@requires_postgres
def test_pg_avery_cancel_commits_the_call_off_and_the_close_together(brazos, dana):
    assert connection.vendor == "postgresql"
    with tenant_ctx(brazos):
        result, record = _avery(dana, brazos)
        move_in_cancel.cancel(dana, record.move_no)
        assert {p.status for p in _originals(result["id"])} == {payment_models.PAYMENT_CANCELLED}
        assert _reversing(result["id"]) == [
            (Decimal("-150.000000"), payment_models.PAYMENT_CANCELLED),
            (Decimal("-25.000000"), payment_models.PAYMENT_CANCELLED),
        ]
        assert not payment_models.Refund.objects.filter(account_id=result["id"]).exists()
        assert move_in_cancel.is_cancelled(customers_models.Account.objects.get(pk=result["id"]))


@requires_postgres
def test_pg_a_refusal_after_the_call_off_rolls_the_call_off_back(brazos, dana, monkeypatch):
    """Law 14: the call-off is inside the cancel's transaction. A refusal after
    it (the audit write here) rolls the payments back to `processing` on
    PostgreSQL, and the connection still answers."""
    from apps.customers import services

    with tenant_ctx(brazos):
        result, record = _avery(dana, brazos)

        def refused(*args, **kwargs):
            raise RuntimeError("refused for the proof")

        monkeypatch.setattr(services, "_audit", refused)
        with pytest.raises(RuntimeError):
            move_in_cancel.cancel(dana, record.move_no)
        assert {p.status for p in _originals(result["id"])} == {payment_models.PAYMENT_PROCESSING}
        assert _reversing(result["id"]) == []
        assert not move_in_cancel.is_cancelled(customers_models.Account.objects.get(pk=result["id"]))


# ═══════════════════════════════════════════════════════════════════════════
# DEF-CUS-9790 · THE NEW DATE ON EVERY MOVE-IN SURFACE
# ═══════════════════════════════════════════════════════════════════════════
def test_the_details_view_reads_the_changed_date(brazos, dana):
    with tenant_ctx(brazos):
        _unit, _result, record = _committed(dana, brazos)
        assert record.effective_on == date(2026, 8, 1)
        move_in_flow.change_move_in_date(dana, record.move_no, "2026-08-03")
        detail = move_record_reads.record_detail(record.move_no)
    assert detail["effective_on"] == "2026-08-03"
    assert detail["what_happened"]["moved_in_on"]["value"] == "2026-08-03"
    assert detail["facts"]["details"]["moved_in_on"] == "2026-08-03"


def test_the_move_ins_list_reads_the_changed_date(brazos, dana):
    with tenant_ctx(brazos):
        _unit, _result, record = _committed(dana, brazos)
        move_in_flow.change_move_in_date(dana, record.move_no, "2026-08-03")
        answer = move_in_list.move_ins_list(q=record.move_no, sort="move_in_date")
    rows = [row for row in answer["rows"] if row.get("move_no") == record.move_no]
    assert len(rows) == 1, answer["rows"]
    assert rows[0]["move_in_date"] == "2026-08-03"


def test_a_move_out_record_keeps_its_own_date():
    """The helper only reads the account for a move-IN."""
    from types import SimpleNamespace

    row = SimpleNamespace(kind=moves.KIND_MOVE_OUT, effective_on=date(2026, 9, 30))
    account = SimpleNamespace(opened_at=date(2026, 1, 1))
    assert move_record_reads.move_in_date_of(row, account) == date(2026, 9, 30)
