# ── Trace ──────────────────────────────────────────────
# Story:    US-PAY-001 (single payment entry — TC-1 the PE-1 check, TC-2 the
#           posting/clearing pair, TC-3 the method lookup, TC-5 the negative
#           amounts, TC-6 the double submit + the frozen row, TC-7 isolation) ·
#           US-PAY-006 (allocation — the `allocations` rows, the oldest-first
#           walk, the carried credit, the four-class order)
#           Screens: S22 · S32 · S33 · S35
# Rules:    BR-PAY-001 · BR-PAY-002 · BR-PAY-010 · BR-PAY-012 · BR-PAY-021 ·
#           BR-PAY-022 · BR-PAY-026 · BR-PAY-028 · BR-PAY-031 · BR-PAY-033 ·
#           BR-PAY-036 · BR-PAY-038 · BR-TEN-029 · BR-TEN-035 · BR-TEN-042 ·
#           BR-TEN-043 · CLAUDE.md rules 1, 2, 4, 5, 6, 7
# Golden:   GT-7 — B5 ❄️ FROZEN 2026-08-08 (asserted at the pure-function level
#           in tests/golden/test_gt07_partial_allocation.py; this file asserts
#           the WRITE path that calls it) · PE-1 / PE-2 / PE-4 (the payments
#           worked examples, 08-payments/07-pre-session-model.md §3/§13) ·
#           LE-1 (the ledger workbook's payment leg: cash DR 292.87 / AR CR)
# ───────────────────────────────────────────────────────
"""Recording a payment: the closed loop, and every guard that stands around it.

**THE TEST THIS FILE EXISTS FOR** is `test_us_pay_001_tc1__pe1_check_settles_two_bills`.
Until 2026-08-11 nothing in this product could receive a payment: the payments
module defined no tables and `apps/ledger/posting.py` — the sole writer of
journal lines — was called by nothing at all. That case takes PE-1's check for
$292.87, settles a $45.00 bill and a $247.87 bill oldest-first, and reads the
journal entry back out of `journal_lines`. If a future change breaks the loop,
that test says where.

EVERY FIGURE HERE IS COPIED, NEVER COMPUTED. PE-1..PE-4 and LE-1 are the
ratified worked examples and the numbers below are transcribed with the line
they came from quoted beside them. A test that recomputed its own expectation
would agree with a broken implementation.

WHAT RUNS WHERE, because it changes what a green run is worth:

  * The SERVICE-LAYER refusals — a float amount, a zero, a cross-tenant
    account, an unknown method, an unsupported purpose, a duplicate submit —
    run everywhere. They are what protects the SQLite developer database, which
    has no triggers and no RLS.
  * The DATABASE laws — the immutability triggers, the deny-by-default freeze,
    the `uq_payments_webhook_key` index and RLS — carry `requires_postgres` and
    SKIP on SQLite rather than passing vacuously.

EVERY GUARD IN THIS FILE WAS DRIVEN RED BEFORE IT WAS TRUSTED GREEN (hard-won
law 7). The five proofs, each run and each quoted verbatim in the lane report:
the immutability trigger dropped (an UPDATE on a cleared payment's amount
SUCCEEDS); the idempotency lookup removed (a double submit records TWO payments
and doubles the money); the RLS policy dropped (a cross-tenant read returns the
other tenant's payments); the ledger seam made a no-op (money is recorded that
never reaches the books); and the class order inverted (a late fee is paid
before the tenant-defined class, against the PO's own $128.88 figure).
"""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from django.db import DatabaseError, IntegrityError, connection, transaction

from core import errors

from apps.payments import billing_seam, idempotency, ledger_seam, models, services
from apps.payments.exceptions import PaymentRuleError

