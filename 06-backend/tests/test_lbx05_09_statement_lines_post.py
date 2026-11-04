# ── Trace ──────────────────────────────────────────────
# Defects:  DEF-PAY-10694 (LBX-05 — returned-item and bank-fee statement lines
#           were only counted) · DEF-PAY-10695 (LBX-09 — a statement imported
#           lines dated after the import and outside its own period)
# Rulings:  decision log 2026-10-30 "Lockbox audit: what is fixed, what is not,
#           and three answers (PO)" — Q1 = A, batch decision G3 RULED: a
#           statement line that is not a deposit MAY post · 2026-10-30 "NSF
#           penalty can be unticked with a reason; a bounce is reversed from
#           three places (PO)" — Q2: from the statement line, or by hand, and
#           never twice
# Rules:    BR-PAY-019 · CLAUDE.md rule 1, 2, 4, 5 (only the ledger posts —
#           balanced pairs), 6 (idempotent), 7 (audit_log on every action)
# ───────────────────────────────────────────────────────
"""The tester's lockbox day, end to end, with the ledger tied out to the cent.

DEP-261026-0007: six cheques, **870.50**, banked 26 Oct. Cheques **4102**
(76.40, NSF, on one account) and **4103** (154.00, account closed, another)
come back. The statement for 26–31 Oct reads:

    27 Oct  LBX4521-1026   +870.50   the deposit
    29 Oct  RET1029-01      −76.40   4102 returned
    29 Oct  RET1029-02     −154.00   4103 returned
    31 Oct  FEE1031         −24.00   the bank's fee

Before LBX-05 the three money-out lines were *"counted only"*: the batch
reconciled 870.50 out of holding, the two reversals put 230.40 back into it,
and the period ended **holding −230.40, books cash 870.50 against bank
616.10**. After: **holding 0.00, books cash 616.10 = bank 616.10, 24.00 in
Bank fees**, and every entry a balanced pair.

4102 is reversed BY HAND first (Payments list) and 4103 is not — so the two
matches exercise both of the PO's Q2 paths: link to the existing reversal, and
reverse from the statement line itself. Neither is ever reversed twice.
"""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from apps.payments import bankrec_models as bankrec
from apps.payments import bankrec_read, models, reconciliation, reversal, services
from apps.payments.exceptions import PaymentRuleError

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_pay_020_023_bank_rec import (
    a_bank_account,
    a_statement,
    an_account_of,
    an_issued_bill,
)

pytestmark = pytest.mark.django_db

DAY = date(2026, 10, 26)
#: The six cheques of DEP-261026-0007 — 870.50 in all.
CHEQUES = (
    ("4101", Decimal("200.00")),
    ("4102", Decimal("76.40")),
    ("4103", Decimal("154.00")),
    ("4104", Decimal("150.00")),
    ("4105", Decimal("190.10")),
    ("4106", Decimal("100.00")),
)
DEPOSIT = Decimal("870.50")
BANK_CLOSING = Decimal("616.10")
FEE = Decimal("24.00")
STATEMENT_ROWS = [
    ("2026-10-27", "LBX4521-1026", "870.50"),
    ("2026-10-29", "RET1029-01", "-76.40"),
    ("2026-10-29", "RET1029-02", "-154.00"),
    ("2026-10-31", "FEE1031", "-24.00"),
]
IMPORTED_AT = datetime(2026, 11, 1, 9, 0, tzinfo=UTC)
WORKED_AT = datetime(2026, 11, 1, 10, 0, tzinfo=UTC)
HAND_REVERSED_AT = datetime(2026, 10, 29, 15, 0, tzinfo=UTC)


