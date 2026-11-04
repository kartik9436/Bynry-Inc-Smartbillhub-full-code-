# ── Trace ──────────────────────────────────────────────
# Change:   CR-059 · CS-35 (a manual credit or adjustment, told apart from
#           cash) · CS-38 (a goodwill concession raises visible account credit)
#           · task 8 (the expired refusal, restated)
# Story:    US-PAY-001 (the recording path) · US-PAY-007 (the carried credit) ·
#           US-PAY-013 (S34 Outstandings, which the ladder runs on) ·
#           US-BIL-016 (the correction that raises a concession)
#           Screens: S21 · S22 · S33 · S34 · S66
# Rules:    BR-PAY-012 (every payment carries a purpose; a deposit is not
#           credit) · BR-PAY-020 (a money giveaway needs an approver above the
#           tenant's threshold) · BR-PAY-025 (deposit batches are day × tender
#           over CLEARED, POSITIVE money) · BR-PAY-041 (a negative credit is a
#           real debt and is never floored) · BR-TEN-036 (seeded, tenant-
#           extensible reference lists) · BR-BIL-074 (a credit note's amount is
#           never positive) · CLAUDE.md hard rules 1 · 2 · 4 · 5 · 6 · 7
# Golden:   ❄️ GT-6 — a $25.00 goodwill credit against a $247.30 invoice leaves
#           the customer owing **$222.30**. Asserted here UNMOVED.
# Tests:    this file
# Impacts:  apps/payments/services.py (`record_payment` takes the type;
#           `record_concession_credit`) · apps/payments/ledger_seam.py
#           (`post_credit_adjustment`, `credit_adjustment_debit_account_id`) ·
#           apps/payments/reconciliation.py (the batching branch) ·
#           apps/payments/billing_seam.py (the chase, net of held credit) ·
#           apps/payments/settings_seam.py · apps/tenancy/settings_families.py ·
#           apps/tenancy/selectors.py · apps/billing/corrections.py ·
#           apps/billing/payments_seam.py
# ───────────────────────────────────────────────────────
"""The concession the customer was told about and the product then denied.

**CS-38 IS THE ONE ITEM IN CR-059 WHERE THE CUSTOMER HAS BEEN TOLD SOMETHING IN
WRITING THAT THE SYSTEM THEN CONTRADICTS.** A utility gives somebody 25.00 off a
247.30 bill. Billing writes the credit note, posts DR write-off / CR customer
credit balance — correctly, under the PO's ruling of 2026-08-12 — and queues an
email saying so. Then: the account screen shows outstanding 247.30 and credit
0.00, the next bill is calculated without the 25.00, and the collection ladder
chases the full amount. Neither figure reads `credit_notes` and nothing ever did.

**CS-35 IS THE MACHINERY CS-38 NEEDED.** The `payments.type` column has carried
`payment | credit | adjustment` since the first migration and the frontend has
published all three since it shipped; nothing had ever written anything but
`payment`, and `record_payment` did not even take the argument. So the only way
to put a credit on an account was to record a fake payment — money the utility
never received, sitting in the day's takings.

════════════════════════════════════════════════════════════════════════════
THE THREE FIGURES CR-059 TASK 26 NAMES, AND WHERE EACH IS ASSERTED
════════════════════════════════════════════════════════════════════════════
    25.00 on a 247.30 bill leaves 222.30    `test_cs38__gt6_end_to_end`
    the ledger carries it exactly ONCE      `test_cs38__the_ledger_carries_it_once`
    the ladder does not chase the 25.00     `test_cs38__the_ladder_does_not_chase_it`

**❄️ GT-6's 222.30 DOES NOT MOVE AND IS NOT RECOMPUTED HERE.** It is written
down as a constant and compared against. What changed is that the product now
reaches it; the figure was signed on 2026-08-08 and nothing in this lane touches
it.

════════════════════════════════════════════════════════════════════════════
WHY THE CREDIT CARRIES RATHER THAN MEETING THE BILL IT CAME FROM — `OQ-215`
════════════════════════════════════════════════════════════════════════════
That row is OPEN and asks exactly this: is a class-C concession a credit note
that moves THIS bill's balance to 222.30, or an account-level credit consumed by
the NEXT bill while this bill still reads 247.30? It records that GT-6's 222.30
is reached either way, and that the choice *"needs one sentence from the PO and
is not a thing an implementer may pick"*.

`apps/billing/corrections.py` implements the second reading — `build_impact`
forces the class-C bill delta to ZERO — so the credit row is recorded with the
carry-credit allocation order and touches no invoice. **Recording it oldest-
first would have settled 25.00 of that very bill and decided OQ-215 on a money
path with no ruling**, which is why `test_cs38__the_bill_is_untouched` asserts
there is no allocation against it. That case exists to fail if a later lane
"simplifies" the order back to the default.

════════════════════════════════════════════════════════════════════════════
THE RED PROOF, RUN BEFORE ANY OF THIS WAS TRUSTED GREEN (hard-won law 7)
════════════════════════════════════════════════════════════════════════════
Each guard was first driven RED by restoring the pre-change behaviour in
process, never by trusting a paragraph. The verbatim failures are quoted in the
lane report and in `12-governance/09-human-review-ledger.md`.
"""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from apps.payments import billing_seam, ladder, models, reconciliation, services
from apps.payments.exceptions import PaymentRuleError

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_pay_001_record_payment import an_issued_bill, journal_legs, leg
from tests.test_w3_billing_models import an_account