from tests.isolation_helpers import (
    assert_denied_without_context,
    assert_rls_scoped,
    live_tenant_context,
    requires_postgres,
    rls,  # noqa: F401 — fixture
    rls_probe_role,  # noqa: F401 — fixture
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_w3_billing_models import an_account

pytestmark = pytest.mark.django_db

# ── PE-1, verbatim (08-payments/07-pre-session-model.md §13 · EP-PAY-01 §4) ──
# "ACC-1042 (WE-1 fixture): open BL-2607-018311 $45.00 (due Jul 22) +
#  BL-2608-018410 $247.87 (due Aug 22; usage+base 221.90 · taxes 20.97 · late
#  5.00). PE-1 payment: check #8842, $292.87, Aug 8, 2026."
OLD_BILL_TOTAL = Decimal("45.00")
NEW_BILL_TOTAL = Decimal("247.87")
PE1_CHECK = Decimal("292.87")

#: PE-4, verbatim: "open 292.87, pay 350 → bills settled + credit 57.13".
PE4_PAYMENT = Decimal("350.00")
PE4_CREDIT = Decimal("57.13")

#: PE-2, verbatim: "bill $247.87 …, pay $200 → … outstanding $47.87".
PE2_PAYMENT = Decimal("200.00")
PE2_OUTSTANDING = Decimal("47.87")

# ── The PO's own OQ-109 figure (BR-PAY-038, ruling 2026-08-11) ──────────────
# "usage+base $100.58 + tax $8.30 + a tenant-defined service fee $15.00 + a late
#  fee $5.00 = $128.88; a payment of $120.00 meets $100.58, then $8.30, then
#  $11.12 of the $15.00, and the late fee stays LAST at $0.00."
FOUR_CLASS_TOTAL = Decimal("128.88")
FOUR_CLASS_PAYMENT = Decimal("120.00")
FOUR_CLASS_USAGE_BASE = Decimal("100.58")
FOUR_CLASS_TAX = Decimal("8.30")
FOUR_CLASS_TENANT_DEFINED_BILLED = Decimal("15.00")
FOUR_CLASS_TENANT_DEFINED_MET = Decimal("11.12")
FOUR_CLASS_LATE_FEE = Decimal("5.00")

#: BR-PAY-021's pair, kept APART on purpose. PE-1 has them equal (Aug 8); the
#: two-date fixture of US-PAY-001 TC-2 is "posted Aug 22 / cleared Aug 25", and
#: every case that is not about the pair uses the PE-1 shape.
POSTED_AT = datetime(2026, 8, 8, 10, 30, tzinfo=UTC)
CLEARED_AT = datetime(2026, 8, 8, 10, 30, tzinfo=UTC)
TC2_POSTED_AT = datetime(2026, 8, 22, 16, 5, tzinfo=UTC)
TC2_CLEARED_AT = datetime(2026, 8, 25, 9, 0, tzinfo=UTC)


# ── fixture helpers ─────────────────────────────────────────────────────────
def an_issued_bill(tenant, account, *, number, total, issued_on, **overrides):
    """One ISSUED bill of `account`, in the shape `record_payment` will meet it.

    Created through billing's ORM directly rather than through its issue path,
    which would drag the whole rating engine, the GL stamp and the release gate
    into a payments test. What this file is about is what happens to a bill
    AFTER it exists, and `issued_at` is the only issue-time fact an allocation
    reads (BR-PAY-001: "oldest").
    """
    from apps.billing import models as billing_models

    values = dict(
        tenant=tenant,
        account=account,
        invoice_no=number,
        status=billing_models.INVOICE_ISSUED,
        service_date=issued_on,
        period_start=issued_on.replace(day=1),
        period_end=issued_on,
        due_date=issued_on,
        subtotal=total,
        tax_total=Decimal("0"),
        total=total,
        issued_at=datetime(issued_on.year, issued_on.month, issued_on.day, 9, 0, tzinfo=UTC),
    )
    values.update(overrides)
    return billing_models.Invoice.objects.create(**values)


def pe1_bills(tenant, account):
    """PE-1's two open bills: July $45.00 (older) and August $247.87."""
    old = an_issued_bill(
        tenant,
        account,
        number="BL-2607-018311",
        total=OLD_BILL_TOTAL,
        issued_on=date(2026, 7, 1),
    )
    new = an_issued_bill(
        tenant,
        account,
        number="BL-2608-018410",
        total=NEW_BILL_TOTAL,
        issued_on=date(2026, 8, 1),
    )
    return old, new


def a_payment(actor, account, *, amount=PE1_CHECK, **overrides):
    """The PE-1 single entry, through the real service — no ORM shortcuts."""
    values = dict(
        account_id=account.pk,
        amount=amount,
        posted_at=POSTED_AT,
        cleared_at=CLEARED_AT,
        confirmation="8842",
        idempotency_reference=uuid.uuid4(),
    )
    values.update(overrides)
    return services.record_payment(actor, **values)


def journal_legs(tenant):
    """Every posted journal line of a tenant as `(code, side, amount)`.

    Summed out of `journal_lines` by hand rather than through a ledger selector:
    what this asserts is what LANDED, and a reporting layer that was wrong in
    the same direction would agree with a broken posting.
    """
    from apps.ledger import models as ledger_models

    return [
        (code, side, amount)
        for code, side, amount in ledger_models.JournalLine.objects.filter(
            tenant=tenant, journal_entry__status=ledger_models.JE_POSTED
        ).values_list("ledger_account__code", "side", "amount")
    ]


def leg(legs, code, side):
    """The one amount posted to `code` on `side`, or Decimal 0 when none was."""
    found = [amount for gl, gl_side, amount in legs if gl == code and gl_side == side]
    return sum(found, Decimal("0"))


def a_composition_read(monkeypatch, rows):
    """Publish billing's PREFERRED read — the contract `billing_seam` names.

    `apps.billing.selectors.issued_invoices_for_account` does not exist yet (the
    billing lane owns it and another lane is in those files). The seam resolves
    it BY NAME at call time, so setting it here is exactly the state a
    deployment is in the day billing publishes it — which is what makes the
    four-class case below a test of the WIRING and not of a mock.
    """
    from apps.billing import selectors as billing_selectors

    monkeypatch.setattr(
        billing_selectors, "issued_invoices_for_account", lambda _id: rows, raising=False
    )


def a_tenant_defined_class(monkeypatch, members=("service_fee",)):
    """Publish the LEDGER read that carries the fourth class's membership.

    BR-PAY-038's amendment is as binding as the option: the class's MEMBERSHIP
    is tenant configuration IN THE LEDGER (*"allow tenant user to define it in
    ledge[r]"*), so `allocation.py` REFUSES a bill that states the class while
    the tenant has defined nothing — fail closed, and `tc3b` below proves that
    refusal reaches the write path.

    This publishes it for a tenant who HAS defined one, which is the state the
    PO's own worked figure describes. Resolved by name at call time, so this is
    exactly what the ledger lane will do.
    """
    from apps.ledger import selectors as ledger_selectors

    monkeypatch.setattr(
        ledger_selectors, "allocation_class_members", lambda: set(members), raising=False
    )


def audit_actions_for(rows, action):
    return [row for row in rows if row["action"] == action]


# ── TC-1 · the case this file exists for ────────────────────────────────────
def test_us_pay_001_tc1__pe1_check_settles_two_bills(brazos, marcus, audit_rows):
    """US-PAY-001 TC-1 / PE-1, verbatim: check #8842, $292.87, apply-to oldest.

    Five things become true in one transaction and all five are asserted here,
    because any one of them missing is a broken loop that every other test would
    still pass: the `payments` row with BOTH dates, its PMT number, the two
    `allocations` rows oldest-first, the audit pair, and the journal entry.

    The ledger legs are LE-1's own: *"payment (cash DR 292.87 / AR CR)"*.
    """
    with tenant_ctx(brazos):
        account = an_account(marcus, brazos)
        old, new = pe1_bills(brazos, account)

        result = a_payment(marcus, account)

        assert result.created is True
        # CR-186-BRC10 (PO 2026-10-21): posted at entry; cleared at reconciliation.
        assert result.status == models.PAYMENT_POSTED
        assert result.amount == PE1_CHECK
        # PE-1: the oldest bill in FULL first, then the newer one.
        assert result.applied == PE1_CHECK
        assert result.credit_carried == Decimal("0")
        assert [(row["invoice_number"], row["amount"]) for row in result.allocations] == [
            ("BL-2607-018311", OLD_BILL_TOTAL),
            ("BL-2608-018410", NEW_BILL_TOTAL),
        ]

        payment = models.Payment.objects.get(pk=result.payment_id)
        # BR-PAY-021 — both dates, always. Stored distinctly even when equal.
        assert payment.posted_at == POSTED_AT
        # CR-186-BRC10 — the clearing date is the bank reconciliation's.
        assert payment.cleared_at is None
        assert payment.payment_no, "BR-TEN-035: a number is allocated at record"
        assert payment.purpose == models.PURPOSE_BILL
        assert payment.currency == account.currency

        rows = models.Allocation.objects.filter(payment=payment).order_by("amount")
        assert [row.amount for row in rows] == [OLD_BILL_TOTAL, NEW_BILL_TOTAL]
        assert {row.invoice_id for row in rows} == {old.pk, new.pk}

        # hard rule 7 — both money events, in the same transaction.
        assert len(audit_actions_for(audit_rows, services.AUDIT_RECORDED)) == 1
        assert len(audit_actions_for(audit_rows, services.AUDIT_ALLOCATED)) == 1

        # CLAUDE.md rule 5 — and LE-1's own leg. The payment REACHED THE BOOKS.
        assert result.posted_to_ledger is True
        assert result.journal_entry_id is not None
        assert result.posting_key == f"payment|{payment.pk}|cleared"
        legs = journal_legs(brazos)
        # ⚠ PO ruling 2026-08-11 (OQ-143 CLOSED → BR-PAY-039): the RECEIPT leg
        # debits **1010 Undeposited funds**, not 1000 Cash — *"until bank record
        # and reconcilaition confirm it it is not realised"*. This case asserted
        # 1000 until that ruling; LE-1's `cash DR 292.87` is now the NET of two
        # steps and the second one is the bank reconciliation
        # (tests/test_us_pay_020_023_bank_rec.py asserts it lands in 1000 there).
        assert leg(legs, "1010", "debit") == PE1_CHECK  # money taken, not yet banked
        assert leg(legs, "1000", "debit") == Decimal("0"), "cash is realised at reconciliation"
        assert leg(legs, "1200", "credit") == PE1_CHECK  # LE-1: AR CR
        assert leg(legs, "1010", "debit") == leg(legs, "1200", "credit")


def test_us_pay_001_tc2__posting_and_clearing_are_different_dates(brazos, marcus):
    """US-PAY-001 TC-2 — "Check posted Aug 22 (= due date), cleared Aug 25".

    BR-PAY-021 is the cardinal rule of this module and the only way to test it
    is with two dates that DIFFER: if they were equal every wrong basis would
    give the right answer. The bill's BOOK date is the CLEARING date, because
    bank reconciliation matches on clearing and cash in the books must agree
    with cash at the bank (BR-PAY-019/021).
    """
    from apps.ledger import models as ledger_models

    with tenant_ctx(brazos):
        account = an_account(marcus, brazos)
        pe1_bills(brazos, account)

        result = a_payment(marcus, account, posted_at=TC2_POSTED_AT, cleared_at=TC2_CLEARED_AT)

        payment = models.Payment.objects.get(pk=result.payment_id)
        assert payment.posted_at.date() == date(2026, 8, 22)
        # ⚠ CR-186-BRC10 (PO 2026-10-21): the clearing date is written by the
        # bank reconciliation, never at entry — a caller's `cleared_at` is not
        # stored, and the two dates still differ (the reconciliation writes the
        # second). The entry is booked on the POSTING date.
        assert payment.cleared_at is None

        entry = ledger_models.JournalEntry.objects.get(pk=result.journal_entry_id)
        assert entry.entry_date == date(2026, 8, 22)
        # … and `posted_at` is the moment the RECORD entered the system, named
        # by the caller and never read from a clock (BR-TEN-043).
        assert entry.posted_at == TC2_POSTED_AT


def test_us_pay_001_tc3__the_four_class_order_pays_the_late_fee_last(
    brazos, marcus, monkeypatch, audit_rows
):
    """BR-PAY-038 — the PO's own worked figure, driven through the WRITE path.

    Verbatim (PO ruling 2026-08-11, OQ-109 option C as amended): *"usage+base
    $100.58 + tax $8.30 + a tenant-defined service fee $15.00 + a late fee $5.00
    = $128.88; a payment of $120.00 meets $100.58, then $8.30, then $11.12 of
    the $15.00, and the late fee stays LAST at $0.00."*

    `tests/test_us_pay_006_allocation.py` asserts that figure on the pure
    function. THIS case asserts that the write path HANDS THE ALLOCATOR THE
    RATIFIED ORDER — the wiring, which is a different failure mode entirely: an
    engine that computes the right answer and a service that passes it the wrong
    class order produce a late fee paid before a service charge, and every
    existing test stays green.

    PROVED RED: with `class_order` inverted so `fees` precedes
    `tenant_defined`, the late fee is met in full at 5.00 and the
    tenant-defined class gets 6.12 — quoted in the lane report.
    """
    with tenant_ctx(brazos):
        account = an_account(marcus, brazos)
        bill = an_issued_bill(
            brazos,
            account,
            number="BL-2608-000128",
            total=FOUR_CLASS_TOTAL,
            issued_on=date(2026, 8, 1),
        )
        a_tenant_defined_class(monkeypatch)
        a_composition_read(
            monkeypatch,
            [
                {
                    "id": bill.pk,
                    "number": bill.invoice_no,
                    "total": FOUR_CLASS_TOTAL,
                    "issued_on": date(2026, 8, 1),
                    "composition": {
                        "usage_base": FOUR_CLASS_USAGE_BASE,
                        "taxes": FOUR_CLASS_TAX,
                        "tenant_defined": FOUR_CLASS_TENANT_DEFINED_BILLED,
                        "fees": FOUR_CLASS_LATE_FEE,
                    },
                }
            ],
        )

        result = a_payment(marcus, account, amount=FOUR_CLASS_PAYMENT)

        assert result.applied == FOUR_CLASS_PAYMENT
        by_class = result.allocations[0]["by_class"]
        assert by_class["usage_base"] == str(FOUR_CLASS_USAGE_BASE)
        assert by_class["taxes"] == str(FOUR_CLASS_TAX)
        assert by_class["tenant_defined"] == str(FOUR_CLASS_TENANT_DEFINED_MET)
        # THE WHOLE POINT: the late fee is LAST and this payment never reached it.
        assert "fees" not in by_class, "a class that received nothing gets no row"

        # The breakdown has no column to live in (B2 §2 — OQ-129), so the audit
        # payload is where tax remittance will read it from. Asserted so the
        # day it gains a column, this test says what moved.
        allocated = audit_actions_for(audit_rows, services.AUDIT_ALLOCATED)[0]
        assert allocated["after"]["allocations"][0]["by_class"]["tenant_defined"] == str(
            FOUR_CLASS_TENANT_DEFINED_MET
        )
        assert allocated["after"]["remaining_by_class"]["fees"] == str(FOUR_CLASS_LATE_FEE)


def test_us_pay_001_tc3b__a_bill_naming_an_undefined_class_refuses_the_payment(
    brazos, marcus, monkeypatch
):
    """BR-PAY-038's amendment, fail-closed, all the way to the write path.

    The MEMBERSHIP of the fourth class is the tenant's and lives in the ledger.
    A bill that states a `tenant_defined` balance while the tenant has defined
    nothing is REFUSED by `allocation.py` — the alternative is money allocated
    into a class nobody defined, at the position that decides how much tax the
    tenant has collected.

    What this case adds beyond the pure-function test is the TRANSLATION: the
    allocator raises `AllocationClassNotConfigured`, a `ValueError`, and a
    caller catching only `PaymentRuleError` would let it escape — DEF-047's
    exact shape. And nothing is written: the payment rolls back with it.
    """
    with tenant_ctx(brazos):
        account = an_account(marcus, brazos)
        bill = an_issued_bill(
            brazos,
            account,
            number="BL-2608-000128",
            total=FOUR_CLASS_TOTAL,
            issued_on=date(2026, 8, 1),
        )
        a_composition_read(
            monkeypatch,
            [
                {
                    "id": bill.pk,
                    "number": bill.invoice_no,
                    "total": FOUR_CLASS_TOTAL,
                    "issued_on": date(2026, 8, 1),
                    "composition": {
                        "usage_base": FOUR_CLASS_USAGE_BASE,
                        "taxes": FOUR_CLASS_TAX,
                        "tenant_defined": FOUR_CLASS_TENANT_DEFINED_BILLED,
                        "fees": FOUR_CLASS_LATE_FEE,
                    },
                }
            ],
        )
        # The ledger publishes NOTHING — today's real state.
        with pytest.raises(PaymentRuleError, match="defined no such class"):
            a_payment(marcus, account, amount=FOUR_CLASS_PAYMENT)

        assert models.Payment.objects.filter(tenant=brazos).count() == 0
        assert models.Allocation.objects.filter(tenant=brazos).count() == 0


def test_us_pay_001_tc4__an_overpayment_carries_credit_and_posts_three_legs(brazos, marcus):
    """PE-4, verbatim: *"open 292.87, pay 350 → bills settled + credit 57.13"*.

    The third journal leg is the one US-LED-001's contract table does not spell
    out and `ledger_seam` derives: the credit has to be CREDITED somewhere or
    the entry cannot balance, and `customer_credit_balance` (2400) is the
    designation the refund row later DEBITS. If that reasoning is ever
    overturned, this is the test that has to move.
    """
    with tenant_ctx(brazos):
        account = an_account(marcus, brazos)
        pe1_bills(brazos, account)

        result = a_payment(marcus, account, amount=PE4_PAYMENT)

        assert result.applied == PE1_CHECK
        assert result.credit_carried == PE4_CREDIT

        legs = journal_legs(brazos)
        # BR-PAY-039 (PO ruling 2026-08-11): every cent received, into
        # UNDEPOSITED FUNDS — the bank has confirmed none of it yet.
        assert leg(legs, "1010", "debit") == PE4_PAYMENT
        assert leg(legs, "1200", "credit") == PE1_CHECK  # what met bills
        assert leg(legs, "2400", "credit") == PE4_CREDIT  # BR-PAY-012's credit
        debits = sum(a for _c, s, a in legs if s == "debit")
        credits = sum(a for _c, s, a in legs if s == "credit")
        assert debits == credits, "hard rule 5 — a posted entry balances to the cent"


def test_us_pay_001_tc4b__a_partial_payment_leaves_the_pe2_outstanding(brazos, marcus):
    """PE-2, verbatim: *"bill $247.87 …, pay $200 → … outstanding $47.87"*.

    Also the case that proves the OPEN BALANCE is recomputed from `allocations`
    rather than read off billing: a second payment against the same bill sees
    47.87 outstanding, not 247.87. That subtraction is the answer to OQ-113 —
    "unpaid" is the payments position — and nothing else in the product has it.
    """
    with tenant_ctx(brazos):
        account = an_account(marcus, brazos)
        bill = an_issued_bill(
            brazos,
            account,
            number="BL-2608-018410",
            total=NEW_BILL_TOTAL,
            issued_on=date(2026, 8, 1),
        )

        a_payment(marcus, account, amount=PE2_PAYMENT)

        position = billing_seam.open_invoices_for_account(account.pk)
        assert [invoice.balance for invoice in position.invoices] == [PE2_OUTSTANDING]

        second = a_payment(marcus, account, amount=PE2_OUTSTANDING)
        assert second.applied == PE2_OUTSTANDING
        assert second.credit_carried == Decimal("0")
        # Settled: the bill drops out of the open position entirely, and a
        # third payment meets no bill at all rather than a 0.00 allocation row.
        assert billing_seam.open_invoices_for_account(account.pk).invoices == ()
        assert billing_seam.allocated_so_far(bill.pk) == NEW_BILL_TOTAL


def test_us_pay_001_tc5__zero_negative_float_and_no_account_are_refused(brazos, marcus):
    """US-PAY-001 TC-5 — "Amount 0 / negative; account id blank → no row".

    The float case is CLAUDE.md rule 2 and is refused rather than converted: a
    conversion would hide the place where money became binary, and the books
    would carry a figure nobody can reproduce.
    """
    with tenant_ctx(brazos):
        account = an_account(marcus, brazos)

        for amount in (Decimal("0"), Decimal("-10.00")):
            with pytest.raises(PaymentRuleError, match="greater than zero"):
                a_payment(marcus, account, amount=amount)

        with pytest.raises(PaymentRuleError, match="float"):
            a_payment(marcus, account, amount=292.87)

        with pytest.raises(PaymentRuleError, match="names no account"):
            services.record_payment(marcus, account_id=None, amount=PE1_CHECK, posted_at=POSTED_AT)

        # BR-PAY-033 / BR-TEN-043 — the posting date is the USER's, and this
        # module refuses to stamp `now()` on their behalf.
        with pytest.raises(PaymentRuleError, match="POSTING date"):
            services.record_payment(marcus, account_id=account.pk, amount=PE1_CHECK, posted_at=None)

        assert models.Payment.objects.count() == 0, "nothing partial is written"


def test_us_pay_001_tc6__a_double_submit_records_one_payment(brazos, marcus, audit_rows):
    """US-PAY-001 TC-6 — "Double-click Record ✓ → One row only".

    The most expensive bug this module could have: the same money taken twice,
    the customer's balance wrong by the payment amount, and the books out
    against the bank by the same. Two guards stand here and BOTH are asserted —
    the pre-insert lookup (cheap, and what a real double-click hits) and the
    `uq_payments_webhook_key` index (what a genuine race hits).

    PROVED RED: with the lookup removed, this case records TWO payments and
    `applied` doubles to 585.74 — quoted verbatim in the lane report.
    """
    with tenant_ctx(brazos):
        account = an_account(marcus, brazos)
        pe1_bills(brazos, account)
        token = uuid.uuid4()

        first = a_payment(marcus, account, idempotency_reference=token)
        second = a_payment(marcus, account, idempotency_reference=token)

        assert first.created is True
        assert second.created is False
        assert second.payment_id == first.payment_id
        assert second.amount == PE1_CHECK, "the money is not doubled"
        assert second.applied == PE1_CHECK

        assert models.Payment.objects.count() == 1
        assert models.Allocation.objects.count() == 2
        assert len(audit_actions_for(audit_rows, services.AUDIT_RECORDED)) == 1

        from apps.ledger import models as ledger_models

        assert ledger_models.JournalEntry.objects.count() == 1
        assert any(problem["code"] == "duplicate_submit_ignored" for problem in second.problems)

        # The key is namespaced, so a webhook redelivery of a DIFFERENT event
        # carrying the same reference is a different string and lawfully lands.
        assert idempotency.inbound_payment_key(
            source=idempotency.SOURCE_ENTRY, reference=token
        ) != idempotency.inbound_payment_key(source=idempotency.SOURCE_WEBHOOK, reference=token)


@requires_postgres
def test_us_pay_001_tc6b__the_database_refuses_a_duplicate_key(brazos, marcus):
    """The second half of hard rule 6: the INDEX, not the lookup.

    A lost race and a replay are the same fact — one payment exists, ours is not
    it — and only the database can decide that. Written as a raw INSERT so the
    service's own lookup cannot be what makes it pass.
    """
    with tenant_ctx(brazos):
        account = an_account(marcus, brazos)
        key = idempotency.inbound_payment_key(source=idempotency.SOURCE_ENTRY, reference="tok-1")
        models.Payment.objects.create(
            tenant=brazos,
            account=account,
            amount=PE1_CHECK,
            currency=account.currency,
            status=models.PAYMENT_PROCESSING,
            posted_at=POSTED_AT,
            webhook_key=key,
        )
        with pytest.raises(IntegrityError), transaction.atomic():
            models.Payment.objects.create(
                tenant=brazos,
                account=account,
                amount=PE1_CHECK,
                currency=account.currency,
                status=models.PAYMENT_PROCESSING,
                posted_at=POSTED_AT,
                webhook_key=key,
            )


@pytest.mark.isolation
def test_us_pay_001_tc7__a_payment_never_crosses_a_tenant(brazos, lonestar, marcus, erin):
    """US-PAY-001 TC-7 — "J. Okafor posts a payment naming a Brazos Bend account".

    Two independent guarantees, and both are checked because either alone can be
    bypassed: the SERVICE refuses the foreign account id (it resolves through
    customers' tenant-scoped read and comes back empty), and RLS refuses the row
    to a non-superuser probe role even if the service were bypassed.
    """
    with tenant_ctx(brazos):
        brazos_account = an_account(marcus, brazos)
        pe1_bills(brazos, brazos_account)
        a_payment(marcus, brazos_account)

    with tenant_ctx(lonestar):
        with pytest.raises(PaymentRuleError, match="not an account of this tenant"):
            services.record_payment(
                erin,
                account_id=brazos_account.pk,
                amount=PE1_CHECK,
                posted_at=POSTED_AT,
                cleared_at=CLEARED_AT,
                idempotency_reference=uuid.uuid4(),
            )
        # Scoped explicitly rather than counting the whole table: on the SQLite
        # tier there is no RLS to do it, so an unscoped count would see Brazos
        # Bend's row and the assertion would be about the wrong thing. The
        # DATABASE half of the same law is `tc7b`, on live Postgres.
        assert (
            models.Payment.objects.filter(tenant=lonestar).count() == 0
        ), "Lone Star Ridge recorded nothing"


@pytest.mark.isolation
@requires_postgres
def test_us_pay_001_tc7b__rls_scopes_payments_and_allocations(
    brazos, lonestar, marcus, rls
):  # noqa: F811
    """CLAUDE.md rule 1 — the DATABASE refuses, not only the queryset.

    Run under `sbh_rls_probe`, a NOLOGIN NOSUPERUSER NOBYPASSRLS role, because
    the app's own role is a superuser and superusers bypass RLS unconditionally
    — every assertion made on that connection would be vacuous.

    PROVED RED: with `payments_tenant_isolation` dropped from
    `db/rls_payments_w4.sql`, the probe reads Brazos Bend's payment from inside
    Lone Star Ridge's tenant context and this case fails naming the leak — the
    measured output is quoted in the lane report.
    """
    with live_tenant_context(brazos.id):
        account = an_account(marcus, brazos)
        pe1_bills(brazos, account)
        result = a_payment(marcus, account)

    assert_rls_scoped(
        rls, "payments", owner=brazos, intruder=lonestar, owner_ids={result.payment_id}
    )
    assert_rls_scoped(rls, "allocations", owner=brazos, intruder=lonestar, min_owner_rows=2)
    # With NO tenant context at all the `::uuid` cast of '' fails and the table
    # is unreadable — deny-by-default, the B2 §3 template's own property.
    assert_denied_without_context(rls, "payments", "allocations")


@requires_postgres
def test_us_pay_001_tc8__a_recorded_payment_cannot_be_changed_or_removed(brazos, marcus):
    """US-PAY-001 TC-6's second half / BR-PAY-002 — "a direct UPDATE … rejected".

    Not the service refusing: the DATABASE refusing. A management command, a
    data fix, a `.update()` on a queryset and a later migration all bypass a
    service layer, and BR-PAY-002 has to hold against every one of them.

    PROVED RED: with `trg_payment_immutable` dropped, `UPDATE payments SET
    amount = 999999` succeeds and the customer's payment silently becomes
    $999,999 — quoted in the lane report.
    """
    with tenant_ctx(brazos):
        account = an_account(marcus, brazos)
        pe1_bills(brazos, account)
        result = a_payment(marcus, account)

        with connection.cursor() as cursor:
            with pytest.raises(DatabaseError, match="append-only"), transaction.atomic():
                cursor.execute(
                    "UPDATE payments SET amount = %s WHERE id = %s",
                    [Decimal("999999.00"), result.payment_id],
                )
            with pytest.raises(DatabaseError, match="cannot be removed"), transaction.atomic():
                cursor.execute("DELETE FROM payments WHERE id = %s", [result.payment_id])
            # BR-PAY-031 — an allocation is append-only from birth; a reapply is
            # a reversing row plus a new row, never an edit.
            with pytest.raises(DatabaseError, match="append-only"), transaction.atomic():
                cursor.execute(
                    "UPDATE allocations SET amount = 1 WHERE payment_id = %s", [result.payment_id]
                )
            with pytest.raises(DatabaseError, match="append-only"), transaction.atomic():
                cursor.execute("DELETE FROM allocations WHERE payment_id = %s", [result.payment_id])

        payment = models.Payment.objects.get(pk=result.payment_id)
        assert payment.amount == PE1_CHECK, "the money is exactly as it was recorded"


@requires_postgres
def test_us_pay_001_tc9__the_freeze_covers_a_column_added_after_it_was_written(brazos, marcus):
    """The lesson two lanes learned on 2026-08-11, asserted rather than trusted.

    A trigger that freezes by NAMING columns leaves the next column somebody
    adds unprotected, and nothing goes red. This one compares whole rows minus a
    three-name allow list, so a column created a month from now is frozen the
    day it exists.

    The probe adds a real column, tries to move it on a still-PROCESSING payment
    — the ONE row state that has an open door at all — and requires a refusal
    naming the column. If this test ever goes green after somebody rewrites the
    trigger as an `IF NEW.x IS DISTINCT FROM OLD.x OR …` chain, it will be
    because the freeze has started failing open.
    """
    with tenant_ctx(brazos):
        account = an_account(marcus, brazos)
        payment = models.Payment.objects.create(
            tenant=brazos,
            account=account,
            amount=PE1_CHECK,
            currency=account.currency,
            status=models.PAYMENT_PROCESSING,
            posted_at=POSTED_AT,
        )
        with connection.cursor() as cursor:
            # The INSERT above leaves DEFERRED FK trigger events pending, and
            # Postgres refuses to ALTER a table that has them. Firing them now
            # is the same `SET CONSTRAINTS ALL IMMEDIATE` the ledger's own tests
            # use to reach commit inside pytest's never-committed transaction.
            cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
            cursor.execute("ALTER TABLE payments ADD COLUMN probe_future_column text")
            try:
                with (
                    pytest.raises(DatabaseError, match="probe_future_column"),
                    transaction.atomic(),
                ):
                    cursor.execute(
                        "UPDATE payments SET probe_future_column = 'moved' WHERE id = %s",
                        [payment.pk],
                    )
            finally:
                cursor.execute("ALTER TABLE payments DROP COLUMN probe_future_column")

        # The one door that IS open: the clearing transition (BR-PAY-021).
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE payments SET status = 'cleared', cleared_at = %s WHERE id = %s",
                [CLEARED_AT, payment.pk],
            )
        payment.refresh_from_db()
        assert payment.status == models.PAYMENT_CLEARED


