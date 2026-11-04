# ── Trace ──────────────────────────────────────────────
# Change:   CR-059 · CS-7 (task 60) — "Refund a credit built from several
#           payments". Done looks like S58: *"a credit built from two
#           overpayments can be refunded, listing the payments behind it."*
# Story:    US-PAY-011 (refunds)   Screens: S58 · S21
# Rules:    BR-PAY-014 (refunds only from a real credit balance; Admin
#           approval; immutable row) · BR-PAY-041 (a credit position is signed
#           and never floored) · CLAUDE.md hard rule 1 · rule 2 · rule 4
# Ruling:   `OQ-167` CLOSED 2026-08-12 (the mechanism) · `OQ-195` CLOSED
#           2026-09-01, option (a) (the schema)
# Tests:    this file
# ───────────────────────────────────────────────────────
"""CS-7 — a refund belongs to the ACCOUNT, so a credit from two payments can go back.

THE CASE, AND THE FIGURE THE PRODUCT OWNER RULED ON
===================================================
An account overpays **$40.00** in June and **$17.13** in July and rings up
asking for the **$57.13** back. **One cheque, one decision.** Before this lane
the table could not say so — `refunds.payment_id` was `NOT NULL` in a SIGNED
schema, so a refund named exactly ONE payment — and the product refused rather
than guessing: `credit.refund_from_credit_balance` raised
`NotImplementedError("OQ-195")` from 2026-08-15.

The PO ruled the MECHANISM on 2026-08-12 (`OQ-167`) — *"user can do a refund or
issue a credit - it will be manula decision, provide a mecahnism to complete the
tasks"* — and the SCHEMA half on 2026-09-01 (`OQ-195`, option (a)):
`payment_id` becomes nullable, `account_id` is added NOT NULL.

WHAT THIS FILE ASSERTS, AND WHERE EACH CLAIM LIVES
==================================================
    the $57.13 goes back as ONE refund          `test_cs7__two_overpayments_one_refund`
    and the payments behind it are listed       `test_cs7__the_sources_are_listed`
    a single-source refund is UNCHANGED         `test_cs7__pe9_single_source_still_works`
    a refund with no address is REFUSED         `test_cs7__neither_link_is_refused`
    a payment on another account is REFUSED     `test_cs7__the_two_links_must_agree`
    every historic row is backfilled            `test_cs7__the_backfill_on_postgres`

⚠ **THE BACKFILL CASE IS THE ONE THAT NEEDS POSTGRESQL** (CLAUDE.md hard-won
law 14). `payments/0018` disables `trg_refund_immutable` for one statement,
fills `account_id` from each refund's own payment, and re-enables it. **SQLite
has no such trigger**, so the whole mechanism the migration was written for is
invisible on the default suite — the migration would pass green on every machine
whether or not it handled the freeze at all.

THE RED PROOF, RUN BEFORE ANY OF THIS WAS TRUSTED GREEN (hard-won law 7)
========================================================================
  * With `refunds._address`'s *"neither was given"* branch removed,
    `test_cs7__neither_link_is_refused` fails on a `null value in column
    "account_id" of relation "refunds" violates not-null constraint` from the
    database — the refusal a clerk can read replaced by a 500 they cannot.
  * With `issue_refund` restored to `refund.payment.account_id`,
    `test_cs7__two_overpayments_one_refund` fails at the issue step with
    `AttributeError: 'NoneType' object has no attribute 'account_id'` — on the
    one step of the whole refund lifecycle that moves a cent.
  * With the migration's `ALTER TABLE refunds DISABLE TRIGGER` lines removed and
    the migration re-run on PostgreSQL, it fails with
    `django.db.utils.InternalError: BR-PAY-014 / hard rule 4: refund … is frozen
    except its status walk … Changed: account_id`.
"""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from apps.payments import credit, models, refunds, selectors, services
from apps.payments.exceptions import PaymentRuleError

from tests.isolation_helpers import requires_postgres
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_pay_020_023_bank_rec import an_account_of
from tests.test_w3_billing_models import an_account

pytestmark = pytest.mark.django_db

