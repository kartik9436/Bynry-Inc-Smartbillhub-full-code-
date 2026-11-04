# ── Trace ──────────────────────────────────────────────
# Change:   CR-171-BRC10 lane RULINGS — `OQ-CUS-12790` CLOSED (a).
# Rules:    PO ruling, decision log *"FOUR PO RULINGS IN ONE REPLY"* (4),
#           verbatim: *"Release the deposit and refund the full $175.00 as one
#           refund, approved by Finance as usual."* · BR-PAY-012 · BR-PAY-014 ·
#           US-PAY-002 TC-1 · CLAUDE.md hard rules 4, 5, 6, 7 · hard-won law 14
# Tests:    this file (SQLite + the `requires_postgres` cases on PostgreSQL 16)
# ───────────────────────────────────────────────────────
"""**A cancelled move-in refunds its deposit WITH the rest, as ONE refund.**

THE PO's WORKED CASE: Nilesh pays **$175.00 by check 1043** — a **$150.00**
deposit and a **$25.00** connection fee — and his move-in is cancelled before
any bill. One refund request for **$175.00** goes to Finance's approval; the
$150.00 leaves the deposit liability for customer credit in the books
(DR 2300 / CR 2400, balanced), the register reads $0.00, and audit rows record
the release and the refund.

RED FIRST (law 7): on the tip, the preview refused with `OQ-CUS-12790` and the
press raised `NotImplementedError('OQ-CUS-12790')`.

WHAT WOULD MAKE THESE PASS WRONGLY (law 7, habit 2): asserting the answer and
not the rows (every case reads the refund, the release, the journal lines and
the register back); a refund of $175.00 with the books still holding $150.00
of deposit (the journal lines are read and footed); two refunds that add up to
$175.00 (the count of refund rows is asserted to be ONE).

Run the PostgreSQL cases:

    DATABASE_URL="postgres://postgres@127.0.0.1:55433/<db>?sslmode=disable" \\
      DJANGO_SETTINGS_MODULE=config.settings.pgtest JOBS_EAGER=false \\
      pytest -q -p no:xdist tests/test_cr171_oq_cus_12790_cancel_refund.py
"""

from __future__ import annotations

from datetime import datetime, timezone as dt_timezone
from decimal import Decimal

import pytest
from django.db import connection

from apps.customers import models as customers_models
from apps.customers import move_in_cancel, moves
from apps.payments import deposit_release
from apps.payments import models as payment_models
from apps.payments.deposit_release_models import DepositRelease
from apps.payments.exceptions import PaymentRuleError
from tests.isolation_helpers import requires_postgres
from tests.test_cr094_wh_deposit import A_DEPOSIT, HARDSHIP
from tests.test_cr171_p1_12_move_in_fees import MOVE_IN_DAY, _move_in, _pay_now, _world
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import audit_rows, brazos, dana, tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db

NILESH_FEES = [
    {"kind": "deposit", "source": "plan", "amount": "150.00"},
    {"kind": "fee", "source": "plan", "code": "CONN", "amount": "25.00"},
]


def _nilesh(actor, tenant):
    """$175.00 by check 1043: $150.00 deposit + $25.00 fee, cleared."""
    _unit, _plan, outgoing = _world(actor, tenant)
    result = _move_in(
        actor,
        outgoing,
        fees=NILESH_FEES,
        payment=_pay_now("175.00"),
    )
    record = moves.MoveRecord.objects.get(account_id=result["id"], kind=moves.KIND_MOVE_IN)
    return result, record


def _deposit_lines(release_id):
    from apps.ledger import models as ledger_models

    return list(
        ledger_models.JournalLine.objects.filter(
            journal_entry__posting_key=f"deposit_release|{release_id}|deposit_applied"
        ).values_list("side", "amount")
    )