def test_us_pay_001_tc10__money_is_never_recorded_without_reaching_the_books(brazos, marcus):
    """CLAUDE.md rule 5 — the posting is not optional, and not "best effort".

    A payment row is immutable the instant it commits, so a payment recorded
    with no journal entry can never be repaired — only explained. The whole
    transaction therefore rolls back when the ledger refuses.

    Driven here by removing the tenant's UNDEPOSITED FUNDS designation, which is
    the real shape of an unseeded or half-migrated chart. (It was the CASH
    designation until the PO's OQ-143 ruling of 2026-08-11 moved the receipt leg
    to 1010 — BR-PAY-039.)

    PROVED RED: with `ledger_seam.post_payment_cleared` made a no-op, the
    payment and both allocation rows commit with NOTHING in `journal_lines` —
    quoted in the lane report.
    """
    from apps.ledger import models as ledger_models

    with tenant_ctx(brazos):
        account = an_account(marcus, brazos)
        pe1_bills(brazos, account)
        ledger_models.LedgerAccount.objects.filter(
            tenant=brazos, designation="undeposited_funds"
        ).update(designation=None)

        with pytest.raises(PaymentRuleError, match="designation"):
            a_payment(marcus, account)

        assert models.Payment.objects.count() == 0, "nothing is recorded that cannot post"
        assert models.Allocation.objects.count() == 0
        assert ledger_models.JournalEntry.objects.count() == 0


