# ── Trace ──────────────────────────────────────────────
# Change:   CR-059 §8 CS-36, task 19 — "the release service and the one call in
#           the restatement, BEFORE the rebill, in the SAME transaction"
#           Screens: S30 (the settlement panel is task 20, not this)
# Rules:    BR-PAY-1072 (append-only negative mirror rows) · BR-PAY-1073 (no
#           journal line) · BR-PAY-1074 (before the rebill, in the correction's
#           one transaction) · BR-PAY-031 (never an edit) · BR-PAY-010 (the
#           released money is carried credit the next issue draws down) ·
#           BR-BIL-014 (billing emits the plan, payments executes it) ·
#           BR-TEN-042 (one currency per utility) · CLAUDE.md rule 4 · rule 5 ·
#           rule 6 · rule 7
# Tests:    this file (the service and the ordering) ·
#           test_cr059_cs36_restatement_pg.py (the three shapes, the tie-out,
#           the replay and the goodwill — on PostgreSQL, task 21)
# ───────────────────────────────────────────────────────
"""The correction's missing fifth step, and the rule that it comes FIRST.

════════════════════════════════════════════════════════════════════════════
WHAT RUNS HERE AND WHAT DOES NOT — hard-won law 1, stated rather than implied
════════════════════════════════════════════════════════════════════════════
* The RELEASE SERVICE runs in full against real rows on both sides: real
  `payments` and `allocations`, real `audit_log`, the real transaction guard.
* The ORDERING and the TRANSACTION BOUNDARY are asserted against the real
  `corrections.execute_restatement`, with the rebill's PRICING and ISSUE
  stubbed — the same three neighbours `test_us_bil_016_bulk_corrections.py`
  stubs, for the same reason.
* **THE MONEY OUTCOME IS NOT ASSERTED HERE.** Whether the customer ends up
  owing 0.00 with 20.00 of credit is CS-36's own proof and it runs against a
  real rating engine, a real ledger and PostgreSQL in
  `test_cr059_cs36_restatement_pg.py` — because hard-won law 14 says a
  multi-statement write inside a transaction proves nothing on SQLite, which
  has no aborted-transaction state at all.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from django.db import transaction


from apps.billing import corrections, models
from apps.billing.correction_models import CLASS_RESTATEMENT
from apps.billing.exceptions import BillingRuleError
from apps.ledger import models as ledger_models
from apps.payments import allocation_release, credit, selectors
from apps.payments import models as payment_models
from apps.payments.exceptions import PaymentRuleError

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_bil_016_bulk_corrections import (
    ISSUED_AT,
    TODAY,
    _PreparedStub,
    _RatedBill,
    _RatedLine,
    an_issued_bill,
)
from tests.test_w3_billing_models import a_run, an_account

pytestmark = pytest.mark.django_db

ORIGINAL_TOTAL = Decimal("247.87")
POSTED_AT = datetime(2026, 8, 15, 10, 0, tzinfo=UTC)
EARLIER = datetime(2026, 8, 10, 10, 0, tzinfo=UTC)


def _a_payment(tenant, account, amount, *, no, posted_at=POSTED_AT, currency="USD"):
    return payment_models.Payment.objects.create(
        tenant=tenant,
        account=account,
        payment_no=no,
        amount=amount,
        currency=currency,
        status=payment_models.PAYMENT_CLEARED,
        posted_at=posted_at,
        cleared_at=posted_at,
    )


def _allocate(tenant, payment, invoice, amount):
    return payment_models.Allocation.objects.create(
        tenant=tenant, payment=payment, invoice=invoice, amount=amount
    )


def _release(invoice, *, reason="wrong_read", actor=None):
    """The service, wrapped as its only lawful caller wraps it (BR-PAY-1074)."""
    with transaction.atomic():
        return allocation_release.release_allocations_for_invoice(
            invoice_id=invoice.pk, reason=reason, occurred_on=date(2026, 8, 28), actor=actor
        )


# ═══════════════════════════════════════════════════════════════════════════
# THE SERVICE
# ═══════════════════════════════════════════════════════════════════════════
def test_cs36_task19_tc1__the_whole_payment_comes_off_as_one_negative_mirror_row(brazos, dana):
    """BR-PAY-1072 — append-only, hung off the payment, editing nothing.

    Exactly what a bounced cheque already writes (`reversal._write_reversal`),
    which is why CS-36 calls this *"not a new mechanism"*. The original row is
    still there, byte-identical, because `allocations` accepts no UPDATE and no
    DELETE in any state.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos)
        bill = an_issued_bill(brazos, account, run, invoice_no="BL-2608-0141")
        payment = _a_payment(brazos, account, ORIGINAL_TOTAL, no="PMT-000001")
        original_row = _allocate(brazos, payment, bill, ORIGINAL_TOTAL)

        result = _release(bill, actor=dana)

        assert result.released == ORIGINAL_TOTAL
        assert result.currency == "USD"
        assert len(result.rows) == 1
        assert result.rows[0].payment_no == "PMT-000001"
        assert result.rows[0].amount == ORIGINAL_TOTAL

        rows = list(
            payment_models.Allocation.objects.filter(invoice=bill).order_by("created_at", "id")
        )
        assert [row.amount for row in rows] == [ORIGINAL_TOTAL, -ORIGINAL_TOTAL]
        assert {row.payment_id for row in rows} == {payment.pk}
        original_row.refresh_from_db()
        assert original_row.amount == ORIGINAL_TOTAL, "the original row is NEVER edited"