def test_nilesh_cancels_and_one_refund_of_175_goes_to_finance(brazos, dana):
    with tenant_ctx(brazos):
        result, record = _nilesh(dana, brazos)
        account = customers_models.Account.objects.get(pk=result["id"])
        assert account.deposit_on_file == Decimal("150.000000"), "the fixture must HOLD a deposit"

        preview = move_in_cancel.preview(record.move_no)
        assert preview["allowed"] is True
        assert preview["refusal"] is None
        assert preview["reverses"]["refund"]["amount"] == "175.0000"
        assert preview["reverses"]["refund"]["deposit_released"] == "150.0000"
        assert "OQ-CUS-12790" not in str(preview)

        answer = move_in_cancel.cancel(dana, record.move_no)

        refunds = list(payment_models.Refund.objects.filter(account_id=result["id"]))
        assert [(row.amount, row.status) for row in refunds] == [
            (Decimal("175.000000"), payment_models.REFUND_REQUESTED)
        ]
        release = DepositRelease.objects.get(account_id=result["id"])
        assert release.amount == Decimal("150.0000")
        assert release.reason == "move_in_cancelled"
        lines = _deposit_lines(release.id)
        assert sorted(lines) == [
            ("credit", Decimal("150.000000")),
            ("debit", Decimal("150.000000")),
        ]
        account.refresh_from_db()
        assert account.deposit_on_file == Decimal("0")
        assert move_in_cancel.is_cancelled(account)
    assert answer["refund"]["amount"] == "175.0000"
    assert answer["refund"]["status"] == payment_models.REFUND_REQUESTED
    assert answer["deposit_released"]["amount"] == "150.0000"


def test_every_money_act_of_the_cancel_writes_audit(brazos, dana, audit_rows):
    with tenant_ctx(brazos):
        _result, record = _nilesh(dana, brazos)
        move_in_cancel.cancel(dana, record.move_no)
        actions = {row["action"] if isinstance(row, dict) else row.action for row in audit_rows}
    assert {
        deposit_release.AUDIT_RELEASED,
        "deposit.released",  # customers' register
        "account.move_in_cancelled",
    } <= actions
    assert any(action.startswith("refund") for action in actions), actions


def test_the_refund_waits_for_finance_and_spends_the_whole_credit(brazos, dana):
    """Approval is Finance's (BR-PAY-014): nothing has left until then, and the
    $175.00 credit is exactly what the one request asks for."""
    from apps.payments import selectors as payment_selectors

    with tenant_ctx(brazos):
        result, record = _nilesh(dana, brazos)
        assert payment_selectors.account_credit_position(result["id"]) == Decimal("25.000000")
        move_in_cancel.cancel(dana, record.move_no)
        assert payment_selectors.account_credit_position(result["id"]) == Decimal("175.000000")
        refund = payment_models.Refund.objects.get(account_id=result["id"])
        assert refund.approved_at is None and refund.issued_at is None