def test_us_pay_001_tc11__a_processing_payment_allocates_and_posts_nothing(brazos, marcus):
    """BR-PAY-021 — "blank clearing date = still processing" (US-PAY-001 §5).

    The money has not arrived, so no bill leaves arrears and nothing reaches the
    books: US-LED-001's contract row is *"Payment CLEARED → DR cash / CR AR"*.
    The row exists, carries its posting date, and says on the result why it did
    nothing else — an absence a caller can read rather than infer.
    """
    from apps.ledger import models as ledger_models

    with tenant_ctx(brazos):
        account = an_account(marcus, brazos)
        pe1_bills(brazos, account)

        result = a_payment(marcus, account, cleared_at=None)

        # ⚠ SUPERSEDED 2026-10-21 (CR-186-BRC10). PO: "first they will pot the
        # payment … then later money is recieved in the bank account" and "a
        # payment is applied to open bills at posting". A blank clearing date
        # no longer means `processing`: the payment is POSTED, applied and
        # journalled at once. The case keeps its name (G10 maps TC ids).
        assert result.created is True
        assert result.status == models.PAYMENT_POSTED
        assert result.applied == PE1_CHECK
        assert result.posted_to_ledger is True
        assert result.journal_entry_id is not None
        assert models.Allocation.objects.count() == 2
        assert ledger_models.JournalEntry.objects.count() == 1


