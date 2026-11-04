# ── Trace ──────────────────────────────────────────────
# Change:   CR-059 · CS-8 (task 31) — "Move money between two accounts of one
#           customer: build it ONCE; four things land on it" · CS-32 (task 39)
#           — "Move a payment to the account it belonged to".
# Story:    US-PAY-011 · US-PAY-010   Screens: S21 · S58 · S35
# Rules:    BR-PAY-864 (one balanced movement recorded on both) · BR-PAY-865
#           (a moved payment is a reversal plus a linked new payment, sharing
#           the original's dates) · BR-PAY-866 (the destination re-allocates
#           under its own rules) · BR-PAY-867 (a move is refused while the
#           batch is reconciled) · BR-CUS-054 (the CUSTOMER entity) ·
#           BR-PAY-1070 (a reversal is Admin-only) · CLAUDE.md rule 4 · rule 5
#           · rule 7 · `OQ-135` CLOSED 2026-08-12 (*"offset first"*)
# Tests:    this file
# ───────────────────────────────────────────────────────
"""CS-8 and CS-32 — money crossing two accounts, through ONE writer.

WHY BOTH ARE IN ONE FILE
========================
CR-059 §0d.1 calls CS-8 **the keystone: four specs wait on it and it has nothing
today**, and CS-32 says the same thing from its own side — *"It shares CS-8's
transfer mechanics; build the two together or the second will be a near-copy of
the first."* They are two different movements sharing one module, and the tests
are where the difference is pinned rather than described:

    a CREDIT TRANSFER   two NEW payment rows and ONE new balanced entry.
                        DR customer credit (source) / CR receivables + credit
                        (destination).
    a PAYMENT MOVE      a REVERSAL of the original plus an ordinary recording on
                        the right account — two entries the ledger already knows
                        how to write, and this module composes neither.

THE FIGURES
===========
    57.13 of credit moves and meets a sibling's 948.20 arrear  → 891.07 left
    a 292.87 cheque recorded on the wrong Patel moves          → dates INTACT
    receivables net to ZERO across the pair on a move
    a move inside a RECONCILED batch is refused (BR-PAY-867)
    a bounce inside a reconciled batch is still RECORDED       (OQ-134, 2026-08-12)

THE RED PROOF, RUN BEFORE ANY OF THIS WAS TRUSTED GREEN (hard-won law 7)
========================================================================
  * With `transfer._refuse_unless_one_customer` made a no-op,
    `test_cs8__two_strangers_accounts_are_refused` fails with
    `Failed: DID NOT RAISE PaymentRuleError` — and the transfer lands, which is
    money moved between two people OQ-135's option (b) warns about by name.
  * With `move_payment_to_account` passing `moved_on` as the destination's
    `posted_at` instead of the original's, `test_cs32__the_dates_are_the_
    originals` fails with `assert datetime(2026, 8, 2, ...) == datetime(2026, 7,
    5, ...)` — the customer 28 days late on a bill they paid a day early.
  * With `_refuse_if_batch_reconciled` removed,
    `test_cs32__a_reconciled_batch_refuses_the_move` fails with `DID NOT RAISE`
    and the payment leaves a batch the bank has already agreed a total for.
  * With `ledger_seam.post_account_transfer`'s footing check removed,
    `test_cs8__the_legs_must_foot` fails — an entry built from figures that do
    not add up, which the ledger would then refuse one layer down for a reason
    naming neither account.
"""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from apps.payments import models, selectors, services, transfer
from apps.payments.exceptions import PaymentRuleError

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_pay_001_record_payment import an_issued_bill, journal_legs
from tests.test_us_pay_020_023_bank_rec import an_account_of
from tests.test_w3_billing_models import an_account

pytestmark = pytest.mark.django_db

#: OQ-135's own repo fixture, and the decision log's worked figure.
THE_CREDIT = Decimal("57.13")
THE_ARREAR = Decimal("948.20")
AFTER_OFFSET = Decimal("891.07")

#: CS-32's case — the cheque recorded against the wrong Patel.
THE_CHEQUE = Decimal("292.87")

#: BR-PAY-011's acknowledgement. A move re-opens a bill the customer has
#: already been sent, so the signed rule asks for one and this lane did NOT
#: exempt the move from it — see `test_cs32__a_move_without_the_approval_is_refused`.
APPROVAL = "Dana Whitfield, 2026-08-02, wrong-account correction"