def test_cs36_task19_tc2__a_replayed_release_takes_nothing_off_twice(brazos, dana):
    """Hard rule 6. The NET arithmetic is the guard, not a second key.

    CS-36: the case row *"holds one row per bill and only moves `queued` to
    `done`, so the guard exists and must be relied on rather than reinvented"*.
    What is proved here is that the arithmetic agrees with it: a second call
    finds net 0.00 and writes NOTHING. A row-by-row mirror would mirror its own
    negative rows back into positives and re-apply 247.87 to a bill nobody owes.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos)
        bill = an_issued_bill(brazos, account, run, invoice_no="BL-2608-0142")
        payment = _a_payment(brazos, account, ORIGINAL_TOTAL, no="PMT-000001")
        _allocate(brazos, payment, bill, ORIGINAL_TOTAL)

        first = _release(bill, actor=dana)
        second = _release(bill, actor=dana)

        assert first.released == ORIGINAL_TOTAL
        assert second.released == Decimal("0")
        assert second.rows == ()
        assert payment_models.Allocation.objects.filter(invoice=bill).count() == 2
        assert selectors.account_credit_position(account.pk) == ORIGINAL_TOTAL


def test_cs36_task19_tc3__the_service_refuses_outside_a_transaction(brazos, dana, monkeypatch):
    """BR-PAY-1074's second half, enforced rather than documented.

    A release that committed on its own would leave the customer holding a
    credit against a bill that was never issued, if the rebill then failed. The
    refusal is what stops a future caller writing that by omission — hard-won
    law 3, the unsafe option is the one you type.

    ⚠ **THE ABSENCE OF A TRANSACTION IS SIMULATED, AND THAT IS SAID OUT LOUD
    RATHER THAN LEFT TO BE FOUND (hard-won law 1).** `pytest.mark.django_db`
    wraps every case in an atomic block, so inside this suite `in_atomic_block`
    is *always* true and the refusal is unreachable — a case written the obvious
    way passes having proved nothing, which is a check that cannot fail. What is
    asserted is the GUARD, on a connection reporting what a caller outside a
    transaction would report. The real-transaction half — that the release and
    the rebill roll back together — is TC-12 here and is proved again on
    PostgreSQL in `test_cr059_cs36_restatement_pg.py`.
    """

    class _NotInATransaction:
        in_atomic_block = False

    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos)
        bill = an_issued_bill(brazos, account, run, invoice_no="BL-2608-0143")
        payment = _a_payment(brazos, account, ORIGINAL_TOTAL, no="PMT-000001")
        _allocate(brazos, payment, bill, ORIGINAL_TOTAL)

        monkeypatch.setattr(
            allocation_release.transaction, "get_connection", lambda *a, **k: _NotInATransaction()
        )
        with pytest.raises(PaymentRuleError) as refusal:
            allocation_release.release_allocations_for_invoice(
                invoice_id=bill.pk, reason="wrong_read", actor=dana
            )
        assert "INSIDE the correction's own transaction" in str(refusal.value)
        assert payment_models.Allocation.objects.filter(invoice=bill).count() == 1


def test_cs36_task19_tc4__two_payments_release_as_two_rows_oldest_first(brazos, dana):
    """A bill met by two receipts comes off as two rows, one per payment.

    Per PAYMENT and not per row, so the money can be put back where it came
    from — the credit position is *"June's 40.00 and July's 17.13"*, never a
    share of a pooled figure (US-PAY-007 TC-4b). Oldest receipt first, the same
    order `credit._unapplied_by_payment` draws credit down in.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos)
        bill = an_issued_bill(brazos, account, run, invoice_no="BL-2608-0144")
        july = _a_payment(brazos, account, Decimal("47.87"), no="PMT-000002")
        june = _a_payment(brazos, account, Decimal("200.00"), no="PMT-000001", posted_at=EARLIER)
        _allocate(brazos, july, bill, Decimal("47.87"))
        _allocate(brazos, june, bill, Decimal("200.00"))

        result = _release(bill, actor=dana)

        assert result.released == ORIGINAL_TOTAL
        assert [(row.payment_no, row.amount) for row in result.rows] == [
            ("PMT-000001", Decimal("200.00")),
            ("PMT-000002", Decimal("47.87")),
        ]