def test_us_pay_001_tc12__three_purposes_are_refused_by_name(brazos, marcus):
    """BR-PAY-012 — ⚠ **SUPERSEDED IN PART 2026-08-15 by US-PAY-002.**

    This case used to assert that `deposit`, `plan_down` and `prepay` were ALL
    refused, each for a linkage that did not exist. US-PAY-002 built every one
    of them (`apps/payments/purposes.py`), so two of the three refusals are gone
    and the third has a different reason. The case is REWRITTEN rather than
    deleted, for the reason hard-won law 1 gives: a reader comparing this file
    against the old behaviour must be able to find out what happened to it.

    Its NAME is kept for the same reason — G10 maps TC ids to tests, and a
    renamed case would read as a case that was dropped.

    WHAT STILL HOLDS, and is what this case now asserts:

      * a purpose whose LINKAGE cannot be made is still refused BY NAME with
        nothing written — US-PAY-002 TC-5 verbatim (*"rejected with a NAMED
        linkage error; no orphan purpose links"*). `plan_down` against an
        account with no live plan is the case that survives;
      * a FIFTH purpose does not exist. BR-PAY-012's four are a closed set and a
        typo must never be treated as `bill`;
      * neither refusal leaves a row, a PMT- number or an audit entry behind.
    """
    with tenant_ctx(brazos):
        account = an_account(marcus, brazos)
        pe1_bills(brazos, account)

        # The linkage that CAN still fail: a down payment with no plan behind it.
        with pytest.raises(PaymentRuleError, match="no live payment plan"):
            a_payment(marcus, account, purpose=models.PURPOSE_PLAN_DOWN)

        with pytest.raises(PaymentRuleError, match="not one of the payment purposes"):
            a_payment(marcus, account, purpose="donation")

        assert models.Payment.objects.count() == 0

        # And the other side of the supersession, so this file records what
        # replaced the two refusals it used to make rather than falling silent:
        # a deposit and a prepay both RECORD now, and neither meets a bill.
        deposit = a_payment(marcus, account, purpose=models.PURPOSE_DEPOSIT)
        assert deposit.created is True
        assert deposit.applied == Decimal("0")
        assert deposit.credit_carried == Decimal("0")  # HELD, never credit