#: The PO's own worked figures (decision log 2026-08-12, `OQ-167`).
JUNE_OVERPAY = Decimal("40.00")
JULY_OVERPAY = Decimal("17.13")
THE_CREDIT = Decimal("57.13")

JUNE_AT = datetime(2026, 6, 8, 10, 0, tzinfo=UTC)
JULY_AT = datetime(2026, 7, 8, 10, 0, tzinfo=UTC)
REQUESTED_AT = datetime(2026, 8, 8, 10, 0, tzinfo=UTC)


def an_overpayment(actor, account, amount, when):
    """One cleared payment that meets no bill, so all of it becomes credit."""
    return services.record_payment(
        actor,
        account_id=account.pk,
        amount=amount,
        posted_at=when,
        cleared_at=when,
        method_code="cash",
        idempotency_reference=uuid.uuid4(),
    )


def a_credit_from_two_payments(actor, account):
    """June's 40.00 and July's 17.13 — the case CS-7 exists for."""
    june = an_overpayment(actor, account, JUNE_OVERPAY, JUNE_AT)
    july = an_overpayment(actor, account, JULY_OVERPAY, JULY_AT)
    return june, july


# ══ THE ACCEPTANCE LINE ════════════════════════════════════════════════════


def test_cs7__two_overpayments_one_refund(brazos, dana):
    """**$40.00 + $17.13 = $57.13, refunded as ONE cheque.** The PO's own case.

    Raised against the ACCOUNT with no payment named — which is the whole point:
    neither the June nor the July payment is *the* source, and before this the
    only expressible answers were two cheques for one decision, or a refusal.

    Carried all the way to ISSUE, because that is the one step that moves a cent
    and the step whose `refund.payment.account_id` read would have thrown on a
    payment that is not there.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        a_credit_from_two_payments(dana, account)
        assert selectors.account_credit_position(account.pk) == THE_CREDIT

        raised = refunds.request_refund(
            dana,
            account_id=account.pk,
            amount=THE_CREDIT,
            method=models.REFUND_METHOD_CHECK,
            reference="10241",
            requested_at=REQUESTED_AT,
            idempotency_key=str(uuid.uuid4()),
        )
        assert raised.created is True
        assert raised.payment_id is None, (
            "the credit came from TWO payments, so the refund names NONE of them — "
            "PO ruling 2026-09-01, OQ-195 option (a)"
        )
        assert raised.account_id == str(account.pk), "and the ACCOUNT is the address"
        assert raised.amount == THE_CREDIT

        row = models.Refund.objects.get(pk=raised.refund_id)
        assert row.payment_id is None
        assert str(row.account_id) == str(account.pk)

        refunds.approve_refund(dana, refund_id=raised.refund_id, approved_at=REQUESTED_AT)
        issued = refunds.issue_refund(dana, refund_id=raised.refund_id, issued_at=REQUESTED_AT)
        assert issued.status == models.REFUND_ISSUED
        assert issued.credit_position_after == Decimal(
            "0"
        ), "the whole 57.13 has left; the account holds nothing on account afterwards"


def test_cs7__the_sources_are_listed(brazos, dana):
    """*"listing the payments behind it"* — the second half of the acceptance line.

    Two rows, each carrying what it CONTRIBUTED rather than its gross amount,
    and a refundable figure of 57.13 that is the POSITION rather than the sum of
    the rows (they agree here only because nothing has been refunded yet — the
    payload says so on `problems`).
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        june, july = a_credit_from_two_payments(dana, account)

        view = selectors.account_credit_sources(account.pk)
        assert view["refundable"] == "57.130000"
        assert view["refundable_display"] == "57.13", "CLAUDE.md rule 2 — display 2"
        assert view["source_count"] == 2
        numbers = {row["payment_id"] for row in view["sources"]}
        assert numbers == {june.payment_id, july.payment_id}
        contributed = {row["payment_id"]: row["contributed"] for row in view["sources"]}
        assert contributed[june.payment_id] == "40.000000"
        assert contributed[july.payment_id] == "17.130000"
        assert any(
            problem["code"] == "sources_are_evidence_not_a_link" for problem in view["problems"]
        ), "the divergence after the first refund is stated, not left to be discovered"