def test_cs36_task19_tc5__a_bill_already_re_opened_by_a_bounce_releases_nothing(brazos, dana):
    """The cheque came back, so there is nothing on this bill to take off.

    Releasing here would write a POSITIVE row (mirroring the bounce's negative
    one) and re-apply money the bank took back.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos)
        bill = an_issued_bill(brazos, account, run, invoice_no="BL-2608-0145")
        original = _a_payment(brazos, account, ORIGINAL_TOTAL, no="PMT-000001")
        _allocate(brazos, original, bill, ORIGINAL_TOTAL)
        bounce = payment_models.Payment.objects.create(
            tenant=brazos,
            account=account,
            payment_no="PMT-000002",
            amount=-ORIGINAL_TOTAL,
            currency="USD",
            status=payment_models.PAYMENT_REVERSED,
            posted_at=POSTED_AT,
            cleared_at=POSTED_AT,
            reverses_payment=original,
        )
        _allocate(brazos, bounce, bill, -ORIGINAL_TOTAL)

        result = _release(bill, actor=dana)

        assert result.released == Decimal("0")
        assert payment_models.Allocation.objects.filter(invoice=bill).count() == 2


def test_cs36_task19_tc6__a_part_paid_bill_releases_exactly_what_was_applied(brazos, dana):
    """CS-36's third shape. 60.00 of a 100.00 bill comes off as 60.00.

    No special case: the same one step, releasing what is there.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos)
        bill = an_issued_bill(brazos, account, run, invoice_no="BL-2608-0146")
        payment = _a_payment(brazos, account, Decimal("60.00"), no="PMT-000001")
        _allocate(brazos, payment, bill, Decimal("60.00"))

        assert _release(bill, actor=dana).released == Decimal("60.00")
        assert selectors.account_credit_position(account.pk) == Decimal("60.00")


