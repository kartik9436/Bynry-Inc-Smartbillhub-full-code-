# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-PAY-6331 — "The cheque number is asked for BEFORE the cheque
#           exists and cannot be recorded when it is written: Raise collects
#           it, POST /refunds/{id}/issue accepts no such field."
# Story:    US-PAY-011 §5 ("required for check") — UNCHANGED in substance and
#           moved in ACT: still required for a cheque, now at the act that
#           writes the cheque.
#           Screens: S58 · blueprint 6·3a Raise, 6·3b Issue.
# Rules:    CLAUDE.md hard rule 2 (money 4dp, never float) · hard rule 4
#           (financial immutability — and `refunds` is NOT one of its tables;
#           its freeze is 0006's deny-by-default, whose allow list this widens
#           by exactly one WRITE-ONCE column) · hard rule 5 (only the ledger
#           posting service writes journal lines) · hard rule 7 (every money
#           action writes `audit_log`)
# Blueprint:05-prototype/06 Payments Page Blueprint.pdf p077-p078, read as
#           IMAGES at scale 2.0 (B14 rule 42). 6·3b annotation ② draws
#           "Cheque number *" with the note **"the only record of which cheque
#           this was"**; 6·3a draws Amount, Reason, How and Note and NO cheque
#           number at all.
# ───────────────────────────────────────────────────────
"""The cheque number is written at the act that writes the cheque.

**THE TEST THIS FILE EXISTS FOR** is
`test_def_pay_6331__the_cheque_number_is_written_at_issue_and_read_back`: issue
a refund with a cheque number and read it back off the stored row.

⚠ **THAT TEST COULD NOT BE WRITTEN BEFORE THIS CHANGE, WHICH IS THE RED PROOF.**
`issue_refund(actor, *, refund_id, issued_at, entry_date=None)` took no
reference of any kind, so the call below raised

    TypeError: issue_refund() got an unexpected keyword argument 'reference'

before a single assertion ran. A clerk typed a cheque number days before anyone
wrote a cheque, and when the real cheque was written there was nowhere to put
its number.

════════════════════════════════════════════════════════════════════════════
WHY THIS IS A WIDENING OF 0006's ALLOW LIST AND NOT A BREACH OF HARD RULE 4
════════════════════════════════════════════════════════════════════════════
Hard rule 4 freezes issued invoices, invoice lines, payments and journal
entries. **`refunds` is none of them** — `payments/0006`'s own exception (4)
says so in as many words: *"`refunds` IS NOT A DB-4 APPEND-ONLY TABLE and is
not frozen as one … the freeze is deny-by-default with the transition columns
allowed"*. That deny-by-default is what made r2's status walk lawful in the
first place, and `reference` joins it **as a WRITE-ONCE column**, the same
shape `journal_entry_id` and `void_journal_entry_id` already have two clauses
above it in the same trigger: NULL → set, and never re-pointed.

So the cheque number is still a fact from the moment it exists. What moved is
WHEN it comes into existence.

════════════════════════════════════════════════════════════════════════════
THE SERVICE ASSERTS EVERY LAW THE TRIGGER ASSERTS, BECAUSE THE TEST DATABASE
IS SQLITE AND HAS NO TRIGGERS
════════════════════════════════════════════════════════════════════════════
`payments/0006` exception (5) already says this and it is why the write-once
guard is written twice. The Postgres half is marked `requires_postgres` and is
the only place the trigger itself is exercised; the service half runs
everywhere. **A guard that skips silently on the developer's own database is
not a guard** (hard-won law 7's *incapable of failing* shape).
"""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from django.db import DatabaseError, connection, transaction

from apps.payments import models, refunds, selectors
from apps.payments.exceptions import PaymentRuleError

from tests.isolation_helpers import requires_postgres
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_pay_001_record_payment import PE4_CREDIT, a_payment, pe1_bills
from tests.test_w3_billing_models import an_account