# ── the world ───────────────────────────────────────────────────────────────
def the_lockbox_day(actor, tenant):
    """Six cheques through the real `record_payment`, into ONE lockbox batch."""
    from apps.customers import models as customer_models

    # ACTIVE accounts, as a lockbox customer's is: since lane NSF-FEE
    # (eb36ee5bd) an NSF bounce prices the penalty off the account's billable
    # scope, and `an_account_of` takes the tenant's FIRST status. A bounce on
    # a NOT-billable (e.g. closed) account currently aborts the whole reversal
    # — filed as its own defect rather than hidden in this fixture.
    active = customer_models.AccountStatus.objects.get(tenant=tenant, code="active")
    payments = {}
    for cheque, amount in CHEQUES:
        account = an_account_of(actor, tenant)
        account.status = active
        account.save(update_fields=["status"])
        an_issued_bill(
            tenant,
            account,
            number=f"BL-2610-{uuid.uuid4().hex[:6]}",
            total=amount,
            issued_on=date(2026, 10, 1),
        )
        recorded = services.record_payment(
            actor,
            account_id=account.pk,
            amount=amount,
            method_code="check",
            posted_at=datetime(2026, 10, 26, 10, 30, tzinfo=UTC),
            idempotency_reference=uuid.uuid4(),
            deposit_channel="lockbox",
            confirmation=cheque,
        )
        payments[cheque] = models.Payment.objects.get(pk=recorded.payment_id)
    (batch_id,) = {row.deposit_batch_id for row in payments.values()}
    batch = bankrec.DepositBatch.objects.get(pk=batch_id)
    assert batch.recorded_total == DEPOSIT
    return payments, batch


def import_the_statement(actor, tenant):
    return reconciliation.import_bank_statement(
        actor=actor,
        bank_account_id=a_bank_account(tenant, name=f"Lockbox {uuid.uuid4().hex[:6]}").pk,
        period_start=date(2026, 10, 26),
        period_end=date(2026, 10, 31),
        payload=a_statement(STATEMENT_ROWS),
        imported_at=IMPORTED_AT,
        opening_balance=Decimal("0.00"),
        closing_balance=BANK_CLOSING,
    )


def line(statement_id, reference):
    return bankrec.BankLine.objects.get(statement_import_id=statement_id, reference=reference)


def balance(tenant, account_id):
    """Σ debits − Σ credits of POSTED lines on one ledger account."""
    from apps.ledger import models as ledger_models

    total = Decimal("0")
    for side, amount in ledger_models.JournalLine.objects.filter(
        tenant=tenant, ledger_account_id=account_id, journal_entry__status=ledger_models.JE_POSTED
    ).values_list("side", "amount"):
        total += amount if side == "debit" else -amount
    return total


def designation(tenant, name):
    from apps.ledger import models as ledger_models

    return ledger_models.LedgerAccount.objects.get(tenant=tenant, designation=name).pk


def holding_account(payment):
    from apps.ledger import selectors as ledger_selectors

    (account_id,) = ledger_selectors.entry_debit_totals([payment.journal_entry_id])
    return account_id


def every_entry_balances(tenant):
    from django.db.models import Sum

    from apps.ledger import models as ledger_models

    for entry in ledger_models.JournalEntry.objects.filter(tenant=tenant):
        debits = ledger_models.JournalLine.objects.filter(
            journal_entry=entry, side="debit"
        ).aggregate(total=Sum("amount"))["total"]
        credits = ledger_models.JournalLine.objects.filter(
            journal_entry=entry, side="credit"
        ).aggregate(total=Sum("amount"))["total"]
        assert debits == credits, f"entry {entry.posting_key} does not balance"


def hand_reverse(actor, payment):
    """Payments › Payments list › Reverse — the PO's Q2 (b)."""
    return reversal.reverse_payment(
        actor,
        payment_id=payment.pk,
        returned_on=HAND_REVERSED_AT,
        reason=models.REVERSAL_REASON_NSF,
        idempotency_reference=uuid.uuid4(),
    )