pytestmark = pytest.mark.django_db

#: ❄️ GT-6, finance-signed 2026-08-08. Quoted, never recomputed.
GT6_BILL_TOTAL = Decimal("247.30")
GT6_CONCESSION = Decimal("25.00")
GT6_OWED = Decimal("222.30")

ON_DATE = date(2026, 8, 20)
POSTED_AT = datetime(2026, 8, 20, 10, 0, tzinfo=UTC)
AS_OF = date(2026, 9, 30)

#: The seeded reason (`lookup_defaults.json` → `reason_codes`). Class C's own
#: correction reason is the lower-case `goodwill`; the lookup row is `GOODWILL`,
#: and the read is case-insensitive on purpose — the two vocabularies were
#: seeded by different lanes and neither is going to be renamed on a money path.
GOODWILL = "goodwill"


def a_gt6_bill(tenant, account):
    """The frozen GT-6 bill: 247.30, issued, open, and long past due."""
    return an_issued_bill(
        tenant,
        account,
        number="BL-2608-000001",
        total=GT6_BILL_TOTAL,
        issued_on=date(2026, 8, 1),
        due_date=date(2026, 8, 15),
    )


def a_concession(actor, account, *, amount=GT6_CONCESSION, reference=None):
    """The concession, through the REAL service payments publishes to billing."""
    return services.record_concession_credit(
        actor,
        account_id=account.pk,
        amount=amount,
        reason_code=GOODWILL,
        on_date=ON_DATE,
        memo="goodwill",
        source_reference=reference or uuid.uuid4(),
    )


# ══ CS-38 · THE THREE FIGURES TASK 26 NAMES ════════════════════════════════