#: PE-9, verbatim: *"ACC-1042 credit 57.13 (from PE-4) → refund 57.13, check
#: #10241, Aug 15, 2026."* The figure is COPIED from the worked example, never
#: computed here.
PE9_CHEQUE = "10241"

#: The number a clerk types at the counter when the cheque is actually written.
#: Deliberately NOT PE-9's, so a test that reads back the right column cannot
#: pass by reading the wrong one.
CHEQUE_WRITTEN = "10307"

REQUESTED_AT = datetime(2026, 7, 24, 9, 0, tzinfo=UTC)
APPROVED_AT = datetime(2026, 7, 24, 9, 30, tzinfo=UTC)
ISSUED_AT = datetime(2026, 7, 24, 10, 0, tzinfo=UTC)


def an_overpaid_account(brazos, marcus):
    """PE-4: open 292.87, pay 350.00 → credit 57.13 carried."""
    account = an_account(marcus, brazos)
    pe1_bills(brazos, account)
    recorded = a_payment(marcus, account, amount=Decimal("350.00"))
    assert recorded.credit_carried == PE4_CREDIT
    return account, recorded


def an_approved_cheque_refund(brazos, marcus, dana, **request_overrides):
    """A refund standing at APPROVED with **no cheque number on it** — which is
    the state every refund raised through the product is now in, because 6·3a
    no longer collects one."""
    account, recorded = an_overpaid_account(brazos, marcus)
    values = dict(
        payment_id=recorded.payment_id,
        amount=PE4_CREDIT,
        method=models.REFUND_METHOD_CHECK,
        reason="Overpayment",
        requested_at=REQUESTED_AT,
    )
    values.update(request_overrides)
    requested = refunds.request_refund(marcus, **values)
    refunds.approve_refund(dana, refund_id=requested.refund_id, approved_at=APPROVED_AT)
    return account, requested.refund_id


# ── the one this file exists for ───────────────────────────────────────────
def test_def_pay_6331__the_cheque_number_is_written_at_issue_and_read_back(brazos, marcus, dana):
    """Issue a refund with a cheque number; read it back off the stored row.

    ⚠ **BEFORE THIS CHANGE THIS TEST COULD NOT BE WRITTEN AT ALL** — the
    keyword did not exist and the call raised `TypeError` before any assertion.
    That is the cleanest red proof available for a record gap: not a wrong
    value, an absent place to put one.
    """
    with tenant_ctx(brazos):
        account, refund_id = an_approved_cheque_refund(brazos, marcus, dana)

        # The row carries NO cheque number until the cheque is written.
        assert models.Refund.objects.get(pk=refund_id).reference is None

        issued = refunds.issue_refund(
            dana, refund_id=refund_id, issued_at=ISSUED_AT, reference=CHEQUE_WRITTEN
        )

        assert issued.status == models.REFUND_ISSUED
        row = models.Refund.objects.get(pk=refund_id)
        assert row.reference == CHEQUE_WRITTEN, "6·3b: the only record of which cheque this was"
        # The money still moved exactly as PE-9 says it does — this change adds
        # a column write to that transaction and moves no figure.
        assert issued.credit_position_after == Decimal("0.00")
        assert selectors.account_credit_position(account.pk) == Decimal("0.00")
        assert row.journal_entry_id is not None


def test_def_pay_6331__the_cheque_number_is_written_in_the_same_statement_as_the_status(
    brazos, marcus, dana
):
    """Never patched afterwards (hard rule 4's shape, kept).

    The cheque number reaches the database in the SAME `UPDATE` as the status
    move and inside the SAME transaction as the posting and the audit row — so
    a refund can never stand ISSUED for even an instant with no record of which
    cheque it was.
    """
    with tenant_ctx(brazos):
        _account, refund_id = an_approved_cheque_refund(brazos, marcus, dana)
        seen: list[tuple] = []

        original = models.Refund.save

        def capture(self, *args, **kwargs):
            if kwargs.get("update_fields") is not None:
                seen.append(tuple(sorted(kwargs["update_fields"])))
            return original(self, *args, **kwargs)

        models.Refund.save = capture
        try:
            refunds.issue_refund(
                dana, refund_id=refund_id, issued_at=ISSUED_AT, reference=CHEQUE_WRITTEN
            )
        finally:
            models.Refund.save = original

        # The SECOND save is the journal-entry write-once stamp that was always
        # here — the entry id arrives microseconds after the posting composes
        # it, in the same transaction, for the reason the module docstring
        # gives. What matters is that the cheque number is in the FIRST one,
        # riding the status move, rather than patched on afterwards.
        assert seen[0] == ("issued_at", "reference", "status", "updated_at"), (
            "the cheque number rides the status move; a later UPDATE would be a patch, "
            "and the trigger refuses one"
        )
        assert seen[1] == ("journal_entry_id", "updated_at")


