# ── Trace ──────────────────────────────────────────────
# Defects:  DEF-PAY-10785 (P1 a1-3 — whose cheque) · DEF-PAY-10786 (P1 a2-2 —
#           the Bank memo is the clerk's to edit) · DEF-PAY-10787 (P1 a2-3 — the
#           search opens on the line's cheque number) · DEF-PAY-10788 (P2 = A —
#           Match to payment and Bank fee from Reconciliation)
# Ruling:   decision log 2026-10-31 "Twelve open payment questions answered
#           (PO)" — *"P1-a1-3 a2-2 a2-3, P2-A"*
# Rules:    BR-PAY-019 · CLAUDE.md rule 4 (never reversed twice), 5 (only the
#           ledger posts), 7 (audit) · B14 rule 31 (an account NUMBER, never an id)
# ───────────────────────────────────────────────────────
"""The tester's lockbox day again, with the four PO answers of 2026-10-31.

The statement's money-out lines now carry the bank's own cheque words —
``RET1029-01 CHK 4102`` — so the search can open on ``4102``.

P2's worked case: 4103 is reversed BY HAND two days after the import. On
Reconciliation, RET1029-02 is still unexplained and offers Match to payment and
Bank fee; matching it LINKS to that reversal (never a second one) and moves
154.00 holding → cash; FEE1031 posts to Bank fees once.
"""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from apps.payments import bankrec_read, models, reconciliation, reversal
from apps.payments.exceptions import PaymentRuleError

