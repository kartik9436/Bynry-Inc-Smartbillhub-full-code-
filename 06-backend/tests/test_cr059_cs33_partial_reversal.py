# ── Trace ──────────────────────────────────────────────
# Change:   CR-059 · CS-33 (tasks 66 and 67) — "Reverse part of a payment: a
#           schema and concurrency change on a money path".
# Story:    US-PAY-009 · US-PAY-010   Screens: S35
# Rules:    BR-PAY-884 (the sum of all reversals may never exceed the payment) ·
#           BR-PAY-885 (newest bill first, unless the clerk names it) ·
#           BR-PAY-028 + CLAUDE.md hard rule 6 (idempotency) · rule 4 · rule 5 ·
#           CLAUDE.md hard-won law 14 (proved on PostgreSQL, not on SQLite)
# Tests:    this file
# ───────────────────────────────────────────────────────
"""CS-33 — part of a payment comes back, and the index that guarded it is gone.

WHY THE CUSTOMER CARES
======================
*"When only part of a payment fails — a partial chargeback, or a cheque where
the words and the figures disagree and the bank honours the lower — the office
must reverse the whole thing and record a second payment for the part that
stood. The customer's history then shows a payment that bounced when it did
not, and if it was a cheque an NSF count and a cash-only flag can follow from
it."*

⚠ THE DANGEROUS PART IS NOT THE ARITHMETIC — CS-33 SAYS SO ITSELF
=================================================================
`uq_payments_reverses` was carrying **two** guarantees: a payment cannot be
over-reversed, and **a lost race and a replay are the same fact**. Dropping it
drops both, and only the first is what this change wants moved.

So the guarantee is re-established three ways, and this file has a case for each:

    over-reversal, one clerk    `_reversible_amount` refuses by name
    over-reversal, two clerks   `SELECT … FOR UPDATE` + the plpgsql trigger
    a retried submit            the REQUIRED idempotency key + its unique index

⚠ **AND ONLY THE FIRST OF THOSE IS OBSERVABLE ON THE DEFAULT SUITE**
(CLAUDE.md hard-won law 14). `config/settings/test.py` hardcodes in-memory
SQLite: `select_for_update` is a no-op there, plpgsql does not exist, and SQLite
serialises writers anyway — **so every concurrency case in this file would pass
with the lock deleted and the trigger never installed.** The cases that matter
carry `requires_postgres` and were run on PostgreSQL 16.13.

THE FIGURES
===========
    292.87 paid; 100.00 comes back, then 192.87  → the payment is finished
    a third reversal of 0.01 is REFUSED
    the same submit token twice writes ONE row
    two concurrent 200.00 reversals: one lands, one is refused
    a partial unwinds the NEWEST bill first (BR-PAY-885)

THE RED PROOF, RUN BEFORE ANY OF THIS WAS TRUSTED GREEN (hard-won law 7)
========================================================================
  * With `_reversible_amount`'s `amount > standing` branch removed,
    `test_cs33__a_third_reversal_is_refused` fails with `DID NOT RAISE` and
    292.88 comes back off a 292.87 payment.
  * With `_by_payment`'s `is_partial_reversal=False` filter removed,
    `test_cs33__the_second_partial_is_not_swallowed_as_a_replay` fails: the
    second request is answered with the FIRST reversal and `created=False` — a
    success message, and 192.87 that never came back off the account.
  * With `_lock_original` made a no-op and run on PostgreSQL,
    `test_cs33__two_concurrent_partials_cannot_both_land` fails — both
    transactions read 0.00 already reversed, both pass their own check, and
    400.00 comes back off a 292.87 payment. **On SQLite that same sabotage
    passes**, which is the whole reason the case is marked.
"""

import threading
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from django.db import connections, transaction

from apps.payments import models, reversal, services
from apps.payments.exceptions import PaymentRuleError

from tests.isolation_helpers import requires_postgres
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_pay_001_record_payment import an_issued_bill
from tests.test_w3_billing_models import an_account

pytestmark = pytest.mark.django_db

#: PE-7's own payment, and CS-33's worked case.
THE_PAYMENT = Decimal("292.87")
FIRST_PART = Decimal("100.00")
THE_REST = Decimal("192.87")

PAID_AT = datetime(2026, 7, 5, 10, 0, tzinfo=UTC)
RETURNED_AT = datetime(2026, 8, 2, 9, 0, tzinfo=UTC)
APPROVAL = "Dana Whitfield, 2026-08-02, partial chargeback"