# ── the requirement MOVED; it did not go away (US-PAY-011 §5) ──────────────
def test_def_pay_6331__a_cheque_refund_may_now_be_RAISED_without_a_cheque_number(brazos, marcus):
    """6·3a draws no cheque number, because a request cannot know one.

    US-PAY-011 §5 reads *"required for check"* and names no ACT. It is still
    required for a cheque; it is required at the act that writes the cheque.
    """
    with tenant_ctx(brazos):
        _account, recorded = an_overpaid_account(brazos, marcus)
        requested = refunds.request_refund(
            marcus,
            payment_id=recorded.payment_id,
            amount=PE4_CREDIT,
            method=models.REFUND_METHOD_CHECK,
            reason="Overpayment",
            requested_at=REQUESTED_AT,
        )
        assert requested.status == models.REFUND_REQUESTED
        assert models.Refund.objects.get(pk=requested.refund_id).reference is None


def test_def_pay_6331__a_cheque_refund_cannot_be_ISSUED_without_a_cheque_number(
    brazos, marcus, dana
):
    """The refusal US-PAY-011 §5 owns, at its new act.

    A payment out that bank rec can never find is how a reconciliation stops
    tying (BR-PAY-021, applied outbound) — which is just as true at issue as it
    was at request, and is the reason the requirement moved rather than went.
    """
    with tenant_ctx(brazos):
        _account, refund_id = an_approved_cheque_refund(brazos, marcus, dana)
        with pytest.raises(PaymentRuleError) as refusal:
            refunds.issue_refund(dana, refund_id=refund_id, issued_at=ISSUED_AT)
        assert "cheque number" in str(refusal.value)
        # NOTHING moved: not the status, not the credit, not the books.
        row = models.Refund.objects.get(pk=refund_id)
        assert row.status == models.REFUND_APPROVED
        assert row.journal_entry_id is None


def test_def_pay_6331__an_ach_refund_still_needs_no_reference(brazos, marcus, dana):
    """`BR-PAY-014` is *"check/ACH v1"* and only the cheque half is refused.

    Guards the mirror-image defect: a requirement widened past the method it
    belongs to would block every ACH refund in the product.
    """
    with tenant_ctx(brazos):
        _account, refund_id = an_approved_cheque_refund(
            brazos, marcus, dana, method=models.REFUND_METHOD_ACH
        )
        issued = refunds.issue_refund(dana, refund_id=refund_id, issued_at=ISSUED_AT)
        assert issued.status == models.REFUND_ISSUED
        assert models.Refund.objects.get(pk=refund_id).reference is None


# ── write-once, asserted at BOTH layers (0006 exception (5)) ───────────────
def test_def_pay_6331__a_cheque_number_already_on_the_row_is_never_overwritten(
    brazos, marcus, dana
):
    """The service half of the write-once guard.

    A refund recorded with its number already known — a back-dated import, or
    the demo fixture, both of which call `request_refund` directly — keeps it.
    Issuing does not silently replace it with a different one.
    """
    with tenant_ctx(brazos):
        _account, refund_id = an_approved_cheque_refund(brazos, marcus, dana, reference=PE9_CHEQUE)
        with pytest.raises(PaymentRuleError) as refusal:
            refunds.issue_refund(
                dana, refund_id=refund_id, issued_at=ISSUED_AT, reference=CHEQUE_WRITTEN
            )
        assert PE9_CHEQUE in str(refusal.value)
        assert models.Refund.objects.get(pk=refund_id).reference == PE9_CHEQUE