from tests.test_lbx05_09_statement_lines_post import (
    BANK_CLOSING,
    FEE,
    IMPORTED_AT,
    WORKED_AT,
    balance,
    designation,
    every_entry_balances,
    holding_account,
    line,
    the_lockbox_day,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_pay_020_023_bank_rec import a_bank_account, a_statement

pytestmark = pytest.mark.django_db

ROWS = [
    ("2026-10-27", "LBX4521-1026", "870.50"),
    ("2026-10-29", "RET1029-01 CHK 4102", "-76.40"),
    ("2026-10-29", "RET1029-02 CHK 4103", "-154.00"),
    ("2026-10-31", "FEE1031", "-24.00"),
]
#: Two days after the 1 Nov import — P2's "reversed by hand later".
LATER = datetime(2026, 11, 3, 15, 0, tzinfo=UTC)


def _import(actor, tenant):
    return reconciliation.import_bank_statement(
        actor=actor,
        bank_account_id=a_bank_account(tenant, name=f"Lockbox {uuid.uuid4().hex[:6]}").pk,
        period_start=date(2026, 10, 26),
        period_end=date(2026, 10, 31),
        payload=a_statement(ROWS),
        imported_at=IMPORTED_AT,
        opening_balance=Decimal("0.00"),
        closing_balance=BANK_CLOSING,
    ).statement_import_id


def _name(tenant, payment, full_name):
    from apps.customers import models as customer_models

    customer_models.Contact.objects.create(
        tenant=tenant, account_id=payment.account_id, full_name=full_name, is_primary=True
    )
    return customer_models.Account.objects.get(pk=payment.account_id).account_no


# ── P1 a2-3 — the cheque number in the line's own words ─────────────────────
@pytest.mark.parametrize(
    ("text", "hint"),
    [
        ("RET1029-01 CHK 4102", "4102"),
        ("RETURNED ITEM #4103", "4103"),
        ("CHECK DEPOSIT 4410", "4410"),
        ("RET1029-01", None),  # "1029" is glued to RET, "01" is two digits
        ("FEE1031", None),
        ("", None),
        (None, None),
    ],
)
def test_a2_3__the_search_hint_is_the_cheque_number_in_the_line(text, hint):
    assert bankrec_read.cheque_number_in(text) == hint


def test_a1_3_and_a2_3__review_rows_name_the_customer_and_carry_the_hint(brazos, dana):
    with tenant_ctx(brazos):
        payments, _batch = the_lockbox_day(dana, brazos)
        account_no = _name(brazos, payments["4102"], "Clara Castillo")
        statement_id = _import(dana, brazos)
        review = bankrec_read.statement_review(statement_id)
        by_ref = {row["reference"]: row for row in review["rows"]}
        assert by_ref["RET1029-01 CHK 4102"]["search_hint"] == "4102"
        assert by_ref["FEE1031"]["search_hint"] is None

        reconciliation.match_returned_line(
            actor=dana,
            bank_line_id=line(statement_id, "RET1029-01 CHK 4102").pk,
            payment_id=payments["4102"].pk,
            occurred_at=WORKED_AT,
        )
        row = {
            r["reference"]: r for r in bankrec_read.statement_review(statement_id)["rows"]
        }["RET1029-01 CHK 4102"]
        assert row["state"] == "explained" and row["posted"] is True
        assert row["returned_customer_name"] == "Clara Castillo"
        assert row["returned_account_no"] == account_no
        # B14 rule 31 — the account NUMBER, never the uuid.
        assert row["returned_account_no"] != str(payments["4102"].account_id)

        posted = bankrec_read.reconciliation_statement(statement_id)["posted_lines"]["rows"]
        (only,) = posted
        assert (only["customer_name"], only["account_no"]) == ("Clara Castillo", account_no)


# ── P1 a2-2 — the clerk's Bank memo reaches the reversal ────────────────────
def test_a2_2__an_edited_bank_memo_is_the_reversals_memo(brazos, dana):
    with tenant_ctx(brazos):
        payments, _batch = the_lockbox_day(dana, brazos)
        statement_id = _import(dana, brazos)
        reconciliation.match_returned_line(
            actor=dana,
            bank_line_id=line(statement_id, "RET1029-02 CHK 4103").pk,
            payment_id=payments["4103"].pk,
            occurred_at=WORKED_AT,
            bank_memo="  NSF - account closed  ",
        )
        reversing = models.Payment.objects.get(reverses_payment=payments["4103"])
        assert reversing.memo == "NSF - account closed"


def test_a2_2__no_memo_given_keeps_the_line_text_and_over_60_refuses(brazos, dana):
    with tenant_ctx(brazos):
        payments, _batch = the_lockbox_day(dana, brazos)
        statement_id = _import(dana, brazos)
        ret2 = line(statement_id, "RET1029-02 CHK 4103")
        with pytest.raises(PaymentRuleError, match="at most 60"):
            reconciliation.match_returned_line(
                actor=dana,
                bank_line_id=ret2.pk,
                payment_id=payments["4103"].pk,
                occurred_at=WORKED_AT,
                bank_memo="x" * 61,
            )
        assert not models.Payment.objects.filter(reverses_payment=payments["4103"]).exists()
        reconciliation.match_returned_line(
            actor=dana, bank_line_id=ret2.pk, payment_id=payments["4103"].pk, occurred_at=WORKED_AT
        )
        reversing = models.Payment.objects.get(reverses_payment=payments["4103"])
        assert reversing.memo == "RET1029-02 CHK 4103"


# ── P2 = A — from Reconciliation, after a hand reversal two days later ─────
def test_p2__reconciliation_offers_both_actions_and_links_the_later_hand_reversal(
    brazos, dana, audit_rows
):
    with tenant_ctx(brazos):
        payments, batch = the_lockbox_day(dana, brazos)
        statement_id = _import(dana, brazos)
        reconciliation.reconcile_batch(actor=dana, batch_id=batch.pk, posted_at=WORKED_AT)
        # RET1029-01 is matched on the import review, as the tester did.
        reconciliation.match_returned_line(
            actor=dana,
            bank_line_id=line(statement_id, "RET1029-01 CHK 4102").pk,
            payment_id=payments["4102"].pk,
            occurred_at=WORKED_AT,
        )
        # 4103 is reversed by hand on 3 Nov — two days after the import.
        reversal.reverse_payment(
            dana,
            payment_id=payments["4103"].pk,
            returned_on=LATER,
            reason=models.REVERSAL_REASON_NSF,
            idempotency_reference=uuid.uuid4(),
        )

        rec = bankrec_read.reconciliation_statement(statement_id)
        unexplained = next(i for i in rec["reconciling_items"] if i["code"] == "unexplained_lines")
        rows = {row["reference"]: row for row in unexplained["rows"]}
        assert set(rows) == {"RET1029-02 CHK 4103", "FEE1031"}
        assert rows["RET1029-02 CHK 4103"]["actions"] == ["match_return", "bank_fee"]
        assert rows["RET1029-02 CHK 4103"]["search_hint"] == "4103"
        assert rows["FEE1031"]["actions"] == ["match_return", "bank_fee"]

        ret2 = rows["RET1029-02 CHK 4103"]["bank_line_id"]
        offered = reconciliation.return_candidates(ret2, query="4103")
        assert [(r["cheque"], r["already_reversed"]) for r in offered] == [("4103", True)]
        matched = reconciliation.match_returned_line(
            actor=dana, bank_line_id=ret2, payment_id=payments["4103"].pk, occurred_at=WORKED_AT
        )
        assert matched.posted and not matched.reversed_now
        # Never reversed twice.
        assert models.Payment.objects.filter(reverses_payment=payments["4103"]).count() == 1

        fee = reconciliation.explain_bank_fee_line(
            actor=dana, bank_line_id=rows["FEE1031"]["bank_line_id"], occurred_at=WORKED_AT
        )
        assert fee.posted
        again = reconciliation.explain_bank_fee_line(
            actor=dana, bank_line_id=rows["FEE1031"]["bank_line_id"], occurred_at=WORKED_AT
        )
        assert again.created is False

        assert balance(brazos, holding_account(payments["4101"])) == Decimal("0.00")
        assert balance(brazos, designation(brazos, "cash")) == BANK_CLOSING
        assert balance(brazos, designation(brazos, "bank_fees")) == FEE  # once, not 48.00
        every_entry_balances(brazos)
        rec = bankrec_read.reconciliation_statement(statement_id)
        assert rec["bank_equals_books"] is True
        assert rec["posted_lines"]["count"] == 3
        actions = [row["action"] for row in audit_rows]
        assert actions.count(reconciliation.AUDIT_LINE_FEE_EXPLAINED) == 1


def test_p2__a_credit_line_offers_neither_action(brazos, dana):
    with tenant_ctx(brazos):
        statement_id = reconciliation.import_bank_statement(
            actor=dana,
            bank_account_id=a_bank_account(brazos, name="Credit").pk,
            period_start=date(2026, 10, 26),
            period_end=date(2026, 10, 31),
            payload=a_statement([("2026-10-28", "WIRE 99812", "12.40")]),
            imported_at=IMPORTED_AT,
        ).statement_import_id
        rec = bankrec_read.reconciliation_statement(statement_id)
        unexplained = next(i for i in rec["reconciling_items"] if i["code"] == "unexplained_lines")
        (row,) = unexplained["rows"]
        assert row["actions"] == []