PAID_AT = datetime(2026, 7, 5, 10, 0, tzinfo=UTC)
NOTICED_ON = date(2026, 8, 2)
MOVED_AT = datetime(2026, 8, 2, 9, 0, tzinfo=UTC)


def two_accounts_of_one_customer(actor, tenant):
    """Two accounts linked to ONE customer through BR-CUS-054's N:M link."""
    from apps.customers import models as customer_models

    first = an_account(actor, tenant, account_no="A-2608-0141")
    second = an_account_of(actor, tenant, service="electric")
    customer = customer_models.Customer.objects.create(
        tenant=tenant, customer_no=f"C-{uuid.uuid4().hex[:6]}", display_name="Patel"
    )
    for account in (first, second):
        customer_models.CustomerAccount.objects.create(
            tenant=tenant, customer=customer, account=account
        )
    return first, second


def a_credit_of(actor, account, amount, when=PAID_AT):
    """A cleared payment meeting no bill — all of it becomes account credit."""
    return services.record_payment(
        actor,
        account_id=account.pk,
        amount=amount,
        posted_at=when,
        cleared_at=when,
        method_code="cash",
        idempotency_reference=uuid.uuid4(),
    )


# ══ CS-8 · THE CREDIT TRANSFER ═════════════════════════════════════════════


def test_cs8__the_offset_first_case_moves_the_money(brazos, dana):
    """**57.13 of credit meets a sibling's 948.20 arrear and leaves 891.07.**

    This is the movement `refunds.offset_before_refund` has computed and refused
    to make since 2026-08-12 — its own docstring says so: *"WHAT THIS FUNCTION
    DOES NOT DO: MOVE THE MONEY."* CS-8 is the writer, and this is the case the
    PO ruled on.
    """
    with tenant_ctx(brazos):
        source, destination = two_accounts_of_one_customer(dana, brazos)
        a_credit_of(dana, source, THE_CREDIT)
        an_issued_bill(
            brazos,
            destination,
            number="BL-2607-000001",
            total=THE_ARREAR,
            issued_on=date(2026, 7, 1),
        )
        assert selectors.account_credit_position(source.pk) == THE_CREDIT

        moved = transfer.transfer_credit_between_accounts(
            dana,
            source_account_id=source.pk,
            destination_account_id=destination.pk,
            amount=THE_CREDIT,
            moved_on=MOVED_AT,
            reason="offset against the arrear on the sibling account",
            idempotency_reference=uuid.uuid4(),
        )

        assert moved.kind == "credit_transfer"
        assert moved.amount == THE_CREDIT
        assert moved.applied == THE_CREDIT, "all of it met the sibling's bill"
        assert moved.credit_carried == Decimal("0")
        assert moved.source_credit_after == Decimal("0"), "the source holds nothing now"

        from apps.payments import billing_seam

        position, _problems = billing_seam.outstanding_positions(account_ids=[destination.pk])
        assert position[0].balance == AFTER_OFFSET, (
            "948.20 − 57.13 = 891.07 — the sibling is still in collections, which is what "
            "the offset-first ruling produces and what the screen must show"
        )


def test_cs8__the_books_are_one_balanced_movement(brazos, dana):
    """BR-PAY-864 — ONE entry, DR the SOURCE's credit / CR the DESTINATION's AR.

    Never a refund on one plus a payment on the other, which would post a cheque
    that was never written and leave bank reconciliation carrying an outgoing
    item nobody can find on a statement.
    """
    with tenant_ctx(brazos):
        source, destination = two_accounts_of_one_customer(dana, brazos)
        a_credit_of(dana, source, THE_CREDIT)
        an_issued_bill(
            brazos,
            destination,
            number="BL-2607-000002",
            total=THE_ARREAR,
            issued_on=date(2026, 7, 1),
        )
        before = set(journal_legs(brazos))

        moved = transfer.transfer_credit_between_accounts(
            dana,
            source_account_id=source.pk,
            destination_account_id=destination.pk,
            amount=THE_CREDIT,
            moved_on=MOVED_AT,
            reason="offset",
            idempotency_reference=uuid.uuid4(),
        )
        assert moved.journal_entry_id is not None, "rule 5 — it reached the books"

        from apps.ledger import models as ledger_models

        lines = list(
            ledger_models.JournalLine.objects.filter(
                tenant=brazos, journal_entry_id=moved.journal_entry_id
            )
        )
        assert len(lines) == 2, "one debit, one credit — nothing carried"
        debits = [line for line in lines if line.side == "debit"]
        credits = [line for line in lines if line.side == "credit"]
        assert len(debits) == 1 and len(credits) == 1
        assert debits[0].amount == credits[0].amount == THE_CREDIT
        assert str(debits[0].account_id) == str(source.pk), (
            "the DEBIT carries the SOURCE account's dimension — the utility's obligation to "
            "that account fell by 57.13"
        )
        assert str(credits[0].account_id) == str(
            destination.pk
        ), "and the CREDIT carries the DESTINATION's — its receivable fell by the same"
        assert before != set(journal_legs(brazos)), "the books moved"