def test_cs38__gt6_end_to_end(brazos, dana):
    """❄️ **25.00 on a 247.30 bill leaves 222.30**, and it is on the screen.

    The whole point of CS-38 in one case. Before this lane the two figures a
    person reads were outstanding **247.30** and credit **0.00**; a letter had
    already told the customer they had 25.00. After it they are outstanding
    **247.30** and credit **25.00**, and what the utility actually chases —
    `outstanding_positions.balance`, the figure S34 renders and the collection
    ladder runs on — is **222.30**.

    The bill itself is untouched at 247.30 forever (hard rule 4), which is
    OQ-215's second reading and the one this engine implements.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        a_gt6_bill(brazos, account)

        before, _ = billing_seam.outstanding_positions(account_ids=[account.pk])
        assert before[0].balance == GT6_BILL_TOTAL, "the whole bill is chased before"

        a_concession(dana, account)

        from apps.payments import selectors

        assert selectors.account_credit_position(account.pk) == GT6_CONCESSION, (
            "CS-38's new rule, verbatim: a goodwill concession must leave VISIBLE "
            "account credit of the same amount"
        )
        after, _ = billing_seam.outstanding_positions(account_ids=[account.pk])
        assert after[0].gross_balance == GT6_BILL_TOTAL, "the bill still says 247.30"
        assert after[0].credit_applied == GT6_CONCESSION
        assert after[0].balance == GT6_OWED, (
            "❄️ GT-6: a $25.00 goodwill credit against a $247.30 invoice leaves the "
            "customer owing $222.30. The figure was signed on 2026-08-08 and has not "
            "moved; what changed is that the product now reaches it."
        )


def test_cs38__the_ledger_carries_it_once(brazos, dana):
    """CS-38's second named proof, and the one that can invent money.

    CS-38: *"a double post here is a real 25.00 of invented money."* Billing
    posts the concession (DR write-off / CR customer credit) and payments'
    credit row is marked NON-POSTING, so this counts BOTH sides: exactly one
    journal entry for the concession, and NO entry sourced from the payment row.
    """
    from apps.ledger import models as ledger_models

    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        a_gt6_bill(brazos, account)
        recorded = a_concession(dana, account)

        assert recorded.posted_to_ledger is False
        assert (
            recorded.journal_entry_id is None
        ), "the payments row posts nothing — the books already carry this 25.00"
        assert any(
            problem["code"] == "posted_by_another_record" for problem in recorded.problems
        ), "the absence is REPORTED by name, never left as a silence a screen would read"

        payment_entries = ledger_models.JournalEntry.objects.filter(
            tenant=brazos, source_type="payment"
        ).count()
        assert (
            payment_entries == 0
        ), "a second entry here would be 25.00 of money the utility never gave away"
        payment = models.Payment.objects.get(pk=recorded.payment_id)
        assert payment.journal_entry_id is None
        assert payment.type == models.PAYMENT_TYPE_CREDIT


def test_cs38__the_ladder_does_not_chase_it(brazos, dana):
    """CS-38's third named proof: **the ladder does not chase the 25.00.**

    `ladder.run_ladder` reads `billing_seam.outstanding_positions`, which is now
    net of the credit the utility holds. The decision it records therefore names
    222.30 and never 247.30 — so the notice that goes out, and the amount it
    quotes, agree with the letter the customer already has.

    ⚠ **THIS DOES NOT FIX `DEF-3121` AND MUST NOT BE READ AS IF IT HAD.** An
    approved write-off writes no payment and no credit row, so an account
    carrying one has an unchanged credit position and is still chased in full.
    That defect stays open.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        a_gt6_bill(brazos, account)
        a_concession(dana, account)

        result = ladder.run_ladder(
            account_ids=(account.pk,),
            as_of=AS_OF,
            actor=dana,
            balance_floor=Decimal("25.00"),
            partial_pause_percent=Decimal("0"),
        )
        chased = [
            decision for decision in result.decisions if str(decision.account_id) == str(account.pk)
        ]
        assert chased, "the account is still a debtor — 222.30 is real and still owed"
        assert chased[0].balance == GT6_OWED, (
            "the ladder chases 222.30, not the 247.30 the bill says. The 25.00 the "
            "customer was told about is not chased."
        )


def test_cs38__the_bill_is_untouched(brazos, dana):
    """`OQ-215` is OPEN and this lane may not decide it.

    The concession is recorded with the carry-credit allocation order, so NO
    allocation row is written against the bill it came from and the bill's own
    open balance is unchanged at 247.30. Recording it oldest-first would have
    settled 25.00 of that bill — OQ-215's FIRST reading — on a money path, with
    no ruling. This case fails if a later lane simplifies the order back to the
    default.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        bill = a_gt6_bill(brazos, account)
        a_concession(dana, account)

        assert models.Allocation.objects.filter(invoice_id=bill.pk).count() == 0, (
            "the concession meets no bill: OQ-215 asks whether it should and says "
            "the answer is not an implementer's to pick"
        )
        position = billing_seam.open_invoices_for_account(account.pk)
        assert position.invoices[0].balance == GT6_BILL_TOTAL


def test_cs38__replaying_the_same_credit_note_writes_one_row(brazos, dana):
    """Hard rule 6 — the credit note is the key.

    A correction replayed after a crash finds the credit row it already wrote
    and returns it with `created=False`. A second 25.00 would be money invented
    by a retry, which is the exact failure idempotency exists to prevent.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        a_gt6_bill(brazos, account)
        note_id = uuid.uuid4()

        first = a_concession(dana, account, reference=note_id)
        second = a_concession(dana, account, reference=note_id)

        assert first.created is True
        assert second.created is False
        assert second.payment_id == first.payment_id
        assert models.Payment.objects.filter(tenant=brazos).count() == 1

        from apps.payments import selectors

        assert selectors.account_credit_position(account.pk) == GT6_CONCESSION