# ════════════════════════════════════════════════════════════════════════════
# LBX-05 — the tester's day ties out
# ════════════════════════════════════════════════════════════════════════════
def test_lbx05__the_testers_day_ties_books_cash_to_the_bank(brazos, dana, audit_rows):
    with tenant_ctx(brazos):
        payments, batch = the_lockbox_day(dana, brazos)
        hand_reverse(dana, payments["4102"])
        imported = import_the_statement(dana, brazos)
        statement_id = imported.statement_import_id

        # (1) the three money-out lines NEED A LOOK — none is "counted only".
        review = bankrec_read.statement_review(statement_id)
        assert review["tiles"]["needs_a_look"] == 3
        assert review["tiles"]["not_in_our_system"] == 0
        assert review["unavailable"] == []
        out = [row for row in review["rows"] if row["amount"].startswith("-")]
        assert {tuple(row["actions"]) for row in out} == {("match_return", "bank_fee")}

        reconciliation.reconcile_batch(actor=dana, batch_id=batch.pk, posted_at=WORKED_AT)
        holding = holding_account(payments["4101"])
        cash = designation(brazos, "cash")
        fees = designation(brazos, "bank_fees")
        # The tester's "before", reproduced: one hand reversal so far.
        assert balance(brazos, holding) == Decimal("-76.40")
        assert balance(brazos, cash) == DEPOSIT

        # (2a) RET1029-01 → 4102, already reversed by hand: LINK, never reverse.
        ret1 = line(statement_id, "RET1029-01")
        offered = reconciliation.return_candidates(ret1.pk)
        assert [(row["cheque"], row["already_reversed"]) for row in offered] == [("4102", True)]
        first = reconciliation.match_returned_line(
            actor=dana, bank_line_id=ret1.pk, payment_id=payments["4102"].pk, occurred_at=WORKED_AT
        )
        assert first.posted and not first.reversed_now

        # (2b) RET1029-02 → 4103, not reversed: the match REVERSES it, once.
        ret2 = line(statement_id, "RET1029-02")
        offered = reconciliation.return_candidates(ret2.pk, query="4103")
        assert [(row["cheque"], row["already_reversed"]) for row in offered] == [("4103", False)]
        second = reconciliation.match_returned_line(
            actor=dana, bank_line_id=ret2.pk, payment_id=payments["4103"].pk, occurred_at=WORKED_AT
        )
        assert second.reversed_now
        again = reconciliation.match_returned_line(
            actor=dana, bank_line_id=ret2.pk, payment_id=payments["4103"].pk, occurred_at=WORKED_AT
        )
        assert again.created is False and again.resolution_id == second.resolution_id
        assert models.Payment.objects.filter(reverses_payment=payments["4103"]).count() == 1

        # (3) FEE1031 → Bank fees (6800) against cash.
        fee = reconciliation.explain_bank_fee_line(
            actor=dana, bank_line_id=line(statement_id, "FEE1031").pk, occurred_at=WORKED_AT
        )
        assert fee.posted and fee.amount == -FEE

        # ── the retest: the period ties ──
        assert balance(brazos, holding) == Decimal("0.00")
        assert balance(brazos, cash) == BANK_CLOSING
        assert balance(brazos, fees) == FEE
        every_entry_balances(brazos)

        # (4) the reconciliation statement shows them settled, nothing unexplained.
        rec = bankrec_read.reconciliation_statement(statement_id)
        assert rec["book_cash_balance"] == "616.100000"
        assert rec["bank_equals_books"] is True
        assert rec["posted_lines"]["count"] == 3
        assert [row["kind"] for row in rec["posted_lines"]["rows"]] == [
            "returned_item",
            "returned_item",
            "bank_fee",
        ]
        assert rec["explained_not_posted"]["count"] == 0
        unexplained = next(i for i in rec["reconciling_items"] if i["code"] == "unexplained_lines")
        assert unexplained["count"] == 0
        review = bankrec_read.statement_review(statement_id)
        assert review["tiles"]["explained"] == 3 and review["tiles"]["needs_a_look"] == 0
        assert all(row["posted"] for row in review["rows"] if row["state"] == "explained")

        # Hard rule 7 — one money-action row per act.
        actions = [row["action"] for row in audit_rows]
        assert actions.count(reconciliation.AUDIT_LINE_RETURN_MATCHED) == 2
        assert actions.count(reconciliation.AUDIT_LINE_FEE_EXPLAINED) == 1


def test_lbx05__a_match_before_the_reconcile_ties_the_same(brazos, dana):
    """Order does not matter: match first, reconcile after, same 0.00 / 616.10."""
    with tenant_ctx(brazos):
        payments, batch = the_lockbox_day(dana, brazos)
        statement_id = import_the_statement(dana, brazos).statement_import_id
        for reference, cheque in (("RET1029-01", "4102"), ("RET1029-02", "4103")):
            reconciliation.match_returned_line(
                actor=dana,
                bank_line_id=line(statement_id, reference).pk,
                payment_id=payments[cheque].pk,
                occurred_at=WORKED_AT,
            )
        reconciliation.explain_bank_fee_line(
            actor=dana, bank_line_id=line(statement_id, "FEE1031").pk, occurred_at=WORKED_AT
        )
        reconciliation.reconcile_batch(actor=dana, batch_id=batch.pk, posted_at=WORKED_AT)
        assert balance(brazos, holding_account(payments["4101"])) == Decimal("0.00")
        assert balance(brazos, designation(brazos, "cash")) == BANK_CLOSING
        every_entry_balances(brazos)