def test_cs36_task19_tc7__two_currencies_on_one_bill_refuse_by_name(brazos, dana):
    """Hard rule 2 — a money figure never travels without its CHAR(3).

    One currency per utility and never converted (BR-TEN-042), so two codes on
    one bill is a broken world. Refused rather than summed into a figure whose
    unit nobody could state.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos)
        bill = an_issued_bill(brazos, account, run, invoice_no="BL-2608-0147")
        usd = _a_payment(brazos, account, Decimal("100.00"), no="PMT-000001")
        cad = _a_payment(brazos, account, Decimal("47.87"), no="PMT-000002", currency="CAD")
        _allocate(brazos, usd, bill, Decimal("100.00"))
        _allocate(brazos, cad, bill, Decimal("47.87"))

        with pytest.raises(PaymentRuleError) as refusal:
            _release(bill, actor=dana)
        assert "more than one currency" in str(refusal.value)
        assert payment_models.Allocation.objects.filter(invoice=bill).count() == 2


def test_cs36_task19_tc8__a_release_writes_no_journal_line(brazos, dana):
    """BR-PAY-1073 — no money moves, so nothing is posted.

    The customer's cash is already in the books, the credit note reverses the
    original's revenue and receivable, and the rebill posts its own. This step
    re-points a SUBLEDGER application. Rule 5 is not reached around; there is
    nothing to post.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos)
        bill = an_issued_bill(brazos, account, run, invoice_no="BL-2608-0148")
        payment = _a_payment(brazos, account, ORIGINAL_TOTAL, no="PMT-000001")
        _allocate(brazos, payment, bill, ORIGINAL_TOTAL)

        before = ledger_models.JournalEntry.objects.count()
        _release(bill, actor=dana)
        assert ledger_models.JournalEntry.objects.count() == before


def test_cs36_task19_tc9__the_release_writes_its_own_audit_row(brazos, dana, audit_rows):
    """Hard rule 7 — every money action writes `audit_log`, inside the write.

    The row is what S33 reads to render the negative allocation as *"re-allocated
    — bill corrected"* rather than as an unexplained negative row (task 20), so
    the released figure, the reason and the rows are all on it.

    Read from the suite's capture sink rather than from the table: an autouse
    fixture in `test_us_met_helpers` swaps `core.audit`'s sink for a list, so a
    case that queried `AuditLog` would find nothing and could not tell that from
    a row never written.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos)
        bill = an_issued_bill(brazos, account, run, invoice_no="BL-2608-0149")
        payment = _a_payment(brazos, account, ORIGINAL_TOTAL, no="PMT-000001")
        _allocate(brazos, payment, bill, ORIGINAL_TOTAL)

        _release(bill, actor=dana)

        written = [row for row in audit_rows if row["action"] == allocation_release.AUDIT_RELEASED]
        assert len(written) == 1
        row = written[0]
        assert row["entity_type"] == "invoice"
        assert row["entity_id"] == str(bill.pk)
        # The trail records the EXACT stored value, so the assertion compares
        # Decimals rather than strings: `allocations.amount` is a lawful 18,6
        # container and its scale is the database's, not this test's.
        assert Decimal(row["after"]["released"]) == ORIGINAL_TOTAL
        assert row["after"]["currency"] == "USD"
        assert row["after"]["reason"] == "wrong_read"
        # BR-PAY-1073, said out loud in the trail a finance user reads.
        assert row["after"]["journal_entry_id"] is None
        assert len(row["after"]["rows"]) == 1


def test_cs36_task19_tc10__a_bill_nobody_paid_releases_nothing_and_audits_nothing(
    brazos, dana, audit_rows
):
    """0.00 released is a real answer and is not an event.

    An audit row for a money action that moved no money would put noise in the
    trail a finance user reads (hard rule 7 owes a row for money that MOVED).
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos)
        bill = an_issued_bill(brazos, account, run, invoice_no="BL-2608-0150")

        result = _release(bill, actor=dana)
        assert result.released == Decimal("0")
        assert result.currency is None
        assert not [row for row in audit_rows if row["action"] == allocation_release.AUDIT_RELEASED]


# ═══════════════════════════════════════════════════════════════════════════
# THE ORDER — the whole trick, and it is invisible in the code
# ═══════════════════════════════════════════════════════════════════════════
def _stub_the_rebill(monkeypatch, rebill, *, recorder=None):
    """Stub the three neighbours, exactly as the US-BIL-016 suite does.

    The rebill's PRICING and ISSUE are stubbed; the release is NOT. What these
    cases are about is the ORDER of two calls inside one function, so the two
    calls are what is recorded.
    """
    import apps.billing.issue as issue_module

    monkeypatch.setattr(corrections, "post_credit_note_reversal", lambda *a, **k: None)
    monkeypatch.setattr(corrections.single, "prepare_single_bill", lambda **k: _PreparedStub())
    monkeypatch.setattr(corrections.single, "calculate_single_bill", lambda *a, **k: rebill)

    def _issue(invoice, **kwargs):
        if recorder is not None:
            recorder.append("issue")
        return invoice

    monkeypatch.setattr(issue_module, "issue_invoice", _issue)