# ══ CS-35 · THE THREE THINGS THAT BRANCH ON THE TYPE ═══════════════════════


def test_cs35__the_type_is_accepted_and_written(brazos, dana):
    """The column has held three values since the first migration; nothing had
    ever written two of them, and the recording path did not take the argument.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        recorded = services.record_payment(
            dana,
            account_id=account.pk,
            amount=Decimal("40.00"),
            posted_at=POSTED_AT,
            cleared_at=POSTED_AT,
            payment_type=models.PAYMENT_TYPE_ADJUSTMENT,
            reason_code=GOODWILL,
            idempotency_reference=uuid.uuid4(),
        )
        assert models.Payment.objects.get(pk=recorded.payment_id).type == "adjustment"

        with pytest.raises(PaymentRuleError, match="is not a payment type"):
            services.record_payment(
                dana,
                account_id=account.pk,
                amount=Decimal("1.00"),
                posted_at=POSTED_AT,
                payment_type="refund",
                reason_code=GOODWILL,
                idempotency_reference=uuid.uuid4(),
            )


def test_cs35__a_credit_needs_a_reason_and_a_payment_may_not_carry_one(brazos, dana):
    """CS-35: *"it carries a reason from a tenant-maintained list"*.

    Both directions, because only the pair is the rule: a credit without a
    reason cannot answer *"how much did we give away last year, and why"*, and a
    payment WITH one would file real cash under a giveaway reason where a report
    would count it.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        with pytest.raises(PaymentRuleError, match="carries a reason"):
            services.record_payment(
                dana,
                account_id=account.pk,
                amount=Decimal("10.00"),
                posted_at=POSTED_AT,
                payment_type=models.PAYMENT_TYPE_CREDIT,
                idempotency_reference=uuid.uuid4(),
            )
        with pytest.raises(PaymentRuleError, match="a payment carries no reason code"):
            services.record_payment(
                dana,
                account_id=account.pk,
                amount=Decimal("10.00"),
                posted_at=POSTED_AT,
                reason_code=GOODWILL,
                idempotency_reference=uuid.uuid4(),
            )


def test_cs35__an_unknown_reason_is_refused_rather_than_defaulted(brazos, dana):
    """A credit filed under a reason nobody recognises is worse than none.

    The refusal comes from `ledger_seam.credit_adjustment_debit_account_id`,
    which owns the list read — one membership test, not two that could disagree.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        with pytest.raises(PaymentRuleError, match="not one of this utility's active reasons"):
            services.record_payment(
                dana,
                account_id=account.pk,
                amount=Decimal("10.00"),
                posted_at=POSTED_AT,
                cleared_at=POSTED_AT,
                payment_type=models.PAYMENT_TYPE_CREDIT,
                reason_code="not_a_reason_anybody_seeded",
                idempotency_reference=uuid.uuid4(),
            )
        assert (
            models.Payment.objects.filter(tenant=brazos).count() == 0
        ), "nothing partial is written — the refusal lands before the row commits"


def test_cs35__branch_2_the_gl_account_is_never_undeposited_funds(brazos, dana):
    """CS-35: *"it posts to its own ledger account, not to undeposited funds"*.

    A manual credit with an unmapped reason debits the ruled `write_off`
    designation — the same account a goodwill concession debits (PO 2026-08-12,
    *"a separate write-off account"*), so the two paths cannot drift — and
    credits receivables for what it met. Worked here on 40.00 against the
    247.30 bill: DR 6900 write-off 40.00 / CR 1200 AR 40.00.

    **Nothing debits 1010 Undeposited funds, and that is the assertion that
    matters:** no cash arrived, no bank line will ever mention it, and money in
    a holding account with nothing coming to clear it is a reconciliation that
    can never be finished.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        a_gt6_bill(brazos, account)
        services.record_payment(
            dana,
            account_id=account.pk,
            amount=Decimal("40.00"),
            posted_at=POSTED_AT,
            cleared_at=POSTED_AT,
            payment_type=models.PAYMENT_TYPE_CREDIT,
            reason_code=GOODWILL,
            idempotency_reference=uuid.uuid4(),
        )
        legs = journal_legs(brazos)
        assert leg(legs, "6900", "debit") == Decimal("40.00")
        assert leg(legs, "1200", "credit") == Decimal("40.00")
        assert leg(legs, "1010", "debit") == Decimal(
            "0"
        ), "a credit is not cash and never debits undeposited funds"
        assert sum(amount for _, side, amount in legs if side == "debit") == sum(
            amount for _, side, amount in legs if side == "credit"
        ), "balanced pairs (hard rule 5)"