def a_paid_bill(actor, tenant, account, *, amount=THE_PAYMENT):
    """One bill met in full by one cleared payment."""
    an_issued_bill(tenant, account, number="BL-0141", total=amount, issued_on=date(2026, 6, 1))
    return services.record_payment(
        actor,
        account_id=account.pk,
        amount=amount,
        posted_at=PAID_AT,
        cleared_at=PAID_AT,
        method_code="check",
        confirmation="8842",
        idempotency_reference=uuid.uuid4(),
    )


def a_partial(actor, payment_id, amount, **extra):
    """One partial reversal through the real service."""
    kwargs = dict(
        payment_id=payment_id,
        returned_on=RETURNED_AT,
        reason=models.REVERSAL_REASON_BANK_CHARGEBACK,
        approval=APPROVAL,
        amount=amount,
        idempotency_reference=uuid.uuid4(),
    )
    kwargs.update(extra)
    return reversal.reverse_payment(actor, **kwargs)


# ══ THE ARITHMETIC CS-33 ASKS FOR ══════════════════════════════════════════


def test_cs33__two_partials_sum_to_the_original(brazos, dana):
    """**100.00 then 192.87 finishes a 292.87 payment.** CS-33's own proof clause.

    And the bill re-opens by exactly what came off it each time — read from
    `allocated_so_far`, which sums NET over the negative mirror rows.
    """
    from apps.payments import billing_seam

    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        paid = a_paid_bill(dana, brazos, account)
        bill = models.Allocation.objects.get(payment_id=paid.payment_id).invoice_id

        first = a_partial(dana, paid.payment_id, FIRST_PART)
        assert first.amount == -FIRST_PART
        assert first.is_partial is True
        assert first.still_stands == THE_REST, "192.87 of it is still good money"
        assert billing_seam.allocated_so_far(bill) == THE_REST

        second = a_partial(dana, paid.payment_id, THE_REST)
        assert second.amount == -THE_REST
        assert second.still_stands == Decimal("0"), "the payment is finished"
        assert billing_seam.allocated_so_far(bill) == Decimal("0"), "the bill is fully open"

        assert reversal.reversed_so_far(brazos.id, paid.payment_id) == THE_PAYMENT


def test_cs33__a_third_reversal_is_refused(brazos, dana):
    """*"a third refused"* — CS-33's own proof clause, to the cent.

    **RED PROOF:** with the `amount > standing` branch removed this fails with
    `DID NOT RAISE` and 292.88 comes back off a 292.87 payment.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        paid = a_paid_bill(dana, brazos, account)
        a_partial(dana, paid.payment_id, FIRST_PART)
        a_partial(dana, paid.payment_id, THE_REST)

        with pytest.raises(PaymentRuleError) as refusal:
            a_partial(dana, paid.payment_id, Decimal("0.01"))
        assert "nothing of it still stands" in str(refusal.value)
        assert reversal.reversed_so_far(brazos.id, paid.payment_id) == THE_PAYMENT


def test_cs33__one_partial_then_a_bounce_takes_only_the_rest(brazos, dana):
    """`amount=None` means the whole of what STILL STANDS, not the whole payment.

    So a bounce after a 100.00 chargeback takes back 192.87 and not 292.87 —
    which is why no existing caller had to change and why none of them can
    accidentally double a debt.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        paid = a_paid_bill(dana, brazos, account)
        a_partial(dana, paid.payment_id, FIRST_PART)

        rest = reversal.reverse_payment(
            dana,
            payment_id=paid.payment_id,
            returned_on=RETURNED_AT,
            reason=models.REVERSAL_REASON_NSF,
            idempotency_reference=uuid.uuid4(),
        )
        assert rest.amount == -THE_REST
        assert rest.still_stands == Decimal("0")