def test_cs8__it_cannot_move_credit_that_is_not_there(brazos, dana):
    """An account 57.13 in credit cannot transfer 100.00.

    Allowing it would drive the source's credit position to **−42.87**, which
    this product means something specific by — *"Yes, it's a real debt"*, PO
    2026-08-11 — and would be a receivable invented by a typo.
    """
    with tenant_ctx(brazos):
        source, destination = two_accounts_of_one_customer(dana, brazos)
        a_credit_of(dana, source, THE_CREDIT)

        with pytest.raises(PaymentRuleError) as refusal:
            transfer.transfer_credit_between_accounts(
                dana,
                source_account_id=source.pk,
                destination_account_id=destination.pk,
                amount=Decimal("100.00"),
                moved_on=MOVED_AT,
                reason="too much",
                idempotency_reference=uuid.uuid4(),
            )
        assert "holds 57.13" in str(refusal.value).replace("57.130000", "57.13")
        assert selectors.account_credit_position(source.pk) == THE_CREDIT, "nothing moved"


def test_cs8__two_strangers_accounts_are_refused(brazos, dana):
    """CS-8's boundary — a transfer needs ONE customer behind both accounts.

    OQ-135's own option (b) records why: *"moving money between accounts unasked
    can be unlawful where the account holders differ"*. A shared surname or
    address counts for nothing (BR-CUS-054).

    **RED PROOF:** with `_refuse_unless_one_customer` made a no-op this fails
    with `DID NOT RAISE PaymentRuleError` and the money crosses.
    """
    with tenant_ctx(brazos):
        mine = an_account(dana, brazos, account_no="A-2608-0141")
        stranger = an_account_of(dana, brazos, service="electric")
        a_credit_of(dana, mine, THE_CREDIT)

        with pytest.raises(PaymentRuleError) as refusal:
            transfer.transfer_credit_between_accounts(
                dana,
                source_account_id=mine.pk,
                destination_account_id=stranger.pk,
                amount=THE_CREDIT,
                moved_on=MOVED_AT,
                reason="not one customer",
                idempotency_reference=uuid.uuid4(),
            )
        assert "not held by one customer" in str(refusal.value)
        assert selectors.account_credit_position(mine.pk) == THE_CREDIT


def test_cs8__a_transfer_needs_a_reason(brazos, dana):
    """Hard rule 7's row is the only record of WHY, so the reason is required."""
    with tenant_ctx(brazos):
        source, destination = two_accounts_of_one_customer(dana, brazos)
        a_credit_of(dana, source, THE_CREDIT)
        with pytest.raises(PaymentRuleError) as refusal:
            transfer.transfer_credit_between_accounts(
                dana,
                source_account_id=source.pk,
                destination_account_id=destination.pk,
                amount=THE_CREDIT,
                moved_on=MOVED_AT,
                reason="   ",
                idempotency_reference=uuid.uuid4(),
            )
        assert "needs a reason" in str(refusal.value)