def test_cs35__branch_1_a_credit_is_never_swept_into_a_deposit_batch(brazos, dana):
    """CS-35: *"the BATCHING branch is the one that matters; without it every
    adjustment silently corrupts the deposit total."*

    A cash payment and a credit on the SAME drawer day. The batch total is the
    cash alone, the credit is not a member of any batch, and — the half that was
    missing — the credit is NAMED in the cut result rather than dropped, so a
    clerk whose drawer does not tie can be told why.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        a_gt6_bill(brazos, account)
        cash = services.record_payment(
            dana,
            account_id=account.pk,
            amount=Decimal("100.00"),
            posted_at=POSTED_AT,
            cleared_at=POSTED_AT,
            method_code="cash",
            idempotency_reference=uuid.uuid4(),
        )
        credit = services.record_payment(
            dana,
            account_id=account.pk,
            amount=Decimal("25.00"),
            posted_at=POSTED_AT,
            cleared_at=POSTED_AT,
            payment_type=models.PAYMENT_TYPE_CREDIT,
            reason_code=GOODWILL,
            idempotency_reference=uuid.uuid4(),
        )
        result = reconciliation.cut_deposit_batches(actor=dana, day=ON_DATE, occurred_at=POSTED_AT)
        assert len(result.batches) == 1
        assert result.batches[0].recorded_total == Decimal(
            "100.0000"
        ), "the day's banking is the CASH alone — a concession never went to the bank"
        assert result.payments_batched == 1
        named = {row["payment_id"]: row for row in result.skipped}
        assert credit.payment_id in named, (
            "CS-35: a credit is named in the result rather than dropped. Before this "
            "lane the query excluded it, so a drawer that did not tie could not be "
            "explained from the cut at all."
        )
        assert named[credit.payment_id]["reason"] == "not_cash"
        assert models.Payment.objects.get(pk=credit.payment_id).deposit_batch_id is None
        assert models.Payment.objects.get(pk=cash.payment_id).deposit_batch_id is not None


def test_cs35__branch_3_above_the_threshold_a_clerk_may_not_record_a_credit(brazos, marcus, dana):
    """CS-35: *"requires Admin approval above a tenant-set threshold, matching
    write-offs"*, and the threshold is seeded **0.00** — so today every credit
    needs a System Admin.

    Server-enforced: a screen that hides the button is not an authorisation
    (BR-SHL-025). The clerk may still record a PAYMENT of the same amount,
    which is the line the control is drawing — taking money is not giving it
    away.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        with pytest.raises(PaymentRuleError, match="above this utility's approval threshold"):
            services.record_payment(
                marcus,
                account_id=account.pk,
                amount=Decimal("25.00"),
                posted_at=POSTED_AT,
                cleared_at=POSTED_AT,
                payment_type=models.PAYMENT_TYPE_CREDIT,
                reason_code=GOODWILL,
                idempotency_reference=uuid.uuid4(),
            )
        assert models.Payment.objects.filter(tenant=brazos).count() == 0

        # The same clerk, the same amount, as MONEY RECEIVED — allowed.
        services.record_payment(
            marcus,
            account_id=account.pk,
            amount=Decimal("25.00"),
            posted_at=POSTED_AT,
            cleared_at=POSTED_AT,
            method_code="cash",
            idempotency_reference=uuid.uuid4(),
        )
        assert models.Payment.objects.filter(tenant=brazos).count() == 1