def test_cs33__a_full_reversal_is_unchanged(brazos, dana):
    """❄️ PE-7's **−292.87** does not move, and neither does its posting shape.

    A first full bounce still goes through the ledger's own MIRROR — the entry
    is `reversal_of` the receipt, which is what makes S56 render both halves —
    and `is_partial` is false. CS-33 widens what is possible; it changes nothing
    that already worked.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        paid = a_paid_bill(dana, brazos, account)
        bounced = reversal.reverse_payment(
            dana,
            payment_id=paid.payment_id,
            returned_on=RETURNED_AT,
            idempotency_reference=uuid.uuid4(),
        )
        assert bounced.amount == -THE_PAYMENT
        assert bounced.is_partial is False
        assert bounced.still_stands == Decimal("0")
        row = models.Payment.objects.get(pk=bounced.reversal_id)
        assert row.is_partial_reversal is False


def test_cs33__the_newest_bill_re_opens_first(brazos, dana):
    """BR-PAY-885 — *"unwinds allocations newest bill first."*

    The kind answer: the OLDEST debt is the one nearest disconnection, so
    re-opening the newest keeps a customer off the collection ladder over money
    the bank only partly took back.
    """
    from apps.payments import billing_seam

    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        older = an_issued_bill(
            brazos, account, number="BL-0141", total=Decimal("100.00"), issued_on=date(2026, 6, 1)
        )
        newer = an_issued_bill(
            brazos, account, number="BL-0155", total=Decimal("100.00"), issued_on=date(2026, 7, 1)
        )
        paid = services.record_payment(
            dana,
            account_id=account.pk,
            amount=Decimal("200.00"),
            posted_at=PAID_AT,
            cleared_at=PAID_AT,
            method_code="check",
            confirmation="8843",
            idempotency_reference=uuid.uuid4(),
        )
        assert billing_seam.allocated_so_far(older.pk) == Decimal("100.00")
        assert billing_seam.allocated_so_far(newer.pk) == Decimal("100.00")

        a_partial(dana, paid.payment_id, Decimal("100.00"))
        assert billing_seam.allocated_so_far(older.pk) == Decimal(
            "100.00"
        ), "the June bill stays settled — it is the one nearest disconnection"
        assert billing_seam.allocated_so_far(newer.pk) == Decimal(
            "0"
        ), "and the JULY bill is the one that re-opens"


def test_cs33__the_clerk_may_name_the_bill(brazos, dana):
    """BR-PAY-885's override — *"unless the clerk names which bill to re-open."*"""
    from apps.payments import billing_seam

    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        older = an_issued_bill(
            brazos, account, number="BL-0141", total=Decimal("100.00"), issued_on=date(2026, 6, 1)
        )
        newer = an_issued_bill(
            brazos, account, number="BL-0155", total=Decimal("100.00"), issued_on=date(2026, 7, 1)
        )
        paid = services.record_payment(
            dana,
            account_id=account.pk,
            amount=Decimal("200.00"),
            posted_at=PAID_AT,
            cleared_at=PAID_AT,
            method_code="check",
            confirmation="8844",
            idempotency_reference=uuid.uuid4(),
        )
        a_partial(dana, paid.payment_id, Decimal("100.00"), targets=(str(older.pk),))
        assert billing_seam.allocated_so_far(older.pk) == Decimal("0"), "the named bill"
        assert billing_seam.allocated_so_far(newer.pk) == Decimal("100.00")


def test_cs33__a_bill_the_payment_never_met_is_refused(brazos, dana):
    """A silently ignored target is a clerk believing they re-opened something."""
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        paid = a_paid_bill(dana, brazos, account)
        stranger = an_issued_bill(
            brazos, account, number="BL-0199", total=Decimal("50.00"), issued_on=date(2026, 7, 20)
        )
        with pytest.raises(PaymentRuleError) as refusal:
            a_partial(dana, paid.payment_id, FIRST_PART, targets=(str(stranger.pk),))
        assert "never met bill" in str(refusal.value)


def test_cs33__the_books_carry_only_what_came_back(brazos, dana):
    """CLAUDE.md rule 5 — and the figure is the point.

    A 100.00 partial must not unwind the whole 292.87 entry. The ledger's own
    mirror would have done exactly that, which is why a partial composes its
    own balanced pair — and why it is checked here in money rather than in
    shape.
    """
    from apps.ledger import models as ledger_models

    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        paid = a_paid_bill(dana, brazos, account)
        result = a_partial(dana, paid.payment_id, FIRST_PART)

        lines = list(
            ledger_models.JournalLine.objects.filter(
                tenant=brazos, journal_entry_id=result.journal_entry_id
            )
        )
        debits = sum(line.amount for line in lines if line.side == "debit")
        credits = sum(line.amount for line in lines if line.side == "credit")
        assert debits == credits == FIRST_PART, (
            "100.00 came back, so 100.00 moves in the books — not the 292.87 the "
            "whole-entry mirror would have unwound"
        )