def test_the_four_statements_the_po_signed_on_2026_10_05(brazos, dana):
    """⚖️ THE HUMAN SIGN-OFF, ASSERTED SO DRIFT GOES RED (PO ruling (B) of
    2026-10-05, decision log *"FIVE PO RULINGS IN ONE REPLY"*, verbatim:
    *"Nilesh's credit becomes $25.00 + $150.00 = $175.00, and one $175.00
    refund goes to Finance for approval. - (a) Approve all four."*).

    (1) a NEW *deposit released $150.00* row; the original $175.00 payment is
        never edited;
    (2) credit $25.00 + $150.00 = $175.00 and ONE $175.00 refund to Finance;
    (3) no interest on the deposit — exactly $150.00 is released;
    (4) the books entry is dated the day of the cancel, $150.00 from deposits
        held (2300) to customer credit (2400).
    """
    from apps.ledger import models as ledger_models
    from apps.payments import selectors as payment_selectors
    from apps.customers import seams as customers_seams

    with tenant_ctx(brazos):
        result, record = _nilesh(dana, brazos)
        before = {
            row.id: (row.amount, row.status, row.purpose)
            for row in payment_models.Payment.objects.filter(account_id=result["id"])
        }
        assert sum(amount for amount, _s, _p in before.values()) == Decimal("175.000000")
        cancel_day = customers_seams.tenant_today()
        move_in_cancel.cancel(dana, record.move_no)

        # (1) the original payment rows are untouched; one release row is new.
        after = {
            row.id: (row.amount, row.status, row.purpose)
            for row in payment_models.Payment.objects.filter(account_id=result["id"])
        }
        assert after == before
        release = DepositRelease.objects.get(account_id=result["id"])
        # (3) no interest: the release is the deposit, to the cent.
        assert release.amount == Decimal("150.0000")
        # (2) the credit and the ONE refund.
        assert payment_selectors.account_credit_position(result["id"]) == Decimal("175.000000")
        assert [
            row.amount for row in payment_models.Refund.objects.filter(account_id=result["id"])
        ] == [Decimal("175.000000")]
        # (4) dated the cancel day; DR 2300 deposits held / CR 2400 customer credit.
        entry = ledger_models.JournalEntry.objects.get(
            posting_key=f"deposit_release|{release.id}|deposit_applied"
        )
        legs = sorted(
            (line.side, line.ledger_account.code, line.amount)
            for line in ledger_models.JournalLine.objects.filter(journal_entry=entry)
        )
    assert release.released_on == cancel_day
    assert entry.entry_date == cancel_day
    assert legs == [
        ("credit", "2400", Decimal("150.000000")),
        ("debit", "2300", Decimal("150.000000")),
    ]


def test_a_cancel_with_no_deposit_releases_nothing(brazos, dana):
    with tenant_ctx(brazos):
        _unit, _plan, outgoing = _world(dana, brazos)
        result = _move_in(
            dana,
            outgoing,
            fees=[{"kind": "fee", "source": "plan", "code": "CONN", "amount": "25.00"}],
            deposit={"decision": "waived", "amount": A_DEPOSIT, "waive_reason": HARDSHIP},
            payment=_pay_now("25.00"),
        )
        record = moves.MoveRecord.objects.get(account_id=result["id"], kind=moves.KIND_MOVE_IN)
        answer = move_in_cancel.cancel(dana, record.move_no)
        assert not DepositRelease.objects.filter(account_id=result["id"]).exists()
    assert answer["deposit_released"] is None
    assert answer["refund"]["amount"] == "25.0000"


def test_a_release_larger_than_the_deposit_held_is_refused_and_writes_nothing(brazos, dana):
    with tenant_ctx(brazos):
        result, record = _nilesh(dana, brazos)
        with pytest.raises(PaymentRuleError):
            deposit_release.release_to_credit(
                dana,
                account_id=result["id"],
                amount=Decimal("150.01"),
                reason="test",
                source_type="test",
                source_id=record.id,
                released_on=MOVE_IN_DAY_DATE,
                posted_at=POSTED,
                idempotency_key="too-much",
            )
        assert not DepositRelease.objects.filter(account_id=result["id"]).exists()


def test_a_replayed_release_releases_once(brazos, dana):
    with tenant_ctx(brazos):
        result, record = _nilesh(dana, brazos)
        kwargs = dict(
            account_id=result["id"],
            amount=Decimal("150.00"),
            reason="test",
            source_type="test",
            source_id=record.id,
            released_on=MOVE_IN_DAY_DATE,
            posted_at=POSTED,
            idempotency_key="once",
        )
        first = deposit_release.release_to_credit(dana, **kwargs)
        second = deposit_release.release_to_credit(dana, **kwargs)
        assert first.created is True and second.created is False
        assert first.release_id == second.release_id
        assert DepositRelease.objects.filter(account_id=result["id"]).count() == 1


def test_the_stub_and_its_question_are_gone():
    """The hold's own expiry test (law 2): the constant that named the open
    question is deleted with the stub, so nothing can raise it again."""
    assert not hasattr(move_in_cancel, "OQ_DEPOSIT")
    assert not hasattr(move_in_cancel, "DEPOSIT_HELD")