def test_cs7__a_payment_that_met_a_bill_contributes_nothing(brazos, dana):
    """A payment every cent of which met a bill is not a source of credit.

    Worked: a **$350.00** cheque against a **$292.87** bill contributes
    **$57.13** — its remainder — and not $350.00. A screen listing the gross
    figure would tell a clerk they could refund $350.00 of a $57.13 credit.
    """
    from tests.test_us_pay_001_record_payment import an_issued_bill

    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        an_issued_bill(
            brazos,
            account,
            number="BL-2606-000001",
            total=Decimal("292.87"),
            issued_on=date(2026, 6, 1),
        )
        big = an_overpayment(dana, account, Decimal("350.00"), JUNE_AT)

        view = selectors.account_credit_sources(account.pk)
        assert view["source_count"] == 1
        assert view["sources"][0]["payment_id"] == big.payment_id
        assert view["sources"][0]["amount"] == "350.000000", "the payment was 350.00"
        assert (
            view["sources"][0]["contributed"] == "57.130000"
        ), "and 57.13 of it is what became credit — the rest met the bill"
        assert view["refundable"] == "57.130000"


# ══ WHAT MUST NOT HAVE CHANGED ═════════════════════════════════════════════


def test_cs7__pe9_single_source_still_works(brazos, dana):
    """PE-9's **$350.00 → $57.13** goes through exactly as it always did.

    The historic call — `payment_id` and no `account_id` — is untouched, and the
    account is read off the payment and stamped on the row. CS-7 widens the
    table; it does not move a figure that was already right.
    """
    from tests.test_us_pay_001_record_payment import an_issued_bill

    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        an_issued_bill(
            brazos,
            account,
            number="BL-2606-000002",
            total=Decimal("292.87"),
            issued_on=date(2026, 6, 1),
        )
        paid = an_overpayment(dana, account, Decimal("350.00"), JUNE_AT)

        raised = refunds.request_refund(
            dana,
            payment_id=paid.payment_id,
            amount=THE_CREDIT,
            method=models.REFUND_METHOD_CHECK,
            reference="10241",
            requested_at=REQUESTED_AT,
            idempotency_key=str(uuid.uuid4()),
        )
        assert raised.payment_id == paid.payment_id, "the source payment is still named"
        assert raised.account_id == str(account.pk), "and the account is now stamped too"
        row = models.Refund.objects.get(pk=raised.refund_id)
        assert str(row.account_id) == str(account.pk)


def test_cs7__neither_link_is_refused(brazos, dana):
    """A refund with no payment AND no account is refused by NAME.

    The NOT NULL constraint is the guarantee; this is the sentence a clerk can
    act on. Both exist for hard-won law 1's reason — a constraint alone gives a
    person a 500 they cannot read.

    **RED PROOF:** with `_address`'s branch removed this fails on
    `null value in column "account_id" of relation "refunds" violates not-null
    constraint` instead.
    """
    with tenant_ctx(brazos):
        with pytest.raises(PaymentRuleError) as refusal:
            refunds.request_refund(
                dana,
                amount=THE_CREDIT,
                method=models.REFUND_METHOD_CHECK,
                reference="10241",
                requested_at=REQUESTED_AT,
                idempotency_key=str(uuid.uuid4()),
            )
        assert "cheque with no addressee" in str(refusal.value)
        assert models.Refund.objects.count() == 0, "and nothing is written"


def test_cs7__the_two_links_must_agree(brazos, dana):
    """Naming a payment of ANOTHER account is refused, in the SERVICE.

    `refunds_api` already refuses it at the door; this is the same rule one
    layer down, so a job, a shell or a second endpoint that forgot the check is
    refused all the same (BR-SHL-025). Without it, a refund could be addressed
    to account A and funded by account B's overpayment — and the credit test,
    the offset and the ledger posting would all be B's while the row said A.
    """
    with tenant_ctx(brazos):
        mine = an_account(dana, brazos)
        theirs = an_account_of(dana, brazos, service="electric")
        paid = an_overpayment(dana, theirs, Decimal("100.00"), JUNE_AT)

        with pytest.raises(PaymentRuleError) as refusal:
            refunds.request_refund(
                dana,
                payment_id=paid.payment_id,
                account_id=mine.pk,
                amount=Decimal("50.00"),
                method=models.REFUND_METHOD_CHECK,
                reference="10242",
                requested_at=REQUESTED_AT,
                idempotency_key=str(uuid.uuid4()),
            )
        assert "disagree" in str(refusal.value)
        assert models.Refund.objects.count() == 0