def test_us_pay_001_tc13__a_payment_is_always_accepted(brazos, marcus):
    """BR-PAY-036, in the PO's own words: *"payment is always accepted - even it
    is disconnected and tagged to account"*.

    Two halves. The money is taken whatever the account's status — asserted by
    driving a CLOSED account — and acceptance NEVER changes that status:
    restoration stays an explicit, audited staff action.

    The absence is also asserted directly: `apps/payments/services.py` must not
    read `accounts.status` at all, because a status check added later would be
    invisible to a test that only ever drives one status.
    """
    import inspect

    from apps.customers import models as customer_models

    with tenant_ctx(brazos):
        account = an_account(marcus, brazos)
        pe1_bills(brazos, account)
        closed = (
            customer_models.AccountStatus.objects.filter(
                tenant=brazos, behavior_class="closed"
            ).first()
            or customer_models.AccountStatus.objects.filter(tenant=brazos).last()
        )
        account.status = closed
        account.save(update_fields=["status"])

        result = a_payment(marcus, account)

        assert result.created is True
        assert result.applied == PE1_CHECK
        account.refresh_from_db()
        assert account.status_id == closed.pk, "acceptance never moves the account's status"

    source = inspect.getsource(services)
    assert "account.status" not in source
    assert "status__" not in source