def test_cs35__a_payment_may_not_claim_it_was_posted_elsewhere(brazos, dana):
    """The one-posting switch is lawful only on a credit or an adjustment.

    A receipt excused from the books is cash the trial balance would never show
    — a hole with no name, which is why this is a refusal and not a default.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        with pytest.raises(PaymentRuleError, match="only a credit or an adjustment"):
            services.record_payment(
                dana,
                account_id=account.pk,
                amount=Decimal("10.00"),
                posted_at=POSTED_AT,
                cleared_at=POSTED_AT,
                already_posted_source="credit_note",
                idempotency_reference=uuid.uuid4(),
            )


# ══ THE CHASE, NET OF HELD CREDIT — AND WHAT IT DOES NOT DO ════════════════


def test_cs38__a_negative_credit_does_not_increase_the_chase(brazos, dana):
    """BR-PAY-041 is untouched, and the narrower judgment is asserted.

    A negative credit is a real debt (PO 2026-08-11, *"Yes, it's a real debt"*)
    and nothing floors the FIGURE — `account_credit_position` still returns it
    signed. What this lane decided, and recorded in the decision log, is that it
    does not ADD to a bill-based chase: there is no bill behind it, and a
    ten-day disconnect notice would state that bills are unpaid which are not.
    It is reported by name instead of being silently dropped.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        a_gt6_bill(brazos, account)
        # A refund taken against a credit that a later reversal removed is the
        # frozen J15 chain's shape; produced here directly, because what is
        # under test is how the CHASE reads a negative position, not how one is
        # arrived at.
        models.Payment.objects.create(
            tenant=brazos,
            account=account,
            payment_no="PMT-NEGATIVE",
            type=models.PAYMENT_TYPE_PAYMENT,
            amount=Decimal("-57.13"),
            currency="USD",
            status=models.PAYMENT_REVERSED,
            purpose=models.PURPOSE_BILL,
            posted_at=POSTED_AT,
            cleared_at=POSTED_AT,
        )
        from apps.payments import selectors

        assert selectors.account_credit_position(account.pk) == Decimal(
            "-57.13"
        ), "signed, and never floored (BR-PAY-041)"
        positions, problems = billing_seam.outstanding_positions(account_ids=[account.pk])
        assert (
            positions[0].balance == GT6_BILL_TOTAL
        ), "the chase is the bills alone — the negative credit does not inflate it"
        assert positions[0].credit_applied == Decimal("0")
        assert any(problem["code"] == "negative_credit_not_added_to_chase" for problem in problems)


def test_cs38__the_bulk_credit_read_agrees_with_the_single_account_read(brazos, dana):
    """Two implementations of one rule is how two figures come to disagree.

    `billing_seam._credit_positions` is the bulk form of
    `selectors.account_credit_position`; this is the case that stops them
    drifting. A deposit is excluded by both (US-PAY-002 TC-1 — held, never
    credit) and a `processing` payment by both (the money has not arrived).
    """
    from apps.payments import selectors

    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        a_gt6_bill(brazos, account)
        a_concession(dana, account)
        services.record_payment(
            dana,
            account_id=account.pk,
            amount=Decimal("150.00"),
            posted_at=POSTED_AT,
            purpose=models.PURPOSE_DEPOSIT,
            method_code="cash",
            cleared_at=POSTED_AT,
            idempotency_reference=uuid.uuid4(),
        )
        bulk = billing_seam._credit_positions([account.pk])
        assert bulk[account.pk] == selectors.account_credit_position(account.pk)
        assert bulk[account.pk] == GT6_CONCESSION, (
            "the 150.00 deposit is HELD, not credit — the utility owes it back at "
            "move-out and must not spend it on the next bill"
        )