def _an_impact(bill, corrected_total=Decimal("227.95")):
    return corrections.build_impact(
        bill,
        reason_codes=("wrong_read",),
        correction_class=CLASS_RESTATEMENT,
        corrected=_RatedBill(
            [_RatedLine("usage", "Water usage 6 kgal", corrected_total)], corrected_total
        ),
    )


def test_cs36_task19_tc11__the_release_happens_BEFORE_the_rebill_issues(brazos, dana, monkeypatch):
    """BR-PAY-1074. ⚠ THE ORDERING IS THE RULE — CS-36: *"the order is the whole trick"*.

    Release AFTER the issue and the rebill draws down a credit balance that does
    not exist yet: it goes out unsettled, at the ORIGINAL due date, so the
    customer is *"overdue on arrival"* for money they have already paid. Nothing
    about the two call sites looks ordered, which is exactly why this is
    asserted rather than left to a reader.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos)
        bill = an_issued_bill(brazos, account, run, invoice_no="BL-2608-0151")
        rebill = an_issued_bill(
            brazos, account, run, invoice_no="BL-2608-0166", status=models.INVOICE_DRAFT
        )
        payment = _a_payment(brazos, account, ORIGINAL_TOTAL, no="PMT-000001")
        _allocate(brazos, payment, bill, ORIGINAL_TOTAL)

        order: list[str] = []
        _stub_the_rebill(monkeypatch, rebill, recorder=order)
        real_release = allocation_release.release_allocations_for_invoice

        def _recorded(**kwargs):
            order.append("release")
            return real_release(**kwargs)

        monkeypatch.setattr(allocation_release, "release_allocations_for_invoice", _recorded)

        result = corrections.execute_restatement(
            bill,
            impact=_an_impact(bill),
            reason="wrong_read",
            issued_at=ISSUED_AT,
            on_date=TODAY,
            template_id=bill.template_id,
            template_version=1,
            actor=dana,
        )

        assert order == ["release", "issue"], "the release must land BEFORE the rebill issues"
        assert result.released_amount == ORIGINAL_TOTAL
        assert result.released_rows[0]["payment_no"] == "PMT-000001"


def test_cs36_task19_tc12__the_release_and_the_rebill_are_ONE_transaction(
    brazos, dana, monkeypatch
):
    """BR-PAY-1074's other half — both land, or neither does.

    The rebill's issue is made to fail. Afterwards there is no credit note, no
    rebill AND no release: the customer's money is still on the original bill,
    which is exactly right, because the bill was never replaced. A release in a
    transaction of its own would have left him holding a credit against nothing.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos)
        bill = an_issued_bill(brazos, account, run, invoice_no="BL-2608-0152")
        rebill = an_issued_bill(
            brazos, account, run, invoice_no="BL-2608-0167", status=models.INVOICE_DRAFT
        )
        payment = _a_payment(brazos, account, ORIGINAL_TOTAL, no="PMT-000001")
        _allocate(brazos, payment, bill, ORIGINAL_TOTAL)

        _stub_the_rebill(monkeypatch, rebill)
        import apps.billing.issue as issue_module

        def _explode(invoice, **kwargs):
            raise BillingRuleError("the rebill could not be issued", br_ref="BR-BIL-047")

        monkeypatch.setattr(issue_module, "issue_invoice", _explode)

        with pytest.raises(BillingRuleError):
            corrections.execute_restatement(
                bill,
                impact=_an_impact(bill),
                reason="wrong_read",
                issued_at=ISSUED_AT,
                on_date=TODAY,
                template_id=bill.template_id,
                template_version=1,
                actor=dana,
            )

        assert not models.CreditNote.objects.filter(original_invoice=bill).exists()
        assert payment_models.Allocation.objects.filter(invoice=bill).count() == 1
        assert selectors.account_credit_position(account.pk) == Decimal("0")
        assert models.Invoice.objects.get(pk=bill.pk).status == models.INVOICE_ISSUED