def test_cs33__the_class_breakdown_is_proportioned(brazos, dana):
    """A part-sized unwind takes its tax back in the same proportion.

    Copying the whole breakdown on to a part-sized mirror would take back more
    tax than money, and the *collected* remittance basis is read from these
    rows — so a utility would remit on a figure that never existed.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        paid = a_paid_bill(dana, brazos, account)
        original_rows = list(
            models.AllocationClass.objects.filter(allocation__payment_id=paid.payment_id)
        )
        if not original_rows:
            pytest.skip("this fixture's bill carries no class breakdown to proportion")

        a_partial(dana, paid.payment_id, FIRST_PART)
        mirrors = list(
            models.AllocationClass.objects.filter(
                allocation__payment__reverses_payment_id=paid.payment_id
            )
        )
        assert (
            sum(-row.amount for row in mirrors) == FIRST_PART
        ), "the classes taken back sum to the money taken back, exactly"


# ══ HARD RULE 6 · THE GUARANTEE THE INDEX USED TO CARRY ════════════════════


def test_cs33__the_same_submit_token_writes_one_row(brazos, dana):
    """A retried request writes ONE reversal and answers with the first.

    This is the guarantee `uq_payments_reverses` used to give for free and now
    rests on the REQUIRED idempotency key — which `reversal_api` has demanded
    since 2026-09-01, naming this change in advance as the reason.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        paid = a_paid_bill(dana, brazos, account)
        token = uuid.uuid4()

        first = a_partial(dana, paid.payment_id, FIRST_PART, idempotency_reference=token)
        second = a_partial(dana, paid.payment_id, FIRST_PART, idempotency_reference=token)

        assert first.created is True and second.created is False
        assert second.reversal_id == first.reversal_id
        assert (
            reversal.reversed_so_far(brazos.id, paid.payment_id) == FIRST_PART
        ), "one token, one reversal — the debt is not doubled"