def test_lbx05__the_statement_bounce_carries_the_nsf_choice_and_the_bank_memo(brazos, dana):
    """PO 2026-10-30: the penalty can be unticked WITH a reason; LBX-04: the
    line's own words are the reversal's Bank memo. Through lane NSF-FEE's
    fee-aware `reverse_payment`, never a second reversal path."""
    with tenant_ctx(brazos):
        payments, _batch = the_lockbox_day(dana, brazos)
        statement_id = import_the_statement(dana, brazos).statement_import_id
        waived = reconciliation.match_returned_line(
            actor=dana,
            bank_line_id=line(statement_id, "RET1029-02").pk,
            payment_id=payments["4103"].pk,
            occurred_at=WORKED_AT,
            nsf_fee_waived=True,
            nsf_fee_waive_reason="bank error",
        )
        assert waived.reversed_now
        assert waived.nsf_fee_status == "nsf_fee_waived"
        reversing = models.Payment.objects.get(reverses_payment=payments["4103"])
        assert reversing.memo == "RET1029-02"
        # the other cheque, penalty left ticked: whatever the plan says, it is
        # NAMED (charged, or why not) — never silently nothing.
        charged = reconciliation.match_returned_line(
            actor=dana,
            bank_line_id=line(statement_id, "RET1029-01").pk,
            payment_id=payments["4102"].pk,
            occurred_at=WORKED_AT,
        )
        assert charged.nsf_fee_status not in (None, "nsf_fee_waived")


def test_lbx05__one_line_one_reversal_and_the_refusals(brazos, dana):
    with tenant_ctx(brazos):
        payments, _batch = the_lockbox_day(dana, brazos)
        statement_id = import_the_statement(dana, brazos).statement_import_id
        ret1 = line(statement_id, "RET1029-01")
        ret2 = line(statement_id, "RET1029-02")
        deposit = line(statement_id, "LBX4521-1026")

        # the wrong amount
        with pytest.raises(PaymentRuleError, match="matches the whole cheque"):
            reconciliation.match_returned_line(
                actor=dana, bank_line_id=ret1.pk, payment_id=payments["4103"].pk,
                occurred_at=WORKED_AT,
            )
        # money IN is not a return
        with pytest.raises(PaymentRuleError, match="matched to a deposit|money came IN"):
            reconciliation.match_returned_line(
                actor=dana, bank_line_id=deposit.pk, payment_id=payments["4101"].pk,
                occurred_at=WORKED_AT,
            )
        reconciliation.match_returned_line(
            actor=dana, bank_line_id=ret1.pk, payment_id=payments["4102"].pk, occurred_at=WORKED_AT
        )
        # the same line cannot be matched to a second payment, nor posted as a fee
        with pytest.raises(PaymentRuleError, match="already explained"):
            reconciliation.explain_bank_fee_line(
                actor=dana, bank_line_id=ret1.pk, occurred_at=WORKED_AT
            )
        # a matched reversal leaves the candidate list
        assert reconciliation.return_candidates(ret2.pk, query="4102") == []
        # nothing changed for 4103 by the refusals
        assert not models.Payment.objects.filter(reverses_payment=payments["4103"]).exists()