def test_cs36_task19_tc13__an_unreachable_payments_module_refuses_the_correction(
    brazos, dana, monkeypatch
):
    """Hard-won law 3 — the silent version is the damage, so it fails CLOSED.

    This is the OPPOSITE posture to `apply_credit_at_issue`, where an unreachable
    seam reports and the bill still issues. Here, proceeding would credit the
    original, issue a replacement and leave the money pointing at a bill nothing
    reads — a wrong number reaching a customer with nothing reporting it.
    """
    from apps.billing import payments_seam

    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos)
        bill = an_issued_bill(brazos, account, run, invoice_no="BL-2608-0153")
        rebill = an_issued_bill(
            brazos, account, run, invoice_no="BL-2608-0168", status=models.INVOICE_DRAFT
        )
        payment = _a_payment(brazos, account, ORIGINAL_TOTAL, no="PMT-000001")
        _allocate(brazos, payment, bill, ORIGINAL_TOTAL)
        _stub_the_rebill(monkeypatch, rebill)
        monkeypatch.setattr(payments_seam, "_resolve", lambda module, attribute: None)

        with pytest.raises(BillingRuleError) as refusal:
            corrections.execute_restatement(
                bill,
                impact=_an_impact(bill),
                reason="wrong_read",
                issued_at=ISSUED_AT,
                on_date=TODAY,
                template_id=bill.template_id,
                template_version=1,
                actor=dana,
            )
        assert "release_allocations_for_invoice" in str(refusal.value)
        assert not models.CreditNote.objects.filter(original_invoice=bill).exists()
        assert models.Invoice.objects.get(pk=bill.pk).status == models.INVOICE_ISSUED


def test_cs36_task19_tc14__the_released_money_is_immediately_drawable_credit(brazos, dana):
    """BR-PAY-010 — the rest of the fix is machinery that already works.

    CS-36: *"the credit position rises on its own … and the rebill draws it
    down"*. Nothing was added for either half; this proves the released money is
    in the shape `credit.apply_credit_at_issue` consumes, which is what makes
    the whole change one inserted step.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos)
        bill = an_issued_bill(brazos, account, run, invoice_no="BL-2608-0154")
        rebill = an_issued_bill(
            brazos, account, run, invoice_no="BL-2608-0169", total=Decimal("227.95")
        )
        payment = _a_payment(brazos, account, ORIGINAL_TOTAL, no="PMT-000001")
        _allocate(brazos, payment, bill, ORIGINAL_TOTAL)

        _release(bill, actor=dana)
        assert selectors.account_credit_position(account.pk) == ORIGINAL_TOTAL

        applied = credit.apply_credit_at_issue(
            actor=dana,
            account_id=account.pk,
            invoice_id=rebill.pk,
            invoice_total=Decimal("227.95"),
        )
        assert applied.applied == Decimal("227.95")
        # 247.87 − 227.95 = 19.92, the WE-9 delta, left as visible credit.
        assert selectors.account_credit_position(account.pk) == Decimal("19.92")


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-059 §8 CS-36 · §11 task 19 · §7 (the bounce's second step, the
#         credit position's arithmetic) · CLAUDE.md rules 4/5/6/7 + law 14
# generated: 2026-09-01 by the CR-059 W4 CS-36 lane (tasks 14/19/21)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — CS-36 asks for no route)
#         E=deferred(no-frontend-half — S30/S21/S33 are task 20) F✔ G✔
#         H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · proved RED first — the release call was deleted from
#         `execute_restatement` (TC-11/TC-14 red), moved AFTER `issue_invoice`
#         (TC-11 red on `['issue', 'release'] == ['release', 'issue']`), and the
#         transaction guard removed (TC-3 red). Transcripts in the lane report.
# exceptions: (1) THE MONEY OUTCOME IS NOT ASSERTED HERE — the three shapes, the
#         subledger/ledger tie-out, the replay and the goodwill run on
#         PostgreSQL in test_cr059_cs36_restatement_pg.py (task 21), because
#         law 14 makes a SQLite proof of a multi-statement transaction worthless.
#         (2) The rebill's PRICING and ISSUE are stubbed here, the same three
#         neighbours the US-BIL-016 suite stubs, because these cases are about
#         the ORDER of two calls and not about the arithmetic.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