def test_cs8__a_double_submit_moves_the_money_once(brazos, dana):
    """CLAUDE.md hard rule 6 — one token, one movement, whatever the clerk clicks."""
    with tenant_ctx(brazos):
        source, destination = two_accounts_of_one_customer(dana, brazos)
        a_credit_of(dana, source, THE_CREDIT)
        token = uuid.uuid4()

        first = transfer.transfer_credit_between_accounts(
            dana,
            source_account_id=source.pk,
            destination_account_id=destination.pk,
            amount=THE_CREDIT,
            moved_on=MOVED_AT,
            reason="offset",
            idempotency_reference=token,
        )
        second = transfer.transfer_credit_between_accounts(
            dana,
            source_account_id=source.pk,
            destination_account_id=destination.pk,
            amount=THE_CREDIT,
            moved_on=MOVED_AT,
            reason="offset",
            idempotency_reference=token,
        )
        assert first.created is True and second.created is False
        assert second.source_payment_id == first.source_payment_id
        assert (
            models.Payment.objects.filter(account_id=destination.pk).count() == 1
        ), "one movement, one destination row — the money is not doubled"


def test_cs8__the_transfer_out_row_is_not_cash(brazos, dana):
    """The source leg is an ADJUSTMENT, so it never reaches the drawer figure.

    Two rules turn on it and neither is this module's: `payments_totals`
    excludes non-cash rows from the day's takings — no cash left the drawer here
    — and `cut_deposit_batches` never sweeps one into a batch, so a transfer
    cannot make a deposit total un-tieable.
    """
    with tenant_ctx(brazos):
        source, destination = two_accounts_of_one_customer(dana, brazos)
        a_credit_of(dana, source, THE_CREDIT)
        moved = transfer.transfer_credit_between_accounts(
            dana,
            source_account_id=source.pk,
            destination_account_id=destination.pk,
            amount=THE_CREDIT,
            moved_on=MOVED_AT,
            reason="offset",
            idempotency_reference=uuid.uuid4(),
        )
        out_row = models.Payment.objects.get(pk=moved.source_payment_id)
        in_row = models.Payment.objects.get(pk=moved.destination_payment_id)
        assert out_row.type == models.PAYMENT_TYPE_ADJUSTMENT
        assert in_row.type == models.PAYMENT_TYPE_ADJUSTMENT
        assert out_row.amount == -THE_CREDIT, "the sign lives on the AMOUNT"
        assert in_row.amount == THE_CREDIT
        assert (
            str(in_row.moved_from_payment_id) == moved.source_payment_id
        ), "the pair is walkable from either end — CS-32's column doing CS-8's job"


# ══ CS-32 · THE PAYMENT MOVE ═══════════════════════════════════════════════


def a_misrecorded_cheque(actor, tenant, wrong, right):
    """292.87 taken at the counter and recorded against the wrong Patel."""
    an_issued_bill(
        tenant, wrong, number="BL-2607-000010", total=THE_CHEQUE, issued_on=date(2026, 7, 1)
    )
    an_issued_bill(
        tenant, right, number="BL-2607-000011", total=THE_CHEQUE, issued_on=date(2026, 7, 1)
    )
    return services.record_payment(
        actor,
        account_id=wrong.pk,
        amount=THE_CHEQUE,
        posted_at=PAID_AT,
        cleared_at=PAID_AT,
        method_code="check",
        confirmation="8842",
        idempotency_reference=uuid.uuid4(),
    )


def test_cs32__the_money_lands_on_the_right_account(brazos, dana):
    """BR-PAY-865 — a reversal on the source, a linked new payment on the right one."""
    with tenant_ctx(brazos):
        wrong, right = two_accounts_of_one_customer(dana, brazos)
        paid = a_misrecorded_cheque(dana, brazos, wrong, right)

        moved = transfer.move_payment_to_account(
            dana,
            payment_id=paid.payment_id,
            destination_account_id=right.pk,
            reason="recorded against the wrong Patel",
            moved_on=NOTICED_ON,
            approval=APPROVAL,
            idempotency_reference=uuid.uuid4(),
        )
        assert moved.kind == "payment_move"
        assert (
            moved.moved_payment_id == paid.payment_id
        ), "the number the customer holds is the ORIGINAL's, so that is what is named"
        assert moved.applied == THE_CHEQUE, "and it met the right account's bill"

        in_row = models.Payment.objects.get(pk=moved.destination_payment_id)
        assert str(in_row.moved_from_payment_id) == paid.payment_id, (
            "S21 renders *moved from PMT-…* off this link, and it names the ORIGINAL "
            "rather than the reversing row"
        )
        assert in_row.confirmation == "8842", "the same cheque number, so the bank line matches"