def test_lbx05__a_reversal_is_matched_to_one_line_only(brazos, dana):
    with tenant_ctx(brazos):
        payments, _batch = the_lockbox_day(dana, brazos)
        statement_id = reconciliation.import_bank_statement(
            actor=dana,
            bank_account_id=a_bank_account(brazos, name="Twice").pk,
            period_start=date(2026, 10, 26),
            period_end=date(2026, 10, 31),
            payload=a_statement(
                [("2026-10-29", "RET-A", "-76.40"), ("2026-10-30", "RET-B", "-76.40")]
            ),
            imported_at=IMPORTED_AT,
        ).statement_import_id
        reconciliation.match_returned_line(
            actor=dana,
            bank_line_id=line(statement_id, "RET-A").pk,
            payment_id=payments["4102"].pk,
            occurred_at=WORKED_AT,
        )
        with pytest.raises(PaymentRuleError, match="already matched to bank line RET-A"):
            reconciliation.match_returned_line(
                actor=dana,
                bank_line_id=line(statement_id, "RET-B").pk,
                payment_id=payments["4102"].pk,
                occurred_at=WORKED_AT,
            )


def test_lbx05__a_fee_typed_on_reverse_is_linked_not_posted_twice(brazos, dana):
    """One bank fee is posted ONCE (decision log 2026-10-30, "LBX-05 built")."""
    with tenant_ctx(brazos):
        payments, _batch = the_lockbox_day(dana, brazos)
        reversal.reverse_payment(
            dana,
            payment_id=payments["4102"].pk,
            returned_on=HAND_REVERSED_AT,
            reason=models.REVERSAL_REASON_NSF,
            bank_fee=FEE,
            idempotency_reference=uuid.uuid4(),
        )
        fees = designation(brazos, "bank_fees")
        assert balance(brazos, fees) == FEE
        statement_id = import_the_statement(dana, brazos).statement_import_id
        fee_line = line(statement_id, "FEE1031")
        offered = reconciliation.bank_fee_candidates(fee_line.pk)
        assert [row["cheque"] for row in offered] == ["4102"]
        linked = reconciliation.explain_bank_fee_line(
            actor=dana,
            bank_line_id=fee_line.pk,
            occurred_at=WORKED_AT,
            payment_id=payments["4102"].pk,
        )
        assert linked.posted is False and linked.journal_entry_id == offered[0]["journal_entry_id"]
        assert balance(brazos, fees) == FEE  # not 48.00
        assert reconciliation.bank_fee_candidates(line(statement_id, "RET1029-02").pk) == []


# ════════════════════════════════════════════════════════════════════════════
# LBX-09 — a line the bank cannot have posted yet, or outside the period
# ════════════════════════════════════════════════════════════════════════════
def test_lbx09__lines_dated_after_the_import_are_refused_by_name(brazos, dana):
    with tenant_ctx(brazos):
        account = a_bank_account(brazos, name="Early")
        # The tester's import on 26 Oct: the deposit dated that day is fine, the
        # first line dated 29 Oct is the one named.
        same_day = [("2026-10-26", "LBX4521-1026", "870.50"), *STATEMENT_ROWS[1:]]
        with pytest.raises(PaymentRuleError, match=r"RET1029-01, 2026-10-29\) is dated after"):
            reconciliation.import_bank_statement(
                actor=dana,
                bank_account_id=account.pk,
                period_start=date(2026, 10, 26),
                period_end=date(2026, 10, 31),
                payload=a_statement(same_day),
                imported_at=datetime(2026, 10, 26, 16, 0, tzinfo=UTC),
            )
        assert not bankrec.BankStatementImport.objects.filter(bank_account=account).exists()
        # and the 31 Oct line by itself is refused the same way
        with pytest.raises(PaymentRuleError, match=r"FEE1031, 2026-10-31\) is dated after"):
            reconciliation.import_bank_statement(
                actor=dana,
                bank_account_id=account.pk,
                period_start=date(2026, 10, 26),
                period_end=date(2026, 10, 31),
                payload=a_statement([("2026-10-31", "FEE1031", "-24.00")]),
                imported_at=datetime(2026, 10, 26, 16, 0, tzinfo=UTC),
            )


def test_lbx09__a_line_outside_the_statement_period_is_refused_by_name(brazos, dana):
    with tenant_ctx(brazos):
        with pytest.raises(PaymentRuleError, match=r"OLD-1, 2026-10-25\) is outside"):
            reconciliation.import_bank_statement(
                actor=dana,
                bank_account_id=a_bank_account(brazos, name="Period").pk,
                period_start=date(2026, 10, 26),
                period_end=date(2026, 10, 31),
                payload=a_statement([("2026-10-25", "OLD-1", "10.00")]),
                imported_at=IMPORTED_AT,
            )