def test_us_pay_001_tc14__the_two_tenancy_seams_are_live(brazos, marcus):
    """BR-TEN-029/030/034 + BR-TEN-042 — two guards that were wired to nothing.

    `apps/tenancy/seams.py` has named both of these functions since W0 and
    answered 0 / False with the honest note *"payments stores no payment rows
    yet"*. That construction died the moment this module got tables, and its own
    docstring says what the 0 was costing: BR-TEN-030 (a code freezes once used)
    and BR-TEN-034 (a used row cannot be deleted) *"cannot bite"*.

    Asserted through TENANCY's seam rather than by calling payments directly,
    because what broke was the wiring and not the function (hard-won law 2).

    **AMENDED 2026-08-11 — DEF-075.** This test used to assert
    `financial_records_exist() is False` with PE-1's TWO ISSUED BILLS already on
    the account, and that assertion passed. It was not a mistake in the test: it
    faithfully recorded what the product did, because `tenancy/seams` polls
    `billing` and `payments` and only payments had ever authored the probe. So a
    tenant holding issued bill BL-2606-000001 (108.88 USD) and no payment could
    still change its currency — measured live, 200 OK, in a browser.

    The False moved to before the bills, where it belongs, and the issued bills
    now flip the lock on their own. The old line is quoted above rather than
    silently rewritten: an assertion that pinned a defect is worth naming once.
    """
    from apps.tenancy import seams as tenancy_seams

    with tenant_ctx(brazos):
        account = an_account(marcus, brazos)

        # Nothing financial has happened yet — the currency is still free to move.
        assert tenancy_seams.financial_records_exist() is False
        assert tenancy_seams.payment_method_used_by_count("check") == 0

        # DEF-075: an ISSUED BILL alone arms the lock, with no payment anywhere.
        pe1_bills(brazos, account)
        assert tenancy_seams.financial_records_exist() is True

        a_payment(marcus, account, method_code="check")

        assert tenancy_seams.financial_records_exist() is True
        assert tenancy_seams.payment_method_used_by_count("check") == 1
        assert tenancy_seams.payment_method_used_by_count("cash") == 0