def test_cs32__the_dates_are_the_originals(brazos, dana):
    """BR-PAY-865 — *"the dates must not be rewritten to today."*

    A cheque posted **5 Jul** against a bill due **6 Jul** was ON TIME. The
    mis-keying is spotted on **2 Aug**. Re-dating the destination payment would
    make that customer 27 days late on a bill they paid a day early — with a
    late fee and a rung of the collection ladder behind it.

    **RED PROOF:** passing `moved_on` as the destination's `posted_at` fails
    here with `assert datetime(2026, 8, 2, ...) == datetime(2026, 7, 5, ...)`.
    """
    with tenant_ctx(brazos):
        wrong, right = two_accounts_of_one_customer(dana, brazos)
        paid = a_misrecorded_cheque(dana, brazos, wrong, right)
        original = models.Payment.objects.get(pk=paid.payment_id)

        moved = transfer.move_payment_to_account(
            dana,
            payment_id=paid.payment_id,
            destination_account_id=right.pk,
            reason="wrong Patel",
            moved_on=NOTICED_ON,
            approval=APPROVAL,
            idempotency_reference=uuid.uuid4(),
        )
        in_row = models.Payment.objects.get(pk=moved.destination_payment_id)
        assert in_row.posted_at == original.posted_at == PAID_AT
        # CR-186-BRC10: neither row is reconciled with the bank yet, so both
        # carry no clearing date — the moved row still shares the original's.
        assert in_row.cleared_at == original.cleared_at


def test_cs32__receivables_net_to_zero_across_the_pair(brazos, dana):
    """CS-32's own proof clause — *"the ledger tie-out: receivables net to zero
    across the pair."*

    The reversal puts 292.87 back on the wrong account's receivable and the new
    payment takes 292.87 off the right one's. Across the two entries the AR
    movement is nil, which is what makes a move a correction rather than a
    transaction.
    """
    from apps.ledger import models as ledger_models

    with tenant_ctx(brazos):
        wrong, right = two_accounts_of_one_customer(dana, brazos)
        paid = a_misrecorded_cheque(dana, brazos, wrong, right)
        before = _ar_movement(ledger_models, brazos)

        transfer.move_payment_to_account(
            dana,
            payment_id=paid.payment_id,
            destination_account_id=right.pk,
            reason="wrong Patel",
            moved_on=NOTICED_ON,
            approval=APPROVAL,
            idempotency_reference=uuid.uuid4(),
        )
        after = _ar_movement(ledger_models, brazos)
        assert after == before, (
            "the move touched receivables on both accounts by the same amount in opposite "
            "directions, so the tenant's net AR position is exactly where it was"
        )


def _ar_movement(ledger_models, tenant):
    """Σ(debits − credits) over every receivables line this tenant has."""
    total = Decimal("0")
    for line in ledger_models.JournalLine.objects.filter(tenant=tenant).select_related(
        "ledger_account"
    ):
        if getattr(line.ledger_account, "code", None) != "1200":
            continue
        total += line.amount if line.side == "debit" else -line.amount
    return total