def test_def_pay_6331__issuing_a_refund_that_already_names_its_cheque_is_lawful(
    brazos, marcus, dana
):
    """…and passing the SAME number again is not an overwrite.

    This is the path the demo fixture takes: `request_refund` wrote #10241 and
    `issue_refund` is called with no reference at all. It must not be refused
    for want of a cheque number the row already has.
    """
    with tenant_ctx(brazos):
        _account, refund_id = an_approved_cheque_refund(brazos, marcus, dana, reference=PE9_CHEQUE)
        issued = refunds.issue_refund(dana, refund_id=refund_id, issued_at=ISSUED_AT)
        assert issued.status == models.REFUND_ISSUED
        assert models.Refund.objects.get(pk=refund_id).reference == PE9_CHEQUE


@requires_postgres
def test_def_pay_6331__the_trigger_allows_the_write_and_refuses_the_rewrite(brazos, marcus, dana):
    """The DATABASE half — the only place `payments/0041` itself is exercised.

    ⚠ **BOTH DIRECTIONS, BECAUSE ONE OF THEM IS A CHECK THAT CANNOT FAIL.** A
    test that only proves the rewrite is refused would pass just as well with
    `reference` left OFF the allow list entirely — the trigger would refuse the
    first write too, and the product would be broken in exactly the way this
    defect is about. So the NULL → set write is asserted first.
    """
    with tenant_ctx(brazos):
        _account, refund_id = an_approved_cheque_refund(brazos, marcus, dana)
        refunds.issue_refund(
            dana, refund_id=refund_id, issued_at=ISSUED_AT, reference=CHEQUE_WRITTEN
        )
        assert models.Refund.objects.get(pk=refund_id).reference == CHEQUE_WRITTEN

        with pytest.raises(DatabaseError) as refused:
            with transaction.atomic(), connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE refunds SET reference = %s WHERE id = %s",
                    [PE9_CHEQUE, str(refund_id)],
                )
        assert "written once" in str(refused.value)
        assert models.Refund.objects.get(pk=refund_id).reference == CHEQUE_WRITTEN


# ── hard rule 7 ────────────────────────────────────────────────────────────
def test_def_pay_6331__the_audit_row_carries_the_cheque_number_that_was_written(
    brazos, marcus, dana, audit_rows
):
    """Hard rule 7: every money action writes `audit_log`.

    `issue_refund` already wrote `"reference": refund.reference` into its
    `after` block — and until today that was **whatever was typed at raise, or
    nothing at all**. It is now the number of the cheque that actually left.
    """
    with tenant_ctx(brazos):
        _account, refund_id = an_approved_cheque_refund(brazos, marcus, dana)
        refunds.issue_refund(
            dana, refund_id=refund_id, issued_at=ISSUED_AT, reference=CHEQUE_WRITTEN
        )
        # ⚠ The capture sink yields DICTS, not objects — `test_us_pay_011`'s own
        # `[r["action"] for r in audit_rows]` is the shape to copy. A first draft
        # read `row.action` and failed with `AttributeError`, which is this
        # file's own small instance of law 7: a check written against a shape
        # nobody verified.
        issued = [row for row in audit_rows if row["action"] == refunds.AUDIT_ISSUED]
        assert len(issued) == 1
        assert issued[0]["after"]["reference"] == CHEQUE_WRITTEN


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-PAY-6331 · 05-prototype/06 Payments Page Blueprint.pdf p077-p078 (images, scale 2.0) · 04-docs/05-modules/08-payments/06-epics/EP-PAY-03-exceptions.md §5 · 06-backend/apps/payments/migrations/0006_w4_reversal_and_refunds.py
# generated: 2026-09-23 by lane REFUND-MONEY
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