def test_cs7__the_stub_is_gone_and_nothing_replaced_it_as_a_writer():
    """`credit.refund_from_credit_balance` no longer exists — and by design.

    It raised `NotImplementedError("OQ-195")` and the question is answered, so
    the refusal is gone. **Nothing replaced it as a second write path**: a
    refund against the credit balance is `refunds.request_refund(account_id=…)`,
    the one writer that already tests the credit, applies the offset-first rule
    and posts to the books. Two writers would eventually disagree about which
    one pays.
    """
    assert not hasattr(credit, "refund_from_credit_balance"), (
        "the stub was removed when OQ-195 was answered; a stub citing a closed "
        "question is a stale stub (G8)"
    )
    assert hasattr(credit, "contributing_payments"), "the READ replaced it, not a writer"


# ══ THE MIGRATION, ON THE DATABASE THAT HAS THE TRIGGER ════════════════════


@requires_postgres
def test_cs7__the_backfill_on_postgres(brazos, dana):
    """Every refund that already existed carries the account it was against.

    ⚠ **THIS CASE IS THE REASON law 14 EXISTS.** `payments/0018` disables
    `trg_refund_immutable` for one statement to fill the new column, and
    **SQLite has no such trigger** — the whole mechanism is invisible on the
    default suite, which would pass green whether the migration handled the
    freeze or not.

    What is asserted here is the POST-MIGRATION invariant rather than a re-run
    of the migration: by the time this test runs the migration has been applied
    to the test database, so **no refund may exist with a NULL account**, and a
    refund raised the historic way must carry the account of its payment. If the
    backfill had not handled the trigger, the migration would have failed and
    this file would not collect at all.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        paid = an_overpayment(dana, account, Decimal("100.00"), JUNE_AT)
        raised = refunds.request_refund(
            dana,
            payment_id=paid.payment_id,
            amount=Decimal("40.00"),
            method=models.REFUND_METHOD_CHECK,
            reference="10243",
            requested_at=REQUESTED_AT,
            idempotency_key=str(uuid.uuid4()),
        )
        row = models.Refund.objects.get(pk=raised.refund_id)
        assert row.account_id is not None
        assert str(row.account_id) == str(account.pk)
        assert models.Refund.objects.filter(account_id=None).count() == 0, (
            "payments/0018's SET NOT NULL is what guarantees this, and the backfill is "
            "what let it be applied at all"
        )


@requires_postgres
def test_cs7__the_account_link_is_still_frozen(brazos, dana):
    """The freeze is RESTORED — a refund cannot be re-pointed after the fact.

    `payments/0018` turns `trg_refund_immutable` off for one statement inside
    its own transaction and turns it back on. If it had left it off, every
    column of every refund would be editable forever, which is hard rule 4
    switched off by a migration nobody would think to look at.
    """
    from django.db import DatabaseError, transaction

    with tenant_ctx(brazos):
        first = an_account(dana, brazos)
        second = an_account_of(dana, brazos, service="electric")
        paid = an_overpayment(dana, first, Decimal("100.00"), JUNE_AT)
        raised = refunds.request_refund(
            dana,
            payment_id=paid.payment_id,
            amount=Decimal("40.00"),
            method=models.REFUND_METHOD_CHECK,
            reference="10244",
            requested_at=REQUESTED_AT,
            idempotency_key=str(uuid.uuid4()),
        )
        row = models.Refund.objects.get(pk=raised.refund_id)
        row.account_id = second.pk
        with pytest.raises(DatabaseError) as refused:
            with transaction.atomic():
                row.save(update_fields=["account", "updated_at"])
        assert "hard rule 4" in str(refused.value)