def test_us_pay_001_tc15__an_unknown_or_retired_method_is_refused(brazos, marcus):
    """US-PAY-001 TC-3 / BR-PAY-026 — the six seeds, and nothing hardcoded.

    The method is a tenant LOOKUP since OQ-031 closed B2's `payment_method_t`
    enum, so a tenant adding "Bill-pay portal" can use it immediately. A code
    that resolves to nothing is refused rather than stored as NULL: a payment on
    S33 with a blank method column is one nobody can tell the instrument of.
    """
    from apps.tenancy import models as tenancy_models

    with tenant_ctx(brazos):
        account = an_account(marcus, brazos)
        pe1_bills(brazos, account)

        for code in ("cash", "check", "card", "ach", "wire", "money_order"):
            assert tenancy_models.PaymentMethod.objects.filter(
                tenant=brazos, code=code, active=True
            ).exists(), f"BR-PAY-026 seeds {code}"

        with pytest.raises(PaymentRuleError, match="active methods"):
            a_payment(marcus, account, method_code="carrier_pigeon")

        tenancy_models.PaymentMethod.objects.filter(tenant=brazos, code="wire").update(active=False)
        with pytest.raises(PaymentRuleError, match="active methods"):
            a_payment(marcus, account, method_code="wire")


def test_us_pay_001_tc16__the_service_reads_no_clock(brazos):
    """BR-TEN-043 / gate G6 — event time is named by the caller, always.

    Every date this module writes is an argument: the posting date is the
    user's (BR-PAY-033, *"never silently the system timestamp"*), the clearing
    date is the bank's, and both travel unchanged into the journal entry. A
    `now()` anywhere in this path would let the moment a request happened to
    arrive decide whether a customer owes a late fee.
    """
    import inspect

    for module in (services, ledger_seam, billing_seam):
        source = inspect.getsource(module)
        assert "timezone.now()" not in source, module.__name__
        assert "datetime.now(" not in source, module.__name__
        assert "date.today(" not in source, module.__name__


def test_us_pay_001_tc17__a_payment_with_no_tenant_context_is_refused(brazos, marcus):
    """CLAUDE.md rule 1 — nothing touches a tenant table without `app.tenant_id`.

    Refused rather than defaulted. On Postgres RLS would block it; on the SQLite
    developer database it would land in whatever tenant happened to be next, and
    "whichever database you happen to be running" is not a security model.
    """
    with tenant_ctx(brazos):
        account = an_account(marcus, brazos)

    with pytest.raises(errors.AuthError):
        services.record_payment(
            marcus, account_id=account.pk, amount=PE1_CHECK, posted_at=POSTED_AT
        )


def test_us_pay_001_tc18__the_open_position_reports_what_it_could_not_answer(brazos, marcus):
    """Hard-won law 1 — an absence a caller can read, not a docstring's word.

    Billing publishes no per-class composition and no kind→class map exists
    (OQ-128), and the fourth class's membership is the tenant's and unpublished
    (BR-PAY-038). So the allocation runs by amount alone — B5 GT-7's own legal
    shape — and says so with a code rather than inventing a breakdown.
    """
    with tenant_ctx(brazos):
        account = an_account(marcus, brazos)
        pe1_bills(brazos, account)

        position = billing_seam.open_invoices_for_account(account.pk)
        assert all(invoice.composition == () for invoice in position.invoices)
        assert any(p["code"] == "invoice_composition_unavailable" for p in position.problems)

        result = a_payment(marcus, account)
        assert all(row["by_class"] == {} for row in result.allocations)
        # Every result also carries what the RECORD path does not do.
        codes = {p["code"] for p in result.problems}
        # ⚠ AMENDED 2026-08-18 (CR-009 C-13): this used to assert
        # `no_receipt_queued` — the standing report that BR-PAY-024's receipt
        # queue was unbuilt. The consumer is now WIRED behind the tenant's
        # "receipt on record-payment" election (BR-NOT-022, DEFAULT ON), so the
        # truthful assertion is stronger, not looser: the receipt OUTCOME must
        # be on every result, and on a fresh tenant (election ON) the outcome
        # is `receipt_queued`. The full election matrix is
        # tests/test_cr_009_c13_a15_toggles.py.
        assert "no_receipt_queued" not in codes
        assert "receipt_queued" in codes
        assert "account_balance_cache_not_updated" in codes


def test_us_pay_001_tc19__void_and_draft_bills_never_receive_a_payment(brazos, marcus):
    """A void bill is no longer owed and a draft has not been issued.

    Allocating against either would take money for a document the customer was
    never sent, or for one that was withdrawn — and both rows are immutable, so
    the allocation could only be reversed, never removed.
    """
    from apps.billing import models as billing_models

    with tenant_ctx(brazos):
        account = an_account(marcus, brazos)
        an_issued_bill(
            brazos,
            account,
            number="BL-2607-DRAFT",
            total=Decimal("60.00"),
            issued_on=date(2026, 7, 1),
            status=billing_models.INVOICE_DRAFT,
            issued_at=None,
        )
        an_issued_bill(
            brazos,
            account,
            number="BL-2607-VOID",
            total=Decimal("70.00"),
            issued_on=date(2026, 7, 2),
            status=billing_models.INVOICE_VOID,
        )
        live = an_issued_bill(
            brazos,
            account,
            number="BL-2608-LIVE",
            total=NEW_BILL_TOTAL,
            issued_on=date(2026, 8, 1),
        )

        position = billing_seam.open_invoices_for_account(account.pk)
        assert [invoice.invoice_id for invoice in position.invoices] == [live.pk]