def test_cs33__the_second_partial_is_not_swallowed_as_a_replay(brazos, dana):
    """⚠ **THE SILENT DATA-LOSS BUG THIS CHANGE HAD TO AVOID.**

    Guard 2 used to return ANY reversal of the payment and the caller treated it
    as a replay — exact while a payment could be reversed once. With partials it
    would answer the SECOND request with the FIRST reversal and `created=False`:
    a success message, and 192.87 that never came back off the account.

    **RED PROOF:** with the `is_partial_reversal=False` filter removed from
    `_by_payment`, this fails on `assert second.created is True`.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        paid = a_paid_bill(dana, brazos, account)

        first = a_partial(dana, paid.payment_id, FIRST_PART)
        second = a_partial(dana, paid.payment_id, THE_REST)

        assert second.created is True, "a lawful SECOND correction, not a replay"
        assert second.reversal_id != first.reversal_id
        assert reversal.reversed_so_far(brazos.id, paid.payment_id) == THE_PAYMENT


def test_cs33__a_full_reversal_still_cannot_happen_twice(brazos, dana):
    """The narrowed index still does its job for the case it still covers."""
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        paid = a_paid_bill(dana, brazos, account)
        first = reversal.reverse_payment(
            dana,
            payment_id=paid.payment_id,
            returned_on=RETURNED_AT,
            idempotency_reference=uuid.uuid4(),
        )
        second = reversal.reverse_payment(
            dana,
            payment_id=paid.payment_id,
            returned_on=RETURNED_AT,
            idempotency_reference=uuid.uuid4(),
        )
        assert second.created is False
        assert second.reversal_id == first.reversal_id


# ══ THE CONCURRENCY PROOF — POSTGRESQL ONLY (CLAUDE.md hard-won law 14) ════


@requires_postgres
# ⚠ `serialized_rollback=True` IS NOT NOISE AND MUST NOT BE TIDIED AWAY
# (DEF-3522). A `transaction=True` test tears down by FLUSHING, and the flush
# empties the PLATFORM reference data the migrations seed — `subscription_plans`
# among them. Without this flag the FIRST transactional case in this file passes
# and then deletes the catalogue, and the SECOND one dies at SETUP inside an
# unrelated helper's `growth_plan` fixture on
# `SubscriptionPlan.objects.get(code="growth")`. That failure names neither
# test, so it reads as broken plumbing rather than as a proof that never ran.
# `tests/conftest.py` documents this trap and names this flag as the answer;
# it is the CALLER's to set, which is why it is here and not there.
@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_cs33__two_concurrent_partials_cannot_both_land(brazos, dana):
    """⚠ **THE CASE CS-33 EXISTS TO BE SAFE ABOUT, ON THE ONLY DATABASE THAT
    CAN SHOW IT.**

    Two clerks each reverse **200.00** of a **292.87** payment at the same
    moment. Both read 0.00 already reversed; both find 200.00 ≤ 292.87. Without
    a lock both commit and **400.00 has come back off a 292.87 payment.**

    `SELECT … FOR UPDATE` on the ORIGINAL serialises them, so the second reads
    the first's row and is refused — and `payments/0019`'s trigger re-sums in
    the database as the independent second guard.

    ⚠ **SQLITE CANNOT SHOW THIS.** `select_for_update` is a no-op there,
    plpgsql does not exist, and SQLite serialises writers anyway — so this same
    test passes with the lock deleted and the trigger never installed. That is
    CLAUDE.md hard-won law 14 exactly, which is why this case is marked and why
    it was run on PostgreSQL 16.13.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        paid = a_paid_bill(dana, brazos, account)
        payment_id = paid.payment_id

    outcomes: list[str] = []
    barrier = threading.Barrier(2)

    def attempt():
        try:
            barrier.wait(timeout=10)
            with tenant_ctx(brazos):
                a_partial(dana, payment_id, Decimal("200.00"))
            outcomes.append("landed")
        except PaymentRuleError:
            outcomes.append("refused")
        except Exception as unexpected:  # the trigger's own refusal, or a lock error
            outcomes.append(f"refused:{type(unexpected).__name__}")
        finally:
            connections.close_all()

    threads = [threading.Thread(target=attempt) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert (
        outcomes.count("landed") == 1
    ), f"exactly one 200.00 reversal may land against a 292.87 payment; got {outcomes}"
    with tenant_ctx(brazos):
        assert reversal.reversed_so_far(brazos.id, payment_id) == Decimal(
            "200.00"
        ), "and the total reversed is 200.00 — not 400.00 off a 292.87 payment"


@requires_postgres
# ⚠ `serialized_rollback=True` IS NOT NOISE AND MUST NOT BE TIDIED AWAY
# (DEF-3522). A `transaction=True` test tears down by FLUSHING, and the flush
# empties the PLATFORM reference data the migrations seed — `subscription_plans`
# among them. Without this flag the FIRST transactional case in this file passes
# and then deletes the catalogue, and the SECOND one dies at SETUP inside an
# unrelated helper's `growth_plan` fixture on
# `SubscriptionPlan.objects.get(code="growth")`. That failure names neither
# test, so it reads as broken plumbing rather than as a proof that never ran.
# `tests/conftest.py` documents this trap and names this flag as the answer;
# it is the CALLER's to set, which is why it is here and not there.
@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_cs33__two_identical_requests_write_one_row(brazos, dana):
    """The brief's own bar: *"concurrent identical requests proved to write ONE
    row on PostgreSQL, since the index that used to guarantee it is gone."*

    Same payment, same amount, **same submit token**, two threads. One row.
    `uq_payments_webhook_key` is what makes the loser's INSERT fail, and
    `reverse_payment`'s existing `IntegrityError` handler turns that into the
    winner's answer rather than a red 409 a clerk would act on.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        paid = a_paid_bill(dana, brazos, account)
        payment_id = paid.payment_id

    token = str(uuid.uuid4())
    outcomes: list[str] = []
    barrier = threading.Barrier(2)

    def attempt():
        try:
            barrier.wait(timeout=10)
            with tenant_ctx(brazos):
                result = a_partial(dana, payment_id, FIRST_PART, idempotency_reference=token)
            outcomes.append("created" if result.created else "replayed")
        except Exception as unexpected:
            outcomes.append(f"error:{type(unexpected).__name__}")
        finally:
            connections.close_all()

    threads = [threading.Thread(target=attempt) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    with tenant_ctx(brazos):
        rows = models.Payment.objects.filter(reverses_payment_id=payment_id).count()
    assert (
        rows == 1
    ), f"two identical submits must leave ONE reversing row; got {rows} and {outcomes}"
    assert (
        "error:IntegrityError" not in outcomes
    ), "the loser must be answered with the winner's reversal, not with a raw database error"


@requires_postgres
def test_cs33__the_database_refuses_an_over_reversal_on_its_own(brazos, dana):
    """`trg_payment_reversal_sum` is a REAL guard, not a comment.

    Written by hand past the service, exactly as an unguarded second endpoint or
    a shell would — because two independent checks on one arithmetic fact is the
    discipline a money path keeps, and a check that only exists in Python is one
    check.
    """
    from django.db import DatabaseError

    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        paid = a_paid_bill(dana, brazos, account)
        original = models.Payment.objects.get(pk=paid.payment_id)

        with pytest.raises(DatabaseError) as refused:
            with transaction.atomic():
                models.Payment.objects.create(
                    tenant=brazos,
                    account=account,
                    payment_no="PMT-CS33-OVER",
                    amount=-Decimal("500.00"),
                    currency="USD",
                    status=models.PAYMENT_REVERSED,
                    posted_at=RETURNED_AT,
                    cleared_at=RETURNED_AT,
                    reverses_payment=original,
                    reversal_reason=models.REVERSAL_REASON_NSF,
                    is_partial_reversal=True,
                )
        assert "BR-PAY-884" in str(refused.value)