def test_cs32__a_reconciled_batch_refuses_the_move(brazos, dana):
    """BR-PAY-867 — the bank has already agreed that total.

    ⚠ **AND IT IS THE OPPOSITE OF THE BOUNCE RULE, WHICH IS THE POINT.** The PO
    closed `OQ-134` on 2026-08-12 and a returned cheque inside a reconciled
    batch IS recorded, because the bank returned it. A move is OUR choice about
    money the bank has tied out, and it would leave the batch claiming eight
    cheques while holding seven.

    **RED PROOF:** with `_refuse_if_batch_reconciled` removed this fails with
    `DID NOT RAISE` and the payment leaves the batch.

    ⚠ **THE BATCH IS BANKED UNDER A TILL, AND IT WAS NOT UNTIL 2026-09-24
    (`DEF-PAY-6463`).** `payments/0033`'s `trg_deposit_batch_needs_session`
    (`P0.6`, `BR-PAY-025` as amended 2026-09-22 — *a batch is one till and one
    tender*) has refused a bare `DepositBatch.objects.create` since
    `5831a9cd5`, with *"deposit batch DEP-260805-CHK cannot be created without
    a counter session"*. SQLite has no trigger, so this case stayed green on
    the default tier and was red on the ONE database where a reconciled batch
    can be proved at all. `DEF-PAY-6399` found the identical fixture shape in
    `test_cr059_cs34_amend_reference.py` and fixed that file only; this is the
    same cheque banked the same way, one file over — which is why its
    prevention now reads *grep every test that creates the guarded row*.
    """
    from apps.payments import bankrec_models
    from apps.payments.counter_session_models import CounterSession
    from apps.tenancy import published_content_models as places

    with tenant_ctx(brazos):
        wrong, right = two_accounts_of_one_customer(dana, brazos)
        paid = a_misrecorded_cheque(dana, brazos, wrong, right)
        from apps.tenancy import models as tenancy_models

        cheque_method = tenancy_models.PaymentMethod.objects.filter(tenant=brazos).first()
        centre = places.ServiceCentre.objects.create(
            tenant=brazos,
            slug=f"main-{uuid.uuid4().hex[:6]}",
            name="Main office",
            address="101 Bend Road",
        )
        till = CounterSession.objects.create(
            tenant=brazos,
            owner=dana.user,
            service_centre=centre,
            opening_float=Decimal("200.0000"),
            opened_at=PAID_AT,
        )
        batch = bankrec_models.DepositBatch.objects.create(
            tenant=brazos,
            code="DEP-260805-CHK",
            session=till,
            method=cheque_method,
            deposited_on=date(2026, 8, 5),
            status=bankrec_models.BATCH_RECONCILED,
            recorded_total=Decimal("2840.00"),
        )
        models.Payment.objects.filter(pk=paid.payment_id).update(deposit_batch_id=batch.pk)

        with pytest.raises(PaymentRuleError) as refusal:
            transfer.move_payment_to_account(
                dana,
                payment_id=paid.payment_id,
                destination_account_id=right.pk,
                reason="wrong Patel",
                moved_on=NOTICED_ON,
                approval=APPROVAL,
                idempotency_reference=uuid.uuid4(),
            )
        assert "RECONCILED" in str(refusal.value)
        assert "Unreconcile the batch first" in str(refusal.value)


def test_cs32__a_payment_moves_once(brazos, dana):
    """One receipt, one destination. A second move is refused by name.

    `uq_payments_reverses` is the database half today; `_movable_payment`'s own
    `moved_to.exists()` check is what stands in for it when **CS-33 removes that
    index** — so the guarantee survives its own schema change.
    """
    with tenant_ctx(brazos):
        wrong, right = two_accounts_of_one_customer(dana, brazos)
        third = an_account_of(dana, brazos, service="electric")
        paid = a_misrecorded_cheque(dana, brazos, wrong, right)

        transfer.move_payment_to_account(
            dana,
            payment_id=paid.payment_id,
            destination_account_id=right.pk,
            reason="wrong Patel",
            moved_on=NOTICED_ON,
            approval=APPROVAL,
            idempotency_reference=uuid.uuid4(),
        )
        with pytest.raises(PaymentRuleError) as refusal:
            transfer.move_payment_to_account(
                dana,
                payment_id=paid.payment_id,
                destination_account_id=third.pk,
                reason="again",
                moved_on=NOTICED_ON,
                approval=APPROVAL,
                idempotency_reference=uuid.uuid4(),
            )
        assert "already been moved" in str(refusal.value)


def test_cs32__a_move_needs_no_customer_link(brazos, dana):
    """⚠ **CS-32 IS NOT CUSTOMER-SCOPED AND CS-8 IS — deliberately.**

    Its case is *"Two accounts named Patel, adjacent unit numbers, one cheque"*:
    the money was NEVER the source account's, and the two Patels may be two
    entirely different people. Requiring one customer would refuse the exact
    clerical error the change exists to repair.

    What guards a move instead is the required reason, the audit row on both
    legs, and the reconciled-batch refusal.
    """
    with tenant_ctx(brazos):
        wrong = an_account(dana, brazos, account_no="A-2608-0141")
        right = an_account_of(dana, brazos, service="electric")  # NO customer link
        paid = a_misrecorded_cheque(dana, brazos, wrong, right)

        moved = transfer.move_payment_to_account(
            dana,
            payment_id=paid.payment_id,
            destination_account_id=right.pk,
            reason="two different Patels, one cheque",
            moved_on=NOTICED_ON,
            approval=APPROVAL,
            idempotency_reference=uuid.uuid4(),
        )
        assert moved.kind == "payment_move"
        assert moved.applied == THE_CHEQUE