MOVE_IN_DAY_DATE = datetime.fromisoformat(MOVE_IN_DAY).date()
POSTED = datetime(2026, 8, 15, 15, tzinfo=dt_timezone.utc)


# ═══════════════════════════════════════════════════════════════════════════
# POSTGRESQL — hard-won law 14
# ═══════════════════════════════════════════════════════════════════════════
@requires_postgres
def test_pg_nilesh_cancel_commits_release_books_register_and_refund_together(brazos, dana):
    assert connection.vendor == "postgresql"
    with tenant_ctx(brazos):
        result, record = _nilesh(dana, brazos)
        move_in_cancel.cancel(dana, record.move_no)
        release = DepositRelease.objects.get(account_id=result["id"])
        assert sorted(_deposit_lines(release.id)) == [
            ("credit", Decimal("150.000000")),
            ("debit", Decimal("150.000000")),
        ]
        assert payment_models.Refund.objects.get(account_id=result["id"]).amount == Decimal(
            "175.000000"
        )
        assert customers_models.Account.objects.get(pk=result["id"]).deposit_on_file == 0


@requires_postgres
def test_pg_a_refused_refund_rolls_the_release_back_too(brazos, dana, monkeypatch):
    """Nothing on the money half is caught: a refusal from the refund writer,
    after the release has written its row and its entry, rolls ALL of it back
    on PostgreSQL — no release, no entry, the register still $150.00, the
    account still open — and the connection still answers."""
    from apps.ledger import models as ledger_models
    from apps.payments import refunds

    def refused(*args, **kwargs):
        raise PaymentRuleError("refused for the proof", br_ref="BR-PAY-014")

    monkeypatch.setattr(refunds, "request_refund", refused)
    with tenant_ctx(brazos):
        result, record = _nilesh(dana, brazos)
        entries = ledger_models.JournalEntry.objects.count()
        with pytest.raises(PaymentRuleError):
            move_in_cancel.cancel(dana, record.move_no)
        assert not DepositRelease.objects.filter(account_id=result["id"]).exists()
        assert ledger_models.JournalEntry.objects.count() == entries
        account = customers_models.Account.objects.get(pk=result["id"])
        assert account.deposit_on_file == Decimal("150.000000")
        assert not move_in_cancel.is_cancelled(account)
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        assert cursor.fetchone() == (1,)


@requires_postgres
def test_pg_the_work_order_catch_after_the_money_keeps_the_money(brazos, dana, monkeypatch):
    """The cancel's ONE catch-and-continue is the work-order loop AFTER the
    commit, each order inside its own SAVEPOINT. A Work door that fails at the
    DATABASE and raises must leave the release and the $175.00 refund standing
    on PostgreSQL, with the order reported, not lost."""
    from apps.customers import seams as customers_seams

    def failing_dispatch(*args, **kwargs):
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1 / 0")

    real_resolve = customers_seams.resolve

    def resolve(module, name, *args, **kwargs):
        if (module, name) == ("work", "set_dispatch_state"):
            return failing_dispatch
        return real_resolve(module, name, *args, **kwargs)

    monkeypatch.setattr(
        move_in_cancel, "_open_orders", lambda move_no: [{"id": 1, "order_no": "WO-1"}]
    )
    monkeypatch.setattr(customers_seams, "resolve", resolve)
    with tenant_ctx(brazos):
        result, record = _nilesh(dana, brazos)
        answer = move_in_cancel.cancel(dana, record.move_no)
        assert answer["warnings"] == [{"code": "work_orders_not_cancelled", "order_no": "WO-1"}]
        assert DepositRelease.objects.filter(account_id=result["id"]).count() == 1
        assert payment_models.Refund.objects.get(account_id=result["id"]).amount == Decimal(
            "175.000000"
        )
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        assert cursor.fetchone() == (1,)