def test_cs32__a_move_needs_a_reason(brazos, dana):
    """CS-32 makes it required — the destination's history will show money it
    never took at the counter, and the audit row is where the explanation is."""
    with tenant_ctx(brazos):
        wrong, right = two_accounts_of_one_customer(dana, brazos)
        paid = a_misrecorded_cheque(dana, brazos, wrong, right)
        with pytest.raises(PaymentRuleError) as refusal:
            transfer.move_payment_to_account(
                dana,
                payment_id=paid.payment_id,
                destination_account_id=right.pk,
                reason="",
                moved_on=NOTICED_ON,
                approval=APPROVAL,
                idempotency_reference=uuid.uuid4(),
            )
        assert "needs a reason" in str(refusal.value)


def test_cs32__the_preview_shows_both_sides(brazos, dana):
    """BR-PAY-866 — what re-opens on the source and what the money will meet.

    *"The destination re-allocates under its own rules, which may land the money
    on entirely different bills — that is correct and must be shown before
    confirming."*
    """
    with tenant_ctx(brazos):
        wrong, right = two_accounts_of_one_customer(dana, brazos)
        paid = a_misrecorded_cheque(dana, brazos, wrong, right)

        view = transfer.preview_payment_move(
            payment_id=paid.payment_id, destination_account_id=right.pk
        )
        # The STORED decimal, at the column's own six places — CLAUDE.md rule 2
        # (money travels as its exact stored value, and the DISPLAY two-place
        # figure is a separate, additional member wherever a screen renders one).
        assert Decimal(view["amount"]) == THE_CHEQUE
        assert len(view["reopens_on_source"]) == 1
        assert Decimal(view["reopens_on_source"][0]["amount"]) == THE_CHEQUE
        assert len(view["meets_on_destination"]) == 1
        assert view["meets_on_destination"][0]["invoice_number"] == "BL-2607-000011"


def test_cs32__a_move_without_the_approval_is_refused(brazos, dana):
    """BR-PAY-011's approval clause fires on a move, and it was NOT exempted.

    The rule is CONFIRMED — *"paid/cross-period requires Admin/Executive
    approval"* — and a move genuinely re-opens a bill the customer has already
    been sent. **This lane found it by measurement rather than by reading:** the
    first draft passed no acknowledgement and every move of a payment that had
    met a bill was refused with *"needs an approval and none was given
    (applied_to_an_issued_bill)"*.

    **Exempting the move would have been this lane widening a signed rule**, so
    the requirement stands and the case exists to keep it standing.
    """
    with tenant_ctx(brazos):
        wrong, right = two_accounts_of_one_customer(dana, brazos)
        paid = a_misrecorded_cheque(dana, brazos, wrong, right)

        with pytest.raises(PaymentRuleError) as refusal:
            transfer.move_payment_to_account(
                dana,
                payment_id=paid.payment_id,
                destination_account_id=right.pk,
                reason="wrong Patel",
                moved_on=NOTICED_ON,
                idempotency_reference=uuid.uuid4(),
            )
        assert "needs an approval" in str(refusal.value)
        assert "applied_to_an_issued_bill" in str(refusal.value)


def test_cs32__the_preview_says_an_approval_will_be_asked_for(brazos, dana):
    """The modal learns it BEFORE the clerk types, not after they press Confirm.

    A refusal that arrives only on submit is a form that wastes somebody's work;
    the verdict is `reversal_rules`' own, so the warning and the outcome cannot
    disagree.
    """
    with tenant_ctx(brazos):
        wrong, right = two_accounts_of_one_customer(dana, brazos)
        paid = a_misrecorded_cheque(dana, brazos, wrong, right)

        view = transfer.preview_payment_move(
            payment_id=paid.payment_id, destination_account_id=right.pk
        )
        assert view["approval_required"] is True
        assert "applied_to_an_issued_bill" in view["approval_reasons"]
